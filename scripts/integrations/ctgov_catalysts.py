#!/usr/bin/env python3
"""
Phase 1 — ClinicalTrials.gov catalyst engine.

The highest-ROI integration: turns the authoritative US trial registry into a
living catalyst timeline for every asset. CT.gov indexes by intervention name,
so it covers the early codename-stage assets that Open Targets/ChEMBL miss.

For each drug in an area it:
  - queries ClinicalTrials.gov v2 by intervention name
  - extracts every trial (NCT, phase, status, dates, sponsor, conditions)
  - writes PROVENANCE straight through (additive, deduped, safe):
        * drug_sources    - one row per (drug, trial) trial_id claim + a stage claim
        * external_entity_map - one ct_gov row per drug (NCT list in payload)
        * trial_registries - per-drug CT.gov summary
  - PROPOSES catalyst events (future primary-completion = upcoming readout) to a
    report + JSON. Inserts into the live `catalysts` table ONLY with
    --write-catalysts, deduped against existing related_trial_id (no-overwrite).

Free API, no Claude-API cost.

Usage:
    python3 ctgov_catalysts.py --area TL1A                      # dry run (report only)
    python3 ctgov_catalysts.py --area TL1A --write             # write provenance (sources/crosswalk/registry)
    python3 ctgov_catalysts.py --area TL1A --write --write-catalysts   # also insert new catalysts
"""
from __future__ import annotations
import argparse, json, os, sys, time, datetime, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meridian_integrations import SupabaseClient, SUPABASE_URL, ADDED_BY  # noqa

SESSION_LABEL = "phase1-ctgov-2026-06-06"
CTGOV = "https://clinicaltrials.gov/api/v2/studies"
TODAY = datetime.date.today()

PHASE_NORM = {"PHASE4": "Phase 4", "PHASE3": "Phase 3", "PHASE2": "Phase 2",
              "PHASE1": "Phase 1", "EARLY_PHASE1": "Phase 1", "NA": "N/A"}
SIG = {"Phase 4": "high", "Phase 3": "high", "Phase 2": "medium", "Phase 1": "low", "N/A": "low"}
DEAD = {"COMPLETED", "TERMINATED", "WITHDRAWN", "SUSPENDED"}
# Relevance guard: TL1A/IL-23 assets are inflammatory/autoimmune. An onco-only trial
# under the same intervention name is almost certainly a name collision (e.g. AB001,
# EPI-001 are also oncology codenames). Flag for review instead of writing as fact.
ONCO_TERMS = ("cancer", "carcinoma", "tumor", "tumour", "neoplasm", "melanoma",
              "lymphoma", "leukemia", "leukaemia", "myeloma", "sarcoma", "glioma",
              "glioblastoma", "prostate", "breast", "lung", "oncology", "metastatic",
              "crpc", "amyloidosis", "nsclc", "sclc", "mds", "aml", "cll", "nhl",
              "dlbcl", "solid tumor", "advanced solid")
# NOTE: still cannot detect a drug appearing only as a COMPARATOR/BACKBONE arm in an
# onco trial (intervention-name search returns those). Post-run QA (verification agent)
# catches these; future hardening = check the drug is the *experimental* arm, not control.


def _is_collision(conditions: list) -> bool:
    c = " ".join(conditions).lower().replace("tumor necrosis", "")  # avoid 'TNF' false positive
    return any(t in c for t in ONCO_TERMS)


def ctgov_search(name: str, page: int = 20) -> list:
    # expanded to capture the high-value fields we used to drop (endpoints, enrollment,
    # geography, collaborators, why-stopped, results-posted) — landed raw in bronze.
    fields = ",".join(["NCTId", "BriefTitle", "Phase", "OverallStatus",
                       "PrimaryCompletionDate", "StartDate", "LeadSponsorName", "Condition",
                       "EnrollmentCount", "PrimaryOutcomeMeasure", "LocationCountry",
                       "CollaboratorName", "WhyStopped", "ResultsFirstPostDate"])
    qs = urllib.parse.urlencode({"query.intr": name, "pageSize": page, "fields": fields})
    req = urllib.request.Request(f"{CTGOV}?{qs}", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
    except Exception:
        return []
    time.sleep(0.15)
    return data.get("studies", [])


def parse_study(s: dict) -> dict:
    p = s.get("protocolSection", {})
    idm = p.get("identificationModule", {})
    stat = p.get("statusModule", {})
    spon = p.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {})
    phases = p.get("designModule", {}).get("phases", []) or ["NA"]
    phase = PHASE_NORM.get(phases[-1], phases[-1])
    return {
        "nct": idm.get("nctId"), "title": idm.get("briefTitle"),
        "status": stat.get("overallStatus"),
        "pcd": (stat.get("primaryCompletionDateStruct") or {}).get("date"),
        "start": (stat.get("startDateStruct") or {}).get("date"),
        "sponsor": spon.get("name"), "phase": phase,
        "conditions": p.get("conditionsModule", {}).get("conditions", []),
    }


