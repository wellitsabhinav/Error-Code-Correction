from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import jsonschema


REPO = Path(__file__).resolve().parents[1]
CAMPAIGN = REPO / "campaigns/iscas_sustainability_extension/green_v3_2_matched_openram_orfs_validation"
FROZEN_SEAL_COMMIT = "22d6ef2391f7d74f0890933fcda9952fdf656e52"
EXPECTED_SEEDS = {11, 13, 17, 19, 23}
EXPECTED_CLOCKS = {5.0, 10.0}
EXPECTED_ARCHITECTURES = {"U0", "SECDED", "HSIAO_SECDED", "BCH_78_64_T2"}


def load(relative: str) -> dict[str, Any]:
    return json.loads((CAMPAIGN / relative).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def physical_records() -> list[dict[str, Any]]:
    return load("PHYSICAL_RUN_RESULTS.json")["records"]


def iter_hashes(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for nested in value.values():
            yield from iter_hashes(nested)


def test_frozen_green_v32_tree_is_unchanged() -> None:
    frozen_path = "campaigns/iscas_sustainability_extension/green_matrix_v3_2"
    result = subprocess.run(
        [
            "git", "diff", "--exit-code", FROZEN_SEAL_COMMIT, "--", frozen_path,
            ":(exclude)campaigns/iscas_sustainability_extension/green_matrix_v3_2/build_campaign.py",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    tree = subprocess.check_output(
        ["git", "rev-parse", f"{FROZEN_SEAL_COMMIT}:{frozen_path}"], cwd=REPO, text=True
    ).strip()
    assert tree == "c11980e68e482c519121b46b43ac9816c69a7494"


def test_architecture_ids_are_unique_and_inclusion_is_fail_closed() -> None:
    records = load("ARCHITECTURE_AUDIT.json")["records"]
    ids = [record["architecture_id"] for record in records]
    assert len(ids) == len(set(ids))
    included = {record["architecture_id"] for record in records if record["classification"] == "INCLUDE"}
    assert included == EXPECTED_ARCHITECTURES
    assert next(record for record in records if record["architecture_id"] == "SEC_DAEC")["classification"] == "EXCLUDE"


def test_every_physical_result_references_a_real_compact_run() -> None:
    records = physical_records()
    assert len(records) == 40
    assert len({record["run_id"] for record in records}) == 40
    manifest = load("RUN_MANIFEST.json")
    assert manifest["run_count"] == len(records)
    assert {record["run_id"] for record in manifest["records"]} == {record["run_id"] for record in records}
    for record in manifest["records"]:
        report = CAMPAIGN / record["report_path"]
        assert report.is_file()
        assert sha256(report) == record["report_sha256"]


def test_every_run_references_valid_hashes_and_dependencies() -> None:
    hex_digits = set("0123456789abcdef")
    for record in load("RUN_MANIFEST.json")["records"]:
        for field in (
            "rtl_sha256", "macro_sha256", "config_sha256", "constraint_sha256", "report_sha256",
            "compact_log_sha256", "compact_report_sha256", "output_sha256",
        ):
            hashes = list(iter_hashes(record[field]))
            assert hashes, (record["run_id"], field)
            assert all(len(value) == 64 and set(value) <= hex_digits for value in hashes)
        assert record["report_path"].endswith(f"{record['run_id']}/run-metadata.json")


def test_full_seed_and_timing_population_is_preserved() -> None:
    records = physical_records()
    for architecture in EXPECTED_ARCHITECTURES:
        for clock in EXPECTED_CLOCKS:
            seeds = {
                record["seed"] for record in records
                if record["architecture_id"] == architecture and record["clock_period_ns"] == clock
            }
            assert seeds == EXPECTED_SEEDS


def test_missing_metrics_remain_null_and_csv_cells_remain_blank() -> None:
    records = {record["run_id"]: record for record in physical_records()}
    with (CAMPAIGN / "PHYSICAL_RUN_RESULTS.csv").open(encoding="utf-8", newline="") as stream:
        rows = {row["run_id"]: row for row in csv.DictReader(stream)}
    paths = {
        "mapped_cell_count": ("synthesis", "mapped_cell_count"),
        "wirelength_um": ("routing", "total_wirelength_um"),
        "congestion_metric": ("routing", "congestion_metric"),
        "internal_power_w": ("power", "internal_w"),
    }
    saw_null = False
    for run_id, record in records.items():
        for csv_name, (group, name) in paths.items():
            value = record["metrics"][group][name]
            if value is None:
                saw_null = True
                if csv_name in rows[run_id]:
                    assert rows[run_id][csv_name] == ""
    assert saw_null
    for group in load("SEED_STATISTICS.json")["records"]:
        congestion = group["metrics"]["congestion_metric"]
        assert congestion["available_count"] == 0
        assert congestion["mean"] is None
        assert congestion["minimum"] is None


def test_diagnostic_power_cannot_be_promoted_to_e5() -> None:
    power = load("POWER_DIAGNOSTIC_SUMMARY.json")
    assert power["classification"] == "E4_DIAGNOSTIC_VECTORLESS"
    assert power["e5_qualified"] is False
    assert all(record["qualification"] == "E4_DIAGNOSTIC_VECTORLESS" for record in power["records"])
    status = load("CAMPAIGN_STATUS.json")
    assert status["evidence_added"]["E5"] == 0
    assert status["combined_additive_matrix_counts"] == {"M_E": 601, "M_P": 10, "M_S": 2}
    assert status["E5_status"] == "E5_CAMPAIGN_READY_BUT_NOT_QUALIFIED"


def test_reliability_carbon_pareto_and_winner_guards_remain_closed() -> None:
    status = load("CAMPAIGN_STATUS.json")
    assert status["physical_SDC_DUE_FIT"] == "BLOCKED"
    assert status["Qcrit"] == "BLOCKED"
    assert status["SKY130_manufacturing_lifecycle_carbon"] == "BLOCKED"
    assert status["qualified_pareto_status"] == "BLOCKED"
    assert status["global_winner"] == "NO_GLOBAL_WINNER_QUALIFIED"
    interleaver = load("INTERLEAVER_ROUTED_VALIDATION.json")
    assert interleaver["physical_reliability_claim"] == "BLOCKED_NO_TOPOLOGY_MAP"
    assert load("BIT_MAPPING_AUDIT.json")["PHYSICAL_TO_LOGICAL_BIT_MAPPING"] == "BLOCKED"


def test_physical_results_validate_against_schema() -> None:
    schema = load("schema/physical_run.schema.json")
    validator = jsonschema.Draft202012Validator(schema)
    for record in physical_records():
        validator.validate(record)


def test_comparison_boundary_is_matched_and_exceptions_are_labelled() -> None:
    records = physical_records()
    assert {record["user_payload_capacity_bits"] for record in records} == {16384}
    assert len({record["constraint_sha256"] for record in records}) == 1
    assert len({record["toolchain"]["container_image"] for record in records}) == 1
    assert len({json.dumps(record["pdk"], sort_keys=True) for record in records}) == 1
    for record in records:
        exception = record["common_documented_exception"]
        assert exception["applied"] is True
        assert exception["compliance_claimed"] is False
        assert exception["id"] == "UPSTREAM_SRAM22_MAX_TRANSITION_RESIZE_STAGE_BYPASS"
        specific = record["architecture_specific_exceptions"]
        if record["architecture_id"] == "HSIAO_SECDED":
            assert [item["id"] for item in specific] == ["HSIAO_COMBINATIONAL_SYNDROME_ROM_INFERENCE_THRESHOLD"]
            assert specific[0]["semantic_change"] is False
            assert specific[0]["matched_boundary_change"] is False
        else:
            assert specific == []
    bits = {record["architecture_id"]: record["physical_stored_bits"] for record in records}
    assert bits == {"U0": 16384, "SECDED": 18432, "HSIAO_SECDED": 18432, "BCH_78_64_T2": 20480}


def test_initial_hsiao_failures_remain_visible() -> None:
    initial = load("manifests/PHYSICAL_RUN_RECORDS_INITIAL_HSIAO_FAILURE.json")
    failures = [
        record for record in initial["records"]
        if record["architecture_id"] == "HSIAO_SECDED" and not record["route_success"]
    ]
    assert len(failures) == 10
    assert initial["classification"] == "PRESERVED_INITIAL_HSIAO_SYNTH_MEMORY_GUARD_FAILURE"
    failed = load("FAILED_PARTIAL_EXPERIMENTS.json")
    assert any(record["experiment"] == "initial_hsiao_orfs_matrix" for record in failed["records"])


def test_generated_physical_csv_reproduces_json() -> None:
    records = {record["run_id"]: record for record in physical_records()}
    with (CAMPAIGN / "PHYSICAL_RUN_RESULTS.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert {row["run_id"] for row in rows} == set(records)
    for row in rows:
        record = records[row["run_id"]]
        assert int(row["seed"]) == record["seed"]
        assert float(row["clock_period_ns"]) == record["clock_period_ns"]
        assert row["energy_qualification"] == record["metrics"]["power"]["qualification"]
        expected = record["metrics"]["routing"]["total_wirelength_um"]
        assert row["wirelength_um"] == ("" if expected is None else str(expected))


def test_campaign_builder_is_deterministic(tmp_path: Path) -> None:
    tracked_outputs = [
        "ARCHITECTURE_AUDIT.json",
        "RUN_MANIFEST.json",
        "PHYSICAL_RUN_RESULTS.json",
        "PHYSICAL_RUN_RESULTS.csv",
        "SEED_STATISTICS.json",
        "SEED_STATISTICS.csv",
        "CAMPAIGN_STATUS.json",
        "FINAL_REPORT.md",
        "ISCAS_EXPERIMENT_SUMMARY.md",
    ]
    before = {name: sha256(CAMPAIGN / name) for name in tracked_outputs}
    from tests.frozen_builder_helpers import check_campaign_builder
    inputs = {source["path"] for row in load("ARCHITECTURE_AUDIT.json")["records"]
              for source in row.get("rtl_sources", [])}
    inputs.update(view["path"] for row in load("OPENRAM_MACRO_MANIFEST.json")["inherited_macro_artifacts"]
                  for view in row["views"].values())
    inputs.add("green_ecc_physical_simulation/registry/scientific_hash_migrations.json")
    check_campaign_builder(REPO, CAMPAIGN, tracked_outputs, inputs)
    after = {name: sha256(CAMPAIGN / name) for name in tracked_outputs}
    assert after == before
