"""Local app: chart-discussion context and conversations, chat backends, and the HTTP server's API + security."""
import json
import shutil
import threading
import urllib.error
import urllib.request

import pytest

from cardiac_imaging import config
from cardiac_imaging.app import chat, server


@pytest.fixture
def run_copy(pipeline_run, monkeypatch, isolated):
    """A private copy of the synthetic run inside this test's RUNS_DIR (so tests can write conversations etc.)."""
    dst = config.RUNS_DIR / pipeline_run['run_dir'].name
    shutil.copytree(pipeline_run['run_dir'], dst)
    repo = isolated / 'run-repo'
    shutil.copytree(pipeline_run['repo'], repo)   # private copy: restore tests commit into it
    monkeypatch.setattr(config, 'REPO_ROOT', repo)
    return dst.name


def test_context_uses_code_at_snapshot(run_copy):
    """Chart context includes the plotting function source, related tables and the data model."""
    ctx = chat.context(run_copy, 'figure8_nb_all_density')
    refs = [r for r, _, _ in ctx['code']]
    assert refs[0] == 'figures.density:plot_density_fit'
    assert all(src.startswith('def ') for _, _, src in ctx['code'])
    assert [n for n, _ in ctx['tables']] == ['nb_density_models', 'filter_log']
    text = chat.context_text(ctx)
    assert 'def plot_density_fit' in text and 'partb_provider_service' in text and ctx['tag'] in text


def test_function_source_missing_returns_empty():
    """Unknown functions yield empty source rather than an error."""
    path, src = chat.function_source('figures.density:not_a_function')
    assert path.endswith('figures/density.py') and src == ''


def test_unknown_chart():
    """Unknown chart stems raise KeyError."""
    with pytest.raises(KeyError):
        chat.chart('nope')


class EchoBackend:
    """Fake backend that echoes, for testing the conversation flow."""

    name = 'echo'

    def reply(self, conv, message, ctx):
        """Echo the message with the chart label."""
        return f"[{ctx['label']}] {message}"


def test_conversation_flow_and_outcome(run_copy):
    """Messages are saved; follow-ups append to the same conversation; outcomes are validated and stored."""
    conv = chat.send(run_copy, 'figure2_market_share', 'Office imaging drives CTA growth', engine=EchoBackend())
    assert [m['role'] for m in conv['messages']] == ['user', 'assistant']
    assert conv['messages'][1]['text'] == '[Figure 2] Office imaging drives CTA growth'
    conv = chat.send(run_copy, 'figure2_market_share', 'What about rural?', conv['id'], engine=EchoBackend())
    assert len(conv['messages']) == 4
    assert chat.list_conversations(run_copy, 'figure2_market_share')[0]['id'] == conv['id']
    assert chat.set_outcome(conv['id'], 'supported', 'clear trend')['outcome'] == 'supported'
    with pytest.raises(ValueError):
        chat.set_outcome(conv['id'], 'maybe')
    with pytest.raises(ValueError):
        chat.load('../etc/passwd')


def test_backend_errors_are_shown_not_raised(run_copy):
    """A failing backend produces a ⚠️ message instead of crashing."""
    class Broken:
        """Backend that always fails."""
        name = 'broken'

        def reply(self, conv, message, ctx):
            """Raise."""
            raise RuntimeError('no network')
    conv = chat.send(run_copy, 'figure1_decomposition', 'hi', engine=Broken())
    assert conv['messages'][-1]['text'] == '⚠️ no network'


def test_handoff_backend_gives_full_prompt(run_copy):
    """Without a model, the reply is a ready-made prompt containing the code and the hypothesis."""
    conv = chat.send(run_copy, 'figure9_density_irr_forest', 'Cardiologist IRR is confounded by urbanicity',
                     engine=chat.HandoffBackend())
    text = conv['messages'][-1]['text']
    assert 'def plot_forest' in text and 'confounded by urbanicity' in text and 'brew install' in text


def test_backend_selection(monkeypatch):
    """auto picks Claude Code when installed, else the API when configured, else hand-off."""
    monkeypatch.setattr(config, 'CHAT_BACKEND', 'auto')
    monkeypatch.setattr(chat.ClaudeCodeBackend, 'available', staticmethod(lambda: False))
    monkeypatch.setattr(chat.AnthropicBackend, 'available', staticmethod(lambda: False))
    assert chat.backend().name == 'handoff'
    monkeypatch.setattr(chat.AnthropicBackend, 'available', staticmethod(lambda: True))
    assert chat.backend().name == 'api'
    monkeypatch.setattr(chat.ClaudeCodeBackend, 'available', staticmethod(lambda: True))
    assert chat.backend().name == 'claude-code'


