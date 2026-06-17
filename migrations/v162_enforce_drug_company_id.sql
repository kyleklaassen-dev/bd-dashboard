-- ============================================================================
-- v162_enforce_drug_company_id.sql
-- Stage 4 — harden drugs.company_id_required with a discovery exception.
-- Created: 2026-06-16 · Author: claude_agent
--
-- Policy: every drug needs an originator company_id (Constitution §5) — EXCEPT
-- auto-discovery records (discovery_status='auto'), which the harvesters insert
-- before the originator is resolved (ct_gov_sync / deep_enrich_intel /
-- company_enrichment all stamp 'auto' inline; approve_discovery later promotes
-- to 'promoted' with the company set). So:
--   * INSERT of a manual/seeded/established drug without company_id  -> BLOCK
--   * INSERT of an auto-discovery drug without company_id            -> allow
-- Enforced on INSERT only (promotion UPDATEs are not blocked yet — stays WARN-
-- able). All 12 current company-less drugs are 'auto', so 0 violations today.
-- ============================================================================

BEGIN;

CREATE OR REPLACE FUNCTION enforce_drug_governance() RETURNS trigger AS $$
DECLARE approved_ok boolean := lower(coalesce(NEW.stage,'')) LIKE 'approved%';
BEGIN
    -- dash/empty brand is invalid (would normalize to NULL in EXCEPTION mode)
    IF NEW.brand_name IN ('—','-','') THEN
        PERFORM _gov_flag('drugs', NEW.id, TG_OP, 'drugs.dash_brand',
            format('brand_name=%L is a placeholder; should be NULL', NEW.brand_name), false);
    ELSIF NEW.brand_name IS NOT NULL AND NOT approved_ok THEN
        PERFORM _gov_flag('drugs', NEW.id, TG_OP, 'drugs.brand_implies_approved',
            format('brand_name=%L but stage=%L (not approved%%)', NEW.brand_name, NEW.stage), false);
    END IF;
    -- originator company required at insert, EXCEPT for auto-discovery records
    IF TG_OP = 'INSERT' AND NEW.company_id IS NULL
       AND coalesce(NEW.discovery_status,'') <> 'auto' THEN
        PERFORM _gov_flag('drugs', NEW.id, 'INSERT', 'drugs.company_id_required',
            format('inserted without company_id (originator); discovery_status=%L is not auto',
                   NEW.discovery_status), true);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

INSERT INTO governance_enforced_rules(rule, note) VALUES
 ('drugs.company_id_required','originator required on insert except discovery_status=auto; 0 violations 2026-06-16')
ON CONFLICT (rule) DO NOTHING;

INSERT INTO schema_change_log
    (migration_version, migration_file, change_type, object_name, field_name,
     old_definition, new_definition, rationale)
VALUES
('v162','v162_enforce_drug_company_id.sql','create_function','enforce_drug_governance',NULL,
 'company_id_required: INSERT + NULL (warn)',
 'company_id_required: INSERT + NULL + discovery_status<>auto (enforced)',
 'Stage 4: enforce originator on insert for established drugs; allow auto-discovery transient.');

COMMIT;
