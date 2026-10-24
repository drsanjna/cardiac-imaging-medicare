"""Per-run output folder RUNS_DIR/<timestamp>_<commit>/: figures/, tables/, console.log and manifest.json."""
import json
import platform
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from .. import audit, config


class _Tee:
    """Write to the real stream and the run's console.log at the same time."""

    def __init__(self, stream, log):
        self.stream, self.log = stream, log

    def write(self, s):
        self.stream.write(s)
        self.log.write(s)
        return len(s)

    def flush(self):
        self.stream.flush()
        self.log.flush()

    def __getattr__(self, name):
        return getattr(self.stream, name)


def _git(*args):
    try:
        return subprocess.check_output(['git', *args], cwd=config.REPO_ROOT, text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ''


def _link(link, target):
    """Create/refresh symlink `link` → `target` (no-op on failure; links are a convenience)."""
    try:
        if link.is_symlink():
            link.unlink()
        if not link.exists():
            link.symlink_to(target)
    except OSError:
        pass


class Run:
    """Context for one pipeline run: redirects figures into the run folder and tees the console into it."""

    def __init__(self, label=None):
        sha = _git('rev-parse', '--short', 'HEAD') or 'nogit'
        dirty = bool(_git('status', '--porcelain', '--', 'src', 'scripts', 'notebooks'))
        slug = f"_{re.sub(r'[^A-Za-z0-9]+', '-', label).strip('-')}" if label else ''
        self.started = datetime.now()
        self.id = f"{self.started:%Y-%m-%d_%H%M%S}_{sha}{'-dirty' if dirty else ''}{slug}"
        self.dir = config.RUNS_DIR / self.id
        (self.dir / 'figures').mkdir(parents=True)
        (self.dir / 'tables').mkdir()
        if config.RUNS_DIR.resolve() != (config.REPO_ROOT / 'runs').resolve():
            _link(config.REPO_ROOT / 'runs', config.RUNS_DIR)
        self.manifest = dict(
            run_id=self.id, label=label, status='running', started=self.started.isoformat(timespec='seconds'),
            commit=_git('rev-parse', 'HEAD'), commit_short=sha, branch=_git('rev-parse', '--abbrev-ref', 'HEAD'),
            dirty=dirty, remote=_git('remote', 'get-url', 'origin'), database=config.DATABASE,
            python=platform.python_version(), save_tiff=config.SAVE_TIFF, steps=[], headline={}, tables={},
        )
        self._saved_output_dir = config.OUTPUT_DIR
        config.OUTPUT_DIR = self.dir / 'figures'
        audit.FILTER_LOG.clear()
        self._log = open(self.dir / 'console.log', 'w', encoding='utf-8', buffering=1)   # line-buffered: tail -f works
        self._streams = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = _Tee(sys.stdout, self._log), _Tee(sys.stderr, self._log)
        print(f"Run {self.id}\n  folder: {self.dir}")

    def log_step(self, name, seconds, ok):
        self.manifest['steps'].append(dict(step=name, seconds=round(seconds, 1), status='ok' if ok else 'failed'))

    def save_tables(self, tables):
        """Write each DataFrame in `tables` to tables/<name>.csv."""
        for name, df in tables.items():
            df.to_csv(self.dir / 'tables' / f'{name}.csv')
            self.manifest['tables'][name] = f'tables/{name}.csv'

    def finish(self, ctx, error=None):
        """Restore stdout, write manifest.json, then build the gallery, PDF, run index and `latest` link."""
        sys.stdout, sys.stderr = self._streams
        self._log.close()
        config.OUTPUT_DIR = self._saved_output_dir
        m = self.manifest
        m['status'] = 'failed' if error else 'ok'
        m['finished'] = datetime.now().isoformat(timespec='seconds')
        m['seconds'] = round((datetime.now() - self.started).total_seconds(), 1)
        if error:
            m['error'] = dict(step=error[0], type=type(error[1]).__name__, message=str(error[1]))
        m['headline'] = ctx.get('headline', {})
        try:
            self.save_tables({**ctx.get('tables', {}), **_filter_table()})
        except Exception as e:
            print(f"  Could not save tables: {e}")
        m['figures'] = sorted(p.name for p in (self.dir / 'figures').glob('*.png'))
        m['bytes'] = sum(p.stat().st_size for p in self.dir.rglob('*') if p.is_file())
        (self.dir / 'manifest.json').write_text(json.dumps(m, indent=2, default=str))

        from . import gallery, index   # imported here: they read manifests this module writes
        for build, what in [(lambda: gallery.build(self.dir), 'gallery/PDF'), (lambda: index.build(config.RUNS_DIR), 'run index')]:
            try:
                build()
            except Exception as e:
                print(f"  Could not build {what}: {type(e).__name__}: {e}")
        _link(config.RUNS_DIR / 'latest', Path(self.id))
        print(f"\nRun {m['status'].upper()} in {m['seconds']:.0f}s — {len(m['figures'])} figures, {m['bytes'] / 1e6:.0f} MB")
        print(f"  gallery : {self.dir / 'gallery.html'}")
        print(f"  all runs: {config.RUNS_DIR / 'index.html'}")


def _filter_table():
    import pandas as pd
    return {'filter_log': pd.DataFrame(audit.FILTER_LOG).set_index('filter')} if audit.FILTER_LOG else {}


def list_runs(runs_dir=None):
    """Manifests of every run in runs_dir, newest first."""
    runs_dir = Path(runs_dir or config.RUNS_DIR)
    out = []
    for f in sorted(runs_dir.glob('*/manifest.json'), reverse=True):
        if f.parent.is_symlink():
            continue
        try:
            out.append(json.loads(f.read_text()))
        except (OSError, ValueError):
            continue
    return out
