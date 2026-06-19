#!/usr/bin/env python3
"""
process_queue_item.py
Executes the research action for a Discovery Queue item (research_queue table).

Routes each item to one of three handlers:
  Route 1 — CT.gov trial search  (context_type contains 'trial', or action mentions CT.gov)
  Route 2 — Drug field enrichment (action mentions 'mechanism', 'target', 'mapping', or
             context_type == 'never_enriched')
  Route 3 — PubMed PK/PD extraction (reason contains PMID, or context_type == 'pkpd_literature')

Usage:
  python3 scripts/process_queue_item.py --id <queue_item_id>
  python3 scripts/process_queue_item.py --batch --limit 5   # top 5 pending by priority_score
  python3 scripts/process_queue_item.py --batch --limit 20  # larger batch

Environment:
  SUPABASE_URL, SUPABASE_SERVICE_KEY (or auto-loaded from .supabase_service_key)
  ANTHROPIC_API_KEY (or auto-loaded from .anthropic_api_key)
"""

import os
import sys
import json
import argparse
import re
import time
import datetime
from typing import Optional

import requests
import anthropic

# ── Credential loading ─────────────────────────────────────────────────────────
# Support both env-var and file-based credentials (same as company_enrichment.py)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_DIR   = os.path.dirname(os.path.dirname(os.path.dirname(_SCRIPT_DIR)))

def _read_file_key(filename: str) -> Optional[str]:
    path = os.path.join(_REPO_DIR, filename)
    if os.path.exists(path):
        return open(path).read().strip() or None
    return None

SUPABASE_URL = os.environ.get("SUPABASE_URL") or "https://tghntyofptvfhmtchwcv.supabase.co"
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_KEY")
    or _read_file_key(".supabase_service_key")
    or ""
)
ANTHROPIC_KEY = (
    os.environ.get("ANTHROPIC_API_KEY")
    or _read_file_key(".anthropic_api_key")
    or ""
)

if not SUPABASE_KEY:
    print("ERROR: SUPABASE_SERVICE_KEY not set and .supabase_service_key not found")
    sys.exit(1)
if not ANTHROPIC_KEY:
    print("ERROR: ANTHROPIC_API_KEY not set and .anthropic_api_key not found")
    sys.exit(1)

client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

SB_H = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
}
BASE = f"{SUPABASE_URL}/rest/v1"
NOW_ISO = datetime.datetime.utcnow().isoformat()


# ── Logging ────────────────────────────────────────────────────────────────────
def log(msg: str):
    print(f"  {msg}", flush=True)


# ── Supabase helpers ───────────────────────────────────────────────────────────
def sb_get(table: str, params: dict) -> list:
    try:
        r = requests.get(f"{BASE}/{table}", headers=SB_H, params=params, timeout=20)
        return r.json() if r.status_code == 200 else []
    except Exception as e:
        log(f"[sb_get {table}] {e}")
        return []


# ── Dry-run gate ──────────────────────────────────────────────────────────────
# The --dry-run flag was previously parsed but never honored (the script wrote
# regardless). All DB writes funnel through sb_patch / sb_post / insert_trials,
# which now short-circuit when dry-run is set.
_RUNTIME = {"dry_run": False}
def set_dry_run(value: bool) -> None:
    _RUNTIME["dry_run"] = bool(value)
def is_dry_run() -> bool:
    return _RUNTIME["dry_run"]


def sb_patch(table: str, params: dict, payload: dict) -> bool:
    if is_dry_run():
        log(f"[DRY-RUN] PATCH {table} {params}")
        return True
    try:
        r = requests.patch(f"{BASE}/{table}", headers=SB_H, params=params, json=payload, timeout=20)
        return r.status_code in (200, 204)
    except Exception as e:
        log(f"[sb_patch {table}] {e}")
        return False


