# Phase 4 Comparison Harness — Meridian BD Platform
**Generated:** 2026-05-25 22:10 UTC  
**Mode:** Read-only · No production data modified  
**Script:** `scripts/phase4_compare_legacy_vs_normalized.py`  

---

## Phase 4 Model

> **Phase 4 success = validated parity + justified correction. Not raw parity.**
> Legacy data is the **production baseline**. Normalized data is the **candidate truth layer**.
> The purpose of Phase 4 is not to force normalized output to match legacy output.
> The purpose is to **explain every difference**.

### Area Status

| Status | Icon | Meaning |
|---|---|---|
| match | ✅ | Raw match ≥ 95%. All differences explained. |
| compare_pass_oos_adjusted | 🟢 | Raw% < 95% but adjusted% ≥ 95% after classifying legacy_noise_removed records. Ready for Phase 4 dual-read — NOT Phase 5 migration. |
| acceptable_mismatch | 🟡 | 70–94% match with unresolved extra-legacy. Review normalized_gap entries. |
| needs_rule_adjustment | 🟠 | Gap points to missing alias, incomplete coverage, or scope difference needing a bridge rule. |
| migration_blocker | 🔴 | Do NOT migrate — unclassified extra-legacy records present, or < 40% raw match. |
| not_ready | ⛔ | Fundamental mapping doesn't exist yet. |

### Difference Classifications

Every extra-legacy or extra-normalized record receives one of these classifications:

| Classification | Direction | Meaning | Default Action |
|---|---|---|---|
| `legacy_noise_removed` | extra_legacy | Legacy includes a record normalized correctly excludes. | Do not backfill. Exclude from readiness denominator. |
| `normalized_gap` | extra_legacy | Legacy has a valid record normalized missed. | Backfill or add alias rule. |
| `ontology_scope_difference` | either | Legacy bucket ≠ normalized bucket semantically. | Bridge rule or keep legacy view. |
| `needs_manual_review` | extra_legacy | Evidence insufficient to classify. | Hold for human review. |
| `new_normalized_value` | extra_norm | Normalized found a valid relationship legacy does not have. | Document as improvement. |
| `source_conflict` | either | Record contradicted by drug target, modality, or source evidence. | Flag for Evidence Reconciliation layer. |
| `cross_table_inconsistency` | either | Record disagrees with multiple evidence tables simultaneously. | Flag for Evidence Reconciliation layer. |

**Readiness metric:** `(overlap + legacy_noise_removed) / legacy_count × 100`  
Not raw overlap. Accepted legacy corrections count toward the threshold.

---

## Part 1 — Legacy Area Drug Population Comparison

For each legacy area_id, compare drug populations between legacy and normalized tables.

> **View-type governance (2026-05-25):** Legacy areas are not a uniform ontological category.
> - **Target views** (`tl1a`, `fcrn`, `igf1r`, `tslp`, `il4ra`): normalized via `drug_targets.target_id`
> - **Indication group views** (`ibd`, `atopy`, `respiratory`, `autoimmune`): normalized via `drug_indications.indication_id`
> - **Indication views** (`ted`): normalized via `drug_indications.indication_id`
> - **Platform views** (`tcell`): no clean normalized path yet
>
> Part 1 compares legacy drug populations against `drug_indications` for coverage assessment.
> Part 2 (dashboard function comparisons) uses the **correct view-type-specific normalized path** per area.

Match % = overlap / legacy_count × 100. A low match % means migrating now would silently drop drugs from the dashboard.

### Summary Table

| Legacy Area | View Type | Normalized Indications | Legacy | Norm | Overlap | Raw% | Noise Rmvd | Adj% | Gaps | Scope Diff | NMR | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `tcell` | platform_view | all, multiple_myeloma | 12 | 7 | 0 | 0.0% | — | — | — | 1 | 11 | ⛔ not_ready |
| `autoimmune` | indication_group_view | gmg, cidp, ra, sle, waiha, sjogrens | 25 | 25 | 13 | 52.0% | — | — | 4 | 1 | 7 | 🟠 needs_rule_adjustment |
| `fcrn` | target_view | gmg, cidp, waiha | 7 | 11 | 5 | 71.4% | — | — | 1 | 1 | — | 🟡 acceptable_mismatch |
| `atopy` | indication_group_view | ad, chronic_urticaria | 10 | 19 | 9 | 90.0% | — | — | 1 | — | — | 🟡 acceptable_mismatch |
| `tl1a` | target_view | uc, cd | 51 | 50 | 47 | 92.2% | 3 | 98.0% | — | — | 1 | 🟢 compare_pass_oos_adjusted |
| `ibd` | indication_group_view | uc, cd | 50 | 50 | 47 | 94.0% | 1 | 96.0% | — | — | 2 | 🟢 compare_pass_oos_adjusted |
| `igf1r` | target_view | ted | 9 | 14 | 9 | 100.0% | — | — | — | — | — | ✅ match |
| `il4ra` | target_view | ad, asthma | 9 | 27 | 9 | 100.0% | — | — | — | — | — | ✅ match |
| `respiratory` | indication_group_view | asthma, copd, crswnp | 14 | 17 | 14 | 100.0% | — | — | — | — | — | ✅ match |
| `ted` | indication_view | ted | 12 | 14 | 12 | 100.0% | — | — | — | — | — | ✅ match |
| `tslp` | target_view | asthma, copd, crswnp | 14 | 17 | 14 | 100.0% | — | — | — | — | — | ✅ match |

_Noise Rmvd = legacy_noise_removed · Adj% = adjusted match % · Gaps = normalized_gap · Scope Diff = ontology_scope_difference · NMR = needs_manual_review_

### Detail by Area

#### `tcell` [platform_view] → `all, multiple_myeloma` ⛔ **not_ready**

| Field | Value |
|---|---|
| Legacy drugs (`drug_areas`) | 12 |
| Legacy drugs (`drug_area_scores`) | 12 |
| Normalized drugs (`drug_indications`) | 7 |
| Overlap | 0 |
| Raw match % | 0.0% |
| Extra in legacy only | 12 |
| Extra in normalized only | 7 |
| Normalized trial count (`trial_indications`) | 0 |
| Deals tagged to legacy area | 26 |
| Catalysts tagged to legacy area | 96 |

**Assessment:** Zero overlap — legacy and normalized are pointing at completely different drug populations. Fundamental mapping issue. Do NOT migrate.

**Difference Classification:**

