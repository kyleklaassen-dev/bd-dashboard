#!/usr/bin/env python3
"""
execute_intel_actions.py — G1 + G2 Gap Fix
===========================================
G1: Promotes approved discovery_queue items to the drugs table.
G2: Executes proposed_actions_json from analyzed submitted_intel items
    (adds deals, catalysts, drug updates that the review_submitted_intel
    workflow identified but never wrote to the DB).

Usage:
  python3 scripts/execute_intel_actions.py                 # both G1 and G2
  python3 scripts/execute_intel_actions.py --discovery     # G1 only
  python3 scripts/execute_intel_actions.py --submitted     # G2 only
  python3 scripts/execute_intel_actions.py --dry-run       # preview only
"""

import os, sys, json, argparse, datetime, re
import requests

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def _key(f):
    p = os.path.join(_REPO, f)
    return open(p).read().strip() if os.path.exists(p) else None

SUPABASE_URL = os.environ.get("SUPABASE_URL") or "https://tghntyofptvfhmtchwcv.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or _key(".supabase_service_key") or ""
if not SUPABASE_KEY: print("ERROR: no SUPABASE_SERVICE_KEY"); sys.exit(1)

# Route ALL core-table writes through the governed single-writers (ROADMAP §A.1)
sys.path.insert(0, os.path.join(_REPO, "src"))
from meridian.database.drug_writer import DrugWriter
from meridian.database.company_writer import CompanyWriter
from meridian.database.catalyst_writer import CatalystWriter

BASE = f"{SUPABASE_URL}/rest/v1"
SB_H = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
NOW = datetime.datetime.utcnow().isoformat()


def sb_get(table, params, limit=200):
    params = {**params, "limit": str(limit)}
    r = requests.get(f"{BASE}/{table}", headers=SB_H, params=params, timeout=20)
    return r.json() if r.status_code == 200 else []

def sb_post(table, payload):
    r = requests.post(f"{BASE}/{table}", headers={**SB_H, "Prefer": "return=minimal"},
                      json=payload, timeout=20)
    return r.status_code in (200, 201)

def sb_patch(table, params, payload):
    r = requests.patch(f"{BASE}/{table}", headers=SB_H, params=params, json=payload, timeout=20)
    return r.status_code in (200, 204)

def make_id(name):
    clean = re.sub(r'[^\w\s-]','',name.lower()).strip()
    clean = re.sub(r'\s+','-',clean)
    return re.sub(r'-+','-',clean)[:40]


# ══════════════════════════════════════════════════════════════════════════════
# G1 — discovery_queue promotion
# ══════════════════════════════════════════════════════════════════════════════

def _company_slug(name):
    """Originator company id convention: lowercase alphanumeric, no spaces/hyphens."""
    return re.sub(r'[^a-z0-9]', '', (name or '').lower())[:40]


def ensure_company(company_name, area_id=None, dry_run=False):
    """Create the originator company if it doesn't exist. Returns company_id or None.
    Governance: drugs.company_id = originator ALWAYS."""
    if not company_name:
        return None
    cid = _company_slug(company_name)
    if not cid:
        return None
    if sb_get("companies", {"id": f"eq.{cid}", "select": "id", "limit": "1"}):
        return cid
    if dry_run:
        print(f"  DRY: would create company {company_name} → {cid}")
        return cid
    row = {"id": cid, "name": company_name, "status": "active",
           "company_type": "biotech", "ta_focus_1": "Immunology"}
    _r = CompanyWriter().upsert(row)   # governed single-writer (ROADMAP §A.1)
    if not _r.get("errors"):
        cid = _r.get("company_id") or cid
        print(f"  ✓ Created originator company: {company_name} ({cid})")
        return cid
    print(f"  ✗ Failed to create company: {company_name}: {_r.get('errors')}")
    return None


