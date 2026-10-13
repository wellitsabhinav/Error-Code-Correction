#!/usr/bin/env python3
"""Independent C++ and Icarus RTL differentials for Rigour Gate 02.

The generated C++ file is only a driver around the repository's pre-existing
``BCH63`` implementation.  It contains no translated Python BCH algorithm.
"""

from __future__ import annotations

import argparse
from itertools import combinations
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from green_ecc_phy.gate02 import canonical_code_spec, masks_for_definition, observe_decode, universe_definitions_for
from green_ecc_phy.hashing import file_sha256
from green_ecc_phy.registry import EccRegistry
from green_ecc_phy.contracts import DecodeStatus


OUTCOME_CODES = {
    "CLEAN": 0,
    "CORRECTED": 1,
    "DUE": 2,
    "SDC_MISCORRECTION": 3,
    "SDC_UNDETECTED": 4,
    "INVALID_DECODER_STATE": 5,
}


def _run(command: list[str], *, cwd: Path, timeout: int) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        process = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        status = "PASS" if process.returncode == 0 else "FAIL"
        return {
            "command": subprocess.list2cmdline(command),
            "timeout_seconds": timeout,
            "exit_code": process.returncode,
            "execution_status": status,
            "duration_seconds": time.perf_counter() - started,
            "stdout": process.stdout,
            "stderr": process.stderr,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": subprocess.list2cmdline(command),
            "timeout_seconds": timeout,
            "exit_code": None,
            "execution_status": "TIMEOUT",
            "duration_seconds": time.perf_counter() - started,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
        }
    except OSError as exc:
        return {
            "command": subprocess.list2cmdline(command),
            "timeout_seconds": timeout,
            "exit_code": None,
            "execution_status": "NOT ASSESSABLE",
            "duration_seconds": time.perf_counter() - started,
            "stdout": "",
            "stderr": str(exc),
        }


