"""End-to-end run: DB → loaders → analysis → figures. Each named step reports its own failure to errors.py.

Run from a notebook with `pipeline.run_all()` or from a shell with `python -m cardiac_imaging.pipeline`.
"""
import argparse
import time

import pandas as pd

from . import config, errors, style
from .analysis import change, nb_models, rates, tables
from .db.connection import get_connection, require_tables
from .figures import change as change_fig
from .figures import choropleths, decomposition, density, forest, market_share, ranked_change, rate_trends
from .loaders import claims, demographics, enrollment, providers
from .reporting import run_store

MANIFEST = """
MAIN TEXT
  Figure 1:  Volume / enrollment / rate decomposition (5 modalities × 3 metrics{comp})
  Figure 2:  Market share — stacked area with advanced-modality zoom insets
  Figure 3:  Stress echo — state rates, {b} / {e} / change
  Figure 4:  SPECT MPI   — state rates, {b} / {e} / change
  Figure 5:  Cardiac CTA — state rates, {b} / {e} / change
  Figure 6:  Cardiac MRI (stress CMR included) — state rates, {b} / {e} / change
  Figure 7:  Cardiac PET — state rates, {b} / {e} / change
  Figure 8:  Cardiac CTA, TAVR and CACS — national rate per 1,000 FFS by year, one axis
  Figures 10–12 (ICA, TAVR, CACS state maps): {compmaps}
  Figure {rk}: States ranked by change in CTA rate, {b}→{e}, with median / IQR / P90:P10 of state rates
  (unnumbered composite: all-modality {e} state panel)

SUPPLEMENT
  Figure S1: All-provider density vs CTA rate — multivariable NB
             (single panel + inline unadjusted/adjusted IRR, CI, p)
  Figure S2: Combined forest plot — density IRRs before/after adjustment
  Figure S3: Radiologist density vs CTA rate — multivariable NB (same layout as S1)
  Figure S4: Cardiologist density vs CTA rate — multivariable NB (same layout as S1)
  (whole-workforce density models stay as tables only: density_sensitivity_workforce, workforce_density_by_year)
  Figure S5: Partial-regression plot, Δlog CTA ~ Δlog radiologists+cardiologists + Δlog FFS, {b}→{e}

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
State enrollment: CMS Program Statistics, Original Medicare enrollment by state ({b}, {e})
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
    ctx['df_comp'] = claims.load_comparators(con)   # ICA, TAVR, CACS when switched on: Figure 1 columns + maps; not imaging
    print("Data pipeline complete.\n")


def step_figure1(ctx):
    """Figure 1 and the BASE_YEAR → END_YEAR change summary."""
    print("Building Figure 1: Volume/Enrollment/Rate Decomposition...")
    trend = ctx['trend']
    if not ctx['df_comp'].empty:    # comparators switched on: extra Figure 1 columns after the modalities
        trend = pd.concat([trend, claims.comparator_trend(ctx['df_comp'])], ignore_index=True)
    decomp_df = rates.decompose(trend)
    decomposition.plot_figure1(decomp_df)
    rates.print_change_summary(decomp_df)
    ctx['tables']['national_volume_rates'] = decomp_df.set_index(['procedure_category', 'year'])
    ctx['tables']['change_summary'] = rates.change_summary(decomp_df)
    print("Figure 1 complete.\n")


def step_rate_trends(ctx):
    """Figure 8: national CTA, TAVR and CACS rates per 1,000 FFS by year (TAVR/CACS loaded here even when comparators are off)."""
    print("Building Figure 8: CTA / TAVR / CACS rate trends...")
    con = ctx['con']
    extra = {k: config.ALL_COMPARATORS[k] for k in (config.TAVR_LABEL, config.CACS_LABEL)}
    comp = ctx['df_comp'] if set(extra) <= set(ctx['df_comp']['procedure_category']) else claims.load_comparators(con, extra)
    comp = comp[comp['procedure_category'].isin(extra)]
    cta = ctx['trend'][ctx['trend']['procedure_category'] == 'Cardiac CTA']
    decomp = rates.decompose(pd.concat([cta, claims.comparator_trend(comp)], ignore_index=True))
    rate_trends.plot_rate_trends(decomp)
    ctx['tables']['cta_tavr_cacs_rates'] = decomp.set_index(['procedure_category', 'year'])
    print("Figure 8 complete.\n")


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
    """State rates for BASE_YEAR and END_YEAR, Figures 3–7, the all-modality panel and Figure 13 (ranked CTA change)."""
    print("Building Figures 3–7: State Choropleth Heatmaps...")
    con, df = ctx['con'], ctx['df_detail']
    ctx['state_ffs_end'] = enrollment.load_state_ffs(con, config.END_YEAR)
    ctx['state_ffs_base'] = enrollment.load_state_ffs(con, config.BASE_YEAR)
    r_end = rates.compute_state_rates(df[df['year'] == config.END_YEAR], ctx['state_ffs_end'])
    r_base = rates.compute_state_rates(df[df['year'] == config.BASE_YEAR], ctx['state_ffs_base'])
    ctx['state_rates_end'] = r_end
    deltas = rates.rate_deltas(r_end, r_base)
    choropleths.plot_state_maps(r_base, r_end, deltas)
    ctx['tables'].update({f'state_rates_{config.BASE_YEAR}': r_base.set_index('state'),
                          f'state_rates_{config.END_YEAR}': r_end.set_index('state'),
                          'state_rate_change': deltas.set_index('state')})
    choropleths.plot_all_modalities_panel(r_end)
    disp = rates.state_rate_dispersion(deltas)
    ctx['tables']['state_rate_dispersion'] = disp
    ranked_change.plot_ranked_state_change(deltas, disp, config.END_YEAR, config.BASE_YEAR)
    print("Figures 3–7 complete.\n")


def step_comparator_maps(ctx):
    """Figures 10–12: state rates for BASE_YEAR and END_YEAR and the change, for each comparator procedure (ICA, TAVR, CACS)."""
    comp = ctx['df_comp']
    if not choropleths.COMPARATOR_MAPS:
        print("Comparator maps skipped (config.INCLUDE_COMPARATORS is off).\n")
        return
    for label, fig_num, note in choropleths.COMPARATOR_MAPS:
        print(f"Building Figure {fig_num}: {label} state map...")
        sub = comp[comp['procedure_category'] == label]
        r_end = rates.compute_state_rates(sub[sub['year'] == config.END_YEAR], ctx['state_ffs_end'])
        r_base = rates.compute_state_rates(sub[sub['year'] == config.BASE_YEAR], ctx['state_ffs_base'])
        deltas = rates.rate_deltas(r_end, r_base, missing_as_zero=False)
        choropleths.plot_comparator_state_maps(label, fig_num, note, r_base, r_end, deltas)
        key = {config.ICA_LABEL: 'ica', config.TAVR_LABEL: 'tavr', config.CACS_LABEL: 'cacs'}[label]
        ctx['tables'][f'{key}_state_rates'] = (deltas.set_index('state').drop(columns='procedure_category')
                                               .sort_values(f'rate_per_1000_{config.END_YEAR}', ascending=False))
    print("Figures 10–12 complete.\n")

def step_state_table(ctx):
    """Print and save the END_YEAR state rate table."""
    print("=" * 80)
    print(f"State-Level Procedure Rate per 1,000 FFS Beneficiaries ({config.END_YEAR}, Top 20)")
    print("=" * 80)
    summary = rates.state_summary_table(ctx['state_rates_end'])
    print(summary.head(20).to_string())
    print(f"\n({len(summary)} states total)")
    ctx['tables'][f'state_summary_{config.END_YEAR}'] = summary


def step_density_models(ctx):
    """Fit the CTA density NB models (all, radiology, cardiology); Figures S1, S3, S4; headline IRRs."""
    print(f"Building multivariable NB (age + sex adjustment), {config.END_YEAR}...")
    con, state_ffs = ctx['con'], ctx['state_ffs_end']
    demo = demographics.load_gv_demographics(con, config.GV_YEAR)
    frames = providers.load_cta_density_frames(con, state_ffs, demo)
    n_phys = providers.national_physician_counts(con)
    providers.report_states_without_billers(state_ffs, frames)

    specs = [  # key, density column, x label, title, color, file stem
        ('all', 'npis_per_100k', 'CTA-Billing NPIs per 100,000 FFS Beneficiaries',
         f'Supplemental Figure S1. All-Provider Density vs CTA Rate — Multivariable NB (age + %female), {config.END_YEAR}',
         style.PURPLE, 'figureS1_nb_all_density'),
        ('rad', 'rad_npis_per_100k', 'Radiologist NPIs per 100,000 FFS Beneficiaries',
         f'Supplemental Figure S3. Radiologist Density vs CTA Rate — Multivariable NB, {config.END_YEAR}',
         style.BLUE, 'figureS3_nb_rad_density'),
        ('card', 'card_npis_per_100k', 'Cardiologist NPIs per 100,000 FFS Beneficiaries',
         f'Supplemental Figure S4. Cardiologist Density vs CTA Rate — Multivariable NB, {config.END_YEAR}',
         style.CARD_RED, 'figureS4_nb_card_density'),
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
    """Sensitivity (post hoc, reviewer R2): the S1/S3/S4 models with all radiologists/cardiologists as exposure (tables only)."""
    print("Sensitivity: density models with the whole radiology/cardiology workforce as exposure...")
    con, state_ffs = ctx['con'], ctx['state_ffs_end']
    demo = demographics.load_gv_demographics(con, config.GV_YEAR)
    frames = providers.load_workforce_density_frames(con, state_ffs, demo)
    n_phys = providers.national_workforce_counts(con)
    labels = {'all': ('wf_npis_per_100k', 'Radiologists + cardiologists (any Part B) per 100,000 FFS'),
              'rad': ('wf_rad_npis_per_100k', 'Radiologists (any Part B) per 100,000 FFS'),
              'card': ('wf_card_npis_per_100k', 'Cardiologists (any Part B) per 100,000 FFS')}
    names = {'all': 'All CTA-billing providers', 'rad': 'Radiologists', 'card': 'Cardiologists'}
    rows, wf_fits = [], {}
    for key, (col, label) in labels.items():
        fit = nb_models.fit_density_models(frames[key], col, label)
        nb_models.print_model_report(fit, f'SENSITIVITY — {label}', n_phys[key], config.END_YEAR)
        wf_fits[key] = fit
        orig = ctx['density_fits'][key]
        for exposure, f, n in [('CTA billers (original)', orig, ctx['nb_results'][key]['n_physicians']),
                               ('Whole specialty workforce (sensitivity)', fit, n_phys[key])]:
            sd = float(f['d'][f['density_col']].std(ddof=0))
            irr, per_sd = f['irr_adj'], nb_models.irr_per_sd(f['irr_adj'], sd)
            rows.append({'model': names[key], 'exposure': exposure, 'states': len(f['d']), 'physicians': n,
                         'density mean': float(f['d'][f['density_col']].mean()), 'density SD': sd,
                         'IRR adj per +1 per 100k': irr[0], 'CI low': irr[1], 'CI high': irr[2], 'p': irr[3],
                         'IRR adj per +1 SD': per_sd[0], 'CI low (SD)': per_sd[1], 'CI high (SD)': per_sd[2]})
    table = pd.DataFrame(rows).set_index(['model', 'exposure'])
    ctx['tables']['density_sensitivity_workforce'] = table

    # Whole radiology + cardiology workforce density vs CTA rate in END_YEAR and BASE_YEAR (table workforce_density_by_year;
    # the two figures were dropped by the user 2026-11-04).
    col, label = labels['all']
    by_year = {config.END_YEAR: (wf_fits['all'], n_phys['all'])}
    ffs18 = ctx['state_ffs_base'] if 'state_ffs_base' in ctx else enrollment.load_state_ffs(con, config.BASE_YEAR)
    frames18 = providers.load_workforce_density_frames(con, ffs18, demographics.load_gv_demographics(con, config.BASE_YEAR),
                                                       year=config.BASE_YEAR)
    fit18 = nb_models.fit_density_models(frames18['all'], col, label)
    by_year[config.BASE_YEAR] = (fit18, providers.national_workforce_counts(con, config.BASE_YEAR)['all'])
    rows = []
    for year in (config.END_YEAR, config.BASE_YEAR):
        fit, n = by_year[year]
        sd = float(fit['d'][col].std(ddof=0))
        irr, per_sd = fit['irr_adj'], nb_models.irr_per_sd(fit['irr_adj'], sd)
        rows.append({'year': year, 'states': len(fit['d']), 'physicians': n,
                     'density mean': float(fit['d'][col].mean()), 'density SD': sd,
                     'CTA rate per 1,000 (mean of states)': float(fit['d']['rate_per_1000'].mean()),
                     'IRR adj per +1 per 100k': irr[0], 'CI low': irr[1], 'CI high': irr[2], 'p': irr[3],
                     'IRR adj per +1 SD': per_sd[0], 'CI low (SD)': per_sd[1], 'CI high (SD)': per_sd[2]})
    ctx['tables']['workforce_density_by_year'] = pd.DataFrame(rows).set_index('year')

    # Figure S5: did states that gained physicians also gain CTA use? (change-on-change, BASE_YEAR → END_YEAR)
    # Plotted as the partial-regression view of the count model, which holds the change in FFS enrollment fixed.
    chg = change.change_frame(frames['all'], frames18['all'], config.END_YEAR, config.BASE_YEAR)
    fits = change.fit_change_models(chg, config.END_YEAR, config.BASE_YEAR)
    pr = change.partial_regression_frame(chg, fits, config.END_YEAR, config.BASE_YEAR)
    change_fig.plot_change_partial_regression(pr, fits, config.END_YEAR, config.BASE_YEAR)
    ctx['tables']['workforce_cta_change_by_state'] = chg.merge(pr, on='state', how='left').set_index('state')
    ctx['tables']['workforce_cta_change_models'] = change.change_results_table(fits)


def step_table1_forest(ctx):
    """Table 1 (specialty shares by modality) and the Figure S2 forest plot."""
    table1 = tables.specialty_distribution(ctx['con'])
    ctx['tables']['table1_specialty_distribution'] = table1
    share_rad, share_card = tables.cta_shares(table1)
    print("\nBuilding Figure S2: Combined density-IRR forest plot...")
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
    ('figure8_rate_trends', step_rate_trends),
    ('figure2_market_share', step_figure2),
    ('figures3_7_state_maps', step_state_maps),
    ('figures10_11_comparator_maps', step_comparator_maps),
    ('state_summary_table', step_state_table),
    ('density_models_fig8_S1_S2', step_density_models),
    ('density_sensitivity_workforce', step_workforce_sensitivity),
    ('table1_and_figureS2_forest', step_table1_forest),
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
        on = bool(config.COMPARATORS)
        print(MANIFEST.format(la=config.TIFF_LINEART_DPI, mp=config.TIFF_PANEL_DPI, out=config.OUTPUT_DIR, b=config.BASE_YEAR,
                              e=config.END_YEAR, rk=style.RANKED_FIG_NUM, comp=' + ICA + TAVR + CACS' if on else '',
                              compmaps='on' if on else 'switched off (config.INCLUDE_COMPARATORS)'))
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
