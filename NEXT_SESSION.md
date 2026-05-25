# NEXT SESSION — BD Platform

**Last session:** Session 53 (2026-05-25)  
**Completed:** Wave 2C COMMITTED (63 rows) · Phase 4 harness updated (OOS-adjusted logic) · tl1a/ibd reclassified to compare_pass_oos_adjusted · uc/cd Program Board badges moved to Compare Pass  
**Prior milestone:** Phase 4 Comparison Harness (Session 51) · L4 Queryable (Session 50)

---

## Advisor Decision — Option A (2026-05-25)

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

## State of the Platform

### What Just Happened (Session 53)
- Wave 2C committed: 63 rows to drug_indications · 2 held (epi-001, review_required)
- drug_indications total: **192 rows**
- Post-commit V1-V8 validation: all pass
- Phase 4 harness v2: OOS-adjusted coverage logic added · `CONFIRMED_OOS_BY_AREA` constant · `compare_pass_oos_adjusted` status · governance rule section in docs
- `docs/phase4_comparison_harness.md` regenerated: tl1a 🟢 · ibd 🟢

### Active Constraints
1. **epi-001 held** — 2 rows remain in backfill_preview as pending_review / review_required. Do NOT commit without manual review of epi-001 IBD indication evidence.
2. **Do NOT unlock ontology_edges** — remains at 25 until advisor explicitly approves after Phase 4 dual-read validation
3. **Do NOT migrate BLOCKED dashboard references** — Phase 4 dual-read comparison layer must validate zero regressions first
4. **compare_pass ≠ migration-ready** — tl1a/ibd cleared Phase 4 compare threshold; they are NOT cleared for Phase 5 (dashboard migration). Dual-read validation is the gate.

---

## Next Sprint Priority Order

### P0 — Phase 4 Dual-Read Validation (Track D)

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

### P1 — epi-001 Manual Review (Track B)
Review EPI-001 clinical evidence:
- Is there any indication_short available or published trial data for IBD?
- If confirmed IBD target: commit epi-001 (uc + cd, conf 76, review_required)
- If uncertain: keep held
- Drug: anti-TL1A antibody, preclinical stage
- Committing epi-001 would push tl1a raw to 96.1% and ibd raw to 98% (both above 95% raw)

### P2 — Track B True Missing Rows
From mismatch classification in `docs/phase4_comparison_harness.md` Part 4:
- `upadacitinib` → ad: true_missing_row
- `imvt-1402` → gmg, cidp, waiha: true_missing_row
- `ep006` → tombstone or merge into es302 (duplicate drug_id data integrity)

### P3 — Portfolio Intelligence Product (Track C)
Drug → Company joins are now available. First intelligence product using completed ontology layer.
**Question:** "What is [company]'s full indication footprint across all areas we track?"

### P4 — Wave 2D: FcRn + Autoimmune Backfill (Track A)
Next largest coverage gaps: fcrn (57.1%) and autoimmune (48%).

---

## 5-Track Workstream Status

| Track | Focus | Status |
|---|---|---|
| A — Relationship Layer | epi-001 review → Wave 2D FcRn/autoimmune | ⏸ epi-001 pending review |
| B — Ontology Quality | True missing rows (upadacitinib, imvt-1402, ep006 merge) | Queued |
| C — Intelligence Products | Portfolio intelligence product | Queued |
| D — Dashboard Architecture | Phase 4 dual-read validation (12 paths) | ▶ NEXT |
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

1. `docs/phase4_comparison_harness.md` — updated with OOS-adjusted logic (regenerated 2026-05-25)
2. `docs/normalization_engine.md` — parser reference
3. `docs/dashboard_dependency_inventory.md` — 12 blocked paths for Phase 4 dual-read
4. `scripts/phase4_compare_legacy_vs_normalized.py` — harness script (v2 with OOS logic)
5. `MEMORY.md` → `project_parallel_workstreams.md`, `project_meridian_maturity.md`
