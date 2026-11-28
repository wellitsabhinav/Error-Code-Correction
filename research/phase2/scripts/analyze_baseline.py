"""Read frozen estimates and produce separate, explicitly historical derivations."""
from __future__ import annotations
import csv
import json
import statistics
from common import PHASE, ROOT, sha256, write_csv, write_json


def load_csv(relative):
    with (ROOT / relative).open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def energy_pj(power_w, interval_ps, completed):
    if power_w < 0 or interval_ps <= 0 or completed <= 0:
        raise ValueError('invalid power/interval/completed count')
    return power_w * interval_ps / completed


def paired_effects(rows, metric, first, second):
    a = {int(r['seed']): float(r[metric]) for r in rows if r['architecture'] == first}
    b = {int(r['seed']): float(r[metric]) for r in rows if r['architecture'] == second}
    common = sorted(a.keys() & b.keys())
    vals = [100 * (b[s] / a[s] - 1) for s in common]
    return {'metric': metric, 'seeds': common, 'paired_percent': vals,
            'mean_percent': statistics.mean(vals), 'median_percent': statistics.median(vals),
            'sample_sd_percent': statistics.stdev(vals), 'min_percent': min(vals), 'max_percent': max(vals),
            'ci': None, 'ci_reason': 'Descriptive deterministic seeds; no random-population inference predeclared.'}


