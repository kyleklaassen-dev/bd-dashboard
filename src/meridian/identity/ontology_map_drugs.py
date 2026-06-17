#!/usr/bin/env python3
"""
ontology_map_drugs.py — map report-derived drugs into the ontology
==================================================================
Competitor/report drugs land in `drugs` but not in the ontology tables that feed
the area tabs and the structural graph (TREATS/ADDRESSES/area edges). This backfills:

  canonical_drugs  (mint CANON_DRUG_<md5> if drugs.canonical_drug_id is null)
  drug_targets     (drug -> target, parsed from drugs.target, resolved via targets)
  drug_indications (drug -> indication, parsed from drugs.indication_short)

The `trg_drug_areas_sync_ig` trigger syncs drug_areas on insert. Run
materialize_structural_edges.py afterwards for the TREATS/ADDRESSES edges.
Idempotent (ignore-duplicates). Scope: catalog_category='Competitor' or
data_source in (deep_enrich_intel, discovery_queue), unmapped, with a target.

Run: SUPABASE_SERVICE_KEY=... python3 scripts/ontology_map_drugs.py
"""
import os, re, hashlib, pathlib, requests

BASE = pathlib.Path(__file__).resolve().parents[3]
URL = os.environ.get("SUPABASE_URL", "https://tghntyofptvfhmtchwcv.supabase.co")
KEY = os.environ.get("SUPABASE_SERVICE_KEY") or (BASE / ".supabase_service_key").read_text().strip()
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
norm = lambda s: re.sub(r"[^a-z0-9]", "", str(s or "").lower())

def getall(t, p):
    out, s = [], 0
    while True:
        r = requests.get(f"{URL}/rest/v1/{t}", headers={**H, "Range": f"{s}-{s+999}"}, params=p)
        d = r.json() if r.status_code in (200, 206) else []
        out += d
        if len(d) < 1000: break
        s += 1000
    return out

def post(t, row):
    return requests.post(f"{URL}/rest/v1/{t}", headers={**H, "Prefer": "return=minimal,resolution=ignore-duplicates"}, json=row).status_code in (200, 201, 204, 409)
def patch(t, q, row):
    return requests.patch(f"{URL}/rest/v1/{t}?{q}", headers={**H, "Prefer": "return=minimal"}, json=row).status_code in (200, 204)

def main():
    tmap = {}
    for t in getall("targets", {"select": "id,label,gene_symbol,alt_names,full_name"}):
        for k in [t.get("id"), t.get("label"), t.get("gene_symbol"), t.get("full_name")] + (t.get("alt_names") or []):
            if k: tmap[norm(k)] = t["id"]
    imap = {"ad": "ad", "ulcerativecolitis": "uc", "crohnsdisease": "cd", "crohn": "cd",
            "atopicdermatitis": "ad", "psoriaticarthritis": "psa"}
    for i in getall("indications", {"select": "id,name,abbreviation"}):
        for k in [i.get("id"), i.get("abbreviation"), i.get("name")]:
            if k: imap[norm(k)] = i["id"]
    res_t = lambda s: list(dict.fromkeys(tmap[norm(x)] for x in re.split(r"[×x/+]|,|\band\b", s or "") if norm(x) in tmap))
    res_i = lambda s: list(dict.fromkeys(imap[norm(x)] for x in re.split(r"[·/,()]|\band\b", s or "") if norm(x) in imap))

    mapped = {e["drug_id"] for e in getall("drug_targets", {"select": "drug_id"})}
    drugs = getall("drugs", {"select": "id,name,display_name,modality,mechanism,target,indication_short,catalog_category,data_source,canonical_drug_id"})
    cand = [d for d in drugs if d["id"] not in mapped and d.get("target") and
            (d.get("catalog_category") == "Competitor" or d.get("data_source") in ("deep_enrich_intel", "discovery_queue"))]
    nc = nt = ni = 0
    for d in cand:
        canon = d.get("canonical_drug_id")
        if not canon:
            canon = "CANON_DRUG_" + hashlib.md5(d["id"].encode()).hexdigest()[:8].upper()
            post("canonical_drugs", {"canonical_id": canon, "canonical_name": d.get("display_name") or d["name"],
                                     "drug_class": d.get("modality") or "mab", "mechanism": d.get("mechanism"),
                                     "target": d.get("target"), "is_active": True, "confidence_score": 80})
            patch("drugs", f"id=eq.{d['id']}", {"canonical_drug_id": canon}); nc += 1
        for tid in res_t(d.get("target")):
            if post("drug_targets", {"drug_id": d["id"], "target_id": tid, "canonical_drug_id": canon, "target_role": "primary",
                                     "source_type": "structured_fk", "extraction_method": "tier1_structured", "confidence_level": "B",
                                     "confidence_score": 80, "review_status": "auto_confirmed", "created_by": "ontology_backfill", "confidence": "model"}): nt += 1
        for iid in res_i(d.get("indication_short")):
            if post("drug_indications", {"drug_id": d["id"], "indication_id": iid, "canonical_drug_id": canon,
                                         "source_type": "pattern_match", "extraction_method": "tier3_pattern", "confidence_level": "B",
                                         "confidence_score": 80, "review_status": "auto_confirmed", "created_by": "ontology_backfill", "confidence": "model"}): ni += 1
    print(f"ontology_map: canonicals {nc}, drug_targets {nt}, drug_indications {ni} over {len(cand)} drugs")

if __name__ == "__main__":
    main()
