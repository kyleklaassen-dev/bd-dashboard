#!/usr/bin/env python3
"""
migrate_drug_area_scores.py
Session 60 — 2026-05-26

Migrates drug_area_scores (212 rows, legacy area_id) →
         drug_competitive_scores (context_type + context_id, normalized)

Three migration modes:
  --audit     Print pre-migration analysis only (no writes)
  --dry-run   Show all rows that would be inserted (no writes)
  --commit    Execute migration + run post-migration validation

Prerequisites:
  1. Apply migrations/_archive/from-docs/drug_competitive_scores_ddl.sql via Supabase SQL Editor
  2. Set SUPABASE_KEY to service role key (writes required)

Environment:
  SUPABASE_URL  — Supabase project URL
  SUPABASE_KEY  — Service role key
"""

import os, sys, json, urllib.request
from collections import defaultdict
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
SB_URL  = os.environ.get('SUPABASE_URL', 'https://tghntyo fptv fhmtchwcv.supabase.co'.replace(' ',''))
SB_KEY  = os.environ.get('SUPABASE_KEY', '')
ANON_KEY = os.environ.get('SUPABASE_ANON_KEY', SB_KEY)
MIGRATION_ID = f"migration-{datetime.utcnow().strftime('%Y%m%d')}"

# ── area_id → (context_type, context_id) mapping ──────────────────────────────
# Note: ibd handled separately (per-drug UC/CD expansion)
# Note: ted and igf1r both map to indication/ted — deduplicated on UNIQUE conflict
# Note: atopy expands to il4ra and/or tslp based on drug_targets
AREA_CONTEXT_MAP = {
    'tl1a':        [('target',         'tl1a')],
    'il4ra':       [('target',         'il4ra')],
    'tslp':        [('target',         'tslp')],
    'fcrn':        [('target',         'fcrn')],
    'igf1r':       [('indication',     'ted')],
    'ted':         [('indication',     'ted')],        # same target as igf1r — UNIQUE deduplication handles
    'autoimmune':  [('strategic_view', 'autoimmune')],
    'respiratory': [('strategic_view', 'respiratory')],
    'tcell':       [('platform_view',  'tcell')],
    # 'ibd'   → handled by _expand_ibd()
    # 'atopy' → handled by _expand_atopy()
}

# confidence_level priority for deduplication (lower = better)
CONF_PRIORITY = {'A': 0, 'B': 1, 'C': 2, 'inferred': 3}


