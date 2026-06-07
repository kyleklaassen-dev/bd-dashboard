-- ============================================================
-- Migration v59: Trajectory System + SOP Framework
-- Phase A — Self-Evolution Infrastructure
--
-- What this builds and why:
-- 1. correction_labels — links Kyle's corrections to enrichment_runs.
--    This is the CRITICAL missing piece for fine-tuning. Without linking
--    corrections to runs, you have data but no labels. With this table,
--    every correction Kyle makes becomes a labeled training example:
--    (run_id, field_name, model_said_X, correct_value_is_Y).
--
-- 2. Enhanced enrichment_runs columns — store the full trajectory:
--    prompt snapshot, raw LLM response, schema validation result,
--    token count, per-field confidence. Without these, you can replay
--    what happened but not WHY the model said what it said.
--
-- 3. sop_registry — version-controlled SOP metadata store.
--    Every skill has a linked SOP. SOPs have versions. When a skill
--    changes, its SOP version bumps. The registry lets any agent ask
--    "what is the current SOP for enrich_drug?" and get the right version.
--
-- 4. entity_relationships temporal fields (valid_from, valid_to) —
--    relationships change over time. A partnership formed in 2023 may
--    have ended by 2025. Without temporal fields, Meridian cannot reason
--    about what was true THEN vs what is true NOW.
--
-- 5. enrichment_field_confirmations — logs fields the model confirmed
--    correct (not just fields that changed). These are positive labels:
--    "model said X, value was already X, Kyle did not correct it."
--    Both positive and negative labels are needed for fine-tuning.
--
-- Apply: Supabase SQL Editor or Management API
-- Session: 2026-05-28
-- ============================================================

-- ── PART 1: ENHANCE enrichment_runs FOR FULL TRAJECTORY CAPTURE ──────────────

ALTER TABLE enrichment_runs
    ADD COLUMN IF NOT EXISTS prompt_snapshot TEXT,
    ADD COLUMN IF NOT EXISTS raw_llm_response TEXT,
    ADD COLUMN IF NOT EXISTS schema_validation_result JSONB,
    ADD COLUMN IF NOT EXISTS schema_valid BOOLEAN DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS validation_errors JSONB,
    ADD COLUMN IF NOT EXISTS fields_attempted TEXT[],
    ADD COLUMN IF NOT EXISTS fields_changed TEXT[],
    ADD COLUMN IF NOT EXISTS fields_confirmed TEXT[],
    ADD COLUMN IF NOT EXISTS fields_failed TEXT[],
    ADD COLUMN IF NOT EXISTS total_tokens_used INTEGER,
    ADD COLUMN IF NOT EXISTS prompt_tokens INTEGER,
    ADD COLUMN IF NOT EXISTS completion_tokens INTEGER,
    ADD COLUMN IF NOT EXISTS run_duration_seconds FLOAT,
    ADD COLUMN IF NOT EXISTS entity_type TEXT DEFAULT 'drug',
    ADD COLUMN IF NOT EXISTS entity_id TEXT,
    ADD COLUMN IF NOT EXISTS skill_name TEXT DEFAULT 'enrich_drug',
    ADD COLUMN IF NOT EXISTS skill_version TEXT DEFAULT '1.0',
    ADD COLUMN IF NOT EXISTS sop_version TEXT,
    ADD COLUMN IF NOT EXISTS correction_count INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS fine_tune_eligible BOOLEAN DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS fine_tune_excluded_reason TEXT;

