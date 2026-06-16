# Company Identity Audit & Cleanup Plan
**Session 66 — 2026-05-26**

---

## Summary

The company entity layer is in good shape. The audit found no case duplicates, no slash-compound names, and no acquired companies missing a parent_company_id. The primary actionable findings are: one intentional branding exception (argenx), one missing entity (Ventyx), one ownership relationship gap (Chugai/Roche), and a large cohort of score-0 reference companies that are deal counterparties with no pipeline data.

---

## Table 1 — Identity Violations

| Company | Issue | Recommended Action | Class |
|---|---|---|---|
| argenx | Name stored as `argenx` (all lowercase) | No action — intentional brand styling per company (argenx SE uses lowercase officially). Document as exception. | Exception |
| Ventyx Biosciences | Not in companies table at all | Add as `status='acquired', parent_company_id='abbvie'`. Add VTX002 (S1P1 receptor modulator) as drug with `company_id='ventyx'`. Required for Session 66 acceptance test. | Missing entity |
| Chugai Pharmaceutical | `parent_company_id = NULL` — Roche owns ~63% | Hold for review. Chugai operates with significant autonomy (separate Tokyo listing, independent pipeline). Recommend setting `parent_company_id='roche'` only if Chugai assets will be displayed under Roche card. Do not merge. | Class 3 (hold) |
| Genentech | Aliased under Roche as subsidiary alias; no standalone company row | Acceptable as-is if no Genentech-specific drugs/catalysts exist. If Genentech-sourced assets enter the pipeline, create `status='acquired', parent_company_id='roche'` row. | Class 3 (monitor) |

**Class 1 fixes executed this session:** None required — database passes all identity checks.

---

## Ownership Relationships — Current State

The `ownership_edges` table contains 2 company-level ACQUIRED edges:
- `candid --[ACQUIRED]--> ucb`
- `prometheus --[ACQUIRED]--> merck`

The `companies` table carries `parent_company_id` for 4 acquired entities:
- Kali Therapeutics → Sanofi
- Prometheus Biosciences → Merck
- Telavant Holdings → Roche
- Candid Therapeutics → UCB

**Critical rule:** Never merge acquired company rows into their acquirer. The separate entity preserves drug origin story, clinical attribution, deal history, and acquisition chain. Display layer shows "X (a Y company)"; the data layer preserves both.

---

## Table 2 — Connectivity Scorecard (Top 30 by Drug Count)

Scoring: 20 pts each for drugs linked, catalysts linked, deals linked, news articles linked, ownership set. Max 100.

| Company | Drugs | Cats | Deals | News | Own | Score | Gap |
|---|---|---|---|---|---|---|---|
| Roche | 12 | 33 | 1 | 1 | — | 80 | No deals gap (1 deal); no ownership edge (Telavant covers it) |
| Johnson & Johnson | 9 | 32 | 26 | 0 | — | 60 | **No news match** — 26 deals but 0 matched_company_ids |
| AbbVie | 9 | 30 | 8 | 0 | — | 60 | **No news match** — likely alias mismatch in fetch_homepage_news.py |
| Spyre Therapeutics | 7 | 10 | 2 | 0 | — | 60 | No news (expected — small company) |
| UCB | 7 | 14 | 6 | 0 | — | 60 | No news |
| Amgen | 6 | 40 | 13 | 0 | — | 60 | **No news match** — major pharma with 0 articles is anomalous |
| Sanofi | 6 | 42 | 22 | 0 | — | 60 | **No news match** — anomalous |
| Novartis | 6 | 23 | 0 | 1 | — | 60 | No deals linked |
| AstraZeneca | 5 | 26 | 6 | 1 | — | 80 | — |
| Eli Lilly | 5 | 16 | 12 | 7 | — | 80 | — |
| Merck & Co. | 4 | 21 | 3 | 5 | — | 80 | — |
| Apogee Therapeutics | 4 | 10 | 1 | 0 | — | 60 | No news (expected) |
| Regeneron | 3 | 23 | 15 | 1 | — | 80 | — |
| Earendil | 3 | 13 | 5 | 0 | — | 60 | No news (expected) |
| Immunovant | 2 | 15 | 6 | 3 | — | 80 | — |
| Pfizer | 2 | 13 | 2 | 1 | — | 80 | — |
| argenx | 2 | 9 | 4 | 0 | — | 60 | No news |
| Generate:Biomedicines | 2 | 25 | 2 | 0 | — | 60 | No news |
| Qyuns Therapeutics | 2 | 17 | 6 | 0 | — | 60 | No news |
| Simcere | 2 | 12 | 1 | 0 | — | 60 | No news |
| Xencor | 2 | 16 | 3 | 0 | — | 60 | No news |
| Mirador Therapeutics | 2 | 24 | 1 | 0 | — | 60 | No news |
| Kyverna Therapeutics | 2 | 19 | 1 | 0 | — | 60 | No news |
| Newsoara Biopharma | 2 | 2 | 0 | 0 | — | 40 | No deals, no news |
| Windward Bio | 2 | 7 | 0 | 0 | — | 40 | No deals, no news |
| Novamab Biopharmaceuticals | 2 | 11 | 0 | 0 | — | 40 | No deals, no news |
| Episcience | 2 | 6 | 0 | 0 | — | 40 | No deals, no news |
| Novo Nordisk | 2 | 0 | 0 | 1 | — | 40 | No catalysts, no deals |
| Viridian Therapeutics | 2 | 1 | 0 | 0 | — | 40 | Near-zero catalysts |
| GSK | 2 | 12 | 0 | 0 | — | 40 | No deals, no news |

