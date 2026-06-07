#!/usr/bin/env python3
"""
Meridian BD Platform — Drug Enrichment Pipeline
=================================================
Systematic enrichment for individual drugs — parallel to company_enrichment.py
but drug-centric. Called by weekend_sprint.py Block B phases.

ARCHITECTURE (mirrors company_enrichment.py 7-step model):
  Drug record (Supabase)
    → Coverage audit (which fields are missing?)
    → Context assembly (company, trials, indications, targets)
    → Claude enrichment (structured Pydantic output)
    → Source validation (validate_source_url before storing)
    → Supabase write (patch drug, upsert enrichment_run)
    → enriched_field_log (old_value captured first)

USAGE:
  python scripts/drug_enrichment.py --drug-id <uuid>
  python scripts/drug_enrichment.py --coverage-below 40 --limit 30
  python scripts/drug_enrichment.py --coverage-below 40 --dry-run

ENVIRONMENT:
  ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY
"""

import os
import sys
import json
import time
import datetime
import argparse
import re
from typing import Optional, List, Dict, Any

from _common import load_credentials, log  # noqa: E402
import _db
import ai.client as ai_client
from ai.client import PromptConfig

# ── Optional: import model_comparison logger if available ─────────────────────
try:
    from model_comparison import log_enrichment_run, update_enrichment_run, patch_enrichment_run
    _MODEL_COMPARISON_AVAILABLE = True
except ImportError:
    _MODEL_COMPARISON_AVAILABLE = False
    def log_enrichment_run(*args, **kwargs): return None
    def update_enrichment_run(*args, **kwargs): return False
    def patch_enrichment_run(*args, **kwargs): return False


# ══════════════════════════════════════════════════════════════════════════════
# CREDENTIALS
# ══════════════════════════════════════════════════════════════════════════════

_url, _key, _ak = load_credentials()
_db.init_db(_url, _key)
ai_client.setup(_ak)

TODAY   = datetime.datetime.utcnow().strftime("%Y-%m-%d")
NOW_ISO = datetime.datetime.utcnow().isoformat()

_DRUG_ENRICH_CFG = PromptConfig(
    name="drug_enrichment",
    system="You are a BD intelligence analyst. Return ONLY valid JSON — no markdown fences, no commentary.",
    model="claude-sonnet-4-6",
    max_tokens=800,
)

# ── Ailux context (constant across all drug enrichments) ──────────────────────
AILUX_CONTEXT = """
Ailux Biotherapeutics is developing a TL1A×IL-23p19 bispecific antibody for IBD
(ulcerative colitis and Crohn's disease). This is the first dual-pathway bispecific
targeting both the TL1A (TNFSF15) and IL-23p19 pathways simultaneously.

TL1A is a TNF superfamily cytokine strongly expressed in IBD mucosa that drives
Th1/Th17 inflammation and tissue remodeling. Anti-TL1A antibodies (tulisokibart,
duvakitug, afimkibart) are in Phase 2-3 for IBD with strong efficacy signals.

IL-23p19 antibodies (risankizumab, mirikizumab, guselkumab) are approved or
Phase 3 for IBD. Blocking both pathways simultaneously could achieve superior
response rates in refractory patients.

Ailux's strategic questions:
1. Which companies have overlapping assets that threaten this program?
2. Which companies could be partnership/licensing targets?
3. What is the competitive differentiation thesis vs mono-therapies?
4. Which drugs show unmet need that Ailux's bispecific could address?
"""

# ── Valid overlap values ───────────────────────────────────────────────────────
VALID_OVERLAPS = {"Direct", "Adjacent", "Same-Space", "None"}

# ── Valid catalog categories ───────────────────────────────────────────────────
VALID_CATEGORIES = {"Immunology", "Oncology", "Small Molecule", "Pipeline"}

# ── Stage normalization ────────────────────────────────────────────────────────
STAGE_ALIASES = {
    "phase i":   "Phase 1",
    "phase ii":  "Phase 2",
    "phase iii": "Phase 3",
    "phase1":    "Phase 1",
    "phase2":    "Phase 2",
    "phase3":    "Phase 3",
}


def normalize_stage(raw: str) -> str:
    s = (raw or "").strip()
    low = s.lower()
    return STAGE_ALIASES.get(low, s)


# sb_get / sb_patch / sb_post provided by _db module


# ══════════════════════════════════════════════════════════════════════════════
# SOURCE URL VALIDATION
# (mirrors company_enrichment.py validate_source_url)
# ══════════════════════════════════════════════════════════════════════════════

