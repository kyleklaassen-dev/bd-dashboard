-- ═══════════════════════════════════════════════════════════════════════
-- v63 — Meridian Database Security Camera
-- Field-level audit trail for every data change across all tracked tables
--
-- Philosophy: "Being wrong is okay, we just want to be correct more often.
-- The more evidence we collect the easier it is to know."
-- Every change must leave a fingerprint. The mistake can still happen.
-- The difference is it can never hide.
--
-- Applied: 2026-05-28
-- Migration file: v63_field_change_audit_security_camera.sql
-- ═══════════════════════════════════════════════════════════════════════


-- ═══════════════════════════════════════════════════════════════════════
-- BLOCK 1 — Create field_change_audit table (the permanent record)
-- ═══════════════════════════════════════════════════════════════════════

-- The security camera table: permanent record of every data change, forever
-- old values are kept even when new becomes old — this is memory, this is the brain
CREATE TABLE IF NOT EXISTS field_change_audit (
    id BIGSERIAL PRIMARY KEY,

    -- WHERE did this change happen?
    table_name TEXT NOT NULL,
    entity_id TEXT NOT NULL,              -- primary key value of the changed row
    entity_type TEXT,                      -- human-friendly type: 'drug', 'company', etc.

    -- WHAT changed?
    field_name TEXT NOT NULL,             -- column name that changed
    old_value TEXT,                        -- value BEFORE the change (null if new row)
    new_value TEXT,                        -- value AFTER the change (null if deleted)

    -- WHEN did it change?
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- WHO or WHAT changed it?
    changed_by TEXT,                       -- agent name, script, migration file, or 'manual'
    enrichment_run_id UUID,               -- if from enrichment pipeline, which run?
    session_id TEXT,                       -- GitHub Actions run ID or session identifier
    change_source TEXT CHECK (change_source IN (
        'enrichment_agent', 'weekend_sprint', 'manual_edit',
        'migration', 'kyle_correction', 'trigger', 'unknown'
    )),

    -- WHY did it change?
    change_reason TEXT,                    -- populated from app.change_reason session var if set

    -- IS THIS A GOVERNANCE-RELEVANT CHANGE?
    is_governance_relevant BOOLEAN DEFAULT FALSE,
    governance_rule TEXT,                  -- which governance rule applies, if any

    -- IS THIS A CORRECTION? (training signal)
    is_correction BOOLEAN DEFAULT FALSE,  -- true if this change came from kyle_reviews

    -- METADATA
    row_snapshot JSONB                     -- optional: full row state after change for deep audit
);

-- Indexes for every query pattern Kyle will use
CREATE INDEX IF NOT EXISTS fca_entity_idx ON field_change_audit(table_name, entity_id);
CREATE INDEX IF NOT EXISTS fca_changed_at_idx ON field_change_audit(changed_at DESC);
CREATE INDEX IF NOT EXISTS fca_field_idx ON field_change_audit(table_name, field_name);
CREATE INDEX IF NOT EXISTS fca_run_idx ON field_change_audit(enrichment_run_id) WHERE enrichment_run_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS fca_governance_idx ON field_change_audit(is_governance_relevant) WHERE is_governance_relevant = TRUE;
CREATE INDEX IF NOT EXISTS fca_correction_idx ON field_change_audit(is_correction) WHERE is_correction = TRUE;
CREATE INDEX IF NOT EXISTS fca_changed_by_idx ON field_change_audit(changed_by);


-- ═══════════════════════════════════════════════════════════════════════
-- BLOCK 2 — Generic trigger function (one function, applied to every table)
-- ═══════════════════════════════════════════════════════════════════════

