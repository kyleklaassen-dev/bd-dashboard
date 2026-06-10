-- v148_trial_results_storage_and_verification.sql
-- Purpose: (1) store the CT.gov RESULTS payload we never captured (per-arm outcome
--          measures = the absolute counts competitor figures hand-build);
--          (2) wire a DB-wide efficacy/NCT verification system on top of the
--          EXISTING infrastructure (benchmark_publication_checks, governance_violations,
--          drug_validation_results) rather than duplicating it;
--          (3) backfill trials.trial_design from trial_results.intervention_model.
-- Origin: TL1A/UC figure verification follow-on (2026-06-10). 56 open
--         trial_misattributed_* violations confirm the NCT problem is DB-wide.

-- 1) Structured CT.gov RESULTS storage (the genuine gap) ----------------------
create table if not exists trial_outcome_measures (
    id                  text primary key,            -- {nct}_{measure_slug}_{group}
    nct_id              text not null,               -- FK trials.id
    drug_id             text,
    indication_id       text,
    outcome_type        text,                        -- 'primary' | 'secondary' | 'other'
    measure_title       text,
    endpoint_definition text,
    timepoint_label     text,
    timepoint_week      integer,
    arm_label           text,
    group_id            text,
    value_num           numeric,
    value_type          text,                        -- 'count' | 'percentage' | 'mean' | ...
    denominator_n       integer,
    units               text,
    p_value             text,
    is_remission_metric boolean default false,
    source_url          text not null,
    fetched_at          timestamptz default now()
);
create index if not exists idx_tom_nct  on trial_outcome_measures(nct_id);
create index if not exists idx_tom_drug on trial_outcome_measures(drug_id);
create index if not exists idx_tom_rem  on trial_outcome_measures(is_remission_metric);
alter table trial_outcome_measures enable row level security;

-- 2) Provenance/verification columns on the efficacy spine (idempotent) --------
alter table drug_efficacy_endpoints add column if not exists nct_verified boolean;
alter table drug_efficacy_endpoints add column if not exists nct_verification_note text;
alter table drug_efficacy_endpoints add column if not exists results_available boolean;
alter table drug_efficacy_endpoints add column if not exists api_last_checked timestamptz;

comment on column trials.trial_design is
  'Registry intervention model (parallel/single_group/crossover/sequential/factorial), backfilled from CT.gov via trial_results. The induction-vs-maintenance comparability nuance (treat_through/re_randomized_responder) lives in drug_efficacy_endpoints.maintenance_design.';
