-- area_metadata DDL
-- Session 61 — 2026-05-26
-- Converts drug_areas disposition documents into a queryable governance table.
-- Apply via: Supabase SQL Editor → New Query
--
-- Design: advisor-specified (Session 61)
-- Source data: docs/drug_areas_disposition_report.md
-- Governance rule: "Future governance queries should hit a table, not parse markdown."

-- ── Main table ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS area_metadata (
  area_id                TEXT    PRIMARY KEY,
  display_name           TEXT    NOT NULL,

  -- Classification
  category               TEXT    NOT NULL CHECK (category IN (
    'ontology_biological',  -- biological target/indication — should be driven by drug_targets/drug_indications
    'curated_strategic',    -- strategic view — driven by company_strategic_views
    'curated_platform'      -- platform modality view — driven by company_platform_views
  )),

  -- Lifecycle
  lifecycle_state        TEXT    NOT NULL CHECK (lifecycle_state IN (
    'active',               -- currently used as primary runtime source
    'redirected',           -- redirected to normalized source; legacy still exists for provenance
    'retired',              -- fully retired, no active reads
    'preserved_curated',    -- preserved as curated strategic view, not an ontology redirect
    'preserved_platform'    -- preserved as platform modality view
  )),

  -- Runtime sources
  current_runtime_source TEXT,   -- current dashboard query source (legacy or normalized)
  normalized_replacement TEXT,   -- target normalized source after full migration

  -- Feature flag (Phase 5 activation tracking)
  feature_flag           TEXT,   -- e.g. 'useUnifiedTL1A', 'useNormalizedIBD'
  flag_activated_at      DATE,   -- date flag was permanently set to true

  -- Retirement sequencing
  retirement_phase       TEXT,   -- e.g. 'phase_5.3', 'phase_5.5'
  retirement_status      TEXT    CHECK (retirement_status IN (
    'not_started',
    'flag_activated',       -- feature flag flipped; legacy retained for monitoring
    'monitoring',           -- in 30-day monitoring window post-activation
    'legacy_retained',      -- monitoring complete; legacy code retained per 30-day rule
    'ready_to_retire',      -- 30-day window elapsed; legacy safe to remove
    'retired'               -- legacy code removed
  )),

  -- Metadata
  notes                  TEXT,
  last_reviewed_at       DATE    DEFAULT CURRENT_DATE,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── updated_at trigger ────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_area_metadata_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_area_metadata_updated_at
  BEFORE UPDATE ON area_metadata
  FOR EACH ROW EXECUTE FUNCTION update_area_metadata_updated_at();

-- ── RLS (match existing table patterns) ──────────────────────────────────────
ALTER TABLE area_metadata ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_read_area_metadata"
  ON area_metadata FOR SELECT USING (true);

CREATE POLICY "service_write_area_metadata"
  ON area_metadata FOR ALL USING (auth.role() = 'service_role');

-- ── Seed: all 11 area_ids ────────────────────────────────────────────────────
-- Sources: docs/drug_areas_disposition_report.md, docs/redirected_entities_inventory.md
-- Activation dates from update_log.md

INSERT INTO area_metadata (
  area_id, display_name, category, lifecycle_state,
  current_runtime_source, normalized_replacement,
  feature_flag, flag_activated_at,
  retirement_phase, retirement_status, notes, last_reviewed_at
) VALUES

-- ── Redirected (ontology_biological → fully migrated) ─────────────────────
('ibd',
 'IBD (UC + CD)',
 'ontology_biological',
 'redirected',
 'drug_indications WHERE indication_id IN (''uc'',''cd'')',
 'drug_indications WHERE indication_id IN (''uc'',''cd'')',
 'useNormalizedIBD',
 '2026-05-25',
 'phase_5.3',
 'legacy_retained',
 'Activated 2026-05-25. IBD drugs split into UC/CD per drug_indications. Legacy drug_areas(ibd) retained per 30-day rule.',
 '2026-05-26'),

('igf1r',
 'IGF-1R / TED',
 'ontology_biological',
 'redirected',
 'drug_indications WHERE indication_id = ''ted''',
 'drug_indications WHERE indication_id = ''ted''',
 'useNormalizedTED',
 '2026-05-25',
 'phase_5.3',
 'legacy_retained',
 'Activated 2026-05-25 (shared with ted area_id). TED consolidated from igf1r+ted into single indication context. Legacy retained per 30-day rule.',
 '2026-05-26'),

('ted',
 'TED (Thyroid Eye Disease)',
 'ontology_biological',
 'redirected',
 'drug_indications WHERE indication_id = ''ted''',
 'drug_indications WHERE indication_id = ''ted''',
 'useNormalizedTED',
 '2026-05-25',
 'phase_5.3',
 'legacy_retained',
 'Activated 2026-05-25. Alias of igf1r area (same indication context). UNIQUE deduplication handles ted+igf1r overlap.',
 '2026-05-26'),

('tl1a',
 'TL1A',
 'ontology_biological',
 'redirected',
 'drug_targets WHERE target_id = ''tl1a''',
 'drug_targets WHERE target_id = ''tl1a''',
 'useUnifiedTL1A',
 '2026-05-25',
 'phase_5.3',
 'legacy_retained',
 'Activated 2026-05-25. 50→34 drugs (17 scope_diff IBD competitors correctly excluded). adj=100%. Legacy retained per 30-day rule.',
 '2026-05-26'),

('il4ra',
 'IL-4Rα',
 'ontology_biological',
 'redirected',
 'drug_targets WHERE target_id = ''il4ra''',
 'drug_targets WHERE target_id = ''il4ra''',
 'useUnifiedAtopy',
 '2026-05-26',
 'phase_5.4',
 'legacy_retained',
 'Activated 2026-05-26 (shared useUnifiedAtopy flag with tslp/atopy). 9→5 drugs (scopeDiff=5 pathway partners excluded). adj=100%.',
 '2026-05-26'),

('tslp',
 'TSLP',
 'ontology_biological',
 'redirected',
 'drug_targets WHERE target_id IN (''tslp'',''tslpr'')',
 'drug_targets WHERE target_id IN (''tslp'',''tslpr'')',
 'useUnifiedAtopy',
 '2026-05-26',
 'phase_5.4',
 'legacy_retained',
 'Activated 2026-05-26. Query includes tslpr (verekitug targets TSLP receptor). 14→10 drugs (scopeDiff=6). adj=100%.',
 '2026-05-26'),

('atopy',
 'Atopy (IL-4Rα + TSLP)',
 'ontology_biological',
 'redirected',
 'drug_targets WHERE target_id IN (''il4ra'',''tslp'',''tslpr'')',
 'drug_targets WHERE target_id IN (''il4ra'',''tslp'',''tslpr'')',
 'useUnifiedAtopy',
 '2026-05-26',
 'phase_5.4',
 'legacy_retained',
 'Activated 2026-05-26. Composite of il4ra+tslp areas — per-drug context expansion based on drug_targets.',
 '2026-05-26'),

('fcrn',
 'FcRn',
 'ontology_biological',
 'redirected',
 'drug_targets WHERE target_id = ''fcrn''',
 'drug_targets WHERE target_id = ''fcrn''',
 'useUnifiedFCRN',
 '2026-05-26',
 'phase_5.5',
 'flag_activated',
 'ACTIVATED 2026-05-26. Final biological tab migration. legacy=7 norm=7 overlap=6 scopeDiff=1(atg-201) adj=100%. Closes Legacy Read Layer Elimination milestone.',
 '2026-05-26'),

-- ── Preserved (curated views — not ontology redirects) ────────────────────
('autoimmune',
 'Autoimmune (Strategic)',
 'curated_strategic',
 'preserved_curated',
 'drug_areas WHERE area_id = ''autoimmune'' (legacy, pending WS4)',
 'company_strategic_views WHERE view_id = ''autoimmune''',
 NULL,
 NULL,
 'phase_5.4',
 'not_started',
 'Preserved as curated strategic view. No biological redirect — disease-agnostic portfolio lens. Migration to company_strategic_views planned in WS4.',
 '2026-05-26'),

('respiratory',
 'Respiratory (Strategic)',
 'curated_strategic',
 'preserved_curated',
 'drug_areas WHERE area_id = ''respiratory'' (legacy, pending WS4)',
 'company_strategic_views WHERE view_id = ''respiratory''',
 NULL,
 NULL,
 'phase_5.4',
 'not_started',
 'Preserved as curated strategic view. Respiratory portfolio lens across TSLP/IL-33/IL-5 pathway drugs. Migration to company_strategic_views planned in WS4.',
 '2026-05-26'),

('tcell',
 'T-Cell Engineering (Platform)',
 'curated_platform',
 'preserved_platform',
 'drug_areas WHERE area_id = ''tcell'' (legacy, pending WS4)',
 'company_platform_views WHERE view_id = ''tcell''',
 NULL,
 NULL,
 'phase_5.4',
 'not_started',
 'Preserved as platform modality view. CAR-T / T-cell engineering platform lens. No biological redirect. Migration to company_platform_views planned in WS4.',
 '2026-05-26')

ON CONFLICT (area_id) DO UPDATE SET
  display_name           = EXCLUDED.display_name,
  category               = EXCLUDED.category,
  lifecycle_state        = EXCLUDED.lifecycle_state,
  current_runtime_source = EXCLUDED.current_runtime_source,
  normalized_replacement = EXCLUDED.normalized_replacement,
  feature_flag           = EXCLUDED.feature_flag,
  flag_activated_at      = EXCLUDED.flag_activated_at,
  retirement_phase       = EXCLUDED.retirement_phase,
  retirement_status      = EXCLUDED.retirement_status,
  notes                  = EXCLUDED.notes,
  last_reviewed_at       = EXCLUDED.last_reviewed_at,
  updated_at             = NOW();

-- ── Verification query ────────────────────────────────────────────────────────
-- SELECT area_id, lifecycle_state, retirement_status, flag_activated_at
-- FROM area_metadata
-- ORDER BY category, lifecycle_state, area_id;

-- ── Comments ──────────────────────────────────────────────────────────────────
COMMENT ON TABLE area_metadata IS
  'Governance table for drug_areas disposition. Records lifecycle state, runtime source, normalized replacement, and retirement status for all 11 area_ids. Replaces static disposition documents with queryable governance data. Created 2026-05-26 Session 61.';
