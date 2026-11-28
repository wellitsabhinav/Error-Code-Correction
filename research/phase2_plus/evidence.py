"""Select and verify the frozen operand cohorts without hydrating waveforms."""

import csv
from dataclasses import dataclass
import hashlib
import json
import math

from campaign_jobs import git_blob
from lifecycle import Service, pj_to_j


ISCAS = "campaigns/iscas_sustainability_extension/green_v3_3_activity_complete_e5"
REFERENCE = "experiments/iscas/generated"
DATE_SERVICE = "STANDALONE_SECDED_72_64_W1_CORRECT_W2_DETECT"
SRAM_SERVICE = "SRAM22_256x72_SECDED_W1_CORRECT_W2_DETECT"
DATE_WORKLOAD = "DATE-breadth-B-100000-no-error-concurrent-encode-decode"
DATE_ARCH = ("secded_comb", "secded_pipe")
SRAM_ARCH = ("SECDED", "HSIAO_SECDED")
SEEDS = (11, 13, 17, 19, 23)
QUALIFIED = "E5_LOGIC_ACTIVITY_QUALIFIED_MACRO_ENERGY_INCOMPLETE"
OPERATIONS = ("IDLE", "WRITE_CLEAN", "READ_CLEAN", "READ_SINGLE_BIT_ERROR_CORRECT",
              "READ_DOUBLE_BIT_ERROR_DETECT")
PVT = {"corner": "tt_025C_1v80", "platform": "sky130hd", "temperature_c": 25, "voltage_v": 1.8}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


class Frozen:
    def __init__(self):
        self.hashes = {}

    def blob(self, path, expected=None):
        raw = git_blob(path)
        observed = sha256(raw)
        require(expected is None or observed == expected, f"Frozen content hash differs: {path}")
        self.hashes[path] = observed
        return raw

    def json(self, path, expected=None):
        return json.loads(self.blob(path, expected))

    def csv(self, path, expected=None):
        return list(csv.DictReader(self.blob(path, expected).decode("utf-8-sig").splitlines()))


@dataclass(frozen=True)
class Candidate:
    identity: str
    name: str
    seed: int
    service: Service
    energy_j: dict[str, float]
    idle_w: float | None
    artifact: str
    routed_netlist_sha256: str
    workload: str
    die_um2: float | None = None
    macro_um2: float | None = None


def historical_date(frozen):
    physical_path = "docs/date2027/revision2/results/REV2_RUN_RESULTS.csv"
    energy_path = "research/phase2/processed/historical_power_reanalysis.csv"
    physical = {(r["architecture"], int(r["seed"])): r for r in frozen.csv(physical_path)}
    power = {(r["architecture"], int(r["seed"])): r for r in frozen.csv(energy_path)}
    original_power = "campaigns/date_2027_breadth_remediation/analysis/B_power_components_per_seed.csv"
    original = {(r["architecture"], int(r["seed"])): r for r in frozen.csv(original_power)}
    pairs = []
    for seed in SEEDS:
        pair = []
        for arch in DATE_ARCH:
            row, e, producer = physical[arch, seed], power[arch, seed], original[arch, seed]
            require(e["source"] == original_power and e["source_sha256"] == frozen.hashes[original_power],
                    "DATE source identity differs")
            require(producer["run_id"] == row["run_id"]
                    and e["source_power_report_sha256"] == producer["power_report_sha256"],
                    "DATE physical/activity identity differs")
            require(math.isclose(float(e["energy_per_op_pj"]),
                                 float(row["no_error_energy_pj_per_operation_estimate"]), rel_tol=1e-12),
                    "DATE energy and matched physical row differ")
            service = Service(DATE_SERVICE, 0, int(row["latency_cycles"]),
                              100e6 / int(row["initiation_interval_cycles"]),
                              float(row["standard_cell_instance_area_um2"]), row["routing_complete"] == "True",
                              float(row["signed_worst_setup_slack_ns"]), float(row["worst_hold_slack_ns"]),
                              int(row["hold_violation_count"]))
            pair.append(Candidate(f"DATE-rev2/{row['run_id']}", arch, seed, service,
                                  {"CONCURRENT_NO_ERROR": pj_to_j(float(e["energy_per_op_pj"]))},
                                  None, original_power, producer["final_netlist_sha256"], DATE_WORKLOAD))
        pairs.append(tuple(pair))
    return pairs


def sealed_iscas(frozen):
    path = f"{ISCAS}/hashes/CAMPAIGN_ARTIFACTS.sha256"
    pinned = frozen.json(f"{REFERENCE}/integrity/source_manifest.json")["frozen_inputs"]
    lines = frozen.blob(path, pinned[path]).decode("ascii").splitlines()
    seal = {relative: digest for digest, relative in (line.split(maxsplit=1) for line in lines)}
    require(len(lines) == len(seal) == 1697, "ISCAS seal identity or population differs")

    def read(relative, expected=None):
        key = seal[relative]
        require(expected is None or expected == key, "ISCAS manifest and seal hash differ")
        return frozen.json(f"{ISCAS}/{relative}", key)

    manifest = read("RUN_MANIFEST.json", pinned[f"{ISCAS}/RUN_MANIFEST.json"])
    parent = manifest["inherited_physical_population"]
    frozen.json(parent["source"], parent["source_sha256"])
    return read, manifest


