-- ============================================================================
-- core_write_audit — extend audit mode to companies + catalysts
-- Applied 2026-06-19 via Management API. Reuses meridian_audit_core_writer()
-- (already created for drugs). Non-blocking; logs non-Writer writes only.
-- ============================================================================

DROP TRIGGER IF EXISTS trg_audit_core_writer_companies ON companies;
CREATE TRIGGER trg_audit_core_writer_companies
    BEFORE INSERT OR UPDATE OR DELETE ON companies
    FOR EACH ROW EXECUTE FUNCTION meridian_audit_core_writer();

DROP TRIGGER IF EXISTS trg_audit_core_writer_catalysts ON catalysts;
CREATE TRIGGER trg_audit_core_writer_catalysts
    BEFORE INSERT OR UPDATE OR DELETE ON catalysts
    FOR EACH ROW EXECUTE FUNCTION meridian_audit_core_writer();

-- Rollback:
--   DROP TRIGGER IF EXISTS trg_audit_core_writer_companies ON companies;
--   DROP TRIGGER IF EXISTS trg_audit_core_writer_catalysts ON catalysts;
