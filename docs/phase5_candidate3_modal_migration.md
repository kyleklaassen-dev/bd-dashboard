# Phase 5 Candidate 3 — Drug Modal Normalized Source Migration

**Status:** ✅ PERMANENTLY ACTIVATED 2026-05-25  
**Commit:** `cc1e0d6e5c24`  
**Flag:** `FEATURE_FLAGS.useNormalizedDrugModal = true`

---

## What Was Built

The drug entity modal (`openDrugEntityModal`) now reads from normalized ontology tables when `useNormalizedDrugModal=true`. Two new sections appear in the Overview tab of any drug with a real database ID:

- **🎯 Targets (Normalized)** — from `drug_targets` table: target_id, confidence_score, review_status. Collapsible detail table included.
- **🩺 Indications (Normalized)** — from `drug_indications` table: indication_id, confidence_score, development_stage, review_status. Collapsible detail table included.
- **Trial indication pills** — green pills on trial rows, sourced from `trial_indications` via trial IDs (fetched in parallel with targets/indications).

Both sections are **conditionally rendered** — they only appear if the respective normalized table has rows for that drug. If `drug_targets` has 0 rows for a drug, the Targets section is suppressed entirely.

---

## Code Changes

### `_cemDrugBody()` — signature extension (line ~10362)

```javascript
function _cemDrugBody(drug, areas, trials, molData, companyName, drugDeals, normData) {
```

`normData` is `{ targets: [...], indications: [...], trialInds: [...] }` or `null`.

### Label maps (added after `_CEM_AMAP`)

```javascript
const _IND_LABEL = {
  uc:'Ulcerative Colitis', cd:"Crohn's Disease", ted:'Thyroid Eye Disease',
  ad:'Atopic Dermatitis', asthma:'Asthma', copd:'COPD', crswnp:'CRSwNP',
  ra:'Rheumatoid Arthritis', sle:'Lupus (SLE)', gmg:'Generalized MG',
  cidp:'CIDP', igg4rd:'IgG4-RD', mg:'Myasthenia Gravis', hs:'Hidradenitis Suppurativa',
  eoe:'EoE', chronic_urticaria:'Chronic Urticaria', psc:'PSC',
  iga_nephropathy:'IgAN', eoe_adult:'EoE', eos_esophagitis:'EoE',
};
const _TARGET_LABEL = {
  tl1a:'TL1A', tslp:'TSLP', il4ra:'IL-4Rα', fcrn:'FcRn',
  igf1r:'IGF1R', tshr:'TSHR', bcma:'BCMA', cd19:'CD19', cd3:'CD3',
  il13:'IL-13', il5:'IL-5', il33:'IL-33', ox40l:'OX40L', ox40:'OX40',
  il23p19:'IL-23p19', il12p40:'IL-12/23p40', il23:'IL-23',
};
```

### `openDrugEntityModal()` — normData fetch block

When `useNormalizedDrugModal=true` and drug has a non-static ID:
1. Parallel fetch `drug_targets` + `drug_indications` for `drug_id`
2. If trials exist: fetch `trial_indications` for up to 30 trial IDs
3. Build `normData = { targets, indications, trialInds }`
4. On any error: log warning, `normData` stays `null` (non-blocking fallback)

---

## Pre-Activation Cleanup Applied

Three cleanup commits before activation:

| Commit | Fix |
|---|---|
| `4b26b6f0` | Confidence score display: `Math.round(score)` not `Math.round(score*100)`. Was showing `9500%` for a 95 score stored as 0–100. |
| `0f99b191` | Same fix applied to all four display locations (targets summary, targets detail, indications summary, indications detail). |
| `e4d7b9e32968` | Label fixes: `eoe`→EoE, `chronic_urticaria`→Chronic Urticaria, `il23p19`→IL-23p19, `il12p40`→IL-12/23p40, `il23`→IL-23. |

---

## CIDP Source Decision

`batoclimab → cidp` was investigated before activation.

- **Row ID:** `bf05a59c-5671-4f1b-9e8b-f30c76e138ab`
- **confidence_score:** 92
- **review_status:** `auto_confirmed`
- **reviewed_by:** `kyle-2026-05-25`
- **review_notes:** "Phase 2 trials: NCT07188, NCT05581 — CIDP. Wave 2D commit, trial evidence, conf=0.97. Approved Kyle 2026-05-25."

Decision: **keep**. Explicit trial evidence, high confidence, advisor-approved in Wave 2D.

---

## Validation Results

All 8 pre-activation gates passed:

| Gate | Result |
|---|---|
| flag=false regression | ✅ Modal renders, no normalized sections injected |
| flag=true rendering | ✅ Both Targets + Indications sections present |
| batoclimab | ✅ FcRn 95% / TED 95% / gMG 92% / CIDP 92% |
| dupilumab | ✅ IL-4Rα 96% / Asthma+AD+EoE+Chronic Urticaria+COPD 87% |
| risankizumab | ✅ IL-23p19 95% / CD+UC 89% |
| sim0709 | ✅ TL1A+IL-23p19 95% / UC+CD 93% (phase1) |
| epi-001 | ✅ TL1A 95%, no indications section (empty table — correct) |
| Console errors | ✅ 0 |
| Phase4C compare records | ✅ 6 records in `window.__MERIDIAN_PHASE4_COMPARE__` |
| Rollback | ✅ flag=false removes both sections cleanly |

---

## Production Verification

Confirmed live on production (commit `cc1e0d6e`, `?nocache=cc1e0d6e`):

- `FEATURE_FLAGS.useNormalizedDrugModal: true` ✅
- `useNormalizedIBD: true` ✅ (Candidate 1 still stable)
- `useNormalizedTED: true` ✅ (Candidate 2 still stable)
- batoclimab modal: FcRn(95%) / TED(95%) / gMG(92%) / CIDP(92%) ✅
- 0 console errors ✅

---

## Monitoring Window

**Open to:** ~2026-06-08  
**Legacy code retention deadline:** 2026-06-24  
**Rollback:** set `useNormalizedDrugModal: false` in FEATURE_FLAGS

New modal inconsistencies should be recorded in `entity_consistency_checks` rather than triggering immediate reverts, unless the issue materially changes displayed scientific content.

---

## Non-Blocking Cleanup (Standing)

`batoclimab` ted + gmg rows carry `review_status: review_required` from session #167. These rows were approved in that session's backfill but the status field was not updated at commit time. Does not affect modal rendering. Update to `confirmed` in a future data quality pass.

---

## Candidate 4 — TL1A (Not Started)

TL1A uses `tl1aPI` (~1700-line separate object), not `_makeAreaPI`. Architecture review required before any Phase 5 migration attempt. See `docs/unified_area_dashboard_architecture.md` and memory `project_tl1a_unification.md`.
