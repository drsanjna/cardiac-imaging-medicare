"""Run sync between laptops and reliable GitHub releases (GitHub is faked — no network)."""
import base64
import importlib.util
import json
import subprocess
import threading

import pytest

from conftest import REAL_REPO
from cardiac_imaging import config
from cardiac_imaging.reporting import publish, run_store, sync


def make_run(runs_dir, run_id, review=None, published=None, pdf=False):
    """A minimal run folder with a manifest complete enough for publishing and release notes."""
    d = runs_dir / run_id
    (d / 'figures').mkdir(parents=True)
    (d / 'gallery.html').write_text('<html></html>')
    if pdf:
        (d / 'all_figures.pdf').write_bytes(b'%PDF')
    m = dict(run_id=run_id, status='ok', started='2026-10-23T22:11:40', finished='2026-10-23T22:12:40', seconds=60,
             summary=f'summary of {run_id}', headline={'All': dict(irr=1.19, lo=1.1, hi=1.3)}, review=review,
             published=published, figures=[], steps=[],
             code=dict(tag=f'run-{run_id}', snapshot='a' * 40, head='b' * 40, branch='main', exact=True, repo='me/repo'))
    run_store.write_manifest(d, m)
    return d


def release_for(run_dir, assets=None, draft=False, record=None):
    """What `gh release view` would return for a complete (or deliberately broken) release of run_dir."""
    m = run_store.read_manifest(run_dir)
    names = publish.expected_assets(run_dir, m) if assets is None else assets
    rec = publish.summary(m) if record is None else record
    body = f"notes\n<!-- {publish.MARKER}{base64.b64encode(json.dumps(rec, default=str).encode()).decode()} -->"
    return dict(url=f"https://github.com/me/repo/releases/tag/run-{m['run_id']}", publishedAt='2026-10-23T22:13:00Z',
                isDraft=draft, body=body, assets=[dict(name=n, size=10, url=f'https://x/{n}') for n in names])


@pytest.fixture
def runs(isolated):
    """The isolated runs folder; gallery/index rebuilding stubbed out."""
    d = config.RUNS_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture(autouse=True)
def no_rebuild(monkeypatch):
    """Skip HTML rebuilding (not under test here)."""
    from cardiac_imaging.reporting import gallery, index
    monkeypatch.setattr(gallery, 'build', lambda *a, **k: None)
    monkeypatch.setattr(index, 'build', lambda *a, **k: None)
    monkeypatch.setattr(sync, 'RETRY_WAITS', (0, 0))


# --- verify_release ------------------------------------------------------------------------------------------------

def test_verify_complete_release(runs, monkeypatch):
    """A release with every expected file and current notes has no problems."""
    d = make_run(runs, 'r1', pdf=True)
    monkeypatch.setattr(publish, 'release_info', lambda tag: release_for(d))
    assert sync.verify_release(d) == []


def test_verify_detects_every_problem(runs, monkeypatch):
    """Missing release, draft, missing/empty files, wrong run, stale notes and no record are all reported."""
    d = make_run(runs, 'r1', pdf=True)
    assert 'all_figures.pdf' in publish.expected_assets(d, run_store.read_manifest(d))
    monkeypatch.setattr(publish, 'release_info', lambda tag: None)
    assert sync.verify_release(d) == ['no GitHub release yet']

    rel = release_for(d, assets=['run_r1.zip', 'manifest.json'], draft=True)
    rel['assets'][0]['size'] = 0
    monkeypatch.setattr(publish, 'release_info', lambda tag: rel)
    problems = sync.verify_release(d)
    assert 'release is still a draft' in problems
    assert 'empty file run_r1.zip' in problems and 'missing file all_figures.pdf' in problems

    other = dict(publish.summary(run_store.read_manifest(d)), run_id='r2')
    monkeypatch.setattr(publish, 'release_info', lambda tag: release_for(d, record=other))
    assert sync.verify_release(d) == ['release notes describe a different run (r2)']

    stale = release_for(d)
    run_store.set_label('r1', 'success', runs_dir=runs)             # label changed locally after publishing
    monkeypatch.setattr(publish, 'release_info', lambda tag: stale)
    assert sync.verify_release(d) == ['release notes out of date (review)']

    monkeypatch.setattr(publish, 'release_info', lambda tag: dict(stale, body='no record'))
    assert sync.verify_release(d) == ['release notes have no run record']


