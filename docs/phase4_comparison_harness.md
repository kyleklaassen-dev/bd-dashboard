# Phase 4 Comparison Harness — Meridian BD Platform
**Generated:** 2026-05-25 20:59 UTC  
**Mode:** Read-only · No production data modified  
**Script:** `scripts/phase4_compare_legacy_vs_normalized.py`  

---

## Status Legend

| Status | Icon | Meaning |
|---|---|---|
| match | ✅ | Legacy and normalized produce equivalent results |
| compare_pass_oos_adjusted | 🟢 | Raw% < 95% but OOS-adjusted% ≥ 95%; confirmed OOS drugs excluded from denominator per governance rule (2026-05-25). Ready for Phase 4 dual-read — NOT Phase 5 migration. |
| acceptable_mismatch | 🟡 | Normalized has more/different but difference is expected and safe |
| needs_rule_adjustment | 🟠 | Gap points to a missing alias, incomplete coverage, or governance rule |
| migration_blocker | 🔴 | Do NOT migrate — normalized source is not ready for production use |
| not_ready | ⛔ | Fundamental mapping doesn't exist yet |

### Governance Rule — OOS Exclusion (2026-05-25)

> **Do not contaminate normalized truth to match legacy noise.**
> If a legacy `drug_areas` record is proven out-of-scope for the mapped indication,
> exclude it from the migration-readiness denominator.
> These are permanent exclusions — do NOT add them to `drug_indications`.

| Area | Confirmed OOS Drug | Reason |
|---|---|---|
| tl1a | `lm-302` | Gastric ADC — placed in tl1a/ibd legacy areas by curation error |
| tl1a | `sim0500` | RRMM trispecific — placed in tl1a/ibd legacy areas by curation error |
| tl1a | `spy072` | TL1A antibody targeting PsA/axSpA (rheumatology, not IBD) |
| ibd | `lm-302` | Same as above |
| ibd | `sim0500` | Same as above |

---

## Part 1 — Indication-Centric Drug Population Comparison

For each legacy area_id, compare drug populations between:
- **Legacy:** `drug_areas.area_id` (what the dashboard currently reads)
- **Normalized:** `drug_indications.indication_id` (ontology-based, post-migration)

Match % = overlap / legacy_count × 100. A low match % means migrating now would silently drop drugs from the dashboard.

### Summary Table

| Legacy Area | Normalized Indications | Legacy | Norm | Overlap | Raw Match% | OOS Excl. | OOS-Adj% | Trials | Status |
|---|---|---|---|---|---|---|---|---|---|
| `tcell` | all, multiple_myeloma | 12 | 7 | 0 | 0.0% | — | — | 0 | ⛔ not_ready |
| `autoimmune` | gmg, cidp, ra, sle, waiha, sjogrens | 25 | 24 | 12 | 48.0% | — | — | 59 | 🟠 needs_rule_adjustment |
| `fcrn` | gmg, cidp, waiha | 7 | 10 | 4 | 57.1% | — | — | 26 | 🟠 needs_rule_adjustment |
| `igf1r` | ted | 9 | 13 | 8 | 88.9% | — | — | 33 | 🟡 acceptable_mismatch |
| `atopy` | ad, chronic_urticaria | 10 | 19 | 9 | 90.0% | — | — | 50 | 🟡 acceptable_mismatch |
| `ted` | ted | 12 | 13 | 11 | 91.7% | — | — | 33 | 🟡 acceptable_mismatch |
| `tl1a` | uc, cd | 51 | 49 | 47 | 92.2% | 3 | 97.9% | 64 | 🟢 compare_pass_oos_adjusted |
| `ibd` | uc, cd | 50 | 49 | 47 | 94.0% | 1 | 95.9% | 64 | 🟢 compare_pass_oos_adjusted |
| `il4ra` | ad, asthma | 9 | 27 | 9 | 100.0% | — | — | 88 | ✅ match |
| `respiratory` | asthma, copd, crswnp | 14 | 17 | 14 | 100.0% | — | — | 66 | ✅ match |
| `tslp` | asthma, copd, crswnp | 14 | 17 | 14 | 100.0% | — | — | 66 | ✅ match |

### Detail by Area

