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
  ct_gov_sync.py is optional — enrichment now auto-syncs missing trials from CT.gov
  before calling Claude, so it is self-contained for drugs with zero trial rows.

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


def sb_upsert(table: str, records: list | dict,
              on_conflict: str | None = None) -> list:
    if isinstance(records, dict):
        records = [records]
    if not records:
        return []
    try:
        url = f"{SUPABASE_URL}/rest/v1/{table}"
        if on_conflict:
            url += f"?on_conflict={on_conflict}"
        r = requests.post(url, headers=SB_UPSERT_HEADERS, json=records, timeout=15)
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


def sb_delete(table: str, match_params: dict) -> int:
    """DELETE rows matching match_params. Returns count of deleted rows."""
    try:
        headers = {**SB_HEADERS, "Prefer": "return=representation"}
        r = requests.delete(f"{SUPABASE_URL}/rest/v1/{table}",
                            headers=headers, params=match_params, timeout=15)
        if r.status_code in (200, 204):
            deleted = r.json() if r.text and r.text.strip() not in ("", "[]") else []
            return len(deleted) if isinstance(deleted, list) else 0
        else:
            log(f"[sb_delete {table}] HTTP {r.status_code}: {r.text[:200]}", indent=2)
            return 0
    except Exception as e:
        log(f"[sb_delete {table}] {e}", indent=1)
        return 0


def sb_patch(table: str, record: dict, match_params: dict) -> bool:
    try:
        r = requests.patch(f"{SUPABASE_URL}/rest/v1/{table}",
                           headers=SB_HEADERS, params=match_params,
                           json=record, timeout=15)
        if r.status_code in (200, 204):
            # With return=representation, 200 + empty body means 0 rows matched
            if r.status_code == 200 and r.text and r.text.strip() in ("[]", ""):
                log(f"[sb_patch {table}] WARNING: 0 rows matched {match_params}", indent=2)
                return False
            return True
        else:
            log(f"[sb_patch {table}] HTTP {r.status_code}: {r.text[:300]}", indent=2)
            return False
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
    """Fetch all companies from Supabase → dict: name/alias/ticker/group_id → id.

    Including ticker and group_id means that if enrichment discovers a variant
    name like 'Spyre Therapeutics (TL1A mono)', it can still resolve to the
    canonical 'spyre' company_id via ticker or group_id match — preventing
    ghost sub-entity creation.
    """
    try:
        rows = sb_get("companies", {"select": "id,name,ticker,group_id"})
        cmap = {}
        for row in rows:
            cmap[row["id"].lower()] = row["id"]
            cmap[row["name"].lower()] = row["id"]
            if row.get("group_id"):
                cmap[row["group_id"].lower()] = row["id"]
            # Ticker-based lookup (skip generic placeholders)
            ticker = (row.get("ticker") or "").strip()
            if ticker and ticker.upper() not in ("PRIVATE", ""):
                cmap[ticker.lower()] = row["id"]
        cmap.update(COMPANY_ALIASES)
        return cmap
    except Exception as e:
        log(f"Company map fetch error: {e}")
        return {}


def resolve_company_id(name: str, company_map: dict) -> Optional[str]:
    """Resolve a company name to its canonical company_id.

    Resolution order:
    1. Exact lowercase match
    2. Strip parenthetical qualifier (e.g. 'Spyre (TL1A mono)' → 'Spyre') then exact match
    3. Substring match (either direction)

    The parenthetical strip prevents enrichment from creating ghost sub-entities
    when Claude qualifies a known company with a program descriptor.
    """
    lc = (name or "").strip().lower()
    if not lc:
        return None
    # 1. Exact match
    if lc in company_map:
        return company_map[lc]
    # 2. Strip trailing parenthetical qualifier, try again
    base = re.sub(r'\s*\([^)]*\)\s*$', '', lc).strip()
    if base and base != lc and base in company_map:
        return company_map[base]
    # 3. Substring match (both directions)
    for key, cid in company_map.items():
        if len(lc) >= 4 and (lc in key or key in lc):
            return cid
    # 4. Base-name substring match
    if base and base != lc:
        for key, cid in company_map.items():
            if len(base) >= 4 and (base in key or key in base):
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
                                  dry_run: bool = False, resolver=None) -> int:
    """
    Proactively discover new competitors via live web search, then diff against
    the existing Supabase entity list. Supplemented by recent in-DB intel.

    IMPORTANT: Discovered entities are NO LONGER auto-inserted into production tables.
    Instead they are written to discovery_queue (status='pending') for manual review.
    Only after human approval are they promoted to companies/drugs/company_areas.

    Relevance scoring (1-10):
      9-10 → Critical (Direct Mechanism or major Clinical Competition) → priority review
      7-8  → Important (Layer 2/3, late-stage) → standard review
      5-6  → Watch (early stage, emerging mechanism)
      <5   → Low relevance → auto-archived, no queue notification

    Returns count of items written to discovery_queue.
    """
    # Run ID ties every row in this batch to a specific discovery run — critical for debugging
    run_id = f"{area_id}_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M')}"

    log(f"\n{'─'*50}")
    log(f"STEP 1 — Entity Discovery (area: {area_id}, run_id: {run_id})")
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
        "SCOPE — THINK INDICATION-FIRST, NOT JUST MECHANISM:\n"
        "Do not limit discovery to exact-mechanism matches. Include companies that compete\n"
        "for the SAME PATIENTS in the SAME INDICATION even if their mechanism differs.\n"
        "Examples: for IBD/TL1A, include IL-23 inhibitors, IL-23+TNF combo programs, JAKs\n"
        "with active UC/CD trials. For atopic disease, include OX40L, IL-31, IL-13 programs.\n"
        "A company running a Phase 3 combo study in UC belongs in the IBD competitive map\n"
        "even if their drug doesn't target TL1A directly. Assign overlap='Adjacent' for these.\n\n"
        "CRITICAL ACQUISITION RULE: If a company was wholly acquired and its drug now belongs to\n"
        "the acquirer (e.g., Prometheus Biosciences was acquired by Merck — tulisokibart is now\n"
        "Merck's program), DO NOT list the acquired company as a new_entity. The drug lives under\n"
        "the acquirer. If the acquirer is NOT yet tracked, list the acquirer as the entity.\n"
        "Only set acquired_by if you are adding the company AND know it was acquired — this\n"
        "is rare (most of the time just skip the acquired company entirely).\n\n"
        "COMPETITION LAYERS:\n"
        "  layer 1 = Direct Mechanism (same target/class as the lead asset)\n"
        "  layer 2 = Direct Clinical Competition (same indication/patient population, different mechanism)\n"
        "  layer 3 = Strategic Threat (adjacent indication, platform breadth, or deal activity)\n\n"
        "RELEVANCE SCORING (1-10):\n"
        "  9-10 = Critical competitor (Direct Mechanism or major late-stage Clinical Competition)\n"
        "  7-8  = Important (Layer 2/3 with Phase 2+ data in same patient population)\n"
        "  5-6  = Watch (early stage, emerging mechanism, or adjacent indication)\n"
        "  1-4  = Low relevance (very early, different patient population)\n\n"
        '{"new_entities": [{'
        '"company_name": "...", "drug_name": "... or null", "target": "...",'
        '"stage": "Phase 1|Phase 2|Phase 3|Pre-IND|Preclinical",'
        '"modality": "mAb|bispecific|small molecule|ADC|nanobody|fusion protein|unknown",'
        '"route": "SC|IV|oral|unknown|null",'
        '"entity_type": "company|molecule|trial|deal|catalyst|article|evidence_item",'
        '"partner_co": "name of licensor/partner company or null",'
        '"acquired_by": "company_id of the acquirer if this entity was wholly acquired and no longer independent, else null",'
        '"overlap": "Direct|Adjacent|Same-Space|Watch",'
        '"competition_layer": 1|2|3,'
        '"relevance_score": 1-10,'
        '"relevance_rationale": "why this score — patient population overlap, stage, mechanism",'
        '"confidence": 60-100,'
        '"reason": "one sentence — why this entity matters for this area",'
        '"suggested_dest": "new_company|molecule_update|trial_update|deal_update|catalyst_update|evidence_update",'
        '"relationship_type": "peer_competitor|licensor|licensee|partner|parent_subsidiary|asset_owner|co_developer|direct_competitor|adjacent_competitor|unknown",'
        '"relationship_confidence": "confirmed|inferred|suggested",'
        '"why_discovered": "brief explanation of what search query / criteria matched this entity"'
        "}]}\n\n"
        "RELATIONSHIP CLASSIFICATION RULES (critical — read before writing relationship_type):\n"
        "- Default: relationship_type = 'peer_competitor', relationship_confidence = 'inferred'\n"
        "  Use this when the entity is in the same competitive landscape but there is NO explicit deal.\n"
        "- Only use 'licensor' or 'licensee' if you can cite a specific licensing agreement (press release,\n"
        "  SEC filing, ClinicalTrials.gov record, or official announcement). Do NOT infer licensing from\n"
        "  market proximity alone.\n"
        "- Use 'confirmed' only for relationships stated explicitly in a primary source.\n"
        "- Use 'inferred' for logical deductions (same target/indication, overlapping geography).\n"
        "- Use 'suggested' for speculative associations that need human verification.\n"
        "- why_discovered: explain the specific search criteria that surfaced this entity\n"
        "  (e.g. 'IL-4Ra antibody in atopic dermatitis Phase 3 — same target and indication').\n"
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

    queued = 0
    for ent in new_entities:
        co_name          = ent.get("company_name", "")
        drug_name        = ent.get("drug_name")
        confidence       = int(ent.get("confidence", 60))
        relevance_score  = int(ent.get("relevance_score", 5))
        relevance_rat    = ent.get("relevance_rationale", "")
        competition_lay  = ent.get("competition_layer") or None
        overlap          = ent.get("overlap", "Watch")
        entity_type      = ent.get("entity_type", "company")
        reason           = ent.get("reason", "")
        suggested_dest   = ent.get("suggested_dest", "new_company")
        partner_co       = ent.get("partner_co") or None
        acquired_by      = ent.get("acquired_by") or None
        # Relationship classification (v10 fields — require migration v10)
        relationship_type = ent.get("relationship_type") or "peer_competitor"
        relationship_conf = ent.get("relationship_confidence") or "inferred"
        why_discovered    = ent.get("why_discovered") or None
        # Enforce: never write licensor/licensee without explicit evidence
        if relationship_type in ("licensor", "licensee") and relationship_conf != "confirmed":
            log(f"    ⚠ relationship_type={relationship_type} requires confirmed evidence — downgrading to peer_competitor/inferred", indent=2)
            relationship_type = "peer_competitor"
            relationship_conf = "inferred"

        # Normalize entity_type to discovery_queue CHECK constraint values
        _valid_etypes = {"company","molecule","trial","deal","catalyst","article","evidence_item","poster"}
        if entity_type not in _valid_etypes:
            entity_type = "company"

        log(
            f"  → {co_name}/{drug_name} "
            f"(conf={confidence} rel={relevance_score} layer={competition_lay}): {reason}",
            indent=1
        )

        if confidence < 70:
            log(f"    ↷ Low confidence ({confidence}) — skip", indent=2)
            continue

        if relevance_score < 5:
            log(f"    ↷ Low relevance ({relevance_score}) — auto-archive", indent=2)
            if not dry_run:
                # Still record it so we have a history, but mark archived immediately
                _dq_archived = {
                    "company_name":           co_name,
                    "company_id_suggested":   re.sub(r'[^a-z0-9]', '', co_name.lower())[:20],
                    "drug_name":              drug_name,
                    "target":                 ent.get("target", ""),
                    "stage":                  ent.get("stage", "Preclinical"),
                    "modality":               ent.get("modality") or None,
                    "route":                  ent.get("route") or None,
                    "entity_type":            entity_type,
                    "partner_co":             partner_co,
                    "acquired_by":            acquired_by,
                    "area_id":                area_id,
                    "overlap":                overlap,
                    "competition_layer":      competition_lay,
                    "confidence_score":       confidence,
                    "relevance_score":        relevance_score,
                    "relevance_rationale":    relevance_rat,
                    "reason":                 reason,
                    "suggested_dest":         suggested_dest,
                    "discovered_by":          "step1_discovery",
                    "discovery_run_id":       run_id,
                    "status":                 "archived",
                    "relationship_type":      relationship_type,
                    "relationship_confidence": relationship_conf,
                    "why_discovered":         why_discovered,
                }
                ok = sb_post("discovery_queue", _dq_archived)
                if not ok:
                    # Fallback: retry without v10 columns (migration not yet applied)
                    _dq_archived.pop("relationship_type", None)
                    _dq_archived.pop("relationship_confidence", None)
                    _dq_archived.pop("why_discovered", None)
                    sb_post("discovery_queue", _dq_archived)
            continue

        # Check if this entity is already in the queue (pending or approved) to avoid duplicates
        co_id_suggested = re.sub(r'[^a-z0-9]', '', co_name.lower())[:20]

        # Check if already a first-class entity in the database
        already_exists = bool(resolve_company_id(co_name, company_map))
        if already_exists:
            existing_area = sb_get("company_areas", {
                "company_id": f"eq.{resolve_company_id(co_name, company_map)}",
                "area_id":    f"eq.{area_id}",
                "select":     "company_id"
            })
            if existing_area:
                log(f"    ↷ Already in DB as {resolve_company_id(co_name, company_map)} — skip queue", indent=2)
                continue

        # Check for duplicate pending entry in discovery_queue
        dq_existing = sb_get("discovery_queue", {
            "company_id_suggested": f"eq.{co_id_suggested}",
            "area_id":              f"eq.{area_id}",
            "status":               "in.(pending,approved)",
            "select":               "id"
        })
        if dq_existing:
            log(f"    ↷ Already in discovery_queue (pending/approved) — skip", indent=2)
            continue

        if dry_run:
            log(f"    [DRY RUN] Would queue: {co_name} rel={relevance_score} layer={competition_lay}", indent=2)
            queued += 1
            continue

        # Determine queue status based on relevance
        # 9-10 → priority (still pending — needs human review but flagged urgent)
        # 7-8  → standard pending
        # 5-6  → watch
        queue_status = "pending"

        _dq_pending = {
            "company_name":            co_name,
            "company_id_suggested":    co_id_suggested,
            "drug_name":               drug_name,
            "target":                  ent.get("target", ""),
            "stage":                   ent.get("stage", "Preclinical"),
            "modality":                ent.get("modality") or None,
            "route":                   ent.get("route") or None,
            "entity_type":             entity_type,
            "partner_co":              partner_co,
            "acquired_by":             acquired_by,
            "area_id":                 area_id,
            "overlap":                 overlap,
            "competition_layer":       competition_lay,
            "confidence_score":        confidence,
            "relevance_score":         relevance_score,
            "relevance_rationale":     relevance_rat,
            "reason":                  reason,
            "suggested_dest":          suggested_dest,
            "discovered_by":           "step1_discovery",
            "discovery_run_id":        run_id,
            "status":                  queue_status,
            "relationship_type":       relationship_type,
            "relationship_confidence": relationship_conf,
            "why_discovered":          why_discovered,
        }
        ok = sb_post("discovery_queue", _dq_pending)
        if not ok:
            # Fallback: retry without v10 columns (migration not yet applied)
            _dq_pending.pop("relationship_type", None)
            _dq_pending.pop("relationship_confidence", None)
            _dq_pending.pop("why_discovered", None)
            ok = sb_post("discovery_queue", _dq_pending)

        priority_flag = " ⚡ PRIORITY" if relevance_score >= 9 else ""
        log(
            f"    → Queued in discovery_queue: {co_name} "
            f"(rel={relevance_score} conf={confidence} layer={competition_lay}){priority_flag}",
            indent=2
        )
        queued += 1

    if queued:
        log(f"  Step 1 complete: {queued} candidates added to discovery_queue (pending review)", indent=1)
    else:
        log(f"  Step 1 complete: no new candidates queued", indent=1)

    return queued


