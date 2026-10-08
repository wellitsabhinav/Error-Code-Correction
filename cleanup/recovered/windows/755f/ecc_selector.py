"""Multi-objective ECC selector.

The :func:`select` helper evaluates a set of ECC codes under a common
scenario and returns a recommendation together with the Pareto optimal
frontier.  The frontier is determined with respect to ``FIT`` (failures in
time), total ``carbon_kg`` and ``latency_ns`` – all of which are minimised.

Only a very small subset of ECC codes is modelled.  The implementation is
light‑weight and trades accuracy for clarity; it is sufficient for unit tests
and for demonstrating the selection flow used by :mod:`eccsim`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Tuple

import argparse
import sys
from pathlib import Path

import logging

import hashlib
import json
import math

from carbon import embodied_kgco2e, operational_kgco2e, default_alpha
from carbon_model import estimate_carbon_bounds
from ecc_mux import compute_ecc_mux_characterization
from energy_model import mux_leakage_power_w, scrub_energy_kwh
from esii import ESIIInputs, compute_esii, normalise_esii
from fit import (
    compute_fit_pre,
    compute_fit_post,
    ecc_coverage_factory,
    fit_system,
)
from mbu import pmf_adjacent
from qcrit_loader import qcrit_lookup
from ser_model import HazuchaParams, ser_hazucha, flux_from_location
from gs import GSInputs, compute_gs
from analysis.knee import max_perp_norm
from analysis.hv import hypervolume, schott_spacing


# ---------------------------------------------------------------------------
# Simplified technology characterisation for supported ECC codes.  The values
# are deliberately approximate – they merely provide ordering for the unit
# tests and examples.


@dataclass(frozen=True)
class _CodeInfo:
    family: str
    parity_bits: int
    latency_ns: float
    area_logic_mm2: float
    word_bits: int = 64
    notes: str = ""


_CODE_DB: Dict[str, _CodeInfo] = {
    "sec-ded-64": _CodeInfo("SEC-DED", parity_bits=8, latency_ns=1.0, area_logic_mm2=1.0),
    "sec-daec-64": _CodeInfo(
        "SEC-DAEC", parity_bits=9, latency_ns=1.3, area_logic_mm2=1.2
    ),
    "taec-64": _CodeInfo("TAEC", parity_bits=11, latency_ns=1.6, area_logic_mm2=1.5),
    "bch-63": _CodeInfo(
        "BCH", parity_bits=12, latency_ns=2.4, area_logic_mm2=2.1, notes="BCH(63,51,2)"
    ),
    "polar-64-32": _CodeInfo(
        "POLAR-64-32",
        parity_bits=32,
        latency_ns=2.2,
        area_logic_mm2=2.0,
        word_bits=64,
        notes="Polar (N=64, K=32) SC decoder",
    ),
    "polar-64-48": _CodeInfo(
        "POLAR-64-48",
        parity_bits=16,
        latency_ns=2.0,
        area_logic_mm2=1.8,
        word_bits=64,
        notes="Polar (N=64, K=48) SC decoder",
    ),
    "polar-128-96": _CodeInfo(
        "POLAR-128-96",
        parity_bits=32,
        latency_ns=2.6,
        area_logic_mm2=2.4,
        word_bits=128,
        notes="Polar (N=128, K=96) SC decoder",
    ),
}


_ECC_MUX_SCHEME = {
    "SEC-DED": "Hamming_SEC",
    "SEC-DAEC": "SEC_DAEC",
    "TAEC": "TAEC",
    "BCH": "BCH",
}


def _parity_bits_secded(word_bits: int) -> int:
    p = 1
    while (2**p) < (word_bits + p + 1):
        p += 1
    return p + 1


def _parity_bits_taec(word_bits: int) -> int:
    patterns = 1 + word_bits + max(0, word_bits - 1) + max(0, word_bits - 2)
    p = 1
    while (2**p) < patterns:
        p += 1
    return p


def _parity_bits_bch(word_bits: int) -> int:
    patterns = 1 + word_bits + (word_bits * max(0, word_bits - 1) // 2)
    p = 1
    while (2**p) < patterns:
        p += 1
    return p


for _wb in (8, 16, 32):
    _CODE_DB[f"sram-secded-{_wb}"] = _CodeInfo(
        "SEC-DED",
        parity_bits=_parity_bits_secded(_wb),
        latency_ns=0.85 + 0.02 * (_wb / 8),
        area_logic_mm2=0.45 + 0.05 * (_wb / 8),
        word_bits=_wb,
        notes=f"SRAM SEC-DED ({_wb}-bit word)",
    )
    _CODE_DB[f"sram-taec-{_wb}"] = _CodeInfo(
        "TAEC",
        parity_bits=_parity_bits_taec(_wb),
        latency_ns=1.1 + 0.05 * (_wb / 8),
        area_logic_mm2=0.60 + 0.08 * (_wb / 8),
        word_bits=_wb,
        notes=f"SRAM TAEC ({_wb}-bit word)",
    )
    _CODE_DB[f"sram-bch-{_wb}"] = _CodeInfo(
        "BCH",
        parity_bits=_parity_bits_bch(_wb),
        latency_ns=1.4 + 0.08 * (_wb / 8),
        area_logic_mm2=0.85 + 0.11 * (_wb / 8),
        word_bits=_wb,
        notes=f"SRAM BCH ({_wb}-bit word)",
    )
    _CODE_DB[f"sram-polar-{_wb}"] = _CodeInfo(
        "POLAR",
        parity_bits=max(1, _wb // 2),
        latency_ns=1.35 + 0.07 * (_wb / 8),
        area_logic_mm2=0.78 + 0.10 * (_wb / 8),
        word_bits=_wb,
        notes=f"SRAM Polar ({_wb}-bit word)",
    )


# ---------------------------------------------------------------------------
# Pareto helpers


_PARETO_EPS = 1e-8


_log = logging.getLogger(__name__)
_logged_fallback = False
_logged_degenerate = False
_carbon_cap_warned = False
_degenerate_warned = {"carbon": False, "latency": False}


def _pareto_front(
    records: Iterable[Mapping[str, float]], eps: float = _PARETO_EPS
) -> List[Dict[str, float]]:
    """Return the Pareto frontier of ``records`` using ε-dominance.

    The comparison operates on min–max normalised axes with a small epsilon to
    avoid floating point jitter.  The returned list is sorted by the ``code``
    field for stable output.
    """

    recs = list(records)
    if not recs:
        return []

    keys = ("FIT", "carbon_kg", "latency_ns")
    mins = {k: min(r[k] for r in recs) for k in keys}
    maxs = {k: max(r[k] for r in recs) for k in keys}

    def norm(k: str, v: float) -> float:
        span = maxs[k] - mins[k]
        if span <= 0:
            return 0.0
        return (v - mins[k]) / span

      
    frontier: List[Dict[str, float]] = []
    for rec in recs:
        dominated = False
        for other in recs:
            if other is rec:
                continue
            le = all(norm(k, other[k]) <= norm(k, rec[k]) + eps for k in keys)
            lt = any(norm(k, other[k]) < norm(k, rec[k]) - eps for k in keys)
            if le and lt:
                dominated = True
                break
        if not dominated:
            frontier.append(dict(rec))

    frontier.sort(key=lambda r: r["code"])
    return frontier


def _nsga2_sort(
    recs: List[Dict[str, float]],
) -> Tuple[List[List[int]], Dict[int, float], Dict[str, float], Dict[str, float], Dict[int, Dict[str, float]]]:
    """Return NSGA-II fronts and crowding distances on normalised axes."""

    if not recs:
        return [], {}, {}, {}, {}

    keys = ("FIT", "carbon_kg", "latency_ns")

    mins = {k: min(r[k] for r in recs) for k in keys}
    maxs = {k: max(r[k] for r in recs) for k in keys}

    def norm(idx: int, key: str) -> float:
        span = maxs[key] - mins[key]
        if span <= 0:
            return 0.0
        return (recs[idx][key] - mins[key]) / span

    # Non-dominated sorting
    S: List[List[int]] = [[] for _ in recs]
    n = [0 for _ in recs]
    fronts: List[List[int]] = [[]]

    def dominates(p: Dict[str, float], q: Dict[str, float]) -> bool:
        return all(p[k] <= q[k] for k in keys) and any(p[k] < q[k] for k in keys)

    for i, p in enumerate(recs):
        for j, q in enumerate(recs):
            if i == j:
                continue
            if dominates(p, q):
                S[i].append(j)
            elif dominates(q, p):
                n[i] += 1
        if n[i] == 0:
            fronts[0].append(i)

    i = 0
    while fronts[i]:
        next_front: List[int] = []
        for p_idx in fronts[i]:
            for q_idx in S[p_idx]:
                n[q_idx] -= 1
                if n[q_idx] == 0:
                    next_front.append(q_idx)
        i += 1
        fronts.append(next_front)

    # Crowding distance on normalised axes
    crowd = {idx: 0.0 for idx in range(len(recs))}
    norm_vals: Dict[int, Dict[str, float]] = {
        i: {k: norm(i, k) for k in keys} for i in range(len(recs))
    }
    for front in fronts:
        if not front:
            continue
        for key in keys:
            sorted_f = sorted(front, key=lambda idx: norm_vals[idx][key])
            crowd[sorted_f[0]] = crowd[sorted_f[-1]] = float("inf")
            for k in range(1, len(sorted_f) - 1):
                prev_val = norm_vals[sorted_f[k - 1]][key]
                next_val = norm_vals[sorted_f[k + 1]][key]
                crowd[sorted_f[k]] += next_val - prev_val
    return fronts, crowd, mins, maxs, norm_vals


# ---------------------------------------------------------------------------
# GS helpers


def _percentile(values: List[float], pct: float) -> float:
    vs = sorted(values)
    if not vs:
        return 0.0
    k = (len(vs) - 1) * pct / 100.0
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return vs[int(k)]
    return vs[f] * (c - k) + vs[c] * (k - f)


def _annotate_gs(recs: List[Dict[str, float]], weights: Tuple[float, float, float]) -> None:
    global _carbon_cap_warned
    carbon_vals = [r["carbon_kg"] for r in recs]
    if len(carbon_vals) < 5:
        cap = max(carbon_vals)
        if not _carbon_cap_warned:
            _log.warning("carbon cap fallback to max for N<5")
            _carbon_cap_warned = True
    else:
        cap = _percentile(carbon_vals, 95)
    carbon_clipped = [min(v, cap) for v in carbon_vals]
    c_span = max(carbon_clipped) - min(carbon_clipped)
    if c_span <= max(1.0, cap) * 1e-9 and not _degenerate_warned["carbon"]:
        _log.warning("carbon values nearly identical; treating as neutral")
        _degenerate_warned["carbon"] = True
        carbon_clipped = [0.0 for _ in carbon_clipped]

    lat_vals = [r["latency_ns"] for r in recs]
    l_span = max(lat_vals) - min(lat_vals)
    if l_span <= max(1.0, max(lat_vals)) * 1e-9 and not _degenerate_warned["latency"]:
        _log.warning("latency values nearly identical; treating as neutral")
        _degenerate_warned["latency"] = True
        lat_vals = [r.get("latency_base_ns", 0.0) for r in recs]

    for rec, c_val, l_val in zip(recs, carbon_clipped, lat_vals):
        inp = GSInputs(
            fit_base=rec["fit_base"],
            fit_ecc=rec["FIT"],
            carbon_kg=c_val,
            latency_ns=l_val,
            latency_base_ns=rec.get("latency_base_ns", 0.0),
        )
        gs_res = compute_gs(inp, weights=weights)
        rec["GS"] = gs_res["GS"]
        rec["Sr"] = gs_res["Sr"]
        rec["Sc"] = gs_res["Sc"]
        rec["Sl"] = gs_res["Sl"]


# ---------------------------------------------------------------------------
# Selection logic


def _compute_metrics(
    code: str,
    *,
    node: int,
    vdd: float,
    temp: float,
    ci: float,
    capacity_gib: float,
    bitcell_um2: float,
    alt_km: float,
    latitude_deg: float,
    flux_rel: float | None,
    mbu: str,
    scrub_s: float,
    lifetime_h: float = float("nan"),
    include_mux_overhead: bool = False,
    mux_activity: float = 1.0,
    mux_energy_scale: float = 1.0,
    mux_depth_delta: int = 0,
) -> Dict[str, float | str]:
    """Return metric record for ``code`` under the specified scenario."""

    info = _CODE_DB[code]

    # --- Reliability -----------------------------------------------------
    try:
        qcrit_fC = qcrit_lookup("sram6t", node, vdd, temp, 50)
        area_um2 = bitcell_um2
    except Exception:  # pragma: no cover - defensive fallback
        qcrit_fC = 0.3
        area_um2 = bitcell_um2

    flux = flux_from_location(alt_km, latitude_deg, flux_rel)
    hp = HazuchaParams(Qs_fC=0.05, flux_rel=flux, area_um2=area_um2)
    fit_bit = ser_hazucha(qcrit_fC, hp)

    word_bits = info.word_bits
    mbu_dist = pmf_adjacent(mbu, word_bits=word_bits, bitline_bits=word_bits)
    severity_scale = {"light": 0.0, "moderate": 1.0, "heavy": 5.0}.get(mbu, 1.0)
    # Scale probabilities to FIT rates; the multiplier ensures MBUs have a
    # noticeable impact on the final metric.
    mbu_rates = {
        k: {kind: fit_bit * word_bits * k * p * severity_scale for kind, p in probs.items()}
        for k, probs in mbu_dist.items()
    }

    fit_pre = compute_fit_pre(word_bits, fit_bit, mbu_rates)
    ecc_cov = ecc_coverage_factory(info.family, word_bits=word_bits)
    fit_post = compute_fit_post(word_bits, fit_bit, mbu_rates, ecc_cov, scrub_s)

    fit_base_sys = fit_system(capacity_gib, fit_pre.nominal)
    fit_post_sys = fit_system(capacity_gib, fit_post.nominal)

    # --- Energy & Carbon -------------------------------------------------
    words = capacity_gib * (2**30 * 8) / word_bits
    e_scrub_base_kwh = scrub_energy_kwh(
        info.parity_bits,
        capacity_gib,
        lifetime_h,
        scrub_s,
        node_nm=node,
        vdd=vdd,
        word_bits=word_bits,
    )
    e_scrub_kwh = e_scrub_base_kwh
    e_dyn = 0.0
    e_leak = 0.0
    mux_details: Dict[str, float | int | str | bool | None] = {}

    mux_area_mm2 = 0.0
    mux_latency_ns = 0.0
    if include_mux_overhead:
        if not 0.0 <= mux_activity <= 1.0:
            raise ValueError("mux_activity must be in [0, 1]")
        if mux_energy_scale < 0.0:
            raise ValueError("mux_energy_scale must be non-negative")
        try:
            mux_scheme = _ECC_MUX_SCHEME[info.family]
        except KeyError as exc:
            raise ValueError(
                f"MUX overhead is unavailable/TBD for ECC family {info.family!r}"
            ) from exc

        mux_char = compute_ecc_mux_characterization(mux_scheme, node)
        mux_count = mux_char.equivalent_mux2_count
        mux_depth = max(1, mux_char.mux_depth + int(mux_depth_delta))
        mux_latency_ns = mux_depth * mux_char.per_stage_delay_ns
        mux_area_mm2 = mux_char.aggregate_area_um2 * 1e-6

        if math.isnan(lifetime_h):
            mux_reads = words
            mux_leakage_j = 0.0
        elif scrub_s > 0.0 and lifetime_h > 0.0:
            mux_reads = (lifetime_h * 3600.0 / scrub_s) * words
            mux_leakage_j = (
                mux_leakage_power_w(
                    vdd=vdd,
                    node_nm=node,
                    temp_c=temp,
                    mux_area_mm2=mux_area_mm2,
                )
                * lifetime_h
                * 3600.0
            )
        else:
            mux_reads = 0.0
            mux_leakage_j = 0.0

        # The aggregate table value is normalised to equivalent 2:1 units so
        # that alpha*N*E exactly recovers the original repository assumption.
        mux_energy_per_read_j = (
            mux_activity
            * mux_count
            * mux_char.energy_per_mux2_pj
            * mux_energy_scale
            * 1e-12
        )
        mux_scrub_kwh = mux_energy_per_read_j * mux_reads / 3_600_000.0
        e_scrub_kwh += mux_scrub_kwh
        e_leak = mux_leakage_j
        mux_details = {
            "mux_model_included": True,
            "mux_scheme": mux_scheme,
            "mux_source": mux_char.source,
            "mux_vdd_characterization": "unavailable/TBD; repository lookup has no VDD dimension",
            "mux_count_2to1": mux_count,
            "mux_fanin": mux_char.fanin,
            "mux_depth": mux_depth,
            "mux_depth_nominal": mux_char.mux_depth,
            "mux_latency_ns": mux_latency_ns,
            "mux_area_mm2": mux_area_mm2,
            "mux_energy_per_2to1_pj": mux_char.energy_per_mux2_pj * mux_energy_scale,
            "mux_energy_per_scrub_read_j": mux_energy_per_read_j,
            "mux_scrub_energy_kWh": mux_scrub_kwh,
            "mux_leakage_energy_kWh": mux_leakage_j / 3_600_000.0,
            "mux_activity": mux_activity,
            "mux_energy_scale": mux_energy_scale,
            "mux_depth_delta": int(mux_depth_delta),
        }

    e_scrub = e_scrub_kwh * 3_600_000.0

    try:
        alpha_logic, alpha_macro = default_alpha(node)
    except ValueError as exc:
        raise ValueError(f"{exc}. Unable to estimate embodied carbon.") from exc
    area_macro_mm2 = info.parity_bits * words * bitcell_um2 / 1e6
    area_logic_mm2 = info.area_logic_mm2 + mux_area_mm2
    embodied = embodied_kgco2e(
        area_logic_mm2, area_macro_mm2, alpha_logic, alpha_macro
    )
    operational = operational_kgco2e(
        e_dyn / 3_600_000.0, e_leak / 3_600_000.0, ci, e_scrub_kwh
    )
    carbon_total = embodied + operational

    esii_inp = ESIIInputs(
        fit_base=fit_base_sys,
        fit_ecc=fit_post_sys,
        e_dyn=e_dyn,
        e_leak=e_leak,
        e_scrub=e_scrub,
        ci_kgco2e_per_kwh=ci,
        embodied_kgco2e=embodied,
        basis="system",
    )
    esii = compute_esii(esii_inp)["ESII"]

    return {
        "code": code,
        "FIT": fit_post_sys,
        "fit_base": fit_base_sys,
        "ESII": esii,
        "carbon_kg": carbon_total,
        "E_dyn_kWh": e_dyn / 3_600_000.0,
        "E_leak_kWh": e_leak / 3_600_000.0,
        "E_scrub_kWh": e_scrub_kwh,
        "latency_ns": info.latency_ns + mux_latency_ns,
        "latency_base_ns": 0.0,
        "area_logic_mm2": area_logic_mm2,
        "area_macro_mm2": area_macro_mm2,
        "notes": info.notes,
        "includes_scrub_energy": True,
        "fit_bit": fit_bit,
        "fit_word_post": fit_post.nominal,
        "flux_rel": flux,
        **mux_details,
    }


def select(
    codes: Iterable[str],
    *,
    weights: Mapping[str, float] | None = None,
    constraints: Mapping[str, float | None] | None = None,
    backend: str = "hazucha",
    mbu: str = "moderate",
    scrub_s: float = 10.0,
    alt_km: float = 0.0,
    latitude_deg: float = 45.0,
    flux_rel: float | None = None,
    carbon_policy: str | None = None,
    include_mux_overhead: bool = False,
    mux_activity: float = 1.0,
    mux_energy_scale: float = 1.0,
    mux_depth_delta: int = 0,
    **kwargs,
) -> Dict[str, object]:
    """Return a recommended ECC and the Pareto frontier.

    Parameters
    ----------
    codes:
        Iterable of code identifiers such as ``"sec-ded-64"``.
    weights:
        Mapping specifying ``reliability``, ``carbon`` and ``latency``
        weights used for scalarisation.  Defaults to ``{1.0, 1.0, 0.25}``.
    constraints:
        Optional ``{"latency_ns_max": ..., "carbon_kg_max": ...}`` limits.
    backend:
        Reliability backend – currently only ``"hazucha"`` is supported.
    mbu:
        Multi-bit upset severity preset.
    scrub_s:
        Scrub interval in seconds.
    **kwargs:
        Additional parameters forwarded to the metric computation such as
        ``node``, ``vdd`` and ``temp``.  Location specific parameters
        (``alt_km``, ``latitude_deg`` and ``flux_rel``) are exposed explicitly
        to allow scenarios to model installation sites.
    """

    if backend != "hazucha":  # pragma: no cover - defensive programming
        raise ValueError("Only 'hazucha' backend supported")

    # ``weights`` are retained for backwards compatibility but ignored by the
    # NSGA-II based recommendation logic.  Supplying them no longer influences
    # the outcome but allows existing callers to remain unchanged.
    weights = dict({"reliability": 1.0, "carbon": 1.0, "latency": 0.25}, **(weights or {}))
    constraints = dict({"latency_ns_max": None, "carbon_kg_max": None}, **(constraints or {}))

    required = {"node", "vdd", "temp", "capacity_gib", "ci", "bitcell_um2"}
    missing = required - kwargs.keys()
    if missing:
        raise ValueError(f"Missing required parameters: {sorted(missing)}")

    # Compute metrics for each candidate and apply constraints
    recs = []
    for code in codes:
        if code not in _CODE_DB:
            raise KeyError(code)
        rec = _compute_metrics(
            code,
            node=int(kwargs["node"]),
            vdd=float(kwargs["vdd"]),
            temp=float(kwargs["temp"]),
            ci=float(kwargs["ci"]),
            capacity_gib=float(kwargs["capacity_gib"]),
            bitcell_um2=float(kwargs["bitcell_um2"]),
            alt_km=float(alt_km),
            latitude_deg=float(latitude_deg),
            flux_rel=float(flux_rel) if flux_rel is not None else None,
            mbu=mbu,
            scrub_s=float(scrub_s),
            lifetime_h=float(kwargs.get("lifetime_h", float("nan"))),
            include_mux_overhead=bool(include_mux_overhead),
            mux_activity=float(mux_activity),
            mux_energy_scale=float(mux_energy_scale),
            mux_depth_delta=int(mux_depth_delta),
        )

        violations = []
        lat_max = constraints.get("latency_ns_max")
        if lat_max is not None and rec["latency_ns"] > lat_max:
            violations.append("latency_ns_max")
        carbon_max = constraints.get("carbon_kg_max")
        if carbon_max is not None and rec["carbon_kg"] > carbon_max:
            violations.append("carbon_kg_max")
        if violations:
            continue
        rec["violations"] = violations

        recs.append(rec)

        if carbon_policy:
            carbon_bounds = estimate_carbon_bounds(
                node_nm=int(kwargs["node"]),
                area_cm2=(float(rec["area_logic_mm2"]) + float(rec["area_macro_mm2"])) * 0.01,
                energy_joules=(float(rec["E_dyn_kWh"]) + float(rec["E_leak_kWh"]) + float(rec["E_scrub_kWh"])) * 3_600_000.0,
                grid_factor_kgco2e_per_kwh=float(kwargs["ci"]),
                lifetime_energy_joules=(float(rec["E_dyn_kWh"]) + float(rec["E_leak_kWh"]) + float(rec["E_scrub_kWh"])) * 3_600_000.0,
            )
            rec["static_carbon_kgco2e"] = carbon_bounds["nominal"]["static_carbon_kgco2e"]
            rec["dynamic_carbon_kgco2e"] = carbon_bounds["nominal"]["dynamic_carbon_kgco2e"]
            rec["carbon_bounds"] = carbon_bounds

    scenario = dict(kwargs)
    scenario.update(
        {
            "mbu": mbu,
            "scrub_s": float(scrub_s),
            "alt_km": float(alt_km),
            "latitude_deg": float(latitude_deg),
            "flux_rel": float(flux_rel) if flux_rel is not None else None,
        }
    )
    if include_mux_overhead:
        scenario.update(
            {
                "include_mux_overhead": True,
                "mux_activity": float(mux_activity),
                "mux_energy_scale": float(mux_energy_scale),
                "mux_depth_delta": int(mux_depth_delta),
            }
        )
    scenario_hash = hashlib.sha1(
        json.dumps(scenario, sort_keys=True).encode()
    ).hexdigest()

    if not recs:
        norm_meta = {
            "method": "winsor",
            "p5": float("nan"),
            "p95": float("nan"),
            "N": 0,
            "scope": "feasible_set",
        }
        return {
            "best": None,
            "pareto": [],
            "normalization": norm_meta,
            "candidates": list(codes),
            "candidate_records": [],
            "scenario_hash": scenario_hash,
        }

    _annotate_gs(recs, (0.6, 0.3, 0.1))

    # Normalise ESII across candidates; fall back deterministically if needed
    esii_vals = [r["ESII"] for r in recs]
    N = len(esii_vals)
    scores, p5, p95 = normalise_esii(esii_vals)
    method = "winsor"
    status = "ok"
    if N < 20 or math.isclose(p5, p95):
        global _logged_fallback
        if not _logged_fallback:
            _log.warning("NESII normalization fallback to min-max")
            _logged_fallback = True
        method = "minmax"
        p5 = min(esii_vals)
        p95 = max(esii_vals)
        span = p95 - p5
        if span <= 0:
            global _logged_degenerate
            if not _logged_degenerate:
                _log.warning("NESII degenerate scale; forcing score 50")
                _logged_degenerate = True
            scores = [50.0 for _ in esii_vals]
            status = "degenerate_scale"
        else:
            scores = [100.0 * (v - p5) / span for v in esii_vals]


    for rec, score in zip(recs, scores):
        rec["NESII"] = score
        rec["p5"] = p5
        rec["p95"] = p95
        rec["N_scale"] = N
        rec["scrub_s"] = float(scrub_s)


    basis = "system"
    lifetime_h = float(kwargs.get("lifetime_h", float("nan")))
    ci_source = kwargs.get("ci_source", "unspecified")

    norm_meta = {
        "method": method,
        "p5": p5,
        "p95": p95,
        "N": N,
        "scope": "feasible_set",

        "epsilon_on_normalized_axes": _PARETO_EPS,
        "basis": basis,
        "lifetime_h": lifetime_h,
        "ci_kg_per_kwh": float(kwargs["ci"]),
        "ci_source": ci_source,

    }
    if status != "ok":
        norm_meta["status"] = status

    # NSGA-II ranking
    fronts, crowd, mins, maxs, norm_vals = _nsga2_sort(recs)
    front_rank = {}
    for rank, f in enumerate(fronts):
        for idx in f:
            front_rank[idx] = rank
    for idx, rec in enumerate(recs):
        rec["front_rank"] = front_rank.get(idx, math.inf)
        rec["crowding"] = crowd.get(idx, 0.0)

    pareto_enum = _pareto_front(recs)
    f1 = [recs[i] for i in fronts[0]] if fronts else []
    f1.sort(key=lambda r: r["code"])
    evo_miss = {r["code"] for r in pareto_enum} != {r["code"] for r in f1}

    # Decision rule ------------------------------------------------------
    fit_max = constraints.get("fit_max")
    lat_max = constraints.get("latency_ns_max")
    carbon_max = constraints.get("carbon_kg_max")

    decision_mode = "knee"
    decision_params = {
        "fit_max": fit_max,
        "latency_max": lat_max,
        "carbon_max": carbon_max,
    }
    knee_index: int | None = None
    knee_distance: float | None = None

    feasible = [
        r
        for r in recs
        if (fit_max is None or r["FIT"] <= fit_max)
        and (lat_max is None or r["latency_ns"] <= lat_max)
    ]

    selected_policy = (carbon_policy or "").strip().lower()
    if selected_policy:
        decision_mode = "carbon-policy"
        policy_candidates = feasible if feasible else recs
        if selected_policy == "minimum_total_carbon":
            best = min(policy_candidates, key=lambda r: (r["carbon_kg"], -r["NESII"]))
        elif selected_policy == "minimum_dynamic_carbon":
            best = min(policy_candidates, key=lambda r: (r["dynamic_carbon_kgco2e"], r["carbon_kg"]))
        elif selected_policy == "minimum_static_carbon":
            best = min(policy_candidates, key=lambda r: (r["static_carbon_kgco2e"], r["carbon_kg"]))
        elif selected_policy == "balanced_carbon_energy":
            tot_vals = [float(r["carbon_kg"]) for r in policy_candidates]
            en_vals = [float(r["E_dyn_kWh"]) + float(r["E_leak_kWh"]) + float(r["E_scrub_kWh"]) for r in policy_candidates]

            def _norm(vals: list[float], x: float) -> float:
                lo = min(vals)
                hi = max(vals)
                if hi <= lo:
                    return 0.0
                return (x - lo) / (hi - lo)

            best = min(
                policy_candidates,
                key=lambda r: (
                    0.5 * _norm(tot_vals, float(r["carbon_kg"]))
                    + 0.5 * _norm(en_vals, float(r["E_dyn_kWh"]) + float(r["E_leak_kWh"]) + float(r["E_scrub_kWh"])),
                    -float(r["NESII"]),
                ),
            )
        else:
            raise ValueError(
                "carbon_policy must be one of: minimum_total_carbon, minimum_dynamic_carbon, minimum_static_carbon, balanced_carbon_energy"
            )
    elif fit_max is not None or lat_max is not None:
        decision_mode = "epsilon-constraint"
        if feasible:
            best = min(feasible, key=lambda r: (r["carbon_kg"], -r["NESII"]))
        else:
            best = min(recs, key=lambda r: (r["carbon_kg"], -r["NESII"]))
    else:
        if fronts and fronts[0]:
            front_records = [recs[i] for i in fronts[0]]
            k_idx, knee_distance = max_perp_norm(front_records)
            best = front_records[k_idx]
            knee_index = f1.index(best)
            nesii_best = max(f1, key=lambda r: r["NESII"]) if f1 else best
            if nesii_best["NESII"] > best["NESII"]:
                best = nesii_best
        else:
            best = recs[0]

    # Frontier quality metrics
    f1_pts = [
        (
            norm_vals[i]["FIT"],
            norm_vals[i]["carbon_kg"],
            norm_vals[i]["latency_ns"],
        )
        for i in fronts[0]
    ] if fronts else []
    hv = hypervolume(f1_pts)
    spacing = schott_spacing(f1_pts)

    cand_hash = hashlib.sha1(",".join(sorted(codes)).encode()).hexdigest()
    seed = int(
        hashlib.sha1((scenario_hash + cand_hash).encode()).hexdigest(), 16
    ) & 0xFFFFFFFF

    nsga_meta = {
        "pop": 64,
        "gens": 64,
        "pc": 0.9,
        "pm": 0.1,
        "seed": seed,
        "deb_constraint_domination": True,
        "crowding_bounds": {"mins": mins, "maxs": maxs},
        "constraints_active": [k for k, v in constraints.items() if v is not None],
        "evolutionary_frontier_miss": evo_miss,
    }

    decision_meta: Dict[str, object] = {"mode": decision_mode, "params": decision_params}
    if knee_index is not None and knee_distance is not None:
        decision_meta.update(
            {
                "knee_index": knee_index,
                "knee_distance": knee_distance,
                "knee_method": "max-perp-normalized",
            }
        )

    quality = {"hypervolume": hv, "spacing": spacing, "ref_point_norm": [1.0, 1.0, 1.0]}

    return {
        "best": best,
        "pareto": f1,
        "normalization": norm_meta,
        "candidates": list(codes),
        "candidate_records": recs,
        "scenario_hash": scenario_hash,
        "includes_scrub_energy": True,
        "quality": quality,
        "nsga2": nsga_meta,
        "decision": decision_meta,
    }


def _record_passes_constraints(rec: Mapping[str, object], constraints: Mapping[str, float | None]) -> bool:
    fit_max = constraints.get("fit_max")
    lat_max = constraints.get("latency_ns_max")
    carbon_max = constraints.get("carbon_kg_max")
    if fit_max is not None and float(rec.get("FIT", float("inf"))) > float(fit_max):
        return False
    if lat_max is not None and float(rec.get("latency_ns", float("inf"))) > float(lat_max):
        return False
    if carbon_max is not None and float(rec.get("carbon_kg", float("inf"))) > float(carbon_max):
        return False
    return True


def _constraint_audit(rec: Mapping[str, object] | None, constraints: Mapping[str, float | None]) -> dict[str, bool | None]:
    if rec is None:
        return {
            "fit_max": None,
            "latency_ns_max": None,
            "carbon_kg_max": None,
            "all_pass": None,
        }

    fit_max = constraints.get("fit_max")
    lat_max = constraints.get("latency_ns_max")
    carbon_max = constraints.get("carbon_kg_max")
    checks = {
        "fit_max": True if fit_max is None else float(rec.get("FIT", float("inf"))) <= float(fit_max),
        "latency_ns_max": True if lat_max is None else float(rec.get("latency_ns", float("inf"))) <= float(lat_max),
        "carbon_kg_max": True if carbon_max is None else float(rec.get("carbon_kg", float("inf"))) <= float(carbon_max),
    }
    checks["all_pass"] = bool(checks["fit_max"] and checks["latency_ns_max"] and checks["carbon_kg_max"])
    return checks


def _baseline_choice(result: Mapping[str, object], feasible: list[dict[str, object]]) -> dict[str, object] | None:
    best = result.get("best")
    if isinstance(best, dict) and any(r.get("code") == best.get("code") for r in feasible):
        return best
    if feasible:
        return min(
            feasible,
            key=lambda r: (float(r.get("carbon_kg", float("inf"))), -float(r.get("NESII", 0.0))),
        )
    if isinstance(best, dict):
        return best
    return None


def _selector_args_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Optional ML-assisted ECC selector")
    parser.add_argument("--ml-model", type=Path, default=None, help="Path to trained ML model directory")
    parser.add_argument("--interactive", action="store_true", help="Prompt for missing inputs and optional sweeps")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")

    parser.add_argument("--codes", type=str, default="sec-ded-64,sec-daec-64,taec-64,bch-63")

    parser.add_argument("--node", type=int, default=None)
    parser.add_argument("--vdd", type=float, default=None)
    parser.add_argument("--temp", type=float, default=None)
    parser.add_argument("--capacity-gib", type=float, default=None)
    parser.add_argument("--ci", type=float, default=None)
    parser.add_argument("--bitcell-um2", type=float, default=None)

    parser.add_argument("--mbu", type=str, default="moderate")
    parser.add_argument("--scrub-s", type=float, default=None)
    parser.add_argument("--alt-km", type=float, default=None)
    parser.add_argument("--latitude", type=float, default=None)
    parser.add_argument("--flux-rel", type=float, default=None)

    parser.add_argument("--fit-max", type=float, default=None)
    parser.add_argument("--latency-ns-max", type=float, default=None)
    parser.add_argument("--carbon-kg-max", type=float, default=None)
    parser.add_argument("--ml-confidence-min", type=float, default=None)
    parser.add_argument("--ml-ood-max", type=float, default=None)
    parser.add_argument(
        "--ml-policy",
        choices=["carbon_min", "fit_min", "energy_min", "utility_balanced"],
        default=None,
    )
    parser.add_argument("--ml-debug", action="store_true", help="Emit JSON-only ML diagnostics")
    parser.add_argument(
        "--strict-sanity",
        action="store_true",
        help="Hard-fail when sanity checks detect implausible predictions",
    )

    return parser


def _prompt_float(label: str, current: float | None, default: float) -> float:
    if current is not None:
        return float(current)
    raw = input(f"{label} [{default}]: ").strip()
    if not raw:
        return float(default)
    return float(raw)


def _prompt_int(label: str, current: int | None, default: int) -> int:
    if current is not None:
        return int(current)
    raw = input(f"{label} [{default}]: ").strip()
    if not raw:
        return int(default)
    return int(raw)


def _prompt_optional_float(label: str, current: float | None) -> float | None:
    if current is not None:
        return float(current)
    raw = input(f"{label} [none]: ").strip()
    if not raw:
        return None
    return float(raw)


def _prompt_yes_no(label: str, default_yes: bool = False) -> bool:
    default_token = "Y/n" if default_yes else "y/N"
    raw = input(f"{label} ({default_token}): ").strip().lower()
    if not raw:
        return default_yes
    return raw in {"y", "yes"}


def _interactive_fill(args: argparse.Namespace) -> None:
    args.node = _prompt_int("Technology node (nm)", args.node, 14)
    args.vdd = _prompt_float("Vdd", args.vdd, 0.8)
    args.temp = _prompt_float("Temperature C", args.temp, 75.0)
    args.capacity_gib = _prompt_float("Capacity GiB", args.capacity_gib, 8.0)
    args.ci = _prompt_float("Carbon intensity kgCO2e/kWh", args.ci, 0.55)
    args.bitcell_um2 = _prompt_float("Bitcell area um^2", args.bitcell_um2, 0.04)
    args.scrub_s = _prompt_float("Scrub interval s", args.scrub_s, 10.0)
    args.alt_km = _prompt_float("Altitude km", args.alt_km, 0.0)
    args.latitude = _prompt_float("Latitude deg", args.latitude, 45.0)
    args.fit_max = _prompt_optional_float("FIT max constraint", args.fit_max)
    args.latency_ns_max = _prompt_optional_float("Latency max (ns)", args.latency_ns_max)
    args.carbon_kg_max = _prompt_optional_float("Carbon max (kg)", args.carbon_kg_max)


def _apply_defaults(args: argparse.Namespace) -> None:
    if args.scrub_s is None:
        args.scrub_s = 10.0
    if args.alt_km is None:
        args.alt_km = 0.0
    if args.latitude is None:
        args.latitude = 45.0


def _required_missing(args: argparse.Namespace) -> list[str]:
    required = ["node", "vdd", "temp", "capacity_gib", "ci", "bitcell_um2"]
    return [name for name in required if getattr(args, name) is None]


def _norm01(values: list[float], value: float) -> float:
    if not values:
        return 0.0
    lo = min(values)
    hi = max(values)
    if hi <= lo:
        return 0.0
    return (value - lo) / (hi - lo)


def _select_ml_candidate(
    entries: list[dict[str, object]],
    policy: str,
) -> dict[str, object]:
    if not entries:
        raise ValueError("No entries to select from")

    policy_norm = str(policy).strip().lower()
    if policy_norm == "fit_min":
        return min(
            entries,
            key=lambda e: (
                float(e["prediction"]["predictions"].get("FIT", float("inf"))),
                str(e["record"].get("code")),
            ),
        )
    if policy_norm == "energy_min":
        return min(
            entries,
            key=lambda e: (
                float(e["prediction"]["predictions"].get("energy_kWh", float("inf"))),
                str(e["record"].get("code")),
            ),
        )
    if policy_norm == "utility_balanced":
        fits = [float(e["prediction"]["predictions"].get("FIT", float("inf"))) for e in entries]
        carbons = [float(e["prediction"]["predictions"].get("carbon_kg", float("inf"))) for e in entries]
        energies = [float(e["prediction"]["predictions"].get("energy_kWh", float("inf"))) for e in entries]

        def score(e: dict[str, object]) -> tuple[float, str]:
            fit = float(e["prediction"]["predictions"].get("FIT", float("inf")))
            carbon = float(e["prediction"]["predictions"].get("carbon_kg", float("inf")))
            energy = float(e["prediction"]["predictions"].get("energy_kWh", float("inf")))
            utility = (_norm01(fits, fit) + _norm01(carbons, carbon) + _norm01(energies, energy)) / 3.0
            return utility, str(e["record"].get("code"))

        return min(entries, key=score)

    return min(
        entries,
        key=lambda e: (
            float(e["prediction"]["predictions"].get("carbon_kg", float("inf"))),
            str(e["record"].get("code")),
        ),
    )


def _run_ml_advisory(args: argparse.Namespace) -> dict[str, object]:
    from ml.predict import predict_with_model, resolve_thresholds
    from ml.explain import format_decision_explanation

    constraints: dict[str, float | None] = {
        "fit_max": args.fit_max,
        "latency_ns_max": args.latency_ns_max,
        "carbon_kg_max": args.carbon_kg_max,
    }

    codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    scenario = {
        "node": int(args.node),
        "vdd": float(args.vdd),
        "temp": float(args.temp),
        "capacity_gib": float(args.capacity_gib),
        "ci": float(args.ci),
        "bitcell_um2": float(args.bitcell_um2),
    }

    result = select(
        codes,
        constraints=constraints,
        mbu=args.mbu,
        scrub_s=float(args.scrub_s),
        alt_km=float(args.alt_km),
        latitude_deg=float(args.latitude),
        flux_rel=float(args.flux_rel) if args.flux_rel is not None else None,
        **scenario,
    )

    records = [dict(r) for r in result.get("candidate_records", [])]
    feasible = [r for r in records if _record_passes_constraints(r, constraints)]
    baseline = _baseline_choice(result, feasible)

    resolved_thresholds = resolve_thresholds(
        {},
        model_dir=args.ml_model,
        confidence_min_override=args.ml_confidence_min,
        ood_threshold_override=args.ml_ood_max,
        policy_override=args.ml_policy,
    )
    selected_policy = str(resolved_thresholds.get("ml_policy", "carbon_min"))

    uncertainty_summary: dict[str, object] = {}
    uncertainty_path = Path(args.ml_model) / "uncertainty.json"
    if uncertainty_path.is_file():
        try:
            payload = json.loads(uncertainty_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                uncertainty_summary = payload
        except Exception:
            uncertainty_summary = {}

    eligible_entries: list[dict[str, object]] = []
    rejected_entries: list[dict[str, object]] = []

    for rec in feasible:
        row = dict(rec)
        row.update(scenario)
        pred = predict_with_model(
            args.ml_model,
            row,
            confidence_min_override=args.ml_confidence_min,
            ood_threshold_override=args.ml_ood_max,
            policy_override=args.ml_policy,
            strict_sanity=args.strict_sanity,
        )

        reasons: list[str] = []
        if bool(pred.get("ood", False)):
            reasons.append("ood")
        if bool(pred.get("low_confidence", False)):
            reasons.append("low_confidence")
        if not reasons and pred.get("fallback_reason"):
            reasons.append(str(pred["fallback_reason"]))

        candidate_diag = {
            "code": rec.get("code"),
            "confidence": float(pred.get("confidence", 0.0)),
            "ood_score": float(pred.get("ood_score", 0.0)),
            "predictions": pred.get("predictions", {}),
            "prediction_set": pred.get("prediction_set"),
        }
        sanity_warnings = list(pred.get("sanity_warnings", []))
        if sanity_warnings:
            candidate_diag["sanity_warnings"] = sanity_warnings

        if reasons:
            candidate_diag["reasons"] = reasons
            rejected_entries.append(candidate_diag)
        else:
            eligible_entries.append({"record": rec, "prediction": pred, "diag": candidate_diag})

    ml_choice = None
    ml_prediction = None
    if eligible_entries:
        picked = _select_ml_candidate(eligible_entries, selected_policy)
        ml_choice = picked["record"]
        ml_prediction = picked["prediction"]

    fallback_reason = None
    if not feasible:
        fallback_reason = "No feasible candidate satisfies hard constraints"
    elif ml_prediction is None:
        fallback_reason = "No admissible ML suggestion (OOD/low confidence); using baseline"

    final_choice = baseline
    if ml_choice is not None and fallback_reason is None:
        final_choice = ml_choice

    baseline_code = baseline.get("code") if isinstance(baseline, dict) else None
    ml_code = ml_choice.get("code") if isinstance(ml_choice, dict) else None
    final_code = final_choice.get("code") if isinstance(final_choice, dict) else None

    confidence = 0.0
    if ml_prediction is not None:
        confidence = float(ml_prediction.get("confidence", 0.0))

    explanation = format_decision_explanation(
        baseline_code=str(baseline_code),
        ml_code=str(ml_code),
        confidence=confidence,
        fallback_reason=fallback_reason,
        hard_constraints_ok=bool(_constraint_audit(final_choice, constraints)["all_pass"]),
    )

    out: dict[str, object] = {
        "baseline_recommendation": baseline_code,
        "ml_recommendation": ml_code,
        "final_decision": final_code,
        "confidence": confidence,
        "fallback_used": fallback_reason is not None,
        "fallback_reason": fallback_reason,
        "constraints": constraints,
        "constraints_audit": {
            "baseline": _constraint_audit(baseline, constraints),
            "ml": _constraint_audit(ml_choice, constraints),
            "final": _constraint_audit(final_choice, constraints),
        },
        "explanation": explanation,
        "predictions": ml_prediction.get("predictions") if ml_prediction else None,
        "scenario_hash": result.get("scenario_hash"),
        "selected_policy": selected_policy,
    }

    if args.ml_debug:
        out.update(
            {
                "confidence_score": float(ml_prediction.get("confidence", 0.0)) if ml_prediction else 0.0,
                "confidence_threshold": float(resolved_thresholds.get("confidence_min", 0.6)),
                "ood_method": str(resolved_thresholds.get("ood_method", "zscore")),
                "ood_score": float(ml_prediction.get("ood_score", 0.0)) if ml_prediction else 0.0,
                "ood_threshold": float(resolved_thresholds.get("ood_threshold", 4.0)),
                "in_distribution": bool(ml_prediction.get("in_distribution", False)) if ml_prediction else False,
                "prediction_set": ml_prediction.get("prediction_set") if ml_prediction else [],
                "eligible_candidates": [e["diag"] for e in eligible_entries],
                "rejected_candidates": rejected_entries,
                "uncertainty": uncertainty_summary,
            }
        )

    return out


def _run_optional_sweeps(args: argparse.Namespace) -> dict[str, list[dict[str, object]]]:
    sweeps: dict[str, list[dict[str, object]]] = {}

    if _prompt_yes_no("Run BER decade sweep?", default_yes=False):
        start_exp = int(_prompt_int("BER decade start exponent", None, -12))
        end_exp = int(_prompt_int("BER decade end exponent", None, -6))
        step = 1 if end_exp >= start_exp else -1
        ber_rows: list[dict[str, object]] = []
        for exp in range(start_exp, end_exp + step, step):
            ber = 10.0**exp
            sweep_args = argparse.Namespace(**vars(args))
            sweep_args.flux_rel = ber / 1e-9
            out = _run_ml_advisory(sweep_args)
            ber_rows.append({
                "ber": ber,
                "final_decision": out["final_decision"],
                "fallback_used": out["fallback_used"],
                "confidence": out["confidence"],
            })
        sweeps["ber_decade_sweep"] = ber_rows

    if _prompt_yes_no("Run Vdd sweep?", default_yes=False):
        v_start = _prompt_float("Vdd sweep start", None, max(0.1, float(args.vdd) - 0.1))
        v_end = _prompt_float("Vdd sweep end", None, float(args.vdd) + 0.1)
        v_step = _prompt_float("Vdd sweep step", None, 0.05)
        if v_step <= 0:
            v_step = 0.05

        rows: list[dict[str, object]] = []
        v = v_start
        direction = 1 if v_end >= v_start else -1
        while (direction == 1 and v <= v_end + 1e-12) or (direction == -1 and v >= v_end - 1e-12):
            sweep_args = argparse.Namespace(**vars(args))
            sweep_args.vdd = round(v, 6)
            out = _run_ml_advisory(sweep_args)
            rows.append({
                "vdd": sweep_args.vdd,
                "final_decision": out["final_decision"],
                "fallback_used": out["fallback_used"],
                "confidence": out["confidence"],
            })
            v += direction * abs(v_step)
        sweeps["vdd_sweep"] = rows

    return sweeps


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)

    # Backward compatibility: legacy positional invocations historically no-op.
    if "--ml-model" not in argv and "--interactive" not in argv:
        return

    parser = _selector_args_parser()
    args = parser.parse_args(argv)

    if args.ml_model is None:
        parser.error("--ml-model is required when ML mode is enabled")

    if args.ml_debug:
        args.json = True

    if args.interactive:
        _interactive_fill(args)

    _apply_defaults(args)
    missing = _required_missing(args)
    if missing:
        parser.error("Missing required arguments: " + ", ".join(missing))

    decision = _run_ml_advisory(args)

    if args.interactive:
        decision["sweeps"] = _run_optional_sweeps(args)

    if args.json:
        print(json.dumps(decision, indent=2, sort_keys=True))
    else:
        print(f"baseline recommendation: {decision['baseline_recommendation']}")
        print(f"ml recommendation: {decision['ml_recommendation']}")
        print(f"final decision: {decision['final_decision']}")
        print(f"confidence: {decision['confidence']:.3f}")
        print(f"fallback used: {decision['fallback_used']}")
        if decision["fallback_reason"]:
            print(f"fallback reason: {decision['fallback_reason']}")
        print(f"constraints audit: {json.dumps(decision['constraints_audit'], sort_keys=True)}")
        print(f"explanation: {decision['explanation']}")

        sweeps = decision.get("sweeps") or {}
        for key, rows in sweeps.items():
            print(f"{key}: {len(rows)} points")


__all__ = ["select", "_pareto_front", "_nsga2_sort"]


if __name__ == "__main__":
    main()
