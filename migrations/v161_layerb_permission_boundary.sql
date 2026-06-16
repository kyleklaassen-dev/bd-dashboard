-- ============================================================================
-- v161_layerb_permission_boundary.sql
-- Stage 4 — Layer B: the permission boundary that makes the Writer the only
-- channel that can mutate core tables (Constitution §4; PROPOSED_drugwriter §B).
-- Created: 2026-06-16 · Author: claude_agent
--
-- BEFORE: anon + authenticated had FULL INSERT/UPDATE/DELETE/TRUNCATE on
-- drugs/companies/catalysts/entity_edges — i.e. the publishable (client) key
-- could rewrite any field of any core row. Only RLS stood in the way, and RLS
-- had an `anon_update_drugs_partnership` UPDATE policy (used by the dashboard's
-- partnership-pill confirm/remove feature, index.html ~L21171).
--
-- AFTER:
--   * anon/authenticated lose INSERT/UPDATE/DELETE/TRUNCATE on all 4 core tables.
--   * SELECT is retained (the client read path).
--   * the ONE live client write — toggling drug partnership status — is preserved
--     by a COLUMN-scoped grant: anon may UPDATE only (partnership_verified,
--     partner_company) on drugs, nothing else.
--   * service_role (the Writers' key) is untouched → pipelines keep working.
-- Reversible: GRANT the privileges back.
-- ============================================================================

BEGIN;

-- 1) drop the broad write grants on all four core tables
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.drugs        FROM anon, authenticated;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.companies    FROM anon, authenticated;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.catalysts    FROM anon, authenticated;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.entity_edges FROM anon, authenticated;

-- 2) preserve ONLY the partnership-pill feature: anon may set these two columns
GRANT UPDATE (partnership_verified, partner_company) ON public.drugs TO anon;

INSERT INTO schema_change_log
    (migration_version, migration_file, change_type, object_name, field_name,
     old_definition, new_definition, rationale)
VALUES
('v161','v161_layerb_permission_boundary.sql','alter_table','drugs/companies/catalysts/entity_edges',NULL,
 'anon+authenticated: full INSERT/UPDATE/DELETE/TRUNCATE',
 'anon write removed except drugs(partnership_verified,partner_company); service_role unchanged',
 'Stage 4 Layer B: Writer (service_role) is the only mutation channel for core tables; client keeps read + the partnership-pill toggle only.');

COMMIT;
