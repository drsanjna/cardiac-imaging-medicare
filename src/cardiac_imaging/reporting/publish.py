"""Upload a run to GitHub as a Release on its code-snapshot tag (outputs zipped as assets), and download runs back."""
import base64
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from .. import config, gitinfo
from .run_store import read_manifest, write_manifest

MARKER = 'cardiac-run-summary:'   # release notes carry <!-- cardiac-run-summary:<base64 JSON> --> for index.html


def _gh(*args, capture=False):
    """Run a `gh` CLI command against this repo (optionally returning its output)."""
    gh = shutil.which('gh')
    if not gh:
        raise RuntimeError("GitHub CLI `gh` not found (brew install gh && gh auth login).")
    cmd = [gh, *args, '--repo', gitinfo.repo_slug()]
    if capture:
        return subprocess.check_output(cmd, text=True, cwd=config.REPO_ROOT)
    subprocess.run(cmd, check=True, cwd=config.REPO_ROOT, stdout=subprocess.DEVNULL)


def summary(m):
    """The subset of a manifest shown in index.html (also embedded in the release notes)."""
    keep = ('run_id', 'label', 'status', 'started', 'finished', 'seconds', 'code', 'database', 'data', 'versions',
            'headline', 'error', 'save_tiff', 'bytes', 'published', 'summary', 'comparison', 'findings', 'review',
            'publish_error')
    s = {k: m.get(k) for k in keep}
    s['figures'] = len(m.get('figures', []))
    s['steps_ok'] = sum(1 for x in m.get('steps', []) if x['status'] == 'ok')
    s['steps_total'] = len(m.get('steps', []))
    return s


def release_notes(m):
    """Markdown release notes for a run: summary table, headline IRRs, restore command, embedded run record."""
    c, d = m['code'], m.get('data', {})
    repo = f"https://github.com/{c.get('repo')}"
    rows = [
        ('Status', f"**{m['status']}**" + (f" — failed in `{m['error']['step']}`: {m['error']['type']}" if m.get('error') else '')),
        ('Started → finished', f"{m['started']} → {m.get('finished', '')} ({m.get('seconds', 0):.0f} s)"),
        ('Code snapshot', f"[`{c['tag']}`]({repo}/tree/{c['tag']}) → `{(c.get('snapshot') or '')[:12]}`"
                          + (' (exact working tree, incl. uncommitted changes)' if c.get('dirty') and c.get('exact') else '')
                          + ('' if c.get('exact') else ' — **approximate** (see note)')),
        ('Based on commit', f"[`{c['head'][:7]}`]({repo}/commit/{c['head']}) on `{c.get('branch')}` — {c.get('subject', '')} ({c.get('date', '')})"),
        ('Data', f"`{m.get('database')}` · Parquet fingerprint `{d.get('fingerprint')}` · "
                 f"{d.get('claims_rows_total', 0):,} claims rows"),
        ('Versions', ', '.join(f'{k} {v}' for k, v in m.get('versions', {}).items())),
        ('Figures', f"{len(m.get('figures', []))}" + ('' if m.get('save_tiff') else ' (no TIFFs)')),
        ('Your label', ((m.get('review') or {}).get('label') or 'none').replace('_', ' ')
                       + (f" — {m['review']['note']}" if (m.get('review') or {}).get('note') else '')),
    ]
    cmp_ = m.get('comparison') or {}
    lines = [f"Pipeline run **{m['run_id']}**", '', m.get('summary', ''), '']
    if cmp_.get('changes'):
        lines += ['**What changed** (vs ' + (f"`{cmp_['previous']}`" if cmp_.get('previous') else 'nothing') + ')', '']
        lines += [f'- {x}' for x in cmp_['changes']] + ['', '**Impact**', ''] + [f'- {x}' for x in cmp_.get('impact', [])] + ['']
    lines += ['<details><summary>Technical details</summary>', '', '| | |', '|---|---|'] + [f'| {k} | {v} |' for k, v in rows]
    if m.get('headline'):
        lines += ['', '| Headline | IRR | 95% CI |', '|---|---|---|']
        lines += [f"| {k} | {h['irr']:.3f} | {h['lo']:.3f}–{h['hi']:.3f} |" for k, h in m['headline'].items()]
    if not c.get('exact'):
        lines += ['', f"> **Note:** {c.get('note', 'The exact code for this run was not captured.')}"]
    lines += ['', '</details>', '', '**Restore this code:**', '```bash', f"git fetch origin tag {c['tag']} && git checkout {c['tag']}", '```',
              '**Open the outputs:** download `run_*.zip`, unzip into `~/Downloads/cms_runs/`, open `gallery.html` '
              f"(or `python scripts/runs.py fetch {m['run_id']}`).",
              '', f"<!-- {MARKER}{base64.b64encode(json.dumps(summary(m), default=str).encode()).decode()} -->"]
    return '\n'.join(lines)


