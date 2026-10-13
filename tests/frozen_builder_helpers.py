"""Run historical builders in disposable copies without mutating sealed evidence."""
from __future__ import annotations

import hashlib
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


def assert_regenerated_outputs(original: Path, regenerated: Path, outputs: list[str]) -> None:
    # Historical Path sorting and write_text newline translation vary by OS.
    # Payloads must be identical after newline decoding; every regenerated
    # seal binding must still match the exact bytes it actually names.
    for name in outputs:
        assert (regenerated / name).read_text(encoding='utf8') == (original / name).read_text(encoding='utf8'), name
    before = seal_bindings(original / 'hashes/CAMPAIGN_ARTIFACTS.sha256')
    after = seal_bindings(regenerated / 'hashes/CAMPAIGN_ARTIFACTS.sha256')
    assert after.keys() == before.keys()
    for relative, digest in after.items():
        actual = hashlib.sha256((regenerated / relative).read_bytes()).hexdigest()
        assert actual == digest, relative
        if digest != before[relative]:
            assert (regenerated / relative).read_text(encoding='utf8') == (original / relative).read_text(encoding='utf8'), relative


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
