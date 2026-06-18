# Schema Cleanup Backlog

Tracks dead/empty DB objects. Supersedes `migrations/PROPOSED_drop_dead_tables.sql`
(removed — Tier A is applied; a "PROPOSED migration" that's been partly executed is
confusing to keep in `migrations/`). Original audit: 2026-06-09; verified + Tier A
executed 2026-06-16.

## Tier A — DONE (dropped 2026-06-16, verified)
All 6 audit candidates were **VIEWS** (the original file mislabeled two as tables —
verified via `pg_class.relkind` before acting). Dropped the 5 with zero repo
references (recreatable from their `CREATE VIEW` definitions in git; no data loss):

- `phase3_regulatory_risk_map`, `recent_field_changes`, `change_frequency_summary`,
  `company_area_detail`, `governance_change_alerts` — **DROPPED**. Dashboard read
  path re-verified healthy after.
- `effective_company_areas` — kept (defined in `scripts/migrations/v25_ownership_edges.sql`;
  unused but left for a follow-up since it's part of the ownership-edges migration).

## Tier B — DECIDE PER TABLE (empty + a script writes to them = collector paused/broken)
For each: either revive the collector or retire BOTH the table and its script.

| table | scripts | note |
|---|---|---|
| `china_trials` | 2 | CDE/NMPA harvest; known-hard source |
| `patent_families` | 2 | patent sweep; was throttled |
| `trial_identity` | 3 | |
| `drug_stage_history` | 5 | |
| `source_collection_gaps` | 3 | |
| `correction_labels` | 4 | |
| `model_validation_results` | 4 | |
| `fine_tune_dataset` | 4 | |
| `target_areas` | 1 | |
| `trajectory_summary` | 1 | |
| `narrative_claim_triangulation` | 1 | |
| `narrative_feedback` | 1 | |
| `narrative_source_diversity` | 1 | |

## Tier C — DO NOT DROP (empty but read by the dashboard → POPULATE, not remove)
`company_areas` (28 reads), `company_profiles` (13), `drug_modalities` (10),
`intel_areas` (11), `intel_companies` (7), `indication_biology_tags` (7),
`drug_routes` (6), `drug_areas` (legacy, 23). These are dark features / data gaps.
