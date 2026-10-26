"""Reporting: audit log, summaries/comparisons, gallery, index, release notes, publishing helpers."""
import base64
import json
import zipfile

import pandas as pd
import pytest

from cardiac_imaging import audit, config
from cardiac_imaging.reporting import gallery, index, insights, publish, run_store


def test_log_filter_records_and_prints(capsys):
    """log_filter returns `after`, records an entry and prints dropped items."""
    audit.FILTER_LOG.clear()
    assert audit.log_filter('states', 10, 8, unit='states', dropped_items={'B', 'A'}) == 8
    assert audit.FILTER_LOG == [dict(filter='states', before=10, after=8, dropped=2, unit='states', dropped_items='A, B')]
    assert "10 → 8 states (2 dropped: ['A', 'B'])" in capsys.readouterr().out


def test_findings_and_summary_from_run(pipeline_run):
    """Findings are read from the run's tables and turned into plain English."""
    f = insights.findings(pipeline_run['run_dir'])
    assert set(f) >= {'rate_change_pct', 'advanced_share_pct', 'irr_adjusted', 'cta_reader_share_pct'}
    text = insights.english_summary(dict(status='ok', findings=f))
    assert 'per 1,000' in text and 'Advanced imaging' in text and 'CTA' in text and '95% CI' in text


def test_summary_for_failed_run():
    """A failed run's summary names the step and suggests what to do."""
    s = insights.english_summary(dict(status='failed', error=dict(step='load_claims', type='KeyError'), steps=[]))
    assert 'load_claims' in s and 'Restore' in s


def _run(run_id, irr=1.2, snap=None, fp='abc', figs=('a.png',), status='ok', tiff=False):
    """Minimal manifest dict for comparison tests."""
    return dict(run_id=run_id, status=status, save_tiff=tiff, figures=list(figs), code=dict(snapshot=snap),
                data=dict(fingerprint=fp, claims_rows_total=100),
                findings=dict(irr_adjusted={'All': dict(irr=irr, lo=1, hi=2, p=0.01)}, rate_change_pct={'Echo': 4.0}))


def test_compare_no_previous():
    """The first run says there's nothing to compare."""
    c = insights.compare(_run('b'), None)
    assert c['previous'] is None and 'First recorded run' in c['changes'][0]


def test_compare_detects_result_data_figure_and_setting_changes():
    """Changed IRRs, data, figures, status and TIFF setting all show up in plain English."""
    prev = _run('a', irr=1.2, figs=('a.png', 'old.png'))
    cur = _run('b', irr=1.3, fp='xyz', figs=('a.png', 'new.png'), tiff=True)
    c = insights.compare(cur, prev)
    text = ' '.join(c['changes'] + c['impact'])
    assert 'Input data changed' in text and 'TIFF export turned on' in text
    assert '1.200 → 1.300' in text and 'new.png' in text and 'old.png' in text


def test_compare_unchanged_results():
    """Identical findings → 'No change in results'."""
    c = insights.compare(_run('b'), _run('a'))
    assert any('No change in results' in x for x in c['impact'])
    assert 'Same input data.' in c['changes']


def test_compare_code_changes_between_snapshots(isolated):
    """Commits and files between the two snapshots are listed."""
    from conftest import git
    repo = config.REPO_ROOT
    a = git(repo, 'rev-parse', 'HEAD')
    (repo / 'src' / 'app.py').write_text('VERSION = 2\n')
    git(repo, 'commit', '-qam', 'Bump version')
    b = git(repo, 'rev-parse', 'HEAD')
    c = insights.compare(_run('b', snap=b), _run('a', snap=a))
    assert c['code_files'] == ['src/app.py'] and c['code_commits'] == ['Bump version']
    assert 'Bump version' in c['changes'][0]
    same = insights.compare(_run('b', snap=a), _run('a', snap=a))
    assert same['changes'][0] == 'Same code as the previous run.'


