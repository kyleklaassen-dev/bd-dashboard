-- PROPOSED 2026-06-19: asset-tab templating (#6) + live valuation comps (#10).
-- ░░ NOT APPLIED ░░  CREATE TABLE only — no data, no triggers on core tables.
-- Rationale + full migration sequence: docs/PROPOSED_asset_tab_templating_and_valuations.md
-- Review gate: Kyle approves these table shapes before this is run via the Management API.
-- Anchored to the existing `target_pairs` table (id is TEXT slug, e.g. 'tl1a-il23p19').
-- NOTE (verified 2026-06-19 against live DB): target_pairs currently has only 5 rows and
-- only tl1a-il23p19 is flagged ailux_pair. The IL-4Rα×TSLP, IL-4Rα×OX40L, FcRn, and
-- BCMA×CD19×CD3 programs have NO pair row yet — so target_pair_id is nullable, and
-- reconciling target_pairs (add missing pairs + flag the 7 ailux) is follow-up ontology work.

-- ════════════════════════════════════════════════════════════════════
-- 1. asset_programs — one row per Ailux program. Replaces the hardcoded
--    per-tab `ailux-card` differentiator / positioning blocks so a new
--    program is a data row, not a ~250-line cloned pane.
-- ════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS public.asset_programs (
  id               bigint generated always as identity primary key,
  program_code     text unique not null,                      -- e.g. 'ALX001'
  target_pair_id   text references public.target_pairs(id),   -- FK to existing ontology (TEXT slug; nullable)
  indication_lead  text,
  modality         text,
  status           text,                                      -- preclinical | phase_1 | phase_2 | ...
  clinical_target  text,                                      -- e.g. 'dupilumab inadequate responders'
  format_advantage text,
  differentiators  jsonb        default '[]'::jsonb,          -- [{label, value, sub}, ...]
  notes            text,
  source_url       text,                                      -- provenance for the program claims
  updated_at       timestamptz  default now(),
  created_at       timestamptz  default now()
);
COMMENT ON TABLE public.asset_programs IS
  'Ailux program profiles driving the asset tabs; replaces hardcoded ailux-card HTML. '
  'Owner: BD/strategy. Sole writer: asset module (TBD, per Single Writer Pattern). '
  'See docs/PROPOSED_asset_tab_templating_and_valuations.md.';

-- ════════════════════════════════════════════════════════════════════
-- 2. deal_comparables — curated, SOURCED comp set feeding the valuation
--    cards (#10). Replaces the hardcoded "Estimated Deal Value" numbers.
-- ════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS public.deal_comparables (
  id              bigint generated always as identity primary key,
  target_pair_id  text references public.target_pairs(id),    -- nullable: some comps are modality-level (TEXT slug)
  modality        text,
  acquirer        text not null,
  asset           text,
  deal_type       text,                                       -- acquisition | licensing | option
  upfront_usd_m   numeric,
  total_usd_m     numeric,
  deal_year       int,
  source_url      text not null,                              -- REQUIRED (constitution: every fact has a source)
  notes           text,
  created_at      timestamptz default now()
);
COMMENT ON TABLE public.deal_comparables IS
  'Sourced deal comparables for asset valuation cards (#10). Every row REQUIRES source_url. '
  'Valuation ranges are derived from these rows, not hardcoded. '
  'See docs/PROPOSED_asset_tab_templating_and_valuations.md.';

-- ════════════════════════════════════════════════════════════════════
-- 3. RLS — frontend reads via the anon/publishable key (platform pattern,
--    mirrors APPLIED_2026-06-16_rls_enable_24_exposed_tables.sql):
--    RLS ON + anon SELECT; INSERT/UPDATE/DELETE blocked for anon;
--    service_role (backend writer) bypasses RLS.
-- ════════════════════════════════════════════════════════════════════
ALTER TABLE public.asset_programs   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.deal_comparables ENABLE ROW LEVEL SECURITY;
CREATE POLICY anon_read_asset_programs   ON public.asset_programs   FOR SELECT TO anon USING (true);
CREATE POLICY anon_read_deal_comparables ON public.deal_comparables FOR SELECT TO anon USING (true);

-- ════════════════════════════════════════════════════════════════════
-- VALIDATION (run after APPLY + backfill; all must pass):
-- 1. all 7 Ailux programs present (target_pair_id may be null where the pair row doesn't exist yet):
--    select count(*) from asset_programs;                                              -- expect 7
-- 2. programs lacking a source are explicitly flagged for curation (not silently trusted):
--    select program_code from asset_programs where source_url is null;  -- review list; backfill sources over time
-- 3. every comp carries a source (also enforced NOT NULL):
--    select id from deal_comparables where source_url is null or source_url = '';      -- expect 0
-- 4. no orphan target_pair FKs:
--    select id from deal_comparables where target_pair_id is not null
--      and target_pair_id not in (select id from target_pairs);                        -- expect 0
-- 5. governance: add asset_programs + deal_comparables rows to
--    docs/database/governance_table.md (owner / sole-writer / validation) on APPLY.
