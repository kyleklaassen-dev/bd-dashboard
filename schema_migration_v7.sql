-- schema_migration_v7.sql
-- Fix: ensure research_queue.assigned_status has DEFAULT 'pending'
-- so the pipeline can upsert rows without including assigned_status in the payload
-- (prevents nightly pipeline from resetting user-set 'in_progress'/'done' statuses).
--
-- Run this once in the Supabase SQL editor.

ALTER TABLE research_queue
  ALTER COLUMN assigned_status SET DEFAULT 'pending';

-- Verify
SELECT column_name, column_default, is_nullable
FROM information_schema.columns
WHERE table_name = 'research_queue'
  AND column_name = 'assigned_status';