#### `tcell` → `all, multiple_myeloma` ⛔ **not_ready**

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

**Drugs in legacy only (first 15):**
- `atg-201`: ATG-201
- `caba-201`: CABA-201
- `cizutamig`: Cizutamig
- `cln-978`: CLN-978
- `cnd261`: CND261
- `cnd319`: CND319
- `cnd460`: CND460
- `descartes08`: Descartes-08
- `kt501`: KT501
- `kyv-101`: KYV-101
- `miv-cel`: Miv-cel (mivocabtagene autoleucel)
- `nipocalimab`: Imaavy (nipocalimab)

**Drugs in normalized only (first 15):**
- `blinatumomab`: Blincyto (blinatumomab) (conf=A)
- `ciltacabtagene-autoleucel`: Carvykti (ciltacabtagene autoleucel) (conf=A)
- `daratumumab`: Daratumumab (Darzalex) (conf=B)
- `linvoseltamab`: linvoseltamab (conf=A)
- `sim0500`: SIM0500 (conf=A)
- `teclistamab`: Tecvayli (teclistamab) (conf=A)
- `tisagenlecleucel`: Kymriah (tisagenlecleucel) (conf=B)

#### `autoimmune` → `gmg, cidp, ra, sle, waiha, sjogrens` 🟠 **needs_rule_adjustment**

| Field | Value |
|---|---|
| Legacy drugs (`drug_areas`) | 25 |
| Legacy drugs (`drug_area_scores`) | 25 |
| Normalized drugs (`drug_indications`) | 24 |
| Overlap | 12 |
| Raw match % | 48.0% |
| Extra in legacy only | 13 |
| Extra in normalized only | 12 |
| Normalized trial count (`trial_indications`) | 59 |
| Deals tagged to legacy area | 0 |
| Catalysts tagged to legacy area | 11 |

**Assessment:** 48% match. 13 legacy drugs missing from normalized. Check: (a) missing drug_indications rows, (b) alias gaps, (c) broad area straddling multiple indications.

**Drugs in legacy only (first 15):**
- `batoclimab`: Batoclimab (IMVT-1401)
- `cnd261`: CND261
- `cnd319`: CND319
- `cnd460`: CND460
- `imvt-1402`: IMVT-1402
- `iscalimab`: Iscalimab (CFZ533)
- `kyv-101`: KYV-101
- `lonigutamab`: lonigutamab
- `ofatumumab`: Kesimpta (ofatumumab)
- `omalizumab`: Xolair (omalizumab)
- `secukinumab`: Cosentyx (secukinumab)
- `sp-1351`: SP-1351
- `tisagenlecleucel`: Kymriah (tisagenlecleucel)

**Drugs in normalized only (first 15):**
- `adalimumab`: Humira (adalimumab) (conf=B)
- `anifrolumab`: Saphnelo (anifrolumab) (conf=B)
- `belimumab`: Benlysta (belimumab) (conf=B)
- `daratumumab`: Daratumumab (Darzalex) (conf=B)
- `obexelimab`: Obexelimab (ZB002) (conf=B)
- `obinutuzumab`: Gazyva (obinutuzumab) (conf=C)
- `ravulizumab`: Ravulizumab (Ultomiris) (conf=B)
- `riliprubart`: Riliprubart (conf=B)
- `rituximab`: Rituxan (rituximab) (conf=B)
- `tocilizumab`: Actemra (tocilizumab) (conf=B)
- `tulisokibart`: Tulisokibart (MK-7240) (conf=B)
- `voclosporin`: Voclosporin (Lupkynis) (conf=B)

#### `fcrn` → `gmg, cidp, waiha` 🟠 **needs_rule_adjustment**

| Field | Value |
|---|---|
| Legacy drugs (`drug_areas`) | 7 |
| Legacy drugs (`drug_area_scores`) | 7 |
| Normalized drugs (`drug_indications`) | 10 |
| Overlap | 4 |
| Raw match % | 57.1% |
| Extra in legacy only | 3 |
| Extra in normalized only | 6 |
| Normalized trial count (`trial_indications`) | 26 |
| Deals tagged to legacy area | 20 |
| Catalysts tagged to legacy area | 41 |

