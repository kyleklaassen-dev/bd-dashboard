# Drug Areas Disposition Report
**Generated:** Session 58 — 2026-05-26  
**Status:** Governance sprint output — advisor review required  
**Scope:** All 11 area_ids present in `drug_areas` and `drug_area_scores` tables

---

## Purpose

This report defines the long-term fate of every `area_id` currently stored in `drug_areas` and `drug_area_scores`. It answers: Should this area be **Retired**, **Redirected** to a normalized ontology table, or **Preserved** as a curated strategic concept? For each area, it identifies the production query path (how the dashboard actually reads drugs), the normalized replacement (where truth lives), and the retirement risk.

This is the governance record that gates the `drug_areas` batch-retirement sprint described in the Phase 5 inflection point advisory.

---

## Classification Framework

Three lifecycle states:

| State | Meaning |
|-------|---------|
| **Active (Biological)** | Still used as primary drug source; migration planned but not yet active |
| **Redirected** | Feature flag activated — runtime reads normalized table; `drug_areas` rows still exist as legacy shadow |
| **Preserved — Strategic** | Non-biological grouping concept; will never map cleanly to `drug_targets` or `drug_indications`; requires `company_strategic_views` architecture |

Four content categories:

| Category | Definition |
|----------|-----------|
| **Ontology-Biological-Target** | Area = a molecular target → maps to `drug_targets` |
| **Ontology-Biological-Indication** | Area = a disease indication → maps to `drug_indications` |
| **Curated-Strategic** | Area = a thematic grouping (mechanism class, competitive landscape concept) |
| **Curated-Platform** | Area = a modality or platform approach (CAR-T, T-cell bispecifics) |

---

## Area-by-Area Inventory

### 1. `atopy`
| Field | Value |
|-------|-------|
| **Drug count in drug_areas** | 10 |
| **Drug count in drug_area_scores** | 10 |
| **Content category** | Ontology-Biological-Target (multi-target) |
| **Lifecycle state** | Active — migration implemented, flag=false |
| **TAB_AREA_MAP** | Not a direct tab key; queried via `il4ra-tslp` ['il4ra','tslp'] and `tslp` ['tslp'] |
| **Current runtime path** | `drug_areas.area_id = 'atopy'` (legacy) |
| **Normalized replacement** | `drug_targets` — union of: il4ra, tslp, il13, il33, il31ra, il4ra×ox40l, jak1, ox40l |
| **Feature flag** | `useUnifiedAtopy` — C5+C6, currently `false` |
| **Retirement gate** | G6/G7 browser validation → advisor approval → `useUnifiedAtopy=true` |
| **Retirement recommendation** | **Retire after C5/C6 activation** |
| **Key risk** | `atopy` area_id is NOT in TAB_AREA_MAP. The relevant tabs use 'il4ra' and 'tslp' area_ids. The `atopy` rows in drug_areas are the aggregated view; ensure `drug_area_scores` atopy rows are still used for competitive scoring after migration. |

Drugs currently in drug_areas(atopy): tralokinumab, rademikibart--cbp-201, amlitelimab, apg777, lebrikizumab, dupilumab, zumilokibart, nemolizumab, apg279, upadacitinib

---

### 2. `autoimmune`
| Field | Value |
|-------|-------|
| **Drug count in drug_areas** | 25 |
| **Drug count in drug_area_scores** | 25 |
| **Content category** | Curated-Strategic |
| **Lifecycle state** | Preserved — no migration path exists |
| **TAB_AREA_MAP** | Not present — no dashboard tab |
| **Current runtime path** | Not queried by tab system. Used in: `company_areas.area_id`, drug modal area display, research queue, drug_area_scores scoring context |
| **Normalized replacement** | None. `autoimmune` is not a target or indication; it is a thematic grouping spanning FcRn inhibitors (efgartigimod, batoclimab, imvt-1402...), CD20 (ofatumumab), CD19 (tisagenlecleucel, kyv-101...), CD38, CAR-T therapies. No single ontology table can represent this concept. |
| **Retirement recommendation** | **Preserve as Curated-Strategic concept** — migrate to `company_strategic_views` architecture (see Track D). Do NOT retire until replacement architecture is live. |
| **Key risk** | 25 drugs span 8+ biological mechanisms. Retiring this area without a strategic view replacement would break company-level BD portfolio analysis. Several drugs appear in BOTH `autoimmune` AND other areas (batoclimab is also in fcrn and ted; kyv-101 is also in tcell). |

