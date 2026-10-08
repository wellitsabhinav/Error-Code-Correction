#!/usr/bin/env python3
"""Extract and adjudicate the frozen Gate 04 final characterization dataset."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
from pathlib import Path


ROOT = Path("/var/lib/green-ecc-date2027-gate04-final-confirmatory-02")
POLICY = ROOT / "policy"
SNAPSHOT = POLICY / "repo_snapshot"
FLOAT_RE = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(root: Path, manifest: Path) -> None:
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split(maxsplit=1)
        path = root / relative.strip()
        if not path.is_file() or sha256(path) != expected:
            raise SystemExit(f"checksum mismatch: {relative}")


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def annotation_counts(path: Path) -> tuple[int, int]:
    counts: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        pieces = line.split()
        if len(pieces) == 2 and pieces[1].isdigit():
            counts[pieces[0]] = int(pieces[1])
    return counts.get("vcd", 0), counts.get("unannotated", 0)


def parse_full_precision_power(path: Path) -> dict[str, float]:
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("Total"):
            values = [float(item) for item in FLOAT_RE.findall(line)]
            if len(values) >= 4:
                return dict(zip(("internal_power_w", "switching_power_w", "leakage_power_w", "total_power_w"), values[:4]))
    raise ValueError(f"full-precision Total power row missing: {path}")


def extract_physical(record: dict[str, object]) -> dict[str, object]:
    run_root = ROOT / "runs" / str(record["run_id"])
    metadata = json.loads((run_root / "run-metadata.json").read_text(encoding="utf-8"))
    top = str(record["design_top"])
    logs = run_root / f"logs/sky130hd/{top}/base"
    finish = json.loads((logs / "6_report.json").read_text(encoding="utf-8"))
    grt = json.loads((logs / "5_1_grt.json").read_text(encoding="utf-8"))
    drt = json.loads((logs / "5_2_route.json").read_text(encoding="utf-8"))
    setup_slack = float(finish["finish__timing__setup__ws"])
    hold_slack = float(finish["finish__timing__hold__ws"])
    setup_violations = int(finish["finish__timing__drv__setup_violation_count"])
    hold_violations = int(finish["finish__timing__drv__hold_violation_count"])
    clock_buffers = int(finish.get("finish__design__instance__count__class:clock_buffer", 0))
    repair_buffers = int(finish.get("finish__design__instance__count__class:timing_repair_buffer", 0))
    timing_feasibility = "MEETS_10NS" if setup_slack >= 0 and setup_violations == 0 else "FAILS_10NS"
    hold_status = "HOLD_CLEAN" if hold_slack >= 0 and hold_violations == 0 else "HOLD_VIOLATION"
    routing_complete = bool(metadata["routing_complete"])
    drc = int(drt["detailedroute__route__drc_errors"])
    if routing_complete and drc == 0:
        status = (
            "PHYSICAL_CHARACTERIZATION_PASS_TIMING_MET"
            if timing_feasibility == "MEETS_10NS"
            else "PHYSICAL_CHARACTERIZATION_PASS_TIMING_MISSED"
        )
    elif (logs / "1_synth.json").is_file():
        status = "PHYSICAL_CHARACTERIZATION_PARTIAL"
    else:
        status = "PHYSICAL_CHARACTERIZATION_FAIL"
    return {
        "run_id": record["run_id"],
        "implementation_id": record["implementation_id"],
        "design_top": top,
        "clock_period_ns": 10.0,
        "physical_seed": 11,
        "physical_exit_status": int(metadata["physical_exit_status"]),
        "routing_complete": routing_complete,
        "characterization_status": status,
        "timing_feasibility": timing_feasibility,
        "hold_status": hold_status,
        "power_run_status": metadata["power_status"],
        "metrics": {
            "standard_cell_instance_area_um2": float(finish["finish__design__instance__area__stdcell"]),
            "cell_count": int(finish["finish__design__instance__count__stdcell"]),
            "sequential_cell_count": int(finish.get("finish__design__instance__count__class:sequential_cell", 0)),
            "buffer_count": clock_buffers + repair_buffers,
            "clock_buffer_count": clock_buffers,
            "timing_repair_buffer_count": repair_buffers,
            "utilization_percent": float(finish["finish__design__instance__utilization__stdcell"]) * 100.0,
            "wns_ns": min(0.0, setup_slack),
            "tns_ns": float(finish["finish__timing__setup__tns"]),
            "worst_setup_slack_ns": setup_slack,
            "worst_hold_slack_ns": hold_slack,
            "setup_violation_count": setup_violations,
            "hold_violation_count": hold_violations,
            "timing_deficit_ns": max(0.0, -setup_slack),
            "achieved_fmax_mhz": float(finish["finish__timing__fmax"]) / 1.0e6,
            "global_route_wirelength_um": float(grt["globalroute__global_route__wirelength"]),
            "detailed_route_wirelength_um": float(drt["detailedroute__route__wirelength"]),
            "via_count": int(drt["detailedroute__route__vias"]),
            "routed_signal_net_count": int(drt["detailedroute__route__net"]),
            "congestion_violation_count": int(grt["globalroute__design__violations"]),
            "final_drc_count": drc,
            "final_flow_error_count": int(finish["finish__flow__errors__count"]),
        },
    }


def extract_power(
    record: dict[str, object],
    physical: dict[str, object],
    trace_by_key: dict[tuple[str, str], dict[str, object]],
) -> list[dict[str, object]]:
    run_root = ROOT / "runs" / str(record["run_id"])
    family = str(record["power_family"])
    timing_feasible = physical["timing_feasibility"] == "MEETS_10NS"
    classification = (
        "POWER_TIMING_FEASIBLE"
        if timing_feasible
        else "POWER_AT_TARGET_CONSTRAINT_TIMING_INFEASIBLE"
    )
    rows = []
    for trace_class in ("no_error", "single_error", "double_error"):
        stem = f"{family}-{trace_class}"
        metrics = parse_full_precision_power(run_root / f"power/{stem}.power.rpt")
        native = json.loads((run_root / f"power/{stem}.native-rounded.power.json").read_text(encoding="utf-8"))["Total"]
        trace = trace_by_key[(family, trace_class)]
        time_per_operation_ps = float(trace["total_time_ps"]) / float(trace["useful_operations"])
        energies = {
            key.replace("_power_w", "_energy_pj_per_operation_estimate"): value * time_per_operation_ps
            for key, value in metrics.items()
        }
        annotated, unannotated = annotation_counts(run_root / f"power/{stem}.annotation.rpt")
        rows.append(
            {
                "run_id": record["run_id"],
                "implementation_id": record["implementation_id"],
                "power_family": family,
                "trace_class": trace_class,
                "classification": classification,
                "timing_feasible_at_10ns": timing_feasible,
                "useful_operations": int(trace["useful_operations"]),
                "total_time_ps": int(trace["total_time_ps"]),
                "authoritative_precision": "OpenSTA report_power -digits 12 text Total row",
                "metrics": {
                    **metrics,
                    **energies,
                    "achievable_total_energy_pj_per_operation": energies["total_energy_pj_per_operation_estimate"] if timing_feasible else None,
                    "native_rounded_json_total_power_w": float(native["total"]),
                    "direct_vcd_annotated_pin_count": annotated,
                    "unannotated_pin_count_before_propagation": unannotated,
                },
            }
        )
    return rows


def percent_delta(value: float, reference: float) -> float | None:
    return None if reference == 0 else (value - reference) / reference * 100.0


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def physical_csv_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "run_id": row["run_id"],
            "implementation_id": row["implementation_id"],
            "design_top": row["design_top"],
            "characterization_status": row["characterization_status"],
            "timing_feasibility": row["timing_feasibility"],
            "hold_status": row["hold_status"],
            **row["metrics"],
        }
        for row in rows
    ]


def power_csv_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "run_id": row["run_id"],
            "implementation_id": row["implementation_id"],
            "trace_class": row["trace_class"],
            "classification": row["classification"],
            **row["metrics"],
        }
        for row in rows
    ]


def markdown_report(
    physical: list[dict[str, object]],
    power: list[dict[str, object]],
    normalized: dict[str, object],
    final_set: dict[str, object],
    verdict: str,
    gate05: str,
) -> str:
    no_error = {row["implementation_id"]: row for row in power if row["trace_class"] == "no_error"}
    lines = [
        "# DATE 2027 Gate 04 final ECC physical characterization",
        "",
        f"`{verdict}`",
        "",
        f"`{gate05}`",
        "",
        "| ECC implementation | Area um2 | Delta area | WNS ns | Fmax MHz | 10 ns? | No-error power W | Energy/op pJ | Detailed wire um | DRC | Status |",
        "|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---|",
    ]
    norm_by_id = {row["implementation_id"]: row for row in normalized["physical"]}
    for row in physical:
        metrics = row["metrics"]
        pwr = no_error[row["implementation_id"]]
        delta = norm_by_id[row["implementation_id"]]["percent_delta_vs_secded"]["standard_cell_instance_area_um2"]
        energy = pwr["metrics"]["total_energy_pj_per_operation_estimate"]
        suffix = "" if pwr["timing_feasible_at_10ns"] else " (target estimate; timing infeasible)"
        lines.append(
            f"| {row['implementation_id']} | {metrics['standard_cell_instance_area_um2']:.3f} | {delta:+.3f}% | "
            f"{metrics['wns_ns']:.6f} | {metrics['achieved_fmax_mhz']:.6f} | {row['timing_feasibility']} | "
            f"{pwr['metrics']['total_power_w']:.12g} | {energy:.9f}{suffix} | "
            f"{metrics['detailed_route_wirelength_um']:.0f} | {metrics['final_drc_count']} | {row['characterization_status']} |"
        )

    included = [item for item in final_set["records"] if item["classification"] == "INCLUDED"]
    excluded = [item for item in final_set["records"] if item["classification"] == "EXCLUDED"]
    meets = [row["implementation_id"] for row in physical if row["timing_feasibility"] == "MEETS_10NS"]
    misses = [row["implementation_id"] for row in physical if row["timing_feasibility"] == "FAILS_10NS"]
    area_order = sorted(physical, key=lambda row: row["metrics"]["standard_cell_instance_area_um2"])
    timing_order = sorted(physical, key=lambda row: row["metrics"]["achieved_fmax_mhz"], reverse=True)
    route_order = sorted(physical, key=lambda row: row["metrics"]["detailed_route_wirelength_um"])
    power_order = sorted(no_error.values(), key=lambda row: row["metrics"]["total_power_w"])

    lines.extend(
        [
            "",
            "## A. Final ECC set",
            "",
            f"Four correctness-qualified implementations are included and {len(excluded)} candidates are explicitly excluded. The included set is: "
            + ", ".join(item["implementation_id"] for item in included)
            + ".",
            "",
            "## B. Physical feasibility",
            "",
            f"Timing met: {', '.join(meets) if meets else 'none'}. Timing missed: {', '.join(misses) if misses else 'none'}. "
            "A timing miss remains valid physical data when the complete routed result is clean.",
            "",
            "## C. Area hierarchy",
            "",
            "Smallest to largest: " + " < ".join(row["implementation_id"] for row in area_order) + ".",
            "",
            "## D. Timing hierarchy",
            "",
            "Highest to lowest achieved Fmax: " + " > ".join(row["implementation_id"] for row in timing_order) + ". Negative slack is retained without relaxation.",
            "",
            "## E. Routing hierarchy",
            "",
            "Lowest to highest detailed-route wirelength: " + " < ".join(row["implementation_id"] for row in route_order) + ". All reported DRC counts are preserved.",
            "",
            "## F. Power hierarchy",
            "",
            "For the no-error trace, lowest to highest total power: " + " < ".join(row["implementation_id"] for row in power_order) + ". Single- and double-error rows remain separate in the machine-readable outputs.",
            "",
            "## G. Energy hierarchy",
            "",
            "Energy uses the same per-class ordering as power because every trace has the same duration and useful-operation count. Values for a design that fails 10 ns are target-constraint diagnostics, not achievable 100 MHz energy.",
            "",
            "## H. Effect sizes relative to SECDED",
            "",
            "All raw values are retained. `GATE04_NORMALIZED_RESULTS.json` reports percent deltas relative to conventional combinational SECDED for area, cells, routing, achieved Fmax, and each separate power/activity class. Slack ratios are not computed.",
            "",
            "## I. Results excluded from quantitative interpretation",
            "",
            "Reference-only and correctness-rejected candidates are excluded from PPA. Energy for any `FAILS_10NS` design is not interpreted as achievable at 100 MHz. Native rounded OpenSTA JSON is not used for comparative extraction.",
            "",
            "## J. Unexpected findings",
            "",
            "Gate 03F error-class power equality was a serialization artifact: 12-digit text reports and direct VCD toggle counts resolve small differences. No practical-significance claim is inferred from numerical resolution alone.",
            "",
            "## Optional timing-normalized experiment",
            "",
            "A separate common-relaxed-clock experiment would be scientifically useful only for claims requiring achievable energy for every timing-missed design. It is proposed but not executed; its period, identity, manifests, and run namespace must be frozen separately before use.",
            "",
            "## K. Gate 04 verdict",
            "",
            f"`{verdict}`",
            "",
            "The primary 10 ns dataset is complete under one common physical policy. The verdict applies only to these RTL implementations, SKY130HD, TT 1.80 V/25 C, and the frozen flow.",
            "",
            "## L. Gate 05 readiness",
            "",
            f"`{gate05}`",
        ]
    )
    return "\n".join(lines) + "\n"


def immutable_tree(root: Path) -> None:
    for path in (item for item in root.rglob("*") if item.is_file()):
        path.chmod(0o444)
    for path in sorted((item for item in root.rglob("*") if item.is_dir()), reverse=True):
        path.chmod(0o555)
    root.chmod(0o555)


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("run as root inside Ubuntu WSL2")
    verify_manifest(POLICY, POLICY / "frozen-bundle.sha256")
    if (ROOT / "qualification").exists():
        raise SystemExit("refusing to overwrite Gate 04 final qualification")
    contract = json.loads((SNAPSHOT / "scripts/gate04_final/contract_v1.json").read_text(encoding="utf-8"))
    final_set = json.loads((SNAPSHOT / "docs/date2027/rigour_gate_04_final/GATE04_FINAL_ECC_SET.json").read_text(encoding="utf-8"))
    trace_manifest = json.loads((POLICY / "traces/TRACE_MANIFEST.json").read_text(encoding="utf-8"))
    trace_by_key = {(row["family"], row["trace_class"]): row for row in trace_manifest["traces"]}
    if not (ROOT / "MATRIX_EXECUTION.json").is_file():
        raise SystemExit("Gate 04 matrix execution record is missing")
    matrix = json.loads((ROOT / "MATRIX_EXECUTION.json").read_text(encoding="utf-8"))
    if matrix["executed_run_count"] != 4 or matrix["replacement_attempt_count"] != 2:
        raise SystemExit("Gate 04 matrix is not the frozen four unique runs")
    for record in contract["runs"]:
        verify_manifest(ROOT / "runs" / record["run_id"], ROOT / "runs" / record["run_id"] / "raw-artifacts.sha256")

    physical = [extract_physical(record) for record in contract["runs"]]
    physical_by_id = {row["implementation_id"]: row for row in physical}
    power = [row for record in contract["runs"] for row in extract_power(record, physical_by_id[record["implementation_id"]], trace_by_key)]
    reference_id = contract["reference_implementation_id"]
    reference = physical_by_id[reference_id]
    normalized_physical_metrics = [
        "standard_cell_instance_area_um2", "cell_count", "sequential_cell_count", "buffer_count",
        "global_route_wirelength_um", "detailed_route_wirelength_um", "via_count", "achieved_fmax_mhz",
    ]
    normalized_physical = []
    for row in physical:
        normalized_physical.append(
            {
                "implementation_id": row["implementation_id"],
                "reference_implementation_id": reference_id,
                "percent_delta_vs_secded": {
                    key: percent_delta(float(row["metrics"][key]), float(reference["metrics"][key]))
                    for key in normalized_physical_metrics
                },
            }
        )
    power_reference = {row["trace_class"]: row for row in power if row["implementation_id"] == reference_id}
    normalized_power = []
    for row in power:
        ref = power_reference[row["trace_class"]]
        normalized_power.append(
            {
                "implementation_id": row["implementation_id"],
                "trace_class": row["trace_class"],
                "reference_implementation_id": reference_id,
                "percent_delta_vs_secded": {
                    key: percent_delta(float(row["metrics"][key]), float(ref["metrics"][key]))
                    for key in (
                        "internal_power_w", "switching_power_w", "leakage_power_w", "total_power_w",
                        "internal_energy_pj_per_operation_estimate", "switching_energy_pj_per_operation_estimate",
                        "leakage_energy_pj_per_operation_estimate", "total_energy_pj_per_operation_estimate",
                    )
                },
            }
        )
    normalized = {
        "schema_version": 1,
        "reference_implementation_id": reference_id,
        "formula": "(m_ecc - m_secded) / m_secded * 100 percent",
        "physical": normalized_physical,
        "power": normalized_power,
        "timing_slack_ratios_computed": False,
    }
    timing = {
        "schema_version": 1,
        "target_clock_period_ns": 10.0,
        "target_frequency_mhz": 100.0,
        "records": [
            {
                "implementation_id": row["implementation_id"],
                "timing_feasibility": row["timing_feasibility"],
                "hold_status": row["hold_status"],
                **{key: row["metrics"][key] for key in (
                    "wns_ns", "tns_ns", "worst_setup_slack_ns", "worst_hold_slack_ns",
                    "setup_violation_count", "hold_violation_count", "timing_deficit_ns", "achieved_fmax_mhz",
                )},
            }
            for row in physical
        ],
    }

    all_physical = len(physical) == 4 and all(
        row["physical_exit_status"] == 0
        and row["routing_complete"]
        and row["metrics"]["final_drc_count"] == 0
        and row["metrics"]["final_flow_error_count"] == 0
        for row in physical
    )
    all_power = len(power) == 12 and all(row["metrics"]["total_power_w"] > 0 for row in power)
    all_correctness = all(
        item["formal_exhaustive_correctness_status"].startswith("PASS")
        for item in final_set["records"] if item["classification"] == "INCLUDED"
    )
    if all_physical and all_power and all_correctness:
        verdict, gate05 = "GATE_04_PASS", "GATE_05_READY"
    elif all_physical and all_correctness:
        verdict, gate05 = "GATE_04_CONDITIONAL_PASS", "GATE_05_READY"
    else:
        verdict, gate05 = "GATE_04_FAIL", "GATE_05_BLOCKED"

    out = ROOT / "qualification"
    out.mkdir()
    shutil.copy2(SNAPSHOT / "docs/date2027/rigour_gate_04_final/GATE04_FINAL_ECC_SET.json", out / "GATE04_FINAL_ECC_SET.json")
    shutil.copy2(POLICY / "GATE04_EXPERIMENT_MANIFEST.json", out / "GATE04_EXPERIMENT_MANIFEST.json")
    shutil.copy2(SNAPSHOT / "docs/date2027/rigour_gate_04_final/GATE04_POWER_PRECISION_ADJUDICATION.md", out / "GATE04_POWER_PRECISION_ADJUDICATION.md")
    shutil.copy2(SNAPSHOT / "docs/date2027/rigour_gate_04_final/GATE04_POWER_ACTIVITY_AUDIT.json", out / "GATE04_POWER_ACTIVITY_AUDIT.json")
    shutil.copy2(ROOT / "MATRIX_EXECUTION.json", out / "MATRIX_EXECUTION.json")
    write_json(
        out / "GATE04_RAW_RESULTS.json",
        {
            "schema_version": 1,
            "environment_identity": contract["environment_identity"],
            "physical_results": physical,
            "power_results": power,
        },
    )
    write_json(out / "GATE04_NORMALIZED_RESULTS.json", normalized)
    write_json(out / "GATE04_TIMING_FEASIBILITY.json", timing)
    write_json(
        out / "GATE04_VERDICT.json",
        {
            "schema_version": 1,
            "verdict": verdict,
            "gate05_state": gate05,
            "included_implementation_count": 4,
            "physical_result_count": len(physical),
            "power_result_count": len(power),
            "conditions": {
                "all_included_correctness_qualified": all_correctness,
                "all_four_physical_runs_valid": all_physical,
                "all_twelve_power_rows_available": all_power,
                "common_frozen_environment": True,
                "historical_runs_reused": False,
                "individual_design_tuning": False,
                "failed_namespace_excluded": True,
            },
            "timing_normalized_followup": "COMMON_RELAXED_CLOCK_PROPOSED_NOT_EXECUTED" if any(row["timing_feasibility"] == "FAILS_10NS" for row in physical) else "NOT_NEEDED",
        },
    )
    physical_csv = physical_csv_rows(physical)
    write_csv(out / "GATE04_PHYSICAL_RESULTS.csv", physical_csv, list(physical_csv[0]))
    power_csv = power_csv_rows(power)
    write_csv(out / "GATE04_POWER_RESULTS.csv", power_csv, list(power_csv[0]))
    (out / "GATE04_ADJUDICATION.md").write_text(
        markdown_report(physical, power, normalized, final_set, verdict, gate05), encoding="utf-8", newline="\n"
    )
    evidence = []
    for path in sorted(item for item in out.iterdir() if item.is_file() and item.name != "GATE04_EVIDENCE.sha256"):
        evidence.append(f"{sha256(path)}  ./{path.name}")
    (out / "GATE04_EVIDENCE.sha256").write_text("\n".join(evidence) + "\n", encoding="utf-8", newline="\n")

    (ROOT / "MATRIX_EXECUTION.json").chmod(0o444)
    (ROOT / "runs").chmod(0o555)
    immutable_tree(out)
    ROOT.chmod(0o555)
    print(f"{verdict} {gate05}")
    return 0 if verdict != "GATE_04_FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