COMMENT ON COLUMN enrichment_runs.prompt_snapshot IS 'The exact system prompt + user prompt sent to the model (truncated at 10K chars for storage). Enables replay.';
COMMENT ON COLUMN enrichment_runs.raw_llm_response IS 'Raw LLM response before parsing (truncated at 10K chars). The ground truth of what the model said.';
COMMENT ON COLUMN enrichment_runs.schema_validation_result IS 'JSONB output from Pydantic/schema validation: {field: {valid: bool, error: str}} for each enriched field.';
COMMENT ON COLUMN enrichment_runs.schema_valid IS 'True if all enriched fields passed schema validation before DB write. False = write blocked or overridden.';
COMMENT ON COLUMN enrichment_runs.fields_attempted IS 'All field names the enrichment attempted to populate for this entity.';
COMMENT ON COLUMN enrichment_runs.fields_changed IS 'Fields where old_value != new_value — actual enrichment changes.';
COMMENT ON COLUMN enrichment_runs.fields_confirmed IS 'Fields where model confirmed existing value was correct (old_value == new_value, no correction).';
COMMENT ON COLUMN enrichment_runs.fields_failed IS 'Fields where enrichment was attempted but schema validation failed or model returned null.';
COMMENT ON COLUMN enrichment_runs.entity_type IS 'Type of entity enriched: drug | company | indication | target';
COMMENT ON COLUMN enrichment_runs.entity_id IS 'The specific entity ID enriched in this run (for single-entity runs).';
COMMENT ON COLUMN enrichment_runs.skill_name IS 'Name of the skill that produced this run (e.g. enrich_drug, company_enrich).';
COMMENT ON COLUMN enrichment_runs.skill_version IS 'Version of the skill at time of run — enables comparing skill performance across versions.';
COMMENT ON COLUMN enrichment_runs.correction_count IS 'Number of Kyle corrections linked to this run via correction_labels. Updated as corrections come in.';
COMMENT ON COLUMN enrichment_runs.fine_tune_eligible IS 'Whether this run can be used in fine-tuning dataset. False if run had critical errors or was test-only.';

-- ── PART 2: ENHANCE enriched_field_log FOR ALL-FIELDS CAPTURE ────────────────

ALTER TABLE enriched_field_log
    ADD COLUMN IF NOT EXISTS was_changed BOOLEAN DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS model_confidence FLOAT,
    ADD COLUMN IF NOT EXISTS source_citation TEXT,
    ADD COLUMN IF NOT EXISTS field_label TEXT,
    ADD COLUMN IF NOT EXISTS label_source TEXT DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS correction_id INTEGER,
    ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS reviewed_by TEXT DEFAULT 'kyle';

COMMENT ON COLUMN enriched_field_log.was_changed IS 'TRUE if new_value differs from old_value. FALSE = model confirmed existing value. Both are valuable training labels.';
COMMENT ON COLUMN enriched_field_log.model_confidence IS 'Model-reported confidence for this field (0.0-1.0). From the enrichment response JSON.';
COMMENT ON COLUMN enriched_field_log.source_citation IS 'URL or reference the model used for this field value.';
COMMENT ON COLUMN enriched_field_log.field_label IS 'Label for fine-tuning: accepted | corrected | rejected | pending. Set by correction_labels trigger.';
COMMENT ON COLUMN enriched_field_log.label_source IS 'How label was determined: kyle_correction | kyle_acceptance | auto_validation | pending';
COMMENT ON COLUMN enriched_field_log.correction_id IS 'FK to correction_labels.id if this field was later corrected by Kyle.';

-- ── PART 3: CORRECTION_LABELS — THE CORE LABELING TABLE ──────────────────────

