"""Code snapshots and one-click restore/undo, in a throwaway git repo."""
import pytest

from cardiac_imaging import config, gitinfo
from cardiac_imaging.app import restore
from conftest import git


def test_snapshot_clean_repo_is_head():
    """A clean working tree snapshots to HEAD itself."""
    sha, dirty = gitinfo.snapshot_commit('snap')
    assert sha == git(config.REPO_ROOT, 'rev-parse', 'HEAD') and dirty is False


def test_snapshot_captures_uncommitted_and_untracked_without_touching_index():
    """Edits and new files are frozen in a commit; the real index, branch and files are unchanged."""
    repo = config.REPO_ROOT
    (repo / 'src' / 'app.py').write_text('VERSION = 99\n')
    (repo / 'src' / 'new.py').write_text('NEW = True\n')
    (repo / 'runs').mkdir()
    (repo / 'runs' / 'ignored.txt').write_text('x')
    head = git(repo, 'rev-parse', 'HEAD')
    sha, dirty = gitinfo.snapshot_commit('snap')
    assert dirty and sha != head
    assert git(repo, 'show', f'{sha}:src/app.py') == 'VERSION = 99'
    assert git(repo, 'show', f'{sha}:src/new.py') == 'NEW = True'
    assert 'runs/ignored.txt' not in git(repo, 'ls-tree', '-r', '--name-only', sha)
    assert git(repo, 'rev-parse', 'HEAD') == head
    assert git(repo, 'diff', '--cached', '--name-only') == ''
    assert '?? src/new.py' in git(repo, 'status', '--porcelain')


def test_ensure_tag_is_idempotent():
    """ensure_tag creates an annotated tag once and leaves it alone afterwards."""
    head = git(config.REPO_ROOT, 'rev-parse', 'HEAD')
    gitinfo.ensure_tag('run-x', head, 'msg')
    gitinfo.ensure_tag('run-x', head, 'msg again')
    assert git(config.REPO_ROOT, 'rev-parse', 'run-x^{commit}') == head
    assert git(config.REPO_ROOT, 'cat-file', '-t', 'run-x') == 'tag'


def test_commit_info_and_repo_slug(monkeypatch):
    """commit_info reads subject/author/date; repo_slug parses GitHub remotes and honours GITHUB_REPOSITORY."""
    info = gitinfo.commit_info('HEAD')
    assert info['subject'] == 'first' and info['author'] == 'Tests' and info['date']
    assert gitinfo.repo_slug() is None
    git(config.REPO_ROOT, 'remote', 'add', 'origin', 'git@github.com:owner/name.git')
    assert gitinfo.repo_slug() == 'owner/name'
    monkeypatch.setenv('GITHUB_REPOSITORY', 'a/b')
    assert gitinfo.repo_slug() == 'a/b'


def _tag_run(run_id, version):
    """Commit a version of src/app.py, tag it as a run snapshot, return the commit."""
    repo = config.REPO_ROOT
    (repo / 'src' / 'app.py').write_text(f'VERSION = {version}\n')
    git(repo, 'commit', '-qam', f'version {version}')
    sha = git(repo, 'rev-parse', 'HEAD')
    gitinfo.ensure_tag(f'run-{run_id}', sha, 'snapshot')
    return sha


def test_restore_then_undo_round_trip():
    """Restore puts files back to the run's version with a new commit and a backup tag; Undo returns to the backup."""
    repo = config.REPO_ROOT
    _tag_run('old', 2)
    (repo / 'src' / 'app.py').write_text('VERSION = 3\n')
    (repo / 'src' / 'extra.py').write_text('X = 1\n')
    git(repo, 'add', '-A')
    git(repo, 'commit', '-qm', 'version 3')
    (repo / 'src' / 'app.py').write_text('VERSION = 4  # uncommitted\n')
    n_commits = int(git(repo, 'rev-list', '--count', 'HEAD'))

    out = restore.restore_run('old')
    assert out['changed'] and out['backup_tag'].startswith('backup-')
    assert (repo / 'src' / 'app.py').read_text() == 'VERSION = 2\n'
    assert not (repo / 'src' / 'extra.py').exists()
    assert int(git(repo, 'rev-list', '--count', 'HEAD')) == n_commits + 1
    assert 'Restore code to run old' in git(repo, 'log', '-1', '--format=%s')
    assert git(repo, 'status', '--porcelain') == ''

    back = restore.undo(out['backup_tag'])
    assert back['changed']
    assert (repo / 'src' / 'app.py').read_text() == 'VERSION = 4  # uncommitted\n'
    assert (repo / 'src' / 'extra.py').read_text() == 'X = 1\n'


def test_restore_noop_when_identical():
    """Restoring the version you're already on changes nothing."""
    _tag_run('same', 5)
    out = restore.restore_run('same')
    assert out['changed'] is False and 'already identical' in out['message']


def test_restore_refuses_detached_head_and_unknown_runs():
    """Plain-English errors for a detached HEAD, an unknown run and a non-backup undo."""
    sha = _tag_run('r1', 6)
    with pytest.raises(restore.RestoreError, match="Couldn't find"):
        restore.restore_run('does-not-exist')
    with pytest.raises(restore.RestoreError, match='backup tags'):
        restore.undo('run-r1')
    git(config.REPO_ROOT, 'checkout', '-q', sha)
    with pytest.raises(restore.RestoreError, match='detached'):
        restore.restore_run('r1')


def test_status_reports_dirty():
    """status() shows branch, head and uncommitted edits."""
    assert restore.status()['dirty'] is False and restore.status()['branch'] == 'main'
    (config.REPO_ROOT / 'src' / 'app.py').write_text('changed\n')
    assert restore.status()['dirty'] is True
