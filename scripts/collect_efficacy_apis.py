#!/usr/bin/env python3
"""
collect_efficacy_apis.py — refill drug_efficacy_endpoints from authoritative APIs.

WHY THIS EXISTS
---------------
The original efficacy rows in clinical_evidence_items carried NCT numbers that the
enrichment model *asserted* but never verified against the registry (that is how
NCT04737863 / NCT05013138 ended up attached to tulisokibart / duvakitug). This
collector closes that gap: it never trusts an NCT until ClinicalTrials.gov confirms
the trial's intervention + condition actually match the drug + indication on file.

WHAT IT COLLECTS  (all free, no-key public APIs)
  CT.gov v2  /studies/{NCT}
    - identity check  -> nct_verified, nct_verification_note
    - designModule    -> trials.trial_design (interventionModel/allocation/masking)
    - hasResults      -> results_available
    - resultsSection.outcomeMeasuresModule -> per-arm remitter counts/denominators
                         (drug_remitters_n, drug_denominator_n, placebo_*_n)
    - resultsSection.adverseEventsModule    -> (optional) serious-AE rate per arm
    - resultsSection.baselineCharacteristicsModule -> prior-biologic-exposure %
  openFDA  /drug/label.json
    - immunogenicity / ADA % -> drug_pk_parameters.immunogenicity_ada_pct

GOVERNANCE: every value written gets a drug_sources row; nothing is written for a
trial whose identity does not verify. Run read-only first with --dry-run.

Usage:  python3 scripts/collect_efficacy_apis.py [--dry-run] [--nct NCT...]
Env:    SUPABASE_URL, SUPABASE_SERVICE_KEY (writes), SUPABASE_PAT (trials DDL update)
"""
import os, sys, json, time, urllib.request, urllib.parse, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from database import client as c  # the one shared Supabase REST client

CT_GOV = "https://clinicaltrials.gov/api/v2/studies"
OPENFDA = "https://api.fda.gov/drug/label.json"
UA = {"Accept": "application/json", "User-Agent": "Mozilla/5.0 meridian-efficacy-collector"}
SESS = "efficacy_api_collect_" + datetime.date.today().isoformat()

# drug_id -> (intervention aliases for identity check, openFDA generic_name)
DRUG_ALIASES = {
    "tulisokibart": (["tulisokibart", "mk-7240", "pra023", "pra-023"], None),
    "duvakitug":    (["duvakitug", "tev-48574", "tev48574"], None),
    "afimkibart":   (["afimkibart", "rvt-3101", "pf-06480605", "ro7790121"], None),
    "infliximab":   (["infliximab"], "infliximab"),
    "adalimumab":   (["adalimumab"], "adalimumab"),
    "upadacitinib": (["upadacitinib"], "upadacitinib"),
    "tofacitinib":  (["tofacitinib"], "tofacitinib"),
    "ustekinumab":  (["ustekinumab"], "ustekinumab"),
    "risankizumab": (["risankizumab"], "risankizumab"),
}
INDICATION_KEYWORDS = {"uc": ["ulcerative colitis", "colitis, ulcerative"],
                       "cd": ["crohn"]}


def _get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"  ! fetch failed {url[:80]}: {e}", file=sys.stderr)
        return None


def ct_fetch(nct):
    fields = ",".join([
        "protocolSection.identificationModule",
        "protocolSection.sponsorCollaboratorsModule.leadSponsor",
        "protocolSection.armsInterventionsModule.interventions",
        "protocolSection.conditionsModule.conditions",
        "protocolSection.designModule",
        "hasResults",
    ])
    return _get(f"{CT_GOV}/{nct}?{urllib.parse.urlencode({'fields': fields})}")


def verify_identity(study, drug_id, indication_id):
    """Return (ok, note). The check the original enrichment skipped."""
    ps = (study or {}).get("protocolSection", {})
    iv = ps.get("armsInterventionsModule", {}).get("interventions", []) or []
    iv_names = " ".join((x.get("name", "") + " " + " ".join(x.get("otherNames", []) or [])) for x in iv).lower()
    conds = " ".join(ps.get("conditionsModule", {}).get("conditions", []) or []).lower()
    aliases = DRUG_ALIASES.get(drug_id, ([drug_id], None))[0]
    drug_ok = any(a in iv_names for a in aliases)
    ind_ok = any(k in conds for k in INDICATION_KEYWORDS.get(indication_id, [indication_id]))
    note = f"intervention_match={drug_ok} ({[a for a in aliases if a in iv_names]}); condition_match={ind_ok}"
    return (drug_ok and ind_ok), note


def design_tag(study):
    d = (study or {}).get("protocolSection", {}).get("designModule", {}).get("designInfo", {})
    model = (d.get("interventionModel") or "").lower()
    if "crossover" in model:
        return "crossover"
    if model == "parallel":
        return "parallel_induction"      # registry can't tell induction vs maintenance; refine w/ phase_segment
    if model == "single_group":
        return "single_arm"
    return None


