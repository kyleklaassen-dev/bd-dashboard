# Phase 4C — 10-Drug Modal Verification Sprint

**Completed:** 2026-05-25 (Session 53o)  
**Purpose:** Verify modal dual-read classification for all 10 test drugs before IBD flag activation  
**Method:** Cross-reference drug_areas (legacy), drug_indications (normalized), drug_area_scores, and entity_consistency_checks per drug. Browser modal output simulated from Supabase data (consistent with _runPhase4BModalDualRead logic).

---

## Verification Matrix

| # | Drug | Legacy areas | Normalized inds | Modal status | ECC entry | IBD block |
|---|---|---|---|---|---|---|
| 1 | sim0709 | ibd, tl1a | cd (93), uc (93) | compare_pass_oos_adjusted | — | ❌ No |
| 2 | batoclimab | autoimmune, fcrn, igf1r, ted | cidp (92), gmg (92), ted (95) | acceptable_mismatch | corrected/resolved | ❌ No |
| 3 | lm-302 | tl1a | (none) | needs_manual_review → ECC accepted | closed/accepted | ❌ No |
| 4 | spy072 | ibd, tl1a | (none) | compare_pass_oos_adjusted | closed/accepted | ❌ No |
| 5 | epi-001 | ibd, tl1a | (none) | acceptable_mismatch (held) | open/held | ❌ No* |
| 6 | upadacitinib | atopy, ibd, tl1a | ad (97), cd (99), uc (99) | compare_pass_oos_adjusted | corrected/resolved | ❌ No |
| 7 | teprotumumab | igf1r, ted | ted (97) | match | — | ❌ No |
| 8 | dupilumab | atopy, il4ra, respiratory, tslp | ad, asthma, copd, eoe, chronic_urticaria | compare_pass_oos_adjusted | — | ❌ No |
| 9 | efgartigimod | autoimmune, fcrn | cidp (87), gmg (95) | match | — | ❌ No |
| 10 | risankizumab | ibd, tl1a | cd (89), uc (89) | compare_pass_oos_adjusted | — | ❌ No |

*epi-001 gate satisfied by "resolved OR formally accepted as held through Phase 5" rule (ECC: open/held).

---

## Per-Drug Analysis

### 1. sim0709
- **Target:** TL1A×IL-23 bispecific
- **Legacy:** drug_areas = {ibd (Direct), tl1a (Direct)}
- **Normalized:** drug_indications = {cd (93, phase1, auto_confirmed), uc (93, phase1, auto_confirmed)}
- **Mapping:** cd+uc → ibd ✅. tl1a area = target classification (OOS — established Phase 4B for 17 drugs)
- **Rationale:** sim0709 appears in drug_areas/tl1a because it targets TL1A. The normalized path captures the disease indication (IBD) correctly. tl1a area is target-driven, not indication-driven — standard OOS pattern.
- **Status: compare_pass_oos_adjusted**

---

### 2. batoclimab
- **Target:** Anti-FcRn mAb (discontinued) + TED program
- **Legacy:** drug_areas = {autoimmune (Watch), fcrn (Watch), igf1r (Watch), ted (Watch)}
- **Normalized:** drug_indications = {cidp (92, phase2, auto_confirmed), gmg (92, phase3, review_required), ted (95, phase3, review_required)}
- **Mapping:** cidp+gmg → fcrn/autoimmune areas ✅; ted → ted/igf1r ✅
- **Difference:** igf1r area in legacy is a catch-all artifact (batoclimab listed under igf1r because TED was historically tracked under igf1r tab). Normalized ted indication correctly covers the TED program.
- **ECC:** `missing_ted_gmg_indications` → corrected/resolved. igf1r/autoimmune legacy catch-all documented in conflict_summary.
- **Status: acceptable_mismatch** (igf1r = legacy catch-all, documented and accepted)

---

