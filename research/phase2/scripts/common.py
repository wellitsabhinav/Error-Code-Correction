"""Small, standard-library-only provenance and resource helpers."""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

PHASE = Path(__file__).resolve().parents[1]
ROOT = PHASE.parents[1]


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.pending')
    temp.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    temp.replace(path)


def write_csv(path, rows, fields=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def storage_check(path, projected_bytes=0, reserve_gib=3):
    if projected_bytes < 0 or reserve_gib < 0:
        raise ValueError('negative storage estimate/reserve')
    usage = shutil.disk_usage(path)
    if usage.free < projected_bytes + reserve_gib * 2**30:
        raise RuntimeError('BLOCKED_STORAGE_BUDGET')
    return {'free_bytes': usage.free, 'total_bytes': usage.total, 'projected_bytes': projected_bytes,
            'reserve_bytes': int(reserve_gib * 2**30)}


def checkpoint(run_id, contract, seconds=14400):
    """A resume retains the first deadline and rejects a changed contract."""
    if not run_id or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in run_id):
        raise ValueError('invalid run ID')
    path = PHASE / 'experiments' / run_id / 'manifest.json'
    identity = hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()
    if path.exists():
        data = json.loads(path.read_text(encoding='utf-8'))
        if data['contract_sha256'] != identity:
            raise RuntimeError('CONTRACT_CHANGED_ON_RESUME')
    else:
        start = time.time()
        data = {'run_id': run_id, 'contract_sha256': identity, 'contract': contract,
                'start_epoch': start, 'deadline_epoch': start + seconds,
                'status': 'STARTED', 'commands': []}
        write_json(path, data)
    if time.time() >= data['deadline_epoch']:
        raise RuntimeError('CAMPAIGN_DEADLINE_EXCEEDED')
    return path, data


def run_command(argv, cwd, log_path, timeout=120):
    """No shell interpolation; capture failures and timeouts as evidence."""
    storage = storage_check(cwd, 16 * 2**20)
    started = time.monotonic()
    try:
        result = subprocess.run([str(x) for x in argv], cwd=cwd, capture_output=True,
                                text=True, errors='replace', timeout=timeout)
        rc, output, status = result.returncode, result.stdout + result.stderr, 'COMPLETED'
    except subprocess.TimeoutExpired as e:
        rc, status = None, 'TIMEOUT'
        output = str(e)
    except OSError as e:
        rc, status, output = None, 'TOOL_UNAVAILABLE', str(e)
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    Path(log_path).write_text(output, encoding='utf-8', newline='\n')
    return {'argv': [str(x) for x in argv], 'cwd': str(cwd), 'exit_code': rc,
            'status': status, 'runtime_seconds': time.monotonic() - started,
            'log': str(log_path), 'log_sha256': sha256(log_path), 'storage_before': storage,
            'utc': datetime.now(timezone.utc).isoformat()}
