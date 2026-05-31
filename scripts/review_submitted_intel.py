#!/usr/bin/env python3
"""
Meridian — Submitted Intel Screening Script (Path 5 Intake)
============================================================
Processes submitted_intel rows with status='new':
  1. Validates source URL (HTTP check)
  2. Fetches and reads page content if accessible
  3. Sends url + text to Claude for entity extraction + analysis
  4. Matches extracted entities to existing Supabase records
  5. Generates: title, summary, key facts, proposed actions, confidence
  6. Updates row status → 'analyzed' or 'needs_review'

Usage:
    python3 scripts/review_submitted_intel.py          # process all new rows
    python3 scripts/review_submitted_intel.py --dry-run  # analyze but don't write back
    python3 scripts/review_submitted_intel.py --id <uuid>  # process single row

Environment (set via .env or export):
    SUPABASE_URL          https://tghntoyofptvfhmtchwcv.supabase.co
    SUPABASE_SERVICE_KEY  <service role key>
    ANTHROPIC_API_KEY     <claude api key>
"""

import os, sys, json, time, argparse, pathlib
from datetime import datetime, timezone
from typing import Optional

import requests

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR = pathlib.Path(__file__).parent.parent

def _load_key(env_var: str, file_name: Optional[str] = None) -> str:
    val = os.environ.get(env_var, "").strip()
    if val:
        return val
    if file_name:
        p = BASE_DIR / file_name
        if p.exists():
            return p.read_text().strip()
    sys.exit(f"ERROR: {env_var} not set and {file_name} not found.")

SUPABASE_URL  = os.environ.get("SUPABASE_URL", "https://tghntyofptvfhmtchwcv.supabase.co")
SERVICE_KEY   = _load_key("SUPABASE_SERVICE_KEY", ".supabase_service_key")
ANTHROPIC_KEY = _load_key("ANTHROPIC_API_KEY", ".anthropic_api_key")
CLAUDE_MODEL  = "claude-opus-4-6"

SB_HEADERS = {
    "apikey":        SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=representation",
}

# ── Supabase helpers ──────────────────────────────────────────────────────────
def sb_get(table: str, params: dict) -> list:
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}?{qs}", headers=SB_HEADERS, timeout=20)
    r.raise_for_status()
    return r.json()

def sb_patch(table: str, row_id: str, payload: dict) -> dict:
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/{table}?id=eq.{row_id}",
        headers=SB_HEADERS, json=payload, timeout=20
    )
    r.raise_for_status()
    return r.json()

def sb_list(table: str, select: str = "*") -> list:
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}?select={select}",
        headers={**SB_HEADERS, "Range": "0-9999"}, timeout=30
    )
    r.raise_for_status()
    return r.json()

# ── URL validation ────────────────────────────────────────────────────────────
def validate_url(url: str) -> tuple[str, int, str]:
    """Returns (validation_status, http_status, source_name)"""
    if not url:
        return ("unchecked", 0, "")
    try:
        resp = requests.head(url, timeout=10, allow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0 (compatible; Meridian/1.0)"})
        status = resp.status_code
        source_name = resp.url.split("/")[2] if resp.url else ""
        validation = "valid" if status < 400 else "broken"
        return (validation, status, source_name)
    except requests.exceptions.Timeout:
        return ("broken", 0, "")
    except Exception:
        return ("broken", 0, "")

def fetch_page_text(url: str, max_chars: int = 6000) -> str:
    """Fetch readable text from a URL (best effort)."""
    if not url:
        return ""
    try:
        resp = requests.get(url, timeout=15, allow_redirects=True,
                            headers={"User-Agent": "Mozilla/5.0 (compatible; Meridian/1.0)"})
        if not resp.ok:
            return ""
        content_type = resp.headers.get("Content-Type", "")
        if "text/html" not in content_type and "text/plain" not in content_type:
            return ""
        # Very light HTML stripping
        import re
        text = re.sub(r"<script[^>]*>.*?</script>", " ", resp.text, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_chars]
    except Exception:
        return ""

# ── Entity lookup ─────────────────────────────────────────────────────────────
_COMPANIES: Optional[list] = None
_DRUGS: Optional[list] = None

def load_entities():
    global _COMPANIES, _DRUGS
    if _COMPANIES is None:
        _COMPANIES = sb_list("companies", "id,name")
    if _DRUGS is None:
        _DRUGS = sb_list("drugs", "id,display_name")

def match_entity(name: str, entities: list, name_field: str) -> Optional[str]:
    """Fuzzy match a string against a list of entities. Returns id or None."""
    if not name:
        return None
    name_lc = name.lower().strip()
    for e in entities:
        primary = (e.get(name_field) or "").lower().strip()
        if name_lc == primary or name_lc in primary or primary in name_lc:
            return e["id"]
        # Aliases field removed — skip alias matching
        pass
    return None

# ── Duplicate detection ───────────────────────────────────────────────────────
import re as _re

def _kw(text: str) -> set:
    """Return meaningful keywords from a string for overlap comparison."""
    STOP = {'the','a','an','and','or','of','to','in','for','on','with','by','at',
            'from','is','are','was','were','after','before','as','that','this',
            'it','its','be','been','has','have','had','will','would','could',
            'not','but','also','than','into','about','over','per','its'}
    words = _re.sub(r'[^a-z0-9\s]', ' ', (text or '').lower()).split()
    return {w for w in words if len(w) > 2 and w not in STOP}

def _overlap(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))

