"""
Node: generate_catalysts
Auto-creates catalyst records from CT.gov trial primary completion dates (Step 4).

Self-contained — no dependency on company_enrichment.py.
"""
from __future__ import annotations

import datetime
import os
import re
import sys
from typing import Optional

_HERE     = os.path.dirname(os.path.abspath(__file__))
_PIPELINE = os.path.dirname(_HERE)
_SCRIPTS  = os.path.dirname(_PIPELINE)
_ENRICH   = os.path.join(_SCRIPTS, "enrichment")
for _p in (_SCRIPTS, _ENRICH):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _common import log         # noqa: E402
from _db import sb_get, sb_upsert  # noqa: E402
from pipeline.state import PipelineState  # noqa: E402


# ── Date parsing ──────────────────────────────────────────────────────────────

def _parse_sort_date(date_str: str) -> Optional[str]:
    """Parse various date formats → YYYY-MM-DD."""
    if not date_str:
        return None
    m = re.match(r"(\d{4}-\d{2}-\d{2})", date_str)
    if m:
        return m.group(1)
    months = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
              "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
    m = re.match(r"(\w{3})\s+(\d{4})", date_str, re.I)
    if m:
        mn = months.get(m.group(1).lower())
        if mn:
            return f"{m.group(2)}-{mn:02d}-01"
    q_map = {"q1": 1, "q2": 4, "q3": 7, "q4": 10, "h1": 1, "h2": 7}
    m = re.match(r"([qh][1-4])\s+(\d{4})", date_str, re.I)
    if m:
        mn = q_map.get(m.group(1).lower())
        if mn:
            return f"{m.group(2)}-{mn:02d}-01"
    m = re.match(r"^(\d{4})$", date_str.strip())
    if m:
        return f"{m.group(1)}-06-01"
    return None


# ── Core logic ────────────────────────────────────────────────────────────────

def step4_generate_catalysts_from_trials(company_id: str, area_id: str,
                                          ctx: dict, dry_run: bool = False) -> int:
    """
    Auto-generate catalyst records from CT.gov trial primary completion dates.
    Returns count of new catalysts created.
    """
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    created = 0
    for trial in ctx.get("trials", []):
        pcd_raw = (trial.get("primary_completion_date") or
                   trial.get("readout_date") or
                   trial.get("pcd_label") or "")
        if not pcd_raw:
            continue

        sort_date = _parse_sort_date(pcd_raw)
        if not sort_date or sort_date < today:
            continue   # past — skip

        trial_id          = trial.get("id", "")
        trial_name        = trial.get("trial_name", trial_id)[:80]
        drug_id           = trial.get("drug_id", "")
        canonical_drug_id = trial.get("canonical_drug_id")
        phase             = trial.get("phase", "")
        pcd_label         = trial.get("pcd_label") or pcd_raw

        significance = ("high"   if "Phase 3" in phase else
                        "medium" if "Phase 2" in phase else "low")

        # Idempotency: dedup by drug × date, not by trial_id.
        # A drug may have multiple NCT IDs sharing the same PCD — collapse to one.
        if canonical_drug_id:
            dedup_q = {
                "company_id":        f"eq.{company_id}",
                "canonical_drug_id": f"eq.{canonical_drug_id}",
                "sort_date":         f"eq.{sort_date}",
                "select":            "id",
            }
        else:
            dedup_q = {
                "company_id": f"eq.{company_id}",
                "drug_id":    f"eq.{drug_id}",
                "sort_date":  f"eq.{sort_date}",
                "select":     "id",
            }
        if sb_get("catalysts", dedup_q):
            continue

        label   = f"{trial_name[:60]} — {phase} primary completion"
        cat_rec = {
            "catalyst_date":      pcd_label,
            "sort_date":          sort_date,
            "label":              label[:200],
            "company_id":         company_id,
            "drug_id":            drug_id,
            "area_id":            area_id,
            "significance":       significance,
            "catalyst_type":      "readout",
            "notes":              f"Auto-generated from ClinicalTrials.gov PCD: {trial_id}",
            "resolved":           False,
            "related_trial_id":   trial_id,
            "is_key_watch":       significance == "high",
            "confidence_source":  "ctgov-pcd",
            "canonical_drug_id":  canonical_drug_id,
        }

        if dry_run:
            log(f"    [DRY RUN] Catalyst: {label[:60]} ({pcd_label})", indent=3)
        else:
            result = sb_upsert("catalysts", cat_rec)
            if result:
                log(f"    + Catalyst [{significance}]: {label[:55]} ({pcd_label})", indent=3)
                created += 1
                # Dual-write to catalyst_calendar (new schema mirror)
                try:
                    cc_rec = {
                        "drug_id":                trial.get("drug_id", ""),
                        "company_id":             company_id,
                        "event_type":             "readout",
                        "event_name":             label[:200],
                        "expected_date":          sort_date,
                        "expected_quarter":       pcd_label,
                        "description":            f"CT.gov trial {trial.get('nct_id', '')} primary completion",
                        "strategic_significance": significance,
                        "confidence":             "inferred",
                        "source_url":             f"https://clinicaltrials.gov/study/{trial.get('nct_id', '')}",
                        "is_past":                False,
                    }
                    sb_upsert("catalyst_calendar", cc_rec)
                except Exception:
                    pass  # non-fatal

    return created


# ── Pipeline node ─────────────────────────────────────────────────────────────

def generate_catalysts(state: PipelineState) -> PipelineState:
    """
    For each trial with a future primary_completion_date, creates an upcoming
    catalyst record.  Idempotent — skips duplicates by drug × date.
    Populates state.catalysts_generated.
    """
    state.catalysts_generated = step4_generate_catalysts_from_trials(
        state.company_id,
        state.area_id,
        state.ctx.as_dict(),
        state.dry_run,
    )
    state.mark_complete("generate_catalysts")
    return state
