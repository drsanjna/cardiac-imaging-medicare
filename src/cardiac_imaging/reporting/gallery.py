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
#lightbox { position:fixed; inset:0; background:rgba(10,10,10,.92); z-index:20; display:flex; flex-direction:column; }
#lightbox[hidden] { display:none; }
#lb-stage { flex:1; overflow:auto; display:flex; align-items:center; justify-content:center; }
#lb-img { max-width:96vw; max-height:84vh; background:#fff; cursor:zoom-in; }
#lb-stage.zoom { align-items:flex-start; justify-content:flex-start; } #lb-stage.zoom #lb-img { max-width:none; max-height:none; cursor:zoom-out; }
#lb-bar { color:#eee; display:flex; gap:10px; align-items:center; padding:10px 16px; font-size:14px; }
#lb-bar button { background:#333; color:#fff; border:0; border-radius:8px; padding:6px 12px; font-size:14px; cursor:pointer; }
#lb-cap { flex:1; }
footer { color:var(--muted); font-size:12px; padding:30px 0 40px; }
"""

JS = """
const figs = JSON.parse(document.getElementById('figdata').textContent);
const lb = document.getElementById('lightbox'), img = document.getElementById('lb-img'),
      cap = document.getElementById('lb-cap'), stage = document.getElementById('lb-stage');
let cur = 0;
function show(i) { cur = (i + figs.length) % figs.length; const f = figs[cur];
  img.src = f.src; img.alt = f.label + ' ' + f.title; cap.textContent = `${f.label} — ${f.title}  (${cur + 1}/${figs.length})`;
  stage.classList.remove('zoom'); lb.hidden = false; }
document.querySelectorAll('[data-fig]').forEach(b => b.addEventListener('click', () => show(+b.dataset.fig)));
document.getElementById('lb-prev').onclick = () => show(cur - 1);
document.getElementById('lb-next').onclick = () => show(cur + 1);
document.getElementById('lb-close').onclick = () => { lb.hidden = true; };
img.onclick = () => stage.classList.toggle('zoom');
document.addEventListener('keydown', e => { if (lb.hidden) return;
  if (e.key === 'ArrowRight') show(cur + 1); else if (e.key === 'ArrowLeft') show(cur - 1); else if (e.key === 'Escape') lb.hidden = true; });
"""


def esc(x):
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

    commit = esc(m.get('commit_short', ''))
    remote = (m.get('remote') or '').removesuffix('.git')
    if 'github.com' in remote and m.get('commit'):
        remote = remote.replace('git@github.com:', 'https://github.com/')
        commit = f'<a href="{esc(remote)}/commit/{esc(m["commit"])}" class="mono">{commit}</a>'
    sections = [s for s in SECTIONS + ['Other'] if any(f['section'] == s for f in figs)]
    nav = ''.join(f'<a href="#{s.lower().replace(" ", "-")}">{esc(s)}</a>' for s in sections)
    nav += '<a href="#results">Results</a><a href="#steps">Steps</a><a href="#files">Files</a>'

    body = []
    if m.get('error'):
        e = m['error']
        body.append(f'<div class="error"><strong>Failed in step <span class="mono">{esc(e["step"])}</span>:</strong> '
                    f'{esc(e["type"])}: {esc(e["message"])}<br>Full traceback in <a href="console.log">console.log</a> '
                    'and <span class="mono">logs/last_error.md</span>.</div>')
    body.append(headline_cards(m) + compare_note(m, run_dir.parent))

    for sec in sections:
        cards = []
        for f in (f for f in figs if f['section'] == sec):
            if f['present']:
                i = present.index(f)
                links = f'<a href="figures/{esc(f["stem"])}.png">PNG</a>'
                if (tiff_dir / f'{f["stem"]}.tiff').exists():
                    links += f'<a href="figures/tiff/{esc(f["stem"])}.tiff">TIFF</a>'
                media = (f'<button data-fig="{i}" aria-label="Open {esc(f["label"])} full screen">'
                         f'<img loading="lazy" src="figures/thumbs/{esc(f["stem"])}.png" alt="{esc(f["label"])}: {esc(f["title"])}"></button>')
            else:
                links, media = '', '<div class="missing">Not produced in this run</div>'
            cards.append(f'<figure class="card">{media}<figcaption><span class="label">{esc(f["label"])}</span>'
                         f'<strong>{esc(f["title"])}</strong><p>{esc(f["caption"])}</p><div class="links">{links}</div>'
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

    figdata = json.dumps([dict(src=f'figures/{f["stem"]}.png', label=f['label'], title=f['title']) for f in present])
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Run {esc(m['run_id'])}</title><style>{CSS}</style></head>
<body>
<header class="top"><div class="wrap">
  <a href="../index.html">← All runs</a>
  <h1>Cardiac imaging run <span class="mono">{esc(m['run_id'])}</span></h1>
  <div class="meta"><span class="badge {esc(m['status'])}">{esc(m['status'])}</span>
    <span>started {esc(m['started'].replace('T', ' '))}</span><span>{m.get('seconds', 0):.0f} s</span>
    <span>commit {commit}{' (uncommitted changes)' if m.get('dirty') else ''}</span><span>branch {esc(m.get('branch', ''))}</span>
    <span class="mono">{esc(m.get('database', ''))}</span></div>
  <nav>{nav}</nav>
</div></header>
<main class="wrap">{''.join(body)}</main>
<footer class="wrap">Generated by cardiac_imaging.reporting.gallery · click a chart for full screen (← → to browse, click image to zoom, Esc to close)</footer>
<div id="lightbox" hidden><div id="lb-stage"><img id="lb-img" alt=""></div>
  <div id="lb-bar"><button id="lb-prev" aria-label="Previous">←</button><span id="lb-cap"></span>
  <button id="lb-next" aria-label="Next">→</button><button id="lb-close">Close</button></div></div>
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
        lines = [f"Run {m['run_id']}", f"Status: {m['status']}   ·   {m['started'].replace('T', ' ')}   ·   commit {m.get('commit_short', '')}",
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
