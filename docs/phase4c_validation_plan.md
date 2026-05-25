# Phase 4C — Pre-Migration Validation Sprint

**Purpose:** Prove that normalized data produces identical or intentionally improved user outcomes before any Phase 5 source-of-truth switch.

**Success criterion:**
```
Every difference is explainable.
No unexplained differences remain.
```
Not: "Everything matches legacy." The distinction matters — normalized data may correctly surface records that legacy missed, and that is a pass, not a failure.

---

## What Phase 4C Is Not

- Not a dashboard rewrite
- Not a source-of-truth switch
- Not a regression test of legacy behavior

Phase 4C is a **classification sprint**: run every major component in dual-read mode, collect the difference set, explain every entry. Unexplained differences graduate to `entity_consistency_checks`. Explained differences are closed.

---

## Dashboard Components — Ranked by Migration Risk × Business Value

Rankings are independent. A low-risk component with high business value is the best Phase 5 candidate. A high-risk component with lower business value should wait.

---

### Rank 1 — IBD Area Tab (PI Table)

| Dimension | Detail |
|---|---|
| **Risk** | Low |
| **Business value** | High — primary indication area for Ailux's TL1A program |
| **Legacy source** | `drug_areas` WHERE area_id IN ('ibd') + `drug_area_scores` → rendered by `_makeAreaPI()` via `ibd_indication_group_view` |
| **Normalized source** | `drug_indications` WHERE indication_id IN ('uc','cd') |
| **Comparison method** | Phase 4B Path A harness: `_runPhase4BDualRead()` already wired inside `_makeAreaPI()` — fires on IBD tab load, pushes to `window.__MERIDIAN_PHASE4_COMPARE__` |
| **Phase 4B status** | ✅ `compare_pass_oos_adjusted` proven (94.0% raw, 100% adjusted) |
| **Phase 4C work** | Verify OOS classifications still hold post-Wave 2C commit (66 rows). Confirm 6 classified OOS items in entity_consistency_checks are still the complete explanation set. Run one live browser session and call `window.showPhase4Compare()`. |
| **Validation criteria** | `compare_pass_oos_adjusted` confirmed on live production data. All differences traceable to entity_consistency_checks records. |
| **Rollback path** | `_makeAreaPI()` legacy read path remains active. Feature-flag: one `const USE_NORMALIZED_IBD = false` boolean gates the read branch. No data mutation. |
| **Phase 5 candidate** | ✅ Yes — first migration |

---

### Rank 2 — TED Area Tab (igf1r-tshr PI Table)

| Dimension | Detail |
|---|---|
| **Risk** | Low |
| **Business value** | High — batoclimab (Phase 3) is the centerpiece; Ailux's BD target |
| **Legacy source** | `drug_areas` WHERE area_id = 'igf1r' + `drug_area_scores` → `_makeAreaPI(['igf1r'])` |
| **Normalized source** | `drug_indications` WHERE indication_id = 'ted' |
| **Comparison method** | No Phase 4B dual-read wired for igf1r-tshr yet. Phase 4C task: add `_runPhase4BTEDDualRead()` following the IBD Path A pattern. Alternatively, run a one-off Python harness query. |
| **Phase 4B status** | ❌ No dual-read instrumented. Phase 4A correction (batoclimab ted + gmg committed) confirmed ted match at the data layer. |
| **Phase 4C work** | Run igf1r-tshr comparison: `drug_areas WHERE area_id='igf1r'` vs `drug_indications WHERE indication_id='ted'`. Note: these are not identical universes — drug_areas uses target-based membership (IGF-1R), normalized source uses indication (TED). Classify each difference. Expected: batoclimab in both; igf1r-targeted drugs without TED indication (scope difference). |
| **Validation criteria** | All drugs in normalized-only or legacy-only sets have a recorded classification. No drug appears in one set with no explanation. |
| **Rollback path** | Feature-flag on igf1r-tshr tab read branch. TED is one of the smallest area sets — minimal blast radius. |
| **Phase 5 candidate** | ✅ Yes — second migration, after IBD |

---

### Rank 3 — Drug Entity Modal

