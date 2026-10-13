#!/usr/bin/env python3
"""Run and archive technology-independent SafeForge RTL validation.

The runner is intentionally cross-platform.  It records the host, exact tool
versions, commands, full logs, and exit codes.  No physical PPA is inferred.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from codeforge.ambiguity import build_support
from codeforge.artifacts import render_systemverilog
from codeforge.faults import load_fault_distribution
from codeforge.hardware import structural_cost
from codeforge.robust import code_with_actions, decoder_actions, nominal_ml_actions


OUT = ROOT / "reports" / "safeforge_hardware_validation"
LOGS = OUT / "logs"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _tool(name: str, *windows_names: str) -> Path | None:
    if os.name == "nt":
        configured = os.environ.get("GREENS_TOOL_BIN")
        base = Path(configured) if configured else None
        for candidate in windows_names or (name + ".exe",):
            path = base / candidate if base else None
            if path and path.exists():
                return path
    found = shutil.which(name)
    if found:
        return Path(found)
    return None


def _portable_iverilog(iverilog: Path, vvp: Path, temporary: Path) -> tuple[Path, Path]:
    """Work around the MSYS Icarus helper failing when its prefix contains spaces."""

    if os.name != "nt" or " " not in str(iverilog):
        return iverilog, vvp
    bin_dir = temporary / "iverilog" / "bin"
    lib_dir = temporary / "iverilog" / "lib" / "ivl"
    bin_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(iverilog, bin_dir / iverilog.name)
    shutil.copy2(vvp, bin_dir / vvp.name)
    source_lib = iverilog.parent.parent / "lib" / "ivl"
    shutil.copytree(source_lib, lib_dir, dirs_exist_ok=True)
    return bin_dir / iverilog.name, bin_dir / vvp.name


def _portable_verilator(verilator: Path, temporary: Path) -> tuple[Path, Path | None]:
    """Give the native Windows binary a space-free VERILATOR_ROOT."""

    if os.name != "nt" or " " not in str(verilator):
        return verilator, None
    bin_dir = temporary / "verilator" / "bin"
    share_dir = temporary / "verilator" / "share" / "verilator"
    bin_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(verilator, bin_dir / verilator.name)
    source_share = verilator.parent.parent / "share" / "verilator"
    shutil.copytree(source_share, share_dir, dirs_exist_ok=True)
    return bin_dir / verilator.name, share_dir


def _quote(command: Iterable[object]) -> str:
    return " ".join(shlex.quote(str(item)) for item in command)


def _run(
    label: str,
    command: list[str],
    *,
    env: dict[str, str],
    cwd: Path = ROOT,
) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    before = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    duration = time.perf_counter() - before
    log_path = LOGS / f"{label}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        f"started_utc: {started.isoformat()}\n"
        f"command: {_quote(command)}\n"
        f"exit_code: {completed.returncode}\n"
        f"duration_seconds: {duration:.6f}\n\n"
        f"{completed.stdout}",
        encoding="utf-8",
    )
    return {
        "label": label,
        "command": _quote(command),
        "exit_code": completed.returncode,
        "status": "passed" if completed.returncode == 0 else "failed",
        "duration_seconds": duration,
        "log": log_path.relative_to(OUT).as_posix(),
        "log_sha256": hashlib.sha256(log_path.read_bytes()).hexdigest(),
    }


def _version(label: str, command: list[str], *, env: dict[str, str]) -> tuple[dict[str, Any], str]:
    result = _run("version_" + label, command, env=env)
    text = (OUT / result["log"]).read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines()[5:] if line.strip()]
    result["version_text"] = lines[0] if lines else "unavailable"
    return result, result["version_text"]


ASIC_SOURCES = [
    "asic/include/ecc_pkg.sv",
    "asic/rtl/common/ecc_bitflip_corrector.sv",
    "asic/rtl/common/green_ecc_select_mux.sv",
    "asic/rtl/common/green_ecc_mode_controller.sv",
    "asic/rtl/common/green_ecc_transition_controller.sv",
    "asic/rtl/secded/secded_codec.sv",
    "asic/rtl/secdaec/secdaec_codec.sv",
    "asic/rtl/taec/taec_codec.sv",
    "asic/rtl/bch/bch_codec.sv",
    "asic/rtl/polar/polar_pkg.sv",
    "asic/rtl/polar/polar_codec.sv",
    "asic/rtl/sram/sram_wrappers.sv",
    "asic/rtl/common/ecc_entries.sv",
]


def _compile_and_run(
    label: str,
    sources: list[str],
    *,
    iverilog: Path,
    vvp: Path,
    build_dir: Path,
    env: dict[str, str],
) -> list[dict[str, Any]]:
    executable = build_dir / (label + ".vvp")
    compile_result = _run(
        label + "_compile",
        [str(iverilog), "-g2012", "-Iasic/include", "-o", str(executable), *sources],
        env=env,
    )
    results = [compile_result]
    if compile_result["exit_code"] == 0:
        results.append(_run(label + "_run", [str(vvp), str(executable)], env=env))
    return results


def _render_nominal_same_matrix(directory: Path) -> tuple[list[str], dict[str, Any]]:
    code = json.loads((ROOT / "reports/safeforge_64_study/code.json").read_text(encoding="utf-8"))
    nominal = load_fault_distribution(
        "configs/fault_distributions/benchmarks/spatial_hot_spots.json", repo_root=ROOT
    )
    expansions = [
        load_fault_distribution(name, repo_root=ROOT)
        for name in (
            "configs/fault_distributions/benchmarks/distribution_shift.json",
            "configs/fault_distributions/benchmarks/voltage_sensitive.json",
            "configs/fault_distributions/benchmarks/mixed_sbu_dbu_mbu.json",
        )
    ]
    support = build_support(nominal, expansions)
    actions = nominal_ml_actions(code, support)
    nominal_code = code_with_actions(code, actions, code_id_suffix="-nominal-policy")
    files = render_systemverilog(nominal_code)
    directory.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (directory / name).write_text(content, encoding="utf-8")
    sv_files = [str(path) for path in sorted(directory.glob("*.sv")) if not path.name.startswith("tb_")]
    return sv_files, {
        "code": nominal_code,
        "actions": actions,
        "top": str(nominal_code["code_id"]).replace("-", "_").lower() + "_decoder",
    }


def _yosys_metrics(text: str) -> dict[str, Any]:
    cells = re.findall(r"Number of cells:\s+(\d+)", text)
    depths = re.findall(r"Longest topological path .*\(length=(\d+)\)", text)
    abc = {
        gate.lower(): int(count)
        for gate, count in re.findall(r"ABC RESULTS:\s+([A-Z0-9_]+) cells:\s+(\d+)", text)
    }
    return {
        "generic_cell_count": int(cells[-1]) if cells else None,
        "longest_topological_path_cells": int(depths[-1]) if depths else None,
        "abc_generic_gate_counts": abc,
    }


def _synthesize(
    label: str,
    sources: list[str],
    top: str,
    *,
    yosys: Path,
    env: dict[str, str],
    workdir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_paths = [Path(item).resolve().as_posix() for item in sources]
    program = (
        "read_verilog -sv "
        + " ".join(source_paths)
        + f"; hierarchy -check -top {top}; proc; flatten; opt; techmap; opt; "
        + "abc -g simple; clean; check -assert; stat; ltp"
    )
    result = _run(label, [str(yosys), "-p", program], env=env, cwd=workdir)
    log = (OUT / result["log"]).read_text(encoding="utf-8")
    return result, _yosys_metrics(log)


def _policy_structure(code: dict[str, Any], actions: dict[int, int]) -> dict[str, Any]:
    cost = structural_cost(code["H"], code["G"], actions, max_xor_fanin=2)
    entries = len(actions)
    return {
        "xor_logic": {
            "matrix_xor_gates": cost["matrix_xor_gates"],
            "syndrome_naive_xor_gates": cost["syndrome"]["naive_xor_gates"],
            "syndrome_max_balanced_depth": cost["syndrome"]["max_balanced_depth"],
        },
        "correction_table": {
            "correction_entries": entries,
            "correction_mask_ones": cost["decoder"]["correction_mask_ones"],
            "syndrome_compare_literals": cost["decoder"]["syndrome_compare_literals"],
        },
        "configuration_storage": {
            "runtime_configuration_bits": 0,
            "reason": "policy is compiled into fixed combinational case logic",
            "dense_logical_table_bits_if_stored": 256 * 73,
            "sparse_payload_bits_if_stored_without_overhead": entries * 80,
        },
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    iverilog = _tool("iverilog", "iverilog.exe")
    vvp = _tool("vvp", "vvp.exe")
    verilator = _tool("verilator", "verilator_bin.exe", "verilator.exe")
    yosys = _tool("yosys", "yosys.exe")
    missing = [name for name, value in (("iverilog", iverilog), ("vvp", vvp), ("verilator", verilator), ("yosys", yosys)) if value is None]
    if missing:
        raise SystemExit("missing required RTL tools: " + ", ".join(missing))

    env = dict(os.environ)
    env["PATH"] = str(iverilog.parent) + os.pathsep + env.get("PATH", "")
    results: list[dict[str, Any]] = []
    versions: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="safeforge-hw-") as temporary_name:
        temporary = Path(temporary_name)
        iverilog, vvp = _portable_iverilog(iverilog, vvp, temporary)
        verilator, verilator_root = _portable_verilator(verilator, temporary)
        if verilator_root is not None:
            env["VERILATOR_ROOT"] = str(verilator_root)
        build = temporary / "build"
        build.mkdir()
        for label, command in (
            ("iverilog", [str(iverilog), "-V"]),
            ("vvp", [str(vvp), "-V"]),
            ("verilator", [str(verilator), "--version"]),
            ("yosys", [str(yosys), "-V"]),
        ):
            result, version = _version(label, command, env=env)
            results.append(result)
            versions[label] = version

        for tb in (
            "tb_secded",
            "tb_secdaec",
            "tb_taec",
            "tb_bch",
            "tb_polar",
            "tb_sram_wrappers",
            "tb_green_ecc_selection",
            "tb_green_ecc_transition_controller",
        ):
            results.extend(
                _compile_and_run(
                    "asic_" + tb,
                    [*ASIC_SOURCES, f"asic/tb/{tb}.sv"],
                    iverilog=iverilog,
                    vvp=vvp,
                    build_dir=build,
                    env=env,
                )
            )

        safe_sets = {
            "safeforge_small_exhaustive": sorted(
                path.relative_to(ROOT).as_posix()
                for path in (ROOT / "reports/safe_decoder/rtl").glob("*.sv")
            ),
            "safeforge_72_modeled_campaign": sorted(
                path.relative_to(ROOT).as_posix()
                for path in (ROOT / "reports/safeforge_64_decoder/rtl").glob("*.sv")
            ),
        }
        for label, sources in safe_sets.items():
            results.extend(
                _compile_and_run(
                    label,
                    sources,
                    iverilog=iverilog,
                    vvp=vvp,
                    build_dir=build,
                    env=env,
                )
            )
            results.append(
                _run(
                    "verilator_" + label,
                    [str(verilator), "--lint-only", "--timing", "-Wall", "-Wno-fatal", *sources],
                    env=env,
                )
            )

        nominal_files, nominal = _render_nominal_same_matrix(temporary / "nominal")
        robust_files = [
            str(ROOT / "reports/safeforge_64_decoder/rtl/safeforge_robust_72_64_mapping_v1_safe_syndrome.sv"),
            str(ROOT / "reports/safeforge_64_decoder/rtl/safeforge_robust_72_64_mapping_v1_safe_safe_decoder.sv"),
        ]
        nominal_yosys, nominal_metrics = _synthesize(
            "yosys_nominal_same_matrix",
            nominal_files,
            nominal["top"],
            yosys=yosys,
            env=env,
            workdir=build,
        )
        robust_yosys, robust_metrics = _synthesize(
            "yosys_robust_same_matrix",
            robust_files,
            "safeforge_robust_72_64_mapping_v1_safe_safe_decoder",
            yosys=yosys,
            env=env,
            workdir=build,
        )
        results.extend((nominal_yosys, robust_yosys))

        robust_code = json.loads(
            (ROOT / "reports/safeforge_64_study/code.json").read_text(encoding="utf-8")
        )
        robust_actions = decoder_actions(robust_code)
        comparison = {
            "schema_version": 1,
            "comparison_control": "same parity-check matrix and physical mapping; decoder policy and robust envelope controls differ",
            "technology_scope": "generic structural synthesis only",
            "characterized_library": None,
            "physical_area_delay_energy_leakage_claim": None,
            "nominal_policy": {
                **_policy_structure(nominal["code"], nominal["actions"]),
                "due_logic": "nonzero unknown syndrome drives detected_uncorrectable",
                "abstain_bits": 0,
                "envelope_control_bits": 0,
                "generic_synthesis": nominal_metrics,
            },
            "robust_policy": {
                **_policy_structure(robust_code, robust_actions),
                "due_logic": "nonzero unapproved syndrome or invalid envelope drives abstain/DUE",
                "abstain_bits": 1,
                "envelope_control_bits": 2,
                "certificate_metadata_output_bits": 128,
                "generic_synthesis": robust_metrics,
            },
        }
        _write_json(OUT / "nominal_robust_structural_comparison.json", comparison)

    tb64 = (ROOT / "reports/safeforge_64_decoder/rtl/tb_safeforge_robust_72_64_mapping_v1_safe_safe.sv").read_text(encoding="utf-8")
    tb8 = (ROOT / "reports/safe_decoder/rtl/tb_forge_hotspot_8_4_v1_safe_safe.sv").read_text(encoding="utf-8")
    failed = [item["label"] for item in results if item["exit_code"] != 0]
    summary = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "host": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "tools": versions,
        "campaigns": {
            "small_exhaustive": {
                "data_words": 16,
                "modeled_error_vectors": tb8.count("received = codeword ^") - 1,
                "cross_product_checks": 16 * (tb8.count("received = codeword ^") - 1),
            },
            "72bit_modeled_errors": {
                "data_representatives": len(re.findall(r"d = \d+; data", tb64)),
                "modeled_error_vectors_per_representative": (tb64.count("received = codeword ^") - 1) // 4,
                "cross_product_checks": tb64.count("received = codeword ^") - 1,
            },
        },
        "generic_asic_regression_semantics": {
            "tb_taec": "negative collision is expected and archived, not a TAEC correction claim",
            "tb_bch": "negative distance/collision is expected and archived, not a verified BCH correction claim",
        },
        "results": results,
        "overall_status": "passed" if not failed else "failed",
        "failed_checks": failed,
        "interpretation": "Actual host execution; technology-independent RTL and generic synthesis only.",
    }
    _write_json(OUT / "validation_summary.json", summary)
    manifest_files = {
        path.relative_to(OUT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(OUT.rglob("*"))
        if path.is_file() and path.name != "result_manifest.json"
    }
    _write_json(
        OUT / "result_manifest.json",
        {
            "manifest_version": 1,
            "files": manifest_files,
            "reproduction_command": "python scripts/run_safeforge_hardware_validation.py",
            "overall_status": summary["overall_status"],
        },
    )
    print(json.dumps({"overall_status": summary["overall_status"], "failed_checks": failed}, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
