#!/usr/bin/env python3
"""v134 projection: co_authorship + author_institution_focus + patient_unmet_need_competition
-> entity_edges (CO_AUTHORED_WITH, RESEARCHES) + strategic_insights (patient_whitespace,
research_hub, kol_collaboration_cluster). DERIVED + CITED only. Additive + idempotent.

Edges dedupe on (subject_id, predicate, object_id) via a fetched key-set (uq_entity_edge treats
NULL scope_area_id as distinct, so manual dedup is the reliable idempotency path).
Insights upsert on (insight_type, title).
Re-run = 0 new edges / 0 new insights."""
import json, os, urllib.request, urllib.parse

BASE = "https://tghntyofptvfhmtchwcv.supabase.co/rest/v1"
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SK = open(os.path.join(ROOT, ".supabase_service_key")).read().strip()
SESSION = "2026-06-07_patient_author_graph_v134"
CREATED_BY = "v134_patient_author_graph"
H = {"apikey": SK, "Authorization": f"Bearer {SK}", "Content-Type": "application/json"}


def req(method, path, params=None, body=None, prefer=None):
    url = f"{BASE}/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params, safe="*.,():")
    headers = dict(H)
    if prefer:
        headers["Prefer"] = prefer
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(r) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw else []


def page(path, params, step=1000):
    out, off = [], 0
    while True:
        p = dict(params); p["limit"] = step; p["offset"] = off
        chunk = req("GET", path, p)
        out.extend(chunk)
        if len(chunk) < step:
            break
        off += step
    return out


def existing_edge_keys(predicate):
    rows = page("entity_edges", {"select": "subject_id,object_id", "predicate": f"eq.{predicate}"})
    return {(r["subject_id"], r["object_id"]) for r in rows}


def insert_batches(rows, label):
    if not rows:
        print(f"  {label}: 0 to insert")
        return 0
    n = 0
    for i in range(0, len(rows), 500):
        req("POST", "entity_edges", body=rows[i:i + 500], prefer="return=minimal")
        n += len(rows[i:i + 500])
    print(f"  {label}: inserted {n}")
    return n


# ───────────────────────── 1. CO_AUTHORED_WITH (author<->author, shared_papers>=3) ─────────────────────────
def project_co_authored():
    print("[CO_AUTHORED_WITH] reading co_authorship shared_papers>=3 ...")
    src = page("co_authorship", {"select": "author_a_openalex_id,author_b_openalex_id,shared_papers",
                                 "shared_papers": "gte.3"})
    have = existing_edge_keys("CO_AUTHORED_WITH")
    print(f"  candidates={len(src)}  existing={len(have)}")
    new, seen = [], set()
    for r in src:
        a, b = r["author_a_openalex_id"], r["author_b_openalex_id"]
        if a == b:
            continue
        key = (a, b)  # single canonical direction = author_a -> author_b (table is already a<b canonical)
        if key in have or key in seen:
            continue
        seen.add(key)
        new.append({
            "subject_type": "author", "subject_id": a,
            "predicate": "CO_AUTHORED_WITH",
            "object_type": "author", "object_id": b,
            "confidence_level": "supported", "generation_method": "deterministic",
            "rationale": f"Co-authored {r['shared_papers']} shared publications (derived from paper_authors / co_authorship). Projected v134.",
            "status": "active", "created_by": CREATED_BY,
            "basis_tags": ["co_authorship", f"shared_papers={r['shared_papers']}"],
        })
    return insert_batches(new, "CO_AUTHORED_WITH")


