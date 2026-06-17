# Repository Layout & Reorganization Plan

**Goal:** make this repo read like a standard, human-maintained Python project — clear
package boundaries, small focused files, predictable naming — without breaking the 53
live GitHub Actions workflows that wire the scripts together.

**Hard reality (why this is incremental, not a big-bang move):** the 135 flat files in
`scripts/` are referenced by 53 workflows (`run: python scripts/X.py`) and import each
other as siblings (flat `scripts/` on `sys.path`). Moving any file breaks its workflow
path AND every sibling import unless both are updated in the same change and verified by
re-running the workflow. So this is executed **one cohesive group at a time, each gated
by a green workflow run.** Reversible via git.

---

## 1. Current state (2026-06-16 inventory)
- **Security: clean** — `.env`, `.supabase_*`, `.anthropic_api_key`, `.github_token_workflow` are all gitignored (verified 404 on `main`). Never commit secrets.
- `scripts/` — **135 flat `.py` files** (53 over 400 lines), plus `integrations/`, `maintenance/`, `migrations/` subdirs. The flat dump is the #1 legibility problem.
- `index.html` — **34,847 lines** (Phase 4; its own plan).
- **Two migration dirs**: `migrations/` (61) and `scripts/migrations/` (13, referenced by seed_competes_with / seed_targets / source_verifier). Consolidate to one.
- **Root clutter**: 13 HTML dashboards + 5 loose docs at root. (HTML is GitHub-Pages-served, so URLs must be preserved — these move only with a Pages config + link update, low priority.)
- `src/` — only `database/` populated (the 4 governed writers). The bulk of logic still lives in `scripts/`.

## 2. Target layout (standard Python project)
```
bd-dashboard/
├── README.md  CLAUDE.md  PRIORITY.md  NEXT_SESSION.md      # entrypoints stay at root
├── pyproject.toml                                          # ADD: deps + tool config (replaces scattered requirements)
├── src/meridian/                # the application package (importable: `from meridian.x import y`)
│   ├── database/                # ← already here (client + drug/company/edge/catalyst writers)
│   ├── ingestion/               # external fetch/sync (ct.gov, openFDA, RSS, pubmed, patents)
│   ├── enrichment/              # LLM + data enrichment (company/drug/molecule/pkpd)
│   ├── identity/                # entity matching, intake, resolution, ontology
│   ├── graph/                   # entity_edges seeders + materializers + graph health
│   ├── scoring/                 # completeness/coverage/strategic/trust/foresight scores
│   ├── products/                # the BD outputs (meridian issue, narratives, briefs, summary)
│   └── validation/              # consistency/conflict/source/governance checks
├── scripts/                     # THIN CLI entrypoints only (argparse → call into meridian.*)
│   └── archive/                 # one-off backfills/migrations kept for history, not run
├── web/                         # the dashboards (index.html + *.html) — needs Pages config
├── migrations/                  # ALL .sql migrations (merge scripts/migrations/ in)
├── tests/
├── docs/
└── .github/workflows/
```

## 3. Naming conventions
- Modules/files: `snake_case.py`, one clear responsibility, **≤ ~300–400 lines** (split beyond that — see §5).
- Rename the PascalCase dashboards (`Meridian_Coverage.html` → `meridian_coverage.html`) when `web/` is created (with a redirect/link sweep).
- No `apply_*` / `one_time_*` / `wave*_*` scripts in the live tree — those are one-offs → `scripts/archive/`.

