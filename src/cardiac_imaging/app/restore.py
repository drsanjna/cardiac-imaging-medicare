"""Restore the code to a run's snapshot (or undo that) as a new commit, after backing up the current state as a tag."""
from datetime import datetime

from .. import config, gitinfo
from ..reporting.run_store import tag_for


class RestoreError(RuntimeError):
    """A restore could not be done safely; the message says why in plain English."""


def _ensure_local_tag(tag):
    """Make sure `tag` exists locally, fetching it from GitHub if needed."""
    if not gitinfo.git('rev-parse', '-q', '--verify', f'refs/tags/{tag}'):
        gitinfo.git('fetch', '-q', 'origin', 'tag', tag)
    if not gitinfo.git('rev-parse', '-q', '--verify', f'refs/tags/{tag}'):
        raise RestoreError(f"Couldn't find the code snapshot {tag} locally or on GitHub.")


def status():
    """Current branch, commit and whether there are uncommitted changes."""
    return dict(branch=gitinfo.git('rev-parse', '--abbrev-ref', 'HEAD'), head=gitinfo.git('rev-parse', 'HEAD'),
                dirty=bool(gitinfo.git('status', '--porcelain', '--untracked-files=all')),
                subject=gitinfo.commit_info('HEAD').get('subject', ''))


def restore_to(ref, message):
    """Make the code on the current branch identical to `ref` with one new commit; returns what happened.

    The current state (including uncommitted edits) is first saved as tag backup-<timestamp>, so nothing is lost
    and the restore can be undone with restore_to(backup_tag, ...).
    """
    st = status()
    if st['branch'] in ('HEAD', ''):
        raise RestoreError("The repository isn't on a branch (detached HEAD); switch to a branch first.")
    target = gitinfo.git('rev-parse', f'{ref}^{{commit}}')
    if not target:
        raise RestoreError(f"Unknown version {ref}.")
    stamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    backup_sha, _ = gitinfo.snapshot_commit(f"Backup before restoring {ref} ({stamp})")
    backup_tag = f'backup-{stamp}'
    gitinfo.ensure_tag(backup_tag, backup_sha, f"State of {st['branch']} before restoring {ref}")

    if gitinfo.git('rev-parse', f'{target}^{{tree}}') == gitinfo.git('rev-parse', f'{backup_sha}^{{tree}}'):
        return dict(changed=False, backup_tag=backup_tag, branch=st['branch'],
                    message='The code is already identical to that version — nothing to do.')
    # Tracked files become exactly the target's; files tracked now but absent there are removed.
    gitinfo.git('restore', '--source', target, '--staged', '--worktree', '--', '.', check=True)
    if not gitinfo.git('diff', '--cached', '--name-only'):   # target == last commit: only unsaved edits were reverted
        return dict(changed=True, backup_tag=backup_tag, branch=st['branch'], commit=gitinfo.git('rev-parse', 'HEAD'),
                    message="Your unsaved edits were reverted to match that version (they're saved — Undo brings them back).")
    # --no-verify: the restored code may predate today's hooks/tests; this commit only reproduces a known version.
    gitinfo.git('commit', '-q', '--no-verify', '-m', f"{message}\n\nRestored files from {ref} ({target[:12]}). "
                f"Previous state saved as tag {backup_tag}.", check=True)
    return dict(changed=True, backup_tag=backup_tag, branch=st['branch'], commit=gitinfo.git('rev-parse', 'HEAD'),
                message=f"Code restored on branch {st['branch']}. Your previous code is saved and can be brought back with Undo.")


def restore_run(run_id):
    """Restore the code used by `run_id` (its run-<id> snapshot tag)."""
    tag = tag_for(run_id)
    _ensure_local_tag(tag)
    return restore_to(tag, f"Restore code to run {run_id}")


def undo(backup_tag):
    """Bring back the code saved in `backup_tag` (undoes a restore)."""
    if not backup_tag.startswith('backup-'):
        raise RestoreError("Only backup tags created by Restore can be undone this way.")
    _ensure_local_tag(backup_tag)
    return restore_to(backup_tag, f"Undo restore (back to {backup_tag})")


def push():
    """Push the current branch to GitHub; returns a plain-English result."""
    branch = status()['branch']
    gitinfo.git('push', '-q', 'origin', branch, check=True)
    return dict(message=f"Pushed {branch} to GitHub.", branch=branch, repo=gitinfo.repo_slug(), root=str(config.REPO_ROOT))
