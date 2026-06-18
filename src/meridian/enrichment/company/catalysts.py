#!/usr/bin/env python3
"""
Step 4 — Catalyst Generation (§3 company_enrichment split).
===========================================================
Extracted verbatim from company_enrichment.py.

Generate upcoming-readout catalyst records from trial primary-completion dates
(significance by phase; idempotent). Writes route through _catalyst_upsert →
CatalystWriter (single-writer). Self-contained.
"""

import re
from typing import Optional

from meridian.enrichment.company.common import (
    TODAY, log, sb_get, sb_upsert, _catalyst_upsert,
)


# ══════════════════════════════════════════════════════════════════════════
# STEP 4 — CATALYST GENERATION
#
# IF trial has primary_completion_date in the future:
#   → Auto-create a readout catalyst record
#   → Significance = high (Ph3), medium (Ph2), low (Ph1)
# IF catalyst for this trial already exists:
#   → Skip (idempotent)
# ══════════════════════════════════════════════════════════════════════════

def _parse_sort_date(date_str: str) -> Optional[str]:
    """Parse various date formats → YYYY-MM-DD."""
    if not date_str:
        return None
    m = re.match(r"(\d{4}-\d{2}-\d{2})", date_str)
    if m:
        return m.group(1)
    months = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
              "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
    m = re.match(r"(\w{3})\s+(\d{4})", date_str, re.I)
    if m:
        mn = months.get(m.group(1).lower())
        if mn:
            return f"{m.group(2)}-{mn:02d}-01"
    q_map = {"q1":1,"q2":4,"q3":7,"q4":10,"h1":1,"h2":7}
    m = re.match(r"([qh][1-4])\s+(\d{4})", date_str, re.I)
    if m:
        mn = q_map.get(m.group(1).lower())
        if mn:
            return f"{m.group(2)}-{mn:02d}-01"
    m = re.match(r"^(\d{4})$", date_str.strip())
    if m:
        return f"{m.group(1)}-06-01"
    return None


def step4_generate_catalysts_from_trials(company_id: str, area_id: str,
                                          ctx: dict, dry_run: bool = False) -> int:
    """
    Auto-generate catalyst records from CT.gov trial primary completion dates.
    Returns count of new catalysts created.
    """
    created = 0
    for trial in ctx.get("trials", []):
        pcd_raw = (trial.get("primary_completion_date") or
                   trial.get("readout_date") or
                   trial.get("pcd_label") or "")
        if not pcd_raw:
            continue

        sort_date = _parse_sort_date(pcd_raw)
        if not sort_date or sort_date < TODAY:
            continue   # past — skip

        trial_id         = trial.get("id", "")
        trial_name       = trial.get("trial_name", trial_id)[:80]
        drug_id          = trial.get("drug_id", "")
        canonical_drug_id = trial.get("canonical_drug_id")   # propagated from ct_gov_sync
        phase            = trial.get("phase", "")
        pcd_label        = trial.get("pcd_label") or pcd_raw

        significance = ("high"   if "Phase 3" in phase else
                        "medium" if "Phase 2" in phase else "low")

        # Idempotency: dedup by drug × date, NOT by trial_id.
        # A drug may have multiple NCT IDs (cohorts, arms, sites) all sharing
        # the same primary_completion_date — those should collapse to ONE catalyst.
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
            "catalyst_date":     pcd_label,
            "sort_date":         sort_date,
            "label":             label[:200],
            "company_id":        company_id,
            "drug_id":           drug_id,
            "area_id":           area_id,
            "significance":      significance,
            "catalyst_type":     "readout",
            "notes":             f"Auto-generated from ClinicalTrials.gov PCD: {trial_id}",
            "resolved":          False,
            "related_trial_id":  trial_id,
            "is_key_watch":      significance == "high",
            "confidence_source": "ctgov-pcd",
            "canonical_drug_id": canonical_drug_id,   # identity spine from trials table
        }

        if dry_run:
            log(f"    [DRY RUN] Catalyst: {label[:60]} ({pcd_label})", indent=3)
        else:
            result = _catalyst_upsert(cat_rec)
            if result:
                log(f"    + Catalyst [{significance}]: {label[:55]} ({pcd_label})", indent=3)
                created += 1
                # BUG 7 FIX: Dual-write to catalyst_calendar (new schema)
                # The legacy catalysts table is the live source; we mirror here going forward
                # so catalyst_calendar self-populates. No bulk migration of 862 legacy rows.
                try:
                    cc_rec = {
                        "drug_id":              trial.get("drug_id", ""),
                        "company_id":           company_id,
                        "event_type":           "readout",
                        "event_name":           label[:200],
                        "expected_date":        sort_date,
                        "expected_quarter":     pcd_label,
                        "description":          f"CT.gov trial {trial.get('nct_id', '')} primary completion",
                        "strategic_significance": significance,
                        "confidence":           "inferred",
                        "source_url":           f"https://clinicaltrials.gov/study/{trial.get('nct_id', '')}",
                        "is_past":              False,
                    }
                    sb_upsert("catalyst_calendar", cc_rec)
                except Exception:
                    pass  # non-fatal

    return created
