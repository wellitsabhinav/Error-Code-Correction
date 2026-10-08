"""Voltage and technology-aware ECC energy model.

Scientific intent
-----------------
The model estimates ECC logic energy from an XOR/AND/adder/MUX abstraction instead
of full transistor-level switching simulation. This keeps command-line analysis
fast and deterministic while preserving first-order code-complexity trends.

Calibration strategy
--------------------
``tech_calib.json`` is loaded at import time and treated as the authoritative
technology table. The table is keyed by process node (nm) and VDD (V), with
per-operation energies for ``xor``, ``and``, and ``adder_stage`` in joules.
Runtime lookups use either:

* ``mode='pwl'``: piecewise-linear interpolation in voltage and then node.
* ``mode='nearest'``: nearest-neighbour lookup (legacy compatibility mode).

Core equations and units
------------------------
* Gate energy: :math:`E_g(node, VDD)` [J/op].
* Read-path estimate: :math:`E_{read} = N_{xor}E_{xor} + N_{and}E_{and}
  + alpha_{mux}N_{mux}E_{mux} + E_{other}` [J].
* Energy per correction (EPC): :math:`EPC = E_{total} / N_{corr}` [J/bit].

Engineering assumptions
-----------------------
* Gate-level abstraction is a surrogate for transistor-level power.
* Node scaling is represented via the calibration table (not compact-model
  re-solving at runtime).
* VDD scaling follows calibrated lookup/interpolation, which approximates
  dynamic power trends while retaining stable CLI behavior.
"""

from __future__ import annotations

import logging
import json
from pathlib import Path
from typing import Dict, Sequence

import numpy as np
import math

from calibration import load_calibration as _load_calib
from validation.output_sanity import (
    enforce_sanity,
    validate_metric_non_negative,
    validate_operating_point,
)


_CALIB = _load_calib(Path(__file__).with_name("tech_calib.json"))

_LOGGER = logging.getLogger(__name__)


class UncertaintyValidationError(ValueError):
    """Raised when uncertainty metadata is missing or violates strict bounds."""


def load_calibration_uncertainty(path: Path) -> Dict[int, Dict[float, dict]]:
    """Load uncertainty sidecar keyed by node and VDD.

    Expected shape mirrors ``tech_calib.json`` key hierarchy with uncertainty
    statistics under ``gates.<gate>`` records.
    """

    raw = json.loads(path.read_text(encoding="utf-8"))
    out: Dict[int, Dict[float, dict]] = {}
    for node_key, node_data in raw.items():
        node_nm = int(node_key)
        out[node_nm] = {}
        for vdd_key, vdd_data in node_data.items():
            vdd = float(vdd_key)
            gates = vdd_data.get("gates", {})
            if set(gates) != {"xor", "and", "adder_stage"}:
                raise ValueError(
                    f"Missing uncertainty gate entries for node {node_key} VDD {vdd_key}"
                )
            gate_out = {}
            for gate_name, stats in gates.items():
                required = {"n", "mean"}
                missing = required - set(stats)
                if missing:
                    raise ValueError(
                        f"Missing {missing} for {node_key}/{vdd_key}/{gate_name}"
                    )
                n = int(stats["n"])
                mean = float(stats["mean"])
                stddev = float(stats.get("stddev", 0.0))
                ci95 = stats.get("ci95")
                if n <= 0:
                    raise ValueError("Uncertainty sample count n must be positive")
                if mean <= 0.0:
                    raise ValueError("Uncertainty mean must be positive")
                if stddev < 0.0:
                    raise ValueError("Uncertainty stddev must be non-negative")
                gate_out[gate_name] = {
                    "n": n,
                    "mean": mean,
                    "stddev": stddev,
                    "ci95": ci95,
                }
            out[node_nm][vdd] = {"gates": gate_out}
    return out