# ══════════════════════════════════════════════════════════════════════════
# CONTEXT FETCH — pulls all existing Supabase data for a company
# (Step 3 trials are pre-populated by ct_gov_sync.py)
# ══════════════════════════════════════════════════════════════════════════

CT_GOV_BASE = "https://clinicaltrials.gov/api/v2"

def _pre_sync_trials_from_ctgov(drugs: list) -> int:
    """
    For each drug in `drugs`, search ClinicalTrials.gov by drug name and upsert
    any found trials into the trials table.  Returns the count of new rows inserted.
    Only runs for drugs that currently have zero trial rows — acts as a lightweight
    ct_gov_sync substitute so the enrichment step is self-contained.
    """
    import time as _time

    STATUS_MAP = {
        "RECRUITING":              "Recruiting",
        "ACTIVE_NOT_RECRUITING":   "Active, not recruiting",
        "COMPLETED":               "Completed",
        "NOT_YET_RECRUITING":      "Not yet recruiting",
        "ENROLLING_BY_INVITATION": "Enrolling by invitation",
        "TERMINATED":              "Terminated",
        "WITHDRAWN":               "Withdrawn",
        "SUSPENDED":               "Suspended",
    }

    def _ctgov_search(drug_name: str, indication: str = None, max_results: int = 8) -> list:
        # Note: query.cond is intentionally omitted — our indication_short strings
        # (e.g. "UC · CD") use abbreviations CT.gov doesn't parse, which returns 0
        # results. The drug name intervention search is specific enough on its own.
        params = {"format": "json", "pageSize": max_results, "query.intr": drug_name}
        try:
            r = requests.get(f"{CT_GOV_BASE}/studies", params=params, timeout=20)
            if r.status_code == 200:
                return r.json().get("studies", [])
        except Exception as e:
            log(f"    CT.gov search error for '{drug_name}': {e}", indent=2)
        return []

    def _parse_study(study: dict, drug_id: str) -> dict | None:
        ps = study.get("protocolSection", {})
        id_mod  = ps.get("identificationModule", {})
        st_mod  = ps.get("statusModule", {})
        de_mod  = ps.get("designModule", {})
        co_mod  = ps.get("conditionsModule", {})

        nct_id = id_mod.get("nctId", "")
        if not nct_id.startswith("NCT"):
            return None

        raw_status = (st_mod.get("overallStatus") or "").upper()
        status = STATUS_MAP.get(raw_status, raw_status.replace("_", " ").title())

        phases = de_mod.get("phases", [])
        if phases:
            phase_str = " / ".join(p.replace("PHASE", "Phase ").replace("_", " ").strip() for p in phases)
        else:
            # No phases → use studyType to determine non-interventional label
            study_type = (de_mod.get("studyType") or "").upper()
            if study_type == "OBSERVATIONAL":
                phase_str = "Observational"
            elif study_type == "EXPANDED_ACCESS":
                phase_str = "Expanded Access"
            else:
                phase_str = None

        pcd_struct = st_mod.get("primaryCompletionDateStruct", {})
        pcd = pcd_struct.get("date") or None  # YYYY-MM-DD or YYYY-MM

        conditions = co_mod.get("conditions", [])
        indication = " · ".join(conditions[:3]) if conditions else None

        return {
            "id":                     nct_id,
            "drug_id":                drug_id,
            "trial_name":             (id_mod.get("briefTitle") or "")[:300] or None,
            "study_acronym":          id_mod.get("acronym") or None,
            "phase":                  phase_str,
            "status":                 status,
            "indication":             indication[:200] if indication else None,
            "primary_completion_date": pcd,
            "source_url":             f"https://clinicaltrials.gov/study/{nct_id}",
            "last_synced_date":       NOW_ISO,
            "discovery_status":       "auto",
        }

    total_new = 0
    for drug in drugs:
        drug_id   = drug["id"]
        drug_name = drug.get("name") or drug_id
        indication = drug.get("indication_short") or None

        log(f"    CT.gov pre-sync: '{drug_name}' ({drug_id})", indent=2)
        studies = _ctgov_search(drug_name, indication=indication)

        inserted = 0
        for study in studies:
            rec = _parse_study(study, drug_id)
            if not rec:
                continue
            # Skip trials that already exist
            existing = sb_get("trials", {"id": f"eq.{rec['id']}", "select": "id"})
            if existing:
                continue
            rec_clean = {k: v for k, v in rec.items() if v is not None}
            result = sb_upsert("trials", rec_clean)
            if result:
                log(f"      ✓ {rec['id']} | {rec.get('phase','?')} | {rec.get('status','?')}", indent=3)
                inserted += 1
            _time.sleep(0.3)

        if not inserted:
            log(f"      no new trials found", indent=3)
        total_new += inserted

    return total_new


def _refresh_existing_trials_from_ctgov(trials: list) -> int:
    """
    For each trial row that already exists in the DB, re-fetch its CT.gov record
    directly by NCT ID and upsert the latest status, phase, PCD, and acronym.
    Returns the count of successfully refreshed rows.
    """
    import time as _time

    STATUS_MAP = {
        "RECRUITING":              "Recruiting",
        "ACTIVE_NOT_RECRUITING":   "Active, not recruiting",
        "COMPLETED":               "Completed",
        "NOT_YET_RECRUITING":      "Not yet recruiting",
        "ENROLLING_BY_INVITATION": "Enrolling by invitation",
        "TERMINATED":              "Terminated",
        "WITHDRAWN":               "Withdrawn",
        "SUSPENDED":               "Suspended",
    }

    def _fetch_study(nct_id: str) -> dict | None:
        try:
            r = requests.get(f"{CT_GOV_BASE}/studies/{nct_id}", params={"format": "json"}, timeout=20)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            log(f"    CT.gov fetch error for {nct_id}: {e}", indent=3)
        return None

    refreshed = 0
    for trial in trials:
        nct_id  = (trial.get("id") or "").strip()
        drug_id = (trial.get("drug_id") or "").strip()
        if not nct_id.startswith("NCT") or not drug_id:
            continue

        study = _fetch_study(nct_id)
        if not study:
            log(f"      ✗ {nct_id} — not found on CT.gov", indent=3)
            _time.sleep(0.2)
            continue

        ps     = study.get("protocolSection", {})
        id_mod = ps.get("identificationModule", {})
        st_mod = ps.get("statusModule", {})
        de_mod = ps.get("designModule", {})
        co_mod = ps.get("conditionsModule", {})
        en_mod = ps.get("designModule", {}).get("enrollmentInfo", {}) or {}

        raw_status = (st_mod.get("overallStatus") or "").upper()
        status = STATUS_MAP.get(raw_status, raw_status.replace("_", " ").title())

        phases = de_mod.get("phases", [])
        if phases:
            phase_str = " / ".join(p.replace("PHASE", "Phase ").replace("_", " ").strip() for p in phases)
        else:
            study_type = (de_mod.get("studyType") or "").upper()
            if study_type == "OBSERVATIONAL":
                phase_str = "Observational"
            elif study_type == "EXPANDED_ACCESS":
                phase_str = "Expanded Access"
            else:
                phase_str = None

        pcd = (st_mod.get("primaryCompletionDateStruct", {}) or {}).get("date") or None

        conditions = co_mod.get("conditions", [])
        indication = " · ".join(conditions[:3]) if conditions else None

        n_enrollment = en_mod.get("count") or None  # integer enrollment count

        update_rec = {
            "id":                     nct_id,
            "drug_id":                drug_id,
            "status":                 status,
            "last_synced_date":       NOW_ISO,
        }
        if phase_str:
            update_rec["phase"] = phase_str
        if pcd:
            update_rec["primary_completion_date"] = pcd
        if indication:
            update_rec["indication"] = indication[:200]
        if id_mod.get("acronym"):
            update_rec["study_acronym"] = id_mod["acronym"]
        if n_enrollment is not None:
            update_rec["n_enrollment"] = n_enrollment
        update_rec["source_url"] = f"https://clinicaltrials.gov/study/{nct_id}"

        ok = sb_upsert("trials", update_rec)
        if ok:
            log(f"      ↻ {nct_id} | {status} | pcd={pcd or '—'}", indent=3)
            refreshed += 1
        else:
            log(f"      ✗ {nct_id} — upsert failed", indent=3)

        _time.sleep(0.25)

    return refreshed


