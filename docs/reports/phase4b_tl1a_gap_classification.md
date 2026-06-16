# Phase 4B — TL1A Target-View Gap Classification
**Session 53h · 2026-05-25**  
**Status:** Complete — all 17 gap drugs classified · harness ready for TL1A dual-read

---

## Summary

| Category | Count | Drugs |
|---|---|---|
| Legacy TL1A (drug_area_scores) | 51 | — |
| Normalized TL1A (drug_targets.target_id='tl1a') | 35 | — |
| Gap (legacy only) | 17 | see below |
| **True TL1A target drugs missing drug_targets row** | **0** | **none** |
| IBD indication drug, not TL1A target | 15 | see below |
| Legacy noise (wrong area) | 2 | lm-302, sim0500 |

---

## Key Finding

> **The legacy TL1A dashboard area was a competitive landscape container, not a strict target-view.**

The legacy `drug_area_scores.area_id='tl1a'` bucket mixed two semantically different drug populations:

1. **True TL1A target drugs** (35) → already normalized in `drug_targets.target_id='tl1a'`  
2. **IBD indication competitors** (15) → correct normalized path is `drug_indications.indication_id IN ('uc','cd')`  
3. **Legacy noise** (2) → wrong area entirely (gastric oncology + RRMM)

Zero gap drugs are true TL1A target drugs with missing `drug_targets` rows. There is no backfill needed to unblock the TL1A target-view dual-read.

**Consequence for Phase 4B Path B:**

The `migration_blocker` status on the TL1A target-view comparison was **correct and structural** — it correctly detected that the legacy and normalized populations are measuring different things. Once all 17 gap drugs are added to `DIFFERENCE_CLASSIFICATIONS` as `ibd_indication_not_tl1a_target` or `legacy_noise_removed`, the adjusted TL1A target-view match becomes **35/35 = 100%** (compare_pass).

---

## Data Quality Flag

`gb004 → drugs.mechanism` reads `"Anti-TL1A"` — **this is incorrect data.**  
Actual mechanism: PHD inhibitor (HIF-1α stabilizer), oral small molecule.  
GB004 is not an anti-TL1A antibody. The mechanism field requires correction before the next enrichment run.

---

## Classification Detail (all 17 gap drugs)

### Legacy Noise Removed (2)

| drug_id | Name | Evidence | Action |
|---|---|---|---|
| `lm-302` | LM-302 | CLDN18.2 MMAE-ADC; gastric/GEJ cancer; all trials `off_target` | Exclude from TL1A denominator. Already classified in IBD gap. |
| `sim0500` | SIM0500 | GPRC5D×BCMA×CD3 trispecific; RRMM (multiple myeloma); `off_target` trial | Exclude from TL1A denominator. Already classified in IBD gap. |

### IBD Indication Drug, Not TL1A Target (15)

These drugs treat UC and/or CD but do not mechanistically target TL1A. They were placed in the legacy TL1A area for competitive landscape tracking — not because they have TL1A biology. Their correct normalized path is `drug_indications.indication_id IN ('uc','cd')`.

| drug_id | Name | Mechanism | Indication | Stage | Action |
|---|---|---|---|---|---|
| `vedolizumab` | vedolizumab | Anti-α4β7 integrin | UC · CD | Approved | drug_indications uc+cd. No drug_targets tl1a. |
| `risankizumab` | risankizumab | Anti-IL-23p19 | PsO, CD, UC | Approved | drug_indications cd+uc. No drug_targets tl1a. |
| `mirikizumab` | mirikizumab | Anti-IL-23p19 | UC (2023), CD (2024) | Approved | drug_indications uc+cd. No drug_targets tl1a. |
| `guselkumab` | guselkumab | Anti-IL-23p19 | PsO, PsA, CD | Approved | drug_indications cd. No drug_targets tl1a. |
| `guselkumab-golimumab` | guselkumab + golimumab | IL-23p19 + TNFα combo | UC Phase 2b/3 | Phase 3 | drug_indications uc. Combo slug — no drug_targets row. |
| `golimumab` | golimumab | Anti-TNFα | RA, PsA, AS, UC | Approved | drug_indications uc. No drug_targets tl1a. |
| `ustekinumab` | ustekinumab | Anti-IL-12/23p40 | PsO, PsA, CD, UC | Approved | drug_indications uc+cd. No drug_targets tl1a. |
| `upadacitinib` | upadacitinib | JAK1 inhibitor (oral) | RA, PsA, AD, UC, CD | Approved | drug_indications uc+cd. Wave 2D: add ad. No drug_targets tl1a. |
| `abbv-382` | ABBV-382 | Anti-α4β7 integrin | UC · CD | Phase 2 | drug_indications uc+cd. No drug_targets tl1a. |
| `abbv-668` | ABBV-668 | RIPK1 inhibitor | CD | Phase 2 | drug_indications cd. No drug_targets tl1a. |
| `lutikizumab` | Lutikizumab | Dual IL-1α/β inhibitor | CD | Phase 3 | drug_indications cd. No drug_targets tl1a. |
| `spy001` | SPY001 | Anti-α4β7 integrin | UC | Phase 2 | drug_indications uc. No drug_targets tl1a. |
| `spy003` | SPY003 | Anti-IL-23p19 | UC · CD | Phase 2 | drug_indications uc+cd. No drug_targets tl1a. |
| `spy130` | SPY130 | Anti-α4β7 + Anti-IL-23 combo | UC · CD | Phase 2 | drug_indications uc+cd. No drug_targets tl1a. |
| `gb004` | GB004 | PHD1/HIF-1α stabilizer (oral) ⚠️ | UC | Terminated | drug_indications uc. No drug_targets tl1a. Fix mechanism field. |

---

## Implication for TL1A Dual-Read (Phase 4B Path B)

The TL1A target-view dual-read **can now proceed** using:

- **Legacy source:** `drug_area_scores.area_id = 'tl1a'`
- **Normalized source:** `drug_targets WHERE target_id = 'tl1a'`
- **Adjusted denominator:** exclude all 17 classified gap drugs (15 × `ibd_indication_not_tl1a_target` + 2 × `legacy_noise_removed`)
- **Expected adjusted match:** 35/35 = **100%** (`compare_pass`)

All 17 gap drugs are now in `DIFFERENCE_CLASSIFICATIONS` in the harness script (Session 53h). The harness re-run after this session should show TL1A target-view at `compare_pass`.

---

## What This Confirms About Phase 5 Architecture

The legacy TL1A dashboard area conflated two things that the normalized graph correctly separates:

| Dashboard concern | Legacy source (Phase 4) | Normalized source (Phase 5) |
|---|---|---|
| Who targets TL1A mechanistically? | `drug_area_scores.area_id='tl1a'` (mixed) | `drug_targets.target_id='tl1a'` |
| Who treats IBD (UC/CD)? | `drug_area_scores.area_id='ibd'` (mixed) | `drug_indications.indication_id IN ('uc','cd')` |

Phase 5 should present these as two distinct queries. The TL1A tab becomes a true target-mechanism view; the IBD tab becomes a true indication view. Drugs like vedolizumab, risankizumab, and mirikizumab correctly appear in the IBD indication tab via drug_indications — not in the TL1A target tab.

---

## Non-Negotiable Rules (unchanged)

1. No backfilling `drug_targets.target_id='tl1a'` for IBD indication drugs.
2. No unlocking `ontology_edges` until advisor approves post Phase 4B.
3. No Phase 5 dashboard migration before Phase 4B dual-read validates.
4. `gb004.drugs.mechanism` data error flagged — requires correction before next enrichment.
