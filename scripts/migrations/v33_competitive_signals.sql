-- Migration v33 — Competitive Signals
-- Applied: 2026-05-24
-- Purpose: Track discrete competitive events (conference abstracts, patent filings,
--          financing rounds, publications, licensing deals) per company / drug / area.
--
-- Key design decisions:
--   • signal_type ENUM covers the five most common BD-relevant event types
--   • Both company_id and drug_id are nullable — a financing round is company-level;
--     a conference abstract is usually drug-level; some signals apply to both
--   • area_id (TEXT, no FK) mirrors the pattern used in drug_area_scores and catalysts
--   • confidence NUMERIC(3,2) is 0.00–1.00; default 0.80 (curated/sourced)
--   • source_date is the event date (abstract submission, patent filing, press release)
--   • created_at is when the row was inserted (for staleness tracking)
--   • enriched_by_run_id links to enrichment_runs for audit trail (nullable)

-- ─── 1. CREATE TABLE ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS competitive_signals (
    id                BIGSERIAL PRIMARY KEY,
    company_id        TEXT REFERENCES companies(id),
    drug_id           TEXT REFERENCES drugs(id),
    area_id           TEXT,                          -- e.g. 'ted', 'tl1a', 'respiratory'
    signal_type       TEXT NOT NULL,                 -- see CHECK below
    title             TEXT NOT NULL,
    description       TEXT,
    source_url        TEXT,
    source_date       DATE,
    confidence        NUMERIC(3,2) DEFAULT 0.80,
    enriched_by_run_id BIGINT,                       -- FK to enrichment_runs.id (soft ref)
    created_at        TIMESTAMPTZ DEFAULT now()
);

-- ─── 2. CONSTRAINTS ───────────────────────────────────────────────────────────

ALTER TABLE competitive_signals
    ADD CONSTRAINT competitive_signals_type_check
    CHECK (signal_type IN ('conference','patent','financing','publication','licensing','regulatory','clinical_update'));

ALTER TABLE competitive_signals
    ADD CONSTRAINT competitive_signals_confidence_check
    CHECK (confidence BETWEEN 0 AND 1);

ALTER TABLE competitive_signals
    ADD CONSTRAINT competitive_signals_has_entity
    CHECK (company_id IS NOT NULL OR drug_id IS NOT NULL);

-- ─── 3. INDEXES ───────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS competitive_signals_company_idx   ON competitive_signals(company_id);
CREATE INDEX IF NOT EXISTS competitive_signals_drug_idx      ON competitive_signals(drug_id);
CREATE INDEX IF NOT EXISTS competitive_signals_area_idx      ON competitive_signals(area_id);
CREATE INDEX IF NOT EXISTS competitive_signals_type_idx      ON competitive_signals(signal_type);
CREATE INDEX IF NOT EXISTS competitive_signals_date_idx      ON competitive_signals(source_date DESC);

-- ─── 4. COMMENTS ──────────────────────────────────────────────────────────────

COMMENT ON TABLE competitive_signals IS
    'Discrete competitive events (conference, patent, financing, etc.) per company/drug/area. '
    'Signal_type values: conference, patent, financing, publication, licensing, regulatory, clinical_update.';

COMMENT ON COLUMN competitive_signals.signal_type IS
    'conference=abstract/poster/oral; patent=filing or grant; financing=round/IPO/ATM; '
    'publication=paper/preprint; licensing=in/out-licensing; regulatory=IND/BLA/approval; '
    'clinical_update=data readout/trial update';
COMMENT ON COLUMN competitive_signals.source_date IS 'Date of the event, not insertion date';
COMMENT ON COLUMN competitive_signals.confidence   IS '0.00–1.00; 0.90=primary source, 0.80=curated, 0.60=inferred';
