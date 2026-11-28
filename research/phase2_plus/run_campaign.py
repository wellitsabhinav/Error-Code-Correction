"""Fixed-deadline, single-coordinator execution for the Phase II+ campaign."""

import argparse
import contextlib
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


REPO = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent
CONTRACT = REPO / "campaigns/phase2_plus_r1/contract.json"
GIB = 1024**3
DEFAULT_ROOT = (
    Path(r"G:\GREEN-ECC-PHY\experiments\phase2_plus")
    if os.name == "nt"
    else Path("/mnt/g/GREEN-ECC-PHY/experiments/phase2_plus")
)
JOBS = {
    "A00": ("audit", "audit", ()),
    "A01": ("physical", "recover", ("A00",)),
    "B01": ("simulator", "simulator", ("A00",)),
    "B01-EXT": ("simulator", "simulator_extended", ("A00",)),
    "B01-COMB": ("simulator", "simulator_combined", ("B01-EXT",)),
    "A02": ("physical", "reconstruct", ("A01",)),
    "B02-ZERO": ("simulator", "zero_delay", ("A02",)),
    "B05-ZERO": ("simulator", "workloads", ("B02-ZERO",)),
    "A03": ("carbon", "iscas", ("A00",)),
    "C01-C07": ("carbon", "carbon", ("A00",)),
}


def utcnow():
    return datetime.now(timezone.utc)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    ) as stream:
        tmp = Path(stream.name)
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    try:
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


@contextlib.contextmanager
def coordinator_lock(root):
    # A single host coordinator owns this lock. WSL workers do not open it.
    with (root / ".coordinator.lock").open("a+b") as stream:
        if os.name == "nt":
            import msvcrt

            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def storage(root):
    return {
        "workspace_free_bytes": shutil.disk_usage(REPO).free,
        "campaign_free_bytes": shutil.disk_usage(root).free,
        "campaign_file_bytes": sum(
            path.stat().st_size for path in root.rglob("*") if path.is_file()
        ),
    }


def git(*args):
    return subprocess.check_output(["git", *args], cwd=REPO, text=True).strip()


def initialize(root, contract):
    now = utcnow()
    usage = storage(root)
    check_storage(usage, contract)
    baseline = REPO / "research/phase2/baseline_manifest.json"
    if digest(baseline) != contract["baseline_manifest_sha256"]:
        raise ValueError("Baseline manifest identity changed")
    return {
        "campaign_id": contract["campaign_id"],
        "contract_sha256": digest(CONTRACT),
        "started_utc": now.isoformat(),
        "deadline_utc": (now + timedelta(hours=contract["budget_hours"])).isoformat(),
        "starting_commit": git("rev-parse", "HEAD"),
        "remote_tracking_commit": git("rev-parse", "@{upstream}"),
        "branch": git("branch", "--show-current"),
        "current_job": None,
        "jobs": {gate: {"status": "PENDING", "attempts": []} for gate in JOBS},
        "storage_history": [{"utc": now.isoformat(), **usage}],
        "restart_command": "python research/phase2_plus/run_campaign.py --resume"
        + ("" if root == DEFAULT_ROOT.resolve() else f' --root "{root}"'),
    }


def check_storage(usage, contract):
    limits = contract["storage"]
    if min(usage["workspace_free_bytes"], usage["campaign_free_bytes"]) < limits["min_free_gib"] * GIB:
        raise ValueError("Free capacity is below the campaign reserve")
    if usage["campaign_file_bytes"] > limits["max_additional_persistent_gib"] * GIB:
        raise ValueError("Campaign files exceed the persistent storage ceiling")


def input_hashes():
    # Implementation provenance is recorded per attempt. The campaign contract
    # and starting evidence are frozen independently of additive code changes.
    return {
        path.relative_to(REPO).as_posix(): digest(path)
        for path in sorted(PACKAGE.rglob("*"))
        if path.is_file()
        and "__pycache__" not in path.parts
        and (path.suffix in {".py", ".sh", ".tcl", ".sv"}
             or path.name.endswith("contract.json") or path.suffix == ".sdf" or "sustainability" in path.parts)
    }


