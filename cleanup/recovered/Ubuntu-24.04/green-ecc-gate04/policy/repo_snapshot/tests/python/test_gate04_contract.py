from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gate04_contract_has_complete_paired_matrix() -> None:
    contract = json.loads((ROOT / "scripts/gate04/contract_v1.json").read_text(encoding="utf-8"))
    assert contract["physical_experiment"]["candidate_ids"] == [
        "secded-rtl-combinational-72-64-v1",
        "secded-rtl-pipelined-72-64-v1",
        "hsiao-generated-combinational-72-64-v1",
        "shortened-bch-78-64-t2-v1-rtl-syndrome-chien-v1",
    ]
    assert contract["physical_experiment"]["clock_periods_ns"] == [10.0, 5.0]
    assert contract["physical_experiment"]["physical_seeds"] == [11, 29, 47, 71, 101]
    assert contract["physical_experiment"]["expected_candidate_flows"] == 40
    assert contract["activity"]["payload_operations_per_trace"] == 100000
    assert contract["statistics"]["material_fraction"] == 0.05


def test_gate04_candidate_and_flow_freezes_reconcile_exact_counts() -> None:
    with (ROOT / "docs/date2027/rigour_gate_04/ASIC_CANDIDATE_MATRIX.csv").open(encoding="utf-8", newline="") as stream:
        candidates = list(csv.DictReader(stream))
    with (ROOT / "docs/date2027/rigour_gate_04/FLOW_RUN_MATRIX.csv").open(encoding="utf-8", newline="") as stream:
        flows = list(csv.DictReader(stream))
    assert sum(row["gate02_eligibility"] == "ELIGIBLE" for row in candidates) == 14
    assert sum(row["gate04_status"] == "MANDATORY_PHYSICAL_CANDIDATE" for row in candidates) == 4
    assert len(flows) == 60
    assert sum(row["kind"] == "candidate" for row in flows) == 40
    assert sum(row["kind"] == "reference" for row in flows) == 20
    assert len({row["run_directory"] for row in flows}) == 60


def test_gate04_trace_encoders_are_systematic_and_exact_width() -> None:
    traces = _module("gate04_generate_traces", "scripts/gate04/generate_traces.py")
    for value in (0, 1, 0x0123456789ABCDEF, (1 << 64) - 1):
        secded = traces.secded_encode(value)
        bch = traces.bch_encode(value)
        assert secded.bit_length() <= 72
        assert bch.bit_length() <= 78
        assert bch & ((1 << 64) - 1) == value
        assert secded.bit_count() % 2 == 0


def test_gate04_wrapper_has_independent_registered_observable_channels() -> None:
    wrapper = (ROOT / "scripts/gate04/rtl/gate04_boundaries.sv").read_text(encoding="utf-8")
    assert wrapper.count("module gate04_") == 6
    assert wrapper.count("dec_codeword_echo_o") == 18
    assert "fault_i" not in wrapper
    assert "ready_i" not in wrapper
    assert "secded_pipelined_72_64_v1_encoder" in wrapper
    assert "secded_pipelined_72_64_v1_decoder" in wrapper


def test_gate04_exact_reliability_enumeration_core_expectations() -> None:
    reliability = _module("gate04_reliability", "scripts/gate04/generate_reliability.py")
    for position in range(72):
        assert reliability.conventional_decoder(1 << position) == "corrected"
    assert reliability.conventional_decoder((1 << 0) | (1 << 1)) == "due"
