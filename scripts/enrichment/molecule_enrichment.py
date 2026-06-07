#!/usr/bin/env python3
"""
Molecule Intelligence Enrichment — Targeted Drug-Level Script
==============================================================
Enriches molecule_intelligence for specific drug IDs using the Claude API.
Operates on drug context from Supabase — no web search (fast, uses training knowledge).

Confidence levels written:
  high   — well-characterized public molecule (approved drug, CT.gov data)
  medium — partially characterized (Phase 1/2, some public disclosure)
  low    — preclinical / minimal public data (inferred from target + company)

Usage:
  # Single drug
  python3 scripts/molecule_enrichment.py --drug-ids risankizumab

  # Multiple drugs
  python3 scripts/molecule_enrichment.py --drug-ids duvakitug spy002 spy003

  # Full priority list (defined at bottom of file)
  python3 scripts/molecule_enrichment.py --priority

  # Dry run (no writes to Supabase)
  python3 scripts/molecule_enrichment.py --drug-ids duvakitug --dry-run

Environment:
  ANTHROPIC_API_KEY     — required
  SUPABASE_URL          — required
  SUPABASE_SERVICE_KEY  — required
"""

import os, sys, json, re, argparse, textwrap, hashlib
from datetime import datetime, timezone

from _common import load_credentials, log
import _db
import ai.client as ai_client
from ai.client import PromptConfig

_url, _key, _ak = load_credentials()
_db.init_db(_url, _key)
ai_client.setup(_ak)

MODEL   = "claude-sonnet-4-6"
NOW_ISO = datetime.now(timezone.utc).isoformat()

# Priority order for --priority flag
# Direct TL1A/bispecific competitors → Adjacent IBD backbones → Watch/reference
PRIORITY_DRUG_IDS = [
    "duvakitug",       # Sanofi TL1A Phase 3 — top Direct competitor
    "spy002",          # Spyre TL1A Phase 2
    "spy072",          # Spyre TL1A Phase 2
    "spy001",          # Spyre α4β7 Phase 2
    "spy003",          # Spyre IL-23 Phase 2
    "spy120",          # Spyre α4β7+TL1A bispecific Phase 2
    "spy130",          # Spyre α4β7+IL-23 bispecific Phase 2
    "spy230",          # Spyre IL-23+TL1A bispecific Phase 2
    "qx030n",          # Qyuns TL1A×IL-23p19 Phase 1
    "ro7837195",       # Roche IL-23p40×TL1A Phase 2
    "fg-m701",         # AbbVie TL1A Phase 1 (display: ABBV-701)
    "abbv-382",        # AbbVie α4β7 Phase 2
    "abbv-668",        # AbbVie RIPK1 Phase 2
    "lutikizumab",     # AbbVie IL-1α/β Phase 3
    "risankizumab",    # Skyrizi — approved IL-23p19 (reference drug)
    "guselkumab",      # Tremfya — approved IL-23p19 (reference drug)
    "mirikizumab",     # Omvoh — approved IL-23p19 (reference drug)
    "upadacitinib",    # Rinvoq — approved JAK1 (reference drug)
    "ustekinumab",     # Stelara — approved IL-12/23p40 (reference drug)
    "golimumab",       # Simponi — approved TNFα (reference drug)
]

_MOL_INTEL_CFG = PromptConfig(
    name="molecule_intel",
    system="",
    model=MODEL,
    max_tokens=1500,
)

# ── Helpers ─────────────────────────────────────────────────────────────────

def make_canonical_id(drug_id):
    """Generate a deterministic canonical_drug_id for drugs that lack one."""
    h = hashlib.md5(drug_id.encode()).hexdigest().upper()[:8]
    return f"CANON_DRUG_{h}"


def ensure_canonical_id(drug):
    """If drug lacks canonical_drug_id, generate one, insert stub into canonical_drugs,
    then PATCH it into the drugs table. Inserting the canonical_drugs row first avoids
    the FK constraint violation on molecule_intelligence.canonical_drug_id."""
    if drug.get("canonical_drug_id"):
        return drug["canonical_drug_id"]

    canon = make_canonical_id(drug["id"])
    stub = {
        "canonical_id":   canon,
        "canonical_name": drug.get("display_name") or drug.get("drug_name") or drug["id"],
        "is_active":      True,
        "confidence_score": 50,
    }
    _db.sb_upsert("canonical_drugs", stub)
    _db.sb_patch(
        "drugs",
        {"canonical_drug_id": canon},
        {"id": f"eq.{drug['id']}"},
    )
    drug["canonical_drug_id"] = canon
    log(f"  ↳ generated canonical_drug_id: {canon} (stub inserted into canonical_drugs)", indent=1)
    return canon


# ── Fetch drug context ───────────────────────────────────────────────────────

