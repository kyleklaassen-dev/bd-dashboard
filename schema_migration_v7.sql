-- ═══════════════════════════════════════════════════════════════════════════════
-- schema_migration_v7.sql — Propagate canonical_drug_id to catalysts + deals
-- ═══════════════════════════════════════════════════════════════════════════════
--
-- CHANGES:
--   1. catalysts table — add canonical_drug_id FK
--      Step 4 of company_enrichment.py creates catalysts from trials.
--      Trials now carry canonical_drug_id (migration v6). This propagates
--      that identity downstream so catalysts are also canonically linked,
--      enabling correct completeness scoring and catalyst rollup per drug.
--
--   2. deals table — add canonical_drug_id FK
--      Step 6 creates deal records. Drug-specific deals (licensing, partnerships)
--      should be tied to the canonical drug identity for cross-table aggregation.
--      Nullable — company-level deals (M&A, financing) have no specific drug.
--
-- APPLIED: via Management API (no SQL editor required)
-- IDEMPOTENT: all statements use ADD COLUMN IF NOT EXISTS
-- ═══════════════════════════════════════════════════════════════════════════════


-- ─────────────────────────────────────────────────────────────────────────────
-- 1. catalysts — add canonical_drug_id
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE catalysts
    ADD COLUMN IF NOT EXISTS canonical_drug_id TEXT
        REFERENCES canonical_drugs(canonical_id);

-- Index for fast lookup: "all catalysts for this canonical drug"
CREATE INDEX IF NOT EXISTS idx_catalysts_canonical_drug_id
    ON catalysts (canonical_drug_id);


-- ─────────────────────────────────────────────────────────────────────────────
-- 2. deals — add canonical_drug_id
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE deals
    ADD COLUMN IF NOT EXISTS canonical_drug_id TEXT
        REFERENCES canonical_drugs(canonical_id);

-- Index for fast lookup: "all deals for this canonical drug"
CREATE INDEX IF NOT EXISTS idx_deals_canonical_drug_id
    ON deals (canonical_drug_id);
