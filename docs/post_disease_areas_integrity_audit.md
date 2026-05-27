# Post-disease_areas Integrity Audit
**Produced:** 2026-05-27 (Session 85)  
**Scope:** Schema + code + ontology bridge audit after `disease_areas` DROP (Session 84)  
**Status: ✅ CLEAN — no hidden inconsistencies found**

---

## 1. Schema Audit

### 1.1 disease_areas Confirmation

```sql
SELECT EXISTS (SELECT FROM information_schema.tables 
  WHERE table_schema = 'public' AND table_name = 'disease_areas') AS table_exists;
-- Result: false ✅
```

Table is gone. No residual FK constraints remain (`remaining_fks = 0` confirmed Session 84).

### 1.2 All area_id Columns — Full Inventory

27 tables in the public schema have an `area_id` column. Each is classified below.

#### Group A — System / Permanent (area_id is the table's own PK or identity field)

| Table | Rows | Notes |
|---|---|---|
| `area_metadata` | 11 | `area_id` IS the PK of this table; it is NOT a FK to disease_areas. Permanent migration-tracking system. Keep forever. |

#### Group B — Legacy Tables Pending Retirement (main migration queue)

| Table | Rows | Status | Blocker |
|---|---|---|---|
| `drug_area_scores` | 212 | Archival baseline — no production UI reads | 5 dual-read harnesses; decommission gate 2026-06-27 |
| `drug_areas` | 208 | Active fallback in `_makeAreaPI` for il4ra/tslp/ted | Phase 5 activations for 3 remaining areas |

#### Group C — Phase 3 Migrated (area_id retained as legacy key, companion ontology columns added)

These tables have BOTH `area_id` (legacy) and one or more of `target_id`, `indication_id`, `therapeutic_area_id` (new ontology columns). The `area_id` column is still populated and still read in production via dual-filter OR expressions. Migration is functionally complete; `area_id` is a safe legacy field.

| Table | Rows | Companion Columns | Production Read Pattern |
|---|---|---|---|
| `catalysts` | 826 | `target_id`, `indication_id`, `therapeutic_area_id` | `.or('target_id.in.(...),area_id.in.(...)')` dual-filter |
| `company_areas` | 134 | `target_id`, `therapeutic_area_id` | `.eq('area_id', ...)` — also exposed via `effective_company_areas` view |
| `deals` | 199 | `target_id`, `therapeutic_area_id` | `.or('target_id.in.(...),area_id.in.(...)')` dual-filter |
| `mechanism_status` | 33 | `target_id`, `indication_id` | Used in OEX / competitive landscape views |
| `target_areas` | 12 | `target_id` | Area-to-target mapping table; `target_id` is primary |

#### Group D — Intelligence / Operational Tables (area_id is primary routing key, not yet migrated)

These tables use `area_id` as their primary area context. No companion ontology columns. Active in production reads. Each is a candidate for future Phase 3-style migration.

| Table | Rows | Code Read Location | Migration Complexity |
|---|---|---|---|
| `intel_areas` | 18 | line ~3145, ~3847 | Low — 18 rows, simple intel→area join |
| `research_queue` | 60 | line ~4164, ~4181 | Low — 60 rows, add `target_id` + dual-filter |
| `competitive_signals` | 252 | line ~13182 | Medium — 252 rows, need target/indication mapping |
| `company_profiles` | 137 | lines ~3156, ~4100, ~10565 | Medium — 137 rows, used in company card modal |
| `discovery_queue` | 64 | lines ~9444, ~9517 | Low — 64 rows; note: has own `strategic_value_score` (active) |
| `signals` | 63 | lines ~3609, ~3731 | Low — 63 rows |

#### Group E — Computed Views / Derived Tables (area_id inherited, not directly migrated)

These are computed views or summary tables derived from Group C/D tables. Their `area_id` values flow from the source tables. No independent migration needed.

| Table | Rows | Source |
|---|---|---|
| `effective_company_areas` | 137 | Derived from `company_areas` |
| `company_area_detail` | 134 | Derived from `company_areas` |
| `catalyst_bd_timing_window` | 293 | Derived from `catalysts` |
| `coverage_scores` | 137 | Computed from `company_areas` |

#### Group F — Sparse / Pipeline Tables (area_id present, no urgent migration)

| Table | Rows | Notes |
|---|---|---|
| `ailux_positions` | 2 | Core config rows; `area_id` = classification anchor |
| `drug_combinations` | 3 | Very sparse; no urgent migration need |
| `landscape_briefings` | 1 | Single entry |
| `enrichment_queue` | 6 | Pipeline management |
| `enrichment_runs` | 0 | Empty |
| `intelligence_debt_queue` | 255 | Backlog tracker |
| `validation_tests` | 1059 | Test harness data — area_id for test scoping |
| `competitive_landscapes` | 5 | Has `area_id` but no companion columns; used in mechanism_status context |

---

## 2. Code Audit

