# Migrations

## Current state

| File | Purpose |
|---|---|
| **`v1_schema.sql`** | Snapshot of production Supabase as of 2026-06-07 (158 public objects). **Do not apply to existing prod.** |
| **`v2_*.sql`+** | Forward migrations from here |
| **`_archive/`** | Pre-v1 historical files + [`SITUATION.md`](_archive/SITUATION.md) explaining what we know and don't |

## Rules (from v2 onward)

1. **One file per change** — `v2_add_foo.sql`, `v3_bar.sql`, etc.
2. **Use the template** — `docs/migration_template.sql`
3. **Never edit `v1_schema.sql` by hand** — regenerate with the export script
4. **Do not re-run `_archive/` files**

## Apply a new migration

```bash
python3 scripts/apply_sql_migration.py migrations/v2_your_change.sql
```

Requires `SUPABASE_PAT` in env or `.supabase_pat`.

## Refresh the v1 snapshot

Read-only — no DB changes:

```bash
python3 scripts/export_schema_snapshot.py
```

With `SUPABASE_PAT` set, exports full `information_schema` DDL. Without it, uses REST queries (~90s).

## Existing prod

Production already has the v1 schema. Skip v1 entirely; apply only v2+.

## New environment

1. Run `v1_schema.sql` in Supabase SQL Editor
2. Apply v2, v3, … in order
