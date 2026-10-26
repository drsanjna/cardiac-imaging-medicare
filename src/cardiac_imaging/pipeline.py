"""End-to-end run: DB → loaders → analysis → figures. Each named step reports its own failure to errors.py.

Run from a notebook with `pipeline.run_all()` or from a shell with `python -m cardiac_imaging.pipeline`.
"""
import argparse
import time

import pandas as pd

from . import config, errors, style
from .analysis import nb_models, rates, tables
from .db.connection import get_connection, require_tables
from .figures import choropleths, decomposition, density, forest, market_share
from .loaders import claims, demographics, enrollment, providers
from .reporting import run_store

MANIFEST = """
MAIN TEXT
  Figure 1:  Volume / enrollment / rate decomposition (5 modalities + ICA + TAVR × 3 metrics)
  Figure 2:  Market share — stacked area with advanced-modality zoom insets
  Figure 3:  Echo        — state rates, 2018 / 2023 / change
  Figure 4:  SPECT       — state rates, 2018 / 2023 / change
  Figure 5:  Cardiac CTA — state rates, 2018 / 2023 / change
  Figure 6:  Cardiac MRI — state rates, 2018 / 2023 / change
  Figure 7:  Cardiac PET — state rates, 2018 / 2023 / change
  Figure 8:  All-provider density vs CTA rate — multivariable NB
             (single panel + inline unadjusted/adjusted IRR, CI, p)
  Figure 9:  Combined forest plot — density IRRs before/after adjustment (FINAL)
  Figure 10: Invasive coronary angiography — state rates, 2018 / 2023 / change
  Figure 11: TAVR — state rates, 2018 / 2023 / change
  (unnumbered composite: all-modality 2023 state panel)

SUPPLEMENT
  Figure S1: Radiologist density vs CTA rate — multivariable NB
             (single panel + inline unadjusted/adjusted IRR, CI, p)
  Figure S2: Cardiologist density vs CTA rate — multivariable NB
             (single panel + inline unadjusted/adjusted IRR, CI, p)
  Table:     Sensitivity — same models with the whole radiology/cardiology workforce as exposure

OUTPUT FORMATS
  Every matplotlib figure: .png (300 DPI working copy) + .tiff (LZW-compressed;
  line art at {la} DPI, large multi-panels at {mp} DPI — raise to 1200 for
  final submission if file sizes allow).
  Plotly choropleths: .png (~300 DPI at print width) + converted .tiff (300 DPI).
  Written to: {out}

POPULATION
  50 states + DC. Excluded everywhere: AS, GU, MP, PR, VI, and unknown/invalid
  state codes (XX, ZZ, blank).

Enrollment: CMS Program Statistics — Original Medicare Enrollment
State enrollment: CMS Monthly Enrollment Reports (2018, 2023)
Claims: Medicare Physician & Other Practitioners by Provider and Service
"""


# ── steps: each takes and extends the shared context dict ───────────────────
def step_connect(ctx):
    """Open the read-only database, check required tables, and record claim rows per year."""
    if ctx.get('con') is None:
        ctx['con'] = get_connection(ctx['database'], read_only=True)
    require_tables(ctx['con'])
    by_year = dict(ctx['con'].execute(
        f"SELECT year, COUNT(*) FROM {config.CLAIMS_TABLE} GROUP BY year ORDER BY year").fetchall())
    ctx['data'] = dict(claims_rows_by_year={str(y): n for y, n in by_year.items()},
                       claims_rows_total=sum(by_year.values()))


def step_load_claims(ctx):
    """Verify specialty strings, load cardiac claim detail, and build segment aggregates + national trend."""
    con = ctx['con']
    claims.verify_specialty_strings(con)
    print("=" * 80 + "\nLOADING AND PROCESSING DATA\n" + "=" * 80)
    ctx['df_detail'] = claims.load_detail(con)
    ctx['df_agg'] = claims.aggregate_segments(ctx['df_detail'])
    ctx['trend'] = claims.national_trend(ctx['df_agg'])
    ctx['df_comp'] = claims.load_comparators(con)   # ICA, TAVR: Figure 1 columns + Figures 10–11; not imaging
    print("Data pipeline complete.\n")


