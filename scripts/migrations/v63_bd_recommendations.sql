-- Migration v63: BD Recommendations Engine table
-- Applied: 2026-05-29
-- Created by: bd_recommender.py via Supabase Management API
-- Purpose: Store weekly ranked BD call list with Claude-generated deal framings

CREATE TABLE IF NOT EXISTS bd_recommendations (
    id                   SERIAL PRIMARY KEY,
    company_id           TEXT NOT NULL,
    recommendation_date  DATE NOT NULL,
    total_score          NUMERIC,          -- 0–100 composite
    strategic_value_pts  NUMERIC,          -- 0–30 from companies.strategic_value_score
    pipeline_urgency_pts NUMERIC,          -- 0–25 from catalyst_calendar (next 12 mo)
    deal_appetite_pts    NUMERIC,          -- 0–20 from deals (last 18 mo)
    partnership_fit_pts  NUMERIC,          -- 0–15 from company_strategic_views.view_type
    coverage_gap_pts     NUMERIC,          -- 0–10 from companies.coverage_status
    rank                 INTEGER,          -- 1 = highest priority
    deal_framing         TEXT,             -- Claude Haiku 3-sentence BD opener
    call_urgency         TEXT,             -- this_week | this_month | this_quarter | watch
    key_catalyst         TEXT,             -- Most urgent upcoming catalyst driving score
    created_at           TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_bd_rec_date    ON bd_recommendations(recommendation_date);
CREATE INDEX IF NOT EXISTS idx_bd_rec_company ON bd_recommendations(company_id);
CREATE INDEX IF NOT EXISTS idx_bd_rec_urgency ON bd_recommendations(call_urgency);

-- Notes:
-- Refreshed weekly by bd_recommender.py (also callable via weekend_sprint.py --phase F9)
-- AbbVie governance constraint enforced at script level (downgraded to 'watch' until Oct 2026)
-- Table is cleared + re-inserted each run (not upserted) to ensure clean weekly snapshot
