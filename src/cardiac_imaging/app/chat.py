"""Discuss a chart with Claude: builds context from the code that drew it (at the run's snapshot), its tables and data model."""
import ast
import base64
import json
import os
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

from .. import config, gitinfo
from ..db import schema
from ..figures.catalog import FIGURES
from ..reporting.run_store import read_manifest

OUTCOMES = ('open', 'supported', 'not_supported', 'inconclusive')
INSTRUCTIONS = (
    "You are helping a cardiology health-services researcher explore new hypotheses about one chart from their "
    "Medicare cardiac imaging analysis. Start from the code that generated the chart (given below, exactly as it was "
    "when the chart was made) and the data behind it. When the user proposes a hypothesis: restate it precisely, say "
    "what the current code and data can and cannot show, name the specific function(s) and data columns involved, "
    "propose the smallest concrete analysis (code change or query) that would test it, and flag confounders or "
    "data-model limits. Be direct and concise; plain English first, code second. Don't claim results you haven't seen."
)


# ── context ────────────────────────────────────────────────────────────────
def chart(stem):
    """Catalog entry for a chart stem (raises KeyError for unknown charts)."""
    for f in FIGURES:
        if f['stem'] == stem:
            return f
    raise KeyError(f"Unknown chart {stem!r}")


_PACKAGE_REPO = Path(__file__).resolve().parents[3]   # repo this package was installed from


def _file_at(rel_path, commit):
    """Text of a repo file at `commit`; falls back to the working tree, then to the installed package's copy."""
    if commit:
        text = gitinfo.git('show', f'{commit}:{rel_path}')
        if text:
            return text
    for root in (config.REPO_ROOT, _PACKAGE_REPO):
        if (root / rel_path).exists():
            return (root / rel_path).read_text()
    return ''


def function_source(ref, commit=None):
    """('src/cardiac_imaging/x.py', 'def f(...): ...') for 'module:function' at `commit`; empty source if not found."""
    module, func = ref.split(':')
    rel = f"src/cardiac_imaging/{module.replace('.', '/')}.py"
    text = _file_at(rel, commit)
    try:
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func:
                return rel, ast.get_source_segment(text, node) or ''
    except SyntaxError:
        pass
    return rel, ''


def data_model_text():
    """Compact text description of the tables and the columns the analysis uses."""
    lines = []
    for t in schema.TABLES:
        lines.append(f"- {t['name']} ({t['kind'].lower()}): {t['grain']}")
        lines += [f"    {c} ({typ}): {meaning}" for c, typ, meaning, used in t['columns'] if used]
    return '\n'.join(lines)


def context(run_id, stem):
    """Everything Claude needs about one chart in one run: metadata, generating code, tables, data model, run summary."""
    run_dir = config.RUNS_DIR / run_id
    m = read_manifest(run_dir)
    f = chart(stem)
    snap = (m.get('code') or {}).get('snapshot')
    code = [(ref, *function_source(ref, snap)) for ref in f.get('sources', [])]
    tables = []
    for name in f.get('tables', []):
        p = run_dir / 'tables' / f'{name}.csv'
        if p.exists():
            tables.append((name, p.read_text()[:20000]))
    image = run_dir / 'figures' / 'thumbs' / f'{stem}.png'
    if not image.exists():
        image = run_dir / 'figures' / f'{stem}.png'
    return dict(run_id=run_id, stem=stem, label=f['label'], title=f['title'], caption=f['caption'],
                snapshot=snap, tag=(m.get('code') or {}).get('tag'), summary=m.get('summary', ''),
                code=code, tables=tables, data_model=data_model_text(), image=str(image))


