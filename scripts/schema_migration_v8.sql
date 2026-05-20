-- ============================================================
-- BD Platform Schema Migration v8
-- Adds indication_group to disease_areas and seeds 'ibd' area
--
-- Design principle:
--   Each drug area (tl1a, tslp, etc.) maps to a broader
--   indication_group (ibd, respiratory, atopy, etc.).
--   Company table rows are controlled by company_areas.area_id = specific area.
--   Drug display in expanded rows is controlled by drug_areas.area_id = indication_group.
--   This way expanding a TL1A company shows all their IBD drugs, not just TL1A drugs.
-- ============================================================

-- 1. Add indication_group column to disease_areas
ALTER TABLE disease_areas
  ADD COLUMN IF NOT EXISTS indication_group TEXT;

-- 2. Populate indication_group for existing areas
UPDATE disease_areas SET indication_group = 'ibd'          WHERE id = 'tl1a';
UPDATE disease_areas SET indication_group = 'respiratory'   WHERE id = 'tslp';
UPDATE disease_areas SET indication_group = 'atopy'         WHERE id = 'il4ra';
UPDATE disease_areas SET indication_group = 'ted'           WHERE id = 'igf1r';
UPDATE disease_areas SET indication_group = 'autoimmune'    WHERE id = 'fcrn';
UPDATE disease_areas SET indication_group = 'autoimmune'    WHERE id = 'tcell';

-- 3. Add 'ibd' as a formal disease_area entry
INSERT INTO disease_areas (id, label, description, sort_order, indication_group)
VALUES (
  'ibd',
  'IBD · Inflammatory Bowel Disease',
  'Inflammatory bowel disease indications: ulcerative colitis (UC), Crohn''s disease (CD). Used as the drug-display filter for the TL1A tab — shows all IBD-mechanism drugs regardless of specific target.',
  10,
  'ibd'
)
ON CONFLICT (id) DO UPDATE
  SET label = EXCLUDED.label,
      description = EXCLUDED.description,
      indication_group = EXCLUDED.indication_group;

-- Index for fast indication_group lookups
CREATE INDEX IF NOT EXISTS disease_areas_indication_group_idx ON disease_areas (indication_group);

COMMENT ON COLUMN disease_areas.indication_group IS
  'Broader indication bucket this area belongs to (ibd, respiratory, atopy, ted, autoimmune). Drug display in PI table expanded rows uses indication_group, not the specific area_id.';
