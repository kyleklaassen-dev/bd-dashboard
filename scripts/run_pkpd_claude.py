#!/usr/bin/env python3
"""
Standalone runner for the Claude-powered PK/PD extractor.
Reads all pkpd_literature items from research_queue and reprocesses with Claude.

Usage:
  ANTHROPIC_API_KEY=... SUPABASE_URL=... SUPABASE_SERVICE_KEY=... python3 scripts/run_pkpd_claude.py
"""

import os, sys, json, datetime, time, re, requests
import anthropic

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

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


def log(msg):
    print(msg, flush=True)


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
    try:
        resp = client.messages.create(
            model=PKPD_CLAUDE_MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        parsed = json.loads(raw)
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
    except json.JSONDecodeError as exc:
        log(f"    Claude PK extraction: JSON parse error — {exc}")
        return {}
    except Exception as exc:
        log(f"    Claude PK extraction error: {exc}")
        return {}


def main():
    log("--- Phase 7: PK/PD queue processor (Claude-powered) ---")
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
    queue_items = r.json() if r.status_code == 200 else []
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
                pr = requests.post(
                    f"{SUPABASE_URL}/rest/v1/drug_pk_parameters",
                    headers={**SB_HEADERS, "Prefer": "resolution=ignore-duplicates,return=minimal"},
                    json=pk_rec,
                    timeout=15,
                )
                if pr.status_code in (200, 201, 204):
                    pk_written += 1
                    log(f"    OK drug_pk_parameters for {drug_id} (PMID {pmid})")
                else:
                    log(f"    FAIL: {pr.status_code} {pr.text[:200]}")
            else:
                log(f"    No PK params found (conf too low) — PMID {pmid}")

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
        time.sleep(0.2)

    log(f"  PK/PD: {processed} items processed, {pk_written} drug_pk_parameters rows written")
    log("--- Phase 7 complete ---")
    return pk_written


if __name__ == "__main__":
    main()
