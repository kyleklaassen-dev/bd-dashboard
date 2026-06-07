-- =============================================================================
-- v61_anti_drift_triggers.sql
-- Meridian Anti-Drift System
-- Created: 2026-05-28
-- Author:  claude_agent
--
-- Purpose: Answers "How do I know every variable/table/column change is tracked?"
--          1. schema_change_log — migration registry: one row per DDL change
--          2. meridian_capture_field_changes() — generic BEFORE UPDATE trigger
--             that writes old/new values to enriched_field_log automatically
--          3. Triggers on 17 critical tables
--          4. Backfill: 65 rows covering v55-v60_p1
-- =============================================================================


-- =============================================================================
-- PART 1 — schema_change_log (the migration registry)
-- Every future migration MUST insert rows here at the end of the file.
-- =============================================================================

CREATE TABLE IF NOT EXISTS schema_change_log (
    id               BIGSERIAL PRIMARY KEY,
    migration_version TEXT NOT NULL,        -- e.g. 'v61'
    migration_file   TEXT NOT NULL,          -- filename of the .sql file
    change_type      TEXT NOT NULL CHECK (change_type IN (
                         'create_table', 'alter_table', 'create_view',
                         'drop_column',  'add_column',  'rename_column',
                         'create_trigger','create_index','create_function',
                         'seed_data',    'backfill',    'drop_table'
                     )),
    object_name      TEXT NOT NULL,          -- table / view / trigger / function
    field_name       TEXT,                   -- column name (add_column / alter_table)
    old_definition   TEXT,                   -- NULL = did not exist before
    new_definition   TEXT,                   -- new DDL or value summary
    rationale        TEXT,                   -- why was this change made?
    applied_at       TIMESTAMPTZ DEFAULT NOW(),
    applied_by       TEXT DEFAULT 'claude_agent',
    session_notes    TEXT                    -- link to NEXT_SESSION.md or task
);

CREATE INDEX IF NOT EXISTS scl_version_idx    ON schema_change_log(migration_version);
CREATE INDEX IF NOT EXISTS scl_object_idx     ON schema_change_log(object_name);
CREATE INDEX IF NOT EXISTS scl_applied_at_idx ON schema_change_log(applied_at DESC);


-- =============================================================================
-- PART 2 — Backfill prior migrations (v55 – v60_p1)
-- Applied via apply_v61_backfill.py — see that script for the INSERT statement.
-- Resulting rows: 65 across 9 prior versions.
-- =============================================================================
-- (executed externally — see /tmp/apply_v61_backfill.py)


-- =============================================================================
-- PART 3 — Generic field change capture function
--
-- Fires BEFORE UPDATE on any tracked table.
-- For each column that changed: writes one row to enriched_field_log with
--   old_value  = the value BEFORE this UPDATE
--   enriched_value = the value AFTER this UPDATE
--   label_source = 'auto_trigger'
--   field_label  = 'pending'  (Kyle can review/approve later)
-- =============================================================================

CREATE OR REPLACE FUNCTION meridian_capture_field_changes()
RETURNS TRIGGER AS $$
DECLARE
    col_record     RECORD;
    old_val        TEXT;
    new_val        TEXT;
    entity_id_val  TEXT;
BEGIN
    -- Resolve the entity id from the incoming row
    BEGIN
        entity_id_val := (row_to_json(NEW)->>'id')::TEXT;
    EXCEPTION WHEN OTHERS THEN
        entity_id_val := 'unknown';
    END;

    -- Walk every non-housekeeping column; emit one enriched_field_log row per change
    FOR col_record IN
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name   = TG_TABLE_NAME
          AND column_name NOT IN (
              'id', 'created_at', 'updated_at', 'enriched_at',
              'detected_at', 'reviewed_at', 'scored_at',
              'enrichment_run_id', 'correction_id'
          )
        ORDER BY ordinal_position
    LOOP
        EXECUTE format('SELECT ($1).%I::TEXT', col_record.column_name)
            INTO old_val USING OLD;
        EXECUTE format('SELECT ($1).%I::TEXT', col_record.column_name)
            INTO new_val USING NEW;

        IF old_val IS DISTINCT FROM new_val THEN
            INSERT INTO enriched_field_log (
                entity_type,
                entity_id,
                field_name,
                old_value,
                old_value_captured_at,
                enriched_value,
                enriched_at,
                label_source,
                field_label,
                was_changed
            ) VALUES (
                TG_TABLE_NAME,
                entity_id_val,
                col_record.column_name,
                old_val,
                NOW(),
                new_val,
                NOW(),
                'auto_trigger',
                'pending',
                TRUE
            );
        END IF;
    END LOOP;

    -- Touch updated_at if the column exists on this table (silently skip if not)
    BEGIN
        NEW.updated_at := NOW();
    EXCEPTION WHEN OTHERS THEN
        NULL;
    END;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- =============================================================================
