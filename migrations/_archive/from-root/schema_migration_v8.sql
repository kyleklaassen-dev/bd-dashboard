-- schema_migration_v8.sql
-- resolver_errors — persistent log of identity resolution failures
-- ─────────────────────────────────────────────────────────────────
-- When DrugIdentityResolver.resolve() fails (network error, Supabase
-- timeout, malformed payload, etc.) the circuit-breaker currently logs
-- a warning and sets canonical_drug_id=None on the calling record.
-- This table persists those failures so they can be retried without
-- re-running a full ct_gov_sync or company_enrichment run.
--
-- Retry workflow:
--   python scripts/identity_resolution.py --retry-errors
--   → reads resolver_errors WHERE resolved_at IS NULL
--   → re-attempts resolve() for each row
--   → on success: stamps the source table row + marks error as resolved
--   → on failure: increments attempt_count, updates last_attempted_at
--
-- Retention: rows resolved > 30 days ago can be pruned.
-- ─────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS resolver_errors (
  id               UUID        DEFAULT gen_random_uuid() PRIMARY KEY,

  -- What failed
  drug_name        TEXT        NOT NULL,
  source           TEXT        NOT NULL,          -- 'ct_gov_sync' | 'company_enrichment' | 'one_time_migration' | 'cli'
  source_table     TEXT,                          -- e.g. 'trials', 'drugs', 'catalysts', 'deals'
  source_row_id    TEXT,                          -- PK of the row that needs canonical_drug_id stamped

  -- Error detail
  error_message    TEXT        NOT NULL,
  error_type       TEXT,                          -- 'network' | 'supabase' | 'value_error' | 'unknown'
  stack_trace      TEXT,

  -- Retry state
  attempt_count    INT         NOT NULL DEFAULT 1,
  last_attempted_at TIMESTAMPTZ DEFAULT NOW(),
  resolved_at      TIMESTAMPTZ,                   -- NULL = still needs retry
  resolved_canonical_id TEXT,                     -- filled on successful retry

  -- Metadata
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_re_unresolved   ON resolver_errors (resolved_at) WHERE resolved_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_re_drug_name    ON resolver_errors (drug_name);
CREATE INDEX IF NOT EXISTS idx_re_source       ON resolver_errors (source);
CREATE INDEX IF NOT EXISTS idx_re_source_row   ON resolver_errors (source_table, source_row_id);
CREATE INDEX IF NOT EXISTS idx_re_created      ON resolver_errors (created_at DESC);
