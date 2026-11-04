# Pending items

Open decisions and follow-ups for the user to come back to. Newest at the bottom of each section.
When one is settled, move it to **Resolved** with the date, the decision and the commit or run that implemented it.

## Open

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

### 10. Ischaemic-testing scope: stress echo, SPECT MPI, CMR code set, comparators off — resolved 2026-11-04
*Decision (user, after the 2026-11-04 biostatistics meeting and R1's scope comment):* (1) Echo becomes **stress echo**
93350 + 93351; resting TTE 93306–93308 is no longer counted. (2) SPECT confirmed as 78451 + 78452, relabelled
**SPECT MPI**. (3) Cardiac MRI = 75557 + 75558 + 75561 + 75562 plus stress CMR 75559 + 75560 + 75563 + 75564, legend
"Cardiac MRI (stress CMR included)"; the flow-mapping add-on 75565 is dropped (75558/75560/75562/75564 are retired CPT
codes with no rows). (4) ICA, TAVR and CACS comparators switched off for now (`config.INCLUDE_COMPARATORS`); their
code and tests stay. *Impact (2018→2024 rate change):* stress echo −28.8% (resting TTE was +6.8%), SPECT MPI −25.6%
(unchanged), CTA +277.9% (unchanged), CMR +150.9% (was +173.6% with the add-on), PET +81.8% (unchanged). Advanced share
of the five is now 27.0% in 2024 (was 6.0% when resting TTE dominated the denominator); SPECT MPI alone is 63.5%.
Table 1 CTA shares and every density IRR are unchanged (CTA-only models). 16 figures; the ranked CTA-change figure is
Figure 10. This also closes item 2 (scope of Echo and CTA): CTA stays 75574 only.
Run `ischemic-scope-stress-echo-cmr` (2026-11-04).

### 9. 2024 data and denominator — resolved 2026-11-02
*Decision (user):* 2024 replaces 2023 as the end year (`END_YEAR = GV_YEAR = 2024`); the 2024 state denominator is CMS
Program Statistics table MDCR ENROLL AB 14 (US 33,229,645), not KFF's 2024 figure (33,192,249, an earlier data vintage,
0.05–0.15% lower in every state). Checks: the 2018 and 2023 state denominators equal KFF's re-publication (2018 all
51 states; 2023 NV and SC differ by 1 person). *Data:* 2024 claims file `PHY_R26_P05_V10_D24_Prov_Svc.csv` (CMS
release R26, May 2026; 9,781,673 rows) converted to Parquet; `state_ffs_enrollment` now holds 2018, 2023 and 2024;
one header-based parser replaces the two per-year ones. *Impact (2018→2024 vs 2018→2023 rate change):* Echo +6.8%
(was +4.1%), SPECT −25.6% (−21.0%), CTA +277.9% (+199.4%), MRI +173.6% (+122.9%), PET +81.8% (+55.4%), ICA −15.3%
(−14.8%), TAVR +72.3% (+61.6%), CACS +554.1% (+374.4%). Adjusted density IRR, all providers 1.157 (was 1.188),
radiologists 1.230 (1.231), cardiologists 1.080 (1.157, now 50 states: WY is the only state without a cardiologist
CTA biller). Table 1 CTA: radiology 58.3% / cardiology 37.6%. Advanced share of imaging 6.0% in 2024.
Run `2026-11-02_205457_a538e15-dirty_end-year-2024`. Open: the 2018 claims file predates CMS's November 2025
re-release of 2013–2022 (see STUDY.md, Known limitations).
*Source confirmed (user, 2026-11-02):* CMS over KFF. The CMS Medicare Monthly Enrollment annual rows (`MONTH=Year`, `ORGNL_MDCR_BENES`) are the same series as AB 14 — 51-state total 33,229,774 vs 33,229,645 — so either file gives the same denominators; the loader keeps the AB 14 workbook. KFF 2024 is 0.05–0.15% lower in every state (uniform vintage lag, nothing concentrated), so it would not change any ranking or IRR.

### 1. Cardiac PET code set — resolved 2026-10-24
*Decision (user):* Cardiac PET = 78491, 78492, 78430, 78431 (myocardial perfusion PET, with or without concurrent CT).
Not counted: 78432/78433 (perfusion + metabolic, ~900 services/yr), 78429/78459 (metabolic/viability), 78434
(blood-flow add-on). *Impact:* 2023 PET services 98,752 → 234,098; 2018→2023 PET rate change −34.4% → +55.4%;
Advanced share of 2023 services 3.6% → 5.1%; Table 1 PET row now 85.5% cardiology / 4.4% radiology / 10.1% other.
CTA models, Table 1 CTA shares and all other modalities unchanged. Run `2026-10-24_162154_a9af40c-dirty_pet-codes-78430-78431`;
commit "Count PET/CT perfusion codes (78430/78431) as Cardiac PET".
