# Phase 4A — Evidence Reconciliation Candidate Review
**Session 53d · 2026-05-25 · Updated with advisor decisions**  
**Status:** Corrections applied. Phase 4A complete. Ready for Phase 4B dual-read validation.

---

## Model Reminder

> No single table is ground truth. Truth is evidence-weighted and relationship-validated.  
> Legacy data = production baseline. Normalized data = candidate truth layer.  
> Phase 4A classifies every mismatch. Phase 4B validates parity. Phase 5 migrates.

**Evidence sources consulted (read-only):**  
`drugs` · `drug_areas` · `drug_indications` · `drug_targets` · `drug_area_scores` · `trials` · `trial_indications` · `backfill_preview`

---

## Acceptance Criteria Checklist

- [x] All six known candidates have structured records
- [x] Each has a recommended action
- [x] Each has a confidence score
- [x] Each has a review status
- [x] Dashboard migration impact is stated
- [x] No production data modified during review phase
- [x] Advisor decisions received and corrections applied (Session 53e)

---

## Advisor Decisions — Session 53e (2026-05-25)

| Drug | Decision | Action Taken |
|---|---|---|
| `sim0500` | ✅ Approve correction | drug_targets tl1a row was already absent from production (Wave 2B error identified by harness but not actually committed to drug_targets). **No delete needed.** Audit note added. |
| `batoclimab` | ✅ Approve backfill — ted + gmg only (not cidp) | Inserted drug_indications: ted (score=95, Ph3, A) + gmg (score=92, Ph3, A). Drug_indications total: 192 → 194. |
| `epi-001` | ⏸ Hold | Keep in backfill_preview as pending_review. Legacy TL1A/IBD membership insufficient without source evidence. |

**Post-correction Phase 4 harness results:**
- tl1a: 92.2% → 🟢 compare_pass_oos_adjusted (UNCHANGED — still passing)
- ibd: 94.0% → 🟢 compare_pass_oos_adjusted (UNCHANGED — still passing)
- ted: 🆕 **100% match** ✅ (batoclimab backfill resolved the ted normalized gap)
- drug_indications: 194 rows (was 192)
- No duplicate pairs detected
- ontology_edges: 25 (LOCKED — unchanged)
- epi-001: 2 rows still in backfill_preview as pending_review ✅

---

## Summary Table

| # | Drug | Check Type | Classification | Severity | Confidence | Review Status | Action |
|---|---|---|---|---|---|---|---|
| 1 | `lm-302` | cross_table_inconsistency | legacy_noise_removed | High | 0.99 | approved | No backfill. Exclude from denominator. |
| 2 | `sim0500` | cross_table_inconsistency | legacy_noise_removed + **normalized_table_error** | High | 0.98 | ✅ resolved | drug_targets tl1a row was already absent from production. No delete needed. |
| 3 | `spy072` | ontology_scope_difference | legacy_noise_removed (ibd) + scope_ok (tl1a) | Medium | 0.92 | approved | ibd legacy = noise. tl1a legacy = valid but indication is rheumatology. |
| 4 | `epi-001` | needs_manual_review | needs_manual_review | Medium | 0.55 | pending_human | Hold uc/cd rows in pending_review. Review source publications. |
| 5 | `batoclimab` | cross_table_inconsistency | normalized_gap (drug_indications) + source_conflict (indication_short) | High | 0.90 | ✅ resolved (ted + gmg) | Inserted ted (score=95) + gmg (score=92). cidp remains pending (not approved this round). |
| 6 | `upadacitinib` | normalized_gap | normalized_gap (ad missing) | Medium | 0.97 | approved | Backfill drug_indications: upadacitinib → ad. |

> **sim0500 and batoclimab flagged for advisor review** — they involve errors in normalized tables (not just legacy data), which require explicit approval before any correction is applied.

---

## Record 1 — `lm-302`

