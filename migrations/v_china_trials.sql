-- china_trials — matched WHO ICTRP / ChiCTR trials for our China-developed assets.
-- Populated by scripts/integrations/ictrp_china_harvest.py (resolve-or-skip;
-- only trials matched to a real drugs.id are written here — bronze lives in
-- source_payloads). Idempotent: CREATE IF NOT EXISTS, UNIQUE(trial_id) for upsert.
CREATE TABLE IF NOT EXISTS public.china_trials (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    trial_id            text NOT NULL UNIQUE,        -- WHO/ChiCTR trial id
    registry            text,                        -- e.g. 'ChiCTR'
    drug_id             text REFERENCES public.drugs(id),
    matched_term        text,
    public_title        text,
    scientific_title    text,
    condition           text,
    intervention        text,
    sponsor             text,
    recruitment_status  text,
    registration_date   text,
    source_url          text NOT NULL,
    session_label       text,
    fetched_at          timestamptz NOT NULL DEFAULT now(),
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_china_trials_drug ON public.china_trials(drug_id);

-- Mirror project RLS convention: lock writes, keep anon reads open for the dashboard.
ALTER TABLE public.china_trials ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS anon_read_china_trials ON public.china_trials;
CREATE POLICY anon_read_china_trials ON public.china_trials FOR SELECT USING (true);