def test_verify_without_tag(runs):
    """A run without a code-snapshot tag cannot have a release."""
    d = make_run(runs, 'r1')
    m = run_store.read_manifest(d)
    m['code'] = {}
    run_store.write_manifest(d, m)
    assert sync.verify_release(d) == ['run has no code-snapshot tag']


# --- publish_reliably ----------------------------------------------------------------------------------------------

def test_publish_reliably_retries_until_verified(runs, monkeypatch):
    """An incomplete first upload is repaired on the next attempt, then publish_error is cleared."""
    d = make_run(runs, 'r1')
    forced, results = [], [['missing file manifest.json'], []]
    monkeypatch.setattr(publish, 'publish_run', lambda run_dir, force=False: forced.append(force))
    monkeypatch.setattr(sync, 'verify_release', lambda run_dir: results.pop(0))
    assert sync.publish_reliably(d) == []
    assert forced == [False, True]                                   # second attempt re-checks the release
    assert run_store.read_manifest(d)['publish_error'] is None


def test_publish_reliably_records_failure(runs, monkeypatch, capsys):
    """When every attempt fails, the problems are kept in the manifest for the next sync."""
    d = make_run(runs, 'r1')
    def boom(run_dir, force=False):
        """gh failing as if offline."""
        raise subprocess.CalledProcessError(1, 'gh')
    monkeypatch.setattr(publish, 'publish_run', boom)
    left = sync.publish_reliably(d, attempts=2)
    assert left and 'CalledProcessError' in left[0]
    err = run_store.read_manifest(d)['publish_error']
    assert err['problems'] == left and err['at']
    assert 'retried by the next sync' in capsys.readouterr().out


def test_finish_publishes_reliably_and_reports_failure(runs, monkeypatch, capsys):
    """Every finished run goes through publish_reliably; an unverified upload is reported, not hidden."""
    def failing(run_dir):
        """Stand-in for an upload that could not be completed."""
        sync._set_publish_error(run_dir, ['missing file manifest.json'])
        return ['missing file manifest.json']
    monkeypatch.setattr(sync, 'publish_reliably', failing)
    run = run_store.Run('t')
    run.finish({}, publish=True)
    out = capsys.readouterr().out
    assert 'GitHub  : NOT complete — missing file manifest.json (next sync retries)' in out
    assert run_store.read_manifest(run.dir)['publish_error']['problems'] == ['missing file manifest.json']


# --- publish_run repair path ---------------------------------------------------------------------------------------

def test_publish_run_repairs_partial_release(runs, monkeypatch):
    """An existing, partial release gets only its missing files (--clobber) and fresh notes."""
    d = make_run(runs, 'r1', pdf=True)
    gh_calls = []
    partial = release_for(d, assets=['run_r1.zip'])                   # earlier upload was cut off
    infos = [partial, release_for(d)]
    monkeypatch.setattr(publish, 'release_info', lambda tag: infos.pop(0))
    monkeypatch.setattr(publish, '_gh', lambda *a, capture=False: gh_calls.append(a))
    monkeypatch.setattr(publish, '_push_tag', lambda tag: None)
    monkeypatch.setattr(publish.gitinfo, 'ensure_tag', lambda *a: None)
    pub = publish.publish_run(d)
    upload, edit = gh_calls
    assert upload[:3] == ('release', 'upload', 'run-r1') and '--clobber' in upload
    uploaded = sorted(a.rsplit('/', 1)[-1] for a in upload[4:])
    assert uploaded == ['all_figures.pdf', 'manifest.json']          # only what was missing
    assert edit[:3] == ('release', 'edit', 'run-r1')
    assert pub['tag'] == 'run-r1' and run_store.read_manifest(d)['published']['release_url'].endswith('run-r1')


