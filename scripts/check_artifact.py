#!/usr/bin/env python3
"""Deterministic integrity checks for the public GREENS research artifact.

This checker validates structure and provenance references. It does not rerun
physical design and does not promote any evidence classification.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_FILES = (
    "README.md",
    "LICENSE",
    "CITATION.cff",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "Makefile",
    "requirements.txt",
    "docs/README.md",
    "docs/getting-started.md",
    "docs/INSTALLATION.md",
    "docs/quickstart.md",
    "docs/architecture.md",
    "docs/methodology.md",
    "docs/experiment-pipeline.md",
    "docs/reliability-model.md",
    "docs/ecc-architectures.md",
    "docs/physical-design.md",
    "docs/sustainability-model.md",
    "docs/evidence-model.md",
    "docs/REPRODUCIBILITY.md",
    "docs/reviewer-guide.md",
    "docs/user-guide.md",
    "docs/developer-guide.md",
    "docs/adding-an-ecc.md",
    "docs/adding-an-experiment.md",
    "docs/results-schema.md",
    "docs/TROUBLESHOOTING.md",
    "docs/limitations.md",
    "docs/roadmap.md",
    "docs/GLOSSARY.md",
    "docs/evidence-map.md",
    # Retained as a compatibility pointer for existing external links.
    "docs/paper-to-artifact.md",
    "AGENTS.md",
    "docs/project-overview.md",
    "docs/maintenance/repository-overhaul.md",
    "docs/papers.md",
    "docs/results.md",
    "experiments/iscas/README.md",
    "experiments/iscas/reproduction.md",
    "experiments/iscas/regeneration.md",
    "experiments/iscas/claims.md",
    "experiments/iscas/evidence/README.md",
    "experiments/iscas/generated/headline_results.json",
    "experiments/iscas/generated/primary_operation_pairs.csv",
    "scripts/reproduce_iscas.py",
)

CRITICAL_JSON = (
    "green_ecc_physical_simulation/registry/registry.json",
    "green_ecc_physical_simulation/multi_ecc_evaluation/framework_summary.json",
    "campaigns/iscas_sustainability_extension/green_matrix_v3_2/CAMPAIGN_STATUS.json",
    "campaigns/iscas_sustainability_extension/green_v3_2_matched_openram_orfs_validation/RUN_MANIFEST.json",
    "campaigns/iscas_sustainability_extension/green_v3_2_matched_openram_orfs_validation/OPENRAM_PROVENANCE.json",
    "campaigns/iscas_sustainability_extension/green_v3_3_activity_complete_e5/CAMPAIGN_STATUS.json",
    "campaigns/iscas_sustainability_extension/green_v3_3_activity_complete_e5/RUN_MANIFEST.json",
)

LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def missing_fields(record: Mapping[str, Any], fields: Iterable[str]) -> list[str]:
    return [field for field in fields if field not in record]


def duplicate_values(records: Iterable[Mapping[str, Any]], field: str) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for record in records:
        if field not in record:
            continue
        value = str(record[field])
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def _link_target(source: Path, raw_target: str) -> Path | None:
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    target = target.split(maxsplit=1)[0]
    parsed = urlsplit(target)
    if parsed.scheme or target.startswith("#"):
        return None
    decoded = unquote(parsed.path)
    if not decoded:
        return None
    return (source.parent / decoded).resolve()


def broken_markdown_links(paths: Iterable[Path]) -> list[str]:
    broken: list[str] = []
    root = ROOT.resolve()
    for source in paths:
        text = source.read_text(encoding="utf-8", errors="replace")
        for raw_target in LINK_RE.findall(text):
            target = _link_target(source, raw_target)
            if target is None:
                continue
            try:
                target.relative_to(root)
            except ValueError:
                broken.append(f"{source.relative_to(ROOT)} -> {raw_target} (outside repository)")
                continue
            if not target.exists():
                broken.append(f"{source.relative_to(ROOT)} -> {raw_target}")
    return sorted(set(broken))


def validate_links() -> list[str]:
    public_docs = [ROOT / "README.md"] + [
        ROOT / path for path in EXPECTED_FILES if path.endswith(".md")
    ]
    existing = [path for path in public_docs if path.is_file()]
    return [f"broken link: {item}" for item in broken_markdown_links(existing)]


def validate_artifact() -> list[str]:
    errors: list[str] = []
    for relative in EXPECTED_FILES:
        if not (ROOT / relative).is_file():
            errors.append(f"missing expected file: {relative}")

    payloads: dict[str, Any] = {}
    for relative in CRITICAL_JSON:
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"missing critical JSON: {relative}")
            continue
        try:
            payloads[relative] = load_json(path)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"invalid critical JSON: {relative}: {exc}")

    registry_rel = CRITICAL_JSON[0]
    registry = payloads.get(registry_rel)
    if isinstance(registry, Mapping):
        registry_root = (ROOT / registry_rel).parent.resolve()
        loaded_registry: dict[str, list[Mapping[str, Any]]] = {}
        for key, id_field in (
            ("codes", "code_id"),
            ("implementations", "implementation_id"),
            ("architectures", "architecture_id"),
        ):
            references = registry.get(key, [])
            if not isinstance(references, list):
                errors.append(f"{registry_rel}: {key} is not a list")
                continue
            records: list[Mapping[str, Any]] = []
            for reference in references:
                if not isinstance(reference, str):
                    errors.append(f"{registry_rel}: non-string {key} reference")
                    continue
                path = (registry_root / reference).resolve()
                try:
                    path.relative_to(registry_root)
                except ValueError:
                    errors.append(f"{registry_rel}: {key} reference escapes registry: {reference}")
                    continue
                if not path.is_file():
                    errors.append(f"{registry_rel}: missing {key} record: {reference}")
                    continue
                try:
                    record = load_json(path)
                except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                    errors.append(f"{registry_rel}: invalid {key} record {reference}: {exc}")
                    continue
                if not isinstance(record, Mapping):
                    errors.append(f"{registry_rel}: {key} record is not an object: {reference}")
                    continue
                records.append(record)
                record_id = record.get(id_field)
                if record_id is None:
                    errors.append(f"{reference}: missing {id_field}")
                elif str(record_id) != path.stem:
                    errors.append(
                        f"{reference}: {id_field} {record_id!r} does not match filename"
                    )
            loaded_registry[key] = records
            duplicates = duplicate_values(records, id_field)
            if duplicates:
                errors.append(f"{registry_rel}: duplicate {id_field}: {duplicates}")

        code_ids = {
            str(record["code_id"])
            for record in loaded_registry.get("codes", [])
            if "code_id" in record
        }
        implementation_ids = {
            str(record["implementation_id"])
            for record in loaded_registry.get("implementations", [])
            if "implementation_id" in record
        }
        for record in loaded_registry.get("implementations", []):
            if record.get("code_id") not in code_ids:
                errors.append(
                    f"implementation {record.get('implementation_id')!r} references unknown "
                    f"code_id {record.get('code_id')!r}"
                )
        for record in loaded_registry.get("architectures", []):
            for implementation_id in record.get("allowed_implementation_ids", []):
                if implementation_id not in implementation_ids:
                    errors.append(
                        f"architecture {record.get('architecture_id')!r} references unknown "
                        f"implementation_id {implementation_id!r}"
                    )

    v33_rel = CRITICAL_JSON[-2]
    v33 = payloads.get(v33_rel)
    if isinstance(v33, Mapping):
        required = (
            "classification",
            "included_architectures",
            "evidence_added",
            "runtime_budget",
            "global_winner",
            "whole_memory_e5_qualified",
        )
        for field in missing_fields(v33, required):
            errors.append(f"{v33_rel}: missing field {field}")
        if v33.get("global_winner") != "NO_GLOBAL_WINNER_QUALIFIED":
            errors.append(f"{v33_rel}: global-winner guard changed")
        if v33.get("whole_memory_e5_qualified") is not False:
            errors.append(f"{v33_rel}: whole-memory E5 guard changed")
        budget = v33.get("runtime_budget", {})
        if isinstance(budget, Mapping):
            if budget.get("scope") != "ENTIRE_CAMPAIGN" or budget.get("seconds") != 54000:
                errors.append(f"{v33_rel}: campaign-wide 54,000-second budget guard changed")

    openram_rel = CRITICAL_JSON[-3]
    openram = payloads.get(openram_rel)
    if isinstance(openram, Mapping):
        fresh = openram.get("fresh_run", {})
        if not isinstance(fresh, Mapping):
            errors.append(f"{openram_rel}: fresh_run is not an object")
        else:
            for field in ("status", "classification", "configuration", "drc_state", "lvs_state"):
                if field not in fresh:
                    errors.append(f"{openram_rel}: fresh_run missing field {field}")
            if fresh.get("fresh_execution") is not True:
                errors.append(f"{openram_rel}: fresh execution provenance is missing")
            if fresh.get("status") == "COMPLETED":
                errors.append(f"{openram_rel}: historical timeout was silently promoted")

    matrix_path = ROOT / (
        "campaigns/iscas_sustainability_extension/green_matrix_v3_2/data/"
        "EVIDENCE_MATRIX.json"
    )
    if matrix_path.is_file():
        try:
            matrix = load_json(matrix_path)
            records = matrix.get("records", []) if isinstance(matrix, Mapping) else []
            duplicates = duplicate_values(
                (item for item in records if isinstance(item, Mapping)), "quantity_id"
            )
            if duplicates:
                errors.append(
                    f"{matrix_path.relative_to(ROOT)}: duplicate quantity_id: {duplicates[:10]}"
                )
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"invalid evidence matrix JSON: {exc}")

    for relative in (
        "campaigns/iscas_sustainability_extension/green_v3_3_activity_complete_e5/E5_OPERATION_STATISTICS.csv",
        "campaigns/iscas_sustainability_extension/green_v3_2_matched_openram_orfs_validation/PHYSICAL_RUN_RESULTS.csv",
    ):
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"missing canonical CSV: {relative}")
            continue
        try:
            with path.open(newline="", encoding="utf-8") as stream:
                reader = csv.DictReader(stream)
                if not reader.fieldnames or next(reader, None) is None:
                    errors.append(f"empty canonical CSV: {relative}")
        except (OSError, UnicodeError, csv.Error) as exc:
            errors.append(f"invalid canonical CSV: {relative}: {exc}")

    errors.extend(validate_links())
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--links-only", action="store_true", help="check public Markdown links only"
    )
    args = parser.parse_args()
    errors = validate_links() if args.links_only else validate_artifact()
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    scope = (
        "documentation links"
        if args.links_only
        else "artifact structure, provenance guards, IDs, CSV, and links"
    )
    print(f"ARTIFACT_CHECK_PASS: {scope}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
