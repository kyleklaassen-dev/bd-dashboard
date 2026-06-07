-- ─────────────────────────────────────────────────────────────────────────────
-- Migration v37: drug_sources table + data_confidence column + source coverage view
-- Apply via: python3 scripts/apply_drug_sources_migration.py
-- Or paste directly into: https://supabase.com/dashboard/project/tghntyofptvfhmtchwcv/sql/new
-- ─────────────────────────────────────────────────────────────────────────────

-- ── Table: drug_sources ───────────────────────────────────────────────────────
-- Every factual claim about a drug must be traceable to a real source URL.
-- claim_type: what is this source proving?
-- source_url: the actual URL (required, validated before insert)
-- content_confirms_claim: did we verify the URL content mentions this drug + claim?

CREATE TABLE IF NOT EXISTS drug_sources (
  id                    BIGSERIAL PRIMARY KEY,
  drug_id               TEXT NOT NULL,        -- references drugs.id (soft FK)
  drug_name             TEXT,                 -- denormalized for readability
  claim_type            TEXT NOT NULL,        -- 'stage' | 'approval' | 'mechanism' | 'brand_name'
                                              -- | 'company' | 'indication' | 'trial_registration'
                                              -- | 'deal' | 'discontinuation' | 'safety_signal'
                                              -- | 'partnership' | 'unverified'
  claim_value           TEXT,                 -- the value being sourced (e.g. 'Phase 3', 'Approved')
  source_url            TEXT NOT NULL,        -- actual URL
  source_type           TEXT,                 -- 'fda_label' | 'clinicaltrials' | 'press_release'
                                              -- | 'sec_filing' | 'pubmed' | 'company_website'
                                              -- | 'ema_label' | 'who_inn' | 'news'
  source_domain         TEXT,                 -- extracted from URL (pubmed.ncbi.nlm.nih.gov, etc.)
  url_status            TEXT DEFAULT 'unverified',  -- 'live' | 'dead' | 'redirects' | 'unverified'
  url_last_checked      TIMESTAMPTZ,
  content_confirms_claim BOOLEAN,             -- did URL content mention this drug + claim?
  confidence            TEXT DEFAULT 'medium', -- 'high' (2+ confirmed) | 'medium' (1 confirmed)
                                               -- | 'low' (unverified source) | 'unverified'
  added_by              TEXT DEFAULT 'system', -- 'human' | 'enrichment' | 'system'
  session_label         TEXT,                 -- which enrichment session added this
  created_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_drug_sources_drug     ON drug_sources(drug_id);
CREATE INDEX IF NOT EXISTS idx_drug_sources_type     ON drug_sources(claim_type);
CREATE INDEX IF NOT EXISTS idx_drug_sources_status   ON drug_sources(url_status);
CREATE INDEX IF NOT EXISTS idx_drug_sources_confirmed ON drug_sources(content_confirms_claim)
  WHERE content_confirms_claim = TRUE;

-- ── Column: drugs.data_confidence ─────────────────────────────────────────────
-- Aggregate confidence level for a drug, derived from drug_sources.
-- 'high'       = 2+ sources with content_confirms_claim = TRUE
-- 'medium'     = 1 source with content_confirms_claim = TRUE
-- 'low'        = has sources but none content-verified
-- 'unverified' = no sources at all

ALTER TABLE drugs ADD COLUMN IF NOT EXISTS data_confidence TEXT DEFAULT 'unverified';

-- ── View: drug_source_coverage ────────────────────────────────────────────────
-- Shows per-drug source count and verification status.
-- Ordered by source_count ASC so zero-source drugs appear first.

CREATE OR REPLACE VIEW drug_source_coverage AS
SELECT
  d.id,
  d.name,
  d.brand_name,
  d.stage,
  d.data_confidence,
  COUNT(s.id)                                          AS source_count,
  COUNT(CASE WHEN s.url_status = 'live' THEN 1 END)   AS live_sources,
  COUNT(CASE WHEN s.content_confirms_claim = TRUE THEN 1 END) AS verified_claims,
  MAX(s.url_last_checked)                              AS last_source_check
FROM drugs d
LEFT JOIN drug_sources s ON s.drug_id = d.id
GROUP BY d.id, d.name, d.brand_name, d.stage, d.data_confidence
ORDER BY source_count ASC;  -- zero-source drugs first (most needing attention)

-- ── Initial confidence update ─────────────────────────────────────────────────
-- Run after seeding drug_sources to populate data_confidence on all drugs.
-- Re-run any time sources are added or verified.

UPDATE drugs d SET data_confidence =
  CASE
    WHEN (SELECT COUNT(*) FROM drug_sources s
          WHERE s.drug_id = d.id AND s.content_confirms_claim = TRUE) >= 2 THEN 'high'
    WHEN (SELECT COUNT(*) FROM drug_sources s
          WHERE s.drug_id = d.id AND s.content_confirms_claim = TRUE) = 1  THEN 'medium'
    WHEN (SELECT COUNT(*) FROM drug_sources s
          WHERE s.drug_id = d.id) > 0                                       THEN 'low'
    ELSE 'unverified'
  END;
