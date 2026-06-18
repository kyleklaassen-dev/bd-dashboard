#!/usr/bin/env python3
"""Materialize deal/ownership relationships into the entity_relationships graph.

The graph was thick in competitive edges (direct_competitor) but thin in the
BD-bearing layer (licensor_licensee / co_developer / parent_subsidiary) because
company_partnerships, asset_transfer_history, and deals were never mirrored into
entity_relationships. This script does that mirror, idempotently (dedup on
source_id+target_id+relationship_type), so the deal layer stays current.

Sources, in priority order:
  1. company_partnerships  — structured, has both company ids + verified flag + source_url
  2. asset_transfer_history — licensing chains (from_entity_id -> to_entity_id)
  3. deals                  — name-resolved against companies, structural deal_types only

Run: python src/meridian/graph/materialize_deal_edges.py [--dry-run]
Env: SUPABASE_URL, SUPABASE_SERVICE_KEY
"""
import os
import sys
import datetime
import requests

from meridian.credentials import read_key

URL = read_key("SUPABASE_URL", ".supabase_url", "https://tghntyofptvfhmtchwcv.supabase.co").rstrip("/")
KEY = read_key("SUPABASE_SERVICE_KEY", ".supabase_service_key")
B = f"{URL}/rest/v1"
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}
HW = {**H, "Content-Type": "application/json", "Prefer": "return=minimal"}
NOW = datetime.datetime.utcnow().isoformat() + "Z"
DRY = "--dry-run" in sys.argv


def g(t, params):
    return requests.get(f"{B}/{t}", headers=H, params={**params, "limit": "5000"}, timeout=40).json()


def main() -> int:
    comps = g("companies", {"select": "id,name"})
    valid = {c["id"] for c in comps}
    name2id = {c["name"].strip().lower(): c["id"] for c in comps if c.get("name")}

    existing = set()
    for e in g("entity_relationships", {"select": "source_id,target_id,relationship_type,source_type"}):
        if e.get("source_type") == "company":
            existing.add((e["source_id"], e["target_id"], e["relationship_type"]))

    rows, seen = [], set()

    def add(src, tgt, rt, conf, score, url, ev, note, vneed):
        if not src or not tgt or src == tgt or src not in valid or tgt not in valid:
            return
        k = (src, tgt, rt)
        if k in existing or k in seen:
            return
        seen.add(k)
        rows.append({
            "source_id": src, "source_type": "company", "target_id": tgt, "target_type": "company",
            "relationship_type": rt, "confidence": conf, "confidence_score": score, "source_url": url,
            "inference_method": "database_join", "evidence": [ev], "notes": note,
            "verification_needed": vneed, "is_current": True, "inferred_at": NOW,
        })

    # 1. company_partnerships
    for p in g("company_partnerships", {"select": "lead_company_id,partner_company_id,partnership_type,deal_type,drug_id,source_url,partnership_verified,geographic_rights"}):
        lead, partner = p.get("lead_company_id"), p.get("partner_company_id")
        pt = (p.get("partnership_type") or p.get("deal_type") or "").lower()
        if pt == "licensed_in":
            src, tgt, rt = partner, lead, "licensor_licensee"
        elif pt == "licensed_out":
            src, tgt, rt = lead, partner, "licensor_licensee"
        elif pt in ("co_developed", "co-commercialization", "collaboration"):
            src, tgt, rt = lead, partner, "co_developer"
        elif pt in ("acquisition", "acquired_asset"):
            src, tgt, rt = lead, partner, "parent_subsidiary"
        else:
            src, tgt, rt = lead, partner, "licensor_licensee"
        v = p.get("partnership_verified") is True
        ev = f"{pt} partnership" + (f" · {p['drug_id']}" if p.get("drug_id") else "") + (f" · {p['geographic_rights']}" if p.get("geographic_rights") else "")
        add(src, tgt, rt, "high" if v else "inferred", 0.9 if v else 0.65, p.get("source_url"),
            ev, f"deal-edge from company_partnerships ({pt})", not v)

    # 2. asset_transfer_history
    for a in g("asset_transfer_history", {"select": "from_entity_id,to_entity_id,transfer_type,drug_id,source_url,verified"}):
        tt = (a.get("transfer_type") or "").lower()
        rt = "parent_subsidiary" if "acqui" in tt else "licensor_licensee"
        add(a.get("from_entity_id"), a.get("to_entity_id"), rt, "high" if a.get("verified") else "inferred",
            0.85 if a.get("verified") else 0.6, a.get("source_url"),
            f"asset transfer ({tt}) · {a.get('drug_id')}", f"deal-edge from asset_transfer_history ({tt})", not a.get("verified"))

    # 3. deals (conservative: both parties resolve + structural deal_type)
    DT = {"licensing": "licensor_licensee", "license": "licensor_licensee",
          "acquisition": "parent_subsidiary", "collaboration": "co_developer", "co-development": "co_developer"}
    for d in g("deals", {"select": "from_company,to_company,company_id,deal_type,drug_id,source_url"}):
        rt = DT.get((d.get("deal_type") or "").lower())
        if not rt:
            continue
        fid = name2id.get((d.get("from_company") or "").strip().lower()) or (d.get("company_id") if d.get("company_id") in valid else None)
        tid = name2id.get((d.get("to_company") or "").strip().lower())
        if not fid or not tid:
            continue
        src, tgt = (tid, fid) if rt == "parent_subsidiary" else (fid, tid)  # acquirer = to_company
        add(src, tgt, rt, "inferred", 0.6, d.get("source_url"),
            f"deal ({d.get('deal_type')}) · {d.get('drug_id')}", f"deal-edge from deals ({d.get('deal_type')})", True)

    print(f"{'[DRY] ' if DRY else ''}deal/ownership edges to add: {len(rows)}")
    if rows and not DRY:
        r = requests.post(f"{B}/entity_relationships", headers=HW, json=rows, timeout=90)
        print("insert:", r.status_code, r.text[:160])
        return 0 if r.status_code in (200, 201, 204) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
