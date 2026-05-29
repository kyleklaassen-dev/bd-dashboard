-- v64 Knowledge Folders — Meridian v2
-- Area knowledge: curated descriptions of each disease area/target
CREATE TABLE IF NOT EXISTS area_knowledge (
    id BIGSERIAL PRIMARY KEY,
    area_slug TEXT UNIQUE NOT NULL,  -- 'tl1a', 'ibd', 'uc', 'atopy', etc.
    area_name TEXT NOT NULL,
    area_type TEXT CHECK (area_type IN ('target', 'disease', 'mechanism', 'modality')),
    icon TEXT,                        -- emoji icon
    tagline TEXT,                     -- one-line summary
    description TEXT NOT NULL,        -- 2-3 paragraph overview
    patient_population TEXT,          -- e.g., "~3M patients in US"
    unmet_need TEXT,                  -- key unmet needs
    standard_of_care TEXT,            -- current standard of care
    key_mechanism TEXT,               -- mechanism of action summary
    ailux_relevance TEXT,             -- why Ailux cares
    drug_count_direct INTEGER,        -- cached from drug_targets
    drug_count_total INTEGER,
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    enrichment_run_id UUID
);

-- Perspectives: CEO/CSO/CBO/CFO/KOL views for each area
CREATE TABLE IF NOT EXISTS area_perspectives (
    id BIGSERIAL PRIMARY KEY,
    area_slug TEXT NOT NULL,
    perspective_role TEXT NOT NULL CHECK (perspective_role IN ('CEO', 'CSO', 'CBO', 'CFO', 'KOL')),
    role_title TEXT NOT NULL,         -- "Chief Executive Officer"
    perspective_icon TEXT,            -- emoji
    narrative TEXT NOT NULL,          -- 2-3 sentence narrative from this lens
    key_points JSONB,                 -- ["Point 1", "Point 2", "Point 3"]
    strategic_question TEXT,          -- the question this role would ask
    bottom_line TEXT,                 -- one-sentence takeaway
    confidence_source TEXT DEFAULT 'model',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(area_slug, perspective_role)
);

CREATE INDEX IF NOT EXISTS ak_slug_idx ON area_knowledge(area_slug);
CREATE INDEX IF NOT EXISTS ap_slug_role_idx ON area_perspectives(area_slug, perspective_role);
