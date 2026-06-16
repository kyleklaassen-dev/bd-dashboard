# Redirected Entities Inventory
**Generated:** Session 58 — 2026-05-26  
**Status:** Governance sprint output — advisor review required  
**Definition:** An entity is "redirected" when the runtime data source at query time differs from the legacy storage source in `drug_areas`. This includes both **fully activated redirects** (feature flag=true) and **pending redirects** (feature flag=false, code implemented).

---

## Governance Principle

**"No single table is truth."** — Meridian Advisor, Session 58

A redirected entity exists in two states simultaneously: the legacy rows in `drug_areas` (the storage state) and the active query path in a normalized ontology table (the runtime state). The redirect is complete when the feature flag is activated and browser-validated. The legacy rows become shadow records.

---

## Active Redirects (Feature Flag = true, Runtime = Normalized Table)

### RE-001: IBD Tab — Area `ibd`
| Field | Value |
|-------|-------|
| **Redirect activated** | 2026-05-25 (Session 55) |
| **Feature flag** | `FEATURE_FLAGS.useNormalizedIBD = true` (Candidate 1) |
| **Legacy storage** | `drug_areas.area_id = 'ibd'` — 48 rows |
| **Runtime source** | `drug_indications.indication_id IN ('uc', 'cd')` |
| **Tab** | `tl1a` (TAB_AREA_MAP key — ibd is a secondary area_id) |
| **Validation gates** | All 8 passed. Runtime: `ibd_indication_group_view = compare_pass_oos_adjusted` |
| **Count: legacy** | 48 drugs in drug_areas |
| **Count: runtime** | Varies based on drug_indications. uc=44, cd=42 (drug_indications). Drug deduplication produces the tab set. |
| **Dual-read harness** | `_runPhase4BIBDDualRead()` — still present for comparison validation |
| **Shadow row status** | Retained. Safe to delete drug_areas(ibd) rows. drug_area_scores(ibd) retained as scoring provenance. |
| **Retirement blocker** | Phase 4B dual-read harness references `drug_area_scores.area_id = 'ibd'` for comparison. |

---

### RE-002: TED/IGF-1R Tab — Area `igf1r`
| Field | Value |
|-------|-------|
| **Redirect activated** | 2026-05-25 (Session 55) |
| **Feature flag** | `FEATURE_FLAGS.useNormalizedTED = true` (Candidate 2) |
| **Legacy storage** | `drug_areas.area_id = 'igf1r'` — 9 rows |
| **Runtime source** | `drug_indications.indication_id = 'ted'` |
| **Tab** | `igf1r-tshr` (TAB_AREA_MAP: `['igf1r']`) |
| **Validation gates** | All 8 passed. Runtime: `ted_indication_group_view = compare_pass_oos_adjusted` |
| **Count: legacy** | 9 drugs in drug_areas(igf1r) |
| **Count: runtime** | drug_indications(ted) = 13 drugs. Count difference reflects indication-vs-target scope: drug_indications captures all TED drugs; drug_areas(igf1r) captured only IGF-1R targeting drugs. |
| **Conceptual shift** | This redirect changed the query dimension: from **target** (IGF-1R) to **indication** (TED). The tab now shows all TED drugs regardless of mechanism, which is the correct BD perspective. |
| **Dual-read harness** | `_runPhase4BTEDDualRead()` (via atopy dual-read path) — still present |
| **Shadow row status** | Retained. Safe to delete drug_areas(igf1r) rows. |

---

