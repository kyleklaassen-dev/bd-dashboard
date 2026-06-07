-- Migration v30 — coverage_scores table
-- Applied: 2026-05-24 (Session 32)
-- Purpose: Per-company, per-area coverage diagnostic layer.
--          Enables Meridian to measure what it knows, what it should know,
--          and where enrichment effort should focus next.
--
-- The principle: "The graph organizes knowledge. It does not create it."
-- A perfect graph over incomplete data produces incomplete intelligence.
-- Coverage measurement makes gaps legible and actionable.
--
-- Populated by: scripts/compute_coverage.py (run nightly)
-- Rows: one per company_areas row (137 at creation)
-- Key output: overall_score + per-dimension scores + recommended_actions_json

CREATE TABLE IF NOT EXISTS coverage_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    entity_type TEXT NOT NULL DEFAULT 'company',
    entity_id   TEXT NOT NULL,   -- 'company_id:area_id' composite key
    company_id  TEXT,
    area_id     TEXT,

    -- Aggregate
    overall_score NUMERIC(5,1),

    -- Dimension scores (0–100)
    target_mapping_score        NUMERIC(5,1),  -- % drugs with drug_targets rows
    ownership_coverage_score    NUMERIC(5,1),  -- % licensed-in drugs with ownership_edges
    source_coverage_score       NUMERIC(5,1),  -- % drug_area_scores with source_url
    confidence_coverage_score   NUMERIC(5,1),  -- % drug_area_scores with confidence_level
    enrichment_recency_score    NUMERIC(5,1),  -- recency of company_profiles.last_enriched_at
    deal_linkage_score          NUMERIC(5,1),  -- % acq/license edges with deal_id
    molecule_intelligence_score NUMERIC(5,1),  -- % drugs with molecule_intelligence rows
    catalyst_coverage_score     NUMERIC(5,1),  -- % clinical drugs with future catalyst
    profile_completeness_score  NUMERIC(5,1),  -- % expected profile fields present

    -- Diagnostic
    missing_items_json         JSONB,  -- per-dimension list of what's missing
    recommended_actions_json   JSONB,  -- ordered list of "what to do next"

    -- Metadata
    computed_at   TIMESTAMPTZ DEFAULT now(),
    score_version TEXT DEFAULT '1.0',

    UNIQUE(entity_id, area_id)
);

CREATE INDEX IF NOT EXISTS idx_coverage_scores_entity_id ON coverage_scores(entity_id);
CREATE INDEX IF NOT EXISTS idx_coverage_scores_area_id   ON coverage_scores(area_id) WHERE area_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_coverage_scores_overall   ON coverage_scores(overall_score);

-- Initial platform state (2026-05-24):
--   Platform coverage: 71.3 / 100
--   Weakest dimensions: catalyst_coverage (43.1), source_coverage (59.5), ownership_coverage (57.7)
--   Strongest dimensions: molecule_intelligence (99.5), deal_linkage (97.1), target_mapping (91.7)
--   Lowest-coverage areas: autoimmune (62.3), atopy (63.3), ibd (67.1)
--   Highest-coverage areas: tslp (80.8), il4ra (78.6), fcrn (78.5)