def test_claude_code_backend_command(run_copy, monkeypatch):
    """The CLI is called read-only with the context on turn 1 and --resume afterwards."""
    calls = []

    class Done:
        """Fake CompletedProcess."""
        stdout = json.dumps({'result': 'answer', 'session_id': 'sess-1', 'is_error': False})
        stderr = ''

    monkeypatch.setattr(chat.shutil, 'which', lambda b: '/usr/local/bin/claude')
    monkeypatch.setattr(chat, '_run_cli', lambda cmd: calls.append(cmd) or Done())
    conv = chat.send(run_copy, 'figure1_decomposition', 'q1', engine=chat.ClaudeCodeBackend())
    conv = chat.send(run_copy, 'figure1_decomposition', 'q2', conv['id'], engine=chat.ClaudeCodeBackend())
    first, second = calls
    assert first[first.index('--tools') + 1] == 'Read,Grep,Glob' and '--append-system-prompt' in first
    assert second[second.index('--resume') + 1] == 'sess-1' and '--append-system-prompt' not in second
    assert conv['messages'][-1]['text'] == 'answer'


@pytest.fixture
def app(run_copy):
    """Running app server on a free port; yields (base_url, run_id)."""
    srv = server.make_server(port=0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f'http://127.0.0.1:{srv.server_address[1]}', run_copy
    srv.shutdown()


def _req(url, body=None, token=None, host=None):
    """(status, json) for a GET (body None) or POST."""
    data = None if body is None else json.dumps(body).encode()
    r = urllib.request.Request(url, data=data, method='GET' if body is None else 'POST')
    r.add_header('Content-Type', 'application/json')
    if token:
        r.add_header('X-App-Token', token)
    if host:
        r.add_header('Host', host)
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, json.loads(resp.read() or b'null')
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'null')


def test_server_serves_index_and_gallery(app):
    """Static pages are served from RUNS_DIR."""
    base, run = app
    with urllib.request.urlopen(f'{base}/') as r:
        assert b'results history' in r.read()
    with urllib.request.urlopen(f'{base}/{run}/gallery.html') as r:
        assert b'data-discuss' in r.read()


def test_server_session_context_and_chat(app):
    """Session gives a token; context returns code; chat works with the token and is refused without it."""
    base, run = app
    status, s = _req(f'{base}/api/session')
    assert status == 200 and s['token'] and s['chat_backend'] == 'handoff'
    status, ctx = _req(f'{base}/api/context?run={run}&stem=figure1_decomposition')
    assert status == 200 and ctx['code'][0]['ref'] == 'figures.decomposition:plot_figure1'
    assert _req(f'{base}/api/chat', {'run': run, 'stem': 'figure1_decomposition', 'message': 'x'})[0] == 403
    status, conv = _req(f'{base}/api/chat', {'run': run, 'stem': 'figure1_decomposition', 'message': 'x'}, token=s['token'])
    assert status == 200 and conv['api_messages'] is None and len(conv['messages']) == 2
    status, conv = _req(f'{base}/api/outcome', {'conversation': conv['id'], 'outcome': 'inconclusive'}, token=s['token'])
    assert status == 200 and conv['outcome'] == 'inconclusive'
    assert _req(f'{base}/api/conversations?run={run}')[1][0]['outcome'] == 'inconclusive'


def test_server_rejects_foreign_host_and_bad_input(app):
    """DNS-rebinding style Host headers are refused; bad requests give 400; unknown routes 404."""
    base, run = app
    assert _req(f'{base}/api/session', host='evil.example.com')[0] == 403
    token = _req(f'{base}/api/session')[1]['token']
    assert _req(f'{base}/api/chat', {'run': run}, token=token)[0] == 400
    assert _req(f'{base}/api/nope')[0] == 404
    assert _req(f'{base}/api/restore', {'run': 'missing'}, token=token)[0] == 409


def test_server_restore_endpoint(app):
    """POST /api/restore restores the run's code in the repo and returns an undoable backup tag."""
    base, run = app
    token = _req(f'{base}/api/session')[1]['token']
    (config.REPO_ROOT / 'src' / 'app.py').write_text('VERSION = 77\n')
    status, out = _req(f'{base}/api/restore', {'run': run}, token=token)
    assert status == 200, out
    assert out['changed'] and (config.REPO_ROOT / 'src' / 'app.py').read_text() == 'VERSION = 1\n'
    status, out = _req(f'{base}/api/undo', {'backup_tag': out['backup_tag']}, token=token)
    assert status == 200 and (config.REPO_ROOT / 'src' / 'app.py').read_text() == 'VERSION = 77\n'
