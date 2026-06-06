-- v78 — Whitespace Finder views
-- Uses the structural graph built 2026-06-06 (TREATS drug->indication, ADDRESSES
-- target->indication) + indication_patient_intelligence to surface where high
-- patient unmet need meets thin late-stage competition. Views = always-live; no
-- staleness. The normalized tables remain the source of truth.
--
-- Scoring is intentionally transparent: every component column is exposed so the
-- opportunity score can be audited and re-tuned without re-deriving the graph.

-- Late-stage = the crowded end of a pipeline (a target/indication with many
-- Phase 3 / filed / approved assets is saturated, not whitespace).
DROP VIEW IF EXISTS v_whitespace_indications CASCADE;
CREATE VIEW v_whitespace_indications AS
WITH dens AS (
  SELECT i.id AS indication_id, i.name AS indication_name, i.disease_area,
         count(DISTINCT t.subject_id) AS drugs_total,
         count(DISTINCT t.subject_id) FILTER (
           WHERE d.stage ILIKE 'approved%' OR d.stage='Approved'
              OR d.stage ILIKE '%phase 3%' OR d.stage='bla_under_review') AS drugs_late,
         count(DISTINCT t.subject_id) FILTER (
           WHERE d.stage ILIKE '%phase 1%' OR d.stage ILIKE '%phase 2%'
              OR d.stage='Preclinical' OR d.stage ILIKE 'IND%') AS drugs_early
  FROM indications i
  LEFT JOIN entity_edges t ON t.object_id=i.id AND t.predicate='TREATS' AND t.status='active'
  LEFT JOIN drugs d ON d.id=t.subject_id AND d.dashboard_visible AND d.record_type='drug'
  GROUP BY i.id, i.name, i.disease_area
)
SELECT
  pi.indication_name,
  dens.indication_id,
  dens.disease_area,
  pi.unmet_need_score,
  pi.biologic_failure_rate_pct,
  pi.patient_count_us,
  pi.market_size_usd_bn,
  COALESCE(dens.drugs_total,0)  AS drugs_total,
  COALESCE(dens.drugs_late,0)   AS drugs_late,
  COALESCE(dens.drugs_early,0)  AS drugs_early,
  -- saturation 0..1 (8+ late-stage assets = fully saturated)
  LEAST(1.0, COALESCE(dens.drugs_late,0)/8.0) AS saturation,
  -- opportunity score 0..100 = (need 45 + escape 25 + scale 15 + endpoint-gap 15) * (1 - 0.6*saturation)
  round((
      (pi.unmet_need_score::numeric/10)*45
    + (COALESCE(pi.biologic_failure_rate_pct,30)/100)*25
    + LEAST(1.0, ln(GREATEST(pi.patient_count_us,1))/ln(20000000))*15
    + CASE WHEN pi.trial_endpoint_gap IS NOT NULL AND pi.trial_endpoint_gap<>'' THEN 15 ELSE 0 END
  ) * (1 - 0.6*LEAST(1.0, COALESCE(dens.drugs_late,0)/8.0)))::int AS opportunity_score,
  CASE WHEN COALESCE(dens.drugs_total,0) >= 3 THEN 'high' ELSE 'low' END AS data_confidence,
  pi.unmet_need_narrative,
  pi.trial_endpoint_gap
FROM indication_patient_intelligence pi
JOIN dens ON dens.indication_name = pi.indication_name;

COMMENT ON VIEW v_whitespace_indications IS
 'Whitespace Finder (indication-level): high patient unmet need vs thin late-stage competition. opportunity_score 0-100, all components exposed. Source: indication_patient_intelligence + TREATS edges. v78 2026-06-06.';

-- Target-level: a mechanism addressing high-unmet indications with few drugs in
-- development is an under-exploited target (mechanism whitespace).
DROP VIEW IF EXISTS v_whitespace_targets CASCADE;
CREATE VIEW v_whitespace_targets AS
WITH drugs_per_target AS (
  -- only count drugs that are live on the dashboard (a hidden/phantom drug's
  -- edge persists until re-materialized, so filter visibility here)
  SELECT e.object_id AS target_id, count(DISTINCT e.subject_id) AS drug_count
  FROM entity_edges e
  JOIN drugs d ON d.id=e.subject_id AND d.dashboard_visible AND d.record_type='drug'
  WHERE e.predicate='TARGETS' AND e.status='active' AND e.object_type='target'
  GROUP BY 1
),
addressed AS (
  SELECT a.subject_id AS target_id,
         max(pi.unmet_need_score) AS best_unmet,
         count(DISTINCT a.object_id) AS indications_addressed,
         max(pi.biologic_failure_rate_pct) AS max_escape_rate
  FROM entity_edges a
  JOIN indications i ON i.id=a.object_id
  JOIN indication_patient_intelligence pi ON pi.indication_name=i.name
  WHERE a.predicate='ADDRESSES' AND a.status='active'
  GROUP BY 1
)
SELECT
  t.id AS target_id,
  t.label AS target_label,
  t.full_name,
  t.target_class,
  t.ailux_relevance,
  t.ailux_program,
  ad.best_unmet,
  ad.indications_addressed,
  ad.max_escape_rate,
  COALESCE(dpt.drug_count,0) AS drug_count,
  LEAST(1.0, COALESCE(dpt.drug_count,0)/10.0) AS mechanism_saturation,
  -- target opportunity 0..100 = (best_unmet 70 + breadth 30) * (1 - 0.55*saturation)
  round((
      (ad.best_unmet::numeric/10)*70
    + (LEAST(ad.indications_addressed,5)::numeric/5)*30
  ) * (1 - 0.55*LEAST(1.0, COALESCE(dpt.drug_count,0)/10.0)))::int AS opportunity_score
FROM addressed ad
JOIN targets t ON t.id=ad.target_id
LEFT JOIN drugs_per_target dpt ON dpt.target_id=ad.target_id;

COMMENT ON VIEW v_whitespace_targets IS
 'Whitespace Finder (target/mechanism-level): targets addressing high-unmet indications with few drugs = under-exploited mechanism. opportunity_score 0-100. Source: ADDRESSES + TARGETS edges + patient intel. v78 2026-06-06.';

NOTIFY pgrst, 'reload schema';