def fetch_company_context(company_id: str, area_id: str) -> dict:
    """Pull all Supabase data for a company × area."""
    companies = sb_get("companies", {"id": f"eq.{company_id}", "select": "*"})
    company   = companies[0] if companies else {}

    profiles = sb_get("company_profiles", {
        "company_id": f"eq.{company_id}", "area_id": f"eq.{area_id}", "select": "*"
    })
    profile = profiles[0] if profiles else {}

    # Fetch the indication_group for this area (e.g. tl1a → 'ibd').
    # The frontend shows drugs tagged with the indication_group (broader IBD set),
    # not just the specific area. We must mirror this so the enrichment context
    # includes the same drugs the dashboard displays (e.g. risankizumab + upadacitinib
    # for AbbVie in the TL1A tab, even though they're tagged 'ibd' not 'tl1a').
    area_meta = sb_get("disease_areas", {"id": f"eq.{area_id}", "select": "indication_group"})
    indication_group = (area_meta[0].get("indication_group") if area_meta else None) or area_id
    fetch_areas = list({area_id, indication_group})  # deduplicate
    drug_area_rows = sb_get("drug_areas", {
        "area_id": f"in.({','.join(fetch_areas)})", "select": "drug_id"
    })
    area_drug_ids  = {r["drug_id"] for r in drug_area_rows}
    all_co_drugs   = sb_get("drugs", {"company_id": f"eq.{company_id}", "select": "*"})
    drugs = [d for d in all_co_drugs if d["id"] in area_drug_ids]

    # Trials: fetch existing rows, then pre-sync any drugs that have none
    trials = []
    for d in drugs:
        t_rows = sb_get("trials", {"drug_id": f"eq.{d['id']}", "select": "*"})
        trials.extend(t_rows)

    # ── Pre-sync missing trials via CT.gov API ────────────────────────────
    # For drugs with zero trial rows, search ClinicalTrials.gov directly and
    # upsert what we find so the TRIALS block Claude sees is already populated.
    drug_ids_with_trials = {t["drug_id"] for t in trials}
    drugs_needing_trials = [d for d in drugs if d["id"] not in drug_ids_with_trials]
    if drugs_needing_trials:
        log(f"  Pre-syncing CT.gov trials for {len(drugs_needing_trials)} drugs with no trial rows…")
        newly_synced = _pre_sync_trials_from_ctgov(drugs_needing_trials)
        if newly_synced:
            # Re-fetch trials so they appear in the TRIALS block sent to Claude
            for d in drugs_needing_trials:
                t_rows = sb_get("trials", {"drug_id": f"eq.{d['id']}", "select": "*"})
                trials.extend(t_rows)
            log(f"  Pre-sync complete — {newly_synced} new trial rows added")

    # ── Refresh existing trials via CT.gov direct fetch ───────────────────
    # For drugs that already have trial rows, re-fetch each NCT ID from CT.gov
    # so status, PCD, enrollment, and phase stay current.
    if trials:
        log(f"  Refreshing {len(trials)} existing trial(s) from CT.gov…")
        refreshed = _refresh_existing_trials_from_ctgov(trials)
        log(f"  Refresh complete — {refreshed}/{len(trials)} trial(s) updated")
        # Re-fetch updated rows so Claude sees the latest values
        if refreshed:
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

    # Fetch ailux_positions for this area (or its indication_group) so enrichment can
    # classify every drug against Ailux's competitive anchor — without hardcoded rules.
    # Try area_id first (e.g. 'tl1a'), then indication_group (e.g. 'ibd') as fallback.
    ailux_pos = {}
    _pos_rows = sb_get("ailux_positions", {"area_id": f"eq.{area_id}", "select": "*"})
    if not _pos_rows and indication_group:
        _pos_rows = sb_get("ailux_positions", {"area_id": f"eq.{indication_group}", "select": "*"})
    if _pos_rows:
        ailux_pos = _pos_rows[0]

    return {
        "company": company, "profile": profile, "drugs": drugs,
        "trials": trials, "catalysts": catalysts, "deals": deals,
        "recent_intel": recent_intel, "ailux_pos": ailux_pos,
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
    # Monospecifics — include indication + patient population context so discovery
    # catches adjacent-mechanism companies competing for the SAME patients
    "tl1a": (
        "TL1A (anti-TL1A antibodies, IBD — UC/CD). "
        "ALSO include: IL-23 inhibitors, IL-23+TNF combo programs (e.g. VEGA/DUET), "
        "JAK inhibitors, and integrin inhibitors with active Phase 2+ IBD programs. "
        "These compete for the same biologic-naive and biologic-experienced UC/CD patients."
    ),
    "tslp": (
        "TSLP (anti-TSLP antibodies, severe asthma/atopic disease). "
        "ALSO include: IL-33, IL-25/TSLP pathway inhibitors, and companies with "
        "active Phase 2+ programs in severe asthma, CRSwNP, or atopic dermatitis "
        "that compete in the same patient population."
    ),
    "il4ra": (
        "IL-4Rα (anti-IL-4Rα or IL-4/IL-13 pathway, atopic dermatitis/asthma). "
        "ALSO include: OX40/OX40L inhibitors, IL-13 inhibitors, IL-31 inhibitors, "
        "and any company with active Phase 2+ programs in moderate-to-severe AD "
        "competing against dupilumab-class agents."
    ),
    "igf1r": (
        "IGF1R (anti-IGF1R, thyroid eye disease / oncology). "
        "ALSO include: TSHR-targeting programs, TSH receptor antibody-targeting approaches, "
        "and any Phase 2+ programs in thyroid eye disease (TED/Graves' orbitopathy)."
    ),
    "fcrn": (
        "FcRn (anti-FcRn, autoimmune/IgG-mediated disease). "
        "ALSO include: programs for CIDP, myasthenia gravis, ITP, pemphigus, NMOSD, "
        "lupus nephritis, and other IgG-mediated autoimmune diseases where FcRn "
        "inhibition or IgG reduction is the mechanism."
    ),
    "tcell": (
        "T-cell engagers / bispecific T-cell redirectors (oncology — hematologic malignancies). "
        "ALSO include: CAR-T programs, CD19/CD20/BCMA-targeted bispecifics, and "
        "any Phase 1+ programs in B-cell malignancies, multiple myeloma, or "
        "autoimmune disease using T-cell redirection."
    ),
    # Bispecifics
    "il4ra_tslp":  "IL-4Rα×TSLP bispecific (atopic dermatitis/asthma)",
    "il4ra_ox40l": "IL-4Rα×OX40L bispecific (atopic dermatitis/asthma)",
    "igf1r_tshr":  "IGF1R×TSHR bispecific (thyroid eye disease / oncology)",
    # Other
    "ace":         "ACE2-based programs (respiratory/cardiometabolic)",
    # Broad groupings (used as indication_group fallback)
    "ibd":         "IBD (inflammatory bowel disease — UC/CD)",
    "atopic":      "Atopic disease (AD, asthma, EoE)",
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

TOPIC 1 — CLINICAL DATA (current AND historical)
Search for trial results across ALL phases — not just the most recent.
What endpoints did they hit? What were the response rates, p-values, or biomarker results?
Which conferences (ECCO, DDW, ACR, ASCO, NEJM, Lancet, NEJM Evidence)?
Any Phase 3 readouts, POC data, dose-selection results in the last 24 months?
CRITICAL: Also search for earlier Phase 1 and Phase 2 proof-of-concept or dose-finding trials that preceded the current Phase 3 program. These are often the scientific foundation for Phase 3 and may have published results (even if the trial completed 2-4 years ago). Search specifically for: "[drug name] Phase 1 results", "[drug name] Phase 2 results", "[drug name] proof of concept", "[drug name] dose escalation". A completed Phase 2b that missed its primary endpoint is MORE important to capture than a currently-recruiting Phase 3, because it carries the key risk data.

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

TARGET NOTATION (CRITICAL — target field must be targets ONLY, never include company or modality annotations):
- IL-23 inhibitors: ALWAYS specify "IL-23p19" (not "IL-23" alone). The p19 subunit is the
  specific target of all modern IL-23 inhibitors. IL-23p40 inhibitors are a different class.
- Bispecifics use "×" separator: "TL1A × IL-23p19" (NOT "TL1A/IL-23" or "anti-TL1A × IL-23")
- Rational combinations (two separate co-administered mAbs) use "+" separator: "IL-23p19 + TL1A"
- Monospecific mAbs: do NOT prefix with "Anti-" in the target field (use in mechanism field only)
- NEVER include modality labels in target: NOT "TL1A × IL-23p19 bispecific" — just "TL1A × IL-23p19"
- NEVER include company annotations in target: NOT "IL-23p40 × TL1A bispecific, Roche/Pfizer co-dev"
  The dashboard will display the "bispecific" modality from drug_format and the partner from partner_company.
  Target field = molecular targets only.

CO-DEVELOPMENT PARTNERSHIP DETECTION:
If you see text like "Company/Company co-dev" or "co-developed with Company" anywhere in the literature:
1. Extract the partner company name and put it in partner_company
2. Set partnership_type = "co_developed"
3. Set partnership_verified = false (mark as inferred — needs confirmation from official source)
4. Leave it OUT of the target field entirely
Confirmed co-development vs. inferred: only set partnership_verified = true when you find an explicit
official press release, ClinicalTrials.gov sponsor field, or SEC filing confirming the partnership.
If the partnership is from secondary sources (news articles, databases), set partnership_verified = false.

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
    co        = ctx["company"]
    profile   = ctx["profile"]
    ailux_pos = ctx.get("ailux_pos", {})
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
                 "primary_endpoint","pcd_label","primary_completion_date","sponsor",
                 "study_acronym")
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
        # Structured intelligence (primary) — shown so model can update/refine existing analysis
        "platform_intelligence": profile.get("platform_intelligence"),
        "bd_intelligence":       profile.get("bd_intelligence"),
        # Scalar fields
        "key_risk":         profile.get("key_risk", ""),
        "why_it_matters":   profile.get("why_it_matters", ""),
        "vs_ailux":         profile.get("vs_ailux", ""),
        # LEGACY TEXT — for context only; do NOT return platform_summary or bd_summary in output
        "_legacy_platform_summary": (profile.get("platform_summary") or "")[:400] or None,
        "_legacy_bd_summary":       (profile.get("bd_summary") or "")[:400] or None,
    }, indent=2)

    financial_fields = (
        '"market_cap_usd_m": null or number,'
        if is_public else
        '"cash_runway": "e.g. H2 2028 or null",'
        '"financing_history": [{"date": "YYYY-MM", "amount_usd_m": X, "series": "Series A", "investors": ["name"]}],'
        '"key_investors": ["name1", "name2"],'
    )

    # Build Ailux competitive anchor block — fetched from ailux_positions table.
    # This is the reference the LLM uses to classify every drug as Direct/Adjacent/Watch.
    # If no position row exists for this area, the block is omitted and the LLM uses
    # its own judgment (acceptable for new areas, but adding a row is strongly preferred).
    if ailux_pos:
        ailux_block = (
            "\nAILUX COMPETITIVE ANCHOR (read this before classifying any drug):\n"
            f"Ailux drug: {ailux_pos.get('ailux_drug','SPY002')} | "
            f"Targets: {ailux_pos.get('ailux_targets','')} | "
            f"Modality: {ailux_pos.get('ailux_modality','')} | "
            f"Stage: {ailux_pos.get('ailux_stage','')}\n"
            f"Ailux angle: {ailux_pos.get('ailux_angle','')}\n\n"
            "TIER CLASSIFICATION RULES (apply to EVERY drug and combo you write):\n"
            f"DIRECT — {ailux_pos.get('direct_criteria','')}\n"
            f"  Examples: {ailux_pos.get('direct_examples','')}\n\n"
            f"ADJACENT — {ailux_pos.get('adjacent_criteria','')}\n"
            f"  Examples: {ailux_pos.get('adjacent_examples','')}\n\n"
            f"WATCH (Same-Space) — {ailux_pos.get('watch_criteria','')}\n"
            f"  Examples: {ailux_pos.get('watch_examples','')}\n\n"
            f"NOTES: {ailux_pos.get('notes','')}\n"
        )
    else:
        ailux_block = (
            "\nNOTE: No ailux_positions row found for this area. "
            "Use your best judgment to classify overlap as Direct (same molecular target as Ailux), "
            "Adjacent (same disease, validating/complementary biology), or Watch (same patients, different pathway).\n"
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
{ailux_block}
Return JSON with EXACTLY these fields:

⚠ CRITICAL SCHEMA REQUIREMENT:
- "platform_intelligence" and "bd_intelligence" are REQUIRED structured objects — NEVER return null for these.
- DO NOT return "platform_summary" or "bd_summary" as text strings — those fields are DEPRECATED. If you return them, they will be ignored. The only accepted format is the structured objects below.
- If existing structured intelligence is shown in CURRENT PROFILE above, refine or extend it — do not regress to plain text.

{{
  "company_profile": {{
    "platform_intelligence": {{
      "facts": [
        "Array of 3-5 tight fact bullets. Each ≤15 words. ONLY directly verifiable statements about the clinical platform — asset name, stage, mechanism, approval status, key data readouts. No BD deals, no financing, no interpretations. Examples: 'ABBV-701 (TL1A mAb, licensed FutureGen Jun 2024): Phase 1 SAD, est. completion Oct 2026', 'Skyrizi (IL-23p19): approved UC+CD; $17.6B FY2025 revenue', 'XENITH-UC Phase 2b (~220 pts): enrolling, primary completion Apr 2028'."
      ],
      "direction": [
        "Array of 2-3 interpretation bullets. Each ≤15 words. Logical conclusions about the PLATFORM STRATEGY derived from the facts — not restatements, not BD behavior. Label each [INFERRED]. Examples: '[INFERRED] ABBV-701 positioned as SKYRIZI combination backbone, not TL1A monotherapy', '[INFERRED] Dual-track strategy hedges monospecific and bispecific formats simultaneously'."
      ],
      "assessment": "[ASSESSED] 1 sentence. A UNIQUE forward-looking strategic read specifically for Ailux — what does this company's platform trajectory mean for Ailux's competitive positioning or partnering opportunity? This must NOT repeat facts or BD deal details already in the other cards. Focus on: how does this change Ailux's competitive landscape, timing pressure, or partner audience? Be specific and direct.",
      "confidence": "high | medium | low — based on volume and quality of public disclosures, trial activity, and deal history"
    }},
    "bd_intelligence": {{
      "profile": "One of: acquirer | licensor | collaborator | partner-friendly | internal-focused — classify the company's dominant BD behavior in this area",
      "transactions": [
        {{"date": "Mon YYYY", "asset": "asset name / target — BD deals and financing only, NOT clinical milestones", "partner": "counterparty short name", "upfront": "$XM or null", "total": "$XM or null"}}
      ],
      "assessment": [
        "Array of 2-3 short [ASSESSED] bullets. Each ≤15 words. BD-specific conclusions ONLY — deal structure, partnering likelihood, pricing benchmarks, timing of BD window. Must NOT repeat platform science facts from platform_intelligence. Examples: '[ASSESSED] Unlikely licensing target — executing TL1A in-house; no external partnership expected', '[ASSESSED] FutureGen deal sets $1.71B floor for Phase 1 TL1A asset pricing'."
      ],
      "confidence": "high | medium | low"
    }},
    "key_risk": "1-2 sentences: single most important risk.",
    "why_it_matters": "1-2 sentences: why this competitor matters for Ailux's BD strategy.",
    "vs_ailux": "1-2 sentences: how this program compares to Ailux's TL1A×IL-23p19 bispecific.",
    "strategic_behavior": "1 sentence: acquirer / licensor / partner-seeker / platform builder.",
    "pipeline_url": "URL or null",
    {financial_fields}
  }},
  "drug_updates": [{{
    "drug_id": "exact drug id from DRUGS list",
    "strategic_role": "REQUIRED — classify this drug's role for this company in this area: 'direct_competitor' (same mechanism as Ailux TL1A×IL-23p19), 'franchise_anchor' (dominant commercial asset the company's IBD strategy is built on), 'combination_asset' (designed to be used in combo with another drug), 'same_space_defense' (same indication, different mechanism, commercially important), 'platform_expansion' (future programs extending the franchise), or 'watch' (early/uncertain relevance)",
    "display_name": "null or override display name — use when company uses a different code than the drug_id. Format: 'CompanyCode (OriginalCode)' e.g. 'ABBV-701 (FG-M701)' or 'Skyrizi (Risankizumab)'. Only set when the canonical displayed name differs from what the drug_id implies.",
    "licensor_name": "null or full legal name of the originating company — e.g. 'FutureGen Biopharmaceutical Co., Ltd.'. Only for in-licensed assets.",
    "licensor_code": "null or original code/name used by licensor — e.g. 'FG-M701'. Only when drug was renamed by licensee.",
    "partner_company": "REQUIRED for any non-self deal — short display name of the originating/partner company, NO legal suffixes (e.g. 'FutureGen Biopharmaceutical', 'Simcere', 'Teva', 'Prometheus Biosciences'). This is what appears in the dashboard pill next to the drug name. Must be null only when partnership_type is 'self' or null.",
    "partnership_verified": "null | false | true. Set false when partnership is inferred from secondary sources (news, databases). Set true ONLY when confirmed from an official source (press release, SEC filing, ClinicalTrials.gov sponsor field). Default null when partnership_type is 'self' or no partner.",
    "modality": "anti-TL1A mAb|TL1A×IL-23p19 bispecific|JAK1 inhibitor (oral small molecule)|anti-α4β7 integrin mAb|etc — full descriptive label",
    "drug_format": "mAb|bispecific|small molecule|ADC|nanobody|fusion protein",
    "route": "SC|IV|SC/IV|oral|null",
    "dosing_type": "Induction|Maintenance|Induction + Maintenance|null",
    "dosing_schedule": "null or e.g. Q3M SC",
    "indication_short": "null or abbreviated indication list using standard clinical abbreviations separated by ' · ' — e.g. 'UC · CD', 'AD · RA', 'AD'. ALWAYS abbreviate: Ulcerative Colitis→UC, Crohn's Disease→CD, Atopic Dermatitis→AD, Rheumatoid Arthritis→RA, Psoriatic Arthritis→PsA, Psoriasis→Ps, Ankylosing Spondylitis→AS, Hidradenitis Suppurativa→HS, Eosinophilic Esophagitis→EoE, Alopecia Areata→AA, SLE, MS, TED, gMG, COPD, NASH, MASH, IBD. Never write full disease names.",
    "stage_detail": "null or e.g. Phase 2b (ARTEMIS-CD)",
    "phase_display": "null or e.g. Phase 3",
    "half_life_note": "null or e.g. ~74 days",
    "mechanism_detail": "null or 1-2 sentences: specific mechanism, format, any structural notes (platform tech, half-life, engineering)",
    "drug_summary": "REQUIRED — 1-2 sentences MAX. Written for PhD scientists and BD professionals: dense, factual, zero filler. Lead with the most clinically or commercially significant fact. Include mechanism, stage, and one differentiating detail (e.g. key data point, platform, deal structure). For approved drugs: include revenue and approval status. Never use phrases like 'noteworthy', 'important', 'significant' — show the fact, not the adjective. Never return null.",
    "key_data": "REQUIRED for approved/late-stage drugs — most important clinical data point in one sentence (e.g. primary endpoint result, pivotal trial outcome). For early-stage with no public data: brief mechanism note. Never leave null if drug_summary is populated.",
    "vs_ailux": "null or 1 sentence comparison to Ailux's TL1A×IL-23p19 bispecific — mechanism, stage, differentiation",
    "overlap": "REQUIRED — Direct | Adjacent | Watch. Use AILUX COMPETITIVE ANCHOR rules above. Direct = same molecular target as Ailux (TL1A) or combo that includes TL1A. Adjacent = same disease, different mechanism, validates biology or is a combination candidate. Watch = same patients, completely different pathway.",
    "overlap_rationale": "REQUIRED — 1-2 sentences explaining why this drug is classified in this tier relative to Ailux's TL1A position. Be specific about the mechanism.",
    "confidence_level": "confirmed|supported|inferred",
    "data_source": "ct_gov|sec_filing|press_release|conference|claude_inferred",
    "aliases": [],
    "approval_date": "null or string: regulatory approval date and indication — e.g. 'May 2023 (UC); Jan 2024 (CD)'. ONLY populate for drugs where stage contains 'Approved'.",
    "annual_revenue": "null or string: latest reported annual revenue with year — e.g. '$10.4B (2024)'. ONLY for approved drugs.",
    "patient_population": "null or string: estimated patients on therapy globally — e.g. '~250,000 patients on therapy'. ONLY for approved drugs.",
    "final_endpoints": "null or string: pivotal trial primary endpoint results narrative in 1-3 sentences. ONLY for approved drugs."
  }}],
  "combination_programs": [{{
    "label": "Short name for this combination — e.g. 'Skyrizi + ABBV-382 (α4β7 + IL-23p19)'",
    "component_drug_ids": ["exact drug_id from DRUGS list", "..."],
    "combination_type": "backbone_addon (established drug + add-on) | rational_combo (two investigational drugs) | sequential (drugs used in sequence, not simultaneously)",
    "stage": "Phase 1|Phase 2|Phase 3|Planned Ph1|Planned Ph2|Planned Ph2b|Preclinical|Concept — use 'Planned Phx' for disclosed but not yet initiated studies (no NCT registered)",
    "phase_display": "null or e.g. 'Phase 2b (anticipated initiation H2 2026)'",
    "anticipated_start": "null or company-guided start timing for planned studies — e.g. 'H2 2026'. REQUIRED when stage starts with 'Planned'.",
    "prerequisite_note": "null or what must happen before this study can begin — e.g. 'Awaiting Phase 1 monotherapy completion for ABBV-701'. REQUIRED when stage starts with 'Planned' and there is a known dependency.",
    "indication_short": "e.g. 'UC · CD'",
    "strategic_significance": "high|medium|low",
    "mechanism_detail": "1-2 sentences: rationale for combining these mechanisms, what complementary biology is targeted",
    "drug_summary": "2-3 sentences: what is known about this combination program — trial data, company guidance, strategic rationale",
    "overlap": "REQUIRED — Direct | Adjacent | Watch. A combo that includes a TL1A component = Direct. A multi-mechanism IBD combo without TL1A = Adjacent. Use AILUX COMPETITIVE ANCHOR rules above.",
    "overlap_rationale": "REQUIRED — 1-2 sentences explaining why this combination program is classified in this tier.",
    "notes": "1 sentence: source or confidence note",
    "source_url": "null or URL to press release, trial registration, or IR page — never fabricate. REQUIRED when stage starts with 'Planned'."
  }}],
  "trial_updates": [{{
    "trial_id": "exact trial id from TRIALS list (the 'id' field, e.g. 'NCT06895343')",
    "study_acronym": "null or string: the branded program acronym this company uses for the trial — e.g. 'SKYLINE-UC' (Spyre), 'U-ACHIEVE' (AbbVie), 'PURSUIT' (J&J), 'ARTEMIS-CD'. Search the company's press releases and IR materials for how they brand this study. If the TRIALS list already shows a non-null study_acronym, confirm or correct it. Only include if you find a specific acronym — never fabricate.",
    "status": "null or current trial status from ClinicalTrials.gov — one of: Recruiting | Active, not recruiting | Completed | Not yet recruiting | Enrolling by invitation | Terminated | Withdrawn | Suspended. Update if the current status differs from the TRIALS list. Return null only if you cannot verify the current status.",
    "primary_completion_date": "null or YYYY-MM-DD: the current primary completion date from ClinicalTrials.gov. Update if the date has changed or was previously null. Return null only if not listed on CT.gov.",
    "area_fit": "REQUIRED — classify this trial's relevance to the current area: 'primary' = trial tests in the exact target indication for this area (e.g. UC or CD trial in the tl1a area), 'secondary' = same disease family but broader (e.g. IBD maintenance in a UC-focused area), 'off_target' = entirely different indication (e.g. psoriasis trial for a drug tracked in the IBD area), 'exclude' = basket/umbrella or observational study.",
    "estimand": "null or string: the ICH E9(R1) estimand strategy used in this trial's primary analysis. Describes how intercurrent events (rescue medication use, discontinuation, study drug change) are handled. Examples: 'Composite estimand — rescue medication use or discontinuation counted as treatment failure', 'Treatment policy estimand — all post-randomisation data included regardless of intercurrent events', 'Hypothetical estimand — data after rescue medication censored'. Search clinical trial registry, protocol, and publications for the statistical analysis plan estimand definition. Return null if not publicly specified.",
    "results_note": "null or string: key primary endpoint results for Completed or Terminated trials — 2-4 sentences. Include: primary endpoint name, response/remission rate for drug vs placebo (with p-value or CI if reported), and any headline safety signal. Source from publications (NEJM, Lancet, Gut), conference abstracts (DDW, ECCO, UEG), or ClinicalTrials.gov results postings. Example: 'GEMINI 1 (UC induction): vedolizumab achieved 47.1% clinical response vs 25.5% PBO at Wk 6 (p<0.001); 16.9% vs 5.4% clinical remission at Wk 6. GEMINI 1 (UC maintenance): 44.8% remission at Wk 52 vs 15.9% PBO (p<0.001). Well-tolerated; nasopharyngitis most common AE.' Return null for ongoing or not-yet-recruiting trials, or if no results are publicly available."
  }}],
  "new_trials": [{{
    "id": "NCT number — e.g. 'NCT06895343'. REQUIRED. Never fabricate. Only include if you have verified this NCT ID exists on ClinicalTrials.gov.",
    "drug_id": "exact drug_id from DRUGS list — the drug this trial is studying",
    "trial_name": "official full study title from ClinicalTrials.gov",
    "phase": "Phase 1 | Phase 1/Phase 2 | Phase 2 | Phase 2/Phase 3 | Phase 3 | Phase 4",
    "status": "Recruiting | Active, not recruiting | Completed | Not yet recruiting | Enrolling by invitation | Terminated | Withdrawn",
    "indication": "short condition/indication — e.g. 'Ulcerative Colitis' or 'Crohn Disease'",
    "primary_completion_date": "YYYY-MM-DD if known, else null",
    "study_acronym": "null or branded program acronym if known — e.g. 'U-ACHIEVE'",
    "source_url": "https://clinicaltrials.gov/study/NCTXXXXXXXX — always include the CTgov URL",
    "estimand": "null or string: ICH E9(R1) estimand strategy for the primary endpoint — how intercurrent events are handled. Examples: 'Composite estimand — rescue medication or discontinuation = treatment failure', 'Treatment policy estimand'. Return null if not publicly specified.",
    "results_note": "null or string: key primary endpoint results — REQUIRED for any Completed or Terminated trial. 2-4 sentences. Include endpoint name, response/remission rate vs placebo with p-value if reported, and headline safety signal. Source from publications, conference abstracts, or ClinicalTrials.gov results posting."
    "area_fit": "REQUIRED — same classification as trial_updates: 'primary' | 'secondary' | 'off_target' | 'exclude'",
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
  }}],
  "news_items": [{{
    "intel_date": "YYYY-MM-DD — date of the news item. Use exact date from article; estimate from context if needed.",
    "headline": "Concise factual headline ≤120 chars — what happened, who, and key number/outcome if applicable.",
    "body": "2-4 sentences: what happened, key data or terms, and why it matters for Ailux's BD strategy. Include the pivotal stat or outcome if a readout.",
    "source_url": "REQUIRED — exact URL of press release, IR page, or primary source. Never fabricate. Omit item if no verifiable URL.",
    "source_name": "Publication or company IR name — e.g. 'AbbVie Press Release', 'FDA', 'NEJM', 'Fierce Biotech'",
    "importance": "high (pivotal readout, major deal, approval) | medium (Phase 2 data, financing, partnership) | low (minor update, conference abstract)",
    "intel_type": "data | deal | regulatory | financing | conference | partnership | management"
  }}],
  "molecule_updates": [{{
    "drug_id": "exact drug_id from DRUGS list — one entry per drug",
    "format": "REQUIRED — e.g. 'monoclonal antibody', 'bispecific IgG1', 'nanobody', 'small molecule', 'fusion protein'",
    "valency": "e.g. 'monospecific bivalent', '2+2 (bivalent both arms)', '1+1'. null if unknown.",
    "modality": "REQUIRED — 'antibody', 'small molecule', 'biologic', 'cell therapy', 'oligonucleotide'",
    "igg_subclass": "IgG1 | IgG2 | IgG4 | other | null — infer from class/mechanism if not stated",
    "fc_engineering": "Any known Fc modifications — e.g. 'S228P hinge stabilization (IgG4)', 'YTE half-life extension', 'LALA effector silencing', 'none known'. null if no data.",
    "epitope": "Binding epitope or region if publicly disclosed — e.g. 'receptor-binding domain of TL1A'. Use 'not publicly disclosed' if absent from literature. Never null — use 'not publicly disclosed'.",
    "affinity_kd": "KD value with units if known — e.g. '0.4 nM (SPR, 37C)'. Use 'not publicly disclosed' if not reported. Never null.",
    "lowest_active_dose": null or number (mg/kg),
    "lowest_active_dose_unit": "null or 'mg/kg' | 'mg' | 'ug/kg'",
    "safety_observations": "Key safety signals from available clinical data. 'No clinical data available — preclinical stage' for pre-IND assets. Never null.",
    "differentiation_claim": "REQUIRED — 1-2 sentences. What makes this molecule structurally or mechanistically distinct from other agents in this area? Be specific: format advantage, engineering feature, epitope differentiation, dosing, CDx strategy. This is the molecule-level competitive thesis — not restating the company's BD profile.",
    "field_status": {{
      "format": "confirmed | inferred | unknown",
      "modality": "confirmed | inferred | unknown",
      "igg_subclass": "confirmed | inferred | unknown",
      "fc_engineering": "confirmed | inferred | unknown",
      "epitope": "confirmed | inferred | unknown",
      "affinity_kd": "confirmed | inferred | unknown",
      "differentiation_claim": "confirmed | inferred | unknown"
    }},
    "confidence": "high (published papers, CT.gov) | medium (press release, conference abstract) | low (analyst report, inference)",
    "source_url": "Primary source URL for molecule data. null if no citable source."
  }}]
}}

MOLECULE FIELD STATUS RULES (CRITICAL — read before writing field_status):
- 'confirmed': field value sourced from a peer-reviewed paper, patent, CT.gov protocol, or official press release with explicit data.
- 'inferred': field value logically deduced from drug class, mechanism, or analogous compounds — NOT directly stated in a source. Example: IgG4 subclass inferred from anti-inflammatory mechanism when subclass not publicly stated.
- 'unknown': no information available from any source, public or inferred.
NEVER write 'confirmed' for a value that is inferred from class effects. If IgG subclass or Fc engineering is not explicitly stated in a public source, use 'inferred'. This is enforced — the dashboard will display the status badge prominently.

RULES:
- drug_updates: only drugs from DRUGS list (exact drug_id). EVERY drug in the DRUGS list must have an entry.
- molecule_updates: one entry per drug in the DRUGS list. REQUIRED fields: format, modality, differentiation_claim, field_status (all keys present). field_status must accurately reflect whether each value is confirmed/inferred/unknown — never write 'confirmed' for inferred values.
- trial_updates: only trials from TRIALS list (exact trial id). Include an entry for EVERY trial where you can provide at least one non-null field — a study acronym, updated status, updated primary_completion_date, estimand, or results_note. Skip a trial only if you have nothing new to add for any of those fields.
- new_trials: use this to seed trials that are NOT already in the TRIALS list above. Only include trials you are confident exist on ClinicalTrials.gov (verified NCT ID). drug_id must exactly match a drug_id in the DRUGS list. Never fabricate NCT IDs. IMPORTANT: Do NOT assume the TRIALS list is complete. Actively search for earlier Phase 1 and Phase 2 trials (including completed and terminated studies) that preceded the current program — a drug in Phase 3 almost certainly ran a Phase 1 and/or Phase 2 first, and those trials may have published results that are not yet in the TRIALS list. The presence of active Phase 3 trials does NOT mean earlier trials have been captured. Only return [] if you have verified through web search that no additional trials exist for these drugs.
- catalysts: only upcoming events (after {TODAY}). ONE entry per distinct event — do NOT duplicate: if multiple trials share the same primary completion date, create ONE catalyst entry for that readout, not one per trial. Deduplicate by event type + approximate date.
- deal_updates: only match to EXISTING DEALS
- combination_programs: include ALL known multi-drug combination programs for this company in this area. If none exist or are being studied, return an empty array [].
- news_items: extract the 3-6 most significant recent news items from WEB INTELLIGENCE. Only include items with a verified source_url. If WEB INTELLIGENCE is empty, return []. Never fabricate articles. Prefer items from the past 12 months. Each item must have a real URL.
- Return ONLY valid JSON. No markdown.
- ALWAYS apply DATA QUALITY STANDARDS from the system prompt: IL-23p19 notation, brand name format, PCD specificity, validated URLs.

STRATEGIC ROLE GUIDANCE (apply to every drug in drug_updates):
Every drug must receive a strategic_role. Think about it from Ailux's BD perspective:
- direct_competitor: mechanistically overlaps with Ailux's TL1A×IL-23p19 bispecific (e.g., another anti-TL1A, another TL1A-based bispecific)
- franchise_anchor: the dominant approved or late-stage asset the company's IBD/disease-area revenue strategy is built around (e.g., Skyrizi is AbbVie's IBD anchor)
- combination_asset: a drug specifically being evaluated in combination with another drug in the same disease area
- same_space_defense: same indication as Ailux's target space but mechanistically unrelated — commercially important but not a direct mechanistic threat (e.g., Rinvoq for AbbVie)
- platform_expansion: an early or future program that extends the company's franchise into new mechanisms
- watch: early-stage or uncertain relevance

