#!/usr/bin/env python3
"""
landscape_narrative.py — target/area-level Meridian narrative (the competitive map)
-----------------------------------------------------------------------------------
Promotes the narrative layer from per-asset to per-SPACE. Synthesizes every asset
hitting a target into one cited landscape narrative + a labeled landscape analysis,
stored as entity_narratives(entity_type='target', entity_id=<target>).

Same discipline as narrative_gen.py: every fact atom is sourced; the analysis is
labeled interpretation that may not introduce a figure absent from the facts.

Run:
  python3 scripts/landscape_narrative.py --target tl1a --dry-run
  python3 scripts/landscape_narrative.py --target tl1a            # write overview+intelligence
"""
import os, re, sys, json, argparse, hashlib, urllib.request, urllib.error
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from narrative_gen import get, _request, fail_closed_check, fail_closed_analysis  # noqa: E402

PHASE = {"Phase 3": 3, "Phase 2": 2, "Phase 1": 1, "Preclinical": 0}


def _ph(s):
    return PHASE.get(str(s or ""), -1)


def build_atoms(target):
    drugs = get(f"drug_targets?target_id=eq.{target}&select=drug_id") or []
    ids = sorted({r["drug_id"] for r in drugs if r.get("drug_id")})
    rows = get(f"drugs?id=in.({','.join(ids)})&dashboard_visible=eq.true"
               "&select=id,display_name,stage,company_display,target,drug_format,overlap,source_url") if ids else []
    deals = get(f"deals?area_id=eq.{target}&order=total_usd_m.desc.nullslast") or []
    atoms = []

    # 1. field size + stage distribution
    from collections import Counter
    dist = Counter(r.get("stage") for r in rows)
    dist_s = ", ".join(f"{dist[s]} {s}" for s in sorted(dist, key=_ph, reverse=True) if s)
    atoms.append({"claim": f"{len(rows)} {target.upper()}-targeting assets are in development: {dist_s}",
                  "source_url": None, "source_table": "drugs (landscape)", "source_row_id": target, "kind": "structured"})

    # 2. clinical leaders (Phase 3), each cited to its own source
    leaders = sorted([r for r in rows if _ph(r.get("stage")) >= 3], key=lambda r: -_ph(r.get("stage")))
    for r in leaders:
        co = r.get("company_display")
        nct = re.search(r"NCT\d{8}", str(r.get("source_url") or ""))
        claim = (f"Phase 3 leader: {r.get('display_name')}" + (f" ({co})" if co else "")
                 + (f" [{nct.group(0)}]" if nct else ""))
        atoms.append({"claim": claim, "source_url": r.get("source_url"),
                      "source_table": "drugs", "source_row_id": r.get("id"), "kind": "external"})

    # 3. architecture split: monospecific mAb vs TL1A×IL-23 bispecific
    bis = [r for r in rows if "23" in str(r.get("target") or "") or "bispecific" in str(r.get("drug_format") or "").lower()]
    mono = [r for r in rows if r not in bis]
    atoms.append({"claim": f"Two architectures: {len(mono)} monospecific anti-{target.upper()} agents "
                           f"(the clinical leaders) vs {len(bis)} {target.upper()}×IL-23 bispecifics "
                           f"(the majority of earlier-stage assets)",
                  "source_url": None, "source_table": "drugs (architecture)", "source_row_id": target, "kind": "structured"})

    # 4. deal activity — name the largest real, drug-attributed transactions only
    # (summing every area deal overcounts: many are non-TL1A-specific collaborations).
    top = [d for d in deals if d.get("total_usd_m") and d.get("drug_id")][:4]
    deal_s = "; ".join(f"{d['to_company']}–{d['from_company']} ${int(float(d['total_usd_m'])):,}M ({d.get('deal_date_label','')})"
                       for d in top)
    if top:
        atoms.append({"claim": f"Landmark TL1A transactions: {deal_s}",
                      "source_url": (top[0].get("source_url")), "source_table": "deals",
                      "source_row_id": str(top[0].get("id")), "kind": "external" if top[0].get("source_url") else "structured"})

    # 5. Ailux's own position in the space (anchor)
    alx = next((r for r in rows if r["id"] in ("anti-tl1a-xpf005-arm", "alx001") or "ALX001" in str(r.get("display_name"))), None)
    if alx:
        atoms.append({"claim": f"Ailux's ALX001 ({alx.get('stage')}, {target.upper()}×IL-23 bispecific) sits in the "
                               f"next-generation bispecific cohort",
                      "source_url": alx.get("source_url"), "source_table": "drugs",
                      "source_row_id": alx.get("id"), "kind": "external" if alx.get("source_url") else "structured"})

    # normalize to narrative_gen atom shape
    for a in atoms:
        a.setdefault("confidence", "confirmed" if a["kind"] == "external" else "inferred")
        a["kind"] = "external_confirmed" if a["kind"] == "external" else "structured_confirmed"
    return atoms, rows


