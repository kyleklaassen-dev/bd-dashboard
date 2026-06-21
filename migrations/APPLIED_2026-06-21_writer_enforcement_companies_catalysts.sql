-- Writer enforcement — companies + catalysts (Phase-2 step 2). APPLIED 2026-06-21.
-- Completes the Single Writer Pattern: all 4 core tables now DB-enforced
-- (drugs live since APPLIED_2026-06-19_writer_enforcement_drugs.sql; entity_edges via UNIQUE constraint).
--
-- Applied MANUALLY via the Management API (scripts/apply_sql_migration.py) during the
-- crons-paused travel window — NOT via writer-enforcement-rollout.yml (that automation is now
-- obsolete and the workflow is disabled). Pre-flight was clean: audit_core_writers.py --strict
-- (0 direct writes) + tests/run_all.py (ALL SUITES GREEN).
--
-- Verified live after apply (no-op same-value REST round-trips):
--   companies  headerless PATCH -> 400 ; X-Meridian-Actor: CompanyWriter  -> 204
--   catalysts  headerless PATCH -> 400 ; X-Meridian-Actor: CatalystWriter -> 204
--
-- Idempotent: function is CREATE OR REPLACE; triggers are DROP IF EXISTS + CREATE.

CREATE OR REPLACE FUNCTION meridian_enforce_single_writer()
RETURNS trigger AS $$
DECLARE
    headers   json;
    actor     text;
    allowed   text;
BEGIN
    BEGIN
        headers := current_setting('request.headers', true)::json;
    EXCEPTION WHEN others THEN
        headers := NULL;
    END;
    IF headers IS NULL THEN
        RETURN NEW;   -- direct SQL / admin / migration => allow
    END IF;
    actor := headers ->> 'x-meridian-actor';
    allowed := CASE TG_TABLE_NAME
        WHEN 'drugs'      THEN 'DrugWriter'
        WHEN 'companies'  THEN 'CompanyWriter'
        WHEN 'catalysts'  THEN 'CatalystWriter'
        ELSE NULL
    END;
    IF allowed IS NULL OR actor IS DISTINCT FROM allowed THEN
        RAISE EXCEPTION
            'Single Writer Pattern: % is write-protected. Route through % (got X-Meridian-Actor=%). See src/meridian/database/.',
            TG_TABLE_NAME, allowed, COALESCE(actor, '<none>')
        USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_enforce_single_writer_companies ON companies;
CREATE TRIGGER trg_enforce_single_writer_companies
    BEFORE INSERT OR UPDATE OR DELETE ON companies
    FOR EACH ROW EXECUTE FUNCTION meridian_enforce_single_writer();

DROP TRIGGER IF EXISTS trg_enforce_single_writer_catalysts ON catalysts;
CREATE TRIGGER trg_enforce_single_writer_catalysts
    BEFORE INSERT OR UPDATE OR DELETE ON catalysts
    FOR EACH ROW EXECUTE FUNCTION meridian_enforce_single_writer();

-- ROLLBACK (instant, lossless):
--   DROP TRIGGER IF EXISTS trg_enforce_single_writer_companies ON companies;
--   DROP TRIGGER IF EXISTS trg_enforce_single_writer_catalysts ON catalysts;
