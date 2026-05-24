-- =============================================================================
-- v32: Coverage Diagnostics
-- Adds derived completeness scoring to competitive_landscapes.
-- Replaces hand-entered landscape_completeness_score with computed columns.
-- =============================================================================

-- ── 1. Add score columns to competitive_landscapes ───────────────────────────
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

-- ── 2. landscape_expected_competitors table ───────────────────────────────────
CREATE TABLE IF NOT EXISTS landscape_expected_competitors (
    id              BIGSERIAL PRIMARY KEY,
    landscape_id    BIGINT NOT NULL REFERENCES competitive_landscapes(id) ON DELETE CASCADE,
    drug_name       TEXT NOT NULL,
    drug_id         TEXT REFERENCES drugs(id) ON DELETE SET NULL,
    tier            INT NOT NULL CHECK (tier IN (1, 2, 3)),
    tier3_weight    NUMERIC(3,2) NOT NULL DEFAULT 1.0,   -- Tier 3 candidates default 0.5×
    confirmed       BOOLEAN NOT NULL DEFAULT FALSE,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_landscape_expected UNIQUE (landscape_id, drug_name)
);

-- ── 3. coverage_computation_log table ────────────────────────────────────────
-- Append-only audit log of each compute_landscape_coverage.py run.
CREATE TABLE IF NOT EXISTS coverage_computation_log (
    id                              BIGSERIAL PRIMARY KEY,
    landscape_id                    BIGINT NOT NULL REFERENCES competitive_landscapes(id) ON DELETE CASCADE,
    computed_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
    captured_drug_count             INT,
    expected_drug_count             INT,
    captured_relationship_count     INT,
    expected_relationship_count     INT,
    captured_catalyst_count         INT,
    expected_catalyst_count         INT,
    sourced_row_count               INT,
    total_row_count                 INT,
    stale_row_count                 INT,
    drug_coverage_score             NUMERIC(5,4),
    relationship_coverage_score     NUMERIC(5,4),
    catalyst_coverage_score         NUMERIC(5,4),
    source_validation_score         NUMERIC(5,4),
    staleness_penalty               NUMERIC(5,4),
    landscape_dependency_score      NUMERIC(5,2),
    coverage_breakdown              JSONB,
    prior_score                     NUMERIC(5,2),
    score_delta                     NUMERIC(5,2),
    notes                           TEXT
);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_landscape_expected_competitors_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_landscape_expected_competitors_updated_at
    ON landscape_expected_competitors;

CREATE TRIGGER trg_landscape_expected_competitors_updated_at
    BEFORE UPDATE ON landscape_expected_competitors
    FOR EACH ROW EXECUTE FUNCTION update_landscape_expected_competitors_updated_at();

-- ── 4. Seed TED × IGF-1R_TSHR expected competitors (Tier 1) ──────────────────
-- Landscape ID is looked up dynamically. Seeding done via compute script.
-- This migration only establishes schema.

-- ── 5. Comments ───────────────────────────────────────────────────────────────
COMMENT ON COLUMN competitive_landscapes.expected_drug_count IS
    'Tier 1 curated count of drugs expected in this landscape. Source: landscape_expected_competitors.';
COMMENT ON COLUMN competitive_landscapes.expected_relationship_count IS
    'Expected number of critical entity_edges (COMPETES_WITH/SUBSTITUTES) for this landscape.';
COMMENT ON COLUMN competitive_landscapes.expected_catalyst_count IS
    'Expected number of upcoming catalysts across Tier-1 drugs in landscape.';
COMMENT ON COLUMN competitive_landscapes.drug_coverage_score IS
    'Fraction of Tier-1 expected drugs present in DB (0-1). Computed by compute_landscape_coverage.py.';
COMMENT ON COLUMN competitive_landscapes.relationship_coverage_score IS
    'Fraction of expected entity_edges present (0-1). Computed by compute_landscape_coverage.py.';
COMMENT ON COLUMN competitive_landscapes.catalyst_coverage_score IS
    'Fraction of Tier-1 landscape drugs that have at least one catalyst (0-1).';
COMMENT ON COLUMN competitive_landscapes.source_validation_score IS
    'Fraction of confirmed/supported drug_area_scores rows that have a valid source_url (0-1).';
COMMENT ON COLUMN competitive_landscapes.staleness_penalty IS
    'Fraction of staleness_status=stale/needs_revalidation rows in landscape (0-1). Applied as negative weight.';
COMMENT ON COLUMN competitive_landscapes.landscape_dependency_score IS
    '0.35×drug + 0.25×relationship + 0.20×catalyst + 0.15×source − 0.05×staleness. Replaces hand-entered landscape_completeness_score.';
COMMENT ON COLUMN competitive_landscapes.coverage_breakdown IS
    'JSON detail: {drug: {captured, expected, missing:[]}, relationship: {...}, catalyst: {...}, source: {...}}';
COMMENT ON COLUMN competitive_landscapes.coverage_computed_at IS
    'Timestamp of last compute_landscape_coverage.py run.';

COMMENT ON TABLE landscape_expected_competitors IS
    'Tier-1 curated list of drugs expected per competitive landscape. Drives drug_coverage_score denominator.';
COMMENT ON COLUMN landscape_expected_competitors.tier IS
    '1=manually curated (ground truth), 2=rule-derived from DB, 3=candidate/pending revalidation.';
COMMENT ON COLUMN landscape_expected_competitors.tier3_weight IS
    'Weight applied in coverage numerator for this drug. Default 1.0; set to 0.5 for Tier-3 candidates pending revalidation.';
COMMENT ON COLUMN landscape_expected_competitors.confirmed IS
    'TRUE when drug_id is linked and validated in Meridian. FALSE = known competitor, not yet in DB.';

COMMENT ON TABLE coverage_computation_log IS
    'Append-only audit log of each compute_landscape_coverage.py run. One row per landscape per run.';
