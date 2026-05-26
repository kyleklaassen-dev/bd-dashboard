# NEXT SESSION — BD Platform

**Last session:** Session 53r (2026-05-25) — Phase 5 Candidate 3 PERMANENTLY ACTIVATED (useNormalizedDrugModal=true, commit cc1e0d6e). Drug modal now reads from normalized tables. Third completed Phase 5 migration.  
**Prior session:** Session 53q — Candidate 2 (TED) permanently activated (useNormalizedTED=true, commit 71974d6)

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

## Phase Sequence (updated Session 53o)

| Phase | Name | Status |
|---|---|---|
| Phase 4A | Evidence Reconciliation — candidate review + corrections | ✅ COMPLETE |
| Phase 4B | Dual-read validation — parallel legacy + normalized reads | ✅ COMPLETE |
| Phase 4C | Pre-migration classification sprint — explain every difference | ✅ COMPLETE — IBD ✅ TED ✅ modal 10/10 ✅ Ranks 5–8 ✅ |
| Phase 5 | Incremental source switch — feature-flagged, per-component | ▶ **ACTIVE — Candidates 1+2 ACTIVATED 2026-05-25** |

**Phase 5 Candidate 1 (IBD): ACTIVATED 2026-05-25. `ibd_indication_group_view=compare_pass_oos_adjusted` (legacy=49, norm=49, adj=95.9%). Monitoring window → ~2026-06-08. Legacy retention deadline: 2026-06-24.**

**Phase 5 Candidate 2 (TED): ACTIVATED 2026-05-25 (commit 71974d6). `ted_indication_group_view=compare_pass_oos_adjusted` (legacy=9, norm=13, raw=100%, adj=100%). 4 genuine new TED additions in normalized. 1 data error fixed (cizutamig false positive removed). Monitoring window → ~2026-06-08. Legacy retention deadline: 2026-06-24. Candidate 3 (Drug modal) is next.**

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
| 5 | TSLP area tab | Medium | ✅ compare_pass_oos_adjusted (42.9% raw, 100% adj) | ⏸ After modal sprint |
| 6 | IL-4Rα area tabs | Medium | ✅ compare_pass_oos_adjusted (44.4% raw, 100% adj) | ⏸ After modal sprint |
| 7 | FcRn area tab | High | ✅ compare_pass_oos_adjusted (85.7% raw, 100% adj) | ⏸ After modal sprint |
| 8 | ACE area tab | High | ❌ DEFERRED permanently — no normalized equivalent | 🚫 Deferred |

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

**Phase 4C task for Drug modal:** ✅ **COMPLETE (Session 53o)** — All 10 drugs verified. 0 unexplained mismatches. 0 IBD blockers. Full report: `docs/phase4c_modal_sprint.md`.

| Drug | Status | IBD block |
|---|---|---|
| sim0709 | compare_pass_oos_adjusted | ❌ |
| batoclimab | acceptable_mismatch (igf1r catch-all, ECC corrected) | ❌ |
| lm-302 | needs_manual_review → ECC accepted | ❌ |
| spy072 | compare_pass_oos_adjusted (OOS classified) | ❌ |
| epi-001 | acceptable_mismatch (ECC held — gate satisfied) | ❌ |
| upadacitinib | compare_pass_oos_adjusted | ❌ |
| teprotumumab | match | ❌ |
| dupilumab | compare_pass_oos_adjusted (il4ra/tslp OOS) | ❌ |
| efgartigimod | match | ❌ |
| risankizumab | compare_pass_oos_adjusted | ❌ |

**Phase 4C Rank 5 — TSLP:** ✅ **compare_pass_oos_adjusted (Session 53o)**

| Metric | Result |
|---|---|
| Legacy (tslp area) | 14 drugs |
| Normalized (tslp ind) | 9 drugs |
| Raw match rate | 42.9% |
| OOS-adjusted match | **100%** |
| Legacy-only extras | 8 — all ontology_scope_difference (IL-33, IL-5Rα, IL-13, OX40L, IL-31RA pathway partners) |
| Norm-only extras | 3 — new_normalized_value additions |

⚠️ **TSLP Phase 5 migration note:** verekitug targets TSLP receptor (tslpr), not ligand. Phase 5 TSLP tab query MUST use `target_id IN ('tslp', 'tslpr')` to capture both.

**Phase 4C Rank 6 — IL-4Rα:** ✅ **compare_pass_oos_adjusted (Session 53o)**

