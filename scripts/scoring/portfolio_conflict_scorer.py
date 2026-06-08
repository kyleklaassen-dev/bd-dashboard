#!/usr/bin/env python3
"""
portfolio_conflict_scorer.py
Scores each company (strategic_value_score > 0) against Ailux's 3 programs:
  ALX001: TL1A x IL-23p19 bispecific (IBD)
  ALX002: CD19 x BCMA bispecific (I&I autoimmune)
  ALX005: FcRn x Albumin bispecific (autoantibody diseases)

Conflict levels:
  HARD  = company has a direct bispecific in the same mechanism class
  SOFT  = company has a monospecific targeting one arm of an Ailux bispecific
  COMBO = company has assets that pair well with an Ailux program (no direct conflict)
  CLEAR = no assets in any relevant target space

Writes to: company_portfolio_conflicts (UPSERT on company_id + ailux_asset_id)
"""

import os
import re
import sys
from datetime import datetime, timezone

_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from _common import load_credentials  # noqa: E402
import _db                              # noqa: E402

SUPABASE_URL, SERVICE_KEY, _ = load_credentials(require_anthropic=False)
_db.init_db(SUPABASE_URL, SERVICE_KEY)

INACTIVE_STAGES = {"Discontinued", "Terminated", "Withdrawn"}
PHASE2_PLUS = {
    "Phase 2", "Phase 2/3", "Phase 3", "Phase 3 complete", "BLA Filed",
    "Approved", "approved_us", "approved_eu", "approved_china",
    "approved_us_eu", "approved_partial"
}


# ---------------------------------------------------------------------------
# Target helpers
# ---------------------------------------------------------------------------

def norm(t: str) -> str:
    """Normalise target string for matching: uppercase, replace bispecific connectors."""
    if not t:
        return ""
    t = t.upper().strip()
    # Normalise bispecific connectors so "TL1A x IL-23" and "TL1A×IL-23" both match
    t = re.sub(r'\s*[xX×]\s*', 'X', t)
    t = re.sub(r'\s+', ' ', t)
    return t


def has(t: str, *terms: str) -> bool:
    """True if ALL terms are present as substrings in the normalised target."""
    n = norm(t)
    return all(term.upper() in n for term in terms)


def is_bispecific(t: str) -> bool:
    """True if target string implies a bispecific (has X connector, /, or explicit keyword)."""
    n = norm(t)
    return bool(re.search(r'[A-Z0-9]X[A-Z0-9]', n)) or '/' in n or 'BISPECIFIC' in n


def is_active(d: dict) -> bool:
    return (d.get("stage") or "").strip() not in INACTIVE_STAGES


def drug_names(drugs: list, ids: list) -> str:
    id_set = set(ids)
    names = [d.get("name") or d["id"] for d in drugs if d["id"] in id_set]
    if not names:
        names = list(ids)
    return ", ".join(names[:3]) + (" + more" if len(names) > 3 else "")


# ---------------------------------------------------------------------------
# ALX001 — TL1A × IL-23p19 bispecific  (IBD)
# ---------------------------------------------------------------------------

