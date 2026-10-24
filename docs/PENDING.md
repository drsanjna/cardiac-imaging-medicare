# Pending items

Open decisions and follow-ups for the user to come back to. Newest at the bottom of each section.
When one is settled, move it to **Resolved** with the date, the decision and the commit or run that implemented it.

## Open

### 1. Cardiac PET code set misses PET/CT codes (decision needed — changes `config.py`)
*Added 2026-10-24.* `config.py` defines Cardiac PET as 78491/78492 only. CPT added myocardial PET performed with
concurrent CT, 78429–78434, from 1 Jan 2020. Services in the claims table (50 states + DC):

| HCPCS | 2019 | 2020 | 2023 |
|---|---|---|---|
| 78492 (counted) | 194,534 | 150,919 | 98,674 |
| 78491 (counted) | 769 | 227 | 78 |
| 78431 PET/CT perfusion, multiple studies (not counted) | 0 | 32,630 | 135,139 |
| 78430 PET/CT perfusion, single study (not counted) | 0 | 109 | 207 |
| 78433 PET/CT perfusion + metabolic (not counted) | 0 | 534 | 934 |
| 78429 PET/CT metabolic (not counted) | 0 | 320 | 664 |
| 78434 absolute blood-flow **add-on** (not counted) | 0 | 35,221 | 117,251 |

As coded, PET appears to fall by about half after 2019; most of that is volume moving to the new codes.
- Decide: which codes define Cardiac PET (likely add 78430/78431/78432/78433; 78429 and 78459 are metabolic/viability —
  include or not; 78434 is an add-on and must not be counted as a separate study).
- Before approving, ask Claude for before/after numbers for PET, the "Advanced" total, Figures 1–2 and Table 1.
- Approval means `pytest -m real_data` pinned numbers change on purpose; update them in the same commit.

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

## Resolved
None yet.
