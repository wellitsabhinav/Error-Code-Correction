#!/usr/bin/env python3
"""Execute one immutable Gate 04 final physical characterization run."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path("/var/lib/green-ecc-date2027-gate04-final")
POLICY = ROOT / "policy"
SNAPSHOT = POLICY / "repo_snapshot"
IMAGE = "openroad/orfs@sha256:f05cee3219a02f26289f02f00e11a3fc986ab51a482a0000a2da810cda219a6e"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_policy() -> None:
    for line in (POLICY / "frozen-bundle.sha256").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split(maxsplit=1)
        path = POLICY / relative.strip()
        if not path.is_file() or sha256(path) != expected:
            raise SystemExit(f"frozen Gate 04 policy hash mismatch: {relative}")


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def immutable_tree(root: Path) -> None:
    for path in (item for item in root.rglob("*") if item.is_file()):
        path.chmod(0o444)
    for path in sorted((item for item in root.rglob("*") if item.is_dir()), reverse=True):
        path.chmod(0o555)
    root.chmod(0o555)


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("run as root inside Ubuntu WSL2")
    if len(sys.argv) != 2:
        raise SystemExit("usage: run_characterization.py RUN_ID")
    verify_policy()
    contract = json.loads((SNAPSHOT / "scripts/gate04_final/contract_v1.json").read_text(encoding="utf-8"))
    run_id = sys.argv[1]
    matches = [item for item in contract["runs"] if item["run_id"] == run_id]
    if len(matches) != 1:
        raise SystemExit(f"run id is not in the frozen Gate 04 matrix: {run_id}")
    record = matches[0]
    run_root = ROOT / "runs" / run_id
    if run_root.exists():
        raise SystemExit(f"refusing to overwrite immutable Gate 04 run: {run_root}")
    run_root.mkdir()

    config = f"/gate04-repo/scripts/gate04_final/configs/{record['config']}"
    physical_script = (
        "set -euo pipefail; source /OpenROAD-flow-scripts/env.sh; "
        "export LEC_CHECK=0 NUM_CORES=1 WORK_HOME=/gate04-run CLOCK_PERIOD=10.0 "
        "GPL_RANDOM_SEED=11 GRT_SEED=11 OR_SEED=11; "
        "cd /OpenROAD-flow-scripts/flow; "
        f"make ABC_CLOCK_PERIOD_IN_PS=10000 DESIGN_CONFIG={config}"
    )
    docker_command = [
        "docker", "run", "--rm", "--platform", "linux/amd64",
        "--volume", f"{run_root}:/gate04-run",
        "--volume", f"{SNAPSHOT}:/gate04-repo:ro",
        "--entrypoint", "/bin/bash", IMAGE, "-lc", physical_script,
    ]
    write_json(
        run_root / "effective-run-environment.json",
        {
            **contract["flow"]["relevant_environment"],
            "DESIGN_CONFIG": config,
            "DESIGN_NAME": record["design_top"],
            "RUN_ID": run_id,
            "IMPLEMENTATION_ID": record["implementation_id"],
        },
    )
    (run_root / "physical-command.txt").write_text(" ".join(docker_command) + "\n", encoding="utf-8", newline="\n")

    start = utc_now()
    physical_status = 1
    physical_failure = ""
    with (run_root / "container.log").open("w", encoding="utf-8", newline="\n") as log:
        try:
            completed = subprocess.run(docker_command, stdout=log, stderr=subprocess.STDOUT, text=True, timeout=7200, check=False)
            physical_status = completed.returncode
        except subprocess.TimeoutExpired:
            physical_status = 124
            physical_failure = "official ORFS flow exceeded the frozen two-hour safety timeout"

    top = record["design_top"]
    results = run_root / f"results/sky130hd/{top}/base"
    logs = run_root / f"logs/sky130hd/{top}/base"
    required = [
        "1_synth.odb", "2_floorplan.odb", "3_place.odb", "4_cts.odb", "5_route.odb",
        "6_final.odb", "6_final.v", "6_final.sdc", "6_final.def", "6_final.gds", "6_final.spef",
    ]
    if physical_status == 0:
        missing = [name for name in required if not (results / name).is_file() or (results / name).stat().st_size == 0]
        if missing:
            physical_status, physical_failure = 91, f"missing required final artifacts: {missing}"
    for report in (logs / "6_report.json", logs / "5_1_grt.json", logs / "5_2_route.json"):
        if physical_status == 0 and (not report.is_file() or report.stat().st_size == 0):
            physical_status, physical_failure = 92, f"missing machine-readable report: {report.name}"
    if physical_status == 0:
        route = json.loads((logs / "5_2_route.json").read_text(encoding="utf-8"))
        if route.get("detailedroute__route__drc_errors") != 0 or route.get("detailedroute__flow__errors__count") != 0:
            physical_status, physical_failure = 93, "detailed routing did not finish with zero DRC and flow errors"
    if physical_status == 0:
        module_types = []
        for line in (results / "6_final.v").read_text(encoding="utf-8", errors="replace").splitlines():
            match = re.match(r"^\s*([^/\s][^\s]*)\s+(?:\\[^\s]+|[A-Za-z_][^\s(]*)\s*\($", line)
            if match:
                module_types.append(match.group(1).lstrip("\\"))
        generic = sorted({cell for cell in module_types if cell.startswith("$_") or cell.startswith("$")})
        if generic:
            physical_status, physical_failure = 94, f"generic cells remain in final netlist: {generic[:10]}"

    power_status = "NOT_RUN_PHYSICAL_FAILURE"
    power_failure = ""
    if physical_status == 0:
        power_root = run_root / "power"
        power_root.mkdir()
        family = record["power_family"]
        trace_specs = ",".join(
            f"{family}-{trace_class}|/gate04-policy/traces/{family}-10ns-{trace_class}.vcd.gz"
            for trace_class in contract["power"]["trace_classes"]
        )
        power_script = (
            "set -euo pipefail; source /OpenROAD-flow-scripts/env.sh; "
            "export LEC_CHECK=0 NUM_CORES=1 WORK_HOME=/gate04-run CLOCK_PERIOD=10.0 "
            "GPL_RANDOM_SEED=11 GRT_SEED=11 OR_SEED=11 "
            f"GATE04_POWER_DIR=/gate04-run/power GATE04_TRACE_SPECS='{trace_specs}'; "
            "cd /OpenROAD-flow-scripts/flow; "
            f"make ABC_CLOCK_PERIOD_IN_PS=10000 DESIGN_CONFIG={config} "
            "RUN_SCRIPT=/gate04-repo/scripts/gate04_final/power.tcl RUN_LOG_NAME_STEM=gate04_power run"
        )
        power_command = [
            "docker", "run", "--rm", "--platform", "linux/amd64",
            "--volume", f"{run_root}:/gate04-run",
            "--volume", f"{SNAPSHOT}:/gate04-repo:ro",
            "--volume", f"{POLICY}:/gate04-policy:ro",
            "--entrypoint", "/bin/bash", IMAGE, "-lc", power_script,
        ]
        (run_root / "power-command.txt").write_text(" ".join(power_command) + "\n", encoding="utf-8", newline="\n")
        with (run_root / "power-container.log").open("w", encoding="utf-8", newline="\n") as log:
            try:
                completed = subprocess.run(power_command, stdout=log, stderr=subprocess.STDOUT, text=True, timeout=600, check=False)
                if completed.returncode == 0:
                    power_status = "ACTIVITY_POWER_PASS_FULL_PRECISION_TEXT"
                else:
                    power_status, power_failure = "POWER_DEFERRED", f"activity power exited {completed.returncode}"
            except subprocess.TimeoutExpired:
                power_status, power_failure = "POWER_DEFERRED", "activity power exceeded the frozen ten-minute timeout"
        if power_status.startswith("ACTIVITY_POWER_PASS"):
            missing = [
                trace_class for trace_class in contract["power"]["trace_classes"]
                if not (power_root / f"{family}-{trace_class}.power.rpt").is_file()
            ]
            if missing:
                power_status, power_failure = "POWER_DEFERRED", f"missing 12-digit power reports: {missing}"

    metadata = {
        "schema_version": 1,
        "run_id": run_id,
        "implementation_id": record["implementation_id"],
        "design_top": top,
        "config": record["config"],
        "clock_period_ns": 10.0,
        "physical_seed": 11,
        "start_time_utc": start,
        "end_time_utc": utc_now(),
        "physical_exit_status": physical_status,
        "physical_failure_reason": physical_failure,
        "routing_complete": physical_status == 0,
        "power_status": power_status,
        "power_failure_reason": power_failure,
        "replacement_attempt": false,
    }
    write_json(run_root / "run-metadata.json", metadata)
    inventory = []
    for path in sorted(item for item in run_root.rglob("*") if item.is_file() and item.name != "raw-artifacts.sha256"):
        inventory.append(f"{sha256(path)}  {path.relative_to(run_root).as_posix()}")
    (run_root / "raw-artifacts.sha256").write_text("\n".join(inventory) + "\n", encoding="utf-8", newline="\n")
    immutable_tree(run_root)
    if physical_status != 0:
        print(f"GATE04_PHYSICAL_RUN_FAIL run={run_id} status={physical_status} reason={physical_failure}", file=sys.stderr)
        return physical_status
    print(f"GATE04_PHYSICAL_RUN_PASS run={run_id} power={power_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
