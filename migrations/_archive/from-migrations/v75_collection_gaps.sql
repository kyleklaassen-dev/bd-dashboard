-- v75: Gap-driven collection queue
-- The triangulation + independence layers tell us WHICH claims are weakly sourced.
-- This turns that into an actionable, always-fresh list: fact-bearing claims that
-- lack an INDEPENDENT (peer-reviewed/regulatory) source, tiered by urgency so the
-- research pipeline (or a human) can go collect the missing second source.
-- Derived view — no state yet (a stateful backing table with status/attempts is the
-- next increment); this is the live truth of what needs corroboration right now.

CREATE OR REPLACE VIEW source_collection_gaps AS
WITH per_claim AS (
  SELECT n.entity_type, n.entity_id, n.section, p.claim_index,
         max(p.claim_text)                                            AS claim_text,
         count(DISTINCT split_part(
                 regexp_replace(p.source_url, '^https?://(www\.)?', ''), '/', 1))
           FILTER (WHERE p.source_url IS NOT NULL)                    AS domains,
         coalesce(max(p.tier_rank), 1)                                AS max_rank,
         bool_or(p.independence_tier IN ('peer_reviewed', 'regulatory')) AS has_independent
  FROM narrative_provenance p
  JOIN entity_narratives n ON n.id = p.narrative_id
  GROUP BY n.entity_type, n.entity_id, n.section, p.claim_index
)
SELECT
  entity_type, entity_id, section, claim_index, claim_text, domains, max_rank,
  CASE WHEN max_rank <= 2 THEN 'no_independent_source'        -- sponsor/internal only (urgent)
       ELSE 'registry_only_no_publication' END AS gap_type,    -- registry but no peer-reviewed paper
  (CASE WHEN claim_text ~* '(\d+(\.\d+)?\s*%|remission|response|endpoint|survival|efficacy)'
        THEN 2 ELSE 0 END
   + CASE WHEN max_rank <= 2 THEN 2 ELSE 0 END
   + CASE WHEN domains < 2 THEN 1 ELSE 0 END)                  AS priority
FROM per_claim
WHERE NOT has_independent
  -- only fact-bearing claims are worth corroborating (skip pure framing/transition)
  AND claim_text ~* '(\d|%|phase|remission|response|approv|half-life|\mweek\M)'
ORDER BY priority DESC, entity_type, entity_id, claim_index;
