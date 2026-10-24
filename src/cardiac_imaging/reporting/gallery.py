"""Per-run gallery.html (every chart, grouped by section, with a full-screen viewer and results tables) and all_figures.pdf."""
import html
import json
from pathlib import Path

import pandas as pd

from ..figures.catalog import FIGURES, SECTIONS
from . import run_store

# Tables shown on the page, in order; every other CSV in tables/ is listed as a download.
SHOWN_TABLES = [
    ('nb_density_models', 'Density models — IRR per +1 NPI per 100,000 FFS beneficiaries (Figures 8, 9, S1, S2)'),
    ('table1_specialty_distribution', 'Table 1 — Provider specialty distribution by modality, 2023'),
    ('change_summary', '2018 → 2023 change in volume, enrollment and rate (%)'),
    ('national_market_share', 'National market share by modality (%)'),
    ('state_summary_2023', 'State rate per 1,000 FFS beneficiaries, 2023 (sorted by all cardiac)'),
    ('filter_log', 'Row filters applied (nothing is dropped silently)'),
]

CSS = """
:root { --bg:#f7f7f5; --panel:#ffffff; --ink:#1d1d1b; --muted:#6b6b66; --line:#e3e2dc; --accent:#6b2c91;
        --ok:#1e7f4f; --okbg:#e3f4ea; --bad:#b42318; --badbg:#fde8e6; --chip:#efeef3; --shadow:0 1px 2px rgba(0,0,0,.06); }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg:#141413; --panel:#1f1f1d; --ink:#ecebe6; --muted:#a3a29b; --line:#34332f; --accent:#c79ee6;
  --ok:#6fd39b; --okbg:#173326; --bad:#ff8a80; --badbg:#3a1a17; --chip:#2a2930; --shadow:none; } }
:root[data-theme="dark"] { --bg:#141413; --panel:#1f1f1d; --ink:#ecebe6; --muted:#a3a29b; --line:#34332f;
  --accent:#c79ee6; --ok:#6fd39b; --okbg:#173326; --bad:#ff8a80; --badbg:#3a1a17; --chip:#2a2930; --shadow:none; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, sans-serif; }
a { color:var(--accent); }
.wrap { max-width:1280px; margin:0 auto; padding:0 16px; }
header.top { position:sticky; top:0; z-index:5; background:var(--bg); border-bottom:1px solid var(--line); padding:14px 0 10px; }
h1 { font-size:20px; margin:4px 0; } h2 { font-size:17px; margin:32px 0 12px; } .mono { font-family:ui-monospace, Menlo, monospace; font-size:.92em; }
.meta { color:var(--muted); font-size:13px; display:flex; flex-wrap:wrap; gap:4px 14px; }
nav { display:flex; flex-wrap:wrap; gap:6px; margin-top:10px; }
nav a, .chip { background:var(--chip); color:var(--ink); text-decoration:none; padding:3px 10px; border-radius:999px; font-size:13px; }
.badge { padding:1px 8px; border-radius:999px; font-size:12px; font-weight:600; }
.badge.ok { color:var(--ok); background:var(--okbg); } .badge.failed, .badge.running { color:var(--bad); background:var(--badbg); }
.cards { display:grid; grid-template-columns:repeat(auto-fill, minmax(min(100%, 230px), 1fr)); gap:12px; margin-top:16px; }
.stat { background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:12px 14px; box-shadow:var(--shadow); }
.stat .k { color:var(--muted); font-size:12px; } .stat .v { font-size:22px; font-weight:650; } .stat .s { color:var(--muted); font-size:12px; }
.note { margin-top:10px; color:var(--muted); font-size:13px; }
.error { background:var(--badbg); color:var(--bad); border-radius:10px; padding:12px 14px; margin-top:16px; }
.grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(min(100%, 560px), 1fr)); gap:16px; }
figure.card { margin:0; background:var(--panel); border:1px solid var(--line); border-radius:12px; overflow:hidden; box-shadow:var(--shadow); }
figure.card button { all:unset; display:block; cursor:zoom-in; background:#fff; width:100%; }
figure.card img { display:block; width:100%; height:300px; object-fit:contain; padding:8px; }
figcaption { padding:10px 14px 12px; border-top:1px solid var(--line); }
figcaption .label { color:var(--accent); font-weight:650; margin-right:6px; } figcaption p { margin:4px 0 6px; color:var(--muted); font-size:13px; }
.links a { font-size:13px; margin-right:10px; }
.missing { padding:40px 14px; text-align:center; color:var(--muted); }
details { background:var(--panel); border:1px solid var(--line); border-radius:10px; margin-bottom:10px; }
summary { cursor:pointer; padding:10px 14px; font-weight:600; } summary a { font-weight:400; font-size:13px; margin-left:8px; }
.tablewrap { overflow:auto; max-height:480px; border-top:1px solid var(--line); }
table { border-collapse:collapse; font-size:13px; width:100%; font-variant-numeric:tabular-nums; }
th, td { padding:5px 10px; border-bottom:1px solid var(--line); text-align:right; white-space:nowrap; }
th:first-child, td:first-child { text-align:left; } thead th { position:sticky; top:0; background:var(--panel); }
#lightbox { position:fixed; inset:0; background:rgba(10,10,10,.94); z-index:20; display:flex; flex-direction:column; }
#lightbox[hidden] { display:none; }
#lb-stage { flex:1; overflow:hidden; position:relative; cursor:grab; touch-action:none; }
#lb-stage.dragging { cursor:grabbing; }
#lb-img { position:absolute; left:0; top:0; transform-origin:0 0; background:#fff; user-select:none; -webkit-user-drag:none; max-width:none; }
#lb-bar { color:#eee; display:flex; flex-wrap:wrap; gap:8px; align-items:center; padding:10px 16px; font-size:14px; }
#lb-bar button, #lb-bar a { background:#333; color:#fff; border:0; border-radius:8px; padding:6px 12px; font-size:14px; cursor:pointer; text-decoration:none; }
#lb-cap { flex:1; min-width:160px; } #lb-zoom { min-width:52px; text-align:center; font-variant-numeric:tabular-nums; }
.card-actions { display:flex; gap:8px; flex-wrap:wrap; margin-top:6px; }
.card-actions button { background:var(--chip); color:var(--ink); border:1px solid var(--line); border-radius:8px; padding:4px 10px; font:inherit; font-size:13px; cursor:pointer; }
#discuss { position:fixed; top:0; right:0; bottom:0; width:min(560px, 100vw); background:var(--panel); border-left:1px solid var(--line);
  z-index:25; display:flex; flex-direction:column; box-shadow:-8px 0 30px rgba(0,0,0,.2); }
#discuss[hidden] { display:none; }
#d-head { padding:14px 16px; border-bottom:1px solid var(--line); display:flex; gap:10px; align-items:flex-start; }
#d-head h3 { margin:0; font-size:16px; flex:1; } #d-head .note { margin:2px 0 0; }
#d-head button { background:var(--chip); border:1px solid var(--line); color:var(--ink); border-radius:8px; padding:4px 10px; cursor:pointer; }
#d-body { flex:1; overflow:auto; padding:12px 16px; }
#d-body details { margin-bottom:10px; } #d-body pre { margin:0; padding:10px; overflow:auto; font-size:12px; max-height:320px; }
.msg { margin:10px 0; padding:10px 12px; border-radius:10px; white-space:pre-wrap; font-size:14px; line-height:1.5; }
.msg.user { background:var(--chip); } .msg.assistant { background:var(--bg); border:1px solid var(--line); }
.msg .who { font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; margin-bottom:4px; }
#d-foot { border-top:1px solid var(--line); padding:12px 16px; display:flex; flex-direction:column; gap:8px; }
#d-foot textarea { width:100%; min-height:72px; resize:vertical; background:var(--bg); color:var(--ink); border:1px solid var(--line); border-radius:10px; padding:8px 10px; font:inherit; }
#d-foot .row { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
#d-foot button, #d-foot select { background:var(--chip); color:var(--ink); border:1px solid var(--line); border-radius:8px; padding:6px 12px; font:inherit; font-size:14px; cursor:pointer; }
#d-foot button.primary { background:var(--accent); color:#fff; border-color:transparent; }
.prev { font-size:13px; margin:6px 0; } .prev a { cursor:pointer; }
footer { color:var(--muted); font-size:12px; padding:30px 0 40px; }
"""

