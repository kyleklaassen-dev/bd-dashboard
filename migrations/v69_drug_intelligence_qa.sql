-- ============================================================
-- v69_drug_intelligence_qa.sql
-- Meridian 100-Question Drug Intelligence Brain
-- Applied: 2026-05-31
--
-- Creates 3 tables:
--   drug_intelligence_qa         — all 100 Q&A pairs per drug
--   drug_clinical_benchmarks     — extracted efficacy benchmarks
--   drug_development_timelines   — extracted milestone dates
-- ============================================================

-- ── Table 1: drug_intelligence_qa ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.drug_intelligence_qa (
  id SERIAL PRIMARY KEY,
  drug_id TEXT REFERENCES public.drugs(id) ON DELETE CASCADE,
  question_id INTEGER NOT NULL CHECK (question_id BETWEEN 1 AND 100),
  domain TEXT NOT NULL CHECK (domain IN ('molecule','clinical','patient','payer','competitive','regulatory','ip','strategic')),
  question_text TEXT NOT NULL,
  answer_text TEXT,
  answer_short TEXT,
  confidence_score NUMERIC(3,2) CHECK (confidence_score BETWEEN 0 AND 1),
  evidence_level TEXT CHECK (evidence_level IN ('high','medium','low','estimated','unknown')),
  source_urls TEXT[],
  source_labels TEXT[],
  last_researched TIMESTAMPTZ DEFAULT NOW(),
  researcher_model TEXT DEFAULT 'claude-sonnet-4-6',
  needs_update BOOLEAN DEFAULT FALSE,
  UNIQUE(drug_id, question_id)
);
GRANT SELECT ON public.drug_intelligence_qa TO anon;
CREATE POLICY "anon_read" ON public.drug_intelligence_qa FOR SELECT TO anon USING (true);
ALTER TABLE public.drug_intelligence_qa ENABLE ROW LEVEL SECURITY;

-- ── Table 2: drug_clinical_benchmarks ────────────────────────────────────────
-- benchmark_type values: primary_remission | endoscopic_remission | clinical_response |
--   deep_remission | mucosal_healing | clinical_remission | steroid_free_remission |
--   histologic_remission
CREATE TABLE IF NOT EXISTS public.drug_clinical_benchmarks (
  id SERIAL PRIMARY KEY,
  drug_id TEXT REFERENCES public.drugs(id) ON DELETE CASCADE,
  indication_id TEXT,
  benchmark_type TEXT NOT NULL,
  rate_pct NUMERIC(5,1),
  comparator_rate_pct NUMERIC(5,1),
  dose_label TEXT,
  timepoint_weeks INTEGER,
  n_enrolled INTEGER,
  trial_name TEXT,
  nct_id TEXT,
  patient_enrichment TEXT,
  data_cutoff_date DATE,
  is_phase3 BOOLEAN DEFAULT FALSE,
  is_approved_label BOOLEAN DEFAULT FALSE,
  source_url TEXT,
  last_updated TIMESTAMPTZ DEFAULT NOW()
);
GRANT SELECT ON public.drug_clinical_benchmarks TO anon;
CREATE POLICY "anon_read" ON public.drug_clinical_benchmarks FOR SELECT TO anon USING (true);
ALTER TABLE public.drug_clinical_benchmarks ENABLE ROW LEVEL SECURITY;

-- ── Table 3: drug_development_timelines ──────────────────────────────────────
-- milestone values: discovery | preclinical_start | ind_filing | fih |
--   phase1_complete | phase2_start | phase2_primary | phase3_start |
--   phase3_primary | nda_filing | approval
CREATE TABLE IF NOT EXISTS public.drug_development_timelines (
  id SERIAL PRIMARY KEY,
  drug_id TEXT REFERENCES public.drugs(id) ON DELETE CASCADE,
  milestone TEXT NOT NULL,
  milestone_label TEXT,
  actual_date DATE,
  estimated_date DATE,
  estimated_year INTEGER,
  estimated_quarter TEXT,
  date_basis TEXT,
  confidence TEXT CHECK (confidence IN ('confirmed','high','medium','low','speculative')),
  source_url TEXT,
  notes TEXT,
  UNIQUE(drug_id, milestone)
);
GRANT SELECT ON public.drug_development_timelines TO anon;
CREATE POLICY "anon_read" ON public.drug_development_timelines FOR SELECT TO anon USING (true);
ALTER TABLE public.drug_development_timelines ENABLE ROW LEVEL SECURITY;
