"""
Node: score_completeness
Computes the post-enrichment completeness score and patches company_profiles.

Self-contained — no dependency on company_enrichment.py.
"""
from __future__ import annotations

import datetime
import os
import sys

_HERE     = os.path.dirname(os.path.abspath(__file__))
_PIPELINE = os.path.dirname(_HERE)
_SCRIPTS  = os.path.dirname(_PIPELINE)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from _common import log          # noqa: E402
from _db import sb_patch         # noqa: E402
from pipeline.state import PipelineState  # noqa: E402


# ── Core logic ────────────────────────────────────────────────────────────────

def _score_company_completeness(company_id: str, area_id: str,
                                 data: dict, ctx: dict) -> dict:
    """
    Compute completeness score and missing_fields for a company×area.

    Merges newly-written data (from Claude's output) with pre-enrichment
    context (ctx) to reflect the true post-run state without an extra DB read.

    Rubric (stage-aware, weights sum to 100):
      platform_intelligence present + non-empty  → 20 pts  (always)
      bd_intelligence present + non-empty        → 20 pts  (always)
      drugs[*].drug_summary all populated        → 15 pts  (always)
      drugs[*].key_data for Phase 2+ drugs       → 10 pts  (stage-gated)
      drugs[*].mechanism_detail all populated    → 10 pts  (always)
      ≥1 catalyst with source_url               → 10 pts  (always)
      key_risk + why_it_matters populated        → 10 pts  (always)
      overlap_rationale for Direct drugs         →  5 pts  (Direct competitors only)

    Returns {"score": int, "tier": str, "missing": list[str]}.
    """
    score = 0
    missing = []

    cp               = data.get("company_profile", {}) or {}
    existing_profile = ctx.get("profile", {}) or {}

    # Prefer newly-written values; fall back to pre-run values
    pi          = cp.get("platform_intelligence") or existing_profile.get("platform_intelligence") or {}
    bi          = cp.get("bd_intelligence")       or existing_profile.get("bd_intelligence")       or {}
    key_risk    = (cp.get("key_risk")       or existing_profile.get("key_risk")       or "").strip()
    why_matters = (cp.get("why_it_matters") or existing_profile.get("why_it_matters") or "").strip()

    # ── 1. platform_intelligence (20 pts) ─────────────────────────────────
    if pi.get("facts") or pi.get("direction") or pi.get("assessment"):
        score += 20
    else:
        missing.append("company_profiles.platform_intelligence")

    # ── 2. bd_intelligence (20 pts) ───────────────────────────────────────
    if bi.get("transactions") or bi.get("assessment") or bi.get("profile"):
        score += 20
    else:
        missing.append("company_profiles.bd_intelligence")

    # ── 3-5. Drug-level fields ─────────────────────────────────────────────
    drug_updates_by_id: dict = {}
    for du in data.get("drug_updates", []):
        did = du.get("drug_id") or ""
        if did:
            drug_updates_by_id[did] = du

    drugs = ctx.get("drugs", [])
    LATE_STAGE_KEYS = {"Phase 2", "Phase 2/Phase 3", "Phase 3", "Approved"}

    all_have_summary   = bool(drugs)
    all_have_mechanism = bool(drugs)
    late_stage_drugs   = []

    for drug in drugs:
        did   = drug.get("id", "")
        du    = drug_updates_by_id.get(did, {})
        stage = drug.get("stage") or ""

        drug_summary     = (du.get("drug_summary")     or drug.get("drug_summary")     or "").strip()
        mechanism_detail = (du.get("mechanism_detail")  or drug.get("mechanism_detail")  or "").strip()

        if not drug_summary:
            all_have_summary = False
            missing.append(f"drugs.drug_summary[{did}]")
        if not mechanism_detail:
            all_have_mechanism = False
            missing.append(f"drugs.mechanism_detail[{did}]")

        if any(p in stage for p in LATE_STAGE_KEYS):
            late_stage_drugs.append((did, du, drug))

    # 3. drug_summary (15 pts)
    if all_have_summary:
        score += 15

    # 4. key_data for Phase 2+ drugs (10 pts) — stage-gated
    if late_stage_drugs:
        all_have_key_data = True
        for (did, du, drug) in late_stage_drugs:
            key_data = (du.get("key_data") or drug.get("key_data") or "").strip()
            if not key_data:
                all_have_key_data = False
                missing.append(f"drugs.key_data[{did}]")
        if all_have_key_data:
            score += 10
    else:
        score += 10  # no late-stage drugs; stage doesn't require key_data

    # 5. mechanism_detail (10 pts)
    if all_have_mechanism:
        score += 10

    # ── 6. Catalyst with source_url (10 pts) ──────────────────────────────
    existing_cats_with_url = [c for c in ctx.get("catalysts", []) if c.get("source_url")]
    new_cats_with_url      = [c for c in data.get("catalysts", [])  if c.get("source_url")]
    if existing_cats_with_url or new_cats_with_url:
        score += 10
    else:
        missing.append("catalysts.source_url")

    # ── 7. key_risk + why_it_matters (10 pts) ─────────────────────────────
    if key_risk and why_matters:
        score += 10
    else:
        if not key_risk:
            missing.append("company_profiles.key_risk")
        if not why_matters:
            missing.append("company_profiles.why_it_matters")

    # ── 8. overlap_rationale for Direct drugs (5 pts) ─────────────────────
    direct_drugs = [
        d for d in drugs
        if (drug_updates_by_id.get(d.get("id", ""), {}).get("overlap") or d.get("overlap")) == "Direct"
    ]
    if direct_drugs:
        all_have_rationale = True
        for drug in direct_drugs:
            did = drug.get("id", "")
            du  = drug_updates_by_id.get(did, {})
            rationale = (du.get("overlap_rationale") or drug.get("overlap_rationale") or "").strip()
            if not rationale:
                all_have_rationale = False
                missing.append(f"drugs.overlap_rationale[{did}]")
        if all_have_rationale:
            score += 5
    else:
        score += 5  # no Direct drugs → requirement doesn't apply

    # ── 9. Molecule-level fields (tracked, no score impact) ───────────────
    mol_updates_by_id: dict = {}
    for mu in (data.get("molecule_updates") or []):
        did = mu.get("drug_id") or ""
        if did:
            mol_updates_by_id[did] = mu

    MOL_REQUIRED = ["format", "modality", "differentiation_claim"]
    MOL_DESIRED  = ["epitope", "affinity_kd", "fc_engineering", "lowest_active_dose"]

    for drug in drugs:
        did = drug.get("id", "")
        mu  = mol_updates_by_id.get(did, {})
        for field in MOL_REQUIRED:
            val = (mu.get(field) or "").strip() if isinstance(mu.get(field), str) else mu.get(field)
            if not val:
                missing.append(f"molecule_intelligence.{field}[{did}]")
        fs = mu.get("field_status") or {}
        for field in MOL_DESIRED:
            if fs.get(field) == "unknown" or (field not in fs and not mu.get(field)):
                missing.append(f"molecule_intelligence.{field}[{did}]")

    tier = "strong" if score >= 70 else ("partial" if score >= 40 else "thin")
    return {"score": score, "tier": tier, "missing": list(dict.fromkeys(missing))}


# ── Pipeline node ─────────────────────────────────────────────────────────────

def score_completeness(state: PipelineState) -> PipelineState:
    """
    Merges newly-written data with pre-enrichment context to compute a
    completeness score (0–100) and tier, without an extra DB round-trip.

    Patches company_profiles with:
      completeness_score, missing_fields, completeness_checked_at

    Populates state.completeness_score, .completeness_tier, .completeness_missing.
    """
    cs = _score_company_completeness(
        state.company_id,
        state.area_id,
        state.validated_data,
        state.ctx.as_dict(),
    )
    state.completeness_score   = cs["score"]
    state.completeness_tier    = cs["tier"]
    state.completeness_missing = cs["missing"]

    if not state.dry_run:
        ok = sb_patch(
            "company_profiles",
            {
                "completeness_score":      state.completeness_score,
                "missing_fields":          state.completeness_missing,
                "completeness_checked_at": datetime.datetime.utcnow().isoformat(),
            },
            {
                "company_id": f"eq.{state.company_id}",
                "area_id":    f"eq.{state.area_id}",
            },
        )
        if not ok:
            log("  ⚠ completeness score patch failed — profile row may not exist yet", indent=1)

    state.mark_complete("score_completeness")
    return state
