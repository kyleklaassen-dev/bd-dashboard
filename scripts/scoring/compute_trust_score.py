#!/usr/bin/env python3
"""
compute_trust_score.py — per-drug data-quality / trust score (0–100)
--------------------------------------------------------------------
The narratives kept surfacing data debt (fabricated DOIs, misattributed/absent
NCTs, null company_display, duplicate catalysts, unresolved governance issues).
This quantifies that per asset so cleanup can be prioritized and the card can show
"how much should you trust this profile."

Transparent penalty model from 100; every deduction is recorded in `breakdown`.
Stored in `drug_trust_scores`. Surfaced on the narrative card.

Run:
  python3 scripts/compute_trust_score.py --area tl1a
  python3 scripts/compute_trust_score.py --drug-id tulisokibart
  python3 scripts/compute_trust_score.py --all --apply
"""
import os, re, sys, argparse
from datetime import datetime, timezone
from collections import Counter

_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from _common import load_credentials  # noqa: E402
import _db                              # noqa: E402

SUPABASE_URL, KEY, _ = load_credentials(require_anthropic=False)
_db.init_db(SUPABASE_URL, KEY)


def get(ep):
    """Call sites pass a 'table?select=...&...' fragment; split it and
    delegate to _db.sb_get's (table, params) interface."""
    table, _, qs = ep.partition("?")
    params = dict(p.split("=", 1) for p in qs.split("&")) if qs else {}
    return _db.sb_get(table, params)


def score_drug(did):
    drug = get(f"drugs?id=eq.{did}&select=display_name,company_display,mechanism,target,stage,source_url")
    if not drug:
        return None
    d = drug[0]
    srcs = get(f"drug_sources?drug_id=eq.{did}&select=content_confirms_claim,url_status,source_url")
    trials = get(f"trials?drug_id=eq.{did}&select=id")
    govs = get(f"governance_violations?row_id=eq.{did}&resolved=eq.false&select=rule_name")
    cats = get(f"catalysts?drug_id=eq.{did}&select=label")
    # independence + agreement signals (v74/v75)
    indep = get(f"narrative_independence?entity_id=eq.{did}&entity_type=eq.drug"
                "&select=claims,multi_domain_claims,independent_claims,peer_reviewed_claims")
    vconf = get(f"narrative_value_conflicts?drug_id=eq.{did}&select=metric")
    gaps = get(f"source_collection_gaps?entity_id=eq.{did}&entity_type=eq.drug&select=gap_type")

    score, brk = 100, []
    def hit(pts, why):
        nonlocal score
        score -= pts; brk.append({"-": pts, "why": why})

    # field completeness
    if not d.get("source_url"):
        hit(15, "no primary source_url")
    if not d.get("company_display"):
        hit(10, "no company_display")
    if not (d.get("mechanism") or d.get("target")):
        hit(10, "no mechanism/target")

    # evidence depth
    confirmed = [s for s in srcs if s.get("content_confirms_claim") is True]
    if not confirmed and not trials:
        hit(20, "no confirmed sources and no trials")
    elif not confirmed:
        hit(8, "no confirmed external sources")
    # dead source URLs
    dead = [s for s in srcs if s.get("url_status") in ("http_403", "empty", "http_404")]
    if dead:
        hit(min(10, 3 * len(dead)), f"{len(dead)} dead source URL(s)")

    # governance debt
    if govs:
        hit(min(30, 10 * len(govs)), f"{len(govs)} unresolved governance issue(s): "
            + ", ".join(sorted({g['rule_name'] for g in govs}))[:60])

    # duplicate catalysts
    labs = [(c.get("label") or "").split("—")[0].strip().lower() for c in cats]
    dups = sum(v - 1 for v in Counter([l for l in labs if l]).values() if v > 1)
    if dups:
        hit(min(8, 2 * dups), f"{dups} duplicate catalyst row(s)")

    # value disagreements — same metric/timepoint/dose, divergent numbers (v74)
    if vconf:
        hit(min(12, 4 * len(vconf)), f"{len(vconf)} unresolved value conflict(s)")

    # source independence — does anything beyond sponsor/registry back the claims? (v74)
    # Only assessable once a narrative exists; uses the best section.
    best = max(indep, key=lambda r: (r.get("peer_reviewed_claims", 0),
                                     r.get("independent_claims", 0)), default=None) if indep else None
    if best:
        if best.get("peer_reviewed_claims", 0) == 0 and confirmed:
            hit(6, "no peer-reviewed/regulatory source backs any claim")
        elif best.get("independent_claims", 0) == 0:
            hit(3, "no independently-corroborated claim (sponsor/registry only)")

    score = max(0, score)
    grade = ("A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else
             "D" if score >= 40 else "F")
    return {"drug_id": did, "score": score, "grade": grade,
            "breakdown": {"name": d.get("display_name"), "deductions": brk,
                          "confirmed_sources": len(confirmed), "trials": len(trials),
                          "open_governance": len(govs),
                          "independent_claims": (best or {}).get("independent_claims", 0),
                          "peer_reviewed_claims": (best or {}).get("peer_reviewed_claims", 0),
                          "value_conflicts": len(vconf),
                          "collection_gaps": len(gaps)}}


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--drug-id"); g.add_argument("--area"); g.add_argument("--all", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    if args.drug_id:
        ids = [args.drug_id]
    elif args.area:
        ids = sorted({r["drug_id"] for r in get(f"drug_targets?target_id=eq.{args.area}&select=drug_id") if r.get("drug_id")})
    else:
        ids = [r["id"] for r in get("drugs?select=id&dashboard_visible=eq.true")]

    rows = []
    for did in ids:
        s = score_drug(did)
        if s:
            rows.append(s)
            print(f"  {s['grade']} {s['score']:3d}  {did:22} "
                  + (("← " + "; ".join(x['why'] for x in s['breakdown']['deductions'])) if s['breakdown']['deductions'] else "clean"))
    if rows:
        avg = sum(r["score"] for r in rows) / len(rows)
        print(f"\n{len(rows)} drugs · mean trust {avg:.0f} · "
              + ", ".join(f"{g}:{sum(1 for r in rows if r['grade']==g)}" for g in "ABCDF"))
    if args.apply and rows:
        for r in rows:
            r["computed_at"] = datetime.now(timezone.utc).isoformat()
        _db.sb_upsert("drug_trust_scores", rows, on_conflict="drug_id")
        print(f"  wrote {len(rows)} trust scores.")
    elif not args.apply:
        print("[dry-run] no write (add --apply).")


if __name__ == "__main__":
    main()