| Metric | Result |
|---|---|
| Legacy (il4ra area) | 9 drugs |
| Normalized (ad + relevant inds) | 5+ drugs |
| Raw match rate | 44.4% |
| OOS-adjusted match | **100%** |
| Legacy-only extras | 5 — all ontology_scope_difference (IL-13, OX40L, IL-31RA, TSLP pathway partners) |

**Phase 4C Rank 7 — FcRn:** ✅ **compare_pass_oos_adjusted (Session 53o)**

| Metric | Result |
|---|---|
| Legacy (fcrn area) | 7 drugs |
| Normalized (gmg+cidp+ted inds) | 7 drugs |
| Raw match rate | 85.7% |
| OOS-adjusted match | **100%** |
| Legacy-only extras | 1 — atg-201 (legacy_noise: CD19×CD3 bispecific, not FcRn biology) |
| Norm-only extras | 1 — new_normalized_value addition |

**Phase 4C Rank 8 — ACE (tcell area):** 🚫 **DEFERRED permanently (Session 53o)** — tcell area has no normalized drug_indications or drug_targets equivalent. Not a valid comparison target. ACE/tcell excluded from Phase 5 migration planning.

---

## Phase 5 Status

| Candidate | Component | Flag | Value | Deployed | Activated |
|---|---|---|---|---|---|
| 1 | IBD area tab | `useNormalizedIBD` | **true** | ✅ commit `522e155` | ✅ **ACTIVATED 2026-05-25** — all 8 gates live; monitoring window open |
| 2 | TED area tab | `useNormalizedTED` | **true** | ✅ commit `71974d6` | ✅ **ACTIVATED 2026-05-25** — 8 gates live; ted_indication_group_view=compare_pass_oos_adjusted (9→13 drugs, raw=100%) |
| 3 | Drug modal | `useNormalizedDrugModal` | **true** | ✅ commit `cc1e0d6e` | ✅ **ACTIVATED 2026-05-25** — 8 gates live; labels clean; CIDP verified; 5-drug validation passed |
| 4 | TL1A tab | `useUnifiedTL1A` | false | ❌ implementation pending | ❌ pending unified rendering migration |

**Candidates 1+2+3 ACTIVATED 2026-05-25.** All three monitoring windows open to ~2026-06-08.

**⚡ FIRST TASK NEXT SESSION — Candidate 3 monitoring + Candidate 4 implementation:**
1. Confirm Candidates 1+2+3 still stable (open modals for batoclimab, dupilumab, sim0709)
2. Check console for errors — any unexpected normalized values → log to `entity_consistency_checks`, not reverts
3. Begin Candidate 4: implement TL1A as a `_makeAreaPI` target_view. Architecture is already decided — this is execution. Read `docs/unified_area_dashboard_architecture.md` for the approved config-driven design.
4. Shadow-render TL1A unified vs tl1aPI before flipping `useUnifiedTL1A=true`

**Candidate 3 — What was built:**
- `_cemDrugBody()` receives `normData` 7th param: `{ targets, indications, trialInds }`
- Two new conditional grid cells: 🎯 Targets (Normalized) + 🩺 Indications (Normalized)
- Trial indication pills on trial rows via `_trialIndMap` keyed by `trial_id`
- Label maps: `_IND_LABEL`, `_TARGET_LABEL` with 20+ entries each
- `openDrugEntityModal()` fetches `drug_targets` + `drug_indications` + `trial_indications` in parallel when flag=true
- Non-blocking: errors fall back to `normData=null`, no normalized cells shown
- Phase4C dual-read still fires unconditionally via `_runPhase4CModalDualRead()`

**Pre-activation checklist for permanent flip:**
- [x] 10-drug modal sprint complete (Session 53o)
- [x] No unexplained modal mismatches (0)
- [x] epi-001 formally held through Phase 5 (ECC open/held — gate satisfied)
- [x] IBD tab loads without console errors (activation test confirmed)
- [x] IBD count matches normalized output (49 legacy = 49 normalized)
- [x] lm-302/sim0500/spy072/epi-001 excluded from normalized set
- [x] Legacy fallback confirmed when flag=false
- [x] **TAB_AREA_MAP fixed** — 'ibd' now in TL1A areaIds; flag path enabled; dual-read can fire
- [ ] **IBD dual-read record directly observed in browser** ← ONLY REMAINING GATE

---

## Next Sprint Priority Order

### P0 — entity_consistency_checks: OPERATIONALLY CLEAN ✅

**Final state (Session 53o, 2026-05-25):**

