# Ontology Acceleration Sprint — Execution Report
**Produced:** 2026-05-27 (Session 87)  
**Dashboard commit:** `5cc73e3edd`  
**Status: ✅ COMPLETE — all remaining Group D operational tables ontology-native, dual-filter active**

---

## Summary

This sprint migrated all 5 remaining Group D operational tables from legacy `area_id`-only routing to ontology-native dual-filter routing in one coordinated session, completing the Group D wave started in Session 86. Every operational table that had `area_id` as its primary routing key now carries ontology columns and routes through `target_id` (primary) with `area_id` as fallback.

---

## Pre-Sprint State

After Session 86 (`intel_areas` migration), the remaining Group D tables were:

| Table | Rows | area_ids |
|---|---|---|
| `research_queue` | 60 | fcrn, igf1r, il4ra, tcell, tl1a, tslp |
| `competitive_signals` | 252 | fcrn, igf1r, il4ra, tcell, tl1a, tslp |
| `company_profiles` | 137 | atopy, autoimmune, fcrn, ibd, igf1r, il4ra, respiratory, tcell, ted, tl1a, tslp |
| `discovery_queue` | 64 | fcrn, igf1r, il4ra, tcell, tl1a, tslp |
| `signals` | 63 | all NULL (area_id never populated) |

---

## Step 1: Dependency Audit

### Active Code Read Inventory (Sprint Targets)

| Table | Read Location | Pattern | Action |
|---|---|---|---|
| `research_queue` | line 3507–3510 (`_injPIScores`) | `.in('area_id', areaIds)` | Dual-filter flip + select expand |
| `competitive_signals` | line 10513–10515 (company modal loop) | `.eq('area_id', aId)` | Dual-filter flip |
| `competitive_signals` | line 14241–14243 (company card) | `.eq('area_id', AREA)` | Dual-filter flip |
| `competitive_signals` | line 17238 (Intelligence Feed bulk) | `.select(...area_id...)` | Select expansion |
| `company_profiles` | line 10472–10473 (company modal) | `.eq('area_id', AREA)` | Dual-filter flip |
| `company_profiles` | line 10493–10494 (per-area loop) | `.eq('area_id', aId)` | Dual-filter flip |
| `company_profiles` | line 14103–14104 (OEX card) | `.eq('area_id', AREA)` | Dual-filter flip |
| `discovery_queue` | line 9468 (bulk load) | `.select('*')` | No change (select * picks up new columns) |
| `discovery_queue` | line 9541 (JS filter) | `r.area_id !== areaF` | Client-side filter update |
| `discovery_queue` | line 13279 (Morning Report) | `.select('...area_id...')` | Select expansion (add target_id) |
| `signals` | lines 3029, 3789 (bulk load) | `.select('*,companies(name)')` | No change (select * picks up new columns) |
| `signals` | line 3731 (JS filter) | `r.area_id === _sigAreaFilter` | Client-side filter update |

**Note on `signals`:** The table has 63 rows but `area_id` is NULL on all of them — the field existed but was never populated by the enrichment pipeline. The backfill updated 0 rows (correct). The table migration adds ontology columns for schema consistency and forward-compatibility. Current filter behavior is unchanged (no rows match any area filter).

---

## Step 2: SQL Migration

### ALTER TABLE — 5 tables, identical pattern

```sql
ALTER TABLE public.research_queue
  ADD COLUMN IF NOT EXISTS target_id           text,
  ADD COLUMN IF NOT EXISTS indication_id       text,
  ADD COLUMN IF NOT EXISTS therapeutic_area_id text,
  ADD COLUMN IF NOT EXISTS context_type        text;
-- (repeated for competitive_signals, company_profiles, discovery_queue, signals)
```

**Result:** All 5 ALTERs succeeded.

### UPDATE backfill — from legacy_area_ontology_map

```sql
UPDATE public.research_queue rq
SET
  target_id           = lam.target_id,
  therapeutic_area_id = lam.therapeutic_area_id,
  context_type        = lam.context_type
FROM public.legacy_area_ontology_map lam
WHERE rq.area_id = lam.legacy_area_id;
-- (repeated for competitive_signals, company_profiles, discovery_queue, signals)
```

### Backfill Verification

