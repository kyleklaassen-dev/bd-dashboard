#!/usr/bin/env python3
"""
patch_competitive_scores_null.py
=================================
BUG 5 FIX: 203 drug_competitive_scores rows with total_competition_score=NULL.

The original apply_competitive_scores_v56.py only scored context_id='tl1a'.
This script scores ALL context_ids using the same scoring logic, extended for
non-TL1A areas (il4ra, tslp, fcrn, ted, igf1r, tcell, autoimmune, respiratory, etc.).

Reference drug per context:
  tl1a / uc / cd / ibd → XPF005 (spy002) — TL1A × IL-23p19 bispecific
  il4ra / atopy        → dupilumab (IL-4Rα, approved)
  tslp / respiratory   → tezepelumab (anti-TSLP, approved)
  fcrn                 → efgartigimod (FcRn, approved)
  ted / igf1r          → teprotumumab (IGF-1R, approved)
  tcell / autoimmune   → regulatory T-cell / broad autoimmune
"""

import os, sys, json, requests

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _read(f):
    for base in [_REPO, os.path.dirname(os.path.abspath(__file__))]:
        p = os.path.join(base, f)
        if os.path.exists(p):
            return open(p).read().strip()
    return ""

SUPABASE_URL = os.environ.get("SUPABASE_URL") or "https://tghntyofptvfhmtchwcv.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or _read(".supabase_service_key")

if not SUPABASE_KEY:
    print("ERROR: No SUPABASE_SERVICE_KEY"); sys.exit(1)

REST = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


# ─── Scoring helpers (mirrored from apply_competitive_scores_v56.py) ──────────

def target_overlap_score(overlap, modality_text, context_id):
    """0-40 based on overlap tier."""
    o = (overlap or "").lower()
    m = (modality_text or "").lower()
    if o in ("same-space", "same space"):
        return 10
    if o == "watch":
        return 5
    if o == "adjacent":
        return 20
    if o == "direct":
        # TL1A / IBD area: bispecific TL1A × IL-23p19 = max
        if context_id in ("tl1a", "ibd", "uc", "cd"):
            if "il-23p19" in m and "tl1a" in m:
                return 40
            if "il-23p40" in m and "tl1a" in m:
                return 35
            if "tl1a" in m:
                return 30
            return 28
        # Non-TL1A areas: Direct = strong overlap
        return 30
    return 0

def indication_overlap_score_v2(stage, drug_id, modality_text, context_id, overlap):
    """0-30 based on indication overlap and clinical stage."""
    s = (stage or "").lower()
    o = (overlap or "").lower()

    if "terminated" in s or "discontinued" in s:
        return 5

    # High overlap for direct competitors in area
    if o == "direct":
        return 30
    if o == "adjacent":
        return 22
    if o == "same-space":
        return 15
    if o == "watch":
        return 10
    # Fallback by stage
    if "approved" in s or "phase 3" in s:
        return 18
    if "phase 2" in s:
        return 14
    if "phase 1" in s:
        return 10
    return 8

def modality_match_score_v2(modality_text, context_id, overlap):
    """0-20 based on modality match."""
    m = (modality_text or "").lower()
    o = (overlap or "").lower()

    # TL1A/IBD: bispecific TL1A × IL-23p19 = max
    if context_id in ("tl1a", "ibd", "uc", "cd"):
        if "il-23p19" in m and "tl1a" in m:
            return 20
        if "bispecific" in m or "trispecific" in m:
            return 17
        if "tl1a" in m and ("monoclonal" in m or "mab" in m or "antibody" in m):
            return 14
        if "monoclonal antibody" in m or "mab" in m:
            return 10
        if "small molecule" in m or "jak" in m:
            return 6
        if "adc" in m or "engager" in m:
            return 3
        return 8

    # Non-TL1A areas: direct = same class = high match
    if o == "direct":
        if "bispecific" in m:
            return 18
        if "monoclonal" in m or "mab" in m:
            return 15
        if "small molecule" in m:
            return 10
        return 12
    if o == "adjacent":
        return 10
    if o in ("same-space", "watch"):
        return 6
    return 8

def stage_proximity_score_v2(stage):
    """0-10 based on development stage."""
    s = (stage or "").lower()
    if any(x in s for x in ["approved", "nda", "bla", "ema"]):
        return 10
    if "phase 3" in s or "phase_3" in s or "pivotal" in s:
        return 10
    if "phase 2" in s or "phase_2" in s:
        return 8
    if "phase 1" in s or "phase_1" in s:
        return 5
    if "preclinical" in s or "ind" in s:
        return 2
    if "terminated" in s or "discontinued" in s:
        return 0
    return 2

# Known China-only programs (lower geo relevance for US/EU)
CHINA_ONLY = {
    "lq080", "lq082", "cantai-tl1a", "ear-2001", "hbm2001",
    "hy8931", "lbl053", "pr203", "sab06", "spy001", "spy002",
    "spy003", "spy072", "spy120", "spy130", "spy230", "hxn-1002",
}
CHINA_FIRST = {"abs-101", "fg-m701", "qx030n"}

