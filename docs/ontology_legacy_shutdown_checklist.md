# Ontology Legacy Shutdown Checklist
**Produced:** 2026-05-27 (Session 88)  
**Status:** Operational — retirement gates are live, not yet triggered  
**Platform state:** Ontology-native production. All 9 operational tables dual-filter active. `disease_areas` DROPPED (Session 84).

---

## Structure 1 — `drug_area_scores` (212 rows)

**Role:** Archival baseline for the 5 dual-read harnesses. The harnesses compare `drug_area_scores` (DAS) against `drug_competitive_scores` (DCS) on every PI tab load to confirm routing parity during the ontology transition period.

**Dependency type:** Validation infrastructure only — not a data source for any user-facing UI element.

**Kill condition:** All 5 dual-read harnesses show ≥30 consecutive days of clean matching (DAS result = DCS result, no discrepancy logged to console) **AND** today's date ≥ 2026-06-27.

**Blocker:** Hard date gate. Do NOT decommission before 2026-06-27 regardless of harness logs.

**Dependency map — 5 harness functions:**
| Function | Code location | Tab |
|---|---|---|
| `_runPhase4BDualRead` | line ~15881 | PI tab (generic) |
| `_runPhase4BTL1ADualRead` | line ~15982 | TL1A tab |
| `_runPhase4BTEDDualRead` | line ~16121 | TED tab |
| `_runPhase4BAtopyDualRead` | line ~16210 | Atopy tab |
| `_runPhase4BFcRNDualRead` | line ~16319 | FcRn tab |

**Harness call sites:** Lines 13836, 13838, 13840, 13842, 13843, 13845 (inside PI class `onEnter`)

**DAS reads inside harness functions:** Lines 15901, 16038, 16134, 16240, 16333 — all `.eq('area_id', ...)` reads against `drug_area_scores`. These are intentional and must NOT be changed until decommission.

**DAS reads in OEX matrix:** Lines 24089, 24118, 24370, 24441 — these are the scoring display in the Ontology Explorer matrix. Also intentional, also gate-blocked.

**Safe retirement sequence (after 2026-06-27, if harnesses clean):**
1. Verify harness logs: search console history for any DAS/DCS mismatch warnings
2. Remove the 5 harness function definitions (~lines 15881–16380)
3. Remove the 6 harness call sites from PI class `onEnter` (~lines 13836–13845)
4. Remove DAS reads from OEX matrix (~lines 24089, 24118, 24370, 24441)
5. Run in Supabase: `DROP TABLE public.drug_area_scores;`
6. Validate: all 6 PI tabs load clean, OEX matrix renders without DAS column, zero console errors
7. Update `area_metadata` row for `drug_area_scores` → `status='dropped'`

---

## Structure 2 — `drug_areas` (208 rows)

**Role:** Active fallback source in `_makeAreaPI` for three areas that have NOT yet completed Phase 5 activation: **il4ra**, **tslp**, **ted**. These three areas still read biological pipeline data (drugs + companies) from `drug_areas` rather than from `drug_targets` + `drug_indications`.

**Dependency type:** Active production data source for il4ra/tslp/ted PI tabs.

**Kill conditions (per area, sequential):**
- il4ra: Phase 5 pre-flight passes + source swap validated in runtime comparison + `useUnifiedIL4RA` flag set true → il4ra rows removable
- tslp: same pattern → tslp rows removable
- ted: same pattern → ted rows removable
- Full table drop: all 3 activations complete + zero remaining reads

**Pre-flight audit required before any activation:**
1. Run: `SELECT da.area_id, COUNT(*) FROM drug_areas da GROUP BY da.area_id` — baseline row counts
2. Run: `SELECT dt.target_id, COUNT(DISTINCT dt.drug_id) FROM drug_targets dt WHERE dt.target_id = '{area}' GROUP BY dt.target_id` — ontology count
3. Classify each `drug_areas` row for the target area as:
   - **redirect** — drug exists in `drug_targets` with matching `target_id`; safe to cut over
   - **preserve** — drug exists only in `drug_areas`; needs `drug_targets` row before activation
   - **new** — drug not in `drug_targets` at all; new data entry required
4. Resolve all **preserve** + **new** rows before flipping activation flag

**Code location:** `_makeAreaPI` function — reads `drug_areas` via `.eq('area_id', '{area}')` at lines ~4100, 4181 (legacy `loadAreaDrugs`), 10581, 13901, 13902, 14145

