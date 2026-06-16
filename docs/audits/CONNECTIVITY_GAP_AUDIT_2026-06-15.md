# Connectivity Gap Audit — Backend Data Not Surfaced on the Live Dashboard

**Date:** 2026-06-15 · **Author:** Claude (cowork, read-only recon) · **Scope:** newer intelligence tables vs. `index.html` (the live dashboard) and `Meridian_Live.html`.
**Method:** REST count of every target table (Supabase `tghntyofptvfhmtchwcv`, `Prefer: count=exact`) cross-referenced against the **112 distinct objects** queried by `index.html`'s **376 `.from()` calls**, plus per-reference tab/function tracing to separate *live* surfacing from *dead-tab* surfacing.
**Companion audits:** `DASHBOARD_BINDING_AUDIT.md` (focused on trial-detail tables) and `DASHBOARD_REORG_PLAN_2026-06-12.md` (the 5-surface target shape). This audit focuses on the **newer relationship/intelligence tables** those two did not fully cover.

> Read-only. No DB writes, no file edits to the dashboard, no deploy.

---

## Headline

The wiring is *clean* (0 broken bindings, 0 dark tables — confirmed). The gap is **value sitting in well-structured, source-bearing tables that no live surface reads.** Three patterns:

1. **Genuinely HIDDEN** — 9 newer tables (≈4.3k rows of genetic validation, manufacturing, EU regulatory, trial-design quality, KOL authorship/metrics, conference signals, ownership) are queried by **no** HTML file at all.
2. **Dead-tab PARTIAL** — the narrative trust layer (`narrative_provenance` 4,137 + `narrative_claim_triangulation` 195) is wired only inside the **retired `changes-feed` tab** (nav button removed 2026-06-06). The *per-drug* narrative path IS live (drug modal), but the standalone provenance/triangulation surface is unreachable.
3. **Search-only PARTIAL** — several intelligence tables (`kols`, `indication_patient_intelligence`, `intel_facts`, `strategic_insights`, `grants`) are reachable only as keyword hits in global search (`_gsSbSearch`) or buried in one feed, with no dedicated panel.

---

## (a) Backend feature → row count → surfacing status

Row counts are exact (REST `count=exact`, 2026-06-15).

