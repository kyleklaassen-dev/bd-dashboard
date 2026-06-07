-- =============================================================================
-- SCHEMA MIGRATION V4 — Intelligence Layer
-- BD Platform | Applied: 2026-05-19
--
-- Adds completeness + trigger fields to drugs table.
-- Creates research_queue table for the research priority engine.
--
-- Safe to re-run (all ADD COLUMN IF NOT EXISTS / CREATE TABLE IF NOT EXISTS).
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. DRUGS — completeness scoring fields
-- -----------------------------------------------------------------------------

ALTER TABLE drugs
  ADD COLUMN IF NOT EXISTS completeness_score  INTEGER,          -- 0–100
  ADD COLUMN IF NOT EXISTS completeness_tier   TEXT,             -- 'thin' | 'partial' | 'strong'
  ADD COLUMN IF NOT EXISTS missing_fields      JSONB,            -- list of field names that are empty
  ADD COLUMN IF NOT EXISTS missing_stages      JSONB,            -- list of stage names with gaps
  ADD COLUMN IF NOT EXISTS next_best_action    TEXT,             -- plain-English recommended next step
  ADD COLUMN IF NOT EXISTS last_scored_at      TIMESTAMPTZ,      -- when completeness was last computed
  ADD COLUMN IF NOT EXISTS priority_score      INTEGER DEFAULT 0, -- research urgency (0–200)
  ADD COLUMN IF NOT EXISTS trigger_flags       JSONB;            -- active trigger types from check_research_triggers()

-- -----------------------------------------------------------------------------
-- 2. RESEARCH QUEUE — one row per (entity_id, area_id), upserted nightly
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS research_queue (
  id                   UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
  entity_id            TEXT        NOT NULL,
  entity_name          TEXT,
  company_id           TEXT,
  area_id              TEXT,

  -- Priority + scoring
  priority_score       INTEGER     DEFAULT 0,         -- 0–200; higher = more urgent
  reason               TEXT,                          -- human-readable explanation
  next_best_action     TEXT,                          -- what to do next
  missing_stage        TEXT,                          -- first missing stage name
  missing_fields       JSONB,                         -- list of missing field names

  -- Strategic context
  strategic_importance TEXT        DEFAULT 'medium',  -- 'high' | 'medium' | 'low'
  completeness_score   INTEGER,                       -- snapshot of score at queue time
  completeness_tier    TEXT,                          -- 'thin' | 'partial' | 'strong'

  -- Trigger state
  trigger_events       JSONB,                         -- list of trigger type strings

  -- Metadata
  last_updated         TIMESTAMPTZ DEFAULT NOW(),
  assigned_status      TEXT        DEFAULT 'pending', -- 'pending' | 'in_progress' | 'done' | 'skipped'
  created_at           TIMESTAMPTZ DEFAULT NOW(),

  UNIQUE (entity_id, area_id)
);

-- -----------------------------------------------------------------------------
-- 3. INDEXES on research_queue
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_rq_entity     ON research_queue (entity_id);
CREATE INDEX IF NOT EXISTS idx_rq_area       ON research_queue (area_id);
CREATE INDEX IF NOT EXISTS idx_rq_priority   ON research_queue (priority_score DESC);
CREATE INDEX IF NOT EXISTS idx_rq_status     ON research_queue (assigned_status);
CREATE INDEX IF NOT EXISTS idx_rq_importance ON research_queue (strategic_importance);
CREATE INDEX IF NOT EXISTS idx_rq_company    ON research_queue (company_id);
CREATE INDEX IF NOT EXISTS idx_rq_updated    ON research_queue (last_updated DESC);

-- -----------------------------------------------------------------------------
-- 4. INDEX on drugs — for completeness queries
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_drugs_completeness_tier ON drugs (completeness_tier);
CREATE INDEX IF NOT EXISTS idx_drugs_priority_score    ON drugs (priority_score DESC);

-- -----------------------------------------------------------------------------
-- Done
-- -----------------------------------------------------------------------------