def validate_source_url(url: str, context: str = "") -> Optional[str]:
    """Validate a source URL. Returns url if valid, None if broken/fabricated."""
    import urllib.request as _urlreq
    import urllib.error as _urlerr

    if not url:
        return None
    url = url.strip()

    if not url.startswith("http"):
        log(f"  E7 [{context}]: source_url rejected (no http): {url[:80]}", indent=2)
        return None

    # Truncation check
    if len(url) > 80 and not url.endswith(('/', '.html', '.pdf', '.htm', '.json')) \
            and url[-1].isalpha() and url[-2].isalpha():
        log(f"  E7 [{context}]: source_url appears truncated: {url[:80]}", indent=2)
        return None

    # NCT hallucination check
    nct_match = re.search(r'NCT(\d+)', url)
    if nct_match and len(nct_match.group(1)) != 8:
        log(f"  E7 [{context}]: malformed NCT number: {url[:80]}", indent=2)
        return None

    # Generic URL warning
    GENERIC_PATTERNS = [
        (r'/pipeline/?$', "generic pipeline page"),
        (r'/programs/?$', "generic programs page"),
        (r'\.com/?$',     "company homepage"),
    ]
    for pattern, label in GENERIC_PATTERNS:
        if re.search(pattern, url, re.I):
            log(f"  E7 [{context}]: {label} (weak evidence): {url[:80]}", indent=2)
            return url

    # HTTP HEAD check
    ua = {"User-Agent": "Mozilla/5.0 (BD-Platform-Audit/1.0)"}
    try:
        req = _urlreq.Request(url, method="HEAD", headers=ua)
        with _urlreq.urlopen(req, timeout=6) as r:
            status = r.status
    except _urlerr.HTTPError as e:
        status = e.code
        if e.code == 405:
            # Try GET
            try:
                req2 = _urlreq.Request(url, method="GET", headers=ua)
                with _urlreq.urlopen(req2, timeout=6) as r2:
                    status = r2.status
            except Exception:
                status = 0
    except Exception:
        status = 0

    if status in (404, 410):
        log(f"  E7 [{context}]: HTTP {status} — nulling url: {url[:80]}", indent=2)
        return None
    if status == 0:
        log(f"  E7 [{context}]: unreachable — nulling url: {url[:80]}", indent=2)
        return None

    return url


# ══════════════════════════════════════════════════════════════════════════════
# DRUG CONTEXT ASSEMBLY
# ══════════════════════════════════════════════════════════════════════════════

def fetch_drug_context(drug_id: str) -> Dict:
    """Fetch all known context for a drug from Supabase."""
    ctx = {}

    # Core drug record
    drugs = _db.sb_get("drugs", {
        "id": f"eq.{drug_id}",
        "select": (
            "id,name,brand_name,target,stage,mechanism,modality,company_id,"
            "overlap,overlap_rationale,bd_angle,risk_summary,drug_summary,"
            "ailux_angle,differentiation_thesis,source_url,catalog_category,"
            "patient_population,primary_endpoint,nct_ids,partner_company,"
            "partnership_type,partnership_verified"
        ),
        "limit": "1"
    })
    if not drugs:
        return {}
    ctx["drug"] = drugs[0]

    # Company name
    try:
        company_id = ctx["drug"].get("company_id")
        if company_id:
            cos = _db.sb_get("companies", {
                "id": f"eq.{company_id}",
                "select": "id,name,hq_country,status,parent_company_id",
                "limit": "1"
            })
            ctx["company"] = cos[0] if cos else {}
    except Exception:
        ctx["company"] = {}

    # Drug targets
    try:
        targets = _db.sb_get("drug_targets", {
            "drug_id": f"eq.{drug_id}",
            "select": "target_name,area_id,is_primary",
            "limit": "10"
        })
        ctx["targets"] = targets
    except Exception:
        ctx["targets"] = []

    # Drug indications
    try:
        indications = _db.sb_get("drug_indications", {
            "drug_id": f"eq.{drug_id}",
            "select": "indication_name,indication_id,is_primary",
            "limit": "10"
        })
        ctx["indications"] = indications
    except Exception:
        ctx["indications"] = []

    # Active trials
    try:
        nct_ids = ctx["drug"].get("nct_ids") or []
        if nct_ids:
            trials = []
            for nct in nct_ids[:3]:
                t = _db.sb_get("trials", {
                    "nct_id": f"eq.{nct}",
                    "select": "nct_id,phase,status,primary_completion_date,title",
                    "limit": "1"
                })
                trials.extend(t)
            ctx["trials"] = trials
        else:
            ctx["trials"] = []
    except Exception:
        ctx["trials"] = []

    return ctx


