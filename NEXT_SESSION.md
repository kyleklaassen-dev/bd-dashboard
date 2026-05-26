# NEXT SESSION — BD Platform

**Last session:** Session 60 (2026-05-26)

**Three tracks completed:**
- **Track A (C7 FcRn):** Infrastructure deployed (flag=false). `_FCRN_NORM` branch + `_runPhase4BFCRNDualRead()` in index.html (commit `4af85431`). riliprubart.mechanism fixed. Awaiting 8-gate browser validation.
- **Track B (Wave 3):** `scripts/wave3_drug_indications_backfill.py` written + committed to Supabase. 49 rows inserted into drug_indications (197 → 246). 35 drugs backfilled from trial_indications data.
- **Track C (drug_competitive_scores):** Full implementation package written: `docs/drug_competitive_scores_ddl.sql` + `scripts/migrate_drug_area_scores.py`. **Table does not exist yet** — DDL must be applied via Supabase SQL Editor before migration can run.

---

## Phase 5 Status — C7 FcRn PENDING ACTIVATION

| Surface | Source | Status |
|---|---|---|
| IBD tab | `drug_indications` | ✅ ACTIVATED |
| TED tab | `drug_indications` | ✅ ACTIVATED |
| Drug Modal | `drug_targets` + `drug_indications` | ✅ ACTIVATED |
| TL1A tab | `drug_targets` | ✅ ACTIVATED |
| TSLP tab | `drug_targets` | ✅ ACTIVATED |
| IL-4Rα tab | `drug_targets` | ✅ ACTIVATED |
| FcRn tab | `drug_targets` | ⏳ **C7 — flag=false, awaiting 8-gate validation** |

`drug_areas` serves NO production biological tab membership queries.

---

## Session 61 — Three Active Work Items

### Item 1 — C7 FcRn: 8-Gate Browser Validation + Activation (HIGHEST PRIORITY)

**Pre-flight metrics (pre-confirmed):**
- legacy=7 (incl. atg-201), norm=7 (incl. riliprubart), overlap=6, scopeDiff=1, adj=6/6=100%
- atg-201 classified: scope_difference (CD19×CD3 bispecific, Watch-tier in legacy; not an FcRn drug)
- riliprubart added: legitimate_target_drug (anti-FcRn mAb, conf=95)
- drugs.mechanism fixed: riliprubart → "Anti-FcRn monoclonal antibody"

**8-gate playbook (run in browser):**

| Gate | What | Expected |
|---|---|---|
| G1 | Legacy FcRn count (drug_areas, area_id='fcrn') | 7 |
| G2 | Normalized FcRn count (drug_targets, target_id='fcrn') | 7 |
| G3 | Key drugs present in normalized | riliprubart ✓ batoclimab ✓ efgartigimod ✓ nipocalimab ✓ orilanolimab ✓ rozanolixizumab ✓ imvt-1402 ✓ |
| G4 | Scope-diff drug absent from normalized | atg-201 ✗ (correct — CD19×CD3, not FcRn) |
| G5 | FcRn tab renders with flag=false (legacy path) | 7 drugs visible, no errors |
| G6 | FcRn tab renders with flag=true (norm path) | 7 drugs visible, no errors |
| G7 | `window.showPhase4Compare()` after loading FcRn tab | `fcrn_target_view → compare_pass_oos_adjusted` |
| G8 | flag=false rollback: FcRn tab shows original 7 drugs | legacy count restored ✓ |

**Activation sequence:**
1. Load live dashboard: `https://kyleklaassen-dev.github.io/bd-dashboard/index.html?bust=<ts>`
2. Confirm `FEATURE_FLAGS.useUnifiedFCRN === false` in console
3. Load FcRn tab → run G1/G2/G3/G4/G5 in browser console
4. `FEATURE_FLAGS.useUnifiedFCRN = true; loadAreaPI('fcrn')` → run G6/G7
5. `FEATURE_FLAGS.useUnifiedFCRN = false; loadAreaPI('fcrn')` → confirm G8
6. **Get advisor go before flipping flag permanently**
7. After approval: set `useUnifiedFCRN: true` in index.html, deploy, confirm live

**Expected post-activation state:**
- FcRn tab shows 7 drugs (same count, different composition vs legacy)
- atg-201 no longer appears in FcRn tab (moved to autoimmune area correctly)
- riliprubart now appears in FcRn tab (new correct addition)
- All 6 feature flags true → drug_areas retired from all normalized biological tab queries

---

### Item 2 — Apply drug_competitive_scores DDL (PREREQUISITE FOR MIGRATION)

The table does not exist yet. Apply via Supabase SQL Editor:

**File:** `docs/drug_competitive_scores_ddl.sql`

Steps:
1. Open Supabase → SQL Editor → New Query
2. Paste full DDL from `docs/drug_competitive_scores_ddl.sql`
3. Run → confirm `drug_competitive_scores` table created
4. Verify in Table Editor: columns context_type, context_id, overlap, confidence_level, UNIQUE constraint

