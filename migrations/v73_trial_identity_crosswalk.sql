-- v73: Study-identity resolver + trial→publication crosswalk
-- Deepens narrative triangulation: resolve any row that mentions a study (by
-- acronym, sponsor id, or DOI/PMID) to its canonical NCT, and pull the trial's
-- AUTHORITATIVE publications from clinicaltrials.gov so a registry claim can be
-- triangulated against its peer-reviewed paper (a genuinely independent domain).
-- Also surfaces fabricated citations: a DOI in our data that no trial's ct.gov
-- reference list contains is suspect.
-- Additive only. Populated by scripts/enrich_trial_identity.py.

-- ── Canonical study identity ────────────────────────────────────────────────
-- One row per registered trial; alias_tokens is the normalized match set
-- (acronym, org study id, secondary ids, distinctive title tokens).
CREATE TABLE IF NOT EXISTS trial_identity (
  nct_id         text PRIMARY KEY,
  drug_id        text,
  acronym        text,
  brief_title    text,
  official_title text,
  org_study_id   text,
  secondary_ids  text[],
  alias_tokens   text[],            -- normalized, for resolver matching
  source         text DEFAULT 'ctgov',
  synced_at      timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_trial_identity_drug ON trial_identity (drug_id);
CREATE INDEX IF NOT EXISTS idx_trial_identity_aliases ON trial_identity USING gin (alias_tokens);

-- ── Trial → publication crosswalk (authoritative, from ct.gov references) ────
-- Each row is an INDEPENDENT source for that trial's results, linked by the
-- registry itself. doi lets us match publication rows already in our data
-- (e.g. drug_clinical_benchmarks.source_url) back to the NCT.
CREATE TABLE IF NOT EXISTS trial_publications (
  id          uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  nct_id      text NOT NULL,
  pmid        text,
  doi         text,                 -- lowercased
  citation    text,
  journal     text,
  pub_url     text,                 -- canonical (https://doi.org/<doi>)
  ref_type    text,                 -- RESULT | BACKGROUND | DERIVED (ct.gov)
  source      text DEFAULT 'ctgov',
  synced_at   timestamptz DEFAULT now(),
  UNIQUE (nct_id, pmid)
);
CREATE INDEX IF NOT EXISTS idx_trial_pub_nct ON trial_publications (nct_id);
CREATE INDEX IF NOT EXISTS idx_trial_pub_doi ON trial_publications (lower(doi));

-- ── RLS: anon read (project pattern; writes via service key only) ────────────
ALTER TABLE trial_identity     ENABLE ROW LEVEL SECURITY;
ALTER TABLE trial_publications ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS anon_read_trial_identity ON trial_identity;
CREATE POLICY anon_read_trial_identity     ON trial_identity     FOR SELECT USING (true);
DROP POLICY IF EXISTS anon_read_trial_publications ON trial_publications;
CREATE POLICY anon_read_trial_publications ON trial_publications FOR SELECT USING (true);
