# Phase 5 — C5/C6 Activation Package & Reconciliation Report

**Prepared:** 2026-05-25 (Session 55)  
**Status:** Pre-activation. No code changes made.

---

## Track A — Reconciliation Batch Status

Both fixes were already applied in a prior operation. No new inserts or updates required.

### Fix 1 — apg333 → tslp (drug_targets)

| Field | Value |
|---|---|
| drug_id | apg333 |
| target_id | tslp |
| confidence_score | 95 |
| review_status | reviewed_accepted |
| Status | **PRESENT ✅ — already in drug_targets** |

**Validation:** 
- No duplicate (drug_id, target_id) pair — exactly one row, confirmed.
- drug_id `apg333` confirmed in `drugs` table (name=APG333, mechanism=Anti-TSLP IgG).
- target_id `tslp` confirmed in `targets` table.
- TSLP adjusted match: 8/(14−6) = **100%** ✅ (was 7/8 = 87.5% without this row).

### Fix 2 — riliprubart.drugs.target

| Field | Before | After |
|---|---|---|
| drugs.target | C1q complement (stale) | **FcRn** ✅ |
| drug_targets | fcrn: conf=95, reviewed_accepted | unchanged ✅ |

**Validation:**
- `drugs.target = 'FcRn'` confirmed.
- `drug_targets` row for riliprubart/fcrn unchanged (confidence=95, reviewed_accepted).
- No unrelated rows changed.

---

## Track B — C5 / C6 / C7 Readiness

### C5 — TSLP

| Metric | Value |
|---|---|
| Legacy (`drug_areas area_id='tslp'`) | 14 |
| Normalized (`drug_targets target_id IN ('tslp','tslpr')`) | 10 |
| Overlap | 8 |
| Extra-legacy | 6 |
| Extra-norm | 2 |
| OOS classified (scope_difference) | 6 |
| Adjusted match | 8 / (14−6) = **100%** |
| Verdict | **✅ READY** |

**Extra-legacy (6) — all `scope_difference`:**
astegolimab (IL-33), benralizumab (IL-5Rα), dupilumab (IL-4Rα), itepekimab (IL-33), mepolizumab (IL-5), tozorakimab (IL-33R/ST2) — pathway partners, not TSLP-targeting

**Extra-norm (2) — both `legitimate_target_drug`:**
- catalog-53 (TSLP, Phase 1, Newsoara) — new normalized addition, correct
- ibi333 (IL-4Rα×TSLP bispecific, Phase 3) — appears in both TSLP and IL-4Rα normalized; correct bispecific coverage

**Architecture note:** Query must use `target_id IN ('tslp','tslpr')` to capture verekitug--upb-101, which targets the TSLP receptor (TSLPR), not the ligand. This is established from Phase 4C.

---

### C6 — IL-4Rα

| Metric | Value |
|---|---|
| Legacy (`drug_areas area_id='il4ra'`) | 9 |
| Normalized (`drug_targets target_id='il4ra'`) | 5 |
| Overlap | 4 |
| Extra-legacy | 5 |
| Extra-norm | 1 |
| OOS classified (scope_difference) | 5 |
| Adjusted match | 4 / (9−5) = **100%** |
| Verdict | **✅ READY** |

**Extra-legacy (5) — all `scope_difference` (atopy pathway partners, not IL-4Rα-targeting):**

| drug_id | name | actual_target | stage | classification |
|---|---|---|---|---|
| amlitelimab | amlitelimab | OX40L | Phase 3 | scope_difference — OX40L mAb, not IL-4Rα |
| lebrikizumab | lebrikizumab | IL-13 | Phase 3 | scope_difference — IL-13 mAb |
| nemolizumab | nemolizumab | IL-31Rα | Approved | scope_difference — IL-31Rα mAb |
| tralokinumab | tralokinumab | IL-13 | Phase 3 | scope_difference — IL-13 mAb |
| zumilokibart | zumilokibart | IL-13 | Phase 2 | scope_difference — IL-13 mAb |

**Extra-norm (1) — `legitimate_target_drug`:**

| drug_id | name | detail | classification |
|---|---|---|---|
| ibi333 | IBI333 | IL-4Rα×TSLP bispecific, Phase 3 (Sanofi), AD+asthma | legitimate_target_drug — drug_targets has both il4ra and tslp rows (conf=95, auto_confirmed) |

**Post-migration count:** 4 overlap + 1 extra-norm = **5 drugs** in IL-4Rα normalized tab.

