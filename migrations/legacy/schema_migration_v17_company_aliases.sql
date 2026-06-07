-- Migration v17: company_aliases table + company_identity_resolver infrastructure
-- Run in Supabase SQL editor before deploying company_identity_resolver.py
-- 2026-05-22

-- ── company_aliases ───────────────────────────────────────────────────────────
-- Stores all known name variants for each company so CompanyIdentityResolver
-- can route free-text company names (from research.py, press releases, deals)
-- to canonical company_id values.

CREATE TABLE IF NOT EXISTS company_aliases (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id    text NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  alias_name    text NOT NULL,
  alias_type    text NOT NULL CHECK (alias_type IN (
                  'primary',       -- official legal name
                  'ticker',        -- stock ticker (ABBV, MRK, etc.)
                  'abbreviation',  -- common short form (J&J, BI, GSK)
                  'common',        -- informal / press name (AbbVie, Merck)
                  'subsidiary',    -- acquired or operating subsidiary (Genentech, Janssen)
                  'former'         -- historical name (Wyeth, Schering-Plough)
                )),
  source        text DEFAULT 'seed',   -- 'seed' | 'resolver' | 'manual'
  confidence    int  DEFAULT 100 CHECK (confidence BETWEEN 0 AND 100),
  is_primary    bool DEFAULT false,
  created_at    timestamptz DEFAULT now(),
  UNIQUE (company_id, alias_name)
);

CREATE INDEX IF NOT EXISTS idx_company_aliases_name
  ON company_aliases (lower(alias_name));

CREATE INDEX IF NOT EXISTS idx_company_aliases_company
  ON company_aliases (company_id);

-- ── Add missing companies ─────────────────────────────────────────────────────
-- Gilead and BMS are referenced in deals but absent from the companies table.

INSERT INTO companies (id, name, ticker, status) VALUES
  ('gilead', 'Gilead Sciences',       'GILD', 'active'),
  ('bms',    'Bristol Myers Squibb',  'BMY',  'active')
ON CONFLICT (id) DO NOTHING;

-- ── Seed data ─────────────────────────────────────────────────────────────────
-- Insert all known aliases. ON CONFLICT DO NOTHING = safe to re-run.

INSERT INTO company_aliases (company_id, alias_name, alias_type, is_primary) VALUES

-- AbbVie
('abbvie', 'AbbVie',                           'primary',      true),
('abbvie', 'AbbVie Inc.',                       'primary',      false),
('abbvie', 'AbbVie Inc',                        'primary',      false),
('abbvie', 'ABBV',                              'ticker',       false),
('abbvie', 'abbvie',                            'common',       false),

-- Merck
('merck',  'Merck',                             'primary',      true),
('merck',  'Merck & Co.',                       'primary',      false),
('merck',  'Merck & Co',                        'primary',      false),
('merck',  'MRK',                               'ticker',       false),
('merck',  'MSD',                               'abbreviation', false),
('merck',  'Merck Sharp & Dohme',               'common',       false),
('merck',  'Merck Sharp and Dohme',             'common',       false),

-- Roche / Genentech
('roche',  'Roche',                             'primary',      true),
('roche',  'F. Hoffmann-La Roche',              'primary',      false),
('roche',  'F. Hoffmann-La Roche Ltd',          'primary',      false),
('roche',  'RHHBY',                             'ticker',       false),
('roche',  'ROG',                               'ticker',       false),
('roche',  'Genentech',                         'subsidiary',   false),
-- Chugai has its own companies row (id=chugai) — not aliased here

-- Johnson & Johnson / Janssen
('jnj',    'Johnson & Johnson',                 'primary',      true),
('jnj',    'Johnson and Johnson',               'primary',      false),
('jnj',    'J&J',                               'abbreviation', false),
('jnj',    'JNJ',                               'ticker',       false),
('jnj',    'JnJ',                               'abbreviation', false),
('jnj',    'Janssen',                           'subsidiary',   false),
('jnj',    'Janssen Biotech',                   'subsidiary',   false),
('jnj',    'Janssen Pharmaceutica',             'subsidiary',   false),

-- Sanofi
('sanofi', 'Sanofi',                            'primary',      true),
('sanofi', 'SNY',                               'ticker',       false),
('sanofi', 'Sanofi S.A.',                       'primary',      false),
('sanofi', 'Sanofi-Aventis',                    'former',       false),
('sanofi', 'Regeneron / Sanofi',                'common',       false),

