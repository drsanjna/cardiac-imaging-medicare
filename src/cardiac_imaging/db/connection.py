"""Open the analysis database: local DuckDB file by default (read-only), or MotherDuck when CARDIAC_DB starts with md:."""
import os
from pathlib import Path

import duckdb

from .. import config


def get_connection(database=None, read_only=True):
    """Return a DuckDB connection to `database` (default config.DATABASE). Analysis connections are read-only."""
    database = database or config.DATABASE
    if database.startswith('md:'):
        if not os.environ.get('MOTHERDUCK_TOKEN'):
            raise RuntimeError("CARDIAC_DB points at MotherDuck but MOTHERDUCK_TOKEN is not set.")
        con = duckdb.connect(database, read_only=read_only)
    else:
        if read_only and not Path(database).exists():
            raise RuntimeError(f"No database at {database}. Build it: "
                               "python scripts/convert_cms_to_parquet.py --duckdb && python scripts/build_database.py")
        con = duckdb.connect(database, read_only=read_only)
    print(f"Connected to {database} ({'read-only' if read_only else 'read-write'}).")
    return con


def require_tables(con, tables=(config.CLAIMS_TABLE, config.ENROLLMENT_TABLE, config.GV_TABLE)):
    """Fail fast with a clear message if a build step has not been run."""
    present = set(con.execute("SELECT table_name FROM information_schema.tables").fetchdf()['table_name'])
    missing = [t for t in tables if t not in present]
    if missing:
        raise RuntimeError(f"Missing tables {missing}. Run: python scripts/build_database.py")
