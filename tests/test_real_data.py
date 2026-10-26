"""Regression tests on the real CMS data (skipped when ~/Downloads/cms_parquet/cms.duckdb is absent, e.g. in CI).

These pin the published numbers: if a code change moves them, the change is a bug unless deliberately approved.
Run before pushing analysis changes:  pytest -m real_data
"""
import json

import duckdb
import pytest

from cardiac_imaging import pipeline
from cardiac_imaging.db import schema
from conftest import REAL_DB

pytestmark = [pytest.mark.real_data,
              pytest.mark.skipif(not REAL_DB.exists(), reason='real cms.duckdb not available')]

GOLDEN_IRR = {'All CTA-billing providers': (1.1878, 1.1459, 1.2312),
              'Radiologists': (1.2307, 1.1475, 1.3198),
              'Cardiologists': (1.1572, 1.0775, 1.2428)}
# Sensitivity (R2 circularity): adjusted IRR per +1 radiologist/cardiologist (any Part B) per 100,000 FFS, 2023.
GOLDEN_WORKFORCE_IRR = {'All CTA-billing providers': 1.0049, 'Radiologists': 1.0067, 'Cardiologists': 1.0133}
GOLDEN_ROWS = {2018: 9_961_865, 2019: 10_140_228, 2020: 9_449_361, 2021: 9_886_177, 2022: 9_755_427, 2023: 9_660_647}


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
    """Radiologists read 59.1% and cardiologists 37.2% of cardiac CTAs in 2023."""
    t1 = real_run['tables']['table1_specialty_distribution']
    assert round(t1.loc['Cardiac CTA', 'Radiology %'], 1) == 59.1
    assert round(t1.loc['Cardiac CTA', 'Cardiology %'], 1) == 37.2


def test_physician_counts_and_states(real_run):
    """Model sizes: 51 / 49 / 46 states; 2,847 / 1,616 / 1,140 unique physicians."""
    nb = real_run['tables']['nb_density_models']
    assert list(nb['states']) == [51, 49, 46] and list(nb['physicians']) == [2847, 1616, 1140]


def test_change_summary_unchanged(real_run):
    """2018→2023 rate change per modality (PET = 78491/78492/78430/78431 since 2026-10-24; was −34.4 without PET/CT)."""
    cs = real_run['tables']['change_summary']['rate_pct'].round(1).to_dict()
    assert cs == {'Echo': 4.1, 'SPECT': -21.0, 'Cardiac CTA': 199.4, 'Cardiac MRI': 122.9, 'Cardiac PET': 55.4,
                  'Invasive Coronary Angiography': -14.8, 'TAVR': 61.6}


def test_manifest_records_real_rows(real_run):
    """The run records all 58,853,705 claim rows."""
    m = json.loads((real_run['run_dir'] / 'manifest.json').read_text())
    assert m['data']['claims_rows_total'] == sum(GOLDEN_ROWS.values())


def test_workforce_sensitivity_irrs(real_run):
    """Whole-workforce exposure (not selected by CTA billing) still gives adjusted IRRs above 1 for all three models."""
    t = real_run['tables']['density_sensitivity_workforce'].xs('Whole specialty workforce (sensitivity)', level='exposure')
    for model, irr in GOLDEN_WORKFORCE_IRR.items():
        assert round(t.loc[model, 'IRR adj per +1 per 100k'], 4) == irr and t.loc[model, 'CI low'] > 1


def test_workforce_density_by_year(real_run):
    """Figures S3/S4: whole-workforce density vs CTA rate is positive in 2023 (IRR 1.0049) and weaker in 2018 (1.0041)."""
    t = real_run['tables']['workforce_density_by_year']
    assert round(t.loc[2023, 'IRR adj per +1 per 100k'], 4) == 1.0049 and t.loc[2023, 'physicians'] == 60976
    assert round(t.loc[2018, 'IRR adj per +1 per 100k'], 4) == 1.0041 and t.loc[2018, 'physicians'] == 57343


def test_workforce_change_models(real_run):
    """Figure S5: Δ rate ~ Δ density slope 0.038 (shared FFS denominator); count model elasticity 1.10, not significant."""
    t = real_run['tables']['workforce_cta_change_models']
    assert round(t.loc['Δ rate ~ Δ density (all states)', 'estimate'], 4) == 0.0380
    c = t.loc['Δlog CTA ~ Δlog physicians + Δlog FFS']
    assert round(c['estimate'], 2) == 1.10 and c['CI low'] < 0 < c['CI high']
