# Next Session — Session 66: Knowledge Graph Integration

**Prepared:** 2026-05-26  
**Phase:** Phase 6 — Fact Connectivity & Canonical Display  
**Session 65 complete:** Live system health audit ✅ · P0 homepage news workflow created ✅ · is_this_week decay fix ✅ · Article routing audit ✅ · Submit intel pipeline audit ✅

---

## The Maturity Shift

Session 66 is the first knowledge graph integration session — not an engineering cleanup. The platform already contains a substantial amount of intelligence. The bottleneck is no longer knowledge acquisition. It is knowledge visibility.

The question is no longer whether the data exists. The question is whether a user can discover it from the entity they are currently viewing.

**Priority order:** Freshness → Connectivity → Canonicality. Those three things create most of the value. New enrichment, new AI signals, and new ontology work are all second-order until these three are complete.

---

## Connectivity Depth Chain (standing metric — run at session start)

For every major table, report five levels before diagnosing any gap:

```
Stored      → total rows
Linked      → rows with canonical entity FK (drug_id, company_id, area_id)
Queryable   → rows a UI query would return under current filters
Rendered    → rows actually rendered in at least one UI component
Reachable   → rows reachable from the most specific context (drug card)
```

Each break point has a different fix: Stored→Linked = entity integrity; Linked→Queryable = filter logic; Queryable→Rendered = missing component; Rendered→Reachable = wrong surface, not wired to asset view.

---

## Session 66 Success Metric

By end of session, answer five questions for each major table: Fresh? Linked? Visible? Owned? Next fix?

And pass two acceptance tests:

**Company test:** Open AbbVie. See all relevant assets, news, catalysts, ownership relationships, and partnerships from one place.

**Drug test:** Open tulisokibart. See all relevant news, catalysts, trials, ownership, and partnerships from one place.

If those tests pass, Meridian will feel significantly more useful than it does today without adding a single new intelligence row to the database.

---

## Priority 0: Review Submitted Intel (5 min — START HERE, manual)

9 items submitted 2026-05-26. By session start they should be `status='analyzed'`.

Open the Submitted Intel tab. For each:
- ✅ Send to Queue (high confidence, clear entities)
- ❌ Reject (irrelevant or duplicate)
- 💬 Needs Review (ambiguous)

Note which entities were matched and where accepted items land. This immediately validates one pipeline path.

---

## Priority 1: Submit Intel Traceability (P0 — build in Session 66)

**Goal:** The Submit Intel screen must show what happened to each submission — what was extracted, what entities matched, what was written to Supabase, and where it appears in the dashboard. This is a factual audit trail, not AI reasoning.

See full spec: `docs/submit_intel_traceability_spec.md`

### Schema additions required

**On `submitted_intel` table** (new columns):
```sql
writes_json          JSONB,   -- {table: [ids written], ...}
placement_json       JSONB,   -- {surface: [entity ids visible at], ...}
matched_entities_json JSONB,  -- {companies:[], drugs:[], targets:[], indications:[]}
processed_at         TIMESTAMPTZ,
published_at         TIMESTAMPTZ,
rejection_reason     TEXT
```

**On downstream tables** (new FK column):
```sql
-- Add to: catalysts, deals, intel
source_submitted_intel_id  UUID REFERENCES submitted_intel(id)
```

### Status lifecycle

```
new → [review_submitted_intel.py] → analyzed / needs_review
    → [Kyle action] → imported (→ discovery_queue) / rejected
                    → [company_enrichment.py] → published
```

Display all 6 states in the Review tab with timestamps.

### UI additions (Submitted Intel Review tab)

For each submission, expand to show:
1. **Status timeline** — received → processed → reviewed → published/rejected + timestamps
2. **Entities discovered** — companies, drugs, targets, indications, catalysts, deals matched
3. **Supabase writes** — exact table + row IDs created or updated
4. **Dashboard placement** — which surfaces now show this intelligence (with navigation buttons)
5. **Rejection reason** — if rejected, why

### Acceptance test

