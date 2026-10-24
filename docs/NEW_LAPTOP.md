# Pick up the research on another Mac

One script sets up everything; it is safe to re-run and never deletes anything.

## 1. Get the data onto the new laptop (either option)

- **Copy from your first laptop (fastest):** AirDrop or USB the folder `~/Downloads/cms_parquet` (2.1 GB) plus
  `original medicare enrollment 2018.xlsx`, `original medicare enrollment 2023.xlsx` and the
  `Medicare_GV_by_National_State_County_….csv` file into `~/Downloads` on the new laptop.
- **Or download from CMS:** the six yearly *Medicare Physician & Other Practitioners — by Provider and Service* CSVs
  (2018–2023), the two *Original Medicare enrollment by state* workbooks, and the *Medicare Geographic Variation — by
  National, State & County* CSV, into `~/Downloads` (or one folder below it).

## 2. Run the setup script

```bash
curl -fsSL https://raw.githubusercontent.com/drsanjna/cardiac-imaging-medicare/main/scripts/setup_laptop.sh -o setup_laptop.sh
```
```bash
bash setup_laptop.sh
```

It checks the Mac, clones the repo to `~/code/cardiac-imaging-medicare` (outside iCloud), creates `~/jupyter-env`, turns on
the git hooks, finds your data and records its location in `.env`, builds `cms.duckdb`, runs the tests — including the
real-data checks that prove the published numbers reproduce exactly — downloads past runs from GitHub, and opens the
results page. If a data file is missing it lists exactly which ones, and you re-run after downloading.

Options: `--data-dir DIR` (if your downloads are elsewhere), `--repo-dir DIR`, `--skip-runs`, `--no-app`.

## 3. Two one-time logins it will remind you about

```bash
gh auth login
```
Live chat in **💬 Discuss** — the script prints the exact `… auth login` command for the Claude Code copy on that laptop.

Then in the Claude app → **Code**, open `~/code/cardiac-imaging-medicare`. The repo's `CLAUDE.md` gives Claude the
project rules, so it works the same way as on the first laptop.

## What syncs between laptops

| Syncs through GitHub | Stays on each laptop |
|---|---|
| Code (git), every run's outputs, code snapshot, summary and **label** (GitHub Releases), the hypotheses log, the work log | The data files, `.env`, chart discussions (`~/Downloads/cms_conversations`), Claude app sessions |

Before switching laptops: commit and push your code. On the other laptop: `git pull` (or re-run the setup script) and
open the results page — runs made on either laptop appear in the list.

### Keeping runs in sync

Runs sync on their own. You never need to copy anything by hand:

- **After every run**, the run is uploaded to GitHub and then **checked**: every file must be there and not empty, and
  the release notes must match the run. If the check fails, the upload is repaired and retried (3 attempts). If it still
  fails (say you're offline), the run is flagged *GitHub copy incomplete* on the results page, and the next sync finishes it.
- **When the results page starts**, and whenever you click **⟳ Sync now**, it syncs both ways:
  - it uploads runs that aren't on GitHub yet, or only partly
  - it downloads runs made on the other laptop
  - it copies over labels changed on the other laptop (the most recent change wins, including clearing a label)
- **From the terminal:**

  ```bash
  python scripts/sync_runs.py              # sync now
  python scripts/sync_runs.py --check      # verify only; exit 1 if anything is out of sync
  python scripts/sync_runs.py --install-schedule 30   # optional: also sync every 30 min in the background
  ```
- **On GitHub**, the `release-check` workflow checks each run's release after its tag is pushed, and again daily. It
  fails, and GitHub emails you, if a release is missing, a draft, or incomplete.

Set `CARDIAC_SYNC_ON_START=0` in `.env` to turn off the sync when the results page starts.