| Dimension | Detail |
|---|---|
| **Risk** | Low–Medium |
| **Business value** | High — opened on every drug that Kyle investigates; surfaces area membership, targets, indications |
| **Legacy source** | `drug_areas` + `drug_area_scores` (per-drug query in `openDrugEntityModal()`) |
| **Normalized source** | `drug_targets` + `drug_indications` + `trials→trial_indications` |
| **Comparison method** | Phase 4B Path C: `_runPhase4CModalDualRead()` already wired at end of `openDrugEntityModal()`. Fires non-blocking on every modal open. Classification output goes to `window.__MERIDIAN_PHASE4_COMPARE__`. |
| **Phase 4B status** | ✅ Infrastructure deployed. Classification logic implemented. Systematic validation not yet run across representative drug set. |
| **Phase 4C work** | Run 10 representative drugs through the modal. Cover: (1) lm-302 (tl1a, ibd areas — classified cross_table_inconsistency), (2) batoclimab (fcrn, ted, autoimmune), (3) epi-001 (held), (4) upadacitinib (atopy gap — accepted), (5) cizutamig (direct TL1A competitor), (6) a Phase 3 approved drug, (7) a preclinical drug, (8) a drug with multiple target memberships, (9) a drug with only indication membership, (10) a drug with no current drug_indications rows. Classify every gap. Graduate any unclassified gaps to entity_consistency_checks. |
| **Validation criteria** | All 10 test drugs produce a recorded status. Zero `cross_table_inconsistency` entries that lack a classification rationale. |
| **Rollback path** | Feature-flag on modal read branch. Modal already renders from legacy; normalized data is supplementary until switch. |
| **Phase 5 candidate** | ✅ Yes — third migration (after 10-drug classification sprint clears) |

---

### Rank 4 — TL1A Area Tab (PI Table)

| Dimension | Detail |
|---|---|
| **Risk** | Medium |
| **Business value** | Highest — Ailux's primary mechanism; most-used tab |
| **Legacy source** | `drug_areas` WHERE area_id='tl1a' + `drug_area_scores` → `_makeAreaPI(['tl1a'])` via `tl1a_target_view`. Note: TL1A uses a separate `tl1aPI` object (~1700 lines), not the shared `_makeAreaPI` factory. See memory `project_tl1a_unification.md`. |
| **Normalized source** | `drug_targets` WHERE target_id='tl1a' + `ontology_edges` for IBD-adjacent drugs |
| **Comparison method** | Phase 4B Path B: `_runPhase4BTL1ADualRead()` wired inside `_makeAreaPI()`. Legacy=51, norm=35, overlap=34, 17 OOS already classified. |
| **Phase 4B status** | ✅ `compare_pass_oos_adjusted` proven (100% adjusted). |
| **Phase 4C work** | Re-run live. Confirm 17 OOS classifications still hold post-Wave 2C. Verify no new OOS items introduced by any data changes since Phase 4B. Map the 16 legacy-only records to their entity_consistency_checks entries or create new entries if any are unclassified. |
| **Validation criteria** | OOS count stable. All legacy-only records have entity_consistency_checks entries with non-null classification. `compare_pass_oos_adjusted` confirmed on live data. |
| **Rollback path** | More complex than other tabs due to TL1A's separate object. Requires feature-flag inside `tl1aPI` rather than `_makeAreaPI`. Plan this carefully before Phase 5 execution. Do not attempt without mapping the full TL1A render path first. |
| **Phase 5 candidate** | ⚠️ Yes — but fourth, not third. Requires separate TL1A read-path architecture review before migration. |

---

### Rank 5 — TSLP Area Tab

