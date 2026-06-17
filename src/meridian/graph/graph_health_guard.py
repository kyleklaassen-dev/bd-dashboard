#!/usr/bin/env python3
"""
graph_health_guard.py — standing graph-integrity enforcement (run weekly, post-harvest).

(1) CONNECTIVITY: reads v_graph_connectivity + checks dangling edges. Any orphan or
    dangling endpoint -> governance_violation 'graph_connectivity' (so disconnected
    data that slips in is caught automatically, not by manual inspection).
(2) EDGE QUALITY: flags INFERRED drug->target edges (e.g. noisy DGIdb calls) whose
    target is NOT in the drug's CURATED target set (confirmed/supported edges)
    -> governance_violation 'inferred_target_unverified' for human review. Keeps
    public-API noise from silently diluting the trusted-intelligence layer.

Idempotent: skips violations already open for the same rule+row. Read-mostly; only
writes governance_violations.

Usage: python3 src/meridian/graph/graph_health_guard.py [--dry-run]
Env:   SUPABASE_URL, SUPABASE_SERVICE_KEY
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from database import client as c

DRY = "--dry-run" in sys.argv


def _open_violations(rule):
    return {str(v.get("row_id")) for v in c.select_all(
        "governance_violations", {"select": "row_id", "rule_name": f"eq.{rule}", "resolved": "eq.false"})}


def check_connectivity():
    # target_* tables expose target_slug-null as "drug_orphans" — those are untracked
    # OFF-targets (intentional), so they're coverage info, NOT hard orphans.
    TARGET_TBLS = {"target_disease_associations", "target_proteins", "target_safety"}
    rows = c.select_all("v_graph_connectivity", {"select": "tbl,rows,drug_orphans,nct_orphans"})
    target_cov = [r for r in rows if r["tbl"] in TARGET_TBLS]
    print("target_slug coverage (info): " + ", ".join(
        f"{r['tbl']} {r['rows']-(r.get('drug_orphans') or 0)}/{r['rows']}" for r in target_cov))
    offenders = [r for r in rows if r["tbl"] not in TARGET_TBLS
                 and ((r.get("drug_orphans") or 0) or (r.get("nct_orphans") or 0))]
    # dangling drug->publication edges
    pubs = {p["pmid"] for p in c.select_all("publications", {"select": "pmid"}) if p.get("pmid")}
    dangling = sum(1 for e in c.select_all("entity_edges",
                   {"select": "object_id", "predicate": "eq.STUDIES", "object_type": "eq.publication"})
                   if e["object_id"] not in pubs)
    viol = []
    if offenders:
        desc = "; ".join(f"{r['tbl']}: {(r.get('drug_orphans') or 0)+(r.get('nct_orphans') or 0)} orphans" for r in offenders)
        viol.append(dict(table_name="(multiple)", row_id="connectivity", rule_name="graph_connectivity",
                         description=f"Orphan rows detected: {desc}"))
    if dangling:
        viol.append(dict(table_name="entity_edges", row_id="dangling_pub_edges", rule_name="graph_connectivity",
                         description=f"{dangling} drug->publication edges point to missing publication nodes"))
    existing = _open_violations("graph_connectivity")
    new = [v for v in viol if v["row_id"] not in existing]
    print(f"connectivity: {len(offenders)} orphan tables, {dangling} dangling edges -> {len(new)} new violations")
    if new and not DRY:
        c.insert("governance_violations", new)
    return len(new)


def check_edge_quality():
    edges = c.select_all("entity_edges", {"select": "id,subject_id,object_id,confidence_level",
                                          "predicate": "eq.TARGETS"})
    curated, inferred = {}, []
    for e in edges:
        if e.get("confidence_level") in ("confirmed", "supported"):
            curated.setdefault(e["subject_id"], set()).add(e["object_id"])
        elif e.get("confidence_level") == "inferred":
            inferred.append(e)
    existing = _open_violations("inferred_target_unverified")
    viol = []
    for e in inferred:
        d = e["subject_id"]
        if d in curated and e["object_id"] not in curated[d] and str(e["id"]) not in existing:
            viol.append(dict(table_name="entity_edges", row_id=str(e["id"]),
                rule_name="inferred_target_unverified",
                description=f"{d} has an INFERRED TARGETS edge to '{e['object_id']}' not in its curated targets "
                            f"{sorted(curated[d])} — review (likely noisy auto-API edge)."))
    print(f"edge quality: {len(inferred)} inferred target edges, {len(viol)} flagged as unverified vs curated")
    if viol and not DRY:
        for i in range(0, len(viol), 200):
            c.insert("governance_violations", viol[i:i+200])
    return len(viol)


import datetime, json

STALE_DAYS = 180  # re-verify edges not touched in this many days


def decay_edges():
    """Mark aging edges 'needs_revalidation' so stale relationships surface for re-check.
    No-op while the DB is young; activates automatically as edges age past STALE_DAYS."""
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=STALE_DAYS)).isoformat()
    stale = c.select_all("entity_edges", {"select": "id", "updated_at": f"lt.{cutoff}",
                                          "staleness_status": "eq.fresh"})
    print(f"edge decay: {len(stale)} edges older than {STALE_DAYS}d -> needs_revalidation")
    if stale and not DRY:
        for i in range(0, len(stale), 200):
            ids = ",".join(s["id"] for s in stale[i:i+200])
            c.update("entity_edges", f"id=in.({ids})", {"staleness_status": "needs_revalidation"})
    return len(stale)


def write_digest(conn_viol, dangling_now, stale_edges):
    edge_counts = {}
    for e in c.select_all("entity_edges", {"select": "predicate"}):
        edge_counts[e["predicate"]] = edge_counts.get(e["predicate"], 0) + 1
    cov = {}
    for r in c.select_all("v_node_coverage", {"select": "source_coverage"}):
        k = str(r["source_coverage"]); cov[k] = cov.get(k, 0) + 1
    open_viol = len(c.select_all("governance_violations", {"select": "id", "resolved": "eq.false"}))
    digest = dict(id=1, connectivity_ok=(conn_viol == 0 and dangling_now == 0),
                  orphan_count=0 if conn_viol == 0 else None, dangling_count=dangling_now,
                  stale_edges=stale_edges, open_violations=open_viol,
                  edge_counts=edge_counts, node_coverage=cov,
                  computed_at=datetime.datetime.utcnow().isoformat())
    print(f"digest: connectivity_ok={digest['connectivity_ok']} edges={sum(edge_counts.values())} open_violations={open_viol}")
    if not DRY:
        c.insert("graph_health_digest", [digest], on_conflict="id")


if __name__ == "__main__":
    print("=== graph health guard" + (" (DRY)" if DRY else "") + " ===")
    n1 = check_connectivity()
    n2 = check_edge_quality()
    n3 = decay_edges()
    # recompute dangling for the digest
    pubs = {p["pmid"] for p in c.select_all("publications", {"select": "pmid"}) if p.get("pmid")}
    dangling_now = sum(1 for e in c.select_all("entity_edges",
                       {"select": "object_id", "predicate": "eq.STUDIES", "object_type": "eq.publication"})
                       if e["object_id"] not in pubs)
    write_digest(n1, dangling_now, n3)
    print(f"DONE. connectivity violations: {n1} | edge-quality flags: {n2} | decayed: {n3}")
    print("HEALTHY" if (n1 == 0 and dangling_now == 0) else "ATTENTION: connectivity issues")
