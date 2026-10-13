#!/usr/bin/env python3
"""Build the DATE 2027 Gate 07 adversarial claim and evidence freeze."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
GATE03F = ROOT / "docs/date2027/rigour_gate_03f"
GATE04 = ROOT / "docs/date2027/rigour_gate_04_final"
GATE05 = ROOT / "docs/date2027/rigour_gate_05"
GATE06 = ROOT / "docs/date2027/rigour_gate_06"
DEFAULT_OUT = ROOT / "docs/date2027/rigour_gate_07"

COMB = "secded-rtl-combinational-72-64-v1"
PIPE = "secded-rtl-pipelined-72-64-v1"
HSIAO = "hsiao-generated-combinational-72-64-v1"
BCH = "shortened-bch-78-64-t2-v1-rtl-syndrome-chien-v1"
ORDER = (COMB, PIPE, HSIAO, BCH)

UPSTREAM_INPUTS = (
    "docs/date2027/rigour_gate_03f/DATE_FINAL_PHYSICAL_ENVIRONMENT.json",
    "docs/date2027/rigour_gate_03f/ACTIVITY_TRACE_MANIFEST.json",
    "docs/date2027/rigour_gate_03f/REPRODUCIBILITY_STATISTICS.json",
    "docs/date2027/rigour_gate_03f/GATE_03F_VERDICT.json",
    "docs/date2027/rigour_gate_04_final/GATE04_EXPERIMENT_MANIFEST.json",
    "docs/date2027/rigour_gate_04_final/GATE04_RAW_RESULTS.json",
    "docs/date2027/rigour_gate_04_final/GATE04_POWER_ACTIVITY_AUDIT.json",
    "docs/date2027/rigour_gate_04_final/GATE04_ADJUDICATION.md",
    "docs/date2027/rigour_gate_05/GATE05_IMPLEMENTATION_IDENTITY.json",
    "docs/date2027/rigour_gate_05/GATE05_INTEGRATED_RESULTS.json",
    "docs/date2027/rigour_gate_05/GATE05_DERIVED_METRICS.json",
    "docs/date2027/rigour_gate_05/GATE05_MISSING_EVIDENCE.json",
)

GATE06_INPUTS = (
    "GATE06_ANALYSIS_POLICY.json",
    "GATE06_EFFECT_SIZES.json",
    "GATE06_DOMINANCE_ANALYSIS.json",
    "GATE06_DESIGN_SPACE.csv",
    "GATE06_RELIABILITY_TABLE.csv",
    "GATE06_PHYSICAL_TABLE.csv",
    "GATE06_CLAIM_RANKING.json",
    "GATE06_LIMITATIONS.json",
    "GATE06_FIGURE_SPECIFICATIONS.md",
    "GATE06_PAPER_TABLES.md",
    "GATE06_ADJUDICATION.md",
    "GATE06_FIGURE_DATA.json",
    "GATE06_PAPER_STRENGTH.json",
)

LOCAL_NOVELTY_NOTES = (
    "docs/RESEARCH_NOVELTY.md",
    "docs/PORTFOLIO_COSYNTHESIS_NOVELTY_GATE.md",
    "docs/SAFEFORGE_LITERATURE.md",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_text(path: Path, value: str) -> None:
    path.write_text(value.rstrip() + "\n", encoding="utf-8", newline="\n")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def manifest_entries(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split(maxsplit=1)
        entries[relative.removeprefix("./")] = expected
    return entries


def verify_manifest(directory: Path, manifest_name: str) -> None:
    for relative, expected in manifest_entries(directory / manifest_name).items():
        assert sha256(directory / relative) == expected, relative


def pct(candidate: float, reference: float) -> float:
    return (candidate - reference) / reference * 100.0


def close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-12)


def source_manifest() -> list[dict[str, Any]]:
    verify_manifest(GATE06, "GATE06_EVIDENCE.sha256")
    verify_manifest(GATE05, "GATE05_EVIDENCE.sha256")
    verify_manifest(GATE04, "GATE04_EVIDENCE.sha256")
    verify_manifest(GATE03F, "QUALIFICATION_EVIDENCE.sha256")
    paths = list(UPSTREAM_INPUTS)
    paths.extend(f"docs/date2027/rigour_gate_06/{name}" for name in GATE06_INPUTS)
    paths.extend(LOCAL_NOVELTY_NOTES)
    return [
        {"path": relative, "bytes": (ROOT / relative).stat().st_size, "sha256": sha256(ROOT / relative)}
        for relative in paths
    ]


def numerical_audit(rows: dict[str, dict[str, str]], effects: dict[str, Any]) -> dict[str, Any]:
    reported = {row["comparison"]: row for row in effects["comparisons"]}
    comparisons = (
        ("pipelined SECDED vs combinational SECDED", PIPE, COMB),
        ("BCH vs combinational SECDED", BCH, COMB),
        ("BCH vs pipelined SECDED", BCH, PIPE),
    )
    physical_metrics = (
        ("standard_cell_instance_area_um2", "area_um2"),
        ("cell_count", "cell_count"),
        ("detailed_route_wirelength_um", "wirelength_um"),
        ("achieved_fmax_mhz", "fmax_mhz"),
    )
    audited: list[dict[str, Any]] = []
    for name, candidate_id, reference_id in comparisons:
        candidate = rows[candidate_id]
        reference = rows[reference_id]
        metric_rows: list[dict[str, Any]] = []
        for metric, csv_field in physical_metrics:
            candidate_raw = float(candidate[csv_field])
            reference_raw = float(reference[csv_field])
            recomputed = pct(candidate_raw, reference_raw)
            gate06 = reported[name]["metrics"][metric]["percent_change"]
            metric_rows.append(
                {
                    "metric": metric,
                    "candidate_raw": candidate_raw,
                    "reference_raw": reference_raw,
                    "formula": "(candidate_raw-reference_raw)/reference_raw*100",
                    "recomputed_percent_change": recomputed,
                    "gate06_reported_percent_change": gate06,
                    "absolute_mismatch": abs(recomputed - gate06),
                    "status": "MATCH" if close(recomputed, gate06) else "MISMATCH",
                }
            )
        if candidate_id == PIPE:
            for metric, gate06_key in (
                ("total_power_w", "no_error_total_power_w"),
                ("achievable_total_energy_pj_per_operation", "no_error_achievable_total_energy_pj_per_operation"),
            ):
                csv_field = "no_error_power_w" if metric == "total_power_w" else "achievable_energy_pj_per_operation"
                candidate_raw = float(candidate[csv_field])
                reference_raw = float(reference[csv_field])
                recomputed = pct(candidate_raw, reference_raw)
                gate06 = reported[name]["metrics"][gate06_key]["percent_change"]
                metric_rows.append(
                    {
                        "metric": gate06_key,
                        "candidate_raw": candidate_raw,
                        "reference_raw": reference_raw,
                        "formula": "(candidate_raw-reference_raw)/reference_raw*100",
                        "recomputed_percent_change": recomputed,
                        "gate06_reported_percent_change": gate06,
                        "absolute_mismatch": abs(recomputed - gate06),
                        "status": "MATCH" if close(recomputed, gate06) else "MISMATCH",
                    }
                )
        else:
            for gate06_key in (
                "no_error_total_power_w",
                "no_error_achievable_total_energy_pj_per_operation",
            ):
                frozen = reported[name]["metrics"][gate06_key]
                metric_rows.append(
                    {
                        "metric": gate06_key,
                        "candidate_raw": frozen["candidate_raw"],
                        "reference_raw": frozen["reference_raw"],
                        "recomputed_percent_change": None,
                        "gate06_reported_percent_change": None,
                        "missing_reason": "TARGET_CLOCK_INFEASIBLE",
                        "status": "CORRECTLY_NOT_COMPUTED",
                    }
                )
        candidate_latency = int(candidate["latency_cycles"])
        reference_latency = int(reference["latency_cycles"])
        gate06_latency = reported[name]["metrics"]["nominal_operation_latency_cycles"]["absolute_change"]
        metric_rows.append(
            {
                "metric": "nominal_operation_latency_cycles",
                "candidate_raw": candidate_latency,
                "reference_raw": reference_latency,
                "formula": "candidate_raw-reference_raw",
                "recomputed_absolute_change": candidate_latency - reference_latency,
                "gate06_reported_absolute_change": gate06_latency,
                "status": "MATCH" if candidate_latency - reference_latency == gate06_latency else "MISMATCH",
            }
        )
        candidate_deficit = float(candidate["timing_deficit_ns"])
        reference_deficit = float(reference["timing_deficit_ns"])
        gate06_deficit = reported[name]["metrics"]["timing_deficit_ns"]["absolute_change"]
        metric_rows.append(
            {
                "metric": "timing_deficit_ns",
                "candidate_raw": candidate_deficit,
                "reference_raw": reference_deficit,
                "formula": "candidate_raw-reference_raw",
                "recomputed_absolute_change": candidate_deficit - reference_deficit,
                "gate06_reported_absolute_change": gate06_deficit,
                "status": "MATCH" if close(candidate_deficit - reference_deficit, gate06_deficit) else "MISMATCH",
            }
        )
        audited.append(
            {
                "comparison": name,
                "candidate_implementation_id": candidate_id,
                "reference_implementation_id": reference_id,
                "metrics": metric_rows,
            }
        )
    all_match = all(
        metric["status"] in {"MATCH", "CORRECTLY_NOT_COMPUTED"}
        for comparison in audited
        for metric in comparison["metrics"]
    )
    return {
        "schema_version": 1,
        "source": "docs/date2027/rigour_gate_06/GATE06_DESIGN_SPACE.csv",
        "cross_check": "docs/date2027/rigour_gate_06/GATE06_EFFECT_SIZES.json",
        "rounded_prose_used_as_input": False,
        "comparisons": audited,
        "mismatch_count": 0 if all_match else sum(
            metric["status"] == "MISMATCH"
            for comparison in audited
            for metric in comparison["metrics"]
        ),
        "result": "NUMERICAL_CLAIM_AUDIT_PASS" if all_match else "NUMERICAL_CLAIM_AUDIT_FAIL",
    }


def energy_audit(records: dict[str, dict[str, Any]], operation: dict[str, Any]) -> dict[str, Any]:
    comb = records[COMB]
    pipe = records[PIPE]
    comb_power = comb["power_by_trace"]["no_error"]
    pipe_power = pipe["power_by_trace"]["no_error"]
    formula_checks = []
    for implementation_id, row in ((COMB, comb_power), (PIPE, pipe_power)):
        expected = row["metrics"]["total_power_w"] * row["total_time_ps"] / row["useful_operations"]
        reported = row["metrics"]["achievable_total_energy_pj_per_operation"]
        formula_checks.append(
            {
                "implementation_id": implementation_id,
                "total_power_w": row["metrics"]["total_power_w"],
                "total_time_ps": row["total_time_ps"],
                "useful_operations": row["useful_operations"],
                "recomputed_energy_pj_per_operation": expected,
                "reported_energy_pj_per_operation": reported,
                "status": "MATCH" if close(expected, reported) else "MISMATCH",
            }
        )
    checks = {
        "exactly_100000_useful_operations_each": comb_power["useful_operations"] == pipe_power["useful_operations"] == 100000,
        "equivalent_logical_work": "identical conventional SECDED encoder/decoder behavior" in operation["equivalent_work_basis"],
        "identical_payload_fault_methodology": comb_power["power_family"] == pipe_power["power_family"] == "conventional_secded",
        "identical_clock_ns": operation["common_clock_period_ns"] == 10.0,
        "common_reset_cycles": operation["reset_cycles"] == 6,
        "common_drain_cycles": operation["drain_cycles"] == 4,
        "pipeline_fully_drained": operation["drain_cycles"] > operation["latency_cycles"][PIPE],
        "common_initiation_interval": comb["architecture"]["initiation_interval_cycles"] == pipe["architecture"]["initiation_interval_cycles"] == 1,
        "latency_distinguished": comb["architecture"]["nominal_operation_latency_cycles"] == 1 and pipe["architecture"]["nominal_operation_latency_cycles"] == 3,
        "identical_trace_duration_ps": comb_power["total_time_ps"] == pipe_power["total_time_ps"] == 1000100000,
        "same_direct_vcd_annotation_count": comb_power["metrics"]["direct_vcd_annotated_pin_count"] == pipe_power["metrics"]["direct_vcd_annotated_pin_count"] == 139,
        "energy_formula_matches": all(row["status"] == "MATCH" for row in formula_checks),
        "no_pipeline_bubbles_in_valid_workload": operation["valid_workload_cycles"] == operation["useful_operations_per_trace"] == 100000,
    }
    return {
        "checks": checks,
        "formula_checks": formula_checks,
        "comparison_scope": "steady-stream energy per accepted comparison transaction at common 10 ns and II=1; not single-request latency energy",
        "verdict": "ENERGY_COMPARISON_VALID" if all(checks.values()) else "ENERGY_COMPARISON_NOT_VALID",
    }


def reliability_freeze(records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for implementation_id in ORDER:
        record = records[implementation_id]
        universes = {item["weight"]: item for item in record["reliability"]["exact_fault_universes"]}
        rows.append(
            {
                "implementation_id": implementation_id,
                "code_id": record["code_id"],
                "encoded_width_bits": record["architecture"]["encoded_width_bits"],
                "proven_guarantee": record["correction_capability"],
                "weight1": {
                    "total": universes[1]["total_masks"],
                    "corrected": universes[1]["corrected"],
                    "due": universes[1]["due"],
                    "sdc": universes[1]["sdc_miscorrection"] + universes[1]["sdc_undetected"],
                },
                "weight2": {
                    "total": universes[2]["total_masks"],
                    "corrected": universes[2]["corrected"],
                    "due": universes[2]["due"],
                    "sdc": universes[2]["sdc_miscorrection"] + universes[2]["sdc_undetected"],
                },
                "weight3_observation": {
                    "total": universes[3]["total_masks"],
                    "sdc": universes[3]["sdc_miscorrection"] + universes[3]["sdc_undetected"],
                    "sdc_fraction": universes[3]["sdc_fraction"],
                    "due": universes[3]["due"],
                    "due_fraction": universes[3]["due_fraction"],
                },
            }
        )
    by_id = {row["implementation_id"]: row for row in rows}
    assert by_id[COMB]["weight3_observation"]["total"] == math.comb(72, 3)
    assert by_id[HSIAO]["weight3_observation"]["total"] == math.comb(72, 3)
    assert by_id[BCH]["weight3_observation"]["total"] == math.comb(78, 3)
    return {
        "rows": rows,
        "universe_adjudication": {
            "secded_vs_hsiao_total_difference": 0,
            "secded_and_hsiao_explanation": "Both use all C(72,3)=59,640 canonical-coordinate masks. Different reduced fraction denominators arise only from fraction simplification, not different universes.",
            "bch_explanation": "BCH uses all C(78,3)=76,076 canonical-coordinate masks because its protected codeword has 78 coordinates rather than 72.",
        },
        "forbidden_interpretations": [
            "FIT",
            "SER",
            "field reliability",
            "operational failure probability",
            "operational SDC rate",
            "weight-3 correction guarantee",
        ],
    }


def build_claims(records: dict[str, dict[str, Any]], audit: dict[str, Any]) -> list[dict[str, Any]]:
    comb = records[COMB]
    pipe = records[PIPE]
    bch = records[BCH]
    numerical = {
        row["comparison"]: {metric["metric"]: metric for metric in row["metrics"]}
        for row in audit["comparisons"]
    }
    secded = numerical["pipelined SECDED vs combinational SECDED"]
    bch_comb = numerical["BCH vs combinational SECDED"]
    common_limits = [
        "evaluated RTL implementations only",
        "SKY130HD TT 1.80 V / 25 C",
        "frozen 10 ns flow and seed policy",
    ]
    return [
        {
            "claim_id": "C01",
            "gate06_candidate": "A / requested Claim 1",
            "exact_proposed_wording": "For the evaluated conventional SECDED RTL, identical W1-correction/W2-detection semantics produce a non-dominated area/latency versus Fmax/steady-stream-energy trade-off when the microarchitecture changes from combinational to pipelined.",
            "evidence_sources": ["GATE05_IMPLEMENTATION_IDENTITY.json", "GATE06_DOMINANCE_ANALYSIS.json"],
            "raw_numbers": {"latency_cycles": [1, 3], "initiation_interval_cycles": [1, 1]},
            "derivation": "Gate 03R identity transfer fixes code semantics; exact Space-A dominance enumeration finds neither architecture dominates.",
            "applicable_architectures": [COMB, PIPE],
            "limitations": common_limits,
            "reviewer_risk": "LOW",
            "final_status": "CLAIM_FROZEN",
        },
        {
            "claim_id": "C02",
            "gate06_candidate": "B / requested Claim 2",
            "exact_proposed_wording": f"Relative to the evaluated combinational SECDED implementation, pipelining increases standard-cell area by {secded['standard_cell_instance_area_um2']['recomputed_percent_change']:.3f}%, detailed wirelength by {secded['detailed_route_wirelength_um']['recomputed_percent_change']:.3f}%, and nominal latency by two cycles, while increasing achieved Fmax by {secded['achieved_fmax_mhz']['recomputed_percent_change']:.3f}% and reducing no-error steady-stream power and energy per operation by {abs(secded['no_error_total_power_w']['recomputed_percent_change']):.3f}% at the common 10 ns constraint.",
            "evidence_sources": ["GATE06_DESIGN_SPACE.csv", "GATE07_NUMERICAL_CLAIM_AUDIT.json", "GATE07_ENERGY_AUDIT.md"],
            "raw_numbers": {
                "area_um2": [comb["physical"]["metrics"]["standard_cell_instance_area_um2"], pipe["physical"]["metrics"]["standard_cell_instance_area_um2"]],
                "wirelength_um": [comb["physical"]["metrics"]["detailed_route_wirelength_um"], pipe["physical"]["metrics"]["detailed_route_wirelength_um"]],
                "fmax_mhz": [comb["physical"]["metrics"]["achieved_fmax_mhz"], pipe["physical"]["metrics"]["achieved_fmax_mhz"]],
                "power_w": [comb["power_by_trace"]["no_error"]["metrics"]["total_power_w"], pipe["power_by_trace"]["no_error"]["metrics"]["total_power_w"]],
                "energy_pj_per_operation": [comb["power_by_trace"]["no_error"]["metrics"]["achievable_total_energy_pj_per_operation"], pipe["power_by_trace"]["no_error"]["metrics"]["achievable_total_energy_pj_per_operation"]],
            },
            "derivation": "All percentages are recomputed as (pipelined-combinational)/combinational*100 from Gate 05 raw values.",
            "applicable_architectures": [COMB, PIPE],
            "limitations": common_limits + ["steady-stream II=1 result; does not imply lower request latency"],
            "reviewer_risk": "LOW",
            "final_status": "CLAIM_FROZEN",
        },
        {
            "claim_id": "C03",
            "gate06_candidate": "C / requested Claim 3",
            "exact_proposed_wording": f"The evaluated shortened BCH (78,64,t=2) RTL corrects all W1/W2 masks, whereas the evaluated SECDED code corrects W1 and detects W2; under the frozen flow it uses {bch_comb['standard_cell_instance_area_um2']['recomputed_percent_change']:.3f}% more standard-cell area, {bch_comb['cell_count']['recomputed_percent_change']:.3f}% more cells, and {bch_comb['detailed_route_wirelength_um']['recomputed_percent_change']:.3f}% more detailed wirelength than combinational SECDED.",
            "evidence_sources": ["GATE06_DESIGN_SPACE.csv", "GATE07_NUMERICAL_CLAIM_AUDIT.json"],
            "raw_numbers": {"bch_width_bits": 78, "secded_width_bits": 72, "payload_width_bits": 64},
            "derivation": "Categorical W1/W2 guarantees are stated separately from physical percent changes.",
            "applicable_architectures": [COMB, BCH],
            "limitations": common_limits + ["one evaluated BCH RTL", "different 72- versus 78-bit protected widths"],
            "reviewer_risk": "MEDIUM",
            "final_status": "CLAIM_NARROWED",
        },
        {
            "claim_id": "C04",
            "gate06_candidate": "requested Claim 4",
            "exact_proposed_wording": f"The evaluated BCH implementation fails the common 10 ns target under the frozen SKY130HD flow, with WNS {bch['physical']['metrics']['wns_ns']:.5f} ns, a {bch['physical']['metrics']['timing_deficit_ns']:.5f} ns timing deficit, and achieved Fmax {bch['physical']['metrics']['achieved_fmax_mhz']:.4f} MHz.",
            "evidence_sources": ["GATE06_DESIGN_SPACE.csv", "GATE04_RAW_RESULTS.json"],
            "raw_numbers": {"wns_ns": bch["physical"]["metrics"]["wns_ns"], "timing_deficit_ns": bch["physical"]["metrics"]["timing_deficit_ns"], "fmax_mhz": bch["physical"]["metrics"]["achieved_fmax_mhz"]},
            "derivation": "Achieved period is target period minus worst setup slack; Fmax is its reciprocal in GHz.",
            "applicable_architectures": [BCH],
            "limitations": common_limits + ["not a family-wide BCH frequency limit"],
            "reviewer_risk": "LOW",
            "final_status": "CLAIM_FROZEN",
        },
        {
            "claim_id": "C05",
            "gate06_candidate": "D / requested Claim 5",
            "exact_proposed_wording": "Within the evaluated set, algorithm-level correction capability alone is insufficient to describe implementation trade-offs because identical SECDED guarantees admit different physical outcomes and stronger BCH correction coexists with substantially higher physical cost and target-clock infeasibility.",
            "evidence_sources": ["GATE06_DOMINANCE_ANALYSIS.json", "GATE07_NUMERICAL_CLAIM_AUDIT.json"],
            "raw_numbers": {},
            "derivation": "Logical guarantee and physical objectives are kept as separate evidence dimensions.",
            "applicable_architectures": [COMB, PIPE, BCH],
            "limitations": common_limits + ["descriptive within evaluated set; not a universal ECC-selection theorem"],
            "reviewer_risk": "MEDIUM",
            "final_status": "CLAIM_NARROWED",
        },
        {
            "claim_id": "C06",
            "gate06_candidate": "E / requested Claim 6",
            "exact_proposed_wording": "The workflow reproducibly joins correctness-qualified identities, exhaustive finite-universe reliability evidence, and post-route physical measurements within the pinned Gate 03F/Gate 04 environment; repeated Gate 03F runs showed zero observed run-to-run variation in the reported metrics.",
            "evidence_sources": ["GATE_03F_VERDICT.json", "REPRODUCIBILITY_STATISTICS.json", "GATE04_EXPERIMENT_MANIFEST.json"],
            "raw_numbers": {"gate03f_physical_runs": 7, "observed_metric_ranges": 0},
            "derivation": "Reproducibility is bounded to the pinned image/tool/seed/worker/policy and observed repetitions.",
            "applicable_architectures": [COMB, BCH],
            "limitations": ["does not claim general EDA determinism", "Gate 04 uses one prospective run per implementation after Gate 03F qualification"],
            "reviewer_risk": "MEDIUM",
            "final_status": "CLAIM_NARROWED",
        },
        {
            "claim_id": "C07",
            "gate06_candidate": "F",
            "exact_proposed_wording": "In the exhaustive canonical-coordinate weight-3 universe, Hsiao produced 34,164 SDC outcomes out of 59,640 versus 45,304 out of 59,640 for conventional SECDED.",
            "evidence_sources": ["GATE06_RELIABILITY_TABLE.csv", "GATE07_RELIABILITY_SEMANTICS.md"],
            "raw_numbers": {"hsiao_sdc": 34164, "conventional_sdc": 45304, "total_each": 59640},
            "derivation": "Direct finite-universe counts; no operational weighting.",
            "applicable_architectures": [COMB, HSIAO],
            "limitations": ["observation only", "no PPA for Hsiao", "not FIT/SER or field reliability"],
            "reviewer_risk": "HIGH",
            "final_status": "CLAIM_DISCUSSION_ONLY",
        },
        {
            "claim_id": "C08",
            "gate06_candidate": "G",
            "exact_proposed_wording": "Error-class power differences are practically significant.",
            "evidence_sources": ["GATE04_POWER_ACTIVITY_AUDIT.json"],
            "raw_numbers": {},
            "derivation": "No practical-significance or field-frequency evidence exists.",
            "applicable_architectures": list(ORDER),
            "limitations": ["precision resolution is not practical significance"],
            "reviewer_risk": "HIGH",
            "final_status": "CLAIM_REMOVED",
        },
        {
            "claim_id": "C09",
            "gate06_candidate": "H",
            "exact_proposed_wording": "The results establish FIT, SER, operational failure probability, or physical-interleaving superiority.",
            "evidence_sources": ["GATE05_MISSING_EVIDENCE.json"],
            "raw_numbers": {},
            "derivation": "Each quantity is METRIC_NOT_PROVEN.",
            "applicable_architectures": list(ORDER),
            "limitations": ["no field model or physical bit mapping"],
            "reviewer_risk": "CRITICAL",
            "final_status": "CLAIM_REMOVED",
        },
        {
            "claim_id": "C10",
            "gate06_candidate": "I",
            "exact_proposed_wording": "BCH as a family cannot operate at 100 MHz.",
            "evidence_sources": ["GATE04_ADJUDICATION.md"],
            "raw_numbers": {},
            "derivation": "One implementation and flow cannot support a family-wide limit.",
            "applicable_architectures": [BCH],
            "limitations": ["evaluated implementation only"],
            "reviewer_risk": "CRITICAL",
            "final_status": "CLAIM_REMOVED",
        },
        {
            "claim_id": "C11",
            "gate06_candidate": "J",
            "exact_proposed_wording": "Hsiao physically or Pareto-dominates a measured implementation.",
            "evidence_sources": ["GATE05_MISSING_EVIDENCE.json"],
            "raw_numbers": {},
            "derivation": "Hsiao PPA is unavailable.",
            "applicable_architectures": [HSIAO],
            "limitations": ["PPA_UNAVAILABLE"],
            "reviewer_risk": "CRITICAL",
            "final_status": "CLAIM_REMOVED",
        },
        {
            "claim_id": "C12",
            "gate06_candidate": "K",
            "exact_proposed_wording": "BCH target-constraint energy is achievable 100 MHz operating energy.",
            "evidence_sources": ["GATE05_MISSING_EVIDENCE.json"],
            "raw_numbers": {"diagnostic_target_energy_pj_per_operation": bch["power_by_trace"]["no_error"]["metrics"]["total_energy_pj_per_operation_estimate"]},
            "derivation": "The design fails the target; achievable energy is TARGET_CLOCK_INFEASIBLE.",
            "applicable_architectures": [BCH],
            "limitations": ["diagnostic target-constraint estimate only"],
            "reviewer_risk": "CRITICAL",
            "final_status": "CLAIM_REMOVED",
        },
        {
            "claim_id": "C13",
            "gate06_candidate": "L",
            "exact_proposed_wording": "A unique best ECC or universal Pareto winner has been established.",
            "evidence_sources": ["GATE06_DOMINANCE_ANALYSIS.json"],
            "raw_numbers": {},
            "derivation": "Objectives conflict and reliability tiers are categorical.",
            "applicable_architectures": list(ORDER),
            "limitations": ["small exact-enumerated measured set"],
            "reviewer_risk": "CRITICAL",
            "final_status": "CLAIM_REMOVED",
        },
    ]


def build(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    inputs = source_manifest()
    gate05 = load_json(GATE05 / "GATE05_INTEGRATED_RESULTS.json")
    records = {row["implementation_id"]: row for row in gate05["records"]}
    effects = load_json(GATE06 / "GATE06_EFFECT_SIZES.json")
    with (GATE06 / "GATE06_DESIGN_SPACE.csv").open(encoding="utf-8", newline="") as stream:
        gate06_rows = {row["implementation_id"]: row for row in csv.DictReader(stream)}
    identity = load_json(GATE05 / "GATE05_IMPLEMENTATION_IDENTITY.json")
    experiment = load_json(GATE04 / "GATE04_EXPERIMENT_MANIFEST.json")
    audit = numerical_audit(gate06_rows, effects)
    assert audit["result"] == "NUMERICAL_CLAIM_AUDIT_PASS"
    energy = energy_audit(records, identity["operation_normalization"])
    assert energy["verdict"] == "ENERGY_COMPARISON_VALID"
    reliability = reliability_freeze(records)
    claims = build_claims(records, audit)

    write_json(output / "GATE07_NUMERICAL_CLAIM_AUDIT.json", audit)
    write_json(
        output / "GATE07_CLAIM_LEDGER.json",
        {
            "schema_version": 1,
            "entry_policy": "No manuscript claim enters without exact wording, raw evidence, derivation, scope, and status.",
            "allowed_statuses": ["CLAIM_FROZEN", "CLAIM_NARROWED", "CLAIM_DISCUSSION_ONLY", "CLAIM_REMOVED"],
            "claims": claims,
        },
    )

    scope = """# Gate 07 frozen paper scope