-- The camera lens: fired before every UPDATE on every tracked table
-- Compares old and new row state column by column
-- Records ONLY columns that actually changed (not noise)
-- Note: Uses CASE statement for entity_type_map (avoids JSONB literal quoting issues)
CREATE OR REPLACE FUNCTION meridian_capture_field_changes()
RETURNS TRIGGER AS $$
DECLARE
    old_json JSONB;
    new_json JSONB;
    col_key TEXT;
    old_val TEXT;
    new_val TEXT;
    entity_id_val TEXT;
    entity_type_val TEXT;

    -- Columns to skip (system/audit columns that change constantly and add noise)
    skip_cols TEXT[] := ARRAY[
        'updated_at', 'created_at', 'enriched_at', 'reviewed_at',
        'detected_at', 'validated_at', 'resolved_at', 'changed_at',
        'last_enrichment_run_id', 'enrichment_run_id', 'id'
    ];

    -- Governance-relevant fields that always trigger the flag
    gov_fields TEXT[] := ARRAY[
        'company_id', 'stage', 'brand_name', 'approval_date',
        'partner_company_id', 'deal_type', 'overlap', 'target',
        'partnership_verified', 'source_url', 'status'
    ];

BEGIN
    -- Only act on UPDATE operations
    IF TG_OP != 'UPDATE' THEN
        RETURN NEW;
    END IF;

    old_json := to_jsonb(OLD);
    new_json := to_jsonb(NEW);

    -- Resolve entity_id: try id, then drug_id, then company_id, then first column
    entity_id_val := COALESCE(
        (old_json->>'id'),
        (old_json->>'drug_id'),
        (old_json->>'company_id'),
        'unknown'
    );

    -- Map table name to entity type
    entity_type_val := CASE TG_TABLE_NAME
        WHEN 'drugs' THEN 'drug'
        WHEN 'companies' THEN 'company'
        WHEN 'drug_targets' THEN 'drug_target'
        WHEN 'drug_indications' THEN 'drug_indication'
        WHEN 'entity_relationships' THEN 'relationship'
        WHEN 'company_partnerships' THEN 'partnership'
        WHEN 'deals' THEN 'deal'
        WHEN 'molecule_intelligence' THEN 'molecule'
        WHEN 'drug_pk_parameters' THEN 'pk_data'
        WHEN 'drug_pd_parameters' THEN 'pd_data'
        WHEN 'drug_biomarkers' THEN 'biomarker'
        WHEN 'non_responder_profiles' THEN 'non_responder'
        WHEN 'clinical_evidence_items' THEN 'clinical_evidence'
        WHEN 'indication_patient_intelligence' THEN 'patient_intel'
        WHEN 'payer_tpp_criteria' THEN 'payer_tpp'
        WHEN 'portfolio_conflict_matrix' THEN 'portfolio_conflict'
        WHEN 'drug_competitive_scores' THEN 'competitive_score'
        WHEN 'drug_validation_results' THEN 'validation'
        WHEN 'governance_violations' THEN 'governance'
        WHEN 'catalyst_calendar' THEN 'catalyst'
        WHEN 'drug_stage_history' THEN 'stage_change'
        WHEN 'drug_approvals' THEN 'approval'
        WHEN 'coverage_scores' THEN 'coverage'
        WHEN 'competitive_landscapes' THEN 'landscape'
        WHEN 'mechanism_status' THEN 'mechanism'
        WHEN 'sop_registry' THEN 'sop'
        WHEN 'enrichment_runs' THEN 'enrichment_run'
        ELSE TG_TABLE_NAME
    END;

    -- Iterate every column and detect changes
    FOR col_key IN SELECT jsonb_object_keys(new_json) LOOP
        -- Skip noise columns
        CONTINUE WHEN col_key = ANY(skip_cols);

        old_val := old_json->>col_key;
        new_val := new_json->>col_key;

        -- Only record if value actually changed (NULL-safe comparison)
        IF old_val IS DISTINCT FROM new_val THEN
            INSERT INTO field_change_audit (
                table_name,
                entity_id,
                entity_type,
                field_name,
                old_value,
                new_value,
                changed_at,
                changed_by,
                enrichment_run_id,
                session_id,
                change_source,
                change_reason,
                is_governance_relevant,
                governance_rule
            ) VALUES (
                TG_TABLE_NAME,
                entity_id_val,
                entity_type_val,
                col_key,
                old_val,
                new_val,
                NOW(),
                -- Try to get change attribution from session variables (set by enrichment scripts)
                COALESCE(
                    current_setting('app.changed_by', true),
                    session_user
                ),
                -- Try to get enrichment_run_id from session variable
                NULLIF(current_setting('app.enrichment_run_id', true), '')::UUID,
                current_setting('app.session_id', true),
                COALESCE(
                    current_setting('app.change_source', true)::TEXT,
                    'unknown'
                ),
                current_setting('app.change_reason', true),
                -- Flag if this is a governance-relevant field
                col_key = ANY(gov_fields),
                -- Add governance rule name for key fields
                CASE
                    WHEN col_key = 'company_id' THEN 'licensing_attribution'
                    WHEN col_key = 'brand_name' THEN 'brand_name_implies_approved'
                    WHEN col_key = 'stage' THEN 'stage_validation'
                    WHEN col_key = 'source_url' THEN 'source_url_required'
                    ELSE NULL
                END
            );
        END IF;
    END LOOP;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


