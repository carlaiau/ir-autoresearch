#!/usr/bin/env python3
"""Render README figures from the sourced metric snapshot.

Run: python3 tools/plot_jev_results.py
Dependency: matplotlib (generated with 3.11.2). Source URLs and manifest hashes
are stored with each row in docs/metrics/jev-reranking-chart.json.
"""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator, FormatStrFormatter

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'docs/metrics/jev-reranking-chart.json'

def main():
    rows = json.loads(DATA.read_text())['rows']
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                         'svg.fonttype': 'none', 'svg.hashsalt': 'jev-results'})
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.9), sharey=True)
    fig.set_facecolor('white')
    fig.subplots_adjust(left=.245, right=.965, top=.73, bottom=.22, wspace=.19)
    fig.text(.04, .93, 'JEV reranking: relevance at a glance', fontsize=22, weight='bold', color='#172b42')
    fig.text(.04, .865, 'Same WSJ/TREC candidates • 50 topics • Higher is better', fontsize=12, color='#526176')
    for ax, metric, title, limit, step in zip(axes, ['map', 'P_10'], ['MAP', 'P@10'], [.35, .70], [.1, .2]):
        values = [r['metrics'][metric] for r in rows]
        assert all(0 <= value <= 1 for value in values)
        ax.set_facecolor('white')
        ax.barh(range(len(rows)), values, color=[r['color'] for r in rows], height=.56, zorder=3)
        ax.set_xlim(0, limit)
        ax.set_title(title, loc='left', fontsize=16, weight='bold', color='#172b42', pad=17)
        ax.set_yticks(range(len(rows)), [r['label'] for r in rows])
        ax.tick_params(axis='both', length=0, labelcolor='#34465b', pad=10)
        ax.xaxis.set_major_locator(MultipleLocator(step))
        ax.xaxis.set_major_formatter(FormatStrFormatter('%.1f'))
        ax.grid(axis='x', color='#e5eaf0', linewidth=.8, zorder=0)
        for spine in ax.spines.values(): spine.set_visible(False)
        for y, value in enumerate(values):
            ax.text(value + limit*.022, y, f'{value:.4f}', va='center', fontsize=11,
                    color='#172b42', weight='bold' if y == 0 else 'normal')
    axes[0].invert_yaxis()
    fig.text(.04, .10, 'Complete-document JEV leads both metrics; its MAP is only 0.0002 above passage MaxP.', fontsize=11, color='#34465b')
    fig.text(.04, .047, 'Duo is the full pointwise → pairwise cascade. Zero-based axes use separate scales. No significance claim.', fontsize=10, color='#526176')
    for suffix in ('svg', 'png'):
        fig.savefig(ROOT/f'docs/metrics/jev-reranking.{suffix}', dpi=180, facecolor='white', metadata={'Date': None} if suffix=='svg' else None)
    plt.close(fig)

if __name__ == '__main__': main()