DISPLAY NAME GUIDANCE (CRITICAL — apply to every acquired/licensed drug):
- If a drug was acquired or in-licensed, display_name MUST be ONLY the acquirer's current name — no parentheticals, no old name.
- Format: "AcquirerCode" ONLY — e.g. "ABBV-701", "JNJ-2113". Do NOT write "ABBV-701 (FG-M701)".
- If the brand name exists: "BrandName (INN)" — e.g. "Skyrizi (risankizumab)".
- The old name belongs in licensor_code (e.g. "FG-M701") and licensor_name (originating company, e.g. "FutureGen Biopharmaceutical Co., Ltd."). The dashboard uses these fields to surface "formerly [licensor_code]" in the detail view automatically — never repeat the old name in display_name.
- NEVER leave display_name null or equal to the drug_id when the drug has a licensor — this creates inaccurate data.

ACQUIRED / RENAMED DRUG DETECTION (CRITICAL — prevents cross-company duplicates):
A drug may appear in the literature under two completely different names when one company acquires a program from another and renames it. Classic patterns:
- Pharma code → INN: "PF-07261271" → "afimkibart" (Pfizer originated; Roche renamed after Telavant acquisition)
- Licensor code → acquirer code: "FG-M701" → "ABBV-701" (FutureGen originated; AbbVie in-licensed and re-coded)
- Partnership/JV rename: "RVT-3101" (Telavant JV) = "RO7790121" = "afimkibart" (Roche INN)

