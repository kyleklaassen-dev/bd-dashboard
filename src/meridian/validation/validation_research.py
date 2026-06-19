#!/usr/bin/env python3
"""
Ailux BD Platform — Validation Research Pass
=============================================
Runs weekly (via GitHub Actions: validation-research.yml).

Reads all unresolved warnings from drug_validation_results, performs
targeted registry searches for each flagged drug, and writes findings
back to Supabase. After this script runs, any drug that truly has no
trials anywhere will have a confirmed 'not_found' across all searched
registries — making the remaining warnings meaningful rather than "we
haven't looked yet."

CHECKS HANDLED:
  stage_trial_match — drug claims a clinical stage but 0 CT.gov trials
    → Search CT.gov by drug name + aliases
    → Search ANZCTR by drug name
    → If found anywhere: update trial_registries, flip warning → pass
    → If not found: update last_searched_at, keep warning (now confirmed gap)

  field_consistency / brand_name — structural contradictions
    → These require model judgment; this script flags them as 'needs_review'
      rather than attempting auto-resolution.

WRITES:
  trial_registries   — search_status + last_searched_at for each registry checked
  drug_validation_results — check_status updated; verified_by='validation_research'
  drugs.validation_summary — refreshed after each drug resolution

USAGE:
  python src/meridian/validation/validation_research.py          # all unresolved warnings
  python src/meridian/validation/validation_research.py --dry-run
  python src/meridian/validation/validation_research.py --drug cldr-001

ENVIRONMENT:
  SUPABASE_URL         — https://tghntyofptvfhmtchwcv.supabase.co
  SUPABASE_SERVICE_KEY — service role key
"""

import os
import sys
import json
import time
import datetime
import argparse
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

from meridian.credentials import read_key

# ═══════════════════════════════════════════════════════════════════════
# CREDENTIALS
# ═══════════════════════════════════════════════════════════════════════

SUPABASE_URL = read_key("SUPABASE_URL", ".supabase_url", "https://tghntyofptvfhmtchwcv.supabase.co")
SUPABASE_KEY = read_key("SUPABASE_SERVICE_KEY", ".supabase_service_key")
CT_GOV_BASE  = "https://clinicaltrials.gov/api/v2"
ANZCTR_BASE  = "https://www.anzctr.org.au/TrialSearch.aspx"
TODAY        = datetime.datetime.utcnow().strftime("%Y-%m-%d")
NOW_ISO      = datetime.datetime.utcnow().isoformat()

SB_HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=minimal",
}
SB_UPSERT_HEADERS = {
    **SB_HEADERS,
    "Prefer": "resolution=merge-duplicates,return=minimal",
}


# ═══════════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════════

def log(msg: str, indent: int = 0):
    ts     = datetime.datetime.utcnow().strftime("%H:%M:%S")
    prefix = "  " * indent
    print(f"[val_research {ts}] {prefix}{msg}", flush=True)


# ═══════════════════════════════════════════════════════════════════════
# SUPABASE HELPERS
# ═══════════════════════════════════════════════════════════════════════

def sb_get(table: str, params: dict) -> list:
    try:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}",
                         headers=SB_HEADERS,
                         params={**params, "limit": "2000"},
                         timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log(f"[sb_get {table}] {e}")
        return []


def sb_upsert(table: str, records: list | dict,
              on_conflict: str | None = None) -> bool:
    if isinstance(records, dict):
        records = [records]
    if not records:
        return True
    # Normalize to identical key set
    all_keys   = sorted({k for r in records for k in r.keys()})
    normalized = [{k: r.get(k) for k in all_keys} for r in records]
    url    = f"{SUPABASE_URL}/rest/v1/{table}"
    params = {"on_conflict": on_conflict} if on_conflict else {}
    try:
        r = requests.post(url, headers=SB_UPSERT_HEADERS,
                          params=params, json=normalized, timeout=15)
        if r.status_code not in (200, 201):
            log(f"[sb_upsert {table}] {r.status_code}: {r.text[:200]}")
            return False
        return True
    except Exception as e:
        log(f"[sb_upsert {table}] {e}")
        return False