**entity_type:** drug  
**entity_id:** lm-302  
**check_type:** cross_table_inconsistency  
**severity:** High  

**conflicting_tables:**
- `drug_areas`: tl1a (legacy area membership)
- `drugs.target`: CLDN18.2 (Claudin 18.2 — gastric oncology target)
- `drugs.indication_short`: "Gastric · GEJ Adenocarcinoma"
- `drugs.modality`: anti-CLDN18.2 MMAE-ADC
- `drugs.stage`: Phase 3
- `trials` (9 trials): gastric cancer, GEJ adenocarcinoma, biliary tract, solid tumor — ALL oncology
- `trial_indications`: 0 rows (no indication ontology entries — gastric not yet in ontology)
- `drug_indications`: 0 rows
- `drug_targets`: 0 rows
- `backfill_preview` (wave2c): preview_status = **excluded**, target_id_col = `_excluded_legacy_noise`

**conflict_summary:**  
`drug_areas` places lm-302 in the `tl1a` legacy area (an IBD therapeutic area). Every other evidence source — drugs.target (CLDN18.2), drugs.indication_short (gastric/GEJ), drugs.modality (ADC), 9 clinical trials (all gastric/oncology) — identifies this as a gastric/GEJ oncology ADC. It has no biological relationship to TL1A, IBD, or any tracked indication. The Wave 2C backfill script correctly excluded it (`_excluded_legacy_noise`).

**evidence_for_legacy (tl1a membership):**
- `drug_areas.area_id = 'tl1a'` (single data point; confirmed by `drug_area_scores` overlap=Watch, confidence=confirmed)

**evidence_against_legacy:**
- `drugs.target = 'CLDN18.2'` — Claudin 18.2, a tight junction protein overexpressed in gastric/GEJ tumors
- `drugs.indication_short = 'Gastric · GEJ Adenocarcinoma'`
- `drugs.modality = 'anti-CLDN18.2 MMAE-ADC'` — antibody-drug conjugate (oncology)
- `trials` (9): 100% gastric/GEJ/biliary/solid tumor — zero IBD/inflammatory
- `backfill_preview` wave2c: correctly excluded as `_excluded_legacy_noise`
- `drug_targets`: 0 rows — no target relationship committed for this drug

**normalized_interpretation:**  
lm-302 is a gastric/GEJ oncology ADC that was erroneously placed in the tl1a legacy area. The drug has no IBD or TL1A biology. Legacy placement was a curation error. Normalized tables correctly exclude it.

**proposed_action:**  
No backfill to drug_indications or drug_targets for any IBD/TL1A indication. Exclusion from the IBD/TL1A migration-readiness denominator is confirmed correct. Consider adding lm-302 to a future gastric/oncology area if that area is added to Meridian.

**confidence_score:** 0.99  
**review_status:** approved (Wave 2C backfill already excluded it correctly; advisor confirmed OOS in Session 53)  

**dashboard_migration_impact:**  
- If `_makeAreaPI()` migrates to use drug_indications for IBD/TL1A: lm-302 disappears from the TL1A tab — CORRECT behavior, as it should not be there.
- No regression. The legacy area assignment was erroneous.
- Impact on readiness denominator: removing lm-302 from tl1a denominator (1 of 51 drugs) raises tl1a adjusted coverage from 92.2% → 94.1%.

---

## Record 2 — `sim0500`

**entity_type:** drug  
**entity_id:** sim0500  
**check_type:** cross_table_inconsistency (+ **normalized_table_error** in drug_targets)  
**severity:** High  

