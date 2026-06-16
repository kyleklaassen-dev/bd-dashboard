-- ============================================================================
-- v157_writer_enforcement_warn.sql
-- Stage 4 (enforcement) — STEP 1 of 2: WARN MODE.
-- Created: 2026-06-16 · Author: claude_agent
--
-- Makes the Writer invariants observable at the database layer for ALL writers,
-- as a backstop behind DrugWriter/CompanyWriter/CatalystWriter/EdgeWriter
-- (Constitution §4/§6, governance_table.md). This step is OBSERVE-ONLY:
--   * mutates nothing (no NEW.* changes)
--   * blocks nothing (never RAISE EXCEPTION)
--   * records every invariant breach to governance_enforcement_log (REST-queryable)
--     and emits a RAISE NOTICE (Postgres log).
--
-- Escalation to EXCEPTION is a separate, evidence-driven migration (STEP 2)
-- authored AFTER watching one live pipeline cycle. The enforcement MODE lives in
-- a one-row config table so escalation does not require redefining functions —
-- but in WARN mode the functions only ever log.
--
-- Coexists with the v61 anti-drift BEFORE UPDATE capture triggers (different name,
-- non-mutating, so trigger order is irrelevant).
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 0 — config (the enforcement mode switch) + the observability log
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS governance_enforcement_config (
    singleton  BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    mode       TEXT NOT NULL DEFAULT 'warn' CHECK (mode IN ('warn','exception')),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by TEXT DEFAULT 'claude_agent'
);
INSERT INTO governance_enforcement_config (singleton, mode)
VALUES (TRUE, 'warn')
ON CONFLICT (singleton) DO NOTHING;

CREATE TABLE IF NOT EXISTS governance_enforcement_log (
    id          BIGSERIAL PRIMARY KEY,
    logged_at   TIMESTAMPTZ DEFAULT NOW(),
    table_name  TEXT NOT NULL,
    entity_id   TEXT,
    op          TEXT,              -- INSERT | UPDATE
    rule        TEXT NOT NULL,     -- machine rule id, e.g. drugs.brand_implies_approved
    severity    TEXT NOT NULL DEFAULT 'warn',   -- warn | would_block
    detail      TEXT,
    mode        TEXT NOT NULL DEFAULT 'warn'
);
CREATE INDEX IF NOT EXISTS gel_logged_at_idx ON governance_enforcement_log(logged_at DESC);
CREATE INDEX IF NOT EXISTS gel_rule_idx      ON governance_enforcement_log(rule);
CREATE INDEX IF NOT EXISTS gel_table_idx     ON governance_enforcement_log(table_name);

-- mode helper (defaults to 'warn' if the config row is somehow missing)
CREATE OR REPLACE FUNCTION _gov_enforcement_mode() RETURNS text AS $$
    SELECT COALESCE((SELECT mode FROM governance_enforcement_config WHERE singleton), 'warn');
$$ LANGUAGE sql STABLE;

-- one place that decides log-vs-block. In WARN mode it ONLY logs.
-- 'would_block' marks rows that WILL raise once mode='exception' AND p_hard.
CREATE OR REPLACE FUNCTION _gov_flag(
    p_table text, p_entity text, p_op text, p_rule text, p_detail text, p_hard boolean
) RETURNS void AS $$
DECLARE m text := _gov_enforcement_mode();
BEGIN
    INSERT INTO governance_enforcement_log(table_name, entity_id, op, rule, severity, detail, mode)
    VALUES (p_table, p_entity, p_op, p_rule,
            CASE WHEN p_hard THEN 'would_block' ELSE 'warn' END, p_detail, m);
    RAISE NOTICE 'governance[%/%]: % on % % — %', m,
        CASE WHEN p_hard THEN 'would_block' ELSE 'warn' END, p_rule, p_table, p_entity, p_detail;
    -- STEP 2 will add here:  IF m='exception' AND p_hard THEN RAISE EXCEPTION ...
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- A — drugs invariants  (brand⇒approved; dash-brand; originator on insert)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION enforce_drug_governance() RETURNS trigger AS $$
DECLARE approved_ok boolean := lower(coalesce(NEW.stage,'')) LIKE 'approved%';
BEGIN
    -- dash/empty brand is invalid (would normalize to NULL in EXCEPTION mode)
    IF NEW.brand_name IN ('—','-','') THEN
        PERFORM _gov_flag('drugs', NEW.id, TG_OP, 'drugs.dash_brand',
            format('brand_name=%L is a placeholder; should be NULL', NEW.brand_name), false);
    -- a real brand implies an approved stage
    ELSIF NEW.brand_name IS NOT NULL AND NOT approved_ok THEN
        PERFORM _gov_flag('drugs', NEW.id, TG_OP, 'drugs.brand_implies_approved',
            format('brand_name=%L but stage=%L (not approved%%)', NEW.brand_name, NEW.stage), false);
    END IF;
    -- originator company required at insert
    IF TG_OP = 'INSERT' AND NEW.company_id IS NULL THEN
        PERFORM _gov_flag('drugs', NEW.id, 'INSERT', 'drugs.company_id_required',
            'inserted without company_id (originator)', true);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_enforce_drug_governance ON drugs;
CREATE TRIGGER trg_enforce_drug_governance
    BEFORE INSERT OR UPDATE ON drugs
    FOR EACH ROW EXECUTE FUNCTION enforce_drug_governance();

