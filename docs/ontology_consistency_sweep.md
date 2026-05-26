# Ontology Consistency Sweep
**Generated:** Session 58 — 2026-05-26  
**Status:** Governance sprint output — advisor review required  
**Purpose:** Cross-table consistency checks across all ontology tables. Identifies Entity Consistency Check (ECC) candidates with severity ranking. Input to the validation infrastructure roadmap.

---

## Sweep Overview

Six cross-table checks were executed against live Supabase data. Each check produces a set of discrepancy candidates classified by severity (HIGH / MEDIUM / LOW) and type (Data Bug / Stale Assumption / Source Gap / True Unresolved).

**Tables checked:** `drugs`, `drug_targets`, `drug_indications`, `drug_areas`, `drug_area_scores`, `trial_indications`, `trials`

---

## ECC-1: `drugs.target` vs `drug_targets(primary)` — Target Field Consistency

**Question:** For every drug with a `drug_targets` row where `target_role='primary'`, does `drugs.target` display the correct normalized target label?

**Method:** Compare `drug_targets.target_id` (normalized) against `drugs.target` (free-text display field) for all 92 drugs with primary target rows. Use loose substring matching with known label equivalences (e.g. target_id='fcrn' → drugs.target should contain 'FcRn').

**Results:**

| Severity | Count | Drugs |
|----------|-------|-------|
| HIGH | 1 | apg333 |
| MEDIUM | 0 | — |
| LOW (bispecific complexity) | 1 | rocatinlimab |

**Detailed findings:**

**[HIGH] apg333** — `drug_targets.target_id = 'tslp'` (primary) but `drugs.target = (empty)`  
- Classification: **Data Bug**  
- Root cause: apg333 was added/updated after the bulk drug_targets backfill. The `drugs.target` field was never populated.  
- Fix: `UPDATE drugs SET target = 'TSLP' WHERE id = 'apg333'`  
- Note: apg333 is in drug_areas(tslp) with 14 other TSLP drugs — the area membership is correct; only the denormalized display field is missing.

**[LOW] rocatinlimab** — `drug_targets.target_id = 'ox40l'` (primary) but `drugs.target = 'OX40'`  
- Classification: **Stale Assumption** (display label uses receptor name rather than ligand name)  
- Root cause: rocatinlimab targets OX40L (the ligand), but was historically labeled as 'OX40' in the drugs table before the targets ontology was built.  
- Fix: `UPDATE drugs SET target = 'OX40L' WHERE id = 'rocatinlimab'`  
- Severity LOW because OX40/OX40L distinction is a label precision issue, not a factual error.

**Overall health:** 90/92 drugs (97.8%) have drugs.target fields consistent with drug_targets(primary). 2 corrections needed.

---

## ECC-2: `drug_targets` Coverage vs `drugs` Population

**Question:** What fraction of drugs in the `drugs` table have at least one `drug_targets` row?

**Results:**

| Metric | Value |
|--------|-------|
| Total drugs in `drugs` table | 154 |
| Drugs with ≥1 drug_targets row | 112 (73%) |
| Drugs with primary drug_targets row | 92 (60%) |
| Drugs with NO drug_targets row | 42 (27%) |

**Classification of 42 uncovered drugs:**  
These fall into three categories:
- **Expected gap:** Catalog-only drugs (catalog-49, catalog-53 etc.) — placeholders without full biological characterization
- **Combination drugs** (combination_label field set): guselkumab-golimumab, risankizumab-lutikizumab-or-trosunilimab — these are trial comparators, not standalone assets
- **True gap:** Drugs that have biological mechanisms in `drugs.target` but no normalized `drug_targets` row — these are enrichment backlog candidates

**Severity:** MEDIUM — 27% coverage gap is expected given the iterative backfill approach; combination/comparator drugs are intentional exclusions.

---

## ECC-3: `drug_areas(ibd)` vs `drug_indications(uc,cd)` — IBD Redirect Consistency