-- PART 4 — Apply trigger to all 17 critical tracked tables
-- All tables confirmed present in information_schema before application.
-- =============================================================================

DROP TRIGGER IF EXISTS trg_capture_changes_drugs ON drugs;
CREATE TRIGGER trg_capture_changes_drugs
    BEFORE UPDATE ON drugs
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS trg_capture_changes_companies ON companies;
CREATE TRIGGER trg_capture_changes_companies
    BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS trg_capture_changes_molecule_intelligence ON molecule_intelligence;
CREATE TRIGGER trg_capture_changes_molecule_intelligence
    BEFORE UPDATE ON molecule_intelligence
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS trg_capture_changes_drug_competitive_scores ON drug_competitive_scores;
CREATE TRIGGER trg_capture_changes_drug_competitive_scores
    BEFORE UPDATE ON drug_competitive_scores
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS trg_capture_changes_entity_relationships ON entity_relationships;
CREATE TRIGGER trg_capture_changes_entity_relationships
    BEFORE UPDATE ON entity_relationships
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS trg_capture_changes_company_partnerships ON company_partnerships;
CREATE TRIGGER trg_capture_changes_company_partnerships
    BEFORE UPDATE ON company_partnerships
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS trg_capture_changes_deals ON deals;
CREATE TRIGGER trg_capture_changes_deals
    BEFORE UPDATE ON deals
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS trg_capture_changes_drug_stage_history ON drug_stage_history;
CREATE TRIGGER trg_capture_changes_drug_stage_history
    BEFORE UPDATE ON drug_stage_history
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS trg_capture_changes_catalyst_calendar ON catalyst_calendar;
CREATE TRIGGER trg_capture_changes_catalyst_calendar
    BEFORE UPDATE ON catalyst_calendar
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS trg_capture_changes_sop_registry ON sop_registry;
CREATE TRIGGER trg_capture_changes_sop_registry
    BEFORE UPDATE ON sop_registry
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS trg_capture_changes_drug_pk_parameters ON drug_pk_parameters;
CREATE TRIGGER trg_capture_changes_drug_pk_parameters
    BEFORE UPDATE ON drug_pk_parameters
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS trg_capture_changes_drug_pd_parameters ON drug_pd_parameters;
CREATE TRIGGER trg_capture_changes_drug_pd_parameters
    BEFORE UPDATE ON drug_pd_parameters
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS trg_capture_changes_drug_biomarkers ON drug_biomarkers;
CREATE TRIGGER trg_capture_changes_drug_biomarkers
    BEFORE UPDATE ON drug_biomarkers
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS trg_capture_changes_non_responder_profiles ON non_responder_profiles;
CREATE TRIGGER trg_capture_changes_non_responder_profiles
    BEFORE UPDATE ON non_responder_profiles
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS trg_capture_changes_clinical_evidence_items ON clinical_evidence_items;
CREATE TRIGGER trg_capture_changes_clinical_evidence_items
    BEFORE UPDATE ON clinical_evidence_items
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS trg_capture_changes_indication_patient_intelligence ON indication_patient_intelligence;
CREATE TRIGGER trg_capture_changes_indication_patient_intelligence
    BEFORE UPDATE ON indication_patient_intelligence
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();

DROP TRIGGER IF EXISTS trg_capture_changes_payer_tpp_criteria ON payer_tpp_criteria;
CREATE TRIGGER trg_capture_changes_payer_tpp_criteria
    BEFORE UPDATE ON payer_tpp_criteria
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();


-- =============================================================================
-- PART 5 — Governance rule comment (see docs/migration_template.sql)
-- Every future migration file MUST include an INSERT into schema_change_log
-- at the end of the file. Template:
--
-- INSERT INTO schema_change_log
--     (migration_version, migration_file, change_type, object_name,
--      field_name, old_definition, new_definition, rationale)
-- VALUES
-- ('vNN', 'vNN_description.sql', 'add_column', 'table_name',
--  'column_name', 'NULL (did not exist)', 'TEXT DEFAULT NULL',
--  'Reason this column was added');
-- =============================================================================


-- =============================================================================
-- PART 6 — Record THIS migration in schema_change_log
-- (Also executed via apply_v61_backfill.py for the 20 v61 rows)
-- =============================================================================