| Backend table | Rows | Status | Where it surfaces (or doesn't) |
|---|---:|---|---|
| **target_genetics** (gnomAD constraint, LoF intolerance) | 117 | **HIDDEN** | No HTML reads it. Index uses `target_proteins`/`target_disease_associations` only. |
| **target_disease_assoc** (Open Targets scores) | 1,537 | **HIDDEN** | Distinct table from the queried `target_disease_associations` (600 rows). The 1,537-row version with `genetic_association_score` etc. is unread. |
| **company_patents** | 532 | SURFACED | Company entity modal (`openCompanyEntityModal`, line 13164). |
| **company_events** (SEC 8-K/financing) | 427 | SURFACED | Industry Insights feed (`loadIndustryInsightsFeed`) + global search. |
| **company_ownership** (LEI parent chains) | 14 | **HIDDEN** | No HTML reads it. Index uses `ownership_edges` (116) instead. |
| **manufacturing_sites** (FDA establishment, in-house flag, supply-deal candidates) | 51 | **HIDDEN** | No HTML reads it. |
| **regulatory_designations** (orphan/BTD/fast-track) | 197 | SURFACED | Drug entity modal (`openDrugEntityModal`, line 16792). |
| **eu_approvals** (EMA dates, EU-vs-US lag) | 47 | **HIDDEN** | No HTML reads it. Index uses `fda_approvals`/`geographic_approvals` only. |
| **kol_metrics** (h-index, citation counts) | 5 | **HIDDEN** | No HTML reads it. (Thin: only 5 rows.) |
| **publication_authors** (authorship → KOL → institution) | 1,060 | **HIDDEN** | No HTML reads it. `kols` itself appears only in global search. |
| **strategic_insights** | 532 | PARTIAL | Industry Insights feed + global search only; no dedicated panel. |
| **entity_edges** (the graph spine) | 28,227 | SURFACED | Ontology explorer (`ontologyLoad`, line 31257); also drug/company graph views. |
| **indication_patient_intelligence** | 28 | PARTIAL | Global search hits only (line 33599). Market-stat cards still hardcoded (per reorg §5). |
| **narrative_provenance** (claim→source) | 4,137 | PARTIAL | Live per-drug in drug modal (`_loadMeridianNarrative`, line 14257→16854). Standalone surface (line 34312) is in the **dead `changes-feed` tab**. |
| **narrative_claim_triangulation** | 195 | **HIDDEN (dead tab)** | Only read at line 34313 inside retired `changes-feed`. No live surface. |
| **grants** (NIH/agency funding) | 642 | PARTIAL | Industry Insights feed + global search only. |
| **trial_design_quality** (randomized/controlled, quality_score/tier) | 1,398 | **HIDDEN** | No HTML reads it. High value, large table. |
| **conference_abstract_signals** (late-breaker, readout phase/direction, signal_score) | 451 | **HIDDEN** | No HTML reads it. Index uses raw `conference_abstracts` (451) for titles, not the *signal* layer. |
| **drug_efficacy_endpoints** | 12 | SURFACED | Drug entity modal (line 16932). Thin table. |
| **payer_tpp_criteria** | 17 | SURFACED | Drug entity modal (line 17082). |
| drugs / companies / catalysts / deals (core) | 194 / 191 / 1,361 / 218 | SURFACED | Throughout. |
| publications | 3,184 | SURFACED | Industry Insights + global search + literature. |
| conference_abstracts | 451 | SURFACED | Industry Insights + global search (titles only). |
| target_disease_associations | 600 | SURFACED | Drug/target modal (line 17036). |
| kols | 316 | PARTIAL | Global search hits only (line 33594); no KOL panel. |

**Confirmed dead/retired tabs** (carry queries but no nav button): `changes-feed` (retired 2026-06-06), `pharma-intel`, `stocks`. The Relationships tab referenced in the task is gone from the nav strip; its function (graph) now lives in the Ontology explorer (`entity_edges`).

---

## (b) Prioritized — top items to wire in (highest value first)

Effort is rough: **S** = add one query + one panel to an existing modal/tab; **M** = new sub-panel + light layout; **L** = new surface/tab.

1. **trial_design_quality (1,398 rows) → Drug modal "Development" + Landscapes PI table.** *Value:* lets every trial show randomized/controlled + a quality_score/tier and "why_stopped" — separates real Phase-2 evidence from open-label noise, directly serving Bill's "does the asset survive?" test. *Effort:* **M** (join on `nct_id`/`drug_id`).

2. **conference_abstract_signals (451) → Landscapes + Today early-warning.** *Value:* THE preclinical/poster early-warning layer (`is_late_breaker`, `is_clinical_readout`, `readout_phase`, `result_direction`, `signal_score`) — this is the platform's stated edge ("earlier than anyone"). Currently only raw titles show. *Effort:* **M**.

3. **target_disease_assoc (1,537, Open Targets) + target_genetics (117, gnomAD) → Landscapes "Biology" / target view.** *Value:* genetic validation of a target (`genetic_association_score`, LoF intolerance) is the scientific backbone for "is the science real?" — the strongest answer to the differentiation question. *Effort:* **M** (the queried 600-row `target_disease_associations` is a thinner duplicate; reconcile to the richer table).

4. **eu_approvals (47) → Drug modal regulatory timeline.** *Value:* EU approval dates + `eu_vs_us_lag_days` + biosimilar flag — ex-US commercial picture and a clean precedent signal. Drug modal already shows FDA; this completes the geography. *Effort:* **S**.

5. **manufacturing_sites (51) → Drug/Company modal "Business".** *Value:* `is_inhouse` + `is_supplies_candidate` + manufacturer→company link surfaces CDMO/supply-deal BD angles and make-vs-buy — a deal vector nothing else exposes. *Effort:* **S–M**.

6. **narrative_claim_triangulation (195) + standalone narrative_provenance surface → revive into a live trust panel.** *Value:* per-claim independence/triangulation is the "trusted intelligence, not AI summaries" promise; the code already exists but only in the dead `changes-feed` tab. *Effort:* **S** to relink the existing block to a live tab (e.g., Today or the drug modal's narrative footer); **M** to do it well.

7. **indication_patient_intelligence (28) → bind the hardcoded market-stat cards.** *Value:* replaces frozen hardcoded patient-count/market-size numbers (reorg §5 item 3) with the live table; honesty + freshness. Currently search-only. *Effort:* **S** per card.

8. **strategic_insights (532) → a dedicated "Insights" panel (Today or Fit).** *Value:* 532 derived cross-table insights with `metric` + `source_tables` are buried in one scrolling feed; a ranked panel makes the platform's own conclusions first-class. *Effort:* **M**.

9. **kols (316) + publication_authors (1,060) + kol_metrics (5) → a KOL panel on the drug/indication/target view.** *Value:* "who are the experts and where" (institution, country, h-index, corresponding-author) is a standard BD/diligence question with zero current home beyond a search hit. *Effort:* **M** (kol_metrics is thin — backfill first).

10. **grants (642) → Landscapes/target "funding momentum" strip.** *Value:* NIH/agency funding by `matched_target` is a leading indicator of a target heating up; currently only in the Industry feed. *Effort:* **S–M**.

11. **company_ownership (14) → Company modal ownership block / reconcile with ownership_edges.** *Value:* LEI parent-chain (`parent_legal_name`, `parent_company_id`) closes subsidiary/parent provenance the governance rules care about. *Effort:* **S** (low rows; mostly a reconcile decision vs. `ownership_edges`).

---

## (c) Quick wins (S effort, high clarity, low risk)

- **eu_approvals (#4)** — one query in the already-open drug modal; instantly adds EU dates + US-lag to the regulatory section.
- **indication_patient_intelligence (#7)** — swap 3 hardcoded market-stat cards to the live table; kills static content the reorg flagged.
- **Relink the narrative trust block (#6)** — the triangulation/provenance rendering already exists at lines 34271–34408; it's stranded in the retired `changes-feed` tab. Pointing it at a live container resurrects 4,332 rows of trust data with no new code.
- **manufacturing_sites supply-candidate filter (#5)** — `is_supplies_candidate=true` is a ready-made BD list; even a raw table view in the company modal is useful day one.

---

## Notes & caveats

- **Thin tables** (defer or backfill first): `kol_metrics` (5), `drug_efficacy_endpoints` (12), `company_ownership` (14), `payer_tpp_criteria` (17), `indication_patient_intelligence` (28). Wire the structure, but value scales only after population.
- **Duplicate-name trap:** `target_disease_assoc` (1,537, unread) vs. `target_disease_associations` (600, queried); `conference_abstract_signals` (451, unread) vs. `conference_abstracts` (451, queried). The *richer/derived* one is the hidden one in both cases — reconcile before wiring, don't double-build.
- **`drug_efficacy_endpoints` only has 12 rows** despite being cited as the efficacy spine; the larger efficacy data lives in the trial-outcome tables called out by `DASHBOARD_BINDING_AUDIT.md` (`trial_outcome_measures`, `v_uc_induction_benchmark`, etc.) — out of scope here but the bigger efficacy win.
- All wiring is **display work in a 34k-line file** — best done panel-by-panel with a screenshot review, per the reorg plan, and only after the stabilization writer-enforcement gate closes.
