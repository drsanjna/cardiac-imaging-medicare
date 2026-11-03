# Work log

One entry per push to `main`, newest first — written automatically by `scripts/work_log.py` from commit messages, the diff and the test run.

## 2026-10-26 15:52 UTC — 3 commits (`4c05f61..b189d71`)

### What was done

- **Remove Figure S3 (density sensitivity forest plot)** (`6a9f67a`)
  - Removed at the user's request: the forest plot was hard to read. Figures S4-S6 show the same sensitivity analysis as scatter plots. The density_sensitivity_workforce table is kept (run page, Results).
  - STUDY.md outputs table now lists Figures S4-S6. Run 2026-10-26_113538_14c3944-dirty_remove-figure-S3.
- **Renumber supplement: workforce figures S4-S6 become S3-S5** (`65eb0f3`)
  - After removing the S3 forest plot, the workforce density figures are renumbered so the supplement runs S1-S5 without a gap: S3 = 2023 density, S4 = 2018 density, S5 = change-on-change 2018-2023.
  - File names, titles, catalog labels, pipeline, tests and STUDY.md updated. Run 2026-10-26_114718_6a9f67a-dirty_renumber-supplement.
- **Merge remote-tracking branch 'origin/main'** (`b189d71`)

### Where the changes landed

| Area | Files | + lines | − lines |
|---|---|---|---|
| code: core | 1 | 6 | 8 |
| code: figures | 4 | 8 | 73 |
| docs | 1 | 5 | 4 |
| tests | 6 | 10 | 10 |

### Impact on the code

- Removed functions (1): `src/cardiac_imaging/figures/forest.py: plot_sensitivity_forest`

### Tests

✅ 158 passed, 0 failed, 0 skipped.

## 2026-10-26 15:29 UTC — 3 commits (`7295757..14c3944`)

### What was done

- **Add Figures S4 and S5: radiologist + cardiologist density vs CTA rate, 2023 and 2018** (`f181cdf`)
  - Same layout as Figure S2, with the x-axis replaced by all unique radiologists + cardiologists billing any Part B service per 100,000 FFS beneficiaries (not selected by CTA billing). S4 is 2023, S5 is 2018, each with that year's claims, state FFS enrollment and age/sex covariates.
  - 2023: adjusted IRR 1.005 per +1 per 100k (1.37 per SD, 1.18-1.61), 60,976 physicians. 2018: 1.004 (1.24 per SD, 1.02-1.51, p=0.03), 57,343 physicians. Two cross-sections, not a within-state change.
  - The workforce loader takes a year; new table workforce_density_by_year; synthetic data gains 2018 covariates; tests and real-data pins. Run 2026-10-26_110728_5275a66-dirty_workforce-density-2018-2023.
- **Add Figure S6: change in workforce density vs change in CTA rate by state, 2018→2023** (`fef605d`)
  - Change-on-change test of whether states that gained radiologists/cardiologists also gained CTA use: Δ CTA rate per 1,000 FFS vs Δ physicians per 100,000 FFS, OLS with robust (HC3) SEs, with and without DC and MN.
  - Result as plotted: slope 0.038 (0.013-0.063), p=0.003; Spearman 0.51. But both axes share the FFS denominator, which fell ~11% in the median state while physician counts rose only ~4%, so the density change mostly reflects the shrinking denominator.
  - Count model that removes this (Δlog CTA ~ Δlog physicians + Δlog FFS): elasticity 1.10 (-2.18 to 4.37), p=0.51, so the change data neither support nor rule out workforce growth driving CTA growth. Shown on the figure.
  - New analysis.change module, figures.change, tables workforce_cta_change_by_state / _models; tests (including a synthetic recovery test) and real-data pins. Run 2026-10-26_112125_f181cdf-dirty_workforce-change-2018-2023.
- **Merge remote-tracking branch 'origin/main'** (`14c3944`)

### Where the changes landed

| Area | Files | + lines | − lines |
|---|---|---|---|
| code: analysis | 2 | 91 | 0 |
| code: core | 1 | 37 | 2 |
| code: db | 1 | 5 | 5 |
| code: figures | 3 | 90 | 0 |
| code: loaders | 2 | 16 | 11 |
| docs | 1 | 6 | 0 |
| tests | 8 | 75 | 5 |

### Impact on the code