**Assessment:** 57% match. 3 legacy drugs missing from normalized. Check: (a) missing drug_indications rows, (b) alias gaps, (c) broad area straddling multiple indications.

**Drugs in legacy only (first 15):**
- `atg-201`: ATG-201
- `batoclimab`: Batoclimab (IMVT-1401)
- `imvt-1402`: IMVT-1402

**Drugs in normalized only (first 15):**
- `caba-201`: CABA-201 (conf=B)
- `cizutamig`: Cizutamig (conf=B)
- `descartes08`: Descartes-08 (conf=B)
- `miv-cel`: Miv-cel (mivocabtagene autoleucel) (conf=B)
- `ravulizumab`: Ravulizumab (Ultomiris) (conf=B)
- `riliprubart`: Riliprubart (conf=B)

#### `igf1r` → `ted` 🟡 **acceptable_mismatch**

| Field | Value |
|---|---|
| Legacy drugs (`drug_areas`) | 9 |
| Legacy drugs (`drug_area_scores`) | 9 |
| Normalized drugs (`drug_indications`) | 13 |
| Overlap | 8 |
| Raw match % | 88.9% |
| Extra in legacy only | 1 |
| Extra in normalized only | 5 |
| Normalized trial count (`trial_indications`) | 33 |
| Deals tagged to legacy area | 18 |
| Catalysts tagged to legacy area | 30 |

**Assessment:** 88.9% legacy coverage. 5 extra drugs in normalized are expected — the ontology is more complete than the legacy area curation. Review extra_legacy list for any true missing rows.

**Drugs in legacy only (first 15):**
- `batoclimab`: Batoclimab (IMVT-1401)

**Drugs in normalized only (first 15):**
- `cizutamig`: Cizutamig (conf=B)
- `crn12755`: CRN12755 (conf=A)
- `iscalimab`: Iscalimab (CFZ533) (conf=B)
- `lonigutamab`: lonigutamab (conf=A)
- `sp-1351`: SP-1351 (conf=A)

#### `atopy` → `ad, chronic_urticaria` 🟡 **acceptable_mismatch**

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

**Assessment:** 90.0% legacy coverage. 10 extra drugs in normalized are expected — the ontology is more complete than the legacy area curation. Review extra_legacy list for any true missing rows.

**Drugs in legacy only (first 15):**
- `upadacitinib`: Rinvoq (upadacitinib)

**Drugs in normalized only (first 15):**
- `abrocitinib`: Cibinqo (abrocitinib) (conf=A)
- `bsi-045b`: Bosakitug (conf=B)
- `catalog-49`: IMG-007 (conf=A)
- `cendakimab`: Cendakimab (conf=B)
- `ibi333`: IBI333 (conf=B)
- `omalizumab`: Xolair (omalizumab) (conf=B)
- `rocatinlimab`: Rocatinlimab (conf=A)
- `ruxolitinib-topical`: Opzelura (ruxolitinib (topical)) (conf=B)
- `win027`: WIN027 (conf=B)
- `zemprocitinib`: zemprocitinib (conf=A)

#### `ted` → `ted` 🟡 **acceptable_mismatch**

| Field | Value |
|---|---|
| Legacy drugs (`drug_areas`) | 12 |
| Legacy drugs (`drug_area_scores`) | 13 |
| Normalized drugs (`drug_indications`) | 13 |
| Overlap | 11 |
| Raw match % | 91.7% |
| Extra in legacy only | 1 |
| Extra in normalized only | 2 |
| Normalized trial count (`trial_indications`) | 33 |
| Deals tagged to legacy area | 0 |
| Catalysts tagged to legacy area | 2 |

**Assessment:** 91.7% legacy coverage. 2 extra drugs in normalized are expected — the ontology is more complete than the legacy area curation. Review extra_legacy list for any true missing rows.

**Drugs in legacy only (first 15):**
- `batoclimab`: Batoclimab (IMVT-1401)

**Drugs in normalized only (first 15):**
- `cizutamig`: Cizutamig (conf=B)
- `iscalimab`: Iscalimab (CFZ533) (conf=B)

#### `tl1a` → `uc, cd` 🟢 **compare_pass_oos_adjusted**

