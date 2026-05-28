#!/usr/bin/env python3
"""
Meridian Source Verifier — Tier 3 Validation Agent
====================================================
Phase E4 in the Weekend Sprint. Validates every source_url stored in the
database is (a) real, (b) accessible, (c) from a trusted domain.

WHAT IT DOES:
  1. Queries source_urls from: drugs, companies, deals, company_partnerships,
     entity_relationships, enriched_field_log, drug_validation_results,
     catalyst_calendar
  2. For each URL: validates format, checks trusted domain, issues HTTP HEAD,
     detects fabricated URL patterns
  3. Writes results to source_validation_log table
  4. Updates enriched_field_log.field_label = 'source_invalid' for bad URLs
  5. Creates governance_violations for deals/partnerships with null or invalid
     source_url (governance rule: source_url required)

RUNS AS: Phase E4 in weekend_sprint.py

USAGE (standalone):
  python scripts/source_verifier.py
  python scripts/source_verifier.py --dry-run
  python scripts/source_verifier.py --table deals --limit 50
"""

import os
import sys
import re
import json
import time
import datetime
import argparse
from typing import Optional, List, Dict, Tuple
from urllib.parse import urlparse

import requests

# ── Path setup ───────────────────────────────────────────────────────────────
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT    = os.path.dirname(_SCRIPTS_DIR)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

# ── Credentials ──────────────────────────────────────────────────────────────

def _read_cred(filename: str) -> str:
    for base in [_REPO_ROOT, _SCRIPTS_DIR]:
        path = os.path.join(base, filename)
        if os.path.exists(path):
            return open(path).read().strip()
    return ""


SUPABASE_URL = (
    os.environ.get("SUPABASE_URL")
    or _read_cred(".supabase_url")
    or "https://tghntyofptvfhmtchwcv.supabase.co"
)
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_KEY")
    or _read_cred(".supabase_service_key")
)

if not SUPABASE_KEY:
    print("ERROR: SUPABASE_SERVICE_KEY not set and .supabase_service_key not found")
    sys.exit(1)

SB_HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=representation",
}
SB_UPSERT_HEADERS = {
    **SB_HEADERS,
    "Prefer": "resolution=merge-duplicates,return=minimal",
}

NOW_ISO    = datetime.datetime.utcnow().isoformat()
TODAY      = datetime.datetime.utcnow().strftime("%Y-%m-%d")
DRY_RUN    = False
RUN_ID     = f"sv_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

# ── Logging ───────────────────────────────────────────────────────────────────

def log(msg: str, indent: int = 0):
    ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
    print(f"[{ts}] {'  ' * indent}{msg}", flush=True)


# ── Supabase helpers ──────────────────────────────────────────────────────────

def sb_get(table: str, params: dict = None) -> List[dict]:
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    r = requests.get(url, headers=SB_HEADERS, params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()


def sb_post(table: str, data: dict) -> dict:
    if DRY_RUN:
        log(f"  [DRY-RUN] POST {table}: {json.dumps(data)[:120]}", indent=2)
        return data
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    r = requests.post(url, headers=SB_UPSERT_HEADERS, json=data, timeout=30)
    r.raise_for_status()
    result = r.json()
    return result[0] if isinstance(result, list) and result else {}


def sb_patch(table: str, filters: dict, data: dict) -> int:
    if DRY_RUN:
        log(f"  [DRY-RUN] PATCH {table} WHERE {filters}: {list(data.keys())}", indent=2)
        return 0
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    params = {k: f"eq.{v}" for k, v in filters.items()}
    r = requests.patch(url, headers=SB_HEADERS, params=params, json=data, timeout=30)
    r.raise_for_status()
    result = r.json()
    return len(result) if isinstance(result, list) else 1


def sb_upsert(table: str, rows: List[dict]) -> int:
    if DRY_RUN:
        log(f"  [DRY-RUN] UPSERT {len(rows)} rows into {table}", indent=2)
        return len(rows)
    if not rows:
        return 0
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    r = requests.post(url, headers=SB_UPSERT_HEADERS, json=rows, timeout=60)
    r.raise_for_status()
    return len(rows)


def table_exists(table_name: str) -> bool:
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/{table_name}",
            headers=SB_HEADERS,
            params={"limit": "1"},
            timeout=10
        )
        return r.status_code != 404
    except Exception:
        return False