def build_enrichment_prompt(ctx: Dict) -> str:
    """Build the Claude enrichment prompt from drug context."""
    drug = ctx.get("drug", {})
    company = ctx.get("company", {})
    targets = ctx.get("targets", [])
    indications = ctx.get("indications", [])
    trials = ctx.get("trials", [])

    # Format targets
    target_str = drug.get("target") or ""
    if targets:
        primary = [t["target_name"] for t in targets if t.get("is_primary")]
        all_tgts = [t["target_name"] for t in targets]
        target_str = " | ".join(primary or all_tgts)

    # Format indications
    ind_str = ", ".join(
        [i.get("indication_name") or "" for i in indications if i.get("indication_name")]
    ) or "unknown"

    # Format trials
    trial_str = ""
    for t in trials[:3]:
        trial_str += (
            f"  NCT: {t.get('nct_id')}, Phase: {t.get('phase')}, "
            f"Status: {t.get('status')}, "
            f"PCD: {t.get('primary_completion_date', 'unknown')}\n"
        )

    prompt = f"""You are a BD intelligence analyst for Ailux Biotherapeutics.

{AILUX_CONTEXT}

Enrich the following drug record with accurate BD intelligence.

DRUG RECORD:
  Name: {drug.get('name')}
  Brand name: {drug.get('brand_name') or 'none'}
  Target(s): {target_str}
  Stage: {drug.get('stage')}
  Mechanism: {drug.get('mechanism') or 'unknown'}
  Modality: {drug.get('modality') or 'unknown'}
  Company: {company.get('name') or drug.get('company_id') or 'unknown'}
  Indications: {ind_str}
  Partner company: {drug.get('partner_company') or 'none'}
  Existing BD angle: {drug.get('bd_angle') or 'MISSING'}
  Existing risk summary: {drug.get('risk_summary') or 'MISSING'}
  Existing overlap: {drug.get('overlap') or 'MISSING'}

Active trials:
{trial_str or '  None known'}

INSTRUCTIONS:
Fill in ALL missing fields below. For fields already set, you may improve them
but only if you have better information.

Rules:
1. overlap must be EXACTLY one of: Direct | Adjacent | Same-Space | None
   - Direct = same dual target (TL1A×IL-23p19) or direct monotherapy competitor
   - Adjacent = related pathway (TL1A mono, IL-23 mono, TNF, JAK, integrin for IBD)
   - Same-Space = same indication (IBD) but different mechanism
   - None = different indication and mechanism
2. source_url: ONLY include if you can cite a real, specific URL (CT.gov NCT link,
   press release, SEC 8-K). Do NOT fabricate. Omit if unsure.
3. bd_angle: 2-3 sentences. Stage-aware: if Phase 1/preclinical, note timing uncertainty.
4. risk_summary: 1-2 sentences on key development risk.
5. drug_summary: 2-3 sentences describing the drug and its mechanism.
6. catalog_category: one of Immunology | Oncology | Small Molecule | Pipeline
7. target field = molecular targets ONLY. Never include company names in target.
8. If brand_name is set, stage MUST be an approved variant. If not approved, clear brand_name.

Return ONLY valid JSON with these keys:
{{
  "mechanism": "string or null",
  "drug_summary": "string or null",
  "ailux_angle": "string or null (specific to Ailux TL1A×IL-23p19 program)",
  "bd_angle": "string or null",
  "risk_summary": "string or null",
  "overlap": "Direct|Adjacent|Same-Space|None or null",
  "overlap_rationale": "string or null",
  "differentiation_thesis": "string or null",
  "patient_population": "string or null",
  "primary_endpoint": "string or null",
  "source_url": "string or null (real URL only)",
  "catalog_category": "Immunology|Oncology|Small Molecule|Pipeline or null"
}}
"""
    return prompt


# ══════════════════════════════════════════════════════════════════════════════
# ENRICHMENT FIELDS AUDIT
# ══════════════════════════════════════════════════════════════════════════════

ENRICHABLE_FIELDS = [
    "mechanism", "drug_summary", "ailux_angle", "bd_angle", "risk_summary",
    "overlap", "overlap_rationale", "differentiation_thesis",
    "patient_population", "primary_endpoint", "catalog_category",
]

