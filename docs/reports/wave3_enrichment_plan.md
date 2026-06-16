# Wave 3 Drug-Indication Enrichment Plan
**Written:** Session 58 — 2026-05-26  
**Status:** Implementation plan — ready for execution Session 59  
**Source of truth:** `trial_indications` table (301 rows, more complete than drug_indications)  
**Goal:** Close ECC-7 gaps — backfill 47 drug-indication pairs across 34 drugs to drug_indications

---

## Background

The ECC-7 consistency sweep revealed a systematic undercount in `drug_indications`. The table currently covers 197 rows (primarily first-line or approved indications). However, `trial_indications` — which ingests directly from CT.gov — captures 301 rows including Phase 2 expansions, combination programs, and secondary indications.

The gap: **47 unique drug-indication pairs in trial_indications but not in drug_indications**, spanning 34 drugs. These represent real clinical programs invisible to ontology-based dashboard queries.

**Why this matters:** The IBD tab (C1), TED tab (C2), and any future ontology-derived query reads from `drug_indications`. Drugs not in drug_indications are invisible to these queries regardless of how many trials exist. Wave 3 closes that invisibility gap.

---

## Priority Tiers

### Tier 1 — High-Volume Gaps (5+ missing pairs per drug)

| Drug | Target | Stage | Missing Indications |
|------|--------|-------|---------------------|
| `iscalimab` | CD40 | Phase 2 | gmg, hs, ra, sjogrens, sle |

**iscalimab note:** This drug has the broadest cross-indication program of any drug with gaps. It's in TED (already in drug_indications via iscalimab → ted) but missing 5 autoimmune programs.

---

### Tier 2 — Moderate-Volume Gaps (2–4 missing pairs per drug)

| Drug | Target | Stage | Missing Indications | Count |
|------|--------|-------|---------------------|-------|
| `lutikizumab` | IL-1α/β | Phase 3 | ad, hs, uc | 3 |
| `imvt-1402` | FcRn | Phase 3 | ra, ted | 2 |
| `astegolimab` | IL-33 | Phase 3 | ad, asthma | 2 |
| `infliximab` | TNFα | Approved | cd, ra | 2 |
| `ianalumab` | BAFF-R | Phase 3 | ra, sjogrens | 2 |
| `afimkibart` | TL1A | Phase 3 | ad, cd | 2 |
| `zumilokibart` | IL-13 | Phase 2 | asthma, crswnp | 2 |
| `itepekimab` | IL-33 | Phase 3 | asthma, crswnp | 2 |

---

### Tier 3 — Single Gaps (1 missing pair per drug)

25 additional drugs with one missing indication each. Full list from ECC-7:

| Drug | Missing Indication | Primary Target |
|------|--------------------|---------------|
| `tezepelumab` | crswnp | TSLP |
| `verekitug` | crswnp | TSLP |
| `omalizumab` | crswnp | IgE |
| `tralokinumab` | crswnp | IL-13 |
| `rademikibart` | crswnp | IL-33 |
| `win378` | crswnp | — |
| `bimekizumab` | hs | IL-17A/F |
| `sonelokimab` | hs | IL-17A/F |
| `secukinumab` | hs | IL-17A |
| `abbv-668` | hs | TSLP |
| `cnd261` | ra | — |
| `ixekizumab` | ra | IL-17A |
| `golimumab` | ra | TNFα |
| `upadacitinib` | ra | JAK1 |
| `rocatinlimab` | asthma | OX40L |
| `apg777` | ad | — |
| `epi-001` | uc | — |
| `sim0500` | cd | — |
| `batoclimab` | gmg | FcRn |
| `efgartigimod` | gmg | FcRn |
| `rozanolixizumab` | gmg | FcRn |
| `nipocalimab` | gmg | FcRn |
| `mim23` | gmg | FcRn |
| `yb-101` | ted | TSHR |
| `apg333` | asthma | TSLP (correcting target per ECC-1) |

---

## Indication Themes — Systematic Backfill

Some indications have systematic gaps across multiple drugs, suggesting a Wave 3 pattern:

