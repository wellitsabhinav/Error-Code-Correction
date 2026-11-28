from pathlib import Path
import sys
import tempfile

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def scratch_path():
    root = Path(__file__).resolve().parents[3] / "tmp"
    root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="phase2_plus_test_", dir=root) as directory:
        yield Path(directory)
