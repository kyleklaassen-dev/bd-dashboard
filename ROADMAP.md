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

## ⭐ Strategic reframe (2026-06-18) — are we improving the repo's VALUE?
The §3 splits (9 files, ≥1000-line bucket 9→1) genuinely improved **maintainability** — Kyle's north-star metric #4,
and a real onboarding/bug-surface win. But they were **byte-identical by design → zero behavior change**, so they did
NOT move the *product* value (intelligence accuracy, the dashboard, decision surfacing). Necessary, not sufficient.
**The gaps that actually cap value (now tracked as §B–§E below):**
- **§B No automated safety net (biggest gap).** 3 test files / 131 modules, and *nothing* ran in CI — a PR could break
  the 4am pipeline and nothing caught it until the unattended run failed. The splits made ~40 modules unit-testable but
  that dividend was uncashed. **Started 2026-06-18:** added `ci-quality-gate.yml` (compile + unit tests + health-no-cycles
  + hygiene + live writer tests) and the first characterization tests (`tests/unit/`). This is the "production-grade /
  any-engineer-can-step-in" enabler — a green check now *means* something.
- **§C Intelligence quality is the actual product, and structure doesn't move it.** ✅ **Scoreboard built 2026-06-18**
  (`scripts/maintenance/intelligence_quality.py`) — validation pass-rate, governance, completeness tiers, source
  coverage, freshness, volume. First run surfaced real work: **38 unresolved governance violations** (mostly
  `trial_misattributed_*`), **115/181 drugs untiered** (completeness never computed), **42 orphan source drug_ids**
  (drug_sources citing non-existent drugs), 17 null source_urls. **Acted 2026-06-18:** ✅ governance **38 → 0** — all `trial_misattributed_*` violations CT.gov-verified and resolved
  (15 stale + 20 wrong links deleted + 3 false-positives kept; reversible backup in `docs/audits/backups/`). NEXT §C work:
  tier the 115 untiered drugs (run the completeness scorer — non-destructive); revisit source coverage; weekly scoreboard +
  trend tracking. This is where repo work converts to BD value.
- **§D The dashboard (index.html, 34k lines) — the surface users actually use — is untouched** (§4/§A.2). Highest product
  leverage, highest risk; needs browser-verify (recipe ready).
