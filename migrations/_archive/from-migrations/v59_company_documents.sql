-- Migration v59: company_documents table
-- Conference abstract and document intelligence layer for Meridian BD Platform
-- Applied: 2026-05-28

CREATE TABLE IF NOT EXISTS company_documents (
    id BIGSERIAL PRIMARY KEY,
    company_id TEXT REFERENCES companies(id) ON DELETE SET NULL,
    drug_id TEXT REFERENCES drugs(id) ON DELETE SET NULL,
    document_type TEXT NOT NULL CHECK (document_type IN ('8-K','abstract','poster','slide_deck','press_release','IND','clinical_data','patent','analyst_report','other')),
    title TEXT NOT NULL,
    authors TEXT,
    conference TEXT,
    conference_date DATE,
    journal TEXT,
    publication_date DATE,
    source_url TEXT,
    pubmed_id TEXT,
    doi TEXT,
    abstract_text TEXT,
    key_findings TEXT,
    drug_names TEXT[],
    target TEXT,
    indication TEXT,
    phase TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    enrichment_run_id UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_cdoc_company ON company_documents(company_id);
CREATE INDEX IF NOT EXISTS idx_cdoc_drug ON company_documents(drug_id);
CREATE INDEX IF NOT EXISTS idx_cdoc_type ON company_documents(document_type);