JS = """
const figs = JSON.parse(document.getElementById('figdata').textContent);
const RUN = document.body.dataset.run;
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

// ── zoomable viewer: wheel / pinch / +− buttons to zoom, drag to pan, double-click to toggle, 0 = fit ──
const lb = $('#lightbox'), stage = $('#lb-stage'), img = $('#lb-img');
let cur = 0, scale = 1, fitScale = 1, tx = 0, ty = 0;
function apply() { img.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`; $('#lb-zoom').textContent = Math.round(scale / fitScale * 100) + '%'; }
function fit() { const r = stage.getBoundingClientRect(); if (!img.naturalWidth) return;
  fitScale = Math.min(r.width / img.naturalWidth, r.height / img.naturalHeight); scale = fitScale;
  tx = (r.width - img.naturalWidth * scale) / 2; ty = (r.height - img.naturalHeight * scale) / 2; apply(); }
function zoomAt(factor, cx, cy) { const r = stage.getBoundingClientRect();
  cx = cx ?? r.width / 2; cy = cy ?? r.height / 2;
  const ns = Math.min(Math.max(scale * factor, fitScale * 0.5), fitScale * 12);
  tx = cx - (cx - tx) * ns / scale; ty = cy - (cy - ty) * ns / scale; scale = ns; apply(); }
function show(i) { cur = (i + figs.length) % figs.length; const f = figs[cur];
  img.onload = fit; img.src = f.src; img.alt = f.label + ' ' + f.title;
  $('#lb-cap').textContent = `${f.label} — ${f.title}  (${cur + 1}/${figs.length})`;
  $('#lb-interactive').hidden = !f.interactive; if (f.interactive) $('#lb-interactive').href = f.interactive;
  lb.hidden = false; }
stage.addEventListener('wheel', e => { e.preventDefault(); const r = stage.getBoundingClientRect();
  zoomAt(Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top); }, {passive: false});
const ptrs = new Map(); let pinch0 = null;
stage.addEventListener('pointerdown', e => { stage.setPointerCapture(e.pointerId); ptrs.set(e.pointerId, {x: e.clientX, y: e.clientY}); stage.classList.add('dragging'); });
stage.addEventListener('pointermove', e => { if (!ptrs.has(e.pointerId)) return; const p = ptrs.get(e.pointerId);
  if (ptrs.size === 1) { tx += e.clientX - p.x; ty += e.clientY - p.y; apply(); }
  ptrs.set(e.pointerId, {x: e.clientX, y: e.clientY});
  if (ptrs.size === 2) { const [a, b] = [...ptrs.values()], d = Math.hypot(a.x - b.x, a.y - b.y), r = stage.getBoundingClientRect();
    if (pinch0) zoomAt(d / pinch0, (a.x + b.x) / 2 - r.left, (a.y + b.y) / 2 - r.top); pinch0 = d; } });
['pointerup', 'pointercancel'].forEach(t => stage.addEventListener(t, e => { ptrs.delete(e.pointerId); pinch0 = null; if (!ptrs.size) stage.classList.remove('dragging'); }));
stage.addEventListener('dblclick', e => { const r = stage.getBoundingClientRect();
  if (scale > fitScale * 1.05) fit(); else zoomAt(2.5, e.clientX - r.left, e.clientY - r.top); });
window.addEventListener('resize', () => { if (!lb.hidden) fit(); });
document.querySelectorAll('[data-fig]').forEach(b => b.addEventListener('click', () => show(+b.dataset.fig)));
$('#lb-prev').onclick = () => show(cur - 1); $('#lb-next').onclick = () => show(cur + 1);
$('#lb-in').onclick = () => zoomAt(1.4); $('#lb-out').onclick = () => zoomAt(1 / 1.4); $('#lb-fit').onclick = fit;
$('#lb-close').onclick = () => { lb.hidden = true; };
$('#lb-discuss').onclick = () => openDiscuss(figs[cur].stem);
document.addEventListener('keydown', e => { if (lb.hidden || !$('#discuss').hidden) return;
  if (e.key === 'ArrowRight') show(cur + 1); else if (e.key === 'ArrowLeft') show(cur - 1); else if (e.key === 'Escape') lb.hidden = true;
  else if (e.key === '+' || e.key === '=') zoomAt(1.4); else if (e.key === '-') zoomAt(1 / 1.4); else if (e.key === '0') fit(); });

// ── discuss a chart with Claude (needs the local app: python -m cardiac_imaging.app) ──
let APP = null, conv = null, dStem = null;
async function api(path, body) {
  const res = await fetch(path, body === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json', 'X-App-Token': APP.token}, body: JSON.stringify(body)});
  const data = await res.json().catch(() => ({error: `HTTP ${res.status}`}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`); return data;
}
const BACKEND = {'claude-code': 'Claude Code (reads the repo, read-only)', 'api': 'Claude via the Anthropic API', 'handoff': 'copy-paste mode (Claude Code not installed)'};
function thread() { $('#d-thread').innerHTML = (conv ? conv.messages : []).map(m =>
  `<div class="msg ${m.role}"><div class="who">${m.role === 'user' ? 'You' : 'Claude'}</div>${esc(m.text)}</div>`).join('');
  $('#d-outcome').value = conv ? conv.outcome : 'open'; $('#d-outcome-row').hidden = !conv; $('#d-body').scrollTop = 1e9; }
async function openDiscuss(stem) {
  dStem = stem; conv = null; const f = figs.find(x => x.stem === stem);
  $('#d-title').textContent = `${f.label} — ${f.title}`; $('#discuss').hidden = false; thread();
  if (!APP) { try { APP = await api('/api/session'); } catch (e) { APP = null; } }
  if (!APP) { $('#d-code').innerHTML = '<p class="note">Discussions need the local app. Start it with <code>python -m cardiac_imaging.app</code> and open this page from there.</p>';
    $('#d-send').disabled = true; return; }
  $('#d-send').disabled = false; $('#d-backend').textContent = 'Answering with: ' + (BACKEND[APP.chat_backend] || APP.chat_backend);
  try {
    const ctx = await api(`/api/context?run=${encodeURIComponent(RUN)}&stem=${encodeURIComponent(stem)}`);
    $('#d-code').innerHTML = `<details><summary>Code that generated this chart (snapshot ${esc((ctx.snapshot || '').slice(0, 7))})</summary>` +
      ctx.code.map(c => `<p class="note mono">${esc(c.ref)} — ${esc(c.path)}</p><pre class="mono">${esc(c.src)}</pre>`).join('') + '</details>';
    const prev = await api(`/api/conversations?run=${encodeURIComponent(RUN)}&stem=${encodeURIComponent(stem)}`);
    $('#d-prev').innerHTML = prev.length ? '<p class="note">Earlier discussions:</p>' + prev.map(p =>
      `<div class="prev"><a data-conv="${esc(p.id)}">${esc((p.messages[0] || {}).text || '(empty)').slice(0, 90)}</a> · ${esc(p.outcome.replace('_', ' '))}</div>`).join('') : '';
  } catch (e) { $('#d-code').innerHTML = `<p class="note">Couldn't load the chart's code: ${esc(e.message)}</p>`; }
}
$('#d-prev').addEventListener('click', async e => { const a = e.target.closest('[data-conv]'); if (!a) return;
  const list = await api(`/api/conversations?run=${encodeURIComponent(RUN)}&stem=${encodeURIComponent(dStem)}`);
  conv = list.find(c => c.id === a.dataset.conv); thread(); });
$('#d-send').onclick = async () => { const msg = $('#d-msg').value.trim(); if (!msg) return;
  $('#d-send').disabled = true; $('#d-send').textContent = 'Thinking…';
  (conv = conv || {messages: []}).messages.push({role: 'user', text: msg}); thread(); $('#d-msg').value = '';
  try { conv = await api('/api/chat', {run: RUN, stem: dStem, message: msg, conversation: conv.id}); }
  catch (e) { conv.messages.push({role: 'assistant', text: '⚠️ ' + e.message}); }
  thread(); $('#d-send').disabled = false; $('#d-send').textContent = 'Send'; };
$('#d-msg').addEventListener('keydown', e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) $('#d-send').click(); });
$('#d-outcome').onchange = async () => { if (!conv || !conv.id) return;
  conv = await api('/api/outcome', {conversation: conv.id, outcome: $('#d-outcome').value}); thread(); };
$('#d-new').onclick = () => { conv = null; thread(); };
$('#d-close').onclick = () => { $('#discuss').hidden = true; };
document.querySelectorAll('[data-discuss]').forEach(b => b.addEventListener('click', () => openDiscuss(b.dataset.discuss)));
"""


