"""Keep runs identical on every laptop through GitHub: verify/repair each run's release, publish reliably, sync both ways."""
import time
from datetime import datetime

from .. import config
from . import gallery, index, publish
from .run_store import list_runs, read_manifest, write_manifest

RETRY_WAITS = (5, 20)   # seconds between publish attempts (3 attempts in all)


def verify_release(run_dir):
    """Problems with a run's GitHub release, in plain English ([] = complete and up to date)."""
    m = read_manifest(run_dir)
    tag = (m.get('code') or {}).get('tag')
    if not tag:
        return ['run has no code-snapshot tag']
    info = publish.release_info(tag)
    if info is None:
        return ['no GitHub release yet']
    problems = []
    if info.get('isDraft'):
        problems.append('release is still a draft')
    have = {a['name']: a.get('size', 0) for a in info.get('assets', [])}
    for name in publish.expected_assets(run_dir, m):
        if name not in have:
            problems.append(f'missing file {name}')
        elif have[name] <= 0:
            problems.append(f'empty file {name}')
    rec = publish.record_from_body(info.get('body'))
    if rec is None:
        problems.append('release notes have no run record')
    elif rec.get('run_id') != m['run_id']:
        problems.append(f"release notes describe a different run ({rec.get('run_id')})")
    else:
        local = publish.summary(m)
        stale = [k for k in ('status', 'summary', 'review', 'headline') if rec.get(k) != local.get(k)]
        if stale:
            problems.append('release notes out of date (' + ', '.join(stale) + ')')
    return problems


def _set_publish_error(run_dir, problems):
    """Record (or clear, when problems is empty) the last publishing failure in the manifest."""
    m = read_manifest(run_dir)
    m['publish_error'] = (dict(at=datetime.now().astimezone().isoformat(timespec='seconds'), problems=problems)
                          if problems else None)
    write_manifest(run_dir, m)


def publish_reliably(run_dir, attempts=3):
    """Publish a run and check the result on GitHub; repair and retry until complete. Returns the remaining problems."""
    problems = ['not attempted']
    for i in range(attempts):
        try:
            publish.publish_run(run_dir, force=i > 0 or bool(read_manifest(run_dir).get('published')))
            problems = verify_release(run_dir)
        except Exception as e:                      # network/gh/git failures: retry, then report
            problems = [f'{type(e).__name__}: {e}']
        if not problems:
            _set_publish_error(run_dir, [])
            print('  ✓ GitHub release verified: every file present and notes up to date')
            return []
        print(f"  ! GitHub release incomplete (attempt {i + 1}/{attempts}): {'; '.join(problems)}")
        if i < attempts - 1:
            time.sleep(RETRY_WAITS[min(i, len(RETRY_WAITS) - 1)])
    _set_publish_error(run_dir, problems)
    print('  ✗ Could not complete the GitHub release — it will be retried by the next sync '
          '(python scripts/sync_runs.py, or Sync now on the results page).')
    return problems


def _newer(a, b):
    """True when review `a` is more recent than review `b` (either may be None)."""
    return bool(a) and (not b or (a.get('at') or '') > (b.get('at') or ''))


def sync(upload=True, download=True, dry_run=False, runs_dir=None):
    """Two-way sync with GitHub. Returns [{run_id, action, detail}] describing what was (or, with dry_run, would be) done.

    Upload: runs not yet (completely) on GitHub are published and verified. Labels: the more recent change wins.
    Download: runs that exist only on GitHub are fetched. Every published run's release is verified and repaired.
    """
    runs_dir = runs_dir or config.RUNS_DIR
    report = []

    def note(run_id, action, detail=''):
        """Record one line of the report and print it."""
        report.append(dict(run_id=run_id, action=action, detail=detail))
        print(f"  {action:<14} {run_id}  {detail}")

    remote = {r['run_id']: r for r in publish.remote_runs()}
    for m in list_runs(runs_dir):
        rid, run_dir = m['run_id'], runs_dir / m['run_id']
        r = remote.get(rid)
        if r is None:
            if not upload:
                note(rid, 'needs upload', 'not on GitHub')
                continue
            if dry_run:
                note(rid, 'would upload')
                continue
            left = publish_reliably(run_dir)
            note(rid, 'uploaded' if not left else 'upload failed', '; '.join(left))
            continue
        if _newer(r.get('review'), m.get('review')):              # label changed on the other laptop more recently
            if dry_run:
                note(rid, 'would update label', f"from GitHub: {(r['review'] or {}).get('label')}")
            else:
                m['review'] = r['review']
                m.setdefault('published', r.get('published'))
                write_manifest(run_dir, m)
                gallery.build(run_dir)
                note(rid, 'label ← GitHub', str((r['review'] or {}).get('label') or 'cleared'))
        problems = verify_release(run_dir)
        if not problems:
            note(rid, 'ok')
        elif not upload or dry_run:
            note(rid, 'needs repair' if not dry_run else 'would repair', '; '.join(problems))
        else:
            left = publish_reliably(run_dir)
            note(rid, 'repaired' if not left else 'repair failed', '; '.join(problems if not left else left))
    local_ids = {m['run_id'] for m in list_runs(runs_dir)}
    for rid in sorted(set(remote) - local_ids):
        if not download:
            note(rid, 'on GitHub only')
        elif dry_run:
            note(rid, 'would download')
        else:
            try:
                publish.fetch_run(rid, runs_dir)
                note(rid, 'downloaded')
            except Exception as e:
                note(rid, 'download failed', f'{type(e).__name__}: {e}')
    if not dry_run:
        index.build(runs_dir)
    return report


def summarize(report):
    """One-line plain-English summary of a sync report."""
    count = lambda *acts: sum(1 for r in report if r['action'] in acts)   # noqa: E731
    failed = count('upload failed', 'repair failed', 'download failed')
    parts = [f"{count('uploaded')} uploaded", f"{count('downloaded')} downloaded",
             f"{count('repaired')} repaired", f"{count('label ← GitHub')} labels updated", f"{count('ok')} already in sync"]
    return ', '.join(parts) + (f' — {failed} FAILED' if failed else '')
