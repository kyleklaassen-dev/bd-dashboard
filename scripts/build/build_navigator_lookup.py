#!/usr/bin/env python3
"""
build_navigator_lookup.py
=========================
Builds navigator_lookup.json from drug_targets + drug_indications + drugs tables.

Output: data/navigator_lookup.json

Maps:
  target_id   → [drug_ids]
  target_id   → [company_ids]
  indication_id → [drug_ids]
  indication_id → [company_ids]
  drug_id     → [target_ids]
  drug_id     → [indication_ids]
  company_id  → [target_ids]
  company_id  → [indication_ids]

The navigator JS loads this file for instant client-side filtering without DB round-trips.

Usage:
  python3 scripts/build_navigator_lookup.py [--deploy]

  --deploy: also push navigator_lookup.json to GitHub Pages via git commit+push
"""

import sys
import os
import json
import requests
import subprocess
from collections import defaultdict
from datetime import datetime, timezone

# ─── Credentials ────────────────────────────────────────────────────────────
WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVC = open(os.path.join(WORKSPACE, '.supabase_service_key')).read().strip()
BASE = 'https://tghntyofptvfhmtchwcv.supabase.co/rest/v1'
H = {'apikey': SVC, 'Authorization': f'Bearer {SVC}', 'Content-Type': 'application/json'}

OUTPUT_PATH = os.path.join(WORKSPACE, 'data', 'navigator_lookup.json')


def fetch_all(endpoint: str, params: str = '', limit: int = 2000) -> list:
    """Fetch all rows from a Supabase REST endpoint."""
    url = f'{BASE}/{endpoint}?{params}&limit={limit}'
    r = requests.get(url, headers=H)
    r.raise_for_status()
    return r.json()


def build_lookup() -> dict:
    print("Fetching drug_targets...")
    dt_rows = fetch_all('drug_targets', 'select=drug_id,target_id,target_role')
    print(f"  → {len(dt_rows)} rows")

    print("Fetching drug_indications...")
    di_rows = fetch_all('drug_indications', 'select=drug_id,indication_id,is_lead_indication')
    print(f"  → {len(di_rows)} rows")

    print("Fetching drugs (catalog only)...")
    drugs = fetch_all('drugs', 'select=id,company_id,display_name,stage,target,catalog_category&catalog_category=not.is.null')
    print(f"  → {len(drugs)} rows")

    print("Fetching targets ontology...")
    targets_ont = fetch_all('targets', 'select=id,label,full_name,target_class,pathway,cross_area')
    print(f"  → {len(targets_ont)} rows")

    print("Fetching indications ontology...")
    inds_ont = fetch_all('indications', 'select=id,name,disease_area,abbreviation')
    print(f"  → {len(inds_ont)} rows")

    print("Fetching companies...")
    companies = fetch_all('companies', 'select=id,name,status')
    companies = [c for c in companies if c.get('status') != 'acquired']
    print(f"  → {len(companies)} rows (active/subsidiary)")

    # ─── Build index maps ──────────────────────────────────────────────────
    drug_to_company: dict[str, str] = {}
    drug_meta: dict[str, dict] = {}
    for d in drugs:
        if d.get('company_id'):
            drug_to_company[d['id']] = d['company_id']
        drug_meta[d['id']] = {
            'display_name': d.get('display_name'),
            'stage': d.get('stage'),
            'target': d.get('target'),
            'catalog_category': d.get('catalog_category'),
            'company_id': d.get('company_id'),
        }

    target_meta: dict[str, dict] = {t['id']: t for t in targets_ont}
    ind_meta: dict[str, dict] = {i['id']: i for i in inds_ont}
    company_meta: dict[str, dict] = {c['id']: {'name': c.get('name'), 'status': c.get('status')} for c in companies}

    # ─── drug → targets ───────────────────────────────────────────────────
    drug_to_targets: dict[str, list[str]] = defaultdict(list)
    for row in dt_rows:
        drug_to_targets[row['drug_id']].append(row['target_id'])

    # ─── drug → indications ───────────────────────────────────────────────
    drug_to_inds: dict[str, list[str]] = defaultdict(list)
    for row in di_rows:
        drug_to_inds[row['drug_id']].append(row['indication_id'])

    # ─── target → drugs ───────────────────────────────────────────────────
    target_to_drugs: dict[str, set] = defaultdict(set)
    for drug_id, tgts in drug_to_targets.items():
        for t in tgts:
            target_to_drugs[t].add(drug_id)

    # ─── indication → drugs ───────────────────────────────────────────────
    ind_to_drugs: dict[str, set] = defaultdict(set)
    for drug_id, inds in drug_to_inds.items():
        for i in inds:
            ind_to_drugs[i].add(drug_id)

    # ─── target → companies ───────────────────────────────────────────────
    target_to_companies: dict[str, set] = defaultdict(set)
    for drug_id, tgts in drug_to_targets.items():
        co = drug_to_company.get(drug_id)
        if co:
            for t in tgts:
                target_to_companies[t].add(co)

    # ─── indication → companies ───────────────────────────────────────────
    ind_to_companies: dict[str, set] = defaultdict(set)
    for drug_id, inds in drug_to_inds.items():
        co = drug_to_company.get(drug_id)
        if co:
            for i in inds:
                ind_to_companies[i].add(co)

    # ─── company → targets ────────────────────────────────────────────────
    company_to_targets: dict[str, set] = defaultdict(set)
    for t, cos in target_to_companies.items():
        for co in cos:
            company_to_targets[co].add(t)

    # ─── company → indications ────────────────────────────────────────────
    company_to_inds: dict[str, set] = defaultdict(set)
    for i, cos in ind_to_companies.items():
        for co in cos:
            company_to_inds[co].add(i)

    # ─── Assemble final lookup ─────────────────────────────────────────────
    lookup = {
        '_meta': {
            'built_at': datetime.now(timezone.utc).isoformat(),
            'drug_count': len(drug_meta),
            'target_count': len(target_meta),
            'indication_count': len(ind_meta),
            'company_count': len(company_meta),
            'drug_target_links': len(dt_rows),
            'drug_indication_links': len(di_rows),
        },
        # target → drugs (list for stable JSON, sorted for determinism)
        'target_drugs': {t: sorted(drugs) for t, drugs in target_to_drugs.items()},
        # target → companies
        'target_companies': {t: sorted(cos) for t, cos in target_to_companies.items()},
        # indication → drugs
        'indication_drugs': {i: sorted(drugs) for i, drugs in ind_to_drugs.items()},
        # indication → companies
        'indication_companies': {i: sorted(cos) for i, cos in ind_to_companies.items()},
        # drug → targets
        'drug_targets': {d: sorted(set(tgts)) for d, tgts in drug_to_targets.items()},
        # drug → indications
        'drug_indications': {d: sorted(set(inds)) for d, inds in drug_to_inds.items()},
        # company → targets
        'company_targets': {co: sorted(tgts) for co, tgts in company_to_targets.items()},
        # company → indications
        'company_indications': {co: sorted(inds) for co, inds in company_to_inds.items()},
        # ontology metadata for display
        'target_meta': {t: {'label': m.get('label'), 'full_name': m.get('full_name'),
                             'target_class': m.get('target_class'), 'pathway': m.get('pathway'),
                             'cross_area': m.get('cross_area')}
                        for t, m in target_meta.items()},
        'indication_meta': {i: {'name': m.get('name'), 'disease_area': m.get('disease_area'),
                                 'abbreviation': m.get('abbreviation')}
                            for i, m in ind_meta.items()},
    }

    return lookup


