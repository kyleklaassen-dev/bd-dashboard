#!/usr/bin/env python3
"""
api_harvester.py — pull 100% of what external APIs provide into Meridian.

Two-layer capture:
  RAW     -> api_raw_documents (full verbatim jsonb; nothing is ever lost)
  REFINED -> typed tables for review/query (parsed from the same payload)

Sources: CT.gov v2 (full study), openFDA (label + FAERS), ChEMBL, Europe PMC,
Open Targets (GraphQL). All free / no key. Every refined row carries source_url.
Outcome measures + design + NCT-identity verification live in collect_efficacy_apis.py;
this harvester covers everything else.

Usage:
  python3 scripts/api_harvester.py --ctgov [--limit N]
  python3 scripts/api_harvester.py --openfda --chembl --europepmc --opentargets
  python3 scripts/api_harvester.py --all [--dry-run] [--limit N]
Env: SUPABASE_URL, SUPABASE_SERVICE_KEY
"""
import os, sys, json, time, datetime, urllib.request, urllib.parse, urllib.error
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from database import client as c

UA = {"Accept": "application/json", "User-Agent": "Mozilla/5.0 meridian-api-harvester"}
NOW = lambda: datetime.datetime.utcnow().isoformat()
DRY = "--dry-run" in sys.argv
LIMIT = next((int(a.split("=")[1]) for a in sys.argv if a.startswith("--limit=")), None)
ARG = lambda f: f in sys.argv or "--all" in sys.argv


def _get(url, parse=True):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
            d = r.read().decode()
            return json.loads(d) if parse else d
    except Exception as e:
        print(f"  ! GET {url[:90]}: {e}", file=sys.stderr); return None


