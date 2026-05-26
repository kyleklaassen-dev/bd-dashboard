# Next Session — Session 66: Company Identity Audit + Routing Fixes

**Prepared:** 2026-05-26  
**Phase:** Phase 6 — Fact Connectivity & Canonical Display  
**Session 65 complete:** Live system health audit ✅ · P0 homepage news workflow created ✅ · is_this_week decay fix ✅ · Article routing audit ✅ · Submit intel pipeline audit ✅

---

## The Maturity Shift

Sessions 1–64 asked: *"Is the data correct?"*  
Session 65 asked: *"Is the pipeline healthy?"*  
Session 66 asks: *"Can a user actually use the data?"*

These are different maturity stages. The platform has shifted from a data modeling problem to a data utilization problem. The highest-value work is no longer enrichment — it is connectivity, entity integrity, and surface completeness.

The new primary KPI is **UI Coverage %**: for each intelligence table, what fraction of stored rows are actually reachable by a user? A row that exists in Supabase but cannot be reached from any UI surface does not exist for the user.

---

## Session 66 Reframe: Knowledge Graph Integration

Session 66 is not an engineering cleanup session. It is the first knowledge graph integration session:

1. Normalize entities (company identity audit)
2. Connect facts to entities (linkage audit)
3. Connect entities to UI surfaces (routing)
4. Define ownership of information (canonical surface matrix)
5. Measure visibility and freshness (connectivity scores)

Once complete, every future missing feature will show up as a measurable connectivity gap rather than a subjective observation.

---

## Session 66 Success Metric

By end of session, answer these five questions for each major Supabase table:

1. **Fresh?** — last row written, pipeline healthy?
2. **Linked?** — what fraction have a canonical entity FK (drug_id, company_id, area_id)?
3. **Visible?** — what fraction are reachable from at least one UI surface?
4. **Owned?** — which surface is the canonical home for this fact type?
5. **Next fix?** — single highest-leverage change to improve reach?

---

## Connectivity Score — Refined Definition

UI Coverage % (rows visible / rows stored) is a start. The more informative metric tracks the full reach chain:

```
790 catalysts stored
750 linked to a company or area (have company_id or area_id)
620 visible somewhere in the UI
420 reachable from a company card
180 reachable from a drug card
```

The drug card number is usually the most revealing. It measures whether the most specific user context — "I am looking at this asset" — can reach the fact. High company-card reach but low drug-card reach means the fact is discoverable only through the portfolio view, not through the asset itself.

---

## Canonical Surface Ownership Matrix (new deliverable)

Produce this as part of the Session 66 audit. Every fact type gets a canonical home. Everything else is a view.

| Fact Type | Canonical Owner | Secondary Surfaces |
|---|---|---|
| Drug news | Drug card | Company card, Area page |
| Company news | Company card | Homepage |
| Catalyst | Drug card (asset timeline) | Company card (portfolio), Area tab (competitive) |
| Trial | Drug card | Company card |
| Partnership | Company card | Drug card |
| Ownership chain | Company card | Drug card |
| Deal | Company card | Drug card, Homepage |
| Article | Drug or Company card (by linkage) | Industry Insights |
| Intel item | Area tab | Company card (pending routing fix) |
| Signal | Area tab | Homepage |

This document forces clarity before building. Same catalyst, three surfaces — but only one perspective per surface, rendered consistently from the same query.

---

## Priority 0: Review Submitted Intel (5 min — START HERE)

9 items submitted 2026-05-26 with `status='new'`. By session start they should be `status='analyzed'`.

Open the Submitted Intel tab. For each analyzed item:
- ✅ Send to Queue (high confidence, no dup concern)
- ❌ Reject (irrelevant or duplicate)
- 💬 Needs Review (ambiguous)

**Do this before any code work.** Submitted intel is the highest-signal input in the system.

---

## Priority 0: Review Submitted Intel (5 min — START HERE)

9 items submitted 2026-05-26 with `status='new'`. By session start they should be `status='analyzed'` (review_submitted_intel.py runs every 6h).

Open the Submitted Intel tab. For each analyzed item:
- ✅ Send to Queue (high confidence, no dup concern)
- ❌ Reject (irrelevant or duplicate)
- 💬 Needs Review (ambiguous, come back later)

**Do this before any code work.** Submitted intel is the highest-signal input in the system.

---

## Priority 1: Company Identity Audit → `company_cleanup_plan.md`

