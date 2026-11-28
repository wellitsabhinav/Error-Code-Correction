"""Run the reconstructed standalone SECDED pair in the existing ORFS image."""

import gzip
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

from campaign_jobs import command, guest_path, wsl_args
from run_campaign import GIB, PACKAGE, REPO, digest, read_json, storage, write_json


PHYSICAL = PACKAGE / "physical"
SLACK = re.compile(r"^worst slack (max|min)\s+([-+\d.eE]+)\s*$", re.MULTILINE)
POWER = re.compile(r"^Total\s+([.eE+\d-]+)\s+([.eE+\d-]+)\s+([.eE+\d-]+)\s+([.eE+\d-]+)", re.MULTILINE)


def stage_inputs(out, config):
    inputs = out / "source"
    expected = read_json(REPO / config["source_identity"])["source_hashes"]
    files = [config["constraints"]]
    for arch in config["physical_profiles"]:
        file = f"scripts/revision2/configs/{arch}.mk"
        files.append(file)
        files.extend(re.findall(r"/rev2-repo/(\S+\.(?:v|sv))", (REPO / file).read_text()))
    for source in sorted(set(files)):
        path = REPO / source
        if source in expected and digest(path) != expected[source]:
            raise ValueError(f"Historical RTL bytes conflict: {source}")
        target = inputs / source
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    return inputs


def trace(out, config):
    workload = config["workload"]
    generator = REPO / workload["generator"]
    spec = importlib.util.spec_from_file_location("gate04_traces", generator)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = out / "trace"
    root.mkdir()
    compressed = root / "activity.vcd.gz"
    record = module.emit_trace(
        compressed, family="conventional_secded", width=72, period_ns=config["clock_period_ns"],
        trace_class="no_error", operations=workload["operations"], payload_seed=workload["payload_seed"],
        fault_seed=workload["fault_seed"], hsiao=[],
    )
    if record["uncompressed_bytes"] > 256 * 2**20:
        raise ValueError("Primary input waveform exceeds the campaign limit")
    with gzip.open(compressed, "rb") as source, (root / "activity.vcd").open("wb") as destination:
        shutil.copyfileobj(source, destination)
    record["generator_sha256"] = digest(generator)
    write_json(root / "manifest.json", record)
    return record


def container(config, name, seconds, *args, mounts=()):
    volumes = [option for host, guest in mounts for option in ("--volume", f"{guest_path(host)}:{guest}")]
    return wsl_args(
        "docker", "run", "--pull", "never", "--rm", "--network", "none", "--platform", "linux/amd64",
        "--name", name, "--cpus", str(config["limits"]["cores"]), "--memory", "2560m",
        "--memory-swap", "2560m", "--pids-limit", "256",
        "--volume", f"{guest_path(PHYSICAL)}:/phase2-plus:ro", *volumes,
        "--entrypoint", "/usr/bin/timeout", config["container"], "--kill-after=10s", f"{seconds}s",
        "/bin/bash", "/phase2-plus/flow.sh", *args,
    )


def run_flow(out, directory, name, args, seconds, budget):
    deadline = time.monotonic() + seconds + 25
    stop_reason = None
    with (directory / "flow.log").open("wb") as log:
        with subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, cwd=REPO) as process:
            write_json(directory / "process.json", {"argv": args, "host_pid": process.pid, "container": name})
            try:
                while process.poll() is None:
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        usage = storage(out.parent.parent)
                        if min(usage["workspace_free_bytes"], usage["campaign_free_bytes"]) < 10 * GIB:
                            stop_reason = "Drive reserve crossed"
                        elif usage["campaign_file_bytes"] > budget:
                            stop_reason = "Projected physical storage ceiling crossed"
                        elif time.monotonic() >= deadline:
                            stop_reason = "Physical wall-clock limit reached"
                        if stop_reason:
                            break
            finally:
                if process.poll() is None:
                    command(directory, "container-stop", wsl_args("docker", "stop", "-t", "5", name), seconds=12)
                    process.kill()
                    process.wait()
    return process.returncode, stop_reason


