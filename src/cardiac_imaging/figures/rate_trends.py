"""Figure 8: national rate per 1,000 FFS beneficiaries by year for cardiac CTA, TAVR and CACS on one axis."""
import matplotlib.pyplot as plt

from .. import config
from ..style import COLOR_CTA
from .export import save_pub_fig

LINE_STYLE = {   # label → (colour, marker, line style)
    'Cardiac CTA': (COLOR_CTA, 'o', '-'),
    config.TAVR_LABEL: ('#2471A3', 's', '--'),
    config.CACS_LABEL: ('#C0392B', 'D', '-.'),
}
TITLES = {'Cardiac CTA': 'Cardiac CTA (CPT 75574)', config.TAVR_LABEL: 'TAVR (CPT 33361–33366)',
          config.CACS_LABEL: 'Coronary artery calcium score (CPT 75571)'}


def plot_rate_trends(decomp_df, procs=('Cardiac CTA', config.TAVR_LABEL, config.CACS_LABEL),
                     fname='figure8_cta_tavr_cacs_rates', fig_num=8):
    """One line per procedure: rate per 1,000 FFS beneficiaries (y) by year (x), end-of-line labels with the last value."""
    fig, ax = plt.subplots(figsize=(9, 6))
    fig.patch.set_facecolor('white')
    present = [p for p in procs if p in set(decomp_df['procedure_category'])]
    for proc in present:
        sub = decomp_df[decomp_df['procedure_category'] == proc].sort_values('year')
        color, marker, ls = LINE_STYLE.get(proc, ('#555555', 'o', '-'))
        ax.plot(sub['year'], sub['rate_per_1000'], color=color, marker=marker, ls=ls, lw=2.4, ms=7,
                label=TITLES.get(proc, proc), zorder=3)
        last = sub.iloc[-1]
        ax.annotate(f'{last["rate_per_1000"]:.2f}', (last['year'], last['rate_per_1000']), xytext=(6, 0),
                    textcoords='offset points', va='center', fontsize=10, color=color, fontweight='bold')
    years = sorted(decomp_df['year'].unique())
    ax.set_xticks(years)
    ax.set_xlim(years[0] - 0.3, years[-1] + 0.8)
    ax.set_ylim(bottom=0)
    ax.set_xlabel('Year', fontsize=12, fontweight='bold')
    ax.set_ylabel('Services per 1,000 FFS beneficiaries', fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.25, linewidth=0.5)
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    ax.legend(fontsize=10, framealpha=0.9, loc='upper left')
    ax.set_title(f'Figure {fig_num}. Cardiac CTA, TAVR and Coronary Calcium Scoring: National Rates per 1,000 FFS '
                 f'Beneficiaries, {years[0]}–{years[-1]}', fontsize=12, fontweight='bold', pad=12)
    fig.text(0.01, 0.005, 'TAVR is usually billed by two co-surgeons, so TAVR services ≈ 2 × procedures. '
             'CACS = standalone calcium score; a calcium score acquired within a CTA is bundled into the CTA code.',
             fontsize=9, color='#555555')
    plt.tight_layout(rect=(0, 0.03, 1, 1))
    save_pub_fig(fig, fname, config.TIFF_LINEART_DPI)
    return present
