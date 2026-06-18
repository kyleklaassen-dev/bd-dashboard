# Governance triage — `trial_misattributed_*` — 2026-06-18

Surfaced by `scripts/maintenance/intelligence_quality.py`. Producer: CT.gov identity checks.

## ✅ EXECUTED (15 STALE resolved 2026-06-18)
The misattributed NCT→drug link was verified **absent** from trials / drug_efficacy_endpoints / drug_sources /
catalysts / entity_edges — i.e. already cleaned, only the open violation row remained. All 15 marked
`resolved=true` (resolved_by=`claude-governance-triage-2026-06-18`, full `resolution_notes`). Governance 38 → 23.

## ⏳ PENDING — 23 LIVE mislinks (need Kyle's row-by-row approval; deletes per CLAUDE.md)
Verified against the live CT.gov record (a token-matcher is NOT trusted here — it mis-judged both `verekitug`
and `apg279`, so each row carries explicit evidence/caveat).

| drug_id | NCT | stored in | CT.gov study (actual) | recommended | caveat |
|---|---|---|---|---|---|
| apg279 | NCT06395948 | trials+drug_sources | A Study Evaluating APG777 in Atopic Dermatitis | REVIEW | APG777≠APG279 (different Apogee assets per repo history) → WRONG despite name echo |
| apg333 | NCT06137170 | trials+drug_sources | A Real-World Study to Learn More About the Order of Differen | REMOVE (registry/observational — not the drug's trial) |  |
| bimekizumab | NCT07149792 | drug_sources | A Multi-center RCT Clinical Trial on Personalized Precision  | REMOVE (different asset in CT.gov) |  |
| filgotinib | NCT02714634 | drug_sources | Clinical Trial Evaluating Methotrexate or Leflunomide + Targ | REMOVE (different asset in CT.gov) |  |
| guselkumab | NCT07198113 | drug_sources | COMPARE - Pediatric Inflammatory Bowel Disease (PIBD) | REMOVE (registry/observational — not the drug's trial) |  |
| guselkumab-golimumab | NCT07177209 | drug_sources | Describing Treatment Patterns and Creating an Updated Treatm | REMOVE (registry/observational — not the drug's trial) |  |
| guselkumab-golimumab | NCT01848028 | drug_sources | PsoBest - The German Psoriasis Registry | REMOVE (registry/observational — not the drug's trial) |  |
| guselkumab-golimumab | NCT06089590 | drug_sources | Ibd CAncer and seRious Infections in France (I-CARE 2) | REMOVE (registry/observational — not the drug's trial) |  |
| inebilizumab | NCT06885957 | drug_sources | Monoclonal Antibody-Based Therapies for AQP4-Positive NMOSD | REMOVE (different asset in CT.gov) |  |
| kt501 | NCT06630806 | trials | A Study to Investigate the Safety and Efficacy of SAR446523  | REMOVE (different asset in CT.gov) |  |
| mepolizumab | NCT06748053 | trials | A Dose Finding Study With an Anti-TSLP Antibody (GSK5784283) | REMOVE (different asset in CT.gov) |  |
| mirikizumab | NCT07198113 | drug_sources | COMPARE - Pediatric Inflammatory Bowel Disease (PIBD) | REMOVE (registry/observational — not the drug's trial) |  |
| mt-251 | NCT07219368 | trials+drug_sources | A First-in-Human Single and Multiple Ascending Dose Study of | REMOVE (different asset in CT.gov) |  |
| risankizumab | NCT06399432 | drug_sources | Mediterranean Diet vs no Dietary Intervention for Improving  | REMOVE (different asset in CT.gov) |  |
| risankizumab-lutikizumab-or-trosunilimab | NCT06548542 | drug_sources | Study of Targeted Therapies for the Treatment of Adult Parti | REVIEW | composite combo entity; 'Targeted Therapies' study may legitimately include risankizumab → VERIFY |
| rituximab | NCT06242327 | drug_sources | An Outcome Analysis of Primary Membranous Nephropathy | REMOVE (registry/observational — not the drug's trial) |  |
| semaglutide | NCT07309094 | drug_sources | Clinical, Morphometric and Biochemical Effects on Adiposopat | REMOVE (different asset in CT.gov) |  |
| spx306 | NCT06259552 | drug_sources | A Study of SPX-303, a Bispecific Antibody Targeting LILRB2 a | REMOVE (different asset in CT.gov) |  |
| spy230 | NCT07012395 | drug_sources | A Study of Long-acting Antibodies Alone and in Combinations  | REMOVE (different asset in CT.gov) |  |
| tralokinumab | NCT03549416 | drug_sources | BioDay Registry: Data Collection Regarding the Use of New Sy | REMOVE (registry/observational — not the drug's trial) |  |
| upadacitinib | NCT06136767 | trials | Registry for Systemic Eczema Treatments | REMOVE (registry/observational — not the drug's trial) |  |
| verekitug--upb-101 | NCT06981078 | trials+drug_sources | A Study to Assess the Efficacy and Safety of Verekitug in Pa | REVIEW | CT.gov title IS Verekitug → FALSE POSITIVE, keep link, resolve violation |
| win027 | NCT07120503 | drug_sources | Study to Evaluate the Safety, Pharmacology and Efficacy of W | REMOVE (different asset in CT.gov) |  |

**Notes for the fix batch:** (1) `drug_sources` removals are low-risk (delete the wrong source row). (2) `trials`
removals must also drop any `TESTED_IN`/`PRESENTED` edges on that NCT (via EdgeWriter) to avoid orphans. (3) Mark each
violation `resolved` with a note recording the action. (4) `verekitug--upb-101` = FALSE POSITIVE → keep link, just
resolve. (5) `apg279`←APG777 and the combo entity need a human eye (domain nuance).
