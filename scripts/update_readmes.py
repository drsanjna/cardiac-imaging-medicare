"""Regenerate every README.md (root + one per code directory) from the code itself: docstrings, functions, imports.

Each README gets a Mermaid flowchart of how its directory connects to the rest of the repo.
Text between <!-- BEGIN MANUAL --> and <!-- END MANUAL --> is preserved across runs.
Standard library only, so it runs anywhere (git hook, GitHub Actions) without installs.

    python scripts/update_readmes.py           # rewrite READMEs
    python scripts/update_readmes.py --check   # exit 1 if any README is stale (CI)
"""
import argparse
import ast
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = 'cardiac_imaging'
PKG_DIR = ROOT / 'src' / PKG
EXTRA_DIRS = ['scripts', 'notebooks', '.github/workflows', '.githooks', 'legacy']
DIR_PURPOSE = {  # directories without an __init__.py docstring
    'scripts': 'Command-line tools: CSV → Parquet conversion, database build, README generation, git hook install.',
    'notebooks': 'Thin Jupyter driver: imports from src/, runs the pipeline. Run headless with papermill.',
    '.github/workflows': 'GitHub Actions: keep READMEs in sync on push; Claude fixes code for @claude / notebook-error issues.',
    '.githooks': 'Local git hooks: regenerate READMEs before each commit.',
    'legacy': 'The original single-file analysis script, kept unchanged for reference. Not imported by anything.',
}
ROOT_HIDDEN = {'config.py', 'style.py', 'audit.py'}   # feed every layer; drawn as one box on the root chart
SUBPACKAGES = ('analysis', 'db', 'figures', 'loaders', 'reporting')
MANUAL_RE = re.compile(r'<!-- BEGIN MANUAL -->.*?<!-- END MANUAL -->', re.S)
DEFAULT_MANUAL = '<!-- BEGIN MANUAL -->\n<!-- END MANUAL -->'


# ── code inspection ──────────────────────────────────────────────────────────
def first_line(text):
    return (text or '').strip().split('\n')[0].strip()


def module_name(path):
    """Dotted name for a .py file: cardiac_imaging.loaders.claims, scripts.update_readmes."""
    base = PKG_DIR.parent if PKG_DIR in path.parents else ROOT
    return '.'.join(path.relative_to(base).with_suffix('').parts)


def describe_py(path):
    tree = ast.parse(path.read_text())
    funcs = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and not node.name.startswith('_'):
            args = [a.arg for a in node.args.args] if isinstance(node, ast.FunctionDef) else []
            funcs.append((f"{node.name}({', '.join(args)})", first_line(ast.get_docstring(node))))
    return first_line(ast.get_docstring(tree)), funcs, tree


