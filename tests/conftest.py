"""Shared fixtures: every test runs isolated (temp repo/run/conversation dirs, GitHub uploads off, no real tags)."""
import os
import subprocess
import sys
from pathlib import Path

# Inside a git hook, git exports GIT_INDEX_FILE / GIT_DIR / … pointing at the real repo. Tests run git in throwaway
# repos, so drop every such variable first — otherwise they could read or write the real repo's index.
for _k in [k for k in os.environ if k.startswith('GIT_')]:
    del os.environ[_k]

import matplotlib
import pytest

matplotlib.use('Agg')
sys.path.insert(0, str(Path(__file__).parent))

import synthetic  # noqa: E402
from cardiac_imaging import config  # noqa: E402

REAL_REPO = Path(__file__).resolve().parents[1]
REAL_DB = Path(config.DATABASE)


def git(repo, *args):
    """Run git in `repo` and return stdout."""
    return subprocess.check_output(['git', *args], cwd=repo, text=True).strip()


def make_repo(path):
    """A throwaway git repo with one commit (src/app.py) and a test identity."""
    path.mkdir(parents=True, exist_ok=True)
    git(path, 'init', '-q', '-b', 'main')
    git(path, 'config', 'user.email', 'tests@example.com')
    git(path, 'config', 'user.name', 'Tests')
    git(path, 'config', 'commit.gpgsign', 'false')
    git(path, 'config', 'core.hooksPath', '/dev/null')
    (path / 'src').mkdir(exist_ok=True)
    (path / 'src' / 'app.py').write_text('VERSION = 1\n')
    (path / '.gitignore').write_text('runs\n')
    git(path, 'add', '-A')
    git(path, 'commit', '-q', '-m', 'first')
    return path


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Point every writable location at tmp dirs and disable GitHub side effects for the duration of a test."""
    repo = make_repo(tmp_path / 'repo')
    monkeypatch.setattr(config, 'REPO_ROOT', repo)
    monkeypatch.setattr(config, 'RUNS_DIR', tmp_path / 'runs')
    monkeypatch.setattr(config, 'OUTPUT_DIR', tmp_path / 'outputs')
    monkeypatch.setattr(config, 'LOG_DIR', tmp_path / 'logs')
    monkeypatch.setattr(config, 'CONVERSATIONS_DIR', tmp_path / 'conversations')
    monkeypatch.setattr(config, 'PUBLISH_RUNS', False)
    monkeypatch.setattr(config, 'SAVE_TIFF', False)
    monkeypatch.setattr(config, 'CHAT_BACKEND', 'handoff')
    monkeypatch.setenv('CARDIAC_REPORT_ERRORS', '0')
    monkeypatch.delenv('GITHUB_REPOSITORY', raising=False)
    yield tmp_path


@pytest.fixture(scope='session')
def synthetic_db(tmp_path_factory):
    """Path to a synthetic cms.duckdb shared by all tests (read-only use)."""
    return synthetic.build(tmp_path_factory.mktemp('db') / 'cms.duckdb')


@pytest.fixture
def con(synthetic_db):
    """Read-only connection to the synthetic database."""
    import duckdb
    c = duckdb.connect(str(synthetic_db), read_only=True)
    yield c
    c.close()


@pytest.fixture
def stub_plotly(monkeypatch):
    """Replace plotly's PNG export (needs Chrome/kaleido) with a tiny PNG so map figures still produce files."""
    import plotly.graph_objects as go
    from PIL import Image

    def write_image(self, path, width=None, height=None, scale=1, **kw):
        """Write a small blank PNG of the requested aspect ratio."""
        Image.new('RGB', (max(1, int((width or 300) / 10)), max(1, int((height or 200) / 10))), 'white').save(path)
    monkeypatch.setattr(go.Figure, 'write_image', write_image)


@pytest.fixture(scope='session')
def pipeline_run(tmp_path_factory, synthetic_db):
    """One full recorded pipeline run on synthetic data (shared; inspect its outputs, don't modify them)."""
    import plotly.graph_objects as go
    from PIL import Image
    from cardiac_imaging import pipeline

    base = tmp_path_factory.mktemp('e2e')
    mp = pytest.MonkeyPatch()
    repo = make_repo(base / 'repo')
    for k, v in dict(REPO_ROOT=repo, RUNS_DIR=base / 'runs', OUTPUT_DIR=base / 'out', LOG_DIR=base / 'logs',
                     PUBLISH_RUNS=False, SAVE_TIFF=False).items():
        mp.setattr(config, k, v)
    mp.setenv('CARDIAC_REPORT_ERRORS', '0')
    mp.setattr(go.Figure, 'write_image',
               lambda self, path, width=None, height=None, scale=1, **kw: Image.new('RGB', (150, 43), 'white').save(path))
    ctx = pipeline.run_all(database=str(synthetic_db), label='synthetic')
    run_dir = ctx['run_dir']
    mp.undo()
    return dict(ctx=ctx, run_dir=run_dir, repo=repo, runs_dir=base / 'runs')
