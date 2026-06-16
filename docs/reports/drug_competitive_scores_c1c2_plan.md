# C1/C2 Drug Modal — Migration Plan
**drug_area_scores → drug_competitive_scores**
**Session 63 — 2026-05-26**

---

## Summary

C1 and C2 are the drug modal primary fetch and name-search fallback respectively. Both are classified as `safe_display_consumer` — no filtering, sorting, or behavioral logic depends on the scores. They are the recommended first migration target.

This document covers the five required pre-implementation deliverables before any code is written.

---

## 1. P0 — strategic_role Audit Result

**VERDICT: SAFE — omit entirely from drug_competitive_scores query.**

### Evidence

`strategic_role` is referenced in three display templates inside `_cemDrugBody` (index.html lines 10496, 10713, 12014) and in one filter expression (line 12000). All four usages are conditional:

```javascript
// Line 10496 — display (never renders)
${a.strategic_role ? `<div class="...">...</div>` : ''}

// Line 10713 — similar conditional block
${a.strategic_role ? `...` : ''}

// Line 12000 — filter
areas.filter(a => a.overlap || a.overlap_rationale || a.strategic_role)

// Line 12014 — display
${a.strategic_role ? `...` : ''}
```

`strategic_role` does NOT exist in `drug_area_scores`. Confirmed by schema query (Session 63). PostgREST silently returns null for absent columns. Therefore:

- The C1 SELECT at line 11677 requests `strategic_role` — PostgREST returns null for every row
- The C2 SELECT at line 11718 does the same
- All four display/filter expressions always evaluate to falsy
- The field has **never rendered in production**

### Decision

Do not add `strategic_role` to the `drug_competitive_scores` query. No compatibility plan needed. The filter at line 12000 remains safe: overlap and overlap_rationale are both present in the new table.

---

## 2. P1 — Confidence Display Mapping

### Problem

`_confBadge` (index.html lines 10185–10190) is hard-coded to the legacy confidence enum:

```javascript
const _confBadge = (confLevel, srcUrl) => {
  if (confLevel === 'confirmed' && srcUrl) return `<span ...>✓</span>`;
  if (confLevel === 'supported')           return `<span ...>≈</span>`;
  if (confLevel === 'inferred')            return `<span ...>~</span>`;
  return `<span ...>?</span>`;
};
```

`drug_competitive_scores.confidence_level` uses the new enum: `('A','B','C','inferred')`.

With new values: `A` and `B` fall through to the `?` fallback — visual regression for all drugs where confidence was previously confirmed/supported (≈ 70% of rows).

### Semantic Mapping

| Legacy | New | Meaning | Badge |
|---|---|---|---|
| `confirmed` | `A` | Direct primary-source evidence | ✓ (with source_url) |
| `supported` | `B` | Secondary/indirect evidence | ≈ |
| *(not present)* | `C` | Limited evidence | ◦ (new symbol) |
| `inferred` | `inferred` | No primary source | ~ |
| null | null | Unverified | ? |

Note: `C` is introduced by drug_competitive_scores but was not present in drug_area_scores. No legacy rows will carry this value from the migration (migrated rows map only confirmed→A, supported→B, inferred→inferred). `C` may appear in future enrichment runs.

### Required Fix: Updated `_confBadge`

Replace lines 10185–10190 with:

```javascript
const _confBadge = (confLevel, srcUrl) => {
  // Handle both new (A/B/C) and legacy (confirmed/supported) confidence values
  if ((confLevel === 'A' || confLevel === 'confirmed') && srcUrl)
    return `<span title="Confirmed: source URL on file" style="font-size:8px;margin-left:3px">✓</span>`;
  if (confLevel === 'B' || confLevel === 'supported')
    return `<span title="Supported: inferred from related evidence" style="font-size:8px;margin-left:3px;opacity:0.7">≈</span>`;
  if (confLevel === 'C')
    return `<span title="Low confidence: limited evidence" style="font-size:8px;margin-left:3px;opacity:0.5">◦</span>`;
  if (confLevel === 'inferred')
    return `<span title="Inferred: no primary source" style="font-size:8px;margin-left:3px;opacity:0.6">~</span>`;
  return `<span title="Unverified: no source URL on file" style="font-size:8px;margin-left:3px;opacity:0.45">?</span>`;
};
```

