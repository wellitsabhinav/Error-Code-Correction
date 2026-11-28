"""Deterministic input preparation and independent SECDED reference models.

This is functional preparation only, not P2-G03 energy characterization.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import itertools
import json
import random
import re
import statistics
from common import PHASE, ROOT, sha256, write_csv, write_json

MASK64 = (1 << 64) - 1
DATA_POS = tuple(p-1 for p in range(1, 72) if p & (p-1))
CHECK_POS = tuple(p-1 for p in range(1, 72) if not p & (p-1)) + (71,)
# Independent construction: odd columns sorted by weight, then integer value.
HSIAO_COLUMNS = tuple(sorted((x for x in range(1, 256) if x.bit_count() >= 3 and x.bit_count() % 2),
                             key=lambda x: (x.bit_count(), x))[:64]) + tuple(1 << i for i in range(8))


def encode(data, family='hamming'):
    if not 0 <= data <= MASK64:
        raise ValueError('payload exceeds 64 bits')
    if family == 'hamming':
        w = sum(((data >> i) & 1) << p for i, p in enumerate(DATA_POS))
        for bit in range(7):
            parity = sum((w >> (p-1)) & 1 for p in range(1, 72) if p & (1 << bit)) % 2
            w |= parity << ((1 << bit)-1)
        return w | ((w.bit_count() % 2) << 71)
    if family != 'hsiao':
        raise ValueError('unknown ECC family')
    syndrome = 0
    for i, column in enumerate(HSIAO_COLUMNS[:64]):
        if data >> i & 1:
            syndrome ^= column
    return data | syndrome << 64


def decode(word, family='hamming'):
    if not 0 <= word < 1 << 72:
        raise ValueError('received word exceeds 72 bits')
    mask, corrected, uncorrectable = 0, False, False
    if family == 'hamming':
        syndrome = 0
        for p in range(1, 72):
            if word >> (p-1) & 1:
                syndrome ^= p
        mismatch = word.bit_count() % 2
        detected = bool(syndrome or mismatch)
        if mismatch and syndrome <= 71:
            mask = 1 << (syndrome-1 if syndrome else 71)
            corrected = True
        elif syndrome and not mismatch:
            uncorrectable = True
        fixed = word ^ mask
        data = sum(((fixed >> p) & 1) << i for i, p in enumerate(DATA_POS))
    elif family == 'hsiao':
        syndrome = 0
        for p, column in enumerate(HSIAO_COLUMNS):
            if word >> p & 1:
                syndrome ^= column
        if syndrome in HSIAO_COLUMNS:
            mask = 1 << HSIAO_COLUMNS.index(syndrome)
            corrected = True
        uncorrectable = bool(syndrome and not corrected)
        detected = corrected or uncorrectable
        fixed, data = word ^ mask, (word ^ mask) & MASK64
    else:
        raise ValueError('unknown ECC family')
    return {'data': data, 'corrected_word': fixed, 'detected': int(detected),
            'corrected': int(corrected), 'uncorrectable': int(uncorrectable)}


def payloads(regime, count, seed):
    rng, previous = random.Random(seed), 0
    for i in range(count):
        if regime == 'uniform':
            value = rng.getrandbits(64)
        elif regime == 'alternating':
            value = MASK64 if i % 2 else 0
        elif regime in ('low_hd', 'medium_hd', 'high_hd'):
            hd = {'low_hd': 4, 'medium_hd': 32, 'high_hd': 60}[regime]
            value = previous ^ sum(1 << b for b in rng.sample(range(64), hd))
        elif regime == 'identical':
            value = 0xA55AA55AA55AA55A
        elif regime == 'counter':
            value = i & MASK64
        elif regime == 'spatial':
            shift = (i // 4) % 64
            base = 0x00000000FFFFFFFF
            value = ((base << shift) | (base >> (64-shift if shift else 64))) & MASK64
        else:
            raise ValueError('unknown data regime')
        yield value
        previous = value


def injection_mask(regime, family, index, rng):
    data_positions = DATA_POS if family == 'hamming' else tuple(range(64))
    checks = CHECK_POS if family == 'hamming' else tuple(range(64, 72))
    if regime == 'none':
        return 0
    if regime in ('single_data', 'burst_correctable'):
        return 1 << rng.choice(data_positions)
    if regime == 'single_check':
        return 1 << rng.choice(checks)
    if regime in ('double', 'burst_uncorrectable'):
        return sum(1 << p for p in rng.sample(range(72), 2))
    if regime == 'adjacent_multi':
        return 7 << rng.randrange(70)
    if regime == 'nonadjacent_multi':
        return sum(1 << p for p in rng.sample(range(0, 72, 3), 3))
    raise ValueError('unknown error regime')


def verify_hsiao_identity():
    path = ROOT / 'green_ecc_physical_simulation/rtl/hsiao_secded_72_64/hsiao_secded_72_64_v2_algorithmic_decoder.sv'
    found = [int(v, 16) for _, v in sorted(re.findall(r'column_match\[(\d+)\]\s*=\s*\(syndrome == 8\x27h([0-9a-f]+)\)', path.read_text()), key=lambda p: int(p[0]))]
    if tuple(found) != HSIAO_COLUMNS:
        raise ValueError('independently constructed Hsiao columns disagree with actual decoder')
    return {'columns': list(HSIAO_COLUMNS), 'decoder_sha256': sha256(path), 'status': 'MATCH'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--count', type=int, default=1000)
    p.add_argument('--seed', type=int, default=17)
    p.add_argument('--vectors', action='store_true', help='Retain a bounded 100-vector representative RTL test file per family')
    a = p.parse_args()
    if a.count < 2 or a.count > 100000:
        raise ValueError('count outside declared stages')
    identity = verify_hsiao_identity()
    characteristics, errors = [], []
    regimes = ('uniform', 'alternating', 'low_hd', 'medium_hd', 'high_hd', 'identical', 'counter', 'spatial')
    for regime in regimes:
        values = list(payloads(regime, a.count, a.seed))
        hd = [(b ^ c).bit_count() for b, c in zip(values, values[1:])]
        characteristics.append({'regime': regime, 'count': len(values), 'seed': a.seed, 'hd_pairs': len(hd),
                                'mean_hd': statistics.mean(hd), 'min_hd': min(hd), 'max_hd': max(hd),
                                'hd_histogram_json': json.dumps({str(k): hd.count(k) for k in sorted(set(hd))}),
                                'trace_sha256': hashlib.sha256(b''.join(v.to_bytes(8, 'little') for v in values)).hexdigest(),
                                'energy_status': 'NOT_MEASURED_P2_G00_BLOCKED'})
    values = list(payloads('uniform', a.count, a.seed))
    for family in ('hamming', 'hsiao'):
        for regime in ('none', 'single_data', 'single_check', 'double', 'adjacent_multi', 'nonadjacent_multi', 'burst_correctable', 'burst_uncorrectable'):
            for fraction in (0, 0.0001, 0.001, 0.01, 0.1, 1):
                rng = random.Random(a.seed)
                n = round(a.count * fraction) if regime != 'none' else 0
                indices = set(range(n)) if regime.startswith('burst') else set(rng.sample(range(a.count), n))
                actual = corrected = detected = mismatched = 0
                for i, value in enumerate(values):
                    word = encode(value, family)
                    mask = injection_mask(regime, family, i, rng) if i in indices else 0
                    output = decode(word ^ mask, family)
                    actual += bool(mask)
                    corrected += output['corrected']
                    detected += output['detected']
                    mismatched += output['data'] != value
                    if mask.bit_count() <= 1 and output['data'] != value:
                        raise ValueError('single correction guarantee violated')
                    if mask.bit_count() == 2 and output['uncorrectable'] != 1:
                        raise ValueError('double detection guarantee violated')
                errors.append({'family': family, 'regime': regime, 'requested_fraction': fraction,
                               'count': a.count, 'actual_injected': actual, 'actual_fraction': actual / a.count,
                               'corrected_flags': corrected, 'detected_flags': detected, 'payload_mismatches': mismatched,
                               'guarantee': 'UNSUPPORTED_WEIGHT_3_OBSERVATION' if regime.endswith('_multi') else 'WITHIN_SECDED_GUARANTEE',
                               'rare_error_sample': 'UNDERPOWERED' if 0 < fraction < 1 and actual < 20 else 'DESCRIPTIVE_ONLY',
                               'conditional_energy_pj': None, 'status': 'SOFTWARE_REFERENCE_ONLY'})
        if a.vectors:
            vectors = []
            for i, value in enumerate(values[:100]):
                word = encode(value, family)
                # Bounded clean/single/double sample; exhaustive mask coverage is in the software tests.
                mask = 0 if i % 4 == 0 else (1 << (i % 72) if i % 4 == 1 else
                        ((1 << (i % 72)) | (1 << ((i+1) % 72))))
                output = decode(word ^ mask, family)
                vectors.append(f'{value:016x} {word ^ mask:018x} {word:018x} {output["data"]:016x} {output["detected"]} {output["corrected"]} {output["uncorrectable"]}')
            path = PHASE / 'workloads' / f'{family}_smoke.txt'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('\n'.join(vectors) + '\n', encoding='utf-8', newline='\n')
    write_csv(PHASE / 'processed/workload_characteristics.csv', characteristics)
    write_csv(PHASE / 'processed/error_conditioned_energy.csv', errors)
    write_json(PHASE / 'manifests/workload_reference.json', {'count': a.count, 'seed': a.seed, 'hsiao_identity': identity,
               'classification': 'Functional preparation; no P2-G03 energy experiment launched.',
               'sampling': 'Fixed exact rounded injection count; contiguous burst prefix or seeded uniform positions. Stress conditions, not SRAM probabilities.'})
    print(json.dumps({'workloads': len(characteristics), 'reference_conditions': len(errors), 'energy_measurements': 0}))


if __name__ == '__main__':
    main()
