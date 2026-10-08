#!/usr/bin/env python3
"""Freeze the prospective Gate 04 experiment under a new external namespace."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path


DEFAULT_ROOT = Path("/var/lib/green-ecc-date2027-gate04-final")
AUTHORITATIVE_ROOT = Path("/var/lib/green-ecc-date2027-final")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def verify_manifest(root: Path, manifest: Path) -> None:
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split(maxsplit=1)
        path = root / relative.strip()
        if not path.is_file() or sha256(path) != expected:
            raise SystemExit(f"authoritative frozen-policy mismatch: {relative}")


def copy_snapshot(repo: Path, snapshot: Path, paths: set[str]) -> list[dict[str, object]]:
    records = []
    for relative in sorted(paths):
        source = repo / relative
        if not source.is_file():
            raise SystemExit(f"missing Gate 04 freeze input: {relative}")
        destination = snapshot / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        destination.chmod(0o444)
        records.append({"path": relative, "bytes": destination.stat().st_size, "sha256": sha256(destination)})
    return records


def freeze_hash_manifest(policy: Path) -> None:
    rows = []
    for path in sorted(item for item in policy.rglob("*") if item.is_file()):
        if path.name != "frozen-bundle.sha256":
            rows.append(f"{sha256(path)}  {path.relative_to(policy).as_posix()}")
    (policy / "frozen-bundle.sha256").write_text("\n".join(rows) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit("run as root inside Ubuntu WSL2")

    repo = args.repo.resolve()
    root = args.evidence_root
    if root.exists():
        raise SystemExit(f"refusing to overwrite Gate 04 final root: {root}")

    gate03f_policy = AUTHORITATIVE_ROOT / "policy"
    verify_manifest(gate03f_policy, gate03f_policy / "frozen-bundle.sha256")
    contract = json.loads((repo / "scripts/gate04_final/contract_v1.json").read_text(encoding="utf-8"))
    environment_path = gate03f_policy / "DATE_FINAL_PHYSICAL_ENVIRONMENT.json"
    if sha256(environment_path) != contract["gate03f_environment_manifest_sha256"]:
        raise SystemExit("authoritative Gate 03F environment identity mismatch")
    environment = json.loads(environment_path.read_text(encoding="utf-8"))
    if environment["state"] != contract["environment_identity"]:
        raise SystemExit("Gate 03F environment is not in the frozen authoritative state")

    for relative, expected in contract["source_hashes"].items():
        path = repo / relative
        if not path.is_file() or sha256(path) != expected:
            raise SystemExit(f"frozen RTL/boundary hash mismatch: {relative}")

    final_set = json.loads((repo / "docs/date2027/rigour_gate_04_final/GATE04_FINAL_ECC_SET.json").read_text(encoding="utf-8"))
    included = [item["implementation_id"] for item in final_set["records"] if item["classification"] == "INCLUDED"]
    if included != contract["included_implementation_ids"]:
        raise SystemExit("final ECC set does not match the frozen four-run contract")
    if len(contract["runs"]) != 4 or len({item["run_id"] for item in contract["runs"]}) != 4:
        raise SystemExit("Gate 04 must contain exactly four unique prospective runs")

    image = contract["technology"]["container_image"]
    image_inspect = json.loads(subprocess.check_output(["docker", "image", "inspect", image], text=True))[0]
    if image_inspect["Id"] != image.split("@", 1)[1]:
        raise SystemExit("local Docker image does not match the authoritative digest")

    policy = root / "policy"
    snapshot = policy / "repo_snapshot"
    traces = policy / "traces"
    reference = policy / "authoritative_gate03f"
    runs = root / "runs"
    snapshot.mkdir(parents=True)
    traces.mkdir()
    reference.mkdir()
    runs.mkdir()

    snapshot_paths = {
        path.relative_to(repo).as_posix()
        for path in (repo / "scripts/gate04_final").rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    snapshot_paths.update(contract["source_hashes"])
    snapshot_paths.update(
        {
            "docs/date2027/rigour_gate_04_final/GATE04_FINAL_ECC_SET.json",
            "docs/date2027/rigour_gate_04_final/GATE04_POWER_ACTIVITY_AUDIT.json",
            "docs/date2027/rigour_gate_04_final/GATE04_POWER_PRECISION_ADJUDICATION.md",
        }
    )
    source_records = copy_snapshot(repo, snapshot, snapshot_paths)

    gate03f_trace_root = gate03f_policy / "traces"
    for source in sorted(gate03f_trace_root.iterdir()):
        if source.is_file():
            shutil.copy2(source, traces / source.name)
    for name in ("DATE_FINAL_PHYSICAL_ENVIRONMENT.json", "IMMUTABLE_INPUT_MANIFEST.json", "frozen-bundle.sha256"):
        shutil.copy2(gate03f_policy / name, reference / name)

    copied_trace_manifest = json.loads((traces / "TRACE_MANIFEST.json").read_text(encoding="utf-8"))
    if len(copied_trace_manifest["traces"]) != 9:
        raise SystemExit("frozen Gate 04 trace copy must contain exactly nine trace records")
    for item in copied_trace_manifest["traces"]:
        path = traces / item["file"]
        if sha256(path) != item["compressed_sha256"]:
            raise SystemExit(f"copied trace hash mismatch: {item['file']}")

    repository_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    status = subprocess.check_output(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=repo, text=True)
    (policy / "repository-status-at-freeze.txt").write_text(status, encoding="utf-8", newline="\n")
    frozen_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    experiment_manifest = {
        "schema_version": 1,
        "gate": contract["gate"],
        "state": "GATE04_FINAL_EXPERIMENT_FROZEN_BEFORE_EXECUTION",
        "frozen_at_utc": frozen_at,
        "evidence_root": str(root),
        "authoritative_environment_identity": contract["environment_identity"],
        "authoritative_environment_manifest_sha256": sha256(environment_path),
        "authoritative_gate03f_policy_hash_manifest_sha256": sha256(gate03f_policy / "frozen-bundle.sha256"),
        "technology": contract["technology"],
        "flow": contract["flow"],
        "reference_implementation_id": contract["reference_implementation_id"],
        "runs": contract["runs"],
        "comparison_boundary": contract["comparison_boundary"],
        "power": {**contract["power"], "trace_manifest_sha256": sha256(traces / "TRACE_MANIFEST.json")},
        "execution_policy": contract["execution_policy"],
        "repository": {
            "git_commit": repository_head,
            "worktree_status_sha256": hashlib.sha256(status.encode("utf-8")).hexdigest(),
            "snapshot_file_count": len(source_records),
            "snapshot_files": source_records,
        },
        "exact_commands": {
            "freeze": f"python3 scripts/gate04_final/prepare_experiment.py --repo {repo}",
            "matrix": "python3 /var/lib/green-ecc-date2027-gate04-final/policy/repo_snapshot/scripts/gate04_final/run_matrix.py",
            "analysis": "python3 /var/lib/green-ecc-date2027-gate04-final/policy/repo_snapshot/scripts/gate04_final/analyze_results.py",
        },
    }
    write_json(policy / "GATE04_EXPERIMENT_MANIFEST.json", experiment_manifest)
    write_json(
        policy / "IMMUTABLE_INPUT_MANIFEST.json",
        {
            "schema_version": 1,
            "algorithm": "sha256-raw-bytes",
            "repository_snapshot": source_records,
            "trace_manifest_sha256": sha256(traces / "TRACE_MANIFEST.json"),
            "authoritative_environment_manifest_sha256": sha256(environment_path),
        },
    )
    freeze_hash_manifest(policy)
    for path in (item for item in policy.rglob("*") if item.is_file()):
        path.chmod(0o444)
    for path in sorted((item for item in policy.rglob("*") if item.is_dir()), reverse=True):
        path.chmod(0o555)
    policy.chmod(0o555)
    print(f"GATE04_FINAL_EXPERIMENT_FROZEN root={root} runs=4 traces=9")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
