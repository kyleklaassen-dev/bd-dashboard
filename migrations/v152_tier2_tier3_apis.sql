-- v152: Tier-2 expansions + Tier-3 new free APIs.
-- ChEMBL mechanism -> drug_mechanisms; UniProt -> target_proteins;
-- Open Targets knownDrugs/safety -> target_known_drugs / target_safety.
create table if not exists drug_mechanisms (
  id text primary key, drug_id text, chembl_id text, mechanism_of_action text,
  action_type text, target_chembl_id text, target_name text, max_phase text,
  source_url text not null, fetched_at timestamptz default now());
create table if not exists target_proteins (
  id text primary key, target_symbol text, uniprot_accession text, protein_name text,
  function_text text, source_url text not null, fetched_at timestamptz default now());
create table if not exists target_known_drugs (
  id text primary key, target_symbol text, ensembl_id text, drug_name text,
  drug_chembl_id text, phase text, mechanism_of_action text, disease_label text,
  source_url text not null, fetched_at timestamptz default now());
create table if not exists target_safety (
  id text primary key, target_symbol text, ensembl_id text, event text,
  biosample text, effect text, source_url text not null, fetched_at timestamptz default now());