def _when(iso):
    """'Thu Oct 23, 2026, 10:44 PM' from an ISO timestamp (empty string if missing)."""
    from datetime import datetime
    try:
        d = datetime.fromisoformat(str(iso).replace('Z', '+00:00')).astimezone()
    except ValueError:
        return str(iso or '')
    return d.strftime('%a %b %-d, %Y, %-I:%M %p')


def esc(x):
    """HTML-escape any value."""
    return html.escape(str(x))


def fmt_num(v):
    """Compact number format for result tables."""
    if isinstance(v, float):
        if v != v:
            return '—'
        if abs(v) >= 1000:
            return f'{v:,.0f}'
        if v != 0 and abs(v) < 0.001:
            return f'{v:.1e}'
        return f'{v:.3f}'
    if isinstance(v, int):
        return f'{v:,}'
    return esc(v)


def table_html(csv_path):
    """Render a results CSV as an HTML table with compact number formatting."""
    df = pd.read_csv(csv_path, index_col=0)
    head = ''.join(f'<th>{esc(c)}</th>' for c in [df.index.name or ''] + list(df.columns))
    rows = ''.join('<tr>' + f'<td>{esc(i)}</td>' + ''.join(f'<td>{fmt_num(v)}</td>' for v in r) + '</tr>'
                   for i, r in zip(df.index, df.itertuples(index=False)))
    return f'<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>'


