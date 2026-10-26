"""Catalog of every output figure: file stem → label, section, title and caption (feeds the run gallery and PDF)."""
from ..style import PROC_ORDER

# Code behind each chart ("module:function", plotting function first) and the result tables it draws on.
_CLAIMS = ['loaders.claims:load_detail', 'loaders.claims:aggregate_segments']
_SRC = {
    'decomposition': (['figures.decomposition:plot_figure1', 'analysis.rates:decompose', 'analysis.rates:change_summary',
                       'loaders.claims:national_trend', 'loaders.claims:comparator_trend', 'loaders.claims:load_comparator_detail',
                       *_CLAIMS, 'pipeline:step_figure1'],
                      ['national_volume_rates', 'change_summary']),
    'market_share': (['figures.market_share:plot_figure2', 'analysis.rates:market_share_by_segment',
                      'analysis.rates:national_market_share', *_CLAIMS, 'pipeline:step_figure2'],
                     ['national_market_share']),
    'maps': (['figures.choropleths:plot_state_maps', 'analysis.rates:compute_state_rates', 'analysis.rates:rate_deltas',
              'loaders.enrollment:load_state_ffs', 'loaders.claims:load_detail', 'pipeline:step_state_maps'],
             ['state_rates_2018', 'state_rates_2023', 'state_rate_change']),
    'ica_map': (['figures.choropleths:plot_comparator_state_maps', 'figures.choropleths:plot_one_state_map',
                 'analysis.rates:compute_state_rates', 'analysis.rates:rate_deltas', 'loaders.claims:load_comparator_detail',
                 'loaders.enrollment:load_state_ffs', 'pipeline:step_comparator_maps'],
                ['ica_state_rates']),
    'tavr_map': (['figures.choropleths:plot_comparator_state_maps', 'figures.choropleths:plot_one_state_map',
                  'analysis.rates:compute_state_rates', 'analysis.rates:rate_deltas', 'loaders.claims:load_comparator_detail',
                  'loaders.enrollment:load_state_ffs', 'pipeline:step_comparator_maps'],
                 ['tavr_state_rates']),
    'workforce': (['figures.density:plot_density_fit', 'pipeline:step_workforce_sensitivity',
                   'loaders.providers:load_workforce_density_frames', 'analysis.nb_models:fit_density_models',
                   'analysis.nb_models:density_partial_curve', 'loaders.demographics:load_gv_demographics'],
                  ['workforce_density_by_year', 'density_sensitivity_workforce']),
    'change': (['figures.change:plot_change_on_change', 'analysis.change:change_frame',
                'analysis.change:fit_change_models', 'analysis.change:change_results_table',
                'loaders.providers:load_workforce_density_frames', 'pipeline:step_workforce_sensitivity'],
               ['workforce_cta_change_by_state', 'workforce_cta_change_models']),
    'panel': (['figures.choropleths:plot_all_modalities_panel', 'analysis.rates:compute_state_rates',
               'loaders.enrollment:load_state_ffs', 'loaders.claims:load_detail', 'pipeline:step_state_maps'],
              ['state_rates_2023', 'state_summary_2023']),
    'density': (['figures.density:plot_density_fit', 'analysis.nb_models:fit_density_models', 'analysis.nb_models:fit_nb_design',
                 'analysis.nb_models:density_partial_curve', 'loaders.providers:load_cta_density_frames',
                 'loaders.demographics:load_gv_demographics', 'pipeline:step_density_models'],
                ['nb_density_models', 'filter_log']),
    'forest': (['figures.forest:plot_forest', 'analysis.tables:specialty_distribution', 'analysis.tables:cta_shares',
                'analysis.nb_models:fit_density_models', 'pipeline:step_table1_forest', 'pipeline:step_density_models'],
               ['nb_density_models', 'table1_specialty_distribution']),
}


def _src(kind):
    """{'sources': [...], 'tables': [...]} for one chart kind."""
    code, tables = _SRC[kind]
    return dict(sources=code, tables=tables)


_MAP_NUMBERS = {proc: i + 3 for i, proc in enumerate(PROC_ORDER)}   # Figures 3–7, same order as choropleths.py

