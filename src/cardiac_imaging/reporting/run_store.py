"""Per-run output folder RUNS_DIR/<timestamp>_<commit>/: figures/, tables/, console.log, manifest.json, plus a code-snapshot tag."""
import hashlib
import json
import platform
import re
import sys
from datetime import datetime
from importlib import metadata
from pathlib import Path

from .. import audit, config, gitinfo

PACKAGES = ('duckdb', 'pandas', 'numpy', 'scipy', 'statsmodels', 'matplotlib', 'plotly', 'kaleido')


class _Tee:
    """Write to the real stream and the run's console.log at the same time."""

    def __init__(self, stream, log):
        """Remember the real stream and the log file."""
        self.stream, self.log = stream, log

    def write(self, s):
        """Write text to both the real stream and the log."""
        self.stream.write(s)
        self.log.write(s)
        return len(s)

    def flush(self):
        """Flush both streams."""
        self.stream.flush()
        self.log.flush()

    def __getattr__(self, name):
        """Delegate any other attribute to the real stream."""
        return getattr(self.stream, name)


def _link(link, target):
    """Create/refresh symlink `link` → `target` (no-op on failure; links are a convenience)."""
    try:
        if link.is_symlink():
            link.unlink()
        if not link.exists():
            link.symlink_to(target)
    except OSError:
        pass


def data_fingerprint(parquet_dir=None):
    """Names, sizes and mtimes of the Parquet inputs, hashed — changes whenever the input data changes."""
    files = sorted(Path(parquet_dir or config.PARQUET_DIR).glob('*.parquet'))
    sig = [(f.name, f.stat().st_size, int(f.stat().st_mtime)) for f in files]
    return dict(fingerprint=hashlib.sha1(json.dumps(sig).encode()).hexdigest()[:12],
                parquet_files=len(files), parquet_bytes=sum(s for _, s, _ in sig))


def package_versions():
    """Installed versions of Python and the key analysis packages."""
    out = {'python': platform.python_version()}
    for p in PACKAGES:
        try:
            out[p] = metadata.version(p)
        except metadata.PackageNotFoundError:
            pass
    return out


def tag_for(run_id):
    """Git tag name holding the code snapshot of a run."""
    return f'run-{run_id}'