- New functions (14): `src/cardiac_imaging/analysis/change.py: _coef`, `src/cardiac_imaging/analysis/change.py: _ols`, `src/cardiac_imaging/analysis/change.py: change_frame`, `src/cardiac_imaging/analysis/change.py: change_results_table`, `src/cardiac_imaging/analysis/change.py: fit_change_models`, `src/cardiac_imaging/figures/change.py: _p`, `src/cardiac_imaging/figures/change.py: plot_change_on_change`, `src/cardiac_imaging/loaders/providers.py: _workforce_where`, `tests/test_analysis.py: _wf`, `tests/test_analysis.py: test_change_count_model_recovers_elasticity`, `tests/test_analysis.py: test_change_frame_computes_state_changes`, `tests/test_loaders.py: test_workforce_density_frames_for_2018`, `tests/test_real_data.py: test_workforce_change_models`, `tests/test_real_data.py: test_workforce_density_by_year`

### Tests

✅ 158 passed, 0 failed, 0 skipped.

## 2026-10-26 14:49 UTC — 2 commits (`a72bbab..5275a66`)

### What was done

- **Show the workforce sensitivity table on the run page** (`fc91686`)
  - The density sensitivity table was only listed as a CSV download, so it could not be viewed on the run page. It now appears under Results, right after the original density models.
- **Merge remote-tracking branch 'origin/main'** (`5275a66`)

### Where the changes landed

| Area | Files | + lines | − lines |
|---|---|---|---|
| code: reporting | 1 | 2 | 0 |
| tests | 1 | 1 | 0 |

### Tests

✅ 155 passed, 0 failed, 0 skipped.

## 2026-10-26 14:29 UTC — 3 commits (`a5f7aea..748095c`)

### What was done

- **Sensitivity analysis for the provider-density models: whole-workforce exposure** (`124df83`)
  - Reviewer R2 says Figure 8/S1/S2 are circular: the exposure counts only NPIs that billed CTA, so total CTAs = billers x CTAs per biller links exposure and outcome by construction.
  - New post hoc sensitivity: same NB models (offset log FFS, age/sex adjusted) with the exposure replaced by all radiologists/cardiologists billing any Part B service in 2023 per 100,000 FFS. Membership no longer depends on CTA.
  - Result: the association holds. Adjusted IRR per +1 SD of density: all 1.66 (1.49-1.84) original vs 1.37 (1.18-1.61) workforce; radiology 1.44 vs 1.31; cardiology 1.32 vs 1.44. Unchanged without DC and Minnesota.
  - New table density_sensitivity_workforce (per +1 per 100k and per +1 SD); tests; real-data pins for the new IRRs; STUDY.md. Run 2026-10-26_093645_bb6724d-dirty_workforce-density-sensitivity.
- **Add Supplemental Figure S3: density sensitivity forest plot** (`5027b71`)
  - New forest plot comparing adjusted density IRRs (per +1 SD) for the original CTA-biller exposure and the whole radiology/cardiology workforce exposure, for all providers, radiologists and cardiologists.
  - Makes the response to R2's circularity concern visible as its own figure: all three IRRs stay above 1.
  - Catalog entry, pipeline wiring, figure counts in tests, STUDY.md. Run 2026-10-26_102439_124df83-dirty_figure-S3-sensitivity.
- **Merge remote-tracking branch 'origin/main'** (`748095c`)

### Where the changes landed

| Area | Files | + lines | − lines |
|---|---|---|---|
| code: analysis | 2 | 6 | 0 |
| code: core | 2 | 33 | 0 |
| code: db | 1 | 5 | 5 |
| code: figures | 3 | 67 | 2 |
| code: loaders | 2 | 53 | 2 |
| docs | 1 | 5 | 0 |
| tests | 7 | 51 | 4 |

### Impact on the code

- New functions (9): `src/cardiac_imaging/analysis/nb_models.py: irr_per_sd`, `src/cardiac_imaging/figures/forest.py: plot_sensitivity_forest`, `src/cardiac_imaging/loaders/providers.py: load_workforce_density_frames`, `src/cardiac_imaging/loaders/providers.py: national_workforce_counts`, `src/cardiac_imaging/pipeline.py: step_workforce_sensitivity`, `tests/test_analysis.py: test_irr_per_sd_rescales_point_and_ci`, `tests/test_loaders.py: test_national_workforce_counts`, `tests/test_loaders.py: test_workforce_density_frames_count_whole_specialties`, `tests/test_real_data.py: test_workforce_sensitivity_irrs`

### Tests

✅ 155 passed, 0 failed, 0 skipped.

## 2026-10-25 15:31 UTC — 2 commits (`5b9da6e..bb6724d`)

### What was done

