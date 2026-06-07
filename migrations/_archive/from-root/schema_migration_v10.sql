-- schema_migration_v10.sql
-- Add study_acronym to trials table + approval fields to drugs table
-- Run in Supabase SQL editor

-- trials: study program acronym (e.g. "SKYLINE-UC", "U-ACHIEVE", "PURSUIT")
ALTER TABLE trials ADD COLUMN IF NOT EXISTS study_acronym TEXT;

-- drugs: approved drug commercial data fields
ALTER TABLE drugs ADD COLUMN IF NOT EXISTS approval_date TEXT;        -- "May 2023 (UC)"
ALTER TABLE drugs ADD COLUMN IF NOT EXISTS annual_revenue TEXT;       -- "$10.4B (2024)"
ALTER TABLE drugs ADD COLUMN IF NOT EXISTS patient_population TEXT;   -- "~250,000 patients on therapy"
ALTER TABLE drugs ADD COLUMN IF NOT EXISTS final_endpoints TEXT;      -- Pivotal trial endpoint results narrative

-- Index for fast acronym lookup
CREATE INDEX IF NOT EXISTS trials_study_acronym_idx ON trials(study_acronym);

COMMENT ON COLUMN trials.study_acronym IS 'Branded program acronym from ClinicalTrials.gov identificationModule.acronym (e.g. SKYLINE-UC, U-ACHIEVE, PURSUIT)';
COMMENT ON COLUMN drugs.approval_date IS 'Regulatory approval date and indication (e.g. "May 2023 (UC); Jan 2024 (CD)")';
COMMENT ON COLUMN drugs.annual_revenue IS 'Latest reported annual revenue with year (e.g. "$10.4B (2024)")';
COMMENT ON COLUMN drugs.patient_population IS 'Estimated number of patients on therapy globally';
COMMENT ON COLUMN drugs.final_endpoints IS 'Pivotal trial primary endpoint results narrative';
