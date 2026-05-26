# Next Session — Session 67: Knowledge Graph Completion

**Prepared:** 2026-05-26  
**Phase:** Phase 6 — Fact Connectivity & Canonical Display  
**Session 66 complete:** Company identity audit ✅ · Drug card news+catalysts (3A/3B) ✅ · Company card intel coverage (Fix 4) ✅ · Area tab news routing (Fix 5) ✅ · Ventyx + VTX002 added ✅

---

## Session 66 — What Was Built

Four routing gaps closed in one session:

| Fix | What | Break point closed |
|---|---|---|
| 3A | Drug card: news_articles section | Rendered → Reachable (drug) |
| 3B | Drug card: catalyst timeline section | Rendered → Reachable (drug) |
| Fix 4 | Company card: intel + news coverage | Rendered → Reachable (company) |
| Fix 5 | Industry Insights: news_articles added | Coverage gap in intel feed |

**Ventyx Biosciences** added as `status='acquired', parent_company_id='abbvie'`. **VTX002** (S1P1 modulator, Phase 2) added as first Ventyx drug.

---

## Connectivity Depth Chain — Session 66 Status

| Table | Stored | Linked | Queryable | Rendered | Reachable (drug card) | Break point |
|---|---|---|---|---|---|---|
| catalysts | 790 | 790 | 781 | ✅ area tab | ✅ drug card (Fix 3B) | **CLOSED** |
| news_articles | 55 | 55 | 55 | ✅ homepage | ✅ drug card (Fix 3A) | **CLOSED** |
| intel | 767 | 767 | 767 | ✅ area tab | ✅ company card (Fix 4) | **CLOSED** |
| deals | 192 | ? | ? | ✅ company card | — | company card OK |
| signals | 51 | 51 | ? | ✅ area tab | — | not yet drug-card |
| submitted_intel | 9+ | — | — | ✅ review tab | — | traceability gap |

---

## Acceptance Tests — Session 66 Status

### Test 1 — Drug traversal (tulisokibart) — check at session start

Open tulisokibart drug card:
- [x] stage + mechanism + indications + targets (existing)
- [x] trials (existing)
- [x] catalysts (upcoming readouts) ← **NEW Fix 3B**
- [x] recent news ← **NEW Fix 3A**
- [ ] ownership chain (Protagonist → Novartis) — not yet built
- [ ] partnerships — partial

### Test 2 — Company traversal (AbbVie)

Open AbbVie company card:
- [x] pipeline drugs (9 drugs including VTX002 path)
- [x] catalysts (30 linked)
- [x] deals/partnerships
- [x] Recent coverage section ← **NEW Fix 4** (will show if news_articles.matched_company_ids includes 'abbvie')
- [ ] Ventyx appears as subsidiary — not yet wired in company card display

### Test 3 — Ventyx traversal

Open Ventyx company card:
- [ ] VTX002 visible in pipeline
- [ ] parent_company_id = abbvie set ✅ (data is correct)
- [ ] AbbVie appears as parent in UI — not yet displayed

---

## Priority 0: Validate Session 66 Routing Fixes (15 min — START HERE)

Open the live dashboard. For each:

**Drug card test:** Open tulisokibart. Verify "Upcoming catalysts" banner and "Recent coverage" sections appear. If catalysts section is empty, check `catalysts.drug_id = 'tulisokibart'` in Supabase. If news is empty, check `news_articles.matched_drug_ids` contains tulisokibart.

**Company card test:** Open AbbVie. Verify "Recent coverage" section appears in the overview grid. Check the section shows intel + news items or an informative "no matches" state.

**Industry Insights test:** Open Industry Insights tab. Verify news articles now appear in the feed alongside intel items.

---

## Priority 1: Submit Intel Traceability (P0 — from Session 66 plan, not yet built)

**Goal:** The Submit Intel screen must show what happened to each submission — what was extracted, what entities matched, what was written to Supabase, and where it appears in the dashboard.

See full spec: `docs/submit_intel_traceability_spec.md` (to be created this session)

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

**On downstream tables** (new FK):
```sql
-- Add to: catalysts, deals, intel
source_submitted_intel_id  UUID REFERENCES submitted_intel(id)
```

### UI additions (Submitted Intel Review tab)

For each submission, expand to show:
1. Status timeline — received → processed → reviewed → published/rejected + timestamps
2. Entities discovered — companies, drugs, targets, indications matched
3. Supabase writes — exact table + row IDs created or updated
4. Dashboard placement — which surfaces now show this intelligence
5. Rejection reason — if rejected, why

### Acceptance test

Submit a Fierce/Endpoints article link. After processing, the Submitted Intel screen must show: matched company, matched drug (if any), accepted/rejected status, written table(s), dashboard placement, and direct navigation to the relevant company card, drug card, or review record.

---

## Priority 2: Ventyx / AbbVie Ownership Display

The data is correct: Ventyx has `parent_company_id='abbvie'`. The UI doesn't yet surface this relationship.

