-- ============================================================================
-- PROPOSED_drugwriter_enforcement.sql  —  STAGED, DO NOT APPLY UNATTENDED
-- ============================================================================
-- Phase-2 capstone (STABILIZATION_PLAN). Makes the Single Writer Pattern REAL by
-- having the database physically reject any direct write to a core table that did
-- not come through that table's Writer.
--
-- HOW IT WORKS
--   Every Writer announces itself on the REST request via the `X-Meridian-Actor`
--   header (client.set_audit_context -> _headers; e.g. "DrugWriter"). PostgREST
--   exposes request headers to SQL as the transaction-local GUC
--   `request.headers`. This BEFORE trigger reads that header and blocks the write
--   unless the actor is the sanctioned Writer for the table.
--
--   Direct SQL / psql / the Supabase Management API do NOT set `request.headers`,
--   so those (migrations, admin fixes, this file) are intentionally ALLOWED — the
--   boundary targets the application/REST write paths, which is where the 20
--   bypasses lived.
--
-- PRECONDITION (must be true before applying — verify with audit_core_writers.py):
--   scripts/maintenance/audit_core_writers.py --strict   # only the _catalyst_upsert
--                                                        # docstring false-positive
--   i.e. ZERO real direct writes to drugs/companies/catalysts remain in code.
--
-- ROLLOUT (Kyle + a watch window — NOT autonomous):
--   1. Re-run the audit above; confirm clean.
--   2. Apply on drugs ONLY first (comment out the companies/catalysts triggers).
--   3. Watch one full nightly cycle (research -> enrichment -> validation). A
--      blocked legitimate write surfaces as a 4xx with the message below.
--   4. If clean, enable companies + catalysts. If anything breaks, run the
--      ROLLBACK section at the bottom — it is instant and lossless.
-- ============================================================================

-- Allowed actor(s) per table. Add more only with review.
CREATE OR REPLACE FUNCTION meridian_enforce_single_writer()
RETURNS trigger AS $$
DECLARE
    headers   json;
    actor     text;
    allowed   text;
BEGIN
    -- request.headers is only set for PostgREST (REST API) requests.
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

-- ── drugs (apply FIRST, watch one nightly cycle) ────────────────────────────
DROP TRIGGER IF EXISTS trg_enforce_single_writer_drugs ON drugs;
CREATE TRIGGER trg_enforce_single_writer_drugs
    BEFORE INSERT OR UPDATE OR DELETE ON drugs
    FOR EACH ROW EXECUTE FUNCTION meridian_enforce_single_writer();

-- ── companies (enable after drugs proves clean) ─────────────────────────────
DROP TRIGGER IF EXISTS trg_enforce_single_writer_companies ON companies;
CREATE TRIGGER trg_enforce_single_writer_companies
    BEFORE INSERT OR UPDATE OR DELETE ON companies
    FOR EACH ROW EXECUTE FUNCTION meridian_enforce_single_writer();

-- ── catalysts (enable after drugs proves clean) ─────────────────────────────
DROP TRIGGER IF EXISTS trg_enforce_single_writer_catalysts ON catalysts;
CREATE TRIGGER trg_enforce_single_writer_catalysts
    BEFORE INSERT OR UPDATE OR DELETE ON catalysts
    FOR EACH ROW EXECUTE FUNCTION meridian_enforce_single_writer();

-- ── VERIFY (run after apply) ────────────────────────────────────────────────
-- A bare REST PATCH with no writer header must now fail:
--   curl -X PATCH "$SUPABASE_URL/rest/v1/drugs?id=eq.<known_id>" \
--        -H "apikey: $KEY" -H "Authorization: Bearer $KEY" \
--        -H "Content-Type: application/json" -d '{"stage":"Phase 2"}'
--   -> expects 400 with the 'Single Writer Pattern' message above.
-- A DrugWriter().update_fields(<id>, {...}) call must still succeed.

-- ============================================================================
-- ROLLBACK (instant, lossless) — run if any legitimate write is blocked:
--   DROP TRIGGER IF EXISTS trg_enforce_single_writer_drugs     ON drugs;
--   DROP TRIGGER IF EXISTS trg_enforce_single_writer_companies ON companies;
--   DROP TRIGGER IF EXISTS trg_enforce_single_writer_catalysts ON catalysts;
--   DROP FUNCTION IF EXISTS meridian_enforce_single_writer();
-- ============================================================================
