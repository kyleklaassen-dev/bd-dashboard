-- v144_manufactures_predicate.sql
-- Append MANUFACTURES to entity_edges.predicate CHECK (additive — preserves all
-- existing predicates incl. SUPPLIES/COLLABORATES/author+institution edges).
-- Used by scripts/integrations/project_manufacturing_edges.py for in-house
-- (manufacturer == owner) openFDA establishment relationships.
-- Applied 2026-06-08 via Management API. Idempotent (DROP IF EXISTS + re-ADD).

ALTER TABLE public.entity_edges DROP CONSTRAINT IF EXISTS entity_edges_predicate_check;
ALTER TABLE public.entity_edges ADD CONSTRAINT entity_edges_predicate_check CHECK (
  predicate = ANY (ARRAY[
    'COMPETES_WITH','SIMILAR_TO','DERIVED_FROM','TARGETS','ACTIVE_IN','SUBSTITUTES',
    'UPSTREAM_MECHANISM','NEXT_GEN_MECHANISM','TREATS','ADDRESSES','DEVELOPED_BY',
    'PARTNERED_WITH','LICENSED_FROM','ACQUIRED','AFFECTED_BY','STUDIES','TESTED_IN',
    'CO_DEVELOPS','REPORTED_IN','APPROVED_FOR','FILED','PRESENTED','HAS_PATENT',
    'INVESTIGATES','WORKS_ON','AFFILIATED_WITH','LED_BY','MENTIONED_IN',
    'PARTICIPATES_IN','APPROVED_IN','TERMINATED','SUPPLIES','AUTHORED',
    'CO_AUTHORED_WITH','RESEARCHES','COLLABORATES','MANUFACTURES'
  ])
);
NOTIFY pgrst, 'reload schema';