- **Add TAVR to Figure 1 and as a new state map (Figure 11)** (`122c1e6`)
  - TAVR (CPT 33361–33366) is a second comparator procedure next to ICA: a Figure 1 column and its own state map, same layout as Figures 3–7. Kept out of the imaging definitions; imaging numbers are unchanged.
  - ICA and TAVR now share one code path (config.COMPARATORS, load_comparators, step_comparator_maps).
  - TAVR is usually billed by two co-surgeons (49% cardiology / 49% cardiac-thoracic surgery every year), so services ≈ 2 × procedures; stated on both figures and in STUDY.md.
  - Comparator maps no longer treat a state with no base-year rows as zero: Wyoming has no TAVR rows in 2018 (none or suppressed) and is shown grey with no change, instead of a false increase.
  - TAVR nationally: 64,891 → 92,986 services (+43.3%); rate per 1,000 FFS beneficiaries 1.71 → 2.76 (+61.6%).
  - Tests for comparators, missing-state deltas and the map footnote; real-data pin gains the TAVR row. Figures: run 2026-10-24_175530_edf94e1-dirty_tavr-figure1-and-map.
- **Merge remote-tracking branch 'origin/main'** (`bb6724d`)

### Where the changes landed

| Area | Files | + lines | − lines |
|---|---|---|---|
| code: analysis | 2 | 10 | 4 |
| code: core | 4 | 33 | 24 |
| code: db | 1 | 7 | 7 |
| code: figures | 4 | 51 | 19 |
| code: loaders | 2 | 22 | 12 |
| docs | 1 | 7 | 2 |
| tests | 8 | 50 | 21 |

### Impact on the code

- New functions (8): `src/cardiac_imaging/figures/choropleths.py: plot_comparator_state_maps`, `src/cardiac_imaging/loaders/claims.py: comparator_trend`, `src/cardiac_imaging/loaders/claims.py: load_comparator_detail`, `src/cardiac_imaging/loaders/claims.py: load_comparators`, `src/cardiac_imaging/pipeline.py: step_comparator_maps`, `tests/test_analysis.py: test_comparator_map_notes_states_without_base_year`, `tests/test_analysis.py: test_rate_deltas_can_keep_missing_states_missing`, `tests/test_loaders.py: test_load_comparators_and_trend`
- Removed functions (5): `src/cardiac_imaging/figures/choropleths.py: plot_ica_state_maps`, `src/cardiac_imaging/loaders/claims.py: ica_trend`, `src/cardiac_imaging/loaders/claims.py: load_ica_detail`, `src/cardiac_imaging/pipeline.py: step_ica_map`, `tests/test_loaders.py: test_load_ica_detail_and_trend`

### Tests

✅ 152 passed, 0 failed, 0 skipped.

## 2026-10-24 21:38 UTC — 4 commits (`b29719a..edf94e1`)

### What was done

- **Register hypotheses H1-H7 and add the H1 MA-selection analysis plan** (`a9af40c`)
  - Added docs/hypotheses/registry.json: seven numbered hypotheses (H1-H7) from the adjacent-dataset research, each with direction, linked public dataset, design and main threat. All are post hoc relative to the main study.
  - consolidate_hypotheses.py now renders the registry as a "Registered hypotheses" section at the top of HYPOTHESES.md, so hand-curated entries survive regeneration; tested in tests/test_scripts.py.
  - Added docs/hypotheses/H1_ma_selection.md, a draft (unlocked) pre-registered plan testing whether Medicare Advantage growth inflates FFS cardiac imaging rates, using GV PUF columns already in the database.
  - PENDING.md: new item 7 (the paper's denominator is 12-16% larger than the GV PUF's FFS Part A & B count, which may deflate 2023 rates by ~4.3%) and item 8 (approve and lock the H1 plan).
  - Regenerating the log also pulled in six existing chart discussions from the local app.
- **Count PET/CT perfusion codes (78430/78431) as Cardiac PET** (`8be88fb`)
  - Cardiac PET is now 78491, 78492, 78430, 78431. CPT 2020 moved PET perfusion done with concurrent CT to 78430/78431, so counting only 78491/78492 made PET look like it was disappearing.
  - Impact: 2023 PET services 98,752 → 234,098; 2018→2023 PET rate change −34.4% → +55.4%; Advanced share of 2023 services 3.6% → 5.1%. CTA models, Table 1 CTA shares and other modalities are unchanged.
  - Still excluded: 78432/78433 (perfusion + metabolic), 78429/78459 (metabolic), 78434 (blood-flow add-on).
  - Real-data PET pin updated; new config test; STUDY.md definitions and PENDING item 1 resolved. Figures: run 2026-10-24_162154_a9af40c-dirty_pet-codes-78430-78431.
