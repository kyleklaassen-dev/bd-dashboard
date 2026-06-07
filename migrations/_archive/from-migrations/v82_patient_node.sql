-- v82_patient_node.sql
-- Relationship-completeness sprint (2026-06-06, cowork) — North Star chain completion.
-- Adds the PATIENT layer to the entity graph so the hierarchy
--   Patient -> Indication -> Target -> Company
-- is traversable end-to-end (value flows upward from patients).
--
-- 1) allow 'patient' as a node type (subject + object, for symmetry/future use)
-- 2) allow the 'AFFECTED_BY' predicate (patient --AFFECTED_BY--> indication/area)
--
-- Additive only — no existing value removed. Reversible (see ROLLBACK).

ALTER TABLE public.entity_edges DROP CONSTRAINT entity_edges_subject_type_check;
ALTER TABLE public.entity_edges ADD CONSTRAINT entity_edges_subject_type_check CHECK (
  subject_type = ANY (ARRAY['drug','company','target','area','indication','patient']::text[])
);

ALTER TABLE public.entity_edges DROP CONSTRAINT entity_edges_object_type_check;
ALTER TABLE public.entity_edges ADD CONSTRAINT entity_edges_object_type_check CHECK (
  object_type = ANY (ARRAY['drug','company','target','area','indication','patient']::text[])
);

ALTER TABLE public.entity_edges DROP CONSTRAINT entity_edges_predicate_check;
ALTER TABLE public.entity_edges ADD CONSTRAINT entity_edges_predicate_check CHECK (
  predicate = ANY (ARRAY[
    'COMPETES_WITH','SIMILAR_TO','DERIVED_FROM','TARGETS','ACTIVE_IN',
    'SUBSTITUTES','UPSTREAM_MECHANISM','NEXT_GEN_MECHANISM','TREATS',
    'ADDRESSES','DEVELOPED_BY',
    'PARTNERED_WITH','LICENSED_FROM','ACQUIRED',
    'AFFECTED_BY'
  ]::text[])
);

-- ROLLBACK:
-- ALTER TABLE public.entity_edges DROP CONSTRAINT entity_edges_subject_type_check;
-- ALTER TABLE public.entity_edges ADD CONSTRAINT entity_edges_subject_type_check CHECK (
--   subject_type = ANY (ARRAY['drug','company','target','area','indication']::text[]));
-- ALTER TABLE public.entity_edges DROP CONSTRAINT entity_edges_object_type_check;
-- ALTER TABLE public.entity_edges ADD CONSTRAINT entity_edges_object_type_check CHECK (
--   object_type = ANY (ARRAY['drug','company','target','area','indication']::text[]));
-- ALTER TABLE public.entity_edges DROP CONSTRAINT entity_edges_predicate_check;
-- ALTER TABLE public.entity_edges ADD CONSTRAINT entity_edges_predicate_check CHECK (
--   predicate = ANY (ARRAY['COMPETES_WITH','SIMILAR_TO','DERIVED_FROM','TARGETS','ACTIVE_IN',
--   'SUBSTITUTES','UPSTREAM_MECHANISM','NEXT_GEN_MECHANISM','TREATS','ADDRESSES','DEVELOPED_BY',
--   'PARTNERED_WITH','LICENSED_FROM','ACQUIRED']::text[]));
