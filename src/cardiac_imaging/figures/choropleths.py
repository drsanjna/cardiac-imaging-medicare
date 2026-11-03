"""Figures 3–7, 10–12: state choropleths per modality and comparator procedure (base year / end year / change), plus an end-year panel."""
import textwrap

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .. import config
from ..style import CHORO_FONT, DELTA_SCALE, PROC_ORDER, PURPLE_SCALE
from .export import save_plotly

_GEOS = dict(scope='usa', projection_type='albers usa',
             showlakes=True, lakecolor='rgb(200,220,240)', bgcolor='white')


NO_DATA_GREY = '#9e9e9e'

# Comparator maps, numbered after the imaging figures (3–9): (label, figure number, footnote).
COMPARATOR_MAPS = [
    (config.ICA_LABEL, 10, 'ICA = diagnostic catheterization with coronary angiography, CPT 93454–93461.'),
    (config.TAVR_LABEL, 11, 'TAVR = transcatheter aortic valve replacement, CPT 33361–33366. Usually billed by two '
                            'co-surgeons, so services ≈ 2 × procedures.'),
    (config.CACS_LABEL, 12, 'CACS = coronary artery calcium score, CPT 75571.'),
]
ALL_STATES = sorted(config.STATE_ABBR_MAP.values())   # 50 states + DC


def map_stem(proc, fig_num):
    """File stem of a state-map figure, e.g. figure4_spect_state_maps."""
    return f'figure{fig_num}_{proc.lower().replace(" ", "_")}_state_maps'


def plot_state_maps(state_rates_2018, state_rates_2023, delta_df):
    """One 3-panel map figure per modality, numbered 3–7 in PROC_ORDER."""
    for idx, proc in enumerate(PROC_ORDER):
        plot_one_state_map(proc, idx + 3, state_rates_2018, state_rates_2023, delta_df)


def plot_comparator_state_maps(label, fig_num, note, state_rates_2018, state_rates_2023, delta_df):
    """A comparator's state map (Figures 10–12), same layout as Figures 3–7; a state with no rows in a year is grey."""
    for year, rates_ in [(config.BASE_YEAR, state_rates_2018), (config.END_YEAR, state_rates_2023)]:
        missing = sorted(set(ALL_STATES) - set(rates_.loc[rates_['procedure_category'] == label, 'state']))
        if missing:
            note += f" No {year} rows for {', '.join(missing)} (none or suppressed): grey, no change shown."
    plot_one_state_map(label, fig_num, state_rates_2018, state_rates_2023, delta_df, note=note,
                       grey_all_missing=True)


def plot_one_state_map(proc, fig_num, state_rates_2018, state_rates_2023, delta_df, note='', grey_all_missing=False):
    """Draw and save one 3-panel (base year / end year / change) state map for `proc`.

    States with end-year rows but none in the base year are grey on the base-year and change panels. With grey_all_missing, every
    state of the 50 + DC without data in a panel is grey there (used for comparators with sparse coverage).
    """
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
        subplot_titles=[str(config.BASE_YEAR), str(config.END_YEAR), f'Change ({config.END_YEAR} − {config.BASE_YEAR})'],
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

    if grey_all_missing:
        grey = {col: sorted(set(ALL_STATES) - set(p['state'])) for col, p in [(1, p2018), (2, p2023), (3, p_delta)]}
    else:
        no_base = sorted(set(p2023['state']) - set(p2018['state']))
        grey = {1: no_base, 3: no_base}
    for col, states in grey.items():   # no data: solid grey (not white, which means "no change" on the delta scale)
        if states:
            fig.add_trace(go.Choropleth(
                locations=states, z=[0] * len(states), locationmode='USA-states',
                colorscale=[[0, NO_DATA_GREY], [1, NO_DATA_GREY]], showscale=False,
                marker_line_color='white', marker_line_width=0.5,
                hovertemplate='<b>%{location}</b><br>No data<extra></extra>',
            ), row=1, col=col)

    note_lines = textwrap.wrap(note, 170)
    height = 430 + (20 * len(note_lines) if note else 0)   # grow the figure for the footnote, keep map size
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
        height=height, width=1500, paper_bgcolor='white',
        margin=dict(l=10, r=10, t=95, b=20 + 20 * len(note_lines) if note else 20),
    )
    if note:   # footnote under the maps (wrapped), so the header matches Figures 3–7
        fig.add_annotation(text='<br>'.join(note_lines), x=0.5, y=-0.04, xref='paper', yref='paper',
                           yanchor='top', showarrow=False, font=dict(size=13))
    # width 1500 × scale 3 = 4500 px ≈ 300 DPI at a 15-inch print width
    save_plotly(fig, f'{map_stem(proc, fig_num)}.png', width=1500, height=height)


def plot_all_modalities_panel(state_rates_2023):
    """Unnumbered composite of end-year state rates for all five modalities (optional Central Illustration)."""
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
        title=dict(text=f'<b>Cardiac Imaging Rates by State ({config.END_YEAR}) — All Modalities</b>'
                        '<br><span style="font-size:13px">Purple scale: darker = higher rate. '
                        'Scales differ by modality.</span>',
                   font=dict(size=20), x=0.5, xanchor='center'),
        height=720, width=1400, paper_bgcolor='white',
        margin=dict(l=10, r=10, t=100, b=20),
    )
    save_plotly(fig_panel, f'figure_panel_all_modalities_{config.END_YEAR}.png', width=1400, height=720)
