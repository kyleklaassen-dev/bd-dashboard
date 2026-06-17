-- APPLIED 2026-06-16: executed via Management API; validation returned 0 RLS-off tables, 24 policies created.
-- PROPOSED: Enable RLS + anon read-only policy on the 24 public tables
-- flagged by Supabase advisory rls_disabled_in_public (2026-06-16).
-- Replicates the established platform pattern: RLS ON + anon_read_<t> SELECT USING(true).
-- Effect: anon (publishable key) keeps READ access; INSERT/UPDATE/DELETE blocked for anon.
-- service_role (backend pipeline) is unaffected (bypasses RLS).

DO $$
DECLARE t text;
  tbls text[] := ARRAY[
    'author_institution_focus','co_authorship','company_events','company_ownership',
    'company_personnel','conference_abstract_signals','drug_safety','drug_trust_scores',
    'entity_narratives','eu_approvals','governance_enforced_rules','governance_enforcement_config',
    'governance_enforcement_log','kol_metrics','manufacturing_profile','manufacturing_sites',
    'narrative_provenance','narrative_revisions','patient_unmet_need_competition','prediction_factors',
    'prediction_revisions','publication_authors','target_disease_assoc','target_genetics'
  ];
BEGIN
  FOREACH t IN ARRAY tbls LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY;', t);
    EXECUTE format(
      'CREATE POLICY %I ON public.%I FOR SELECT TO anon USING (true);',
      'anon_read_' || t, t
    );
  END LOOP;
END $$;

-- VALIDATION (expect 0 rows = no remaining RLS-off public base tables):
-- select c.relname from pg_class c join pg_namespace n on n.oid=c.relnamespace
-- where n.nspname='public' and c.relkind='r' and c.relrowsecurity=false;