**Do this before routing fixes.** Routing quality depends on entity quality. `news_articles.matched_company_ids` is populated at write time by fuzzy-matching company names against `companies.name`. If "AbbVie", "abbvie", and "ABBVIE" are three different `company_id` values, news articles matched to one variant will not surface on the other company cards. Fix company identity first.

This is not a simple duplicate name check. Build a complete company identity audit.

### Part A — Identity Violations

```sql
-- Duplicate names (case variants)
SELECT LOWER(name) AS name_lower, array_agg(id ORDER BY id) AS ids, COUNT(*) AS ct
FROM companies GROUP BY LOWER(name) HAVING COUNT(*) > 1 ORDER BY ct DESC;

-- Slash-compound names (should be parent_company_id relationship)
SELECT id, name FROM companies WHERE name LIKE '%/%' ORDER BY name;

-- Lowercase names (should be title case)
SELECT id, name FROM companies WHERE name != INITCAP(name) AND name = LOWER(name) ORDER BY name;

-- Acquired companies without parent_company_id set
SELECT id, name, status FROM companies WHERE status = 'acquired' AND parent_company_id IS NULL ORDER BY name;

-- Current parent_company_id relationships
SELECT c.id, c.name, p.id AS parent_id, p.name AS parent_name
FROM companies c JOIN companies p ON c.parent_company_id = p.id ORDER BY p.name, c.name;
```

### Part B — Company Connectivity Score

For every company in the watchlist, compute a connectivity score across all linked intelligence tables. This tells you where entity integrity is weak — not by looking at the company record, but by looking at how much downstream data reaches it.

```sql
-- Connectivity score per company
SELECT
  c.id,
  c.name,
  COUNT(DISTINCT d.id)    AS drugs_linked,
  COUNT(DISTINCT ca.id)   AS catalysts_linked,
  COUNT(DISTINCT de.id)   AS deals_linked,
  COUNT(DISTINCT oe.id)   AS ownership_edges,
  (c.parent_company_id IS NOT NULL)::int AS has_parent,
  CASE WHEN c.status = 'acquired' AND c.parent_company_id IS NULL THEN 1 ELSE 0 END AS orphaned_acquisition
FROM companies c
LEFT JOIN drugs d       ON d.company_id = c.id
LEFT JOIN catalysts ca  ON ca.company_id = c.id
LEFT JOIN deals de      ON de.company_id = c.id
LEFT JOIN ownership_edges oe ON oe.from_company_id = c.id OR oe.to_company_id = c.id
WHERE c.status != 'acquired'
GROUP BY c.id, c.name, c.parent_company_id, c.status
ORDER BY drugs_linked DESC;
```

For `news_articles` (array field, requires different approach):
```sql
-- Companies that appear in news_articles.matched_company_ids
SELECT DISTINCT unnest(matched_company_ids) AS company_id, COUNT(*) AS article_count
FROM news_articles
GROUP BY 1 ORDER BY 2 DESC LIMIT 30;
```

### Part C — Output Format

`docs/company_cleanup_plan.md` should include two tables:

**Table 1 — Identity violations** (action required per company):

| Company | Current ID | Violation Type | Recommended Action |
|---|---|---|---|
| abbvie | abbvie-2 | Case duplicate of abbvie | Merge → abbvie, add alias |
| Roche / Genentech | roche-gen | Slash compound | Split: parent_company_id relationship |

**Table 2 — Connectivity scorecard** (top 30 companies by drug count):

| Company | Drugs | Catalysts | News | Deals | Ownership | Score |
|---|---|---|---|---|---|---|
| AbbVie | 8 | 12 | 14 | 5 | ✅ | 100 |
| Company X | 3 | 0 | 1 | 2 | ❌ | 43 |

Score formula: presence in each category = 20 pts, max 100.

### Part D — Three Classes of Fix (execute by class, not all at once)

**Class 1 — Easy (execute immediately in session):**
- Capitalization: `abbvie` → `AbbVie`
- Spacing / punctuation: `Johnson&Johnson` → `Johnson & Johnson`
- Company/Company formatting: flag for relationship fix

**Class 2 — Alias (add to `company_aliases`, do not merge rows):**
- `AbbVie` / `Abbvie` / `ABBVIE` → one canonical id, others become aliases
- `J&J` / `Johnson and Johnson` → aliases pointing to `Johnson & Johnson`
- `Roche` / `Genentech` → aliases if same entity, or parent_company_id if separate

