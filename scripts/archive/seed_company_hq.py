#!/usr/bin/env python3
"""
seed_company_hq.py
-------------------
Seeds hq_city + hq_country for all companies in the DB.
Also fixes NULL tickers to either a real ticker or 'Private'.

Run from the BD Platform directory:
    python3 scripts/seed_company_hq.py [--dry-run]
"""

import argparse
import json
import ssl
import sys
import urllib.error
import urllib.request

SUPABASE_URL = 'https://tghntyofptvfhmtchwcv.supabase.co'
SVC_KEY_FILE = '.supabase_service_key'

# ── COMPANY DATA ─────────────────────────────────────────────────────────────
# Each entry: company_id → (ticker_fix_or_None, hq_city, hq_country)
# ticker_fix = new ticker value (overrides DB), or None = keep existing
# 'Private' means explicitly mark as private company

COMPANY_HQ = {
    'abbvie':           (None,        'North Chicago',      'US'),
    'absci':            (None,        'Portland',           'US'),
    'alumis':           (None,        'San Francisco',      'US'),
    'amgen':            (None,        'Thousand Oaks',      'US'),
    'antengene':        ('6996.HK',   'Hangzhou',           'China'),
    'apogee':           (None,        'Waltham',            'US'),
    'argenx':           (None,        'Amsterdam',          'Netherlands'),
    'astellas':         (None,        'Tokyo',              'Japan'),
    'astrazeneca':      (None,        'Cambridge',          'UK'),
    'bayer':            (None,        'Leverkusen',         'Germany'),
    'beone':            (None,        'Basel',              'Switzerland'),
    'biogen':           (None,        'Cambridge',          'US'),
    'biosion':          ('Private',   'San Diego',          'US'),
    'boehringer':       (None,        'Ingelheim',          'Germany'),
    'bms':              (None,        'New York',           'US'),
    'cabaletta':        (None,        'Philadelphia',       'US'),
    'caldera':          (None,        'Berkeley',           'US'),
    'candid':           ('Private',   'New York',           'US'),
    'cantai':           ('Private',   'Nanjing',            'China'),
    'cartesian':        (None,        'Gaithersburg',       'US'),
    'celgene':          (None,        'Summit',             'US'),
    'chugai':           ('4519.T',    'Tokyo',              'Japan'),
    'connectbiopharma': (None,        'San Diego',          'US'),
    'crinetics':        (None,        'San Diego',          'US'),
    'cspc':             (None,        'Shijiazhuang',       'China'),
    'cullinan':         (None,        'Cambridge',          'US'),
    'earendil':         (None,        'Cambridge',          'US'),
    'elpiscience':      ('Private',   'Shanghai',           'China'),
    'episcience':       (None,        'San Diego',          'US'),
    'fosun':            (None,        'Shanghai',           'China'),
    'futuregen':        ('Private',   'Beijing',            'China'),
    'galderma':         (None,        'Zug',                'Switzerland'),
    'generate':         (None,        'San Francisco',      'US'),
    'gensci':           (None,        'Beijing',            'China'),
    'gilead':           (None,        'Foster City',        'US'),
    'gossamerbio':      (None,        'San Diego',          'US'),
    'gsk':              (None,        'London',             'UK'),
    'hansoh':           (None,        'Lianyungang',        'China'),
    'harbourbiomed':    ('Private',   'Suzhou',             'China'),
    'helixon':          ('Private',   'Shanghai',           'China'),
    'hengrui':          (None,        'Lianyungang',        'China'),
    'hutchmed':         (None,        'Hong Kong',          'China'),
    'immunovant':       (None,        'New York',           'US'),
    'innovent':         (None,        'Suzhou',             'China'),
    'jnj':              (None,        'New Brunswick',      'US'),
    'kali':             ('Private',   'Guangzhou',          'China'),
    'kyverna':          (None,        'Emeryville',         'US'),
    'lanova':           (None,        'Nanjing',            'China'),
    'leofarma':         ('Private',   'Ballerup',           'Denmark'),
    'leads':            ('Private',   'Chengdu',            'China'),
    'lilly':            (None,        'Indianapolis',       'US'),
    'merck':            (None,        'Rahway',             'US'),
    'minghui':          ('Private',   'Beijing',            'China'),
    'mirador':          (None,        'San Francisco',      'US'),
    'moderna':          (None,        'Cambridge',          'US'),
    'newsoara':         ('Private',   'Chengdu',            'China'),
    'novamab':          ('Private',   'Suzhou',             'China'),
    'novartis':         (None,        'Basel',              'Switzerland'),
    'novonordisk':      (None,        'Bagsvaerd',          'Denmark'),
    'ollin':            ('Private',   'South San Francisco','US'),
    'pfizer':           ('PFE',       'New York',           'US'),
    'prometheus':       ('Private',   'La Jolla',           'US'),
    'ptc':              (None,        'South Plainfield',   'US'),
    'qyuns':            ('Private',   'Chengdu',            'China'),
    'regeneron':        (None,        'Tarrytown',          'US'),
    'remegen':          (None,        'Yantai',             'China'),
    'roche':            (None,        'Basel',              'Switzerland'),
    'roivant':          ('ROIV',      'New York',           'US'),
    'sanofi':           (None,        'Paris',              'France'),
    'santaana':         ('Private',   'Suzhou',             'China'),
    'septerna':         ('Private',   'South San Francisco','US'),
    'shanghai-pharma':  (None,        'Shanghai',           'China'),
    'shboan':           ('Private',   'Shanghai',           'China'),
    'simcere':          (None,        'Nanjing',            'China'),
    'sinobiopharma':    (None,        'Beijing',            'China'),
    'sinopharm':        (None,        'Beijing',            'China'),
    'sparx':            ('Private',   'Tokyo',              'Japan'),
    'spyre':            (None,        'Waltham',            'US'),
    'takeda':           (None,        'Tokyo',              'Japan'),
    'telavant':         ('Private',   'New York',           'US'),
    'teva':             (None,        'Tel Aviv',           'Israel'),
    'ucb':              (None,        'Brussels',           'Belgium'),
    'upstreambio':      (None,        'Cambridge',          'US'),
    'vant':             ('Private',   'New York',           'US'),
    'vertex':           (None,        'Boston',             'US'),
    'viridian':         (None,        'Waltham',            'US'),
    'windward':         ('Private',   'Oakland',            'US'),
    'wuxi-bio':         (None,        'Wuxi',               'China'),
    'xencor':           (None,        'Monrovia',           'US'),
    'xencor-412':       (None,        'Monrovia',           'US'),
    'xencor-942':       (None,        'Monrovia',           'US'),
    'yarrow':           (None,        'South San Francisco','US'),
    'yunnan-baiyao':    (None,        'Kunming',            'China'),
    'zailab':           (None,        'Shanghai',           'China'),
    'pien-tze-huang':   (None,        'Zhangzhou',          'China'),
}