CREATE TABLE IF NOT EXISTS correction_labels (
    id                  SERIAL PRIMARY KEY,
    run_id              UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL,
    entity_type         TEXT NOT NULL DEFAULT 'drug',
    entity_id           TEXT NOT NULL,
    field_name          TEXT NOT NULL,
    model_output        TEXT,
    correct_value       TEXT NOT NULL,
    error_type          TEXT,
    error_severity      TEXT DEFAULT 'medium',
    correction_source   TEXT DEFAULT 'kyle',
    correction_notes    TEXT,
    version_number      TEXT,
    excel_row_ref       TEXT,
    fine_tune_use       BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE correction_labels IS
'Every correction Kyle makes to an enrichment output. This is the LABEL for the trajectory.
run_id links to the enrichment run that produced the wrong value.
model_output = what the model said. correct_value = what it should have been.
These (prompt, model_output, correct_value) triples are the fine-tuning dataset.';

COMMENT ON COLUMN correction_labels.run_id IS 'FK to enrichment_runs.id — which run produced this wrong value. NULL if correction predates run_id system.';
COMMENT ON COLUMN correction_labels.model_output IS 'What the model produced for this field (the wrong value). May be NULL if model omitted the field.';
COMMENT ON COLUMN correction_labels.correct_value IS 'The ground truth value Kyle supplied. This is the fine-tuning target.';
COMMENT ON COLUMN correction_labels.error_type IS 'Classification of error: hallucination | wrong_attribution | stale_data | schema_violation | missing_context | correct_but_incomplete';
COMMENT ON COLUMN correction_labels.error_severity IS 'Impact: critical (governance violation) | high (wrong attribution) | medium (incomplete) | low (style)';
COMMENT ON COLUMN correction_labels.excel_row_ref IS 'Reference to the Excel Corrections Log row (e.g. v15-row-42) for retroactive linking.';
COMMENT ON COLUMN correction_labels.fine_tune_use IS 'Whether to include in fine-tuning dataset. False for ambiguous corrections or test entries.';

CREATE INDEX IF NOT EXISTS idx_correction_labels_run_id ON correction_labels(run_id);
CREATE INDEX IF NOT EXISTS idx_correction_labels_entity ON correction_labels(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_correction_labels_field ON correction_labels(field_name);
CREATE INDEX IF NOT EXISTS idx_correction_labels_fine_tune ON correction_labels(fine_tune_use) WHERE fine_tune_use = TRUE;

-- ── PART 4: TRIGGER — UPDATE enrichment_runs.correction_count AUTOMATICALLY ──

CREATE OR REPLACE FUNCTION update_run_correction_count()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.run_id IS NOT NULL THEN
        UPDATE enrichment_runs
        SET correction_count = (
            SELECT COUNT(*) FROM correction_labels
            WHERE run_id = NEW.run_id
        ),
        updated_at = NOW()
        WHERE id = NEW.run_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_correction_count ON correction_labels;
CREATE TRIGGER trg_correction_count
    AFTER INSERT OR DELETE ON correction_labels
    FOR EACH ROW EXECUTE FUNCTION update_run_correction_count();

-- ── PART 5: TRIGGER — UPDATE enriched_field_log.field_label WHEN CORRECTED ──

CREATE OR REPLACE FUNCTION update_field_label_on_correction()
RETURNS TRIGGER AS $$
BEGIN
    -- Mark the enriched_field_log entry as corrected
    UPDATE enriched_field_log
    SET field_label = 'corrected',
        label_source = 'kyle_correction',
        correction_id = NEW.id,
        reviewed_at = NOW()
    WHERE run_id = NEW.run_id
      AND field_name = NEW.field_name
      AND entity_id = NEW.entity_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_field_label_correction ON correction_labels;
CREATE TRIGGER trg_field_label_correction
    AFTER INSERT ON correction_labels
    FOR EACH ROW EXECUTE FUNCTION update_field_label_on_correction();

-- ── PART 6: FINE_TUNE_DATASET VIEW — THE TRAINING DATA EXPORT ────────────────

CREATE OR REPLACE VIEW fine_tune_dataset AS
SELECT
    er.id                           AS run_id,
    er.skill_name,
    er.skill_version,
    er.entity_type,
    er.entity_id,
    er.model_used,
    er.prompt_snapshot,
    er.raw_llm_response,
    cl.field_name,
    cl.model_output                 AS model_said,
    cl.correct_value                AS correct_value,
    cl.error_type,
    cl.error_severity,
    er.created_at                   AS run_date,
    cl.created_at                   AS correction_date,
    EXTRACT(EPOCH FROM (cl.created_at - er.created_at))/3600 AS hours_to_correction
FROM correction_labels cl
JOIN enrichment_runs er ON er.id = cl.run_id
WHERE cl.fine_tune_use = TRUE
  AND er.fine_tune_eligible = TRUE
  AND cl.correct_value IS NOT NULL
ORDER BY er.created_at DESC;

COMMENT ON VIEW fine_tune_dataset IS
'The fine-tuning training dataset. Each row is one (prompt, wrong_output, correct_output) triple.
Export this view when preparing fine-tuning data for Anthropic API.
Format for Anthropic: {"prompt": prompt_snapshot, "completion": correct_value}
Filter by field_name to build field-specific fine-tuning datasets.';

-- ── PART 7: SOP_REGISTRY — VERSIONED SKILL SOPs ──────────────────────────────

CREATE TABLE IF NOT EXISTS sop_registry (
    id              SERIAL PRIMARY KEY,
    sop_name        TEXT NOT NULL UNIQUE,
    display_name    TEXT NOT NULL,
    version         TEXT NOT NULL DEFAULT '1.0',
    skill_name      TEXT NOT NULL,
    file_path       TEXT,
    description     TEXT,
    status          TEXT DEFAULT 'active' CHECK (status IN ('active','deprecated','draft','review')),
    inputs          JSONB,
    outputs         JSONB,
    steps_count     INTEGER,
    error_handling  TEXT,
    last_updated    TIMESTAMPTZ DEFAULT NOW(),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    deprecated_at   TIMESTAMPTZ,
    deprecated_reason TEXT,
    changelog       JSONB DEFAULT '[]'::jsonb
);

COMMENT ON TABLE sop_registry IS
'Version-controlled registry of all Meridian skill SOPs.
Each SOP maps to one skill. When the skill logic changes, the SOP version bumps.
The file_path points to docs/sops/{sop_name}_v{version}.yaml in the GitHub repo.
Any agent can query: SELECT * FROM sop_registry WHERE skill_name = $1 AND status = ''active'' to get the current SOP.';

COMMENT ON COLUMN sop_registry.version IS 'Semantic version: 1.0, 1.1, 2.0. Major = breaking change. Minor = additive.';
COMMENT ON COLUMN sop_registry.skill_name IS 'The callable skill this SOP governs (must match SKILLS_REGISTRY).';
COMMENT ON COLUMN sop_registry.file_path IS 'Relative path in GitHub repo: docs/sops/enrich_drug_v1.0.yaml';
COMMENT ON COLUMN sop_registry.inputs IS 'JSON schema of expected inputs: {field: {type, required, description}}';
COMMENT ON COLUMN sop_registry.outputs IS 'JSON schema of expected outputs: {field: {type, description}}';
COMMENT ON COLUMN sop_registry.changelog IS 'Array of {version, date, change} — full version history.';

-- Seed with the 5 core SOPs
INSERT INTO sop_registry (sop_name, display_name, version, skill_name, file_path, description, status, steps_count, inputs, outputs) VALUES
('drug_attribution_v1', 'Drug Attribution & Governance', '1.0', 'validate_drug',
 'docs/sops/drug_attribution_v1.0.yaml',
 'Rules for identifying originator vs licensee vs acquirer. When to set status=acquired vs subsidiary. How to handle co-development. Applies governance_violations check after every write.',
 'active', 7,
 '{"drug_id": {"type": "string", "required": true}, "company_id": {"type": "string", "required": true}, "partner_company": {"type": "string", "required": false}}',
 '{"governance_violations": {"type": "array"}, "attribution_correct": {"type": "boolean"}}'
),
('deal_sequencing_v1', 'Deal Sequencing Logic', '1.0', 'bd_recommend',
 'docs/sops/deal_sequencing_v1.0.yaml',
 'When is a pharma company ''call now'' vs ''too early''? Decision tree: IF company has Phase 3 TL1A asset AND no bispecific AND readout within 18 months → call_timing=now. AbbVie gate: Oct 2026.',
 'active', 5,
 '{"company_id": {"type": "string", "required": true}, "drug_id": {"type": "string", "required": false}}',
 '{"call_timing": {"type": "string", "enum": ["now", "6_months", "12_months", "blocked", "never"]}, "rationale": {"type": "string"}, "constraints": {"type": "array"}}'
),
('competitive_scoring_v1', 'Competitive Relevance Scoring', '1.0', 'score_drug',
 'docs/sops/competitive_scoring_v1.0.yaml',
 '5-dimension scoring model for drug competitive relevance vs XPF005 reference. Dimensions: target_overlap (0-40), indication (0-30), modality (0-20), stage (0-10), geography_penalty (-20 to 0).',
 'active', 5,
 '{"drug_id": {"type": "string", "required": true}, "reference_drug_id": {"type": "string", "default": "anti-tl1a-xpf005-arm"}}',
 '{"total_score": {"type": "integer", "min": 0, "max": 100}, "dimension_scores": {"type": "object"}, "tier": {"type": "string", "enum": ["Tier 1", "Tier 2", "Tier 3", "Tier 4"]}}'
),
('meridian_issue_style_v1', 'Meridian Issue Style Guide', '1.0', 'write_meridian_issue',
 'docs/sops/meridian_issue_style_v1.0.yaml',
 'How to write each section of the Meridian Issue: signal, mechanism, significance score (1-5 rubric), Ailux implication. What makes meridian_issue_worthy=TRUE: significance >= 4 OR direct XPF005 implication.',
 'active', 6,
 '{"signals": {"type": "array", "required": true}, "indication_context": {"type": "string", "required": false}}',
 '{"html_content": {"type": "string"}, "meridian_issue_worthy_items": {"type": "array"}, "significance_scores": {"type": "object"}}'
),
('db_safety_v1', 'Database Safety Protocol', '1.0', 'safety_audit',
 'docs/sops/db_safety_v1.0.yaml',
 'Rules for safe DB writes: soft-delete only (never hard DELETE), source_url required for all new partner records, brand_name requires approved stage, bulk updates require backup snapshot first. Safety agent runs after every write.',
 'active', 8,
 '{"operation": {"type": "string", "enum": ["INSERT", "UPDATE", "DELETE", "BULK_UPDATE"]}, "table": {"type": "string"}, "rows_affected": {"type": "integer"}}',
 '{"approved": {"type": "boolean"}, "violations": {"type": "array"}, "requires_backup": {"type": "boolean"}}'
)
ON CONFLICT (sop_name) DO UPDATE SET
    version = EXCLUDED.version,
    description = EXCLUDED.description,
    last_updated = NOW();

-- ── PART 8: ENTITY_RELATIONSHIPS TEMPORAL FIELDS ─────────────────────────────

ALTER TABLE entity_relationships
    ADD COLUMN IF NOT EXISTS valid_from  DATE,
    ADD COLUMN IF NOT EXISTS valid_to    DATE,
    ADD COLUMN IF NOT EXISTS is_current  BOOLEAN DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS end_reason  TEXT,
    ADD COLUMN IF NOT EXISTS confidence  TEXT DEFAULT 'medium' CHECK (confidence IN ('high','medium','low','inferred'));

COMMENT ON COLUMN entity_relationships.valid_from IS 'Date this relationship became active. NULL = predates tracking.';
COMMENT ON COLUMN entity_relationships.valid_to IS 'Date this relationship ended. NULL = still active (current).';
COMMENT ON COLUMN entity_relationships.is_current IS 'TRUE if relationship is currently active. FALSE = historical only.';
COMMENT ON COLUMN entity_relationships.end_reason IS 'Why the relationship ended: acquired, partnership_expired, asset_sold, company_dissolved, deal_terminated';
COMMENT ON COLUMN entity_relationships.confidence IS 'How confident we are in the relationship: high (press release/SEC filing) | medium (inferred from news) | low (speculative) | inferred (rule-derived)';

-- ── PART 9: TRAJECTORY SUMMARY VIEW ─────────────────────────────────────────

CREATE OR REPLACE VIEW trajectory_summary AS
SELECT
    er.id                           AS run_id,
    er.skill_name,
    er.entity_type,
    er.entity_id,
    er.model_used,
    er.status,
    er.created_at                   AS run_date,
    er.correction_count,
    er.schema_valid,
    er.fine_tune_eligible,
    ARRAY_LENGTH(er.fields_attempted, 1)  AS fields_attempted_count,
    ARRAY_LENGTH(er.fields_changed, 1)    AS fields_changed_count,
    ARRAY_LENGTH(er.fields_confirmed, 1)  AS fields_confirmed_count,
    ARRAY_LENGTH(er.fields_failed, 1)     AS fields_failed_count,
    CASE
        WHEN er.correction_count > 0 THEN 'has_corrections'
        WHEN er.fields_changed IS NOT NULL AND ARRAY_LENGTH(er.fields_changed,1) > 0 THEN 'enriched_no_corrections'
        WHEN er.fields_confirmed IS NOT NULL AND ARRAY_LENGTH(er.fields_confirmed,1) > 0 THEN 'confirmed_only'
        ELSE 'empty_run'
    END                             AS trajectory_type,
    (er.correction_count::float / GREATEST(ARRAY_LENGTH(er.fields_changed,1), 1)) AS correction_rate
FROM enrichment_runs er
ORDER BY er.created_at DESC;

COMMENT ON VIEW trajectory_summary IS
'Summary view of all enrichment trajectories. Use to monitor:
- correction_rate: high rate = model struggling with this entity type
- trajectory_type: has_corrections = labeled training data available
- fine_tune_eligible: filter for fine-tuning dataset preparation
Query: SELECT * FROM trajectory_summary WHERE trajectory_type = ''has_corrections'' AND fine_tune_eligible = TRUE';

-- ── VERIFICATION QUERIES (run after applying) ─────────────────────────────────
-- SELECT column_name FROM information_schema.columns WHERE table_name = 'enrichment_runs' AND column_name IN ('prompt_snapshot', 'raw_llm_response', 'schema_valid', 'correction_count');
-- SELECT COUNT(*) FROM sop_registry;
-- SELECT column_name FROM information_schema.columns WHERE table_name = 'correction_labels';
-- SELECT * FROM trajectory_summary LIMIT 5;
-- SELECT * FROM fine_tune_dataset LIMIT 5;
