-- Migration v25 — ownership_edges table
-- Applied: 2026-05-24 (via Supabase Management API, overnight execution Phase 1)
-- Purpose: Explicit ownership and control relationships for drugs and companies.
--          Separates ORIGINATED_BY (immutable), CONTROLLED_BY (changes on M&A),
--          and LICENSED_IN/FROM (scoped rights) into queryable edge rows.
--
-- See: docs/ownership_edges_design.md for full design rationale.
-- See: docs/meridian_graph_schema_proposal.md for broader entity graph context.

CREATE TABLE IF NOT EXISTS ownership_edges (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Subject (the thing being owned/controlled)
    subject_type        TEXT NOT NULL CHECK (subject_type IN ('drug', 'company')),
    subject_id          TEXT NOT NULL,

    -- Predicate
    predicate           TEXT NOT NULL CHECK (predicate IN (
                            'ORIGINATED_BY', 'CONTROLLED_BY',
                            'LICENSED_IN', 'LICENSED_FROM',
                            'ACQUIRED', 'SPUN_OUT_FROM'
                        )),

    -- Object (the controlling/originating entity)
    object_type         TEXT NOT NULL DEFAULT 'company' CHECK (object_type IN ('company')),
    object_id           TEXT NOT NULL,

    -- Scope (optional — a license may be indication- or geo-specific)
    scope_indication    TEXT,
    scope_geography     TEXT,

    -- Provenance
    confidence_level    TEXT NOT NULL DEFAULT 'inferred'
                        CHECK (confidence_level IN ('confirmed', 'supported', 'inferred')),
    source_url          TEXT,
    source_type         TEXT CHECK (source_type IN (
                            'press_release', 'sec_filing', 'clinical_trial',
                            'pipeline_page', 'annual_report', 'inferred', 'manual'
                        )),

    -- Temporal
    effective_date      DATE,
    end_date            DATE,
    status              TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'historical', 'pending')),

    -- Audit
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by          TEXT NOT NULL DEFAULT 'manual',
    notes               TEXT
);

CREATE INDEX IF NOT EXISTS idx_ownership_subject   ON ownership_edges(subject_type, subject_id);
CREATE INDEX IF NOT EXISTS idx_ownership_object    ON ownership_edges(object_type, object_id);
CREATE INDEX IF NOT EXISTS idx_ownership_predicate ON ownership_edges(predicate);
CREATE INDEX IF NOT EXISTS idx_ownership_status    ON ownership_edges(status);

-- Backfill rows inserted at creation time:
--   P0: UCB acquires Candid (2026-05-03) — cizutamig, CND319, CND460 CONTROLLED_BY→UCB; ORIGINATED_BY→Candid
--   P0: UCB licenses ATG-201 from Antengene (2026-03-01) — LICENSED_IN→UCB; ORIGINATED_BY→Antengene
--   P1: Merck acquires Prometheus (2023-06-01) — tulisokibart CONTROLLED_BY→Merck; ORIGINATED_BY→Prometheus
-- See: docs/ownership_edges_design.md § Part 6 for full backfill priority list.

-- Effective_company_areas view — derives acquirer area membership from ownership_edges.
-- Switches dashboard queries from company_areas to this view for correct post-M&A display.
CREATE OR REPLACE VIEW effective_company_areas AS
  -- Direct membership
  SELECT company_id, area_id, 'direct' AS source
  FROM company_areas
  UNION
  -- Inherited via acquisition: if A acquired B and B is active in area X, A inherits X
  SELECT oe.object_id AS company_id, ca.area_id, 'via_acquisition' AS source
  FROM ownership_edges oe
  JOIN company_areas ca ON ca.company_id = oe.subject_id
  WHERE oe.predicate = 'ACQUIRED'
    AND oe.status = 'active';
