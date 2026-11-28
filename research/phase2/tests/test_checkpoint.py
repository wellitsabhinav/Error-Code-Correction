import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import common


def test_resume_preserves_original_deadline_and_rejects_changed_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(common, 'PHASE', tmp_path)
    monkeypatch.setattr(common.time, 'time', lambda: 1000)
    path, first = common.checkpoint('bounded-run', {'seed': 11}, seconds=10)
    monkeypatch.setattr(common.time, 'time', lambda: 1005)
    _, resumed = common.checkpoint('bounded-run', {'seed': 11}, seconds=100000)
    assert resumed['deadline_epoch'] == first['deadline_epoch'] == 1010
    with pytest.raises(RuntimeError, match='CONTRACT_CHANGED'):
        common.checkpoint('bounded-run', {'seed': 13})
    monkeypatch.setattr(common.time, 'time', lambda: 1011)
    with pytest.raises(RuntimeError, match='DEADLINE_EXCEEDED'):
        common.checkpoint('bounded-run', {'seed': 11}, seconds=100000)


def test_cleanup_rejects_symlink_even_with_inside_target(tmp_path):
    from storage_manager import resolve_scratch
    scratch = tmp_path / 'scratch'
    scratch.mkdir()
    target = scratch / 'user.txt'
    target.write_text('preserve')
    link = scratch / 'alias.txt'
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip('symlink privilege not available on this host')
    with pytest.raises(ValueError, match='linked'):
        resolve_scratch('scratch/alias.txt', tmp_path)
    assert target.read_text() == 'preserve'
