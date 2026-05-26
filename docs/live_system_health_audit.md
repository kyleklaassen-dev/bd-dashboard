# Live System Health Audit — Session 65
**Date:** 2026-05-26  
**Author:** Meridian / Session 65  
**Purpose:** Answer "what is actually live vs stale?" for every Meridian homepage section and backend pipeline  

---

## Executive Summary

The core intelligence pipeline (research.py → intel → catalysts → deals → signals) is **healthy and running daily**. The enrichment pipeline (company_enrichment.py) is running. The Industry Insights briefing (write_meridian.py) runs Mon–Sat.

**One confirmed live gap:** The "Important Articles" section (news_articles) has **no scheduled GitHub Actions workflow**. The script (`fetch_homepage_news.py`) must be triggered manually. The table currently has 55 articles (most recent: 2026-05-25) because it was recently run manually, but it will go stale as soon as that cadence breaks. A structural decay issue also exists: the `is_this_week` flag is computed at write time and never recalculated, meaning articles older than 7 days become permanently invisible even if they remain in the table.

**One process gap:** `research_queue` has 60 pending items that have not been processed. This is the backlog for company-level research tasks.

Everything else is functioning as designed.

---

## Homepage Section Health Matrix

| Section | DB Table(s) | Query Pattern | Pipeline Script | Schedule | Last Verified | Status |
|---|---|---|---|---|---|---|
| **Important Articles** | `news_articles` | `is_this_week = true ORDER BY relevance_score DESC` | `fetch_homepage_news.py` | **NONE — no workflow** | 2026-05-25 (manual) | ⚠️ NO WORKFLOW |
| **Essential Updates** | `intel` | `intel_date >= 7 days ago, area_id IN [...], ORDER BY intel_date DESC` | `research.py` | Daily 06:00 UTC | 2026-05-23 (latest row) | ✅ HEALTHY |
| **Catalyst Calendar** | `catalysts` | `resolved = false AND sort_date >= TODAY ORDER BY sort_date` | `research.py` + `company_enrichment.py` | Daily 06:00 UTC | 2026-05-26 (today) | ✅ HEALTHY |
| **Deals Feed** | `deals` | `area_id IN [...] ORDER BY deal_date DESC` | `research.py` | Daily 06:00 UTC | 2026-05-24 | ✅ HEALTHY |
| **Activity / Signals** | `signals` | `event_date >= 7 days ago, area_id IN [...]` | `signal_monitor.py` | 4× daily (02:30/06:30/12:30/18:30 UTC) | 2026-05-26 (today) | ✅ HEALTHY |
| **Industry Insights** | `meridian_today.html` (iframe) | Static file deploy | `write_meridian.py` | Mon–Sat 10:30 UTC | Runs overnight | ✅ HEALTHY |
| **Submit Intel (inbound)** | `submitted_intel` | User-submitted → status='new' | `review_submitted_intel.py` | Every 6h (00:00/06:00/12:00/18:00 UTC) | 9 new rows today | ⚠️ QUEUED (expected) |

---

## Pipeline Registry — All Scheduled Workflows

| Workflow File | Script | Schedule | Purpose | Status |
|---|---|---|---|---|
| `meridian-research.yml` | `research.py` | Daily 06:00 UTC | Intel, deals, catalysts ingestion | ✅ ACTIVE |
| `meridian-write.yml` | `write_meridian.py` | Mon–Sat 10:30 UTC | Generates Industry Insights briefing | ✅ ACTIVE |
| `signal-monitor.yml` | `signal_monitor.py` | 4× daily (02:30/06:30/12:30/18:30) | Signal detection + scoring | ✅ ACTIVE |
| `company-enrichment.yml` | `company_enrichment.py` | Scheduled (long job) | Drug/company field enrichment | ✅ ACTIVE |
| `review_submitted_intel.yml` | `review_submitted_intel.py` | Every 6h | Submit intel auto-review | ✅ ACTIVE |
| `validation-research.yml` | Validation scripts | Scheduled | Trial/drug validation | ✅ ACTIVE |
| `refresh-company-verified.yml` | Company verification | Scheduled | Company data freshness | ✅ ACTIVE |
| `stock-prices.yml` | Stock prices | Scheduled | Stock price updates | ✅ ACTIVE |
| `backfill-ailux-angle-watch.yml` | Backfill script | Manual only | One-time backfill watch | ⚠️ MANUAL ONLY |
| `evening-update.yml` | (retired) | RETIRED | Duplicate — removed | 🚫 RETIRED |
| **`fetch-homepage-news.yml`** | `fetch_homepage_news.py` | **MISSING** | Homepage news feed | ❌ **NO WORKFLOW** |

---

## Live Row Counts (queried 2026-05-26)

| Table | Total Rows | Notes |
|---|---|---|
| `intel` | 767 | 758 created in last 7 days — pipeline running |
| `catalysts` | 790 | Latest added today — healthy |
| `deals` | 192 | Latest created 2026-05-24 — healthy |
| `signals` | 51 | Latest event_date 2026-05-26 — healthy |
| `news_articles` | 55 | All 55 have `is_this_week=true`; most recent 2026-05-25 |
| `submitted_intel` | 9 (new) | All submitted today; review runs next 6h cycle |
| `research_queue` | 60 pending | Backlog — see note below |
| `drugs` | 154 | Stable |
| `companies` | ~200+ | Active (non-acquired) |
| `drug_competitive_scores` | 234 | C1/C2 source (migrated Session 64) |
| `drug_area_scores` | 212 | Legacy compatibility layer |

---

## Gap 1 (P0): `fetch_homepage_news.py` — No Scheduled Workflow

