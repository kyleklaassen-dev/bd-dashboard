-- v60: Core trajectory quality + positive label infrastructure
-- Applied: 2026-05-28

-- 1. enriched_field_log: add old_value tracking (critical for diff training)
ALTER TABLE enriched_field_log 
  ADD COLUMN IF NOT EXISTS old_value TEXT,
  ADD COLUMN IF NOT EXISTS old_value_captured_at TIMESTAMPTZ;

-- 2. enrichment_runs: add model version + run type
ALTER TABLE enrichment_runs
  ADD COLUMN IF NOT EXISTS model_version TEXT DEFAULT 'claude-sonnet-4-6',
  ADD COLUMN IF NOT EXISTS run_type TEXT DEFAULT 'scheduled'
    CHECK (run_type IN ('scheduled', 'manual', 'correction', 'weekend_sprint', 'validation'));

-- 3. kyle_reviews table: the positive label store
CREATE TABLE IF NOT EXISTS kyle_reviews (
  id BIGSERIAL PRIMARY KEY,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  field_name TEXT NOT NULL,
  field_value TEXT,
  enrichment_run_id UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL,
  action TEXT NOT NULL CHECK (action IN ('confirmed', 'corrected', 'uncertain', 'skipped')),
  reviewed_at TIMESTAMPTZ DEFAULT NOW(),
  session_id TEXT,
  notes TEXT,
  fine_tune_use BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS kyle_reviews_entity_idx ON kyle_reviews(entity_id, field_name);
CREATE INDEX IF NOT EXISTS kyle_reviews_action_idx ON kyle_reviews(action);
CREATE INDEX IF NOT EXISTS kyle_reviews_time_idx ON kyle_reviews(reviewed_at DESC);

-- 4. drug_stage_history: SCD for stage transitions
CREATE TABLE IF NOT EXISTS drug_stage_history (
  id BIGSERIAL PRIMARY KEY,
  drug_id TEXT NOT NULL REFERENCES drugs(id) ON DELETE CASCADE,
  stage_from TEXT,
  stage_to TEXT NOT NULL,
  effective_date DATE,
  detected_at TIMESTAMPTZ DEFAULT NOW(),
  change_event TEXT CHECK (change_event IN ('trial_initiation', 'trial_completion', 'press_release', 'regulatory', 'manual_correction', 'enrichment_update')),
  source_url TEXT,
  confidence TEXT DEFAULT 'model' CHECK (confidence IN ('verified', 'model', 'inferred')),
  enrichment_run_id UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL,
  notes TEXT
);

CREATE INDEX IF NOT EXISTS drug_stage_history_drug_idx ON drug_stage_history(drug_id);
CREATE INDEX IF NOT EXISTS drug_stage_history_date_idx ON drug_stage_history(detected_at DESC);

-- 5. agent_disagreements: track when agents conflict (valuable training signal)
CREATE TABLE IF NOT EXISTS agent_disagreements (
  id BIGSERIAL PRIMARY KEY,
  entity_id TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  field_name TEXT NOT NULL,
  run_id_a UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL,
  run_id_b UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL,
  value_a TEXT,
  value_b TEXT,
  disagreement_score NUMERIC(3,2),
  resolution TEXT,
  resolved_by TEXT CHECK (resolved_by IN ('kyle', 'agent', 'governance_rule', 'unresolved')),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Rebuild fine_tune_dataset view with positive + negative labels
DROP VIEW IF EXISTS fine_tune_dataset;
CREATE OR REPLACE VIEW fine_tune_dataset AS

-- NEGATIVE: Kyle explicit corrections
SELECT
  cl.run_id,
  cl.entity_id,
  cl.entity_type,
  er.skill_name,
  er.prompt_snapshot as prompt,
  cl.field_name,
  cl.model_output as model_said,
  cl.correct_value as ground_truth,
  'negative' as label_type,
  'kyle_correction' as label_source,
  cl.error_type,
  cl.fine_tune_use,
  cl.created_at
FROM correction_labels cl
LEFT JOIN enrichment_runs er ON er.id = cl.run_id
WHERE cl.fine_tune_use = TRUE

UNION ALL

-- POSITIVE EXPLICIT: Kyle confirmed correct
SELECT
  kr.enrichment_run_id as run_id,
  kr.entity_id,
  kr.entity_type,
  NULL as skill_name,
  NULL as prompt,
  kr.field_name,
  kr.field_value as model_said,
  kr.field_value as ground_truth,
  'positive_explicit' as label_type,
  'kyle_confirmed' as label_source,
  NULL as error_type,
  kr.fine_tune_use,
  kr.reviewed_at as created_at
FROM kyle_reviews kr
WHERE kr.action = 'confirmed'
AND kr.fine_tune_use = TRUE

UNION ALL

-- POSITIVE IMPLICIT: enriched, not null, not corrected, settled 7+ days
SELECT
  efl.enrichment_run_id as run_id,
  efl.entity_id,
  efl.entity_type,
  NULL as skill_name,
  NULL as prompt,
  efl.field_name,
  efl.enriched_value as model_said,
  efl.enriched_value as ground_truth,
  'positive_implicit' as label_type,
  'implicit_acceptance' as label_source,
  NULL as error_type,
  TRUE as fine_tune_use,
  efl.enriched_at as created_at
FROM enriched_field_log efl
WHERE efl.field_label NOT IN ('corrected', 'needs_review')
AND efl.enriched_value IS NOT NULL
AND efl.enriched_value NOT IN ('', 'Unknown', 'N/A', 'Unable to verify', 'Not available', 'TBD')
AND efl.enriched_at < NOW() - INTERVAL '7 days'
AND NOT EXISTS (
  SELECT 1 FROM correction_labels cl
  WHERE cl.entity_id = efl.entity_id
  AND cl.field_name = efl.field_name
)
AND NOT EXISTS (
  SELECT 1 FROM kyle_reviews kr
  WHERE kr.entity_id = efl.entity_id
  AND kr.field_name = efl.field_name
  AND kr.action IN ('corrected', 'uncertain')
);

-- 7. Trajectory health summary view
CREATE OR REPLACE VIEW trajectory_quality AS
SELECT
  label_type,
  label_source,
  COUNT(*) as record_count,
  COUNT(DISTINCT entity_id) as unique_entities,
  MIN(created_at) as oldest,
  MAX(created_at) as newest
FROM fine_tune_dataset
GROUP BY label_type, label_source
ORDER BY label_type, label_source;
