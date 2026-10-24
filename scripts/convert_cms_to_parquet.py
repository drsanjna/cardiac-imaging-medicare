#!/usr/bin/env python3
"""
Convert CMS "Medicare Physician & Other Practitioners - by Provider and Service"
CSVs to Parquet, then report how much smaller they get.

Finds CSVs in ~/Downloads (top level or one folder deep) whose name contains
"Medicare_Physician_Other_Practitioners_by_Provider_and_Service" and a 4-digit year,
e.g. Medicare_Physician_Other_Practitioners_by_Provider_and_Service_2022.csv.
Matching is case-insensitive and tolerates spaces/hyphens instead of underscores.

What it checks:
  1. Per-file CSV size vs. Parquet size (compression ratio)
  2. Row count of the CSV vs. row count of the Parquet. A mismatch means rows were
     lost, so the script flags it.
  3. Total size vs. the MotherDuck Lite 10 GB free limit
  4. With --duckdb: builds one combined table (with a `year` column) in a native
     .duckdb file. That size is closer to what MotherDuck actually stores.

Usage:
    python convert_cms_to_parquet.py              # convert + report
    python convert_cms_to_parquet.py --duckdb     # also build combined cms.duckdb
    python convert_cms_to_parquet.py --force      # redo files already converted

Paths: CMS_CSV_DIR (default ~/Downloads) and CMS_PARQUET_DIR (default <CMS_CSV_DIR>/cms_parquet).
Next step: python scripts/build_database.py  (adds enrollment + GV reference tables to cms.duckdb)
"""
import argparse
import csv
import os
import re
import sys
import time
from pathlib import Path

import duckdb

DOWNLOADS = Path(os.environ.get("CMS_CSV_DIR") or Path.home() / "Downloads").expanduser()
# Case-insensitive; separators can be _, -, space; year = first 4-digit 20xx/19xx after the name.
NAME_RE = re.compile(
    r"medicare[ _-]*physician[ _-]*other[ _-]*practitioners[ _-]*by[ _-]*provider[ _-]*and[ _-]*service"
    r".*?((?:19|20)\d{2})",
    re.IGNORECASE,
)
OUT_DIR = Path(os.environ.get("CMS_PARQUET_DIR") or DOWNLOADS / "cms_parquet").expanduser()
FREE_LIMIT_GB = 10.0  # MotherDuck Lite storage cap

# Identifier/code columns forced to text. Auto-detection can read NPIs, ZIPs, FIPS and
# HCPCS (e.g. '0001A') as numbers, which drops leading zeros or fails mid-file.
# Only columns that actually exist in a given file get overridden.
FORCE_VARCHAR = [
    "Rndrng_NPI", "HCPCS_Cd", "Rndrng_Prvdr_Zip5",
    "Rndrng_Prvdr_State_FIPS", "Rndrng_Prvdr_RUCA",
]

GB = 1e9


def header(csv_path: Path) -> list[str]:
    """Return the CSV's header row (column names)."""
    with open(csv_path, newline="", encoding="utf-8-sig", errors="replace") as f:
        return next(csv.reader(f))


def read_csv_sql(csv_path: Path) -> str:
    """DuckDB read_csv(...) expression for a CSV, forcing identifier/code columns to VARCHAR."""
    cols = set(header(csv_path))
    overrides = {c: "VARCHAR" for c in FORCE_VARCHAR if c in cols}
    types = "{" + ", ".join(f"'{c}': '{t}'" for c, t in overrides.items()) + "}"
    types_arg = f", types={types}" if overrides else ""
    return f"read_csv('{csv_path.as_posix()}', header=true{types_arg})"


