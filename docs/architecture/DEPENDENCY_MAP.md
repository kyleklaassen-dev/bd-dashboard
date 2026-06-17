# Codebase Dependency Map

Generated from a reliable snapshot of `main` (2026-06-16). The Cowork mount drops
files in bulk reads, so this is the trustworthy reference for what-relates-to-what.

## Pipeline DAG — which workflow runs which scripts (in order)

- **api-harvest-daily.yml** → api_harvester → enrich_pub_stubs → graph_health_guard → seed_api_edges
- **api-harvest.yml** → api_harvester → enrich_pub_stubs → graph_health_guard → seed_api_edges
- **atlas-refresh.yml** → compute_attribute_completeness → seed_data_sources
- **chunk_extract.yml** → chunk_extract → link_entities → materialize_structural_edges → ontology_map_drugs → seed_target_edges → unify_graph
- **company-enrichment.yml** → company_enrichment → ct_gov_sync → identity_health_check → research_intelligence → write_ranking_snapshots
- **evidence-collectors.yml** → collect_evidence → collect_patient_evidence
- **meridian-derived-rebuild.yml** → compute_attribute_completeness → derive_ownership_rights
- **meridian-free-ingest.yml** → compute_indication_priority → compute_patient_whitespace → sync_catalyst_calendar
- **meridian-graph-rebuild.yml** → build_institution_intel → project_patient_author_graph
- **refresh-company-verified.yml** → company_validator → refresh_company_verified
- **school-week-sprint.yml** → apply_competitive_scores_v56 → company_enrichment → compute_coverage → ct_gov_sync → drug_intelligence_researcher → molecule_enrichment → validate_ground_truth → write_ranking_snapshots
- **validation-research.yml** → conflict_detector → validation_research

_Plus 36 single-script workflows (one workflow, one entrypoint)._

## Shared utility modules (imported by other scripts — move these FIRST in any package migration, and update every importer)

- `build_fact_graph` ← imported by: link_entities
- `company_identity_resolver` ← imported by: catalog_backfill, company_intake, drug_intake, research
- `company_intake` ← imported by: approve_discovery
- `entity_matcher` ← imported by: build_fact_graph, link_entities
- `identity_resolution` ← imported by: company_enrichment, ct_gov_sync, one_time_migration
- `meridian_integrations_feed` ← imported by: dryrun_meridian, write_meridian
- `model_comparison` ← imported by: company_enrichment, drug_enrichment
- `narrative_gen` ← imported by: collect_evidence, generate_area_narratives, generate_patient_briefs, landscape_narrative, patient_narrative, reconcile_drug_integrity, seed_company_edges, seed_partnership_edges, seed_patient_edges, strategic_brief, verify_publication_values

## Import coupling (every script that imports a sibling — these import lines change on a move)

- `approve_discovery` → imports `company_intake`, `company_writer`, `drug_writer`
- `build_fact_graph` → imports `entity_matcher`
- `catalog_backfill` → imports `company_identity_resolver`
- `collect_evidence` → imports `narrative_gen`
- `company_enrichment` → imports `catalyst_writer`, `identity_resolution`, `model_comparison`
- `company_intake` → imports `company_identity_resolver`
- `ct_gov_sync` → imports `identity_resolution`
- `drug_enrichment` → imports `model_comparison`
- `drug_intake` → imports `company_identity_resolver`
- `dryrun_meridian` → imports `meridian_integrations_feed`, `write_meridian`
- `generate_area_narratives` → imports `narrative_gen`
- `generate_patient_briefs` → imports `narrative_gen`
- `landscape_narrative` → imports `narrative_gen`
- `link_entities` → imports `build_fact_graph`, `entity_matcher`
- `molecule_enrichment` → imports `drug_writer`
- `one_time_migration` → imports `identity_resolution`
- `patient_narrative` → imports `narrative_gen`
- `reconcile_drug_integrity` → imports `narrative_gen`
- `research` → imports `company_identity_resolver`, `source_verifier`
- `seed_company_edges` → imports `narrative_gen`
- `seed_partnership_edges` → imports `narrative_gen`
- `seed_patient_edges` → imports `narrative_gen`
- `seed_tl1a_companies` → imports `company_writer`, `drug_writer`
- `strategic_brief` → imports `narrative_gen`
- `verify_publication_values` → imports `narrative_gen`
- `write_meridian` → imports `meridian_integrations_feed`

## Classification
- **Active** (run by a workflow): 63 scripts — never archive these.
- **Utility** (imported, not directly run): 8 — `build_fact_graph`, `company_identity_resolver`, `company_intake`, `entity_matcher`, `identity_resolution`, `meridian_integrations_feed`, `model_comparison`, `narrative_gen`.
- **Archived 2026-06-16** (one-off backfills/migrations → `scripts/archive/`): 17.
- **Manual/on-demand tools** (the rest): not scheduled, not imported — kept in `scripts/` for now; categorize into `src/meridian/<domain>/` during the package migration (see REPO_LAYOUT.md).