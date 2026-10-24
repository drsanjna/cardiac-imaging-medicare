"""Figures 3–7, 10, 11: state choropleths per modality and comparator procedure (2018 / 2023 / change), plus a 2023 panel."""
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .. import config
from ..style import CHORO_FONT, DELTA_SCALE, PROC_ORDER, PURPLE_SCALE
from .export import save_plotly

_GEOS = dict(scope='usa', projection_type='albers usa',
             showlakes=True, lakecolor='rgb(200,220,240)', bgcolor='white')


# Comparator maps, numbered after the imaging figures (3–9): (label, figure number, footnote).
COMPARATOR_MAPS = [
    (config.ICA_LABEL, 10, 'ICA = diagnostic catheterization with coronary angiography, CPT 93454–93461.'),
    (config.TAVR_LABEL, 11, 'TAVR = transcatheter aortic valve replacement, CPT 33361–33366. Usually billed by two '
                            'co-surgeons, so services ≈ 2 × procedures.'),
]


def map_stem(proc, fig_num):
    """File stem of a state-map figure, e.g. figure4_spect_state_maps."""
    return f'figure{fig_num}_{proc.lower().replace(" ", "_")}_state_maps'


def plot_state_maps(state_rates_2018, state_rates_2023, delta_df):
    """One 3-panel map figure per modality, numbered 3–7 in PROC_ORDER."""
    for idx, proc in enumerate(PROC_ORDER):
        plot_one_state_map(proc, idx + 3, state_rates_2018, state_rates_2023, delta_df)


def plot_comparator_state_maps(label, fig_num, note, state_rates_2018, state_rates_2023, delta_df):
    """A comparator's state map (Figures 10–11), same layout as Figures 3–7; states with no 2018 rows are left blank."""
    no_base = sorted(set(state_rates_2023['state']) - set(state_rates_2018['state']))
    if no_base:
        note += f" No 2018 rows for {', '.join(no_base)} (none or suppressed): blank, no change shown."
    plot_one_state_map(label, fig_num, state_rates_2018, state_rates_2023, delta_df, note=note)