Drugs currently in drug_areas(autoimmune): ianalumab, iscalimab, secukinumab, ofatumumab, batoclimab, imvt-1402, kyv-101, cizutamig, cnd460, omalizumab, tisagenlecleucel, cnd319, caba-201, cln-978, descartes08, cnd261, efgartigimod, kt501, miv-cel, nipocalimab, orilanolimab, rozanolixizumab, atg-201, sp-1351, lonigutamab

---

### 3. `fcrn`
| Field | Value |
|-------|-------|
| **Drug count in drug_areas** | 6 |
| **Drug count in drug_area_scores** | 7 |
| **Content category** | Ontology-Biological-Target |
| **Lifecycle state** | Active — migration prepared (C7), flag not yet implemented |
| **TAB_AREA_MAP** | `'fcrn': ['fcrn']` |
| **Current runtime path** | `drug_areas.area_id = 'fcrn'` |
| **Normalized replacement** | `drug_targets.target_id = 'fcrn'` — 7 drugs confirmed: imvt-1402, orilanolimab, rozanolixizumab, efgartigimod, nipocalimab, batoclimab, riliprubart |
| **Coverage gap** | drug_areas(fcrn) has 6 drugs; drug_targets(fcrn) has 7 drugs. `riliprubart` is in drug_targets but NOT in drug_areas. This is the count discrepancy documented in pre-flight audit C7. |
| **Feature flag** | `useUnifiedFCRN` — C7, NOT YET IMPLEMENTED |
| **Retirement gate** | Implement C7 feature flag → 8-gate browser validation → advisor approval → activate |
| **Retirement recommendation** | **Retire after C7 activation** |
| **Key risk** | `riliprubart` shows `drugs.target = 'C1q complement'` (stale field). After C7 activation, drugs.target should read 'FcRn'. The drugs.target field is a denormalized display field that requires a separate update. |

---

### 4. `ibd`
| Field | Value |
|-------|-------|
| **Drug count in drug_areas** | 48 |
| **Drug count in drug_area_scores** | 49 |
| **Content category** | Ontology-Biological-Indication |
| **Lifecycle state** | **Redirected** — C1 active since 2026-05-25 |
| **TAB_AREA_MAP** | `'tl1a': ['tl1a', 'ibd']` (ibd enables IBD indication path) |
| **Current runtime path** | `drug_indications.indication_id IN ('uc', 'cd')` via `useNormalizedIBD=true` |
| **Legacy path (shadow)** | `drug_areas.area_id = 'ibd'` — rows still exist, not queried by dashboard tab |
| **Normalized replacement** | `drug_indications` (uc + cd) — fully operational |
| **Retirement recommendation** | **Eligible for retirement** — shadow rows can be batch-deleted after stability period |
| **Key risk** | `drug_area_scores.area_id = 'ibd'` still used by Phase 4B dual-read (`_runPhase4BIBDDualRead`) for comparison. Do not delete drug_area_scores(ibd) until dual-read validation is fully retired or replaced. drug_areas(ibd) rows themselves are safe to delete. |

---

