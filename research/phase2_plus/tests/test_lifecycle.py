import math

import pytest

from lifecycle import (
    Interval, Service, Wafer, act_area_kg, break_even_operations, deployment, embodied_kg, grams_to_kg,
    joules_to_kwh, minimax_regret, normalized_mix, operational_kg, pareto_front, pj_to_j, time_crossings,
    um2_to_mm2, wafer_area_mm2,
)


@pytest.mark.parametrize(("function", "operand", "expected"), [
    (joules_to_kwh, 3.6e6, 1), (pj_to_j, 1e12, 1), (grams_to_kg, 1000, 1), (um2_to_mm2, 1e6, 1),
    (wafer_area_mm2, 200, math.pi * 10000),
])
def test_units(function, operand, expected):
    assert function(operand) == pytest.approx(expected)
    with pytest.raises(ValueError):
        function(-1)


def test_wafer_geometry_and_yield():
    unit = Wafer(400, 200, 0, 0, 1)
    low_yield = Wafer(400, 200, 0, 0, 0.8)
    loss = Wafer(400, 200, 3, 0.08, 0.8, aspect_ratio=2)
    post_yield = Wafer(500, 200, 0, 0, None, burden_includes_die_yield=True)
    expected_gross = math.pi * 100**2 / 10 - math.pi * 200 / math.sqrt(20)
    assert unit.gross_dies(10) == pytest.approx(expected_gross)
    assert loss.gross_dies(10) < unit.gross_dies(10)
    assert low_yield.die_kg(10) == pytest.approx(unit.die_kg(10) / 0.8)
    assert post_yield.die_kg(10) == pytest.approx(low_yield.die_kg(10))
    for duplicate_yield in ({"die_yield": 0.8}, {"die_yield": None, "defects_per_mm2": 0.001}):
        with pytest.raises(ValueError, match="already included"):
            Wafer(500, 200, 0, 0, burden_includes_die_yield=True, **duplicate_yield)


def test_three_allocation_boundaries():
    wafer = Wafer(400, 200, 3, 0.08, 0.9)
    total = wafer.die_kg(10)
    assert embodied_kg(wafer, "fixed", 10, 1) == embodied_kg(wafer, "fixed", 10, 2) == total
    assert embodied_kg(wafer, "allocated", 10, 1) + embodied_kg(wafer, "allocated", 10, 9) == pytest.approx(total)
    assert embodied_kg(wafer, "marginal", 10, 1) == wafer.die_kg(11)
    assert embodied_kg(wafer, "marginal", 10, 2) > embodied_kg(wafer, "marginal", 10, 1)
    assert embodied_kg(None, "fixed", 10, 1) is None
    assert embodied_kg(wafer, "marginal", 10, None) is None
    with pytest.raises(ValueError):
        embodied_kg(wafer, "allocated", 10, 11)


def test_act_eq_five_and_manufacturing_scope():
    # Separate calculation for an input for which the published Eq. 4/5 fit.
    expected = (100 / 100) * (0.4 * 0.5 + 0.15 + 0.02) / 0.8
    assert act_area_kg(100, 0.4, 0.5, 0.15, 0.02, 0.8) == pytest.approx(0.4625)
    assert expected == pytest.approx(0.4625)
    # Adding ACT's fab and materials again to a complete wafer inventory is
    # outside the wafer allocation interface.
    with pytest.raises(TypeError):
        embodied_kg(Wafer(400, 200, 0, 0, 0.9), "fixed", 10, None, act_kg=expected)


def test_constant_and_varying_grid_with_disjoint_idle():
    active_j = {"read": 2, "write": 3}
    idle_w = 0.5
    first = Interval(10, 4, 0.6, {"read": 2, "write": 2})
    second = Interval(5, 3, 0.3, {"read": 3})
    assert operational_kg([first], active_j, idle_w) == pytest.approx((10 + 6 * 0.5) * 0.6 / 3.6e6)
    assert operational_kg([first, second], active_j, idle_w) == pytest.approx((13 * 0.6 + 7 * 0.3) / 3.6e6)
    assert Interval(10, 10, 0, {"read": 2}).carbon_kg(active_j, None) == 0
    assert Interval(10, 10, 0.5, {"read": 2}).carbon_kg(active_j, None) == pytest.approx(2 / 3.6e6)
    with pytest.raises(ValueError, match="overlap"):
        Interval(10, 11, 0.4, {"read": 1})
    with pytest.raises(ValueError, match="outside"):
        Interval(10, 0, 0.4, {"read": 1})