def _uncertainty_at_node(
    uncertainty: Dict[int, Dict[float, dict]],
    node_nm: int,
    gate: str,
    v: np.ndarray,
    field: str,
) -> np.ndarray:
    table = uncertainty[node_nm]
    vols = np.array(sorted(table))
    vals = np.array([float(table[vol]["gates"][gate].get(field, 0.0)) for vol in vols])
    return np.interp(v, vols, vals)


def uncertainty_stats_vec(
    node_nm: float,
    vdd_array: Sequence[float],
    gate: str,
    uncertainty: Dict[int, Dict[float, dict]],
) -> dict:
    """Interpolate uncertainty metadata for a gate over VDD and node."""

    v = np.asanyarray(vdd_array, dtype=float)
    nodes = np.array(sorted(uncertainty))
    means = np.stack(
        [_uncertainty_at_node(uncertainty, int(n), gate, v, "mean") for n in nodes],
        axis=0,
    )
    stddevs = np.stack(
        [_uncertainty_at_node(uncertainty, int(n), gate, v, "stddev") for n in nodes],
        axis=0,
    )
    ns = np.stack(
        [_uncertainty_at_node(uncertainty, int(n), gate, v, "n") for n in nodes],
        axis=0,
    )
    mean_interp = np.array([np.interp(node_nm, nodes, means[:, i]) for i in range(v.size)])
    std_interp = np.array([np.interp(node_nm, nodes, stddevs[:, i]) for i in range(v.size)])
    n_interp = np.array([np.interp(node_nm, nodes, ns[:, i]) for i in range(v.size)])
    return {"mean": mean_interp, "stddev": std_interp, "n": n_interp}


def operation_confidence(
    code: str,
    node_nm: float,
    vdd: float,
    *,
    uncertainty_path: Path,
    word_bits: int = 64,
    max_relative_stddev: float = 0.25,
    strict_validation: bool = False,
) -> dict:
    """Return additive confidence indicators for a dynamic energy estimate."""

    uncertainty = load_calibration_uncertainty(uncertainty_path)
    primitives = primitive_counts(code, word_bits)
    weighted_mean = 0.0
    weighted_var = 0.0
    sample_counts = []
    for gate in ("xor", "and", "adder_stage"):
        stats = uncertainty_stats_vec(node_nm, np.array([vdd]), gate, uncertainty)
        mean = float(stats["mean"].item())
        stddev = float(stats["stddev"].item())
        n = int(round(float(stats["n"].item())))
        if strict_validation and n <= 0:
            raise UncertaintyValidationError(
                f"Missing uncertainty sample count for {gate} at node={node_nm}, vdd={vdd}"
            )
        weighted_mean += primitives[gate] * mean
        weighted_var += (primitives[gate] * stddev) ** 2
        sample_counts.append(n)
    combined_stddev = float(math.sqrt(weighted_var))
    if weighted_mean <= 0.0:
        relative_stddev = 0.0
    else:
        relative_stddev = combined_stddev / weighted_mean
    if strict_validation and relative_stddev > max_relative_stddev:
        raise UncertaintyValidationError(
            "Uncertainty too wide for strict validation: "
            f"relative_stddev={relative_stddev:.6f} > {max_relative_stddev:.6f}"
        )
    confidence_score = max(0.0, min(1.0, 1.0 - (relative_stddev / max_relative_stddev)))
    return {
        "uncertainty_used": True,
        "sample_count_min": int(min(sample_counts)) if sample_counts else 0,
        "relative_stddev": float(relative_stddev),
        "confidence_score": float(confidence_score),
        "confidence_threshold": float(max_relative_stddev),
    }


def _nearest(v: float, choices) -> float:
    """Return the closest value in ``choices`` to ``v``."""
    return min(choices, key=lambda c: abs(c - v))


def gate_energy(
    node_nm: float, vdd: float, gate: str, *, mode: str = "pwl"
) -> float:
    """Return interpolated energy per primitive gate operation.

    Parameters
    ----------
    node_nm : int
        Technology node in nanometres.
    vdd : float
        Supply voltage in volts.
    gate : str
        Either ``"xor"`` or ``"and"``.

    Returns
    -------
    float
        Energy in joules (J/op) for the specified primitive operation.
    """
    if gate not in {"xor", "and", "adder_stage"}:
        raise KeyError(gate)

    return gate_energy_vec(node_nm, np.array([vdd]), gate, mode=mode).item()