def step_figure1(ctx):
    """Figure 1 and the 2018 → 2023 change summary."""
    print("Building Figure 1: Volume/Enrollment/Rate Decomposition...")
    decomp_df = rates.decompose(pd.concat([ctx['trend'], claims.comparator_trend(ctx['df_comp'])], ignore_index=True))
    decomposition.plot_figure1(decomp_df)
    rates.print_change_summary(decomp_df)
    ctx['tables']['national_volume_rates'] = decomp_df.set_index(['procedure_category', 'year'])
    ctx['tables']['change_summary'] = rates.change_summary(decomp_df)
    print("Figure 1 complete.\n")


def step_figure2(ctx):
    """Figure 2 and the national market share table."""
    print("Building Figure 2: Market Share...")
    market_share.plot_figure2(rates.market_share_by_segment(ctx['df_agg']))
    nat_pct = rates.national_market_share(ctx['trend'])
    print("National Market Share (%):")
    print(nat_pct.round(3).to_string())
    ctx['tables']['national_market_share'] = nat_pct
    print("Figure 2 complete.\n")


def step_state_maps(ctx):
    """State rates for 2018 and 2023, Figures 3–7 and the all-modality panel."""
    print("Building Figures 3–7: State Choropleth Heatmaps...")
    con, df = ctx['con'], ctx['df_detail']
    ctx['state_ffs_2023'] = enrollment.load_state_ffs(con, config.END_YEAR)
    ctx['state_ffs_2018'] = enrollment.load_state_ffs(con, config.BASE_YEAR)
    r23 = rates.compute_state_rates(df[df['year'] == config.END_YEAR], ctx['state_ffs_2023'])
    r18 = rates.compute_state_rates(df[df['year'] == config.BASE_YEAR], ctx['state_ffs_2018'])
    ctx['state_rates_2023'] = r23
    deltas = rates.rate_deltas(r23, r18)
    choropleths.plot_state_maps(r18, r23, deltas)
    ctx['tables'].update(state_rates_2018=r18.set_index('state'), state_rates_2023=r23.set_index('state'),
                         state_rate_change=deltas.set_index('state'))
    choropleths.plot_all_modalities_panel(r23)
    print("Figures 3–7 complete.\n")


def step_comparator_maps(ctx):
    """Figures 10–11: state rates for 2018 and 2023 and the change, for each comparator procedure (ICA, TAVR)."""
    comp = ctx['df_comp']
    for label, fig_num, note in choropleths.COMPARATOR_MAPS:
        print(f"Building Figure {fig_num}: {label} state map...")
        sub = comp[comp['procedure_category'] == label]
        r23 = rates.compute_state_rates(sub[sub['year'] == config.END_YEAR], ctx['state_ffs_2023'])
        r18 = rates.compute_state_rates(sub[sub['year'] == config.BASE_YEAR], ctx['state_ffs_2018'])
        deltas = rates.rate_deltas(r23, r18, missing_as_zero=False)
        choropleths.plot_comparator_state_maps(label, fig_num, note, r18, r23, deltas)
        key = {config.ICA_LABEL: 'ica', config.TAVR_LABEL: 'tavr'}[label]
        ctx['tables'][f'{key}_state_rates'] = (deltas.set_index('state').drop(columns='procedure_category')
                                               .sort_values('rate_per_1000_2023', ascending=False))
    print("Figures 10–11 complete.\n")

def step_state_table(ctx):
    """Print and save the 2023 state rate table."""
    print("=" * 80)
    print(f"State-Level Procedure Rate per 1,000 FFS Beneficiaries ({config.END_YEAR}, Top 20)")
    print("=" * 80)
    summary = rates.state_summary_table(ctx['state_rates_2023'])
    print(summary.head(20).to_string())
    print(f"\n({len(summary)} states total)")
    ctx['tables']['state_summary_2023'] = summary


