# Study protocol summary

What this repo is building toward: a research paper on cardiac imaging use in Medicare fee-for-service, 2018–2023.
Definitions here describe what the code does today; `src/cardiac_imaging/config.py` remains the single source of truth.
Open decisions live in [PENDING.md](PENDING.md).

## At a glance
| | |
|---|---|
| Question | How did use of Echo, SPECT, cardiac CTA, cardiac MRI and cardiac PET change in Medicare FFS from 2018 to 2023, nationally and by state, and is state CTA use associated with the density of physicians who bill for CTA? |
| Primary hypothesis | TODO (user): state it, with direction, before further analysis. |
| Primary outcome | TODO (user): e.g. change in CTA services per 1,000 FFS beneficiaries 2018→2023, or the adjusted density IRR. |
| Design | Serial cross-sectional (national and state trends) + state-level ecological regression (density models). |
| Population | Medicare FFS Part B services rendered in the 50 states + DC. Territories and invalid state codes excluded. |
| Years | 2018–2023 (`BASE_YEAR`–`END_YEAR`); density models use 2023 only. |
| Target journal | TODO (user). TIFF settings follow JACC artwork rules, so a JACC-family journal is assumed until confirmed. |
| Reporting checklist | RECORD (STROBE extension for routinely collected health data). |

## Data sources
| Table | Source | Used for |
|---|---|---|
| `partb_provider_service` | CMS Medicare Physician & Other Practitioners — by Provider and Service PUF, one file per year | Numerators (services), provider counts, specialty, RUCA, place of service |
| `state_ffs_enrollment` | CMS Program Statistics — Original Medicare enrollment by state | State denominators |
| `MEDICARE_ENROLLMENT` (config) | CMS Program Statistics — national Original Medicare enrollment | National denominators |
| `gv_puf` | CMS Medicare Geographic Variation PUF, 2023 | State mean beneficiary age and % female (model covariates) |

## Definitions (as coded)
| Modality | HCPCS | Group |
|---|---|---|
| Echo | 93306, 93307, 93308 (resting TTE only) | Traditional |
| SPECT | 78451, 78452 | Traditional |
| Cardiac CTA | 75574 (coronary CTA only) | Advanced |
| Cardiac MRI | 75557–75565 | Advanced |
| Cardiac PET | 78491, 78492 (PET); 78430, 78431 (PET with concurrent CT, from 2020) | Advanced |
| Invasive coronary angiography (comparator, not imaging) | 93454–93461 (diagnostic cath with coronary angiography) | — |

ICA (added 2026-10-24) appears only in Figure 1 and Figure 10. It is kept out of the modality definitions, so market
share, Table 1, the Traditional/Advanced totals and the state summary stay imaging-only. Codes stable 2018–2023; 98–99%
billed in facilities, so rows are the professional component. PCI codes (92920–92944) are not included.

Codes deliberately or possibly out of scope (must be stated in Methods): stress echo 93350/93351, TEE 93312,
calcium score 75571, structural cardiac CT 75572/75573, FFR-CT 0501T–0504T; PET perfusion + metabolic 78432/78433,
metabolic/viability PET 78429/78459, and the absolute blood-flow add-on 78434 (an add-on to a perfusion study, so
never counted as a separate study). PET codes set by the user on 2026-10-24 (PENDING.md, Resolved).

- **Rate**: services (`Tot_Srvcs`) per 1,000 FFS beneficiaries. Nationally: national FFS enrollment; by state: state FFS
  enrollment.
- **Specialty groups**: Radiology = Diagnostic Radiology, Nuclear Medicine, Interventional Radiology. Cardiology =
  Cardiology, Interventional Cardiology, Clinical Cardiac Electrophysiology, Advanced Heart Failure and Transplant
  Cardiology. Everyone else = Other.
- **Rural/urban**: rendering provider's ZIP RUCA, ≤ 3 urban, > 3 rural; unknown RUCA dropped from segment analyses only.
- **Setting**: `Place_Of_Srvc` F (facility) / O (office).

## Models (Figures 8, 9, S1, S2)
- Unit: state (≤ 51). Outcome: 2023 CTA service count. Offset: log state FFS enrollment. Family: negative binomial
  (NB2), Poisson start values.
- Exposure: CTA-billing NPIs per 100,000 FFS beneficiaries — all providers (Fig 8), radiology (S1), cardiology (S2).
  Density is in natural units, so the IRR is per 1 additional CTA-billing NPI per 100,000 beneficiaries.
