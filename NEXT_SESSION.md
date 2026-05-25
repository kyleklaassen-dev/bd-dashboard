# NEXT SESSION — BD Platform

**Last session:** Session 53e (2026-05-25)  
**Completed:** Phase 4A corrections applied · batoclimab ted+gmg backfilled · Phase 4 harness re-run · ted now 100% match  
**Prior milestones:** Phase 4A Candidate Review (Session 53d) · Wave 2C COMMITTED 63 rows (Session 53) · tl1a/ibd compare_pass_oos_adjusted

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

## Next Sprint Priority Order

### P0 — Phase 4B: Dual-Read Validation (Track D)

**Goal:** Add parallel read paths alongside legacy queries in `_makeAreaPI` and `openDrugEntityModal`. Compare outputs in-browser, log any regressions. Assert parity. NO visual changes.

**Ontology governance (2026-05-25 — applies to Phase 4B design):**
> Legacy dashboard areas are not a uniform category. TL1A is a biological TARGET. IBD is an indication group. These have different normalized replacement paths and require separate dual-read validation:
>
> - **TL1A [target_view]** → normalized via `drug_targets WHERE target_id = 'tl1a'`
> - **IBD [indication_group_view]** → normalized via `drug_indications WHERE indication_id IN ('uc','cd')`
>
> Do NOT implement a single merged dual-read for both. Do NOT compare tl1a + ibd as one pool.

**Starting files:**
- `docs/phase4_comparison_harness.md` — Part 2 (view-type-separated comparisons) and Part 5 (readiness by view type)
- `docs/dashboard_dependency_inventory.md` — blocked dashboard paths
- `LEGACY_VIEW_TYPES` constant in `scripts/phase4_compare_legacy_vs_normalized.py` — canonical view type mapping

**Current Phase 4 comparison status by view type:**

| Legacy Area | View Type | Phase 4 Status | Normalized Path | Phase 4B Ready? |
|---|---|---|---|---|
| `ibd` | indication_group_view | 🟢 compare_pass_oos_adjusted | `drug_indications` uc+cd | ✅ Ready for indication-group dual-read |
| `ted` | indication_view | ✅ 100% match | `drug_indications` ted | ✅ Ready for indication dual-read |
| `tl1a` | target_view | 🔴 migration_blocker* | `drug_targets` tl1a | ❌ Blocked — target-view gap identified |

*TL1A target-view shows migration_blocker when compared against `drug_targets.target_id = 'tl1a'` (the correct semantic path). This is a new finding from the ontology clarification: many drugs in the legacy TL1A area are UC/CD indication drugs that were placed there for IBD relevance, not because they directly target TL1A. The TL1A target-view dual-read requires drug_targets backfill before it can pass.

**Phase 4B implementation — two separate dual-read paths:**

**Path A: IBD indication-group dual-read** (ready now — begin here)
1. In `_makeAreaPI()` for the IBD tab:
   - Legacy read: `drug_area_scores WHERE area_id = 'ibd'`
   - Normalized read: `drug_indications WHERE indication_id IN ('uc','cd')`
   - Log to console: `[Phase4B-IBD] legacy_count={N} norm_count={N} diff=[...]`
   - Assert row count parity (adjusted for classified noise)

**Path B: TL1A target-view dual-read** (blocked — needs drug_targets coverage audit first)
1. Identify which drugs in `drug_area_scores.area_id = 'tl1a'` are missing `drug_targets.target_id = 'tl1a'` rows
2. Classify: are they (a) confirmed TL1A target drugs missing drug_targets rows → backfill needed, or (b) IBD indication drugs placed in legacy TL1A area → ontology_scope_difference
3. After classification: implement dual-read using `drug_targets WHERE target_id = 'tl1a'` as the normalized source
4. Only then assert parity

**Path C: openDrugEntityModal() dual-read** (separate — uses drug_targets + drug_indications alongside drug_area_scores)

**Acceptance criteria:**
- (a) Both read paths run without error
- (b) IBD indication-group path: row counts match (with classified noise accounted for)
- (c) TL1A target-view path: gap fully classified before parity assertion
- (d) No dashboard visual regressions
- (e) No merged ibd+tl1a comparison anywhere in the dual-read implementation

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