def figure_list(run_dir):
    """Catalog entries for this run (in catalog order), plus any uncatalogued PNGs under 'Other'."""
    pngs = {p.stem for p in (run_dir / 'figures').glob('*.png')}
    figs = [dict(f, present=f['stem'] in pngs) for f in FIGURES]
    known = {f['stem'] for f in FIGURES}
    figs += [dict(stem=s, label=s, section='Other', title=s, caption='', present=True) for s in sorted(pngs - known)]
    return figs


def make_thumbs(run_dir, figs, width=1400):
    """figures/thumbs/<stem>.png at `width` px for the grid; the full-resolution PNG opens in the viewer."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    d = run_dir / 'figures' / 'thumbs'
    d.mkdir(exist_ok=True)
    for f in figs:
        target = d / f'{f["stem"]}.png'
        if not target.exists():
            im = Image.open(run_dir / 'figures' / f'{f["stem"]}.png')
            im.thumbnail((width, width))
            im.save(target, optimize=True)


def headline_cards(m):
    """HTML stat cards for headline IRRs, steps completed and figure count."""
    cards = []
    for name, h in m.get('headline', {}).items():
        pstr = 'p&lt;0.001' if h['p'] < 0.001 else f"p={h['p']:.3f}"
        cards.append(f'<div class="stat"><div class="k">{esc(name)}</div><div class="v">{h["irr"]:.3f}</div>'
                     f'<div class="s">95% CI {h["lo"]:.3f}–{h["hi"]:.3f} · {pstr}</div></div>')
    n_ok = sum(1 for s in m.get('steps', []) if s['status'] == 'ok')
    cards.append(f'<div class="stat"><div class="k">Steps completed</div><div class="v">{n_ok}/{len(m.get("steps", []))}</div>'
                 f'<div class="s">{m.get("seconds", 0):.0f} s total</div></div>')
    cards.append(f'<div class="stat"><div class="k">Figures</div><div class="v">{len(m.get("figures", []))}</div>'
                 f'<div class="s">{m.get("bytes", 0) / 1e6:.0f} MB in this run folder</div></div>')
    return '<div class="cards">' + ''.join(cards) + '</div>'


def details_html(m, repo):
    """Run details panel: code snapshot + restore command, GitHub upload, data, versions."""
    c, d, pub = m.get('code', {}), m.get('data', {}), m.get('published')
    tag = esc(c.get('tag', ''))
    snap = esc((c.get('snapshot') or '')[:12])
    if c.get('exact'):
        how = 'exact working tree, incl. uncommitted changes' if c.get('dirty') else 'clean commit'
    else:
        how = f'<strong>approximate</strong> — {esc(c.get("note", "exact code not captured"))}'
    rows = [
        ('Started', esc(m.get('started', '').replace('T', ' '))),
        ('Finished', f"{esc(m.get('finished', '').replace('T', ' '))} ({m.get('seconds', 0):.0f} s)"),
        ('Pushed to GitHub', (f'{esc(pub["at"])} · <a href="{esc(pub["release_url"])}">release</a>') if pub else 'not yet'),
        ('Code snapshot', (f'<a href="{repo}/tree/{tag}" class="mono">{tag}</a> → <span class="mono">{snap}</span> ({how})'
                           if repo else f'<span class="mono">{tag}</span> ({how})')),
        ('Restore this code', f'<code class="mono">git fetch origin tag {tag} &amp;&amp; git checkout {tag}</code>'),
        ('Based on commit', f'<span class="mono">{esc(c.get("head", "")[:7])}</span> on {esc(c.get("branch", ""))} — '
                            f'{esc(c.get("subject", ""))} ({esc(c.get("date", ""))})'),
        ('Data', f'<span class="mono">{esc(m.get("database", ""))}</span> · fingerprint <span class="mono">{esc(d.get("fingerprint", ""))}</span>'
                 f' · {d.get("parquet_files", 0)} Parquet files ({d.get("parquet_bytes", 0) / 1e9:.2f} GB) · '
                 f'{d.get("claims_rows_total", 0):,} claims rows'),
        ('Rows per year', esc(', '.join(f'{y}: {n:,}' for y, n in d.get('claims_rows_by_year', {}).items())) or '—'),
        ('Versions', esc(', '.join(f'{k} {v}' for k, v in m.get('versions', {}).items()))),
    ]
    trs = ''.join(f'<tr><td>{k}</td><td style="text-align:left;white-space:normal">{v}</td></tr>' for k, v in rows)
    return (f'<section id="details"><h2>Run details</h2><details open><summary>Code, data and timing</summary>'
            f'<div class="tablewrap"><table><tbody>{trs}</tbody></table></div></details></section>')


def compare_note(m, runs_dir):
    """One line comparing headline numbers with the previous successful run."""
    prev = next((r for r in run_store.list_runs(runs_dir)
                 if r['run_id'] < m['run_id'] and r.get('status') == 'ok' and r.get('headline')), None)
    if not prev:
        return '<p class="note">No earlier successful run to compare with.</p>'
    link = f'<a href="../{esc(prev["run_id"])}/gallery.html" class="mono">{esc(prev["run_id"])}</a>'
    diffs = [k for k, h in m.get('headline', {}).items()
             if k not in prev['headline'] or any(round(h[x], 4) != round(prev['headline'][k][x], 4) for x in ('irr', 'lo', 'hi'))]
    if not diffs:
        return f'<p class="note">Headline IRRs identical to the previous run {link}.</p>'
    return f'<p class="note"><strong>Changed vs previous run</strong> {link}: {esc(", ".join(diffs))}.</p>'


def build(run_dir):
    """Write gallery.html and all_figures.pdf into run_dir from its manifest.json, figures/ and tables/."""
    run_dir = Path(run_dir)
    m = json.loads((run_dir / 'manifest.json').read_text())
    figs = figure_list(run_dir)
    present = [f for f in figs if f['present']]
    tiff_dir = run_dir / 'figures' / 'tiff'
    make_thumbs(run_dir, present)

    c = m.get('code', {})
    repo = f"https://github.com/{c['repo']}" if c.get('repo') else ''
    commit = (f'<a href="{repo}/commit/{esc(c["head"])}" class="mono">{esc(c["head"][:7])}</a>' if repo and c.get('head')
              else esc(c.get('head', '')[:7]))
    sections = [s for s in SECTIONS + ['Other'] if any(f['section'] == s for f in figs)]
    nav = ''.join(f'<a href="#{s.lower().replace(" ", "-")}">{esc(s)}</a>' for s in sections)
    nav += '<a href="#details">Run details</a><a href="#results">Results</a><a href="#steps">Steps</a><a href="#files">Files</a>'

    body = []
    if m.get('error'):
        e = m['error']
        body.append(f'<div class="error"><strong>Failed in step <span class="mono">{esc(e["step"])}</span>:</strong> '
                    f'{esc(e["type"])}: {esc(e["message"])}<br>Full traceback in <a href="console.log">console.log</a> '
                    'and <span class="mono">logs/last_error.md</span>.</div>')
    body.append(headline_cards(m) + compare_note(m, run_dir.parent))
    body.append(details_html(m, repo))

    for sec in sections:
        cards = []
        for f in (f for f in figs if f['section'] == sec):
            if f['present']:
                i = present.index(f)
                links = f'<a href="figures/{esc(f["stem"])}.png">PNG</a>'
                if (tiff_dir / f'{f["stem"]}.tiff').exists():
                    links += f'<a href="figures/tiff/{esc(f["stem"])}.tiff">TIFF</a>'
                if (run_dir / 'figures' / 'interactive' / f'{f["stem"]}.html').exists():
                    links += f'<a href="figures/interactive/{esc(f["stem"])}.html">Interactive</a>'
                media = (f'<button data-fig="{i}" aria-label="Open {esc(f["label"])} full screen">'
                         f'<img loading="lazy" src="figures/thumbs/{esc(f["stem"])}.png" alt="{esc(f["label"])}: {esc(f["title"])}"></button>')
                acts = (f'<div class="card-actions"><button data-fig="{i}">🔍 Zoom</button>'
                        f'<button data-discuss="{esc(f["stem"])}">💬 Discuss a hypothesis</button></div>')
            else:
                links, media, acts = '', '<div class="missing">Not produced in this run</div>', ''
            cards.append(f'<figure class="card">{media}<figcaption><span class="label">{esc(f["label"])}</span>'
                         f'<strong>{esc(f["title"])}</strong><p>{esc(f["caption"])}</p>{acts}<div class="links">{links}</div>'
                         '</figcaption></figure>')
        body.append(f'<section id="{sec.lower().replace(" ", "-")}"><h2>{esc(sec)}</h2><div class="grid">{"".join(cards)}</div></section>')

    tables = m.get('tables', {})
    blocks = []
    for name, title in SHOWN_TABLES:
        if name in tables and (run_dir / tables[name]).exists():
            blocks.append(f'<details {"open" if name != "state_summary_2023" else ""}><summary>{esc(title)}'
                          f'<a href="{esc(tables[name])}" download>CSV</a></summary>'
                          f'<div class="tablewrap">{table_html(run_dir / tables[name])}</div></details>')
    others = [n for n in tables if n not in dict(SHOWN_TABLES)]
    if others:
        blocks.append('<p class="note">More tables: ' + ' · '.join(
            f'<a href="{esc(tables[n])}" download>{esc(n)}.csv</a>' for n in others) + '</p>')
    body.append('<section id="results"><h2>Results</h2>' + (''.join(blocks) or '<p class="note">No tables saved.</p>') + '</section>')

    steps = ''.join(f'<tr><td class="mono">{esc(s["step"])}</td><td>{s["seconds"]:.1f}</td>'
                    f'<td><span class="badge {esc(s["status"])}">{esc(s["status"])}</span></td></tr>' for s in m.get('steps', []))
    body.append(f'<section id="steps"><h2>Steps</h2><details open><summary>Pipeline steps and timings</summary>'
                f'<div class="tablewrap"><table><thead><tr><th>Step</th><th>Seconds</th><th>Status</th></tr></thead>'
                f'<tbody>{steps}</tbody></table></div></details></section>')
    files = ['<a href="all_figures.pdf">all_figures.pdf</a> (every chart, one per page)',
             '<a href="console.log">console.log</a> (full printed output)',
             '<a href="manifest.json">manifest.json</a> (run metadata)',
             '<a href="figures/">figures/</a>', '<a href="tables/">tables/</a>']
    body.append('<section id="files"><h2>Files</h2><ul>' + ''.join(f'<li>{x}</li>' for x in files) + '</ul></section>')

    figdata = json.dumps([dict(src=f'figures/{f["stem"]}.png', label=f['label'], title=f['title'], stem=f['stem'],
                               interactive=(f'figures/interactive/{f["stem"]}.html'
                                            if (run_dir / 'figures' / 'interactive' / f'{f["stem"]}.html').exists() else None))
                          for f in present]).replace('</', '<\\/')
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Run {esc(m['run_id'])}</title><style>{CSS}</style></head>
<body data-run="{esc(m['run_id'])}">
<header class="top"><div class="wrap">
  <a href="../index.html">← All runs</a>
  <h1>Results from {esc(_when(m['started']))}</h1>
  <div class="meta"><span class="badge {esc(m['status'])}">{'completed' if m['status'] == 'ok' else esc(m['status'])}</span>
    <span>{m.get('seconds', 0):.0f} s</span><span>{('saved to GitHub ' + esc(_when(m['published']['at']))) if m.get('published') else 'not yet saved to GitHub'}</span></div>
  <nav>{nav}</nav>
</div></header>
<main class="wrap">{''.join(body)}</main>
<footer class="wrap">Click a chart to zoom: scroll or pinch to zoom, drag to move, double-click to toggle, 0 to fit, ← → to browse.</footer>
<div id="lightbox" hidden><div id="lb-stage"><img id="lb-img" alt="" draggable="false"></div>
  <div id="lb-bar"><button id="lb-prev" aria-label="Previous chart">←</button><span id="lb-cap"></span>
  <button id="lb-out" aria-label="Zoom out">−</button><span id="lb-zoom">100%</span><button id="lb-in" aria-label="Zoom in">+</button>
  <button id="lb-fit">Fit</button><a id="lb-interactive" hidden target="_blank">Interactive</a>
  <button id="lb-discuss">💬 Discuss</button><button id="lb-next" aria-label="Next chart">→</button><button id="lb-close">Close</button></div></div>
<aside id="discuss" hidden aria-label="Discuss this chart">
  <div id="d-head"><div style="flex:1"><h3 id="d-title"></h3><p class="note" id="d-backend"></p></div>
    <button id="d-new">New</button><button id="d-close">Close</button></div>
  <div id="d-body"><div id="d-code"></div><div id="d-prev"></div><div id="d-thread"></div></div>
  <div id="d-foot"><textarea id="d-msg" placeholder="Describe a hypothesis about this chart — e.g. “The CTA growth is concentrated in states that expanded office-based imaging.” (⌘↵ to send)"></textarea>
    <div class="row"><button class="primary" id="d-send">Send</button>
      <span id="d-outcome-row" hidden>Outcome: <select id="d-outcome"><option value="open">open</option><option value="supported">supported</option>
      <option value="not_supported">not supported</option><option value="inconclusive">inconclusive</option></select></span></div></div>
</aside>
<script type="application/json" id="figdata">{figdata}</script>
<script>{JS}</script>
</body></html>
"""
    (run_dir / 'gallery.html').write_text(page, encoding='utf-8')
    build_pdf(run_dir, m, present)


