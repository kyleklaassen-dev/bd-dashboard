#!/usr/bin/env python3
"""Source triangulation + value-conflict detection (§3 narrative_gen split)."""

import re

from meridian.products.narrative.common import _request, NCT_RE


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