def step_density_models(ctx):
    """Fit the CTA density NB models (all, radiology, cardiology); Figures 8, S1, S2; headline IRRs."""
    print(f"Building multivariable NB (age + sex adjustment), {config.END_YEAR}...")
    con, state_ffs = ctx['con'], ctx['state_ffs_2023']
    demo = demographics.load_gv_demographics(con, config.GV_YEAR)
    frames = providers.load_cta_density_frames(con, state_ffs, demo)
    n_phys = providers.national_physician_counts(con)
    providers.report_states_without_billers(state_ffs, frames)

    specs = [  # key, density column, x label, title, color, file stem
        ('all', 'npis_per_100k', 'CTA-Billing NPIs per 100,000 FFS Beneficiaries',
         'Figure 8. All-Provider Density vs CTA Rate — Multivariable NB (age + %female), 2023',
         style.PURPLE, 'figure8_nb_all_density'),
        ('rad', 'rad_npis_per_100k', 'Radiologist NPIs per 100,000 FFS Beneficiaries',
         'Supplemental Figure S1. Radiologist Density vs CTA Rate — Multivariable NB, 2023',
         style.BLUE, 'figureS1_nb_rad_density'),
        ('card', 'card_npis_per_100k', 'Cardiologist NPIs per 100,000 FFS Beneficiaries',
         'Supplemental Figure S2. Cardiologist Density vs CTA Rate — Multivariable NB, 2023',
         style.CARD_RED, 'figureS2_nb_card_density'),
    ]
    ctx['nb_results'] = {}
    for key, col, label, title, color, fname in specs:
        fit = nb_models.fit_density_models(frames[key], col, label)
        ctx.setdefault('density_fits', {})[key] = fit   # reused by the workforce sensitivity step
        nb_models.print_model_report(fit, title, n_phys[key], config.END_YEAR)
        density.plot_density_fit(fit, title, color, fname, n_phys[key])
        ctx['nb_results'][key] = dict(irr_un=fit['irr_un'], irr_adj=fit['irr_adj'],
                                      n=len(fit['d']), n_physicians=n_phys[key])
    names = {'all': 'All CTA-billing providers', 'rad': 'Radiologists', 'card': 'Cardiologists'}
    ctx['tables']['nb_density_models'] = nb_models.results_table(ctx['nb_results'], names)
    ctx['headline'] = {f'Adjusted IRR — {names[k]}': dict(zip(('irr', 'lo', 'hi', 'p'), map(float, r['irr_adj'])))
                       for k, r in ctx['nb_results'].items()}


def step_workforce_sensitivity(ctx):
    """Sensitivity (post hoc, reviewer R2): Figure 8/S1/S2 models with all radiologists/cardiologists as exposure."""
    print("Sensitivity: density models with the whole radiology/cardiology workforce as exposure...")
    con, state_ffs = ctx['con'], ctx['state_ffs_2023']
    demo = demographics.load_gv_demographics(con, config.GV_YEAR)
    frames = providers.load_workforce_density_frames(con, state_ffs, demo)
    n_phys = providers.national_workforce_counts(con)
    labels = {'all': ('wf_npis_per_100k', 'Radiologists + cardiologists (any Part B) per 100,000 FFS'),
              'rad': ('wf_rad_npis_per_100k', 'Radiologists (any Part B) per 100,000 FFS'),
              'card': ('wf_card_npis_per_100k', 'Cardiologists (any Part B) per 100,000 FFS')}
    names = {'all': 'All CTA-billing providers', 'rad': 'Radiologists', 'card': 'Cardiologists'}
    rows = []
    for key, (col, label) in labels.items():
        fit = nb_models.fit_density_models(frames[key], col, label)
        nb_models.print_model_report(fit, f'SENSITIVITY — {label}', n_phys[key], config.END_YEAR)
        orig = ctx['density_fits'][key]
        for exposure, f, n in [('CTA billers (original)', orig, ctx['nb_results'][key]['n_physicians']),
                               ('Whole specialty workforce (sensitivity)', fit, n_phys[key])]:
            sd = float(f['d'][f['density_col']].std(ddof=0))
            irr, per_sd = f['irr_adj'], nb_models.irr_per_sd(f['irr_adj'], sd)
            rows.append({'model': names[key], 'exposure': exposure, 'states': len(f['d']), 'physicians': n,
                         'density mean': float(f['d'][f['density_col']].mean()), 'density SD': sd,
                         'IRR adj per +1 per 100k': irr[0], 'CI low': irr[1], 'CI high': irr[2], 'p': irr[3],
                         'IRR adj per +1 SD': per_sd[0], 'CI low (SD)': per_sd[1], 'CI high (SD)': per_sd[2]})
    ctx['tables']['density_sensitivity_workforce'] = pd.DataFrame(rows).set_index(['model', 'exposure'])


