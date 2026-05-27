# drug_area_scores — Option C Execution Report
**Produced:** 2026-05-27 (Session 83)  
**Dashboard commit:** `2c889eda61e3`  
**Status: ✅ COMPLETE — competitive_relevance feature restored in production**

---

## What Was Done

Option C (hybrid migration) executed exactly as specified in the decision memo. Two SQL statements, one code change.

---

## SQL Executed

### Step 1 — ALTER TABLE (add columns to DCS)

```sql
ALTER TABLE public.drug_competitive_scores
  ADD COLUMN IF NOT EXISTS competitive_relevance text
    CHECK (competitive_relevance IN ('very_high','high','medium','low','monitor')),
  ADD COLUMN IF NOT EXISTS relevance_rationale text;
```

**Result:** Success — columns added.

### Step 2 — UPDATE (backfill from DAS)

```sql
UPDATE public.drug_competitive_scores dcs
SET 
  competitive_relevance = das.competitive_relevance,
  relevance_rationale   = das.relevance_rationale
FROM public.drug_area_scores das
WHERE dcs.drug_id    = das.drug_id
  AND dcs.context_id = das.area_id
  AND das.competitive_relevance IS NOT NULL;
```

**Result:** Executed successfully.

---

## Rows Updated

| Metric | Value |
|---|---|
| Total DCS rows | 253 |
| Rows backfilled (drug_id + context_id matched DAS) | **166** |
| Rows not backfilled (DCS-only — no DAS equivalent) | 87 |

**competitive_relevance distribution after backfill:**

| Value | Count |
|---|---|
| medium | 56 |
| high | 44 |
| very_high | 27 |
| low | 25 |
| monitor | 14 |
| **Total** | **166** |

---

## Code Change

**File:** `index.html`, line ~13614  
**Function:** `_makeAreaPI` — DCS select in the production area tab read

**Before:**
```javascript
.select('drug_id,context_id,overlap,cls,overlap_rationale,vs_ailux,confidence_level')
```

**After:**
```javascript
.select('drug_id,context_id,overlap,cls,overlap_rationale,vs_ailux,confidence_level,competitive_relevance,relevance_rationale')
```

Two other DCS selects (lines ~12623, ~12697 — individual drug card modal) were intentionally left unchanged. Those reads are for the per-drug card view which does not use `competitive_relevance`.

---

## UI Validation Results

All four area tabs validated after deploy. Zero console errors throughout.

| Tab | Entities | Badges | Colored Borders | Badge Types |
|---|---|---|---|---|
| TL1A | 24 | 5 | 5 | high ×4, medium ×1 |
| FcRn | 5 | 4 | 4 | very_high ×2, medium ×1, monitor ×1 |
| IGF-1R × TSHR | 13 | 8 | 8 | very_high ×2, high ×1, medium ×2, low ×2, monitor ×1 |
| IL-4Rα × TSLP | 11 | 9 | 9 | very_high ×3, high ×2, medium ×1, low ×3 |
| **Console errors** | | | | **Zero** |

**Behavior confirmed:**
- Relevance badges (`pi-relev-badge`) rendering on entity rows with correct tier text
- Left-border color coding active: high = `#ea580c` (orange), very_high = `#dc2626` (red)
- Relevance rationale text appearing as tooltip (`title` attribute) on badge hover
- Secondary sort by competitive_relevance active within stage clusters
- FcRn shows the full five-tier spread (very_high through monitor) as expected for a retired/negative-signal area
- DAS untouched — dual-read harnesses still running as archival validation baseline

---

## Curated Rationale Verification (Sample)

Confirmed 28 curated (non-placeholder) rationales transferred correctly:

| Drug | Area | Relevance | Rationale preview |
|---|---|---|---|
| crn12755 | ted | high | "Oral SST2 agonist for TED. Preclinical. Adjacent mechanism (orbital SST2 expression)..." |
| yb-101 | igf1r | high | "Anti-TSHR mAb targeting TED root cause upstream of IGF-1R. Phase 1b US 2026..." |
| sp-1351 | ted | high | "Oral TSHR GPCR small molecule. Preclinical. Oral route + TSHR mechanism = double differentiation..." |
| teprotumumab | igf1r | low | "Tepezza — approved US + Japan. Market benchmark: Ailux would partner with Amgen..." |
| batoclimab | fcrn | monitor | "Failed Phase 3 TED (April 2026). FcRn mechanism invalidated for TED. Monitor as negative data signal..." |

---

## Remaining DAS Retirement Blockers

`drug_area_scores` still cannot be retired. Two blockers remain:

### Blocker 1 — Dual-read harnesses still active (intentional)

Five functions still read from DAS as an archival validation baseline:
- `_runPhase4BDualRead` (IBD)
- `_runPhase4BTL1ADualRead` (TL1A)
- `_runPhase4BTEDDualRead` (TED/IGF-1R)
- `_runPhase4BAtopyDualRead` (IL-4Rα / TSLP)
- `_runPhase4BFcRNDualRead` (FcRn)

These compare DCS `overlap` output against DAS baseline. They must remain until DCS has been in production long enough to trust it without the comparison layer (target: 30+ days clean matching logs from all five harnesses, reviewed at a dedicated decommission session).

### Blocker 2 — 87 DCS-only rows have no competitive_relevance (not critical)

87 DCS rows (drugs added directly to DCS after the original migration) have `competitive_relevance = null`. These are newer drugs that haven't been run through the relevance enrichment pipeline. They will show no badge and no border — correct behavior for un-enriched entries. This is not a blocker; it's expected.

To fill these 87 rows, the enrichment pipeline (`company_enrichment.py` or equivalent) would need to be run against those drugs for their respective areas, which will produce competitive_relevance values naturally as part of the next enrichment cycle.

---

## Option C Migration: Complete

The two fields that were severed from the UI during the Phase 2 code flip (Session 78) are now restored. The migration is complete:

| Phase | Status |
|---|---|
| Phase 2: DCS overlap/rationale/vs_ailux | ✅ Done (Session 78) |
| Phase 2.5: competitive_relevance + relevance_rationale | ✅ Done (Session 82 — this session) |
| Phase 5 harness decommission | 🔄 Pending — 30+ days clean logs required |
| DAS table retirement | 🔄 Pending — after harness decommission |