### Tooltip Label Fix

Line 10196 renders the raw `confidence_level` string as a tooltip when no source_url is present:

```javascript
const tooltip = a.source_url
  ? `title="Source: ${a.source_url}"`
  : (a.confidence_level ? `title="${a.confidence_level}"` : '');
```

After migration, this will display `"A"`, `"B"`, or `"C"` instead of `"confirmed"`, `"supported"`. Add a label map inline:

```javascript
const _CONF_LABEL = {A:'Confirmed',B:'Supported','C':'Low confidence',inferred:'Inferred',confirmed:'Confirmed',supported:'Supported'};
const tooltip = a.source_url
  ? `title="Source: ${a.source_url}"`
  : (a.confidence_level ? `title="${_CONF_LABEL[a.confidence_level] || a.confidence_level}"` : '');
```

**This fix must be applied before C1/C2 goes live.** It is the single P0 blocker.

---

## 3. C1/C2 Implementation Plan

### Architecture Change

**Before (C1 — primary fetch, line 11677):**
```javascript
_sb.from('drug_area_scores')
  .select('area_id,overlap,overlap_rationale,strategic_role,cls,confidence_level,source_url')
  .eq('drug_id', drugId)
```

**After (C1 — new fetch):**
```javascript
_sb.from('drug_competitive_scores')
  .select('context_type,context_id,overlap,overlap_rationale,cls,confidence_level,source_url,vs_ailux')
  .eq('drug_id', drugId)
```

The same change applies to C2 (name-search fallback, line 11718).

### scoreMap Rekey

**Before:** `scoreMap0[s.area_id] = s`

**After:** `scoreMap0[s.context_id] = s`

This works because `context_id` aligns with the legacy `area_id` for all non-IBD areas:
- `tl1a`, `il4ra`, `tslp`, `fcrn`, `ted`, `autoimmune`, `respiratory`, `tcell` → unchanged
- `ibd` drugs → now split to `uc` / `cd` context_ids

### areas[] Object Shape

**Before:**
```javascript
areas = areaRes0.data.map(a => ({
  area_id: a.area_id,
  overlap: scoreMap0[a.area_id]?.overlap || null,
  overlap_rationale: scoreMap0[a.area_id]?.overlap_rationale || null,
  strategic_role: scoreMap0[a.area_id]?.strategic_role || null,  // always null — remove
  confidence_level: scoreMap0[a.area_id]?.confidence_level || null,
  source_url: scoreMap0[a.area_id]?.source_url || null,
}));
```

**After:**
```javascript
areas = scoreRes0.data.map(s => ({
  area_id: s.context_id,        // expose as area_id for compatibility with _cemDrugBody
  context_type: s.context_type, // carry forward for potential future use
  overlap: s.overlap || null,
  overlap_rationale: s.overlap_rationale || null,
  // strategic_role: omitted — never existed, never rendered
  confidence_level: s.confidence_level || null,
  source_url: s.source_url || null,
  vs_ailux: s.vs_ailux || null,
}));
```

**Key design decision:** expose `context_id` as `area_id` on the areas object. This preserves all downstream code in `_cemDrugBody` without changes — the renderer uses `a.area_id` for chip labels and the existing `_CEM_AMAP` / `_IND_LABEL` lookups all work against this field.

**Migration from drug_areas join:** The new table is self-contained — every row has overlap data. The `drug_areas` join (which provided the membership list, with scores joined in) is no longer needed. `scoreRes0.data` is the complete source. The `if (!areas.length && scoreRes0.data?.length)` fallback remains valid and simplifies: the fallback IS the primary path.

### Area Label Display — uc/cd Context Fix

