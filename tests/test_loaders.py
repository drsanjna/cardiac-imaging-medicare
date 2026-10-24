"""Loaders: claims detail and filters, enrollment parsing, GV demographics, provider density."""
import numpy as np
import pandas as pd
import pytest

import synthetic
from cardiac_imaging import audit, config
from cardiac_imaging.loaders import claims, demographics, enrollment, providers


def test_specialty_guard(con):
    """Passes when every specialty string exists; fails loudly when one is missing."""
    claims.verify_specialty_strings(con)
    import duckdb
    c = duckdb.connect()
    c.execute(f"CREATE TABLE {config.CLAIMS_TABLE} AS SELECT 'Cardiology' AS Rndrng_Prvdr_Type")
    with pytest.raises(AssertionError, match='Specialty string not found'):
        claims.verify_specialty_strings(c)


def test_load_detail_filters_and_classifies(con):
    """Only cardiac codes, no territories/invalid states, RUCA cast to Urban/Rural/Unknown, every row has a modality."""
    audit.FILTER_LOG.clear()
    df = claims.load_detail(con)
    assert set(df['procedure_category']) == set(synthetic.CODES)
    assert 'PR' not in set(df['state']) and 'AA' in set(df['state'])
    assert set(df['rural_urban']) == {'Urban', 'Rural', 'Unknown'}
    assert set(df['modality_type']) == {'Advanced', 'Traditional'}
    assert '99213' not in set(df['HCPCS_Cd'])
    labels = [f['filter'] for f in audit.FILTER_LOG]
    assert any('excluding territories' in l for l in labels)


def test_ruca_threshold_matches_numeric_comparison(con):
    """VARCHAR RUCA is compared numerically: ≤3 Urban, >3 Rural."""
    df = claims.load_detail(con)
    raw = con.execute(f"SELECT DISTINCT Rndrng_NPI, Rndrng_Prvdr_RUCA FROM {config.CLAIMS_TABLE} "
                      f"WHERE {config.CARDIAC_HCPCS_WHERE}").fetchdf()
    merged = df.merge(raw, on='Rndrng_NPI')
    for ruca, label in [('1', 'Urban'), ('2.0', 'Urban'), ('3', 'Urban'), ('4.1', 'Rural'), ('10', 'Rural')]:
        assert set(merged.loc[merged['Rndrng_Prvdr_RUCA'] == ruca, 'rural_urban']) == {label}
    assert set(merged.loc[merged['Rndrng_Prvdr_RUCA'].isna(), 'rural_urban']) == {'Unknown'}


def test_aggregate_segments_drops_unknown_and_logs(con):
    """Segment aggregates exclude Unknown RUCA and log the services dropped."""
    audit.FILTER_LOG.clear()
    agg = claims.aggregate_segments(claims.load_detail(con))
    assert 'Unknown' not in set(agg['rural_urban'])
    assert set(agg['segment']) <= {'Urban / Office', 'Urban / Facility', 'Rural / Office', 'Rural / Facility'}
    log = audit.FILTER_LOG[-1]
    assert log['unit'] == 'services' and log['dropped'] > 0
    trend = claims.national_trend(agg)
    assert set(trend['year']) == set(synthetic.YEARS)


def _raw_2023():
    """A tiny raw 2023 enrollment sheet with junk rows and a territory."""
    return pd.DataFrame([['Area of Residence', None, None, None, 'x'],
                         ['Alabama', 1, 2, 3, 900_000], ['Alaska', 1, 2, 3, '80000'],
                         ['Puerto Rico', 1, 2, 3, 500], ['United States', 1, 2, 3, 99], ['Notes: blah', None, None, None, None]])


def test_parse_enrollment_2023():
    """Keeps states, drops header/total/notes rows and territories, converts FFS to int."""
    out = enrollment.parse_enrollment_2023(_raw_2023())
    assert out.to_dict('records') == [{'year': 2023, 'state': 'AL', 'ffs': 900000}, {'year': 2023, 'state': 'AK', 'ffs': 80000}]


def test_parse_enrollment_2018_with_extra_columns():
    """Works when the 2018 sheet has more columns than named."""
    raw = pd.DataFrame([['Texas', 3_000_000, 1, 2, 'extra', 'more'], ['Guam', 10, 1, 2, 'x', 'y']])
    out = enrollment.parse_enrollment_2018(raw)
    assert out.to_dict('records') == [{'year': 2018, 'state': 'TX', 'ffs': 3000000}]


def test_load_state_ffs(con):
    """Returns {state: ffs} for a year and fails for a missing year."""
    ffs = enrollment.load_state_ffs(con, 2023)
    assert len(ffs) == 51 and all(isinstance(v, int) for v in ffs.values())
    with pytest.raises(ValueError):
        enrollment.load_state_ffs(con, 1999)


def test_gv_demographics_resolution_and_cleaning(con):
    """States resolved from name, postal code or FIPS; fractions → %; territories, age bands and other years dropped."""
    demo = demographics.load_gv_demographics(con, 2023)
    assert len(demo) == 51 and set(demo['state']) == set(synthetic.STATES)
    assert demo['pct_female'].between(40, 70).all()
    assert demo['mean_age'].between(60, 80).all()


def test_gv_missing_year(con):
    """Asking for a year not in the file fails with the available years."""
    with pytest.raises(ValueError, match='not in GV PUF'):
        demographics.load_gv_demographics(con, 1990)


def test_num_parses_cms_text():
    """Percent signs, thousands separators and suppression markers are handled."""
    out = demographics._num(pd.Series(['12.5%', '1,234', '*', '.', '', 'x']))
    assert out.iloc[0] == 12.5 and out.iloc[1] == 1234
    assert out.iloc[2:].isna().all()


def test_cta_density_frames(con):
    """Density frames drop states lacking enrollment (AA) or specialty billers (AK/SD, DE/WY) and carry demographics."""
    ffs = enrollment.load_state_ffs(con, 2023)
    demo = demographics.load_gv_demographics(con, 2023)
    frames = providers.load_cta_density_frames(con, ffs, demo)
    assert len(frames['all']) == 51 and 'AA' not in set(frames['all']['state'])
    assert not set(frames['rad']['state']) & synthetic.NO_RAD
    assert not set(frames['card']['state']) & synthetic.NO_CARD
    for k, col in [('all', 'npis_per_100k'), ('rad', 'rad_npis_per_100k'), ('card', 'card_npis_per_100k')]:
        f = frames[k]
        assert (f[col] > 0).all() and f['mean_age'].notna().all()
        assert np.allclose(f['rate_per_1000'], f['total_services'] / f['ffs_enrollment'] * 1000)


def test_national_counts_deduplicate_multistate_npis(con):
    """National unique NPI counts never exceed the sum of per-state counts; specialty counts ≤ all."""
    n = providers.national_physician_counts(con)
    assert n['rad'] + n['card'] <= n['all'] and n['rad'] > 0 and n['card'] > 0


def test_states_without_billers(con, capsys):
    """Missing-biller report lists exactly the synthetic gaps."""
    ffs = enrollment.load_state_ffs(con, 2023)
    frames = providers.load_cta_density_frames(con, ffs, demographics.load_gv_demographics(con, 2023))
    missing = providers.report_states_without_billers(ffs, frames)
    assert missing['all'] == [] and set(missing['rad']) == synthetic.NO_RAD and set(missing['card']) == synthetic.NO_CARD
    assert 'ZERO CTA-BILLING' in capsys.readouterr().out