def compute_coverage(drug: dict) -> int:
    """Compute simple coverage score for a drug record."""
    filled = sum(1 for f in ENRICHABLE_FIELDS if drug.get(f))
    has_target  = 1 if drug.get("target") else 0
    has_stage   = 1 if drug.get("stage")  else 0
    has_source  = 1 if drug.get("source_url") else 0
    total_fields = len(ENRICHABLE_FIELDS) + 3
    return round((filled + has_target + has_stage + has_source) / total_fields * 100)


def fields_to_enrich(drug: dict) -> List[str]:
    """Return list of fields that need enrichment."""
    missing = [f for f in ENRICHABLE_FIELDS if not drug.get(f)]
    if not drug.get("target"):
        missing.insert(0, "target")
    return missing


# ══════════════════════════════════════════════════════════════════════════════
# VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

def validate_output(raw: dict, drug_name: str) -> Dict:
    """Validate and sanitize LLM output before writing to Supabase."""
    validated = {}

    # overlap
    ov = raw.get("overlap")
    if ov and ov in VALID_OVERLAPS:
        validated["overlap"] = ov
    elif ov:
        log(f"  WARN: invalid overlap value '{ov}' — dropped", indent=2)

    # catalog_category
    cc = raw.get("catalog_category")
    if cc and cc in VALID_CATEGORIES:
        validated["catalog_category"] = cc
    elif cc:
        log(f"  WARN: invalid catalog_category '{cc}' — dropped", indent=2)

    # source_url — validate before storing
    url = raw.get("source_url")
    if url:
        validated_url = validate_source_url(url, context=drug_name)
        if validated_url:
            validated["source_url"] = validated_url
        # else: omit (validate_source_url already logged the rejection)

    # Text fields — basic length guards
    TEXT_FIELDS = {
        "mechanism": 300,
        "drug_summary": 600,
        "ailux_angle": 600,
        "bd_angle": 600,
        "risk_summary": 400,
        "overlap_rationale": 400,
        "differentiation_thesis": 600,
        "patient_population": 200,
        "primary_endpoint": 200,
    }
    for field, max_len in TEXT_FIELDS.items():
        val = raw.get(field)
        if val and isinstance(val, str) and val.strip() and val != "null":
            validated[field] = val.strip()[:max_len]

    # brand_name governance: if brand_name is set in output, check stage
    # (we don't write brand_name directly — that's managed elsewhere)

    return validated


# ══════════════════════════════════════════════════════════════════════════════
# ENRICHMENT LOG
# ══════════════════════════════════════════════════════════════════════════════

def log_field_change(drug_id: str, field: str,
                     old_value: Any, new_value: Any,
                     enrichment_run_id: Optional[str] = None,
                     model_confidence: float = 0.8,
                     source_url: Optional[str] = None,
                     skill_name: str = "drug_enrich"):
    """Write to enriched_field_log with full provenance (old_value, enrichment_run_id, was_changed)."""
    try:
        old_str = str(old_value) if old_value is not None else None
        new_str = str(new_value) if new_value is not None else None
        was_changed = old_str != new_str if old_str is not None else True
        _now_ts = datetime.datetime.utcnow().isoformat()
        row = {
            "entity_id":        drug_id,
            "entity_type":      "drug",
            "field_name":       field,
            "old_value":        old_str,
            "enriched_value":   new_str,
            "was_changed":      was_changed,
            "model_confidence": model_confidence,
            "enriched_at":      _now_ts,
            "field_label":      "pending",
            "label_source":     "pending",
        }
        if enrichment_run_id:
            row["enrichment_run_id"] = enrichment_run_id
        if source_url:
            row["source_citation"] = source_url
        _db.sb_post("enriched_field_log", row)
    except Exception as e:
        log(f"  enriched_field_log write failed for {field}: {e}", indent=3)


# ══════════════════════════════════════════════════════════════════════════════
# CORE ENRICHMENT FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def enrich_drug(drug_id: str, dry_run: bool = False) -> bool:
    """Enrich a single drug via the LangGraph pipeline. Returns True on success."""
    from pipeline.drug.graph import build_drug_graph
    from pipeline.drug.state import DrugPipelineState

    log(f"Enriching drug: {drug_id}", indent=0)
    t0 = time.time()

    state = DrugPipelineState(drug_id=drug_id, dry_run=dry_run)
    app = build_drug_graph()
    result = app.invoke(state)

    elapsed = time.time() - t0
    log(f"  Pipeline completed in {elapsed:.1f}s | "
        f"nodes={result.nodes_completed} | ok={result.ok}", indent=1)

    if result.errors:
        for err in result.errors:
            log(f"  ERROR: {err}", indent=2)

    return result.ok


