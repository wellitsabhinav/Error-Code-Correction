#!/usr/bin/env python3
"""Run the frozen four-design Gate 04 matrix exactly once."""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
from pathlib import Path


ROOT = Path("/var/lib/green-ecc-date2027-gate04-final")
SNAPSHOT = ROOT / "policy/repo_snapshot"


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("run as root inside Ubuntu WSL2")
    runs_root = ROOT / "runs"
    if any(runs_root.iterdir()):
        raise SystemExit("Gate 04 run namespace is not empty; refusing duplicate or replacement execution")
    contract = json.loads((SNAPSHOT / "scripts/gate04_final/contract_v1.json").read_text(encoding="utf-8"))
    started = now()
    outcomes = []
    for record in contract["runs"]:
        completed = subprocess.run(
            ["python3", str(SNAPSHOT / "scripts/gate04_final/run_characterization.py"), record["run_id"]],
            check=False,
        )
        outcomes.append(
            {
                "run_id": record["run_id"],
                "implementation_id": record["implementation_id"],
                "process_exit_status": completed.returncode,
            }
        )
    payload = {
        "schema_version": 1,
        "started_at_utc": started,
        "completed_at_utc": now(),
        "planned_run_count": 4,
        "executed_run_count": len(outcomes),
        "replacement_attempt_count": 0,
        "outcomes": outcomes,
    }
    (ROOT / "MATRIX_EXECUTION.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    success = len(outcomes) == 4 and all(item["process_exit_status"] == 0 for item in outcomes)
    print("GATE04_MATRIX_COMPLETE" if success else "GATE04_MATRIX_COMPLETE_WITH_FAILURES")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
