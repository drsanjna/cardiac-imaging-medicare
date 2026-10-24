"""Figure 1: volume vs FFS enrollment vs utilization rate, 3 metrics × 5 modalities."""
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from .. import config
from ..style import COLOR_ENROLLMENT, COLOR_RATE, COLOR_VOLUME, PROC_ORDER
from .export import save_pub_fig

ROW_CONFIG = [
    ('total_services', 'Procedure Volume',             COLOR_VOLUME,     'o'),
    ('enrollment',     'FFS Enrollment',                COLOR_ENROLLMENT, 's'),
    ('rate_per_1000',  'Rate per 1,000 Beneficiaries',  COLOR_RATE,       'D'),
]


def plot_figure1(decomp_df):
    """Draw and save Figure 1 (volume, FFS enrollment and rate per modality, 3 × 5 panels)."""
    fig = plt.figure(figsize=(22, 13))
    outer_gs = gridspec.GridSpec(3, 5, hspace=0.45, wspace=0.35,
                                 left=0.05, right=0.97, top=0.87, bottom=0.07)
    years_all = sorted(decomp_df['year'].unique())

    for col_idx, proc in enumerate(PROC_ORDER):
        sub = decomp_df[decomp_df['procedure_category'] == proc].sort_values('year')
        years = sub['year'].values
        for row_idx, (col_name, row_label, color, marker) in enumerate(ROW_CONFIG):
            ax = fig.add_subplot(outer_gs[row_idx, col_idx])
            vals = sub[col_name].values
            ax.plot(years, vals, marker=marker, color=color, linewidth=2.2, markersize=7, zorder=3)
            ax.fill_between(years, vals, alpha=0.08, color=color, zorder=1)
            for yr, v in zip(years, vals):
                if col_name == 'enrollment':
                    label = f'{v/1e6:.1f}M'
                elif col_name == 'total_services':
                    label = f'{v/1e6:.2f}M' if v >= 1_000_000 else f'{v/1e3:.1f}K'
                else:
                    label = f'{v:.2f}'
                ax.annotate(label, (yr, v), textcoords="offset points", xytext=(0, 9),
                            fontsize=10, ha='center', color=color, fontweight='bold')
            ax.set_xticks(years_all)
            ax.tick_params(labelsize=10)
            ax.grid(True, alpha=0.2)
            if col_name == 'enrollment':
                ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x/1e6:.0f}M'))
            elif col_name == 'total_services':
                if vals.max() >= 1_000_000:
                    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x/1e6:.1f}M'))
                else:
                    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x/1e3:.0f}K'))
            ymin, ymax = vals.min(), vals.max()
            yrange = ymax - ymin if ymax != ymin else ymax * 0.1
            ax.set_ylim(ymin - yrange * 0.15, ymax + yrange * 0.3)
            if row_idx == 0:
                ax.set_title(proc, fontsize=13, fontweight='bold', pad=10)
            if col_idx == 0:
                ax.set_ylabel(row_label, fontsize=11, fontweight='bold')
            if row_idx == 2:
                ax.set_xlabel('Year', fontsize=11)
            else:
                ax.set_xticklabels([])

    fig.suptitle('Figure 1. Decomposing Procedure Volume: Volume vs. FFS Enrollment vs. Utilization Rate\n'
                 'Source: CMS Medicare Physician & Other Practitioners  |  Denominator: CMS Original Medicare Enrollment',
                 fontsize=14, fontweight='bold', y=0.96)
    fig.text(0.05, 0.015,
             'Symbols: circles = annual procedure volume; squares = national FFS enrollment; '
             'diamonds = utilization rate per 1,000 FFS beneficiaries.',
             fontsize=10, color='#555555')
    save_pub_fig(fig, 'figure1_decomposition', config.TIFF_PANEL_DPI)
