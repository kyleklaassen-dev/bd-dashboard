# Pre-v1 migration archive

**Do not re-run anything in this folder on production.**

These files are historical reference from months of ad-hoc schema changes applied via Supabase SQL Editor and Management API. They are **superseded by `../v1_schema.sql`**, which was generated from the live database on 2026-06-07.

## What we know was applied

| Range | Evidence |
|---|---|
| v2–v43 (legacy `schema_migration_*`) | Core tables exist (`canonical_drugs`, `research_queue`, `drug_area_scores`, `entity_edges`, etc.) |
| v55–v63 | Explicit rows in `schema_change_log` |
| v64–v82 | Verified present via live table/view checks (2026-06-07) |
| v80 | Data purge only (MK-1695 phantom) — not schema |

## What we're unsure about

- **`v62_agent_validation_tables.sql`** — partial: `drug_validation_results` exists, `validation_agent_runs` does not
- **`drug_patents`, `drug_exclusivity`, `ownership_rights`, `company_financials`** — exist in production, no migration file in this archive (DDL auto-captured in `schema_change_log` with null version, 2026-06-07)
- **Duplicate version numbers** — e.g. two different files both called "v7" or "v8" in `from-root/` vs `from-scripts/`
- **Referenced but missing files** — `v16_provenance.sql`, `v18_intelligence_debt_queue.sql`, `v70_narrative_layer.sql` were mentioned in docs but never committed (or were renamed)

## Folder layout

| Subfolder | Origin |
|---|---|
| `from-migrations/` | Old `migrations/*.sql` |
| `from-scripts-migrations/` | Old `scripts/migrations/*.sql` |
| `from-scripts/` | `scripts/schema_migration_v*.sql`, etc. |
| `from-root/` | Root-level `schema_migration_v*.sql` |
| `from-docs/` | Reference DDL (`area_metadata`, `drug_competitive_scores`) |

## If you need the old DDL for archaeology

Search here. If you need the **current** schema, use `../v1_schema.sql` or re-run:

```bash
python3 scripts/export_schema_snapshot.py
```