def test_normalized_equal_delivered_work_and_missing():
    mix = {"read": 0.4, "write": 0.6}
    a = deployment(10, 0.5, 100, 0.6, mix)
    b = deployment(20, 0.25, 100, 0.3, mix)
    assert a.operation_counts == b.operation_counts == {"read": 200, "write": 300}
    assert operational_kg([a], {"read": 2}, 0) is None
    assert operational_kg([a], {"read": 2, "write": 3}, None) is None
    with pytest.raises(ValueError, match="sum to one"):
        normalized_mix({"read": 0.4, "write": 0.5})


@pytest.mark.parametrize(("embodied", "savings", "grid", "expected"), [
    (0, 0, 0.2, "TIE"), (1, 0, 0.2, "IMMEDIATE_REFERENCE"), (-1, 0, 0.2, "IMMEDIATE_CANDIDATE"),
    (1, 2, 0, "IMMEDIATE_REFERENCE"), (-1, 2, 0.2, "IMMEDIATE_CANDIDATE"),
    (1, -2, 0.2, "IMMEDIATE_REFERENCE"), (1, 2, 0.2, "CANDIDATE_PAYBACK"),
    (-1, -2, 0.2, "REFERENCE_PAYBACK"), (None, 2, 0.2, "UNAVAILABLE"),
])
def test_constant_break_even(embodied, savings, grid, expected):
    value = break_even_operations(embodied, savings, grid)
    assert value.status == expected
    if "PAYBACK" in expected:
        assert value.crossings[0] == pytest.approx(9e6)
    else:
        assert not value.crossings


def test_piecewise_break_even():
    multiple = time_crossings(1, [(2, -2), (4, 4), (6, -6)])
    assert multiple.status == "CROSSES_IN_LIFETIME"
    assert multiple.crossings == (1, 3, 9)
    outside = time_crossings(3, [(2, -2)])
    assert outside.status == "REFERENCE_LOWER_OR_EQUAL"
    assert outside.crossings == ()
    assert time_crossings(0, [(2, 0)]).ties == ((0, 2),)
    assert time_crossings(None, [(2, -2)]).status == "UNAVAILABLE"


def test_service_and_eligibility():
    requirements = dict(contract="SECDED", capacity_words=256, max_latency=3, min_rate=1e8, max_area=400)
    fields = dict(contract="SECDED", capacity_words=256, latency_cycles=2, rate_hz=1e8, area_um2=300,
                  route_complete=True, setup_ns=0, hold_ns=0.1, hold_violations=0)
    assert Service(**fields).eligible(**requirements)
    for failure in (
        {"hold_ns": -0.01}, {"hold_ns": None}, {"hold_violations": 1}, {"setup_ns": -1}, {"setup_ns": None},
        {"route_complete": False}, {"capacity_words": 128}, {"latency_cycles": 4}, {"rate_hz": 50e6},
        {"contract": "BCH"}, {"area_um2": None}, {"area_um2": 401},
    ):
        assert not Service(**(fields | failure)).eligible(**requirements)


def test_minimax_regret_and_pareto():
    cases = [{"a": 2, "b": 1, "c": 4}, {"a": 1, "b": 3, "c": 5}]
    assert minimax_regret(cases) == (("a",), {"a": 1, "b": 2, "c": 4},
                                      {"a": [1, 0], "b": [0, 2], "c": [3, 4]})
    assert pareto_front({"a": (2, 1), "b": (1, 3), "c": (4, 5), "d": (1, 3)}) == ("a", "b", "d")
    with pytest.raises(ValueError):
        minimax_regret([{"a": 1}, {"b": 1}])
    with pytest.raises(ValueError):
        pareto_front({"a": (math.nan,)})
