"""Freeze read-only references and source-hash conflicts without repairing history."""
from __future__ import annotations
import json
import subprocess
from pathlib import Path
from common import PHASE, ROOT, sha256, write_json, write_csv


def main():
    tree = subprocess.check_output(['git', 'ls-tree', '-r', 'HEAD'], cwd=ROOT, text=True).splitlines()
    records = []
    for line in tree:
        meta, path = line.split('\t', 1)
        mode, kind, oid = meta.split()
        records.append({'path': path, 'git_blob': oid, 'kind': kind,
                        'available_in_sparse_checkout': (ROOT / path).is_file()})
    contracts = ['scripts/revision2/contract_v1.json', 'campaigns/date_2027_breadth_remediation/physical/contract_v1.json']
    references, conflicts = {}, []
    for contract in contracts:
        d = json.loads((ROOT / contract).read_text(encoding='utf-8'))
        for path, expected in d['source_hashes'].items():
            p = ROOT / path
            actual = sha256(p) if p.is_file() else None
            key = contract + ':' + path
            crlf_match = False
            if actual is not None and actual != expected:
                import hashlib
                crlf_match = hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')).hexdigest() == expected
            references[key] = {'path': path, 'expected_sha256': expected, 'actual_sha256': actual,
                               'status': 'MATCH' if actual == expected else ('MISSING' if actual is None else 'CONFLICT'),
                               'expected_matches_CRLF_representation': crlf_match,
                               'action': 'REFERENCE_ONLY_NO_BYTE_REWRITE'}
            if actual != expected:
                conflicts.append(references[key])
    selected = []
    prefixes = ('campaigns/date_2027_breadth_remediation/', 'campaigns/date_2027_activity_qualified_ecc_energy_rev2/',
                'docs/date2027/revision2/', 'docs/date2027/rigour_gate_03r/', 'scripts/revision2/')
    paths = {r['path'] for r in references.values()} | set(contracts)
    for rec in records:
        if rec['available_in_sparse_checkout'] and (rec['path'].startswith(prefixes) or rec['path'] in paths):
            path = ROOT / rec['path']
            if path.suffix in ('.csv', '.json', '.sv', '.sdc', '.tcl', '.mk', '.sha256', '.md', '.py', '.log'):
                selected.append({**rec, 'size_bytes': path.stat().st_size, 'sha256': sha256(path)})
    manifest = {'schema_version': 1,
                'checkout_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'frozen_scientific_commit': '8cf245ac6ac8cb9b010c073d439f04eb204d48a1',
                'source_hash_checks': list(references.values()), 'hash_conflicts': conflicts,
                'baseline_files': selected,
                'technology': json.loads((ROOT / contracts[0]).read_text())['technology'],
                'raw_physical_evidence': 'Archive references retained; original DATE run directories and D:/GREENS_ARCHIVES absent locally.',
                'policy': 'References only; no baseline repair, normalization, resealing, or overwrite.'}
    write_json(PHASE / 'baseline_manifest.json', manifest)
    write_csv(PHASE / 'processed' / 'repository_artifact_index.csv', records)
    write_csv(PHASE / 'processed' / 'baseline_hash_checks.csv', list(references.values()))
    print(json.dumps({'tracked_paths': len(records), 'hashed_baseline_files': len(selected), 'conflicts': len(conflicts)}, indent=2))


if __name__ == '__main__':
    main()
