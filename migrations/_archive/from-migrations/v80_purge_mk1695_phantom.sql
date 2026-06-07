-- v80 — Purge the MK-1695 phantom (confirmed hallucination, 2026-06-06)
--
-- MK-1695 has no public existence (Merck's anti-TL1A is MK-7240/tulisokibart).
-- The record was internally contradictory (target='IL-23 + TNF' vs mechanism=TL1A)
-- and is a confirmed bad ingestion. Kyle confirmed it is unfindable.
--
-- We delete the RECORD and all its derived edges, but DELIBERATELY KEEP the
-- error memory so the system can't silently re-create it:
--   • drug_sources row (content_confirms_claim=false) — KEPT
--   • governance_violations #58 (resolved, with notes)   — KEPT
--
-- Footprint scanned 2026-06-06: drug_areas(2), drug_indications(1),
-- drug_competitive_scores(1), drug_intelligence_qa(2), entity_edges(2),
-- entity_relationships(52), drug_validation_results(3), drugs(1).
--
-- Run in the Supabase SQL editor (service role). Idempotent.

BEGIN;

-- derived graph (not FK-constrained, would otherwise dangle)
DELETE FROM entity_relationships WHERE source_id='mk-1695' OR target_id='mk-1695';
DELETE FROM entity_edges          WHERE subject_id='mk-1695' OR object_id='mk-1695';

-- FK children
DELETE FROM drug_areas             WHERE drug_id='mk-1695';
DELETE FROM drug_indications       WHERE drug_id='mk-1695';
DELETE FROM drug_competitive_scores WHERE drug_id='mk-1695';
DELETE FROM drug_intelligence_qa   WHERE drug_id='mk-1695';
DELETE FROM drug_validation_results WHERE drug_id='mk-1695';

-- the phantom record itself
DELETE FROM drugs WHERE id='mk-1695';

-- KEEP drug_sources (error memory) + governance_violations #58 (resolved trace).

-- verification — every row below should read 0 except drug_sources (1)
SELECT 'drugs' t, count(*) n FROM drugs WHERE id='mk-1695'
UNION ALL SELECT 'entity_relationships', count(*) FROM entity_relationships WHERE source_id='mk-1695' OR target_id='mk-1695'
UNION ALL SELECT 'entity_edges', count(*) FROM entity_edges WHERE subject_id='mk-1695' OR object_id='mk-1695'
UNION ALL SELECT 'drug_areas', count(*) FROM drug_areas WHERE drug_id='mk-1695'
UNION ALL SELECT 'drug_indications', count(*) FROM drug_indications WHERE drug_id='mk-1695'
UNION ALL SELECT 'drug_competitive_scores', count(*) FROM drug_competitive_scores WHERE drug_id='mk-1695'
UNION ALL SELECT 'drug_intelligence_qa', count(*) FROM drug_intelligence_qa WHERE drug_id='mk-1695'
UNION ALL SELECT 'drug_validation_results', count(*) FROM drug_validation_results WHERE drug_id='mk-1695'
UNION ALL SELECT 'drug_sources (KEEP=1)', count(*) FROM drug_sources WHERE drug_id='mk-1695';

COMMIT;
