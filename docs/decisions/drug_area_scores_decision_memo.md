# drug_area_scores — Decision Memo
**Produced:** 2026-05-27 (Session 81)  
**Author:** Claude (analysis session — no code written)  
**Status:** Recommendation only. No table touched, no harnesses removed, no UI modified.

---

## Executive Summary

**Recommendation: Option C — Hybrid migration.**

Add `competitive_relevance` and `relevance_rationale` to `drug_competitive_scores`. Backfill from DAS. Update the `_makeAreaPI` select to include them. The feature comes back to life in one coding session with two SQL statements and one line of code.

Do not deprecate. Do not drop DAS yet. Do not touch dual-read harnesses.

---

## Field-by-Field Comparison

### DAS columns (19 total)
| Field | DAS Population | DCS Equivalent | Status |
|---|---|---|---|
| `id` | 212/212 | `id` (int, not uuid) | ✅ Both |
| `drug_id` | 212/212 | `drug_id` | ✅ Both |
| `area_id` | 212/212 | `context_id` (renamed) | ✅ Both (different name) |
| `overlap` | 212/212 | `overlap` | ✅ Both |
| `overlap_rationale` | 179/212 | `overlap_rationale` | ✅ Both |
| `cls` | 75/212 | `cls` | ✅ Both |
| `confidence_level` | 185/212 | `confidence_level` | ✅ Both |
| `source_url` | 186/212 | `source_url` | ✅ Both |
| `vs_ailux_positioning` | 97/212 | `vs_ailux` (renamed) | ✅ Migrated (field renamed) |
| `competitive_relevance` | **212/212** | ❌ **NOT IN DCS** | 🔴 **Gap — feature dead** |
| `relevance_rationale` | **212/212** | ❌ **NOT IN DCS** | 🔴 **Gap — feature dead** |
| `area_fit` | 0/212 | ❌ Not migrated | ⚪ Empty — safe to discard |
| `area_fit_rationale` | 0/212 | ❌ Not migrated | ⚪ Empty — safe to discard |
| `strategic_value_score` | 0/212 | ❌ Not migrated | ⚪ Empty — feature moved to discovery_queue |
| `canonical_drug_id` | 89/212 | ❌ Not migrated | 🟡 Partial — audit value only |
| `enriched_model` | 97/212 | `enriched_by` (partial) | 🟡 Close enough |
| `enriched_by_run_id` | 0/212 | `notes` carries run info | ⚪ Empty in DAS |
| `last_enriched_at` | 212/212 | `enriched_at` | ✅ Both |
| `created_at` | 212/212 | `created_at` | ✅ Both |

### DCS-only columns (not in DAS)
| Field | DCS Population | Note |
|---|---|---|
| `context_type` | 253/253 | New dimension — `target`, `indication`, `area` |
| `migrated_from` | 253/253 | Provenance trail |
| `notes` | 253/253 | Free-text migration notes + model info |
| `updated_at` | 253/253 | Mutable audit timestamp |

---

## The Ten Questions

### 1. What fields exist only in DAS?

**Two fields with data:** `competitive_relevance` (212/212) and `relevance_rationale` (212/212).  
**Three fields that are empty:** `area_fit` (0/212), `area_fit_rationale` (0/212), `strategic_value_score` (0/212).  
`area_fit` and `strategic_value_score` were never populated — they are vestigial columns from the original schema design that never got enrichment pipeline support.

### 2. Which fields are still used in UI or validation?

**`competitive_relevance`** — Referenced in four places in `_makeAreaPI`:
- Drug-level sort in the expanded drug list (line ~15002): `_RELEV_SORT_DA[a.competitive_relevance]`
- Entity-level `bestRelevance` computation (line ~13776): reduce to find highest-tier program
- Relevance badge render: `this._relevBadge(ent.bestRelevance, ent.bestRelevanceRationale)` (line ~14259)
- Relevance border on entity rows: `border-left:3px solid ${_RELEV_BORDER[ent.bestRelevance]}` (line ~14278)
- Entity sort by relevance (line ~14201): `_RELEV_ORD_SORT[a.bestRelevance]`

**`relevance_rationale`** — Referenced in two places:
- Drug card expanded row tooltip (line ~9791): full text display in a detail panel
- Drug card compact list item (line ~9518): 150-char truncated display

**But all of these are currently dead.** The DCS select at line 13614 only fetches `drug_id,context_id,overlap,cls,overlap_rationale,vs_ailux,confidence_level` — no `competitive_relevance` or `relevance_rationale`. So `score?.competitive_relevance` is always `undefined → null`, and every drug gets relevance rank 6 (the null fallback). The badges, borders, and rationale text never render.

### 3. What does `competitive_relevance` mean?

It is a **strategic importance tier** — independent of clinical stage, independent of mechanistic overlap. It answers: "How much should Ailux pay attention to this drug right now?"

