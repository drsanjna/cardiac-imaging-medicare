"""Ranked CTA-change figure (number = style.RANKED_FIG_NUM): every state by its change in CTA rate per 1,000, base → end year."""
import matplotlib.pyplot as plt
import numpy as np

from .. import config
from ..style import COLOR_CTA, RANKED_FIG_NUM
from .export import save_pub_fig


def plot_ranked_state_change(deltas, dispersion, end_year, base_year, proc='Cardiac CTA', fname=None):
    """Horizontal lollipop chart: states on the y-axis sorted by Δ rate, Δ rate per 1,000 on the x-axis.

    Each lollipop is labelled "base → end" rate; the median state change is a dashed line and the dispersion of
    state rates in each year (median, IQR, P90/P10) sits in a box in the empty lower-right corner.
    """
    fname = fname or f'figure{RANKED_FIG_NUM}_cta_state_ranked_change'
    d = (deltas[deltas['procedure_category'] == proc]
         .sort_values('rate_delta', ascending=True).reset_index(drop=True))      # largest change at the top
    y = np.arange(len(d))
    x = d['rate_delta'].values
    fig, ax = plt.subplots(figsize=(8.5, 0.21 * len(d) + 1.8))
    fig.patch.set_facecolor('white')
    ax.hlines(y, 0, x, color=COLOR_CTA, lw=1.6, alpha=0.7, zorder=2)
    ax.scatter(x, y, color=COLOR_CTA, s=42, zorder=3, edgecolors='white', linewidths=0.6)
    med = float(np.median(x))
    ax.axvline(med, color='#555555', lw=1.0, ls='--', zorder=1)
    ax.axvline(0, color='#bbbbbb', lw=0.8, zorder=1)
    pad = 0.012 * (x.max() - min(x.min(), 0))
    for yi, xi, r0, r1 in zip(y, x, d[f'rate_per_1000_{base_year}'], d[f'rate_per_1000_{end_year}']):
        neg = xi < 0                       # a falling state: label on the far side of the dot, away from the stem
        ax.text(xi - pad if neg else xi + pad, yi, f'{r0:.1f} → {r1:.1f}', va='center',
                ha='right' if neg else 'left', fontsize=7.5, color='#444444', fontfamily='monospace')
    ax.set_yticks(y)
    ax.set_yticklabels(d['state'], fontsize=8, fontfamily='monospace')
    ax.set_ylim(-0.8, len(d) - 0.2)
    ax.set_xlim(min(x.min(), 0) * 1.05 - 0.14 * x.max(), x.max() * 1.22)
    ax.set_xlabel(f'Change in {proc} services per 1,000 FFS beneficiaries, {base_year}→{end_year}',
                  fontsize=11, fontweight='bold')
    ax.tick_params(axis='x', labelsize=9)
    ax.grid(True, axis='x', alpha=0.2, linewidth=0.5)
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    ax.annotate(f'median state change {med:+.2f}', (med, len(d) - 0.6), fontsize=8.5, color='#555555',
                xytext=(4, 0), textcoords='offset points', va='center')

    disp = dispersion.loc[proc]
    lines = [f'State {proc} rate per 1,000 FFS', '']
    for year in (base_year, end_year):
        r = disp.loc[year]
        lines.append(f'{year}: median {r["median"]:.2f} (IQR {r["Q1"]:.2f}–{r["Q3"]:.2f}); '
                     f'P90/P10 = {r["P90/P10"]:.1f}')
    ax.text(0.98, 0.03, '\n'.join(lines), transform=ax.transAxes, fontsize=8.5, ha='right', va='bottom',
            fontfamily='monospace',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='white', edgecolor='#cccccc', alpha=0.95))
    ax.set_title(f'Figure {RANKED_FIG_NUM}. States Ranked by Change in {proc} Rate, {base_year}→{end_year}',
                 fontsize=12, fontweight='bold', pad=10)
    plt.tight_layout()
    save_pub_fig(fig, fname, config.TIFF_LINEART_DPI)