def _as_date(s: str | None):
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def run(area_token: str, area_id: str, write: bool, write_catalysts: bool, do_all: bool = False,
        offset: int = 0, limit: int = 0) -> dict:
    sb = SupabaseClient(write=write)
    if do_all:
        drugs = sb.get("drugs", "select=id,name,target,mechanism,modality,stage&order=id&limit=2000")
    else:
        drugs = sb.drugs_for_area(area_token)
    if offset or limit:
        drugs = drugs[offset: offset + limit if limit else None]

    # per-drug area_id map (from existing catalysts) so --all groups correctly; existing NCTs for dedupe
    area_map, existing_ncts = {}, set()
    try:
        ex = sb.get("catalysts", "select=drug_id,area_id,related_trial_id&related_trial_id=not.is.null&limit=20000")
        for r in ex:
            if r.get("related_trial_id"):
                existing_ncts.add(r["related_trial_id"])
            if r.get("drug_id") and r.get("area_id"):
                area_map.setdefault(r["drug_id"], r["area_id"])
    except Exception:
        pass

    source_rows, crosswalk_rows, registry_rows, catalyst_rows = [], [], [], []
    review_rows, per_drug, payloads = [], [], []

    for d in drugs:
        raw = ctgov_search(d["name"])
        if raw:
            payloads.append({"source": "ct_gov", "entity_type": "drug", "meridian_id": d["id"],
                             "external_id": (raw[0].get("protocolSection", {}).get("identificationModule", {}) or {}).get("nctId"),
                             "endpoint": "studies?query.intr", "payload": {"studies": raw}, "session_label": SESSION_LABEL})
        d_area = area_map.get(d["id"], area_id if not do_all else None)
        all_studies = [parse_study(s) for s in raw]
        all_studies = [s for s in all_studies if s["nct"]]
        # split clean vs collision (onco trial under an inflammatory drug name)
        studies = [s for s in all_studies if not _is_collision(s["conditions"])]
        for s in all_studies:
            if _is_collision(s["conditions"]):
                review_rows.append({"drug": d["name"], "nct": s["nct"], "phase": s["phase"],
                                    "conditions": s["conditions"], "title": s["title"]})
        ncts = [s["nct"] for s in studies]
        upcoming = []
        for s in studies:
            pcd = _as_date(s["pcd"])
            is_future = pcd and pcd >= TODAY and s["status"] not in DEAD
            # provenance: trial_id claim per trial
            source_rows.append({
                "drug_id": d["id"], "drug_name": d["name"], "claim_type": "trial_id",
                "claim_value": s["nct"], "source_url": f"https://clinicaltrials.gov/study/{s['nct']}",
                "source_type": "ct_gov", "source_domain": "clinicaltrials.gov",
                "content_confirms_claim": True, "confidence": "confirmed",
                "added_by": ADDED_BY, "session_label": SESSION_LABEL,
            })
            if is_future:
                upcoming.append(s)
                label = f"{d['name']} {s['phase']} {(s['conditions'] or [''])[0]} primary completion ({s['nct']})".strip()
                cat = {
                    "drug_id": d["id"], "area_id": d_area,
                    "label": label[:240],
                    "catalyst_date": pcd.strftime("%B %Y"), "sort_date": pcd.isoformat(),
                    "catalyst_type": "readout", "significance": SIG.get(s["phase"], "low"),
                    "related_trial_id": s["nct"],
                    "source_url": f"https://clinicaltrials.gov/study/{s['nct']}",
                    "confidence_source": "ct_gov", "confidence_level": "confirmed",
                    "catalyst_status": "pending", "staleness_status": "fresh", "confidence_score": 1.0,
                    "notes": f"{s['title']} | sponsor: {s['sponsor']} | status: {s['status']} | "
                             f"auto-generated from ClinicalTrials.gov ({SESSION_LABEL})",
                }
                catalyst_rows.append({"_new": s["nct"] not in existing_ncts, **cat})
        # stage confirmation from max observed phase
        phases_seen = [s["phase"] for s in studies if s["phase"].startswith("Phase")]
        if phases_seen:
            maxp = sorted(phases_seen)[-1]
            source_rows.append({
                "drug_id": d["id"], "drug_name": d["name"], "claim_type": "stage",
                "claim_value": maxp, "source_url": f"https://clinicaltrials.gov/search?intr={urllib.parse.quote(d['name'])}",
                "source_type": "ct_gov", "source_domain": "clinicaltrials.gov",
                "content_confirms_claim": (str(d.get("stage", "")).lower().replace(" ", "") .find(maxp.split()[-1]) >= 0),
                "confidence": "confirmed", "added_by": ADDED_BY, "session_label": SESSION_LABEL,
            })
        if ncts:
            crosswalk_rows.append({
                "meridian_entity_type": "drug", "meridian_id": d["id"], "meridian_name": d["name"],
                "source": "ct_gov", "external_id": ncts[0], "external_name": "ClinicalTrials.gov",
                "match_method": "intervention_name", "match_confidence": "confirmed",
                "payload": {"nct_ids": ncts, "trial_count": len(ncts)},
                "added_by": ADDED_BY, "session_label": SESSION_LABEL,
            })
            registry_rows.append({
                "drug_id": d["id"], "registry_name": "ClinicalTrials.gov", "registry_id": ncts[0],
                "registry_url": f"https://clinicaltrials.gov/search?intr={urllib.parse.quote(d['name'])}",
                "search_status": "found", "trial_count": len(ncts),
                "last_searched_at": datetime.datetime.utcnow().isoformat() + "Z",
                "verified_by": ADDED_BY, "notes": SESSION_LABEL,
            })
        per_drug.append({"name": d["name"], "our_stage": d.get("stage"),
                         "trials": len(ncts), "upcoming": len(upcoming),
                         "max_phase": (sorted(phases_seen)[-1] if phases_seen else None)})

    new_catalysts = [c for c in catalyst_rows if c["_new"]]
    result = {"per_drug": per_drug, "source_rows": source_rows, "crosswalk_rows": crosswalk_rows,
              "registry_rows": registry_rows, "catalyst_rows": catalyst_rows, "review_rows": review_rows,
              "new_catalysts": new_catalysts, "existing_ncts": len(existing_ncts), "payloads": len(payloads)}

    def safe(fn, label):
        try:
            fn()
        except Exception as e:
            print(f"  [write warn] {label}: {e}")

    if write:
        if payloads:
            safe(lambda: sb.save_payloads(payloads), "bronze")   # full CT.gov responses
        # dedupe drug_sources against existing (drug_id, claim_value, source_url)
        existing_src, existing_reg = set(), set()
        ids = list({r["drug_id"] for r in source_rows})
        for chunk in [ids[i:i+40] for i in range(0, len(ids), 40)]:
            inlist = ",".join(chunk)
            try:
                rows = sb.get("drug_sources", f"select=drug_id,claim_value,source_url&drug_id=in.({inlist})&limit=10000")
                existing_src |= {(r["drug_id"], r.get("claim_value"), r.get("source_url")) for r in rows}
            except Exception:
                pass
        # dedupe trial_registries against existing (drug_id, registry_name)
        reg_ids = list({r["drug_id"] for r in registry_rows})
        for chunk in [reg_ids[i:i+40] for i in range(0, len(reg_ids), 40)]:
            try:
                rows = sb.get("trial_registries", f"select=drug_id,registry_name&drug_id=in.({','.join(chunk)})&limit=10000")
                existing_reg |= {(r["drug_id"], r.get("registry_name")) for r in rows}
            except Exception:
                pass
        fresh_src = [r for r in source_rows if (r["drug_id"], r["claim_value"], r["source_url"]) not in existing_src]
        fresh_reg = [r for r in registry_rows if (r["drug_id"], r["registry_name"]) not in existing_reg]
        if fresh_src:
            safe(lambda: sb.upsert_plain("drug_sources", fresh_src), "drug_sources")
        if crosswalk_rows:
            safe(lambda: sb.upsert("external_entity_map", crosswalk_rows), "crosswalk")
        if fresh_reg:
            safe(lambda: sb.upsert_plain("trial_registries", fresh_reg), "trial_registries")
        print(f"[write] drug_sources +{len(fresh_src)} | crosswalk {len(crosswalk_rows)} | "
              f"registries +{len(fresh_reg)} | bronze {len(payloads)}")
        if write_catalysts and new_catalysts:
            payload = [{k: v for k, v in c.items() if k != "_new"} for c in new_catalysts]
            safe(lambda: sb.upsert_plain("catalysts", payload), "catalysts")
            print(f"[write] catalysts +{len(payload)} new readout events")

    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--area", default="TL1A")
    ap.add_argument("--area-id", default="tl1a")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--write-catalysts", action="store_true")
    ap.add_argument("--all", action="store_true", help="process the entire drug catalog")
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    res = run(args.area, args.area_id, args.write, args.write_catalysts, do_all=args.all,
              offset=args.offset, limit=args.limit)
    today = TODAY.isoformat()
    ws = os.environ.get("MERIDIAN_WORKSPACE", os.getcwd())
    scope = "all" if args.all else args.area.lower()
    out = os.path.join(ws, "docs", "reports", f"{scope}_ctgov_catalysts_{today}.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)

    pd = res["per_drug"]
    with_trials = [d for d in pd if d["trials"]]
    total_trials = sum(d["trials"] for d in pd)
    total_up = sum(d["upcoming"] for d in pd)

    L = []
    L.append(f"# {args.area} — ClinicalTrials.gov Catalyst Engine ({today})")
    L.append("")
    L.append(f"Drugs: **{len(pd)}** | with CT.gov trials: **{len(with_trials)}** "
             f"({round(100*len(with_trials)/max(len(pd),1))}%) | total trials linked: **{total_trials}** | "
             f"upcoming readouts: **{total_up}** | NEW catalysts proposed: **{len(res['new_catalysts'])}** "
             f"(existing in DB for area: {res['existing_ncts']})")
    L.append("")
    L.append("| Drug | Our stage | CT.gov max phase | Trials | Upcoming readouts |")
    L.append("|---|---|---|---|---|")
    for d in sorted(pd, key=lambda x: -x["trials"]):
        L.append(f"| {d['name']} | {d.get('our_stage','')} | {d.get('max_phase') or '—'} | {d['trials']} | {d['upcoming']} |")
    L.append("")
    L.append("## New catalysts proposed (future primary completion, not already in DB)")
    for c in sorted(res["new_catalysts"], key=lambda x: x["sort_date"])[:60]:
        L.append(f"- **{c['sort_date']}** · {c['label']} · _{c['significance']}_ · {c['source_url']}")
    L.append("")
    if res["review_rows"]:
        L.append("## ⚠️ Name-collision / mis-tag review (excluded from writes)")
        L.append("These trials matched the intervention name but are oncology — almost certainly a different "
                 "molecule sharing the codename, or a mis-tagged asset. Flagged, NOT written as fact.")
        L.append("")
        for r in res["review_rows"]:
            L.append(f"- **{r['drug']}** → {r['nct']} ({r['phase']}): {', '.join(r['conditions'])} — {r['title']}")
        L.append("")
    L.append(f"_Provenance written to drug_sources/external_entity_map/trial_registries when --write. "
             f"Catalysts inserted only with --write-catalysts (deduped by related_trial_id)._")
    with open(out, "w") as f:
        f.write("\n".join(L))
    jout = out.replace(".md", "_proposed.json")
    with open(jout, "w") as f:
        json.dump({"new_catalysts": [{k: v for k, v in c.items() if k != "_new"} for c in res["new_catalysts"]]}, f, indent=2)

    print(f"report -> {out}")
    print(f"summary -> drugs {len(pd)} | with_trials {len(with_trials)} | trials {total_trials} | "
          f"upcoming {total_up} | NEW catalysts {len(res['new_catalysts'])}")


if __name__ == "__main__":
    main()