def admitted_iscas(frozen):
    read, manifest = sealed_iscas(frozen)
    runs = {(r["physical_seed"], r["architecture_id"]): r for r in manifest["canonical_fresh_runs"]}
    reference = {(int(r["seed"]), r["operation"]): r for r in frozen.csv(f"{REFERENCE}/primary_operation_pairs.csv")}
    manifest_records = {r["record_id"]: r for r in manifest["new_activity_power_records"]}
    pairs, observations, exclusions = [], [], []
    for seed in SEEDS:
        pair, records, rejected = [], [], []
        for architecture in SRAM_ARCH:
            run = runs[seed, architecture]
            canonical = read(run["canonical_result"], run["canonical_result_sha256"])
            physical = read(run["physical_result"], run["physical_result_sha256"])["physical"]
            report = read(run["physical_result"].rsplit("/", 1)[0] + "/attempt01/physical/6_report.json")
            service = Service(SRAM_SERVICE, 256, 1, 100e6,
                              report["finish__design__instance__area__stdcell"],
                              physical["finish_exit_code"] == 0, report.get("finish__timing__setup__ws"),
                              report.get("finish__timing__hold__ws"), report.get("finish__timing__drv__hold_violation_count"))
            ops = {r["operation_class"]: r for r in canonical["operation_records"] if r["qualification"] == QUALIFIED}
            require(len(ops) == run["qualified_operation_count"], "ISCAS admitted operation count differs from manifest")
            if set(ops) != set(OPERATIONS) or not service.eligible(
                    contract=SRAM_SERVICE, capacity_words=256, max_latency=1, min_rate=100e6):
                rejected.append({"architecture_id": architecture, "placement_seed": seed,
                                 "setup_ns": service.setup_ns, "hold_ns": service.hold_ns,
                                 "hold_violations": service.hold_violations, "qualified_operation_count": len(ops)})
                continue
            energies = {}
            source = f"{ISCAS}/{run['canonical_result']}"
            identity = f"ISCAS-v3.3/{run['physical_result'].split('/')[-2]}"
            for operation in OPERATIONS:
                row = ops[operation]
                registered = manifest_records[row["record_id"]]
                power = row["power"]["ecc_logic_excluding_macro_w"]["total_w"]
                require(row["pvt"] == PVT and row["physical_seed"] == seed and row["clock_period_ns"] == 10.0
                        and row["architecture_id"] == architecture and row["qualification"] == QUALIFIED
                        and row["power"]["whole_memory_energy_j_per_operation"] is None,
                        "ISCAS operation identity, qualification or boundary differs")
                require(row["exact_operation_count"] == 256
                        and row["activity"]["coverage"]["functional_logic_coverage_fraction"] >= 0.95
                        and row["activity"]["macro_output_activity_root_adapter"]["all_required_roots_annotated"],
                        "ISCAS count or activity gate differs")
                reconstructed = power * row["measurement_duration_seconds"] / row["exact_operation_count"]
                ref = reference[seed, operation]
                prefix = "secded" if architecture == "SECDED" else "hsiao"
                require(row["record_id"] == ref[f"{prefix}_record_id"]
                        and math.isclose(reconstructed, float(ref[f"{prefix}_energy_j"]), rel_tol=1e-12)
                        and math.isclose(reconstructed, row["power"]["ecc_logic_energy_j_per_operation"], rel_tol=1e-12)
                        and math.isclose(reconstructed, registered["energy_j_per_operation"], rel_tol=1e-12),
                        "ISCAS raw power/window/count do not reproduce both references")
                energies[operation] = reconstructed
                records.append({"architecture_id": architecture, "placement_seed": seed,
                                "physical_identity": identity,
                                "service_contract": SRAM_SERVICE, "technology": "SKY130HD TT 1.8 V 25 C",
                                "workload_identity": row["workload_sha256"], "source_model_identity": "ISCAS-v3.3-E5",
                                "operation": operation, "energy_j": reconstructed,
                                "power_w": power, "window_s": row["measurement_duration_seconds"],
                                "operations_or_idle_cycles": row["exact_operation_count"], "unit": "J per operation or idle cycle",
                                "evidence_class": "HISTORICAL_VALIDATED_ESTIMATE", "eligibility": "ADMITTED",
                                "result_status": "COMPLETED", "experiment_id": "GREENS-PHASE2-PLUS-R1/A03",
                                "artifact_reference": source, "record_id": row["record_id"]})
            pair.append(Candidate(identity, architecture, seed, service,
                                  {op: v for op, v in energies.items() if op != "IDLE"},
                                  ops["IDLE"]["power"]["ecc_logic_excluding_macro_w"]["total_w"],
                                  source, ops["IDLE"]["routed_netlist_sha256"], "ISCAS-v3.3-canonical-operation-mix",
                                  report["finish__design__die__area"], report["finish__design__instance__area__macros"]))
        if rejected:
            exclusions.extend(rejected)
            continue
        for operation in OPERATIONS:
            left, right = (r for r in records if r["operation"] == operation)
            require(left["workload_identity"] == right["workload_identity"] and left["window_s"] == right["window_s"],
                    "ISCAS workload or window is unmatched")
        require(pair[0].die_um2 == pair[1].die_um2 and pair[0].macro_um2 == pair[1].macro_um2,
                "ISCAS fixed die or common macro premise differs")
        pairs.append(tuple(pair))
        observations.extend(records)
    require(tuple(pair[0].seed for pair in pairs) == (13, 17, 19, 23) and len(observations) == 40,
            "ISCAS cohort reproduction differs")
    return pairs, observations, exclusions
