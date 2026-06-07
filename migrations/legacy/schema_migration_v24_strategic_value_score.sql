-- Migration v24: Add strategic_value_score to discovery_queue + drug_area_scores
-- Apply in Supabase SQL Editor:
-- https://supabase.com/dashboard/project/tghntyofptvfhmtchwcv/sql/new
--
-- strategic_value_score: how much should Kyle care about this asset from a BD perspective?
--   Orthogonal to coverage_score (completeness) and evidence_tier (certainty).
--   A 40%-coverage Emerging drug that is Direct in a core area can outscore
--   a 95%-coverage Confirmed drug that is Watch.
--
-- Persisted in two places:
--   discovery_queue.strategic_value_score  — review prioritization (which intake items first?)
--   drug_area_scores.strategic_value_score — dashboard prioritization (which area tab assets matter most?)
--
-- Scoring model (0-10):
--   Overlap × Area Primacy   0-4.0   (Direct in core area = 4, Watch = 0.5)
--   Stage Maturity           0-2.0   (Phase 3/Approved = 2, Discovery = 0)
--   Catalyst Proximity       0-1.5   (catalyst <90 days = 1.5, none = 0)
--   Evidence Confidence      0-1.0   (Confirmed = 1, Hypothesis = 0.1)
--   Deal Activity            0-0.75  (has deals = 0.75)
--   Company Importance       0-0.5   (major pharma = 0.5)
--   Max total = 9.75 → rounded to 10
--
-- Safe: all columns nullable, zero downtime.

ALTER TABLE discovery_queue
  ADD COLUMN IF NOT EXISTS strategic_value_score INT DEFAULT NULL;

ALTER TABLE drug_area_scores
  ADD COLUMN IF NOT EXISTS strategic_value_score INT DEFAULT NULL;

COMMENT ON COLUMN discovery_queue.strategic_value_score IS
  'BD importance 0-10: how much should Kyle care? Combines overlap tier × area primacy, stage, catalyst proximity, evidence confidence, deal activity, company importance. Orthogonal to coverage_score.';

COMMENT ON COLUMN drug_area_scores.strategic_value_score IS
  'BD importance 0-10 for this drug in this area. Used to sort area tab drugs by strategic importance (not just stage or name). Updated by drug_intake.py and enrichment pipeline.';
