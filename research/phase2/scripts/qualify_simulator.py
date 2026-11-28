"""Execute small SDF probes; preserve negative annotation results.

The official two-cell wrappers do not include their separate specify files.
An explicitly labelled local assembly adds the official specify fragments to
the size wrappers. It qualifies only this synthetic circuit, never a routed ECC.
"""
from __future__ import annotations
import argparse
import json
import shutil
from pathlib import Path
from activity_stream import parse_vcd
from common import PHASE, ROOT, checkpoint, run_command, sha256, write_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--iverilog', default='iverilog')
    p.add_argument('--vvp', default='vvp')
    p.add_argument('--ivl-base', help='Existing Icarus helper directory, when relocated')
    p.add_argument('--run-id', default='simulator-qualification')
    p.add_argument('--consistent-timescale', action='store_true', help='Express SDF in the cell models\' ns units; retain ps mismatch probe separately')
    a = p.parse_args()
    source = PHASE / 'verification'
    official = source / 'sky130_minimal'
    out = PHASE / 'raw' / a.run_id
    scratch = PHASE / 'scratch' / a.run_id
    out.mkdir(parents=True, exist_ok=True)
    scratch.mkdir(parents=True, exist_ok=True)
    files = [source / 'hazard_tb.sv', source / 'hazard.sdf', source / 'interconnect.sdf', source / 'timing_checks_tb.sv',
             Path(__file__), Path(__file__).with_name('activity_stream.py'), Path(__file__).with_name('common.py')] + sorted(official.glob('*'))
    contract = {'inputs': {str(f.relative_to(ROOT)): sha256(f) for f in files},
                'iverilog': a.iverilog, 'vvp': a.vvp, 'ivl_base': a.ivl_base,
                'consistent_timescale': a.consistent_timescale, 'scope': 'synthetic only', 'revision': 2}
    manifest_path, manifest = checkpoint(a.run_id, contract)
    results = []

    def command(args, label, cwd=out):
        record = run_command(args, cwd, out / (label + '.log'))
        manifest['commands'].append(record)
        write_json(manifest_path, manifest)
        return record

    command([a.iverilog, '-V'], 'simulator_version')
    for cell in ('buf', 'xor2'):
        original = official / f'sky130_fd_sc_hd__{cell}_1.v'
        assembled = original.read_text(encoding='utf-8').replace(
            'endmodule', f'`include "sky130_fd_sc_hd__{cell}.specify.v"\nendmodule')
        (scratch / original.name).write_text(assembled, encoding='utf-8', newline='\n')
    assembly = {'method': 'Insert the upstream specify fragment before each size-wrapper endmodule; upstream base functional module unchanged.',
                'source_scope': 'Public SKY130 two-cell synthetic qualification, not full baseline timing models.',
                'files': {f.name: sha256(f) for f in scratch.glob('*.v')}}
    write_json(out / 'model_assembly.json', assembly)
    for label, assembled, corner, sdf, flags in [
        ('zero', True, 'typ', None, []),
        ('upstream_unassembled', False, 'typ', 'hazard.sdf', []),
        ('iopath_min', True, 'min', 'hazard.sdf', []),
        ('iopath_typ', True, 'typ', 'hazard.sdf', []),
        ('iopath_max', True, 'max', 'hazard.sdf', []),
        ('interconnect', True, 'typ', 'interconnect.sdf', []),
        ('interconnect_flag_probe', True, 'typ', 'interconnect.sdf', ['-ginterconnect']),
        ('narrow_pulse', True, 'typ', 'narrow_pulse.sdf', []),
        ('bad_hierarchy', True, 'typ', 'bad_hierarchy.sdf', [])]:
        binary = scratch / (label + '.vvp')
        model_dir = scratch if assembled else official
        base_flags = ['-B', a.ivl_base] if a.ivl_base else []
        argv = [a.iverilog, *base_flags, '-g2012', '-gspecify', '-T' + corner, *flags,
                '-I', str(official), '-s', 'hazard_tb', '-o', str(binary),
                str(source / 'hazard_tb.sv'), str(model_dir / 'sky130_fd_sc_hd__buf_1.v'),
                str(model_dir / 'sky130_fd_sc_hd__xor2_1.v')]
        compile_result = command(argv, label + '_compile')
        record = {'label': label, 'corner': corner, 'compile_exit': compile_result['exit_code'],
                  'expected_annotation_arcs': 4 if sdf == 'hazard.sdf' else (2 if sdf == 'interconnect.sdf' else 0)}
        if compile_result['exit_code'] == 0:
            vcd = out / (label + '.vcd')
            args = [a.vvp, str(binary), '+VCD=' + str(vcd)]
            if sdf:
                if sdf in ('bad_hierarchy.sdf', 'narrow_pulse.sdf'):
                    bad = scratch / sdf
                    text = (source / 'hazard.sdf').read_text()
                    if sdf == 'bad_hierarchy.sdf':
                        text = text.replace('u_fast', 'missing_fast')
                    else:
                        text = text.replace('1000:2000:3000', '125:250:375')
                    bad.write_text(text, encoding='utf-8')
                    args.append('+SDF=' + str(bad))
                else:
                    args.append('+SDF=' + str(source / sdf))
                if a.consistent_timescale:
                    actual = Path(args[-1].removeprefix('+SDF='))
                    text = actual.read_text().replace('TIMESCALE 1ps', 'TIMESCALE 1ns')
                    for old, new in [('1000:2000:3000', '1:2:3'), ('100:200:300', '0.1:0.2:0.3'),
                                     ('50:100:150', '0.05:0.1:0.15'), ('125:250:375', '0.125:0.25:0.375')]:
                        text = text.replace(old, new)
                    converted = scratch / (label + '_ns.sdf')
                    converted.write_text(text, encoding='utf-8')
                    args[-1] = '+SDF=' + str(converted)
                    record['applied_sdf_sha256'] = sha256(converted)
            execution = command(args, label + '_run')
            record['run_exit'] = execution['exit_code']
            record['annotation_log'] = execution['log']
            if execution['exit_code'] == 0 and vcd.exists():
                with vcd.open(encoding='utf-8') as f:
                    activity = parse_vcd(f, 5000, 49000)
                write_json(out / (label + '.activity.json'), activity)
                y = next(s for s in activity['signals'] if 'hazard_tb.y' in s['aliases'])
                record.update({'y_binary_transitions': y['binary_transitions'],
                               'y_min_pulse_ps': y['min_pulse_ps'],
                               'y_unknown_duration_ps': y['durations_ps']['x'] + y['durations_ps']['z'],
                               'y_high_duration_ps': y['durations_ps']['1'],
                               'pulse_samples_ps': y['pulse_samples_ps'],
                               'vcd_sha256': sha256(vcd), 'vcd_bytes': vcd.stat().st_size})
        results.append(record)
    timing_binary = scratch / 'timing.vvp'
    c = command([a.iverilog, *base_flags, '-g2012', '-gspecify', '-s', 'timing_checks_tb', '-o', str(timing_binary),
                 str(source / 'timing_checks_tb.sv')], 'timing_checks_compile')
    if c['exit_code'] == 0:
        command([a.vvp, str(timing_binary)], 'timing_checks_run')
    by = {r['label']: r for r in results}
    passed = by['zero'].get('y_binary_transitions') == 0 and by['zero'].get('y_unknown_duration_ps') == 0
    for label, width in [('iopath_min', 900), ('iopath_typ', 1800), ('iopath_max', 2700)]:
        passed &= (by[label].get('y_binary_transitions') == 4 and by[label].get('y_min_pulse_ps') == width
                   and by[label].get('y_unknown_duration_ps') == 0)
    data = {'schema_version': 1, 'synthetic_iopath_pass': bool(passed), 'results': results,
            'production_readiness': 'BLOCKED',
            'reason': 'Synthetic assembly cannot qualify full routed ECC models, missing DATE physical artifacts or untested full annotation coverage.',
            'delays': 'Artificial controlled path delays, not Liberty-derived cell or routed-wire delays.',
            'timing_check_log': str(out / 'timing_checks_run.log')}
    write_json(out / 'results.json', data)
    manifest['status'] = 'SYNTHETIC_PROBES_COMPLETED_PRODUCTION_BLOCKED'
    manifest['result_sha256'] = sha256(out / 'results.json')
    write_json(manifest_path, manifest)
    print(json.dumps(data, indent=2))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
