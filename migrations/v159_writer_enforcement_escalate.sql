-- ============================================================================
-- v159_writer_enforcement_escalate.sql
-- Stage 4 (enforcement) — STEP 2: escalate WARN -> EXCEPTION, PER RULE.
-- Created: 2026-06-16 · Author: claude_agent
--
-- v157 installed observe-only triggers (log to governance_enforcement_log).
-- After cleaning the data (v158 + dedupe merges -> orphan drug edges = 0;
-- stage flips -> brand_implies_approved = 0), we now hard-block the rules that
-- are clean, while the rest keep logging (warn) until their data is fixed.
--
-- Enforcement is now PER RULE (table governance_enforced_rules), not a single
-- global flag — so we can harden incrementally:
--   ENFORCED NOW:  edges.subject_drug_orphan, edges.object_drug_orphan
--                  (referential integrity; 0 current violations; watch was clean)
--   STILL WARN:    catalysts.must_link        (26 unlinked catalysts to link first)
--                  drugs.company_id_required  (discovery inserts code-named drugs)
--                  drugs.brand_implies_approved / dash_brand, companies.*  (data quality)
-- To harden another rule later: INSERT its id into governance_enforced_rules.
-- To roll back: DELETE it (or TRUNCATE the table -> everything back to warn).
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS governance_enforced_rules (
    rule        TEXT PRIMARY KEY,
    enforced_at TIMESTAMPTZ DEFAULT NOW(),
    note        TEXT
);

INSERT INTO governance_enforced_rules(rule, note) VALUES
 ('edges.subject_drug_orphan','referential integrity; data clean as of v158+merges'),
 ('edges.object_drug_orphan','referential integrity; data clean as of v158+merges')
ON CONFLICT (rule) DO NOTHING;

-- mark the program as having begun enforcement (display/back-compat)
UPDATE governance_enforcement_config SET mode='exception', updated_at=NOW() WHERE singleton;

-- _gov_flag: log as before, then RAISE for any rule that is in the enforced set.
CREATE OR REPLACE FUNCTION _gov_flag(
    p_table text, p_entity text, p_op text, p_rule text, p_detail text, p_hard boolean
) RETURNS void AS $$
DECLARE m text := _gov_enforcement_mode();
        enforced boolean := EXISTS (SELECT 1 FROM governance_enforced_rules WHERE rule = p_rule);
BEGIN
    INSERT INTO governance_enforcement_log(table_name, entity_id, op, rule, severity, detail, mode)
    VALUES (p_table, p_entity, p_op, p_rule,
            CASE WHEN enforced THEN 'blocked' WHEN p_hard THEN 'would_block' ELSE 'warn' END, p_detail, m);
    IF enforced THEN
        RAISE EXCEPTION 'governance violation [%]: % % — %', p_rule, p_table, p_entity, p_detail
            USING ERRCODE = 'check_violation';
    ELSE
        RAISE NOTICE 'governance[%/%]: % on % % — %', m,
            CASE WHEN p_hard THEN 'would_block' ELSE 'warn' END, p_rule, p_table, p_entity, p_detail;
    END IF;
END;
$$ LANGUAGE plpgsql;

INSERT INTO schema_change_log
    (migration_version, migration_file, change_type, object_name, field_name,
     old_definition, new_definition, rationale)
VALUES
('v159','v159_writer_enforcement_escalate.sql','create_table','governance_enforced_rules',NULL,
 NULL,'TABLE','Per-rule enforcement allow-list; presence => RAISE EXCEPTION in _gov_flag.'),
('v159','v159_writer_enforcement_escalate.sql','create_function','_gov_flag',NULL,
 'log + notice only','log + RAISE EXCEPTION for enforced rules',
 'Stage 4 STEP 2: hard-block the 2 edge referential rules; others stay warn.');

COMMIT;