def check_duplicates(url: str, submitted_text: str, extraction: Optional[dict]) -> dict:
    """
    Check four duplicate vectors before finalising status.
    Returns: { is_duplicate: bool, reasons: [str], risk: 'high'|'medium'|'low' }
    """
    reasons = []

    # 1. Same source_url already submitted (exact match, any status except rejected)
    if url:
        existing_urls = sb_get("submitted_intel", {
            "source_url": f"eq.{url}",
            "status":     "neq.rejected",
            "select":     "id,status,created_at",
        })
        # Filter to rows that aren't the current submission (can't easily exclude by id here,
        # but the caller won't pass the current row's url if it's the only one)
        if len(existing_urls) > 1:
            reasons.append(f"Same URL already submitted ({len(existing_urls)-1} prior submission(s))")

    # 2. Same extracted title already exists in submitted_intel
    title = (extraction or {}).get("extracted_title", "").strip() if extraction else ""
    if title:
        title_kw = _kw(title)
        existing_titles = sb_get("submitted_intel", {
            "status":  "neq.rejected",
            "select":  "extracted_title",
        })
        for row in existing_titles:
            t = (row.get("extracted_title") or "").strip()
            if t and t != title and _overlap(title_kw, _kw(t)) > 0.75:
                reasons.append(f"Near-identical title already in queue: \"{t[:70]}\"")
                break

    # 3. Similar company/drug event already in discovery_queue
    companies = list({c.lower() for c in (extraction or {}).get("extracted_entities", {}).get("companies", [])})
    drugs     = list({d.lower() for d in (extraction or {}).get("extracted_entities", {}).get("drugs", [])})
    if companies or drugs:
        dq_rows = sb_get("research_queue", {
            "select": "entity_name,reason",
            "limit":  "200",
        })
        for row in dq_rows:
            dq_text = " ".join(filter(None, [row.get("entity_name"), row.get("reason")])).lower()
            for co in companies:
                if co in dq_text:
                    reasons.append(f"Company \"{co}\" already has an open discovery_queue item")
                    break
            for drug in drugs:
                if drug in dq_text:
                    reasons.append(f"Drug \"{drug}\" already in discovery_queue")
                    break

    # 4. Same catalyst or deal already exists
    intel_type = (extraction or {}).get("intel_type", "")
    if intel_type in ("catalyst", "deal") and title:
        title_kw = _kw(title)
        table = "catalysts" if intel_type == "catalyst" else "deals"
        label_field = "label" if intel_type == "catalyst" else "headline"
        existing = sb_get(table, {"select": label_field, "limit": "300"})
        for row in existing:
            label = (row.get(label_field) or "").strip()
            if label and _overlap(title_kw, _kw(label)) > 0.65:
                reasons.append(f"Similar {intel_type} already in `{table}`: \"{label[:70]}\"")
                break

    # Deduplicate reasons and assign risk level
    seen, unique_reasons = set(), []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            unique_reasons.append(r)

    risk = "high" if len(unique_reasons) >= 2 else ("medium" if unique_reasons else "low")
    return {"is_duplicate": bool(unique_reasons), "reasons": unique_reasons, "risk": risk}


# ── Claude analysis ───────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a pharmaceutical business development intelligence analyst for Ailux, a biotech company.
Your job is to analyze submitted intelligence and extract structured information for the Meridian BD dashboard.