def step_table1_forest(ctx):
    """Table 1 (specialty shares by modality) and the Figure 9 forest plot."""
    table1 = tables.specialty_distribution(ctx['con'])
    ctx['tables']['table1_specialty_distribution'] = table1
    share_rad, share_card = tables.cta_shares(table1)
    print("\nBuilding Figure 9: Combined density-IRR forest plot...")
    r = ctx['nb_results']
    forest.plot_forest([
        ('All CTA-billing providers', 'all interpretations',                 r['all'],  style.PURPLE),
        ('Radiologists',              f'{share_rad:.1f}% of interpretations',  r['rad'],  style.BLUE),
        ('Cardiologists',             f'{share_card:.1f}% of interpretations', r['card'], style.CARD_RED),
    ])


STEPS = [
    ('connect_database', step_connect),
    ('load_claims', step_load_claims),
    ('figure1_decomposition', step_figure1),
    ('figure2_market_share', step_figure2),
    ('figures3_7_state_maps', step_state_maps),
    ('figures10_11_comparator_maps', step_comparator_maps),
    ('state_summary_table', step_state_table),
    ('density_models_fig8_S1_S2', step_density_models),
    ('density_sensitivity_workforce', step_workforce_sensitivity),
    ('table1_and_figure9_forest', step_table1_forest),
]


def run_all(con=None, database=None, report_errors=True, record=True, label=None):
    """Run every step in order; on failure, report it (log file + optional GitHub issue) and re-raise.

    record=True saves everything into a new folder under config.RUNS_DIR (figures, tables, console.log,
    manifest.json, gallery.html, all_figures.pdf) and refreshes the all-runs index.
    """
    style.apply_rcparams()
    ctx = {'con': con, 'database': database, 'tables': {}}
    run = run_store.Run(label) if record else None
    ctx['run_dir'] = run.dir if run else None
    error = None
    try:
        for name, fn in STEPS:
            t0 = time.time()
            try:
                fn(ctx)
            except Exception as exc:
                error = (name, exc)
                if report_errors:
                    errors.report(exc, name)
                raise
            finally:
                if run:
                    run.log_step(name, time.time() - t0, ok=error is None)
        print("\n" + "=" * 80 + "\nALL FIGURES COMPLETE — FINAL NUMBERING\n" + "=" * 80)
        print(MANIFEST.format(la=config.TIFF_LINEART_DPI, mp=config.TIFF_PANEL_DPI, out=config.OUTPUT_DIR))
    finally:
        if run:
            run.finish(ctx, error)
    return ctx


def main():
    """Command-line entry point: parse options and run the pipeline."""
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db', default=None, help=f"Database file or md:<name> (default {config.DATABASE})")
    p.add_argument('--no-report', action='store_true', help="Don't write error logs or open GitHub issues")
    p.add_argument('--label', help="Short note appended to the run folder name, e.g. 'after-RUCA-fix'")
    p.add_argument('--no-tiff', action='store_true', help="Skip submission TIFFs (much faster, smaller run folder)")
    p.add_argument('--no-record', action='store_true', help=f"Write figures to {config.OUTPUT_DIR} instead of a run folder")
    args = p.parse_args()
    if args.no_tiff:
        config.SAVE_TIFF = False
    run_all(database=args.db, report_errors=not args.no_report, record=not args.no_record, label=args.label)


if __name__ == '__main__':
    main()
