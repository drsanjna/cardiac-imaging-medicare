"""Local web server: serves RUNS_DIR (index + galleries) and a small JSON API for restore/undo/push and chart chats."""
import json
import secrets
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .. import config
from ..reporting import index, publish
from . import chat, restore

TOKEN = secrets.token_urlsafe(24)   # per server start; only same-origin pages can read it from /api/session


class Handler(SimpleHTTPRequestHandler):
    """Static files from RUNS_DIR plus /api/* endpoints (POSTs need the session token)."""

    server_version = 'CardiacRuns/1.0'

    def log_message(self, fmt, *args):
        """Quiet access log (errors still surface through responses)."""
        if self.path.startswith('/api/'):
            super().log_message(fmt, *args)

    def end_headers(self):
        """Never let the browser cache API answers or regenerated pages."""
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    # ── helpers ──
    def _host_ok(self):
        """Reject requests whose Host isn't this machine (blocks DNS-rebinding attacks)."""
        host = (self.headers.get('Host') or '').split(':')[0]
        return host in ('localhost', '127.0.0.1', '[::1]')

    def _json(self, status, payload):
        """Send a JSON response."""
        body = json.dumps(payload, default=str).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        """Parsed JSON request body ({} if empty)."""
        n = int(self.headers.get('Content-Length') or 0)
        return json.loads(self.rfile.read(n) or b'{}') if n else {}

    # ── routes ──
    def do_GET(self):
        """Static files, or a GET API route."""
        if not self._host_ok():
            return self._json(403, {'error': 'forbidden host'})
        url = urlparse(self.path)
        if not url.path.startswith('/api/'):
            if url.path in ('/', '/index.html'):
                _try_rebuild_index()
            return super().do_GET()
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        try:
            if url.path == '/api/session':
                engine = chat.backend()
                return self._json(200, {'token': TOKEN, 'chat_backend': engine.name, 'status': restore.status()})
            if url.path == '/api/status':
                return self._json(200, restore.status())
            if url.path == '/api/context':
                ctx = chat.context(q['run'], q['stem'])
                return self._json(200, {k: ctx[k] for k in ('label', 'title', 'caption', 'tag', 'snapshot', 'summary')}
                                  | {'code': [dict(ref=r, path=p, src=s) for r, p, s in ctx['code']],
                                     'tables': [n for n, _ in ctx['tables']]})
            if url.path == '/api/conversations':
                return self._json(200, [chat.with_html(c) for c in chat.list_conversations(q.get('run'), q.get('stem'))])
            return self._json(404, {'error': 'unknown endpoint'})
        except (KeyError, FileNotFoundError, ValueError) as e:
            return self._json(400, {'error': str(e)})

    def do_POST(self):
        """Mutating API routes; require the session token in X-App-Token."""
        if not self._host_ok():
            return self._json(403, {'error': 'forbidden host'})
        if not secrets.compare_digest(self.headers.get('X-App-Token', ''), TOKEN):
            return self._json(403, {'error': 'missing or wrong app token — reload the page'})
        path = urlparse(self.path).path
        try:
            b = self._body()
            if path == '/api/restore':
                return self._json(200, restore.restore_run(b['run']))
            if path == '/api/undo':
                return self._json(200, restore.undo(b['backup_tag']))
            if path == '/api/push':
                return self._json(200, restore.push())
            if path == '/api/fetch':
                publish.fetch_run(b['run'])
                _try_rebuild_index()
                return self._json(200, {'message': 'Downloaded.'})
            if path == '/api/chat':
                conv = chat.send(b['run'], b['stem'], b['message'].strip(), b.get('conversation'))
                return self._json(200, chat.with_html(conv))
            if path == '/api/open-in-app':
                return self._json(200, chat.with_html(chat.open_in_claude_app(b['conversation'])))
            if path == '/api/outcome':
                return self._json(200, chat.with_html(chat.set_outcome(b['conversation'], b['outcome'], b.get('note', ''))))
            return self._json(404, {'error': 'unknown endpoint'})
        except (restore.RestoreError, RuntimeError) as e:
            return self._json(409, {'error': str(e)})
        except (KeyError, ValueError, FileNotFoundError) as e:
            return self._json(400, {'error': f'bad request: {e}'})
        except Exception as e:   # surface git/subprocess failures to the UI in plain words
            return self._json(500, {'error': f'{type(e).__name__}: {e}'})


_index_lock = threading.Lock()


def _try_rebuild_index():
    """Refresh index.html so runs finished since the server started appear (best effort)."""
    with _index_lock:
        try:
            index.build(config.RUNS_DIR)
        except Exception as e:
            print(f"  index rebuild failed: {e}")


def make_server(port=None, host='127.0.0.1'):
    """A ready-to-serve server bound to localhost (port 0 picks a free port)."""
    config.RUNS_DIR.mkdir(parents=True, exist_ok=True)
    _try_rebuild_index()
    handler = partial(Handler, directory=str(config.RUNS_DIR))
    return ThreadingHTTPServer((host, config.APP_PORT if port is None else port), handler)
