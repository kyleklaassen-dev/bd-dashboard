# Drug Validation Triage — 2026-06-15

Triage of all non-pass rows in `drug_validation_results`. Conservative pass:
no stage flips, no brand/approved changes, no core-entity deletes. Resolved only
provably-benign test bugs and stale assumptions; flagged real data bugs and
genuinely open items for human review.

## Result summary

| Status | Before | After | Δ |
|---|---|---|---|
| pass | 960 | 968 | +8 |
| fail | 0 | 0 | 0 |
| warning | 38 | 34 | −4 |
| needs_review | 5 | 1 | −4 |

**8 rows resolved** (4 needs_review + 4 warning). **35 remain** (34 warning + 1 needs_review).

## Method note — why the registry "found" rows could NOT be trusted

Several flagged drugs have a `trial_registries` row marked `search_status='found'`
under `registry_name='ClinicalTrials.gov'` (written by older syncs:
`meridian_integrations.py` / `phase1-ctgov`). I spot-checked the linked NCTs
against CT.gov directly and **5 of 5 with verifiable study/search URLs were
spurious codename-prefix matches**:

- es302 → NCT04841538 = **ES101** (PD-L1×4-1BB oncology, Elpiscience) — not es302
- lq080 / lq082 → NCT04993443 = **LQ036** — different asset
- spx306 → NCT05702086 = **"SPARX"** psychology e-intervention (York U) — junk match
- yb-101 → NCT06330688 = **cholecystostomy** study (Attikon) — junk match

Conclusion: the older `ClinicalTrials.gov` registry links are unreliable. The
`validation_research.py` warnings (name-hard-gated CT.gov + ANZCTR search, run
2026-06-14) are the **trustworthy** signal — so most stage_trial_match warnings
are *correct confirmed gaps*, not false positives, and must NOT be auto-passed.
(CT.gov was unreachable from the sandbox for the `?intr=`-search-URL links
spy001/spy003/spy120/spy130/sm-101; those are left as warnings — see below.)

---

## Classification of all 43 rows (taxonomy: 1 data bug / 2 test bug / 3 stale / 4 source gap / 5 true-unresolved)

### needs_review (5)

| drug | check | type | disposition |
|---|---|---|---|
| lbp-ec01 | identity | (3) stale | **RESOLVED → pass.** Codename collision investigated; target corrected to AIEC; bad links removed. |
| ab001 | identity | (2/3) test/stale | **RESOLVED → pass.** External AB001=oncology small mol was a collision; bad links removed; our target IL-23p19 correct. |
| ab001 | modality_match | (2) test bug | **RESOLVED → pass.** ChEMBL CHEMBL5095207 (small molecule) is the *colliding* AB001; our record does not adopt it (modality null). Benign external mismatch. |
| cendakimab | modality_match | (3) stale | **RESOLVED → pass.** Record modality now 'Antibody' and AGREES with ChEMBL (cendakimab is a real anti-IL-13 mAb). Flagged a residual data bug — see below. |
| epi-001 | identity | (5) true unresolved | **LEFT for review.** Our anti-TL1A EPI-001 (episcience) is unverified; designation collides with EPI-001 AR-NTD inhibitor (prostate). Asset existence not confirmed. |

### modality_match warnings — handled above (cendakimab, ab001).

### stage_trial_match (38)

**Resolved (4) — test bug, preclinical:** stage_trial_match should not fire on a
Preclinical / IND-enabling asset (no registered trial expected yet). 0 trials on
2026-06-14 is consistent with stage. → pass, re-flag if it advances to clinic.

- sab06 (Preclinical), sim0709 (Preclinical), lbl053 (Preclinical), xmab412 (Preclinical)

**Remaining 34 = genuine gaps (mostly type 4 source gap / 5 true-unresolved):**
Phase 1+ assets (largely China / early-stage) where CT.gov + ANZCTR confirm no
registered trial. These are *working as intended* — confirmed gaps, not false
positives. Likely registered in Chinese CDE / EUCTR (not yet searched) or
not-yet-registered. Leave as warning until CDE/EUCTR search is added.

