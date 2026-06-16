# Governance Violations Triage — 2026-06-15

Triage of `governance_violations WHERE resolved=false`. Scope: classify + resolve clear
false-positives only. No data changes (no deletes, merges, stage-flips, approved-flips, or
edge removals) — those are flagged for Kyle's review.

## Table schema (`governance_violations`)
| column | notes |
|---|---|
| `id` | int PK |
| `table_name` | the table the violation references (e.g. `drugs`, `companies`, `entity_edges`, `meridian_issue_factcheck`) |
| `row_id` | the referenced row key (drug id, company id, edge uuid, or a comma-list) |
| `rule_name` | the check that fired (e.g. `phase_inflation_audit`, `inferred_target_unverified`, `trial_misattributed_<NCT>`, `country_conflict`/`entity_identity_mismatch`, `stage_attribution_review`, `mechanism_target_inconsistency`, `missing_originator_obscure`, `ambiguous_identity`, `draft_format_contradicts_db`) |
| `description` | human-readable detail of the violation |
| `detected_at` | timestamptz |
| `resolved` | bool |
| `resolved_at` | timestamptz |
| `resolved_by` | text (e.g. `claude-cowork`) |
| `resolution_notes` | text — why resolved |
| `enrichment_run_id` | nullable FK to the run that detected it |

## Counts
- **Before:** 86 unresolved.
- **Resolved this pass (clear false-positives):** 12.
- **After:** 74 unresolved.

## Breakdown by rule (the 86 starting rows)
| rule | count | disposition |
|---|---|---|
| `trial_misattributed_<NCT>` | 48 | **B/C** — real wrong-asset links; fix = unlink (needs review). NOT casing. |
| `phase_inflation_audit` | 17 | **C** — stage-confidence; fix = possible stage-flip → Kyle approval. |
| `inferred_target_unverified` | 15 | **A (12 resolved)** + **C (3 ambiguous)** |
| `stage_attribution_review` | 2 | **C** — Phase 3 unverified in China CDE; fact-check. |
| `mechanism_target_inconsistency` | 1 | **C** — primary-source verification needed. |
| `missing_originator_obscure` | 1 | **C** — hold in research queue. |
| `ambiguous_identity` | 1 | **C** — HOLD, never auto-map. |
| `draft_format_contradicts_db` | 1 | **B/C** — bispecific/monospecific contradictions; review. |

> Note: the known casing/punctuation `trial_misattributed` and subsidiary/LEI
> `country_conflict` false-positive classes from error memory were already cleared in the prior
> sweep (86→24 on 2026-06-11). **Zero** casing/punctuation or subsidiary/LEI cases remain in this
> batch — confirmed by scanning all 86 descriptions.

---

## (A) Clear false-positives RESOLVED this pass — 12
All `inferred_target_unverified` on `entity_edges`. These are biologically impossible or
redundant auto-API inferred TARGETS edges where the **curated target is provably correct** (DB
mechanism cross-checked). Resolution closes the governance flag only; the edge itself was **left
in place** (deleting edges needs approval — flagged below).

| id | drug | bad inferred target | why FP |
|---|---|---|---|
| 163 | adalimumab (anti-TNF-α mAb) | cd40l | impossible for anti-TNF mAb |
| 164 | adalimumab | il13 | impossible |
| 167 | infliximab (anti-TNF-α mAb) | il23r | impossible |
| 172 | rituximab (anti-CD20 mAb) | jak | surface-antigen mAb can't hit intracellular kinase |
| 166 | ustekinumab (anti-p40 mAb) | il13 | impossible |
| 165 | ustekinumab | il23p19 | binds shared p40, not IL-23-specific p19 |
| 160 | benralizumab (anti-IL-5Rα mAb) | il5 | binds receptor, not the IL-5 ligand |
| 168 | filgotinib (selective JAK1) | tyk2 | contradicts selective-JAK1 mechanism |
| 169 | upadacitinib (JAK1) | tyk2 | not a primary target |
| 170 | zemprocitinib (selective JAK1) | tyk2 | contradicts selective-JAK1 mechanism |
| 171 | filgotinib | jak (generic) | redundant/less-precise than curated jak1 |
| 173 | upadacitinib | jak (generic) | redundant/less-precise than curated jak1 |

**Follow-up (needs approval):** the 12 underlying noisy edges should eventually be pruned from
`entity_edges`. That is a delete and was deliberately NOT performed.

---

## (B) True issues needing a data fix — flagged, NOT auto-fixed

