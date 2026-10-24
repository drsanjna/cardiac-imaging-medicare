"""RUNS_DIR/index.html: every run — local and on GitHub — with timestamps, code snapshot, data, headline IRRs and links."""
import json
from pathlib import Path

from .. import config, gitinfo
from .gallery import CSS, esc
from .publish import MARKER, summary
from .run_store import list_runs

INDEX_CSS = """
.toolbar { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin:14px 0; }
.toolbar input, .toolbar select { background:var(--panel); color:var(--ink); border:1px solid var(--line); border-radius:8px; padding:6px 10px; font:inherit; }
.toolbar input { flex:1; min-width:180px; }
.run { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:14px 16px; margin-bottom:12px; box-shadow:var(--shadow); }
.run h3 { margin:0 0 4px; font-size:16px; display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
.kv { display:grid; grid-template-columns:repeat(auto-fill, minmax(min(100%, 260px), 1fr)); gap:6px 18px; margin:10px 0; font-size:13px; }
.kv .k { display:block; color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.04em; }
.irrs { display:flex; flex-wrap:wrap; gap:8px; margin:6px 0 10px; }
.irrs .chip b { font-variant-numeric:tabular-nums; }
.src { font-size:11px; border:1px solid var(--line); border-radius:999px; padding:0 7px; color:var(--muted); }
.restore { display:flex; gap:6px; align-items:center; flex-wrap:wrap; font-size:13px; }
.restore code { background:var(--chip); padding:3px 8px; border-radius:6px; overflow-wrap:anywhere; }
.restore button { background:var(--chip); color:var(--ink); border:1px solid var(--line); border-radius:6px; padding:2px 8px; cursor:pointer; font:inherit; font-size:12px; }
.warn { color:var(--bad); }
"""

