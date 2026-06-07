# Wrong-Area Audit — drug_area_scores vs drug_areas
**Date:** 2026-05-23  
**Scope:** All 76 orphaned `drug_area_scores` rows (rows with no matching `drug_areas` counterpart)  
**Query:** `drug_area_scores` LEFT JOIN `drug_areas` ON (drug_id, area_id) WHERE drug_areas.drug_id IS NULL

---

## Summary

| Outcome | Count |
|---------|-------|
| DELETE (clearly wrong area — stale enrichment artifact) | 56 |
| UNCERTAIN — review before acting | 20 |
| **Total orphaned rows** | **76** |

No rows are classified as KEEP (all orphans are either wrong or require review — correct rows should exist in `drug_areas`).

**Root cause:** Past enrichment runs used company-level context to classify drugs. When a company has both IBD and oncology drugs (e.g., Roche, Merck, JNJ, AbbVie), the enrichment prompt sometimes assigned Watch scores to oncology drugs in IBD/atopy areas, or assigned IBD drug scores to atopy/fcrn areas. These rows were never added to `drug_areas` (the canonical membership table), making them orphans.

---

## Direct/Adjacent Orphans (5 rows — highest priority)

These are the most serious: Direct or Adjacent overlap scores with no `drug_areas` counterpart.

| drug_id | area_id | overlap | target | verdict | rationale |
|---------|---------|---------|--------|---------|-----------|
| `abbv-382` | atopy | Adjacent | α4β7 | **DELETE** | α4β7 integrin inhibitor — IBD and TL1A area drug. No atopy program. Correct areas (ibd, tl1a) already exist in drug_areas. |
| `generate-uc` | tslp | Direct | TL1A×IL-23p19 | **DELETE** | TL1A×IL-23 bispecific — tl1a/ibd area, not tslp. Enrichment confused company name (Generate Biomedicines) with tslp area. Correct drug_areas entries are ibd and tl1a. |
| `qx030n` | respiratory | Direct | TL1A×IL-23p19 | **DELETE** | TL1A×IL-23 bispecific — tl1a/ibd area, not respiratory. No respiratory program. Correct drug_areas entries are ibd and tl1a. |
| `sim0500` | ibd | Direct | TL1A | **ADD TO drug_areas** | TL1A inhibitor (Simcere, Phase 1). IBD IS the correct area. Score is valid — `drug_areas` is missing the sim0500/ibd row. |
| `cld-423` | tl1a | Direct | TL1A×IL-23 | **UNCERTAIN** | TL1A×IL-23 bispecific — tl1a IS correct area; has a valid source_url. But cld-423 may be a duplicate of cldr-001 (unresolved). Do not delete. Resolve cldr-001/cld-423 identity first, then add missing drug_areas row. |

---

## Watch Orphans by Area

### atopy (22 rows)

