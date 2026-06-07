-- drug_competitive_scores DDL
-- Session 60 — 2026-05-26
-- Replaces: drug_area_scores (212 rows, legacy area_id dependency)
-- Apply via: Supabase SQL Editor → New Query

-- ── Main table ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS drug_competitive_scores (
  id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  drug_id           TEXT    NOT NULL REFERENCES drugs(id),

  -- Context: what competitive lens does this score address?
  -- context_type values:
  --   'target'         — competitive score within a biological target space (e.g. TL1A)
  --   'indication'     — competitive score within a disease indication (e.g. UC)
  --   'strategic_view' — curated strategic area view (e.g. autoimmune portfolio)
  --   'platform_view'  — platform modality view (e.g. T-cell engineering)
  context_type      TEXT    NOT NULL CHECK (context_type IN ('target','indication','strategic_view','platform_view')),

  -- context_id values by type:
  --   target         → drug_targets.target_id          (e.g. 'tl1a', 'il4ra', 'fcrn')
  --   indication     → drug_indications.indication_id  (e.g. 'uc', 'cd', 'ted', 'ra')
  --   strategic_view → 'autoimmune' | 'respiratory'
  --   platform_view  → 'tcell'
  context_id        TEXT    NOT NULL,

  -- Competitive intelligence (migrated from drug_area_scores)
  overlap           TEXT    CHECK (overlap IN ('Direct','Adjacent','Same-Space','Watch')),
  overlap_rationale TEXT,           -- Claude reasoning text
  cls               TEXT,           -- free-form classification tag
  confidence_level  TEXT    CHECK (confidence_level IN ('A','B','C','inferred')),
  source_url        TEXT,           -- primary evidence URL
  vs_ailux          TEXT,           -- positioning note relative to Ailux

  -- Provenance
  enriched_by       TEXT    DEFAULT 'migration',  -- 'claude' | 'migration' | 'manual'
  enriched_at       TIMESTAMPTZ,
  migrated_from     TEXT,           -- e.g. 'drug_area_scores.area_id=tl1a' (audit trail)
  notes             TEXT,           -- free-form migration notes

  -- Timestamps
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- One score per drug per context
  UNIQUE (drug_id, context_type, context_id)
);

-- ── Indexes ──────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_dcs_drug_id
  ON drug_competitive_scores (drug_id);

CREATE INDEX IF NOT EXISTS idx_dcs_context
  ON drug_competitive_scores (context_type, context_id);

CREATE INDEX IF NOT EXISTS idx_dcs_overlap
  ON drug_competitive_scores (overlap);

CREATE INDEX IF NOT EXISTS idx_dcs_drug_context
  ON drug_competitive_scores (drug_id, context_type);

-- ── updated_at trigger ───────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_dcs_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_dcs_updated_at
  BEFORE UPDATE ON drug_competitive_scores
  FOR EACH ROW EXECUTE FUNCTION update_dcs_updated_at();

-- ── Row-level security (match drug_area_scores pattern) ──────────────────────
ALTER TABLE drug_competitive_scores ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_read_drug_competitive_scores"
  ON drug_competitive_scores
  FOR SELECT
  USING (true);

CREATE POLICY "service_write_drug_competitive_scores"
  ON drug_competitive_scores
  FOR ALL
  USING (auth.role() = 'service_role');

-- ── Comments ─────────────────────────────────────────────────────────────────
COMMENT ON TABLE drug_competitive_scores IS
  'Competitive intelligence scores for drugs, indexed by biological context (target, indication, strategic view, or platform view). Replaces drug_area_scores, which used legacy area_id. Migrated 2026-05-26.';

COMMENT ON COLUMN drug_competitive_scores.context_type IS
  'target | indication | strategic_view | platform_view';

COMMENT ON COLUMN drug_competitive_scores.context_id IS
  'FK to drug_targets.target_id, drug_indications.indication_id, or strategic view ID';

COMMENT ON COLUMN drug_competitive_scores.migrated_from IS
  'Audit trail: original drug_area_scores.area_id value used to derive this row';