- Covariates: state mean beneficiary age and % female (z-scored). Unadjusted and adjusted IRRs both reported; VIFs
  checked (> 5 flags collinearity).
- Specialty models keep only states with ≥ 1 specialty CTA biller (logged in `filter_log`).

## Outputs → manuscript
| Output | Content |
|---|---|
| Figure 1 | Volume vs FFS enrollment vs rate, by modality plus ICA, 2018–2023 |
| Figure 2 | Modality share by rural/urban × office/facility |
| Figures 3–7 | State rate maps 2018 / 2023 / change, one per modality |
| Figure 8 | All-provider density vs CTA rate, NB fits |
| Figure 9 | Forest plot of density IRRs, unadjusted vs adjusted |
| Figure 10 | Invasive coronary angiography state rate maps 2018 / 2023 / change |
| Table 1 | Specialty distribution (Cardiology / Radiology / Other) by modality |
| Figures S1–S2 | Radiologist and cardiologist density models |
| Composite | 2023 state rates, all modalities (candidate Central Illustration) |

## Known limitations — check every claim against these
- **Small-cell suppression**: the PUF omits provider × HCPCS × place-of-service rows with < 11 beneficiaries. Counts are
  undercounts, most in low-volume (often rural, small) states, and NPIs with few CTAs are invisible to the density measure.
- **Geography mismatch**: services are assigned to the rendering provider's state, enrollment to the beneficiary's state
  of residence. Cross-border care (e.g. DC, states served by neighbouring academic centres) distorts state rates.
- **FFS only, shrinking denominator**: national FFS enrollment fell from 38.0 M (2018) to 33.7 M (2023) as Medicare
  Advantage grew, unevenly by state. A rate change mixes practice change with a changing FFS population.
- **Services, not patients**: facility rows carry only the professional (interpretation) component; `Tot_Srvcs` counts
  services, and `Tot_Benes` is not unique across providers. Never describe results as patients or studies performed.
- **2020 is a COVID discontinuity**: trend statements need a sensitivity analysis excluding 2020.
- **CPT code changes inside the window**: every modality's code set must be audited year by year for added or deleted
  codes. PET: CPT 2020 split PET perfusion into PET only (78491/78492) and PET with concurrent CT (78430/78431); both
  are counted since 2026-10-24, so the series is continuous. This was a correction of a coding error found while
  reviewing the PET trend; report it in Methods as such. Echo, SPECT, CTA and MRI still need the same audit.
- **Ecological design**: n ≤ 51; associations are state-level only (no individual-level inference). Density and use can
  drive each other (supply-induced demand vs demand attracting physicians), so no causal language. Neighbouring states
  are not independent (spatial autocorrelation). Keep covariates few for 51 units, and report how many density measures
  were tested.
- **Exposure–outcome coupling**: density counts NPIs that billed CTA, and the outcome counts the CTAs they billed, from
  the same rows. A state with more CTAs mechanically has more visible billers (worsened by suppression). An independent
  workforce measure is needed as a sensitivity analysis (see PENDING.md).

## Rules for producing the manuscript
- Every number in the text comes from a run's `tables/*.csv` and is cited with its run id. Never hand-compute,
  hand-type or hand-edit a reported number; regenerate it.
- `docs/ANALYSIS_PLAN.md` (to be written) holds primary/secondary outcomes and pre-specified sensitivity analyses. Any
  later change is dated, explained, and labelled post hoc. Exploratory results go to `docs/hypotheses/` as post hoc.
- Language: "associated with", "rate per 1,000 FFS beneficiaries", "services" (not patients or scans per person).
  Every IRR is reported with its unit, 95% CI and the adjustment set.
- Citations: every reference carries a DOI or PMID that was actually checked. Anything unverified is marked `[verify]`;
  never invent a citation, trial result or guideline class.
- Background to check and cite (verify before use): 2021 AHA/ACC multisociety chest pain guideline; 2019 ESC chronic
  coronary syndromes guideline; ISCHEMIA, SCOT-HEART and PROMISE trials; CMS payment changes for coronary CTA during the
  window as possible context for CTA growth.

## Working efficiently
- Before querying the database, look at `runs/latest/tables/` and `docs/hypotheses/` — the answer may already exist.
- Quick checks: read-only DuckDB queries from the scratchpad, never new code in `src/` for a one-off question.
- New open questions or decisions for the user go to `docs/PENDING.md`, not only into chat.
