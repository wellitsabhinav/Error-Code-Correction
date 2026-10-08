#!/usr/bin/env python3
"""Opt-in restoration of mixed newlines frozen by historical evidence hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restore', action='store_true', help='Restore only manifest-authorized newline positions')
    parser.add_argument('--refresh-index', action='store_true', help='Refresh Git stat metadata after verifying normalized blob identity')
    parser.add_argument('--repo', type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.repo.resolve()
    records = json.loads((ROOT / 'cleanup/FROZEN_MIXED_NEWLINES.json').read_text(encoding='utf8'))
    changed = []
    for record in records:
        relative = record['path']
        path = (root / relative).resolve()
        if not relative.startswith('docs/date2027/') or not path.is_relative_to(root):
            raise ValueError('Manifest path is outside the historical evidence scope')
        current = path.read_bytes()
        if digest(current) == record['frozen_sha256']:
            continue
        canonical = current.replace(b'\r\n', b'\n')
        if digest(canonical) != record['canonical_lf_sha256']:
            raise ValueError('Content differs beyond newline materialization: ' + relative)
        pieces = canonical.split(b'\n')
        positions = set(record['crlf_line_indices'])
        restored = b''.join(part + (b'\r\n' if i in positions else b'\n') for i, part in enumerate(pieces[:-1])) + pieces[-1]
        if digest(restored) != record['frozen_sha256']:
            raise ValueError('Frozen reconstruction hash mismatch: ' + relative)
        changed.append(relative)
        if args.restore:
            path.write_bytes(restored)
    if args.refresh_index:
        if not args.restore:
            parser.error('--refresh-index requires --restore')
        for relative in changed:
            expected = subprocess.check_output(['git', 'rev-parse', 'HEAD:' + relative], cwd=root).strip()
            actual = subprocess.check_output(['git', 'hash-object', '--path=' + relative, relative], cwd=root).strip()
            if actual != expected:
                raise ValueError('Normalized Git blob differs: ' + relative)
        if changed:
            subprocess.run(['git', 'add', '--', *changed], cwd=root, check=True)
    print(('Restored' if args.restore else 'Needs restoration:') + f' {len(changed)} mixed-newline historical files')


if __name__ == '__main__':
    main()
