#!/usr/bin/env python3
"""
Ailux BD Platform — Systematic Intelligence Pipeline
=====================================================
The full 7-step conditional intelligence model.

ARCHITECTURE:
  Strategic Competitive Entity (top-level unit in the dashboard)
    └── Drugs / Programs     (one or many per entity)
          └── Trials         (synced by ct_gov_sync.py — Step 3)
                └── Catalysts (generated from trial dates — Step 4)
    └── Deals                (discovered + enriched — Step 6)
    └── Company Profile      (narrative fields — Step 5)

STEP OVERVIEW (if/then logic):

  STEP 1 — Entity Discovery
    IF new competitor found in target/disease space:
      → Create strategic entity, drug, company records
      → tag discovery_status='auto', confidence_score
    Called once per area per pipeline run.

  STEP 2 — Drug Mapping  (handled by Supabase entity_id on drugs)
    IF entity has one drug → show single drug in expanded row
    IF entity has multiple drugs → group under platform entity
    IF two companies share one asset → entity_type = 'partnership'
    (The data model enforces this; no runtime step needed here.)

  STEP 3 — Trial Sync  (handled by ct_gov_sync.py — runs BEFORE this script)
    IF drug has known NCT IDs → fetch from CT.gov, upsert trials table
    IF drug has no NCT ID → search CT.gov by name
    This script reads from the already-populated trials table.

  STEP 4 — Catalyst Generation
    IF trial has primary_completion_date → create upcoming catalyst
    IF company disclosed expected data timing → override with company date
    IF catalyst date has passed → mark resolved, search for results

  STEP 5 — Company Enrichment (Claude Sonnet)
    IF company profile is incomplete → generate all narrative fields
    IF public company → collect market cap, cash runway
    IF private → collect financing history, key investors
    Writes: company_profiles (all fields), drugs (detail columns)

  STEP 6 — Deal Intelligence
    IF new deal found for company/asset → create deal record
    IF existing deal missing fields → back-fill from Claude synthesis

  STEP 7 — Dashboard Integration (handled by frontend JS)
    The dashboard reads directly from Supabase — no pipeline step needed.

USAGE:
  python scripts/company_enrichment.py --area tl1a
  python scripts/company_enrichment.py --area tl1a --company sanofi
  python scripts/company_enrichment.py --area tl1a --discover-only
  python scripts/company_enrichment.py --area tl1a --dry-run

DEPENDS ON:
  ct_gov_sync.py must run FIRST (populates trials table for Step 3 context)

ENVIRONMENT:
  ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY
"""

import os
import json
import time
import datetime
import argparse
import re
from typing import Optional

import requests
import anthropic

try:
    from identity_resolution import DrugIdentityResolver
    _IDENTITY_RESOLVER_AVAILABLE = True
except ImportError:
    _IDENTITY_RESOLVER_AVAILABLE = False


# ══════════════════════════════════════════════════════════════════════════
# CREDENTIALS + SETUP
# ══════════════════════════════════════════════════════════════════════════

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
SB_UPSERT_HEADERS = {
    **SB_HEADERS,
    "Prefer": "resolution=merge-duplicates,return=representation",
}

TODAY    = datetime.datetime.utcnow().strftime("%Y-%m-%d")
NOW_ISO  = datetime.datetime.utcnow().isoformat()

CT_API = "https://clinicaltrials.gov/api/v2"


def log(msg: str, indent: int = 0):
    ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
    prefix = "  " * indent
    print(f"[{ts}] {prefix}{msg}", flush=True)


# ══════════════════════════════════════════════════════════════════════════
# SUPABASE HELPERS
# Single source of truth for all Supabase I/O in this script.
# ══════════════════════════════════════════════════════════════════════════

def sb_get(table: str, params: dict) -> list:
    try:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}",
                         headers=SB_HEADERS, params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log(f"[sb_get {table}] {e}", indent=1)
        return []


def sb_upsert(table: str, records: list | dict) -> list:
    if isinstance(records, dict):
        records = [records]
    if not records:
        return []
    try:
        r = requests.post(f"{SUPABASE_URL}/rest/v1/{table}",
                          headers=SB_UPSERT_HEADERS, json=records, timeout=15)
        if r.status_code not in (200, 201):
            log(f"[sb_upsert {table}] {r.status_code}: {r.text[:300]}", indent=1)
            return []
        return r.json()
    except Exception as e:
        log(f"[sb_upsert {table}] {e}", indent=1)
        return []


def sb_post(table: str, record: dict) -> Optional[dict]:
    try:
        r = requests.post(f"{SUPABASE_URL}/rest/v1/{table}",
                          headers=SB_HEADERS, json=record, timeout=15)
        if r.status_code not in (200, 201):
            log(f"[sb_post {table}] {r.status_code}: {r.text[:200]}", indent=1)
            return None
        data = r.json()
        return data[0] if data else None
    except Exception as e:
        log(f"[sb_post {table}] {e}", indent=1)
        return None


def sb_patch(table: str, record: dict, match_params: dict) -> bool:
    try:
        r = requests.patch(f"{SUPABASE_URL}/rest/v1/{table}",
                           headers=SB_HEADERS, params=match_params,
                           json=record, timeout=15)
        return r.status_code in (200, 204)
    except Exception as e:
        log(f"[sb_patch {table}] {e}", indent=1)
        return False


# ══════════════════════════════════════════════════════════════════════════
# COMPANY NAME → SUPABASE ID MAPPING
# ══════════════════════════════════════════════════════════════════════════

COMPANY_ALIASES = {
    "johnson & johnson":     "jnj",
    "j&j":                   "jnj",
    "eli lilly":             "lilly",
    "roche":                 "roche",
    "roche/genentech":       "roche",
    "genentech":             "roche",
    "boehringer ingelheim":  "boehringer",
    "bristol myers squibb":  "bms",
    "bristol-myers squibb":  "bms",
    "merck":                 "merck",
    "merck & co":            "merck",
    "merck & co.":           "merck",
    "generate:biomedicines": "generate",
    "harbour biomed":        "harbourbiomed",
    "santa ana bio":         "santaana",
}


def get_company_map() -> dict[str, str]:
    """Fetch all companies from Supabase → dict: name/alias → id."""
    try:
        rows = sb_get("companies", {"select": "id,name"})
        cmap = {}
        for row in rows:
            cmap[row["id"].lower()]   = row["id"]
            cmap[row["name"].lower()] = row["id"]
        cmap.update(COMPANY_ALIASES)
        return cmap
    except Exception as e:
        log(f"Company map fetch error: {e}")
        return {}


def resolve_company_id(name: str, company_map: dict) -> Optional[str]:
    lc = (name or "").strip().lower()
    if not lc:
        return None
    if lc in company_map:
        return company_map[lc]
    for key, cid in company_map.items():
        if len(lc) >= 4 and (lc in key or key in lc):
            return cid
    return None


