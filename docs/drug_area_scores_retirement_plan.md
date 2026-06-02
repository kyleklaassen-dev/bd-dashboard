# drug_area_scores Retirement Plan
<!-- created: 2026-06-02 | author: cowork autonomous -->

## Timeline
- Monitoring window started: ~2026-05-27 (Option C migration)
- Window closes: ~2026-06-26 (30 days)
- Retire after: 2026-06-27

## Current State
- `drug_area_scores`: 210 rows, 89 read sites in index.html
- All biological data migrated to `drug_competitive_scores` (Session 64 / Phase 5)
- Dashboard reads migrated: DCS is primary source via `_makeAreaPI`
- Remaining reads: mostly legacy fallback paths + validation test (spy072/ibd)

## What Still Reads drug_area_scores

### index.html (89 occurrences)
Key remaining reads:
1. **Line 4051**: Health check count query — just a monitoring stat display
2. **Line 14794**: C1 legacy fallback path inside `_makeAreaPI` (condition: useUnified flag NOT set)
3. **Line 16062**: Comment-only references — no actual reads
4. **Lines 15309, 15992, 15998**: Legacy source references in migration comments

Since all 7 feature flags (C1–C7) are set to TRUE in production, the legacy fallback paths at line 14794 are NEVER executed. The only live read is the health check count on line 4051.

### validate_ground_truth.py
1. `drug_area_score_check` test type — queries drug_area_scores for spy072/ibd (1 failing test)

## Retirement Steps

### Step 1: Code Cleanup (do on June 27)
In `index.html`:
- Remove the `drug_area_scores` count query on line 4051
- Remove the display div referencing `drug_area_scores` (line 4093)  
- Keep the migration comments for documentation
- The C1 flag condition at line 14794 will never be reached with flag=true, but can leave as dead code

In `scripts/validate_ground_truth.py`:
- Remove or mark the `drug_area_score_check` test type as retired
- Or update it to check drug_competitive_scores instead

### Step 2: Table Retirement SQL (run after code cleanup)
```sql
-- Verify no active reads before dropping
-- Then:
ALTER TABLE drug_area_scores DISABLE TRIGGER ALL;
DROP TABLE IF EXISTS drug_area_scores CASCADE;
```

### Step 3: area_metadata update
```sql
UPDATE area_metadata SET retirement_status = 'retired', updated_at = NOW()
WHERE retirement_status = 'monitoring';
```

## Risk Assessment
- **Low risk**: All 7 feature flags are true, DCS is the live source
- **Zero dashboard impact**: C1 fallback paths never executed with flags=true
- **1 test to update**: spy072/ibd DAS check — convert to DCS check or delete
- **Zero data loss**: All competitive_relevance data is in drug_competitive_scores

## WS4 (Post-Retirement)
After drug_area_scores is retired, WS4 can complete the area_metadata migration:
- Move `autoimmune` and `respiratory` strategic views to `company_strategic_views`
- Move `tcell` platform view to `company_platform_views`
- Formalize area_metadata as the canonical governance source

