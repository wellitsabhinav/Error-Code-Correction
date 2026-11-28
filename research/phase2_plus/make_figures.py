"""Generate vector figures from the package's traceable derived tables."""

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np

from evidence import Frozen, historical_date
from run_campaign import PACKAGE, digest, read_json, write_json


BLUE, ORANGE, GRAY = "#006c9d", "#c34f21", "#495769"
LABEL = {"secded_comb": "Combinational", "secded_pipe": "Pipelined"}


def table(folder, name):
    with (folder / (name + ".csv")).open(encoding="utf-8", newline="") as src:
        return list(csv.DictReader(src))


def clean(ax, grid="y"):
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis=grid, color="#e0e6ec", linewidth=0.7)
    ax.set_axisbelow(True)


def save(fig, target, name):
    fig.savefig(target / (name + ".pdf"), metadata={"CreationDate": None, "ModDate": None})
    fig.savefig(target / (name + ".svg"), metadata={"Date": None})
    plt.close(fig)


def estimator(derived, target):
    results = table(derived, "estimator_comparison")
    physical = {r["architecture_id"]: r for r in table(derived, "physical_characterization")}
    fig, (a, b) = plt.subplots(1, 2, figsize=(9.2, 3.6), layout="constrained")
    x = np.arange(2)
    for offset, (method, title, color) in enumerate((
        ("A", "Primary-input propagation", GRAY), ("B", "Zero-delay internal VCD", BLUE),
    )):
        values = [float(r["energy_pj"]) for r in results if r["method"] == method]
        a.bar(x + (offset - 0.5) * 0.32, values, width=0.32, color=color, label=title)
    a.set_xticks(x, [*LABEL.values()])
    a.set(title="Matched estimators on the new routes", ylabel="Energy (pJ / completed codec pair)", ylim=(0, 103))
    a.legend(loc="upper left", frameon=False, fontsize=8)
    clean(a)
    historical = historical_date(Frozen())
    for i, (arch, color) in enumerate(zip(LABEL, (BLUE, ORANGE))):
        b.scatter([pair[i].service.area_um2 / 1e3 for pair in historical],
                  [pair[i].energy_j["CONCURRENT_NO_ERROR"] * 1e12 for pair in historical],
                  edgecolors=color, facecolors="none", s=44, linewidths=1.2,
                  label="Historical, 5 seeds" if i == 0 else None)
        row = next(r for r in results if r["method"] == "B" and r["architecture_id"] == arch)
        b.scatter(float(physical[arch]["stdcell_area_um2"]) / 1e3, float(row["energy_pj"]),
                  color=color, s=50, marker="s", label="New routes, seed 17" if i == 0 else None)
    b.set(title="Area and energy by implementation",
          xlabel="Standard-cell area (10³ µm²)", ylabel="Modeled energy (pJ / codec pair)", ylim=(42, 162))
    b.legend(loc="lower right", frameon=False, fontsize=8)
    clean(b)
    save(fig, target, "01_estimator_area")


def break_even(derived, target):
    data = read_json(derived / "scenario_summary.json")
    secs = data["date_reference_utilization_break_even_years_mid_grid"]["allocated"]
    grid = {r["id"]: float(r["converted_value"]) for r in table(derived, "operational_grid_scenarios")}
    fig, (a, b) = plt.subplots(1, 2, figsize=(9.2, 3.7), layout="constrained")
    utilization = np.geomspace(1, 100, 160)
    for key, label, color in (("grid_low", "Lower intensity", BLUE), ("grid_mid", "US average", GRAY),
                              ("grid_high", "Higher intensity", ORANGE)):
        scale = grid["grid_mid"] / grid[key] / utilization
        a.plot(utilization, secs["median"] * scale, label=label, color=color, linewidth=1.6)
        a.fill_between(utilization, secs["min"] * scale, secs["max"] * scale, color=color, alpha=0.17, linewidth=0)
    a.set(xscale="log", yscale="log", xlabel="Utilization (%)", ylabel="Carbon break-even (years)",
          title="Historical codec pair • allocated area")
    a.legend(frameon=False, fontsize=8)
    clean(a)
    rows = table(derived, "carbon_break_even")
    rows = [r for r in rows if r["cohort"] == "DATE" and r["utilization"] == "0.01" and r["allocation"] != ""]
    levels = ["fixed", "allocated", "marginal"]
    for y, model in enumerate(levels):
        group = [float(r["delta_scoped_lifecycle_kg"]) * 1e6 for r in rows if r["allocation"] == model]
        b.hlines(y, min(group), max(group), color=BLUE, lw=2)
        b.plot(group, [y] * len(group), marker="o", ms=4, linestyle="none", color=BLUE, alpha=0.70)
    b.set_yticks(range(3), ["Fixed die", "Area allocation", "Die growth"])
    b.axvline(0, color=GRAY, lw=0.9, linestyle="--")
    b.set(xlabel="Pipelined − combinational (mg CO₂e)",
          title="One year, 1% utilization, US average")
    clean(b, "x")
    save(fig, target, "02_historical_carbon")


