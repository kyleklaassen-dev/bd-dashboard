-- Migration v10: Add relationship classification fields to discovery_queue
-- Run this once in the Supabase SQL Editor: https://supabase.com/dashboard/project/tghntyofptvfhmtchwcv/sql/new
-- ─────────────────────────────────────────────────────────────────────────────
-- 1. discovery_queue: relationship_type, relationship_confidence, why_discovered
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE discovery_queue
  ADD COLUMN IF NOT EXISTS relationship_type TEXT
    CHECK (relationship_type IN (
      'peer_competitor',
      'licensor',
      'licensee',
      'partner',
      'parent_subsidiary',
      'asset_owner',
      'co_developer',
      'direct_competitor',
      'adjacent_competitor',
      'unknown'
    )),
  ADD COLUMN IF NOT EXISTS relationship_confidence TEXT
    CHECK (relationship_confidence IN ('confirmed', 'inferred', 'suggested')),
  ADD COLUMN IF NOT EXISTS why_discovered TEXT;

-- 2. intel: add 'financing' and 'pipeline' to the intel_type check constraint
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE intel DROP CONSTRAINT IF EXISTS intel_intel_type_check;
ALTER TABLE intel ADD CONSTRAINT intel_intel_type_check
  CHECK (intel_type IN (
    'data',
    'deal',
    'regulatory',
    'financing',
    'conference',
    'partnership',
    'management',
    'pipeline'
  ));

-- Verify
SELECT
  column_name,
  data_type,
  character_maximum_length
FROM information_schema.columns
WHERE table_name = 'discovery_queue'
  AND column_name IN ('relationship_type','relationship_confidence','why_discovered')
ORDER BY column_name;
