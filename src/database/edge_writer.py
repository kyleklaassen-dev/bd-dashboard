#!/usr/bin/env python3
"""
src/database/edge_writer.py — the SINGLE writer for `entity_edges`.
==================================================================
Only approved path to create knowledge-graph edges (Constitution §4, ADR-007/009/010).
Enforces the CHECK-constraint vocabulary (predicate, generation_method) and is
idempotent via the entity_edges_subj_pred_obj_uniq constraint (on_conflict).
Validates that both endpoints exist. Dry-run capable.
"""
import sys, pathlib
_BASE = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BASE / "src" / "database"))
import client

# Allowed vocab (keep in sync with the entity_edges CHECK constraints — ADR-007).
PREDICATES = {"TARGETS", "COMPETES_WITH", "DEVELOPED_BY", "PARTNERED_WITH", "LICENSED_FROM",
              "ACQUIRED", "APPROVED_IN", "AFFECTED_BY", "ACTIVE_IN", "CO_DEVELOPS",
              "TERMINATED", "SUPPLIES", "AUTHORED", "ACTIVE_IN"}
GEN_METHODS = {"deterministic", "manual"}
NODE_TYPES = {"drug", "company", "target", "indication", "patient", "geography"}


class EdgeWriter:
    def __init__(self, dry_run=False, verify_endpoints=True):
        self.dry_run = dry_run
        self.verify_endpoints = verify_endpoints
        self._known = {}

    def _exists(self, ntype, nid):
        table = {"drug": "drugs", "company": "companies", "target": "targets",
                 "indication": "indications"}.get(ntype)
        if not table:
            return True  # patient/geography ids are synthetic; skip verification
        if (ntype, nid) not in self._known:
            self._known[(ntype, nid)] = bool(client.select(table, {"id": f"eq.{nid}", "select": "id"}))
        return self._known[(ntype, nid)]

    def check(self, e):
        errs = []
        if e.get("predicate") not in PREDICATES:
            errs.append(f"predicate '{e.get('predicate')}' not in allowed set")
        if e.get("generation_method", "deterministic") not in GEN_METHODS:
            errs.append(f"generation_method '{e.get('generation_method')}' invalid")
        for side in ("subject", "object"):
            if e.get(f"{side}_type") not in NODE_TYPES:
                errs.append(f"{side}_type '{e.get(f'{side}_type')}' invalid")
        if self.verify_endpoints and not errs:
            if not self._exists(e["subject_type"], e["subject_id"]):
                errs.append(f"subject {e['subject_type']}:{e['subject_id']} does not exist")
            if not self._exists(e["object_type"], e["object_id"]):
                errs.append(f"object {e['object_type']}:{e['object_id']} does not exist")
        return errs

    def write(self, edges):
        edges = edges if isinstance(edges, list) else [edges]
        report = {"checked": len(edges), "rejected": [], "written": 0, "dry_run": self.dry_run}
        valid = []
        for e in edges:
            e.setdefault("generation_method", "deterministic")
            e.setdefault("status", "active")
            errs = self.check(e)
            if errs:
                report["rejected"].append({"edge": f"{e.get('subject_id')}-{e.get('predicate')}-{e.get('object_id')}", "errs": errs})
            else:
                valid.append(e)
        if self.dry_run or not valid:
            report["written"] = 0 if self.dry_run else 0
            report["would_write"] = len(valid)
            return report
        for i in range(0, len(valid), 200):
            code, body, _ = client.insert(
                "entity_edges", valid[i:i+200],
                on_conflict="subject_id,predicate,object_id",
                ignore_duplicates=True, return_rep=False)
            if code < 300:
                report["written"] += len(valid[i:i+200])
        return report


if __name__ == "__main__":
    w = EdgeWriter(dry_run=True)
    print("valid edge:", w.write({"subject_type": "drug", "subject_id": "sl325", "predicate": "TARGETS",
                                  "object_type": "target", "object_id": "dr3"}))
    print("bad predicate:", w.write({"subject_type": "drug", "subject_id": "sl325", "predicate": "FOO",
                                     "object_type": "target", "object_id": "dr3"}))
    print("missing node:", w.write({"subject_type": "drug", "subject_id": "nope999", "predicate": "TARGETS",
                                    "object_type": "target", "object_id": "dr3"}))
