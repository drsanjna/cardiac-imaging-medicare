# Instructions for Claude Code in this repo

## Layout
- `src/cardiac_imaging/` — all logic. Each directory has a generated README.md with a flowchart.
- `notebooks/main.ipynb` — thin driver only: imports from `src/`, config, run. No business logic in cells.
- `scripts/` — `convert_cms_to_parquet.py` (CSV → Parquet), `build_database.py` (cms.duckdb), `update_readmes.py`.
- `legacy/original_sourcecode.py` — frozen original; never edit or import it.

## Data
- Local DuckDB `~/Downloads/cms_parquet/cms.duckdb` (override: `CARDIAC_DB`). Tables: `partb_provider_service`
  (view over the yearly Parquet files, with `year`), `state_ffs_enrollment`, `gv_puf`.
- Analysis connections are read-only. Only `scripts/build_database.py` writes.
- Identifier columns (NPI, HCPCS, ZIP5, FIPS, RUCA) are VARCHAR. Cast explicitly for numeric comparisons (`TRY_CAST(Rndrng_Prvdr_RUCA AS DOUBLE)`).

## Debug loop
1. Run headless: `papermill notebooks/main.ipynb runs/out.ipynb` (or `python -m cardiac_imaging.pipeline --no-report`).
2. On failure read `logs/last_error.md` (names the failing step from `pipeline.STEPS`) or the papermill traceback.
3. Fix the code in `src/`, NOT the .ipynb JSON. Only touch a cell if the bug is in the cell itself.
4. Re-run step 1 until it passes.
5. Run `python scripts/update_readmes.py`, then commit code + READMEs together.

## Rules
- Every module gets a one-line module docstring and every public function/class a one-line docstring (they feed the READMEs).
- Analysis definitions (HCPCS codes, specialty lists, excluded territories, enrollment, year range) live only in `config.py`. Changing them needs the user's explicit approval — never change one to make an error go away.
- No silent row drops: every filter logs before/after counts via `audit.log_filter`.
- Credentials only from environment variables. Never delete source data (CSVs, Parquet) without explicit confirmation.
