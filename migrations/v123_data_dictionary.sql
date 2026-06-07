-- v123: Data Dictionary + Attribute Completeness (Kyle voice-memo 2026-06-07)
-- Attribute taxonomy anchored to the 100Q 8-domain frame, phase-conditional
-- completeness measurement, and the Citeline benchmark mapping.
-- Additive only. Rollback at bottom.

create table if not exists data_dictionary (
  attribute_key   text primary key,
  display_name    text not null,
  domain          text not null check (domain in
    ('Molecule','Clinical','Patient','Payer','Competitive','Regulatory','IP','Strategic BD')),
  source_table    text not null,
  source_column   text,                    -- null => satellite row-existence check
  check_type      text not null check (check_type in ('column_nonnull','satellite_rows')),
  phase_expected  int  not null check (phase_expected between 0 and 5),
  -- 0=Preclinical 1=Ph1 2=Ph2 3=Ph3 4=Filed 5=Approved
  plain_description text,                  -- plain-English, non-technical
  example_text    text,
  citeline_module text,                    -- which paid-platform module this maps to
  benchmark_status text check (benchmark_status in ('have','partial','missing')),
  benchmark_note  text,
  sort_order      int default 100,
  created_at      timestamptz default now()
);

create table if not exists attribute_completeness (
  id            bigserial primary key,
  drug_id       text not null,
  drug_name     text,
  stage         text,
  stage_rank    int,                        -- same 0-5 scale; null = excluded (discontinued)
  attribute_key text not null references data_dictionary(attribute_key),
  domain        text not null,
  expected      boolean not null,           -- stage_rank >= phase_expected
  filled        boolean not null,
  computed_at   timestamptz default now(),
  unique (drug_id, attribute_key)
);

create index if not exists idx_attr_comp_drug on attribute_completeness(drug_id);
create index if not exists idx_attr_comp_attr on attribute_completeness(attribute_key);

-- Rollup: % filled per domain per phase (expected attributes only)
create or replace view v_completeness_by_phase as
select domain, stage_rank,
       count(*) filter (where expected)              as expected_n,
       count(*) filter (where expected and filled)   as filled_n,
       round(100.0 * count(*) filter (where expected and filled)
             / nullif(count(*) filter (where expected),0), 1) as pct_filled
from attribute_completeness
where stage_rank is not null
group by domain, stage_rank;

-- anon read (RLS pattern per project_rls_read_policies)
alter table data_dictionary enable row level security;
alter table attribute_completeness enable row level security;
drop policy if exists anon_read_data_dictionary on data_dictionary;
create policy anon_read_data_dictionary on data_dictionary for select using (true);
drop policy if exists anon_read_attribute_completeness on attribute_completeness;
create policy anon_read_attribute_completeness on attribute_completeness for select using (true);

-- ROLLBACK:
-- drop view if exists v_completeness_by_phase;
-- drop table if exists attribute_completeness;
-- drop table if exists data_dictionary;
