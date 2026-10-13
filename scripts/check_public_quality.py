#!/usr/bin/env python3
"""Validate GREENS public documentation, metadata, and repository hygiene."""
from __future__ import annotations

import argparse
import ast
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
TRANSIENT = re.compile(r"(^|/)(__pycache__|node_modules|\.pytest_cache|\.venv|local_tmp)(/|$)|\.pyc$")


def changed_paths(base: str | None) -> list[Path]:
    if base:
        if not base.strip('0'):
            base = 'origin/main'
        names = subprocess.check_output(['git', 'diff', '--name-only', base, 'HEAD'], cwd=ROOT, text=True).splitlines()
    else:
        names = subprocess.check_output(['git', 'ls-files'], cwd=ROOT, text=True).splitlines()
    return [ROOT / name for name in names]


def public_markdown(path: Path) -> bool:
    relative = path.relative_to(ROOT).as_posix()
    return path.suffix == '.md' and not relative.startswith(
        ('campaigns/', 'cleanup/', 'archives/', 'reports/', 'docs/date2027/', 'docs/archive/'))


def validate(paths: list[Path]) -> list[str]:
    errors = []
    markdown = [p for p in paths if p.is_file() and public_markdown(p)]
    errors.extend(broken_markdown_links(markdown))
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        if TRANSIENT.search(relative):
            errors.append('committed transient file: ' + relative)
        if not path.is_file():
            continue
        if public_markdown(path):
            text = path.read_text(encoding='utf-8')
            fences = re.findall(r'^\s*(`{3,}|~{3,}).*$', text, flags=re.MULTILINE)
            if len(fences) % 2:
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
    citation = yaml.safe_load((ROOT / 'CITATION.cff').read_text(encoding='utf-8'))
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
