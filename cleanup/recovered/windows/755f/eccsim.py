#!/usr/bin/env python3
"""Command line entry point for ECC selection and evaluation.

This CLI exposes a selection-oriented workflow (scenario inputs → candidate
metrics → Pareto frontier → recommendation) plus supporting analysis and
evaluation subcommands. The ``--version`` output combines:

* the repository Git commit hash (when available),
* the SHA256 hash of ``tech_calib.json`` (to identify calibration content), and
* the semantic version string stored in ``VERSION``.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
from pathlib import Path
import csv
import json
import sys
from typing import Dict

from esii import ESIIInputs
from scores import compute_scores
from carbon import embodied_kgco2e, operational_kgco2e, default_alpha
from carbon_model import estimate_carbon_bounds, carbon_breakdown
from ser_model import HazuchaParams, ser_hazucha, flux_from_location
from qcrit_loader import qcrit_lookup
from mbu import pmf_adjacent
from fit import (
    compute_fit_pre,
    compute_fit_post,
    ecc_coverage_factory,
    fit_system,
    mttf_from_fit,
    FitEstimate,
)
from energy_model import UncertaintyValidationError, energy_report
from validation.output_sanity import OutputSanityError
from ecc_selector import select
from sram_workflow import run_sram_backend, run_sram_selection, write_sram_records_csv
from schema import SELECT_CANDIDATE_CSV_FIELDS, TARGET_FEASIBLE_CSV_FIELDS
from integrated_toolkit import ToolkitInput, evaluate_toolkit


def _format_reliability_report(result: dict) -> str:
    """Return a human-readable reliability report string.

    Parameters
    ----------
    result:
        Mapping of metric names to values as produced by the reliability
        backend.

    Returns
    -------
    str
        Multi-line string with metrics in a stable order, formatted to three
        significant figures for floats.
    """

    order = [
        "qcrit",
        "qs",
        "flux_rel",
        "fit_bit",
        "fit_word_pre",
        "fit_word_post",
        "fit_system",
        "mttf",
    ]

    lines = []
    for key in order:
        value = result[key]
        if isinstance(value, FitEstimate):
            if value.stddev is not None:
                lines.append(
                    f"{key:<15} {value.nominal:.3e} ± {value.stddev:.1e}"
                )
            else:
                lines.append(f"{key:<15} {value.nominal:.3e}")
        elif isinstance(value, float):
            lines.append(f"{key:<15} {value:.3e}")
        else:
            lines.append(f"{key:<15} {value}")
    return "\n".join(lines)


def _read_git_head_hash(repo_path: Path) -> str | None:
    """Best-effort commit hash lookup by reading `.git` metadata directly.

    This supports both a normal `.git/` directory layout and the worktree
    layout where `.git` is a text file containing `gitdir: ...`.
    """

    git_path = repo_path / ".git"

    try:
        if git_path.is_dir():
            gitdir = git_path
        elif git_path.is_file():
            first = git_path.read_text(errors="replace").splitlines()[0].strip()
            if not first.lower().startswith("gitdir:"):
                return None
            raw = first.split(":", 1)[1].strip()
            gitdir = Path(raw)
            if not gitdir.is_absolute():
                gitdir = (repo_path / gitdir).resolve()
        else:
            return None

        common_dir = gitdir
        commondir_path = gitdir / "commondir"
        if commondir_path.exists():
            raw = commondir_path.read_text(errors="replace").strip()
            common_dir = Path(raw)
            if not common_dir.is_absolute():
                common_dir = (gitdir / common_dir).resolve()

        head = (gitdir / "HEAD").read_text(errors="replace").strip()
        if re.fullmatch(r"[0-9a-fA-F]{40}", head):
            return head.lower()
        if head.lower().startswith("ref:"):
            ref_name = head.split(":", 1)[1].strip()
            for base in (gitdir, common_dir):
                ref_path = base / ref_name
                if ref_path.exists():
                    ref_hash = ref_path.read_text(errors="replace").strip()
                    if re.fullmatch(r"[0-9a-fA-F]{40}", ref_hash):
                        return ref_hash.lower()
            packed_refs = common_dir / "packed-refs"
            if packed_refs.exists():
                for line in packed_refs.read_text(errors="replace").splitlines():
                    if not line or line.startswith("#") or line.startswith("^"):
                        continue
                    parts = line.split()
                    if (
                        len(parts) >= 2
                        and parts[1] == ref_name
                        and re.fullmatch(r"[0-9a-fA-F]{40}", parts[0])
                    ):
                        return parts[0].lower()
    except Exception:
        return None

    return None


def _git_hash(repo_path: Path) -> str:
    """Return the current Git commit hash or ``unknown`` if unavailable.

    Git may be unavailable (or refuse to run due to environment hardening such
    as `safe.directory` checks). In that case, fall back to parsing `.git`
    metadata to recover the commit hash for repository builds.
    """

    try:
        return (
            subprocess.check_output(
                ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except Exception:
        head_hash = _read_git_head_hash(repo_path)
        return head_hash or "unknown"


def _file_hash(path: Path) -> str:
    """Return the SHA256 hash for the contents of ``path``."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _load_json(path: Path):
    """Load JSON content from ``path`` supporting multiple encodings."""

    raw = path.read_bytes()
    attempts = (
        ("utf-8", "UTF-8"),
        ("utf-8-sig", "UTF-8-SIG"),
        ("utf-16", "UTF-16"),
        ("utf-16-le", "UTF-16 LE"),
        ("utf-16-be", "UTF-16 BE"),
    )
    errors: list[str] = []
    for encoding, label in attempts:
        try:
            text = raw.decode(encoding)
            if text.startswith("\ufeff"):
                text = text[1:]
        except UnicodeDecodeError as exc:
            errors.append(f"{label}: {exc}")
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            errors.append(f"{label}: {exc}")
    raise ValueError(
        "Failed to decode JSON from "
        f"{path}: " + "; ".join(errors)
    )



def _bounded_open_01(value: str) -> float:
    """argparse helper for (0, 1) bounded floats."""

    try:
        out = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Expected a float in (0,1), got {value!r}") from exc
    if not (0.0 < out < 1.0):
        raise argparse.ArgumentTypeError(f"Expected a float in (0,1), got {value!r}")
    return out

