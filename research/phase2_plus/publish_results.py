"""Build compact paper tables from the hash-verified external campaign records."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil

from evidence import DATE_SERVICE
from lifecycle import JOULES_PER_KWH, SECONDS_PER_YEAR, embodied_kg, um2_to_mm2
from physical import PHYSICAL, metrics
from routed_mechanisms import activity_proxy, xor_pair
from run_campaign import DEFAULT_ROOT, PACKAGE, digest, read_json, write_json
from scenarios import grid_value, read_inputs, wafer_proxy, write_csv


def verified(root, state, gate, relative):
    for attempt in reversed(state["jobs"][gate]["attempts"]):
        expected = attempt.get("artifact_sha256", {}).get(relative)
        if expected:
            path = root / attempt["directory"] / relative
            if digest(path) != expected:
                raise ValueError(f"Campaign bytes changed: {gate}/{relative}")
            return path
    raise FileNotFoundError(f"Unverified campaign artifact: {gate}/{relative}")


def provenance(experiment, arch, identity, evidence_class, unit, reference,
               *, model=None, workload=None, eligibility="ADMITTED", status="COMPLETED"):
    return {
        "experiment_id": experiment, "evidence_class": evidence_class, "architecture_id": arch,
        "service_contract": DATE_SERVICE if arch else None, "physical_identity": identity,
        "technology": "SKY130HD TT 1.8 V 25 C" if identity else None, "placement_seed": 17 if identity else None,
        "workload_identity": workload, "source_model_identity": model, "unit": unit,
        "eligibility": eligibility, "result_status": status, "artifact_reference": reference,
    }


def execute(root, output):
    state = read_json(root / "campaign.json")
    output.mkdir(parents=True, exist_ok=True)
    names = ("operation_conditioned_energy.csv", "carbon_regret.csv", "ranking_reversal.csv",
             "robustness_analysis.csv", "uncertainty_analysis.csv", "scenario_summary.json",
             "manufacturing_scenarios.csv", "operational_grid_scenarios.csv", "sustainability_source_registry.csv",
             "carbon_input_manifest.json")
    for name in names:
        shutil.copyfile(verified(root, state, "C01-C07", name), output / name)
    for name in ("embodied_carbon", "operational_carbon", "lifecycle_carbon", "carbon_break_even",
                 "architecture_selection"):
        path = verified(root, state, "C01-C07", name + ".csv")
        with path.open(encoding="utf-8", newline="") as stream:
            rows = [row for row in csv.DictReader(stream)
                    if ".grid_mid.u0.01.y1." in row["scenario_id"] or ".grid_mid.u0.25.y5." in row["scenario_id"]]
        write_csv(output / (name + ".csv"), rows)

    physical_config = read_json(PHYSICAL / "contract.json")
    attempted = verified(root, state, "A02", "physical-observations.json").parent
    trace = read_json(verified(root, state, "A02", "trace/manifest.json"))
    simulator = read_json(verified(root, state, "B01-COMB", "combined-results.json"))
    extended = read_json(verified(
        root, state, "B01-EXT", "probe/research/phase2/raw/p2plus_icarus13_extended/results.json",
    ))
    v13_rows = {r["label"]: r for r in extended["results"]}
    upstream = read_json(verified(root, state, "B01-EXT", "upstream-gold-controls.json"))
    inventory = []
    for row in read_json(verified(root, state, "A01", "artifact-inventory.json")):
        inventory.append(provenance("A01", None, None, "UNAVAILABLE", None, "A01/artifact-inventory.json",
                                    eligibility="MISSING", status=row["status"]) | row)
    physical_rows, all_sdf, cell_groups = [], [], []
    examples = {}
    raw_ab = read_json(verified(root, state, "B02-ZERO", "method-ab.json"))
    estimator_rows = []
    for arch, top in physical_config["physical_profiles"].items():
        seed = physical_config["placement_and_route_seed"]
        directory = attempted / arch
        verified(root, state, "A02", f"{arch}/flow.log")
        status = metrics(directory, arch, top, seed, 0, None, trace)
        identity = status["physical_identity"]
        logdir = f"{arch}/logs/sky130hd/{top}/seed{seed}"
        routed = read_json(verified(root, state, "A02", f"{logdir}/5_2_route.json"))
        finish = read_json(verified(root, state, "A02", f"{logdir}/6_report.json"))
        verdict = provenance("A02", arch, identity, "NEW_PHYSICAL_TOOL_ESTIMATE", "ns; um²; um",
                             f"A02/{logdir}/6_report.json", model=physical_config["container"])
        physical_rows.append(verdict | {
            "route_complete": status["route_artifacts_present"], "setup_wns_ns": status["setup_worst_slack_ns"],
            "hold_wns_ns": status["hold_worst_slack_ns"],
            "hold_violations": finish["finish__timing__drv__hold_violation_count"],
            "setup_violations": finish["finish__timing__drv__setup_violation_count"],
            "stdcell_area_um2": finish["finish__design__instance__area__stdcell"],
            "die_area_um2": finish["finish__design__die__area"],
            "core_area_um2": finish["finish__design__core__area"],
            "detail_route_drc_markers": routed["detailedroute__route__drc_errors"],
            "detail_route_wirelength_um": routed["detailedroute__route__wirelength"],
            "latency_cycles": 1 if arch.endswith("comb") else 3, "initiation_interval_cycles": 1,
        })
        for name, checksum in status["artifact_sha256"].items():
            base = directory if name == "6_final.sdf" or name.endswith(".rpt") else directory / (
                f"results/sky130hd/{top}/seed{seed}"
            )
            inventory.append(verdict | {
                "artifact": name, "sha256": checksum, "status": "RECONSTRUCTED",
                "artifact_reference": (base / name).relative_to(root).as_posix(),
            })
        sdf_path = verified(root, state, "A02", f"{arch}/6_final.sdf")
        sdf = sdf_path.read_text(encoding="ascii")
        for label in ("IOPATH", "INTERCONNECT", "COND", "TIMINGCHECK", "SETUP", "HOLD", "WIDTH"):
            all_sdf.append(verdict | {
                "construct": label, "required_count": len(re.findall(rf"\({label}\b", sdf)),
                "measured_annotated_count": None, "result_status": "UNAVAILABLE", "eligibility": "BLOCKED",
                "artifact_reference": f"A02/{arch}/6_final.sdf",
            })
        ab = {r["method"]: r for r in raw_ab if r["architecture_id"] == arch}
        netdir = f"{arch}/results/sky130hd/{top}/seed{seed}"
        verilog = verified(root, state, "A02", f"{netdir}/6_final.v")
        spef = verified(root, state, "A02", f"{netdir}/6_final.spef")
        window = verified(root, state, "B02-ZERO", f"{arch}/window.vcd")
        examples[arch] = {"netlist_sha256": digest(verilog), "connected_xor_cells": xor_pair(verilog)}
        cell_groups.append(verdict | {
            "experiment_id": "B04", "mechanism": "Ground-capacitance weighted binary activity",
            "unit": "pJ / completed pair", "workload_identity": "gate04-clean-prefix-1000",
            "artifact_reference": f"A02/{netdir}/6_final.spef + B02-ZERO/{arch}/window.vcd",
            "interpretation": "ZERO_DELAY_COMPONENT_PROXY",
            **activity_proxy(spef, window, ab["B"]["window_ps"], ab["B"]["scoreboard_completed"], physical_config["voltage_v"]),
        })
        for label, r in ab.items():
            estimator_rows.append(verdict | {
                "experiment_id": "B02-ZERO", "method": label, "eligibility": r["eligibility"],
                "unit": "pJ / completed simultaneous encode and decode pair",
                "energy_pj": r["energy_j_per_completed_pair"] * 1e12,
                "internal_w": r["power_w"]["internal"], "switching_w": r["power_w"]["switching"],
                "leakage_w": r["power_w"]["leakage"], "total_w": r["power_w"]["total"],
                "workload_identity": "gate04-clean-prefix-1000", "window_ps": r["window_ps"],
                "scoreboard_completed": r["scoreboard_completed"],
                "direct_vcd_count": r["before"]["vcd"], "unannotated_before_propagation": r["before"]["unannotated"],
                "direct_vcd_pin_fraction": r["direct_vcd_pin_fraction"],
                "unknown_bit_time_ps": r["unknown_bit_time_ps"], "waveform_sha256": r["waveform_sha256"],
                "artifact_reference": f"B02-ZERO/{arch}/method-{label}/power.rpt",
            })
        estimator_rows.append(verdict | {
            "experiment_id": "B03", "evidence_class": "UNAVAILABLE", "method": "C", "eligibility": "BLOCKED",
            "unit": "pJ / completed simultaneous encode and decode pair", "energy_pj": None,
            "workload_identity": "gate04-clean-prefix-1000", "result_status": "UNAVAILABLE",
            "artifact_reference": "reports/B02_RESTRICTED_PROTOCOL.md",
        })
        power_path = verified(root, state, "B02-ZERO", f"{arch}/method-B/power.rpt")
        for group, energy in re.findall(r"^(Sequential|Combinational|Clock)\s+"
                                        r"[\deE.+-]+\s+[\deE.+-]+\s+[\deE.+-]+\s+([\deE.+-]+)",
                                        power_path.read_text(), flags=re.MULTILINE):
            cell_groups.append(verdict | {"experiment_id": "B04", "mechanism": group, "total_power_w": float(energy),
                                          "unit": "W", "workload_identity": "gate04-clean-prefix-1000",
                                          "artifact_reference": f"B02-ZERO/{arch}/method-B/power.rpt",
                                          "interpretation": "TOOL_ACCOUNTING_PARTITION"})
        cell_groups.append(verdict | {"experiment_id": "B04", "mechanism": "Delay-induced ECC switching",
                                      "evidence_class": "UNAVAILABLE", "total_power_w": None, "unit": "W",
                                      "eligibility": "BLOCKED", "result_status": "UNAVAILABLE",
                                      "interpretation": "INCONCLUSIVE"})
    capabilities = []
    for label, result in [
        ("Upstream interconnect gold cases", f"{sum(upstream.values())}/{len(upstream)} pass"),
        ("SKY130 two-cell IOPATH min/typ/max", "PASS" if extended["synthetic_iopath_pass"] else "FAIL"),
        ("SKY130 two-cell interconnect flags", "PASS" if v13_rows["interconnect_flag_probe"]["y_binary_transitions"] == 4 else "FAIL"),
        ("Short-pulse negative control", "PASS" if v13_rows["narrow_pulse"]["y_binary_transitions"] == 0 else "FAIL"),
        ("Wrong hierarchy negative control", "PASS" if v13_rows["bad_hierarchy"]["y_min_pulse_ps"] == 2000 else "FAIL"),
        ("Dynamic setup/hold/width and notifier", "FAIL"),
        ("Conditional and negative timing constructs", "UNAVAILABLE"),
    ]:
        capabilities.append(provenance("B01-EXT", None, None, "SYNTHETIC_QUALIFICATION_RESULT", "qualification",
                                       "B01-EXT/upstream-gold-controls.json", model="Icarus-v13.0") |
                            {"capability": label, "result": result})
    for result in simulator:
        capabilities.append(provenance("B01-COMB", None, None, "SYNTHETIC_QUALIFICATION_RESULT", "ps",
                                       "B01-COMB/combined-results.json", model="Icarus-v13.0") |
                            {"capability": "Combined asymmetric delay and capture", **result})
    for name, rows in (
        ("physical_artifact_inventory", inventory), ("physical_characterization", physical_rows),
        ("sdf_annotation_coverage", all_sdf), ("simulator_capabilities", capabilities),
        ("mechanism_evidence", cell_groups), ("estimator_comparison", estimator_rows),
    ):
        write_csv(output / (name + ".csv"), rows)
    write_json(output / "routed_xor_example.json", examples)

    workloads = read_json(verified(root, state, "B05-ZERO", "workload-results.json"))
    inputs = {r["architecture_id"]: r for r in physical_rows}
    work_rows = [provenance("B05-ZERO", row["architecture_id"], inputs[row["architecture_id"]]["physical_identity"],
                           "NEW_PHYSICAL_TOOL_ESTIMATE",
                           "pJ / completed simultaneous encode and decode pair",
                           f"B05-ZERO/{row['architecture_id']}/{row['workload']}/power.rpt",
                           model="OpenSTA internal zero-delay VCD", workload=row["workload"],
                           eligibility=row["status"], status="COMPLETED" if row["pJ"] else row["status"]) | {
        "energy_pj": row["pJ"], "scoreboard_completed": row.get("completed"),
        "payload_regime": row["payload_regime"], "payload_mean_hamming_distance": row["payload_mean_hamming_distance"],
        "injection_counts": json.dumps(row["injection_counts"], sort_keys=True),
        "software_payload_mismatches": row["software_payload_mismatches"],
        "logic_guarantee": "outside SECDED" if row["workload"] == "adjacent_multi" else "SECDED",
        "import_fraction": row["annotation"]["direct_vcd_pin_fraction"] if row.get("annotation") else None,
        "raw_activity_sha256": row.get("full_waveform_sha256"),
    } for row in workloads]
    write_csv(output / "reconstructed_workload_energy.csv", work_rows)
    shutil.copyfile(verified(root, state, "B05-ZERO", "mixed-validation.json"), output / "mixed_workload_validation.json")
    storage_rows = [{"experiment_id": state["campaign_id"], **sample} for sample in state["storage_history"]]
    write_csv(output / "storage_history.csv", storage_rows)
    write_json(output / "campaign_registry.json", {
        key: state[key] for key in ("campaign_id", "started_utc", "deadline_utc", "starting_commit", "branch",
                                   "contract_sha256", "current_job")
    } | {"jobs": {
        gate: {
            "status": value["status"], "reason": value.get("reason"),
            "attempts": [
                {key: attempt.get(key) for key in ("directory", "started_utc", "finished_utc", "returncode", "commit")}
                | {"artifact_count": len(attempt.get("artifact_sha256", {})),
                   "receipt_sha256": hashlib.sha256(json.dumps(
                       attempt.get("artifact_sha256", {}), sort_keys=True
                   ).encode("ascii")).hexdigest()}
                for attempt in value["attempts"]
            ],
        }
        for gate, value in state["jobs"].items()
    }})
    for table, reason in (
        ("optimization_candidates", "Hardware generation deferred pending a qualified delay-aware and independent optimization opportunity"),
        ("held_out_validation", "No optimized candidate admitted for held-out execution"),
    ):
        write_csv(output / (table + ".csv"), [provenance(
            "D05" if table == "optimization_candidates" else "D06", None, None,
            "UNAVAILABLE", None, "reports/B02_RESTRICTED_PROTOCOL.md", eligibility="BLOCKED", status="BLOCKED"
        ) | {"reason": reason}])
    reconstructed_carbon(physical_rows, estimator_rows, output)


def reconstructed_carbon(physical, estimators, output):
    """Evaluate the new pair independently at the preregistered nominal point."""
    sources, assumptions = read_inputs()
    wafer = wafer_proxy(sources["tsmc8_2025"], assumptions["wafer_model"])
    intensity = grid_value(sources, "grid_mid")
    energy = {r["architecture_id"]: r["energy_pj"] for r in estimators if r["method"] == "B" and r["eligibility"] == "ADMITTED"}
    rows = []
    for physical_row in physical:
        arch = physical_row["architecture_id"]
        for mode in assumptions["allocation_models"]:
            area = um2_to_mm2(physical_row["stdcell_area_um2"]) / assumptions["effective_area_utilization"]
            embodied = embodied_kg(wafer, mode, assumptions["parent_die_mm2"], area)
            operational = energy[arch] * 1e-12 * (0.01 * 100e6 * SECONDS_PER_YEAR) * intensity / JOULES_PER_KWH
            rows.append(provenance("C09", arch, physical_row["physical_identity"], "CONDITIONAL_CARBON_SCENARIO",
                                   "kgCO2e", "estimator_comparison.csv", model="tsmc8_2025|grid_mid|" + mode,
                                   workload="seed17-zero-delay-clean; 1 year; 1% util; equal zero incremental idle") |
                        {"allocation": mode, "embodied_kg": embodied, "operational_kg": operational,
                         "scoped_lifecycle_kg": embodied + operational, "idle_difference_measured": None})
    write_csv(output / "reconstructed_carbon.csv", rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=PACKAGE / "processed")
    args = parser.parse_args()
    execute(args.root, args.output)