### 3. lm-302
- **Target:** CLDN18.2 ADC (anti-TL1A mislabeled in legacy)
- **Legacy:** drug_areas = {tl1a (Watch)}
- **Normalized:** drug_indications = {} (none)
- **Mapping:** tl1a area = legacy noise. lm-302 is a CLDN18.2 ADC — no TL1A biology.
- **ECC:** `legacy_ibd_tl1a_noise` → closed/accepted. Correctly absent from normalized source.
- **Status: needs_manual_review** (auto-classification for absent normalized rows) → **ECC accepted** → fully explainable, no action needed
- **Note:** Not an IBD drug. tl1a area appearance is legacy noise only.

---

### 4. spy072
- **Target:** Anti-TL1A (rheumatology-focused)
- **Legacy:** drug_areas = {ibd (Adjacent), tl1a (Direct)}
- **Normalized:** drug_indications = {} (none)
- **Phase 4B:** spy072 classified as OOS in IBD harness — one of 3 OOS in the ibd compare_pass_oos_adjusted run (epi-001/sim0500/spy072). 94% raw → 100% adjusted.
- **ECC:** `tl1a_rheumatology_scope` → closed/accepted. Ontology scope difference — rheumatology focus, IBD indication not confirmed.
- **Status: compare_pass_oos_adjusted** (Phase 4B OOS classification accepted; normalized correctly excludes)

---

### 5. epi-001
- **Target:** Anti-TL1A (preclinical)
- **Legacy:** drug_areas = {ibd (Direct), tl1a (Watch)}
- **Normalized:** drug_indications = {} (none — held in backfill_preview as pending_review)
- **Phase 4B:** classified as OOS in IBD harness
- **ECC:** `ibd_indication_evidence_gap` → open/held. confidence=0.55. Do NOT commit without source evidence.
- **Status: acceptable_mismatch** (held pending source evidence)
- **IBD block:** Gate satisfied by updated rule — "epi-001 resolved OR formally accepted as held through Phase 5." ECC documents the hold explicitly. epi-001 is a preclinical asset with ambiguous IBD signal; intentional exclusion from normalized output is the correct conservative posture.

---

### 6. upadacitinib
- **Target:** JAK1 inhibitor (approved IBD + RA + atopy)
- **Legacy:** drug_areas = {atopy (Watch), ibd (Watch), tl1a (Watch)}
- **Normalized:** drug_indications = {ad (97, approved, auto_confirmed), cd (99, auto_confirmed), uc (99, auto_confirmed)}
- **Mapping:** cd+uc → ibd ✅; ad → atopy ✅. tl1a area = OOS (JAK1 appears in tl1a legacy as JAK inhibitor catch-all)
- **ECC:** `atopy_ad_gap` → corrected/resolved (ad indication inserted Session 53n)
- **Status: compare_pass_oos_adjusted** (ibd+atopy fully matched; tl1a OOS)

---

### 7. teprotumumab
- **Target:** IGF-1R mAb (TED — approved)
- **Legacy:** drug_areas = {igf1r (Watch), ted (Direct)}
- **Normalized:** drug_indications = {ted (97, approved, auto_confirmed)}
- **Mapping:** ted indication covers both igf1r+ted area presence. teprotumumab targets IGF-1R specifically for TED disease — one indication, two area memberships in legacy. Normalized correctly uses the disease indication.
- **Status: match** (ted indication fully explains igf1r+ted legacy areas)

---

### 8. dupilumab
- **Target:** IL-4Rα/IL-13 dual blocker (multiple approved indications)
- **Legacy:** drug_areas = {atopy (Adjacent), il4ra (Direct), respiratory (Adjacent), tslp (Watch)}
- **Normalized:** drug_indications = {ad (87), asthma (87), chronic_urticaria (87), copd (87), eoe (87)} — all pattern_match/sampling_queue
- **Mapping:** ad+chronic_urticaria+eoe → atopy ✅; asthma+copd → respiratory ✅; il4ra/tslp = target areas (OOS — same pattern as tl1a)
- **Note:** All normalized rows are pattern_match/sampling_queue (conf=87), not auto_confirmed. Valid IBD-irrelevant coverage — relevant caveat for future IL-4Rα/TSLP tab migration but not blocking here.
- **Status: compare_pass_oos_adjusted** (atopy+respiratory covered; il4ra+tslp are target-driven areas = OOS)

---

