-- Migration v29 — ACTIVE_IN edges in entity_edges
-- Applied: 2026-05-24 (Session 31)
-- Purpose: Materialize company → ACTIVE_IN → area relationships into the
--          universal entity_edges graph layer so landscape queries become
--          single graph lookups rather than runtime joins on company_areas.
--
-- Before: "Who is active in IBD?" required:
--   SELECT company_id FROM company_areas WHERE area_id = 'ibd'
--
-- After: "Who is active in IBD?" is a graph query:
--   SELECT subject_id FROM entity_edges
--   WHERE predicate = 'ACTIVE_IN' AND object_id = 'ibd'
--
-- Design notes:
--   • 137 rows seeded from full company_areas table (54 companies × areas)
--   • subject_type='company', object_type='area'
--   • generation_method='deterministic' (derived from company_areas)
--   • All rows confidence_level='confirmed', status='active'
--   • No DDL required — ACTIVE_IN accepted by entity_edges (no predicate constraint)
--   • Future: when company_intake.py writes a new company_areas row, it should
--     also write a corresponding ACTIVE_IN entity_edge for graph consistency.
--
-- Seeded by: seed_active_in (Session 31 Python script, not a standalone SQL file)
-- Validation: validation_tests id=1077 (active_in_edges_coverage, expected=137)

-- The actual inserts were performed via Supabase REST API.
-- This file documents intent + design for the migration log.

-- To verify:
SELECT predicate, COUNT(*) FROM entity_edges
WHERE predicate = 'ACTIVE_IN'
GROUP BY predicate;

-- To query — "who is active in TL1A?":
-- SELECT subject_id FROM entity_edges
-- WHERE predicate = 'ACTIVE_IN' AND object_id = 'tl1a' AND status = 'active';

-- To query — "what areas is Sanofi active in?":
-- SELECT object_id FROM entity_edges
-- WHERE predicate = 'ACTIVE_IN' AND subject_id = 'sanofi' AND status = 'active';
