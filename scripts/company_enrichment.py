#!/usr/bin/env python3
"""
Ailux BD Platform — Company Enrichment Pipeline
================================================
Runs overnight (or on-demand) to enrich each company in a given disease area
with current clinical, competitive, and BD intelligence.

What it does per company:
  1. Pulls existing Supabase data (drugs, trials, catalysts, deals, intel)
  2. Fetches fresh clinical trial data from ClinicalTrials.gov v2 API
  3. Calls Claude Sonnet to synthesize updated narrative fields
  4. Upserts to: company_profiles, drugs (detail columns), trials (detail columns),
                 catalysts (upcoming events), deals (company_id wiring)

Usage:
  python scripts/company_enrichment.py --area tl1a
  python scripts/company_enrichment.py --area tl1a --company sanofi
  python scripts/company_enrichment.py --area tl1a --dry-run

Environment variables (required):
  ANTHROPIC_API_KEY   — Claude API key
  SUPABASE_URL        — https://tghntyofptvfhmtchwcv.supabase.co
  SUPABASE_SERVICE_KEY — service role key (full write access)

GitHub Actions: runs 2 AM ET Sun via .github/workflows/company-enrichment.yml
"""

import os, json, time, datetime, argparse, re
from typing import Optional
import requests
import anthropic

# ── Credentials ──────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY  = os.environ["ANTHROPIC_API_KEY"]
SUPABASE_URL       = os.environ["SUPABASE_URL"]
SUPABASE_KEY       = os.environ["SUPABASE_SERVICE_KEY"]

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SB_HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=representation",
}
SB_UPSERT_HEADERS = {**SB_HEADERS, "Prefer": "resolution=merge-duplicates,return=representation"}
CT_API = "https://clinicaltrials.gov/api/v2"

TODAY = datetime.datetime.utcnow().strftime("%Y-%m-%d")


def log(msg: str):
    ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


# ── Supabase helpers ──────────────────────────────────────────────────────────
def sb_get(table: str, params: dict) -> list:
    try:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=SB_HEADERS, params=params)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log(f"  [sb_get {table}] Error: {e}")
        return []


def sb_upsert(table: str, records: list | dict, conflict_cols: str = None) -> list:
    if isinstance(records, dict):
        records = [records]
    if not records:
        return []
    headers = dict(SB_UPSERT_HEADERS)
    if conflict_cols:
        headers["Prefer"] = f"resolution=merge-duplicates,return=representation"
    try:
        r = requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=headers, json=records)
        if r.status_code not in (200, 201):
            log(f"  [sb_upsert {table}] {r.status_code}: {r.text[:300]}")
            return []
        return r.json()
    except Exception as e:
        log(f"  [sb_upsert {table}] Error: {e}")
        return []


def sb_patch(table: str, record: dict, match_params: dict) -> bool:
    """PATCH a single record using query param filters."""
    try:
        r = requests.patch(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=SB_HEADERS,
            params=match_params,
            json=record,
        )
        return r.status_code in (200, 204)
    except Exception as e:
        log(f"  [sb_patch {table}] Error: {e}")
        return False