INSERT INTO schema_change_log
    (migration_version, migration_file, change_type, object_name, field_name,
     old_definition, new_definition, rationale)
VALUES
('v61','v61_anti_drift_triggers.sql','create_table','schema_change_log',NULL,
 NULL,'TABLE',
 'Meta-table tracking every schema change for drift prevention. The migration registry.'),
('v61','v61_anti_drift_triggers.sql','create_function','meridian_capture_field_changes',NULL,
 NULL,'FUNCTION',
 'Generic BEFORE UPDATE trigger: captures old/new field values into enriched_field_log'),
('v61','v61_anti_drift_triggers.sql','create_trigger','trg_capture_changes_drugs',NULL,
 NULL,'TRIGGER ON drugs','Auto before/after capture on every UPDATE to drugs'),
('v61','v61_anti_drift_triggers.sql','create_trigger','trg_capture_changes_companies',NULL,
 NULL,'TRIGGER ON companies','Auto before/after capture on every UPDATE to companies'),
('v61','v61_anti_drift_triggers.sql','create_trigger','trg_capture_changes_molecule_intelligence',NULL,
 NULL,'TRIGGER ON molecule_intelligence',
 'Solves G-04: MI field changes now always recorded with old/new values'),
('v61','v61_anti_drift_triggers.sql','create_trigger','trg_capture_changes_drug_competitive_scores',NULL,
 NULL,'TRIGGER ON drug_competitive_scores','Competitive score drift detection'),
('v61','v61_anti_drift_triggers.sql','create_trigger','trg_capture_changes_entity_relationships',NULL,
 NULL,'TRIGGER ON entity_relationships','Relationship edge change capture'),
('v61','v61_anti_drift_triggers.sql','create_trigger','trg_capture_changes_company_partnerships',NULL,
 NULL,'TRIGGER ON company_partnerships',
 'Partnership change capture: licensing attribution drift prevention'),
('v61','v61_anti_drift_triggers.sql','create_trigger','trg_capture_changes_deals',NULL,
 NULL,'TRIGGER ON deals','Deal field change capture with before/after state'),
('v61','v61_anti_drift_triggers.sql','create_trigger','trg_capture_changes_drug_stage_history',NULL,
 NULL,'TRIGGER ON drug_stage_history','Stage history change capture'),
('v61','v61_anti_drift_triggers.sql','create_trigger','trg_capture_changes_catalyst_calendar',NULL,
 NULL,'TRIGGER ON catalyst_calendar','Catalyst date drift detection'),
('v61','v61_anti_drift_triggers.sql','create_trigger','trg_capture_changes_sop_registry',NULL,
 NULL,'TRIGGER ON sop_registry','SOP version change capture'),
('v61','v61_anti_drift_triggers.sql','create_trigger','trg_capture_changes_drug_pk_parameters',NULL,
 NULL,'TRIGGER ON drug_pk_parameters','PK parameter change capture'),
('v61','v61_anti_drift_triggers.sql','create_trigger','trg_capture_changes_drug_pd_parameters',NULL,
 NULL,'TRIGGER ON drug_pd_parameters','PD parameter change capture'),
('v61','v61_anti_drift_triggers.sql','create_trigger','trg_capture_changes_drug_biomarkers',NULL,
 NULL,'TRIGGER ON drug_biomarkers','Biomarker association change capture'),
('v61','v61_anti_drift_triggers.sql','create_trigger','trg_capture_changes_non_responder_profiles',NULL,
 NULL,'TRIGGER ON non_responder_profiles','Non-responder profile change capture'),
('v61','v61_anti_drift_triggers.sql','create_trigger','trg_capture_changes_clinical_evidence_items',NULL,
 NULL,'TRIGGER ON clinical_evidence_items','Clinical evidence change capture'),
('v61','v61_anti_drift_triggers.sql','create_trigger','trg_capture_changes_indication_patient_intelligence',NULL,
 NULL,'TRIGGER ON indication_patient_intelligence','Patient intelligence change capture'),
('v61','v61_anti_drift_triggers.sql','create_trigger','trg_capture_changes_payer_tpp_criteria',NULL,
 NULL,'TRIGGER ON payer_tpp_criteria','Payer TPP change capture'),
('v61','v61_anti_drift_triggers.sql','seed_data','schema_change_log',NULL,
 NULL,'85 rows total (65 backfill + 20 v61)',
 'Backfilled prior migrations v55-v60_p1 into schema_change_log for continuity');
