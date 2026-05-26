# Next Session — Session 66: Routing Fixes + Company Normalization

**Prepared:** 2026-05-26  
**Phase:** Phase 6 — Fact Connectivity & Canonical Display  
**Session 65 complete:** Live system health audit ✅ · P0 homepage news workflow created ✅ · is_this_week decay fix ✅ · Article routing audit ✅ · Submit intel pipeline audit ✅

---

## What Session 65 Established

Session 65 answered: *"Is the live system healthy?"*  
The answer: core pipeline (intel, catalysts, deals, signals) is healthy. One confirmed P0 gap fixed: `fetch_homepage_news.py` now has a scheduled workflow at 07:30 UTC daily. The `is_this_week` decay bug is patched.

Session 65 also produced three routing maps:
- `live_system_health_audit.md` — pipeline health by section
- `article_relationship_audit.md` — how articles route to surfaces
- `submit_intel_pipeline_audit.md` — full submit intel flow

Session 66 answers: *"Can we close the three highest-leverage routing gaps?"*

---

## Priority 0: Review Submitted Intel (5 min — START HERE)

9 items submitted 2026-05-26 with `status='new'`. By session start they should be `status='analyzed'` (review_submitted_intel.py runs every 6h).

Open the Submitted Intel tab. For each analyzed item:
- ✅ Send to Queue (high confidence, no dup concern)
- ❌ Reject (irrelevant or duplicate)
- 💬 Needs Review (ambiguous, come back later)

**Do this before any code work.** Submitted intel is the highest-signal input in the system.

---

## Priority 1: Company Normalization Audit → `company_cleanup_plan.md`

**Do this before routing fixes.** Routing quality depends on entity quality. `news_articles.matched_company_ids` is populated at write time by fuzzy-matching company names against `companies.name`. If "AbbVie", "abbvie", and "ABBVIE" are three different `company_id` values, news articles matched to one variant will not surface on the other company cards. Fix company identity first — every downstream routing improvement depends on it.

```sql
-- Find likely duplicates (same name, different case)
SELECT LOWER(name) AS name_lower, array_agg(id ORDER BY id) AS ids, COUNT(*) AS ct
FROM companies
GROUP BY LOWER(name)
HAVING COUNT(*) > 1
ORDER BY ct DESC;

-- Find company/company patterns (slash-separated)
SELECT id, name FROM companies WHERE name LIKE '%/%' ORDER BY name;

-- Find lowercase names (should be title case)
SELECT id, name FROM companies WHERE name != INITCAP(name) AND name = LOWER(name) ORDER BY name;

-- Find acquired companies without parent_company_id
SELECT id, name, status FROM companies WHERE status = 'acquired' AND parent_company_id IS NULL ORDER BY name;

-- Find parent_company_id relationships (current state)
SELECT c.id, c.name, p.id AS parent_id, p.name AS parent_name
FROM companies c JOIN companies p ON c.parent_company_id = p.id
ORDER BY p.name, c.name;
```

Output: `docs/company_cleanup_plan.md` — table of violating companies with recommended action (merge, alias, ownership_edge, rename, split).

Execute safe fixes in the same session:
- Rename clearly misspelled or miscased names (direct UPDATE)
- Set `parent_company_id` for known acquired companies
- Do NOT merge row IDs without verifying FK dependencies first (check drugs, partnerships, catalysts, deals, company_areas for each id)

---

## Priority 2: Three Routing Fixes (from article_relationship_audit.md)

These are the three highest-leverage gaps with the lowest implementation cost. Each is a targeted fetch addition — no schema changes required.

### Fix 1A — Area tabs: Add news_articles surface (45 min)

**Gap B3:** `news_articles.matched_area_ids` is populated but never queried in area tabs. TL1A, TSLP, IL-4Rα, FcRn, IGF1R, BCMA area tabs show `intel` but not `news_articles`.

**Fix:** In each area tab data load, add a parallel fetch:
```javascript
const { data: areaNews } = await _sb.from('news_articles')
  .select('id,headline,source_name,published_at,article_url,relevance_score,meridian_summary,why_it_matters,matched_drug_ids,matched_company_ids')
  .contains('matched_area_ids', [areaId])
  .eq('is_this_week', true)
  .neq('source_validation_status', 'invalid')
  .order('relevance_score', { ascending: false })
  .limit(10);
```

Render as a "Recent Coverage" block in the area tab, below the intel feed. Style identically to the company card's news section.

### Fix 1B — Company card: Add intel surface (30 min)

**Gap A1:** `intel.primary_company_id` exists but is never used to filter intel on company cards. Company card "Recent Coverage" shows `news_articles` but not `intel`.

**Fix:** In `openCompanySlideOver` data fetch (around L9693), add:
```javascript
const { data: companyIntel } = await _sb.from('intel')
  .select('id,intel_date,headline,intel_type,source_url,importance')
  .eq('primary_company_id', companyId)
  .gte('intel_date', _90dAgo)
  .order('intel_date', { ascending: false })
  .limit(15);
```

Render above the `news_articles` block. These are higher-signal items (Claude-extracted) and deserve priority placement.

### Fix 1C — Drug card modal: Add news_articles (30 min)

**Gap B1 + B2:** `_cemDrugBody` (standalone drug modal) has no news section. Drug news is only visible as a derived subset inside the company card expansion.

