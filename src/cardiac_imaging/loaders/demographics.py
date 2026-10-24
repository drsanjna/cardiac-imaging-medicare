"""State mean age and % female from the CMS Geographic Variation PUF (model covariates)."""
import numpy as np
import pandas as pd

from .. import config
from ..audit import log_filter


def _num(s):
    s = (s.astype(str).str.replace('%', '', regex=False)
                      .str.replace(',', '', regex=False).str.strip())
    return pd.to_numeric(s.replace({'*': np.nan, '.': np.nan, '': np.nan}),
                         errors='coerce')


def load_gv_demographics(con, year=config.GV_YEAR):
    """DataFrame(state, mean_age, pct_female) for 50 states + DC in `year`."""
    gv = con.execute(f"SELECT * FROM {config.GV_TABLE}").fetchdf()
    gv.columns = [c.strip().upper() for c in gv.columns]

    yr = pd.to_numeric(gv['YEAR'], errors='coerce')
    avail = sorted(yr.dropna().astype(int).unique())
    if year not in avail:
        raise ValueError(f"Year {year} not in GV PUF (available: {avail}).")

    lvl = gv['BENE_GEO_LVL'].astype(str).str.strip().str.lower()
    age = gv['BENE_AGE_LVL'].astype(str).str.strip().str.lower()
    gv = gv[(lvl == 'state') & (age.str.startswith('all')) & (yr == year)].copy()
    if gv.empty:
        raise ValueError("0 rows after State/all-ages/year filter.")

    name2abbr = {k.lower(): v for k, v in config.STATE_ABBR_MAP.items()}
    valid_abbr = set(config.STATE_ABBR_MAP.values())
    gv = gv.reset_index(drop=True)
    desc = gv['BENE_GEO_DESC'].fillna('').astype(str).str.strip()
    if 'BENE_GEO_CD' in gv.columns:
        cd = (gv['BENE_GEO_CD'].fillna('').astype(str).str.strip()
              .str.split('.').str[0].str.zfill(2))
    else:
        cd = pd.Series([''] * len(gv))

    def resolve(d, c):
        if d.upper() in valid_abbr:  return d.upper()
        if d.lower() in name2abbr:   return name2abbr[d.lower()]
        return config.FIPS2ABBR.get(c)

    gv['state'] = [resolve(d, c) for d, c in zip(desc, cd)]
    gv = gv.dropna(subset=['state']).reset_index(drop=True)   # drops territories + National

    out = pd.DataFrame({'state': gv['state'].values})
    out['mean_age'] = _num(gv['BENE_AVG_AGE']).values
    fem = _num(gv['BENE_FEML_PCT']).values
    if np.nanmedian(fem) < 1.5:
        fem = fem * 100.0
    out['pct_female'] = fem
    n, states = len(out), set(out['state'])
    out = out.dropna().drop_duplicates('state').reset_index(drop=True)
    log_filter('GV state rows with numeric age and % female', n, len(out),
               dropped_items=states - set(out['state']))
    if out.empty:
        raise ValueError("GV demographics empty after numeric coercion.")
    print(f"  GV PUF demographics usable: {len(out)} states (year {year})")
    return out
