-- Migration v43: next_gen_rankings — historical bispecific race positions
-- Tracks ranking, score, stage for each entity in each area tab over time.
-- Powers: movement arrows, predictive scoring, BD intelligence timeline.

CREATE TABLE IF NOT EXISTS public.next_gen_rankings (
  id            BIGSERIAL PRIMARY KEY,
  entity_id     TEXT NOT NULL,
  entity_name   TEXT,
  area_id       TEXT NOT NULL,
  rank_position INTEGER NOT NULL,
  score         INTEGER NOT NULL,
  stage         TEXT,
  is_ailux      BOOLEAN DEFAULT FALSE,
  score_breakdown JSONB,
  snapshot_date DATE NOT NULL DEFAULT CURRENT_DATE,
  recorded_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS next_gen_rankings_daily_uniq
  ON public.next_gen_rankings (entity_id, area_id, snapshot_date);

CREATE INDEX IF NOT EXISTS next_gen_rankings_area_date
  ON public.next_gen_rankings (area_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS next_gen_rankings_entity_area
  ON public.next_gen_rankings (entity_id, area_id, recorded_at DESC);

ALTER TABLE public.next_gen_rankings ENABLE ROW LEVEL SECURITY;
CREATE POLICY IF NOT EXISTS "anon_read"   ON public.next_gen_rankings FOR SELECT TO anon USING (true);
CREATE POLICY IF NOT EXISTS "anon_insert" ON public.next_gen_rankings FOR INSERT TO anon WITH CHECK (true);
CREATE POLICY IF NOT EXISTS "anon_update" ON public.next_gen_rankings FOR UPDATE TO anon USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE ON public.next_gen_rankings TO anon;