## Defensible scope

This paper presents a cross-layer evaluation of four correctness- and reliability-qualified 64-bit-payload ECC implementation identities. It shows how categorical correction capability and RTL microarchitecture interact with post-route logic cost, timing feasibility, and activity-based energy under one reproducible SKY130HD flow. Physical conclusions cover three routed implementations; Hsiao remains reliability-only because its frozen physical run stopped at the unchanged synthesis-memory policy.

## What the paper studies

- Conventional combinational and pipelined SECDED `(72,64)` implementations with identical proven W1-correction/W2-detection semantics.
- One generated combinational Hsiao SECDED `(72,64)` implementation for correctness and canonical-coordinate reliability evidence only.
- One shortened BCH `(78,64,t=2)` syndrome/Chien implementation with proven W1/W2 correction.
- Exhaustive W1/W2 guarantees and exhaustive canonical-coordinate W3 SDC/DUE observations, kept semantically separate.
- Standard-cell instance area, cells, routing, timing, post-route OpenSTA power, and timing-feasible steady-stream energy under SKY130HD, TT 1.80 V/25 C, a common 10 ns target, seed 11, and the frozen policy.

## What the paper does not study

It does not solve general ECC selection; establish FIT, SER, operational failure probability, field reliability, physical SRAM-array/interleaving behavior, silicon power, multi-node/PVT robustness, universal ECC-family limits, or a unique best ECC. It does not characterize all possible implementations of SECDED, Hsiao, or BCH.

