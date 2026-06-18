#!/usr/bin/env python3
"""
Shared base layer for the company_enrichment split (§3 large-file refactor).
============================================================================
Extracted verbatim from company_enrichment.py. This is the bottom of the
dependency star: every company/* feature module imports from here, and nothing
here imports from a feature module (no cycles).

Holds the cross-cutting primitives:
  - credentials + the Anthropic LLM client + run-token accounting
  - Supabase REST headers/URL and the sb_get/sb_upsert/sb_post/sb_delete/sb_patch
    helpers (+ _catalyst_upsert single-writer drop-in, update_system_status)
  - log(), area-id normalization, the known-drug-target guard table
  - source-URL validation + post-LLM confidence-constraint enforcement

NOTE (deferred, supervised): routing the sb_* writes through the src/meridian/database
writers/client is the documented next step — it changes write behavior, so it must be
dispatch-verified (company-enrichment --dry-run). For now these are a verbatim relocation.
"""

import os
import sys
import json
import time
import datetime
import re
from typing import Optional, List

import requests
import anthropic


# ══════════════════════════════════════════════════════════════════════════
# CREDENTIALS + SETUP
# ══════════════════════════════════════════════════════════════════════════

# repo root: this file is src/meridian/enrichment/company/common.py → 5 dirnames up.
_WORKSPACE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))


def _read_key(env, filename, default=""):
    """Credential read, tolerant for CI/tests: env var first, then the repo-root file,
    then default (never raises) so feature submodules import test-clean without secrets."""
    if os.environ.get(env, "").strip():
        return os.environ[env].strip()
    try:
        with open(os.path.join(_WORKSPACE, filename)) as f:
            return f.read().strip()
    except FileNotFoundError:
        return default


ANTHROPIC_API_KEY  = _read_key("ANTHROPIC_API_KEY", ".anthropic_api_key")
SUPABASE_URL       = _read_key("SUPABASE_URL", ".supabase_url", "https://tghntyofptvfhmtchwcv.supabase.co")
SUPABASE_KEY       = _read_key("SUPABASE_SERVICE_KEY", ".supabase_service_key")

# Guarded: the SDK raises on an empty api_key, which would break test-clean imports.
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

# ── Token accounting (Wave 1: enrichment_runs token columns were always 0) ────
# Module-level so it accumulates across every LLM call in a run (discovery, web,
# molecule, synthesis, coverage). Written to enrichment_runs at run end → spend
# becomes computable (tokens × model price).
_RUN_TOKENS = {"in": 0, "out": 0}

def _acc_tokens(resp):
    try:
        _RUN_TOKENS["in"]  += getattr(resp.usage, "input_tokens", 0) or 0
        _RUN_TOKENS["out"] += getattr(resp.usage, "output_tokens", 0) or 0
    except Exception:
        pass

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

# ── Valid area IDs — must match TAB_AREA_MAP keys in the frontend ────────────
VALID_AREA_IDS = {"tl1a", "tslp", "il4ra", "fcrn", "igf1r", "tcell"}

# Area-ID normalization: fix common LLM/typo variants before any validation
_AREA_ID_ALIASES: dict[str, str] = {
    "tll1a":   "tl1a",   # extra 'l' typo
    "tl1":     "tl1a",
    "il4r":    "il4ra",
    "il-4ra":  "il4ra",
    "il4-ra":  "il4ra",
    "fcrna":   "fcrn",
    "fcRn":    "fcrn",
    "igf-1r":  "igf1r",
    "igf1":    "igf1r",
    "t-cell":  "tcell",
}

def normalize_area_id(raw: str) -> str:
    """Lowercase, strip whitespace, apply alias map.  Returns '' if unrecognised."""
    cleaned = raw.strip().lower()
    resolved = _AREA_ID_ALIASES.get(cleaned, cleaned)
    return resolved if resolved in VALID_AREA_IDS else ""