When you identify such a renaming event for a drug belonging to this company:
1. Set licensor_code = the ORIGINAL code used by the prior owner (e.g. "PF-07261271")
2. Set licensor_name = the full legal name of the originating company (e.g. "Pfizer / Telavant Holdings (Roivant Sciences JV)")
3. Set partner_company = the SHORT recognizable name of the originating company (e.g. "Pfizer") — this is what renders in the "w/ X" pill on the dashboard
4. Set partnership_type = "licensed_in" for in-licensing, "acquired" for outright acquisition
5. Set display_name = the CURRENT acquirer code ONLY (no old name in parentheses)

IMPORTANT: If you find that a drug in this company's portfolio is a renamed/acquired version of a drug that another company already has in the database, do NOT create a second entry for the originating company. The lead developer (the company running the trials) is the canonical owner; the originating company's code goes in licensor_code.

COMBINATION PROGRAM GUIDANCE:
Identify ALL known combination programs for this company in this area. Include:
- Ongoing combination trials (two drugs being studied together)
- Company-disclosed combination development plans
- Rational combinations the company is known to be building toward (clearly stated in press releases or investor materials)
Do NOT include speculative combos. If no combinations exist, return []. Combinations appear in the dashboard alongside standalone drugs — the label should be clear and short enough to read in a dropdown (e.g., "Skyrizi + ABBV-382 combo").

CRITICAL DISTINCTION — bispecific ≠ combination:
A bispecific antibody (e.g., RO7837195: IL-23p40 × TL1A) is a SINGLE MOLECULE that hits two targets simultaneously. It is NOT a combination program. Write it as a standalone drug_updates entry with its bispecific target notation. Do NOT put it in combination_programs.
A combination program involves two or more SEPARATE drugs administered together (e.g., Skyrizi + ABBV-382).
A co-developed drug (two companies developing one molecule) is also a standalone drug — put the partner in partner_company, NOT in combination_programs.

STUDY ACRONYM GUIDANCE:
Companies brand their clinical programs with memorable acronyms shown on their IR pages, ECCO/DDW posters, and press releases (e.g., Spyre uses "SKYLINE" for their TL1A program, AbbVie uses "U-ACHIEVE" for upadacitinib UC trials, J&J uses "PURSUIT" for guselkumab CD). Search the WEB INTELLIGENCE and known sources. ClinicalTrials.gov sometimes includes them in identificationModule.acronym — cross-reference if present in TRIALS list.

APPROVED DRUG GUIDANCE:
For any drug where stage contains "Approved", populate approval_date, annual_revenue, patient_population, and final_endpoints. Revenue figures come from company earnings reports; patient population from analyst estimates or company disclosures; pivotal endpoints from the registrational trial publication or FDA label.

