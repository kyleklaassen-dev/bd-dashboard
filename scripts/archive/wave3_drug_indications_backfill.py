#!/usr/bin/env python3
"""
Wave 3 drug_indications backfill
Session 60 — 2026-05-26

Source: trial_indications (joined through trials → drug_id)
Target: drug_indications (49 missing drug-indication pairs)
Method: Insert rows where drug-indication pair exists in trial_indications
        but not in drug_indications.

Usage:
  python3 wave3_drug_indications_backfill.py --dry-run   # Preview all rows
  python3 wave3_drug_indications_backfill.py --commit     # Insert all rows

Environment:
  SUPABASE_URL  — Supabase project URL
  SUPABASE_KEY  — Service role key (for writes)
"""

import os, sys, json, urllib.request, urllib.parse
from collections import defaultdict
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
SB_URL = os.environ.get('SUPABASE_URL', 'https://tghntyo fptv fhmtchwcv.supabase.co'.replace(' ', ''))
SB_KEY = os.environ.get('SUPABASE_KEY', '')

WAVE_DATE = '2026-05-26'
CREATED_BY = f'wave3_backfill/wave3_drug_indications_{WAVE_DATE.replace("-","")}'

# Phase → confidence_score (numeric, 0–100 scale matching existing rows style)
PHASE_CONFIDENCE = {
    'Approved':                92,
    'Phase 4':                 90,
    'Phase 3':                 85,
    'Phase 2/3':               80,
    'Phase 2/Phase 3':         80,
    'Phase 2':                 70,
    'Phase 1/2':               55,
    'Phase 1/Phase 2':         55,
    'Phase 1':                 40,
    'Early Phase 1':           35,
    'Not Applicable':          50,
}
DEFAULT_CONFIDENCE = 55

def conf_to_level(score):
    """Convert numeric confidence to letter grade (matches existing schema)."""
    if score >= 85: return 'A'
    if score >= 70: return 'B'
    return 'C'


def _get_headers(write=False):
    key = SB_KEY if write else os.environ.get('SUPABASE_ANON_KEY', SB_KEY)
    return {
        'apikey': key,
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json',
    }


def fetch(path, write=False):
    url = f'{SB_URL}/rest/v1/{path}'
    req = urllib.request.Request(url, headers=_get_headers(write))
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def compute_gap():
    """Returns list of (drug_id, indication_id) pairs in trial_indications but not drug_indications."""
    print('[Step 1] Fetching trial_indications...')
    ti = fetch('trial_indications?select=trial_id,indication_id&limit=2000')
    ti_by_trial = defaultdict(set)
    for row in ti:
        if row['indication_id']:
            ti_by_trial[row['trial_id']].add(row['indication_id'])
    print(f'  → {len(ti)} rows, {len(ti_by_trial)} unique trials')

    print('[Step 2] Fetching trials (drug_id mapping)...')
    trials = fetch('trials?select=id,drug_id&limit=2000')
    trial_to_drug = {}
    for t in trials:
        if t.get('drug_id'):
            trial_to_drug[t['id']] = t['drug_id']
    print(f'  → {len(trials)} rows')

    print('[Step 3] Fetching valid drug IDs...')
    drugs_all = fetch('drugs?select=id&limit=1000')
    valid_drugs = {r['id'] for r in drugs_all}
    print(f'  → {len(valid_drugs)} valid drug IDs')

    print('[Step 4] Building (drug,indication) pairs from trial_indications...')
    ti_drug_ind = set()
    for trial_id, inds in ti_by_trial.items():
        drug_id = trial_to_drug.get(trial_id)
        if drug_id and drug_id in valid_drugs:
            for ind in inds:
                ti_drug_ind.add((drug_id, ind))
    print(f'  → {len(ti_drug_ind)} unique (drug,indication) pairs in trial_indications')

    print('[Step 5] Fetching existing drug_indications...')
    di = fetch('drug_indications?select=drug_id,indication_id&limit=1000')
    di_pairs = set((r['drug_id'], r['indication_id']) for r in di)
    print(f'  → {len(di_pairs)} existing (drug,indication) pairs')

    gap = sorted(ti_drug_ind - di_pairs)
    print(f'\n[Gap] {len(gap)} pairs to backfill')
    return gap


def get_phase_confidence(drug_id, indication_id, all_trials):
    """Determine best confidence from trial phases for this drug-indication pair."""
    # Filter trials for this drug_id
    drug_trials = [t for t in all_trials if t.get('drug_id') == drug_id]
    if not drug_trials:
        return DEFAULT_CONFIDENCE
    # Fetch trial_indications for these trial IDs to find matching indication
    trial_ids = [t['id'] for t in drug_trials]
    # Use phase from the trials table directly (not per-indication)
    phases = [t.get('phase', '') for t in drug_trials if t.get('phase')]
    if not phases:
        return DEFAULT_CONFIDENCE
    # Take max confidence across all phases for this drug
    return max((PHASE_CONFIDENCE.get(p, DEFAULT_CONFIDENCE) for p in phases), default=DEFAULT_CONFIDENCE)