# ── Known drug-alias table (prevents LLM confusing similar assets) ───────────
KNOWN_DRUG_TARGETS: dict[str, dict] = {
    # Akeso bispecifics — do NOT mix up
    "AK104":  {"target": "PD-1/CTLA-4",  "stage": "Approved",  "note": "cadonilimab; China approved 2022 for cervical cancer"},
    "AK112":  {"target": "PD-1/VEGF",    "stage": "Phase 3",   "note": "ivonescimab"},
    "AK129":  {"target": "PD-1/TIM-3",   "stage": "Phase 1",   "note": "distinct from AK104; do NOT conflate"},
    # JAK inhibitors — selectivity matters
    "SHR0302":   {"target": "JAK1-selective", "stage": "Phase 3",   "note": "ivarmacitinib; JAK1-selective, NOT dual JAK1/JAK2"},
    "baricitinib":{"target": "JAK1/JAK2",    "stage": "Approved",  "note": "dual JAK1/JAK2 inhibitor"},
    "ruxolitinib":{"target": "JAK1/JAK2",    "stage": "Approved",  "note": "dual JAK1/JAK2 inhibitor"},
    "upadacitinib":{"target": "JAK1-selective","stage":"Approved",  "note": "rinvoq; JAK1-selective"},
    "filgotinib": {"target": "JAK1-selective","stage": "Approved",  "note": "JAK1-selective"},
    "abrocitinib":{"target": "JAK1-selective","stage": "Approved",  "note": "cibinqo; JAK1-selective"},
    # Novamab (Shanghai Novamab Biopharmaceuticals) — LQ-prefix programs
    # CRITICAL: LQ080 ≠ ZW191. ZW191 is a Zymeworks FRα-targeting ADC for oncology — completely unrelated.
    # LQ-prefix drugs belong to Novamab (company_id=novamab), NOT LaNova (lanova).
    "LQ080":  {"target": "TL1A×IL-23p19",       "stage": "Phase 1",      "company": "novamab", "note": "Novamab VHH bispecific for IBD; DO NOT alias with ZW191 (unrelated Zymeworks FRα ADC for oncology)"},
    "LQ082":  {"target": "TL1A×IL-23p19×α4β7",  "stage": "Preclinical",  "company": "novamab", "note": "Novamab trispecific for IBD; LQ-prefix = Novamab not LaNova"},
}

# ── Oncology / Immunology target sets for catalog_category inference ──────────
# catalog_category logic centralized in meridian.enrichment.catalog_category
import sys as _s_cc, pathlib as _pl_cc
for _p_cc in _pl_cc.Path(__file__).resolve().parents:
    if (_p_cc/'meridian'/'enrichment').is_dir(): _s_cc.path.insert(0,str(_p_cc)); break
    if (_p_cc/'src'/'meridian'/'enrichment').is_dir(): _s_cc.path.insert(0,str(_p_cc/'src')); break
from meridian.enrichment.catalog_category import infer_catalog_category


