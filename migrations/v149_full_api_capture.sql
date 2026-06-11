-- v149_full_api_capture.sql
-- Goal: capture 100% of what each external API provides, organized for review.
-- Design: a universal RAW landing table (verbatim jsonb = nothing is ever lost) +
--         REFINED typed tables for the high-value slices, all source-stamped.
-- Sources wired: CT.gov v2, openFDA (label + FAERS), Europe PMC, ChEMBL, Open Targets.
-- Origin: 2026-06-10 "populate and connect everything" directive.

-- ============================================================
-- 0) RAW landing — the 100%-capture guarantee
-- ============================================================
create table if not exists api_raw_documents (
    id           text primary key,        -- '<source>:<entity_key>[:variant]'
    source       text not null,           -- ctgov | openfda_label | openfda_event | europepmc | chembl | opentargets | dailymed
    entity_type  text,                    -- trial | drug | target | publication | molecule
    entity_key   text,                    -- NCT id / drug_id / CHEMBL id / PMID / ensembl id
    drug_id      text,                    -- link to drugs when resolvable
    api_version  text,
    source_url   text not null,
    payload      jsonb not null,          -- the FULL response, verbatim
    fetched_at   timestamptz default now()
);
create index if not exists idx_raw_source on api_raw_documents(source);
create index if not exists idx_raw_key    on api_raw_documents(entity_key);
create index if not exists idx_raw_drug   on api_raw_documents(drug_id);
create index if not exists idx_raw_gin    on api_raw_documents using gin(payload);

-- ============================================================
-- 1) CT.gov refined (beyond outcomes/design already stored)
-- ============================================================
create table if not exists trial_participant_flow (
    id text primary key, nct_id text not null, drug_id text,
    period_label text, group_label text, milestone text,   -- STARTED | COMPLETED | NOT COMPLETED
    count_n integer, drop_reason text, source_url text not null, fetched_at timestamptz default now());
create index if not exists idx_tpf_nct on trial_participant_flow(nct_id);

create table if not exists trial_baseline_characteristics (
    id text primary key, nct_id text not null, drug_id text,
    group_label text, characteristic text, category text,
    value_num numeric, value_text text, unit text, source_url text not null, fetched_at timestamptz default now());
create index if not exists idx_tbc_nct on trial_baseline_characteristics(nct_id);

create table if not exists ct_trial_adverse_events (
    id text primary key, nct_id text not null, drug_id text,
    group_label text, event_term text, organ_system text,
    serious boolean, affected_n integer, at_risk_n integer,
    source_url text not null, fetched_at timestamptz default now());
create index if not exists idx_ctae_nct on ct_trial_adverse_events(nct_id);

create table if not exists trial_eligibility (
    nct_id text primary key, drug_id text,
    minimum_age text, maximum_age text, sex text, healthy_volunteers boolean,
    criteria_text text, prior_biologic_required boolean, source_url text not null, fetched_at timestamptz default now());

create table if not exists trial_locations (
    id text primary key, nct_id text not null, facility text, city text, state text,
    country text, status text, source_url text not null, fetched_at timestamptz default now());
create index if not exists idx_tloc_nct on trial_locations(nct_id);

-- ============================================================
-- 2) openFDA refined — typed label facts (ADA, approval, warnings)
-- ============================================================
create table if not exists drug_label_facts (
    id text primary key, drug_id text, application_number text, set_id text,
    fact_type text,                       -- immunogenicity_ada | approval_date | boxed_warning | indication | dosage
    value_text text, value_num numeric, section_name text,
    source_url text not null, fetched_at timestamptz default now());
create index if not exists idx_dlf_drug on drug_label_facts(drug_id);
create index if not exists idx_dlf_type on drug_label_facts(fact_type);

-- ============================================================
-- 3) Open Targets — target/disease association scores + genetics
-- ============================================================
create table if not exists target_disease_associations (
    id text primary key, target_symbol text, ensembl_id text,
    disease_label text, efo_id text, overall_score numeric,
    genetic_association numeric, known_drug numeric, literature numeric,
    datatype_scores jsonb, source_url text not null, fetched_at timestamptz default now());
create index if not exists idx_tda_target on target_disease_associations(target_symbol);

-- ============================================================
-- 4) ChEMBL — molecule chemistry + regulatory metadata
-- ============================================================
create table if not exists molecule_properties (
    id text primary key, drug_id text, chembl_id text, pref_name text,
    molecule_type text, max_phase text, first_approval integer, first_in_class integer,
    black_box_warning integer, oral boolean, parenteral boolean, withdrawn_flag boolean,
    mw_freebase numeric, alogp numeric, psa numeric, hba integer, hbd integer,
    ro5_violations integer, canonical_smiles text, standard_inchi_key text,
    usan_stem text, usan_stem_definition text, atc_classifications jsonb, synonyms jsonb,
    source_url text not null, fetched_at timestamptz default now());
create index if not exists idx_molprop_drug on molecule_properties(drug_id);

-- ============================================================
-- 5) Europe PMC — literature records (reconcile w/ existing publication tables later)
-- ============================================================
create table if not exists literature_records (
    id text primary key, pmid text, doi text, title text, journal text,
    pub_year integer, authors text, is_open_access boolean, cited_by_count integer,
    mesh_terms jsonb, keywords jsonb, abstract_text text, drug_id text, nct_id text,
    source_url text not null, fetched_at timestamptz default now());
create index if not exists idx_lit_pmid on literature_records(pmid);
create index if not exists idx_lit_drug on literature_records(drug_id);

-- ============================================================
-- 6) API source registry + coverage view
-- ============================================================
create table if not exists api_sources (
    source text primary key, base_url text, auth_required boolean default false,
    cadence text, free boolean default true, status text default 'active',
    last_run timestamptz, notes text);
