#!/usr/bin/env python3
"""
PK/PD queue processor (§3 research split — "GAP 1 FIX"). Pulls PubMed abstracts and
extracts PK/PD parameters with Claude. Extracted verbatim.
"""

import json
import re
import time
import datetime

import requests

from meridian.ingestion.research_pipeline.common import log, client, SB_HEADERS, SUPABASE_URL


# ── GAP 1 FIX: PK/PD queue processor ─────────────────────────────────────────

PKPD_CLAUDE_MODEL = "claude-haiku-4-5-20251001"

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


def fetch_pubmed_abstract(pmid: str, timeout: int = 10) -> str:
    """
    Fetch abstract text for a PubMed PMID via the NCBI efetch API.
    Returns empty string on failure.
    """
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


def extract_pk_with_claude(abstract_text: str) -> dict:
    """
    Use Claude claude-haiku-4-5-20251001 to extract PK parameters from a PubMed abstract.
    Returns parsed dict with extracted parameters; empty dict on failure or low confidence.
    Only returns fields where confidence > 0.5.
    """
    if not abstract_text or len(abstract_text.strip()) < 50:
        return {}

    # Truncate to ~4000 chars to keep costs minimal
    abstract_trimmed = abstract_text[:4000]

    prompt = PKPD_EXTRACTION_PROMPT.replace("{abstract_text}", abstract_trimmed)

    try:
        resp = client.messages.create(
            model=PKPD_CLAUDE_MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        parsed = json.loads(raw)
        confidence = float(parsed.get("confidence", 0.0))

        if confidence <= 0.5:
            return {}

        # Build output dict — only non-null fields that map to db columns
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

        # dose_route is the column name in drug_pk_parameters (not "route")
        # Only allow exact values: SC, IV, oral — reject combined strings like "SC/IV"
        route_val = str(parsed.get("route") or "").strip()
        if route_val in ("SC", "IV", "oral"):
            result["dose_route"] = route_val

        # species is not a column in drug_pk_parameters — embed in notes instead
        if parsed.get("species"):
            result["_species"] = str(parsed["species"])

        result["_confidence"] = confidence  # internal — not written to db column
        return result

    except json.JSONDecodeError as exc:
        log(f"    Claude PK extraction: JSON parse error — {exc}")
        return {}
    except Exception as exc:
        log(f"    Claude PK extraction error: {exc}")
        return {}


def process_pkpd_queue() -> int:
    """
    GAP 1 FIX: Process research_queue items where context_type='pkpd_literature'.
    Uses Claude claude-haiku-4-5-20251001 for structured extraction (replaces regex).

    For each item:
      1. Extract PMID from the reason field.
      2. Fetch the PubMed abstract via NCBI efetch.
      3. Send abstract to Claude — get structured PK parameter JSON.
      4. If confidence > 0.5, write to drug_pk_parameters.
      5. Mark the research_queue item as assigned_status='completed'.

    Returns count of items processed.
    """
    log("--- Phase 7: PK/PD queue processor (Claude-powered) ---")

    # Fetch ALL pkpd queue items regardless of status — reset completed so they
    # get reprocessed by Claude (regex run may have missed parameters).
    queue_items = []
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/research_queue",
            headers=SB_HEADERS,
            params={
                "context_type": "eq.pkpd_literature",
                "select": "id,entity_id,reason,assigned_status",
                "limit": "100",
            },
            timeout=15,
        )
        if r.status_code == 200:
            queue_items = r.json()
        else:
            log(f"  research_queue fetch error: {r.status_code}")
    except Exception as exc:
        log(f"  PK/PD queue fetch error: {exc}")
        return 0

    log(f"  Found {len(queue_items)} PK/PD queue items (all statuses)")
    if not queue_items:
        return 0

    processed = 0
    pk_written = 0
    NOW_ISO = datetime.datetime.utcnow().isoformat()

    for item in queue_items:
        item_id = item["id"]
        drug_id = item.get("entity_id", "")
        reason = item.get("reason", "")

        # Extract PMID from reason text: "PMID 39073504"
        pmid_match = re.search(r"PMID\s+(\d+)", reason)
        if not pmid_match:
            log(f"  No PMID found in reason for {drug_id}: {reason[:80]}")
            requests.patch(
                f"{SUPABASE_URL}/rest/v1/research_queue",
                headers={**SB_HEADERS, "Prefer": "return=minimal"},
                params={"id": f"eq.{item_id}"},
                json={"assigned_status": "completed"},
                timeout=10,
            )
            processed += 1
            continue

        pmid = pmid_match.group(1)
        source_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

        log(f"  Processing {drug_id} — PMID {pmid}")
        time.sleep(0.4)  # NCBI courtesy delay

        abstract = fetch_pubmed_abstract(pmid)
        if not abstract:
            log(f"    No abstract returned for PMID {pmid}")
        else:
            pk_params = extract_pk_with_claude(abstract)
            confidence = pk_params.pop("_confidence", 0.0)

            if pk_params:
                log(f"    Claude extracted PK params (conf={confidence:.2f}): {list(pk_params.keys())}")
                # _species is not a column — move it to notes
                species_note = pk_params.pop("_species", None)
                notes_str = f"Claude-extracted from PubMed PMID {pmid} (conf={confidence:.2f})"
                if species_note:
                    notes_str += f"; species={species_note}"
                pk_rec = {
                    "drug_id":      drug_id,
                    # source_type CHECK constraint: Phase1|Phase2|Phase3|label|abstract|poster|investor_PR|ClinicalTrials
                    "source_type":  "abstract",
                    "source_url":   source_url,
                    "notes":        notes_str,
                    "verified":     False,
                    **pk_params,
                }
                try:
                    pr = requests.post(
                        f"{SUPABASE_URL}/rest/v1/drug_pk_parameters",
                        headers={**SB_HEADERS, "Prefer": "resolution=ignore-duplicates,return=minimal"},
                        json=pk_rec,
                        timeout=15,
                    )
                    if pr.status_code in (200, 201, 204):
                        pk_written += 1
                        log(f"    ✓ Wrote drug_pk_parameters for {drug_id} (PMID {pmid})")
                    else:
                        log(f"    ✗ Write failed: {pr.status_code} {pr.text[:100]}")
                except Exception as exc:
                    log(f"    Write error: {exc}")
            else:
                log(f"    No PK parameters found by Claude (confidence too low or none present) — PMID {pmid}")

        # Mark research_queue item as completed
        try:
            requests.patch(
                f"{SUPABASE_URL}/rest/v1/research_queue",
                headers={**SB_HEADERS, "Prefer": "return=minimal"},
                params={"id": f"eq.{item_id}"},
                json={"assigned_status": "completed", "last_action_at": NOW_ISO},
                timeout=10,
            )
        except Exception:
            pass

        processed += 1
        time.sleep(0.2)  # avoid Claude rate-limit on haiku

    log(f"  PK/PD queue: {processed} items processed, {pk_written} drug_pk_parameters rows written")
    log("--- Phase 7 complete ---")
    return processed
