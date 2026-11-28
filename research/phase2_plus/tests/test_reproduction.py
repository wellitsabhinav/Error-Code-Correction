import json

import pytest

from evidence import Frozen, admitted_iscas, historical_date
from reproduce_sram_snapshot import safe_path
from scenarios import cases, generate, read_inputs
from zero_delay import trim_vcd


def test_admission_and_deterministic_deployment_grid():
    sources, assumptions = read_inputs()
    frozen = Frozen()
    date = historical_date(frozen)
    sram, observations, exclusions = admitted_iscas(frozen)
    assert len(date) == 5
    assert len(sram) == 4 and len(observations) == 40
    assert [(r["architecture_id"], r["placement_seed"]) for r in exclusions] == [("SECDED", 11), ("HSIAO_SECDED", 11)]
    assert any(r["hold_ns"] < 0 for r in exclusions)
    first = [row.label for row in cases(date, sram, assumptions)]
    assert first == [row.label for row in cases(date, sram, assumptions)]
    assert len(first) == len(set(first)) == 1995
    assert float(sources["grid_mid"]["converted_value"]) == pytest.approx(770.884 * 0.45359237 / 1000)


def test_integrated_carbon_and_absent_values(scratch_path):
    summary = generate(scratch_path, summaries_only=True)
    assert summary["sram_whole_memory_lifecycle_preference"] is None
    assert summary["sky130_matched_inventory"] is None
    assert summary["date_allocation_counts"]["fixed"] == {"reference": 0, "candidate": 525, "ties": 0}
    assert summary["date_allocation_counts"]["allocated"]["reference"] == 43
    assert summary["date_reference_utilization_break_even_years_mid_grid"]["allocated"]["mean"] == pytest.approx(3.239665619)
    assert summary["act_eq_4_5_analytical_check_kg"]["implemented"] == pytest.approx(
        summary["act_eq_4_5_analytical_check_kg"]["manual"]
    )
    manifest = json.loads((scratch_path / "carbon_input_manifest.json").read_text())
    assert len(manifest["frozen_operands_sha256"]) == 30
    assert "operation_conditioned_energy.csv" in manifest["outputs_sha256"]


def test_window_starts_with_prior_values_and_preserves_stop(scratch_path):
    original = scratch_path / "original.vcd"
    cropped = scratch_path / "cropped.vcd"
    header = "$timescale 1ps $end\n$scope module tb $end\n$var wire 1 ! a $end\n$upscope $end\n$enddefinitions $end\n"
    original.write_text(header + "#0\n0!\n#10\n1!\n#20\n0!\n#30\n1!\n")
    trim_vcd(original, cropped, 10, 30)
    assert cropped.read_text() == header + "#0\n$dumpvars\n1!\n$end\n#10\n0!\n#20\n1!\n"
    with pytest.raises(ValueError, match="span"):
        trim_vcd(original, cropped, 10, 40)


@pytest.mark.parametrize("path", ("../foreign", "nested/../../unsafe", "C:/foreign", "/foreign", r"nested\foreign"))
def test_snapshot_paths_confined(path):
    with pytest.raises(ValueError, match="Unsafe"):
        safe_path(path)