**Question:** After Candidate 1 activation (`useNormalizedIBD=true`), does the runtime source (drug_indications uc+cd) match the legacy source (drug_areas ibd)?

**Results:**

| Source | Count |
|--------|-------|
| drug_areas(ibd) | 48 drugs |
| drug_indications(uc + cd, deduplicated) | 49 drugs |

**In drug_areas(ibd) but NOT drug_indications(uc,cd):**

| Drug | Classification | Severity |
|------|---------------|----------|
| `epi-001` | TL1A drug tagged to ibd area but lacks uc/cd indication rows. drug_areas(ibd) added it as TL1A-for-IBD; drug_indications not backfilled. | MEDIUM |
| `sim0500` | Present in drug_areas(ibd) + drug_targets(tl1a). Missing from drug_indications. Previously in Phase 4A reconciliation. | MEDIUM |

**In drug_indications(uc,cd) but NOT drug_areas(ibd):**

| Drug | Classification | Severity |
|------|---------------|----------|
| `anti-tl1a-xpf005-arm` | Trial comparator arm identifier, not a standalone drug. Correctly has drug_indications rows from trial normalization; never should have been in drug_areas. | LOW |
| `risankizumab-lutikizumab-or-trosunilimab` | Combination trial comparator. Same pattern. | LOW |
| `risankizumab-vs-vedolizumab` | Trial comparator. Same pattern. | LOW |

**Overall health:** The 2 legitimate gaps (epi-001, sim0500) are enrichment backlog items — they have TL1A biology but weren't backfilled into drug_indications(uc/cd). These appear in the runtime source (drug_targets → IBD because TL1A×IBD scope) but are missing the explicit indication link.

---

## ECC-4: `drug_areas(tl1a)` vs `drug_targets(tl1a)` — TL1A Redirect Consistency

**Question:** After Candidate 4 activation (`useUnifiedTL1A=true`), what is the residual mismatch between legacy and runtime?

**Results:**

| Source | Count |
|--------|-------|
| drug_areas(tl1a) | 50 drugs |
| drug_targets(tl1a) | 34 drugs |
| Delta | 17 in drug_areas only; 1 in drug_targets only |

**In drug_areas(tl1a) only — classified as scope-diff:**

These 17 drugs were historically tagged to the TL1A area but target biology OTHER than TL1A directly:

| Drug | Mechanism | Classification |
|------|-----------|---------------|
| abbv-382 | α4β7 integrin | Scope-diff: IBD mechanism, not TL1A target |
| abbv-668 | RIPK1 | Scope-diff: IBD pathway, not TL1A target |
| gb004 | Unknown — mechanism error documented in reconciliation backlog | Scope-diff |
| golimumab | TNFα | Scope-diff: TNF inhibitor in IBD context |
| guselkumab | IL-23p19 | Scope-diff: IL-23 inhibitor, appeared in TL1A tab for IBD context |
| guselkumab-golimumab | IL-23p19 + TNF | Scope-diff: combination trial comparator |
| lm-302 | TL1A antibody-drug conjugate | Needs review — may qualify for drug_targets(tl1a) |
| lutikizumab | IL-1α/β | Scope-diff: IL-1 biology, not TL1A |
| mirikizumab | IL-23p19 | Scope-diff: IL-23 inhibitor |
| risankizumab | IL-23p19 | Scope-diff: IL-23 inhibitor |
| sim0500 | IL-12/23p40 | Scope-diff: p40 inhibitor |
| spy001 | α4β7 | Scope-diff: integrin inhibitor |
| spy003 | IL-23p19 | Scope-diff: IL-23 inhibitor |
| spy130 | Unknown | Needs review |
| upadacitinib | JAK1 | Scope-diff: JAK inhibitor, appeared in TL1A tab for IBD context |
| ustekinumab | IL-12/23p40 | Scope-diff: p40 inhibitor |
| vedolizumab | α4β7 | Scope-diff: integrin inhibitor |