| drug_id | target | company | verdict | reason |
|---------|--------|---------|---------|--------|
| `abbv-668` | RIPK1 | abbvie | **DELETE** | RIPK1 IBD drug; no atopy program |
| `adalimumab` | TNFα | abbvie | **DELETE** | TNF inhibitor; IBD/RA indication. Not atopy |
| `bemarituzumab` | FGFR2b | amgen | **DELETE** | Anti-FGFR2b; gastric/gastroesophageal cancer. No atopy connection |
| `blinatumomab` | CD19×CD3 | amgen | **DELETE** | BiTE for B-cell ALL. Hematologic oncology, not atopy |
| `ciltacabtagene-autoleucel` | BCMA | jnj | **DELETE** | CAR-T for multiple myeloma. No atopy connection |
| `guselkumab-golimumab` | IL-23p19+TNFα | jnj | **DELETE** | IBD confirmatory combo trial. Not atopy |
| `daratumumab` | CD38 | jnj | **DELETE** | Anti-CD38 for multiple myeloma. No atopy connection |
| `golimumab` | TNFα | jnj | **DELETE** | TNF inhibitor; UC/RA. Not atopy |
| `guselkumab` | IL-23p19 | jnj | **DELETE** | IL-23 inhibitor; IBD/PsA. Not atopy |
| `inebilizumab` | CD19 | amgen | **DELETE** | Anti-CD19 for NMOSD. Neurology, not atopy |
| `infliximab` | TNFα | jnj | **DELETE** | TNF inhibitor; IBD/RA. Not atopy |
| `lutikizumab` | IL-1α/β | abbvie | **DELETE** | IL-1 dual inhibitor; IBD combo context. Not atopy |
| `m701` | FcRn¹ | amgen | **DELETE** | Rationale confirms oncology (EpCAM×CD3) — no atopy connection regardless of target field |
| `nipocalimab` | FcRn | jnj | **DELETE** | FcRn mAb; IgG catabolism. No atopy mechanism. Belongs in fcrn area |
| `risankizumab` | IL-23p19 | abbvie | **DELETE** | IL-23 inhibitor; IBD/PsA. Not atopy |
| `risankizumab-lutikizumab-or-trosunilimab` | IL-23p19+combo | abbvie | **DELETE** | IBD combination trial. Not atopy |
| `risankizumab-vs-vedolizumab` | IL-23p19 vs α4β7 | abbvie | **DELETE** | IBD head-to-head trial. Not atopy |
| `teclistamab` | BCMA×CD3 | jnj | **DELETE** | BiTE for multiple myeloma. No atopy connection |
| `teprotumumab` | IGF-1R | amgen | **DELETE** | Anti-IGF-1R for thyroid eye disease. No atopy connection |
| `tezepelumab` | TSLP | amgen | **DELETE** | TSLP mAb; approved for asthma. Belongs in tslp area, not atopy. Duplicate coverage |
| `ustekinumab` | IL-12/23p40 | jnj | **DELETE** | IL-12/23 inhibitor; IBD drug (Stelara). Not atopy |
| `upadacitinib` | JAK1 | abbvie | **UNCERTAIN** | JAK1 inhibitor approved for atopic dermatitis (Rinvoq). Legitimate atopy Watch. drug_areas may be missing this row rather than score being wrong. |

¹ m701 target field appears to be mislabeled in DB; rationale confirms oncology (EpCAM×CD3)

---

### autoimmune (6 rows)

All 6 are Novartis drugs. Enrichment ran with company-level autoimmune context and created Watch scores, but `drug_areas` was never updated. These drugs have partial autoimmune relevance but are peripherally connected to the platform's BD focus.

| drug_id | target | verdict | reason |
|---------|--------|---------|--------|
| `omalizumab` | IgE | **UNCERTAIN** | Anti-IgE; chronic urticaria has autoimmune etiology. Marginal |
| `ianalumab` | BAFF-R | **UNCERTAIN** | Anti-BAFF-R; Sjögren's, SLE. Legitimate B-cell autoimmune drug |
| `iscalimab` | CD40 | **UNCERTAIN** | CD40 blocker; Sjögren's. Legitimate autoimmune mechanism |
| `ofatumumab` | CD20 | **UNCERTAIN** | Anti-CD20; multiple sclerosis (Kesimpta). Autoimmune relevant |
| `secukinumab` | IL-17A | **UNCERTAIN** | IL-17A inhibitor; PsA/AS/psoriasis. Autoimmune adjacent |
| `tisagenlecleucel` | CD19 | **UNCERTAIN** | CD19 CAR-T; experimental use in refractory SLE/autoimmune. Investigational only |

**Recommendation:** Review whether the `autoimmune` area in `drug_areas` is intended to capture this company-level breadth. If yes, add the relevant rows to `drug_areas` and keep scores. If no, delete all 6.

---

### fcrn (4 rows)

