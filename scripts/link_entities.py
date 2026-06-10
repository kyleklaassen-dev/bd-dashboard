#!/usr/bin/env python3
"""
link_entities.py — the dashboard-wide automatic entity-matching pass.
====================================================================
One command that connects every free-text entity reference across the data
tables to the canonical knowledge graph, using the shared `entity_matcher`:

  1. intel_facts        -> intel_fact_entities (+ subject_id backfill)   [via build_fact_graph]
  2. market_landscape   -> company_id   (matched from the `company` column)
  3. rx_market_tracker  -> drug_id      (matched from `drug_name` / `brand_name`)

Safe by construction: only unambiguous, single-id matches are written; ambiguous
surfaces (duplicate rows) and untracked entities are reported as review/discovery
candidates, never guessed.

Usage:
    SUPABASE_SERVICE_KEY=... python3 scripts/link_entities.py            # DRY RUN (default)
    SUPABASE_SERVICE_KEY=... python3 scripts/link_entities.py --apply    # write changes
"""
import os, sys, pathlib, collections, requests

BASE = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from entity_matcher import Registry
import build_fact_graph as bfg

SUPABASE_URL = bfg.SUPABASE_URL
H = bfg.H
APPLY = "--apply" in sys.argv


def getall(t, p):
    return bfg.getall(t, p)


def patch(table, row_id, body):
    return requests.patch(f"{SUPABASE_URL}/rest/v1/{table}?id=eq.{row_id}",
                          headers={**H, "Prefer": "return=minimal"}, json=body).status_code in (200, 204)


def link_column(reg, table, id_col, text_cols, want_type):
    """Backfill <id_col> on rows where it is null, by resolving text_cols."""
    rows = getall(table, {"select": "id," + id_col + "," + ",".join(text_cols)})
    todo = [r for r in rows if not r.get(id_col)]
    filled = 0
    matched, ambiguous, unmatched = [], [], []
    for r in todo:
        blob = " ".join(str(r.get(c) or "") for c in text_cols).strip()
        hits = [h for h in reg.resolve(blob) if h[0] == want_type]
        if len(hits) == 1:
            matched.append((r, hits[0]))
        elif len(hits) > 1:
            ambiguous.append((r, hits))
        else:
            unmatched.append((r, blob))
    if APPLY:
        for r, hit in matched:
            if patch(table, r["id"], {id_col: hit[1]}):
                filled += 1
    print(f"\n[{table}.{id_col}] {len(rows)} rows, {len(todo)} unlinked -> "
          f"{len(matched)} matchable{' ('+str(filled)+' written)' if APPLY else ''}, "
          f"{len(ambiguous)} ambiguous, {len(unmatched)} untracked")
    if matched[:6]:
        for r, hit in matched[:6]:
            src = " ".join(str(r.get(c) or "") for c in text_cols)[:32]
            print(f"    ✓ {src:32s} -> {hit[1]} ({reg.id2name.get(hit[1])})")
    uniq_unmatched = sorted({b for _, b in unmatched if b})
    if uniq_unmatched:
        print(f"    discovery candidates (untracked): {', '.join(uniq_unmatched[:12])}"
              + (" ..." if len(uniq_unmatched) > 12 else ""))
    return len(matched), filled


def main():
    print("=" * 72)
    print("DASHBOARD-WIDE ENTITY MATCHING  —  " + ("APPLY (writing)" if APPLY else "DRY RUN (no writes)"))
    print("=" * 72)
    reg = Registry(SUPABASE_URL, H)
    print(f"registry: {len(reg.name2ids)} surfaces, {len(reg.pinned)} pinned, "
          f"{len(reg.ambiguous)} ambiguous (duplicate rows — review)")
    if reg.ambiguous:
        print("  ambiguous surfaces:", ", ".join(sorted(reg.ambiguous)))

    # 1) intel_facts -> intel_fact_entities
    facts = getall("intel_facts", {"select": "id,subject_id,subject_type,subject_name,area_id,claim"})
    rows, subj_fill = bfg.build_edges(reg, facts)
    linked_facts = {r["fact_id"] for r in rows}
    before = sum(1 for f in facts if f.get("subject_id"))
    print(f"\n[intel_facts -> intel_fact_entities] {len(facts)} facts, "
          f"{len(linked_facts)} will have >=1 edge ({100*len(linked_facts)//len(facts)}%); "
          f"subject_id set before={before}, will backfill {sum(len(v) for v in subj_fill.values())}")
    if APPLY:
        ins, fail, nuniq = bfg.insert_edges(rows)
        fixed = 0
        for (sid, st), ids in subj_fill.items():
            for j in range(0, len(ids), 200):
                ch = ids[j:j+200]
                if requests.patch(f"{SUPABASE_URL}/rest/v1/intel_facts?id=in.({','.join(map(str, ch))})",
                                  headers={**H, "Prefer": "return=minimal"}, json={"subject_id": sid, "subject_type": st}).status_code in (200, 204):
                    fixed += len(ch)
        print(f"    written: {ins} edges, subject_id backfilled {fixed}, {fail} failed")

    # 2) market_landscape.company_id   3) rx_market_tracker.drug_id
    link_column(reg, "market_landscape", "company_id", ["company"], "company")
    link_column(reg, "rx_market_tracker", "drug_id", ["drug_name", "brand_name"], "drug")

    print("\n" + ("Done (changes written)." if APPLY else "Dry run complete. Re-run with --apply to write."))


if __name__ == "__main__":
    main()
