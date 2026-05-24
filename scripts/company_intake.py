#!/usr/bin/env python3
"""
company_intake.py — Company-First Discovery Engine (Phase 1)

CLI tool: python scripts/company_intake.py --company "Akeso"

PURPOSE
-------
Answers: "Is this company worth onboarding into Meridian, and which areas
          should it be enriched for?"

This is a *routing* tool, not a *classification* tool. It produces a discovery
package that goes into discovery_queue for human review. Final area scoring
and drug-level intelligence happen in research_intelligence.py AFTER approval.

WORKFLOW
--------
1. Resolve company identity via CompanyIdentityResolver
   - resolved_existing  → report what Meridian already knows, offer to re-enrich
   - alias_match        → same
   - unresolved         → warn about possible alias conflict, prompt for confirmation
   - candidate_new      → proceed with research

2. Research company across all active Meridian areas using Claude + ClinicalTrials.gov
   - Open-ended discovery prompt (no prior area assumption)
   - Identify molecules, targets, indications, trials, deals

3. Score area relevance for each active Meridian area
   - Direct / Adjacent / Same-patient competitor / Strategic watchlist / Not relevant
   - Minimum evidence threshold: at least one molecule OR one verified clinical program

4. Write discovery_queue rows with source='user_intake'
   - One row per relevant area (confidence ≥ 0.5)
   - Dedup: skip if same company×area row exists from last 30 days (not rejected)

5. Print summary area map to console

USAGE
-----
  python scripts/company_intake.py --company "Akeso"
  python scripts/company_intake.py --company "Hengrui" --dry-run
  python scripts/company_intake.py --company "Zenas BioPharma" --verbose

ENVIRONMENT
-----------
  ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY
  (or workspace files: .supabase_config, .supabase_service_key)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests
import anthropic

# ── Resolver import ───────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from company_identity_resolver import CompanyIdentityResolver, get_credentials

# ══════════════════════════════════════════════════════════════════════════════
# CREDENTIALS
# ══════════════════════════════════════════════════════════════════════════════

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
SUPABASE_URL, SUPABASE_KEY = get_credentials()

_sb_headers = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=minimal",
}

# Lazy-init: _ai is created on first use so import doesn't require ANTHROPIC_API_KEY
_ai: anthropic.Anthropic | None = None

def _get_ai() -> anthropic.Anthropic:
    global _ai
    if _ai is None:
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            raise SystemExit(
                "ERROR: ANTHROPIC_API_KEY not set. "
                "export ANTHROPIC_API_KEY=sk-ant-..."
            )
        _ai = anthropic.Anthropic(api_key=key)
    return _ai

# ── Active Meridian areas ─────────────────────────────────────────────────────

ACTIVE_AREAS = {
    "tl1a":   {
        "label":    "TL1A × IBD",
        "keywords": ["TL1A", "TNF-like ligand 1A", "DR3", "IBD", "Crohn", "ulcerative colitis", "UC", "CD"],
    },
    "tslp":   {
        "label":    "TSLP × Respiratory",
        "keywords": ["TSLP", "thymic stromal lymphopoietin", "asthma", "COPD", "atopic", "eosinophil"],
    },
    "il4ra":  {
        "label":    "IL-4Rα × Atopy",
        "keywords": ["IL-4R", "IL-4Rα", "IL4", "dupilumab", "atopic dermatitis", "AD", "asthma", "CRSwNP"],
    },
    "fcrn":   {
        "label":    "FcRn × Autoimmune",
        "keywords": ["FcRn", "neonatal Fc receptor", "IgG", "autoimmune", "gMG", "ITP", "pemphigus", "HDFN", "nipocalimab", "rozanolixizumab", "efgartigimod"],
    },
    "igf1r":  {
        "label":    "IGF-1R × Thyroid Eye",
        "keywords": ["IGF-1R", "IGF1R", "TSH receptor", "TSHR", "thyroid eye disease", "TED", "Graves", "teprotumumab"],
    },
    "tcell":  {
        "label":    "T-cell Engineering × Autoimmune",
        "keywords": ["CAR-T", "T cell", "TCR", "BCMA", "CD19", "autoimmune", "cell therapy", "ACE", "CAR"],
    },
}

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — IDENTITY RESOLUTION
# ══════════════════════════════════════════════════════════════════════════════

def resolve_identity(company_name: str, dry_run: bool = False) -> dict:
    """Resolve company name using CompanyIdentityResolver."""
    resolver = CompanyIdentityResolver(SUPABASE_URL, SUPABASE_KEY, dry_run=dry_run)
    result = resolver.resolve_with_detail(company_name, source="company_intake")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — OPEN-ENDED COMPANY RESEARCH
# ══════════════════════════════════════════════════════════════════════════════

RESEARCH_PROMPT = """You are a pharmaceutical competitive intelligence analyst.

