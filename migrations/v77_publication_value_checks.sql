-- v77: Cross-publication value agreement
-- The intra-DB agreement check (v74) compares values we already stored. This goes
-- a step further: it reads the number printed in the LINKED PAPER's own abstract
-- (via Europe PMC, linked through the v73 ct.gov crosswalk) and checks whether our
-- stored benchmark value actually appears there.
--   confirmed              -> the paper's abstract reports our number (independent confirmation)
--   unconfirmed_in_abstract-> our number is not in the abstract (may be full-text-only, or wrong)
-- Populated by scripts/verify_publication_values.py.

CREATE TABLE IF NOT EXISTS benchmark_publication_checks (
  id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  drug_id         text NOT NULL,
  nct_id          text,
  pmid            text,
  doi             text,
  metric          text,
  timepoint_weeks int,
  dose_label      text,
  stored_value    numeric,
  status          text CHECK (status IN ('confirmed', 'unconfirmed_in_abstract')),
  abstract_values numeric[],
  checked_at      timestamptz DEFAULT now(),
  UNIQUE (drug_id, nct_id, metric, timepoint_weeks, dose_label, stored_value)
);
CREATE INDEX IF NOT EXISTS idx_pub_checks_drug ON benchmark_publication_checks (drug_id);

ALTER TABLE benchmark_publication_checks ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS anon_read_pub_checks ON benchmark_publication_checks;
CREATE POLICY anon_read_pub_checks ON benchmark_publication_checks FOR SELECT USING (true);
