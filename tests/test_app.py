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


def test_handoff_backend_gives_full_prompt(run_copy, monkeypatch):
    """Without a model, the reply is a ready-made prompt containing the code and the hypothesis, plus setup steps."""
    monkeypatch.setattr(chat, 'claude_binary', lambda: None)
    conv = chat.send(run_copy, 'figure9_density_irr_forest', 'Cardiologist IRR is confounded by urbanicity',
                     engine=chat.HandoffBackend())
    text = conv['messages'][-1]['text']
    assert 'def plot_forest' in text and 'confounded by urbanicity' in text and 'brew install' in text


def test_setup_hint_when_bundled_cli_not_logged_in(monkeypatch):
    """If Claude Code is present but logged out, the hint gives the exact one-time login command for that binary."""
    monkeypatch.setattr(chat, 'claude_binary', lambda: '/Apps/Claude/claude')
    hint = chat.setup_hint()
    assert '"/Apps/Claude/claude" auth login' in hint and 'no restart needed' in hint and 'brew' not in hint


def test_claude_binary_prefers_path_then_newest_bundled(tmp_path, monkeypatch):
    """`claude` on PATH wins; otherwise the newest version bundled with the desktop app is used."""
    for v in ('2.1.255', '2.1.308', '2.1.99'):
        b = tmp_path / 'Library/Application Support/Claude/claude-code' / v / 'abc/claude.app/Contents/MacOS/claude'
        b.parent.mkdir(parents=True)
        b.write_text('')
    monkeypatch.setattr(chat.Path, 'home', staticmethod(lambda: tmp_path))
    monkeypatch.setattr(chat.shutil, 'which', lambda _: None)
    assert '/2.1.308/' in chat.claude_binary()
    monkeypatch.setattr(chat.shutil, 'which', lambda _: '/usr/local/bin/claude')
    assert chat.claude_binary() == '/usr/local/bin/claude'
    monkeypatch.setattr(chat.shutil, 'which', lambda _: None)
    monkeypatch.setattr(chat.Path, 'home', staticmethod(lambda: tmp_path / 'empty'))
    assert chat.claude_binary() is None


def test_claude_logged_in_reads_auth_status(tmp_path, monkeypatch):
    """Login state comes from `auth status` JSON; errors count as logged out; results are cached briefly."""
    fake = tmp_path / 'claude'
    fake.write_text('#!/bin/sh\necho \'{"loggedIn": true, "authMethod": "claude.ai"}\'\n')
    fake.chmod(0o755)
    monkeypatch.setattr(chat, '_LOGIN_CACHE', {})
    assert chat.claude_logged_in(str(fake)) is True
    fake.write_text('#!/bin/sh\necho \'{"loggedIn": false}\'\n')
    assert chat.claude_logged_in(str(fake)) is True          # cached
    monkeypatch.setattr(chat, '_LOGIN_CACHE', {})
    assert chat.claude_logged_in(str(fake)) is False
    assert chat.claude_logged_in(str(tmp_path / 'missing')) is False


def test_claude_code_backend_unavailable_when_logged_out(monkeypatch):
    """A logged-out CLI doesn't count as an available backend (so auto falls back instead of erroring)."""
    monkeypatch.setattr(chat, 'claude_binary', lambda: '/x/claude')
    monkeypatch.setattr(chat, 'claude_logged_in', lambda b: False)
    assert chat.ClaudeCodeBackend.available() is False
    monkeypatch.setattr(chat, 'claude_logged_in', lambda b: True)
    assert chat.ClaudeCodeBackend.available() is True


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
        assert 'Cardiac imaging · Results'.encode() in r.read()
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
    assert status == 200 and 'api_messages' not in conv and len(conv['messages']) == 2
    assert all('html' in m for m in conv['messages'])          # both sides arrive rendered as Markdown
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


def test_cli_calls_never_inherit_stdin(monkeypatch):
    """Both CLI calls pass stdin=DEVNULL (an inherited open stdin made `claude` hang until the timeout)."""
    seen = []

    class Done:
        """Fake CompletedProcess."""
        stdout, stderr = '{"loggedIn": true}', ''

    monkeypatch.setattr(chat.subprocess, 'run', lambda cmd, **kw: seen.append(kw) or Done())
    monkeypatch.setattr(chat, '_LOGIN_CACHE', {})
    chat.claude_logged_in('/x/claude')
    chat._run_cli(['/x/claude', '-p', 'hi'])
    assert [kw.get('stdin') for kw in seen] == [chat.subprocess.DEVNULL, chat.subprocess.DEVNULL]