# ══════════════════════════════════════════════════════════════════════════
# STEP 1 — ENTITY DISCOVERY
#
# IF new competitor found in the target/disease space:
#   → Create company + drug + company_areas records
#   → Tag discovery_status='auto', confidence_score
#   → Link to disease area
#
# Phase A: Live web search for current competitive landscape (web_search_20250305)
# Phase B: Claude Haiku compares landscape against existing DB, extracts new entities
# Secondary: recent Supabase intel used as supplemental signal if available
# ══════════════════════════════════════════════════════════════════════════

DISCOVERY_SYSTEM = """You are a biopharma competitive intelligence analyst for Ailux Biotherapeutics.
Identify NEW companies or drug programs that are relevant to the given disease area but not yet in our
database. Return ONLY valid JSON — no markdown, no explanation."""

LANDSCAPE_SEARCH_SYSTEM = """You are a biopharma competitive intelligence researcher.
Use web_search to find ALL companies with active clinical-stage programs in the given target area.
Include large pharma (Pfizer, Roche, AZ, Lilly, etc.) as well as small/mid-cap biotechs.
Focus on programs that are Phase 1 or later. Be comprehensive — missing a player is worse than
a false positive. Return a structured text report: company name, drug name/ID, mechanism, stage,
indication, any partnership info."""


def gather_landscape_intel(area_id: str) -> str:
    """
    Phase A of Step 1: live web search for current competitive landscape.
    Returns free-text summary or empty string on failure.
    """
    area_label = AREA_LABELS_MAP.get(area_id, area_id)
    year = datetime.datetime.utcnow().year

    prompt = (
        f"Search for ALL companies with active clinical-stage drug programs targeting {area_label} "
        f"as of {year-1}-{year}. Include:\n"
        "1. Large pharma (Pfizer, Roche, AstraZeneca, Lilly, Sanofi, AbbVie, etc.) with relevant programs\n"
        "2. Mid-cap and small-cap biotechs\n"
        "3. Academic spinouts with IND-stage programs\n"
        "For each, find: company name, drug name/compound ID, mechanism of action, clinical phase, "
        "indication (UC, CD, asthma, etc.), partnership details if any.\n"
        "Search multiple angles: clinical trial registries, conference abstracts, pipeline pages, press releases."
    )

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2500,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
            system=LANDSCAPE_SEARCH_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        parts = [block.text for block in resp.content if hasattr(block, "text") and block.text]
        return "\n\n".join(parts)
    except Exception as e:
        log(f"  Landscape search error: {e}", indent=1)
        return ""


def step1_discover_new_entities(area_id: str, company_map: dict,
                                  dry_run: bool = False) -> int:
    """
    Proactively discover new competitors via live web search, then diff against
    the existing Supabase entity list. Supplemented by recent in-DB intel.
    Returns count of new entities created.
    """
    log(f"\n{'─'*50}")
    log(f"STEP 1 — Entity Discovery (area: {area_id})")
    log(f"{'─'*50}")

    existing_cos = sb_get("company_areas", {
        "area_id": f"eq.{area_id}", "select": "company_id"
    })
    existing_ids = {r["company_id"] for r in existing_cos}

    # Fetch indication_group for this area (e.g. tl1a → 'ibd').
    # New drugs are tagged to BOTH the specific area AND the indication_group area,
    # so the frontend's expanded drug row (filtered by indication_group) picks them up.
    area_meta = sb_get("disease_areas", {"id": f"eq.{area_id}", "select": "indication_group"})
    indication_group = (area_meta[0].get("indication_group") if area_meta else None) or area_id

    # ── Phase A: live web search for current landscape ──────────────────────
    log("  Phase A — Web landscape search...", indent=1)
    landscape_text = gather_landscape_intel(area_id)
    if landscape_text:
        log(f"  Landscape search returned {len(landscape_text)} chars", indent=1)
    else:
        log("  Landscape search returned nothing — will rely on local intel", indent=1)

    # ── Secondary: recent Supabase intel (last 14 days) ─────────────────────
    fourteen_ago = (datetime.datetime.utcnow() - datetime.timedelta(days=14)).strftime("%Y-%m-%d")
    intel_areas = sb_get("intel_areas", {"area_id": f"eq.{area_id}", "select": "intel_id"})
    intel_ids   = [r["intel_id"] for r in intel_areas[:20]]
    recent_intel = []
    for iid in intel_ids:
        rows = sb_get("intel", {
            "id":         f"eq.{iid}",
            "intel_date": f"gte.{fourteen_ago}",
            "select":     "headline,body,source_url",
        })
        recent_intel.extend(rows)

    if not landscape_text and not recent_intel:
        log("  No web results and no local intel — skipping discovery", indent=1)
        return 0

    intel_text = "\n\n".join(
        f"HEADLINE: {i['headline']}\nBODY: {(i.get('body') or '')[:300]}"
        for i in recent_intel[:10]
    ) if recent_intel else "(none)"

    existing_list = ", ".join(sorted(existing_ids)[:40])

    # Build landscape section safely (no nested f-string with special chars)
    landscape_section = ""
    if landscape_text:
        landscape_section = (
            "\nCURRENT LANDSCAPE (live web search — primary signal):\n"
            + landscape_text[:3000]
        )

    prompt = (
        f"Disease area: {area_id}  |  Today: {TODAY}\n"
        f"Already tracked IDs: {existing_list}\n"
        f"{landscape_section}\n"
        f"\nSUPPLEMENTAL INTEL (recent Supabase intel, last 14 days):\n{intel_text}\n\n"
        "Find NEW companies or drugs in this space NOT already tracked above.\n"
        "Include large pharma subsidiaries/programs if their compound is not yet tracked.\n"
        "Return only genuine competitive entries (not CROs, service providers, etc.).\n\n"
        '{"new_entities": [{'
        '"company_name": "...", "drug_name": "... or null", "target": "...",'
        '"stage": "Phase 1|Phase 2|Phase 3|Pre-IND|Preclinical",'
        '"modality": "mAb|bispecific|small molecule|ADC|nanobody|fusion protein|unknown",'
        '"route": "SC|IV|oral|unknown|null",'
        '"entity_type": "platform|partnership|standalone|licensed",'
        '"partner_co": "name of licensor/partner company or null",'
        '"overlap": "Direct|Adjacent|Same-Space|Watch",'
        '"confidence": 60-100,'
        '"reason": "one sentence"'
        "}]}\n\n"
        'IF none found: {"new_entities": []}'
    )

    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=1500,
            system=DISCOVERY_SYSTEM,
            messages=[{"role": "user", "content": prompt}]
        )
        text = resp.content[0].text.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:].strip()
        data = json.loads(text)
    except Exception as e:
        log(f"  Discovery error: {e}", indent=1)
        return 0

    new_entities = data.get("new_entities", [])
    if not new_entities:
        log("  No new entities found", indent=1)
        return 0

    created = 0
    for ent in new_entities:
        co_name    = ent.get("company_name", "")
        drug_name  = ent.get("drug_name")
        confidence = ent.get("confidence", 60)
        stage      = ent.get("stage", "Preclinical")
        target     = ent.get("target", "")

        log(f"  → {co_name}/{drug_name} (conf={confidence}): {ent.get('reason','')}", indent=1)
        if confidence < 70:
            log(f"    ↷ Low confidence — skip", indent=2)
            continue
        if dry_run:
            log(f"    [DRY RUN] Would create entity for {co_name}", indent=2)
            continue

        co_id = resolve_company_id(co_name, company_map)
        if not co_id:
            co_id = re.sub(r'[^a-z0-9]', '', co_name.lower())[:20]
            # group_id defaults to co_id for newly discovered standalone entities.
            # partner_co is set if the entity is a partnership (entity_type field from Claude).
            partner_co = ent.get("partner_co") or ent.get("partner") or None
            sb_upsert("companies", {
                "id":           co_id,
                "name":         co_name,
                "ticker":       "Private",
                "company_type": "small_cap",
                "group_id":     co_id,           # self-group by default
                "display_co":   co_name,          # can be overridden manually later
                "partner_co":   partner_co,       # populated if Claude finds a partner
                "overlap":      ent.get("overlap", "Watch"),  # default Watch until enriched
                "ailux_angle":  f"Newly discovered: {ent.get('reason','')}",
                "last_verified": TODAY,
            })
            company_map[co_name.lower()] = co_id
            log(f"    + Company: {co_id} (group_id={co_id}, partner={partner_co})", indent=2)

        existing_link = sb_get("company_areas", {
            "company_id": f"eq.{co_id}", "area_id": f"eq.{area_id}", "select": "company_id"
        })
        if not existing_link:
            sb_upsert("company_areas", {"company_id": co_id, "area_id": area_id})
            # Also tag to indication_group area (e.g. 'ibd' for 'tl1a').
            # Company eligibility for the TL1A tab is IBD-based, not TL1A-specific.
            if indication_group != area_id:
                sb_upsert("company_areas", {"company_id": co_id, "area_id": indication_group})

        if drug_name:
            drug_slug = re.sub(r'[^a-z0-9]', '-', drug_name.lower()).strip('-')
            existing_drug = sb_get("drugs", {"id": f"eq.{drug_slug}", "select": "id"})
            if not existing_drug:
                _stage_to_expected = {
                    "Preclinical": 1, "Pre-IND": 1, "IND-enabling": 1,
                    "Phase 1": 2, "Phase 2": 3, "Phase 3": 4, "Approved": 5,
                }
                sb_upsert("drugs", {
                    "id": drug_slug, "name": drug_name, "company_id": co_id,
                    "entity_id": co_id, "entity_name": co_name,
                    "entity_type": ent.get("entity_type", "standalone"),
                    "stage": stage, "target": target,
                    "mechanism": f"Anti-{target}" if target else None,
                    "modality": ent.get("modality") or None,
                    "drug_format": ent.get("modality") or None,
                    "route": ent.get("route") or None,
                    "cls": "Next Gen" if "×" in (target or "") else "1st Gen",
                    "overlap": "Direct",
                    "discovery_status": "auto",
                    "confidence_score": confidence,
                    "confidence_level": "inferred",
                    "data_source": "claude_inferred",
                    "expected_evidence_stage": _stage_to_expected.get(stage, 2),
                    "sort_order": 99,
                })
                sb_upsert("drug_areas", {"drug_id": drug_slug, "area_id": area_id})
                # Also tag to indication_group area (e.g. 'ibd') so drug shows in
                # expanded rows for any company in that broader indication bucket.
                if indication_group != area_id:
                    sb_upsert("drug_areas", {"drug_id": drug_slug, "area_id": indication_group})
                log(f"    + Drug: {drug_slug} (areas: {area_id}, {indication_group})", indent=2)

        created += 1

    return created