| Dimension | Detail |
|---|---|
| **Risk** | Medium |
| **Business value** | Medium — respiratory target area; TSLP competitors relevant for Ailux respiratory context |
| **Legacy source** | `drug_areas` WHERE area_id='tslp' → `_makeAreaPI(['tslp'])` |
| **Normalized source** | `drug_targets` WHERE target_id='tslp' |
| **Comparison method** | No Phase 4B dual-read instrumented. Phase 4C task: wire `_runPhase4BGenericDualRead('tslp')` following the Path A pattern, or run Python harness query. |
| **Phase 4B status** | ❌ None. |
| **Phase 4C work** | Build and run a TSLP target-view comparison. Count legacy vs normalized. Classify all differences. Expected: some TSLP drugs in legacy that lack a `drug_targets` row (Wave 2B coverage gaps). |
| **Validation criteria** | Every legacy-only record is either (a) a coverage gap queued for Wave 2D, or (b) classified as scope difference. |
| **Rollback path** | Standard `_makeAreaPI()` feature-flag. |
| **Phase 5 candidate** | ⏸ After Wave 2D coverage work confirms TSLP target coverage. |

---

### Rank 6 — IL-4Rα Area Tabs (il4ra-tslp, il4ra-ox40l)

| Dimension | Detail |
|---|---|
| **Risk** | Medium |
| **Business value** | Medium — atopy/AD-relevant; two sub-tabs with different area_id combinations |
| **Legacy source** | `drug_areas` WHERE area_id IN ('il4ra','tslp') or IN ('il4ra') → `_makeAreaPI(['il4ra','tslp'])` and `_makeAreaPI(['il4ra'])` |
| **Normalized source** | `drug_targets` WHERE target_id IN ('il4ra') + `drug_indications` WHERE indication_id='ad' |
| **Comparison method** | No Phase 4B work. Dual-tab structure adds complexity — il4ra-tslp shows union of two areas. |
| **Phase 4C work** | Run comparison for each sub-tab separately. Map upadacitinib atopy_ad_gap (accepted in entity_consistency_checks) as the canonical example. |
| **Validation criteria** | upadacitinib gap explained. No other unexplained absences. |
| **Rollback path** | Feature-flag per sub-tab. |
| **Phase 5 candidate** | ⏸ After Wave 2D atopy backfill (upadacitinib → ad). |

---

### Rank 7 — FcRn Area Tab

| Dimension | Detail |
|---|---|
| **Risk** | High |
| **Business value** | Medium — important FcRn competitive landscape, but normalized coverage is incomplete |
| **Legacy source** | `drug_areas` WHERE area_id='fcrn' → `_makeAreaPI(['fcrn'])` |
| **Normalized source** | `drug_targets` WHERE target_id='fcrn' |
| **Phase 4B status** | ❌ None. Coverage: 57.1% → target 85%+. |
| **Blocker** | Wave 2D FcRn backfill must run first. Do not attempt Phase 4C validation on FcRn until fcrn drug_targets coverage reaches ≥80%. |
| **Phase 5 candidate** | 🚫 Blocked until Wave 2D. |

---

### Rank 8 — ACE Area Tab

| Dimension | Detail |
|---|---|
| **Risk** | High |
| **Business value** | Lower — T-cell reset / CAR-T area; least mature data layer |
| **Legacy source** | `drug_areas` WHERE area_id='tcell' → `_makeAreaPI(['tcell'])` |
| **Normalized source** | `drug_targets` WHERE target_id IN (cd19, bcma, ...) — target mapping for tcell area is not formalized |
| **Phase 4B status** | ❌ None. tcell target ontology is incomplete. |
| **Blocker** | Requires formal target→area mapping for tcell area before any comparison is meaningful. Deferred until after other areas validated. |
| **Phase 5 candidate** | 🚫 Deferred. |

---

### Rank 9 — Landscape Cards (competitive_landscapes)

| Dimension | Detail |
|---|---|
| **Risk** | Medium |
| **Business value** | Medium — landscape_dependency_score and expected competitor counts |
| **Source** | `competitive_landscapes` + `landscape_expected_competitors` — already normalized tables, not drug_areas-dependent. Migration risk is query restructuring, not source switch. |
| **Phase 5 candidate** | ⏸ Not a drug_areas migration. Separate workstream (Track B coverage diagnostics). |

---

## Proposed Phase 5 Migrations — First Three

### Migration 1: IBD Area Tab → Normalized

**Rationale:** compare_pass_oos_adjusted proven in Phase 4B Path A. All OOS items classified. Smallest conceptual change — the dual-read is already running; Phase 5 just promotes the normalized read to primary and silences the legacy read.