### 9. efgartigimod
- **Target:** Anti-FcRn mAb (Vyvgart — approved gMG)
- **Legacy:** drug_areas = {autoimmune (Watch), fcrn (Direct)}
- **Normalized:** drug_indications = {cidp (87, pattern_match, sampling_queue), gmg (95, approved, auto_confirmed)}
- **Mapping:** cidp+gmg → fcrn/autoimmune ✅
- **Note:** drug_area_scores has efgartigimod/ted=Direct but drug_areas has no ted row. Score without area membership — not a modal issue.
- **Status: match** (cidp+gmg correctly map to fcrn/autoimmune)

---

### 10. risankizumab
- **Target:** IL-23p19 mAb (Skyrizi — approved CD, UC, PsA)
- **Legacy:** drug_areas = {ibd (Adjacent), tl1a (Adjacent)}
- **Normalized:** drug_indications = {cd (89, pattern_match, sampling_queue), uc (89, pattern_match, sampling_queue)}
- **Mapping:** cd+uc → ibd ✅. tl1a area = OOS (IL-23 inhibitor appearing in tl1a area as IBD biologic catch-all)
- **Note:** pattern_match/sampling_queue rows (conf=89). Risankizumab is approved for CD and UC — the indication is correct even with pattern_match provenance. Lower-confidence provenance is not a quality concern for a well-established approved drug.
- **Status: compare_pass_oos_adjusted** (ibd covered via cd+uc; tl1a OOS)

---

## Summary — IBD-Relevant Drugs

| Drug | IBD in legacy | IBD inds in normalized | Mapping | OOS/hold status | Clear for activation |
|---|---|---|---|---|---|
| sim0709 | ✅ (Direct) | cd (93), uc (93) | ✅ | tl1a OOS | ✅ |
| spy072 | ✅ (Adjacent) | — | OOS classified | Phase 4B OOS + ECC accepted | ✅ |
| epi-001 | ✅ (Direct) | — | Held | ECC open/held — gate satisfied | ✅ |
| upadacitinib | ✅ (Watch) | cd (99), uc (99) | ✅ | tl1a OOS | ✅ |
| risankizumab | ✅ (Adjacent) | cd (89), uc (89) | ✅ | tl1a OOS | ✅ |

**5/5 IBD-relevant drugs: all classified, all explainable, none blocking.**

---

## Sprint Outcome

| Metric | Result |
|---|---|
| Drugs verified | 10/10 |
| Unexplained mismatches | 0 |
| IBD blockers | 0 |
| ECC rows cited | 5 (all pre-existing — no new rows required) |
| New entity_consistency_checks needed | 0 |
| Pattern_match/sampling_queue IBD drugs | risankizumab (89), dupilumab (not IBD) — noted, not blocking |

---

## Pre-Activation Checklist — Candidate 1 (IBD)

| Gate | Status |
|---|---|
| 10-drug modal sprint complete | ✅ COMPLETE (2026-05-25) |
| No unexplained modal mismatches | ✅ All 10 classified |
| epi-001 resolved OR formally held through Phase 5 | ✅ ECC open/held — gate satisfied |
| cizutamig resolved | ⏸ Pending (TED indication scope review — not blocking IBD) |
| IBD tab loads without console errors (flag=true) | ⏸ Pending browser validation |
| IBD count matches expected normalized output | ⏸ Pending browser validation |
| Legacy fallback works when flag=false | ✅ Confirmed (current deploy) |

**Recommendation:** 4 of 7 gates satisfied from data. Remaining 3 require browser run with `useNormalizedIBD=true`. cizutamig is TED-scope only — does not block IBD activation.

---

## Next Step for Flag Activation

1. Set `FEATURE_FLAGS.useNormalizedIBD = true` locally
2. Load IBD tab in browser
3. Verify no console errors
4. Run `window.showPhase4Compare()` — confirm IBD comparison record
5. Spot-check drug count: expect ~50 drugs (excluding sim0500, spy072, epi-001 as OOS)
6. Confirm legacy tab still works when flag reverted to `false`
7. Get advisor go → deploy with flag=true → log in update_log.md