def main() -> None:
    repo_path = Path(__file__).resolve().parent
    version_base = (repo_path / "VERSION").read_text().strip()
    tech_hash = _file_hash(repo_path / "tech_calib.json")
    git_hash = _git_hash(repo_path)

    if len(sys.argv) == 2 and sys.argv[1] == "--version":
        print(f"{git_hash} {tech_hash} {version_base}")
        return

    parser = argparse.ArgumentParser(description="ECC simulator")
    parser.add_argument(
        "--version",
        action="version",
        version=f"{git_hash} {tech_hash} {version_base}",
    )
    sub = parser.add_subparsers(dest="command")

    energy_parser = sub.add_parser("energy", help="Estimate energy use")
    energy_parser.add_argument(
        "--code", type=str, required=True, choices=["sec-ded", "sec-daec", "taec", "polar"]
    )
    energy_parser.add_argument("--node", type=float, required=True)
    energy_parser.add_argument("--vdd", type=float, required=True)
    energy_parser.add_argument("--temp", type=float, required=True)
    energy_parser.add_argument("--ops", type=float, required=True)
    energy_parser.add_argument("--lifetime-h", type=float, required=True)
    energy_parser.add_argument(
        "--report", type=str, choices=["json"], default=None
    )
    energy_parser.add_argument(
        "--uncertainty-path",
        type=Path,
        default=None,
        help="Optional uncertainty sidecar JSON to compute confidence indicators",
    )
    energy_parser.add_argument(
        "--strict-validation",
        action="store_true",
        help="Reject predictions when uncertainty metadata is missing or too wide",
    )
    energy_parser.add_argument(
        "--max-relative-stddev",
        type=float,
        default=0.25,
        help="Maximum allowed relative stddev for strict validation",
    )
    energy_parser.add_argument(
        "--strict-sanity",
        action="store_true",
        help="Hard-fail when output sanity checks detect implausible values",
    )

    carbon_parser = sub.add_parser("carbon", help="Estimate carbon footprint")
    carbon_parser.add_argument(
        "--areas",
        type=str,
        required=True,
        help="Comma separated logic and macro areas in mm^2",
    )
    carbon_parser.add_argument(
        "--alpha",
        type=str,
        required=True,
        help="Comma separated alpha factors for logic and macros",
    )
    carbon_parser.add_argument("--ci", type=float, required=True)
    carbon_parser.add_argument("--Edyn", type=float, required=True)
    carbon_parser.add_argument("--Eleak", type=float, required=True)
    carbon_parser.add_argument("--calibrated", action="store_true", help="Enable calibrated static/dynamic carbon model")
    carbon_parser.add_argument("--node", type=int, default=16, help="Technology node for calibrated carbon mode")
    carbon_parser.add_argument("--area-cm2", type=float, default=None, help="Effective area in cm^2 for calibrated mode")
    carbon_parser.add_argument("--memory-bits", type=int, default=None, help="Memory bits proxy when area-cm2 is not provided")
    carbon_parser.add_argument("--bitcell-area-um2", type=float, default=None, help="Bitcell area in um^2 when using memory proxy")
    carbon_parser.add_argument("--grid-region", type=str, default="global_avg", help="Grid region for calibrated dynamic carbon")
    carbon_parser.add_argument("--years", type=float, default=None, help="Lifetime years")
    carbon_parser.add_argument("--accesses-per-day", type=float, default=None, help="Lifetime accesses per day")
    carbon_parser.add_argument("--total-accesses", type=float, default=None, help="Explicit total accesses")

    esii_parser = sub.add_parser("esii", help="Compute the ESII metric")
    esii_parser.add_argument("--reliability", type=Path)
    esii_parser.add_argument("--energy", type=Path)
    esii_parser.add_argument("--area", type=Path)
    esii_parser.add_argument("--fit-base", type=float)
    esii_parser.add_argument("--fit-ecc", type=float)
    esii_parser.add_argument("--e-dyn-j", type=float)
    esii_parser.add_argument("--e-leak-j", type=float)
    esii_parser.add_argument("--ci", type=float, required=True)
    esii_parser.add_argument("--embodied-kgco2e", type=float)
    esii_parser.add_argument(
        "--embodied-override-kgco2e",
        type=str,
        default="none",
        help="Use this embodied carbon value instead of computing from area",
    )
    esii_parser.add_argument(
        "--basis", choices=["per_gib", "system"], required=True
    )
    esii_parser.add_argument("--out", type=Path)

    select_parser = sub.add_parser(
        "select", help="Multi-objective ECC selection"
    )
    select_parser.add_argument(
        "--codes",
        type=str,
        required=True,
        help="Comma separated code identifiers",
    )
    select_parser.add_argument(
        "--weights",
        type=str,
        default="1.0,1.0,0.25",
        help="Comma separated weights for reliability, carbon, latency",
    )
    select_parser.add_argument(
        "--constraints",
        type=str,
        default="",
        help="Comma separated key=value constraints",
    )
    select_parser.add_argument("--node", type=int, required=True)
    select_parser.add_argument("--vdd", type=float, required=True)
    select_parser.add_argument("--temp", type=float, required=True)
    select_parser.add_argument("--mbu", type=str, default="moderate")
    select_parser.add_argument("--scrub-s", type=float, default=10.0)
    select_parser.add_argument("--alt-km", type=float, default=0.0)
    select_parser.add_argument("--latitude", type=float, default=45.0)
    select_parser.add_argument("--flux-rel", type=float, default=None)
    select_parser.add_argument("--capacity-gib", type=float, required=True)
    select_parser.add_argument("--ci", type=float, required=True)
    select_parser.add_argument("--bitcell-um2", type=float, required=True)
    select_parser.add_argument("--lifetime-h", type=float, default=float("nan"))
    select_parser.add_argument("--ci-source", type=str, default="unspecified")
    select_parser.add_argument("--report", type=Path, default=None)
    select_parser.add_argument("--plot", type=Path, default=None)
    select_parser.add_argument(
        "--emit-candidates", type=Path, default=None, help="Write feasible candidates to CSV"
    )
    select_parser.add_argument(
        "--carbon-policy",
        choices=["minimum_total_carbon", "minimum_dynamic_carbon", "minimum_static_carbon", "balanced_carbon_energy"],
        default=None,
        help="Optional carbon ranking mode; default preserves existing selector behavior",
    )

    target_parser = sub.add_parser(
        "target", help="Min-carbon ECC meeting BER/UWER target"
    )
    target_parser.add_argument(
        "--codes",
        type=str,
        required=True,
        help="Comma separated code identifiers",
    )
    target_parser.add_argument(
        "--target-type",
        choices=["bit", "uwer"],
        required=True,
        help="Reliability metric to constrain",
    )
    target_parser.add_argument("--target", type=float, required=True)
    target_parser.add_argument("--node", type=int, required=True)
    target_parser.add_argument("--vdd", type=float, required=True)
    target_parser.add_argument("--temp", type=float, required=True)
    target_parser.add_argument("--mbu", type=str, default="moderate")
    target_parser.add_argument("--scrub-s", type=float, default=10.0)
    target_parser.add_argument("--alt-km", type=float, default=0.0)
    target_parser.add_argument("--latitude", type=float, default=45.0)
    target_parser.add_argument("--flux-rel", type=float, default=None)
    target_parser.add_argument("--capacity-gib", type=float, required=True)
    target_parser.add_argument("--ci", type=float, required=True)
    target_parser.add_argument("--bitcell-um2", type=float, required=True)
    target_parser.add_argument("--lifetime-h", type=float, default=float("nan"))
    target_parser.add_argument("--ci-source", type=str, default="unspecified")
    target_parser.add_argument(
        "--feasible", type=Path, default=Path("feasible.csv"), help="Feasible set CSV"
    )
    target_parser.add_argument(
        "--choice", type=Path, default=Path("choice.json"), help="Chosen point JSON"
    )

    analyze_parser = sub.add_parser("analyze", help="Post-selection analysis")
    analyze_sub = analyze_parser.add_subparsers(dest="analyze_command")

    trade_parser = analyze_sub.add_parser("tradeoffs", help="Quantify trade-offs")
    trade_parser.add_argument("--from", dest="from_csv", type=Path, required=True)
    trade_parser.add_argument("--out", type=Path, required=True)
    trade_parser.add_argument("--basis", choices=["per_gib", "system"], default="per_gib")
    trade_parser.add_argument("--filter", type=str, default=None)
    trade_parser.add_argument("--seed", type=int, default=0)
    trade_parser.add_argument("--bootstrap", type=int, default=20000)

    arch_parser = analyze_sub.add_parser("archetype", help="Classify archetypes")
    arch_parser.add_argument("--from", dest="from_csv", type=Path, required=True)
    arch_parser.add_argument("--out", type=Path, required=True)

    surface_parser = analyze_sub.add_parser(
        "surface", help="Analyse feasible surface from candidates"
    )
    surface_parser.add_argument(
        "--from-candidates", dest="cand_csv", type=Path, required=True
    )
    surface_parser.add_argument("--out-csv", dest="out_csv", type=Path, required=True)
    surface_parser.add_argument("--plot", type=Path, default=None)

    sens_parser = analyze_sub.add_parser(
        "sensitivity", help="Sensitivity analysis (one or two factors)"
    )
    sens_parser.add_argument("--factor", type=str, required=True)
    sens_parser.add_argument("--grid", type=str, required=True)
    sens_parser.add_argument("--factor2", type=str, default=None)
    sens_parser.add_argument("--grid2", type=str, default=None)
    sens_parser.add_argument("--csv", type=Path, default=None)
    sens_parser.add_argument("--from", dest="from_json", type=Path, required=True)
    sens_parser.add_argument("--out", type=Path, required=True)

    plot_parser = sub.add_parser("plot", help="Strict factual plotting")
    plot_sub = plot_parser.add_subparsers(dest="plot_command")

    plot_pareto = plot_sub.add_parser("pareto", help="Generate scenario-exact Pareto plot")
    plot_pareto.add_argument("--from", dest="from_path", type=Path, required=True)
    plot_pareto.add_argument("--x", type=str, default="carbon_kg")
    plot_pareto.add_argument("--y", type=str, default="FIT")
    plot_pareto.add_argument("--x-objective", choices=["min", "max"], default="min")
    plot_pareto.add_argument("--y-objective", choices=["min", "max"], default="min")
    plot_pareto.add_argument("--out", type=Path, required=True)
    plot_pareto.add_argument("--codes", type=str, default=None)
    plot_pareto.add_argument("--node", type=int, default=None)
    plot_pareto.add_argument("--vdd", type=float, default=None)
    plot_pareto.add_argument("--temp", type=float, default=None)
    plot_pareto.add_argument("--scrub-interval-s", dest="scrub_interval_s", type=float, default=None)
    plot_pareto.add_argument("--capacity-gib", type=float, default=None)
    plot_pareto.add_argument("--target-ber", dest="target_ber", type=float, default=None)
    plot_pareto.add_argument("--burst-length", dest="burst_length", type=int, default=None)
    plot_pareto.add_argument("--required-bits", dest="required_bits", type=int, default=None)
    plot_pareto.add_argument("--sustainability", dest="sustainability", action="store_true")
    plot_pareto.add_argument("--energy-budget-nj", dest="energy_budget_nj", type=float, default=None)
    plot_pareto.add_argument("--show-dominated", action="store_true")
    plot_pareto.add_argument("--save-metadata", action=argparse.BooleanOptionalAction, default=True)
    plot_pareto.add_argument("--strict-scenario", action=argparse.BooleanOptionalAction, default=True)
    plot_pareto.add_argument("--error-on-empty", action=argparse.BooleanOptionalAction, default=True)
    plot_pareto.add_argument("--log-x", action="store_true")
    plot_pareto.add_argument("--log-y", action="store_true")
    reliability_parser = sub.add_parser(
        "reliability", help="Reliability calculations"
    )
    reliability_sub = reliability_parser.add_subparsers(dest="reliability_command")

    hazucha_parser = reliability_sub.add_parser(
        "hazucha", help="Hazucha-Svensson SER model"
    )
    hazucha_parser.add_argument("--qcrit", type=float, required=True)
    hazucha_parser.add_argument("--qs", type=float, required=True)
    hazucha_parser.add_argument("--area", type=float, required=True)
    hazucha_parser.add_argument("--alt-km", type=float, default=0.0)
    hazucha_parser.add_argument("--latitude", type=float, default=45.0)
    hazucha_parser.add_argument("--flux-rel", type=float, default=None)

    report_parser = reliability_sub.add_parser(
        "report", help="Generate reliability report"
    )
    report_parser.add_argument("--qcrit", type=float, default=None)
    report_parser.add_argument("--qs", type=float, required=True)
    report_parser.add_argument("--area", type=float, required=True)
    report_parser.add_argument("--alt-km", type=float, default=0.0)
    report_parser.add_argument("--latitude", type=float, default=45.0)
    report_parser.add_argument("--flux-rel", type=float, default=None)
    report_parser.add_argument("--word-bits", type=int, default=64)
    report_parser.add_argument(
        "--ecc",
        type=str,
        default="SEC-DED",
        choices=["SEC-DED", "SEC-DAEC", "TAEC", "POLAR", "POLAR-64-32", "POLAR-64-48", "POLAR-128-96"],
    )
    report_parser.add_argument("--scrub-interval", type=float, default=0.0)
    report_parser.add_argument("--capacity-gib", type=float, default=1.0)
    report_parser.add_argument("--basis", choices=["per_gib", "system"], default="per_gib")
    report_parser.add_argument(
        "--mbu", type=str, default="moderate", choices=["none", "light", "moderate", "heavy"]
    )
    report_parser.add_argument("--node-nm", type=int, required=True)
    report_parser.add_argument("--vdd", type=float, required=True)
    report_parser.add_argument("--tempC", type=float, required=True)
    report_parser.add_argument("--json", action="store_true")

    sram_parser = sub.add_parser("sram", help="SRAM-oriented ECC workflows")
    sram_sub = sram_parser.add_subparsers(dest="sram_command")

    sram_sim = sram_sub.add_parser("simulate", help="Run SRAM ECC simulation")
    sram_sim.add_argument("--size-kb", type=int, required=True, choices=[64, 128, 256])
    sram_sim.add_argument("--word-bits", type=int, required=True, choices=[8, 16, 32])
    sram_sim.add_argument("--scheme", type=str, required=True, choices=["sec-ded", "taec", "bch", "polar"])
    sram_sim.add_argument("--iterations", type=int, default=5000)
    sram_sim.add_argument("--seed", type=int, default=42)
    sram_sim.add_argument("--fault-model", type=str, default="adjacent")
    sram_sim.add_argument("--json", action="store_true")
    sram_sim.add_argument("--out-csv", type=Path, default=None)

    sram_stress = sram_sub.add_parser("stress", help="Run SRAM stress campaign")
    sram_stress.add_argument("--size-kb", type=int, required=True, choices=[64, 128, 256])
    sram_stress.add_argument("--word-bits", type=int, required=True, choices=[8, 16, 32])
    sram_stress.add_argument("--scheme", type=str, required=True, choices=["sec-ded", "taec", "bch", "polar"])
    sram_stress.add_argument("--iterations", type=int, default=20000)
    sram_stress.add_argument("--seed", type=int, default=42)
    sram_stress.add_argument("--fault-model", type=str, default="geoburst")
    sram_stress.add_argument("--json", action="store_true")
    sram_stress.add_argument("--out-csv", type=Path, default=None)

    sram_cmp = sram_sub.add_parser("compare", help="Compare SRAM ECC schemes")
    sram_cmp.add_argument("--size-kb", type=int, required=True, choices=[64, 128, 256])
    sram_cmp.add_argument("--word-bits", type=int, required=True, choices=[8, 16, 32])
    sram_cmp.add_argument("--schemes", type=str, default="sec-ded,taec,bch,polar")
    sram_cmp.add_argument("--iterations", type=int, default=10000)
    sram_cmp.add_argument("--seed", type=int, default=42)
    sram_cmp.add_argument("--fault-model", type=str, default="adjacent")
    sram_cmp.add_argument("--json", action="store_true")
    sram_cmp.add_argument("--out-csv", type=Path, default=None)

    sram_sel = sram_sub.add_parser("select", help="SRAM-aware deterministic ECC selection")
    sram_sel.add_argument("--size-kb", type=int, required=True, choices=[64, 128, 256])
    sram_sel.add_argument("--word-bits", type=int, required=True, choices=[8, 16, 32])
    sram_sel.add_argument("--schemes", type=str, default="sec-ded,taec,bch,polar")
    sram_sel.add_argument("--node", type=int, required=True)
    sram_sel.add_argument("--vdd", type=float, required=True)
    sram_sel.add_argument("--temp", type=float, required=True)
    sram_sel.add_argument("--ci", type=float, required=True)
    sram_sel.add_argument("--bitcell-um2", type=float, required=True)
    sram_sel.add_argument("--lifetime-h", type=float, default=float("nan"))
    sram_sel.add_argument("--mbu", type=str, default="moderate")
    sram_sel.add_argument("--scrub-s", type=float, default=10.0)
    sram_sel.add_argument("--alt-km", type=float, default=0.0)
    sram_sel.add_argument("--latitude", type=float, default=45.0)
    sram_sel.add_argument("--flux-rel", type=float, default=None)
    sram_sel.add_argument("--report", type=Path, default=None)
    sram_sel.add_argument("--emit-candidates", type=Path, default=None)
    sram_sel.add_argument("--ml-model", type=Path, default=None)
    sram_sel.add_argument("--ml-confidence-min", type=float, default=None)
    sram_sel.add_argument("--ml-ood-max", type=float, default=None)
    sram_sel.add_argument(
        "--ml-policy",
        choices=["carbon_min", "fit_min", "energy_min", "utility_balanced"],
        default=None,
    )
    ml_parser = sub.add_parser("ml", help="Optional ML advisory workflows")
    ml_sub = ml_parser.add_subparsers(dest="ml_command")

    ml_build = ml_sub.add_parser("build-dataset", help="Build ML dataset from ECC artifacts")
    ml_build.add_argument("--from", dest="from_dir", type=Path, required=True)
    ml_build.add_argument("--out", dest="out_dir", type=Path, required=True)
    ml_build.add_argument("--seed", type=int, default=1)
    ml_build.add_argument(
        "--label-policy",
        choices=["carbon_min", "fit_min", "energy_min", "utility_balanced"],
        default="carbon_min",
    )
    ml_build.add_argument("--utility-alpha-fit", type=float, default=1.0)
    ml_build.add_argument("--utility-beta-carbon", type=float, default=1.0)
    ml_build.add_argument("--utility-gamma-energy", type=float, default=1.0)
    ml_build.add_argument("--split-strategy", choices=["random", "scenario_hash"], default="scenario_hash")
    ml_build.add_argument(
        "--feature-pack",
        choices=["core", "core+telemetry", "core+telemetry+workload"],
        default="core",
    )
    ml_build.add_argument(
        "--enable-feature",
        action="append",
        default=[],
        help="Repeatable optional feature enable list",
    )
    ml_build.add_argument(
        "--disable-feature",
        action="append",
        default=[],
        help="Repeatable optional feature disable list",
    )

    ml_split = ml_sub.add_parser("split-dataset", help="Create deterministic ML train/validation/holdout splits")
    ml_split.add_argument("--dataset", type=Path, required=True, help="Dataset directory")
    ml_split.add_argument("--out", type=Path, default=None, help="Optional split output file (default: <dataset>/dataset_splits.json)")
    ml_split.add_argument("--seed", type=int, default=1)
    ml_split.add_argument("--train-ratio", type=float, default=0.7)
    ml_split.add_argument("--validation-ratio", type=float, default=0.15)
    ml_split.add_argument("--holdout-ratio", type=float, default=0.15)
    ml_split.add_argument("--group-column", default="scenario_hash")

    ml_train = ml_sub.add_parser("train", help="Train ML advisory model")
    ml_train.add_argument("--dataset", type=Path, required=True, help="Dataset directory")
    ml_train.add_argument("--model-out", type=Path, required=True)
    ml_train.add_argument("--seed", type=int, default=1)
    ml_train.add_argument("--model-type", choices=["rf", "gbdt", "linear"], default="rf")
    ml_train.add_argument("--calibrate-confidence", choices=["none", "isotonic", "platt"], default="none")
    ml_train.add_argument("--confidence-target-metric", choices=["accuracy", "f1_macro"], default="accuracy")
    ml_train.add_argument("--ood-method", choices=["zscore", "mahalanobis", "iforest"], default="zscore")
    ml_train.add_argument("--ood-quantile", type=_bounded_open_01, default=0.995)
    ml_train.add_argument("--conformal-alpha", type=_bounded_open_01, default=0.1)

    ml_eval = ml_sub.add_parser("evaluate", help="Evaluate ML advisory model")
    ml_eval.add_argument("--dataset", type=Path, required=True, help="Dataset directory")
    ml_eval.add_argument("--model", type=Path, required=True, help="Model directory")
    ml_eval.add_argument("--out", type=Path, required=True, help="Evaluation output directory")
    ml_eval.add_argument("--policy", choices=["carbon_min", "fit_min", "energy_min", "utility_balanced"], default=None)
    ml_eval.add_argument("--ood-threshold", type=float, default=None)
    ml_eval.add_argument("--split", choices=["all", "train", "validation", "holdout"], default="all")
    ml_eval.add_argument("--signoff-thresholds", type=Path, default=None)
    ml_eval.add_argument("--strict-signoff", action="store_true")
    ml_eval.add_argument("--json", action="store_true")

    ml_drift = ml_sub.add_parser("check-drift", help="Compute ML data drift report")
    ml_drift.add_argument("--model", type=Path, required=True, help="Model directory")
    ml_drift.add_argument("--new-data", type=Path, required=True, help="New dataset directory")
    ml_drift.add_argument("--out", type=Path, default=Path("drift.json"), help="Drift report path")
    ml_drift.add_argument(
        "--drift-policy-out",
        type=Path,
        default=None,
        help="Optional drift policy action report path (separate file to preserve drift.json schema)",
    )
    ml_drift.add_argument("--fail-on-drift", action="store_true")
    ml_report_card = ml_sub.add_parser("report-card", help="Generate consolidated model report card")
    ml_report_card.add_argument("--model", type=Path, required=True, help="Model directory")
    ml_report_card.add_argument(
        "--out",
        type=Path,
        default=Path("model_card.md"),
        help="Markdown output path (relative paths are resolved from current working directory)",
    )

    eval_parser = sub.add_parser("evaluate", help="Integrated SRAM ECC evaluation toolkit")
    eval_parser.add_argument("--capacity", type=float, required=True, help="SRAM capacity in GiB")
    eval_parser.add_argument("--word-length", type=int, required=True)
    eval_parser.add_argument("--node", type=int, required=True)
    eval_parser.add_argument("--vdd", type=float, required=True)
    eval_parser.add_argument("--temp", type=float, required=True)
    eval_parser.add_argument("--ber", type=float, default=None)
    eval_parser.add_argument("--ser", type=float, default=None)
    eval_parser.add_argument("--altitude", type=float, default=0.0, help="Altitude in km")
    eval_parser.add_argument("--burst-length", type=int, default=1)
    eval_parser.add_argument("--fault-modes", nargs="+", default=["sbu", "dbu", "mbu", "burst"])
    eval_parser.add_argument("--ci", type=float, default=0.55)
    eval_parser.add_argument("--grid-score", type=float, default=None)
    eval_parser.add_argument("--sustainability-mode", action="store_true")
    eval_parser.add_argument("--ml-enabled", action="store_true")
    eval_parser.add_argument("--ml-model", type=Path, default=None)
    eval_parser.add_argument("--ml-confidence-min", type=float, default=None)
    eval_parser.add_argument("--ml-ood-max", type=float, default=None)
    eval_parser.add_argument("--outdir", type=Path, required=True)

    compare_parser = sub.add_parser("compare", help="Run integrated evaluation from JSON config")
    compare_parser.add_argument("--input-config", type=Path, required=True)
    compare_parser.add_argument("--outdir", type=Path, required=True)

    pareto_parser = sub.add_parser("pareto", help="Generate pareto plots from integrated CSV")
    pareto_parser.add_argument("--input", type=Path, required=True)
    pareto_parser.add_argument("--outdir", type=Path, required=True)

    report_top = sub.add_parser("report", help="Regenerate integrated report from all_candidates.csv")
    report_top.add_argument("--input", type=Path, required=True)
    report_top.add_argument("--outdir", type=Path, required=True)

    ml_infer = sub.add_parser("ml-infer", help="Run integrated evaluation in ML-advisory mode")
    ml_infer.add_argument("--input-config", type=Path, required=True)
    ml_infer.add_argument("--model", type=Path, required=True)
    ml_infer.add_argument("--outdir", type=Path, required=True)

    args = parser.parse_args()

    if args.command == "evaluate":
        cfg = ToolkitInput(
            sram_capacity_gib=args.capacity,
            word_length_bits=args.word_length,
            tech_node_nm=args.node,
            vdd_volts=args.vdd,
            temperature_c=args.temp,
            ber=args.ber,
            ser=args.ser,
            altitude_km=args.altitude,
            burst_length=args.burst_length,
            fault_modes=tuple(args.fault_modes),
            carbon_intensity_kgco2_per_kwh=args.ci,
            grid_score=args.grid_score,
            sustainability_mode=bool(args.sustainability_mode),
            ml_enabled=bool(args.ml_enabled),
            ml_model=args.ml_model,
            ml_confidence_min=args.ml_confidence_min,
            ml_ood_max=args.ml_ood_max,
            output_dir=args.outdir,
        )
        result = evaluate_toolkit(cfg)
        print(json.dumps(result, indent=2, sort_keys=True))
        return

    if args.command in {"compare", "ml-infer"}:
        payload = _load_json(args.input_config)
        payload["output_dir"] = Path(args.outdir)
        if args.command == "ml-infer":
            payload["ml_enabled"] = True
            payload["ml_model"] = Path(args.model)
        cfg = ToolkitInput(**payload)
        result = evaluate_toolkit(cfg)
        print(json.dumps(result, indent=2, sort_keys=True))
        return

    if args.command == "pareto":
        from analysis.plot_pipeline import PlotRequest, generate_pareto_plot

        outdir = Path(args.outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        img = outdir / "pareto_energy_vs_reliability.png"
        generate_pareto_plot(
            PlotRequest(
                from_path=args.input,
                out_path=img,
                x="energy_total_j",
                y="FIT",
                scenario_filters={},
                show_dominated=True,
                save_metadata=True,
                strict_scenario=False,
                error_on_empty=False,
                log_x=False,
                log_y=True,
                x_objective="min",
                y_objective="min",
                allow_recompute=False,
            )
        )
        print(str(img))
        return

    if args.command == "report":
        rows = []
        with args.input.open("r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
        outdir = Path(args.outdir)
        summary = outdir / "summary"
        summary.mkdir(parents=True, exist_ok=True)
        payload = {
            "rows": len(rows),
            "columns": list(rows[0].keys()) if rows else [],
            "note": "Generated from existing all_candidates.csv; no recomputation performed.",
        }
        (summary / "integrated_report.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        (summary / "integrated_report.md").write_text("# Integrated Report\n\n" + json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload, indent=2))
        return

    if args.command == "ml":
        if args.ml_command == "build-dataset":
            from ml.dataset import build_dataset

            try:
                artifacts = build_dataset(
                    args.from_dir,
                    args.out_dir,
                    seed=args.seed,
                    label_policy=args.label_policy,
                    utility_alpha_fit=args.utility_alpha_fit,
                    utility_beta_carbon=args.utility_beta_carbon,
                    utility_gamma_energy=args.utility_gamma_energy,
                    split_strategy=args.split_strategy,
                    feature_pack=args.feature_pack,
                    enable_features=args.enable_feature,
                    disable_features=args.disable_feature,
                )
            except ValueError as exc:
                parser.error(str(exc))
            for key in ("dataset", "schema", "manifest"):
                print(f"{key}: {artifacts[key]}")
        elif args.ml_command == "split-dataset":
            from ml.splits import create_deterministic_splits
            try:
                split_path = create_deterministic_splits(
                    args.dataset,
                    args.out,
                    seed=args.seed,
                    train_ratio=args.train_ratio,
                    validation_ratio=args.validation_ratio,
                    holdout_ratio=args.holdout_ratio,
                    group_column=args.group_column,
                )
            except FileNotFoundError as exc:
                ml_split.error(
                    f"{exc}. Run `ml build-dataset --from <artifacts_dir> --out {args.dataset}` first."
                )
            print(f"splits: {split_path}")
        elif args.ml_command == "train":
            from ml.train import train_models

            artifacts = train_models(
                args.dataset,
                args.model_out,
                seed=args.seed,
                model_type=args.model_type,
                calibrate_confidence=args.calibrate_confidence,
                confidence_target_metric=args.confidence_target_metric,
                ood_method=args.ood_method,
                ood_quantile=args.ood_quantile,
                conformal_alpha=args.conformal_alpha,
            )
            for key in ("model", "metrics", "features", "thresholds", "uncertainty", "model_card"):
                print(f"{key}: {artifacts[key]}")
        elif args.ml_command == "evaluate":
            from ml.evaluate import evaluate_model

            artifacts = evaluate_model(
                args.dataset,
                args.model,
                args.out,
                policy=args.policy,
                ood_threshold=args.ood_threshold,
                split=args.split,
                signoff_thresholds=args.signoff_thresholds,
                strict_signoff=args.strict_signoff,
            )
            if args.json:
                print(json.dumps({k: str(v) for k, v in artifacts.items()}, indent=2, sort_keys=True))
            else:
                for key in ("evaluation", "holdout_report", "signoff"):
                    if key in artifacts:
                        print(f"{key}: {artifacts[key]}")
        elif args.ml_command == "check-drift":
            from ml.drift import check_drift

            artifacts = check_drift(
                args.model,
                args.new_data,
                args.out,
                policy_out_path=args.drift_policy_out,
            )
            print(f"drift: {artifacts['drift']}")
            if "drift_policy" in artifacts:
                print(f"drift_policy: {artifacts['drift_policy']}")
            if args.fail_on_drift and bool(artifacts["drift_detected"]):
                raise SystemExit(2)
        elif args.ml_command == "report-card":
            from ml.report_card import generate_report_card

            artifacts = generate_report_card(args.model, args.out)
            for key in ("report_card",):
                print(f"{key}: {artifacts[key]}")
        else:
            parser.error("ml subcommand required")
        return

    if args.command == "sram":
        repo_root = Path(__file__).resolve().parent
        if args.sram_command in {"simulate", "stress", "compare"}:
            if args.sram_command in {"simulate", "stress"}:
                schemes = [args.scheme]
            else:
                schemes = [c.strip() for c in args.schemes.split(",") if c.strip()]
            try:
                result = run_sram_backend(
                    repo_root=repo_root,
                    mode=args.sram_command,
                    size_kb=args.size_kb,
                    word_bits=args.word_bits,
                    schemes=schemes,
                    iterations=args.iterations,
                    seed=args.seed,
                    fault_model=args.fault_model,
                )
            except Exception as exc:
                parser.error(str(exc))

            if args.out_csv:
                write_sram_records_csv(args.out_csv, result["records"])

            if args.json:
                print(json.dumps(result, indent=2, sort_keys=True))
            else:
                records = result.get("records", [])
                print(f"backend={result['backend']} scenario_hash={result['scenario_hash']} records={len(records)}")
                for rec in records:
                    print(
                        f"{rec['codec']} reliability={rec['reliability_success']:.4f} "
                        f"sdc={rec['sdc_rate']:.3e} energy_proxy={rec['energy_proxy']:.4f} "
                        f"latency_proxy={rec['latency_proxy']:.4f} utility={rec['utility']:.4f}"
                    )
            return

        if args.sram_command == "select":
            schemes = [c.strip() for c in args.schemes.split(",") if c.strip()]
            try:
                result = run_sram_selection(
                    schemes=schemes,
                    size_kb=args.size_kb,
                    word_bits=args.word_bits,
                    node=args.node,
                    vdd=args.vdd,
                    temp=args.temp,
                    ci=args.ci,
                    bitcell_um2=args.bitcell_um2,
                    lifetime_h=args.lifetime_h,
                    mbu=args.mbu,
                    scrub_s=args.scrub_s,
                    flux_rel=args.flux_rel,
                    alt_km=args.alt_km,
                    latitude_deg=args.latitude,
                    ml_model=args.ml_model,
                    ml_confidence_min=args.ml_confidence_min,
                    ml_ood_max=args.ml_ood_max,
                    ml_policy=args.ml_policy,
                )
            except Exception as exc:
                parser.error(str(exc))

            if args.report:
                args.report.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
            if args.emit_candidates:
                import csv

                rows = result.get("candidate_records", [])
                if rows:
                    fieldnames = list(rows[0].keys())
                else:
                    fieldnames = ["code", "FIT", "carbon_kg", "latency_ns", "ESII", "NESII", "GS"]
                with args.emit_candidates.open("w", newline="", encoding="utf-8") as fh:
                    writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
                    writer.writeheader()
                    for row in rows:
                        writer.writerow(row)

            if result.get("best"):
                best = result["best"]
                print(f"{best['code']} ESII={best['ESII']:.3g} NESII={best['NESII']:.2f} GS={best['GS']:.2f}")
            return

        parser.error("sram subcommand required")

    if args.command == "plot":
        if args.plot_command == "pareto":
            from analysis.plot_pipeline import PlotRequest, generate_pareto_plot

            scenario_filters = {
                "codes": args.codes,
                "node": args.node,
                "vdd": args.vdd,
                "temp": args.temp,
                "scrub_interval_s": args.scrub_interval_s,
                "capacity_gib": args.capacity_gib,
                "target_ber": args.target_ber,
                "burst_length": args.burst_length,
                "required_bits": args.required_bits,
                "sustainability": True if args.sustainability else None,
                "energy_budget_nj": args.energy_budget_nj,
            }
            try:
                result = generate_pareto_plot(
                    PlotRequest(
                        from_path=args.from_path,
                        out_path=args.out,
                        x=args.x,
                        y=args.y,
                        scenario_filters=scenario_filters,
                        show_dominated=args.show_dominated,
                        save_metadata=args.save_metadata,
                        strict_scenario=args.strict_scenario,
                        error_on_empty=args.error_on_empty,
                        log_x=args.log_x,
                        log_y=args.log_y,
                        x_objective=args.x_objective,
                        y_objective=args.y_objective,
                        allow_recompute=True,
                    )
                )
            except Exception as exc:
                plot_pareto.error(str(exc))

            print(
                f"plot={result.out_path} rows_loaded={result.rows_loaded} "
                f"rows_filtered={result.rows_filtered} rows_plotted={result.rows_plotted}"
            )
            if result.metadata_path is not None:
                print(f"metadata={result.metadata_path}")
        else:
            parser.error("plot subcommand required")
        return
    if args.command == "analyze":
        if args.analyze_command == "tradeoffs":
            from analysis.tradeoff import TradeoffConfig, analyze_tradeoffs

            cfg = TradeoffConfig(
                n_resamples=args.bootstrap,
                seed=args.seed,
                filter_expr=args.filter,
                basis=args.basis,
            )
            analyze_tradeoffs(args.from_csv, args.out, cfg)
        elif args.analyze_command == "archetype":
            from analysis.archetype import classify_archetypes

            classify_archetypes(args.from_csv, args.out)
        elif args.analyze_command == "surface":
            from analysis.surface import analyze_surface
            try:
                analyze_surface(args.cand_csv, args.out_csv, args.plot)
            except FileNotFoundError as exc:
                surface_parser.error(
                    f"{exc}. Generate candidates first via `select --emit-candidates <path>` "
                    "or point --from-candidates to an existing CSV."
                )
        elif args.analyze_command == "sensitivity":
            from analysis.sensitivity import analyze_sensitivity
            if (args.factor2 is None) != (args.grid2 is None):
                sens_parser.error("--factor2 and --grid2 must be provided together")

            grid_vals = [float(x) for x in args.grid.split(",") if x.strip()]
            grid2_vals = (
                [float(x) for x in args.grid2.split(",") if x.strip()]
                if args.grid2
                else None
            )
            analyze_sensitivity(
                args.from_json,
                args.factor,
                grid_vals,
                args.out,
                args.factor2,
                grid2_vals,
                args.csv,
            )
        else:
            parser.error("analyze subcommand required")
        return

    if args.command == "select":
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]
        try:
            w_vals = [float(x) for x in args.weights.split(",")]
            weights = {
                "reliability": w_vals[0],
                "carbon": w_vals[1],
                "latency": w_vals[2] if len(w_vals) > 2 else 0.0,
            }
        except Exception:
            parser.error("--weights must be three comma separated floats")

        constraints: Dict[str, float] = {}
        if args.constraints:
            for part in args.constraints.split(","):
                if not part:
                    continue
                try:
                    k, v = part.split("=")
                    constraints[k] = float(v)
                except Exception:
                    parser.error("Invalid constraint format")

        params = {
            "node": args.node,
            "vdd": args.vdd,
            "temp": args.temp,
            "capacity_gib": args.capacity_gib,
            "ci": args.ci,
            "bitcell_um2": args.bitcell_um2,
            "lifetime_h": args.lifetime_h,
            "ci_source": args.ci_source,
        }

        result = select(
            codes,
            weights=weights,
            constraints=constraints,
            mbu=args.mbu,
            scrub_s=args.scrub_s,
            alt_km=args.alt_km,
            latitude_deg=args.latitude,
            flux_rel=args.flux_rel,
            carbon_policy=getattr(args, "carbon_policy", None),
            **params,
        )

        if args.report:
            import csv

            fieldnames = [
                "code",
                "scrub_s",
                "FIT",
                "carbon_kg",
                "latency_ns",
                "ESII",
                "NESII",
                "GS",
                "p5",
                "p95",
                "N_scale",
                "area_logic_mm2",
                "area_macro_mm2",
                "E_dyn_kWh",
                "E_leak_kWh",
                "E_scrub_kWh",
                "notes",
            ]
            with open(args.report, "w", newline="") as fh:
                writer = csv.DictWriter(
                    fh, fieldnames=fieldnames, extrasaction="ignore"
                )
                writer.writeheader()
                for rec in result["pareto"]:
                    writer.writerow(rec)

        if args.emit_candidates:
            import csv

            fieldnames = list(SELECT_CANDIDATE_CSV_FIELDS)
            with open(args.emit_candidates, "w", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=fieldnames)
                writer.writeheader()
                for rec in result.get("candidate_records", []):
                    areas = {
                        "logic_mm2": rec.get("area_logic_mm2", 0.0),
                        "macro_mm2": rec.get("area_macro_mm2", 0.0),
                    }
                    energies = {
                        "E_dyn_kWh": rec.get("E_dyn_kWh", 0.0),
                        "E_leak_kWh": rec.get("E_leak_kWh", 0.0),
                        "E_scrub_kWh": rec.get("E_scrub_kWh", 0.0),
                    }
                    row = {
                        "code": rec.get("code"),
                        "scrub_s": rec.get("scrub_s"),
                        "FIT": rec.get("FIT"),
                        "carbon_kg": rec.get("carbon_kg"),
                        "latency_ns": rec.get("latency_ns"),
                        "ESII": rec.get("ESII"),
                        "NESII": rec.get("NESII"),
                        "areas": json.dumps(areas, sort_keys=True),
                        "energies": json.dumps(energies, sort_keys=True),
                        "violations": json.dumps(rec.get("violations", []), sort_keys=True),
                        "scenario_hash": result.get("scenario_hash"),
                    }
                    writer.writerow(row)

        if args.plot:
            from analysis.plot_pipeline import generate_pareto_plot_from_records

            scenario_for_plot = {
                "codes": codes,
                "node": args.node,
                "vdd": args.vdd,
                "temp": args.temp,
                "mbu": args.mbu,
                "scrub_s": args.scrub_s,
                "capacity_gib": args.capacity_gib,
                "ci": args.ci,
                "bitcell_um2": args.bitcell_um2,
                "alt_km": args.alt_km,
                "latitude_deg": args.latitude,
                "flux_rel": args.flux_rel,
                "lifetime_h": args.lifetime_h,
                "ci_source": args.ci_source,
            }
            try:
                generate_pareto_plot_from_records(
                    [dict(r) for r in result.get("candidate_records", [])],
                    out_path=args.plot,
                    x="carbon_kg",
                    y="FIT",
                    x_objective="min",
                    y_objective="min",
                    show_dominated=True,
                    save_metadata=True,
                    scenario=scenario_for_plot,
                    source_files=[str(args.emit_candidates)] if args.emit_candidates else None,
                )
            except Exception as exc:
                parser.error(str(exc))

        if result["best"]:
            best = result["best"]
            print(
                f"{best['code']} "
                f"ESII={best['ESII']:.3g} "
                f"NESII={best['NESII']:.2f} "
                f"GS={best['GS']:.2f}"
            )
        return

    if args.command == "target":
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]
        params = {
            "node": args.node,
            "vdd": args.vdd,
            "temp": args.temp,
            "capacity_gib": args.capacity_gib,
            "ci": args.ci,
            "bitcell_um2": args.bitcell_um2,
            "lifetime_h": args.lifetime_h,
            "ci_source": args.ci_source,
        }

        result = select(
            codes,
            mbu=args.mbu,
            scrub_s=args.scrub_s,
            alt_km=args.alt_km,
            latitude_deg=args.latitude,
            flux_rel=args.flux_rel,
            **params,
        )

        records = result.get("candidate_records", [])
        if args.target_type == "bit":
            def metric(rec):
                return rec.get("fit_bit", float("inf"))
        else:
            def metric(rec):
                return rec.get("fit_word_post", float("inf"))

        feasible = [r for r in records if metric(r) <= args.target]

        import csv
        fieldnames = list(TARGET_FEASIBLE_CSV_FIELDS)
        with open(args.feasible, "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for rec in feasible:
                writer.writerow(rec)

        provenance = {
            "git": _git_hash(repo_path),
            "tech_calib": _file_hash(repo_path / "tech_calib.json"),
            "scenario_hash": result.get("scenario_hash"),
        }

        if feasible:
            best = min(feasible, key=lambda r: (r["carbon_kg"], -r["NESII"]))
            choice = {
                "status": "ok",
                "target_type": args.target_type,
                "target": args.target,
                "scrub_s": args.scrub_s,
                "provenance": provenance,
                "choice": best,
            }
            print(
                f"{best['code']} "
                f"ESII={best['ESII']:.3g} "
                f"NESII={best['NESII']:.2f} "
                f"GS={best['GS']:.2f}"
            )
        else:
            nearest = min(records, key=lambda r: abs(metric(r) - args.target)) if records else None
            if nearest is not None:
                delta = metric(nearest) - args.target
                print(
                    f"No feasible candidate; nearest {nearest['code']} by {delta:+.3e}",
                    file=sys.stderr,
                )
            choice = {
                "status": "infeasible",
                "target_type": args.target_type,
                "target": args.target,
                "scrub_s": args.scrub_s,
                "provenance": provenance,
            }
            if nearest is not None:
                choice["nearest"] = {
                    "code": nearest["code"],
                    "metric": metric(nearest),
                    "delta": metric(nearest) - args.target,
                }

        json.dump(choice, open(args.choice, "w"))
        return

    if args.command == "esii":
        fit_base: float
        fit_ecc: float
        basis = args.basis

        if args.reliability:
            rel = _load_json(args.reliability)
            fit_base = rel["fit"]["base"]
            fit_ecc = rel["fit"]["ecc"]
            if rel.get("basis") and rel["basis"] != basis:
                parser.error("Basis mismatch between --basis and reliability report")
        else:
            if args.fit_base is None or args.fit_ecc is None:
                parser.error(
                    "Provide --reliability or both --fit-base and --fit-ecc"
                )
            fit_base = args.fit_base
            fit_ecc = args.fit_ecc

        if args.energy:
            energy = _load_json(args.energy)
            e_dyn_j = energy["dynamic_J"]
            e_leak_j = energy["leakage_J"]
        else:
            if args.e_dyn_j is None or args.e_leak_j is None:
                parser.error("Provide --energy or both --e-dyn-j and --e-leak-j")
            e_dyn_j = args.e_dyn_j
            e_leak_j = args.e_leak_j

        embodied: float | None = None
        if args.embodied_override_kgco2e.lower() != "none":
            embodied = float(args.embodied_override_kgco2e)
        elif args.embodied_kgco2e is not None:
            embodied = args.embodied_kgco2e
        elif args.area:
            area = _load_json(args.area)
            logic_mm2 = area["logic_mm2"]
            macro_mm2 = area["macro_mm2"]
            node_nm = area["node_nm"]
            alpha_logic, alpha_macro = default_alpha(node_nm)
            embodied = embodied_kgco2e(logic_mm2, macro_mm2, alpha_logic, alpha_macro)
        else:
            parser.error(
                "Provide --embodied-kgco2e, --area or --embodied-override-kgco2e"
            )

        inp = ESIIInputs(
            fit_base=fit_base,
            fit_ecc=fit_ecc,
            e_dyn=e_dyn_j,
            e_leak=e_leak_j,
            e_scrub=0.0,
            ci_kgco2e_per_kwh=args.ci,
            embodied_kgco2e=embodied,
        )
        result = compute_scores(inp, latency_ns=0.0)

        provenance = {
            "git": git_hash,
            "tech_calib": tech_hash,
            "qcrit": _file_hash(repo_path / "data" / "qcrit_sram6t.json"),
        }
        out = {
            "provenance": provenance,
            "basis": basis,
            "inputs": {
                "fit_base": fit_base,
                "fit_ecc": fit_ecc,
                "E_dyn_kWh": result["E_dyn_kWh"],
                "E_leak_kWh": result["E_leak_kWh"],
                "E_scrub_kWh": result["E_scrub_kWh"],
                "ci_kgCO2e_per_kWh": args.ci,
                "embodied_kgCO2e": embodied,
            },
            "carbon": {
                "operational_kgCO2e": result["operational_kgCO2e"],
                "embodied_kgCO2e": embodied,
                "total_kgCO2e": result["total_kgCO2e"],
            },
            "delta_FIT": result["delta_FIT"],
            "ESII": result["ESII"],
            "NESII": result["NESII"],
            "GS": result["GS"],
            "p5": result["p5"],
            "p95": result["p95"],
        }

        if args.out:
            json.dump(out, open(args.out, "w"))
        else:
            json.dump(out, sys.stdout)
            sys.stdout.write("\n")
        return

    if args.command == "carbon":
        try:
            area_logic, area_macro = [float(x) for x in args.areas.split(",")]
            alpha_logic, alpha_macro = [float(x) for x in args.alpha.split(",")]
        except Exception:
            parser.error("--areas and --alpha require two comma separated floats")

        embodied = embodied_kgco2e(area_logic, area_macro, alpha_logic, alpha_macro)
        operational = operational_kgco2e(args.Edyn, args.Eleak, args.ci, 0.0)
        total = embodied + operational

        if not args.calibrated:
            print(f"{'Embodied (kgCO2e)':<20} {embodied:.3f}")
            print(f"{'Operational (kgCO2e)':<20} {operational:.3f}")
            print(f"{'Total (kgCO2e)':<20} {total:.3f}")
            return

        energy_j = (args.Edyn + args.Eleak) * 3_600_000.0
        bounds = estimate_carbon_bounds(
            node_nm=args.node,
            energy_joules=energy_j,
            area_cm2=args.area_cm2,
            memory_bits=args.memory_bits,
            bitcell_area_um2=args.bitcell_area_um2,
            grid_region=args.grid_region,
            grid_factor_kgco2e_per_kwh=args.ci,
            years=args.years,
            accesses_per_day=args.accesses_per_day,
            total_accesses=args.total_accesses,
        )
        breakdown = carbon_breakdown(bounds=bounds)
        out = {
            "legacy": {
                "embodied_kgco2e": embodied,
                "operational_kgco2e": operational,
                "total_kgco2e": total,
            },
            "calibrated": {
                "nominal": bounds["nominal"],
                "best_case": bounds["best_case"],
                "worst_case": bounds["worst_case"],
                "score": breakdown,
                "assumptions": bounds["assumptions"],
            },
        }
        json.dump(out, sys.stdout)
        sys.stdout.write("\n")
        return

    if args.command == "energy":
        try:
            result = energy_report(
                args.code,
                args.node,
                args.vdd,
                args.temp,
                args.ops,
                args.lifetime_h,
                uncertainty_path=args.uncertainty_path,
                include_confidence=args.uncertainty_path is not None,
                strict_validation=args.strict_validation,
                max_relative_stddev=args.max_relative_stddev,
                strict_sanity=args.strict_sanity,
            )
        except (UncertaintyValidationError, OutputSanityError) as exc:
            energy_parser.error(str(exc))
        if args.report == "json":
            json.dump(result, sys.stdout)
            sys.stdout.write("\n")
        else:
            print(f"{'Dynamic (J)':<15} {result['dynamic_J']:.3e}")
            print(f"{'Leakage (J)':<15} {result['leakage_J']:.3e}")
            print(f"{'Total (J)':<15} {result['total_J']:.3e}")
        for warning in result.get("sanity_warnings", []):
            print(f"warning: {warning}", file=sys.stderr)
        return

    if args.command == "reliability":
        if args.reliability_command == "hazucha":
            flux = flux_from_location(
                args.alt_km, args.latitude, flux_rel=args.flux_rel
            )
            hp = HazuchaParams(
                Qs_fC=args.qs, flux_rel=flux, area_um2=args.area
            )
            fit = ser_hazucha(args.qcrit, hp)
            print(f"{fit:.3e}")
            return
        if args.reliability_command == "report":
            flux = flux_from_location(
                args.alt_km, args.latitude, flux_rel=args.flux_rel
            )
            hp = HazuchaParams(
                Qs_fC=args.qs, flux_rel=flux, area_um2=args.area
            )
            try:
                qcrit = (
                    args.qcrit
                    if args.qcrit is not None
                    else qcrit_lookup("sram6t", args.node_nm, args.vdd, args.tempC, 50)
                )
            except ValueError as exc:
                report_parser.error(str(exc))
            fit_bit = ser_hazucha(qcrit, hp)

            if args.mbu == "none":
                mbu_rates = {}
            else:
                mbu_dist = pmf_adjacent(
                    args.mbu, word_bits=args.word_bits, bitline_bits=args.word_bits
                )
                severity_scale = {
                    "light": 0.0,
                    "moderate": 1.0,
                    "heavy": 5.0,
                }.get(args.mbu, 1.0)
                mbu_rates = {
                    k: {
                        kind: fit_bit * args.word_bits * k * p * severity_scale
                        for kind, p in probs.items()
                    }
                    for k, probs in mbu_dist.items()
                }

            fit_pre = compute_fit_pre(args.word_bits, fit_bit, mbu_rates)
            coverage = ecc_coverage_factory(args.ecc, word_bits=args.word_bits)
            fit_post = compute_fit_post(
                args.word_bits, fit_bit, mbu_rates, coverage, args.scrub_interval
            )
            if args.basis == "system":
                fit_base = fit_system(args.capacity_gib, fit_pre)
                fit_ecc = fit_system(args.capacity_gib, fit_post)
            else:
                fit_base = fit_system(1.0, fit_pre)
                fit_ecc = fit_system(1.0, fit_post)

            fit_sys = fit_system(args.capacity_gib, fit_post)
            mttf = mttf_from_fit(
                fit_sys.nominal if isinstance(fit_sys, FitEstimate) else fit_sys
            )
            result = {
                "qcrit": qcrit,
                "qs": args.qs,
                "flux_rel": flux,
                "fit_bit": fit_bit,
                "fit_word_pre": fit_pre,
                "fit_word_post": fit_post,
                "fit_system": fit_sys,
                "mttf": mttf,
            }
            report_str = _format_reliability_report(result)
            if args.json:
                json_out = {
                    "basis": args.basis,
                    "fit": {
                        "base": fit_base.nominal
                        if isinstance(fit_base, FitEstimate)
                        else fit_base,
                        "ecc": fit_ecc.nominal
                        if isinstance(fit_ecc, FitEstimate)
                        else fit_ecc,
                    },
                    "mbu": args.mbu,
                    "scrub_s": args.scrub_interval,
                    "node_nm": args.node_nm,
                    "vdd": args.vdd,
                    "tempC": args.tempC,
                }
                json.dump(json_out, sys.stdout)
                sys.stdout.write("\n")
                print(report_str, file=sys.stderr)
            else:
                print(report_str)
            return

    # If no command is provided the parser will show usage via argparse


if __name__ == "__main__":
    main()