def main():
    source = 'campaigns/date_2027_breadth_remediation/analysis/B_power_components_per_seed.csv'
    data = load_csv(source)
    result = []
    for r in data:
        interval, count, power = float(r['trace_total_time_ps']), int(r['useful_operations']), float(r['total_power_w'])
        e = energy_pj(power, interval, count)
        if abs(e - float(r['energy_per_op_pj'])) > 1e-8:
            raise ValueError('historical energy reconstruction failed')
        result.append({'seed': r['seed'], 'architecture': r['architecture'], 'method': 'A_historical_reference',
                       'power_w': power, 'interval_ps': interval, 'completed_operations': count,
                       'energy_per_op_pj': e, 'steady_state_II_over_f_pj': power * 10000,
                       'finite_window_overhead_percent': 100 * (interval / (count * 10000) - 1),
                       'source': source, 'source_sha256': sha256(ROOT / source), 'source_power_report_sha256': r['power_report_sha256'],
                       'classification': 'RECONSTRUCTED_HISTORICAL_ESTIMATE_NOT_NEW_PHYSICAL_MEASUREMENT'})
    write_csv(PHASE / 'processed/historical_power_reanalysis.csv', result)
    metrics = ['internal_power_w', 'switching_power_w', 'leakage_power_w', 'total_power_w',
               'energy_per_op_pj', 'sequential_total_power_w', 'combinational_total_power_w', 'clock_total_power_w']
    effects = [paired_effects(data, m, 'secded_comb', 'secded_pipe') for m in metrics]
    summaries = {}
    for arch in ('secded_comb', 'secded_pipe'):
        records = [r for r in data if r['architecture'] == arch]
        summaries[arch] = {m: statistics.mean(float(r[m]) for r in records) for m in metrics}
    write_json(PHASE / 'processed/historical_statistics.json', {'effects': effects, 'architecture_means': summaries,
               'paired_unit': 'physical placement seed', 'n': 5, 'source_sha256': sha256(ROOT / source)})
    # Schemas retain missing measurements as empty CSV fields, never zero.
    structural = load_csv('campaigns/date_2027_breadth_remediation/analysis/A_structural_pair_per_seed.csv')
    comparison = []
    for architecture in ('secded_comb', 'secded_pipe', 'hsiao_flat', 'hsiao_hierarchical'):
        for seed in (11, 13, 17, 19, 23):
            for method in ('A', 'B', 'C'):
                row = {'architecture': architecture, 'seed': seed, 'method': method,
                       'status': 'BLOCKED_P2_G00', 'internal_power_w': None, 'switching_power_w': None,
                       'leakage_power_w': None, 'clock_power_w': None, 'sequential_power_w': None,
                       'combinational_power_w': None, 'total_power_w': None, 'energy_per_completed_op_pj': None,
                       'completed_operations': None, 'interval_ps': None, 'throughput_ops_per_s': None,
                       'latency_cycles': 3 if architecture == 'secded_pipe' else 1, 'timing_slack_ns': None,
                       'annotation_coverage_percent': None, 'internal_events': None, 'runtime_s': None,
                       'peak_storage_bytes': None, 'relative_deviation_vs_C_percent': None,
                       'historical_energy_reference_pj': None}
                if method == 'A':
                    row['status'] = 'HISTORICAL_REFERENCE_ONLY_WINDOW_NOT_MATCHED'
                    candidates = data if architecture.startswith('secded') else structural
                    name = architecture if architecture.startswith('secded') else 'A_' + architecture
                    old = next(r for r in candidates if r['architecture'] == name and int(r['seed']) == seed)
                    row['historical_energy_reference_pj'] = float(old['energy_per_op_pj'])
                comparison.append(row)
    write_csv(PHASE / 'processed/power_method_comparison.csv', comparison)
    rankings = []
    for a, b, pool in [('secded_comb', 'secded_pipe', data), ('A_hsiao_flat', 'A_hsiao_hierarchical', structural)]:
        for seed in (11, 13, 17, 19, 23):
            er = {r['architecture']: float(r['energy_per_op_pj']) for r in pool if int(r['seed']) == seed}
            rankings.append({'seed': seed, 'first': a, 'second': b, 'historical_A_lower_energy': a if er[a] < er[b] else b,
                             'B_lower_energy': None, 'C_lower_energy': None, 'ranking_agreement': None,
                             'ranking_reversal': None, 'status': 'NO_QUALIFIED_THREE_WAY_COMPARISON'})
    write_csv(PHASE / 'processed/architecture_ranking_comparison.csv', rankings)
    mapped = json.loads((ROOT / 'campaigns/date_2027_breadth_remediation/synthesis/A_synthesis_structural_comparison.json').read_text())
    cell_rows = []
    for arch, key in [('hsiao_flat', 'baseline'), ('hsiao_hierarchical', 'new_hierarchical')]:
        for cell, count in mapped[key]['cell_type_histogram'].items():
            cell_rows.append({'architecture': arch, 'cell_type': cell, 'count': count,
                              'stage': 'HISTORICAL_COMMON_SYNTHESIS_NOT_ROUTED', 'mapped_netlist_sha256': mapped[key]['mapped_netlist_sha256']})
    write_csv(PHASE / 'processed/cell_distribution.csv', cell_rows)
    write_csv(PHASE / 'processed/net_capacitance.csv', [], ['net', 'parasitic_capacitance_pf', 'pin_capacitance_pf', 'capacitance_boundary', 'source_sha256'])
    evidence = [
        {'hypothesis': 'H1_glitch', 'classification': 'INCONCLUSIVE', 'evidence': 'Synthetic IOPATH qualification only; no matched routed internal switching.'},
        {'hypothesis': 'H2_capacitance', 'classification': 'INCONCLUSIVE', 'evidence': 'DATE SPEF absent locally; no capacitance-weighted measured transitions.'},
        {'hypothesis': 'H3_mapping', 'classification': 'PARTIALLY SUPPORTED', 'evidence': 'Historical flat/hierarchical common mapped counts 1244/1254; XOR/XNOR 350/343; no causal energy attribution.'},
        {'hypothesis': 'H4_clock_sequential_overhead', 'classification': 'SUPPORTED', 'evidence': 'Within historical Method A: sequential +70.861003%, clock +74.337936%; delay-aware magnitude unresolved.'},
        {'hypothesis': 'H5_propagation_bias', 'classification': 'INCONCLUSIVE', 'evidence': 'Methods B and C unavailable; historical -49.481332% switching cannot identify bias.'},
        {'hypothesis': 'H6_normalization', 'classification': 'NOT SUPPORTED', 'evidence': 'Within the historical pair both cases use 100MHz and II=1 with the same 0.01% finite trace overhead. Frequency normalization does not explain that paired reduction; other operating points remain unresolved.'}]
    write_csv(PHASE / 'processed/mechanism_evidence.csv', evidence)
    print(json.dumps({'rows_reconstructed': len(result), 'mean_energy_pj': {k:v['energy_per_op_pj'] for k,v in summaries.items()},
                      'switching_effect_percent': effects[1]['mean_percent']}, indent=2))


if __name__ == '__main__':
    main()