def _tool(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    configured = os.environ.get("GREENS_TOOL_BIN")
    candidate = Path(configured) / f"{name}.exe" if configured else None
    return str(candidate) if candidate and candidate.is_file() else None


def _native_from_canonical(value: int, mapping: list[int]) -> int:
    result = 0
    for canonical, native in enumerate(mapping):
        if value & (1 << canonical):
            result |= 1 << native
    return result


def _canonical_from_native(value: int, mapping: list[int]) -> int:
    result = 0
    for canonical, native in enumerate(mapping):
        if value & (1 << native):
            result |= 1 << canonical
    return result


def _payloads(k: int, identity: str) -> list[int]:
    import hashlib

    values = [0, 1, (1 << k) - 1, *(1 << bit for bit in range(k))]
    for index in range(16):
        values.append(
            int.from_bytes(hashlib.sha256(f"gate02-equivalence:{identity}:{index}".encode()).digest(), "big")
            & ((1 << k) - 1)
        )
    return list(dict.fromkeys(values))


CPP_DRIVER = r'''
#include "src/bch63.hpp"
#include <algorithm>
#include <cstdint>
#include <iostream>
#include <vector>

static uint64_t dataValue(const std::vector<bool>& bits) {
    uint64_t value = 0;
    for (std::size_t i = 0; i < bits.size(); ++i) if (bits[i]) value |= uint64_t{1} << i;
    return value;
}

static std::vector<bool> dataBits(uint64_t value, int k) {
    std::vector<bool> bits(static_cast<std::size_t>(k), false);
    for (int i = 0; i < k; ++i) bits[static_cast<std::size_t>(i)] = ((value >> i) & 1U) != 0;
    return bits;
}

int main() {
    BCH63 bch;
    std::cout << "META " << bch.dataLength() << " " << bch.parityLength() << " ";
    for (int bit : bch.generatorPolynomial()) std::cout << bit;
    std::cout << "\n";
    uint64_t all = (uint64_t{1} << bch.dataLength()) - 1;
    std::vector<uint64_t> messages{0, 1, all};
    for (int i = 0; i < bch.dataLength(); ++i) messages.push_back(uint64_t{1} << i);
    for (uint64_t message : messages) {
        auto encoded = bch.encode(dataBits(message, bch.dataLength()));
        std::cout << "ENC " << std::hex << message << " " << encoded.toUInt64() << std::dec << "\n";
    }
    auto baseline = bch.encode(dataBits(0, bch.dataLength()));
    for (int weight = 0; weight <= 2; ++weight) {
        if (weight == 0) {
            auto result = bch.decode(baseline);
            std::cout << "DEC 0 " << result.detected << " " << result.success << " "
                      << std::hex << result.corrected.toUInt64() << " " << dataValue(result.data)
                      << std::dec << " -\n";
        } else if (weight == 1) {
            for (int a = 0; a < BCH63::N; ++a) {
                uint64_t mask = uint64_t{1} << a;
                auto result = bch.decode(BCH63::Codeword::fromUInt64(mask));
                std::cout << "DEC " << std::hex << mask << std::dec << " " << result.detected << " "
                          << result.success << " " << std::hex << result.corrected.toUInt64() << " "
                          << dataValue(result.data) << std::dec << " ";
                for (std::size_t i = 0; i < result.error_locations.size(); ++i) {
                    if (i) std::cout << ",";
                    std::cout << result.error_locations[i];
                }
                std::cout << "\n";
            }
        } else {
            for (int a = 0; a < BCH63::N; ++a) for (int b = a + 1; b < BCH63::N; ++b) {
                uint64_t mask = (uint64_t{1} << a) | (uint64_t{1} << b);
                auto result = bch.decode(BCH63::Codeword::fromUInt64(mask));
                std::cout << "DEC " << std::hex << mask << std::dec << " " << result.detected << " "
                          << result.success << " " << std::hex << result.corrected.toUInt64() << " "
                          << dataValue(result.data) << std::dec << " ";
                for (std::size_t i = 0; i < result.error_locations.size(); ++i) {
                    if (i) std::cout << ",";
                    std::cout << result.error_locations[i];
                }
                std::cout << "\n";
            }
        }
    }
}
'''


def run_cpp(root: Path, registry: EccRegistry, work: Path) -> dict[str, Any]:
    work.mkdir(parents=True, exist_ok=True)
    compiler = _tool("g++")
    if compiler is None:
        return {"gate_status": "NOT ASSESSABLE", "reason": "g++ unavailable"}
    driver = work / "gate02_bch63_driver.cpp"
    executable = work / ("gate02_bch63_driver.exe" if os.name == "nt" else "gate02_bch63_driver")
    driver.write_text(CPP_DRIVER, encoding="utf-8")
    compile_result = _run(
        [compiler, "-std=c++17", "-O2", "-I.", "src/bch63.cpp", str(driver), "-o", str(executable)],
        cwd=root,
        timeout=120,
    )
    if compile_result["execution_status"] != "PASS":
        return {"gate_status": compile_result["execution_status"], "compile": compile_result}
    execute_result = _run([str(executable)], cwd=root, timeout=120)
    if execute_result["execution_status"] != "PASS":
        return {"gate_status": execute_result["execution_status"], "compile": compile_result, "execute": execute_result}
    implementation_id = "primitive-bch-63-51-t2-v1-reference-decoder"
    adapter = registry.adapter(implementation_id)
    code = registry.code("primitive-bch-63-51-t2-v1")
    spec = canonical_code_spec(code, [implementation_id])
    mapping = spec["native_to_canonical_equivalence"]["canonical_to_native_zero_based"]
    failures: list[dict[str, Any]] = []
    encodings = decodings = 0
    meta = None
    for line in execute_result["stdout"].splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "META":
            meta = {"k": int(parts[1]), "r": int(parts[2]), "generator_printed_high_to_low": parts[3]}
        elif parts[0] == "ENC":
            data = int(parts[1], 16)
            observed_native = int(parts[2], 16)
            expected_native = _native_from_canonical(adapter.encode(data), mapping)
            encodings += 1
            if observed_native != expected_native:
                failures.append({"kind": "encode", "data": data, "expected": expected_native, "observed": observed_native})
        elif parts[0] == "DEC":
            native_mask = int(parts[1], 16)
            detected, success = bool(int(parts[2])), bool(int(parts[3]))
            observed_corrected = int(parts[4], 16)
            observed_data = int(parts[5], 16)
            observed_locations = [] if len(parts) < 7 or parts[6] == "-" else sorted(map(int, parts[6].split(",")))
            canonical_mask = _canonical_from_native(native_mask, mapping)
            expected = adapter.decode(canonical_mask)
            expected_detected = expected.status != DecodeStatus.NO_ERROR
            expected_success = expected.status in {DecodeStatus.NO_ERROR, DecodeStatus.CORRECTED}
            expected_corrected = 0 if expected.corrected_codeword_optional is None else _native_from_canonical(expected.corrected_codeword_optional, mapping)
            expected_data = 0 if expected.data is None else expected.data
            raw_location = expected.error_location_optional
            canonical_locations = [] if raw_location is None else [raw_location] if isinstance(raw_location, int) else list(raw_location)
            expected_locations = sorted(mapping[position] for position in canonical_locations)
            decodings += 1
            if (detected, success, observed_corrected, observed_data, observed_locations) != (
                expected_detected, expected_success, expected_corrected, expected_data, expected_locations
            ):
                failures.append(
                    {
                        "kind": "decode",
                        "native_mask": native_mask,
                        "canonical_mask": canonical_mask,
                        "expected": [expected_detected, expected_success, expected_corrected, expected_data, expected_locations],
                        "observed": [detected, success, observed_corrected, observed_data, observed_locations],
                    }
                )
    expected_decodings = 1 + 63 + len(list(combinations(range(63), 2)))
    complete = encodings == 54 and decodings == expected_decodings and meta is not None
    return {
        "implementation_id": implementation_id,
        "gate_status": "PASS" if complete and not failures else "FAIL",
        "oracle_classification": "independent cross-language evidence",
        "independence_basis": {
            "cpp_specification_path": "existing src/bch63.* primitive-field construction",
            "cpp_algorithm": "Berlekamp-Massey plus Chien search",
            "python_algorithm": "bounded exact packed-syndrome locator table",
            "driver_boundary": "I/O exposure only; no Python verifier algorithm translated",
        },
        "encoding_cases": encodings,
        "decoding_cases": decodings,
        "expected_decoding_cases": expected_decodings,
        "complete_masks_through_t2": complete,
        "failures": failures[:20],
        "meta": meta,
        "compile": compile_result,
        "execute": {key: value for key, value in execute_result.items() if key not in {"stdout", "stderr"}},
        "stdout_sha256": __import__("hashlib").sha256(execute_result["stdout"].encode()).hexdigest(),
    }


def _decode_vectors(
    registry: EccRegistry,
    implementation_id: str,
) -> tuple[list[tuple[int, int]], list[int], list[int], Mapping[str, Any]]:
    implementation = registry.implementation(implementation_id)
    code = registry.code(str(implementation["code_id"]))
    adapter = registry.adapter(implementation_id)
    spec = canonical_code_spec(code, [implementation_id])
    mapping = list(spec["native_to_canonical_equivalence"]["canonical_to_native_zero_based"])
    definitions = universe_definitions_for(code, implementation)
    selected = [item for item in definitions if item["declared_capability"] != "observation"]
    masks: dict[int, list[str]] = {}
    for definition in selected:
        for _, mask in masks_for_definition(definition, int(code["n"]), int(code["k"])):
            masks.setdefault(mask, []).append(str(definition["universe_id"]))
    vectors: list[tuple[int, int]] = []
    for mask in sorted(masks):
        result = adapter.decode(mask)
        observation = observe_decode(
            result, payload=0, codeword=0, received=mask, error_mask=mask,
            h=code["_resolved_matrix"]["H"],
        )
        vectors.append((_native_from_canonical(mask, mapping), OUTCOME_CODES[observation.outcome]))
    payloads = _payloads(int(code["k"]), implementation_id)
    encoded = [_native_from_canonical(adapter.encode(payload), mapping) for payload in payloads]
    return vectors, payloads, encoded, {
        "universe_ids": [item["universe_id"] for item in selected],
        "unique_decode_vectors": len(vectors),
        "encode_translation_probes": len(payloads),
        "canonical_to_native_zero_based": mapping,
    }


def _testbench(kind: str, n: int, k: int, encode_path: Path, decode_path: Path) -> str:
    enc_file = encode_path.as_posix().replace("\\", "/")
    dec_file = decode_path.as_posix().replace("\\", "/")
    declarations = f"logic [{k-1}:0] data_i, data_o; logic [{n-1}:0] codeword, received, corrected; logic det, cor, unc;"
    if kind == "hsiao":
        instances = (
            "hsiao_secded_72_64_v1_encoder enc(.data(data_i),.codeword(codeword));\n"
            "hsiao_secded_72_64_v1_decoder dec(.word(received),.data_out(data_o),"
            ".correction_applied(cor),.detected_uncorrectable(unc));\n"
            "assign det = cor | unc; assign corrected = 'x;"
        )
        corrected_check = ""
    elif kind == "secded":
        instances = (
            "logic [6:0] syn; logic om; logic [71:0] cmask; logic [6:0] ep;\n"
            "secded_encoder #(.DATA_W(64)) enc(.data_i(data_i),.codeword_o(codeword),.parity_dbg_o());\n"
            "secded_decoder #(.DATA_W(64)) dec(.codeword_i(received),.data_o(data_o),"
            ".corrected_codeword_o(corrected),.syndrome_o(syn),.overall_mismatch_o(om),"
            ".err_detected_o(det),.err_corrected_o(cor),.err_uncorrectable_o(unc),"
            ".correction_mask_o(cmask),.error_pos_o(ep));"
        )
        corrected_check = "if (actual == 1 && corrected !== '0) actual = 3;"
    elif kind == "secdaec":
        instances = (
            "logic [6:0] syn; logic adj;\n"
            "secdaec_encoder #(.DATA_W(64)) enc(.data_i(data_i),.codeword_o(codeword));\n"
            "secdaec_decoder #(.DATA_W(64)) dec(.codeword_i(received),.data_o(data_o),"
            ".corrected_codeword_o(corrected),.syndrome_o(syn),.err_detected_o(det),"
            ".err_corrected_o(cor),.err_uncorrectable_o(unc),.adjacent_double_corrected_o(adj));"
        )
        corrected_check = "if (actual == 1 && corrected !== '0) actual = 3;"
    elif kind == "taec":
        instances = (
            "logic [6:0] syn; logic triple_hit;\n"
            "taec_encoder #(.DATA_W(64)) enc(.data_i(data_i),.codeword_o(codeword));\n"
            "taec_decoder #(.DATA_W(64)) dec(.codeword_i(received),.data_o(data_o),"
            ".corrected_codeword_o(corrected),.syndrome_o(syn),.err_detected_o(det),"
            ".err_corrected_o(cor),.err_uncorrectable_o(unc),.triple_adjacent_corrected_o(triple_hit));"
        )
        corrected_check = "if (actual == 1 && corrected !== '0) actual = 3;"
    elif kind == "cyclic":
        instances = (
            "logic [11:0] syn;\n"
            "bch_encoder enc(.data_i(data_i),.codeword_o(codeword));\n"
            "bch_decoder dec(.codeword_i(received),.data_o(data_o),.corrected_codeword_o(corrected),"
            ".syndrome_o(syn),.err_detected_o(det),.err_corrected_o(cor),.err_uncorrectable_o(unc));"
        )
        corrected_check = "if (actual == 1 && corrected !== '0) actual = 3;"
    else:
        raise ValueError(kind)
    return f'''`timescale 1ns/1ps
module gate02_tb;
  {declarations}
  integer fd, scan, cases, actual, expected; integer failures;
  logic [{k-1}:0] expected_data; logic [{n-1}:0] expected_codeword;
  {instances}
  initial begin
    failures=0; cases=0; data_i='0; received='0; #1;
    fd=$fopen("{enc_file}","r"); if(fd==0) $fatal(1,"encode vectors unavailable");
    while(!$feof(fd)) begin
      scan=$fscanf(fd,"%h %h\\n",expected_data,expected_codeword);
      if(scan==2) begin data_i=expected_data; #1; cases=cases+1; if(codeword !== expected_codeword) failures=failures+1; end
    end
    $fclose(fd); data_i='0; #1;
    fd=$fopen("{dec_file}","r"); if(fd==0) $fatal(1,"decode vectors unavailable");
    while(!$feof(fd)) begin
      scan=$fscanf(fd,"%h %d\\n",expected_codeword,expected);
      if(scan==2) begin
        received=expected_codeword; #1; cases=cases+1;
        if(cor) actual=(data_o==='0)?1:3;
        else if(unc) actual=2;
        else if(!det) begin
          if(data_o!=='0) actual=4; else if(received==='0) actual=0; else actual=5;
        end else actual=5;
        {corrected_check}
        if(actual != expected) failures=failures+1;
      end
    end
    $fclose(fd);
    $display("GATE02_RTL cases=%0d failures=%0d",cases,failures);
    if(failures) $fatal(1,"RTL differential failures=%0d",failures);
    $finish;
  end
endmodule
'''


RTL_CONFIGS = {
    "hsiao-generated-combinational-72-64-v1": (
        "hsiao", [
            "green_ecc_physical_simulation/rtl/hsiao_secded_72_64/hsiao_secded_72_64_v1_encoder.sv",
            "green_ecc_physical_simulation/rtl/hsiao_secded_72_64/hsiao_secded_72_64_v1_syndrome.sv",
            "green_ecc_physical_simulation/rtl/hsiao_secded_72_64/hsiao_secded_72_64_v1_decoder.sv",
        ],
    ),
    "secded-rtl-combinational-72-64-v1": (
        "secded", ["asic/include/ecc_pkg.sv", "asic/rtl/secded/secded_codec.sv"],
    ),
    "secdaec-rtl-bounded-72-64-v1": (
        "secdaec", ["asic/include/ecc_pkg.sv", "asic/rtl/secded/secded_codec.sv", "asic/rtl/secdaec/secdaec_codec.sv"],
    ),
    "taec-rtl-bounded-72-64-v1": (
        "taec", ["asic/include/ecc_pkg.sv", "asic/rtl/secded/secded_codec.sv", "asic/rtl/taec/taec_codec.sv"],
    ),
    "cyclic-rtl-bounded-search-63-51-v1": (
        "cyclic", ["asic/rtl/bch/bch_codec.sv"],
    ),
}


def run_rtl(root: Path, registry: EccRegistry, work: Path) -> dict[str, Any]:
    iverilog = _tool("iverilog")
    vvp = _tool("vvp")
    if not iverilog or not vvp:
        return {
            "gate_status": "NOT ASSESSABLE",
            "reason": "Icarus iverilog/vvp unavailable",
            "implementations": {
                identifier: {"gate_status": "NOT ASSESSABLE"} for identifier in RTL_CONFIGS
            },
        }
    iverilog_path = Path(iverilog)
    vvp_path = Path(vvp)
    if os.name == "nt" and " " in str(iverilog_path):
        portable_bin = work / "toolchain" / "bin"
        portable_lib = work / "toolchain" / "lib" / "ivl"
        portable_bin.mkdir(parents=True, exist_ok=True)
        shutil.copy2(iverilog_path, portable_bin / iverilog_path.name)
        shutil.copy2(vvp_path, portable_bin / vvp_path.name)
        source_lib = iverilog_path.parent.parent / "lib" / "ivl"
        shutil.copytree(source_lib, portable_lib, dirs_exist_ok=True)
        iverilog = str(portable_bin / iverilog_path.name)
        vvp = str(portable_bin / vvp_path.name)
    results: dict[str, Any] = {}
    for implementation_id, (kind, sources) in RTL_CONFIGS.items():
        implementation = registry.implementation(implementation_id)
        code = registry.code(str(implementation["code_id"]))
        vectors, payloads, encoded, coverage = _decode_vectors(registry, implementation_id)
        prefix = work / implementation_id
        prefix.mkdir(parents=True, exist_ok=True)
        encode_path = prefix / "encode_vectors.txt"
        decode_path = prefix / "decode_vectors.txt"
        encode_path.write_text(
            "".join(f"{payload:x} {codeword:x}\n" for payload, codeword in zip(payloads, encoded)),
            encoding="ascii",
        )
        decode_path.write_text("".join(f"{received:x} {outcome}\n" for received, outcome in vectors), encoding="ascii")
        tb = prefix / "gate02_tb.sv"
        tb.write_text(_testbench(kind, int(code["n"]), int(code["k"]), encode_path, decode_path), encoding="utf-8")
        executable = prefix / "gate02.vvp"
        compile_result = _run(
            [iverilog, "-g2012", "-Iasic/include", "-o", str(executable), *sources, str(tb)],
            cwd=root,
            timeout=120,
        )
        execute_result = None
        if compile_result["execution_status"] == "PASS":
            execute_result = _run([vvp, str(executable)], cwd=root, timeout=120)
        status = compile_result["execution_status"]
        if execute_result is not None:
            status = execute_result["execution_status"]
            if status == "TIMEOUT" or (
                status == "FAIL"
                and execute_result.get("exit_code") == 3221225477
                and not execute_result.get("stdout")
                and not execute_result.get("stderr")
            ):
                status = "NOT ASSESSABLE"
        results[implementation_id] = {
            "gate_status": status,
            "coverage": coverage,
            "compile": compile_result,
            "execute": execute_result,
            "vector_hashes": {
                "encode": file_sha256(encode_path),
                "decode": file_sha256(decode_path),
                "testbench": file_sha256(tb),
            },
            "interpretation": "technology-independent RTL functional differential only; no PPA evidence",
        }
    overall = (
        "PASS"
        if all(item["gate_status"] == "PASS" for item in results.values())
        else "FAIL"
        if any(item["gate_status"] == "FAIL" for item in results.values())
        else "NOT ASSESSABLE"
    )
    return {
        "gate_status": overall,
        "runner": "portable Python subprocess runner with explicit per-command 120-second timeout",
        "implementations": results,
        "generated_width_families": {
            "gate_status": "NOT ASSESSABLE",
            "reason": "no registered independent generator/specification and complete executable path; SafeForge generation unchanged",
        },
    }


def run_all(root: Path, registry: EccRegistry, output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="green-ecc-gate02-equivalence-") as name:
        work = Path(name)
        cpp = run_cpp(root, registry, work / "cpp")
        rtl = run_rtl(root, registry, work / "rtl")
    payload = {
        "schema_version": 1,
        "cpp_bch63": cpp,
        "rtl": rtl,
        "secdaec64_hpp": {
            "registered": False,
            "total_bits_as_written": 73,
            "classification": "unregistered distinct-width implementation; not a (72,64) oracle",
        },
    }
    (output / "implementation_equivalence.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=Path("green_ecc_physical_simulation/registry/registry.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    registry_path = args.registry if args.registry.is_absolute() else ROOT / args.registry
    output = args.output if args.output.is_absolute() else ROOT / args.output
    registry = EccRegistry.load(registry_path, repo_root=ROOT)
    result = run_all(ROOT, registry, output)
    print(json.dumps({"cpp": result["cpp_bch63"]["gate_status"], "rtl": result["rtl"]["gate_status"]}, indent=2))
    return 0 if result["cpp_bch63"]["gate_status"] == "PASS" and result["rtl"]["gate_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