| drug_id | target | verdict | reason |
|---------|--------|---------|--------|
| `argx-117` | "FcRn×CD131"¹ | **DELETE** | argx-117 is actually an anti-C2 complement mAb, not an FcRn drug. Target field is mislabeled. Wrong area. |
| `bimekizumab` | IL-17A/F | **DELETE** | Dual IL-17A/F inhibitor; PsO/PsA. No FcRn connection whatsoever |
| `batoclimab` | FcRn | **UNCERTAIN** | Legitimate anti-FcRn mAb (Immunovant, discontinued). FcRn IS correct area. drug_areas likely missing this row |
| `imvt-1402` | FcRn | **UNCERTAIN** | Next-gen albumin-sparing anti-FcRn mAb (Immunovant, Phase 3). FcRn IS correct area. drug_areas likely missing this row |

¹ argx-117 target column is erroneous; should be investigated and corrected separately.

---

### ibd (28 rows)

| drug_id | target | company | verdict | reason |
|---------|--------|---------|---------|--------|
| `sim0500` | TL1A | simcere | **ADD TO drug_areas** | TL1A Phase 1 IBD drug. Score is correct; drug_areas missing this entry |
| `abs-101` | TL1A | absci | **UNCERTAIN** | TL1A inhibitor, Phase 1. IBD is the correct area. drug_areas likely missing this row |
| `cld-423` | TL1A×IL-23 | caldera | **UNCERTAIN** | TL1A×IL-23 → IBD is correct. But cld-423 may be a duplicate of cldr-001. Resolve identity first |
| `hxn-1003` | TL1A×IL-23 | earendil | **DELETE** | hxn-1003 was merged into erd-1 in Session 5 (commit 14df877). This is a stale row for a deleted drug |
| `mt-251` | TL1A×IL-23p19 | mirador | **UNCERTAIN** | TL1A×IL-23 → IBD is correct. drug_areas likely missing this row |
| `abrocitinib` | JAK1 | pfizer | **DELETE** | JAK1 inhibitor; approved in atopic dermatitis (Cibinqo), not IBD |
| `amlitelimab` | OX40L | sanofi | **DELETE** | Anti-OX40L; atopy/AD. Rationale confirms no IBD program |
| `astegolimab` | IL-33 | roche | **DELETE** | Anti-IL-33; COPD. Rationale explicitly excludes IBD |
| `atezolizumab` | PD-L1 | roche | **DELETE** | Anti-PD-L1; cancer immunotherapy. No IBD indication |
| `belzutifan` | HIF-2α | merck | **DELETE** | HIF-2α inhibitor; VHL/ccRCC cancer. No IBD connection |
| `bevacizumab` | VEGF-A | roche | **DELETE** | Anti-VEGF; cancer. No IBD indication |
| `dupilumab` | IL-4Rα | sanofi | **DELETE** | IL-4Rα mAb; atopy (AD, asthma). No approved IBD indication per rationale |
| `glofitamab` | CD20×CD3 | roche | **DELETE** | CD20×CD3 bispecific; B-cell lymphoma. No IBD connection |
| `ibi333` | IL-4Rα×TSLP | sanofi | **DELETE** | IL-4Rα×TSLP bispecific; atopy/asthma. No IBD program |
| `ixekizumab` | IL-17A | lilly | **DELETE** | IL-17A inhibitor; IL-17 pathway actually worsens IBD. No IBD indication |
| `lebrikizumab` | IL-13 | lilly | **DELETE** | IL-13 inhibitor; atopic dermatitis. Rationale confirms no IBD/TL1A connection |
| `lenvatinib` | VEGFR/FGFR/multi | merck | **DELETE** | Multikinase TKI; cancer (HCC, thyroid). No IBD connection |
| `linsitinib` | IGF-1R | roche | **DELETE** | Oral IGF-1R inhibitor; oncology. No IBD connection |
| `mosunetuzumab` | CD20×CD3 | roche | **DELETE** | CD20×CD3 bispecific; B-cell lymphoma. No IBD connection |
| `obinutuzumab` | CD20 | roche | **DELETE** | Anti-CD20; CLL/lymphoma. No IBD indication |
| `ocrelizumab` | CD20 | roche | **DELETE** | Anti-CD20; multiple sclerosis. No IBD connection |
| `pembrolizumab` | PD-1 | merck | **DELETE** | Anti-PD-1; cancer immunotherapy. No IBD indication |
| `retatrutide` | GLP-1R+GIPR+GCGR | lilly | **DELETE** | Triple incretin agonist; metabolic/obesity. No direct IBD program (GLP-1 / IBD link is mechanistic only) |
| `riliprubart` | C1q complement | sanofi | **DELETE** | Anti-C1q; neurology/rare (CIDP). No IBD connection |
| `rituximab` | CD20 | roche | **DELETE** | Anti-CD20; RA/lymphoma. Not an IBD drug |
| `rocatinlimab` | OX40 | pfizer | **DELETE** | Anti-OX40; atopic dermatitis. Not IBD |
| `tirzepatide` | GLP-1R+GIPR | lilly | **DELETE** | Dual incretin agonist; T2D/obesity. No IBD program |
| `tocilizumab` | IL-6R | roche | **DELETE** | Anti-IL-6R; RA/COVID. IL-6R not an IBD mechanism of action |