def sb_post(table: str, payload, prefer: str = "return=minimal") -> bool:
    if is_dry_run():
        log(f"[DRY-RUN] POST {table}")
        return True
    try:
        h = {**SB_H, "Prefer": prefer}
        r = requests.post(f"{BASE}/{table}", headers=h, json=payload, timeout=20)
        return r.status_code in (200, 201)
    except Exception as e:
        log(f"[sb_post {table}] {e}")
        return False


# ── Queue helpers ──────────────────────────────────────────────────────────────
def get_item(item_id: str) -> Optional[dict]:
    rows = sb_get("research_queue", {"id": f"eq.{item_id}", "select": "*", "limit": "1"})
    return rows[0] if rows else None


def mark_resolved(item_id: str, summary: str):
    ok = sb_patch(
        "research_queue",
        {"id": f"eq.{item_id}"},
        {
            "assigned_status": "resolved",
            "next_best_action": f"DONE: {summary[:200]}",
            "last_action_at":  NOW_ISO,
        },
    )
    if not ok:
        log(f"WARNING: failed to mark {item_id} resolved")


def mark_processing(item_id: str):
    sb_patch(
        "research_queue",
        {"id": f"eq.{item_id}"},
        {"assigned_status": "processing", "last_action_at": NOW_ISO},
    )


# ══════════════════════════════════════════════════════════════════════════════
# ROUTE 1 — ClinicalTrials.gov search
# ══════════════════════════════════════════════════════════════════════════════

def search_ctgov(drug_name: str, company_name: Optional[str] = None) -> list:
    """Search ClinicalTrials.gov API v2 for trials matching this drug."""
    query = drug_name
    if company_name and company_name != drug_name:
        query = f"{drug_name} {company_name}"
    try:
        r = requests.get(
            "https://clinicaltrials.gov/api/v2/studies",
            params={"query.term": query, "pageSize": 10, "format": "json"},
            timeout=25,
        )
        if r.status_code != 200:
            log(f"CT.gov returned HTTP {r.status_code}")
            return []
        studies = r.json().get("studies", [])
        results = []
        for s in studies:
            proto  = s.get("protocolSection", {})
            ident  = proto.get("identificationModule", {})
            status = proto.get("statusModule", {})
            design = proto.get("designModule", {})
            phases = design.get("phases", [])
            results.append({
                "nct_id":     ident.get("nctId"),
                "title":      (ident.get("briefTitle") or "")[:200],
                "phase":      str(phases[0]) if phases else "",
                "status":     status.get("overallStatus", ""),
                "start_date": (status.get("startDateStruct") or {}).get("date"),
            })
        return results
    except Exception as e:
        log(f"CT.gov search error: {e}")
        return []


def insert_trials(drug_id: str, trials: list) -> int:
    """Update the trial_registries ClinicalTrials.gov row for this drug.

    The table has a unique constraint on (drug_id, registry_name), so there is
    exactly one row per registry per drug. We PATCH the existing row with the
    best NCT ID found, trial count, and search_status='found'. If no row exists
    yet, we POST to create it.

    Returns 1 if any write succeeded, 0 otherwise.
    """
    if not trials:
        return 0

    # Pick the best trial: prefer Phase 3 > Phase 2 > Phase 1 > any
    def phase_rank(t):
        p = t.get("phase", "")
        if "3" in p: return 0
        if "2" in p: return 1
        if "1" in p: return 2
        return 3

    best = sorted([t for t in trials if t.get("nct_id")], key=phase_rank)
    if not best:
        return 0

    top = best[0]
    payload = {
        "registry_id":  top["nct_id"],
        "registry_url": f"https://clinicaltrials.gov/study/{top['nct_id']}",
        "search_status": "found",
        "trial_count":  len(trials),
        "last_searched_at": NOW_ISO,
    }

    if is_dry_run():
        log(f"[DRY-RUN] would write trial_registries for {drug_id}: {top['nct_id']} ({len(trials)} trials)")
        return 1

    # Try PATCH first (row likely already exists from backfill_v35)
    try:
        r = requests.patch(
            f"{BASE}/trial_registries",
            headers=SB_H,
            params={"drug_id": f"eq.{drug_id}", "registry_name": "eq.ClinicalTrials.gov"},
            json=payload,
            timeout=20,
        )
        if r.status_code in (200, 204):
            log(f"PATCHED trial_registries for {drug_id}: {top['nct_id']} ({len(trials)} trials)")
            return 1
    except Exception as e:
        log(f"PATCH trial_registries error: {e}")

    # Row doesn't exist — POST
    try:
        row = {"drug_id": drug_id, "registry_name": "ClinicalTrials.gov", **payload}
        r = requests.post(f"{BASE}/trial_registries", headers=SB_H, json=row, timeout=20)
        if r.status_code in (200, 201):
            log(f"POST trial_registries for {drug_id}: {top['nct_id']}")
            return 1
        else:
            log(f"trial_registries POST {r.status_code}: {r.text[:120]}")
            return 0
    except Exception as e:
        log(f"POST trial_registries error: {e}")
        return 0