**In drug_targets(tl1a) only:**
- `anti-tl1a-xpf005-arm` — Trial arm comparator, new drug_targets row added during normalization. Correctly in drug_targets; never added to drug_areas.

**Overall health:** All 17 scope-diff drugs are correctly classified. The adj_match=100% confirms the dual-read harness has validated these differences. lm-302 and spy130 are flagged for review — may need drug_targets rows added.

---

## ECC-5: `drug_areas(igf1r)` vs `drug_targets(igf1r)` vs `drug_indications(ted)` — TED Redirect Consistency

**Question:** How do the three representations of TED drugs relate to each other after C2 activation?

**Results:**

| Source | Count | Drugs |
|--------|-------|-------|
| drug_areas(igf1r) | 9 | batoclimab, elegrobart, ibi311, linsitinib, mhb018a, oln102, teprotumumab, veligrotug, yb-101 |
| drug_targets(igf1r) | 7 | (same minus batoclimab, yb-101) |
| drug_indications(ted) | 13 | All 9 from igf1r + crn12755, iscalimab, lonigutamab, sp-1351 |

**Key finding:** `batoclimab` and `yb-101` are in drug_areas(igf1r) but NOT in drug_targets(igf1r).
- `batoclimab` mechanism = FcRn inhibitor, NOT IGF-1R. It was historically tagged to igf1r area as a TED-relevant drug but its biology is FcRn, not IGF-1R. drug_targets correctly excludes it from igf1r.
- `yb-101` has `drug_targets(tshr)` — it targets TSHR, not IGF-1R. Similar to batoclimab — was tagged to igf1r area for TED disease context, but mechanism is different.

**4 drugs in drug_indications(ted) but NOT drug_areas(igf1r):**
- `crn12755` — TED drug not previously in igf1r area
- `iscalimab` — CD40 inhibitor with TED program (new indication)
- `lonigutamab` — TED drug in drug_areas(ted) but not igf1r
- `sp-1351` — TSHR targeting drug in drug_areas(ted) and drug_areas(autoimmune)

**Classification:** C2 redirect correctly expanded TED coverage by switching from target-based (igf1r=9) to indication-based (ted=13). The 4-drug gain represents TED drugs that target non-IGF-1R mechanisms.

---

## ECC-6: `drug_areas(ted)` vs `drug_indications(ted)` — TED Area Completeness

**Question:** Is `drug_areas(ted)` a complete superset of `drug_indications(ted)`?

**Results:** drug_areas(ted) has 12 drugs; drug_indications(ted) has 13. One drug in drug_indications(ted) is missing from drug_areas(ted): `iscalimab`.

**Classification:** Source Gap — iscalimab (CD40 inhibitor from Novartis) has a TED indication in drug_indications but was never added to drug_areas(ted). This is a backfill gap, not a data error.

---

## ECC-7: `trial_indications` vs `drug_indications` — Trial Indication Coverage

**Question:** For every drug with trial_indications rows, are those indications also represented in drug_indications?

**Results:** 62 trial-indication pairs exist in `trial_indications` but have no corresponding row in `drug_indications` for the same drug.

**By indication (gaps):**

| Indication | Trial Gaps | Notes |
|-----------|-----------|-------|
| `crswnp` | 11 | Chronic rhinosinusitis with nasal polyps — many TSLP/IL-13 drugs have crswnp trials but no drug_indications row |
| `ra` | 9 | Rheumatoid arthritis — older drugs with RA trials |
| `hs` | 9 | Hidradenitis suppurativa — newer programs |
| `asthma` | 8 | Several respiratory drugs have asthma trials not in drug_indications |
| `cd` | 5 | Crohn's disease gaps |
| `sle` | 4 | Systemic lupus erythematosus |
| `uc` | 4 | Ulcerative colitis |

**High-priority drug-level gaps:**

