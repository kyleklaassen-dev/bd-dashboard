-- APPLIED 2026-06-19: writer enforcement — DRUGS ONLY (Phase-2 capstone, staged rollout).
-- Drugs-first per the runbook in PROPOSED_drugwriter_enforcement.sql. companies + catalysts
-- triggers are intentionally NOT created here — enable them only after drugs proves clean
-- through a full nightly cycle. Function + drugs trigger; direct SQL/Management API is allowed
-- (request.headers NULL); only REST writes without X-Meridian-Actor=DrugWriter are blocked.

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

    -- No REST headers => direct SQL / admin / migration => allow.
    IF headers IS NULL THEN
        RETURN NEW;
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

-- DRUGS trigger only (companies/catalysts deferred to a later watched window).
DROP TRIGGER IF EXISTS trg_enforce_single_writer_drugs ON drugs;
CREATE TRIGGER trg_enforce_single_writer_drugs
    BEFORE INSERT OR UPDATE OR DELETE ON drugs
    FOR EACH ROW EXECUTE FUNCTION meridian_enforce_single_writer();

-- ROLLBACK (instant, lossless):
--   DROP TRIGGER IF EXISTS trg_enforce_single_writer_drugs ON drugs;
--   DROP FUNCTION IF EXISTS meridian_enforce_single_writer();
