-- ============================================================
-- Meridian v62 Migration: Agent Validation Tables
-- Applied: 2026-05-28
-- Session: Weekend Sprint — Tier 3/4/5 Agent Scripts
-- ============================================================
-- Run this in Supabase SQL Editor (one block at a time if needed)

-- ─────────────────────────────────────────────────────────────
-- 1. source_validation_log
--    Stores per-URL validation results from source_verifier.py
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

COMMENT ON TABLE source_validation_log IS
    'Per-URL HTTP validation results from source_verifier.py (Tier 3 Validation Agent). '
    'Populated by Phase E4 of the Weekend Sprint.';

-- ─────────────────────────────────────────────────────────────
-- 2. enriched_field_log: add review priority columns
--    Used by human_queue_builder.py (Tier 5 Meta Agent)
-- ─────────────────────────────────────────────────────────────

ALTER TABLE enriched_field_log
    ADD COLUMN IF NOT EXISTS review_priority_score  INTEGER,
    ADD COLUMN IF NOT EXISTS review_queue_position  INTEGER;

CREATE INDEX IF NOT EXISTS efl_priority_idx
    ON enriched_field_log(review_priority_score DESC NULLS LAST)
    WHERE field_label = 'pending';

COMMENT ON COLUMN enriched_field_log.review_priority_score IS
    'Priority score (0-150+) computed by human_queue_builder.py. '
    'Higher = review first. Based on overlap, stage, confidence, staleness, catalyst proximity.';

COMMENT ON COLUMN enriched_field_log.review_queue_position IS
    'Queue position (1 = top priority) assigned by human_queue_builder.py. '
    'Reset each sprint run.';

-- ─────────────────────────────────────────────────────────────
-- 3. Verify
-- ─────────────────────────────────────────────────────────────

SELECT
    'source_validation_log' AS table_name,
    COUNT(*) AS row_count
FROM source_validation_log
UNION ALL
SELECT
    'enriched_field_log (priority cols)' AS table_name,
    COUNT(*) AS row_count
FROM enriched_field_log
WHERE review_priority_score IS NOT NULL;