def resolve_imports(tree, mod, is_pkg_init, known):
    """Set of known modules that `mod` imports (relative and absolute)."""
    out = set()
    pkg_parts = mod.split('.') if is_pkg_init else mod.split('.')[:-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                base_parts = pkg_parts[:len(pkg_parts) - node.level + 1]
                base = '.'.join(base_parts + ([node.module] if node.module else []))
            else:
                base = node.module or ''
            for alias in node.names:
                if f'{base}.{alias.name}' in known:
                    out.add(f'{base}.{alias.name}')
                elif base in known:
                    out.add(base)
        elif isinstance(node, ast.Import):
            out.update(a.name for a in node.names if a.name in known)
    out.discard(mod)
    return out


def describe_other(path):
    """One-line purpose for non-Python files."""
    text = path.read_text(errors='ignore')
    if path.suffix == '.ipynb':
        for cell in json.loads(text).get('cells', []):
            if cell['cell_type'] == 'markdown':
                return ''.join(cell['source']).strip().split('\n')[0].lstrip('# ').strip()
        return ''
    if path.suffix in ('.yml', '.yaml'):
        m = re.search(r'^name:\s*(.+)$', text, re.M)
        c = re.search(r'^#\s*(.+)$', text, re.M)
        return ' — '.join(x for x in [m and m.group(1).strip(), c and c.group(1).strip()] if x)
    for line in text.splitlines():
        if line.startswith('#') and not line.startswith('#!'):
            return line.lstrip('# ').strip()
    return ''


def notebook_imports(path, known):
    code = []
    for cell in json.loads(path.read_text()).get('cells', []):
        if cell['cell_type'] == 'code':
            code += [l for l in ''.join(cell['source']).splitlines() if not l.lstrip().startswith(('%', '!'))]
    try:
        return resolve_imports(ast.parse('\n'.join(code)), 'notebooks.nb', False, known)
    except SyntaxError:
        return set()


def scan():
    """Files with descriptions, the import graph (edges), and 'runs' references from non-Python files."""
    py_files = sorted(PKG_DIR.rglob('*.py')) + sorted((ROOT / 'scripts').glob('*.py'))
    files, mod_to_path, trees = {}, {}, {}
    for p in py_files:
        purpose, funcs, tree = describe_py(p)
        mod = module_name(p).removesuffix('.__init__')
        rel = p.relative_to(ROOT).as_posix()
        files[rel] = dict(purpose=purpose, funcs=funcs)
        mod_to_path[mod] = rel
        trees[rel] = (tree, mod, p.name == '__init__.py')
    known = set(mod_to_path)
    edges = set()   # (provider, consumer): consumer imports provider
    for rel, (tree, mod, is_init) in trees.items():
        for dep in resolve_imports(tree, mod, is_init, known):
            if not mod_to_path[dep].endswith('__init__.py'):
                edges.add((mod_to_path[dep], rel))
    for d in EXTRA_DIRS:
        for p in sorted((ROOT / d).glob('*')):
            rel = p.relative_to(ROOT).as_posix()
            if p.is_file() and p.name != 'README.md' and rel not in files:
                files[rel] = dict(purpose=describe_py(p)[0] if p.suffix == '.py' else describe_other(p), funcs=[])
                if p.suffix == '.ipynb':
                    edges.update((mod_to_path[m], rel) for m in notebook_imports(p, known)
                                 if not mod_to_path[m].endswith('__init__.py'))
    runs = set()    # (runner, target): a workflow/hook/script that invokes another file
    for rel in files:
        if Path(rel).suffix not in ('.py', '.ipynb'):
            text = (ROOT / rel).read_text(errors='ignore')
            runs.update((rel, t) for t in files if t != rel and t in text)
    return files, edges, runs


# ── rendering ────────────────────────────────────────────────────────────────
def node_id(label):
    return 'n_' + re.sub(r'\W', '_', label)


def group_of(path, focus_dir):
    """Node label for `path` when drawing focus_dir: files inside focus_dir stay files, others collapse."""
    parent, pkg = str(Path(path).parent), f'src/{PKG}'
    if parent in (focus_dir, pkg):        # own files, and top-level package modules, stay visible
        return Path(path).name
    if parent.startswith(pkg + '/'):
        return parent.removeprefix(pkg + '/').split('/')[0] + '/'
    return parent + '/'


def collapse(pairs, focus_dir, only_touching=True):
    out = set()
    for a, b in pairs:
        if not only_touching or focus_dir in (str(Path(a).parent), str(Path(b).parent)):
            ga, gb = group_of(a, focus_dir), group_of(b, focus_dir)
            if ga != gb:
                out.add((ga, gb))
    return out


def mermaid(focus_dir, files, edges, runs):
    in_dir = [f for f in files if str(Path(f).parent) == focus_dir and not f.endswith('__init__.py')]
    pairs, run_pairs = collapse(edges, focus_dir), collapse(runs, focus_dir)
    if not in_dir and not pairs and not run_pairs:
        return ''
    lines = ['```mermaid', 'flowchart LR', f'  subgraph here["{focus_dir}/"]']
    lines += [f'    {node_id(Path(f).name)}["{Path(f).name}"]' for f in in_dir]
    lines.append('  end')
    labels = {x for p in pairs | run_pairs for x in p} - {Path(f).name for f in in_dir}
    lines += [f'  {node_id(lab)}["{lab}"]' for lab in sorted(labels)]
    lines += [f'  {node_id(a)} --> {node_id(b)}' for a, b in sorted(pairs)]
    lines += [f'  {node_id(a)} -. runs .-> {node_id(b)}' for a, b in sorted(run_pairs)]
    lines.append('```')
    return '\n'.join(lines)


def rel_link(from_dir, to_path):
    return os.path.relpath(ROOT / to_path, ROOT / from_dir).replace(os.sep, '/')


def files_table(d, files):
    rows = ['| File | What it does |', '|---|---|']
    for f in sorted(files):
        if str(Path(f).parent) == d and not f.endswith('__init__.py'):
            rows.append(f"| [`{Path(f).name}`]({Path(f).name}) | {files[f]['purpose'] or '—'} |")
    return '\n'.join(rows)


def api_section(d, files):
    out = []
    for f in sorted(files):
        if str(Path(f).parent) == d and files[f]['funcs']:
            out.append(f"**`{Path(f).name}`**")
            out += [f"- `{sig}`" + (f" — {doc}" if doc else '') for sig, doc in files[f]['funcs']]
            out.append('')
    return '\n'.join(out).strip()


def dir_purpose(d, files):
    return (files.get(f'{d}/__init__.py', {}).get('purpose') or DIR_PURPOSE.get(d, '')).strip()


def code_dirs(files):
    dirs = sorted({str(Path(f).parent) for f in files if f.startswith('src/')})
    return dirs + [d for d in EXTRA_DIRS if any(str(Path(f).parent) == d for f in files)]


def render_dir(d, files, edges, runs):
    parts = [f'# `{d}/`', '', f'> {dir_purpose(d, files)}', '',
             f'[← Project README]({rel_link(d, "README.md")})', '']
    chart = mermaid(d, files, edges, runs)
    if chart:
        parts += ['## How it connects', '',
                  'Solid `A --> B` = B imports A (A feeds B). Dotted = A runs B. '
                  'Other directories are collapsed to one box.', '', chart, '']
    parts += ['## Files', '', files_table(d, files), '']
    api = api_section(d, files)
    if api:
        parts += ['## Functions', '', api, '']
    return parts


def render_root(files, edges, runs):
    pkg = f'src/{PKG}'
    pairs = {p for p in collapse(edges, '__root__', only_touching=False) if not ROOT_HIDDEN & set(p)}
    run_pairs = collapse(runs, '__root__', only_touching=False)
    labels = sorted({x for p in pairs | run_pairs for x in p})
    inside = [l for l in labels if l.endswith('.py') or l.rstrip('/') in SUBPACKAGES]
    outside = [l for l in labels if l not in inside]
    chart = ['```mermaid', 'flowchart LR',
             '  csv[("CMS CSVs<br/>~/Downloads, 19 GB")]',
             '  pq[("Parquet, zstd<br/>~/Downloads/cms_parquet, 2.1 GB")]',
             '  duck[("cms.duckdb<br/>claims view + reference tables")]',
             '  out[/"~/Downloads/cms_runs/&lt;run&gt;/<br/>figures · tables · console.log<br/>gallery.html · all_figures.pdf"/]',
             '  idx[/"cms_runs/index.html<br/>all runs"/]',
             '  claude(["Claude Code"])',
             '  gh(["GitHub repo"])',
             f'  subgraph code["{pkg}/"]']
    chart += [f'    {node_id(l)}["{l}"]' for l in inside]
    chart += ['    cfg["config.py · style.py · audit.py<br/>(used by every layer)"]', '  end']
    chart += [f'  {node_id(l)}["{l}"]' for l in outside]
    chart += [f'  {node_id(a)} --> {node_id(b)}' for a, b in sorted(pairs)]
    chart += [f'  {node_id(a)} -. runs .-> {node_id(b)}' for a, b in sorted(run_pairs)]
    chart += [f'  csv -- "convert_cms_to_parquet.py" --> pq', f'  pq -- "build_database.py" --> duck',
              f'  duck -- "read-only SQL" --> {node_id("db/")}', f'  {node_id("reporting/")} --> out', 'out --> idx',
              f'  {node_id("notebooks/")} -- "papermill traceback" --> claude',
              f'  claude -- "fix src/, commit, push" --> gh', f'  gh -- "git pull" --> {node_id("notebooks/")}',
              '```']
    dir_rows = ['| Directory | What it is |', '|---|---|']
    dir_rows += [f'| [`{d}/`]({d}/README.md) | {dir_purpose(d, files)} |' for d in code_dirs(files)]
    return [
        '# Cardiac Imaging Utilization in Medicare FFS (2018–2023)', '',
        '> State and national trends in Echo, SPECT, cardiac CTA, MRI and PET among Medicare fee-for-service '
        'beneficiaries, plus negative binomial models of CTA use vs imaging-physician density. '
        'Produces Figures 1–9, S1–S2 and Table 1.', '',
        '## How it all connects', '',
        'Solid `A --> B` = B uses A. Dotted = A runs B. Each directory has its own README (table below).', '',
        '\n'.join(chart), '',
        '## Quick start', '',
        '```bash\nsource ~/jupyter-env/bin/activate && pip install -e ".[notebook]"\n```',
        '```bash\npython scripts/convert_cms_to_parquet.py\n```',
        '```bash\npython scripts/build_database.py\n```',
        '```bash\npython -m cardiac_imaging.pipeline\n```', '',
        'Each run gets its own folder in `~/Downloads/cms_runs/` (linked as `runs/` here): figures (PNG + TIFF), '
        'result tables (CSV), `console.log`, `manifest.json`, a `gallery.html` of every chart and `all_figures.pdf`. '
        '`runs/index.html` lists every run with its headline IRRs. Use `--no-tiff` for quick runs, `--label` to tag one.', '',
        'Paths default to `~/Downloads`; override with the variables in [`.env.example`](.env.example). '
        'Full setup and the Claude debug loop: [`docs/SETUP_PLAN.md`](docs/SETUP_PLAN.md).', '',
        '## Directory map', '', '\n'.join(dir_rows), '',
        '## How errors reach Claude', '',
        '1. Claude Code runs `papermill notebooks/main.ipynb runs/out.ipynb`; a failing step writes `logs/last_error.md`.',
        '2. Claude reads the traceback, fixes `src/` (never the notebook JSON), reruns until it passes.',
        '3. Claude runs `python scripts/update_readmes.py` and commits code + READMEs together, then pushes.',
        '4. Optional: with `CARDIAC_GITHUB_TOKEN` set, a failure also opens a `notebook-error` issue that the Claude GitHub Action answers with a fix PR.', '',
        '## READMEs are generated', '',
        'Every `README.md` is rebuilt from docstrings and imports by [`scripts/update_readmes.py`](scripts/update_readmes.py) '
        '— on every commit (git hook) and every push (GitHub Action). '
        'To change a description, edit the module docstring, not the README. '
        'Free-form notes go inside the MANUAL block below.', '',
    ]


def with_manual(parts, old_text):
    m = MANUAL_RE.search(old_text or '')
    parts += ['## Notes', '', m.group(0) if m else DEFAULT_MANUAL, '',
              '<!-- Generated by scripts/update_readmes.py — edit docstrings, not this file. -->']
    return '\n'.join(parts) + '\n'


def build():
    """{README path: content} for the whole repo."""
    files, edges, runs = scan()
    targets = {'README.md': render_root(files, edges, runs)}
    for d in code_dirs(files):
        targets[f'{d}/README.md'] = render_dir(d, files, edges, runs)
    out = {}
    for path, parts in targets.items():
        p = ROOT / path
        out[path] = with_manual(parts, p.read_text() if p.exists() else '')
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--check', action='store_true', help='exit 1 if any README is out of date; write nothing')
    args = ap.parse_args()
    stale = []
    for path, content in build().items():
        p = ROOT / path
        if not p.exists() or p.read_text() != content:
            stale.append(path)
            if not args.check:
                p.write_text(content)
    if args.check:
        print('Stale READMEs: ' + ', '.join(stale) if stale else 'READMEs up to date.')
        sys.exit(1 if stale else 0)
    print('Updated: ' + ', '.join(stale) if stale else 'READMEs already up to date.')


if __name__ == '__main__':
    main()
