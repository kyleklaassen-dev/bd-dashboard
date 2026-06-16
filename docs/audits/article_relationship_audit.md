# Article & Intelligence Routing Audit — Session 65
**Date:** 2026-05-26  
**Purpose:** Trace how articles move from ingestion to every user-visible surface. Identify where routing succeeds and where it goes dark.

---

## Routing Architecture — Two Parallel Pipelines

Meridian has two distinct article ingestion pipelines that produce different record types and surface through different mechanisms.

```
Pipeline A: research.py (RSS → intel + intel_areas + deals + catalysts)
Pipeline B: fetch_homepage_news.py (RSS → news_articles with matched entity arrays)
```

They are independent. An article that appears in Pipeline A does NOT appear in `news_articles`, and an article that scores in Pipeline B does NOT appear in `intel`. The user therefore sees two different "views" of the same news ecosystem depending on which surface they're on.

---

## Pipeline A — research.py → intel

### Ingestion
`research.py` runs daily at 06:00 UTC. It fetches from RSS sources, extracts intelligence using Claude, and writes structured rows to `intel` and `intel_areas`.

### Routing table

| Surface | Table queried | Filter | Status |
|---|---|---|---|
| Area tab intel feed (all 6 areas) | `intel` + `intel_areas` | `intel_areas.area_id = currentArea` | ✅ Connected |
| TL1A intel tab (L16320) | `intel` + `intel_areas` | `area_id='tl1a'` | ✅ Connected |
| Global intel search | `intel` | `intel_date >= 7d, ORDER BY intel_date` | ✅ Connected |
| Homepage "Essential Updates" | `intel` | Date-filtered, area-filtered | ✅ Connected |
| Drug card modal | **Not queried** | — | ❌ Not connected |
| Company card | **Not queried** | intel.primary_company_id unused | ❌ Not connected |
| Homepage news block | **Not queried** | Different pipeline (news_articles) | — |

### intel routing gaps

**Gap A1 — No company-level intel routing:**  
`intel` has a `primary_company_id` column but it is never used to filter intel in the company card. The company card's "Recent Coverage" section is populated from `news_articles` (Pipeline B), not `intel`. If research.py extracts an important piece of intelligence about AbbVie, it appears in the area tab and nowhere else accessible from the company's profile.

**Gap A2 — No drug-level intel routing:**  
`intel` has no `drug_id` foreign key. There is no mechanism to surface a specific intel item on a specific drug's card. Drug-specific intelligence from research.py is only discoverable by scanning the area tab's feed.

**Gap A3 — intel_areas coverage:**  
`intel_areas` only captures area-level routing. If an intel item spans two areas (e.g., a TL1A + IBD dual-angle story), it may only be tagged to one area depending on how research.py assigns `intel_areas` rows. Cross-area intel is hard to surface.

---

## Pipeline B — fetch_homepage_news.py → news_articles

### Ingestion
`fetch_homepage_news.py` is triggered manually (no scheduled workflow as of 2026-05-26). It fetches from FierceBiotech, BioPharma Dive, and STAT News, scores relevance, and writes to `news_articles` with three entity arrays pre-computed at write time: `matched_company_ids`, `matched_drug_ids`, `matched_area_ids`.

### Routing table

| Surface | Query | Filter | Status |
|---|---|---|---|
| Homepage "Important Articles" (L16161) | `news_articles` REST call | `is_this_week=true, source_validation_status≠invalid, review_status≠suppressed` | ✅ Connected |
| Company card "Recent Coverage" (L13101) | `_sb.from('news_articles').contains('matched_company_ids', [companyId])` | `.gte('published_at', 90dAgo)` | ✅ Connected |
| Drug card news (within company expansion) (L14411–14413) | `sbData.newsArticles.filter(a => a.matched_drug_ids.includes(d.id))` | Pre-filtered from company card load | ⚠️ Derived only |
| Drug card modal (`_cemDrugBody`) | **Not queried** | — | ❌ Not connected |
| Area tabs | **Not queried** | `news_articles.matched_area_ids` unused | ❌ Not connected |

### news_articles routing gaps