After DDL applied:
```bash
export SUPABASE_URL="https://tghntyo fptv fhmtchwcv.supabase.co".replace(' ','')  # from scripts
export SUPABASE_KEY="<service_role_key from .supabase_service_key>"
python3 scripts/migrate_drug_area_scores.py --audit    # preview only — no writes
python3 scripts/migrate_drug_area_scores.py --dry-run  # confirm row counts
python3 scripts/migrate_drug_area_scores.py --commit   # execute + validate
```

**Expected migration output:**
- Source: drug_area_scores — 212 rows, 11 area_ids
- Target: drug_competitive_scores — ~220+ rows (IBD expansion adds UC+CD rows per drug)
- Spot-checks: risankizumab/indication/cd, mirikizumab/indication/uc, efgartigimod/target/fcrn, dupilumab/target/il4ra
- Deduplication: ted+igf1r merged to single (indication,ted) row per drug

---

### Item 3 — Update memory file: production read layer milestone

After C7 activates, update `memory/project_production_read_layer.md` and `memory/project_meridian_maturity.md` to reflect:
- All 7 biological tabs reading from ontology tables
- drug_areas retired from all normalized biological tab queries
- Next inflection: drug_area_scores = read-only (pending drug_competitive_scores migration + consumer swap)

---

## Phase 6 Workstream Status

| WS | Name | Status |
|---|---|---|
| WS1 | C5+C6+C7 activation | WS1 = C5+C6 ✅ DONE; C7 ⏳ next |
| WS2 | Wave 3 +47 drug-indication pairs | ✅ **DONE Session 60** — 49 rows committed |
| WS3 | drug_competitive_scores | ⏳ **DDL written, table not yet created** |
| WS4 | Strategic views (autoimmune/respiratory → company_strategic_views) | Not started |

**WS3 remaining work (5–8 sessions per design doc):**
1. Apply DDL → run migration → validate (Session 61 if DDL applied this session)
2. Consumer inventory: 8 consumers in index.html need updating
3. Enable parallel write in company_enrichment.py (dual-write window)
4. Sequential consumer migration per `docs/drug_competitive_scores_design.md`
5. drug_area_scores → read-only when all consumers migrated
6. drug_area_scores → retired after 30-day monitoring

---

## Data Layer State After Session 60

```sql
SELECT count(*) FROM drug_indications;            -- expect 246 (+49 Wave 3)
SELECT count(*) FROM drug_targets;                -- expect ~170
SELECT count(*) FROM trial_indications;           -- expect ~540+
SELECT count(*) FROM drug_area_scores;            -- expect 212 (unchanged — legacy source)
-- drug_competitive_scores does NOT exist yet — DDL must be applied
```

---

## Active Constraints

1. **ontology_edges locked** — 25 rows. Do NOT unlock until advisor explicitly approves.
2. **All Phase 5 flags except useUnifiedFCRN = true.** C7 FcRn flag=false. Do not flip without 8-gate sign-off + advisor go.
3. **30-day rule** — Keep legacy code commented (not deleted) for 30 days after any flag flip.
4. **epi-001 held** — 2 rows in backfill_preview as pending_review. Do NOT commit without source evidence.
5. **drug_competitive_scores consumers** — Do NOT update consumers in index.html or enrichment scripts until migration is committed and validated. Dual-write window required before cutover.
6. **area_metadata table** — Formal governance table proposal (advisor-flagged 2026-05-26). Evaluate during WS4 strategic views work; do not block on it.

---

## Validation Checks at Session Start

```sql
-- drug_indications post-Wave 3:
SELECT count(*) FROM drug_indications;            -- expect 246
-- Key backfill verification:
SELECT indication_id FROM drug_indications WHERE drug_id = 'lutikizumab' ORDER BY indication_id;
-- expect: ad, hs, uc (+ any previously existing)
SELECT indication_id FROM drug_indications WHERE drug_id = 'iscalimab' ORDER BY indication_id;
-- expect: gmg, hs, ra, sjogrens, sle (+ any previously existing)
-- drug_competitive_scores check (will error if DDL not applied):
SELECT count(*) FROM drug_competitive_scores;
-- entity_consistency_checks: 0 open high-severity
SELECT entity_id, issue_key, status FROM entity_consistency_checks WHERE status = 'open';
```

---

## Files

- `docs/drug_competitive_scores_ddl.sql` — Apply via Supabase SQL Editor
- `scripts/migrate_drug_area_scores.py` — Run after DDL applied
- `scripts/wave3_drug_indications_backfill.py` — Complete (Wave 3 committed)
- `docs/phase6_master_plan.md` — Full session sequence and dependency map
- `docs/drug_competitive_scores_design.md` — Consumer migration plan, dual-write strategy