def test_publish_run_creates_missing_release(runs, monkeypatch):
    """With no release yet, publish_run creates one on the pushed tag."""
    d = make_run(runs, 'r1')
    gh_calls = []
    infos = [None, release_for(d)]
    monkeypatch.setattr(publish, 'release_info', lambda tag: infos.pop(0))
    monkeypatch.setattr(publish, '_gh', lambda *a, capture=False: gh_calls.append(a))
    monkeypatch.setattr(publish, '_push_tag', lambda tag: None)
    monkeypatch.setattr(publish.gitinfo, 'ensure_tag', lambda *a: None)
    publish.publish_run(d)
    (create,) = gh_calls
    assert create[:3] == ('release', 'create', 'run-r1') and '--verify-tag' in create


# --- two-way sync --------------------------------------------------------------------------------------------------

def test_sync_uploads_downloads_and_merges_labels(runs, monkeypatch):
    """Local-only runs upload, GitHub-only runs download, and a newer label from GitHub is copied in."""
    make_run(runs, 'local_only')
    shared = make_run(runs, 'shared', review=dict(label='needs_review', note='', at='2026-10-23T10:00:00-04:00'))
    remote_review = dict(label='success', note='checked', at='2026-10-24T09:00:00-04:00')
    remote = [dict(run_id='shared', review=remote_review, published=dict(tag='run-shared')),
              dict(run_id='remote_only', review=None, published=dict(tag='run-remote_only'))]
    monkeypatch.setattr(publish, 'remote_runs', lambda: remote)
    uploaded, fetched = [], []
    monkeypatch.setattr(sync, 'publish_reliably', lambda run_dir: uploaded.append(run_dir.name) or [])
    monkeypatch.setattr(sync, 'verify_release', lambda run_dir: [])
    monkeypatch.setattr(publish, 'fetch_run', lambda rid, runs_dir: fetched.append(rid))
    report = sync.sync(runs_dir=runs)
    actions = {(r['run_id'], r['action']) for r in report}
    assert ('local_only', 'uploaded') in actions and ('remote_only', 'downloaded') in actions
    assert ('shared', 'label ← GitHub') in actions and ('shared', 'ok') in actions
    assert uploaded == ['local_only'] and fetched == ['remote_only']
    assert run_store.read_manifest(shared)['review'] == remote_review
    assert sync.summarize(report) == '1 uploaded, 1 downloaded, 0 repaired, 1 labels updated, 1 already in sync'


def test_sync_keeps_newer_local_label_and_repairs(runs, monkeypatch):
    """A newer local change (even clearing a label) wins; an out-of-date release is repaired."""
    d = make_run(runs, 'r1', review=dict(label=None, note='', at='2026-10-24T12:00:00-04:00'))   # cleared here, later
    remote = [dict(run_id='r1', review=dict(label='failure', note='', at='2026-10-24T08:00:00-04:00'))]
    monkeypatch.setattr(publish, 'remote_runs', lambda: remote)
    monkeypatch.setattr(sync, 'verify_release', lambda run_dir: ['release notes out of date (review)'])
    monkeypatch.setattr(sync, 'publish_reliably', lambda run_dir: [])
    report = sync.sync(runs_dir=runs, download=False)
    assert [r['action'] for r in report] == ['repaired']
    assert run_store.read_manifest(d)['review']['label'] is None     # the newer local "cleared" wins


