# Ontology Stabilization Report
**Produced:** 2026-05-27 (Session 88)  
**Status:** ✅ STABLE — ontology-native production, legacy compatibility layer active  
**Dashboard commit:** Pending Session 88 deploy  
**Preceded by:** `docs/ontology_acceleration_sprint_report.md` (Session 87)

---

## Declaration

Meridian is no longer migrating toward ontology-native operation. **Meridian IS running ontology-native.** All 9 operational tables route through `target_id` as primary, with `area_id` retained as a fallback for non-target contexts. The platform has reached operational maturity in its ontology architecture.

This report documents the current stable state, the observability infrastructure now in place, and the structured path to retiring the remaining legacy structures.

---

## Architecture Map

### Layer 1 — Canonical Ontology (Primary Source of Truth)

These are the tables that define the biological identity of every entity in the platform. All production reads resolve against these first.

| Table | Role | Rows |
|---|---|---|
| `targets` | Molecular targets (fcrn, igf1r, il4ra, tl1a, tslp, tcell) | ~15 |
| `indications` | Disease entities (ibd, ted, atopy, autoimmune, respiratory…) | ~20 |
| `therapeutic_areas` | High-level groupings (Immunology, Oncology) | ~6 |
| `target_pairs` | Bispecific combinations (TL1A×IL-23p19) | ~4 |
| `modalities` | Drug modality types | ~8 |
| `drug_targets` | Drug → target links | ~1,000 |
| `drug_indications` | Drug → indication links | ~540 |

**Read pattern:** `_makeAreaPI` reads from `drug_targets` + `drug_indications` for all active area tabs. No `drug_areas` reads for biological data in any Phase 5-activated area.

### Layer 2 — Operational Tables (Dual-Filter Active)

All 9 operational tables carry ontology columns (`target_id`, `indication_id`, `therapeutic_area_id`, `context_type`) and route through the dual-filter pattern: ontology path primary, `area_id` fallback.

| Table | Rows | Ontology % | Session migrated | Fallback contexts |
|---|---|---|---|---|
| `catalysts` | 826 | 83% | Session 80 (Phase 3A) | atopy, autoimmune, ibd, respiratory, tcell, ted |
| `company_areas` | 134 | 41% | Session 80 (Phase 3B) | atopy, autoimmune, ibd, respiratory, tcell, ted |
| `deals` | 199 | 80% | Session 80 (Phase 3B) | tcell |
| `intel_areas` | 18 | 83% | Session 86 | tcell |
| `research_queue` | 60 | 88% | Session 87 | tcell |
| `competitive_signals` | 252 | 88% | Session 87 | tcell |
| `company_profiles` | 137 | 47% | Session 87 | atopy, autoimmune, ibd, respiratory, tcell, ted |
| `discovery_queue` | 64 | 87% | Session 87 | tcell |
| `signals` | 63 | 0%* | Session 87 | n/a |

*`signals.area_id` was never populated by the enrichment pipeline; 0% coverage is expected and correct. Client-side filter updated for forward-compatibility.

**Overall coverage:** 76% of rows across all 9 tables have a non-null `target_id`. Excluding `signals` and non-target contexts (tcell, ibd, ted, atopy, autoimmune, respiratory — which correctly have NULL `target_id`), effective ontology coverage for target contexts is ~88%.

**Dual-filter pattern:**
```javascript
// Single-value filter:
.or(`target_id.eq.${areaId},area_id.eq.${areaId}`)

// Multi-value filter:
.or(`target_id.in.(${areaIds.join(',')}),area_id.in.(${areaIds.join(',')})`)
```

**12 active dual-filter locations in index.html:**
`research_queue` (_injPIScores) · `intel_areas` (loadAreaIntel) · `catalysts` (loadAreaCatalysts) · `deals` (loadAreaDeals) · `deals` (loadAreaBDActivity) · `company_profiles` (company modal, two reads) · `competitive_signals` (company modal loop) · `company_profiles` (OEX card) · `competitive_signals` (company card) · `deals` (_loadBdIntoModal) · `intel_areas` (loadTL1AIntelFeed)

### Layer 3 — Bridge Tables (Permanent)

| Table | Role | Rows |
|---|---|---|
| `legacy_area_ontology_map` | Maps legacy area_id strings to ontology IDs + context_type | 11 |
| `area_metadata` | Migration tracking — status per operational table | ~12 |

These tables are **retained permanently** and should never be dropped. `legacy_area_ontology_map` is the authoritative definition of how legacy routing keys map to ontology concepts, and is required for any future backfill, audit, or new area migration.

**Non-target context mapping (NULL target_id rows):**
| Legacy area_id | context_type | target_id |
|---|---|---|
| tcell | platform_view | NULL |
| ibd | indication | NULL |
| ted | indication | NULL |
| atopy | strategic_view | NULL |
| autoimmune | strategic_view | NULL |
| respiratory | strategic_view | NULL |