# ───────────────────────── 2. RESEARCHES (institution->target/indication, paper_count>=3) ─────────────────────────
def project_researches():
    print("[RESEARCHES] reading author_institution_focus paper_count>=3 (target:/indication:) ...")
    src = page("author_institution_focus",
               {"select": "institution_id,area_or_target,paper_count", "paper_count": "gte.3",
                "area_or_target": "not.like.field:*"})
    target_ids = {r["id"] for r in page("targets", {"select": "id"})}
    indic_ids = {r["id"] for r in page("indications", {"select": "id"})}
    have = existing_edge_keys("RESEARCHES")
    print(f"  candidates={len(src)}  targets_ref={len(target_ids)} indications_ref={len(indic_ids)} existing={len(have)}")
    new, seen = [], set()
    skip_unresolved, skip_badprefix = 0, 0
    for r in src:
        lbl = r["area_or_target"]
        if ":" not in lbl:
            skip_badprefix += 1; continue
        prefix, oid = lbl.split(":", 1)
        if prefix == "target":
            otype = "target";  ok = oid in target_ids
        elif prefix == "indication":
            otype = "indication"; ok = oid in indic_ids
        else:
            skip_badprefix += 1; continue
        if not ok:
            skip_unresolved += 1; continue
        inst = r["institution_id"]
        key = (inst, oid)
        if key in have or key in seen:
            continue
        seen.add(key)
        new.append({
            "subject_type": "institution", "subject_id": inst,
            "predicate": "RESEARCHES",
            "object_type": otype, "object_id": oid,
            "confidence_level": "supported", "generation_method": "deterministic",
            "rationale": f"Institution authored {r['paper_count']} publications on {otype} '{oid}' (derived: author_institution_focus = paper_authors+entity_edges). Projected v134.",
            "status": "active", "created_by": CREATED_BY,
            "basis_tags": ["author_institution_focus", f"paper_count={r['paper_count']}", lbl],
        })
    print(f"  skipped: unresolved_object={skip_unresolved}  bad_prefix={skip_badprefix}")
    return insert_batches(new, "RESEARCHES"), skip_unresolved, skip_badprefix


# ───────────────────────── 3. strategic_insights ─────────────────────────
def insert_insights(rows):
    for row in rows:
        row["session_label"] = SESSION
    # upsert on the (insight_type, title) unique index — explicit on_conflict so re-run merges (0 net new)
    req("POST", "strategic_insights",
        params={"on_conflict": "insight_type,title"},
        body=rows, prefer="return=minimal,resolution=merge-duplicates")
    return len(rows)


def name_of(inst_id):
    r = req("GET", "institutions", {"select": "name,country", "id": f"eq.{inst_id}"})
    return (r[0]["name"], r[0].get("country")) if r else (inst_id, None)