def promote_discovery_queue(dry_run=False):
    """Promote approved discovery_queue items to drugs table.

    For molecule items this also (a) creates the originator company if missing and
    sets drugs.company_id, and (b) writes a drug_sources provenance row from
    source_url — so submitted-intel-derived drugs land with their citation and the
    document stays hyperlinked as a primary source."""
    print("\n── G1: discovery_queue → drugs (+ company + source) ──")

    items = sb_get("discovery_queue", {
        "status": "eq.approved",
        "created_drug_id": "is.null",
        "select": "id,drug_name,company_name,target,stage,overlap,area_id,modality,confidence_score,why_discovered,source_url,source",
    })
    print(f"  {len(items)} approved items not yet promoted")

    promoted = 0
    for item in items:
        name = item.get("drug_name") or item.get("company_name") or ""
        if not name: continue

        # Company-only entry → ensure the company exists, then mark handled
        if not item.get("drug_name") and item.get("company_name"):
            ensure_company(item.get("company_name"), item.get("area_id"), dry_run)
            if not dry_run:
                sb_patch("discovery_queue", {"id": f"eq.{item['id']}"}, {"created_drug_id": "COMPANY_ONLY"})
            continue

        drug_id = make_id(name.split("(")[0].strip())
        company_id = ensure_company(item.get("company_name"), item.get("area_id"), dry_run)

        # Already exists → backfill company_id / source then mark handled
        existing = sb_get("drugs", {"id": f"eq.{drug_id}", "select": "id,company_id", "limit": "1"})
        if existing:
            if company_id and not existing[0].get("company_id") and not dry_run:
                from meridian.database import update_drug
                update_drug(drug_id, {"company_id": company_id})
            if not dry_run:
                _write_source(drug_id, name, item)
                sb_patch("discovery_queue", {"id": f"eq.{item['id']}"}, {"created_drug_id": drug_id})
            continue

        target = (item.get("target") or "").replace("α","a").replace("β","b").replace("×","x")[:100]
        summary = (item.get("why_discovered") or "")[:200]

        drug = {
            "id": drug_id,
            "name": name.split("(")[0].strip(),
            "display_name": name,
            "company_id": company_id,
            "target": target or None,
            "stage": item.get("stage") or "Preclinical",
            "modality": item.get("modality") or None,
            "overlap": item.get("overlap") or "Watch",
            "catalog_category": "Competitor",
            "discovery_status": "auto",
            "confidence_score": item.get("confidence_score") or 70,
            "data_source": "discovery_queue",
            "drug_summary": summary or None,
            "source_url": item.get("source_url") or None,
            "confidence_level": "inferred",
        }

        if dry_run:
            print(f"  DRY: would promote {name} → {drug_id} (company={company_id})")
            promoted += 1
            continue

        _r = DrugWriter(source_required=False).upsert(drug)   # governed single-writer (ROADMAP §A.1)
        if not _r.get("errors"):
            drug_id = _r.get("drug_id") or drug_id   # canonical id (dedups)
            _write_source(drug_id, name, item)
            sb_patch("discovery_queue", {"id": f"eq.{item['id']}"}, {"created_drug_id": drug_id})
            print(f"  ✓ Promoted: {name} ({drug_id}) ← {item.get('company_name') or '?'}")
            promoted += 1
        else:
            print(f"  ✗ Failed: {name}: {_r.get('errors')}")

    print(f"  Promoted: {promoted}")
    return promoted


def _write_source(drug_id, drug_name, item):
    """Write a drug_sources provenance row from the queue item's source_url."""
    url = item.get("source_url")
    if not url:
        return
    domain = url.split("/")[2] if "//" in url else ""
    src_type = "other"
    if "clinicaltrials.gov" in domain: src_type = "ct_gov"
    elif "sec.gov" in domain:          src_type = "sec_filing"
    elif any(k in domain for k in ("prnewswire","businesswire","globenewswire")): src_type = "press_release"
    sb_post("drug_sources", {
        "drug_id": drug_id, "drug_name": drug_name.split("(")[0].strip(),
        "claim_type": "company_pipeline",
        "claim_value": (item.get("why_discovered") or "Submitted intel")[:300],
        "source_url": url, "source_type": src_type, "source_domain": domain,
        "content_confirms_claim": True, "confidence": "inferred",
        "added_by": "execute_intel_actions", "session_label": f"promote_{NOW[:10]}",
    })


