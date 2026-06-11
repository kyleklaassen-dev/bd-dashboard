-- v151: drug identity crosswalk (PubChem/RxNorm/UNII/InChIKey) + register new sources.
-- drugsfda -> EXISTING fda_approvals (no new table). literature_records DROPPED
-- (was a duplicate of publications; folded in, raw preserved in api_raw_documents).
create table if not exists compound_identifiers (
    id text primary key, drug_id text, name text,
    pubchem_cid text, rxcui text, unii text, inchikey text,
    molecular_formula text, molecular_weight numeric, smiles text,
    source_url text, fetched_at timestamptz default now());
create index if not exists idx_cid_drug on compound_identifiers(drug_id);
create index if not exists idx_cid_inchikey on compound_identifiers(inchikey);
alter table compound_identifiers enable row level security;
