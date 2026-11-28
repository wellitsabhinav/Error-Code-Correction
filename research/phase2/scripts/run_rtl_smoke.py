"""Independent functional check on exact current-checkout RTL; no physical claim."""
from __future__ import annotations
import argparse
from common import PHASE, ROOT, run_command, sha256, write_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--iverilog', required=True)
    p.add_argument('--vvp', required=True)
    p.add_argument('--ivl-base', required=True)
    a = p.parse_args()
    out = PHASE / 'raw/rtl_smoke'
    out.mkdir(parents=True, exist_ok=True)
    scratch = PHASE / 'scratch/rtl_smoke'
    scratch.mkdir(parents=True, exist_ok=True)
    files = [
        'scripts/gate03r/rtl/secded_characterization_tops.sv',
        'asic/rtl/secded/secded_pipelined_72_64_v1.sv',
        'scripts/gate04/rtl/gate04_boundaries.sv',
        'scripts/revision2/rtl/rev2_hsiao_boundary.sv',
        'green_ecc_physical_simulation/rtl/hsiao_secded_72_64/hsiao_secded_72_64_v1_encoder.sv',
        'green_ecc_physical_simulation/rtl/hsiao_secded_72_64/hsiao_secded_72_64_v1_syndrome.sv',
        'green_ecc_physical_simulation/rtl/hsiao_secded_72_64/hsiao_secded_72_64_v2_algorithmic_decoder.sv',
        'campaigns/date_2027_breadth_remediation/rtl/hsiao_secded_72_64_v3_hierarchical_decoder.sv',
        'campaigns/date_2027_breadth_remediation/rtl/breadth_hsiao_hierarchical_boundary.sv',
        'research/phase2/verification/rtl_smoke_tb.sv']
    binary = scratch / 'smoke.vvp'
    compile_record = run_command([a.iverilog, '-B', a.ivl_base, '-g2012', '-s', 'rtl_smoke_tb', '-o', str(binary),
                                  *[str(ROOT / f) for f in files]], out, out / 'compile.log')
    run = None
    if compile_record['exit_code'] == 0:
        run = run_command([a.vvp, str(binary)], out, out / 'run.log')
    status = 'PASS' if run and run['exit_code'] == 0 and 'PASS architectures=4' in (out / 'run.log').read_text() else 'FAIL'
    write_json(out / 'results.json', {'status': status, 'compile': compile_record, 'run': run,
               'source_hashes': {f: sha256(ROOT / f) for f in files},
               'scope': 'Current-checkout RTL functional smoke only; Hsiao frozen byte conflicts remain unresolved.',
               'completed_operations_per_architecture': 100 if status == 'PASS' else None})
    print(status)
    return 0 if status == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