# ══════════════════════════════════════════════════════════════════════════
# CONTEXT FETCH — pulls all existing Supabase data for a company
# (Step 3 trials are pre-populated by ct_gov_sync.py)
# ══════════════════════════════════════════════════════════════════════════

def fetch_company_context(company_id: str, area_id: str) -> dict:
    """Pull all Supabase data for a company × area."""
    companies = sb_get("companies", {"id": f"eq.{company_id}", "select": "*"})
    company   = companies[0] if companies else {}

    profiles = sb_get("company_profiles", {
        "company_id": f"eq.{company_id}", "area_id": f"eq.{area_id}", "select": "*"
    })
    profile = profiles[0] if profiles else {}

    drug_area_rows = sb_get("drug_areas", {"area_id": f"eq.{area_id}", "select": "drug_id"})
    area_drug_ids  = {r["drug_id"] for r in drug_area_rows}
    all_co_drugs   = sb_get("drugs", {"company_id": f"eq.{company_id}", "select": "*"})
    drugs = [d for d in all_co_drugs if d["id"] in area_drug_ids]

    # Trials already populated by ct_gov_sync (Step 3)
    trials = []
    for d in drugs:
        t_rows = sb_get("trials", {"drug_id": f"eq.{d['id']}", "select": "*"})
        trials.extend(t_rows)

    ninety_ago = (datetime.datetime.utcnow() - datetime.timedelta(days=90)).strftime("%Y-%m-%d")
    intel_co   = sb_get("intel_companies", {"company_id": f"eq.{company_id}", "select": "intel_id"})
    recent_intel = []
    for row in intel_co[:10]:
        items = sb_get("intel", {
            "id": f"eq.{row['intel_id']}", "intel_date": f"gte.{ninety_ago}",
            "select": "intel_date,headline,body,source_url"
        })
        recent_intel.extend(items)

    catalysts = sb_get("catalysts", {
        "company_id": f"eq.{company_id}", "area_id": f"eq.{area_id}",
        "resolved": "eq.false", "select": "*", "order": "sort_date.asc"
    })

    deals = sb_get("deals", {
        "company_id": f"eq.{company_id}", "area_id": f"eq.{area_id}",
        "select": "*", "order": "deal_date.desc"
    })
    if not deals:
        co_name_prefix = (company.get("name") or "")[:12]
        if co_name_prefix:
            deals = sb_get("deals", {
                "area_id": f"eq.{area_id}",
                "or": f"(from_company.ilike.*{co_name_prefix}*,to_company.ilike.*{co_name_prefix}*)",
                "select": "*", "order": "deal_date.desc"
            })

    return {
        "company": company, "profile": profile, "drugs": drugs,
        "trials": trials, "catalysts": catalysts, "deals": deals,
        "recent_intel": recent_intel,
    }


