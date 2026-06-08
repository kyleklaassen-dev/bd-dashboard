#!/usr/bin/env python3
"""project_author_graph_v131.py — Author layer → entity_edges + strategic_insights.

DERIVED + CITED only. Additive + idempotent (app-level natural-key dedupe vs the
LIVE table). Resolve-or-skip; never fabricate identity. See migrations/v131_author_graph.sql.

Edges:
  AUTHORED  author(openalex_id) -> publication(pmid)
    SELECTIVE CAP: only paper_authors rows whose author is high-signal =
    corpus works_count >= 3 (recurring) OR author_position in ('first','last').

Insights:
  author_hub        top corpus authors by works_count            (authors+paper_authors)
  kol_dual_signal   investigators who are recurring authors       (kols+authors)
                    confidence='supported' only if shared-institution corroborated;
                    name-only -> 'inferred' (NOT an identity claim).
  seminal_evidence  top influential_citation_count among BD-relevant pubs
                    (REPORTED_IN-linked drug/trial, topic-filtered, instruments out)
                    (publications+trial_results)
"""
import urllib.request, urllib.parse, json, collections, sys, os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SK = open(os.path.join(BASE_DIR, ".supabase_service_key")).read().strip()
B = "https://tghntyofptvfhmtchwcv.supabase.co/rest/v1"
SESSION = "v131_author_graph"
CREATED_BY = "project_author_graph_v131"
DRY = "--write" not in sys.argv

H = {"apikey": SK, "Authorization": "Bearer " + SK}

def get(path):
    req = urllib.request.Request(B + path, headers=H)
    return json.load(urllib.request.urlopen(req))

def page(table, select, extra=""):
    out = []; off = 0
    while True:
        rows = get(f"/{table}?select={select}&limit=1000&offset={off}{extra}")
        if not rows: break
        out += rows; off += 1000
        if len(rows) < 1000: break
    return out

def post(path, rows):
    if not rows: return 0
    data = json.dumps(rows).encode()
    req = urllib.request.Request(B + path, data=data, method="POST",
        headers={**H, "Content-Type": "application/json", "Prefer": "return=minimal"})
    urllib.request.urlopen(req)
    return len(rows)

# ── load silver ──────────────────────────────────────────────────────────────
print("Loading silver...")
authors = page("authors", "openalex_id,works_count,full_name,orcid,normalized_name")
pa = page("paper_authors", "pmid,author_openalex_id,author_position,institution_id,raw_affiliation")
pubs = page("publications", "pmid,title,journal,pub_year,influential_citation_count,cited_by_count,mesh_terms,fields_of_study")
kols = page("kols", "id,name,normalized_name,primary_institution_id,trial_count,role")
ri = page("entity_edges", "subject_type,subject_id,object_id", "&predicate=eq.REPORTED_IN&object_type=eq.publication")

amap = {a["openalex_id"]: a for a in authors if a["openalex_id"]}
wc3 = {oid for oid, a in amap.items() if (a["works_count"] or 0) >= 3}
pmap = {str(p["pmid"]): p for p in pubs if p["pmid"]}
pubset = set(pmap)

# ── 1. AUTHORED edges (selective) ────────────────────────────────────────────
existing_authored = set()
for r in page("entity_edges", "subject_id,object_id", "&predicate=eq.AUTHORED&subject_type=eq.author"):
    existing_authored.add((r["subject_id"], str(r["object_id"])))

cand = {}
skip_noauthor = skip_nopub = skip_tail = 0
for r in pa:
    oid = r["author_openalex_id"]; pmid = str(r["pmid"]) if r["pmid"] is not None else None
    if not oid or oid not in amap: skip_noauthor += 1; continue
    if pmid not in pubset: skip_nopub += 1; continue
    if not ((oid in wc3) or (r["author_position"] in ("first", "last"))):
        skip_tail += 1; continue
    cand[(oid, pmid)] = r  # last write wins for rationale (position)

edge_rows = []
for (oid, pmid), r in cand.items():
    if (oid, pmid) in existing_authored: continue
    a = amap[oid]
    edge_rows.append({
        "subject_type": "author", "subject_id": oid, "predicate": "AUTHORED",
        "object_type": "publication", "object_id": pmid,
        "confidence_level": "confirmed", "generation_method": "deterministic",
        "source_url": oid if oid.startswith("http") else None,
        "created_by": CREATED_BY, "status": "active",
        "rationale": (f"{a['full_name']} authored publication PMID {pmid} "
                      f"(author_position={r['author_position']}, corpus works_count="
                      f"{a['works_count']}). High-signal cap: works_count>=3 OR first/last. "
                      f"Source: paper_authors (OpenAlex). Projected {SESSION}."),
    })

