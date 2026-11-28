"""Execute the workload-conditioned, zero-delay routed-pair pilot."""

from collections import Counter
import gzip
import hashlib
import random
import shutil
import statistics
import sys
import time

from campaign_jobs import SIM_CACHE, command, guest_path, wsl_args
from physical import PHYSICAL
from run_campaign import GIB, REPO, digest, read_json, storage, write_json
from zero_delay import SIM_TOOLS, power, trim_vcd, wave_activity


def fixture(directory, regime, errors, config):
    sys.path.insert(0, str(REPO / "research/phase2/scripts"))
    try:
        from workloads import decode, encode, injection_mask, payloads
    finally:
        sys.path.pop(0)
    values = list(payloads(regime, len(errors), config["workload_seed"]))
    masks = {kind: random.Random(config["fault_seed"]) for kind in set(errors)}
    codes = [encode(value) for value in values]
    received = [word ^ injection_mask(kind, "hamming", i, masks[kind])
                for i, (kind, word) in enumerate(zip(errors, codes))]
    decoded = [decode(word) for word in received]
    flags = [4 * row["detected"] + 2 * row["corrected"] + row["uncorrectable"] for row in decoded]
    for name, numbers, width in (
        ("payload", values, 16), ("codewords", codes, 18), ("received", received, 18),
        ("expected_data", [row["data"] for row in decoded], 16), ("expected_flags", flags, 1),
    ):
        (directory / (name + ".hex")).write_text(
            "".join(f"{value:0{width}x}\n" for value in numbers), encoding="ascii", newline="\n"
        )
    return {
        "payload_regime": regime, "injection_counts": dict(Counter(errors)), "requested_operations": len(errors),
        "software_detected": sum(row["detected"] for row in decoded),
        "software_corrected": sum(row["corrected"] for row in decoded),
        "software_uncorrectable": sum(row["uncorrectable"] for row in decoded),
        "software_payload_mismatches": sum(row["data"] != value for row, value in zip(decoded, values)),
        "payload_mean_hamming_distance": statistics.mean((a ^ b).bit_count() for a, b in zip(values, values[1:])),
        "inputs_sha256": {path.name: digest(path) for path in sorted(directory.glob("*.hex"))},
    }


