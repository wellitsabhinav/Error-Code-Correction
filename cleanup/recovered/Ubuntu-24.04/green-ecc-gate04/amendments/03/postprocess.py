#!/usr/bin/env python3
"""Validate, reduce, and adjudicate the complete frozen Gate 04 matrix."""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import random
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "docs/date2027/rigour_gate_04"
BASELINE = "secded-rtl-combinational-72-64-v1"
PIPELINE = "secded-rtl-pipelined-72-64-v1"
CANDIDATES = (BASELINE, PIPELINE, "hsiao-generated-combinational-72-64-v1", "shortened-bch-78-64-t2-v1-rtl-syndrome-chien-v1")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def last_metric(run_root: Path, key: str) -> tuple[float, str, int]:
    records = json.loads((run_root / "metric-occurrences.json").read_text(encoding="utf-8"))
    matches = [record for record in records if record["key"] == key and isinstance(record["value"], (int, float))]
    if not matches:
        raise ValueError(f"metric {key} missing from {run_root}")
    record = matches[-1]
    return float(record["value"]), str(record["source"]), int(record["key_occurrence"])


def parse_power(path: Path) -> dict[str, float]:
    value = json.loads(path.read_text(encoding="utf-8"))
    total = value.get("Total")
    if not isinstance(total, dict):
        raise ValueError(f"Total power group missing: {path}")
    return {name: float(total[name]) for name in ("internal", "switching", "leakage", "total")}


def annotation(path: Path) -> tuple[int, int]:
    text = path.read_text(encoding="utf-8", errors="replace")
    vcd = re.search(r"(?m)^vcd\s+(\d+)\s*$", text)
    unannotated = re.search(r"(?m)^unannotated\s+(\d+)\s*$", text)
    if not vcd or not unannotated:
        raise ValueError(f"annotation counts missing: {path}")
    return int(vcd.group(1)), int(unannotated.group(1))


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def bootstrap_ci(values: list[float], *, seed: int, resamples: int) -> tuple[float, float]:
    rng = random.Random(seed)
    samples = [statistics.median(rng.choices(values, k=len(values))) for _ in range(resamples)]
    return percentile(samples, 0.025), percentile(samples, 0.975)


def summary(values: list[float]) -> dict[str, float]:
    return {
        "minimum": min(values), "q1": percentile(values, 0.25),
        "median": statistics.median(values), "q3": percentile(values, 0.75),
        "maximum": max(values), "iqr": percentile(values, 0.75) - percentile(values, 0.25),
    }


def validate_protected_bytes(out: Path) -> tuple[bool, list[str]]:
    manifest = json.loads((out / "STARTING_PROTECTED_BYTE_MANIFEST.json").read_text(encoding="utf-8"))
    failures: list[str] = []
    for record in manifest["files"]:
        path = ROOT / record["path"]
        if not path.is_file() or path.stat().st_size != record["bytes"] or sha256(path) != record["sha256"]:
            failures.append(record["path"])
    return not failures, failures