# ── ClinicalTrials.gov v2 API ─────────────────────────────────────────────────
def fetch_ctgov_study(nct_id: str) -> Optional[dict]:
    """Fetch a single study from ClinicalTrials.gov v2 API."""
    if not nct_id or nct_id in ("Pending", "Pending/China", "N/A"):
        return None
    try:
        r = requests.get(
            f"{CT_API}/studies/{nct_id}",
            params={"format": "json", "fields": (
                "NCTId,BriefTitle,OverallStatus,Phase,EnrollmentInfo,"
                "PrimaryCompletionDateStruct,PrimaryOutcomesModule,"
                "EligibilityCriteria,LocationCountries,SponsorCollaboratorsModule"
            )},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
        log(f"  CT.gov {nct_id}: HTTP {r.status_code}")
        return None
    except Exception as e:
        log(f"  CT.gov {nct_id} error: {e}")
        return None


def parse_ctgov_study(study: dict, nct_id: str) -> dict:
    """Extract key fields from a CT.gov v2 study response."""
    proto = study.get("protocolSection", {})
    id_mod = proto.get("identificationModule", {})
    stat_mod = proto.get("statusModule", {})
    design_mod = proto.get("designModule", {})
    enroll = design_mod.get("enrollmentInfo", {})
    pcd = stat_mod.get("primaryCompletionDateStruct", {})
    outcomes = proto.get("outcomesModule", {}).get("primaryOutcomes", [])

    return {
        "nct_id":          id_mod.get("nctId", nct_id),
        "brief_title":     id_mod.get("briefTitle", ""),
        "status":          stat_mod.get("overallStatus", ""),
        "phase":           ", ".join(design_mod.get("phases", [])),
        "enrollment_n":    enroll.get("count"),
        "pcd_date":        pcd.get("date", ""),
        "pcd_type":        pcd.get("type", ""),
        "primary_outcome": outcomes[0].get("measure", "") if outcomes else "",
    }


# ── Pull existing Supabase context for a company ─────────────────────────────
def fetch_company_context(company_id: str, area_id: str) -> dict:
    """Pull all Supabase data for a company in a given area."""
    # Company info
    companies = sb_get("companies", {"id": f"eq.{company_id}", "select": "*"})
    company = companies[0] if companies else {}

    # Existing profile
    profiles = sb_get("company_profiles", {
        "company_id": f"eq.{company_id}",
        "area_id":    f"eq.{area_id}",
        "select":     "*",
    })
    profile = profiles[0] if profiles else {}

    # Drugs in this area
    drug_area_rows = sb_get("drug_areas", {"area_id": f"eq.{area_id}", "select": "drug_id"})
    drug_ids = [r["drug_id"] for r in drug_area_rows]

    drugs = []
    if drug_ids:
        drug_filter = ",".join(drug_ids)
        all_drugs = sb_get("drugs", {
            "id":      f"in.({drug_filter})",
            "company_id": f"eq.{company_id}",
            "select":  "*",
        })
        drugs = all_drugs

    # Trials for these drugs
    trials = []
    for d in drugs:
        t_rows = sb_get("trials", {"drug_id": f"eq.{d['id']}", "select": "*"})
        trials.extend(t_rows)

    # Recent intel mentioning this company (last 90 days)
    ninety_days_ago = (datetime.datetime.utcnow() - datetime.timedelta(days=90)).strftime("%Y-%m-%d")
    intel_co = sb_get("intel_companies", {
        "company_id": f"eq.{company_id}",
        "select":     "intel_id",
    })
    recent_intel = []
    for row in intel_co[:10]:  # cap at 10 most recent
        items = sb_get("intel", {
            "id":          f"eq.{row['intel_id']}",
            "intel_date":  f"gte.{ninety_days_ago}",
            "select":      "intel_date,headline,body,source_url",
        })
        recent_intel.extend(items)

    # Existing catalysts
    catalysts = sb_get("catalysts", {
        "company_id": f"eq.{company_id}",
        "area_id":    f"eq.{area_id}",
        "resolved":   "eq.false",
        "select":     "*",
        "order":      "sort_date.asc",
    })

    # Existing deals
    deals = sb_get("deals", {
        "company_id": f"eq.{company_id}",
        "area_id":    f"eq.{area_id}",
        "select":     "*",
        "order":      "deal_date.desc",
    })
    # Also check from_company string matches if company_id not yet wired
    if not deals:
        deals_by_name = sb_get("deals", {
            "area_id":      f"eq.{area_id}",
            "or":           f"(from_company.ilike.*{company.get('name','')[:10]}*,to_company.ilike.*{company.get('name','')[:10]}*)",
            "select":       "*",
            "order":        "deal_date.desc",
        })
        deals = deals_by_name

    return {
        "company":      company,
        "profile":      profile,
        "drugs":        drugs,
        "trials":       trials,
        "catalysts":    catalysts,
        "deals":        deals,
        "recent_intel": recent_intel,
    }


# ── Enrich trials from ClinicalTrials.gov ────────────────────────────────────
def enrich_trials_from_ctgov(trials: list) -> list:
    """Fetch fresh CT.gov data for each trial and merge."""
    enriched = []
    for t in trials:
        nct = t.get("id") or t.get("nct_id") or ""
        if not nct or not nct.startswith("NCT"):
            enriched.append({**t, "_ctgov": None})
            continue
        log(f"    CT.gov: {nct}...")
        study = fetch_ctgov_study(nct)
        if study:
            parsed = parse_ctgov_study(study, nct)
            enriched.append({**t, "_ctgov": parsed})
        else:
            enriched.append({**t, "_ctgov": None})
        time.sleep(0.4)   # polite rate limiting
    return enriched


# ── Claude Sonnet enrichment prompt ──────────────────────────────────────────
ENRICHMENT_SYSTEM = """You are a senior biopharma business development analyst for Ailux Biotherapeutics,
a biotech developing a TL1A×IL-23p19 bispecific antibody for IBD. Your job is to synthesize clinical,
competitive, and BD intelligence into structured data that powers a live dashboard.

Key context about Ailux:
- Ailux's lead asset is a TL1A×IL-23p19 bispecific antibody for UC and CD
- Primary BD goal: identify the right pharma partner — timing, deal structure, and positioning vs. competitors
- You are tracking competitors in the TL1A·IBD landscape to understand Ailux's positioning

Output rules:
- All text fields: 2–4 concise, information-dense sentences. No bullet points. No markdown.
- BD Summary focus: financing, deal history, partnering strategy, cash runway, deal timing windows
- Key Risk: the single most important risk for THIS company's program — be specific
- Why It Matters: specifically why this company matters for Ailux's BD strategy
- Catalysts: only real upcoming events with realistic dates — no speculation
- Do not fabricate data. If uncertain, use hedging language ("expected", "anticipated")
- Return ONLY valid JSON — no markdown fences, no explanation text"""


def build_enrichment_prompt(company_id: str, area_id: str, ctx: dict, dry_run: bool = False) -> str:
    co = ctx["company"]
    profile = ctx["profile"]
    drugs_text = json.dumps([{
        k: v for k, v in d.items()
        if k in ("id","name","mechanism","stage","stage_detail","key_data",
                 "route","dosing_type","drug_format","half_life_note","indication_short")
    } for d in ctx["drugs"]], indent=2)

    trials_text = json.dumps([{
        k: v for k, v in t.items()
        if k not in ("created_at", "updated_at")
    } for t in ctx["trials"][:10]], indent=2)

    ctgov_text = json.dumps([{
        "nct_id":          t.get("_ctgov", {}).get("nct_id") if t.get("_ctgov") else t.get("id"),
        "brief_title":     t.get("_ctgov", {}).get("brief_title") if t.get("_ctgov") else t.get("trial_name"),
        "status":          t.get("_ctgov", {}).get("status") if t.get("_ctgov") else t.get("status"),
        "enrollment_n":    t.get("_ctgov", {}).get("enrollment_n") if t.get("_ctgov") else t.get("n_enrollment"),
        "pcd_date":        t.get("_ctgov", {}).get("pcd_date") if t.get("_ctgov") else t.get("readout_date"),
        "primary_outcome": t.get("_ctgov", {}).get("primary_outcome") if t.get("_ctgov") else t.get("primary_endpoint"),
    } for t in ctx["trials"][:10]], indent=2)

    existing_cats = json.dumps([{
        "date":  c.get("catalyst_date"), "label": c.get("label"), "type": c.get("catalyst_type")
    } for c in ctx["catalysts"]], indent=2)

    existing_deals = json.dumps([{
        "date": d.get("deal_date_label"), "headline": d.get("headline"), "detail": d.get("detail"),
        "upfront": d.get("upfront_usd_m"), "total": d.get("total_usd_m"),
    } for d in ctx["deals"][:8]], indent=2)

    recent_intel = json.dumps([{
        "date": i.get("intel_date"), "headline": i.get("headline"), "body": i.get("body","")[:300],
    } for i in ctx["recent_intel"][:6]], indent=2)

    current_profile = json.dumps({
        "platform_summary": profile.get("platform_summary",""),
        "bd_summary":       profile.get("bd_summary",""),
        "key_risk":         profile.get("key_risk",""),
        "why_it_matters":   profile.get("why_it_matters",""),
    }, indent=2)

    return f"""Enrich the company profile for: {co.get('name',company_id)} (ID: {company_id})
Disease area: {area_id}
Today's date: {TODAY}

CURRENT PROFILE (may be stale — update if you have better information):
{current_profile}

DRUGS IN SUPABASE:
{drugs_text}

CLINICAL TRIALS (Supabase + CT.gov live data):
{ctgov_text}

EXISTING CATALYSTS:
{existing_cats}

EXISTING DEALS:
{existing_deals}

RECENT INTEL (last 90 days from news pipeline):
{recent_intel}

Return a JSON object with EXACTLY these fields:

{{
  "company_profile": {{
    "platform_summary": "2-4 sentences: current clinical status, key data, program scope in this disease area.",
    "bd_summary": "2-4 sentences: financing, deal history/structure, partnering strategy, timing window for deals.",
    "key_risk": "1-2 sentences: the single most important risk specific to this company's program.",
    "why_it_matters": "1-2 sentences: why this competitor matters specifically for Ailux's BD strategy.",
    "pipeline_url": "URL to public pipeline page or null"
  }},
  "drug_updates": [
    {{
      "drug_id": "supabase drug id",
      "route": "SC|IV|SC/IV|null",
      "dosing_type": "Induction|Maintenance|Induction + Maintenance|null",
      "drug_format": "mAb|bispecific|nanobody|YTE-modified mAb|null",
      "is_combo": false,
      "dosing_schedule": "e.g. Q3M SC or null",
      "indication_short": "e.g. UC · CD or null",
      "phase_display": "e.g. Phase 3 or null",
      "half_life_note": "e.g. ~74 days or null",
      "vs_ailux": "1 sentence on how this drug compares to Ailux's asset or null"
    }}
  ],
  "trial_updates": [
    {{
      "trial_id": "NCT number (Supabase id)",
      "trial_name": "short descriptive name e.g. STARSCAPE UC — induction",
      "n_enrollment": 980,
      "pcd_label": "human readable: May 2028",
      "status": "Recruiting|Completed|Active not recruiting|Planned"
    }}
  ],
  "catalysts": [
    {{
      "catalyst_date": "e.g. May 2028",
      "sort_date_approx": "YYYY-MM-DD best estimate",
      "label": "concise event label ≤120 chars",
      "catalyst_type": "readout|filing|approval|conference|deal",
      "significance": "high|medium|low",
      "notes": "1 sentence context"
    }}
  ]
}}

Only include drug_updates for drugs that exist in the DRUGS IN SUPABASE list above.
Only include trial_updates for trials with real NCT numbers.
Only include catalysts that are UPCOMING (after {TODAY}) and have a reasonable basis.
Return ONLY the JSON object. No markdown. No explanation."""


# ── Parse and validate Claude's response ─────────────────────────────────────
def parse_enrichment_response(text: str) -> Optional[dict]:
    """Strip markdown fencing and parse JSON."""
    text = text.strip()
    if "```" in text:
        parts = text.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{"):
                text = p
                break
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        log(f"  JSON parse error: {e}\n  Raw: {text[:400]}")
        return None


# ── Write enrichment results to Supabase ─────────────────────────────────────
def write_enrichment(company_id: str, area_id: str, data: dict, dry_run: bool = False):
    if dry_run:
        log(f"  [DRY RUN] Would write: {json.dumps(data, indent=2)[:600]}...")
        return

    cp = data.get("company_profile", {})
    if cp:
        profile_rec = {
            "company_id":        company_id,
            "area_id":           area_id,
            "platform_summary":  cp.get("platform_summary"),
            "bd_summary":        cp.get("bd_summary"),
            "key_risk":          cp.get("key_risk"),
            "why_it_matters":    cp.get("why_it_matters"),
            "pipeline_url":      cp.get("pipeline_url"),
            "last_enriched_at":  datetime.datetime.utcnow().isoformat(),
            "enriched_by":       "claude-enrichment-v1",
        }
        result = sb_upsert("company_profiles", profile_rec)
        log(f"  company_profiles: {'✓' if result else '✗'}")

    for du in data.get("drug_updates", []):
        drug_id = du.pop("drug_id", None)
        if not drug_id:
            continue
        update_fields = {k: v for k, v in du.items() if v is not None}
        if update_fields:
            ok = sb_patch("drugs", update_fields, {"id": f"eq.{drug_id}"})
            log(f"  drug {drug_id}: {'✓' if ok else '✗'}")

    for tu in data.get("trial_updates", []):
        trial_id = tu.pop("trial_id", None)
        if not trial_id:
            continue
        update_fields = {
            "trial_name":   tu.get("trial_name"),
            "n_enrollment": tu.get("n_enrollment"),
            "pcd_label":    tu.get("pcd_label"),
            "status":       tu.get("status"),
        }
        update_fields = {k: v for k, v in update_fields.items() if v is not None}
        if update_fields:
            ok = sb_patch("trials", update_fields, {"id": f"eq.{trial_id}"})
            log(f"  trial {trial_id}: {'✓' if ok else '✗'}")

    # Catalysts — upsert upcoming events
    for cat in data.get("catalysts", []):
        sort_date = cat.get("sort_date_approx") or TODAY
        cat_rec = {
            "catalyst_date":  cat.get("catalyst_date", ""),
            "sort_date":      sort_date,
            "label":          (cat.get("label") or "")[:200],
            "company_id":     company_id,
            "area_id":        area_id,
            "significance":   cat.get("significance", "medium"),
            "catalyst_type":  cat.get("catalyst_type", "readout"),
            "notes":          cat.get("notes", ""),
            "resolved":       False,
        }
        result = sb_upsert("catalysts", cat_rec)
        log(f"  catalyst '{cat_rec['label'][:40]}': {'✓' if result else '✗'}")


# ── Main enrichment loop ──────────────────────────────────────────────────────
def enrich_company(company_id: str, area_id: str, dry_run: bool = False):
    log(f"\n{'='*60}")
    log(f"Enriching: {company_id} / {area_id}")
    log(f"{'='*60}")

    # 1. Pull existing context from Supabase
    log("Fetching Supabase context...")
    ctx = fetch_company_context(company_id, area_id)
    log(f"  Found: {len(ctx['drugs'])} drugs, {len(ctx['trials'])} trials, "
        f"{len(ctx['catalysts'])} catalysts, {len(ctx['deals'])} deals, "
        f"{len(ctx['recent_intel'])} intel items")

    # 2. Enrich trials from ClinicalTrials.gov
    if ctx["trials"]:
        log("Fetching ClinicalTrials.gov data...")
        ctx["trials"] = enrich_trials_from_ctgov(ctx["trials"])

    # 3. Build prompt and call Claude Sonnet
    log("Calling Claude Sonnet for enrichment...")
    prompt = build_enrichment_prompt(company_id, area_id, ctx, dry_run)

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=4096,
            system=ENRICHMENT_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text
        cost_in  = resp.usage.input_tokens  / 1_000_000 * 3.0   # Sonnet input: $3/M
        cost_out = resp.usage.output_tokens / 1_000_000 * 15.0  # Sonnet output: $15/M
        log(f"  Tokens: {resp.usage.input_tokens} in / {resp.usage.output_tokens} out "
            f"(est. ${cost_in+cost_out:.4f})")
    except Exception as e:
        log(f"  Claude API error: {e}")
        return False

    # 4. Parse response
    data = parse_enrichment_response(text)
    if not data:
        log("  Failed to parse response — skipping write")
        return False

    # 5. Write to Supabase
    log("Writing to Supabase...")
    write_enrichment(company_id, area_id, data, dry_run)

    return True


def run_area(area_id: str, company_filter: Optional[str] = None, dry_run: bool = False):
    """Enrich all companies in a given disease area."""
    log(f"\n{'#'*60}")
    log(f"# Company Enrichment Pipeline")
    log(f"# Area: {area_id}  |  Date: {TODAY}")
    log(f"# Model: claude-sonnet-4-5  |  Dry run: {dry_run}")
    log(f"{'#'*60}")

    # Fetch all companies in this area
    company_areas = sb_get("company_areas", {
        "area_id":  f"eq.{area_id}",
        "select":   "company_id",
    })
    company_ids = [r["company_id"] for r in company_areas]

    if company_filter:
        company_ids = [c for c in company_ids if company_filter.lower() in c.lower()]
        log(f"Filtered to {len(company_ids)} companies matching '{company_filter}'")

    if not company_ids:
        log(f"No companies found for area '{area_id}'")
        return

    log(f"Companies to enrich: {company_ids}")
    log(f"Estimated cost: ~${len(company_ids) * 0.05:.2f} (rough estimate)")

    results = {"success": 0, "failed": 0, "skipped": 0}
    for cid in company_ids:
        try:
            ok = enrich_company(cid, area_id, dry_run=dry_run)
            if ok:
                results["success"] += 1
            else:
                results["failed"] += 1
        except Exception as e:
            log(f"  FATAL error for {cid}: {e}")
            results["failed"] += 1
        # Rate limiting — be polite to Claude API
        time.sleep(2)

    log(f"\n{'='*60}")
    log(f"Enrichment complete: {results['success']} success, {results['failed']} failed, "
        f"{results['skipped']} skipped")
    log(f"{'='*60}")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ailux BD Platform — Company Enrichment Pipeline"
    )
    parser.add_argument(
        "--area", required=True,
        help="Disease area ID (e.g. tl1a, tslp, il4ra)"
    )
    parser.add_argument(
        "--company", default=None,
        help="Optional: only enrich companies matching this string (substring match)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Fetch and synthesize data but do not write to Supabase"
    )
    args = parser.parse_args()

    run_area(
        area_id=args.area,
        company_filter=args.company,
        dry_run=args.dry_run,
    )
