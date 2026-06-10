# Meridian Stabilization & Production-Readiness Audit

**Date:** 2026-06-09 · **Type:** Stabilization sprint — *audit first, no rebuild.*
**Guiding principle (yours):** *Do not optimize for speed. Optimize for clarity, reversibility, testability, and database stability.*

This document is the deliverable set for the first stabilization sprint: repo inventory, large-file report, DB write-path report, workflow map, deprecated/duplicate list, table-cleanup classification, cross-table connection analysis, proposed architecture, and the first 10 refactor tasks ranked by risk reduction. Nothing destructive was executed — drops are staged for your review.

---

## 0. My insight on the directive (before the data)

The directive is sound. Three things I'd add or sharpen:

1. **The real instability isn't file size — it's uncoordinated database write paths.** 165 scripts write to Supabase; **17 different scripts write to `drugs`, 9 to `companies`, 7 to `entity_edges`.** That, not a 4,000-line file, is what produces the duplicates and drift we keep fixing (e.g., the `sl-325`/`sl325` and 10 entity duplicates merged today). Splitting files is good hygiene; **routing all writes through a single guarded data-access layer is what actually buys stability.** I'd make that the spine of the work, not an afterthought.

2. **"Empty table" is two very different problems.** Some empty tables are *retired* (safe to drop). Others are *read by the UI but never populated* — `company_areas` is referenced **28×** in `index.html` but holds **0 rows**, `company_profiles` 13×, `drug_modalities` 10×. Those are **dark features**, not dead tables. And ~12 tables are *written by a script but still empty* — **silently broken or paused collectors.** Cleanup must separate these three.

3. **Reversibility first.** A dropped table is unrecoverable without a backup. So the cleanup is staged as a reviewable migration, and the file restructure should move files (git-tracked, reversible) before deleting anything. I recommend we never `DROP` in the same PR that does anything else.

---

## 1. Repo inventory

| Area | Count | Notes |
|---|---|---|
| Python files (total) | **300** (~112,900 LOC) | 185 in `scripts/`, **40 loose at repo root** |
| Root-level one-off builders | **17** (`build_v3.py`…`build_v20.py`) | Dashboard-generation history; belong in `/scripts/one_off` or `/archive` |
| GitHub workflows | **50** `.yml` | Many overlapping (graph rebuild appears in 3+ places) |
| SQL migrations | **155** | Numbered `v1`…`v145`+; no consolidated schema snapshot |
| Docs | **194 files** under `/docs` | Sprawling; no clear "read-first" index |
| Root `.md` | 23 | PRIORITY, NEXT_SESSION, ARCHITECTURE x3, etc. |
| Root `.html` | 33 | `index.html` + many prototypes/backups |
| Supabase tables/views | **268** | 192 carry entity columns; 42 empty |

**Top-line problem:** the root directory is a working scratchpad (one-offs, backups, audits, debug scripts) mixed with production code. A reviewer can't tell what's live.

## 2. Large-file report (>300-line rule)

| File | Lines | Disposition |
|---|---|---|
| `index.html` | **33,983** | ⚠️ The monolith. Single-file dashboard. Highest-effort, highest-value split (see Phase 3). |
| `scripts/company_enrichment.py` | 4,422 | Split: prompt/templates → config; IO → data layer; logic → modules |
| `scripts/weekend_sprint.py` | 2,999 | One-off orchestration → `/scripts/one_off` |
| `scripts/write_meridian.py` | 2,391 | Split: prompt assembly / data feed / render |
| `scripts/drug_intake.py` | 1,659 | Split: identity / enrichment / write |
| `scripts/research.py` | 1,538 | Split: fetch / parse / write |
| `scripts/ct_gov_sync.py` | 1,409 | Split: fetch / map / write |
| `build_v11/18/20.py` (root) | 1,100–1,580 | Archive (one-offs) |
| `scripts/narrative_gen.py`, `acquisition_scorer.py`, `company_intake.py` | 1,000–1,200 | Split per layer |

~25 scripts exceed 300 lines. **None should be split blindly** — each split must preserve the public entrypoint and pass a smoke test (Phase 3 rule).

## 3. Database write-path report (the stability core)

165 scripts perform writes. Concentration on core tables (each = an independent, ungoverned write path):