def gate_energy_vec(
    node_nm: float,
    vdd_array: Sequence[float],
    gate: str,
    *,
    mode: str = "pwl",
) -> np.ndarray:
    """Vectorised gate-energy lookup with node/VDD interpolation.

    Parameters
    ----------
    node_nm : int
        Technology node in nanometres.
    vdd_array : sequence of float
        Array of voltages.
    gate : str
        Either ``"xor"`` or ``"and"``.
    mode : str
        ``"pwl"`` performs piecewise-linear interpolation over calibration
        points. ``"nearest"`` uses nearest calibrated VDD/node entries.
    """
    v = np.asanyarray(vdd_array, dtype=float)
    if mode == "nearest":
        table = _CALIB[int(_nearest(node_nm, _CALIB.keys()))]
        vols = np.array(sorted(table))
        idx = np.abs(vols[:, None] - v).argmin(0)
        nearest = vols[idx]
        unique_rounds = np.unique(nearest[v != nearest])
        if unique_rounds.size:
            logging.warning("VDD rounded to nearest entry: %s", unique_rounds)
        return np.vectorize(lambda x: table[x]["gates"][gate])(nearest)

    if mode == "pwl":
        nodes = np.array(sorted(_CALIB))

        all_vols = [sorted(table) for table in _CALIB.values()]
        v_min = min(vs[0] for vs in all_vols)
        v_max = max(vs[-1] for vs in all_vols)
        if np.any((v < v_min) | (v > v_max)):
            _LOGGER.warning(
                "VDD outside calibration range; clamped to [%s, %s]", v_min, v_max
            )
            v = np.clip(v, v_min, v_max)

        def energy_at_node(n: int) -> np.ndarray:
            table = _CALIB[n]
            vols = np.array(sorted(table))
            vals = [table[vol]["gates"][gate] for vol in vols]
            return np.interp(v, vols, vals)

        energies = np.stack([energy_at_node(n) for n in nodes], axis=0)
        return np.array([np.interp(node_nm, nodes, energies[:, i]) for i in range(v.size)])

    raise ValueError("mode must be 'nearest' or 'pwl'")


def estimate_energy(
    parity_bits: int,
    detected_errors: int,
    *,
    node_nm: int = 28,
    vdd: float = 0.8,
    mux_count: int = 0,
    mux_energy_j: float | None = None,
    mux_activity: float = 1.0,
    other_energy_j: float = 0.0,
) -> float:
    """Estimate ECC dynamic energy for a read-side operation.

    Parameters
    ----------
    parity_bits : int
        Number of parity bits evaluated using XOR gates.
    detected_errors : int
        Number of detected error bits which trigger AND gate checks.

    Returns
    -------
    float
        Estimated energy in joules (``J``) computed as
        ``parity_bits * E_xor + detected_errors * E_and
        + mux_activity * mux_count * mux_energy_j + other_energy_j``.
    """
    if parity_bits < 0 or detected_errors < 0 or mux_count < 0:
        raise ValueError("Counts must be non-negative")
    if not 0.0 <= mux_activity <= 1.0:
        raise ValueError("mux_activity must be in [0, 1]")
    if other_energy_j < 0.0:
        raise ValueError("other_energy_j must be non-negative")
    if mux_count and mux_energy_j is None:
        raise ValueError("mux_energy_j is required when mux_count is non-zero")
    if mux_energy_j is not None and mux_energy_j < 0.0:
        raise ValueError("mux_energy_j must be non-negative")

    e_xor = gate_energy_vec(node_nm, np.array([vdd]), "xor", mode="pwl").item()
    e_and = gate_energy_vec(node_nm, np.array([vdd]), "and", mode="pwl").item()
    e_mux = 0.0 if mux_energy_j is None else mux_activity * mux_count * mux_energy_j
    return parity_bits * e_xor + detected_errors * e_and + e_mux + other_energy_j


