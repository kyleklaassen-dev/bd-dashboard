-- =============================================================================
-- vNN_description.sql  (forward migrations start at v2 — see migrations/README.md)
-- Migration: <one-line description of what this migration does>
-- Created: YYYY-MM-DD
-- Author:  claude_agent
--
-- Governance: Every migration MUST insert rows into schema_change_log at the
-- bottom of this file. One row per DDL object created/altered/dropped.
-- This is the Meridian anti-drift contract. No exceptions.
-- =============================================================================


-- =============================================================================
-- DDL CHANGES
-- Replace the examples below with your actual changes.
-- =============================================================================

-- Example: add a column
-- ALTER TABLE my_table ADD COLUMN IF NOT EXISTS new_column TEXT;

-- Example: create a table
-- CREATE TABLE IF NOT EXISTS new_table (
--     id   BIGSERIAL PRIMARY KEY,
--     name TEXT NOT NULL,
--     ...
-- );

-- Example: create a trigger
-- DROP TRIGGER IF EXISTS trg_capture_changes_new_table ON new_table;
-- CREATE TRIGGER trg_capture_changes_new_table
--     BEFORE UPDATE ON new_table
--     FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();


-- =============================================================================
-- MANDATORY: Register this migration in schema_change_log
--
-- change_type must be one of:
--   create_table | alter_table | create_view | drop_column | add_column |
--   rename_column | create_trigger | create_index | create_function |
--   seed_data | backfill | drop_table
--
-- old_definition: NULL if the object did not previously exist.
--                 Otherwise, the prior DDL or value (quoted string, e.g. 'TEXT NOT NULL').
-- new_definition: Brief summary of the new state (e.g. 'TEXT DEFAULT NULL', 'TABLE', 'TRIGGER').
-- rationale:      Why was this change made? Link to session notes or design doc if available.
-- =============================================================================

INSERT INTO schema_change_log
    (migration_version, migration_file, change_type, object_name,
     field_name, old_definition, new_definition, rationale)
VALUES
-- One row per DDL object. Add more rows as needed.
('vNN', 'vNN_description.sql', 'add_column',    'table_name',  'column_name',
 'NULL (did not exist)', 'TEXT DEFAULT NULL',
 'Reason this column was added'),

('vNN', 'vNN_description.sql', 'create_table',  'new_table',   NULL,
 NULL, 'TABLE',
 'Reason this table was created'),

('vNN', 'vNN_description.sql', 'create_trigger','trg_capture_changes_new_table', NULL,
 NULL, 'TRIGGER ON new_table',
 'Auto change capture added — add to tracked tables in v61_anti_drift_triggers.sql');


-- =============================================================================
-- HOW TO ADD A NEW TABLE TO CHANGE CAPTURE
--
-- When you create a new table that needs change tracking:
-- 1. Add the trigger here in this migration file:
--
--    DROP TRIGGER IF EXISTS trg_capture_changes_{tablename} ON {tablename};
--    CREATE TRIGGER trg_capture_changes_{tablename}
--        BEFORE UPDATE ON {tablename}
--        FOR EACH ROW EXECUTE FUNCTION meridian_capture_field_changes();
--
-- 2. Log it in schema_change_log (see template row above, change_type='create_trigger').
--
-- 3. Add the table name to the "tables" list in scripts/apply_v61_full.py
--    so it is documented as a tracked table going forward.
-- =============================================================================