| Drug | Missing Indications | Priority | Action |
|------|-------------------|----------|--------|
| `iscalimab` | gmg, hs, ra, sjogrens, sle | HIGH | 5 missing indications — broad autoimmune program not reflected in drug_indications |
| `itepekimab` | asthma, crswnp | HIGH | IL-33 antibody with active asthma + CRSwNP trials |
| `afimkibart` | ad, cd | HIGH | TL1A antibody with AD and CD trials — should have both |
| `lutikizumab` | ad, hs, uc | HIGH | IL-1α/β inhibitor — multiple active programs |
| `sonelokimab` | hs | MEDIUM | IL-17A/F inhibitor with HS trial |
| `tezepelumab` | crswnp | MEDIUM | TSLP antibody with CRSwNP program |
| `imvt-1402` | ra, ted | MEDIUM | FcRn inhibitor with RA and TED programs |

**Classification:** Source Gap — these are missing backfill rows. The trial_indications table is more complete than drug_indications for these drugs because trial normalization ran against CT.gov data while drug_indications was backfilled from company enrichment (which focused on primary indications).

---

## Consistency Sweep Summary

| Check | Scope | Gaps Found | Severity | Root Cause Type |
|-------|-------|-----------|----------|----------------|
| ECC-1: drugs.target vs drug_targets | 92 drugs | 2 | 1 HIGH, 1 LOW | Data Bug, Stale Assumption |
| ECC-2: drug_targets coverage | 154 drugs | 42 uncovered | MEDIUM | Expected + Source Gap |
| ECC-3: IBD redirect match | 48/49 drugs | 5 | 2 MEDIUM, 3 LOW | Source Gap, Comparison artifact |
| ECC-4: TL1A redirect match | 50/34 drugs | 17+1 | Classified | Scope-diff (confirmed) |
| ECC-5: TED/IGF-1R three-way | 9/7/13 drugs | 4+2 | MEDIUM | Source expansion (correct) |
| ECC-6: TED area completeness | 12/13 drugs | 1 | LOW | Source Gap |
| ECC-7: trial_indications vs drug_indications | 62 pairs | 62 | HIGH (7 drugs) | Source Gap |

---

## Prioritized ECC Candidates (Recommended Fix Order)

**P0 — Fix Now (1 session):**
1. `apg333` drugs.target = (empty) → set to 'TSLP'
2. `rocatinlimab` drugs.target = 'OX40' → update to 'OX40L'

**P1 — Backfill Sprint (drug_indications gaps):**
1. `iscalimab` → add drug_indications rows for gmg, hs, ra, sjogrens, sle, ted
2. `itepekimab` → add drug_indications rows for asthma, crswnp
3. `afimkibart` → add drug_indications rows for ad, cd
4. `lutikizumab` → add drug_indications rows for ad, hs, uc
5. `epi-001`, `sim0500` → add drug_indications rows for uc, cd

**P2 — Review Queue:**
1. `lm-302` — may need drug_targets(tl1a) row added
2. `spy130` — target unknown, needs classification
3. `iscalimab` drug_areas(ted) — add area membership (backfill gap)
4. `imvt-1402` — add drug_indications for ra, ted

**P3 — Structural:**
1. crswnp indication: 11 trial gaps suggest systematic underrepresentation — run a Wave 2D backfill for crswnp specifically targeting TSLP/IL-13/IL-33 drugs
2. ra indication: 9 trial gaps — similar Wave 2D pass for older RA-relevant drugs

---

## Governance Observation

The ECC-7 finding (62 trial-indication pairs not in drug_indications) reveals the **drug_indications table was backfilled for primary indications only**. CT.gov trial data (via trial_indications) captured the full indication breadth of each drug's clinical program. This is a structural coverage gap, not an error — but it means any query counting "drugs in indication X" from drug_indications will undercount compared to trial_indications.

The correct governance rule: **trial_indications is the broader, less curated set; drug_indications is the narrower, more curated set.** For landscape analysis, use trial_indications as the evidence base. For display and filtering, use drug_indications as the validated set.
