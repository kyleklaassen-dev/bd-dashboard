# Meridian Stabilization Plan — Living Guide

**Status:** ACTIVE · **Started:** 2026-06-09 · **Owner:** Kyle + Claude
**Update cadence:** edit this file at the end of every stabilization session (check off done items, append notes). This is the reference doc — read it first.

> **North-star goal:** *By the end of this effort there is exactly ONE approved, enforced path that can modify each core entity (drug, company, edge). Optimize for clarity, reversibility, testability, and database stability — not speed.*

> **The one rule that makes this real:** "single writer" is a *convention* until the database enforces it. Every phase's success is measured by **enforcement** (a permission boundary), not by "scripts were rewritten."

---

## Diagnosis (why we're doing this)

Not file size. The instability is **uncoordinated database write paths**: 165 scripts write to Supabase — **17 → `drugs`, 9 → `companies`, 7 → `entity_edges`**. Governance exists (CLAUDE.md §1–6, ~30 memory files, trust/contradiction/source machinery) but is **scattered and unenforced**. The job is to *consolidate and enforce*, not invent.

---

## Phase map (status legend: ⬜ todo · 🔄 in progress · ✅ done)

### Phase 0 — Audit  ✅ DONE (2026-06-09)
- ✅ Dashboard-wide connectivity audit (`docs/audits/`), repo inventory, write-path report, table classification, cross-table analysis.
- ✅ Data fixes done as groundwork: 10 duplicate entities merged, 50 combo-target edges, market/rx tables linked, shared `entity_matcher` deployed.

### Phase 0.5 — Governance (consolidate + enforce)  🔄 IN PROGRESS
Define the rules (short, machine-checkable) and prove enforcement on ONE entity.
- ⬜ **Meridian Constitution** (1–2 pages): what is truth, what may modify it, source hierarchy, what's immutable, what needs approval. *Distilled from existing rules, not invented.*
- ⬜ **Drug Lifecycle Map** (active paths only): source → script → table → transformation → validation → writer → frontend. **This is the truth-test — if we can't map it accurately, we can't safely build DrugWriter.**
- ⬜ **Data Governance Table**: per core table → owner / sole-writer / validation / source-hierarchy.
- ⬜ **ADR** (Architecture Decision Register): consolidate the ~30 memory decisions into `docs/decisions.md`.

### Phase 1 — Quick wins (safe, reversible, parallel)  🔄 IN PROGRESS
- ✅ **`entity_edges` UNIQUE(subject_id,predicate,object_id)** — DONE 2026-06-09. Removed 51 dup rows, added constraint `entity_edges_subj_pred_obj_uniq` via Management API; `seed_target_edges.py` now uses on_conflict. Edge writes are idempotent at the DB layer.
- ⬜ **Root file cleanup** — move 40 loose root scripts (17 `build_v*.py` + audit/debug one-offs) → `/scripts/one_off` + `/archive`.
- ⬜ **CLAUDE.md slim** — keep operational-only; move detail to `/docs/architecture.md`, `workflows.md`, `database.md`, `decisions.md`, `/docs/archive/`.
- ⬜ **Decide the 12 broken-collector tables** (revive vs retire) + apply the 6 safe drops (`migrations/PROPOSED_drop_dead_tables.sql`).

### Phase 2 — Single Writer Pattern (the stability payoff)  ⬜
- ⬜ **Build `DrugWriter`** (`src/database/drug_writer.py`): identity resolution + governance checks + dedup-on-write + validation query after write. One table, one writer.
- ⬜ **ENFORCE**: revoke direct write on `drugs` from anon/service; route all writes through DrugWriter (RPC/edge function or RLS). **Success = direct writes to `drugs` are physically blocked.**
- ⬜ Migrate the *active* drug write paths through DrugWriter (dead ones archived).
- ⬜ **Regression tests** (`tests/database/`): dup detection, governance invariants, orphan check.
- ⬜ Stress-test DrugWriter in real operation before moving on.
- ⬜ Repeat for `CompanyWriter`, then `EdgeWriter`, then `CatalystWriter` — one at a time, only after the prior survives.

### Phase 3 — Modularization  ⬜
- ⬜ Split the 6 largest scripts (>1,500 lines) per layer, preserving entrypoints + smoke tests.
- ⬜ Stand up the `/src` layer structure (ingestion / identity / ontology / enrichment / scoring / database / frontend / utils).
- ⬜ Backfill `source_documents.entity_id`, resolve `signals` / `efficacy_benchmarks`.

### Phase 4 — Frontend  ⬜
- ⬜ Decompose `index.html` (33,983 lines) into components. Highest effort, last.

### Phase 5 — Resume features  ⬜
- ⬜ Only once Phases 1–3 are green.

---

## The five maps (authored across phases, live in `/docs`)
1. ⬜ Structure map — file → folder → status (active/legacy/deprecated)
2. 🔄 Workflow map — source → ingestion → identity → ontology → enrichment → scoring → database → frontend
3. 🔄 Database stability map — core tables, write paths, read paths, FK deps, risky columns, validation-per-write
4. 🔄 Frontend dependency map — UI section → tables/functions (first cut from `index.html` grep)
5. ⬜ Claude working map — read-first / source-of-truth / avoid-unless-asked

## Claude behavior rules (enforced every change)
**Before editing:** state the layer, affected files, affected tables, breakpoints, proposed tests. Keep changes small + reviewable.
**After editing:** run/propose tests, update the changelog + this plan, deprecate (don't ambiguously delete), add no duplicate workflows.
**Hard rule:** no DB write path ships without a validation query. No new features until Phases 1–3 are green.

## Success criteria (how we know we're done)
- [ ] Exactly one enforced writer per core entity (drug → company → edge → catalyst).
- [ ] Direct writes to core tables physically blocked (permission boundary).
- [ ] `entity_edges` idempotent at the DB layer.
- [ ] Root directory contains only live code; one-offs archived.
- [ ] CLAUDE.md short; governance consolidated into Constitution + Governance Table + ADR.
- [ ] Regression tests green for dup/governance/orphan invariants.

---

## Drug write-path findings (Phase 0.5 input — first pass, finalize in the lifecycle map)
Candidate scripts that write `drugs`: `company_enrichment.py`, `write_meridian.py`, `drug_intake.py`, `molecule_enrichment.py`, `catalog_backfill.py`, `company_intake.py`, `inference_rules.py`, `normalize_targets_modality.py`, `verify_sources.py`, `one_time_migration.py`, `apply_drug_sources_migration.py` (+ ~6 more referencing `drugs`).
**Key structural finding:** each script has its *own* `sb_upsert()`-style write wrapper — there is **no shared write layer**. That is precisely what `DrugWriter` replaces.
Workflow linkage is murky (many run on-demand via Cowork since API spend is paused, or via orchestrators) — the lifecycle map must trace orchestrators, not just `.yml` name matches. Active confirmed: `company_enrichment`→backfill-bd-angle, `research`→meridian-graph-rebuild.

## Session log
- **2026-06-09** — Plan created. Phase 0 ✅. Phase 1: entity_edges UNIQUE constraint ✅ (51 dups removed + constraint added). Phase 0.5: drug write-path classified (first pass) — found per-script `sb_upsert` wrappers / no shared layer. **Next:** author the Drug Lifecycle Map (active paths, tracing orchestrators) + Governance Table, then build `DrugWriter`. Run quick wins (root cleanup, CLAUDE.md slim) in parallel. _(append future sessions here)_