- **Add invasive coronary angiography to Figure 1 and as a new state map (Figure 10)** (`5947fb4`)
  - Invasive coronary angiography (ICA, CPT 93454–93461) is a comparator, not an imaging modality, so it is kept out of the modality definitions: market share, Table 1, Traditional/Advanced totals and the state summary stay imaging-only.
  - Figure 1 has a sixth column for ICA. Figure 10 is an ICA state map with the same layout as Figures 3–7 (2018 / 2023 / change). New table ica_state_rates; change_summary gains an ICA row.
  - ICA nationally: 734,826 → 555,168 services (−24.4%); rate per 1,000 FFS beneficiaries 19.34 → 16.48 (−14.8%). Imaging numbers are unchanged.
  - Tests: ICA loader, change summary ordering, pipeline outputs; synthetic data has ICA rows; real-data pin gains the ICA row. Figures: run 2026-10-24_172521_8be88fb-dirty_ica-figure1-and-map.
- **Merge remote-tracking branch 'origin/main'** (`edf94e1`)

### Where the changes landed

| Area | Files | + lines | − lines |
|---|---|---|---|
| code: analysis | 2 | 5 | 5 |
| code: core | 4 | 37 | 5 |
| code: db | 1 | 8 | 8 |
| code: figures | 4 | 109 | 72 |
| code: loaders | 2 | 26 | 0 |
| docs | 6 | 362 | 29 |
| repo root | 1 | 1 | 0 |
| scripts | 2 | 28 | 3 |
| tests | 9 | 80 | 11 |

### Impact on the code

- New functions (12): `scripts/consolidate_hypotheses.py: load_registry`, `scripts/consolidate_hypotheses.py: render_registry`, `src/cardiac_imaging/figures/choropleths.py: map_stem`, `src/cardiac_imaging/figures/choropleths.py: plot_ica_state_maps`, `src/cardiac_imaging/figures/choropleths.py: plot_one_state_map`, `src/cardiac_imaging/loaders/claims.py: ica_trend`, `src/cardiac_imaging/loaders/claims.py: load_ica_detail`, `src/cardiac_imaging/pipeline.py: step_ica_map`, `tests/test_analysis.py: test_change_summary_adds_ica_after_imaging_modalities`, `tests/test_config.py: test_pet_codes_are_perfusion_pet_with_and_without_ct`, `tests/test_loaders.py: test_load_ica_detail_and_trend`, `tests/test_scripts.py: test_consolidate_hypotheses_registry`

### Tests

✅ 150 passed, 0 failed, 0 skipped.

## 2026-10-24 13:39 UTC — 1 commit (`46d4dab..e238aea`)

### What was done

