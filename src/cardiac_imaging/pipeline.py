"""End-to-end run: DB → loaders → analysis → figures. Each named step reports its own failure to errors.py.

Run from a notebook with `pipeline.run_all()` or from a shell with `python -m cardiac_imaging.pipeline`.
"""
import argparse

from . import config, errors, style
from .analysis import nb_models, rates, tables
from .db.connection import get_connection, require_tables
from .figures import choropleths, decomposition, density, forest, market_share
from .loaders import claims, demographics, enrollment, providers

MANIFEST = """
MAIN TEXT
  Figure 1:  Volume / enrollment / rate decomposition (5 modalities × 3 metrics)
  Figure 2:  Market share — stacked area with advanced-modality zoom insets
  Figure 3:  Echo        — state rates, 2018 / 2023 / change
  Figure 4:  SPECT       — state rates, 2018 / 2023 / change
  Figure 5:  Cardiac CTA — state rates, 2018 / 2023 / change
  Figure 6:  Cardiac MRI — state rates, 2018 / 2023 / change
  Figure 7:  Cardiac PET — state rates, 2018 / 2023 / change
  Figure 8:  All-provider density vs CTA rate — multivariable NB
             (single panel + inline unadjusted/adjusted IRR, CI, p)
  Figure 9:  Combined forest plot — density IRRs before/after adjustment (FINAL)
  (unnumbered composite: all-modality 2023 state panel)

SUPPLEMENT
  Figure S1: Radiologist density vs CTA rate — multivariable NB
             (single panel + inline unadjusted/adjusted IRR, CI, p)
  Figure S2: Cardiologist density vs CTA rate — multivariable NB
             (single panel + inline unadjusted/adjusted IRR, CI, p)

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
    if ctx.get('con') is None:
        ctx['con'] = get_connection(ctx['database'], read_only=True)
    require_tables(ctx['con'])


def step_load_claims(ctx):
    con = ctx['con']
    claims.verify_specialty_strings(con)
    print("=" * 80 + "\nLOADING AND PROCESSING DATA\n" + "=" * 80)
    ctx['df_detail'] = claims.load_detail(con)
    ctx['df_agg'] = claims.aggregate_segments(ctx['df_detail'])
    ctx['trend'] = claims.national_trend(ctx['df_agg'])
    print("Data pipeline complete.\n")


def step_figure1(ctx):
    print("Building Figure 1: Volume/Enrollment/Rate Decomposition...")
    decomp_df = rates.decompose(ctx['trend'])
    decomposition.plot_figure1(decomp_df)
    rates.print_change_summary(decomp_df)
    print("Figure 1 complete.\n")


def step_figure2(ctx):
    print("Building Figure 2: Market Share...")
    market_share.plot_figure2(rates.market_share_by_segment(ctx['df_agg']))
    print("National Market Share (%):")
    print(rates.national_market_share(ctx['trend']).round(3).to_string())
    print("Figure 2 complete.\n")


def step_state_maps(ctx):
    print("Building Figures 3–7: State Choropleth Heatmaps...")
    con, df = ctx['con'], ctx['df_detail']
    ctx['state_ffs_2023'] = enrollment.load_state_ffs(con, config.END_YEAR)
    ctx['state_ffs_2018'] = enrollment.load_state_ffs(con, config.BASE_YEAR)
    r23 = rates.compute_state_rates(df[df['year'] == config.END_YEAR], ctx['state_ffs_2023'])
    r18 = rates.compute_state_rates(df[df['year'] == config.BASE_YEAR], ctx['state_ffs_2018'])
    ctx['state_rates_2023'] = r23
    choropleths.plot_state_maps(r18, r23, rates.rate_deltas(r23, r18))
    choropleths.plot_all_modalities_panel(r23)
    print("Figures 3–7 complete.\n")


def step_state_table(ctx):
    print("=" * 80)
    print(f"State-Level Procedure Rate per 1,000 FFS Beneficiaries ({config.END_YEAR}, Top 20)")
    print("=" * 80)
    summary = rates.state_summary_table(ctx['state_rates_2023'])
    print(summary.head(20).to_string())
    print(f"\n({len(summary)} states total)")


def step_density_models(ctx):
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
        nb_models.print_model_report(fit, title, n_phys[key], config.END_YEAR)
        density.plot_density_fit(fit, title, color, fname, n_phys[key])
        ctx['nb_results'][key] = dict(irr_un=fit['irr_un'], irr_adj=fit['irr_adj'],
                                      n=len(fit['d']), n_physicians=n_phys[key])


def step_table1_forest(ctx):
    table1 = tables.specialty_distribution(ctx['con'])
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
    ('state_summary_table', step_state_table),
    ('density_models_fig8_S1_S2', step_density_models),
    ('table1_and_figure9_forest', step_table1_forest),
]


def run_all(con=None, database=None, report_errors=True):
    """Run every step in order; on failure, report it (log file + optional GitHub issue) and re-raise."""
    style.apply_rcparams()
    ctx = {'con': con, 'database': database}
    for name, fn in STEPS:
        try:
            fn(ctx)
        except Exception as exc:
            if report_errors:
                errors.report(exc, name)
            raise
    print("\n" + "=" * 80 + "\nALL FIGURES COMPLETE — FINAL NUMBERING\n" + "=" * 80)
    print(MANIFEST.format(la=config.TIFF_LINEART_DPI, mp=config.TIFF_PANEL_DPI, out=config.OUTPUT_DIR))
    return ctx


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db', default=None, help=f"Database file or md:<name> (default {config.DATABASE})")
    p.add_argument('--no-report', action='store_true', help="Don't write error logs or open GitHub issues")
    args = p.parse_args()
    run_all(database=args.db, report_errors=not args.no_report)


if __name__ == '__main__':
    main()