def score_alx001(drugs: list) -> dict:
    hard, soft_tl1a, soft_il23 = [], [], []

    for d in drugs:
        if not is_active(d):
            continue
        t = d.get("target", "")
        did = d["id"]

        # HARD: bispecific hitting both TL1A and IL-23
        if has(t, "TL1A") and has(t, "IL-23") and is_bispecific(t):
            hard.append(did)
        # SOFT: TL1A monospecific only
        elif has(t, "TL1A") and not has(t, "IL-23"):
            soft_tl1a.append(did)
        # SOFT: IL-23 only (no TL1A)
        elif has(t, "IL-23") and not has(t, "TL1A"):
            soft_il23.append(did)

    # COMBO: has Phase 2+ IL-23 mono AND no TL1A at all in pipeline
    all_tl1a = [d["id"] for d in drugs if is_active(d) and has(d.get("target", ""), "TL1A")]
    combo, combo_desc = False, None
    if soft_il23 and not all_tl1a:
        il23_objs = [d for d in drugs if d["id"] in soft_il23]
        adv = [d for d in il23_objs if (d.get("stage") or "") in PHASE2_PLUS]
        if adv:
            names = ", ".join(d.get("name") or d["id"] for d in adv)
            combo = True
            combo_desc = (
                f"{names} (IL-23 inhibitor, {adv[0].get('stage', '')}) pairs with ALX001's TL1A arm. "
                f"Combined dual-pathway coverage is stronger than either asset alone in IBD — "
                f"ideal co-development or in-licensing target for TL1A×IL-23 combination strategy."
            )

    if hard:
        return {
            "conflict_level": "hard",
            "conflict_rationale": (
                f"Direct TL1A×IL-23p19 bispecific competitor: {drug_names(drugs, hard)}. "
                f"Same asset class as ALX001. Partnership would face strong internal cannibalization "
                f"pressure — internal BD team unlikely to champion ALX001."
            ),
            "conflicting_drug_ids": hard,
            "combo_opportunity": False,
            "combo_description": None,
        }
    elif soft_tl1a or soft_il23:
        all_soft = soft_tl1a + soft_il23
        parts = []
        if soft_tl1a:
            parts.append(f"anti-TL1A ({drug_names(drugs, soft_tl1a)})")
        if soft_il23:
            parts.append(f"anti-IL-23 ({drug_names(drugs, soft_il23)})")
        return {
            "conflict_level": "combo" if combo else "soft",
            "conflict_rationale": (
                f"Has {' and '.join(parts)}. Covers one arm of ALX001’s dual mechanism. "
                f"Could view ALX001 as a bispecific upgrade — or as a competitive threat in the "
                f"same IBD pathway."
            ),
            "conflicting_drug_ids": all_soft,
            "combo_opportunity": combo,
            "combo_description": combo_desc,
        }
    else:
        return {
            "conflict_level": "clear",
            "conflict_rationale": (
                "No TL1A or IL-23p19 assets in pipeline. ALX001 presents no internal conflict."
            ),
            "conflicting_drug_ids": [],
            "combo_opportunity": False,
            "combo_description": None,
        }


# ---------------------------------------------------------------------------
# ALX002 — CD19 × BCMA bispecific  (I&I autoimmune)
# ---------------------------------------------------------------------------

