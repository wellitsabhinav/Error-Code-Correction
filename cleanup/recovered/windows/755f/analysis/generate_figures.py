"""Generate figures for the energy-aware ECC manuscript."""

from __future__ import annotations


import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import ecc_selector as selector
from gs import (
    CARBON_HALFSAT_KG,
    FIT_FLOOR,
    LATENCY_HALFSAT_NS,
    LOG_RELIABILITY_HALFSAT_DECADES,
    GSInputs,
    compute_gs,
)


FIG_DIR = ROOT / "reports" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

SCENARIO = dict(
    node=28,
    vdd=0.8,
    temp=65.0,
    capacity_gib=32.0,
    ci=0.35,
    bitcell_um2=0.09,
    lifetime_h=5 * 365 * 24,
)

CODES = ["sec-ded-64", "sec-daec-64", "taec-64"]


def _save(fig, name: str, *, tight: bool = True) -> None:
    out_png = FIG_DIR / name
    save_kwargs = {"dpi": 300}
    if tight:
        save_kwargs["bbox_inches"] = "tight"
    fig.savefig(out_png, **save_kwargs)
    if out_png.suffix.lower() == ".png":
        pdf_kwargs: dict[str, object] = {}
        if tight:
            pdf_kwargs["bbox_inches"] = "tight"
        fig.savefig(out_png.with_suffix(".pdf"), **pdf_kwargs)


def _base_records(scrub_s: float = 10.0) -> list[dict[str, float]]:
    result = selector.select(
        CODES,
        scrub_s=scrub_s,
        mbu="moderate",
        alt_km=0.0,
        latitude_deg=45.0,
        flux_rel=None,
        **SCENARIO,
    )
    return [dict(rec) for rec in result["candidate_records"]]


def pareto_frontier_fig() -> None:
    records = _base_records(scrub_s=20.0)
    if not records:
        raise RuntimeError("No records returned from selector")

    pareto = selector._pareto_front(records)
    pareto_codes = {rec["code"] for rec in pareto}

    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    for rec in records:
        label = rec["code"].replace("-64", "").upper()
        ax.scatter(
            rec["carbon_kg"],
            rec["FIT"],
            s=120,
            marker="o" if rec["code"] in pareto_codes else "x",
            c="#1f77b4" if rec["code"] in pareto_codes else "#bbbbbb",
            edgecolor="black" if rec["code"] in pareto_codes else "none",
            linewidths=1.0,
            alpha=0.9 if rec["code"] in pareto_codes else 0.7,
            label=label,
        )
        ax.annotate(
            label,
            (rec["carbon_kg"], rec["FIT"]),
            textcoords="offset points",
            xytext=(0, 10),
            ha="center",
            fontsize=9,
        )

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Total carbon (kg CO$_2$e)")
    ax.set_ylabel("Post-ECC FIT (failures / 10$^9$ h)")
    ax.set_title("Pareto frontier across ECC candidates")
    ax.grid(True, which="both", ls=":", alpha=0.6)
    ax.legend(frameon=False, loc="upper right")

    fig.tight_layout()
    _save(fig, "fig_pareto_frontier.png")
    plt.close(fig)