def best_phase(phases: list) -> str:
    if any("3" in p for p in phases):
        return "Phase 3"
    if any("2" in p for p in phases):
        return "Phase 2"
    if any("1" in p for p in phases):
        return "Phase 1"
    return ""


def handle_ctgov(item: dict) -> list:
    entity_name = item.get("entity_name") or ""
    entity_id   = item.get("entity_id") or ""
    company_id  = item.get("company_id") or ""

    log("Route: CT.gov trial search")
    trials = search_ctgov(entity_name, company_id)
    log(f"Found {len(trials)} trials for '{entity_name}'")

    actions = []
    if not trials:
        return actions

    if entity_id:
        # Try to find the actual drug ID from entity_id (may be a company ID)
        # entity_id in research_queue can be either drug ID or company ID
        drug_rows = sb_get("drugs", {"id": f"eq.{entity_id}", "select": "id,stage", "limit": "1"})
        if not drug_rows:
            # entity_id is probably a company ID — look for their drugs
            drug_rows = sb_get(
                "drugs",
                {"company_id": f"eq.{entity_id}", "select": "id,stage", "limit": "10"},
            )

        for drug in drug_rows:
            did = drug["id"]
            inserted = insert_trials(did, trials)
            log(f"Inserted {inserted} trial records for drug {did}")
            if inserted:
                actions.append(f"Found {len(trials)} CT.gov trials, inserted {inserted} for {did}")

            # Advance stage from Preclinical only
            phases = [t["phase"] for t in trials if t.get("phase")]
            if phases:
                bp = best_phase(phases)
                if bp and drug.get("stage") in ("Preclinical", "preclinical", None, ""):
                    from meridian.database import update_drug
                    ok = update_drug(did, {"stage": bp})
                    if ok:
                        actions.append(f"Stage advanced to {bp} from CT.gov evidence")
    else:
        actions.append(f"Found {len(trials)} trials (no entity_id — cannot link to drug)")

    return actions


# ══════════════════════════════════════════════════════════════════════════════
# ROUTE 2 — Drug field enrichment via Claude
# ══════════════════════════════════════════════════════════════════════════════

_DRUG_ENRICH_SYSTEM = """You are Meridian, a pharmaceutical intelligence assistant for Ailux Biotherapeutics.
Ailux is developing ALX001, a TL1A×IL-23p19 bispecific antibody for IBD.
When researching competitor drugs, apply a competitive lens focused on:
- Mechanism of action and molecular target(s)
- Clinical stage and key differentiators vs existing therapies
- Relevance to Ailux's TL1A and IL-23 bispecific program

Respond only with valid JSON — no markdown, no prose, no code fences."""


