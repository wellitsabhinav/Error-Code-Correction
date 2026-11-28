"""Audit storage; delete only manifest-authorized, hash-verified scratch files.

No broad glob, repository, baseline, PDK, virtual disk or system cleanup exists.
"""
from __future__ import annotations
import argparse
import csv
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from common import PHASE, ROOT, sha256, write_csv, write_json


def resolve_scratch(relative, phase=PHASE):
    phase = Path(phase).resolve()
    original = phase / relative
    for component in (original, *original.parents):
        if component == phase:
            break
        if component.is_symlink() or (hasattr(component, 'is_junction') and component.is_junction()):
            raise ValueError('cleanup rejects linked paths')
    candidate = original.resolve()
    scratch = (phase / 'scratch').resolve()
    if candidate == scratch or not candidate.is_relative_to(scratch):
        raise ValueError('cleanup target outside configured scratch root')
    if not candidate.is_file() or candidate.is_symlink():
        raise ValueError('cleanup accepts existing regular files only')
    return candidate


def verified_candidates(manifest_path, phase=PHASE):
    phase = Path(phase).resolve()
    manifest_path = Path(manifest_path).resolve()
    if not manifest_path.is_relative_to(phase / 'experiments'):
        raise ValueError('cleanup manifest outside experiment workspace')
    data = json.loads(manifest_path.read_text(encoding='utf-8'))
    if data.get('status') != 'COMPLETE' or not data.get('retained_artifacts'):
        raise ValueError('incomplete or unauditable run; preserving recovery files')
    retained = []
    for ref in data['retained_artifacts']:
        p = (phase / ref['path']).resolve()
        if not p.is_relative_to(phase) or not p.is_file() or sha256(p) != ref['sha256']:
            raise ValueError('retained artifact verification failed')
        retained.append(p)
    candidates = []
    for item in data.get('disposable_temporary', []):
        if item.get('unique_scientific_evidence') is not False or item.get('verified_temporary') is not True:
            raise ValueError('temporary classification missing')
        p = resolve_scratch(item['path'], phase)
        if p in retained or sha256(p) != item['sha256']:
            raise ValueError('temporary hash mismatch or retained evidence conflict')
        candidates.append((p, item['sha256']))
    if len({p for p, _ in candidates}) != len(candidates):
        raise ValueError('duplicate cleanup entry')
    return candidates


def cleanup(manifest_path, phase=PHASE, execute=False):
    candidates = verified_candidates(manifest_path, phase)
    records = [{'path': str(p), 'bytes': p.stat().st_size, 'sha256': h} for p, h in candidates]
    print(json.dumps({'dry_run': not execute, 'would_remove': records}, indent=2), flush=True)
    if execute:
        log = Path(phase) / 'processed' / 'cleanup.jsonl'
        log.parent.mkdir(parents=True, exist_ok=True)
        for p, expected in candidates:
            # Re-resolve and re-hash immediately before deleting each exact file.
            resolve_scratch(p, phase)
            if sha256(p) != expected:
                raise ValueError('file changed since cleanup verification')
            with log.open('a', encoding='utf-8') as f:
                f.write(json.dumps({'path': str(p), 'sha256': expected, 'utc': datetime.now(timezone.utc).isoformat(), 'action': 'verified_remove'}) + '\n')
                f.flush()
            p.unlink()
    return records


def audit(label):
    history = PHASE / 'processed' / 'storage_history.csv'
    rows = []
    for drive in ('C:/', 'G:/', 'F:/', str(PHASE)):
        if not Path(drive).exists():
            continue
        usage = shutil.disk_usage(drive)
        rows.append({'utc': datetime.now(timezone.utc).isoformat(), 'label': label,
                     'path': drive, 'total_bytes': usage.total, 'free_bytes': usage.free})
    existing = []
    if history.exists():
        with history.open(encoding='utf-8', newline='') as f:
            existing = list(csv.DictReader(f))
    write_csv(history, existing + rows)
    inventory = []
    for p in sorted(PHASE.rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts and '.pytest_cache' not in p.parts:
            inventory.append({'path': str(p.relative_to(ROOT)).replace('\\', '/'),
                              'size_bytes': p.stat().st_size, 'sha256': sha256(p),
                              'class': 'temporary' if 'scratch' in p.relative_to(PHASE).parts else 'retained'})
    write_csv(PHASE / 'processed' / 'artifact_inventory.csv', inventory,
              ['path', 'size_bytes', 'sha256', 'class'])
    return {'drives': rows, 'phase2_bytes': sum(r['size_bytes'] for r in inventory),
            'files': len(inventory), 'note': 'Host free-space samples include unrelated host activity; phase bytes are exact sampled file lengths. Inventory excludes its new self-version.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    au = sub.add_parser('audit')
    au.add_argument('--label', default='sample')
    cl = sub.add_parser('cleanup')
    cl.add_argument('--manifest', required=True)
    group = cl.add_mutually_exclusive_group()
    group.add_argument('--dry-run', action='store_true')
    group.add_argument('--verified-temporary-only', action='store_true')
    a = p.parse_args()
    if a.command == 'audit':
        print(json.dumps(audit(a.label), indent=2))
    else:
        cleanup(a.manifest, execute=a.verified_temporary_only)


if __name__ == '__main__':
    main()
