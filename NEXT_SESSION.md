# NEXT_SESSION.md — Session 86 Handoff
**Written:** 2026-05-27  
**Last commit:** `2c889eda61e3` (Session 83 — competitive_relevance restored in DCS)  
**Last DB change:** Session 84 — `disease_areas` dropped  
**Last analysis:** Session 85 — post-retirement integrity audit

---

## Session 85 Complete: Ontology Integrity Audit

Post-`disease_areas` audit confirmed clean. Full findings in `docs/post_disease_areas_integrity_audit.md`.

**Key findings:**
- No orphaned reads, no broken joins, no hidden inconsistencies
- `legacy_area_ontology_map` intact: 11/11 contexts mapped
- All child table data intact after CASCADE
- 9 stale comments in `index.html` still say "pending DB FK teardown" — cosmetic only

---

## Prioritized Migration Queue

From the audit. The full classification is in `docs/post_disease_areas_integrity_audit.md`.

| Priority | Table | Rows | Blocker | Action |
|---|---|---|---|---|
| P1 | `drug_area_scores` | 212 | Harness decommission gate **2026-06-27** | Review logs at gate → decommission 5 harnesses → DROP TABLE |
| P2 | `drug_areas` | 208 | Phase 5 activations (il4ra, tslp, ted) | Activate 3 areas → DROP TABLE |
| P3 | `intel_areas` | 18 | None | Add `target_id`, backfill, swap to `intel_target_links` pattern |
| P4 | `research_queue` | 60 | None | Add `target_id`, backfill, dual-filter reads |
| P5 | `competitive_signals` | 252 | None | Add `target_id`+`indication_id`, backfill, dual-filter |
| P6 | `company_profiles` | 137 | None | Add `therapeutic_area_id`, backfill, update modal reads |
| P7 | `discovery_queue` | 64 | None (caution: active product surface) | Add `target_id`, backfill; validate carefully |

**Already Phase 3 migrated (dual-filter active, no action needed):** `catalysts`, `company_areas`, `deals`, `mechanism_status`, `target_areas`

---

## Session 86 Options

### Option A — Stale comment cleanup (5-minute code session)

9 comments in `index.html` still say "pending DB FK teardown". Replace with "DB teardown complete Session 84". No functional impact — purely cosmetic.

Lines: ~22716, 22775, 22780, 23616, 23625, 23633, 23644, 23645, 23653, 23661-23662, 23679-23681.

### Option B — Phase 5 activations: il4ra

Pre-flight audit required before activation (see `project_phase5_inflection.md`). Count/overlap/classify the il4ra drug set in `drug_areas` vs `drug_targets`. If clean match, activate.

This is the first step toward unblocking `drug_areas` retirement (P2).

### Option C — P3 intel_areas migration

Low-complexity migration: 18 rows, add `target_id`, backfill from `legacy_area_ontology_map`, update 2 read locations. `intel_target_links` table already exists — migration may be a simple data merge.

### Option D — Harness log review (not before 2026-06-27)

Do not start this before the gate date. Earliest eligible: **2026-06-27**.

---

## Retirement Status Summary

| Table | Status | Next Step |
|---|---|---|
| `disease_areas` | **✅ RETIRED** | Done |
| `drug_area_scores` | **🟡 Near-ready** | Harness decommission gate: 2026-06-27 |
| `drug_areas` | **🔴 Blocked** | Phase 5 activations: il4ra, tslp, ted |
| `intel_areas` | **🟡 Migration candidate** | P3 — add target_id, swap to intel_target_links |
| `research_queue` | **🟡 Migration candidate** | P4 — add target_id, dual-filter |
| `competitive_signals` | **🟡 Migration candidate** | P5 — medium complexity |
| `company_profiles` | **🟡 Migration candidate** | P6 — medium complexity |
| `discovery_queue` | **🟡 Migration candidate** | P7 — active surface, validate carefully |
| `area_metadata` | **✅ Keep permanently** | Migration tracking system |
| `legacy_area_ontology_map` | **✅ Keep permanently** | Bridge table |

### area_metadata current state

| area_id | retirement_status | Note |
|---|---|---|
| atopy | flag_activated | Phase 3 done |
| fcrn | flag_activated | Phase 3 done |
| igf1r | flag_activated | Phase 3 done |
| tl1a | flag_activated | Phase 3 done |
| ibd | flag_activated | Phase 3 done |
| il4ra | legacy_retained | biological reads still on drug_area_scores pending Phase 5 activation |
| ted | legacy_retained | biological reads still on drug_area_scores pending Phase 5 activation |
| tslp | legacy_retained | biological reads still on drug_area_scores pending Phase 5 activation |
| autoimmune | not_started | Preserved strategic view |
| respiratory | not_started | Preserved strategic view |
| tcell | not_started | Preserved platform view |

---

## Session 86 Constraints

Do NOT:
- Drop `drug_area_scores` or `drug_areas`
- Remove dual-read harnesses before 2026-06-27
- Start Phase 5 activations without a pre-flight audit

---

## Known Good State

- Dashboard: live at GitHub Pages, commit `2c889eda61e3`
- `disease_areas`: **DROPPED from Supabase** (Session 84)
- `drug_competitive_scores`: 253 rows — 166 with `competitive_relevance`, 87 null (enrichment queue)
- `drug_area_scores`: archival only — dual-read harness baseline, no production UI reads
- `drug_areas`: active fallback for il4ra/tslp/ted
- Zero console errors across all tabs
- All stale "pending DB FK teardown" comments: cosmetic cleanup pending (Option A)
