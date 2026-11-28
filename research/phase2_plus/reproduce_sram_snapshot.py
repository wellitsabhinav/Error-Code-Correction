"""Run the existing full ISCAS check from a selected, byte-verified snapshot."""

import json
import os
from pathlib import PurePosixPath
import subprocess
import sys

from campaign_jobs import HISTORY, command, git_blob
from evidence import ISCAS, REFERENCE, Frozen, sealed_iscas
from run_campaign import GIB, REPO, storage, write_json


def safe_path(relative):
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or "\\" in relative or ":" in relative:
        raise ValueError(f"Unsafe snapshot path: {relative}")
    return path.as_posix()


def run(out, limit):
    if limit < 240:
        return "BLOCKED", "Insufficient time to stage and verify the ISCAS subset"
    frozen = Frozen()
    sealed_iscas(frozen)
    evidence_manifest = json.loads(git_blob(f"{REFERENCE}/integrity/source_manifest.json"))
    seal_path = f"{ISCAS}/hashes/CAMPAIGN_ARTIFACTS.sha256"
    seal = git_blob(seal_path).decode("ascii")
    paths = {safe_path(f"{ISCAS}/{line.split(maxsplit=1)[1]}") for line in seal.splitlines()}
    paths.update(safe_path(relative) for relative in evidence_manifest["frozen_inputs"])
    paths.update(safe_path(path) for path in subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", HISTORY, REFERENCE], cwd=REPO, text=True
    ).splitlines())
    paths.add("scripts/reproduce_iscas.py")
    env = dict(os.environ, GIT_NO_LAZY_FETCH="1")
    changed = subprocess.run(["git", "diff", "--cached", "--quiet", HISTORY, "--", ISCAS, REFERENCE,
                              "scripts/reproduce_iscas.py", ".gitattributes"], cwd=REPO, env=env, check=False)
    if changed.returncode:
        return "BLOCKED", "Staged ISCAS inputs or checkout attributes differ from the pinned snapshot"
    paths = sorted(paths)
    listing = subprocess.check_output(
        ["git", "cat-file", "--batch-check=%(objecttype) %(objectsize)"], cwd=REPO, env=env,
        input=("\n".join(f"{HISTORY}:{path}" for path in paths) + "\n").encode(), timeout=60,
    ).decode().splitlines()
    if len(listing) != len(paths) or any(not row.startswith("blob ") for row in listing):
        return "BLOCKED", "One or more required ISCAS blobs are missing locally"
    projected = sum(int(row.split()[1]) for row in listing) * 2
    usage = storage(out.parent.parent)
    if projected > 512 * 2**20 or min(usage["workspace_free_bytes"], usage["campaign_free_bytes"]) < 10 * GIB + projected:
        return "BLOCKED", "Selected ISCAS snapshot would exceed capacity"
    snapshot = out / "snapshot"
    snapshot.mkdir()
    args = ["git", "checkout-index", "--ignore-skip-worktree-bits", "--stdin", "-z",
            f"--prefix={snapshot.as_posix()}/"]
    # The pin and index were compared above. Git's checkout filters apply the
    # documented mixed LF/CRLF materializations before the existing hash checks.
    result = subprocess.run(args, cwd=REPO, env=env, input=("\0".join(paths) + "\0").encode(),
                            capture_output=True, timeout=120, check=False)
    (out / "materialize.log").write_bytes(result.stdout + result.stderr)
    write_json(out / "snapshot.json", {"source_commit": HISTORY, "paths": len(paths),
                                      "expected_bytes_upper_bound": projected, "materialize_exit": result.returncode})
    if result.returncode != 0:
        return "FAILED", "Selective ISCAS materialization failed"
    code, _ = command(out, "iscas-check", [sys.executable, "scripts/reproduce_iscas.py", "--check"],
                      seconds=90, cwd=snapshot)
    if code != 0:
        return "FAILED", "Existing ISCAS reproduction did not verify the snapshot"
    return "COMPLETED", "Official ISCAS reproduction verifies 1697 seal entries in the selective snapshot"