def enrich_drug_fields(drug_id: str, drug_name: str, context: str) -> dict:
    """Use Claude Sonnet to fill missing drug fields."""
    prompt = f"""Research the pharmaceutical drug "{drug_name}" for the Meridian BD intelligence platform.

Context from Meridian database: {context}

Return a JSON object with these fields. Use null for any field you cannot determine with reasonable confidence — do NOT hallucinate.

{{
  "target": "molecular target(s), e.g. 'TL1A × IL-23p19' or 'PD-1'. Single string.",
  "mechanism": "2–3 sentence mechanistic description covering receptor binding, downstream pathway, and functional outcome.",
  "differentiation_thesis": "1–2 sentence statement of what makes this drug unique vs the class.",
  "ailux_angle": "1–2 sentence relevance to Ailux's TL1A×IL-23p19 bispecific program — competitive threat, complementary asset, or partner opportunity.",
  "drug_summary": "3–4 sentence overview: what it is, who makes it, current stage, key clinical data.",
  "stage": "one of: Preclinical | Phase 1 | Phase 2 | Phase 3 | NDA Filed | Approved",
  "indication_short": "primary indication(s), e.g. 'UC, CD' or 'TED' or 'Atopic dermatitis'"
}}"""

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1200,
            system=_DRUG_ENRICH_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        # Strip code fences if model wrapped the JSON
        if "```" in raw:
            raw = re.sub(r"```(?:json)?", "", raw).strip()
        return json.loads(raw)
    except json.JSONDecodeError as e:
        log(f"Claude JSON parse error: {e}")
        return {}
    except Exception as e:
        log(f"Claude API error: {e}")
        return {}


def handle_drug_enrichment(item: dict) -> list:
    entity_id   = item.get("entity_id") or ""
    entity_name = item.get("entity_name") or ""
    area_id     = item.get("area_id") or ""
    context_type = item.get("context_type") or ""
    missing_fields = item.get("missing_fields") or []

    log("Route: Drug field enrichment (Claude Sonnet)")

    # Resolve drug ID — entity_id may be a company ID
    drug_rows = sb_get("drugs", {"id": f"eq.{entity_id}", "select": "*", "limit": "1"})
    if not drug_rows:
        # entity_id is a company — enrich all their area drugs
        drug_rows = sb_get(
            "drugs",
            {"company_id": f"eq.{entity_id}", "select": "*", "limit": "20"},
        )

    if not drug_rows:
        log(f"No drugs found for entity_id={entity_id}")
        return [f"No drugs found for entity {entity_id}"]

    actions = []
    for drug in drug_rows:
        did   = drug["id"]
        dname = drug.get("name") or drug.get("display_name") or did
        context = (
            f"area={area_id}, "
            f"stage={drug.get('stage') or 'unknown'}, "
            f"company={drug.get('company_id') or 'unknown'}, "
            f"context_type={context_type}, "
            f"missing_fields={missing_fields[:5]}"
        )

        enriched = enrich_drug_fields(did, dname, context)
        if not enriched:
            log(f"No enrichment data returned for {dname}")
            continue

        # Only write fields that are currently null/empty in the DB
        update = {}
        NULLABLE_FIELDS = [
            "target", "mechanism", "differentiation_thesis",
            "ailux_angle", "drug_summary",
        ]
        for field in NULLABLE_FIELDS:
            if enriched.get(field) and not drug.get(field):
                update[field] = enriched[field]

        # Stage: only advance, never overwrite an existing non-null stage
        if enriched.get("stage") and not drug.get("stage"):
            update["stage"] = enriched["stage"]

        # indication_short: fill if empty
        if enriched.get("indication_short") and not drug.get("indication_short"):
            update["indication_short"] = enriched["indication_short"]

        update["last_synced_date"] = datetime.datetime.utcnow().strftime("%Y-%m-%d")

        if update:
            from meridian.database import update_drug
            ok = update_drug(did, update)
            if ok:
                filled = [k for k in update if k != "last_synced_date"]
                log(f"Updated {dname}: {filled}")
                actions.append(f"Filled {filled} for {dname}")
            else:
                log(f"PATCH failed for {dname}")
        else:
            log(f"No new fields to write for {dname} (all already populated)")
            actions.append(f"All fields already present for {dname}")

    return actions


# ══════════════════════════════════════════════════════════════════════════════
# ROUTE 3 — PubMed PK/PD extraction
# ══════════════════════════════════════════════════════════════════════════════