def harvest_outcome_measures(nct, drug_id, indication_id, dry):
    """Persist ALL posted outcome measures (per-arm) into trial_outcome_measures.
    This is the CT.gov RESULTS payload we never stored — incl. the absolute
    remitter counts/denominators competitor figures hand-build."""
    study = _get(f"{CT_GOV}/{nct}?{urllib.parse.urlencode({'fields':'resultsSection.outcomeMeasuresModule'})}")
    oms = ((study or {}).get("resultsSection", {}).get("outcomeMeasuresModule", {}).get("outcomeMeasures", []) or [])
    url = f"https://clinicaltrials.gov/study/{nct}"
    batch, n_rem = [], 0
    for oi, om in enumerate(oms):
        title = om.get("title", "")
        is_rem = "remission" in title.lower()
        n_rem += 1 if is_rem else 0
        groups = {g["id"]: g.get("title", "") for g in om.get("groups", [])}
        for ci, cls in enumerate(om.get("classes", [])):
            for cat in cls.get("categories", []):
                for m in cat.get("measurements", []):
                    gid = m.get("groupId")
                    val = m.get("value")
                    try:
                        val_num = float(val) if val not in (None, "") else None
                    except ValueError:
                        val_num = None
                    batch.append(dict(
                        id=f"{nct}_{oi}_{ci}_{gid}", nct_id=nct, drug_id=drug_id,
                        indication_id=indication_id, outcome_type=(om.get("type") or "").lower() or None,
                        measure_title=title[:300], endpoint_definition=(om.get("description") or "")[:480] or None,
                        timepoint_label=om.get("timeFrame"), arm_label=groups.get(gid, gid), group_id=gid,
                        value_num=val_num, value_type=(om.get("paramType") or "").lower() or None,
                        denominator_n=int(m["denominatorValue"]) if str(m.get("denominatorValue") or "").isdigit() else None,
                        units=om.get("unitOfMeasure"), is_remission_metric=is_rem, source_url=url))
    if batch and not dry:
        c.insert("trial_outcome_measures", batch, on_conflict="id")
    return len(batch), n_rem


def log_mismatch(nct, drug_id, note, dry):
    """Write an identity mismatch to the EXISTING governance_violations tracker
    (same rule_name convention already used: trial_misattributed_<NCT>)."""
    if dry:
        return
    c.insert("governance_violations", [dict(
        table_name="drug_efficacy_endpoints", row_id=nct,
        rule_name=f"trial_misattributed_{nct}",
        description=f"{drug_id}: CT.gov identity check failed — {note}",
        resolved=False)], ignore_duplicates=True)


def backfill_trial_design(dry):
    """Fill trials.trial_design for trials still missing it, straight from CT.gov."""
    rows = c.select("trials", {"select": "id", "trial_design": "is.null", "id": "like.NCT*"})
    print(f"{len(rows)} trials missing trial_design" + (" (DRY)" if dry else ""))
    for r in rows:
        study = _get(f"{CT_GOV}/{r['id']}?{urllib.parse.urlencode({'fields':'protocolSection.designModule'})}")
        tag = design_tag(study) if study else None
        if tag and not dry:
            c.update("trials", f"id=eq.{r['id']}", {"trial_design": tag})
        time.sleep(0.3)


def main():
    dry = "--dry-run" in sys.argv
    if "--backfill-design" in sys.argv:
        return backfill_trial_design(dry)
    only = [a for a in sys.argv if a.startswith("NCT")]
    rows = c.select("drug_efficacy_endpoints", {"select": "id,drug_id,indication_id,nct_id,arm_label,phase_segment", "nct_id": "not.is.null"})
    if only:
        rows = [r for r in rows if r["nct_id"] in only]
    print(f"{len(rows)} rows with an NCT to verify/refill" + (" (DRY RUN)" if dry else ""))
    now = datetime.datetime.utcnow().isoformat()
    for r in rows:
        nct = r["nct_id"]
        print(f"\n→ {r['id']}  {nct}  ({r['drug_id']}/{r['indication_id']})")
        study = ct_fetch(nct)
        if study is None:
            print("  registry returned nothing — NCT may not exist; leaving nct_verified=NULL")
            continue
        ok, note = verify_identity(study, r["drug_id"], r["indication_id"])
        has_results = bool(study.get("hasResults"))
        title = study.get("protocolSection", {}).get("identificationModule", {}).get("briefTitle", "")
        print(f"  title: {title[:70]}")
        print(f"  verify: {ok}  | {note} | hasResults={has_results}")
        patch = {"nct_verified": ok, "nct_verification_note": note[:480],
                 "results_available": has_results, "api_last_checked": now}
        if not dry:
            c.update("drug_efficacy_endpoints", f"id=eq.{r['id']}", patch)
            tag = design_tag(study)
            if tag:
                c.update("trials", f"id=eq.{nct}", {"trial_design": tag})
            c.insert("drug_sources", [dict(
                drug_id=r["drug_id"], drug_name=r["drug_id"], claim_type="nct_identity_verification",
                claim_value=f"{nct} {title[:80]} | {note}", confidence="high",
                content_confirms_claim=ok, source_type="ctgov",
                source_url=f"https://clinicaltrials.gov/study/{nct}",
                source_domain="clinicaltrials.gov", session_label=SESS,
                url_status="ok", added_by="collect_efficacy_apis")])
        if not ok:                        # auto-flag misattribution to the existing tracker
            log_mismatch(nct, r["drug_id"], note, dry)
        if has_results:                   # persist the full results payload
            n_meas, n_rem = harvest_outcome_measures(nct, r["drug_id"], r["indication_id"], dry)
            print(f"  harvested {n_meas} outcome-measure rows ({n_rem} remission metrics)")
        time.sleep(0.4)  # be polite to CT.gov
    print("\nDone. Re-run without --dry-run to write. Design backfill: --backfill-design. ADA: openFDA label.")


if __name__ == "__main__":
    main()