def main() -> int:
    """Find the yearly CSVs, convert each to zstd Parquet, verify row counts, and report sizes."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--duckdb", action="store_true", help="also build combined cms.duckdb")
    ap.add_argument("--force", action="store_true", help="re-convert existing parquet files")
    args = ap.parse_args()

    # Look at CSVs at the top of Downloads and one folder down; the year can be in
    # either the file name or the parent folder name.
    candidates = sorted(set(DOWNLOADS.glob("*.csv")) | set(DOWNLOADS.glob("*/*.csv")))
    candidates = [c for c in candidates if OUT_DIR not in c.parents]
    matched = []
    for c in candidates:
        m = NAME_RE.search(c.name) or NAME_RE.search(c.parent.name)
        if m:
            matched.append((m.group(1), c))

    if not matched:
        print("No matching CSVs found. CSVs I can see in Downloads:")
        for c in candidates[:30]:
            print("   ", c.relative_to(DOWNLOADS))
        print("Paste this list back so the pattern can be adjusted.")
        return 1

    # Same file name + same byte size in two places = the same download copied twice
    # (e.g. one in Downloads and one inside an unzipped folder). Keep one, report the rest.
    by_year, seen = {}, {}
    for year, c in sorted(matched, key=lambda t: (t[0], len(t[1].parts), str(t[1]))):
        key = (year, c.name, c.stat().st_size)
        if key in seen:
            print(f"[{year}] identical copy ignored: {c.relative_to(DOWNLOADS)} "
                  f"(same name and size as {seen[key].relative_to(DOWNLOADS)})")
            continue
        seen[key] = c
        by_year.setdefault(year, []).append(c)
    matched = [(y, c) for y, cs in by_year.items() for c in cs]

    dupes = {y: cs for y, cs in by_year.items() if len(cs) > 1}
    print(f"Using {len(matched)} CSV(s) covering years: {', '.join(sorted(by_year))}")
    for y, cs in dupes.items():
        print(f"WARNING: {len(cs)} DIFFERENT files for {y}: "
              + ", ".join(str(c.relative_to(DOWNLOADS)) for c in cs))
    print()

    OUT_DIR.mkdir(exist_ok=True)
    con = duckdb.connect()  # in-memory engine; it spills to disk if needed
    rows, failures = [], []

    for year, csv_path in sorted(matched):
        tag = "" if csv_path.parent == DOWNLOADS else f"{csv_path.parent.name}__"
        out = OUT_DIR / f"{year}__{tag}{csv_path.stem}.parquet"
        src = read_csv_sql(csv_path)
        t0 = time.time()
        try:
            if args.force or not out.exists():
                con.execute(f"COPY (SELECT * FROM {src}) TO '{out.as_posix()}' "
                            f"(FORMAT parquet, COMPRESSION zstd)")
            n_csv = con.execute(f"SELECT count(*) FROM {src}").fetchall()[0][0]
            n_pq = con.execute(f"SELECT count(*) FROM read_parquet('{out.as_posix()}')").fetchall()[0][0]
        except Exception as e:  # report and continue, never silently drop a file
            failures.append((csv_path.name, str(e).splitlines()[0]))
            print(f"[{year}] FAILED {csv_path.name}: {str(e).splitlines()[0]}")
            continue

        csv_gb, pq_gb = csv_path.stat().st_size / GB, out.stat().st_size / GB
        rows.append((year, csv_path.name, csv_gb, pq_gb, n_csv, n_pq))
        flag = "OK" if n_csv == n_pq else f"ROW MISMATCH ({n_csv - n_pq:+,})"
        print(f"[{year}] {csv_gb:6.2f} GB -> {pq_gb:5.2f} GB  "
              f"({csv_gb / pq_gb:4.1f}x)  rows {n_pq:>12,}  {flag}  [{time.time() - t0:.0f}s]")

    if dupes and args.duckdb:
        print("\nSkipping combined cms.duckdb: duplicate years would double-count rows. "
              "Remove the extra download(s) and re-run.")
        args.duckdb = False

    if not rows:
        return 1

    tot_csv = sum(r[2] for r in rows)
    tot_pq = sum(r[3] for r in rows)
    print("\n" + "=" * 70)
    print(f"Files converted : {len(rows)}   failed: {len(failures)}")
    print(f"Total CSV       : {tot_csv:6.2f} GB")
    print(f"Total Parquet   : {tot_pq:6.2f} GB   ({tot_csv / tot_pq:.1f}x smaller)")
    print(f"MotherDuck Lite : {'FITS' if tot_pq < FREE_LIMIT_GB else 'DOES NOT FIT'} "
          f"under {FREE_LIMIT_GB:.0f} GB (Parquet size; native DuckDB size can differ)")
    if any(r[4] != r[5] for r in rows):
        print("WARNING: at least one file lost rows in conversion. Do not use until resolved.")

    if args.duckdb:
        db_path = OUT_DIR / "cms.duckdb"
        db = duckdb.connect(str(db_path))  # replace only the claims table; keep reference tables
        db.execute("DROP TABLE IF EXISTS partb_provider_service")
        # union_by_name handles columns that were added or dropped across years;
        # `year` comes from the file name prefix, so every row is traceable to its source year.
        db.execute(f"""
            CREATE TABLE partb_provider_service AS
            SELECT CAST(split_part(parse_filename(filename, true), '__', 1) AS INTEGER) AS year, *
                   EXCLUDE (filename)
            FROM read_parquet('{OUT_DIR.as_posix()}/*.parquet', union_by_name=true, filename=true)
        """)
        n = db.execute("SELECT count(*) FROM partb_provider_service").fetchall()[0][0]
        db.execute("CHECKPOINT")
        db.close()
        db_gb = db_path.stat().st_size / GB
        print(f"Native DuckDB   : {db_gb:6.2f} GB, {n:,} rows -> "
              f"MotherDuck Lite {'FITS' if db_gb < FREE_LIMIT_GB else 'DOES NOT FIT'}")
        if n != sum(r[5] for r in rows):
            print("WARNING: combined table row count != sum of Parquet rows.")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
