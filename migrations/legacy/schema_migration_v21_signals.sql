-- Migration v21: signals + enrichment_queue tables
-- Tier 1 signal monitoring backbone per tiered_enrichment_architecture.md
-- Applied via Management API on 2026-05-22.

-- ── signals table ──────────────────────────────────────────────────────────
-- One row per detected event. Deduped on source_url_hash (per-article)
-- and content_hash (company + headline + date fingerprint for non-URL dedup).
CREATE TABLE IF NOT EXISTS signals (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id           text REFERENCES companies(id),
  area_id              text,
  signal_type          text NOT NULL,  -- 'press_release' | 'trial_update' | 'deal' | 'abstract' | 'financing' | 'pipeline_change' | 'fda'
  headline             text NOT NULL,
  source_url           text,
  source_url_hash      text GENERATED ALWAYS AS (md5(COALESCE(source_url, ''))) STORED,
  content_hash         text,           -- md5(company_id || headline || event_date::text)
  event_date           date,
  relevance_score      int DEFAULT 0,  -- 1–10 heuristic; ≥8 triggers Tier 2 dispatch
  enrichment_triggered bool DEFAULT false,
  raw_headline         text,           -- original headline before normalisation
  source_name          text,           -- 'BioPharma Dive' | 'FierceBiotech' | 'FDA' | 'ClinicalTrials.gov'
  created_at           timestamptz DEFAULT now()
);

-- Primary dedup: one URL = one signal row
CREATE UNIQUE INDEX IF NOT EXISTS idx_signals_url_dedup
  ON signals (source_url_hash)
  WHERE source_url IS NOT NULL AND source_url != '';

-- Secondary dedup: catch same event from different URLs (content fingerprint)
CREATE UNIQUE INDEX IF NOT EXISTS idx_signals_content_dedup
  ON signals (content_hash)
  WHERE content_hash IS NOT NULL;

-- Lookup indexes
CREATE INDEX IF NOT EXISTS idx_signals_company_date
  ON signals (company_id, event_date DESC);
CREATE INDEX IF NOT EXISTS idx_signals_relevance
  ON signals (relevance_score DESC, created_at DESC);

-- ── enrichment_queue table ─────────────────────────────────────────────────
-- Records targeted Tier 2 enrichment requests dispatched by signal_monitor.
-- company_enrichment.py checks this at startup and processes pending items
-- before running its scheduled sweep.
CREATE TABLE IF NOT EXISTS enrichment_queue (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id  text NOT NULL,
  area_id     text NOT NULL,
  trigger     text NOT NULL DEFAULT 'signal',  -- 'signal' | 'scheduled' | 'manual' | 'curation'
  signal_id   uuid REFERENCES signals(id),
  priority    int DEFAULT 5,  -- 1–10 (mirrors signal relevance_score; higher = run sooner)
  status      text DEFAULT 'pending',  -- 'pending' | 'dispatched' | 'complete' | 'skipped'
  dispatched_at timestamptz,
  completed_at  timestamptz,
  created_at  timestamptz DEFAULT now(),
  -- Prevent double-queueing the same company × area pair when already pending
  UNIQUE(company_id, area_id, status) DEFERRABLE INITIALLY DEFERRED
);

CREATE INDEX IF NOT EXISTS idx_enrichment_queue_pending
  ON enrichment_queue (status, priority DESC, created_at)
  WHERE status = 'pending';

-- ── RLS ────────────────────────────────────────────────────────────────────
ALTER TABLE signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE enrichment_queue ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_select_signals"
  ON signals FOR SELECT TO anon USING (true);

CREATE POLICY "anon_select_enrichment_queue"
  ON enrichment_queue FOR SELECT TO anon USING (true);
