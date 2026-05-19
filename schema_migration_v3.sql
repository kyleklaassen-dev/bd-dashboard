-- ============================================================
-- Ailux BD Platform — Schema Migration v3
-- Purpose: Full Intelligence Architecture
--          Adds all missing columns to support the Strategic
--          Competitive Entity model and systematic pipeline.
-- Run in Supabase SQL editor:
--   https://supabase.com/dashboard/project/tghntyofptvfhmtchwcv/sql
-- Date: 2026-05-19
-- ============================================================
--
-- ARCHITECTURE:
--   Strategic Competitive Entity
--     └── Drugs / Programs     (one or many per entity)
--           └── Trials         (one or many per drug)
--                └── Catalysts (linked to trial, drug, or entity)
--     └── Deals                (linked to entity + company)
--     └── Company Profile      (one per company × area)
--
-- DATA QUALITY FIELDS (on drugs + trials):
--   discovery_status: 'manual' | 'auto' | 'unverified' | 'verified'
--   confidence_score: 0–100 integer (higher = more reliable)
--   last_synced_date: when ct_gov_sync last updated this record
-- ============================================================


-- ────────────────────────────────────────────────────────────
-- 1. TRIALS — add all missing structured fields
--    Existing: id (NCT ID), drug_id, indication, phase,
--              primary_endpoint, status, trial_name,
--              n_enrollment, pcd_label, readout_date, results_note
--    Adding:   arms, secondary_endpoints, start_date,
--              primary_completion_date, source_url,
--              last_synced_date, discovery_status, confidence_score,
--              entity_id, sponsor
-- ────────────────────────────────────────────────────────────

ALTER TABLE trials
  -- CT.gov structured fields
  ADD COLUMN IF NOT EXISTS arms                  JSONB,
    -- [{label, type, description}] arm group definitions
  ADD COLUMN IF NOT EXISTS secondary_endpoints   JSONB,
    -- [{measure, time_frame}] array from CT.gov
  ADD COLUMN IF NOT EXISTS start_date            TEXT,
    -- e.g. "2023-01-15" (ACTUAL) or "2024-Q3" (ESTIMATED)
  ADD COLUMN IF NOT EXISTS primary_completion_date TEXT,
    -- ISO date string from CT.gov
  ADD COLUMN IF NOT EXISTS source_url            TEXT,
    -- https://clinicaltrials.gov/study/NCT...
  ADD COLUMN IF NOT EXISTS sponsor               TEXT,
    -- Lead sponsor name from CT.gov
  -- Data quality / pipeline tracking
  ADD COLUMN IF NOT EXISTS last_synced_date      TIMESTAMPTZ,
    -- When ct_gov_sync last fetched this record
  ADD COLUMN IF NOT EXISTS discovery_status      TEXT DEFAULT 'manual',
    -- 'manual'=hardcoded seed | 'auto'=pipeline found, high confidence
    -- 'unverified'=pipeline found, needs review | 'verified'=human confirmed
  ADD COLUMN IF NOT EXISTS confidence_score      INTEGER DEFAULT 100,
    -- 0-100: how confident we are this trial belongs to this drug
  -- Cross-reference
  ADD COLUMN IF NOT EXISTS entity_id             TEXT;
    -- Denormalized from drug.entity_id for direct entity→trials lookups

COMMENT ON COLUMN trials.discovery_status IS
  'manual=seeded | auto=pipeline-discovered (high confidence) | unverified=needs review | verified=human-confirmed';
COMMENT ON COLUMN trials.confidence_score IS
  '0-100 confidence that this CT.gov study matches the drug record. 100=direct NCT ID match, 60-84=name search match, <60=skip';


-- ────────────────────────────────────────────────────────────
-- 2. DRUGS — add intelligence architecture fields
--    Existing: id, name, company_id, entity_id, entity_name,
--              entity_type, stage, cls, overlap, mechanism,
--              target, indication_short, stage_detail, route,
--              dosing_type, drug_format, etc.
--    Adding:   aliases, differentiation_thesis,
--              discovery_status, confidence_score,
--              trial_data_status, last_synced_date
-- ────────────────────────────────────────────────────────────