def validated_attempt(run_root: Path, metadata: dict[str, object]) -> bool:
    validation_path = run_root / "run-validation.json"
    administrative_adjudication = any(
        path.is_file() and json.loads(path.read_text(encoding="utf-8")).get("status") == "PASS"
        for path in (run_root / "amendment03-validation-metadata.json", run_root / "amendment02-validation-metadata.json")
    )
    return bool(
        validation_path.is_file()
        and json.loads(validation_path.read_text(encoding="utf-8"))["status"] == "PASS"
        and (metadata.get("exit_status") == 0 or administrative_adjudication)
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-root", type=Path, default=Path("/var/lib/green-ecc-gate04"))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    evidence = args.evidence_root.resolve()
    policy = evidence / "policy"
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    contract = json.loads((ROOT / "scripts/gate04/contract_v1.json").read_text(encoding="utf-8"))
    frozen_matrix = read_csv(policy / "repo_snapshot/docs/date2027/rigour_gate_04/FLOW_RUN_MATRIX.csv")

    policy_hash_failures: list[str] = []
    for line in (policy / "frozen-bundle.sha256").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split(maxsplit=1)
        relative = relative.lstrip("*")
        path = policy / relative
        if not path.is_file() or sha256(path) != expected:
            policy_hash_failures.append(relative)

    final_matrix: list[dict[str, object]] = []
    ppa_by_run: dict[tuple[str, float, int], dict[str, object]] = {}
    power_by_key: dict[tuple[str, float, int, str, str], dict[str, float]] = {}
    ppa_rows: list[dict[str, object]] = []
    power_rows: list[dict[str, object]] = []
    blockers: list[str] = []
    external_rows: list[dict[str, object]] = []
    raw_log_rows: list[dict[str, object]] = []
    retry_rows: list[dict[str, object]] = []

    ppa_metrics = {
        "die_area_um2": ("finish__design__die__area", "um^2"),
        "stdcell_area_um2": ("finish__design__instance__area__stdcell", "um^2"),
        "setup_worst_slack_ns": ("finish__timing__setup__ws", "ns"),
        "fmax_hz": ("finish__timing__fmax", "Hz"),
        "sequential_cells": ("finish__design__instance__count__class:sequential_cell", "count"),
        "total_instances": ("finish__design__instance__count", "count"),
    }

    for planned in frozen_matrix:
        row: dict[str, object] = dict(planned)
        base_id = planned["run_id"].removesuffix("-attempt1")
        attempt_roots = sorted((evidence / "runs").glob(base_id + "-attempt*"))
        selected_root: Path | None = None
        for attempt_root in attempt_roots:
            attempt_metadata_path = attempt_root / "run-metadata.json"
            attempt_validation_path = attempt_root / "run-validation.json"
            attempt_metadata = json.loads(attempt_metadata_path.read_text(encoding="utf-8")) if attempt_metadata_path.is_file() else {}
            attempt_passed = validated_attempt(attempt_root, attempt_metadata)
            retry_rows.append(
                {
                    "planned_run_id": planned["run_id"], "attempt_run_id": attempt_root.name,
                    "attempt": attempt_root.name.rsplit("attempt", 1)[-1],
                    "status": "PASS" if attempt_passed else "FAIL",
                    "exit_status": attempt_metadata.get("exit_status", "UNAVAILABLE"),
                    "failure_reason": attempt_metadata.get("failure_reason", "metadata or validation missing"),
                    "run_directory": attempt_root.as_posix(),
                    "raw_manifest": (attempt_root / "raw-artifacts.sha256").as_posix() if (attempt_root / "raw-artifacts.sha256").is_file() else "UNAVAILABLE",
                }
            )
            if attempt_passed and selected_root is None:
                selected_root = attempt_root
        run_root = selected_root or (attempt_roots[-1] if attempt_roots else evidence / "runs" / planned["run_id"])
        metadata_path = run_root / "run-metadata.json"
        if not metadata_path.is_file():
            row.update(status="MISSING", failure_reason="run directory or metadata missing", resolved_run_id="UNAVAILABLE")
            blockers.append(f"missing run {planned['run_id']}")
            final_matrix.append(row)
            continue
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        validation_path = run_root / "run-validation.json"
        passed = validated_attempt(run_root, metadata)
        row.update(
            status="PASS" if passed else "FAIL",
            resolved_run_id=run_root.name,
            exit_status=metadata["exit_status"], start_time_utc=metadata["start_time_utc"],
            end_time_utc=metadata["end_time_utc"], failure_reason=metadata.get("failure_reason", ""),
        )
        final_matrix.append(row)
        if not passed:
            blockers.append(f"failed run {planned['run_id']}: {metadata.get('failure_reason', '')}")
            continue

        raw_manifests = [run_root / "raw-artifacts.sha256"]
        if (run_root / "raw-artifacts-amendment03.sha256").is_file():
            raw_manifests.append(run_root / "raw-artifacts-amendment03.sha256")
        if (run_root / "raw-artifacts-amendment02.sha256").is_file():
            raw_manifests.append(run_root / "raw-artifacts-amendment02.sha256")
        for raw_manifest in raw_manifests:
            for line in raw_manifest.read_text(encoding="utf-8").splitlines():
                expected, relative = line.split(maxsplit=1)
                relative = relative.lstrip("*")
                path = run_root / relative
                if not path.is_file() or sha256(path) != expected:
                    blockers.append(f"raw hash mismatch {run_root.name}/{relative}")
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
        impl = planned["implementation_id"]
        clock = float(planned["clock_period_ns"])
        seed = int(planned["physical_seed"])
        metrics: dict[str, object] = {"timing_met": validation["timing_met"]}
        for metric_name, (source_key, unit) in ppa_metrics.items():
            value, source, occurrence = last_metric(run_root, source_key)
            metrics[metric_name] = value
            ppa_rows.append(
                {
                    "implementation_id": impl, "clock_period_ns": clock, "physical_seed": seed,
                    "workload_fault_trace": "NOT_APPLICABLE", "metric": metric_name, "value": value, "unit": unit,
                    "source_artifact": f"external:{run_root.name}/{source}",
                    "source_field": source_key, "source_key_occurrence": occurrence,
                    "evidence_class": "SYNTHESIZED", "calculation": "last ordered producer occurrence; all occurrences retained in metric-occurrences.json",
                    "validation_status": "PASS",
                }
            )
        ppa_by_run[(impl, clock, seed)] = metrics

        for power_path in sorted((run_root / "power").glob("*.power.json")):
            label = power_path.name.removesuffix(".power.json")
            family, trace = label.rsplit("-", 1)
            if trace == "error":
                # labels end in no_error/single_error/double_error; recover both words.
                match = re.match(r"(.+)-(no_error|single_error|double_error)$", label)
                if not match:
                    raise ValueError(label)
                family, trace = match.groups()
            values = parse_power(power_path)
            vcd_count, unannotated_count = annotation(power_path.with_name(label + ".annotation.rpt"))
            power_by_key[(impl, clock, seed, family, trace)] = values
            throughput = 1.0 / (clock * 1e-9) if metrics["timing_met"] else math.nan
            energy = values["total"] / throughput if math.isfinite(throughput) else math.nan
            power_rows.append(
                {
                    "implementation_id": impl, "clock_period_ns": clock, "physical_seed": seed,
                    "workload_fault_trace": trace, "activity_family": family,
                    "internal_power_w": values["internal"], "switching_power_w": values["switching"],
                    "leakage_power_w": values["leakage"], "total_power_w": values["total"],
                    "achieved_useful_throughput_ops_s": throughput if math.isfinite(throughput) else "UNRESOLVED_TIMING_UNMET",
                    "energy_per_useful_operation_j": energy if math.isfinite(energy) else "UNRESOLVED_TIMING_UNMET",
                    "direct_vcd_annotated_pins": vcd_count, "unannotated_pins": unannotated_count,
                    "unit": "W; op/s; J/op", "source_artifact": f"external:{run_root.name}/power/{power_path.name}",
                    "source_field": "Total.{internal,switching,leakage,total}; report_activity_annotation",
                    "evidence_class": "SYNTHESIZED", "calculation": "OpenSTA read_vcd post-route activity propagation; energy=P/(1/period) only when setup timing met",
                    "validation_status": "PASS" if metrics["timing_met"] else "POWER_PASS_ENERGY_UNRESOLVED_TIMING_UNMET",
                }
            )

        for path in sorted(item for item in run_root.rglob("*") if item.is_file()):
            rel = path.relative_to(evidence).as_posix()
            record = {"run_id": run_root.name, "path": rel, "bytes": path.stat().st_size, "sha256": sha256(path), "evidence_class": "SYNTHESIZED"}
            external_rows.append(record)
            if "/logs/" in f"/{rel}" or path.suffix in {".log", ".rpt"}:
                raw_log_rows.append(record)

    write_csv(out / "FLOW_RUN_MATRIX.csv", final_matrix, list(final_matrix[0]))
    write_csv(out / "RETRY_LEDGER.csv", retry_rows, ["planned_run_id", "attempt_run_id", "attempt", "status", "exit_status", "failure_reason", "run_directory", "raw_manifest"])

    # Failed attempts remain indexed even when a later visible retry succeeds.
    indexed_paths = {str(record["path"]) for record in external_rows}
    for attempt_root in sorted(path for path in (evidence / "runs").glob("*") if path.is_dir()):
        for path in sorted(item for item in attempt_root.rglob("*") if item.is_file()):
            rel = path.relative_to(evidence).as_posix()
            if rel in indexed_paths:
                continue
            record = {"run_id": attempt_root.name, "path": rel, "bytes": path.stat().st_size, "sha256": sha256(path), "evidence_class": "SYNTHESIZED"}
            external_rows.append(record)
            if "/logs/" in f"/{rel}" or path.suffix in {".log", ".rpt"}:
                raw_log_rows.append(record)
            indexed_paths.add(rel)

    # Explicit paired reference subtraction; raw candidate and raw reference values remain primary evidence.
    for impl in CANDIDATES:
        reference = "boundary-reference-78-64-v1" if "bch-78" in impl else "boundary-reference-72-64-v1"
        family = "bch78" if "bch-78" in impl else ("hsiao" if impl.startswith("hsiao") else "conventional_secded")
        for clock in (10.0, 5.0):
            for seed in (11, 29, 47, 71, 101):
                candidate = ppa_by_run.get((impl, clock, seed))
                boundary = ppa_by_run.get((reference, clock, seed))
                if candidate and boundary:
                    delta = float(candidate["stdcell_area_um2"]) - float(boundary["stdcell_area_um2"])
                    ppa_rows.append(
                        {
                            "implementation_id": impl, "clock_period_ns": clock, "physical_seed": seed,
                            "workload_fault_trace": "NOT_APPLICABLE", "metric": "codec_plus_candidate_retained_interface_area_minus_boundary_reference_um2",
                            "value": delta, "unit": "um^2", "source_artifact": f"paired external runs {impl} and {reference}",
                            "source_field": "finish__design__instance__area__stdcell", "source_key_occurrence": "last in each run",
                            "evidence_class": "DERIVED", "calculation": "candidate stdcell area - width-matched boundary-reference stdcell area",
                            "validation_status": "PASS" if delta >= 0 else "UNRESOLVED_NEGATIVE_REFERENCE_SUBTRACTION",
                        }
                    )
                for trace in ("no_error", "single_error", "double_error"):
                    candidate_power = power_by_key.get((impl, clock, seed, family, trace))
                    boundary_power = power_by_key.get((reference, clock, seed, family, trace))
                    if candidate_power and boundary_power:
                        delta_power = candidate_power["total"] - boundary_power["total"]
                        power_rows.append(
                            {
                                "implementation_id": impl, "clock_period_ns": clock, "physical_seed": seed,
                                "workload_fault_trace": trace, "activity_family": family,
                                "internal_power_w": "NOT_SEPARATELY_DEEMBEDDED", "switching_power_w": "NOT_SEPARATELY_DEEMBEDDED",
                                "leakage_power_w": "NOT_SEPARATELY_DEEMBEDDED", "total_power_w": delta_power,
                                "achieved_useful_throughput_ops_s": "SEE_RAW_CANDIDATE_ROW",
                                "energy_per_useful_operation_j": delta_power * clock * 1e-9 if ppa_by_run[(impl, clock, seed)]["timing_met"] else "UNRESOLVED_TIMING_UNMET",
                                "direct_vcd_annotated_pins": "PAIRED", "unannotated_pins": "PAIRED",
                                "unit": "W; J/op", "source_artifact": f"paired external runs {impl} and {reference}",
                                "source_field": "Total.total", "evidence_class": "DERIVED",
                                "calculation": "candidate total post-route power - width-matched reference under identical VCD",
                                "validation_status": "PASS" if delta_power >= 0 else "UNRESOLVED_NEGATIVE_REFERENCE_SUBTRACTION",
                            }
                        )

    write_csv(out / "PPA_RESULTS.csv", ppa_rows, list(ppa_rows[0]) if ppa_rows else [])
    write_csv(out / "POWER_RESULTS.csv", power_rows, list(power_rows[0]) if power_rows else [])
    write_csv(out / "EXTERNAL_ARTIFACT_INDEX.csv", external_rows, ["run_id", "path", "bytes", "sha256", "evidence_class"])
    write_csv(out / "RAW_LOG_INDEX.csv", raw_log_rows, ["run_id", "path", "bytes", "sha256", "evidence_class"])

    protected_ok, protected_failures = validate_protected_bytes(out)
    if not protected_ok:
        blockers.append(f"historical/protected raw bytes changed: {protected_failures[:10]}")
    if policy_hash_failures:
        blockers.append(f"frozen policy hashes failed: {policy_hash_failures[:10]}")

    # Paired statistics and H2.
    statistical: list[dict[str, object]] = []
    h2_effects: list[dict[str, object]] = []
    bootstrap_seed = int(contract["statistics"]["bootstrap_seed"])
    resamples = int(contract["statistics"]["bootstrap_resamples"])
    for clock in (10.0, 5.0):
        for impl in CANDIDATES:
            for metric in ("stdcell_area_um2", "fmax_hz", "sequential_cells"):
                values = [float(ppa_by_run[(impl, clock, seed)][metric]) for seed in (11, 29, 47, 71, 101) if (impl, clock, seed) in ppa_by_run]
                if len(values) == 5:
                    statistical.append({"implementation_id": impl, "clock_period_ns": clock, "metric": metric, **summary(values), "unit": "um^2" if "area" in metric else ("Hz" if metric == "fmax_hz" else "count")})
        for metric in ("stdcell_area_um2", "fmax_hz"):
            differences: list[float] = []
            for seed in (11, 29, 47, 71, 101):
                if (PIPELINE, clock, seed) in ppa_by_run and (BASELINE, clock, seed) in ppa_by_run:
                    pipe = float(ppa_by_run[(PIPELINE, clock, seed)][metric])
                    comb = float(ppa_by_run[(BASELINE, clock, seed)][metric])
                    differences.append((pipe - comb) / comb)
            if len(differences) == 5:
                low, high = bootstrap_ci(differences, seed=bootstrap_seed + int(clock) + len(metric), resamples=resamples)
                effect = {"clock_period_ns": clock, "metric": metric, "paired_fractional_differences": differences, "median_fractional_difference": statistics.median(differences), "bootstrap_95_low": low, "bootstrap_95_high": high, "interval_excludes_zero": low > 0 or high < 0}
                h2_effects.append(effect)
    write_json(out / "STATISTICAL_SUMMARY.json", {"schema_version": 1, "bootstrap_seed": bootstrap_seed, "bootstrap_resamples": resamples, "summaries": statistical, "h2_effects": h2_effects})

    # Implementation-aware exhaustive DSE.
    reliability_rows = read_csv(out / "RELIABILITY_RESULTS.csv")
    reliability = {
        (row["implementation_id"], row["fault_model"], row["logical_physical_mapping"], int(row["interleaving_factor"])): (float(row["residual_sdc_probability"]), float(row["due_probability"]))
        for row in reliability_rows
    }
    scenario = contract["scenario_matrix"]
    dse_rows: list[dict[str, object]] = []
    changed_scenarios: set[str] = set()
    selectors = ("fixed_conventional_combinational_secded", "mathematical_code_only", "current_verified_analytical_selector", "implementation_aware_exhaustive")
    math_default = {BASELINE: BASELINE, PIPELINE: BASELINE, CANDIDATES[2]: CANDIDATES[2], CANDIDATES[3]: CANDIDATES[3]}
    scenario_index = 0
    for factors in itertools.product(
        scenario["fault_models"], scenario["logical_physical_mappings"], scenario["interleaving_factors"],
        scenario["scrub_intervals_operations"], scenario["read_fractions"], scenario["error_conditioned_decoder_activity"],
        scenario["service_clock_constraints_ns"], scenario["max_conditional_residual_sdc"], scenario["max_conditional_due"],
        sorted(scenario["objective_profiles"]),
    ):
        fault, mapping, interleave, scrub, read_fraction, activity_class, clock, sdc_limit, due_limit, profile_name = factors
        scenario_index += 1
        scenario_id = f"S{scenario_index:05d}"
        exposure = min(1.0, float(scrub) / 1_000_000.0) * float(read_fraction)
        trace = "no_error" if activity_class == "nominal" else "double_error"
        weights = scenario["objective_profiles"][profile_name]
        for seed in (11, 29, 47, 71, 101):
            records: list[dict[str, object]] = []
            for impl in CANDIDATES:
                ppa = ppa_by_run.get((impl, float(clock), seed))
                family = "bch78" if "bch-78" in impl else ("hsiao" if impl.startswith("hsiao") else "conventional_secded")
                power = power_by_key.get((impl, float(clock), seed, family, trace))
                conditional_sdc, conditional_due = reliability[(impl, fault, mapping, int(interleave))]
                residual_sdc = conditional_sdc * exposure
                due = conditional_due * exposure
                feasible = bool(ppa and power and ppa["timing_met"] and residual_sdc <= float(sdc_limit) and due <= float(due_limit))
                records.append(
                    {
                        "implementation_id": impl, "n": 78 if "bch-78" in impl else 72,
                        "area": float(ppa["stdcell_area_um2"]) if ppa else math.nan,
                        "energy": float(power["total"]) * float(clock) * 1e-9 if power and ppa and ppa["timing_met"] else math.nan,
                        "residual_sdc": residual_sdc, "due": due, "feasible": feasible,
                        "timing_met": bool(ppa and ppa["timing_met"]),
                    }
                )
            feasible_records = [record for record in records if record["feasible"]]
            axes = ("area", "energy", "residual_sdc", "due")
            bounds = {axis: (min(float(record[axis]) for record in feasible_records), max(float(record[axis]) for record in feasible_records)) for axis in axes} if feasible_records else {}
            def score(record: dict[str, object]) -> float:
                if not record["feasible"]:
                    return math.inf
                total = 0.0
                for axis, weight_key in (("area", "stdcell_area"), ("energy", "energy"), ("residual_sdc", "residual_sdc"), ("due", "due")):
                    low, high = bounds[axis]
                    normalized = 0.0 if high <= low else (float(record[axis]) - low) / (high - low)
                    total += float(weights[weight_key]) * normalized
                return total
            for record in records:
                record["score"] = score(record)
            full = min(records, key=lambda record: (float(record["score"]), int(record["n"]), str(record["implementation_id"]))) if feasible_records else None
            math_feasible = [record for record in records if record["residual_sdc"] <= float(sdc_limit) and record["due"] <= float(due_limit)]
            math_selected = min(math_feasible, key=lambda record: (int(record["n"]), float(record["residual_sdc"]), float(record["due"]), str(record["implementation_id"]))) if math_feasible else None
            if math_selected:
                math_selected = next(record for record in records if record["implementation_id"] == math_default[str(math_selected["implementation_id"])])
            selected_by = {
                selectors[0]: next(record for record in records if record["implementation_id"] == BASELINE),
                selectors[1]: math_selected,
                selectors[2]: next(record for record in records if record["implementation_id"] == BASELINE),
                selectors[3]: full,
            }
            if full and any(record and record["implementation_id"] != full["implementation_id"] for name, record in selected_by.items() if name != selectors[3]):
                changed_scenarios.add(scenario_id)
            for selector_name, selected in selected_by.items():
                selected_score = float(selected["score"]) if selected else math.inf
                full_score = float(full["score"]) if full else math.inf
                regret = selected_score - full_score if math.isfinite(selected_score) and math.isfinite(full_score) else math.nan
                dse_rows.append(
                    {
                        "scenario_id": scenario_id, "selector": selector_name, "physical_seed": seed,
                        "fault_model": fault, "logical_physical_mapping": mapping, "interleaving_factor": interleave,
                        "scrub_interval_operations": scrub, "read_fraction": read_fraction,
                        "error_conditioned_activity": activity_class, "clock_period_ns": clock,
                        "max_residual_sdc": sdc_limit, "max_due": due_limit, "objective_profile": profile_name,
                        "selected_implementation_id": selected["implementation_id"] if selected else "NONE",
                        "feasible": bool(selected and selected["feasible"]),
                        "constraint_violation": "" if selected and selected["feasible"] else "timing_or_reliability_constraint",
                        "normalized_score": selected_score if math.isfinite(selected_score) else "UNAVAILABLE",
                        "normalized_regret_vs_exhaustive": regret if math.isfinite(regret) else "UNAVAILABLE",
                        "stdcell_area_um2": selected["area"] if selected else "UNAVAILABLE",
                        "energy_per_operation_j": selected["energy"] if selected else "UNAVAILABLE",
                        "residual_sdc_probability": selected["residual_sdc"] if selected else "UNAVAILABLE",
                        "due_probability": selected["due"] if selected else "UNAVAILABLE",
                        "unit": "dimensionless normalized score/regret; um^2; J/op; conditional probability",
                        "source_artifact": "PPA_RESULTS.csv; POWER_RESULTS.csv; RELIABILITY_RESULTS.csv; contract_v1.json",
                        "source_field": "frozen exhaustive scenario evaluation",
                        "evidence_class": "DERIVED", "calculation": "scenario-local min-max normalization and exhaustive four-implementation enumeration",
                        "validation_status": "PASS" if full else "NO_FEASIBLE_IMPLEMENTATION",
                    }
                )
    write_csv(out / "DSE_RESULTS.csv", dse_rows, list(dse_rows[0]) if dse_rows else [])

    h1_supported = len(changed_scenarios) >= 2
    h2_supported = any(abs(float(effect["median_fractional_difference"])) > 0.05 and effect["interval_excludes_zero"] for effect in h2_effects)
    exhaustive_rows = [row for row in dse_rows if row["selector"] == "implementation_aware_exhaustive" and row["selected_implementation_id"] != "NONE"]
    h3_groups: dict[tuple[object, ...], set[str]] = defaultdict(set)
    for row in exhaustive_rows:
        key = (row["fault_model"], row["logical_physical_mapping"], row["scrub_interval_operations"], row["read_fraction"], row["error_conditioned_activity"], row["clock_period_ns"], row["max_residual_sdc"], row["max_due"], row["objective_profile"], row["physical_seed"])
        # Interleaving is intentionally omitted: this is a stratified interaction test.
        h3_groups[key].add(str(row["selected_implementation_id"]))
    h3_changed_strata = sum(len(values) > 1 for values in h3_groups.values())
    h3_supported = h3_changed_strata > 0
    hypotheses = {
        "schema_version": 1,
        "H1": {"supported": h1_supported, "changed_preregistered_scenarios": len(changed_scenarios), "threshold": "at least two scenarios or >5% paired regret CI"},
        "H2": {"supported": h2_supported, "distinct_rtl_sequential_invariant": True, "paired_effects": h2_effects, "threshold": ">5% and paired bootstrap 95% interval excludes zero"},
        "H3": {"supported": h3_supported, "interleaving_strata_with_selected_implementation_change": h3_changed_strata, "method": "stratified full-exhaustive selection holding all listed factors except interleaving fixed"},
        "H4": {"supported": False, "reason": "no independently varied calibrated carbon factor; operational-carbon ranking would duplicate energy"},
    }
    write_json(out / "HYPOTHESIS_RESULTS.json", hypotheses)
    (out / "HYPOTHESIS_RESULTS.md").write_text(
        "# Gate 04 hypothesis results\n\n" + "\n".join(f"- {name}: **{'SUPPORTED' if result['supported'] else 'NOT SUPPORTED'}** — {result.get('reason', result.get('method', result.get('threshold', 'frozen test')))}" for name, result in hypotheses.items() if name.startswith("H")) + "\n",
        encoding="utf-8", newline="\n",
    )

    physical_complete = not blockers and len(ppa_by_run) == 60
    if physical_complete and h1_supported and (h2_supported or h3_supported):
        verdict = "ASIC_EVIDENCE_COMPLETE_MATERIAL_SELECTION_EFFECT"
    elif physical_complete:
        verdict = "ASIC_EVIDENCE_COMPLETE_NO_MATERIAL_SELECTION_EFFECT"
    else:
        verdict = "ASIC_EXPERIMENT_BLOCKED"

    claims_rows = [
        {"claim_id": "C01", "claim": "All mandatory Gate 04 physical flows and references completed under the freeze", "status": "SUPPORTED" if physical_complete else "BLOCKED", "evidence_class": "SYNTHESIZED", "evidence": "FLOW_RUN_MATRIX.csv; EXTERNAL_ARTIFACT_INDEX.csv", "restriction": "tool-derived, not silicon measurement"},
        {"claim_id": "C02", "claim": "Activity-based codec power is post-route OpenSTA estimation", "status": "SUPPORTED" if physical_complete else "BLOCKED", "evidence_class": "SYNTHESIZED", "evidence": "POWER_RESULTS.csv", "restriction": "primary-input VCD with propagated internal activity; direct/unannotated counts reported"},
        {"claim_id": "C03", "claim": "Same-code physical implementation identity has a material paired effect", "status": "SUPPORTED" if h2_supported else "NOT_SUPPORTED", "evidence_class": "DERIVED", "evidence": "HYPOTHESIS_RESULTS.json", "restriction": "conditional on SKY130HD pinned flow"},
        {"claim_id": "C04", "claim": "Implementation-aware selection has a material frozen-scenario effect", "status": "SUPPORTED" if h1_supported else "NOT_SUPPORTED", "evidence_class": "DERIVED", "evidence": "DSE_RESULTS.csv", "restriction": "no global optimality beyond enumerated four-candidate space"},
        {"claim_id": "C05", "claim": "SRAM macro area and energy", "status": "UNRESOLVED", "evidence_class": "UNRESOLVED", "evidence": "FAIRNESS_CONTRACT.md", "restriction": "no common characterized SRAM macro"},
        {"claim_id": "C06", "claim": "Silicon measurement, foundry signoff, publication readiness, independent reproduction", "status": "PROHIBITED", "evidence_class": "UNRESOLVED", "evidence": "EXPERIMENT_FREEZE.md", "restriction": "not claimed"},
    ]
    write_csv(out / "CLAIMS_LEDGER.csv", claims_rows, list(claims_rows[0]))
    (out / "GATE_04_VERDICT.txt").write_text(verdict + "\n", encoding="utf-8", newline="\n")

    write_json(out / "POSTPROCESS_VALIDATION.json", {"schema_version": 1, "status": "PASS" if physical_complete else "FAIL", "verdict": verdict, "blockers": blockers, "policy_hash_failures": policy_hash_failures, "protected_bytes_unchanged": protected_ok, "protected_byte_failures": protected_failures, "completed_validated_runs": len(ppa_by_run), "hypotheses": hypotheses})
    (out / "REPRODUCIBILITY.md").write_text(
        "# Gate 04 reproducibility\n\nThe immutable external policy is `/var/lib/green-ecc-gate04/policy`; its SHA-256 bundle fixes authorization, source snapshot, wrappers, configs, trace generator, 18 compressed traces, seed-control source, container digest, candidate matrix, run matrix, statistics, hypotheses, and analysis code. Runs are sequential, use unique attempt directories, and are never silently retried. Every run retains the effective three-variable seed environment, full ORFS logs/results/reports, ordered JSON occurrences, mapped and post-route equivalence logs, VCD annotation reports, power JSON, validation record, and raw SHA-256 manifest.\n\nReproduction requires Ubuntu WSL2/Docker, the exact image digest, and read access to the immutable policy. These results do not claim independent reproduction.\n",
        encoding="utf-8", newline="\n",
    )
    report = f"""# GREEN-ECC Gate 04 report

Final adjudication: `{verdict}`

Gate 03E-R and Gate 03E-S remain formal `ENVIRONMENT_ENABLEMENT_FAILED` verdicts. Gate 04 was entered only under the explicit superseding authorization based on `SCIENTIFIC_ENVIRONMENT_READY_FORMAL_GATE_FAILED`; neither prior verdict was changed.

## Execution

- Validated full candidate/reference flows: {len(ppa_by_run)} / 60.
- Mandatory candidate flows planned: 40; boundary-reference flows planned: 20.
- Historical/protected raw bytes unchanged: {protected_ok}.
- Frozen policy hashes valid: {not policy_hash_failures}.
- Blockers: {json.dumps(blockers)}.

## Scientific outcome

- H1 implementation-aware selection: {'SUPPORTED' if h1_supported else 'NOT SUPPORTED'} ({len(changed_scenarios)} changed preregistered scenarios).
- H2 same-code physical distinction: {'SUPPORTED' if h2_supported else 'NOT SUPPORTED'}.
- H3 cross-layer interaction: {'SUPPORTED' if h3_supported else 'NOT SUPPORTED'} ({h3_changed_strata} interleaving strata changed the exhaustive selection).
- H4 carbon independence: NOT SUPPORTED; carbon remains outside the primary claim.

All physical values are pinned-flow SKY130HD/OpenROAD estimates. Activity power uses post-route primary-input VCD annotation and propagation, with direct and unannotated pin counts retained. Codec and boundary-reference results are separate. Exact storage overhead is 8 parity bits for the 72-bit candidates and 14 for BCH(78,64). SRAM macro, controller, metadata, scrub machinery, migration, total-memory PPA, total-system energy, silicon measurement, foundry signoff, and publication readiness remain unresolved or prohibited.
"""
    (out / "GATE_04_REPORT.md").write_text(report, encoding="utf-8", newline="\n")
    print(f"GATE04_POSTPROCESS verdict={verdict} validated_runs={len(ppa_by_run)} blockers={len(blockers)}")
    return 0 if physical_complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
