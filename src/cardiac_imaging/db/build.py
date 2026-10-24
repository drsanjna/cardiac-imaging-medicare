"""Build the database tables: claims from the yearly Parquet files, plus enrollment and GV reference tables."""
import glob

import pandas as pd

from .. import config
from ..loaders import enrollment


def build_claims_table(con, parquet_dir=config.PARQUET_DIR, materialize=False):
    """(Re)create CLAIMS_TABLE over YYYY__*.parquet with `year` from the file name; prints rows per year.

    Default is a VIEW (reads the 2.1 GB of Parquet in place). materialize=True copies it into a
    native table (+4.2 GB on disk, somewhat faster queries).
    """
    pattern = f"{parquet_dir}/*.parquet"
    if not glob.glob(pattern):
        raise FileNotFoundError(f"No Parquet files in {parquet_dir}. Run scripts/convert_cms_to_parquet.py first.")
    con.execute(f"DROP VIEW IF EXISTS {config.CLAIMS_TABLE}")
    con.execute(f"DROP TABLE IF EXISTS {config.CLAIMS_TABLE}")
    con.execute(f"""
        CREATE {'TABLE' if materialize else 'VIEW'} {config.CLAIMS_TABLE} AS
        SELECT CAST(split_part(parse_filename(filename, true), '__', 1) AS INTEGER) AS year, *
               EXCLUDE (filename)
        FROM read_parquet('{pattern}', union_by_name=true, filename=true)
    """)
    report_claims(con)


def report_claims(con):
    """Rows per year and the types of the identifier columns (must be VARCHAR)."""
    per_year = con.execute(
        f"SELECT year, COUNT(*) AS n FROM {config.CLAIMS_TABLE} GROUP BY year ORDER BY year").fetchall()
    for y, n in per_year:
        print(f"  {config.CLAIMS_TABLE} {y}: {n:,} rows")
    print(f"  total: {sum(n for _, n in per_year):,} rows")
    types = dict(con.execute(f"SELECT column_name, column_type FROM (DESCRIBE {config.CLAIMS_TABLE})").fetchall())
    for col in ('Rndrng_NPI', 'HCPCS_Cd', 'Rndrng_Prvdr_Zip5', 'Rndrng_Prvdr_State_FIPS', 'Rndrng_Prvdr_RUCA'):
        print(f"  {col}: {types.get(col, 'MISSING')}")


def load_state_enrollment(con, xlsx_2018, xlsx_2023):
    """Parse the CMS state enrollment workbooks and store one clean (year, state, ffs) table."""
    df = pd.concat([
        enrollment.parse_enrollment_2018(pd.read_excel(xlsx_2018, header=None, skiprows=4)),
        enrollment.parse_enrollment_2023(pd.read_excel(xlsx_2023, header=None, skiprows=4)),
    ], ignore_index=True)
    con.register('_enr', df)
    con.execute(f"CREATE OR REPLACE TABLE {config.ENROLLMENT_TABLE} AS SELECT * FROM _enr")
    con.unregister('_enr')
    print(f"  {config.ENROLLMENT_TABLE}: {len(df)} rows "
          f"({df.groupby('year').size().to_dict()} states per year)")


def load_gv_puf(con, csv_glob=config.GV_PUF_GLOB):
    """Load the Geographic Variation PUF as all-VARCHAR (cleaning happens in loaders.demographics)."""
    files = sorted(glob.glob(str(csv_glob)))
    if not files:
        raise FileNotFoundError(f"No GV PUF file matched: {csv_glob}")
    file_list = '[' + ', '.join(f"'{f}'" for f in files) + ']'
    con.execute(f"""
        CREATE OR REPLACE TABLE {config.GV_TABLE} AS
        SELECT * FROM read_csv({file_list}, all_varchar=true, header=true, union_by_name=true)
    """)
    n = con.execute(f"SELECT COUNT(*) FROM {config.GV_TABLE}").fetchall()[0][0]
    print(f"  {config.GV_TABLE}: {n:,} rows from {[f.split('/')[-1] for f in files]}")
