#!/usr/bin/env python3
"""Validate one complete Gate 04 physical run without collapsing duplicate JSON keys."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ordered_pairs(path: Path) -> list[tuple[str, object]]:
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=lambda pairs: pairs)
    if not isinstance(value, list):
        raise ValueError(f"expected JSON object at {path}")
    return value


def numeric_occurrences(pairs: list[tuple[str, object]], key: str) -> list[float]:
    return [float(value) for name, value in pairs if name == key and isinstance(value, (int, float))]


def power_has_positive_total(value: object) -> bool:
    if isinstance(value, list):
        # object_pairs_hook objects are lists of (key, value) tuples.
        for item in value:
            if isinstance(item, tuple) and len(item) == 2:
                key, child = item
                if str(key).lower() in {"total", "total_power", "power_total"} and isinstance(child, (int, float)) and child > 0:
                    return True
                if power_has_positive_total(child):
                    return True
            elif power_has_positive_total(item):
                return True
    elif isinstance(value, dict):
        return any(power_has_positive_total(child) for child in value.values())
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--implementation-id", required=True)
    parser.add_argument("--top", required=True)
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--clock-ns", type=float, required=True)
    args = parser.parse_args()
    run_root = args.run_root.resolve()
    matches = list((run_root / "results/sky130hd" / args.top).glob("base"))
    if len(matches) != 1:
        raise SystemExit("RUN VALIDATION FAIL: results directory is not unique")
    results = matches[0]
    logs = run_root / "logs/sky130hd" / args.top / "base"
    reports = run_root / "reports/sky130hd" / args.top / "base"
    checks: list[dict[str, object]] = []

    def check(condition: bool, name: str, detail: object = None) -> None:
        checks.append({"check": name, "status": "PASS" if condition else "FAIL", "detail": detail})
        if not condition:
            raise SystemExit(f"RUN VALIDATION FAIL: {name}: {detail}")

    required_artifacts = [
        "1_synth.odb", "2_floorplan.odb", "3_place.odb", "4_cts.odb", "5_route.odb",
        "6_final.odb", "6_final.v", "6_final.sdc", "6_final.def", "6_final.gds", "6_final.spef",
    ]
    check(all((results / name).is_file() and (results / name).stat().st_size > 0 for name in required_artifacts), "all full-flow physical artifacts exist")
    required_logs = ["1_2_yosys.log", "2_1_floorplan.log", "3_3_place_gp.log", "4_1_cts.log", "5_1_grt.log", "5_2_route.log", "6_report.log", "6_report.json"]
    check(all((logs / name).is_file() and (logs / name).stat().st_size > 0 for name in required_logs), "all mandatory stage logs exist")

    all_pairs: list[tuple[str, object]] = []
    occurrence_records: list[dict[str, object]] = []
    for path in sorted(logs.glob("*.json")):
        pairs = ordered_pairs(path)
        all_pairs.extend(pairs)
        seen: dict[str, int] = {}
        for ordinal, (key, value) in enumerate(pairs):
            occurrence = seen.get(key, 0)
            seen[key] = occurrence + 1
            if isinstance(value, (int, float, str, bool)) or value is None:
                occurrence_records.append(
                    {
                        "source": path.relative_to(run_root).as_posix(),
                        "pair_ordinal": ordinal,
                        "key": key,
                        "key_occurrence": occurrence,
                        "value": value,
                    }
                )
    (run_root / "metric-occurrences.json").write_text(json.dumps(occurrence_records, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    for key in (
        "finish__design__die__area", "finish__design__instance__area",
        "finish__design__instance__count", "finish__design__instance__count__class:sequential_cell",
        "finish__timing__setup__ws", "finish__timing__fmax",
    ):
        check(bool(numeric_occurrences(all_pairs, key)), f"required physical metric present: {key}")
    check(all(value == 0 for value in numeric_occurrences(all_pairs, "finish__flow__errors__count")), "final flow error count is zero")
    check(all(value == 0 for value in numeric_occurrences(all_pairs, "detailedroute__route__drc_errors")), "final detailed-route DRC error count is zero")
    check(all(value == 0 for value in numeric_occurrences(all_pairs, "detailedroute__antenna__violating__nets")), "final antenna violating-net count is zero")
    check(all(value == 0 for value in numeric_occurrences(all_pairs, "detailedroute__antenna__violating__pins")), "final antenna violating-pin count is zero")
    drc_report = reports / "5_route_drc.rpt"
    check(drc_report.is_file() and not drc_report.read_text(encoding="utf-8", errors="replace").strip(), "detailed-route DRC report is empty")

    setup_values = numeric_occurrences(all_pairs, "finish__timing__setup__ws")
    timing_met = bool(setup_values and setup_values[-1] >= 0)
    if args.clock_ns == 10.0:
        check(timing_met, "mandatory 10 ns setup timing met", setup_values[-1] if setup_values else None)
    else:
        checks.append({"check": "5 ns setup timing", "status": "PASS" if timing_met else "DATA", "detail": setup_values[-1] if setup_values else None})

    netlist = (results / "6_final.v").read_text(encoding="utf-8", errors="replace")
    modules = re.findall(r"(?m)^module\s+([A-Za-z_][A-Za-z0-9_$]*)", netlist)
    check(modules == [args.top], "final netlist contains only the expected top module", modules)
    check(not re.search(r"\$_[A-Z]|\\\$[A-Za-z_]", netlist), "no generic Yosys cell remains")
    check(not re.search(r"sky130_fd_sc_hd__dlxt|sky130_fd_sc_hd__dlrb|sky130_fd_sc_hd__dlrt", netlist), "no unintended latch cell remains")
    header = netlist[: netlist.find(");") + 2]
    check(not re.search(r"fault|inject|test", header, flags=re.IGNORECASE), "no fault/test port synthesized")

    sequential_values = numeric_occurrences(all_pairs, "finish__design__instance__count__class:sequential_cell")
    sequential_cells = int(sequential_values[-1])
    if args.implementation_id.startswith("boundary-reference-"):
        # Pure pass mappings may legally share identical output registers.
        common_boundary_floor = 125 + 2 * args.n
    else:
        common_boundary_floor = 128 + 3 * args.n
    check(sequential_cells >= common_boundary_floor, "common registered boundary survived", {"observed": sequential_cells, "floor": common_boundary_floor})
    if args.implementation_id == "secded-rtl-pipelined-72-64-v1":
        check(sequential_cells >= common_boundary_floor + 300, "internal same-code pipeline registers survived", {"observed": sequential_cells, "floor": common_boundary_floor + 300})

    for name in ("mapped-equivalence.log", "postroute-equivalence.log"):
        path = run_root / name
        check(path.is_file() and "Equivalence successfully proven" in path.read_text(encoding="utf-8", errors="replace"), f"exact {name.removesuffix('.log')} passed")

    power_files = sorted((run_root / "power").glob("*.power.json"))
    expected_power_files = 6 if args.implementation_id == "boundary-reference-72-64-v1" else 3
    check(len(power_files) == expected_power_files, "all activity power conditions exist", {"observed": len(power_files), "expected": expected_power_files})
    annotation_files = sorted((run_root / "power").glob("*.annotation.rpt"))
    check(len(annotation_files) == expected_power_files, "all activity annotation reports exist")
    direct_floor = args.n + 67
    coverages: list[dict[str, object]] = []
    for path in annotation_files:
        text = path.read_text(encoding="utf-8", errors="replace")
        vcd_match = re.search(r"(?m)^vcd\s+(\d+)\s*$", text)
        unannotated_match = re.search(r"(?m)^unannotated\s+(\d+)\s*$", text)
        vcd_count = int(vcd_match.group(1)) if vcd_match else -1
        unannotated_count = int(unannotated_match.group(1)) if unannotated_match else -1
        check(vcd_count >= direct_floor and unannotated_count >= 0, f"direct VCD coverage recorded: {path.name}", {"vcd": vcd_count, "unannotated": unannotated_count, "input_pin_floor": direct_floor})
        coverages.append({"trace": path.stem.removesuffix(".annotation"), "vcd": vcd_count, "unannotated": unannotated_count})
    for path in power_files:
        parsed = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=lambda pairs: pairs)
        check(power_has_positive_total(parsed), f"positive post-route power total: {path.name}")

    result = {
        "schema_version": 1,
        "status": "PASS",
        "implementation_id": args.implementation_id,
        "design_top": args.top,
        "clock_period_ns": args.clock_ns,
        "timing_met": timing_met,
        "sequential_cells": sequential_cells,
        "direct_annotation_coverage": coverages,
        "checks": checks,
        "validated_artifacts": [
            {"path": (results / name).relative_to(run_root).as_posix(), "sha256": sha256(results / name)}
            for name in required_artifacts
        ],
    }
    (run_root / "run-validation.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"GATE04_RUN_VALIDATION_PASS checks={len(checks)} sequential_cells={sequential_cells}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
