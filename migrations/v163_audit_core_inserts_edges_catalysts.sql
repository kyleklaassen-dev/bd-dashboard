-- ═══════════════════════════════════════════════════════════════════════
-- v163 — Close the §A.4 audit gaps for the 4 core tables
-- ═══════════════════════════════════════════════════════════════════════
-- Builds on v63 field_change_audit ("security camera"). Two gaps remained after
-- §A.1 routed every core-table write through its Writer:
--   1. entity_edges + catalysts had NO audit trigger (v63 audited entity_relationships
--      + catalyst_calendar, not these) — yet they are now single-writer.
--   2. v63 only audits UPDATEs (TG_OP != 'UPDATE' → return). New-record CREATES were
--      never captured.
--   3. WHO/WHY: also read changed_by/change_reason from PostgREST request headers
--      (x-meridian-actor / x-meridian-reason) the Writers send, so attribution is the
--      Writer/script, not just the DB role.
--
-- SAFETY:
--  • The existing shared function meridian_capture_field_changes() and its ~30 triggers
--    are NOT modified (zero blast radius).
--  • The new function meridian_capture_core_changes() swallows its own errors
--    (EXCEPTION WHEN OTHERS → RETURN NEW) so an audit failure can NEVER block a real write.
--  • Triggers are AFTER (the row is already written) for the same reason.
--  • drugs/companies keep their proven v63 BEFORE UPDATE trigger for field-level update
--    audit; we only ADD an AFTER INSERT trigger for them (no double-audit).
-- ═══════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION meridian_capture_core_changes()
RETURNS TRIGGER AS $$
DECLARE
    nj JSONB; oj JSONB; hdrs JSON;
    actor TEXT; reason TEXT; src TEXT;
    ck TEXT; ov TEXT; nv TEXT; eid TEXT; etype TEXT;
    skip TEXT[] := ARRAY['updated_at','created_at','enriched_at','reviewed_at',
                         'detected_at','validated_at','resolved_at','changed_at',
                         'enrichment_run_id','last_enrichment_run_id','id'];
BEGIN
    nj := to_jsonb(NEW);
    BEGIN hdrs := NULLIF(current_setting('request.headers', true), '')::json;
    EXCEPTION WHEN OTHERS THEN hdrs := NULL; END;
    actor  := COALESCE(current_setting('app.changed_by', true), hdrs->>'x-meridian-actor', session_user);
    reason := COALESCE(current_setting('app.change_reason', true), hdrs->>'x-meridian-reason');
    src    := COALESCE(current_setting('app.change_source', true), 'unknown');
    eid    := COALESCE(nj->>'id', nj->>'drug_id', nj->>'company_id', 'unknown');
    etype  := CASE TG_TABLE_NAME
                WHEN 'drugs' THEN 'drug' WHEN 'companies' THEN 'company'
                WHEN 'entity_edges' THEN 'edge' WHEN 'catalysts' THEN 'catalyst'
                ELSE TG_TABLE_NAME END;

    IF TG_OP = 'INSERT' THEN
        INSERT INTO field_change_audit (
            table_name, entity_id, entity_type, field_name, old_value, new_value,
            changed_at, changed_by, change_source, change_reason, is_governance_relevant, row_snapshot)
        VALUES (TG_TABLE_NAME, eid, etype, '__record_created__', NULL,
                COALESCE(nj->>'name', nj->>'label', nj->>'predicate', eid),
                NOW(), actor, src, reason, TRUE, nj);
    ELSE
        oj := to_jsonb(OLD);
        FOR ck IN SELECT jsonb_object_keys(nj) LOOP
            CONTINUE WHEN ck = ANY(skip);
            ov := oj->>ck; nv := nj->>ck;
            IF ov IS DISTINCT FROM nv THEN
                INSERT INTO field_change_audit (
                    table_name, entity_id, entity_type, field_name, old_value, new_value,
                    changed_at, changed_by, change_source, change_reason)
                VALUES (TG_TABLE_NAME, eid, etype, ck, ov, nv, NOW(), actor, src, reason);
            END IF;
        END LOOP;
    END IF;
    RETURN NEW;
EXCEPTION WHEN OTHERS THEN
    RETURN NEW;  -- audit must NEVER block a real write
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- entity_edges + catalysts: full INSERT + UPDATE audit (they had none)
DROP TRIGGER IF EXISTS audit_entity_edges_core ON entity_edges;
CREATE TRIGGER audit_entity_edges_core AFTER INSERT OR UPDATE ON entity_edges
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_core_changes();
DROP TRIGGER IF EXISTS audit_catalysts_core ON catalysts;
CREATE TRIGGER audit_catalysts_core AFTER INSERT OR UPDATE ON catalysts
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_core_changes();

-- drugs + companies: add INSERT auditing (their UPDATE audit already lives in v63)
DROP TRIGGER IF EXISTS audit_drugs_inserts ON drugs;
CREATE TRIGGER audit_drugs_inserts AFTER INSERT ON drugs
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_core_changes();
DROP TRIGGER IF EXISTS audit_companies_inserts ON companies;
CREATE TRIGGER audit_companies_inserts AFTER INSERT ON companies
    FOR EACH ROW EXECUTE FUNCTION meridian_capture_core_changes();