def scrub_energy_kwh(
    parity_bits: int,
    capacity_gib: float,
    lifetime_h: float,
    scrub_s: float,
    *,
    node_nm: int = 28,
    vdd: float = 0.8,
    word_bits: int = 64,
) -> float:
    """Return background scrub energy in kWh.

    Parameters
    ----------
    parity_bits : int
        Parity bits evaluated during a scrub read.
    capacity_gib : float
        Memory capacity in gibibits.
    lifetime_h : float
        Operating lifetime over which scrubbing occurs.
    scrub_s : float
        Interval between scrub passes in seconds.
    node_nm : int, optional
        Technology node in nanometres.
    vdd : float, optional
        Supply voltage in volts.
    word_bits : int, optional
        Word width in bits. Defaults to 64.

    Returns
    -------
    float
        Total energy spent on background scrubbing in kilowatt-hours.
    """
    e_per_read = estimate_energy(parity_bits, 0, node_nm=node_nm, vdd=vdd)
    words = capacity_gib * (2**30 * 8) / word_bits

    if scrub_s <= 0 or lifetime_h <= 0:
        return 0.0
    if math.isnan(lifetime_h):
        return e_per_read * words / 3_600_000.0

    n_reads = (lifetime_h * 3600.0 / scrub_s) * words
    return n_reads * e_per_read / 3_600_000.0


def epc(
    xor_cnt: int,
    and_cnt: int,
    corrections: int,
    *,
    node_nm: int = 28,
    vdd: float = 0.8,
    mux_count: int = 0,
    mux_energy_j: float | None = None,
    mux_activity: float = 1.0,
    other_energy_j: float = 0.0,
) -> float:
    """Return energy per corrected bit (EPC).

    Parameters
    ----------
    xor_cnt : int
        Count of XOR operations.
    and_cnt : int
        Count of AND operations.
    corrections : int
        Number of bits corrected.

    Returns
    -------
    float
        Energy per corrected bit in joules per bit (``J/bit``):
        ``estimate_energy(xor_cnt, and_cnt) / corrections``.
    """
    if corrections <= 0:
        raise ValueError("corrections must be positive")

    total = estimate_energy(
        xor_cnt,
        and_cnt,
        node_nm=node_nm,
        vdd=vdd,
        mux_count=mux_count,
        mux_energy_j=mux_energy_j,
        mux_activity=mux_activity,
        other_energy_j=other_energy_j,
    )
    return total / corrections


# ---------------------------------------------------------------------------
# Depth models


def depth_parity(bits: int) -> int:
    """Depth of a balanced XOR tree computing parity of ``bits`` inputs."""
    if bits <= 1:
        return 0
    return int(math.ceil(math.log2(bits)))


def depth_syndrome(bits: int) -> int:
    """Depth of XOR tree for syndrome calculation."""
    return depth_parity(bits)


def depth_locator(code: str) -> int:
    """Return adder depth for the locator stage of ``code``."""
    mapping = {"sec-ded": 1, "sec-daec": 2, "taec": 3, "polar": 3}
    try:
        return mapping[code.lower()]
    except KeyError:
        raise KeyError(code)


# ---------------------------------------------------------------------------
# Leakage model


# Leakage current density reference values expressed in microamps per square
# millimetre (\u03bcA/mm^2) at 25\u00b0C. Prior revisions treated these as amps,
# greatly overstating leakage energy.
_LEAK_BASE_UA_PER_MM2 = {28: 0.5, 16: 0.7, 7: 1.0}

# Simple process-corner multipliers to allow leakage exploration.
_LEAK_CORNER_MUL = {"ss": 0.7, "tt": 1.0, "ff": 1.3}


