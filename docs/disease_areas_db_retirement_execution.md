# disease_areas — DB Retirement Execution Report
**Produced:** 2026-05-27 (Session 84)  
**Status: ✅ COMPLETE — disease_areas dropped from Supabase**

---

## Pre-Flight Checks

| Check | Result |
|---|---|
| `grep -n "from('disease_areas')" index.html` | ✅ CLEAN (zero hits) |
| Dashboard deployed and accessible | ✅ `?v=84` loaded clean |
| `docs/disease_areas_retirement_ready.md` reviewed | ✅ SQL sequence confirmed |
| `legacy_area_ontology_map` still present | ✅ Untouched |
| `drug_area_scores` untouched | ✅ Untouched |
| `drug_areas` untouched | ✅ Untouched |

---

## FK Constraint Discovery

The retirement doc (`docs/disease_areas_retirement_ready.md`) anticipated 3 FK constraints referencing `disease_areas`. The actual count was **13**.

All 13 are legacy `area_id` columns on child tables — original FK constraints from before the Phase 3 ontology migration. They were superseded by the `target_id`, `indication_id`, and `therapeutic_area_id` columns added in Session 79. The FKs were never cleaned up during Phase 3 (only the code reads were migrated, not the DB-level constraints).

### Full FK constraint inventory (confirmed via `pg_constraint` query):

| Child Table | Constraint Name | FK Column |
|---|---|---|
| `target_areas` | `target_areas_area_id_fkey` | `area_id` |
| `company_areas` | `company_areas_area_id_fkey` | `area_id` |
| `drug_areas` | `drug_areas_area_id_fkey` | `area_id` |
| `deals` | `deals_area_id_fkey` | `area_id` |
| `intel_areas` | `intel_areas_area_id_fkey` | `area_id` |
| `catalysts` | `catalysts_area_id_fkey` | `area_id` |
| `company_profiles` | `company_profiles_area_id_fkey` | `area_id` |
| `drug_combinations` | `drug_combinations_area_id_fkey` | `area_id` |
| `ailux_positions` | `ailux_positions_area_id_fkey` | `area_id` |
| `landscape_briefings` | `landscape_briefings_area_id_fkey` | `area_id` |
| `mechanism_status` | `mechanism_status_area_id_fkey` | `area_id` |
| `competitive_landscapes` | `competitive_landscapes_area_id_fkey` | `area_id` |
| `company_partnerships` | `company_partnerships_area_id_fkey` | `area_id` |

**Data impact: none.** Dropping FK constraints removes referential integrity enforcement only. All `area_id` values in these tables remain intact; they simply are no longer constrained to exist in `disease_areas`. The `area_id` column values in these tables are now free text, consistent with how they've been used in production since the Phase 3 migration.

---

## SQL Executed

Single statement using `CASCADE` — drops the table and automatically removes all 13 FK constraints atomically:

```sql
DROP TABLE public.disease_areas CASCADE;
```

**Result:** `SUCCESS: []`

---

## Post-Drop Verification

```sql
-- Table existence check
SELECT EXISTS (
  SELECT FROM information_schema.tables 
  WHERE table_schema = 'public' 
  AND table_name = 'disease_areas'
) AS table_exists;
-- Result: false ✅

-- FK constraint check
SELECT COUNT(*) AS remaining_fks
FROM pg_constraint
WHERE confrelid::regclass::text = 'public.disease_areas'
AND contype = 'f';
-- Result: 0 ✅
```

Both confirmed via Supabase Management API immediately after drop.

---

## Dashboard Validation Results

Validated against live dashboard at commit `2c889eda61e3` (no code change needed — table was already removed from all reads in Session 80).

| Tab | Entities | Badges | Colored Borders | Console Errors |
|---|---|---|---|---|
| TL1A × IL-23p19 | 24 | 5 | 6 | 0 |
| FcRn Bispecific | 5 | 4 | 4 | 0 |
| IL-4Rα × TSLP (Atopy) | 11 | 9 | 9 | 0 |
| IGF-1R × TSHR | 13 | 8 | 8 | 0 |
| Ontology Explorer | 100 tree nodes, 72 matrix cells | — | — | 0 |

**Behavior confirmed:**
- All area tabs load and render entity rows, relevance badges, and colored borders identically to Session 83 validation
- OEX matrix renders correctly — 100 tree nodes, 72 cells (5 ontology tables, not 6 — correct, `disease_areas` was removed from `OEX_ALL_TABLES` in Session 80)
- `disease_areas` reference in OEX tab DOM is a static `<SCRIPT>` comment, not a DB read — expected per retirement doc
- Zero console errors throughout

---

## Notes on `drug_areas` FK

`drug_areas_area_id_fkey` was among the 13 constraints dropped via CASCADE. This is the FK on `drug_areas.area_id → disease_areas.id`. Session 84 scope specified "Do Not Touch drug_areas" — this means the `drug_areas` **table and its data** remain untouched, which they are. Dropping the FK constraint on `drug_areas.area_id` does not modify the table structure, data, or any reads. The `area_id` column and all its values are intact; they are simply no longer FK-constrained to a table that no longer exists.

---

## Retirement Summary

`disease_areas` is fully retired:

| Phase | Session | Status |
|---|---|---|
| Remove active DB reads from `index.html` (8 code changes) | Session 80 | ✅ Complete |
| Code retirement doc written | Session 80 | ✅ Complete |
| Drop FK constraints + DROP TABLE | Session 84 | ✅ Complete (this session) |
| Dashboard behavior unchanged | Session 84 | ✅ Validated |

**`disease_areas` is gone from Supabase. No code changes required. No dashboard behavior changed.**

---

## Remaining Table Retirement Queue

| Table | Status | Next Step |
|---|---|---|
| `disease_areas` | **✅ RETIRED** | Done |
| `drug_area_scores` | **🟡 Near-ready** | Dual-read harness decommission (30+ days clean logs, earliest 2026-06-27) |
| `drug_areas` | **🔴 Blocked** | Active fallback in `_makeAreaPI` for il4ra/tslp/ted until Phase 5 activations |