# ══════════════════════════════════════════════════════════════════════════════
# BATCH RUNNER
# ══════════════════════════════════════════════════════════════════════════════

def run_batch(coverage_below: int = 40, limit: int = 30,
              dry_run: bool = False, area: str = None) -> Dict:
    """
    Run drug enrichment for all drugs below coverage threshold.
    Returns summary dict.
    """
    log(f"Drug enrichment batch: coverage<{coverage_below}, limit={limit}, "
        f"dry_run={dry_run}, area={area}")

    summary = {"attempted": 0, "succeeded": 0, "failed": 0, "skipped": 0}

    # Get drugs by coverage
    drug_ids = []
    try:
        scores = _db.sb_get("coverage_scores", {
            "entity_type":   "eq.drug",
            "coverage_score": f"lt.{coverage_below}",
            "select":        "entity_id,coverage_score",
            "order":         "coverage_score.asc",
            "limit":         str(limit),
        })
        drug_ids = [s["entity_id"] for s in scores if s.get("entity_id")]
    except Exception:
        pass

    if not drug_ids:
        # Fallback: drugs missing key enrichment fields
        try:
            query_params = {
                "select": "id,name,target,stage,bd_angle,overlap",
                "bd_angle": "is.null",
                "limit": str(limit),
                "order": "stage.desc",
            }
            if area:
                # Filter by area_id via drug_targets join
                area_drugs = _db.sb_get("drug_targets", {
                    "area_id": f"eq.{area}",
                    "select":  "drug_id",
                    "limit":   str(limit),
                })
                if area_drugs:
                    area_drug_ids = [d["drug_id"] for d in area_drugs if d.get("drug_id")]
                    if area_drug_ids:
                        query_params["id"] = f"in.({','.join(area_drug_ids[:limit])})"
                        del query_params["bd_angle"]

            drugs = _db.sb_get("drugs", query_params)
            drug_ids = [d["id"] for d in drugs]
        except Exception as e:
            log(f"Fallback drug query failed: {e}")
            return summary

    log(f"Found {len(drug_ids)} drugs to enrich")

    # Check for recently-enriched drugs (skip if enriched within 7 days)
    recent_cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=7)).isoformat()
    try:
        recently_enriched = _db.sb_get("enrichment_runs", {
            "entity_type": "eq.drug",
            "skill_name":  "eq.drug_enrich",
            "created_at":  f"gt.{recent_cutoff}",
            "select":      "entity_id",
            "limit":       "500",
        })
        recent_ids = {r["entity_id"] for r in recently_enriched}
    except Exception:
        recent_ids = set()

    for drug_id in drug_ids[:limit]:
        if drug_id in recent_ids:
            log(f"  Skip {drug_id}: enriched within 7 days", indent=1)
            summary["skipped"] += 1
            continue

        summary["attempted"] += 1
        try:
            success = enrich_drug(drug_id, dry_run=dry_run)
            if success:
                summary["succeeded"] += 1
            else:
                summary["failed"] += 1
        except Exception as e:
            summary["failed"] += 1
            log(f"  Unhandled error for drug {drug_id}: {e}", indent=1)

        time.sleep(2)  # rate limit: ~30 req/min

    log(f"\nBatch complete: attempted={summary['attempted']} "
        f"succeeded={summary['succeeded']} failed={summary['failed']} "
        f"skipped={summary['skipped']}")
    return summary


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Meridian Drug Enrichment Pipeline"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--drug-id", help="Enrich a single drug by UUID")
    group.add_argument("--coverage-below", type=int,
                       help="Enrich all drugs with coverage_score below this value")
    parser.add_argument("--limit", type=int, default=30,
                        help="Max drugs to enrich in batch (default: 30)")
    parser.add_argument("--area", help="Filter by area_id (tl1a, tslp, il4ra, etc.)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch and synthesize but do not write to Supabase")
    args = parser.parse_args()

    if args.drug_id:
        success = enrich_drug(args.drug_id, dry_run=args.dry_run)
        sys.exit(0 if success else 1)
    else:
        summary = run_batch(
            coverage_below=args.coverage_below,
            limit=args.limit,
            dry_run=args.dry_run,
            area=args.area,
        )
        failed = summary.get("failed", 0)
        sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