def i_leak_density_A_per_mm2(
    node_nm: float, temp_c: float, *, corner: str = "tt"
) -> float:
    """Return leakage current density in ``A/mm^2``.

    Parameters
    ----------
    node_nm : float
        Technology node in nanometres.
    temp_c : float
        Junction temperature in degrees Celsius.
    corner : str, optional
        Process corner: ``"ss"`` (slow), ``"tt"`` (typical) or ``"ff"`` (fast).
    """

    nodes = np.array(sorted(_LEAK_BASE_UA_PER_MM2))
    base_ua = np.array([_LEAK_BASE_UA_PER_MM2[n] for n in nodes])
    base = base_ua * 1e-6  # convert \u03bcA/mm^2 to A/mm^2
    density_25 = np.interp(node_nm, nodes, base)
    try:
        mul = _LEAK_CORNER_MUL[corner.lower()]
    except KeyError:
        raise KeyError(corner)
    # Empirical temperature scaling: roughly doubles every 15\u00b0C.
    return density_25 * mul * 2 ** ((temp_c - 25.0) / 15.0)


_AREA_OVERHEAD = {"sec-ded": 0.1, "sec-daec": 0.12, "taec": 0.15, "polar": 0.17}


def area_overhead_mm2(code: str) -> float:
    try:
        return _AREA_OVERHEAD[code.lower()]
    except KeyError:
        raise KeyError(code)


def leakage_energy_j(
    vdd: float,
    node_nm: float,
    temp_c: float,
    code: str,
    lifetime_h: float,
    *,
    corner: str = "tt",
) -> float:
    i = i_leak_density_A_per_mm2(node_nm, temp_c, corner=corner)
    area = area_overhead_mm2(code)
    return vdd * i * area * (lifetime_h * 3600.0)


def mux_leakage_power_w(
    *,
    vdd: float,
    node_nm: float,
    temp_c: float,
    mux_area_mm2: float,
    corner: str = "tt",
) -> float:
    """Return MUX leakage power from the repository area-density surrogate.

    This is an analytical area-density derivation, not a cell-library leakage
    value.  ``mux_area_mm2`` must contain only the incremental ECC-internal MUX
    area so that existing logic-area proxies are not counted twice.
    """

    if mux_area_mm2 < 0.0:
        raise ValueError("mux_area_mm2 must be non-negative")
    return (
        vdd
        * i_leak_density_A_per_mm2(node_nm, temp_c, corner=corner)
        * mux_area_mm2
    )


# ---------------------------------------------------------------------------
# Dynamic energy model per ECC


_PRIMITIVE_BASE_PER_64: Dict[str, Dict[str, int]] = {
    "sec-ded": {"xor": 100, "and": 50, "adder_stage": 0},
    "sec-daec": {"xor": 120, "and": 60, "adder_stage": 10},
    "taec": {"xor": 150, "and": 70, "adder_stage": 20},
    "polar": {"xor": 180, "and": 80, "adder_stage": 24},
}


def primitive_counts(code: str, word_bits: int = 64) -> Dict[str, int]:
    """Estimate primitive gate counts for ``code`` and ``word_bits``.

    Counts scale linearly with ``word_bits`` using 64‑bit as the reference.
    """

    base = _PRIMITIVE_BASE_PER_64[code.lower()]
    scale = word_bits / 64.0
    return {k: int(math.ceil(v * scale)) for k, v in base.items()}


