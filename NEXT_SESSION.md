# NEXT SESSION — BD Platform

**Last session:** Session 53o (2026-05-25) — Phase 5 migration plan + unified dashboard architecture design  
**Prior session:** Session 53n — Phase 4B Path C modal verification + Phase 4C IBD verified

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

## Phase Sequence (updated Session 53m)

| Phase | Name | Status |
|---|---|---|
| Phase 4A | Evidence Reconciliation — candidate review + corrections | ✅ COMPLETE |
| Phase 4B | Dual-read validation — parallel legacy + normalized reads | ✅ COMPLETE |
| Phase 4C | Pre-migration classification sprint — explain every difference | ▶ **CURRENT** |
| Phase 5 | Incremental source switch — feature-flagged, per-component | Blocked until 4C clears |

**Do NOT proceed to Phase 5 without completing Phase 4C. Do NOT do broad dashboard rewiring — migrate one component at a time with feature flags.**

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

**Path C verification — COMPLETED (Session 53m browser run):**

| Drug | Modal status | entity_consistency_checks | Verdict |
|---|---|---|---|
| lm-302 | `needs_manual_review` | closed / legacy_noise_removed | ✅ Explainable — tl1a area is legacy noise (CLDN18.2 ADC, not TL1A biology) |
| batoclimab | `cross_table_inconsistency` | corrected (ted+gmg fixed) | ✅ Explainable — igf1r/autoimmune = legacy catch-all artifact (documented in conflict_summary) |
| epi-001 | `acceptable_mismatch` | open / held | ✅ Explainable — IBD inds held pending source evidence |

**Correction from original prediction:** lm-302 is in `drug_areas` for `tl1a` ONLY — not ibd. The "(tl1a, ibd areas)" prediction was wrong. Confirmed via direct Supabase query.