def build_rows(gap, all_trials):
    """Build drug_indications row dicts for each gap pair."""
    rows = []
    for (drug_id, indication_id) in gap:
        score = get_phase_confidence(drug_id, indication_id, all_trials)
        rows.append({
            'drug_id':          drug_id,
            'indication_id':    indication_id,
            'is_lead_indication': False,       # expansion indication — not primary
            'confidence_score': score,
            'confidence_level': conf_to_level(score),
            'source_type':      'clinicaltrials_api',
            'source_text':      f'Backfilled from trial_indications — {WAVE_DATE}',
            'extraction_method': 'tier3_pattern',
            'review_status':    'sampling_queue',
            'created_by':       CREATED_BY,
        })
    return rows


def dry_run(rows):
    print('\n' + '='*70)
    print(f'DRY RUN — {len(rows)} rows to insert into drug_indications')
    print('='*70)

    by_drug = defaultdict(list)
    for r in rows:
        by_drug[r['drug_id']].append(r['indication_id'])

    print(f'\nBreakdown by drug ({len(by_drug)} drugs):')
    for drug, inds in sorted(by_drug.items(), key=lambda x: -len(x[1])):
        conf_sample = next((r['confidence_score'] for r in rows if r['drug_id'] == drug), 0)
        lvl_sample  = next((r['confidence_level'] for r in rows if r['drug_id'] == drug), '?')
        print(f'  {drug:40s} ({len(inds)}) conf={conf_sample} [{lvl_sample}] → {", ".join(sorted(inds))}')

    print('\nM1: Total gap pairs to commit:', len(rows))
    print('M2: Unique drugs affected:', len(by_drug))
    print('M3: Expected drug_indications post-commit:', 197 + len(rows))
    print('\nSample rows (first 5):')
    for r in rows[:5]:
        print(f'  {r["drug_id"]:35s} → {r["indication_id"]:15s} conf={r["confidence_score"]} level={r["confidence_level"]} lead={r["is_lead_indication"]}')


def commit(rows):
    if not SB_KEY:
        print('ERROR: SUPABASE_KEY not set. Cannot commit.')
        sys.exit(1)

    print(f'\nCommitting {len(rows)} rows to drug_indications...')
    headers = {
        **_get_headers(write=True),
        'Prefer': 'resolution=ignore-duplicates,return=representation',
    }

    inserted = 0
    skipped  = 0
    BATCH    = 50

    for i in range(0, len(rows), BATCH):
        batch = rows[i:i+BATCH]
        payload = json.dumps(batch).encode()
        url = f'{SB_URL}/rest/v1/drug_indications'
        req = urllib.request.Request(url, data=payload, headers=headers, method='POST')
        try:
            with urllib.request.urlopen(req) as r:
                result = json.loads(r.read())
                n = len(result) if isinstance(result, list) else 0
                inserted += n
                skipped  += len(batch) - n
                print(f'  Batch {i//BATCH+1}: inserted={n} skipped={len(batch)-n}')
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            print(f'  ERROR batch {i//BATCH+1}: {e.code} {body[:200]}')

    print(f'\nCommit complete: {inserted} inserted, {skipped} skipped (duplicates)')
    return inserted


def validate(expected_count):
    """Post-commit validation."""
    print('\n[Validation]')
    di = fetch('drug_indications?select=drug_id,indication_id&limit=1000')
    actual = len(di)
    print(f'  drug_indications row count: {actual} (expected ~{expected_count})')

    # Check key drugs
    for drug_id in ['iscalimab', 'lutikizumab', 'imvt-1402', 'astegolimab']:
        drug_rows = [r for r in di if r['drug_id'] == drug_id]
        print(f'  {drug_id}: {len(drug_rows)} indication(s) → {", ".join(sorted(r["indication_id"] for r in drug_rows))}')


def main():
    mode = '--dry-run'
    if len(sys.argv) > 1:
        mode = sys.argv[1]

    print(f'Wave 3 drug_indications backfill — {WAVE_DATE}')
    print(f'Mode: {mode}\n')

    gap = compute_gap()

    print('\n[Fetching trial data for confidence scores...]')
    all_trials = fetch('trials?select=id,drug_id,phase&limit=2000')

    rows = build_rows(gap, all_trials)

    if mode == '--dry-run':
        dry_run(rows)
    elif mode == '--commit':
        dry_run(rows)
        print('\nProceeding with commit...')
        inserted = commit(rows)
        validate(197 + inserted)
    else:
        print(f'Unknown mode: {mode}. Use --dry-run or --commit')
        sys.exit(1)


if __name__ == '__main__':
    main()