Submit a Fierce/Endpoints article link. After processing, the Submitted Intel screen must show: matched company, matched drug (if any), accepted/rejected status, written table(s), dashboard placement, and direct navigation to the relevant company card, drug card, or review record.

---

## Priority 2: Company Identity Audit → `docs/company_cleanup_plan.md`

Do before routing fixes. Routing quality depends on entity quality — `news_articles.matched_company_ids` is populated by fuzzy-matching against `companies.name`. Fragmented company IDs degrade every downstream surface.

### Part A — Identity violation queries

```sql
-- Case duplicates
SELECT LOWER(name) AS name_lower, array_agg(id ORDER BY id) AS ids, COUNT(*) AS ct
FROM companies GROUP BY LOWER(name) HAVING COUNT(*) > 1 ORDER BY ct DESC;

-- Slash-compound names (should be ownership relationships)
SELECT id, name FROM companies WHERE name LIKE '%/%' ORDER BY name;

-- Lowercase names
SELECT id, name FROM companies WHERE name != INITCAP(name) AND name = LOWER(name) ORDER BY name;

-- Acquired companies without parent_company_id
SELECT id, name, status FROM companies WHERE status = 'acquired' AND parent_company_id IS NULL ORDER BY name;

-- Current ownership relationships
SELECT c.id, c.name, p.id AS parent_id, p.name AS parent_name
FROM companies c JOIN companies p ON c.parent_company_id = p.id ORDER BY p.name, c.name;
```

### Part B — Connectivity score matrix

```sql
SELECT c.id, c.name,
  COUNT(DISTINCT d.id)   AS drugs_linked,
  COUNT(DISTINCT ca.id)  AS catalysts_linked,
  COUNT(DISTINCT de.id)  AS deals_linked,
  COUNT(DISTINCT oe.id)  AS ownership_edges,
  (c.parent_company_id IS NOT NULL)::int AS has_parent
FROM companies c
LEFT JOIN drugs d       ON d.company_id = c.id
LEFT JOIN catalysts ca  ON ca.company_id = c.id
LEFT JOIN deals de      ON de.company_id = c.id
LEFT JOIN ownership_edges oe ON oe.from_company_id = c.id OR oe.to_company_id = c.id
WHERE c.status != 'acquired'
GROUP BY c.id, c.name, c.parent_company_id, c.status ORDER BY drugs_linked DESC;
```

For news_articles linkage:
```sql
SELECT DISTINCT unnest(matched_company_ids) AS company_id, COUNT(*) AS article_count
FROM news_articles GROUP BY 1 ORDER BY 2 DESC LIMIT 30;
```

### Part C — Three classes of fix (execute by class)

**Class 1 — Formatting (execute immediately):**
Capitalization, spacing, punctuation — safe direct UPDATEs. Examples: `abbvie` → `AbbVie`.

**Class 2 — Aliases (add to `company_aliases`, do not merge rows):**
`J&J` → alias pointing to `Johnson & Johnson`. `AbbVie` / `Abbvie` → one canonical id.

**Class 3 — Corporate structure (hold for review before execution):**
Roche ↔ Genentech, Prometheus ↔ Merck, Seagen ↔ Pfizer, Ventyx ↔ AbbVie. These are business questions, not naming questions. Always create the ownership relationship — NEVER merge or delete the subsidiary entity. Preserving both records retains the drug's origin story, clinical attribution, and acquisition chain.

### Part D — Output

`docs/company_cleanup_plan.md`:
- Table 1: identity violations + recommended action
- Table 2: connectivity scorecard (top 30 by drug count)

---

## Priority 3: Drug Card News + Catalyst Integration (index.html)

Drug card is becoming the canonical asset page. Start here before area-tab news because the drug card currently has zero activity sections — highest impact per line of code.

### Fix 3A — News section (30 min)

In `_cemDrugBody` C1/C2 fetch path, add:
```javascript
const { data: drugNews } = await _sb.from('news_articles')
  .select('id,headline,source_name,published_at,article_url,relevance_score,meridian_summary,why_it_matters')
  .contains('matched_drug_ids', [drugId])
  .neq('source_validation_status', 'invalid')
  .gte('published_at', _90dAgo)
  .order('relevance_score', { ascending: false })
  .limit(5);
```

