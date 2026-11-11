"""Figure 8 (cardiac CTA, TAVR procedures, CACS, structural CT) and Figure S6 (invasive FFR, FFR-CT): national rate per
1,000 FFS beneficiaries by year, one axis per figure."""
import matplotlib.pyplot as plt

from .. import config
from ..style import COLOR_CTA
from .export import save_pub_fig

LINE_STYLE = {   # label → (colour, marker, line style)
    'Cardiac CTA': (COLOR_CTA, 'o', '-'),
    config.TAVR_LABEL: ('#2471A3', 's', '--'),
    config.CACS_LABEL: ('#C0392B', 'D', '-.'),
    config.CARDIAC_CT_LABEL: ('#7F8C8D', '^', ':'),
    config.FFR_LABEL: ('#2471A3', 's', '-'),
    config.FFRCT_LABEL: (COLOR_CTA, 'o', '--'),
}
TITLES = {'Cardiac CTA': 'Cardiac CTA (CPT 75574)',
          config.TAVR_LABEL: 'TAVR procedures (CPT 33361–33366, services ÷ 2)',
          config.CACS_LABEL: 'Coronary artery calcium score (CPT 75571)',
          config.CARDIAC_CT_LABEL: 'Cardiac structural CT, non-coronary (CPT 75572)',
          config.FFR_LABEL: 'Invasive FFR, first vessel (CPT 93571)',
          config.FFRCT_LABEL: 'FFR-CT (CPT 0501T + 0504T; 75580 from 2024)'}
FIG8_PROCS = ('Cardiac CTA', config.TAVR_LABEL, config.CACS_LABEL, config.CARDIAC_CT_LABEL)
FFR_FIG_PROCS = (config.FFR_LABEL, config.FFRCT_LABEL)
FFR_FIG_STEM = 'figureS6_ffr_ffrct_rates'
FIG8_NOTE = ('TAVR is billed by both heart-team physicians (modifier 62), so procedures = services ÷ 2 (cardiology and '
             'surgery each bill ~49% of services every year). CACS = standalone calcium score; a calcium score acquired '
             'within a CTA is bundled into the CTA code. 75572 is the non-coronary cardiac CT code under which a '
             'TAVR-planning CT may be billed instead of 75574.')
FFR_NOTE = ('93571 is an add-on to invasive coronary angiography (first vessel; additional vessels, 93572, not counted). '
            'FFR-CT: Category III codes 0501T (complete) and 0504T (interpretation) to 2023, Category I 75580 from 2024. '
            'CMS suppresses every provider–code row with fewer than 11 beneficiaries; FFR-CT is the lowest-volume series '
            'in this study and the most affected, so its rates are a lower bound and are shown as context only.')


def plot_rate_trends(decomp_df, procs=FIG8_PROCS, fname='figure8_cta_tavr_cacs_rates', fig_num=8,
                     title='Cardiac CTA, TAVR, Coronary Calcium Scoring and Structural Cardiac CT',
                     ylabel='Procedures per 1,000 FFS beneficiaries', note=FIG8_NOTE, legend_loc='upper left'):
    """One line per procedure: rate per 1,000 FFS beneficiaries (y) by year (x), end-of-line labels with the last value.

    Returns the procedures actually drawn (those present in `decomp_df`, in `procs` order)."""
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
    ax.set_ylabel(ylabel, fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.25, linewidth=0.5)
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    ax.legend(fontsize=10, framealpha=0.9, loc=legend_loc)
    ax.set_title(f'Figure {fig_num}. {title}: National Rates per 1,000 FFS Beneficiaries, {years[0]}–{years[-1]}',
                 fontsize=12, fontweight='bold', pad=12)
    fig.text(0.01, 0.005, note, fontsize=8.5, color='#555555', wrap=True)
    plt.tight_layout(rect=(0, 0.06, 1, 1))
    save_pub_fig(fig, fname, config.TIFF_LINEART_DPI)
    return present


def plot_ffr_trends(decomp_df):
    """Figure S6: invasive FFR (93571) and FFR-CT (0501T/0504T, 75580) national rates per 1,000 FFS by year."""
    return plot_rate_trends(decomp_df, procs=FFR_FIG_PROCS, fname=FFR_FIG_STEM, fig_num='S6',
                            title='Invasive FFR and FFR-CT', ylabel='Services per 1,000 FFS beneficiaries', note=FFR_NOTE,
                            legend_loc='center left')   # upper left would cover the 2019 invasive-FFR peak
