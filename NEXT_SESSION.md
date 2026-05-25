# NEXT SESSION — BD Platform

**Last session:** Session 53i (2026-05-25)  
**Completed:** Phase 4B Path B — TL1A target-view dual-read in `_makeAreaPI()` · `_runPhase4BTL1ADualRead` added · gb004 mechanism error added to evidence reconciliation backlog  
**Prior milestones:** Session 53h TL1A gap classification · Session 53g Phase 4B Path A (IBD dual-read) · Session 53f LEGACY_VIEW_TYPES

---

## Phase 4A: COMPLETE ✅

All Phase 4A work is done. Corrections applied and verified.

| Candidate | Status | Result |
|---|---|---|
| lm-302 | ✅ approved | legacy_noise_removed — no action needed |
| sim0500 | ✅ resolved | drug_targets tl1a row already absent from production (Wave 2B error ID'd but never committed) |
| spy072 | ✅ approved | ontology_scope_difference — no action needed |
| epi-001 | ⏸ held | needs_manual_review — keep in backfill_preview pending_review |
| batoclimab | ✅ applied | Inserted drug_indications: ted (95, Ph3) + gmg (92, Ph3). cidp deferred to Wave 2D. |
| upadacitinib | ✅ approved | normalized_gap — queue for Wave 2D atopy batch |

**Post-correction harness results (re-run Session 53e):**
- tl1a: 🟢 compare_pass_oos_adjusted (92.2% raw) — UNCHANGED, still passing
- ibd: 🟢 compare_pass_oos_adjusted (94.0% raw) — UNCHANGED, still passing
- ted: ✅ **100% match** — batoclimab correction resolved the TED normalized gap
- drug_indications: **194 rows** (192 + 2 batoclimab)
- ontology_edges: **25** (LOCKED)
- epi-001: 2 rows pending_review in backfill_preview — correctly held

---

## Phase Sequence (updated Session 53e)

| Phase | Name | Status |
|---|---|---|
| Phase 4A | Evidence Reconciliation — candidate review + corrections | ✅ COMPLETE |
| Phase 4B | Dual-read validation — parallel legacy + normalized reads | ▶ **NEXT** |
| Phase 5 | Switch dashboard logic | Blocked until 4B clears |

**Do NOT proceed to Phase 5 without completing Phase 4B.**

---

## Phase 4B Status

| Path | Description | Status |
|---|---|---|
| Path A | IBD indication-group dual-read in `_makeAreaPI()` | ✅ **COMPLETE (Session 53g)** |
| Path B | TL1A target-view gap classification | ✅ **COMPLETE (Session 53h)** |
| Path B → impl | TL1A target-view dual-read in `_makeAreaPI()` | ✅ **COMPLETE (Session 53i)** |
| Path C | `openDrugEntityModal()` dual-read | ▶ **NEXT** |

**Path A verification (run in browser after loading IBD tab):**
```javascript
window.showPhase4Compare()
// Expected: 🟢 _makeAreaPI — ibd_indication_group_view → compare_pass_oos_adjusted
```

**Path B verification (run in browser after loading TL1A tab):**
```javascript
window.showPhase4Compare()
// Expected: two records —
//   🟢 _makeAreaPI — ibd_indication_group_view → compare_pass_oos_adjusted
//   🟢 _makeAreaPI — tl1a_target_view          → compare_pass_oos_adjusted
// Console: [Phase4B-TL1A] legacy=51 norm=35 overlap=34 raw=66.7% adj=100% oos=17 → compare_pass_oos_adjusted
```

**Data quality backlog:**
`gb004.drugs.mechanism = 'Anti-TL1A'` is incorrect (actual: PHD inhibitor / HIF-1α stabilizer). Logged in `docs/evidence_reconciliation_layer.md`. Requires separate evidence review — do not fix in Phase 4B work.

---

## Next Sprint Priority Order

### P0 — Phase 4B Path C: `openDrugEntityModal()` dual-read

**Goal:** Add dual-read validation for the drug entity modal — the third blocked dashboard path.

**Context from `docs/dashboard_dependency_inventory.md`:**
The modal reads from `drug_area_scores` for competitive positioning data (overlap, cls, rationale). This is a `migration_blocker` because `drug_area_scores` has enrichment columns (overlap, rationale, cls, vs_ailux) with no equivalent in `drug_indications`/`drug_targets`. The dual-read here is diagnostic — confirming which drugs appear in modal vs. normalized, not yet switching the source.

**Implementation pattern:**
- In `openDrugEntityModal()` or `_loadDynamicDetail()`: run parallel reads from `drug_targets` and `drug_indications` for the opened drug
- Compare against `drug_area_scores` data already fetched
- Write record to `window.__MERIDIAN_PHASE4_COMPARE__` with `path: 'drug_entity_modal'`
- No visual changes — modal still reads from legacy source

### P1 — epi-001 Manual Review (Track B)

### P1 — epi-001 Manual Review (Track B)
- Search for published source evidence confirming IBD indication
- If IBD confirmed: commit uc + cd rows from backfill_preview (wave2c run)
- If no evidence: keep held or set review_status = 'no_evidence'
- Drug: anti-TL1A antibody, preclinical stage. **Do NOT commit without source evidence.**

### P2 — Wave 2D: FcRn + Autoimmune Backfill (Track A)
- fcrn coverage: 57.1% → target: 85%+
- autoimmune coverage: 52% → target: 80%+
- Include: upadacitinib → ad (approved), batoclimab → cidp (re-evaluate), imvt-1402 → gmg/cidp/waiha
- Run standard backfill_preview → validate → commit workflow

### P3 — Track B True Missing Rows
- `imvt-1402` → gmg, cidp, waiha: true_missing_row
- `ep006` → tombstone or merge into es302 (duplicate drug_id data integrity)

### P4 — Portfolio Intelligence Product (Track C)
Drug → Company joins now available. First intelligence product.
**Question:** "What is [company]'s full indication footprint across all areas we track?"

### P5 — Build entity_consistency_checks Table
**Trigger:** Build AFTER Phase 4B dual-read validates and first reconciliation script is ready to write rows. Do NOT build speculatively.  
**Migration SQL:** in `docs/evidence_reconciliation_layer.md`  
**Seed data:** 6 Phase 4A candidates + their advisor-approved resolution status

---

## 5-Track Workstream Status

| Track | Focus | Status |
|---|---|---|
| A — Relationship Layer | Wave 2D FcRn + autoimmune (epi-001 first) | ⏸ epi-001 pending review |
| B — Ontology Quality | Phase 4B dual-read → true missing rows | ▶ NEXT (with D) |
| C — Intelligence Products | Portfolio intelligence product | Queued |
| D — Dashboard Architecture | Phase 4B dual-read validation | ▶ NEXT |
| E — Data Acquisition | Normalization engine → platform library | Documented; deferred |

---

## Active Constraints

1. **ontology_edges locked** — 25 rows. Do NOT unlock until advisor approves after Phase 4B.
2. **No Phase 5 dashboard migration** — Phase 4B dual-read must validate zero regressions first.
3. **epi-001 held** — 2 rows in backfill_preview as pending_review. Do NOT commit without source evidence.
4. **batoclimab → cidp** — NOT committed. Deferred to Wave 2D FcRn backfill batch.
5. **compare_pass ≠ migration-ready** — tl1a/ibd/ted cleared Phase 4 compare threshold. Phase 4B dual-read is the migration gate.

---

## Validation Checks Before Starting Work

```sql
SELECT count(*) FROM drug_indications;             -- expect 194
SELECT count(*) FROM trial_indications;            -- expect 301
SELECT count(*) FROM drug_targets;                 -- expect 168
SELECT count(*) FROM ontology_edges;               -- expect 25 (LOCKED)
-- batoclimab correction verified:
SELECT indication_id, confidence_score FROM drug_indications WHERE drug_id = 'batoclimab';
-- expect: ted (95), gmg (92)
-- epi-001 still held:
SELECT source_id, target_id_col, preview_status FROM backfill_preview
  WHERE backfill_run_id = 'wave2c_ibd_20260525_203134' AND source_id = 'epi-001';
-- expect 2 rows: uc + cd, preview_status = 'pending_review'
```

---

## Files to Load at Start of Next Session

1. `docs/phase4_comparison_harness.md` — current harness output (tl1a 🟢 · ibd 🟢 · ted ✅)
2. `docs/phase4a_reconciliation_review.md` — Phase 4A candidate review with advisor decisions
3. `docs/evidence_reconciliation_layer.md` — entity_consistency_checks design
4. `docs/dashboard_dependency_inventory.md` — 12 blocked paths for Phase 4B dual-read
5. `docs/normalization_engine.md` — parser reference
6. `scripts/phase4_compare_legacy_vs_normalized.py` — harness script (v3)
7. `MEMORY.md` → `project_parallel_workstreams.md`, `project_meridian_maturity.md`
