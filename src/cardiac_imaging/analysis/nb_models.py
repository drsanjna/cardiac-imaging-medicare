"""Multivariable negative binomial (NB2) models of state CTA counts vs physician density, adjusted for age and sex.

log(CTA count)_s = β0 + β1·density + β2·meanAge + β3·%female + log(FFS_s)
exp(β1) = density IRR. Covariates z-scored; density in natural units.
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from statsmodels.discrete.discrete_model import NegativeBinomial
from statsmodels.stats.outliers_influence import variance_inflation_factor

from ..audit import log_filter

Z95 = stats.norm.ppf(0.975)


def fit_nb_design(X, counts, offset):
    """Fit NB2 with Poisson start values; returns (result, alpha, Poisson dispersion)."""
    pois = sm.GLM(counts, X, family=sm.families.Poisson(), offset=offset).fit()
    sp = np.append(pois.params, 1.0)
    res = None
    for method, kw in [('nm', dict(maxiter=8000)), ('lbfgs', dict(maxiter=3000))]:
        cand = NegativeBinomial(counts, X, offset=offset).fit(
                   start_params=sp, method=method, disp=0, **kw)
        if cand.mle_retvals.get('converged', False):
            res = cand; break
        res = res or cand
    return res, float(res.params[-1]), pois.pearson_chi2 / pois.df_resid


def irr_at(res, idx):
    """(IRR, CI low, CI high, p) for coefficient idx."""
    b, se, p = res.params[idx], res.bse[idx], res.pvalues[idx]
    return np.exp(b), np.exp(b - Z95 * se), np.exp(b + Z95 * se), p


def density_partial_curve(res, x_grid, ncoef, per=1000):
    """Predicted rate per `per` beneficiaries across x_grid, other covariates at their mean (0 when z-scored)."""
    rows = np.zeros((len(x_grid), ncoef)); rows[:, 0] = 1.0; rows[:, 1] = x_grid
    beta = np.asarray(res.params)[:ncoef]
    cov = np.asarray(res.cov_params())[:ncoef, :ncoef]
    lp = rows @ beta
    se = np.sqrt(np.einsum('ij,jk,ik->i', rows, cov, rows))
    return np.exp(lp) * per, np.exp(lp - Z95 * se) * per, np.exp(lp + Z95 * se) * per


def vif_table(Xz_df):
    Xc = sm.add_constant(Xz_df.values)
    return {col: variance_inflation_factor(Xc, i + 1)
            for i, col in enumerate(Xz_df.columns)}


def fit_density_models(df, density_col, density_label):
    """Fit unadjusted and age/sex-adjusted NB2 models for one density measure.

    Returns a dict with the modeled DataFrame (`d`), both fits, IRRs, VIFs and NB alphas.
    """
    d = df.dropna(subset=['mean_age', 'pct_female']).copy()
    log_filter(f"{density_label}: states with demographics", len(df), len(d), unit='states',
               dropped_items=set(df['state']) - set(d['state']))
    if len(d) < 10:
        raise ValueError(f"Only {len(d)} states merged demographics for '{density_label}'.")
    counts = d['total_services'].values.astype(float)
    offset = np.log(d['ffs_enrollment'].values.astype(float))
    dens = d[density_col].values.astype(float)

    for c in ['mean_age', 'pct_female']:
        d[c + '_z'] = (d[c] - d[c].mean()) / d[c].std(ddof=0)

    res_un, a_un, disp_un = fit_nb_design(sm.add_constant(dens), counts, offset)
    Xz = d[[density_col, 'mean_age_z', 'pct_female_z']].copy()
    res_adj, a_adj, _ = fit_nb_design(sm.add_constant(Xz.values), counts, offset)

    return dict(
        d=d, density_col=density_col, density_label=density_label,
        res_un=res_un, res_adj=res_adj, ncoef_adj=Xz.shape[1] + 1,
        irr_un=irr_at(res_un, 1), irr_adj=irr_at(res_adj, 1),
        vifs=vif_table(Xz.rename(columns={density_col: 'density'})),
        alpha_un=a_un, alpha_adj=a_adj, dispersion_un=disp_un,
    )


def print_model_report(fit, title, n_physicians, year):
    """Console table of adjusted-model IRRs plus unadjusted vs adjusted density IRR."""
    n_states = len(fit['d'])
    res_adj, irr_un, irr_adj = fit['res_adj'], fit['irr_un'], fit['irr_adj']
    print("=" * 76)
    print(f"{title}   (n = {n_states} states, {n_physicians:,} unique physicians, {year})")
    print("Outcome = raw CTA counts | offset = log(FFS) | NB2 | covariates z-scored")
    print("-" * 76)
    names = ['intercept', fit['density_label'], 'mean age (+1 SD)', '% female (+1 SD)']
    print(f"{'Adjusted-model term':<24}{'IRR':>9}{'95% CI':>20}{'p':>10}")
    for i, nm in enumerate(names):
        irr, lo, hi, p = irr_at(res_adj, i)
        pstr = "<0.001" if p < 0.001 else f"{p:.3f}"
        if i == 0:
            print(f"{nm:<24}{'—':>9}{'(baseline)':>20}{'':>10}")
        else:
            print(f"{nm:<24}{irr:>9.4f}{f'{lo:.4f}-{hi:.4f}':>20}{pstr:>10}")
    print("-" * 76)
    print(f"DENSITY IRR — unadjusted: {irr_un[0]:.4f} ({irr_un[1]:.4f}-{irr_un[2]:.4f})")
    print(f"DENSITY IRR — adjusted  : {irr_adj[0]:.4f} ({irr_adj[1]:.4f}-{irr_adj[2]:.4f})")
    print(f"VIF: " + ", ".join(f"{k}={v:.2f}" for k, v in fit['vifs'].items()) + "   (>5 = concern)")
    print(f"NB alpha: unadj {fit['alpha_un']:.3f} / adj {fit['alpha_adj']:.3f} | "
          f"Poisson dispersion ~{fit['dispersion_un']:.0f}")
    print("=" * 76)


def results_table(results, names):
    """One row per density model: states, physicians, unadjusted and adjusted IRR with 95% CI and p."""
    rows = []
    for key, r in results.items():
        (u, ul, uh, up), (a, al, ah, ap) = r['irr_un'], r['irr_adj']
        rows.append({'model': names.get(key, key), 'states': r['n'], 'physicians': r['n_physicians'],
                     'IRR unadjusted': u, 'CI low (unadj)': ul, 'CI high (unadj)': uh, 'p (unadj)': up,
                     'IRR adjusted': a, 'CI low (adj)': al, 'CI high (adj)': ah, 'p (adj)': ap})
    return pd.DataFrame(rows).set_index('model')
