-- Drug clinical-evidence signals (UI revamp Phase C).
-- Pre-aggregated per-drug signals derived from the large CTGov harvest tables
-- (ct_trial_adverse_events 72k, trial_outcome_measures 41k, trial_design_quality 1.4k),
-- which already carry drug_id (0 orphans). ~119 rows — small + anon-readable, so the
-- frontend reads it cheaply with the publishable key instead of re-aggregating 163k rows.
-- Idempotent: CREATE IF NOT EXISTS + upsert. Refreshed weekly by meridian-derived-rebuild.yml.
-- NOTE: do NOT join to the editorial `trials` table — different universe; they meet only at drug_id.

CREATE TABLE IF NOT EXISTS public.drug_clinical_signals (
  drug_id                  text primary key,
  best_quality_tier        text,
  best_quality_score       numeric,
  n_rct                    int,
  total_trials_scored      int,
  max_enrollment           int,
  any_discontinued         boolean,
  why_stopped              text,
  serious_ae_organ_classes int,
  top_serious_organ        text,
  best_remission_pct       numeric,
  computed_at              timestamptz default now()
);

-- Frontend reads via the publishable/anon key → needs an explicit anon SELECT policy
-- (mirrors anon_read_trial_design_quality); without it the key returns 0 rows silently.
ALTER TABLE public.drug_clinical_signals ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS anon_read_drug_clinical_signals ON public.drug_clinical_signals;
CREATE POLICY anon_read_drug_clinical_signals ON public.drug_clinical_signals FOR SELECT TO anon USING (true);

-- ── Refresh (idempotent upsert) ──────────────────────────────────────────────
WITH dq AS (
  SELECT drug_id,
         max(quality_score) AS best_quality_score,
         (array_agg(quality_tier ORDER BY CASE lower(coalesce(quality_tier,''))
            WHEN 'high' THEN 4 WHEN 'moderate' THEN 3 WHEN 'medium' THEN 3
            WHEN 'single_arm' THEN 2 ELSE 1 END DESC))[1] AS best_quality_tier,
         count(*) FILTER (WHERE randomized AND controlled) AS n_rct,
         count(*) AS total_trials_scored,
         max(enrollment) AS max_enrollment,
         bool_or(discontinued) AS any_discontinued,
         (array_agg(why_stopped) FILTER (WHERE why_stopped IS NOT NULL))[1] AS why_stopped
  FROM trial_design_quality WHERE drug_id IS NOT NULL GROUP BY drug_id),
ae AS (
  SELECT drug_id,
         count(DISTINCT organ_system) FILTER (WHERE serious) AS serious_ae_organ_classes,
         mode() WITHIN GROUP (ORDER BY organ_system) FILTER (WHERE serious) AS top_serious_organ
  FROM ct_trial_adverse_events WHERE drug_id IS NOT NULL GROUP BY drug_id),
eff AS (
  SELECT drug_id, max(value_num) FILTER (WHERE is_remission_metric) AS best_remission_pct
  FROM trial_outcome_measures WHERE drug_id IS NOT NULL GROUP BY drug_id)
INSERT INTO public.drug_clinical_signals
  (drug_id, best_quality_tier, best_quality_score, n_rct, total_trials_scored, max_enrollment,
   any_discontinued, why_stopped, serious_ae_organ_classes, top_serious_organ, best_remission_pct, computed_at)
SELECT drug_id, dq.best_quality_tier, dq.best_quality_score, dq.n_rct, dq.total_trials_scored, dq.max_enrollment,
       dq.any_discontinued, dq.why_stopped, ae.serious_ae_organ_classes, ae.top_serious_organ,
       eff.best_remission_pct, now()
FROM dq FULL JOIN ae USING (drug_id) FULL JOIN eff USING (drug_id)
ON CONFLICT (drug_id) DO UPDATE SET
  best_quality_tier=excluded.best_quality_tier, best_quality_score=excluded.best_quality_score,
  n_rct=excluded.n_rct, total_trials_scored=excluded.total_trials_scored, max_enrollment=excluded.max_enrollment,
  any_discontinued=excluded.any_discontinued, why_stopped=excluded.why_stopped,
  serious_ae_organ_classes=excluded.serious_ae_organ_classes, top_serious_organ=excluded.top_serious_organ,
  best_remission_pct=excluded.best_remission_pct, computed_at=now();

-- VALIDATION:
--   select count(*) from drug_clinical_signals;                       -- expect ~119
--   select count(*) from drug_clinical_signals where best_quality_tier is not null; -- ~115
--   select * from pg_policy where polname='anon_read_drug_clinical_signals';        -- 1 row