| Drug | Direction | Classification | Recommended Action |
|---|---|---|---|
| `atg-201` (ATG-201) | extra_legacy | `ontology_scope_difference` | Investigate ATG-201 indication; may need new indication node. |
| `caba-201` (CABA-201) | extra_legacy | `needs_manual_review` | Review required — no classification on record. |
| `cizutamig` (Cizutamig) | extra_legacy | `needs_manual_review` | Review required — no classification on record. |
| `cln-978` (CLN-978) | extra_legacy | `needs_manual_review` | Review required — no classification on record. |
| `cnd261` (CND261) | extra_legacy | `needs_manual_review` | Review required — no classification on record. |
| `cnd319` (CND319) | extra_legacy | `needs_manual_review` | Review required — no classification on record. |
| `cnd460` (CND460) | extra_legacy | `needs_manual_review` | Review required — no classification on record. |
| `descartes08` (Descartes-08) | extra_legacy | `needs_manual_review` | Review required — no classification on record. |
| `kt501` (KT501) | extra_legacy | `needs_manual_review` | Review required — no classification on record. |
| `kyv-101` (KYV-101) | extra_legacy | `needs_manual_review` | Review required — no classification on record. |
| `miv-cel` (Miv-cel (mivocabtagene autoleucel)) | extra_legacy | `needs_manual_review` | Review required — no classification on record. |
| `nipocalimab` (Imaavy (nipocalimab)) | extra_legacy | `needs_manual_review` | Review required — no classification on record. |
| `blinatumomab` (Blincyto (blinatumomab), conf=A) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `ciltacabtagene-autoleucel` (Carvykti (ciltacabtagene autoleucel), conf=A) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `daratumumab` (Daratumumab (Darzalex), conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `linvoseltamab` (linvoseltamab, conf=A) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `sim0500` (SIM0500, conf=A) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `teclistamab` (Tecvayli (teclistamab), conf=A) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `tisagenlecleucel` (Kymriah (tisagenlecleucel), conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |

**Notes on extra-legacy records:**
- `atg-201`: ATG-201 is CAR-T targeting GD2; legacy tcell area is a broad dashboard bucket. GD2 targets are not ALL or MM specifically. tcell area lacks a clean indication mapping.
- `caba-201`: Drug `caba-201` is in legacy `tcell` area but absent from normalized. Cause unknown; may be coverage gap, scope difference, or noise.
- `cizutamig`: Drug `cizutamig` is in legacy `tcell` area but absent from normalized. Cause unknown; may be coverage gap, scope difference, or noise.
- `cln-978`: Drug `cln-978` is in legacy `tcell` area but absent from normalized. Cause unknown; may be coverage gap, scope difference, or noise.
- `cnd261`: Drug `cnd261` is in legacy `tcell` area but absent from normalized. Cause unknown; may be coverage gap, scope difference, or noise.
- `cnd319`: Drug `cnd319` is in legacy `tcell` area but absent from normalized. Cause unknown; may be coverage gap, scope difference, or noise.
- `cnd460`: Drug `cnd460` is in legacy `tcell` area but absent from normalized. Cause unknown; may be coverage gap, scope difference, or noise.
- `descartes08`: Drug `descartes08` is in legacy `tcell` area but absent from normalized. Cause unknown; may be coverage gap, scope difference, or noise.
- `kt501`: Drug `kt501` is in legacy `tcell` area but absent from normalized. Cause unknown; may be coverage gap, scope difference, or noise.
- `kyv-101`: Drug `kyv-101` is in legacy `tcell` area but absent from normalized. Cause unknown; may be coverage gap, scope difference, or noise.
- `miv-cel`: Drug `miv-cel` is in legacy `tcell` area but absent from normalized. Cause unknown; may be coverage gap, scope difference, or noise.
- `nipocalimab`: Drug `nipocalimab` is in legacy `tcell` area but absent from normalized. Cause unknown; may be coverage gap, scope difference, or noise.

#### `autoimmune` [indication_group_view] → `gmg, cidp, ra, sle, waiha, sjogrens` 🟠 **needs_rule_adjustment**

| Field | Value |
|---|---|
| Legacy drugs (`drug_areas`) | 25 |
| Legacy drugs (`drug_area_scores`) | 25 |
| Normalized drugs (`drug_indications`) | 25 |
| Overlap | 13 |
| Raw match % | 52.0% |
| Extra in legacy only | 12 |
| Extra in normalized only | 12 |
| Normalized trial count (`trial_indications`) | 59 |
| Deals tagged to legacy area | 0 |
| Catalysts tagged to legacy area | 11 |

**Assessment:** 52.0% raw match. 12 extra-legacy drug(s). Check: (a) normalized_gap → backfill needed, (b) ontology_scope_difference → bridge rule needed, (c) needs_manual_review → hold for review.

**Difference Classification:**

| Drug | Direction | Classification | Recommended Action |
|---|---|---|---|
| `cnd261` (CND261) | extra_legacy | `normalized_gap` | Backfill drug_indications: cnd261 — identify indication. |
| `cnd319` (CND319) | extra_legacy | `normalized_gap` | Backfill drug_indications: cnd319 — identify indication. |
| `cnd460` (CND460) | extra_legacy | `needs_manual_review` | Review required — no classification on record. |
| `imvt-1402` (IMVT-1402) | extra_legacy | `needs_manual_review` | Review required — no classification on record. |
| `iscalimab` (Iscalimab (CFZ533)) | extra_legacy | `normalized_gap` | Backfill drug_indications: iscalimab — confirm indication. |
| `kyv-101` (KYV-101) | extra_legacy | `needs_manual_review` | Review required — no classification on record. |
| `lonigutamab` (lonigutamab) | extra_legacy | `needs_manual_review` | Review required — no classification on record. |
| `ofatumumab` (Kesimpta (ofatumumab)) | extra_legacy | `normalized_gap` | Backfill drug_indications: ofatumumab → gmg. |
| `omalizumab` (Xolair (omalizumab)) | extra_legacy | `ontology_scope_difference` | Exclude from autoimmune drug_indications. |
| `secukinumab` (Cosentyx (secukinumab)) | extra_legacy | `needs_manual_review` | Review required — no classification on record. |
| `sp-1351` (SP-1351) | extra_legacy | `needs_manual_review` | Review required — no classification on record. |
| `tisagenlecleucel` (Kymriah (tisagenlecleucel)) | extra_legacy | `needs_manual_review` | Review required — no classification on record. |
| `adalimumab` (Humira (adalimumab), conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `anifrolumab` (Saphnelo (anifrolumab), conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `belimumab` (Benlysta (belimumab), conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `daratumumab` (Daratumumab (Darzalex), conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `obexelimab` (Obexelimab (ZB002), conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `obinutuzumab` (Gazyva (obinutuzumab), conf=C) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `ravulizumab` (Ravulizumab (Ultomiris), conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `riliprubart` (Riliprubart, conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `rituximab` (Rituxan (rituximab), conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `tocilizumab` (Actemra (tocilizumab), conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `tulisokibart` (Tulisokibart (MK-7240), conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `voclosporin` (Voclosporin (Lupkynis), conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |

**Notes on extra-legacy records:**
- `cnd261`: Wave 2A did not cover CND261; indication unclear, needs classification.
- `cnd319`: Wave 2A did not cover CND319; indication unclear, needs classification.
- `cnd460`: Drug `cnd460` is in legacy `autoimmune` area but absent from normalized. Cause unknown; may be coverage gap, scope difference, or noise.
- `imvt-1402`: Drug `imvt-1402` is in legacy `autoimmune` area but absent from normalized. Cause unknown; may be coverage gap, scope difference, or noise.
- `iscalimab`: Iscalimab (CD40) is gMG-adjacent; needs indication review. Likely gmg or sjogrens.
- `kyv-101`: Drug `kyv-101` is in legacy `autoimmune` area but absent from normalized. Cause unknown; may be coverage gap, scope difference, or noise.
- `lonigutamab`: Drug `lonigutamab` is in legacy `autoimmune` area but absent from normalized. Cause unknown; may be coverage gap, scope difference, or noise.
- `ofatumumab`: Ofatumumab (anti-CD20) has gMG indication; missed in Wave 2A autoimmune backfill.
- `omalizumab`: Omalizumab (anti-IgE) is in autoimmune legacy catch-all; indication is CSU/asthma, not canonical autoimmune. Handled via atopy/tslp areas.
- `secukinumab`: Drug `secukinumab` is in legacy `autoimmune` area but absent from normalized. Cause unknown; may be coverage gap, scope difference, or noise.
- `sp-1351`: Drug `sp-1351` is in legacy `autoimmune` area but absent from normalized. Cause unknown; may be coverage gap, scope difference, or noise.
- `tisagenlecleucel`: Drug `tisagenlecleucel` is in legacy `autoimmune` area but absent from normalized. Cause unknown; may be coverage gap, scope difference, or noise.

#### `fcrn` [target_view] → `gmg, cidp, waiha` 🟡 **acceptable_mismatch**

| Field | Value |
|---|---|
| Legacy drugs (`drug_areas`) | 7 |
| Legacy drugs (`drug_area_scores`) | 7 |
| Normalized drugs (`drug_indications`) | 11 |
| Overlap | 5 |
| Raw match % | 71.4% |
| Extra in legacy only | 2 |
| Extra in normalized only | 6 |
| Normalized trial count (`trial_indications`) | 26 |
| Deals tagged to legacy area | 20 |
| Catalysts tagged to legacy area | 41 |

**Assessment:** 71.4% raw legacy coverage. 2 extra-legacy drug(s) unresolved (normalized_gap or needs_review). 6 extra normalized drugs are expected ontology expansion. Review unresolved extra-legacy list before declaring compare-pass.

**Difference Classification:**

| Drug | Direction | Classification | Recommended Action |
|---|---|---|---|
| `atg-201` (ATG-201) | extra_legacy | `ontology_scope_difference` | Keep atg-201 in legacy tcell view; do not add to drug_indications via fcrn. |
| `imvt-1402` (IMVT-1402) | extra_legacy | `normalized_gap` | Backfill drug_indications: imvt-1402 → gmg, cidp, waiha. |
| `caba-201` (CABA-201, conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `cizutamig` (Cizutamig, conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `descartes08` (Descartes-08, conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `miv-cel` (Miv-cel (mivocabtagene autoleucel), conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `ravulizumab` (Ravulizumab (Ultomiris), conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `riliprubart` (Riliprubart, conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |

**Notes on extra-legacy records:**
- `atg-201`: ATG-201 is a CAR-T targeting GD2; placed in fcrn legacy area incorrectly. Different mechanism entirely.
- `imvt-1402`: IMVT-1402 is FcRn inhibitor in Phase 3 for gMG, CIDP, WAIHA; missed in Wave 2A FcRn backfill.

#### `atopy` [indication_group_view] → `ad, chronic_urticaria` 🟡 **acceptable_mismatch**

| Field | Value |
|---|---|
| Legacy drugs (`drug_areas`) | 10 |
| Legacy drugs (`drug_area_scores`) | 10 |
| Normalized drugs (`drug_indications`) | 19 |
| Overlap | 9 |
| Raw match % | 90.0% |
| Extra in legacy only | 1 |
| Extra in normalized only | 10 |
| Normalized trial count (`trial_indications`) | 50 |
| Deals tagged to legacy area | 0 |
| Catalysts tagged to legacy area | 3 |

**Assessment:** 90.0% raw legacy coverage. 1 extra-legacy drug(s) unresolved (normalized_gap or needs_review). 10 extra normalized drugs are expected ontology expansion. Review unresolved extra-legacy list before declaring compare-pass.

**Difference Classification:**

| Drug | Direction | Classification | Recommended Action |
|---|---|---|---|
| `upadacitinib` (Rinvoq (upadacitinib)) | extra_legacy | `normalized_gap` | Backfill drug_indications: upadacitinib → ad (atopic dermatitis). |
| `abrocitinib` (Cibinqo (abrocitinib), conf=A) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `bsi-045b` (Bosakitug, conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `catalog-49` (IMG-007, conf=A) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `cendakimab` (Cendakimab, conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `ibi333` (IBI333, conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `omalizumab` (Xolair (omalizumab), conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `rocatinlimab` (Rocatinlimab, conf=A) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `ruxolitinib-topical` (Opzelura (ruxolitinib (topical)), conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `win027` (WIN027, conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `zemprocitinib` (zemprocitinib, conf=A) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |

**Notes on extra-legacy records:**
- `upadacitinib`: Upadacitinib has FDA-approved AD indication; missed in Wave 2A backfill.

#### `tl1a` [target_view] → `uc, cd` 🟢 **compare_pass_oos_adjusted**

| Field | Value |
|---|---|
| Legacy drugs (`drug_areas`) | 51 |
| Legacy drugs (`drug_area_scores`) | 51 |
| Normalized drugs (`drug_indications`) | 50 |
| Overlap | 47 |
| Raw match % | 92.2% |
| legacy_noise_removed | 3 (lm-302, sim0500, spy072) |
| Adjusted match % (overlap + noise_removed) / legacy | 98.0% |
| Extra in legacy only | 4 |
| Extra in normalized only | 3 |
| Normalized trial count (`trial_indications`) | 64 |
| Deals tagged to legacy area | 67 |
| Catalysts tagged to legacy area | 384 |

**Assessment:** Raw 92.2% < 95% threshold. Adjusted coverage 98.0% ≥ 95% after accepting 3 legacy_noise_removed record(s) as confirmed corrections (not ontology gaps). Governance rule (2026-05-25): legacy noise is excluded from the migration-readiness denominator. Ready for Phase 4 dual-read validation — NOT Phase 5 migration.

**Difference Classification:**

| Drug | Direction | Classification | Recommended Action |
|---|---|---|---|
| `epi-001` (EPI-001) | extra_legacy | `needs_manual_review` | Review EPI-001 clinical evidence before committing. |
| `lm-302` (LM-302) | extra_legacy | `legacy_noise_removed` | Do not backfill. Exclude from TL1A target-view denominator. |
| `sim0500` (SIM0500) | extra_legacy | `legacy_noise_removed` | Do not backfill. Exclude from TL1A target-view denominator. |
| `spy072` (SPY072) | extra_legacy | `legacy_noise_removed` | Do not backfill. Exclude from readiness denominator. |
| `anti-tl1a-xpf005-arm` (Anti-TL1A (XPF005 arm), conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `risankizumab-lutikizumab-or-trosunilimab` (TARGET-CD (M24-885) (risankizumab + lutikizumab or trosunilimab), conf=A) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `risankizumab-vs-vedolizumab` (risankizumab vs vedolizumab, conf=A) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |

**Notes on extra-legacy records:**
- `epi-001`: Anti-TL1A antibody, preclinical stage. IBD indication unconfirmed; held in backfill_preview as review_required.
- `lm-302`: CLDN18.2 MMAE-ADC for gastric/GEJ cancer. All trials off_target. No TL1A biology. Wrong legacy area assignment.
- `sim0500`: GPRC5D×BCMA×CD3 trispecific for RRMM (multiple myeloma). No TL1A biology. Wrong legacy area assignment.
- `spy072`: TL1A mechanism (correct) but indication is PsA/axSpA (rheumatology). Not a UC/CD indication drug — ontology_scope_difference from IBD view.

#### `ibd` [indication_group_view] → `uc, cd` 🟢 **compare_pass_oos_adjusted**

| Field | Value |
|---|---|
| Legacy drugs (`drug_areas`) | 50 |
| Legacy drugs (`drug_area_scores`) | 50 |
| Normalized drugs (`drug_indications`) | 50 |
| Overlap | 47 |
| Raw match % | 94.0% |
| legacy_noise_removed | 1 (sim0500) |
| Adjusted match % (overlap + noise_removed) / legacy | 96.0% |
| Extra in legacy only | 3 |
| Extra in normalized only | 3 |
| Normalized trial count (`trial_indications`) | 64 |
| Deals tagged to legacy area | 0 |
| Catalysts tagged to legacy area | 18 |

**Assessment:** Raw 94.0% < 95% threshold. Adjusted coverage 96.0% ≥ 95% after accepting 1 legacy_noise_removed record(s) as confirmed corrections (not ontology gaps). Governance rule (2026-05-25): legacy noise is excluded from the migration-readiness denominator. Ready for Phase 4 dual-read validation — NOT Phase 5 migration.

**Difference Classification:**

| Drug | Direction | Classification | Recommended Action |
|---|---|---|---|
| `epi-001` (EPI-001) | extra_legacy | `needs_manual_review` | Review EPI-001 clinical evidence before committing. |
| `sim0500` (SIM0500) | extra_legacy | `legacy_noise_removed` | Do not backfill. Exclude from readiness denominator. |
| `spy072` (SPY072) | extra_legacy | `needs_manual_review` | Review required — no classification on record. |
| `anti-tl1a-xpf005-arm` (Anti-TL1A (XPF005 arm), conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `risankizumab-lutikizumab-or-trosunilimab` (TARGET-CD (M24-885) (risankizumab + lutikizumab or trosunilimab), conf=A) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `risankizumab-vs-vedolizumab` (risankizumab vs vedolizumab, conf=A) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |

**Notes on extra-legacy records:**
- `epi-001`: Same as tl1a/epi-001 above.
- `sim0500`: RRMM trispecific — same curation error as tl1a target-view area. Not an IBD indication drug. Indication is multiple myeloma.
- `spy072`: Drug `spy072` is in legacy `ibd` area but absent from normalized. Cause unknown; may be coverage gap, scope difference, or noise.

#### `igf1r` [target_view] → `ted` ✅ **match**

| Field | Value |
|---|---|
| Legacy drugs (`drug_areas`) | 9 |
| Legacy drugs (`drug_area_scores`) | 9 |
| Normalized drugs (`drug_indications`) | 14 |
| Overlap | 9 |
| Raw match % | 100.0% |
| Extra in legacy only | 0 |
| Extra in normalized only | 5 |
| Normalized trial count (`trial_indications`) | 33 |
| Deals tagged to legacy area | 18 |
| Catalysts tagged to legacy area | 30 |

**Assessment:** 100.0% of legacy drugs represented in normalized. All differences explained or negligible. Extra normalized drugs are genuine ontology expansion — not regressions.

**Difference Classification:**

| Drug | Direction | Classification | Recommended Action |
|---|---|---|---|
| `cizutamig` (Cizutamig, conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `crn12755` (CRN12755, conf=A) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `iscalimab` (Iscalimab (CFZ533), conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `lonigutamab` (lonigutamab, conf=A) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `sp-1351` (SP-1351, conf=A) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |

#### `il4ra` [target_view] → `ad, asthma` ✅ **match**

| Field | Value |
|---|---|
| Legacy drugs (`drug_areas`) | 9 |
| Legacy drugs (`drug_area_scores`) | 9 |
| Normalized drugs (`drug_indications`) | 27 |
| Overlap | 9 |
| Raw match % | 100.0% |
| Extra in legacy only | 0 |
| Extra in normalized only | 18 |
| Normalized trial count (`trial_indications`) | 88 |
| Deals tagged to legacy area | 24 |
| Catalysts tagged to legacy area | 65 |

**Assessment:** 100.0% of legacy drugs represented in normalized. All differences explained or negligible. Extra normalized drugs are genuine ontology expansion — not regressions.

**Difference Classification:**

| Drug | Direction | Classification | Recommended Action |
|---|---|---|---|
| `abrocitinib` (Cibinqo (abrocitinib), conf=A) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `apg333` (APG333, conf=A) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `benralizumab` (Fasenra (benralizumab), conf=A) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `bsi-045b` (Bosakitug, conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `catalog-49` (IMG-007, conf=A) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `cendakimab` (Cendakimab, conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `gb0895` (GB-0895, conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `ibi333` (IBI333, conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `mepolizumab` (Nucala (mepolizumab), conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `omalizumab` (Xolair (omalizumab), conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `qx031n` (QX031N, conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `rocatinlimab` (Rocatinlimab, conf=A) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `ruxolitinib-topical` (Opzelura (ruxolitinib (topical)), conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `tezepelumab` (Tezspire (tezepelumab), conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `tozorakimab` (Tozorakimab, conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `verekitug--upb-101` (Verekitug (UPB-101), conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `win027` (WIN027, conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `zemprocitinib` (zemprocitinib, conf=A) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |

#### `respiratory` [indication_group_view] → `asthma, copd, crswnp` ✅ **match**

| Field | Value |
|---|---|
| Legacy drugs (`drug_areas`) | 14 |
| Legacy drugs (`drug_area_scores`) | 14 |
| Normalized drugs (`drug_indications`) | 17 |
| Overlap | 14 |
| Raw match % | 100.0% |
| Extra in legacy only | 0 |
| Extra in normalized only | 3 |
| Normalized trial count (`trial_indications`) | 66 |
| Deals tagged to legacy area | 0 |
| Catalysts tagged to legacy area | 4 |

**Assessment:** 100.0% of legacy drugs represented in normalized. All differences explained or negligible. Extra normalized drugs are genuine ontology expansion — not regressions.

**Difference Classification:**

| Drug | Direction | Classification | Recommended Action |
|---|---|---|---|
| `ibi333` (IBI333, conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `omalizumab` (Xolair (omalizumab), conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `rademikibart--cbp-201` (Rademikibart (CBP-201), conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |

#### `ted` [indication_view] → `ted` ✅ **match**

| Field | Value |
|---|---|
| Legacy drugs (`drug_areas`) | 12 |
| Legacy drugs (`drug_area_scores`) | 13 |
| Normalized drugs (`drug_indications`) | 14 |
| Overlap | 12 |
| Raw match % | 100.0% |
| Extra in legacy only | 0 |
| Extra in normalized only | 2 |
| Normalized trial count (`trial_indications`) | 33 |
| Deals tagged to legacy area | 0 |
| Catalysts tagged to legacy area | 2 |

**Assessment:** 100.0% of legacy drugs represented in normalized. All differences explained or negligible. Extra normalized drugs are genuine ontology expansion — not regressions.

**Difference Classification:**

| Drug | Direction | Classification | Recommended Action |
|---|---|---|---|
| `cizutamig` (Cizutamig, conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `iscalimab` (Iscalimab (CFZ533), conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |

#### `tslp` [target_view] → `asthma, copd, crswnp` ✅ **match**

| Field | Value |
|---|---|
| Legacy drugs (`drug_areas`) | 14 |
| Legacy drugs (`drug_area_scores`) | 14 |
| Normalized drugs (`drug_indications`) | 17 |
| Overlap | 14 |
| Raw match % | 100.0% |
| Extra in legacy only | 0 |
| Extra in normalized only | 3 |
| Normalized trial count (`trial_indications`) | 66 |
| Deals tagged to legacy area | 28 |
| Catalysts tagged to legacy area | 119 |

**Assessment:** 100.0% of legacy drugs represented in normalized. All differences explained or negligible. Extra normalized drugs are genuine ontology expansion — not regressions.

**Difference Classification:**

| Drug | Direction | Classification | Recommended Action |
|---|---|---|---|
| `ibi333` (IBI333, conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `omalizumab` (Xolair (omalizumab), conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |
| `rademikibart--cbp-201` (Rademikibart (CBP-201), conf=B) | extra_norm | `new_normalized_value` | Document as improvement. No legacy backfill needed. |

---

## Part 2 — High-Risk Dashboard Function Comparisons

For each of the 5 high-risk legacy dashboard paths (from `docs/dashboard_dependency_inventory.md`), this section compares what the legacy path produces vs. what the normalized replacement would produce.

### openDrugEntityModal()  🔴 **migration_blocker**

- **Lines:** 11557–11620
- **Legacy source:** drug_area_scores (competitive positioning)
- **Normalized source:** drug_targets + drug_indications
- **Legacy count:** 107
- **Normalized count:** 143
- **Overlap:** 104
- **Match %:** 97.2%
- **Notes:** drug_area_scores has competitive enrichment data (overlap, rationale, cls) that has no equivalent column in drug_indications/drug_targets. The competitive positioning modal content CANNOT be replaced until drug_area_scores enrichment is migrated to drug_indications. Separate concern from drug population coverage.

### _makeAreaPI() — TL1A target tab [target_view]  🟢 **compare_pass_oos_adjusted**

- **Lines:** 12121–12200
- **Legacy source:** drug_area_scores.area_id = 'tl1a'
- **Normalized source:** drug_targets WHERE target_id = 'tl1a'
- **Legacy count:** 51
- **Normalized count:** 35
- **Overlap:** 34
- **Match %:** 66.7%
- **Notes:** TL1A is a biological TARGET. The legacy tl1a area is a target-view: it groups drugs by TL1A mechanism engagement. Normalized replacement path is drug_targets.target_id = 'tl1a', NOT drug_indications. Do not conflate this with the IBD indication-group view. Legacy TL1A target-view: 51 drugs. Normalized drug_targets (tl1a): 35 drugs. Overlap: 34. Raw coverage: 66.7%. Adjusted: 100.0% after classifying 17 legacy noise record(s). Ready for Phase 4B target-view dual-read validation.

### _makeAreaPI() — IBD indication tab [indication_group_view]  🟢 **compare_pass_oos_adjusted**

- **Lines:** 12121–12200
- **Legacy source:** drug_area_scores.area_id = 'ibd'
- **Normalized source:** drug_indications WHERE indication_id IN ('uc','cd')
- **Legacy count:** 50
- **Normalized count:** 50
- **Overlap:** 47
- **Match %:** 94.0%
- **Notes:** IBD is an INDICATION GROUP (UC + CD). The legacy ibd area is an indication-group-view: it groups drugs by UC/CD disease indication. Normalized replacement path is drug_indications WHERE indication_id IN ('uc','cd'). This is a separate migration path from the TL1A target-view above — do not merge them. Legacy IBD indication-group-view: 50 drugs. Normalized drug_indications (uc+cd): 50 drugs. Overlap: 47. Raw coverage: 94.0%. Adjusted: 96.0% after classifying 1 legacy noise record(s). Ready for Phase 4B indication-group-view dual-read validation.

### loadAreaDeals() / _loadBdIntoModal()  ⛔ **not_ready**

- **Lines:** 3410–3447 / 12063–12091
- **Legacy source:** deals.area_id IN (area_ids) → 6 area buckets
- **Normalized source:** No normalized equivalent — deals not linked to indication_ids
- **Legacy count:** 183
- **Normalized count:** 0
- **Overlap:** 0
- **Match %:** 0.0%
- **Notes:** 183 deals tagged with area_id across fcrn/igf1r/il4ra/tcell/tl1a/tslp. deals table has no indication_id column. No bridge between deals and indication ontology exists. Migration requires: (a) add indication_id FK to deals, or (b) build deals→area_id→indication bridge via ontology_mappings. Do NOT migrate. Deals feed is safe as legacy through Phase 5.

### loadAreaCatalysts()  🟠 **needs_rule_adjustment**

- **Lines:** 3376–3408
- **Legacy source:** catalysts.area_id IN (areas)
- **Normalized source:** trial_indications WHERE indication_id IN (ind_ids)
- **Legacy count:** 773
- **Normalized count:** 301
- **Notes:** 773 catalysts tagged with area_id. trial_indications has 301 rows across 16 indications. These are different record types (catalysts = upcoming readouts, trial_indications = indication-level trial metadata). Catalysts cannot be directly replaced by trial_indications — they contain curated readout dates and notes not in trial_indications. Normalized path should JOIN trials + trial_indications to derive catalyst-like records. Rule needed: area_id → indication_id bridge for catalysts.area_id filter.

### Trial + Signal feed paths (_loadAreaDrugTabs)  🟠 **needs_rule_adjustment**

- **Lines:** 3337–3460 / 3418 / 3460
- **Legacy source:** signals.area_id, trials join via drug_id
- **Normalized source:** trial_indications WHERE indication_id IN (ind_ids)
- **Normalized count:** 301
- **Notes:** trials table has indication_id column but it is NULL for all rows inspected. trial_indications is now populated (319 rows) and provides the canonical trial → indication link. However, the trials table itself does not yet have indication_id backfilled from trial_indications. Migration path: backfill trials.indication_id from trial_indications, then replace area_id filter with indication_id filter. Phase 4 acceptance criteria: trial counts per indication via trial_indications must match or exceed legacy catalyst count per area.

---

## Part 3 — Migration Blockers (Do Not Migrate)

These paths must NOT be migrated until the blocking conditions are resolved:

- ⛔ **`tcell`** (0.0% match): Zero overlap — legacy and normalized are pointing at completely different drug populations. Fundamental mapping issue. Do NOT migrate.
- 🔴 **openDrugEntityModal()**: drug_area_scores has competitive enrichment data (overlap, rationale, cls) that has no equivalent column in drug_indicat...
- ⛔ **loadAreaDeals() / _loadBdIntoModal()**: 183 deals tagged with area_id across fcrn/igf1r/il4ra/tcell/tl1a/tslp. deals table has no indication_id column. No bridg...

---

## Part 4 — Difference Classification Master List (Track B)

All classified differences from `DIFFERENCE_CLASSIFICATIONS`. This replaces the legacy spot-check approach with a formal per-record taxonomy.

### Classified Extra-Legacy Records (drugs in legacy but NOT normalized)

| Area | Drug | Classification | Action Required | Note |
|---|---|---|---|---|
| `atopy` | `upadacitinib` (Rinvoq (upadacitinib)) | `normalized_gap` | Backfill drug_indications: upadacitinib → ad (atopic dermatitis). | Upadacitinib has FDA-approved AD indication; missed in Wave 2A backfill. |
| `autoimmune` | `batoclimab` (Batoclimab (IMVT-1401)) | `ontology_scope_difference` | Exclude from autoimmune drug_indications. | FcRn drug placed in autoimmune legacy catch-all; indication is gMG/CIDP, handled via fcrn … |
| `autoimmune` | `cnd261` (CND261) | `normalized_gap` | Backfill drug_indications: cnd261 — identify indication. | Wave 2A did not cover CND261; indication unclear, needs classification. |
| `autoimmune` | `cnd319` (CND319) | `normalized_gap` | Backfill drug_indications: cnd319 — identify indication. | Wave 2A did not cover CND319; indication unclear, needs classification. |
| `autoimmune` | `iscalimab` (Iscalimab (CFZ533)) | `normalized_gap` | Backfill drug_indications: iscalimab — confirm indication. | Iscalimab (CD40) is gMG-adjacent; needs indication review. Likely gmg or sjogrens. |
| `autoimmune` | `ofatumumab` (Kesimpta (ofatumumab)) | `normalized_gap` | Backfill drug_indications: ofatumumab → gmg. | Ofatumumab (anti-CD20) has gMG indication; missed in Wave 2A autoimmune backfill. |
| `autoimmune` | `omalizumab` (Xolair (omalizumab)) | `ontology_scope_difference` | Exclude from autoimmune drug_indications. | Omalizumab (anti-IgE) is in autoimmune legacy catch-all; indication is CSU/asthma, not can… |
| `fcrn` | `atg-201` (ATG-201) | `ontology_scope_difference` | Keep atg-201 in legacy tcell view; do not add to drug_indications via fcrn. | ATG-201 is a CAR-T targeting GD2; placed in fcrn legacy area incorrectly. Different mechan… |
| `fcrn` | `batoclimab` (Batoclimab (IMVT-1401)) | `ontology_scope_difference` | Keep batoclimab in legacy fcrn view only; do not add to drug_indications via fcrn. | Batoclimab is FcRn-targeting (IgG recycling pathway) but was placed in fcrn legacy area de… |
| `fcrn` | `imvt-1402` (IMVT-1402) | `normalized_gap` | Backfill drug_indications: imvt-1402 → gmg, cidp, waiha. | IMVT-1402 is FcRn inhibitor in Phase 3 for gMG, CIDP, WAIHA; missed in Wave 2A FcRn backfi… |
| `ibd` | `epi-001` (EPI-001) | `needs_manual_review` | Review EPI-001 clinical evidence before committing. | Same as tl1a/epi-001 above. |
| `ibd` | `lm-302` (LM-302) | `legacy_noise_removed` | Do not backfill. Exclude from readiness denominator. | Gastric/GEJ ADC — same curation error as tl1a target-view area. Not an IBD indication drug… |
| `ibd` | `sim0500` (SIM0500) | `legacy_noise_removed` | Do not backfill. Exclude from readiness denominator. | RRMM trispecific — same curation error as tl1a target-view area. Not an IBD indication dru… |
| `igf1r` | `batoclimab` (Batoclimab (IMVT-1401)) | `ontology_scope_difference` | Exclude batoclimab from ted/igf1r drug_indications. | Batoclimab is FcRn mechanism; legacy igf1r area misclassified it. Not a TED drug. |
| `tcell` | `atg-201` (ATG-201) | `ontology_scope_difference` | Investigate ATG-201 indication; may need new indication node. | ATG-201 is CAR-T targeting GD2; legacy tcell area is a broad dashboard bucket. GD2 targets… |
| `ted` | `batoclimab` (Batoclimab (IMVT-1401)) | `ontology_scope_difference` | Exclude from ted drug_indications. | Batoclimab is FcRn mechanism; legacy igf1r area shared with ted. Not a TED drug. |
| `tl1a` | `abbv-382` (ABBV-382) | `ibd_indication_not_tl1a_target` | No action. Correct path: drug_indications uc+cd. | Anti-α4β7 integrin mAb. UC/CD Phase 2. No TL1A biology. |
| `tl1a` | `abbv-668` (ABBV-668) | `ibd_indication_not_tl1a_target` | No action. Correct path: drug_indications cd. | RIPK1 inhibitor. CD Phase 2. No TL1A biology. |
| `tl1a` | `epi-001` (EPI-001) | `needs_manual_review` | Review EPI-001 clinical evidence before committing. | Anti-TL1A antibody, preclinical stage. IBD indication unconfirmed; held in backfill_previe… |
| `tl1a` | `es302` (ES302) | `normalized_gap` | Backfill drug_indications: es302 → uc + cd. | ES302 is an IL-23 inhibitor with UC/CD indication; missed in Wave 2C coverage. |
| `tl1a` | `gb004` (GB004) | `ibd_indication_not_tl1a_target` | No action. Correct path: drug_indications uc. FLAG: fix drugs.mechanism field. | PHD1/HIF-1α stabilizer (oral). UC — TERMINATED. No TL1A biology. DATA ERROR: drugs.mechani… |
| `tl1a` | `golimumab` (Simponi (golimumab)) | `ibd_indication_not_tl1a_target` | No action. Correct path: drug_indications uc. | Anti-TNFα mAb. Approved RA/PsA/AS/UC. No TL1A biology. |
| `tl1a` | `guselkumab` (Tremfya (guselkumab)) | `ibd_indication_not_tl1a_target` | No action. Correct path: drug_indications cd. | Anti-IL-23p19 mAb. Approved PsO/PsA/CD. No TL1A biology. |
| `tl1a` | `guselkumab-golimumab` (guselkumab + golimumab) | `ibd_indication_not_tl1a_target` | No action. Correct path: drug_indications uc. Combo slug — no drug_targets row. | IL-23p19 + TNFα combination. UC Phase 2b/3. No TL1A biology. |
| `tl1a` | `lm-302` (LM-302) | `legacy_noise_removed` | Do not backfill. Exclude from TL1A target-view denominator. | CLDN18.2 MMAE-ADC for gastric/GEJ cancer. All trials off_target. No TL1A biology. Wrong le… |
| `tl1a` | `lutikizumab` (Lutikizumab) | `ibd_indication_not_tl1a_target` | No action. Correct path: drug_indications cd. | Dual IL-1α/β inhibitor. CD Phase 3. No TL1A biology. |
| `tl1a` | `mirikizumab` (Omvoh (mirikizumab)) | `ibd_indication_not_tl1a_target` | No action. Correct path: drug_indications uc+cd. | Anti-IL-23p19 mAb. Approved UC (2023)/CD (2024). No TL1A biology. |
| `tl1a` | `risankizumab` (Skyrizi (risankizumab)) | `ibd_indication_not_tl1a_target` | No action. Correct path: drug_indications cd+uc. | Anti-IL-23p19 mAb. Approved PsO/CD/UC. No TL1A biology. |
| `tl1a` | `sim0500` (SIM0500) | `legacy_noise_removed` | Do not backfill. Exclude from TL1A target-view denominator. | GPRC5D×BCMA×CD3 trispecific for RRMM (multiple myeloma). No TL1A biology. Wrong legacy are… |
| `tl1a` | `spy001` (SPY001) | `ibd_indication_not_tl1a_target` | No action. Correct path: drug_indications uc. | Anti-α4β7 integrin mAb. UC Phase 2. No TL1A biology. |
| `tl1a` | `spy003` (SPY003) | `ibd_indication_not_tl1a_target` | No action. Correct path: drug_indications uc+cd. | Anti-IL-23p19 mAb. UC/CD Phase 2. No TL1A biology. |
| `tl1a` | `spy072` (SPY072) | `legacy_noise_removed` | Do not backfill. Exclude from readiness denominator. | TL1A mechanism (correct) but indication is PsA/axSpA (rheumatology). Not a UC/CD indicatio… |
| `tl1a` | `spy130` (SPY130) | `ibd_indication_not_tl1a_target` | No action. Correct path: drug_indications uc+cd. Combo slug. | SPY001 (α4β7) + SPY003 (IL-23) combination. UC/CD Phase 2. No TL1A biology. |
| `tl1a` | `upadacitinib` (Rinvoq (upadacitinib)) | `ibd_indication_not_tl1a_target` | No action. Correct path: drug_indications uc+cd. Wave 2D: add ad. | JAK1 inhibitor (oral). Approved RA/PsA/AD/UC/CD. No TL1A biology. Also in atopy area — upa… |
| `tl1a` | `ustekinumab` (Stelara (ustekinumab)) | `ibd_indication_not_tl1a_target` | No action. Correct path: drug_indications uc+cd. | Anti-IL-12/23p40 mAb. Approved PsO/PsA/CD/UC. No TL1A biology. |
| `tl1a` | `vedolizumab` (Entyvio (vedolizumab)) | `ibd_indication_not_tl1a_target` | No action. Correct path: drug_indications uc+cd. | Anti-α4β7 integrin mAb. Approved UC/CD. No TL1A biology. Legacy TL1A area used as IBD comp… |

### Unclassified Extra-Legacy Records (needs_manual_review default)

Drugs in legacy areas that have no entry in `DIFFERENCE_CLASSIFICATIONS` and are not in normalized. These are conservative `needs_manual_review` by default.

| Area | Drug | Default Classification |
|---|---|---|
| `autoimmune` | `cnd460` (CND460) | `needs_manual_review` (unclassified) |
| `autoimmune` | `imvt-1402` (IMVT-1402) | `needs_manual_review` (unclassified) |
| `autoimmune` | `kyv-101` (KYV-101) | `needs_manual_review` (unclassified) |
| `autoimmune` | `lonigutamab` (lonigutamab) | `needs_manual_review` (unclassified) |
| `autoimmune` | `secukinumab` (Cosentyx (secukinumab)) | `needs_manual_review` (unclassified) |
| `autoimmune` | `sp-1351` (SP-1351) | `needs_manual_review` (unclassified) |
| `autoimmune` | `tisagenlecleucel` (Kymriah (tisagenlecleucel)) | `needs_manual_review` (unclassified) |
| `ibd` | `spy072` (SPY072) | `needs_manual_review` (unclassified) |
| `tcell` | `caba-201` (CABA-201) | `needs_manual_review` (unclassified) |
| `tcell` | `cizutamig` (Cizutamig) | `needs_manual_review` (unclassified) |
| `tcell` | `cln-978` (CLN-978) | `needs_manual_review` (unclassified) |
| `tcell` | `cnd261` (CND261) | `needs_manual_review` (unclassified) |
| `tcell` | `cnd319` (CND319) | `needs_manual_review` (unclassified) |
| `tcell` | `cnd460` (CND460) | `needs_manual_review` (unclassified) |
| `tcell` | `descartes08` (Descartes-08) | `needs_manual_review` (unclassified) |
| `tcell` | `kt501` (KT501) | `needs_manual_review` (unclassified) |
| `tcell` | `kyv-101` (KYV-101) | `needs_manual_review` (unclassified) |
| `tcell` | `miv-cel` (Miv-cel (mivocabtagene autoleucel)) | `needs_manual_review` (unclassified) |
| `tcell` | `nipocalimab` (Imaavy (nipocalimab)) | `needs_manual_review` (unclassified) |

### Extra-Normalized Records (drugs in normalized but NOT legacy)

These are new valid relationships the ontology found that legacy missed. Default: `new_normalized_value`. No dashboard regression — these are improvements.

| Area | Drug | Classification | Confidence |
|---|---|---|---|
| `atopy` | `abrocitinib` (Cibinqo (abrocitinib)) | `new_normalized_value` | A |
| `atopy` | `bsi-045b` (Bosakitug) | `new_normalized_value` | B |
| `atopy` | `catalog-49` (IMG-007) | `new_normalized_value` | A |
| `atopy` | `cendakimab` (Cendakimab) | `new_normalized_value` | B |
| `atopy` | `ibi333` (IBI333) | `new_normalized_value` | B |
| `atopy` | `omalizumab` (Xolair (omalizumab)) | `new_normalized_value` | B |
| `atopy` | `rocatinlimab` (Rocatinlimab) | `new_normalized_value` | A |
| `atopy` | `ruxolitinib-topical` (Opzelura (ruxolitinib (topical))) | `new_normalized_value` | B |
| `atopy` | `win027` (WIN027) | `new_normalized_value` | B |
| `atopy` | `zemprocitinib` (zemprocitinib) | `new_normalized_value` | A |
| `autoimmune` | `adalimumab` (Humira (adalimumab)) | `new_normalized_value` | B |
| `autoimmune` | `anifrolumab` (Saphnelo (anifrolumab)) | `new_normalized_value` | B |
| `autoimmune` | `belimumab` (Benlysta (belimumab)) | `new_normalized_value` | B |
| `autoimmune` | `daratumumab` (Daratumumab (Darzalex)) | `new_normalized_value` | B |
| `autoimmune` | `obexelimab` (Obexelimab (ZB002)) | `new_normalized_value` | B |
| `autoimmune` | `obinutuzumab` (Gazyva (obinutuzumab)) | `new_normalized_value` | C |
| `autoimmune` | `ravulizumab` (Ravulizumab (Ultomiris)) | `new_normalized_value` | B |
| `autoimmune` | `riliprubart` (Riliprubart) | `new_normalized_value` | B |
| `autoimmune` | `rituximab` (Rituxan (rituximab)) | `new_normalized_value` | B |
| `autoimmune` | `tocilizumab` (Actemra (tocilizumab)) | `new_normalized_value` | B |
| `autoimmune` | `tulisokibart` (Tulisokibart (MK-7240)) | `new_normalized_value` | B |
| `autoimmune` | `voclosporin` (Voclosporin (Lupkynis)) | `new_normalized_value` | B |
| `fcrn` | `caba-201` (CABA-201) | `new_normalized_value` | B |
| `fcrn` | `cizutamig` (Cizutamig) | `new_normalized_value` | B |
| `fcrn` | `descartes08` (Descartes-08) | `new_normalized_value` | B |
| `fcrn` | `miv-cel` (Miv-cel (mivocabtagene autoleucel)) | `new_normalized_value` | B |
| `fcrn` | `ravulizumab` (Ravulizumab (Ultomiris)) | `new_normalized_value` | B |
| `fcrn` | `riliprubart` (Riliprubart) | `new_normalized_value` | B |
| `ibd` | `anti-tl1a-xpf005-arm` (Anti-TL1A (XPF005 arm)) | `new_normalized_value` | B |
| `ibd` | `risankizumab-lutikizumab-or-trosunilimab` (TARGET-CD (M24-885) (risankizumab + lutikizumab or trosunilimab)) | `new_normalized_value` | A |
| `ibd` | `risankizumab-vs-vedolizumab` (risankizumab vs vedolizumab) | `new_normalized_value` | A |
| `igf1r` | `cizutamig` (Cizutamig) | `new_normalized_value` | B |
| `igf1r` | `crn12755` (CRN12755) | `new_normalized_value` | A |
| `igf1r` | `iscalimab` (Iscalimab (CFZ533)) | `new_normalized_value` | B |
| `igf1r` | `lonigutamab` (lonigutamab) | `new_normalized_value` | A |
| `igf1r` | `sp-1351` (SP-1351) | `new_normalized_value` | A |
| `il4ra` | `abrocitinib` (Cibinqo (abrocitinib)) | `new_normalized_value` | A |
| `il4ra` | `apg333` (APG333) | `new_normalized_value` | A |
| `il4ra` | `benralizumab` (Fasenra (benralizumab)) | `new_normalized_value` | A |
| `il4ra` | `bsi-045b` (Bosakitug) | `new_normalized_value` | B |
| `il4ra` | `catalog-49` (IMG-007) | `new_normalized_value` | A |
| `il4ra` | `cendakimab` (Cendakimab) | `new_normalized_value` | B |
| `il4ra` | `gb0895` (GB-0895) | `new_normalized_value` | B |
| `il4ra` | `ibi333` (IBI333) | `new_normalized_value` | B |
| `il4ra` | `mepolizumab` (Nucala (mepolizumab)) | `new_normalized_value` | B |
| `il4ra` | `omalizumab` (Xolair (omalizumab)) | `new_normalized_value` | B |
| `il4ra` | `qx031n` (QX031N) | `new_normalized_value` | B |
| `il4ra` | `rocatinlimab` (Rocatinlimab) | `new_normalized_value` | A |
| `il4ra` | `ruxolitinib-topical` (Opzelura (ruxolitinib (topical))) | `new_normalized_value` | B |
| `il4ra` | `tezepelumab` (Tezspire (tezepelumab)) | `new_normalized_value` | B |
| `il4ra` | `tozorakimab` (Tozorakimab) | `new_normalized_value` | B |
| `il4ra` | `verekitug--upb-101` (Verekitug (UPB-101)) | `new_normalized_value` | B |
| `il4ra` | `win027` (WIN027) | `new_normalized_value` | B |
| `il4ra` | `zemprocitinib` (zemprocitinib) | `new_normalized_value` | A |
| `respiratory` | `ibi333` (IBI333) | `new_normalized_value` | B |
| `respiratory` | `omalizumab` (Xolair (omalizumab)) | `new_normalized_value` | B |
| `respiratory` | `rademikibart--cbp-201` (Rademikibart (CBP-201)) | `new_normalized_value` | B |
| `tcell` | `blinatumomab` (Blincyto (blinatumomab)) | `new_normalized_value` | A |
| `tcell` | `ciltacabtagene-autoleucel` (Carvykti (ciltacabtagene autoleucel)) | `new_normalized_value` | A |
| `tcell` | `daratumumab` (Daratumumab (Darzalex)) | `new_normalized_value` | B |
| `tcell` | `linvoseltamab` (linvoseltamab) | `new_normalized_value` | A |
| `tcell` | `sim0500` (SIM0500) | `new_normalized_value` | A |
| `tcell` | `teclistamab` (Tecvayli (teclistamab)) | `new_normalized_value` | A |
| `tcell` | `tisagenlecleucel` (Kymriah (tisagenlecleucel)) | `new_normalized_value` | B |
| `ted` | `cizutamig` (Cizutamig) | `new_normalized_value` | B |
| `ted` | `iscalimab` (Iscalimab (CFZ533)) | `new_normalized_value` | B |
| `tl1a` | `anti-tl1a-xpf005-arm` (Anti-TL1A (XPF005 arm)) | `new_normalized_value` | B |
| `tl1a` | `risankizumab-lutikizumab-or-trosunilimab` (TARGET-CD (M24-885) (risankizumab + lutikizumab or trosunilimab)) | `new_normalized_value` | A |
| `tl1a` | `risankizumab-vs-vedolizumab` (risankizumab vs vedolizumab) | `new_normalized_value` | A |
| `tslp` | `ibi333` (IBI333) | `new_normalized_value` | B |
| `tslp` | `omalizumab` (Xolair (omalizumab)) | `new_normalized_value` | B |
| `tslp` | `rademikibart--cbp-201` (Rademikibart (CBP-201)) | `new_normalized_value` | B |

---

## Part 4b — Evidence Reconciliation Candidates

These records are flagged as cross-table inconsistencies — they disagree across legacy area assignment, normalized indication, drug target, modality, and/or source evidence. They are the seed set for the Evidence Reconciliation Layer (design: `docs/evidence_reconciliation_layer.md`).

No single table is treated as ground truth here. Truth is evidence-weighted and relationship-validated across all tables.

| Drug | Legacy Area | Conflict Type | Legacy Evidence | Conflicting Evidence | Classification | Proposed Fix | Confidence |
|---|---|---|---|---|---|---|---|
| `lm-302` | tl1a, ibd | `cross_table_inconsistency` | drug_areas: tl1a + ibd | target=CLDN18.2, indication=gastric cancer, modality=ADC, no IBD/TL1A biology | `legacy_noise_removed` | Exclude from normalized IBD/TL1A migration denominator. Do not add to drug_indications. | High |
| `sim0500` | tl1a, ibd | `cross_table_inconsistency` | drug_areas: tl1a + ibd | modality=trispecific, indication=RRMM (multiple myeloma), no IBD/TL1A biology | `legacy_noise_removed` | Exclude from normalized IBD/TL1A migration denominator. Do not add to drug_indications. | High |
| `spy072` | tl1a | `ontology_scope_difference` | drug_areas: tl1a | target=TL1A, indication=PsA/axSpA (rheumatology, not IBD) | `legacy_noise_removed` | Exclude from IBD/TL1A denominator. Could be valid for future rheumatology area. | High |
| `epi-001` | tl1a, ibd | `needs_manual_review` | drug_areas: tl1a + ibd | anti-TL1A preclinical; indication_short absent; no trial evidence for UC/CD yet | `needs_manual_review` | Hold in backfill_preview as review_required until source evidence confirms indication. | Medium |
| `batoclimab` | fcrn, igf1r, autoimmune, ted | `cross_table_inconsistency` | drug_areas: 4 separate legacy areas | target=FcRn (neonatal Fc receptor), mechanism=IgG recycling inhibitor; drug_indications: gmg/cidp/waiha; none of the legacy areas map cleanly to these | `ontology_scope_difference` | Canonical indication is gMG/CIDP/WAIHA via fcrn/autoimmune. Legacy area overcount is a curation artifact; resolve in next fcrn backfill. | High |
| `upadacitinib` | atopy | `normalized_gap` | drug_areas: atopy | FDA-approved for atopic dermatitis (JAK1 inhibitor); absent from drug_indications | `normalized_gap` | Backfill drug_indications: upadacitinib → ad. High-confidence omission. | High |

_Note: This section is populated from `DIFFERENCE_CLASSIFICATIONS` + manual curation. Future versions will be generated automatically from `entity_consistency_checks` table._

---

## Part 5 — Phase 4 Acceptance Criteria

Phase 4 migration is safe when ALL of the following are true:

### Per-Indication Criteria

Readiness metric: `(overlap + legacy_noise_removed) / legacy_count × 100` ≥ 95%

| Indication(s) | Required | Raw% | Noise Rmvd | Adj% | Unresolved Gaps | Criteria Met? |
|---|---|---|---|---|---|---|
| `igf1r` → ted | ≥95% | 100.0% | — | — | — | ✅ raw |
| `il4ra` → ad, asthma | ≥95% | 100.0% | — | — | — | ✅ raw |
| `respiratory` → asthma, copd, crswnp | ≥95% | 100.0% | — | — | — | ✅ raw |
| `ted` → ted | ≥95% | 100.0% | — | — | — | ✅ raw |
| `tslp` → asthma, copd, crswnp | ≥95% | 100.0% | — | — | — | ✅ raw |
| `ibd` → uc, cd | ≥95% | 94.0% | 1 | 96.0% | 2 | 🟢 adjusted |
| `tl1a` → uc, cd | ≥95% | 92.2% | 3 | 98.0% | 1 | 🟢 adjusted |
| `atopy` → ad, chronic_urticaria | ≥95% | 90.0% | — | — | 1 | ❌ |
| `fcrn` → gmg, cidp, waiha | ≥95% | 71.4% | — | — | 1 | ❌ |
| `autoimmune` → gmg, cidp, ra, sle, waiha, sjogrens | ≥95% | 52.0% | — | — | 11 | ❌ |
| `tcell` → all, multiple_myeloma | ≥95% | 0.0% | — | — | 11 | ❌ |

_🟢 adjusted = passes after classifying legacy_noise_removed records as accepted corrections._

### Dashboard Function Criteria

| Function | Blocking Condition | Resolved? |
|---|---|---|
| `openDrugEntityModal()` | drug_indications must have competitive enrichment data (overlap, rationale, cls) | ❌ Not yet — enrichment migration pending |
| `_makeAreaPI()` TL1A **[target_view]** | TL1A target-view: drug_targets.target_id = 'tl1a' coverage ≥ 95% | 🟢 Phase 4 compare pass (adjusted) — ready for target-view dual-read |
| `_makeAreaPI()` IBD **[indication_group_view]** | IBD indication-group: drug_indications UC+CD coverage ≥ 95% | 🟢 Phase 4 compare pass (adjusted) — ready for indication-group dual-read |
| `loadAreaDeals()` | deals.indication_id FK must exist | ❌ Column does not exist |
| `loadAreaCatalysts()` | area_id→indication_id bridge must exist for catalysts | ❌ Bridge not built |
| Trial + Signal feeds | trials.indication_id must be backfilled from trial_indications | ❌ trials.indication_id is NULL |

---

## Phase 4 Overall Status

**Comparison date:** 2026-05-25 22:10 UTC
**Areas compared:** 11
- ✅ match: 5
- 🟢 compare_pass_oos_adjusted: 2
- 🟡 acceptable_mismatch: 2
- 🟠 needs_rule_adjustment: 1
- 🔴 migration_blocker: 0
- ⛔ not_ready: 1

**OOS-adjusted pass areas:** ibd, tl1a  
These areas meet the 95% migration-readiness threshold after removing confirmed OOS drugs from the legacy denominator. Ready for **Phase 4 dual-read validation**. Do NOT advance to Phase 5 (migration) until dual-read comparison confirms zero regressions.

**Verdict:** Phase 4 migration is **NOT YET SAFE** for all areas. Remaining blockers must be resolved before any dashboard query is switched. See Part 3 for specific blocking conditions.

**Next action (Track D):** Build Phase 4B dual-read layer for `_makeAreaPI` and `openDrugEntityModal` — two separate parallel read paths:  
- **TL1A target-view dual-read:** legacy `drug_area_scores.area_id = 'tl1a'` vs normalized `drug_targets WHERE target_id = 'tl1a'`  
- **IBD indication-group dual-read:** legacy `drug_area_scores.area_id = 'ibd'` vs normalized `drug_indications WHERE indication_id IN (''uc'',''cd'')`  
Assert row count parity per path. Log any regressions. Starting point: `docs/phase4_comparison_harness.md` Part 2 and Part 5.
