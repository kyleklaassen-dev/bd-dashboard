-- Migration v28 — ownership_edges.deal_id FK
-- Applied: 2026-05-24 (Phase 3 of relationship-completeness sprint)
-- Purpose: Link ownership_edges rows to the deals table so every acquisition/
--          license edge can trace back to its originating deal record.
--
-- Design notes:
--   • deal_id is nullable (not all edges come from a tracked deal)
--   • ON DELETE SET NULL — edge survives even if deal record is removed
--   • Backfilled for the three known acquisition transactions:
--       deal 19  → UCB/Candid acquisition (7 edges)
--       deal 167 → UCB/Antengene license   (3 edges)
--       deal 28  → Merck/Prometheus acquisition (3 edges)
--
-- After this migration, Transaction Intake (company_enrichment.py) should
-- write deal_id onto any ownership_edge it creates so the link is automatic
-- going forward.  See TRANSACTION_PIPELINE_EXPANSION block in that script.

ALTER TABLE ownership_edges
    ADD COLUMN IF NOT EXISTS deal_id INTEGER REFERENCES deals(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_ownership_edges_deal_id
    ON ownership_edges(deal_id)
    WHERE deal_id IS NOT NULL;

-- Backfill: UCB/Candid acquisition (deals.id = 19)
UPDATE ownership_edges SET deal_id = 19
WHERE id IN (
    'f19c4cf0-cfb6-49a9-98d2-3815bca85a4c',  -- candid ACQUIRED→ ucb
    'e7d36da8-adfd-495e-9bc9-6c94def9bc94',  -- cizutamig ORIGINATED_BY→ candid
    'dce743d6-73a9-49d6-978d-049ab9678f3a',  -- cizutamig CONTROLLED_BY→ ucb
    '0994ed45-81c2-496b-88c8-5be7a200ad6c',  -- cnd319 ORIGINATED_BY→ candid
    'd355433e-f5e2-4c20-b2cf-14e91633858a',  -- cnd319 CONTROLLED_BY→ ucb
    'dd41116e-1325-4b49-bb9b-25f8713068d6',  -- cnd460 ORIGINATED_BY→ candid
    'd4aa04b7-a707-433d-83c6-5a05613b0351'   -- cnd460 CONTROLLED_BY→ ucb
);

-- Backfill: UCB/Antengene license (deals.id = 167)
UPDATE ownership_edges SET deal_id = 167
WHERE id IN (
    '5182db64-a7e2-4a88-b223-a39f6e792c40',  -- atg-201 LICENSED_IN→ ucb
    'd7ab2fb5-3701-4126-b721-6d411f363b97',  -- atg-201 ORIGINATED_BY→ antengene
    '00977654-baac-404d-9208-74b8c30281a5'   -- atg-201 LICENSED_FROM→ antengene
);

-- Backfill: Merck/Prometheus acquisition (deals.id = 28)
UPDATE ownership_edges SET deal_id = 28
WHERE id IN (
    '98a364e7-8969-40b4-b81c-baf604979ed6',  -- prometheus ACQUIRED→ merck
    '8e5b661c-9afb-4ed9-b153-d4bcb0b534b3',  -- tulisokibart ORIGINATED_BY→ prometheus
    'cca226e1-a45c-4a63-89c0-29c23625707b'   -- tulisokibart CONTROLLED_BY→ merck
);
