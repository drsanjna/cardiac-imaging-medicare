"""Figure S6: change in radiologist + cardiologist density vs change in CTA rate by state, 2018 → 2023."""
import matplotlib.pyplot as plt
import numpy as np

from .. import config
from ..analysis.change import Z95
from ..style import GRAY, PURPLE
from .export import save_pub_fig


def _p(p):
    """'p<0.001' or 'p=0.012'."""
    return 'p<0.001' if p < 0.001 else f'p={p:.3f}'


def plot_change_on_change(df, fits, end_year, base_year, fname='figureS6_workforce_change_vs_cta_change'):
    """Scatter of Δ density vs Δ CTA rate per state, OLS line with 95% CI band, model results in a box below the plot."""
    x, y = df['d_density'].values, df['d_rate'].values
    fig, ax = plt.subplots(figsize=(10.5, 7.0))
    fig.patch.set_facecolor('white')
    ax.axhline(0, color='#bbbbbb', lw=0.8, zorder=1)
    ax.axvline(0, color='#bbbbbb', lw=0.8, zorder=1)
    ax.scatter(x, y, color=PURPLE, s=70, alpha=0.85, edgecolors='white', linewidths=0.7, zorder=3,
               label='State (labeled with postal code)')
    res = fits['all states']['res']
    xg = np.linspace(x.min(), x.max(), 200)
    X = np.column_stack([np.ones_like(xg), xg])
    pred = X @ np.asarray(res.params)
    se = np.sqrt(np.einsum('ij,jk,ik->i', X, np.asarray(res.cov_params()), X))
    ax.fill_between(xg, pred - Z95 * se, pred + Z95 * se, color=PURPLE, alpha=0.10, zorder=2,
                    label='95% CI of fit (shaded band, robust SE)')
    ax.plot(xg, pred, color=PURPLE, lw=2.4, ls='--', zorder=4, label='OLS fit, all states (dashed line)')
    sub = fits[[k for k in fits if k.startswith('without')][0]]['res']
    ax.plot(xg, np.column_stack([np.ones_like(xg), xg]) @ np.asarray(sub.params), color=GRAY, lw=2.0, ls=':',
            zorder=4, label='OLS fit without DC and MN (dotted line)')
    for _, r in df.iterrows():
        ax.annotate(r['state'], (r['d_density'], r['d_rate']), fontsize=10, color='#333333',
                    fontfamily='monospace', xytext=(4, 3), textcoords='offset points')
    ax.set_xlabel(f'Change in radiologists + cardiologists per 100,000 FFS, {base_year}→{end_year}',
                  fontsize=12, fontweight='bold')
    ax.set_ylabel(f'Change in CTA rate per 1,000 FFS, {base_year}→{end_year}', fontsize=12, fontweight='bold')

    a, w, c = fits['all states'], fits[[k for k in fits if k.startswith('without')][0]], fits['count model']
    s, lo, hi, p = a['slope']; s2, lo2, hi2, p2 = w['slope']; el, ell, elh, elp = c['elasticity']
    text = (f"Slope, all states    = {s:.3f} ({lo:.3f}–{hi:.3f}), {_p(p)}\n"
            f"Slope, without DC/MN = {s2:.3f} ({lo2:.3f}–{hi2:.3f}), {_p(p2)}\n"
            f"Spearman rho = {a['rho']:.2f}, {_p(a['rho_p'])}; n = {a['n']} states\n"
            f"Count model elasticity = {el:.2f} ({ell:.2f}–{elh:.2f}), {_p(elp)}\n"
            f"  (Δlog CTA ~ Δlog physicians + Δlog FFS)")
    ax.text(0.5, -0.13, text, transform=ax.transAxes, fontsize=10, ha='center', va='top', fontfamily='monospace',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='white', edgecolor='#cccccc', alpha=0.95))
    ax.legend(fontsize=10, framealpha=0.9, loc='upper left')
    ax.tick_params(labelsize=10)
    ax.grid(True, alpha=0.2, linewidth=0.5)
    ax.set_title(f'Supplemental Figure S6. Change in Radiologist + Cardiologist Density vs Change in CTA Rate, '
                 f'{base_year}→{end_year}', fontsize=13, fontweight='bold', pad=12)
    plt.tight_layout()
    save_pub_fig(fig, fname, config.TIFF_LINEART_DPI)
