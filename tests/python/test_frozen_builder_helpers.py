"""Cross-platform comparison must tolerate rounding, never missing evidence."""
import pytest
from tests.frozen_builder_helpers import equivalent_value


def test_statistics_last_bit_rounding_is_equivalent():
    assert equivalent_value({'mean': 3.9627120000000002}, {'mean': 3.962712})


@pytest.mark.parametrize('changed', [None, 0, True, 1.01, float('nan')])
def test_missing_changed_or_invalid_measurements_are_rejected(changed):
    assert not equivalent_value({'mean': 1.0}, {'mean': changed})


def test_record_identity_and_sequence_remain_strict():
    assert not equivalent_value(['seed13', 'seed17'], ['seed17', 'seed13'])