print(f"AUTHORED candidates(dedup pairs)={len(cand)}  new_edges={len(edge_rows)}  "
      f"already_present={len(cand)-len(edge_rows)}")
print(f"  skipped: no_author_resolve={skip_noauthor} no_pub_resolve={skip_nopub} "
      f"low_signal_tail(middle & wc<3)={skip_tail}  total_paper_authors={len(pa)}")

# ── insights helpers ─────────────────────────────────────────────────────────
existing_ins = set()
for s in page("strategic_insights", "insight_type,title"):
    existing_ins.add((s["insight_type"], s["title"]))
insight_rows = []
def add_insight(itype, title, detail, refs, metric, srcs, conf):
    if (itype, title) in existing_ins: return False
    insight_rows.append({
        "insight_type": itype, "title": title, "detail": detail,
        "entity_refs": refs, "metric": metric, "source_tables": srcs,
        "confidence": conf, "session_label": SESSION})
    existing_ins.add((itype, title)); return True

# author->institution set (for dual-signal corroboration)
auth_inst = collections.defaultdict(set)
for r in pa:
    if r["institution_id"]: auth_inst[r["author_openalex_id"]].add(r["institution_id"])

# ── 2. author_hub — top corpus authors by works_count ────────────────────────
top_auth = sorted([a for a in authors if a["openalex_id"]],
                  key=lambda a: (a["works_count"] or 0), reverse=True)[:8]
n_hub = 0
for a in top_auth:
    title = f"Literature KOL — {a['full_name']} ({a['works_count']} core-corpus papers)"
    detail = (f"{a['full_name']} authors {a['works_count']} papers in Meridian's core "
              f"literature corpus (OpenAlex works_count), among the most-published voices "
              f"across the tracked TL1A/IL-23/IBD & adjacent immunology literature. This is "
              f"a LITERATURE-derived KOL signal (authorship volume) that complements the "
              f"CT.gov trial-investigator kol_hub view — high publishing presence marks "
              f"thought-leadership and review/guideline influence distinct from trial PI roles. "
              f"Source: authors.works_count + paper_authors (OpenAlex).")
    refs = {"authors": [a["openalex_id"]]}
    if a["orcid"]: refs["orcid"] = [a["orcid"]]
    n_hub += add_insight("author_hub", title, detail, refs, float(a["works_count"] or 0),
                         ["authors", "paper_authors"], "supported")

# ── 3. kol_dual_signal — recurring author × investigator (76 overlaps) ────────
amap_by_norm = collections.defaultdict(list)
for a in authors: amap_by_norm[a["normalized_name"]].append(a)
dual = []
for k in kols:
    matches = amap_by_norm.get(k["normalized_name"])
    if not matches: continue
    best = max(matches, key=lambda a: (a["works_count"] or 0))
    if (best["works_count"] or 0) < 3: continue  # recurring only
    insts = auth_inst.get(best["openalex_id"], set())
    corrob = bool(k["primary_institution_id"]) and k["primary_institution_id"] in insts
    dual.append((k, best, corrob))
dual.sort(key=lambda d: -(d[1]["works_count"] or 0))
n_dual = 0; n_corrob = 0
for k, best, corrob in dual[:12]:
    if corrob: n_corrob += 1
    conf = "supported" if corrob else "inferred"
    corr_txt = ("Identity CORROBORATED via shared institution (kols.primary_institution_id "
                "matches a paper_authors institution for this author).") if corrob else \
               ("Name-only match (normalized name) — NOT asserted as a confirmed identity; "
                "same-name-different-person risk, no shared institution/ORCID corroboration "
                "found. Treat as inferred linkage.")
    title = f"KOL dual-signal — {k['name']} ({k['trial_count']} trials + {best['works_count']} papers)"
    detail = (f"{k['name']} appears BOTH as a CT.gov trial investigator (kols, "
              f"trial_count={k['trial_count']}) AND as a recurring author in the core literature "
              f"corpus (authors, works_count={best['works_count']}). Investigators who are also "
              f"prolific publishers are the strongest KOL signal — they shape both the evidence "
              f"base and clinical practice. {corr_txt} Source: kols + authors (OpenAlex).")
    refs = {"kols": [k["id"]], "authors": [best["openalex_id"]],
            "corroborated": corrob}
    if best["orcid"]: refs["orcid"] = [best["orcid"]]
    n_dual += add_insight("kol_dual_signal", title, detail, refs,
                          float(best["works_count"] or 0), ["kols", "authors"], conf)