# ══════════════════════════════════════════════════════════════════════════
# STEP 4 — CATALYST GENERATION
#
# IF trial has primary_completion_date in the future:
#   → Auto-create a readout catalyst record
#   → Significance = high (Ph3), medium (Ph2), low (Ph1)
# IF catalyst for this trial already exists:
#   → Skip (idempotent)
# ══════════════════════════════════════════════════════════════════════════

def _parse_sort_date(date_str: str) -> Optional[str]:
    """Parse various date formats → YYYY-MM-DD."""
    if not date_str:
        return None
    m = re.match(r"(\d{4}-\d{2}-\d{2})", date_str)
    if m:
        return m.group(1)
    months = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
              "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
    m = re.match(r"(\w{3})\s+(\d{4})", date_str, re.I)
    if m:
        mn = months.get(m.group(1).lower())
        if mn:
            return f"{m.group(2)}-{mn:02d}-01"
    q_map = {"q1":1,"q2":4,"q3":7,"q4":10,"h1":1,"h2":7}
    m = re.match(r"([qh][1-4])\s+(\d{4})", date_str, re.I)
    if m:
        mn = q_map.get(m.group(1).lower())
        if mn:
            return f"{m.group(2)}-{mn:02d}-01"
    m = re.match(r"^(\d{4})$", date_str.strip())
    if m:
        return f"{m.group(1)}-06-01"
    return None


def step4_generate_catalysts_from_trials(company_id: str, area_id: str,
                                          ctx: dict, dry_run: bool = False) -> int:
    """
    Auto-generate catalyst records from CT.gov trial primary completion dates.
    Returns count of new catalysts created.
    """
    created = 0
    for trial in ctx.get("trials", []):
        pcd_raw = (trial.get("primary_completion_date") or
                   trial.get("readout_date") or
                   trial.get("pcd_label") or "")
        if not pcd_raw:
            continue

        sort_date = _parse_sort_date(pcd_raw)
        if not sort_date or sort_date < TODAY:
            continue   # past — skip

        trial_id         = trial.get("id", "")
        trial_name       = trial.get("trial_name", trial_id)[:80]
        drug_id          = trial.get("drug_id", "")
        canonical_drug_id = trial.get("canonical_drug_id")   # propagated from ct_gov_sync
        phase            = trial.get("phase", "")
        pcd_label        = trial.get("pcd_label") or pcd_raw

        significance = ("high"   if "Phase 3" in phase else
                        "medium" if "Phase 2" in phase else "low")

        # Idempotency: dedup by drug × date, NOT by trial_id.
        # A drug may have multiple NCT IDs (cohorts, arms, sites) all sharing
        # the same primary_completion_date — those should collapse to ONE catalyst.
        if canonical_drug_id:
            dedup_q = {
                "company_id":        f"eq.{company_id}",
                "canonical_drug_id": f"eq.{canonical_drug_id}",
                "sort_date":         f"eq.{sort_date}",
                "select":            "id",
            }
        else:
            dedup_q = {
                "company_id": f"eq.{company_id}",
                "drug_id":    f"eq.{drug_id}",
                "sort_date":  f"eq.{sort_date}",
                "select":     "id",
            }
        if sb_get("catalysts", dedup_q):
            continue

        label   = f"{trial_name[:60]} — {phase} primary completion"
        cat_rec = {
            "catalyst_date":     pcd_label,
            "sort_date":         sort_date,
            "label":             label[:200],
            "company_id":        company_id,
            "drug_id":           drug_id,
            "area_id":           area_id,
            "significance":      significance,
            "catalyst_type":     "readout",
            "notes":             f"Auto-generated from ClinicalTrials.gov PCD: {trial_id}",
            "resolved":          False,
            "related_trial_id":  trial_id,
            "is_key_watch":      significance == "high",
            "confidence_source": "ctgov-pcd",
            "canonical_drug_id": canonical_drug_id,   # identity spine from trials table
        }

        if dry_run:
            log(f"    [DRY RUN] Catalyst: {label[:60]} ({pcd_label})", indent=3)
        else:
            result = sb_upsert("catalysts", cat_rec)
            if result:
                log(f"    + Catalyst [{significance}]: {label[:55]} ({pcd_label})", indent=3)
                created += 1

    return created


# ══════════════════════════════════════════════════════════════════════════
# STEP 5 — COMPANY ENRICHMENT (Claude Sonnet + web_search)
#
# Phase A: Web intelligence gathering — live search for clinical data, financing,
#           deals, catalyst timing (web_search_20250305 tool).
# Phase B: Claude synthesis — structured enrichment using Supabase context +
#           web intelligence → company_profiles, drugs, catalysts, deals.
# ══════════════════════════════════════════════════════════════════════════

AREA_LABELS_MAP = {
    "tl1a": "TL1A (anti-TL1A antibodies, IBD)",
    "tslp": "TSLP (anti-TSLP antibodies, asthma/atopic disease)",
    "il4ra": "IL-4Rα (anti-IL-4Rα, atopic dermatitis/asthma)",
    "igf1r": "IGF1R (anti-IGF1R, oncology)",
    "fcrn": "FcRn (anti-FcRn, autoimmune/IgG-mediated disease)",
    "tcell": "T-cell engagers (oncology)",
}

WEB_SEARCH_SYSTEM = """You are a biopharma competitive intelligence researcher.
Use web_search to gather current, specific facts about the target company.
Extract actual numbers, dates, partner names, dollar amounts — not general descriptions.
Prioritize press releases, SEC filings, ClinicalTrials.gov, conference abstracts, and IR pages.
Summarize findings in dense factual paragraphs. Do not fabricate — if you can't find something, say so."""


