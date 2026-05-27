# disease_areas — Code Retirement Checklist
**Produced:** 2026-05-27 (Session 80)  
**Dashboard commit:** `fba9f390cc53`  
**Status: ✅ CODE RETIREMENT COMPLETE — table is safely droppable**

---

## Summary

All active JavaScript DB reads referencing `disease_areas` have been removed or stubbed from `index.html`. The table can now be dropped in a future DB session once the three FK constraints on child tables are torn down first.

---

## What Was Cleaned in Session 80 (8 code changes)

| Change | Location | Before | After |
|---|---|---|---|
| `OEX_ALL_TABLES` | line ~23592 | `'disease_areas',` in table array | Removed with comment |
| `ALL_TABLES` homepage counter | line ~17704 | `'disease_areas',` in counter array | Removed with comment |
| Admin row-count fetch | line ~24939 | `_sb.from('disease_areas').select('*').order('name')` | `Promise.resolve({ data: [] })` stub |
| `_loadOntologyExplorer` | line ~26388 | `_sb.from('disease_areas').select('id,label,...')` | `Promise.resolve({ data: [] })` stub |
| `OEX_JOIN_MAP` (primary) | line ~23596 | `disease_areas: [...]` key with FK children | Key removed; mechanism_status/competitive_landscapes/area_metadata set to `[]` |
| `OEX_JOIN_MAP` (fallback) | line ~22755 | Same disease_areas key in admin catalog copy | Key removed; same cleanup |
| `OEX_FK_MAP` | line ~23641 | `disease_areas:'area_id'` in every child-table entry | All entries removed; area_metadata/mechanism_status/competitive_landscapes have `{}` |
| `SEED_CAT_DATA` | line ~22696 | `disease_areas` entry in ontology tables catalog | Entry removed with comment |

---

## Final Grep Verification

```
grep -n "_sb.from('disease_areas')" index.html  →  CLEAN (zero hits)
grep -n ".from('disease_areas')"    index.html  →  CLEAN (zero hits)
```

Run at commit `fba9f390cc53`. Zero active DB reads remain.

---

## Remaining References (All Static — Safe)

These references do NOT issue DB queries. They are static HTML documentation strings and display labels that remain for historical/audit context.

| Lines | Type | Content | Action |
|---|---|---|---|
| ~20621–21032 | Static HTML | Ontology Audit architecture notes | **Keep** — historical docs |
| ~24967 | Admin display | `disease_areas: (daRows\|\|[]).length` → renders `0` | **Keep** — count is 0 from stub |
| ~25005 | Admin taxonomy row | Documents disease_areas as "Layer 1 · Taxonomy" | **Keep** — static admin reference |
| ~25120 | Admin table card | Documentation card for disease_areas | **Keep** — static admin reference |
| ~25209–25216 | Ontology matrix diagram | Hardcoded relationship visualization | **Keep** — static diagram |
| ~25273–25337 | Admin issue cards | Documents ontology migration history | **Keep** — historical docs |
| ~26313, ~26316 | OEX reference panel | `card('disease_areas',...)` display label | **Keep** — static display |

---

## OEX Validation Results (Session 80)

| Check | Result |
|---|---|
| OEX tree: `disease_areas` node present | ✅ Absent — removed from `OEX_ALL_TABLES` |
| OEX Ontology group table count | ✅ **5 tables** (was 6 — correct) |
| OEX matrix renders (TL1A/IBD rows) | ✅ TL1A 94%, IBD 96% |
| Ontology Audit panel loads | ✅ Clean, no errors |
| Console errors | ✅ Zero |

---

## DB FK Constraints Still Present (Require Separate DB Session)

The `disease_areas` table is still a FK **parent** for three child tables. These constraints must be dropped before the table can be dropped.

```sql
-- Step 1: Find constraint names (run in Supabase SQL Editor first)
SELECT conname, conrelid::regclass AS table_name
FROM pg_constraint
WHERE confrelid = 'public.disease_areas'::regclass
AND contype = 'f';
```

Expected constraints to drop:

```sql
-- Step 2: Drop FK constraints
ALTER TABLE public.area_metadata         DROP CONSTRAINT IF EXISTS area_metadata_area_id_fkey;
ALTER TABLE public.mechanism_status      DROP CONSTRAINT IF EXISTS mechanism_status_area_id_fkey;
ALTER TABLE public.competitive_landscapes DROP CONSTRAINT IF EXISTS competitive_landscapes_area_id_fkey;

-- Step 3: Drop the table
DROP TABLE public.disease_areas;
```

> ⚠️ **Run Step 1 first** to confirm actual constraint names — they may differ from the expected names above.

---

## Tables That Must NOT Be Dropped (Keep Permanently)

| Table | Reason |
|---|---|
| `area_metadata` | Migration tracking system; `area_id` is this table's own PK, not just a FK |
| `legacy_area_ontology_map` | Bridge table powering all Phase 3 backfills; needed for future migrations |
| `drug_areas` | Still active fallback in `_makeAreaPI` for non-activated areas (il4ra, tslp, ted) |
| `drug_area_scores` | Cannot retire yet — `competitive_relevance`/`relevance_rationale` fields only exist here; dual-read harnesses active |

---

## drug_area_scores Retirement Blocker (Not Session 80 Scope)

Before `drug_area_scores` can be retired, one of the following must happen:

**Option A** — Backfill `competitive_relevance` + `relevance_rationale` into `drug_competitive_scores`, then decommission dual-read harnesses.

**Option B** — Formally deprecate those fields (accept data loss), decommission dual-read harnesses.

Until decided: `drug_area_scores` stays untouched. The dual-read harnesses (`_runPhase4B*DualRead`) are intentional archival validation and must not be removed.

---

## Session 80 Success Criteria — Final Status

| Criterion | Status |
|---|---|
| `grep -n "from('disease_areas')" index.html` returns zero hits | ✅ PASS |
| OEX Explorer matrix renders all area rows | ✅ PASS (TL1A 94%, IBD 96%, etc.) |
| Admin panel (Ontology Audit) loads without JS errors | ✅ PASS |
| `disease_areas_retirement_ready.md` written | ✅ This file |
| No table dropped | ✅ Confirmed |
| `update_log.md` updated | 🔄 Pending |
| `NEXT_SESSION.md` updated for Session 81 | 🔄 Pending |