def test_sync_dry_run_changes_nothing(runs, monkeypatch):
    """Dry run and check mode only report what they would do."""
    make_run(runs, 'local_only')
    monkeypatch.setattr(publish, 'remote_runs', lambda: [dict(run_id='remote_only')])
    monkeypatch.setattr(sync, 'publish_reliably', lambda run_dir: pytest.fail('dry run uploaded'))
    monkeypatch.setattr(publish, 'fetch_run', lambda *a: pytest.fail('dry run downloaded'))
    report = sync.sync(runs_dir=runs, dry_run=True)
    assert [r['action'] for r in report] == ['would upload', 'would download']
    check = sync.sync(runs_dir=runs, upload=False, download=False, dry_run=True)
    assert [r['action'] for r in check] == ['needs upload', 'on GitHub only']


def test_summarize_flags_failures():
    """The one-line summary calls out failures."""
    report = [dict(run_id='a', action='upload failed', detail=''), dict(run_id='b', action='ok', detail='')]
    assert sync.summarize(report).endswith('1 already in sync — 1 FAILED')


# --- app endpoint --------------------------------------------------------------------------------------------------

def test_api_sync_endpoint(runs, monkeypatch):
    """POST /api/sync runs a sync and returns its report; it needs the session token."""
    import urllib.request
    from cardiac_imaging.app import server
    monkeypatch.setattr(sync, 'sync', lambda: [dict(run_id='a', action='downloaded', detail='')])
    srv = server.make_server(port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{srv.server_address[1]}'
    try:
        with urllib.request.urlopen(base + '/api/session') as r:
            s = json.loads(r.read())
        assert 'sync' in s
        req = urllib.request.Request(base + '/api/sync', data=b'{}', method='POST',
                                     headers={'Content-Type': 'application/json', 'X-App-Token': s['token']})
        with urllib.request.urlopen(req) as r:
            out = json.loads(r.read())
        assert out['report'][0]['action'] == 'downloaded'
        assert out['sync']['summary'].startswith('0 uploaded, 1 downloaded') and not out['sync']['running']
        no_token = urllib.request.Request(base + '/api/sync', data=b'{}', method='POST')
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(no_token)
        assert e.value.code == 403
    finally:
        srv.shutdown()


def test_run_sync_survives_errors(monkeypatch):
    """An offline sync is recorded as failed instead of crashing the app."""
    from cardiac_imaging.app import server
    def offline():
        """Sync failing as if there's no network."""
        raise RuntimeError('offline')
    monkeypatch.setattr(sync, 'sync', offline)
    assert server.run_sync() is None
    assert server.SYNC_STATE['failed'] and 'offline' in server.SYNC_STATE['summary']


# --- scripts -------------------------------------------------------------------------------------------------------

def load(name):
    """Import scripts/<name>.py as a module."""
    spec = importlib.util.spec_from_file_location(name, REAL_REPO / 'scripts' / f'{name}.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_sync_runs_schedule_plist():
    """The LaunchAgent runs sync_runs.py at the requested interval."""
    mod = load('sync_runs')
    text = mod.plist_text(30)
    assert '<integer>1800</integer>' in text and 'sync_runs.py' in text and mod.LABEL in text


def test_check_releases_problems():
    """The CI check flags missing releases, drafts, missing/empty files and wrong or missing run records."""
    mod = load('check_releases')
    rec = base64.b64encode(json.dumps(dict(run_id='x')).encode()).decode()
    good = dict(draft=False, body=f'<!-- {mod.MARKER}{rec} -->',
                assets=[dict(name='run_x.zip', size=5), dict(name='manifest.json', size=1)])
    assert mod.problems_for('run-x', good) == []
    assert mod.problems_for('run-x', None) == ['no release for this tag']
    bad = dict(good, draft=True, body='', assets=[dict(name='run_x.zip', size=0), dict(name='tiff_x.zip', size=0)])
    assert mod.problems_for('run-x', bad) == ['release is a draft', 'empty run_x.zip', 'missing manifest.json',
                                              'empty tiff_x.zip', 'notes have no run record']
    assert mod.problems_for('run-y', good) == ['missing run_y.zip', 'notes describe x']
