#!/usr/bin/env python3
"""Atom extraction (§3 narrative_gen split): turn a recipe into claim atoms + conflict scrub."""

import re

from meridian.products.narrative.common import NCT_RE, RECIPE_DRUG_FIELDS


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