### 2.1 disease_areas References in index.html

Total references: **25**. Classification:

| Type | Count | Lines | Status |
|---|---|---|---|
| Static educational HTML (Ontology Audit section) | 12 | ~20641–21004 | **Safe** — static documentation text, no DB interaction |
| Code comments (Session 80 retirement notes) | 9 | ~22716, 22775, 22780, 23616, 23625, 23633, 23644, 23645, 23653 | **Stale but harmless** — say "pending DB FK teardown"; teardown now done. Minor cleanup for a future session. |
| Admin stub rows showing count of 0 | 2 | ~24959, 24972, 24987 | **Safe** — `Promise.resolve({ data: [] })` stubs; `disease_areas: (daRows||[]).length` = 0 |
| Static admin taxonomy reference card | 2 | ~25025, ~25107–25174 | **Safe** — static HTML card; renders correctly with count 0 |

**Zero live DB reads on disease_areas.** The only dynamic reference produces a count of 0 from a stub.

### 2.2 area_id in Live DB Reads

All active `area_id` DB reads fall into two patterns:

**Pattern 1 — Dual-filter (Phase 3 complete):** Four reads use `.or('target_id.in.(...),area_id.in.(...)')` — these are the Phase 3 migration pattern and are correct.
```
line ~3895  loadAreaCatalysts
line ~3931  loadAreaDeals
line ~3974  loadAreaBDActivity
line ~13443 _loadBdIntoModal
```

**Pattern 2 — Direct area_id filter (expected legacy):**
- `drug_areas` reads (~13804, ~10484, ~12458) — the active fallback for il4ra/tslp/ted in `_makeAreaPI`. Intentional until Phase 5 activations.
- `drug_area_scores` reads (~15803, ~15940) — dual-read harness comparisons. Intentional until decommission gate.
- Intelligence/signal reads (intel_areas, research_queue, competitive_signals, company_profiles, discovery_queue) — Group D tables, all legitimate active reads, migration deferred.

**No orphaned or broken reads.** Every `area_id` read hits a table that still exists and has data.

### 2.3 Stale Comment Cleanup (Non-Blocking)

Nine comments in `index.html` still say "pending DB FK teardown" — these are now stale since Session 84 completed the teardown. Examples at lines ~23644, ~23645, ~23679, ~23680, ~23681. These are purely cosmetic and don't affect any behavior. A 5-minute grep-replace in a future cleanup session will remove them.

---

## 3. Ontology Bridge Validation

### 3.1 legacy_area_ontology_map — 11/11 Contexts Present

| legacy_area_id | context_type | context_id | target_id | migration_status |
|---|---|---|---|---|
| atopy | strategic_view | atopy | — | flag_activated |
| autoimmune | strategic_view | autoimmune | — | preserved_curated |
| fcrn | target | fcrn | fcrn | flag_activated |
| ibd | indication | uc | — | flag_activated |
| igf1r | target | igf1r | igf1r | flag_activated |
| il4ra | target | il4ra | il4ra | flag_activated |
| respiratory | strategic_view | respiratory | — | legacy_retained |
| tcell | platform_view | tcell | — | preserved_platform |
| ted | indication | ted | — | flag_activated |
| tl1a | target | tl1a | tl1a | flag_activated |
| tslp | target | tslp | tslp | flag_activated |

**All 11 legacy contexts mapped. Bridge intact.**

### 3.2 Child Data Integrity After CASCADE

The `DROP TABLE ... CASCADE` in Session 84 dropped FK constraints only — no child rows were deleted. Spot-check confirms all area_id data intact:

| Table | Expected | Confirmed |
|---|---|---|
| `drug_areas` | 208 rows across 11 areas | ✅ 208 rows |
| `drug_area_scores` | 212 rows across 11 areas | ✅ 212 rows |
| `catalysts` | 826 rows across 11 areas | ✅ 826 rows |
| `company_areas` | 134 rows across 11 areas | ✅ 134 rows |
| `deals` | 199 rows (6 areas with FK-constrained values) | ✅ 199 rows |
| `intel_areas` | 18 rows across 5 areas | ✅ 18 rows |
| `research_queue` | 60 rows across 6 areas | ✅ 60 rows |
| `competitive_signals` | 252 rows across 6 areas | ✅ 252 rows |
| `company_profiles` | 137 rows across 11 areas | ✅ 137 rows |

**Zero data loss. CASCADE behavior confirmed correct: dropped constraints, not rows.**

---

## 4. Prioritized Next-Migration List

Ranked by: production impact, migration complexity, and retirement dependency chain.

### P1 — drug_area_scores (retirement, not migration)

**Type:** Legacy archive table  
**Rows:** 212  
**Current role:** Dual-read harness baseline — `_runPhase4B*DualRead` functions compare DCS `overlap` tiers against DAS as ground truth  
**Blocker:** 5 dual-read harnesses must log 30+ clean matching days before decommission  
**Decommission gate:** 2026-06-27 (earliest)  
**What to do:** Review harness logs at gate date. If all 5 show clean matches for 30+ days, decommission harnesses and drop table.  
**Code to remove:** 5 `_runPhase4B*DualRead` functions + their callers