def _fetch(path, write_key=False):
    key = SB_KEY if write_key else ANON_KEY
    req = urllib.request.Request(
        f'{SB_URL}/rest/v1/{path}',
        headers={'apikey': key, 'Authorization': f'Bearer {key}'}
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def _post(path, rows):
    if not SB_KEY:
        raise RuntimeError('SUPABASE_KEY not set — cannot commit')
    headers = {
        'apikey':        SB_KEY,
        'Authorization': f'Bearer {SB_KEY}',
        'Content-Type':  'application/json',
        'Prefer':        'resolution=merge-duplicates,return=representation',
    }
    payload = json.dumps(rows).encode()
    req = urllib.request.Request(f'{SB_URL}/rest/v1/{path}', data=payload, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f'POST {path} failed {e.code}: {body[:300]}')


def load_source_data():
    """Fetch all data needed for migration."""
    print('[Loading] drug_area_scores...')
    scores = _fetch('drug_area_scores?select=drug_id,area_id,overlap,cls,overlap_rationale,vs_ailux_positioning,confidence_level,source_url&limit=500')
    print(f'  {len(scores)} rows')

    print('[Loading] drug_indications (for IBD UC/CD classification)...')
    di = _fetch('drug_indications?select=drug_id,indication_id&indication_id=in.(uc,cd)&limit=1000')
    print(f'  {len(di)} UC/CD rows')

    print('[Loading] drug_targets (for atopy IL-4Rα/TSLP expansion)...')
    dt = _fetch('drug_targets?select=drug_id,target_id&target_id=in.(il4ra,tslp,tslpr)&limit=500')
    print(f'  {len(dt)} atopy target rows')

    return scores, di, dt


def _build_ibd_drug_contexts(ibd_drugs, di_rows):
    """
    For each IBD drug, determine which indication contexts to emit.
    Logic:
      - has uc ∧ cd → emit both ('indication','uc') and ('indication','cd')
      - has uc only → emit ('indication','uc')
      - has cd only → emit ('indication','cd')
      - neither     → emit ('indication','ibd') as legacy fallback
    """
    drug_inds = defaultdict(set)
    for r in di_rows:
        if r['drug_id'] in ibd_drugs:
            drug_inds[r['drug_id']].add(r['indication_id'])

    result = {}
    for drug in ibd_drugs:
        inds = drug_inds.get(drug, set())
        has_uc = 'uc' in inds
        has_cd = 'cd' in inds
        if has_uc and has_cd:
            result[drug] = [('indication','uc'), ('indication','cd')]
        elif has_uc:
            result[drug] = [('indication','uc')]
        elif has_cd:
            result[drug] = [('indication','cd')]
        else:
            result[drug] = [('indication','ibd')]  # legacy fallback
    return result


def _build_atopy_drug_contexts(atopy_drugs, dt_rows):
    """
    For each atopy drug, determine which target contexts to emit based on drug_targets.
    - has il4ra in drug_targets → emit ('target','il4ra')
    - has tslp or tslpr        → emit ('target','tslp')
    - neither                  → emit ('target','il4ra') as fallback (IL-4Rα is primary atopy target)
    """
    drug_targets = defaultdict(set)
    for r in dt_rows:
        if r['drug_id'] in atopy_drugs:
            drug_targets[r['drug_id']].add(r['target_id'])

    result = {}
    for drug in atopy_drugs:
        tgts = drug_targets.get(drug, set())
        contexts = []
        if 'il4ra' in tgts:
            contexts.append(('target','il4ra'))
        if 'tslp' in tgts or 'tslpr' in tgts:
            contexts.append(('target','tslp'))
        if not contexts:
            contexts = [('target','il4ra')]  # fallback
        result[drug] = contexts
    return result


def build_output_rows(scores, di_rows, dt_rows):
    """
    Transform drug_area_scores rows into drug_competitive_scores rows.
    Returns (rows_to_insert, audit_log).
    """
    by_area = defaultdict(list)
    for r in scores:
        by_area[r['area_id']].append(r)

    # Build context maps for special area_ids
    ibd_drugs   = {r['drug_id'] for r in by_area.get('ibd', [])}
    atopy_drugs = {r['drug_id'] for r in by_area.get('atopy', [])}

    ibd_ctx_map   = _build_ibd_drug_contexts(ibd_drugs, di_rows)
    atopy_ctx_map = _build_atopy_drug_contexts(atopy_drugs, dt_rows)

    # Deduplicate output (UNIQUE key = drug_id + context_type + context_id)
    # Keep best row by confidence_level, then prefer non-null source_url
    output = {}   # (drug_id, context_type, context_id) → row dict
    audit  = []

    # Map drug_area_scores.confidence_level (legacy enum) → drug_competitive_scores CHECK constraint
    # drug_area_scores used: 'confirmed' (67), 'supported' (76), 'inferred' (42), NULL (27)
    # drug_competitive_scores CHECK: ('A','B','C','inferred')
    CONF_MAP = {
        'confirmed': 'A',    # direct primary-source evidence — maps to A-grade
        'supported': 'B',    # secondary/indirect evidence — maps to B-grade
        'inferred':  'inferred',
        None:        None,
    }

    def _make_row(src, context_type, context_id):
        raw_conf = src.get('confidence_level')
        return {
            'drug_id':           src['drug_id'],
            'context_type':      context_type,
            'context_id':        context_id,
            'overlap':           src.get('overlap'),
            'overlap_rationale': src.get('overlap_rationale'),
            'cls':               src.get('cls'),
            'confidence_level':  CONF_MAP.get(raw_conf, raw_conf),  # map legacy → A/B/C/inferred
            'source_url':        src.get('source_url'),
            'vs_ailux':          src.get('vs_ailux_positioning'),
            'enriched_by':       'migration',
            'enriched_at':       datetime.utcnow().isoformat(),
            'migrated_from':     f"drug_area_scores.area_id={src['area_id']}",
            'notes':             f'Migrated {MIGRATION_ID}. Legacy confidence: {raw_conf}',
        }

    def _better(existing, candidate):
        """Return True if candidate is better than existing."""
        ep = CONF_PRIORITY.get(existing.get('confidence_level'), 9)
        cp = CONF_PRIORITY.get(candidate.get('confidence_level'), 9)
        if cp < ep: return True
        if cp > ep: return False
        # same level: prefer non-null source_url
        if candidate.get('source_url') and not existing.get('source_url'):
            return True
        return False

    def _add(src, ctx_type, ctx_id):
        key = (src['drug_id'], ctx_type, ctx_id)
        row = _make_row(src, ctx_type, ctx_id)
        if key not in output:
            output[key] = row
        elif _better(output[key], row):
            audit.append({'action': 'replaced', 'key': key,
                          'old_from': output[key]['migrated_from'], 'new_from': row['migrated_from']})
            output[key] = row
        else:
            audit.append({'action': 'discarded', 'key': key,
                          'discarded_from': row['migrated_from'], 'kept_from': output[key]['migrated_from']})

    for area_id, area_scores in by_area.items():
        for src in area_scores:
            drug = src['drug_id']

            if area_id == 'ibd':
                contexts = ibd_ctx_map.get(drug, [('indication','ibd')])
                for ct, ci in contexts:
                    _add(src, ct, ci)

            elif area_id == 'atopy':
                contexts = atopy_ctx_map.get(drug, [('target','il4ra')])
                for ct, ci in contexts:
                    _add(src, ct, ci)

            else:
                contexts = AREA_CONTEXT_MAP.get(area_id)
                if contexts:
                    for ct, ci in contexts:
                        _add(src, ct, ci)
                else:
                    audit.append({'action': 'unmapped', 'area_id': area_id, 'drug_id': drug})

    return list(output.values()), audit


def print_audit_report(scores, rows, audit_log):
    by_area = defaultdict(list)
    for r in scores:
        by_area[r['area_id']].append(r)

    print('\n' + '='*70)
    print('PRE-MIGRATION AUDIT')
    print('='*70)
    print(f'\nSource: drug_area_scores — {len(scores)} rows across {len(by_area)} area_ids')
    print(f'Target: drug_competitive_scores — {len(rows)} rows to insert\n')

    print('Area breakdown (source → output):')
    for area_id in sorted(by_area.keys()):
        src_count = len(by_area[area_id])
        # Count output rows derived from this area
        out_count = sum(1 for r in rows if area_id in r.get('migrated_from',''))
        print(f'  {area_id:20s} src={src_count:3d} → out={out_count:3d}')

    by_ctx = defaultdict(list)
    for r in rows:
        by_ctx[(r['context_type'], r['context_id'])].append(r)

    print('\nOutput breakdown by context:')
    for (ct, ci), ctx_rows in sorted(by_ctx.items()):
        print(f'  {ct:15s}/{ci:20s} → {len(ctx_rows)} rows')

    replaced  = [e for e in audit_log if e['action'] == 'replaced']
    discarded = [e for e in audit_log if e['action'] == 'discarded']
    unmapped  = [e for e in audit_log if e['action'] == 'unmapped']
    print(f'\nDeduplication: {len(replaced)} replacements, {len(discarded)} discarded, {len(unmapped)} unmapped')
    if unmapped:
        print('  UNMAPPED (need manual review):')
        for e in unmapped:
            print(f"    area_id={e['area_id']} drug={e['drug_id']}")


def run_validation():
    print('\n' + '='*70)
    print('POST-MIGRATION VALIDATION')
    print('='*70)

    rows = _fetch('drug_competitive_scores?select=drug_id,context_type,context_id,overlap,confidence_level&limit=1000')
    print(f'\ndrug_competitive_scores total rows: {len(rows)}')

    by_ctx = defaultdict(list)
    for r in rows:
        by_ctx[(r['context_type'], r['context_id'])].append(r)

    print('\nContext breakdown:')
    for (ct, ci), ctx_rows in sorted(by_ctx.items()):
        print(f'  {ct:15s}/{ci:20s} → {len(ctx_rows)} rows')

    # Spot-check key drugs
    print('\nSpot-checks:')
    checks = [
        ('risankizumab', 'indication', 'cd'),
        ('mirikizumab',  'indication', 'uc'),
        ('upadacitinib', 'indication', 'uc'),
        ('efgartigimod', 'target',     'fcrn'),
        ('dupilumab',    'target',     'il4ra'),
    ]
    for (drug, ct, ci) in checks:
        match = [r for r in rows if r['drug_id']==drug and r['context_type']==ct and r['context_id']==ci]
        status = f"✓ overlap={match[0]['overlap']}" if match else '✗ MISSING'
        print(f'  {drug:25s} {ct}/{ci}: {status}')

    # Integrity check: no NULL context_type or context_id
    null_ctx = [r for r in rows if not r['context_type'] or not r['context_id']]
    print(f'\nIntegrity: null context rows = {len(null_ctx)} (expected 0)')

    return len(rows)


def main():
    mode = '--audit'
    if len(sys.argv) > 1:
        mode = sys.argv[1]

    print(f'migrate_drug_area_scores — mode: {mode}\n')

    scores, di_rows, dt_rows = load_source_data()
    rows, audit_log = build_output_rows(scores, di_rows, dt_rows)

    if mode == '--audit':
        print_audit_report(scores, rows, audit_log)

    elif mode == '--dry-run':
        print_audit_report(scores, rows, audit_log)
        print('\n[DRY RUN] No rows written.')
        print('Run with --commit to execute migration.')

    elif mode == '--commit':
        print_audit_report(scores, rows, audit_log)
        if not SB_KEY:
            print('\nERROR: SUPABASE_KEY not set.')
            sys.exit(1)

        print(f'\n[Committing] {len(rows)} rows to drug_competitive_scores...')
        BATCH = 50
        total_inserted = 0
        for i in range(0, len(rows), BATCH):
            batch = rows[i:i+BATCH]
            try:
                result = _post('drug_competitive_scores', batch)
                n = len(result) if isinstance(result, list) else len(batch)
                total_inserted += n
                print(f'  Batch {i//BATCH+1}: {n} rows')
            except RuntimeError as e:
                print(f'  ERROR batch {i//BATCH+1}: {e}')

        print(f'\nCommit complete: {total_inserted} rows written')
        run_validation()

    else:
        print(f'Unknown mode: {mode}. Use --audit, --dry-run, or --commit')
        sys.exit(1)


if __name__ == '__main__':
    main()
