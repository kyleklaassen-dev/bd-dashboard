# Next Session — Session 65: Meridian Fact Connectivity Audit

**Prepared:** 2026-05-26  
**Phase:** Phase 6 — Fact Connectivity & Canonical Display  
**Session 64 complete:** C1/C2 migration ✅ · write_meridian ailux_angle fix ✅ · company surface audit ✅ · enrichment observability design ✅

---

## The Reframe

Sessions 55–64 answered: *"Are the facts structured correctly?"*  
Session 65 answers: *"Can a user actually see every fact we have?"*

The intelligence layer is largely built. The ontology is in place. The enrichment pipeline is running. The question is no longer about generating more insight — it is about complete factual connectivity. Every canonical fact in Supabase should have a clear path:

**Ingestion → Storage → Relationship → UI Display**

If a fact is stored but not displayed, it does not exist for the user.

---

## Open at Session Start (5 min)

### C1/C2 dual-read validation (standing from Session 64)

Open the drug modal for these 5 drugs, check browser console for `[MERIDIAN_CMP]`:

```
batoclimab → expected: OK, old=1 new=1 matched=1 (fcrn)
upadacitinib → expected: OK, ibd_expansion=true (old=ibd, new=uc+cd)
efgartigimod → expected: OK, old=1 new=1 matched=1 (fcrn)
risankizumab → expected: OK, ibd_expansion=true
spy072 → expected: OK, old=1 new=1 matched=1 (ibd fallback)
```

If any drug shows `[MERIDIAN_CMP] Discrepancy` with `field_mismatches.length > 0` on a non-IBD field → investigate before audit work.

---

## Priority 1: Company Normalization Audit → `company_cleanup_plan.md`

**This is the first task. Start here.**

Query Supabase for every company name and surface violations:

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

**What to look for:**
- `abbvie` / `AbbVie` / `ABBVIE` → one canonical, others become aliases
- `Roche / Genentech` → should be `parent_company_id` relationship, not compound name
- `Johnson & Johnson` / `J&J` / `Johnson and Johnson` → one canonical
- `company/company` patterns → usually two companies that should be separate with a partnership record
- Acquired companies that appear as standalone entries instead of owned by acquirer

**Output:** `docs/company_cleanup_plan.md`  
Format: table of violating companies with recommended action (merge, alias, ownership_edge, rename, split).

**Then execute safe fixes in the same session:**
- Rename clearly misspelled or miscased company names (direct UPDATE)
- Set `parent_company_id` for known acquired companies with no parent set
- Do NOT merge row IDs without verifying no FK dependencies exist (check drugs, partnerships, catalysts, deals, company_areas for each id first)

---

## Priority 2: Drug Fact Connectivity Matrix → `frontend_coverage_matrix.md` (drugs section)

For every major field in `drugs`, determine: stored / queried / rendered / user-visible / missing.

**Fields to audit:**

| Field | DB column | Drug Card | Company Card | Homepage | Area Tab |
|---|---|---|---|---|---|
| mechanism | `drugs.mechanism` | ? | ? | ? | ? |
| stage | `drugs.stage` | ? | ? | ? | ? |
| ailux_angle | `drugs.ailux_angle` | ✅ | ? | ? | ? |
| overlap | `drugs.overlap` | ✅ | ? | ? | ✅ |
| overlap_rationale | `drugs.overlap_rationale` | ❌ not rendered | ? | ? | ? |
| target | `drugs.target` | ✅ | ? | ? | ? |
| indication_short | `drugs.indication_short` | ✅ | ? | ? | ? |
| catalyst (via FK) | `catalysts.drug_id` | ❌ not on card | ? | ? | ✅ area calendar |
| partnership | `partnerships.drug_id` | partial | ? | ? | ✅ licensor pill |
| ownership chain | `companies.parent_company_id` | ❌ | ? | ? | ? |
| drug_targets (ontology) | `drug_targets.target_id` | entity modal only | ? | ? | ✅ |
| drug_indications (ontology) | `drug_indications.indication_id` | entity modal only | ? | ? | ✅ |
| confidence_score | `drugs.confidence_score` | ❌ | ? | ? | ? |
| news coverage | `news_articles` (co match) | ❌ | partial | ✅ | ? |
| trials | `trials.drug_id` | ✅ | ? | ? | ? |
| deals | `deals.drug_id` | partial | ? | ? | ? |
| competitive scores | `drug_competitive_scores` | ✅ (post-Session 64) | ? | ? | ✅ |

Fill in every `?` by grepping index.html for each field name and confirming whether it is fetched and rendered.

