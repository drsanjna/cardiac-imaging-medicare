"""Manage run history: list local + GitHub runs, publish runs as GitHub Releases, download runs back, rebuild the index.

    python scripts/runs.py list
    python scripts/runs.py publish --pending            # upload every local run not yet on GitHub
    python scripts/runs.py publish RUN_ID [--assume-commit SHA --note "..."]   # older runs without a snapshot
    python scripts/runs.py fetch RUN_ID | --all         # download outputs from GitHub into the runs folder
    python scripts/runs.py index                        # rebuild runs/index.html
"""
import argparse

from cardiac_imaging import config, gitinfo
from cardiac_imaging.reporting import gallery, index, publish
from cardiac_imaging.reporting.run_store import data_fingerprint, list_runs, read_manifest, tag_for, write_manifest


def backfill_code(run_dir, sha, note):
    """Give a run made before code snapshots existed a best-known code commit (marked approximate)."""
    m = read_manifest(run_dir)
    if m.get('code', {}).get('snapshot'):
        return
    sha = gitinfo.git('rev-parse', sha, check=True)
    head = m.pop('commit', '') or sha
    m['code'] = dict(branch=m.pop('branch', ''), head=head, dirty=m.pop('dirty', False),
                     repo=gitinfo.repo_slug(), tag=tag_for(m['run_id']), snapshot=sha, exact=False,
                     note=note or f"Run predates code snapshots; tagged at {sha[:7]}, the first commit containing its code.",
                     **gitinfo.commit_info(head))
    for k in ('commit_short', 'remote'):
        m.pop(k, None)
    m.setdefault('data', data_fingerprint())
    m.setdefault('versions', {'python': m.pop('python', '')})
    m.setdefault('published', None)
    write_manifest(run_dir, m)
    gallery.build(run_dir)
    print(f"  Backfilled code for {m['run_id']} → {sha[:7]} (approximate)")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('list', help='local and GitHub runs')
    pub = sub.add_parser('publish', help='upload runs as GitHub Releases')
    pub.add_argument('run_ids', nargs='*')
    pub.add_argument('--pending', action='store_true', help='every local run not yet on GitHub')
    pub.add_argument('--assume-commit', help='for runs made before code snapshots: commit to tag them at')
    pub.add_argument('--note', help='why that commit is a good stand-in (shown on the run)')
    fetch = sub.add_parser('fetch', help='download run outputs from GitHub')
    fetch.add_argument('run_ids', nargs='*')
    fetch.add_argument('--all', action='store_true', help='every GitHub run missing locally')
    sub.add_parser('index', help='rebuild index.html')
    args = p.parse_args()

    if args.cmd == 'list':
        local = {m['run_id']: m for m in list_runs()}
        remote = {r['run_id']: r for r in publish.remote_runs()}
        for rid in sorted(set(local) | set(remote), reverse=True):
            r = local.get(rid) or remote[rid]
            where = ' + '.join(x for x, ok in [('local', rid in local), ('GitHub', rid in remote)] if ok)
            print(f"{rid:<60} {r.get('status', ''):<7} {where}")
        return
    if args.cmd == 'publish':
        ids = args.run_ids or [m['run_id'] for m in list_runs() if args.pending and not m.get('published')]
        for rid in ids:
            d = config.RUNS_DIR / rid
            if args.assume_commit:
                backfill_code(d, args.assume_commit, args.note)
            publish.publish_run(d)
    elif args.cmd == 'fetch':
        ids = args.run_ids
        if args.all:
            have = {m['run_id'] for m in list_runs()}
            ids = [r['run_id'] for r in publish.remote_runs() if r['run_id'] not in have]
        for rid in ids:
            publish.fetch_run(rid)
    index.build(config.RUNS_DIR)
    print(f"Index: {config.RUNS_DIR / 'index.html'}")


if __name__ == '__main__':
    main()