ALTER TABLE drugs
  ADD COLUMN IF NOT EXISTS aliases               JSONB,
    -- ["QX030N", "HXN-1003"] array of alternate names / prior names
  ADD COLUMN IF NOT EXISTS differentiation_thesis TEXT,
    -- 1-2 sentences: what makes this drug distinctly different
  ADD COLUMN IF NOT EXISTS discovery_status      TEXT DEFAULT 'manual',
    -- same values as trials.discovery_status
  ADD COLUMN IF NOT EXISTS confidence_score      INTEGER DEFAULT 100,
  ADD COLUMN IF NOT EXISTS trial_data_status     TEXT DEFAULT 'unknown',
    -- 'populated'=trials table has records | 'missing'=no NCT ID found
    -- 'searching'=pipeline is looking | 'pending'=pre-IND/no trial yet
  ADD COLUMN IF NOT EXISTS last_synced_date      TIMESTAMPTZ;
    -- When ct_gov_sync last processed this drug

COMMENT ON COLUMN drugs.aliases IS
  'JSON array of alternate names. e.g. ["QX030N", "CLD-423"] for the same molecule.';
COMMENT ON COLUMN drugs.trial_data_status IS
  'populated=trials table has records | missing=searched, no NCT found | searching=pipeline looking | pending=pre-IND';


-- ────────────────────────────────────────────────────────────
-- 3. COMPANY_PROFILES — add financial + strategic depth fields
--    Existing: company_id, area_id, platform_summary, bd_summary,
--              key_risk, why_it_matters, pipeline_url,
--              research_sources, last_enriched_at, enriched_by
--    Adding:   market_cap_usd_m, cash_runway, financing_history,
--              key_investors, strategic_behavior, vs_ailux,
--              hq_country, website
-- ────────────────────────────────────────────────────────────

ALTER TABLE company_profiles
  ADD COLUMN IF NOT EXISTS market_cap_usd_m      NUMERIC,
    -- Market cap in USD millions (public companies)
  ADD COLUMN IF NOT EXISTS cash_runway           TEXT,
    -- Human readable: "H2 2028", "~18 months (YE 2026)"
  ADD COLUMN IF NOT EXISTS financing_history     JSONB,
    -- [{date, amount_usd_m, series, investors}] most recent first
  ADD COLUMN IF NOT EXISTS key_investors         JSONB,
    -- ["Farallon", "Foresite Capital", "RA Capital"] array
  ADD COLUMN IF NOT EXISTS strategic_behavior    TEXT,
    -- How this company typically behaves in BD: acquirer, licensor, partner-seeker
  ADD COLUMN IF NOT EXISTS vs_ailux              TEXT,
    -- 1-2 sentences: how this company's position compares to Ailux's asset
  ADD COLUMN IF NOT EXISTS hq_country            TEXT,
  ADD COLUMN IF NOT EXISTS website               TEXT;

COMMENT ON COLUMN company_profiles.financing_history IS
  'JSON array: [{date: "2024-03", amount_usd_m: 400, series: "Series B", investors: ["Blackstone"]}]';


-- ────────────────────────────────────────────────────────────
-- 4. CATALYSTS — add impact + key-watch + trial linkage
--    Existing: id, catalyst_date, sort_date, label, company_id,
--              area_id, significance, catalyst_type, notes,
--              resolved, resolved_note, drug_id
--    Adding:   expected_impact, is_key_watch, related_trial_id,
--              source_url, confidence_source
-- ────────────────────────────────────────────────────────────

ALTER TABLE catalysts
  ADD COLUMN IF NOT EXISTS expected_impact       TEXT,
    -- What Ailux should do / how this affects BD strategy if catalyst lands
  ADD COLUMN IF NOT EXISTS is_key_watch          BOOLEAN DEFAULT FALSE,
    -- TRUE = show as prominent "Key Watch" in dashboard
  ADD COLUMN IF NOT EXISTS related_trial_id      TEXT,
    -- FK to trials.id (the NCT ID) — for trial readout catalysts
  ADD COLUMN IF NOT EXISTS source_url            TEXT,
    -- Where this catalyst timing came from (press release, CT.gov, etc.)
  ADD COLUMN IF NOT EXISTS confidence_source     TEXT DEFAULT 'estimated';
    -- 'company-disclosed' | 'ctgov-pcd' | 'estimated' | 'analyst'