| Field | Value |
|---|---|
| Legacy drugs (`drug_areas`) | 51 |
| Legacy drugs (`drug_area_scores`) | 51 |
| Normalized drugs (`drug_indications`) | 49 |
| Overlap | 47 |
| Raw match % | 92.2% |
| Confirmed OOS excluded (`confirmed_oos_legacy_noise`) | 3 (lm-302, sim0500, spy072) |
| OOS-adjusted match % | 97.9% |
| Extra in legacy only | 4 |
| Extra in normalized only | 2 |
| Normalized trial count (`trial_indications`) | 64 |
| Deals tagged to legacy area | 67 |
| Catalysts tagged to legacy area | 384 |

**Assessment:** Raw 92.2% < 95% threshold, but OOS-adjusted coverage is 97.9% ≥ 95% after removing 3 confirmed out-of-scope legacy drug(s) from denominator. Governance rule (2026-05-25): confirmed OOS drugs excluded from migration-readiness denominator. Ready for Phase 4 compare pass — NOT Phase 5 migration (requires dual-read validation first).

**Drugs in legacy only (first 15):**
- `epi-001`: EPI-001
- `lm-302`: LM-302
- `sim0500`: SIM0500
- `spy072`: SPY072

**Drugs in normalized only (first 15):**
- `risankizumab-lutikizumab-or-trosunilimab`: TARGET-CD (M24-885) (risankizumab + lutikizumab or trosunilimab) (conf=A)
- `risankizumab-vs-vedolizumab`: risankizumab vs vedolizumab (conf=A)

#### `ibd` → `uc, cd` 🟢 **compare_pass_oos_adjusted**

| Field | Value |
|---|---|
| Legacy drugs (`drug_areas`) | 50 |
| Legacy drugs (`drug_area_scores`) | 50 |
| Normalized drugs (`drug_indications`) | 49 |
| Overlap | 47 |
| Raw match % | 94.0% |
| Confirmed OOS excluded (`confirmed_oos_legacy_noise`) | 1 (sim0500) |
| OOS-adjusted match % | 95.9% |
| Extra in legacy only | 3 |
| Extra in normalized only | 2 |
| Normalized trial count (`trial_indications`) | 64 |
| Deals tagged to legacy area | 0 |
| Catalysts tagged to legacy area | 18 |

**Assessment:** Raw 94.0% < 95% threshold, but OOS-adjusted coverage is 95.9% ≥ 95% after removing 1 confirmed out-of-scope legacy drug(s) from denominator. Governance rule (2026-05-25): confirmed OOS drugs excluded from migration-readiness denominator. Ready for Phase 4 compare pass — NOT Phase 5 migration (requires dual-read validation first).

**Drugs in legacy only (first 15):**
- `epi-001`: EPI-001
- `sim0500`: SIM0500
- `spy072`: SPY072

**Drugs in normalized only (first 15):**
- `risankizumab-lutikizumab-or-trosunilimab`: TARGET-CD (M24-885) (risankizumab + lutikizumab or trosunilimab) (conf=A)
- `risankizumab-vs-vedolizumab`: risankizumab vs vedolizumab (conf=A)

#### `il4ra` → `ad, asthma` ✅ **match**

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

**Assessment:** 100.0% of legacy drugs represented in normalized. Extra normalized drugs are genuine ontology expansion, not regressions.

**Drugs in normalized only (first 15):**
- `abrocitinib`: Cibinqo (abrocitinib) (conf=A)
- `apg333`: APG333 (conf=A)
- `benralizumab`: Fasenra (benralizumab) (conf=A)
- `bsi-045b`: Bosakitug (conf=B)
- `catalog-49`: IMG-007 (conf=A)
- `cendakimab`: Cendakimab (conf=B)
- `gb0895`: GB-0895 (conf=B)
- `ibi333`: IBI333 (conf=B)
- `mepolizumab`: Nucala (mepolizumab) (conf=B)
- `omalizumab`: Xolair (omalizumab) (conf=B)
- `qx031n`: QX031N (conf=B)
- `rocatinlimab`: Rocatinlimab (conf=A)
- `ruxolitinib-topical`: Opzelura (ruxolitinib (topical)) (conf=B)
- `tezepelumab`: Tezspire (tezepelumab) (conf=B)
- `tozorakimab`: Tozorakimab (conf=B)
- _(+3 more)_