---

## Score < 40 — Low-Connectivity Companies

46 companies score below 40. Two categories:

**Score-20 (single dimension only):** 19 companies with drugs but no catalysts/deals/news. These are mostly emerging biotech or Chinese biopharma pipeline companies (Alumis, MoonLake, Innovent, Crinetics, etc.). They have pipeline assets but no enriched intelligence. Expected — these are secondary tracking entities, not primary Ailux targets.

**Score-0 (no connected data):** 27 companies with zero drugs, catalysts, deals, or news matches. These are deal counterparties or sector reference entities (Celgene, Bayer, WuXi Biologics, Astellas, various Chinese pharma). They were added as part of deal enrichment but have no pipeline data in the Meridian universe.

| Company | Issue | Recommendation |
|---|---|---|
| Teva Pharmaceutical | 0 drugs, 10 catalysts — orphaned catalysts | Investigate: are these catalysts correctly assigned? Check catalyst company_id='teva'. |
| Roivant Sciences | 0 drugs, 3 deals | Expected — Roivant is a holding company; track Aruvant, Kiniksa, Kiora as subsidiaries instead |
| Biogen | 0 drugs, 4 news articles | Pipeline not tracked; news articles match 'biogen' but no drugs in system |
| Bristol Myers Squibb, Celgene, Bayer, WuXi, Vertex, etc. | Score 0 | Reference entities — no action needed unless assets enter tracking universe |

---

## News Routing Gap — Root Cause

12 of 55 news_articles have company matches. Top matched: Lilly (7), Merck (5), Biogen (4). Major companies with 0 news matches despite large pipelines: J&J (26 deals), AbbVie (9 drugs, 30 catalysts), Amgen (40 catalysts), Sanofi (42 catalysts).

**Likely cause:** `fetch_homepage_news.py` matches company names against article text using fuzzy matching. These companies may be mentioned under different names (Janssen, ABBV, MSD, Enbrel) that aren't in company_aliases, or the articles covering their pipelines simply haven't been fetched yet.

**Fix:** This is not a company entity integrity problem. It is a `fetch_homepage_news.py` alias coverage problem. When the daily workflow runs, check if J&J/AbbVie aliases (Janssen, ABBV, etc.) are in the matching set. No schema changes needed.

---

## Connectivity Depth Chain — Catalysts

```
Stored:     790
Linked:     790  (all have at least area_id set)
  drug_id:    143 catalysts
  company_id: 737 catalysts
  area_id:    790 catalysts
Queryable:  781  (unresolved + future sort_date)
Rendered:     ~790 (area tab calendar renders catalysts by area)
Reachable:    0   (drug card has no catalyst section — Fix 3B)
```

**Break point: Rendered → Reachable.** Data is fully linked and queryable. The 143 drug-linked catalysts cannot reach the drug card because the drug card has no catalyst component yet (Fix 3B in this session).

---

## Connectivity Depth Chain — News Articles

```
Stored:     55
Linked:     55   (all have matched_company_ids or matched_drug_ids set at write time)
Queryable:  55   (all is_this_week=true — decay fix from Session 65 will correct this daily)
Rendered:   55   (homepage "Important Articles" renders them)
Reachable:  0    (drug card has no news section; company card shows news but only 12/55 have company matches)
```

**Break points:** 
- Drug card: Queryable → Rendered (no component — Fix 3A)
- Company card: correct component exists but only 12/55 articles have matched_company_ids populated

---

## Connectivity Depth Chain — Intel

```
Stored:     767
Linked:     767  (primary_company_id and/or area_id set)
Queryable:  767
Rendered:   ~767 (area tab intel feed)
Reachable:  0    (company card ignores intel.primary_company_id — Fix 4)
```

**Break point: Rendered → Reachable (company card).** Intel is rendered in area tabs. It is not surfaced on the company card even though `primary_company_id` FK exists. Fix 4 closes this gap.

---

## Action Summary

| Action | Priority | Effort | Session |
|---|---|---|---|
| Add Ventyx Biosciences to companies (status=acquired, parent=abbvie) | P1 | 5 min | 66 |
| Add VTX002 to drugs (company_id=ventyx) | P1 | 5 min | 66 |
| Review Chugai / Roche ownership | P3 | 10 min | 67 |
| Investigate Teva orphaned catalysts | P3 | 15 min | 67 |
| Fix 3A: Drug card news section | P1 | 30 min | 66 |
| Fix 3B: Drug card catalyst section | P1 | 30 min | 66 |
| Fix 4: Company card intel section | P2 | 20 min | 66 |
| Fix 5: Area tab news routing | P3 | 20 min | 66 |
