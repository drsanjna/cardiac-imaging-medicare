"""Analysis: rates, change summary, market share, state tables, Table 1, and the NB density models."""
import numpy as np
import pandas as pd
import pytest

from cardiac_imaging import audit, config
from cardiac_imaging.analysis import nb_models, rates, tables
from cardiac_imaging.loaders import claims
from cardiac_imaging.style import PROC_ORDER


def _trend():
    """Year × modality totals with simple known numbers."""
    rows = []
    for y in range(2018, 2024):
        for i, p in enumerate(PROC_ORDER):
            rows.append(dict(year=y, procedure_category=p, total_services=1000.0 * (i + 1) * (1 + 0.1 * (y - 2018))))
    return pd.DataFrame(rows)


def test_decompose_rate_per_1000():
    """Rate = services / national FFS enrollment × 1000."""
    d = rates.decompose(_trend())
    row = d[(d['year'] == 2020) & (d['procedure_category'] == 'Echo')].iloc[0]
    assert row['enrollment'] == config.MEDICARE_ENROLLMENT[2020]
    assert row['rate_per_1000'] == pytest.approx(row['total_services'] / row['enrollment'] * 1000)


def test_change_summary_matches_hand_calculation():
    """2018→2023 % change computed per modality; enrollment change identical for all."""
    cs = rates.change_summary(rates.decompose(_trend()))
    assert list(cs.index) == PROC_ORDER
    assert cs.loc['Echo', 'volume_pct'] == pytest.approx(50.0)
    enr = config.MEDICARE_ENROLLMENT
    assert cs['enrollment_pct'].nunique() == 1
    assert cs.loc['SPECT', 'enrollment_pct'] == pytest.approx((enr[2023] - enr[2018]) / enr[2018] * 100)
    expected_rate = ((1.5 / enr[2023]) / (1 / enr[2018]) - 1) * 100
    assert cs.loc['Cardiac PET', 'rate_pct'] == pytest.approx(expected_rate)


def test_print_change_summary_format(capsys):
    """Console table keeps its original layout."""
    rates.print_change_summary(rates.decompose(_trend()))
    out = capsys.readouterr().out
    assert '2018 → 2023 Change Summary' in out and 'Cardiac CTA' in out and '+50.0%' in out


def test_market_shares_sum_to_100(con):
    """Each segment's yearly shares sum to 100; national shares add Traditional + Advanced."""
    agg = claims.aggregate_segments(claims.load_detail(con))
    for seg, pct in rates.market_share_by_segment(agg).items():
        assert np.allclose(pct.sum(axis=1), 100), seg
    nat = rates.national_market_share(claims.national_trend(agg))
    assert np.allclose(nat['Traditional'] + nat['Advanced'], 100)


def test_state_rates_and_deltas():
    """State rates drop states without (or with zero) enrollment, log them, and deltas fill missing years with 0."""
    detail = pd.DataFrame(dict(state=['AL', 'AL', 'AK', 'AA', 'ZZ'], procedure_category=['Echo', 'SPECT', 'Echo', 'Echo', 'Echo'],
                               Tot_Srvcs=[100.0, 50.0, 10.0, 5.0, 1.0]))
    audit.FILTER_LOG.clear()
    r = rates.compute_state_rates(detail, {'AL': 1000, 'AK': 0, 'ZZ': None})
    assert set(r['state']) == {'AL'}
    assert r.loc[r['procedure_category'] == 'Echo', 'rate_per_1000'].iloc[0] == pytest.approx(100.0)
    assert set(audit.FILTER_LOG[-1]['dropped_items'].split(', ')) == {'AA', 'AK', 'ZZ'}
    base = r.copy()
    base['rate_per_1000'] = 50.0
    end = pd.concat([r, pd.DataFrame([dict(state='TX', procedure_category='Echo', rate_per_1000=7.0)])])
    d = rates.rate_deltas(end, base)
    assert d.loc[d['state'] == 'TX', 'rate_delta'].iloc[0] == pytest.approx(7.0)
    assert d.loc[(d['state'] == 'AL') & (d['procedure_category'] == 'Echo'), 'rate_delta'].iloc[0] == pytest.approx(50.0)