JS = """
const LOCAL = JSON.parse(document.getElementById('local-runs').textContent);
const REPO = document.body.dataset.repo, MARKER = document.body.dataset.marker;
const runs = new Map(LOCAL.map(r => [r.run_id, {...r, local: true}]));
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = iso => iso ? new Date(iso).toLocaleString(undefined, {dateStyle:'medium', timeStyle:'medium'}) : '—';
const gh = REPO ? `https://github.com/${REPO}` : '';

function decode(body) {
  const i = (body || '').indexOf(MARKER); if (i < 0) return null;
  const b64 = body.slice(i + MARKER.length).split('-->')[0].trim();
  return JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(b64), c => c.charCodeAt(0))));
}

function card(r, prev) {
  const c = r.code || {}, d = r.data || {}, p = r.published;
  const tag = esc(c.tag), local = r.local;
  const links = [];
  if (local) links.push(`<a href="${esc(r.run_id)}/gallery.html">Gallery</a>`, `<a href="${esc(r.run_id)}/all_figures.pdf">PDF</a>`, `<a href="${esc(r.run_id)}/console.log">Log</a>`);
  if (p) {
    links.push(`<a href="${esc(p.release_url)}">GitHub release</a>`);
    const a = p.assets || {}, zip = a[`run_${r.run_id}.zip`];
    if (!local && zip) links.push(`<a href="${esc(zip)}">Download outputs (zip)</a>`);
    if (!local && a['all_figures.pdf']) links.push(`<a href="${esc(a['all_figures.pdf'])}">PDF</a>`);
  }
  if (gh && c.tag && p) links.push(`<a href="${gh}/tree/${tag}">Code at this run</a>`);
  if (gh && c.tag && p && prev && prev.code && prev.code.tag && prev.published) links.push(`<a href="${gh}/compare/${esc(prev.code.tag)}...${tag}">Code diff vs previous run</a>`);
  const how = c.exact ? (c.dirty ? 'exact (incl. uncommitted changes)' : 'exact (clean commit)') : `<span class="warn">approximate</span>`;
  const irrs = Object.entries(r.headline || {}).map(([k, h]) =>
    `<span class="chip">${esc(k.replace('Adjusted IRR — ', ''))}: <b>${h.irr.toFixed(3)}</b> (${h.lo.toFixed(3)}–${h.hi.toFixed(3)})</span>`).join('');
  const versions = Object.entries(r.versions || {}).map(([k, v]) => `${k} ${v}`).join(', ');
  return `<article class="run" data-text="${esc([r.run_id, r.label, r.status, c.branch, c.subject, c.head].join(' ').toLowerCase())}" data-status="${esc(r.status)}">
    <h3><span class="badge ${esc(r.status)}">${esc(r.status)}</span><span class="mono">${esc(r.run_id)}</span>
      ${r.label ? `<span class="chip">${esc(r.label)}</span>` : ''}
      ${local ? '<span class="src">local</span>' : ''}${p ? '<span class="src">on GitHub</span>' : '<span class="src warn">not pushed</span>'}</h3>
    ${r.error ? `<div class="note warn">Failed in <span class="mono">${esc(r.error.step)}</span>: ${esc(r.error.type)}: ${esc(r.error.message)}</div>` : ''}
    <div class="irrs">${irrs}</div>
    <div class="kv">
      <div><span class="k">Started</span>${fmt(r.started)}</div>
      <div><span class="k">Finished · duration</span>${fmt(r.finished)} · ${Math.round(r.seconds || 0)} s</div>
      <div><span class="k">Pushed to GitHub</span>${p ? fmt(p.at) : '<span class="warn">not yet</span>'}</div>
      <div><span class="k">Steps · figures · size</span>${r.steps_ok}/${r.steps_total} · ${r.figures} · ${((r.bytes || 0) / 1e6).toFixed(0)} MB${r.save_tiff ? '' : ' (no TIFF)'}</div>
      <div><span class="k">Code snapshot</span><span class="mono">${tag}</span><br>${esc((c.snapshot || '').slice(0, 12))} · ${how}</div>
      <div><span class="k">Based on commit</span>${gh && c.head ? `<a class="mono" href="${gh}/commit/${esc(c.head)}">${esc((c.head || '').slice(0, 7))}</a>` : esc((c.head || '').slice(0, 7))}
        on ${esc(c.branch)} — ${esc(c.subject)}<br>${fmt(c.date)}</div>
      <div><span class="k">Data</span>fingerprint <span class="mono">${esc(d.fingerprint)}</span> · ${(d.claims_rows_total || 0).toLocaleString()} rows<br>${d.parquet_files || 0} Parquet files, ${((d.parquet_bytes || 0) / 1e9).toFixed(2)} GB</div>
      <div><span class="k">Versions</span>${esc(versions)}</div>
    </div>
    ${c.exact ? '' : `<div class="note warn">${esc(c.note || 'Exact code for this run was not captured.')}</div>`}
    <div class="restore"><span class="note" style="margin:0">Restore code:</span><code>git fetch origin tag ${tag} &amp;&amp; git checkout ${tag}</code>
      <button data-copy="git fetch origin tag ${tag} && git checkout ${tag}">Copy</button>
      ${!local && p ? `<code>python scripts/runs.py fetch ${esc(r.run_id)}</code>` : ''}</div>
    <div class="links note">${links.join(' · ')}</div>
  </article>`;
}

function render() {
  const list = [...runs.values()].sort((a, b) => (b.started || '').localeCompare(a.started || ''));
  const q = $('#q').value.trim().toLowerCase(), st = $('#status').value;
  const html = list.map((r, i) => card(r, list[i + 1])).join('');
  $('#runs').innerHTML = html || '<p class="note">No runs yet.</p>';
  document.querySelectorAll('.run').forEach(el => {
    el.hidden = (q && !el.dataset.text.includes(q)) || (st && el.dataset.status !== st);
  });
  const nLocal = list.filter(r => r.local).length, nGh = list.filter(r => r.published).length;
  $('#counts').textContent = `${list.length} runs · ${nLocal} local · ${nGh} on GitHub`;
}

async function loadGitHub() {
  if (!REPO) { $('#ghstatus').textContent = 'No GitHub remote configured — local runs only.'; return; }
  $('#ghstatus').textContent = 'Loading runs from GitHub…';
  try {
    let page = 1, n = 0;
    while (page <= 10) {
      const res = await fetch(`https://api.github.com/repos/${REPO}/releases?per_page=100&page=${page}`, {headers: {Accept: 'application/vnd.github+json'}});
      if (!res.ok) throw new Error(`GitHub API ${res.status}`);
      const rels = await res.json();
      for (const rel of rels) {
        const s = decode(rel.body); if (!s) continue;
        s.published = {at: rel.published_at, release_url: rel.html_url, tag: rel.tag_name,
                       assets: Object.fromEntries((rel.assets || []).map(a => [a.name, a.browser_download_url]))};
        const cur = runs.get(s.run_id);
        runs.set(s.run_id, cur ? {...cur, published: s.published} : {...s, local: false});
        n++;
      }
      if (rels.length < 100) break; page++;
    }
    $('#ghstatus').textContent = `Loaded ${n} runs from github.com/${REPO} at ${new Date().toLocaleTimeString()}.`;
  } catch (e) {
    $('#ghstatus').innerHTML = `<span class="warn">Couldn't reach GitHub (${esc(e.message)}) — showing local runs only.</span>`;
  }
  render();
}

document.addEventListener('click', e => {
  const b = e.target.closest('[data-copy]'); if (!b) return;
  navigator.clipboard.writeText(b.dataset.copy).then(() => { b.textContent = 'Copied'; setTimeout(() => b.textContent = 'Copy', 1200); });
});
$('#q').addEventListener('input', render); $('#status').addEventListener('change', render);
$('#refresh').addEventListener('click', loadGitHub);
render(); loadGitHub();
"""


def build(runs_dir=None):
    """Rewrite index.html in runs_dir: local run summaries embedded, GitHub releases merged in by the page itself."""
    runs_dir = Path(runs_dir or config.RUNS_DIR)
    local = [summary(m) for m in list_runs(runs_dir)]
    repo = gitinfo.repo_slug() or ''
    data = json.dumps(local, default=str).replace('</', '<\\/')
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cardiac imaging runs</title><style>{CSS}{INDEX_CSS}</style></head>
<body data-repo="{esc(repo)}" data-marker="{esc(MARKER)}">
<header class="top"><div class="wrap"><h1>Cardiac imaging — all runs</h1>
  <div class="meta"><span id="counts"></span><span id="ghstatus"></span></div></div></header>
<main class="wrap">
  <div class="toolbar"><input id="q" type="search" placeholder="Filter by run, label, branch, commit…" aria-label="Filter runs">
    <select id="status" aria-label="Status"><option value="">All statuses</option><option value="ok">ok</option><option value="failed">failed</option></select>
    <button id="refresh" class="chip" style="border:0;cursor:pointer">Refresh from GitHub</button></div>
  <div id="runs"></div>
  <p class="note">Local runs live in <span class="mono">{esc(runs_dir)}</span>. Runs on GitHub are loaded live from the repo's releases
  (one release per run, on the run's code-snapshot tag). Times are shown in your local time zone.</p>
</main>
<footer class="wrap">Generated by cardiac_imaging.reporting.index.</footer>
<script type="application/json" id="local-runs">{data}</script>
<script>{JS}</script>
</body></html>
"""
    (runs_dir / 'index.html').write_text(page, encoding='utf-8')