#### `respiratory` → `asthma, copd, crswnp` ✅ **match**

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

**Assessment:** 100.0% of legacy drugs represented in normalized. Extra normalized drugs are genuine ontology expansion, not regressions.

**Drugs in normalized only (first 15):**
- `ibi333`: IBI333 (conf=B)
- `omalizumab`: Xolair (omalizumab) (conf=B)
- `rademikibart--cbp-201`: Rademikibart (CBP-201) (conf=B)

#### `tslp` → `asthma, copd, crswnp` ✅ **match**

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

**Assessment:** 100.0% of legacy drugs represented in normalized. Extra normalized drugs are genuine ontology expansion, not regressions.

**Drugs in normalized only (first 15):**
- `ibi333`: IBI333 (conf=B)
- `omalizumab`: Xolair (omalizumab) (conf=B)
- `rademikibart--cbp-201`: Rademikibart (CBP-201) (conf=B)

---

## Part 2 — High-Risk Dashboard Function Comparisons

For each of the 5 high-risk legacy dashboard paths (from `docs/dashboard_dependency_inventory.md`), this section compares what the legacy path produces vs. what the normalized replacement would produce.

### openDrugEntityModal()  🔴 **migration_blocker**

- **Lines:** 11557–11620
- **Legacy source:** drug_area_scores (competitive positioning)
- **Normalized source:** drug_targets + drug_indications
- **Legacy count:** 107
- **Normalized count:** 144
- **Overlap:** 104
- **Match %:** 97.2%
- **Notes:** drug_area_scores has competitive enrichment data (overlap, rationale, cls) that has no equivalent column in drug_indications/drug_targets. The competitive positioning modal content CANNOT be replaced until drug_area_scores enrichment is migrated to drug_indications. Separate concern from drug population coverage.

### _makeAreaPI() — IBD/TL1A tab  🟢 **compare_pass_oos_adjusted**

- **Lines:** 12121–12200
- **Legacy source:** drug_areas.in('area_id', ['ibd']) or ['tl1a']
- **Normalized source:** drug_indications WHERE indication_id IN ('uc','cd')
- **Legacy count:** 51
- **Normalized count:** 49
- **Overlap:** 47
- **Match %:** 92.2%
- **Notes:** Legacy ibd+tl1a areas contain 51 drugs. drug_indications covers 49 UC+CD drugs (47 overlap). Raw coverage: 92.2%. OOS-adjusted coverage: 97.9% after removing 3 confirmed OOS drugs (['lm-302', 'sim0500', 'spy072']). Governance rule (2026-05-25): OOS drugs are legacy curation noise — do NOT add them to drug_indications. Ready for Phase 4 dual-read comparison — NOT Phase 5 migration.

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

## Part 4 — Mismatch Classification (Track B)

Classifying why each mismatch exists. Types: `coverage_gap` | `alias_gap` | `scope_difference` | `legacy_noise` | `true_missing_row`

| Area | Extra-Legacy Drug | Classification | Action |
|---|---|---|---|
| `atopy` | `upadacitinib` (Rinvoq (upadacitinib)) | true_missing_row | Add drug_indications row: upadacitinib → ad |
| `autoimmune` | `batoclimab` (Batoclimab (IMVT-1401)) | scope_difference | FcRn mechanism drug placed in autoimmune legacy catch-all |
| `autoimmune` | `cnd261` (CND261) | coverage_gap | Wave 2A did not cover CND261; need drug_indications backfill |
| `autoimmune` | `cnd319` (CND319) | coverage_gap | Wave 2A did not cover CND319; need drug_indications backfill |
| `autoimmune` | `iscalimab` (Iscalimab (CFZ533)) | coverage_gap | Iscalimab (CD40; gMG-adjacent) missing from drug_indications |
| `fcrn` | `atg-201` (ATG-201) | scope_difference | ATG-201 is CAR-T (tcell area), placed in fcrn legacy; different mechanism |
| `fcrn` | `batoclimab` (Batoclimab (IMVT-1401)) | scope_difference | Batoclimab = FcRn-targeting but in legacy igf1r/autoimmune areas; not in gmg/cidp/waiha drug_indications |
| `fcrn` | `imvt-1402` (IMVT-1402) | true_missing_row | IMVT-1402 is FcRn; add drug_indications rows for gmg/cidp/waiha |
| `igf1r` | `batoclimab` (Batoclimab (IMVT-1401)) | scope_difference | Batoclimab = FcRn/IgG pathway, classified in igf1r legacy area; exclude from ted |
| `tcell` | `atg-201` (ATG-201) | scope_difference | ATG-201 is CAR-T targeting GD2; not ALL or MM specifically |
| `ted` | `batoclimab` (Batoclimab (IMVT-1401)) | scope_difference | Batoclimab is FcRn; legacy igf1r area misclassified it; not TED |