**Output format:**
- ✅ = stored, queried, rendered, user-visible
- ⚠️ = stored, queried, but not rendered clearly
- ❌ = stored but not displayed at this surface
- — = not applicable

---

## Priority 3: Catalyst Connectivity Audit → `catalyst_connectivity_audit.md`

**Goal:** One catalyst, four surfaces. Every catalyst should be visible everywhere relevant.

**Expected surfaces:**
1. Drug card — next 1–3 catalysts for the specific drug
2. Company card — all upcoming catalysts for the company
3. Area tab — calendar of catalysts for that area
4. Homepage — global upcoming catalysts feed

**Current state queries:**

```sql
-- How many catalysts exist?
SELECT COUNT(*) FROM catalysts;

-- How many are linked to drugs via drug_id?
SELECT COUNT(*) FROM catalysts WHERE drug_id IS NOT NULL;

-- How many are linked via canonical_drug_id?
SELECT COUNT(*) FROM catalysts WHERE canonical_drug_id IS NOT NULL;

-- How many have no drug link at all?
SELECT COUNT(*) FROM catalysts WHERE drug_id IS NULL AND canonical_drug_id IS NULL;

-- How many are future (unresolved)?
SELECT COUNT(*) FROM catalysts WHERE resolved = false AND sort_date >= CURRENT_DATE;

-- Distribution by area_id
SELECT area_id, COUNT(*) AS ct FROM catalysts GROUP BY area_id ORDER BY ct DESC;
```

**Audit grep (index.html):**

```bash
grep -n "catalysts\|catalyst" index.html | grep -v "<!--\|comment\|doc" | head -40
```

Confirm: is `catalysts` fetched on drug card open? On company card open? On homepage load? On area tab load?

**Output:** `docs/catalyst_connectivity_audit.md`  
Include: count table, 4-surface visibility matrix, gap list, recommended fixes.

---

## Priority 4: News Connectivity Audit → `news_connectivity_audit.md`

**Goal:** Understand where articles actually surface and where they go dark.

**Supabase queries:**

```sql
-- How many articles exist total?
SELECT COUNT(*) FROM news_articles;

-- How many have a company_id match?
SELECT COUNT(*) FROM news_articles WHERE company_id IS NOT NULL;

-- How many have a drug mention?
SELECT COUNT(*) FROM news_articles WHERE drug_mentions IS NOT NULL AND drug_mentions != '[]';

-- How many are recent (last 7 days)?
SELECT COUNT(*) FROM news_articles WHERE published_at >= NOW() - INTERVAL '7 days';

-- Relevance score distribution
SELECT
  CASE
    WHEN relevance_score >= 0.8 THEN 'high'
    WHEN relevance_score >= 0.5 THEN 'medium'
    WHEN relevance_score >= 0.2 THEN 'low'
    ELSE 'minimal'
  END AS tier,
  COUNT(*) AS ct
FROM news_articles
GROUP BY 1 ORDER BY 2 DESC;
```

**Audit grep:**
Find every location in index.html that queries or renders `news_articles`. Confirm: homepage, company card, drug card, area tabs.

**Output:** `docs/news_connectivity_audit.md`  
Include: count summary, surface visibility matrix, gap list.

---

## Priority 5: Ownership Audit → `ownership_relationship_audit.md`

**Goal:** For every drug asset, can the dashboard show: originator, current owner, licensee, partner, co-dev partner, acquirer, parent company?

**Supabase queries:**

```sql
-- How many drugs have ownership data?
SELECT
  COUNT(*) AS total_drugs,
  COUNT(partner_company) AS has_partner,
  COUNT(licensor_name) AS has_licensor,
  COUNT(current_owner_company_id) AS has_current_owner,
  COUNT(originator_company_id) AS has_originator,
  COUNT(parent_company_id) AS parent_co_set  -- on companies table, not drugs
FROM drugs;

-- ownership_edges table — what's there?
SELECT edge_type, COUNT(*) AS ct FROM ownership_edges GROUP BY edge_type ORDER BY ct DESC;

-- Companies with parent_company_id set
SELECT COUNT(*) FROM companies WHERE parent_company_id IS NOT NULL;
```

**Audit grep:**
Where in index.html is `licensor_name`, `partner_company`, `current_owner_company_id`, `originator_company_id`, `parent_company_id`, `ownership_edges` rendered?

**Output:** `docs/ownership_relationship_audit.md`  
Include: field fill rates, surface visibility, ownership chain gaps.

---

## Priority 6: Frontend Coverage Matrix (all tables) → `frontend_coverage_matrix.md`