### P2 — drug_areas (retirement, not migration)

**Type:** Legacy biological drug-area mapping table  
**Rows:** 208  
**Current role:** Active fallback in `_makeAreaPI` for 3 unactivated areas (il4ra, tslp, ted). Lines ~13804, ~10484, ~12458.  
**Blocker:** Phase 5 activations for il4ra, tslp, ted — each requires pre-flight audit + runtime comparison (see `project_phase5_inflection.md`)  
**What to do:** Activate each of the 3 areas, then drop table  
**Sequence:** il4ra → tslp → ted (or parallel) → verify all 3 clean → drop drug_areas

### P3 — intel_areas (migration)

**Type:** Intel-to-area join table  
**Rows:** 18  
**Current role:** Join table linking intel items to their area context (`intel_id → area_id`)  
**Read locations:** line ~3145 (select), line ~3847 (filter)  
**Migration path:** 
1. Add `target_id` column to `intel_areas`
2. Backfill from `legacy_area_ontology_map` (18 rows → trivial)
3. Update reads to dual-filter or replace with `intel_target_links` table (already exists in schema)
4. Deprecate `area_id` in `intel_areas`

**Note:** `intel_target_links` table already exists (15 rows per schema). This migration may be a simple data merge + read swap rather than an ontology column add.  
**Complexity:** Low  
**Dependency:** None

### P4 — research_queue (migration)

**Type:** Research task queue, scoped by area  
**Rows:** 60  
**Current role:** Research backlog items, each tagged to an area (lines ~4164, ~4181)  
**Migration path:**
1. Add `target_id` column to `research_queue`
2. Backfill from `legacy_area_ontology_map`
3. Update reads to accept both `area_id` and `target_id`
4. New items use `target_id`; `area_id` becomes historical

**Complexity:** Low  
**Dependency:** None

### P5 — competitive_signals (migration)

**Type:** Competitive intelligence signal store  
**Rows:** 252  
**Current role:** Signals tagged by area; read at line ~13182 in discovery_queue view  
**Migration path:** Add `target_id` + `indication_id`, backfill, dual-filter reads  
**Complexity:** Medium (252 rows; need to map `area_id` values correctly for multi-indication areas like `igf1r` vs `ted`)  
**Dependency:** None

### P6 — company_profiles (migration)

**Type:** Per-company per-area profile summaries  
**Rows:** 137  
**Current role:** Company profile text per area; read in company card modal (lines ~3156, ~4100, ~10565)  
**Migration path:** Add `therapeutic_area_id`, backfill, update reads  
**Complexity:** Medium (company card modal logic is non-trivial)  
**Dependency:** None

### P7 — discovery_queue (migration, lower urgency)

**Type:** BD opportunity queue  
**Rows:** 64  
**Current role:** Core intelligence product — `area_id` is primary routing field, drives tab filtering, display, enrichment commands  
**Migration path:** Add `target_id` → update filter reads → update enrichment CLI output  
**Complexity:** Low (64 rows) but high code surface — discovery_queue has its own tab, filter UI, enrichment output, and strategic_value_score  
**Dependency:** None — but consider migrating after P3/P4 to validate the pattern first  
**Note:** Do not rush. discovery_queue is an active product surface. Migration here should be validated carefully.

---

## 5. Summary

### What's Clean

- `disease_areas` is gone, no residual FKs, no broken reads ✅
- All child table data intact after CASCADE ✅
- `legacy_area_ontology_map` complete (11/11) ✅
- All live `area_id` DB reads hit tables that exist and have data ✅
- Zero console errors on live dashboard ✅

### What's Stale (Cosmetic, Non-Blocking)

- 9 code comments in `index.html` still say "pending DB FK teardown" — teardown is done. Minor cleanup, no behavior impact.
- Static HTML in the Ontology Audit section still shows `disease_areas` in architecture diagrams — intentional historical documentation.

### Remaining Legacy Area Structures

| Structure | Tables | Path Forward |
|---|---|---|
| **Active legacy fallback** | `drug_areas` (208 rows) | Phase 5 activations for il4ra/tslp/ted → retire |
| **Archival baseline** | `drug_area_scores` (212 rows) | Decommission dual-read harnesses (gate: 2026-06-27) → retire |
| **Not yet migrated, active** | `intel_areas`, `research_queue`, `competitive_signals`, `company_profiles`, `discovery_queue`, `signals` | Phase 3-style migration (add ontology columns, dual-filter reads, deprecate area_id) |
| **Phase 3 complete** | `catalysts`, `company_areas`, `deals`, `mechanism_status`, `target_areas` | `area_id` retained as legacy key; dual-filter active; no action needed |
| **Permanent** | `area_metadata` | Keep forever |