Five tiers:
- `very_high` — Direct threat, actionable intelligence required (e.g., duvakitug Phase 3 in IBD)
- `high` — Significant competitive context, should monitor trajectory
- `medium` — Relevant background, useful for deal benchmarking
- `low` — Low immediate threat, watch list only
- `monitor` — Historical/negative signal worth tracking (e.g., failed trials that inform pathway confidence)

This is **not** the same as `overlap`. A drug can be mechanistically Direct (hits the same target) but strategically low (preclinical, small company, no BD angle). A drug can be Watch (different mechanism) but very_high (Regeneron approved competing indication, partnership target).

### 4. What does `relevance_rationale` mean?

Natural-language explanation for the `competitive_relevance` tier assignment. Two quality tiers exist in the data:

**28 curated rationales** — Written by Claude with specific competitive intelligence. These are the valuable ones:
- `"Failed Phase 3 TED (April 2026). FcRn mechanism invalidated for TED. Monitor as negative data signal confirming IGF-1R is the validated path."` (batoclimab, monitor)
- `"Oral TSHR GPCR small molecule. Preclinical. Oral route + TSHR mechanism = double differentiation from IV IGF-1R mAb. If oral efficacy proven = significant threat."` (sp-1351, high)
- `"NMPA approved China March 2025. China-market reference for IGF-1R approval pathway. Partnership signal: Innovent licensing model."` (ibi311, low)

**184 stage-derived auto-placeholders** — Generated mechanically during enrichment:
- `"Stage-derived: Approved Watch competitor in tslp. Rationale pending deep curation."`
These have no analytical value. The tier assignment is real; the rationale text is a placeholder.

### 5. Are these still valuable in the Meridian ontology?

**`competitive_relevance` — YES, highly valuable.** It is a distinct semantic dimension that currently has no equivalent in the production read layer. Without it:
- The "Relevance" column in the area tab entity table always shows blank
- Entity rows have no left-border color coding
- The secondary sort by strategic importance is a no-op
- Kyle cannot visually separate "drugs I need to track" from "background noise"

The `overlap` tier tells you *what kind* of competitor something is. `competitive_relevance` tells you *how much it matters right now*. Both dimensions are necessary for the area tabs to be useful.

**`relevance_rationale` — YES, conditionally valuable.** The 28 curated rationales are the most compact form of strategic intelligence in the system — they are exactly what the "early-warning system" is supposed to surface. The 184 placeholders are noise but carry no cost; they can be replaced over time by deeper curation.

### 6. If valuable, where should they live in `drug_competitive_scores`?

As direct columns on the `drug_competitive_scores` table, matching DAS semantics exactly:

```sql
ALTER TABLE public.drug_competitive_scores
  ADD COLUMN competitive_relevance text 
    CHECK (competitive_relevance IN ('very_high','high','medium','low','monitor')),
  ADD COLUMN relevance_rationale   text;
```

These map cleanly — `drug_competitive_scores` already has `drug_id` and `context_id` as the primary key pair, which maps to DAS's `drug_id` + `area_id`.

### 7. If deprecated, what UI or logic should be removed?

If deprecated (Option B), the following UI code becomes dead weight and should be removed:
- `_relevBadge()` function (line ~13943–13952) 
- `_RELEV_ORD`, `_RELEV_ORD_SORT`, `_RELEV_SORT_DA`, `_RELEV_BORDER` constants
- Sort logic at lines ~14201–14202, ~15002–15003
- `bestRelevance` / `bestRelevanceRationale` computation in `_groupEntities` (lines ~13775–13779, ~13780)
- `relevBadge` and `relevBorder` in entity row render (lines ~14259, ~14278)
- The "Relevance" column header in the entity table (line ~14299)
- `relevance_rationale` display in drug detail rows (lines ~9791–9795, ~9518–9522)

That is a large surface to clean. And it removes a feature that exists in the data and has design intent.

**Recommendation against deprecation.**

### 8. What harnesses depend on DAS as baseline?

Five dual-read harnesses compare DCS output (current production) against DAS (legacy baseline):
- `_runPhase4BDualRead` — IBD
- `_runPhase4BTL1ADualRead` — TL1A
- `_runPhase4BTEDDualRead` — TED/IGF-1R
- `_runPhase4BAtopyDualRead` — IL-4Rα / TSLP
- `_runPhase4BFcRNDualRead` — FcRn

These harnesses only compare `overlap` tier (the primary classification). They do not compare `competitive_relevance`, `relevance_rationale`, or any other DAS field. So adding `competitive_relevance`/`relevance_rationale` to DCS does not affect the harnesses in any way.

The harnesses should remain until formally decommissioned — they are the proof layer that DCS overlap tiers are correct.

### 9. What data would be lost if DAS were dropped today?

