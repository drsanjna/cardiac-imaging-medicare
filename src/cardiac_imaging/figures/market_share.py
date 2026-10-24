"""Figure 2: modality market share by rural/urban × office/facility, with advanced-modality zoom insets."""
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

from .. import config
from ..analysis.rates import SEGMENTS
from ..style import COLOR_CTA, COLOR_MRI, COLOR_PET, PROC_COLORS, PROC_ORDER
from .export import save_pub_fig

SEG_TITLES = {
    'Urban / Office': 'Urban – Office', 'Urban / Facility': 'Urban – Facility',
    'Rural / Office': 'Rural – Office', 'Rural / Facility': 'Rural – Facility',
}
ADV_PROCS  = ['Cardiac CTA', 'Cardiac MRI', 'Cardiac PET']
ADV_COLORS = [COLOR_CTA, COLOR_MRI, COLOR_PET]


def plot_figure2(market_data):
    """Draw and save Figure 2 (stacked market share per setting with advanced-modality insets)."""
    fig = plt.figure(figsize=(18, 14))
    outer_gs = gridspec.GridSpec(2, 2, hspace=0.35, wspace=0.3,
                                 left=0.06, right=0.94, top=0.90, bottom=0.06)

    for idx, seg in enumerate(SEGMENTS):
        row, col = divmod(idx, 2)
        inner_gs = gridspec.GridSpecFromSubplotSpec(2, 1, subplot_spec=outer_gs[row, col],
                                                    height_ratios=[3, 1.8], hspace=0.14)
        ax_main = fig.add_subplot(inner_gs[0])
        ax_inset = fig.add_subplot(inner_gs[1])

        seg_pct = market_data[seg]
        years = seg_pct.index.values

        y_stack = np.zeros(len(years))
        for i, proc in enumerate(PROC_ORDER):
            vals = seg_pct[proc].values if proc in seg_pct.columns else np.zeros(len(years))
            ax_main.fill_between(years, y_stack, y_stack + vals,
                                 color=PROC_COLORS[i], label=proc, alpha=0.85)
            y_stack += vals

        ax_main.set_ylim(0, 100); ax_main.set_xlim(years.min(), years.max())
        ax_main.set_title(SEG_TITLES[seg], fontsize=13, fontweight='bold', pad=8)
        ax_main.set_ylabel('Market Share (%)', fontsize=12)
        ax_main.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:.0f}'))
        ax_main.set_xticks(years)
        ax_main.tick_params(labelsize=10)
        ax_main.grid(True, alpha=0.2)

        if idx == 0:
            h, l = ax_main.get_legend_handles_labels()
            ax_main.legend(h[::-1], l[::-1], fontsize=10, loc='center left',
                           framealpha=0.9, title='Modality (shaded band)', title_fontsize=10)

        y_stack_adv = np.zeros(len(years))
        for i, proc in enumerate(ADV_PROCS):
            vals = seg_pct[proc].values if proc in seg_pct.columns else np.zeros(len(years))
            ax_inset.fill_between(years, y_stack_adv, y_stack_adv + vals,
                                  color=ADV_COLORS[i], label=proc, alpha=0.85)
            y_stack_adv += vals

        ax_inset.set_ylim(0, max(y_stack_adv.max() * 1.35, 0.5))
        ax_inset.set_xlim(years.min(), years.max())
        ax_inset.set_xlabel('Year', fontsize=12)
        ax_inset.set_ylabel('Advanced Share (%)', fontsize=11)
        ax_inset.set_xticks(years)
        ax_inset.tick_params(labelsize=10)
        ax_inset.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:.2f}'))
        ax_inset.grid(True, alpha=0.2)
        ax_inset.set_title('Zoom: Advanced Modalities (CTA + CMR + PET)', fontsize=10,
                           fontstyle='italic', color='#555555', pad=4)

        if idx == 0:
            h_a, l_a = ax_inset.get_legend_handles_labels()
            ax_inset.legend(h_a[::-1], l_a[::-1], fontsize=10, loc='upper left', framealpha=0.9)

        for yr_idx in [0, -1]:
            ax_inset.annotate(f'{y_stack_adv[yr_idx]:.2f}%',
                              (years[yr_idx], y_stack_adv[yr_idx]),
                              textcoords="offset points", xytext=(0, 8),
                              fontsize=10, ha='center', fontweight='bold', color='#5B005B')

    fig.suptitle('Figure 2. Market Share: Composition of Cardiac Imaging Modalities\n'
                 'Traditional (Echo + SPECT) vs Advanced (CTA + CMR + PET)',
                 fontsize=15, fontweight='bold', y=0.97)
    fig.text(0.06, 0.015,
             'Shaded bands = each modality’s share of total cardiac imaging volume. '
             'Bold labels on insets = advanced-modality share in first and last year.',
             fontsize=10, color='#555555')
    save_pub_fig(fig, 'figure2_market_share', config.TIFF_PANEL_DPI)
