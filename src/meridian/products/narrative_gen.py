#!/usr/bin/env python3
"""
narrative_gen.py — Narrative Knowledge Layer generator (v0)
-----------------------------------------------------------
Design: docs/NARRATIVE_KNOWLEDGE_LAYER.md
Schema: migrations/v70_narrative_layer.sql

Builds the `overview` narrative for ONE drug, the derived-not-authored way:

  recipe rows  ->  claim atoms (deterministic)  ->  compose prose from atoms only
               ->  fail-closed claim match      ->  write entity_narratives + provenance

GOVERNANCE (the whole point):
  - A sentence may assert a fact ONLY if a claim atom backs it.
  - A structured-row field (e.g. drugs.stage) is admitted as an asserted atom
    ONLY if a CONFIRMED external source (drug_sources, content_confirms_claim=true)
    corroborates it. Otherwise it goes to the UNVERIFIED bucket and is NOT narrated.
  - Anything a verifier DISCONFIRMED (content_confirms_claim=false) is scrubbed
    from the prose entirely (e.g. a fabricated NCT id).
  - Conflicts between a structured field and a confirmed source are surfaced,
    never smoothed over.

This means the narrative can only ever be as wrong as the CONFIRMED source set.

Run:
  python3 scripts/narrative_gen.py --drug-id mt-251 --dry-run
  python3 scripts/narrative_gen.py --drug-id mt-251 --composer template   # offline, no API key
  python3 scripts/narrative_gen.py --drug-id mt-251                        # llm compose + write

Flags:
  --drug-id ID     required
  --dry-run        do everything except DB writes (prints atoms, conflicts, prose)
  --composer       llm (default) | template  (template = deterministic, no API key)
  --section        overview (only section implemented in v0)
"""

import os
import re
import sys
import json
import hashlib
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timezone

# ── §3 SPLIT — base/atoms/triangulate now in meridian.products.narrative.* ──
from meridian.products.narrative.common import (
    _request, get, fetch_recipe, recipe_hash, SUPA_URL, SUPA_KEY,
)
from meridian.products.narrative.atoms import extract_atoms
from meridian.products.narrative.triangulate import (
    _source_tier, build_study_resolver, triangulate, detect_value_conflicts, persist_value_conflicts, conflicts_note,
)


# 2.6 LEARNING LOOP — read prior human corrections so generation honors them
# ---------------------------------------------------------------------------
def fetch_feedback(entity_type, entity_id, section):
    """Unresolved narrative_feedback for this entity+section (the corrections to honor)."""
    from urllib.parse import quote
    rows = get(f"narrative_feedback?entity_type=eq.{entity_type}"
               f"&entity_id=eq.{quote(str(entity_id))}&section=eq.{section}"
               f"&applied=eq.false&order=created_at.asc")
    return rows or []


def feedback_block(fb):
    """Render unresolved corrections as prompt guidance. Corrections shape EMPHASIS,
    INTERPRETATION and TONE — they are NOT new facts: a correction that asserts a fact
    absent from the atoms must still be omitted (the fail-closed check enforces this)."""
    if not fb:
        return ""
    lines = []
    for f in fb:
        ft = f.get("feedback_type") or "other"
        q = (f.get("quote") or "").strip()
        cor = (f.get("correction") or "").strip()
        lines.append(f"- [{ft}]" + (f' re: "{q[:120]}"' if q else "") + f" → {cor}")
    return ("\n\nPRIOR HUMAN CORRECTIONS — honor these (they override default phrasing and "
            "emphasis; they are GUIDANCE, not new facts — you still may not assert any "
            "fact, number, %, date, or trial id that is absent from the atoms/facts above; "
            "if a correction would require an unsupported fact, reflect its intent without "
            "stating the fact):\n" + "\n".join(lines))


def mark_feedback_applied(fb):
    ids = [str(f["id"]) for f in fb if f.get("id")]
    if not ids:
        return
    _request("PATCH", f"narrative_feedback?id=in.({','.join(ids)})",
             {"applied": True}, {"Prefer": "return=minimal"})
    print(f"  marked {len(ids)} feedback row(s) applied")