def validate_source_url(url: str, context: str = "", head_check: bool = True) -> Optional[str]:
    """
    P0+P1 source URL validation gate. Called before storing any source_url.

    Checks:
    1. Format validation — must start with http, not obviously truncated
    2. Generic URL detection — pipeline/homepage URLs don't support specific claims → warn
    3. HTTP HEAD check (when head_check=True) — reject 404 / timeout; keep 30x redirects
    4. Hallucination patterns — flag impossible NCT numbers, malformed domains

    Returns:
      - The original URL if valid
      - None if the URL is malformed, broken (404), or times out (so caller stores null)
    Logs a warning in all rejection cases so failures are auditable.
    """
    import urllib.request as _urlreq
    import urllib.error as _urlerr

    if not url:
        return None
    url = url.strip()

    # ── 1. Format check ──────────────────────────────────────────────────────
    if not url.startswith("http"):
        log(f"  ⚠ E7 [{context}]: source_url rejected — does not start with http: {url[:80]}", indent=2)
        return None

    # Detect truncated URLs (ends mid-word, common enrichment artifact)
    if len(url) > 80 and not url.endswith(('/', '.html', '.pdf', '.htm', '.json')) \
            and url[-1].isalpha() and url[-2].isalpha():
        log(f"  ⚠ E7 [{context}]: source_url appears truncated → rejecting: {url[:80]}", indent=2)
        return None

    # ── 2. Hallucination patterns ─────────────────────────────────────────────
    # NCT numbers must be exactly 8 digits
    nct_match = re.search(r'NCT(\d+)', url)
    if nct_match and len(nct_match.group(1)) != 8:
        log(f"  ⚠ E7 [{context}]: malformed NCT number ({nct_match.group(0)}) → rejecting: {url[:80]}", indent=2)
        return None

    # ── 3. Generic URL warning (don't reject, but warn loudly) ───────────────
    GENERIC_PATTERNS = [
        (r'/pipeline/?$',          "generic pipeline page"),
        (r'/programs/?$',          "generic programs page"),
        (r'/news-releases/?$',     "generic news releases index"),
        (r'/press-releases/?$',    "generic press releases index"),
        (r'\.com/?$',              "company homepage"),
        (r'\.com/en/?$',           "company homepage"),
    ]
    for pattern, label in GENERIC_PATTERNS:
        if re.search(pattern, url, re.I):
            log(f"  ⚠ E7 [{context}]: source_url is a {label} (not claim-specific): {url[:80]}", indent=2)
            # Don't reject — generic URLs are weak evidence but not false. Caller decides confidence.
            return url  # return early, skip HTTP check for generic pages

    # ── 4. HTTP HEAD check ───────────────────────────────────────────────────
    if head_check:
        ua = {"User-Agent": "Mozilla/5.0 (compatible; BD-Platform-Audit/1.0)"}
        try:
            req = _urlreq.Request(url, method="HEAD", headers=ua)
            with _urlreq.urlopen(req, timeout=6) as r:
                status = r.status
        except _urlerr.HTTPError as e:
            if e.code == 405:
                # HEAD not allowed — try GET
                try:
                    req2 = _urlreq.Request(url, method="GET", headers=ua)
                    with _urlreq.urlopen(req2, timeout=6) as r2:
                        status = r2.status
                except _urlerr.HTTPError as e2:
                    status = e2.code
                except Exception:
                    status = 0
            else:
                status = e.code
        except Exception:
            status = 0  # timeout or DNS failure

        if status == 404 or status == 410:
            log(f"  ⚠ E7 [{context}]: source_url returns HTTP {status} → nulling: {url[:80]}", indent=2)
            return None
        if status == 0:
            log(f"  ⚠ E7 [{context}]: source_url unreachable (timeout/DNS) → nulling: {url[:80]}", indent=2)
            return None
        if status not in (200, 201, 301, 302, 303, 307, 308, 403, 405):
            log(f"  ⚠ E7 [{context}]: source_url returned unexpected HTTP {status}: {url[:80]}", indent=2)
            # Unusual status — warn but don't reject (may be geo-blocked, behind login, etc.)

    return url


