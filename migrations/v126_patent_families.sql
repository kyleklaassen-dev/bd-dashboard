-- v126: patent_families — INPADOC-style family members per patent (SureChEMBL, keyless, free)
-- Gives every tracked patent its global family (jurisdictions it's filed in) as referenceable sources.
create table if not exists patent_families (
  id            bigserial primary key,
  patent_number text not null,          -- the seed patent we looked up (normalized US-xxxxx-xx)
  family_doc_id text not null,          -- a member doc id (e.g. EP-1234567-A1)
  jurisdiction  text,                   -- country/authority code (US, EP, WO, JP, CN...)
  kind_code     text,
  drug_id       text,                   -- linked drug if the seed maps to one
  company_id    text,                   -- linked company if the seed maps to one
  source        text default 'surechembl',
  source_url    text,                   -- patents.google.com URL for the member
  fetched_at    timestamptz default now(),
  unique (patent_number, family_doc_id)
);
create index if not exists idx_patfam_seed on patent_families(patent_number);
create index if not exists idx_patfam_drug on patent_families(drug_id);
alter table patent_families enable row level security;
drop policy if exists anon_read_patent_families on patent_families;
create policy anon_read_patent_families on patent_families for select using (true);
-- ROLLBACK: drop table if exists patent_families;
