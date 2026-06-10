-- ============================================================================
-- PROPOSED — STAGED FOR REVIEW. DO NOT APPLY UNSUPERVISED.
-- Makes DrugWriter the enforced single write path for `drugs` (Constitution §4,
-- ADR-010). Two layers: (A) a DB trigger backstop that holds regardless of which
-- client writes, and (B) a permission boundary so app keys must go through an RPC.
-- Roll out in a window where you can watch the live pipelines; trigger can block
-- existing ad-hoc writers until they are migrated to DrugWriter.
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- LAYER A — validation trigger backstop (enforces invariants for ANY writer).
-- Start in WARN mode (RAISE NOTICE) for one cycle, then switch to RAISE EXCEPTION.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION enforce_drug_governance() RETURNS trigger AS $$
DECLARE approved text[] := ARRAY['approved','approved_us','approved_eu','approved_china','approved_us_eu','approved_partial'];
BEGIN
  -- normalize a dash brand to NULL (CLAUDE.md §4)
  IF NEW.brand_name IN ('—','-','') THEN NEW.brand_name := NULL; END IF;
  -- brand implies approved
  IF NEW.brand_name IS NOT NULL AND lower(coalesce(NEW.stage,'')) <> ALL(approved) THEN
    RAISE NOTICE 'drug % has brand_name but non-approved stage %', NEW.id, NEW.stage;  -- switch to RAISE EXCEPTION after migration
  END IF;
  -- company_id (originator) required on insert
  IF TG_OP = 'INSERT' AND NEW.company_id IS NULL THEN
    RAISE NOTICE 'drug % inserted without company_id (originator)', NEW.id;            -- switch to RAISE EXCEPTION after migration
  END IF;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;

-- DROP TRIGGER IF EXISTS trg_enforce_drug_governance ON drugs;
-- CREATE TRIGGER trg_enforce_drug_governance BEFORE INSERT OR UPDATE ON drugs
--   FOR EACH ROW EXECUTE FUNCTION enforce_drug_governance();

-- ---------------------------------------------------------------------------
-- LAYER B — permission boundary (the real "single writer").
-- Move ingestion scripts off the service_role key onto a limited role, then:
--   REVOKE INSERT, UPDATE ON public.drugs FROM authenticated, anon;
-- and expose a SECURITY DEFINER RPC that only DrugWriter-shaped payloads use:
--   CREATE FUNCTION write_drug(payload jsonb) RETURNS jsonb
--     SECURITY DEFINER ... (validates, upserts, records source) ...
--   GRANT EXECUTE ON FUNCTION write_drug(jsonb) TO authenticated;
-- service_role retains direct access for admin/break-glass only.
-- Success criterion: a non-DrugWriter client can no longer INSERT/UPDATE drugs.
-- ---------------------------------------------------------------------------

ROLLBACK;  -- change to COMMIT only after: (1) DrugWriter live, (2) scripts migrated,
           -- (3) trigger validated in WARN mode, (4) you can watch the pipelines.
