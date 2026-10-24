"""GitHub-facing code with GitHub simulated: publishing runs, reading them back, downloading, error issues, API chat."""
import base64
import json
import shutil
import sys
import types
import zipfile

import pytest

from cardiac_imaging import config, errors
from cardiac_imaging.app import chat
from cardiac_imaging.reporting import publish, run_store
from conftest import git


@pytest.fixture
def run_dir(pipeline_run, isolated, monkeypatch):
    """Private copy of the synthetic run and its repo, with a fake GitHub remote."""
    repo = isolated / 'gh-repo'
    shutil.copytree(pipeline_run['repo'], repo)
    monkeypatch.setattr(config, 'REPO_ROOT', repo)
    git(repo, 'remote', 'add', 'origin', 'https://github.com/owner/repo.git')
    d = config.RUNS_DIR / pipeline_run['run_dir'].name
    shutil.copytree(pipeline_run['run_dir'], d)
    return d


class FakeGh:
    """Records gh/git invocations and answers `release view` like GitHub would."""

    def __init__(self):
        """Start with no calls."""
        self.calls = []

    def gh(self, *args, capture=False):
        """Fake publish._gh."""
        self.calls.append(args)
        if args[:2] == ('release', 'view'):
            return json.dumps({'url': 'https://github.com/owner/repo/releases/tag/x', 'publishedAt': '2026-10-24T01:00:00Z',
                               'assets': [{'name': 'run.zip', 'url': 'https://example/run.zip'}]})
        return ''


def test_publish_run_creates_release_and_records_it(run_dir, monkeypatch):
    """publish_run pushes the tag, uploads zips/PDF/manifest with notes, and stores the release info."""
    fake = FakeGh()
    monkeypatch.setattr(publish, '_gh', fake.gh)
    pushed = []
    monkeypatch.setattr(publish, '_push_tag', lambda tag: pushed.append(tag))
    info = publish.publish_run(run_dir)
    assert info['at'] == '2026-10-24T01:00:00Z' and info['tag'].startswith('run-')
    assert pushed == [info['tag']]
    create = next(c for c in fake.calls if c[:2] == ('release', 'create'))
    assert '--verify-tag' in create and any(str(a).endswith('all_figures.pdf') for a in create)
    assert any(str(a).endswith(f'run_{run_dir.name}.zip') for a in create)
    m = run_store.read_manifest(run_dir)
    assert m['published']['release_url'].endswith('/x')
    assert 'saved to GitHub' in (run_dir / 'gallery.html').read_text()
    assert publish.publish_run(run_dir) == m['published']          # second call is a no-op
    assert publish.update_release_notes(run_dir) is True
    assert any(c[:2] == ('release', 'edit') for c in fake.calls)


def test_update_notes_skips_unpublished(run_dir):
    """Unpublished runs have no release notes to update."""
    assert publish.update_release_notes(run_dir) is False


def test_remote_runs_decodes_release_records(monkeypatch):
    """Runs are rebuilt from release bodies; releases without a record are ignored."""
    rec = {'run_id': 'r1', 'status': 'ok', 'summary': 'hello'}
    body = f"notes\n<!-- {publish.MARKER}{base64.b64encode(json.dumps(rec).encode()).decode()} -->"
    rels = [dict(body=body, published_at='2026-10-24T01:00:00Z', html_url='u', tag_name='run-r1',
                 assets=[dict(name='a.zip', browser_download_url='d')]), dict(body='a normal release')]
    monkeypatch.setattr(publish, '_gh_api_releases', lambda: rels)
    out = publish.remote_runs()
    assert len(out) == 1 and out[0]['summary'] == 'hello' and out[0]['published']['assets'] == {'a.zip': 'd'}


def _fake_download(zip_members):
    """A fake `gh release download` that writes a zip with the given members into --dir."""
    def gh(*args, capture=False):
        """Write the zip where gh would."""
        out = args[args.index('--dir') + 1]
        name = args[args.index('--pattern') + 1]
        with zipfile.ZipFile(f'{out}/{name}', 'w') as z:
            for m in zip_members:
                z.writestr(m, '{}')
    return gh


def test_fetch_run_unpacks_into_runs_dir(monkeypatch):
    """A GitHub-only run is downloaded and unpacked as <runs_dir>/<run id>/."""
    monkeypatch.setattr(publish, '_gh', _fake_download(['r9/manifest.json', 'r9/gallery.html']))
    d = publish.fetch_run('r9')
    assert (d / 'manifest.json').exists() and d == config.RUNS_DIR / 'r9'
    assert publish.fetch_run('r9') == d                               # already local → no download