def score_alx002(drugs: list) -> dict:
    hard, soft_cd19, soft_bcma = [], [], []

    for d in drugs:
        if not is_active(d):
            continue
        t = d.get("target", "")
        did = d["id"]

        if has(t, "CD19") and has(t, "BCMA"):
            hard.append(did)
        elif has(t, "CD19") and not has(t, "BCMA"):
            soft_cd19.append(did)
        elif has(t, "BCMA") and not has(t, "CD19"):
            soft_bcma.append(did)

    all_cd19 = [d["id"] for d in drugs if is_active(d) and has(d.get("target", ""), "CD19")]
    all_bcma = [d["id"] for d in drugs if is_active(d) and has(d.get("target", ""), "BCMA")]
    cd38_drugs = [d for d in drugs if is_active(d) and "CD38" in norm(d.get("target", ""))]

    combo, combo_desc = False, None
    if soft_bcma and not all_cd19:
        adv = [d for d in drugs if d["id"] in soft_bcma and (d.get("stage") or "") in PHASE2_PLUS]
        if adv:
            names = ", ".join(d.get("name") or d["id"] for d in adv)
            combo = True
            combo_desc = (
                f"{names} (BCMA inhibitor) + ALX002’s CD19 arm = broader B-cell and plasma-cell "
                f"depletion across the full B-lineage. Strong co-development rationale in autoimmune "
                f"settings (SLE, IgAN, MG)."
            )
    elif soft_cd19 and not all_bcma:
        adv = [d for d in drugs if d["id"] in soft_cd19 and (d.get("stage") or "") in PHASE2_PLUS]
        if adv:
            names = ", ".join(d.get("name") or d["id"] for d in adv)
            combo = True
            combo_desc = (
                f"{names} (CD19 inhibitor) + ALX002’s BCMA arm = deeper B-cell lineage coverage. "
                f"ALX002 adds plasma cell depletion that CD19-alone assets lack in autoimmune disease."
            )
    elif cd38_drugs and not all_cd19 and not all_bcma:
        names = ", ".join(d.get("name") or d["id"] for d in cd38_drugs[:2])
        combo = True
        combo_desc = (
            f"{names} (CD38 inhibitor) + ALX002 creates a three-target B-cell/plasma-cell depletion "
            f"strategy. Complementary portfolios with no direct conflict in the B-cell space."
        )

    if hard:
        return {
            "conflict_level": "hard",
            "conflict_rationale": (
                f"Direct CD19×BCMA bispecific competitor: {drug_names(drugs, hard)}. "
                f"Same target pair as ALX002 — internal cannibalization risk is high."
            ),
            "conflicting_drug_ids": hard,
            "combo_opportunity": False,
            "combo_description": None,
        }
    elif soft_cd19 or soft_bcma:
        all_soft = soft_cd19 + soft_bcma
        parts = []
        if soft_cd19:
            parts.append(f"anti-CD19 ({drug_names(drugs, soft_cd19)})")
        if soft_bcma:
            parts.append(f"anti-BCMA ({drug_names(drugs, soft_bcma)})")
        return {
            "conflict_level": "combo" if combo else "soft",
            "conflict_rationale": (
                f"Has {' and '.join(parts)}. One arm of ALX002’s mechanism covered. "
                f"Could view ALX002 as bispecific upgrade or B-cell depletion competitor."
            ),
            "conflicting_drug_ids": all_soft,
            "combo_opportunity": combo,
            "combo_description": combo_desc,
        }
    elif cd38_drugs and combo:
        return {
            "conflict_level": "combo",
            "conflict_rationale": combo_desc,
            "conflicting_drug_ids": [],
            "combo_opportunity": True,
            "combo_description": combo_desc,
        }
    else:
        return {
            "conflict_level": "clear",
            "conflict_rationale": (
                "No CD19 or BCMA assets in pipeline. ALX002 presents no internal conflict."
            ),
            "conflicting_drug_ids": [],
            "combo_opportunity": False,
            "combo_description": None,
        }


# ---------------------------------------------------------------------------
# ALX005 — FcRn × Albumin bispecific  (autoantibody diseases)
# ---------------------------------------------------------------------------

def score_alx005(drugs: list) -> dict:
    hard, soft_fcrn = [], []

    for d in drugs:
        if not is_active(d):
            continue
        t = d.get("target", "")
        did = d["id"]

        if "FCRN" in norm(t) and is_bispecific(t):
            hard.append(did)
        elif "FCRN" in norm(t) and not is_bispecific(t):
            soft_fcrn.append(did)

    combo, combo_desc = False, None
    if soft_fcrn:
        adv = [d for d in drugs if d["id"] in soft_fcrn and (d.get("stage") or "") in PHASE2_PLUS]
        if adv:
            names = ", ".join(d.get("name") or d["id"] for d in adv)
            combo = True
            combo_desc = (
                f"{names} (FcRn monospecific, {adv[0].get('stage', '')}) establishes their FcRn "
                f"franchise. ALX005 adds the albumin arm for extended half-life and potential SC "
                f"dosing — differentiated next-generation format that complements rather than "
                f"cannibalizes the FcRn mono."
            )

    if hard:
        return {
            "conflict_level": "hard",
            "conflict_rationale": (
                f"FcRn bispecific competitor: {drug_names(drugs, hard)}. "
                f"Directly competes with ALX005’s bispecific format in the same mechanism class."
            ),
            "conflicting_drug_ids": hard,
            "combo_opportunity": False,
            "combo_description": None,
        }
    elif soft_fcrn:
        return {
            "conflict_level": "combo" if combo else "soft",
            "conflict_rationale": (
                f"Has FcRn monospecific ({drug_names(drugs, soft_fcrn)}). Covers the FcRn axis but "
                f"not the bispecific format. Could view ALX005 as a next-gen upgrade — or as a "
                f"competitor in overlapping autoantibody indications."
            ),
            "conflicting_drug_ids": soft_fcrn,
            "combo_opportunity": combo,
            "combo_description": combo_desc,
        }
    else:
        return {
            "conflict_level": "clear",
            "conflict_rationale": (
                "No FcRn assets in pipeline. ALX005 presents no internal conflict."
            ),
            "conflicting_drug_ids": [],
            "combo_opportunity": False,
            "combo_description": None,
        }


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------