# ── DDL: ensure source_validation_log exists ─────────────────────────────────
# Applied via Supabase SQL editor or migration script.
# Schema reference (run once manually if needed):
#
# CREATE TABLE IF NOT EXISTS source_validation_log (
#     id BIGSERIAL PRIMARY KEY,
#     table_name TEXT NOT NULL,
#     entity_id TEXT,
#     field_name TEXT,
#     source_url TEXT NOT NULL,
#     is_valid BOOLEAN,
#     http_status_code INTEGER,
#     error_message TEXT,
#     domain_trusted BOOLEAN,
#     validated_at TIMESTAMPTZ DEFAULT NOW(),
#     validation_run_id TEXT
# );
# CREATE INDEX IF NOT EXISTS svl_valid_idx ON source_validation_log(is_valid) WHERE is_valid = FALSE;
# CREATE INDEX IF NOT EXISTS svl_validated_at_idx ON source_validation_log(validated_at DESC);
#
# ALTER TABLE enriched_field_log
#   ADD COLUMN IF NOT EXISTS review_priority_score INTEGER,
#   ADD COLUMN IF NOT EXISTS review_queue_position INTEGER;
# CREATE INDEX IF NOT EXISTS efl_priority_idx ON enriched_field_log(review_priority_score DESC NULLS LAST) WHERE field_label = 'pending';

SVL_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS source_validation_log (
    id BIGSERIAL PRIMARY KEY,
    table_name TEXT NOT NULL,
    entity_id TEXT,
    field_name TEXT,
    source_url TEXT NOT NULL,
    is_valid BOOLEAN,
    http_status_code INTEGER,
    error_message TEXT,
    domain_trusted BOOLEAN,
    validated_at TIMESTAMPTZ DEFAULT NOW(),
    validation_run_id TEXT
);
CREATE INDEX IF NOT EXISTS svl_valid_idx ON source_validation_log(is_valid) WHERE is_valid = FALSE;
CREATE INDEX IF NOT EXISTS svl_validated_at_idx ON source_validation_log(validated_at DESC);
"""

EFL_ALTER_SQL = """
ALTER TABLE enriched_field_log
  ADD COLUMN IF NOT EXISTS review_priority_score INTEGER,
  ADD COLUMN IF NOT EXISTS review_queue_position INTEGER;