-- ---------------------------------------------------------------------------
-- B — companies invariants  (status default; parent on sub/acq)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION enforce_company_governance() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'INSERT' AND NEW.status IS NULL THEN
        PERFORM _gov_flag('companies', NEW.id, 'INSERT', 'companies.status_default',
            'inserted without status (should default to subsidiary)', false);
    END IF;
    IF NEW.status IN ('subsidiary','acquired') AND NEW.parent_company_id IS NULL THEN
        PERFORM _gov_flag('companies', NEW.id, TG_OP, 'companies.parent_required',
            format('status=%L but parent_company_id is NULL', NEW.status), false);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_enforce_company_governance ON companies;
CREATE TRIGGER trg_enforce_company_governance
    BEFORE INSERT OR UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION enforce_company_governance();

-- ---------------------------------------------------------------------------
-- C — catalysts invariants  (linked to a drug or company; date sane)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION enforce_catalyst_governance() RETURNS trigger AS $$
BEGIN
    IF NEW.drug_id IS NULL AND NEW.company_id IS NULL THEN
        PERFORM _gov_flag('catalysts', NEW.id::text, TG_OP, 'catalysts.must_link',
            'catalyst linked to neither a drug nor a company', true);
    END IF;
    IF NEW.catalyst_date IS NULL THEN
        PERFORM _gov_flag('catalysts', NEW.id::text, TG_OP, 'catalysts.date_required',
            'catalyst_date is NULL', false);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_enforce_catalyst_governance ON catalysts;
CREATE TRIGGER trg_enforce_catalyst_governance
    BEFORE INSERT OR UPDATE ON catalysts
    FOR EACH ROW EXECUTE FUNCTION enforce_catalyst_governance();

-- ---------------------------------------------------------------------------
-- D — entity_edges referential integrity
--     (drug-typed endpoints must exist in drugs; catches the cld-423 orphan
--      and company-mistyped-as-drug edges from REVIEW_ITERATION_1 §3c)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION enforce_edge_governance() RETURNS trigger AS $$
BEGIN
    IF NEW.subject_type = 'drug'
       AND NOT EXISTS (SELECT 1 FROM drugs d WHERE d.id = NEW.subject_id) THEN
        PERFORM _gov_flag('entity_edges', NEW.id::text, TG_OP, 'edges.subject_drug_orphan',
            format('subject_type=drug but subject_id=%L not in drugs (predicate=%L)',
                   NEW.subject_id, NEW.predicate), true);
    END IF;
    IF NEW.object_type = 'drug'
       AND NOT EXISTS (SELECT 1 FROM drugs d WHERE d.id = NEW.object_id) THEN
        PERFORM _gov_flag('entity_edges', NEW.id::text, TG_OP, 'edges.object_drug_orphan',
            format('object_type=drug but object_id=%L not in drugs (predicate=%L)',
                   NEW.object_id, NEW.predicate), true);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_enforce_edge_governance ON entity_edges;
CREATE TRIGGER trg_enforce_edge_governance
    BEFORE INSERT OR UPDATE ON entity_edges
    FOR EACH ROW EXECUTE FUNCTION enforce_edge_governance();

-- ---------------------------------------------------------------------------
-- registry
-- ---------------------------------------------------------------------------
INSERT INTO schema_change_log
    (migration_version, migration_file, change_type, object_name, field_name,
     old_definition, new_definition, rationale)
VALUES
('v157','v157_writer_enforcement_warn.sql','create_table','governance_enforcement_config',NULL,
 NULL,'TABLE','Stage 4 enforcement MODE switch (warn|exception); one row.'),
('v157','v157_writer_enforcement_warn.sql','create_table','governance_enforcement_log',NULL,
 NULL,'TABLE','REST-queryable log of every Writer-invariant breach observed at the DB layer.'),
('v157','v157_writer_enforcement_warn.sql','create_function','enforce_drug_governance',NULL,
 NULL,'FUNCTION','WARN-mode drugs invariants: brand⇒approved, dash-brand, originator on insert.'),
('v157','v157_writer_enforcement_warn.sql','create_function','enforce_company_governance',NULL,
 NULL,'FUNCTION','WARN-mode companies invariants: status default, parent on sub/acq.'),
('v157','v157_writer_enforcement_warn.sql','create_function','enforce_catalyst_governance',NULL,
 NULL,'FUNCTION','WARN-mode catalysts invariants: must link to drug/company, date sane.'),
('v157','v157_writer_enforcement_warn.sql','create_function','enforce_edge_governance',NULL,
 NULL,'FUNCTION','WARN-mode entity_edges referential integrity for drug-typed endpoints.'),
('v157','v157_writer_enforcement_warn.sql','create_trigger','trg_enforce_drug_governance',NULL,
 NULL,'TRIGGER ON drugs','BEFORE INSERT OR UPDATE — observe-only invariant logging.'),
('v157','v157_writer_enforcement_warn.sql','create_trigger','trg_enforce_company_governance',NULL,
 NULL,'TRIGGER ON companies','BEFORE INSERT OR UPDATE — observe-only invariant logging.'),
('v157','v157_writer_enforcement_warn.sql','create_trigger','trg_enforce_catalyst_governance',NULL,
 NULL,'TRIGGER ON catalysts','BEFORE INSERT OR UPDATE — observe-only invariant logging.'),
('v157','v157_writer_enforcement_warn.sql','create_trigger','trg_enforce_edge_governance',NULL,
 NULL,'TRIGGER ON entity_edges','BEFORE INSERT OR UPDATE — observe-only invariant logging.');

COMMIT;

-- After commit: triggers are LIVE in warn mode. Verify with:
--   select rule, severity, count(*) from governance_enforcement_log group by 1,2 order by 3 desc;
-- Escalate in STEP 2 (v158) by adding the RAISE EXCEPTION branch to _gov_flag for hard rules
-- and flipping governance_enforcement_config.mode='exception'.
