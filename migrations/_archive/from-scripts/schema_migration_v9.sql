-- ============================================================
-- BD Platform Schema Migration v9
-- Adds drug modality / characteristics columns,
-- Truth State (confidence_level + data_source) on drugs and catalysts,
-- and expected_evidence_stage for completeness-scoring calibration.
--
-- Design principle:
--   Every drug row should carry enough characterisation to evaluate
--   competitive positioning against Ailux's TL1A×IL-23p19 bispecific.
--   Truth State fields distinguish Claude-inferred data from
--   CT.gov-confirmed or SEC-filed data so the platform can surface
--   evidence reliability alongside the data itself.
-- ============================================================

-- ── 1. Drug characteristics (ensure columns exist) ───────────────────────────
-- Some of these may already be present if added via PATCH — IF NOT EXISTS guards.

ALTER TABLE drugs
  ADD COLUMN IF NOT EXISTS modality          TEXT,        -- e.g. 'mAb', 'bispecific', 'small molecule', 'ADC'
  ADD COLUMN IF NOT EXISTS route             TEXT,        -- 'SC', 'IV', 'SC/IV', 'oral'
  ADD COLUMN IF NOT EXISTS drug_format       TEXT,        -- short UI label: same values as modality; kept for legacy
  ADD COLUMN IF NOT EXISTS dosing_type       TEXT,        -- 'Induction', 'Maintenance', 'Induction + Maintenance'
  ADD COLUMN IF NOT EXISTS dosing_schedule   TEXT,        -- e.g. 'Q3M SC', 'QD oral', '600mg IV Q8W'
  ADD COLUMN IF NOT EXISTS half_life_note    TEXT,        -- e.g. '~74 days', 'not disclosed'
  ADD COLUMN IF NOT EXISTS indication_short  TEXT,        -- e.g. 'UC · CD', 'UC'
  ADD COLUMN IF NOT EXISTS stage_detail      TEXT,        -- e.g. 'Phase 2b (ARTEMIS-CD)', 'Approved (US, EU)'
  ADD COLUMN IF NOT EXISTS key_data          TEXT,        -- latest clinical data headline
  ADD COLUMN IF NOT EXISTS mechanism_detail  TEXT,        -- full mechanism description
  ADD COLUMN IF NOT EXISTS is_combo          BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS aliases           JSONB DEFAULT '[]'::jsonb;

-- ── 2. Truth State — drugs ────────────────────────────────────────────────────
-- confidence_level: epistemic status of the drug data row
-- data_source:      primary evidence source for stage / clinical information

ALTER TABLE drugs
  ADD COLUMN IF NOT EXISTS confidence_level TEXT DEFAULT 'inferred',
  ADD COLUMN IF NOT EXISTS data_source      TEXT DEFAULT 'claude_inferred';

-- Valid values (not enforced by constraint — allow evolution):
--   confidence_level: confirmed | supported | inferred | contradictory | unknown
--   data_source:      ct_gov | sec_filing | press_release | conference | claude_inferred | manual

COMMENT ON COLUMN drugs.confidence_level IS
  'Epistemic status: confirmed (CT.gov/SEC), supported (multiple secondary), inferred (Claude reasoning), contradictory (sources disagree), unknown.';

COMMENT ON COLUMN drugs.data_source IS
  'Primary evidence source for stage/clinical data: ct_gov | sec_filing | press_release | conference | claude_inferred | manual.';

-- ── 3. Expected Evidence Stage — drugs ───────────────────────────────────────
-- Prevents preclinical / IND-stage companies from being penalised by completeness
-- scoring for missing trial data. The pipeline reads this to adjust scoring floors.
--
-- Maps to completeness scoring stages 0-5:
--   0  basic_identity
--   1  drug_programs
--   2  clinical_evidence (trials — not expected for Preclinical)
--   3  profile_narrative
--   4  catalysts_deals
--   5  vs_ailux

ALTER TABLE drugs
  ADD COLUMN IF NOT EXISTS expected_evidence_stage INTEGER DEFAULT 2;

-- Seed expected_evidence_stage from existing stage values
UPDATE drugs SET expected_evidence_stage = 1
  WHERE stage IN ('Preclinical', 'IND-enabling', 'Pre-IND')
  AND   expected_evidence_stage = 2;  -- only update rows still at default

UPDATE drugs SET expected_evidence_stage = 2
  WHERE stage = 'Phase 1'
  AND   expected_evidence_stage = 2;

UPDATE drugs SET expected_evidence_stage = 3
  WHERE stage = 'Phase 2'
  AND   expected_evidence_stage = 2;

UPDATE drugs SET expected_evidence_stage = 4
  WHERE stage = 'Phase 3'
  AND   expected_evidence_stage = 2;

UPDATE drugs SET expected_evidence_stage = 5
  WHERE stage = 'Approved'
  AND   expected_evidence_stage = 2;

COMMENT ON COLUMN drugs.expected_evidence_stage IS
  'Maximum completeness-scoring stage expected for this drug given its development phase. Preclinical = 1 (no trial data expected). Adjusted at enrichment time.';

-- ── 4. Truth State — catalysts ────────────────────────────────────────────────
ALTER TABLE catalysts
  ADD COLUMN IF NOT EXISTS confidence_level TEXT DEFAULT 'inferred';

COMMENT ON COLUMN catalysts.confidence_level IS
  'Evidence reliability for this catalyst: confirmed (company filing/PDUFA), supported, inferred (Claude reasoning from trial dates), unknown.';

-- Update existing CT.gov-sourced catalysts
UPDATE catalysts SET confidence_level = 'confirmed'
  WHERE confidence_source = 'ctgov-pcd'
  AND   confidence_level   = 'inferred';

UPDATE catalysts SET confidence_level = 'supported'
  WHERE confidence_source = 'company-disclosed'
  AND   confidence_level   = 'inferred';

-- ── 5. Indexes ────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS drugs_confidence_level_idx      ON drugs (confidence_level);
CREATE INDEX IF NOT EXISTS drugs_data_source_idx           ON drugs (data_source);
CREATE INDEX IF NOT EXISTS drugs_expected_evidence_stage_idx ON drugs (expected_evidence_stage);
CREATE INDEX IF NOT EXISTS catalysts_confidence_level_idx  ON catalysts (confidence_level);

-- ── 6. Comments ───────────────────────────────────────────────────────────────
COMMENT ON COLUMN drugs.modality IS
  'Drug format class: mAb | bispecific | small molecule | ADC | nanobody | fusion protein | oligonucleotide. Use drug_format for short UI labels.';

COMMENT ON COLUMN drugs.expected_evidence_stage IS
  'Maximum completeness-scoring stage expected for this drug given its development phase. Preclinical = 1 (no trial data expected).';
