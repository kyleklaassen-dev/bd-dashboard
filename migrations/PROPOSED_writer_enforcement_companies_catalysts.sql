-- Writer enforcement — companies + catalysts (Phase-2 step 2).
-- Applied automatically by .github/workflows/writer-enforcement-rollout.yml ONLY after the
-- overnight cron proves drugs enforcement is clean (see scripts/maintenance/writer_enforcement_rollout.py).
-- Idempotent: function is CREATE OR REPLACE; triggers are DROP IF EXISTS + CREATE.
-- The drugs trigger is already live (APPLIED_2026-06-19_writer_enforcement_drugs.sql).

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