# ---------------------------------------------------------------------------
# 3. COMPOSE — narrate ONLY the asserted atoms
# ---------------------------------------------------------------------------
COMPOSE_SYSTEM = (
    "You are Meridian's narrative composer. You will receive a list of CLAIM ATOMS, "
    "each already backed by a source. Write a short, fluent plain-English overview of "
    "the drug using ONLY facts present in the atoms. You may reorder and connect them "
    "and add neutral connective language, but you MUST NOT introduce any factual claim "
    "not present in the atoms — no mechanism-of-action explanation, disease background, "
    "comparative or speculative language, or domain knowledge of any kind unless it is "
    "stated verbatim in an atom. Every clause that asserts a fact must carry an inline "
    "[n] citation; if you cannot cite a clause, delete it. Do not mention any identifier "
    "or fact in the SCRUB list. Be substantive and structured: when the atoms contain them, "
    "include, when the atoms provide them: (a) patient population / unmet need + who fails "
    "current therapy, (b) the molecule (format, target, differentiation), (c) efficacy with "
    "comparators and any target-engagement-vs-efficacy gap, (d) PK, (e) ownership / deal "
    "value, (f) the primary competitors with stage, and (g) the next catalyst and date. "
    "Organize with short markdown section headers. End with one sentence of positioning that "
    "draws ONLY on the cited facts — no new facts. Keep it under 380 words."
)