NEWS ITEMS GUIDANCE:
Extract 3-6 of the most significant recent news items found in WEB INTELLIGENCE. Prioritize:
- Phase 2/3 trial readouts with data (always high importance)
- New deals, partnerships, or licensing agreements (high if >$100M, else medium)
- FDA/regulatory approvals, BTD, Priority Review, REMS (high importance)
- New financings (medium, include amount)
- Major conference presentations with data (medium)
- Management changes, pipeline updates (low)
Only include items with a real, verifiable URL you found in WEB INTELLIGENCE. Never fabricate URLs or articles. If WEB INTELLIGENCE is empty or contains no news with verifiable links, return []."""


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


def write_step5(company_id: str, area_id: str, data: dict, ctx: dict, dry_run: bool = False):
    """Write Claude enrichment results to Supabase."""
    if dry_run:
        log(f"  [DRY RUN] {json.dumps(data, indent=2)[:400]}...", indent=1)
        return

    cp = data.get("company_profile", {})
    if cp:
        # Validate structured intelligence fields are present
        pi = cp.get("platform_intelligence") or {}
        bi = cp.get("bd_intelligence") or {}

        if not pi:
            log("  ⚠ WARNING: platform_intelligence is null — model did not follow structured schema. "
                "Check model output. Falling back to legacy text if present.", indent=1)
        else:
            # Evidence label compliance — direction bullets must start with [INFERRED],
            # assessment must start with [ASSESSED]. Log warnings, don't block writes.
            direction = pi.get("direction") or []
            for i, bullet in enumerate(direction):
                if isinstance(bullet, str) and not bullet.strip().startswith("[INFERRED]"):
                    log(f"  ⚠ DATA QUALITY: platform_intelligence.direction[{i}] missing [INFERRED] label: "
                        f"'{bullet[:80]}'", indent=1)
            assessment = pi.get("assessment") or ""
            if assessment and isinstance(assessment, str) and not assessment.strip().startswith("[ASSESSED]"):
                log(f"  ⚠ DATA QUALITY: platform_intelligence.assessment missing [ASSESSED] label: "
                    f"'{assessment[:80]}'", indent=1)
            facts = pi.get("facts") or []
            if not facts:
                log("  ⚠ DATA QUALITY: platform_intelligence.facts is empty — no factual bullets written", indent=1)

        if not bi:
            log("  ⚠ WARNING: bd_intelligence is null — model did not follow structured schema. "
                "Check model output.", indent=1)
        else:
            bd_assessments = bi.get("assessment") or []
            for i, bullet in enumerate(bd_assessments):
                if isinstance(bullet, str) and not bullet.strip().startswith("[ASSESSED]"):
                    log(f"  ⚠ DATA QUALITY: bd_intelligence.assessment[{i}] missing [ASSESSED] label: "
                        f"'{bullet[:80]}'", indent=1)

        profile_rec = {
            "company_id":       company_id,
            "area_id":          area_id,
            "last_enriched_at": NOW_ISO,
            "enriched_by":      "claude-intelligence-v2",
        }
        for field in ["platform_intelligence","bd_intelligence",
                      "platform_summary","bd_summary","key_risk","why_it_matters",
                      "vs_ailux","strategic_behavior","pipeline_url",
                      "market_cap_usd_m","cash_runway","financing_history","key_investors"]:
            if cp.get(field) is not None:
                profile_rec[field] = cp[field]
        # Patch-or-insert: avoid duplicate rows (no UNIQUE constraint in DB yet)
        existing = sb_get("company_profiles", {
            "company_id": f"eq.{company_id}",
            "area_id":    f"eq.{area_id}",
            "select":     "company_id",
            "limit":      "1",
        })
        if existing:
            ok = sb_patch("company_profiles", profile_rec,
                          {"company_id": f"eq.{company_id}", "area_id": f"eq.{area_id}"})
            log(f"  company_profiles: {'✓ patched' if ok else '✗ patch failed'}", indent=1)
        else:
            result = sb_upsert("company_profiles", profile_rec)
            log(f"  company_profiles: {'✓ inserted' if result else '✗ insert failed'}", indent=1)

    # Pre-validate drug IDs: fetch actual IDs in DB so we catch Claude hallucinating non-existent ones
    db_drug_ids = {d["id"] for d in sb_get("drugs", {"company_id": f"eq.{company_id}", "select": "id"})}

    # canonical_drug_id lookup for drug_area_scores parallel write (P1-D)
    _canon_map: dict = {d["id"]: d.get("canonical_drug_id") for d in ctx.get("drugs", []) if d.get("id")}

    # Area-specific fields that belong in drug_area_scores (in addition to drugs table)
    _AREA_SCORE_FIELDS = {"overlap", "overlap_rationale", "cls", "vs_ailux", "area_fit"}

    for du in data.get("drug_updates", []):
        drug_id = du.pop("drug_id", None)
        if not drug_id:
            log("  drug_updates entry missing drug_id — skipping", indent=1)
            continue
        if drug_id not in db_drug_ids:
            log(f"  WARNING: Claude returned unknown drug_id '{drug_id}' (not in DB for {company_id}) — skipping", indent=1)
            log(f"    Valid IDs are: {sorted(db_drug_ids)}", indent=2)
            continue
        update_fields = {k: v for k, v in du.items() if v is not None}
        # strategic_role must always be written, even if it's the first enrichment
        if "strategic_role" in du and du["strategic_role"] is None:
            update_fields.pop("strategic_role", None)  # skip null roles
        if update_fields:
            ok = sb_patch("drugs", update_fields, {"id": f"eq.{drug_id}"})
            role = update_fields.get("strategic_role", "")
            summary_preview = (update_fields.get("drug_summary") or "")[:60]
            log(f"  drug {drug_id} [{role}]: {'✓' if ok else '✗'} | summary: {summary_preview!r}", indent=1)

            # ── P1-D: Parallel write to drug_area_scores ──────────────────────
            # Write area-specific competitive fields to the normalised table so
            # multi-area drugs accumulate per-area scores without overwriting.
            _das_payload = {
                k: update_fields[k] for k in _AREA_SCORE_FIELDS if k in update_fields
            }
            if _das_payload:
                _das_rec = {
                    "drug_id":            drug_id,
                    "canonical_drug_id":  _canon_map.get(drug_id),
                    "area_id":            area_id,
                    "last_enriched_at":   NOW_ISO,
                }
                # Map vs_ailux → vs_ailux_positioning (column name differs in drug_area_scores)
                if "vs_ailux" in _das_payload:
                    _das_rec["vs_ailux_positioning"] = _das_payload.pop("vs_ailux")
                _das_rec.update(_das_payload)
                _das_existing = sb_get("drug_area_scores", {
                    "drug_id": f"eq.{drug_id}",
                    "area_id": f"eq.{area_id}",
                    "select":  "drug_id",
                    "limit":   "1",
                })
                if _das_existing:
                    sb_patch("drug_area_scores", _das_rec,
                             {"drug_id": f"eq.{drug_id}", "area_id": f"eq.{area_id}"})
                else:
                    sb_upsert("drug_area_scores", _das_rec)
                log(f"    drug_area_scores [{area_id}]: overlap={_das_rec.get('overlap','—')} cls={_das_rec.get('cls','—')}", indent=2)

            # ── partner_company guard — must be set for all non-self deals ──────
            pt_written = update_fields.get("partnership_type") or du.get("partnership_type")
            pc_written = update_fields.get("partner_company") or du.get("partner_company")
            if pt_written and pt_written != 'self' and not pc_written:
                log(f"  ⚠ DATA QUALITY: drug '{drug_id}' has partnership_type='{pt_written}' "
                    f"but partner_company is null — pill will not render. "
                    f"Set partner_company to the short originator name (e.g. 'Simcere', 'FutureGen Biopharmaceutical').", indent=1)

            # ── Acquired-drug display_name guard ─────────────────────────────
            # If drug has a licensor but display_name wasn't set (or equals drug_id),
            # this is a data quality failure — log a hard warning so it's visible in CI logs.
            licensor_code_written = update_fields.get("licensor_code") or du.get("licensor_code")
            display_name_written  = update_fields.get("display_name") or ""
            if licensor_code_written and (not display_name_written or display_name_written == drug_id):
                log(f"  ⚠ DATA QUALITY: drug '{drug_id}' has licensor_code='{licensor_code_written}' "
                    f"but display_name='{display_name_written or 'null'}' — acquirer code not set. "
                    f"Set display_name to the acquirer's name ONLY (e.g. 'ABBV-701', not 'ABBV-701 ({licensor_code_written})').", indent=1)
            # Also warn if display_name looks like "AcquirerCode (OldCode)" — old format
            elif licensor_code_written and licensor_code_written in (display_name_written or ''):
                log(f"  ⚠ DATA QUALITY: drug '{drug_id}' display_name='{display_name_written}' "
                    f"still contains the old licensor code '{licensor_code_written}'. "
                    f"Update to acquirer name only (strip the '({licensor_code_written})' suffix).", indent=1)

    # Write combination programs
    for combo in data.get("combination_programs", []):
        label = (combo.get("label") or "").strip()
        if not label:
            continue
        component_ids = combo.get("component_drug_ids") or []
        stage_val = combo.get("stage") or "Concept"
        is_planned = stage_val.startswith("Planned")
        combo_rec = {
            "company_id":            company_id,
            "area_id":               area_id,
            "label":                 label[:300],
            "component_drug_ids":    component_ids,
            "combination_type":      combo.get("combination_type") or "rational_combo",
            "stage":                 stage_val,
            "phase_display":         combo.get("phase_display"),
            "anticipated_start":     combo.get("anticipated_start"),
            "prerequisite_note":     combo.get("prerequisite_note"),
            "indication_short":      combo.get("indication_short"),
            "strategic_significance": combo.get("strategic_significance") or "medium",
            "mechanism_detail":      combo.get("mechanism_detail"),
            "drug_summary":          combo.get("drug_summary"),
            "overlap":               combo.get("overlap"),
            "overlap_rationale":     combo.get("overlap_rationale"),
            "notes":                 combo.get("notes"),
            "updated_at":            NOW_ISO,
        }
        if combo.get("source_url"):
            combo_rec["source_url"] = combo["source_url"]
        elif is_planned:
            log(f"  ⚠ combo '{label[:45]}': stage is Planned but source_url missing — data quality risk", indent=1)
        # Upsert by company + label (idempotent)
        existing = sb_get("drug_combinations", {
            "company_id": f"eq.{company_id}",
            "label":      f"eq.{label}",
            "select":     "id",
            "limit":      "1",
        })
        if existing:
            combo_id = existing[0].get("id")
            ok = sb_patch("drug_combinations", combo_rec, {"id": f"eq.{combo_id}"})
            log(f"  combo '{label[:45]}': {'✓ patched' if ok else '✗ patch failed'}", indent=1)
        else:
            result = sb_upsert("drug_combinations", combo_rec)
            log(f"  combo '{label[:45]}': {'✓ inserted' if result else '✗ insert failed'}", indent=1)

    # ── Insert net-new trials discovered by Claude ────────────────────────────
    # These are trials Claude found (via web intelligence or knowledge) that are
    # not yet in the trials table. We upsert on id (NCT number) so re-runs are safe.
    new_trials = data.get("new_trials", [])
    if new_trials:
        log(f"  new_trials to seed: {len(new_trials)}", indent=1)
    for nt in new_trials:
        nct_id = (nt.get("id") or "").strip()
        drug_id = (nt.get("drug_id") or "").strip()
        if not nct_id or not nct_id.startswith("NCT") or not drug_id:
            log(f"  ✗ skipping new_trial — missing/invalid id or drug_id: {nt}", indent=2)
            continue
        if drug_id not in db_drug_ids:
            log(f"  ✗ skipping new_trial {nct_id} — drug_id '{drug_id}' not in DB", indent=2)
            continue
        trial_rec = {
            "id":                     nct_id,
            "drug_id":                drug_id,
            "trial_name":             nt.get("trial_name") or None,
            "phase":                  nt.get("phase") or None,
            "status":                 nt.get("status") or None,
            "indication":             nt.get("indication") or None,
            "primary_completion_date": nt.get("primary_completion_date") or None,
            "study_acronym":          nt.get("study_acronym") or None,
            "source_url":             nt.get("source_url") or None,
            "estimand":               nt.get("estimand") or None,
            "results_note":           nt.get("results_note") or None,
            "area_fit":               nt.get("area_fit") or None,
        }
        # Strip None values — only send fields with actual data
        trial_rec = {k: v for k, v in trial_rec.items() if v is not None}
        ok = sb_upsert("trials", trial_rec)
        log(f"  new trial {nct_id} ({drug_id}): {'✓ inserted' if ok else '✗ failed'}", indent=2)

    for tu in data.get("trial_updates", []):
        trial_id = tu.get("trial_id")
        if not trial_id:
            continue
        update_fields = {k: v for k, v in tu.items()
                        if k != "trial_id" and v is not None}
        if update_fields:
            ok = sb_patch("trials", update_fields, {"id": f"eq.{trial_id}"})
            log(f"  trial {trial_id}: {'✓' if ok else '✗'}", indent=1)

    for cat in data.get("catalysts", []):
        sort_date = _parse_sort_date(
            cat.get("sort_date_approx") or cat.get("catalyst_date") or TODAY
        ) or TODAY
        if sort_date < TODAY:
            continue
        drug_id_raw = (cat.get("drug_id") or "").strip() or None
        cat_type    = cat.get("catalyst_type", "readout")

        # Dedup check: skip if this (company, drug, type, date) already exists
        # Mirrors the step4 pattern — the unique index uses COALESCE(drug_id,'')
        # which PostgREST cannot use as an on_conflict target, so we guard here.
        dedup_params: dict = {
            "company_id":   f"eq.{company_id}",
            "catalyst_type": f"eq.{cat_type}",
            "sort_date":    f"eq.{sort_date}",
            "select":       "id",
        }
        if drug_id_raw:
            dedup_params["drug_id"] = f"eq.{drug_id_raw}"
        else:
            dedup_params["drug_id"] = "is.null"
        if sb_get("catalysts", dedup_params):
            log(f"  catalyst '{(cat.get('label') or '')[:40]}': already exists, skipping", indent=1)
            continue

        cat_rec = {
            "catalyst_date":    cat.get("catalyst_date", ""),
            "sort_date":        sort_date,
            "label":            (cat.get("label") or "")[:200],
            "company_id":       company_id,
            "area_id":          area_id,
            "drug_id":          drug_id_raw,
            "significance":     cat.get("significance", "medium"),
            "catalyst_type":    cat_type,
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

    # Write news items to intel + intel_companies junction
    # Deduplicate by source_url — skip if already in DB
    news_written = 0
    for item in data.get("news_items", []):
        source_url = (item.get("source_url") or "").strip()
        headline   = (item.get("headline") or "").strip()
        if not source_url or not headline:
            continue  # require both — no unverified articles

        # Deduplicate: skip if source_url already exists in intel
        existing = sb_get("intel", {
            "source_url": f"eq.{source_url}",
            "select": "id",
            "limit": "1",
        })
        if existing:
            log(f"  news '{headline[:45]}': already in DB — skip", indent=1)
            continue

        # Normalize intel_type: 'financing' and 'pipeline' not yet in DB check constraint.
        # Map to nearest valid value until constraint is updated via Supabase dashboard.
        # TODO: ALTER TABLE intel DROP CONSTRAINT intel_intel_type_check;
        #       ALTER TABLE intel ADD CONSTRAINT intel_intel_type_check
        #         CHECK (intel_type IN ('data','deal','regulatory','financing',
        #                               'conference','partnership','management','pipeline'));
        _INTEL_TYPE_NORM = {"financing": "deal", "pipeline": "data"}
        _raw_type = item.get("intel_type") or "data"
        _norm_type = _INTEL_TYPE_NORM.get(_raw_type, _raw_type)

        intel_rec = {
            "intel_date":  (item.get("intel_date") or TODAY),
            "headline":    headline[:255],
            "body":        (item.get("body") or "")[:2000],
            "source_url":  source_url,
            "source_name": (item.get("source_name") or "")[:100],
            "importance":  item.get("importance") or "medium",
            "intel_type":  _norm_type,
            "verified":    True,
        }
        intel_rec["primary_company_id"] = company_id  # P1-B: spine FK for direct lookups
        result = sb_upsert("intel", intel_rec)
        if result and isinstance(result, list) and result:
            intel_id = result[0].get("id")
            if intel_id:
                # Tag to company via junction table
                sb_upsert("intel_companies", {"intel_id": intel_id, "company_id": company_id})
                news_written += 1
                log(f"  news '{headline[:45]}': ✓ saved (id={intel_id})", indent=1)
            else:
                log(f"  news '{headline[:45]}': ✗ insert returned no id", indent=1)
        else:
            log(f"  news '{headline[:45]}': ✗ insert failed", indent=1)

    if news_written:
        log(f"  → {news_written} new intel item(s) saved for {company_id}", indent=1)

    # ── Molecule Intelligence ────────────────────────────────────────────
    mol_written = write_molecule_intelligence(company_id, area_id, data, ctx, dry_run)
    if mol_written:
        log(f"  → {mol_written} molecule_intelligence row(s) upserted", indent=1)


# ══════════════════════════════════════════════════════════════════════════
# MOLECULE INTELLIGENCE WRITER
# ══════════════════════════════════════════════════════════════════════════

def write_molecule_intelligence(company_id: str, area_id: str,
                                 data: dict, ctx: dict,
                                 dry_run: bool = False) -> int:
    """Upsert molecule_intelligence rows for each drug in molecule_updates.

    Keyed on canonical_drug_id (UNIQUE) — one row per molecule, area-agnostic.
    field_status JSONB distinguishes confirmed / inferred / unknown per field.
    Returns count of rows upserted.
    """
    mol_updates = data.get("molecule_updates") or []
    if not mol_updates:
        return 0

    # Build a quick lookup: drug_id → canonical_drug_id from context drugs
    canon_map = {d["id"]: d.get("canonical_drug_id") for d in ctx.get("drugs", []) if d.get("id")}

    written = 0
    for mu in mol_updates:
        drug_id = mu.get("drug_id") or ""
        if not drug_id:
            log("  ⚠ molecule_update missing drug_id — skipped", indent=2)
            continue

        canonical_drug_id = canon_map.get(drug_id)
        if not canonical_drug_id:
            log(f"  ⚠ no canonical_drug_id for {drug_id} — skipping molecule write", indent=2)
            continue

        # Validate field_status values
        VALID_STATUS = {"confirmed", "inferred", "unknown"}
        raw_fs = mu.get("field_status") or {}
        field_status = {}
        for k, v in raw_fs.items():
            if v in VALID_STATUS:
                field_status[k] = v
            else:
                log(f"  ⚠ field_status[{k}]={v!r} invalid — defaulting to 'unknown'", indent=2)
                field_status[k] = "unknown"

        rec = {
            "canonical_drug_id":       canonical_drug_id,
            "drug_id":                 drug_id,
            "format":                  mu.get("format")                or None,
            "valency":                 mu.get("valency")               or None,
            "modality":                mu.get("modality")              or None,
            "igg_subclass":            mu.get("igg_subclass")          or None,
            "fc_engineering":          mu.get("fc_engineering")        or None,
            "epitope":                 mu.get("epitope")               or None,
            "affinity_kd":             mu.get("affinity_kd")           or None,
            "lowest_active_dose":      mu.get("lowest_active_dose")    or None,
            "lowest_active_dose_unit": mu.get("lowest_active_dose_unit") or None,
            "safety_observations":     mu.get("safety_observations")   or None,
            "differentiation_claim":   mu.get("differentiation_claim") or None,
            "field_status":            field_status,
            "confidence":              mu.get("confidence")            or None,
            "source_url":              mu.get("source_url")            or None,
            "last_enriched_at":        NOW_ISO,
            "enriched_by":             "company_enrichment.py",
        }
        # Strip Nones except field_status (always present)
        rec = {k: v for k, v in rec.items() if v is not None or k == "field_status"}

        if dry_run:
            log(f"  [dry] molecule {drug_id}: format={rec.get('format')} "
                f"modality={rec.get('modality')} "
                f"status_keys={list(field_status.keys())}", indent=2)
            written += 1
            continue

        ok = sb_upsert("molecule_intelligence", rec,
                        on_conflict="canonical_drug_id")
        if ok:
            inferred_fields = [k for k, v in field_status.items() if v == "inferred"]
            unknown_fields  = [k for k, v in field_status.items() if v == "unknown"]
            log(f"  molecule {drug_id}: ✓ upserted | "
                f"inferred={inferred_fields} unknown={unknown_fields}", indent=2)
            written += 1
        else:
            log(f"  molecule {drug_id}: ✗ upsert failed", indent=2)

    return written


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
    # RULE: "Related News" = any notable company event, not just formal BD deals.
    # Keywords expanded to capture financing rounds, press releases, regulatory news, and pipeline milestones.
    # Financing rounds (Series A/B/C, IPO, SPAC) are critical competitive signals and must be captured.
    deal_kws   = {
        # Formal BD
        "license","acqui","partner","collaborat","deal","agreement","merger",
        # Financing
        "series a","series b","series c","series d","financing","raises","raised",
        "ipo","spac","public offering","oversubscribed","valuation",
        "million","billion","$",
        # Company milestones
        "invest","phase","readout","data","approval","clearance","fda","ema","cde",
        "breakthrough","fast track","orphan","pdufa",
        # Press release markers
        "announces","announced","today announced","reports","closes","completes",
    }

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

        # Infer deal_type from headline content — displayed as badge in "Related News" panel
        # RULE: financing rounds, press releases, and clinical milestones all belong in Related News
        hl = (item.get("headline") or "").lower()
        if any(w in hl for w in ["series","financing","raises","raised","ipo","offering","valuation","oversubscribed"]):
            inferred_type = "financing"
        elif any(w in hl for w in ["acqui","merger","acquisition"]):
            inferred_type = "acquisition"
        elif any(w in hl for w in ["partner","collaborat","co-develop"]):
            inferred_type = "partnership"
        elif any(w in hl for w in ["license","licens"]):
            inferred_type = "licensing"
        elif any(w in hl for w in ["approval","approved","clearance","pdufa","fda","ema","cde"]):
            inferred_type = "regulatory"
        elif any(w in hl for w in ["readout","data","phase","trial","endpoint"]):
            inferred_type = "clinical"
        else:
            inferred_type = "news"

        deal_rec = {
            "deal_date":         deal_date,
            "deal_date_label":   deal_date_label,
            "from_company":      ctx["company"].get("name", company_id),
            "to_company":        "",
            "company_id":        company_id,
            "area_id":           area_id,
            "deal_type":         inferred_type,
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
# POST-ENRICHMENT COMPLETENESS SCORING
#
# Called after write_step5 completes. Computes a 0-100 score per company×area
# based on the actual state of data after this enrichment run, and writes:
#   company_profiles.completeness_score  — integer 0-100
#   company_profiles.missing_fields      — jsonb list of field paths that are empty
#   company_profiles.completeness_checked_at — timestamp of this scoring run
#
# Rubric (stage-aware, weights sum to 100):
#   platform_intelligence present + non-empty  → 20 pts  (always)
#   bd_intelligence present + non-empty        → 20 pts  (always)
#   drugs[*].drug_summary all populated        → 15 pts  (always)
#   drugs[*].key_data for Phase 2+ drugs       → 10 pts  (stage-gated)
#   drugs[*].mechanism_detail all populated    → 10 pts  (always)
#   ≥1 catalyst with source_url               → 10 pts  (always)
#   key_risk + why_it_matters populated        → 10 pts  (always)
#   overlap_rationale for Direct drugs         →  5 pts  (Direct competitors only)
# ══════════════════════════════════════════════════════════════════════════

def _score_company_completeness(company_id: str, area_id: str,
                                 data: dict, ctx: dict) -> dict:
    """
    Compute completeness score and missing_fields for a company×area.
    Merges newly-written data (from Claude's output) with pre-enrichment
    context (ctx) to reflect the true post-run state without an extra DB read.
    Returns {"score": int, "missing": list[str]}.
    """
    score = 0
    missing = []

    cp = data.get("company_profile", {}) or {}
    existing_profile = ctx.get("profile", {}) or {}

    # Prefer newly-written values; fall back to pre-run values
    pi           = cp.get("platform_intelligence") or existing_profile.get("platform_intelligence") or {}
    bi           = cp.get("bd_intelligence")       or existing_profile.get("bd_intelligence")       or {}
    key_risk     = (cp.get("key_risk")       or existing_profile.get("key_risk")       or "").strip()
    why_matters  = (cp.get("why_it_matters") or existing_profile.get("why_it_matters") or "").strip()

    # ── 1. platform_intelligence (20 pts) ───────────────────────────────
    pi_has_content = bool(pi.get("facts") or pi.get("direction") or pi.get("assessment"))
    if pi_has_content:
        score += 20
    else:
        missing.append("company_profiles.platform_intelligence")

    # ── 2. bd_intelligence (20 pts) ─────────────────────────────────────
    bi_has_content = bool(bi.get("transactions") or bi.get("assessment") or bi.get("profile"))
    if bi_has_content:
        score += 20
    else:
        missing.append("company_profiles.bd_intelligence")

    # ── 3-5. Drug-level fields ───────────────────────────────────────────
    # Build merged drug state: apply drug_updates on top of existing ctx drugs
    drug_updates_by_id = {}
    for du in data.get("drug_updates", []):
        did = du.get("drug_id") or ""
        if did:
            drug_updates_by_id[did] = du

    drugs = ctx.get("drugs", [])
    LATE_STAGE_KEYS = {"Phase 2", "Phase 2/Phase 3", "Phase 3", "Approved"}

    all_have_summary   = bool(drugs)   # false if no drugs at all
    all_have_mechanism = bool(drugs)
    late_stage_drugs   = []

    for drug in drugs:
        did   = drug.get("id", "")
        du    = drug_updates_by_id.get(did, {})
        stage = drug.get("stage") or ""

        drug_summary    = (du.get("drug_summary")    or drug.get("drug_summary")    or "").strip()
        mechanism_detail= (du.get("mechanism_detail") or drug.get("mechanism_detail") or "").strip()

        if not drug_summary:
            all_have_summary = False
            missing.append(f"drugs.drug_summary[{did}]")
        if not mechanism_detail:
            all_have_mechanism = False
            missing.append(f"drugs.mechanism_detail[{did}]")

        if any(p in stage for p in LATE_STAGE_KEYS):
            late_stage_drugs.append((did, du, drug))

    # 3. drug_summary (15 pts)
    if all_have_summary:
        score += 15

    # 4. key_data for Phase 2+ drugs (10 pts) — stage-gated
    if late_stage_drugs:
        all_have_key_data = True
        for (did, du, drug) in late_stage_drugs:
            key_data = (du.get("key_data") or drug.get("key_data") or "").strip()
            if not key_data:
                all_have_key_data = False
                missing.append(f"drugs.key_data[{did}]")
        if all_have_key_data:
            score += 10
    else:
        score += 10  # no late-stage drugs; stage doesn't require key_data

    # 5. mechanism_detail (10 pts)
    if all_have_mechanism:
        score += 10

    # ── 6. Catalyst with source_url (10 pts) ────────────────────────────
    existing_cats_with_url = [c for c in ctx.get("catalysts", []) if c.get("source_url")]
    new_cats_with_url      = [c for c in data.get("catalysts", [])  if c.get("source_url")]
    if existing_cats_with_url or new_cats_with_url:
        score += 10
    else:
        missing.append("catalysts.source_url")

    # ── 7. key_risk + why_it_matters (10 pts) ───────────────────────────
    if key_risk and why_matters:
        score += 10
    else:
        if not key_risk:
            missing.append("company_profiles.key_risk")
        if not why_matters:
            missing.append("company_profiles.why_it_matters")

    # ── 8. overlap_rationale for Direct drugs (5 pts) ───────────────────
    direct_drugs = [
        d for d in drugs
        if (drug_updates_by_id.get(d.get("id",""), {}).get("overlap") or d.get("overlap")) == "Direct"
    ]
    if direct_drugs:
        all_have_rationale = True
        for drug in direct_drugs:
            did = drug.get("id", "")
            du  = drug_updates_by_id.get(did, {})
            rationale = (du.get("overlap_rationale") or drug.get("overlap_rationale") or "").strip()
            if not rationale:
                all_have_rationale = False
                missing.append(f"drugs.overlap_rationale[{did}]")
        if all_have_rationale:
            score += 5
    else:
        score += 5   # no Direct drugs → requirement doesn't apply

    # ── 9. Molecule-level fields (tracked in missing_fields, no score impact) ─
    # Required: format, modality, differentiation_claim
    # Desired:  epitope, affinity_kd, fc_engineering, lowest_active_dose
    # These don't change the 0-100 company score — molecule completeness is a
    # separate dimension surfaced via research_queue.
    mol_updates_by_id = {}
    for mu in (data.get("molecule_updates") or []):
        did = mu.get("drug_id") or ""
        if did:
            mol_updates_by_id[did] = mu

    MOL_REQUIRED = ["format", "modality", "differentiation_claim"]
    MOL_DESIRED  = ["epitope", "affinity_kd", "fc_engineering", "lowest_active_dose"]

    for drug in drugs:
        did = drug.get("id", "")
        mu  = mol_updates_by_id.get(did, {})
        # Check required molecule fields
        for field in MOL_REQUIRED:
            val = (mu.get(field) or "").strip() if isinstance(mu.get(field), str) else mu.get(field)
            if not val:
                missing.append(f"molecule_intelligence.{field}[{did}]")
        # Check desired molecule fields (only flag if field_status shows 'unknown')
        fs = mu.get("field_status") or {}
        for field in MOL_DESIRED:
            if fs.get(field) == "unknown" or (field not in fs and not mu.get(field)):
                missing.append(f"molecule_intelligence.{field}[{did}]")

    tier = "strong" if score >= 70 else ("partial" if score >= 40 else "thin")
    return {"score": score, "tier": tier, "missing": list(dict.fromkeys(missing))}


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
                model="claude-sonnet-4-6", max_tokens=8192,
                system=ENRICHMENT_SYSTEM,
                messages=[{"role": "user", "content": prompt}]
            )
            text = resp.content[0].text
            cost = (resp.usage.input_tokens / 1e6 * 3.0 +
                    resp.usage.output_tokens / 1e6 * 15.0)
            finish = getattr(resp, 'stop_reason', None)
            log(f"  {resp.usage.input_tokens}in / {resp.usage.output_tokens}out (${cost:.4f}) stop={finish}", indent=1)
            # Detect truncation — if stop_reason is max_tokens, the JSON is incomplete
            if finish == 'max_tokens':
                log("  WARNING: response truncated at max_tokens — JSON will be incomplete, retrying is unlikely to help. Increase max_tokens or shorten prompt.", indent=1)
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

    write_step5(company_id, area_id, data, ctx, dry_run)

    # POST-ENRICHMENT COMPLETENESS SCORING
    log("  Completeness scoring...", indent=1)
    cs = _score_company_completeness(company_id, area_id, data, ctx)
    c_score  = cs["score"]
    c_tier   = cs["tier"]
    c_missing = cs["missing"]
    log(f"  Score: {c_score}/100 ({c_tier}) | {len(c_missing)} missing field(s)", indent=1)
    if c_missing:
        log(f"    Missing: {', '.join(c_missing[:8])}", indent=2)
    if not dry_run:
        # Write score + missing_fields to company_profiles
        # Profile row must exist (just written above) — safe to patch
        ok = sb_patch("company_profiles", {
            "completeness_score":      c_score,
            "missing_fields":          c_missing,
            "completeness_checked_at": NOW_ISO,
        }, {"company_id": f"eq.{company_id}", "area_id": f"eq.{area_id}"})
        if not ok:
            log("  ⚠ completeness score patch failed — profile row may not exist yet", indent=1)

    # STEP 6: Deal intelligence
    log("STEP 6 — Deal intelligence...", indent=1)
    deals = step6_deal_intelligence(company_id, area_id, ctx, company_map, dry_run,
                                    resolver=resolver)
    log(f"  {deals} new deals", indent=1)

    return True


# ══════════════════════════════════════════════════════════════════════════
# RECONCILIATION — post-run cleanup for an area
#
# Runs after all enrichment is complete. Two jobs:
#
# Job A — Stale removal:
#   Any company in company_areas that has ZERO drugs (in drug_areas) AND
#   ZERO combo programs (in drug_combinations) for this area gets removed
#   from company_areas. They disappear from the PI table automatically.
#   Safe: company + drug records are NOT deleted — only the area link.
#
# Job B — Ghost entity detection:
#   Companies in this area with the same ticker but different IDs are flagged.
#   This catches any sub-entities that slipped past the improved resolver.
#   Logs them clearly so they can be merged manually or auto-merged in future.
#
# Skipped when company_filter is set (targeted runs don't reconcile the whole area).
# ══════════════════════════════════════════════════════════════════════════

def reconcile_company_areas(area_id: str, dry_run: bool = False) -> dict:
    """Post-run reconciliation for a disease area."""
    log(f"\n── Reconciliation: area={area_id} ──")
    results = {"stale_removed": 0, "ghost_flagged": 0}

    # All companies currently linked to this area
    ca_rows = sb_get("company_areas", {"area_id": f"eq.{area_id}", "select": "company_id"})
    all_company_ids = [r["company_id"] for r in ca_rows]
    if not all_company_ids:
        log("  No companies in area — nothing to reconcile", indent=1)
        return results

    # Which companies have drugs in this area (via drug_areas)?
    da_rows = sb_get("drug_areas", {"area_id": f"eq.{area_id}", "select": "drug_id"})
    drug_ids_in_area = {r["drug_id"] for r in da_rows}
    companies_with_drugs: set[str] = set()
    if drug_ids_in_area:
        chunk = list(drug_ids_in_area)[:300]
        drug_rows = sb_get("drugs", {
            "id": f"in.({','.join(chunk)})",
            "select": "id,company_id",
        })
        companies_with_drugs = {d["company_id"] for d in drug_rows}

    # Which companies have combo programs in this area?
    combo_rows = sb_get("drug_combinations", {
        "area_id": f"eq.{area_id}",
        "select": "company_id",
    })
    companies_with_combos = {r["company_id"] for r in combo_rows}

    companies_with_programs = companies_with_drugs | companies_with_combos

    # ── Job A: remove stale company_areas links ──────────────────────────
    stale = [cid for cid in all_company_ids if cid not in companies_with_programs]
    if stale:
        log(f"  Stale companies (no programs in '{area_id}'): {stale}", indent=1)
        for cid in stale:
            if dry_run:
                log(f"    [DRY RUN] Would remove {cid} from company_areas", indent=2)
            else:
                n = sb_delete("company_areas", {
                    "company_id": f"eq.{cid}",
                    "area_id":    f"eq.{area_id}",
                })
                log(f"    ✓ Removed {cid} from company_areas ({n} rows)", indent=2)
                results["stale_removed"] += 1
    else:
        log("  Job A: no stale companies", indent=1)

    # ── Job B: detect ghost entities (same ticker, multiple company IDs) ──
    if all_company_ids:
        co_details = sb_get("companies", {
            "id":     f"in.({','.join(all_company_ids[:150])})",
            "select": "id,name,ticker,group_id",
        })
        ticker_to_ids: dict[str, list[str]] = {}
        for co in co_details:
            t = (co.get("ticker") or "").strip().upper()
            if not t or t == "PRIVATE":
                continue
            ticker_to_ids.setdefault(t, []).append(co["id"])

        for ticker, ids in ticker_to_ids.items():
            if len(ids) > 1:
                log(f"  ⚠ Ghost entities — ticker '{ticker}' → {ids}", indent=1)
                log(f"    Action: set group_id on sub-entities to canonical ID, then re-run.", indent=2)
                results["ghost_flagged"] += 1

        if results["ghost_flagged"] == 0:
            log("  Job B: no ghost entities", indent=1)

    log(f"  Done — stale_removed={results['stale_removed']}  ghost_flagged={results['ghost_flagged']}")
    return results


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

    # STEP 1: Entity Discovery (resolver passed for cross-company collision check)
    new_entities = step1_discover_new_entities(area_id, company_map, dry_run=dry_run,
                                               resolver=run_resolver)
    log(f"Step 1 complete: {new_entities} candidates queued to discovery_queue (pending review)")

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

    # ── Check enrichment_queue for signal-triggered priority items (Tier 1 P2) ──
    # Signal monitor writes high-relevance signals here. We process queued companies
    # first so they benefit from latest signal data, then continue with the full sweep.
    queued_items = sb_get("enrichment_queue", {
        "area_id": f"eq.{area_id}",
        "status":  "eq.pending",
        "select":  "id,company_id,priority,trigger",
        "order":   "priority.desc",
        "limit":   "50",
    })
    if queued_items:
        queued_cos = [q["company_id"] for q in queued_items]
        log(f"\n⚡ enrichment_queue: {len(queued_items)} pending item(s) for {area_id}")
        for q in queued_items:
            log(f"  {q['company_id']} (priority={q['priority']}, trigger={q['trigger']})", indent=1)
        # Mark queued items as dispatched
        if not dry_run:
            for q in queued_items:
                sb_patch("enrichment_queue",
                         {"status": "dispatched", "dispatched_at": NOW_ISO},
                         {"id": f"eq.{q['id']}"})
        # Reorder: queued companies run first, then the rest (deduped)
        queued_set = set(queued_cos)
        company_ids = queued_cos + [c for c in company_ids if c not in queued_set]
    else:
        log("\n── enrichment_queue: no pending items for this area ──")

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

    # Mark dispatched enrichment_queue items as complete
    if not dry_run and queued_items:
        for q in queued_items:
            sb_patch("enrichment_queue",
                     {"status": "complete", "completed_at": NOW_ISO},
                     {"id": f"eq.{q['id']}"})
        log(f"enrichment_queue: marked {len(queued_items)} item(s) complete")

    # Reconciliation — runs only on full-area runs (not targeted --company filters).
    # Removes stale company_areas links and flags any remaining ghost entities.
    if not company_filter:
        reconcile_company_areas(area_id, dry_run=dry_run)
    else:
        log(f"\n── Reconciliation skipped (targeted run: {company_filter}) ──")


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
