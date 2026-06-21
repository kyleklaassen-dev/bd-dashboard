# Data-Quality Review — 2026-06-21 (Domain C1)

Read-only audit of the two integrity flags from the week-plan DB assessment. **No data changed** — both classes are judgment calls flagged for Kyle (constitution §7: ambiguous edits / deletes / merges need approval). Counts are live as of 2026-06-21 (crons paused, so static).

## 1. `brand_name` set but `stage` not approved — 7 drugs (NOT errors; a rule gap)
All 7 are **genuinely approved** competitor drugs (real brand + `approval_date`); `stage` reflects the **Ailux-relevant indication's trial stage**, not the drug's overall regulatory status:

| drug_id | brand | stage (now) | approved |
|---|---|---|---|
| rozanolixizumab | Rystiggo | Phase 3 | gMG 2023, CIDP 2024 |
| mepolizumab | Nucala | Phase 2 | asthma 2015 … COPD 2025 |
| benralizumab | Fasenra | Phase 3 | asthma 2017 |
| upadacitinib | Rinvoq | Phase 3 | RA 2019 … UC/CD |
| tralokinumab | Adbry | Phase 3 | AD 2021/2022 |
| nipocalimab | Imaavy | Phase 3 | gMG 2025 |
| lebrikizumab | Ebglyss | Phase 3 | AD 2023/2024 |

**Root cause:** the governance rule `brand_name ⇒ approved` (constitution; `DrugWriter.check_governance`) doesn't model "approved elsewhere, in trials for *our* indication."

**Options (Kyle's call):**
- **(A) Refine the rule** — accept `brand_name` when `stage` is approved **OR** `approval_date` is present; keep the Ailux-indication stage in `stage_detail`/`phase_display`. *Recommended* — preserves competitive nuance, fixes the false positives systemically, code-only change to `DrugWriter.check_governance` + the test baseline.
- (B) Flip `stage`→`Approved` for all 7 — factually true for the drug, but loses indication-trial signal and the enrichment cron would likely revert it on resume.
- (C) Leave as-is; keep them on the known-violation baseline (currently 7).

## 2. `company_id` IS NULL — 3 drugs (low-info strays)
`SM-101`, `LBP-EC01`, `AB001` — no originator, no `company_display`, no `dev_code`. `LBP-EC01` is Locus Biosciences' anti-*E. coli* phage (UTI) — **not Ailux-relevant** (I&I). Likely stray imports.

**Options (Kyle's call):** research + assign originator via `DrugWriter` (needs a source per governance — research pipeline is paused), or remove if confirmed non-relevant strays (delete needs §7 approval). **Not actioned** — assigning a company without a source would itself be a governance violation.

## Recommendation
Do **(A)** for class 1 when Kyle's available (small, systemic, test-gated), and triage the 3 strays then. Nothing here is urgent or data-corrupting; surfaced for decision.
