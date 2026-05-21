-- =============================================================================
-- Migration v12: Indication Group Sync — drug_areas completeness
-- =============================================================================
-- Problem: The TL1A tab fetches drugs via area_id='ibd' (the indication_group),
-- but many drugs are only tagged with their specific area (tl1a, tslp, il4ra, etc.),
-- not the broader indication_group. This caused enrichment and trial sync to miss
-- approved IBD drugs (e.g. Skyrizi, Rinvoq for AbbVie) when running against tl1a.
--
-- Fix has three parts:
--   PART 1: Add indication_group rows to disease_areas (so FK constraint allows
--           drug_areas entries with indication_group as area_id)
--   PART 2: Backfill missing indication_group tags in drug_areas
--   PART 3: Trigger to auto-sync indication_group tags on future inserts
-- =============================================================================


-- PART 1 — Add indication_group rows to disease_areas
-- These are NOT user-facing tabs (sort_order 11+). They exist purely so that
-- drug_areas can have FK-valid entries for the indication_group area_id.
-- The ibd row already exists (sort_order=10). Add the others.
-- =============================================================================

INSERT INTO disease_areas (id, label, description, sort_order, indication_group)
VALUES
  ('respiratory', 'Respiratory (grouping)',
   'Respiratory disease indications: asthma, COPD, atopic lung disease. Used as the drug-display filter for the TSLP tab — shows all respiratory-mechanism drugs regardless of specific target.',
   11, 'respiratory'),
  ('atopy', 'Atopy (grouping)',
   'Atopic disease indications: atopic dermatitis, allergic asthma, chronic rhinosinusitis. Used as the drug-display filter for the IL-4Rα tab.',
   12, 'atopy'),
  ('ted', 'TED / Orbital (grouping)',
   'Thyroid eye disease and related orbital fibrosis indications. Used as the drug-display filter for the IGF1R tab.',
   13, 'ted'),
  ('autoimmune', 'Autoimmune (grouping)',
   'IgG-mediated and T-cell-driven autoimmune disease indications. Used as the drug-display filter for the FcRn and T-cell tabs.',
   14, 'autoimmune')
ON CONFLICT (id) DO NOTHING;


-- PART 2 — Backfill missing indication_group tags in drug_areas
-- Insert a (drug_id, indication_group) row for every drug that has a specific
-- area tag but is missing the corresponding indication_group tag.
-- ON CONFLICT DO NOTHING makes this idempotent.
-- =============================================================================

INSERT INTO drug_areas (drug_id, area_id)
SELECT DISTINCT da.drug_id, dis.indication_group
FROM   drug_areas da
JOIN   disease_areas dis ON dis.id = da.area_id
WHERE  dis.indication_group IS NOT NULL
  AND  dis.indication_group <> da.area_id
  AND  NOT EXISTS (
    SELECT 1 FROM drug_areas da2
    WHERE  da2.drug_id = da.drug_id
      AND  da2.area_id = dis.indication_group
  )
  AND  EXISTS (
    SELECT 1 FROM disease_areas ig_row WHERE ig_row.id = dis.indication_group
  );


-- PART 3 — Trigger: auto-sync indication_group tag on INSERT
-- When any row is inserted into drug_areas with a specific area_id that has
-- an indication_group, automatically insert the indication_group tag as well
-- (if the indication_group exists as a valid row in disease_areas).
-- This ensures future manual inserts and pipeline-created entries are always
-- complete — no manual IG tagging needed.
-- =============================================================================

CREATE OR REPLACE FUNCTION fn_sync_drug_indication_group()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
  v_ig TEXT;
BEGIN
  -- Look up the indication_group for the area being tagged
  SELECT indication_group INTO v_ig
  FROM   disease_areas
  WHERE  id = NEW.area_id;

  -- Only proceed if there IS an indication_group that differs from the area itself,
  -- and that indication_group is itself a valid disease_areas row (FK-safe).
  IF v_ig IS NOT NULL AND v_ig <> NEW.area_id THEN
    INSERT INTO drug_areas (drug_id, area_id)
    SELECT NEW.drug_id, v_ig
    WHERE  EXISTS (SELECT 1 FROM disease_areas WHERE id = v_ig)
    ON CONFLICT DO NOTHING;
  END IF;

  RETURN NEW;
END;
$$;

-- Drop existing trigger if re-running this migration
DROP TRIGGER IF EXISTS trg_drug_areas_sync_ig ON drug_areas;

CREATE TRIGGER trg_drug_areas_sync_ig
AFTER INSERT ON drug_areas
FOR EACH ROW
EXECUTE FUNCTION fn_sync_drug_indication_group();


-- PART 3b — Mirror trigger for company_areas (same pattern)
-- When a company is tagged with a specific area (e.g. tl1a), also tag it
-- with the indication_group (e.g. ibd). Keeps company eligibility aligned.
-- =============================================================================

CREATE OR REPLACE FUNCTION fn_sync_company_indication_group()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
  v_ig TEXT;
BEGIN
  SELECT indication_group INTO v_ig
  FROM   disease_areas
  WHERE  id = NEW.area_id;

  IF v_ig IS NOT NULL AND v_ig <> NEW.area_id THEN
    INSERT INTO company_areas (company_id, area_id)
    SELECT NEW.company_id, v_ig
    WHERE  EXISTS (SELECT 1 FROM disease_areas WHERE id = v_ig)
    ON CONFLICT DO NOTHING;
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_company_areas_sync_ig ON company_areas;

CREATE TRIGGER trg_company_areas_sync_ig
AFTER INSERT ON company_areas
FOR EACH ROW
EXECUTE FUNCTION fn_sync_company_indication_group();


-- VERIFICATION QUERY
-- After applying, run this to confirm 0 gaps remain:
-- =============================================================================
/*
SELECT da.drug_id, da.area_id AS specific_area, dis.indication_group
FROM   drug_areas da
JOIN   disease_areas dis ON dis.id = da.area_id
WHERE  dis.indication_group <> da.area_id
  AND  NOT EXISTS (
    SELECT 1 FROM drug_areas da2
    WHERE  da2.drug_id = da.drug_id AND da2.area_id = dis.indication_group
  );
-- Should return 0 rows.
*/
