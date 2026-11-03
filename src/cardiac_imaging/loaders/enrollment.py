"""State-level Original Medicare (FFS) enrollment: parse CMS workbooks at upload, read back as {state: ffs}."""
import pandas as pd

from .. import config

_JUNK_ROWS = 'BLANK|All Areas|United States|Notes|Source|¹|²|Area of Residence'
# Header text of the FFS column in the two CMS Program Statistics layouts the workbooks come in:
# MDCR ENROLL AB 14 (Original Medicare enrollees by type of entitlement) and AB 2 (total / Original / MA enrollment).
FFS_HEADERS = ('Total Original Medicare Enrollees', 'Original Medicare Enrollment')


def _finish(df, ffs_col, year):
    """Drop note/total rows, map state names to codes, drop territories, return (year, state, ffs)."""
    df = df[~df['Area_of_Residence'].astype(str).str.contains(_JUNK_ROWS, na=False)].copy()
    df['STCD'] = df['Area_of_Residence'].astype(str).str.strip().map(config.STATE_ABBR_MAP)
    df = df.dropna(subset=['STCD'])
    df = df[~df['STCD'].isin(config.TERR)]
    ffs = pd.to_numeric(df[ffs_col], errors='coerce').astype(int)
    return pd.DataFrame({'year': year, 'state': df['STCD'].values, 'ffs': ffs.values})


def find_ffs_column(raw):
    """Index of the FFS column: the first cell in the top rows (column 1 onward) whose text is one of FFS_HEADERS.

    Column 0 holds the area names and the sheet title (the AB 14 title is 'Original Medicare Enrollment', the same
    text as the AB 2 column header), so it is never a candidate.
    """
    for i in range(min(len(raw), 15)):
        for j, v in enumerate(raw.iloc[i].tolist()):
            if j > 0 and isinstance(v, str) and v.strip() in FFS_HEADERS:
                return j
    raise ValueError(f"No column headed {FFS_HEADERS} in the first rows of the enrollment sheet.")


def parse_enrollment(raw, year):
    """Raw CMS enrollment sheet (read with header=None) → DataFrame(year, state, ffs).

    Works for the AB 14 and AB 2 layouts: the state name is in the first column and the FFS column is found by its
    header text, so the number of columns and preamble rows does not matter.
    """
    raw = raw.copy()
    raw.columns = range(raw.shape[1])
    col = find_ffs_column(raw)
    df = raw.rename(columns={0: 'Area_of_Residence', col: 'ffs_raw'})
    df = df.dropna(subset=['Area_of_Residence', 'ffs_raw'])
    return _finish(df, 'ffs_raw', int(year))


def enrollment_sheet(path):
    """Sheet to read in an enrollment workbook: the AB 14 sheet if there is one, else AB 2, else the first sheet."""
    names = pd.ExcelFile(path).sheet_names
    for key in ('AB 14', 'AB 2'):
        hit = [s for s in names if key in s]
        if hit:
            return hit[0]
    return names[0]


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