def test_gallery_html(pipeline_run):
    """Gallery lists every chart with zoom + discuss buttons, the run details panel and the viewer controls."""
    html = (pipeline_run['run_dir'] / 'gallery.html').read_text()
    assert html.count('data-discuss=') == 15 and 'id="lb-in"' in html and 'id="lb-fit"' in html
    assert 'id="discuss"' in html and 'Restore this code' in html and 'Rows per year' in html
    assert 'Interactive' in html
    assert 'Sensitivity — density models with the whole radiology/cardiology workforce' in html   # shown, not just a CSV link


def test_gallery_layout_summary_top_development_bottom(pipeline_run):
    """The run's English summary is the first section; run details/steps/files sit in a collapsed Development tab at the end."""
    from cardiac_imaging.reporting import run_store
    html = (pipeline_run['run_dir'] / 'gallery.html').read_text()
    m = run_store.read_manifest(pipeline_run['run_dir'])
    order = [html.index(x) for x in ('id="summary"', 'id="main-text"', 'id="results"', 'id="development"')]
    assert order == sorted(order)
    top = html[html.index('id="summary"'):html.index('id="main-text"')]
    assert gallery.esc(m['summary']) in top and 'What changed' in top
    dev = html[html.index('id="development"'):]
    assert '<details id="dev-panel">' in dev and 'Rows per year' in dev and 'Pipeline steps' in dev and 'console.log' in dev
    assert 'href="#development">Development</a>' in html


def test_fmt_num():
    """Compact number formatting for tables."""
    assert gallery.fmt_num(1234.5) == '1,234' and gallery.fmt_num(0.00001) == '1.0e-05'
    assert gallery.fmt_num(1.23456) == '1.235' and gallery.fmt_num(float('nan')) == '—' and gallery.fmt_num(7) == '7'
    assert gallery.fmt_num('<b>') == '&lt;b&gt;'


def test_index_embeds_runs_and_actions(pipeline_run):
    """Index embeds each run's summary and offers open / what-changed / restore actions."""
    index.build(pipeline_run['runs_dir'])
    html = (pipeline_run['runs_dir'] / 'index.html').read_text()
    data = json.loads(html.split('id="local-runs">')[1].split('</script>')[0])
    assert data[0]['summary'].startswith('From 2018')
    assert 'data-restore' in html and 'What changed' in html and 'Restore the code to this version?' in html


def test_release_notes_roundtrip(pipeline_run):
    """Release notes carry the English summary, what changed, restore command and a decodable run record."""
    m = run_store.read_manifest(pipeline_run['run_dir'])
    notes = publish.release_notes(m)
    assert m['summary'] in notes and '**What changed**' in notes and f"git checkout {m['code']['tag']}" in notes
    b64 = notes.split(publish.MARKER)[1].split('-->')[0].strip()
    rec = json.loads(base64.b64decode(b64))
    assert rec['run_id'] == m['run_id'] and rec['figures'] == 15 and rec['summary'] == m['summary']


def test_zip_splits_tiffs(tmp_path):
    """Outputs zip excludes TIFFs; TIFF zip contains only TIFFs; paths are rooted at the run id."""
    run = tmp_path / '2026-01-01_000000_abc'
    (run / 'figures' / 'tiff').mkdir(parents=True)
    (run / 'figures' / 'a.png').write_text('png')
    (run / 'figures' / 'tiff' / 'a.tiff').write_text('tiff')
    (run / 'manifest.json').write_text('{}')
    publish._zip(run, tmp_path / 'o.zip', include_tiff=False)
    publish._zip(run, tmp_path / 't.zip', include_tiff=True)
    assert sorted(zipfile.ZipFile(tmp_path / 'o.zip').namelist()) == [f'{run.name}/figures/a.png', f'{run.name}/manifest.json']
    assert zipfile.ZipFile(tmp_path / 't.zip').namelist() == [f'{run.name}/figures/tiff/a.tiff']


def test_publish_requires_snapshot(tmp_path):
    """Publishing a run without a code snapshot is refused with guidance."""
    run = tmp_path / 'r'
    run.mkdir()
    run_store.write_manifest(run, dict(run_id='r', code=dict(snapshot=None, tag='run-r'), published=None))
    with pytest.raises(RuntimeError, match='no code snapshot'):
        publish.publish_run(run)