def context_text(ctx):
    """The context as one text block (system prompt for the API, appended prompt for Claude Code, or copyable prompt)."""
    parts = [INSTRUCTIONS, '',
             f"# Chart: {ctx['label']} — {ctx['title']}", ctx['caption'],
             f"Run {ctx['run_id']}; code snapshot {ctx['tag']} ({(ctx['snapshot'] or 'unknown')[:12]}). "
             f"Restore that exact code with: git checkout {ctx['tag']}",
             f"Chart image: {ctx['image']}", '', f"Run summary: {ctx['summary']}", '',
             '# Code that generated the chart (plotting function first, then the analysis and data loading it uses)']
    for ref, path, src in ctx['code']:
        parts += [f"## {ref}  ({path})", '```python', src or '# (source not found at this snapshot)', '```']
    parts += ['', '# Result tables behind the chart (CSV)']
    for name, csv in ctx['tables']:
        parts += [f'## {name}', '```csv', csv.strip(), '```']
    parts += ['', '# Data model (columns the analysis uses)', ctx['data_model']]
    return '\n'.join(parts)


# ── conversations ──────────────────────────────────────────────────────────
def _path(conv_id):
    """File holding one conversation."""
    if not conv_id or any(c not in '0123456789abcdef-' for c in conv_id):
        raise ValueError('bad conversation id')
    return config.CONVERSATIONS_DIR / f'{conv_id}.json'


def load(conv_id):
    """A saved conversation."""
    return json.loads(_path(conv_id).read_text())


def save(conv):
    """Write a conversation to CONVERSATIONS_DIR."""
    config.CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)
    conv['updated'] = datetime.now().astimezone().isoformat(timespec='seconds')
    _path(conv['id']).write_text(json.dumps(conv, indent=2, default=str))


def new_conversation(run_id, stem):
    """Start an empty conversation about one chart."""
    f = chart(stem)
    now = datetime.now().astimezone().isoformat(timespec='seconds')
    return dict(id=str(uuid.uuid4()), run_id=run_id, stem=stem, label=f['label'], title=f['title'], started=now,
                updated=now, backend=None, session_id=None, api_messages=[], messages=[], outcome='open', outcome_note='')