**Class 3 — Relationship (ownership edges, not merges):**
- Subsidiaries → `parent_company_id` FK
- Acquisitions → `companies.status='acquired'` + `parent_company_id`
- Slash compounds → separate company records + explicit `ownership_edges` row
- Do NOT merge row IDs. Set relationships. Check FK dependencies (drugs, partnerships, catalysts, deals, company_areas) before any structural change.

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

## Priority 3: Industry Insights Audit → `industry_insights_audit.md`

Industry Insights is the daily briefing iframe (`meridian_today.html`). It is nominally healthy (write_meridian.py runs Mon–Sat at 10:30 UTC). But "healthy pipeline" ≠ "complete coverage." The audit question is: how many recent intelligence items exist in Supabase that do NOT appear in the daily briefing?

**Audit queries:**

```sql
-- How many intel rows from last 7 days?
SELECT COUNT(*) FROM intel WHERE intel_date >= CURRENT_DATE - 7;

-- How many catalysts unresolved and upcoming?
SELECT COUNT(*) FROM catalysts WHERE resolved = false AND sort_date >= CURRENT_DATE;

-- How many deals from last 14 days?
SELECT COUNT(*) FROM deals WHERE deal_date >= CURRENT_DATE - 14;
```

**Audit grep (write_meridian.py):**
```bash
grep -n "intel\|catalyst\|deals\|news_articles" scripts/write_meridian.py | head -40
```

Confirm: which tables does write_meridian.py query? What filters does it apply? Are there relevance thresholds that exclude recent items?

**Output:** `docs/industry_insights_audit.md`  
Include: tables queried, filters applied, row counts available vs. included, coverage gap.

---

## Priority 4: Catalyst Connectivity Audit → `catalyst_connectivity_audit.md`

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

## Drug Card — Target Information Architecture (for Session 67+)

The canonical drug card (`_cemDrugBody`) must be **primarily factual**. AI-generated signals (ailux_angle, overlap_rationale, BD framing) go in a collapsible secondary section. The card should be trustworthy and readable without AI annotation — facts first, interpretation available but not leading.

**Priority order for the factual sections:**

```
Asset Overview
  current owner / company · originator / licensor · stage
  indications · targets · mechanism

Development
  trials (phase, endpoint, readout date)
  catalysts (next 3 upcoming · past 2 resolved)

Business
  partnerships (type · partner · economics summary)
  deal history (type · counterparty · value · date)
  ownership chain (originator → current owner → licensees)

Activity
  recent news (news_articles.matched_drug_ids)
  submitted intel lineage (future: source_submitted_intel_id FK)

[Collapsible] BD Intelligence
  ailux_angle · overlap / overlap_rationale
  vs_ailux framing · confidence + source URL
```

All data exists in Supabase. Build in Session 67 after connectivity audit confirms linkage rates. Start with news (simplest) and catalysts (highest BD value).

---

## Submit Intel Traceability Gap (Session 68+)

From `submit_intel_pipeline_audit.md`: once a submission is promoted to `discovery_queue` and processed into `catalysts`/`deals`/`intel`, there is no FK back to the originating `submitted_intel` row. A submitted article that generates a catalyst has no traceable lineage.

Future fix: add `source_submitted_intel_id` FK to `catalysts`, `deals`, and `intel`. This makes every submission traceable to its downstream outputs. Defer until submit intel volume increases enough to justify.

---

## Priority 5: Surface B Removal (10 min — if time allows)

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

## Acceptance Tests — Session 66 Validation

Before closing the session, verify these three traversals work end-to-end. If any fails, identify which layer of the depth chain is broken.

**Test 1 — Company traversal:**  
Open Ventyx Biosciences company card. Confirm visible without navigation:
- [ ] ownership (ABBVie acquired 2022 — parent_company_id set)
- [ ] drugs (VTX002 / izokibep / other pipeline)
- [ ] catalysts (upcoming readouts)
- [ ] news (recent articles mentioning Ventyx or VTX002)
- [ ] deals / partnerships

**Test 2 — Drug traversal:**  
Open tulisokibart drug card. Confirm visible without navigation:
- [ ] stage + mechanism + indications + targets
- [ ] trials (active studies)
- [ ] catalysts (upcoming readouts)
- [ ] ownership (Protagonist → Novartis chain)
- [ ] partnerships
- [ ] recent news

**Test 3 — News routing:**  
Confirm a recent AbbVie article surfaces in all expected locations:
- [ ] AbbVie company card "Recent Coverage"
- [ ] Drug cards for matched_drug_ids
- [ ] Homepage "Important Articles"

Any failure maps directly to a depth chain break (Linked / Queryable / Rendered / Reachable) and becomes the next session's P1.

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
