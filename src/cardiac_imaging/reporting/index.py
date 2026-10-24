"""RUNS_DIR/index.html: the landing page — a filterable run list beside the selected run's summary, changes, labels and actions."""
import json
from pathlib import Path

from .. import config, gitinfo
from .gallery import CSS, esc
from .publish import MARKER, summary
from .run_store import list_runs

INDEX_CSS = """
body { height:100vh; display:flex; flex-direction:column; overflow:hidden; }
.appbar { background:var(--brand); color:var(--brand-ink); padding:10px 18px; display:flex; flex-wrap:wrap; gap:6px 18px; align-items:center; }
.appbar h1 { font-size:16px; margin:0; letter-spacing:.01em; } .appbar .meta { color:var(--brand-muted); font-size:12px; gap:4px 14px; }
.appbar .spacer { flex:1; }
.appbar kbd { background:rgba(255,255,255,.12); border-radius:4px; padding:0 5px; font-size:11px; font-family:inherit; }
.toolbar { display:flex; flex-wrap:wrap; gap:8px; align-items:center; padding:10px 18px; border-bottom:1px solid var(--line); background:var(--panel); }
.toolbar input { flex:1; min-width:180px; max-width:360px; background:var(--bg); color:var(--ink); border:1px solid var(--line); border-radius:8px; padding:7px 10px; font:inherit; font-size:14px; }
.seg { display:flex; flex-wrap:wrap; gap:4px; }
.seg button { border:1px solid var(--line); background:var(--panel); color:var(--ink); border-radius:999px; padding:4px 11px; font:inherit; font-size:13px; cursor:pointer; }
.seg button[aria-pressed="true"] { background:var(--accent); border-color:var(--accent); color:var(--accent-ink); }
.seg button .n { opacity:.7; margin-left:4px; font-variant-numeric:tabular-nums; }
.layout { flex:1; display:grid; grid-template-columns:minmax(260px, 340px) 1fr; min-height:0; }
#list { border-right:1px solid var(--line); overflow:auto; background:var(--panel); }
.row { display:block; width:100%; text-align:left; border:0; border-bottom:1px solid var(--line); background:transparent; color:var(--ink);
  padding:10px 14px 10px 12px; cursor:pointer; font:inherit; border-left:3px solid transparent; }
.row:hover { background:var(--bg); } .row[aria-selected="true"] { background:var(--accent-soft); border-left-color:var(--accent); }
.row .l1 { display:flex; align-items:center; gap:6px; font-weight:600; font-size:14px; }
.row .l2 { color:var(--muted); font-size:12px; margin-top:2px; display:flex; gap:8px; flex-wrap:wrap; }
.dot { width:8px; height:8px; border-radius:50%; flex:none; background:var(--line); }
.dot.ok { background:var(--ok); } .dot.failed { background:var(--bad); }
.pill { font-size:11px; font-weight:600; border-radius:999px; padding:1px 8px; background:var(--chip); color:var(--muted); }
.pill.success { background:var(--okbg); color:var(--ok); } .pill.failure { background:var(--badbg); color:var(--bad); }
.pill.needs_review { background:var(--warnbg); color:var(--warn); } .pill.archived { background:var(--chip); color:var(--muted); }
.pill.latest { background:var(--accent); color:var(--accent-ink); }
#detail { overflow:auto; padding:18px 22px 40px; }
.dhead { display:flex; flex-wrap:wrap; align-items:baseline; gap:8px 14px; }
.dhead h2 { margin:0; font-size:20px; } .dhead .sub { color:var(--muted); font-size:13px; }
.actions { display:flex; flex-wrap:wrap; gap:8px; margin:14px 0 6px; }
.btn { border:1px solid var(--line); background:var(--panel); color:var(--ink); border-radius:8px; padding:7px 13px; font:inherit; font-size:14px;
  cursor:pointer; text-decoration:none; display:inline-flex; align-items:center; gap:6px; }
.btn:hover { border-color:var(--accent); } .btn.primary { background:var(--accent); border-color:var(--accent); color:var(--accent-ink); }
.btn:disabled { opacity:.5; cursor:not-allowed; }
.panel { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:14px 16px; margin-top:14px; }
.panel h3 { margin:0 0 8px; font-size:12px; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); }
.panel p { margin:0; line-height:1.55; } .panel ul { margin:0; padding-left:18px; } .panel li { margin:3px 0; }
.tiles { display:grid; grid-template-columns:repeat(auto-fit, minmax(170px, 1fr)); gap:10px; margin-top:14px; }
.tile { background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:10px 12px; }
.tile .k { color:var(--muted); font-size:12px; } .tile .v { font-size:22px; font-weight:650; font-variant-numeric:tabular-nums; } .tile .s { color:var(--muted); font-size:12px; }
.two { display:grid; grid-template-columns:1fr 1fr; gap:14px; } .two .panel { margin-top:14px; }
.labelbar { display:flex; flex-wrap:wrap; gap:6px; align-items:center; }
.labelbar button { border:1px solid var(--line); background:var(--panel); color:var(--ink); border-radius:999px; padding:3px 10px; font:inherit; font-size:12px; cursor:pointer; }
.labelbar button[aria-pressed="true"] { border-color:var(--accent); background:var(--accent-soft); font-weight:600; }
.labelbar .note { margin-left:4px; }
.empty { color:var(--muted); padding:30px; text-align:center; }
.foot { color:var(--muted); font-size:12px; margin-top:18px; } .foot a { color:var(--muted); }
#toast { position:fixed; left:50%; bottom:20px; transform:translateX(-50%); background:var(--brand); color:var(--brand-ink); padding:11px 14px; border-radius:10px;
  box-shadow:0 6px 24px rgba(0,0,0,.25); display:flex; gap:10px; align-items:center; max-width:min(92vw, 720px); z-index:30; font-size:14px; }
#toast[hidden] { display:none; } #toast .btn { background:transparent; color:var(--brand-ink); border-color:rgba(255,255,255,.5); padding:3px 10px; }
dialog { border:1px solid var(--line); border-radius:12px; background:var(--panel); color:var(--ink); max-width:min(92vw, 520px); padding:20px; }
dialog::backdrop { background:rgba(0,0,0,.45); } dialog h3 { margin:0 0 8px; } dialog p { color:var(--muted); font-size:14px; }
dialog .actions { justify-content:flex-end; }
@media (max-width: 820px) { body { height:auto; overflow:auto; } .layout { grid-template-columns:1fr; } #list { max-height:45vh; border-right:0; border-bottom:1px solid var(--line); }
  .two { grid-template-columns:1fr; } }
"""