def gather_web_intelligence(company_name: str, area_id: str,
                             drugs: list, ticker: str = "") -> str:
    """
    Phase A of Step 5: use Claude with web_search to gather live intelligence.

    Runs 4 targeted searches:
      1. Clinical data — trial results, efficacy endpoints, conference readouts
      2. Financing — funding rounds, investors, cash runway, IPO/SPAC details
      3. BD activity — partnerships, licensing deals, M&A, collaborations
      4. Catalyst timeline — company-guided data windows, PDUFA dates, filings

    Returns a structured text block to inject into the Phase B enrichment prompt.
    Falls back to empty string on any failure (Phase B continues with Supabase context only).
    """
    area_label = AREA_LABELS_MAP.get(area_id, area_id)
    drug_names = ", ".join(d.get("name", "") for d in drugs[:4] if d.get("name"))
    ticker_str = f" (Ticker: {ticker})" if ticker and ticker.upper() not in ("PRIVATE", "N/A", "") else ""
    year = datetime.datetime.utcnow().year

    prompt = f"""Research {company_name}{ticker_str} for a competitive intelligence database.
Area of focus: {area_label}
Key programs to research: {drug_names or 'see company pipeline'}

Use web_search to find and extract SPECIFIC facts on all four topics:

TOPIC 1 — CLINICAL DATA
Search for the most recent trial results, efficacy endpoints, safety data, and conference presentations.
What endpoints did they hit? What were the response rates, p-values, or biomarker results?
Which conferences (ECCO, DDW, ACR, ASCO, NEJM, Lancet, NEJM Evidence)?
Any Phase 3 readouts, POC data, dose-selection results in the last 24 months?

TOPIC 2 — FINANCING & COMPANY STATUS
All funding rounds with amounts, dates, and lead investors.
IPO, SPAC, or public listing details if applicable.
Current cash position or runway guidance if disclosed.
Key shareholders or strategic investors.

TOPIC 3 — BD ACTIVITY
Any licensing deals, partnerships, co-development agreements, M&A.
Deal terms where disclosed: upfront, milestones, royalties, geography.
Any stated partnering strategy or BD timeline guidance from management.

TOPIC 4 — CATALYST TIMELINE
Company-guided data readout windows for each program.
Any upcoming PDUFA dates, regulatory filings, or NDA/BLA submissions.
Expected enrollment completion or primary completion dates from company guidance (not just CT.gov).

Search year range: {year - 1}–{year}.
Be specific. Extract actual numbers and dates. Indicate uncertainty where present."""

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3000,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
            system=WEB_SEARCH_SYSTEM,
            messages=[{"role": "user", "content": prompt}]
        )
        # Extract all text content blocks (tool_use and tool_result blocks are intermediate)
        parts = []
        for block in resp.content:
            if hasattr(block, "text") and block.text:
                parts.append(block.text.strip())
        result = "\n\n".join(parts)
        tokens_in  = resp.usage.input_tokens
        tokens_out = resp.usage.output_tokens
        cost = (tokens_in / 1e6 * 3.0) + (tokens_out / 1e6 * 15.0)
        log(f"  Web search: {tokens_in}in / {tokens_out}out (${cost:.4f})", indent=2)
        return result if result else ""
    except Exception as e:
        log(f"  Web search failed (non-fatal): {e}", indent=2)
        return ""


ENRICHMENT_SYSTEM = """You are a senior biopharma business development analyst for Ailux Biotherapeutics,
a biotech developing a TL1A×IL-23p19 bispecific antibody for IBD. You synthesize clinical, competitive,
and BD intelligence into structured data that powers a live competitive tracking dashboard.

KEY CONTEXT: Ailux's lead asset is a TL1A×IL-23p19 bispecific for UC/CD.
Primary BD goal: identify the right pharma partner — timing, deal structure, positioning.

OUTPUT RULES:
- Narrative text fields: 2-4 concise, dense sentences. No bullets. No markdown.
- BD Summary: financing, deal history, partnering strategy, cash runway, BD timing windows.
- Key Risk: the SINGLE most important risk specific to THIS company's program.
- vs_ailux: how this company/drug compares to Ailux — mechanism, stage, format, differentiation.
- Do not fabricate. If uncertain, use "expected", "anticipated", "estimated".
- Return ONLY valid JSON — no markdown fences, no explanation.

DATA QUALITY STANDARDS (mandatory — these prevent downstream display errors):

TARGET NOTATION:
- IL-23 inhibitors: ALWAYS specify "IL-23p19" (not "IL-23" alone). The p19 subunit is the
  specific target of all modern IL-23 inhibitors. IL-23p40 inhibitors are a different class.
- Bispecifics use "×" separator: "TL1A × IL-23p19" (NOT "TL1A/IL-23" or "anti-TL1A × IL-23")
- Rational combinations (two separate co-administered mAbs) use "+" separator: "IL-23p19 + TL1A"
- Monospecific mAbs: do NOT prefix with "Anti-" in the target field (use in mechanism field only)

DRUG NAME FORMAT:
- If a drug has an approved brand name (e.g., Skyrizi, Rinvoq, Entyvio):
  → name field = "BrandName (INN)" e.g. "Skyrizi (Risankizumab)"
  → The pill will show "BrandName" — do NOT use the numbered code (e.g. NOT "BI 765063")
- If a drug has INN but no brand name: name field = "INN (NumberCode)" if code is meaningful,
  otherwise just "INN" (e.g. "Afimkibart" not "Afimkibart (RO7790121)")
- If only a code name exists (no INN yet): use code name (e.g. "XmAb942", "SPY002")

PCD / DATE GRANULARITY:
- Primary completion dates must include the SPECIFIC DAY when known: "April 28, 2028" NOT "Apr 2028"
- For catalyst dates where only month/quarter is known, use "Q3 2026" or "H2 2026" — never just a year
- Always pull PCD from the actual CT.gov filing (primary_completion_date) — include the day

VALIDATED REFERENCES:
- Every catalyst must include a source_url (CT.gov NCT link, press release, SEC filing, or company IR)
- Every deal must include a source_url — at minimum the company press release or SEC 8-K
- Every news item / recent development should reference its source
- Do not fabricate URLs. If you cannot find a verified URL, omit the field rather than guess.

CHINA CDE AWARENESS:
- Many China-based programs are registered on China's Clinical Trial Registry (www.chinadrugtrials.org.cn)
  but NOT on CT.gov. When researching Chinese biotech or programs with China CDE registry entries,
  note this explicitly in mechanism_detail (e.g., "Phase 1 registered on China CDE registry; NCT pending")."""