def load_service_key():
    with open(SVC_KEY_FILE) as f:
        return f.read().strip()


def sb_patch(svc_key, company_id, payload, dry_run=False):
    url = f'{SUPABASE_URL}/rest/v1/companies?id=eq.{company_id}'
    body = json.dumps(payload).encode()
    if dry_run:
        print(f'  [DRY] PATCH {company_id}: {payload}')
        return
    req = urllib.request.Request(url, data=body, method='PATCH', headers={
        'apikey':        svc_key,
        'Authorization': f'Bearer {svc_key}',
        'Content-Type':  'application/json',
        'Prefer':        'return=minimal',
    })
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, context=ctx, timeout=30):
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    svc_key = load_service_key()

    # Fetch current DB state so we know which tickers to skip
    anon_key = open('.supabase_anon_key').read().strip()
    req = urllib.request.Request(
        f'{SUPABASE_URL}/rest/v1/companies?select=id,ticker&limit=200',
        headers={'apikey': anon_key, 'Authorization': f'Bearer {anon_key}',
                 'Accept': 'application/json'},
    )
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, context=ctx) as r:
        db_rows = {row['id']: row['ticker'] for row in json.loads(r.read())}

    ok = err = skip = 0
    print(f'Seeding {len(COMPANY_HQ)} companies (dry_run={args.dry_run})\n')

    for co_id, (ticker_fix, hq_city, hq_country) in sorted(COMPANY_HQ.items()):
        if co_id not in db_rows:
            print(f'  ⚠  {co_id:<28} not in DB — skip')
            skip += 1
            continue

        payload = {'hq_city': hq_city, 'hq_country': hq_country}

        # Apply ticker fix: either explicit override, or backfill NULL → 'Private'
        current_ticker = db_rows.get(co_id)
        if ticker_fix is not None:
            payload['ticker'] = ticker_fix
        elif not current_ticker:
            # NULL ticker with no explicit fix → mark Private
            payload['ticker'] = 'Private'

        ticker_note = ''
        if 'ticker' in payload:
            ticker_note = f' ticker={current_ticker!r}→{payload["ticker"]!r}'

        label = f'{co_id:<28} {hq_city}, {hq_country}{ticker_note}'
        try:
            sb_patch(svc_key, co_id, payload, dry_run=args.dry_run)
            print(f'  ✓ {label}')
            ok += 1
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='replace')
            print(f'  ✗ {label}\n    HTTP {e.code}: {body[:200]}', file=sys.stderr)
            err += 1

    print(f'\n{"DRY RUN —" if args.dry_run else "Done —"} {ok} updated, {skip} skipped, {err} errors')


if __name__ == '__main__':
    main()
