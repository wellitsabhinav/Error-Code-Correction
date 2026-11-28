"""Execute one campaign gate and keep its evidence in the assigned attempt."""

import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

from run_campaign import CONTRACT, PACKAGE, REPO, digest, git, read_json, storage, write_json


HISTORY = "967015e1501bf237800f8851bd78ea12f36938af"
ARCHIVE_DIR = Path("D:/GREENS_ARCHIVES/physical_validation")
SIM_CACHE = "/mnt/f/AgenticAI/.local/m9-icarus-linux/extracted"
ARCHIVE_NAMES = (
    "green-ecc-date2027-revision2-runs.tar.gz",
    "green-ecc-date2027-breadth-remediation-runs.tar.gz",
)
PHASE = REPO / "research/phase2"


def command(out, label, args, seconds=120, cwd=REPO):
    start = time.monotonic()
    try:
        process = subprocess.run(args, cwd=cwd, capture_output=True, timeout=seconds, check=False)
        code, stdout, stderr = process.returncode, process.stdout, process.stderr
    except subprocess.TimeoutExpired as error:
        code, stdout, stderr = None, error.stdout or b"", (error.stderr or b"") + b"\nTimeout"
    except FileNotFoundError as error:
        code, stdout, stderr = None, b"", str(error).encode()
    log = out / f"{label}.log"
    log.write_bytes(stdout[-2**20:] + b"\n" + stderr[-2**20:])
    with (out / "commands.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"argv": list(map(str, args)), "exit": code,
                                 "seconds": time.monotonic() - start, "log": log.name}) + "\n")
    return code, stdout


def wsl_args(*args):
    return ["wsl.exe", "-d", "AutonomousEDA", "--", *args] if os.name == "nt" else list(args)


def guest_path(path):
    if os.name != "nt":
        return path.as_posix()
    drive, remainder = path.resolve().as_posix().split(":", 1)
    return f"/mnt/{drive.lower()}{remainder}"


def audit(out, _):
    py = sys.executable
    check, _ = command(out, "phase2-integrity", [py, "research/phase2/scripts/validate_phase2.py"])
    tests, _ = command(out, "phase2-tests", [py, "-m", "pytest", "-q", "-rs", "research/phase2/tests"])
    command(out, "storage-guest", wsl_args("df", "-B1", "/", "/mnt/c", "/mnt/g", "/mnt/f"))
    command(out, "memory-guest", wsl_args("free", "-b"))
    command(out, "cpu-guest", wsl_args("nproc"))
    write_json(out / "checkpoint.json", {
        "commit": git("rev-parse", "HEAD"),
        "remote_tracking_commit": git("rev-parse", "@{upstream}"),
        "branch": git("branch", "--show-current"),
        "baseline_manifest_sha256": digest(PHASE / "baseline_manifest.json"),
        "tracked_changes": git("status", "--porcelain", "--untracked-files=no").splitlines(),
        "sparse_checkout": git("sparse-checkout", "list").splitlines(),
        "storage": storage(out.parent.parent),
        "tools_on_path": {name: shutil.which(name) is not None for name in
                          ("python", "make", "gh", "g++", "wsl", "iverilog", "yosys")},
        "baseline_exit": check,
        "baseline_tests_exit": tests,
    })
    return ("COMPLETED", None) if check == tests == 0 else ("FAILED", "Phase II validation failed")


def git_blob(relative):
    # Bounded readers name the specific pinned blobs they require.
    env = dict(os.environ, GIT_NO_LAZY_FETCH="1")
    return subprocess.check_output(["git", "cat-file", "--filters", f"{HISTORY}:{relative}"],
                                   cwd=REPO, env=env, timeout=45)


def release_artifacts(out):
    result = {}
    base = "https://api.github.com/repos/wellitsabhinav/Error-Code-Correction"
    for endpoint in ("releases?per_page=100", "actions/artifacts?per_page=100"):
        try:
            with urlopen(Request(f"{base}/{endpoint}", headers={"User-Agent": "GREENS-research"}), timeout=12) as response:
                body = json.loads(response.read(2**20))
            if isinstance(body, list):
                result["releases"] = [
                    {"tag": row["tag_name"], "assets": [asset["name"] for asset in row["assets"]]}
                    for row in body
                ]
            else:
                result["actions_total"] = body["total_count"]
                result["actions"] = [{field: row[field] for field in ("name", "expired", "size_in_bytes")}
                                     for row in body["artifacts"]]
        except (URLError, TimeoutError, ValueError) as error:
            result[endpoint] = str(error)
    write_json(out / "github-archive-index.json", result)


def search_archive_roots(out):
    candidates = {name: [] for name in ARCHIVE_NAMES}
    for name in candidates:
        direct = ARCHIVE_DIR / name
        if direct.is_file():
            candidates[name].append(direct)
    roots = (
        Path("G:/GREEN-ECC-PHY"), Path("G:/ECC Continued"),
        Path("F:/Research/PhysicalDesignResearch"), REPO.parent,
    )
    for root in roots:
        if not root.is_dir():
            continue
        for directory, dirs, files in os.walk(root):
            relative = Path(directory).relative_to(root)
            dirs[:] = [name for name in dirs if name not in {".git", "phase2_plus", "node_modules", "tmp"}
                       and len(relative.parts) < 5]
            for name in sorted(set(files) & candidates.keys()):
                candidates[name].append(Path(directory) / name)
    command(out, "wsl-archive-search", wsl_args(
        "find", "/opt", "/home", "/var/lib", "/mnt/d", "/mnt/g", "-maxdepth", "3",
        "(", "-name", ARCHIVE_NAMES[0], "-o", "-name", ARCHIVE_NAMES[1], ")", "-print",
    ), seconds=75)
    return candidates