---

### C7 — FcRn

| Metric | Value |
|---|---|
| Legacy (`drug_areas area_id='fcrn'`) | 6 |
| Normalized (`drug_targets target_id='fcrn'`) | 7 |
| Overlap | 6 |
| Extra-legacy | 0 |
| Extra-norm | 1 |
| Raw match | 6/6 = **100%** |
| Adjusted match | **100%** |
| Verdict | **✅ READY** |

**Extra-legacy (0):** All 6 legacy FcRn drugs confirmed in normalized. ✅  

**Extra-norm (1):** riliprubart (Sanofi SAR443765) — Phase 3 FcRn mAb confirmed by drug_targets review_notes and drugs.target field (now corrected from "C1q complement" → "FcRn").

---

### Summary

| Candidate | Legacy | Norm | Overlap | Adj match | Verdict |
|---|---|---|---|---|---|
| C5 TSLP | 14 | 10 | 8 | **100%** | ✅ **READY** |
| C6 IL-4Rα | 9 | 5 | 4 | **100%** | ✅ **READY** |
| C7 FcRn | 6 | 7 | 6 | **100%** | ✅ **READY** |

---

## Track C — C6 (IL-4Rα) Activation Package

### Architecture Decision: Bundle C5 + C6

**Critical finding:** The `TAB_AREA_MAP` has two tabs using `il4ra`:

```javascript
'il4ra-tslp': ['il4ra','tslp'],    // combined atopy tab
'il4ra-ox40l': ['il4ra'],          // pure IL-4Rα tab
```

The `il4ra-tslp` tab queries `drug_areas WHERE area_id IN ('il4ra','tslp')`. If only C6 activates (il4ra migrates but tslp stays in drug_areas), the `il4ra-tslp` tab would need a mixed-source query. This is architecturally messy.

**Recommendation: Activate C5 (TSLP) and C6 (IL-4Rα) together as a single sprint.** Both are READY. The combined normalized query for `il4ra-tslp` tab becomes `drug_targets WHERE target_id IN ('il4ra','tslp','tslpr')`. Clean, no mixed sources.

`il4ra-ox40l` tab (areaIds=['il4ra']) handles gracefully with just `drug_targets WHERE target_id='il4ra'`.

---

### Proposed Feature Flag

```javascript
const FEATURE_FLAGS = {
  useNormalizedIBD:       true,   // C1: ACTIVATED
  useNormalizedTED:       true,   // C2: ACTIVATED
  useNormalizedDrugModal: true,   // C3: ACTIVATED
  useUnifiedTL1A:         true,   // C4: ACTIVATED
  useUnifiedAtopy:        false,  // C5+C6: TSLP + IL-4Rα combined (do not enable yet)
};
```

Flag name: `useUnifiedAtopy` — covers both TSLP and IL-4Rα together since they share the `il4ra-tslp` tab.

Alternative: Two separate flags `useNormalizedIL4RA` + `useNormalizedTSLP` — allows granular control but requires mixed-source handling in `_makeAreaPI` for the combined tab.

**Recommendation: `useUnifiedAtopy` (single flag for the atopy axis).** Rationale: both are READY, they share a tab, and bundling reduces migration complexity.

---

### Source Queries

**Legacy (flag=false):**
```javascript
_sb.from('drug_areas').select('drugs(id,name,...)')
   .in('area_id', this.areaIds)
// il4ra-tslp: area_id IN ('il4ra','tslp')   → 14+9 unique drugs (some overlap possible)
// il4ra-ox40l: area_id IN ('il4ra')          → 9 drugs
```

**Normalized (flag=true):**
```javascript
// New instance flag (computed at init):
const _ATOPY_NORM = !!(FEATURE_FLAGS.useUnifiedAtopy && 
                       (this.areaIds.includes('il4ra') || this.areaIds.includes('tslp')));
this._atopyNorm = _ATOPY_NORM;

// In parallel fetch:
_ATOPY_NORM
  ? _sb.from('drug_targets').select('drug_id').in('target_id', ['il4ra','tslp','tslpr'])
  : ...existing chain...

// il4ra-tslp: drug_targets WHERE target_id IN ('il4ra','tslp','tslpr')  → ~14 drugs
// il4ra-ox40l: drug_targets WHERE target_id IN ('il4ra','tslp','tslpr') filtered by this.areaIds 
//   → actually for ox40l tab areaIds=['il4ra'], so target_id='il4ra' only → 5 drugs
```

