-- ============================================================================
-- core_write_audit (drugs) — AUDIT MODE for the Single Writer Pattern
-- Applied 2026-06-19 via Management API. Phase 1 of enforcement rollout.
-- ============================================================================
-- Logs any write to `drugs` that did NOT come through DrugWriter (identified by
-- the X-Meridian-Actor request header), but NEVER blocks the write. This proves
-- at RUNTIME that nothing bypasses the writer (stronger than the static audit,
-- which can't see dynamic table names) without any risk to the live pipeline.
--
-- After N nightlies with core_write_audit empty for `drugs`, flip to hard-block
-- by replacing the body's INSERT with a RAISE EXCEPTION (see
-- PROPOSED_drugwriter_enforcement.sql). Rollback: DROP TRIGGER + FUNCTION + TABLE.
-- ============================================================================

CREATE TABLE IF NOT EXISTS core_write_audit (
    id          bigserial PRIMARY KEY,
    table_name  text        NOT NULL,
    op          text        NOT NULL,
    actor       text,
    occurred_at timestamptz NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION meridian_audit_core_writer()
RETURNS trigger AS $$
DECLARE
    headers json;
    actor   text;
    allowed text;
BEGIN
    -- The whole body is exception-guarded: auditing must NEVER break a write.
    BEGIN
        headers := current_setting('request.headers', true)::json;
        IF headers IS NOT NULL THEN                      -- a PostgREST (app) write
            actor   := headers ->> 'x-meridian-actor';
            allowed := CASE TG_TABLE_NAME
                           WHEN 'drugs'     THEN 'DrugWriter'
                           WHEN 'companies' THEN 'CompanyWriter'
                           WHEN 'catalysts' THEN 'CatalystWriter'
                           ELSE NULL
                       END;
            IF allowed IS NULL OR actor IS DISTINCT FROM allowed THEN
                INSERT INTO core_write_audit(table_name, op, actor)
                VALUES (TG_TABLE_NAME, TG_OP, COALESCE(actor, '<none>'));
            END IF;
        END IF;
    EXCEPTION WHEN OTHERS THEN
        NULL;
    END;
    -- Non-blocking: return the correct row for the op so the write proceeds.
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_core_writer_drugs ON drugs;
CREATE TRIGGER trg_audit_core_writer_drugs
    BEFORE INSERT OR UPDATE OR DELETE ON drugs
    FOR EACH ROW EXECUTE FUNCTION meridian_audit_core_writer();