### 5. `igf1r`
| Field | Value |
|-------|-------|
| **Drug count in drug_areas** | 9 |
| **Drug count in drug_area_scores** | 9 |
| **Content category** | Ontology-Biological-Target |
| **Lifecycle state** | **Redirected** — C2 active since 2026-05-25 |
| **TAB_AREA_MAP** | `'igf1r-tshr': ['igf1r']` |
| **Current runtime path** | `drug_indications.indication_id = 'ted'` via `useNormalizedTED=true` |
| **Legacy path (shadow)** | `drug_areas.area_id = 'igf1r'` — rows still exist, not queried by tab |
| **Normalized replacement** | `drug_indications` (ted) — fully operational |
| **Note** | C2 redirects from target-based area (`igf1r`) to indication-based source (`ted`). This is a target→indication conceptual shift. The `igf1r` area represents the mechanistic approach; `ted` represents the disease. Both are correct; the normalized path correctly uses disease indication. |
| **Retirement recommendation** | **Eligible for retirement** — shadow rows can be batch-deleted after stability period |
| **Key risk** | Same as ibd: `drug_area_scores.area_id = 'igf1r'` used in Phase 4B dual-read. drug_areas(igf1r) rows are safe to delete; drug_area_scores(igf1r) rows should be preserved until dual-read harness is retired. |

---

### 6. `il4ra`
| Field | Value |
|-------|-------|
| **Drug count in drug_areas** | 9 |
| **Drug count in drug_area_scores** | 9 |
| **Content category** | Ontology-Biological-Target |
| **Lifecycle state** | Active — migration implemented (bundled in C5+C6), flag=false |
| **TAB_AREA_MAP** | `'il4ra-tslp': ['il4ra','tslp']` and `'il4ra-ox40l': ['il4ra']` |
| **Current runtime path** | `drug_areas.area_id = 'il4ra'` (legacy) |
| **Normalized replacement** | `drug_targets.target_id IN ('il4ra', 'ox40l')` — il4ra has 5 drugs, ox40l has 4 |
| **Feature flag** | `useUnifiedAtopy` — C5+C6, currently `false` |
| **Retirement gate** | G6/G7 browser validation → advisor approval → `useUnifiedAtopy=true` |
| **Retirement recommendation** | **Retire after C5/C6 activation** |
| **Key risk** | IL-4Rα×OX40L bispecifics (apg279, apg777) exist as combination targets in drug_targets. The `il4ra-ox40l` tab uses area_id='il4ra' but the full biology includes ox40l. Ensure normalized path returns both pure IL-4Rα drugs and the bispecifics. |

---

### 7. `respiratory`
| Field | Value |
|-------|-------|
| **Drug count in drug_areas** | 14 |
| **Drug count in drug_area_scores** | 14 |
| **Content category** | Curated-Strategic |
| **Lifecycle state** | Preserved — no migration path |
| **TAB_AREA_MAP** | Not present — no dashboard tab |
| **Current runtime path** | Not queried by tab system. Used by: company_areas, drug modal, drug_area_scores scoring context |
| **Normalized replacement** | None. `respiratory` spans TSLP (tezepelumab, bsi-045b), IL-33 (tozorakimab, astegolimab, itepekimab), IL-13 (win027, zumilokibart), JAK (dupilumab COPD context), and IL-5Rα — these are different targets unified only by the disease-organ system (lung/airway). No single `drug_targets` or `drug_indications` query can reconstruct this grouping. |
| **Retirement recommendation** | **Preserve as Curated-Strategic concept** — migrate to `company_strategic_views` architecture |
| **Key risk** | Several drugs appear in both `respiratory` and `tslp`/`atopy` (dupilumab, bsi-045b, win378, apg333, gb0895, qx031n, tezepelumab, win027). The respiratory area is the broader competitive landscape view; tslp/atopy are mechanistic subsets. Retiring `respiratory` without a strategic view replacement loses the cross-mechanism landscape context. |

Drugs: mepolizumab, benralizumab, astegolimab, dupilumab, win378, bsi-045b, apg333, gb0895, itepekimab, qx031n, tezepelumab, tozorakimab, win027, verekitug--upb-101

---

