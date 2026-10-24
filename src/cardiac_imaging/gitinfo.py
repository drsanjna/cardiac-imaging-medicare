"""Git helpers: run git, find the GitHub repo, and freeze the exact working tree as a code-snapshot commit + tag."""
import os
import subprocess
import tempfile

from . import config


def git(*args, env=None, check=False):
    """Output of `git <args>` in the repo ('' on failure unless check=True)."""
    try:
        return subprocess.check_output(['git', *args], cwd=config.REPO_ROOT, text=True, env=env,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:
        if check:
            raise
        return ''


def repo_slug():
    """owner/name from GITHUB_REPOSITORY or the origin remote URL (None if not on GitHub)."""
    slug = os.environ.get('GITHUB_REPOSITORY')
    if slug:
        return slug
    url = git('remote', 'get-url', 'origin')
    if 'github.com' not in url:
        return None
    return url.split('github.com')[-1].lstrip(':/').removesuffix('.git')


def commit_info(sha):
    """Subject, author and ISO date of a commit."""
    out = git('show', '-s', '--format=%s%x1f%an%x1f%cI', sha)
    subject, author, date = (out.split('\x1f') + ['', '', ''])[:3]
    return dict(subject=subject, author=author, date=date)


def snapshot_commit(message):
    """Commit holding the exact working tree (tracked + untracked, .gitignore respected), without touching
    the real index, branch or files. Returns (sha, uncommitted_changes_included); HEAD itself when clean."""
    head = git('rev-parse', 'HEAD')
    if not head:
        return None, False
    if not git('status', '--porcelain', '--untracked-files=all'):
        return head, False
    with tempfile.TemporaryDirectory() as d:
        env = {**os.environ, 'GIT_INDEX_FILE': os.path.join(d, 'index')}
        git('read-tree', 'HEAD', env=env, check=True)
        git('add', '-A', env=env, check=True)
        tree = git('write-tree', env=env, check=True)
    return git('commit-tree', tree, '-p', head, '-m', message, check=True), True


def ensure_tag(tag, sha, message):
    """Create annotated tag `tag` → sha if it doesn't exist (keeps the snapshot commit from being garbage-collected)."""
    if not git('rev-parse', '-q', '--verify', f'refs/tags/{tag}'):
        git('tag', '-a', tag, sha, '-m', message, check=True)
