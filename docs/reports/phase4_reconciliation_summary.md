# Phase 4 Reconciliation Summary
**Meridian BD Platform — Sessions 53a–53o (2026-05-25)**  
**Status at close: Reconciliation layer operationally clean. Phase 5 active.**

---

## Overview

Phase 4 was the pre-migration reconciliation sprint for the Meridian normalized data layer. Its goal was to verify that every difference between the legacy `drug_areas` layer and the normalized `drug_indications` / `drug_targets` layer could be explained, classified, and either corrected or accepted before any Phase 5 feature flag was activated.

This document is the standing record of that work — major corrections applied, data quality changes made, lessons learned, and the state of remaining held items.

---

## 1. Phase Structure

| Phase | Name | Sessions | Outcome |
|---|---|---|---|
| 4A | Evidence Reconciliation — candidate review | 53a–53e | 6 candidates reviewed; corrections applied |
| 4B | Dual-read validation — parallel reads | 53f–53j | All 3 paths deployed and verified |
| 4C | Pre-migration classification — explain every difference | 53k–53o | All 8 area components classified |
| 5 | Incremental source switch — feature-flagged | 53o → | Candidate 1 deployed (IBD, flag=false) |

---

## 2. Validation Metrics: Before vs After

### drug_indications

| Metric | Before Phase 4 | After Phase 4 | Delta |
|---|---|---|---|
| Total rows | 192 | **200** | +8 |
| batoclimab coverage | ted only | ted + gmg + cidp | +2 |
| upadacitinib coverage | cd + uc | cd + uc + ad | +1 |
| imvt-1402 coverage | (none) | gmg + cidp | +2 |
| FcRn area raw match | 85.7% | **100%** | atg-201 removal |
| TED area raw match | incomplete | **100%** | batoclimab correction |
| IBD area OOS-adj match | 94.0% | 94.0% (unchanged) | — |
| TL1A area OOS-adj match | 92.2% | 92.2% (unchanged) | — |

### drug_targets

| Metric | Before Phase 4 | After Phase 4 |
|---|---|---|
| Total rows | 168 | **173** |
| gb004 target accuracy | mechanism='Anti-TL1A' (wrong) | mechanism='PHD inhibitor (HIF-1α stabilizer)' ✅ |

### drug_areas (legacy footprint)

| Area | Before | After | Change |
|---|---|---|---|
| fcrn | 7 drugs | **6 drugs** | atg-201 removed (legacy noise) |
| tcell | included nipocalimab | nipocalimab removed | legacy noise corrected |
| all others | unchanged | unchanged | — |

### entity_consistency_checks

| Metric | At creation | At close |
|---|---|---|
| Total rows | 8 | **10** |
| Open high-severity | 0 | **0** |
| Corrected/resolved | 3 | **5** |
| Closed/accepted | 3 | **3** |
| Open/held | 2 | **2** |

---

## 3. Major Corrections Applied

### 3a. Data corrections (drug_indications)

| Drug | Correction | Session | Evidence basis |
|---|---|---|---|
| batoclimab | Added ted (95, Ph3) + gmg (92, Ph3) | 53e | trial_indications Phase 3 data |
| batoclimab | Added cidp (92, Ph2) — Wave 2D | 53o | trial_indications Phase 2 data |
| upadacitinib | Added ad (97, Approved) — Wave 2D | 53n | advisor-accepted; JAK inhibitor, approved atopic dermatitis indication |
| imvt-1402 | Added gmg (94, Ph3) + cidp (91, Ph2) — Wave 2D | 53o | trial_indications evidence |

**Not committed:**
- `imvt-1402 / waiha` — no trial_indications evidence. Held.
- `epi-001 / uc + cd` — confidence=0.55; no source evidence found. Held.

### 3b. Field corrections (drugs table)

| Drug | Field | Before | After | Session |
|---|---|---|---|---|
| gb004 | mechanism | 'Anti-TL1A' | 'PHD inhibitor (HIF-1α stabilizer)' | 53n |