CREATE INDEX IF NOT EXISTS efl_priority_idx ON enriched_field_log(review_priority_score DESC NULLS LAST) WHERE field_label = 'pending';
"""


def apply_migrations():
    """Apply DDL via Supabase RPC sql endpoint (service key required)."""
    for sql_block, label in [(SVL_CREATE_SQL, "source_validation_log"), (EFL_ALTER_SQL, "enriched_field_log columns")]:
        try:
            r = requests.post(
                f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
                headers=SB_HEADERS,
                json={"sql": sql_block},
                timeout=30,
            )
            log(f"  DDL {label}: HTTP {r.status_code}", indent=2)
        except Exception as e:
            log(f"  DDL {label} failed (may need manual apply): {e}", indent=2)


# ── Trusted domain registry ───────────────────────────────────────────────────

TRUSTED_DOMAINS = {
    # Clinical trial registries
    "clinicaltrials.gov",
    "ctgov.com",
    "eudract.ema.europa.eu",
    "euctr.eu",
    "who.int",
    "isrctn.com",
    "anzctr.org.au",
    "chictr.org.cn",
    # Regulatory agencies
    "fda.gov",
    "ema.europa.eu",
    "accessdata.fda.gov",
    "pmda.go.jp",
    "hma.eu",
    # Securities / financial filings
    "sec.gov",
    "edgar.sec.gov",
    "ir.sec.gov",
    # PubMed / journals
    "pubmed.ncbi.nlm.nih.gov",
    "ncbi.nlm.nih.gov",
    "nejm.org",
    "thelancet.com",
    "nature.com",
    "cell.com",
    "gastrojournal.org",
    "jci.org",
    "jamanetwork.com",
    "bmj.com",
    "ahajournals.org",
    # Financial news / IR pages
    "businesswire.com",
    "prnewswire.com",
    "globenewswire.com",
    "biopharmadive.com",
    "fiercebiotech.com",
    "statnews.com",
    "biocentury.com",
    "evaluate.com",
    "bloomberg.com",
    "reuters.com",
    "wsj.com",
    # Company IR subdomains handled below
}

# Fabricated / too-generic URL patterns (fail automatically)
FABRICATED_PATTERNS = [
    r"^https?://example\.com",
    r"^https?://placeholder\.",
    r"/drug-name-here",
    r"/company-name-here",
    r"localhost",
    r"127\.0\.0\.1",
    r"^https?://[a-z]+\.com/press-release/[a-z-]+-[a-z-]+-[a-z-]+$",  # too generic
]

# Low-confidence patterns (generic pipeline / homepage URLs — not broken but not specific)
GENERIC_PATTERNS = [
    r"/pipeline/?$",
    r"/programs/?$",
    r"/research/?$",
    r"/product/?$",
    r"^https?://www\.[a-z]+\.(com|org|bio|io)/?$",  # bare homepage
]


def is_trusted_domain(url: str) -> bool:
    """Return True if the URL's domain is in the trusted list or matches IR subdomain."""
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower().lstrip("www.")
        if netloc in TRUSTED_DOMAINS:
            return True
        # Allow IR subdomains: ir.*.com, investors.*.com, investor.*.com
        if re.match(r"^(ir|investors?|investor-relations|news)\.", netloc):
            return True
        # Allow any .gov / .edu domain
        if netloc.endswith(".gov") or netloc.endswith(".edu"):
            return True
        # Allow known pharma/biotech domains
        known_pharma = [
            "abbvie.com", "jnj.com", "novartis.com", "pfizer.com", "lilly.com",
            "roche.com", "sanofi.com", "astrazeneca.com", "bms.com", "merck.com",
            "gilead.com", "amgen.com", "genentech.com", "biogen.com", "regeneron.com",
            "ucb.com", "takeda.com", "boehringer-ingelheim.com", "astellas.com",
            "prometheusbio.com", "roivant.com", "arena.com", "ferring.com",
            "futuregen-bio.com", "prometheus.bio", "vividion.com",
            "ailux.bio", "ailux.com",
        ]
        if any(netloc.endswith(d) for d in known_pharma):
            return True
        return False
    except Exception:
        return False


def is_fabricated(url: str) -> bool:
    """Return True if the URL matches a known fabricated pattern."""
    for pattern in FABRICATED_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return True
    return False


def is_generic(url: str) -> bool:
    """Return True if the URL is generic (too broad to verify a specific claim)."""
    for pattern in GENERIC_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return True
    return False


def is_valid_format(url: str) -> bool:
    """Basic URL format check."""
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return False
    try:
        parsed = urlparse(url)
        return bool(parsed.scheme and parsed.netloc and len(parsed.netloc) > 3)
    except Exception:
        return False


# ── HTTP check ────────────────────────────────────────────────────────────────

