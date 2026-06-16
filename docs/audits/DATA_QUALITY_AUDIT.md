# Meridian Data Quality Audit — systematic dimension sweep

A structured burn-down of data-integrity dimensions so gap-hunting is ordered, not random.
Each dimension: a repeatable scan, a finding count, and a status. Re-run any scan anytime.

Status key: ✅ done · 🔄 in progress · ⬜ not yet run · ⚠️ findings open

---

## Tier 1 — high impact, high likelihood of issues

| # | Dimension | What it catches | Status | Findings |
|---|-----------|-----------------|--------|----------|
| 1 | **Mechanism ↔ target consistency** | mechanism text describing a different target than `target` (hallucination) | ✅ | 7 found · 4 fixed w/ sources · 4 flagged · root-cause prompt rule added |
| 2 | **Trial attribution** | sibling-drug NCTs leaking onto the wrong drug (the mt-251 pattern) | ✅ | 52 "foreign codes" scanned — nearly all are each drug's OWN dev-code (AIN457=secukinumab, etc.), i.e. correctly matched. No mt-251-style misattributions beyond the one already fixed. Opportunity: harvest these dev-codes into drug_aliases. |
| 3 | **Duplicate / alias entities** | same molecule under multiple drug ids (the obexelimab / CLD-423 pattern) | ✅ | 0 by shared canonical_id; found + merged **BSI-045B = bosakitug = ATI-045** (un-deduped TSLP mAb; trials migrated, originator fixed to Biosion + Aclaris partner). |
| 4 | **Target-field hygiene** | modality/company annotations in `target`; malformed bispecific notation | ✅ | 1 found + fixed (kyv-101 "CD19 (CAR-T)" → "CD19"). Field otherwise clean. |
| 5 | **Indication hygiene** | `indication_short` holding a target/qualifier instead of a disease (ontology rule) | ✅ | **28 fixed** — drugs with a target/area code (TSLP, IL4RA, FCRN, TCELL, TL1A) in indication_short → mapped to area-lead disease (Asthma/AD, AD, IgG-autoimmune, B-cell-autoimmune, IBD). |

## Tier 2 — medium impact

| # | Dimension | What it catches | Status | Findings |
|---|-----------|-----------------|--------|----------|
| 6 | **Source coverage** | visible drugs with no `source_url` / claims without `drug_sources` | ⬜ | — |
| 7 | **Company attribution** | `company_id` = originator rule; acquired/subsidiary correctness | ⬜ | — |
| 8 | **Partnership verification** | unverified or wrong partner attributions | ⬜ | — |
| 9 | **Stage consistency** | stage vs trials vs approval mismatch | partial | brand+Phase-3 pattern confirmed intentional (_resolveStage) |

## Tier 3 — lower impact / hygiene

| # | Dimension | What it catches | Status | Findings |
|---|-----------|-----------------|--------|----------|
| 10 | **Brand-name validity** | dash brand names; brand set without approval milestone | ✅ | 0 dash brands; 1 fixed (benralizumab missing approval_date → added Fasenra Nov 2017). |
| 11 | **Null critical fields** | visible drugs missing company_id / area / summary | ✅ | mechanism/target/summary 0 null. company_id 93% (148/159) after originator-research round: attributed Innovent, Hengrui, Zai Lab, Akeso, Novartis, Henlius, Ionis, Aclaris, Merck, Dermavant. **Caught 4 mis-ingested junk records** with wrong targets, out of scope, polluting landscapes as phantom competitors → hidden (RGX-181=Batten gene therapy, LBP-EC01=UTI phage, GB1275=CD11b oncology, SRF-231=discontinued CD47 oncology). 11 obscure early-stage codes remain flagged. |
| 12 | **Area classification spot-check** | drugs mapped to the wrong competitive area | ✅ | 36 target/area "mismatches" — nearly all legit cross-mechanism competitors (ustekinumab IL-12/23 in IBD, batoclimab FcRn in TED, etc.). 1 real error: **SIM0500** (GPRC5D×BCMA×CD3 myeloma TCE) wrongly in IBD/TL1A, inflating it to #1 in IBD ranking → removed + hidden. |

---

## Tier 1b — query/schema mismatches (dashboard `.select()` vs real columns)

| # | Dimension | What it catches | Status | Findings |
|---|-----------|-----------------|--------|----------|
| 13 | **Query ↔ schema mismatch** | dashboard `_sb.from(t).select(col)` referencing a column that doesn't exist → silent empty/failed feature | ⚠️ | **49 found** (sweep of 303 select calls / 78 tables). Fixed 4 high-impact: deals `value_usd`→`total_usd_m`, indications search `synonyms`→`abbreviation`, drug_validation_results `status/detail/checked_at`→`check_status/details/verified_at`, governance display `entity_id/violation_description`→`row_id/description`. **~45 remain** — backlog below. |

**Remaining query/schema mismatches to fix (table.wrong_col → likely_right_col):**
- company_profiles: `confidence_tier`, `assessment`, `competitive_position`, `completeness_tier`→`completeness_score`
- companies: `sector`, `market_cap_usd_m`→`market_cap` (or read from company_profiles), `cash_runway` (on company_profiles), `stage`
- intel: `summary`→`body`, `area_id` (via intel_areas), `ailux_angle`
- catalysts: `catalyst_text`/`catalyst_name`→`label`/`notes`
- catalyst_calendar: `company_name`/`drug_name`/`call_priority` (join needed)
- catalyst_bd_timing_window: `bd_score`→`overall_bd_score`, `drug_id` (n/a)
- deal_sequencing_constraints: `constraint_description`→`description`, `timing_note`→`reasoning`, `bd_action_blocked_until`→`window_opens`, `constraint_expires`
- geographic_approvals: `approval_status`→`approval_type`
- coverage_scores: `coverage_score`→`overall_score`
- research_queue: `status`→`assigned_status`, `notes`→`reason`, `priority`→`priority_score`, `entity_type`/`gap_type` (n/a)
- drug_failure_cascade: `drug_id`→`failed_drug_id`, `rationale`→`impact_rationale`, `severity`
- targets: `name`→`label`; target_pairs: `name`→`pair_symbol`, `area`
- drug_area_scores: `score`, `legacy_area_id`/`context_type`/`target_id` (legacy dual-read — verify intent)
- drugs: `company`→`company_id`
- indications (other call): `therapeutic_area_id`→`disease_area`

Re-run the sweep anytime: it lives in this session's notes — extract `.from(t).select('...')`, diff against `information_schema.columns`.

## Resolved this engagement (context)
- Catalog tail (90 unmapped → 0 visible) · drug_areas trigger fix · alias persistence
- 47-table RLS read regression · deal-edge layer 19→79 · 5 patient-intel indications
- 4 governance violations researched + fixed · mechanism/target prevention rule

## Open flags awaiting source verification (governance_violations, resolved=false)
- mk-1695, shr0817, hlx36, abs-101 — mechanism/target mismatch, true field unconfirmed by web search
