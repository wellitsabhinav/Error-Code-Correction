"""Read-only validation; blocked scientific readiness is not a package error."""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import json
import subprocess
from common import PHASE, ROOT, sha256, write_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seal', action='store_true', help='Write package file hashes after validation')
    a = p.parse_args()
    errors=[]
    baseline=json.loads((PHASE/'baseline_manifest.json').read_text())
    for r in baseline['baseline_files']:
        if not (ROOT/r['path']).is_file() or sha256(ROOT/r['path']) != r['sha256']:
            errors.append('baseline changed: '+r['path'])
    changed=subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=ROOT,text=True).splitlines()
    if any(not path.startswith('research/phase2/') for path in changed):
        errors.append('tracked non-Phase-II changes present')
    with (PHASE/'processed/power_method_comparison.csv').open(newline='',encoding='utf-8') as f:
        rows=list(csv.DictReader(f))
    if len(rows)!=60:
        errors.append('expected 4 architectures × 5 seeds × 3 method status rows')
    for row in rows:
        if row['energy_per_completed_op_pj'] or row['relative_deviation_vs_C_percent']:
            errors.append('unqualified production result populated')
    qualification=json.loads((PHASE/'raw/qualification_final/results.json').read_text())
    if qualification['production_readiness']!='BLOCKED' or not qualification['synthetic_iopath_pass']:
        errors.append('qualification status inconsistent')
    for record in qualification['results']:
        if record.get('vcd_sha256'):
            path=PHASE/'raw/qualification_final'/f'{record["label"]}.vcd'
            if sha256(path)!=record['vcd_sha256']:
                errors.append('qualification waveform changed: '+record['label'])
    compression=PHASE/'manifests/compression.json'
    if compression.exists():
        for r in json.loads(compression.read_text())['records']:
            path=PHASE/r['retained']
            if sha256(path)!=r['compressed_sha256'] or hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()!=r['original_sha256']:
                errors.append('compressed evidence failed: '+r['retained'])
    for r in json.loads((PHASE/'figures/figure_manifest.json').read_text()):
        for source,expected in r['sources'].items():
            if sha256(ROOT/source)!=expected:
                errors.append('figure source changed: '+source)
    package=PHASE/'manifests/package_sha256.json'
    if package.exists() and not a.seal:
        for r in json.loads(package.read_text())['files']:
            path=PHASE/r['path']
            if not path.is_file() or sha256(path)!=r['sha256']:
                errors.append('sealed package hash failed: '+r['path'])
    if a.seal and not errors:
        files=[]
        for path in sorted(PHASE.rglob('*')):
            rel=path.relative_to(PHASE)
            if path.is_file() and path!=package and not any(x in rel.parts for x in ('scratch','__pycache__','.pytest_cache')):
                files.append({'path':rel.as_posix(),'sha256':sha256(path),'bytes':path.stat().st_size})
        write_json(package,{'files':files,'note':'Self and scratch/caches excluded; no frozen artifact resealed.'})
    result={'package_status':'PASS' if not errors else 'FAIL','production_readiness':'BLOCKED',
            'baseline_hashed_files_unchanged':len(baseline['baseline_files']),'errors':errors}
    print(json.dumps(result,indent=2))
    return 1 if errors else 0


if __name__=='__main__':
    raise SystemExit(main())