- **§E Real dedup/clarity debt:** 17 entity-resolution implementations (converge on `entity_matcher`, metric #3);
  `weekend_sprint` duplicates `company_enrichment`/`compute_coverage`/`source_verifier`/`bd_recommender` logic;
  51 workflows (operational surface — observability + consolidation candidates). Plus: module-level `os.environ[...]`
  credential reads at import block clean unit-testing (make them lazy → cashes more of the testability dividend).

## Now / Next (the short list)
0. 🟡 **§B safety net** — CI quality gate + first unit tests landed (2026-06-18). NEXT: grow characterization tests over the
   split pure modules (scoring dims, `build_step5_prompt`, `parse_*`); make credential reads lazy so modules import test-clean.
1. ✅ **One clear data-write path** (§A.1, 2026-06-17) — DONE at code layer; all 4 core tables route pipeline writes through their Writer (scoreboard ✓). Dashboard-feature freeze can lift re: write integrity. Next correctness work: §A.2 UI/logic split, §A.4 audit, §A.5 edge-case tests.
2. ✅ **Package migration structurally COMPLETE** (§1, 2026-06-17) — `src/` is one unified `meridian` package (incl. writers→`src/meridian/database/`, narrative cluster, enrichment-core). Tail: a few LLM stragglers; most remaining flat scripts are manual tools + `weekend_sprint`.
3. ⬜ **Decompose `weekend_sprint`** into proper homes, then retire it (§2).
4. ⬜ **Large-file splits** — `company_enrichment` (4,437), `write_meridian` (2,391), others (§3).
5. ⬜ **`index.html` Phase 4** decomposition (§4) — also separates UI from intelligence logic (§A.2).
6. ✅ **`web/` reorg DONE** (§5) — 13 static dashboards → `web/`, root HTML 15→2; 4 secondary docs → `docs/`.
7. ⬜ **Drift guardrails** wired as a recurring check (§6).

---

## A. Product architecture — the correctness spine (strategic frame, 2026-06-17)
**The package migration gave Meridian a legible skeleton; this is the discipline that goes on top.**
The goal: make the *wrong thing impossible*, not just organized. These are the product-architecture
guarantees (and they restate `STABILIZATION_PLAN.md` / `constitution.md` as a crisp priority order).

**🔑 Gating question: _Can ONE approved path create or modify a drug record from ingestion → database → dashboard?_**
**Now essentially YES at the CODE layer** (2026-06-17): all 4 core tables route pipeline writes through their
Writer — scoreboard `drugs/companies/entity_edges/catalysts` all ✓. The earlier "NO" overstated the gap (the metric
counted reads as writes; fixed). The one remaining non-writer is `dedupe_entities` — an approval-gated FK-aware
**merge** tool (not a pipeline path; merges already need Kyle's approval per CLAUDE.md), recognized as the maintenance exception.

1. ✅ **One clear data-write path** — DONE at the code layer (2026-06-17). Routed: `execute_intel_actions`
   (drugs/companies/catalysts creates), all 6 `entity_edges` seeders → EdgeWriter, `research` catalyst create +
   `write_meridian` catalyst-resolve → CatalystWriter, `verify_sources`+`stock_prices` narrow patches → Drug/Company
   `update_fields`. Writer tests 8/0+6/0 throughout. **Remaining (lower priority):**
   - `dedupe_entities` merge tool — keep as the audited maintenance exception (or add a writer `merge()` later).
   - Consider DB-layer hardening (extend v161 REVOKE so service_role-bypass can't re-introduce raw writes) — optional.
   - **Top target (DONE): `execute_intel_actions`** — was raw-creating drugs + companies + catalysts.
   - **entity_edges (6):** route the edge seeders (`seed_target_edges`/`seed_targets`/`unify_graph`/`seed_api_edges`/`connect_ctgov_raw`/`company_intake`) through `EdgeWriter` (seed_competes_with already does).
   - **catalysts:** `research`, `write_meridian` (PATCH) → CatalystWriter.
   - **Narrow field-patches** (lower risk): `verify_sources` (data_confidence), `stock_prices` (price) → through writers or an allow-listed patch path.
   - **`dedupe_entities`** (FK-aware maintenance) — decide: route through writers or keep as an explicit, audited maintenance exception.
   *Note:* `drug_intake`/`company_intake`/`write_meridian` only READ drugs (earlier "raw writer" claim was the metric bug). Gate every change with `tests/database/`.
2. 🟡 **Separate UI from intelligence logic** — `index.html` currently decides (`_resolveStage`, `_score`, `_dedup`,
   `canonical` ×61, `partnership_verified` writes). Move identity/scoring/stage rules server-side; the dashboard displays trusted data. (overlaps §4)
3. 🟡 **Define canonical entities** — one source of truth per entity (drugs/companies/trials/mechanisms/deals/catalysts);
   converge the 22 ad-hoc resolvers onto `entity_matcher`.
4. ✅ **Audit logs** — DONE (2026-06-17). `field_change_audit` (v63) + **v163** now cover all 4 core tables on
   INSERT+UPDATE; Writers send `X-Meridian-Actor`/`X-Meridian-Reason` headers → audit captures WHO (the writer) + WHY.
   Verified end-to-end (CatalystWriter write → changed_by="CatalystWriter"). Error-swallowing — never blocks a write.
5. ✅ **Tests around known edge cases** — DONE (`tests/database/test_edge_cases.py`, 9/9): tulisokibart=MK-7240
   canonical identity (originator=Prometheus, not Merck), VTX002/Ventyx, Roche/Telavant acquisition modeling,
   LBL-053 TL1A bispecific. (HLX36 not in DB — unresolved flag; covered LBL-053 instead.)
6. 🟢 **Lifecycle map** — `docs/architecture/drug_lifecycle.md` exists; refresh to true current state (ingestion→enrich→dashboard→update).

**Sequence:** A.1 first (unblocks the gating question) → A.4 audit on the now-single path → A.3 canonical convergence →
A.2 UI/logic split (with §4) → A.5 tests → A.6 doc refresh. A.1 also completes stabilization Stage 4.

---

## 1. Package migration — remaining (`scripts/` → `src/meridian/<domain>/`)
**Done so far (49 scripts, 0 engine failures):** graph/9 · scoring/7 · ingestion/12 · validation/9 ·
products/3 · enrichment/2 · ops/3 · identity/4. Plus 5 deletions + `payer_pricing_agent` wired into free-ingest.
Method documented in `docs/architecture/REPO_LAYOUT.md` §6.

**PROGRESS (freeze lifted → dispatch-verified):** moved the **write_meridian cluster** (write_meridian + meridian_integrations_feed + dryrun_meridian → products/, meridian-preview dry-run GREEN), the 3 LLM leaves (execute_intel_actions→products, process_queue_item + review_submitted_intel→identity; fixed a pre-existing None-slice bug), and **research_intelligence** → scoring/. ~58 flat scripts remain.

**🧭 LEARNING — switch the last two webs to package imports.** The remaining two clusters are *densely* cross-coupled and span multiple packages, so the own-dir `sys.path.insert(dirname(__file__))` + sibling-import trick (great for the first ~55 scripts) now produces fragile, many-file commits. **Recommended next step before moving them:** make `meridian` a real importable package — add `PYTHONPATH=$GITHUB_WORKSPACE/src` (job-level `env:`) to the workflows (or a `pyproject.toml` + `pip install -e .`), convert the writers' + cross-package imports to `from meridian.<domain>.<mod> import ...`, then the two webs move cleanly with no sys.path redirects. Verify with the writer tests + a dry-run dispatch.

  - **narrative web (12 files, 4 domains):** `narrative_gen` (lib) + its product consumers (generate_area_narratives, generate_patient_briefs, landscape_narrative, patient_narrative, strategic_brief) → products/; collect_evidence → ingestion/; seed_company/partnership/patient_edges → graph/; reconcile_drug_integrity + verify_publication_values → validation/. All 11 import `narrative_gen` via own-dir sibling import → redirect once package imports land.
  - **enrichment-core web (8 files):** company_enrichment(4435) + ct_gov_sync(1409) + company_intake(1185) + identity_resolution + model_comparison + company_identity_resolver + source_verifier + research(1538). Mutual coupling: research→{company_identity_resolver, source_verifier}; company_enrichment→{identity_resolution, model_comparison}; ct_gov_sync→identity_resolution; company_intake→company_identity_resolver. Move together once package imports land. Several are also large-file-split targets (§3) — split during the move.

**Remaining = the LLM-core clusters.** Move each as ONE atomic commit (move members + update EVERY importer +
update all workflows read from `main` + `__init__.py`), then **dispatch-verify** the workflow green (freeze off).
Always run the full-repo importer sweep first — the depmap misses `src/database/`, `scripts/maintenance/`, and dynloads.

- ⬜ **write_meridian cluster** → `products/`: `write_meridian` (2,391) + `meridian_integrations_feed` + `dryrun_meridian`.
  ⚠️ `research.py` **dynloads** `write_meridian` — move/redirect together. Verify via `meridian-preview` (built-in dry run) + `meridian-write`.
- ✅ **research cluster**: `research` (1,538) → `ingestion/` (2026-06-17, meridian-research dispatch ran past startup); `research_intelligence` (1,379) → `scoring/` (prior session).
- ✅ **enrichment-core cluster** DONE (2026-06-17): `company_enrichment` (4,437) → `enrichment/` (fixed parents[1]→[3] + _HINTS_PATH depth; repointed 11 workflow lines + weekend_sprint B2 subprocess); `ct_gov_sync` (1,409) → `ingestion/`; `company_intake` (1,185) → `identity/`; leaf libs (identity_resolution, model_comparison, company_identity_resolver, source_verifier) done prior session. Writer tests green; also fixed a stray `.gitignore` `enrichment/` pattern that was ignoring the package.
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
Per `docs/architecture/modularization_plan.md` + `PHASE3_4_EXECUTION_DESIGN.md`. Thin CLI + focused modules.
- ✅ `company_enrichment.py` (4,377 → **937** + 11 modules `src/meridian/enrichment/company/`) — DONE 2026-06-17.
- ✅ `write_meridian.py` (2,387 → **435** + 9 modules `src/meridian/products/issue/`) — DONE 2026-06-17.
- ✅ `ct_gov_sync.py` (1,409 → **691** + 5 modules `src/meridian/ingestion/ctgov/`, fetch/map/validate/write) — DONE 2026-06-17.
  All three: byte-identical / AST-guided / writer-test-gated; branch `refactor/section3-company-enrichment-prompts` (not yet pushed).
  Deferred (supervised): route the `sb_*` raw writes in each `common.py` → the `src/meridian/database` writers via watched `--dry-run`.
- ✅ `research.py` (1,539→913 + `ingestion/research_pipeline/` {common,pkpd,monitors}) — DONE 2026-06-17.
- ✅ `research_intelligence.py` (1,379→413 + `scoring/research_intel/` {common,context,scoring,triggers,queue}) — DONE.
- ✅ `company_intake.py` (1,180→504 + `identity/intake/` {common,research,queue,edges}) — DONE (preserved external `write_active_in_edge` surface).
- ✅ `narrative_gen.py` (1,123→405 + `products/narrative/` {common,atoms,triangulate}) — DONE (preserved 3-importer surface; fixed a WORKSPACE depth bug).
- ✅ `drug_intake.py` (1,627→456) — migrated `scripts/`→`ingestion/` + `ingestion/drugintake/` {common,research,scoring,queue}. DONE.
- ✅ `acquisition_scorer.py` (1,091→197) — migrated `scripts/`→`scoring/` + `scoring/acquisition/` {common,data,scoring,write}; fixed dead-token bug. DONE.
- **All 9 splittable large files DONE — ≥1000-line bucket 9 → 1.** Remaining: `weekend_sprint.py` (3,001) = §2
  (decompose the active scheduled orchestrator to *call into* the extracted modules; not a clean §3 split — supervised).

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
