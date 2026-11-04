"""Catalog of every output figure: file stem → label, section, title and caption (feeds the run gallery and PDF)."""
from .. import config
from ..style import PROC_ORDER

B, E = config.BASE_YEAR, config.END_YEAR

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
             [f'state_rates_{B}', f'state_rates_{E}', 'state_rate_change']),
    'ica_map': (['figures.choropleths:plot_comparator_state_maps', 'figures.choropleths:plot_one_state_map',
                 'analysis.rates:compute_state_rates', 'analysis.rates:rate_deltas', 'loaders.claims:load_comparator_detail',
                 'loaders.enrollment:load_state_ffs', 'pipeline:step_comparator_maps'],
                ['ica_state_rates']),
    'tavr_map': (['figures.choropleths:plot_comparator_state_maps', 'figures.choropleths:plot_one_state_map',
                  'analysis.rates:compute_state_rates', 'analysis.rates:rate_deltas', 'loaders.claims:load_comparator_detail',
                  'loaders.enrollment:load_state_ffs', 'pipeline:step_comparator_maps'],
                 ['tavr_state_rates']),
    'cacs_map': (['figures.choropleths:plot_comparator_state_maps', 'figures.choropleths:plot_one_state_map',
                  'analysis.rates:compute_state_rates', 'analysis.rates:rate_deltas', 'loaders.claims:load_comparator_detail',
                  'loaders.enrollment:load_state_ffs', 'pipeline:step_comparator_maps'],
                 ['cacs_state_rates']),
    'workforce': (['figures.density:plot_density_fit', 'pipeline:step_workforce_sensitivity',
                   'loaders.providers:load_workforce_density_frames', 'analysis.nb_models:fit_density_models',
                   'analysis.nb_models:density_partial_curve', 'loaders.demographics:load_gv_demographics'],
                  ['workforce_density_by_year', 'density_sensitivity_workforce']),
    'ranked': (['figures.ranked_change:plot_ranked_state_change', 'analysis.rates:state_rate_dispersion',
                'analysis.rates:rate_deltas', 'analysis.rates:compute_state_rates', 'loaders.enrollment:load_state_ffs',
                'loaders.claims:load_detail', 'pipeline:step_state_maps'],
               ['state_rate_change', 'state_rate_dispersion']),
    'change': (['figures.change:plot_change_partial_regression', 'analysis.change:change_frame',
                'analysis.change:fit_change_models', 'analysis.change:partial_regression_frame',
                'analysis.change:change_results_table',
                'loaders.providers:load_workforce_density_frames', 'pipeline:step_workforce_sensitivity'],
               ['workforce_cta_change_by_state', 'workforce_cta_change_models']),
    'panel': (['figures.choropleths:plot_all_modalities_panel', 'analysis.rates:compute_state_rates',
               'loaders.enrollment:load_state_ffs', 'loaders.claims:load_detail', 'pipeline:step_state_maps'],
              [f'state_rates_{E}', f'state_summary_{E}']),
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
                 'for each imaging modality, invasive coronary angiography (CPT 93454–93461), TAVR (CPT 33361–33366) and '
                 'coronary artery calcium score (CPT 75571), '
                 f'{B}–{E}. TAVR services ≈ 2 × procedures (co-surgeon billing).', **_src('decomposition')),
    dict(stem='figure2_market_share', label='Figure 2', section='Main text',
         title='Modality market share by setting',
         caption='Share of cardiac imaging volume by modality in urban/rural × office/facility segments, '
                 'with zoom insets for CTA + CMR + PET.', **_src('market_share')),
    *[dict(stem=f'figure{n}_{proc.lower().replace(" ", "_")}_state_maps', label=f'Figure {n}', section='Main text',
           title=f'{proc}: state rates {B} / {E} / change',
           caption=f'{proc} rate per 1,000 FFS beneficiaries by state in {B} and {E}, and the change '
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
         title=f'Invasive coronary angiography: state rates {B} / {E} / change',
         caption='Invasive coronary angiography (diagnostic catheterization with coronary angiography, CPT 93454–93461) '
                 f'rate per 1,000 FFS beneficiaries by state in {B} and {E}, and the change (red = decrease, '
                 'blue = increase). Same layout as Figures 3–7. Territories excluded.', **_src('ica_map')),
    dict(stem='figure11_tavr_state_maps', label='Figure 11', section='Main text',
         title=f'TAVR: state rates {B} / {E} / change',
         caption='Transcatheter aortic valve replacement (CPT 33361–33366) services per 1,000 FFS beneficiaries by state '
                 f'in {B} and {E}, and the change. TAVR is usually billed by two co-surgeons, so services ≈ 2 × '
                 f'procedures. States with no {B} rows are grey. Same layout as Figures 3–7.', **_src('tavr_map')),
    dict(stem='figure12_cacs_state_maps', label='Figure 12', section='Main text',
         title=f'Coronary artery calcium score: state rates {B} / {E} / change',
         caption=f'Coronary artery calcium score (CPT 75571) services per 1,000 FFS beneficiaries by state in {B} and {E}, '
                 'and the change. States with no rows in a year (none, or suppressed) are grey. Same layout as Figures 3–7.',
         **_src('cacs_map')),
    dict(stem='figure13_cta_state_ranked_change', label='Figure 13', section='Main text',
         title=f'States ranked by change in CTA rate, {B}→{E}',
         caption=f'Each state\'s change in CTA services per 1,000 FFS beneficiaries, {B}→{E}, largest at the top, '
                 f'labelled with the {B} → {E} rates; dashed line = median state change. Box: median, IQR and '
                 'P90/P10 ratio of the state rates in each year.', **_src('ranked')),
    dict(stem=f'figure_panel_all_modalities_{E}', label='Composite', section='Composite',
         title=f'All modalities, {E} state rates',
         caption=f'Unnumbered composite of {E} state rates for all five modalities (optional Central Illustration).',
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
      for num, year in [('S3', E), ('S4', B)]],
    dict(stem='figureS5_cta_change_partial_regression', label='Figure S5', section='Supplement',
         title=f'Change in CTA services vs change in radiologist + cardiologist numbers, {B}→{E} (partial regression)',
         caption='Added-variable plot for the count model Δlog CTA = α + β·Δlog physicians + γ·Δlog FFS enrollment: '
                 'each state is plotted after removing the part of both changes explained by its change in FFS '
                 'enrollment, so the slope is the adjusted elasticity β (line through the origin, 95% band from '
                 'HC3 SEs). Radiologists + cardiologists billing any Part B service. The unadjusted Δ rate ~ Δ '
                 'density slopes remain in the model table. Post hoc.', **_src('change')),
]

SECTIONS = ['Main text', 'Composite', 'Supplement']
