#!/usr/bin/env python3
"""
strategic_brief.py — the decision layer (apex of the stack)
-----------------------------------------------------------
Turns the TRUSTED graph into action: a ranked, cited BD brief for Ailux over a
target landscape. Each asset is presented with its stage, overlap-to-Ailux, and
DATA-TRUST grade, so the recommendation explicitly discounts low-trust profiles —
plus deal-sequencing constraints. Grounded + fail-closed (no fabricated figures).

Stored as entity_narratives(entity_type='target', section='business').

Run:
  python3 scripts/strategic_brief.py --area tl1a --dry-run
  python3 scripts/strategic_brief.py --area tl1a
"""
import os, re, sys, json, hashlib, argparse
from datetime import datetime, timezone

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
sys.path.insert(0, os.path.join(_SCRIPTS, 'narrative'))

from _common import load_credentials  # noqa: E402
import ai.client as ai_client  # noqa: E402
from ai.client import PromptConfig  # noqa: E402
import narrative_gen as ng  # noqa: E402

_, _, _ANTHROPIC_KEY = load_credentials(require_anthropic=False)
if _ANTHROPIC_KEY:
    ai_client.setup(_ANTHROPIC_KEY)

PH = {"Phase 3": 3, "Phase 2": 2, "Phase 1": 1, "Preclinical": 0}


def _ph(s):
    return PH.get(str(s or ""), -1)


# Deal-sequencing constraints (governance canon — see CLAUDE.md §6). Each is a cited
# atom so the brief can honor timing without the model inventing it.
SEQUENCING_NOTES = {
    "tl1a": "Deal-sequencing constraint: AbbVie cannot be targeted for a TL1A bispecific "
            "until after the ABBV-701 Phase 1 readout (expected Oct 2026); treat as timing-gated.",
}


def build_atoms(area):
    drugs = ng.get(f"drug_targets?target_id=eq.{area}&select=drug_id") or []
    ids = sorted({r["drug_id"] for r in drugs if r.get("drug_id")})
    rows = ng.get(f"drugs?id=in.({','.join(ids)})&dashboard_visible=eq.true"
                  "&select=id,display_name,stage,company_display,overlap,source_url") if ids else []
    trust = {t["drug_id"]: t for t in
             ng.get(f"drug_trust_scores?drug_id=in.({','.join(ids)})&select=drug_id,grade,score")} if ids else {}
    atoms = []

    # field overview
    from collections import Counter
    dist = Counter(r.get("stage") for r in rows)
    atoms.append({"claim": f"{len(rows)} {area.upper()} assets tracked: "
                  + ", ".join(f"{dist[s]} {s}" for s in sorted(dist, key=_ph, reverse=True) if s),
                  "source_url": None, "source_table": "drugs (landscape)", "source_row_id": area,
                  "kind": "structured_confirmed", "confidence": "inferred"})

    # one atom per clinical-stage asset, carrying stage + overlap + TRUST grade
    for r in sorted([r for r in rows if _ph(r.get("stage")) >= 2], key=lambda r: -_ph(r.get("stage"))):
        t = trust.get(r["id"], {})
        tg = f"; data-trust {t.get('grade')}({t.get('score')})" if t else "; data-trust n/a"
        ov = r.get("overlap")
        claim = (f"{r.get('display_name')}" + (f" ({r.get('company_display')})" if r.get('company_display') else "")
                 + f" — {r.get('stage')}" + (f"; overlap to Ailux: {ov}" if ov else "") + tg)
        atoms.append({"claim": claim, "source_url": r.get("source_url"), "source_table": "drugs",
                      "source_row_id": r.get("id"),
                      "kind": "external_confirmed" if r.get("source_url") else "structured_confirmed",
                      "confidence": "confirmed" if r.get("source_url") else "inferred"})

    # Ailux anchor
    alx = next((r for r in rows if r["id"] in ("alx001", "anti-tl1a-xpf005-arm")
                or "ALX001" in str(r.get("display_name"))), None)
    if alx:
        atoms.append({"claim": f"Ailux's ALX001 ({alx.get('stage')}) is the home asset in this space",
                      "source_url": alx.get("source_url"), "source_table": "drugs", "source_row_id": alx.get("id"),
                      "kind": "structured_confirmed", "confidence": "inferred"})

    # deal-sequencing constraint
    if area in SEQUENCING_NOTES:
        atoms.append({"claim": SEQUENCING_NOTES[area], "source_url": None,
                      "source_table": "governance (deal_sequencing)", "source_row_id": area,
                      "kind": "structured_confirmed", "confidence": "inferred"})
    return atoms, rows