**Fix:** In `_cemDrugBody` fetch (C1 or C2 path), add:
```javascript
const { data: drugNews } = await _sb.from('news_articles')
  .select('id,headline,source_name,published_at,article_url,relevance_score,meridian_summary,why_it_matters')
  .contains('matched_drug_ids', [drugId])
  .neq('source_validation_status', 'invalid')
  .gte('published_at', _90dAgo)
  .order('relevance_score', { ascending: false })
  .limit(5);
```

Render as the last section in the drug modal, after trials and competitive scores.

**Do all three fixes in a single index.html edit.** Deploy once after all three are done.

---

## Priority 3: Catalyst Connectivity Audit → `catalyst_connectivity_audit.md`

```sql
SELECT COUNT(*) FROM catalysts;
SELECT COUNT(*) FROM catalysts WHERE drug_id IS NOT NULL;
SELECT COUNT(*) FROM catalysts WHERE canonical_drug_id IS NOT NULL;
SELECT COUNT(*) FROM catalysts WHERE drug_id IS NULL AND canonical_drug_id IS NULL;
SELECT COUNT(*) FROM catalysts WHERE resolved = false AND sort_date >= CURRENT_DATE;
SELECT area_id, COUNT(*) AS ct FROM catalysts GROUP BY area_id ORDER BY ct DESC;
```

Audit grep (index.html):
```bash
grep -n "catalysts\|catalyst" index.html | grep -v "<!--\|comment\|doc" | head -40
```

**Output:** `docs/catalyst_connectivity_audit.md`  
Include: count table, 4-surface visibility matrix (drug card / company card / area tab / homepage), gap list, recommended fixes.

---

## Priority 4: Surface B Removal (10 min — if time allows)

From `company_surface_inventory_session64.md`:

Remove dead DOM shell `#co-slideover` (lines 3757–3766 in index.html) and its CSS (lines 1291–1300).  
No functional impact — confirmed nothing writes to these elements.

---

## New Tracking Metric: UI Coverage %

Starting Session 66, track this per intelligence table:

```
UI Coverage % = rows visible in UI / rows stored in Supabase
```

| Table | Stored | Linked (entity FK) | Visible in UI | UI Coverage |
|---|---|---|---|---|
| `catalysts` | 790 | ~790 (created by pipeline) | ? (area tab only) | ? |
| `news_articles` | 55 | 55 (all scored) | 55 (homepage) | ~100% |
| `intel` | 767 | 767 (via intel_areas) | ? (area tab + global search) | ? |
| `deals` | 192 | ? (drug_id or company_id) | ? (area tab deals) | ? |
| `signals` | 51 | 51 (area-tagged) | ? | ? |
| `ownership_edges` | ? | ? | ? (company card only) | ? |

Fill during catalyst and frontend coverage audits. The target question:
**How much of our intelligence can users actually access?**

This is a better KPI than enrichment coverage because it measures utilization, not storage.

---

## What NOT to Do in Session 66

- Do not build new AI enrichment fields
- Do not start C11 parallel-write
- Do not add new Ailux signal generation
- Do not build the full Drug Card Sprint (deferred until routing is confirmed)
- Do not modify company_enrichment.py yet (pending enrichment_runs table from Session 64 design)

---

## Deliverables — Session 66

| File | Type | Priority |
|---|---|---|
| `index.html` | Fixes 1A + 1B + 1C (routing) | P1 |
| `docs/company_cleanup_plan.md` | Audit + safe fixes | P2 |
| `docs/catalyst_connectivity_audit.md` | Audit document | P2 |

---

## Session 67+ (Revised Roadmap)

1. **Session 67:** Frontend coverage matrix (complete `?` fill-in) + ownership audit → confirms what's truly missing before building
2. **Session 68:** Company card completion (parent_company_id display, full portfolio view) + Surface C redirect
3. **Session 69:** Drug Card Sprint 1 — build the definitive single-drug view with all confirmed facts
4. **Session 70:** C3 PI tab migration + C11 parallel-write (backend, high-risk)
5. **Session 71:** company_strategic_views + company_platform_views DDL (governance tables)

---

## Modified Files — Session 65 (for reference)

| File | Change |
|---|---|
| `scripts/fetch_homepage_news.py` | Step 1: bulk reset `is_this_week=false` for articles older than 7 days |
| `.github/workflows/fetch-homepage-news.yml` | NEW — daily 07:30 UTC, includes workflow_dispatch with dry_run/no_claude/since/limit inputs |
| `docs/live_system_health_audit.md` | NEW — pipeline health matrix, live counts, gap analysis |
| `docs/article_relationship_audit.md` | NEW — two-pipeline routing map, 5 gaps, fix recommendations |
| `docs/submit_intel_pipeline_audit.md` | NEW — full submit flow, status state machine, gap analysis |
| `NEXT_SESSION.md` | This file |

---

## Priority Allocation Reminder (from Kyle's Session 65 reframe)

- **40%** Connectivity — making stored facts reach the right surfaces  
- **30%** Live pipeline health — keeping the intelligence layer current  
- **20%** Canonical entity experience — company and drug cards as the primary product  
- **10%** New features  

Session 66 is weighted: ~50% connectivity (routing fixes), ~30% data quality (company normalization), ~20% audit (catalyst).