def test_state_summary_table_sorted():
    """All Cardiac = sum of modality rates, sorted descending."""
    sr = pd.DataFrame(dict(state=['A', 'A', 'B'], procedure_category=['Echo', 'SPECT', 'Echo'], rate_per_1000=[1.0, 2.0, 5.0]))
    t = rates.state_summary_table(sr)
    assert list(t.index) == ['B', 'A'] and t.loc['A', 'All Cardiac'] == pytest.approx(3.0)


def test_table1_shares(con):
    """Specialty shares sum to 100 per modality; CTA shares come straight from Table 1."""
    t1 = tables.specialty_distribution(con)
    assert list(t1.index) == PROC_ORDER
    assert np.allclose(t1[['Cardiology %', 'Radiology %', 'Other %']].sum(axis=1), 100)
    rad, card = tables.cta_shares(t1)
    assert rad == t1.loc['Cardiac CTA', 'Radiology %'] and card == t1.loc['Cardiac CTA', 'Cardiology %']


def _nb_data(n=60, irr=1.2, seed=3):
    """Simulated state data with a known density IRR (NB2)."""
    rng = np.random.default_rng(seed)
    dens = rng.uniform(1, 10, n)
    ffs = rng.integers(100_000, 2_000_000, n).astype(float)
    mu = ffs / 1000 * 0.5 * irr ** dens
    counts = rng.negative_binomial(5, 5 / (5 + mu))
    return pd.DataFrame(dict(state=[f'S{i}' for i in range(n)], total_services=counts, ffs_enrollment=ffs, dens=dens,
                             mean_age=rng.normal(72, 1, n), pct_female=rng.normal(54, 1, n),
                             rate_per_1000=counts / ffs * 1000))


def test_nb_recovers_known_irr():
    """The adjusted density IRR is close to the simulated truth and its CI contains it."""
    fit = nb_models.fit_density_models(_nb_data(), 'dens', 'density')
    irr, lo, hi, p = fit['irr_adj']
    assert lo < 1.2 < hi and abs(irr - 1.2) < 0.06 and p < 0.001
    assert fit['ncoef_adj'] == 4 and set(fit['vifs']) == {'density', 'mean_age_z', 'pct_female_z'}
    assert fit['alpha_adj'] > 0


def test_irr_and_partial_curve_properties():
    """CIs bracket the estimate; the partial curve rises with density when IRR > 1 and its band contains it."""
    fit = nb_models.fit_density_models(_nb_data(), 'dens', 'density')
    for i in range(4):
        irr, lo, hi, _ = nb_models.irr_at(fit['res_adj'], i)
        assert lo <= irr <= hi
    grid = np.linspace(1, 10, 20)
    mid, lo, hi = nb_models.density_partial_curve(fit['res_adj'], grid, fit['ncoef_adj'])
    assert np.all(np.diff(mid) > 0) and np.all(lo <= mid) and np.all(mid <= hi)


def test_nb_requires_ten_states():
    """Fewer than 10 states with demographics is refused."""
    with pytest.raises(ValueError, match='Only'):
        nb_models.fit_density_models(_nb_data(n=9), 'dens', 'density')


def test_results_table_and_report(capsys):
    """results_table has one row per model with adjusted and unadjusted IRRs; the report prints the key lines."""
    fit = nb_models.fit_density_models(_nb_data(), 'dens', 'density')
    res = {'all': dict(irr_un=fit['irr_un'], irr_adj=fit['irr_adj'], n=60, n_physicians=123)}
    t = nb_models.results_table(res, {'all': 'All'})
    assert list(t.index) == ['All'] and t.loc['All', 'physicians'] == 123
    assert {'IRR adjusted', 'CI low (adj)', 'p (unadj)'} <= set(t.columns)
    nb_models.print_model_report(fit, 'Title', 123, 2023)
    out = capsys.readouterr().out
    assert 'DENSITY IRR — adjusted' in out and 'VIF:' in out
