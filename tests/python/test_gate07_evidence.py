from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from scripts.gate03es.scope_compatibility import is_registered_additive_path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/date2027/rigour_gate_07"
GATE06 = ROOT / "docs/date2027/rigour_gate_06"

COMB = "secded-rtl-combinational-72-64-v1"
PIPE = "secded-rtl-pipelined-72-64-v1"
BCH = "shortened-bch-78-64-t2-v1-rtl-syndrome-chien-v1"


def _json(name: str):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_gate07_required_outputs_and_additive_scope() -> None:
    for name in (
        "GATE07_SCOPE_STATEMENT.md",
        "GATE07_REVIEWER_ATTACKS.md",
        "GATE07_CLAIM_LEDGER.json",
        "GATE07_NUMERICAL_CLAIM_AUDIT.json",
        "GATE07_ENERGY_AUDIT.md",
        "GATE07_RELIABILITY_SEMANTICS.md",
        "GATE07_PHYSICAL_COMPARABILITY.md",
        "GATE07_CONTRIBUTION_FREEZE.md",
        "GATE07_FIGURE_FREEZE.json",
        "GATE07_TABLE_FREEZE.json",
        "GATE07_LIMITATIONS.md",
        "GATE07_MANUSCRIPT_EVIDENCE.json",
        "GATE07_ADJUDICATION.md",
        "GATE07_FIGURE_DATA.json",
        "GATE07_TABLE_I_IMPLEMENTATIONS.csv",
        "GATE07_TABLE_II_RESULTS.csv",
    ):
        assert (OUT / name).is_file()
    for path in (
        "docs/date2027/rigour_gate_07/GATE07_ADJUDICATION.md",
        "scripts/gate07/build_gate07.py",
        "tests/python/test_gate07_evidence.py",
    ):
        assert is_registered_additive_path(path)


def test_gate07_hashes_and_frozen_sources_verify() -> None:
    for line in (OUT / "GATE07_EVIDENCE.sha256").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split(maxsplit=1)
        assert _sha(OUT / relative.removeprefix("./")) == expected
    evidence = _json("GATE07_MANUSCRIPT_EVIDENCE.json")
    for source in evidence["authoritative_inputs"]:
        path = ROOT / source["path"]
        assert _sha(path) == source["sha256"]
        assert path.stat().st_size == source["bytes"]
    assert evidence["input_policy"]["gate06_frozen"] is True
    assert evidence["input_policy"]["new_measurements"] is False


def test_gate07_numerical_audit_uses_gate06_raw_rows() -> None:
    audit = _json("GATE07_NUMERICAL_CLAIM_AUDIT.json")
    assert audit["source"] == "docs/date2027/rigour_gate_06/GATE06_DESIGN_SPACE.csv"
    assert audit["result"] == "NUMERICAL_CLAIM_AUDIT_PASS"
    assert audit["mismatch_count"] == 0
    comparisons = {
        row["comparison"]: {metric["metric"]: metric for metric in row["metrics"]}
        for row in audit["comparisons"]
    }
    secded = comparisons["pipelined SECDED vs combinational SECDED"]
    assert 36.702 < secded["standard_cell_instance_area_um2"]["recomputed_percent_change"] < 36.703
    assert 45.910 < secded["achieved_fmax_mhz"]["recomputed_percent_change"] < 45.912
    assert -24.017 < secded["no_error_achievable_total_energy_pj_per_operation"]["recomputed_percent_change"] < -24.015
    bch = comparisons["BCH vs combinational SECDED"]
    assert 207.355 < bch["standard_cell_instance_area_um2"]["recomputed_percent_change"] < 207.357
    assert bch["timing_deficit_ns"]["candidate_raw"] == 4.78052
    assert bch["no_error_achievable_total_energy_pj_per_operation"]["status"] == "CORRECTLY_NOT_COMPUTED"


def test_gate07_energy_and_reliability_semantics_are_reviewer_safe() -> None:
    energy = (OUT / "GATE07_ENERGY_AUDIT.md").read_text(encoding="utf-8")
    assert "`ENERGY_COMPARISON_VALID`" in energy
    assert "100,000 accepted" in energy
    assert "6 / 100,000 / 4 cycles" in energy
    assert "does not assert lower single-request latency" in energy
    reliability = (OUT / "GATE07_RELIABILITY_SEMANTICS.md").read_text(encoding="utf-8")
    assert "do **not** have different W3 universe sizes" in reliability
    assert "59,640" in reliability and "76,076" in reliability
    assert "not FIT, SER" in reliability
    assert "not operational probabilities or correction guarantees" not in reliability  # wording is expanded, not collapsed


