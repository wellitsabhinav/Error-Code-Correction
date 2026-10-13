from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

import jsonschema
import pytest


REPO = Path(__file__).resolve().parents[1]
CAMPAIGN = REPO / "campaigns/iscas_sustainability_extension/green_v3_3_activity_complete_e5"
PARENT_SEAL = "8af0fc5a2532b3471016a86cde7968af7d15cfa9"
FROZEN_V32 = "campaigns/iscas_sustainability_extension/green_v3_2_matched_openram_orfs_validation"

sys.path.insert(0, str(REPO))
from campaigns.iscas_sustainability_extension.green_v3_3_activity_complete_e5.campaign_runtime import (  # noqa: E402
    BUDGET_SCOPE,
    CAMPAIGN_BUDGET_SECONDS,
    CampaignDeadline,
    CampaignController,
    load_or_create_state,
)


def load(name: str) -> dict[str, Any]:
    return json.loads((CAMPAIGN / name).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_budget_is_fifteen_hours_for_the_entire_campaign() -> None:
    assert CAMPAIGN_BUDGET_SECONDS == 15 * 60 * 60
    for name in ("RUN_MANIFEST.json", "CAMPAIGN_QUEUE.json", "CAMPAIGN_STATUS.json"):
        payload = load(name)
        budget = payload.get("budget", payload.get("runtime_budget", payload))
        assert budget.get("scope", budget.get("budget_scope")) == BUDGET_SCOPE
        assert budget.get("maximum_wall_clock_seconds", budget.get("seconds", budget.get("campaign_budget_seconds"))) == 54000
        assert budget["per_run_timeout_seconds"] is None


def test_resuming_does_not_reset_the_deadline(tmp_path: Path) -> None:
    state_path = tmp_path / "runtime.json"
    deadline_a, state_a = load_or_create_state(state_path, now=1_000.0, budget_seconds=54000)
    deadline_b, state_b = load_or_create_state(state_path, now=20_000.0, budget_seconds=54000)
    assert deadline_b.start_timestamp == deadline_a.start_timestamp == 1_000.0
    assert deadline_b.deadline_timestamp == deadline_a.deadline_timestamp == 55_000.0
    assert state_b["campaign_start_time_utc"] == state_a["campaign_start_time_utc"]
    assert state_b["hard_deadline_utc"] == state_a["hard_deadline_utc"]


def test_new_jobs_receive_only_remaining_campaign_time() -> None:
    deadline = CampaignDeadline.create(now=100.0)
    assert deadline.effective_job_timeout(now=100.0) == 54000
    assert deadline.effective_job_timeout(now=3700.0) == 50400
    assert deadline.effective_job_timeout(now=3700.0, requested_seconds=600) == 600
    assert deadline.effective_job_timeout(now=54000.0, requested_seconds=10000) == 100
    assert deadline.effective_job_timeout(now=54100.0) == 0
    with pytest.raises(ValueError, match="15-hour maximum"):
        CampaignDeadline.create(now=100.0, budget_seconds=54001)


def test_existing_campaign_cannot_be_reinterpreted_with_a_fresh_budget(tmp_path: Path) -> None:
    state_path = tmp_path / "runtime.json"
    load_or_create_state(state_path, now=10.0, budget_seconds=54000)
    with pytest.raises(ValueError, match="different budget"):
        load_or_create_state(state_path, now=20.0, budget_seconds=100)


def test_controller_reuses_completion_artifact_without_recomputation(tmp_path: Path) -> None:
    artifact = tmp_path / "already-finished.json"
    artifact.write_text("{}\n", encoding="utf-8")
    marker = tmp_path / "should-not-exist"
    controller = CampaignController(
        state_path=tmp_path / "state.json",
        progress_path=tmp_path / "PROGRESS.md",
        budget_seconds=10,
        launch_guard_seconds=0,
        poll_seconds=0.01,
    )
    state = controller.run(
        [
            {
                "job_id": "existing",
                "command": [sys.executable, "-c", f"from pathlib import Path; Path({str(marker)!r}).touch()"],
                "completion_artifact": str(artifact),
            }
        ]
    )
    assert state["jobs"]["existing"]["status"] == "COMPLETED_REUSED"
    assert not marker.exists()


def test_pathological_job_is_stopped_by_global_campaign_deadline(tmp_path: Path) -> None:
    controller = CampaignController(
        state_path=tmp_path / "state.json",
        progress_path=tmp_path / "PROGRESS.md",
        budget_seconds=1,
        launch_guard_seconds=0,
        poll_seconds=0.02,
        terminate_grace_seconds=0.1,
    )
    started = time.monotonic()
    state = controller.run(
        [
            {"job_id": "pathological", "priority": 1, "command": [sys.executable, "-c", "import time; time.sleep(30)"]},
            {"job_id": "must_not_launch", "priority": 2, "command": [sys.executable, "-c", "raise SystemExit(99)"]},
        ]
    )
    assert time.monotonic() - started < 5
    assert state["status"] == "CAMPAIGN_RUNTIME_CUTOFF"
    assert state["jobs"]["pathological"]["status"] == "CAMPAIGN_RUNTIME_CUTOFF"
    assert state["jobs"]["must_not_launch"]["status"] == "CAMPAIGN_RUNTIME_CUTOFF"
    assert state["jobs"]["pathological"]["effective_subprocess_timeout_seconds"] <= 1


def test_process_launch_failure_is_preserved_as_tool_failure(tmp_path: Path) -> None:
    controller = CampaignController(
        state_path=tmp_path / "state.json",
        progress_path=tmp_path / "PROGRESS.md",
        budget_seconds=10,
        launch_guard_seconds=0,
    )
    state = controller.run(
        [{"job_id": "missing_tool", "priority": 1, "command": [str(tmp_path / "does-not-exist")]}]
    )
    assert state["status"] == "COMPLETED_WITH_PARTIAL_FAILURES"
    assert state["jobs"]["missing_tool"]["status"] == "TOOL_FAILURE"
    assert state["jobs"]["missing_tool"]["classification"] == "PROCESS_LAUNCH_FAILURE"


def test_runtime_state_schema_accepts_controller_state(tmp_path: Path) -> None:
    state_path = tmp_path / "runtime.json"
    _, state = load_or_create_state(state_path, now=1_000.0, budget_seconds=54000)
    schema = load("schema/runtime_state.schema.json")
    jsonschema.Draft202012Validator(schema).validate(state)


def test_empty_queue_does_not_start_campaign_clock(tmp_path: Path) -> None:
    queue = tmp_path / "queue.json"
    queue.write_text('{"budget_scope": "ENTIRE_CAMPAIGN", "jobs": []}\n', encoding="utf-8")
    state_path = tmp_path / "state.json"
    result = subprocess.run(
        [
            sys.executable,
            str(CAMPAIGN / "scripts/run_campaign.py"),
            "--queue", str(queue),
            "--runtime-state", str(state_path),
            "--progress", str(tmp_path / "PROGRESS.md"),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "refusing to start" in result.stderr
    assert not state_path.exists()


def test_workloads_are_complete_deterministic_and_semantically_matched() -> None:
    manifest = load("WORKLOAD_MANIFEST.json")
    assert manifest["record_count"] == 180
    records = manifest["records"]
    assert len({row["workload_record_id"] for row in records}) == 180
    for row in records:
        assert row["exact_operation_count"] == 256
        assert row["warm_up_cycles"] == 16
        assert row["activity_end_timestamp_ns"] > row["activity_begin_timestamp_ns"]
        assert row["activity_sha256"] is None or len(row["activity_sha256"]) == 64
        assert len(row["workload_sha256"]) == 64
    qualified = [row for row in records if row["activity_sha256"] is not None]
    assert len(qualified) == 46
    clean_read_hashes = {row["workload_sha256"] for row in records if row["operation_class"] == "READ_CLEAN"}
    clean_write_hashes = {row["workload_sha256"] for row in records if row["operation_class"] == "WRITE_CLEAN"}
    assert len(clean_read_hashes) == 1
    assert len(clean_write_hashes) == 1


def test_timing_partition_is_fail_closed() -> None:
    groups = load("TIMING_FEASIBILITY.json")["records"]
    classes = {(row["architecture_id"], row["clock_period_ns"]): row["implementation_class"] for row in groups}
    assert classes[("U0", 10.0)] == "TIMING_FEASIBLE_10NS"
    assert classes[("SECDED", 10.0)] == "TIMING_FEASIBLE_10NS"
    assert classes[("HSIAO_SECDED", 10.0)] == "TIMING_FEASIBLE_10NS"
    assert classes[("BCH_78_64_T2", 10.0)] == "TIMING_INFEASIBLE_AS_IMPLEMENTED"
    assert classes[("U0", 5.0)] == "TIMING_FEASIBLE_5NS"
    assert all(row["setup_feasible_seed_count"] in {0, 5} for row in groups)


def test_macro_audit_blocks_unrestricted_whole_memory_e5() -> None:
    audit = load("SRAM_MACRO_POWER_QUALIFICATION.json")
    assert audit["whole_memory_e5_qualified"] is False
    assert audit["qualification"] == "E5_LOGIC_ACTIVITY_QUALIFIED_MACRO_ENERGY_INCOMPLETE"
    quantities = audit["required_quantity_classification"]
    assert quantities["leakage"] == "AVAILABLE"
    assert quantities["address_dependent_transitions"] == "ABSENT"
    assert quantities["data_dependent_transitions"] == "ABSENT"
    assert all(row["observed_construct_counts"]["internal_power_groups"] > 0 for row in audit["macro_records"])


def test_only_qualified_activity_power_is_promoted_to_e5() -> None:
    status = load("CAMPAIGN_STATUS.json")
    statistics = load("E5_OPERATION_STATISTICS.json")
    matrix = load("GREEN_V3_3_ADDITIVE_MATRIX.json")
    assert status["evidence_added"]["E5"] == 46
    assert status["E5_status"] == "E5_LOGIC_ACTIVITY_QUALIFIED_MACRO_ENERGY_INCOMPLETE"
    assert status["ecc_logic_e5_qualified"] is True
    assert status["whole_memory_e5_qualified"] is False
    assert statistics["qualified_measurement_count"] == 46
    assert statistics["record_count"] == 10
    assert {row["count"] for row in statistics["records"]} == {4, 5}
    assert matrix["new_evidence_counts"]["E5"] == 46
    assert matrix["global_winner"] == "NO_GLOBAL_WINNER_QUALIFIED"


def test_campaign_hash_manifest_covers_all_immutable_artifacts() -> None:
    manifest_path = CAMPAIGN / "hashes/CAMPAIGN_ARTIFACTS.sha256"
    recorded: dict[str, str] = {}
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        recorded[relative] = digest
    expected = {
        path.relative_to(CAMPAIGN).as_posix(): path
        for path in CAMPAIGN.rglob("*")
        if path.is_file()
        and path != manifest_path
        and "__pycache__" not in path.parts
        and path.name != "RUNTIME_STATE.json"
        and "logs" not in path.parts
        and "progress" not in path.parts
    }
    assert set(recorded) == set(expected)
    assert all(recorded[relative] == sha256(path) for relative, path in expected.items())


def test_parent_v32_tree_is_unchanged() -> None:
    result = subprocess.run(
        [
            "git", "diff", "--exit-code", PARENT_SEAL, "--", FROZEN_V32,
            ":(exclude)campaigns/iscas_sustainability_extension/green_v3_2_matched_openram_orfs_validation/build_campaign.py",
            ":(exclude)campaigns/iscas_sustainability_extension/green_v3_2_matched_openram_orfs_validation/hashes/CAMPAIGN_ARTIFACTS.sha256",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_builder_is_deterministic(tmp_path: Path) -> None:
    outputs = [
        "CAMPAIGN_PLAN.md",
        "CAMPAIGN_STATUS.json",
        "RUN_MANIFEST.json",
        "WORKLOAD_MANIFEST.json",
        "TIMING_FEASIBILITY.json",
        "E5_OPERATION_STATISTICS.json",
        "E5_MATCHED_SEED_DELTAS.csv",
        "SRAM_MACRO_POWER_QUALIFICATION.json",
        "FINAL_REPORT.md",
        "VALIDATION_RESULTS.json",
    ]
    before = {name: sha256(CAMPAIGN / name) for name in outputs}
    from tests.frozen_builder_helpers import check_campaign_builder
    inputs = {FROZEN_V32 + "/PHYSICAL_RUN_RESULTS.json", FROZEN_V32 + "/RUN_MANIFEST.json"}
    inputs.update(row["path"] for row in load("SRAM_MACRO_POWER_QUALIFICATION.json")["macro_records"])
    check_campaign_builder(REPO, CAMPAIGN, outputs, inputs)
    after = {name: sha256(CAMPAIGN / name) for name in outputs}
    assert after == before
