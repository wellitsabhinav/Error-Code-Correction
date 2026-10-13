#!/usr/bin/env python3
"""Validate GREENS public documentation, metadata, and repository hygiene."""
from __future__ import annotations

import argparse
import ast
import hashlib
from datetime import date, datetime
import json
from pathlib import Path
import re
import subprocess
import sys

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.check_artifact import broken_markdown_links  # noqa: E402

PERSONAL_PATH = re.compile(r"(?<![\w])(?:[A-Za-z]:[\\/](?=\S)|/home/[\w.-]+/|/mnt/[a-z]/|/Users/[\w.-]+/|/root/(?:\.codex|workspace)/|/tmp/codex[\w.-]*/)")
DEVELOPMENT_HASH = re.compile(r"\b[0-9a-f]{40,64}\b", re.IGNORECASE)
# Original executed capability-gate record; retain its byte-bound provenance.
HISTORICAL_PROVENANCE_FILES = {'green_ecc_physical_simulation/SIMULATION_CAPABILITY_AUDIT.md'}
TRANSIENT = re.compile(r"(^|/)(__pycache__|node_modules|\.pytest_cache|\.venv|local_tmp)(/|$)|\.pyc$")


def changed_paths(base: str | None) -> list[Path]:
    if base:
        if not base.strip('0'):
            base = 'origin/main'
        names = subprocess.check_output(['git', 'diff', '--diff-filter=ACMR', '--name-only', base, 'HEAD'], cwd=ROOT, text=True).splitlines()
    else:
        names = subprocess.check_output(['git', 'ls-files'], cwd=ROOT, text=True).splitlines()
    return [ROOT / name for name in names]


def public_markdown(path: Path) -> bool:
    relative = path.relative_to(ROOT).as_posix()
    return path.suffix == '.md' and relative not in HISTORICAL_PROVENANCE_FILES and not relative.startswith(
        ('campaigns/', 'cleanup/', 'archives/', 'reports/', 'docs/date2027/', 'docs/archive/'))


def fences_balanced(text: str) -> bool:
    opener = None
    for line in text.splitlines():
        match = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if not match:
            continue
        delimiter, tail = match.groups()
        if opener is None:
            if delimiter[0] != '`' or '`' not in tail:
                opener = delimiter
        elif delimiter[0] == opener[0] and len(delimiter) >= len(opener) and not tail.strip():
            opener = None
    return opener is None


def normalize_yaml_dates(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: normalize_yaml_dates(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_yaml_dates(item) for item in value]
    return value


def validate(paths: list[Path]) -> list[str]:
    errors = []
    identity = json.loads((ROOT / 'docs/maintenance/integrity/historical_records.json').read_text(encoding='utf8'))
    for relative in HISTORICAL_PROVENANCE_FILES:
        record = ROOT / relative
        expected = identity['records'][relative]['sha256']
        if hashlib.sha256(record.read_bytes().replace(b'\r\n', b'\n')).hexdigest() != expected:
            errors.append('historical provenance content changed: ' + relative)
    tracked = subprocess.check_output(['git', 'ls-files', '*.md'], cwd=ROOT, text=True).splitlines()
    markdown = [ROOT / name for name in tracked if (ROOT / name).is_file() and public_markdown(ROOT / name)]
    errors.extend(broken_markdown_links(markdown))
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        if not path.is_file():
            continue
        if TRANSIENT.search(relative):
            errors.append('committed transient file: ' + relative)
        if public_markdown(path):
            text = path.read_text(encoding='utf-8')
            if not fences_balanced(text):
                errors.append('unbalanced Markdown fences: ' + relative)
            for line in text.splitlines():
                # External citations and exact tool versions are legitimate.
                clean = re.sub(r'https?://[^\s)]+', '', line)
                if PERSONAL_PATH.search(clean):
                    errors.append('personal filesystem path in public prose: ' + relative)
                if DEVELOPMENT_HASH.search(clean):
                    errors.append('raw development/integrity hash in public prose: ' + relative)
            for alt in re.findall(r'!\[([^\]]*)\]\(', text):
                if not alt.strip():
                    errors.append('empty image description: ' + relative)
            for block in re.findall(r'```json\s*\n(.*?)```', text, re.DOTALL):
                try:
                    json.loads(block)
                except ValueError:
                    errors.append('invalid JSON example: ' + relative)
        if relative.startswith('.github/') and path.suffix in {'.yml', '.yaml'}:
            try:
                yaml.safe_load(path.read_text(encoding='utf-8'))
            except yaml.YAMLError:
                errors.append('invalid YAML: ' + relative)
        if relative.startswith(('configs/', 'schemas/')) and path.suffix == '.json':
            try:
                json.loads(path.read_text(encoding='utf-8'))
            except ValueError:
                errors.append('invalid JSON: ' + relative)
        if path.suffix == '.py' and relative.startswith(('scripts/', 'validation/')):
            try:
                ast.parse(path.read_text(encoding='utf-8'), filename=relative)
            except SyntaxError:
                errors.append('invalid Python syntax: ' + relative)
    citation = normalize_yaml_dates(yaml.safe_load((ROOT / 'CITATION.cff').read_text(encoding='utf-8')))
    schema = json.loads((ROOT / 'schemas/citation-1.2.0.schema.json').read_text(encoding='utf-8'))
    try:
        jsonschema.Draft7Validator(schema, format_checker=jsonschema.FormatChecker()).validate(citation)
    except jsonschema.ValidationError as error:
        errors.append('invalid CITATION.cff: ' + error.message)
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-ref', help='Validate changed paths against a known Git ref; frozen history remains excluded')
    args = parser.parse_args()
    paths = changed_paths(args.base_ref)
    errors = validate(paths)
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print('PUBLIC_QUALITY_PASS: Markdown links/images/fences, YAML/JSON, citation schema, syntax and hygiene')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