FIGURES = [
    dict(stem='figure1_decomposition', label='Figure 1', section='Main text',
         title='Volume vs FFS enrollment vs utilization rate',
         caption='Annual procedure volume, national FFS enrollment and rate per 1,000 beneficiaries '
                 'for each imaging modality, invasive coronary angiography (CPT 93454–93461) and TAVR (CPT 33361–33366), '
                 '2018–2023. TAVR services ≈ 2 × procedures (co-surgeon billing).', **_src('decomposition')),
    dict(stem='figure2_market_share', label='Figure 2', section='Main text',
         title='Modality market share by setting',
         caption='Share of cardiac imaging volume by modality in urban/rural × office/facility segments, '
                 'with zoom insets for CTA + CMR + PET.', **_src('market_share')),
    *[dict(stem=f'figure{n}_{proc.lower().replace(" ", "_")}_state_maps', label=f'Figure {n}', section='Main text',
           title=f'{proc}: state rates 2018 / 2023 / change',
           caption=f'{proc} rate per 1,000 FFS beneficiaries by state in 2018 and 2023, and the change '
                   '(red = decrease, blue = increase). Territories excluded.', **_src('maps'))
      for proc, n in _MAP_NUMBERS.items()],
    dict(stem='figure8_nb_all_density', label='Figure 8', section='Main text',
         title='All-provider density vs CTA rate',
         caption='State CTA rate vs CTA-billing NPIs per 100,000 FFS beneficiaries, with unadjusted and '
                 'age/sex-adjusted negative binomial fits.', **_src('density')),
    dict(stem='figure9_density_irr_forest', label='Figure 9', section='Main text',
         title='Density IRRs before and after adjustment',
         caption='Forest plot of density incidence rate ratios for all providers, radiologists and cardiologists.',
         **_src('forest')),
    dict(stem='figure10_invasive_coronary_angiography_state_maps', label='Figure 10', section='Main text',
         title='Invasive coronary angiography: state rates 2018 / 2023 / change',
         caption='Invasive coronary angiography (diagnostic catheterization with coronary angiography, CPT 93454–93461) '
                 'rate per 1,000 FFS beneficiaries by state in 2018 and 2023, and the change (red = decrease, '
                 'blue = increase). Same layout as Figures 3–7. Territories excluded.', **_src('ica_map')),
    dict(stem='figure11_tavr_state_maps', label='Figure 11', section='Main text',
         title='TAVR: state rates 2018 / 2023 / change',
         caption='Transcatheter aortic valve replacement (CPT 33361–33366) services per 1,000 FFS beneficiaries by state '
                 'in 2018 and 2023, and the change. TAVR is usually billed by two co-surgeons, so services ≈ 2 × '
                 'procedures. States with no 2018 rows are grey. Same layout as Figures 3–7.', **_src('tavr_map')),
    dict(stem='figure_panel_all_modalities_2023', label='Composite', section='Composite',
         title='All modalities, 2023 state rates',
         caption='Unnumbered composite of 2023 state rates for all five modalities (optional Central Illustration).',
         **_src('panel')),
    dict(stem='figureS1_nb_rad_density', label='Figure S1', section='Supplement',
         title='Radiologist density vs CTA rate',
         caption='Same model as Figure 8, using radiologist NPIs per 100,000 FFS beneficiaries.', **_src('density')),
    dict(stem='figureS2_nb_card_density', label='Figure S2', section='Supplement',
         title='Cardiologist density vs CTA rate',
         caption='Same model as Figure 8, using cardiologist NPIs per 100,000 FFS beneficiaries.', **_src('density')),
    *[dict(stem=f'figure{num}_workforce_density_{year}', label=f'Figure {num}', section='Supplement',
           title=f'Radiologist + cardiologist density vs CTA rate, {year}',
           caption=f'Same layout as Figure S2. x-axis: unique radiologists + cardiologists billing any Part B service in '
                   f'{year} per 100,000 FFS beneficiaries (not selected by CTA billing); y-axis: {year} CTA rate. '
                   'Unadjusted and age/sex-adjusted NB fits (post hoc, responds to the circularity concern).',
           **_src('workforce'))
      for num, year in [('S4', 2023), ('S5', 2018)]],
    dict(stem='figureS6_workforce_change_vs_cta_change', label='Figure S6', section='Supplement',
         title='Change in radiologist + cardiologist density vs change in CTA rate, 2018→2023',
         caption='Each state: change in radiologists + cardiologists (any Part B) per 100,000 FFS beneficiaries vs '
                 'change in CTA rate per 1,000, 2018→2023. OLS fits (robust SE) with and without DC and MN; the box '
                 'also gives a count model that holds the change in FFS enrollment fixed (both axes share the FFS '
                 'denominator). Post hoc.', **_src('change')),
]

SECTIONS = ['Main text', 'Composite', 'Supplement']