def _zip(run_dir, out, include_tiff):
    """Zip run_dir as <run_id>/... ; TIFFs go only in the TIFF zip."""
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in sorted(run_dir.rglob('*')):
            rel = p.relative_to(run_dir)
            is_tiff = rel.parts[:2] == ('figures', 'tiff')
            if p.is_file() and is_tiff == include_tiff:
                z.write(p, Path(run_dir.name) / rel)


def _push_tag(tag):
    """Push one tag (and the snapshot commit it points to) to GitHub."""
    subprocess.run(['git', 'push', '-q', 'origin', f'refs/tags/{tag}'], check=True, cwd=config.REPO_ROOT)


def expected_assets(run_dir, m):
    """Names of the files a complete release for this run must have."""
    names = [f"run_{m['run_id']}.zip", 'manifest.json']
    if (Path(run_dir) / 'all_figures.pdf').exists():
        names.append('all_figures.pdf')
    if any((Path(run_dir) / 'figures' / 'tiff').glob('*.tiff')):
        names.append(f"tiff_{m['run_id']}.zip")
    return names


def _build_assets(run_dir, m, tmp):
    """Write the release files (outputs zip, TIFF zip, PDF, manifest) into tmp; returns their paths."""
    assets = [tmp / f"run_{m['run_id']}.zip"]
    _zip(run_dir, assets[0], include_tiff=False)
    if any((run_dir / 'figures' / 'tiff').glob('*.tiff')):
        assets.append(tmp / f"tiff_{m['run_id']}.zip")
        _zip(run_dir, assets[-1], include_tiff=True)
    for name in ('all_figures.pdf', 'manifest.json'):
        if (run_dir / name).exists():
            shutil.copy(run_dir / name, tmp / name)
            assets.append(tmp / name)
    return assets


def release_info(tag):
    """The GitHub release for `tag` (url, publishedAt, isDraft, body, assets with name/size/url), or None if there isn't one."""
    try:
        return json.loads(_gh('release', 'view', tag, '--json', 'url,publishedAt,isDraft,body,assets', capture=True))
    except subprocess.CalledProcessError:
        return None