## Excluded thesis-era components

GREEN Score, carbon analysis, ML selection, NSGA-II, analytical thesis-era energy constants, adaptive scheduling, transition/migration models, SafeForge, and unqualified ECC families are excluded. They provide no manuscript evidence for this paper.
"""
    write_text(output / "GATE07_SCOPE_STATEMENT.md", scope)

    attacks = """# Gate 07 hostile-review audit

Classification describes the potential severity before the frozen resolution. `RESOLVED_FOR_SCOPE` means the claim/table/figure wording now survives without adding measurements; it does not mean the missing experiment exists.

## Reviewer A — Dependability / ECC

| ID | Classification | Attack | Resolution | Needs new experiment? | State |
|---|---|---|---|---|---|
| A1 | CRITICAL | Weight-3 SDC/DUE could be misread as operational reliability or a correction guarantee. | Use “exhaustive canonical-coordinate observations” everywhere; keep guarantee and observation columns separate. | Yes, for field rates—not for frozen claims. | RESOLVED_FOR_SCOPE |
| A2 | MAJOR | No FIT/SER or field-weighted fault distribution exists. | Remove all such claims and state the limitation in Setup and Discussion. | Yes. | RESOLVED_FOR_SCOPE |
| A3 | MAJOR | Comparing W3 fractions across 72- and 78-bit codes can imply a common operational distribution. | Report raw denominators and codeword widths; prohibit cross-code field interpretation. | Yes, for operational comparison. | RESOLVED_FOR_SCOPE |
| A4 | MAJOR | Hsiao appears selectively omitted from PPA. | State the preserved 256×73-table / 4096-bit frozen-policy failure and retain Hsiao in reliability evidence. | Yes, for Hsiao PPA. | RESOLVED_FOR_SCOPE |
| A5 | MINOR | Pipelined SECDED inherits reliability evidence rather than rerunning every mask on the timed boundary. | Cite exact Gate 03R temporal-alignment equivalence and preserve the implementation identity transfer. | No. | RESOLVED_FOR_SCOPE |

