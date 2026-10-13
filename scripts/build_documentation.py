#!/usr/bin/env python3
"""Regenerate and validate the complete GREENS documentation suite."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Iterable, Mapping
from urllib.parse import unquote

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from green_ecc_phy.hashing import scientific_file_sha256


EVALUATION = Path("green_ecc_physical_simulation/multi_ecc_evaluation")
REGISTRY = Path("green_ecc_physical_simulation/registry")
BEGIN = "<!-- BEGIN GENERATED:{name} -->"
END = "<!-- END GENERATED:{name} -->"
TARGET_DOCS = [
    Path("README.md"), Path("GREEN_ECC_PHY_TECHNICAL_GUIDE.md"),
    *[Path("docs") / name for name in (
        "index.md", "GETTING_STARTED.md", "USE_CASES.md", "CONCEPTS_AND_IDENTITIES.md",
        "SYSTEM_ARCHITECTURE.md", "INSTALLATION.md", "CLI_REFERENCE.md", "ECC_CATALOGUE.md",
        "VERIFICATION_METHODOLOGY.md", "CHARACTERIZATION_AND_EVIDENCE.md",
        "RELIABILITY_AND_ERROR_MODELS.md", "ENERGY_AND_CARBON_MODELS.md",
        "SCENARIOS_AND_WORKLOADS.md", "FAIR_COMPARISON.md", "PARETO_AND_SELECTION.md",
        "RESULTS_AND_INTERPRETATION.md", "EXTENDING_WITH_A_NEW_ECC.md", "REPRODUCIBILITY.md",
        "LIMITATIONS_AND_VALID_CLAIMS.md", "TROUBLESHOOTING.md", "GLOSSARY.md",
        "CLAIM_LEDGER.md", "FIGURE_INDEX.md",
    )],
]
SAFE_HELP_COMMANDS = [
    ["eccsim.py", "--help"], ["eccsim.py", "ecc", "--help"],
    ["eccsim.py", "characterize", "--help"], ["eccsim.py", "characterize-all", "--help"],
    ["eccsim.py", "select-physical", "--help"], ["eccsim.py", "doctor", "--help"],
    ["eccsim.py", "analyze", "--help"], ["eccsim.py", "plot", "--help"],
    ["eccsim.py", "reliability", "--help"], ["eccsim.py", "sram", "--help"],
    ["eccsim.py", "ml", "--help"],
    ["scripts/build_multi_ecc_catalogue.py", "--help"],
    ["scripts/run_multi_ecc_framework_evaluation.py", "--help"],
    ["scripts/generate_documentation_figures.py", "--help"],
]


def load_json(root: Path, path: Path | str) -> dict[str, Any]:
    return json.loads((root / path).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(root: Path, arguments: list[str], *, retries: int = 0) -> None:
    """Run one documentation prerequisite, retrying only when requested.

    A single retry is used for the large evaluation write because cloud-synced
    Windows workspaces can transiently reject replacement of the 28 MiB
    scenario artifact. Persistent failures still surface unchanged.
    """

    for attempt in range(retries + 1):
        try:
            subprocess.run([sys.executable, *arguments], cwd=root, check=True)
            return
        except subprocess.CalledProcessError:
            if attempt >= retries:
                raise
            print(f"Retrying after transient command failure: python {' '.join(arguments)}", file=sys.stderr)


def replace_generated(text: str, name: str, body: str) -> str:
    begin, end = BEGIN.format(name=name), END.format(name=name)
    replacement = f"{begin}\n{body.rstrip()}\n{end}"
    pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.DOTALL)
    if not pattern.search(text):
        raise ValueError(f"missing generated section markers: {name}")
    return pattern.sub(lambda _match: replacement, text, count=1)


def read_registry_entries(root: Path, registry: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    return [load_json(root, REGISTRY / raw) for raw in registry[key]]


def render_status(summary: Mapping[str, Any], study: Mapping[str, Any], architecture_count: int) -> str:
    return "\n".join(
        [
            f"**Current regenerated evidence:** {summary['registered_code_specifications']} mathematical code specifications, "
            f"{summary['registered_encoder_decoder_implementations']} encoder/decoder implementations, "
            f"{architecture_count} deployment architectures in the registry, and "
            f"{summary['selectable_candidate_count']} selectable implementations.",
            "",
            f"The exact-functional and analytical study has {study['scenario_count']} scenarios; "
            f"{study['feasible_scenario_count']} have a feasible winner and {study['no_winner_scenario_count']} have none. "
            f"The evidence gate records {len(summary['verification']['passed'])} passing and "
            f"{len(summary['verification']['rejected'])} rejected implementations. Physical objectives remain null, "
            "so no physical winner, physical PPA comparison, or measured adaptive break-even is computable.",
            "",
            "Source: [`framework_summary.json`](green_ecc_physical_simulation/multi_ecc_evaluation/framework_summary.json) "
            "and [`software_study_summary.json`](green_ecc_physical_simulation/multi_ecc_evaluation/software_study_summary.json).",
        ]
    )


def render_catalogue(root: Path, registry: Mapping[str, Any], capability: Mapping[str, Any]) -> str:
    codes = read_registry_entries(root, registry, "codes")
    implementations = read_registry_entries(root, registry, "implementations")
    status = {row["implementation_id"]: row["capability_verification_status"] for row in capability["rows"]}
    lines = [
        "### Mathematical codes", "",
        "| `code_spec_id` | Family | `(n,k)` | Redundancy | Rate | Implementations |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for code in sorted(codes, key=lambda item: item["code_id"]):
        count = sum(item["code_id"] == code["code_id"] for item in implementations)
        lines.append(f"| `{code.get('code_spec_id', code['code_id'])}` | {code['family']} | ({code['n']},{code['k']}) | {code['redundancy']} | {code['k'] / code['n']:.6f} | {count} |")
    lines.extend([
        "", "### Encoder/decoder implementations", "",
        "| `implementation_id` | `code_spec_id` | `decoder_policy_id` | Verification state | Architectures |",
        "|---|---|---|---|---:|",
    ])
    for item in sorted(implementations, key=lambda value: value["implementation_id"]):
        lines.append(f"| `{item['implementation_id']}` | `{item['code_spec_id']}` | `{item['decoder_policy_id']}` | `{status[item['implementation_id']]}` | {len(item['compatible_deployment_architectures'])} |")
    lines.extend([
        "", "### Registry totals", "",
        f"The current registry contains **{len(codes)} codes**, **{len(implementations)} implementations**, "
        f"**{len(registry['architectures'])} architectures**, and **{len(registry['backends'])} backend manifests**. "
        "These totals exclude the test-only external repetition-code fixture.",
    ])
    return "\n".join(lines)


def render_results(summary: Mapping[str, Any], study: Mapping[str, Any], capability: Mapping[str, Any], architecture_count: int) -> str:
    winner_lines = [f"| `{identifier}` | {count} | {100 * count / study['scenario_count']:.3f}% |" for identifier, count in sorted(study["winner_frequency"].items(), key=lambda item: (-item[1], item[0]))]
    rejected = []
    for row in capability["rows"]:
        if row["capability_verification_status"] == "rejected":
            details = "; ".join(row["failed_capabilities"])
            rejected.append(f"| `{row['implementation_id']}` | {details} |")
    regret = study["fixed_baseline_regret"]
    regret_lines = []
    for identifier, item in sorted(regret.items()):
        regret_lines.append(f"| `{identifier}` | {item['comparable_feasible_scenarios']} | {item['constraint_failure_or_missing_scenarios']} | {100 * item['mean_fractional_regret']:.6f}% | {item['total_analytical_energy_regret_j']:.12g} J |")
    stability_lines = [f"| `{key}` | {item['base_winner_agreement_count']}/{study['scenario_count']} | {100 * item['base_winner_agreement_fraction']:.6f}% |" for key, item in sorted(study["uncertainty_stability"].items())]
    threshold = study["adaptive_threshold"]
    return "\n".join([
        "### Regenerated study summary", "",
        "| Quantity | Current value | Evidence |", "|---|---:|---|",
        f"| Registered mathematical codes | {summary['registered_code_specifications']} | exact registry |",
        f"| Registered implementations | {summary['registered_encoder_decoder_implementations']} | exact registry |",
        f"| Registered architectures | {architecture_count} | exact registry |",
        f"| Selectable implementations | {summary['selectable_candidate_count']} | exact verification gate |",
        f"| Verified capability claims | {summary['verified_capability_count']} | exact functional |",
        f"| Rejected implementations | {len(summary['verification']['rejected'])} | exact functional |",
        f"| Scenarios | {study['scenario_count']} | preregistered analytical grid |",
        f"| Feasible/no-winner scenarios | {study['feasible_scenario_count']} / {study['no_winner_scenario_count']} | exact constraint evaluation over analytical metrics |",
        "| Physical objective coverage | 0 | unsupported/null |", "",
        "### Exact negative results", "", "| Rejected implementation | Exact reason |", "|---|---|", *rejected, "",
        "The bounded TAEC policy remains selectable only for its verified SECDED capabilities: its adjacent-triple claim fails **62/62** tested adjacent triples. "
        "The valid primitive BCH `(63,51,t=2)` reference passes all **2,016/2,016** weight-two patterns. "
        "See [`implementation_capability_matrix.json`](../green_ecc_physical_simulation/multi_ecc_evaluation/implementation_capability_matrix.json) and the per-implementation verification reports.", "",
        "### Winner distribution", "", "| Implementation | Selected scenarios | Share |", "|---|---:|---:|", *winner_lines, "",
        "### Fixed-baseline regret", "", "| Baseline | Comparable feasible | Infeasible/missing | Mean fractional regret | Total analytical regret |", "|---|---:|---:|---:|---:|", *regret_lines, "",
        "### Recommendation stability", "", "| Deterministic sensitivity model | Base-winner agreements | Stability |", "|---|---:|---:|", *stability_lines, "",
        "### Parameterized adaptive threshold", "",
        f"The gross oracle advantage relative to `{threshold['best_single_fixed_candidate']}` is "
        f"**{threshold['gross_oracle_advantage_j_across_comparable_grid']:.12g} J** across comparable scenarios. "
        "That value is the maximum tolerable *total hypothetical* adaptation overhead under the analytical model; "
        "physical MUX, controller, transition, and re-encoding costs are null, so this is not a measured break-even.", "",
        f"**Strongest supported positive:** {summary['strongest_positive_result']}", "",
        f"**Strongest negative:** {summary['strongest_negative_result']}", "",
        "Machine-readable sources: [`software_study_summary.json`](../green_ecc_physical_simulation/multi_ecc_evaluation/software_study_summary.json), "
        "[`pareto_and_regret.json`](../green_ecc_physical_simulation/multi_ecc_evaluation/pareto_and_regret.json), and "
        "[`uncertainty_and_sensitivity.json`](../green_ecc_physical_simulation/multi_ecc_evaluation/uncertainty_and_sensitivity.json).",
    ])


def render_figures(manifest: Mapping[str, Any]) -> str:
    lines = ["| Figure | Research question | Data source | Evidence class | Generation command | Included in |", "|---|---|---|---|---|---|"]
    for figure in manifest["figures"]:
        sources = "<br>".join(f"[`{Path(item['path']).name}`](../{item['path']})" for item in figure["source_artifacts"][:3])
        if len(figure["source_artifacts"]) > 3: sources += f"<br>+{len(figure['source_artifacts']) - 3} hashed sources"
        included = "<br>".join(f"[`{Path(path).name}`](../{path})" for path in figure["included_in"])
        data = figure["figure_data"][0]["path"]
        lines.append(f"| [{figure['title']}](figures/{figure['figure_id']}.svg) | {figure['alt_text']} | {sources}<br>[plot data]({data.removeprefix('docs/')}) | {', '.join(f'`{item}`' for item in figure['evidence_classes'])} | `{figure['generation_command']}` | {included} |")
    lines.extend(["", "### Deliberately omitted plots", ""])
    for item in manifest["omitted_figures"]:
        lines.append(f"- `{item['figure_id']}` — {item['reason']}")
    return "\n".join(lines)


def render_claims(summary: Mapping[str, Any]) -> str:
    rows = [
        ("A new external ECC can be added without family-specific core edits.", "supported", "exact_functional", "extensibility_acceptance.json", "python -m pytest -q tests/python/test_multi_ecc_framework.py", "Fixture proves the public extension contract, not production quality."),
        ("The registry supports multiple distinct code specifications.", "supported", "exact_functional", "framework_summary.json", "python scripts/build_multi_ecc_catalogue.py", "Identity is manifest/hash based."),
        ("All selectable implementations satisfy their declared verification gate.", "supported", "exact_functional", "implementation_capability_matrix.json", "python scripts/run_multi_ecc_framework_evaluation.py", "Only declared/tested universes are guaranteed."),
        ("The bounded TAEC implementation guarantees adjacent-triple correction.", "disproved by current evidence", "exact_functional", "verification/taec-rtl-bounded-72-64-v1.json", "python eccsim.py ecc verify --implementation taec-rtl-bounded-72-64-v1", "62/62 adjacent triples silently miscorrect in the claimed universe."),
        ("The bounded SEC-DAEC implementation guarantees adjacent-double correction and DED.", "disproved by current evidence", "exact_functional", "verification/secdaec-rtl-bounded-72-64-v1.json", "python eccsim.py ecc verify --implementation secdaec-rtl-bounded-72-64-v1", "53/63 adjacent pairs and 302/2,556 doubles miscorrect."),
        ("The valid primitive and shortened BCH references meet their declared t-bit correction universes.", "supported", "exact_functional", "implementation_capability_matrix.json", "python scripts/run_multi_ecc_framework_evaluation.py", "Applies to the registered references, not every BCH-labelled artifact."),
        ("Scenario-aware selection changes the analytical winner and has non-zero fixed-baseline regret.", "conditionally supported", "analytical_model", "software_study_summary.json", "python scripts/run_multi_ecc_framework_evaluation.py", "Conditional on preregistered fault/workload/model parameters."),
        ("A proxy-to-physical winner reversal occurs.", "not computable", "unsupported", "physical_selection.json", "python eccsim.py select-physical --characterization green_ecc_physical_simulation/multi_ecc_evaluation/characterization --scenario green_ecc_physical_simulation/registry/scenarios/no-physical-selection-v1.json --outdir tmp/physical-selection", "No physical winner exists."),
        ("Implementations have comparable physical PPA.", "not computable", "unsupported", "framework_summary.json", "python scripts/run_multi_ecc_framework_evaluation.py", "All physical objectives are null."),
        ("Measured MUX/controller overhead is known.", "unsupported", "unsupported", "framework_summary.json", "python scripts/run_multi_ecc_framework_evaluation.py", "MUX/controller fields are null."),
        ("An adaptive architecture has a measured break-even point.", "not computable", "unsupported", "uncertainty_and_sensitivity.json", "python scripts/run_multi_ecc_framework_evaluation.py", "Only a parameterized analytical threshold exists."),
        ("Results are technology independent.", "unsupported", "unsupported", "framework_summary.json", "python scripts/run_multi_ecc_framework_evaluation.py", "Structural counts are technology independent; PPA conclusions are not."),
        ("The study includes hardware measurements.", "unsupported", "unsupported", "framework_summary.json", "python scripts/run_multi_ecc_framework_evaluation.py", "No hardware-measurement artifact enters selection."),
        ("The ECCs are silicon/radiation validated.", "unsupported", "unsupported", "framework_summary.json", "python scripts/run_multi_ecc_framework_evaluation.py", "No silicon or radiation campaign is present."),
    ]
    lines = ["| Claim | Status | Evidence class | Supporting artifact | Reproduction command | Limitation |", "|---|---|---|---|---|---|"]
    for claim, status, evidence, artifact, command, limitation in rows:
        path = f"../{EVALUATION.as_posix()}/{artifact}"
        lines.append(f"| {claim} | **{status}** | `{evidence}` | [`{artifact}`]({path}) | `{command}` | {limitation} |")
    return "\n".join(lines)


def render_guide_status(summary: Mapping[str, Any], study: Mapping[str, Any], architecture_count: int) -> str:
    return "\n".join([
        f"The regenerated registry contains **{summary['registered_code_specifications']} code specifications**, "
        f"**{summary['registered_encoder_decoder_implementations']} implementations**, **{architecture_count} architectures**, and "
        f"**{summary['selectable_candidate_count']} selectable implementations**. The current analytical grid evaluates "
        f"**{study['scenario_count']} scenarios**, of which **{study['feasible_scenario_count']}** have a feasible winner.",
        "",
        "The defensible evidence ceiling is exact functional execution plus an explicitly parameterized analytical sensitivity model. "
        "Generic structural evidence exists, but every physical area, timing, energy, routing, MUX/controller, transition, "
        "and re-encoding objective remains null. Consequently, the physical-capability gate fails and no physical winner is claimed.",
    ])


def generated_sections(root: Path) -> dict[Path, list[tuple[str, str]]]:
    summary = load_json(root, EVALUATION / "framework_summary.json")
    study = load_json(root, EVALUATION / "software_study_summary.json")
    capability = load_json(root, EVALUATION / "implementation_capability_matrix.json")
    registry = load_json(root, REGISTRY / "registry.json")
    manifest = load_json(root, "docs/figure_data/figure_manifest.json")
    return {
        Path("README.md"): [("CURRENT_STATUS", render_status(summary, study, len(registry["architectures"])))],
        Path("GREEN_ECC_PHY_TECHNICAL_GUIDE.md"): [("CURRENT_GUIDE_STATUS", render_guide_status(summary, study, len(registry["architectures"])))],
        Path("docs/ECC_CATALOGUE.md"): [("CATALOGUE_TABLES", render_catalogue(root, registry, capability))],
        Path("docs/RESULTS_AND_INTERPRETATION.md"): [("CURRENT_RESULTS", render_results(summary, study, capability, len(registry["architectures"])))],
        Path("docs/FIGURE_INDEX.md"): [("FIGURE_TABLE", render_figures(manifest))],
        Path("docs/CLAIM_LEDGER.md"): [("CLAIM_TABLE", render_claims(summary))],
    }


def expected_documents(root: Path) -> dict[Path, str]:
    result = {}
    for path, sections in generated_sections(root).items():
        text = (root / path).read_text(encoding="utf-8")
        for name, body in sections:
            text = replace_generated(text, name, body)
        result[path] = text
    return result


def validate_links(root: Path) -> list[str]:
    errors = []
    link_pattern = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
    for relative in TARGET_DOCS:
        path = root / relative
        if not path.exists():
            errors.append(f"missing documentation file: {relative.as_posix()}")
            continue
        text = path.read_text(encoding="utf-8")
        for raw in link_pattern.findall(text):
            target = raw.strip().split()[0].strip("<>")
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = unquote(target.split("#", 1)[0])
            if not target:
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                errors.append(f"broken link in {relative.as_posix()}: {raw}")
        for alt, raw in re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", text):
            if not alt.strip():
                errors.append(f"empty image alt text in {relative.as_posix()}: {raw}")
    return errors


def validate_json_blocks(root: Path) -> list[str]:
    errors = []
    for relative in TARGET_DOCS:
        path = root / relative
        if not path.exists():
            continue
        for index, block in enumerate(re.findall(r"```json\s*\n(.*?)```", path.read_text(encoding="utf-8"), re.DOTALL), 1):
            try:
                json.loads(block)
            except json.JSONDecodeError as exc:
                errors.append(f"invalid JSON example in {relative.as_posix()} block {index}: {exc}")
    return errors


def validate_data_files(root: Path) -> list[str]:
    errors = []
    for base in (root / "docs/figure_data", root / EVALUATION):
        for path in base.rglob("*.json"):
            try: json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc: errors.append(f"invalid JSON {path.relative_to(root).as_posix()}: {exc}")
    for path in (root / "docs/figure_data").glob("*.csv"):
        try:
            with path.open(encoding="utf-8", newline="") as handle: list(csv.DictReader(handle))
        except (OSError, csv.Error) as exc: errors.append(f"invalid CSV {path.relative_to(root).as_posix()}: {exc}")
    return errors


def validate_manifest(root: Path) -> list[str]:
    errors = []
    manifest = load_json(root, "docs/figure_data/figure_manifest.json")
    for figure in manifest["figures"]:
        for item in figure["source_artifacts"]:
            path = root / item["path"]
            if not path.exists(): errors.append(f"figure manifest missing file: {item['path']}")
            elif scientific_file_sha256(path) != item["sha256"]: errors.append(f"figure manifest hash mismatch: {item['path']}")
        for item in [*figure["figure_data"], *figure["files"].values()]:
            path = root / item["path"]
            if not path.exists(): errors.append(f"figure manifest missing file: {item['path']}")
            elif sha256(path) != item["sha256"]: errors.append(f"figure manifest hash mismatch: {item['path']}")
    expected_hash = dict(manifest); declared = expected_hash.pop("manifest_sha256")
    canonical = hashlib.sha256(json.dumps(expected_hash, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
    if canonical != declared: errors.append("figure manifest self-hash mismatch")
    return errors


def validate_cli(root: Path) -> list[str]:
    errors = []
    for arguments in SAFE_HELP_COMMANDS:
        completed = subprocess.run([sys.executable, *arguments], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if completed.returncode != 0 or "usage:" not in completed.stdout:
            errors.append(f"CLI help failed: python {' '.join(arguments)}")
    return errors


def build_summary(root: Path) -> dict[str, Any]:
    manifest = load_json(root, "docs/figure_data/figure_manifest.json")
    summary = load_json(root, EVALUATION / "framework_summary.json")
    return {
        "schema_version": 1,
        "documentation_files": len(TARGET_DOCS),
        "figures": len(manifest["figures"]),
        "figure_formats": ["svg", "png", "pdf"],
        "png_dpi": manifest["png_dpi"],
        "pareto_scenarios_independently_validated": manifest["pareto_validation"]["scenarios_checked"],
        "registered_code_specifications": summary["registered_code_specifications"],
        "registered_implementations": summary["registered_encoder_decoder_implementations"],
        "selectable_implementations": summary["selectable_candidate_count"],
        "physical_selection_computable": not summary["all_physical_metrics_unsupported"],
        "documentation_sha256": {path.as_posix(): sha256(root / path) for path in TARGET_DOCS},
        "figure_manifest_sha256": sha256(root / "docs/figure_data/figure_manifest.json"),
        "validation": {"links": "passed", "json_csv": "passed", "figure_hashes": "passed", "cli_help": "passed", "generated_sections": "current"},
    }


def validate(root: Path, *, check_cli_help: bool = True) -> None:
    errors = [*validate_links(root), *validate_json_blocks(root), *validate_data_files(root), *validate_manifest(root)]
    if check_cli_help: errors.extend(validate_cli(root))
    if errors: raise SystemExit("Documentation validation failed:\n" + "\n".join(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check", action="store_true", help="Non-mutating stale-content and validation check")
    args = parser.parse_args(); root = args.repo_root.resolve()
    if args.check:
        run(root, ["scripts/generate_documentation_figures.py", "--check"])
        stale = [path.as_posix() for path, expected in expected_documents(root).items() if (root / path).read_text(encoding="utf-8") != expected]
        if stale: raise SystemExit("Generated documentation sections are stale:\n" + "\n".join(stale))
        validate(root)
        expected_summary = build_summary(root)
        actual_summary = load_json(root, "docs/figure_data/documentation_build_summary.json")
        if actual_summary != expected_summary: raise SystemExit("Documentation build summary is stale")
        print(json.dumps({"status": "current", "documentation_files": len(TARGET_DOCS), "figures": expected_summary["figures"], "links": "passed", "figure_hashes": "passed", "cli_help": "passed"}, indent=2, sort_keys=True))
        return 0

    run(root, ["scripts/build_multi_ecc_catalogue.py"])
    run(root, ["scripts/run_multi_ecc_framework_evaluation.py"], retries=1)
    run(root, ["scripts/generate_documentation_figures.py"])
    for path, expected in expected_documents(root).items():
        (root / path).write_text(expected, encoding="utf-8")
    validate(root)
    summary = build_summary(root)
    output = root / "docs/figure_data/documentation_build_summary.json"
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "built", "summary": output.relative_to(root).as_posix(), **{key: summary[key] for key in ("documentation_files", "figures", "pareto_scenarios_independently_validated", "physical_selection_computable")}}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