| Core table | # scripts writing/referencing | Risk |
|---|---|---|
| `drugs` | **17** | Duplicate rows, field drift, attribution overwrites |
| `companies` | **9** | Duplicate companies (8 merged today), status flip-flops |
| `entity_edges` | **7** | Inconsistent predicates, orphan nodes, no unique constraint |
| `catalysts` | 3 | Duplicate/again stale catalysts |
| `intel_facts` / `drug_targets` | 2 each | Already centralized — good model to copy |

**Recommendation:** introduce `src/database/` with one writer per core table (`drugs_writer`, `companies_writer`, `edges_writer`) that enforces: identity resolution (via `entity_matcher`), governance rules (CLAUDE.md §1–6), dedup-on-write, and a validation query after every write. No script writes a core table directly after that.

**Also found:** `entity_edges` has **no unique constraint** (today's combo-target seeder had to dedup in-memory). Add `UNIQUE(subject_id, predicate, object_id)` so writes are idempotent at the DB layer.

## 4. Table-cleanup classification (staged — nothing dropped)

Of 42 empty tables/views:

- **SAFE-DROP — empty, 0 frontend reads, 0 script refs (6):** `change_frequency_summary`, `company_area_detail`, `effective_company_areas`, `governance_change_alerts`, `phase3_regulatory_risk_map`, `recent_field_changes`. *(Several are VIEWS — confirm table-vs-view before dropping; staged migration uses `DROP VIEW IF EXISTS` / `DROP TABLE IF EXISTS` accordingly.)*
- **BROKEN/PAUSED COLLECTORS — script writes exist but table empty (12):** `china_trials`, `correction_labels`, `drug_stage_history`, `fine_tune_dataset`, `model_validation_results`, `narrative_claim_triangulation`, `narrative_feedback`, `narrative_source_diversity`, `source_collection_gaps`, `target_areas`, `trajectory_summary`, `trial_identity`. **Action: decide per-table — revive the collector or retire both table + script.** (Matches your "retired vs broken" question — these are the suspects.)
- **DARK FEATURES — UI reads them but they're empty (keep, populate):** `company_areas` (read 28×), `company_profiles` (13×), `drug_modalities` (10×), `intel_areas` (11×), `intel_companies` (7×), `indication_biology_tags` (7×), `drug_routes` (6×), + others. **These are research gaps, not cleanup targets** — the dashboard has features wired to data we never produced.
- **LEGACY-but-referenced:** `drug_areas` (read 23×, written 24×) — superseded by `drug_targets` per CLAUDE.md, but legacy fallback code still reads it. Retire only after removing the fallback reads.

Staged migration: `migrations/PROPOSED_drop_dead_tables.sql` (review & apply manually).

## 5. Cross-table connection analysis (missing relationships)

Analyzed all 192 entity-bearing tables for links they *should* have:

1. **Non-standard entity columns escape all FK tooling.** `asset_transfer_history` links companies via `from_entity_id`/`to_entity_id` (not `company_id`); `entity_edges`/`ownership_edges` use `subject_id`/`object_id`. These broke today's merge until handled. **Action: adopt a canonical FK naming convention** (`<entity>_id`) or maintain an explicit alias-column registry the tooling reads.
2. **`source_documents` → entity: 54/55 unlinked.** Research PDFs aren't connected to the company/drug they cover (their *facts* are, the documents aren't).
3. **`intel_digests.companies`/`drugs` are text arrays, never resolved to ids** — the per-document entity list isn't in the graph.
4. **`market_landscape`/`rx_market_tracker`** — fixed today (0→72% / 0→88%).
5. **Orphan nodes in `entity_edges`:** 63/191 companies, 8 targets, 15 indications have zero edges (drugs now 0 orphans after today's fix).
6. **`signals` (32%), `efficacy_benchmarks`, `ailux_strategic_context`** — entity columns present but unresolved.

**Heatmap inputs (where research/coverage is thinnest):** Payer/TPP, Patient-intelligence, and IP/patent domains remain the thinnest (consistent with the Coverage Atlas); add to that the **dark-feature tables** (company_areas, company_profiles, drug_modalities) as concrete "populate me" targets, and the **broken-collector tables** as "fix or cut."

## 6. Proposed target architecture

```
/src
  /ingestion     external fetch (ct.gov, SEC, PubMed, PDFs, news) — fetch only, no writes
  /identity      entity_matcher + canonical id resolution (today's module lives here)
  /ontology      targets/indications/areas mapping + combo-target logic
  /enrichment    model-driven field enrichment (prompts in /config, not inline)
  /scoring       coverage / strategic-value / foresight / trust
  /database      ONE writer per core table; all governance + validation here
  /frontend      dashboard build (split index.html into components)
  /utils         shared http/supabase client, logging
/docs
  /architecture  /workflows  /database  /decisions  /audits  /archive
/tests
  /unit  /integration  /database  /regression
/scripts
  /one_off  /maintenance  /migration
```

**The five maps** (to be authored in `/docs`):
1. **Structure map** — file → folder → status (active/legacy/deprecated).
2. **Workflow map** — source → ingestion → identity → ontology → enrichment → scoring → database → frontend.
3. **Database stability map** — core tables, write paths, read paths, FK deps, risky columns, validation query per write.
4. **Frontend dependency map** — which UI section reads which table/function (we have a first cut from the `index.html` grep).
5. **Claude working map** — read-first files, source-of-truth files, avoid-unless-asked files.

**CLAUDE.md split:** keep `CLAUDE.md` short/operational; move detail to `/docs/architecture.md`, `/docs/workflows.md`, `/docs/database.md`, `/docs/decisions.md`, `/docs/archive/`.

## 7. First 10 refactor tasks — ranked by risk reduction (low risk, high payoff first)

| # | Task | Why (risk reduced) | Effort | Risk |
|---|---|---|---|---|
| 1 | Add `UNIQUE(subject_id,predicate,object_id)` to `entity_edges` | Idempotent edge writes; kills a whole dup class | S | Low |
| 2 | Move 40 root one-offs/backups → `/scripts/one_off` + `/archive` | Reviewer can see what's live | S | Low |
| 3 | Author the 5 maps + split `CLAUDE.md` | Clarity; less Claude context overload | M | Low |
| 4 | Decide the 12 broken-collector tables (revive vs retire) + apply staged drops for the 6 safe ones | Removes confusion | M | Low (staged) |
| 5 | Create `src/database/` writers for `drugs`, `companies`, `entity_edges` (wrap existing logic) | Collapses 17/9/7 write paths → 1 each | L | Med |
| 6 | Route the top 5 enrichment scripts through the new writers | Stops drift/dupes at the source | M | Med |
| 7 | Add `tests/database/` regression: dup detection, governance invariants, orphan check | Catches regressions automatically | M | Low |
| 8 | Backfill `source_documents.entity_id` + resolve `signals`/`efficacy_benchmarks` | Connectivity | S | Low |
| 9 | Split the 6 largest scripts (>1,500 lines) per-layer, preserving entrypoints + smoke tests | Reviewability | L | Med |
| 10 | Split `index.html` into components (last — highest effort) | Frontend maintainability | XL | High |

## 8. Phased plan

- **Phase 0 — Audit (this document).** ✅ Done. Plus today's data fixes (dedupe, combo-target edges, matcher).
- **Phase 1 — Safe structure & guardrails (Tasks 1–4).** No logic changes. Move files, add the edge constraint, author maps, split CLAUDE.md, apply the 6 safe drops + decide collectors. Fully reversible.
- **Phase 2 — Data-access layer (Tasks 5–7).** Build `src/database/` writers + tests; migrate top write paths. *This is the stability payoff.*
- **Phase 3 — Modularization (Tasks 8–9).** Split oversized scripts behind stable entrypoints with smoke tests.
- **Phase 4 — Frontend (Task 10).** Decompose `index.html`.
- **Phase 5 — Resume features** only once Phases 1–3 are green.

**Claude behavior rule for all phases (adopt into CLAUDE.md):** before editing — state the layer, affected files, affected tables, breakpoints, and proposed tests; keep changes small. After editing — run/propose tests, update changelog, deprecate (don't delete ambiguously), add no duplicate workflows. No DB write path without a validation query.

---

*Companion artifacts produced today: `Knowledge_Graph_Connectivity_Audit_2026-06-09.md` (graph connectivity), `migrations/PROPOSED_drop_dead_tables.sql` (staged, review before apply). Data changes executed today: 10 entity duplicates merged, 50 combo-target edges added, market/rx tables linked, shared `entity_matcher` deployed.*
