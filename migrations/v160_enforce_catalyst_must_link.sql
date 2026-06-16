-- ============================================================================
-- v160_enforce_catalyst_must_link.sql
-- Stage 4 — harden catalysts.must_link (after linking the 26 unlinked catalysts).
-- Created: 2026-06-16 · Author: claude_agent
--
-- The original rule fired only on (drug_id NULL AND company_id NULL). But area-
-- level conference/market catalysts legitimately have no single drug/company —
-- they are anchored by area_id/target_id/indication_id (every catalyst in the
-- table has at least one anchor; 0 are truly orphaned). So the TRUE invariant is
-- "a catalyst must be anchored to a tracked entity": drug OR company OR area OR
-- target OR indication. Broaden the check, then enforce it.
-- ============================================================================

BEGIN;

-- broaden the rule to "any anchor"
CREATE OR REPLACE FUNCTION enforce_catalyst_governance() RETURNS trigger AS $$
BEGIN
    IF NEW.drug_id IS NULL AND NEW.company_id IS NULL
       AND NEW.area_id IS NULL AND NEW.target_id IS NULL AND NEW.indication_id IS NULL THEN
        PERFORM _gov_flag('catalysts', NEW.id::text, TG_OP, 'catalysts.must_link',
            'catalyst not anchored to any entity (drug/company/area/target/indication)', true);
    END IF;
    IF NEW.catalyst_date IS NULL THEN
        PERFORM _gov_flag('catalysts', NEW.id::text, TG_OP, 'catalysts.date_required',
            'catalyst_date is NULL', false);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- enforce it (0 current violations)
INSERT INTO governance_enforced_rules(rule, note) VALUES
 ('catalysts.must_link','catalyst must anchor to drug/company/area; 26 unlinked resolved 2026-06-16')
ON CONFLICT (rule) DO NOTHING;

INSERT INTO schema_change_log
    (migration_version, migration_file, change_type, object_name, field_name,
     old_definition, new_definition, rationale)
VALUES
('v160','v160_enforce_catalyst_must_link.sql','create_function','enforce_catalyst_governance',NULL,
 'must_link = drug OR company','must_link = drug OR company OR area OR target OR indication',
 'Broaden to the true anchor invariant; then enforce (RAISE EXCEPTION).');

COMMIT;
