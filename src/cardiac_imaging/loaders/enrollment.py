"""State-level Original Medicare (FFS) enrollment: parse CMS workbooks at upload, read back as {state: ffs}."""
import pandas as pd

from .. import config

_JUNK_ROWS = 'BLANK|All Areas|United States|Notes|Source|¹|²|Area of Residence'


def _finish(df, ffs_col, year):
    df = df[~df['Area_of_Residence'].astype(str).str.contains(_JUNK_ROWS, na=False)].copy()
    df['STCD'] = df['Area_of_Residence'].astype(str).str.strip().map(config.STATE_ABBR_MAP)
    df = df.dropna(subset=['STCD'])
    df = df[~df['STCD'].isin(config.TERR)]
    ffs = pd.to_numeric(df[ffs_col], errors='coerce').astype(int)
    return pd.DataFrame({'year': year, 'state': df['STCD'].values, 'ffs': ffs.values})


def parse_enrollment_2023(raw):
    """Raw 2023 CMS workbook (header=None, skiprows=4) → DataFrame(year, state, ffs)."""
    col_names = ['Area_of_Residence', 'State_Population', 'Total_Medicare_Enrollment',
                 'Total_Medicare_Pct', 'Original_Medicare_Enrollment',
                 'Original_Medicare_Pct', 'MA_Enrollment', 'MA_Pct',
                 'Metro_Enrollment', 'Micro_Enrollment', 'NonCore_Enrollment']
    raw = raw.copy()
    raw.columns = col_names[:len(raw.columns)]
    raw = raw.dropna(subset=['Area_of_Residence', 'Original_Medicare_Enrollment'])
    return _finish(raw, 'Original_Medicare_Enrollment', 2023)


def parse_enrollment_2018(raw):
    """Raw 2018 CMS workbook (header=None, skiprows=4) → DataFrame(year, state, ffs)."""
    col_names = ['Area_of_Residence', 'Total_Original_Medicare_Enrollees',
                 'Total_Aged', 'Aged_Without_ESRD']
    for i in range(len(col_names), len(raw.columns)):
        col_names.append(f'Extra_{i}')
    raw = raw.copy()
    raw.columns = col_names[:len(raw.columns)]
    raw = raw.dropna(subset=['Area_of_Residence', 'Total_Original_Medicare_Enrollees'])
    return _finish(raw, 'Total_Original_Medicare_Enrollees', 2018)


def load_state_ffs(con, year):
    """{state: FFS enrollment} for one year, from ENROLLMENT_TABLE."""
    df = con.execute(
        f"SELECT state, ffs FROM {config.ENROLLMENT_TABLE} WHERE year = ?", [year]
    ).fetchdf()
    lookup = dict(zip(df['state'], df['ffs'].astype(int)))
    if not lookup:
        raise ValueError(f"No state enrollment rows for {year} in {config.ENROLLMENT_TABLE}.")
    print(f"  {year} state enrollment loaded: {len(lookup)} states, "
          f"national total = {sum(lookup.values()):,}")
    return lookup