class Run:
    """Context for one pipeline run: snapshots the code, redirects figures into the run folder, tees the console."""

    def __init__(self, label=None):
        """Create the run folder, snapshot + tag the code, start teeing the console."""
        self.started = datetime.now().astimezone()
        head = gitinfo.git('rev-parse', 'HEAD')
        dirty = bool(gitinfo.git('status', '--porcelain', '--untracked-files=all'))
        sha = head[:7] or 'nogit'
        slug = f"_{re.sub(r'[^A-Za-z0-9]+', '-', label).strip('-')}" if label else ''
        self.id = f"{self.started:%Y-%m-%d_%H%M%S}_{sha}{'-dirty' if dirty else ''}{slug}"
        self.dir = config.RUNS_DIR / self.id
        (self.dir / 'figures').mkdir(parents=True)
        (self.dir / 'tables').mkdir()
        if config.RUNS_DIR.resolve() != (config.REPO_ROOT / 'runs').resolve():
            _link(config.REPO_ROOT / 'runs', config.RUNS_DIR)

        code = dict(branch=gitinfo.git('rev-parse', '--abbrev-ref', 'HEAD'), head=head, dirty=dirty,
                    repo=gitinfo.repo_slug(), tag=tag_for(self.id), exact=True, **gitinfo.commit_info(head))
        try:   # freeze the exact code used (incl. uncommitted edits) before anything runs
            snap, _ = gitinfo.snapshot_commit(f"Code snapshot for run {self.id}\n\nWorking tree as of "
                                              f"{self.started.isoformat(timespec='seconds')} (branch {code['branch']}).")
            gitinfo.ensure_tag(code['tag'], snap, f"Code used for run {self.id}")
            code['snapshot'] = snap
        except Exception as e:
            code.update(snapshot=None, exact=False, snapshot_error=str(e))
        self.manifest = dict(
            run_id=self.id, label=label, status='running', started=self.started.isoformat(timespec='seconds'),
            code=code, database=config.DATABASE, data=data_fingerprint(), versions=package_versions(),
            save_tiff=config.SAVE_TIFF, steps=[], headline={}, tables={}, published=None,
        )
        self._saved_output_dir = config.OUTPUT_DIR
        config.OUTPUT_DIR = self.dir / 'figures'
        audit.FILTER_LOG.clear()
        self._log = open(self.dir / 'console.log', 'w', encoding='utf-8', buffering=1)   # line-buffered: tail -f works
        self._streams = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = _Tee(sys.stdout, self._log), _Tee(sys.stderr, self._log)
        print(f"Run {self.id}\n  folder: {self.dir}\n  code snapshot: tag {code['tag']} → "
              f"{(code.get('snapshot') or 'FAILED')[:12]}{' (includes uncommitted changes)' if dirty else ''}")

    def log_step(self, name, seconds, ok):
        """Record one pipeline step's duration and status."""
        self.manifest['steps'].append(dict(step=name, seconds=round(seconds, 1), status='ok' if ok else 'failed'))

    def save_tables(self, tables):
        """Write each DataFrame in `tables` to tables/<name>.csv."""
        for name, df in tables.items():
            df.to_csv(self.dir / 'tables' / f'{name}.csv')
            self.manifest['tables'][name] = f'tables/{name}.csv'

    def finish(self, ctx, error=None, publish=None):
        """Restore stdout, write manifest.json, build gallery + PDF, publish to GitHub (if enabled), refresh the index."""
        sys.stdout, sys.stderr = self._streams
        self._log.close()
        config.OUTPUT_DIR = self._saved_output_dir
        m = self.manifest
        finished = datetime.now().astimezone()
        m['status'] = 'failed' if error else 'ok'
        m['finished'] = finished.isoformat(timespec='seconds')
        m['seconds'] = round((finished - self.started).total_seconds(), 1)
        if error:
            m['error'] = dict(step=error[0], type=type(error[1]).__name__, message=str(error[1]))
        m['headline'] = ctx.get('headline', {})
        m['data'].update(ctx.get('data', {}))
        try:
            self.save_tables({**ctx.get('tables', {}), **_filter_table()})
        except Exception as e:
            print(f"  Could not save tables: {e}")
        m['figures'] = sorted(p.name for p in (self.dir / 'figures').glob('*.png'))
        m['bytes'] = sum(p.stat().st_size for p in self.dir.rglob('*') if p.is_file())
        from . import gallery, index, insights, publish as pub   # imported here: they read manifests this module writes
        _try(lambda: insights.annotate(self.dir, m, previous_run(m['run_id'])), 'summary')
        write_manifest(self.dir, m)

        _try(lambda: gallery.build(self.dir), 'gallery/PDF')
        if config.PUBLISH_RUNS if publish is None else publish:
            _try(lambda: pub.publish_run(self.dir), 'GitHub release')
        _try(lambda: index.build(config.RUNS_DIR), 'run index')
        _link(config.RUNS_DIR / 'latest', Path(self.id))
        m = read_manifest(self.dir)
        print(f"\nRun {m['status'].upper()} in {m['seconds']:.0f}s — {len(m['figures'])} figures, {m['bytes'] / 1e6:.0f} MB")
        print(f"  gallery : {self.dir / 'gallery.html'}")
        print(f"  all runs: {config.RUNS_DIR / 'index.html'}")
        print(f"  code    : git checkout {m['code']['tag']}")
        if m.get('published'):
            print(f"  GitHub  : {m['published']['release_url']} (pushed {m['published']['at']})")


def _try(fn, what):
    """Run a reporting step, printing (not raising) any failure."""
    try:
        fn()
    except Exception as e:
        print(f"  Could not build {what}: {type(e).__name__}: {e}")


def _filter_table():
    """The current run's filter log as a DataFrame (empty dict if nothing was filtered)."""
    import pandas as pd
    return {'filter_log': pd.DataFrame(audit.FILTER_LOG).set_index('filter')} if audit.FILTER_LOG else {}


def read_manifest(run_dir):
    """Load a run folder's manifest.json."""
    return json.loads((Path(run_dir) / 'manifest.json').read_text())


def write_manifest(run_dir, m):
    """Write a run folder's manifest.json."""
    (Path(run_dir) / 'manifest.json').write_text(json.dumps(m, indent=2, default=str))


LABELS = ('success', 'failure', 'needs_review', 'archived')   # your verdict on a run; separate from its technical status


def set_label(run_id, label, note='', runs_dir=None):
    """Record your verdict on a run (success / failure / needs_review / archived, or None to clear) in its manifest."""
    from datetime import datetime
    if label is not None and label not in LABELS:
        raise ValueError(f"label must be one of {LABELS} or None")
    run_dir = Path(runs_dir or config.RUNS_DIR) / run_id
    if not (run_dir / 'manifest.json').exists():
        raise FileNotFoundError(f"Run {run_id} isn't on this Mac — download it first.")
    m = read_manifest(run_dir)
    m['review'] = None if label is None else dict(label=label, note=note,
                                                  at=datetime.now().astimezone().isoformat(timespec='seconds'))
    write_manifest(run_dir, m)
    return m


def previous_run(run_id, runs_dir=None):
    """Manifest of the most recent run started before `run_id` (None if it is the first)."""
    return next((r for r in list_runs(runs_dir) if r['run_id'] < run_id), None)


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