**Pre-condition:** Phase 4C verification run (one browser session, `window.showPhase4Compare()` confirms status).

**Implementation:** In `_makeAreaPI()`, add `const USE_NORMALIZED_IBD = true` flag. When true, primary render uses `drug_indications WHERE indication_id IN ('uc','cd')`. Legacy read path remains as commented-out fallback for 30 days.

**Measure:** After switch, count rows rendered. Compare to legacy count from Phase 4B. Delta must be ≤ classified OOS count.

---

### Migration 2: TED Area Tab (igf1r-tshr) → Normalized

**Rationale:** Phase 4A correction proved batoclimab ted match at data layer. TED is the smallest area set — low blast radius. Indication set is simple (just `ted`).

**Pre-condition:** Phase 4C comparison run: `drug_areas WHERE area_id='igf1r'` vs `drug_indications WHERE indication_id='ted'`. All differences classified.

**Implementation:** In `_makeAreaPI(['igf1r'])`, feature-flag primary read to `drug_indications WHERE indication_id='ted'`. Note: the igf1r-tshr tab is for TED (thyroid eye disease) — the indication is ted, the target is igf1r+tshr. Phase 5 migration means the PI table reflects indication evidence, not target membership.

**Measure:** batoclimab present. Row count within expected range. No unexplained additions or removals.

---

### Migration 3: Drug Entity Modal → Normalized

**Rationale:** `_runPhase4CModalDualRead()` already deployed. Infrastructure is live. Phase 5 just promotes the normalized read to the visible render path.

**Pre-condition:** 10-drug classification sprint complete (see Rank 3 Phase 4C work above). Zero unclassified `cross_table_inconsistency` entries in entity_consistency_checks.

**Implementation:** In `openDrugEntityModal()`, add feature-flag to route area membership display from `drug_areas` + `drug_area_scores` to `drug_targets` + `drug_indications`. The modal already fetches both in dual-read mode — Phase 5 swaps which branch drives the render.

**Measure:** For each of the 10 test drugs, modal output matches expected normalized result. No drug disappears from a tab it belongs to.

---

## Entity Consistency Checks — Phase 4C Integration

All unexplained differences discovered during Phase 4C validation **must** graduate to `entity_consistency_checks` before any Phase 5 migration proceeds.

Format:
```sql
INSERT INTO entity_consistency_checks
  (entity_type, entity_id, issue_key, check_type, classification,
   severity, status, review_status, description, proposed_action)
VALUES
  ('drug', '<drug_id>', '<area>_<type>_gap', 'cross_table_inconsistency',
   'needs_manual_review', 'medium', 'open', 'proposed', '...', '...')
ON CONFLICT (entity_type, entity_id, issue_key) DO NOTHING;
```

Phase 5 migration gate: `SELECT count(*) FROM entity_consistency_checks WHERE status IN ('open','in_review') AND severity = 'high'` must return 0 for the specific component being migrated.

---

## Constraints (Carry-Forward from Phase 4B)

1. `ontology_edges` LOCKED at 25 rows — do not unlock until advisor approves post-Phase 4B sign-off
2. `epi-001` HELD — 2 rows in `backfill_preview` as `pending_review`. Do NOT commit without source evidence
3. `gb004 / mechanism_field_conflict` HELD — requires advisor approval before applying
4. `batoclimab → cidp` NOT committed — deferred to Wave 2D FcRn batch
5. No Phase 5 migration on TL1A tab until TL1A read-path architecture is mapped (separate `tl1aPI` object vs `_makeAreaPI` factory)

---

## Phase Sequence (Updated)

| Phase | Name | Status |
|---|---|---|
| Phase 4A | Evidence Reconciliation | ✅ COMPLETE |
| Phase 4B | Dual-Read Validation (IBD, TL1A, Modal) | ✅ COMPLETE |
| Phase 4C | Pre-Migration Classification Sprint | ▶ **CURRENT** |
| Phase 5 | Incremental Source Switch (feature-flagged, per-component) | Blocked until 4C clears |

---

*Generated: 2026-05-25 — Session 53m*
