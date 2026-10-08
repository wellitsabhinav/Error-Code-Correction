import logging
import math

import pytest

from ecc_selector import select, _pareto_front
from ser_model import flux_from_location


def test_pareto_dominance():
    records = [
        {"code": "a", "FIT": 1.0, "carbon_kg": 1.0, "latency_ns": 2.0},
        {"code": "b", "FIT": 2.0, "carbon_kg": 1.5, "latency_ns": 1.0},
        {"code": "c", "FIT": 3.0, "carbon_kg": 2.0, "latency_ns": 3.0},
    ]
    front = _pareto_front(records)
    assert [r["code"] for r in front] == ["a", "b"]


def _default_params():
    return {
        "node": 14,
        "vdd": 0.8,
        "temp": 75.0,
        "capacity_gib": 8.0,
        "ci": 0.55,
        "bitcell_um2": 0.040,
    }


def test_constraint_pruning():
    res = select(
        ["sec-ded-64", "sec-daec-64", "taec-64"],
        constraints={"latency_ns_max": 1.2},
        **_default_params(),
    )
    assert [r["code"] for r in res["pareto"]] == ["sec-ded-64"]


def test_mux_overhead_is_explicit_and_additive():
    params = _default_params()
    params["lifetime_h"] = 8760.0
    baseline = select(["sec-ded-64"], scrub_s=20.0, **params)
    updated = select(
        ["sec-ded-64"],
        scrub_s=20.0,
        include_mux_overhead=True,
        **params,
    )
    old = baseline["candidate_records"][0]
    new = updated["candidate_records"][0]
    assert "mux_model_included" not in old
    assert new["mux_model_included"] is True
    assert new["latency_ns"] > old["latency_ns"]
    assert new["carbon_kg"] > old["carbon_kg"]
    assert new["E_scrub_kWh"] > old["E_scrub_kWh"]


def test_scenario_shift_mbu():
    codes = ["sec-ded-64", "sec-daec-64", "taec-64"]
    light = select(codes, mbu="light", **_default_params())
    heavy = select(codes, mbu="heavy", **_default_params())

    codes_light = {r["code"] for r in light["pareto"]}
    codes_heavy = {r["code"] for r in heavy["pareto"]}

    assert codes_light == {"sec-ded-64"}
    assert {"sec-daec-64", "taec-64"}.issubset(codes_heavy)


def test_nesii_normalisation():
    res = select(["sec-ded-64", "sec-daec-64", "taec-64"], **_default_params())
    norm = res["normalization"]
    assert norm["p5"] <= norm["p95"]

    assert norm["epsilon_on_normalized_axes"] == 1e-8
    assert norm["basis"] == "system"
    assert math.isnan(norm["lifetime_h"])
    assert norm["ci_kg_per_kwh"] == _default_params()["ci"]
    assert norm["ci_source"] == "unspecified"

    for rec in res["pareto"]:
        assert 0.0 <= rec["NESII"] <= 100.0
        assert rec["p5"] == norm["p5"]
        assert rec["p95"] == norm["p95"]
        assert rec["N_scale"] == norm["N"]
        assert 0.0 <= rec["GS"] <= 100.0
        assert all(k in rec for k in ["Sr", "Sc", "Sl"])


def test_location_scaling():
    codes = ["sec-ded-64"]
    params = _default_params()

    sea_level = select(codes, alt_km=0.0, latitude_deg=45.0, **params)
    high_alt = select(codes, alt_km=10.0, latitude_deg=60.0, **params)

    sea_fit = sea_level["candidate_records"][0]["fit_bit"]
    high_fit = high_alt["candidate_records"][0]["fit_bit"]

    assert high_fit > sea_fit

    base_flux = flux_from_location(0.0, 45.0)
    scaled_flux = flux_from_location(10.0, 60.0)
    expected = sea_fit * (scaled_flux / base_flux)
    assert high_fit == pytest.approx(expected, rel=1e-3)


def test_nesii_fallback_logs_once(caplog):
    import ecc_selector

    ecc_selector._logged_fallback = False
    ecc_selector._logged_degenerate = False
    params = _default_params()
    caplog.set_level(logging.WARNING)
    select(["sec-ded-64"], **params)
    select(["sec-ded-64"], **params)
    msgs = [r.message for r in caplog.records if "NESII" in r.message]
    assert msgs == [
        "NESII normalization fallback to min-max",
        "NESII degenerate scale; forcing score 50",
    ]


def test_selector_quality_block():
    res = select(["sec-ded-64", "sec-daec-64", "taec-64"], **_default_params())
    q = res["quality"]
    assert q["ref_point_norm"] == [1.0, 1.0, 1.0]
    assert q["hypervolume"] >= 0.0
    assert q["spacing"] >= 0.0


def test_select_unknown_node_surfaces_message():
    params = _default_params()
    params["node"] = 99
    with pytest.raises(ValueError, match="Unknown technology node 99"):
        select(["sec-ded-64"], **params)

