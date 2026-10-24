"""Create cms.duckdb: a claims view over the Parquet files, plus the enrollment and GV reference tables.

Run after scripts/convert_cms_to_parquet.py:
    python scripts/build_database.py
"""
import argparse
from pathlib import Path

from cardiac_imaging import config
from cardiac_imaging.db import build, schema
from cardiac_imaging.db.connection import get_connection


def main():
    """Parse arguments, build/refresh cms.duckdb tables, and validate them against the data model."""
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--db', default=config.DATABASE, help=f"Database file (default {config.DATABASE})")
    p.add_argument('--claims', action='store_true', help="Rebuild the claims view from Parquet even if it exists")
    p.add_argument('--materialize', action='store_true',
                   help="Copy claims into a native table (+4.2 GB disk) instead of a view over Parquet")
    p.add_argument('--reference-dir', type=Path, default=config.REFERENCE_DIR,
                   help="Folder with 'original medicare enrollment 2018.xlsx' and '... 2023.xlsx'")
    p.add_argument('--gv', default=config.GV_PUF_GLOB, help="Glob for the Geographic Variation PUF CSV(s)")
    args = p.parse_args()

    con = get_connection(args.db, read_only=False)
    tables = set(con.execute("SELECT table_name FROM information_schema.tables").fetchdf()['table_name'])
    if args.claims or args.materialize or config.CLAIMS_TABLE not in tables:
        print(f"Building {config.CLAIMS_TABLE} from {config.PARQUET_DIR} ...")
        build.build_claims_table(con, materialize=args.materialize)
    else:
        print(f"{config.CLAIMS_TABLE} already present (use --claims to rebuild):")
        build.report_claims(con)
    d = args.reference_dir.expanduser()
    build.load_state_enrollment(con, d / 'original medicare enrollment 2018.xlsx',
                                d / 'original medicare enrollment 2023.xlsx')
    build.load_gv_puf(con, Path(args.gv).expanduser())
    con.execute("CHECKPOINT")
    problems = schema.validate(con)
    if problems:
        raise SystemExit("Database does not match the data model (src/cardiac_imaging/db/schema.py):\n  "
                         + "\n  ".join(problems))
    print("Database ready (matches the data model in db/schema.py).")


if __name__ == '__main__':
    main()