| Indication | Total Gap Count | Key Drugs Needing Backfill |
|------------|----------------|---------------------------|
| `crswnp` | 8 drugs | tezepelumab, itepekimab, zumilokibart, verekitug, omalizumab, tralokinumab, rademikibart, win378 |
| `hs` | 6 drugs | iscalimab, bimekizumab, sonelokimab, lutikizumab, secukinumab, abbv-668 |
| `ra` | 8 drugs | iscalimab, infliximab, ianalumab, cnd261, ixekizumab, golimumab, upadacitinib, imvt-1402 |
| `asthma` | 6 drugs | astegolimab, itepekimab, zumilokibart, rocatinlimab, win378, tralokinumab |
| `ad` | 4 drugs | lutikizumab, astegolimab, afimkibart, apg777 |
| `gmg` | 5 drugs | iscalimab, batoclimab, efgartigimod, rozanolixizumab, nipocalimab, mim23 |
| `sle` | 1 drug | iscalimab |
| `sjogrens` | 2 drugs | iscalimab, ianalumab |
| `cd` | 2 drugs | afimkibart, infliximab, sim0500 |
| `uc` | 2 drugs | lutikizumab, epi-001 |
| `ted` | 2 drugs | imvt-1402, yb-101 |

---

## Backfill Script Design

**File:** `scripts/wave3_drug_indications_backfill.py`

### Strategy

Use `trial_indications` as the source of truth. For each drug-indication pair in trial_indications but not drug_indications:
1. Look up the drug's primary target from `drugs.target`
2. Verify the indication exists in `indications` reference table
3. Compute `primary_indication` boolean (False for expansion indications — primary is already set)
4. Set `confidence_score` from trial count / trial phase
5. Insert with `source='trial_indications'` to track Wave 3 origin

### Confidence Score Logic

| Basis | confidence_score |
|-------|-----------------|
| Phase 3 or Approved trial | 0.85 |
| Phase 2 trial | 0.70 |
| Phase 1/2 trial | 0.55 |
| Phase 1 only | 0.40 |
| Multiple phases (take highest) | use max phase rule |

### Script Pseudocode

```python
"""
Wave 3 drug_indications backfill
Source: trial_indications
Target: drug_indications (add missing drug-indication pairs)
"""

import os
import json
import requests
from datetime import datetime

SB_URL = os.environ['SUPABASE_URL']
SB_KEY = os.environ['SUPABASE_SERVICE_KEY']
HEADERS = {'apikey': SB_KEY, 'Authorization': f'Bearer {SB_KEY}', 'Content-Type': 'application/json'}

PHASE_CONFIDENCE = {
    'Phase 3': 0.85, 'Phase 2/3': 0.80, 'Approved': 0.90,
    'Phase 2': 0.70, 'Phase 1/2': 0.55, 'Phase 1': 0.40
}

def get_gap_pairs():
    """
    Returns list of (drug_id, indication_id) pairs in trial_indications but not drug_indications.
    """
    # Query trial_indications: distinct drug_id + indication_id pairs
    ti_resp = requests.get(
        f'{SB_URL}/rest/v1/trial_indications',
        headers=HEADERS,
        params={'select': 'drug_id,indication_id', 'limit': 1000}
    )
    ti_pairs = {(r['drug_id'], r['indication_id']) for r in ti_resp.json()}
    
    # Query drug_indications: existing pairs
    di_resp = requests.get(
        f'{SB_URL}/rest/v1/drug_indications',
        headers=HEADERS,
        params={'select': 'drug_id,indication_id', 'limit': 1000}
    )
    di_pairs = {(r['drug_id'], r['indication_id']) for r in di_resp.json()}
    
    gaps = ti_pairs - di_pairs
    return list(gaps)

def compute_confidence(drug_id, indication_id):
    """
    Determine confidence_score from trial phases for this drug-indication pair.
    """
    resp = requests.get(
        f'{SB_URL}/rest/v1/trial_indications',
        headers=HEADERS,
        params={
            'drug_id': f'eq.{drug_id}',
            'indication_id': f'eq.{indication_id}',
            'select': 'phase'
        }
    )
    phases = [r.get('phase', '') for r in resp.json()]
    return max((PHASE_CONFIDENCE.get(p, 0.40) for p in phases), default=0.40)

def backfill_gaps(gaps, dry_run=True):
    """
    Insert drug_indications rows for all gap pairs.
    """
    rows = []
    for (drug_id, indication_id) in gaps:
        confidence = compute_confidence(drug_id, indication_id)
        rows.append({
            'drug_id': drug_id,
            'indication_id': indication_id,
            'primary_indication': False,  # expansion indication
            'confidence_score': confidence,
            'source': 'trial_indications',
            'notes': f'Wave 3 backfill — 2026-05-26'
        })
    
    if dry_run:
        print(f'[DRY RUN] Would insert {len(rows)} rows')
        for r in rows[:10]:
            print(f"  {r['drug_id']} → {r['indication_id']} ({r['confidence_score']})")
        return rows
    
    # Batch insert (100 rows per request)
    for i in range(0, len(rows), 100):
        batch = rows[i:i+100]
        resp = requests.post(
            f'{SB_URL}/rest/v1/drug_indications',
            headers={**HEADERS, 'Prefer': 'resolution=ignore-duplicates'},
            json=batch
        )
        if resp.status_code not in (200, 201):
            print(f'ERROR batch {i//100}: {resp.status_code} {resp.text}')
        else:
            print(f'Inserted batch {i//100+1} ({len(batch)} rows)')
    
    return rows

if __name__ == '__main__':
    gaps = get_gap_pairs()
    print(f'Found {len(gaps)} gap pairs')
    backfill_gaps(gaps, dry_run=False)
```

