# Migrations

All Supabase DDL lives under this directory. Moving or renaming files here does **not** affect the live database — only running SQL in Supabase does.

## Layout

| Folder | Purpose |
|---|---|
| `migrations/` (this level) | Numbered schema migrations (`v10`–`v82`) in apply order |
| `legacy/` | Early `schema_migration_v*` files and renamed version collisions |
| `maintenance/` | One-off data fixes, purges, trigger patches (not schema evolution) |
| `checks/` | Validation and consistency SQL (run on demand, not migrations) |

Reference DDL (not versioned migrations): `docs/ddl/`  
New migration template: `docs/migration_template.sql`

## Apply a migration

```bash
# Via Management API (preferred in CI)
python3 scripts/apply_sql_migration.py migrations/v78_whitespace_views.sql

# Or paste file contents into Supabase SQL Editor
```

Helper scripts with baked-in paths:

- `scripts/apply_governance_violations.py` → `legacy/schema_migration_governance_v1.sql`
- `scripts/apply_entity_consistency_checks.py` → `checks/entity_consistency_checks_v1.sql`
- `scripts/apply_drug_sources_migration.py` → `v37_drug_sources.sql`
- `scripts/seed_targets.py --apply-migration` → `v27_targets.sql`
- `scripts/seed_competes_with.py --apply-migration` → `v26_entity_edges.sql`

## Numbered migrations (v10+)

| File | Summary |
|---|---|
| `v10_relationship_fields.sql` | Company relationship fields for enrichment |
| `v14_catalyst_unique_index.sql` | Catalyst dedup index |
| `v17_validation_tests_unique_name.sql` | Unique constraint on validation test names |
| `v25_ownership_edges.sql` | Ownership edge predicates |
| `v26_entity_edges.sql` | `entity_edges` graph table |
| `v27_targets.sql` | `targets` table + drug_targets junction |
| `v28_ownership_edges_deal_id.sql` | Deal FK on ownership edges |
| `v29_active_in_edges.sql` | ACTIVE_IN edges |
| `v30_coverage_scores.sql` | Coverage scoring table |
| `v32_coverage_diagnostics.sql` | Coverage diagnostics DDL |
| `v32_source_verifications.sql` | URL health tracking |
| `v33_competitive_signals.sql` | Competitive signals table |
| `v37_drug_sources.sql` | Drug source provenance |
| `v43_next_gen_rankings.sql` | Next-gen ranking support |
| `v59_company_documents.sql` | Company documents |
| `v59_trajectory_sop_framework.sql` | Trajectory SOP framework |
| `v59b_fix_trigger_run_id.sql` | Trigger run_id fix |
| `v60_p1_provenance_columns.sql` | Provenance columns (p1) |
| `v60_trajectory_quality.sql` | Trajectory quality |
| `v61_p0_core_tables.sql` | P0 core tables |
| `v61_anti_drift_triggers.sql` | `schema_change_log` + field capture triggers |
| `v62_agent_validation_tables.sql` | Agent validation tables |
| `v62_confidence_p2_gaps.sql` | Confidence P2 gaps |
| `v63_bd_recommendations.sql` | BD recommendations |
| `v63_field_change_audit_security_camera.sql` | Field change audit + DDL event trigger |
| `v64_knowledge_folders.sql` | Knowledge folders |
| `v67_indication_priority_scores.sql` | Indication priority scores |
| `v69_drug_intelligence_qa.sql` | Drug intelligence QA |
| `v71_narrative_growth.sql` | Narrative feedback/growth |
| `v72_narrative_triangulation.sql` | Narrative triangulation |
| `v73_trial_identity_crosswalk.sql` | Trial identity crosswalk |
| `v74_independence_agreement.sql` | Independence agreement checks |
| `v75_collection_gaps.sql` | Collection gaps |
| `v76_collection_queue_table.sql` | Collection queue |
| `v78_whitespace_views.sql` | Whitespace finder views |
| `v79_drugcode_review_fixes.sql` | Drug-code review data fixes |
| `v81_partnership_predicates.sql` | Partnership edge predicates |
| `v82_patient_node.sql` | Patient node in entity graph |

## Legacy (`legacy/`)

Early schema built in order v2 → v24. Notable renames for version collisions:

- `v7_research_queue_default.sql` — was root `schema_migration_v7.sql`
- `v7_companies_group_fields.sql` — was `scripts/schema_migration_v7.sql`
- `v8_resolver_errors.sql` — was root `schema_migration_v8.sql`
- `v8_indication_group.sql` — was `scripts/schema_migration_v8.sql`

## Maintenance (`maintenance/`)

| File | Purpose |
|---|---|
| `wrong_area_cleanup.sql` | Wrong-area drug_areas cleanup |
| `v80_purge_mk1695_phantom.sql` | MK-1695 phantom purge (applied 2026-06-06) |
| `fix_company_areas_trigger.sql` | Company areas trigger fix |
| `prune_field_change_audit.sql` | Audit log pruning |

## Checks (`checks/`)

| File | Purpose |
|---|---|
| `v15_validation_tests.sql` | Ground-truth validation test definitions |
| `v77_publication_value_checks.sql` | Publication value agreement checks |
| `entity_consistency_checks_v1.sql` | Entity consistency check table + seeds |

## Apply status

**Do not infer apply status from this folder alone.** Use live Supabase:

```sql
SELECT migration_version, migration_file, MAX(applied_at) AS last_applied
FROM schema_change_log
GROUP BY 1, 2
ORDER BY last_applied DESC;
```

Session notes: `NEXT_SESSION.md` (v72–v77 applied), `update_log.md` (v80 confirmed applied 2026-06-06).