-- AstraZeneca
('astrazeneca', 'AstraZeneca',                  'primary',      true),
('astrazeneca', 'AZN',                          'ticker',       false),
('astrazeneca', 'AZ',                           'abbreviation', false),
('astrazeneca', 'AstraZeneca PLC',              'primary',      false),
('astrazeneca', 'Astra Zeneca',                 'common',       false),
('astrazeneca', 'MedImmune',                    'subsidiary',   false),
('astrazeneca', 'Alexion',                      'subsidiary',   false),
('astrazeneca', 'Alexion Pharmaceuticals',      'subsidiary',   false),

-- Regeneron
('regeneron', 'Regeneron',                      'primary',      true),
('regeneron', 'Regeneron Pharmaceuticals',      'primary',      false),
('regeneron', 'REGN',                           'ticker',       false),

-- Pfizer
('pfizer', 'Pfizer',                            'primary',      true),
('pfizer', 'PFE',                               'ticker',       false),
('pfizer', 'Pfizer Inc.',                       'primary',      false),
('pfizer', 'Pfizer Inc',                        'primary',      false),
('pfizer', 'Wyeth',                             'former',       false),

-- Gilead
('gilead', 'Gilead',                            'primary',      true),
('gilead', 'Gilead Sciences',                   'primary',      false),
('gilead', 'Gilead Sciences Inc.',              'primary',      false),
('gilead', 'Gilead Sciences Inc',               'primary',      false),
('gilead', 'GILD',                              'ticker',       false),

-- Novartis
('novartis', 'Novartis',                        'primary',      true),
('novartis', 'NVS',                             'ticker',       false),
('novartis', 'Novartis AG',                     'primary',      false),
('novartis', 'Sandoz',                          'subsidiary',   false),

-- Takeda
('takeda',  'Takeda',                           'primary',      true),
('takeda',  'Takeda Pharmaceutical',            'primary',      false),
('takeda',  'Takeda Pharmaceutical Co.',        'primary',      false),
('takeda',  'TAK',                              'ticker',       false),
('takeda',  'TKPYY',                            'ticker',       false),

-- UCB
('ucb',    'UCB',                               'primary',      true),
('ucb',    'UCB S.A.',                          'primary',      false),
('ucb',    'UCB Pharma',                        'common',       false),

-- Eli Lilly
('lilly',  'Eli Lilly',                         'primary',      true),
('lilly',  'Lilly',                             'common',       false),
('lilly',  'Eli Lilly and Company',             'primary',      false),
('lilly',  'LLY',                               'ticker',       false),

-- Boehringer Ingelheim
('boehringer', 'Boehringer Ingelheim',          'primary',      true),
('boehringer', 'BI',                            'abbreviation', false),
('boehringer', 'Boehringer',                    'common',       false),

-- GSK
('gsk',    'GSK',                               'primary',      true),
('gsk',    'GlaxoSmithKline',                   'primary',      false),
('gsk',    'GlaxoSmithKline PLC',               'primary',      false),
('gsk',    'Glaxo SmithKline',                  'common',       false),

-- Bristol Myers Squibb
('bms',    'Bristol Myers Squibb',              'primary',      true),
('bms',    'Bristol-Myers Squibb',              'primary',      false),
('bms',    'BMS',                               'abbreviation', false),
('bms',    'BMY',                               'ticker',       false),

-- Amgen
('amgen',  'Amgen',                             'primary',      true),
('amgen',  'Amgen Inc.',                        'primary',      false),
('amgen',  'AMGN',                              'ticker',       false),

-- Immunovant
('immunovant', 'Immunovant',                    'primary',      true),
('immunovant', 'IMVT',                          'ticker',       false),
('immunovant', 'Immunovant Inc.',               'primary',      false),

-- argenx
('argenx', 'argenx',                            'primary',      true),
('argenx', 'Argenx',                            'common',       false),
('argenx', 'ARGX',                              'ticker',       false),
('argenx', 'argenx SE',                         'primary',      false)

ON CONFLICT (company_id, alias_name) DO NOTHING;

-- ── Verify ────────────────────────────────────────────────────────────────────
-- After running, check counts:
-- SELECT company_id, count(*) FROM company_aliases GROUP BY company_id ORDER BY company_id;