def fetch_drug_context(drug_id):
    """Return drug record + recent trials for context."""
    drugs = _db.sb_get("drugs", {
        "select": "id,display_name,name,company_id,partner_company,target,stage,"
                  "cls,overlap,indication_short,canonical_drug_id,source_url,drug_summary",
        "id": f"eq.{drug_id}",
        "limit": 1,
    })
    drug = drugs[0] if drugs else None

    trials = _db.sb_get("trials", {
        "select": "trial_name,phase,status,indication,n_enrollment,primary_endpoint",
        "drug_id": f"eq.{drug_id}",
        "order": "phase.desc",
        "limit": 5,
    })

    return drug, trials


# ── Build prompt ─────────────────────────────────────────────────────────────

SCHEMA_BLOCK = """
Return a single JSON object with these fields:

{
  "format": "e.g. 'monoclonal antibody', 'bispecific antibody', 'small molecule (JAK1 inhibitor)', 'antibody-drug conjugate'",
  "valency": "e.g. 'monospecific', 'bispecific', 'tetravalent bispecific (2+2)' — null if not applicable",
  "modality": "one of: 'antibody', 'small molecule', 'cell therapy', 'fusion protein', 'ADC'",
  "igg_subclass": "e.g. 'IgG1', 'IgG4', 'IgG2' — null if not antibody or unknown",
  "fc_engineering": "brief description of Fc modifications, e.g. 'YTE half-life extension', 'LALAPG effector-null', 'none known'. Use null only if not an antibody.",
  "epitope": "binding region description if disclosed, e.g. 'receptor-binding domain of TL1A', 'IL-23p19 subunit'. Use 'not publicly disclosed' if unknown.",
  "affinity_kd": "e.g. '0.4 nM (KD)' — null if not publicly disclosed",
  "differentiation_claim": "2-4 sentence BD-focused differentiation argument. What makes this molecule mechanistically or structurally distinct from its competitive class? Include dosing profile, engineering advantages, or clinical data differentiators. This is the single most important field — be specific.",
  "field_status": {
    "format": "confirmed | inferred | unknown",
    "valency": "confirmed | inferred | unknown",
    "modality": "confirmed | inferred | unknown",
    "igg_subclass": "confirmed | inferred | unknown",
    "fc_engineering": "confirmed | inferred | unknown",
    "epitope": "confirmed | inferred | unknown",
    "affinity_kd": "confirmed | inferred | unknown",
    "differentiation_claim": "confirmed | inferred | unknown"
  },
  "confidence": "high | medium | low",
  "source_url": "most authoritative public URL for this molecule (clinicaltrials.gov, company IR, FDA label, peer-reviewed paper). null if none available."
}

Confidence guidance:
- high: approved drug OR Phase 3 drug with published clinical data and known structure
- medium: Phase 1/2 with disclosed format and some clinical data
- low: preclinical, IND-stage, or very limited public disclosure

field_status guidance:
- confirmed: directly stated in a primary source (CT.gov, FDA label, peer-reviewed paper, company IR)
- inferred: reasonable inference from target class, company platform, or related program disclosure
- unknown: genuinely not determinable from available information
"""


def build_prompt(drug, trials):
    display = drug.get("display_name") or drug.get("name") or drug["id"]
    company = drug.get("company_id", "")
    partner = drug.get("partner_company") or ""
    target  = drug.get("target") or ""
    stage   = drug.get("stage") or ""
    cls     = drug.get("cls") or ""
    ind     = drug.get("indication_short") or ""
    summary = drug.get("drug_summary") or ""
    src     = drug.get("source_url") or ""

    trial_lines = ""
    for t in trials:
        trial_lines += f"  - {t.get('trial_name','?')} | {t.get('phase','?')} | {t.get('status','?')} | {t.get('indication','?')}\n"

    prompt = textwrap.dedent(f"""
        You are a biotech intelligence analyst building a molecule intelligence database for BD strategy.

        Characterize the following drug molecule with the precision needed for a pharma BD team.
        Use your training knowledge about this molecule — do NOT fabricate specific KD values or
        structural details you cannot confirm. Mark unknown fields as "unknown" in field_status.

        ## Drug Context

        Drug ID:        {drug["id"]}
        Display name:   {display}
        Company:        {company}{f' (partner: {partner})' if partner else ''}
        Target:         {target}
        Stage:          {stage}
        Class:          {cls}
        Indication:     {ind}
        Summary:        {summary or '(none)'}
        Source URL:     {src or '(none)'}

        ## Clinical Trials (from database)
        {trial_lines.strip() or '(none on file)'}

        ## Your Task
        Produce molecule intelligence for this drug. Focus on:
        1. Molecular format and engineering (IgG subclass, Fc mods, valency)
        2. Mechanistic differentiation vs. others in the same target class
        3. Dosing and PK implications from known structure
        4. What a BD team at a competing company would want to know

        ## Governance Rules (mandatory)
        - ATTRIBUTION: company_id in the database = originator (developer). If you see a licensee
          relationship, note it in source_url context but do NOT suggest changing company_id.
        - BRAND NAME: Only populate brand_name for fully approved drugs. A drug in Phase 1/2/3
          with a brand name is an error — leave brand_name null unless the drug is approved.
        - SOURCE: source_url must be a real, verifiable URL (CT.gov, FDA label, peer-reviewed paper,
          company IR). Do not fabricate. Omit rather than guess.
        - CO-DEV: If co-developed, note partner in source_url context. Do NOT embed partner name
          in the target field. Target = molecular targets only (e.g. "TL1A × IL-23p19").

        {SCHEMA_BLOCK}

        Return only the JSON object, no markdown fences, no commentary.
    """).strip()

    return prompt