`_CEM_AMAP` (line 10366) has no entries for `uc` or `cd`:
```javascript
const _CEM_AMAP = {tl1a:'TL1A',tslp:'TSLP',il4ra:'IL-4Rα',igf1r:'IGF1R/TSHR',fcrn:'FcRn',tcell:'BCMA/CD19/CD3',ox40l:'OX40L',ibd:'IBD',atopy:'Atopy',respiratory:'Respiratory'};
```

After migration, IBD drugs will have `area_id = 'uc'` and `area_id = 'cd'`. The chip label lookup at line 10194:
```javascript
const lbl = a.area_id !== 'global' ? (_AREA_LABEL[a.area_id] || a.area_id || '') : '';
```

Note: this uses `_AREA_LABEL`, not `_CEM_AMAP`. Check `_AREA_LABEL` separately — but `_IND_LABEL` already has `uc: 'Ulcerative Colitis'` and `cd: "Crohn's Disease"` (line 10369).

Inside `_cemDrugBody`, the scoreMap label lookup at line 10366 uses `_CEM_AMAP`. Add `uc`/`cd` entries:

```javascript
const _CEM_AMAP = {
  tl1a:'TL1A', tslp:'TSLP', il4ra:'IL-4Rα', igf1r:'IGF1R/TSHR', fcrn:'FcRn',
  tcell:'BCMA/CD19/CD3', ox40l:'OX40L', ibd:'IBD', atopy:'Atopy',
  respiratory:'Respiratory',
  // IBD expansion — drug_competitive_scores uses indication context_ids
  uc:'UC', cd:'CD',
  // ted is also an indication context_id post-migration
  ted:'TED',
};
```

Short labels (`UC`, `CD`, `TED`) match the chip space constraints. Full names available via `_IND_LABEL` for tooltips if needed.

### `_AREA_LABEL` vs `_CEM_AMAP`

These two maps serve different contexts. `_AREA_LABEL` drives the overlap chip labels in the header band (line 10194); `_CEM_AMAP` drives labels in the `_cemDrugBody` modal card body. Both need `uc`/`cd`/`ted` entries added.

`_AREA_LABEL` location: search for `const _AREA_LABEL` before implementation to confirm line number and add the same entries.

### `vs_ailux_positioning` → `vs_ailux` Rename

The legacy column is `vs_ailux_positioning`. The new column is `vs_ailux`. No dashboard display code currently renders this field in the modal (verified: no `vs_ailux` or `vs_ailux_positioning` reference in `_cemDrugBody` display templates). Carry forward in the areas object as `vs_ailux` for future use. No consumer impact.

### Full Diff Summary (C1 — lines 11674–11700)

| Line range | Change |
|---|---|
| 11677 | `drug_area_scores` → `drug_competitive_scores`; remove `strategic_role`; add `context_type,context_id,vs_ailux`; remove `area_id` |
| 11684–11693 | Remove `scoreMap0` + `drug_areas` join merge; replace with direct `scoreRes0.data.map(s => ...)` keyed on `context_id` as `area_id` |
| 11695–11699 | Simplify fallback: same pattern, already reads from `sr.data` directly |
| 11718 | Same select change as 11677 |
| 11722–11736 | Same areas[] reshape as above for C2 path |
| 10185–10190 | Update `_confBadge` (P0 blocker) |
| 10196 | Add `_CONF_LABEL` map for tooltip |
| 10366 | Add `uc`, `cd`, `ted` to `_CEM_AMAP` |

---

## 4. Dual-Read Validation Design

### Overview

For the first implementation, a temporary comparison harness captures live read discrepancies on each modal open. No UI impact. Console-only output. Keyed by drug_id for deduplication. Stays in production for ≥7 days (the minimum confidence window before removing the legacy read).

### Harness: `window.__MERIDIAN_COMPETITIVE_SCORE_COMPARE__`

Add after the new scores fetch resolves, before rendering:

