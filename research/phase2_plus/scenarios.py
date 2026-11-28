"""Reproduce conditional carbon and selection on the two frozen cohorts."""

import argparse
from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
from itertools import product
from pathlib import Path
import shutil
import statistics

from evidence import DATE_SERVICE, Frozen, admitted_iscas, historical_date
from lifecycle import (
    JOULES_PER_KWH, SECONDS_PER_YEAR, Wafer, act_area_kg, act_cpa_kg, break_even_operations,
    deployment, embodied_kg, minimax_regret, normalized_mix, pareto_front, time_crossings,
    um2_to_mm2, wafer_area_mm2,
)
from run_campaign import PACKAGE, digest, read_json, write_json


SUST = PACKAGE / "sustainability"
DATE_MIX = {"CONCURRENT_NO_ERROR": 1.0}
TECHNOLOGY = "SKY130HD TT 1.8 V 25 C"
IDS = {
    "limit": "GREENS-PHASE2-PLUS-R1/C06",
    "carbon": "GREENS-PHASE2-PLUS-R1/C07",
    "selection": "GREENS-PHASE2-PLUS-R1/D03",
}


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        fields = list(dict.fromkeys(key for row in rows for key in row))
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_inputs():
    with (SUST / "sources.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    return {row["id"]: row for row in rows}, read_json(SUST / "scenario_assumptions.yaml")


def wafer_proxy(source, controls):
    return Wafer(float(source["converted_value"]), float(source["wafer_diameter_mm"]),
                 **{name: controls[name] for name in ("edge_mm", "scribe_mm", "die_yield", "aspect_ratio")})


def grid_value(sources, grid_id):
    return float(sources[grid_id]["converted_value"])


def argmin(cost):
    minimum = min(cost.values())
    return "|".join(sorted(name for name, value in cost.items() if value == minimum))


def preferences(values):
    return {"reference": sum(value > 0 for value in values),
            "candidate": sum(value < 0 for value in values),
            "ties": sum(value == 0 for value in values)}


def metadata(candidate, source_model, workload, unit, *, evidence_class="CONDITIONAL_CARBON_SCENARIO"):
    return {
        "experiment_id": IDS["carbon"], "evidence_class": evidence_class,
        "architecture_id": candidate.name, "service_contract": candidate.service.contract,
        "physical_identity": candidate.identity, "technology": TECHNOLOGY, "placement_seed": candidate.seed,
        "workload_identity": workload, "source_model_identity": source_model,
        "unit": unit, "eligibility": "CONDITIONAL", "result_status": "COMPLETED",
        "artifact_reference": candidate.artifact,
    }


@dataclass(frozen=True)
class Case:
    cohort: str
    pair: tuple
    model: str
    grid: str
    utilization: float
    years: int
    workload: str
    mix: dict
    wafer_id: str

    @property
    def label(self):
        return f"{self.cohort}.s{self.pair[0].seed}.{self.model}.{self.grid}.u{self.utilization:g}.y{self.years}.{self.workload}"


def cases(date, sram, assumptions):
    for pair, model, grid, utilization, years in product(
        date, assumptions["allocation_models"], assumptions["grid_ids"],
        assumptions["utilizations"], assumptions["lifetimes_years"],
    ):
        yield Case("DATE", pair, model, grid, utilization, years, "concurrent_clean", DATE_MIX, "tsmc8_2025")
    for pair, grid, utilization, (name, mix) in product(
        sram, assumptions["grid_ids"], assumptions["utilizations"], assumptions["sram_comparison"]["mixes"].items(),
    ):
        yield Case("ISCAS", pair, "fixed", grid, utilization, 5, name, mix, "tsmc8_2025")


def active_energy(candidate, mix):
    return sum(candidate.energy_j[operation] * weight for operation, weight in normalized_mix(mix).items())


def evaluate(case, sources, assumptions):
    reference, candidate = case.pair
    intensity = grid_value(sources, case.grid)
    wafer = wafer_proxy(sources[case.wafer_id], assumptions["wafer_model"])
    date = case.cohort == "DATE"
    model = case.model
    if date and not all(a.service.eligible(
            contract=DATE_SERVICE, capacity_words=0, max_latency=assumptions["date_comparison"]["required_latency_cycles"],
            min_rate=100e6, max_area=assumptions["date_comparison"]["max_area_um2"]) for a in case.pair):
        raise ValueError("DATE seed pair violates the declared service requirements")
    interval = deployment(case.years * SECONDS_PER_YEAR, case.utilization, reference.service.rate_hz, intensity, case.mix)
    seconds = interval.seconds
    scope = f"{case.wafer_id}|{case.grid}|{model}"
    costs = []
    acts = {}
    constraint_rows = []
    for a in case.pair:
        effective_area = um2_to_mm2(a.service.area_um2) / assumptions["effective_area_utilization"]
        parent = assumptions["parent_die_mm2"] if date else um2_to_mm2(a.die_um2)
        embodied = embodied_kg(wafer, model, parent, effective_area)
        idle = assumptions["date_comparison"]["assumed_equal_idle_w"] if date else a.idle_w
        operational = interval.carbon_kg(a.energy_j, idle)
        if embodied is None or operational is None:
            raise ValueError("Primary case is missing a required carbon operand")
        pre_yield_cpa = wafer.kg_per_wafer / wafer_area_mm2(wafer.diameter_mm, wafer.edge_mm) * 100
        act_area = {"fixed": parent, "allocated": effective_area, "marginal": parent + effective_area}[model]
        acts[a.name] = act_cpa_kg(act_area, pre_yield_cpa, wafer.die_yield) + operational
        costs.append(metadata(a, scope, case.workload, "kgCO2e") | {
            "scenario_id": case.label, "cohort": case.cohort, "allocation": model, "grid": case.grid,
            "lifetime_years": case.years, "utilization": case.utilization, "embodied_kg": embodied,
            "operational_kg": operational, "lifecycle_kg": embodied + operational,
            "assumed_idle_w": idle if date else None, "historical_idle_w": idle if not date else None,
            "act_reduced_lifecycle_kg": acts[a.name], "useful_operations": sum(interval.operation_counts.values()),
            "active_energy_j_per_useful_operation": active_energy(a, case.mix),
        })
        constraint_rows.append((a.service.area_um2, 10 - a.service.setup_ns, active_energy(a, case.mix)))
    left, right = costs
    # Subtract like components first so the fixed shared manufacturing term
    # cannot cause cancellation at a near-zero difference.
    delta_emb = right["embodied_kg"] - left["embodied_kg"]
    delta_op = right["operational_kg"] - left["operational_kg"]
    delta = delta_emb + delta_op
    payback = time_crossings(delta_emb, [(seconds, delta_op)])
    constant = break_even_operations(
        delta_emb, left["active_energy_j_per_useful_operation"] - right["active_energy_j_per_useful_operation"], intensity,
    ) if date else None
    choice = candidate.name if delta < 0 else reference.name if delta > 0 else "|".join(sorted((candidate.name, reference.name)))
    selection = {
        "B0_minimum_area": argmin({a.name: a.service.area_um2 for a in case.pair}),
        "B1_single_operation_energy": argmin({a.name: a.energy_j[next(iter(DATE_MIX)) if date else "READ_CLEAN"]
                                              for a in case.pair}),
        "B2_setup_path_estimate": argmin({a.name: 10 - a.service.setup_ns for a in case.pair}),
        "B3_PPA_front": "|".join(pareto_front({a.name: values for a, values in zip(case.pair, constraint_rows)})),
        "B4_GREEN_score": None,
        "B5_ACT_area_method": argmin(acts),
        "B6_workload_operational": argmin({a.name: r["operational_kg"] for a, r in zip(case.pair, costs)}),
        "conditional_lifecycle_choice": choice,
    }
    return costs, metadata(candidate, scope, case.workload, "kgCO2e") | {
        "experiment_id": IDS["limit"], "scenario_id": case.label, "cohort": case.cohort,
        "reference_architecture": reference.name, "allocation": model, "grid": case.grid,
        "lifetime_years": case.years, "utilization": case.utilization, "delta_embodied_kg": delta_emb,
        "delta_operational_kg": delta_op, "delta_scoped_lifecycle_kg": delta,
        "in_lifetime": "|".join(f"{point / SECONDS_PER_YEAR:.12g}" for point in payback.crossings),
        "time_status": payback.status, "constant_break_even_operations": constant.crossings[0]
        if constant and constant.crossings else None, "constant_status": constant.status if constant else None,
        **selection,
    }


def descriptive(values):
    return {"n": len(values), "mean": statistics.mean(values), "median": statistics.median(values),
            "sample_sd": statistics.stdev(values) if len(values) > 1 else None, "min": min(values), "max": max(values),
            "confidence_interval": None}


def summarize_groups(deltas, costs):
    by_group = defaultdict(list)
    by_scenario = defaultdict(dict)
    for row in costs:
        by_scenario[row["scenario_id"]][row["architecture_id"]] = row["lifecycle_kg"]
    for row in deltas:
        by_group[row["cohort"], row["allocation"]].append(row)
    reversals, regrets = [], []
    for (cohort, allocation), rows in sorted(by_group.items()):
        matrix = [by_scenario[row["scenario_id"]] for row in rows]
        static, worst, per_case = minimax_regret(matrix)
        robust_front = pareto_front({name: tuple(cost[name] for cost in matrix) for name in worst})
        for name in sorted(worst):
            regrets.append({
                "experiment_id": IDS["selection"], "evidence_class": "CONDITIONAL_CARBON_SCENARIO",
                "architecture_id": name, "service_contract": rows[0]["service_contract"],
                "physical_identity": rows[0]["cohort"] + "-matched-pairs", "technology": TECHNOLOGY,
                "placement_seed": None, "workload_identity": "enumerated mixes",
                "source_model_identity": "scenario_assumptions.yaml", "unit": "kgCO2e", "eligibility": "CONDITIONAL",
                "result_status": "COMPLETED", "artifact_reference": "lifecycle_carbon.csv",
                "cohort": cohort, "allocation": allocation, "scenario_cells": len(rows),
                "minimax_winner": name in static, "robust_pareto_member": name in robust_front,
                "worst_regret_kg": worst[name], "mean_regret_kg": statistics.mean(per_case[name]),
            })
        for baseline in ("B0_minimum_area", "B1_single_operation_energy", "B2_setup_path_estimate",
                         "B5_ACT_area_method", "B6_workload_operational"):
            changes = [row for row in rows if row[baseline] != row["conditional_lifecycle_choice"]
                       and "|" not in row[baseline] and "|" not in row["conditional_lifecycle_choice"]]
            regret = [min(matrix[i][name] for name in row[baseline].split("|")) - min(matrix[i].values())
                      for i, row in enumerate(rows)]
            reversals.append({
                "experiment_id": IDS["selection"], "evidence_class": "CONDITIONAL_CARBON_SCENARIO",
                "architecture_id": rows[0]["reference_architecture"] + "|" + rows[0]["architecture_id"],
                "service_contract": rows[0]["service_contract"], "physical_identity": cohort + "-matched-pairs",
                "technology": TECHNOLOGY, "placement_seed": None, "workload_identity": "enumerated mixes",
                "source_model_identity": "scenario_assumptions.yaml", "unit": "scenario count; kgCO2e for regret",
                "eligibility": "CONDITIONAL", "result_status": "COMPLETED", "artifact_reference": "carbon_break_even.csv",
                "cohort": cohort, "allocation": allocation, "baseline": baseline, "scenario_cells": len(rows),
                "ranking_reversals": len(changes), "fraction_of_grid": len(changes) / len(rows),
                "worst_baseline_regret_kg": max(regret),
            })
    return reversals, regrets


def sram_boundaries(sram):
    result = []
    for left, right in sram:
        d_read = right.energy_j["READ_CLEAN"] - left.energy_j["READ_CLEAN"]
        d_write = right.energy_j["WRITE_CLEAN"] - left.energy_j["WRITE_CLEAN"]
        d_idle = right.idle_w - left.idle_w
        d_active_w = d_read * left.service.rate_hz
        for utilization in (0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 1):
            slope = utilization * (d_read - d_write) * left.service.rate_hz
            intercept = utilization * d_write * left.service.rate_hz + (1 - utilization) * d_idle
            crossing = -intercept / slope if slope else None
            idle_crossing = -d_idle / (d_active_w - d_idle) if d_active_w != d_idle else None
            result.append(metadata(right, "linear E5 active mix and disjoint idle", "clean_read_write", "fraction") | {
                "utilization": utilization, "clean_read_fraction_where_equal": crossing
                if crossing is not None and 0 <= crossing <= 1 else None,
                "pure_read_utilization_where_equal": idle_crossing
                if idle_crossing is not None and 0 <= idle_crossing <= 1 else None,
                "delta_idle_w": d_idle, "delta_clean_read_j": d_read, "delta_clean_write_j": d_write,
                "delta_all_read_w_at_utilization": intercept + slope,
                "delta_all_write_w_at_utilization": intercept,
                "whole_sram_lifecycle_winner": None,
            })
    return result


def sensitivities(date, sources, assumptions):
    model_controls = assumptions["wafer_model"]
    integration = {
        "id": "reference", "parent_die_mm2": assumptions["parent_die_mm2"], **model_controls,
        "effective_area_utilization": assumptions["effective_area_utilization"],
    }
    mixed = assumptions["sensitivity"]
    layouts = [integration] + [integration | variant for variant in mixed["joint_manufacturing_points"]]
    rows = []
    for (left, right), manufacturing, layout, mode in product(
        date, assumptions["wafer_ids"], layouts, ("allocated", "marginal"),
    ):
        wafer = wafer_proxy(sources[manufacturing], layout)
        die = layout["parent_die_mm2"]
        effective = [um2_to_mm2(a.service.area_um2) / layout["effective_area_utilization"] for a in (left, right)]
        ref, candidate = (embodied_kg(wafer, mode, die, area) for area in effective)
        emb_delta = candidate - ref
        saved_j = active_energy(left, DATE_MIX) - active_energy(right, DATE_MIX)
        for idle_delta in mixed["hypothetical_idle_delta_w"]:
            # For a delta, the shared idle baseline cancels. At 1% utilization
            # an unknown 0.1 mW difference can dominate either active estimate.
            differences = []
            for grid in mixed["hypothetical_time_grid"]:
                change_j = SECONDS_PER_YEAR * (0.99 * idle_delta - 0.01 * left.service.rate_hz * saved_j)
                differences.append((SECONDS_PER_YEAR, change_j * grid_value(sources, grid) / JOULES_PER_KWH))
            roots = time_crossings(emb_delta, differences)
            rows.append(metadata(right, manufacturing, "DATE-1pct-two-interval", "kgCO2e",
                                 evidence_class="HYPOTHETICAL_SENSITIVITY") | {
                "layout": layout["id"], "allocation": mode, "idle_delta_w": idle_delta,
                "delta_embodied_kg": emb_delta,
                "delta_scoped_lifecycle_kg": emb_delta + sum(value for _, value in differences),
                "carbon_break_even_years": "|".join(f"{point / SECONDS_PER_YEAR:.12g}" for point in roots.crossings),
                "time_status": roots.status,
            })
    return rows


def generate(out, *, summaries_only=False):
    out.mkdir(parents=True, exist_ok=True)
    sources, assumptions = read_inputs()
    frozen = Frozen()
    date = historical_date(frozen)
    sram, operations, exclusions = admitted_iscas(frozen)
    costs, deltas = [], []
    for case in cases(date, sram, assumptions):
        operands, difference = evaluate(case, sources, assumptions)
        costs.extend(operands)
        deltas.append(difference)
    reversals, regrets = summarize_groups(deltas, costs)
    boundaries = sram_boundaries(sram)
    stresses = sensitivities(date, sources, assumptions)
    date_points = [row for row in deltas if row["cohort"] == "DATE"]
    seed_baseline = [row for row in date_points if row["grid"] == "grid_mid" and row["lifetime_years"] == 1
                     and row["utilization"] == 0.01]
    sram_deltas = {operation: descriptive([
        next(r["energy_j"] for r in operations if r["operation"] == operation and
             r["placement_seed"] == left.seed and r["architecture_id"] == right.name)
        - next(r["energy_j"] for r in operations if r["operation"] == operation and
               r["placement_seed"] == left.seed and r["architecture_id"] == left.name)
        for left, right in sram]) for operation in dict.fromkeys(r["operation"] for r in operations)}
    bare = act_area_kg(100, 0.4, 0.5, 0.15, 0.02, 0.8)
    materiality = {}
    for cohort in ("DATE", "ISCAS"):
        # Compare the scoped totals at a declared common accounting boundary.
        selected = [r for r in deltas if r["cohort"] == cohort and
                    r["allocation"] == ("allocated" if cohort == "DATE" else "fixed")]
        references = {r["scenario_id"]: r["lifecycle_kg"] for r in costs
                      if r["cohort"] == cohort and r["architecture_id"] in {"secded_comb", "SECDED"}}
        materiality[cohort] = {str(threshold): sum(
            abs(row["delta_scoped_lifecycle_kg"]) / references[row["scenario_id"]] >= threshold for row in selected
        ) for threshold in assumptions["sensitivity"]["hypothetical_relative_delta_thresholds"]}
    summary = {
        "date_paired_energy_saving_j": descriptive([active_energy(a, DATE_MIX) - active_energy(b, DATE_MIX)
                                                     for a, b in date]),
        "date_allocation_counts": {
            model: preferences([r["delta_scoped_lifecycle_kg"] for r in date_points if r["allocation"] == model])
            for model in assumptions["allocation_models"]
        },
        "date_one_year_one_percent_mid_grid": {
            model: descriptive([r["delta_scoped_lifecycle_kg"] for r in seed_baseline if r["allocation"] == model])
            for model in assumptions["allocation_models"]
        },
        "date_constant_payback_operations_mid_grid": {
            model: descriptive([r["constant_break_even_operations"] for r in seed_baseline if r["allocation"] == model])
            for model in ("allocated", "marginal")
        },
        "date_reference_utilization_break_even_years_mid_grid": {
            model: descriptive([r["constant_break_even_operations"] / (0.01 * 100e6 * SECONDS_PER_YEAR)
                                for r in seed_baseline if r["allocation"] == model])
            for model in ("allocated", "marginal")
        },
        "sram_paired_operation_delta_j": sram_deltas,
        "sram_workload_preferences": {
            workload: preferences([r["delta_scoped_lifecycle_kg"] for r in deltas if r["cohort"] == "ISCAS"
                                    and r["workload_identity"] == workload])
            for workload in assumptions["sram_comparison"]["mixes"]
        },
        "date_primary_scenario_cells": len(date_points),
        "sram_primary_scenario_cells": sum(row["cohort"] == "ISCAS" for row in deltas),
        "sram_historical_energy_records": len(operations), "sram_excluded_runs": exclusions,
        "sram_whole_memory_lifecycle_preference": None,
        "sensitivity_time_positions": len(stresses),
        "sensitivity_statuses": dict(Counter(r["time_status"] for r in stresses)),
        "materiality_counts": materiality,
        "act_eq_4_5_analytical_check_kg": {"implemented": bare, "manual": 0.4625,
                                           "source": "ACT Eq. 4/5 with explicit hypothetical operands"},
        "sky130_matched_inventory": None,
    }
    write_json(out / "scenario_summary.json", summary)
    tables = {
        "operation_conditioned_energy": operations,
        "architecture_selection": [{key: value for key, value in r.items()
                                     if key.startswith("B") or key in {"scenario_id", "placement_seed",
                                         "architecture_id", "physical_identity", "service_contract", "cohort",
                                         "workload_identity", "source_model_identity", "conditional_lifecycle_choice",
                                         "artifact_reference", "evidence_class", "eligibility", "result_status",
                                         "experiment_id", "technology", "unit"}} for r in deltas],
        "carbon_regret": regrets, "ranking_reversal": reversals, "robustness_analysis": boundaries,
        "uncertainty_analysis": stresses,
    }
    if not summaries_only:
        tables |= {"lifecycle_carbon": costs, "carbon_break_even": deltas,
                   "embodied_carbon": [{k: v for k, v in r.items() if k not in
                                        {"operational_kg", "lifecycle_kg", "act_reduced_lifecycle_kg"}} for r in costs],
                   "operational_carbon": [{k: v for k, v in r.items() if k not in
                                           {"embodied_kg", "lifecycle_kg", "act_reduced_lifecycle_kg"}} for r in costs]}
    # The package retains concise summaries. The full scenario-level grid is
    # reproducible in the external run directory with the default invocation.
    if summaries_only:
        tables.pop("architecture_selection")
    for title, data in tables.items():
        write_csv(out / f"{title}.csv", data)
    write_csv(out / "manufacturing_scenarios.csv", [row for key, row in sources.items() if key.startswith("tsmc8_")])
    write_csv(out / "operational_grid_scenarios.csv", [sources[key] for key in assumptions["grid_ids"]])
    shutil.copyfile(SUST / "sources.csv", out / "sustainability_source_registry.csv")
    write_json(out / "carbon_input_manifest.json", {
        "frozen_operands_sha256": frozen.hashes,
        "sustainability_inputs_sha256": {path.name: digest(path) for path in sorted(SUST.iterdir()) if path.is_file()},
        "outputs_sha256": {path.name: digest(path) for path in sorted(out.iterdir())
                           if path.is_file() and path.name in {*(title + ".csv" for title in tables),
                               "scenario_summary.json", "manufacturing_scenarios.csv",
                               "operational_grid_scenarios.csv", "sustainability_source_registry.csv"}},
    })
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--summaries-only", action="store_true")
    args = parser.parse_args()
    outcome = generate(args.output, summaries_only=args.summaries_only)
    print(f"Reproduced {outcome['date_primary_scenario_cells']} DATE and {outcome['sram_primary_scenario_cells']} ISCAS scenario cells")