**Note for il4ra-ox40l:** When `areaIds=['il4ra']` only (no 'tslp'), the query should restrict to `target_id='il4ra'` only, not include tslp/tslpr. The ternary should check `this.areaIds.includes('il4ra')` separately.

**Refined query logic:**
```javascript
const _il4ra = this.areaIds.includes('il4ra');
const _tslp  = this.areaIds.includes('tslp');
const _ATOPY_NORM = !!(FEATURE_FLAGS.useUnifiedAtopy && (_il4ra || _tslp));
const _atopyTargets = [
  ...(_il4ra ? ['il4ra'] : []),
  ...(_tslp  ? ['tslp','tslpr'] : [])
];
// Query: drug_targets WHERE target_id IN (_atopyTargets)
```

---

### Expected Count Changes

| Tab | Legacy count | Normalized count | Change |
|---|---|---|---|
| il4ra-ox40l | 9 | 5 | −4 (5 scope_diff excluded: OX40L×1, IL-13×3, IL-31Rα×1) |
| il4ra-tslp | ~19 (il4ra∪tslp unique) | ~14 (il4ra∪tslp∪tslpr unique) | net −5, +2 new |

**il4ra-tslp normalized breakdown:**
- IL-4Rα drugs: apg279, apg777, dupilumab, ibi333, rademikibart--cbp-201 (5)
- TSLP/TSLPR drugs: apg333, bsi-045b, catalog-53, gb0895, ibi333, qx031n, tezepelumab, verekitug--upb-101, win027, win378 (10, incl. ibi333 which overlaps)
- Union: ~14 unique drugs

---

### Code Touchpoints

| Location | Line | Change Required |
|---|---|---|
| `FEATURE_FLAGS` block | ~2044 | Add `useUnifiedAtopy: false` |
| `_makeAreaPI().init()` parallel fetch | ~12499 | Add `_ATOPY_NORM` ternary branch BEFORE `_IBD_NORM` check |
| `_makeAreaPI().init()` instance flags | ~12493 | Add `this._atopyNorm = _ATOPY_NORM` |
| `_makeAreaPI()._loadEntityMeta()` | ~12673 | Add `this._atopyNorm` ternary branch BEFORE `this._ibdNorm` check |
| `_makeAreaPI()._runPhase4BDualRead()` | ~12619 | May need atopy dual-read variant (or reuse existing structure) |

**Priority rule (must check in this order, same as TL1A fix):**
```
_ATOPY_NORM → _TL1A_NORM → _IBD_NORM → _TED_NORM → drug_areas fallback
```
Prevents the same precedence bug that was caught during C4 validation.

---

### Phase 4B Dual-Read

A new dual-read path (`_runPhase4BAtopyDualRead`) should fire for the atopy tabs, comparing:
- `il4ra_target_view`: `drug_areas(il4ra)` vs `drug_targets(il4ra)`
- `tslp_target_view`: `drug_areas(tslp)` vs `drug_targets(tslp,tslpr)`

Expected status for both: `compare_pass_oos_adjusted`.

---

### 8-Gate Validation Checklist (C5+C6)

| Gate | Check |
|---|---|
| G1 | flag=false → legacy path fires; `drug_areas` is source; il4ra-ox40l count≈9 |
| G2 | flag=true → normalized path fires; `drug_targets` is source; il4ra-ox40l count≈5 |
| G3 | Real IL-4Rα drugs present: dupilumab, rademikibart--cbp-201, apg279, apg777, ibi333 |
| G4 | Scope-diff drugs absent: amlitelimab, lebrikizumab, nemolizumab, tralokinumab, zumilokibart |
| G5 | TSLP tab: tezepelumab, apg333, bsi-045b, verekitug--upb-101, gb0895 present |
| G6 | Zero console errors |
| G7 | Phase 4B dual-read: il4ra_target_view + tslp_target_view both = compare_pass_oos_adjusted |
| G8 | flag=false rollback restores legacy counts (il4ra-ox40l≈9, tslp≈14) |

---

### Rollback Path

Set `FEATURE_FLAGS.useUnifiedAtopy = false`. No data changes required — `drug_areas` table is untouched. Same pattern as all prior activations.

---

## Track D — drug_areas Governance Inventory

**Source data:** 208 rows total, 11 distinct area_ids.

