# Work log

One entry per push to `main`, newest first — written automatically by `scripts/work_log.py` from commit messages, the diff and the test run.

## 2026-10-24 12:11 UTC — 1 commit (`40d1fc7..feff14e`)

### What was done

- **Discuss: live chat via the Claude app's Claude Code, Markdown replies, hand-off to the Claude app** (`feff14e`)
  - Live chat works without installing anything: when `claude` isn't on PATH the app uses the Claude Code copy bundled with the Claude desktop app, checks its login, and otherwise shows the exact one-time `auth login` command (no restart needed afterwards).
  - Fixed a hang: CLI calls inherited the server's open stdin and waited until the timeout (20 s on every page load, and every chat message); they now get stdin=/dev/null.
  - Chat messages render Markdown (headings, bold/italic, inline and fenced code, nested lists, links, quotes, tables, rules) via a new escape-first renderer, app/markdown.py — raw HTML and javascript: links can't execute.
  - "Continue in Claude app" button hands a discussion to the Claude desktop app (`claude --desktop --resume`, run under a pseudo-terminal) so it stays in the session sidebar; later panel messages continue on a fork so the two never interleave.
  - 22 new tests (122 total, 92% coverage): renderer elements and injection cases, CLI discovery/login, stdin handling, hand-off and fork behaviour, server endpoints.

### Where the changes landed

| Area | Files | + lines | − lines |
|---|---|---|---|
| code: app | 4 | 275 | 17 |
| code: reporting | 1 | 29 | 5 |
| tests | 3 | 244 | 4 |

### Impact on the code

- New functions (35): `src/cardiac_imaging/app/chat.py: _open_desktop`, `src/cardiac_imaging/app/chat.py: _version_key`, `src/cardiac_imaging/app/chat.py: claude_binary`, `src/cardiac_imaging/app/chat.py: claude_logged_in`, `src/cardiac_imaging/app/chat.py: open_in_claude_app`, `src/cardiac_imaging/app/chat.py: setup_hint`, `src/cardiac_imaging/app/chat.py: with_html`, `src/cardiac_imaging/app/markdown.py: _cells`, `src/cardiac_imaging/app/markdown.py: _emphasis`, `src/cardiac_imaging/app/markdown.py: _inline`, `src/cardiac_imaging/app/markdown.py: _list_html`, `src/cardiac_imaging/app/markdown.py: render`, `tests/test_app.py: _claude_code_conv`, `tests/test_app.py: test_claude_binary_prefers_path_then_newest_bundled`, `tests/test_app.py: test_claude_code_backend_unavailable_when_logged_out`, `tests/test_app.py: test_claude_logged_in_reads_auth_status`, `tests/test_app.py: test_cli_calls_never_inherit_stdin`, `tests/test_app.py: test_open_desktop_uses_pty_and_no_stdin`, `tests/test_app.py: test_open_in_claude_app_errors`, `tests/test_app.py: test_open_in_claude_app_hands_off_and_follow_ups_fork`, `tests/test_app.py: test_server_open_in_app_endpoint`, `tests/test_app.py: test_setup_hint_when_bundled_cli_not_logged_in`, `tests/test_markdown.py: test_blockquote_and_rule`, `tests/test_markdown.py: test_code_block_is_escaped_and_tagged`, `tests/test_markdown.py: test_empty_and_none` …

### Tests

✅ 122 passed, 0 failed, 0 skipped.

## 2026-10-24 10:53 UTC — 1 commit (`ca9e052..b878a1b`)

### What was done

- **Add physician-scientist role to the Claude Code instructions** (`b878a1b`)
  - CLAUDE.md now opens with a Role section: senior physician-scientist and data researcher persona for every Claude Code session in this repo.
  - It sets how analyses are run (pre-specified hypotheses and outcomes, data profiling before modelling, effect sizes with CIs, sensitivity analyses by default) and how results are communicated.
  - Impact: instructions only; no analysis code, data definitions or outputs change.

### Where the changes landed

| Area | Files | + lines | − lines |
|---|---|---|---|
| code: app | 1 | 17 | 2 |
| repo root | 1 | 49 | 0 |
| tests | 1 | 23 | 1 |

### Tests

❌ 99 passed, 1 failed, 0 skipped.

## 2026-10-24 09:57 UTC — 4 commits (`2bb9222..28424d2`)

### What was done

