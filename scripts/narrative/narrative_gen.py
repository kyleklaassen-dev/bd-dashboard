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

# ---------------------------------------------------------------------------
# Config / credentials (house pattern)
# ---------------------------------------------------------------------------
SUPA_URL = "https://tghntyofptvfhmtchwcv.supabase.co/rest/v1"
WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read_key(filename, env=None):
    # env var first (CI / GitHub Actions secrets), then the local workspace file.
    if env and os.environ.get(env, "").strip():
        return os.environ[env].strip()
    with open(os.path.join(WORKSPACE, filename)) as f:
        return f.read().strip()


SUPA_KEY = _read_key(".supabase_service_key", "SUPABASE_SERVICE_KEY")

# Drugs columns the overview recipe is allowed to look at (candidate structured atoms).
# Each is admitted to the ASSERTED set only if a confirmed source corroborates it.
RECIPE_DRUG_FIELDS = [
    "name", "company_display", "company_id", "mechanism", "modality",
    "stage", "phase_display", "route", "drug_format", "indication_short",
    "target", "half_life_note", "dosing_schedule",
]

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
def _request(method, endpoint, data=None, extra_headers=None):
    url = f"{SUPA_URL}/{endpoint}"
    body = json.dumps(data).encode() if data is not None else None
    hdrs = {"apikey": SUPA_KEY, "Authorization": f"Bearer {SUPA_KEY}",
            "Content-Type": "application/json"}
    if extra_headers:
        hdrs.update(extra_headers)
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw) if raw.strip() else []
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} {method} /{endpoint.split('?')[0]}: {e.read().decode()[:200]}",
              file=sys.stderr)
        return None


def get(endpoint):
    return _request("GET", endpoint) or []


# ---------------------------------------------------------------------------
# 1. RECIPE — fetch the row set that feeds a drug/overview narrative
# ---------------------------------------------------------------------------
# indication_id (ontology) -> indication_name (patient-intel table key)
IND_NAME = {
    "uc": "Ulcerative Colitis", "cd": "Crohn's Disease", "ra": "Rheumatoid Arthritis",
    "ax-spa": "Axial Spondyloarthritis", "hs": "Hidradenitis Suppurativa",
    "ssc-ild": "Systemic Sclerosis", "ibd": "Inflammatory Bowel Disease",
    "psoriasis": "Psoriasis", "ad": "Atopic Dermatitis", "asthma": "Asthma",
}


def fetch_recipe(drug_id):
    from urllib.parse import quote
    drug = get(f"drugs?id=eq.{drug_id}")
    if not drug:
        raise SystemExit(f"drug '{drug_id}' not found")
    targets = get(f"drug_targets?drug_id=eq.{drug_id}")
    indications = get(f"drug_indications?drug_id=eq.{drug_id}")

    # Patient-population depth — epidemiology + unmet need for the lead indications
    # (fall back to all indications when none are flagged lead).
    _lead = {i.get("indication_id") for i in indications if i.get("is_lead_indication")}
    _inds = _lead or {i.get("indication_id") for i in indications}
    patients = []
    for iid in _inds:
        nm = IND_NAME.get(iid)
        if nm:
            patients += get("indication_patient_intelligence?indication_name=eq."
                            + quote(nm) + "&select=indication_name,patient_count_us,"
                            "patient_count_global,biologic_failure_rate_pct,unmet_need_score,"
                            "unmet_need_narrative,treatment_cascade,patient_reported_priorities,"
                            "source_urls")

    # Competitor depth — other agents hitting the same primary target.
    competitors = []
    prim = next((t["target_id"] for t in targets), None)
    if prim:
        cids = [r["drug_id"] for r in
                get(f"drug_targets?target_id=eq.{prim}&select=drug_id")
                if r.get("drug_id") and r["drug_id"] != drug_id]
        if cids:
            ids = ",".join(sorted(set(cids)))
            competitors = get(f"drugs?id=in.({ids})&dashboard_visible=eq.true"
                              "&select=id,display_name,stage,company_display,source_url")

    # Study-identity resolver inputs: canonical aliases + the trial→publication
    # crosswalk (v73), so a registry claim can triangulate against its paper and
    # any row naming a study by acronym/sponsor-id/DOI resolves to its NCT.
    tids = get(f"trial_identity?drug_id=eq.{drug_id}")
    _ncts = [t["nct_id"] for t in tids if t.get("nct_id")]
    tpubs = get(f"trial_publications?nct_id=in.({','.join(_ncts)})") if _ncts else []

    return {
        "drug": drug[0],
        "sources": get(f"drug_sources?drug_id=eq.{drug_id}"),
        "trial_identity": tids,
        "trial_publications": tpubs,
        "targets": targets,
        "indications": indications,
        # Clinical-evidence depth — each row carries its own CT.gov provenance.
        "trials": get(f"trials?drug_id=eq.{drug_id}"),
        "benchmarks": get(f"drug_clinical_benchmarks?drug_id=eq.{drug_id}"),
        "pk": get(f"drug_pk_parameters?drug_id=eq.{drug_id}"),
        "patients": patients,
        "competitors": competitors,
        "primary_target": prim,
        # Strategic depth — ownership, molecule, escape biology, the clock.
        "deals": get(f"deals?drug_id=eq.{drug_id}"),
        "molecule": get(f"molecule_intelligence?drug_id=eq.{drug_id}"),
        "non_responder": get(f"non_responder_profiles?drug_id=eq.{drug_id}"),
        "catalysts": get(f"catalysts?drug_id=eq.{drug_id}&catalyst_status=neq.resolved"
                         "&order=sort_date.asc&limit=8"),
    }


