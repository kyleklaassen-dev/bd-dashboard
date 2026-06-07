-- Migration v19: intel.primary_company_id column
-- Adds a direct FK from intel to companies, eliminating the need for
-- a junction table JOIN on every company-scoped intel query.
-- Applied via Management API on 2026-05-22.

ALTER TABLE intel
  ADD COLUMN IF NOT EXISTS primary_company_id TEXT REFERENCES companies(id);

CREATE INDEX IF NOT EXISTS idx_intel_primary_company
  ON intel (primary_company_id);

-- Backfill from intel_companies junction (pick arbitrary first company per row)
UPDATE intel
SET primary_company_id = (
  SELECT company_id FROM intel_companies
  WHERE intel_id = intel.id
  ORDER BY company_id
  LIMIT 1
)
WHERE primary_company_id IS NULL;

-- After running: 341 of 345 rows populated (4 had no company link = acceptable)

-- research.py and company_enrichment.py updated to set primary_company_id
-- on all new intel writes (P1-B in hardening plan).