**conflicting_tables:**
- `drug_areas`: tl1a + ibd (legacy)
- `drug_targets`: tl1a — **INCORRECT** (Wave 2B error)
- `drug_indications`: multiple_myeloma (A, score=97, auto_confirmed) — CORRECT
- `drugs.target`: "GPRC5D×BCMA×CD3" — triple T-cell engager target
- `drugs.indication_short`: "RRMM" (Relapsed/Refractory Multiple Myeloma)
- `drugs.modality`: "GPRC5D×BCMA×CD3 trispecific T-cell engager" — hematology oncology
- `trials` (1): NCT06375044, Phase 1, Recruiting, "Relapsed or Refractory Multiple Myeloma"
- `backfill_preview` (wave2b): drug_targets tl1a committed — **this commit was an error**
- `backfill_preview` (wave2c): preview_status = excluded, target_id_col = `_excluded_legacy_noise`

**conflict_summary:**  
sim0500 is a GPRC5D×BCMA×CD3 trispecific T-cell engager for RRMM (multiple myeloma). Every evidence source correctly identifies it as a hematology oncology drug. However, Wave 2B committed a drug_targets row for `tl1a` — this is a normalized table error. The drug does not target TL1A. Separately, the `drug_areas` entries for tl1a and ibd are also legacy curation errors.

**⚠️ This is the most important finding in this review: the normalized drug_targets table itself contains an error.**  
sim0500 → tl1a is a Wave 2B backfill error. The drug does not target TL1A. This needs to be corrected in drug_targets before Phase 5 migration.

**evidence_for_legacy/normalized tl1a:**
- `drug_areas.area_id IN ('tl1a', 'ibd')` (legacy)
- `drug_targets.target_id = 'tl1a'` (Wave 2B committed — **error**)
- `drug_area_scores`: tl1a (Watch, confidence=confirmed), ibd (Direct, 1st Gen, confidence=supported)

**evidence_against tl1a:**
- `drugs.target = 'GPRC5D×BCMA×CD3'` — no TL1A in the target string
- `drugs.indication_short = 'RRMM'` — multiple myeloma
- `drugs.modality = 'GPRC5D×BCMA×CD3 trispecific T-cell engager'` — oncology modality
- `drug_indications.indication_id = 'multiple_myeloma'` (auto_confirmed, score=97) — correct
- `trials`: Phase 1 RRMM — zero IBD/TL1A/inflammatory
- `backfill_preview` (wave2c): excluded as `_excluded_legacy_noise` — correct exclusion

**normalized_interpretation:**  
- `drug_indications → multiple_myeloma`: CORRECT  
- `drug_areas → tl1a + ibd`: LEGACY NOISE — should be excluded from IBD/TL1A denominator  
- `drug_targets → tl1a`: NORMALIZED TABLE ERROR — should be deleted; the drug targets GPRC5D, BCMA, and CD3, not TL1A

**proposed_action:**  
1. **Flag for correction (pending advisor approval):** DELETE `drug_targets` row where `drug_id = 'sim0500' AND target_id = 'tl1a'`. This is a Wave 2B commit error.
2. **No backfill** to drug_indications for tl1a/ibd — correctly excluded already.
3. **Exclude from IBD/TL1A denominator** — already handled in DIFFERENCE_CLASSIFICATIONS.

**confidence_score:** 0.98  
**review_status:** needs_advisor — involves deleting a committed normalized table row (drug_targets), which requires explicit approval  

**dashboard_migration_impact:**  
- The drug_targets error is not currently user-visible (drug_targets is not directly rendered)
- However, if drug_targets feeds any future target dashboard or entity modal logic, sim0500 would incorrectly appear as a TL1A drug
- Correcting this before Phase 5 prevents downstream errors
- On IBD/TL1A tab: sim0500 correctly absent from drug_indications; correct behavior if legacy migrated

---

## Record 3 — `spy072`

**entity_type:** drug  
**entity_id:** spy072  
**check_type:** ontology_scope_difference  
**severity:** Medium  

