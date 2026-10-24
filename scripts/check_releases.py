"""Check on GitHub that every run's code-snapshot tag has a complete release (standard library + `gh` only; used in CI).

    python scripts/check_releases.py                       # check every run-* tag
    python scripts/check_releases.py --wait-for run-<id>   # wait (up to --timeout s) for that run's upload to finish, then check
Exit 1 if any release is missing, still a draft, lacks run_<id>.zip / manifest.json, has empty files, or lacks its run record.
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import time

MARKER = 'cardiac-run-summary:'
REQUIRED = lambda run_id: [f'run_{run_id}.zip', 'manifest.json']   # noqa: E731


def gh_json(path):
    """GET a GitHub API path (all pages) via `gh api`, flattened into one list."""
    out = subprocess.check_output(['gh', 'api', '--paginate', '--slurp', path], text=True)
    pages = json.loads(out)
    return [item for page in pages for item in (page if isinstance(page, list) else [page])]


def repo_slug():
    """owner/name from GITHUB_REPOSITORY or the git remote."""
    if os.environ.get('GITHUB_REPOSITORY'):
        return os.environ['GITHUB_REPOSITORY']
    url = subprocess.check_output(['git', 'remote', 'get-url', 'origin'], text=True).strip()
    return url.split('github.com')[-1].lstrip(':/').removesuffix('.git')


def problems_for(tag, release):
    """Plain-English problems with one run release ([] = complete)."""
    run_id = tag.removeprefix('run-')
    if release is None:
        return ['no release for this tag']
    out = []
    if release.get('draft'):
        out.append('release is a draft')
    sizes = {a['name']: a.get('size', 0) for a in release.get('assets', [])}
    for name in REQUIRED(run_id):
        if name not in sizes:
            out.append(f'missing {name}')
        elif sizes[name] <= 0:
            out.append(f'empty {name}')
    out += [f'empty {n}' for n, sz in sizes.items() if sz <= 0 and n not in REQUIRED(run_id)]
    body = release.get('body') or ''
    try:
        rec = json.loads(base64.b64decode(body.split(MARKER, 1)[1].split('-->', 1)[0].strip())) if MARKER in body else None
    except ValueError:
        rec = None
    if rec is None:
        out.append('notes have no run record')
    elif rec.get('run_id') != run_id:
        out.append(f"notes describe {rec.get('run_id')}")
    return out


def check(slug, only=None):
    """{tag: problems} for every run-* tag (or just `only`)."""
    tags = [t['name'] for t in gh_json(f'repos/{slug}/tags?per_page=100') if t['name'].startswith('run-')]
    releases = {r['tag_name']: r for r in gh_json(f'repos/{slug}/releases?per_page=100')}
    if only:
        tags = [only]
    return {t: problems_for(t, releases.get(t)) for t in sorted(tags)}


def main():
    """Check releases (optionally waiting for one) and exit 1 on problems."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--wait-for', help='a run-* tag whose upload may still be in progress')
    ap.add_argument('--timeout', type=int, default=900)
    args = ap.parse_args()
    slug = repo_slug()
    deadline = time.time() + args.timeout
    while True:
        result = check(slug, args.wait_for)
        if not args.wait_for or not result[args.wait_for] or time.time() > deadline:
            break
        print(f"  waiting for {args.wait_for}: {'; '.join(result[args.wait_for])}")
        time.sleep(30)
    bad = {t: p for t, p in result.items() if p}
    for t, p in result.items():
        print(f"{'✗' if p else '✓'} {t}" + (f": {'; '.join(p)}" if p else ''))
    print(f"{len(result) - len(bad)}/{len(result)} run releases complete.")
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
