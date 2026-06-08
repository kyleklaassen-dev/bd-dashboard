#!/usr/bin/env python3
"""v133 PATIENT whitespace rollup — apex of Meridian's North Star.

Derives patient_unmet_need_competition from:
  - indication_patient_intelligence  (unmet need + patient numbers + source_urls)
  - drug_indications + entity_edges TREATS   (competition: distinct drugs treating the disease)
  - entity_edges ADDRESSES                    (targets addressing the disease)
  - drug_targets                              (mechanism-level competition)

whitespace_score = (unmet_need_score/10) / ln(2 + competitor_count)

FREE / derived only. Idempotent (UNIQUE(indication_id) upsert; re-run = 0 changed rows).
resolve-or-skip: indication_name -> canonical indications.id; unmatched are reported + skipped
(no fabrication). 'Target Area' / 'Broad' rows are target rollups, not diseases -> skipped.
"""
import json, math, os, re, urllib.request, urllib.parse

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "https://tghntyofptvfhmtchwcv.supabase.co/rest/v1"
SK = open(os.path.join(BASE, ".supabase_service_key")).read().strip()
H = {"apikey": SK, "Authorization": f"Bearer {SK}", "Content-Type": "application/json"}

def get(path):
    out, off = [], 0
    while True:
        sep = "&" if "?" in path else "?"
        req = urllib.request.Request(f"{URL}/{path}{sep}limit=1000&offset={off}", headers=H)
        chunk = json.loads(urllib.request.urlopen(req).read())
        out += chunk
        if len(chunk) < 1000:
            break
        off += 1000
    return out

def norm(s):
    s = (s or "").lower()
    s = re.sub(r"\(.*?\)", " ", s)          # drop parentheticals
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

# ---- load ----
pintel = get("indication_patient_intelligence?select=indication_name,unmet_need_score,patient_count_us,patient_count_global,market_size_usd_bn,source_urls")
inds = get("indications?select=id,name")
di = get("drug_indications?select=drug_id,indication_id")
treats = get("entity_edges?select=subject_id,object_id&predicate=eq.TREATS&object_type=eq.indication")
addr = get("entity_edges?select=subject_id,object_id&predicate=eq.ADDRESSES&object_type=eq.indication")
dt = get("drug_targets?select=drug_id,target_id")

by_norm = {norm(i["name"]): i["id"] for i in inds}
by_id = {i["id"]: i["name"] for i in inds}

# Manual aliases for patient-intel names whose phrasing differs from master.
ALIAS = {
    "severe asthma": "asthma",
    "gastric gej adenocarcinoma fgfr2b": "gastric_cancer",
    "systemic lupus erythematosus": "sle",
    "cidp": "cidp",
    "copd": "copd",                 # "COPD (Type-2 / eosinophilic)" -> paren stripped -> "copd"
    "eosinophilic esophagitis": "eoe",
    "plaque psoriasis": "psoriasis",
    "ibd": "ibd",                   # "IBD (Inflammatory Bowel Disease)" -> paren stripped -> "ibd"
}

def resolve(name):
    n = norm(name)
    if n in by_norm:
        return by_norm[n]
    if n in ALIAS:
        return ALIAS[n]
    # Target-area / broad rollups are not diseases.
    if "target area" in n or "broad" in n:
        return None
    return None

# competition: distinct drugs treating each indication (union of both sources)
treat_drugs = {}
for r in di:
    treat_drugs.setdefault(r["indication_id"], set()).add(r["drug_id"])
for r in treats:
    treat_drugs.setdefault(r["object_id"], set()).add(r["subject_id"])

# addressing targets per indication
addr_targets = {}
for r in addr:
    addr_targets.setdefault(r["object_id"], set()).add(r["subject_id"])

# drugs per target (for mechanism-level competition)
target_drugs = {}
for r in dt:
    target_drugs.setdefault(r["target_id"], set()).add(r["drug_id"])

FORMULA = "whitespace_score = (unmet_need_score/10) / ln(2 + competitor_count)"

rows, matched, unmatched = [], [], []
for p in pintel:
    iid = resolve(p["indication_name"])
    if not iid or iid not in by_id:
        unmatched.append(p["indication_name"])
        continue
    matched.append((p["indication_name"], iid))
    comp = treat_drugs.get(iid, set())
    comp_n = len(comp)
    tgts = sorted(addr_targets.get(iid, set()))
    adrugs = set()
    for t in tgts:
        adrugs |= target_drugs.get(t, set())
    uns = p.get("unmet_need_score")
    ws = round((uns / 10.0) / math.log(2 + comp_n), 4) if uns is not None else None
    rationale = (
        f"{FORMULA}; unmet_need_score={uns}, competitor_count={comp_n} "
        f"(distinct drugs TREAT via drug_indications+entity_edges TREATS), "
        f"addressing_targets={len(tgts)}, addressing_drugs={len(adrugs)}. "
        "Derived metric (v133); high unmet need x thin competition = BD whitespace wedge."
    )
    rows.append({
        "indication_id": iid,
        "indication_name": by_id[iid],
        "unmet_need_score": uns,
        "patient_count_us": p.get("patient_count_us"),
        "patient_count_global": p.get("patient_count_global"),
        "market_size_usd_bn": p.get("market_size_usd_bn"),
        "competitor_count": comp_n,
        "addressing_targets": tgts,
        "addressing_drugs_count": len(adrugs),
        "whitespace_score": ws,
        "rationale": rationale,
        "source_urls": p.get("source_urls") or [],
    })

# de-dup by indication_id (multiple patient-intel rows could map to one canonical id)
seen = {}
for r in rows:
    seen[r["indication_id"]] = r  # last wins (deterministic; none expected here)
rows = list(seen.values())

# ---- upsert (idempotent on indication_id) ----
req = urllib.request.Request(
    f"{URL}/patient_unmet_need_competition?on_conflict=indication_id",
    data=json.dumps(rows).encode(),
    headers={**H, "Prefer": "resolution=merge-duplicates,return=representation"},
    method="POST",
)
resp = json.loads(urllib.request.urlopen(req).read())

print(f"Formula: {FORMULA}")
print(f"patient-intel rows: {len(pintel)} | matched: {len(matched)} | unmatched(skipped): {len(unmatched)}")
print(f"upserted rows: {len(resp)}")
print("\nUNMATCHED (skipped, not diseases / no canonical id):")
for u in unmatched:
    print("  -", u)
print("\nTOP WHITESPACE (high unmet need, thin competition):")
for r in sorted([x for x in rows if x["whitespace_score"] is not None], key=lambda x: -x["whitespace_score"])[:12]:
    print(f"  {r['whitespace_score']:.3f}  {r['indication_name']:<42} unmet={r['unmet_need_score']} comp={r['competitor_count']} tgts={len(r['addressing_targets'])}")
print("\nMOST SATURATED (high competition):")
for r in sorted(rows, key=lambda x: -x["competitor_count"])[:8]:
    print(f"  comp={r['competitor_count']:<3} ws={r['whitespace_score']}  {r['indication_name']:<42} unmet={r['unmet_need_score']}")
