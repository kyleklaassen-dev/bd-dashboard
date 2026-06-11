-- v150: count->rate conversion view + API->graph edge provenance.
-- v_trial_remission_rates: joins trial_outcome_measures remitter COUNTS to
-- trial_participant_flow STARTED denominators -> auto-computed remission %.
create or replace view v_trial_remission_rates as
with denom as (
  select nct_id, group_label, max(count_n) as started_n
  from trial_participant_flow where milestone='STARTED' group by nct_id, group_label)
select o.nct_id, o.drug_id, o.measure_title, o.arm_label, o.timepoint_label,
       o.value_num as remitters_n,
       coalesce(o.denominator_n, d.started_n) as denominator_n,
       round(100.0 * o.value_num / nullif(coalesce(o.denominator_n, d.started_n),0), 1) as remission_rate_pct,
       o.source_url
from trial_outcome_measures o
left join denom d on d.nct_id=o.nct_id and d.group_label=o.arm_label
where o.is_remission_metric and o.value_type ilike '%count%';
-- Taxonomy: ASSOCIATED_WITH predicate added for target<->indication (Open Targets genetics).
-- Graph edges seeded by scripts/seed_api_edges.py (notes='api_harvest_v149'):
--   target --ASSOCIATED_WITH--> indication ; drug --STUDIES--> publication.
