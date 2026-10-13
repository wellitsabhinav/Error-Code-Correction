"""Scientific admission regressions for the GREENS reviewer entry point."""
import copy
import json
import subprocess
import sys

import pytest

from scripts import reproduce_iscas as artifact


def test_setup_pass_does_not_override_hold_failure_or_missing_measurement():
    physical = {"finish_exit_code": 0}
    report = {"finish__timing__setup__ws": 0.5, "finish__timing__hold__ws": -0.01,
              "finish__timing__drv__hold_violation_count": 1}
    reasons = artifact.timing_admission(physical, report)
    assert "HOLD_FAILED_OR_MISSING" in reasons
    assert "HOLD_VIOLATIONS_OR_MISSING_COUNT" in reasons
    del report["finish__timing__hold__ws"]
    assert "HOLD_FAILED_OR_MISSING" in artifact.timing_admission(physical, report)


@pytest.mark.parametrize("failure", ["workload", "unavailable_energy", "wrong_denominator"])
def test_operation_join_rejects_substitution_and_invalid_energy(failure):
    rows = json.loads((artifact.CAMPAIGN / "RUN_MANIFEST.json").read_text())["new_activity_power_records"]
    left = copy.deepcopy(next(r for r in rows if r["architecture_id"] == "SECDED" and r["physical_seed"] == 13 and r["operation_class"] == "READ_CLEAN"))
    right = copy.deepcopy(next(r for r in rows if r["architecture_id"] == "HSIAO_SECDED" and r["physical_seed"] == 13 and r["operation_class"] == "READ_CLEAN"))
    if failure == "workload":
        right["workload_sha256"] = "another workload"
    elif failure == "unavailable_energy":
        right["energy_j_per_operation"] = None
    else:
        left["exact_operation_count"] = right["exact_operation_count"] = 128
    with pytest.raises(ValueError, match="fail closed"):
        artifact.paired_cell(left, right)


def test_changed_frozen_bytes_are_rejected_without_resealing(tmp_path):
    (tmp_path / "hashes").mkdir()
    source = tmp_path / "evidence.json"
    source.write_bytes(b'{"energy": 1}\n')
    (tmp_path / "hashes/CAMPAIGN_ARTIFACTS.sha256").write_text(f"{artifact.digest(source)}  evidence.json\n")
    source.write_bytes(b'{"energy": 2}\n')
    with pytest.raises(ValueError, match="sealed bytes differ"):
        artifact.verify_seal(tmp_path)


def test_frozen_campaign_cannot_be_used_as_derivation_output():
    with pytest.raises(ValueError, match="outside frozen campaigns"):
        artifact.write_outputs(artifact.CAMPAIGN, {}, figures=False)


def test_documented_claim_command_matches_tracked_numerical_derivations():
    result = subprocess.run([sys.executable, "scripts/reproduce_iscas.py", "--check"],
                            cwd=artifact.ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    headline = json.loads(result.stdout)
    assert headline["primary_seeds"] == [13, 17, 19, 23]
    assert headline["paired_operation_cells"] == 20
    assert headline["hsiao_lower_cells"] == 4
    assert headline["whole_sram_lifecycle_winner"] is None


def test_resealing_does_not_change_the_frozen_campaign_identity(tmp_path, monkeypatch):
    campaign = tmp_path / 'campaign'
    reference = tmp_path / 'reference'
    (campaign / 'hashes').mkdir(parents=True)
    (reference / 'integrity').mkdir(parents=True)
    evidence = campaign / 'evidence.json'
    evidence.write_bytes(b'{"energy": 1}\n')
    seal = campaign / 'hashes/CAMPAIGN_ARTIFACTS.sha256'
    seal.write_text(f"{artifact.digest(evidence)}  evidence.json\n")
    relative = (artifact.frozen.CAMPAIGN_REL / 'hashes/CAMPAIGN_ARTIFACTS.sha256').as_posix()
    identity = {"frozen_inputs": {relative: artifact.digest(seal)}}
    (reference / 'integrity/source_manifest.json').write_text(json.dumps(identity))
    evidence.write_bytes(b'{"energy": 2}\n')
    seal.write_text(f"{artifact.digest(evidence)}  evidence.json\n")
    monkeypatch.setattr(artifact, 'CAMPAIGN', campaign)
    monkeypatch.setattr(artifact, 'REFERENCE', reference)
    with pytest.raises(ValueError, match='resealing is not reproduction'):
        artifact.verified_frozen_campaign()


@pytest.mark.parametrize('slack', [None, True, float('nan'), float('inf')])
def test_missing_or_non_numeric_slack_cannot_admit_a_run(slack):
    report = {"finish__timing__setup__ws": slack, "finish__timing__hold__ws": 0.1,
              "finish__timing__drv__hold_violation_count": 0}
    assert 'SETUP_FAILED_OR_MISSING' in artifact.timing_admission({"finish_exit_code": 0}, report)


def test_boolean_hold_count_is_not_a_measured_zero():
    report = {"finish__timing__setup__ws": 0.1, "finish__timing__hold__ws": 0.1,
              "finish__timing__drv__hold_violation_count": False}
    assert 'HOLD_VIOLATIONS_OR_MISSING_COUNT' in artifact.timing_admission({"finish_exit_code": 0}, report)
