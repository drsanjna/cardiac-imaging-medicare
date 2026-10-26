"""End-to-end: a full recorded run on synthetic data, plus failure handling."""
import json

import pytest

from cardiac_imaging import config, pipeline
from cardiac_imaging.figures.catalog import FIGURES


def test_run_completes_every_step(pipeline_run):
    """All steps succeed and the manifest says so."""
    m = json.loads((pipeline_run['run_dir'] / 'manifest.json').read_text())
    assert m['status'] == 'ok'
    assert [s['step'] for s in m['steps']] == [name for name, _ in pipeline.STEPS]
    assert all(s['status'] == 'ok' for s in m['steps'])


def test_run_produces_every_catalogued_figure(pipeline_run):
    """Each catalog entry has a PNG and a thumbnail; nothing uncatalogued is produced."""
    figs = pipeline_run['run_dir'] / 'figures'
    produced = {p.stem for p in figs.glob('*.png')}
    assert produced == {f['stem'] for f in FIGURES}
    assert {p.stem for p in (figs / 'thumbs').glob('*.png')} == produced
    assert (figs / 'interactive' / 'figure5_cardiac_cta_state_maps.html').exists()


def test_run_saves_tables_and_records(pipeline_run):
    """Result tables, console log, filter log, headline IRRs, findings and an English summary are saved."""
    d = pipeline_run['run_dir']
    m = json.loads((d / 'manifest.json').read_text())
    for t in ('change_summary', 'national_market_share', 'nb_density_models', 'table1_specialty_distribution',
              'state_summary_2023', 'filter_log', 'ica_state_rates', 'tavr_state_rates', 'density_sensitivity_workforce', 'workforce_density_by_year'):
        assert (d / 'tables' / f'{t}.csv').exists(), t
    import pandas as pd
    assert {'Invasive Coronary Angiography', 'TAVR'} <= set(pd.read_csv(d / 'tables' / 'change_summary.csv')['modality'])
    tavr = pd.read_csv(d / 'tables' / 'tavr_state_rates.csv', index_col='state')
    sens = pd.read_csv(d / 'tables' / 'density_sensitivity_workforce.csv')
    assert list(pd.read_csv(d / 'tables' / 'workforce_density_by_year.csv')['year']) == [2023, 2018]
    assert len(sens) == 6 and set(sens['exposure']) == {'CTA billers (original)', 'Whole specialty workforce (sensitivity)'}
    assert pd.isna(tavr.loc['VT', 'rate_delta']) and tavr.loc['VT', 'rate_per_1000_2023'] > 0   # no 2018 rows: no delta
    assert 'Invasive Coronary Angiography' not in pd.read_csv(d / 'tables' / 'national_market_share.csv').columns
    assert 'Adjusted IRR — All CTA-billing providers' in m['headline']
    assert m['findings']['irr_adjusted'] and m['summary'].startswith('From 2018 to 2023')
    assert m['comparison']['previous'] is None
    assert m['data']['claims_rows_total'] > 0 and m['versions']['python']
    log = (d / 'console.log').read_text()
    assert 'ALL FIGURES COMPLETE' in log and '[filter]' in log


def test_run_snapshot_tag_and_reports(pipeline_run):
    """The code snapshot is tagged; gallery, PDF and index are built; `latest` points at the run."""
    from conftest import git
    d, repo = pipeline_run['run_dir'], pipeline_run['repo']
    m = json.loads((d / 'manifest.json').read_text())
    assert git(repo, 'rev-parse', f"{m['code']['tag']}^{{commit}}") == m['code']['snapshot']
    assert m['code']['exact'] is True
    assert (d / 'gallery.html').exists() and (d / 'all_figures.pdf').stat().st_size > 10_000
    assert (pipeline_run['runs_dir'] / 'index.html').exists()
    assert (pipeline_run['runs_dir'] / 'latest').resolve() == d.resolve()


def test_failure_is_recorded(synthetic_db, tmp_path, monkeypatch):
    """A failing step marks the run failed, names the step, writes logs/last_error.md, and re-raises."""
    def boom(ctx):
        """Simulated failure."""
        raise ValueError('synthetic failure')
    steps = list(pipeline.STEPS)
    steps[2] = ('figure1_decomposition', boom)
    monkeypatch.setattr(pipeline, 'STEPS', steps)
    with pytest.raises(ValueError, match='synthetic failure'):
        pipeline.run_all(database=str(synthetic_db))
    run = sorted(config.RUNS_DIR.glob('2*'))[-1]
    m = json.loads((run / 'manifest.json').read_text())
    assert m['status'] == 'failed' and m['error']['step'] == 'figure1_decomposition'
    assert 'stopped at' in m['summary']
    assert 'synthetic failure' in (config.LOG_DIR / 'last_error.md').read_text()


def test_no_record_mode(synthetic_db, stub_plotly):
    """record=False writes figures to OUTPUT_DIR and creates no run folder."""
    pipeline.run_all(database=str(synthetic_db), record=False)
    assert (config.OUTPUT_DIR / 'figure1_decomposition.png').exists()
    assert not config.RUNS_DIR.exists() or not list(config.RUNS_DIR.glob('2*'))


def test_tiffs_when_enabled(synthetic_db, stub_plotly, monkeypatch):
    """With SAVE_TIFF on, matplotlib and plotly figures get TIFF copies in figures/tiff/."""
    monkeypatch.setattr(config, 'SAVE_TIFF', True)
    monkeypatch.setattr(config, 'TIFF_LINEART_DPI', 100)
    monkeypatch.setattr(config, 'TIFF_PANEL_DPI', 100)
    pipeline.run_all(database=str(synthetic_db), record=False)
    tiffs = {p.stem for p in (config.OUTPUT_DIR / 'tiff').glob('*.tiff')}
    assert {'figure1_decomposition', 'figure9_density_irr_forest', 'figure3_echo_state_maps'} <= tiffs