LANDSCAPE_SYSTEM = (
    "You are Meridian mapping a competitive target landscape for Ailux (developer of ALX001, a "
    "TL1A×IL-23 bispecific). You receive NUMBERED cited facts about every asset hitting the "
    "target. Write a tight landscape overview: field size and stage distribution, the clinical "
    "leaders, the architectural split (monospecific vs bispecific), and the deal/valuation "
    "activity. Use ONLY the numbered facts; cite as [n]; introduce no number not in the facts. "
    "State facts only — no editorializing or 'this signals…' sentences (save that for the "
    "analysis). Every fact-bearing sentence carries a [n]. Markdown section headers. Under 230 words.")

ANALYSIS_SYSTEM_LS = (
    "You are Meridian's BD strategist. From the NUMBERED landscape facts, write a 'Meridian "
    "Analysis' — explicitly INTERPRETATION — answering: where is this space heading, where is "
    "the white space, and what does it mean for Ailux's bispecific (ALX001)? Reason only from "
    "the facts; cite [n]; introduce no new figure. Do NOT sum, total, average, or reformat any "
    "dollar figure (do not convert $7,250M to $7.25B or add deals together) — reference each "
    "deal individually as written, or omit the number. Start with exactly "
    "'_Meridian Analysis — interpretation, grounded in the cited facts._'. Under 180 words.")


def compose(system, drug_label, atoms):
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    numbered = "\n".join(f"[{i+1}] {a['claim']}" for i, a in enumerate(atoms))
    r = client.messages.create(model="claude-sonnet-4-6", max_tokens=600, temperature=0,
        system=system, messages=[{"role": "user", "content": f"TARGET: {drug_label}\n\nFACTS:\n{numbered}\n\nWrite it now."}])
    return r.content[0].text.strip()


def write(target, section, prose, atoms, rh):
    payload = {"entity_type": "target", "entity_id": target, "section": section, "body_md": prose,
               "confidence": "inferred", "source_rows_hash": rh, "stale": False,
               "generated_by": "landscape_narrative.py@v0", "updated_at": datetime.now(timezone.utc).isoformat()}
    res = _request("POST", "entity_narratives?on_conflict=entity_type,entity_id,section",
                   payload, {"Prefer": "resolution=merge-duplicates,return=representation"})
    if not res:
        print("  write failed", file=sys.stderr); return
    nid = res[0]["id"]
    _request("DELETE", f"narrative_provenance?narrative_id=eq.{nid}")
    prov = [{"narrative_id": nid, "claim_index": i + 1, "claim_text": a["claim"],
             "source_url": a.get("source_url"), "source_table": a["source_table"],
             "source_row_id": a.get("source_row_id"),
             "content_confirms_claim": (a["kind"] == "external_confirmed") or None}
            for i, a in enumerate(atoms)]
    _request("POST", "narrative_provenance", prov, {"Prefer": "return=minimal"})
    print(f"  wrote target/{section} {nid} + {len(prov)} provenance rows")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    atoms, rows = build_atoms(args.target)
    rh = hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()[:16]
    print(f"\n=== {args.target.upper()} landscape — {len(atoms)} atoms ===")
    for i, a in enumerate(atoms):
        print(f"  [{i+1}] {a['claim'][:96]}  <- {a.get('source_url') or a['source_table']}")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n(no ANTHROPIC_API_KEY — atoms only)"); return

    label = args.target.upper()

    def gen(system, checker):
        for i in range(3):
            prose = compose(system, label, atoms)
            probs = checker(prose, atoms, [])
            if not probs:
                return prose, probs
            print(f"  (retry {i+1}/2: {probs[0][:50]})", file=sys.stderr)
        return prose, probs

    overview, p1 = gen(LANDSCAPE_SYSTEM, fail_closed_check)
    print(f"\n--- LANDSCAPE OVERVIEW ---\n{overview}\n", "PASS" if not p1 else f"PROBLEMS {p1}")
    analysis, p2 = gen(ANALYSIS_SYSTEM_LS, fail_closed_analysis)
    print(f"\n--- LANDSCAPE ANALYSIS ---\n{analysis}\n", "PASS" if not p2 else f"PROBLEMS {p2}")

    if args.dry_run:
        print("\n[dry-run] no write."); return
    if not p1:
        write(args.target, "overview", overview, atoms, rh)
    if not p2:
        write(args.target, "intelligence", analysis, atoms, rh)


if __name__ == "__main__":
    main()
