-- ============================================================
-- Meridian v62 Migration: Confidence P2 Gaps + Schema Audit
-- Applied: 2026-05-28
-- Session: P2 Schema Fixes — confidence_tier, strategic views,
--          source_validation_log, strategic_value_score,
--          enrichment_run_id sweep
-- ============================================================

-- ─────────────────────────────────────────────────────────────
-- TASK 1: molecule_intelligence — rename confidence → confidence_tier
--         + add confidence_source with verified/model/inferred/human_review
-- ─────────────────────────────────────────────────────────────

ALTER TABLE molecule_intelligence
    RENAME COLUMN confidence TO confidence_tier;

ALTER TABLE molecule_intelligence
    ADD COLUMN IF NOT EXISTS confidence_source TEXT
        DEFAULT 'model'
        CHECK (confidence_source IN ('verified', 'model', 'inferred', 'human_review'));

-- Backfill: high → verified, low → inferred, medium → model
UPDATE molecule_intelligence
SET confidence_source = CASE
    WHEN confidence_tier = 'high' THEN 'verified'
    WHEN confidence_tier = 'low'  THEN 'inferred'
    ELSE 'model'
END
WHERE confidence_source IS NULL OR confidence_source = 'model';

-- ─────────────────────────────────────────────────────────────
-- TASK 2: source_validation_log (from v62_agent_validation_tables.sql)
--         + enriched_field_log priority columns
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS source_validation_log (
    id                  BIGSERIAL PRIMARY KEY,
    table_name          TEXT NOT NULL,
    entity_id           TEXT,
    field_name          TEXT,
    source_url          TEXT NOT NULL,
    is_valid            BOOLEAN,
    http_status_code    INTEGER,
    error_message       TEXT,
    domain_trusted      BOOLEAN,
    validated_at        TIMESTAMPTZ DEFAULT NOW(),
    validation_run_id   TEXT
);

CREATE INDEX IF NOT EXISTS svl_valid_idx
    ON source_validation_log(is_valid)
    WHERE is_valid = FALSE;

CREATE INDEX IF NOT EXISTS svl_validated_at_idx
    ON source_validation_log(validated_at DESC);

CREATE INDEX IF NOT EXISTS svl_table_name_idx
    ON source_validation_log(table_name);

ALTER TABLE enriched_field_log
    ADD COLUMN IF NOT EXISTS review_priority_score  INTEGER,
    ADD COLUMN IF NOT EXISTS review_queue_position  INTEGER;

CREATE INDEX IF NOT EXISTS efl_priority_idx
    ON enriched_field_log(review_priority_score DESC NULLS LAST)
    WHERE field_label = 'pending';

-- ─────────────────────────────────────────────────────────────
-- TASK 3: company_strategic_views + company_platform_views
--         P2 gap G-11: strategic view classification per company
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS company_strategic_views (
    id                  BIGSERIAL PRIMARY KEY,
    company_id          TEXT REFERENCES companies(id) ON DELETE CASCADE,
    view_type           TEXT NOT NULL CHECK (view_type IN (
                            'competitive', 'partnership',
                            'acquisition_target', 'licensing_candidate')),
    summary             TEXT,
    key_assets          TEXT[],
    ailux_relevance     TEXT,
    strategic_score     INTEGER CHECK (strategic_score BETWEEN 0 AND 100),
    enrichment_run_id   UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL,
    source_url          TEXT,
    confidence_source   TEXT DEFAULT 'model'
                            CHECK (confidence_source IN (
                                'verified', 'model', 'inferred', 'human_review')),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS csv_company_idx ON company_strategic_views(company_id);

CREATE TABLE IF NOT EXISTS company_platform_views (
    id                      BIGSERIAL PRIMARY KEY,
    company_id              TEXT REFERENCES companies(id) ON DELETE CASCADE,
    platform_type           TEXT NOT NULL,
    platform_description    TEXT,
    relevance_to_ailux      TEXT,
    partnership_potential   TEXT CHECK (partnership_potential IN (
                                'high', 'medium', 'low', 'none')),
    enrichment_run_id       UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL,
    confidence_source       TEXT DEFAULT 'model',
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS cpv_company_idx ON company_platform_views(company_id);

-- ─────────────────────────────────────────────────────────────
-- TASK 4: strategic_value_score on companies
--         P2 gap G-12: BD prioritization score
-- ─────────────────────────────────────────────────────────────

ALTER TABLE companies
    ADD COLUMN IF NOT EXISTS strategic_value_score      INTEGER CHECK (strategic_value_score BETWEEN 0 AND 100),
    ADD COLUMN IF NOT EXISTS strategic_value_rationale  TEXT,
    ADD COLUMN IF NOT EXISTS strategic_value_updated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS strategic_value_run_id     UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL;

-- ─────────────────────────────────────────────────────────────
-- TASK 5: entity_type on enriched_field_log
-- ─────────────────────────────────────────────────────────────

ALTER TABLE enriched_field_log
    ADD COLUMN IF NOT EXISTS entity_type TEXT;

-- Backfill from enrichment_runs
UPDATE enriched_field_log efl
SET entity_type = er.entity_type
FROM enrichment_runs er
WHERE er.id = efl.enrichment_run_id
  AND efl.entity_type IS NULL;

-- ─────────────────────────────────────────────────────────────
-- TASK 6: enrichment_run_id sweep — key intelligence/entity tables
-- ─────────────────────────────────────────────────────────────

ALTER TABLE drugs               ADD COLUMN IF NOT EXISTS enrichment_run_id UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL;
ALTER TABLE companies           ADD COLUMN IF NOT EXISTS enrichment_run_id UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL;
ALTER TABLE company_profiles    ADD COLUMN IF NOT EXISTS enrichment_run_id UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL;
ALTER TABLE company_partnerships ADD COLUMN IF NOT EXISTS enrichment_run_id UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL;
ALTER TABLE deals                ADD COLUMN IF NOT EXISTS enrichment_run_id UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL;
ALTER TABLE catalysts            ADD COLUMN IF NOT EXISTS enrichment_run_id UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL;
ALTER TABLE intel                ADD COLUMN IF NOT EXISTS enrichment_run_id UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL;
ALTER TABLE intelligence_discoveries ADD COLUMN IF NOT EXISTS enrichment_run_id UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL;
ALTER TABLE meridian_issues      ADD COLUMN IF NOT EXISTS enrichment_run_id UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL;
ALTER TABLE bd_insights          ADD COLUMN IF NOT EXISTS enrichment_run_id UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL;

-- ─────────────────────────────────────────────────────────────
-- TASK 7: schema_change_log entries — applied via Python script
-- (see insert_schema_log.py for full INSERT executed 2026-05-28)
-- ─────────────────────────────────────────────────────────────

-- Verify
SELECT
    table_name,
    COUNT(*) as row_count
FROM (
    SELECT 'source_validation_log' AS table_name FROM source_validation_log
    UNION ALL
    SELECT 'company_strategic_views' FROM company_strategic_views
    UNION ALL
    SELECT 'company_platform_views' FROM company_platform_views
) subq
GROUP BY table_name;

SELECT COUNT(*) as schema_log_v62_entries
FROM schema_change_log
WHERE migration_version = 'v62';
