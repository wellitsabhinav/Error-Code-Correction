import io
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from activity_stream import parse_vcd

HEADER = '''$timescale 1ps $end
$scope module top $end
$var wire 1 ! y $end
$var wire 1 ! alias $end
$var wire 2 a bus [1:0] $end
$upscope $end
$enddefinitions $end
'''


def test_known_edges_window_aliases_and_unknown_time():
    vcd = HEADER + '#0\n0!\nb00 a\n#10\n1!\nb11 a\n#12\n0!\n#20\nx!\n#25\nz!\n#30\n'
    result = parse_vcd(io.StringIO(vcd), 5, 30)
    y = next(x for x in result['signals'] if x['identifier'] == '!')
    assert y['binary_transitions'] == 2
    assert y['durations_ps'] == {'0': 13, '1': 2, 'x': 5, 'z': 5}
    assert y['min_pulse_ps'] == 2
    assert y['aliases'] == ['top.y', 'top.alias']
    assert len(result['signals']) == 3
    assert all(sum(s['durations_ps'].values()) == 25 for s in result['signals'])


def test_zero_duration_edges_are_not_observable_pulses():
    vcd = HEADER + '#0\n0!\nbx a\n#10\n1!\n0!\n#20\n'
    y = parse_vcd(iter(vcd.splitlines(True)))['signals'][0]
    assert y['binary_transitions'] == 2
    assert y['same_timestamp_binary_edges'] == 1
    assert y['observable_pulse_count'] == 0


def test_half_open_end_and_short_input_rejected():
    vcd = HEADER + '#0\n0!\nb0 a\n#10\n1!\n#20\n'
    r = parse_vcd(io.StringIO(vcd), 0, 10)
    assert r['signals'][0]['binary_transitions'] == 0
    with pytest.raises(ValueError, match='ends before'):
        parse_vcd(io.StringIO(vcd), 0, 30)


def test_nonmonotonic_and_no_timescale_rejected():
    with pytest.raises(ValueError, match='nonmonotonic'):
        parse_vcd(io.StringIO(HEADER + '#10\n0!\n#9\n'))
    with pytest.raises(ValueError, match='timescale missing'):
        parse_vcd(io.StringIO(HEADER.replace('$timescale 1ps $end', '') + '#10\n'))


def test_stream_matches_independent_complete_scalar_oracle():
    # Independent full-event calculation on the retained typical hazard window.
    p = Path(__file__).resolve().parents[1] / 'raw/qualification_ns/iopath_typ.vcd'
    if not p.exists():
        pytest.skip('qualification evidence not generated')
    lines = p.read_text().splitlines()
    code = next(line.split()[3] for line in lines if line.startswith('$var wire 1') and ' y ' in line)
    now, value, edges, events = 0, 'x', 0, []
    for line in lines:
        if line.startswith('#'):
            now = int(line[1:])
        elif line and line[0] in '01xz' and line[1:] == code:
            if 5000 <= now < 49000 and value in '01' and line[0] in '01' and value != line[0]:
                edges += 1
                events.append(now)
            value = line[0]
    stream = parse_vcd(iter(p.read_text().splitlines(True)), 5000, 49000)
    y = next(s for s in stream['signals'] if 'hazard_tb.y' in s['aliases'])
    assert edges == y['binary_transitions'] == 4
    assert events == [10300, 12100, 30300, 32100]
    assert y['durations_ps']['1'] == (events[1]-events[0]) + (events[3]-events[2]) == 3600
