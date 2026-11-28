"""Record required existing checks with bounded runtime; never rewrite baselines."""
from __future__ import annotations
import argparse
import os
import sys
from common import PHASE, ROOT, run_command, write_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--timeout', type=int, default=120)
    a = p.parse_args()
    out = PHASE / 'raw/validation'
    out.mkdir(parents=True, exist_ok=True)
    commands = [
        ('make', ['make']), ('make_test', ['make', 'test']),
        ('pytest', [sys.executable, '-m', 'pytest', '-q']),
        ('artifact', [sys.executable, 'scripts/check_artifact.py']),
        ('iscas', [sys.executable, 'scripts/reproduce_iscas.py', '--check']),
        ('documentation', [sys.executable, 'scripts/check_documentation.py']),
        ('phase2', [sys.executable, '-m', 'pytest', '-q', 'research/phase2/tests']),
        ('diff', ['git', 'diff', '--check'])]
    results = []
    # Do not cascade thousands of failures from absent sparse-checkout evidence.
    # The command and stop policy are explicit; interrupted broad checks are not PASS.
    os.environ['PYTEST_ADDOPTS'] = '--maxfail=5 --tb=short'
    for label, argv in commands:
        r = run_command(argv, ROOT, out / (label + '.log'), timeout=a.timeout)
        results.append({'check': label, **r})
        write_json(out / 'results.json', {'checks': results, 'pytest_stop_policy': '--maxfail=5; full-suite success not asserted after early failure'})
        print(label, r['status'], r['exit_code'], flush=True)


if __name__ == '__main__':
    main()