Render after the trials section. Style consistent with company card "Recent Coverage".

### Fix 3B — Catalyst section (30 min)

```javascript
const { data: drugCatalysts } = await _sb.from('catalysts')
  .select('id,catalyst_text,sort_date,catalyst_type,resolved,source_url')
  .eq('drug_id', drugId)
  .eq('resolved', false)
  .gte('sort_date', new Date().toISOString().slice(0,10))
  .order('sort_date', { ascending: true })
  .limit(5);
```

Render as a timeline above the news section (Timeline comes before Activity in the five-layer IA).

---

## Priority 4: Company Card Intel Integration (index.html)

**Gap A1 from article_relationship_audit.md:** `intel.primary_company_id` exists but is never used. Opening AbbVie should expose AbbVie intel items, not just news articles.

In `openCompanySlideOver` fetch block, add alongside the existing `news_articles` fetch:
```javascript
const { data: companyIntel } = await _sb.from('intel')
  .select('id,intel_date,headline,intel_type,source_url,importance')
  .eq('primary_company_id', companyId)
  .gte('intel_date', _90dAgo)
  .order('intel_date', { ascending: false })
  .limit(15);
```

Render above the news_articles block in the Recent Coverage section. Intel items are Claude-extracted — higher signal than RSS articles and deserve priority placement.

---

## Priority 5: Area Tab Article Routing (index.html)

Third routing fix. Area tabs already have an intel feed so this is lower urgency, but it closes the gap for area-level news visibility.

Add to each area tab data load:
```javascript
const { data: areaNews } = await _sb.from('news_articles')
  .select('id,headline,source_name,published_at,article_url,relevance_score,meridian_summary,why_it_matters,matched_drug_ids,matched_company_ids')
  .contains('matched_area_ids', [areaId])
  .eq('is_this_week', true)
  .neq('source_validation_status', 'invalid')
  .order('relevance_score', { ascending: false })
  .limit(10);
```

Render as "Recent Coverage" below the intel feed.

---

## Priority 6: Industry Insights Coverage Audit → `docs/industry_insights_audit.md`

Pipeline is healthy (write_meridian.py Mon–Sat 10:30 UTC). The question is coverage — how many recent intelligence items exist in Supabase that do NOT appear in the daily briefing?

```bash
grep -n "intel\|catalyst\|deals\|news_articles" scripts/write_meridian.py | head -40
```

Confirm: which tables are queried? What filters exclude items? Are relevance thresholds cutting recent content?

Output: `docs/industry_insights_audit.md` — tables queried, filters applied, available vs. included row counts, coverage gap.

---

## Priority 7: Catalyst Connectivity Audit → `docs/catalyst_connectivity_audit.md`

Run depth chain for catalysts:

```sql
SELECT COUNT(*) FROM catalysts;                                                    -- stored
SELECT COUNT(*) FROM catalysts WHERE drug_id IS NOT NULL OR company_id IS NOT NULL; -- linked
SELECT COUNT(*) FROM catalysts WHERE resolved = false AND sort_date >= CURRENT_DATE; -- queryable/future
SELECT area_id, COUNT(*) AS ct FROM catalysts GROUP BY area_id ORDER BY ct DESC;   -- distribution
```

Four-surface visibility matrix: drug card / company card / area tab / homepage.

---

## UI Coverage Matrix (build continuously, not end-of-session)

Populate this throughout the session as each audit runs:

| Table | Stored | Linked | Queryable | Rendered | Reachable (drug card) | Break point |
|---|---|---|---|---|---|---|
| catalysts | 790 | ? | ? | ? | ? | ? |
| news_articles | 55 | 55 | 55 | 55 | 0 | Rendered→Reachable |
| intel | 767 | 767 | ? | ? | 0 | Rendered→Reachable |
| deals | 192 | ? | ? | ? | ? | ? |
| signals | 51 | 51 | ? | ? | 0 | ? |
| submitted_intel | 9 | ? | — | ? | 0 | Rendered→Reachable |

---

## Canonical Surface Ownership Matrix