def build_pdf(run_dir, m, figs, max_px=2400):
    """all_figures.pdf: a cover page, then one landscape page per chart with its label and title."""
    import numpy as np
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.figure import Figure
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = None
    with PdfPages(run_dir / 'all_figures.pdf') as pdf:
        cover = Figure(figsize=(11, 8.5))
        lines = [f"Run {m['run_id']}", f"Status: {m['status']}   ·   {m['started'].replace('T', ' ')}   ·   commit {m.get('code', {}).get('head', '')[:7]}",
                 f"{len(figs)} figures"] + [f"{k}: IRR {h['irr']:.3f} ({h['lo']:.3f}–{h['hi']:.3f})" for k, h in m.get('headline', {}).items()]
        cover.text(0.08, 0.85, 'Cardiac imaging utilization in Medicare FFS — figures', fontsize=20, weight='bold')
        for i, line in enumerate(lines):
            cover.text(0.08, 0.75 - i * 0.05, line, fontsize=13)
        pdf.savefig(cover)
        for f in figs:
            im = Image.open(run_dir / 'figures' / f'{f["stem"]}.png').convert('RGB')
            im.thumbnail((max_px, max_px))
            page = Figure(figsize=(11, 8.5))
            page.text(0.04, 0.95, f"{f['label']} — {f['title']}", fontsize=14, weight='bold', va='top')
            page.text(0.04, 0.915, f['caption'], fontsize=9, color='#555555', va='top', wrap=True)
            ax = page.add_axes([0.03, 0.03, 0.94, 0.86])
            ax.imshow(np.asarray(im))
            ax.axis('off')
            pdf.savefig(page, dpi=220)