def sb_patch(table: str, record: dict, match_params: dict) -> bool:
    try:
        r = requests.patch(f"{SUPABASE_URL}/rest/v1/{table}",
                           headers=SB_HEADERS,
                           params=match_params,
                           json=record, timeout=15)
        return r.status_code in (200, 204)
    except Exception as e:
        log(f"[sb_patch {table}] {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════
# CT.GOV SEARCH
# ═══════════════════════════════════════════════════════════════════════

def search_ctgov(drug_name: str, aliases: list[str],
                 indication: str = "") -> list[dict]:
    """
    Search CT.gov API v2 for trials matching drug_name or any alias.
    Returns list of {nct_id, title, phase, status, sponsor} dicts.
    """
    found = {}
    search_terms = [drug_name] + (aliases or [])
    # De-duplicate, drop blanks
    search_terms = list({t.strip() for t in search_terms if t and t != "—"})

    for term in search_terms:
        try:
            r = requests.get(
                f"{CT_GOV_BASE}/studies",
                params={
                    "query.term":  term,
                    "filter.overallStatus": "RECRUITING,ACTIVE_NOT_RECRUITING,"
                                            "COMPLETED,NOT_YET_RECRUITING,"
                                            "ENROLLING_BY_INVITATION",
                    "fields":      "NCTId,BriefTitle,OverallStatus,Phase,LeadSponsorName",
                    "pageSize":    20,
                    "format":      "json",
                },
                timeout=15,
            )
            if not r.ok:
                continue
            for study in r.json().get("studies", []):
                p  = study.get("protocolSection", {})
                id_mod = p.get("identificationModule", {})
                nct_id = id_mod.get("nctId", "")
                if not nct_id or nct_id in found:
                    continue
                # Hard gate: drug name must appear in interventions or title
                title   = id_mod.get("briefTitle", "").lower()
                arms    = p.get("armsInterventionsModule", {})
                interv  = " ".join(
                    i.get("name", "") for i in arms.get("interventions", [])
                ).lower()
                haystack = title + " " + interv
                matched = any(
                    t.lower() in haystack or
                    any(p2 in haystack for p2 in t.lower().replace("-", " ").split()
                        if len(p2) > 5)
                    for t in search_terms
                )
                if not matched:
                    continue
                sp = p.get("sponsorCollaboratorsModule", {})
                found[nct_id] = {
                    "nct_id":  nct_id,
                    "title":   id_mod.get("briefTitle", ""),
                    "phase":   (p.get("designModule", {})
                                 .get("phases", [""])[0]
                                 .replace("PHASE", "Phase ")),
                    "status":  p.get("statusModule", {}).get("overallStatus", ""),
                    "sponsor": sp.get("leadSponsor", {}).get("name", ""),
                }
        except Exception as e:
            log(f"  CT.gov search error ({term}): {e}", indent=2)
        time.sleep(0.5)

    return list(found.values())


# ═══════════════════════════════════════════════════════════════════════
# ANZCTR SEARCH
# ═══════════════════════════════════════════════════════════════════════

def search_anzctr(drug_name: str) -> list[dict]:
    """
    Search ANZCTR (Australian New Zealand Clinical Trials Registry)
    by drug name. Returns list of {actrn_id, title, url} dicts.
    ANZCTR does not have a JSON API; we parse the HTML search results.
    """
    found = []
    try:
        r = requests.get(
            ANZCTR_BASE,
            params={"searchTxt": drug_name, "isBasicSearch": "True"},
            headers={"User-Agent": "Ailux-BD-Platform/1.0 (research@ailux.io)"},
            timeout=20,
        )
        if not r.ok:
            return found
        # Simple parse: look for ACTRN numbers in the response HTML
        import re
        actrns = re.findall(r'ACTRN\d{14}', r.text)
        # Deduplicate
        seen = set()
        for actrn in actrns:
            if actrn not in seen:
                seen.add(actrn)
                found.append({
                    "actrn_id": actrn,
                    "url": f"https://www.anzctr.org.au/Trial/Registration/TrialReview.aspx?id={actrn[5:]}",
                })
        if found:
            log(f"  ANZCTR: found {len(found)} trial(s) for '{drug_name}'", indent=2)
    except Exception as e:
        log(f"  ANZCTR search error: {e}", indent=2)
    return found


# ═══════════════════════════════════════════════════════════════════════
# RESOLVE ONE DRUG
# ═══════════════════════════════════════════════════════════════════════

def resolve_drug(drug: dict, dry_run: bool = False) -> dict:
    """
    Search all registries for a drug flagged by stage_trial_match.
    Returns a result dict summarising what was found.
    """
    did       = drug["id"]
    name      = drug.get("name", did)
    aliases   = [a for a in (drug.get("aliases") or []) if a and a != "—"]
    indication = drug.get("indication_short") or ""

    log(f"[{did}] Searching registries for '{name}'...", indent=1)

    result = {
        "drug_id":      did,
        "ct_gov":       [],
        "anzctr":       [],
        "resolved":     False,
        "new_nct_ids":  [],
    }

    # ── CT.gov ────────────────────────────────────────────────────────
    ct_results = search_ctgov(name, aliases, indication)
    result["ct_gov"] = ct_results
    if ct_results:
        log(f"  CT.gov: {len(ct_results)} trial(s) found", indent=2)
        for t in ct_results:
            log(f"    {t['nct_id']} — {t['title'][:70]}", indent=2)
        result["new_nct_ids"] = [t["nct_id"] for t in ct_results]

    # ── ANZCTR ───────────────────────────────────────────────────────
    time.sleep(1.0)
    anzctr_results = search_anzctr(name)
    result["anzctr"] = anzctr_results

    # ── Write to trial_registries ─────────────────────────────────────
    if not dry_run:
        ct_status  = "found" if ct_results  else "not_found"
        az_status  = "found" if anzctr_results else "not_found"

        tr_rows = [
            {
                "drug_id":          did,
                "registry_name":    "ct_gov",
                "search_status":    ct_status,
                "trial_count":      len(ct_results),
                "last_searched_at": NOW_ISO,
                "verified_by":      "validation_research",
                "notes":            (f"{len(ct_results)} trial(s) found via search"
                                     if ct_results else "Searched; no matching trials found"),
                "updated_at":       NOW_ISO,
            },
            {
                "drug_id":          did,
                "registry_name":    "anzctr",
                "search_status":    az_status,
                "trial_count":      len(anzctr_results),
                "last_searched_at": NOW_ISO,
                "verified_by":      "validation_research",
                "notes":            (f"ANZCTR IDs: {[a['actrn_id'] for a in anzctr_results]}"
                                     if anzctr_results else "Searched; no matching trials found"),
                "updated_at":       NOW_ISO,
            },
        ]
        sb_upsert("trial_registries", tr_rows, on_conflict="drug_id,registry_name")

        # ── Update drug_validation_results ────────────────────────────
        found_anywhere = bool(ct_results or anzctr_results)
        result["resolved"] = found_anywhere
        new_status   = "pass" if found_anywhere else "warning"
        new_notes    = (
            f"Found: CT.gov={len(ct_results)}, ANZCTR={len(anzctr_results)}"
            if found_anywhere
            else f"Searched CT.gov + ANZCTR on {TODAY}; no trials found. May be in CDE or not yet registered."
        )
        sb_upsert(
            "drug_validation_results",
            {
                "drug_id":      did,
                "check_type":   "stage_trial_match",
                "check_status": new_status,
                "confidence":   "confirmed" if found_anywhere else "supported",
                "verified_by":  "validation_research",
                "verified_at":  NOW_ISO,
                "details": {
                    "ct_gov_count":   len(ct_results),
                    "anzctr_count":   len(anzctr_results),
                    "new_nct_ids":    result["new_nct_ids"],
                    "last_searched":  TODAY,
                },
                "notes":       new_notes,
                "updated_at":  NOW_ISO,
            },
            on_conflict="drug_id,check_type",
        )

        # ── Refresh validation_summary on drug ────────────────────────
        # Pull all checks for this drug and recompute overall
        all_checks = sb_get("drug_validation_results", {"drug_id": f"eq.{did}", "select": "check_type,check_status"})
        statuses   = {r["check_type"]: r["check_status"] for r in all_checks}
        # Merge in the just-written status
        statuses["stage_trial_match"] = new_status
        all_vals = list(statuses.values())
        overall  = "fail" if "fail" in all_vals else ("warning" if "warning" in all_vals else "pass")
        from meridian.database import update_drug
        update_drug(did, {"validation_summary": {
            **statuses,
            "overall":           overall,
            "last_validated_at": NOW_ISO,
        }})

    return result


# ═══════════════════════════════════════════════════════════════════════
# UPGRADE FIELD_CONSISTENCY / BRAND_NAME WARNINGS → needs_review
# ═══════════════════════════════════════════════════════════════════════

def escalate_structural_warnings(dry_run: bool = False):
    """
    field_consistency and brand_name warnings can't be auto-resolved
    (they require model judgment). Flip their status to 'needs_review'
    so the next session's check surfaces them clearly.
    """
    rows = sb_get("drug_validation_results", {
        "select":       "drug_id,check_type,check_status",
        "check_status": "eq.warning",
        "check_type":   "in.(field_consistency,brand_name)",
    })
    if not rows:
        return
    log(f"Escalating {len(rows)} field_consistency/brand_name warnings → needs_review")
    if not dry_run:
        for row in rows:
            sb_upsert(
                "drug_validation_results",
                {
                    "drug_id":      row["drug_id"],
                    "check_type":   row["check_type"],
                    "check_status": "needs_review",
                    "verified_by":  "validation_research",
                    "verified_at":  NOW_ISO,
                    "notes":        "Requires model/human judgment to resolve. Surfaced for next session.",
                    "updated_at":   NOW_ISO,
                },
                on_conflict="drug_id,check_type",
            )


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

def run(drug_filter: str = None, dry_run: bool = False):
    log(f"{'='*60}")
    log(f"Validation Research Pass — {TODAY}")
    log(f"Dry run: {dry_run} | Drug filter: {drug_filter or 'none'}")
    log(f"{'='*60}")

    # ── Fetch unresolved stage_trial_match warnings ───────────────────
    warning_rows = sb_get("drug_validation_results", {
        "select":       "drug_id,check_type,check_status",
        "check_status": "in.(warning,pending)",
        "check_type":   "eq.stage_trial_match",
    })
    if not warning_rows:
        log("No unresolved stage_trial_match warnings found — nothing to do.")
    else:
        drug_ids = [r["drug_id"] for r in warning_rows]
        if drug_filter:
            drug_ids = [d for d in drug_ids if drug_filter.lower() in d.lower()]

        # Fetch full drug records for name + aliases
        if drug_ids:
            id_filter = ",".join(drug_ids)
            drugs = sb_get("drugs", {
                "id":     f"in.({id_filter})",
                "select": "id,name,aliases,indication_short,stage",
            })
        else:
            drugs = []

        log(f"Drugs to research: {len(drugs)}")

        stats = {"resolved": 0, "still_missing": 0, "new_nct_ids": []}

        for drug in drugs:
            result = resolve_drug(drug, dry_run=dry_run)
            if result["resolved"]:
                stats["resolved"] += 1
                stats["new_nct_ids"].extend(result["new_nct_ids"])
                log(f"  ✓ {drug['id']}: resolved ({len(result['new_nct_ids'])} CT.gov trials found)", indent=1)
            else:
                stats["still_missing"] += 1
                log(f"  ○ {drug['id']}: still missing (searched CT.gov + ANZCTR)", indent=1)
            time.sleep(2.0)

        log(f"\nStage_trial_match results:")
        log(f"  Resolved:       {stats['resolved']} drugs")
        log(f"  Still missing:  {stats['still_missing']} drugs (confirmed gap)")
        log(f"  New NCT IDs:    {stats['new_nct_ids'] or 'none'}")

        if stats["new_nct_ids"] and not dry_run:
            log(f"\n⚠ ACTION REQUIRED: {len(stats['new_nct_ids'])} new NCT IDs found.")
            log(f"  Add these to NCT_SEED_MAP in ct_gov_sync.py and re-run the sync:")
            for nct in stats["new_nct_ids"]:
                log(f"    {nct}")

    # ── Escalate structural warnings → needs_review ───────────────────
    escalate_structural_warnings(dry_run=dry_run)

    log(f"\n{'='*60}")
    log(f"Validation research complete — {TODAY}")
    log(f"{'='*60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ailux BD Platform — Validation Research Pass"
    )
    parser.add_argument("--drug",    help="Drug ID substring to research (e.g. cldr-001)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Search but do not write to Supabase")
    args = parser.parse_args()

    run(drug_filter=args.drug, dry_run=args.dry_run)
