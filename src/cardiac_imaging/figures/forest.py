"""Figure 9: density IRRs before/after adjustment by specialty."""
import textwrap

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.lines import Line2D

from .. import config
from ..style import GRAY
from .export import save_pub_fig

Y_OFFSET = {'un': +0.17, 'adj': -0.17}
RESULT_X = 1.40     # fixed results gutter: whiskers live in 0.95–1.35, numbers align here
SEP_X    = 1.375

CAPTION = (
    'Horizontal bars = 95% CIs. NB2 models, state-level. n = nationally deduplicated '
    'unique CTA-billing NPIs (COUNT DISTINCT across all states) for each specialty group. '
    'Models fit on states with ≥1 qualifying NPI and complete demographic data; states with '
    'no billers of a given specialty are excluded from that model. Offset = log(FFS enrollment). '
    'Adjusted models include z-scored mean age and % female. Interpretation shares from Table 1. '
    'IRR > 1 indicates higher CTA rates in higher-density states. CIs overlap across specialties; '
    'between-specialty differences were not formally tested.'
)


def plot_forest(rows):
    """rows: [(label, share_note, result_dict(irr_un, irr_adj, n_physicians), color), ...]."""
    fig, ax = plt.subplots(figsize=(11.5, 5.8))
    fig.patch.set_facecolor('white')

    for i, (label, share_note, r, color) in enumerate(rows):
        for key, (irr, lo, hi, p) in [('un', r['irr_un']), ('adj', r['irr_adj'])]:
            yy = i + Y_OFFSET[key]
            c = GRAY if key == 'un' else color
            marker = 'o' if key == 'un' else 's'
            ax.plot([lo, hi], [yy, yy], color=c, lw=2.4, zorder=2, solid_capstyle='round')
            ax.scatter([irr], [yy], color=c, s=95, marker=marker, zorder=3,
                       edgecolors='white', linewidths=1)
            pstr = 'p<0.001' if p < 0.001 else f'p={p:.3f}'
            ax.text(RESULT_X, yy, f"{irr:.3f}    {pstr}", va='center', ha='left',
                    fontsize=10, fontfamily='monospace', color='#333333')

    ax.text(RESULT_X, -0.62, 'IRR      p-value', va='center', ha='left',
            fontsize=9.5, fontfamily='monospace', fontweight='bold', color='#555555')

    ax.axvline(1.0,   color='#777777', lw=1.2, ls='--', zorder=1)
    ax.axvline(SEP_X, color='#dddddd', lw=1.0, zorder=1)

    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(
        [f"{label}\n({note}, n={r['n_physicians']:,})" for label, note, r, _ in rows],
        fontsize=11
    )
    ax.invert_yaxis()
    ax.set_ylim(len(rows) - 0.5, -0.75)

    ax.set_xscale('log')
    xticks = [0.95, 1.0, 1.05, 1.1, 1.15, 1.2, 1.25, 1.3, 1.35]
    ax.set_xticks(xticks)
    ax.set_xticklabels([f'{t:g}' for t in xticks], fontsize=10)
    ax.xaxis.set_minor_locator(mticker.NullLocator())
    ax.set_xlim(0.95, 1.62)          # room for the results gutter; ticks stop at 1.35
    ax.set_xlabel('Density Incidence Rate Ratio (per +1 NPI per 100,000 FFS beneficiaries)',
                  fontsize=12, fontweight='bold')

    legend_elems = [
        Line2D([0], [0], marker='o', color=GRAY, lw=2.4, markersize=9,
               markeredgecolor='white', label='Unadjusted'),
        Line2D([0], [0], marker='s', color='#444444', lw=2.4, markersize=9,
               markeredgecolor='white', label='Adjusted (age, sex)'),
        Line2D([0], [0], color='#777777', lw=1.2, ls='--', label='Null (IRR = 1.0)'),
    ]
    ax.legend(handles=legend_elems, loc='upper left', fontsize=9.5,
              framealpha=0.95, borderaxespad=0.8, handlelength=1.6)

    ax.grid(True, axis='x', alpha=0.2, linewidth=0.5)
    ax.spines[['top', 'right']].set_visible(False)

    ax.set_title(
        'Figure 9. CTA Utilization vs Imaging Physician Density (2023):\n'
        'Density IRRs Before and After Demographic Adjustment, by Interpreting Specialty',
        fontsize=13, fontweight='bold', pad=12,
    )
    fig.text(0.5, -0.06, textwrap.fill(CAPTION, width=112),
             ha='center', va='top', fontsize=9, color='#555555', linespacing=1.4,
             bbox=dict(boxstyle='round,pad=0.7', facecolor='#f7f7f7',
                       edgecolor='#cccccc', linewidth=0.8))

    plt.tight_layout()
    save_pub_fig(fig, 'figure9_density_irr_forest', config.TIFF_LINEART_DPI)