**Safe retirement sequence (per area, post-validation):**
1. Complete pre-flight audit (classify all rows)
2. Backfill `drug_targets` / `drug_indications` for any "preserve" rows
3. Run runtime comparison: enable `useUnifiedX = true` in test, compare drug count before/after
4. Confirm match → flag stays true in production
5. After all 3 areas activated: audit remaining `drug_areas` reads in code
6. Run: `DROP TABLE public.drug_areas;`
7. Update `area_metadata` row → `status='dropped'`

---

## Structure 3 — `area_id` fallback columns (all 9 tables)

**Role:** Retained legacy routing key. The dual-filter pattern reads `target_id` as primary; if `target_id` is NULL (which happens for `tcell`, `ibd`, `ted`, `atopy`, `autoimmune`, `respiratory` contexts where `legacy_area_ontology_map` maps these to NULL target_id), the query falls through to the `area_id` match.

**Dependency type:** Active fallback — currently serving real query traffic for 6 non-target contexts.

**Kill conditions:**
- `area_id` can be deprecated on a per-table basis only after all rows in that table have either:
  (a) a non-NULL `target_id` (meaning the non-target contexts have been migrated to a proper indication_id / strategic_view_id routing system), OR
  (b) confirmed stable production traffic for ≥30 days with zero fallback hits
- Full deprecation requires Phase 5+ activation of non-target contexts (tcell, ibd, ted, atopy, autoimmune, respiratory) — this is a multi-session architecture project, not imminent

**Current fallback coverage by table:**
| Table | Fallback contexts | Rows using area_id fallback |
|---|---|---|
| catalysts | atopy, autoimmune, ibd, respiratory, tcell, ted | ~140 rows (17%) |
| company_areas | atopy, autoimmune, ibd, respiratory, tcell, ted | ~79 rows (59%) |
| company_profiles | atopy, autoimmune, ibd, respiratory, tcell, ted | ~73 rows (53%) |
| competitive_signals | tcell | ~30 rows (12%) |
| deals | tcell | ~40 rows (20%) |
| discovery_queue | tcell | ~8 rows (13%) |
| intel_areas | tcell | ~3 rows (17%) |
| research_queue | tcell | ~7 rows (12%) |
| signals | n/a — area_id never populated | 0 rows |

**Outstanding code flips (low urgency — works correctly today):**
- `catalysts` reads in company modal: lines 10476, 10500 — still `.eq('area_id', ...)`; safe because `catalysts.area_id` populated; flip in future cleanup session
- `catalysts` read in OEX card: line 14110 — same situation

**Safe retirement sequence (future, no rush):**
1. Design non-target context routing (indication_id for ibd/ted; strategic_view_id for atopy/autoimmune/respiratory; platform_view_id for tcell)
2. Add those FK columns to each table + backfill
3. Update dual-filter reads to use new primary IDs
4. Verify 30+ days with zero `area_id` hits in any context
5. Run `ALTER TABLE ... DROP COLUMN area_id` per table
6. Remove fallback clauses from all dual-filter reads

---

## Summary Timeline

| Gate | Condition | Action |
|---|---|---|
| **2026-06-27** | Hard date — review DAS harnesses | If clean: decommission harnesses + DROP drug_area_scores |
| **Post-il4ra activation** | Phase 5 pre-flight passes | Remove il4ra drug_areas rows from read path |
| **Post-tslp activation** | Phase 5 pre-flight passes | Remove tslp drug_areas rows from read path |
| **Post-ted activation** | Phase 5 pre-flight passes | Remove ted drug_areas rows from read path |
| **All 3 Phase 5 activations done** | All drug_areas reads removed | DROP drug_areas |
| **Future cleanup sprint** | Non-target contexts fully routed through new IDs | DROP area_id columns (all tables) |

---

## What Is Permanent (Never Retire)

| Structure | Reason |
|---|---|
| `legacy_area_ontology_map` | Bridge table — 11 rows mapping legacy area_ids to ontology IDs; required for any future backfill or audit |
| `area_metadata` | Migration tracking — records migration status per table; keep as audit trail |
| `target_id` / `indication_id` / `therapeutic_area_id` / `context_type` columns | These ARE the ontology — they are the canonical routing keys going forward |

---

*Reference: `docs/ontology_stabilization_report.md` for architecture context.*  
*Reference: `docs/ontology_acceleration_sprint_report.md` for Session 87 migration execution log.*