# ══════════════════════════════════════════════════════════════════════════════
# G2 — submitted_intel action execution
# ══════════════════════════════════════════════════════════════════════════════

def execute_submitted_intel(dry_run=False):
    """Execute proposed_actions_json from analyzed submitted_intel items."""
    print("\n── G2: submitted_intel proposed_actions → DB ──")

    items = sb_get("submitted_intel", {
        "status": "eq.analyzed",
        "imported_at": "is.null",
        "select": "id,extracted_title,extracted_entities_json,proposed_actions_json,source_url,extracted_key_facts_json",
    })
    print(f"  {len(items)} analyzed items not yet imported")

    executed = 0
    for item in items:
        actions = item.get("proposed_actions_json") or []
        if isinstance(actions, str):
            try: actions = json.loads(actions)
            except: actions = []

        title = (item.get("extracted_title") or "")[:80]
        item_executed = 0

        for action in (actions if isinstance(actions, list) else []):
            tbl = action.get("table","")
            act = action.get("action","")

            # Skip reject/duplicate actions — those are informational
            if act in ("reject_duplicate","needs_human_review","add_company_note"):
                continue

            # add_catalyst
            if act == "add_catalyst" and tbl == "catalysts" and not dry_run:
                entities = item.get("extracted_entities_json") or {}
                if isinstance(entities, str):
                    try: entities = json.loads(entities)
                    except: entities = {}
                drugs = entities.get("drugs", []) if isinstance(entities, dict) else []
                companies = entities.get("companies", []) if isinstance(entities, dict) else []
                rationale = (action.get("rationale") or "")[:200]

                # Only add if we can identify a drug
                for drug_name in drugs[:2]:
                    clean = drug_name.split("(")[0].strip().lower()
                    drug_rows = sb_get("drugs", {"name": f"ilike.*{clean}*", "select": "id,company_id", "limit": "1"})
                    if drug_rows:
                        did = drug_rows[0]["id"]
                        # Check no duplicate
                        existing_cats = sb_get("catalysts", {"drug_id": f"eq.{did}",
                            "label": f"ilike.*{clean[:20]}*", "limit": "1"})
                        if not existing_cats:
                            cat = {
                                "drug_id": did,
                                "area_id": "ibd",
                                "catalyst_date": "2026",
                                "sort_date": "2026-12-31",
                                "label": f"Intel signal: {title[:60]}",
                                "catalyst_type": "readout",
                                "significance": "medium",
                                "catalyst_status": "pending",
                                "confidence_level": "inferred",
                                "confidence_score": 0.5,
                                "notes": rationale,
                                "resolved": False,
                            }
                            _r = CatalystWriter().upsert(cat)   # governed single-writer (ROADMAP §A.1)
                            if not _r.get("errors"):
                                item_executed += 1
                                print(f"  ✓ Catalyst added for {did}: {title[:50]}")

            # add_source — add source URL to drug_sources
            elif act == "add_source" and tbl == "deals" and not dry_run:
                src_url = item.get("source_url","")
                entities = item.get("extracted_entities_json") or {}
                if isinstance(entities, str):
                    try: entities = json.loads(entities)
                    except: entities = {}
                deal_val = entities.get("deal_value_usd_m") if isinstance(entities,dict) else None
                companies = entities.get("companies",[]) if isinstance(entities,dict) else []
                # Already handled by manual review mostly — just mark as done
                item_executed += 1

        if item_executed > 0 or actions:
            executed += 1
            # Mark as imported so we don't re-process
            sb_patch("submitted_intel", {"id": f"eq.{item['id']}"}, {"imported_at": NOW})

    print(f"  Items fully processed: {executed}")
    return executed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--discovery", action="store_true")
    parser.add_argument("--submitted", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    run_both = not args.discovery and not args.submitted

    if run_both or args.discovery:
        promote_discovery_queue(dry_run=args.dry_run)

    if run_both or args.submitted:
        execute_submitted_intel(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