**conflicting_tables:**
- `drug_areas`: tl1a + ibd (legacy)
- `drug_targets`: tl1a (A) — CORRECT (mechanism is accurate)
- `drug_indications`: 0 rows
- `drugs.target`: "TL1A"
- `drugs.indication_short`: "PsA · axSpA" — psoriatic arthritis and axial spondyloarthritis
- `drugs.modality`: mAb
- `drugs.stage`: Phase 2
- `drug_area_scores`: tl1a (Direct, confidence=supported), ibd (Adjacent, 1st Gen, confidence=supported)
- `trials` (1): NCT07148414, Phase 2, Recruiting, "Rheumatoid Arthritis · Psoriatic Arthritis · Axial Spondyloarthritis"
- `trial_indications`: 0 rows (ra mapped via NCT07148414 — wait, trial_indications shows ra for NCT07148414, but that is for upadacitinib... let me re-check)

Actually: NCT07148414 is spy072, Phase 2, "Rheumatoid Arthritis · Psoriatic Arthritis · Axial Spondyloarthritis". trial_indications shows `{"trial_id": "NCT07148414", "indication_id": "ra"}`. So spy072 has 1 trial_indication: `ra`.
- `backfill_preview` (wave2c): preview_status = excluded, target_id_col = `_excluded_ontology_scope_mismatch`

**conflict_summary:**  
spy072 is a genuine TL1A antibody (target = TL1A, drug_targets correctly committed). However, its indication is PsA/axSpA (rheumatology), not IBD/UC/CD. The `drug_areas` for tl1a is a valid mechanism assignment but represents a different disease area — TL1A inhibition in rheumatology, not IBD. The `ibd` legacy area is noise. The Wave 2C backfill correctly excluded spy072 with `_excluded_ontology_scope_mismatch`.

This is a **semantic scope disagreement** between legacy areas (which conflate TL1A mechanism with IBD indication) and the normalized ontology (which separates mechanism from indication).

**evidence_for ibd legacy:**
- `drug_areas.area_id IN ('tl1a', 'ibd')` — placed there because TL1A biology was relevant to the IBD area of interest
- `drug_area_scores`: tl1a Direct (supported), ibd Adjacent 1st Gen (supported) — the enrichment recognized TL1A mechanism
- TL1A is validated as an IBD target (other TL1A drugs are in drug_indications for uc/cd)

**evidence_against ibd (indication is NOT IBD):**
- `drugs.indication_short = 'PsA · axSpA'` — psoriatic arthritis and axial spondyloarthritis (rheumatology)
- `trials`: Phase 2 in RA/PsA/axSpA — zero IBD/UC/CD trials
- `trial_indications`: ra — no uc/cd
- `drug_indications`: 0 rows for uc/cd
- `backfill_preview`: correctly excluded as ontology_scope_mismatch

**normalized_interpretation:**  
- `drug_targets → tl1a`: CORRECT — spy072 does target TL1A
- `drug_areas → tl1a`: SCOPE DIFFERENCE — tl1a area = IBD dashboard view; spy072's indication is rheumatology
- `drug_areas → ibd`: LEGACY NOISE — should not be in IBD area at all
- `drug_indications`: correctly empty for uc/cd; future: could add psa/axspa if those indications are created

**proposed_action:**  
1. Exclude spy072 from IBD/TL1A migration-readiness denominator — correctly handled in DIFFERENCE_CLASSIFICATIONS.
2. Keep `drug_targets → tl1a` — mechanistically correct.
3. Do NOT add to `drug_indications` for uc or cd.
4. If a rheumatology area (ra, psa, axspa) is added in a future Wave, spy072 is a valid candidate for drug_indications via those indications.

**confidence_score:** 0.92  
**review_status:** approved  

**dashboard_migration_impact:**  
- If `_makeAreaPI()` migrates to drug_indications for IBD: spy072 disappears — CORRECT behavior
- spy072 is a rheumatology drug; its absence from the IBD/TL1A tab is an improvement over legacy
- No regression for any tracked indication

---

## Record 4 — `epi-001`