def compress_verified(raw):
    raw_hash = digest(raw)
    compressed = raw.with_suffix(raw.suffix + ".gz")
    with raw.open("rb") as source, gzip.GzipFile(filename=str(compressed), mode="wb", mtime=0) as target:
        shutil.copyfileobj(source, target)
    with gzip.open(compressed, "rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != raw_hash:
            raise ValueError("Waveform compression round trip differs")
    return raw_hash


def run(out, limit):
    root = out.parent.parent
    state = read_json(root / "campaign.json")
    if limit < 600:
        return "BLOCKED", "The workload pilot needs ten minutes of remaining campaign budget"
    config = read_json(PHYSICAL / "workload_contract.json")
    base_usage = storage(root)
    if min(base_usage["workspace_free_bytes"], base_usage["campaign_free_bytes"]) < 10 * GIB + config["max_additional_bytes"]:
        return "BLOCKED", "Insufficient reserve for the workload pilot"
    controls = read_json(PHYSICAL / "zero_delay_contract.json")
    physical_config = read_json(PHYSICAL / "contract.json")
    parent = state["jobs"]["A02"]["attempts"][-1]
    zero = state["jobs"]["B02-ZERO"]["attempts"][-1]
    physical = root / parent["directory"]
    library = root / zero["directory"] / "model/functional.v"
    if digest(library) != zero["artifact_sha256"]["model/functional.v"]:
        raise ValueError("Functional cell model does not match the qualified activity input")
    if not all(row["eligibility"] == "ADMITTED"
               for row in read_json(root / zero["directory"] / "method-ab.json")):
        return "BLOCKED", "Parent gate did not admit zero-delay activity"

    count = config["operations"]
    start, stop = controls["window_start_ps"], controls["window_end_ps"]
    cases = [(regime, regime, ["none"] * count) for regime in config["clean_payloads"]]
    cases += [(kind, "uniform", [kind] * count) for kind in config["fault_profiles_with_uniform_payloads"]]
    mix = [kind for kind, number in config["mixed_counts"].items() for _ in range(number)]
    if len(mix) != count:
        raise ValueError("Mixed operation count differs from the contract")
    random.Random(config["fault_seed"]).shuffle(mix)
    cases.append(("mixed", "uniform", mix))
    results = []
    seed = physical_config["placement_and_route_seed"]
    base = SIM_CACHE + "/usr"
    timer = time.monotonic()
    for arch, top in physical_config["physical_profiles"].items():
        netdir = physical / arch / f"results/sky130hd/{top}/seed{seed}"
        for file in ("6_final.v", "6_final.sdc", "6_final.spef", "6_final.odb"):
            path = netdir / file
            if digest(path) != parent["artifact_sha256"][path.relative_to(physical).as_posix()]:
                raise ValueError("Parent netlist, constraints, or parasitics changed")
        arch_dir = out / arch
        arch_dir.mkdir()
        binary = arch_dir / "gate.vvp"
        code, _ = command(arch_dir, "compile", wsl_args(
            base + "/bin/iverilog", "-B", base + "/lib/x86_64-linux-gnu/ivl", "-g2012", "-DP2P_CONDITIONED",
            "-s", "phase2_gate_tb", f"-DP2P_TOP={top}", "-DP2P_LATENCY=" + ("1" if arch.endswith("comb") else "3"),
            "-o", guest_path(binary), guest_path(PHYSICAL / "zero_delay_tb.sv"), guest_path(netdir / "6_final.v"),
            guest_path(library),
        ), seconds=40)
        if code != 0:
            return "FAILED", f"Conditioned scoreboard compile failed for {arch}"
        for label, regime, errors in cases:
            usage = storage(root)
            if (time.monotonic() - timer > limit - 120
                    or usage["campaign_file_bytes"] - base_usage["campaign_file_bytes"] > config["max_additional_bytes"]
                    or min(usage["workspace_free_bytes"], usage["campaign_free_bytes"]) < 10 * GIB + 512 * 2**20):
                return "FAILED", "Pilot stopped on its deadline or storage guard; completed cases retained"
            trial = arch_dir / label
            trial.mkdir()
            inputs = fixture(trial, regime, errors, config)
            write_json(trial / "vectors.json", inputs)
            result = {"architecture_id": arch, "workload": label, **inputs, "pJ": None, "status": "FAILED"}
            code, stdout = command(trial, "simulate", wsl_args(
                "bash", guest_path(SIM_TOOLS / "run_in.sh"), guest_path(trial),
                "timeout", "--kill-after=5s", "45s", "prlimit", f"--fsize={controls['single_waveform_bytes']}",
                base + "/bin/vvp", guest_path(binary),
            ), seconds=60)
            if code == 0 and f"SCOREBOARD_PASS completed={count}".encode() in stdout:
                gate = trial / "gate.vcd"
                window = trial / "window.vcd"
                trim_vcd(gate, window, start, stop)
                activity = wave_activity(window, stop - start)
                unknown = sum(s["durations_ps"]["x"] + s["durations_ps"]["z"] for s in activity["signals"])
                annotation = power(physical_config, trial, netdir, trial, "phase2_gate_tb/dut",
                                   f"greens-p2p-r1-workload-{arch}")
                result.update(unknown_bit_time_ps=unknown, annotation=annotation, completed=count)
                if (unknown == 0 and annotation and annotation["before"].get("vcd") == annotation["after"].get("vcd")
                        and annotation["direct_vcd_pin_fraction"] >= config["min_direct_vcd_pin_fraction"]):
                    result.update(status="ADMITTED", pJ=annotation["power_w"]["total"] * (stop - start) / count)
                result["full_waveform_sha256"] = compress_verified(gate)
                result["imported_waveform_sha256"] = compress_verified(window)
                write_json(trial / "compression-manifest.json", {
                    path.name: {"raw_sha256": raw_hash, "retained": path.name + ".gz",
                                "retained_sha256": digest(path.with_suffix(".vcd.gz"))}
                    for path, raw_hash in ((gate, result["full_waveform_sha256"]),
                                           (window, result["imported_waveform_sha256"]))
                })
                # These two files were generated in this attempt and their
                # compressed byte-for-byte round trips have just been verified.
                gate.unlink()
                window.unlink()
            results.append(result)
            write_json(out / "workload-results.json", results)
    prediction = []
    for arch in physical_config["physical_profiles"]:
        values = {r["workload"]: r["pJ"] for r in results if r["architecture_id"] == arch}
        constituents = {"none": "uniform", "single_data": "single_data", "single_check": "single_check", "double": "double"}
        if None in (values["mixed"], *(values[label] for label in constituents.values())):
            predicted = None
        else:
            predicted = sum(config["mixed_counts"][kind] * values[label] for kind, label in constituents.items()) / count
        prediction.append({"architecture_id": arch, "actual_pj": values["mixed"], "linear_prediction_pj": predicted,
                           "observed_minus_predicted_percent": 100 * (values["mixed"] / predicted - 1)
                           if predicted else None})
    write_json(out / "mixed-validation.json", prediction)
    return "COMPLETED", f"Conditioned workloads admitted {sum(row['status'] == 'ADMITTED' for row in results)}/{len(results)}"
