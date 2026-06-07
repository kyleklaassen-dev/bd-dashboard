-- v81_partnership_predicates.sql
-- Relationship-completeness sprint (2026-06-06, cowork).
-- Extend entity_edges.predicate CHECK to allow company-relationship predicates
-- used by scripts/seed_partnership_edges.py:
--   PARTNERED_WITH  (bidirectional, from company_partnerships)
--   LICENSED_FROM   (directional, from asset_transfer_history transfer_type='license')
--   ACQUIRED        (directional, from asset_transfer_history transfer_type='acquisition')
--
-- Additive only — no existing predicate value removed. Reversible (see ROLLBACK).

ALTER TABLE public.entity_edges DROP CONSTRAINT entity_edges_predicate_check;

ALTER TABLE public.entity_edges ADD CONSTRAINT entity_edges_predicate_check CHECK (
  predicate = ANY (ARRAY[
    'COMPETES_WITH','SIMILAR_TO','DERIVED_FROM','TARGETS','ACTIVE_IN',
    'SUBSTITUTES','UPSTREAM_MECHANISM','NEXT_GEN_MECHANISM','TREATS',
    'ADDRESSES','DEVELOPED_BY',
    'PARTNERED_WITH','LICENSED_FROM','ACQUIRED'
  ]::text[])
);

-- ROLLBACK:
-- ALTER TABLE public.entity_edges DROP CONSTRAINT entity_edges_predicate_check;
-- ALTER TABLE public.entity_edges ADD CONSTRAINT entity_edges_predicate_check CHECK (
--   predicate = ANY (ARRAY[
--     'COMPETES_WITH','SIMILAR_TO','DERIVED_FROM','TARGETS','ACTIVE_IN',
--     'SUBSTITUTES','UPSTREAM_MECHANISM','NEXT_GEN_MECHANISM','TREATS',
--     'ADDRESSES','DEVELOPED_BY'
--   ]::text[])
-- );