def print_summary(lookup: dict):
    meta = lookup['_meta']
    print("\n=== Navigator Lookup Summary ===")
    print(f"  Built at:              {meta['built_at']}")
    print(f"  Drugs cataloged:       {meta['drug_count']}")
    print(f"  Targets in ontology:   {meta['target_count']}")
    print(f"  Indications in ontol.: {meta['indication_count']}")
    print(f"  Companies active:      {meta['company_count']}")
    print(f"  Drug→Target links:     {meta['drug_target_links']}")
    print(f"  Drug→Indication links: {meta['drug_indication_links']}")
    print(f"  target_drugs keys:     {len(lookup['target_drugs'])}")
    print(f"  target_companies keys: {len(lookup['target_companies'])}")
    print(f"  indication_drugs keys: {len(lookup['indication_drugs'])}")
    print(f"  indication_companies:  {len(lookup['indication_companies'])}")
    print(f"  drug_targets keys:     {len(lookup['drug_targets'])}")
    print(f"  drug_indications keys: {len(lookup['drug_indications'])}")
    # Top targets by drug count
    top_targets = sorted(lookup['target_drugs'].items(), key=lambda x: len(x[1]), reverse=True)[:10]
    print("\n  Top 10 targets by drug count:")
    for t, drugs in top_targets:
        label = lookup['target_meta'].get(t, {}).get('label', t)
        print(f"    {label:30s} → {len(drugs)} drugs, {len(lookup['target_companies'].get(t, []))} companies")
    # Top indications by drug count
    top_inds = sorted(lookup['indication_drugs'].items(), key=lambda x: len(x[1]), reverse=True)[:10]
    print("\n  Top 10 indications by drug count:")
    for i, drugs in top_inds:
        name = lookup['indication_meta'].get(i, {}).get('name', i)
        print(f"    {name:35s} → {len(drugs)} drugs, {len(lookup['indication_companies'].get(i, []))} companies")


def deploy(workspace: str):
    """Commit and push navigator_lookup.json to GitHub Pages."""
    token_path = os.path.join(workspace, '.github_token')
    token = open(token_path).read().strip()

    print("\nDeploying navigator_lookup.json to GitHub Pages...")
    cmds = [
        f'cd "{workspace}" && git add data/navigator_lookup.json',
        f'cd "{workspace}" && git commit -m "build: regenerate navigator_lookup.json ({datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")} UTC)"',
        f'cd "{workspace}" && git push https://kyleklaassen-dev:{token}@github.com/kyleklaassen-dev/bd-dashboard.git main',
    ]
    for cmd in cmds:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  WARN: {result.stderr.strip()[:200]}")
        else:
            print(f"  OK: {result.stdout.strip()[:100] or cmd.split('&&')[-1].strip()[:60]}")


if __name__ == '__main__':
    deploy_flag = '--deploy' in sys.argv

    print("Building navigator_lookup.json...")
    lookup = build_lookup()

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(lookup, f, indent=2)

    file_size = os.path.getsize(OUTPUT_PATH)
    print(f"\nWritten to {OUTPUT_PATH} ({file_size:,} bytes)")

    print_summary(lookup)

    if deploy_flag:
        deploy(WORKSPACE)
    else:
        print("\nRun with --deploy to push to GitHub Pages.")
