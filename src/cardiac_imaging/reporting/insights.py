"""Plain-English run summaries: key findings from a run's tables, and what changed (and its impact) vs the previous run."""
from pathlib import Path

import pandas as pd

from .. import gitinfo

# Findings compared between runs; a change bigger than the tolerance counts as an impact.
TOLERANCE = {'irr': 0.0005, 'pct': 0.05}


def _read(run_dir, name):
    """A saved results table, or None when the run didn't produce it."""
    p = Path(run_dir) / 'tables' / f'{name}.csv'
    return pd.read_csv(p, index_col=0) if p.exists() else None


def findings(run_dir):
    """Key numbers from a run's tables: utilization change per modality, advanced share, IRRs, CTA reader shares."""
    f = {}
    cs = _read(run_dir, 'change_summary')
    if cs is not None:
        f['rate_change_pct'] = {m: round(float(v), 2) for m, v in cs['rate_pct'].items()}
        f['enrollment_change_pct'] = round(float(cs['enrollment_pct'].iloc[0]), 2)
    ms = _read(run_dir, 'national_market_share')
    if ms is not None and 'Advanced' in ms:
        f['advanced_share_pct'] = {str(y): round(float(v), 2) for y, v in ms['Advanced'].items()}
    nb = _read(run_dir, 'nb_density_models')
    if nb is not None:
        f['irr_adjusted'] = {m: dict(irr=round(float(r['IRR adjusted']), 4), lo=round(float(r['CI low (adj)']), 4),
                                     hi=round(float(r['CI high (adj)']), 4), p=float(r['p (adj)']))
                             for m, r in nb.iterrows()}
    t1 = _read(run_dir, 'table1_specialty_distribution')
    if t1 is not None and 'Cardiac CTA' in t1.index:
        f['cta_reader_share_pct'] = dict(radiology=round(float(t1.loc['Cardiac CTA', 'Radiology %']), 1),
                                         cardiology=round(float(t1.loc['Cardiac CTA', 'Cardiology %']), 1))
    return f


def _pct(v):
    """'+199%' / '−34%' style percentage."""
    return f"{'+' if v >= 0 else '−'}{abs(v):.0f}%"


def english_summary(m):
    """Two to four plain-English sentences describing a run's outcome and main results."""
    f = m.get('findings') or {}
    if m.get('status') == 'failed':
        e = m.get('error') or {}
        done = sum(1 for s in m.get('steps', []) if s.get('status') == 'ok')
        return (f"This run stopped at the “{e.get('step', '?')}” step ({e.get('type', 'error')}) after {done} steps completed, "
                "so its results are incomplete. Restore an earlier version or open the log to see why.")
    parts = []
    rc = f.get('rate_change_pct')
    if rc:
        up = sorted(((v, k) for k, v in rc.items() if v > 0), reverse=True)
        down = sorted((v, k) for k, v in rc.items() if v < 0)
        s = 'From 2018 to 2023, use per 1,000 fee-for-service beneficiaries '
        if up:
            s += 'rose for ' + ', '.join(f'{k} ({_pct(v)})' for v, k in up)
        if down:
            s += ('' if not up else ' and ') + 'fell for ' + ', '.join(f'{k} ({_pct(v)})' for v, k in down)
        parts.append(s + '.')
    adv = f.get('advanced_share_pct')
    if adv:
        ys = sorted(adv)
        parts.append(f"Advanced imaging (CTA, MRI, PET) grew from {adv[ys[0]]:.1f}% to {adv[ys[-1]]:.1f}% of all cardiac imaging.")
    irr = f.get('irr_adjusted', {}).get('All CTA-billing providers')
    if irr:
        sig = 'statistically significant' if irr['p'] < 0.05 else 'not statistically significant'
        parts.append(f"States with more CTA-reading physicians used more CTA: each additional reader per 100,000 beneficiaries "
                     f"was linked to {(irr['irr'] - 1) * 100:.1f}% more CTA use after adjusting for age and sex "
                     f"(95% CI {(irr['lo'] - 1) * 100:.1f}–{(irr['hi'] - 1) * 100:.1f}%, {sig}).")
    share = f.get('cta_reader_share_pct')
    if share:
        parts.append(f"Radiologists read {share['radiology']:.0f}% of cardiac CTAs and cardiologists {share['cardiology']:.0f}%.")
    return ' '.join(parts) or 'The run completed; no summary tables were saved.'