def recover(out, _):
    candidates = search_archive_roots(out)
    release_artifacts(out)
    command(out, "git-archive-history", ["git", "log", "--all", "--oneline", "--", "archives/MANIFEST.csv"])
    command(out, "git-physical-members", ["git", "ls-tree", "-r", "--name-only", "HEAD", "docs/date2027",
                                          "campaigns/date_2027_activity_qualified_ecc_energy_rev2",
                                          "campaigns/date_2027_breadth_remediation"])
    archive_index = list(csv.DictReader(git_blob("archives/MANIFEST.csv").decode("utf-8-sig").splitlines()))
    expected_archives = {name: next(row for row in archive_index
                                    if any(value.endswith("/" + name) for value in row.values()))
                         for name in ARCHIVE_NAMES}
    ref = read_json(PHASE / "manifests/archived_physical_references.json")
    rows = []
    for name, paths in candidates.items():
        expected = next(value for value in expected_archives[name].values()
                        if len(value) == 64 and all(c in "0123456789abcdef" for c in value))
        archive = next((path for path in paths if digest(path) == expected), None)
        rows.append({"artifact": name, "expected_sha256": expected,
                     "status": "EXACT_HASH_MATCH" if archive else "INCOMPATIBLE" if paths else "MISSING"})
        if name != ARCHIVE_NAMES[0] or archive is None:
            continue
        # Stream the archive and extract only the explicitly frozen member set.
        members = {row["path"]: row["sha256"] for row in ref["selected_members"]}
        with tarfile.open(archive, "r|gz") as stream:
            for member in stream:
                if member.name not in members or not member.isfile():
                    continue
                target = out / "verified" / member.name
                target.parent.mkdir(parents=True, exist_ok=True)
                with stream.extractfile(member) as source, target.open("wb") as destination:
                    shutil.copyfileobj(source, destination)
                if digest(target) != members[member.name]:
                    raise ValueError(f"Archive member hash mismatch: {member.name}")
                rows.append({"artifact": member.name, "status": "EXACT_HASH_MATCH",
                             "expected_sha256": members[member.name]})
    write_json(out / "artifact-inventory.json", rows)
    return "COMPLETED", "Archive search finished; see inventory for recovery status"


def replay_synthetic(out, simulator, prefix, base):
    # Run the original probe from a small isolated copy so historical paths,
    # checkpoints, VCDs, and package hashes remain byte-identical.
    clone = out / "probe/research/phase2"
    for name in ("verification", "scripts"):
        shutil.copytree(PHASE / name, clone / name, ignore=shutil.ignore_patterns("__pycache__"))
    bench = clone / "verification/hazard_tb.sv"
    old = bench.read_text(encoding="utf-8")
    new = old.replace("reg [1023:0] sdf_file, vcd_file;", "string sdf_file, vcd_file;")
    if old == new:
        raise ValueError("Synthetic bench path-storage declaration changed")
    bench.write_text(new, encoding="utf-8", newline="\n")
    entry = clone / "scripts/qualify_simulator.py"
    run_id = "p2plus_" + simulator
    front = wsl_args("bash", guest_path(PACKAGE / "simulator/replay.sh"),
                     guest_path(out / "probe"), guest_path(entry))
    code, _ = command(out, "simulator-probe", front + [
        "--run-id", run_id, "--consistent-timescale",
        "--iverilog", prefix + "/bin/iverilog", "--vvp", prefix + "/bin/vvp", "--ivl-base", base,
    ], seconds=150)
    if code != 0:
        return "BLOCKED", "Cached simulator probe did not execute successfully"
    result = clone / "raw" / run_id / "results.json"
    if not result.is_file():
        return "FAILED", "Simulator qualification did not produce a result"
    return "COMPLETED", "Synthetic qualification finished; production eligibility is recorded separately"


def simulator(out, limit):
    from simulate import qualify
    result = qualify(out, limit)
    if result[0] == "COMPLETED":
        return result
    control = out / "cached-v12"
    control.mkdir()
    replay_synthetic(control, "icarus12", SIM_CACHE + "/usr", SIM_CACHE + "/usr/lib/x86_64-linux-gnu/ivl")
    return result


def simulator_extended(out, _):
    from simulate import extend
    return extend(out)


def simulator_combined(out, _):
    from simulate import combined_retry
    return combined_retry(out)


def zero_delay(out, limit):
    from zero_delay import run
    return run(out, limit)


def workloads(out, limit):
    from workload_pilot import run
    return run(out, limit)


def reconstruct(out, limit):
    from physical import run
    return run(out, limit)


def iscas(out, limit):
    from reproduce_sram_snapshot import run
    return run(out, limit)


def carbon(out, _):
    from scenarios import generate
    generate(out)
    return "COMPLETED", "Historical-estimator-conditioned scenario derivations"


def main():
    stage, directory, seconds = sys.argv[1:]
    out = Path(directory)
    jobs = {"audit": audit, "recover": recover, "simulator": simulator, "simulator_extended": simulator_extended,
            "simulator_combined": simulator_combined,
            "zero_delay": zero_delay, "workloads": workloads, "reconstruct": reconstruct,
            "iscas": iscas, "carbon": carbon}
    status, reason = jobs[stage](out, int(seconds))
    write_json(out / "result.json", {"status": status, "reason": reason})


if __name__ == "__main__":
    main()