-- ═══════════════════════════════════════════════════════════════════════
-- BLOCK 3 — Apply trigger to ALL tracked tables
-- ═══════════════════════════════════════════════════════════════════════

-- Core entity tables
DROP TRIGGER IF EXISTS audit_drugs_changes ON drugs;
CREATE TRIGGER audit_drugs_changes
    BEFORE UPDATE ON drugs
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS audit_companies_changes ON companies;
CREATE TRIGGER audit_companies_changes
    BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS audit_drug_targets_changes ON drug_targets;
CREATE TRIGGER audit_drug_targets_changes
    BEFORE UPDATE ON drug_targets
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS audit_drug_indications_changes ON drug_indications;
CREATE TRIGGER audit_drug_indications_changes
    BEFORE UPDATE ON drug_indications
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS audit_entity_relationships_changes ON entity_relationships;
CREATE TRIGGER audit_entity_relationships_changes
    BEFORE UPDATE ON entity_relationships
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS audit_company_partnerships_changes ON company_partnerships;
CREATE TRIGGER audit_company_partnerships_changes
    BEFORE UPDATE ON company_partnerships
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS audit_deals_changes ON deals;
CREATE TRIGGER audit_deals_changes
    BEFORE UPDATE ON deals
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

-- Intelligence tables
DROP TRIGGER IF EXISTS audit_molecule_intelligence_changes ON molecule_intelligence;
CREATE TRIGGER audit_molecule_intelligence_changes
    BEFORE UPDATE ON molecule_intelligence
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS audit_drug_pk_parameters_changes ON drug_pk_parameters;
CREATE TRIGGER audit_drug_pk_parameters_changes
    BEFORE UPDATE ON drug_pk_parameters
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS audit_drug_pd_parameters_changes ON drug_pd_parameters;
CREATE TRIGGER audit_drug_pd_parameters_changes
    BEFORE UPDATE ON drug_pd_parameters
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS audit_drug_biomarkers_changes ON drug_biomarkers;
CREATE TRIGGER audit_drug_biomarkers_changes
    BEFORE UPDATE ON drug_biomarkers
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS audit_non_responder_profiles_changes ON non_responder_profiles;
CREATE TRIGGER audit_non_responder_profiles_changes
    BEFORE UPDATE ON non_responder_profiles
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS audit_clinical_evidence_items_changes ON clinical_evidence_items;
CREATE TRIGGER audit_clinical_evidence_items_changes
    BEFORE UPDATE ON clinical_evidence_items
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS audit_indication_patient_intelligence_changes ON indication_patient_intelligence;
CREATE TRIGGER audit_indication_patient_intelligence_changes
    BEFORE UPDATE ON indication_patient_intelligence
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS audit_payer_tpp_criteria_changes ON payer_tpp_criteria;
CREATE TRIGGER audit_payer_tpp_criteria_changes
    BEFORE UPDATE ON payer_tpp_criteria
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS audit_portfolio_conflict_matrix_changes ON portfolio_conflict_matrix;
CREATE TRIGGER audit_portfolio_conflict_matrix_changes
    BEFORE UPDATE ON portfolio_conflict_matrix
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

