# scripts/

Pipeline entrypoints run by the GitHub Actions workflows in `.github/workflows/`.

> **Heads up (being actively reorganized):** this directory is a flat list today; it is
> being migrated into a proper package at `src/meridian/<domain>/` one group at a time.
> See `docs/architecture/REPO_LAYOUT.md` for the target structure and migration order.
> Until then, use the map below to navigate. New code should go in `src/meridian/`, and
> every DB write must go through the writers in `src/database/`.

## Map by domain

**Ingestion** — pull external data (ct.gov, openFDA, RSS, pubmed, patents, prices)
`abstract_fetcher` `api_harvester` `ct_gov_sync` `connect_ctgov_raw` `fetch_homepage_news` `collect_efficacy_apis` `collect_evidence` `collect_patient_evidence` `refresh_orange_purple_book` `stock_prices` `chunk_extract` `enrich_pub_stubs`

**Enrichment** — LLM + data enrichment of drugs/companies/molecules
`company_enrichment` `drug_enrichment` `molecule_enrichment` `deep_enrich_intel` `quick_profiles_enrich` `run_pkpd_claude` `drug_intelligence_researcher` `patient_population_agent` `payer_pricing_agent`

**Identity** — entity matching, intake, resolution, ontology
`drug_intake` `company_intake` `conversation_intake` `entity_matcher` `identity_resolution` `company_identity_resolver` `link_entities` `ontology_map_drugs` `approve_discovery` `process_queue_item` `human_queue_builder` `build_navigator_lookup`

**Graph** — entity_edges seeders + materializers (route writes through `EdgeWriter`)
`seed_competes_with` `seed_targets` `seed_target_edges` `seed_company_edges` `seed_partnership_edges` `seed_patient_edges` `seed_api_edges` `seed_preclinical_competitors` `materialize_structural_edges` `materialize_deal_edges` `build_fact_graph` `build_institution_intel` `project_patient_author_graph` `unify_graph` `derive_ownership_rights` `graph_health_guard`

**Scoring** — completeness / coverage / strategic / trust / foresight metrics
`acquisition_scorer` `compute_attribute_completeness` `compute_coverage` `compute_indication_priority` `compute_landscape_coverage` `compute_landscape_scores` `compute_patient_whitespace` `compute_strategic_value` `compute_trust_score` `rescore_completeness` `recompute_indication_priority` `portfolio_conflict_scorer` `score_foresight` `add_competitive_relevance` `write_ranking_snapshots` `seed_indication_priorities`

**Products** — the BD outputs (Meridian Issue, narratives, briefs, summaries)
`write_meridian` `narrative_gen` `generate_area_narratives` `generate_landscape_briefing` `generate_patient_briefs` `patient_narrative` `landscape_narrative` `strategic_brief` `bd_recommender` `morning_summary` `meridian_integrations_feed` `dryrun_meridian`

**Validation & governance** — consistency / conflict / source / integrity checks
`validate_ground_truth` `validation_research` `consistency_checker` `conflict_detector` `content_verifier` `source_verifier` `source_verify` `verify_sources` `verify_competitor_edges` `verify_publication_values` `company_validator` `audit_sources` `trial_id_audit` `identity_health_check` `reconcile_drug_integrity` `apply_governance_violations` `apply_entity_consistency_checks`

**Ops & monitoring**
`pipeline_health` `pipeline_monitor` `signal_monitor` `deploy_files` `model_comparison`

**Archive (one-off backfills/migrations — not on any schedule; → `scripts/archive/`)**
`backfill_*` `*_s36` `wave2b/2c/3_*` `one_time_migration` `apply_{drug_sources,prompt_improvements,sql}_migration` `migrate_drug_area_scores` `patch_stale_data` `seed_{kyle_reviews,data_sources,company_hq,competitive_signals,strategic_views,tl1a_companies}` `extract_fine_tune_signal` `flywheel_phase2` `weekend_sprint` `phase4_compare_legacy_vs_normalized` `catalog_backfill`

## Subdirectories
- `integrations/` — external-API edge projectors (manufacturing, author graph, patents)
- `maintenance/` — dedupe / audit / link tools (`dedupe_entities.py`, `graph_audit.py`)
- `migrations/` — legacy SQL (being consolidated into the top-level `migrations/`)

> **⚠ Accuracy note (verified 2026-06-16 via the GitHub API, the reliable source —
> the Cowork mount silently drops files in bulk greps, so on-mount analysis is NOT
> trustworthy for move-safety):** the AUTHORITATIVE set of **active** scripts is the
> **64 referenced by the 53 workflows**. Several entries that look like one-offs are
> actually workflow-wired and must NOT be archived/moved without updating their
> workflow: `weekend_sprint`, `flywheel_phase2`, `backfill_bd_angle`, `seed_data_sources`,
> `apply_sql_migration`, `apply_competitive_scores_v56`. Before archiving ANY script,
> confirm it is (a) not in the 64 workflow-referenced scripts AND (b) not imported by
> another script — using API-fetched content, not the mount.