**Calibration note:** Modal auto-classification differs from entity_consistency_checks human classifications. This is expected — modal produces first-pass automated classifications; entity_consistency_checks holds human-reviewed resolutions. All 3 differences are fully explainable when cross-referenced. No new entity_consistency_checks rows required (batoclimab igf1r/autoimmune documented in existing row's conflict_summary).

**gb004 mechanism patch — APPLIED (Session 53n):**
`drugs.mechanism` updated: `'Anti-TL1A'` → `'PHD inhibitor (HIF-1α stabilizer)'`. Approved by Kyle 2026-05-25. entity_consistency_checks row → status=corrected, review_status=resolved.

---

## Phase 4C Sprint — Component Validation Order

Full plan: `docs/phase4c_validation_plan.md`

| Rank | Component | Risk | Phase 4B Status | Phase 5 Candidate |
|---|---|---|---|---|
| 1 | IBD area tab | Low | ✅ compare_pass_oos_adjusted | ✅ First |
| 2 | TED area tab (igf1r-tshr) | Low | ✅ data layer proven (4A) | ✅ Second |
| 3 | Drug entity modal | Low–Med | ✅ Path C deployed | ✅ Third (after 10-drug sprint) |
| 4 | TL1A area tab | Medium | ✅ compare_pass_oos_adjusted | ⚠️ Fourth — needs TL1A arch review |
| 5 | TSLP area tab | Medium | ❌ None | ⏸ After Wave 2D |
| 6 | IL-4Rα area tabs | Medium | ❌ None | ⏸ After Wave 2D atopy |
| 7 | FcRn area tab | High | ❌ None | 🚫 Blocked — Wave 2D first |
| 8 | ACE area tab | High | ❌ None | 🚫 Deferred |

**Phase 4C task for IBD:** ✅ **VERIFIED (Session 53m)** — compare_pass_oos_adjusted. legacy=50, norm=50, overlap=47, 3 OOS (epi-001/sim0500/spy072), raw=94.0%, adj=100%. 3 norm-only extras (anti-tl1a-xpf005-arm, risankizumab variants) are correct new normalized additions.

**Phase 4C task for TED:** ✅ **VERIFIED (Session 53n)** — compare_pass (100% raw, no OOS needed).

| Metric | Result |
|---|---|
| Legacy (igf1r area) | 9 drugs |
| Normalized (ted ind) | 14 drugs |
| Overlap | 9 drugs (100%) |
| Extra-legacy | 0 — no legacy igf1r drugs missing from normalized ✅ |
| Extra-norm | 5 — new normalized additions beyond legacy footprint |
| Raw match | **100.0%** |
| Status | **compare_pass ✅** |

**Extra-norm drugs (ted ind, not in igf1r area) — all classified:**

| Drug | Target | Stage | Review | Classification |
|---|---|---|---|---|
| crn12755 | SST2 | Preclinical | auto_confirmed | ✅ new_normalized_value — valid SST2 TED drug |
| lonigutamab | TSHR | Preclinical | auto_confirmed | ✅ new_normalized_value — TSHR mAb |
| sp-1351 | TSHR | Preclinical | auto_confirmed | ✅ new_normalized_value — TSHR small molecule |
| iscalimab | CD40 | Phase 2 | sampling_queue | ✅ new_normalized_value — CD40 in TED, Phase 2 trial data |
| cizutamig | BCMA×CD3 | Phase 1 | sampling_queue | ⚠️ **needs_validation** — pattern_match source; BCMA×CD3 TED biology unusual; validate before Phase 5 |

**cizutamig flag:** drug_indications/ted row has source_type=pattern_match, review_status=sampling_queue, conf=87. Not in drug_areas/igf1r (areas: tcell, autoimmune). The TED indication claim should be confirmed via trial evidence before Phase 5 migration includes it. No action needed now — sampling_queue is the correct holding state.

**Phase 4C task for Drug modal:** ✅ **PARTIALLY VERIFIED (Session 53m)** — 3 test drugs passed (lm-302, batoclimab, epi-001). All differences explainable via entity_consistency_checks. Remaining task: run full 10-drug sprint covering additional area tabs (TL1A, FcRn, TED drugs).

**Phase 5 feature-flag pattern (required for all migrations):**
```javascript
const USE_NORMALIZED_IBD = false; // flip to true for Phase 5 migration
```
Legacy read path stays active as commented fallback for 30 days post-migration.

---

## Next Sprint Priority Order

### P0 — entity_consistency_checks: COMPLETE ✅

**Executed:** 2026-05-25 — advisor approval granted by Kyle on 2026-05-25.  
**Migration:** `migrations/entity_consistency_checks_v1.sql` — executed via Supabase Management API.  
**Apply script:** `scripts/apply_entity_consistency_checks.py`

**Verified state:**

| Status | Count | Entities |
|---|---|---|
| closed | 3 | lm-302, sim0500, spy072 — resolved in Phase 4A, no data action needed |
| corrected | 2 | batoclimab — ted+gmg committed; **gb004 — mechanism patched (Session 53n)** |
| open | 2 | epi-001 (held), upadacitinib (queued Wave 2D) |

**Phase 5 gate: Open high-severity = 0 ✅**

**Held items — do not act without further input:**
- `epi-001 / ibd_indication_evidence_gap` — held pending source evidence for IBD indication. confidence=0.55. Do NOT commit.

**Action queue (open + accepted):**
- `upadacitinib / atopy_ad_gap` — queue for Wave 2D atopy backfill alongside imvt-1402. confidence=0.97.

**Architecture rule (standing):**
Automated scanners (`drug_validation_results`, `conflict_detector.py`, `company_validator.py`) continue writing to their own logs. A finding graduates to `entity_consistency_checks` only when a human or harness review has classified it and a proposed action exists. This is the durable human reconciliation layer — not a scan log.

**Phase 5 migration is blocked until Phase 4C classification sprint complete + ontology_edges advisor unlock.**

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

### P5 — entity_consistency_checks Table: COMPLETE ✅
Built and seeded 2026-05-25. See P0 section above for full state. Trigger condition (Phase 4B complete) was satisfied before execution.

---

## 5-Track Workstream Status

| Track | Focus | Status |
|---|---|---|
| A — Relationship Layer | Wave 2D FcRn + autoimmune (epi-001 first) | ⏸ epi-001 pending review |
| B — Ontology Quality | Phase 4C validation sprint → true missing rows | ▶ NEXT (with D) |
| C — Intelligence Products | Portfolio intelligence product | Queued — begin after Phase 4C |
| D — Dashboard Architecture | Phase 4C pre-migration classification | ▶ NEXT |
| E — Data Acquisition | Normalization engine → platform library | Documented; deferred |

---

## Active Constraints

1. **ontology_edges locked** — 25 rows. Do NOT unlock until advisor explicitly approves.
2. **No Phase 5 dashboard migration** — Phase 4C classification sprint must complete first. Migrate per-component with feature flags, never broad rewiring.
3. **epi-001 held** — 2 rows in backfill_preview as pending_review. Do NOT commit without source evidence.
4. **batoclimab → cidp** — NOT committed. Deferred to Wave 2D FcRn backfill batch.
5. **compare_pass ≠ migration-ready** — tl1a/ibd/ted cleared Phase 4 compare threshold. Phase 4C classification + feature-flag design is the Phase 5 gate.
6. **TL1A Phase 5 requires arch review** — `tl1aPI` is a separate ~1700-line object, not `_makeAreaPI`. Map its read path before any Phase 5 migration attempt on TL1A tab.

---

## Validation Checks Before Starting Work

```sql
SELECT count(*) FROM drug_indications;             -- expect 194
SELECT count(*) FROM trial_indications;            -- expect 301
SELECT count(*) FROM drug_targets;                 -- expect 168
SELECT count(*) FROM ontology_edges;               -- expect 25 (LOCKED)
-- entity_consistency_checks state:
SELECT entity_id, issue_key, status, review_status FROM entity_consistency_checks ORDER BY entity_id;
-- expect 7 rows; open high-severity = 0
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

1. `docs/phase5_migration_plan.md` — **Phase 5 controlled migration plan (read first)**
2. `docs/unified_area_dashboard_architecture.md` — unified engine design (TL1A unification path)
3. `docs/phase4c_validation_plan.md` — Phase 4C component ranking + validation criteria
4. `docs/phase4_comparison_harness.md` — current harness output (tl1a 🟢 · ibd 🟢 · ted ✅)
5. `docs/phase4a_reconciliation_review.md` — Phase 4A candidate review with advisor decisions
6. `docs/evidence_reconciliation_layer.md` — entity_consistency_checks design
7. `docs/dashboard_dependency_inventory.md` — component migration dependency map
8. `scripts/phase4_compare_legacy_vs_normalized.py` — harness script (v3)
9. `MEMORY.md` → `project_parallel_workstreams.md`, `project_meridian_maturity.md`, `project_tl1a_unification.md`