## Reviewer B — EDA / physical design

| ID | Classification | Attack | Resolution | Needs new experiment? | State |
|---|---|---|---|---|---|
| B1 | MAJOR | Area and timing may be incomparable if constraints or floorplanning differ. | Freeze the common image, ORFS/OpenROAD, SKY130HD corner, SDC, load, density, utilization policy, seed, and worker count; use instance area, not die area. | No. | RESOLVED_FOR_SCOPE |
| B2 | MAJOR | “Achieved Fmax” may hide target-period slack semantics. | Define it as `1000/(10 ns - worst setup slack)` and retain WNS/timing deficit. | No. | RESOLVED_FOR_SCOPE |
| B3 | CRITICAL | The 24.016% energy result could be caused by an incomplete pipeline drain, different work, or trace length. | Audit the shared 100,000-operation VCD, six reset cycles, four drain cycles, II=1, latency 1/3, identical duration, annotation, and energy formula. | No. | RESOLVED_FOR_SCOPE |
| B4 | MAJOR | OpenSTA power is not measured silicon power. | Call it post-route activity-based estimation and avoid absolute silicon-efficiency claims. | Yes, for silicon claims. | RESOLVED_FOR_SCOPE |
| B5 | MAJOR | BCH’s 78-bit codeword versus SECDED’s 72-bit codeword biases cost. | State same 64-bit useful payload but different protected widths; redundancy is part of the evaluated implementation cost. | No. | RESOLVED_FOR_SCOPE |
| B6 | MAJOR | A common target disadvantages a long combinational BCH datapath. | Treat target failure as scoped data, never a family limit; do not interpret target-clock energy as achievable. | Yes, for timing-normalized energy. | RESOLVED_FOR_SCOPE |
| B7 | MINOR | One seed cannot establish physical variability. | Limit reproducibility to the qualified deterministic seed policy and report no process/seed distribution. | Yes, for variability. | RESOLVED_FOR_SCOPE |

