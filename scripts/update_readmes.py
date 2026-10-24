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
EXTRA_DIRS = ['scripts', 'tests', 'notebooks', '.github/workflows', '.githooks', 'legacy']
DIR_PURPOSE = {  # directories without an __init__.py docstring
    'scripts': 'Command-line tools: CSV → Parquet, database build, run history, README/docstring checks, work log, hypotheses.',
    'tests': 'Test suite (pytest): synthetic-data tests for every layer + real-data regression tests that pin published numbers.',
    'notebooks': 'Thin Jupyter driver: imports from src/, runs the pipeline. Run headless with papermill.',
    '.github/workflows': 'GitHub Actions: tests + docstring rule + READMEs + work log on every push; Claude fixes @claude issues.',
    '.githooks': 'Local git hooks: before each commit — every function documented, READMEs regenerated, quick tests pass.',
    'legacy': 'The original single-file analysis script, kept unchanged for reference. Not imported by anything.',
}
ROOT_HIDDEN = {'config.py', 'style.py', 'audit.py'}   # feed every layer; drawn as one box on the root chart
SUBPACKAGES = ('analysis', 'db', 'figures', 'loaders', 'reporting')
MANUAL_RE = re.compile(r'<!-- BEGIN MANUAL -->.*?<!-- END MANUAL -->', re.S)
DEFAULT_MANUAL = '<!-- BEGIN MANUAL -->\n<!-- END MANUAL -->'


# ── code inspection ──────────────────────────────────────────────────────────
def first_line(text):
    """First line of a docstring (empty string if none)."""
    return (text or '').strip().split('\n')[0].strip()


def module_name(path):
    """Dotted name for a .py file: cardiac_imaging.loaders.claims, scripts.update_readmes."""
    base = PKG_DIR.parent if PKG_DIR in path.parents else ROOT
    return '.'.join(path.relative_to(base).with_suffix('').parts)


def describe_py(path):
    """Parse a .py file: (module purpose, [(signature, doc, private?)...], AST)."""
    tree = ast.parse(path.read_text())
    funcs = []

    def visit(nodes, prefix=''):
        for node in nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                args = [a.arg for a in node.args.args if a.arg != 'self'] if not isinstance(node, ast.ClassDef) else []
                sig = f"{prefix}{node.name}({', '.join(args)})" if not isinstance(node, ast.ClassDef) else f"class {node.name}"
                funcs.append((sig, first_line(ast.get_docstring(node)), node.name.startswith('_')))
                if isinstance(node, ast.ClassDef):
                    visit(node.body, prefix=f'{node.name}.')
    visit(tree.body)
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
    """Known modules imported by a notebook's code cells (magics skipped)."""
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
    py_files = sorted(PKG_DIR.rglob('*.py')) + sorted((ROOT / 'scripts').glob('*.py')) + sorted((ROOT / 'tests').glob('*.py'))
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
        if rel.startswith('tests/'):   # tests import everything; drawing those edges would bury the system map
            continue
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
    """Mermaid-safe node id for a label."""
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
    """Map file-level edges to the boxes drawn for focus_dir, dropping self-edges."""
    out = set()
    for a, b in pairs:
        if not only_touching or focus_dir in (str(Path(a).parent), str(Path(b).parent)):
            ga, gb = group_of(a, focus_dir), group_of(b, focus_dir)
            if ga != gb:
                out.add((ga, gb))
    return out


def mermaid(focus_dir, files, edges, runs):
    """Mermaid flowchart for one directory: its files plus collapsed neighbours."""
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
    """Relative link from one directory to a repo path."""
    return os.path.relpath(ROOT / to_path, ROOT / from_dir).replace(os.sep, '/')


def files_table(d, files):
    """Markdown table of the files in a directory and what each does."""
    rows = ['| File | What it does |', '|---|---|']
    for f in sorted(files):
        if str(Path(f).parent) == d and not f.endswith('__init__.py'):
            rows.append(f"| [`{Path(f).name}`]({Path(f).name}) | {files[f]['purpose'] or '—'} |")
    return '\n'.join(rows)


def api_section(d, files):
    """Markdown list of every function in a directory with its one-line explanation."""
    out = []
    for f in sorted(files):
        if str(Path(f).parent) == d and files[f]['funcs']:
            out.append(f"**`{Path(f).name}`**")
            out += [f"- `{sig}`" + (' *(internal)*' if private else '') + (f" — {doc}" if doc else ' — **undocumented**')
                    for sig, doc, private in files[f]['funcs']]
            out.append('')
    return '\n'.join(out).strip()


def dir_purpose(d, files):
    """A directory's one-line purpose (its __init__ docstring or DIR_PURPOSE)."""
    return (files.get(f'{d}/__init__.py', {}).get('purpose') or DIR_PURPOSE.get(d, '')).strip()


def code_dirs(files):
    """Directories that get a README, in display order."""
    dirs = sorted({str(Path(f).parent) for f in files if f.startswith('src/')})
    return dirs + [d for d in EXTRA_DIRS if any(str(Path(f).parent) == d for f in files)]


def render_dir(d, files, edges, runs):
    """README lines for one directory."""
    parts = [f'# `{d}/`', '', f'> {dir_purpose(d, files)}', '',
             f'[← Project README]({rel_link(d, "README.md")})', '']
    chart = mermaid(d, files, edges, runs)
    if chart:
        parts += ['## How it connects', '',
                  'Solid `A --> B` = B imports A (A feeds B). Dotted = A runs B. '
                  'Other directories are collapsed to one box.', '', chart, '']
    parts += ['## Files', '', files_table(d, files), '']
    if d == f'src/{PKG}/db':
        parts += data_model_section()
    api = api_section(d, files)
    if api:
        parts += ['## Functions', '', 'Every function and class in this directory, including internal helpers.', '', api, '']
    return parts


