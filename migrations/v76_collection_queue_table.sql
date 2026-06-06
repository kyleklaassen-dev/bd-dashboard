-- v76: Stateful collection queue (makes the v75 gaps view actionable)
-- The view is always-fresh truth; this table carries LIFECYCLE so the research
-- pipeline can work a gap, mark progress, and not have resolved gaps re-surface.
-- Populated by scripts/sync_collection_queue.py from source_collection_gaps.

CREATE TABLE IF NOT EXISTS source_collection_queue (
  id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  entity_type     text NOT NULL,
  entity_id       text NOT NULL,
  section         text NOT NULL,
  claim_index     int,
  claim_text      text,
  gap_type        text,
  priority        int,
  status          text NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open', 'in_progress', 'resolved', 'dismissed')),
  attempts        int  NOT NULL DEFAULT 0,
  resolution_note text,
  first_seen      timestamptz DEFAULT now(),
  last_seen       timestamptz DEFAULT now(),
  resolved_at     timestamptz,
  UNIQUE (entity_type, entity_id, section, claim_index)
);
CREATE INDEX IF NOT EXISTS idx_collection_queue_status
  ON source_collection_queue (status, priority DESC);
CREATE INDEX IF NOT EXISTS idx_collection_queue_entity
  ON source_collection_queue (entity_type, entity_id);

ALTER TABLE source_collection_queue ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS anon_read_collection_queue ON source_collection_queue;
CREATE POLICY anon_read_collection_queue ON source_collection_queue FOR SELECT USING (true);