- **Sync runs between laptops and verify every GitHub release** (`e238aea`)
  - reporting/sync.py: verify_release (every file present and non-empty, notes match the manifest), publish_reliably (publish, verify, repair, retry; failures kept as publish_error until the next sync), and a two-way sync (upload missing, download the other laptop's runs, newest label wins).
  - publish_run repairs partial releases (uploads only missing files, refreshes notes) instead of failing on "release exists"; clearing a label is now timestamped.
  - Every finished run publishes reliably and says whether GitHub is verified.
  - scripts/sync_runs.py: sync / --dry-run / --check / optional LaunchAgent schedule.
  - App: background sync on start (CARDIAC_SYNC_ON_START), "Sync now" button, "GitHub copy incomplete" notice, POST /api/sync.
  - CI: release-check.yml + scripts/check_releases.py check every run release on tag push and daily.
  - Tests (tests/test_sync.py) and docs (NEW_LAPTOP.md, CLAUDE.md, .env.example).

### Where the changes landed

| Area | Files | + lines | − lines |
|---|---|---|---|
| automation | 2 | 30 | 0 |
| code: app | 2 | 34 | 5 |
| code: core | 1 | 2 | 0 |
| code: reporting | 5 | 268 | 30 |
| docs | 1 | 23 | 0 |
| repo root | 3 | 6 | 1 |
| scripts | 4 | 202 | 0 |
| tests | 6 | 330 | 2 |

### Impact on the code

- New functions (41): `scripts/check_releases.py: check`, `scripts/check_releases.py: gh_json`, `scripts/check_releases.py: main`, `scripts/check_releases.py: problems_for`, `scripts/check_releases.py: repo_slug`, `scripts/sync_runs.py: install_schedule`, `scripts/sync_runs.py: main`, `scripts/sync_runs.py: plist_text`, `scripts/sync_runs.py: uninstall_schedule`, `src/cardiac_imaging/app/server.py: run_sync`, `src/cardiac_imaging/reporting/publish.py: _build_assets`, `src/cardiac_imaging/reporting/publish.py: expected_assets`, `src/cardiac_imaging/reporting/publish.py: record_from_body`, `src/cardiac_imaging/reporting/publish.py: release_info`, `src/cardiac_imaging/reporting/sync.py: _newer`, `src/cardiac_imaging/reporting/sync.py: _set_publish_error`, `src/cardiac_imaging/reporting/sync.py: publish_reliably`, `src/cardiac_imaging/reporting/sync.py: summarize`, `src/cardiac_imaging/reporting/sync.py: sync`, `src/cardiac_imaging/reporting/sync.py: verify_release`, `tests/test_sync.py: load`, `tests/test_sync.py: make_run`, `tests/test_sync.py: no_rebuild`, `tests/test_sync.py: release_for`, `tests/test_sync.py: runs` …

### Tests

✅ 146 passed, 0 failed, 0 skipped.

## 2026-10-24 12:39 UTC — 4 commits (`bca10d2..638101d`)

### What was done

- **Run page: summary at the top, development details in a bottom tab** (`5173be2`)
  - Each run page opens with its plain-English summary and a collapsible 'What changed & impact' (matching the main page).
  - Run details (code snapshot, data, versions), pipeline steps and files move into a collapsed Development tab at the bottom; the nav link and #details/#steps/#files links open it.
- **Two-tone landing page with run labels; run-page polish; second-laptop setup script** (`9d8cc02`)
  - Landing page redesigned for fast use: navy app bar, search, filter chips with counts (Active, Success, Failure, Needs review, Unlabeled, Archived, All), a compact run list beside the selected run's summary, headline IRRs, what changed / impact and actions; keyboard ↑/↓, Enter, /.
  - Runs can be marked Success, Failure, Needs review or Archived (POST /api/label). Labels are stored in the run's manifest and, for published runs, in its GitHub release notes so the other laptop sees them; archived runs are hidden from the default view.
  - Run pages share the navy/teal palette (navy header band) and show each figure's label and title above the chart.
  - scripts/setup_laptop.sh sets up another Mac end to end (tools check, clone outside iCloud, ~/jupyter-env, hooks, finds the data and writes per-laptop paths to .env, builds the database, runs tests incl. real-data checks, fetches run history, Claude login hints, opens the app). docs/NEW_LAPTOP.md explains it and what syncs.
  - Every command now reads the repo's .env (config.load_dotenv) so data paths can differ per laptop; ~ is expanded in path settings.
  - 8 new tests (130 total).
- **Add study protocol summary and pending-items tracker; link both from CLAUDE.md** (`525250e`)
  - docs/STUDY.md records the study as coded: question, design, data sources, HCPCS definitions, rate and density definitions, the NB2 models, the figure-to-manuscript map, known data limitations and the rules for writing the manuscript.
  - docs/PENDING.md tracks open decisions for the user, starting with the Cardiac PET code set, which misses the PET/CT codes (78429-78434) introduced in 2020, so PET looks like it halves after 2019.
  - CLAUDE.md now loads both files in every session and tells Claude to log new user decisions in PENDING.md.
  - Impact: documentation only; no analysis code, definitions or outputs change.
- **Merge remote-tracking branch 'origin/main'** (`638101d`)

### Where the changes landed

| Area | Files | + lines | − lines |
|---|---|---|---|
| code: app | 1 | 11 | 1 |
| code: core | 2 | 24 | 3 |
| code: reporting | 5 | 233 | 108 |
| docs | 3 | 202 | 0 |
| repo root | 2 | 9 | 1 |
| scripts | 3 | 163 | 1 |
| tests | 4 | 104 | 1 |

### Impact on the code

- New functions (12): `src/cardiac_imaging/config.py: load_dotenv`, `src/cardiac_imaging/reporting/gallery.py: development_html`, `src/cardiac_imaging/reporting/gallery.py: summary_html`, `src/cardiac_imaging/reporting/run_store.py: set_label`, `tests/test_app.py: test_server_label_endpoint`, `tests/test_config.py: test_load_dotenv_fills_unset_vars_only`, `tests/test_config.py: test_setup_script_is_valid_bash_and_documents_steps`, `tests/test_reporting.py: test_figure_title_above_chart`, `tests/test_reporting.py: test_gallery_layout_summary_top_development_bottom`, `tests/test_reporting.py: test_label_travels_to_github_notes_and_index`, `tests/test_reporting.py: test_landing_page_structure`, `tests/test_reporting.py: test_set_label_store_clear_and_validate`

### Tests

✅ 130 passed, 0 failed, 0 skipped.

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