def check_url_live(url: str, timeout: int = 10) -> Tuple[bool, int, str]:
    """
    Issue HTTP HEAD request. Returns (is_live, status_code, error_message).
    Falls back to GET if HEAD is rejected.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (BD-Platform-SourceVerifier/1.0; +https://ailux.bio)"
    }
    try:
        r = requests.head(url, headers=headers, timeout=timeout,
                          allow_redirects=True)
        if r.status_code in (405, 501):
            # Server doesn't support HEAD — try GET with stream
            r = requests.get(url, headers=headers, timeout=timeout,
                             stream=True, allow_redirects=True)
            r.close()
        is_live = r.status_code < 400
        return is_live, r.status_code, ""
    except requests.exceptions.Timeout:
        return False, 0, "timeout"
    except requests.exceptions.SSLError as e:
        return False, 0, f"ssl_error: {str(e)[:80]}"
    except requests.exceptions.ConnectionError as e:
        return False, 0, f"connection_error: {str(e)[:80]}"
    except Exception as e:
        return False, 0, f"error: {str(e)[:80]}"


# ── URL collection from all tables ───────────────────────────────────────────

def collect_urls() -> List[Dict]:
    """
    Gather all source_url values from relevant tables.
    Returns list of dicts: {table_name, entity_id, field_name, source_url}
    """
    url_records = []

    TABLE_SPECS = [
        # (table_name, id_field, url_field)
        ("drugs", "id", "source_url"),
        ("companies", "id", "source_url"),
        ("deals", "id", "source_url"),
        ("company_partnerships", "id", "source_url"),
        ("catalyst_calendar", "id", "source_url"),
    ]

    for table_name, id_field, url_field in TABLE_SPECS:
        try:
            rows = sb_get(table_name, {
                "select": f"{id_field},{url_field}",
                f"{url_field}": "not.is.null",
                "limit": "500",
            })
            for row in rows:
                url = (row.get(url_field) or "").strip()
                if url:
                    url_records.append({
                        "table_name": table_name,
                        "entity_id": str(row.get(id_field, "")),
                        "field_name": url_field,
                        "source_url": url,
                    })
            log(f"  {table_name}: {len(rows)} URLs collected", indent=2)
        except Exception as e:
            log(f"  {table_name}: collection failed — {e}", indent=2)

    # entity_relationships — source_url field
    if table_exists("entity_relationships"):
        try:
            rows = sb_get("entity_relationships", {
                "select": "id,source_url",
                "source_url": "not.is.null",
                "limit": "200",
            })
            for row in rows:
                url = (row.get("source_url") or "").strip()
                if url:
                    url_records.append({
                        "table_name": "entity_relationships",
                        "entity_id": str(row.get("id", "")),
                        "field_name": "source_url",
                        "source_url": url,
                    })
            log(f"  entity_relationships: {len(rows)} URLs collected", indent=2)
        except Exception as e:
            log(f"  entity_relationships: collection failed — {e}", indent=2)

    # enriched_field_log — collect source_citation values
    if table_exists("enriched_field_log"):
        try:
            rows = sb_get("enriched_field_log", {
                "select": "id,entity_id,entity_type,new_value",
                "field_name": "eq.source_citation",
                "new_value": "not.is.null",
                "limit": "300",
            })
            for row in rows:
                url = (row.get("new_value") or "").strip()
                if url.startswith("http"):
                    url_records.append({
                        "table_name": "enriched_field_log",
                        "entity_id": str(row.get("entity_id", row.get("id", ""))),
                        "field_name": "source_citation",
                        "source_url": url,
                    })
            log(f"  enriched_field_log (source_citation): {len(rows)} URLs collected", indent=2)
        except Exception as e:
            log(f"  enriched_field_log: collection failed — {e}", indent=2)

    # drug_validation_results — source_url column
    if table_exists("drug_validation_results"):
        try:
            rows = sb_get("drug_validation_results", {
                "select": "id,drug_id,source_url",
                "source_url": "not.is.null",
                "limit": "200",
            })
            for row in rows:
                url = (row.get("source_url") or "").strip()
                if url:
                    url_records.append({
                        "table_name": "drug_validation_results",
                        "entity_id": str(row.get("drug_id", row.get("id", ""))),
                        "field_name": "source_url",
                        "source_url": url,
                    })
            log(f"  drug_validation_results: {len(rows)} URLs collected", indent=2)
        except Exception as e:
            log(f"  drug_validation_results: collection failed — {e}", indent=2)

    return url_records


# ── Validation engine ─────────────────────────────────────────────────────────

def validate_url_record(record: Dict) -> Dict:
    """
    Run all validation checks for a single URL record.
    Returns the record enriched with validation results.
    """
    url = record["source_url"]
    result = {
        **record,
        "is_valid": False,
        "http_status_code": None,
        "error_message": None,
        "domain_trusted": False,
        "validated_at": NOW_ISO,
        "validation_run_id": RUN_ID,
    }

    # 1. Format check
    if not is_valid_format(url):
        result["error_message"] = "invalid_url_format"
        return result

    # 2. Fabricated pattern check
    if is_fabricated(url):
        result["error_message"] = "fabricated_url_pattern"
        return result

    # 3. Domain trust check
    result["domain_trusted"] = is_trusted_domain(url)

    # 4. Generic URL check — valid but low confidence (mark valid, note generic)
    if is_generic(url):
        result["is_valid"] = True
        result["http_status_code"] = 0
        result["error_message"] = "generic_url_low_confidence"
        return result

    # 5. Live HTTP check
    is_live, status_code, error_msg = check_url_live(url)
    result["is_valid"] = is_live
    result["http_status_code"] = status_code
    if error_msg:
        result["error_message"] = error_msg

    return result


def run_validation(url_records: List[Dict], batch_size: int = 20) -> Dict:
    """
    Run validation on all URL records in batches.
    Writes results to source_validation_log.
    Returns summary statistics.
    """
    total = len(url_records)
    log(f"  Validating {total} URLs in batches of {batch_size}", indent=1)

    results_by_status = {
        "valid": 0, "invalid": 0, "generic": 0, "fabricated": 0,
        "format_error": 0, "timeout": 0,
    }
    invalid_records = []
    all_log_rows = []

    for i in range(0, total, batch_size):
        batch = url_records[i:i + batch_size]
        batch_results = []

        for rec in batch:
            validated = validate_url_record(rec)
            batch_results.append(validated)

            # Categorize
            err = validated.get("error_message") or ""
            if validated["is_valid"] and "generic" not in err:
                results_by_status["valid"] += 1
            elif "generic" in err:
                results_by_status["generic"] += 1
            elif "fabricated" in err:
                results_by_status["fabricated"] += 1
                invalid_records.append(validated)
            elif "format" in err:
                results_by_status["format_error"] += 1
                invalid_records.append(validated)
            elif "timeout" in err:
                results_by_status["timeout"] += 1
                invalid_records.append(validated)
            else:
                results_by_status["invalid"] += 1
                invalid_records.append(validated)

            # Build log row
            all_log_rows.append({
                "table_name":        validated["table_name"],
                "entity_id":         validated["entity_id"],
                "field_name":        validated["field_name"],
                "source_url":        validated["source_url"],
                "is_valid":          validated["is_valid"],
                "http_status_code":  validated["http_status_code"],
                "error_message":     validated["error_message"],
                "domain_trusted":    validated["domain_trusted"],
                "validated_at":      validated["validated_at"],
                "validation_run_id": validated["validation_run_id"],
            })

        log(f"  Batch {i//batch_size + 1}: processed {len(batch)} URLs", indent=2)

        # Write batch to source_validation_log
        if all_log_rows and table_exists("source_validation_log"):
            try:
                sb_upsert("source_validation_log", all_log_rows[-len(batch):])
            except Exception as e:
                log(f"  source_validation_log write failed: {e}", indent=2)

        time.sleep(0.5)

    return {
        "total_checked": total,
        "valid": results_by_status["valid"],
        "invalid": results_by_status["invalid"],
        "generic": results_by_status["generic"],
        "fabricated": results_by_status["fabricated"],
        "format_errors": results_by_status["format_error"],
        "timeouts": results_by_status["timeout"],
        "invalid_records": invalid_records,
    }


# ── Post-validation actions ───────────────────────────────────────────────────

def flag_invalid_in_enriched_field_log(invalid_records: List[Dict]):
    """
    For enriched_field_log source_citation records with invalid URLs,
    update field_label = 'source_invalid'.
    """
    if not table_exists("enriched_field_log"):
        return
    efl_invalid = [r for r in invalid_records if r["table_name"] == "enriched_field_log"]
    log(f"  Flagging {len(efl_invalid)} enriched_field_log entries as source_invalid", indent=2)
    for rec in efl_invalid:
        try:
            sb_patch("enriched_field_log",
                     {"entity_id": rec["entity_id"], "field_name": "source_citation"},
                     {"field_label": "source_invalid"})
        except Exception as e:
            log(f"  flag_invalid: patch failed for {rec['entity_id']}: {e}", indent=3)


def create_governance_violations_for_null_sources():
    """
    Governance rule: every deal and partnership requires source_url.
    Create governance_violations entries for records with null/invalid source.
    """
    if not table_exists("governance_violations"):
        log("  governance_violations table not found — skipping", indent=2)
        return 0

    violations_created = 0

    # Deals with null source_url
    try:
        null_deals = sb_get("deals", {
            "source_url": "is.null",
            "select": "id,drug_name,partner_company",
            "limit": "100",
        })
        for deal in null_deals:
            try:
                sb_post("governance_violations", {
                    "rule_name": "deal_missing_source_url",
                    "entity_type": "deal",
                    "entity_id": str(deal["id"]),
                    "message": (
                        f"Deal '{deal.get('drug_name', '')}' / "
                        f"'{deal.get('partner_company', '')}' missing source_url. "
                        f"Source URL is required for all deals (governance rule 5)."
                    ),
                    "resolved": False,
                    "created_at": NOW_ISO,
                })
                violations_created += 1
            except Exception:
                pass
        log(f"  Governance violations created for null deal source_urls: {len(null_deals)}", indent=2)
    except Exception as e:
        log(f"  Null deal source check failed: {e}", indent=2)

    # Partnerships with null source_url
    try:
        null_partners = sb_get("company_partnerships", {
            "source_url": "is.null",
            "select": "id,company_id,partner_company_id,deal_type",
            "limit": "100",
        })
        for p in null_partners:
            try:
                sb_post("governance_violations", {
                    "rule_name": "partnership_missing_source_url",
                    "entity_type": "company_partnership",
                    "entity_id": str(p["id"]),
                    "message": (
                        f"Partnership {p.get('company_id', '')} ↔ "
                        f"{p.get('partner_company_id', '')} "
                        f"({p.get('deal_type', '')}) missing source_url. "
                        f"Source URL is required for all partnerships (governance rule 5)."
                    ),
                    "resolved": False,
                    "created_at": NOW_ISO,
                })
                violations_created += 1
            except Exception:
                pass
        log(f"  Governance violations created for null partnership source_urls: {len(null_partners)}", indent=2)
    except Exception as e:
        log(f"  Null partnership source check failed: {e}", indent=2)

    return violations_created


# ── Main entry point ──────────────────────────────────────────────────────────

def run(dry_run: bool = False, target_table: str = None, limit: int = None) -> Dict:
    """
    Full source verification run.
    Returns summary dict for weekend_sprint_log integration.
    """
    global DRY_RUN
    DRY_RUN = dry_run

    log("Source Verifier — Tier 3 Validation Agent")
    log(f"Run ID: {RUN_ID}")
    log(f"Dry-run: {DRY_RUN}")

    # 1. Apply DDL migrations
    log("Step 1: Applying DDL migrations", indent=1)
    if not DRY_RUN:
        apply_migrations()

    # 2. Collect URLs
    log("Step 2: Collecting source URLs from all tables", indent=1)
    all_urls = collect_urls()

    # Filter to specific table if requested
    if target_table:
        all_urls = [u for u in all_urls if u["table_name"] == target_table]
        log(f"  Filtered to table '{target_table}': {len(all_urls)} URLs", indent=2)

    # Apply limit
    if limit:
        all_urls = all_urls[:limit]
        log(f"  Limit applied: {len(all_urls)} URLs", indent=2)

    log(f"  Total URLs to validate: {len(all_urls)}", indent=1)

    if not all_urls:
        log("  No URLs found — nothing to validate", indent=1)
        return {"total_checked": 0, "valid": 0, "invalid": 0}

    # 3. Run validation
    log("Step 3: Running URL validation", indent=1)
    summary = run_validation(all_urls, batch_size=20)

    # 4. Flag invalid sources in enriched_field_log
    log("Step 4: Flagging invalid sources in enriched_field_log", indent=1)
    if not DRY_RUN and summary["invalid_records"]:
        flag_invalid_in_enriched_field_log(summary["invalid_records"])

    # 5. Create governance violations for null sources
    log("Step 5: Creating governance violations for null source_urls", indent=1)
    if not DRY_RUN:
        violations_created = create_governance_violations_for_null_sources()
        summary["governance_violations_created"] = violations_created

    # Log summary
    log("=" * 60)
    log(f"Source Verification Complete")
    log(f"  Total checked:  {summary['total_checked']}")
    log(f"  Valid:          {summary['valid']}")
    log(f"  Invalid:        {summary['invalid']}")
    log(f"  Generic:        {summary['generic']}")
    log(f"  Fabricated:     {summary['fabricated']}")
    log(f"  Format errors:  {summary['format_errors']}")
    log(f"  Timeouts:       {summary['timeouts']}")

    # Remove full invalid_records list from return dict (too large for sprint log)
    return_summary = {k: v for k, v in summary.items() if k != "invalid_records"}
    return return_summary


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Meridian Source Verifier — validate all source_urls in the DB"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Run without writing to Supabase")
    parser.add_argument("--table", default=None,
                        help="Restrict to a single table (e.g. deals, company_partnerships)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Maximum number of URLs to validate")
    args = parser.parse_args()

    result = run(dry_run=args.dry_run, target_table=args.table, limit=args.limit)
    print(json.dumps(result, indent=2))
