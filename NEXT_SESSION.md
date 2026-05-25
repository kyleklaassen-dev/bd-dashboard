# NEXT SESSION — BD Platform

**Last session:** Session 52 (2026-05-25)  
**Completed:** Wave 2C IBD Backfill Preview · Track B mismatch classification · Track C readiness indicator  
**Prior milestone:** Phase 4 Comparison Harness (Session 51) · L4 Queryable (Session 50)  
**Deploy commits:** a9829d58b1 (harness.md) · ff37daa24e (index.html)

---

## State of the Platform

### What Just Happened (Session 52)
- Wave 2C `--preview` run: run_id `wave2c_ibd_20260525_203134` · 68 rows in backfill_preview
- 36 missing tl1a/ibd drugs assessed: 32 mapped, 3 excluded (legacy_noise + OOS), 1 held (epi-001, review_required)
- Expected post-commit match %: ≥97% for both tl1a and ibd (above 95% threshold)
- Track B: Full mismatch classification added to `docs/phase4_comparison_harness.md` — 6 type taxonomy
- Track C: Migration readiness badge added to Indication Landscape Card (uc/cd=Blocked, asthma=Ready, ad/ted=Close, gmg/sle=Not Ready)
- **WAITING:** Advisor approval to commit Wave 2C rows to drug_indications

### What Just Happened (Session 51)
- Phase 4 Comparison Harness built: `scripts/phase4_compare_legacy_vs_normalized.py` + `docs/phase4_comparison_harness.md`
- 11 legacy area_id → indication mappings compared; 5 high-risk dashboard functions assessed
- **Primary gating item identified:** drug_indications covers only 30% of tl1a/ibd legacy drugs (17/50)
- tcell area: 0% overlap — not_ready; fundamental mapping issue between legacy CAR-T drugs and approved hematology drugs
- 3 areas at 100% match: il4ra, respiratory, tslp — safe when drug_indications scale is resolved

### What Just Happened (Session 50)
- Wave 2B trial_indications committed: 315 rows + 4 held rows individually reviewed
- L4 canonical query validation suite: 5/5 passed
- ontology_edges count: 25 — **LOCKED until Phase 4 comparison layer proven**

### Active Constraints
1. **Do NOT commit Wave 2C** — advisor approval required first (preview staged in backfill_preview, run_id: wave2c_ibd_20260525_203134)
2. **Do NOT unlock ontology_edges** — remains at 25 until advisor explicitly approves after Phase 4 dual-read validation
3. **Do NOT migrate BLOCKED/NEEDS MIGRATION dashboard references** — Phase 4 comparison layer must exist first

---

## Next Sprint Priority Order

### P0 — Wave 2C Commit (Track A) ← AWAITING ADVISOR APPROVAL
**The preview is complete.** The advisor must review the preview report and approve the commit.

Preview report is in the `--preview` terminal output (run_id: wave2c_ibd_20260525_203134). Key metrics:
- 65 committable rows (32 drugs × UC+CD, minus golimumab which is UC-only)
- 3 exclusions: lm-302, sim0500, spy072
- 2 held rows: epi-001 (both uc + cd, conf 76, review_required)
- Data integrity flag: ep006 + es302 are duplicate drug_ids for ES302

**To commit once approved:**
```bash
python3 scripts/wave2c_drug_indications_ibd_backfill.py --commit
```

**Post-commit action required:** Run `--validate` to confirm V1-V8 checks pass.

**After commit:** Run Phase 4 harness script again to confirm tl1a/ibd match % ≥ 95%.

### P1 — Phase 4 Dual-Read Validation (Track D)
**What to build:** For `_makeAreaPI` and `openDrugEntityModal`, add a parallel read path alongside the legacy query. Compare outputs in-browser and log any regressions.

**Starting point:** `docs/phase4_comparison_harness.md` Part 2 and Part 5.

**Acceptance criteria:**
- (a) Both old and new read paths run in parallel on production data
- (b) Row counts match for each indication
- (c) No dashboard visual regressions
- (d) Enrichment write-side simultaneously migrated (for drug_area_scores replacement)

### P1 — Portfolio Intelligence Product (Track C)
Drug → Company joins are now available via `drugs.company_id`. The company portfolio view hasn't been built.

**Question it answers:** "What is [company]'s full indication footprint across all areas we track?"

**Dependencies:** drugs (company_id), drug_indications (indication_id), drug_targets (target_id), indications

### P2 — Track B Follow-Up: True Missing Rows
From the mismatch classification in `docs/phase4_comparison_harness.md` Part 4:
- `upadacitinib` → ad: true_missing_row (atopy area drug, should be in drug_indications)
- `imvt-1402` → gmg, cidp, waiha: true_missing_row (FcRn drug missing from drug_indications)
- `ep006` → tombstone or merge into es302 (duplicate drug_id data integrity issue)

### P3 — Wave 2C: UC/CD Composite Resolution (Track B/E)
28 UC·CD composite strings were deferred from Wave 2A. These should now be resolved using the composite split logic documented in `normalization_engine.md`.

**Note:** Run dry-run first. These are expected to resolve cleanly via the middle-dot composite splitter.

### P4 — Ontology Edges Unlock (Track B)
Once Phase 4 comparison layer validates zero regressions, advisor approves ontology_edges expansion. Current lock count: 25. The missing edges (veligrotug/elegrobart for TED × IGF-1R_TSHR) are documented in `project_competitive_landscape_layer.md`.

---

## 5-Track Workstream Status

| Track | Focus | Status |
|---|---|---|
| A — Relationship Layer | Wave 2C commit approval · then FcRn/autoimmune backfill | ⏸ WAITING ADVISOR APPROVAL |
| B — Ontology Quality | True missing rows (upadacitinib→ad, imvt-1402→fcrn); ep006 merge | Queued |
| C — Intelligence Products | Portfolio intelligence product | Queued |
| D — Dashboard Architecture | Phase 4 dual-read validation | Queued |
| E — Data Acquisition | Normalization engine → platform library | Documented; library build deferred |

Resource allocation: A 70% · B 10% · C 10% · D 5% · E 5%

---

## Validation Checks Before Starting Work

```sql
SELECT count(*) FROM trial_indications;            -- expect 319
SELECT count(*) FROM drug_indications;             -- expect 129 (pre-Wave 2C commit)
SELECT count(*) FROM drug_targets;                 -- expect 173
SELECT count(*) FROM ontology_edges;               -- expect 25 (LOCKED)
SELECT count(*) FROM backfill_preview
  WHERE backfill_run_id = 'wave2c_ibd_20260525_203134'
  AND preview_status = 'pending_review';           -- expect 68 (65 + 3 excluded rows staged)
```

After Wave 2C commit:
```sql
SELECT count(*) FROM drug_indications;             -- expect 129 + 63 = ~192 (65 rows minus 2 review_required)
```

---

## Files to Load at Start of Next Session

1. `docs/phase4_comparison_harness.md` — comparison results + Track B classifications
2. `docs/normalization_engine.md` — parser reference  
3. `scripts/wave2c_drug_indications_ibd_backfill.py` — commit with `--commit` flag when approved
4. `MEMORY.md` → `project_parallel_workstreams.md`, `project_meridian_maturity.md`