### 8. `tcell`
| Field | Value |
|-------|-------|
| **Drug count in drug_areas** | 11 |
| **Drug count in drug_area_scores** | 12 |
| **Content category** | Curated-Platform (modality/mechanism) |
| **Lifecycle state** | Active — no migration planned |
| **TAB_AREA_MAP** | `'ace': ['tcell']` |
| **Current runtime path** | `drug_areas.area_id = 'tcell'` (active, no flag) |
| **Normalized replacement** | None. `tcell` is a modality concept (CAR-T, T-cell engagers, CD3-bispecifics) not a target or indication. Drugs include: miv-cel, caba-201, kyv-101 (CAR-T), cizutamig, cnd460, kt501, cln-978, descartes08 (CD19/CD3 bispecifics), cnd261, cnd319, atg-201. Their targets span CD19, CD20, BCMA, CD3 — no single target captures the concept. |
| **Retirement recommendation** | **Preserve as Curated-Platform concept** — migrate to `company_platform_views` architecture |
| **Key risk** | This is the only non-redirected tab-connected area. The `ace` tab actively queries `drug_areas.area_id = 'tcell'`. Cannot retire until `company_platform_views` replacement is built and validated with 8-gate protocol. Highest dependency risk of all preserved areas. |

---

### 9. `ted`
| Field | Value |
|-------|-------|
| **Drug count in drug_areas** | 12 |
| **Drug count in drug_area_scores** | 13 |
| **Content category** | Ontology-Biological-Indication (parallel/alias) |
| **Lifecycle state** | Preserved — orphaned alias for `igf1r` |
| **TAB_AREA_MAP** | Not present — no tab uses `ted` area_id directly |
| **Current runtime path** | Not queried by any tab in TAB_AREA_MAP. Queried by: drug_area_scores scoring, company_areas, drug modal overlap display |
| **Normalized replacement** | `drug_indications.indication_id = 'ted'` — same indication used by C2 redirect for the igf1r-tshr tab |
| **Governance note** | `ted` (disease) and `igf1r` (target) are overlapping but distinct. igf1r-tshr tab maps to `igf1r` area_id (9 drugs, target-centric). `ted` area_id has 12 drugs (disease-centric, includes TSHR-targeting drugs teprotumumab, batoclimab not in the igf1r drug_targets set). `drug_areas(ted)` contains: batoclimab, elegrobart, yb-101, linsitinib, teprotumumab, veligrotug, ibi311, oln102, sp-1351, crn12755, lonigutamab, mhb018a — note batoclimab, sp-1351, lonigutamab are also in `autoimmune`. |
| **Retirement recommendation** | **Preserve short-term, evaluate for retirement** — `drug_areas(ted)` rows could theoretically be retired since `drug_indications(ted)` covers the indication. However the 3-drug difference (batoclimab, sp-1351, lonigutamab in ted but not igf1r) requires audit before deletion. |
| **Key risk** | This area straddles two concepts. `igf1r` = IGF-1R target drugs. `ted` = TED indication drugs. They overlap but are not identical. Retiring `ted` from drug_areas without a reconciliation audit could silently drop drugs that are TED-relevant but not IGF-1R targeting. |

---

### 10. `tl1a`
| Field | Value |
|-------|-------|
| **Drug count in drug_areas** | 50 |
| **Drug count in drug_area_scores** | 50 |
| **Content category** | Ontology-Biological-Target |
| **Lifecycle state** | **Redirected** — C4 active since 2026-05-25 |
| **TAB_AREA_MAP** | `'tl1a': ['tl1a', 'ibd']` |
| **Current runtime path** | `drug_targets.target_id = 'tl1a'` via `useUnifiedTL1A=true` |
| **Legacy path (shadow)** | `drug_areas.area_id = 'tl1a'` — 50 rows still exist, not queried by tab |
| **Normalized replacement** | `drug_targets` (tl1a) — 34 drugs. Count difference (50→34) is explained by scope-diff drugs: TL1A combination bispecifics with additional non-TL1A targets that fall outside single-target canonical matching. adj_match=100%. |
| **Retirement recommendation** | **Eligible for retirement** — shadow rows can be batch-deleted after stability period |
| **Key risk** | `drug_area_scores.area_id = 'tl1a'` used in Phase 4B dual-read (`_runPhase4BTL1ADualRead`) for comparison. Same pattern as ibd/igf1r: drug_areas(tl1a) safe to delete; drug_area_scores(tl1a) should be preserved until dual-read harness is retired. |

---

