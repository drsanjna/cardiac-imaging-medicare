# Pending items

Open decisions and follow-ups for the user to come back to. Newest at the bottom of each section.
When one is settled, move it to **Resolved** with the date, the decision and the commit or run that implemented it.

## Open

### 2. Confirm the scope of Echo and CTA (Methods wording)
*Added 2026-10-24.* Echo is resting TTE only (excludes stress echo 93350/93351, ~200k/yr, and TEE 93312). CTA is
coronary CTA 75574 only (excludes calcium score 75571, structural CT 75572/75573, FFR-CT 0501T). Confirm these are
intended and state them in Methods.

### 3. Fill in the study TODOs in `docs/STUDY.md`
*Added 2026-10-24.* Primary hypothesis (with direction), primary outcome, and target journal.

### 4. Density models: exposure and outcome come from the same rows
*Added 2026-10-24.* Density = CTA-billing NPIs per 100k; outcome = those NPIs' CTA services. Decide on an independent
workforce measure for a sensitivity analysis (e.g. all radiologists/cardiologists billing any Part B service in the
state, or an external workforce file) and whether to pre-specify it.

### 5. Add the Role to the app's API chat prompt
*Added 2026-10-24.* The Claude Code chat path picks up CLAUDE.md; the Anthropic API path in `app/chat.py` builds its own
system prompt and does not. Do once the chat work is committed.

### 6. Write `docs/ANALYSIS_PLAN.md`
*Added 2026-10-24.* Primary/secondary outcomes, pre-specified sensitivity analyses (exclude 2020; PET code set;
independent density measure; spatial dependence), labelled pre-specified vs post hoc. Depends on items 1–4.

### 7. State denominator may include beneficiaries without Part B (decision needed — affects every rate)
*Added 2026-10-24.* The paper's denominator (CMS Program Statistics, Original Medicare) exceeds the GV PUF's FFS
Part A & B count (`BENES_OM_CNT`) by 12.2% in 2018 (37.99 M vs 33.37 M) and 16.0% in 2023 (33.69 M vs 28.31 M).
If the gap is people without Part B, who cannot generate Part B claims, the paper's 2023 rates are deflated by
about 4.3% relative to 2018, uniformly across modalities. Confirm the cause from both data dictionaries, then
decide whether to switch denominators or report the alternative as a sensitivity analysis. Changing the
denominator changes pinned `real_data` numbers.
- *Update 2026-10-24 (cause confirmed):* both workbooks count Original Medicare "Part A **and/or** Part B" enrollees
  (person-year), so people without Part B are in the denominator. CMS table **MDCR ENROLL AB 13** (in the "Original
  Medicare Enrollment" zip, tables 9–14) gives per-state **Part B Total** and **Part A and Part B Total** columns for
  each year. US 2023: A and/or B 33,694,472; Part B 28,516,856; A and B 28,209,170. US 2024: 33,229,645; 27,875,552;
  27,567,891. From 2024 CMS excludes Part B immunosuppressive-drug-only (PBID) beneficiaries from Part B counts.

### 8. Approve and lock the H1 (MA-selection) analysis plan
*Added 2026-10-24.* Draft: [hypotheses/H1_ma_selection.md](hypotheses/H1_ma_selection.md). Needs: a review,
approval of its proposed config entries (years, r grid, 1.04 threshold, bootstrap seed), item 1 settled first, then
a commit whose hash is recorded in the plan before any H1 outcome is queried.

## Resolved

### 1. Cardiac PET code set — resolved 2026-10-24
*Decision (user):* Cardiac PET = 78491, 78492, 78430, 78431 (myocardial perfusion PET, with or without concurrent CT).
Not counted: 78432/78433 (perfusion + metabolic, ~900 services/yr), 78429/78459 (metabolic/viability), 78434
(blood-flow add-on). *Impact:* 2023 PET services 98,752 → 234,098; 2018→2023 PET rate change −34.4% → +55.4%;
Advanced share of 2023 services 3.6% → 5.1%; Table 1 PET row now 85.5% cardiology / 4.4% radiology / 10.1% other.
CTA models, Table 1 CTA shares and all other modalities unchanged. Run `2026-10-24_162154_a9af40c-dirty_pet-codes-78430-78431`;
commit "Count PET/CT perfusion codes (78430/78431) as Cardiac PET".