### B1. `trial_misattributed_<NCT>` — wrong asset linked (48 rows)
These are **not** casing/punctuation issues. In each case a drug record is linked to an NCT whose
listed interventions are a *different* drug. The detector itself warns "⚠ VERIFY before
unlinking." Fix = unlink the trial from the drug (a data change → review before executing).

Clear wrong-asset links (intervention is plainly a different molecule):
- 102 ab001 → NCT00555828 (allogeneic mesenchymal precursor cells)
- 104 abs-101 → NCT06730126 (soquelitinib / ITK inhibitor)
- 105 apg279 → NCT06395948 (APG777)
- 106 apg333 → NCT06137170 (regorafenib real-world CRC study)
- 121 kt501 → NCT06630806 (SAR446523)
- 123 mepolizumab → NCT06748053 (anti-TSLP GSK5784283)
- 124 metis-mrna-cd19bcmacd3 → NCT07526350 (MTS109)
- 125/126 mg-k10 → NCT01762761 (eltrombopag) / NCT06906081 (finerenone)
- 130 mt-251 → NCT07219368 (MT-201)
- 131 nemolizumab → NCT04350359 (tibial nerve stimulation)
- 132 ocrelizumab → NCT04486716 (ofatumumab)
- 133 omalizumab → NCT06162728 (briquilimab)
- 134/135 ravulizumab → NCT04861259 (crovalimab) / NCT05744921 (pozelimab+cemdisiran)
- 136 risankizumab → NCT02902094 (drug-eluting balloon venoplasty)
- 142/143 ruxolitinib-topical → NCT02553265 (carbidopa) / NCT07606703 (madecassoside)
- 146 spx306 → NCT06259552 (SPX-303)
- 147 spy230 → NCT07012395 (SPY001/SPY002/SPY003 — related programme, not spy230)
- 149 tocilizumab → NCT04366245 (hyperimmune plasma, COVID)
- 151 tulisokibart → NCT05104333 (COVID booster vaccine)
- 154 verekitug--upb-101 → NCT06981078 (verekitug COPD — likely the right molecule, wrong code form; verify)
- 156 win027 → NCT07120503 (WIN378)
- 191/192 kyv-101 → NCT05361551 (liver ablation) / NCT05765071 (botulinum toxin)
- 121-series, 138 risankizumab-lutikizumab-or-trosunilimab → NCT06548542 (interventions DO include all three; the *combo-id* record may be a modelling artifact — review whether the combo drug record should exist)

Recommended: unlink these NCTs from the named drug records. **Approval not strictly required for a
plain trial<->drug unlink, but per the detector's own warning each should be eyeballed; do these
in a single reviewed batch.**

### B2. `draft_format_contradicts_db` (id 68) — format contradictions in Issue prose
Post-draft factcheck found prose describing bispecific/monospecific status inconsistently with
`drugs`. Per canonical fact in error memory: ALX001 = bispecific (DB correct, draft wrong);
SPY072 = monospecific (DB correct, draft wrong). XmAb942, Omvoh/mirikizumab also flagged. These
are **draft/prose** errors, not DB errors — fix = regenerate the affected Issue, do not touch the
`drugs` rows. Already covered by the `audit_draft_against_db` gate.

---

## (C) Ambiguous / needs human judgment — flagged, NOT auto-fixed

### C1. `inferred_target_unverified` — curated target may be the GAP (3 rows)
Unlike the 12 above, here the inferred edge may be *more* correct than the curated target, so
closing the flag would risk hiding a real data gap:
- **159 cendakimab**: curated `il13ra1`, inferred `il13`. Cendakimab is in reality an
  **anti-IL-13 ligand** antibody; the inferred `il13` edge may be the correct one and the curated
  `il13ra1` (and DB mechanism "IL-13Rα1 antagonist") may be **wrong**. Verify against
  primary source before deciding which target stands. (Target correction → review.)
- **161/162 tofacitinib**: curated generic `jak`, inferred `jak1` / `tyk2`. Tofacitinib is a
  pan-JAK inhibitor (JAK1/JAK3 primary, some TYK2/JAK2). The inferred edges are biologically real
  refinements; the curated `jak` is over-broad. Decide whether to upgrade curated targets to the
  specific isoforms. (Target enrichment, not noise.)

