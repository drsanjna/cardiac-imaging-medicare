# Analysis plan H1: does Medicare Advantage selection inflate FFS cardiac imaging rates?

| | |
|---|---|
| Status | **Draft, not locked.** Locks when the user approves it and it is committed. The lock commit hash goes here: `TODO`. |
| Written | 2026-10-24 (Claude Code, for the user's review) |
| Label | **Post hoc** relative to the main study (raised after Figures 1–9 existed). Pre-specified relative to its own outcome: no H1 outcome has been queried. |
| Relation to main study | A validity check on every FFS rate in the paper (Figures 1, 3–7, the change summary), not a new headline result. |

## 1. Background and why it matters
FFS rates use FFS beneficiaries as the denominator. Over the study window, national MA participation among
beneficiaries with Part A and B rose from 38.6% (2018) to 52.9% (2023) (`gv_puf`, `MA_PRTCPTN_RATE`). MedPAC found that
people who switch from FFS to MA had 90–96% of the risk-adjusted FFS spending of those who stayed, in the year before
switching, every year from 2007 to 2020 (MedPAC, *MA selection*, Nov 2023,
https://www.medpac.gov/wp-content/uploads/2023/03/MA-selection-MedPAC-11.23.pdf). If imaging follows spending, the
remaining FFS population uses more imaging per person each year without any change in practice. A rate change from
2018 to 2023 would then mix real practice change with a changing population.

**Expected size (inference, not data).** Let *q* be the share of the would-be FFS population that leaves for MA and *r*
the leavers' imaging use relative to stayers. The stayers' rate is inflated by **1 / (1 − q(1 − r))**. Nationally the FFS
share fell from 0.614 to 0.4715, so q ≈ 0.232:

| r (leavers vs stayers) | 1.00 | 0.96 | 0.93 | 0.90 | 0.80 |
|---|---|---|---|---|---|
| Inflation of the 2023 rate vs 2018 | 0% | +0.9% | +1.7% | +2.4% | +4.9% |
| Implied IRR per 10 pp MA (from 45% MA) | 1.000 | 1.007 | 1.013 | 1.019 | 1.038 |

The MedPAC range (r = 0.90–0.96) predicts a **small** bias, about 1–2.5% over five years. r = 0.80 is a pessimistic
bound for imaging-specific selection that MedPAC did not measure. Two consequences shape this plan:
1. A 51-state panel is unlikely to detect an IRR of about 1.01, so a null result from the regression alone would
   not clear the paper. Part B (an analytic bound) is therefore pre-specified alongside the regression.
2. The bias matters most where an observed change is small (likely echo, SPECT). It is unlikely to explain large
   changes (likely CTA, PET); this is a prior, not a result.

## 2. Hypotheses (directional, stated before any outcome data)
- **H1 (primary).** Within a state over time, a 10-percentage-point higher MA participation rate is associated with a
  higher rate of FFS cardiac imaging services per 1,000 FFS beneficiaries (IRR > 1).
- **H1b (mechanism, secondary).** Adding the FFS population's composition (dual share, mean age, % female, % Black,
  % Hispanic) moves the H1 IRR toward 1. **Expected: little movement.** MedPAC's selection is on risk-adjusted cost,
  which is by construction not explained by these demographics. So non-attenuation does **not** refute H1.
- **Competing mechanism (opposite sign).** MA "spillover": physicians in high-MA markets may practice more
  conservatively for everyone, which would lower FFS rates (Baicker, Chernew & Robbins, *J Health Econ* 2013 [verify]).
  The H1 estimate is the net of selection and spillover. A null can mean the two cancel out.

## 3. Data (all already in `cms.duckdb`)
| Element | Source | Column(s) | Notes |
|---|---|---|---|
| Outcome numerator | `partb_provider_service` | `Tot_Srvcs`, `HCPCS_Cd`, `Rndrng_Prvdr_State_Abrvtn`, `year` | Modalities from `config.MODALITY_CASE`. Provider-address state. |
| Exposure | `gv_puf` (State, `BENE_AGE_LVL = 'All'`) | `MA_PRTCPTN_RATE` | Stored as a fraction (0.386); analyse as percentage points / 10. Equals `BENES_MA_CNT / BENES_WTH_PTAPTB_CNT` (checked nationally). |
| Primary denominator | `gv_puf` | `BENES_OM_CNT` | FFS beneficiaries with Part A **and** B; available every year 2014–2024, from the same source as the exposure. |
| Paper's denominator | `state_ffs_enrollment` | `ffs` | Only 2018 and 2023 are loaded, so it cannot serve a yearly panel. Used in sensitivity 7. |
| Composition covariates (H1b) | `gv_puf` | `BENE_DUAL_PCT`, `BENE_AVG_AGE`, `BENE_FEML_PCT`, `BENE_RACE_BLACK_PCT`, `BENE_RACE_HSPNC_PCT` | Step 0 confirms from the GV data dictionary that these describe FFS beneficiaries. |
| Positive control | `gv_puf` | `TOT_MDCR_STDZD_PYMT_PC` | Standardized FFS spending per capita. MedPAC's finding predicts it rises with MA. |
| Residence-based imaging | `gv_puf` (County) | `IMGNG_EVNTS_PER_1000_BENES`, `BENES_OM_CNT` | All imaging, not cardiac-specific, but located by beneficiary residence and free of the provider file's < 11 suppression. |

**Denominator discrepancy found while drafting (affects the main paper; see [PENDING.md](../PENDING.md) item 7).** The paper's state
denominator (CMS Program Statistics, Original Medicare) is larger than the GV PUF's FFS Part A & B count by **12.2% in
2018 and 16.0% in 2023** (37.99 M vs 33.37 M; 33.69 M vs 28.31 M). The likely cause is beneficiaries without Part B
(who cannot generate Part B claims), but this is not confirmed. If so, the paper's rates are deflated by a growing
amount: about 4.3% by 2023 relative to 2018, which is larger than the MA-selection bias in the table above.

## 4. Population and unit
- Unit: state-year. 50 states + DC (`config.EXCLUDED_AREAS` applied to the claims; GV rows `PR`, `VI`, `Territory`,
  `ZZ` dropped). Every drop is logged with `audit.log_filter`.
- Years: 2018–2023 (`config.BASE_YEAR`–`END_YEAR`): 51 × 6 = 306 state-years.
- **Precondition:** settle PENDING.md item 1 (PET code set) before the run. The run records which PET definition it
  used. H1 is not re-run under the other definition unless the user asks; any re-run is labelled post hoc.

## 5. Primary analysis (Part A, empirical)
- **Outcome:** all cardiac imaging services (sum of the five modalities) per state-year.
- **Model:** Poisson quasi-maximum likelihood with state and year fixed effects, offset log(`BENES_OM_CNT`),
  standard errors clustered by state (51 clusters).
  - *Why Poisson rather than the paper's NB2:* with fixed effects, Poisson QMLE is consistent whenever the mean is
    right, whatever the overdispersion (Wooldridge 1999 [verify]; Santos Silva & Tenreyro 2006 [verify]). NB2 with
    dummies is sensitivity 2.
  - *Why fixed effects:* state FE remove fixed state practice style and the provider-vs-resident geography gap, as far
    as it is stable. Year FE remove national shocks (COVID 2020, the 2021 chest pain guideline, payment changes).
    Identification comes only from states whose MA share grew faster or slower than the national trend.
- **Estimate:** IRR per 10 pp MA participation, 95% CI, two-sided p. One primary test at α = 0.05.
- **Interpretation rules, fixed now:**
  - IRR > 1 with CI excluding 1: supports H1.
  - CI includes 1 and its upper bound is < 1.04 per 10 pp: the data rule out selection worse than the r = 0.80 bound.
    Part B's bound then stands as the adjustment for the paper.
  - CI includes 1 and its upper bound is ≥ 1.04: **uninformative**, and reported as such. "No association" is not to be
    written.
  - IRR > 1.04 with CI excluding 1.04: selection exceeds the analytic bound. Part B is replaced by the empirical IRR
    for adjusting state rates (§7).

## 6. Secondary analyses (pre-specified, labelled secondary)
1. **Modality-specific H1:** the primary model separately for Echo, SPECT, CTA, MRI, PET. Holm correction across the five.
2. **H1b attenuation:** the primary model plus the five composition covariates. Report both IRRs and the % change in
   log IRR, with a 95% CI from a state-cluster bootstrap (2,000 resamples, seed fixed in config).
3. **Positive control:** the same model with `TOT_MDCR_STDZD_PYMT_PC` as the outcome (Poisson QMLE on the per-capita
   amount, weighted by `BENES_OM_CNT`). A null here means the design cannot see selection even in spending, so a null
   on imaging tells us nothing.
4. **Residence-based, county level:** county-year Poisson QMLE of `IMGNG_EVNTS_PER_1000_BENES` (weighted by
   `BENES_OM_CNT`, county + year FE, clustered by state) on county `MA_PRTCPTN_RATE`. Suppressed county cells are
   dropped and logged. Tests the mechanism with about 3,100 counties and correct geography, at the cost of being all
   imaging rather than cardiac imaging.

## 7. Part B: analytic bias bound on the paper's published changes
Not a hypothesis test; a deterministic recalculation of the paper's numbers, specified now so it cannot be tuned later.
- For each modality, recompute the 2018→2023 national rate change after dividing the 2023 rate by the composition
  factor 1 / (1 − q(1 − r)), for r ∈ {0.96, 0.93, 0.90, 0.80}, with q from national GV MA participation.
- Repeat per state using each state's own q, for the state rate changes behind Figures 3–7. Report: the number of
  states whose change flips sign, and the Spearman correlation of state changes before vs after adjustment.
- **Flag rule:** a modality or state is flagged when |observed % change| < the r = 0.80 inflation for that geography.
  Its change could then be explained entirely by selection, and the paper must say so.
- If §5 lands in the "selection exceeds the bound" case, use the empirical IRR in place of the formula.

## 8. Sensitivity analyses (all pre-specified)
| # | Change | Threat addressed |
|---|---|---|
| 1 | Drop 2020 and 2021 | COVID shocks that differ by state and could correlate with MA growth |
| 2 | NB2 with state and year dummies | Choice of count model |
| 3 | Add state-specific linear trends | States on different pre-existing paths |
| 4 | Add 2018 standardized FFS spending per capita × year | MA plans grow where FFS spending (and so MA benchmarks) is high |
| 5 | Exclude DC | Extreme cross-border care: provider state ≠ beneficiary state |
| 6 | Exposure lagged one year (uses GV 2017) | Timing of switching vs claims |
| 7 | Long difference 2018 vs 2023 with the paper's `state_ffs_enrollment` denominator | Shows the result on exactly the paper's rates |
| 8 | Leave-one-state-out; jackknife (CR3) SEs | Single influential states; few clusters |

Sensitivity results are reported in full whatever their direction. None replaces the primary estimate.

## 9. Known limitations to state in any write-up
- Ecological, state-level: no inference about individuals. "Associated with", never "caused".
- Numerator is located by provider address, denominator and exposure by residence; state FE absorb only the stable
  part of that gap.
- The provider file suppresses provider × code × setting rows with < 11 beneficiaries. If suppression changes as volume
  changes, it biases the numerator.
- The H1 estimate is the net of selection and spillover (§2); a null does not rule out either.
- Neighbouring states are not independent; clustering by state does not handle spatial correlation.
- Only 51 clusters; sensitivity 8 checks how much that matters.

## 10. Implementation (after approval; not done yet)
- Config (needs the user's approval, per CLAUDE.md): MA analysis years, the r grid {0.96, 0.93, 0.90, 0.80}, the
  1.04 decision threshold, the bootstrap seed and size.
- `src/cardiac_imaging/loaders/gv_panel.py`: state-year (and county-year) exposure, denominator, covariates, reusing
  `demographics._num` and the state resolver.
- `src/cardiac_imaging/analysis/ma_selection.py`: `fit_ppml_fe`, `composition_factor`, `bias_bounded_change`.
- Tests in `tests/`, with `tests/synthetic.py` extended to a panel with a known IRR so the estimator is shown to
  recover it.
- Outputs: `tables/ma_selection_*.csv` and one figure (IRR forest: primary, modalities, sensitivities), registered in
  `figures/catalog.py`.

## 11. Data access log (what had been seen when this was written)
- `gv_puf` schema, `BENE_AGE_LVL` values, state row counts per year, state codes present.
- National `MA_PRTCPTN_RATE` 2014–2024; national `BENES_TOTAL_CNT`, `BENES_WTH_PTAPTB_CNT`, `BENES_OM_CNT`,
  `BENES_MA_CNT` 2018–2023.
- Summed state denominators: `state_ffs_enrollment` vs GV `BENES_OM_CNT` / `BENES_WTH_PTAPTB_CNT`, 2018 and 2023.
- **Not seen:** any state- or county-level MA value; any H1 outcome (claims by state-year, GV imaging or spending
  columns); any model fit. The main study's published national and state rates exist in earlier runs, but were not
  read for this plan.

## 12. Deviations
Any change after locking is added here with the date, the reason, and the label "post hoc".