def publish_run(run_dir, force=False):
    """Push the run's tag and make its GitHub Release complete; records `published` in the manifest.

    Creates the release if it's missing; if it exists (e.g. an earlier upload was cut off) uploads only the missing or
    empty files and refreshes the notes. `force` re-checks a run that is already marked published.
    """
    from . import gallery
    run_dir = Path(run_dir)
    m = read_manifest(run_dir)
    if m.get('published') and not force:
        print(f"  Already on GitHub: {m['published']['release_url']}")
        return m['published']
    c = m['code']
    if not c.get('snapshot'):
        raise RuntimeError(f"Run {m['run_id']} has no code snapshot; backfill it first (scripts/runs.py publish --assume-commit).")
    gitinfo.ensure_tag(c['tag'], c['snapshot'], f"Code used for run {m['run_id']}")
    _push_tag(c['tag'])

    existing = release_info(c['tag'])
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        notes = tmp / 'notes.md'
        notes.write_text(release_notes(m))
        if existing is None:
            assets = _build_assets(run_dir, m, tmp)
            title = (f"Run {m['started'][:16].replace('T', ' ')} · {m['status']} · {c['head'][:7]}"
                     + (f" · {m['label']}" if m.get('label') else ''))
            print(f"  Uploading run to GitHub release {c['tag']} ({sum(a.stat().st_size for a in assets) / 1e6:.0f} MB) ...")
            _gh('release', 'create', c['tag'], '--verify-tag', '--latest=false', '--title', title,
                '--notes-file', str(notes), *map(str, assets))
        else:
            have = {a['name']: a.get('size', 0) for a in existing.get('assets', [])}
            missing = [n for n in expected_assets(run_dir, m) if have.get(n, 0) <= 0]
            if missing:
                assets = [a for a in _build_assets(run_dir, m, tmp) if a.name in missing]
                print(f"  Repairing release {c['tag']}: uploading {', '.join(a.name for a in assets)}")
                _gh('release', 'upload', c['tag'], '--clobber', *map(str, assets))
            _gh('release', 'edit', c['tag'], '--notes-file', str(notes))

    info = release_info(c['tag'])
    if info is None:
        raise RuntimeError(f"GitHub has no release for {c['tag']} after uploading.")
    m['published'] = dict(at=info['publishedAt'], release_url=info['url'], tag=c['tag'],
                          assets={a['name']: a['url'] for a in info['assets']})
    write_manifest(run_dir, m)
    gallery.build(run_dir)
    print(f"  Published: {info['url']} at {info['publishedAt']}")
    return m['published']


def record_from_body(body):
    """The run record embedded in release notes (decoded), or None."""
    if not body or MARKER not in body:
        return None
    try:
        return json.loads(base64.b64decode(body.split(MARKER, 1)[1].split('-->', 1)[0].strip()))
    except (ValueError, TypeError):
        return None


def update_release_notes(run_dir):
    """Rewrite an existing GitHub release's notes from the run's current manifest (e.g. after refreshing summaries)."""
    m = read_manifest(run_dir)
    if not m.get('published'):
        return False
    with tempfile.TemporaryDirectory() as tmp:
        notes = Path(tmp) / 'notes.md'
        notes.write_text(release_notes(m))
        _gh('release', 'edit', m['code']['tag'], '--notes-file', str(notes))
    return True


def remote_runs():
    """Run summaries decoded from the GitHub releases' notes (newest first), each with its release URL and time."""
    out = []
    for r in _gh_api_releases():
        s = record_from_body(r.get('body'))
        if s is None:
            continue
        s['published'] = dict(at=r['published_at'], release_url=r['html_url'], tag=r['tag_name'],
                              assets={a['name']: a['browser_download_url'] for a in r.get('assets', [])})
        out.append(s)
    return out


def _gh_api_releases():
    """All of the repo's releases from the GitHub API (all pages)."""
    gh = shutil.which('gh')
    if not gh:
        raise RuntimeError("GitHub CLI `gh` not found.")
    out = subprocess.check_output([gh, 'api', '--paginate', '--slurp', f'repos/{gitinfo.repo_slug()}/releases?per_page=100'],
                                  text=True, cwd=config.REPO_ROOT)
    return [r for page in json.loads(out) for r in page]


def fetch_run(run_id, runs_dir=None):
    """Download a published run's outputs (run_*.zip) from GitHub and unpack them into runs_dir."""
    runs_dir = Path(runs_dir or config.RUNS_DIR)
    if (runs_dir / run_id / 'manifest.json').exists():
        print(f"  {run_id} is already local.")
        return runs_dir / run_id
    with tempfile.TemporaryDirectory() as tmp:
        _gh('release', 'download', f'run-{run_id}', '--pattern', f'run_{run_id}.zip', '--dir', tmp)
        with zipfile.ZipFile(Path(tmp) / f'run_{run_id}.zip') as z:
            bad = [n for n in z.namelist() if not n.startswith(f'{run_id}/') or '..' in Path(n).parts]
            if bad:
                raise RuntimeError(f"Unexpected paths in archive: {bad[:3]}")
            z.extractall(runs_dir)
    print(f"  Downloaded {run_id} → {runs_dir / run_id}")
    return runs_dir / run_id