### C2. `phase_inflation_audit` (17 rows) — stage-confidence, possible stage-flip
All 17 are drugs at Phase 1/2–Phase 3 with **zero registrational footprint** (no NCT, no
trial_facts/results, no FDA/EU approval, no China trials). The detector asks for human review
before relying on the stage. Recommended fix = set `stage_confidence='low'` (informational, safe)
and verify each stage against primary source; any actual **stage downgrade is an `approved`/stage
write → requires Kyle's approval**.
Rows: 85 gb1275, 86 ky1044, 87 eta1001, 88 srf-231, 89 shr0817, 90 xb3217, 91 rgx-181,
92 ionis-tslp-25rx, 93 hlx36 (desc marked "CONFIRMED"), 94 lq082, 95 calt-100, 96 es302,
97 hr7044, 98 nvx-360, 99 ear-2001 (HXN-1001), 100 generate-uc (GB-3250), 101 bel512.

### C3. `stage_attribution_review` (2 rows) — Phase 3 unverified in China CDE
- 83 lbl-053, 84 hlx36 — marked Phase 3 but zero footprint in China CDE/NMPA. Either a global
  trial exists (check CT.gov) or the stage is unverified. Fact-check; stage change → approval.

### C4. `mechanism_target_inconsistency` (id 59)
shr0817 (target=IL-4Rα, mechanism text says IL-23/p19) and hlx36 (target=IL-4Rα, mechanism text
says IL-17A). Internal contradiction; web search could not disambiguate (found sibling SHR-1819).
Needs primary-source verification before any field edit.

### C5. `missing_originator_obscure` (id 65)
5 early-stage obscure codes (calt-100, dam-51, eta1001, nvx-360, xb3217) with no searchable
public presence. Hold in research queue; resolve as they disclose. Note in description: several
siblings already resolved 2026-06-06; ab001/sm-101 moved to `ambiguous_identity`.

### C6. `ambiguous_identity` (id 67) — HOLD, do not auto-map
- **AB001**: overloaded across PD-L1 small molecule / PSMA radioligand / IL-21R / BCMA decoy.
- **SM-101**: dual identity (valziflocept/SHP-652 soluble FcγRIIb fusion vs SMP-534 p38/FcγRIIa);
  DB currently holds a third unverified CD19×CD3 TCE attribution that needs scrubbing.
Auto-mapping is explicitly unsafe. Leave flagged; resolve only with a verified single identity
(identity correction → review).

---

## Top true issues needing attention (priority for Kyle)
1. **48 mis-attributed trials (B1)** — wrong NCTs linked to drug records; pollute landscape/stage
   inference. Recommend a single reviewed unlink batch.
2. **SM-101 false third identity (C6)** — DB holds an unverified CD19×CD3 attribution on a record
   that is really a soluble FcγRIIb fusion. Scrub after identity confirmation.
3. **cendakimab target may be wrong (C1, id 159)** — DB says IL-13Rα1 antagonist; drug is anti-IL-13.
4. **17 phase-inflation suspects (C2)** — stages claimed with zero registrational footprint;
   set stage_confidence='low' and verify before relying on these stages.

---

## Trial mis-attribution fixes (executed) — 2026-06-15 (claude-cowork)

Scope: the 48 unresolved `trial_misattributed_<NCT>` violations from this batch. Method: located the
actual stored link (the mis-link lives in **`catalysts.related_trial_id`** for most rows, and in
**`trial_facts` + `trial_registries`** for a few — `drugs` has no trial_ids array), verified each
NCT against **ClinicalTrials.gov API v2** interventions, and only unlinked where the trial is
*provably* a different molecule. Conservative rule applied: registries / observational / background-
therapy studies where the claimed drug is plausibly in scope were **left for human review**.

### Outcome counts
- **Verified-wrong + UNLINKED (fix applied): 14**
  - 13 by deleting an auto-generated readout catalyst (the catalyst's label/notes were derived
    entirely from the wrong NCT, so the whole row was spurious).
  - 1 (spy230) by deleting the `trial_facts` + `trial_registries` rows.
- **False-positive — link was CORRECT, flag cleared, link kept: 4**
- **Stale — mis-link already removed in a prior cleanup (no live link in trial_facts /
  trial_registries / catalysts), flag closed as correction-in-effect: 17**
- **Skipped / ambiguous (drug plausibly involved or ct.gov generic) — LEFT UNRESOLVED for human
  review: 13**
- No core entity (drug/company) was deleted or merged. No stage / approved / brand flags touched.

