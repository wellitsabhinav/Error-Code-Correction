#!/usr/bin/env python3
"""Verify a GREENS campaign archive against its published member manifest."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(4 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def verify(archive, manifest):
    payload = json.loads(Path(manifest).read_text(encoding='utf-8'))
    if sha256_file(archive) != payload['archive_sha256']:
        raise ValueError('Archive SHA256 does not match the manifest')
    expected = [{k: v for k, v in item.items() if k != 'mtime'} for item in payload['members']]
    root = Path(payload['source']).name
    actual = []
    with tarfile.open(archive, 'r:gz') as stream:
        for member in stream:
            if member.name == root:
                continue
            if not member.name.startswith(root + '/'):
                raise ValueError('Unexpected archive member: ' + member.name)
            relative = member.name[len(root) + 1:]
            if member.isfile():
                digest = hashlib.sha256()
                with stream.extractfile(member) as content:
                    while block := content.read(4 * 1024 * 1024):
                        digest.update(block)
                actual.append(dict(path=relative, kind='file', size_bytes=member.size, sha256=digest.hexdigest()))
            elif member.issym():
                actual.append(dict(path=relative, kind='symlink', target=member.linkname, size_bytes=0))
            elif member.isdir():
                actual.append(dict(path=relative, kind='directory', size_bytes=0))
            else:
                raise ValueError('Unsupported archive member: ' + member.name)
    if sorted(actual, key=lambda item: item['path']) != expected:
        raise ValueError('Archive member names, types, links, counts, sizes, or SHA256 differ')
    return sum(item['kind'] == 'file' for item in actual)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True, type=Path)
    parser.add_argument('--manifest', required=True, type=Path)
    args = parser.parse_args()
    count = verify(args.archive, args.manifest)
    print(f'PASS: {count} regular files; archive and every member verified')


if __name__ == '__main__':
    main()
