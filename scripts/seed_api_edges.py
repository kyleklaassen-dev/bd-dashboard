#!/usr/bin/env python3
"""
seed_api_edges.py — connect the v149 API tables into the entity_edges graph.

Governed/deterministic (mirrors the existing 4 seeders): only creates an edge when
BOTH endpoints resolve unambiguously to existing nodes. Unresolved rows are skipped,
not guessed. Every edge carries source_url + generation_method.

Edges created:
  target  --ASSOCIATED_WITH--> indication   (from target_disease_associations / Open Targets)
  drug    --STUDIES-->          publication  (from literature_records / Europe PMC; pmid node)

Attribute tables (molecule_properties, drug_label_facts, trial_* detail) connect to
core entities via their drug_id / nct_id foreign keys and need no edge.

Usage: python3 scripts/seed_api_edges.py [--dry-run]
"""
import os, sys, datetime, uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from database import client as c

DRY = "--dry-run" in sys.argv
NOW = datetime.datetime.utcnow().isoformat()
NS = uuid.UUID("a7f1c0de-1111-4222-8333-0a1b2c3d4e5f")
_uid = lambda natural_key: str(uuid.uuid5(NS, natural_key))  # deterministic -> idempotent

# Open Targets HGNC symbol -> our target node slug (lowercase-direct fallback + curated)
TARGET_SYN = {
    "IL23A": "il23p19", "TNFSF15": "tl1a", "TNFRSF25": "dr3", "FCGRT": "fcrn",
    "IL4R": "il4ra", "CD40LG": "cd40l", "CD3D": "cd3", "IGHE": "ige",
    "IL1RL2": "il36r", "CRLF2": "tslpr", "TSLP": "tslp", "IL5RA": "il5ra",
    "IL31RA": "il31ra", "IFNAR1": "ifnar1",
}


def load_targets():
    rows = c.select_all("entity_edges", {"select": "object_id", "object_type": "eq.target"})
    return {r["object_id"] for r in rows}


def load_indication_resolver():
    res = {}
    for i in c.select_all("indications", {"select": "id,name"}):
        res[i["id"].lower()] = i["id"]
        if i.get("name"):
            res[i["name"].strip().lower()] = i["id"]
    for a in c.select_all("indication_aliases", {"select": "normalized_alias,indication_id"}):
        if a.get("normalized_alias"):
            res[a["normalized_alias"].strip().lower()] = a["indication_id"]
    return res


_CROSSWALK = None
def _crosswalk():
    """HGNC/token -> graph target slug, loaded from the target_crosswalk table (v154).
    This is the durable, growable mapping; TARGET_SYN is a fallback."""
    global _CROSSWALK
    if _CROSSWALK is None:
        try:
            _CROSSWALK = {r["symbol"].upper(): r["target_slug"]
                          for r in c.select_all("target_crosswalk", {"select": "symbol,target_slug"})}
        except Exception:
            _CROSSWALK = {}
    return _CROSSWALK


def resolve_target(sym, valid):
    # crosswalk table first (authoritative), then synonym map, then lowercase
    slug = _crosswalk().get((sym or "").upper()) or TARGET_SYN.get(sym, (sym or "").lower())
    return slug if slug in valid else None


def edge(natural_key, st, sid, pred, ot, oid, src, basis, conf):
    return dict(id=_uid(natural_key), subject_type=st, subject_id=sid, predicate=pred,
                object_type=ot, object_id=oid, source_url=src, basis_text=basis,
                confidence_level=conf, generation_method="deterministic",
                notes="api_harvest_v149", status="active", created_by="seed_api_edges",
                created_at=NOW, updated_at=NOW)


def seed_target_indication():
    valid = load_targets(); res = load_indication_resolver()
    rows = c.select_all("target_disease_associations",
                        {"select": "target_symbol,disease_label,efo_id,overall_score,source_url"})
    edges, skipped = [], 0
    for r in rows:
        tslug = resolve_target(r["target_symbol"], valid)
        ind = res.get((r.get("disease_label") or "").strip().lower())
        if not (tslug and ind):
            skipped += 1; continue
        sc = r.get("overall_score") or 0
        conf = "supported" if sc >= 0.5 else "inferred"   # OT = computational/genetic evidence
        edges.append(edge(f"OTASSOC_{tslug}_{ind}", "target", tslug, "ASSOCIATED_WITH",
                          "indication", ind, r.get("source_url"),
                          f"Open Targets overall association score {sc} (EFO {r.get('efo_id')})", conf))
    # de-dupe by id (multiple OT diseases can map to same indication)
    uniq = {e["id"]: e for e in edges}
    print(f"target→indication: {len(uniq)} edges, {skipped} unresolved/skipped")
    if uniq and not DRY:
        c.insert("entity_edges", list(uniq.values()), on_conflict="id")
    return len(uniq)


def seed_drug_publication():
    # literature_records was deprecated (folded into publications). drug->publication
    # edges are owned by the abstract/author pipeline; skip gracefully if table absent.
    rows = c.select("literature_records", {"select": "pmid,drug_id,source_url", "pmid": "not.is.null", "limit": "1"})
    if not rows:
        print("drug→publication: literature_records absent/empty — skipped (owned by abstract_fetcher)")
        return 0
    rows = c.select_all("literature_records", {"select": "pmid,drug_id,source_url", "pmid": "not.is.null"})
    edges = {}
    for r in rows:
        if not r.get("drug_id"):
            continue
        eid = f"LITSTUDIES_{r['drug_id']}_{r['pmid']}"
        edges[eid] = edge(eid, "drug", r["drug_id"], "STUDIES", "publication", r["pmid"],
                          r.get("source_url"), "Europe PMC literature match", "inferred")
    print(f"drug→publication: {len(edges)} edges")
    if edges and not DRY:
        for i in range(0, len(edges), 500):
            c.insert("entity_edges", list(edges.values())[i:i+500], on_conflict="id")
    return len(edges)


def seed_drug_target_from_interactions():
    """DGIdb drug→gene → drug --TARGETS--> target edges, where the gene symbol resolves
    to an existing target node (lowercase + the same TARGET_SYN map). Connects the
    pharmacology layer into the graph. IUPHAR target names are descriptive (not gene
    symbols) so they connect via drug_id FK only for now."""
    try:
        rows = c.select_all("dgidb_interactions", {"select": "drug_id,gene_name,interaction_type"})
    except Exception:
        print("dgidb_interactions absent — skipped"); return 0
    if not rows:
        print("drug→target (DGIdb): no rows yet — skipped"); return 0
    valid = load_targets()
    edges = {}
    for r in rows:
        if not (r.get("drug_id") and r.get("gene_name")):
            continue
        tslug = resolve_target(r["gene_name"], valid)
        if not tslug:
            continue
        e = edge(f"DGIDB_{r['drug_id']}_{tslug}", "drug", r["drug_id"], "TARGETS",
                 "target", tslug, "https://dgidb.org",
                 f"DGIdb drug-gene interaction ({r.get('interaction_type') or 'n/a'})", "inferred")
        edges[e["id"]] = e
    print(f"drug→target (DGIdb): {len(edges)} edges")
    if edges and not DRY:
        c.insert("entity_edges", list(edges.values()),
                 on_conflict="subject_id,predicate,object_id", ignore_duplicates=True)
    return len(edges)


if __name__ == "__main__":
    print("Seeding API→graph edges" + (" (DRY)" if DRY else ""))
    seed_target_indication()
    seed_drug_publication()
    seed_drug_target_from_interactions()
    print("Done.")