```javascript
// ── DUAL-READ COMPARISON HARNESS ─────────────────────────────────────
// Remove after 30-day monitoring window closes
(async () => {
  try {
    const { data: legacyScores } = await _sb
      .from('drug_area_scores')
      .select('area_id,overlap,overlap_rationale,confidence_level,source_url')
      .eq('drug_id', drug.id);

    const legacyMap = {};
    (legacyScores || []).forEach(r => { legacyMap[r.area_id] = r; });

    const newMap = {};
    (scoreRes0.data || []).forEach(r => { newMap[r.context_id] = r; });

    // Context-id alignment: legacy area_id should match new context_id for non-IBD drugs
    // IBD drugs: legacy has 'ibd', new has 'uc'/'cd' — expect old_only=['ibd'], new_only=['uc','cd']
    const legacyKeys = new Set(Object.keys(legacyMap));
    const newKeys    = new Set(Object.keys(newMap));

    const matched   = [...legacyKeys].filter(k => newKeys.has(k));
    const oldOnly   = [...legacyKeys].filter(k => !newKeys.has(k));
    const newOnly   = [...newKeys].filter(k => !legacyKeys.has(k));

    // Field parity check for matched contexts
    const fieldMismatches = [];
    for (const ctx of matched) {
      const l = legacyMap[ctx];
      const n = newMap[ctx];
      const CONF_LEGACY_TO_NEW = {confirmed:'A', supported:'B', inferred:'inferred'};
      const lConf = CONF_LEGACY_TO_NEW[l.confidence_level] || l.confidence_level;
      if (l.overlap   !== n.overlap)   fieldMismatches.push({ctx, field:'overlap',   legacy:l.overlap, new_:n.overlap});
      if (lConf       !== n.confidence_level) fieldMismatches.push({ctx, field:'confidence_level', legacy:l.confidence_level, mapped:lConf, new_:n.confidence_level});
      if (l.source_url !== n.source_url) fieldMismatches.push({ctx, field:'source_url', legacy:l.source_url, new_:n.source_url});
    }

    const report = {
      drug_id:    drug.id,
      drug_name:  drug.name,
      ts:         new Date().toISOString(),
      old_count:  legacyScores?.length || 0,
      new_count:  scoreRes0.data?.length || 0,
      matched:    matched.length,
      old_only:   oldOnly,
      new_only:   newOnly,
      field_mismatches: fieldMismatches,
    };

    window.__MERIDIAN_COMPETITIVE_SCORE_COMPARE__ = window.__MERIDIAN_COMPETITIVE_SCORE_COMPARE__ || [];
    window.__MERIDIAN_COMPETITIVE_SCORE_COMPARE__.push(report);

    if (oldOnly.length || fieldMismatches.length) {
      console.warn('[MERIDIAN_CMP] Discrepancy for', drug.name, report);
    } else {
      console.debug('[MERIDIAN_CMP] OK:', drug.name, `old=${report.old_count} new=${report.new_count} matched=${report.matched}`);
    }
  } catch (e) {
    console.warn('[MERIDIAN_CMP] Harness error:', e);
  }
})();
// ── END DUAL-READ HARNESS ─────────────────────────────────────────────
```

### Expected Output by Validation Drug

| Drug | Legacy area_ids | Expected new context_ids | old_only | new_only |
|---|---|---|---|---|
| sim0709 | ibd | uc, cd (if in drug_indications) or ibd (fallback) | ibd | uc,cd |
| batoclimab | fcrn | fcrn | — | — |
| dupilumab | atopy, il4ra | il4ra, tslp (per drug_targets) | atopy | tslp (if present) |
| risankizumab | ibd | uc, cd | ibd | uc,cd |
| efgartigimod | fcrn | fcrn | — | — |
| riliprubart | fcrn | fcrn | — | — |
| epi-001 | ibd | ibd (fallback — no UC/CD in drug_indications) | — | — |
| lm-302 | ibd | uc, cd or ibd | ibd | uc,cd |
| spy072 | ibd | ibd (fallback — pending backfill) | — | — |
| upadacitinib | ibd | uc, cd | ibd | uc,cd |

Note: `old_only: ['ibd']` + `new_only: ['uc','cd']` is the expected IBD expansion pattern — not a regression. The harness does not flag these as errors; they appear in the report for review.

