#!/usr/bin/env python3
"""
patient_narrative.py — the Meridian Patient Brief (the North Star layer)
-----------------------------------------------------------------------
"The molecule and the patient are the most important thing." This generates a
cited, derived patient brief per INDICATION from indication_patient_intelligence
— epidemiology, who fails current therapy, the treatment cascade, what patients
prioritize, the unmet-need gap, and what an ideal therapy must deliver — plus a
strategic 'molecule × patient' read for Ailux.

Same discipline as narrative_gen.py (derived, cited, fail-closed) and it REUSES
that machinery: every patient fact becomes a provenance row, so the independence
view, source_collection_gaps and the queue light up for indications for free.
Because indication_patient_intelligence.source_urls is mostly NULL, these facts
land as INTERNAL tier — which correctly flags the whole patient layer as needing
external sources (the evidence collector then sources them).

Stored as entity_narratives(entity_type='indication', section='overview'|'intelligence').

Run:
  python3 scripts/patient_narrative.py --indication "Ulcerative Colitis" --dry-run
  python3 scripts/patient_narrative.py --indication "Ulcerative Colitis"
"""
import os, re, sys, json, hashlib, argparse
from datetime import datetime, timezone
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import narrative_gen as ng  # get/_request/_source_tier/fail_closed_*/feedback/key handling


def fetch_patient(name):
    rows = ng.get("indication_patient_intelligence?indication_name=eq." + quote(name))
    if not rows:
        raise SystemExit(f"no patient-intel row for '{name}'")
    row = rows[0]
    # how many assets are in development for this indication (graph context)
    iid = {v: k for k, v in ng.IND_NAME.items()}.get(name)
    n_assets = 0
    if iid:
        n_assets = len(ng.get(f"drug_indications?indication_id=eq.{iid}&select=drug_id"))
    return {"row": row, "indication_id": iid, "n_assets": n_assets}


def _src(row):
    su = row.get("source_urls")
    if isinstance(su, list) and su:
        return su[0]
    if isinstance(su, str) and su.strip():
        return su.split(",")[0].strip()
    return None


# (field, label) → narrated as one atom when the field is populated.
PATIENT_FIELDS = [
    ("global_prevalence", "Epidemiology"), ("patient_count_us", "US patients"),
    ("patient_count_global", "Global patients"), ("market_size_usd_bn", "Market size ($B)"),
    ("biologic_failure_rate_pct", "Biologic failure rate (%)"),
    ("biologic_nonresponse_rate", "Biologic non-response"),
    ("annual_loss_of_response", "Annual loss of response"),
    ("remission_rate_soc_pct", "SoC remission rate (%)"),
    ("clinical_remission_benchmark", "Clinical remission benchmark"),
    ("endoscopic_remission_benchmark", "Endoscopic remission benchmark"),
    ("deep_remission_benchmark", "Deep remission benchmark"),
    ("patients_no_options", "Patients out of options"),
    ("unmet_need_narrative", "Unmet need"), ("why_it_matters", "Why it matters"),
    ("quality_of_life_impact", "Quality-of-life burden"),
    ("escalation_triggers", "Escalation triggers"),
    ("preferred_formulation", "Preferred formulation"),
    ("trial_endpoint_gap", "Trial-endpoint gap"),
    ("fda_preferred_endpoints", "FDA-preferred endpoints"),
    ("surgical_rate_lifetime", "Lifetime surgical rate"),
    ("colectomy_rate", "Colectomy rate"),
]


def extract_patient_atoms(rec):
    row = rec["row"]
    src = _src(row)
    name = row["indication_name"]
    atoms = []

    def add(claim, confirmed=False):
        atoms.append({
            "claim": claim,
            "kind": "external_confirmed" if (confirmed and src) else "patient_structured",
            "confidence": "confirmed" if (confirmed and src) else "inferred",
            "source_url": src if confirmed else None,
            "source_table": "indication_patient_intelligence",
            "source_row_id": name})

    # headline epidemiology / unmet-need score as their own crisp atoms
    us, gl = row.get("patient_count_us"), row.get("patient_count_global")
    if us or gl:
        parts = ([f"~{int(us):,} US"] if us else []) + ([f"~{int(gl):,} global"] if gl else [])
        add(f"{name} affects {' / '.join(parts)} patients", bool(src))
    un = row.get("unmet_need_score") or row.get("unmet_need_severity")
    if un:
        add(f"{name} unmet-need score {un}/10")
    bf = row.get("biologic_failure_rate_pct")
    if bf:
        add(f"~{bf}% of {name} patients fail biologic therapy")

    casc = row.get("treatment_cascade")
    if isinstance(casc, dict):
        soc = casc.get("soc_drugs")
        if soc:
            add(f"{name} standard of care: {str(soc)[:160]}")
        surg = casc.get("surgical")
        if surg:
            add(f"{name} surgical options: {', '.join(surg) if isinstance(surg, list) else str(surg)[:80]}")
    prio = row.get("patient_reported_priorities")
    if isinstance(prio, list) and prio:
        add(f"{name} patients prioritize: " + ", ".join(str(x) for x in prio[:5]))

    for f, label in PATIENT_FIELDS:
        v = row.get(f)
        if v in (None, "", [], {}):
            continue
        vs = ", ".join(str(x) for x in v) if isinstance(v, list) else str(v)
        add(f"{label}: {vs[:220]}")

    if rec.get("n_assets"):
        atoms.append({"claim": f"{rec['n_assets']} assets are in development for {name}",
                      "kind": "structured_confirmed", "confidence": "inferred", "source_url": None,
                      "source_table": "drug_indications", "source_row_id": rec.get("indication_id") or name})

    # dedup by claim
    seen, out = set(), []
    for a in atoms:
        if a["claim"] not in seen:
            seen.add(a["claim"]); out.append(a)
    return out