def compose_llm(drug_name, atoms, scrub, feedback=None):
    import anthropic  # imported lazily so --composer template works without the lib
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    numbered = "\n".join(f"[{i+1}] ({a['kind']}/{a['confidence']}) {a['claim']}"
                         for i, a in enumerate(atoms))
    prompt = (f"DRUG: {drug_name}\n\nCLAIM ATOMS:\n{numbered}\n\n"
              f"SCRUB (never mention): {', '.join(scrub) or '(none)'}"
              + feedback_block(feedback) + "\n\nWrite the overview now.")
    resp = client.messages.create(
        model="claude-sonnet-4-6", max_tokens=700, temperature=0,
        system=COMPOSE_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()


ANALYSIS_SYSTEM = (
    "You are Meridian's BD strategist writing for Ailux (developer of ALX001, a TL1A×IL-23 "
    "bispecific antibody for IBD). You receive a NUMBERED list of CITED FACTS about another "
    "asset, plus optional prior framing notes. Write a short 'Meridian Analysis' that is "
    "explicitly an INTERPRETATION, not new fact, answering: (1) Is this asset a competitor, "
    "partner, market-validator, or threat to Ailux — and why? (2) What single dependency or "
    "catalyst could most change the story? (3) Where does it create or destroy value for "
    "Ailux's bispecific program? Reason ONLY from the numbered facts and cite them as [n]. You "
    "MUST NOT introduce any new number, %, date, dose, or trial id that is not in the facts. "
    "Start with exactly: '_Meridian Analysis — interpretation, grounded in the cited facts._' "
    "Then 2–3 short paragraphs. Under 200 words."
)


def compose_analysis(drug_name, atoms, framing, feedback=None, conflict_note=""):
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    numbered = "\n".join(f"[{i+1}] {a['claim']}" for i, a in enumerate(atoms))
    fr = "\n".join(f"- {k}: {v}" for k, v in framing.items() if v)
    prompt = (f"ASSET: {drug_name}\n\nCITED FACTS:\n{numbered}\n\n"
              f"PRIOR FRAMING (context only, not citable):\n{fr or '(none)'}"
              + conflict_note + feedback_block(feedback) + "\n\nWrite the Meridian Analysis now.")
    resp = client.messages.create(
        model="claude-sonnet-4-6", max_tokens=500, temperature=0,
        system=ANALYSIS_SYSTEM, messages=[{"role": "user", "content": prompt}])
    return resp.content[0].text.strip()


def fail_closed_analysis(prose, atoms, scrub, extra_figures=None):
    """Analysis is inference, so it needn't cite every clause — but it must not fabricate
    facts. Block if it introduces a %/NCT/$ figure absent from the fact atoms, or a scrub token.
    extra_figures = figures legitimately allowed from detected value-conflicts."""
    problems = []
    corpus = " ".join(a["claim"] for a in atoms)
    allowed = {f.replace(" ", "") for f in (extra_figures or set())}
    for tok in scrub:
        if tok.lower() in prose.lower():
            problems.append(f"scrubbed token '{tok}' present")
    for nct in set(re.findall(r"NCT\d{8}", prose, re.I)):
        if nct.upper() not in corpus.upper():
            problems.append(f"introduced NCT not in facts: {nct}")
    for fig in set(re.findall(r"\d+(?:\.\d+)?%|\$\s?\d[\d,\.]*\s?[BMbm]?", prose)):
        if fig.replace(" ", "") not in corpus.replace(" ", "") and fig.replace(" ", "") not in allowed:
            problems.append(f"introduced figure not in facts: {fig}")
    if "Meridian Analysis" not in prose:
        problems.append("missing the interpretation label")
    return problems


def compose_template(drug_name, atoms, scrub):
    """Deterministic, guaranteed-grounded baseline (no API key needed)."""
    parts = [f"{drug_name} overview (derived; every clause cites a source atom):", ""]
    for i, a in enumerate(atoms):
        parts.append(f"- {a['claim']} [{i+1}]")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# 4. FAIL-CLOSED CHECK — every asserted sentence must trace to an atom index
# ---------------------------------------------------------------------------
def fail_closed_check(prose, atoms, scrub):
    problems = []
    # Normalize: pull any citations that trail past a sentence terminator back
    # INSIDE the sentence ("text. [3]" -> "text [3].") so per-sentence checks are fair.
    norm = re.sub(r"([.!?])(\s*)((?:\[[\d,–—\- ]+\])+)", r" \3\1\2", prose)
    # citations may be [3], [17,18,10] or ranges [11-14]/[11–14]; pull every integer.
    cited = set(int(x) for grp in re.findall(r"\[([\d,–—\- ]+)\]", norm)
                for x in re.findall(r"\d+", grp))
    for n in cited:
        if not (1 <= n <= len(atoms)):
            problems.append(f"citation [{n}] has no matching atom")
    for tok in scrub:
        if tok.lower() in norm.lower():
            problems.append(f"scrubbed token '{tok}' present in prose")
    # Drop markdown headers / bold-only lines (structure, not claims).
    lines = [l for l in norm.splitlines()
             if l.strip() and not re.match(r"^\s*(#{1,6}\s|\*\*[^*]+\*\*\s*$)", l.strip())]
    text = " ".join(lines)
    # A sentence needs a citation ONLY if it asserts a HARD fact (number, %, phase,
    # trial id, efficacy/PK term). Pure framing/transition sentences are allowed.
    # Split on sentence-end followed by a capital, so decimals ("1.0%") and "vs."
    # don't fragment the sentence.
    FACT = re.compile(r"\d|%|phase|NCT|remission|response|half-life|\bweek\b|approv", re.I)
    for sent in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text):
        s = sent.strip()
        if len(s.split()) > 6 and FACT.search(s) and not re.search(r"\[\d", s):
            problems.append(f"uncited factual sentence: \"{s[:60]}...\"")
    return problems