JS = """
const LOCAL = JSON.parse(document.getElementById('local-runs').textContent);
const REPO = document.body.dataset.repo, MARKER = document.body.dataset.marker;
const runs = new Map(LOCAL.map(r => [r.run_id, {...r, local: true}]));
const LABELS = {success: 'Success', failure: 'Failure', needs_review: 'Needs review', archived: 'Archived'};
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const when = (iso, o) => iso ? new Date(iso).toLocaleString(undefined, o || {month:'short', day:'numeric', year:'numeric', hour:'numeric', minute:'2-digit'}) : '—';
let APP = null, FILTER = 'active', SEL = null;

async function api(path, body) {
  const res = await fetch(path, body === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json','X-App-Token':APP.token}, body:JSON.stringify(body)});
  const data = await res.json().catch(() => ({error:`HTTP ${res.status}`}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`); return data;
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
const label = r => (r.review && r.review.label) || null;
function matches(r, f) {
  const l = label(r);
  if (f === 'active') return l !== 'archived';
  if (f === 'unlabeled') return !l;
  return f === 'all' ? true : l === f;
}
function sorted() { return [...runs.values()].sort((a, b) => (b.started || '').localeCompare(a.started || '')); }
function visible() {
  const q = $('#q').value.trim().toLowerCase();
  return sorted().filter(r => matches(r, FILTER) && (!q || [r.run_id, r.label, r.summary, label(r)].join(' ').toLowerCase().includes(q)));
}

function renderFilters() {
  const all = sorted(), count = f => all.filter(r => matches(r, f)).length;
  const opts = [['active', 'Active'], ['success', 'Success'], ['failure', 'Failure'], ['needs_review', 'Needs review'],
                ['unlabeled', 'Unlabeled'], ['archived', 'Archived'], ['all', 'All']];
  $('#filters').innerHTML = opts.map(([k, t]) => `<button data-filter="${k}" aria-pressed="${k === FILTER}">${t}<span class="n">${count(k)}</span></button>`).join('');
}
function renderList() {
  const list = visible(), latest = sorted()[0];
  if (SEL && !list.some(r => r.run_id === SEL)) SEL = null;
  if (!SEL && list.length) SEL = list[0].run_id;
  $('#list').innerHTML = list.map(r => {
    const h = (r.headline || {})['Adjusted IRR — All CTA-billing providers'];
    return `<button class="row" role="option" data-run="${esc(r.run_id)}" aria-selected="${r.run_id === SEL}">
      <div class="l1"><span class="dot ${r.status === 'ok' ? 'ok' : 'failed'}" title="${r.status === 'ok' ? 'completed' : 'stopped early'}"></span>
        ${esc(when(r.started))}${latest && r.run_id === latest.run_id ? '<span class="pill latest">latest</span>' : ''}
        ${label(r) ? `<span class="pill ${label(r)}">${LABELS[label(r)]}</span>` : ''}</div>
      <div class="l2">${r.label ? `<span>${esc(r.label)}</span>` : ''}${h ? `<span>IRR ${h.irr.toFixed(3)}</span>` : ''}
        <span>${r.local ? 'on this Mac' : 'GitHub only'}</span></div></button>`; }).join('') || '<div class="empty">No runs match.</div>';
  renderDetail();
}
function renderDetail() {
  const r = runs.get(SEL), d = $('#detail');
  if (!r) { d.innerHTML = '<div class="empty">Select a run.</div>'; return; }
  const id = esc(r.run_id), ok = r.status === 'ok', p = r.published, cmp = r.comparison || {}, prev = cmp.previous && runs.get(cmp.previous);
  const tiles = Object.entries(r.headline || {}).map(([k, h]) => `<div class="tile"><div class="k">${esc(k.replace('Adjusted IRR — ', 'Adjusted IRR · '))}</div>
    <div class="v">${h.irr.toFixed(3)}</div><div class="s">95% CI ${h.lo.toFixed(3)}–${h.hi.toFixed(3)}</div></div>`).join('');
  const li = xs => (xs || []).map(x => `<li>${esc(x)}</li>`).join('') || '<li>—</li>';
  const labelBtns = Object.entries(LABELS).map(([k, t]) => `<button data-label="${k}" aria-pressed="${label(r) === k}">${t}</button>`).join('')
    + (label(r) ? '<button data-label="">Clear</button>' : '');
  const open = r.local ? `<a class="btn primary" href="${id}/gallery.html">Open charts ↵</a>`
             : (p ? `<button class="btn primary" data-fetch="${id}">Download to this Mac</button>` : '');
  d.innerHTML = `
    <div class="dhead"><h2>${esc(when(r.started, {weekday:'short', month:'short', day:'numeric', year:'numeric', hour:'numeric', minute:'2-digit'}))}</h2>
      <span class="sub">${ok ? 'Completed' : 'Stopped early'} · ${Math.round(r.seconds || 0)} s · ${p ? 'saved to GitHub ' + esc(when(p.at)) : 'not yet on GitHub'}${r.label ? ' · ' + esc(r.label) : ''}</span></div>
    <div class="actions">${open}<button class="btn" data-restore="${id}">↺ Restore this version</button>
      ${r.local ? `<a class="btn" href="${id}/gallery.html#development">Development details</a>` : ''}
      ${p ? `<a class="btn" href="${esc(p.release_url)}" target="_blank" rel="noopener">GitHub record ↗</a>` : ''}</div>
    <div class="labelbar"><span class="note">Mark as:</span>${r.local ? labelBtns : '<span class="note">download the run to label it</span>'}</div>
    ${r.error ? `<div class="panel"><h3>Why it stopped</h3><p>Step <code>${esc(r.error.step)}</code>: ${esc(r.error.type)} — ${esc(r.error.message)}</p></div>` : ''}
    <div class="panel"><h3>Summary</h3><p>${esc(r.summary || 'No summary recorded for this run.')}</p></div>
    ${tiles ? `<div class="tiles">${tiles}</div>` : ''}
    <div class="two"><div class="panel"><h3>What changed${prev ? ' since ' + esc(when(prev.started)) : ''}</h3><ul>${li(cmp.changes)}</ul></div>
      <div class="panel"><h3>Impact on results</h3><ul>${li(cmp.impact)}</ul></div></div>
    <div class="foot">${esc(r.run_id)}</div>`;
}
function render() { renderFilters(); renderList(); }
function select(id) { SEL = id; document.querySelectorAll('.row').forEach(b => b.setAttribute('aria-selected', b.dataset.run === id)); renderDetail();
  const el = document.querySelector(`.row[data-run="${CSS.escape(id)}"]`); if (el) el.scrollIntoView({block: 'nearest'}); }

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
        runs.set(s.run_id, cur ? {...cur, published: s.published, review: cur.review || s.review} : {...s, local: false});
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
  $('#code').textContent = s ? `${s.branch} · ${s.subject}${s.dirty ? ' (unsaved edits)' : ''}` : 'Static view — start the app for Restore and labels';
}

async function setLabel(id, value) {
  if (!APP) return toast('Labels need the app: <code>python -m cardiac_imaging.app</code>');
  try {
    const out = await api('/api/label', {run: id, label: value || null});
    runs.get(id).review = out.review; render(); select(id);
    toast(value ? `Marked as ${LABELS[value]}${out.synced_to_github ? ' · saved to GitHub too' : ''}` : 'Label cleared', [], 3500);
  } catch (e) { toast('Could not save the label: ' + esc(e.message)); }
}
async function doRestore(id) {
  $('#confirm-when').textContent = when(runs.get(id).started); $('#confirm').showModal();
  const go = await new Promise(res => { $('#confirm-yes').onclick = () => res(true); $('#confirm-no').onclick = () => res(false); });
  $('#confirm').close(); if (!go) return;
  if (!APP) return toast('Restore needs the app: <code>python -m cardiac_imaging.app</code>');
  toast('Restoring…');
  try { const out = await api('/api/restore', {run: id}); toast(esc(out.message), out.changed ? [['Undo', () => undo(out.backup_tag)], ['Push to GitHub', push]] : []); loadApp(); }
  catch (e) { toast('Restore failed: ' + esc(e.message)); }
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
  if (!APP) return toast('Downloading needs the app (python -m cardiac_imaging.app).');
  toast('Downloading from GitHub…');
  try { await api('/api/fetch', {run: id}); location.reload(); } catch (e) { toast('Download failed: ' + esc(e.message)); }
}

document.addEventListener('click', e => {
  const t = e.target.closest('.row,[data-filter],[data-label],[data-restore],[data-fetch]'); if (!t) return;
  if (t.classList.contains('row')) select(t.dataset.run);
  else if (t.dataset.filter) { FILTER = t.dataset.filter; render(); }
  else if (t.dataset.label !== undefined) setLabel(SEL, t.dataset.label);
  else if (t.dataset.restore) doRestore(t.dataset.restore);
  else if (t.dataset.fetch) download(t.dataset.fetch);
});
document.addEventListener('keydown', e => {
  if (e.target.matches('input, textarea') || $('#confirm').open) { if (e.key === 'Escape') e.target.blur(); return; }
  const list = visible(), i = list.findIndex(r => r.run_id === SEL);
  if (e.key === '/') { e.preventDefault(); $('#q').focus(); }
  else if ((e.key === 'ArrowDown' || e.key === 'j') && i < list.length - 1) { e.preventDefault(); select(list[i + 1].run_id); }
  else if ((e.key === 'ArrowUp' || e.key === 'k') && i > 0) { e.preventDefault(); select(list[i - 1].run_id); }
  else if (e.key === 'Enter' && SEL && runs.get(SEL).local) location.href = `${SEL}/gallery.html`;
});
$('#q').addEventListener('input', render);
render(); loadApp(); loadGitHub();
"""


