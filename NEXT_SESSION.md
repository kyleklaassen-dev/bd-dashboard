# NEXT SESSION — BD Platform

**Last session:** Session 53d (2026-05-25)  
**Completed:** Phase 4A Evidence Reconciliation Candidate Review — all 6 known candidates classified  
**Prior milestones:** Wave 2C COMMITTED (63 rows) · Phase 4 harness v3 (DIFFERENCE_CLASSIFICATIONS) · tl1a/ibd compare_pass_oos_adjusted · Phase 4A/4B/Phase 5 sequence established

---

## Advisor Decisions Required Before Next Session

These items are **blocked on advisor input**. Do not auto-apply.

### 1. sim0500 — Drug Targets Deletion (HIGH PRIORITY)
**Action required:** Approve or reject DELETE from `drug_targets` where `drug_id = 'sim0500' AND target_id = 'tl1a'`  
**Why:** sim0500 is a GPRC5D×BCMA×CD3 trispecific for RRMM (hematology). It was erroneously committed to `drug_targets` with `target_id = 'tl1a'` during Wave 2B. This is a normalized table error (not a legacy error). The row is factually wrong.  
**Confidence:** 0.98  
**Impact:** If not deleted, sim0500 will appear as a TL1A drug in normalized queries — causing a dashboard regression when Phase 4B dual-read runs.

**SQL to run after approval:**
```sql
DELETE FROM drug_targets WHERE drug_id = 'sim0500' AND target_id = 'tl1a';
```

### 2. batoclimab — Drug Indications Backfill (CRITICAL)
**Action required:** Approve or reject backfill of `drug_indications` for batoclimab (ted, gmg, cidp)  
**Why:** batoclimab has 7 trials across TED/gMG/CIDP in `trial_indications`, is correctly classified in `drug_targets` (FcRn/FCGRT), has `drugs.indication_short = 'gMG, CIDP'` — but has **zero rows in drug_indications**. This is the highest-priority normalized gap. If any fcrn/ted/autoimmune area migrates before this is fixed, batoclimab disappears from all tabs incorrectly.  
**Confidence:** 0.90  
**Impact:** CRITICAL — dashboard regression risk in Phase 4B dual-read; migration of fcrn/ted/autoimmune areas is blocked until resolved.

**Rows to insert after approval:**
```sql
INSERT INTO drug_indications (drug_id, indication_id, confidence_score, review_status, source_notes)
VALUES
  ('batoclimab', 'ted',  0.88, 'review_required', 'Phase 3 TED trials in trial_indications; FcRn mechanism confirmed'),
  ('batoclimab', 'gmg',  0.92, 'review_required', 'Phase 3 gMG trials in trial_indications; indication_short confirms'),
  ('batoclimab', 'cidp', 0.85, 'review_required', 'Phase 3 CIDP trials in trial_indications; FcRn mechanism confirmed');
```
*Note: also update `drugs.indication_short` from 'gMG, CIDP' → 'gMG, CIDP, TED' after approval.*

### 3. epi-001 — Manual Evidence Review (PENDING HUMAN)
**Action required:** Human must search for published clinical evidence confirming IBD indication  
**Why:** epi-001 is an anti-TL1A antibody at preclinical stage. No `indication_short`, no trials, no source evidence in current DB. Two rows sit in `backfill_preview` as `pending_review`/`review_required`. TL1A mechanism is IBD-relevant but mechanism alone is insufficient.  
**Confidence:** 0.55 (insufficient to auto-decide)  
**Search guidance:** Check ClinicalTrials.gov for epi-001 or EPI-001; check Epicentrex/developer pipeline page; search PUBMED for "EPI-001 TL1A IBD"  
- If IBD indication confirmed → commit epi-001 (uc + cd, conf 76, review_required) → tl1a raw coverage 96.1%, ibd raw 98%
- If not confirmed → keep held indefinitely

### 4. upadacitinib (Rinvoq) — AD Backfill Timing
**Action required:** Confirm inclusion in Wave 2D atopy batch  
**Why:** upadacitinib is FDA-approved for atopic dermatitis (JAK1 inhibitor). It is in `drug_areas` (atopy) but absent from `drug_indications` for `ad`. Three AD trials confirmed in `trial_indications`. Approved for next atopy Wave 2D batch.  
**Confidence:** 0.97 — pre-approved, just needs scheduling.

---

## Phase 4A Status: ✅ CANDIDATE REVIEW COMPLETE

All 6 Phase 4A known candidates have been classified. Reference: `docs/phase4a_reconciliation_review.md`