PATIENT_SYSTEM = (
    "You are Meridian writing a PATIENT BRIEF — the layer Ailux cares most about, because the "
    "molecule and the patient are the most important thing. You receive NUMBERED claim atoms about "
    "an indication's patients. Write a derived, fluent brief using ONLY facts in the atoms; every "
    "fact-bearing clause carries an inline [n] citation; if you cannot cite a clause, delete it. "
    "Cover, when the atoms provide them: (a) who the patient is and the disease burden, (b) the "
    "treatment cascade and who fails current therapy, (c) what patients themselves prioritize, "
    "(d) the unmet-need gap and patients out of options, (e) the efficacy ceiling of current "
    "therapy. Short markdown section headers. No new facts, no disease knowledge beyond the atoms. "
    "Under 320 words.")

PATIENT_ANALYSIS_SYSTEM = (
    "You are Meridian's scientist-strategist writing for Ailux (ALX001, a TL1A×IL-23 bispecific). "
    "From the NUMBERED patient facts, write a 'Meridian Patient Analysis' — explicitly an "
    "INTERPRETATION — on MOLECULE × PATIENT FIT: (1) which unmet need in this population a "
    "differentiated mechanism must address, (2) what an ideal therapy's profile would have to "
    "deliver for these patients, (3) where Ailux's bispecific is rationally positioned for the "
    "patients who fail current therapy. Reason ONLY from the facts; cite [n]; introduce no new "
    "number/%/figure. Start with exactly "
    "'_Meridian Patient Analysis — interpretation, grounded in the cited facts._'. Under 190 words.")


def _compose(system, name, atoms, feedback=None):
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    numbered = "\n".join(f"[{i+1}] {a['claim']}" for i, a in enumerate(atoms))
    prompt = (f"INDICATION: {name}\n\nPATIENT FACTS:\n{numbered}"
              + ng.feedback_block(feedback) + "\n\nWrite it now.")
    r = client.messages.create(model="claude-sonnet-4-6", max_tokens=700, temperature=0,
                               system=system, messages=[{"role": "user", "content": prompt}])
    return r.content[0].text.strip()


def write_patient(name, section, prose, atoms, rh):
    payload = {"entity_type": "indication", "entity_id": name, "section": section,
               "body_md": prose, "confidence": "inferred", "source_rows_hash": rh, "stale": False,
               "generated_by": "patient_narrative.py@v0", "updated_at": datetime.now(timezone.utc).isoformat()}
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
    print(f"  wrote indication/{section} {nid} + {len(prov)} provenance rows")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--indication", required=True)
    ap.add_argument("--section", default="both", choices=["overview", "intelligence", "both"])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rec = fetch_patient(args.indication)
    atoms = extract_patient_atoms(rec)
    rh = hashlib.sha256(json.dumps(rec["row"], sort_keys=True, default=str).encode()).hexdigest()[:16]
    name = rec["row"]["indication_name"]
    sourced = sum(1 for a in atoms if a.get("source_url"))
    print(f"\n=== Patient Brief: {name} — {len(atoms)} atoms ({sourced} externally sourced) ===")
    for i, a in enumerate(atoms):
        print(f"  [{i+1}] ({a['kind']}) {a['claim'][:88]}")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n(no ANTHROPIC_API_KEY — atoms only)"); return
    want = ["overview", "intelligence"] if args.section == "both" else [args.section]

    def _analysis_check(prose, atoms, scrub):
        # reuse the analysis fail-closed, but accept our 'Meridian Patient Analysis' label
        probs = ng.fail_closed_analysis(prose, atoms, scrub)
        return [p for p in probs if not (p == "missing the interpretation label"
                                         and "Meridian Patient Analysis" in prose)]

    for sec in want:
        sys_p = PATIENT_SYSTEM if sec == "overview" else PATIENT_ANALYSIS_SYSTEM
        checker = ng.fail_closed_check if sec == "overview" else _analysis_check
        fb = ng.fetch_feedback("indication", name, sec)
        prose = problems = None
        for i in range(3):
            prose = _compose(sys_p, name, atoms, fb)
            problems = checker(prose, atoms, [])
            if not problems:
                break
            print(f"  ({sec} retry {i+1}/2: {problems[0][:48]})", file=sys.stderr)
        print(f"\n--- {sec.upper()} ---\n{prose}\n", "PASS" if not problems else f"PROBLEMS {problems}")
        if args.dry_run:
            continue
        if not problems:
            write_patient(name, sec, prose, atoms, rh)
            ng.mark_feedback_applied(fb)
    if args.dry_run:
        print("\n[dry-run] no write.")


if __name__ == "__main__":
    main()
