"""Same-netlist primary-input and zero-delay internal activity preflight."""

from pathlib import Path
import re
import sys

from campaign_jobs import SIM_CACHE, command, guest_path, wsl_args
from physical import PHYSICAL, POWER, container, metrics
from run_campaign import GIB, PACKAGE, REPO, digest, read_json, storage, write_json


PIN_COUNTS = re.compile(r"^([A-Za-z_]+)\s+(\d+)\s*$", re.MULTILINE)
INPUTS = ("clk_i", "rst_ni", "valid_i", "enc_data_i", "dec_codeword_i")
SIM_TOOLS = PACKAGE / "simulator"


def trim_vcd(src, dest, start_ps, end_ps):
    """Emit known values at a new origin and preserve changes through the stop."""
    if end_ps <= start_ps:
        raise ValueError("Waveform window must have positive duration")
    with src.open(encoding="ascii") as source, dest.open("w", encoding="ascii", newline="\n") as target:
        header = []
        for line in source:
            target.write(line)
            header.append(line)
            if line.strip().startswith("$enddefinitions"):
                break
        if not re.search(r"\$timescale\s+1\s*ps\s+\$end", "".join(header)):
            raise ValueError("Waveform is outside the qualified 1 ps window protocol")
        time_ps = 0
        values = {}
        started = False
        for raw in source:
            line = raw.strip()
            if not line or line.startswith("$"):
                continue
            if line.startswith("#"):
                time_ps = int(line[1:])
                if time_ps > start_ps and not started:
                    target.write("#0\n$dumpvars\n")
                    target.writelines(f"{value}\n" for value in values.values())
                    target.write("$end\n")
                    started = True
                if time_ps > end_ps:
                    break
                if started:
                    target.write(f"#{time_ps - start_ps}\n")
            elif started:
                target.write(line + "\n")
            else:
                code = line.split()[-1] if line[0] in "bB" else line[1:]
                values[code] = line
        if not started or time_ps < end_ps:
            raise ValueError("Raw VCD does not span the entire observation window")


def simulation_vectors(vcd, out, count):
    payload, codewords = [], []
    with vcd.open(encoding="ascii") as stream:
        for line in stream:
            if not line.startswith("b"):
                continue
            value, key = line.split()
            if key == "#":
                payload.append(int(value[1:], 2))
            if key == "$":
                codewords.append(int(value[1:], 2))
    for values, width, filename in ((payload, 16, "payload.hex"), (codewords, 18, "codewords.hex")):
        if len(values) != count + 2 or values[0] != 0 or values[-1] != 0:
            raise ValueError("Unexpected stimulus initialization, count or drain")
        (out / filename).write_text("".join(f"{v:0{width}x}\n" for v in values[1:-1]), encoding="ascii")


def wave_activity(vcd, duration):
    sys.path.insert(0, str(REPO / "research/phase2/scripts"))
    try:
        from activity_stream import parse_vcd
    finally:
        sys.path.pop(0)
    with vcd.open(encoding="ascii") as stream:
        return parse_vcd(stream, 0, duration)


def input_signature(activity, scope):
    signatures = {}
    for signal in activity["signals"]:
        for alias in signal["aliases"]:
            port = alias.removeprefix(scope + ".")
            base, bracket, _ = port.partition("[")
            if base in INPUTS:
                key = f"{base}[{signal['bit']}]" if bracket else base
                signatures[key] = (signal["binary_transitions"], signal["durations_ps"]["0"],
                                   signal["durations_ps"]["1"], signal["durations_ps"]["x"], signal["durations_ps"]["z"])
    if len(signatures) != 139:
        raise ValueError(f"Incomplete primary port activity signature: {len(signatures)} of 139")
    return signatures


def power(config, direc, routed, activity, scope, name):
    run = container(config, name, 60, scope, mounts=(
        (direc, "/campaign-run"), (activity, "/activity:ro"), (routed, "/routed:ro"),
    ))
    # Select another pinned entry script while keeping the same immutable image.
    run[run.index("/phase2-plus/flow.sh")] = "/phase2-plus/zero_tool.sh"
    code, _ = command(direc, "openroad", run, seconds=80)
    if code != 0:
        return None
    annotations = [{name: int(value) for name, value in PIN_COUNTS.findall(
        (direc / file).read_text(encoding="utf-8")
    )} for file in ("annotation.rpt", "annotation_after_power.rpt")]
    match = POWER.search((direc / "power.rpt").read_text(encoding="utf-8"))
    if not match or not annotations[0].get("vcd"):
        return None
    return {"power_w": dict(zip(("internal", "switching", "leakage", "total"), map(float, match.groups()))),
            "before": annotations[0], "after": annotations[1],
            "direct_vcd_pin_fraction": annotations[0]["vcd"] / sum(annotations[0].values())}


