# Meridian BD Platform — Baseline v1.0

**Status:** Release candidate. Phase 4 reconciliation complete. Phase 5 active (Candidate 1 deployed, flag=false).  
**Date:** 2026-05-25  
**Git commit:** `2de30191923649a469294082a24f0e74ced075f3`  
**Short SHA:** `2de301919236`  
**Latest commit message:** Session 53o: Phase 4 reconciliation summary document

This document is a frozen reference point. It records the exact known-good state of the platform at the close of Phase 4. It is not a report — it is a regression baseline. When Phase 5 enrichment, new ingestion sources, ontology changes, or UI migrations introduce unexpected deltas, this document is the ground truth.

---

## Entity Counts

| Entity | Count | Notes |
|---|---|---|
| **companies** | **101** | 65 active · 19 reference · 15 planned · 2 orphan |
| **drugs** | **154** | Across all tracked areas |
| **drug_indications** | **198** | 17 distinct indication_ids |
| **drug_targets** | **170** | 35 distinct target_ids |
| **trial_indications** | **301** | Normalized trial→indication relationships |
| **trials** | **543** | All tracked clinical trials |
| **ontology_edges** | **25** | LOCKED — do not expand without advisor approval |
| **drug_areas** (legacy) | **209** | 11 areas; legacy layer; deprecated by Phase 5 |
| **company_aliases** | **184** | Primary + former name aliases |
| **entity_consistency_checks** | **10** | Durable human reconciliation layer |
| **drug_validation_results** | **839** | Automated scan output (separate from ECC) |
| **backfill_preview** | **873** | Staged enrichment candidates |

---

## Coverage by Area (Legacy drug_areas)

| Area | Drugs in legacy layer |
|---|---|
| tl1a | 50 |
| ibd | 49 |
| autoimmune | 25 |
| respiratory | 14 |
| tslp | 14 |
| tcell | 11 |
| atopy | 10 |
| igf1r | 9 |
| il4ra | 9 |
| ted | 12 |
| fcrn | 6 |

---

## Validation State

### drug_validation_results

| Status | Count |
|---|---|
| pass | 785 |
| needs_review | 38 |
| warning | 16 |
| **Total** | **839** |

**Open issues (54 total):**

| Check type | Count | Notes |
|---|---|---|
| company_resolution | 34 | Companies in need of enrichment pipeline pass |
| stage_trial_match | 16 | Known standing warnings; reviewed and accepted |
| target_consistency | 2 | Minor field inconsistencies |
| indication_consistency | 2 | Minor field inconsistencies |

**Interpretation:** The 34 `company_resolution` needs_review items are B-grade active companies (ailux, aurinia, biosion, etc.) awaiting the enrichment pipeline. The 16 `stage_trial_match` warnings are a known class, reviewed and accepted. Neither category represents a P0 data defect. All P0 issues were resolved in Phase 4.

### entity_consistency_checks

| Status | Count | Entities |
|---|---|---|
| closed / accepted | 3 | lm-302, sim0500, spy072 |
| corrected / resolved | 5 | batoclimab, gb004, upadacitinib, atg-201, nipocalimab |
| open / held | 2 | epi-001, cizutamig |

**Open high-severity: 0 ✅**

Open items are evidence gaps, not known defects:
- `epi-001` (id=4, medium, conf=0.55) — IBD indication not source-confirmed. Hold.
- `cizutamig` (id=15, medium, conf=0.87) — TED indication pattern_match only. Validate before Phase 5 TED.

---

## Company Fleet

| Metric | Value |
|---|---|
| Total companies | 101 |
| Active | 65 |
| Reference (acquired/inactive) | 19 |
| Planned (pipeline, not yet tracked) | 15 |
| Orphan (intentional, no pipeline) | 2 |
| Active + verified/enriched | 55 of 65 (85%) |
| Fleet Health Score | **96 / 100** |
| A-grade companies | 89 |
| B-grade companies | 12 (10 enrichment queue · 2 intentional orphans) |
| C-grade companies | 0 |

---

## Data Quality Snapshot

| Dimension | Metric | Value |
|---|---|---|
| drug_validation pass rate | 785 / 839 | 93.6% |
| ECC open high-severity | 0 of 10 | 0% |
| drug_indications confirmed (tier1/tier2) | — | Majority sourced from trial_indications or structured data |
| ontology_edges stability | 25 rows | LOCKED |
| Company health score | 96 / 100 | Fleet average |
| FcRn area match (post-correction) | 6 / 6 | 100% |
| TED area match | 9 / 9 | 100% |
| IBD area OOS-adjusted match | 94.0% raw → 100% adj | — |
| TL1A area OOS-adjusted match | 92.2% raw → 100% adj | — |
| TSLP area OOS-adjusted match | 42.9% raw → 100% adj | — |
| IL-4Rα area OOS-adjusted match | 44.4% raw → 100% adj | — |

---

## Architecture State

### Phase status

| Phase | Name | Status |
|---|---|---|
| 4A | Evidence reconciliation | ✅ COMPLETE |
| 4B | Dual-read validation | ✅ COMPLETE |
| 4C | Pre-migration classification | ✅ COMPLETE |
| 5 | Incremental source switch (feature-flagged) | ▶ ACTIVE — Candidate 1 at flag=false |

### Feature flags (index.html FEATURE_FLAGS)

