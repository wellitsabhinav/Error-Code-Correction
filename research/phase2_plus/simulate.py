"""Build and qualify a pinned Icarus release under the synthetic-test scope."""

import math
import re
import shutil
import sys

from campaign_jobs import command, guest_path, replay_synthetic, wsl_args
from run_campaign import GIB, PACKAGE, digest, read_json, storage, write_json


SCRIPTS = PACKAGE / "simulator"


def matching_previous(root, inputs):
    state = read_json(root / "campaign.json")
    for attempt in reversed(state["jobs"]["B01"]["attempts"]):
        previous = root / attempt["directory"]
        receipt = attempt.get("artifact_sha256", {})
        if ("icarus13/bin/vvp" not in receipt
                or read_json(previous / "build-inputs.json")["inputs"] != inputs):
            continue
        selected = [name for name in receipt if name.startswith("icarus13/")
                    or re.search(r"upstream-checks/.*\.(?:v|sdf|gold)$", name)]
        if all((previous / name).is_file() and digest(previous / name) == receipt[name] for name in selected):
            return previous
    return None


def upstream(out, built):
    dest = out / "upstream-validated"
    (dest / "ivltests").mkdir(parents=True)
    for name in ("sdf_interconnect1", "sdf_interconnect2", "sdf_interconnect3", "sdf_interconnect4"):
        for suffix in (".v", ".sdf", "-vvp-stdout.gold"):
            target = dest / name if suffix.endswith("gold") else dest / "ivltests" / name
            shutil.copyfile(built / "upstream-checks" / (name + suffix), target.with_name(name + suffix))
    return command(out, "upstream-tests", wsl_args(
        "bash", guest_path(SCRIPTS / "upstream_checks.sh"), guest_path(dest), guest_path(built / "icarus13")
    ), seconds=60)[0]


def combined_probes(out, prefix, helper):
    from run_campaign import REPO
    sys.path.insert(0, str(REPO / "research/phase2/scripts"))
    try:
        from activity_stream import parse_vcd
    finally:
        sys.path.pop(0)
    sdf = (SCRIPTS / "combined.sdf").read_text()
    ps_sdf = re.sub(r"(\d+\.\d+):(\d+\.\d+):(\d+\.\d+)",
                    lambda match: ":".join(str(round(float(n) * 1000)) for n in match.groups()),
                    sdf.replace("1ns", "1ps"))
    measurements = []
    for units, content in (("ns", sdf), ("ps", ps_sdf)):
        trial = out / f"combined-{units}"
        trial.mkdir()
        (trial / "combined.sdf").write_text(content, encoding="ascii", newline="\n")
        binary = trial / "combined.vvp"
        cwd = guest_path(trial)
        front = wsl_args("bash", guest_path(SCRIPTS / "run_in.sh"), cwd)
        code, _ = command(trial, "compile", front + [
            prefix + "/bin/iverilog", "-B", helper, "-g2012", "-gspecify", "-ginterconnect",
            "-s", "phase2_combined_tb", "-o", guest_path(binary), guest_path(SCRIPTS / "combined.sv"),
        ], seconds=20)
        execution = None
        output = b""
        if code == 0:
            argv = front + [prefix + "/bin/vvp", guest_path(binary), "+SDF=combined.sdf"]
            execution, output = command(trial, "run", argv, seconds=20)
        observation = {"sdf_timescale": units, "compile_exit": code, "execution_exit": execution,
                       "expected_synthetic_arcs": 5, "applied_constructs_from_output": None, "status": "FAIL"}
        vcd = trial / "activity.vcd"
        if execution == 0 and vcd.is_file():
            with vcd.open(encoding="utf-8") as stream:
                activity = parse_vcd(stream, 5000, 44000)
            row = next(row for row in activity["signals"] if "phase2_combined_tb.hazard" in row["aliases"])
            high = row["durations_ps"]["1"]
            observation.update(transitions=row["binary_transitions"], high_duration_ps=high,
                               unknown_ps=row["durations_ps"]["x"] + row["durations_ps"]["z"],
                               vcd_sha256=digest(vcd), pulse_segments_ps=row["pulse_samples_ps"])
            exact_edges = (b"FAST 10450 1", b"SLOW 11550 1", b"FAST 31050 0", b"SLOW 32250 0")
            if (row["binary_transitions"] == 4 and math.isclose(high, 2300, abs_tol=1)
                    and observation["unknown_ps"] == 0 and all(edge in output for edge in exact_edges)
                    and b"SDF WARNING" not in output and b"SDF ERROR" not in output):
                observation.update(status="PASS", applied_constructs_from_output=5)
        measurements.append(observation)
    write_json(out / "combined-results.json", measurements)
    return measurements


