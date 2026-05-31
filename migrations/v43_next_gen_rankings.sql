-- Migration v43: next_gen_rankings — historical bispecific race positions
-- Rankings are derived from ACTUAL DB field values (stage, competitive score).
-- When competitive_scoring.py updates a drug's score, the rank changes.
-- The snapshot records what values were before each change — that's the learning signal.
--
-- Apply at: https://supabase.com/dashboard/project/tghntyofptvfhmtchwcv/sql/new

CREATE TABLE IF NOT EXISTS public.next_gen_rankings (
  id                BIGSERIAL PRIMARY KEY,
  entity_id         TEXT NOT NULL,
  entity_name       TEXT,
  area_id           TEXT NOT NULL,
  rank_position     INTEGER NOT NULL,
  -- Actual known DB values that produced this rank:
  total_score       NUMERIC,    -- drug_competitive_scores.total_competition_score
  stage             TEXT,       -- drugs.stage at time of snapshot
  competitive_relev TEXT,       -- drug_competitive_scores.competitive_relevance
  is_ailux          BOOLEAN DEFAULT FALSE,
  snapshot_date     DATE NOT NULL DEFAULT CURRENT_DATE,
  recorded_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS next_gen_rankings_daily_uniq
  ON public.next_gen_rankings (entity_id, area_id, snapshot_date);

CREATE INDEX IF NOT EXISTS next_gen_rankings_area_date
  ON public.next_gen_rankings (area_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS next_gen_rankings_entity_history
  ON public.next_gen_rankings (entity_id, area_id, recorded_at DESC);

ALTER TABLE public.next_gen_rankings ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  CREATE POLICY "anon_read" ON public.next_gen_rankings FOR SELECT TO anon USING (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "anon_insert" ON public.next_gen_rankings FOR INSERT TO anon WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "anon_update" ON public.next_gen_rankings FOR UPDATE TO anon USING (true) WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

GRANT SELECT, INSERT, UPDATE ON public.next_gen_rankings TO anon;
