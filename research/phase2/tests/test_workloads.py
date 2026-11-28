import itertools
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from workloads import encode, decode, payloads, verify_hsiao_identity
from analyze_baseline import energy_pj


@pytest.mark.parametrize('family', ['hamming', 'hsiao'])
def test_all_single_positions_and_all_double_positions(family):
    payload = 0xA51BFFFF87654321
    code = encode(payload, family)
    assert decode(code, family)['data'] == payload
    for i in range(72):
        d = decode(code ^ (1 << i), family)
        assert d == {'data': payload, 'corrected_word': code, 'detected': 1, 'corrected': 1, 'uncorrectable': 0}
    for i, j in itertools.combinations(range(72), 2):
        d = decode(code ^ (1 << i) ^ (1 << j), family)
        assert d['uncorrectable'] == d['detected'] == 1
        assert d['corrected'] == 0


def test_hsiao_matrix_and_deterministic_activity():
    assert verify_hsiao_identity()['status'] == 'MATCH'
    for label, expected in [('low_hd', 4), ('medium_hd', 32), ('high_hd', 60), ('identical', 0), ('alternating', 64)]:
        a = list(payloads(label, 100, 17))
        assert a == list(payloads(label, 100, 17))
        assert all((x ^ y).bit_count() == expected for x, y in zip(a, a[1:]))


def test_energy_units_and_invalid_counts():
    assert energy_pj(0.01, 1000000, 100) == 100
    with pytest.raises(ValueError):
        energy_pj(0.01, 1000000, 0)