After the above individual audits, compile the master matrix covering every table:

| Table | Rows | Queried in UI? | Rendered on? | Major gaps |
|---|---|---|---|---|
| companies | ? | ✅ multiple surfaces | company card, drug row | parent_company_id not displayed |
| drugs | 154 | ✅ everywhere | drug card, area tabs | overlap_rationale, catalysts |
| partnerships | ? | partial | licensor pill | full deal terms not surfaced |
| catalysts | ? | partial | area calendar | not on drug card or homepage feed |
| trials | ? | ✅ | drug modal, area tabs | — |
| deals | ? | partial | drug modal | not on company card |
| news_articles | ? | partial | homepage, company card | not on drug card |
| ownership_edges | ? | partial | company card | not on drug card |
| drug_targets | 176 | ✅ | area tabs, entity modal | not on inline drug card |
| drug_indications | 246 | ✅ | area tabs, entity modal | not on inline drug card |
| company_areas | 136 | ✅ | company card | — |
| drug_competitive_scores | 234 | ✅ post-Session 64 | drug modal | not on inline card |

Fill every row with live counts and confirmed display status.

---

## Priority 7: Company Card Consolidation (from Session 64 audit)

**Already classified in `docs/company_surface_inventory_session64.md`.**

**Execute in Session 65 if time allows after audits:**

**Surface B removal (10 min):**
Remove dead DOM shell `#co-slideover` (lines 3757–3766) and its CSS (lines 1291–1300).
No functional impact — confirmed nothing writes to these elements.

**Surface C redirect (30 min):**
Replace `openCOPanel` body with a single delegation to `openCompanySlideOver`:
```javascript
window.openCOPanel = function(companyId, piRow) {
  // Delegating to canonical entity modal (Session 65)
  // URL hash routing preserved via entity-modal hashchange handler (TODO Session 66)
  var name = (piRow && piRow.querySelector && piRow.querySelector('.ac-co-name')?.textContent) || companyId;
  openCompanySlideOver(companyId, name, 'pharma-intel');
};
```
This makes the Pharma Landscape "⎘ Profile" button open the canonical card.
URL deep-link routing (`#/company/{id}`) is preserved as a Phase 2 addition.

---

## What NOT to Do in Session 65

- Do not add new AI enrichment fields
- Do not add new Ailux signal generation
- Do not start Drug Card Sprint 1 (this is deferred until fact connectivity is confirmed)
- Do not migrate C3 PI tab (still waiting on C11, which is now deferred)
- Do not build new frontend components until the connectivity matrix confirms what's actually missing

---

## Deliverables — Session 65

| File | Type | Priority |
|---|---|---|
| `docs/company_cleanup_plan.md` | Audit + data fixes | P1 |
| `docs/frontend_coverage_matrix.md` | Audit document | P1 |
| `docs/catalyst_connectivity_audit.md` | Audit document | P1 |
| `docs/news_connectivity_audit.md` | Audit document | P2 |
| `docs/ownership_relationship_audit.md` | Audit document | P2 |
| `index.html` | Surface B/C consolidation | P2 if time allows |

---

## Session 66+ (Revised Roadmap)

Once the connectivity audits are complete, the roadmap becomes concrete and evidence-based:

1. **Session 66:** Execute company normalization fixes (merges, aliases, parent_company_id corrections) + build drug card catalyst timeline (confirmed gap from catalyst audit)
2. **Session 67:** Build drug card ownership chain + fill company card gaps (confirmed from ownership audit)  
3. **Session 68:** Build homepage catalyst feed + area-level news feed (confirmed from news/catalyst audits)
4. **Session 69:** C3 PI tab migration + C11 parallel-write (backend, high-risk, defer until above UI value is shipped)
5. **Session 70:** company_strategic_views + company_platform_views DDL (governance tables)

The Drug Card Sprint and C11 parallel-write are not cancelled — they are sequenced after we know exactly which facts are missing from which surfaces.

---

## Modified Files — Session 64 (for reference)

| File | Change |
|---|---|
| `scripts/write_meridian.py` | `ailux_angle` + `overlap_rationale` added to drug context fetch; `BD Signal:` line in context block |
| `index.html` | C1/C2 migrated to `drug_competitive_scores`; `_confBadge` A/B/C fix; dual-read harness; label maps extended |
| `docs/company_surface_inventory_session64.md` | New — 3 company surfaces classified |
| `docs/enrichment_observability_plan_session64.md` | New — `enrichment_runs` table DDL + logging design |
| `NEXT_SESSION.md` | This file |