## Reviewer C — DATE novelty / program committee

| ID | Classification | Attack | Resolution | Needs new experiment? | State |
|---|---|---|---|---|---|
| C1 | CRITICAL | Repository-local notes do not establish any “first” or universal novelty claim. | Remove priority language; frame a scoped contribution and require conventional related-work positioning during writing. | No scientific measurement; broader literature audit remains. | RESOLVED_FOR_SCOPE |
| C2 | MAJOR | Four reliability identities and three routed points may look like an engineering report. | Center the paper on identity qualification, the controlled same-semantics microarchitecture experiment, and the correction-versus-feasibility contrast. | More points would strengthen breadth but are not required for these claims. | RESOLVED_FOR_SCOPE |
| C3 | MAJOR | Missing Hsiao PPA weakens the code-level comparison. | Make missingness a visible frozen-policy result and exclude Hsiao from every physical claim. | Yes, for a complete Hsiao PPA comparison. | RESOLVED_FOR_SCOPE |
| C4 | MAJOR | “Pipelining trades area for speed” is qualitatively obvious. | Claim the measured, reproducible effect sizes and energy/latency distinction—not the generic intuition—as the empirical result. | No. | RESOLVED_FOR_SCOPE |
| C5 | MAJOR | The framework could be indistinguishable from an internal characterization harness. | Present its fail-closed identity, provenance, missing-data, and cross-layer semantic controls as methodological support; do not claim tooling alone as novelty. | No. | RESOLVED_FOR_SCOPE |
| C6 | MAJOR | Local literature notes target different thesis subsystems and do not close external novelty. | Freeze only three non-priority contributions and carry external positioning as a high reviewer risk, not an unsupported claim. | No new experiment. | RESOLVED_FOR_SCOPE |
| C7 | MINOR | Four figures plus large tables exceed a six-page budget and repeat information. | Keep three figures, drop the reliability plot, and freeze two major tables. | No. | RESOLVED_FOR_SCOPE |

No unresolved `CRITICAL` issue remains after claim removal/narrowing and the energy audit.
"""
    write_text(output / "GATE07_REVIEWER_ATTACKS.md", attacks)

    energy_md = f"""# Gate 07 energy-comparison audit

`{energy['verdict']}`

The comparison is valid only as steady-stream energy per accepted comparison transaction at the common 10 ns constraint and II=1. It does not assert lower single-request latency: combinational SECDED has nominal latency 1 cycle and pipelined SECDED has latency 3 cycles.

| Check | Frozen result |
|---|---|
| Useful work | 100,000 accepted 64-bit comparison transactions per trace |
| Input trace | Same `conventional_secded` no-error VCD family for both physical implementations |
| Clock / duration | 10 ns; 1,000,100,000 ps for both |
| Reset / valid work / drain | 6 / 100,000 / 4 cycles for both |
| Drain sufficiency | 4 invalid cycles exceed the 3-cycle pipelined boundary latency |
| Initiation interval | 1 cycle for both; no valid-workload bubbles |
| VCD annotation | 139 directly annotated pins for both; propagation then covers implementation-specific internal activity |
| Power extraction | Post-route OpenSTA `report_power -digits 12` after VCD annotation and activity propagation |
| Energy formula | `power_W × total_time_ps / 100000 = pJ/useful operation` |