def _post(url, body):
    try:
        req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                     headers={**UA, "Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"  ! POST {url[:90]}: {e}", file=sys.stderr); return None


def store_raw(source, etype, key, drug_id, url, payload):
    if DRY or payload is None:
        return
    c.insert("api_raw_documents", [dict(
        id=f"{source}:{key}", source=source, entity_type=etype, entity_key=str(key),
        drug_id=drug_id, source_url=url, payload=payload, fetched_at=NOW())], on_conflict="id")


def write(table, rows):
    if rows and not DRY:
        c.insert(table, rows, on_conflict="id")


def drugs():
    rows = c.select_all("drugs", {"select": "id,name,inn_name,brand_name,target", "dashboard_visible": "eq.true"})
    return rows[:LIMIT] if LIMIT else rows


# ---------------- CT.gov: full study -> raw + flow/baseline/AE/eligibility/locations ----------
def harvest_ctgov():
    ncts = c.select_all("trials", {"select": "id,drug_id", "id": "like.NCT*"})
    ncts = ncts[:LIMIT] if LIMIT else ncts
    print(f"CT.gov: {len(ncts)} trials")
    for t in ncts:
        nct, did = t["id"], t.get("drug_id")
        study = _get(f"https://clinicaltrials.gov/api/v2/studies/{nct}")
        if not study:
            continue
        url = f"https://clinicaltrials.gov/study/{nct}"
        store_raw("ctgov", "trial", nct, did, url, study)        # 100% capture
        ps = study.get("protocolSection", {}); rs = study.get("resultsSection", {})
        # eligibility
        el = ps.get("eligibilityModule", {})
        if el and not DRY:
            crit = el.get("eligibilityCriteria", "")
            c.insert("trial_eligibility", [dict(nct_id=nct, drug_id=did, minimum_age=el.get("minimumAge"),
                maximum_age=el.get("maximumAge"), sex=el.get("sex"),
                healthy_volunteers=(str(el.get("healthyVolunteers")).lower() == "yes"),
                criteria_text=crit[:6000], prior_biologic_required=("biologic" in crit.lower()),
                source_url=url, fetched_at=NOW())], on_conflict="nct_id")  # PK is nct_id, not id
        # locations
        locs = ps.get("contactsLocationsModule", {}).get("locations", []) or []
        write("trial_locations", [dict(id=f"{nct}_{i}", nct_id=nct, facility=l.get("facility"),
            city=l.get("city"), state=l.get("state"), country=l.get("country"),
            status=l.get("status"), source_url=url, fetched_at=NOW()) for i, l in enumerate(locs)])
        # participant flow
        flow = rs.get("participantFlowModule", {})
        groups = {g["id"]: g.get("title", "") for g in flow.get("groups", [])}
        prows = []
        for pr in flow.get("periods", []):
            for ms in pr.get("milestones", []):
                for a in ms.get("achievements", []):
                    prows.append(dict(id=f"{nct}_{pr.get('title','')}_{ms.get('type','')}_{a.get('groupId')}"[:120],
                        nct_id=nct, drug_id=did, period_label=pr.get("title"),
                        group_label=groups.get(a.get("groupId"), a.get("groupId")),
                        milestone=ms.get("type"),
                        count_n=int(a["numSubjects"]) if str(a.get("numSubjects") or "").isdigit() else None,
                        source_url=url, fetched_at=NOW()))
        write("trial_participant_flow", prows)
        # baseline
        bl = rs.get("baselineCharacteristicsModule", {})
        bgroups = {g["id"]: g.get("title", "") for g in bl.get("groups", [])}
        brows = []
        for mi, meas in enumerate(bl.get("measures", [])):
            ttl = meas.get("title", "")
            for cl in meas.get("classes", []):
                for cat in cl.get("categories", []):
                    for m in cat.get("measurements", []):
                        v = m.get("value")
                        brows.append(dict(id=f"{nct}_bl{mi}_{cat.get('title','')}_{m.get('groupId')}"[:120],
                            nct_id=nct, drug_id=did, group_label=bgroups.get(m.get("groupId"), m.get("groupId")),
                            characteristic=ttl[:200], category=cat.get("title"),
                            value_num=float(v) if _isnum(v) else None, value_text=None if _isnum(v) else v,
                            unit=meas.get("unitOfMeasure"), source_url=url, fetched_at=NOW()))
        write("trial_baseline_characteristics", brows)
        # adverse events
        ae = rs.get("adverseEventsModule", {})
        aegroups = {g["id"]: g.get("title", "") for g in ae.get("eventGroups", [])}
        aerows = []
        for serious, keyname in [(True, "seriousEvents"), (False, "otherEvents")]:
            for ev in ae.get(keyname, []) or []:
                for s in ev.get("stats", []):
                    aerows.append(dict(id=f"{nct}_{'S' if serious else 'O'}_{ev.get('term','')[:30]}_{s.get('groupId')}"[:120],
                        nct_id=nct, drug_id=did, group_label=aegroups.get(s.get("groupId"), s.get("groupId")),
                        event_term=ev.get("term"), organ_system=ev.get("organSystem"), serious=serious,
                        affected_n=int(s["numAffected"]) if str(s.get("numAffected") or "").isdigit() else None,
                        at_risk_n=int(s["numAtRisk"]) if str(s.get("numAtRisk") or "").isdigit() else None,
                        source_url=url, fetched_at=NOW()))
        write("ct_trial_adverse_events", aerows)
        time.sleep(0.35)
    _stamp("ctgov")


# ---------------- openFDA: label -> raw + drug_label_facts ; FAERS -> fda_adverse_events ------
def harvest_openfda():
    for d in drugs():
        gen = (d.get("inn_name") or d.get("name") or "").strip()
        if not gen:
            continue
        q = urllib.parse.quote(f'openfda.generic_name:"{gen.lower()}"')
        url = f"https://api.fda.gov/drug/label.json?search={q}&limit=1"
        res = _get(url)
        if res and res.get("results"):
            lab = res["results"][0]
            store_raw("openfda_label", "drug", d["id"], d["id"], url, lab)
            facts = []
            of = lab.get("openfda", {})
            appno = (of.get("application_number") or [None])[0]
            sid = lab.get("set_id")
            def add(ft, txt, sec):
                if txt:
                    facts.append(dict(id=f"{d['id']}_{ft}", drug_id=d["id"], application_number=appno,
                        set_id=sid, fact_type=ft, value_text=(txt if isinstance(txt, str) else " ".join(txt))[:6000],
                        section_name=sec, source_url=url, fetched_at=NOW()))
            add("immunogenicity_ada", lab.get("immunogenicity") or _find_ada(lab), "immunogenicity")
            add("boxed_warning", lab.get("boxed_warning"), "boxed_warning")
            add("indication", lab.get("indications_and_usage"), "indications_and_usage")
            write("drug_label_facts", facts)
        # FAERS top reactions
        fq = urllib.parse.quote(f'patient.drug.medicinalproduct:"{gen}"')
        furl = f"https://api.fda.gov/drug/event.json?search={fq}&count=patient.reaction.reactionmeddrapt.exact&limit=15"
        fres = _get(furl)
        if fres and fres.get("results") and not DRY:
            c.insert("fda_adverse_events", [dict(id=f"{d['id']}_{r['term'][:40]}", drug_id=d["id"],
                brand_name=(d.get("brand_name") or ""), reaction=r["term"], report_count=r["count"],
                source_url=furl, fetched_at=NOW()) for r in fres["results"]], on_conflict="id")
        time.sleep(0.3)
    _stamp("openfda_label")


def _find_ada(lab):
    for sec in ("adverse_reactions", "clinical_pharmacology"):
        txt = " ".join(lab.get(sec, []) or []) if isinstance(lab.get(sec), list) else (lab.get(sec) or "")
        i = txt.lower().find("immunogenic")
        if i >= 0:
            return txt[i:i + 1500]
    return None


# ---------------- ChEMBL: molecule chemistry + regulatory metadata ----------------------------
def harvest_chembl():
    for d in drugs():
        name = (d.get("inn_name") or d.get("name") or "").strip()
        if not name:
            continue
        url = f"https://www.ebi.ac.uk/chembl/api/data/molecule/search?q={urllib.parse.quote(name)}&format=json&limit=1"
        res = _get(url)
        mols = (res or {}).get("molecules", [])
        if not mols:
            time.sleep(0.25); continue
        m = mols[0]; store_raw("chembl", "molecule", m.get("molecule_chembl_id"), d["id"], url, m)
        p = m.get("molecule_properties") or {}; s = m.get("molecule_structures") or {}
        write("molecule_properties", [dict(id=d["id"], drug_id=d["id"], chembl_id=m.get("molecule_chembl_id"),
            pref_name=m.get("pref_name"), molecule_type=m.get("molecule_type"), max_phase=str(m.get("max_phase")),
            first_approval=m.get("first_approval"), first_in_class=m.get("first_in_class"),
            black_box_warning=m.get("black_box_warning"), oral=m.get("oral"), parenteral=m.get("parenteral"),
            withdrawn_flag=m.get("withdrawn_flag"), mw_freebase=_num(p.get("mw_freebase")),
            alogp=_num(p.get("alogp")), psa=_num(p.get("psa")), hba=p.get("hba"), hbd=p.get("hbd"),
            ro5_violations=p.get("num_ro5_violations"), canonical_smiles=s.get("canonical_smiles"),
            standard_inchi_key=s.get("standard_inchi_key"), usan_stem=m.get("usan_stem"),
            usan_stem_definition=m.get("usan_stem_definition"),
            atc_classifications=m.get("atc_classifications"), synonyms=m.get("molecule_synonyms"),
            source_url=url, fetched_at=NOW())])
        time.sleep(0.3)
    _stamp("chembl")


# ---------------- Europe PMC: abstracts/MeSH/citations -> literature_records --------------------
def harvest_europepmc():
    for d in drugs():
        name = (d.get("name") or "").strip()
        if not name:
            continue
        url = ("https://www.ebi.ac.uk/europepmc/webservices/rest/search?"
               f"query={urllib.parse.quote(name)}&format=json&pageSize=10&resultType=core")
        res = _get(url)
        for r in ((res or {}).get("resultList", {}).get("result", []) or []):
            store_raw("europepmc", "publication", r.get("id"), d["id"], url, r)
            ji = r.get("journalInfo", {}).get("journal", {})
            write("literature_records", [dict(id=f"epmc_{r.get('id')}", pmid=r.get("pmid"), doi=r.get("doi"),
                title=(r.get("title") or "")[:600], journal=ji.get("title"),
                pub_year=int(r["pubYear"]) if str(r.get("pubYear") or "").isdigit() else None,
                authors=(r.get("authorString") or "")[:800], is_open_access=(r.get("isOpenAccess") == "Y"),
                cited_by_count=r.get("citedByCount"),
                mesh_terms=r.get("meshHeadingList"), keywords=r.get("keywordList"),
                abstract_text=(r.get("abstractText") or "")[:8000], drug_id=d["id"],
                source_url=url, fetched_at=NOW())])
        time.sleep(0.3)
    _stamp("europepmc")


# ---------------- Open Targets: target-disease association (GraphQL) ----------------------------
OT = "https://api.platform.opentargets.org/api/v4/graphql"
def harvest_opentargets():
    targets = {(d.get("target") or "").split("×")[0].split("/")[0].strip() for d in drugs() if d.get("target")}
    for sym in sorted(t for t in targets if t):
        srch = _post(OT, {"query": "query($q:String!){search(queryString:$q,entityNames:[\"target\"]){hits{id name}}}",
                          "variables": {"q": sym}})
        hits = (((srch or {}).get("data") or {}).get("search") or {}).get("hits") or []
        if not hits:
            continue
        ens = hits[0]["id"]
        q = ("query($id:String!){target(ensemblId:$id){approvedSymbol "
             "associatedDiseases(page:{index:0,size:15}){rows{score disease{id name} "
             "datatypeScores{id score}}}}}")
        res = _post(OT, {"query": q, "variables": {"id": ens}})
        tgt = (((res or {}).get("data") or {}).get("target") or {})
        store_raw("opentargets", "target", ens, None, f"{OT}#{ens}", res or {})
        rows = []
        for row in (tgt.get("associatedDiseases", {}) or {}).get("rows", []) or []:
            dis = row.get("disease", {}); dts = {x["id"]: x["score"] for x in row.get("datatypeScores", [])}
            rows.append(dict(id=f"{ens}_{dis.get('id')}", target_symbol=tgt.get("approvedSymbol", sym),
                ensembl_id=ens, disease_label=dis.get("name"), efo_id=dis.get("id"),
                overall_score=row.get("score"), genetic_association=dts.get("genetic_association"),
                known_drug=dts.get("known_drug"), literature=dts.get("literature"),
                datatype_scores=row.get("datatypeScores"), source_url=f"{OT}#{ens}", fetched_at=NOW()))
        write("target_disease_associations", rows)
        time.sleep(0.4)
    _stamp("opentargets")


def _isnum(v):
    try: float(v); return True
    except (TypeError, ValueError): return False
def _num(v): return float(v) if _isnum(v) else None
def _stamp(src):
    if not DRY: c.update("api_sources", f"source=eq.{src}", {"last_run": NOW()})


def main():
    if not any([ARG("--ctgov"), ARG("--openfda"), ARG("--chembl"), ARG("--europepmc"), ARG("--opentargets")]):
        print("specify --ctgov/--openfda/--chembl/--europepmc/--opentargets or --all"); return
    if ARG("--ctgov"): harvest_ctgov()
    if ARG("--openfda"): harvest_openfda()
    if ARG("--chembl"): harvest_chembl()
    if ARG("--europepmc"): harvest_europepmc()
    if ARG("--opentargets"): harvest_opentargets()
    print("Harvest complete" + (" (DRY)" if DRY else ""))


if __name__ == "__main__":
    main()
