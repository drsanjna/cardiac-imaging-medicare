"""Change-on-change, 2018 → 2023: did states that gained radiologists/cardiologists also gain CTA use?

Primary (as plotted): Δ CTA rate per 1,000 FFS ~ Δ workforce per 100,000 FFS, OLS with HC3 robust SEs.
Both axes share the FFS denominator, so a state losing FFS enrollees to Medicare Advantage rises on both axes
mechanically. The count model avoids that: Δlog(CTA services) ~ Δlog(physicians) + Δlog(FFS enrollment).
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

from ..audit import log_filter

Z95 = stats.norm.ppf(0.975)
KEEP = ['state', 'wf_unique_npis', 'wf_npis_per_100k', 'total_services', 'rate_per_1000', 'ffs_enrollment']


def change_frame(wf_end, wf_base, end_year, base_year):
    """One row per state with both years' workforce, CTA and FFS values and their changes (states in both years)."""
    end = wf_end[KEEP].rename(columns={c: f'{c}_{end_year}' for c in KEEP if c != 'state'})
    base = wf_base[KEEP].rename(columns={c: f'{c}_{base_year}' for c in KEEP if c != 'state'})
    df = end.merge(base, on='state', how='inner')
    log_filter(f'change {base_year}→{end_year}: states present in both years', len(end), len(df), unit='states',
               dropped_items=set(end['state']) - set(df['state']))
    e, b = end_year, base_year
    df['d_density'] = df[f'wf_npis_per_100k_{e}'] - df[f'wf_npis_per_100k_{b}']
    df['d_rate'] = df[f'rate_per_1000_{e}'] - df[f'rate_per_1000_{b}']
    df['pct_physicians'] = (df[f'wf_unique_npis_{e}'] / df[f'wf_unique_npis_{b}'] - 1) * 100
    df['pct_ffs'] = (df[f'ffs_enrollment_{e}'] / df[f'ffs_enrollment_{b}'] - 1) * 100
    return df.sort_values('d_density', ascending=False).reset_index(drop=True)


def _ols(y, X):
    """OLS with HC3 robust standard errors."""
    return sm.OLS(y, sm.add_constant(X)).fit(cov_type='HC3')


def _coef(res, i):
    """(estimate, CI low, CI high, p) for coefficient i of a fitted OLS."""
    b, se = res.params[i], res.bse[i]
    return float(b), float(b - Z95 * se), float(b + Z95 * se), float(res.pvalues[i])


def fit_change_models(df, end_year, base_year, exclude=('DC', 'MN')):
    """Primary rate model (all states and without `exclude`), Spearman ρ, and the count model; returns a dict."""
    e, b = end_year, base_year
    out = {}
    for name, d in [('all states', df), (f"without {', '.join(exclude)}", df[~df['state'].isin(exclude)])]:
        res = _ols(d['d_rate'].values, d['d_density'].values)
        rho, rho_p = stats.spearmanr(d['d_density'], d['d_rate'])
        out[name] = dict(n=len(d), slope=_coef(res, 1), r2=float(res.rsquared), rho=float(rho), rho_p=float(rho_p),
                         res=res)
    pos = df[(df[f'total_services_{e}'] > 0) & (df[f'total_services_{b}'] > 0)]
    log_filter('change count model: states with CTA in both years', len(df), len(pos), unit='states',
               dropped_items=set(df['state']) - set(pos['state']))
    X = np.column_stack([np.log(pos[f'wf_unique_npis_{e}'] / pos[f'wf_unique_npis_{b}']),
                         np.log(pos[f'ffs_enrollment_{e}'] / pos[f'ffs_enrollment_{b}'])])
    res = _ols(np.log(pos[f'total_services_{e}'] / pos[f'total_services_{b}']).values, X)
    out['count model'] = dict(n=len(pos), elasticity=_coef(res, 1), ffs_coef=_coef(res, 2), r2=float(res.rsquared),
                              res=res)
    return out


def change_results_table(fits):
    """Tidy table of the change models (one row per model)."""
    rows = []
    for name in [k for k in fits if k != 'count model']:
        f = fits[name]
        s, lo, hi, p = f['slope']
        rows.append({'model': f'Δ rate ~ Δ density ({name})', 'states': f['n'],
                     'estimate': s, 'CI low': lo, 'CI high': hi, 'p': p, 'R2': f['r2'],
                     'Spearman rho': f['rho'], 'Spearman p': f['rho_p'],
                     'meaning': 'Δ CTA per 1,000 FFS per +1 physician per 100,000 FFS'})
    c = fits['count model']
    s, lo, hi, p = c['elasticity']
    rows.append({'model': 'Δlog CTA ~ Δlog physicians + Δlog FFS', 'states': c['n'], 'estimate': s,
                 'CI low': lo, 'CI high': hi, 'p': p, 'R2': c['r2'], 'Spearman rho': np.nan, 'Spearman p': np.nan,
                 'meaning': '% change in CTA services per 1% change in physicians, FFS change held fixed'})
    return pd.DataFrame(rows).set_index('model')