### A. Unlinked (verified wrong asset)
| viol id | drug (claimed) | NCT | ct.gov actual intervention(s) | action |
|---|---|---|---|---|
| 147 | spy230 | NCT07012395 | SPY001 / SPY002 / SPY003 (Spyre UC) | deleted trial_facts 499193da + trial_registries b9167c56 |
| 104 | abs-101 | NCT06730126 | Soquelitinib (ITK inh.) | deleted catalyst 2168 |
| 111 | ep006 | NCT06212999 | Povorcitinib / INCB054707 | deleted catalyst 2184 |
| 121 | kt501 | NCT06630806 | SAR446523 | deleted catalyst 2453 |
| 123 | mepolizumab | NCT06748053 | GSK5784283 (anti-TSLP) / SHR-1905 | deleted catalyst 2165 |
| 126 | mg-k10 | NCT06906081 | Finerenone (Kerendia) | deleted catalyst 2967 |
| 130 | mt-251 | NCT07219368 | MT-201 (sibling) | deleted catalyst 2598 |
| 131 | nemolizumab | NCT04350359 | transcutaneous tibial nerve stim. (device) | deleted catalyst 2133 |
| 133 | omalizumab | NCT06162728 | Briquilimab (JSP191) | deleted catalyst 3010 |
| 135 | ravulizumab | NCT05744921 | Pozelimab / Cemdisiran | deleted catalyst 3023 |
| 141 | rituximab | NCT06646497 | allogeneic HSCT | deleted catalyst 3042 |
| 143 | ruxolitinib-topical | NCT07606703 | Madecassoside Tablets | deleted catalyst 3053 |
| 191 | kyv-101 | NCT05361551 | liver ablation (procedure) | deleted catalyst 1779 |
| 192 | kyv-101 | NCT05765071 | Botulinum toxin A | deleted catalyst 1728 |

### B. False-positive (link correct — flag cleared, nothing unlinked)
| viol id | drug | NCT | ct.gov interventions | note |
|---|---|---|---|---|
| 138 | risankizumab-lutikizumab-or-trosunilimab | NCT06548542 | Risankizumab + Lutikizumab + Trosunilimab + ABBV-8736 | combo record matches trial; (whether the combo-id record should exist = separate identity question) |
| 144 | semaglutide | NCT07309094 | GLP-1RA study incl. **semaglutide** | drug present |
| 154 | verekitug--upb-101 | NCT06981078 | **Verekitug (UPB-101)** | molecule matches; detector tripped on compound code form |
| 152 | upadacitinib | NCT01965132 | Korean Rheum. Biologics/Targeted Registry incl. **upadacitinib** | registry legitimately tracks the drug |

