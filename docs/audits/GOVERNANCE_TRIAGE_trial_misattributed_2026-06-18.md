# Governance triage — `trial_misattributed_*` — 2026-06-18 ✅ COMPLETE (38 → 0 unresolved)

Surfaced by `scripts/maintenance/intelligence_quality.py`. Producer: CT.gov identity checks. Every one of the
38 open `trial_misattributed_*` violations was triaged against the **authoritative CT.gov record** (API v2:
title + interventions + sponsor + studyType) — never on a token-matcher (which mis-judged both `verekitug` and
`apg279`). All 38 are now resolved with in-row audit notes; reversible backup at `/tmp/governance_fix_backup.json`.

## Outcome
| disposition | n | action |
|---|---|---|
| **STALE** | 15 | link already absent from trials/efficacy/drug_sources/catalysts/edges → marked `resolved` (log hygiene) |
| **REMOVE** | 20 | CT.gov shows a different asset or a pure observational registry → deleted the wrong `trials`/`drug_sources` row(s) (6 trials + 18 sources), then `resolved` |
| **KEEP (false positive)** | 3 | CT.gov confirms the trial genuinely studies the drug/combo → link retained, violation `resolved` |

## REMOVE detail (CT.gov intervention = the real asset)
apg279←APG777 · apg333←Regorafenib(Bayer real-world) · kt501←SAR446523(Sanofi) · mepolizumab←GSK5784283(anti-TSLP) ·
mt-251←MT-201(Mirador) · spx306←SPX-303(SparX) · win027←WIN378(Windward) · filgotinib←MTX/leflunomide study ·
bimekizumab←precision-medicine platform · risankizumab←Mediterranean-diet study · semaglutide←GLP-1-class observational ·
guselkumab/mirikizumab←COMPARE-PIBD registry · guselkumab-golimumab←{PsoBest, I-CARE 2, Pfizer treatment-patterns} ·
inebilizumab←generic mAb NMOSD registry · rituximab←membranous-nephropathy outcome analysis · tralokinumab←BioDay registry ·
upadacitinib←Systemic Eczema registry.

## KEEP detail (validator slug-match false positives — verified correct)
- `verekitug--upb-101` ← NCT06981078 — CT.gov interventions = **Verekitug** (Upstream Bio).
- `risankizumab-lutikizumab-or-trosunilimab` ← NCT06548542 — AbbVie study arms = **Risankizumab/Lutikizumab/Trosunilimab**.
- `spy230` ← NCT07012395 — Spyre Phase-2 platform trial of SPY001/002/003 **+ combinations**; SPY230 is a Spyre combination
  ([spyre.com/pipeline](https://www.spyre.com/pipeline)).

## Reversibility
`/tmp/governance_fix_backup.json` holds the full pre-delete content of every removed `trials`/`drug_sources`/edge row.
