# NEXT SESSION — BD Platform

**Last session:** Session 53l (2026-05-25) — Freshness Automation + Company Fleet lift to 96/100  
**Prior session:** Session 53k — Company Governance Phase

---

## Company Governance Phase: COMPLETE ✅

Company layer is now structurally sound. Do not revisit manually — freshness is the only remaining gap, and it should be automated (see P0 below).

| Metric | Result |
|---|---|
| P0 (blocking) | 0 |
| P1 (quality) | 2 (intentional orphan signals only) |
| Fleet average | 96/100 (after freshness automation — see below) |
| A-grade companies | 89 |
| B-grade companies | 12 (10 need enrichment pipeline; 2 intentional orphans) |
| C-grade companies | 0 |

**What was built/applied this session:**
- Acquired-asset rule: `company_id=acquirer`, `company_display="X w/Y"`, `original_company_id`, `acquired_asset=true`
- OWNERSHIP ≠ IDENTITY governance rule (Ailux/XtalPi model; parent_company_id + ownership_type)
- QuantumPharm resolved: former name of XtalPi Holdings (same entity); alias marked 'former'
- Ghost records deleted: xencor-412, xencor-942 (17 intel rows migrated to xencor)
- `coverage_status` field: active / reference / planned / orphan
- 32 no-drug companies classified; 4 acquired companies set to reference
- 50 companies geography-backfilled from hq_country
- 71 primary aliases seeded
- `company_validator.py` deployed: P0/P1/P2 checks + 6-dimension Health Score (0–100)

**Backlog note (do not build now):**
Add `drug_id` / `program_id` to the `intel` table for structured program-level attribution. Currently intel rolls up to company level; program specificity lives in headline/body text only.

---

## Freshness Automation: COMPLETE ✅

**Built and deployed (2026-05-25):**
- `scripts/refresh_company_verified.py` — 3-tier freshness refresh (protected fields list; JSONL log; drug_validation_results)
- `.github/workflows/refresh-company-verified.yml` — weekly Sunday 06:00 UTC; manual dispatch with --company / --dry-run / --all options

**Result after first run:**
| Metric | Before | After |
|---|---|---|
| Fleet average | 91/100 | **96/100** |
| A-grade | 60 | **89** |
| B-grade | 39 | **12** |
| C-grade | 2 | **0** |

**Remaining B-grade (12 companies):**
- 10 active companies with `last_verified=null` and no `last_enriched_at` — these are in the enrichment pipeline queue (ailux, aurinia, biosion, imagenebio, incyte, lynkpharma, moonlake, viridian, yarrow, zenas). They will auto-lift to A once enrichment pipeline runs for them.
- 2 intentional orphans (yunnan-baiyao, pien-tze-huang) — pipeline=0 penalty is correct, do not change.

**Target:** Fleet average 98+ once enrichment pipeline touches the 10 active B-grade companies.

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
| Path C | `openDrugEntityModal()` dual-read | ✅ **COMPLETE (Session 53j)** |

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

**Path C verification (open drug entity modal for a test drug):**
```javascript
// After opening any drug modal (e.g., lm-302, batoclimab, epi-001):
window.showPhase4Compare()
// Expected: record with component='openDrugEntityModal', path='drug_entity_modal'
// Console: [Phase4C-Modal] drug=X areas=[...] targets=[...] inds=[...] → status

// Test cases:
// lm-302 (tl1a, ibd areas) → cross_table_inconsistency (no tl1a target, no ibd inds)
// epi-001 (tl1a, ibd areas) → needs_manual_review
// batoclimab (fcrn, ted, autoimmune) → acceptable_mismatch or match
```

**Data quality backlog:**
`gb004.drugs.mechanism = 'Anti-TL1A'` is incorrect (actual: PHD inhibitor / HIF-1α stabilizer). Logged in `docs/evidence_reconciliation_layer.md`. Requires separate evidence review — do not fix in Phase 4B work.

---

## Next Sprint Priority Order

### P0 — entity_consistency_checks: One manual step to execute

**Status:** Plan advisor-approved + all three fixes applied. Awaiting manual SQL execution.

**One manual step:**
1. Open: https://supabase.com/dashboard/project/tghntyofptvfhmtchwcv/sql/new
2. Paste contents of `migrations/entity_consistency_checks_v1.sql`
3. Click Run (Cmd+Enter)
4. Then run `python3 scripts/apply_entity_consistency_checks.py` — verifies 7 rows and prints results

**Advisor fixes applied (v1 final):**
- `issue_key TEXT NOT NULL` added — allows multiple issues per entity × classification
- `UNIQUE (entity_type, entity_id, issue_key)` — granular idempotency
- CHECK constraints on `check_type` (5 values) and `classification` (8 values)
- upadacitinib: `review_status = 'accepted'` (gap confirmed real, correction pending Wave 2D)

**Expected post-execution verification:**
- count(*) = 7
- open + high-severity = 0 (no Phase 5 blockers)
- Held: epi-001 + gb004
- upadacitinib: status=open, review_status=accepted
- batoclimab: status=corrected, review_status=resolved
- lm-302 / sim0500 / spy072: status=closed, review_status=accepted

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
