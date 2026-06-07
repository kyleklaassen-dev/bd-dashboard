-- Migration v18: Catalyst deduplication + unique index
-- Run in Supabase SQL editor (or already applied via Management API on 2026-05-22)
--
-- Problem: company_enrichment.py called sb_upsert("catalysts", ...) without a
-- UNIQUE constraint, causing PostgREST to INSERT every time instead of merging.
-- Result: 474 duplicate rows across 6-area enrichment runs.
--
-- Fix:
--   1. Dedup existing rows — keep lowest id per (company, drug, type, date)
--   2. Add unique expression index using COALESCE to treat NULL drug_id as ''

-- Step 1: Remove duplicates (keep oldest id per logical key)
DELETE FROM catalysts WHERE id NOT IN (
  SELECT MIN(id)
  FROM catalysts
  GROUP BY company_id, COALESCE(drug_id, ''), catalyst_type, sort_date::date
);

-- Step 2: Add unique index — COALESCE(drug_id, '') normalises NULLs so
-- only one company-level catalyst per (type, date) is allowed.
CREATE UNIQUE INDEX IF NOT EXISTS idx_catalysts_dedup
ON catalysts (company_id, COALESCE(drug_id, ''), catalyst_type, sort_date);

-- Note: PostgREST cannot use expression indexes as on_conflict targets.
-- company_enrichment.py instead does a dedup pre-check (sb_get) before
-- inserting step5/6 catalysts (mirrors the step4 pattern).

-- Verify:
-- SELECT company_id, drug_id, catalyst_type, sort_date, COUNT(*) FROM catalysts
-- GROUP BY company_id, drug_id, catalyst_type, sort_date HAVING COUNT(*) > 1;
-- → should return 0 rows
