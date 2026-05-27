# intel_areas — Ontology Migration Report
**Produced:** 2026-05-27 (Session 86)  
**Dashboard commit:** `9635495a3f`  
**Status: ✅ COMPLETE — intel_areas reads ontology-native, dual-filter active**

---

## Summary

`intel_areas` was migrated from legacy `area_id`-only routing to ontology-native routing using the standard Phase 3 pattern: add ontology columns, backfill from `legacy_area_ontology_map`, flip reads to dual-filter.

This is the first migration in the Group D (operational tables) wave. The same pattern applies directly to `research_queue`, `competitive_signals`, `company_profiles`, and `signals`.

---

## Pre-Migration Audit

### Table State Before Migration

| Column | Type | Notes |
|---|---|---|
| `intel_id` | bigint NOT NULL | FK to intel table |
| `area_id` | text NOT NULL | Legacy routing key — only column before this session |

18 rows across 5 area_ids: `fcrn` (3), `igf1r` (6), `il4ra` (4), `tcell` (3), `tslp` (2)

### Code Read Inventory (9 total references, 6 actual DB reads)

| Line | Function / Context | Pattern | Migration action |
|---|---|---|---|
| 3145 | Morning Report Promise.all | `select('intel_id,area_id')` | Add `target_id,context_type` to select |
| 3846–3847 | `loadAreaIntel` area tab filter | `.in('area_id', areas)` | **Flip to dual-filter** |
| 17235 | Intelligence Feed bulk load | `select(...).limit(2000)` | Add `target_id,context_type` to select |
| 17615 | `loadLiveIntel` bulk load | `select(...).limit(200)` | Add `target_id,context_type` to select |
| 17816 | `ALL_TABLES` homepage poller | Table name only | No change (count display only) |
| 18015 | `loadTL1AIntelFeed` | `.eq('area_id','tl1a')` | Flip to dual-filter |
| 18412 | Search embedded select | `intel_areas(area_id)` | Add `target_id` to sub-select |

### Decision: Phase 3 Migration (Not intel_target_links Swap)

`intel_target_links` (1,288 rows) was considered as a replacement. It was ruled out because the two tables serve different roles:
- `intel_areas` = **editorial curation** — a human/Claude decision that an intel item is relevant to an area
- `intel_target_links` = **auto-generated mentions** — `mention_type = 'mentioned'` for all 1,288 rows; tracks which targets appear in each intel item's text

Overlap was partial (8/18 rows existed in both), and `intel_target_links` uses specific target IDs (bcma, cd19, etc.) rather than area IDs (tcell), making it unsuitable as a drop-in replacement for `intel_areas`.

---

## SQL Executed

### Step 1 — Add ontology columns

```sql
ALTER TABLE public.intel_areas
  ADD COLUMN IF NOT EXISTS target_id           text,
  ADD COLUMN IF NOT EXISTS indication_id       text,
  ADD COLUMN IF NOT EXISTS therapeutic_area_id text,
  ADD COLUMN IF NOT EXISTS context_type        text;
```

**Result:** Success

### Step 2 — Backfill from legacy_area_ontology_map

```sql
UPDATE public.intel_areas ia
SET
  target_id           = lam.target_id,
  therapeutic_area_id = lam.therapeutic_area_id,
  context_type        = lam.context_type
FROM public.legacy_area_ontology_map lam
WHERE ia.area_id = lam.legacy_area_id;
```

**Result:** 18 rows updated (100% — all rows mapped)

### Backfill Verification

| area_id | target_id | context_type | therapeutic_area_id | rows |
|---|---|---|---|---|
| fcrn | fcrn | target | neurology | 3 |
| igf1r | igf1r | target | ophthalmology | 6 |
| il4ra | il4ra | target | dermatology | 4 |
| tcell | **null** | platform_view | immunology | 3 |
| tslp | tslp | target | respiratory | 2 |

Note: `tcell` correctly has `target_id = null` — it maps to a `platform_view` context, not a specific target. The dual-filter handles this via `area_id` fallback.

---

## Code Changes

**6 changes in `index.html`**, all in existing DB read calls:

### Change 1 — Morning Report bulk load (line 3145)

```javascript
// Before:
_sb.from('intel_areas').select('intel_id,area_id'),
// After:
_sb.from('intel_areas').select('intel_id,area_id,target_id,context_type'),
```