**If DAS dropped today (before migration):**
- 212 `competitive_relevance` tier assignments — all lost
- 28 curated `relevance_rationale` narratives — permanently lost (these are not recoverable without re-running enrichment)
- 184 stage-derived placeholder rationales — lost but disposable
- `vs_ailux_positioning` for 97 drugs — partially covered by DCS `vs_ailux` (114 rows) but overlap unclear
- `canonical_drug_id` for 89 drugs — audit trail value; not used in production reads

**Critical data to preserve:** the 28 curated rationales and all 212 `competitive_relevance` tier values.

### 10. What is the lowest-risk migration path?

Two SQL statements, one line of code:

**Step 1 — Add columns to DCS (safe, additive):**
```sql
ALTER TABLE public.drug_competitive_scores
  ADD COLUMN IF NOT EXISTS competitive_relevance text 
    CHECK (competitive_relevance IN ('very_high','high','medium','low','monitor')),
  ADD COLUMN IF NOT EXISTS relevance_rationale text;
```

**Step 2 — Backfill from DAS where keys match:**
```sql
UPDATE public.drug_competitive_scores dcs
SET 
  competitive_relevance = das.competitive_relevance,
  relevance_rationale   = das.relevance_rationale
FROM public.drug_area_scores das
WHERE dcs.drug_id   = das.drug_id
  AND dcs.context_id = das.area_id
  AND das.competitive_relevance IS NOT NULL;
```

Expected: 166 rows updated (the 166 drug_id + area_id pairs present in both tables).

**Step 3 — Add fields to the `_makeAreaPI` select (one line):**  
Change line ~13614 from:  
`.select('drug_id,context_id,overlap,cls,overlap_rationale,vs_ailux,confidence_level')`  
to:  
`.select('drug_id,context_id,overlap,cls,overlap_rationale,vs_ailux,confidence_level,competitive_relevance,relevance_rationale')`

That is the entire migration. The sort logic, badge render, border color, and detail display all come back to life automatically — no other code changes needed.

---

## Data Verification Queries (Run in Supabase Before Executing)

```sql
-- Verify row count that will be updated
SELECT COUNT(*) FROM drug_competitive_scores dcs
JOIN drug_area_scores das ON dcs.drug_id = das.drug_id AND dcs.context_id = das.area_id
WHERE das.competitive_relevance IS NOT NULL;
-- Expected: 166

-- Confirm curated rationales are preserved
SELECT dcs.drug_id, das.competitive_relevance, left(das.relevance_rationale, 100) as preview
FROM drug_competitive_scores dcs
JOIN drug_area_scores das ON dcs.drug_id = das.drug_id AND dcs.context_id = das.area_id
WHERE das.relevance_rationale NOT LIKE 'Stage-derived:%'
  AND das.relevance_rationale NOT LIKE '%pending deep curation%'
ORDER BY das.competitive_relevance;
-- Expected: ~28 rows with substantive content
```

---

## Recommendation

**Option C: Hybrid — add to DCS, backfill, activate.**

This is functionally identical to Option A (migrate and preserve) but framed correctly: we are not "migrating" DAS — we are completing the Phase 2 migration that was left partial. The `competitive_relevance` and `relevance_rationale` fields were always meant to be in the production read layer; they simply weren't added to DCS during the initial migration.

Do not choose Option B (deprecate). The feature is designed, coded, enriched, and valuable. Removing it means removing the strategic importance signal from the area tabs permanently — that is the highest-value layer in Meridian.

**Do not execute now.** Confirm this recommendation first. The next session should be a short coding session: 2 SQL statements, 1 code change, validate relevance badges appear on area tab entity rows, deploy.

---

## What This Unblocks

Once `competitive_relevance` and `relevance_rationale` are in DCS and live in the UI:

1. **DAS has no remaining production UI dependencies.** Only dual-read harnesses (intentional archival) and OEX schema exploration (user-triggered) remain. DAS becomes retirable on the same schedule as the harnesses.

2. **Area tab entity rows get visual priority signals.** The relevance border and badge system comes back — Kyle can see which rows are "very high" threat at a glance, which are "monitor" background context.

3. **Drug card expanded rows show strategic rationale.** The 28 curated rationales become visible in the detail panel — this is where the "early warning signal" text surfaces.

4. **Secondary sort by strategic importance becomes active.** Within each stage cluster, drugs sort by `competitive_relevance` before reverting to stage order.

---

## Fields Safe to Discard (No Code Dependencies, Empty in DAS)

The following DAS-only fields have zero population and zero code references outside static documentation. They do not need to be migrated:
- `area_fit` — 0/212 populated, referenced only in Audit panel explanatory text
- `area_fit_rationale` — 0/212 populated, no code references
- `strategic_value_score` — 0/212 populated in DAS; feature moved to `discovery_queue` where it is active
- `enriched_by_run_id` — 0/212 populated, no code references

These can be left in DAS as vestigial columns until the table is dropped.