# ── Validation ────────────────────────────────────────────────────────────────

VALID_STATUS = {"confirmed", "inferred", "unknown"}
VALID_CONFIDENCE = {"high", "medium", "low"}


def write_mol_intel(drug, parsed, dry_run=False):
    drug_id = drug["id"]
    canonical = ensure_canonical_id(drug)

    raw_fs = parsed.get("field_status") or {}
    field_status = {k: (v if v in VALID_STATUS else "unknown") for k, v in raw_fs.items()}

    confidence = parsed.get("confidence") or "low"
    if confidence not in VALID_CONFIDENCE:
        confidence = "low"

    rec = {
        "drug_id":                 drug_id,
        "format":                  parsed.get("format")               or None,
        "valency":                 parsed.get("valency")              or None,
        "modality":                parsed.get("modality")             or None,
        "igg_subclass":            parsed.get("igg_subclass")         or None,
        "fc_engineering":          parsed.get("fc_engineering")       or None,
        "epitope":                 parsed.get("epitope")              or None,
        "affinity_kd":             parsed.get("affinity_kd")          or None,
        "differentiation_claim":   parsed.get("differentiation_claim") or None,
        "safety_observations":     parsed.get("safety_observations")  or None,
        "field_status":            field_status,
        "confidence":              confidence,
        "source_url":              parsed.get("source_url")           or None,
        "last_enriched_at":        NOW_ISO,
        "enriched_by":             "molecule_enrichment.py",
        "canonical_drug_id":       canonical,
    }
    rec = {k: v for k, v in rec.items() if v is not None or k == "field_status"}

    if dry_run:
        log(f"  [dry] would write: format={rec.get('format')} | "
            f"modality={rec.get('modality')} | confidence={rec.get('confidence')}", indent=1)
        return True

    _db.sb_delete("molecule_intelligence", {"drug_id": f"eq.{drug_id}"})
    result = _db.sb_post("molecule_intelligence", rec)
    ok = result is not None
    if ok:
        log(f"  ✓ written: format={rec.get('format')} | confidence={confidence}", indent=1)
    return ok


# ── Main loop ────────────────────────────────────────────────────────────────

def enrich_drug(drug_id, dry_run=False):
    log(f"\n{'='*60}")
    log(f"Drug: {drug_id}")

    drug, trials = fetch_drug_context(drug_id)
    if not drug:
        log(f"  ✗ drug_id '{drug_id}' not found in drugs table — skipping")
        return False

    display = drug.get("display_name") or drug.get("name") or drug_id
    log(f"  {display} | {drug.get('company_id')} | {drug.get('target')} | {drug.get('stage')}")
    log(f"  {len(trials)} trial(s) on file")

    prompt = build_prompt(drug, trials)

    log("  Calling Claude API...", indent=0)
    result = ai_client.run_json(_MOL_INTEL_CFG, prompt)
    if not result.ok:
        log(f"  ✗ API call or JSON parse failed")
        return False

    parsed = result.data
    log(f"  Parsed: format={parsed.get('format')} | "
        f"confidence={parsed.get('confidence')} | "
        f"source_url={parsed.get('source_url') or 'none'}")

    return write_mol_intel(drug, parsed, dry_run=dry_run)


def main():
    parser = argparse.ArgumentParser(description="Molecule Intelligence Enrichment")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--drug-ids", nargs="+", help="Drug IDs to enrich")
    group.add_argument("--priority", action="store_true", help="Run full priority list")
    parser.add_argument("--dry-run", action="store_true", help="Print results without writing")
    args = parser.parse_args()

    drug_ids = PRIORITY_DRUG_IDS if args.priority else args.drug_ids

    log(f"Molecule Intelligence Enrichment")
    log(f"Model: {MODEL} | Dry run: {args.dry_run}")
    log(f"Drugs to process: {len(drug_ids)}")

    success, failed = 0, []
    for did in drug_ids:
        ok = enrich_drug(did, dry_run=args.dry_run)
        if ok:
            success += 1
        else:
            failed.append(did)

    log(f"\n{'='*60}")
    log(f"Complete: {success}/{len(drug_ids)} succeeded")
    if failed:
        log(f"Failed: {failed}")


if __name__ == "__main__":
    main()
