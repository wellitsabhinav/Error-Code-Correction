"""Run historical builders in disposable copies without mutating sealed evidence."""
from __future__ import annotations

import hashlib
import csv
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def copy_input(repo: Path, isolated: Path, relative: str) -> None:
    source = repo / relative
    target = isolated / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def copy_campaign(repo: Path, isolated: Path, campaign: Path) -> Path:
    target = isolated / campaign.relative_to(repo)
    shutil.copytree(campaign, target, ignore=shutil.ignore_patterns('__pycache__'))
    return target


def seal_bindings(path: Path) -> dict[str, str]:
    return {relative: digest for digest, relative in
            (line.split('  ', 1) for line in path.read_text(encoding='utf8').splitlines())}


def equivalent_value(left, right) -> bool:
    if isinstance(left, float) and isinstance(right, float):
        # Python statistics implementations can differ in their last bits.
        return math.isclose(left, right, rel_tol=1e-14, abs_tol=0.0)
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(equivalent_value(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(equivalent_value(a, b) for a, b in zip(left, right))
    return left == right


def equivalent_payload(left: Path, right: Path) -> bool:
    if left.suffix == '.json':
        return equivalent_value(json.loads(left.read_text(encoding='utf8')), json.loads(right.read_text(encoding='utf8')))
    if left.suffix == '.csv':
        def rows(path):
            with path.open(encoding='utf8', newline='') as stream:
                result = list(csv.reader(stream))
            for row in result:
                for i, value in enumerate(row):
                    try:
                        row[i] = float(value)
                    except ValueError:
                        pass
            return result
        return equivalent_value(rows(left), rows(right))
    return left.read_text(encoding='utf8') == right.read_text(encoding='utf8')


def assert_regenerated_outputs(original: Path, regenerated: Path, outputs: list[str]) -> None:
    # Historical Path sorting and write_text newline translation vary by OS.
    # Payloads must be identical after newline decoding; every regenerated
    # seal binding must still match the exact bytes it actually names.
    for name in outputs:
        assert equivalent_payload(regenerated / name, original / name), name
    before = seal_bindings(original / 'hashes/CAMPAIGN_ARTIFACTS.sha256')
    after = seal_bindings(regenerated / 'hashes/CAMPAIGN_ARTIFACTS.sha256')
    assert after.keys() == before.keys()
    for relative, digest in after.items():
        actual = hashlib.sha256((regenerated / relative).read_bytes()).hexdigest()
        assert actual == digest, relative
        if digest != before[relative]:
            assert equivalent_payload(regenerated / relative, original / relative), relative


def check_campaign_builder(repo: Path, campaign: Path, outputs: list[str], inputs: set[str]) -> None:
    original_seal = (campaign / 'hashes/CAMPAIGN_ARTIFACTS.sha256').read_bytes()
    # Use a short system temp path: historical Python imports on Windows do
    # not reliably support the repository's deeply nested pytest fixture path.
    with tempfile.TemporaryDirectory(prefix='greens-') as directory:
        isolated = Path(directory)
        regenerated = copy_campaign(repo, isolated, campaign)
        for relative in inputs:
            copy_input(repo, isolated, relative)
        subprocess.run([sys.executable, str(regenerated / 'build_campaign.py'),
                        '--repo', str(isolated)], cwd=isolated, check=True,
                       capture_output=True, text=True)
        assert_regenerated_outputs(campaign, regenerated, outputs)
    assert (campaign / 'hashes/CAMPAIGN_ARTIFACTS.sha256').read_bytes() == original_seal