def _claude_code_conv(run_copy, monkeypatch):
    """A saved conversation answered by a (fake) Claude Code backend, with a session id."""
    class Done:
        """Fake CompletedProcess for `claude -p`."""
        stdout = json.dumps({'result': 'ok', 'session_id': 'sess-A', 'is_error': False})
        stderr = ''
    calls = []
    monkeypatch.setattr(chat, 'claude_binary', lambda: '/x/claude')
    monkeypatch.setattr(chat, '_run_cli', lambda cmd: calls.append(cmd) or Done())
    conv = chat.send(run_copy, 'figure1_decomposition', 'q1', engine=chat.ClaudeCodeBackend())
    return conv, calls


def test_open_in_claude_app_hands_off_and_follow_ups_fork(run_copy, monkeypatch):
    """`--desktop --resume <session>` runs under a pseudo-terminal; later panel messages fork instead of interleaving."""
    conv, calls = _claude_code_conv(run_copy, monkeypatch)
    desktop = []

    class Opened:
        """Fake output of `claude --desktop`."""
        stdout, stderr = 'Opening session sess-A in Claude Desktop', ''
    monkeypatch.setattr(chat, '_open_desktop', lambda cmd: desktop.append(cmd) or Opened())
    conv = chat.open_in_claude_app(conv['id'])
    assert desktop == [['/x/claude', '--desktop', '--resume', 'sess-A']]
    assert conv['handed_off'] is True and conv['app_session'] == 'local_sess-A'
    chat.send(run_copy, 'figure1_decomposition', 'q2', conv['id'], engine=chat.ClaudeCodeBackend())
    assert '--fork-session' in calls[-1] and calls[-1][calls[-1].index('--resume') + 1] == 'sess-A'
    assert chat.load(conv['id'])['handed_off'] is False             # the fork is now the panel's own session


def test_open_in_claude_app_errors(run_copy, monkeypatch):
    """Copy-paste conversations can't be handed off; a refusal from the app is reported in plain words."""
    plain = chat.send(run_copy, 'figure1_decomposition', 'x', engine=chat.HandoffBackend())
    with pytest.raises(ValueError, match='Only discussions answered by Claude Code'):
        chat.open_in_claude_app(plain['id'])
    conv, _ = _claude_code_conv(run_copy, monkeypatch)

    class Refused:
        """Fake failing output."""
        stdout, stderr = '', '--desktop requires a Claude subscription login'
    monkeypatch.setattr(chat, '_open_desktop', lambda cmd: Refused())
    with pytest.raises(RuntimeError, match="didn't accept"):
        chat.open_in_claude_app(conv['id'])


def test_open_desktop_uses_pty_and_no_stdin(monkeypatch):
    """The desktop hand-off runs through `script` (a pseudo-terminal) with stdin closed."""
    seen = []
    monkeypatch.setattr(chat.subprocess, 'run', lambda cmd, **kw: seen.append((cmd, kw)))
    chat._open_desktop(['/x/claude', '--desktop', '--resume', 's'])
    cmd, kw = seen[0]
    assert cmd[:3] == ['script', '-q', '/dev/null'] and kw['stdin'] == chat.subprocess.DEVNULL


def test_server_open_in_app_endpoint(app, monkeypatch):
    """POST /api/open-in-app returns 409 with a readable message when the conversation can't be handed off."""
    base, run = app
    token = _req(f'{base}/api/session')[1]['token']
    conv = _req(f'{base}/api/chat', {'run': run, 'stem': 'figure1_decomposition', 'message': 'x'}, token=token)[1]
    status, out = _req(f'{base}/api/open-in-app', {'conversation': conv['id']}, token=token)
    assert status == 400 and 'Only discussions answered by Claude Code' in out['error']


def test_server_label_endpoint(app):
    """POST /api/label saves the label (not synced for unpublished runs), clears it, and rejects unknown labels."""
    base, run = app
    token = _req(f'{base}/api/session')[1]['token']
    status, out = _req(f'{base}/api/label', {'run': run, 'label': 'success'}, token=token)
    assert status == 200 and out['review']['label'] == 'success' and out['synced_to_github'] is False
    assert json.loads((config.RUNS_DIR / run / 'manifest.json').read_text())['review']['label'] == 'success'
    assert _req(f'{base}/api/label', {'run': run, 'label': None}, token=token)[1]['review'] is None
    assert _req(f'{base}/api/label', {'run': run, 'label': 'nope'}, token=token)[0] == 400
    assert _req(f'{base}/api/label', {'run': run, 'label': 'success'})[0] == 403