Coverage areas:
- TL1A × IL-23p19 (IBD: Crohn's, UC)
- TSLP × IL-33 (Respiratory: asthma, COPD)
- IL-4Rα × TSLP (Atopic disease: atopic dermatitis, eczema)
- IL-4Rα × OX40L (AD immune reset)
- IGF1R × TSHR (Thyroid Eye Disease)
- FcRn Bispecific (Autoimmune)
- BCMA × CD19 × CD3 (T-cell engineering, Immune Reset)

Always respond with valid JSON only. No markdown, no explanation outside JSON."""

EXTRACTION_PROMPT = """Analyze this intelligence submission and extract structured information.

SOURCE URL: {url}
SUBMITTED TEXT: {text}
PAGE CONTENT (if fetched): {page_content}

Return a JSON object with exactly these fields:
{{
  "extracted_title": "One-sentence summary of the key BD-relevant information (max 120 chars)",
  "extracted_summary": "2-4 sentences explaining what this is, why it matters for BD, and what action it implies",
  "source_type": "one of: press_release / clinical_trial / news / publication / deck / conference / regulatory / other",
  "extracted_key_facts": ["fact 1", "fact 2", "fact 3"],
  "extracted_entities": {{
    "companies": ["company name 1", "company name 2"],
    "drugs": ["drug name 1"],
    "targets": ["target 1"],
    "areas": ["tl1a|tslp|il4ra|igf1r|fcrn|tcell|general"],
    "deal_value_usd_m": null,
    "trial_ids": ["NCT..."],
    "catalysts": []
  }},
  "intel_type": "one of: company / drug / target / deal / catalyst / clinical_trial / publication / regulatory / conference / observation",
  "proposed_actions": [
    {{
      "action": "one of: add_catalyst / add_deal / update_drug / add_source / create_discovery_queue_item / add_company_note / reject_duplicate / needs_human_review",
      "table": "target table name",
      "rationale": "why this action",
      "priority": "high|medium|low"
    }}
  ],
  "confidence_level": "one of: confirmed / supported / inferred / unverified",
  "confidence_rationale": "why this confidence level",
  "bd_relevance": "high|medium|low|none",
  "duplicate_risk": "likely_duplicate|possible_duplicate|appears_unique"
}}"""

def call_claude(url: str, text: str, page_content: str) -> Optional[dict]:
    """Call Claude API and return parsed extraction JSON."""
    prompt = EXTRACTION_PROMPT.format(
        url=url or "(none)",
        text=text or "(none)",
        page_content=page_content[:3000] if page_content else "(not fetched)"
    )
    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 1500,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": prompt}]
    }
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload, timeout=60
        )
        resp.raise_for_status()
        raw = resp.json()["content"][0]["text"].strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"    ✗ Claude returned non-JSON: {e}")
        return None
    except Exception as e:
        print(f"    ✗ Claude API error: {e}")
        return None

# ── Process single row ────────────────────────────────────────────────────────
def process_row(row: dict, dry_run: bool = False) -> dict:
    row_id = row["id"]
    url    = row.get("source_url") or ""
    text   = row.get("submitted_text") or ""
    by     = row.get("submitted_by", "unknown")

    print(f"\n  ┌─ Row {row_id[:8]}… | by: {by}")
    print(f"  │  URL:  {url[:80] or '(none)'}")
    print(f"  │  Text: {text[:80] or '(none)'}")

    # Step 1: Validate URL
    val_status, http_status, source_name = validate_url(url)
    print(f"  │  URL validation: {val_status} (HTTP {http_status})")

    # Step 2: Fetch page content
    page_content = ""
    if url and val_status == "valid":
        page_content = fetch_page_text(url)
        print(f"  │  Page content: {len(page_content)} chars fetched")

    # Step 3: Claude analysis
    print(f"  │  Running Claude extraction...")
    extraction = call_claude(url, text, page_content)

    if extraction is None:
        final_status = "needs_review"
        update = {
            "status": final_status,
            "source_validation_status": val_status,
            "source_http_status": http_status,
            "source_name": source_name or None,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "review_notes": "Claude extraction failed — needs manual review",
        }
    else:
        # Step 4: Entity matching
        load_entities()
        entities = extraction.get("extracted_entities", {})
        companies_raw = entities.get("companies", [])
        drugs_raw = entities.get("drugs", [])

        matched_companies = [match_entity(c, _COMPANIES, "name") for c in companies_raw]
        matched_drugs = [match_entity(d, _DRUGS, "display_name") for d in drugs_raw]

        # Add matched IDs to extraction
        extraction["matched_company_ids"] = [c for c in matched_companies if c]
        extraction["matched_drug_ids"] = [d for d in matched_drugs if d]
        extraction["unmatched_companies"] = [companies_raw[i] for i, c in enumerate(matched_companies) if not c]
        extraction["unmatched_drugs"] = [drugs_raw[i] for i, d in enumerate(matched_drugs) if not d]

        # Step 5: Duplicate detection (runs against submitted_intel, discovery_queue, catalysts, deals)
        print(f"  │  Running duplicate check...")
        dup_result = check_duplicates(url, text, extraction)
        extraction["duplicate_check"] = dup_result
        if dup_result["reasons"]:
            for r in dup_result["reasons"]:
                print(f"  │  ⚠ Duplicate signal: {r}")

        # Step 6: Determine final status
        dup_risk_claude = extraction.get("duplicate_risk", "appears_unique")
        bd_rel = extraction.get("bd_relevance", "medium")
        conf = extraction.get("confidence_level", "unverified")

        # Route to needs_review if: Claude flagged it, our detector found signals, or BD-irrelevant
        if dup_result["risk"] == "high" or dup_risk_claude == "likely_duplicate" or bd_rel == "none":
            final_status = "needs_review"
        elif dup_result["risk"] == "medium":
            final_status = "needs_review"  # let human decide on ambiguous duplicates
        else:
            final_status = "analyzed"

        print(f"  │  Extracted: {extraction.get('extracted_title','')[:70]}")
        print(f"  │  Confidence: {conf} | BD relevance: {bd_rel} | Dup risk: {dup_result['risk']} | Status → {final_status}")

        # Prepend duplicate warnings to proposed_actions so reviewer sees them first
        proposed = list(extraction.get("proposed_actions") or [])
        if dup_result["reasons"]:
            dup_actions = [{
                "action":    "reject_duplicate",
                "table":     "submitted_intel",
                "rationale": reason,
                "priority":  "high" if dup_result["risk"] == "high" else "medium",
            } for reason in dup_result["reasons"]]
            proposed = dup_actions + proposed

        update = {
            "status":                    final_status,
            "source_validation_status":  val_status,
            "source_http_status":        http_status,
            "source_name":               source_name or extraction.get("source_name") or None,
            "source_type":               extraction.get("source_type"),
            "extracted_title":           extraction.get("extracted_title"),
            "extracted_summary":         extraction.get("extracted_summary"),
            "extracted_key_facts_json":  extraction.get("extracted_key_facts"),
            "extracted_entities_json":   extraction.get("extracted_entities"),
            "proposed_actions_json":     proposed or None,
            "confidence_level":          conf,
            "analyzed_at":               datetime.now(timezone.utc).isoformat(),
        }

    # Step 6: Write back
    if dry_run:
        print(f"  └─ [DRY RUN] Would update row to status={update['status']}")
    else:
        try:
            sb_patch("submitted_intel", row_id, update)
            print(f"  └─ ✓ Updated → status={update['status']}")
        except Exception as e:
            print(f"  └─ ✗ Failed to update: {e}")

    return update

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Screen submitted intel rows")
    parser.add_argument("--dry-run",  action="store_true", help="Analyze without writing back")
    parser.add_argument("--id",       type=str,            help="Process single row by UUID")
    parser.add_argument("--limit",    type=int, default=20, help="Max rows to process (default 20)")
    args = parser.parse_args()

    print("=" * 60)
    print("Meridian — Submitted Intel Screening")
    print(f"Model: {CLAUDE_MODEL} | Dry run: {args.dry_run}")
    print("=" * 60)

    if args.id:
        rows = sb_get("submitted_intel", {"id": f"eq.{args.id}", "select": "*"})
    else:
        rows = sb_get("submitted_intel", {
            "status": "eq.new",
            "select": "*",
            "order": "created_at.asc",
            "limit": str(args.limit),
        })

    if not rows:
        print("\nNo new rows to process.")
        return

    print(f"\nFound {len(rows)} row(s) to process.")
    processed = 0
    for row in rows:
        process_row(row, dry_run=args.dry_run)
        processed += 1
        if processed < len(rows):
            time.sleep(1)  # rate limit courtesy pause

    print(f"\n{'─'*60}")
    print(f"Done. Processed {processed} row(s).")

if __name__ == "__main__":
    main()