def test_previous_run_and_list(tmp_path):
    """list_runs is newest first; previous_run finds the run before a given id."""
    for rid in ('2026-01-01_a', '2026-01-02_b', '2026-01-03_c'):
        (tmp_path / rid).mkdir()
        run_store.write_manifest(tmp_path / rid, dict(run_id=rid))
    assert [m['run_id'] for m in run_store.list_runs(tmp_path)] == ['2026-01-03_c', '2026-01-02_b', '2026-01-01_a']
    assert run_store.previous_run('2026-01-03_c', tmp_path)['run_id'] == '2026-01-02_b'
    assert run_store.previous_run('2026-01-01_a', tmp_path) is None


def test_data_fingerprint_changes_with_files(tmp_path):
    """The data fingerprint changes when a Parquet file changes."""
    (tmp_path / 'a.parquet').write_bytes(b'1')
    f1 = run_store.data_fingerprint(tmp_path)
    (tmp_path / 'a.parquet').write_bytes(b'12')
    f2 = run_store.data_fingerprint(tmp_path)
    assert f1['fingerprint'] != f2['fingerprint'] and f2['parquet_files'] == 1


def test_save_tables(tmp_path):
    """Run.save_tables writes CSVs and registers them in the manifest (via a stub Run)."""
    r = run_store.Run.__new__(run_store.Run)
    r.dir = tmp_path
    (tmp_path / 'tables').mkdir()
    r.manifest = dict(tables={})
    r.save_tables({'t': pd.DataFrame({'a': [1]})})
    assert (tmp_path / 'tables' / 't.csv').exists() and r.manifest['tables'] == {'t': 'tables/t.csv'}


def test_set_label_store_clear_and_validate(tmp_path):
    """Labels are saved in the manifest, can be cleared, must be known, and need the run to be local."""
    (tmp_path / 'r1').mkdir()
    run_store.write_manifest(tmp_path / 'r1', dict(run_id='r1'))
    m = run_store.set_label('r1', 'needs_review', 'check IRR drift', runs_dir=tmp_path)
    assert m['review']['label'] == 'needs_review' and m['review']['note'] == 'check IRR drift' and m['review']['at']
    assert run_store.read_manifest(tmp_path / 'r1')['review']['label'] == 'needs_review'
    cleared = run_store.set_label('r1', None, runs_dir=tmp_path)['review']
    assert cleared['label'] is None and cleared['at']          # clearing is timestamped for sync
    with pytest.raises(ValueError):
        run_store.set_label('r1', 'great', runs_dir=tmp_path)
    with pytest.raises(FileNotFoundError, match='download it first'):
        run_store.set_label('missing', 'success', runs_dir=tmp_path)


def test_label_travels_to_github_notes_and_index(pipeline_run, tmp_path):
    """A label appears in the release notes and in the run record the landing page reads (local and from GitHub)."""
    m = run_store.read_manifest(pipeline_run['run_dir'])
    m['review'] = dict(label='archived', note='superseded', at='2026-10-24T10:00:00')
    notes = publish.release_notes(m)
    assert '| Your label | archived — superseded |' in notes
    rec = json.loads(base64.b64decode(notes.split(publish.MARKER)[1].split('-->')[0].strip()))
    assert rec['review']['label'] == 'archived'


def test_landing_page_structure(pipeline_run):
    """Landing page: app bar, search, filters incl. Archived, run list + detail pane, label controls, keyboard hints."""
    index.build(pipeline_run['runs_dir'])
    html = (pipeline_run['runs_dir'] / 'index.html').read_text()
    for needle in ('class="appbar"', 'id="q"', 'id="filters"', 'id="list"', 'id="detail"', "['archived', 'Archived']",
                   'data-label', '/api/label', '<kbd>/</kbd> search', 'data-restore', 'What changed'):
        assert needle in html, needle


def test_figure_title_above_chart(pipeline_run):
    """Each card shows the figure label and title above the image, caption below."""
    html = (pipeline_run['run_dir'] / 'gallery.html').read_text()
    card = html[html.index('<figure class="card">'):html.index('</figure>')]
    assert card.index('fig-title') < card.index('<img') < card.index('<figcaption>')
