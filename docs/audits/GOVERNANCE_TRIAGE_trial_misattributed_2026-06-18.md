# Governance triage — `trial_misattributed_*` (38 unresolved) — 2026-06-18

Read-only investigation of the 38 open `governance_violations` surfaced by the new intelligence-quality
scoreboard. Producer: CT.gov identity checks (a trial/source's CT.gov title doesn't mention the linked drug).
**Finding: NOT all stale — 15 are stale (link already gone), 23 are LIVE (mislink still stored).**
Auto-resolving all would hide 23 real defects; auto-deleting all would wrongly remove false positives
(e.g. `verekitug--upb-101` ← NCT06981078 *is* a real Verekitug COPD study). So: triage, then approval-gated fix.

## Dispositions
- **STALE (15)** — link absent from trials/efficacy/drug_sources → safe to mark `resolved=true` (log hygiene).
- **LIVE-WRONG** — link stored but CT.gov title is a different asset/registry → remove the trials/drug_sources link **(delete → Kyle's approval)**.
- **LIVE-FALSE-POSITIVE** — title actually matches the drug; validator slug-match missed it → mark `resolved=true`, keep link.

| drug_id | NCT | stored in | actual CT.gov study title | suggested |
|---|---|---|---|---|
| ab001 | NCT00555828 | STALE(none) | Safety Study of Allogeneic Mesenchymal Precursor Cells (MPCs) in | STALE → resolve |
| apg279 | NCT06395948 | trials+drug_sources | A Study Evaluating APG777 in Atopic Dermatitis | WRONG → remove [approval] |
| apg333 | NCT06137170 | trials+drug_sources | A Real-World Study to Learn More About the Order of Different Tr | WRONG → remove [approval] |
| bimekizumab | NCT07149792 | drug_sources | A Multi-center RCT Clinical Trial on Personalized Precision Medi | WRONG → remove [approval] |
| deucravacitinib | NCT07021495 | STALE(none) | SKIN Disease Profiling by an Exploratory, pRospective, Biomarker | STALE → resolve |
| filgotinib | NCT02714634 | drug_sources | Clinical Trial Evaluating Methotrexate or Leflunomide + Targeted | WRONG → remove [approval] |
| filgotinib | NCT02084199 | STALE(none) | Study to Evaluate GLPG0634 in Subjects With Renal Impairment Com | STALE → resolve |
| guselkumab | NCT07198113 | drug_sources | COMPARE - Pediatric Inflammatory Bowel Disease (PIBD) | WRONG → remove [approval] |
| guselkumab | NCT07545317 | STALE(none) | Real-World Study of IL-23 Inhibitors in Active Crohn | STALE → resolve |
| guselkumab-golimumab | NCT07177209 | drug_sources | Describing Treatment Patterns and Creating an Updated Treatment  | WRONG → remove [approval] |
| guselkumab-golimumab | NCT02490631 | STALE(none) | 2% Chlorhexidine Gluconate Skin Cloths to Prevent SSI in Spine S | STALE → resolve |
| guselkumab-golimumab | NCT01848028 | drug_sources | PsoBest - The German Psoriasis Registry | WRONG (registry) → remove [approval] |
| guselkumab-golimumab | NCT06089590 | drug_sources | Ibd CAncer and seRious Infections in France (I-CARE 2) | WRONG → remove [approval] |
| inebilizumab | NCT06885957 | drug_sources | Monoclonal Antibody-Based Therapies for AQP4-Positive NMOSD | WRONG → remove [approval] |
| kt501 | NCT06630806 | trials | A Study to Investigate the Safety and Efficacy of SAR446523 Inje | WRONG → remove [approval] |
| mepolizumab | NCT06748053 | trials | A Dose Finding Study With an Anti-TSLP Antibody (GSK5784283) in  | WRONG → remove [approval] |
| metis-mrna-cd19bcmacd3 | NCT07526350 | STALE(none) | MTS109 in Patients With Refractory Autoimmune Diseases | STALE → resolve |
| mg-k10 | NCT01762761 | STALE(none) | Eltrombopag Phase III Study In Chinese Chronic ITP Patients | STALE → resolve |
| mirikizumab | NCT07198113 | drug_sources | COMPARE - Pediatric Inflammatory Bowel Disease (PIBD) | WRONG → remove [approval] |
| mt-251 | NCT07219368 | trials+drug_sources | A First-in-Human Single and Multiple Ascending Dose Study of MT- | WRONG → remove [approval] |
| ocrelizumab | NCT04486716 | STALE(none) | A Single Arm Study Evaluating the Efficacy, Safety and Tolerabil | STALE → resolve |
| ravulizumab | NCT04861259 | STALE(none) | A Study Evaluating the Efficacy, Safety, Pharmacokinetics and Ph | STALE → resolve |
| risankizumab | NCT06399432 | drug_sources | Mediterranean Diet vs no Dietary Intervention for Improving Sign | WRONG → remove [approval] |
| risankizumab | NCT02902094 | STALE(none) | Drug Eluting Balloon Venoplasty in AV Fistula Stenosis | STALE → resolve |
| risankizumab-lutikizumab-or-trosunilimab | NCT06548542 | drug_sources | Study of Targeted Therapies for the Treatment of Adult Participa | WRONG → remove [approval] |
| risankizumab-vs-vedolizumab | NCT03467958 | STALE(none) | An Extension Study of Oral Ozanimod for Moderately to Severely A | STALE → resolve |
| rituximab | NCT06242327 | drug_sources | An Outcome Analysis of Primary Membranous Nephropathy | WRONG → remove [approval] |
| ruxolitinib-topical | NCT02553265 | STALE(none) | Carbidopa for the Treatment of Excessive Blood Pressure Variabil | STALE → resolve |
| semaglutide | NCT07309094 | drug_sources | Clinical, Morphometric and Biochemical Effects on Adiposopathy A | WRONG → remove [approval] |
| spx306 | NCT06259552 | drug_sources | A Study of SPX-303, a Bispecific Antibody Targeting LILRB2 and P | WRONG → remove [approval] |
| spy230 | NCT07012395 | drug_sources | A Study of Long-acting Antibodies Alone and in Combinations for  | WRONG → remove [approval] |
| tocilizumab | NCT04366245 | STALE(none) | Clinical Trial to Evaluate the Efficacy of Treatment With Hyperi | STALE → resolve |
| tralokinumab | NCT03549416 | drug_sources | BioDay Registry: Data Collection Regarding the Use of New System | WRONG (registry) → remove [approval] |
| tulisokibart | NCT05104333 | STALE(none) | Evaluation of Immunogenicity, Safety and Antibody Persistence of | STALE → resolve |
| upadacitinib | NCT01965132 | STALE(none) | Korean College of Rheumatology Biologics and Targeted Therapy Re | STALE → resolve |
| upadacitinib | NCT06136767 | trials | Registry for Systemic Eczema Treatments | WRONG (registry) → remove [approval] |
| verekitug--upb-101 | NCT06981078 | trials+drug_sources | A Study to Assess the Efficacy and Safety of Verekitug in Partic | FP? verify → resolve (title matches) |
| win027 | NCT07120503 | drug_sources | Study to Evaluate the Safety, Pharmacology and Efficacy of WIN37 | WRONG → remove [approval] |