def _changed(a, b, tol):
    """True when two numbers differ by more than `tol` (or one is missing)."""
    if a is None or b is None:
        return a is not b
    return abs(a - b) > tol


def compare(m, prev):
    """What changed since `prev` (code, data, settings) and the impact on results, as plain-English lines + structured data."""
    if not prev:
        return dict(previous=None, changes=['First recorded run — nothing to compare with.'], impact=[], code_files=[])
    changes, impact = [], []
    c, pc = m.get('code', {}), prev.get('code', {})
    a, b = pc.get('snapshot'), c.get('snapshot')
    commits, files = [], []
    if a and b and a != b:
        log = gitinfo.git('log', '--format=%s', f'{a}..{b}')
        commits = [x for x in log.splitlines() if x and not x.startswith(('Code snapshot for run', 'Merge ', 'docs: '))]
        files = [x for x in gitinfo.git('diff', '--name-only', a, b).splitlines() if x]
    if a and b and a == b:
        changes.append('Same code as the previous run.')
    elif files:
        areas = sorted({'repo root' if Path(x).parent.as_posix() == '.' else Path(x).parent.as_posix() for x in files})
        changes.append(f"Code changed in {len(files)} file{'s' * (len(files) != 1)} ({', '.join(areas)})"
                       + (f": {'; '.join(commits[:3])}" if commits else ' (uncommitted edits)') + '.')
    elif a and b:
        changes.append('Code snapshot differs, but no file contents changed.')
    else:
        changes.append('The exact code of one of these runs is unknown.')
    d, pd_ = m.get('data', {}), prev.get('data', {})
    if d.get('fingerprint') and pd_.get('fingerprint') and d['fingerprint'] != pd_['fingerprint']:
        changes.append(f"Input data changed (rows {pd_.get('claims_rows_total', 0):,} → {d.get('claims_rows_total', 0):,}).")
    else:
        changes.append('Same input data.')
    if bool(m.get('save_tiff')) != bool(prev.get('save_tiff')):
        changes.append('TIFF export ' + ('turned on.' if m.get('save_tiff') else 'turned off (PNG only).'))

    f, pf = m.get('findings') or {}, prev.get('findings') or {}
    for k, h in f.get('irr_adjusted', {}).items():
        ph = pf.get('irr_adjusted', {}).get(k)
        if ph and _changed(h['irr'], ph['irr'], TOLERANCE['irr']):
            impact.append(f"{k}: adjusted IRR {ph['irr']:.3f} → {h['irr']:.3f}.")
    for k, v in f.get('rate_change_pct', {}).items():
        pv = pf.get('rate_change_pct', {}).get(k)
        if pv is not None and _changed(v, pv, TOLERANCE['pct']):
            impact.append(f"{k}: 2018→2023 rate change {_pct(pv)} → {_pct(v)}.")
    figs, pfigs = set(m.get('figures', [])), set(prev.get('figures', []))
    if figs - pfigs:
        impact.append(f"New figures: {', '.join(sorted(figs - pfigs))}.")
    if pfigs - figs:
        impact.append(f"Figures no longer produced: {', '.join(sorted(pfigs - figs))}.")
    if m.get('status') != prev.get('status'):
        impact.append(f"Run status changed from {prev.get('status')} to {m.get('status')}.")
    if not impact:
        impact.append('No change in results — every headline number matches the previous run.')
    return dict(previous=prev.get('run_id'), changes=changes, impact=impact, code_files=files, code_commits=commits)


def annotate(run_dir, m, prev):
    """Add findings, the English summary and the comparison with `prev` to manifest `m` (in place) and return it."""
    m['findings'] = findings(run_dir)
    m['summary'] = english_summary(m)
    m['comparison'] = compare(m, prev)
    return m