| Status | Count | Entities |
|---|---|---|
| closed / accepted | 3 | lm-302, sim0500, spy072 — Phase 4A legacy noise, no data action needed |
| corrected / resolved | 5 | batoclimab (ted+gmg+cidp), gb004 (mechanism), upadacitinib (ad), atg-201 (fcrn area), nipocalimab (tcell area) |
| open / held | 2 | epi-001 (ibd evidence gap), cizutamig (ted pattern_match source) |

**Total rows: 10. Phase 5 gate: 0 open high-severity ✅**

**Held items — standing rule: do not act without source evidence:**
- `epi-001 / ibd_indication_evidence_gap` (id=4, medium) — confidence=0.55. No source evidence found. Do NOT commit until publication, trial registry, or company materials confirm IBD indication.
- `cizutamig / ted_indication_scope_review` (id=15, medium) — BCMA×CD3 TED indication sourced from pattern_match only. confidence=0.87. Validate before Phase 5 TED migration.

**Wave 2D committed totals (Sessions 53n–53o):**
- upadacitinib/ad · batoclimab/cidp · imvt-1402/gmg · imvt-1402/cidp
- drug_indications total: **200 rows**
- imvt-1402/waiha — NOT committed (no trial_indications evidence)

**ECC Governance Rules (approved Session 53o):**

A proposed cleanup may execute (`open/proposed → corrected/resolved`) only when one of:
1. **Direct source evidence** — company materials, trial registry, regulatory filing, or publication
2. **Cross-table contradiction, overwhelming confidence** — target assignment directly contradicts area assignment with no supporting evidence in any table
3. **Prior accepted pattern** — same error class already reviewed and approved

Future ECC records should be reserved for:
- Genuine contradictions requiring human judgment
- Advisor-reviewed reconciliation candidates with proposed action
- Source-backed correction proposals

Do NOT create ECC records for speculative enrichment opportunities — those belong in `backfill_preview` or `drug_validation_results`.

**Architecture rule (standing):**
Automated scanners (`drug_validation_results`, `conflict_detector.py`, `company_validator.py`) write to their own logs. A finding graduates to ECC only after human/harness review has classified it with a proposed action.

**Reference document:** `docs/phase4_reconciliation_summary.md` — full corrections log, before/after metrics, lessons learned.

### P1 — Phase 5 Candidate 4 (TL1A) — Data Source Migration

**Status:** Not started. `tl1aPI` was already retired (Session 45, commit `b4355353`). TL1A rendering already runs through `_makeAreaPI`. This is a source swap + validation sprint.

**Current source:** `drug_areas WHERE area_id='tl1a'`  
**Target source:** `drug_targets WHERE target_id='tl1a'`  
**Flag:** `FEATURE_FLAGS.useUnifiedTL1A`

**Step 1 — Pre-Flight Audit (before touching any code)**
- Legacy TL1A population count (`drug_areas WHERE area_id='tl1a'`)
- Normalized TL1A population count (`drug_targets WHERE target_id='tl1a'`)
- Overlap %, extra_legacy list, extra_normalized list
- Difference classification for every mismatch (legitimate_target_drug / legacy_noise / scope_difference / normalized_gap / source_conflict / manual_review)
- Adjusted match %
- **Deliverable: classification report. Nothing proceeds without it.**

**Step 2 — Reconciliation**
Every difference must be explainable before implementation starts. Unresolved mismatches → `entity_consistency_checks`.

**Step 3 — Implementation**
After audit clears: add normalized path inside `_makeAreaPI` behind `useUnifiedTL1A` flag. Source swap only — no rendering changes needed. Small code change.

**Step 4 — Validation**
Same 8-gate playbook as Candidates 1–3. Runtime observation wins over assumptions.

**Step 5 — Activation**
Flip flag permanently. Monitor to ~2026-06-08. Inconsistencies → `entity_consistency_checks`, not reverts.

**Why this moves fast:** Unified engine ✅ · Feature flag stub ✅ · Dual-read framework ✅ · Comparison harness ✅ · Reconciliation layer ✅. The framework is built. The work is proving the data source swap is correct.

### P2 — epi-001 Manual Review (Standing Hold)

- Drug: anti-TL1A antibody, preclinical stage. ECC id=4, confidence=0.55.
- Search for published source evidence confirming IBD indication (publication, trial registry, company pipeline disclosure)
- If IBD confirmed: commit uc + cd rows from backfill_preview (wave2c run)
- If no evidence: set review_status = 'no_evidence' and close ECC row
- **Do NOT commit without source evidence.**

### P3 — Wave 2D Remaining