def recipe_hash(recipe):
    """Stable hash of the underlying rows — drives staleness / drift detection."""
    blob = json.dumps(recipe, sort_keys=True, default=str).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


# ---------------------------------------------------------------------------
# 2. ATOM EXTRACTION (deterministic — no model involved)
# ---------------------------------------------------------------------------
# An atom: {claim, backing, kind, confidence, source_url, source_table, source_row_id}
#   kind ∈ external_confirmed | ontology | structured_unverified | conflict | scrubbed

NCT_RE = re.compile(r"NCT\d{8}", re.I)


def extract_atoms(recipe, known_companies=None):
    drug = recipe["drug"]
    asserted, unverified, conflicts, scrub, flagged = [], [], [], set(), []

    # --- Tier 1: confirmed external sources (the gold atoms) -----------------
    confirmed_text = []   # corroboration corpus
    for s in recipe["sources"]:
        # Skip the reconciler's own audit trail — those are records ABOUT corrections,
        # not substantive claims about the drug, and must not become narrative atoms.
        if (s.get("added_by") or "").startswith("reconcile_drug_integrity"):
            continue
        cv = (s.get("claim_value") or "").strip()
        if s.get("content_confirms_claim") is True:
            asserted.append({
                "claim": cv,
                "kind": "external_confirmed",
                "confidence": s.get("confidence", "confirmed"),
                "source_url": s.get("source_url"),
                "source_table": "drug_sources",
                "source_row_id": str(s.get("id")),
            })
            confirmed_text.append(f"{s.get('claim_type','')}: {cv}")
        elif s.get("content_confirms_claim") is False:
            # Disconfirmed — build a scrub list (e.g. fabricated NCT ids).
            for tok in NCT_RE.findall(cv) + NCT_RE.findall(str(drug.get("source_url", ""))):
                scrub.add(tok.upper())
            conflicts.append({
                "issue": "verifier_disconfirmed",
                "detail": cv,
                "source_url": s.get("source_url"),
            })
    corpus = " || ".join(confirmed_text).lower()

    # --- Tier 2: ontology (targets / indications) — model-confidence atoms ----
    tgts = [t["target_id"] for t in recipe["targets"]]
    if tgts:
        asserted.append({
            "claim": f"Targets: {', '.join(sorted(tgts))} "
                     f"({recipe['targets'][0].get('target_role','')}).",
            "kind": "ontology", "confidence": "inferred",
            "source_url": None, "source_table": "drug_targets",
            "source_row_id": ",".join(t["id"] for t in recipe["targets"]),
        })
    leads = [i["indication_id"] for i in recipe["indications"] if i.get("is_lead_indication")]
    if leads:
        asserted.append({
            "claim": f"Lead indication(s): {', '.join(sorted(leads))}.",
            "kind": "ontology", "confidence": "inferred",
            "source_url": None, "source_table": "drug_indications",
            "source_row_id": ",".join(i["id"] for i in recipe["indications"]),
        })

    # --- Tier 2.5: CLINICAL-EVIDENCE DEPTH (trials / efficacy / PK) -----------
    # Each row is sourced to a CT.gov record -> real, citable depth. This is where
    # a deep narrative comes from (drug_sources is often thin; the clinical tables
    # are where the substance lives).
    def _nct(u):
        m = re.search(r"NCT\d{8}", str(u or ""), re.I)
        return m.group(0).upper() if m else None

    def _url_suspect(u):
        # Fabricated-citation signatures (seen in drug_clinical_benchmarks): a DOI/PII
        # path ending in a word like 'limitations' instead of a numeric id is a model
        # hallucination. CT.gov URLs are trusted (verifiable). Others with these tells
        # are held back from citation and flagged.
        s = str(u or "")
        if not s:
            return False
        if "clinicaltrials.gov" in s:
            return False
        return bool(re.search(r"(limitations|placeholder|example|xxxx|tbd)", s, re.I))

    def _clin_atom(claim, source_url, table, rid):
        if source_url and _url_suspect(source_url):
            flagged.append({"claim": claim, "source_url": source_url, "table": table,
                            "reason": "fabricated_source_url"})
            return
        asserted.append({
            "claim": claim, "kind": "external_confirmed" if source_url else "structured_confirmed",
            "confidence": "confirmed", "source_url": source_url,
            "source_table": table, "source_row_id": str(rid)})

    for t in recipe.get("trials", []) or []:
        nct = _nct(t.get("source_url"))
        ph, ind, stt = t.get("phase"), t.get("indication"), t.get("status")
        pcd = (t.get("primary_completion_date") or "")[:10]
        acr = t.get("study_acronym")
        lbl = (ph or "Trial") + (f" {acr}" if acr else "") + (f" in {ind}" if ind else "")
        if stt:
            lbl += f" ({stt}" + (f", primary completion {pcd}" if pcd else "") + ")"
        if nct:
            lbl += f" [{nct}]"
        _clin_atom(lbl, t.get("source_url"), "trials", t.get("id"))

    for b in recipe.get("benchmarks", []) or []:
        dl = str(b.get("dose_label") or "")
        # skip rows whose dose_label is actually a COMPETITOR name (e.g. 'mirikizumab');
        # the drug's own results carry a dose pattern (mg / IV / SC).
        if not re.search(r"\d+\s*mg|\bIV\b|\bSC\b", dl, re.I):
            continue
        rate, comp = b.get("rate_pct"), b.get("comparator_rate_pct")
        bt = str(b.get("benchmark_type") or "").replace("_", " ")
        tw, tn = b.get("timepoint_weeks"), b.get("trial_name")
        claim = (f"{bt} {rate}%" + (f" vs {comp}% comparator" if comp else "")
                 + (f" at week {tw}" if tw else "") + f", {dl}"
                 + (f" ({tn})" if tn else ""))
        _clin_atom(claim, b.get("source_url"), "drug_clinical_benchmarks", b.get("id"))

    for p in recipe.get("pk", []) or []:
        hl = p.get("half_life_hours")
        if not hl:
            continue
        claim = (f"terminal half-life ~{hl} h" + (f" at {p.get('dose_mg')} mg" if p.get('dose_mg') else "")
                 + (f" {p.get('dose_route')}" if p.get('dose_route') else ""))
        _clin_atom(claim, p.get("source_url"), "drug_pk_parameters", p.get("id"))

    # --- Tier 2.6: PATIENT POPULATION (epidemiology + unmet need) ------------
    for pt in recipe.get("patients", []) or []:
        nm, us, gl = pt.get("indication_name"), pt.get("patient_count_us"), pt.get("patient_count_global")
        bf, un = pt.get("biologic_failure_rate_pct"), pt.get("unmet_need_score")
        parts = ([f"~{int(us):,} US"] if us else []) + ([f"~{int(gl):,} global" if gl else ""])
        pop = " / ".join([p for p in parts if p])
        claim = f"{nm} affects {pop} patients" if pop else f"{nm} patient population"
        if bf:
            claim += f"; ~{bf}% fail biologic therapy"
        if un:
            claim += f" (unmet-need {un}/10)"
        su = pt.get("source_urls")
        su0 = su[0] if isinstance(su, list) and su else None
        asserted.append({
            "claim": claim, "kind": "external_confirmed" if su0 else "structured_confirmed",
            "confidence": "confirmed" if su0 else "inferred", "source_url": su0,
            "source_table": "indication_patient_intelligence", "source_row_id": str(nm)})
        # Patient journey — treatment cascade + what patients prioritize.
        casc = pt.get("treatment_cascade")
        prio = pt.get("patient_reported_priorities")
        jbits = []
        if isinstance(casc, dict):
            soc = casc.get("soc_drugs")
            if soc:
                jbits.append(f"standard of care: {str(soc)[:110]}")
        elif casc:
            jbits.append(f"treatment cascade: {str(casc)[:110]}")
        if isinstance(prio, list) and prio:
            jbits.append("patient priorities: " + ", ".join(str(x) for x in prio[:3]))
        elif prio:
            jbits.append(f"patient priorities: {str(prio)[:90]}")
        if jbits:
            asserted.append({
                "claim": f"{nm} patient journey — " + "; ".join(jbits),
                "kind": "structured_confirmed", "confidence": "inferred", "source_url": su0,
                "source_table": "indication_patient_intelligence", "source_row_id": str(nm) + ":journey"})

    # --- Tier 2.7: COMPETITIVE LANDSCAPE (same primary target) ----------------
    comps = recipe.get("competitors", []) or []
    if comps:
        def _ph(s):
            m = re.search(r"Phase\s*([0-9])", str(s or ""), re.I)
            return int(m.group(1)) if m else 0
        tgt = str(recipe.get("primary_target") or "").upper()
        asserted.append({
            "claim": f"{len(comps)} other {tgt}-targeting agents are in clinical development",
            "kind": "structured_confirmed", "confidence": "inferred", "source_url": None,
            "source_table": "drugs (competitive set)", "source_row_id": tgt})
        for c in sorted([c for c in comps if _ph(c.get("stage")) >= 2],
                        key=lambda c: -_ph(c.get("stage")))[:5]:
            nm, st, co = c.get("display_name"), c.get("stage"), c.get("company_display")
            nct = _nct(c.get("source_url"))
            claim = (f"competing {tgt} agent {nm}" + (f" ({co})" if co else "")
                     + (f" is in {st}" if st else "") + (f" [{nct}]" if nct else ""))
            _clin_atom(claim, c.get("source_url"), "drugs", c.get("id"))

    # --- Tier 2.8: DEAL / OWNERSHIP (precedent valuation) --------------------
    for d in recipe.get("deals", []) or []:
        to, frm = d.get("to_company"), d.get("from_company")
        typ = (d.get("deal_type") or "deal").replace("_", " ")
        tot = d.get("total_usd_m")
        when = d.get("deal_date_label") or (str(d.get("deal_date") or "")[:4])
        if not to:
            continue
        amt = f" for ${int(float(tot)):,}M" if tot else ""
        claim = (f"Owned by {to} — {to} obtained the asset via {typ}"
                 + (f" of {frm}" if frm else "") + amt + (f" ({when})" if when else ""))
        _clin_atom(claim, d.get("source_url"), "deals", d.get("id"))

    # --- Tier 2.9: MOLECULE CHARACTERIZATION ---------------------------------
    for m in (recipe.get("molecule", []) or [])[:1]:
        bits = [m.get("format"), m.get("valency")]
        fc = m.get("fc_engineering")
        ep = m.get("epitope")
        claim = "Molecule: " + ", ".join([b for b in bits if b])
        if fc:
            claim += f"; Fc: {fc}"
        if ep:
            claim += f"; epitope: {ep.split(';')[0][:90]}"
        asserted.append({"claim": claim, "kind": "structured_confirmed", "confidence": "inferred",
                         "source_url": m.get("source_url"), "source_table": "molecule_intelligence",
                         "source_row_id": str(m.get("id"))})

    # --- Tier 3.0: ESCAPE BIOLOGY (target engagement ≠ efficacy) -------------
    for nr in (recipe.get("non_responder", []) or [])[:1]:
        rate = nr.get("non_responder_rate_pct")
        esc = nr.get("active_escape_pathways")
        esc_s = ", ".join(esc[:4]).replace("_", " ") if isinstance(esc, list) else ""
        txt = (nr.get("escape_mechanism_text") or "").split(".")[0]
        claim = "Target-engagement vs efficacy: " + (txt[:150] if txt else "")
        if rate:
            claim += f" (~{rate}% non-responders)"
        if esc_s:
            claim += f"; escape pathways: {esc_s}"
        asserted.append({"claim": claim, "kind": "structured_confirmed", "confidence": "inferred",
                         "source_url": nr.get("source_url"), "source_table": "non_responder_profiles",
                         "source_row_id": str(nr.get("id"))})

    # --- Tier 3.1: CATALYST CLOCK (next readouts) ----------------------------
    seen_cat = set()
    for c in recipe.get("catalysts", []) or []:
        lbl = (c.get("label") or "").split("—")[0].strip()
        key = lbl[:40].lower()
        if not lbl or key in seen_cat:
            continue
        seen_cat.add(key)
        when = c.get("catalyst_date")
        claim = (f"Upcoming catalyst" + (f" ({when})" if when else "") + f": {lbl[:90]}")
        _clin_atom(claim, c.get("source_url"), "catalysts", c.get("id"))
        if len(seen_cat) >= 3:
            break

    # dedup atoms by claim text (benchmarks table has duplicate rows)
    seen, deduped = set(), []
    for a in asserted:
        k = a["claim"]
        if k not in seen:
            seen.add(k); deduped.append(a)
    asserted = deduped

    # --- Tier 3: structured drug fields — admit ONLY if corroborated ----------
    for f in RECIPE_DRUG_FIELDS:
        val = drug.get(f)
        if val in (None, "", [], {}):
            continue
        val_s = str(val)
        if NCT_RE.search(val_s) and scrub:
            # contains a scrubbed token -> never assert
            continue
        # corroboration: do the value's salient tokens appear in confirmed corpus?
        toks = [w for w in re.split(r"[\s,×x/·]+", val_s.lower()) if len(w) > 3]
        hits = sum(1 for w in toks if w in corpus)
        corroborated = hits >= max(1, len(toks) // 3)
        item = {"claim": f"{f} = {val_s}", "field": f, "value": val_s,
                "source_table": "drugs", "source_row_id": drug["id"]}
        if corroborated:
            item.update(kind="structured_confirmed", confidence="confirmed", source_url=None)
            asserted.append(item)
        else:
            item.update(kind="structured_unverified", confidence="unverified", source_url=None)
            unverified.append(item)

    # --- Cross-field conflict detection (stage label vs confirmed source) -----
    _detect_conflicts(drug, corpus, scrub, conflicts, known_companies)

    # --- Reconciliation: a field implicated in a conflict cannot be ASSERTED --
    # (catches e.g. stage='Phase 2' that token-corroborated on the word "phase"
    #  but contradicts the confirmed Phase 1 source). Demote to a conflicted bucket.
    conflicted_fields = {c["field"] for c in conflicts if c.get("field")}
    conflicted, kept = [], []
    for a in asserted:
        if a.get("field") in conflicted_fields:
            a["kind"] = "conflicted"
            conflicted.append(a)
        else:
            kept.append(a)

    return {"asserted": kept, "unverified": unverified, "conflicted": conflicted,
            "conflicts": conflicts, "scrub": sorted(scrub), "flagged": flagged}


def _detect_conflicts(drug, corpus, scrub, conflicts, known_companies=None):
    # Stage: confirmed source mentions a phase; does drugs.stage agree?
    m = re.search(r"phase\s*([0-9])", corpus)
    if m:
        confirmed_phase = m.group(1)
        stage = str(drug.get("stage", ""))
        sm = re.search(r"phase\s*([0-9])", stage.lower())
        if sm and sm.group(1) != confirmed_phase:
            conflicts.append({
                "issue": "stage_mismatch", "field": "stage",
                "detail": f"drugs.stage='{stage}' but confirmed source says Phase {confirmed_phase}",
                # fix hint: deterministic, driven by a CONFIRMED source -> high confidence
                "fix": {"kind": "set_field", "field": "stage",
                        "wrong": stage, "correct": f"Phase {confirmed_phase}",
                        "confidence": "high", "rule": "stage_matches_confirmed_source"},
            })
    # Company-name mismatch in a prose field. SAFE ONLY with a company registry:
    # we flag a parenthetical token ONLY if it resolves to a REAL company in the
    # `companies`/`company_aliases` registry that differs from this drug's company_id.
    # Without the registry we skip entirely (the naive regex caught countries like
    # "(Australia)" and gene names like "(TNFSF15)" — never auto-edit on that).
    if known_companies:
        token_to_cid = known_companies["token_to_cid"]
        cid_to_name = known_companies["cid_to_name"]
        this_cid = drug.get("company_id")
        correct = cid_to_name.get(this_cid)
        for f in ("ailux_angle", "vs_ailux", "drug_summary"):
            txt = str(drug.get(f, ""))
            for co in re.findall(r"\(([A-Z][a-zA-Z][a-zA-Z]+)\)", txt):
                cid = token_to_cid.get(co.lower())
                if cid and cid != this_cid and correct:
                    conflicts.append({
                        "issue": "company_mismatch", "field": f,
                        "detail": f"drugs.{f} names another company '{co}' "
                                  f"(={cid}) but drug.company_id='{this_cid}' ({correct})",
                        # LOW = review-queue only, never auto-edit: a parenthetical
                        # company is often a legitimate PARTNER (originator-attribution
                        # rule), so the "correct" value needs human judgment.
                        "fix": {"kind": "replace_token", "field": f,
                                "wrong": co, "correct": correct,
                                "confidence": "low", "rule": "company_mismatch_review"},
                    })
    if scrub:
        conflicts.append({
            "issue": "scrubbed_identifier_still_in_row",
            "detail": f"row fields still reference disconfirmed id(s): {', '.join(sorted(scrub))}",
            # verifier already disproved these tokens -> complete confidence to remove
            "fix": {"kind": "scrub_tokens", "tokens": sorted(scrub),
                    "confidence": "high", "rule": "remove_verifier_disconfirmed_identifier"},
        })


# ---------------------------------------------------------------------------
# 2.5 TRIANGULATION — attach INDEPENDENT corroborating sources to each atom
# ---------------------------------------------------------------------------
# Depth of trust: a claim resting on a single source is weaker than one backed by
# several INDEPENDENT sources (distinct domains). Per-claim triangulation scans the
# confirming drug_sources pool for rows that independently back each atom and attaches
# them as `corroborations`. write_narrative emits one provenance row per corroboration,
# all sharing the atom's claim_index — so the UI can show "backed by N sources" per claim
# and narrative_source_diversity / narrative_claim_triangulation count real depth.
def _domain(u):
    m = re.search(r"^https?://([^/]+)", str(u or ""))
    d = (m.group(1).lower() if m else "")
    return d[4:] if d.startswith("www.") else d


def _toks(s):
    return {w for w in re.split(r"[\s,×x/·()\[\]:;]+", str(s or "").lower()) if len(w) > 4}


# Independence weighting — WHO controls the source decides how much a corroboration
# is worth. Peer-reviewed/regulatory (independent) > registry (independent platform,
# sponsor-submitted) > independent news > sponsor PR/IR/SEC > our own internal rows.
_PEER_DOMAINS = {"doi.org", "nejm.org", "thelancet.com", "nature.com", "science.org",
                 "cell.com", "jamanetwork.com", "bmj.com", "annals.org", "gastrojournal.org",
                 "journals.lww.com", "academic.oup.com", "oup.com", "sciencedirect.com",
                 "springer.com", "link.springer.com", "wiley.com", "onlinelibrary.wiley.com",
                 "tandfonline.com", "frontiersin.org", "plos.org", "journals.plos.org",
                 "mdpi.com", "pubmed.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov", "europepmc.org",
                 "ashpublications.org", "ahajournals.org", "atsjournals.org"}
_REG_DOMAINS = {"fda.gov", "accessdata.fda.gov", "ema.europa.eu", "hpra.ie", "pmda.go.jp"}
_REGISTRY_DOMAINS = {"clinicaltrials.gov", "anzctr.org.au", "clinicaltrialsregister.eu",
                     "isrctn.com", "chictr.org.cn", "trialregister.nl", "who.int", "jrct.niph.go.jp"}
_NEWS_DOMAINS = {"fiercebiotech.com", "statnews.com", "endpts.com", "biopharmadive.com",
                 "reuters.com", "apnews.com", "bloomberg.com", "biospace.com"}


def _source_tier(url, table):
    """(tier_name, tier_rank). Higher rank = more independent/authoritative."""
    if table == "trial_publications":
        return "peer_reviewed", 5
    d = _domain(url)
    if not d:
        return "internal", 1
    if d in _PEER_DOMAINS:
        return "peer_reviewed", 5
    if d in _REG_DOMAINS:
        return "regulatory", 5
    if d in _REGISTRY_DOMAINS:
        return "registry", 4
    if d in _NEWS_DOMAINS:
        return "independent_news", 3
    return "sponsor", 2          # company IR / PR wire / SEC / any other company domain


# Distinctive study identifiers (trial acronyms): the machine-linkable key that ties an
# independent publication (e.g. nejm.org) to a registry trial (clinicaltrials.gov) for the
# SAME study. Blocklist strips domain-generic all-caps tokens that would false-match.
_STUDY_BLOCKLIST = {"PHASE", "TL1A", "IL23", "STUDY", "TRIAL", "COHORT", "PLACEBO",
                    "WEEKS", "RANDOM", "COHORTS", "ACTIVE", "BISPECIFIC"}
_ACR_RE = re.compile(r"\b([A-Z][A-Z0-9]{4,}(?:-[A-Z0-9]+)*)\b")


def _study_keys(*texts):
    keys = set()
    for t in texts:
        for m in _ACR_RE.findall(str(t or "")):
            if m.split("-")[0] not in _STUDY_BLOCKLIST:
                keys.add(m.upper())
    return keys


DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"'<>)\]]+", re.I)


