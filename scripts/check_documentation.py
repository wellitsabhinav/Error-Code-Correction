#!/usr/bin/env python3
"""Check maintained documentation and numerical figure data without resealing figures."""
from pathlib import Path
import csv
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import build_documentation as docs
from scripts.generate_documentation_figures import generate


def main() -> int:
    docs.validate(ROOT)
    stale = [p.as_posix() for p, expected in docs.expected_documents(ROOT).items()
             if (ROOT / p).read_text(encoding='utf8') != expected]
    if stale:
        raise ValueError('Stale generated sections: ' + ', '.join(stale))
    actual = json.loads((ROOT / 'docs/figure_data/documentation_build_summary.json').read_text(encoding='utf8'))
    if actual != docs.build_summary(ROOT):
        raise ValueError('Stale documentation build summary')
    checked = set()
    with tempfile.TemporaryDirectory(prefix='greens-docs-') as raw:
        output = Path(raw)
        manifest = generate(ROOT, output)
        for figure in manifest['figures']:
            for item in figure['figure_data']:
                relative = item['path']
                if relative in checked:
                    continue
                checked.add(relative)
                left, right = ROOT / relative, output / relative
                if left.suffix == '.json':
                    equal = json.loads(left.read_text(encoding='utf8')) == json.loads(right.read_text(encoding='utf8'))
                else:
                    with left.open(encoding='utf8', newline='') as a, right.open(encoding='utf8', newline='') as b:
                        equal = list(csv.reader(a)) == list(csv.reader(b))
                if not equal:
                    raise ValueError('Changed scientific figure data: ' + relative)
    print(json.dumps({'status': 'PASS', 'scientific_data_files': len(checked),
                      'retained_figure_integrity': 'PASS', 'generated_sections': 'CURRENT'}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
