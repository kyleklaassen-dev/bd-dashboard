-- v124: data_sources — registry of every connected external API/source (Kyle ask 2026-06-07)
create table if not exists data_sources (
  source_key   text primary key,
  display_name text not null,
  category     text not null,         -- science | clinical | regulatory | financial | ip | literature | news | entity | china
  what_we_get  text not null,         -- plain English
  tables_fed   text[],                -- supabase tables this source populates
  access       text not null default 'free',  -- free | freemium | paid | blocked
  status       text not null default 'active',-- active | partial | attempted_blocked | planned
  status_note  text,
  api_url      text,
  sort_order   int default 100
);
alter table data_sources enable row level security;
drop policy if exists anon_read_data_sources on data_sources;
create policy anon_read_data_sources on data_sources for select using (true);
-- ROLLBACK: drop table if exists data_sources;