def build_study_resolver(recipe):
    """alias / DOI / PMID  →  canonical NCT, from trial_identity + trial_publications (v73)."""
    alias2nct, doi2nct, pmid2nct = {}, {}, {}
    for it in recipe.get("trial_identity", []) or []:
        nct = it.get("nct_id")
        for a in (it.get("alias_tokens") or []):
            if a:
                alias2nct[a.upper()] = nct
        if it.get("acronym"):
            alias2nct[it["acronym"].upper()] = nct
    for p in recipe.get("trial_publications", []) or []:
        if p.get("doi"):
            doi2nct[p["doi"].lower()] = p["nct_id"]
        if p.get("pmid"):
            pmid2nct[str(p["pmid"])] = p["nct_id"]
    return {"alias2nct": alias2nct, "doi2nct": doi2nct, "pmid2nct": pmid2nct}


def resolve_ncts(text, url, resolver):
    """Every canonical NCT a piece of text/URL refers to: direct NCT, a resolvable
    study alias (acronym/sponsor id) as a whole token, a known DOI, or a known PMID."""
    blob = f"{text} {url}"
    up = blob.upper()
    ncts = {t.upper() for t in NCT_RE.findall(blob)}
    for alias, nct in resolver["alias2nct"].items():
        if re.search(r"(?<![A-Z0-9])" + re.escape(alias) + r"(?![A-Z0-9])", up):
            ncts.add(nct)
    for doi in DOI_RE.findall(blob):
        nct = resolver["doi2nct"].get(doi.lower())
        if nct:
            ncts.add(nct)
    for pmid, nct in resolver["pmid2nct"].items():
        if re.search(r"(?<!\d)" + re.escape(pmid) + r"(?!\d)", blob):
            ncts.add(nct)
    return ncts


