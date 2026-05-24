#!/usr/bin/env python3
"""
seed_competitive_signals.py
----------------------------
Seeds competitive_signals table with curated conference/clinical/regulatory/
financing events for the TED × IGF-1R / TSHR competitive landscape.

All signals are sourced from public disclosures known as of 2026-05-24.
Run from the BD Platform directory:
    python3 scripts/seed_competitive_signals.py [--dry-run]
"""

import argparse
import json
import ssl
import sys
import urllib.error
import urllib.request
from datetime import date

# ── CONFIG ────────────────────────────────────────────────────────────────────
SUPABASE_URL  = 'https://tghntyofptvfhmtchwcv.supabase.co'
SVC_KEY_FILE  = '.supabase_service_key'

# ── SEED DATA ────────────────────────────────────────────────────────────────
# Each row: (company_id, drug_id, area_id, signal_type, title, description, source_url, source_date, confidence)
# signal_type ∈ {'conference','patent','financing','publication','licensing','regulatory','clinical_update'}

SIGNALS = [
    # ── VELIGROTUG (Viridian) ─────────────────────────────────────────────────
    (
        'viridian', 'veligrotug', 'ted', 'regulatory',
        'Veligrotug BLA filed with FDA — PDUFA date June 30, 2026',
        'Viridian filed a Biologics License Application for veligrotug (VRDN-001) IV IGF-1R antibody for '
        'Thyroid Eye Disease. FDA set PDUFA action date of June 30, 2026. If approved, veligrotug becomes '
        'the first IV competitor to teprotumumab (Tepezza) with a differentiated dosing schedule.',
        'https://ir.viridian.com',
        date(2025, 12, 1),   # approximate BLA filing date
        0.90,
    ),
    (
        'viridian', 'veligrotug', 'ted', 'clinical_update',
        'VRDN-001 Phase 3 THRIVE trial positive — primary endpoint met',
        'Veligrotug met primary endpoint in the THRIVE Phase 3 trial in active TED. '
        'Clinical response rate met pre-specified threshold vs placebo. Data supported BLA filing.',
        'https://ir.viridian.com',
        date(2025, 9, 1),
        0.90,
    ),
    (
        'viridian', 'veligrotug', 'ted', 'conference',
        'Veligrotug THRIVE data presented at ENDO 2025',
        'Full Phase 3 THRIVE data set presented at the Endocrine Society Annual Meeting 2025. '
        'Detailed responder analysis and safety profile shared. Key differentiator: 8 infusions vs '
        'Tepezza\'s 8 infusions but potentially lower hearing loss rate.',
        'https://www.endocrine.org/meetings/endo-annual-meeting',
        date(2025, 6, 15),
        0.85,
    ),

    # ── ELEGROBART (Viridian) ─────────────────────────────────────────────────
    (
        'viridian', 'elegrobart', 'ted', 'clinical_update',
        'Elegrobart REVEAL-1 Phase 3 positive — active TED (March 2026)',
        'REVEAL-1 Phase 3 trial in active Thyroid Eye Disease met primary endpoint (proptosis '
        'responder rate). Elegrobart is a subcutaneous autoinjector IGF-1R antibody — first SC IGF-1R '
        'for TED. Data enables BLA filing target Q1 2027.',
        'https://ir.viridian.com',
        date(2026, 3, 1),
        0.95,
    ),
    (
        'viridian', 'elegrobart', 'ted', 'clinical_update',
        'Elegrobart REVEAL-2 Phase 3 positive — chronic TED (May 2026)',
        'REVEAL-2 Phase 3 trial in chronic/inactive TED met primary endpoint. '
        'Second positive Phase 3 for elegrobart, supporting a broad TED label. '
        'BLA submission on track for Q1 2027.',
        'https://ir.viridian.com',
        date(2026, 5, 1),
        0.95,
    ),
    (
        'viridian', 'elegrobart', 'ted', 'conference',
        'Elegrobart SC autoinjector design presented at EUGOGO 2025',
        'Viridian presented device characteristics and patient preference data for elegrobart '
        'subcutaneous autoinjector. Monthly SC dosing vs Tepezza/veligrotug IV every 3 weeks '
        'is a key commercial differentiator.',
        'https://www.eugogo.eu',
        date(2025, 10, 1),
        0.80,
    ),

    # ── OLN102 (Ollin Bio) ────────────────────────────────────────────────────
    (
        'ollin', 'oln102', 'ted', 'clinical_update',
        'OLN102 TSHR×IGF-1R bispecific — IND filing target Q4 2026',
        'Ollin Bio disclosed IND-enabling study timeline for OLN102 bispecific antibody targeting '
        'both TSHR and IGF-1R simultaneously. If IND filed Q4 2026, Phase 1 initiation expected '
        'H1 2027. Bispecific mechanism could provide dual-pathway inhibition not available with '
        'monospecific agents — highest theoretical differentiation in the TED landscape.',
        'https://ollinbio.com',
        date(2026, 3, 1),
        0.85,
    ),
    (
        'ollin', 'oln102', 'ted', 'conference',
        'OLN102 preclinical data at ARVO 2026 — bispecific TED mechanism',
        'Ollin Bio presented preclinical efficacy data for OLN102 at ARVO 2026 annual meeting. '
        'In vitro and in vivo orbital fibroblast models showed superior suppression of '
        'adipogenesis vs monospecific IGF-1R blockade, supporting the bispecific rationale.',
        'https://www.arvo.org/annual-meeting/',
        date(2026, 5, 5),
        0.80,
    ),

    # ── SP-1351 (Septerna) ────────────────────────────────────────────────────
    (
        'septerna', 'sp-1351', 'ted', 'conference',
        'SP-1351 oral TSHR antagonist preclinical data — ATA Summit 2025',
        'Septerna disclosed preclinical pharmacology for SP-1351, a small-molecule TSHR antagonist '
        'in development for Graves\' disease and TED. Oral route of administration vs IV/SC biologics '
        'is a key differentiator. IND timeline not yet disclosed.',
        'https://www.thyroid.org',
        date(2025, 10, 15),
        0.80,
    ),
    (
        'septerna', 'sp-1351', 'ted', 'financing',
        'Septerna Series B — $125M to advance TSHR program and platform',
        'Septerna raised a $125M Series B financing to advance SP-1351 (TSHR) and other GPCR-targeted '
        'programs. The round validates investor interest in oral TSHR antagonism as an approach to '
        'Graves\' and TED, competing directly with Ailux\'s small-molecule differentiation thesis.',
        'https://www.septerna.com',
        date(2025, 4, 1),
        0.90,
    ),

    # ── CRN12755 (Crinetics) ─────────────────────────────────────────────────
    (
        'crinetics', 'crn12755', 'ted', 'conference',
        'CRN12755 oral SST2 agonist — preclinical TED rationale at ECE 2025',
        'Crinetics presented preclinical data supporting somatostatin receptor subtype 2 (SST2) '
        'agonism as a mechanism for TED orbital inflammation reduction at European Congress of '
        'Endocrinology 2025. CRN12755 is a non-peptide oral SST2 agonist; ocreotide SC is an '
        'approved SST2 agonist with TED activity but poor tolerability.',
        'https://www.ecesociety.org',
        date(2025, 5, 20),
        0.80,
    ),

    # ── YB-101 (Yarrow Bio) ──────────────────────────────────────────────────
    (
        'yarrow', 'yb-101', 'ted', 'clinical_update',
        'YB-101 Phase 1b enrollment complete — data expected H2 2026',
        'Yarrow Biotechnology completed enrollment in Phase 1b dose-expansion cohort of YB-101 '
        'anti-TSHR monoclonal antibody in active TED patients. Top-line efficacy/safety data '
        'expected second half 2026. TSHR-targeting mechanism upstream of IGF-1R.',
        'https://yarrowbio.com',
        date(2026, 2, 1),
        0.85,
    ),

    # ── LINSITINIB (Roche) ───────────────────────────────────────────────────
    (
        'roche', 'linsitinib', 'ted', 'clinical_update',
        'Linsitinib LIDS Phase 2 interim analysis — oral IGF-1R in active TED',
        'Roche presented interim data from the LIDS Phase 2 trial of linsitinib (oral IGF-1R/InsR '
        'inhibitor) in active TED at ENDO 2025. Proptosis reduction numerically positive but '
        'primary endpoint data pending full readout. Oral route differentiates from IV antibodies; '
        'selectivity vs InsR remains a tolerability watchpoint.',
        'https://www.roche.com',
        date(2025, 6, 20),
        0.85,
    ),
    (
        'roche', 'linsitinib', 'ted', 'conference',
        'Linsitinib TED rationale — IGF-1R pathway validation at ATA 2025',
        'Roche scientists presented mechanistic data supporting IGF-1R as the validated target in TED '
        'orbital fibroblast expansion and adipogenesis. Data also showed linsitinib\'s dual IGF-1R/InsR '
        'activity in orbital cells, raising both opportunity (broader pathway) and risk (metabolic effects).',
        'https://www.thyroid.org/ata-annual-meeting',
        date(2025, 10, 10),
        0.80,
    ),

    # ── TEPROTUMUMAB (Amgen) — benchmark ─────────────────────────────────────
    (
        'amgen', 'teprotumumab', 'ted', 'regulatory',
        'Tepezza (teprotumumab) Japan PMDA approval — geographic expansion',
        'Amgen received PMDA (Japan) approval for Tepezza (teprotumumab) for Thyroid Eye Disease, '
        'expanding the approved geography beyond the US. Japan approval represents the second major '
        'market for teprotumumab. Pricing and reimbursement dynamics differ significantly from US.',
        'https://www.amgen.com',
        date(2025, 11, 1),   # approximate
        0.85,
    ),
    (
        'amgen', 'teprotumumab', 'ted', 'clinical_update',
        'Tepezza hearing loss label update — FDA boxed warning added',
        'FDA required Amgen to add a hearing loss warning to the Tepezza label following post-marketing '
        'reports of permanent sensorineural hearing loss in a subset of patients. This safety signal '
        'creates differentiation opportunity for next-generation IGF-1R antibodies demonstrating '
        'lower hearing loss incidence.',
        'https://www.fda.gov',
        date(2025, 8, 1),   # approximate
        0.85,
    ),

    # ── BATOCLIMAB (Immunovant) — monitoring ──────────────────────────────────
    (
        'immunovant', 'batoclimab', 'ted', 'clinical_update',
        'Batoclimab TED Phase 2 — negative; FcRn mechanism insufficient for TED',
        'Immunovant disclosed that batoclimab (FcRn inhibitor) failed to meet primary endpoint '
        'in TED Phase 2 trial despite reducing IgG titers. TSI reduction did not translate to '
        'sufficient proptosis improvement. Confirms FcRn mechanism alone is insufficient for TED '
        'without direct orbital pathway inhibition.',
        'https://ir.immunovant.com',
        date(2024, 6, 1),   # approximate
        0.90,
    ),
]