def fetch_pubmed_abstract(pmid: str) -> str:
    """Fetch abstract text from PubMed eutils."""
    try:
        r = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
            params={"db": "pubmed", "id": pmid, "rettype": "abstract", "retmode": "text"},
            timeout=20,
        )
        return r.text[:3000] if r.status_code == 200 else ""
    except Exception as e:
        log(f"PubMed fetch error: {e}")
        return ""


def extract_pk_with_claude(drug_name: str, abstract_text: str) -> dict:
    """Use Claude Haiku to extract PK parameters from an abstract."""
    prompt = f"""Extract pharmacokinetic (PK) parameters from this clinical or preclinical abstract for the drug "{drug_name}".

Return only valid JSON — no prose, no markdown:
{{
  "half_life_h": null,
  "half_life_unit": "h",
  "dose_route": null,
  "cmax_value": null,
  "cmax_unit": null,
  "bioavailability_pct": null,
  "species": "human",
  "confidence": 0.0
}}

Rules:
- half_life_h: numeric value only (convert to hours if given in days: multiply by 24)
- dose_route: "IV" | "SC" | "IM" | "oral" | "topical" | null
- species: "human" | "monkey" | "mouse" | "rat" | "dog"
- confidence: 0.0–1.0 (how confident you are this data is in the abstract)
- Use null for fields not mentioned in the abstract

Abstract:
{abstract_text[:2500]}"""

    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        if "```" in raw:
            raw = re.sub(r"```(?:json)?", "", raw).strip()
        return json.loads(raw)
    except Exception as e:
        log(f"PK extraction error: {e}")
        return {}


def handle_pkpd(item: dict) -> list:
    entity_id   = item.get("entity_id") or ""
    entity_name = item.get("entity_name") or ""
    reason      = item.get("reason") or ""

    log("Route: PubMed PK/PD extraction")

    pmid_match = re.search(r"PMID\s*:?\s*(\d+)", reason, re.IGNORECASE)
    if not pmid_match:
        log("No PMID found in reason field — cannot proceed")
        return ["No PMID in reason field"]

    pmid = pmid_match.group(1)
    log(f"Fetching PMID {pmid}")
    abstract = fetch_pubmed_abstract(pmid)
    if not abstract:
        log("PubMed returned empty abstract")
        return [f"PubMed abstract empty for PMID {pmid}"]

    log(f"Abstract fetched ({len(abstract)} chars)")
    pk = extract_pk_with_claude(entity_name, abstract)
    log(f"PK extracted: {pk}")

    if not pk or pk.get("confidence", 0) < 0.5:
        return [f"Low confidence PK extraction for PMID {pmid} (conf={pk.get('confidence', 0):.2f})"]

    # Resolve drug ID
    drug_rows = sb_get("drugs", {"id": f"eq.{entity_id}", "select": "id", "limit": "1"})
    if not drug_rows:
        drug_rows = sb_get(
            "drugs",
            {"company_id": f"eq.{entity_id}", "select": "id", "limit": "1"},
        )
    if not drug_rows:
        return [f"Cannot find drug for entity_id={entity_id}"]

    did = drug_rows[0]["id"]

    # Choose the most informative parameter to store
    if pk.get("half_life_h"):
        param_type  = "half_life"
        value       = pk["half_life_h"]
        unit        = pk.get("half_life_unit", "h")
    elif pk.get("cmax_value"):
        param_type  = "cmax"
        value       = pk["cmax_value"]
        unit        = pk.get("cmax_unit") or "ng/mL"
    elif pk.get("bioavailability_pct"):
        param_type  = "bioavailability"
        value       = pk["bioavailability_pct"]
        unit        = "%"
    else:
        return [f"No numeric PK value extracted from PMID {pmid}"]

    pk_row = {
        "drug_id":        did,
        "parameter_type": param_type,
        "value_numeric":  value,
        "unit":           unit,
        "dose_route":     pk.get("dose_route"),
        "species":        pk.get("species", "human"),
        "source_type":    "abstract",
        "source_url":     f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "confidence_score": pk.get("confidence", 0.6),
    }

    ok = sb_post("drug_pk_parameters", pk_row, prefer="return=minimal")
    if ok:
        log(f"Inserted PK row: {param_type}={value}{unit} from PMID {pmid}")
        return [f"Extracted {param_type}={value}{unit} from PMID {pmid}"]
    else:
        return [f"PK row insert failed for PMID {pmid}"]


