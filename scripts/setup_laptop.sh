#!/usr/bin/env bash
# Set up this project on another Mac so you can pick up the research exactly where you left off.
#
#   curl -fsSL https://raw.githubusercontent.com/drsanjna/cardiac-imaging-medicare/main/scripts/setup_laptop.sh -o setup_laptop.sh
#   bash setup_laptop.sh            # or: bash scripts/setup_laptop.sh   (from inside a clone)
#
# Safe to re-run: every step checks what's already done. It never deletes anything.
# Options:  --repo-dir DIR  (default ~/code/cardiac-imaging-medicare)   --data-dir DIR  (where your CMS downloads are; default ~/Downloads)
#           --skip-runs  (don't download past runs from GitHub)          --no-app  (don't start the app at the end)
set -euo pipefail

REPO_SLUG="drsanjna/cardiac-imaging-medicare"
REPO_DIR="$HOME/code/cardiac-imaging-medicare"
DATA_DIR="$HOME/Downloads"
VENV="${CARDIAC_PYTHON_ENV:-$HOME/jupyter-env}"
SKIP_RUNS=0; START_APP=1
while [ $# -gt 0 ]; do
  case "$1" in
    --repo-dir) REPO_DIR="$2"; shift 2 ;;
    --data-dir) DATA_DIR="$2"; shift 2 ;;
    --skip-runs) SKIP_RUNS=1; shift ;;
    --no-app) START_APP=0; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "Unknown option $1"; exit 1 ;;
  esac
done

bold() { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  ✓ %s\n' "$*"; }
todo() { printf '  → %s\n' "$*"; TODO+=("$*"); }
die()  { printf '\n✗ %s\n' "$*" >&2; exit 1; }
TODO=()

bold "1/8  Checking this Mac"
[ "$(uname -s)" = "Darwin" ] || die "This script is for macOS."
free_gb=$(df -g "$HOME" | awk 'NR==2 {print $4}')
[ "${free_gb:-0}" -ge 5 ] && ok "free disk space: ${free_gb} GB" || todo "Only ${free_gb} GB free — the Parquet data needs ~2.1 GB plus working space (5 GB+ recommended)."
xcode-select -p >/dev/null 2>&1 && ok "Xcode command line tools (git)" || die "Install the command line tools first:  xcode-select --install   — then re-run."
PY=""
for c in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then PY="$(command -v "$c")"; break; fi
done
[ -n "$PY" ] && ok "Python: $("$PY" --version)" || die "Python 3.10+ is needed:  brew install python@3.12   (Homebrew: https://brew.sh) — then re-run."
if command -v gh >/dev/null; then
  ok "GitHub CLI: $(gh --version | head -1)"
  gh auth status >/dev/null 2>&1 && ok "GitHub CLI logged in" || todo "Log in to GitHub (needed to publish runs and fetch history):  gh auth login"
else
  todo "Install the GitHub CLI (publishing runs, run history):  brew install gh && gh auth login"
fi

bold "2/8  Getting the code"
case "$REPO_DIR" in "$HOME/Desktop"*|"$HOME/Documents"*)
  echo "  ! $REPO_DIR may be synced by iCloud (it caused hangs and duplicate git files on the first laptop)."
  echo "    Prefer the default ~/code/cardiac-imaging-medicare unless iCloud Desktop & Documents sync is off." ;;
esac
if [ -d "$REPO_DIR/.git" ]; then
  git -C "$REPO_DIR" pull --ff-only -q && ok "updated $REPO_DIR" || todo "Could not fast-forward $REPO_DIR (local changes?) — run: git -C \"$REPO_DIR\" status"
else
  mkdir -p "$(dirname "$REPO_DIR")"
  if command -v gh >/dev/null && gh auth status >/dev/null 2>&1; then gh repo clone "$REPO_SLUG" "$REPO_DIR" -- -q
  else git clone -q "https://github.com/$REPO_SLUG.git" "$REPO_DIR"; fi
  ok "cloned into $REPO_DIR"
fi
cd "$REPO_DIR"

bold "3/8  Python environment ($VENV)"
[ -x "$VENV/bin/python" ] || "$PY" -m venv "$VENV"
"$VENV/bin/python" -m pip install -q --upgrade pip
"$VENV/bin/python" -m pip install -q -e ".[notebook,test]"
ok "packages installed (editable) into $VENV"
sh scripts/install_hooks.sh >/dev/null && ok "git hooks on (docstrings, READMEs, quick tests before each commit)"
git config user.name >/dev/null || todo "Set your git identity:  git config --global user.name \"Your Name\" && git config --global user.email you@example.com"

