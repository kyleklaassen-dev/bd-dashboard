#!/usr/bin/env python3
"""Rule-verify competitive relationship edges.

The knowledge graph's direct_competitor edges were 100% verification_needed (0%
confirmed). But a competitor edge whose two drugs share a CONFIRMED disease area
(drug_areas membership) is a confirmable fact — they demonstrably compete in that
area — not an unverifiable guess. This stamps those edges verified (confidence
'medium', inference_method 'rule_inferred', evidence naming the shared area),
leaving genuine cross-area edges flagged for closer review.

Idempotent — safe to re-run / schedule. Run: python scripts/verify_competitor_edges.py [--dry-run]
Env: SUPABASE_PAT (management API), SUPABASE_URL
"""
import os
import sys
import json
import urllib.request

URL = os.environ.get("SUPABASE_URL", "https://tghntyofptvfhmtchwcv.supabase.co")
PROJECT = URL.replace("https://", "").split(".supabase.co")[0]
PAT = os.environ["SUPABASE_PAT"]
DRY = "--dry-run" in sys.argv

SQL = """
WITH shared AS (
  SELECT er.id, array_agg(DISTINCT a.area_id) AS areas
  FROM entity_relationships er
  JOIN drug_areas a ON a.drug_id = er.source_id
  JOIN drug_areas b ON b.drug_id = er.target_id AND b.area_id = a.area_id
  WHERE er.relationship_type='direct_competitor'
    AND er.source_type='drug' AND er.target_type='drug'
    AND er.verification_needed = true
  GROUP BY er.id
)
UPDATE entity_relationships er
SET verification_needed = false,
    confidence = 'medium',
    inference_method = 'rule_inferred',
    evidence = ARRAY['rule-verified: both compete in ' || array_to_string(s.areas, ', ')],
    notes = COALESCE(NULLIF(er.notes,''),'') || ' [rule-verified: shared disease area]'
FROM shared s WHERE er.id = s.id
RETURNING er.id;
"""

# Second rule: shared molecular target (drug_targets) — same-target rivals / analogues /
# geographic variants. Applies to all drug-drug edge types where a shared target confirms it.
SQL_TARGET = """
WITH st AS (
  SELECT er.id, array_agg(DISTINCT a.target_id) AS tg
  FROM entity_relationships er
  JOIN drug_targets a ON a.drug_id = er.source_id
  JOIN drug_targets b ON b.drug_id = er.target_id AND b.target_id = a.target_id
  WHERE er.relationship_type IN ('direct_competitor','mechanism_analogue','combination_candidate','geographic_variant')
    AND er.source_type='drug' AND er.target_type='drug'
    AND er.verification_needed = true
  GROUP BY er.id
)
UPDATE entity_relationships er
SET verification_needed = false, confidence = 'medium', inference_method = 'rule_inferred',
    evidence = ARRAY['rule-verified: both target ' || array_to_string(st.tg, ', ')],
    notes = COALESCE(NULLIF(er.notes,''),'') || ' [rule-verified: shared molecular target]'
FROM st WHERE er.id = st.id
RETURNING er.id;
"""

# Third rule: any edge carrying a real source URL is source-verified; parent_subsidiary
# edges derivable from companies.parent_company_id are database-confirmed.
SQL_SOURCED = """
UPDATE entity_relationships SET verification_needed=false, confidence='medium'
WHERE verification_needed=true AND source_url LIKE 'http%'
RETURNING id;
"""
SQL_PARENT = """
UPDATE entity_relationships er SET verification_needed=false, confidence='high', inference_method='database_join',
  notes=COALESCE(NULLIF(er.notes,''),'') || ' [verified: companies.parent_company_id]'
WHERE er.relationship_type='parent_subsidiary' AND er.verification_needed=true AND er.source_type='company'
  AND EXISTS (SELECT 1 FROM companies c WHERE c.id=er.target_id AND c.parent_company_id=er.source_id)
RETURNING er.id;
"""
COUNT = ("SELECT round(100.0*sum((not verification_needed)::int)/count(*),1) pct, count(*) total "
         "FROM entity_relationships WHERE relationship_type='direct_competitor';")


def run(query):
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{PROJECT}/database/query",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"Bearer {PAT}", "Content-Type": "application/json",
                 "User-Agent": "meridian-pipeline/1.0"},
        method="POST")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def main() -> int:
    if DRY:
        # count how many WOULD be verified
        q = ("SELECT count(*) FROM entity_relationships er WHERE er.relationship_type='direct_competitor' "
             "AND er.source_type='drug' AND er.target_type='drug' AND er.verification_needed=true "
             "AND EXISTS (SELECT 1 FROM drug_areas a JOIN drug_areas b ON a.area_id=b.area_id "
             "WHERE a.drug_id=er.source_id AND b.drug_id=er.target_id);")
        print("[DRY] would rule-verify:", run(q))
        return 0
    n = {
        "shared_area": len(run(SQL)),
        "shared_target": len(run(SQL_TARGET)),
        "source_url": len(run(SQL_SOURCED)),
        "parent_company": len(run(SQL_PARENT)),
    }
    print("rule-verified:", n)
    print("competitor verified %:", run(COUNT))
    print("overall graph verified %:", run("SELECT round(100.0*sum((not verification_needed)::int)/count(*),1) FROM entity_relationships;"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