def load_schema():
    """Load db/schema.py by file path (standard library only, so the generator needs no installs)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('_schema', PKG_DIR / 'db' / 'schema.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def column_usage():
    """{column name: ['loaders/claims.py: load_detail', ...]} — functions whose source mentions the column."""
    usage = {}
    for p in sorted(PKG_DIR.rglob('*.py')):
        if p.name == 'schema.py':
            continue
        src = p.read_text()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                seg = ast.get_source_segment(src, node) or ''
                for name in re.findall(r'\b[A-Za-z_][A-Za-z0-9_]*\b', seg):
                    usage.setdefault(name, set()).add(f"{p.relative_to(PKG_DIR).as_posix()}: {node.name}")
    return usage


def data_model_section():
    """README lines describing every table, column meaning and which functions use each column."""
    schema = load_schema()
    usage = column_usage()
    er = ['```mermaid', 'erDiagram']
    for t in schema.TABLES:
        er.append(f'  {t["name"]} {{')
        er += [f'    {typ} {col}' for col, typ, _, used in t['columns'] if used]
        er.append('  }')
    er += [f'  {a} }}o--|| {b} : "{keys}"' for a, b, keys, _ in schema.RELATIONSHIPS]
    er.append('```')
    out = ['## Data model', '',
           'Defined in [`schema.py`](schema.py) — the build script and the tests check the real database against it. '
           'The diagram shows only the columns the analysis uses.', '', '\n'.join(er), '']
    out += ['**Joins**', ''] + [f'- `{a}` → `{b}` on `{k}`: {m}' for a, b, k, m in schema.RELATIONSHIPS] + ['']
    for t in schema.TABLES:
        out += [f'### `{t["name"]}` ({t["kind"].lower()})', '', f'- **One row =** {t["grain"]}',
                f'- **Source:** {t["source"]}', f'- **Built by:** {t["built_by"]}', f'- **Size:** {t["size"]}', '']
        if not t['all_columns_listed']:
            out += ['Only the columns the analysis reads are listed; every other raw column is kept as VARCHAR.', '']
        out += ['| Column | Type | Meaning | Used in |', '|---|---|---|---|']
        for col, typ, meaning, used in t['columns']:
            where = sorted(usage.get(col, ()))
            shown = '<br>'.join(f'`{w}`' for w in where[:5]) + (f'<br>…and {len(where) - 5} more' if len(where) > 5 else '')
            used_in = shown if (used and where) else ('—' if not used else 'config / SQL')
            out.append(f'| `{col}` | {typ} | {meaning} | {used_in} |')
        out.append('')
    return out


def render_root(files, edges, runs):
    """README lines for the repository root (system map, quick start, directory index)."""
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
        '```bash\npython -m cardiac_imaging.pipeline\n```',
        '```bash\npython -m cardiac_imaging.app\n```', '',
        'The app (last command) opens the results history: each run\'s time, a plain-English summary, what changed, '
        'and one-click **Restore**; galleries let you zoom into every chart and **discuss a hypothesis** with Claude.', '',
        'Each run gets its own folder in `~/Downloads/cms_runs/` (linked as `runs/` here): figures (PNG + TIFF), '
        'result tables (CSV), `console.log`, `manifest.json`, a `gallery.html` of every chart and `all_figures.pdf`. '
        '`runs/index.html` lists every run with its headline IRRs. Use `--no-tiff` for quick runs, `--label` to tag one.', '',
        '**Another laptop?** Follow [`docs/NEW_LAPTOP.md`](docs/NEW_LAPTOP.md) — one script (`scripts/setup_laptop.sh`) sets it all up. '
        'Paths default to `~/Downloads`; each laptop can override them in its own `.env` (see [`.env.example`](.env.example)). '
        'Full setup and the Claude debug loop: [`docs/SETUP_PLAN.md`](docs/SETUP_PLAN.md).', '',
        '## Directory map', '', '\n'.join(dir_rows), '',
        '## How errors reach Claude', '',
        '1. Claude Code runs `papermill notebooks/main.ipynb runs/out.ipynb`; a failing step writes `logs/last_error.md`.',
        '2. Claude reads the traceback, fixes `src/` (never the notebook JSON), reruns until it passes.',
        '3. Claude runs `python scripts/update_readmes.py` and commits code + READMEs together, then pushes.',
        '4. Optional: with `CARDIAC_GITHUB_TOKEN` set, a failure also opens a `notebook-error` issue that the Claude GitHub Action answers with a fix PR.', '',
        '## Safety nets', '',
        '- **Tests:** `pytest` (synthetic data, ~30 s) runs before every commit and on every push; '
        '`pytest -m real_data` pins the published numbers on the real data.',
        '- **Docs:** every function must have a docstring (pre-commit + CI); READMEs are regenerated from them.',
        '- **Work log:** each push to `main` appends an English summary to [`docs/WORK_LOG.md`](docs/WORK_LOG.md).',
        '- **Hypotheses:** `python scripts/consolidate_hypotheses.py` writes [`docs/hypotheses/`](docs/hypotheses/HYPOTHESES.md).', '',
        '## READMEs are generated', '',
        'Every `README.md` is rebuilt from docstrings and imports by [`scripts/update_readmes.py`](scripts/update_readmes.py) '
        '— on every commit (git hook) and every push (GitHub Action). '
        'To change a description, edit the module docstring, not the README. '
        'Free-form notes go inside the MANUAL block below.', '',
    ]


def with_manual(parts, old_text):
    """Append the preserved MANUAL block and the generated-file footer."""
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
    """Regenerate READMEs, or with --check report which are stale."""
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
