-- Migration v27 — targets table + drug_targets junction
-- Applied: 2026-05-24 (Phase 2 of relationship-completeness sprint)
-- Purpose: Normalize drugs.target free-text field into queryable target nodes.
--          Enables target-level aggregation, competitive clustering, and the
--          "which mechanism class is most crowded?" query without LLM extraction.
--
-- Design principles:
--   • targets.id is the canonical slug (e.g. 'tl1a', 'il23p19', 'bcma_cd3')
--   • drug_targets is a junction table — one drug can have multiple target rows
--     (bispecifics → two rows, monospecifics → one row)
--   • drugs.target free-text field is preserved for display; drug_targets is the
--     queryable graph layer on top of it
--   • target_class captures the mechanism tier (cytokine, receptor, enzyme, etc.)
--   • pathway captures the signaling pathway (IL-4/13 atopy, IL-23/IL-12 axis, etc.)
--
-- After this migration, running scripts/seed_targets.py will:
--   1. Populate the targets table with canonical entries
--   2. Populate drug_targets from drugs.target text parsing
--   3. Add validation test: area-linked drug must have ≥1 target node

-- ── targets ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS targets (
    id              TEXT PRIMARY KEY,        -- canonical slug: 'tl1a', 'il23p19', etc.
    name            TEXT NOT NULL,           -- display name: 'TL1A/TNFSF15'
    alt_names       TEXT[],                  -- synonyms / alternate notations
    target_class    TEXT CHECK (target_class IN (
                        'cytokine',          -- IL-4, TL1A, TSLP
                        'cytokine_receptor', -- IL-4Rα, FcRn, TSLPR
                        'enzyme',            -- JAK1, PDE4
                        'surface_antigen',   -- BCMA, CD19, CD20
                        'growth_factor',     -- IGF-1R, VEGF
                        'checkpoint',        -- PD-1, CTLA-4
                        'bispecific_pair',   -- composite targets (e.g. TL1A×IL-23p19)
                        'other'
                    )),
    pathway         TEXT,                    -- e.g. 'il4_il13_atopy', 'tl1a_ibd', 'fcrn_igg'
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── drug_targets ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS drug_targets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    drug_id         TEXT NOT NULL,
    target_id       TEXT NOT NULL REFERENCES targets(id) ON DELETE RESTRICT,

    -- Role: for bispecifics, each component target gets a row
    -- 'primary'   → monospecific drug has one primary target
    -- 'component' → one arm of a bispecific
    role            TEXT NOT NULL DEFAULT 'primary'
                    CHECK (role IN ('primary', 'component')),

    -- Provenance
    confidence_level TEXT NOT NULL DEFAULT 'confirmed'
                     CHECK (confidence_level IN ('confirmed', 'supported', 'inferred')),
    source_url      TEXT,
    derived_from    TEXT DEFAULT 'drugs.target'  -- where this came from ('drugs.target', 'manual', 'llm')

    , created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
    , created_by    TEXT NOT NULL DEFAULT 'system'

    , CONSTRAINT uq_drug_target UNIQUE (drug_id, target_id)
);

CREATE INDEX IF NOT EXISTS idx_drug_targets_drug   ON drug_targets(drug_id);
CREATE INDEX IF NOT EXISTS idx_drug_targets_target ON drug_targets(target_id);

-- ── entity_edges TARGETS predicate view ───────────────────────────────────────
-- Note: TARGETS edges will also be written to entity_edges (see seed_targets.py)
-- so that the universal graph can answer "what does drug X target?" via the
-- standard entity_edges query pattern.
--
-- Columns already exist in entity_edges:
--   subject_type='drug', subject_id=drug_id, predicate='TARGETS',
--   object_type='target', object_id=target_id
--
-- This completes the triangle:
--   drug → COMPETES_WITH → drug  (Phase 1)
--   drug → TARGETS → target      (Phase 2)
--   target → [reverse] → drug    (via entity_edges queries)