def carbon_heatmap_fig() -> None:
    code = "sec-daec-64"
    scrub_vals = np.logspace(0, 3, 40)
    ci_vals = np.linspace(0.05, 0.7, 36)

    Z = np.zeros((ci_vals.size, scrub_vals.size))
    for i, ci in enumerate(ci_vals):
        for j, scrub in enumerate(scrub_vals):
            rec = selector._compute_metrics(
                code,
                node=SCENARIO["node"],
                vdd=SCENARIO["vdd"],
                temp=SCENARIO["temp"],
                ci=float(ci),
                capacity_gib=SCENARIO["capacity_gib"],
                bitcell_um2=SCENARIO["bitcell_um2"],
                alt_km=0.0,
                latitude_deg=45.0,
                flux_rel=None,
                mbu="moderate",
                scrub_s=float(scrub),
                lifetime_h=SCENARIO["lifetime_h"],
            )
            Z[i, j] = rec["carbon_kg"]

    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    im = ax.imshow(
        Z,
        origin="lower",
        aspect="auto",
        extent=[
            math.log10(scrub_vals.min()),
            math.log10(scrub_vals.max()),
            ci_vals.min(),
            ci_vals.max(),
        ],
        cmap="viridis",
    )
    cbar = fig.colorbar(im, ax=ax, pad=0.02)
    cbar.set_label("Total carbon (kg CO$_2$e)")

    x_ticks = np.array([1, 3, 10, 30, 100, 300, 1000])
    ax.set_xticks(np.log10(x_ticks))
    ax.set_xticklabels([f"{int(x)}" for x in x_ticks])
    ax.set_xlabel("Scrub interval (s)")
    ax.set_ylabel("Grid carbon intensity (kg CO$_2$e/kWh)")
    ax.set_title("Carbon sensitivity for SEC-DAEC")

    fig.tight_layout()
    _save(fig, "fig_carbon_heatmap.png")
    plt.close(fig)


def metric_correlation_fig() -> None:
    rows: list[dict[str, float]] = []
    scrub_candidates = [1, 5, 10, 30, 60, 120, 300, 600]
    for code in CODES:
        for scrub in scrub_candidates:
            rec = selector._compute_metrics(
                code,
                node=SCENARIO["node"],
                vdd=SCENARIO["vdd"],
                temp=SCENARIO["temp"],
                ci=SCENARIO["ci"],
                capacity_gib=SCENARIO["capacity_gib"],
                bitcell_um2=SCENARIO["bitcell_um2"],
                alt_km=0.0,
                latitude_deg=45.0,
                flux_rel=None,
                mbu="moderate",
                scrub_s=float(scrub),
                lifetime_h=SCENARIO["lifetime_h"],
            )
            rec = dict(rec)
            rec["code"] = code
            rec["scrub_s"] = scrub
            rows.append(rec)

    df = pd.DataFrame(rows)
    metrics = ["FIT", "carbon_kg", "latency_ns", "ESII"]
    corr = df[metrics].corr()

    fig, ax = plt.subplots(figsize=(6.2, 4.6), constrained_layout=True)
    im = ax.imshow(corr, vmin=-1, vmax=1, cmap="coolwarm")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Pearson correlation")

    ax.set_xticks(range(len(metrics)))
    ax.set_yticks(range(len(metrics)))
    ax.set_xticklabels(metrics, rotation=45, ha="right")
    ax.set_yticklabels(metrics)
    ax.set_title("Metric correlation across codes & scrubs")

    for i in range(len(metrics)):
        for j in range(len(metrics)):
            ax.text(
                j,
                i,
                f"{corr.iloc[i, j]:.2f}",
                ha="center",
                va="center",
                color="black",
                fontsize=9,
            )

    _save(fig, "fig_metric_correlation.png")
    plt.close(fig)