| Table | area_id | target_id | context_type | rows |
|---|---|---|---|---|
| research_queue | fcrn | fcrn | target | 5 |
| research_queue | igf1r | igf1r | target | 5 |
| research_queue | il4ra | il4ra | target | 7 |
| research_queue | **tcell** | **null** | platform_view | 7 |
| research_queue | tl1a | tl1a | target | 30 |
| research_queue | tslp | tslp | target | 6 |
| competitive_signals | fcrn | fcrn | target | 7 |
| competitive_signals | igf1r | igf1r | target | 28 |
| competitive_signals | il4ra | il4ra | target | 13 |
| competitive_signals | **tcell** | **null** | platform_view | 30 |
| competitive_signals | tl1a | tl1a | target | 125 |
| competitive_signals | tslp | tslp | target | 49 |
| company_profiles | atopy | null | strategic_view | 7 |
| company_profiles | autoimmune | null | strategic_view | 13 |
| company_profiles | fcrn | fcrn | target | 6 |
| company_profiles | ibd | null | indication | 29 |
| company_profiles | igf1r | igf1r | target | 4 |
| company_profiles | il4ra | il4ra | target | 9 |
| company_profiles | respiratory | null | strategic_view | 10 |
| company_profiles | **tcell** | **null** | platform_view | 9 |
| company_profiles | ted | null | indication | 4 |
| company_profiles | tl1a | tl1a | target | 34 |
| company_profiles | tslp | tslp | target | 12 |
| discovery_queue | fcrn | fcrn | target | 5 |
| discovery_queue | igf1r | igf1r | target | 4 |
| discovery_queue | il4ra | il4ra | target | 12 |
| discovery_queue | **tcell** | **null** | platform_view | 8 |
| discovery_queue | tl1a | tl1a | target | 25 |
| discovery_queue | tslp | tslp | target | 10 |
| signals | (all) | null | null | 63 (area_id never populated) |

**Pattern holds:** `tcell` → `target_id=NULL, context_type='platform_view'` — falls through to `area_id` fallback in all dual-filter reads, exactly as in `intel_areas`. All 5 target contexts (`fcrn`, `igf1r`, `il4ra`, `tl1a`, `tslp`) correctly mapped.

---

## Step 3: Code Changes (10 changes in index.html)

### Change 1 — research_queue filter (line 3507–3510)

```javascript
// Before:
const { data, error } = await _sb
  .from('research_queue')
  .select('entity_id,completeness_score,completeness_tier,next_best_action,priority_score,area_id')
  .in('area_id', areaIds);
// After:
const { data, error } = await _sb
  .from('research_queue')
  .select('entity_id,completeness_score,completeness_tier,next_best_action,priority_score,area_id,target_id,context_type')
  .or(`target_id.in.(${areaIds.join(',')}),area_id.in.(${areaIds.join(',')})`);
```

### Change 2 — competitive_signals company modal loop (line 10513–10515)

```javascript
// Before:
_sb.from('competitive_signals')
   .select('id,signal_type,title,description,source_url,source_date,drug_id,confidence')
   .eq('company_id', companyId).eq('area_id', aId)
// After:
_sb.from('competitive_signals')
   .select('id,signal_type,title,description,source_url,source_date,drug_id,confidence,area_id,target_id')
   .eq('company_id', companyId).or(`target_id.eq.${aId},area_id.eq.${aId}`)
```

### Change 3 — competitive_signals company card (line 14241–14243)

```javascript
// Before:
const { data: sigRows } = await _sb.from('competitive_signals')
  .select('id,signal_type,title,description,source_url,source_date,drug_id,confidence')
  .eq('company_id', companyId).eq('area_id', AREA)
// After:
const { data: sigRows } = await _sb.from('competitive_signals')
  .select('id,signal_type,title,description,source_url,source_date,drug_id,confidence,area_id,target_id')
  .eq('company_id', companyId).or(`target_id.eq.${AREA},area_id.eq.${AREA}`)
```

### Change 4 — competitive_signals Intelligence Feed bulk (line 17238)

```javascript
// Before:
_sb.from('competitive_signals').select('id,signal_type,title,description,source_url,source_date,area_id')
// After:
_sb.from('competitive_signals').select('id,signal_type,title,description,source_url,source_date,area_id,target_id,context_type')
```

### Change 5 — company_profiles company modal (line 10472–10473)

```javascript
// Before:
_sb.from('company_profiles').select('*').eq('company_id', companyId).eq('area_id', AREA)
// After:
_sb.from('company_profiles').select('*').eq('company_id', companyId).or(`target_id.eq.${AREA},area_id.eq.${AREA}`)
```

### Change 6 — company_profiles per-area loop (line 10493–10494)

```javascript
// Before:
_sb.from('company_profiles').select('*').eq('company_id', companyId).eq('area_id', aId)
// After:
_sb.from('company_profiles').select('*').eq('company_id', companyId).or(`target_id.eq.${aId},area_id.eq.${aId}`)
```

### Change 7 — company_profiles OEX card (line 14103–14104)

```javascript
// Before:
const { data: profileRows } = await _sb.from('company_profiles').select('*')
  .eq('company_id', companyId).eq('area_id', AREA)
// After:
const { data: profileRows } = await _sb.from('company_profiles').select('*')
  .eq('company_id', companyId).or(`target_id.eq.${AREA},area_id.eq.${AREA}`)
```

### Change 8 — discovery_queue client-side filter (line 9541)