def run(out, limit):
    if limit < 300:
        return "BLOCKED", "Insufficient budget for method A/B preflight"
    root = out.parent.parent
    use = storage(root)
    if min(use["workspace_free_bytes"], use["campaign_free_bytes"]) < 11 * GIB:
        return "BLOCKED", "Space for bounded A/B waveforms is unavailable"
    parent = read_json(root / "campaign.json")["jobs"]["A02"]["attempts"][-1]
    physical = root / parent["directory"]
    controls = read_json(PHYSICAL / "zero_delay_contract.json")
    config = read_json(PHYSICAL / "contract.json")
    source = physical / "trace/activity.vcd"
    if digest(source) != parent["artifact_sha256"]["trace/activity.vcd"]:
        return "FAILED", "Parent input VCD no longer matches reconstruction receipt"
    count = controls["operation_count"]
    start, stop = controls["window_start_ps"], controls["window_end_ps"]
    a_dir = out / "primary"
    a_dir.mkdir()
    trim_vcd(source, a_dir / "window.vcd", start, stop)
    a_signature = input_signature(wave_activity(a_dir / "window.vcd", stop - start), "gate04_trace_top")
    model = out / "model"
    model.mkdir()
    argv = container(config, "greens-p2p-r1-functional-model", 40, "library", mounts=((model, "/campaign-run"),))
    argv[argv.index("/phase2-plus/flow.sh")] = "/phase2-plus/zero_tool.sh"
    code, _ = command(out, "models", argv, seconds=55)
    if code != 0:
        return "FAILED", "Could not generate the functional model from the tied Liberty"
    library = model / "functional.v"
    write_json(out / "inputs.json", {"protocol_sha256": digest(PHYSICAL / "zero_delay_contract.json"),
                                    "parent_attempt": parent["directory"], "library_model_sha256": digest(library),
                                    "matched_primary_trace_sha256": digest(source)})
    results = []
    seed = config["placement_and_route_seed"]
    for arch, top in config["physical_profiles"].items():
        rtl = physical / arch
        netdir = rtl / f"results/sky130hd/{top}/seed{seed}"
        for name in ("6_final.odb", "6_final.v", "6_final.sdc", "6_final.spef"):
            path = netdir / name
            if parent["artifact_sha256"][path.relative_to(physical).as_posix()] != digest(path):
                raise ValueError(f"Parent physical-change detection: {name}")
        phy = metrics(rtl, arch, top, seed, 0, None, read_json(physical / "trace/manifest.json"))
        if not phy["route_artifacts_present"] or min(phy["setup_worst_slack_ns"], phy["hold_worst_slack_ns"]) < 0:
            raise ValueError("Parent route, setup or hold prerequisite failed")
        arch_dir = out / arch
        arch_dir.mkdir()
        simulation_vectors(source, arch_dir, count)
        base = SIM_CACHE + "/usr"
        front = wsl_args("bash", guest_path(SIM_TOOLS / "run_in.sh"), guest_path(arch_dir))
        compile_code, _ = command(arch_dir, "compile", front + [
            base + "/bin/iverilog", "-B", base + "/lib/x86_64-linux-gnu/ivl", "-g2012",
            "-s", "phase2_gate_tb", f"-DP2P_TOP={top}", "-DP2P_LATENCY=" + ("1" if arch.endswith("comb") else "3"),
            "-o", "gate.vvp", guest_path(PHYSICAL / "zero_delay_tb.sv"), guest_path(netdir / "6_final.v"),
            guest_path(library),
        ], seconds=45)
        if compile_code != 0:
            return "FAILED", f"Zero-delay compile failed for {arch}"
        exit_code, stdout = command(arch_dir, "simulation", front + [
            "timeout", "--kill-after=5s", "50s", "prlimit", f"--fsize={controls['single_waveform_bytes']}",
            base + "/bin/vvp", "gate.vvp"
        ], seconds=65)
        if exit_code != 0 or f"SCOREBOARD_PASS completed={count}".encode() not in stdout:
            return "FAILED", f"Zero-delay scoreboard or storage guard failed for {arch}"
        gate_vcd = arch_dir / "gate.vcd"
        trimmed = arch_dir / "window.vcd"
        trim_vcd(gate_vcd, trimmed, start, stop)
        activity = wave_activity(trimmed, stop - start)
        matched = a_signature == input_signature(activity, "phase2_gate_tb.dut")
        if not matched:
            write_json(arch_dir / "input-differences.json", {
                "reference": a_signature, "observed": input_signature(activity, "phase2_gate_tb.dut")})
            return "FAILED", f"Zero-delay primary stimulus differs for {arch}"
        summary = {key: value for key, value in activity.items() if key != "signals"}
        summary["unknown_bit_time_ps"] = sum(signal["durations_ps"]["x"] + signal["durations_ps"]["z"]
                                             for signal in activity["signals"])
        summary["binary_transitions"] = sum(signal["binary_transitions"] for signal in activity["signals"])
        write_json(arch_dir / "activity_summary.json", summary)
        for label, waves, scope in (("A", a_dir, "gate04_trace_top"), ("B", arch_dir, "phase2_gate_tb/dut")):
            report = arch_dir / f"method-{label}"
            report.mkdir()
            row = power(config, report, netdir, waves, scope, f"greens-p2p-r1-{arch}-method-{label.lower()}")
            if row is None:
                return "FAILED", f"Activity import or power report failed for {arch} method {label}"
            direct = row["before"]["vcd"] == row["after"].get("vcd")
            coverage = label == "A" or row["direct_vcd_pin_fraction"] >= controls["min_direct_vcd_pin_fraction"]
            admitted = direct and coverage and (label == "A" or summary["unknown_bit_time_ps"] == 0)
            row |= {
                "architecture_id": arch, "physical_identity": phy["physical_identity"], "method": label,
                "window_ps": stop - start, "scoreboard_completed": count,
                "energy_j_per_completed_pair": row["power_w"]["total"] * (stop - start) * 1e-12 / count,
                "waveform_sha256": digest(waves / "window.vcd"), "raw_zero_delay_waveform_sha256": digest(gate_vcd),
                "eligibility": "ADMITTED" if admitted else "COVERAGE_OR_UNKNOWN_ACTIVITY_GAP",
                "unknown_bit_time_ps": summary["unknown_bit_time_ps"] if label == "B" else None,
                "primary_signal_match": matched,
            }
            results.append(row)
            write_json(out / "method-ab.json", results)
    return "COMPLETED", "Matched A/B zero-delay preflight completed; use row-level coverage and X/Z eligibility"