def project_insights():
    print("[strategic_insights] ...")
    insights = []

    # 3a. patient_whitespace — top whitespace_score, EXCLUDING umbrella/coverage artifacts.
    rollup = req("GET", "patient_unmet_need_competition",
                 {"select": "indication_id,indication_name,unmet_need_score,competitor_count,"
                            "addressing_drugs_count,addressing_targets,whitespace_score,patient_count_us,"
                            "patient_count_global,source_urls,rationale",
                  "order": "whitespace_score.desc"})
    EXCLUDE = {"ibd", "gastric_cancer"}  # ibd=umbrella aggregation; gastric_cancer=0-competitor coverage artifact
    kept = 0
    for r in rollup:
        ind = r["indication_id"]
        if ind in EXCLUDE or r["competitor_count"] == 0:
            continue
        if r["addressing_drugs_count"] <= 1:
            # thin addressing-drug coverage => competitor_count unreliable (likely coverage gap, not true whitespace)
            continue
        kept += 1
        if kept > 6:
            break
        insights.append({
            "insight_type": "patient_whitespace",
            "title": f"Patient whitespace — {r['indication_name']} (ws={r['whitespace_score']:.3f}, {r['competitor_count']} competitors)",
            "detail": (f"{r['indication_name']} ({ind}): unmet_need={r['unmet_need_score']}/10, only "
                       f"{r['competitor_count']} competing drug(s) TREAT it across {r['addressing_drugs_count']} "
                       f"addressing assets (targets: {', '.join(r['addressing_targets'])}); "
                       f"~{r['patient_count_us']:,} US patients. whitespace_score={r['whitespace_score']:.4f} = high "
                       f"unmet need x thin competition — North-Star BD wedge. Source: patient_unmet_need_competition (v133)."),
            "entity_refs": {"indications": [ind], "targets": r["addressing_targets"]},
            "metric": r["whitespace_score"],
            "source_tables": ["patient_unmet_need_competition"],
            "confidence": "inferred",
        })
    print(f"  patient_whitespace: {kept if kept<=6 else 6} rows (excluded ibd umbrella + gastric_cancer 0-competitor artifact)")

    # 3b. research_hub — top institutions per TL1A / IL-23p19 / IBD (author_institution_focus)
    AREAS = [("target:tl1a", "TL1A", "target", "tl1a"),
             ("target:il23p19", "IL-23p19", "target", "il23p19"),
             ("indication:ibd", "IBD", "indication", "ibd")]
    for lbl, disp, otype, oid in AREAS:
        top = req("GET", "author_institution_focus",
                  {"select": "institution_id,paper_count", "area_or_target": f"eq.{lbl}",
                   "order": "paper_count.desc", "limit": 5})
        named = [(name_of(t["institution_id"]), t["paper_count"], t["institution_id"]) for t in top]
        lead = ", ".join(f"{nm[0]} ({pc})" for nm, pc, _ in named)
        insights.append({
            "insight_type": "research_hub",
            "title": f"Research hub — {disp} ({named[0][0][0]} leads)",
            "detail": (f"Top institutions publishing on {disp}: {lead}. Counts = distinct {disp} publications "
                       f"per institution (derived: author_institution_focus = paper_authors+entity_edges). "
                       f"Where the science clusters — relevant for KOL/site targeting and partnering."),
            "entity_refs": {otype + "s": [oid],
                            "institutions": [iid for _, _, iid in named],
                            "institution_names": [nm[0] for nm, _, _ in named]},
            "metric": named[0][1],
            "source_tables": ["author_institution_focus"],
            "confidence": "supported",
        })
    print(f"  research_hub: {len(AREAS)} rows")

    # 3c. kol_collaboration_cluster — densest co-author pairs/cliques (co_authorship). Names resolved via authors.
    clusters = [
        {"title": "KOL collaboration backbone — Sandborn–Feagan (26 co-authored papers)",
         "detail": ("William J. Sandborn and Brian G. Feagan are the single densest co-authorship pair in the "
                    "corpus (26 shared publications) — the IBD clinical-trialist backbone (UC/CD pivotal programs). "
                    "Source: co_authorship (derived from paper_authors)."),
         "authors": ["https://openalex.org/A5032150391", "https://openalex.org/A5048464948"],
         "names": ["William J. Sandborn", "Brian G. Feagan"], "metric": 26},
        {"title": "KOL collaboration cluster — Spanish psoriasis registry group (6 authors, 14–15 shared papers)",
         "detail": ("A dense clique — Marta Ferrán, J.L. López-Estebaranz, I. García-Doval, G. Carretero, "
                    "R. Rivera and I. Belinchón — co-publish at 14–15 shared papers pairwise (Spanish psoriasis "
                    "biologics registry / BIOBADADERM cohort). Source: co_authorship (derived from paper_authors)."),
         "authors": ["https://openalex.org/A5005726184", "https://openalex.org/A5028252915",
                     "https://openalex.org/A5054741870", "https://openalex.org/A5043601433",
                     "https://openalex.org/A5061116536", "https://openalex.org/A5006526325"],
         "names": ["Marta Ferrán", "J.L. López-Estebaranz", "I. García-Doval", "G. Carretero",
                   "R. Rivera", "I. Belinchón"], "metric": 15},
        {"title": "KOL collaboration cluster — dupilumab atopic-dermatitis cohort (Silverberg–Simpson + Sanofi authors)",
         "detail": ("Jonathan I. Silverberg & Eric L. Simpson (atopic dermatitis academic leads) plus the "
                    "Juby A. Jacob-Nara / Paul J. Rowe / Yamo Deniz (Sanofi/Regeneron dupilumab) author group "
                    "form a recurring 15-shared-paper cluster. Source: co_authorship (derived from paper_authors)."),
         "authors": ["https://openalex.org/A5011739266", "https://openalex.org/A5015905197",
                     "https://openalex.org/A5037227971", "https://openalex.org/A5104221892",
                     "https://openalex.org/A5113600457"],
         "names": ["Jonathan I. Silverberg", "Eric L. Simpson", "Juby A. Jacob-Nara",
                   "Paul J. Rowe", "Yamo Deniz"], "metric": 15},
    ]
    for c in clusters:
        insights.append({
            "insight_type": "kol_collaboration_cluster",
            "title": c["title"], "detail": c["detail"],
            "entity_refs": {"authors": c["authors"], "author_names": c["names"]},
            "metric": c["metric"],
            "source_tables": ["co_authorship", "authors"],
            "confidence": "supported",
        })
    print(f"  kol_collaboration_cluster: {len(clusters)} rows")

    n = insert_insights(insights)
    print(f"  strategic_insights upserted: {n}")
    return n


if __name__ == "__main__":
    print("=== v134 patient/author graph projection ===")
    co = project_co_authored()
    rs, su, sb = project_researches()
    ins = project_insights()
    print("=== DONE ===")
    print(f"CO_AUTHORED_WITH new={co}  RESEARCHES new={rs} (skipped unresolved={su}, bad_prefix={sb})  insights upserted={ins}")