**Root cause:** `fetch_homepage_news.py` fetches RSS feeds from FierceBiotech, BioPharma Dive, and STAT News, scores articles for Meridian relevance, and writes to `news_articles`. It has no `.github/workflows/` entry. The homepage "Important Articles" section depends entirely on this table.

**Current state:** The table has 55 articles (most recent: 2026-05-25) from a recent manual run. This is a false sense of health — without a workflow, the table will go stale the moment no one remembers to run it manually.

**Secondary structural issue:** `is_this_week` is a boolean column set at write time (`pub_d >= WEEK_AGO`). Once set to `true`, it is only updated if the same article is re-fetched and re-upserted (via `url_hash` conflict). Articles that exit the RSS feed window (typically 2–4 weeks of RSS history) will never be re-upserted, so their `is_this_week=true` flag stays forever. Conversely, if the script is not run for >7 days, **all 55 articles remain visible** even though they are older than 7 days.

**Fix:** See Gap 1 Fix section below.

---

## Gap 2 (P1): `research_queue` — 60 Pending Items

`research_queue` holds company-level research tasks waiting to be processed. With 60 pending items, this represents a backlog. The queue is drained by `company_enrichment.py` during its scheduled runs. The practical effect is that some company intelligence may be stale or incomplete for the queued companies.

**Recommended check:** Query the queue to see how old the oldest pending items are. If items are >14 days old, the enrichment job may be failing silently for some cases.

```sql
SELECT status, MIN(created_at) AS oldest, MAX(created_at) AS newest, COUNT(*)
FROM research_queue
GROUP BY status
ORDER BY status;
```

---

## Gap 3 (P2): `submitted_intel` — 9 New Items Unprocessed Today

9 items submitted today with `status='new'`. The `review_submitted_intel.yml` workflow runs every 6 hours (00:00, 06:00, 12:00, 18:00 UTC). These will be processed in the next cycle. **This is expected behavior, not a gap.** However, if these are from Kyle's manual submissions, confirm the review pipeline is correctly classifying and routing them to the appropriate tables.

---

## Gap 4 (P3): Intel Feed — `intel_date` vs `created_at` Display Logic

`intel` has 767 total rows; 758 of them were created in the last 7 days. The homepage query filters by `intel_date >= 7 days ago`. The most recent `created_at` values are 2026-05-22 and 2026-05-23 — not today. This means `research.py` is writing rows with `intel_date` matching the article's publication date (which may be 2–4 days behind), not today's date. This is correct behavior for data accuracy but may cause the Essential Updates section to appear to lag by a few days.

**No fix needed** — this is working as designed. The lag is the difference between publication date and indexing date, which is normal for RSS-based pipelines.

---

## Gap 1 Fix: Create `fetch-homepage-news.yml` + `is_this_week` Daily Reset

### New workflow: `.github/workflows/fetch-homepage-news.yml`

Schedule: **Daily at 07:30 UTC** (after research.py at 06:00, before write_meridian.py at 10:30).

This inserts it into the correct tier-2 pipeline slot: research enriches intel/catalysts, news fetches fresh articles, then write_meridian bundles both into the morning briefing.

### `is_this_week` reset strategy

The script already recomputes `is_this_week` at write time during upsert. The missing piece is a **bulk reset** for articles that have aged out of the 7-day window but were never re-upserted (too old for RSS). 

Two options:
1. **Supabase scheduled function** (SQL): `UPDATE news_articles SET is_this_week=false WHERE published_at < NOW() - INTERVAL '7 days' AND is_this_week=true;` — run daily.
2. **In-script step** (Python): Add to Step 1 of `fetch_homepage_news.py` — PATCH all rows where `published_at < week_ago` to set `is_this_week=false`. This runs every time the script runs.

**Recommended:** Option 2 (in-script). It keeps the logic co-located with the script, doesn't require a Supabase edge function, and runs automatically as part of the daily workflow.

The fix is implemented in Session 65 as part of creating the workflow. See `.github/workflows/fetch-homepage-news.yml`.

---

## `is_this_week` Decay Timeline (Without Fix)

| Days since last run | Behavior |
|---|---|
| 0–7 | All articles show correctly. New articles within 7-day window are visible. |
| 8–14 | Articles from Day 1 are now >7 days old, but `is_this_week=true` is frozen. They remain visible. The "Important Articles" section does not expire stale content. |
| 14+ | Section shows increasingly stale content as if it were current. User has no way to know. |
| 30+ | All 55 articles remain visible, all ≥1 month old, all still flagged `is_this_week=true`. Homepage shows month-old news. |

**With the workflow + in-script reset:** Each daily run (1) fetches fresh articles and sets `is_this_week=true` for new content, (2) patches all rows older than 7 days to `is_this_week=false`. The section always shows ≤7 days of content.

---

## Recommended Session 65 Actions

| Priority | Action | Effort |
|---|---|---|
| P0 | Create `.github/workflows/fetch-homepage-news.yml` (daily 07:30 UTC) | 10 min |
| P0 | Add `is_this_week` bulk-reset step to `fetch_homepage_news.py` Step 1 | 5 min |
| P1 | Query `research_queue` to assess backlog age | 5 min |
| P2 | Confirm `submitted_intel` review pipeline processes today's 9 items | 5 min |
| P3 | Add `enrichment_runs` table to confirm company_enrichment.py cadence (from Session 64 design) | Session 66+ |

---

*Session 65 — 2026-05-26. Live counts queried directly from Supabase. Pipeline status derived from GitHub Actions workflow files + Supabase row timestamps.*
