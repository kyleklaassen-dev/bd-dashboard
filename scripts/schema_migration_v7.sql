-- ============================================================
-- BD Platform Schema Migration v7
-- Adds partner_co, group_id, display_co to companies table
-- These support the grouped PI table format and pipeline seeding
-- ============================================================

-- Add columns (idempotent — IF NOT EXISTS)
ALTER TABLE companies
  ADD COLUMN IF NOT EXISTS partner_co   TEXT,
  ADD COLUMN IF NOT EXISTS group_id     TEXT,
  ADD COLUMN IF NOT EXISTS display_co   TEXT;

-- Add overlap column to companies (mirrors the drug-level field for company-level context)
ALTER TABLE companies
  ADD COLUMN IF NOT EXISTS overlap      TEXT;

-- Index on group_id for grouped queries
CREATE INDEX IF NOT EXISTS companies_group_id_idx ON companies (group_id);

-- Comments
COMMENT ON COLUMN companies.partner_co  IS 'Licensor/partner company name shown in drug row tag (e.g. Telavant for Roche)';
COMMENT ON COLUMN companies.group_id    IS 'Group key for consolidating related entries in PI table (e.g. abbvie, spyre)';
COMMENT ON COLUMN companies.display_co  IS 'Override display name for company column (defaults to name if null)';
COMMENT ON COLUMN companies.overlap     IS 'Competitive overlap classification: Direct, Adjacent, Same-Space, Watch, Next Gen';