**Root cause:** gb004 is a PHD/HIF-1α small molecule. The TL1A mechanism was a legacy mis-classification inherited from area-based tagging. All other gb004 fields (target, modality, drug_format, overlap_rationale, drug_summary) already correctly described it as a PHD program.

### 3c. Legacy area corrections (drug_areas)

| Drug | Area removed | Rationale | Session |
|---|---|---|---|
| atg-201 | fcrn | CD19×CD3 bispecific T-cell engager; drug_targets = cd19 + cd3 only; no FcRn biology present anywhere | 53o |
| nipocalimab | tcell | Anti-FcRn full mAb; drug_targets = fcrn (95, conf A); no T-cell biology present anywhere | 53o |

Both satisfied ECC execution Criteria #2 (cross-table contradiction, overwhelming confidence) and #3 (prior accepted pattern — same legacy noise class as lm-302/sim0500).

---

## 4. Legacy-Noise Classifications (no data change required)

These Phase 4A candidates were reviewed and classified as acceptable — no corrective action taken:

| Drug | Classification | Explanation |
|---|---|---|
| lm-302 | legacy_noise_removed | CLDN18.2 ADC in tl1a area; no TL1A biology. Correctly excluded from normalized layer. ECC closed/accepted. |
| sim0500 | legacy_noise_removed | drug_targets tl1a row was never committed to production (Wave 2B error caught by harness). ECC closed/accepted. |
| spy072 | ontology_scope_difference | Rheumatology drug in tl1a area; legitimate adjacent biology, different ontology scope. ECC closed/accepted. |

### Area-level OOS classifications

All TSLP and IL-4Rα legacy-only extras were classified as `ontology_scope_difference` — pathway partners targeting adjacent biology (IL-33, IL-5Rα, IL-13, OX40L, IL-31RA) that were grouped under catch-all legacy area labels. These are expected differences, not data errors. No corrections made.

---

## 5. Company Governance Work

Work completed in the company layer during Phase 4 sessions:

**Schema additions:**
- `parent_company_id`, `ownership_type` — subsidiary/parent relationship modelling
- `original_company_id`, `acquired_asset`, `acquired_by` — acquired asset attribution
- `coverage_status` — active / reference / planned / orphan classification

**Key corrections applied:**
- Ghost records deleted: xencor-412, xencor-942 (17 intel rows migrated to xencor)
- QuantumPharm resolved: former name of XtalPi Holdings; alias marked 'former'
- 32 no-drug companies classified with coverage_status
- 50 companies geography-backfilled from hq_country
- 71 primary aliases seeded
- 4 acquired companies set to reference status

**Governance rules established:**
- OWNERSHIP ≠ IDENTITY (Ailux/XtalPi model): parent_company_id + ownership_type track relationships without collapsing entities
- Acquired asset rule: company_id=acquirer, display="X w/Y", original_company_id retained
- Prometheus→Merck as canonical acquired-company example

**Automation deployed:**
- `scripts/refresh_company_verified.py` — 3-tier freshness refresh
- `.github/workflows/refresh-company-verified.yml` — weekly Sunday 06:00 UTC
- `scripts/company_validator.py` — P0/P1/P2 checks + 6-dimension Health Score

**Fleet result after freshness run:**

| Metric | Before | After |
|---|---|---|
| Fleet average Health Score | 91/100 | 96/100 |
| A-grade companies | 60 | 89 |
| B-grade companies | 39 | 12 |
| C-grade companies | 2 | 0 |

---

## 6. Phase 4B Dual-Read Architecture

Three dual-read paths were deployed to enable parallel legacy/normalized reads in the dashboard without behavioral change:

| Path | Location | Description | Status |
|---|---|---|---|
| Path A | `_makeAreaPI()` | IBD indication-group dual-read | ✅ Verified |
| Path B | `_makeAreaPI()` | TL1A target-view dual-read | ✅ Verified |
| Path C | `openDrugEntityModal()` | Drug entity modal dual-read | ✅ Deployed; 3/10 drugs verified |

