"""Regression tests on the real CMS data (skipped when ~/Downloads/cms_parquet/cms.duckdb is absent, e.g. in CI).

These pin the published numbers: if a code change moves them, the change is a bug unless deliberately approved.
Run before pushing analysis changes:  pytest -m real_data
"""
import json

import duckdb
import pytest

from cardiac_imaging import config, pipeline
from cardiac_imaging.db import schema
from conftest import REAL_DB

pytestmark = [pytest.mark.real_data,
              pytest.mark.skipif(not REAL_DB.exists(), reason='real cms.duckdb not available')]

# End year 2024 since 2026-11-02 (user decision; 2023 values: 1.1878 / 1.2307 / 1.1572).
GOLDEN_IRR = {'All CTA-billing providers': (1.1575, 1.1099, 1.2071),
              'Radiologists': (1.2301, 1.1486, 1.3174),
              'Cardiologists': (1.0798, 1.0117, 1.1524)}
# Sensitivity (R2 circularity): adjusted IRR per +1 radiologist/cardiologist (any Part B) per 100,000 FFS, 2024.
GOLDEN_WORKFORCE_IRR = {'All CTA-billing providers': 1.0032, 'Radiologists': 1.0043, 'Cardiologists': 1.0089}
GOLDEN_ROWS = {2018: 9_961_865, 2019: 10_140_228, 2020: 9_449_361, 2021: 9_886_177, 2022: 9_755_427, 2023: 9_660_647,
               2024: 9_781_673}


def test_real_database_matches_data_model():
    """The live database still matches db/schema.py."""
    con = duckdb.connect(str(REAL_DB), read_only=True)
    assert schema.validate(con) == []
    rows = dict(con.execute("SELECT year, COUNT(*) FROM partb_provider_service GROUP BY year").fetchall())
    assert rows == GOLDEN_ROWS


@pytest.fixture(scope='module')
def real_run(tmp_path_factory):
    """One full run on the real data (no TIFFs, not published, isolated folders)."""
    import plotly.graph_objects as go
    from PIL import Image
    from cardiac_imaging import config
    from conftest import make_repo
    base = tmp_path_factory.mktemp('real')
    mp = pytest.MonkeyPatch()
    for k, v in dict(REPO_ROOT=make_repo(base / 'repo'), RUNS_DIR=base / 'runs', OUTPUT_DIR=base / 'out',
                     LOG_DIR=base / 'logs', PUBLISH_RUNS=False, SAVE_TIFF=False).items():
        mp.setattr(config, k, v)
    mp.setattr(go.Figure, 'write_image', lambda self, p, **kw: Image.new('RGB', (10, 10)).save(p))
    ctx = pipeline.run_all(database=str(REAL_DB), report_errors=False)
    mp.undo()
    return ctx


def test_headline_irrs_unchanged(real_run):
    """Adjusted density IRRs and CIs match the published values to 4 decimals."""
    for model, (irr, lo, hi) in GOLDEN_IRR.items():
        h = real_run['headline'][f'Adjusted IRR — {model}']
        assert (round(h['irr'], 4), round(h['lo'], 4), round(h['hi'], 4)) == (irr, lo, hi), model


def test_table1_cta_shares_unchanged(real_run):
    """Radiologists read 58.3% and cardiologists 37.6% of cardiac CTAs in 2024."""
    t1 = real_run['tables']['table1_specialty_distribution']
    assert round(t1.loc['Cardiac CTA', 'Radiology %'], 1) == 58.3
    assert round(t1.loc['Cardiac CTA', 'Cardiology %'], 1) == 37.6


def test_physician_counts_and_states(real_run):
    """Model sizes: 51 / 49 / 50 states; 3,223 / 1,746 / 1,353 unique physicians (2024)."""
    nb = real_run['tables']['nb_density_models']
    assert list(nb['states']) == [51, 49, 50] and list(nb['physicians']) == [3223, 1746, 1353]


def test_change_summary_unchanged(real_run):
    """2018→2024 rate change per modality under the ischaemic-testing scope set 2026-11-04 (stress echo instead of resting
    TTE; CMR without the 75565 add-on; comparators off). Before that change: Echo (TTE) +6.8, SPECT −25.6, CTA +277.9,
    MRI +173.6, PET +81.8, ICA −15.3, TAVR +72.3, CACS +554.1."""
    cs = real_run['tables']['change_summary']['rate_pct'].round(1).to_dict()
    expected = {'Stress Echo': -28.8, 'SPECT MPI': -25.6, 'Cardiac CTA': 277.9, 'Cardiac MRI': 150.9, 'Cardiac PET': 81.8}
    if config.COMPARATORS:
        expected.update({'Invasive Coronary Angiography': -15.3, 'TAVR': 72.3, 'CACS': 554.1})
    assert cs == expected


def test_manifest_records_real_rows(real_run):
    """The run records all 68,635,378 claim rows (2018–2024)."""
    m = json.loads((real_run['run_dir'] / 'manifest.json').read_text())
    assert m['data']['claims_rows_total'] == sum(GOLDEN_ROWS.values())


def test_workforce_sensitivity_irrs(real_run):
    """Whole-workforce exposure (not selected by CTA billing) still gives adjusted IRRs above 1 for all three models."""
    t = real_run['tables']['density_sensitivity_workforce'].xs('Whole specialty workforce (sensitivity)', level='exposure')
    for model, irr in GOLDEN_WORKFORCE_IRR.items():
        assert round(t.loc[model, 'IRR adj per +1 per 100k'], 4) == irr and t.loc[model, 'CI low'] > 1


def test_workforce_density_by_year(real_run):
    """Figures S3/S4: whole-workforce density vs CTA rate is positive in 2024 (IRR 1.0032) and in 2018 (1.0041)."""
    t = real_run['tables']['workforce_density_by_year']
    assert round(t.loc[2024, 'IRR adj per +1 per 100k'], 4) == 1.0032 and t.loc[2024, 'physicians'] == 62103
    assert round(t.loc[2018, 'IRR adj per +1 per 100k'], 4) == 1.0041 and t.loc[2018, 'physicians'] == 57343


def test_workforce_change_models(real_run):
    """Figure S5: Δ rate ~ Δ density slope 0.026 (shared FFS denominator); count model elasticity 0.27, not significant."""
    t = real_run['tables']['workforce_cta_change_models']
    assert round(t.loc['Δ rate ~ Δ density (all states)', 'estimate'], 4) == 0.0265
    c = t.loc['Δlog CTA ~ Δlog physicians + Δlog FFS']
    assert round(c['estimate'], 2) == 0.27 and c['CI low'] < 0 < c['CI high']
