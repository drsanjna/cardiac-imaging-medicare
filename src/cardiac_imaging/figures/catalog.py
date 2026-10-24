"""Catalog of every output figure: file stem → label, section, title and caption (feeds the run gallery and PDF)."""
from ..style import PROC_ORDER

_MAP_NUMBERS = {proc: i + 3 for i, proc in enumerate(PROC_ORDER)}   # Figures 3–7, same order as choropleths.py

FIGURES = [
    dict(stem='figure1_decomposition', label='Figure 1', section='Main text',
         title='Volume vs FFS enrollment vs utilization rate',
         caption='Annual procedure volume, national FFS enrollment and rate per 1,000 beneficiaries '
                 'for each modality, 2018–2023.'),
    dict(stem='figure2_market_share', label='Figure 2', section='Main text',
         title='Modality market share by setting',
         caption='Share of cardiac imaging volume by modality in urban/rural × office/facility segments, '
                 'with zoom insets for CTA + CMR + PET.'),
    *[dict(stem=f'figure{n}_{proc.lower().replace(" ", "_")}_state_maps', label=f'Figure {n}', section='Main text',
           title=f'{proc}: state rates 2018 / 2023 / change',
           caption=f'{proc} rate per 1,000 FFS beneficiaries by state in 2018 and 2023, and the change '
                   '(red = decrease, blue = increase). Territories excluded.')
      for proc, n in _MAP_NUMBERS.items()],
    dict(stem='figure8_nb_all_density', label='Figure 8', section='Main text',
         title='All-provider density vs CTA rate',
         caption='State CTA rate vs CTA-billing NPIs per 100,000 FFS beneficiaries, with unadjusted and '
                 'age/sex-adjusted negative binomial fits.'),
    dict(stem='figure9_density_irr_forest', label='Figure 9', section='Main text',
         title='Density IRRs before and after adjustment',
         caption='Forest plot of density incidence rate ratios for all providers, radiologists and cardiologists.'),
    dict(stem='figure_panel_all_modalities_2023', label='Composite', section='Composite',
         title='All modalities, 2023 state rates',
         caption='Unnumbered composite of 2023 state rates for all five modalities (optional Central Illustration).'),
    dict(stem='figureS1_nb_rad_density', label='Figure S1', section='Supplement',
         title='Radiologist density vs CTA rate',
         caption='Same model as Figure 8, using radiologist NPIs per 100,000 FFS beneficiaries.'),
    dict(stem='figureS2_nb_card_density', label='Figure S2', section='Supplement',
         title='Cardiologist density vs CTA rate',
         caption='Same model as Figure 8, using cardiologist NPIs per 100,000 FFS beneficiaries.'),
]

SECTIONS = ['Main text', 'Composite', 'Supplement']
