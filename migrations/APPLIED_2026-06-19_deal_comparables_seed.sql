-- APPLIED 2026-06-19: backfill deal_comparables from the live, SOURCED deals table (#10).
-- "Comps beside the estimate" approach (Kyle): valuation cards keep their labeled estimate
-- and gain a list of real, sourced comparables. Every row's source_url comes from deals —
-- nothing fabricated (constitution). area_id added so the renderer can match comps to a program.

ALTER TABLE public.deal_comparables ADD COLUMN IF NOT EXISTS area_id text;

-- Idempotent reseed: clear prior auto-import, then import sourced+valued deals.
DELETE FROM public.deal_comparables WHERE notes = 'auto-import from deals';

INSERT INTO public.deal_comparables
  (area_id, acquirer, asset, deal_type, upfront_usd_m, total_usd_m, deal_year, source_url, notes)
SELECT
  d.area_id,
  COALESCE(d.to_company, d.from_company)            AS acquirer,
  d.headline                                         AS asset,
  d.deal_type,
  d.upfront_usd_m,
  d.total_usd_m,
  CASE WHEN d.deal_date IS NOT NULL THEN extract(year FROM d.deal_date)::int END AS deal_year,
  d.source_url,
  'auto-import from deals'                            AS notes
FROM public.deals d
WHERE d.source_url IS NOT NULL
  AND d.source_url <> ''
  AND (d.upfront_usd_m IS NOT NULL OR d.total_usd_m IS NOT NULL);

-- VALIDATION:
-- 1. every comp has a source (enforced NOT NULL too):
--    select count(*) from deal_comparables where source_url is null or source_url='';  -- expect 0
-- 2. comps available per area (sanity):
--    select area_id, count(*) from deal_comparables group by area_id order by 2 desc;
