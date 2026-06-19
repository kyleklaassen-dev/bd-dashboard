# PROPOSED — Asset-tab templating (#6) + live valuation wiring (#10)

**Status:** PROPOSAL FOR REVIEW · **Authored:** 2026-06-19 (tab value-audit, Batch C follow-up) · **Owner:** Kyle approval required before any DB write.

> Scope: this is the deferred, DB-dependent half of audit recs **#6** and **#10**. Nothing here has been applied. The safe, no-DB parts (factual fixes + honest valuation disclaimers) already shipped in Batch C on branch `cleanup/tab-value-audit`.

---

## Problem (today)

The 7 asset tabs (TL1A, TSLP, IL-4Rα×TSLP, IL-4Rα×OX40L, IGF1R×TSHR, FcRn, BCMA×CD19×CD3) are **structural clones**. Only 3 blocks per tab are live (Program-Intelligence table, catalysts, BD activity). The rest — differentiators, market stats, China molecules, SOC ladders, biology/history, **and the deal-value cards** — are **hardcoded HTML dated "May 2026."** Consequences:
- Drift / rot (e.g. the OX40L `Ebglyss`/`$4.5B` errors just fixed by hand).
- A new target = a new ~250-line hand-cloned pane.
- The most strategically load-bearing numbers (valuations) are the *least* trustworthy (static, unsourced).

## Goal

A new asset tab = **a data row, not a cloned pane.** One renderer reads per-target content from Supabase; valuation cards are computed from real deal comparables, each with a source.

---

## #6 — Data model for asset-tab content

Reuse existing tables where they already hold the data; add narrowly-scoped tables only for the prose blocks that have no home.

**Already live (reuse, no new table):**
- `drugs`, `entity_edges` (TREATS / competitive) → Program-Intelligence + competitive race.
- `catalysts` → catalyst calendar.
- `deals` → BD activity.
- `indication_patient_intelligence` → market stats (market size, US/global patients, unmet-need, biologic-failure, SoC remission). *(already powers Home Preview.)*
- `payer_tpp_criteria` → payer/TPP hurdle.
- `entity_narratives` (+ `narrative_provenance`, `narrative_claim_triangulation`) → cited prose for differentiators / biology / history / SoC. *(already powers Home Preview.)*

**Proposed new (only for content with no current home):** — schema drafted in `migrations/PROPOSED_asset_templating.sql` (CREATE TABLE only, **not applied**).
1. `asset_programs` — one row per Ailux program, **anchored to the existing `target_pairs` table** (`target_pair_id` → `target_pairs.id`; the 7 programs = `target_pairs WHERE ailux_pair`). Cols: `program_code` (ALX001…), `target_pair_id`, `indication_lead`, `modality`, `status`, `clinical_target`, `format_advantage`, `differentiators jsonb` (label/value/sub triples), `source_url`, `updated_at`. Source: migrated from the current hardcoded `ailux-card` blocks.
2. `competitor_molecules_supplemental` *(optional)* — only if the China-molecule cards carry facts not already in `drugs`. Prefer folding these into `drugs` with a `region`/`origin` flag rather than a new table.

**Renderer:** one `renderAssetTab(targetKey)` in a new `assets/js/asset_tab.js` that hydrates a single template from the above. Retire the per-tab hardcoded panes once parity is verified tab-by-tab (deprecate, don't bulk-delete).

**Governance:** writes to `drugs`/`entity_edges` go through the existing Writers (DrugWriter/EdgeWriter) — no ad-hoc `sb_upsert`. New tables (`asset_programs`) get an owner/sole-writer row in `governance_table.md` and a validation query.

## #10 — Valuation cards from real comps

3. `deal_comparables` — curated, **sourced** comp set. Cols: `id`, `target_pair`/`modality`, `acquirer`, `asset`, `deal_type`, `upfront_usd_m`, `total_usd_m`, `year`, `source_url` (**required**), `notes`. Seed from `deals` where structured, hand-curate the rest.
4. `asset_valuation_model` *(or a view)* — per `program_code`: derive Est. Upfront / Est. Total / post-Ph1 / post-Ph2 ranges **from `deal_comparables`** (e.g. median upfront of same-modality pre-IND deals ± band), not hardcoded. Each card renders the comp rows it was computed from + their source URLs.

When live: delete `labelValuationEstimates()` (the interim disclaimer) and replace with the real comp provenance panel.

---

## Migration sequence (each step reversible, gated)

1. **Review this doc** → Kyle approves table shapes.
2. Author `migrations/PROPOSED_asset_templating.sql` (CREATE TABLE only; no data) → review.
3. Backfill `asset_programs` + `deal_comparables` from current hardcoded content **with sources** → validation query (every row has a source_url; counts match the 7 programs).
4. Build `asset_tab.js` renderer behind a flag; verify **one** tab (TL1A) at parity in preview.
5. Roll remaining 6 tabs; deprecate hardcoded panes per tab as each reaches parity.
6. Wire valuation cards to `deal_comparables`; remove the interim disclaimer.

## Risks / open questions

- Does `entity_narratives` already cover the biology/history/SoC prose for all 7 targets, or only the home-preview indications? (audit before relying on it.)
- China-molecule cards: fold into `drugs` (preferred) vs. a supplemental table — needs a data check.
- Valuation bands are judgment calls; the model must show its comp set so the number is defensible, not a black box.
- **Sourcing is the gating constraint, not the schema.** The current hardcoded asset/valuation content has **no source rows**. The constitution forbids fabricating URLs, so step 3 (backfill) cannot be auto-generated — each `asset_programs`/`deal_comparables` row needs a real source found and attached. This is curation work, and is why this half was split out: the *schema* is cheap; the *sourced data* is the real effort.

## Status / next gate
- ✅ Table shapes approved (Kyle, 2026-06-19).
- ✅ **APPLIED** `migrations/APPLIED_2026-06-19_asset_templating.sql` via Management API — `asset_programs` + `deal_comparables` created with RLS anon-read; verified (columns, RLS, anon 200).
- ✅ **Pilot APPLIED + verified**: `asset_programs` seeded with ALX001 (TL1A) from the hardcoded card (`APPLIED_2026-06-19_asset_programs_seed_tl1a.sql`); `assets/js/asset_tab.js` renders the TL1A differentiator grid from the table (`data-source="asset_programs"`, 4 items, exact parity) with a silent static fallback. No console errors.
- ⬜ **Next (repeatable per tab):** seed the remaining 6 programs (TSLP, IL-4Rα×TSLP, IL-4Rα×OX40L, IGF1R×TSHR, FcRn, BCMA×CD19×CD3) — each: extract its `ailux-card` content → seed row → add `id="asset-diff-<tab>"` + a `DIFF_GRID_BY_PROGRAM` entry → verify. Then **#10**: backfill `deal_comparables` with **sourced** comps (source_url is NOT NULL — derive from the live `deals` table where sourced; no fabricated URLs) → render valuation cards from it → remove the interim `labelValuationEstimates()` disclaimer.
- Note: target_pairs reconciliation (add the 4 missing pairs + flag the 7 `ailux_pair`) is follow-up ontology work; `asset_programs.target_pair_id` is nullable until then.