### Accessing Harness Output

In browser console after opening any drug modal:
```javascript
// See all comparison results
window.__MERIDIAN_COMPETITIVE_SCORE_COMPARE__

// Find any with field mismatches
window.__MERIDIAN_COMPETITIVE_SCORE_COMPARE__.filter(r => r.field_mismatches.length > 0)

// Find unexpected old_only (non-IBD areas that disappeared)
window.__MERIDIAN_COMPETITIVE_SCORE_COMPARE__.filter(r =>
  r.old_only.some(k => !['ibd'].includes(k))
)
```

### Removal Trigger

Remove harness (and legacy drug_area_scores fetch inside the harness) after:
- ≥7 days with zero unexpected field mismatches
- Validation set (10 drugs above) all pass expected patterns
- No user-reported display regressions

---

## 5. Blockers Before Coding

### P0 — `_confBadge` update (REQUIRED before deploying C1/C2)

**Risk:** Visual regression. With new A/B/C values, `_confBadge` returns `?` for all previously-confirmed (A) and previously-supported (B) drugs. This affects the overlap chip badges on the modal header.

**Fix:** Defined in P1 above. Two changes: (a) update `_confBadge` to handle A/B/C alongside legacy strings, (b) add `_CONF_LABEL` map for tooltip display.

**Status:** Fix is ready to implement. Must land in the same commit as C1/C2.

### Pre-flight — _AREA_LABEL check

`_AREA_LABEL` (used in header chip labels, line 10194) needs `uc`/`cd`/`ted` entries confirmed or added. Locate `_AREA_LABEL` definition before implementation and verify.

### Constraint — epi-001 fallback is expected

`epi-001` will show `context_id = 'ibd'` (fallback) in `drug_competitive_scores`. The dual-read harness will report `old_only=[]`, `new_only=[]` (both have `ibd`). This is correct. Do NOT backfill epi-001 to UC/CD without source evidence.

### Constraint — C3 PI tab not in scope

C3 (`_makeAreaPI` scoreRows fetch, line 12548) is a behavioral consumer. Do not migrate in this session. It requires a separate area→context_id lookup map and behavioral validation.

### Constraint — Phase 4B consumers (C4–C8) are permanent legacy reads

C4–C8 are dual-read comparison consumers. Their purpose is to compare drug_area_scores vs normalized counts. They must permanently read from `drug_area_scores`. Never migrate them to `drug_competitive_scores`.

### Constraint — company_enrichment.py write path unchanged

Do not modify write path in this session. C11 (parallel-write) must be planned and deployed separately, after C1/C2 is stable ≥7 days.

---

## Implementation Sequence

1. **Pre-flight** — locate `_AREA_LABEL` in index.html; confirm or add `uc`/`cd`/`ted` entries
2. **`_confBadge` fix** — update to handle A/B/C; add `_CONF_LABEL` tooltip map (P0 blocker)
3. **`_CEM_AMAP` update** — add `uc`, `cd`, `ted`
4. **C1 fetch** — swap `drug_area_scores` → `drug_competitive_scores`; update SELECT fields; rekey scoreMap on `context_id`; reshape areas[] object
5. **C2 fetch** — same as C1 for the name-search fallback path
6. **Dual-read harness** — insert comparison block after new fetch resolves
7. **Deploy** — single commit; message: `feat: C1/C2 drug modal migrated to drug_competitive_scores with dual-read harness`
8. **Validate** — open each of 10 validation drugs; confirm console output; confirm no `?` badges on confirmed/supported drugs

---

## Files

- `docs/drug_competitive_scores_consumer_inventory.md` — Full consumer inventory and classifications
- `docs/drug_competitive_scores_design.md` — Consumer migration architecture
- `docs/drug_competitive_scores_migration_report.md` — Migration audit (Session 62)
- `scripts/migrate_drug_area_scores.py` — Migration script (committed, idempotent)

---

*Session 63 — 2026-05-26. C1/C2 planning complete. Implementation pending.*
