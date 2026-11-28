import json
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from common import checkpoint, sha256, storage_check
from storage_manager import cleanup, resolve_scratch


def test_cleanup_preserves_unknown_and_incomplete_files(tmp_path):
    scratch = tmp_path / 'scratch'
    scratch.mkdir()
    user = scratch / 'user.txt'
    user.write_text('user evidence')
    manifest = tmp_path / 'experiments/run/manifest.json'
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({'status': 'STARTED', 'disposable_temporary': []}))
    with pytest.raises(ValueError, match='incomplete'):
        cleanup(manifest, tmp_path, execute=True)
    assert user.read_text() == 'user evidence'
    with pytest.raises(ValueError, match='outside'):
        resolve_scratch('../user.txt', tmp_path)


def test_cleanup_only_exact_verified_file_and_retained_hash(tmp_path):
    (tmp_path / 'scratch').mkdir()
    disposable = tmp_path / 'scratch/temp.txt'
    disposable.write_text('temporary')
    evidence = tmp_path / 'summary.json'
    evidence.write_text('retained')
    manifest = tmp_path / 'experiments/run/manifest.json'
    manifest.parent.mkdir(parents=True)
    data = {'status': 'COMPLETE', 'retained_artifacts': [{'path': 'summary.json', 'sha256': sha256(evidence)}],
            'disposable_temporary': [{'path': 'scratch/temp.txt', 'sha256': sha256(disposable),
                                      'verified_temporary': True, 'unique_scientific_evidence': False}]}
    manifest.write_text(json.dumps(data))
    assert len(cleanup(manifest, tmp_path)) == 1
    assert disposable.exists()
    cleanup(manifest, tmp_path, execute=True)
    assert not disposable.exists() and evidence.exists()


def test_storage_reserve_blocks_oversized_job(tmp_path):
    with pytest.raises(RuntimeError, match='BLOCKED_STORAGE'):
        storage_check(tmp_path, projected_bytes=10**30)
