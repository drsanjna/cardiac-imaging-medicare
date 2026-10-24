# Hypotheses log

Consolidated 2026-10-24 from 6 chart discussion(s) and 13 Claude Code session(s) by `scripts/consolidate_hypotheses.py`. Edit `status_override` / `notes` in `hypotheses.json` to correct an entry.

## Registered hypotheses

Hand-curated in `registry.json`. Each is **post hoc** relative to the main study until its plan is locked.

| ID | Hypothesis | Linked data | Design | Main threat | Status |
|---|---|---|---|---|---|
| [H1](H1_ma_selection.md) | Within a state, +10 pp Medicare Advantage participation is associated with a higher FFS cardiac imaging rate per 1,000 FFS beneficiaries (IRR > 1), because people who stay in FFS cost more. | GV PUF (already loaded): MA_PRTCPTN_RATE, BENES_OM_CNT, BENE_DUAL_PCT; state + year | State-year Poisson QMLE with state and year FE, 2018–2023, plus an analytic bias bound on published changes | Expected effect is small (~1–2.5% over 2018–2023), so the panel may be underpowered; MA spillover pulls the other way | analysis plan drafted, not locked |
| H2 | After the Oct 2021 AHA/ACC chest pain guideline, the CTA trend steepened (+) and the SPECT trend fell further (−), with echo unchanged (negative control). | Already in hand: claims by HCPCS, state, year | Comparative interrupted time series by state-year; 2020 dropped or modelled; test a change in slope, not level | COVID recovery happens at the same time; only two post-guideline years | candidate (post hoc, no plan) |
| H3 | Cardiologists who gain a hospital affiliation or join a top-quartile-size group shift echo and SPECT from office to facility billing (+), with no change in total volume. | CMS Doctors & Clinicians file (archived releases): Org_PAC_ID, num_org_mem, hosp_afl_1–5; NPI | NPI-year staggered difference-in-differences on the switch year | Snapshots are not a clean panel; acquisition changes billing without changing where care happens | candidate (post hoc, no plan) |
| H4 | Physicians who first receive industry payments tied to a product (FFR-CT, PET tracer) bill more of the matching modality afterwards (+), with no change for unrelated products. | CMS Open Payments general payments: recipient NPI (2021+), product name; NPI + year | NPI-year event study on first payment; unrelated-product payments as negative control | Reverse causation (manufacturers target high-volume readers); suppression of low-volume rows | candidate (post hoc, no plan) |
| H5 | Counties with no cardiologist and low CT supply have a lower CTA-to-SPECT ratio than metro counties (−), with a wider rural gap for CTA, PET and MRI than for echo. | HRSA Area Health Resources File: cardiologist counts, CT supply; county FIPS | County cross-section, repeated by year, age/sex standardized | Provider-file suppression (< 11 beneficiaries) and provider-address geography push rural rates toward zero | candidate (post hoc, no plan) |
| H6 | HRRs with higher standardized SPECT + CTA rates have no lower 30-day AMI/HF mortality (slope ≈ 0). | Dartmouth ZIP→HRR crosswalk (2019); Care Compare MORT_30_AMI/HF via hospital CCN | HRR-year ecological analysis; descriptive, cannot support a causal claim | Imaging located by provider address, not patient; confounding by indication | candidate (post hoc, no plan) |
| H7 | The CY2025 hospital-outpatient payment rise for CTA (75574) increased facility CTA relative to office CTA and facility SPECT (+). | OPPS Addendum B by HCPCS + year (payment size unverified); needs the 2025 provider file | NPI- or state-year difference-in-differences | Untestable in the 2018–2023 window; the provider file never shows the facility payment | candidate (post hoc, no plan; data not yet released) |

## Tested through chart discussions

Tally: open: 6

| Date | Chart | Hypothesis | Outcome | What was concluded |
|---|---|---|---|---|
| 2026-10-24 | Figure 1 — Volume vs FFS enrollment vs utilization rate | what does this chart means ? | **open** | ## What Figure 1 shows It's a 3 × 5 grid. Each **column** is one modality (Echo, SPECT, Cardiac CTA, Cardiac MRI, Cardiac PET). Each **row** is one piece of the same calculation: | Row | Marker | What it is | Source | |---|---|---|---| | 1 | circles | **Volume**: total services billed per year (`Tot_Srvcs` summed) | Part B Physician & Other Practitioners file | | 2 | squares | **Denominator**: na… |
| 2026-10-24 | Figure 1 — Volume vs FFS enrollment vs utilization rate | what can I do next here ? | **open** | The most important next step is to check the PET finding before reading anything into it. The −34% PET decline may be a coding artifact, not a real drop in use. ## 1. Check the data before building hypotheses on it **a. PET codes (most important).** In `config.MODALITY_CASE` (`src/cardiac_imaging/config.py:79`), Cardiac PET is only `78491`/`78492`. CPT 2020 added PET codes with concurrently acqui… |
| 2026-10-24 | Figure 1 — Volume vs FFS enrollment vs utilization rate | what does this do ? | **open** | Figure 1 splits each modality's change in procedure count into two parts: how many people were in fee-for-service (FFS) Medicare, and how much each of them used the test. ## What the chart shows It's a 3 × 5 grid. Each column is one modality (CTA, MRI, PET, Echo, SPECT), and each row is one measure for 2018–2023: 1. **Volume (circles):** total Medicare Part B services billed for that modality. 2.… |
| 2026-10-24 | Figure 1 — Volume vs FFS enrollment vs utilization rate | what can be improved here ? | **open** | — |
| 2026-10-24 | Figure 1 — Volume vs FFS enrollment vs utilization rate | what column does this data uses ? | **open** | Figure 1 uses only a few columns. Most of the data model isn't involved. **From the claims view `partb_provider_service`** (pulled in `loaders.claims:load_detail`): | Column | Role in Figure 1 | |---|---| | `year` | x-axis; grouping key | | `HCPCS_Cd` | mapped to the five modalities through `config.MODALITY_CASE`, giving `procedure_category` (one column of panels per modality) | | `Tot_Srvcs` | *… |
| 2026-10-24 | Figure 2 — Modality market share by setting | hello | **open** | Hi. We're looking at **Figure 2: modality market share by setting**. It shows each modality's share of cardiac imaging volume (`Tot_Srvcs`) in four segments, urban or rural crossed with office or facility, for 2018–2023. Under each panel there's a zoomed view of CTA + CMR + PET. Here's how the chart is built, which limits what it can test: - **Shares, not rates.** `market_share_by_segment` divide… |

## Candidates raised in Claude Code conversations

None found so far (conversations have been about building the pipeline).