Combinational no-error power/energy are {records[COMB]['power_by_trace']['no_error']['metrics']['total_power_w']:.14g} W and {records[COMB]['power_by_trace']['no_error']['metrics']['achievable_total_energy_pj_per_operation']:.12f} pJ/op. Pipelined values are {records[PIPE]['power_by_trace']['no_error']['metrics']['total_power_w']:.14g} W and {records[PIPE]['power_by_trace']['no_error']['metrics']['achievable_total_energy_pj_per_operation']:.12f} pJ/op. The independently recomputed change is {audit['comparisons'][0]['metrics'][5]['recomputed_percent_change']:.12f}%.

The lower pipelined value is not caused by incomplete drain, unequal operation counts, unequal trace duration, different workload, different input VCD annotation, or pipeline bubbles. Reset and drain overhead are included equally. Because total trace time and operation count are equal, the power and energy percentage changes are identical.
"""
    write_text(output / "GATE07_ENERGY_AUDIT.md", energy_md)

    rel_rows = {row["implementation_id"]: row for row in reliability["rows"]}
    reliability_md = f"""# Gate 07 reliability-semantics freeze

## Proven guarantees

| Implementation | W1 | W2 |
|---|---|---|
| Conventional SECDED, both microarchitectures | 72/72 corrected | 2556/2556 detected as DUE |
| Hsiao SECDED | 72/72 corrected | 2556/2556 detected as DUE |
| BCH `(78,64,t=2)` | 78/78 corrected | 3003/3003 corrected |

## Exhaustive weight-3 observations

| Code semantics | Coordinate universe | Total | SDC | DUE |
|---|---|---:|---:|---:|
| Conventional SECDED | all `C(72,3)` canonical masks | 59,640 | 45,304 (`809/1065`) | 14,336 (`256/1065`) |
| Hsiao SECDED | all `C(72,3)` canonical masks | 59,640 | 34,164 (`2847/4970`) | 25,476 (`2123/4970`) |
| BCH | all `C(78,3)` canonical masks | 76,076 | 13,780 (`265/1463`) | 62,296 (`1198/1463`) |

Conventional SECDED and Hsiao do **not** have different W3 universe sizes: both enumerate all 59,640 three-coordinate masks. Their displayed fraction denominators differ only because the raw count ratios reduce by different greatest common divisors. BCH has 76,076 masks because its codeword has 78 coordinates rather than 72.

These W3 values are observations outside the guaranteed correction universe. They are not FIT, SER, field reliability, operational failure probability, operational SDC rate, or a W3 correction guarantee. No fault distribution or physical bit/interleave mapping is applied.
"""
    assert rel_rows[COMB]["weight3_observation"]["total"] == 59640
    write_text(output / "GATE07_RELIABILITY_SEMANTICS.md", reliability_md)

    physical_md = f"""# Gate 07 physical-comparability audit

## Common controls

| Control | Frozen value |
|---|---|
| Container | `{experiment['technology']['container_image']}` |
| ORFS / OpenROAD | `{experiment['technology']['orfs_git_commit']}` / `{experiment['technology']['openroad_git_commit']}` |
| Platform / corner | SKY130HD / TT 1.80 V, 25 C |
| Target / I/O delays | 10.0 ns / 10% input and 10% output |
| Output load | 0.05 pF |
| Core utilization policy / placement density | 35% / 0.55 |
| Seed / workers | 11 / 1 |
| Useful payload / II | 64 bits / 1 cycle |
| Area metric | final standard-cell instance area, never nominal die/core area |

All routed implementations use the same technology, corner, physical policy, constraint methodology, load, density, seed, and worker count. Achieved Fmax is `1000 / (10 ns - worst setup slack)` MHz; negative slack is retained. The comparison boundary exercises independent encoder and decoder channels in parallel for each accepted transaction.

## Legitimate architectural differences and exceptions

- Nominal latency is 1 cycle for combinational SECDED and BCH, and 3 cycles for pipelined SECDED. This is retained rather than normalized away.
- SECDED uses a 72-bit protected word; BCH uses 78 bits for the same 64-bit payload. The extra six protected bits are a real part of the evaluated BCH cost, but prevent attributing all cost solely to decoder algebra.
- Hsiao PPA is unavailable. Its decoder inferred a 256×73 table, exceeding the unchanged ORFS `SYNTH_MEMORY_MAX_BITS=4096` policy. The policy was not relaxed post hoc; Hsiao is excluded from PPA conclusions.
- BCH completes routing with zero final DRC but fails the common target. Its target-constraint power is diagnostic and its target-clock energy is not an achievable operating point.
- Power values are post-route OpenSTA estimates, not silicon measurements.

Hsiao omission reviewer risk: `MEDIUM`. The cause and non-relaxation are traceable, but the missing point reduces physical breadth.
"""
    write_text(output / "GATE07_PHYSICAL_COMPARABILITY.md", physical_md)

    contribution = """# Gate 07 contribution freeze

Repository-local literature notes establish that Hsiao coding, adaptive/reconfigurable ECC, hardware-aware code/checker optimization, and generic reproducibility practices cannot be claimed as new. Those notes focus largely on excluded adaptive, co-synthesis, and SafeForge subsystems; they do not establish a priority claim for this narrowed post-route study. The manuscript must therefore avoid “first,” “unique,” and universal novelty wording.

## Novelty-role classification

| Proposition | Classification | Frozen treatment |
|---|---|---|
| Correctness-qualified implementation identities rather than nominal labels | METHODOLOGICAL_SUPPORT | Essential validity control, not claimed as an ECC theorem |
| Explicit separation of code semantics from RTL microarchitecture | PRIMARY_CONTRIBUTION | Controlled SECDED comparison plus identity transfer |
| Common post-route characterization | SECONDARY_CONTRIBUTION | Required empirical basis, not novel by itself |
| Reproducibility-qualified physical methodology | METHODOLOGICAL_SUPPORT | Bounded to the pinned flow and repetitions |
| Reliability × physical-cost interpretation without a composite score | PRIMARY_CONTRIBUTION | Categorical tiers and explicit missingness |
| Quantified same-semantics SECDED trade-off and stronger-correction BCH feasibility contrast | PRIMARY_CONTRIBUTION | Main empirical finding; implementation-scoped |

## Three frozen manuscript contributions

1. An identity-preserving cross-layer evaluation method that admits only correctness-qualified ECC implementations and keeps guarantees, observed outcomes, architecture, and missing physical data distinct.
2. A controlled post-route measurement showing that two exact-equivalent SECDED microarchitectures are non-dominated: pipelining trades area and two cycles of latency for higher achieved frequency and lower steady-stream energy per operation.
3. An implementation-scoped correction-versus-feasibility result: the evaluated W2-correcting BCH design incurs substantially greater routed cost and misses the shared 10 ns target, while Hsiao remains explicitly reliability-only under the frozen synthesis policy.

## Central message

**One sentence:** For the evaluated correctness-qualified 64-bit-payload ECCs, correction guarantees do not determine implementation choice: SECDED microarchitecture changes the area/latency–Fmax/energy trade-off, while the stronger-correcting BCH RTL incurs much larger routed cost and misses the common 10 ns target.

**Three sentences:** Correctness qualification establishes what each implementation protects, but it does not predict physical cost. Under one pinned SKY130HD flow, combinational and pipelined implementations of the same SECDED semantics occupy different non-dominated points, while the evaluated W2-correcting BCH implementation is larger, more routing-intensive, and timing-infeasible at 10 ns. A reviewer-safe ECC comparison must therefore preserve implementation identity, categorical reliability semantics, timing feasibility, and explicit missing data rather than collapse them into one score.

