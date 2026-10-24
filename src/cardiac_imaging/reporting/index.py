"""RUNS_DIR/index.html: results history — when each run happened, what it found (plain English), what changed, one-click restore."""
import json
from pathlib import Path

from .. import config, gitinfo
from .gallery import CSS, esc
from .publish import MARKER, summary
from .run_store import list_runs

INDEX_CSS = """
main.wrap { max-width:920px; }
.bar { display:flex; flex-wrap:wrap; gap:10px; align-items:center; justify-content:space-between; margin:16px 0 6px; }
.bar input { flex:1; min-width:200px; background:var(--panel); color:var(--ink); border:1px solid var(--line); border-radius:10px; padding:8px 12px; font:inherit; }
.run { background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:16px 18px; margin:14px 0; box-shadow:var(--shadow); }
.run .when { font-size:18px; font-weight:650; display:flex; flex-wrap:wrap; align-items:center; gap:8px; }
.run .sub { color:var(--muted); font-size:13px; margin-top:2px; }
.run p.summary { margin:10px 0 12px; font-size:15px; line-height:1.55; }
.actions { display:flex; flex-wrap:wrap; gap:8px; }
.btn { border:1px solid var(--line); background:var(--chip); color:var(--ink); border-radius:10px; padding:7px 14px; font:inherit; font-size:14px; cursor:pointer; text-decoration:none; display:inline-flex; align-items:center; gap:6px; }
.btn.primary { background:var(--accent); color:#fff; border-color:transparent; }
.btn:disabled { opacity:.5; cursor:not-allowed; }
.changes { margin-top:12px; padding:12px 14px; border-radius:10px; background:var(--bg); border:1px solid var(--line); font-size:14px; }
.changes h4 { margin:0 0 6px; font-size:13px; text-transform:uppercase; letter-spacing:.04em; color:var(--muted); }
.changes ul { margin:0 0 10px; padding-left:18px; }
.tag { font-size:11px; border-radius:999px; padding:1px 8px; background:var(--chip); color:var(--muted); font-weight:500; }
.tag.latest { background:var(--accent); color:#fff; }
.ok-dot { color:var(--ok); } .bad-dot { color:var(--bad); }
.tech { font-size:12px; color:var(--muted); margin-top:10px; }
.tech a { color:var(--muted); }
#toast { position:fixed; left:50%; bottom:22px; transform:translateX(-50%); background:var(--ink); color:var(--bg); padding:12px 16px; border-radius:12px;
  box-shadow:0 6px 24px rgba(0,0,0,.25); display:flex; gap:10px; align-items:center; max-width:min(92vw, 720px); z-index:30; font-size:14px; }
#toast[hidden] { display:none; } #toast .btn { background:transparent; color:var(--bg); border-color:var(--bg); padding:4px 10px; }
dialog { border:1px solid var(--line); border-radius:14px; background:var(--panel); color:var(--ink); max-width:min(92vw, 520px); padding:20px; }
dialog::backdrop { background:rgba(0,0,0,.45); }
dialog h3 { margin:0 0 8px; } dialog p { color:var(--muted); font-size:14px; } dialog .actions { justify-content:flex-end; margin-top:14px; }
"""