def dynamic_energy_per_op(
    code: str,
    node_nm: float,
    vdd: float,
    *,
    word_bits: int = 64,
    mode: str = "pwl",
    mux_count: int = 0,
    mux_energy_j: float | None = None,
    mux_activity: float = 1.0,
    other_energy_j: float = 0.0,
) -> float:
    """Energy per ECC operation in joules for one word."""

    primitives = primitive_counts(code, word_bits)
    e_xor = gate_energy(node_nm, vdd, "xor", mode=mode)
    e_and = gate_energy(node_nm, vdd, "and", mode=mode)
    e_add = gate_energy(node_nm, vdd, "adder_stage", mode=mode)
    gate_energy_total = (
        primitives["xor"] * e_xor
        + primitives["and"] * e_and
        + primitives["adder_stage"] * e_add
    )
    if mux_count < 0:
        raise ValueError("mux_count must be non-negative")
    if not 0.0 <= mux_activity <= 1.0:
        raise ValueError("mux_activity must be in [0, 1]")
    if mux_count and mux_energy_j is None:
        raise ValueError("mux_energy_j is required when mux_count is non-zero")
    if mux_energy_j is not None and mux_energy_j < 0.0:
        raise ValueError("mux_energy_j must be non-negative")
    if other_energy_j < 0.0:
        raise ValueError("other_energy_j must be non-negative")
    e_mux = 0.0 if mux_energy_j is None else mux_activity * mux_count * mux_energy_j
    return gate_energy_total + e_mux + other_energy_j


def dynamic_energy_j(
    ops: float,
    code: str,
    node_nm: float,
    vdd: float,
    *,
    word_bits: int = 64,
    mode: str = "pwl",
    mux_count: int = 0,
    mux_energy_j: float | None = None,
    mux_activity: float = 1.0,
    other_energy_j: float = 0.0,
) -> float:
    """Total dynamic energy for ``ops`` ECC operations."""

    return ops * dynamic_energy_per_op(
        code,
        node_nm,
        vdd,
        word_bits=word_bits,
        mode=mode,
        mux_count=mux_count,
        mux_energy_j=mux_energy_j,
        mux_activity=mux_activity,
        other_energy_j=other_energy_j,
    )


def energy_report(
    code: str,
    node_nm: float,
    vdd: float,
    temp_c: float,
    ops: float,
    lifetime_h: float,
    *,
    word_bits: int = 64,
    corner: str = "tt",
    mode: str = "pwl",
    uncertainty_path: Path | None = None,
    include_confidence: bool = False,
    strict_validation: bool = False,
    max_relative_stddev: float = 0.25,
    strict_sanity: bool = False,
) -> Dict[str, float]:
    dyn = dynamic_energy_j(ops, code, node_nm, vdd, word_bits=word_bits, mode=mode)
    leak = leakage_energy_j(vdd, node_nm, temp_c, code, lifetime_h, corner=corner)
    result = {"dynamic_J": dyn, "leakage_J": leak, "total_J": dyn + leak}
    sanity_warnings = []
    sanity_warnings.extend(
        validate_operating_point(
            _CALIB,
            node_nm=node_nm,
            vdd=vdd,
        )
    )
    sanity_warnings.extend(
        validate_metric_non_negative(
            {"dynamic_J": dyn, "leakage_J": leak, "total_J": dyn + leak},
            context={"node": node_nm, "vdd": vdd, "gate": code},
        )
    )
    enforce_sanity(sanity_warnings, strict=strict_sanity)
    if sanity_warnings:
        result["sanity_warnings"] = sanity_warnings
    if include_confidence or strict_validation:
        if uncertainty_path is None:
            if strict_validation:
                raise UncertaintyValidationError(
                    "Strict validation requires uncertainty metadata path"
                )
            return result
        result["confidence"] = operation_confidence(
            code,
            node_nm,
            vdd,
            uncertainty_path=uncertainty_path,
            word_bits=word_bits,
            strict_validation=strict_validation,
            max_relative_stddev=max_relative_stddev,
        )
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Estimate energy per read")
    parser.add_argument("parity_bits", type=int, help="Number of parity bits")
    parser.add_argument(
        "detected_errors", type=int, nargs="?", default=0,
        help="Number of detected error bits (default: 0)"
    )
    parser.add_argument("--node", type=int, default=28, help="Process node in nm")
    parser.add_argument("--vdd", type=float, default=0.8, help="Supply voltage")
    args = parser.parse_args()

    energy = estimate_energy(
        args.parity_bits,
        args.detected_errors,
        node_nm=args.node,
        vdd=args.vdd,
    )
    print(f"Estimated energy per read: {energy:.3e} J")