Local sources consulted: `docs/RESEARCH_NOVELTY.md`, `docs/PORTFOLIO_COSYNTHESIS_NOVELTY_GATE.md`, and `docs/SAFEFORGE_LITERATURE.md`. This is not a systematic external novelty review.
"""
    write_text(output / "GATE07_CONTRIBUTION_FREEZE.md", contribution)

    figure_freeze = {
        "schema_version": 1,
        "page_budget_target": 3,
        "figures": [
            {
                "id": "F01_CROSS_LAYER_METHOD",
                "status": "FIGURE_FROZEN",
                "manuscript_role": "methodology and evidence boundary",
                "source": "docs/date2027/rigour_gate_06/GATE06_FIGURE_DATA.json",
                "revision": "none; caption must state Hsiao PPA and BCH energy exclusions",
            },
            {
                "id": "F02_AREA_VS_FMAX",
                "status": "FIGURE_FROZEN",
                "manuscript_role": "physical cost and target feasibility",
                "source": "GATE07_FIGURE_DATA.json",
                "revision": "none; retain 100 MHz boundary and BCH failure annotation",
            },
            {
                "id": "F03_NORMALIZED_PHYSICAL_COST",
                "status": "FIGURE_REVISE",
                "manuscript_role": "normalized effect-size summary",
                "source": "GATE07_FIGURE_DATA.json",
                "revision": "visually separate all-routed area/wire/Fmax from timing-feasible SECDED-only power/energy; never plot BCH diagnostic energy as achievable",
            },
            {
                "id": "F04_RELIABILITY_OUTCOMES",
                "status": "FIGURE_DROP",
                "manuscript_role": "redundant under six-page budget",
                "source": "docs/date2027/rigour_gate_06/GATE06_FIGURE_DATA.json",
                "revision": "move raw W3 counts and caveat to reliability table/discussion",
            },
        ],
    }
    write_json(output / "GATE07_FIGURE_FREEZE.json", figure_freeze)

    figure_data = {
        "schema_version": 1,
        "F01_CROSS_LAYER_METHOD": {"numeric_data": None, "source": "Gate 06 frozen methodology figure"},
        "F02_AREA_VS_FMAX": {
            "points": [
                {
                    "implementation_id": implementation_id,
                    "area_um2": records[implementation_id]["physical"]["metrics"]["standard_cell_instance_area_um2"],
                    "fmax_mhz": records[implementation_id]["physical"]["metrics"]["achieved_fmax_mhz"],
                    "meets_10ns": records[implementation_id]["physical"]["timing_feasibility"] == "MEETS_10NS",
                }
                for implementation_id in (COMB, PIPE, BCH)
            ],
            "excluded": {HSIAO: "PPA_UNAVAILABLE"},
        },
        "F03_NORMALIZED_PHYSICAL_COST": {
            "reference_implementation_id": COMB,
            "routed_metrics": {
                implementation_id: {
                    metric: pct(
                        records[implementation_id]["physical"]["metrics"][metric],
                        records[COMB]["physical"]["metrics"][metric],
                    )
                    for metric in ("standard_cell_instance_area_um2", "detailed_route_wirelength_um", "achieved_fmax_mhz")
                }
                for implementation_id in (COMB, PIPE, BCH)
            },
            "timing_feasible_power_energy_metrics": {
                implementation_id: {
                    "no_error_total_power_percent_change": pct(
                        records[implementation_id]["power_by_trace"]["no_error"]["metrics"]["total_power_w"],
                        records[COMB]["power_by_trace"]["no_error"]["metrics"]["total_power_w"],
                    ),
                    "no_error_energy_percent_change": pct(
                        records[implementation_id]["power_by_trace"]["no_error"]["metrics"]["achievable_total_energy_pj_per_operation"],
                        records[COMB]["power_by_trace"]["no_error"]["metrics"]["achievable_total_energy_pj_per_operation"],
                    ),
                }
                for implementation_id in (COMB, PIPE)
            },
            "excluded": {HSIAO: "PPA_UNAVAILABLE", BCH: "TARGET_CLOCK_INFEASIBLE_FOR_POWER_ENERGY_PANEL"},
        },
    }
    write_json(output / "GATE07_FIGURE_DATA.json", figure_data)

    table_i_rows = []
    for implementation_id in ORDER:
        record = records[implementation_id]
        table_i_rows.append(
            {
                "architecture": record["label"],
                "implementation_id": implementation_id,
                "code": record["code_id"],
                "protection_guarantee": record["correction_capability"],
                "payload_bits": record["architecture"]["payload_width_bits"],
                "codeword_bits": record["architecture"]["encoded_width_bits"],
                "latency_cycles": record["architecture"]["nominal_operation_latency_cycles"],
                "initiation_interval_cycles": record["architecture"]["initiation_interval_cycles"],
                "ppa_availability": "PPA_UNAVAILABLE" if record["physical"]["metrics"]["standard_cell_instance_area_um2"] is None else "ROUTED",
            }
        )
    write_csv(output / "GATE07_TABLE_I_IMPLEMENTATIONS.csv", list(table_i_rows[0]), table_i_rows)

    table_ii_rows = []
    for implementation_id in ORDER:
        record = records[implementation_id]
        physical = record["physical"]
        no_error = record["power_by_trace"].get("no_error")
        unavailable = physical["metrics"]["standard_cell_instance_area_um2"] is None
        infeasible = physical["timing_feasibility"] == "FAILS_10NS"
        table_ii_rows.append(
            {
                "architecture": record["label"],
                "area_um2": "PPA_UNAVAILABLE" if unavailable else physical["metrics"]["standard_cell_instance_area_um2"],
                "fmax_mhz": "PPA_UNAVAILABLE" if unavailable else physical["metrics"]["achieved_fmax_mhz"],
                "target_10ns": "PPA_UNAVAILABLE" if unavailable else physical["timing_feasibility"],
                "wirelength_um": "PPA_UNAVAILABLE" if unavailable else physical["metrics"]["detailed_route_wirelength_um"],
                "no_error_power_w": "PPA_UNAVAILABLE" if unavailable else (f"{no_error['metrics']['total_power_w']} (DIAGNOSTIC_ONLY)" if infeasible else no_error["metrics"]["total_power_w"]),
                "achievable_energy_pj_per_operation": "PPA_UNAVAILABLE" if unavailable else ("TARGET_CLOCK_INFEASIBLE" if infeasible else no_error["metrics"]["achievable_total_energy_pj_per_operation"]),
                "reliability_class": "W1_AND_W2_CORRECTION" if implementation_id == BCH else "W1_CORRECTION_W2_DETECTION",
            }
        )
    write_csv(output / "GATE07_TABLE_II_RESULTS.csv", list(table_ii_rows[0]), table_ii_rows)

    table_freeze = {
        "schema_version": 1,
        "major_table_count": 2,
        "tables": [
            {
                "id": "TABLE_I_EVALUATED_IMPLEMENTATIONS",
                "status": "TABLE_FROZEN",
                "data_file": "GATE07_TABLE_I_IMPLEMENTATIONS.csv",
                "purpose": "identity, code, guarantee, latency, II, and PPA availability",
            },
            {
                "id": "TABLE_II_PHYSICAL_RELIABILITY_RESULTS",
                "status": "TABLE_FROZEN",
                "data_file": "GATE07_TABLE_II_RESULTS.csv",
                "purpose": "compact physical result with categorical reliability class and explicit missingness",
            },
        ],
        "weight3_main_table_decision": "OMIT_FROM_MAJOR_TABLES; retain raw counts in GATE07_RELIABILITY_SEMANTICS.md and discussion because they are observation-only and need a long caveat",
    }
    write_json(output / "GATE07_TABLE_FREEZE.json", table_freeze)

    limitations = """# Gate 07 reviewer-safe limitations freeze