**Gap B1 — Drug card modal has no news:**  
The standalone drug card modal (`_cemDrugBody`, opened from drug rows, search results, URLs) does not query `news_articles`. Drug-specific news from Pipeline B is only visible inside the company card's drug row expansion. If a user opens a drug directly via drug ID, there is no news section.

**Gap B2 — Drug news is derived, not direct:**  
Drug news in the company card expansion is filtered from articles already loaded for the company (`sbData.newsArticles`). This means a drug will only see news if: (a) the drug's company was matched in `news_articles.matched_company_ids`, AND (b) the drug itself appears in `news_articles.matched_drug_ids`. If an article mentions the drug but not the company (common for branded names from small biotechs), it may score a company match for the wrong entity and be invisible on the right drug.

**Gap B3 — Area tabs have no news_articles surface:**  
`matched_area_ids` is populated on every `news_articles` row but is never queried in area tab rendering. The TL1A tab fetches `intel` (via intel_areas) but never fetches `news_articles WHERE matched_area_ids @> ['tl1a']`. Area users cannot see recent biotech news about their area in the area tab.

**Gap B4 — No scheduled ingestion (P0):**  
Confirmed in live_system_health_audit.md. The table goes stale without manual intervention. See fix in `.github/workflows/fetch-homepage-news.yml` (Session 65 deliverable).

---

## The Two-Pipeline Problem

The fundamental tension: research.py and fetch_homepage_news.py both ingest from biotech news RSS feeds but produce different record types with different routing. From a user's perspective, they are invisible to each other.

A concrete example of the breakage:

> AstraZeneca licenses a TSLP bispecific from a small biotech (published Monday).  
> research.py picks it up → writes to `intel` with `intel_areas.area_id='tslp'` → visible in TSLP area tab.  
> fetch_homepage_news.py picks it up → writes to `news_articles` with `matched_company_ids=['astrazeneca']` and `matched_area_ids=['tslp']` → visible on AZ company card and homepage, but NOT in TSLP area tab's intel feed.  
> The drug card for the bispecific: no intel, no news.

This is not wrong — it's by design — but the gap is that neither pipeline surfaces everywhere relevant.

---

## Recommended Routing Additions (Post-Session 65)

| Gap | Fix | Effort | Session |
|---|---|---|---|
| A1 — No company intel | Add `intel WHERE primary_company_id = companyId` to company card fetch | 30 min | Session 66 |
| B3 — No area news | Add `news_articles WHERE matched_area_ids @> [areaId]` to area tab data load | 45 min | Session 66 |
| B1 — No drug modal news | Add `news_articles WHERE matched_drug_ids @> [drugId]` to `_cemDrugBody` fetch | 30 min | Session 66 |
| A2 — No drug intel | Add `drug_id` FK to `intel` OR add intel to `_cemDrugBody` via intel content scan | 2–3h design + build | Session 67+ |
| B2 — Drug derivation | Add direct `matched_drug_ids` query to `_cemDrugBody` independent of company fetch | 30 min (bundled with B1) | Session 66 |

---

## intel_areas — Current Coverage

From index.html analysis, `intel_areas` is the canonical routing table for area-based intel:

- All 6 biological area PI tabs read from `intel_areas` with `area_id` filter
- TL1A intel tab: explicit `eq('area_id','tl1a')` query
- Global intel search: joins `intel_areas(area_id)` to render area tags
- intel rows without a corresponding `intel_areas` entry are invisible in all area tabs

The `intel_areas` table is populated by `research.py` during extraction. If research.py fails to classify an area for an article, it becomes unrouted and invisible in any area tab.

---

## submit_intel Routing

See `submit_intel_pipeline_audit.md` for the full flow. In terms of article routing: submitted intel that gets "Send to Queue" → `discovery_queue` → `company_enrichment.py` → may produce new `catalysts`, `deals`, or `intel` rows with proper area routing. The routing quality depends on `extracted_entities_json.areas[]` accuracy from the Claude analysis step.

---

*Session 65 — 2026-05-26. Analysis based on grep of index.html and live Supabase queries.*
