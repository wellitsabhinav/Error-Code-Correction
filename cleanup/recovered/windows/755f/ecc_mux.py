"""ECC-internal multiplexer parameter helpers.

The repository does not contain a standard-cell library or a synthesis report
from which mux cells can be counted.  The values in :data:`_BASE_MUX_PARAMS`
are therefore *model assumptions* retained from the original benchmark, not
silicon measurements.  This module makes the associated derivations explicit:

* an ``F:1`` mux is normalised to ``F - 1`` equivalent 2:1 muxes;
* a balanced implementation has ``ceil(log2(F))`` mux stages; and
* intermediate nodes are obtained by piecewise-linear interpolation of the
  existing 7, 16 and 28 nm lookup values.

The lookup has no VDD or temperature dimension.  Callers must not represent
the returned energy, delay or area as library-characterised data.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Dict, Mapping, Tuple

# Base illustrative assumption per ECC scheme at the repository's 28 nm row.
_BASE_MUX_PARAMS: Dict[str, Tuple[float, float, float, int]] = {
    # The fan-in values (final column) capture the effective mux size that the
    # datapath must steer parity bits through for each ECC topology. They are
    # expressed as the number of inputs to a single output (e.g. 2 indicates a
    # 2:1 multiplexer).
    "Hamming_SEC": (0.05, 0.02, 1.0, 2),
    "SEC_DAEC": (0.065, 0.027, 1.25, 6),
    "TAEC": (0.07, 0.03, 1.4, 8),
    "BCH": (0.09, 0.04, 1.9, 16),
}


def _scale_mux_params(
    base: Tuple[float, float, float, int],
    scaling: Mapping[str, float],
) -> Tuple[float, float, float, int]:
    """Return *base* parameters scaled for a particular technology node."""

    latency, energy, area, fanin = base
    return (
        latency * scaling["latency"],
        energy * scaling["energy"],
        area * scaling["area"],
        fanin,
    )


_NODE_SCALING: Dict[str, Dict[str, float]] = {
    "28nm": {"latency": 1.0, "energy": 1.0, "area": 1.0},
    "16nm": {"latency": 0.85, "energy": 0.8, "area": 0.7},
    "7nm": {"latency": 0.65, "energy": 0.6, "area": 0.5},
}


# Latency in ns, energy in pJ, area in square microns for each ECC scheme and node.
_MUX_TABLE: Dict[str, Dict[str, Tuple[float, float, float, int]]] = {
    scheme: {
        node: _scale_mux_params(params, node_scaling)
        for node, node_scaling in _NODE_SCALING.items()
    }
    for scheme, params in _BASE_MUX_PARAMS.items()
}


@dataclass(frozen=True)
class ECCMuxCharacterization:
    """Traceable analytical view of one scheme's assumed mux overhead."""

    scheme: str
    node_nm: float
    fanin: int
    equivalent_mux2_count: int
    mux_depth: int
    aggregate_latency_ns: float
    per_stage_delay_ns: float
    aggregate_energy_pj: float
    energy_per_mux2_pj: float
    aggregate_area_um2: float
    area_per_mux2_um2: float
    vdd: None = None
    leakage_power_w: None = None
    source: str = (
        "repository assumed lookup in ecc_mux.py; balanced-tree and 2:1 "
        "normalisation analytically derived"
    )


def _node_value(node: str | int | float) -> float:
    if isinstance(node, str):
        text = node.strip().lower()
        if text.endswith("nm"):
            text = text[:-2]
        try:
            return float(text)
        except ValueError as exc:
            raise ValueError(f"Invalid mux technology node: {node!r}") from exc
    return float(node)


def _interpolated_mux_params(
    scheme: str, node: str | int | float
) -> Tuple[float, float, float, int]:
    """Return table values, linearly interpolating only within 7--28 nm."""

    try:
        node_table = _MUX_TABLE[scheme]
    except KeyError as exc:  # pragma: no cover - defensive
        available = ", ".join(sorted(_MUX_TABLE))
        raise ValueError(
            f"Unknown scheme: {scheme!r}. Available schemes: {available}"
        ) from exc

    node_nm = _node_value(node)
    points = sorted((float(k[:-2]), value) for k, value in node_table.items())
    exact = next((value for n, value in points if math.isclose(n, node_nm)), None)
    if exact is not None:
        return exact

    if node_nm < points[0][0] or node_nm > points[-1][0]:
        available_nodes = ", ".join(sorted(node_table))
        raise ValueError(
            f"No mux calibration for node {node!r} and scheme {scheme!r}. "
            f"Interpolation is limited to {points[0][0]:g}--{points[-1][0]:g} nm; "
            f"tabulated nodes: {available_nodes}"
        )

    for (lo_node, lo), (hi_node, hi) in zip(points, points[1:]):
        if lo_node <= node_nm <= hi_node:
            weight = (node_nm - lo_node) / (hi_node - lo_node)
            latency = lo[0] + weight * (hi[0] - lo[0])
            energy = lo[1] + weight * (hi[1] - lo[1])
            area = lo[2] + weight * (hi[2] - lo[2])
            if lo[3] != hi[3]:  # pragma: no cover - table invariant
                raise ValueError("Mux fan-in must not vary across technology nodes")
            return latency, energy, area, lo[3]

    raise AssertionError("unreachable mux interpolation state")


def compute_ecc_mux_params(
    scheme: str, node: str | int | float
) -> Tuple[float, float, float, int]:
    """Return multiplexer latency, energy, area and fan-in for *scheme* and *node*.

    Parameters are derived from a simple look-up table and are intended for
    illustrative benchmarking rather than detailed circuit modelling.
    """

    return _interpolated_mux_params(scheme, node)


def compute_ecc_mux_characterization(
    scheme: str, node: str | int | float
) -> ECCMuxCharacterization:
    """Return the explicit 2:1 normalisation of the repository mux assumption."""

    latency, energy, area, fanin = compute_ecc_mux_params(scheme, node)
    equivalent_mux2_count = fanin - 1
    mux_depth = int(math.ceil(math.log2(fanin)))
    return ECCMuxCharacterization(
        scheme=scheme,
        node_nm=_node_value(node),
        fanin=fanin,
        equivalent_mux2_count=equivalent_mux2_count,
        mux_depth=mux_depth,
        aggregate_latency_ns=latency,
        per_stage_delay_ns=latency / mux_depth,
        aggregate_energy_pj=energy,
        energy_per_mux2_pj=energy / equivalent_mux2_count,
        aggregate_area_um2=area,
        area_per_mux2_um2=area / equivalent_mux2_count,
    )


__all__ = [
    "ECCMuxCharacterization",
    "compute_ecc_mux_characterization",
    "compute_ecc_mux_params",
]
