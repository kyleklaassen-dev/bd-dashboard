-- Migration v15: Validation test framework
-- Run in Supabase SQL editor.
-- Creates the validation_tests table — the platform's immune system.
-- Every enrichment run can be graded against these known-good facts.
--
-- 2026-05-22: Initial schema. Seeded with TL1A ground truth from parity audit.

CREATE TABLE IF NOT EXISTS public.validation_tests (
  id                  SERIAL PRIMARY KEY,
  test_name           TEXT NOT NULL,           -- human-readable slug, e.g. "duvakitug-tl1a-overlap"
  test_type           TEXT NOT NULL,           -- overlap_check | company_visible | field_present | drug_exists | not_hallucinated | stage_check
  area_id             TEXT,                    -- e.g. "tl1a" — null means global
  entity_type         TEXT NOT NULL,           -- "drug" | "company" | "profile"
  entity_id           TEXT NOT NULL,           -- drug_id, company_id, or "company_id/area_id"
  field_name          TEXT,                    -- column to check, e.g. "overlap", "completeness_score", "stage"
  expected_value      TEXT NOT NULL,           -- the expected value as a string
  expected_operator   TEXT NOT NULL DEFAULT 'eq',  -- eq | ne | gte | lte | contains | not_null | is_null
  priority            TEXT NOT NULL DEFAULT 'P1',  -- P1 (regression blocker) | P2 (quality) | P3 (informational)
  source              TEXT,                    -- where this ground truth came from: "tl1a_parity_audit" | "manual" | "ct_gov"
  notes               TEXT,                    -- context: why this test exists, what it catches
  created_at          TIMESTAMPTZ DEFAULT NOW(),
  updated_at          TIMESTAMPTZ DEFAULT NOW(),

  -- Result tracking (written by validate_ground_truth.py after each run)
  last_checked_at     TIMESTAMPTZ,
  last_actual_value   TEXT,
  last_pass_fail      TEXT,                    -- "pass" | "fail" | "skip" | "error"
  consecutive_failures INT DEFAULT 0,
  last_failure_at     TIMESTAMPTZ
);

-- Index for fast lookup by area + type
CREATE INDEX IF NOT EXISTS validation_tests_area_type ON validation_tests (area_id, test_type);
CREATE INDEX IF NOT EXISTS validation_tests_priority ON validation_tests (priority, last_pass_fail);

-- Unique test name per area (prevents duplicate tests)
CREATE UNIQUE INDEX IF NOT EXISTS validation_tests_name_area ON validation_tests (test_name, COALESCE(area_id, ''));

-- Seed: TL1A overlap ground truth (from parity audit 2026-05-22)
-- These are facts verified against clinical literature and the legacy curated dataset.

INSERT INTO public.validation_tests
  (test_name, test_type, area_id, entity_type, entity_id, field_name, expected_value, expected_operator, priority, source, notes)
VALUES

-- ── OVERLAP: Direct competitors (TL1A target, same mechanism as SPY002) ──
('duvakitug-tl1a-overlap',        'overlap_check', 'tl1a', 'drug', 'duvakitug',      'overlap', 'Direct',     'eq', 'P1', 'tl1a_parity_audit', 'Sanofi anti-TL1A mAb, most advanced competitor'),
('tulisokibart-tl1a-overlap',     'overlap_check', 'tl1a', 'drug', 'tulisokibart',   'overlap', 'Direct',     'eq', 'P1', 'tl1a_parity_audit', 'Teva/Roche anti-TL1A mAb (Phase 3)'),
('tozorakimab-tl1a-overlap',      'overlap_check', 'tl1a', 'drug', 'tozorakimab',   'overlap', 'Direct',     'eq', 'P1', 'tl1a_parity_audit', 'AZ anti-TL1A — Watch in TL1A (TSLP/IL-33 primary)'),
('abbv-701-tl1a-overlap',         'overlap_check', 'tl1a', 'drug', 'abbv-701',      'overlap', 'Direct',     'eq', 'P1', 'tl1a_parity_audit', 'AbbVie anti-TL1A mAb (ex-FutureGen FG-M701)'),
('cld-423-tl1a-overlap',          'overlap_check', 'tl1a', 'drug', 'cld-423',       'overlap', 'Direct',     'eq', 'P1', 'tl1a_parity_audit', 'Caldera anti-TL1A'),
('spy002-tl1a-overlap',           'overlap_check', 'tl1a', 'drug', 'spy002',        'overlap', 'Direct',     'eq', 'P1', 'tl1a_parity_audit', 'Ailux/Spyre TL1A×IL-23p19 bispecific — the anchor'),
('jnj-64304500-tl1a-overlap',     'overlap_check', 'tl1a', 'drug', 'jnj-64304500', 'overlap', 'Direct',     'eq', 'P1', 'tl1a_parity_audit', 'J&J anti-TL1A mAb'),

-- ── OVERLAP: Adjacent (same IBD biology, validates mechanism, combo candidate) ──
('risankizumab-tl1a-overlap',     'overlap_check', 'tl1a', 'drug', 'risankizumab',  'overlap', 'Adjacent',   'eq', 'P1', 'tl1a_parity_audit', 'Abbvie IL-23p19, canonical Adjacent — validates biology'),
('mirikizumab-tl1a-overlap',      'overlap_check', 'tl1a', 'drug', 'mirikizumab',   'overlap', 'Adjacent',   'eq', 'P1', 'tl1a_parity_audit', 'Lilly IL-23p19 (Omvoh), approved UC'),
('guselkumab-tl1a-overlap',       'overlap_check', 'tl1a', 'drug', 'guselkumab',    'overlap', 'Adjacent',   'eq', 'P1', 'tl1a_parity_audit', 'J&J IL-23p19 (Tremfya), IBD expansion'),

