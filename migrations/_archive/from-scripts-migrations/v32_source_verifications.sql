-- v32: source_verifications table
-- Tracks HTTP health of every source_url stored in the platform.
-- Cross-referenced by drug_area_scores, catalysts, intel, deals.
-- Run: apply in Supabase SQL editor.

CREATE TABLE IF NOT EXISTS source_verifications (
    id              BIGSERIAL PRIMARY KEY,
    url             TEXT        NOT NULL UNIQUE,
    source_status   TEXT        NOT NULL DEFAULT 'unknown',
      -- valid | broken | timeout | generic | truncated | malformed
    http_status     INTEGER,
      -- Last HTTP response code (200, 404, 0=timeout, etc.)
    source_type     TEXT,
      -- ct_study | fda | pubmed | sec | press_release | news_article
      -- generic_pipeline | generic_ir | generic_homepage | other_specific
    source_tier     INTEGER,
      -- 1=CT.gov/FDA/PubMed/SEC  2=Company IR/Investor  3=News/Press  4=Generic
    is_generic      BOOLEAN     NOT NULL DEFAULT FALSE,
      -- TRUE if URL points to a page listing (not a specific claim)
    last_checked_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_source_verifications_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_source_verifications_updated_at
    BEFORE UPDATE ON source_verifications
    FOR EACH ROW EXECUTE FUNCTION update_source_verifications_updated_at();

-- Source tier classification for quick lookup
COMMENT ON COLUMN source_verifications.source_tier IS
    '1=CT.gov/FDA/PubMed/SEC (primary), 2=Company IR/investor deck, 3=News/press, 4=Generic pipeline page';

COMMENT ON TABLE source_verifications IS
    'Per-URL HTTP health tracking. Populated by scripts/audit_sources.py. '
    'Cross-referenced by drug_area_scores.source_url, catalysts.source_url, intel.source_url.';
