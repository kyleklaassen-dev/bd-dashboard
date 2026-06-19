#!/usr/bin/env python3
"""score_foresight.py — the Foresight Rate resolution loop.

What it does (idempotent, safe to re-run):
  1. SCAN    — find catalysts past their sort_date.
  2. LOG     — catalysts already resolved (resolved=true / status='met') become
               foresight_events rows (foreseen=true, matched to the catalyst).
  3. VERIFY  — past-due *pending* catalysts with a related_trial_id are checked
               against ClinicalTrials.gov v2; clear outcomes (results posted /
               COMPLETED past primary completion / TERMINATED) auto-resolve.
  4. QUEUE   — everything else is written to docs/foresight_review_queue.md for
               human resolution (Kyle confirms outcome + source, or kills stale rows).
  5. SCORE   — recompute foresight_scores per (period, area) + ALL roll-up from
               foresight_events, upserted on (period, area_id).

What it does NOT do: detect MISSES (material events that had no catalyst row).
Miss detection needs the event sweep (research.py / news pipeline integration) —
until then, Foresight Rate is an UPPER BOUND and is labeled as such in notes.

Usage:
  python3 src/meridian/scoring/score_foresight.py [--dry-run]

Env/files: .supabase_service_key in workspace root (or SUPABASE_SERVICE_KEY env).
See docs/frameworks/FORESIGHT_RATE_METRIC.md and migrations/v105/v106.
"""

import json
import os
import sys
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import date, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
URL = "https://tghntyofptvfhmtchwcv.supabase.co"
TODAY = date.today().isoformat()
DRY = "--dry-run" in sys.argv
QUEUE_DOC = os.path.join(ROOT, "docs", "foresight_review_queue.md")
PRED_QUEUE_DOC = os.path.join(ROOT, "docs", "prediction_review_queue.md")

# status -> outcome score for Brier (1=happened, 0=didn't, 0.5=partial)
OUTCOME = {"correct": 1.0, "incorrect": 0.0, "partially_correct": 0.5}

# Miss-detection scope
COVERED_AREAS = ("tl1a", "tslp", "il4ra", "igf1r", "fcrn", "ibd", "ted")
TRACKING_START = "2026-05-18"        # Meridian's birthday — no system existed before this, so
                                     # pre-existing events cannot be "missed". Honest window start.
MATCH_TOLERANCE_DAYS = 120           # a catalyst's sort_date must be within +/- this of the event
# deal_type (ground-truth event) -> the catalyst_type(s) that would count as having predicted it.
# Per-type so an M&A event is only credited to a deal-family catalyst, not an unrelated approval.
DEAL_TYPE_TO_CATALYST = {
    "acquisition":   {"deal", "partnership"},
    "licensing":     {"deal", "partnership"},
    "collaboration": {"deal", "partnership"},
    "partnership":   {"deal", "partnership"},
    "option":        {"deal", "partnership"},
    "financing":     {"financing", "deal"},
    "regulatory":    {"regulatory", "approval", "filing"},
    "clinical":      {"readout", "clinical_update"},
}
DEFAULT_CATALYST_MATCH = {"deal", "partnership"}
# covered mechanism -> drugs.target keyword (to scope clinical readouts to covered areas)
COVERED_TARGET_KW = {"tl1a": "TL1A", "tslp": "TSLP", "il4ra": "IL-4", "igf1r": "IGF-1R", "fcrn": "FcRn"}
READOUT_CATALYST_TYPES = {"readout", "clinical_update"}


def service_key() -> str:
    k = os.environ.get("SUPABASE_SERVICE_KEY")
    if k:
        return k.strip()
    with open(os.path.join(ROOT, ".supabase_service_key")) as f:
        return f.read().strip()


SK = service_key()
HDRS = {"apikey": SK, "Authorization": f"Bearer {SK}", "Content-Type": "application/json"}


def rest(path: str, method: str = "GET", body=None, prefer: str | None = None):
    headers = dict(HDRS)
    if prefer:
        headers["Prefer"] = prefer
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{URL}/rest/v1/{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        print(f"  !! REST {method} {path} -> {e.code}: {e.read().decode()[:300]}", file=sys.stderr)
        raise


def period_of(d: str) -> str:
    y, m = d[:4], int(d[5:7])
    return f"{y}-Q{(m - 1) // 3 + 1}"


def ctgov_status(nct: str):
    """Best-effort CT.gov v2 lookup. Returns dict or None."""
    try:
        req = urllib.request.Request(
            f"https://clinicaltrials.gov/api/v2/studies/{nct}"
            "?fields=protocolSection.statusModule,hasResults",
            headers={"User-Agent": "meridian-foresight/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            j = json.load(r)
        sm = j.get("protocolSection", {}).get("statusModule", {})
        return {
            "overall": sm.get("overallStatus"),
            "primary_completion": (sm.get("primaryCompletionDateStruct") or {}).get("date"),
            "results_posted": bool(j.get("hasResults")),
            "last_update": (sm.get("lastUpdatePostDateStruct") or {}).get("date"),
        }
    except Exception as e:  # noqa: BLE001 — network best-effort, queue on any failure
        print(f"  ctgov lookup failed for {nct}: {e}")
        return None


def existing_event_catalyst_ids() -> set:
    rows = rest("foresight_events?select=matched_catalyst_id&matched_catalyst_id=not.is.null&limit=10000")
    return {r["matched_catalyst_id"] for r in rows}


def log_event(cat: dict, event_date: str, foreseen: bool, source_url: str,
              source_type: str, notes: str) -> None:
    """Insert one foresight_events row matched to a catalyst."""
    try:
        terr = (datetime.fromisoformat(cat["sort_date"]) - datetime.fromisoformat(event_date)).days
    except Exception:  # noqa: BLE001
        terr = None
    row = {
        "period": period_of(event_date),
        "area_id": cat.get("area_id"),
        "event_type": cat.get("catalyst_type") or "readout",
        "asset_label": cat["label"][:300],
        "drug_id": cat.get("drug_id"),
        "company_id": cat.get("company_id"),
        "event_date": event_date,
        "source_url": source_url or "https://clinicaltrials.gov",
        "source_type": source_type,
        "significance": cat.get("significance") or "medium",
        "foreseen": foreseen,
        "matched_catalyst_id": cat["id"],
        "timing_error_days": terr,
        "notes": notes,
        "added_by": "score_foresight.py",
    }
    if DRY:
        print(f"  [dry] would log event for catalyst #{cat['id']}: {notes}")
        return
    rest("foresight_events", "POST", row, prefer="return=minimal")
    print(f"  + event logged for catalyst #{cat['id']} ({cat.get('area_id')}/{row['event_type']}) — {notes}")


def resolve_catalyst(cat_id: int, note: str) -> None:
    if DRY:
        return
    from meridian.database import update_catalyst
    update_catalyst(cat_id, {"resolved": True, "catalyst_status": "met",
                             "resolved_note": note[:500]})