def artifact_hashes(directory):
    return {
        path.relative_to(directory).as_posix(): digest(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def run_gate(gate, state, path, contract, retry):
    _, stage, dependencies = JOBS[gate]
    entry = state["jobs"][gate]
    if entry["status"] == "COMPLETED":
        attempt = entry["attempts"][-1]
        if artifact_hashes(path.parent / attempt["directory"]) != attempt["artifact_sha256"]:
            entry.update(status="INVALIDATED", reason="Completed output hash mismatch")
        return
    if any(state["jobs"][dependency]["status"] != "COMPLETED" for dependency in dependencies):
        return
    if entry["status"] not in {"PENDING", "RUNNING"} and not retry:
        return
    remaining = (datetime.fromisoformat(state["deadline_utc"]) - utcnow()).total_seconds()
    if remaining <= 0:
        entry.update(status="DEFERRED_BUDGET", reason="Campaign deadline reached")
        return
    if len(entry["attempts"]) > contract["execution"]["retries_after_failure"]:
        return
    if entry["status"] == "RUNNING":
        entry.update(status="FAILED", reason="Previous coordinator interrupted; verify worker exit before retrying")
        state["current_job"] = None
        write_json(path, state)
        return
    check_storage(storage(path.parent), contract)
    worker = PACKAGE / "campaign_jobs.py"
    if not worker.is_file():
        entry.update(status="BLOCKED", reason="Worker implementation is unavailable")
        return
    directory = path.parent / gate / f"attempt-{len(entry['attempts']) + 1}"
    directory.mkdir(parents=True, exist_ok=False)
    limit = min(remaining, contract["archive_search_minutes"] * 60) if gate == "A01" else remaining
    command = [sys.executable, str(worker), stage, str(directory), str(int(limit))]
    attempt = {
        "directory": directory.relative_to(path.parent).as_posix(),
        "started_utc": utcnow().isoformat(),
        "commit": git("rev-parse", "HEAD"),
        "input_sha256": input_hashes(),
        "argv": command,
        "timeout_seconds": limit,
    }
    entry["attempts"].append(attempt)
    entry.update(status="RUNNING", reason=None)
    state["current_job"] = gate
    write_json(path, state)
    with (directory / "worker.log").open("wb") as log:
        with subprocess.Popen(command, cwd=REPO, stdout=log, stderr=subprocess.STDOUT) as worker_process:
            attempt["pid"] = worker_process.pid
            write_json(path, state)
            try:
                attempt["returncode"] = worker_process.wait(timeout=limit)
            except subprocess.TimeoutExpired:
                worker_process.kill()
                worker_process.wait()
                entry.update(status="FAILED", reason="Worker deadline reached")
            except KeyboardInterrupt:
                worker_process.terminate()
                raise
    result_path = directory / "result.json"
    if entry["status"] == "RUNNING":
        if attempt["returncode"] == 0 and result_path.is_file():
            result = read_json(result_path)
            if result["status"] not in {"BLOCKED", "COMPLETED", "FAILED"}:
                raise ValueError(f"Invalid worker status for {gate}")
            entry.update(status=result["status"], reason=result.get("reason"))
        else:
            entry.update(status="FAILED", reason="Worker exited without a valid result")
    attempt.update(finished_utc=utcnow().isoformat(), artifact_sha256=artifact_hashes(directory))
    state["current_job"] = None
    state["storage_history"].append({"utc": utcnow().isoformat(), **storage(path.parent)})
    write_json(path, state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--initialize", action="store_true")
    action.add_argument("--status", action="store_true")
    action.add_argument("--audit", action="store_true")
    action.add_argument("--resume", action="store_true")
    action.add_argument("--track", choices=("physical", "simulator", "carbon"))
    action.add_argument("--gate", choices=JOBS)
    parser.add_argument("--root", default=DEFAULT_ROOT, type=Path)
    parser.add_argument("--retry", action="store_true", help="Retry an unsuccessful gate once after correcting its blocker")
    args = parser.parse_args()
    root = args.root.resolve()
    path = root / "campaign.json"
    contract = read_json(CONTRACT)
    if args.status:
        state = read_json(path)
        print(json.dumps({key: value for key, value in state.items() if key != "jobs"} | {
            "head_now": git("rev-parse", "HEAD"),
            "upstream_tracking_now": git("rev-parse", "@{upstream}"),
            "remaining_seconds": max(0, (datetime.fromisoformat(state["deadline_utc"]) - utcnow()).total_seconds()),
            "jobs": {gate: {"status": row["status"], "reason": row.get("reason"),
                           "attempts": len(row["attempts"])} for gate, row in state["jobs"].items()},
        }, indent=2))
        return
    if args.initialize:
        root.mkdir(parents=True, exist_ok=True)
    with coordinator_lock(root):
        if args.initialize and not path.exists():
            write_json(path, initialize(root, contract))
        state = read_json(path)
        if state["contract_sha256"] != digest(CONTRACT):
            raise ValueError("Campaign contract changed; the original deadline cannot be renewed")
        for gate in JOBS:
            state["jobs"].setdefault(gate, {"status": "PENDING", "attempts": []})
        if not args.initialize:
            for gate, (track, _, _) in JOBS.items():
                if args.resume or args.track == track or (args.audit and gate == "A00") or args.gate == gate:
                    run_gate(gate, state, path, contract, args.retry)
                    write_json(path, state)
        for gate, entry in state["jobs"].items():
            print(f"{gate} {entry['status']} {entry.get('reason') or ''}".rstrip())
        print(f"{state['campaign_id']} deadline {state['deadline_utc']}")


if __name__ == "__main__":
    main()
