#!/usr/bin/env python3
"""Final schema, provenance, scope, figure, hypothesis, and repository validation."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/date2027/rigour_gate_04"
EVIDENCE = Path("/var/lib/green-ecc-gate04")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def main() -> int:
    checks: list[dict[str, object]] = []
    failures: list[str] = []

    def check(condition: bool, name: str, detail: object = None) -> None:
        checks.append({"check": name, "status": "PASS" if condition else "FAIL", "detail": detail})
        if not condition:
            failures.append(name)

    required = [
        "GATE_04_REPORT.md", "EXPERIMENT_FREEZE.md", "FAIRNESS_CONTRACT.md",
        "ASIC_CANDIDATE_MATRIX.csv", "FLOW_RUN_MATRIX.csv", "PPA_RESULTS.csv", "POWER_RESULTS.csv",
        "RELIABILITY_RESULTS.csv", "DSE_RESULTS.csv", "HYPOTHESIS_RESULTS.json", "HYPOTHESIS_RESULTS.md",
        "CLAIMS_LEDGER.csv", "FIGURE_DATA_MANIFEST.csv", "EXTERNAL_ARTIFACT_INDEX.csv",
        "REPRODUCIBILITY.md", "environment_manifest.json", "command_manifest.json",
        "RAW_LOG_INDEX.csv", "GATE_04_VERDICT.txt", "POSTPROCESS_VALIDATION.json",
        "GATE04_REPOSITORY_COMMAND_RESULTS.json", "RETRY_LEDGER.csv", "POLICY_AMENDMENT_01.md",
    ]
    check(all((OUT / name).is_file() and (OUT / name).stat().st_size > 0 for name in required), "all required Gate 04 artifacts exist")
    candidates = read_csv(OUT / "ASIC_CANDIDATE_MATRIX.csv")
    flows = read_csv(OUT / "FLOW_RUN_MATRIX.csv")
    check(sum(row["gate02_eligibility"] == "ELIGIBLE" for row in candidates) == 14, "all 14 mathematically eligible implementations reconciled")
    check(sum(row["gate04_status"] == "MANDATORY_PHYSICAL_CANDIDATE" for row in candidates) == 4, "all four mandatory physical candidates reconciled")
    check(len(flows) == 60 and len({row["run_id"] for row in flows}) == 60, "complete unique expected flow matrix")
    verdict = (OUT / "GATE_04_VERDICT.txt").read_text(encoding="utf-8").strip()
    allowed = {"ASIC_EXPERIMENT_BLOCKED", "ASIC_EVIDENCE_COMPLETE_NO_MATERIAL_SELECTION_EFFECT", "ASIC_EVIDENCE_COMPLETE_MATERIAL_SELECTION_EFFECT"}
    check(verdict in allowed, "verdict is one exact authorized token", verdict)
    if verdict != "ASIC_EXPERIMENT_BLOCKED":
        check(all(row["status"] == "PASS" for row in flows), "all 60 planned flows passed full validation")
    else:
        check(any(row["status"] != "PASS" for row in flows), "blocked verdict has an explicit failed or missing mandatory item")

    for filename in ("PPA_RESULTS.csv", "POWER_RESULTS.csv", "RELIABILITY_RESULTS.csv", "DSE_RESULTS.csv"):
        result_rows = read_csv(OUT / filename)
        check(bool(result_rows), f"{filename} has data rows")
        check(all(row.get("implementation_id", row.get("selected_implementation_id", "")) for row in result_rows), f"{filename} IDs populated")
        check(all(row.get("unit", "") for row in result_rows), f"{filename} units populated")
        check(all(row.get("source_artifact", "") and row.get("source_field", "") for row in result_rows), f"{filename} provenance populated")
        check(all(row.get("evidence_class", "") in {"MEASURED", "SYNTHESIZED", "SIMULATED", "DERIVED", "ASSUMED", "PROXY", "UNRESOLVED"} for row in result_rows), f"{filename} evidence classes valid")

    contract = json.loads((ROOT / "scripts/gate04/contract_v1.json").read_text(encoding="utf-8"))
    hypotheses = json.loads((OUT / "HYPOTHESIS_RESULTS.json").read_text(encoding="utf-8"))
    check(set(hypotheses) >= {"H1", "H2", "H3", "H4"}, "all frozen hypotheses adjudicated")
    check(contract["statistics"]["material_fraction"] == 0.05 and contract["statistics"]["bootstrap_resamples"] == 20000, "frozen thresholds unchanged")
    postprocess = json.loads((OUT / "POSTPROCESS_VALIDATION.json").read_text(encoding="utf-8"))
    check(postprocess["verdict"] == verdict, "postprocess and verdict file agree")
    check(postprocess["protected_bytes_unchanged"], "all previous gates, production RTL, registries, and selectors retain raw bytes")
    check(not postprocess["policy_hash_failures"], "immutable external policy hashes validate")

    figures = read_csv(OUT / "FIGURE_DATA_MANIFEST.csv")
    check(len(figures) == 10, "exactly ten preregistered figure records")
    if verdict != "ASIC_EXPERIMENT_BLOCKED":
        check(all(row["status"] == "GENERATED_FROM_VALIDATED_MACHINE_READABLE_DATA" for row in figures), "all required figures generated from validated data")
        check(all((OUT / row["file"]).is_file() and sha256(OUT / row["file"]) == row["sha256"] for row in figures), "all figure hashes validate")
    else:
        check(all(row["status"] == "NOT_GENERATED_BLOCKED_RAW_EVIDENCE" for row in figures), "blocked figures are explicitly not generated")
    check(all(all((OUT / source.strip()).is_file() for source in row["raw_data_references"].split(";") if source.strip().endswith(".csv")) for row in figures), "every figure raw CSV reference resolves")

    command_results = json.loads((OUT / "GATE04_REPOSITORY_COMMAND_RESULTS.json").read_text(encoding="utf-8"))
    check(all(item["status"] == "PASS" for item in command_results["commands"]), "focused, golden, make, make test, full pytest, diff, and scope checks pass")

    snapshot = EVIDENCE / "policy/repo_snapshot/scripts/gate04"
    amendment = EVIDENCE / "amendments/01"
    source_mismatches = []
    for path in (ROOT / "scripts/gate04").rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            relative = path.relative_to(ROOT / "scripts/gate04")
            frozen = amendment / relative if (amendment / relative).is_file() else snapshot / relative
            if not frozen.is_file() or sha256(path) != sha256(frozen):
                source_mismatches.append(relative.as_posix())
    check(not source_mismatches, "executed Gate 04 analysis code matches immutable pre-flow snapshot", source_mismatches)
    text_paths = [path for path in (ROOT / "scripts/gate04").rglob("*") if path.is_file() and path.suffix in {".py", ".sh", ".sv", ".mk", ".sdc", ".json"}]
    text_paths.append(ROOT / "tests/python/test_gate04_contract.py")
    check(all(b"\r" not in path.read_bytes() for path in text_paths), "Gate 04 source and focused test files preserve LF bytes")

    result = {"schema_version": 1, "status": "PASS" if not failures else "FAIL", "verdict": verdict, "checks": checks, "failures": failures}
    (OUT / "FINAL_VALIDATION.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    manifest_paths = sorted(path for path in OUT.rglob("*") if path.is_file() and path.name != "GATE04_EVIDENCE.sha256")
    with (OUT / "GATE04_EVIDENCE.sha256").open("w", encoding="utf-8", newline="\n") as stream:
        for path in manifest_paths:
            stream.write(f"{sha256(path)}  {path.relative_to(OUT).as_posix()}\n")
    print(f"GATE04_FINAL_VALIDATION_{'PASS' if not failures else 'FAIL'} checks={len(checks)} failures={len(failures)}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