-- ────────────────────────────────────────────────────────────
-- 5. DEALS — add deal structure + strategic intelligence fields
--    Existing: id, deal_date, deal_date_label, from_company,
--              to_company, area_id, deal_type, upfront_usd_m,
--              total_usd_m, headline, detail, source_url,
--              ailux_signal, company_id, drug_id
--    Adding:   parties, geography_rights, economics_royalties,
--              strategic_signal, ailux_relevance, entity_id
-- ────────────────────────────────────────────────────────────

ALTER TABLE deals
  ADD COLUMN IF NOT EXISTS parties               JSONB,
    -- [{company_id, role: "acquirer|licensor|licensee|partner"}]
  ADD COLUMN IF NOT EXISTS geography_rights      TEXT,
    -- e.g. "Global ex-China", "North America + Europe", "Worldwide"
  ADD COLUMN IF NOT EXISTS economics_royalties   TEXT,
    -- Royalty/economics disclosure if available: "tiered royalties 8-15%"
  ADD COLUMN IF NOT EXISTS strategic_signal      TEXT,
    -- What this deal signals about the competitive landscape
  ADD COLUMN IF NOT EXISTS ailux_relevance       TEXT,
    -- Specific to Ailux: how does this deal change Ailux's BD strategy?
  ADD COLUMN IF NOT EXISTS entity_id             TEXT;
    -- Which strategic competitive entity this deal belongs to


-- ────────────────────────────────────────────────────────────
-- 6. INDEXES — for new columns
-- ────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_trials_entity       ON trials(entity_id);
CREATE INDEX IF NOT EXISTS idx_trials_synced       ON trials(last_synced_date DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_trials_discovery    ON trials(discovery_status);
CREATE INDEX IF NOT EXISTS idx_drugs_discovery     ON drugs(discovery_status);
CREATE INDEX IF NOT EXISTS idx_drugs_trial_status  ON drugs(trial_data_status);
CREATE INDEX IF NOT EXISTS idx_catalysts_keywatch  ON catalysts(is_key_watch) WHERE is_key_watch = TRUE;
CREATE INDEX IF NOT EXISTS idx_deals_entity        ON deals(entity_id);


-- ────────────────────────────────────────────────────────────
-- 7. BACKFILL — set entity_id on existing trial records
--    (once drug records have entity_id, propagate to trials)
-- ────────────────────────────────────────────────────────────

UPDATE trials t
SET entity_id = d.entity_id
FROM drugs d
WHERE t.drug_id = d.id
  AND t.entity_id IS NULL
  AND d.entity_id IS NOT NULL;


-- ────────────────────────────────────────────────────────────
-- 8. VIEW UPDATE — extend company_area_detail view
--    (drop and recreate to include new fields)
-- ────────────────────────────────────────────────────────────

DROP VIEW IF EXISTS company_area_detail;

CREATE OR REPLACE VIEW company_area_detail AS
  SELECT
    c.id              AS company_id,
    c.name,
    c.ticker,
    c.company_type,
    c.insight_text,
    c.ailux_angle,
    ca.area_id,
    cp.platform_summary,
    cp.bd_summary,
    cp.key_risk,
    cp.why_it_matters,
    cp.vs_ailux,
    cp.pipeline_url,
    cp.market_cap_usd_m,
    cp.cash_runway,
    cp.key_investors,
    cp.strategic_behavior,
    cp.financing_history,
    cp.last_enriched_at,
    cp.enriched_by
  FROM companies c
  JOIN company_areas    ca ON ca.company_id = c.id
  LEFT JOIN company_profiles cp ON cp.company_id = c.id AND cp.area_id = ca.area_id;

GRANT SELECT ON company_area_detail TO anon;


-- ────────────────────────────────────────────────────────────
-- Done.
-- Next step: run scripts/ct_gov_sync.py to populate trials table.
-- ────────────────────────────────────────────────────────────