## 4. `scripts/` categorization (the move map — also the current navigation guide in `scripts/README.md`)
- **ingestion →** abstract_fetcher, api_harvester, ct_gov_sync, connect_ctgov_raw, fetch_homepage_news, collect_efficacy_apis, collect_evidence, collect_patient_evidence, refresh_orange_purple_book, stock_prices, chunk_extract, enrich_pub_stubs
- **enrichment →** company_enrichment, drug_enrichment, molecule_enrichment, deep_enrich_intel, quick_profiles_enrich, run_pkpd_claude, drug_intelligence_researcher, patient_population_agent, payer_pricing_agent
- **identity →** drug_intake, company_intake, conversation_intake, entity_matcher, identity_resolution, company_identity_resolver, link_entities, ontology_map_drugs, approve_discovery, process_queue_item, human_queue_builder, build_navigator_lookup
- **graph →** seed_{competes_with,targets,target_edges,company_edges,partnership_edges,patient_edges,api_edges,preclinical_competitors}, materialize_{structural,deal}_edges, build_fact_graph, build_institution_intel, project_patient_author_graph, unify_graph, derive_ownership_rights, graph_health_guard
- **scoring →** acquisition_scorer, compute_{attribute_completeness,coverage,indication_priority,landscape_coverage,landscape_scores,patient_whitespace,strategic_value,trust_score}, rescore_completeness, recompute_indication_priority, portfolio_conflict_scorer, score_foresight, add_competitive_relevance, write_ranking_snapshots, seed_indication_priorities
- **products →** write_meridian, narrative_gen, generate_area_narratives, generate_landscape_briefing, generate_patient_briefs, patient_narrative, landscape_narrative, strategic_brief, bd_recommender, morning_summary, meridian_integrations_feed, dryrun_meridian
- **validation →** validate_ground_truth, validation_research, consistency_checker, conflict_detector, content_verifier, source_verifier, source_verify, verify_{sources,competitor_edges,publication_values}, company_validator, audit_sources, trial_id_audit, identity_health_check, reconcile_drug_integrity, apply_governance_violations, apply_entity_consistency_checks
- **ops →** pipeline_health, pipeline_monitor, signal_monitor, deploy_files, model_comparison
- **archive (one-offs — do not run) →** backfill_*, *_s36, wave2b/2c/3_*, one_time_migration, apply_{drug_sources,prompt_improvements,sql}_migration, migrate_drug_area_scores, patch_stale_data, seed_{kyle_reviews,data_sources,company_hq,competitive_signals,strategic_views,tl1a_companies}, extract_fine_tune_signal, flywheel_phase2, weekend_sprint, phase4_compare_legacy_vs_normalized, catalog_backfill

## 5. Large-file split targets (smaller files = humans can manage them)
Per-script splits follow `docs/architecture/modularization_plan.md` + `PHASE3_4_EXECUTION_DESIGN.md`:
company_enrichment.py (4,435) · weekend_sprint.py (2,999, likely archive) · write_meridian.py (2,391) · drug_intake.py (1,659) · research.py (1,538) · ct_gov_sync.py (1,409) · research_intelligence.py (1,379) · company_intake.py (1,185) · narrative_gen.py (1,123) · acquisition_scorer.py (1,091). And **index.html (34,847)** = Phase 4 (extract self-contained JS modules to `/assets/js/*.js`, one per PR, page-load-verified).

## 6. Safe migration sequence (each step = move + update workflow paths + update imports + dispatch the affected workflow → must stay green; one PR each)
1. **Foundations (no moves):** add `pyproject.toml`; add `src/meridian/__init__.py` + subpackage `__init__.py`; add `scripts/README.md` (done — the §4 map).
2. **graph/** group first (cohesive; the seeders we just hardened/wired). Move into `src/meridian/graph/`, keep thin `scripts/` CLIs, route writes through EdgeWriter. Verify: structural-edges, deal-edges, verify-edges runs green.
3. **scoring/**, then **ingestion/**, then **validation/**, then **products/**, then **enrichment/** (biggest, last). One group per PR.
4. **migrations/** consolidation: move `scripts/migrations/*.sql` → `migrations/`, update the 3 referencing scripts' relative paths.
5. **archive/**: move one-off scripts to `scripts/archive/` (none are workflow-wired — low risk).
6. **web/** + HTML rename: only after a GitHub Pages path/redirect plan (preserve URLs).
7. **index.html** Phase 4 extractions, last.

## 7. Standing rules
- New code goes in `src/meridian/<domain>/`, not flat `scripts/`.
- One responsibility per module; split at ~300–400 lines.
- Every DB write goes through `src/database` writers.
- A move isn't done until the workflow that exercises it runs green.

> **⚠ Accuracy note (verified 2026-06-16 via the GitHub API, the reliable source —
> the Cowork mount silently drops files in bulk greps, so on-mount analysis is NOT
> trustworthy for move-safety):** the AUTHORITATIVE set of **active** scripts is the
> **64 referenced by the 53 workflows**. Several entries that look like one-offs are
> actually workflow-wired and must NOT be archived/moved without updating their
> workflow: `weekend_sprint`, `flywheel_phase2`, `backfill_bd_angle`, `seed_data_sources`,
> `apply_sql_migration`, `apply_competitive_scores_v56`. Before archiving ANY script,
> confirm it is (a) not in the 64 workflow-referenced scripts AND (b) not imported by
> another script — using API-fetched content, not the mount.