-- Scoring and validation tables
DROP TRIGGER IF EXISTS audit_drug_competitive_scores_changes ON drug_competitive_scores;
CREATE TRIGGER audit_drug_competitive_scores_changes
    BEFORE UPDATE ON drug_competitive_scores
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS audit_drug_validation_results_changes ON drug_validation_results;
CREATE TRIGGER audit_drug_validation_results_changes
    BEFORE UPDATE ON drug_validation_results
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS audit_governance_violations_changes ON governance_violations;
CREATE TRIGGER audit_governance_violations_changes
    BEFORE UPDATE ON governance_violations
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS audit_catalyst_calendar_changes ON catalyst_calendar;
CREATE TRIGGER audit_catalyst_calendar_changes
    BEFORE UPDATE ON catalyst_calendar
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS audit_drug_stage_history_changes ON drug_stage_history;
CREATE TRIGGER audit_drug_stage_history_changes
    BEFORE UPDATE ON drug_stage_history
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS audit_coverage_scores_changes ON coverage_scores;
CREATE TRIGGER audit_coverage_scores_changes
    BEFORE UPDATE ON coverage_scores
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS audit_competitive_landscapes_changes ON competitive_landscapes;
CREATE TRIGGER audit_competitive_landscapes_changes
    BEFORE UPDATE ON competitive_landscapes
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS audit_mechanism_status_changes ON mechanism_status;
CREATE TRIGGER audit_mechanism_status_changes
    BEFORE UPDATE ON mechanism_status
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();


-- ═══════════════════════════════════════════════════════════════════════
-- BLOCK 4 — Enhanced schema_change_log with DDL event trigger
-- ═══════════════════════════════════════════════════════════════════════

-- Enhance schema_change_log if it exists (may already exist from previous sessions)
ALTER TABLE schema_change_log
    ADD COLUMN IF NOT EXISTS command_text TEXT,
    ADD COLUMN IF NOT EXISTS session_user_name TEXT,
    ADD COLUMN IF NOT EXISTS changed_by TEXT,
    ADD COLUMN IF NOT EXISTS schema_before JSONB,
    ADD COLUMN IF NOT EXISTS schema_after JSONB;

-- NOTE: migration_file and migration_version columns already exist in schema_change_log
-- (from the initial schema_change_log setup), so we only add truly new columns above.

-- DDL event trigger: automatically captures EVERY schema change forever
-- This means ALTER TABLE, CREATE TABLE, DROP TABLE, CREATE INDEX, etc.
CREATE OR REPLACE FUNCTION meridian_log_ddl_change()
RETURNS event_trigger AS $$
DECLARE
    r RECORD;
    cmd_text TEXT;
BEGIN
    -- Get the SQL command that caused this trigger
    cmd_text := current_query();

    FOR r IN SELECT * FROM pg_event_trigger_ddl_commands() LOOP
        -- Skip logging changes to the audit tables themselves to avoid recursion
        CONTINUE WHEN r.object_identity ILIKE '%field_change_audit%';
        CONTINUE WHEN r.object_identity ILIKE '%schema_change_log%';

        INSERT INTO schema_change_log (
            change_type,
            object_name,
            command_text,
            applied_at,
            session_user_name,
            changed_by,
            migration_file,
            migration_version
        ) VALUES (
            r.command_tag,
            r.object_identity,
            LEFT(cmd_text, 2000),  -- truncate very long DDL
            NOW(),
            session_user,
            COALESCE(current_setting('app.changed_by', true), session_user),
            current_setting('app.migration_file', true),
            current_setting('app.migration_version', true)
        )
        ON CONFLICT DO NOTHING;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Create the event trigger (fires after every DDL command completes)