---

### il4ra (4 rows)

| drug_id | target | company | verdict | reason |
|---------|--------|---------|---------|--------|
| `apg777` | IL-4Rα×OX40L | apogee | **UNCERTAIN** | IL-4Rα bispecific — il4ra IS the correct area. drug_areas likely missing this row |
| `itepekimab` | IL-33 | regeneron | **DELETE** | Anti-IL-33; IL-33 is upstream of IL-4/TSLP but does not target IL-4Rα. Belongs in tslp or atopy area, not il4ra |
| `linvoseltamab` | BCMA×CD3 | regeneron | **DELETE** | BCMA×CD3 BiTE; multiple myeloma. No il4ra connection |
| `zumilokibart` | IL-13 | apogee | **UNCERTAIN** | IL-13 inhibitor; IL-13 signals partly through IL-4Rα. Adjacent connection possible. Apogee is an il4ra-focused company |

---

### respiratory (3 rows)

| drug_id | target | company | verdict | reason |
|---------|--------|---------|---------|--------|
| `qx030n` | TL1A×IL-23p19 | qyuns | **DELETE** | (Direct — already in Direct/Adjacent section.) TL1A×IL-23 → tl1a/ibd, not respiratory |
| `belimumab` | BAFF | gsk | **DELETE** | Anti-BAFF; SLE. No respiratory program |
| `mepolizumab` | IL-5 | gsk | **UNCERTAIN** | Anti-IL-5; asthma (Nucala). Respiratory IS the correct area. drug_areas likely missing this row |

---

### tcell (2 rows)

| drug_id | target | company | verdict | reason |
|---------|--------|---------|---------|--------|
| `kyv-101` | CD19 (CAR-T) | kyverna | **UNCERTAIN** | CD19 CAR-T; Kyverna is focused on autoimmune (SLE, MS) using CAR-T. tcell area relevance depends on whether tcell captures this type of asset. Needs judgment call |
| `nipocalimab` | FcRn | jnj | **DELETE** | FcRn mAb; IgG catabolism. Not a T-cell mechanism. Belongs in fcrn area |

---

### tslp (5 rows)

| drug_id | target | company | verdict | reason |
|---------|--------|---------|---------|--------|
| `generate-uc` | TL1A×IL-23p19 | generate | **DELETE** | (Direct — already in Direct/Adjacent section.) TL1A×IL-23 → tl1a/ibd, not tslp |
| `anifrolumab` | IFNAR1 | astrazeneca | **DELETE** | Type I interferon receptor mAb; SLE. No TSLP connection |
| `benralizumab` | IL-5Rα | astrazeneca | **UNCERTAIN** | Anti-IL-5Rα; asthma. IL-5 is downstream of TSLP in the atopic/eosinophilic cascade. Loose Watch connection possible |
| `cendakimab` | IL-33¹ | astrazeneca | **DELETE** | IL-33/ST2 pathway; EoE. Not a TSLP mechanism. Incorrect company (cendakimab is not AZ). Data quality issue |
| `ravulizumab` | C5 complement | astrazeneca | **DELETE** | Anti-C5 complement; PNH/aHUS. No TSLP connection |

