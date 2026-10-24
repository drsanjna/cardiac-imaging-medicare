"""Figures 8, S1, S2: state CTA rate vs physician density with unadjusted/adjusted NB fits and inline IRRs."""
import matplotlib.pyplot as plt
import numpy as np

from .. import config
from ..analysis.nb_models import density_partial_curve
from ..style import GRAY
from .export import save_pub_fig


def plot_density_fit(fit, title, color, fname, n_physicians, tiff_dpi=None):
    """Single panel: scatter + both NB fits + inline text box with unadjusted and adjusted IRR, CI, p."""
    d, density_col = fit['d'], fit['density_col']
    dens = d[density_col].values.astype(float)
    n_states = len(d)

    fig, ax = plt.subplots(figsize=(10.5, 7.0))
    fig.patch.set_facecolor('white')

    y = d['rate_per_1000'].values
    ax.scatter(dens, y, color=color, s=70, alpha=0.85,
               edgecolors='white', linewidths=0.7, zorder=3,
               label='State (labeled with postal code)')
    xg = np.linspace(dens.min(), dens.max(), 300)
    ru, _, _ = density_partial_curve(fit['res_un'], xg, 2)
    ra, la, ha = density_partial_curve(fit['res_adj'], xg, fit['ncoef_adj'])
    ax.fill_between(xg, la, ha, color=color, alpha=0.10, zorder=2,
                    label='95% CI of adjusted fit (shaded band)')
    ax.plot(xg, ru, color=GRAY, lw=2.2, ls=':', zorder=4,
            label='Unadjusted NB fit (dotted line)')
    ax.plot(xg, ra, color=color, lw=2.4, ls='--', zorder=5,
            label='Adjusted NB fit, age & %female at mean (dashed line)')
    for _, r in d.iterrows():
        ax.annotate(r['state'], (r[density_col], r['rate_per_1000']),
                    fontsize=10, color='#333333', fontfamily='monospace',
                    xytext=(4, 3), textcoords='offset points')
    ax.set_xlabel(fit['density_label'], fontsize=12, fontweight='bold')
    ax.set_ylabel('CTA Rate per 1,000 FFS Beneficiaries', fontsize=12, fontweight='bold')

    un_irr, un_lo, un_hi, un_p = fit['irr_un']
    adj_irr, adj_lo, adj_hi, adj_p = fit['irr_adj']
    un_pstr  = 'p<0.001' if un_p  < 0.001 else f'p={un_p:.3f}'
    adj_pstr = 'p<0.001' if adj_p < 0.001 else f'p={adj_p:.3f}'
    stats_text = (
        f"Unadjusted IRR = {un_irr:.3f} ({un_lo:.3f}–{un_hi:.3f}), {un_pstr}\n"
        f"Adjusted IRR   = {adj_irr:.3f} ({adj_lo:.3f}–{adj_hi:.3f}), {adj_pstr}\n"
        f"n = {n_states} states, {n_physicians:,} physicians"
    )
    ax.text(0.97, 0.05, stats_text, transform=ax.transAxes,
            fontsize=10, ha='right', va='bottom', fontfamily='monospace',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='white',
                      edgecolor='#cccccc', alpha=0.95))

    ax.legend(fontsize=10, framealpha=0.9, loc='upper left')
    ax.tick_params(labelsize=10)
    ax.grid(True, alpha=0.2, linewidth=0.5)
    ax.set_title(title, fontsize=13, fontweight='bold', pad=12)

    plt.tight_layout()
    save_pub_fig(fig, fname, tiff_dpi or config.TIFF_LINEART_DPI)   # read at call time so config overrides apply
