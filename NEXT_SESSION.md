# NEXT SESSION — BD Platform Intelligence Quality Session

**Written:** 2026-05-22  
**Session focus:** Intelligence Quality Framework — source verification, overlap classification, data audit

---

## What Was Accomplished This Session

### ✅ Task 1: TL1A Overlap Validation (50/50 correct)
- Validated all 50 TL1A drugs across `drugs` and `drug_area_scores` tables
- Fixed golimumab: `drug_area_scores.overlap` was Same-Space → corrected to Watch (TNF inhibitor)

### ✅ Task 2: 4-Tier Prompt Verification (all checks pass)
- Enrichment prompt renders DIRECT / ADJACENT / SAME-SPACE / WATCH correctly from DB anchor
- `ailux_positions` ibd row updated with `same_space_criteria` + `same_space_examples` columns

### ✅ Task 3: Source Verification Framework
- Added `drugs.source_url` + `drug_area_scores.source_url` / `confidence_level` columns to schema
- Backfilled CT.gov URLs for 18 trial-verified drugs; company IR URLs for 22 more
- `source_url` now REQUIRED in enrichment prompt's `drug_updates` JSON schema
- Coverage: **40/50 TL1A drugs (80%)** have source_url; **100%** have confidence_level

### ✅ Task 4: Risk/BD Angle Framework
- `key_risk`, `why_it_matters`, `bd_summary` existed and were already populated
- Filled bd_summary for jnj and roivant (last 2 gaps)
- key_risk / why_it_matters / vs_ailux now marked REQUIRED in enrichment prompt
- **Result: 25/25 TL1A companies have risk + BD angle content**

### ✅ Task 5: Enrichment Batch Runner Created
- `scripts/run_tl1a_enrichment.sh` runs all 25 TL1A companies in priority order
- Logs to `logs/tl1a_enrichment_YYYYMMDD_HHMM.log`
- **Run it:** `cd ~/Documents/Claude/Projects/BD\ Platform && bash scripts/run_tl1a_enrichment.sh`
- Time estimate: ~2-3 hours for all 25 companies

---

## Current TL1A State (2026-05-22)

| Metric | Before Session | After Session |
|--------|---------------|---------------|
| Drugs with correct overlap | ~35/50 | **50/50** |
| Drugs with target | 38/50 | **50/50** |
| Drugs with source_url | 0/50 | **40/50 (80%)** |
| Drugs with confidence_level | 0/50 | **50/50 (100%)** |
| Companies with bd_summary | 23/25 | **25/25** |
| Companies with key_risk | 25/25 | 25/25 |
| Deals with source_url | ~94% | 94% |
| Catalysts with source_url | ~15% | 15% ← main gap |

**Tier breakdown (50 drugs):** Direct=33, Adjacent=10, Same-Space=1, Watch=6

---

## Top Priority Next Session

### 🔴 1. Run Full TL1A Enrichment
```bash
cd ~/Documents/Claude/Projects/BD\ Platform
bash scripts/run_tl1a_enrichment.sh
```
Companies needing most work (score ≤ 75): jnj, celgene, roivant, xencor-942, xencor-412, prometheus, teva

### 🔴 2. Catalyst Deduplication
**Problem:** 394 catalyst rows for tl1a (vs ~50 curated in legacy). Only 15% have source_url.  
Same events appear 2-4x because enrichment inserts without dedup checks.  
**Ask Claude:** "Deduplicate the tl1a catalysts table — same company + label + date = keep most recent"

### 🟡 3. Intelligence Audit Dashboard
Build a live quality-control view (Cowork artifact) showing:
- Drugs with null target / missing overlap / no source_url
- Direct competitors mis-classified as Watch
- Approved drugs with no key_data
- Catalyst duplicates
- Company profiles missing bd_summary  

**Ask Claude:** "Create a data quality audit artifact for the BD platform connected to Supabase"

### 🟡 4. TL1A Learning Report
Classify each legacy↔framework discrepancy as A/B/C/D:
- A = Legacy correct, framework missed → what prompt/rule change would have caught it?
- B = Framework correct, legacy stale  
- C = Classification disagreement
- D = Neither verified  

**Ask Claude:** "Generate the TL1A learning report from TL1A_Parity_Audit.md"

---

## Schema Changes Applied This Session

| Table | Added Columns |
|-------|---------------|
| `ailux_positions` | `same_space_criteria` (text), `same_space_examples` (text) |
| `drugs` | `source_url` (text) |
| `drug_area_scores` | `source_url` (text), `confidence_level` (text) |

---

## Deployed to GitHub
- `scripts/company_enrichment.py` → commit `68b8b76a`
- `update_log.md` → commit `e9dd6d63`

Files needing deploy next session:
- `scripts/run_tl1a_enrichment.sh` (new file)