Research the company: **{company_name}**

Your task is OPEN-ENDED DISCOVERY — do not assume any specific area of focus.
Research this company comprehensively across all biopharma/pharma activity.

Return a JSON object with this exact structure:

{{
  "company": {{
    "canonical_name": "string — official full company name",
    "short_name": "string — common short name / ticker name",
    "ticker": "string or null — stock ticker if public",
    "exchange": "string or null — NYSE/NASDAQ/HKEX/etc.",
    "geography": "string — primary HQ country",
    "company_type": "string — large_cap|mid_cap|small_cap|biotech|startup|private",
    "founded": "string or null — founding year",
    "website": "string or null",
    "tagline": "string — 1-sentence summary of what the company does"
  }},
  "pipeline": [
    {{
      "drug_name": "string — INN or code name",
      "brand_name": "string or null",
      "target": "string — molecular target(s)",
      "mechanism": "string — MoA",
      "modality": "string — mAb|bispecific|ADC|small molecule|cell therapy|etc.",
      "indication": "string — primary indication(s)",
      "stage": "string — Preclinical|Phase 1|Phase 2|Phase 3|Approved|Terminated",
      "nct_ids": ["string"],
      "partner": "string or null — licensor/licensee if applicable",
      "evidence_note": "string — brief citation or evidence summary"
    }}
  ],
  "deals": [
    {{
      "date": "string — YYYY or YYYY-MM",
      "type": "string — licensing|acquisition|collaboration|co-development|etc.",
      "partner": "string — other company",
      "asset": "string — drug or platform",
      "value": "string or null — deal value if disclosed",
      "description": "string — 1-2 sentence summary"
    }}
  ],
  "area_assessment": {{
    "tl1a":  {{"relevance": "Direct|Adjacent|Same-patient|Watchlist|Not relevant", "rationale": "string", "confidence": 0.0, "evidence": "string"}},
    "tslp":  {{"relevance": "Direct|Adjacent|Same-patient|Watchlist|Not relevant", "rationale": "string", "confidence": 0.0, "evidence": "string"}},
    "il4ra": {{"relevance": "Direct|Adjacent|Same-patient|Watchlist|Not relevant", "rationale": "string", "confidence": 0.0, "evidence": "string"}},
    "fcrn":  {{"relevance": "Direct|Adjacent|Same-patient|Watchlist|Not relevant", "rationale": "string", "confidence": 0.0, "evidence": "string"}},
    "igf1r": {{"relevance": "Direct|Adjacent|Same-patient|Watchlist|Not relevant", "rationale": "string", "confidence": 0.0, "evidence": "string"}},
    "tcell": {{"relevance": "Direct|Adjacent|Same-patient|Watchlist|Not relevant", "rationale": "string", "confidence": 0.0, "evidence": "string"}}
  }},
  "summary": "string — 2-3 sentences on what this company does and why it matters to a TL1A/FcRn/IL-4Rα IBD/autoimmune BD analyst",
  "data_quality": "string — high|medium|low — how much verified public information is available",
  "why_relevant": "string or null — if any area is Direct/Adjacent, explain the key BD angle in 1-2 sentences"
}}

Area definitions for scoring:
- TL1A/IBD: TL1A inhibitors, IL-23 inhibitors in IBD, IL-12/23, integrin inhibitors (IBD indication specifically), JAK inhibitors in IBD
- TSLP/Respiratory: TSLP inhibitors, IL-33, IL-4/13 in asthma, anti-eosinophil biologics (mepolizumab/benralizumab class)
- IL-4Rα/Atopy: IL-4Rα inhibitors, IL-13, IL-31, TSLP in atopic dermatitis, TARC pathway in AD
- FcRn/Autoimmune: FcRn inhibitors for IgG-mediated diseases (gMG, ITP, pemphigus, HDFN, SLE, MN)
- IGF-1R/Thyroid Eye: IGF-1R inhibitors or TSH receptor antibodies in TED or Graves disease
- T-cell/Autoimmune Cell Therapy: CAR-T, TCR-T, CAR-Treg, or related cell therapies for autoimmune indications