Every fact type has one canonical owner. Secondary surfaces show filtered views. This prevents future duplication as the platform grows.

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
| Intel item | Area tab | Company card (P4 routing fix) |
| Signal | Area tab | Homepage |

---

## Acceptance Tests

**Test 1 — Company traversal (Ventyx / VTX002):**

VTX002 is a S1P1 receptor modulator from Ventyx. Ventyx was acquired by AbbVie in 2022. Both entities must be preserved — do not collapse them.

Open Ventyx company card:
- [ ] `parent_company_id = abbvie` set
- [ ] VTX002 and Ventyx pipeline drugs visible
- [ ] Catalysts for Ventyx pipeline visible
- [ ] Recent news mentioning Ventyx or VTX002

Open AbbVie company card:
- [ ] Ventyx appears as subsidiary / acquired entity
- [ ] VTX002 visible through portfolio/ownership relationship
- [ ] Ownership chain: VTX002 → Ventyx → AbbVie renders correctly

**Test 2 — Drug traversal (tulisokibart):**

Open tulisokibart drug card:
- [ ] stage + mechanism + indications + targets
- [ ] trials (active studies)
- [ ] catalysts (upcoming readouts)
- [ ] ownership chain (Protagonist → Novartis if confirmed in DB)
- [ ] partnerships
- [ ] recent news

**Test 3 — News routing (AbbVie article):**

Confirm a recent AbbVie article surfaces in:
- [ ] AbbVie company card "Recent Coverage"
- [ ] Drug cards for matched_drug_ids
- [ ] Homepage "Important Articles"

---

## Drug Card — Target IA (reference, for implementation)

Five-layer order — facts before interpretation:

```
1. Identity:    current owner · originator · parent chain
2. Status:      stage · indications · targets · mechanism
3. Timeline:    catalysts (next 3) · trials · milestones
4. Activity:    news · deals · partnerships · submitted intel lineage
5. [Collapsible] Interpretation: ailux_angle · overlap · BD framing
```

AI-generated signals always collapsible, never leading.

---

## What NOT to Do in Session 66

- No new enrichment fields
- No new AI signal generation
- No new Ailux angle generation
- No C11 parallel-write
- No therapeutic area navigation redesign
- No new ontology work
- Do not merge company row IDs without FK dependency check
- Do not collapse Roche/Genentech, Prometheus/Merck, or Ventyx/AbbVie into single entities

---

## Deliverables — Session 66

| File | Type | Priority |
|---|---|---|
| `docs/submit_intel_traceability_spec.md` | Design spec | P0 |
| `index.html` | DDL + schema additions (submitted_intel columns) | P0 |
| `index.html` | Drug card news + catalyst sections (Fixes 3A + 3B) | P1 |
| `index.html` | Company card intel section (Fix 4) | P2 |
| `docs/company_cleanup_plan.md` | Identity audit + connectivity scorecard + Class 1 fixes | P2 |
| `index.html` | Area tab article routing (Fix 5) | P3 |
| `docs/industry_insights_audit.md` | Coverage audit | P3 |
| `docs/catalyst_connectivity_audit.md` | Depth chain + surface matrix | P3 |
| `docs/ui_coverage_matrix.md` | Running depth chain per table | P3 |

---

## Session 67+ Roadmap

1. **Session 67:** Submit Intel Traceability UI build + backend wiring (if not complete in 66)
2. **Session 68:** Drug card full five-layer redesign (ownership chain, deal history)
3. **Session 69:** Company card full five-layer redesign + Surface C redirect
4. **Session 70:** C3 PI tab migration + C11 parallel-write

---

## Modified Files — Session 65

| File | Change |
|---|---|
| `scripts/fetch_homepage_news.py` | Step 1: bulk reset is_this_week=false for articles older than 7 days |
| `.github/workflows/fetch-homepage-news.yml` | NEW — daily 07:30 UTC |
| `docs/live_system_health_audit.md` | NEW |
| `docs/article_relationship_audit.md` | NEW |
| `docs/submit_intel_pipeline_audit.md` | NEW |
| `NEXT_SESSION.md` | This file |