¹ cendakimab data appears mislabeled in the DB (wrong company, potentially wrong target). Investigate separately.

---

### tl1a (1 row)

| drug_id | target | company | verdict | reason |
|---------|--------|---------|---------|--------|
| `cld-423` | TL1A×IL-23 | caldera | **UNCERTAIN** | Has valid source_url (NCT05906563). tl1a IS the correct area. Orphaned because drug_areas has no cld-423/tl1a row. Resolve cld-423/cldr-001 identity first, then add missing drug_areas row |

---

## Action Plan

### Phase 1: Safe Deletes (56 rows)
Apply the SQL in `migrations/maintenance/wrong_area_cleanup.sql`. These are all clearly wrong-area enrichment artifacts with no BD relevance in the assigned area.

### Phase 2: Resolve Uncertainties (20 rows)

**Requires one-time judgment calls:**

1. **hxn-1003/ibd** — Merged into erd-1 in Session 5. If hxn-1003 drug record was deleted, this row is an orphan with no parent. **Recommend: DELETE** after confirming hxn-1003 no longer exists in `drugs`.

2. **cld-423 (both tl1a and ibd)** — Resolve cld-423/cldr-001 identity question first. If they are the same drug, delete all cld-423 scores and ensure cldr-001 has tl1a and ibd entries. If distinct, add drug_areas rows for cld-423/tl1a and cld-423/ibd.

3. **sim0500/ibd** — TL1A IBD drug with Direct score. **Recommend: ADD drug_areas row** (sim0500, ibd).

4. **abs-101/ibd, mt-251/ibd** — TL1A×IL-23 drugs. **Recommend: ADD drug_areas rows** after verifying drugs exist.

5. **batoclimab/fcrn, imvt-1402/fcrn** — Legitimate FcRn drugs. **Recommend: ADD drug_areas rows**.

6. **apg777/il4ra** — IL-4Rα bispecific. **Recommend: ADD drug_areas row**.

7. **autoimmune Novartis 6** — Decide scope of autoimmune area. If intended as a competitor-breadth area: **ADD drug_areas rows** for relevant ones. If not: **DELETE**.

8. **upadacitinib/atopy** — JAK1 in eczema. **Recommend: ADD drug_areas row** (upadacitinib clearly has atopy relevance).

9. **mepolizumab/respiratory** — IL-5 in asthma. **Recommend: ADD drug_areas row**.

10. **kyv-101/tcell** — Needs decision on tcell area scope.

11. **argx-117 target field** — Appears mislabeled in `drugs` table. Investigate and fix separately.

12. **cendakimab data** — Appears to have wrong company and possibly wrong target in `drugs` table. Investigate and fix separately.

---

## Missing Score Rows (84 rows)
These are `drug_areas` rows with no corresponding `drug_area_scores` entry. Not addressed in this audit — these need enrichment runs, not cleanup. Priority: run enrichment for missing TL1A/IBD/FcRn/IL-4Rα scores after the cleanup above is applied.

---

## Appendix: Delete Count by Area

| Area | Delete | Uncertain |
|------|--------|-----------|
| atopy | 21 | 1 |
| autoimmune | 0 | 6 |
| fcrn | 2 | 2 |
| ibd | 20 | 5 |
| il4ra | 2 | 2 |
| respiratory | 2 | 1 |
| tcell | 1 | 1 |
| tslp | 4 | 1 |
| tl1a | 0 | 1 |
| **Total** | **52** | **20** |

*Note: Direct/Adjacent orphans (abbv-382, generate-uc, qx030n = 3 DELETE; sim0500, cld-423/tl1a = 5 UNCERTAIN/ADD) are counted in their respective area rows above. Total DELETE = 52 (Watch) + 4 (Direct/Adjacent clear deletes) = 56.*