JS = """
const LOCAL = JSON.parse(document.getElementById('local-runs').textContent);
const REPO = document.body.dataset.repo, MARKER = document.body.dataset.marker;
const runs = new Map(LOCAL.map(r => [r.run_id, {...r, local: true}]));
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const when = iso => iso ? new Date(iso).toLocaleString(undefined, {weekday:'short', month:'short', day:'numeric', year:'numeric', hour:'numeric', minute:'2-digit'}) : '—';
let APP = null;   // {token, chat_backend, status} when served by the local app

async function api(path, body) {
  const res = await fetch(path, body === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json','X-App-Token':APP.token}, body:JSON.stringify(body)});
  const data = await res.json().catch(() => ({error:`HTTP ${res.status}`}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}
function toast(html, actions = [], ms = 0) {
  const t = $('#toast'); t.innerHTML = `<span>${html}</span>`;
  for (const [label, fn] of actions) { const b = document.createElement('button'); b.className = 'btn'; b.textContent = label; b.onclick = fn; t.append(b); }
  const x = document.createElement('button'); x.className = 'btn'; x.textContent = '✕'; x.onclick = () => t.hidden = true; t.append(x);
  t.hidden = false; if (ms) setTimeout(() => t.hidden = true, ms);
}

function decode(body) {
  const i = (body || '').indexOf(MARKER); if (i < 0) return null;
  const b64 = body.slice(i + MARKER.length).split('-->')[0].trim();
  return JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(b64), c => c.charCodeAt(0))));
}

function card(r, isLatest) {
  const id = esc(r.run_id), ok = r.status === 'ok', p = r.published, cmp = r.comparison || {};
  const prev = cmp.previous && runs.get(cmp.previous);
  const open = r.local ? `<a class="btn primary" href="${id}/gallery.html">Open charts</a>`
             : (p ? `<button class="btn primary" data-fetch="${id}">Download to this Mac</button>` : '');
  const changes = (cmp.changes || []).map(x => `<li>${esc(x)}</li>`).join('');
  const impact = (cmp.impact || []).map(x => `<li>${esc(x)}</li>`).join('');
  const tech = [r.local ? `<a href="${id}/gallery.html#details">technical details</a>` : '', p ? `<a href="${esc(p.release_url)}">GitHub record</a>` : ''].filter(Boolean).join(' · ');
  return `<article class="run" data-text="${esc([r.run_id, r.label, r.summary].join(' ').toLowerCase())}">
    <div class="when"><span class="${ok ? 'ok-dot' : 'bad-dot'}">${ok ? '✓' : '✗'}</span>${when(r.started)}
      ${isLatest ? '<span class="tag latest">latest</span>' : ''}${r.label ? `<span class="tag">${esc(r.label)}</span>` : ''}
      ${!r.local ? '<span class="tag">on GitHub only</span>' : ''}</div>
    <div class="sub">${ok ? 'Completed' : 'Stopped early'} in ${Math.round(r.seconds || 0)} s${p ? ` · saved to GitHub ${when(p.at)}` : ' · not yet saved to GitHub'}</div>
    <p class="summary">${esc(r.summary || 'No summary for this run yet.')}</p>
    <div class="actions">${open}
      <button class="btn" data-toggle="${id}">What changed &amp; impact ▾</button>
      <button class="btn" data-restore="${id}">↺ Restore this version</button></div>
    <div class="changes" id="ch-${id}" hidden>
      <h4>What changed${prev ? ' since ' + esc(when(prev.started)) : ''}</h4><ul>${changes || '<li>No comparison recorded for this run.</li>'}</ul>
      <h4>Impact on results</h4><ul>${impact || '<li>—</li>'}</ul></div>
    ${tech ? `<div class="tech">${tech}</div>` : ''}
  </article>`;
}

function render() {
  const list = [...runs.values()].sort((a, b) => (b.started || '').localeCompare(a.started || ''));
  const q = $('#q').value.trim().toLowerCase();
  $('#runs').innerHTML = list.map((r, i) => card(r, i === 0)).join('') || '<p class="note">No runs yet — run the analysis to create one.</p>';
  if (q) document.querySelectorAll('.run').forEach(el => el.hidden = !el.dataset.text.includes(q));
  $('#counts').textContent = `${list.length} run${list.length === 1 ? '' : 's'}`;
}

async function loadGitHub() {
  if (!REPO) return;
  try {
    for (let page = 1; page <= 10; page++) {
      const res = await fetch(`https://api.github.com/repos/${REPO}/releases?per_page=100&page=${page}`, {headers:{Accept:'application/vnd.github+json'}});
      if (!res.ok) throw new Error(`GitHub ${res.status}`);
      const rels = await res.json();
      for (const rel of rels) {
        const s = decode(rel.body); if (!s) continue;
        s.published = {at: rel.published_at, release_url: rel.html_url, tag: rel.tag_name,
                       assets: Object.fromEntries((rel.assets || []).map(a => [a.name, a.browser_download_url]))};
        const cur = runs.get(s.run_id);
        runs.set(s.run_id, cur ? {...cur, published: s.published} : {...s, local: false});
      }
      if (rels.length < 100) break;
    }
    $('#gh').textContent = 'Synced with GitHub';
  } catch (e) { $('#gh').textContent = 'GitHub unreachable — showing runs on this Mac'; }
  render();
}

async function loadApp() {
  try { APP = await api('/api/session'); } catch (e) { APP = null; }
  const s = APP && APP.status;
  $('#code').textContent = s ? `Code: ${s.branch} — ${s.subject}${s.dirty ? ' (unsaved edits)' : ''}` : 'Open via the app (python -m cardiac_imaging.app) to enable Restore';
}

async function doRestore(id) {
  const r = runs.get(id);
  const dlg = $('#confirm');
  $('#confirm-when').textContent = when(r.started);
  dlg.showModal();
  const go = await new Promise(res => { $('#confirm-yes').onclick = () => res(true); $('#confirm-no').onclick = () => res(false); });
  dlg.close(); if (!go) return;
  if (!APP) return toast('Restore needs the local app. Start it with <code>python -m cardiac_imaging.app</code>.');
  toast('Restoring…');
  try {
    const out = await api('/api/restore', {run: id});
    toast(esc(out.message), out.changed ? [['Undo', () => undo(out.backup_tag)], ['Push to GitHub', push]] : []);
    loadApp();
  } catch (e) { toast('Restore failed: ' + esc(e.message)); }
}
async function undo(tag) {
  toast('Undoing…');
  try { const out = await api('/api/undo', {backup_tag: tag}); toast(esc(out.message.replace('restored', 'brought back')), [['Push to GitHub', push]]); loadApp(); }
  catch (e) { toast('Undo failed: ' + esc(e.message)); }
}
async function push() {
  toast('Pushing to GitHub…');
  try { const out = await api('/api/push', {}); toast(esc(out.message), [], 5000); } catch (e) { toast('Push failed: ' + esc(e.message)); }
}
async function download(id) {
  if (!APP) return toast('Downloading needs the local app (python -m cardiac_imaging.app).');
  toast('Downloading from GitHub…');
  try { await api('/api/fetch', {run: id}); location.reload(); } catch (e) { toast('Download failed: ' + esc(e.message)); }
}

document.addEventListener('click', e => {
  const t = e.target.closest('[data-toggle],[data-restore],[data-fetch]'); if (!t) return;
  if (t.dataset.toggle) { const el = document.getElementById('ch-' + t.dataset.toggle); el.hidden = !el.hidden;
    t.textContent = el.hidden ? 'What changed & impact ▾' : 'What changed & impact ▴'; }
  if (t.dataset.restore) doRestore(t.dataset.restore);
  if (t.dataset.fetch) download(t.dataset.fetch);
});
$('#q').addEventListener('input', render);
render(); loadApp(); loadGitHub();
"""