**Fix A — Company card subsidiary display:**
In `openCompanySlideOver`, after the company row fetch, fetch subsidiaries:
```javascript
const { data: subsidiaries } = await _sb.from('companies')
  .select('id,name,status')
  .eq('parent_company_id', companyId)
  .eq('status', 'acquired');
```
Render as an "Acquired subsidiaries" row in the identity section of `_cemCompanyBody`. Show subsidiary name + link to open their card.

**Fix B — Drug card ownership chain:**
Add to drug modal fetch:
```javascript
const { data: originatorCo } = await _sb.from('companies')
  .select('id,name,parent_company_id')
  .eq('id', drug.originator_company_id || drug.company_id)
  .limit(1);
```
If `parent_company_id` is set, show "via [Originator] (a [Parent] company)" in the identity section.

---

## Priority 3: Drug Card Ownership Chain + Partnership Display

The drug card currently shows no ownership chain. VTX002 → Ventyx → AbbVie should be visible from the drug card.

**Current state:**
- `drugs.current_owner_company_id` = 'abbvie' (set for VTX002)
- `drugs.originator_company_id` = 'ventyx' (set for VTX002)
- `drugs.ownership_status` = 'acquired'

**Display spec (Identity layer, layer 1 in five-layer IA):**
```
Current owner: AbbVie [→ open company card]
Originator:    Ventyx Biosciences [→ open company card] (acquired 2022)
Mechanism:     S1P1 receptor modulator
```

---

## Priority 4: Catalyst Connectivity — drug_id backfill audit

143 of 790 catalysts have `drug_id` set. The remaining 647 are linked only via `company_id` + `area_id`. These are catalysts that cannot reach the drug card.

Run:
```sql
SELECT c.company_id, c.area_id, COUNT(*) AS ct
FROM catalysts c 
WHERE c.drug_id IS NULL AND c.resolved = false
GROUP BY 1, 2 ORDER BY ct DESC LIMIT 20;
```

For the top companies/areas, check if the catalyst text contains drug names that could be back-linked. Write a Python script to:
1. For each catalyst WHERE drug_id IS NULL, search catalyst_text for drug names in the database
2. If confident match found (drug company_id matches catalyst company_id), set drug_id

Output: `docs/catalyst_drug_backfill_audit.md` with match counts and confidence distribution.

---

## Priority 5: Company Cleanup — Class 1 Formatting Fixes

From `docs/company_cleanup_plan.md`:
- Only one identity issue: `argenx` (intentional branding, no change needed)
- Investigate Teva's 10 orphaned catalysts (company_id='teva' but no drugs linked)
- Decide Chugai/Roche ownership (Roche ~63% owner — set parent_company_id?)

---

## Canonical Surface Ownership Matrix (standing reference)

| Fact Type | Canonical Owner | Secondary Surfaces |
|---|---|---|
| Drug news | Drug card ✅ Fixed 3A | Company card, Area page |
| Company news | Company card ✅ Fixed 4 | Homepage |
| Catalyst | Drug card (asset timeline) ✅ Fixed 3B | Company card (portfolio), Area tab |
| Trial | Drug card | Company card |
| Partnership | Company card | Drug card |
| Ownership chain | Company card | Drug card |
| Deal | Company card | Drug card, Homepage |
| Article | Drug or Company card (by linkage) | Industry Insights ✅ Fixed 5 |
| Intel item | Area tab | Company card ✅ Fixed 4 |

---

## Session 68+ Roadmap

1. **Session 68:** Drug card full five-layer redesign (ownership chain, deal history, partnership display)
2. **Session 69:** Company card full five-layer redesign + subsidiary display
3. **Session 70:** Submit intel traceability build (backend + UI)
4. **Session 71:** Catalyst drug_id backfill + P1 cleanup

---

## What NOT to Do in Session 67

- No new enrichment fields
- No new AI signal generation
- No new Ailux angle generation
- No C11 parallel-write
- Do not merge company row IDs without FK dependency check
- Do not collapse Roche/Genentech, Prometheus/Merck, or Ventyx/AbbVie into single entities

---

## Modified Files — Session 66

| File | Change |
|---|---|
| `index.html` | Fix 3A: drug card news section (_cemDrugBody + openDrugEntityModal) |
| `index.html` | Fix 3B: drug card catalyst timeline section (_cemDrugBody + openDrugEntityModal) |
| `index.html` | Fix 4: company card coverage section (_cemCompanyBody + openCompanySlideOver) |
| `index.html` | Fix 5: industry insights news_articles routing (loadIndustryInsightsFeed) |
| `docs/company_cleanup_plan.md` | NEW — identity violations + connectivity scorecard + depth chains |
| `NEXT_SESSION.md` | This file |

**Supabase inserts:**
- `companies`: ventyx (Ventyx Biosciences, acquired, parent=abbvie)
- `drugs`: vtx002 (VTX002, S1P1 modulator, Phase 2, company_id=ventyx, current_owner=abbvie)