def test_gate07_claim_ledger_removes_unsafe_claims() -> None:
    claims = _json("GATE07_CLAIM_LEDGER.json")["claims"]
    assert len(claims) == 13
    by_id = {row["claim_id"]: row for row in claims}
    assert by_id["C01"]["final_status"] == "CLAIM_FROZEN"
    assert by_id["C02"]["final_status"] == "CLAIM_FROZEN"
    assert by_id["C03"]["final_status"] == "CLAIM_NARROWED"
    assert by_id["C06"]["final_status"] == "CLAIM_NARROWED"
    assert by_id["C07"]["final_status"] == "CLAIM_DISCUSSION_ONLY"
    assert all(by_id[key]["final_status"] == "CLAIM_REMOVED" for key in ("C09", "C10", "C11", "C12", "C13"))
    assert "evaluated" in by_id["C03"]["exact_proposed_wording"].lower()
    assert "does not claim general EDA determinism" in by_id["C06"]["limitations"]


def test_gate07_reviewers_figures_tables_and_limitations_are_frozen() -> None:
    attacks = (OUT / "GATE07_REVIEWER_ATTACKS.md").read_text(encoding="utf-8")
    assert all(name in attacks for name in ("Reviewer A", "Reviewer B", "Reviewer C"))
    assert "No unresolved `CRITICAL` issue" in attacks
    figures = {row["id"]: row for row in _json("GATE07_FIGURE_FREEZE.json")["figures"]}
    assert figures["F01_CROSS_LAYER_METHOD"]["status"] == "FIGURE_FROZEN"
    assert figures["F03_NORMALIZED_PHYSICAL_COST"]["status"] == "FIGURE_REVISE"
    assert figures["F04_RELIABILITY_OUTCOMES"]["status"] == "FIGURE_DROP"
    tables = _json("GATE07_TABLE_FREEZE.json")
    assert tables["major_table_count"] == 2
    with (OUT / "GATE07_TABLE_II_RESULTS.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 4
    assert any(row["area_um2"] == "PPA_UNAVAILABLE" for row in rows)
    assert any(row["achievable_energy_pj_per_operation"] == "TARGET_CLOCK_INFEASIBLE" for row in rows)
    limitations = (OUT / "GATE07_LIMITATIONS.md").read_text(encoding="utf-8")
    assert all(section in limitations for section in ("Experimental Setup", "Results", "Discussion", "Artifact-only detail"))


def test_gate07_manuscript_readiness_and_gate08_boundary() -> None:
    evidence = _json("GATE07_MANUSCRIPT_EVIDENCE.json")
    assert evidence["gate_verdict"] == "GATE_07_PASS"
    assert evidence["date_manuscript_readiness"] == "DATE_MANUSCRIPT_READY"
    assert evidence["unresolved_critical_reviewer_issues"] == []
    assert len(evidence["readiness_scores_1_to_10"]) == 9
    assert evidence["final_figures"] == [
        "F01_CROSS_LAYER_METHOD",
        "F02_AREA_VS_FMAX",
        "F03_NORMALIZED_PHYSICAL_COST_REVISED",
    ]
    report = (OUT / "GATE07_ADJUDICATION.md").read_text(encoding="utf-8")
    assert "`GATE_07_PASS`" in report
    assert "`DATE_MANUSCRIPT_READY`" in report
    assert report.rstrip().endswith("`GATE_08_READY`")


def test_gate07_validator_and_builder_are_deterministic(tmp_path: Path) -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/gate07/validate_gate07.py")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    regenerated = tmp_path / "gate07"
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/gate07/build_gate07.py"), "--out", str(regenerated)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    original = {
        path.relative_to(OUT).as_posix(): _sha(path)
        for path in OUT.rglob("*") if path.is_file()
    }
    candidate = {
        path.relative_to(regenerated).as_posix(): _sha(path)
        for path in regenerated.rglob("*") if path.is_file()
    }
    # Preserve exact payload bytes. Historical native Path sorting can change
    # seal line order across Windows and Linux, but never its checksum bindings.
    assert candidate.keys() == original.keys()
    different = {name for name in original if candidate[name] != original[name]}
    for name in different:
        assert "SHA256" in name.upper(), name
        def bindings(path: Path) -> dict[str, str]:
            return {relative: digest for digest, relative in
                    (line.split("  ", 1) for line in path.read_text(encoding="utf8").splitlines())}
        assert bindings(regenerated / name) == bindings(OUT / name)
