#!/usr/bin/env python3
"""v132 author-network projection: co-authorship, institution focus, KOL ORCID disambiguation.
DERIVED / FREE only. Additive, idempotent, resolve-or-skip, no fabrication."""
import json, urllib.request, urllib.parse, itertools, collections, os, sys

BASE = "https://tghntyofptvfhmtchwcv.supabase.co/rest/v1"
SK = open("/sessions/peaceful-ecstatic-bardeen/mnt/BD Platform/.supabase_service_key").read().strip()
H = {"apikey": SK, "Authorization": f"Bearer {SK}", "User-Agent": "curl/8", "Content-Type": "application/json"}

def get_all(path, select, extra=""):
    rows, off = [], 0
    while True:
        url = f"{BASE}/{path}?select={urllib.parse.quote(select)}&limit=1000&offset={off}{extra}"
        req = urllib.request.Request(url, headers=H)
        d = json.load(urllib.request.urlopen(req))
        rows += d
        if len(d) < 1000: break
        off += 1000
    return rows

def post(path, payload, prefer="resolution=merge-duplicates,return=minimal"):
    h = dict(H); h["Prefer"] = prefer
    req = urllib.request.Request(f"{BASE}/{path}", data=json.dumps(payload).encode(), headers=h, method="POST")
    try:
        r = urllib.request.urlopen(req); return r.getcode(), r.read().decode()[:200]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]

print("Loading source tables...", file=sys.stderr)
authors = get_all("authors", "openalex_id,full_name,normalized_name,orcid,works_count")
paper_authors = get_all("paper_authors", "pmid,author_openalex_id,author_position,institution_id")
institutions = get_all("institutions", "id,name,normalized_name")
kols = get_all("kols", "id,name,normalized_name,primary_institution_id,orcid,author_openalex_id")
edges_reported = get_all("entity_edges", "subject_type,subject_id,object_id", "&predicate=eq.REPORTED_IN&object_type=eq.publication")
edges_targets = get_all("entity_edges", "subject_id,object_id", "&predicate=eq.TARGETS")
edges_treats = get_all("entity_edges", "subject_id,object_id", "&predicate=in.(TREATS,TESTED_IN,APPROVED_FOR)")
edges_studies = get_all("entity_edges", "subject_id,object_id", "&predicate=eq.STUDIES")
pubs = get_all("publications", "pmid,fields_of_study")

print(f"authors={len(authors)} paper_authors={len(paper_authors)} inst={len(institutions)} kols={len(kols)}", file=sys.stderr)
print(f"edges: reported={len(edges_reported)} targets={len(edges_targets)} treats={len(edges_treats)} studies={len(edges_studies)} pubs={len(pubs)}", file=sys.stderr)

# ---- indexes ----
auth_by_oa = {a["openalex_id"]: a for a in authors if a.get("openalex_id")}
works_count = {a["openalex_id"]: (a.get("works_count") or 0) for a in authors if a.get("openalex_id")}
inst_by_id = {i["id"]: i for i in institutions}

# ===========================================================================
# 1. CO-AUTHORSHIP — high-signal authors (works_count>=3), >=2 shared papers
# ===========================================================================
HIGH = {oa for oa, wc in works_count.items() if wc >= 3}
print(f"high-signal authors (wc>=3): {len(HIGH)}", file=sys.stderr)

paper_to_authors = collections.defaultdict(set)
for pa in paper_authors:
    oa = pa.get("author_openalex_id")
    if oa and oa in HIGH:
        paper_to_authors[pa["pmid"]].add(oa)

pair_papers = collections.Counter()
for pmid, oas in paper_to_authors.items():
    if len(oas) < 2: continue
    for a, b in itertools.combinations(sorted(oas), 2):
        pair_papers[(a, b)] += 1

co_rows = [{"author_a_openalex_id": a, "author_b_openalex_id": b,
            "shared_papers": n, "source": "derived:paper_authors"}
           for (a, b), n in pair_papers.items() if n >= 2]
print(f"co_authorship rows to write: {len(co_rows)}", file=sys.stderr)

# densest 5
dense = sorted(co_rows, key=lambda r: -r["shared_papers"])[:5]
for r in dense:
    na = auth_by_oa.get(r["author_a_openalex_id"], {}).get("full_name", "?")
    nb = auth_by_oa.get(r["author_b_openalex_id"], {}).get("full_name", "?")
    print(f"  DENSE {r['shared_papers']}x  {na}  <->  {nb}", file=sys.stderr)

# ===========================================================================
# 2. INSTITUTION FOCUS
#    publication(pmid) <- REPORTED_IN <- drug/trial ; trial->STUDIES->drug
#    drug -> TARGETS target ; drug -> TREATS/TESTED_IN/APPROVED_FOR indication
#    fallback: publications.fields_of_study
# ===========================================================================
drug_targets = collections.defaultdict(set)
for e in edges_targets: drug_targets[e["subject_id"]].add(e["object_id"])
drug_inds = collections.defaultdict(set)
for e in edges_treats: drug_inds[e["subject_id"]].add(e["object_id"])
trial_drugs = collections.defaultdict(set)
for e in edges_studies: trial_drugs[e["subject_id"]].add(e["object_id"])

# pmid -> set of area_or_target labels
pmid_areas = collections.defaultdict(set)
for e in edges_reported:
    pmid = e["object_id"]; st = e["subject_type"]; sid = e["subject_id"]
    drugs = set()
    if st == "drug": drugs.add(sid)
    elif st == "trial": drugs |= trial_drugs.get(sid, set())
    for d in drugs:
        for t in drug_targets.get(d, set()): pmid_areas[pmid].add(f"target:{t}")
        for ind in drug_inds.get(d, set()): pmid_areas[pmid].add(f"indication:{ind}")

