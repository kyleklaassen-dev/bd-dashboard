# scripts/archive/

One-off, run-once scripts kept for historical reference — **not on any schedule
and not imported by any live code** (verified 2026-06-16). These were session-specific
backfills and one-run table migrations. If you ever need to re-run one, it may need its
import paths refreshed (it was written for the flat `scripts/` layout).

Contents: session backfills (catalysts/sources/biomarkers), wave2/3 indication backfills,
one-run table-creation migrations (drug_sources, governance_violations, entity_consistency_checks),
and assorted patch/migrate one-offs.