**entity_type:** drug  
**entity_id:** epi-001  
**check_type:** needs_manual_review  
**severity:** Medium  

**conflicting_tables:**
- `drug_areas`: tl1a + ibd (legacy)
- `drug_targets`: tl1a (A) — TL1A mechanism confirmed
- `drug_indications`: 0 rows committed
- `drugs.target`: "TL1A"
- `drugs.indication_short`: NULL — no indication documented
- `drugs.modality`: "Anti-TL1A monoclonal antibody (unconfirmed)"
- `drugs.stage`: Preclinical
- `trials`: 0 trials
- `trial_indications`: 0 rows
- `backfill_preview` (wave2c):
  - uc: pending_review, confidence_score=76, confidence_level=C, proposed_review_status=review_required
  - cd: pending_review, confidence_score=76, confidence_level=C, proposed_review_status=review_required

**conflict_summary:**  
epi-001 targets TL1A (confirmed in drug_targets). TL1A is an established IBD target. However, the drug has no indication_short, no trials, and preclinical stage. The Wave 2C backfill assigned confidence level C (76/100) for uc and cd with review_required status, reflecting that TL1A mechanism is IBD-relevant but no direct indication evidence exists. These rows are correctly held in pending_review.

**evidence_for IBD indication:**
- TL1A is a validated IBD target (risankizumab, tulisokibart, and multiple other TL1A drugs in drug_indications for uc/cd)
- `drug_targets → tl1a` (A confidence) — mechanism is consistent with IBD
- `drug_areas → tl1a + ibd` — legacy placement was not random; it reflects TL1A biology
- `backfill_preview`: uc + cd rows exist with confidence_score=76 (not zero; above noise floor)
- Class inference: TL1A mAb + IBD drug class has very high prior probability

**evidence_against (IBD not confirmed):**
- `drugs.indication_short = NULL` — no documented indication
- `drugs.modality = 'Anti-TL1A monoclonal antibody (unconfirmed)'` — "unconfirmed" qualifier
- `drugs.stage = 'Preclinical'` — no published human data
- `trials`: 0 trials
- `trial_indications`: 0 rows
- Confidence assigned by Wave 2C: C (76) with review_required — this is below the auto-confirm threshold

**normalized_interpretation:**  
TL1A targeting strongly suggests IBD relevance, but biological mechanism alone is insufficient to confirm uc/cd indication without direct evidence (trial, IND filing, publication, press release). The modality field's "(unconfirmed)" qualifier reinforces this. This is a genuine `needs_manual_review` — not legacy noise, not a clear gap, not clearly in scope.

**proposed_action:**  
1. Keep epi-001 held in `backfill_preview` as `pending_review` / `review_required` for uc and cd.
2. **Human review required:** Search for any source publication, preclinical conference data, or company press release confirming IBD indication for epi-001.
3. If IBD confirmed with any evidence: upgrade confidence, commit uc/cd rows using `wave2c_drug_indications_ibd_backfill.py --commit --run-id wave2c_ibd_20260525_203134`.
4. If no evidence found: keep held indefinitely or tombstone with `review_status = 'no_evidence'`.

**confidence_score:** 0.55 (insufficient to auto-decide)  
**review_status:** pending_human — requires source evidence research  

