#!/usr/bin/env python3
"""Cross-platform smoke test runner for compiled binaries and selector."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def _binary_path(name: str) -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    return REPO / f"{name}{suffix}"


def _run_binary(name: str) -> None:
    binary = _binary_path(name)
    subprocess.run(
        [str(binary), "--smoke"],
        cwd=REPO,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> int:
    for program in ["BCHvsHamming", "Hamming32bit1Gb", "Hamming64bit128Gb", "SATDemo"]:
        print(f"Testing {program}")
        _run_binary(program)

    print("Testing ecc_selector.py")
    subprocess.run(
        [sys.executable, "ecc_selector.py", "1e-6", "2", "0.6", "1e-15", "1", "--sustainability"],
        cwd=REPO,
        check=True,
        stdout=subprocess.DEVNULL,
    )

    print("All smoke tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