### RE-003: TL1A Tab — Area `tl1a`
| Field | Value |
|-------|-------|
| **Redirect activated** | 2026-05-25 (Session 56) |
| **Feature flag** | `FEATURE_FLAGS.useUnifiedTL1A = true` (Candidate 4) |
| **Legacy storage** | `drug_areas.area_id = 'tl1a'` — 50 rows |
| **Runtime source** | `drug_targets.target_id = 'tl1a'` |
| **Tab** | `tl1a` (TAB_AREA_MAP: `['tl1a', 'ibd']`) |
| **Validation gates** | All 8 passed. Runtime: `tl1a_target_view = compare_pass_oos_adjusted` |
| **Count: legacy** | 50 drugs in drug_areas(tl1a) |
| **Count: runtime** | 34 drugs in drug_targets(tl1a). Difference = 16 scope-diff drugs (TL1A bispecifics whose co-targets place them outside single-target canonical match). adj_match=100%. |
| **Scope diff drugs** | TL1A×IL-23p19 bispecifics, TL1A×α4β7 combos — in drug_areas(tl1a) historically but not in drug_targets(tl1a) single-target rows. They may have multi-target rows in drug_targets. |
| **Dual-read harness** | `_runPhase4BTL1ADualRead()` — still present |
| **Shadow row status** | Retained. Safe to delete drug_areas(tl1a) rows. drug_area_scores(tl1a) retained as scoring provenance. |

---

### RE-004: Drug Entity Modal — Cross-area drug membership
| Field | Value |
|-------|-------|
| **Redirect activated** | 2026-05-25 (Session 55) |
| **Feature flag** | `FEATURE_FLAGS.useNormalizedDrugModal = true` (Candidate 3) |
| **Legacy storage** | `drug_areas.area_id` (membership) + `drug_area_scores` (overlap, rationale, cls, source_url) — fetched per drug_id |
| **Runtime source** | `drug_targets` (target membership) + `drug_indications` (indication membership) — joined to construct area affiliation |
| **Context** | Drug entity modal — when a user clicks a drug to see its full profile |
| **Validation gates** | All 8 passed. Labels clean (IL-23p19, EoE, Chronic Urticaria), confidence display correct (95%, not 9500%), CIDP evidence verified. |
| **Dual-read harness** | `_runPhase4BModalDualRead()` — compares normalized vs legacy area memberships per drug |
| **Shadow row status** | drug_areas rows retained as fallback reference. drug_area_scores still queried in modal for overlap/rationale display (`legacy_sources: ['drug_areas', 'drug_area_scores']`). |
| **Key note** | The modal redirect is the most complex — it constructs area affiliation by joining drug_targets→targets.disease_areas + drug_indications→indications. Some drugs have legacy area memberships (drug_areas) not yet representable via drug_targets/drug_indications. These appear as discrepancies in the dual-read validation. |

---

## Pending Redirects (Feature Flag = false, Code Implemented but Not Activated)

### PR-001: Atopy (TSLP + IL-4Rα) Tabs — Areas `tslp`, `il4ra`, `atopy`
| Field | Value |
|-------|-------|
| **Redirect status** | Pending — C5+C6, `useUnifiedAtopy=false` |
| **Feature flag** | `FEATURE_FLAGS.useUnifiedAtopy = false` (Candidates 5+6, bundled) |
| **Legacy storage** | `drug_areas.area_id IN ('tslp', 'il4ra', 'atopy')` |
| **Runtime source (planned)** | `drug_targets.target_id IN ('il4ra', 'tslp', 'il13', 'il31ra', 'il33', 'jak1', 'ox40l')` |
| **Tabs affected** | `tslp` (TAB_AREA_MAP: `['tslp']`), `il4ra-tslp` (`['il4ra','tslp']`), `il4ra-ox40l` (`['il4ra']`) |
| **Blocking gates** | G6 (zero console errors) + G7 (compare_pass_oos_adjusted) — blocked by GitHub Pages degradation |
| **Data-layer gates** | G1–G5 + G8 confirmed pre-validated. IL-4Rα adj_match=100%, TSLP adj_match=100%. |
| **Deployment state** | Code committed as `089819dd`. GitHub Pages CDN not serving new code (infrastructure degraded). |
| **Why bundled** | `TAB_AREA_MAP['il4ra-tslp'] = ['il4ra','tslp']` — mixed-source read (one area from drug_areas, one from drug_targets) would be architecturally messy. Both must activate together. |
| **Counts** | il4ra: drug_areas=9, drug_targets=5. tslp: drug_areas=14, drug_targets=9. Count differences are scope_diff (bispecifics, combination drugs). |