All reads write to `window.__MERIDIAN_PHASE4_COMPARE__`. Access via `window.showPhase4Compare()` in browser console.

**Status escalation logic:** `match → acceptable_mismatch → needs_manual_review → cross_table_inconsistency`

---

## 7. Phase 4C Area Component Results

| Rank | Component | Raw match | OOS-adjusted | Status |
|---|---|---|---|---|
| 1 | IBD area tab | 94.0% | 100% | ✅ compare_pass_oos_adjusted |
| 2 | TED area tab | 100.0% | 100% | ✅ compare_pass |
| 3 | Drug entity modal | — | — | ⏸ 3/10 verified; 7 remaining |
| 4 | TL1A area tab | 92.2% | 100% | ✅ compare_pass_oos_adjusted |
| 5 | TSLP area tab | 42.9% | 100% | ✅ compare_pass_oos_adjusted |
| 6 | IL-4Rα area tabs | 44.4% | 100% | ✅ compare_pass_oos_adjusted |
| 7 | FcRn area tab | 85.7%→100% | 100% | ✅ compare_pass (post-correction) |
| 8 | ACE/tcell area tab | N/A | N/A | 🚫 DEFERRED permanently |

**ACE/tcell deferred rationale:** No normalized drug_indications or drug_targets equivalent exists for the tcell area. Not a valid migration target. Excluded from Phase 5 planning.

**TSLP migration note (standing):** verekitug targets TSLP receptor (tslpr), not TSLP ligand. Phase 5 TSLP tab migration must query `target_id IN ('tslp', 'tslpr')`.

---

## 8. entity_consistency_checks Governance

### Final state at Phase 4 close

```
Total rows: 10
Open/held (2):
  - epi-001 / ibd_indication_evidence_gap    (medium, conf=0.55)
  - cizutamig / ted_indication_scope_review   (medium, conf=0.87)
Corrected/resolved (5):
  - batoclimab / missing_ted_gmg_indications  (high)
  - gb004 / mechanism_field_conflict          (medium)
  - upadacitinib / atopy_ad_gap               (medium)
  - atg-201 / fcrn_area_mismatch              (medium)
  - nipocalimab / tcell_area_mismatch         (low)
Closed/accepted (3):
  - lm-302 / legacy_ibd_tl1a_noise            (high)
  - sim0500 / legacy_ibd_tl1a_noise           (high)
  - spy072 / tl1a_rheumatology_scope          (medium)
Phase 5 gate: 0 open high-severity ✅
```

### Execution criteria (approved Session 53o)

A proposed cleanup may execute (`open/proposed → corrected/resolved`) only when one of:

1. **Direct source evidence** — company materials, clinical trial registry, regulatory filing, or publication
2. **Cross-table contradiction, overwhelming confidence** — target assignment directly contradicts area assignment with no supporting evidence in any table
3. **Prior accepted pattern** — same error class already reviewed and approved

### Governance interpretation

Open ECC items now represent **unresolved evidence questions**, not known data defects. The table should remain sparse. Future entries should be reserved for:
- Genuine contradictions requiring human judgment
- Advisor-reviewed reconciliation candidates with a proposed action
- Source-backed correction proposals

Speculative enrichment opportunities belong in `backfill_preview` or `drug_validation_results`, not ECC.

---

## 9. Remaining Held Items

### epi-001 / ibd_indication_evidence_gap (ECC id=4)
- **Drug:** Anti-TL1A antibody (preclinical). Potentially in-licensed or early-stage.
- **Issue:** drug_indications has uc + cd rows in `backfill_preview` at pending_review (wave2c run). No source publication, trial registry entry, or company disclosure found confirming IBD indication.
- **Confidence:** 0.55
- **Standing rule:** Do NOT commit without source evidence. If no evidence found after reasonable search, set review_status='no_evidence' and close ECC row.
- **Not blocking Phase 5 IBD migration** — epi-001 has no normalized indication rows that would be surfaced by the IBD tab.

