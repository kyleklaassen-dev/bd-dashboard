#!/usr/bin/env python3
"""Materialize the structural entity graph into entity_edges (the triple store).

entity_edges already held the COMPETES_WITH / TARGETS / ACTIVE_IN edges but was
missing the structural backbone that makes the patient → indication → target →
drug → company chain traversable:

  TREATS       drug   -> indication   (from drug_indications)
  ADDRESSES    target -> indication   (derived: a drug targeting T treats I  ⇒  T addresses I)
  DEVELOPED_BY drug   -> company      (from drugs.company_id)

This script materializes those, idempotently. The normalized tables remain the
source of truth; these edges are the derived, traversable graph layer. Run after
the catalog changes. Idempotent — safe to schedule.

Run: python src/meridian/graph/materialize_structural_edges.py [--dry-run]
Env: SUPABASE_PAT, SUPABASE_URL
"""
import os
import sys
import json
import urllib.request

URL = os.environ.get("SUPABASE_URL", "https://tghntyofptvfhmtchwcv.supabase.co")
PROJECT = URL.replace("https://", "").split(".supabase.co")[0]
PAT = os.environ["SUPABASE_PAT"]
DRY = "--dry-run" in sys.argv

COMMON = ("generation_method,confidence_level,status,rationale,created_at,updated_at")

EDGES = {
    "TREATS": """
        INSERT INTO entity_edges (subject_type,subject_id,predicate,object_type,object_id,%s)
        SELECT DISTINCT 'drug',di.drug_id,'TREATS','indication',di.indication_id,'deterministic','confirmed','active','from drug_indications',now(),now()
        FROM drug_indications di JOIN drugs d ON d.id=di.drug_id AND d.dashboard_visible AND d.record_type='drug'
        WHERE di.indication_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM entity_edges e WHERE e.subject_id=di.drug_id AND e.predicate='TREATS' AND e.object_id=di.indication_id)
        RETURNING id;""" % COMMON,
    "ADDRESSES": """
        INSERT INTO entity_edges (subject_type,subject_id,predicate,object_type,object_id,%s)
        SELECT DISTINCT 'target',dt.target_id,'ADDRESSES','indication',di.indication_id,'deterministic','inferred','active','derived: drug targeting T treats I',now(),now()
        FROM drug_targets dt JOIN drug_indications di ON di.drug_id=dt.drug_id
        JOIN drugs d ON d.id=dt.drug_id AND d.dashboard_visible AND d.record_type='drug'
        WHERE dt.target_id IS NOT NULL AND di.indication_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM entity_edges e WHERE e.subject_id=dt.target_id AND e.predicate='ADDRESSES' AND e.object_id=di.indication_id)
        RETURNING id;""" % COMMON,
    "DEVELOPED_BY": """
        INSERT INTO entity_edges (subject_type,subject_id,predicate,object_type,object_id,%s)
        SELECT DISTINCT 'drug',d.id,'DEVELOPED_BY','company',d.company_id,'deterministic','confirmed','active','from drugs.company_id',now(),now()
        FROM drugs d WHERE d.company_id IS NOT NULL AND d.dashboard_visible AND d.record_type='drug'
          AND NOT EXISTS (SELECT 1 FROM entity_edges e WHERE e.subject_id=d.id AND e.predicate='DEVELOPED_BY' AND e.object_id=d.company_id)
        RETURNING id;""" % COMMON,
}


def run(query):
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{PROJECT}/database/query",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"Bearer {PAT}", "Content-Type": "application/json",
                 "User-Agent": "meridian-pipeline/1.0"}, method="POST")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def main() -> int:
    if DRY:
        print("[DRY] structural-edge materializer — would insert missing TREATS/ADDRESSES/DEVELOPED_BY edges")
        return 0
    for name, q in EDGES.items():
        print(f"{name}: +{len(run(q))} new edges")
    print("predicate counts:", run("SELECT predicate, count(*) FROM entity_edges WHERE status='active' GROUP BY 1 ORDER BY 2 DESC"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