def build(runs_dir=None):
    """Rewrite index.html in runs_dir: local run summaries embedded; GitHub runs, labels and app actions loaded by the page."""
    runs_dir = Path(runs_dir or config.RUNS_DIR)
    local = [summary(m) for m in list_runs(runs_dir)]
    repo = gitinfo.repo_slug() or ''
    data = json.dumps(local, default=str).replace('</', '<\\/')
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cardiac imaging results</title><style>{CSS}{INDEX_CSS}</style></head>
<body data-repo="{esc(repo)}" data-marker="{esc(MARKER)}">
<header class="appbar"><h1>Cardiac imaging · Results</h1>
  <div class="meta"><span id="code"></span><span id="gh">Checking GitHub…</span></div><span class="spacer"></span>
  <div class="meta"><span><kbd>↑</kbd><kbd>↓</kbd> move</span><span><kbd>↵</kbd> open charts</span><span><kbd>/</kbd> search</span></div></header>
<div class="toolbar"><input id="q" type="search" placeholder="Search runs, summaries, labels…" aria-label="Search runs">
  <div class="seg" id="filters" role="group" aria-label="Filter runs"></div></div>
<div class="layout"><nav id="list" role="listbox" aria-label="Runs"></nav><main id="detail" aria-live="polite"></main></div>
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