| Candidate | Classification | Severity | Confidence | Review Status |
|---|---|---|---|---|
| lm-302 | cross_table_inconsistency → legacy_noise_removed | High | 0.99 | ✅ approved |
| sim0500 | cross_table_inconsistency + normalized_table_error | High | 0.98 | ⚠️ needs_advisor |
| spy072 | ontology_scope_difference → legacy_noise_removed (ibd) | Medium | 0.92 | ✅ approved |
| epi-001 | needs_manual_review | Medium | 0.55 | 🔲 pending_human |
| batoclimab | cross_table_inconsistency + normalized_gap (CRITICAL) | High | 0.90 | ⚠️ needs_advisor |
| upadacitinib | normalized_gap (ad) | Medium | 0.97 | ✅ approved |

**No production data was modified during Phase 4A review.** All changes above await explicit advisor approval.

---

## Phase Sequence (updated Session 53d)

| Phase | Name | Status |
|---|---|---|
| Phase 4A | Evidence Reconciliation — candidate review | ✅ COMPLETE (review only) |
| Phase 4A | Evidence Reconciliation — apply approved corrections | ▶ NEXT (after advisor decisions above) |
| Phase 4B | Dual-read validation — parallel legacy + normalized reads, assert parity | Queued |
| Phase 5 | Switch dashboard logic | Blocked until 4A + 4B clear |

**Do NOT proceed to Phase 4B or Phase 5 without:**
1. sim0500 drug_targets error resolved (delete approved)
2. batoclimab drug_indications backfill resolved (insert approved)
3. epi-001 manual review complete (hold or commit decided)

---

## Next Sprint Priority Order

### P0 — Apply Phase 4A Approved Corrections (after advisor decisions)

1. **sim0500 drug_targets DELETE** — run after advisor approves (see SQL above)
2. **batoclimab drug_indications INSERT** — run after advisor approves (see SQL above)
3. **Re-run Phase 4 harness** — regenerate `docs/phase4_comparison_harness.md` with corrections applied
4. **Re-run V1-V8 validation** — confirm no regressions after corrections
5. **Build `entity_consistency_checks` table** — only after first correction is approved and ready to write rows. Do NOT build the table speculatively. Migration SQL is in `docs/evidence_reconciliation_layer.md`.
6. **Seed `entity_consistency_checks`** — write the 6 Phase 4A candidate records to the table after it exists

### P1 — Phase 4B: Dual-Read Validation (Track D)

**What to build:** For `_makeAreaPI` and `openDrugEntityModal`, add a parallel read path alongside the legacy query. Compare outputs in-browser and log any regressions.

**Starting point:** `docs/phase4_comparison_harness.md` Part 2 and Part 5.

**12 drug_indications-blocked dashboard paths to validate:**
These paths were identified in `docs/dashboard_dependency_inventory.md` as needing Phase 4 comparison before migration. With tl1a/ibd now at compare_pass, begin the dual-read layer.

**Implementation approach:**
1. In `_makeAreaPI()` (lines ~12121–12200): add a secondary query to `drug_indications WHERE indication_id IN ('uc','cd')` in parallel to the legacy `drug_areas.in('area_id', ['ibd','tl1a'])` query
2. Log the result sets side-by-side to browser console: `[Phase4] legacy_count vs norm_count, diff: []`
3. Assert row count parity — flag any drug present in legacy but not normalized (or vice versa)
4. For `openDrugEntityModal()`: similar parallel read using `drug_targets + drug_indications` alongside `drug_area_scores`
5. NO visual changes — dual-read is invisible to end user
6. Acceptance criteria: (a) both read paths run without error, (b) row counts match for each indication, (c) no dashboard visual regressions, (d) enrichment write-side simultaneously migrated for drug_area_scores replacement

### P2 — epi-001 Manual Review (Track B)
Review EPI-001 clinical evidence:
- Is there any indication_short available or published trial data for IBD?
- If confirmed IBD target: commit epi-001 (uc + cd, conf 76, review_required)
- If uncertain: keep held
- Drug: anti-TL1A antibody, preclinical stage
- Committing epi-001 would push tl1a raw to 96.1% and ibd raw to 98% (both above 95% raw)

### P3 — Track B True Missing Rows
From mismatch classification in `docs/phase4_comparison_harness.md` Part 4:
- `upadacitinib` → ad: true_missing_row (queue in Wave 2D)
- `imvt-1402` → gmg, cidp, waiha: true_missing_row
- `ep006` → tombstone or merge into es302 (duplicate drug_id data integrity)

### P4 — Portfolio Intelligence Product (Track C)
Drug → Company joins are now available. First intelligence product using completed ontology layer.
**Question:** "What is [company]'s full indication footprint across all areas we track?"

### P5 — Wave 2D: FcRn + Autoimmune Backfill (Track A)
Next largest coverage gaps: fcrn (57.1%) and autoimmune (48%).  
**Prerequisite:** batoclimab drug_indications backfill must be resolved first (it is a fcrn/ted drug).

