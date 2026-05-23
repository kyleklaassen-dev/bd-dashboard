-- Migration v14: Catalyst deduplication unique index
-- Run in Supabase SQL editor after completing the dedup cleanup.
-- Prevents future accumulation of duplicate catalyst rows.
--
-- Prerequisites: Run the dedup cleanup first (docs/catalyst_quality_diagnosis.md Step 1)
-- Before running: verify no duplicates remain:
--   SELECT COUNT(*) FROM catalysts
--   WHERE id NOT IN (SELECT MAX(id) FROM catalysts GROUP BY company_id, area_id, label);
-- Expected: 0 rows
--
-- 2026-05-22: 137 exact duplicate rows removed (710 → 573 total)
-- Root cause: enrichment pipeline inserted without label-based dedup check.
-- Fix: dedup check in company_enrichment.py now includes label as primary key.
-- This index enforces it at the database level.

CREATE UNIQUE INDEX IF NOT EXISTS catalysts_company_area_label_unique
ON catalysts (company_id, area_id, label);

-- Verify:
-- SELECT indexname FROM pg_indexes WHERE tablename = 'catalysts' AND indexname = 'catalysts_company_area_label_unique';
