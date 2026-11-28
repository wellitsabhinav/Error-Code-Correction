"""Streaming VCD bit activity. Aliases share one accumulator. No pulse is called a glitch.

Window is half-open [start_ps,end_ps). A transition at start is included only if
the preceding value is known. Initialization and X/Z changes are not binary edges.
Widths require two binary transitions; partial boundary pulses are excluded.
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from common import write_json

UNITS = {'s': 10**12, 'ms': 10**9, 'us': 10**6, 'ns': 1000, 'ps': 1, 'fs': 0.001}


@dataclass
class Bit:
    value: str = 'x'
    time_ps: float = 0
    rise: int = 0
    fall: int = 0
    unknown_changes: int = 0
    same_timestamp_binary_edges: int = 0
    durations: dict = field(default_factory=lambda: dict.fromkeys('01xz', 0.0))
    last_edge_ps: float | None = None
    pulse_count: int = 0
    min_pulse_ps: float | None = None
    max_pulse_ps: float | None = None
    pulse_samples_ps: list = field(default_factory=list)

    def update(self, value, now, start, end):
        right = min(now, end) if end is not None else now
        left = max(self.time_ps, start)
        if right > left:
            self.durations[self.value] += right - left
        in_window = now >= start and (end is None or now < end)
        if value != self.value:
            if in_window and self.value in '01' and value in '01':
                self.rise += value == '1'
                self.fall += value == '0'
                if self.last_edge_ps is not None:
                    width = now - self.last_edge_ps
                    if width == 0:
                        self.same_timestamp_binary_edges += 1
                    elif self.last_edge_ps >= start:
                        self.pulse_count += 1
                        self.min_pulse_ps = width if self.min_pulse_ps is None else min(width, self.min_pulse_ps)
                        self.max_pulse_ps = width if self.max_pulse_ps is None else max(width, self.max_pulse_ps)
                        if len(self.pulse_samples_ps) < 32:
                            self.pulse_samples_ps.append(width)
                self.last_edge_ps = now
            else:
                if in_window:
                    self.unknown_changes += 1
                self.last_edge_ps = None
            self.value = value
        self.time_ps = now


def parse_vcd(lines, start_ps=0, end_ps=None, max_signals=1000000):
    if start_ps < 0 or (end_ps is not None and end_ps <= start_ps):
        raise ValueError('invalid observation window')
    scopes, signals, factor, now, header, pending = [], {}, None, 0, True, ''
    last_tick = 0
    for raw in lines:
        line = raw.strip()
        if header:
            pending += ' ' + line
            while (terminator := re.search(r'\$end(?=\s|$)', pending)) is not None:
                declaration, pending = pending[:terminator.start()], pending[terminator.end():]
                words = declaration.split()
                if not words:
                    continue
                if words[0] == '$timescale':
                    m = re.fullmatch(r'(\d+)\s*(s|ms|us|ns|ps|fs)', ''.join(words[1:]))
                    if not m:
                        raise ValueError('unsupported timescale')
                    factor = int(m[1]) * UNITS[m[2]]
                elif words[0] == '$scope':
                    scopes.append(words[2])
                elif words[0] == '$upscope':
                    scopes.pop()
                elif words[0] == '$var':
                    width, code = int(words[2]), words[3]
                    if words[1] in ('real', 'realtime', 'string'):
                        raise ValueError('non-logic VCD variable')
                    name = '.'.join(scopes + [''.join(words[4:])])
                    if code in signals:
                        if width != signals[code]['width']:
                            raise ValueError('inconsistent alias width')
                        signals[code]['aliases'].append(name)
                    else:
                        if len(signals) >= max_signals or width > 65536:
                            raise ValueError('signal budget exceeded')
                        signals[code] = {'width': width, 'aliases': [name], 'bits': [Bit() for _ in range(width)]}
                elif words[0] == '$enddefinitions':
                    if factor is None:
                        raise ValueError('VCD timescale missing')
                    header = False
            continue
        if not line or line.startswith('$'):
            continue
        if line.startswith('#'):
            tick = int(line[1:])
            if tick < last_tick:
                raise ValueError('nonmonotonic VCD')
            last_tick, now = tick, tick * factor
            if end_ps is not None and now >= end_ps:
                break
            continue
        if line[0] in 'bB':
            value, code = line[1:].split()
            value = value.lower()
        elif line[0] in '01xXzZ':
            value, code = line[0].lower(), line[1:]
        else:
            raise ValueError('unsupported VCD event: ' + line[:60])
        if code not in signals:
            raise ValueError('event for undeclared VCD identifier')
        signal = signals[code]
        if any(v not in '01xz' for v in value) or len(value) > signal['width']:
            raise ValueError('invalid logic vector')
        extension = value[0] if value[0] in 'xz' else '0'
        value = value.rjust(signal['width'], extension)
        for bit, v in zip(signal['bits'], reversed(value)):
            bit.update(v, now, start_ps, end_ps)
    if header:
        raise ValueError('incomplete VCD header')
    finish = end_ps if end_ps is not None else now
    if finish > now:
        raise ValueError('VCD ends before requested window')
    if finish <= start_ps:
        raise ValueError('empty VCD observation interval')
    records = []
    for code, s in signals.items():
        for index, b in enumerate(s['bits']):
            b.update(b.value, finish, start_ps, finish)
            records.append({'identifier': code, 'bit': index, 'aliases': s['aliases'], 'rising': b.rise,
                            'falling': b.fall, 'binary_transitions': b.rise + b.fall,
                            'unknown_changes': b.unknown_changes, 'durations_ps': b.durations,
                            'same_timestamp_binary_edges': b.same_timestamp_binary_edges,
                            'observable_pulse_count': b.pulse_count, 'min_pulse_ps': b.min_pulse_ps,
                            'max_pulse_ps': b.max_pulse_ps, 'pulse_samples_ps': b.pulse_samples_ps})
    return {'schema_version': 1, 'start_ps': start_ps, 'end_ps': finish,
            'interval_ps': finish - start_ps, 'resolution_ps': factor, 'signals': records,
            'pulse_definition': 'Two consecutive binary transitions with positive time separation; pulse candidates, not automatically glitches.',
            'alias_policy': 'One physical VCD identifier counted once; aliases retained.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', required=True, help='VCD, VCD.gz, or - for a pipe')
    p.add_argument('--output', required=True)
    p.add_argument('--start-ps', type=float, default=0)
    p.add_argument('--end-ps', type=float)
    a = p.parse_args()
    if a.input == '-':
        result = parse_vcd(sys.stdin, a.start_ps, a.end_ps)
    else:
        opener = gzip.open if a.input.endswith('.gz') else open
        with opener(a.input, 'rt', encoding='utf-8') as f:
            result = parse_vcd(f, a.start_ps, a.end_ps)
    write_json(a.output, result)
    print(json.dumps({'bits': len(result['signals']), 'interval_ps': result['interval_ps']}))


if __name__ == '__main__':
    main()