def test_fetch_run_rejects_unsafe_archives(monkeypatch):
    """Archives with paths outside the run folder are refused."""
    monkeypatch.setattr(publish, '_gh', _fake_download(['r8/ok.txt', '../evil.txt']))
    with pytest.raises(RuntimeError, match='Unexpected paths'):
        publish.fetch_run('r8')


def test_gh_missing(monkeypatch):
    """A clear error when the GitHub CLI isn't installed."""
    monkeypatch.setattr(publish.shutil, 'which', lambda _: None)
    with pytest.raises(RuntimeError, match='gh'):
        publish._gh('release', 'list')


def test_error_report_and_issue(monkeypatch):
    """report() writes the log; with a token it opens an issue, or comments when one is already open."""
    calls = []

    def fake_github(method, url, token, payload=None):
        """Simulate the issues API."""
        calls.append((method, url, payload))
        if method == 'GET':
            return [{'title': 'Notebook error in step_x: ValueError', 'number': 5, 'html_url': 'https://gh/issues/5'}]
        return {'html_url': 'https://gh/issues/6'}
    monkeypatch.setattr(errors, '_github', fake_github)
    monkeypatch.setenv('GITHUB_REPOSITORY', 'owner/repo')
    try:
        raise ValueError('boom')
    except ValueError as e:
        exc = e
    errors.report(exc, 'step_x')                                     # CARDIAC_REPORT_ERRORS=0 in tests → log only
    assert 'boom' in (config.LOG_DIR / 'last_error.md').read_text() and calls == []
    monkeypatch.setenv('CARDIAC_REPORT_ERRORS', '1')
    monkeypatch.setenv('CARDIAC_GITHUB_TOKEN', 't')
    errors.report(exc, 'step_x')
    assert calls[-1][0] == 'POST' and calls[-1][1].endswith('/issues/5/comments')
    assert errors.open_issue('A different error', 'body') == 'https://gh/issues/6'
    assert calls[-1][2]['labels'] == [errors.ISSUE_LABEL] and '@claude' in calls[-1][2]['body']
    monkeypatch.delenv('CARDIAC_GITHUB_TOKEN')
    assert errors.open_issue('x', 'y') is None


def test_anthropic_backend_with_fake_sdk(pipeline_run, monkeypatch, isolated):
    """The API backend sends the image on turn 1, keeps full content blocks, and handles refusals."""
    sent = []

    class Block:
        """Fake content block."""
        def __init__(self, type_, text=''):
            """Store type and text."""
            self.type, self.text = type_, text

        def to_dict(self):
            """Serialize like the SDK."""
            return {'type': self.type, 'text': self.text}

    class Messages:
        """Fake client.beta.messages."""
        def create(self, **kw):
            """Record the request and answer."""
            sent.append(kw)
            stop = 'refusal' if 'refuse' in kw['messages'][-1]['content'][-1]['text'] else 'end_turn'
            return types.SimpleNamespace(content=[Block('thinking'), Block('text', 'an answer')], stop_reason=stop)

    fake = types.ModuleType('anthropic')
    fake.Anthropic = lambda: types.SimpleNamespace(beta=types.SimpleNamespace(messages=Messages()))
    for name in ('AuthenticationError', 'RateLimitError', 'APIStatusError', 'APIConnectionError'):
        setattr(fake, name, type(name, (Exception,), {}))
    monkeypatch.setitem(sys.modules, 'anthropic', fake)
    shutil.copytree(pipeline_run['run_dir'], config.RUNS_DIR / pipeline_run['run_dir'].name)
    rid = pipeline_run['run_dir'].name
    conv = chat.send(rid, 'figure1_decomposition', 'first', engine=chat.AnthropicBackend())
    assert conv['messages'][-1]['text'] == 'an answer'
    first = sent[0]['messages'][0]['content']
    assert first[0]['type'] == 'image' and first[1]['text'] == 'first'
    assert sent[0]['model'] == config.CHAT_MODEL and sent[0]['fallbacks'] == 'default'
    conv = chat.send(rid, 'figure1_decomposition', 'please refuse', conv['id'], engine=chat.AnthropicBackend())
    assert 'declined' in conv['messages'][-1]['text']
    assert sent[1]['messages'][1]['content'][0]['type'] == 'thinking'    # full assistant content replayed
    assert all(c['type'] == 'text' for c in sent[1]['messages'][2]['content'])