def combined_retry(out):
    config = read_json(SCRIPTS / "contract.json")
    inputs = {"iverilog-v13_0.tar.gz": config["archive_sha256"]} | {
        "deb/" + name: expected for name, expected in config["build_packages"].items()
    }
    previous = matching_previous(out.parent.parent, inputs)
    if previous is None:
        return "BLOCKED", "No hash-verified v13 build for the combined fixture"
    prefix = guest_path(previous / "icarus13")
    rows = combined_probes(out, prefix, prefix + "/lib/ivl")
    count = sum(row["status"] == "PASS" for row in rows)
    return "COMPLETED", f"Combined synthetic probes passed {count}/{len(rows)} timescale controls"


def extend(out):
    config = read_json(SCRIPTS / "contract.json")
    inputs = {"iverilog-v13_0.tar.gz": config["archive_sha256"]} | {
        "deb/" + name: expected for name, expected in config["build_packages"].items()
    }
    root = out.parent.parent
    previous = matching_previous(root, inputs)
    if previous is None:
        return "BLOCKED", "No hash-verified v13 build to extend"
    prefix = guest_path(previous / "icarus13")
    helper = prefix + "/lib/ivl"
    completed = read_json(root / "campaign.json")["jobs"]["B01"]["attempts"]
    latest = next((a for a in reversed(completed) if "artifact_sha256" in a), None)
    receipt = latest["artifact_sha256"]
    audited = root / latest["directory"] / "upstream-validated"
    checks = {}
    for label in ("sdf_interconnect1", "sdf_interconnect2", "sdf_interconnect3", "sdf_interconnect4"):
        diff = audited / f"{label}.diff"
        checks[label] = diff.is_file() and diff.stat().st_size == 0 and digest(diff) == receipt.get(
            f"upstream-validated/{label}.diff"
        )
    result = replay_synthetic(out, "icarus13_extended", prefix, helper)
    combined_probes(out, prefix, helper)
    write_json(out / "upstream-gold-controls.json", checks)
    return result


def qualify(out, limit):
    config = read_json(SCRIPTS / "contract.json")
    root = out.parent.parent
    tool_inputs = root / "tool-inputs"
    inputs = {"iverilog-v13_0.tar.gz": config["archive_sha256"]} | {
        "deb/" + name: expected for name, expected in config["build_packages"].items()
    }
    if any(not (tool_inputs / name).is_file() or digest(tool_inputs / name) != expected
           for name, expected in inputs.items()):
        return "BLOCKED", "Pinned simulator source or build-package bytes are unavailable"
    usable = storage(root)
    if min(usable["workspace_free_bytes"], usable["campaign_free_bytes"]) < 11 * GIB:
        return "BLOCKED", "Free capacity is insufficient for simulator build"
    seconds = min(config["build_seconds"], limit - 180)
    if seconds < 60:
        return "BLOCKED", "Insufficient campaign time for simulator build"
    previous = matching_previous(root, inputs)
    write_json(out / "build-inputs.json", {"contract_sha256": digest(SCRIPTS / "contract.json"), "inputs": inputs,
                                         "reused_build_attempt": previous.name if previous else None})
    args = wsl_args(
        "docker", "run", "--pull", "never", "--rm", "--network", "none", "--platform", "linux/amd64",
        "--name", "greens-p2p-r1-icarus-build", "--cpus", str(config["cores"]),
        "--memory", f"{config['memory_mib']}m", "--memory-swap", f"{config['memory_mib']}m",
        "--pids-limit", "256", "--volume", f"{guest_path(SCRIPTS)}:/probe:ro",
        "--volume", f"{guest_path(tool_inputs)}:/tool-inputs:ro", "--volume", f"{guest_path(out)}:/campaign-run",
        "--entrypoint", "/usr/bin/timeout", config["image"], "--kill-after=10s", f"{seconds}s",
        "/bin/bash", "/probe/build.sh",
    )
    if previous is None:
        code, _ = command(out, "build", args, seconds=seconds + 25)
        if code != 0:
            return "FAILED", "Pinned Icarus build failed"
    built = previous or out
    prefix = built / "icarus13"
    base = next((p.parent for p in prefix.rglob("ivl") if p.is_file()), None)
    if base is None:
        return "FAILED", "Icarus helper path missing after build"
    upstream_code = upstream(out, built)
    result = replay_synthetic(out, "icarus13", guest_path(prefix), guest_path(base))
    combined_probes(out, guest_path(prefix), guest_path(base))
    if upstream_code != 0:
        return "FAILED", "Upstream interconnect gold check failed"
    return result