def build(runs_dir=None):
    """Rewrite index.html in runs_dir: local run summaries embedded; GitHub runs and app actions loaded by the page."""
    runs_dir = Path(runs_dir or config.RUNS_DIR)
    local = [summary(m) for m in list_runs(runs_dir)]
    repo = gitinfo.repo_slug() or ''
    data = json.dumps(local, default=str).replace('</', '<\\/')
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cardiac imaging results</title><style>{CSS}{INDEX_CSS}</style></head>
<body data-repo="{esc(repo)}" data-marker="{esc(MARKER)}">
<header class="top"><div class="wrap" style="max-width:920px"><h1>Cardiac imaging — results history</h1>
  <div class="meta"><span id="counts"></span><span id="gh">Checking GitHub…</span><span id="code"></span></div></div></header>
<main class="wrap">
  <div class="bar"><input id="q" type="search" placeholder="Search runs…" aria-label="Search runs"></div>
  <div id="runs"></div>
</main>
<dialog id="confirm"><h3>Restore the code to this version?</h3>
  <p>The code will be put back exactly as it was for the run of <strong id="confirm-when"></strong>.
  Your current code is saved first, so you can undo this. Nothing is deleted and nothing is pushed until you choose to.</p>
  <div class="actions"><button class="btn" id="confirm-no">Cancel</button><button class="btn primary" id="confirm-yes">Restore</button></div></dialog>
<div id="toast" hidden role="status" aria-live="polite"></div>
<script type="application/json" id="local-runs">{data}</script>
<script>{JS}</script>
</body></html>
"""
    (runs_dir / 'index.html').write_text(page, encoding='utf-8')