### 11. `tslp`
| Field | Value |
|-------|-------|
| **Drug count in drug_areas** | 14 |
| **Drug count in drug_area_scores** | 14 |
| **Content category** | Ontology-Biological-Target |
| **Lifecycle state** | Active — migration implemented (bundled in C5+C6), flag=false |
| **TAB_AREA_MAP** | `'tslp': ['tslp']` and `'il4ra-tslp': ['il4ra','tslp']` |
| **Current runtime path** | `drug_areas.area_id = 'tslp'` (legacy) |
| **Normalized replacement** | `drug_targets.target_id = 'tslp'` — 9 drugs: ibi333, qx031n, gb0895, catalog-53, apg333, win378, win027, tezepelumab, bsi-045b |
| **Coverage gap** | drug_areas(tslp)=14 drugs vs drug_targets(tslp)=9 drugs. 5 drugs in drug_areas(tslp) not in drug_targets(tslp). These are the scope-diff drugs (likely TSLP bispecifics or respiratory-area overlaps). The `_runPhase4BAtopyDualRead` method handles this via `scope_difference` classification + OOS adjustment. adj_match=100% confirmed G1-G5. |
| **Feature flag** | `useUnifiedAtopy` — C5+C6, currently `false` |
| **Retirement gate** | G6/G7 browser validation → advisor approval → `useUnifiedAtopy=true` |
| **Retirement recommendation** | **Retire after C5/C6 activation** |
| **Key risk** | 5-drug count gap must be fully classified as scope_diff or resolved before retirement. The dual-read harness confirms adj_match=100%, which means all 5 gaps are classified — but the individual drug list should be reviewed to confirm no legitimate TSLP drugs are being excluded. |

---

## Summary Matrix

| area_id | Drugs | Category | State | Retirement Path |
|---------|-------|----------|-------|----------------|
| `atopy` | 10 | Ontology-Target (multi) | Active (C5/C6 pending) | Retire after C5/C6 activation |
| `autoimmune` | 25 | Curated-Strategic | Preserved | Migrate to company_strategic_views |
| `fcrn` | 6 | Ontology-Target | Active (C7 pending) | Retire after C7 activation |
| `ibd` | 48 | Ontology-Indication | **Redirected** (C1 live) | **Eligible for retirement** |
| `igf1r` | 9 | Ontology-Target | **Redirected** (C2 live) | **Eligible for retirement** |
| `il4ra` | 9 | Ontology-Target | Active (C5/C6 pending) | Retire after C5/C6 activation |
| `respiratory` | 14 | Curated-Strategic | Preserved | Migrate to company_strategic_views |
| `tcell` | 11 | Curated-Platform | Active (no migration planned) | Migrate to company_platform_views FIRST |
| `ted` | 12 | Ontology-Indication (alias) | Preserved (orphaned) | Audit → retire after reconciliation |
| `tl1a` | 50 | Ontology-Target | **Redirected** (C4 live) | **Eligible for retirement** |
| `tslp` | 14 | Ontology-Target | Active (C5/C6 pending) | Retire after C5/C6 activation |

**208 total drug_areas rows | 212 total drug_area_scores rows**

---

## Retirement Sequencing

**Phase 5.3 (current):** Complete C5/C6/C7 activations  
→ Retire: atopy, il4ra, tslp (after C5/C6) | fcrn (after C7)

**Phase 5.4:** Batch-retire shadow rows for already-redirected areas  
→ Retire: ibd, igf1r, tl1a drug_areas rows  
→ Preserve: their drug_area_scores rows (still used by Phase 4B dual-read harness)

**Phase 5.5:** Build company_strategic_views + company_platform_views  
→ Migrate: autoimmune, respiratory → company_strategic_views  
→ Migrate: tcell → company_platform_views  
→ Retire drug_areas for these three only after replacement is live and validated

**Phase 5.6:** Resolve orphans  
→ Audit ted vs igf1r overlap, reconcile 3-drug discrepancy  
→ Retire ted from drug_areas once reconciliation is clean

**Final state:** drug_areas table has 0 active rows. drug_area_scores retained as scoring provenance (read-only historical record). Both tables frozen, then archived.
