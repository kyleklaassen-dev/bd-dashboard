#!/usr/bin/env python3
"""
sync_collection_queue.py — reconcile the stateful queue with the live gaps view
-------------------------------------------------------------------------------
source_collection_gaps (v75) is always-fresh truth; source_collection_queue (v76)
carries lifecycle. This reconciles them:
  • new gap            -> insert status='open'
  • still-present gap   -> refresh priority/claim_text/last_seen (PRESERVE status)
  • gap now absent      -> auto-resolve any open/in_progress row (it got corroborated
                          or the claim changed) with resolved_at + a note
So a human/pipeline can mark a row in_progress and it won't be clobbered, and gaps
that get an independent source drop off automatically.

Run:
  python3 scripts/sync_collection_queue.py --area tl1a
  python3 scripts/sync_collection_queue.py --all
"""
import os, sys, json, argparse, urllib.request, urllib.error
from datetime import datetime, timezone

SUPA = "https://tghntyofptvfhmtchwcv.supabase.co/rest/v1"
WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = (os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
       or open(os.path.join(WORK, ".supabase_service_key")).read().strip())


def _req(method, ep, data=None, prefer=None):
    h = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
    if prefer:
        h["Prefer"] = prefer
    r = urllib.request.Request(f"{SUPA}/{ep}", data=json.dumps(data).encode() if data is not None else None,
                               headers=h, method=method)
    try:
        with urllib.request.urlopen(r) as resp:
            raw = resp.read(); return json.loads(raw) if raw.strip() else []
    except urllib.error.HTTPError as e:
        print(f"  {e.code} {ep[:50]}: {e.read().decode()[:160]}", file=sys.stderr); return None


def get(ep):
    return _req("GET", ep) or []


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--area"); g.add_argument("--all", action="store_true")
    args = ap.parse_args()

    scope_ids = None
    if args.area:
        scope_ids = sorted({r["drug_id"] for r in
                            get(f"drug_targets?target_id=eq.{args.area}&select=drug_id") if r.get("drug_id")})
        if not scope_ids:
            print("no drugs in area"); return
        filt = f"&entity_id=in.({','.join(scope_ids)})"
    else:
        filt = ""

    gaps = get(f"source_collection_gaps?select=*{filt}")
    queue = get(f"source_collection_queue?select=*{filt}")
    now = datetime.now(timezone.utc).isoformat()

    def keyof(r):
        return (r["entity_type"], r["entity_id"], r["section"], r.get("claim_index"))

    qby = {keyof(q): q for q in queue}
    gby = {keyof(x): x for x in gaps}

    inserts, patches, resolves = [], 0, 0
    for k, x in gby.items():
        if k in qby:
            q = qby[k]
            _req("PATCH", f"source_collection_queue?id=eq.{q['id']}",
                 {"priority": x.get("priority"), "claim_text": x.get("claim_text"),
                  "gap_type": x.get("gap_type"), "last_seen": now}, "return=minimal")
            patches += 1
        else:
            inserts.append({"entity_type": x["entity_type"], "entity_id": x["entity_id"],
                            "section": x["section"], "claim_index": x.get("claim_index"),
                            "claim_text": x.get("claim_text"), "gap_type": x.get("gap_type"),
                            "priority": x.get("priority"), "status": "open",
                            "first_seen": now, "last_seen": now})
    if inserts:
        _req("POST", "source_collection_queue", inserts, "return=minimal")

    # auto-resolve gaps that are no longer present
    for k, q in qby.items():
        if k not in gby and q.get("status") in ("open", "in_progress"):
            _req("PATCH", f"source_collection_queue?id=eq.{q['id']}",
                 {"status": "resolved", "resolved_at": now,
                  "resolution_note": "gap no longer present (corroborated or claim changed)"},
                 "return=minimal")
            resolves += 1

    print(f"queue sync{' ['+args.area+']' if args.area else ''}: "
          f"{len(inserts)} new, {patches} refreshed, {resolves} auto-resolved "
          f"(live gaps: {len(gaps)})")


if __name__ == "__main__":
    main()