# ── 4. seminal_evidence — top influential among BD-relevant pubs ──────────────
linked = collections.defaultdict(lambda: {"drugs": set(), "trials": set()})
for r in ri:
    key = "drugs" if r["subject_type"] == "drug" else "trials"
    linked[str(r["object_id"])][key].add(r["subject_id"])
KW = ["tl1a", "dr3", "tnfsf15", "il-23", "il23", "interleukin-23", "interleukin 23",
      "ustekinumab", "risankizumab", "guselkumab", "mirikizumab", "brazikumab",
      "crohn", "colitis", "inflammatory bowel", "ulcerative", "psoria",
      "atopic dermatitis", "il-4", "il-13", "thymic stromal", "tslp", "fcrn",
      "spondylo", "ibd", "il-33", "alarmin"]
INSTR = ["pittsburgh sleep", "perceived stress", "redcap", "montreal cognitive",
         "physical activity questionnaire", "eating questionnaire", "whoqol",
         "quality of life assessment", "nmda-receptor", "mcdonald criteria"]
def relevant(p):
    t = (p["title"] or "").lower()
    if any(x in t for x in INSTR): return False
    mesh = " ".join(p["mesh_terms"]).lower() if isinstance(p["mesh_terms"], list) else ""
    return any(k in (t + " " + mesh) for k in KW)
sem = []
for pmid, info in linked.items():
    p = pmap.get(pmid)
    if not p: continue
    direct = len(info["drugs"]) > 0
    if direct or relevant(p):
        sem.append((p, info, direct))
sem.sort(key=lambda x: (x[0]["influential_citation_count"] or -1), reverse=True)
n_sem = 0
for p, info, direct in sem[:10]:
    icc = p["influential_citation_count"]
    if icc is None or icc <= 0:  # only assert genuinely influential papers
        continue
    title = f"Seminal evidence — {(p['title'] or '')[:70].rstrip()} (infl. cites {icc})"
    drg = sorted(info["drugs"]); trl = sorted(info["trials"])
    link_txt = (f"Directly linked to BD asset(s) {drg}." if drg else
                f"Linked via REPORTED_IN to {len(trl)} tracked trial(s).")
    detail = (f"\"{p['title']}\" ({p['journal']}, {p['pub_year']}) carries "
              f"influential_citation_count={icc} (cited_by={p['cited_by_count']}), among the "
              f"highest of any BD-RELEVANT publication in the corpus (TL1A/IL-23/IBD & adjacent "
              f"immunology). {link_txt} This is the corrected 'seminal papers' view: the global "
              f"influence leaderboard is dominated by generic instrument papers (PSQI/REDCap/MoCA) "
              f"pulled in as trial reference citations; those are excluded here. "
              f"Source: publications (Semantic Scholar influence) + trial_results / REPORTED_IN edges.")
    refs = {"publications": [str(p["pmid"])]}
    if drg: refs["drugs"] = drg
    n_sem += add_insight("seminal_evidence", title, detail, refs, float(icc),
                         ["publications", "trial_results"], "confirmed")

print(f"\nINSIGHTS new: author_hub={n_hub} kol_dual_signal={n_dual} "
      f"(institution-corroborated={n_corrob}/{min(12,len(dual))}) seminal_evidence={n_sem}")
print(f"  recurring dual-signal candidates total={len(dual)} (of 76 name overlaps)")

# ── write ────────────────────────────────────────────────────────────────────
if DRY:
    print("\n[DRY-RUN] pass --write to insert. No rows written.")
    print(f"  would insert edges={len(edge_rows)} insights={len(insight_rows)}")
else:
    written = 0
    for i in range(0, len(edge_rows), 500):
        written += post("/entity_edges", edge_rows[i:i+500])
    print(f"\nInserted entity_edges: {written}")
    iw = post("/strategic_insights", insight_rows)
    print(f"Inserted strategic_insights: {iw}")