def ablation_sensitivity_fig() -> None:
    """Visualise GS parameter robustness."""

    scrub_candidates = np.array([1, 5, 10, 20, 40, 80, 160, 320], dtype=float)
    records: list[dict[str, float]] = []

    for code in CODES:
        for scrub in scrub_candidates:
            rec = selector._compute_metrics(
                code,
                node=SCENARIO["node"],
                vdd=SCENARIO["vdd"],
                temp=SCENARIO["temp"],
                ci=SCENARIO["ci"],
                capacity_gib=SCENARIO["capacity_gib"],
                bitcell_um2=SCENARIO["bitcell_um2"],
                alt_km=0.0,
                latitude_deg=45.0,
                flux_rel=None,
                mbu="moderate",
                scrub_s=float(scrub),
                lifetime_h=SCENARIO["lifetime_h"],
            )
            rec = dict(rec)
            rec["code"] = code
            rec["scrub_s"] = float(scrub)
            rec["id"] = f"{code}@{int(scrub)}"
            records.append(rec)

    def _norm_weights(weights: tuple[float, float, float]) -> tuple[float, float, float]:
        total = sum(weights)
        if total <= 0:
            raise ValueError("weights must sum to a positive value")
        return tuple(w / total for w in weights)

    base_weights = (0.6, 0.3, 0.1)
    # Baseline half-saturation constants from the *implemented* GS model,
    # swept by +/-25% below.
    base_kappas = (LOG_RELIABILITY_HALFSAT_DECADES, CARBON_HALFSAT_KG, LATENCY_HALFSAT_NS)

    variants: list[dict[str, object]] = [
        {
            "label": "Baseline",
            "weights": _norm_weights(base_weights),
            "kappas": base_kappas,
        }
    ]

    for name, idx in (("wR", 0), ("wC", 1), ("wL", 2)):
        for scale, suffix in ((0.75, "-25%"), (1.25, "+25%")):
            w = list(base_weights)
            w[idx] *= scale
            variants.append(
                {
                    "label": f"{name} {suffix}",
                    "weights": _norm_weights(tuple(w)),
                    "kappas": base_kappas,
                }
            )

    for sym, idx in (("R", 0), ("C", 1), ("L", 2)):
        for scale, suffix in ((0.75, "-25%"), (1.25, "+25%")):
            k = list(base_kappas)
            k[idx] *= scale
            variants.append(
                {
                    "label": f"$\\kappa_{sym}$ {suffix}",
                    "weights": _norm_weights(base_weights),
                    "kappas": tuple(k),
                }
            )

    scores: dict[str, dict[str, float]] = {}

    for variant in variants:
        weights = variant["weights"]  # type: ignore[assignment]
        kappas = variant["kappas"]  # type: ignore[assignment]
        variant_scores: dict[str, float] = {}
        for rec in records:
            # `gs.compute_gs` does not expose kappa_R directly. Emulate sweeping the
            # reliability half-saturation by scaling the FIT-decade gap before
            # calling the implemented GS utility.
            kappa_r, kappa_c, kappa_l = kappas  # type: ignore[misc]
            fit_base = max(float(rec["fit_base"]), 0.0)
            fit_ecc = max(float(rec["FIT"]), 0.0)

            log_fit_base = math.log10(max(fit_base, FIT_FLOOR))
            log_fit_ecc = math.log10(max(fit_ecc, FIT_FLOOR))
            decades = max(log_fit_base - log_fit_ecc, 0.0)
            if float(kappa_r) <= 0:
                raise ValueError("kappa_r must be positive")
            s = LOG_RELIABILITY_HALFSAT_DECADES / float(kappa_r)
            log_fit_ecc_adj = log_fit_base - s * decades
            fit_ecc_adj = 10**log_fit_ecc_adj

            gs_val = compute_gs(
                GSInputs(
                    fit_base=fit_base,
                    fit_ecc=fit_ecc_adj,
                    carbon_kg=rec["carbon_kg"],
                    latency_ns=rec["latency_ns"],
                    latency_base_ns=rec.get("latency_base_ns", 0.0),
                ),
                weights=weights,  # type: ignore[arg-type]
                carbon_halfsat_kg=float(kappa_c),
                latency_halfsat_ns=float(kappa_l),
            )["GS"]
            variant_scores[rec["id"]] = gs_val
        scores[variant["label"]] = variant_scores  # type: ignore[index]

    baseline = variants[0]["label"]
    baseline_order = sorted(
        records,
        key=lambda rec: scores[baseline][rec["id"]],
        reverse=True,
    )
    baseline_ids = [rec["id"] for rec in baseline_order]

    def kendall_tau(order: list[str], reference: list[str]) -> float:
        ref_index = {rid: idx for idx, rid in enumerate(reference)}
        n = len(order)
        concordant = 0
        discordant = 0
        for i in range(n):
            for j in range(i + 1, n):
                a = order[i]
                b = order[j]
                if ref_index[a] < ref_index[b]:
                    concordant += 1
                else:
                    discordant += 1
        denom = n * (n - 1) / 2
        return (concordant - discordant) / denom if denom else 1.0

    tau_values: dict[str, float] = {}
    for variant in variants:
        label = variant["label"]  # type: ignore[index]
        ordering = sorted(
            records,
            key=lambda rec: scores[label][rec["id"]],
            reverse=True,
        )
        tau_values[label] = kendall_tau(
            [rec["id"] for rec in ordering], baseline_ids
        )

    spreads = {
        rec["id"]: (
            min(score_map[rec["id"]] for score_map in scores.values()),
            max(score_map[rec["id"]] for score_map in scores.values()),
        )
        for rec in records
    }

    fig, (ax_front, ax_tau) = plt.subplots(
        2,
        1,
        figsize=(6.8, 7.2),
        gridspec_kw={"height_ratios": [3, 2]},
        constrained_layout=True,
    )

    spread_vals = [spreads[rec["id"]][1] - spreads[rec["id"]][0] for rec in records]
    sc = ax_front.scatter(
        [rec["carbon_kg"] for rec in records],
        [rec["FIT"] for rec in records],
        c=spread_vals,
        cmap="plasma",
        s=65,
        alpha=0.85,
    )
    cbar = fig.colorbar(sc, ax=ax_front, pad=0.02, fraction=0.05)
    cbar.set_label(r"GS span across $\pm 25\%$ sweeps")

    frontier = selector._pareto_front(records)
    frontier_sorted = sorted(frontier, key=lambda rec: rec["carbon_kg"])
    ax_front.plot(
        [rec["carbon_kg"] for rec in frontier_sorted],
        [rec["FIT"] for rec in frontier_sorted],
        color="#1f77b4",
        linewidth=1.4,
        label="Carbon--FIT frontier",
    )

    baseline_id = baseline_ids[0]
    base_rec = next(rec for rec in records if rec["id"] == baseline_id)
    ax_front.scatter(
        [base_rec["carbon_kg"]],
        [base_rec["FIT"]],
        marker="*",
        s=220,
        edgecolor="black",
        facecolor="#2ca02c",
        label="Baseline top pick",
        zorder=5,
    )

    ax_front.set_xscale("log")
    ax_front.set_yscale("log")
    ax_front.set_xlabel("Total carbon (kg CO$_2$e)")
    ax_front.set_ylabel("Post-ECC FIT (failures / 10$^9$ h)")
    ax_front.set_title(r"GREEN Score robustness to $\kappa$ and weight sweeps")
    ax_front.grid(True, which="both", ls=":", alpha=0.6)
    ax_front.legend(frameon=False, loc="lower left")

    variant_labels = [v["label"] for v in variants[1:]]  # type: ignore[index]
    tau_vals = [tau_values[label] for label in variant_labels]
    ax_tau.barh(variant_labels, tau_vals, color="#1f77b4")
    ax_tau.set_xlim(0.95, 1.001)
    ax_tau.set_xlabel(r"Kendall $\tau$ vs. baseline ranking")
    ax_tau.set_title(r"Rank stability under $\pm 25\%$ perturbations")
    ax_tau.grid(axis="x", linestyle=":", alpha=0.5)

    for y, val in enumerate(tau_vals):
        ax_tau.text(
            val + 0.001,
            y,
            f"{val:.3f}",
            va="center",
            fontsize=8,
        )

    _save(fig, "fig_ablation_sensitivity.png", tight=False)
    plt.close(fig)


if __name__ == "__main__":
    pareto_frontier_fig()
    carbon_heatmap_fig()
    metric_correlation_fig()
    ablation_sensitivity_fig()