def build_step5_prompt(company_id: str, area_id: str, ctx: dict,
                       web_intel: str = "") -> str:
    co      = ctx["company"]
    profile = ctx["profile"]
    is_public = (co.get("ticker") or "").upper() not in ("PRIVATE", "", "N/A")

    drugs_text = json.dumps([{
        k: v for k, v in d.items()
        if k in ("id","name","mechanism","mechanism_detail","drug_summary","stage","stage_detail",
                 "key_data","route","dosing_type","drug_format","half_life_note","indication_short",
                 "target","cls","overlap","entity_type","aliases")
    } for d in ctx["drugs"]], indent=2)

    trials_text = json.dumps([{
        k: v for k, v in t.items()
        if k in ("id","trial_name","phase","status","indication","n_enrollment",
                 "primary_endpoint","pcd_label","primary_completion_date","sponsor")
    } for t in ctx["trials"][:12]], indent=2)

    existing_cats = json.dumps([{
        "date": c.get("catalyst_date"), "label": c.get("label"),
        "significance": c.get("significance"),
    } for c in ctx["catalysts"]], indent=2)

    existing_deals = json.dumps([{
        "date": d.get("deal_date_label"), "headline": d.get("headline"),
        "from": d.get("from_company"), "to": d.get("to_company"),
        "upfront": d.get("upfront_usd_m"), "total": d.get("total_usd_m"),
    } for d in ctx["deals"][:8]], indent=2)

    recent_intel = json.dumps([{
        "date": i.get("intel_date"),
        "headline": i.get("headline"),
        "body": (i.get("body") or "")[:300],
    } for i in ctx["recent_intel"][:6]], indent=2)

    current_profile = json.dumps({
        "platform_summary": profile.get("platform_summary", ""),
        "bd_summary":       profile.get("bd_summary", ""),
        "key_risk":         profile.get("key_risk", ""),
        "why_it_matters":   profile.get("why_it_matters", ""),
        "vs_ailux":         profile.get("vs_ailux", ""),
    }, indent=2)

    financial_fields = (
        '"market_cap_usd_m": null or number,'
        if is_public else
        '"cash_runway": "e.g. H2 2028 or null",'
        '"financing_history": [{"date": "YYYY-MM", "amount_usd_m": X, "series": "Series A", "investors": ["name"]}],'
        '"key_investors": ["name1", "name2"],'
    )

    # Build web intelligence section separately to avoid f-string nesting issues
    if web_intel:
        web_intel_section = (
            "\nWEB INTELLIGENCE (live research - highest priority source):\n"
            + web_intel
            + "\n\nINSTRUCTION: Use WEB INTELLIGENCE as your primary source for clinical endpoints, "
            "financing amounts, deal terms, and catalyst timing. It contains current data retrieved "
            "directly from press releases, SEC filings, and company IR pages. Cross-reference with "
            "TRIALS/DEALS above; prefer web data where it is more specific or more recent.\n"
        )
    else:
        web_intel_section = ""

    return f"""Enrich company: {co.get('name', company_id)} (ID: {company_id})
Area: {area_id}  |  Public: {is_public}  |  Today: {TODAY}

CURRENT PROFILE:
{current_profile}

DRUGS:
{drugs_text}

TRIALS (from ClinicalTrials.gov — Step 3):
{trials_text}

EXISTING CATALYSTS:
{existing_cats}

EXISTING DEALS:
{existing_deals}

RECENT INTEL:
{recent_intel}
{web_intel_section}
Return JSON with EXACTLY these fields:
{{
  "company_profile": {{
    "platform_summary": "2-4 sentences: current clinical status, key data, program scope.",
    "bd_summary": "2-4 sentences: financing, deal history, partnering strategy, timing window.",
    "key_risk": "1-2 sentences: single most important risk.",
    "why_it_matters": "1-2 sentences: why this competitor matters for Ailux's BD strategy.",
    "vs_ailux": "1-2 sentences: how this program compares to Ailux's TL1A×IL-23p19 bispecific.",
    "strategic_behavior": "1 sentence: acquirer / licensor / partner-seeker / platform builder.",
    "pipeline_url": "URL or null",
    {financial_fields}
  }},
  "drug_updates": [{{
    "drug_id": "exact drug id from DRUGS list",
    "modality": "anti-TL1A mAb|TL1A×IL-23p19 bispecific|JAK1 inhibitor (oral small molecule)|anti-α4β7 integrin mAb|etc — full descriptive label",
    "drug_format": "mAb|bispecific|small molecule|ADC|nanobody|fusion protein",
    "route": "SC|IV|SC/IV|oral|null",
    "dosing_type": "Induction|Maintenance|Induction + Maintenance|null",
    "is_combo": false,
    "dosing_schedule": "null or e.g. Q3M SC",
    "indication_short": "null or e.g. UC · CD",
    "stage_detail": "null or e.g. Phase 2b (ARTEMIS-CD)",
    "phase_display": "null or e.g. Phase 3",
    "half_life_note": "null or e.g. ~74 days",
    "mechanism_detail": "null or 1-2 sentences: specific mechanism, format, any structural notes (platform tech, half-life, engineering)",
    "drug_summary": "null or 2-3 sentences: the most important facts about THIS molecule — what makes it noteworthy (platform tech, clinical differentiation, half-life, conference presentations, Phase readout highlights). This is displayed as the first thing a user reads about the drug.",
    "key_data": "null or most important recent clinical data point in one sentence",
    "vs_ailux": "null or 1 sentence comparison to Ailux's TL1A×IL-23p19 bispecific — mechanism, stage, differentiation",
    "confidence_level": "confirmed|supported|inferred",
    "data_source": "ct_gov|sec_filing|press_release|conference|claude_inferred",
    "aliases": []
  }}],
  "catalysts": [{{
    "catalyst_date": "Include specific day when known: 'April 28, 2028'. Use 'Q3 2026' or 'H2 2026' when only quarter/half known. Never just a year.",
    "sort_date_approx": "YYYY-MM-DD best estimate",
    "label": "concise event label ≤120 chars",
    "catalyst_type": "readout|filing|approval|conference|deal|partnership",
    "significance": "high|medium|low",
    "is_key_watch": true or false,
    "confidence_level": "confirmed (company filing/PDUFA)|supported (multiple sources)|inferred (derived from trial dates or guidance)",
    "source_url": "REQUIRED — CT.gov NCT link, press release URL, SEC filing, or company IR page. Omit field if no verified URL found (never fabricate).",
    "notes": "1 sentence context — include evidence source (e.g. 'Company-guided Q3 2026 per ECCO 2025 presentation')"
  }}],
  "deal_updates": [{{
    "headline": "match to existing deal headline",
    "geography_rights": "null or e.g. Global ex-China",
    "economics_royalties": "null or e.g. tiered royalties 8-15%",
    "strategic_signal": "1 sentence: what this deal signals",
    "ailux_relevance": "1 sentence: how this affects Ailux's BD strategy",
    "source_url": "REQUIRED — press release URL, SEC 8-K, or company IR page. Omit if not verified (never fabricate)."
  }}]
}}

RULES:
- drug_updates: only drugs from DRUGS list (exact drug_id)
- catalysts: only upcoming events (after {TODAY})
- deal_updates: only match to EXISTING DEALS
- Return ONLY valid JSON. No markdown.
- ALWAYS apply DATA QUALITY STANDARDS from the system prompt: IL-23p19 notation, brand name format, PCD specificity, validated URLs."""


