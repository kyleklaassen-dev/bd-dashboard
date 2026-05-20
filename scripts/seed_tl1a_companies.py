#!/usr/bin/env python3
"""
seed_tl1a_companies.py
======================
One-time (re-runnable) script that seeds all TL1A_PROGRAMS static data
from index.html into Supabase so the pipeline can enrich them.

Writes to:
  companies      — id, name, ticker, company_type, partner_co, group_id, display_co, overlap
  company_areas  — company_id × area_id='tl1a'
  drugs          — one row per drug name within each program entry
  drug_areas     — drug_id × area_id='tl1a'

Idempotent — safe to run multiple times (uses upsert with merge-duplicates).

USAGE:
  python scripts/seed_tl1a_companies.py
  python scripts/seed_tl1a_companies.py --dry-run
"""

import os
import re
import sys
import argparse
import datetime
import requests

# ── Credentials ──────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE  = os.path.join(SCRIPT_DIR, "..")

def _read_cred(filename):
    path = os.path.join(WORKSPACE, filename)
    with open(path) as f:
        return f.read().strip()

SUPABASE_URL = _read_cred(".supabase_config").split("SUPABASE_URL=")[-1].split()[0] \
    if "SUPABASE_URL=" in _read_cred(".supabase_config") \
    else "https://tghntyofptvfhmtchwcv.supabase.co"
SUPABASE_KEY = _read_cred(".supabase_service_key")

TODAY = datetime.datetime.utcnow().strftime("%Y-%m-%d")

SB_HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "resolution=merge-duplicates,return=representation",
}

# ── TL1A Programs (mirrors TL1A_PROGRAMS in index.html) ──────────────────────
# Each entry: id, co, ticker, drug (comma-sep for multi-drug), target,
#             stageKey, overlap, groupId, partnerCo (optional), trials (optional)
TL1A_PROGRAMS = [
    # NOTE: Tulisokibart (MK-7240/PRA023) is Merck's drug, acquired via Prometheus Biosciences.
    # It is listed under groupId='merck' below. Do not add it under spyre.

    dict(id="spyre-mono",    co="Spyre Therapeutics", ticker="SYRE",
         drug="SPY002",
         target="TL1A × IL-23", stageKey="Phase 1", overlap="Direct",
         groupId="spyre", partnerCo=None),

    dict(id="spyre-230",     co="Spyre Therapeutics", ticker="SYRE",
         drug="SPY230",
         target="TL1A × FcRn", stageKey="Phase 1", overlap="Direct",
         groupId="spyre", partnerCo=None),

    dict(id="roche",         co="Roche", ticker="ROG",
         drug="Afimkibart (RO7790121)",
         target="TL1A", stageKey="Phase 3", overlap="Direct",
         groupId="roche", partnerCo="Telavant (Roivant)"),

    dict(id="abbvie",        co="AbbVie", ticker="ABBV",
         drug="FG-M701",
         target="TL1A", stageKey="Phase 2", overlap="Direct",
         groupId="abbvie", partnerCo=None),

    dict(id="abbvie-skyrizi", co="AbbVie", ticker="ABBV",
         drug="Risankizumab (Skyrizi)",
         target="IL-23 (p19)", stageKey="Approved", overlap="Adjacent",
         groupId="abbvie", partnerCo=None),

    dict(id="abbvie-rinvoq", co="AbbVie", ticker="ABBV",
         drug="Upadacitinib (Rinvoq)",
         target="JAK1", stageKey="Approved", overlap="Adjacent",
         groupId="abbvie", partnerCo=None),

    dict(id="sanofi",        co="Sanofi", ticker="SNY",
         drug="Duvakitug (SAR447029)",
         target="TL1A", stageKey="Phase 3", overlap="Direct",
         groupId="sanofi", partnerCo="Teva"),

    dict(id="xencor-942",   co="Xencor", ticker="XNCR",
         drug="XmAb942 (Vudalimab)",
         target="TL1A", stageKey="Phase 2", overlap="Direct",
         groupId="xencor", partnerCo=None),

    dict(id="xencor-412",   co="Xencor", ticker="XNCR",
         drug="XmAb412",
         target="TL1A × IL-23", stageKey="Phase 1", overlap="Direct",
         groupId="xencor", partnerCo=None),

    dict(id="simcere",       co="Simcere", ticker="Private",
         drug="SIM0500",
         target="TL1A", stageKey="Phase 1", overlap="Direct",
         groupId="simcere", partnerCo="Boehringer Ingelheim"),

    dict(id="caldera",       co="Caldera", ticker="Private",
         drug="CLDR-001",
         target="TL1A", stageKey="Phase 1", overlap="Direct",
         groupId="caldera", partnerCo="Qyuns Therapeutics"),

    dict(id="earendil",      co="Earendil / Helixon", ticker="Private",
         drug="EAR-2001",
         target="TL1A", stageKey="Phase 1", overlap="Direct",
         groupId="earendil", partnerCo="Sanofi"),

    dict(id="lanova",        co="LaNova", ticker="Private",
         drug="LM-302",
         target="TL1A", stageKey="Phase 1", overlap="Direct",
         groupId="lanova", partnerCo="Zymeworks"),

    dict(id="episcience",    co="Episcience", ticker="Private",
         drug="EPI-001",
         target="TL1A", stageKey="Preclinical", overlap="Watch",
         groupId="episcience", partnerCo=None),

    dict(id="merck",         co="Merck & Co.", ticker="MRK",
         drug="Tulisokibart (MK-7240/PRA023)",
         target="TL1A", stageKey="Phase 3", overlap="Direct",
         groupId="merck", partnerCo=None),

    dict(id="mirador",       co="Mirador Therapeutics", ticker="Private",
         drug="MDR-018",
         target="TL1A", stageKey="Phase 1", overlap="Direct",
         groupId="mirador", partnerCo=None),

    dict(id="lilly-omvoh",   co="Eli Lilly", ticker="LLY",
         drug="Mirikizumab (Omvoh)",
         target="IL-23 (p19)", stageKey="Approved", overlap="Adjacent",
         groupId="lilly", partnerCo=None),

    dict(id="takeda-entyvio", co="Takeda", ticker="TAK",
         drug="Vedolizumab (Entyvio)",
         target="α4β7", stageKey="Approved", overlap="Adjacent",
         groupId="takeda", partnerCo=None),
]