### cizutamig / ted_indication_scope_review (ECC id=15)
- **Drug:** BCMA×CD3 bispecific T-cell engager (Phase 1).
- **Issue:** drug_indications has ted row sourced from pattern_match / sampling_queue. TED indication for a BCMA×CD3 engager is biologically unusual — BCMA is a plasma cell target, not a thyroid pathway.
- **Confidence:** 0.87
- **Standing rule:** Validate against clinical trial registry or company disclosure before Phase 5 TED migration includes cizutamig.
- **Not blocking Phase 5 IBD migration** — only relevant to Phase 5 TED (Candidate 2).

---

## 10. Lessons Learned

### L1: OOS-adjusted match is the correct primary metric
Raw match rates for legacy catch-all areas (TSLP: 42.9%, IL-4Rα: 44.4%) look alarming but are expected. Legacy areas grouped pathway partners together; normalized areas are mechanism-specific. All differences in these areas were ontology_scope_differences, not data errors. The OOS-adjusted rate (100% for both) is the meaningful signal.

### L2: Area assignment ≠ target membership
Multiple drugs were placed in legacy areas without having a corresponding target. The dual-read framework exposed this cleanly — `drug_targets` is the ground truth; `drug_areas` is a derived view that accumulated noise over time. atg-201 (CD19×CD3 in fcrn area) and nipocalimab (FcRn mAb in tcell area) are canonical examples of this failure mode.

### L3: Mechanism field is a weak signal alone; cross-field consistency is required
gb004 had mechanism='Anti-TL1A' while every other field (target, drug_format, overlap_rationale, drug_summary) described a PHD/HIF-1α small molecule. Single-field validation would have missed this; the conflict_detector.py cross-table scan surfaced it.

### L4: Pattern_match source_type requires explicit human review before Phase 5 inclusion
Two held items (epi-001, cizutamig) both have drug_indications rows sourced from pattern_match / sampling_queue. These should not graduate to Phase 5 inclusion without at minimum synonym_match or tier1_structured evidence. The source_type field is a reliable signal for prioritizing review effort.

### L5: The ECC table is a judgment ledger, not a scan log
The most important architectural decision of Phase 4 was keeping ECC sparse and human-curated. Automated scanners (drug_validation_results, conflict_detector) write to their own logs. ECC entries require a human or harness review + a proposed action before creation. This kept the Phase 5 gate meaningful — 0 open high-severity items means the table is actually clean, not just that nothing was checked.

### L6: Feature flags enable safe migration; do not skip them
Phase 5 Candidate 1 (IBD) was deployed with useNormalizedIBD=false. This gives the normalized layer a production presence with zero behavioral change — the flag can be verified, tested in browser, and flipped in a single commit. This pattern should be applied to all Phase 5 candidates.

### L7: Wave 2D evidence standard prevented false additions
The rule "trial_indications rows required for Wave 2D commits" prevented imvt-1402/waiha from being committed despite waiha being a known FcRn indication class. No trial evidence exists in the normalized layer for that specific drug/indication pair. Holding was the correct call; it will auto-resolve when enrichment pipeline runs with waiha in scope.

---

## 11. Phase 5 Activation Sequence

For reference, the planned Phase 5 component order:

| Candidate | Component | Flag | Gate |
|---|---|---|---|
| 1 | IBD area tab | `useNormalizedIBD` | 10-drug modal sprint + advisor go |
| 2 | TED area tab | `useNormalizedTED` | Candidate 1 live + cizutamig resolved |
| 3 | Drug entity modal | `useNormalizedDrugModal` | 10-drug sprint complete |
| 4 | TL1A area tab | `useUnifiedTL1A` | Arch review of tl1aPI object (~1700 lines) |
| — | TSLP / IL-4Rα / FcRn | TBD | After Candidates 1–3 stable |
| — | ACE / tcell | N/A | DEFERRED permanently |

**30-day rule:** When any flag is flipped to true, keep legacy code commented (not deleted) for 30 days before removal.

---

*Document written Session 53o, 2026-05-25. Next update due when Phase 5 Candidate 1 activates.*
