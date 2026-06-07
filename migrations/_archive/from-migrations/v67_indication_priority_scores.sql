-- v67_indication_priority_scores.sql
-- Creates the indication_priority_scores table for the Patient→Indication→Target→Company hierarchy
-- Apply via Supabase SQL Editor: https://supabase.com/dashboard/project/tghntyofptvfhmtchwcv/sql/new

CREATE TABLE IF NOT EXISTS public.indication_priority_scores (
    indication_id TEXT PRIMARY KEY,
    indication_name TEXT NOT NULL,
    patient_count_us INTEGER,
    market_size_usd_bn NUMERIC,
    unmet_need_score INTEGER CHECK (unmet_need_score BETWEEN 1 AND 10),
    biologic_failure_rate_pct NUMERIC,
    remission_rate_soc_pct NUMERIC,
    ailux_fit_score INTEGER CHECK (ailux_fit_score BETWEEN 1 AND 10),
    competitive_white_space INTEGER CHECK (competitive_white_space BETWEEN 1 AND 10),
    indication_priority_rank INTEGER,
    priority_rationale TEXT,
    alx_programs TEXT[],
    last_computed TIMESTAMPTZ DEFAULT NOW()
);

-- Grant read access to anon (dashboard reads)
GRANT SELECT ON public.indication_priority_scores TO anon;
-- Grant full access to service role (enrichment pipeline writes)
GRANT ALL ON public.indication_priority_scores TO service_role;

COMMENT ON TABLE public.indication_priority_scores IS
'Patient→Indication→Target→Company hierarchy anchor table.
Scores and ranks all 17 Meridian indication areas by:
  (1) Ailux program fit, (2) competitive white space,
  (3) unmet need, (4) biologic failure rate.
Computed by scripts/seed_indication_priorities.py.';

COMMENT ON COLUMN public.indication_priority_scores.ailux_fit_score IS
'1-10: how directly does an ALX program address this indication?
10=direct program target (UC/CD/gMG/CIDP), 7-9=strong mechanistic fit,
4-6=adjacent, 1-3=exploratory/watch only.';

COMMENT ON COLUMN public.indication_priority_scores.competitive_white_space IS
'1-10: how uncrowded is the bispecific space?
10=no approved bispecific, only mono Phase 1s,
7-9=some Phase 2 bispecifics no Phase 3 readout <12mo,
4-6=Phase 3 bispecifics underway,
1-3=bispecific approved or imminent.';

COMMENT ON COLUMN public.indication_priority_scores.indication_priority_rank IS
'Composite rank across all tracked indications.
Formula: (unmet_need_score * 0.3) + (ailux_fit_score * 0.3)
         + (competitive_white_space * 0.2) + (biologic_failure_rate_pct / 10 * 0.2)';