### Change 2 — `loadAreaIntel` filter (lines 3846–3847) — CRITICAL

```javascript
// Before:
const { data: iaRows, error: iaErr } = await _sb.from('intel_areas')
  .select('intel_id').in('area_id', areas);
// After:
const { data: iaRows, error: iaErr } = await _sb.from('intel_areas')
  .select('intel_id').or(`target_id.in.(${areas.join(',')}),area_id.in.(${areas.join(',')})`);
```

This is the read that powers the live-intel card on every area tab. Ontology path (`target_id`) is now primary; `area_id` is the fallback. `tcell` tab (ACE tab) uses `area_id` fallback correctly since `target_id = null`.

### Change 3 — Intelligence Feed bulk load (line 17235)

```javascript
// Before:
_sb.from('intel_areas').select('intel_id,area_id').limit(2000),
// After:
_sb.from('intel_areas').select('intel_id,area_id,target_id,context_type').limit(2000),
```

### Change 4 — `loadLiveIntel` bulk load (line 17615)

```javascript
// Before:
const { data: iaRows } = await _sb.from('intel_areas').select('intel_id,area_id').limit(200);
// After:
const { data: iaRows } = await _sb.from('intel_areas').select('intel_id,area_id,target_id,context_type').limit(200);
```

### Change 5 — `loadTL1AIntelFeed` filter (line 18015)

```javascript
// Before:
const { data: iaRows } = await _sb.from('intel_areas').select('intel_id,area_id').eq('area_id','tl1a').limit(100);
// After:
const { data: iaRows } = await _sb.from('intel_areas').select('intel_id,area_id,target_id').or('target_id.eq.tl1a,area_id.eq.tl1a').limit(100);
```

Note: No `intel_areas` rows exist for `tl1a` — this read returns empty before and after migration. Change is for consistency.

### Change 6 — Search embedded select (line 18412)

```javascript
// Before:
_sb.from('intel').select('id,intel_date,headline,intel_type,importance,source_url,intel_areas(area_id)')
// After:
_sb.from('intel').select('id,intel_date,headline,intel_type,importance,source_url,intel_areas(area_id,target_id)')
```

---

## Validation Results

All four intel-bearing area tabs confirmed rendering correctly after deploy:

| Tab | area_ids | Routing path | Intel rendered | Console errors |
|---|---|---|---|---|
| FcRn | fcrn | `target_id = 'fcrn'` (ontology path) | ✅ 3 items, incl. Immunovant Phase 3 failure | 0 |
| IGF-1R × TSHR | igf1r | `target_id = 'igf1r'` (ontology path) | ✅ 6 items | 0 |
| IL-4Rα × TSLP | il4ra, tslp | `target_id IN ('il4ra','tslp')` (ontology path) | ✅ 6 combined items | 0 |
| ACE (T-cell) | tcell | `area_id = 'tcell'` (**fallback path** — target_id null) | ✅ 3 items | 0 |
| TL1A | tl1a, ibd | n/a — TL1A uses separate intel feed function | no live-intel element (expected) | 0 |

**Dual-filter validated:** both paths confirmed working — ontology path for target-mapped areas, `area_id` fallback for platform_view context (`tcell`).

---

## Reusable Pattern

This migration establishes the standard pattern for all remaining Group D operational tables (`research_queue`, `competitive_signals`, `company_profiles`, `signals`):

1. **ALTER TABLE** — add `target_id text`, `indication_id text`, `therapeutic_area_id text`, `context_type text`
2. **UPDATE** — backfill from `legacy_area_ontology_map` on `area_id = legacy_area_id`
3. **Code flip** — change `.in('area_id', areas)` → `.or('target_id.in.(...),area_id.in.(...)')`
4. **Select expansion** — add `target_id,context_type` to all bulk reads

The backfill SQL is identical for every table; only the table name changes. The dual-filter string is identical for every code read; only the `areas` variable content differs.

---

## What area_id Is Now

After this migration, `intel_areas.area_id` is a **retained legacy key** — exactly like `catalysts.area_id`, `company_areas.area_id`, and `deals.area_id` after their Phase 3 migrations. It:
- Still contains valid data (unchanged)
- Is still read via the dual-filter fallback (for `tcell` and any future unmapped areas)
- Is no longer the sole routing field
- Can be deprecated once the ontology columns have proven stable (no rush — not a blocker for any retirement)