---

## Pre-flight Checklist

Before running the backfill script:

1. **Verify indication_id values exist** in `indications` reference table:
   - `crswnp`, `hs`, `ra`, `asthma`, `sjogrens`, `sle`, `gmg`, `ad`, `uc`, `cd`, `ted`
   - Run: `GET /rest/v1/indications?id=in.(crswnp,hs,ra,asthma,sjogrens,sle,gmg,ad,uc,cd,ted)&select=id,name`
   - Expected: all 11 return rows. If any missing → add to `indications` table first.

2. **Verify drug_id values exist** in `drugs` table:
   - Cross-check Tier 1+2 drugs: iscalimab, lutikizumab, imvt-1402, astegolimab, infliximab, ianalumab, afimkibart, zumilokibart, itepekimab
   - Run: `GET /rest/v1/drugs?id=in.(iscalimab,lutikizumab,imvt-1402,...)&select=id,name`

3. **Apply P0 ECC-1 fixes first:**
   - `PATCH /rest/v1/drugs?id=eq.apg333` body: `{"target": "TSLP"}`
   - `PATCH /rest/v1/drugs?id=eq.rocatinlimab` body: `{"target": "OX40L"}`

4. **Run dry-run first:** `dry_run=True` to audit the 47 rows before committing

---

## Post-Backfill Validation

After running the script:

1. **Row count check:** `drug_indications` should have ~244 rows (+47)
2. **Re-run ECC-7 query:** `trial_indications gaps` should return 0 rows
3. **Spot-check 5 drugs:** Query drug_indications for iscalimab, lutikizumab, itepekimab — verify new rows appear with correct indication_ids
4. **Dashboard smoke test:** Load IBD tab, TED tab — verify drug lists unchanged (new rows are expansion indications; `primary_indication=false` won't affect primary queries)
5. **Update ontology_consistency_sweep.md** ECC-7 section to reflect Wave 3 complete

---

## Wave 3 Deliverables

| Deliverable | Status |
|------------|--------|
| `scripts/wave3_drug_indications_backfill.py` | Not yet written |
| P0 ECC-1 fixes (apg333, rocatinlimab) | Not yet applied |
| 47 new `drug_indications` rows | Not yet committed |
| 2 `drugs.target` corrections | Not yet applied |
| ontology_consistency_sweep.md — ECC-7 updated | Not yet done |

**Target session:** Session 59 (can be done while GitHub Pages degraded — Supabase writes only)

---

## Estimated Row Counts Post-Wave 3

| Table | Current | After Wave 3 |
|-------|---------|-------------|
| drug_indications | 197 rows | ~244 rows (+47) |
| drugs.target corrections | 2 stale | 0 stale |
| trial_indications gaps | 47 pairs | 0 pairs |
