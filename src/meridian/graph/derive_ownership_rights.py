#!/usr/bin/env python3
"""Derive ownership_rights rows from authoritative relationship columns already in DB.

FREE / derived only. resolve-or-skip. NO fabrication of territory/terms.
Idempotent: dedupes on the unique key (drug_id, holder_company_id, right_type, territory).

Sources promoted:
  drugs.company_id              -> right_type='current_owner'  source='drugs.company_id'
  drugs.originator_company_id   -> right_type='originator'     source='drugs.originator_company_id'
       (only where set AND differs from company_id)
  company_partnerships          -> right_type='licensee' | 'co_developer'
       source='company_partnerships#<id>' (+ source_url, territory, terms from the row)
  asset_transfer_history        -> right_type='acquisition' | 'territory_license'
       source='asset_transfer_history#<id>' (+ source_url, territory, terms from the row)

Does NOT alter drugs.company_id or originator attribution. Does NOT touch entity_edges.
"""
import json, os, urllib.request

BASE = "https://tghntyofptvfhmtchwcv.supabase.co/rest/v1"
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SK = open(os.path.join(ROOT, ".supabase_service_key")).read().strip()
HDR = {"apikey": SK, "Authorization": f"Bearer {SK}", "Content-Type": "application/json"}


def get(path):
    out, off = [], 0
    while True:
        req = urllib.request.Request(f"{BASE}/{path}&limit=1000&offset={off}", headers=HDR)
        chunk = json.load(urllib.request.urlopen(req))
        out += chunk
        if len(chunk) < 1000:
            break
        off += 1000
    return out


def post(rows):
    if not rows:
        return 0
    req = urllib.request.Request(f"{BASE}/ownership_rights", method="POST",
                                 headers={**HDR, "Prefer": "return=minimal"},
                                 data=json.dumps(rows).encode())
    urllib.request.urlopen(req)
    return len(rows)


def key(r):
    return (r["drug_id"], r["holder_company_id"], r["right_type"], r.get("territory"))


def main():
    drugs = get("drugs?select=id,company_id,originator_company_id")
    parts = get("company_partnerships?select=id,drug_id,lead_company_id,partner_company_id,"
                "company_id,partnership_type,deal_type,geographic_rights,notes,source_url")
    xfers = get("asset_transfer_history?select=id,drug_id,to_entity_id,transfer_type,"
                "geographic_scope,deal_value_notes,transfer_notes,source_url")
    existing = get("ownership_rights?select=drug_id,holder_company_id,right_type,territory")

    seen = set(key(r) for r in existing)
    # holder-level set: a (drug, holder) pair already asserted by ANY existing row.
    # used to avoid creating parallel/semantic-duplicate rows for the same fact.
    holder_seen = set((r["drug_id"], r["holder_company_id"]) for r in existing)
    new = []

    def add(row):
        if not row["drug_id"] or not row["holder_company_id"]:
            return  # resolve-or-skip
        if key(row) in seen:
            return
        seen.add(key(row))
        new.append(row)

    # 1. current_owner  <- drugs.company_id
    for d in drugs:
        if d["company_id"]:
            add({"drug_id": d["id"], "holder_company_id": d["company_id"],
                 "right_type": "current_owner", "territory": None, "terms": None,
                 "source": "drugs.company_id", "source_url": None})

    # 2. originator  <- drugs.originator_company_id (set AND differs)
    for d in drugs:
        oc = d["originator_company_id"]
        if oc and oc != d["company_id"]:
            add({"drug_id": d["id"], "holder_company_id": oc,
                 "right_type": "originator", "territory": None, "terms": None,
                 "source": "drugs.originator_company_id", "source_url": None})

    # 3. company_partnerships -> licensee / co_developer
    LIC = {"licensed_in", "licensing"}
    CODEV = {"co_developed", "co-development"}
    for p in parts:
        did = p.get("drug_id")
        if not did:
            continue
        pt = (p.get("partnership_type") or "")
        dt = (p.get("deal_type") or "")
        if pt in LIC or dt == "licensing":
            holder, rt = p.get("lead_company_id"), "licensee"
        elif pt in CODEV or dt == "co-development":
            holder, rt = p.get("partner_company_id"), "co_developer"
        else:
            continue
        if not holder or (did, holder) in holder_seen:
            continue  # skip fact already represented by an existing row
        add({"drug_id": did, "holder_company_id": holder, "right_type": rt,
             "territory": p.get("geographic_rights"), "terms": p.get("notes"),
             "source": f"company_partnerships#{p['id']}", "source_url": p.get("source_url")})

    # 4. asset_transfer_history -> acquisition / territory_license (receiving entity gains rights)
    for x in xfers:
        did, holder = x.get("drug_id"), x.get("to_entity_id")
        if not did or not holder:
            continue
        tt = (x.get("transfer_type") or "")
        rt = "acquisition" if tt == "acquisition" else "territory_license"
        if (did, holder) in holder_seen:
            continue
        terms = x.get("deal_value_notes") or x.get("transfer_notes")
        add({"drug_id": did, "holder_company_id": holder, "right_type": rt,
             "territory": x.get("geographic_scope"), "terms": terms,
             "source": f"asset_transfer_history#{x['id']}", "source_url": x.get("source_url")})

    # breakdown
    from collections import Counter
    by_rt = Counter((r["right_type"], r["source"].split("#")[0]) for r in new)
    print(f"candidate new rows: {len(new)}")
    for (rt, src), n in sorted(by_rt.items()):
        print(f"  {rt:16s} <- {src:28s} {n}")

    inserted = post(new)
    print(f"inserted: {inserted}")


if __name__ == "__main__":
    main()