def fetch_json(url: str) -> list:
    """Call sites pass a 'table?select=...&...' fragment; split it and
    delegate to _db.sb_get's (table, params) interface."""
    table, _, qs = url.partition("?")
    params = dict(p.split("=", 1) for p in qs.split("&")) if qs else {}
    return _db.sb_get(table, params)


def upsert_row(row: dict) -> bool:
    result = _db.sb_upsert("company_portfolio_conflicts", row,
                           on_conflict="company_id,ailux_asset_id")
    if not result:
        print("  WARN upsert failed", file=sys.stderr)
    return bool(result)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=== Portfolio Conflict Scorer ===")
    print(f"Run: {datetime.now(timezone.utc).isoformat()}\n")

    companies = fetch_json(
        "companies?strategic_value_score=gt.0"
        "&select=id,name,strategic_value_score,status&order=strategic_value_score.desc"
    )
    all_drugs = fetch_json(
        "drugs?select=id,name,target,cls,stage,company_id&limit=500"
    )
    partnerships = fetch_json(
        "company_partnerships?select=company_id,partner_company_id,deal_type,drug_id&limit=500"
    )

    print(f"Companies: {len(companies)}  |  Drugs: {len(all_drugs)}  |  Partnerships: {len(partnerships)}\n")

    # Build company -> drugs map (direct + licensed-in)
    co_drugs: dict = {}
    for d in all_drugs:
        cid = d.get("company_id")
        if cid:
            co_drugs.setdefault(cid, []).append(d)

    drug_by_id = {d["id"]: d for d in all_drugs}
    for p in partnerships:
        # partner_company_id is the licensee who holds the drug
        cid = p.get("partner_company_id")
        did = p.get("drug_id")
        if cid and did and did in drug_by_id:
            existing_ids = {d["id"] for d in co_drugs.get(cid, [])}
            if did not in existing_ids:
                co_drugs.setdefault(cid, []).append(drug_by_id[did])

    SKIP = {"ailux"}

    scorers = {
        "alx001": score_alx001,
        "alx002": score_alx002,
        "alx005": score_alx005,
    }

    stats = {"clear": 0, "soft": 0, "hard": 0, "combo": 0}
    rows_written = 0
    now_ts = datetime.now(timezone.utc).isoformat()
    BADGE = {"clear": "GREEN ", "soft": "YELLOW", "hard": "RED   ", "combo": "BLUE  "}

    for co in companies:
        cid, cname = co["id"], co["name"]
        if cid in SKIP:
            continue
        drugs = co_drugs.get(cid, [])

        for asset_id, scorer in scorers.items():
            result = scorer(drugs)
            row = {
                "company_id":           cid,
                "ailux_asset_id":        asset_id,
                "conflict_level":        result["conflict_level"],
                "conflict_rationale":    result["conflict_rationale"],
                "conflicting_drug_ids":  result["conflicting_drug_ids"],
                "combo_opportunity":     result["combo_opportunity"],
                "combo_description":     result.get("combo_description"),
                "last_evaluated":        now_ts,
            }
            ok = upsert_row(row)
            if ok:
                rows_written += 1
            level = result["conflict_level"]
            stats[level] += 1
            badge = BADGE[level]
            preview = result["conflict_rationale"][:62]
            print(f"  [{badge}] {cname:32} {asset_id:8}  {preview}...")

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Companies scored:  {len(companies) - len(SKIP)}")
    print(f"Rows written:      {rows_written}")
    print(f"CLEAR  (green):    {stats['clear']}")
    print(f"SOFT   (yellow):   {stats['soft']}")
    print(f"HARD   (red):      {stats['hard']}")
    print(f"COMBO  (blue):     {stats['combo']}")
    total = sum(stats.values())
    print(f"Total scored:      {total}  (companies x 3 assets)")


if __name__ == "__main__":
    main()