def _corroboration_pool(recipe, resolver):
    """Every CONFIRMING sourced row in the recipe, as an independent-source candidate.
    drug_sources carries free text (token-matchable); the clinical tables carry a
    registered trial id in their URL (the strong, low-noise corroboration signal)."""
    pool = []
    for s in recipe.get("sources", []) or []:
        if (s.get("added_by") or "").startswith("reconcile_drug_integrity"):
            continue
        if s.get("content_confirms_claim") is False:   # disconfirmed → never corroborates
            continue
        url = s.get("source_url")
        dom = s.get("source_domain") or _domain(url)
        if not dom:
            continue
        cv = s.get("claim_value") or ""
        pool.append({"url": url, "table": "drug_sources", "rid": str(s.get("id")), "domain": dom,
                     "keys": {t.upper() for t in NCT_RE.findall(cv + " " + str(url or ""))} | _study_keys(cv),
                     "ncts": resolve_ncts(cv, url, resolver), "toks": _toks(cv), "text": True})
    # study-name field per table → the cross-domain link to its registry trial
    for tbl, key, namef in [("trials", "trials", "study_acronym"),
                            ("drug_clinical_benchmarks", "benchmarks", "trial_name"),
                            ("drug_pk_parameters", "pk", "trial_name"),
                            ("deals", "deals", None), ("molecule_intelligence", "molecule", None),
                            ("drugs", "competitors", None),
                            ("indication_patient_intelligence", "patients", None)]:
        for r in recipe.get(key, []) or []:
            url = r.get("source_url")
            dom = _domain(url)
            if not dom:
                continue
            namev = r.get(namef) if namef else ""
            keys = {t.upper() for t in NCT_RE.findall(str(url))}
            keys |= _study_keys(namev)
            pool.append({"url": url, "table": tbl, "rid": str(r.get("id") or r.get("indication_name")),
                         "domain": dom, "keys": keys, "toks": set(), "text": False,
                         "ncts": resolve_ncts(namev, url, resolver)})
    # v73: authoritative trial publications — each is an INDEPENDENT-domain source for
    # its trial's claims, linked by clinicaltrials.gov itself.
    for p in recipe.get("trial_publications", []) or []:
        url = p.get("pub_url")
        dom = _domain(url)
        if not dom:
            continue
        pool.append({"url": url, "table": "trial_publications",
                     "rid": str(p.get("pmid") or p.get("id")), "domain": dom,
                     "keys": set(), "toks": set(), "text": False,
                     "ncts": {p["nct_id"]} if p.get("nct_id") else set()})
    return pool


