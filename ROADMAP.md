# Meridian — ROADMAP / Single Source of Future Work

**This file is the one place all planned work lives.** If a task isn't here, it's at risk of being
lost — so put it here. `PRIORITY.md` = what's active *right now*; `NEXT_SESSION.md` = the last
session's handoff; **this file = everything still to do, by theme, with enough context to pick it up cold.**

Last updated: 2026-06-16. Status legend: ⬜ not started · 🟡 in progress · ✅ done (kept briefly, then pruned).

---

## 0. How to use this file
- Start a work session by reading `START_HERE.md` (the reading guide), then this file's **Now / Next**.
- When you finish something, check it off and pull the next item into **Now**.
- When you discover new work mid-task, add it here immediately (don't rely on memory or a code comment).
- Keep items **outcome-phrased** and **self-contained** (a future reader has no memory of today).

## Now / Next (the short list)
1. 🟡 **Finish the package migration — LLM-core clusters** (§1). Freeze is OFF → each move is dispatch-verified.
2. ⬜ **Decompose `weekend_sprint`** into proper homes, then retire it (§2).
3. ⬜ **Large-file splits** — `company_enrichment` (4,435), `write_meridian` (2,391), others (§3).
4. ⬜ **`index.html` Phase 4** decomposition (§4).
5. ⬜ **Drift guardrails** wired as a recurring check (§6).

---

## 1. Package migration — remaining (`scripts/` → `src/meridian/<domain>/`)
**Done so far (49 scripts, 0 engine failures):** graph/9 · scoring/7 · ingestion/12 · validation/9 ·
products/3 · enrichment/2 · ops/3 · identity/4. Plus 5 deletions + `payer_pricing_agent` wired into free-ingest.
Method documented in `docs/architecture/REPO_LAYOUT.md` §6.

**Remaining = the LLM-core clusters.** Move each as ONE atomic commit (move members + update EVERY importer +
update all workflows read from `main` + `__init__.py`), then **dispatch-verify** the workflow green (freeze off).
Always run the full-repo importer sweep first — the depmap misses `src/database/`, `scripts/maintenance/`, and dynloads.

- ⬜ **write_meridian cluster** → `products/`: `write_meridian` (2,391) + `meridian_integrations_feed` + `dryrun_meridian`.
  ⚠️ `research.py` **dynloads** `write_meridian` — move/redirect together. Verify via `meridian-preview` (built-in dry run) + `meridian-write`.
- ⬜ **research cluster**: `research` (1,538) + `research_intelligence` (1,379). Verify via `meridian-research` + `research-intelligence` dispatch.
- ⬜ **enrichment-core cluster** → `enrichment/` + `identity/`: `company_enrichment` (4,435) + `ct_gov_sync` (1,409) + `company_intake` (1,185) + `identity_resolution` + `model_comparison` + `company_identity_resolver` + `source_verifier`. Verify via `company-enrichment` dispatch + writer tests.
- ⬜ **narrative cluster** → `products/`: `narrative_gen` (1,123) + `collect_evidence` + `generate_area_narratives` + `generate_patient_briefs`. Verify via `narrative-generation` / `patient-briefs` / `evidence-collectors`.
- ⬜ **LLM stragglers**: `execute_intel_actions`, `process_queue_item` → `identity/`, `review_submitted_intel`. Verify each via its workflow.
- ⬜ **writers + database consolidation**: move `src/database/` (`client`, `drug_writer`, `company_writer`, `edge_writer`, `catalyst_writer`) → `src/meridian/database/`, bring `apply_sql_migration` with them. Touches every writer importer — run `tests/database/` after.

**Regression gate (every migration touching writers/identity):** run `tests/database/test_drug_writer.py` +
`test_writers.py` (live, read-only). They are NOT on a workflow — see guardrails §6 (wire into CI).

## 2. Decompose `weekend_sprint` (2,999-line legacy umbrella), then retire it
Old 56-phase Saturday orchestrator. Most phases re-run scripts that now have their own workflows. **But 9
functions are scheduled NOWHERE else** — retiring it blind takes them dark. Give each a proper home (its own
small workflow or a fold into an existing domain workflow), then archive `weekend_sprint` + `drug_enrichment`.

Still-needed-but-only-here (verify each, then rehome):
- ⬜ `build_navigator_lookup` — rebuilds `navigator_lookup.json` + deploys to Pages (dashboard search).
- ⬜ `update_area_knowledge_counts` — refreshes `area_knowledge` drug counts (live dashboard).
- ⬜ `seed_indication_priorities` — recompute indication ranks (reconcile with free-ingest's `compute_indication_priority`).
- ⬜ `seed_strategic_views` — strategic views refresh.
- ⬜ `coverage_gap_finder` · `consistency_checker` · `human_queue_builder` — QA / review-queue agents.
- ⬜ `patch_competitive_scores_null` — backfill null competitive scores.
- ⬜ `drug_enrichment` — drug-centric enrichment (keep wired, or merge into company/molecule enrichment).
Already covered elsewhere (weekend_sprint just duplicates): `company_enrichment`, `compute_coverage`, `source_verifier`, `bd_recommender`.

**Bonus:** the 56-phase list is a good seed for the comprehensive periodic QA/refresh checklist (guardrails §6).

## 3. Large-file splits (smaller files = humans + Claude can manage them)
Per `docs/architecture/modularization_plan.md` + `PHASE3_4_EXECUTION_DESIGN.md`. Thin CLI + focused modules ≤ ~300–400 lines.
- ⬜ `company_enrichment.py` (4,435) — do during its migration (§1).
- ⬜ `write_meridian.py` (2,391) — do during its migration (§1).
- ⬜ `drug_intake.py` (1,659) · `research.py` (1,538) · `ct_gov_sync.py` (1,409, fetch/map/write split designed) · `research_intelligence.py` (1,379) · `company_intake.py` (1,185) · `narrative_gen.py` (1,123) · `acquisition_scorer.py` (1,091, manual).

## 4. `index.html` (34,847 lines) — Phase 4 decomposition
Per `docs/architecture/INDEX_HTML_MAP.md` + `INDEX_HTML_DECOMPOSITION_PLAN.md`. Extract self-contained JS modules
to `web/assets/js/*.js`, one per PR, page-load-verified. Lowest-priority, highest-risk; do last.

## 5. `web/` + HTML reorganization (preserve GitHub Pages URLs)
- ⬜ Move the 13 root `*.html` dashboards into `web/`, rename PascalCase → snake_case
  (`Meridian_Coverage.html` → `meridian_coverage.html`), with a Pages config + a link/redirect sweep so URLs don't break.

## 6. Drift guardrails (keep it organized over time)
The repo must not silently regress to a flat dump. Build a lightweight recurring check:
- ⬜ **`scripts`-hygiene CI check** (small workflow + script): warn/fail if a new top-level `scripts/*.py` is added
  outside `archive/` (new code belongs in `src/meridian/`), if a workflow references a non-existent path, or if a
  `src/meridian/**` module is imported by nothing and wired to no workflow (orphan).
- ⬜ **Wire the writer regression tests into CI** (`tests/database/`) so writer/identity changes are gated automatically.
- ⬜ **Periodic comprehensive review** (monthly): run the QA/refresh checklist (seeded from weekend_sprint's phases) —
  schema health, governance violations, dup/stale detection, coverage recompute, orphan-workflow scan → short report.
- ⬜ Keep `docs/architecture/DEPENDENCY_MAP.md` + `REPO_LAYOUT.md` current as part of any structural change.

## 7. Schema/data cleanup (from `docs/audits/SCHEMA_CLEANUP_BACKLOG.md`)
- ⬜ **Tier B** (empty + a script writes → revive collector or retire both): `china_trials`, `patent_families`,
  `trial_identity`, `drug_stage_history`, `source_collection_gaps`, `correction_labels`, `model_validation_results`,
  `fine_tune_dataset`, `target_areas`, `trajectory_summary`, narrative_* (3).
- ⬜ **Tier C** (empty but read by the dashboard → POPULATE, don't drop): `company_areas`, `company_profiles`,
  `drug_modalities`, `intel_areas`, `intel_companies`, `indication_biology_tags`, `drug_routes`, `drug_areas` (legacy).

## 7b. Reconcile (found by the hygiene guardrail 2026-06-16)
- ⬜ **Competitive scoring updater**: `school-week-sprint` called `apply_competitive_scores_v56.py` (deleted one-off,
  masked by `continue-on-error`). Removed the dead line. CONFIRM `drug_competitive_scores` still has a live updater
  (e.g. `compute_landscape_scores` / `drug_competitive_scores` path) or wire one — otherwise that score may be going stale.
- ✅ Deleted dead workflow `backfill-ailux-angle-watch.yml` (script never existed, zero runs).

## 8. Cosmetic / housekeeping
- ✅ Docstring usage-paths synced across all 49 moved modules (commit ba367813).
- ⬜ Fold the older `PRIORITY.md` / `NEXT_SESSION.md` fragments into this file as they age out, so this stays the single source.