# ---------------------------------------------------------------------------
# 5. WRITE (skipped on --dry-run; requires v70 applied)
# ---------------------------------------------------------------------------
def write_narrative(drug, section, prose, atoms, rh, composer):
    payload = {
        "entity_type": "drug", "entity_id": drug["id"], "section": section,
        "body_md": prose, "coverage_score": drug.get("confidence_score"),
        "confidence": "inferred", "source_rows_hash": rh, "stale": False,
        "generated_by": f"narrative_gen.py@v0/{composer}",
    }
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    # Upsert needs the conflict target, else it 409s on the existing (type,id,section) row.
    res = _request("POST", "entity_narratives?on_conflict=entity_type,entity_id,section",
                   payload, {"Prefer": "resolution=merge-duplicates,return=representation"})
    if not res:
        print("  write failed (is v70 applied?)", file=sys.stderr)
        return
    nid = res[0]["id"]
    # Replace stale provenance for this narrative before inserting the fresh set.
    _request("DELETE", f"narrative_provenance?narrative_id=eq.{nid}")
    # claim_index = the [n] used inline in body_md (1-based atom position). This is
    # the STABLE ordering the UI cites against — provenance.id is a random uuid.
    # PER-CLAIM TRIANGULATION: each atom emits its primary row PLUS one row per
    # independent corroborating source, all sharing the same claim_index.
    def _dsid(table, rid):
        return rid if (table == "drug_sources" and str(rid).isdigit()) else None
    prov = []
    triangulated = 0
    for i, a in enumerate(atoms):
        ptier, prank = _source_tier(a.get("source_url"), a["source_table"])
        prov.append({
            "narrative_id": nid, "claim_index": i + 1, "claim_text": a["claim"],
            "drug_source_id": _dsid(a["source_table"], a.get("source_row_id")),
            "source_url": a.get("source_url"), "source_table": a["source_table"],
            "source_row_id": a.get("source_row_id"),
            "content_confirms_claim": (a["kind"] == "external_confirmed") or None,
            "independence_tier": ptier, "tier_rank": prank,
        })
        corr = a.get("corroborations", []) or []
        if corr:
            triangulated += 1
        for c in corr:
            ctier, crank = _source_tier(c.get("source_url"), c["source_table"])
            prov.append({
                "narrative_id": nid, "claim_index": i + 1, "claim_text": a["claim"],
                "drug_source_id": _dsid(c["source_table"], c.get("source_row_id")),
                "source_url": c.get("source_url"), "source_table": c["source_table"],
                "source_row_id": c.get("source_row_id"),
                "content_confirms_claim": c.get("content_confirms_claim"),
                "independence_tier": ctier, "tier_rank": crank,
            })
    _request("POST", "narrative_provenance", prov, {"Prefer": "return=minimal"})
    print(f"  wrote narrative {nid} + {len(prov)} provenance rows "
          f"({triangulated}/{len(atoms)} claims triangulated)")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drug-id", required=True)
    ap.add_argument("--section", default="overview", choices=["overview", "intelligence"])
    ap.add_argument("--composer", default="llm", choices=["llm", "template"])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    recipe = fetch_recipe(args.drug_id)
    rh = recipe_hash(recipe)
    atoms = extract_atoms(recipe)
    asserted = triangulate(atoms["asserted"], recipe)
    resolver = build_study_resolver(recipe)
    value_conflicts = detect_value_conflicts(recipe, resolver)
    feedback = fetch_feedback("drug", args.drug_id, args.section)
    if not args.dry_run:
        persist_value_conflicts(value_conflicts)

    print(f"\n=== {args.drug_id} / {args.section}  (recipe hash {rh}) ===")
    n_tri = sum(1 for a in asserted if a.get("corroborations"))
    print(f"\nASSERTED atoms ({len(asserted)}; {n_tri} triangulated by ≥1 independent source):")
    for i, a in enumerate(asserted):
        src = a.get("source_url") or a["source_table"]
        tri = a.get("triangulation", 1)
        tag = f"  +{len(a['corroborations'])} corrob → {tri} domains" if a.get("corroborations") else ""
        print(f"  [{i+1}] ({a['kind']}/{a['confidence']}) {a['claim']}  <- {src}{tag}")
    n_indep = sum(1 for a in asserted
                  if any(_source_tier(c.get("source_url"), c["source_table"])[1] >= 5
                         for c in a.get("corroborations", [])))
    print(f"  ({n_indep} of those corroborated by a peer-reviewed/regulatory source)")
    if value_conflicts:
        print(f"\nVALUE CONFLICTS detected ({len(value_conflicts)}):")
        for c in value_conflicts:
            print(f"  ! {c['metric']} wk{c['timepoint_weeks']} {c['dose_norm']}: "
                  f"{c['value_min']}% vs {c['value_max']}% (Δ{c['delta']})")
    if feedback:
        print(f"\nUNRESOLVED FEEDBACK to honor ({len(feedback)}):")
        for f in feedback:
            print(f"  ↳ [{f.get('feedback_type')}] {(f.get('correction') or '')[:80]}")
    print(f"\nUNVERIFIED — held out of prose ({len(atoms['unverified'])}):")
    for u in atoms["unverified"]:
        print(f"  - {u['claim']}")
    print(f"\nCONFLICTED — demoted, NOT asserted ({len(atoms['conflicted'])}):")
    for c in atoms["conflicted"]:
        print(f"  ~ {c['claim']}")
    print(f"\nFLAGGED — fabricated/suspect source URL, NOT cited ({len(atoms.get('flagged', []))}):")
    for fl in atoms.get("flagged", []):
        print(f"  ! {fl['claim'][:60]}  <- {fl['source_url']}")
    print(f"\nCONFLICTS ({len(atoms['conflicts'])}):")
    for c in atoms["conflicts"]:
        print(f"  ! {c['issue']}: {c['detail']}")
    print(f"\nSCRUB list: {atoms['scrub'] or '(none)'}")

    dname = recipe["drug"].get("display_name") or recipe["drug"]["name"]

    # ── MERIDIAN ANALYSIS tier (interpretation, grounded in the cited facts) ──
    if args.section == "intelligence":
        drug = recipe["drug"]
        framing = {k: drug.get(k) for k in
                   ("ailux_angle", "vs_ailux", "differentiation_thesis", "overlap")}
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit("the analysis tier requires ANTHROPIC_API_KEY (it is inference).")
        cnote, cfigs = conflicts_note(value_conflicts)
        for i in range(3):
            prose = compose_analysis(dname, asserted, framing, feedback, cnote)
            problems = fail_closed_analysis(prose, asserted, atoms["scrub"], cfigs)
            if not problems:
                break
            if i < 2:
                print(f"  (analysis retry {i + 1}/2)", file=sys.stderr)
        print(f"\n--- MERIDIAN ANALYSIS ---\n{prose}\n")
        if problems:
            print("FAIL-CLOSED (analysis) problems (would block write):")
            for p in problems:
                print(f"  x {p}")
        else:
            print("analysis fail-closed: PASS")
        if args.dry_run:
            print("\n[dry-run] no DB write.")
            return
        if problems:
            raise SystemExit("blocked: analysis introduced unsupported facts.")
        write_narrative(drug, "intelligence", prose, asserted, rh, "llm-analysis")
        mark_feedback_applied(feedback)
        return

    composer = args.composer
    if composer == "llm" and not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n(no ANTHROPIC_API_KEY -> falling back to template composer)")
        composer = "template"
    dname = recipe["drug"].get("display_name") or recipe["drug"]["name"]
    composer_fn = compose_template if composer == "template" else compose_llm
    # The LLM compose step is the soft spot (citation formatting varies run to run).
    # Retry on a fail-closed block before giving up — temperature=0 makes this rare.
    attempts = 1 if composer == "template" else 3
    for i in range(attempts):
        prose = (composer_fn(dname, asserted, atoms["scrub"], feedback)
                 if composer == "llm" else composer_fn(dname, asserted, atoms["scrub"]))
        problems = fail_closed_check(prose, asserted, atoms["scrub"])
        if not problems:
            break
        if i < attempts - 1:
            print(f"  (fail-closed retry {i + 1}/{attempts - 1})", file=sys.stderr)

    print(f"\n--- COMPOSED ({composer}) ---\n{prose}\n")
    if problems:
        print("FAIL-CLOSED problems (would block write):")
        for p in problems:
            print(f"  x {p}")
    else:
        print("fail-closed check: PASS")

    if args.dry_run:
        print("\n[dry-run] no DB write.")
        return
    if problems:
        raise SystemExit("blocked: fail-closed problems present.")
    write_narrative(recipe["drug"], args.section, prose, asserted, rh, composer)
    mark_feedback_applied(feedback)


if __name__ == "__main__":
    main()