# Map stageKey → company_type (rough heuristic for pipeline)
STAGE_TO_TYPE = {
    "Approved":    "large_cap",
    "Phase 3":     "mid_cap",
    "Phase 2":     "small_cap",
    "Phase 1":     "small_cap",
    "Preclinical": "small_cap",
}


# ── Supabase helpers ──────────────────────────────────────────────────────────

def sb_upsert(table, records, dry_run=False):
    if isinstance(records, dict):
        records = [records]
    if not records:
        return []
    if dry_run:
        print(f"  [DRY] {table}: {[r.get('id') or r for r in records]}")
        return records
    r = requests.post(f"{SUPABASE_URL}/rest/v1/{table}",
                      headers=SB_HEADERS, json=records, timeout=15)
    if r.status_code not in (200, 201):
        print(f"  [ERR] {table} {r.status_code}: {r.text[:300]}")
        return []
    return r.json()


def sb_get(table, params):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}",
                     headers=SB_HEADERS, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


# ── Slug helpers ──────────────────────────────────────────────────────────────

def slugify(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


# ── Main ──────────────────────────────────────────────────────────────────────

def seed(dry_run=False):
    print(f"{'[DRY RUN] ' if dry_run else ''}Seeding TL1A programs → Supabase")
    print(f"  URL: {SUPABASE_URL}")
    print()

    # Deduplicate by groupId for company-level records
    seen_groups = {}  # groupId → first entry representing the group
    for prog in TL1A_PROGRAMS:
        gid = prog["groupId"]
        if gid not in seen_groups:
            seen_groups[gid] = prog

    # 1. Upsert companies (one per groupId)
    print("── Companies ──────────────────────────────────────────")
    for gid, prog in seen_groups.items():
        co_id     = gid  # groupId IS the company_id (e.g. 'spyre', 'abbvie', 'roche')
        co_name   = prog["co"].split(" / ")[0].strip()  # first name only for display
        co_type   = STAGE_TO_TYPE.get(prog["stageKey"], "small_cap")

        record = {
            "id":           co_id,
            "name":         co_name,
            "ticker":       prog["ticker"],
            "company_type": co_type,
            "group_id":     gid,
            "display_co":   prog["co"],          # full display name (may include "/ Helixon")
            "partner_co":   prog.get("partnerCo"),
            "overlap":      prog["overlap"],
            "last_verified": TODAY,
        }
        print(f"  → {co_id}: {co_name} ({prog['stageKey']})")
        sb_upsert("companies", record, dry_run=dry_run)

    print()

    # 2. Upsert company_areas — tag to BOTH specific area (tl1a) AND indication_group (ibd).
    # Company eligibility for the TL1A tab is IBD-based: any company with an IBD drug qualifies.
    print("── company_areas ───────────────────────────────────────")
    for gid in seen_groups:
        print(f"  → {gid} × tl1a + ibd")
        sb_upsert("company_areas", {"company_id": gid, "area_id": "tl1a"}, dry_run=dry_run)
        sb_upsert("company_areas", {"company_id": gid, "area_id": "ibd"},  dry_run=dry_run)

    print()

    # 3. Upsert drugs (one row per drug name; multiple per entry if comma-sep)
    print("── drugs ───────────────────────────────────────────────")
    for prog in TL1A_PROGRAMS:
        co_id      = prog["groupId"]
        drug_names = [d.strip() for d in prog["drug"].split(",") if d.strip()]

        for raw_name in drug_names:
            # Slug: use first word/identifier (e.g. "Afimkibart" from "Afimkibart (RO7790121)")
            short_name = re.sub(r'\s*[(/].*', '', raw_name).strip()
            drug_slug  = slugify(short_name)
            if not drug_slug:
                continue

            record = {
                "id":                drug_slug,
                "name":              raw_name,
                "company_id":        co_id,
                "entity_id":         co_id,
                "entity_name":       prog["co"],
                "entity_type":       "partnership" if prog.get("partnerCo") else "standalone",
                "stage":             prog["stageKey"],
                "target":            prog["target"],
                "mechanism":         f"Anti-{prog['target']}" if prog["target"] else None,
                "cls":               "Next Gen" if "×" in (prog["target"] or "") else "1st Gen",
                "overlap":           prog["overlap"],
                "discovery_status":  "seeded",
                "sort_order":        1 if prog["overlap"] == "Direct" else 5,
            }
            print(f"  → {drug_slug} ({co_id})")
            sb_upsert("drugs", record, dry_run=dry_run)

            # drug_areas — tag to specific target area AND the broader indication_group area.
            # 'ibd' is the indication_group for tl1a: drugs tagged here show in the
            # expanded row for any IBD-tab company, not just TL1A-specific drugs.
            sb_upsert("drug_areas", {"drug_id": drug_slug, "area_id": "tl1a"}, dry_run=dry_run)
            sb_upsert("drug_areas", {"drug_id": drug_slug, "area_id": "ibd"}, dry_run=dry_run)

    print()
    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed TL1A programs to Supabase")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be done without writing")
    args = parser.parse_args()
    seed(dry_run=args.dry_run)