# fields_of_study fallback (skip the near-universal 'Medicine' noise label)
for p in pubs:
    fos = p.get("fields_of_study") or []
    for f in fos:
        if f and f.lower() != "medicine":
            pmid_areas[p["pmid"]].add(f"field:{f}")

# institution x area -> distinct papers
inst_area_papers = collections.defaultdict(set)
for pa in paper_authors:
    iid = pa.get("institution_id"); pmid = pa.get("pmid")
    if not iid or iid not in inst_by_id: continue
    for area in pmid_areas.get(pmid, ()):
        inst_area_papers[(iid, area)].add(pmid)

focus_rows = [{"institution_id": iid, "area_or_target": area,
               "paper_count": len(pmids), "source": "derived:paper_authors+entity_edges"}
              for (iid, area), pmids in inst_area_papers.items()]
print(f"author_institution_focus rows to write: {len(focus_rows)}", file=sys.stderr)

# TL1A / IL-23 / IBD anchors
def top_for(pred, label):
    cand = [r for r in focus_rows if pred(r["area_or_target"])]
    agg = collections.Counter()
    for r in cand: agg[r["institution_id"]] += r["paper_count"]
    print(f"  TOP institutions for {label}:", file=sys.stderr)
    for iid, n in agg.most_common(6):
        print(f"    {n:>4}  {inst_by_id.get(iid,{}).get('name','?')}", file=sys.stderr)

top_for(lambda a: a in ("target:tl1a","target:tnfsf15"), "TL1A")
top_for(lambda a: "il23" in a or "il-23" in a or a in ("target:il23p19","target:il23"), "IL-23")
top_for(lambda a: a in ("indication:cd","indication:uc","indication:ibd"), "IBD (CD/UC/IBD)")

# ===========================================================================
# 3. KOL ORCID / OPENALEX DISAMBIGUATION (corroborated by shared institution)
# ===========================================================================
# authors that publish from a given institution_id
author_insts = collections.defaultdict(set)
for pa in paper_authors:
    if pa.get("author_openalex_id") and pa.get("institution_id"):
        author_insts[pa["author_openalex_id"]].add(pa["institution_id"])

# normalized_name -> list of author records
authors_by_norm = collections.defaultdict(list)
for a in authors:
    nn = (a.get("normalized_name") or "").strip()
    if nn: authors_by_norm[nn].append(a)

corroborated, name_only_collision, no_match, already = [], [], [], []
kol_updates = []
for k in kols:
    if k.get("author_openalex_id"):  # idempotent: already resolved
        already.append(k); continue
    nn = (k.get("normalized_name") or "").strip()
    pid = k.get("primary_institution_id")
    cands = authors_by_norm.get(nn, [])
    if not cands:
        no_match.append(k); continue
    if not pid:
        name_only_collision.append((k, len(cands))); continue
    # require shared institution corroboration
    matched = [a for a in cands if pid in author_insts.get(a["openalex_id"], set())]
    if len(matched) == 1:
        a = matched[0]
        kol_updates.append((k["id"], a.get("orcid"), a["openalex_id"]))
        corroborated.append((k, a))
    elif len(matched) > 1:
        name_only_collision.append((k, len(matched)))  # ambiguous even w/ inst
    else:
        no_match.append(k)  # name matches but no institution corroboration -> skip

print(f"\nKOL disambiguation: corroborated={len(corroborated)} "
      f"ambiguous/collision={len(name_only_collision)} no-corroboration={len(no_match)} "
      f"already-resolved={len(already)}", file=sys.stderr)
for k, a in corroborated[:12]:
    print(f"  ✓ {k['name']}  ->  {a['full_name']} ({a['openalex_id'].split('/')[-1]}) orcid={a.get('orcid')}", file=sys.stderr)

# ---- WRITES ----
WRITE = "--write" in sys.argv
if not WRITE:
    print("\nDRY RUN (pass --write to persist).", file=sys.stderr)
    sys.exit(0)

print("\nWriting co_authorship...", file=sys.stderr)
for i in range(0, len(co_rows), 500):
    code, msg = post("co_authorship", co_rows[i:i+500],
                     "resolution=merge-duplicates,return=minimal")
    print(f"  batch {i}: {code} {msg}", file=sys.stderr)

print("Writing author_institution_focus...", file=sys.stderr)
for i in range(0, len(focus_rows), 500):
    code, msg = post("author_institution_focus", focus_rows[i:i+500],
                     "resolution=merge-duplicates,return=minimal")
    print(f"  batch {i}: {code} {msg}", file=sys.stderr)

print("Updating kols...", file=sys.stderr)
ok = 0
for kid, orcid, oaid in kol_updates:
    body = {"author_openalex_id": oaid}
    if orcid: body["orcid"] = orcid
    h = dict(H); h["Prefer"] = "return=minimal"
    req = urllib.request.Request(f"{BASE}/kols?id=eq.{kid}", data=json.dumps(body).encode(), headers=h, method="PATCH")
    try:
        urllib.request.urlopen(req); ok += 1
    except urllib.error.HTTPError as e:
        print(f"  kol {kid} fail: {e.code} {e.read().decode()[:200]}", file=sys.stderr)
print(f"  kols updated: {ok}", file=sys.stderr)
print("DONE.", file=sys.stderr)
