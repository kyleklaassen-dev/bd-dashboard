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

### Phase 0.5 — Governance (consolidate + enforce)  ✅ DONE (2026-06-09)
- ✅ **Meridian Constitution** — `docs/constitution.md` (1-2pg, distilled from existing rules).
- ✅ **Drug Lifecycle Map** — `docs/architecture/drug_lifecycle.md` (truth-test; found "no shared write layer, 30 sb_upsert helpers").
- ✅ **Data Governance Table** — `docs/database/governance_table.md` (per-table owner/writer/validation/source-hierarchy).
- ✅ **ADR** — `docs/decisions.md` (ADR-001…011 consolidating memory).

### Phase 1 — Quick wins (safe, reversible, parallel)  🔄 IN PROGRESS
- ✅ **`entity_edges` UNIQUE(subject_id,predicate,object_id)** — DONE 2026-06-09. Removed 51 dup rows, added constraint `entity_edges_subj_pred_obj_uniq` via Management API; `seed_target_edges.py` now uses on_conflict. Edge writes are idempotent at the DB layer.
- ✅ **Root file cleanup** — DONE. 40→3 root `.py`; 47 one-offs/backups → `archive/dashboard_builds`, `archive/html_backups`, `scripts/one_off` (local; these weren't in the repo).
- ✅ **CLAUDE.md slim** — DONE. 176→45 lines, operational + pointers to `/docs`; original preserved at `docs/archive/CLAUDE_full_2026-06-09.md`.
- 🔄 **Decide the 12 broken-collector tables** (revive vs retire) — REVIEWED (see Open decisions). Safe drops staged in `migrations/PROPOSED_drop_dead_tables.sql` (await Kyle).

### Phase 2 — Single Writer Pattern (the stability payoff)  🔄 IN PROGRESS
- ✅ **Shared client** `src/database/client.py` (replaces the 30 ad-hoc `sb_upsert` helpers).
- ✅ **Build `DrugWriter`** (`src/database/drug_writer.py`): identity resolution + governance + dedup + validation. Smoke-tested live (resolved SL-325→sl325, no dup; rejected brand+Phase1).
- ✅ **Regression tests** (`tests/database/test_drug_writer.py`): 6/6 green; found 7 pre-existing brand⇒approved cases (baselined — see Open decisions).
- ⬜ **ENFORCE** (staged, needs Kyle + a watch window): `migrations/PROPOSED_drugwriter_enforcement.sql` — trigger backstop + permission boundary. **Success = direct writes to `drugs` physically blocked.**
- ⬜ Migrate the *active* drug write paths through DrugWriter (intake → enrichment → normalize → meridian).
- ⬜ Stress-test, then repeat for `CompanyWriter` → `EdgeWriter` → `CatalystWriter`.

### Phase 3 — Modularization  ⬜
- ⬜ Split the 6 largest scripts (>1,500 lines) per layer, preserving entrypoints + smoke tests.
- ⬜ Stand up the `/src` layer structure (ingestion / identity / ontology / enrichment / scoring / database / frontend / utils).
- ✅ Backfill `source_documents.entity_id` (54→0 unlinked) + `signals.company_id` (+12) via `scripts/maintenance/link_extras.py`. `efficacy_benchmarks` needs a `drug_id` column first (schema change — Open decisions).

### Phase 4 — Frontend  ⬜
- ⬜ Decompose `index.html` (33,983 lines) into components. Highest effort, last.

### Phase 5 — Resume features  ⬜
- ⬜ Only once Phases 1–3 are green.

---

## The five maps  ✅ DONE (2026-06-09) — `docs/architecture/repo_maps.md` (+ lifecycle + governance_table)
1. ✅ Structure map — `repo_maps.md` §1
2. ✅ Workflow map — `repo_maps.md` §2 (50 workflows grouped) + `drug_lifecycle.md`
3. ✅ Database stability map — `database/governance_table.md` (+ `repo_maps.md` §5)
4. ✅ Frontend dependency map — `repo_maps.md` §3 (index.html table reads)
5. ✅ Claude working map — `repo_maps.md` §4

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

## Open decisions for Kyle (await approval)
1. **DrugWriter enforcement** — apply `migrations/PROPOSED_drugwriter_enforcement.sql` (trigger in WARN→EXCEPTION + permission boundary). Needs a window to watch live pipelines. This is the step that makes "single writer" real.
2. **7 brand⇒approved cases** (benralizumab/Fasenra, rozanolixizumab/Rystiggo, upadacitinib/Rinvoq, mepolizumab/Nucala, nipocalimab/Imaavy, tralokinumab/Adbry, lebrikizumab/Ebglyss). These are approved molecules tracked at the *phase of an Ailux-relevant indication*. Decide: set `stage='approved...'` (molecule truth) and move per-indication phase to `drug_indications`, OR keep as-is and treat brand as informational. Currently baselined in the test.
3. **Table drops** — `migrations/PROPOSED_drop_dead_tables.sql` (6 safe + 12 broken-collector decisions). Review & apply.
4. **`efficacy_benchmarks`** — add a `drug_id` column so its 12 rows can join the graph (schema change).
5. **Repo file relocation** (moving live `scripts/` into `/src` layers) — deferred to a supervised pass; would require updating workflow paths.

## Session log
- **2026-06-09 (a)** — Plan created. Phase 0 ✅. entity_edges UNIQUE constraint ✅. Drug write-path classified — no shared write layer.
- **2026-06-09 (b, overnight autonomous)** — **Phase 0.5 ✅** (Constitution, Lifecycle Map, Governance Table, ADR). **Phase 1**: root cleanup ✅ (40→3 root .py), CLAUDE.md slim ✅ (176→45), broken-collectors reviewed. **Phase 2 🔄**: shared `client.py` ✅, `DrugWriter` ✅ (live smoke-tested), regression suite ✅ 6/6; enforcement staged. **Phase 3**: source_documents + signals connectivity ✅. All committed. **Next:** Kyle reviews Open decisions → apply DrugWriter enforcement → migrate active drug write paths → then CompanyWriter. _(append future sessions here)_