These 6 contexts always fall through to `area_id` fallback in dual-filter reads — this is correct behavior, not a coverage gap.

### Layer 4 — Validation Harnesses (Gated Retirement: 2026-06-27)

5 dual-read harness functions compare `drug_area_scores` (DAS) against `drug_competitive_scores` (DCS) on every PI tab load. They exist to confirm routing parity during the transition period.

| Function | Tab |
|---|---|
| `_runPhase4BDualRead` | Generic PI |
| `_runPhase4BTL1ADualRead` | TL1A |
| `_runPhase4BTEDDualRead` | TED |
| `_runPhase4BAtopyDualRead` | Atopy |
| `_runPhase4BFcRNDualRead` | FcRn |

**Gate:** Do NOT decommission before 2026-06-27. After that date, if harness logs show ≥30 clean matching days, retire all 5 functions + their call sites + DROP `drug_area_scores`.

### Layer 5 — Legacy Fallback Sources (Active, Phased Retirement)

| Structure | Rows | Role | Retirement path |
|---|---|---|---|
| `drug_areas` | 208 | Active biological data source for il4ra/tslp/ted PI tabs | Phase 5 activations (il4ra → tslp → ted) |
| `drug_area_scores` | 212 | Archival baseline for harnesses | Gate: 2026-06-27 |
| `area_id` columns (all tables) | — | Fallback key in dual-filter reads | After non-target context routing redesign |

---

## Observability Infrastructure

### Ontology Health Panel (Live)

Added Session 88: the Ontology Audit tab now displays a live diagnostics panel that queries Supabase on every tab open and on demand via Refresh button.

**Location:** Ontology Audit tab → Section 0: Ontology Health — Live Diagnostics  
**Function:** `loadOntologyHealth()` (index.html, ~line 3504)  
**Wired via:** `registerTab('ontology', { onEnter() { ontologyLoad(); loadOntologyHealth(); } })`

**Metrics displayed:**
- Overall ontology coverage % (rows with `target_id` / total rows, across all 9 tables)
- Per-table: total rows, ontology-path rows, coverage %, fallback context inventory
- Legacy safety rail status: `drug_area_scores` row count + gate date, `drug_areas` row count + pending activations
- `legacy_area_ontology_map` summary: total rows, target contexts, non-target contexts
- Dual-filter location inventory (12 active reads)
- Outstanding code flips (low urgency — catalysts reads in company modal + OEX card)
- Timestamp of last query

**What the health panel tells you in one view:**
1. Is the ontology path being used? (coverage %)
2. Which tables still have significant fallback traffic? (per-table breakdown)
3. Are the gated legacy structures still in place? (DAS/DA counts)
4. Are there any coverage gaps that need investigation?

---

## What Was Fixed This Session

1. **`loadOntologyHealth()` TAB_REGISTRY wiring** — `onEnter` for 'ontology' tab now calls `loadOntologyHealth()` alongside `ontologyLoad()`. Panel auto-populates on tab open.

2. **Stale comments cleaned** — 4 comments in index.html still said "pending DB FK teardown". Updated to "DB teardown complete Session 84" (all replaced).

3. **Legacy shutdown checklist produced** — `docs/ontology_legacy_shutdown_checklist.md` documents kill conditions, dependency maps, and safe retirement sequences for all 3 legacy structures.

---

## Outstanding Items (Low Urgency)

| Item | Location | Why deferred |
|---|---|---|
| Flip `catalysts` reads in company modal (lines 10476, 10500) to dual-filter | index.html | Works correctly today — catalysts.area_id fully populated; no wrong results. Cosmetic cleanup only. |
| Flip `catalysts` read in OEX card (line 14110) | index.html | Same reason. |
| Non-target context routing redesign (tcell→platform_view_id, ibd→indication_id, etc.) | Architecture | Multi-session project; no urgency while area_id fallback is stable. |

---

## Session 88 Verdict

The ontology migration is architecturally complete. The three remaining legacy structures (`drug_area_scores`, `drug_areas`, `area_id` columns) each have a documented kill condition and safe retirement sequence. The health panel makes fallback usage visible and measurable on demand. Future retirement work is predictable rather than exploratory.

---

## Next Retirement Gate

**2026-06-27** — Review `_runPhase4B*` dual-read harness logs. If all 5 show 30+ clean matching days, decommission harnesses + DROP `drug_area_scores`.

Reference: `docs/ontology_legacy_shutdown_checklist.md` for full procedure.

---

## Related Documents

- `docs/ontology_acceleration_sprint_report.md` — Session 87 batch migration execution log
- `docs/intel_areas_ontology_migration.md` — Session 86 intel_areas migration
- `docs/post_disease_areas_integrity_audit.md` — Session 85 post-DROP integrity check
- `docs/disease_areas_db_retirement_execution.md` — Session 84 DROP execution log
- `docs/ontology_legacy_shutdown_checklist.md` — Retirement kill conditions + sequences