def triangulate(asserted, recipe):
    """For each asserted atom, attach INDEPENDENT corroborating sources from a DIFFERENT
    domain: a shared registered trial id (precise), or ≥3 salient-token overlap against a
    text-rich drug_sources row. Sets a['corroborations'] and a['triangulation']
    (# distinct independent domains backing the claim, including its primary)."""
    resolver = build_study_resolver(recipe)
    pool = _corroboration_pool(recipe, resolver)
    for a in asserted:
        a.setdefault("corroborations", [])
        prim_dom = _domain(a.get("source_url")) if a.get("source_url") else None
        used = {prim_dom} if prim_dom else set()
        a_url = str(a.get("source_url") or "")
        a_keys = ({t.upper() for t in NCT_RE.findall(a["claim"] + " " + a_url)}
                  | _study_keys(a["claim"]))
        a_ncts = resolve_ncts(a["claim"], a_url, resolver)   # canonical study identity
        a_toks = _toks(a["claim"])
        for c in pool:
            if c["table"] == a.get("source_table") and c["rid"] == str(a.get("source_row_id")):
                continue                                # not the atom's own primary row
            if not c["domain"] or c["domain"] in used:  # independence = a NEW domain
                continue
            if ((a_ncts & c["ncts"]) or (a_keys & c["keys"])
                    or (c["text"] and len(a_toks & c["toks"]) >= 3)):
                a["corroborations"].append({
                    "source_url": c["url"], "source_table": c["table"],
                    "source_row_id": c["rid"], "content_confirms_claim": True})
                used.add(c["domain"])
        a["triangulation"] = len(used)
    return asserted


