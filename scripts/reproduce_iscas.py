#!/usr/bin/env python3
"""Reproduce GREENS ISCAS claim derivations without modifying frozen evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import statistics
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from campaigns.iscas_sustainability_extension.green_v3_3_activity_complete_e5 import (  # noqa: E402
    finalize_executed_campaign as frozen,
)

CAMPAIGN = ROOT / frozen.CAMPAIGN_REL
PARENT = ROOT / frozen.PARENT_REL
REFERENCE = ROOT / "experiments/iscas/generated"
DATA_FILES = (
    "headline_results.json", "primary_operation_pairs.csv", "operation_summary.csv",
    "cohort_admission.csv", "bch_setup_feasibility.csv", "workload_read_write_slice.csv",
    "campaign_conditions.json", "integrity/source_manifest.json", "integrity/tool_environment.json",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(f"fail closed: {message}")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def verify_seal(campaign: Path) -> int:
    seal = campaign / "hashes/CAMPAIGN_ARTIFACTS.sha256"
    lines = seal.read_text(encoding="utf-8").splitlines()
    for line in lines:
        expected, relative = line.split(maxsplit=1)
        path = (campaign / relative.strip()).resolve()
        require(path.is_relative_to(campaign.resolve()), "seal path escapes campaign")
        require(path.is_file() and digest(path) == expected, f"sealed bytes differ: {relative}")
    return len(lines)


def load(path: Path, sources: dict[str, str]) -> dict:
    sources[path.relative_to(ROOT).as_posix()] = digest(path)
    return json.loads(path.read_text(encoding="utf-8"))


def timing_admission(physical: dict, report: dict) -> list[str]:
    reasons = []
    if physical.get("finish_exit_code") != 0:
        reasons.append("ROUTE_NOT_COMPLETED")
    for field, reason in (
        ("finish__timing__setup__ws", "SETUP_FAILED_OR_MISSING"),
        ("finish__timing__hold__ws", "HOLD_FAILED_OR_MISSING"),
    ):
        value = report.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            reasons.append(reason)
    if type(report.get("finish__timing__drv__hold_violation_count")) is not int or report.get("finish__timing__drv__hold_violation_count") != 0:
        reasons.append("HOLD_VIOLATIONS_OR_MISSING_COUNT")
    return reasons


def paired_cell(left: dict, right: dict) -> dict:
    for field in ("physical_seed", "clock_period_ns", "operation_class", "workload_sha256",
                  "exact_operation_count", "measurement_duration_seconds", "activity_boundary"):
        require(left[field] == right[field], f"unmatched operation field: {field}")
    for row in (left, right):
        require(row["qualification"] == frozen.QUALIFIED, "unqualified operation")
        require(row["whole_memory_energy_j_per_operation"] is None, "unexpected whole-memory energy")
        for field in ("activity_sha256", "routed_netlist_sha256", "spef_sha256", "workload_sha256"):
            require(bool(row[field]), f"missing identity: {field}")
        energy = row["energy_j_per_operation"]
        require(not isinstance(energy, bool) and isinstance(energy, (int, float)) and math.isfinite(energy) and energy > 0,
                "missing or invalid operation energy")
        require(row["exact_operation_count"] > 0, "missing operation denominator")
        reconstructed = row["total_power_w"] * row["measurement_duration_seconds"] / row["exact_operation_count"]
        require(math.isclose(energy, reconstructed, rel_tol=1e-12), "energy does not match power/window/count")
    delta = right["energy_j_per_operation"] - left["energy_j_per_operation"]
    return {
        "seed": left["physical_seed"], "operation": left["operation_class"],
        "secded_energy_j": left["energy_j_per_operation"],
        "hsiao_energy_j": right["energy_j_per_operation"],
        "hsiao_minus_secded_j": delta, "hsiao_lower": delta < 0,
        "secded_record_id": left["record_id"], "hsiao_record_id": right["record_id"],
        "secded_source": (frozen.CAMPAIGN_REL / left["source_result"]).as_posix(),
        "hsiao_source": (frozen.CAMPAIGN_REL / right["source_result"]).as_posix(),
    }


def verified_frozen_campaign() -> int:
    relative = (frozen.CAMPAIGN_REL / "hashes/CAMPAIGN_ARTIFACTS.sha256").as_posix()
    identity = json.loads((REFERENCE / "integrity/source_manifest.json").read_text(encoding="utf8"))
    require(digest(CAMPAIGN / "hashes/CAMPAIGN_ARTIFACTS.sha256") == identity["frozen_inputs"][relative],
            "frozen seal identity differs; resealing is not reproduction")
    count = verify_seal(CAMPAIGN)
    require(count == 1697, "unexpected frozen campaign population")
    return count


def derive() -> dict:
    sources: dict[str, str] = {}
    sealed_count = verified_frozen_campaign()
    sources[(frozen.CAMPAIGN_REL / "hashes/CAMPAIGN_ARTIFACTS.sha256").as_posix()] = digest(
        CAMPAIGN / "hashes/CAMPAIGN_ARTIFACTS.sha256")
    manifest = load(CAMPAIGN / "RUN_MANIFEST.json", sources)
    measurements, runs = frozen.collect(CAMPAIGN)  # Existing read-only scientific collector.
    require(measurements == manifest["new_activity_power_records"], "raw operation records differ from manifest")
    require(runs == manifest["canonical_fresh_runs"], "raw runs differ from manifest")
    inherited = manifest["inherited_physical_population"]
    parent_manifest = load(ROOT / inherited["source"], sources)
    require(sources[inherited["source"]] == inherited["source_sha256"], "parent manifest identity differs")
    lookup = {(r["architecture_id"], r["physical_seed"], r["operation_class"]): r for r in measurements}
    require(len(lookup) == len(measurements), "duplicate operation identity")
    admission = []
    admitted_seeds = []
    for seed in frozen.SEEDS:
        pair_reasons = []
        seed_rows = []
        for architecture in frozen.ARCHITECTURES:
            run = next(r for r in runs if r["architecture_id"] == architecture and r["physical_seed"] == seed)
            canonical = load(CAMPAIGN / run["canonical_result"], sources)
            physical_result = load(CAMPAIGN / run["physical_result"], sources)
            physical = physical_result["physical"]
            report_path = CAMPAIGN / Path(run["physical_result"]).parent / "attempt01/physical/6_report.json"
            report = load(report_path, sources)
            reasons = timing_admission(physical, report)
            if any((architecture, seed, op) not in lookup for op in frozen.OPERATIONS):
                reasons.append("INCOMPLETE_FIVE_OPERATION_SET")
            for op in canonical["operation_records"]:
                require(op["pvt"] == {"corner": "tt_025C_1v80", "platform": "sky130hd",
                                      "temperature_c": 25, "voltage_v": 1.8}, "unexpected PVT boundary")
            seed_rows.append({"seed": seed, "architecture": architecture,
                              "setup_wns_ns": report.get("finish__timing__setup__ws"),
                              "hold_wns_ns": report.get("finish__timing__hold__ws"),
                              "qualified_operations": run["qualified_operation_count"],
                              "reasons": ";".join(reasons) or "PASS"})
            pair_reasons.extend(reasons)
        admitted = not pair_reasons
        for row in seed_rows:
            row["primary_pair_admitted"] = admitted
        admission.extend(seed_rows)
        if admitted:
            admitted_seeds.append(seed)
    pairs = [paired_cell(lookup[("SECDED", seed, op)], lookup[("HSIAO_SECDED", seed, op)])
             for seed in admitted_seeds for op in frozen.OPERATIONS]
    legacy = load(CAMPAIGN / "E5_MATCHED_SEED_DELTAS.json", sources)
    for pair in pairs:
        old = next(r for r in legacy["records"] if r["seed"] == pair["seed"])
        require(math.isclose(pair["hsiao_minus_secded_j"], old[frozen.PREFIX[pair["operation"]] + "_energy_j_delta"],
                             rel_tol=1e-12, abs_tol=1e-25), "paired delta differs from frozen derivation")
    bch = []
    for run in parent_manifest["records"]:
        if run["architecture_id"] == "BCH_78_64_T2" and run["clock_period_ns"] == 10.0:
            path = PARENT / run["report_path"]
            report = load(path, sources)
            require(digest(path) == run["report_sha256"], "BCH physical report hash differs")
            wns = report["metrics"]["timing"]["setup_wns_ns"]
            require(not isinstance(wns, bool) and isinstance(wns, (int, float)) and math.isfinite(wns), "BCH setup measurement unavailable")
            bch.append({"seed": run["seed"], "clock_period_ns": 10.0, "setup_wns_ns": wns,
                        "setup_feasible": wns >= 0, "source": path.relative_to(ROOT).as_posix()})
    summary = [{"operation": op, "paired_cells": len(rows),
                "hsiao_lower_cells": sum(r["hsiao_lower"] for r in rows),
                "mean_hsiao_minus_secded_pj": statistics.mean(r["hsiao_minus_secded_j"] for r in rows) * 1e12}
               for op in frozen.OPERATIONS if (rows := [r for r in pairs if r["operation"] == op])]
    headline = {"schema_version": 1, "boundary": "POST_ROUTE_ECC_LOGIC_ONLY",
                "primary_seeds": admitted_seeds, "matched_pairs": len(admitted_seeds),
                "paired_operation_cells": len(pairs), "primary_energy_records": 2 * len(pairs),
                "hsiao_lower_cells": sum(r["hsiao_lower"] for r in pairs),
                "retained_diagnostic_energy_records": len(measurements) - 2 * len(pairs),
                "historical_activity_records": len(measurements),
                "historical_paired_cells": legacy["matched_operation_comparison_count"],
                "bch_setup_feasible_seeds": sum(r["setup_feasible"] for r in bch), "bch_seeds": len(bch),
                "whole_sram_lifecycle_winner": None, "verified_campaign_seal_entries": sealed_count}
    require((admitted_seeds, len(pairs), headline["hsiao_lower_cells"], len(bch), headline["bch_setup_feasible_seeds"])
            == ([13, 17, 19, 23], 20, 4, 5, 0), "headline differs from the documented ISCAS claim set")
    # A two-operation slice of sum_o w_o * (E_Hsiao,o - E_SECDED,o).
    # Idle/correction/detection weights are zero here; no reliability rates are inferred.
    workload = []
    for seed in admitted_seeds:
        read = next(r["hsiao_minus_secded_j"] for r in pairs if r["seed"] == seed and r["operation"] == "READ_CLEAN")
        write = next(r["hsiao_minus_secded_j"] for r in pairs if r["seed"] == seed and r["operation"] == "WRITE_CLEAN")
        for step in range(101):
            weight = step / 100
            workload.append({"seed": seed, "clean_read_fraction": weight,
                             "hsiao_minus_secded_pj": (weight * read + (1 - weight) * write) * 1e12})
    return {"headline": headline, "pairs": pairs, "summary": summary, "admission": admission,
            "bch": sorted(bch, key=lambda r: r["seed"]), "workload": workload,
            "conditions": {"artifact": "GREENS ISCAS reproducibility artifact",
                           "service": "W1 correction / W2 detection for the primary SECDED pair",
                           "technology": "SKY130HD", "corner": "TT", "temperature_c": 25,
                           "voltage_v": 1.8, "clock_period_ns": 10.0,
                           "tested_seeds": list(frozen.SEEDS), "primary_seeds": admitted_seeds,
                           "macro_views": ["SRAM22 256x64", "SRAM22 256x8"],
                           "warm_up_cycles": 16, "measured_operations": 256,
                           "activity": "Zero-delay routed-netlist VCD with final SPEF",
                           "energy_boundary": "ECC logic only; macro-internal energy incomplete",
                           "tools": {"OpenROAD": "26Q3-1080", "OpenSTA": "3.1.0", "Yosys": "0.68+post"},
                           "flow_exception": "Common SRAM22 transition-stage resize bypass",
                           "primary_operations": list(frozen.OPERATIONS)},
            "tool_environment": manifest["toolchain"],
            "sources": {"schema_version": 1, "algorithm": "GREENS_ISCAS_PRIMARY_COHORT_V1",
                        "frozen_inputs": dict(sorted(sources.items()))}}


def write_csv(path: Path, rows: list[dict]) -> None:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.write_bytes(stream.getvalue().encode("utf-8"))


def write_outputs(output: Path, data: dict, *, figures: bool = True) -> None:
    require(not output.resolve().is_relative_to(ROOT / "campaigns"), "output must be outside frozen campaigns")
    output.mkdir(parents=True, exist_ok=True)
    for name, key in (("headline_results.json", "headline"), ("campaign_conditions.json", "conditions"),
                      ("integrity/source_manifest.json", "sources"), ("integrity/tool_environment.json", "tool_environment")):
        (output / name).parent.mkdir(parents=True, exist_ok=True)
        (output / name).write_bytes((json.dumps(data[key], indent=2, sort_keys=True) + "\n").encode("utf-8"))
    for name, key in (("primary_operation_pairs.csv", "pairs"), ("operation_summary.csv", "summary"),
                      ("cohort_admission.csv", "admission"), ("bch_setup_feasibility.csv", "bch"),
                      ("workload_read_write_slice.csv", "workload")):
        write_csv(output / name, data[key])
    if figures:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.rcParams.update({"svg.hashsalt": "GREENS_ISCAS_V1", "font.size": 10, "svg.fonttype": "none"})
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), layout="constrained")
        labels = ["Idle", "Clean write", "Clean read", "Correction", "Detection"]
        for index, seed in enumerate(data["headline"]["primary_seeds"]):
            marker, style = [("o", "-"), ("s", "--"), ("^", "-."), ("D", ":")][index]
            values = [r["hsiao_minus_secded_j"] * 1e12 for r in data["pairs"] if r["seed"] == seed]
            axes[0].plot(labels, values, marker=marker, linestyle=style, label=f"Seed {seed}", linewidth=1)
            rows = [r for r in data["workload"] if r["seed"] == seed]
            axes[1].plot([r["clean_read_fraction"] for r in rows], [r["hsiao_minus_secded_pj"] for r in rows], linestyle=style, label=f"Seed {seed}")
        for ax in axes:
            ax.axhline(0, color="#222222", linewidth=0.8)
            ax.grid(alpha=0.2)
            ax.set_ylabel("Hsiao − Extended Hamming (pJ / operation)")
        axes[0].set_title("Primary cohort: 4 of 20 cells favor Hsiao")
        axes[0].tick_params(axis="x", labelrotation=25)
        axes[1].set_title("Clean-read / clean-write workload slice")
        axes[1].set_xlabel("Clean-read fraction; remaining operations are clean writes")
        axes[1].legend(loc="best", fontsize=8)
        fig.savefig(output / "operation_and_workload.svg", metadata={"Date": None})
        svg = output / "operation_and_workload.svg"
        svg.write_bytes(("\n".join(line.rstrip() for line in svg.read_text(encoding="utf8").splitlines()) + "\n").encode("utf8"))
        plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "tmp/reproduce-iscas")
    parser.add_argument("--check", action="store_true", help="Compare regenerated numerical outputs with tracked references without writing them")
    args = parser.parse_args()
    try:
        data = derive()
        if args.check:
            with tempfile.TemporaryDirectory(prefix="greens-iscas-") as directory:
                output = Path(directory)
                write_outputs(output, data, figures=False)
                for name in DATA_FILES:
                    require((REFERENCE / name).read_bytes() == (output / name).read_bytes(), f"stale generated reference: {name}")
        else:
            write_outputs(args.output.resolve(), data)
        print(json.dumps({"status": "PASS", **data["headline"]}, indent=2, sort_keys=True))
        return 0
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