-- ── OVERLAP: Same-Space (approved SOC, different pathway, sets efficacy bar) ──
('ustekinumab-tl1a-overlap',      'overlap_check', 'tl1a', 'drug', 'ustekinumab',   'overlap', 'Same-Space', 'eq', 'P1', 'tl1a_parity_audit', 'IL-12/23 blocker (Stelara), approved CD+UC, canonical Same-Space'),

-- ── OVERLAP: Watch (different mechanism, same patients) ──
('golimumab-tl1a-overlap',        'overlap_check', 'tl1a', 'drug', 'golimumab',     'overlap', 'Watch',      'eq', 'P1', 'tl1a_parity_audit', 'TNF inhibitor — Watch, not Same-Space; was mis-classified'),
('upadacitinib-tl1a-overlap',     'overlap_check', 'tl1a', 'drug', 'upadacitinib',  'overlap', 'Watch',      'eq', 'P1', 'tl1a_parity_audit', 'JAK1 inhibitor (Rinvoq) — Watch tier'),

-- ── COMPANY VISIBILITY: Critical companies must appear in TL1A area ──
('sanofi-visible-tl1a',           'company_visible', 'tl1a', 'company', 'sanofi',   NULL, 'true', 'eq', 'P1', 'tl1a_parity_audit', 'Sanofi duvakitug is the most advanced TL1A competitor'),
('abbvie-visible-tl1a',           'company_visible', 'tl1a', 'company', 'abbvie',   NULL, 'true', 'eq', 'P1', 'tl1a_parity_audit', 'AbbVie ABBV-701, major TL1A player'),
('jnj-visible-tl1a',              'company_visible', 'tl1a', 'company', 'jnj',      NULL, 'true', 'eq', 'P1', 'tl1a_parity_audit', 'J&J has TL1A program and risankizumab'),
('roche-visible-tl1a',            'company_visible', 'tl1a', 'company', 'roche',    NULL, 'true', 'eq', 'P1', 'tl1a_parity_audit', 'Roche afimkibart + tulisokibart'),
('teva-visible-tl1a',             'company_visible', 'tl1a', 'company', 'teva',     NULL, 'true', 'eq', 'P1', 'tl1a_parity_audit', 'Teva duvakitug co-dev partner'),
('lilly-visible-tl1a',            'company_visible', 'tl1a', 'company', 'lilly',    NULL, 'true', 'eq', 'P2', 'tl1a_parity_audit', 'Lilly mirikizumab IBD approved'),
('merck-visible-tl1a',            'company_visible', 'tl1a', 'company', 'merck',    NULL, 'true', 'eq', 'P1', 'tl1a_parity_audit', 'Merck acquired Prometheus + tulisokibart'),
('caldera-visible-tl1a',          'company_visible', 'tl1a', 'company', 'caldera',  NULL, 'true', 'eq', 'P2', 'tl1a_parity_audit', 'Caldera CLD-423 Phase 1'),

-- ── FIELD PRESENCE: Key company profiles must have BD-critical fields ──
('sanofi-tl1a-has-bd-summary',    'field_present', 'tl1a', 'profile', 'sanofi',    'bd_summary',    'true', 'not_null', 'P1', 'manual', 'BD posture summary is required for every major TL1A competitor'),
('abbvie-tl1a-has-bd-summary',    'field_present', 'tl1a', 'profile', 'abbvie',    'bd_summary',    'true', 'not_null', 'P1', 'manual', ''),
('sanofi-tl1a-has-key-risk',      'field_present', 'tl1a', 'profile', 'sanofi',    'key_risk',      'true', 'not_null', 'P1', 'manual', 'Key risk required for every P1-tier company'),
('sanofi-tl1a-has-vs-ailux',      'field_present', 'tl1a', 'profile', 'sanofi',    'vs_ailux',      'true', 'not_null', 'P1', 'manual', 'vs_ailux comparison required for positioning'),

-- ── NOT HALLUCINATED: Known fabricated assets — these should NOT exist ──
-- (Add specific hallucinations discovered during enrichment review)
-- Example template (uncomment and fill when a hallucination is discovered):
-- ('zen3694-not-in-tl1a',    'not_hallucinated', 'tl1a', 'drug', 'zen3694',    'overlap', NULL, 'is_null', 'P1', 'manual', 'ZEN3694 is a BET bromodomain inhibitor — not a TL1A asset'),

-- ── STAGE CHECKS: Approved drugs must show as Approved ──
('risankizumab-stage-approved',   'stage_check', 'tl1a', 'drug', 'risankizumab',  'stage', 'Approved', 'eq', 'P2', 'ct_gov', 'Skyrizi approved CD+UC'),
('ustekinumab-stage-approved',    'stage_check', 'tl1a', 'drug', 'ustekinumab',   'stage', 'Approved', 'eq', 'P2', 'ct_gov', 'Stelara approved CD+UC (Jansen/J&J)'),
('upadacitinib-stage-approved',   'stage_check', 'tl1a', 'drug', 'upadacitinib',  'stage', 'Approved', 'eq', 'P2', 'ct_gov', 'Rinvoq approved UC+CD')

ON CONFLICT (test_name, COALESCE(area_id, '')) DO UPDATE SET
  expected_value    = EXCLUDED.expected_value,
  expected_operator = EXCLUDED.expected_operator,
  notes             = EXCLUDED.notes,
  updated_at        = NOW();

-- Verify:
-- SELECT test_type, COUNT(*) FROM validation_tests GROUP BY test_type ORDER BY test_type;