---

## Planned Redirects (Not Yet Implemented in Code)

### PLR-001: FcRn Tab — Area `fcrn`
| Field | Value |
|-------|-------|
| **Candidate** | C7 |
| **Feature flag** | `FEATURE_FLAGS.useUnifiedFCRN` — NOT YET ADDED to index.html |
| **Legacy storage** | `drug_areas.area_id = 'fcrn'` — 6 rows |
| **Runtime source (planned)** | `drug_targets.target_id = 'fcrn'` — 7 rows (riliprubart is in drug_targets but not drug_areas) |
| **Tab** | `fcrn` (TAB_AREA_MAP: `['fcrn']`) |
| **Pre-flight status** | Audit completed (Session 56). drug_targets(fcrn) has 7 drugs vs drug_areas(fcrn) 6 drugs — riliprubart is the delta. Activation package in `docs/phase5_candidate7_fcrn.md`. |
| **Implementation steps** | Add `useUnifiedFCRN: false` to FEATURE_FLAGS → implement source swap in `_makeAreaPI()` → build `_runPhase4BFCRNDualRead()` → 8-gate validation → activation |
| **Known issue** | `riliprubart` has `drugs.target = 'C1q complement'` (stale). After C7 activation, drugs.target field should be updated to 'FcRn'. |

---

## Redirect Status Summary

| Entity | Legacy Area | Runtime Table | Flag | Status |
|--------|-------------|---------------|------|--------|
| IBD drugs | drug_areas(ibd) | drug_indications(uc,cd) | true | ✅ Active (C1) |
| TED/IGF-1R drugs | drug_areas(igf1r) | drug_indications(ted) | true | ✅ Active (C2) |
| Drug modal areas | drug_areas + drug_area_scores | drug_targets + drug_indications | true | ✅ Active (C3) |
| TL1A drugs | drug_areas(tl1a) | drug_targets(tl1a) | true | ✅ Active (C4) |
| TSLP drugs | drug_areas(tslp) | drug_targets(tslp) | false | ⏳ Pending (C5) |
| IL-4Rα drugs | drug_areas(il4ra) | drug_targets(il4ra,ox40l) | false | ⏳ Pending (C6) |
| FcRn drugs | drug_areas(fcrn) | drug_targets(fcrn) | n/a | 🔲 Planned (C7) |

**Not redirected (no migration path):** autoimmune, respiratory, tcell, ted, atopy (aggregate)

---

## Key Governance Observations

**1. Storage ≠ Runtime creates a two-truth state.** For RE-001 through RE-004, the `drug_areas` table still has rows that disagree with what the dashboard shows. This is intentional (rollback safety) but creates confusion during audits. Any correctness check against drug_areas for ibd/igf1r/tl1a will produce stale results.

**2. Dual-read harness is the integrity bridge.** The Phase 4B dual-read methods (`_runPhase4BIBDDualRead`, `_runPhase4BTL1ADualRead`, etc.) compare legacy vs runtime for every redirect. These must remain in code until the legacy sources are batch-deleted.

**3. drug_area_scores is NOT the same as drug_areas.** All redirects preserve drug_area_scores rows. This is correct: drug_area_scores stores enrichment output (overlap classification, rationale, confidence) — it is not replaced by drug_targets or drug_indications. It is an independent assessment layer.

**4. The modal (C3) is the most complex redirect.** It constructs area affiliation from targets.disease_areas + indications — a join not present in any other redirect. Monitor for drugs whose disease_areas arrays in the targets table are incomplete.

**5. Count gaps in pending redirects (C5/C6) are classified, not unresolved.** tslp: 14→9, il4ra: 9→5. These deltas are scope_diff drugs confirmed by adj_match=100% dual-read. The deltas are not missing data; they are drugs with multi-target biology that fall outside single-target canonical matching.