- **Simple results page with restore, zoomable charts, chart discussions, tests and work log** (`bddf974`)
  - Main page shows each run's time, a plain-English summary of the results and three actions: open charts, what changed & impact (code/data/settings changes vs the previous run and how headline numbers moved), and one-click Restore with Undo and Push. Execution details move into each run's record (local + GitHub notes).
  - New local app (python -m cardiac_imaging.app): serves the history and a token-protected localhost API for restore/undo/push/download and chat; restore backs up the current code as a tag first and commits the run's snapshot.
  - Charts: full zoom viewer (wheel, pinch, drag, double-click, +/−/fit); state maps also saved as interactive HTML.
  - "Discuss a hypothesis" on every chart: chat with Claude that starts from the exact code that drew the chart (at the run's snapshot), its tables and the data model; uses Claude Code CLI, the Anthropic API, or a copyable prompt. Outcomes are recorded; scripts/consolidate_hypotheses.py writes docs/hypotheses/.
  - Data model in db/schema.py with meaning and usage of every column; rendered into db/README.md (ER diagram, which functions use each column) and checked against the real database by build_database.py and tests.
  - Every function now has a docstring (60 added); READMEs list all functions, including tests; pre-commit and CI enforce it.
  - Test suite: 100 synthetic-data tests (91% coverage) covering every layer, plus 6 real-data tests pinning the published IRRs, Table 1 shares, model sizes, change summary and row counts. Tests scrub git hook variables so they can never touch the real repo.
  - post-push workflow replaces readme-sync: docstring rule + tests (coverage ≥ 85%) + READMEs, and on main an English work-log entry in docs/WORK_LOG.md.
  - Fixes found by the tests: TIFF DPI settings now read at call time; restoring with only unsaved edits no longer errors; chart context falls back to current code when a snapshot lacks it.
- **Keep 'What changed' panels open when the page refreshes from GitHub** (`c783514`)
  - The results page re-renders after loading runs from GitHub; open panels used to snap shut. Open state is now remembered per run.
- **Fix chart-card button styling; add initial hypotheses log** (`4af5f8e`)
  - The image-button style also hit the new Zoom/Discuss buttons, turning them into full-width white bars; it is now scoped to the chart image only.
  - docs/hypotheses/ created by scripts/consolidate_hypotheses.py (no hypotheses recorded yet).

### Where the changes landed

| Area | Files | + lines | − lines |
|---|---|---|---|
| automation | 5 | 78 | 48 |
| code: analysis | 2 | 4 | 1 |
| code: app | 6 | 635 | 0 |
| code: core | 4 | 37 | 10 |
| code: db | 2 | 223 | 0 |
| code: figures | 6 | 70 | 18 |
| code: loaders | 4 | 12 | 0 |
| code: reporting | 6 | 521 | 141 |
| docs | 3 | 42 | 0 |
| other | 1 | 3 | 3 |
| repo root | 4 | 57 | 3 |
| scripts | 8 | 577 | 36 |
| tests | 14 | 1783 | 0 |

### Impact on the code

- New functions (215): `scripts/check_docs.py: main`, `scripts/check_docs.py: missing_docstrings`, `scripts/check_docs.py: source_files`, `scripts/consolidate_hypotheses.py: clean`, `scripts/consolidate_hypotheses.py: from_chart_discussions`, `scripts/consolidate_hypotheses.py: from_claude_code`, `scripts/consolidate_hypotheses.py: main`, `scripts/consolidate_hypotheses.py: merge`, `scripts/consolidate_hypotheses.py: render`, `scripts/consolidate_hypotheses.py: rid`, `scripts/consolidate_hypotheses.py: transcripts_dir`, `scripts/consolidate_hypotheses.py: user_texts`, `scripts/runs.py: refresh_all`, `scripts/update_readmes.py: column_usage`, `scripts/update_readmes.py: data_model_section`, `scripts/update_readmes.py: load_schema`, `scripts/work_log.py: area`, `scripts/work_log.py: bullets`, `scripts/work_log.py: entry`, `scripts/work_log.py: functions_at`, `scripts/work_log.py: git`, `scripts/work_log.py: main`, `scripts/work_log.py: prepend`, `scripts/work_log.py: resolve_range`, `scripts/work_log.py: test_counts` …

### Tests

✅ 100 passed, 0 failed, 0 skipped.
