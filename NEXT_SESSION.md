# NEXT SESSION — BD Platform

**Last session:** Session 51 (2026-05-25)  
**Completed:** Phase 4 Comparison Harness — 11 legacy areas vs normalized ontology, 5 dashboard functions  
**Prior milestone:** L4 Queryable (Session 50) — drug_targets (173) + drug_indications (129) + trial_indications (319)  
**Deploy commit:** (see below)

---

## State of the Platform

### What Just Happened (Session 51)
- Phase 4 Comparison Harness built: `scripts/phase4_compare_legacy_vs_normalized.py` + `docs/phase4_comparison_harness.md`
- 11 legacy area_id → indication mappings compared; 5 high-risk dashboard functions assessed
- **Primary gating item identified:** drug_indications covers only 30% of tl1a/ibd legacy drugs (17/50)
- **tcell area:** 0% overlap — not_ready; fundamental mapping issue between legacy CAR-T drugs and approved hematology drugs
- **loadAreaDeals:** not_ready — deals.indication_id FK does not exist
- 3 areas at 100% match: il4ra, respiratory, tslp — safe when drug_indications scale is resolved

### What Just Happened (Session 50)
- Wave 2B trial_indications committed: 315 rows + 4 held rows individually reviewed
- L4 canonical query validation suite: 5/5 passed
- Program Board updated (Track C), dependency inventory updated (Track D), normalization engine documented (Track E)
- ontology_edges count: 25 — **LOCKED until Phase 4 comparison layer proven**

### Active Constraints
1. **Do NOT unlock ontology_edges** — remains at 25 until advisor explicitly approves after Phase 4 dual-read validation
2. **Do NOT migrate BLOCKED/NEEDS MIGRATION dashboard references** — Phase 4 comparison layer must exist first
3. **Do NOT commit Wave 2C (UC·CD composites)** or Wave 2D (multi-portfolio) without advisor approval

---

## Next Sprint Priority Order

### P0 — Expand drug_indications coverage for tl1a/ibd areas (Track A)
**This is the primary gating item.** The Phase 4 harness found that drug_indications covers only 30% of tl1a/ibd legacy drugs.

The comparison harness (`docs/phase4_comparison_harness.md`) lists 36 drugs in the legacy `tl1a` area with no drug_indications counterpart. These are the drugs the IBD/TL1A tab will lose if migrated now.

**Action:** Build Wave 2C drug_indications backfill targeting the specific drugs in `drug_areas.area_id = 'tl1a'` or `'ibd'` that do NOT appear in `drug_indications`. Use the normalization engine pipeline (dry-run → preview → advisor approval → commit).

**Acceptance criteria:** tl1a+ibd match % ≥ 95% before any _makeAreaPI migration.

### P1 — Phase 4 Dual-Read Validation (Track D)
**What to build:** For _makeAreaPI and openDrugEntityModal, add a parallel read path alongside the legacy query. Compare outputs in-browser and log any regressions.

**Starting point:** `docs/phase4_comparison_harness.md` Part 2 and Part 5.

**Acceptance criteria (from inventory):**
- (a) Both old and new read paths run in parallel on production data
- (b) Row counts match for each indication
- (c) No dashboard visual regressions
- (d) Enrichment write-side simultaneously migrated (for drug_area_scores replacement)

### P1 — Portfolio Intelligence Product (Track C)
Drug → Company joins are now available via `drugs.company_id`. The company portfolio view hasn't been built. This is the first intelligence product that requires the completed ontology layer.

**Question it answers:** "What is [company]'s full indication footprint across all areas we track?"

**Dependencies:** drugs (company_id), drug_indications (indication_id), drug_targets (target_id), indications

### P2 — Wave 2C: UC/CD Composite Resolution (Track B/E)
28 UC·CD composite strings were deferred from Wave 2A. These should now be resolved using the composite split logic documented in `normalization_engine.md`.

**Note:** Run dry-run first. These are expected to resolve cleanly via the middle-dot composite splitter.

### P3 — Ontology Edges Unlock (Track B)
Once Phase 4 comparison layer validates zero regressions, advisor approves ontology_edges expansion. Current lock count: 25. The missing edges (veligrotug/elegrobart for TED × IGF-1R_TSHR) are documented in `project_competitive_landscape_layer.md`.

### P4 — QA Sprint: Catalyst Cleanup (Track B)
From `project_qa_sprint_roadmap.md`:
- P1: catalyst cleanup (sources, deduplication)
- P2: re-enrich verification fields
- P3: validation_tests table

---

## 5-Track Workstream Status

| Track | Focus | Status |
|---|---|---|
| A — Relationship Layer | Phase 4 comparison layer | ▶ NEXT |
| B — Ontology Quality | Wave 2C composites; catalyst QA | Queued |
| C — Intelligence Products | Portfolio intelligence product | Queued |
| D — Dashboard Architecture | Phase 4 gating; dependency migration | ▶ NEXT (with A) |
| E — Data Acquisition | Normalization engine → platform library | Documented; library build deferred |

Resource allocation: A 70% · B 10% · C 10% · D 5% · E 5%

---

## Files to Load at Start of Next Session

1. `docs/dashboard_dependency_inventory.md` — Phase 4 targets
2. `docs/normalization_engine.md` — parser reference
3. `scripts/wave2b_trial_indications_backfill.py` — template for Wave 2C
4. `MEMORY.md` → `project_meridian_maturity.md`, `project_parallel_workstreams.md`

---

## Validation Checks Before Starting Work

```
SELECT count(*) FROM trial_indications;            -- expect 319
SELECT count(*) FROM drug_indications;             -- expect 129
SELECT count(*) FROM drug_targets;                 -- expect 173
SELECT count(*) FROM ontology_edges;               -- expect 25 (LOCKED)
SELECT count(*) FROM backfill_preview
  WHERE preview_status = 'pending_review';         -- expect 0 (all held rows committed)
```