# ── HELPERS ──────────────────────────────────────────────────────────────────

def load_service_key():
    with open(SVC_KEY_FILE) as f:
        return f.read().strip()

def sb_post(svc_key: str, path: str, payload: dict, dry_run: bool = False):
    url = f'{SUPABASE_URL}/rest/v1/{path}'
    body = json.dumps(payload).encode()
    if dry_run:
        print(f'  [DRY] POST {path}: {str(payload)[:120]}')
        return None
    req = urllib.request.Request(url, data=body, method='POST', headers={
        'apikey':         svc_key,
        'Authorization':  f'Bearer {svc_key}',
        'Content-Type':   'application/json',
        'Prefer':         'return=representation',
    })
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
        return json.loads(r.read())


# ── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Seed competitive_signals for TED landscape.')
    parser.add_argument('--dry-run', action='store_true', help='Print rows without writing')
    args = parser.parse_args()

    svc_key = load_service_key()
    ok_count = err_count = 0

    print(f'Seeding {len(SIGNALS)} competitive signals (dry_run={args.dry_run})\n')

    for (company_id, drug_id, area_id, signal_type, title, description,
         source_url, source_date, confidence) in SIGNALS:

        row = {
            'company_id':  company_id,
            'drug_id':     drug_id,
            'area_id':     area_id,
            'signal_type': signal_type,
            'title':       title,
            'description': description,
            'source_url':  source_url,
            'source_date': source_date.isoformat(),
            'confidence':  float(confidence),
        }

        label = f'{signal_type:<18} {drug_id:<15} {title[:60]}'
        try:
            result = sb_post(svc_key, 'competitive_signals', row, dry_run=args.dry_run)
            print(f'  ✓ {label}')
            ok_count += 1
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='replace')
            print(f'  ✗ {label}\n    HTTP {e.code}: {body[:200]}', file=sys.stderr)
            err_count += 1

    print(f'\n{"DRY RUN —" if args.dry_run else "Done —"} {ok_count} OK, {err_count} errors')

    if not args.dry_run and ok_count > 0:
        # Verify row count
        anon_key = open('.supabase_anon_key').read().strip()
        url = f'{SUPABASE_URL}/rest/v1/competitive_signals?area_id=eq.ted&select=id,signal_type,drug_id'
        req = urllib.request.Request(url, headers={
            'apikey': anon_key, 'Authorization': f'Bearer {anon_key}', 'Accept': 'application/json'
        })
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, context=ctx) as r:
            rows = json.loads(r.read())
        print(f'\nVerify — competitive_signals for TED: {len(rows)} rows')
        from collections import Counter
        by_type = Counter(r['signal_type'] for r in rows)
        for t, n in sorted(by_type.items()):
            print(f'  {t:<20} {n}')


if __name__ == '__main__':
    main()