---

## Standing Advisor Decisions (permanent)

### Option A — OOS-Adjusted Coverage Metric (2026-05-25)

**Rule adopted:** OOS-adjusted coverage is the migration-readiness metric for TL1A / IBD.

**Standing governance rule:**
> "Do not contaminate normalized truth to match legacy noise. If a legacy record is proven out-of-scope, remove it from the migration-readiness denominator."

**Three confirmed OOS exclusions (permanent — do NOT add to drug_indications):**
- `lm-302` — gastric ADC; in tl1a/ibd legacy areas by curation error
- `sim0500` — RRMM trispecific; in tl1a/ibd legacy areas by curation error
- `spy072` — TL1A antibody for PsA/axSpA (rheumatology, not IBD); in tl1a area only

**Result:**
- tl1a: 92.2% raw → **97.9% OOS-adjusted** 🟢 compare_pass_oos_adjusted
- ibd: 94.0% raw → **97.9% OOS-adjusted** 🟢 compare_pass_oos_adjusted
- uc/cd Program Board readiness badges: `blocked` → `compare_pass` (98%)

---

## Active Constraints (unchanged)

1. **epi-001 held** — 2 rows remain in backfill_preview as pending_review / review_required. Do NOT commit without manual review of epi-001 IBD indication evidence.
2. **Do NOT unlock ontology_edges** — remains at 25 until advisor explicitly approves after Phase 4 dual-read validation
3. **Do NOT migrate BLOCKED dashboard references** — Phase 4 dual-read comparison layer must validate zero regressions first
4. **compare_pass ≠ migration-ready** — tl1a/ibd cleared Phase 4 compare threshold; they are NOT cleared for Phase 5 (dashboard migration). Dual-read validation is the gate.
5. **No single table is ground truth** — truth is evidence-weighted and relationship-validated across all tables

---

## State of the Platform

### What Just Happened (Session 53d)
- Phase 4A Evidence Reconciliation Candidate Review: **COMPLETE** (review only — no data changes)
- All 6 known candidates classified with structured records and 13-field analysis
- New findings: sim0500 has erroneous drug_targets tl1a row (Wave 2B commit error); batoclimab has 0 drug_indications (CRITICAL gap); upadacitinib missing ad from drug_indications
- `docs/phase4a_reconciliation_review.md` created — full candidate review
- `docs/evidence_reconciliation_layer.md` created — `entity_consistency_checks` design + build order
- entity_consistency_checks table NOT yet built (by design — awaiting first approved correction)
- NEXT_SESSION.md updated with advisor decisions required

### Cumulative Normalized Data
- drug_indications: **192 rows** (post-Wave 2C)
- drug_targets: **173 rows**
- trial_indications: **319 rows**
- ontology_edges: **25 rows** (LOCKED)
- backfill_preview wave2c: 63 committed · 2 held (epi-001)

---

## Validation Checks Before Starting Work

```sql
SELECT count(*) FROM drug_indications;             -- expect 192
SELECT count(*) FROM trial_indications;            -- expect 319
SELECT count(*) FROM drug_targets;                 -- expect 173
SELECT count(*) FROM ontology_edges;               -- expect 25 (LOCKED)
SELECT count(*) FROM backfill_preview
  WHERE backfill_run_id = 'wave2c_ibd_20260525_203134'
  AND preview_status = 'pending_review';           -- expect 2 (epi-001 held)
SELECT count(*) FROM backfill_preview
  WHERE backfill_run_id = 'wave2c_ibd_20260525_203134'
  AND preview_status = 'committed';               -- expect 63
-- Verify sim0500 normalized table error (should exist, pending deletion):
SELECT * FROM drug_targets WHERE drug_id = 'sim0500' AND target_id = 'tl1a';  -- expect 1 row (error row)
-- Verify batoclimab drug_indications gap (should be empty):
SELECT * FROM drug_indications WHERE drug_id = 'batoclimab';  -- expect 0 rows (gap to fill)
```

---

## Files to Load at Start of Next Session

1. `docs/phase4a_reconciliation_review.md` — Phase 4A candidate review (all 6 candidates)
2. `docs/evidence_reconciliation_layer.md` — entity_consistency_checks design + build order
3. `docs/phase4_comparison_harness.md` — current harness output (tl1a 🟢 · ibd 🟢)
4. `docs/normalization_engine.md` — parser reference
5. `docs/dashboard_dependency_inventory.md` — 12 blocked paths for Phase 4 dual-read
6. `scripts/phase4_compare_legacy_vs_normalized.py` — harness script (v3 with DIFFERENCE_CLASSIFICATIONS)
7. `MEMORY.md` → `project_parallel_workstreams.md`, `project_meridian_maturity.md`