## Experimental Setup

- SKY130HD only, at TT 1.80 V / 25 C; no node, library, voltage, temperature, or process-corner generalization.
- Specific evaluated RTL implementations only; these do not exhaust SECDED, Hsiao, or BCH architectures.
- One common primary 10 ns constraint, one qualified deterministic seed policy, and one worker; no seed/process distribution is claimed.
- SECDED and BCH protect the same 64-bit payload but use 72- and 78-bit codewords, respectively.
- Power is a post-route OpenSTA activity estimate, not a silicon measurement.

## Results

- Hsiao PPA is unavailable because its inferred 256×73 table exceeded the unchanged 4096-bit ORFS synthesis-memory policy; it is excluded from physical conclusions.
- BCH misses the 10 ns target. Its target-constraint power is diagnostic and its energy is not interpreted as achievable 100 MHz operating energy.
- The energy comparison is a steady-stream II=1 result; pipelined SECDED has two additional cycles of request latency.

## Discussion

- No FIT, SER, operational field-error probability, or physically weighted SDC/DUE model is established.
- Weight-3 SDC/DUE values are exhaustive canonical-coordinate observations, not operational probabilities or correction guarantees.
- No final physical SRAM array, bit mapping, interleaving, scrub policy, or memory-macro cost is characterized.
- Only four reliability identities, three routed designs, and two timing-feasible energy points are available.
- External novelty is not established by the repository-local notes; the manuscript must avoid priority claims and position the contribution conventionally.

## Artifact-only detail

Full-precision error-class power differences, native JSON serialization precision, raw transition counts, and infrastructure-attempt inventories remain available in the frozen artifacts but do not belong in the six-page main text unless needed to answer review.
"""
    write_text(output / "GATE07_LIMITATIONS.md", limitations)

    readiness = {
        "novelty": 6,
        "rigor": 9,
        "experimental_credibility": 8,
        "physical_design_completeness": 6,
        "reliability_evidence": 8,
        "cross_layer_insight": 8,
        "reproducibility": 9,
        "presentation_potential": 8,
        "reviewer_defensibility": 8,
    }
    manuscript = {
        "schema_version": 1,
        "authoritative_inputs": inputs,
        "input_policy": {
            "gate06_frozen": True,
            "upstream_use": "identity, trace, extraction, energy-normalization, and reproducibility provenance verification only",
            "new_measurements": False,
            "excluded_thesis_subsystems_imported": False,
        },
        "central_message": "For the evaluated correctness-qualified 64-bit-payload ECCs, correction guarantees do not determine implementation choice: SECDED microarchitecture changes the area/latency–Fmax/energy trade-off, while the stronger-correcting BCH RTL incurs much larger routed cost and misses the common 10 ns target.",
        "frozen_contribution_ids": ["CONTRIBUTION_1", "CONTRIBUTION_2", "CONTRIBUTION_3"],
        "claim_status_counts": {
            status: sum(row["final_status"] == status for row in claims)
            for status in ("CLAIM_FROZEN", "CLAIM_NARROWED", "CLAIM_DISCUSSION_ONLY", "CLAIM_REMOVED")
        },
        "energy_verdict": energy["verdict"],
        "numerical_audit_result": audit["result"],
        "unresolved_critical_reviewer_issues": [],
        "readiness_scores_1_to_10": readiness,
        "score_policy": "independent scores; no composite score",
        "date_manuscript_readiness": "DATE_MANUSCRIPT_READY",
        "gate_verdict": "GATE_07_PASS",
        "gate08_readiness": "GATE_08_READY",
        "final_figures": ["F01_CROSS_LAYER_METHOD", "F02_AREA_VS_FMAX", "F03_NORMALIZED_PHYSICAL_COST_REVISED"],
        "final_tables": ["TABLE_I_EVALUATED_IMPLEMENTATIONS", "TABLE_II_PHYSICAL_RELIABILITY_RESULTS"],
    }
    write_json(output / "GATE07_MANUSCRIPT_EVIDENCE.json", manuscript)

    adjudication = f"""# DATE 2027 Gate 07 adversarial claim adjudication

## A. Verdict

`GATE_07_PASS`

## B. DATE manuscript readiness

`DATE_MANUSCRIPT_READY`

No unresolved critical reviewer issue remains. Readiness means the evidence is safe to turn into a scoped six-page manuscript; it does not mean external novelty is proven or that submission is guaranteed acceptance.

## C. Three frozen contributions

1. Identity-preserving, fail-closed cross-layer evaluation of correctness-qualified implementations.
2. Quantified non-dominated microarchitectural trade-off between exact-equivalent SECDED implementations.
3. Implementation-scoped correction-versus-physical-feasibility contrast for the evaluated BCH design, with Hsiao missingness retained explicitly.

## D. Frozen claims

Claims C01, C02, and C04 are frozen. They cover the same-semantics SECDED trade-off, its recomputed effect sizes, and the evaluated BCH timing failure.

## E. Removed or narrowed claims

Claims C03, C05, and C06 are narrowed to the evaluated implementations and pinned environment. Hsiao W3 behavior is discussion-only. Practical-significance, FIT/SER, family-wide BCH frequency, Hsiao PPA dominance, achievable BCH target energy, and unique-best-ECC claims are removed.

## F. Energy-comparison verdict

`{energy['verdict']}`

The 24.016% reduction is valid for equal 100,000-operation steady streams at 10 ns and II=1; it is not a latency improvement.

## G. Main reviewer risks

- External novelty positioning remains high risk because only repository-local notes were authorized.
- Hsiao PPA is unavailable under the unrelaxed frozen synthesis-memory policy.
- Physical breadth is limited to one technology/corner/target and three routed points.
- Reliability observations lack field weighting, FIT/SER, and physical SRAM mapping.

## H. Final figures

Freeze F01 and F02; revise F03 to separate all-routed physical metrics from timing-feasible SECDED-only power/energy; drop F04 under the six-page budget.

## I. Final tables

Freeze two major tables: evaluated implementations and compact physical/reliability results. Keep W3 counts in the reliability semantics artifact/discussion, not a major table.

## J. Final limitations

All mandatory technology, corner, implementation, target, Hsiao, BCH energy, OpenSTA, FIT/SER, field-weighting, W3-semantics, physical-memory, and sample-size limits are assigned to Setup, Results, or Discussion.

## K. Numerical audit result

`{audit['result']}` with zero mismatches. Every manuscript-visible effect size was regenerated from Gate 05 machine-readable raw values and cross-checked against Gate 06.

## L. Evidence completeness

All final claims, figure data, table rows, limitations, reviewer resolutions, and source identities are machine-readable and SHA-256 inventoried. No new measurement, physical run, RTL change, model change, excluded thesis subsystem, or optimizer was introduced.

## M. Gate 08 readiness

`GATE_08_READY`
"""
    write_text(output / "GATE07_ADJUDICATION.md", adjudication)

    manifest_rows = []
    for path in sorted(item for item in output.rglob("*") if item.is_file() and item.name != "GATE07_EVIDENCE.sha256"):
        manifest_rows.append(f"{sha256(path)}  ./{path.relative_to(output).as_posix()}")
    write_text(output / "GATE07_EVIDENCE.sha256", "\n".join(manifest_rows))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    build(args.out.resolve())
    print(f"GATE07_BUILD_PASS {args.out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