bold "4/8  Finding your data (in $DATA_DIR)"
find_file() { find "$DATA_DIR" -maxdepth 3 -type f -name "$1" -size +0 2>/dev/null | sort | head -1; }
PARQUET_DIR="${CMS_PARQUET_DIR:-$DATA_DIR/cms_parquet}"
n_pq=$(ls "$PARQUET_DIR"/20??__*.parquet 2>/dev/null | wc -l | tr -d ' ')
missing=()
if [ "$n_pq" -ge 6 ]; then ok "Parquet already present: $n_pq files in $PARQUET_DIR (CSVs not needed)"
else
  CSV_DIR=""
  for y in 2018 2019 2020 2021 2022 2023; do
    f=$(find_file "Medicare_Physician_Other_Practitioners_by_Provider_and_Service_$y.csv")
    [ -n "$f" ] && CSV_DIR="${CSV_DIR:-$(dirname "$f")}" || missing+=("Medicare_Physician_Other_Practitioners_by_Provider_and_Service_$y.csv  (CMS 'Medicare Physician & Other Practitioners — by Provider and Service', $y)")
  done
  [ ${#missing[@]} -eq 0 ] && ok "all 6 yearly claims CSVs found"
fi
ENR18=$(find_file "original medicare enrollment 2018.xlsx"); ENR23=$(find_file "original medicare enrollment 2023.xlsx")
GV=$(find_file "Medicare_GV_by_National_State_County*.csv")
[ -n "$ENR18" ] || missing+=("original medicare enrollment 2018.xlsx  (CMS Original Medicare enrollment by state, 2018)")
[ -n "$ENR23" ] || missing+=("original medicare enrollment 2023.xlsx  (CMS Original Medicare enrollment by state, 2023)")
[ -n "$GV" ]    || missing+=("Medicare_GV_by_National_State_County_….csv  (CMS 'Medicare Geographic Variation — by National, State & County')")
if [ ${#missing[@]} -gt 0 ]; then
  echo "  These files are missing from $DATA_DIR (or one folder below it):"
  for m in "${missing[@]}"; do echo "     • $m"; done
  echo "  Download them (or copy them, or the whole ~/Downloads/cms_parquet folder, from the other laptop) and re-run this script."
  echo "  Everything else is set up."
  exit 2
fi
[ -n "$ENR18" ] && ok "enrollment workbooks: $(dirname "$ENR18")"
ok "GV PUF: $GV"
# Per-laptop paths go in .env (gitignored); every command in the project reads it.
{
  echo "# Written by scripts/setup_laptop.sh on $(date '+%Y-%m-%d') for $(hostname -s) — data locations on this laptop"
  [ -n "${CSV_DIR:-}" ] && echo "CMS_CSV_DIR=\"$CSV_DIR\""
  echo "CMS_PARQUET_DIR=\"$PARQUET_DIR\""
  echo "CMS_REFERENCE_DIR=\"$(dirname "$ENR18")\""
  echo "CMS_GV_GLOB=\"$GV\""
  echo "CARDIAC_RUNS_DIR=\"$DATA_DIR/cms_runs\""
  echo "CARDIAC_CONVERSATIONS_DIR=\"$DATA_DIR/cms_conversations\""
} > .env.setup
if [ -f .env ]; then
  echo "  .env already exists — new paths saved to .env.setup for you to compare (yours is kept)."
else mv .env.setup .env && ok "data paths saved to .env (this laptop only)"; fi

bold "5/8  Building the database"
set -a; . ./.env 2>/dev/null || true; set +a
if [ "$n_pq" -lt 6 ]; then
  CMS_CSV_DIR="$CSV_DIR" "$VENV/bin/python" scripts/convert_cms_to_parquet.py
fi
"$VENV/bin/python" scripts/build_database.py
ok "cms.duckdb ready and matches the data model"

bold "6/8  Checking the results match the first laptop"
if "$VENV/bin/python" -m pytest -q -p no:cacheprovider -m "not real_data" -x --no-cov >/tmp/cardiac_setup_tests.log 2>&1; then
  ok "test suite passed ($(tail -1 /tmp/cardiac_setup_tests.log))"
else todo "Some tests failed — see /tmp/cardiac_setup_tests.log"; fi
if "$VENV/bin/python" -m pytest -q -p no:cacheprovider -m real_data --no-cov | tail -1 | grep -q passed; then
  ok "real-data checks passed: published IRRs, Table 1 shares, model sizes and row counts reproduce exactly"
else
  todo "Real-data checks did not pass — run:  $VENV/bin/python -m pytest -m real_data   and look at the differences"
fi

bold "7/8  Run history and Claude"
if [ "$SKIP_RUNS" = 0 ] && command -v gh >/dev/null && gh auth status >/dev/null 2>&1; then
  "$VENV/bin/python" scripts/runs.py fetch --all | tail -1 && ok "past runs downloaded from GitHub"
else ok "skipped downloading past runs (they still show on the results page, loaded from GitHub)"; fi
CLAUDE_BIN=$(command -v claude || "$VENV/bin/python" -c "from cardiac_imaging.app.chat import claude_binary; print(claude_binary() or '')")
if [ -n "$CLAUDE_BIN" ]; then
  if "$CLAUDE_BIN" auth status </dev/null 2>/dev/null | grep -q '"loggedIn": true'; then ok "Claude Code logged in — 💬 Discuss uses live chat"
  else todo "Turn on live chat in Discuss (one-time):  \"$CLAUDE_BIN\" auth login"; fi
else
  todo "For live chat in Discuss: install the Claude desktop app (or: brew install --cask claude-code), then run: claude auth login"
fi
todo "In the Claude app → Code, open the folder $REPO_DIR — CLAUDE.md there gives Claude the project rules, so it works the same as on the first laptop."
echo "  Note: chart discussions are saved per laptop (in $DATA_DIR/cms_conversations); runs, labels and code sync through GitHub."

bold "8/8  Done"
if [ ${#TODO[@]} -gt 0 ]; then echo "  Still to do:"; for t in "${TODO[@]}"; do echo "   • $t"; done; fi
echo "  Results page:  cd \"$REPO_DIR\" && $VENV/bin/python -m cardiac_imaging.app"
echo "  New run:       cd \"$REPO_DIR\" && $VENV/bin/python -m cardiac_imaging.pipeline"
if [ "$START_APP" = 1 ]; then
  echo "  Starting the results page… (Ctrl+C to stop)"
  exec "$VENV/bin/python" -m cardiac_imaging.app
fi
