-- Migration v20: drug_area_scores table
-- Phase 1 (parallel write — no removal of drugs.overlap/cls yet)
--
-- Problem: drugs.overlap/cls/overlap_rationale/vs_ailux are area-relative fields
-- stored directly on the drug row with no area_id. A drug in two areas gets its
-- classification overwritten on each enrichment run by whichever area runs last.
--
-- Fix: New drug_area_scores table stores area-specific competitive interpretation.
-- company_enrichment.py writes to BOTH tables so dashboard continues working.
-- Phase 2 (during Molecule Database migration): drop legacy columns from drugs.
--
-- Applied via Management API on 2026-05-22.

CREATE TABLE IF NOT EXISTS drug_area_scores (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  drug_id               text NOT NULL REFERENCES drugs(id),
  canonical_drug_id     text REFERENCES canonical_drugs(canonical_id),
  area_id               text NOT NULL,
  overlap               text,         -- Direct | Adjacent | Same-Space | Watch
  cls                   text,         -- mechanism class label (area-relative)
  overlap_rationale     text,         -- why this tier relative to Ailux in this area
  vs_ailux_positioning  text,         -- how this drug compares to Ailux in this area
  area_fit              text,         -- primary | secondary | off_target | exclude
  area_fit_rationale    text,
  last_enriched_at      timestamptz DEFAULT now(),
  created_at            timestamptz DEFAULT now(),
  UNIQUE(drug_id, area_id)
);

-- Fast lookups by area and by canonical drug
CREATE INDEX IF NOT EXISTS idx_drug_area_scores_area
  ON drug_area_scores (area_id, overlap);

CREATE INDEX IF NOT EXISTS idx_drug_area_scores_canonical
  ON drug_area_scores (canonical_drug_id);

-- RLS: anon can SELECT; only service_role can write
ALTER TABLE drug_area_scores ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_select_drug_area_scores"
  ON drug_area_scores FOR SELECT
  TO anon USING (true);

-- Backfill: For each drug with area context, attempt to derive area_id from
-- company_areas. Use the earliest (first) area for multi-area companies.
-- This is approximate — next enrichment run will correct with authoritative values.
INSERT INTO drug_area_scores (drug_id, canonical_drug_id, area_id, overlap, cls, overlap_rationale, vs_ailux_positioning, last_enriched_at)
SELECT DISTINCT ON (d.id)
  d.id                   AS drug_id,
  d.canonical_drug_id    AS canonical_drug_id,
  ca.area_id             AS area_id,
  d.overlap              AS overlap,
  d.cls                  AS cls,
  d.overlap_rationale    AS overlap_rationale,
  d.vs_ailux             AS vs_ailux_positioning,
  now()                          AS last_enriched_at
FROM drugs d
JOIN company_areas ca ON ca.company_id = d.company_id
WHERE d.overlap IS NOT NULL
   OR d.cls IS NOT NULL
   OR d.vs_ailux IS NOT NULL
ORDER BY d.id, ca.area_id  -- DISTINCT ON uses first area_id alphabetically for multi-area companies
ON CONFLICT (drug_id, area_id) DO NOTHING;

-- Report backfill results
-- SELECT area_id, overlap, COUNT(*) FROM drug_area_scores GROUP BY area_id, overlap ORDER BY area_id, overlap;
