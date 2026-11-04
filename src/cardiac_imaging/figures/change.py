"""Figure S5: partial-regression plot of the change-on-change count model, base year → end year."""
import matplotlib.pyplot as plt
import numpy as np

from .. import config
from ..analysis.change import Z95
from ..style import PURPLE
from .export import save_pub_fig


def _p(p):
    """'p<0.001' or 'p=0.012'."""
    return 'p<0.001' if p < 0.001 else f'p={p:.3f}'


def plot_change_partial_regression(pr, fits, end_year, base_year, fname='figureS5_cta_change_partial_regression'):
    """Added-variable plot for Δlog CTA ~ Δlog physicians + Δlog FFS: residual vs residual per state, with the
    model's elasticity as a line through the origin and its 95% band (HC3 SE); coefficients in a box below."""
    x, y = pr['x_resid'].values, pr['y_resid'].values
    c = fits['count model']
    beta, lo, hi, p = c['elasticity']
    se = (hi - lo) / (2 * Z95)
    fig, ax = plt.subplots(figsize=(10.5, 7.2))
    fig.patch.set_facecolor('white')
    ax.axhline(0, color='#bbbbbb', lw=0.8, zorder=1)
    ax.axvline(0, color='#bbbbbb', lw=0.8, zorder=1)
    ax.scatter(x, y, color=PURPLE, s=70, alpha=0.85, edgecolors='white', linewidths=0.7, zorder=3,
               label='State (labeled with postal code)')
    xg = np.linspace(x.min(), x.max(), 200)
    ax.fill_between(xg, (beta - Z95 * se) * xg, (beta + Z95 * se) * xg, color=PURPLE, alpha=0.10, zorder=2,
                    label='95% CI of the adjusted slope (robust SE)')
    ax.plot(xg, beta * xg, color=PURPLE, lw=2.4, ls='--', zorder=4,
            label=f'Adjusted association (elasticity β = {beta:.2f})')
    for _, r in pr.iterrows():
        ax.annotate(r['state'], (r['x_resid'], r['y_resid']), fontsize=10, color='#333333',
                    fontfamily='monospace', xytext=(4, 3), textcoords='offset points')
    ax.set_xlabel(f'Δlog radiologists + cardiologists, {base_year}→{end_year}\n'
                  '(residual after adjusting for Δlog FFS enrollment)', fontsize=12, fontweight='bold')
    ax.set_ylabel(f'Δlog CTA services, {base_year}→{end_year}\n(residual after adjusting for Δlog FFS enrollment)',
                  fontsize=12, fontweight='bold')
    g, glo, ghi, gp = c['ffs_coef']
    text = (f"Model: Δlog C = α + β·Δlog P + γ·Δlog E   (C = CTA services, P = radiologists + cardiologists, "
            f"E = FFS enrollment; n = {c['n']} states)\n"
            f"β (physicians) = {beta:.2f} ({lo:.2f} to {hi:.2f}), {_p(p)}   —   "
            f"% change in CTA per 1% change in physicians, FFS change held fixed\n"
            f"γ (FFS enrollment) = {g:.2f} ({glo:.2f} to {ghi:.2f}), {_p(gp)};  R² = {c['r2']:.2f};  OLS with HC3 robust SEs")
    ax.text(0.5, -0.17, text, transform=ax.transAxes, fontsize=9.5, ha='center', va='top', fontfamily='monospace',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='white', edgecolor='#cccccc', alpha=0.95))
    ax.legend(fontsize=10, framealpha=0.9, loc='upper left')
    ax.tick_params(labelsize=10)
    ax.grid(True, alpha=0.2, linewidth=0.5)
    ax.set_title(f'Supplemental Figure S5. Change in CTA Services vs Change in Radiologist + Cardiologist Numbers, '
                 f'{base_year}→{end_year}\nPartial regression, adjusted for change in FFS enrollment',
                 fontsize=13, fontweight='bold', pad=12)
    plt.tight_layout()
    save_pub_fig(fig, fname, config.TIFF_LINEART_DPI)