def sram_regions(derived, target):
    rows = table(derived, "robustness_analysis")
    seeds = [13, 17, 19, 23]
    axis = np.linspace(0, 1, 101)
    read, active = np.meshgrid(axis, axis)
    fields = {}
    for seed in seeds:
        row = next(r for r in rows if int(r["placement_seed"]) == seed)
        idle = float(row["delta_idle_w"])
        read_w = 1e8 * float(row["delta_clean_read_j"])
        write_w = 1e8 * float(row["delta_clean_write_j"])
        fields[seed] = ((1 - active) * idle + active * (read * read_w + (1 - read) * write_w)) * 1e6
    limit = max(abs(field).max() for field in fields.values())
    fig, axes = plt.subplots(2, 2, figsize=(7.4, 6.3), sharex=True, sharey=True, layout="constrained")
    norm = TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit)
    for seed, ax in zip(seeds, axes.flat):
        field = fields[seed]
        color = ax.pcolormesh(100 * axis, 100 * axis, field, shading="auto", cmap="RdBu_r", norm=norm,
                              rasterized=True)
        if np.min(field) < 0 < np.max(field):
            ax.contour(100 * read, 100 * active, field, levels=[0], colors="#242b33", linewidths=1.0)
        ax.set(title=f"Seed {seed}", xlim=(0, 100), ylim=(0, 100))
    fig.supxlabel("Clean-read share of active operations (%)")
    fig.supylabel("Utilization (%)")
    fig.colorbar(color, ax=axes, shrink=0.86, label="Hsiao − Extended Hamming ECC-logic power (µW)")
    save(fig, target, "03_sram_workload_regions")


def conditioned(derived, target):
    rows = table(derived, "reconstructed_workload_energy")
    payload = [("identical", "Repeated"), ("spatial", "Spatial"), ("counter", "Counter"),
               ("low_hd", "Low HD"), ("medium_hd", "Medium HD"), ("uniform", "Uniform"),
               ("high_hd", "High HD"), ("alternating", "Alternating")]
    errors = [("uniform", "Clean"), ("single_data", "Data-bit correction"), ("single_check", "Check-bit correction"),
              ("double", "Double detection"), ("adjacent_multi", "Adjacent W3"), ("mixed", "Mixed")]
    fig, axes = plt.subplots(1, 2, figsize=(9.8, 4.6), sharex=True, layout="constrained")
    for ax, conditions, title in zip(axes, (payload, errors), ("Clean payload patterns", "Injected errors and mixed trace")):
        for arch, color, marker in zip(LABEL, (BLUE, ORANGE), ("o", "s")):
            for i, (key, _) in enumerate(conditions):
                r = next(row for row in rows if row["architecture_id"] == arch and row["workload_identity"] == key)
                if r["energy_pj"]:
                    ax.scatter(float(r["energy_pj"]), i, label=LABEL[arch] if i == 0 else None, color=color,
                               marker=marker, s=34, zorder=3)
        ax.set(yticks=range(len(conditions)), yticklabels=[label for _, label in conditions], title=title,
               xlabel="Energy (pJ / completed codec pair)")
        ax.invert_yaxis()
        clean(ax, "x")
    axes[1].legend(frameon=False, fontsize=8, loc="lower right")
    save(fig, target, "04_reconstructed_workloads")


def circuit(derived, target):
    cell = read_json(derived / "routed_xor_example.json")["secded_comb"]["connected_xor_cells"]
    fig, ax = plt.subplots(figsize=(7.0, 2.65), layout="constrained")
    ax.axis("off")
    ax.set(xlim=(0, 10), ylim=(0, 3.2))
    first, second = cell["first"], cell["second"]
    nodes = [first, second]
    for x, definition in zip((2.7, 6.8), nodes):
        label = definition["cell"].split("__")[-1]
        ax.text(x, 1.42, f"{label}\n{definition['instance']}", ha="center", va="center",
                fontsize=10, bbox={"boxstyle": "round,pad=0.55", "facecolor": "#e8f3fa", "edgecolor": BLUE})
    ax.annotate("", (5.8, 1.42), (3.7, 1.42), arrowprops={"arrowstyle": "->", "color": GRAY})
    ax.text(4.75, 1.63, cell["matching_net"], ha="center", color=GRAY)
    second_input = next(pin for port, pin in second["pins"].items() if port in {"A", "B"} and pin != cell["matching_net"])
    for pos, end, text in [
        ((0.3, 2.5), (2.1, 1.75), first["pins"]["A"]),
        ((0.3, 0.45), (2.1, 1.10), first["pins"]["B"]),
        ((5.0, 2.50), (6.35, 1.76), second_input),
    ]:
        ax.annotate(text, end, pos, arrowprops={"arrowstyle": "->", "color": GRAY}, fontsize=9, color=GRAY)
    ax.annotate("", (9.18, 1.42), (7.8, 1.42), arrowprops={"arrowstyle": "->", "color": GRAY})
    ax.text(8.5, 1.63, second["pins"]["X"], ha="center", fontsize=9, color=GRAY)
    ax.set_title("Two connected XOR cells in the reconstructed combinational codec", fontsize=11)
    save(fig, target, "05_routed_xor_cells")


def main(derived, target):
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 9.6, "axes.titleweight": "semibold", "axes.labelcolor": "#1f2937",
        "svg.hashsalt": "GREENS-PHASE2-PLUS-R1", "svg.fonttype": "none", "pdf.fonttype": 42,
    })
    target.mkdir(parents=True, exist_ok=True)
    for draw in (estimator, break_even, sram_regions, conditioned, circuit):
        draw(derived, target)
    write_json(target / "manifest.json", {
        "inputs": {path.name: digest(path) for path in sorted(derived.iterdir()) if path.is_file()},
        "figures": {path.name: digest(path) for path in sorted(target.iterdir()) if path.suffix in {".pdf", ".svg"}},
        "historical_estimator_operands": "Frozen DATE paths in processed/carbon_input_manifest.json",
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed", type=Path, default=PACKAGE / "processed")
    parser.add_argument("--output", type=Path, default=PACKAGE / "figures")
    args = parser.parse_args()
    main(args.processed, args.output)