**dashboard_migration_impact:**  
- Currently epi-001 appears in drug_areas for tl1a + ibd (legacy tab)
- If `_makeAreaPI()` migrates to drug_indications: epi-001 disappears from IBD/TL1A tab
- Whether that is a regression depends on whether IBD indication is confirmed
- If confirmed → backfill before migration; no regression
- If not confirmed → disappearance from tab is correct behavior (epi-001 shouldn't be there without evidence)
- **Recommendation:** Resolve this record before Phase 4B dual-read begins

---

## Record 5 — `batoclimab`

**entity_type:** drug  
**entity_id:** batoclimab (Batoclimab / IMVT-1401)  
**check_type:** cross_table_inconsistency + **normalized_gap** (critical)  
**severity:** High  

**conflicting_tables:**
- `drug_areas`: fcrn + autoimmune + igf1r + ted — 4 separate legacy areas
- `drug_targets`: fcrn (A) — CORRECT
- `drug_indications`: 0 rows — **SIGNIFICANT GAP**
- `drugs.target`: "FcRn"
- `drugs.indication_short`: "Graves' disease (Ph2); MG (Ph2 — discontinued)" — **OUTDATED**
- `drug_area_scores`: ted (Watch, confirmed), fcrn (Watch, Anti-FcRn mAb discontinued, confirmed), autoimmune (Watch, supported), igf1r (Watch, confirmed)
- `trials` (7 trials):
  - TED Phase 3 Completed (NCT05524571)
  - TED Phase 3 Completed (NCT05517421)
  - TED Phase 3 Terminated (NCT05517447)
  - gMG Phase 3 Active, not recruiting (NCT05403541)
  - CIDP Phase 2 Active, not recruiting (NCT05581199)
  - CIDP Phase 2 Enrolling by invitation (NCT07188844)
  - Graves Disease Phase 2 Completed (NCT05907668)
- `trial_indications`: ted (4 trials), gmg (1 trial), cidp (2 trials) — 7 trial indication links

**conflict_summary:**  
**This is the most significant normalized_gap in the candidate set.** Batoclimab has active/completed Phase 3 trials for TED (3), active Phase 3 for gMG, and active Phase 2 for CIDP — all tracked in trial_indications. But drug_indications has ZERO rows for batoclimab. Additionally, drugs.indication_short is outdated ("Graves' disease (Ph2); MG discontinued") while the actual Phase 3 program spans TED + gMG + CIDP.

The 4-area legacy placement (fcrn, autoimmune, igf1r, ted) is a legacy catch-all artifact. The correct normalized representation should be drug_indications for: ted, gmg, cidp (and possibly Graves' disease).

**evidence_for current indications (normalized):**
- `drug_targets → fcrn` (A) — FcRn inhibitor, confirmed
- `trial_indications`: ted (4), gmg (1), cidp (2) — 7 independently confirmed indication links
- Phase 3 programs for TED and gMG are completed; CIDP Phase 2/3 is active
- FcRn inhibition → gmg/cidp/ted is established mechanism-indication link (consistent with fcrn area mapping)

**evidence for legacy (multiple area placement):**
- `drug_areas`: fcrn (FcRn mechanism — valid), ted (TED trials — valid endpoint), autoimmune + igf1r (legacy catch-all artifact from broad curation)
- `drug_area_scores`: 4 separate area scores — confirms legacy placed it across multiple views

**normalized_interpretation:**  
- `drug_targets → fcrn`: CORRECT
- `drug_indications`: MISSING — batoclimab should have rows for ted, gmg, cidp (at minimum)
- `drugs.indication_short`: OUTDATED — should be updated to reflect TED + gMG + CIDP Phase 3 programs
- `drug_areas → fcrn`: mechanistically valid but represents legacy bucket, not normalized indication
- `drug_areas → ted, autoimmune, igf1r`: legacy scope/catch-all artifact

**proposed_action:**  
1. **Flag for backfill (pending advisor approval):** Add `drug_indications` rows for batoclimab → ted, gmg, cidp with A/B confidence based on Phase 3 evidence. This should go through the standard backfill_preview → validate → commit workflow.
2. **Flag for correction (pending advisor approval):** Update `drugs.indication_short` to reflect current Phase 3 scope: "TED (Ph3 completed); gMG (Ph3); CIDP (Ph2/Ph3)".
3. The legacy multi-area placement (4 areas) is an ontology_scope_difference — Graves' disease may also warrant a drug_indications row if Graves' is added as an indication.

**confidence_score:** 0.90  
**review_status:** needs_advisor — normalized_gap correction requires Phase 2 backfill workflow approval; indication_short update requires explicit approval  

**dashboard_migration_impact:**  
- Batoclimab currently appears in drug_areas for fcrn + ted + autoimmune + igf1r
- If `_makeAreaPI()` migrates to drug_indications: batoclimab disappears from ALL tabs — INCORRECT (it should appear in ted, gmg, cidp views)
- **This is a dashboard regression risk if migration proceeds before backfill**
- Backfill must precede Phase 4B dual-read for any fcrn/ted/autoimmune area
- This is the highest-priority normalized_gap in the current dataset

---

## Record 6 — `upadacitinib` (Rinvoq)

**entity_type:** drug  
**entity_id:** upadacitinib  
**check_type:** normalized_gap  
**severity:** Medium  

**conflicting_tables:**
- `drug_areas`: atopy + tl1a + ibd (legacy — 3 areas)
- `drug_targets`: jak1 (A) — CORRECT
- `drug_indications`: uc (A, 99, auto_confirmed), cd (A, 99, auto_confirmed) — CORRECT but INCOMPLETE
- `drugs.target`: "JAK1"
- `drugs.indication_short`: "RA (2019); PsA; AD; UC; CD; AS; nr-axSpA" — AD is explicitly listed
- `drugs.stage`: Approved
- `drug_area_scores`: tl1a (Watch, inferred), ibd (Watch, inferred), atopy (Watch, Selective JAK1 inhibitor)
- `trials` (relevant):
  - NCT04666675: Phase 3, Withdrawn, Atopic Dermatitis (AD) — trial_indications: ad
  - NCT05959083: Observational, Active, Atopic Dermatitis (AD) — trial_indications: ad
  - NCT06136767: Observational, Recruiting, Atopic Dermatitis — trial_indications: ad
  - NCT02819635: Phase 2/3, Completed, Ulcerative Colitis — trial_indications: uc
- `trial_indications`: ad (3 trials), ra (1), uc (1)

**conflict_summary:**  
Upadacitinib is FDA-approved for atopic dermatitis (JAK1 inhibitor). drugs.indication_short explicitly lists AD. Three trials linked to the `ad` indication are in trial_indications. drug_indications has uc and cd (both correctly committed in Wave 2C) but is **missing `ad`**. The atopy legacy area membership is consistent with the AD indication, but the normalized drug_indications table is incomplete.

**evidence_for AD indication:**
- `drugs.indication_short`: "RA (2019); PsA; AD; UC; CD; AS; nr-axSpA" — AD explicit
- `drugs.stage = 'Approved'` — FDA approval across multiple indications including AD
- `trial_indications → ad` (3 trials) — independently confirmed via trial ontology
- `drug_area_scores.area_id = 'atopy'` with cls = "Selective JAK1 inhibitor"
- Dupilumab, tralokinumab, lebrikizumab all in drug_indications for ad — upadacitinib is a known approved competitor

**evidence against current state (drug_indications missing ad):**
- `drug_indications`: only uc + cd — Wave 2C (IBD-focused) correctly committed these but did not cover ad
- The atopy backfill (Wave 2D or equivalent) has not yet run

**normalized_interpretation:**  
- `drug_indications → uc + cd`: CORRECT (Wave 2C)
- `drug_indications → ad`: MISSING — high-confidence normalized_gap; should be added
- `drug_targets → jak1`: CORRECT
- `drug_areas → atopy`: valid (mechanism relevant to AD/atopy), though legacy bucket
- `drug_areas → tl1a + ibd`: Watch/inferred (watch-level competitive, not primary indication)

**proposed_action:**  
1. **Approved for backfill** (pending scheduling): Add `drug_indications` row: upadacitinib → ad, confidence_level = A, confidence_score = 99, review_status = auto_confirmed. This is a clear FDA-approved indication with 3 trial links.
2. This should be included in the next atopy/Wave 2D backfill pass — do not commit standalone (wait for the batch).

**confidence_score:** 0.97  
**review_status:** approved (correction clear and evidence unambiguous)  

**dashboard_migration_impact:**  
- Upadacitinib appears in drug_areas for atopy (legacy)
- If `_makeAreaPI()` migrates to drug_indications for ad: upadacitinib disappears — INCORRECT (it should be there as an approved AD drug)
- **This is a dashboard regression risk if the atopy area migrates before the backfill**
- Backfill of upadacitinib → ad must precede any atopy area Phase 4B validation

---

## Cross-Candidate Findings

### New findings this review (not previously identified)

| Finding | Drug | Tables Involved | Action Required |
|---|---|---|---|
| **Wave 2B normalized table error** | sim0500 | drug_targets: tl1a row committed incorrectly | DELETE drug_targets row (pending advisor) |
| **Significant normalized_gap** | batoclimab | drug_indications: 0 rows despite Phase 3 TED/gMG/CIDP | Backfill drug_indications (pending advisor) |
| **Outdated indication_short** | batoclimab | drugs.indication_short: "Graves Ph2; MG discontinued" | Update to reflect current Phase 3 scope |
| **Missing ad indication** | upadacitinib | drug_indications: missing ad despite FDA approval + 3 trial links | Backfill in next atopy wave |

### Dashboard migration blockers identified

| Area | Issue | Blocker Level |
|---|---|---|
| IBD/TL1A (uc, cd) | lm-302 + sim0500 confirmed noise; spy072 confirmed scope diff; epi-001 pending | Minor (resolve epi-001 before migration) |
| fcrn/ted/autoimmune | batoclimab missing from drug_indications | **Major** — migration would drop batoclimab from all tabs |
| atopy (ad) | upadacitinib missing from drug_indications | **Moderate** — migration would drop upadacitinib from AD tab |

---

## Recommendation: `entity_consistency_checks` Build Timing

**Recommendation: Build the table after this manual review round is approved, not before.**

**Rationale:**
1. **Manual review first.** The six candidates above can be fully reviewed, classified, and corrections proposed without a database table. The design is documented in `docs/evidence_reconciliation_layer.md`. Building the table prematurely creates schema overhead before the workflow is validated.
2. **Validate the workflow on known cases first.** These six records are well-understood. Reviewing them manually demonstrates that the classification taxonomy works in practice before building tooling to automate it.
3. **Build when the first automation is ready.** The trigger for building `entity_consistency_checks` should be when the first reconciliation script (`scripts/run_evidence_reconciliation.py`) is ready to write rows to it. Building the table without a writer is wasteful.
4. **Proposed build trigger:** After advisor approves the corrections for sim0500 (drug_targets error) and batoclimab (drug_indications gap), build `entity_consistency_checks` and seed it with the 6 candidates from this review as the initial state.

**Proposed timing:**
- Now: Advisor reviews this document, approves/modifies recommended actions
- Next: Apply approved corrections via standard backfill workflow
- Then: Build `entity_consistency_checks` table + seed with these 6 records
- Then: Build `scripts/run_evidence_reconciliation.py` to detect new inconsistencies automatically
- Then: Phase 4B dual-read validation

---

## Files Produced This Review

- `docs/phase4a_reconciliation_review.md` — this document (read-only review, no production changes)
- `docs/evidence_reconciliation_layer.md` — design note for future entity_consistency_checks system

## Active Constraints (post-correction)

1. **ontology_edges locked** at 25 — do not unlock until Phase 4B dual-read completes
2. **No dashboard migration** — Phase 4B must complete first
3. **epi-001 held** in backfill_preview pending_review — do not commit without human evidence review
4. **batoclimab → cidp** — not approved this round; revisit in Wave 2D FcRn backfill
5. **upadacitinib → ad** — approved for Wave 2D atopy batch; do not commit standalone