| area_id | Count | Classification | Rationale |
|---|---|---|---|
| `tl1a` | 50 | **ontology_derived** | Phase 5 C4 ACTIVATED (useUnifiedTL1A=true). Fully replaced by drug_targets(tl1a). |
| `ibd` | 48 | **ontology_derived** | Phase 5 C1 ACTIVATED (useNormalizedIBD=true). Fully replaced by drug_indications(uc,cd). |
| `il4ra` | 9 | **ontology_derived** | Phase 5 C6 — next activation. drug_targets(il4ra) equivalent exists (5 drugs, 100% adj match). |
| `tslp` | 14 | **ontology_derived** | Phase 5 C5 — bundled with C6. drug_targets(tslp,tslpr) equivalent exists (10 drugs, 100% adj match). |
| `fcrn` | 6 | **ontology_derived** | Phase 5 C7 — after atopy. drug_targets(fcrn) equivalent exists (7 drugs, 100% raw match). |
| `igf1r` | 9 | **ontology_derived** | Phase 5 C2 ACTIVATED (useNormalizedTED=true). TED tab already reads drug_indications(ted). `igf1r` area is the legacy equivalent. |
| `ted` | 12 | **ontology_derived** | Fully superseded by igf1r area + C2 activation. `ted` area appears to be a legacy data artifact — 12 drugs overlap almost entirely with igf1r area. Not referenced in TAB_AREA_MAP. |
| `respiratory` | 14 | **ontology_derived** | Identical population to `tslp` area (same 14 drugs). Appears to be a legacy alias. Superseded by C5 when it activates. Not referenced in TAB_AREA_MAP. |
| `atopy` | 10 | **ontology_derived** | Almost identical to `il4ra` area plus upadacitinib (JAK1). Will be superseded by C6. Not referenced in TAB_AREA_MAP as a standalone tab. |
| `autoimmune` | 25 | **curated_competitive_view** | Broad FcRn/B-cell/CAR-T competitive context (batoclimab, efgartigimod, CAR-T programs, CD20 mAbs, etc.). No single normalized equivalent — spans multiple target types. Worth preserving as a curated competitive landscape view until a formal "autoimmune" ontology concept is defined. |
| `tcell` | 11 | **legacy_artifact** | CAR-T / TCR / T-cell therapies. ACE tab driver. No drug_targets equivalent (explicitly deferred — Phase 4C Rank 8). Dashboard audit tab classifies tcell as "Platform / Modality" concept, not a therapeutic area. Survives as intentional platform view until ACE tab strategy is decided. |

---

### Observations

**7 of 11 area_ids are ontology_derived** — they either have activated normalized equivalents (tl1a, ibd, igf1r) or will activate soon (il4ra, tslp, fcrn). Their survival in drug_areas is a legacy retention artifact governed by the 30-day rule.

**3 area_ids are redundant aliases** — `ted`, `respiratory`, `atopy` appear to be historical curation artifacts with populations identical or near-identical to their counterpart areas. None are referenced in TAB_AREA_MAP.

**1 area_id (`autoimmune`) is a genuine curated view** — 25 drugs spanning FcRn, CD19/20, complement, and T-cell depletion modalities. Useful as competitive context. No ontology equivalent yet. Should survive.

**1 area_id (`tcell`) is an intentional platform view** — ACE tab, classified by the platform audit as "Platform / Modality." Stays until an ACE strategy decision is made.

---

### Post-C7 State (projected)

After all planned activations (C4 done, C5+C6+C7 pending):

| area_id | Survival | Reason |
|---|---|---|
| tl1a | Retire after 2026-06-24 | 30-day retention period expires |
| ibd | Retire after 2026-06-24 | 30-day retention period expires |
| il4ra | Retire after C6 monitoring window | Will be set post-activation |
| tslp | Retire after C5 monitoring window | Will be set post-activation |
| fcrn | Retire after C7 monitoring window | Will be set post-activation |
| igf1r | Retire after C2 monitoring window (~2026-06-08) | Already activated |
| ted | Retire (deferred cleanup) | Legacy alias, no active tab dependency |
| respiratory | Retire (deferred cleanup) | Legacy alias, identical to tslp |
| atopy | Retire (deferred cleanup) | Legacy alias, near-identical to il4ra |
| autoimmune | **Retain** | Curated competitive view — intentional |
| tcell | **Retain** | Platform/modality view — intentional until ACE strategy decided |

**Next question after C7:** Should `autoimmune` be formalized as a named concept in `disease_areas`/`indications` with proper ontology edges? Or remain as a curation bucket? This is the "should this area continue to exist as a concept" question.