### C. Stale — already corrected (no live link found; flag closed)
17 rows, ids: 102 (ab001→MPCs), 105 (apg279→APG777), 106 (apg333→regorafenib CRC), 110
(deucravacitinib→SKINERGY biomarker), 112 (filgotinib→GLPG0634 renal-impairment PK — actually
filgotinib's own code but link absent), 117 (guselkumab-golimumab→chlorhexidine spine SSI), 124
(metis-mrna-cd19bcmacd3→MTS109), 125 (mg-k10→eltrombopag), 132 (ocrelizumab→ofatumumab), 134
(ravulizumab→Crovalimab), 136 (risankizumab→drug-eluting balloon venoplasty), 139
(risankizumab-vs-vedolizumab→ozanimod ext.), 142 (ruxolitinib-topical→carbidopa), 146
(spx306→SPX-303), 149 (tocilizumab→hyperimmune plasma COVID), 151 (tulisokibart→COVID booster
vaccine), 156 (win027→WIN378). Each verified to have **no** surviving link in trial_facts /
trial_registries / catalysts for that drug+NCT — wrong link was removed in a prior harvest/cleanup.

### D. Skipped / ambiguous — LEFT UNRESOLVED (human review)
Drug is plausibly in scope (registry / observational / background-therapy / generic ct.gov
intervention), so unlinking would not be provably correct:
| viol id | drug | NCT | why skipped |
|---|---|---|---|
| 107 | bimekizumab | NCT07149792 | psoriasis precision-medicine RCT; "biologics treatment" generic, bimekizumab is a psoriasis biologic |
| 113 | filgotinib | NCT02714634 | "MTX/leflunomide + targeted therapy" arm unspecified; filgotinib could be the targeted therapy |
| 114 | guselkumab | NCT07198113 | COMPARE pediatric IBD comparison; interventions empty |
| 115 | guselkumab | NCT07545317 | real-world IL-23-inhibitor Crohn's study; guselkumab IS an IL-23 inhibitor |
| 116 | guselkumab-golimumab | NCT01848028 | PsoBest registry; combo-record artifact (review separately) |
| 118 | guselkumab-golimumab | NCT06089590 | I-CARE 2 IBD registry; non-interventional |
| 119 | guselkumab-golimumab | NCT07177209 | UC treatment-pattern registry; interventions list incl. guselkumab + golimumab |
| 120 | inebilizumab | NCT06885957 | AQP4+ NMOSD "Mab Therapy" (generic); inebilizumab/Uplizna is approved for AQP4 NMOSD |
| 127 | mirikizumab | NCT07198113 | COMPARE pediatric IBD comparison; interventions empty |
| 137 | risankizumab | NCT06399432 | Mediterranean-diet study in *risankizumab-treated* psoriasis patients (drug = enrolled population) |
| 140 | rituximab | NCT06242327 | membranous nephropathy outcome analysis (observational); rituximab is SoC |
| 150 | tralokinumab | NCT03549416 | BioDay registry of new systemic AD treatments; tralokinumab is an AD systemic |
| 153 | upadacitinib | NCT06136767 | systemic-eczema treatment registry; upadacitinib (Rinvoq) approved for AD |

### Counts after this pass
- trial_misattributed resolved this pass: **35** (14 unlinked + 4 FP + 17 stale).
- trial_misattributed still unresolved (all ambiguous, above): **13**.
- **Total `governance_violations WHERE resolved=false`: 39** (was 86 at start of the 2026-06-15 triage; the 12 inferred-target FPs + this 35 = 47 resolved).

---

## Approved fixes executed (2026-06-15)

Owner-approved Stage 1 data fixes. Deletes were owner-approved "if validation is
accurate" — every NCT was **re-verified live against ClinicalTrials.gov API v2**
before deleting. Governance respected: trial_registries deletes done directly
(non-core table); the one `drugs` write went through `DrugWriter`, never an ad-hoc
PATCH. No drug/company entity deleted/merged; no `approved`/brand flags touched.

### TASK A — spurious trial links deleted (5)

Re-verified each NCT's interventions via CT.gov v2; all confirmed to be a
**different molecule/study** than the linked drug. Deleted the offending
`trial_registries` row (the lone `registry_name='ClinicalTrials.gov'`,
`search_status='found'` prefix-match row). No `trial_facts` rows existed for any
of these drugs (links lived only in trial_registries).

| drug | deleted trial_registries id | NCT | CT.gov v2 interventions (re-verified) | verdict |
|---|---|---|---|---|
| es302  | bf0ba632-d971-4ada-b36a-43865d6f4313 | NCT04841538 | DRUG **ES101** ("ES101 (PD-L1x4-1BB Bispecific) in advanced thoracic tumors") | spurious — different asset (Elpiscience oncology) |
| lq080  | bde5a7ed-4283-4f0d-bd5b-c693269cdc96 | NCT04993443 | DRUG **LQ036** + Matching Placebo (FIH LQ036 study) | spurious — LQ036, not lq080 |
| lq082  | eaf7d536-1f38-49cb-aab3-d36b6ada7b3c | NCT04993443 | DRUG **LQ036** + Matching Placebo | spurious — LQ036, not lq082 |
| spx306 | af3d70d3-bcb8-4a76-8ed8-2dc4265f44f4 | NCT05702086 | OTHER **"SPARX"** (youth-depression e-intervention, "Making SPARX Fly in Nunavut", York U) | spurious — psychology study, not spx306 |
| yb-101 | 5dbc5069-2e1c-4436-bd91-2d1af7b11778 | NCT06330688 | PROCEDURE **percutaneous cholecystostomy** (Attikon) | spurious — surgical study, not yb-101 |

All 5 DELETE returned HTTP 204; post-delete fetch returned empty. None skipped —
all five re-verified as spurious.

**Validation rows updated (notes, status kept):** the 5 `stage_trial_match`
`drug_validation_results` rows (es302/lq080/lq082/spx306/yb-101) had their `notes`
rewritten to record the delete + the CT.gov v2 interventions
(`verified_by=triage_2026-06-15_stage1_fixes`). **Status left as `warning`** — not
flipped to `pass` — because the *data bug* (bad link) is fixed but the underlying
`stage_trial_match` gap (CT.gov+ANZCTR true-negative 2026-06-14, no real registered
trial) genuinely persists, consistent with VALIDATION_TRIAGE's documented position
(these are confirmed gaps, not false positives). They clear when CDE/EUCTR search
is added.

**Governance violations:** no standalone `trial_misattributed_<NCT>` rows existed
for these 5 drugs (the spurious links were caught by the validation layer in
trial_registries, not by the catalyst/trial_facts mis-attribution detector), so no
trial-link governance row needed resolving here.

### TASK B — cendakimab modality fixed (via DrugWriter)

- **Before:** `modality='Antibody'` but `modality_class='Small molecule'` (internal
  contradiction). Cendakimab is a real anti-IL-13 monoclonal antibody (ChEMBL
  CHEMBL4297864).
- **Action:** `DrugWriter().update_fields("cendakimab", {"modality_class":
  "Monoclonal antibody"})` — ran in-sandbox (env `SUPABASE_SERVICE_KEY` from
  `.supabase_service_key`; `src/database/client.py` reads that var). Returned
  `errors: []`. Chose `'Monoclonal antibody'` because that is the canonical
  `modality_class` value already used for mAbs in `drugs`.
- **After:** `modality='Antibody'`, `modality_class='Monoclonal antibody'` —
  consistent.
- **Validation:** cendakimab `modality_match` row was already `pass`; updated its
  `notes` to record the fix.

### TASK C — phase-inflation stage-confidence flags (sanctioned script)

Ran `scripts/phase_inflation_audit.py --write` (the sanctioned tool). It is
idempotent; the prior pass had already set `stage_confidence='low'` on 17 of 19
suspects and applied the one confirmed stage *value* correction (lbl053 Phase 3 ->
Preclinical, already in effect — no-op this run).

- **`stage_confidence='low'` newly set on 2 drugs:** `jnj-4804` (J&J combo
  guselkumab+golimumab, Phase 3, no own NCT) and `spy230` (Spyre co-formulation
  SPY002+SPY003, Phase 2, trial registered under the SPY00x/SKYLINE umbrella). Both
  are real combo/co-formulation assets whose footprint sits under the component or
  umbrella program — informational flag only, **stage value unchanged**.
- **2 new `governance_violations` (phase_inflation_audit) rows** auto-created for
  jnj-4804 (id 222) and spy230 (id 223) — legitimate review rows, left unresolved
  per the detector's design (human verification before relying on stage).
- The other 17 phase-inflation suspects already carried `stage_confidence='low'`
  and existing review rows — left as-is (genuine review items, not auto-resolved
  per GOVERNANCE_TRIAGE section C2).

**Stage VALUE changes deliberately NOT executed (left for Kyle):** the task
authorized a `drugs` stage write via DrugWriter *only where a source clearly
contradicts the stored stage*. Three assets have `stage_detail` text contradicting
the stored `stage` — but **none has a backing stage source row in `drug_sources`**
(checked; only a generic UC-prevalence publication exists for each). Per the
"every fact needs a source row" hard rule + the constitution's "stage flips need
Kyle's approval," I set `stage_confidence='low'` (done) and leave the value change
to Kyle. Exact DrugWriter commands (run from a clean clone with
`SUPABASE_SERVICE_KEY` set), to apply **only after attaching a real source URL**:

    # es302: stage_detail says "Preclinical — ... no IND filed; no CT.gov/CDE reg."
    DrugWriter().update_fields("es302", {"stage": "Preclinical"})   # add source row first

    # generate-uc: stage_detail says "Phase 1 per IPO S-1 (Feb 2026)"
    DrugWriter().update_fields("generate-uc", {"stage": "Phase 1"}) # cite the S-1 in drug_sources first

    # lq082: stage_detail says "Lead optimization (preclinical)"
    DrugWriter().update_fields("lq082", {"stage": "Preclinical"})   # add source row first

`hlx36` / `jnj-4804` / `spy230` are ambiguous (unverified, not contradicted) —
keep stage_confidence='low' only, no value change.

### Net DB deltas this pass
- `trial_registries`: -5 spurious rows (es302, lq080, lq082, spx306, yb-101).
- `drugs`: 1 write via DrugWriter (cendakimab `modality_class`). No stage/brand/approved changes.
- `drug_validation_results`: 6 `notes` updates (5 trial-link warnings + cendakimab modality_match). No status flips.
- `governance_violations` unresolved: **39 -> 41** (+2 new phase_inflation review rows: jnj-4804 id 222, spy230 id 223).
- Validation: warnings **34** (unchanged), needs_review **1** (unchanged — epi-001, left for review).