- `imvt-1402 / waiha` — NOT committed. Revisit if trial_indications evidence emerges.
- All other Wave 2D items committed. Wave 2D is otherwise complete.

### P3 — Track B True Missing Rows
- `imvt-1402` → gmg, cidp, waiha: true_missing_row
- `ep006` → tombstone or merge into es302 (duplicate drug_id data integrity)

### P4 — Portfolio Intelligence Product (Track C)
Drug → Company joins now available. First intelligence product. Queued after Phase 5 Candidate 1 activation.
**Question:** "What is [company]'s full indication footprint across all areas we track?"

### P5 — entity_consistency_checks Table: COMPLETE ✅
Built and seeded 2026-05-25. Final state: 10 rows, operationally clean. See governance rules in P0 section above.

---

## 5-Track Workstream Status

| Track | Focus | Status |
|---|---|---|
| A — Relationship Layer | Wave 2D complete; imvt-1402/waiha held pending evidence | ✅ Wave 2D done; epi-001 held |
| B — Ontology Quality | Phase 4C complete; epi-001 + cizutamig held | ✅ Phase 4C done |
| C — Intelligence Products | Portfolio intelligence product | Queued after Phase 5 Candidate 1 activation |
| D — Dashboard Architecture | Phase 5 Candidate 1 — final gate (IBD dual-read manual confirm → permanent flip) | ▶ **PRIMARY FOCUS** |
| E — Data Acquisition | Normalization engine → platform library | Documented; deferred |

---

## Active Constraints

1. **ontology_edges locked** — 25 rows. Do NOT unlock until advisor explicitly approves.
2. **Phase 5 Candidates 1+2+3 — ALL ACTIVATED (flag=true)** — `useNormalizedIBD=true` (commit `522e155`), `useNormalizedTED=true` (commit `71974d6`), `useNormalizedDrugModal=true` (commit `cc1e0d6e`). All activated 2026-05-25. Monitoring windows open to ~2026-06-08. Legacy paths retained until 2026-06-24. New modal inconsistencies → `entity_consistency_checks`, not reverts.
3. **epi-001 held** — 2 rows in backfill_preview as pending_review. Do NOT commit without source evidence.
4. **batoclimab → cidp** — ✅ COMMITTED in Wave 2D (Session 53o). batoclimab drug_indications: ted(95), gmg(92), cidp(92).
5. **compare_pass ≠ migration-ready** — tl1a/ibd/ted cleared Phase 4 compare threshold. Phase 4C classification + feature-flag design is the Phase 5 gate.
6. **TL1A Candidate 4 is a data source migration, not a rendering debate** — `tl1aPI` was already retired in Session 45 (commit `b4355353`). TL1A already runs through `_makeAreaPI`. Candidate 4 swaps the query inside that engine from `drug_areas WHERE area_id='tl1a'` to `drug_targets WHERE target_id='tl1a'` via `useUnifiedTL1A` flag. Same 8-gate sprint pattern as Candidates 1–3.
7. **30-day rule** — When any flag is flipped to true, keep legacy code commented (not deleted) for 30 days.

---

## Validation Checks Before Starting Work

```sql
SELECT count(*) FROM drug_indications;             -- expect 198 (verified 2026-05-25)
SELECT count(*) FROM trial_indications;            -- expect 301 (verified 2026-05-25)
SELECT count(*) FROM drug_targets;                 -- expect 170 (verified 2026-05-25)
SELECT count(*) FROM ontology_edges;               -- expect 25 (LOCKED)
-- entity_consistency_checks state:
SELECT entity_id, issue_key, status, review_status FROM entity_consistency_checks ORDER BY entity_id;
-- expect 10 rows; open high-severity = 0
-- open/held (2):      epi-001 (ibd_indication_evidence_gap), cizutamig (ted_indication_scope_review)
-- corrected/resolved (5): batoclimab, gb004, upadacitinib, atg-201, nipocalimab
-- closed/accepted (3):    lm-302, sim0500, spy072
-- upadacitinib Wave 2D verified:
SELECT indication_id, confidence_score, development_stage FROM drug_indications WHERE drug_id = 'upadacitinib';
-- expect: ad (97, approved), cd (99), uc (99)
-- batoclimab Wave 2D verified:
SELECT indication_id, confidence_score FROM drug_indications WHERE drug_id = 'batoclimab';
-- expect: ted (95), gmg (92), cidp (92)
-- imvt-1402 Wave 2D verified:
SELECT indication_id, confidence_score FROM drug_indications WHERE drug_id = 'imvt-1402';
-- expect: gmg (94), cidp (91)
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
