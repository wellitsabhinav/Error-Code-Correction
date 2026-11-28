"""Derive structural and ground-capacitance activity proxies from matched files."""

from collections import defaultdict
import re

from zero_delay import wave_activity


INSTANCE = re.compile(r"\b(sky130_fd_sc_hd__\w+)\s+(\S+)\s+\((.+?)\);", re.DOTALL)
PIN = re.compile(r"\.(\w+)\(([^)]+)\)")


def xor_pair(verilog):
    cells = []
    for cell, instance, ports in INSTANCE.findall(verilog.read_text(encoding="ascii")):
        if "__xor2_" not in cell and "__xnor2_" not in cell:
            continue
        pins = {port: signal.strip() for port, signal in PIN.findall(ports)}
        if {"A", "B", "X"} <= pins.keys():
            cells.append({"cell": cell, "instance": instance, "pins": pins})
    for source in cells:
        for sink in cells:
            if source["pins"]["X"] in {sink["pins"]["A"], sink["pins"]["B"]}:
                return {"first": source, "second": sink, "matching_net": source["pins"]["X"],
                        "xor_xnor_cell_count": len(cells)}
    return None


def ground_caps_pf(path):
    """Read only SPEF ground-capacitance rows. Coupling and pin terms stay excluded."""
    scale = None
    names = {}
    result = defaultdict(float)
    partition = ""
    net = None
    with path.open(encoding="ascii") as stream:
        for line in stream:
            tokens = line.split()
            if not tokens:
                continue
            keyword = tokens[0]
            if keyword == "*C_UNIT":
                scale = float(tokens[1]) * {"PF": 1.0, "FF": 1e-3}[tokens[2].upper()]
            elif keyword == "*NAME_MAP":
                partition = "names"
            elif keyword == "*D_NET":
                key = tokens[1]
                net = names.get(key, key).replace("\\", "")
                partition = "net"
            elif keyword == "*CAP":
                partition = "cap"
            elif keyword in {"*CONN", "*PORTS", "*RES", "*END"}:
                partition = ""
            elif partition == "names" and re.fullmatch(r"\*\d+", keyword):
                names[keyword] = " ".join(tokens[1:])
            elif partition == "cap" and len(tokens) == 3 and keyword.isdigit():
                result[net] += float(tokens[2])
    if scale is None or not result:
        raise ValueError("No usable ground capacitance inventory")
    return {name: value * scale for name, value in result.items()}


def activity_proxy(spef, vcd, end_ps, transactions, voltage):
    # Match VCD flat DUT aliases only. Use each physical net once, regardless
    # of how many hierarchical gate pins share its activity.
    caps = ground_caps_pf(spef)
    switched_pf = {}
    for signal in wave_activity(vcd, end_ps)["signals"]:
        for alias in signal["aliases"]:
            name = alias.removeprefix("phase2_gate_tb.dut.").replace("\\", "")
            name = re.sub(r"\[\d+:\d+\]$", f"[{signal['bit']}]", name)
            if name not in caps:
                continue
            if name in switched_pf:
                raise ValueError(f"Ambiguous activity alias for {name}")
            if signal["durations_ps"]["x"] == signal["durations_ps"]["z"] == 0:
                switched_pf[name] = caps[name] * signal["binary_transitions"]
    return {
        "ground_cap_total_pf": sum(caps.values()),
        "spef_nets_with_ground_cap": len(caps),
        "waveform_matched_known_nets": len(switched_pf),
        "matched_ground_cap_fraction": sum(caps[key] for key in switched_pf) / sum(caps.values()),
        "counted_rise_and_fall_proxy_pj_per_operation": 0.5 * voltage**2 * sum(switched_pf.values()) / transactions,
        "scope": "Matched ground SPEF capacitance only, B waveform, both binary directions",
    }