# ══════════════════════════════════════════════════════════════════════════════
# ROUTER — dispatch to correct handler
# ══════════════════════════════════════════════════════════════════════════════

def _classify_route(item: dict) -> str:
    """Determine which handler to invoke."""
    context_type = (item.get("context_type") or "").lower()
    action       = (item.get("next_best_action") or "").lower()
    reason       = (item.get("reason") or "").lower()

    # Route 3: explicit PK/PD or PMID signal
    if (
        "pmid" in reason
        or "pubmed" in reason
        or "pk/pd" in context_type
        or "pkpd" in context_type
        or "pk_" in context_type
    ):
        return "pkpd"

    # Route 1: trial / CT.gov signal
    if (
        "ct.gov" in action
        or "clinical trial" in action
        or "ctgov" in action
        or "trial" in context_type
        or ("trial" in action and "run" in action)
    ):
        return "ctgov"

    # Route 2: drug field enrichment
    if (
        "mapping" in action
        or "mechanism" in action
        or "target" in action
        or "enrichment" in action
        or context_type == "never_enriched"
        or "drug mapping" in action
        or "run full" in action
    ):
        return "drug_enrich"

    # Default: drug enrichment (most common gap type)
    return "drug_enrich"


def process_item(item: dict) -> list:
    """Route queue item to appropriate handler. Returns list of action strings."""
    item_id      = item["id"]
    entity_name  = item.get("entity_name") or item.get("entity_id") or "unknown"

    print(
        f"\n[{NOW_ISO[:19]}] Processing: {entity_name}"
        f" | ctx={item.get('context_type')} | P={item.get('priority_score')}",
        flush=True,
    )
    log(f"Action hint: {str(item.get('next_best_action', ''))[:80]}")

    mark_processing(item_id)

    route = _classify_route(item)
    log(f"Route selected: {route}")

    try:
        if route == "ctgov":
            actions = handle_ctgov(item)
        elif route == "pkpd":
            actions = handle_pkpd(item)
        else:
            actions = handle_drug_enrichment(item)
    except Exception as e:
        log(f"FATAL handler error: {e}")
        actions = [f"Handler error: {e}"]

    summary = "; ".join(actions) if actions else "No new data found — item reviewed"
    mark_resolved(item_id, summary)
    log(f"Resolved: {summary[:120]}")
    return actions


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Meridian — Execute a Discovery Queue (research_queue) item"
    )
    parser.add_argument("--id",    help="Process a single queue item by UUID")
    parser.add_argument("--batch", action="store_true",
                        help="Process top N pending items by priority_score")
    parser.add_argument("--limit", type=int, default=5,
                        help="Number of items to process in batch mode (default: 5)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Classify and log routes only — no Supabase writes")
    args = parser.parse_args()
    set_dry_run(args.dry_run)

    if args.id:
        item = get_item(args.id)
        if item:
            process_item(item)
        else:
            print(f"ERROR: Item {args.id} not found in research_queue")
            sys.exit(1)

    elif args.batch:
        pending = sb_get(
            "research_queue",
            {
                "assigned_status": "eq.pending",
                "select": "*",
                "order": "priority_score.desc",
                "limit": str(args.limit),
            },
        )
        print(f"\nBatch: processing {len(pending)} pending item(s) (limit={args.limit})")
        total_actions = 0
        for item in pending:
            actions = process_item(item)
            total_actions += len(actions)
            time.sleep(2)   # rate-limit Claude + CT.gov calls
        print(f"\nDone: {len(pending)} items processed, {total_actions} actions taken")

    else:
        parser.print_help()
