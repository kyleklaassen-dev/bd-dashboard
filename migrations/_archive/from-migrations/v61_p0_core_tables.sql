-- =============================================================================
-- Migration v61: P0 Core Table Fixes
-- Applied: 2026-05-28
-- Purpose: Fill governance-critical gaps in company_partnerships, molecule_intelligence,
--          indication_patient_intelligence, and entity_relationships.
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- TASK 1: EXPAND company_partnerships to match CLAUDE.md governance schema
-- Existing table uses lead_company_id/partner_name; add governance columns.
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE company_partnerships
  ADD COLUMN IF NOT EXISTS company_id TEXT,
  ADD COLUMN IF NOT EXISTS deal_type TEXT CHECK (deal_type IN (
      'licensing', 'co-development', 'option', 'collaboration',
      'acquisition', 'distribution', 'co-promotion', 'discovery'
  )),
  ADD COLUMN IF NOT EXISTS partner_company_name TEXT,
  ADD COLUMN IF NOT EXISTS partnership_verified BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS source_url TEXT,
  ADD COLUMN IF NOT EXISTS geographic_rights TEXT,
  ADD COLUMN IF NOT EXISTS start_date DATE,
  ADD COLUMN IF NOT EXISTS end_date DATE,
  ADD COLUMN IF NOT EXISTS is_current BOOLEAN DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS notes TEXT,
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

UPDATE company_partnerships
SET company_id = lead_company_id
WHERE company_id IS NULL;

UPDATE company_partnerships
SET partner_company_name = partner_name
WHERE partner_company_name IS NULL;

UPDATE company_partnerships
SET deal_type = CASE
  WHEN partnership_type IN ('licensed_in', 'licensed_out') THEN 'licensing'
  WHEN partnership_type = 'co_developed' THEN 'co-development'
  WHEN partnership_type = 'option' THEN 'option'
  WHEN partnership_type = 'collaboration' THEN 'collaboration'
  ELSE 'licensing'
END
WHERE deal_type IS NULL AND partnership_type IS NOT NULL;

CREATE INDEX IF NOT EXISTS cp_company_id_idx ON company_partnerships(company_id);
CREATE INDEX IF NOT EXISTS cp_deal_type_idx ON company_partnerships(deal_type);
CREATE INDEX IF NOT EXISTS cp_is_current_idx ON company_partnerships(is_current);
CREATE INDEX IF NOT EXISTS cp_drug_id_fk_idx ON company_partnerships(drug_id);

CREATE OR REPLACE FUNCTION update_company_partnerships_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_cp_updated_at ON company_partnerships;
CREATE TRIGGER trg_cp_updated_at
BEFORE UPDATE ON company_partnerships
FOR EACH ROW EXECUTE FUNCTION update_company_partnerships_updated_at();

UPDATE company_partnerships
SET
  company_id           = 'futuregen',
  deal_type            = 'licensing',
  partnership_verified = FALSE,
  source_url           = 'https://www.futuregen-biopharma.com/pipeline',
  notes                = 'FutureGen (originator) out-licensed ABBV-701 to AbbVie. AbbVie holds global rights. Phase 1 readout expected Oct 2026. AbbVie constraint applies per deal_sequencing_constraints.',
  is_current           = TRUE,
  updated_at           = NOW()
WHERE lead_company_id = 'abbvie' AND partner_company_id = 'futuregen' AND drug_id = 'fg-m701';

UPDATE company_partnerships
SET
  company_id           = 'simcere',
  deal_type            = 'licensing',
  partnership_verified = TRUE,
  source_url           = 'https://www.boehringer-ingelheim.com/press-release/boehringer-ingelheim-and-simcere-pharmaceutical-announce-license-agreement-sim0709',
  notes                = 'Simcere (originator) out-licensed SIM0709 (TL1A×IL-23p19) to Boehringer Ingelheim. EUR42M upfront, EUR1.05B total.',
  is_current           = TRUE,
  updated_at           = NOW()
WHERE lead_company_id = 'simcere' AND partnership_type = 'licensed_out';

