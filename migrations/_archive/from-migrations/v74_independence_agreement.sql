-- v74: Independence weighting + agreement (value-conflict) layer
-- Makes triangulation depth mean BETTER, not just MORE: a claim corroborated by a
-- peer-reviewed/regulatory source across domains is stronger than two same-sponsor
-- pages; and when two sources report different numbers for the same metric, we
-- surface the disagreement instead of smoothing it.
-- Additive only.

-- ── Independence tier on each provenance row ────────────────────────────────
-- tier_rank: peer_reviewed/regulatory=5, registry=4, independent_news=3,
-- sponsor (company IR / PR wire / SEC)=2, internal (our tables, no URL)=1.
ALTER TABLE narrative_provenance ADD COLUMN IF NOT EXISTS independence_tier text;
ALTER TABLE narrative_provenance ADD COLUMN IF NOT EXISTS tier_rank int;

-- ── Per-narrative independence metric ───────────────────────────────────────
-- multi_domain_claims  = ≥2 distinct domains (basic triangulation).
-- independent_claims    = ≥2 domains AND backed by a peer-reviewed/regulatory
--                         source (rank 5) — the gold standard of corroboration.
-- peer_reviewed_claims  = ≥1 peer-reviewed source.
CREATE OR REPLACE VIEW narrative_independence AS
WITH per_claim AS (
  SELECT narrative_id, claim_index,
         count(DISTINCT split_part(
                 regexp_replace(source_url, '^https?://(www\.)?', ''), '/', 1))
           FILTER (WHERE source_url IS NOT NULL)        AS domains,
         max(tier_rank)                                 AS max_rank,
         bool_or(independence_tier = 'peer_reviewed'
                 OR independence_tier = 'regulatory')   AS has_independent
  FROM narrative_provenance
  GROUP BY narrative_id, claim_index
)
SELECT n.entity_type, n.entity_id, n.section, n.id AS narrative_id,
       count(*)                                                       AS claims,
       count(*) FILTER (WHERE pc.domains >= 2)                        AS multi_domain_claims,
       count(*) FILTER (WHERE pc.domains >= 2 AND pc.has_independent) AS independent_claims,
       count(*) FILTER (WHERE pc.has_independent)                     AS peer_reviewed_claims
FROM entity_narratives n
JOIN per_claim pc ON pc.narrative_id = n.id
GROUP BY n.entity_type, n.entity_id, n.section, n.id;

-- ── Agreement: detected value disagreements across sources ──────────────────
-- Same drug + metric + timepoint + normalized dose, materially divergent reported
-- rates = a contradiction worth a human's eyes (data error, or two sources that
-- genuinely disagree). Feeds the trust score and a future "disagreement" badge.
CREATE TABLE IF NOT EXISTS narrative_value_conflicts (
  id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  drug_id         text NOT NULL,
  nct_id          text,
  metric          text NOT NULL,
  timepoint_weeks int,
  dose_norm       text,
  values_json     jsonb,          -- [{value, source_url, trial_name}]
  value_min       numeric,
  value_max       numeric,
  delta           numeric,
  detected_at     timestamptz DEFAULT now(),
  UNIQUE (drug_id, metric, timepoint_weeks, dose_norm)
);
CREATE INDEX IF NOT EXISTS idx_value_conflicts_drug ON narrative_value_conflicts (drug_id);

ALTER TABLE narrative_value_conflicts ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS anon_read_value_conflicts ON narrative_value_conflicts;
CREATE POLICY anon_read_value_conflicts ON narrative_value_conflicts FOR SELECT USING (true);