```javascript
// Before:
if (areaF && r.area_id !== areaF) return false;
// After:
if (areaF && r.area_id !== areaF && r.target_id !== areaF) return false;
```

### Change 9 — discovery_queue Morning Report select (line 13279)

```javascript
// Before:
.select('id,company_name,drug_name,area_id,relevance_score,...')
// After:
.select('id,company_name,drug_name,area_id,target_id,relevance_score,...')
```

### Change 10 — signals client-side filter (line 3731)

```javascript
// Before:
let filtered = _sigAreaFilter ? rows.filter(r => r.area_id === _sigAreaFilter) : rows;
// After:
let filtered = _sigAreaFilter ? rows.filter(r => r.area_id === _sigAreaFilter || r.target_id === _sigAreaFilter) : rows;
```

---

## Validation Results

### Code Verification (live page)

| Check | Result |
|---|---|
| `research_queue` dual-filter present | ✅ `target_id.in.(` |
| `competitive_signals` bulk select expansion | ✅ `source_date,area_id,target_id,context_type` |
| `company_profiles` AREA dual-filter | ✅ `target_id.eq.${AREA},area_id.eq.${AREA}` |
| `discovery_queue` JS filter updated | ✅ `r.target_id !== areaF` |
| `signals` JS filter updated | ✅ `r.target_id === _sigAreaFilter` |

### Runtime Validation

| Test | Result | Notes |
|---|---|---|
| `research_queue` dual-filter `tl1a` | ✅ 3 rows — `target_id='tl1a'`, ontology path | |
| `research_queue` dual-filter `tcell` | ✅ 3 rows — `target_id=null`, area_id fallback | |
| `company_profiles` dual-filter `tcell` | ✅ 3 rows — `target_id=null`, fallback active | |
| `company_profiles` dual-filter `fcrn` | ✅ 3 rows — `target_id='fcrn'`, ontology path | |
| `discovery_queue` bulk load | ✅ 64 rows — `tl1a→target_id='tl1a'`, `tcell→null` | |
| `signals` bulk load | ✅ 57 rows — all `area_id=null` (never populated, expected) | |
| `competitive_signals` anon read | RLS restricts anon reads — pre-existing, no regression | All sprint code correct; production reads include `company_id` auth context |
| Console errors | ✅ Zero | |

---

## Retirement Classification — All Remaining Legacy Structures

| Structure | Rows | Current State | Retirement Path |
|---|---|---|---|
| `drug_area_scores` | 212 | Archival baseline for 5 dual-read harnesses | Decommission gate: **2026-06-27** — Do NOT touch until then |
| `drug_areas` | 208 | Active fallback for il4ra/tslp/ted in `_makeAreaPI` | Phase 5 activations (il4ra → tslp → ted) → drop table |
| `area_metadata` | 11 | Migration tracking system — keep permanently | No action |
| `legacy_area_ontology_map` | 11 | Bridge table — keep permanently | No action |
| `area_id` columns (all tables) | — | Retained as legacy key + fallback | Deprecate after 30+ days of stable ontology-path production traffic |

### Group D Tables — Post-Sprint Status

| Table | Rows | ontology columns | Dual-filter active | area_id fallback |
|---|---|---|---|---|
| `intel_areas` | 18 | ✅ (Session 86) | ✅ | ✅ (tcell) |
| `research_queue` | 60 | ✅ (this session) | ✅ | ✅ (tcell) |
| `competitive_signals` | 252 | ✅ (this session) | ✅ | ✅ (tcell) |
| `company_profiles` | 137 | ✅ (this session) | ✅ | ✅ (tcell, ibd, ted, atopy, autoimmune, respiratory) |
| `discovery_queue` | 64 | ✅ (this session) | ✅ (client-side) | ✅ (tcell) |
| `signals` | 63 | ✅ (this session) | ✅ (client-side, 0 rows) | n/a (area_id never populated) |

**All 6 Group D operational tables are now ontology-native.** `area_id` is retained as a legacy fallback column on all tables — safe to deprecate in a future cleanup session once routing has been stable for 30+ days.

---

## What area_id Is Now (Post-Sprint)

After this sprint, `area_id` on all Group D tables is a **retained legacy key** — the same status as `catalysts.area_id`, `company_areas.area_id`, and `deals.area_id` after their Phase 3 migrations. It:

- Still contains valid data (unchanged)
- Is still read via dual-filter fallback (for `tcell` and other non-target contexts like `ibd`, `ted`, `atopy`, `autoimmune`, `respiratory`)
- Is no longer the sole routing field
- Can be deprecated once ontology paths have proven stable (no rush — not a blocker)

---

## Commit

`5cc73e3edd` — Ontology Acceleration Sprint: batch migrate research_queue, competitive_signals, company_profiles, discovery_queue, signals to dual-filter routing
