#!/usr/bin/env python3
"""Render the GREENS research flow as a small, readable vector diagram."""
import argparse
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = Path(__file__).resolve().parents[1]


def generate(output: Path, preview: Path | None = None) -> None:
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                         'svg.hashsalt': 'GREENS_RESEARCH_FLOW_V1', 'svg.fonttype': 'none'})
    fig, ax = plt.subplots(figsize=(12, 4.1))
    fig.subplots_adjust(left=0.025, right=0.975, top=0.96, bottom=0.03)
    ax.set(xlim=(0, 12), ylim=(0, 4))
    ax.axis('off')
    stages = [
        ('Qualify the hardware', '#e9f1fa', '#315a83',
         ['Declare W1 / W2 service', 'Bind the exact RTL identity', 'Verify faults and protocol']),
        ('Implement the boundary', '#e7f4ef', '#27634d',
         ['Match macro, PVT, clock, seeds', 'Synthesize, place and route', 'Admit route + setup + hold']),
        ('Derive the decision', '#f6effb', '#674586',
         ['Join operation VCD + SPEF', 'Normalize ECC-logic energy', 'Compare the workload mix']),
    ]
    for index, (title, fill, edge, labels) in enumerate(stages):
        x = 0.1 + 4 * index
        ax.add_patch(FancyBboxPatch((x, 0.85), 3.7, 2.9, boxstyle='round,pad=0.02,rounding_size=0.12',
                                   linewidth=1.2, edgecolor=edge, facecolor=fill))
        ax.text(x+1.85, 3.38, title, ha='center', va='center', fontsize=13, weight='bold', color=edge)
        for row, label in enumerate(labels):
            y = 2.78 - 0.68 * row
            ax.text(x+1.85, y, label, ha='center', va='center', color='#182c3d')
            if row < 2:
                ax.add_patch(FancyArrowPatch((x+1.85, y-0.2), (x+1.85, y-0.45),
                                            arrowstyle='-|>', mutation_scale=10, color=edge))
        if index < 2:
            ax.add_patch(FancyArrowPatch((x+3.77, 2.25), (x+3.99, 2.25), arrowstyle='-|>',
                                        mutation_scale=16, linewidth=1.3, color='#34495e'))
    ax.text(6, 0.47, 'Missing or failed evidence stays excluded; negative results are retained.',
            ha='center', va='center', color='#713d32', fontsize=11)
    ax.text(6, 0.14, 'ECC semantics  →  hardware identity  →  physical evidence  →  conditional preference',
            ha='center', va='center', color='#34495e', fontsize=10)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, metadata={'Date': None})
    output.write_bytes(('\n'.join(line.rstrip() for line in output.read_text(encoding='utf8').splitlines())+'\n').encode('utf8'))
    if preview:
        preview.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(preview, dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'docs/figures/greens_research_flow.svg')
    parser.add_argument('--preview', type=Path)
    args = parser.parse_args()
    if any(p and p.resolve().is_relative_to(ROOT/'campaigns') for p in (args.output, args.preview)):
        parser.error('Output must be outside frozen campaigns')
    generate(args.output, args.preview)


if __name__ == '__main__':
    main()