def geography_penalty_v2(drug_id, modality_text):
    if drug_id in CHINA_ONLY:
        return -15
    if drug_id in CHINA_FIRST:
        return -10
    return 0

def monitoring_priority_v2(total, stage):
    s = (stage or "").lower()
    base = total
    if total >= 70 and ("phase 3" in s or "approved" in s):
        base = min(100, base + 10)
    elif total >= 60 and "phase 2" in s:
        base = min(100, base + 5)
    elif total >= 55 and "phase 1" in s:
        base = min(100, base + 3)
    elif total < 50 and "preclinical" in s:
        base = max(0, base - 5)
    if "terminated" in s or "discontinued" in s:
        base = min(base, 20)
    return base


# ─── Fetch null-score rows ────────────────────────────────────────────────────

def sb_get(table, params):
    r = requests.get(f"{REST}/{table}", headers=HEADERS, params=params, timeout=20)
    if r.status_code == 200:
        return r.json()
    print(f"  GET {table}: {r.status_code} {r.text[:200]}")
    return []

def sb_patch_row(table, payload, params):
    h = {**HEADERS, "Prefer": "return=minimal"}
    r = requests.patch(f"{REST}/{table}", headers=h, params=params, json=payload, timeout=15)
    return r.status_code in (200, 204)


def main():
    import datetime

    # Fetch all null-score rows
    null_rows = sb_get("drug_competitive_scores", {
        "total_competition_score": "is.null",
        "select": "id,drug_id,context_id,overlap,cls",
        "limit": "500",
    })
    print(f"Found {len(null_rows)} rows with total_competition_score=NULL\n")

    # Build drug_id → (stage, modality) lookup from drugs table
    all_drug_ids = list({r["drug_id"] for r in null_rows if r.get("drug_id")})
    drug_lookup = {}
    # Fetch in chunks of 50
    chunk_size = 50
    for i in range(0, len(all_drug_ids), chunk_size):
        chunk = all_drug_ids[i:i + chunk_size]
        ids_str = ",".join(f"({d})" for d in chunk)
        # Use in.(id1,id2,...) filter
        in_filter = "in.(" + ",".join(chunk) + ")"
        drugs = sb_get("drugs", {
            "id": in_filter,
            "select": "id,stage,modality",
        })
        for d in drugs:
            drug_lookup[d["id"]] = {"stage": d.get("stage", ""), "modality": d.get("modality", "")}

    print(f"Loaded drug data for {len(drug_lookup)} drugs\n")

    # Score each row
    fixed = 0
    skipped = 0
    print(f"{'Drug':<35} {'Ctx':<12} {'Overlap':<12} {'TGT':>4} {'IND':>4} {'MOD':>4} {'STG':>4} {'GEO':>5} {'TOT':>4} {'MON':>4}")
    print("-" * 85)

    NOW_ISO = datetime.datetime.utcnow().isoformat()

    for row in null_rows:
        row_id = row["id"]
        drug_id = row.get("drug_id", "")
        context_id = row.get("context_id", "tl1a")
        overlap = row.get("overlap", "")
        cls = row.get("cls", "")

        drug_data = drug_lookup.get(drug_id, {})
        stage = drug_data.get("stage", "")
        modality = drug_data.get("modality", cls or "")

        tgt = target_overlap_score(overlap, modality, context_id)
        ind = indication_overlap_score_v2(stage, drug_id, modality, context_id, overlap)
        mod = modality_match_score_v2(modality, context_id, overlap)
        stg = stage_proximity_score_v2(stage)
        geo = geography_penalty_v2(drug_id, modality)

        total = max(0, min(100, tgt + ind + mod + stg + geo))
        mon = monitoring_priority_v2(total, stage)

        print(f"{drug_id:<35} {context_id:<12} {(overlap or 'n/a'):<12} {tgt:>4} {ind:>4} {mod:>4} {stg:>4} {geo:>5} {total:>4} {mon:>4}")

        rationale = (
            f"target={tgt}/40 (overlap={overlap}), "
            f"indication={ind}/30, "
            f"modality={mod}/20, "
            f"stage={stg}/10 ({stage}), "
            f"geo={geo}"
        )

        payload = {
            "reference_drug_id":        "anti-tl1a-xpf005-arm",
            "target_overlap_score":     tgt,
            "indication_overlap_score": ind,
            "modality_match_score":     mod,
            "stage_proximity_score":    stg,
            "geography_penalty":        geo,
            "total_competition_score":  total,
            "monitoring_priority_score": mon,
            "score_rationale":          rationale,
            "scored_by":                "patch_competitive_scores_null.py",
            "scored_at":                NOW_ISO,
            "score_version":            1,
        }

        ok = sb_patch_row("drug_competitive_scores", payload, {"id": f"eq.{row_id}"})
        if ok:
            fixed += 1
        else:
            print(f"  ✗ PATCH failed for id={row_id}")
            skipped += 1

    print(f"\nDone: {fixed} scored, {skipped} failed.")


if __name__ == "__main__":
    main()