-- NOTE: Requires superuser — will skip gracefully if permission denied
DROP EVENT TRIGGER IF EXISTS meridian_capture_schema_changes;
CREATE EVENT TRIGGER meridian_capture_schema_changes
    ON ddl_command_end
    WHEN TAG IN (
        'ALTER TABLE', 'CREATE TABLE', 'DROP TABLE',
        'CREATE INDEX', 'DROP INDEX', 'CREATE VIEW', 'DROP VIEW',
        'ALTER VIEW', 'CREATE FUNCTION', 'DROP FUNCTION',
        'CREATE TRIGGER', 'DROP TRIGGER', 'CREATE TYPE', 'DROP TYPE'
    )
    EXECUTE FUNCTION meridian_log_ddl_change();


-- ═══════════════════════════════════════════════════════════════════════
-- BLOCK 5 — Useful views for the dashboard and Kyle's review
-- ═══════════════════════════════════════════════════════════════════════

-- View: recent changes across all tables (what happened in last 7 days)
CREATE OR REPLACE VIEW recent_field_changes AS
SELECT
    fca.changed_at,
    fca.table_name,
    fca.entity_id,
    fca.entity_type,
    fca.field_name,
    fca.old_value,
    fca.new_value,
    fca.changed_by,
    fca.change_source,
    fca.is_governance_relevant,
    fca.is_correction,
    -- Join drug name if this is a drug change
    d.name AS drug_name,
    -- Join company name if this is a company change
    c.name AS company_name
FROM field_change_audit fca
LEFT JOIN drugs d ON fca.table_name = 'drugs' AND fca.entity_id = d.id
LEFT JOIN companies c ON fca.table_name = 'companies' AND fca.entity_id = c.id
WHERE fca.changed_at >= NOW() - INTERVAL '7 days'
ORDER BY fca.changed_at DESC;

-- View: governance-sensitive changes needing review
CREATE OR REPLACE VIEW governance_change_alerts AS
SELECT
    fca.changed_at,
    fca.table_name,
    fca.entity_id,
    fca.entity_type,
    fca.field_name,
    fca.old_value,
    fca.new_value,
    fca.changed_by,
    fca.governance_rule,
    d.name AS drug_name,
    c.name AS company_name
FROM field_change_audit fca
LEFT JOIN drugs d ON fca.table_name = 'drugs' AND fca.entity_id = d.id
LEFT JOIN companies c ON fca.table_name = 'companies' AND fca.entity_id = c.id
WHERE fca.is_governance_relevant = TRUE
ORDER BY fca.changed_at DESC;

-- View: change frequency by entity (which drugs/companies change the most)
CREATE OR REPLACE VIEW change_frequency_summary AS
SELECT
    table_name,
    entity_id,
    entity_type,
    COUNT(*) AS total_changes,
    COUNT(DISTINCT field_name) AS fields_changed,
    COUNT(DISTINCT changed_by) AS change_sources,
    MIN(changed_at) AS first_change,
    MAX(changed_at) AS last_change,
    SUM(CASE WHEN is_correction THEN 1 ELSE 0 END) AS correction_count,
    SUM(CASE WHEN is_governance_relevant THEN 1 ELSE 0 END) AS governance_changes
FROM field_change_audit
GROUP BY table_name, entity_id, entity_type
ORDER BY total_changes DESC;


-- ═══════════════════════════════════════════════════════════════════════
-- BLOCK 6 — Record this migration in schema_change_log
-- ═══════════════════════════════════════════════════════════════════════

INSERT INTO schema_change_log (
    migration_version,
    migration_file,
    change_type,
    object_name,
    rationale,
    applied_at,
    applied_by
) VALUES (
    'v63',
    'v63_field_change_audit_security_camera.sql',
    'CREATE TABLE + TRIGGERS + VIEWS',
    'field_change_audit, meridian_capture_field_changes(), 24 triggers, 3 views',
    'Security camera: field-level audit trail on all 24 tracked tables. Every data change leaves a permanent fingerprint. Governance-relevant fields (company_id, stage, brand_name, source_url, etc.) are flagged automatically. Session variables (app.changed_by, app.change_source, app.enrichment_run_id) route attribution from enrichment scripts.',
    NOW(),
    'migration_v63'
);
