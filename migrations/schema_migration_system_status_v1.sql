-- ============================================================================
-- schema_migration_system_status_v1.sql
-- Singleton "heartbeat" table that nightly pipelines stamp on completion.
-- The dashboard polls this row to know when fresh intelligence has arrived
-- (S3 — last-updated banner). One row only, id = 1, enforced by CHECK.
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.system_status (
    id                    integer PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    last_enrichment_at    timestamptz,        -- company_enrichment.py completion
    last_research_at      timestamptz,        -- research.py completion
    last_pipeline_label   text,               -- which pipeline last stamped (e.g. 'enrichment')
    updated_record_count  integer DEFAULT 0,  -- rows touched by the last run
    note                  text,               -- optional human-readable summary
    updated_at            timestamptz NOT NULL DEFAULT now()
);

-- Seed the singleton row if it doesn't exist yet.
INSERT INTO public.system_status (id, note, updated_at)
VALUES (1, 'system_status initialized', now())
ON CONFLICT (id) DO NOTHING;

-- Read-only access for the dashboard's anon role (poll-only; writes use service key).
ALTER TABLE public.system_status ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS system_status_anon_read ON public.system_status;
CREATE POLICY system_status_anon_read
    ON public.system_status
    FOR SELECT
    TO anon, authenticated
    USING (true);
