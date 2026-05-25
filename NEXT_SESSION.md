# NEXT SESSION — BD Platform

**Last session:** Session 53 (2026-05-25)  
**Completed:** Wave 2C COMMITTED (63 rows) · Phase 4 harness rerun · tl1a/ibd reclassified  
**Prior milestone:** Phase 4 Comparison Harness (Session 51) · L4 Queryable (Session 50)

---

## State of the Platform

### What Just Happened (Session 53)
- Wave 2C committed: 63 rows to drug_indications · 2 held (epi-001, review_required)
- drug_indications total: **192 rows** (129 pre-Wave 2C + 63 committed)
- Post-commit V1-V8 validation: all pass
- Phase 4 harness rerun: tl1a **92.2%** 🟡 · ibd **94.0%** 🟡 (both reclassified from 🔴 migration_blocker → 🟡 acceptable_mismatch)
- **Gap analysis:** 3 OOS exclusions (lm-302/sim0500/spy072) + 1 held (epi-001) keep raw % below 95%. Effective coverage excluding confirmed OOS = **97.9%**
- **Pending advisor decision:** does 95% threshold apply to raw or OOS-adjusted (effective) coverage?
- Readiness indicator: uc=92% blocked, cd=94% blocked — awaiting advisor threshold decision

### Active Constraints
1. **epi-001 held** — 2 rows remain in backfill_preview as pending_review / review_required. Do NOT commit without manual review of epi-001 IBD indication evidence.
2. **Do NOT unlock ontology_edges** — remains at 25 until advisor explicitly approves after Phase 4 dual-read validation
3. **Do NOT migrate BLOCKED dashboard references** — Phase 4 comparison layer must exist first
4. **tl1a/ibd readiness decision pending** — advisor must rule on raw vs. effective threshold before moving to Phase 4 compare pass

---

## Next Sprint Priority Order

### P0 — Advisor Decision: 95% threshold (raw vs. effective)
The commit is done. The gap between projected (97.9% effective) and actual (92.2%/94.0% raw) is explained entirely by 3 confirmed OOS drugs that will NEVER be in drug_indications:
- `lm-302`: gastric cancer drug, in legacy tl1a area by curation error
- `sim0500`: RRMM drug, in legacy tl1a area by curation error
- `spy072`: TL1A-targeting drug for PsA/axSpA (rheumatology), not IBD

**Option A:** Accept effective coverage (97.9%) as the threshold metric → tl1a/ibd move to "ready for Phase 4 compare". Update COMPARISON_READINESS in index.html from "blocked" to "close" (or "ready" if advisor approves Phase 4 compare pass).

**Option B:** Commit epi-001 after manual review → raw coverage becomes 49/51 = 96.1% for tl1a, 49/50 = 98% for ibd → both above 95% → tl1a/ibd move to ready.

**Option C:** Keep 95% raw threshold. Accept that 3 permanently excluded OOS drugs create a 2.8%/1% floor on the raw gap. Move on to Phase 4 compare pass with current 92-94% (the actual dashboard migration safety is high since the excluded drugs are confirmed not-IBD).

### P1 — Phase 4 Dual-Read Validation (Track D)
**What to build:** For `_makeAreaPI` and `openDrugEntityModal`, add a parallel read path alongside the legacy query. Compare outputs in-browser and log any regressions.

**Starting point:** `docs/phase4_comparison_harness.md` Part 2 and Part 5.

**Acceptance criteria:**
- (a) Both old and new read paths run in parallel on production data
- (b) Row counts match for each indication
- (c) No dashboard visual regressions
- (d) Enrichment write-side simultaneously migrated (for drug_area_scores replacement)

### P2 — epi-001 Manual Review
Review EPI-001 clinical evidence:
- Is there any indication_short available or published trial data for IBD?
- If confirmed IBD target: commit epi-001 (uc + cd, conf 76, review_required)
- If uncertain: keep held
- Drug: anti-TL1A antibody, preclinical stage

### P3 — Track B True Missing Rows
From mismatch classification in `docs/phase4_comparison_harness.md` Part 4:
- `upadacitinib` → ad: true_missing_row
- `imvt-1402` → gmg, cidp, waiha: true_missing_row
- `ep006` → tombstone or merge into es302 (duplicate drug_id data integrity)

### P4 — Portfolio Intelligence Product (Track C)
Drug → Company joins are now available. First intelligence product using completed ontology layer.
**Question:** "What is [company]'s full indication footprint across all areas we track?"

### P5 — Wave 2D: FcRn + Autoimmune Backfill (Track A)
Next largest coverage gaps: fcrn (57.1%) and autoimmune (48%). After advisor clears the tl1a/ibd threshold question.

---

## 5-Track Workstream Status

| Track | Focus | Status |
|---|---|---|
| A — Relationship Layer | Threshold decision → epi-001 review → Wave 2D | ⏸ AWAITING ADVISOR |
| B — Ontology Quality | True missing rows (upadacitinib, imvt-1402, ep006 merge) | Queued |
| C — Intelligence Products | Portfolio intelligence product | Queued |
| D — Dashboard Architecture | Phase 4 dual-read validation | ▶ NEXT |
| E — Data Acquisition | Normalization engine → platform library | Documented; deferred |

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
```

---

## Files to Load at Start of Next Session

1. `docs/phase4_comparison_harness.md` — current comparison state (rerun 2026-05-25 20:48)
2. `docs/normalization_engine.md` — parser reference
3. `scripts/wave2c_drug_indications_ibd_backfill.py` — if epi-001 review needed, use `--commit --run-id wave2c_ibd_20260525_203134`
4. `MEMORY.md` → `project_parallel_workstreams.md`, `project_meridian_maturity.md`
