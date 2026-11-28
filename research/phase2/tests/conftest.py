"""Local scratch fixture compatible with the repository's disabled tmpdir plugin."""
from pathlib import Path
import uuid
import pytest


@pytest.fixture
def tmp_path():
    path = Path(__file__).resolve().parents[1] / 'scratch/tests' / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=False)
    return path
