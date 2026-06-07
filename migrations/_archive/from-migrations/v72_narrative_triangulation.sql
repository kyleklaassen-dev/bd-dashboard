-- v72: Per-claim triangulation metric + learning-loop write path
-- Builds on v70 (narrative layer) + v71 (feedback table, source-diversity view).
-- Additive only.
--
-- WHAT CHANGED IN THE GENERATOR (context):
--   narrative_gen.triangulate() now attaches INDEPENDENT corroborating sources
--   (distinct domains) to each claim atom, and write_narrative() emits one
--   narrative_provenance row per corroboration, all sharing the atom's claim_index.
--   So triangulation is now measurable PER CLAIM, not just per narrative.

-- ── Per-claim triangulation view ────────────────────────────────────────────
-- v71's narrative_source_diversity counts distinct domains across a WHOLE
-- narrative. This counts depth at the CLAIM level: how many individual claims
-- are backed by ≥2 independent sources — the real "depth of trust" signal.
CREATE OR REPLACE VIEW narrative_claim_triangulation AS
WITH per_claim AS (
  SELECT narrative_id, claim_index,
         count(*) AS source_rows,
         count(DISTINCT split_part(
                 regexp_replace(source_url, '^https?://(www\.)?', ''), '/', 1))
           FILTER (WHERE source_url IS NOT NULL)            AS distinct_domains,
         count(DISTINCT source_table)                       AS distinct_tables
  FROM narrative_provenance
  GROUP BY narrative_id, claim_index
)
SELECT n.entity_type, n.entity_id, n.section, n.id AS narrative_id,
       count(*)                                              AS claims,
       count(*) FILTER (WHERE pc.source_rows    >= 2)        AS multi_source_claims,
       count(*) FILTER (WHERE pc.distinct_domains >= 2)      AS triangulated_claims,
       round(100.0 * count(*) FILTER (WHERE pc.distinct_domains >= 2)
             / nullif(count(*), 0))                          AS triangulation_pct
FROM entity_narratives n
JOIN per_claim pc ON pc.narrative_id = n.id
GROUP BY n.entity_type, n.entity_id, n.section, n.id;

-- ── Learning-loop access (narrative_feedback created in v71) ─────────────────
-- Match the project's RLS pattern: anon may READ feedback and may CAPTURE new
-- corrections (the dashboard's "this is wrong" path), but may NOT mark them
-- applied — that's the generator's job (service key bypasses RLS).
ALTER TABLE narrative_feedback ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS anon_read_narrative_feedback ON narrative_feedback;
CREATE POLICY anon_read_narrative_feedback
  ON narrative_feedback FOR SELECT USING (true);

DROP POLICY IF EXISTS anon_capture_narrative_feedback ON narrative_feedback;
CREATE POLICY anon_capture_narrative_feedback
  ON narrative_feedback FOR INSERT
  WITH CHECK (applied = false);   -- can submit, cannot self-resolve
