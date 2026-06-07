-- Migration v23: Add drug intake fields to discovery_queue
-- Apply in Supabase SQL Editor:
-- https://supabase.com/dashboard/project/tghntyofptvfhmtchwcv/sql/new
--
-- Adds three columns to discovery_queue used by drug_intake.py:
--   coverage_score     INT       — 0-100 coverage % across graph dimensions
--   completeness_gaps  JSONB     — per-dimension breakdown (identity, company, target, trials, ...)
--   promotion_payload  JSONB     — full node set to promote on approval
--                                  (drug, drug_areas, drug_area_scores, catalysts, trials, MI)
--
-- Safe: all columns nullable, zero downtime.

ALTER TABLE discovery_queue
  ADD COLUMN IF NOT EXISTS coverage_score     INT     DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS completeness_gaps  JSONB   DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS promotion_payload  JSONB   DEFAULT NULL;

COMMENT ON COLUMN discovery_queue.coverage_score    IS 'Drug intake coverage score 0-100 across graph dimensions (identity, company, target, trials, catalysts, MI, conference, deals)';
COMMENT ON COLUMN discovery_queue.completeness_gaps IS 'Per-dimension completeness: {"identity":100,"company":100,"target":100,"trials":50,"catalysts":0,"molecule_intel":40,"conference_intel":20,"deals":"n/a"}';
COMMENT ON COLUMN discovery_queue.promotion_payload IS 'On approval, promote all nodes in this payload: {drug, drug_areas, drug_area_scores, molecule_intelligence, catalysts, trials}';