For confidence: 0.9–1.0 = clinical evidence in the area; 0.6–0.9 = preclinical or platform; 0.3–0.6 = platform company, possible indication; <0.3 = speculative

IMPORTANT:
- If you have limited information on this company, say so in data_quality and be conservative in scoring
- Do NOT fabricate clinical trial NCT IDs — leave nct_ids empty if unknown
- It is fine for most areas to be "Not relevant" — only score areas where real evidence exists
- Return ONLY the JSON object, no prose before or after

Company to research: {company_name}
"""

def research_company(company_name: str, verbose: bool = False) -> dict | None:
    """
    Call Claude to research the company open-endedly across all active areas.
    Returns parsed JSON dict or None on failure.
    """
    prompt = RESEARCH_PROMPT.format(company_name=company_name)

    # Model selection: use env var override for fast validation, default to sonnet for production
    _model = os.environ.get("INTAKE_MODEL", "claude-sonnet-4-6")

    if verbose:
        print(f"  → Calling Claude ({_model}) for open-ended research on '{company_name}'...")

    try:
        resp = _get_ai().messages.create(
            model=_model,
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()

        # Strip code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        data = json.loads(raw)
        if verbose:
            print(f"  → Research complete. Pipeline: {len(data.get('pipeline', []))} drugs, "
                  f"Deals: {len(data.get('deals', []))} entries.")
        return data

    except json.JSONDecodeError as e:
        print(f"  ⚠️  JSON parse error: {e}")
        print(f"  Raw response (first 500 chars): {raw[:500]}")
        return None
    except Exception as e:
        print(f"  ❌ Research call failed: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — AREA RELEVANCE FILTERING
# ══════════════════════════════════════════════════════════════════════════════

# Minimum evidence thresholds before writing a queue row
_RELEVANCE_INCLUDE = {"Direct", "Adjacent", "Same-patient"}
_RELEVANCE_WATCHLIST_MIN_CONFIDENCE = 0.6   # watchlist only if high-confidence
_MIN_CONFIDENCE = 0.5                        # skip any area below this

def _has_minimum_evidence(research: dict, area_id: str) -> bool:
    """
    Check if there's at least one molecule OR one clinical program found.
    Prevents writing queue rows for pure speculation.
    """
    pipeline = research.get("pipeline", [])
    if not pipeline:
        # No drugs found — only allow if company itself is in the area (strategic watchlist)
        area_data = research.get("area_assessment", {}).get(area_id, {})
        if area_data.get("relevance") == "Direct" and area_data.get("confidence", 0) >= 0.7:
            return True
        return False
    return True


def get_relevant_areas(research: dict) -> list[dict]:
    """
    Extract areas that meet the minimum evidence + confidence thresholds.
    Returns list of dicts with area_id, relevance, confidence, rationale, evidence.
    """
    assessment = research.get("area_assessment", {})
    result = []

    for area_id, area_info in assessment.items():
        if area_id not in ACTIVE_AREAS:
            continue

        relevance   = area_info.get("relevance", "Not relevant")
        confidence  = float(area_info.get("confidence", 0))
        rationale   = area_info.get("rationale", "")
        evidence    = area_info.get("evidence", "")

        # Skip non-relevant
        if relevance == "Not relevant":
            continue

        # Watchlist needs high confidence
        if relevance == "Watchlist" and confidence < _RELEVANCE_WATCHLIST_MIN_CONFIDENCE:
            continue

        # Minimum confidence floor
        if confidence < _MIN_CONFIDENCE:
            continue

        # Minimum evidence check
        if not _has_minimum_evidence(research, area_id):
            continue

        result.append({
            "area_id":    area_id,
            "area_label": ACTIVE_AREAS[area_id]["label"],
            "relevance":  relevance,
            "confidence": confidence,
            "rationale":  rationale,
            "evidence":   evidence,
        })

    # Sort: Direct first, then Adjacent, then Same-patient, then Watchlist
    _order = {"Direct": 0, "Adjacent": 1, "Same-patient": 2, "Watchlist": 3}
    result.sort(key=lambda x: (_order.get(x["relevance"], 9), -x["confidence"]))
    return result


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — DEDUP CHECK
# ══════════════════════════════════════════════════════════════════════════════

def _check_existing_queue_rows(company_id: str, area_ids: list[str]) -> set[str]:
    """
    Return the set of area_ids that already have a pending/reviewed queue row
    from the last 30 days (not rejected). These will be skipped.
    """
    if not company_id or not area_ids:
        return set()

    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/discovery_queue",
            headers={**_sb_headers, "Prefer": ""},
            params={
                "company_id_suggested": f"eq.{company_id}",
                "status":              "not.eq.rejected",
                "discovered_at":       f"gte.{cutoff}",
                "select":              "area_id",
            },
        )
        if resp.status_code == 200:
            return {row["area_id"] for row in resp.json() if row.get("area_id")}
    except Exception:
        pass
    return set()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — WRITE DISCOVERY QUEUE ROWS
# ══════════════════════════════════════════════════════════════════════════════

def write_queue_rows(
    company_name: str,
    company_id: str | None,
    resolution: dict,
    research: dict,
    relevant_areas: list[dict],
    run_id: str,
    dry_run: bool = False,
) -> list[str]:
    """
    Write one discovery_queue row per relevant area.
    Returns list of area_ids successfully written.
    """
    co_info    = research.get("company", {})
    pipeline   = research.get("pipeline", [])
    deals      = research.get("deals", [])

    # Canonical name from research or resolver
    canonical_name = co_info.get("canonical_name") or company_name
    suggested_id   = company_id or resolution.get("canonical_name") or company_name.lower().replace(" ", "")

    # Check for existing rows to skip
    existing_areas = _check_existing_queue_rows(suggested_id, [a["area_id"] for a in relevant_areas])
    written = []

    for area in relevant_areas:
        area_id = area["area_id"]

        if area_id in existing_areas:
            print(f"  ⏭️  {area_id}: skipped (recent row already exists, not rejected)")
            continue

        # Find drugs most relevant to this area
        area_keywords  = [k.lower() for k in ACTIVE_AREAS[area_id]["keywords"]]
        relevant_drugs = []
        for drug in pipeline:
            drug_text = (
                (drug.get("target") or "") + " " +
                (drug.get("indication") or "") + " " +
                (drug.get("mechanism") or "")
            ).lower()
            if any(kw in drug_text for kw in area_keywords):
                relevant_drugs.append(drug)

        # Build a drug summary string for the why_discovered field
        drug_summary = "; ".join(
            f"{d['drug_name']} ({d['target']}, {d['stage']})"
            for d in relevant_drugs[:3]
        ) or "No specific drug identified — platform-level relevance"

        # Build queue row
        row = {
            "company_name":           canonical_name,
            "company_id_suggested":   suggested_id,
            "drug_name":              relevant_drugs[0]["drug_name"] if relevant_drugs else None,
            "target":                 relevant_drugs[0]["target"]    if relevant_drugs else None,
            "stage":                  relevant_drugs[0]["stage"]     if relevant_drugs else None,
            "modality":               relevant_drugs[0].get("modality") if relevant_drugs else None,
            "entity_type":            "molecule" if relevant_drugs else "company",
            "area_id":                area_id,
            "overlap":                _map_relevance_to_overlap(area["relevance"]),
            "competition_layer":      _map_relevance_to_layer(area["relevance"]),
            "confidence_score":       int(area["confidence"] * 100),
            "relevance_score":        _confidence_to_relevance_score(area["confidence"], area["relevance"]),
            "relevance_rationale":    area["rationale"],
            "reason":                 f"{area['relevance']} relevance to {ACTIVE_AREAS[area_id]['label']} — {area['evidence']}",
            "source_url":             None,
            "suggested_dest":         "new_company" if not company_id else "update_company",
            "discovered_by":          "company_intake",
            "status":                 "pending",
            "discovery_run_id":       run_id,
            "relationship_type":      _map_relevance_to_relationship(area["relevance"]),
            "relationship_confidence": "high" if area["confidence"] >= 0.8 else "medium" if area["confidence"] >= 0.6 else "inferred",
            "why_discovered":         f"User intake: '{company_name}' → {area_id}. Evidence: {drug_summary}. {area['rationale']}",
        }

        # Add source column if it exists (migration v22 may not be applied yet)
        row["source"] = "user_intake"

        if dry_run:
            print(f"  [DRY RUN] Would write queue row: {area_id} / {area['relevance']} / confidence={area['confidence']:.2f}")
            written.append(area_id)
            continue

        try:
            resp = requests.post(
                f"{SUPABASE_URL}/rest/v1/discovery_queue",
                headers=_sb_headers,
                json=row,
                timeout=10,
            )
            if resp.status_code in (200, 201):
                written.append(area_id)
                print(f"  ✅ {area_id}: queued ({area['relevance']}, confidence={area['confidence']:.0%})")
            elif resp.status_code == 409:
                print(f"  ⏭️  {area_id}: conflict (row already exists)")
            else:
                # Try without 'source' column in case migration not applied
                row_no_source = {k: v for k, v in row.items() if k != "source"}
                resp2 = requests.post(
                    f"{SUPABASE_URL}/rest/v1/discovery_queue",
                    headers=_sb_headers,
                    json=row_no_source,
                    timeout=10,
                )
                if resp2.status_code in (200, 201):
                    written.append(area_id)
                    print(f"  ✅ {area_id}: queued ({area['relevance']}, confidence={area['confidence']:.0%}) [source col pending migration]")
                else:
                    print(f"  ❌ {area_id}: write failed {resp2.status_code} — {resp2.text[:200]}")
        except Exception as e:
            print(f"  ❌ {area_id}: exception — {e}")

    return written


# ══════════════════════════════════════════════════════════════════════════════
# TRANSACTION INTAKE — ACQUISITION EDGE WRITER
# ══════════════════════════════════════════════════════════════════════════════
#
# Rule (v28, 2026-05-24): When a Transaction Intake processes an acquisition
# deal, it must write ownership_edges with deal_id set so every edge traces
# back to its originating deal record.
#
# Pattern for any acquisition:
#   1. Write (or find) deals row → get deal_id
#   2. Write ownership_edges:
#        • acquired_company ACQUIRED→ acquirer_company  (deal_id=deal_id)
#        • drug ORIGINATED_BY→ acquired_company          (deal_id=deal_id)
#        • drug CONTROLLED_BY→ acquirer_company          (deal_id=deal_id)
#
# Canonical examples (backfilled 2026-05-24):
#   UCB/Candid (deal 19), UCB/Antengene (deal 167), Merck/Prometheus (deal 28)
#
# Usage: call write_acquisition_edges() after a deals row is inserted and
# the company + drug IDs are confirmed.

def write_acquisition_edges(
    deal_id: int,
    acquirer_id: str,
    acquired_id: str,
    drug_ids: list[str],
    source_url: str | None = None,
    dry_run: bool = False,
) -> int:
    """
    Write ownership_edges for an acquisition transaction with deal_id FK set.

    Returns number of edges successfully written.
    """
    edges = [
        # Company-level acquisition edge
        {
            "subject_type":     "company",
            "subject_id":       acquired_id,
            "predicate":        "ACQUIRED",
            "object_type":      "company",
            "object_id":        acquirer_id,
            "deal_id":          deal_id,
            "confidence_level": "confirmed",
            "source_url":       source_url,
            "source_type":      "press_release",
            "status":           "active",
            "created_by":       "company_intake",
        }
    ]

    for drug_id in drug_ids:
        # Drug originated in acquired company
        edges.append({
            "subject_type":     "drug",
            "subject_id":       drug_id,
            "predicate":        "ORIGINATED_BY",
            "object_type":      "company",
            "object_id":        acquired_id,
            "deal_id":          deal_id,
            "confidence_level": "confirmed",
            "source_url":       source_url,
            "source_type":      "press_release",
            "status":           "active",
            "created_by":       "company_intake",
        })
        # Drug now controlled by acquirer
        edges.append({
            "subject_type":     "drug",
            "subject_id":       drug_id,
            "predicate":        "CONTROLLED_BY",
            "object_type":      "company",
            "object_id":        acquirer_id,
            "deal_id":          deal_id,
            "confidence_level": "confirmed",
            "source_url":       source_url,
            "source_type":      "press_release",
            "status":           "active",
            "created_by":       "company_intake",
        })

    if dry_run:
        print(f"  [DRY RUN] Would write {len(edges)} acquisition ownership_edges (deal_id={deal_id})")
        for e in edges:
            print(f"    {e['subject_id']} -{e['predicate']}→ {e['object_id']}")
        return len(edges)

    ok = 0
    for edge in edges:
        try:
            resp = requests.post(
                f"{SUPABASE_URL}/rest/v1/ownership_edges",
                headers={**_sb_headers, "Prefer": "resolution=ignore-duplicates,return=representation"},
                json=edge,
                timeout=10,
            )
            if resp.status_code in (200, 201):
                ok += 1
            else:
                print(f"  ⚠ Edge {edge['subject_id']}/{edge['predicate']}: {resp.status_code} {resp.text[:150]}")
        except Exception as e:
            print(f"  ❌ Edge write error: {e}")

    print(f"  ✓ {ok}/{len(edges)} acquisition ownership_edges written (deal_id={deal_id})")
    return ok


def write_license_edges(
    deal_id: int,
    licensor_id: str,
    licensee_id: str,
    drug_ids: list[str],
    source_url: str | None = None,
    dry_run: bool = False,
) -> int:
    """
    Write ownership_edges for a licensing deal with deal_id FK set.
    Used for in-licensing (licensee receives rights from licensor).
    """
    edges = []
    for drug_id in drug_ids:
        edges.append({
            "subject_type":     "drug",
            "subject_id":       drug_id,
            "predicate":        "ORIGINATED_BY",
            "object_type":      "company",
            "object_id":        licensor_id,
            "deal_id":          deal_id,
            "confidence_level": "confirmed",
            "source_url":       source_url,
            "source_type":      "press_release",
            "status":           "active",
            "created_by":       "company_intake",
        })
        edges.append({
            "subject_type":     "drug",
            "subject_id":       drug_id,
            "predicate":        "LICENSED_IN",
            "object_type":      "company",
            "object_id":        licensee_id,
            "deal_id":          deal_id,
            "confidence_level": "confirmed",
            "source_url":       source_url,
            "source_type":      "press_release",
            "status":           "active",
            "created_by":       "company_intake",
        })
        edges.append({
            "subject_type":     "drug",
            "subject_id":       drug_id,
            "predicate":        "LICENSED_FROM",
            "object_type":      "company",
            "object_id":        licensor_id,
            "deal_id":          deal_id,
            "confidence_level": "confirmed",
            "source_url":       source_url,
            "source_type":      "press_release",
            "status":           "active",
            "created_by":       "company_intake",
        })

    if dry_run:
        print(f"  [DRY RUN] Would write {len(edges)} license ownership_edges (deal_id={deal_id})")
        return len(edges)

    ok = 0
    for edge in edges:
        try:
            resp = requests.post(
                f"{SUPABASE_URL}/rest/v1/ownership_edges",
                headers={**_sb_headers, "Prefer": "resolution=ignore-duplicates,return=representation"},
                json=edge,
                timeout=10,
            )
            if resp.status_code in (200, 201):
                ok += 1
            else:
                print(f"  ⚠ Edge {edge['subject_id']}/{edge['predicate']}: {resp.status_code} {resp.text[:150]}")
        except Exception as e:
            print(f"  ❌ Edge write error: {e}")

    print(f"  ✓ {ok}/{len(edges)} license ownership_edges written (deal_id={deal_id})")
    return ok


# ══════════════════════════════════════════════════════════════════════════════
# GRAPH CONSISTENCY — ACTIVE_IN EDGE WRITER
# ══════════════════════════════════════════════════════════════════════════════
#
# Rule (v29, 2026-05-24): Every company_areas write must be paired with a
# corresponding entity_edges ACTIVE_IN row so the graph can answer
# "who is active in [area]?" as a single predicate lookup.
#
# This function is called by approve_discovery.py immediately after each
# sb_upsert("company_areas", ...) call.
#
# Idempotent: uses resolution=ignore-duplicates so re-running is safe.

def write_active_in_edge(
    company_id: str,
    area_id: str,
    dry_run: bool = False,
    created_by: str = "approve_discovery",
) -> bool:
    """
    Write a single entity_edges ACTIVE_IN row for company → area.
    Returns True if written (or dry-run), False on error.

    Idempotent — safe to call even if the edge already exists.
    """
    edge = {
        "subject_type":      "company",
        "subject_id":        company_id,
        "predicate":         "ACTIVE_IN",
        "object_type":       "area",
        "object_id":         area_id,
        "confidence_level":  "confirmed",
        "generation_method": "deterministic",
        "rationale":         "Derived from company_areas table",
        "status":            "active",
        "created_by":        created_by,
    }

    if dry_run:
        print(f"  [DRY RUN] Would write ACTIVE_IN edge: {company_id} → {area_id}")
        return True

    try:
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/entity_edges",
            headers={**_sb_headers, "Prefer": "resolution=ignore-duplicates,return=minimal"},
            json=edge,
            timeout=10,
        )
        if resp.status_code in (200, 201):
            print(f"  + entity_edges ACTIVE_IN: {company_id} → {area_id}")
            return True
        else:
            print(f"  ⚠ ACTIVE_IN edge {company_id}/{area_id}: {resp.status_code} {resp.text[:150]}")
            return False
    except Exception as e:
        print(f"  ❌ ACTIVE_IN edge write error ({company_id}/{area_id}): {e}")
        return False


# ── Overlap/layer/score helpers ───────────────────────────────────────────────

def _map_relevance_to_overlap(relevance: str) -> str:
    return {
        "Direct":       "Direct",
        "Adjacent":     "Adjacent",
        "Same-patient": "Same-Space",
        "Watchlist":    "Watch",
    }.get(relevance, "Watch")


def _map_relevance_to_layer(relevance: str) -> int:
    return {"Direct": 1, "Adjacent": 2, "Same-patient": 3, "Watchlist": 4}.get(relevance, 4)


def _confidence_to_relevance_score(confidence: float, relevance: str) -> int:
    base = {"Direct": 8, "Adjacent": 6, "Same-patient": 5, "Watchlist": 4}.get(relevance, 3)
    return min(10, int(base + confidence * 2))


def _map_relevance_to_relationship(relevance: str) -> str:
    return {
        "Direct":       "direct_competitor",
        "Adjacent":     "platform_overlap",
        "Same-patient": "same_patient_population",
        "Watchlist":    "strategic_watchlist",
    }.get(relevance, "strategic_watchlist")


# ══════════════════════════════════════════════════════════════════════════════
# PRINTING HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _print_area_map(company_name: str, research: dict, relevant_areas: list[dict], written: list[str]):
    co = research.get("company", {})
    print()
    print("═" * 65)
    print(f"  AREA MAP — {co.get('canonical_name', company_name)}")
    ticker = co.get("ticker")
    if ticker:
        print(f"  {ticker} · {co.get('exchange', '')} · {co.get('geography', '')}")
    print(f"  {co.get('tagline', '')}")
    print("═" * 65)

    if not relevant_areas:
        print("  No areas meet the minimum evidence threshold.")
        print("  Company may not operate in active Meridian focus areas.")
    else:
        for area in relevant_areas:
            aid = area["area_id"]
            label = ACTIVE_AREAS[aid]["label"]
            status = "✅ queued" if aid in written else "⏭️  skipped"
            conf_bar = "█" * int(area["confidence"] * 10) + "░" * (10 - int(area["confidence"] * 10))
            print(f"\n  {area['relevance']:<15} {label}")
            print(f"  Confidence  [{conf_bar}] {area['confidence']:.0%}  {status}")
            print(f"  Rationale   {area['rationale'][:120]}")
            if area["evidence"]:
                print(f"  Evidence    {area['evidence'][:120]}")

    pipeline = research.get("pipeline", [])
    if pipeline:
        print(f"\n  Pipeline ({len(pipeline)} drug{'s' if len(pipeline) != 1 else ''} found):")
        for d in pipeline[:6]:
            stage = d.get("stage", "?")
            print(f"    • {d['drug_name']} — {d['target']} — {stage} — {d['indication'][:60]}")
        if len(pipeline) > 6:
            print(f"    ... and {len(pipeline) - 6} more")

    deals = research.get("deals", [])
    if deals:
        print(f"\n  Deals ({len(deals)} found):")
        for dl in deals[:3]:
            print(f"    • {dl.get('date', '?')} — {dl.get('partner', '?')} — {dl.get('asset', '?')}")

    why = research.get("why_relevant")
    if why:
        print(f"\n  BD Angle: {why}")

    print()
    print(f"  Data quality: {research.get('data_quality', 'unknown')}")
    if written:
        print(f"  {len(written)} area row(s) written to discovery_queue (source=user_intake, status=pending)")
        print("  → Review in Meridian Dashboard → Discovery Queue tab")
    print("═" * 65)
    print()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def run_intake(company_name: str, dry_run: bool = False, verbose: bool = False, force: bool = False):
    """
    Full intake workflow for a single company name.
    """
    ts   = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    slug = company_name.lower().replace(" ", "_").replace("&", "").replace("/", "_")
    run_id = f"intake_{slug}_{ts}"

    print()
    print(f"Company Intake — '{company_name}'")
    print(f"Run ID: {run_id}  |  dry_run={dry_run}")
    print("─" * 55)

    # ── Step 1: Identity resolution ──────────────────────────────────────────
    print("\n[1/4] Resolving company identity...")
    resolution = resolve_identity(company_name, dry_run=dry_run)
    rtype = resolution["resolution_type"]

    if rtype in ("resolved_existing", "alias_match"):
        existing_id = resolution["company_id"]
        print(f"  ℹ️  Company already in Meridian: {existing_id} ({rtype})")
        if not force:
            print(f"  Use --force to re-research an existing company.")
            print(f"  Or use the Company Database tab to view their current profile.")
            return
        print(f"  --force flag set: proceeding with research for {existing_id}")

    elif rtype == "unresolved":
        print(f"  ⚠️  Possible alias conflict detected:")
        print(f"     '{company_name}' is {resolution['fuzzy_ratio']:.0%} similar to "
              f"'{resolution['fuzzy_match']}' → {resolution['fuzzy_company_id']}")
        print(f"     If this is a new company, use --force to proceed.")
        print(f"     If this is an alias, add it via company_aliases table first.")
        if not force:
            return
        print(f"  --force flag set: treating as candidate_new.")

    else:
        # candidate_new — normal path
        print(f"  ✅ New company candidate: '{company_name}' (suggested_id: {resolution['canonical_name']})")

    company_id = resolution.get("company_id")  # None for new candidates

    # ── Model-tier guard ─────────────────────────────────────────────────────
    # Haiku hallucinates drug names and fabricates pipeline data.
    # Live writes to discovery_queue require Sonnet quality.
    _active_model = os.environ.get("INTAKE_MODEL", "claude-sonnet-4-6")
    if not dry_run and "haiku" in _active_model.lower():
        print(f"\n  ❌ Model tier error: INTAKE_MODEL='{_active_model}' cannot be used for live writes.")
        print(f"     Haiku hallucinates company pipelines — fabricated drug names may enter discovery_queue.")
        print(f"     Set INTAKE_MODEL=claude-sonnet-4-6 (or unset INTAKE_MODEL) for live runs.")
        print(f"     Use --dry-run with Haiku for fast structural validation only.")
        return

    # ── Step 2: Research ──────────────────────────────────────────────────────
    print("\n[2/4] Researching company across all Meridian areas...")
    research = research_company(company_name, verbose=verbose)
    if not research:
        print("  ❌ Research failed. Cannot proceed.")
        return

    # ── Step 3: Score area relevance ──────────────────────────────────────────
    print("\n[3/4] Scoring area relevance...")
    relevant_areas = get_relevant_areas(research)

    if not relevant_areas:
        print("  No areas meet minimum evidence threshold.")
        print("  This company may not be relevant to active Meridian areas.")
        _print_area_map(company_name, research, [], [])
        return

    for area in relevant_areas:
        print(f"  • {area['area_id']:<8} {area['relevance']:<15} confidence={area['confidence']:.0%}")

    # ── Step 4: Write queue rows ──────────────────────────────────────────────
    print(f"\n[4/4] Writing {len(relevant_areas)} row(s) to discovery_queue...")
    written = write_queue_rows(
        company_name   = company_name,
        company_id     = company_id,
        resolution     = resolution,
        research       = research,
        relevant_areas = relevant_areas,
        run_id         = run_id,
        dry_run        = dry_run,
    )

    # ── Summary ───────────────────────────────────────────────────────────────
    _print_area_map(company_name, research, relevant_areas, written)


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Company-First Discovery Engine — research a company and route it to discovery_queue",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/company_intake.py --company "Akeso"
  python scripts/company_intake.py --company "Hengrui Medicine" --verbose
  python scripts/company_intake.py --company "Zenas BioPharma" --dry-run
  python scripts/company_intake.py --company "AbbVie" --force  # re-research existing
        """,
    )
    parser.add_argument("--company",  required=True, help="Company name to research")
    parser.add_argument("--dry-run",  action="store_true", help="Research but do not write to Supabase")
    parser.add_argument("--verbose",  action="store_true", help="Print extra debug info")
    parser.add_argument("--force",    action="store_true",
                        help="Proceed even if company exists in DB or fuzzy conflict detected")
    args = parser.parse_args()

    run_intake(
        company_name = args.company,
        dry_run      = args.dry_run,
        verbose      = args.verbose,
        force        = args.force,
    )