| Flag | Value | Component |
|---|---|---|
| `useNormalizedIBD` | `false` | IBD area tab — deployed, not yet active |
| `useNormalizedTED` | not written | TED area tab — pending |
| `useNormalizedDrugModal` | not written | Drug entity modal — pending |
| `useUnifiedTL1A` | not written | TL1A tab — arch review required first |

### Governance rules in force

- **ECC execution criteria:** Direct source evidence OR cross-table contradiction (overwhelming confidence) OR prior accepted pattern. No speculative enrichment in ECC.
- **ontology_edges locked:** 25 rows. Do not expand without explicit advisor approval.
- **Wave 2D evidence standard:** trial_indications rows required for new drug_indication commits. Pattern_match alone is insufficient.
- **30-day rule:** Legacy code stays commented (not deleted) for 30 days after any feature flag is flipped to true.
- **OWNERSHIP ≠ IDENTITY:** parent_company_id tracks relationships; entity identity does not collapse on acquisition.
- **Acquired asset rule:** company_id=acquirer; display="X w/Y"; original_company_id retained.

### Automation running

| Script | Schedule | Purpose |
|---|---|---|
| `refresh_company_verified.py` | Weekly Sunday 06:00 UTC | Company freshness refresh |
| `ct_gov_sync.py` | Weekly | Trial registry sync + validation |
| `validation_research.py` | Weekly | Drug validation registry search |
| `conflict_detector.py` | Weekly | Cross-table contradiction scan |
| `research.py` | Daily 02:00 ET | News intelligence fetch |
| `write_meridian.py` | Daily 06:30 ET | Meridian today digest |

---

## Regression Checklist

Use this when evaluating whether a Phase 5 change has introduced regressions.

```sql
-- Core counts (compare against baseline above)
SELECT count(*) FROM companies;               -- baseline: 101
SELECT count(*) FROM drugs;                   -- baseline: 154
SELECT count(*) FROM drug_indications;        -- baseline: 198
SELECT count(*) FROM drug_targets;            -- baseline: 170
SELECT count(*) FROM trial_indications;       -- baseline: 301
SELECT count(*) FROM trials;                  -- baseline: 543
SELECT count(*) FROM ontology_edges;          -- baseline: 25 (LOCKED)
SELECT count(*) FROM entity_consistency_checks; -- baseline: 10

-- ECC gate
SELECT count(*) FROM entity_consistency_checks
  WHERE status = 'open' AND severity = 'high'; -- baseline: 0

-- Validation gate
SELECT check_status, count(*) FROM drug_validation_results
  GROUP BY check_status;
-- baseline: pass=785, needs_review=38, warning=16

-- FcRn area clean (no non-FcRn biology)
SELECT drug_id FROM drug_areas WHERE area_id = 'fcrn'; -- baseline: 6 drugs
-- expect: efgartigimod, nipocalimab, batoclimab, imvt-1402, rozanolixizumab, orilanolimab

-- Open ECC items (should remain: epi-001, cizutamig only)
SELECT entity_id, issue_key, severity, status, review_status
  FROM entity_consistency_checks WHERE status = 'open';
```

---

## BD Usefulness Metrics

Phase 4 proved the data is trustworthy. Phase 5 must prove the platform creates value. These metrics track whether the platform answers the right questions — not whether the database is correct.

| Metric | Question | How to measure |
|---|---|---|
| Opportunity surfaced | Did the platform identify a company or asset worth contacting? | Log in `update_log.md` when an outreach or analysis originates from platform output |
| Intelligence discovered | Did it reveal something the user did not already know? | Note when a competitive signal, catalyst, or drug status changes how a situation is understood |
| Time saved | Did it reduce manual research effort? | Qualitative — note when a question that would have required manual lookup was answered by the platform in <2 minutes |
| Action taken | Did a meeting, outreach, or analysis directly result from platform output? | Log in `update_log.md` with date and nature of action |

**Tracking convention:** When any of the above occurs, add a brief note to `update_log.md` under the date it happened, tagged `[BD_VALUE]`. This creates a lightweight audit trail of platform ROI without requiring a formal tracking system.

**Phase 5 success is not measured by validation counts alone.** A platform with zero ECC issues and zero BD intelligence produced is not a success. Phase 5 should produce at least one `[BD_VALUE]` log entry within the first 30 days of Candidate 1 activation.

---

## Migration Acceptance Criteria

Before any Phase 5 feature flag is flipped to `true`, all of the following must hold. This is the ship / do not ship checklist.

| Metric | Threshold | Current |
|---|---|---|
| Open high-severity ECC items | **0** | 0 ✅ |
| Validation pass rate (drug_validation_results) | **≥ 93%** | 93.6% ✅ |
| Company fleet health score | **≥ 95 / 100** | 96 / 100 ✅ |
| Regression in baseline entity counts | **None unless documented** | — |
| Feature flag rollback available | **Required** (flag=false path retained) | ✅ |
| Legacy path retained post-activation | **30 days minimum** (commented, not deleted) | — |

**Interpretation:**
- A candidate passes when all six rows are satisfied for that specific component.
- The entity count regression rule means: if any count moves in an unexpected direction (e.g., drug_indications drops without a documented deletion), the flag does not ship until the cause is identified.
- "Documented" means an entry in `update_log.md` with a rationale, not a verbal explanation.

---

*Frozen 2026-05-25 at commit `2de30191923649a469294082a24f0e74ced075f3`.*  
*v1.1: Added Migration Acceptance Criteria section (2026-05-25).*  
*Do not edit further. Create a new versioned snapshot (platform_baseline_v2.0, etc.) when the first Phase 5 component activates in production.*
