-- v32_coverage_diagnostics.sql
-- Coverage Diagnostics: derived landscape_dependency_score replaces self-reported completeness.
-- Apply in Supabase SQL editor:
--   https://supabase.com/dashboard/project/tghntyofptvfhmtchwcv/sql/new
--
-- What this migration does:
--   1. Extends competitive_landscapes with 9 derived-score columns
--   2. Creates landscape_expected_competitors (Tier 1 curated drug list per landscape)
--
-- After applying, run: python3 scripts/compute_landscape_coverage.py

-- ── 1. Extend competitive_landscapes ──────────────────────────────────────────

ALTER TABLE competitive_landscapes
    ADD COLUMN IF NOT EXISTS expected_drug_count          INT,
    ADD COLUMN IF NOT EXISTS expected_relationship_count  INT,
    ADD COLUMN IF NOT EXISTS expected_catalyst_count      INT,
    ADD COLUMN IF NOT EXISTS drug_coverage_score          NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS relationship_coverage_score  NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS catalyst_coverage_score      NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS source_validation_score      NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS staleness_penalty            NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS landscape_dependency_score   NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS coverage_breakdown           JSONB,
    ADD COLUMN IF NOT EXISTS coverage_computed_at         TIMESTAMPTZ;

COMMENT ON COLUMN competitive_landscapes.landscape_dependency_score IS
    'Derived completeness score: 0.35×drug + 0.25×relationship + 0.20×catalyst + 0.15×source − 0.05×staleness. Replaces self-reported landscape_completeness_score.';

COMMENT ON COLUMN competitive_landscapes.coverage_breakdown IS
    'JSONB: per-dimension detail — captured_drugs, expected_drugs, captured_edges, expected_edges, etc.';

-- ── 2. Create landscape_expected_competitors ──────────────────────────────────

CREATE TABLE IF NOT EXISTS landscape_expected_competitors (
    id              BIGSERIAL PRIMARY KEY,
    landscape_id    BIGINT       NOT NULL REFERENCES competitive_landscapes(id) ON DELETE CASCADE,
    drug_name       TEXT         NOT NULL,   -- canonical display name
    drug_id         TEXT         REFERENCES drugs(id) ON DELETE SET NULL,
    tier            INT          NOT NULL CHECK (tier IN (1, 2, 3)),
    confirmed       BOOLEAN      NOT NULL DEFAULT FALSE,
    mechanism_class TEXT,                    -- e.g. 'IGF-1R mAb', 'FcRn mAb', 'TSHR mAb'
    include_in_score BOOLEAN     NOT NULL DEFAULT TRUE,  -- FALSE for excluded/OOscope drugs
    notes           TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT uq_landscape_expected UNIQUE (landscape_id, drug_name)
);

COMMENT ON TABLE landscape_expected_competitors IS
    'Tier 1 manually curated expected drug list per competitive landscape. Used by compute_landscape_coverage.py to compute drug_coverage_score.';

-- Auto-update updated_at on any row change
CREATE OR REPLACE FUNCTION update_landscape_expected_competitors_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_lec_updated_at ON landscape_expected_competitors;
CREATE TRIGGER trg_lec_updated_at
    BEFORE UPDATE ON landscape_expected_competitors
    FOR EACH ROW EXECUTE FUNCTION update_landscape_expected_competitors_updated_at();

-- ── Verification ──────────────────────────────────────────────────────────────

SELECT 'competitive_landscapes columns' AS check,
       COUNT(*) AS added_columns
FROM information_schema.columns
WHERE table_name = 'competitive_landscapes'
  AND column_name IN (
      'expected_drug_count', 'expected_relationship_count', 'expected_catalyst_count',
      'drug_coverage_score', 'relationship_coverage_score', 'catalyst_coverage_score',
      'source_validation_score', 'staleness_penalty', 'landscape_dependency_score',
      'coverage_breakdown', 'coverage_computed_at'
  );

SELECT 'landscape_expected_competitors' AS check, COUNT(*) AS rows FROM landscape_expected_competitors;
