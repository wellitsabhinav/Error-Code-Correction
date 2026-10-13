#!/usr/bin/env python3
"""Run bounded GREENS SECDED RTL smoke checks without modifying evidence."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    compiler = shutil.which('iverilog')
    simulator = shutil.which('vvp')
    if not compiler or not simulator:
        raise SystemExit('Icarus Verilog and vvp must be on PATH')
    with tempfile.TemporaryDirectory(prefix='greens-rtl-') as directory:
        temporary = Path(directory)
        if os.name == 'nt' and ' ' in compiler:
            # Icarus helpers require a prefix without spaces on this platform.
            from scripts.run_safeforge_hardware_validation import _portable_iverilog
            compiler, simulator = _portable_iverilog(Path(compiler), Path(simulator), temporary)
        image = temporary / 'secded.vvp'
        build = subprocess.run([str(compiler), '-g2012', '-I', 'asic/include', '-s', 'tb_secded',
                                '-o', str(image), 'asic/include/ecc_pkg.sv',
                                'asic/rtl/secded/secded_codec.sv', 'asic/tb/tb_secded.sv'],
                               cwd=ROOT, capture_output=True, text=True, timeout=60)
        if build.returncode:
            raise SystemExit(build.stderr)
        result = subprocess.run([str(simulator), str(image)], cwd=ROOT,
                                capture_output=True, text=True, timeout=60)
        if result.returncode or 'TB_SEDDED_PASS' not in result.stdout:
            raise SystemExit(result.stdout + result.stderr)
        print('RTL_SMOKE_PASS: clean SECDED, all 72 single-bit positions, double-bit detection')


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(ROOT))
    main()
