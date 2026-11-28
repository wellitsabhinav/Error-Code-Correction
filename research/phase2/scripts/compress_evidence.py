"""Losslessly compress generated inactive activity JSON; verify before removal.

Only the exact *.activity.json files in known synthetic qualification directories
are eligible. Raw VCD evidence remains complete and tiny. No baseline is touched.
"""
from __future__ import annotations
import gzip
import hashlib
from pathlib import Path
from common import PHASE, sha256, write_json


def main():
    records = []
    for label in ('qualification', 'qualification_ns', 'qualification_final'):
        root = (PHASE / 'raw' / label).resolve()
        if not root.is_dir():
            continue
        for source in sorted(root.glob('*.activity.json')):
            if source.is_symlink() or source.resolve().parent != root:
                raise ValueError('refusing linked activity evidence')
            payload = source.read_bytes()
            original_sha = hashlib.sha256(payload).hexdigest()
            target = source.with_suffix(source.suffix + '.gz')
            with target.open('wb') as stream:
                with gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0) as compressed:
                    compressed.write(payload)
            if gzip.decompress(target.read_bytes()) != payload:
                raise ValueError('lossless roundtrip verification failed')
            records.append({'source': str(source.relative_to(PHASE)).replace('\\', '/'),
                            'original_sha256': original_sha, 'original_bytes': len(payload),
                            'retained': str(target.relative_to(PHASE)).replace('\\', '/'),
                            'compressed_sha256': sha256(target), 'compressed_bytes': target.stat().st_size,
                            'verification': 'BYTE_IDENTICAL_GZIP_ROUNDTRIP', 'action': 'REMOVE_VERIFIED_UNCOMPRESSED_DUPLICATE'})
            if sha256(source) != original_sha:
                raise ValueError('source changed before compression finalization')
            source.unlink()
    previous = PHASE / 'manifests/compression.json'
    if records:
        write_json(previous, {'records': records, 'saved_bytes': sum(r['original_bytes']-r['compressed_bytes'] for r in records)})
    print(f'compressed and verified {len(records)} generated activity summaries')


if __name__ == '__main__':
    main()
