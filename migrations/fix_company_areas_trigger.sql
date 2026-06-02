-- fix_company_areas_trigger.sql
-- 2026-06-02 — Fix broken trigger on company_areas that references retired disease_areas table
-- Context: disease_areas was retired as part of Phase 5 legacy read layer elimination (May 2026).
-- Any trigger/FK on company_areas that references disease_areas causes INSERT failures.
-- This migration: (1) drops broken trigger, (2) adds missing rows, (3) verifies.

-- ── 1. Identify and drop broken triggers ──────────────────────────────────────
DO $$
DECLARE
  trig_name TEXT;
BEGIN
  -- Drop any trigger on company_areas that references disease_areas
  FOR trig_name IN
    SELECT t.trigname
    FROM pg_trigger t
    JOIN pg_class c ON c.oid = t.tgrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relname = 'company_areas'
      AND n.nspname = 'public'
      AND t.tgisinternal = false
  LOOP
    RAISE NOTICE 'Dropping trigger: %', trig_name;
    EXECUTE format('DROP TRIGGER IF EXISTS %I ON public.company_areas CASCADE', trig_name);
  END LOOP;
END $$;

-- ── 2. Also drop any FK constraint referencing disease_areas ─────────────────
DO $$
DECLARE
  con_name TEXT;
BEGIN
  FOR con_name IN
    SELECT conname
    FROM pg_constraint
    WHERE conrelid = 'public.company_areas'::regclass
      AND contype = 'f'
      AND confrelid = (SELECT oid FROM pg_class WHERE relname = 'disease_areas' AND relnamespace = 'public'::regnamespace)
  LOOP
    RAISE NOTICE 'Dropping FK constraint: %', con_name;
    EXECUTE format('ALTER TABLE public.company_areas DROP CONSTRAINT IF EXISTS %I', con_name);
  END LOOP;
END $$;

-- ── 3. Insert missing company_areas rows ──────────────────────────────────────
-- These companies are P1 validation blockers — must appear in their respective tabs.

-- Candid Therapeutics in TCE (T cell) tab
-- Rationale: Candid has cizutamig (BCMA×CD3 autoimmune TCE) + full autoimmune TCE platform
INSERT INTO public.company_areas (company_id, area_id, context_type)
VALUES ('candid', 'tcell', 'platform_view')
ON CONFLICT DO NOTHING;

-- Merck in TL1A tab
-- Rationale: Merck owns tulisokibart (Phase 3 TL1A mAb via Prometheus acquisition)
INSERT INTO public.company_areas (company_id, area_id, context_type)
VALUES ('merck', 'tl1a', 'target')
ON CONFLICT DO NOTHING;

-- ── 4. Verification ───────────────────────────────────────────────────────────
SELECT company_id, area_id, context_type
FROM public.company_areas
WHERE (company_id = 'candid' AND area_id = 'tcell')
   OR (company_id = 'merck'  AND area_id = 'tl1a')
ORDER BY company_id, area_id;

-- Expected output: 2 rows
-- candid | tcell | platform_view
-- merck  | tl1a  | target