INSERT INTO company_partnerships (
  lead_company_id, partner_name, partner_company_id, partnership_type,
  company_id, deal_type, drug_id, partnership_verified,
  source_url, notes, is_current
)
SELECT
  'lanova', 'Zymeworks', 'zymeworks', 'licensed_out',
  'lanova', 'licensing', 'lq080', TRUE,
  'https://www.zymeworks.com/pipeline/',
  'LaNova (originator) out-licensed LQ080/ZW191 (TL1A x IL-23p19 VHH nanobody) to Zymeworks. Global ex-China rights.',
  TRUE
WHERE NOT EXISTS (
  SELECT 1 FROM company_partnerships
  WHERE lead_company_id = 'lanova' AND partner_company_id = 'zymeworks' AND drug_id = 'lq080'
);

INSERT INTO company_partnerships (
  lead_company_id, partner_name, partner_company_id, partnership_type,
  company_id, deal_type, drug_id, partnership_verified,
  source_url, notes, is_current
)
SELECT
  'qyuns', 'Caldera Therapeutics', 'caldera', 'licensed_out',
  'qyuns', 'licensing', 'qx030n', TRUE,
  'https://www.businesswire.com/news/home/20250423764573/en/Caldera-Therapeutics-Launches-with-75-Million-Series-A-Financing-and-License-Agreement-for-Novel-Bispecific-Antibody-to-Treat-Inflammatory-Bowel-Disease',
  'Qyuns (originator) out-licensed CLD-423/QX030N (TL1A x IL-23p19) to Caldera. $10M + equity, $545M total.',
  TRUE
WHERE NOT EXISTS (
  SELECT 1 FROM company_partnerships
  WHERE lead_company_id = 'qyuns' AND partner_company_id = 'caldera' AND drug_id = 'qx030n'
);

-- ─────────────────────────────────────────────────────────────────────────────
-- TASK 2: ALTER molecule_intelligence
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE molecule_intelligence
  ADD COLUMN IF NOT EXISTS enrichment_run_id UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW(),
  ADD COLUMN IF NOT EXISTS source_url TEXT,
  ADD COLUMN IF NOT EXISTS model_version TEXT,
  ADD COLUMN IF NOT EXISTS confidence TEXT DEFAULT 'model'
    CHECK (confidence IN ('verified', 'model', 'inferred', 'unknown'));

UPDATE molecule_intelligence SET updated_at = NOW() WHERE updated_at IS NULL;

CREATE OR REPLACE FUNCTION update_molecule_intelligence_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_mi_updated_at ON molecule_intelligence;
CREATE TRIGGER trg_mi_updated_at
BEFORE UPDATE ON molecule_intelligence
FOR EACH ROW EXECUTE FUNCTION update_molecule_intelligence_updated_at();

-- ─────────────────────────────────────────────────────────────────────────────
-- TASK 3: ALTER indication_patient_intelligence
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE indication_patient_intelligence
  ADD COLUMN IF NOT EXISTS enrichment_run_id UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW(),
  ADD COLUMN IF NOT EXISTS model_version TEXT;

UPDATE indication_patient_intelligence
SET updated_at = last_updated::TIMESTAMPTZ
WHERE updated_at IS NULL AND last_updated IS NOT NULL;

UPDATE indication_patient_intelligence
SET updated_at = NOW()
WHERE updated_at IS NULL;

-- ─────────────────────────────────────────────────────────────────────────────
-- TASK 4: ALTER entity_relationships
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE entity_relationships
  ADD COLUMN IF NOT EXISTS source_url TEXT,
  ADD COLUMN IF NOT EXISTS verification_needed BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS enrichment_run_id UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL;

UPDATE entity_relationships
SET confidence = 'inferred'
WHERE confidence = 'medium';

UPDATE entity_relationships
SET verification_needed = TRUE,
    confidence = COALESCE(NULLIF(confidence, ''), 'model')
WHERE source_url IS NULL OR source_url = '';

UPDATE entity_relationships
SET verification_needed = FALSE,
    confidence = 'verified'
WHERE source_url IS NOT NULL AND source_url != '';