SYSTEM = (
    "You are Meridian's BD strategist writing for Ailux (ALX001, a TL1A×IL-23 bispecific for IBD). "
    "You receive NUMBERED cited facts about a target landscape; each asset carries its stage, its "
    "overlap to Ailux, and a DATA-TRUST grade (A best … F worst). Produce a ranked BD priority brief "
    "labeled as INTERPRETATION. Weigh each opportunity by (a) overlap/threat to Ailux, (b) stage and "
    "timing, (c) DATA TRUST — explicitly discount or caveat assets with low trust grades, and "
    "(d) any deal-sequencing constraint. Group recommendations as **Call now**, **Watch**, and "
    "**Timing-gated**, each item citing [n]. Reason ONLY from the facts; cite [n]; introduce no new "
    "number/%/date. Start with exactly "
    "'_Meridian Strategic Brief — interpretation, grounded in the cited facts._'. Under 340 words.")

_BRIEF_CFG = PromptConfig(
    name="strategic_brief",
    system=SYSTEM,
    model="claude-sonnet-4-6",
    max_tokens=900,
    temperature=0,
)


def compose(area, atoms):
    numbered = "\n".join(f"[{i+1}] {a['claim']}" for i, a in enumerate(atoms))
    prompt = f"TARGET: {area.upper()}\n\nFACTS:\n{numbered}\n\nWrite the brief now."
    return ai_client.run_text(_BRIEF_CFG, prompt).strip()


def check(prose, atoms):
    probs = ng.fail_closed_analysis(prose, atoms, [])
    return [p for p in probs if not (p == "missing the interpretation label"
                                     and "Meridian Strategic Brief" in prose)]


def write(area, prose, atoms, rh):
    payload = {"entity_type": "target", "entity_id": area, "section": "business", "body_md": prose,
               "confidence": "inferred", "source_rows_hash": rh, "stale": False,
               "generated_by": "strategic_brief.py@v0", "updated_at": datetime.now(timezone.utc).isoformat()}
    res = ng._request("POST", "entity_narratives?on_conflict=entity_type,entity_id,section",
                      payload, {"Prefer": "resolution=merge-duplicates,return=representation"})
    if not res:
        print("  write failed", file=sys.stderr); return
    nid = res[0]["id"]
    ng._request("DELETE", f"narrative_provenance?narrative_id=eq.{nid}")
    prov = []
    for i, a in enumerate(atoms):
        tier, rank = ng._source_tier(a.get("source_url"), a["source_table"])
        prov.append({"narrative_id": nid, "claim_index": i + 1, "claim_text": a["claim"],
                     "source_url": a.get("source_url"), "source_table": a["source_table"],
                     "source_row_id": a.get("source_row_id"),
                     "content_confirms_claim": (a["kind"] == "external_confirmed") or None,
                     "independence_tier": tier, "tier_rank": rank})
    ng._request("POST", "narrative_provenance", prov, {"Prefer": "return=minimal"})
    print(f"  wrote target/business {nid} + {len(prov)} provenance rows")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--area", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    atoms, rows = build_atoms(args.area)
    rh = hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()[:16]
    print(f"\n=== {args.area.upper()} Strategic Brief — {len(atoms)} atoms ===")
    for i, a in enumerate(atoms):
        print(f"  [{i+1}] {a['claim'][:96]}")
    if not _ANTHROPIC_KEY:
        print("\n(no ANTHROPIC_API_KEY — atoms only)"); return

    prose = probs = None
    for i in range(3):
        prose = compose(args.area, atoms)
        probs = check(prose, atoms)
        if not probs:
            break
        print(f"  (retry {i+1}/2: {probs[0][:50]})", file=sys.stderr)
    print(f"\n--- STRATEGIC BRIEF ---\n{prose}\n", "PASS" if not probs else f"PROBLEMS {probs}")
    if args.dry_run:
        print("[dry-run] no write."); return
    if not probs:
        write(args.area, prose, atoms, rh)


if __name__ == "__main__":
    main()