def plot_one_state_map(proc, fig_num, state_rates_2018, state_rates_2023, delta_df, note=''):
    """Draw and save one 3-panel (2018 / 2023 / change) state map for `proc`."""
    p2018 = state_rates_2018[state_rates_2018['procedure_category'] == proc]
    p2023 = state_rates_2023[state_rates_2023['procedure_category'] == proc]
    p_delta = delta_df[delta_df['procedure_category'] == proc].dropna(subset=['rate_delta'])
    if p2023.empty:
        print(f"  No data for {proc} — skipping")
        return

    all_rates = pd.concat([p2018['rate_per_1000'], p2023['rate_per_1000']])
    rate_min, rate_max = all_rates.min(), all_rates.max()

    fig = make_subplots(
        rows=1, cols=3,
        specs=[[{'type': 'choropleth'}] * 3],
        subplot_titles=['2018', '2023', 'Change (2023 − 2018)'],
        horizontal_spacing=0.02,
    )
    fig.add_trace(go.Choropleth(
        locations=p2018['state'], z=p2018['rate_per_1000'],
        locationmode='USA-states', colorscale=PURPLE_SCALE,
        zmin=rate_min, zmax=rate_max,
        colorbar=dict(title='Rate/1K', len=0.6, x=0.29, thickness=14, tickfont=CHORO_FONT),
        marker_line_color='white', marker_line_width=0.5,
        hovertemplate='<b>%{location}</b><br>Rate: %{z:.2f}/1K<extra></extra>',
    ), row=1, col=1)
    fig.add_trace(go.Choropleth(
        locations=p2023['state'], z=p2023['rate_per_1000'],
        locationmode='USA-states', colorscale=PURPLE_SCALE,
        zmin=rate_min, zmax=rate_max,
        colorbar=dict(title='Rate/1K', len=0.6, x=0.62, thickness=14, tickfont=CHORO_FONT),
        marker_line_color='white', marker_line_width=0.5,
        hovertemplate='<b>%{location}</b><br>Rate: %{z:.2f}/1K<extra></extra>',
    ), row=1, col=2)
    delta_abs_max = max(abs(p_delta['rate_delta'].min()), abs(p_delta['rate_delta'].max()), 0.01)
    fig.add_trace(go.Choropleth(
        locations=p_delta['state'], z=p_delta['rate_delta'],
        locationmode='USA-states', colorscale=DELTA_SCALE,
        zmid=0, zmin=-delta_abs_max, zmax=delta_abs_max,
        colorbar=dict(title='Δ Rate/1K', len=0.6, x=0.96, thickness=14, tickfont=CHORO_FONT),
        marker_line_color='white', marker_line_width=0.5,
        hovertemplate='<b>%{location}</b><br>Δ Rate: %{z:+.2f}/1K<extra></extra>',
    ), row=1, col=3)

    fig.update_geos(**_GEOS)
    fig.update_annotations(font=dict(size=18))
    fig.update_layout(
        title=dict(
            text=(f'<b>Figure {fig_num}.</b> {proc} — Rate per 1,000 FFS Beneficiaries by State<br>'
                  f'<span style="font-size:13px">Purple scale: darker = higher rate. '
                  f'Diverging scale (right panel): red = rate decrease, blue = rate increase, '
                  f'white = no change. Territories excluded.</span>'),
            font=dict(size=18), x=0.5, xanchor='center',
        ),
        height=430, width=1500, paper_bgcolor='white',
        margin=dict(l=10, r=10, t=95, b=45 if note else 20),
    )
    if note:   # footnote under the maps, so the header matches Figures 3–7
        fig.add_annotation(text=note, x=0.5, y=-0.06, xref='paper', yref='paper', showarrow=False,
                           font=dict(size=13))
    # width 1500 × scale 3 = 4500 px ≈ 300 DPI at a 15-inch print width
    save_plotly(fig, f'{map_stem(proc, fig_num)}.png', width=1500, height=430)


def plot_all_modalities_panel(state_rates_2023):
    """Unnumbered composite of 2023 state rates for all five modalities (optional Central Illustration)."""
    fig_panel = make_subplots(
        rows=2, cols=3,
        specs=[[{'type': 'choropleth'}] * 3, [{'type': 'choropleth'}] * 2 + [None]],
        subplot_titles=[f'{p}' for p in PROC_ORDER],
        horizontal_spacing=0.02, vertical_spacing=0.08,
    )
    positions = [(1, 1), (1, 2), (1, 3), (2, 1), (2, 2)]
    for i, (proc, (row, col)) in enumerate(zip(PROC_ORDER, positions)):
        pdata = state_rates_2023[state_rates_2023['procedure_category'] == proc]
        if pdata.empty:
            continue
        fig_panel.add_trace(go.Choropleth(
            locations=pdata['state'], z=pdata['rate_per_1000'],
            locationmode='USA-states', colorscale=PURPLE_SCALE,
            colorbar=dict(title='Rate/1K', len=0.35, thickness=12, tickfont=CHORO_FONT),
            marker_line_color='white', marker_line_width=0.5,
            showscale=(i == 0),
            hovertemplate='<b>%{location}</b><br>Rate: %{z:.2f}/1K<extra></extra>',
        ), row=row, col=col)
    fig_panel.update_geos(**_GEOS)
    fig_panel.update_annotations(font=dict(size=18))
    fig_panel.update_layout(
        title=dict(text='<b>Cardiac Imaging Rates by State (2023) — All Modalities</b>'
                        '<br><span style="font-size:13px">Purple scale: darker = higher rate. '
                        'Scales differ by modality.</span>',
                   font=dict(size=20), x=0.5, xanchor='center'),
        height=720, width=1400, paper_bgcolor='white',
        margin=dict(l=10, r=10, t=100, b=20),
    )
    save_plotly(fig_panel, 'figure_panel_all_modalities_2023.png', width=1400, height=720)