# ---------------------------------------------------------------------------
# 2.55 AGREEMENT — do the sources AGREE on the numbers? Surface, don't smooth.
# ---------------------------------------------------------------------------
def _dose_norm(dl):
    s = str(dl or "").lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*mg", s)
    route = next((r for r in ("iv", "sc", "po", "oral") if re.search(r"\b" + r + r"\b", s)), "")
    return ((m.group(1) + "mg") if m else "") + ((" " + route) if route else "")


def detect_value_conflicts(recipe, resolver, tol=5.0):
    """Same drug + metric + timepoint + normalized dose, but materially divergent
    reported rates = a contradiction to surface (data error, or genuinely disagreeing
    sources). Returns one record per conflicted (metric, timepoint, dose)."""
    from collections import defaultdict
    drug_id = recipe["drug"]["id"]
    groups = defaultdict(list)
    for b in recipe.get("benchmarks", []) or []:
        rate = b.get("rate_pct")
        dl = str(b.get("dose_label") or "")
        if rate is None or not re.search(r"\d+\s*mg|\bIV\b|\bSC\b", dl, re.I):
            continue                                   # skip comparator-name rows
        dn = _dose_norm(dl)
        if not dn:
            continue
        nct = next(iter(resolve_ncts(b.get("trial_name") or "", b.get("source_url"), resolver)), None)
        groups[(str(b.get("benchmark_type") or ""), b.get("timepoint_weeks"), dn)].append(
            {"value": float(rate), "source_url": b.get("source_url"),
             "trial_name": b.get("trial_name"), "nct": nct})
    conflicts = []
    for (metric, tw, dn), vals in groups.items():
        distinct = sorted({round(v["value"], 1) for v in vals})
        if len(distinct) >= 2 and (distinct[-1] - distinct[0]) > tol:
            conflicts.append({
                "drug_id": drug_id, "metric": metric, "timepoint_weeks": tw, "dose_norm": dn,
                "nct_id": next((v["nct"] for v in vals if v["nct"]), None),
                "values_json": vals, "value_min": distinct[0], "value_max": distinct[-1],
                "delta": round(distinct[-1] - distinct[0], 1)})
    return conflicts


def persist_value_conflicts(conflicts):
    if not conflicts:
        return
    _request("POST", "narrative_value_conflicts?on_conflict=drug_id,metric,timepoint_weeks,dose_norm",
             conflicts, {"Prefer": "resolution=merge-duplicates,return=minimal"})
    print(f"  persisted {len(conflicts)} value conflict(s)")


def conflicts_note(conflicts):
    """Render conflicts as analysis-prompt guidance + the figures that may be cited."""
    if not conflicts:
        return "", set()
    lines, figs = [], set()
    for c in conflicts:
        m = c["metric"].replace("_", " ")
        wk = f" at week {c['timepoint_weeks']}" if c.get("timepoint_weeks") else ""
        lines.append(f"- {m}{wk} ({c['dose_norm']}) is reported as "
                     f"{c['value_min']}% AND {c['value_max']}% across sources — discordant.")
        figs.add(f"{c['value_min']}%"); figs.add(f"{c['value_max']}%")
    note = ("\n\nDATA CONFLICTS — surface these, do not smooth over (Meridian governance): "
            "if material to the read, flag that the figures disagree.\n" + "\n".join(lines))
    return note, figs


# ---------------------------------------------------------------------------
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