---

## Part 5 — Phase 4 Acceptance Criteria

Phase 4 migration is safe when ALL of the following are true:

### Per-Indication Criteria

| Indication(s) | Required | Raw% | OOS-Adj% | OOS Excl. | Criteria Met? |
|---|---|---|---|---|---|
| `il4ra` → ad, asthma | ≥95% | 100.0% | — | — | ✅ raw |
| `respiratory` → asthma, copd, crswnp | ≥95% | 100.0% | — | — | ✅ raw |
| `tslp` → asthma, copd, crswnp | ≥95% | 100.0% | — | — | ✅ raw |
| `ibd` → uc, cd | ≥95% | 94.0% | 95.9% | 1 | 🟢 OOS-adj |
| `tl1a` → uc, cd | ≥95% | 92.2% | 97.9% | 3 | 🟢 OOS-adj |
| `ted` → ted | ≥95% | 91.7% | — | — | ❌ |
| `atopy` → ad, chronic_urticaria | ≥95% | 90.0% | — | — | ❌ |
| `igf1r` → ted | ≥95% | 88.9% | — | — | ❌ |
| `fcrn` → gmg, cidp, waiha | ≥95% | 57.1% | — | — | ❌ |
| `autoimmune` → gmg, cidp, ra, sle, waiha, sjogrens | ≥95% | 48.0% | — | — | ❌ |
| `tcell` → all, multiple_myeloma | ≥95% | 0.0% | — | — | ❌ |

_🟢 OOS-adj = passes after removing confirmed OOS drugs from denominator per governance rule (2026-05-25)._

### Dashboard Function Criteria

| Function | Blocking Condition | Resolved? |
|---|---|---|
| `openDrugEntityModal()` | drug_indications must have competitive enrichment data (overlap, rationale, cls) | ❌ Not yet — enrichment migration pending |
| `_makeAreaPI()` IBD/TL1A | OOS-adjusted coverage ≥ 95% — ready for Phase 4 dual-read | 🟢 Phase 4 compare pass (OOS-adjusted) |
| `loadAreaDeals()` | deals.indication_id FK must exist | ❌ Column does not exist |
| `loadAreaCatalysts()` | area_id→indication_id bridge must exist for catalysts | ❌ Bridge not built |
| Trial + Signal feeds | trials.indication_id must be backfilled from trial_indications | ❌ trials.indication_id is NULL |

---

## Phase 4 Overall Status

**Comparison date:** 2026-05-25 20:59 UTC
**Areas compared:** 11
- ✅ match: 3
- 🟢 compare_pass_oos_adjusted: 2
- 🟡 acceptable_mismatch: 3
- 🟠 needs_rule_adjustment: 2
- 🔴 migration_blocker: 0
- ⛔ not_ready: 1

**OOS-adjusted pass areas:** ibd, tl1a  
These areas meet the 95% migration-readiness threshold after removing confirmed OOS drugs from the legacy denominator. Ready for **Phase 4 dual-read validation**. Do NOT advance to Phase 5 (migration) until dual-read comparison confirms zero regressions.

**Verdict:** Phase 4 migration is **NOT YET SAFE** for all areas. Remaining blockers must be resolved before any dashboard query is switched. See Part 3 for specific blocking conditions.

**Next action (Track D):** Build Phase 4 dual-read layer for `_makeAreaPI` and `openDrugEntityModal` — parallel read paths, assert row count parity, log any visual regressions. Starting point: `docs/phase4_comparison_harness.md` Part 2 and Part 5.
