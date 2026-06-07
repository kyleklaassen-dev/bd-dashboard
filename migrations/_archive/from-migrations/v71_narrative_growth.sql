-- v71: Narrative growth — learning loop + triangulation scaffolding
-- Design: docs/NARRATIVE_QUESTIONS_THAT_MATTER.md §growth
-- Additive only.

-- ── Learning loop ──────────────────────────────────────────────────────────
-- Captures human corrections to a narrative / Meridian Analysis so future
-- generation can read them as guidance (the first real learning loop). The
-- generator will surface unresolved feedback for an entity into the compose
-- prompt as "prior corrections — honor these".
CREATE TABLE IF NOT EXISTS narrative_feedback (
  id           uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  entity_type  text NOT NULL,                 -- drug | company | indication | target
  entity_id    text NOT NULL,
  section      text NOT NULL,                 -- overview | intelligence | ...
  narrative_id uuid REFERENCES entity_narratives(id) ON DELETE SET NULL,
  feedback_type text CHECK (feedback_type IN (
                 'wrong_fact', 'wrong_interpretation', 'missing_point',
                 'tone', 'endorse', 'other')),
  quote        text,                           -- the passage being corrected
  correction   text NOT NULL,                  -- what it should say / why
  created_by   text,
  created_at   timestamptz DEFAULT now(),
  applied      boolean NOT NULL DEFAULT false  -- set true once a regen has honored it
);
CREATE INDEX IF NOT EXISTS idx_narrative_feedback_entity
  ON narrative_feedback (entity_type, entity_id, applied);

-- ── Triangulation (depth of trust) ─────────────────────────────────────────
-- Per-narrative source diversity: how many INDEPENDENT domains and source types
-- back the claims. A narrative resting on one domain is weaker than one
-- triangulated across CT.gov + a publication + a press release. (Full per-claim
-- multi-source triangulation lands once the generator attaches >1 source/atom.)
CREATE OR REPLACE VIEW narrative_source_diversity AS
SELECT n.entity_type, n.entity_id, n.section, n.id AS narrative_id,
       count(p.*)                                           AS claims,
       count(p.source_url)                                  AS cited_claims,
       count(DISTINCT split_part(regexp_replace(p.source_url,'^https?://',''),'/',1))
                                                            AS distinct_domains,
       count(DISTINCT p.source_table)                       AS distinct_tables,
       count(*) FILTER (WHERE p.source_url ILIKE '%clinicaltrials.gov%') AS ctgov_cited
FROM entity_narratives n
LEFT JOIN narrative_provenance p ON p.narrative_id = n.id
GROUP BY n.entity_type, n.entity_id, n.section, n.id;