def parse_enrichment_response(text: str) -> Optional[dict]:
    text = text.strip()
    if "```" in text:
        for p in text.split("```"):
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{"):
                text = p
                break
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        log(f"  JSON parse error: {e} | Raw: {text[:400]}", indent=1)
        return None


def write_step5(company_id: str, area_id: str, data: dict, dry_run: bool = False):
    """Write Claude enrichment results to Supabase."""
    if dry_run:
        log(f"  [DRY RUN] {json.dumps(data, indent=2)[:400]}...", indent=1)
        return

    cp = data.get("company_profile", {})
    if cp:
        profile_rec = {
            "company_id":       company_id,
            "area_id":          area_id,
            "last_enriched_at": NOW_ISO,
            "enriched_by":      "claude-intelligence-v2",
        }
        for field in ["platform_summary","bd_summary","key_risk","why_it_matters",
                      "vs_ailux","strategic_behavior","pipeline_url",
                      "market_cap_usd_m","cash_runway","financing_history","key_investors"]:
            if cp.get(field) is not None:
                profile_rec[field] = cp[field]
        result = sb_upsert("company_profiles", profile_rec)
        log(f"  company_profiles: {'✓' if result else '✗'}", indent=1)

    for du in data.get("drug_updates", []):
        drug_id = du.pop("drug_id", None)
        if not drug_id:
            continue
        update_fields = {k: v for k, v in du.items() if v is not None}
        if update_fields:
            ok = sb_patch("drugs", update_fields, {"id": f"eq.{drug_id}"})
            log(f"  drug {drug_id}: {'✓' if ok else '✗'}", indent=1)

    for cat in data.get("catalysts", []):
        sort_date = _parse_sort_date(
            cat.get("sort_date_approx") or cat.get("catalyst_date") or TODAY
        ) or TODAY
        if sort_date < TODAY:
            continue
        cat_rec = {
            "catalyst_date":    cat.get("catalyst_date", ""),
            "sort_date":        sort_date,
            "label":            (cat.get("label") or "")[:200],
            "company_id":       company_id,
            "area_id":          area_id,
            "significance":     cat.get("significance", "medium"),
            "catalyst_type":    cat.get("catalyst_type", "readout"),
            "notes":            cat.get("notes", ""),
            "is_key_watch":     bool(cat.get("is_key_watch", False)),
            "confidence_level": cat.get("confidence_level", "inferred"),
            "resolved":         False,
            "confidence_source": "company-disclosed",
        }
        # RULE: Always persist source_url when provided — required for validated references
        if cat.get("source_url"):
            cat_rec["source_url"] = cat["source_url"]
        result = sb_upsert("catalysts", cat_rec)
        log(f"  catalyst '{cat_rec['label'][:40]}': {'✓' if result else '✗'}", indent=1)

    for du in data.get("deal_updates", []):
        headline = du.get("headline", "")
        if not headline:
            continue
        # RULE: source_url is a validated reference field — always persist if provided
        update_fields = {k: v for k, v in du.items()
                        if k != "headline" and v is not None}
        if update_fields:
            ok = sb_patch("deals", update_fields,
                          {"headline": f"ilike.*{headline[:30]}*",
                           "company_id": f"eq.{company_id}"})
            log(f"  deal '{headline[:40]}': {'✓' if ok else '✗'}", indent=1)


# ══════════════════════════════════════════════════════════════════════════
# STEP 6 — DEAL INTELLIGENCE
#
# IF recent intel contains deal announcement not yet in deals table:
#   → Create deal record
#   → Connect to entity, company
# ══════════════════════════════════════════════════════════════════════════

def _deal_signature(headline: str) -> str:
    """Normalised fingerprint for deal deduplication.

    Strips all non-alphanumeric characters, lowercases, and returns the first
    100 characters.  Using 100 normalised chars (vs the old raw[:50]) removes
    punctuation/spacing variance that caused false positives and catches more
    near-duplicate headlines.
    """
    return re.sub(r"[^a-z0-9]", "", headline.lower())[:100]


def step6_deal_intelligence(company_id: str, area_id: str, ctx: dict,
                             company_map: dict, dry_run: bool = False,
                             resolver=None) -> int:
    """Log new deals found in recent intel. Returns count created.

    Args:
      resolver: a pre-instantiated DrugIdentityResolver (passed from run_intelligence_pipeline).
                Pass None to skip canonical identity stamping on deals.
    """
    existing_signatures = {
        _deal_signature(d.get("headline") or "")
        for d in ctx.get("deals", [])
    }
    new_deals = 0
    deal_kws   = {"license","acqui","partner","collaborat","deal","invest",
                  "$","million","billion","agreement","merger"}

    # Build a quick lookup: drug name → canonical_drug_id for this company's drugs.
    # Resolver pre-instantiated by caller — no per-company Supabase round-trip here.
    drug_canonical_map: dict[str, str] = {}
    if resolver is not None and not dry_run:
        for drug in ctx.get("drugs", []):
            drug_name = drug.get("name") or drug.get("id", "")
            if drug_name:
                try:
                    canon_id, _, _ = resolver.resolve(
                        drug_name, source="company_enrichment",
                        drug_class=drug.get("drug_class"),
                        mechanism=drug.get("mechanism"),
                        target=drug.get("target"),
                    )
                    drug_canonical_map[drug_name.lower()] = canon_id
                except Exception as inner_exc:
                    try:
                        resolver.log_resolver_error(
                            drug_name=drug_name, source="company_enrichment",
                            error=inner_exc, source_table="drugs",
                            source_row_id=drug.get("id"),
                        )
                    except Exception:
                        pass

    for item in ctx.get("recent_intel", []):
        headline = (item.get("headline") or "").lower()
        if not any(kw in headline for kw in deal_kws):
            continue
        if _deal_signature(headline) in existing_signatures:
            continue

        deal_date = item.get("intel_date") or TODAY
        try:
            deal_date_label = datetime.datetime.strptime(deal_date[:7], "%Y-%m").strftime("%b %Y")
        except Exception:
            deal_date_label = deal_date[:7]

        # Attempt to identify which drug this deal is about (if any)
        headline_lc = (item.get("headline") or "").lower()
        deal_canonical_drug_id = None
        for drug_name_lc, canon_id in drug_canonical_map.items():
            if drug_name_lc in headline_lc:
                deal_canonical_drug_id = canon_id
                break

        deal_rec = {
            "deal_date":         deal_date,
            "deal_date_label":   deal_date_label,
            "from_company":      ctx["company"].get("name", company_id),
            "to_company":        "",
            "company_id":        company_id,
            "area_id":           area_id,
            "deal_type":         "license",
            "headline":          (item.get("headline") or "")[:200],
            "detail":            (item.get("body") or "")[:1000],
            "source_url":        item.get("source_url", ""),
            "ailux_signal":      "",
            "canonical_drug_id": deal_canonical_drug_id,
        }
        if dry_run:
            log(f"  [DRY RUN] Deal: {deal_rec['headline'][:60]}", indent=2)
        else:
            result = sb_post("deals", deal_rec)
            if result:
                log(f"  + Deal: {deal_rec['headline'][:60]}", indent=2)
                new_deals += 1

    return new_deals


# ══════════════════════════════════════════════════════════════════════════
# PER-COMPANY ORCHESTRATION — Steps 4, 5, 6
# ══════════════════════════════════════════════════════════════════════════

def enrich_company(company_id: str, area_id: str, company_map: dict,
                   dry_run: bool = False, resolver=None) -> bool:
    """Run Steps 4-6 for one company.

    Args:
      resolver: a pre-instantiated DrugIdentityResolver (passed from run_intelligence_pipeline).
    """
    log(f"\n{'='*56}")
    log(f"Enriching: {company_id} / {area_id}")
    log(f"{'='*56}")

    log("Fetching Supabase context...", indent=1)
    ctx = fetch_company_context(company_id, area_id)
    log(f"  {len(ctx['drugs'])} drugs | {len(ctx['trials'])} trials | "
        f"{len(ctx['catalysts'])} catalysts | {len(ctx['deals'])} deals | "
        f"{len(ctx['recent_intel'])} intel items", indent=1)

    # STEP 4: Auto-catalysts from trial dates
    log("STEP 4 — Catalyst auto-generation...", indent=1)
    cats = step4_generate_catalysts_from_trials(company_id, area_id, ctx, dry_run)
    log(f"  {cats} new catalysts", indent=1)

    # STEP 5: Claude narrative enrichment
    log("STEP 5 — Claude enrichment...", indent=1)

    # Phase A: Web intelligence gathering (live search, non-fatal)
    co = ctx["company"]
    log("  Phase A — Web intelligence search...", indent=1)
    web_intel = gather_web_intelligence(
        company_name=co.get("name", company_id),
        area_id=area_id,
        drugs=ctx["drugs"],
        ticker=co.get("ticker", ""),
    )
    if web_intel:
        log(f"  Web intelligence gathered ({len(web_intel)} chars)", indent=1)
    else:
        log("  No web intelligence (continuing with Supabase context only)", indent=1)

    # Phase B: Claude synthesis with web context injected
    log("  Phase B — Claude synthesis...", indent=1)
    prompt = build_step5_prompt(company_id, area_id, ctx, web_intel=web_intel)

    text = None
    for attempt in range(1, 4):
        try:
            resp = client.messages.create(
                model="claude-sonnet-4-6", max_tokens=4096,
                system=ENRICHMENT_SYSTEM,
                messages=[{"role": "user", "content": prompt}]
            )
            text = resp.content[0].text
            cost = (resp.usage.input_tokens / 1e6 * 3.0 +
                    resp.usage.output_tokens / 1e6 * 15.0)
            log(f"  {resp.usage.input_tokens}in / {resp.usage.output_tokens}out (${cost:.4f})", indent=1)
            break
        except Exception as e:
            log(f"  Claude error (attempt {attempt}/3): {e}", indent=1)
            if attempt < 3:
                time.sleep(10 * attempt)

    if text is None:
        log("  Claude failed — skipping", indent=1)
        return False

    data = parse_enrichment_response(text)
    if not data:
        log("  Parse failed — skipping", indent=1)
        return False

    write_step5(company_id, area_id, data, dry_run)

    # STEP 6: Deal intelligence
    log("STEP 6 — Deal intelligence...", indent=1)
    deals = step6_deal_intelligence(company_id, area_id, ctx, company_map, dry_run,
                                    resolver=resolver)
    log(f"  {deals} new deals", indent=1)

    return True


# ══════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE ORCHESTRATION — all 7 steps for one area
# ══════════════════════════════════════════════════════════════════════════

def run_intelligence_pipeline(area_id: str,
                               company_filter: Optional[str] = None,
                               discover_only: bool = False,
                               dry_run: bool = False):
    """
    Runs the full intelligence pipeline for one disease area.

    Note: Step 3 (Trial Sync) is handled by ct_gov_sync.py
    and must run BEFORE this script in the GitHub Actions workflow.
    """
    log(f"\n{'#'*60}")
    log(f"# Ailux Intelligence Pipeline — v2")
    log(f"# Area: {area_id}  |  Date: {TODAY}")
    log(f"# Model: claude-sonnet-4-6  |  Dry run: {dry_run}")
    log(f"{'#'*60}")

    company_map = get_company_map()
    log(f"Loaded {len(company_map)} company name→ID mappings")

    # Instantiate identity resolver once per pipeline run.
    # A single instance loads the alias cache once (one Supabase round-trip),
    # then every enrich_company → step6 call reuses it.
    run_resolver = None
    if _IDENTITY_RESOLVER_AVAILABLE and not dry_run:
        try:
            run_resolver = DrugIdentityResolver(SUPABASE_URL, SUPABASE_KEY)
            run_resolver._load_alias_cache()  # pre-load once; per-company calls reuse this
            log(f"Identity resolver ready ({len(run_resolver._alias_cache)} cached aliases)")
        except Exception as exc:
            log(f"⚠ Could not initialise identity resolver: {exc} — running without it")

    # STEP 1: Entity Discovery
    new_entities = step1_discover_new_entities(area_id, company_map, dry_run=dry_run)
    log(f"Step 1 complete: {new_entities} new entities")

    if discover_only:
        log("--discover-only: stopping after Step 1")
        return

    # STEPS 4-6: Per-company enrichment
    company_areas = sb_get("company_areas", {"area_id": f"eq.{area_id}", "select": "company_id"})
    company_ids   = [r["company_id"] for r in company_areas]

    if company_filter:
        company_ids = [c for c in company_ids if company_filter.lower() in c.lower()]
        log(f"Filtered to {len(company_ids)} matching '{company_filter}'")

    if not company_ids:
        log(f"No companies for area '{area_id}'")
        return

    log(f"\n{len(company_ids)} companies to enrich: {company_ids}")
    log("Note: Trials pre-populated by ct_gov_sync.py (Step 3)")

    results = {"success": 0, "failed": 0}
    for cid in company_ids:
        try:
            ok = enrich_company(cid, area_id, company_map, dry_run=dry_run,
                                resolver=run_resolver)
            results["success" if ok else "failed"] += 1
        except Exception as e:
            log(f"FATAL: {cid}: {e}")
            results["failed"] += 1
        time.sleep(2)

    log(f"\n{'='*60}")
    log(f"Complete: {results['success']} success, {results['failed']} failed")
    log(f"{'='*60}")


# ══════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ailux BD Platform — Systematic Intelligence Pipeline"
    )
    parser.add_argument("--area",     required=True,
                        help="Disease area ID (e.g. tl1a, tslp, il4ra)")
    parser.add_argument("--company",  default=None,
                        help="Company ID substring filter")
    parser.add_argument("--discover-only", action="store_true",
                        help="Only run Step 1 (entity discovery)")
    parser.add_argument("--dry-run",  action="store_true",
                        help="No Supabase writes")
    args = parser.parse_args()

    run_intelligence_pipeline(
        area_id=args.area,
        company_filter=args.company,
        discover_only=args.discover_only,
        dry_run=args.dry_run,
    )