def list_conversations(run_id=None, stem=None):
    """Saved conversations (newest first), optionally for one run and/or chart."""
    out = []
    for p in sorted(config.CONVERSATIONS_DIR.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            c = json.loads(p.read_text())
        except ValueError:
            continue
        if (run_id is None or c['run_id'] == run_id) and (stem is None or c['stem'] == stem):
            out.append({k: c.get(k) for k in ('id', 'run_id', 'stem', 'label', 'title', 'started', 'updated',
                                              'outcome', 'outcome_note', 'messages', 'backend', 'session_id',
                                              'handed_off', 'app_session')})
    return out


def with_html(conv):
    """Copy of a conversation for the browser: every message gains rendered Markdown (`html`); API history dropped."""
    from .markdown import render
    out = {k: v for k, v in conv.items() if k != 'api_messages'}
    out['messages'] = [dict(m, html=render(m.get('text', ''))) for m in conv.get('messages', [])]
    return out


def open_in_claude_app(conv_id):
    """Hand a Claude Code discussion to the Claude desktop app (`claude --desktop --resume <session>`), where it stays in
    the session sidebar. Later messages typed in the panel continue on a fork, so the two never interleave."""
    conv = load(conv_id)
    if conv.get('backend') != 'claude-code' or not conv.get('session_id'):
        raise ValueError('Only discussions answered by Claude Code can be opened in the Claude app.')
    binary = claude_binary()
    if not binary:
        raise RuntimeError('Claude Code was not found on this Mac.')
    out = _open_desktop([binary, '--desktop', '--resume', conv['session_id']])
    text = (out.stdout or '') + (out.stderr or '')
    if 'Opening session' not in text:
        raise RuntimeError(f"The Claude app didn't accept the session: {text.strip()[:300] or 'no output'}")
    conv['handed_off'], conv['app_session'] = True, f"local_{conv['session_id']}"
    save(conv)
    return conv


def _open_desktop(cmd):
    """Run a `claude --desktop …` command under a pseudo-terminal (it refuses redirected output) with no stdin."""
    return subprocess.run(['script', '-q', '/dev/null', *cmd], capture_output=True, text=True, timeout=60,
                          stdin=subprocess.DEVNULL, cwd=config.REPO_ROOT)


def set_outcome(conv_id, outcome, note=''):
    """Record what the discussion concluded about the hypothesis (open / supported / not_supported / inconclusive)."""
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {OUTCOMES}")
    conv = load(conv_id)
    conv['outcome'], conv['outcome_note'] = outcome, note
    save(conv)
    return conv


# ── backends ───────────────────────────────────────────────────────────────
BUNDLED_CLI_GLOB = 'Library/Application Support/Claude/claude-code/*/*/claude.app/Contents/MacOS/claude'
_LOGIN_CACHE = {}   # binary -> (checked_at, logged_in); re-checked every 20 s so a fresh login is picked up live


def _version_key(path):
    """Sort key from the version folder of a bundled CLI path (…/claude-code/2.1.308/…)."""
    part = Path(path).parents[4].name
    return tuple(int(x) if x.isdigit() else 0 for x in part.split('.'))


def claude_binary():
    """Claude Code CLI to use: CARDIAC_CLAUDE_BIN or `claude` on PATH, else the newest copy bundled with the Claude desktop app."""
    found = shutil.which(config.CLAUDE_BIN)
    if found:
        return found
    bundled = sorted(Path.home().glob(BUNDLED_CLI_GLOB), key=_version_key)
    return str(bundled[-1]) if bundled else None


def claude_logged_in(binary):
    """Whether `binary auth status` reports a login usable outside the desktop app (cached for 20 s)."""
    import time
    now = time.time()
    cached = _LOGIN_CACHE.get(binary)
    if cached and now - cached[0] < 20:
        return cached[1]
    try:
        # stdin=DEVNULL: otherwise the CLI waits for input inherited from the server process and times out.
        out = subprocess.run([binary, 'auth', 'status'], capture_output=True, text=True, timeout=20,
                             stdin=subprocess.DEVNULL)
        ok = bool(json.loads(out.stdout or '{}').get('loggedIn'))
    except (OSError, ValueError, subprocess.SubprocessError):
        ok = False
    _LOGIN_CACHE[binary] = (now, ok)
    return ok


def _run_cli(cmd):
    """Run the Claude Code CLI from the repo root (separate function so tests can replace it)."""
    # stdin=DEVNULL: `claude -p` reads piped stdin as extra input and would block on the server's inherited stdin.
    return subprocess.run(cmd, cwd=config.REPO_ROOT, capture_output=True, text=True, timeout=900,
                          stdin=subprocess.DEVNULL)


class ClaudeCodeBackend:
    """Claude Code CLI in print mode, read-only tools, resuming the same session each turn (uses your Claude login)."""

    name = 'claude-code'

    @staticmethod
    def available():
        """True when a Claude Code CLI is found and logged in."""
        binary = claude_binary()
        return bool(binary) and claude_logged_in(binary)

    def reply(self, conv, message, ctx):
        """Send `message` and return Claude's answer; stores the session id on `conv`."""
        cmd = [claude_binary(), '-p', message, '--output-format', 'json',
               '--tools', 'Read,Grep,Glob', '--permission-mode', 'dontAsk',
               '--add-dir', str(Path(ctx['image']).parent), '--model', config.CHAT_MODEL]
        if conv.get('session_id'):
            cmd += ['--resume', conv['session_id']]
            if conv.get('handed_off'):   # the original now lives in the Claude app: continue on a copy, never interleave
                cmd += ['--fork-session']
        else:
            cmd += ['--append-system-prompt', context_text(ctx)]
        out = _run_cli(cmd)
        try:
            data = json.loads(out.stdout)
        except ValueError:
            raise RuntimeError(f"Claude Code failed: {(out.stderr or out.stdout).strip()[:500]}")
        if data.get('is_error'):
            raise RuntimeError(f"Claude Code error: {data.get('result') or data.get('subtype')}")
        conv['session_id'] = data.get('session_id') or conv.get('session_id')
        conv['handed_off'] = False
        return data.get('result', '')


class AnthropicBackend:
    """Anthropic Messages API (needs the `anthropic` package and an API key or `ant auth login` profile)."""

    name = 'api'

    @staticmethod
    def available():
        """True when the SDK is installed and credentials look configured."""
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return bool(os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('ANTHROPIC_AUTH_TOKEN')
                    or (Path.home() / '.config' / 'anthropic').exists())

    def reply(self, conv, message, ctx):
        """Send `message` (with the chart image on the first turn) and return the text answer."""
        import anthropic
        content = [{'type': 'text', 'text': message}]
        if not conv['api_messages'] and Path(ctx['image']).exists():
            data = base64.standard_b64encode(Path(ctx['image']).read_bytes()).decode()
            content.insert(0, {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png', 'data': data}})
        conv['api_messages'].append({'role': 'user', 'content': content})
        client = anthropic.Anthropic()
        try:
            resp = client.beta.messages.create(
                model=config.CHAT_MODEL, max_tokens=16000, system=context_text(ctx),
                messages=conv['api_messages'], output_config={'effort': 'high'},
                betas=['server-side-fallback-2026-07-01'], fallbacks='default')
        except anthropic.AuthenticationError:
            conv['api_messages'].pop()
            raise RuntimeError('The Anthropic API key was rejected.')
        except anthropic.RateLimitError:
            conv['api_messages'].pop()
            raise RuntimeError('Rate limited by the Anthropic API — try again in a minute.')
        except anthropic.APIStatusError as e:
            conv['api_messages'].pop()
            raise RuntimeError(f'Anthropic API error {e.status_code}: {e.message}')
        except anthropic.APIConnectionError:
            conv['api_messages'].pop()
            raise RuntimeError("Couldn't reach the Anthropic API (network).")
        # Append the full content (thinking/fallback blocks included) so later turns stay valid.
        conv['api_messages'].append({'role': 'assistant', 'content': [b.to_dict() for b in resp.content]})
        if resp.stop_reason == 'refusal':
            return "Claude declined to answer this one. Try rephrasing the hypothesis."
        return '\n'.join(b.text for b in resp.content if b.type == 'text')


class HandoffBackend:
    """No model available: return a ready-made prompt to paste into Claude Code."""

    name = 'handoff'

    @staticmethod
    def available():
        """Always available."""
        return True

    def reply(self, conv, message, ctx):
        """Explain the one step that enables live chat here, and return the full prompt to copy meanwhile."""
        return f"{setup_hint()}\n\n---\n{context_text(ctx)}\n\n# My hypothesis\n{message}"


def setup_hint():
    """Plain-English instruction for turning on live chat on this Mac (depends on what is installed)."""
    binary = claude_binary()
    if binary:
        return ("Live chat is one step away: Claude Code is already on this Mac (it comes with the Claude app) but isn't "
                "logged in for use outside the app. Run this once in Terminal, approve the login in your browser, then "
                f"click Send again — no restart needed:\n\n    \"{binary}\" auth login\n\n"
                "Meanwhile, here's a ready-made prompt you can paste into Claude Code (it includes the chart's code, "
                "tables and data model).")
    return ("Live chat isn't set up on this Mac yet. Install Claude Code (`brew install --cask claude-code`, then run "
            "`claude auth login` once) and click Send again. Meanwhile, here's a ready-made prompt you can paste into "
            "Claude Code (it includes the chart's code, tables and data model).")


BACKENDS = {'claude-code': ClaudeCodeBackend, 'api': AnthropicBackend, 'handoff': HandoffBackend}


def backend():
    """The configured backend, or with CHAT_BACKEND=auto the first available of claude-code → api → handoff."""
    if config.CHAT_BACKEND != 'auto':
        return BACKENDS[config.CHAT_BACKEND]()
    for cls in (ClaudeCodeBackend, AnthropicBackend, HandoffBackend):
        if cls.available():
            return cls()


def send(run_id, stem, message, conv_id=None, engine=None):
    """Add a user message to a (new or existing) conversation about a chart, get Claude's reply, save, return the conversation."""
    conv = load(conv_id) if conv_id else new_conversation(run_id, stem)
    engine = engine or backend()
    ctx = context(conv['run_id'], conv['stem'])
    now = datetime.now().astimezone().isoformat(timespec='seconds')
    conv['messages'].append(dict(role='user', text=message, at=now))
    try:
        answer = engine.reply(conv, message, ctx)
    except Exception as e:
        answer = f"⚠️ {e}"
    conv['backend'] = engine.name
    conv['messages'].append(dict(role='assistant', text=answer, at=datetime.now().astimezone().isoformat(timespec='seconds')))
    save(conv)
    return conv
