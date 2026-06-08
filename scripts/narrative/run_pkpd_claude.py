#!/usr/bin/env python3
"""
Standalone runner for the Claude-powered PK/PD extractor.
Reads all pkpd_literature items from research_queue and reprocesses with Claude.

Usage:
  ANTHROPIC_API_KEY=... SUPABASE_URL=... SUPABASE_SERVICE_KEY=... python3 scripts/run_pkpd_claude.py
"""

import os, sys, json, datetime, time, re, requests

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from _common import load_credentials, log  # noqa: E402
import _db  # noqa: E402
import ai.client as ai_client  # noqa: E402
from ai.client import PromptConfig  # noqa: E402

SUPABASE_URL, SUPABASE_KEY, ANTHROPIC_API_KEY = load_credentials()
_db.init_db(SUPABASE_URL, SUPABASE_KEY)
ai_client.setup(ANTHROPIC_API_KEY)

PKPD_CLAUDE_MODEL = "claude-haiku-4-5-20251001"

_PKPD_CFG = PromptConfig(
    name="pkpd_extraction",
    system="",
    model=PKPD_CLAUDE_MODEL,
    max_tokens=512,
)

PKPD_EXTRACTION_PROMPT = """\
Extract PK/PD parameters from this abstract. Return JSON only — no markdown, no explanation.
Use null for any field not mentioned. Confidence should reflect how clearly the value appears
(1.0 = explicit numeric in results section, 0.5 = approximate or inferred, 0.0 = not found).

{
  "half_life_h": null,
  "half_life_unit": null,
  "cmax_value": null,
  "cmax_unit": null,
  "auc_value": null,
  "auc_unit": null,
  "bioavailability_pct": null,
  "vd_value": null,
  "vd_unit": null,
  "clearance_value": null,
  "clearance_unit": null,
  "route": null,
  "species": null,
  "confidence": 0.0
}

Rules:
- half_life_unit: use "h" for hours, "d" for days, "wk" for weeks
- route: MUST be exactly ONE of: "SC", "IV", "oral", or null — never a combination like "SC/IV"
  If multiple routes are studied, pick the PRIMARY route or null
- species: "human", "mouse", "monkey", "rat", or null
- If half_life_h is given in days in the abstract, convert to hours (multiply by 24) and set half_life_unit="h"
- Only extract values explicitly stated — do not infer or estimate
- confidence above 0.5 means the abstract explicitly reports the parameter with a numeric value

Abstract:
{abstract_text}"""


def fetch_pubmed_abstract(pmid, timeout=10):
    try:
        url = (
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            f"?db=pubmed&id={pmid}&rettype=abstract&retmode=text"
        )
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Meridian-BD/1.0"})
        if resp.status_code == 200:
            return resp.text
    except Exception as exc:
        log(f"  PubMed fetch error (PMID {pmid}): {exc}")
    return ""


def extract_pk_with_claude(abstract_text):
    if not abstract_text or len(abstract_text.strip()) < 50:
        return {}
    abstract_trimmed = abstract_text[:4000]
    prompt = PKPD_EXTRACTION_PROMPT.replace("{abstract_text}", abstract_trimmed)
    result = ai_client.run_json(_PKPD_CFG, prompt)
    parsed = result.data
    if not parsed:
        return {}
    try:
        confidence = float(parsed.get("confidence", 0.0))
        if confidence <= 0.5:
            return {}
        result = {}
        if parsed.get("half_life_h") is not None:
            result["half_life_hours"] = float(parsed["half_life_h"])
        if parsed.get("bioavailability_pct") is not None:
            result["bioavailability_pct"] = float(parsed["bioavailability_pct"])
        if parsed.get("cmax_value") is not None:
            result["cmax_ng_ml"] = float(parsed["cmax_value"])
        if parsed.get("auc_value") is not None:
            result["auc_inf_ng_hr_ml"] = float(parsed["auc_value"])
        if parsed.get("vd_value") is not None:
            result["volume_distribution_l"] = float(parsed["vd_value"])
        if parsed.get("clearance_value") is not None:
            result["clearance_ml_hr_kg"] = float(parsed["clearance_value"])
        # dose_route: only allow SC, IV, oral — reject combined strings like "SC/IV"
        route_val = str(parsed.get("route") or "").strip()
        if route_val in ("SC", "IV", "oral"):
            result["dose_route"] = route_val
        # species is not a db column — embed in notes
        if parsed.get("species"):
            result["_species"] = str(parsed["species"])
        result["_confidence"] = confidence
        return result
    except Exception as exc:
        log(f"    Claude PK extraction error: {exc}")
        return {}


def main():
    log("--- Phase 7: PK/PD queue processor (Claude-powered) ---")
    queue_items = _db.sb_get("research_queue", {
        "context_type": "eq.pkpd_literature",
        "select": "id,entity_id,reason,assigned_status",
        "limit": "100",
    })
    log(f"  Found {len(queue_items)} PK/PD queue items (all statuses)")

    processed = 0
    pk_written = 0
    NOW_ISO = datetime.datetime.utcnow().isoformat()

    for item in queue_items:
        item_id = item["id"]
        drug_id = item.get("entity_id", "")
        reason = item.get("reason", "")
        pmid_match = re.search(r"PMID\s+(\d+)", reason)
        if not pmid_match:
            log(f"  No PMID for {drug_id}: {reason[:60]}")
            _db.sb_patch("research_queue", {"assigned_status": "completed"}, {"id": f"eq.{item_id}"})
            processed += 1
            continue

        pmid = pmid_match.group(1)
        source_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        log(f"  Processing {drug_id} — PMID {pmid}")
        time.sleep(0.4)

        abstract = fetch_pubmed_abstract(pmid)
        if not abstract:
            log(f"    No abstract for PMID {pmid}")
        else:
            pk_params = extract_pk_with_claude(abstract)
            confidence = pk_params.pop("_confidence", 0.0)
            species_note = pk_params.pop("_species", None)
            if pk_params:
                log(f"    Claude extracted (conf={confidence:.2f}): {list(pk_params.keys())}")
                notes_str = f"Claude-extracted from PubMed PMID {pmid} (conf={confidence:.2f})"
                if species_note:
                    notes_str += f"; species={species_note}"
                pk_rec = {
                    "drug_id": drug_id,
                    "source_type": "abstract",
                    "source_url": source_url,
                    "notes": notes_str,
                    "verified": False,
                    **pk_params,
                }
                if _db.sb_insert("drug_pk_parameters", pk_rec):
                    pk_written += 1
                    log(f"    OK drug_pk_parameters for {drug_id} (PMID {pmid})")
                else:
                    log(f"    FAIL: insert failed (see log)")
            else:
                log(f"    No PK params found (conf too low) — PMID {pmid}")

        _db.sb_patch("research_queue",
                     {"assigned_status": "completed", "last_action_at": NOW_ISO},
                     {"id": f"eq.{item_id}"})
        processed += 1
        time.sleep(0.2)

    log(f"  PK/PD: {processed} items processed, {pk_written} drug_pk_parameters rows written")
    log("--- Phase 7 complete ---")
    return pk_written


if __name__ == "__main__":
    main()
