-- ═══════════════════════════════════════════════════════════════════════════════
-- schema_migration_v5.sql — Canonical Drug Identity Layer
-- ═══════════════════════════════════════════════════════════════════════════════
--
-- PURPOSE: Resolves the duplicate identity problem where the same real-world drug
--   (e.g., tulisokibart / CLD-423 / anti-TL1A mAb) exists as separate records,
--   fragmenting trials, catalysts, scoring, and deals.
--
-- NEW TABLES:
--   canonical_drugs      — one row per real-world drug program
--   drug_aliases         — all known names / codes that map to a canonical drug
--   identity_audit_log   — immutable audit trail for all identity operations
--
-- ALTERED TABLES:
--   drugs                — adds canonical_drug_id FK + resolution metadata
--
-- SAFETY: All statements are IF NOT EXISTS / IF NOT EXISTS safe.
--   Re-running this migration is idempotent.
--
-- APPLIED: (date TBD — see update_log.md)
-- ═══════════════════════════════════════════════════════════════════════════════


-- ─────────────────────────────────────────────────────────────────────────────
-- TABLE: canonical_drugs
-- One row per real-world drug / biologic program.
-- canonical_id format: CANON_DRUG_{8-char hex hash of normalized canonical_name}
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS canonical_drugs (
    canonical_id        TEXT        PRIMARY KEY,            -- CANON_DRUG_{hash}
    canonical_name      TEXT        NOT NULL,               -- preferred INN or programme name
    drug_class          TEXT,                               -- 'mab','small_molecule','bispecific','car_t','rna','gene_therapy','fusion_protein','other'
    mechanism           TEXT,                               -- free-text mechanism of action
    target              TEXT,                               -- primary molecular target (e.g. 'TL1A')
    is_active           BOOLEAN     NOT NULL DEFAULT TRUE,  -- FALSE if merged/retired
    merged_into         TEXT        REFERENCES canonical_drugs(canonical_id),  -- set when this record is superseded
    merge_reason        TEXT,                               -- human-readable reason for merge
    canonical_entity_id TEXT,                               -- FK to entities table (future; nullable now)
    confidence_score    INT         NOT NULL DEFAULT 100,   -- 0-100; lower = less certain
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- TABLE: drug_aliases
-- Every known name variant that resolves to a canonical drug.
-- UNIQUE(canonical_id, alias_name) prevents duplicate alias rows.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS drug_aliases (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_id    TEXT        NOT NULL REFERENCES canonical_drugs(canonical_id) ON DELETE CASCADE,
    alias_name      TEXT        NOT NULL,               -- exact string as seen in source data
    alias_type      TEXT,                               -- 'primary_name','code_name','inn','prior_name',
                                                        -- 'partnership_name','regional_brand','typo'
    source          TEXT,                               -- 'ct_gov','company_enrichment','manual','one_time_migration'
    confidence_score INT        NOT NULL DEFAULT 100,   -- how certain is this alias mapping (0-100)
    is_primary      BOOLEAN     NOT NULL DEFAULT FALSE, -- TRUE for the canonical preferred name alias
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(canonical_id, alias_name)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- TABLE: identity_audit_log
-- Immutable append-only log of all identity resolution operations.
-- Never DELETE from this table.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS identity_audit_log (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    operation       TEXT        NOT NULL,   -- 'create_canonical','add_alias','resolve_drug',
                                            -- 'flag_review','merge_canonical','backfill'
    canonical_id    TEXT,                   -- canonical drug involved (nullable for review flags)
    related_id      TEXT,                   -- e.g. drug.id being resolved; or second canonical in merge
    old_value       JSONB,                  -- state before operation
    new_value       JSONB,                  -- state after operation
    reason          TEXT,                   -- plain-English explanation
    performed_by    TEXT        NOT NULL DEFAULT 'system',  -- 'system','one_time_migration','manual'
    performed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- ALTER drugs — add identity resolution columns
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE drugs ADD COLUMN IF NOT EXISTS canonical_drug_id   TEXT  REFERENCES canonical_drugs(canonical_id);
ALTER TABLE drugs ADD COLUMN IF NOT EXISTS identity_confidence INT;    -- 0-100; confidence of the resolution
ALTER TABLE drugs ADD COLUMN IF NOT EXISTS identity_method     TEXT;   -- 'exact','normalized','fuzzy','manual','unresolved'

-- ─────────────────────────────────────────────────────────────────────────────
-- INDEXES
-- ─────────────────────────────────────────────────────────────────────────────

-- Fast lookup of aliases by name (used on every resolve() call)
CREATE INDEX IF NOT EXISTS idx_drug_aliases_alias_name
    ON drug_aliases (alias_name);

-- Fast lookup of all aliases for a canonical drug
CREATE INDEX IF NOT EXISTS idx_drug_aliases_canonical_id
    ON drug_aliases (canonical_id);

-- Filter active canonical drugs
CREATE INDEX IF NOT EXISTS idx_canonical_drugs_is_active
    ON canonical_drugs (is_active);

-- Filter canonical drugs by target (used in per-area scoring rollup)
CREATE INDEX IF NOT EXISTS idx_canonical_drugs_target
    ON canonical_drugs (target);

-- Join drugs to canonical drugs
CREATE INDEX IF NOT EXISTS idx_drugs_canonical_drug_id
    ON drugs (canonical_drug_id);

-- Audit log queries by canonical or related drug
CREATE INDEX IF NOT EXISTS idx_identity_audit_log_canonical_id
    ON identity_audit_log (canonical_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- TRIGGER: keep canonical_drugs.updated_at fresh
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_canonical_drugs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_canonical_drugs_updated_at ON canonical_drugs;
CREATE TRIGGER trg_canonical_drugs_updated_at
    BEFORE UPDATE ON canonical_drugs
    FOR EACH ROW EXECUTE FUNCTION update_canonical_drugs_updated_at();
