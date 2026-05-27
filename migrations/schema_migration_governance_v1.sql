-- Governance Violations Table — Migration v1
-- Created: 2026-05-27
-- Purpose: Track data integrity violations against governance rules.
-- Violations are soft (logged, not hard-blocking) to allow enrichment to continue
-- while surfacing issues for human review.

CREATE TABLE IF NOT EXISTS governance_violations (
  id BIGSERIAL PRIMARY KEY,
  table_name TEXT NOT NULL,
  row_id TEXT NOT NULL,
  rule_name TEXT NOT NULL,
  description TEXT,
  detected_at TIMESTAMPTZ DEFAULT NOW(),
  resolved BOOLEAN DEFAULT FALSE,
  resolved_at TIMESTAMPTZ,
  resolved_by TEXT,
  resolution_notes TEXT,
  UNIQUE(table_name, row_id, rule_name)
);

CREATE INDEX IF NOT EXISTS governance_violations_resolved_idx 
  ON governance_violations(resolved) WHERE resolved = FALSE;

CREATE INDEX IF NOT EXISTS governance_violations_rule_idx 
  ON governance_violations(rule_name);

-- Seed: brand_name_implies_approved violations (found 2026-05-27)
-- These drugs have a brand_name set but stage is not an approved variant.
-- brand_name "—" is a data entry error (dash used as placeholder) — should be NULL or cleared.
-- brand_name "HY-6725" for catalog-53 appears to be a catalog/reagent number, not a brand name.
-- brand_name "TARGET-CD (M24-885)" appears to be a trial name, not a brand name.
INSERT INTO governance_violations (table_name, row_id, rule_name, description)
VALUES
  ('drugs', 'astegolimab', 'brand_name_implies_approved',
   'astegolimab has brand_name="—" (dash placeholder) but stage=Phase 3. Clear brand_name or update stage.'),
  ('drugs', 'caba-201', 'brand_name_implies_approved',
   'CABA-201 has brand_name="—" (dash placeholder) but stage=Phase 2. Clear brand_name.'),
  ('drugs', 'catalog-53', 'brand_name_implies_approved',
   'Newsoara TSLP Ab (catalog-53) has brand_name="HY-6725" (catalog reagent number, not brand) but stage=Phase 1. Clear brand_name.'),
  ('drugs', 'itepekimab', 'brand_name_implies_approved',
   'itepekimab has brand_name="—" (dash placeholder) but stage=Phase 3. Note: itepekimab (Dupixent competitor) IS approved as Kyntheum in EU for AD. Update stage to approved_eu or clear brand_name.'),
  ('drugs', 'risankizumab-lutikizumab-or-trosunilimab', 'brand_name_implies_approved',
   'Combination trial "risankizumab + lutikizumab or trosunilimab" has brand_name="TARGET-CD (M24-885)" which is a trial identifier, not a brand name. Clear brand_name field.')
ON CONFLICT (table_name, row_id, rule_name) DO NOTHING;

-- Seed: deals missing source_url (found 2026-05-27)
INSERT INTO governance_violations (table_name, row_id, rule_name, description)
VALUES
  ('deals', '198', 'codev_requires_source_url',
   'Agenus → Spyre licensing deal (id=198) has no source_url. Add press release URL.'),
  ('deals', '201', 'codev_requires_source_url',
   'Lanova → Zymeworks licensing deal (id=201) has no source_url. Add press release URL.')
ON CONFLICT (table_name, row_id, rule_name) DO NOTHING;
