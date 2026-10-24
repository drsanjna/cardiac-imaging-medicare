"""Write an English summary of pushed work to docs/WORK_LOG.md (run by the post-push GitHub Action on every push to main).

    python scripts/work_log.py --before <sha> --after <sha> [--junit report.xml] [--print]
"""
import argparse
import ast
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / 'docs' / 'WORK_LOG.md'
HEADER = ('# Work log\n\nOne entry per push to `main`, newest first — written automatically by '
          '`scripts/work_log.py` from commit messages, the diff and the test run.\n')
ZERO = '0' * 40


def git(*args):
    """Output of a git command in the repo ('' on failure)."""
    try:
        return subprocess.check_output(['git', *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except subprocess.CalledProcessError:
        return ''


def resolve_range(before, after):
    """(base, head) commits; a new branch (all-zero `before`) or missing base falls back to after's parent."""
    head = git('rev-parse', after or 'HEAD')
    if not before or before == ZERO or not git('rev-parse', '-q', '--verify', f'{before}^{{commit}}'):
        before = git('rev-parse', f'{head}~1') or head
    return git('rev-parse', before), head


def area(path):
    """Human label for where a file lives."""
    p = Path(path)
    if p.parts[:2] == ('src', 'cardiac_imaging'):
        return 'code: ' + ('/'.join(p.parts[2:-1]) or 'core')
    return {'tests': 'tests', 'scripts': 'scripts', 'docs': 'docs', 'notebooks': 'notebook', '.github': 'automation',
            '.githooks': 'automation'}.get(p.parts[0], 'other') if len(p.parts) > 1 else 'repo root'


def functions_at(commit, path):
    """Names of functions/classes (Class.method for methods) in a Python file at `commit`."""
    text = git('show', f'{commit}:{path}')
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return set()
    names = set()
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(n.name)
        elif isinstance(n, ast.ClassDef):
            names.add(n.name)
            names |= {f'{n.name}.{m.name}' for m in n.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))}
    return names


def test_counts(junit):
    """(passed, failed, skipped) from a pytest JUnit XML report, or None."""
    if not junit or not Path(junit).exists():
        return None
    root = ET.parse(junit).getroot()
    suites = [root] if root.tag == 'testsuite' else list(root)
    tot = lambda k: sum(int(s.get(k, 0)) for s in suites)   # noqa: E731
    failed = tot('failures') + tot('errors')
    return tot('tests') - failed - tot('skipped'), failed, tot('skipped')


def bullets(body):
    """Commit-body points as single lines: '- ' starts a point; wrapped continuation lines are joined back on."""
    out = []
    for line in re.sub(r'Co-Authored-By:.*', '', body).splitlines():
        t = line.strip()
        if not t:
            continue
        if t.startswith(('- ', '* ')) or not out:
            out.append(t.lstrip('-* ').strip())
        else:
            out[-1] += ' ' + t
    return out


def entry(before, after, junit=None):
    """Markdown for one work-log entry."""
    commits = git('log', '--reverse', '--format=%H%x1f%s%x1f%b%x1e', f'{before}..{after}').split('\x1e')
    commits = [c.strip().split('\x1f') for c in commits if c.strip()]
    stats = defaultdict(lambda: [0, 0, 0])
    added_fn, removed_fn = [], []
    for line in git('diff', '--numstat', before, after).splitlines():
        a, d, path = line.split('\t', 2)
        s = stats[area(path)]
        s[0] += 1
        s[1] += int(a) if a.isdigit() else 0
        s[2] += int(d) if d.isdigit() else 0
        if path.endswith('.py'):
            old, new = functions_at(before, path), functions_at(after, path)
            added_fn += [f'{path}: {n}' for n in sorted(new - old)]
            removed_fn += [f'{path}: {n}' for n in sorted(old - new)]
    when = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    lines = [f"## {when} — {len(commits)} commit{'s' * (len(commits) != 1)} (`{before[:7]}..{after[:7]}`)", '',
             '### What was done', '']
    for sha, subject, body, *_ in [c + [''] * (3 - len(c)) for c in commits]:
        if subject.startswith(('Merge branch', 'Merge pull request', 'docs: regenerate READMEs')):
            continue
        lines.append(f'- **{subject}** (`{sha[:7]}`)')
        lines += [f'  - {b}' for b in bullets(body)[:10]]
    lines += ['', '### Where the changes landed', '', '| Area | Files | + lines | − lines |', '|---|---|---|---|']
    lines += [f'| {a} | {f} | {ad} | {de} |' for a, (f, ad, de) in sorted(stats.items())]
    if added_fn or removed_fn:
        lines += ['', '### Impact on the code', '']
        if added_fn:
            lines.append(f"- New functions ({len(added_fn)}): " + ', '.join(f'`{x}`' for x in added_fn[:25])
                         + (' …' if len(added_fn) > 25 else ''))
        if removed_fn:
            lines.append(f"- Removed functions ({len(removed_fn)}): " + ', '.join(f'`{x}`' for x in removed_fn[:25])
                         + (' …' if len(removed_fn) > 25 else ''))
    tc = test_counts(junit)
    if tc:
        p, f, s = tc
        lines += ['', f"### Tests\n\n{'✅' if not f else '❌'} {p} passed, {f} failed, {s} skipped."]
    return '\n'.join(lines) + '\n'


def prepend(text, after):
    """Insert an entry at the top of WORK_LOG.md unless this head commit is already logged."""
    current = LOG.read_text() if LOG.exists() else HEADER
    if f'..{after[:7]}`)' in current:
        return False
    older = (current[len(HEADER):] if current.startswith(HEADER) else current).strip('\n')
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text(HEADER + '\n' + text + ('\n' + older + '\n' if older else ''))
    return True


def main():
    """Build the entry for --before..--after and prepend it (or print it with --print)."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--before')
    ap.add_argument('--after', default='HEAD')
    ap.add_argument('--junit')
    ap.add_argument('--print', action='store_true', help='print the entry instead of writing WORK_LOG.md')
    args = ap.parse_args()
    before, after = resolve_range(args.before, args.after)
    text = entry(before, after, args.junit)
    if args.print:
        print(text)
        return
    print('WORK_LOG.md updated.' if prepend(text, after) else 'Already logged.')


if __name__ == '__main__':
    sys.exit(main())