def enforce_confidence_constraints(record: dict, context: str = "") -> dict:
    """
    Post-LLM invariant enforcement for confidence_level fields. (E6)

    Rule 1: confidence='confirmed' requires source_url IS NOT NULL → demote to 'supported'
    Rule 2: source_type='inferred' → confidence cannot be 'confirmed' or 'supported' → demote to 'inferred'
    Rule 3: confidence='supported' requires source_url IS NOT NULL → warn (do not demote)
            Supported rows are in the source_coverage scoring denominator (v1.2+).
            A supported row without source_url will reduce the source_coverage score.
    Rule 4 (E7): source_url must pass format + HTTP validation before storage.
            Broken/malformed/truncated URLs are nulled; confidence demoted accordingly.

    Modifies record in place and returns it. Called before every drug_area_scores write
    so that LLM-assigned confidence values are sanitised before persistence.
    """
    confidence  = record.get("confidence_level") or "inferred"
    source_url  = (record.get("source_url") or "").strip()
    source_type = (record.get("source_type") or "").lower().strip()

    # Rule 4 (E7): validate source_url before applying confidence rules
    # Use head_check=False for CT.gov ct_study URLs (format is already authoritative)
    # Use head_check=True for all other URLs (press releases, company IR, etc.)
    if source_url:
        is_ct_study = bool(re.search(r'clinicaltrials\.gov/study/NCT\d{8}$', source_url))
        validated_url = validate_source_url(source_url, context=context, head_check=not is_ct_study)
        if validated_url != source_url:
            # URL was rejected or modified
            record["source_url"] = validated_url  # None if rejected
            source_url = validated_url or ""
            if not source_url and confidence == "confirmed":
                log(f"  ⚠ E7→E6 [{context}]: source_url rejected → demoting confirmed→supported", indent=2)
                record["confidence_level"] = "supported"
                confidence = "supported"
            elif not source_url and confidence == "supported":
                log(f"  ⚠ E7→E6 [{context}]: source_url rejected → demoting supported→inferred", indent=2)
                record["confidence_level"] = "inferred"
                confidence = "inferred"

    if confidence == "confirmed" and not source_url:
        log(f"  ⚠ E6 [{context}]: confidence='confirmed' but source_url is null → demoting to 'supported'", indent=2)
        record["confidence_level"] = "supported"
        confidence = "supported"

    if source_type == "inferred" and confidence in ("confirmed", "supported"):
        log(f"  ⚠ E6 [{context}]: source_type='inferred' but confidence='{confidence}' → demoting to 'inferred'", indent=2)
        record["confidence_level"] = "inferred"

    # Rule 3: warn if supported + no source_url (affects source_coverage score)
    if confidence == "supported" and not source_url:
        log(f"  ⚠ E6-R3 [{context}]: confidence='supported' but source_url is null — "
            f"this will reduce source_coverage score. Add source_url or demote to 'inferred'.", indent=2)

    return record


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


def _catalyst_upsert(rec):
    """Single-writer drop-in (ADR-010) for sb_upsert('catalysts', ...).
    Routes through CatalystWriter; preserves list-on-success / [] contract."""
    import sys, pathlib as _pl
    _b = _pl.Path(__file__).resolve().parents[4]   # repo root from src/meridian/enrichment/company/
    for _p in (str(_b / "src" / "meridian" / "database"), str(_b / "scripts")):
        if _p not in sys.path:
            sys.path.insert(0, _p)
    from catalyst_writer import CatalystWriter
    _r = CatalystWriter().upsert(rec)
    return [] if _r.get("errors") else [{"id": _r.get("catalyst_id")}]


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


def update_system_status(pipeline_label: str, record_count: int = 0,
                         note: Optional[str] = None) -> bool:
    """Stamp the system_status singleton so the dashboard knows fresh data arrived.

    Powers the S3 "New intelligence available — refresh" banner. Sets the
    timestamp column matching the pipeline (enrichment vs research), bumps
    updated_at, and records how many rows were touched. Best-effort: a failure
    here must never break a pipeline run.
    """
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    rec = {
        "updated_at": now_iso,
        "last_pipeline_label": pipeline_label,
        "updated_record_count": int(record_count or 0),
    }
    _col = {
        "research":   "last_research_at",
        "meridian":   "last_meridian_at",
        "scoring":    "last_scoring_at",
        "enrichment": "last_enrichment_at",
    }.get(pipeline_label, "last_enrichment_at")
    rec[_col] = now_iso
    if note:
        rec["note"] = note[:500]
    try:
        ok = sb_patch("system_status", rec, {"id": "eq.1"})
        if ok:
            log(f"  system_status stamped ({pipeline_label}, {record_count} records)", indent=1)
        else:
            log(f"  system_status stamp returned no match (table missing?)", indent=1)
        return ok
    except Exception as e:
        log(f"  system_status stamp failed (non-fatal): {e}", indent=1)
        return False


# ══════════════════════════════════════════════════════════════════════════
# AREA LABELS — descriptive per-area search/labeling strings (shared by the
# discovery and catalyst modules).
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
