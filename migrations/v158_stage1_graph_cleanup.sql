-- ============================================================================
-- v158_stage1_graph_cleanup.sql
-- Stage 1 residual graph cleanup (Kyle-approved 2026-06-16). Edge deletes only;
-- molecule MERGES (xmab5871->obexelimab, ati-045->bosakitug) run via
-- scripts/maintenance/dedupe_entities.py (FK-aware), not here.
--
--  1. Purge phantom drug codes mk-1718 + mdr-018 (no real-world asset; verified
--     no web evidence; matches the prior mk-1695 phantom purge in v80).
--  2. Delete company-as-drug type-error edges (subject/object_type='drug' but the
--     id is a company: abbvie, amgen, aurinia, jnj, ucb, orukatherapeutics).
--  3. cld-423 wrong-id edges: CLD-423 is real but already stored as 'cldr-001'
--     (52 edges). The 16 'cld-423' edges are redundant -> delete + alias the code.
-- ============================================================================

BEGIN;

-- 1. phantom purge
DELETE FROM entity_edges
 WHERE subject_id IN ('mk-1718','mdr-018') OR object_id IN ('mk-1718','mdr-018');

-- 2. company-as-drug type errors (explicit ids, verified company-as-drug; avoids over-delete)
DELETE FROM entity_edges
 WHERE (subject_type='drug' AND subject_id IN ('abbvie','amgen','aurinia','jnj','ucb','orukatherapeutics'))
    OR (object_type ='drug' AND object_id  IN ('abbvie','amgen','aurinia','jnj','ucb','orukatherapeutics'));

-- 3. cld-423 redundant edges -> delete, then alias the code onto canonical cldr-001
DELETE FROM entity_edges WHERE subject_id='cld-423' OR object_id='cld-423';

UPDATE drugs SET aliases = (
    SELECT jsonb_agg(DISTINCT e)
    FROM jsonb_array_elements_text(coalesce(aliases,'[]'::jsonb) || '["CLD-423","cld-423"]'::jsonb) e
) WHERE id='cldr-001';

-- registry
INSERT INTO schema_change_log
    (migration_version, migration_file, change_type, object_name, field_name,
     old_definition, new_definition, rationale)
VALUES
('v158','v158_stage1_graph_cleanup.sql','backfill','entity_edges',NULL,
 'phantom + type-error + redundant edges','deleted',
 'Stage 1: purge mk-1718/mdr-018 phantoms, company-as-drug edges, redundant cld-423 edges; alias CLD-423->cldr-001 (Kyle-approved).');

COMMIT;