Remaining warning drugs: qx030n, spy001, shr0817, xb3217, eta1001, hlx36, spy003,
dam-51, ionis-tslp-25rx, spy130, lq082, es302, sm-101, ky1044, yb-101, lq080,
ati-052, cldr-001, generate-uc, hr7044, cld-423, nvx-360, win027, abs-101, bel512,
calt-100, spx306, qx031n, gb1275, ear-2001, spy120, srf-231, rgx-181, spy230.

---

## Remaining items needing attention

### A. Data bugs to fix (flagged on the validation rows; need a writer/human action)

| # | item | recommended fix | approval? |
|---|---|---|---|
| A1 | **cendakimab** `drugs.modality_class='Small molecule'` while `modality='Antibody'` | Correct `modality_class` → 'Monoclonal antibody'/'Biologic'. Internal contradiction. | No — clearly wrong, but route through drug Writer. |
| A2 | **es302** spurious trial link NCT04841538 (=ES101 oncology) in trial_registries | Delete the bad `trial_registries` row. | Delete → **Kyle approval** per governance. |
| A3 | **lq080 / lq082** spurious link NCT04993443 (=LQ036) | Delete the bad trial_registries rows. | Delete → **Kyle approval**. |
| A4 | **spx306** spurious link NCT05702086 (=SPARX psychology) | Delete bad trial_registries row. | Delete → **Kyle approval**. |
| A5 | **yb-101** spurious link NCT06330688 (=cholecystostomy) | Delete bad trial_registries row. | Delete → **Kyle approval**. |
| A6 | **Systemic:** older `ClinicalTrials.gov`-named registry links (prefix-matched, unreliable) | Audit all `registry_name='ClinicalTrials.gov'` rows for prefix-only matches; supersede with name-gated `ct_gov` results. | Bulk delete → **Kyle approval**. |

### B. Possible stage overstatements (do NOT auto-fix — flagged only)

Per the hard rule (no stage flips without approval), these are flagged for review:

| drug | stage field | conflicting evidence | recommendation |
|---|---|---|---|
| **generate-uc** | Phase 3 | stage_detail: "Phase 1 per IPO S-1"; 0 trials found | Verify true stage; likely overstated. **Kyle review.** |
| **lq082** | Phase 2 | stage_detail: "Lead optimization"; trispecific; 0 trials | Likely preclinical. **Kyle review.** |
| **es302** | Phase 2 | stage_detail: "Preclinical — symmetric…"; 0 trials | Likely preclinical. **Kyle review.** |
| **hlx36** | Phase 3 | 0 trials on CT.gov/ANZCTR (IL-4Rα) | Verify — Phase 3 with no registered trial is unusual; may be China-only (CDE). |
| **cld-423** | (null) | stage=None yet flagged stage_trial_match | Check why the check fired with no stage; likely a stale check row. |

### C. Test-improvement recommendations (for `validation_research.py`)

1. **Skip stage_trial_match for Preclinical / IND-enabling stages** — prevents the 4 false-fires resolved here (and future ones).
2. **Add Chinese CDE + EUCTR search** — `trial_registries` already has `chinese_cde`/`euctr` rows in `not_searched`; most remaining gaps are China assets. This would convert many warnings to pass.
3. **Normalize `registry_name` casing** (`ct_gov` vs `ClinicalTrials.gov`) and reconcile the two CT.gov sync paths so a confirmed trial in one path clears the warning in the other.
4. **Tighten prefix matching** — require ≥6-char token match AND an intervention-name (not title-only) hit to avoid SPARX/cholecystostomy-type junk.

---

## What was changed in the DB (all reversible; notes-only + status flips)

- 8 `drug_validation_results.check_status` flipped to `pass` with explanatory
  `notes`, `verified_by='triage_2026-06-15'` (4 needs_review, 4 preclinical warnings).
- 5 stage_trial_match `notes` appended with data-bug detail (es302, lq080, lq082,
  spx306, yb-101) — **status left as warning**.
- No `drugs` rows modified. No stage/brand/approved changes. No deletes.
