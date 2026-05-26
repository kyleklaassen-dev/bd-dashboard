# NEXT SESSION — BD Platform

**Last session:** Session 63 (2026-05-26)

---

## ✅ MILESTONE CLOSED: Legacy Read Layer Elimination (Session 61)

All 6 feature flags permanently true. drug_areas no longer serves any biological dashboard tab.

---

## Phase 6 Workstream Status

| WS | Name | Status |
|---|---|---|
| WS1 | C5+C6+C7 activation | ✅ **COMPLETE** |
| WS2 | Wave 3 drug-indication pairs | ✅ **COMPLETE** — 49 rows, quality validated |
| WS3 | drug_competitive_scores | ✅ **Table created + 234 rows migrated** |
| WS3 (next) | C1/C2 drug modal migration | ⏳ **PLAN COMPLETE** — ready to implement |
| WS4 | Strategic views (autoimmune/respiratory/tcell) | Not started |

---

## Session 64 Priority: C1/C2 Implementation

### Context

C1/C2 planning is complete. Full plan in `docs/drug_competitive_scores_c1c2_plan.md`.

Pre-implementation audit complete:
- **strategic_role** — SAFE to omit. Column does not exist in drug_area_scores. All display code conditionally null. No compatibility work needed.
- **_confBadge** — P0 blocker identified. Must update before deploying C1/C2.

### Implementation Sequence

1. **`_AREA_LABEL` pre-flight** — locate definition; confirm or add `uc`/`cd`/`ted` entries
2. **`_confBadge` fix (P0 blocker)** — update to handle A/B/C + legacy strings simultaneously; add `_CONF_LABEL` map for tooltip
3. **`_CEM_AMAP` update** — add `uc:'UC'`, `cd:'CD'`, `ted:'TED'`
4. **C1 fetch** — swap `drug_area_scores` → `drug_competitive_scores`; update SELECT (remove strategic_role; add context_type,context_id,vs_ailux); rekey scoreMap on `context_id`; reshape areas[] (expose context_id as area_id)
5. **C2 fetch** — same changes for name-search fallback path
6. **Dual-read harness** — `window.__MERIDIAN_COMPETITIVE_SCORE_COMPARE__` — insert after new fetch resolves
7. **Deploy** — single commit: `feat: C1/C2 drug modal migrated to drug_competitive_scores with dual-read harness`
8. **Validate** — 10-drug validation set in browser console

### 10-Drug Validation Set

sim0709, batoclimab, dupilumab, risankizumab, efgartigimod, riliprubart, epi-001, lm-302, spy072, upadacitinib

Expected patterns:
- Non-IBD drugs: `old_only=[]`, `new_only=[]`, zero field mismatches
- IBD drugs: `old_only=['ibd']`, `new_only=['uc','cd']` — expected expansion, not regression
- epi-001, spy072: `old_only=[]`, `new_only=[]` — both have `ibd` fallback

### Open Items from WS3 Migration

**3 indication/ibd fallback drugs** — IBD drugs with no UC or CD entries in drug_indications:
- `epi-001` — held in backfill_preview — do NOT touch without source evidence
- `sim0500` — should have UC/CD entries (backfill in Wave 4)
- `spy072` — should have UC/CD entries (backfill in Wave 4)

Action for Wave 4: backfill sim0500 and spy072 into drug_indications for UC and/or CD.

---

## Active Constraints

1. **ontology_edges locked** — 25 rows. Do NOT unlock without advisor approval.
2. **30-day rule** — Keep legacy flag branches until monitoring window closes.
3. **drug_area_scores** — Do NOT delete. Legacy provenance for 212 rows.
4. **drug_areas** — Do NOT delete. Serves autoimmune/respiratory/tcell.
5. **C3 (PI tab scoreRows)** — Do NOT migrate yet. Behavioral consumer, HIGH risk.
6. **C4–C8 (Phase 4B dual-read)** — NEVER migrate to drug_competitive_scores. They are permanent legacy readers by design.
7. **company_enrichment.py** — Do NOT change write path yet. C11 parallel-write must wait until C1/C2 is stable ≥7 days.
8. **epi-001** — Do NOT commit to drug_indications without source evidence.

---

## Monitoring Windows (30-day rule)

| Candidate | 30-day window closes |
|---|---|
| C1/C2/C3 (IBD/TED/Modal) | ~2026-06-24 |
| C4 (TL1A) | ~2026-06-24 |
| C5/C6 (Atopy) | ~2026-06-25 |
| C7 (FcRn) | ~2026-06-25 |

---

## Validation Checks at Session Start

```sql
-- Standing rule: check for validation failures first
SELECT entity_id, check_type, check_status, failure_reason
FROM drug_validation_results
WHERE check_status IN ('fail','warning','needs_review')
ORDER BY check_status, entity_id LIMIT 20;

-- Open ECC items:
SELECT entity_id, issue_key, status FROM entity_consistency_checks WHERE status = 'open';

-- Confirm row counts:
SELECT count(*) FROM drug_indications;            -- expect 246
SELECT count(*) FROM drug_competitive_scores;     -- expect 234
SELECT count(*) FROM drug_area_scores;            -- expect 212 (legacy — do not delete)
SELECT count(*) FROM area_metadata;               -- expect 11
-- 3 indication/ibd fallback rows:
SELECT drug_id FROM drug_competitive_scores WHERE context_id = 'ibd';
-- expect: epi-001, sim0500, spy072
```

---

## Files

- `docs/drug_competitive_scores_c1c2_plan.md` — **C1/C2 implementation plan (Session 63)** — start here
- `docs/drug_competitive_scores_consumer_inventory.md` — Full consumer inventory + classifications
- `docs/drug_competitive_scores_design.md` — Consumer migration architecture
- `docs/drug_competitive_scores_migration_report.md` — Full migration audit (Session 62)
- `scripts/migrate_drug_area_scores.py` — Migration script (committed, idempotent)
- `docs/phase6_master_plan.md` — Full session sequence and dependency map