def metrics(directory, arch, top, seed, code, stop_reason, stimulus):
    result = directory / f"results/sky130hd/{top}/seed{seed}"
    flow_text = (directory / "flow.log").read_text(encoding="utf-8", errors="replace")
    setup_hold = {kind: float(value) for kind, value in SLACK.findall(flow_text)}
    required = ("6_final.odb", "6_final.v", "6_final.sdc", "6_final.spef")
    artifacts = {file.name: digest(file) for file in [*(result / name for name in required),
                    directory / "6_final.sdf", directory / "setup.rpt", directory / "hold.rpt",
                    directory / "method-a.power.rpt"] if file.is_file()}
    power = directory / "method-a.power.rpt"
    match = POWER.search(power.read_text(encoding="utf-8")) if power.is_file() else None
    watts = dict(zip(("internal", "switching", "leakage", "total"), map(float, match.groups()))) if match else None
    area = re.findall(r"Design area\s+(\d+(?:\.\d+)?)", flow_text)
    return {
        "architecture_id": arch,
        "physical_identity": f"PHASE2_PLUS_RECONSTRUCTED_BASELINE_R1/{top}/seed{seed}",
        "placement_seed": seed,
        "technology": "SKY130HD TT 1.8 V 25 C",
        "flow_exit": code,
        "stop_reason": stop_reason,
        "route_artifacts_present": all(name in artifacts for name in required),
        "setup_worst_slack_ns": setup_hold.get("max"),
        "hold_worst_slack_ns": setup_hold.get("min"),
        "reported_design_area_um2": float(area[-1]) if area else None,
        "artifact_sha256": artifacts,
        "method_a_power_w": watts,
        "method_a_energy_j_per_stimulus_op": (
            watts["total"] * stimulus["total_time_ps"] * 1e-12 / stimulus["useful_operations"] if watts else None
        ),
        "observed_completed_operations": None,
        "method_c_energy_j": None,
    }


def run(out, limit):
    config = read_json(PHYSICAL / "contract.json")
    usage = storage(out.parent.parent)
    extra = config["limits"]["peak_bytes_for_pair"]
    if min(usage["workspace_free_bytes"], usage["campaign_free_bytes"]) < 10 * GIB + extra:
        return "BLOCKED", "Estimated physical peak would cross the host free-space reserve"
    if limit < 150:
        return "BLOCKED", "Insufficient remaining budget for physical preflight"
    if (out.parent.parent / "A01/attempt-1/verified").is_dir():
        return "BLOCKED", "Verified historical artifacts need qualification before reconstruction"
    source = stage_inputs(out, config)
    stimulus = trace(out, config)
    write_json(out / "inputs.json", {
        "plan": config, "contract_sha256": digest(PHYSICAL / "contract.json"),
        "source_sha256": {path.relative_to(source).as_posix(): digest(path)
                          for path in sorted(source.rglob("*")) if path.is_file()},
        "workload": stimulus,
    })
    start = time.monotonic()
    code, _ = command(out, "tool-preflight", container(config, "greens-p2p-r1-preflight", 50,
                      "preflight", config["liberty_sha256"]), seconds=65)
    if code != 0:
        return "BLOCKED", "Pinned ORFS tool or Liberty preflight failed"
    observations = []
    seed = config["placement_and_route_seed"]
    for arch, top in config["physical_profiles"].items():
        seconds = min(config["limits"]["seconds_per_implementation"], int(limit - (time.monotonic() - start) - 60))
        if seconds < 60:
            break
        directory = out / arch
        directory.mkdir()
        name = f"greens-p2p-r1-{arch}"
        args = container(config, name, seconds, arch, top, str(seed), mounts=(
            (directory, "/campaign-run"), (source, "/rev2-repo:ro"), (out / "trace", "/trace:ro"),
        ))
        code, reason = run_flow(out, directory, name, args, seconds, usage["campaign_file_bytes"] + extra)
        observations.append(metrics(directory, arch, top, seed, code, reason, stimulus))
        write_json(out / "physical-observations.json", observations)
    if len(observations) == 2 and all(row["flow_exit"] == 0 for row in observations):
        return "COMPLETED", "Both physical tool processes completed; check route, setup, hold and activity independently"
    return "FAILED", "Incomplete reconstruction; the attempt retains the successful stages and failure logs"
