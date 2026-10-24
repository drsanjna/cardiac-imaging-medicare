"""Deterministic synthetic cms.duckdb built from the data model (db/schema.py), small enough for fast tests."""
import duckdb
import numpy as np
import pandas as pd

from cardiac_imaging import config
from cardiac_imaging.db import schema

STATES = sorted(set(config.STATE_ABBR_MAP.values()))          # 50 + DC
NAME = {v: k for k, v in config.STATE_ABBR_MAP.items()}
ABBR2FIPS = {v: k for k, v in config.FIPS2ABBR.items()}
NO_RAD = {'AK', 'SD'}                  # states with no radiologist CTA reader in 2023 (exercises the ≥1-biller filter)
NO_CARD = {'DE', 'WY'}                 # states with no cardiologist CTA reader in 2023
EXTRA_AREAS = ['PR', 'AA']             # territory (excluded) and military code (passes the filter, has no enrollment)
CODES = {'Echo': '93306', 'SPECT': '78452', 'Cardiac CTA': '75574', 'Cardiac MRI': '75561', 'Cardiac PET': '78492'}
YEARS = list(range(2018, 2024))


def claims_frame(seed=7):
    """Synthetic Physician & Other Practitioners rows covering every filter the pipeline applies."""
    rng = np.random.default_rng(seed)
    cols = [c[0] for c in schema.CLAIMS_COLUMNS]
    rows, npi = [], 1_000_000_000
    rad_types, card_types = list(config.RAD_TYPES), list(config.CARD_TYPES)
    for si, st in enumerate(STATES + EXTRA_AREAS):
        n_rad = 0 if st in NO_RAD else 1 + si % 5
        n_card = 0 if st in NO_CARD else 1 + (si * 3) % 4
        density = n_rad + n_card
        providers = ([(rad_types[i % 3], 'rad') for i in range(n_rad)] + [(card_types[i % 4], 'card') for i in range(n_card)]
                     + [('Internal Medicine', 'other')])
        for ptype, kind in providers:
            npi += 1
            ruca = ['1', '2.0', '3', '4.1', '10', None][npi % 6]
            for year in YEARS:
                growth = 1 + 0.25 * (year - 2018)
                mods = {'rad': ['Cardiac CTA', 'Cardiac MRI', 'SPECT'], 'card': ['Echo', 'SPECT', 'Cardiac CTA', 'Cardiac PET'],
                        'other': ['Echo']}[kind]
                for mod in mods:
                    base = {'Echo': 400, 'SPECT': 120, 'Cardiac CTA': 8 * density * growth, 'Cardiac MRI': 5 * growth, 'Cardiac PET': 15}[mod]
                    srv = float(max(11, rng.poisson(base)))
                    rows.append({**{c: None for c in cols}, 'year': year, 'Rndrng_NPI': str(npi), 'Rndrng_Prvdr_Type': ptype,
                                 'Rndrng_Prvdr_State_Abrvtn': st, 'Rndrng_Prvdr_Cntry': 'US', 'Rndrng_Prvdr_RUCA': ruca,
                                 'Rndrng_Prvdr_State_FIPS': ABBR2FIPS.get(st, '72'), 'Rndrng_Prvdr_Zip5': f'0{npi % 10000:04d}',
                                 'HCPCS_Cd': CODES[mod], 'Place_Of_Srvc': 'F' if npi % 3 else 'O', 'Tot_Srvcs': srv,
                                 'Tot_Bene_Day_Srvcs': int(srv * 0.9), 'Tot_Benes': int(srv * 0.8), 'Rndrng_Prvdr_Ent_Cd': 'I'})
            rows.append({**{c: None for c in cols}, 'year': 2023, 'Rndrng_NPI': str(npi), 'Rndrng_Prvdr_Type': ptype,
                         'Rndrng_Prvdr_State_Abrvtn': st, 'Rndrng_Prvdr_Cntry': 'US', 'HCPCS_Cd': '99213', 'Place_Of_Srvc': 'O',
                         'Tot_Srvcs': 500.0, 'Tot_Bene_Day_Srvcs': 400, 'Tot_Benes': 300})   # non-cardiac row
    return pd.DataFrame(rows, columns=cols)


def enrollment_frame():
    """FFS enrollment for 50 states + DC in 2018 and 2023 (no territories, no AA)."""
    return pd.DataFrame([dict(year=y, state=st, ffs=200_000 + 37_000 * i + (5_000 if y == 2018 else 0))
                         for y in (2018, 2023) for i, st in enumerate(STATES)])


def gv_frame():
    """Raw GV PUF rows (all text) with national, territory, age-band, name/postal/FIPS-only and suppressed cases."""
    rows = [dict(YEAR='2023', BENE_GEO_LVL='National', BENE_GEO_DESC='National', BENE_GEO_CD='', BENE_AGE_LVL='All',
                 BENE_AVG_AGE='72.0', BENE_FEML_PCT='0.55', EXTRA_COL='x')]
    for i, st in enumerate(STATES):
        desc = NAME[st] if i % 3 == 0 else (st if i % 3 == 1 else '')
        for year in ('2022', '2023'):
            rows.append(dict(YEAR=year, BENE_GEO_LVL='State', BENE_GEO_DESC=desc, BENE_GEO_CD=f'{ABBR2FIPS[st]}.0',
                             BENE_AGE_LVL='All', BENE_AVG_AGE=f'{70 + (i % 9) * 0.4:.1f}', BENE_FEML_PCT=f'{0.50 + (i % 7) * 0.01:.2f}',
                             EXTRA_COL='x'))
        rows.append(dict(YEAR='2023', BENE_GEO_LVL='State', BENE_GEO_DESC=desc, BENE_GEO_CD=ABBR2FIPS[st], BENE_AGE_LVL='<65',
                         BENE_AVG_AGE='*', BENE_FEML_PCT='*', EXTRA_COL='x'))
    rows.append(dict(YEAR='2023', BENE_GEO_LVL='State', BENE_GEO_DESC='Puerto Rico', BENE_GEO_CD='72', BENE_AGE_LVL='All',
                     BENE_AVG_AGE='70.0', BENE_FEML_PCT='0.56', EXTRA_COL='x'))
    return pd.DataFrame(rows)


def build(path, claims=None):
    """Write the three tables to a DuckDB file at `path` with the data model's column types; returns the path."""
    con = duckdb.connect(str(path))
    claims = claims_frame() if claims is None else claims
    con.register('_c', claims)
    cast = ', '.join(f'CAST("{c}" AS {t}) AS "{c}"' for c, t, _, _ in schema.CLAIMS_COLUMNS)
    con.execute(f"CREATE TABLE {config.CLAIMS_TABLE} AS SELECT {cast} FROM _c")
    con.register('_e', enrollment_frame())
    con.execute(f"CREATE TABLE {config.ENROLLMENT_TABLE} AS SELECT CAST(year AS BIGINT) AS year, state, CAST(ffs AS BIGINT) AS ffs FROM _e")
    con.register('_g', gv_frame())
    con.execute(f"CREATE TABLE {config.GV_TABLE} AS SELECT * FROM _g")
    con.close()
    return path
