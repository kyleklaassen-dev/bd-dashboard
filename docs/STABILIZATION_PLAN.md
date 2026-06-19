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
- ✅ **All drug write paths migrated (2026-06-09):** `approve_discovery.py` (birth point), `molecule_enrichment.py` (canonical_drug_id via `update_fields`), `seed_tl1a_companies.py` (seeder). `write_meridian.py` = reads only. **Zero `sb_upsert('drugs')` / direct drugs writes remain.** Regression 6/6 green.
- ⬜ Apply enforcement (`PROPOSED_drugwriter_enforcement.sql`) — needs Kyle + watch window.
- ✅ **CompanyWriter migration COMPLETE (2026-06-09):** `approve_discovery.py` (canonical dedup + create via CompanyWriter) + `seed_tl1a_companies.py`. **Zero direct `companies` writes remain.**
- ✅ **CatalystWriter built + migrated:** `src/database/catalyst_writer.py` (4th core writer) + `company_enrichment.py` catalyst writes routed via a contract-preserving drop-in. **Zero direct `catalysts` writes remain.**
- ✅ **EdgeWriter built**; `entity_edges` is idempotent at the DB layer (UNIQUE constraint). Existing edge seeders self-dedup + are constraint-protected → adopt EdgeWriter for NEW edge code (no risky churn of working deterministic seeders).
- ✅ All 4 core writers tested: `tests/run_all.py` → 14 tests green.
- ⚠️ **CORRECTION (2026-06-18) — the "Direct-write audit: drugs 0 / companies 0 / catalysts 0" claim was incomplete.** It only checked `sb_upsert` (create paths). A full write-verb audit (`scripts/maintenance/audit_core_writers.py`, covers upsert/insert/post/**patch**/update/delete) finds **18 direct writes still bypassing the Writers**: 16 `sb_patch('drugs',…)`, 1 `sb_patch('companies',…)`, 1 `sb_upsert('catalysts',…)`, across 11 active files (`ct_gov_sync.py`, `process_queue_item.py`, `execute_intel_actions.py`, `company_enrichment.py`, `weekend_sprint.py`, …). These patch fields like `company_id`, `stage`, `bd_angle`. **So "single writer" is not yet true for field *updates*.**
- ✅ **Guard added (2026-06-18):** `audit_core_writers.py --ci` runs in `ci-quality-gate.yml`. CI blocks any **NEW** file from writing a core table directly.
- ✅ **ALL bypasses MIGRATED (2026-06-18):** **20** real direct writes — 17 `sb_*` (16 `drugs`, 1 `companies`) **plus 3 raw-REST writes the first audit missed** (`reconcile_drug_integrity.py` PATCH `drugs`, `compute_strategic_value.py` PATCH `companies`, `score_foresight.py` PATCH `catalysts`) — now route through `update_drug()` / `update_company()` / `update_catalyst()` (`src/meridian/database/__init__.py` → the Writers' `update_fields`). Added `CatalystWriter.update_fields`. The 1 remaining audit match is a false positive (the `sb_upsert('catalysts')` in the `_catalyst_upsert` docstring). **Real direct-write debt to core tables is now ZERO** (audit `--strict`). Verified: writer suites 23/23 green, all migrated modules import, byte-compile clean.
- ✅ **Audit hardened (2026-06-18):** `audit_core_writers.py` now catches BOTH `sb_*('table')` calls AND raw-REST writes (`_req("PATCH", f"drugs?…")`, `rest(f"catalysts?…","PATCH")`, `patch(f"companies?…")`). The original blind spot (only `sb_upsert`) is closed; this class can't silently regress.
- ✅ **Enforcement AUTHORED (2026-06-18):** `migrations/PROPOSED_drugwriter_enforcement.sql` — a BEFORE trigger that reads the `X-Meridian-Actor` header (via PostgREST `request.headers`) and physically blocks any REST write to `drugs`/`companies`/`catalysts` not from its Writer; direct SQL/admin is allowed. Staged with a drugs-first rollout, verify steps, and an instant rollback. **Now safe to apply** because real debt is zero. (`PROPOSED_drop_dead_tables.sql` was NOT re-created — the 2026-06-18 live-DB check found the "dead" tables are real-but-empty framework tables, none safe to drop.)
- ⬜ **APPLY enforcement** (`PROPOSED_drugwriter_enforcement.sql`) — **needs Kyle + a watch window** (live-DB DDL). Apply drugs first, watch one nightly cycle, then companies/catalysts. **Success = direct REST writes to `drugs` physically blocked.** This is the last open Phase-2 item.

### Phase 3 — Modularization  🔄 IN PROGRESS
- 🔄 Split the 6 largest scripts — **plan authored** (`docs/architecture/modularization_plan.md`); execution pending (safe, one-at-a-time, after writer migrations).
- ✅ `/src` layer structure stood up (database populated; identity/ingestion/ontology/enrichment/scoring/frontend/utils = staged dirs).
- ✅ Backfill `source_documents.entity_id` (54→0) + `signals.company_id` (+12) via `scripts/maintenance/link_extras.py`.
- ✅ Added `drug_id` to `efficacy_benchmarks` (10/12 linked) + `ailux_strategic_context` (2/12) — additive columns, backfilled via matcher.
- ✅ Graph refreshed post-dedupe (link_entities --apply): 82% facts linked, consistent.

### Phase 4 — Frontend  🔄 (mostly done — see correction)
- ✅ **`index.html` decomposition essentially DONE** (2026-06-19 audit): it is **7,124 lines** now (not 33,983), with JS externalized into `assets/js/` (16 modules). Only ~78 lines of inline JS remain (5 small `<script>` blocks).
- ⬜ **New target: `assets/js/app.js` (13,554 lines, 211 functions)** — the monolith the JS moved into. Classic global-scope script; split per `docs/STATUS_AND_GAPS_2026-06-19.md` §4, browser-verified (needs supervision — live dashboard).

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
- **2026-06-15→16 (overnight, autonomous legibility + state-refresh pass)** — Operated on the LIVE repo (Contents + Git Data APIs); did NOT touch `index.html`. **Repo legibility:** trimmed `update_log.md` 495KB→~79KB (recent ~50 entries) with history archived to `docs/reports/update_log_archive.md`; organized `docs/` root 66→10 files (56 moved into reports/audits/database/frameworks/decisions, governance + script-referenced docs kept at root, git history preserves moves); reconciled `README.md`'s repository map to reality. **State refresh:** rewrote `PRIORITY.md` around the stabilization stage board and refreshed `NEXT_SESSION.md`. **TRUE state captured (anon read, 2026-06-15/16):** Engine re-enabled (15 core workflows live); Stage 0 (single protected `main`, clean clone) ✅; Stage 1 triage ✅ — `governance_violations` 86→**41** unresolved, `drug_validation_results` non-pass 43→**35** (0 fail); Stage 2 ✅ — 📡 Intelligence tab surfaces **11** previously-dark datasets. **Still blocked (the gate):** single-writer **enforcement** (`PROPOSED_drugwriter_enforcement.sql`) + Stage 1 residual data fixes + Stage 5 backfills are all **blocked on lost DB credentials** (Supabase service key + GitHub PAT) — rotate/re-share or remount to unblock. Live counts: drugs 194, companies 191, deals 218.
- **2026-06-09 (a)** — Plan created. Phase 0 ✅. entity_edges UNIQUE constraint ✅. Drug write-path classified — no shared write layer.
- **2026-06-09 (e)** — **Single Writer Pattern COMPLETE across all 4 core entities.** CompanyWriter migration finished (approve_discovery create routed through it); CatalystWriter built + company_enrichment catalyst writes migrated (contract-preserving drop-in); EdgeWriter built (entity_edges constraint-protected). Added `tests/run_all.py` (14 tests green). Direct-write audit: drugs/companies/catalysts all 0. Remaining: enforcement boundary (Kyle), then modularization (Phase 3) + frontend (Phase 4).
- **2026-06-09 (d)** — Phase 2 drug-writer migration COMPLETE (approve_discovery + molecule_enrichment + seed_tl1a_companies; write_meridian reads-only; zero direct drugs writes remain). Entered Phase 3: linked `efficacy_benchmarks`/`ailux_strategic_context` via new `drug_id` columns, refreshed the graph post-dedupe, authored `modularization_plan.md`. Next: continue writer migrations (Company/Edge/Catalyst) + execute script splits per plan; enforcement still awaits Kyle.
- **2026-06-09 (c)** — Phase 2 migration started: corrected the drug write-path inventory (drug_intake = reads only; `approve_discovery.py` = the real birth point; company_enrichment writes supporting tables, not `drugs`). **Migrated `approve_discovery.py` onto DrugWriter** — drug creation now resolves canonical identity first (fixes the slug-mismatch dup class at the source). Verified via dry-run (SL-325→sl325 reuse; new molecule mints clean slug). Next: migrate molecule_enrichment / seed_tl1a_companies / write_meridian, then enforcement.
- **2026-06-09 (b, overnight autonomous)** — **Phase 0.5 ✅** (Constitution, Lifecycle Map, Governance Table, ADR). **Phase 1**: root cleanup ✅ (40→3 root .py), CLAUDE.md slim ✅ (176→45), broken-collectors reviewed. **Phase 2 🔄**: shared `client.py` ✅, `DrugWriter` ✅ (live smoke-tested), regression suite ✅ 6/6; enforcement staged. **Phase 3**: source_documents + signals connectivity ✅. All committed. **Next:** Kyle reviews Open decisions → apply DrugWriter enforcement → migrate active drug write paths → then CompanyWriter. _(append future sessions here)_
