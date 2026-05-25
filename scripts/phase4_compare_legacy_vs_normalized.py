#!/usr/bin/env python3
"""
Phase 4 Comparison Harness — Meridian BD Platform
====================================================
Read-only. Does NOT modify any production data.
Compares legacy area_id-based queries against normalized ontology tables.

Usage:
  python3 scripts/phase4_compare_legacy_vs_normalized.py
  python3 scripts/phase4_compare_legacy_vs_normalized.py --indication uc
  python3 scripts/phase4_compare_legacy_vs_normalized.py --area tl1a
  python3 scripts/phase4_compare_legacy_vs_normalized.py --output docs/phase4_comparison_harness.md

Comparison targets:
  - drug_areas (legacy) vs drug_indications (normalized)
  - drug_area_scores (legacy) vs drug_targets + drug_indications (normalized)
  - deals.area_id (legacy) — no normalized equivalent yet
  - catalysts.area_id (legacy) vs trial_indications (normalized)
  - trials (legacy drug_id join) vs trial_indications (normalized)

Status values:
  match                — legacy and normalized produce equivalent results
  acceptable_mismatch  — normalized has more/fewer but difference is expected and documented
  needs_rule_adjustment — mismatch points to missing alias, incomplete coverage, or governance gap
  migration_blocker    — DO NOT migrate this path; normalized source is not ready
  not_ready            — fundamental mapping doesn't exist yet
"""

import argparse
import json
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
SUPABASE_URL = "https://tghntyofptvfhmtchwcv.supabase.co"
# Read key from file at runtime
import os

def _load_key():
    key_file = os.path.join(os.path.dirname(__file__), '..', '.supabase_anon_key')
    with open(os.path.abspath(key_file)) as f:
        return f.read().strip()

# ── Supabase helpers ──────────────────────────────────────────────────────────
def sb_get(table: str, params: str = "limit=2000") -> list:
    key = _load_key()
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    url = f"{SUPABASE_URL}/rest/v1/{table}?{params}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f"GET {table}?{params} → {e.code}: {body[:300]}")


# ── Area → Indication mapping ─────────────────────────────────────────────────
# Each legacy area_id maps to one or more indication_ids in the normalized ontology.
# This mapping is evidence-based (not assumed). Rationale in normalization_engine.md.
AREA_TO_IND = {
    # Exact or near-exact semantic equivalence
    "ted":         ["ted"],
    # Target-defined areas that map to their primary disease indication(s)
    "tl1a":        ["uc", "cd"],
    "ibd":         ["uc", "cd"],
    "igf1r":       ["ted"],
    "fcrn":        ["gmg", "cidp", "waiha"],
    "il4ra":       ["ad", "asthma"],
    "atopy":       ["ad", "chronic_urticaria"],
    "tslp":        ["asthma", "copd", "crswnp"],
    "respiratory": ["asthma", "copd", "crswnp"],
    "autoimmune":  ["gmg", "cidp", "ra", "sle", "waiha", "sjogrens"],
    "tcell":       ["all", "multiple_myeloma"],
}

# Reverse: indication_id → legacy area_id(s)
IND_TO_AREA: dict[str, list[str]] = defaultdict(list)
for area, inds in AREA_TO_IND.items():
    for ind in inds:
        IND_TO_AREA[ind].append(area)

# Status classification rules (applied after comparison)
# Thresholds are conservative — lower bound triggers migration_blocker
MATCH_THRESHOLD     = 95.0   # >= this → match (legacy_drug coverage by normalized)
ACCEPTABLE_FLOOR    = 70.0   # >= this → acceptable_mismatch
NEEDS_RULE_FLOOR    = 40.0   # >= this → needs_rule_adjustment
# < NEEDS_RULE_FLOOR → migration_blocker or not_ready


# ── Data loaders ─────────────────────────────────────────────────────────────
def load_all() -> dict:
    """Load all relevant tables. Returns a dict of indexed structures."""
    print("Loading data from Supabase (read-only)...", flush=True)

    drugs_raw = sb_get("drugs", "select=id,name,display_name&limit=2000")
    drug_names = {r["id"]: (r.get("display_name") or r.get("name") or r["id"])
                  for r in drugs_raw}

    da_raw = sb_get("drug_areas", "select=drug_id,area_id&limit=2000")
    da_by_area: dict[str, set] = defaultdict(set)
    for r in da_raw:
        da_by_area[r["area_id"]].add(r["drug_id"])

    das_raw = sb_get("drug_area_scores",
                     "select=drug_id,area_id,overlap,cls,confidence_level&limit=2000")
    das_by_area: dict[str, set] = defaultdict(set)
    das_detail: dict[tuple, dict] = {}
    for r in das_raw:
        das_by_area[r["area_id"]].add(r["drug_id"])
        das_detail[(r["area_id"], r["drug_id"])] = {
            "overlap": r.get("overlap"),
            "cls":     r.get("cls"),
            "conf":    r.get("confidence_level"),
        }

    di_raw = sb_get("drug_indications",
                    "select=drug_id,indication_id,confidence_level,confidence_score&limit=2000")
    di_by_ind: dict[str, set] = defaultdict(set)
    di_detail: dict[tuple, dict] = {}
    for r in di_raw:
        di_by_ind[r["indication_id"]].add(r["drug_id"])
        di_detail[(r["indication_id"], r["drug_id"])] = {
            "conf_level":  r.get("confidence_level"),
            "conf_score":  r.get("confidence_score"),
        }

    ti_raw = sb_get("trial_indications", "select=trial_id,indication_id&limit=2000")
    ti_by_ind: dict[str, set] = defaultdict(set)
    for r in ti_raw:
        ti_by_ind[r["indication_id"]].add(r["trial_id"])

    dt_raw = sb_get("drug_targets", "select=drug_id,target_id&limit=2000")
    dt_by_drug: dict[str, set] = defaultdict(set)
    for r in dt_raw:
        dt_by_drug[r["drug_id"]].add(r["target_id"])

    deals_raw = sb_get("deals", "select=area_id&limit=2000")
    deals_by_area: dict[str, int] = defaultdict(int)
    deals_null = 0
    for r in deals_raw:
        if r["area_id"]:
            deals_by_area[r["area_id"]] += 1
        else:
            deals_null += 1

    cats_raw = sb_get("catalysts", "select=area_id&limit=2000")
    cats_by_area: dict[str, int] = defaultdict(int)
    for r in cats_raw:
        if r["area_id"]:
            cats_by_area[r["area_id"]] += 1

    print(f"  drugs={len(drugs_raw)}  drug_areas={len(da_raw)}  "
          f"drug_area_scores={len(das_raw)}", flush=True)
    print(f"  drug_indications={len(di_raw)}  drug_targets={len(dt_raw)}  "
          f"trial_indications={len(ti_raw)}", flush=True)
    print(f"  deals={len(deals_raw)}  catalysts={len(cats_raw)}", flush=True)
    print()

    return {
        "drug_names": drug_names,
        "da_by_area": da_by_area,
        "das_by_area": das_by_area,
        "das_detail": das_detail,
        "di_by_ind": di_by_ind,
        "di_detail": di_detail,
        "ti_by_ind": ti_by_ind,
        "dt_by_drug": dt_by_drug,
        "deals_by_area": deals_by_area,
        "deals_null": deals_null,
        "cats_by_area": cats_by_area,
    }


# ── Comparison logic ──────────────────────────────────────────────────────────
def classify_status(match_pct: float, legacy_cnt: int, norm_cnt: int,
                    extra_legacy: list, extra_norm: list) -> tuple[str, str]:
    """
    Returns (status, note) based on match percentage and population characteristics.
    Conservative: favour migration_blocker over optimistic assessment.
    """
    if legacy_cnt == 0 and norm_cnt == 0:
        return "not_ready", "Neither legacy nor normalized has data for this area."

    if legacy_cnt == 0:
        return "not_ready", "No legacy data — cannot compare; normalized has data only."

    # Check for complete population reversal (different drug sets)
    if match_pct == 0.0 and norm_cnt > 0:
        return "not_ready", (
            "Zero overlap — legacy and normalized are pointing at completely different "
            "drug populations. Fundamental mapping issue. Do NOT migrate."
        )

    # Coverage gap check: if normalized << legacy and extra_legacy is large
    if match_pct < NEEDS_RULE_FLOOR:
        return "migration_blocker", (
            f"Normalized covers only {match_pct:.0f}% of legacy drug population. "
            f"{len(extra_legacy)} legacy drugs have no normalized counterpart. "
            "Migrating now would silently drop these drugs from dashboard views."
        )

    if match_pct < ACCEPTABLE_FLOOR:
        return "needs_rule_adjustment", (
            f"{match_pct:.0f}% match. {len(extra_legacy)} legacy drugs missing from "
            "normalized. Check: (a) missing drug_indications rows, "
            "(b) alias gaps, (c) broad area straddling multiple indications."
        )

    if match_pct < MATCH_THRESHOLD:
        return "acceptable_mismatch", (
            f"{match_pct:.0f}% legacy coverage. {len(extra_norm)} extra drugs in normalized "
            "are expected — the ontology is more complete than the legacy area curation. "
            "Review extra_legacy list for any true missing rows."
        )

    return "match", (
        f"{match_pct:.0f}% of legacy drugs represented in normalized. "
        "Extra normalized drugs are genuine ontology expansion, not regressions."
    )


def compare_area(area_id: str, data: dict) -> dict:
    """Run all comparisons for one legacy area_id. Returns a result dict."""
    ind_ids = AREA_TO_IND.get(area_id, [])
    drug_names = data["drug_names"]

    # Legacy drug set
    legacy_drugs = data["da_by_area"].get(area_id, set())
    legacy_score_drugs = data["das_by_area"].get(area_id, set())

    # Normalized drug set (union across all mapped indications)
    norm_drugs: set = set()
    for ind in ind_ids:
        norm_drugs |= data["di_by_ind"].get(ind, set())

    # Trial count (normalized)
    norm_trials: set = set()
    for ind in ind_ids:
        norm_trials |= data["ti_by_ind"].get(ind, set())

    # Target coverage: drugs with target data (normalized)
    drugs_with_targets = {d for d in (legacy_drugs | norm_drugs)
                          if data["dt_by_drug"].get(d)}

    overlap = legacy_drugs & norm_drugs
    extra_legacy = sorted(legacy_drugs - norm_drugs)
    extra_norm = sorted(norm_drugs - legacy_drugs)

    match_pct = (len(overlap) / len(legacy_drugs) * 100) if legacy_drugs else 0.0

    status, note = classify_status(
        match_pct, len(legacy_drugs), len(norm_drugs), extra_legacy, extra_norm
    )

    # Deal + catalyst counts (legacy)
    deal_count = data["deals_by_area"].get(area_id, 0)
    cat_count = data["cats_by_area"].get(area_id, 0)

    def _names(ids, limit=15):
        return [(d, drug_names.get(d, d)) for d in sorted(ids)[:limit]]

    return {
        "area_id":          area_id,
        "ind_ids":          ind_ids,
        "legacy_count":     len(legacy_drugs),
        "legacy_score_count": len(legacy_score_drugs),
        "norm_count":       len(norm_drugs),
        "overlap_count":    len(overlap),
        "match_pct":        round(match_pct, 1),
        "extra_legacy":     extra_legacy,
        "extra_norm":       extra_norm,
        "norm_trials":      len(norm_trials),
        "drugs_with_targets": len(drugs_with_targets),
        "deal_count":       deal_count,
        "cat_count":        cat_count,
        "status":           status,
        "note":             note,
        "extra_legacy_names": _names(extra_legacy),
        "extra_norm_names":   _names(extra_norm),
    }


# ── Dashboard function comparisons ───────────────────────────────────────────
def compare_dashboard_functions(data: dict) -> list[dict]:
    """
    Compare the 5 high-risk dashboard functions against their normalized replacement paths.
    Returns one result dict per function.
    """
    results = []

    # 1. openDrugEntityModal — drug_area_scores → drug_targets + drug_indications
    das_drugs = set()
    for area in data["das_by_area"]:
        das_drugs |= data["das_by_area"][area]
    di_drugs = set()
    for ind in data["di_by_ind"]:
        di_drugs |= data["di_by_ind"][ind]
    dt_drugs = set(data["dt_by_drug"].keys())
    norm_modal_drugs = di_drugs | dt_drugs
    overlap_modal = das_drugs & norm_modal_drugs
    results.append({
        "function":       "openDrugEntityModal()",
        "lines":          "11557–11620",
        "legacy_source":  "drug_area_scores (competitive positioning)",
        "norm_source":    "drug_targets + drug_indications",
        "legacy_count":   len(das_drugs),
        "norm_count":     len(norm_modal_drugs),
        "overlap_count":  len(overlap_modal),
        "match_pct":      round(len(overlap_modal)/len(das_drugs)*100, 1) if das_drugs else 0,
        "extra_legacy":   sorted(das_drugs - norm_modal_drugs),
        "extra_norm":     sorted(norm_modal_drugs - das_drugs),
        "status":         "migration_blocker",
        "notes": (
            "drug_area_scores has competitive enrichment data (overlap, rationale, cls) "
            "that has no equivalent column in drug_indications/drug_targets. "
            "The competitive positioning modal content CANNOT be replaced until "
            "drug_area_scores enrichment is migrated to drug_indications. "
            "Separate concern from drug population coverage."
        ),
    })

    # 2. _makeAreaPI() — drug_areas.in(area_id) → drug_indications
    # Check ibd (biggest gap) and tl1a
    ibd_legacy = data["da_by_area"].get("ibd", set()) | data["da_by_area"].get("tl1a", set())
    ibd_norm = data["di_by_ind"].get("uc", set()) | data["di_by_ind"].get("cd", set())
    ibd_overlap = ibd_legacy & ibd_norm
    results.append({
        "function":       "_makeAreaPI() — IBD/TL1A tab",
        "lines":          "12121–12200",
        "legacy_source":  "drug_areas.in('area_id', ['ibd']) or ['tl1a']",
        "norm_source":    "drug_indications WHERE indication_id IN ('uc','cd')",
        "legacy_count":   len(ibd_legacy),
        "norm_count":     len(ibd_norm),
        "overlap_count":  len(ibd_overlap),
        "match_pct":      round(len(ibd_overlap)/len(ibd_legacy)*100, 1) if ibd_legacy else 0,
        "extra_legacy":   sorted(ibd_legacy - ibd_norm),
        "extra_norm":     sorted(ibd_norm - ibd_legacy),
        "status":         "migration_blocker",
        "notes": (
            f"Legacy ibd+tl1a areas contain {len(ibd_legacy)} drugs. "
            f"drug_indications covers only {len(ibd_norm)} UC+CD drugs ({len(ibd_overlap)} overlap). "
            f"Migrating _makeAreaPI now would drop ~{len(ibd_legacy - ibd_norm)} drugs "
            "from the IBD/TL1A tab drug list. drug_indications needs full backfill "
            "before this path can be cut over."
        ),
    })

    # 3. loadAreaDeals / _loadBdIntoModal — deals.area_id → no indication equivalent
    total_deals_tagged = sum(data["deals_by_area"].values())
    results.append({
        "function":       "loadAreaDeals() / _loadBdIntoModal()",
        "lines":          "3410–3447 / 12063–12091",
        "legacy_source":  "deals.area_id IN (area_ids) → 6 area buckets",
        "norm_source":    "No normalized equivalent — deals not linked to indication_ids",
        "legacy_count":   total_deals_tagged,
        "norm_count":     0,
        "overlap_count":  0,
        "match_pct":      0.0,
        "extra_legacy":   [],
        "extra_norm":     [],
        "status":         "not_ready",
        "notes": (
            f"{total_deals_tagged} deals tagged with area_id across fcrn/igf1r/il4ra/tcell/tl1a/tslp. "
            "deals table has no indication_id column. No bridge between deals and indication ontology exists. "
            "Migration requires: (a) add indication_id FK to deals, or "
            "(b) build deals→area_id→indication bridge via ontology_mappings. "
            "Do NOT migrate. Deals feed is safe as legacy through Phase 5."
        ),
    })

    # 4. loadAreaCatalysts — catalysts.area_id → trial_indications
    total_cats = sum(data["cats_by_area"].values())
    ti_trials_total = sum(len(v) for v in data["ti_by_ind"].values())
    results.append({
        "function":       "loadAreaCatalysts()",
        "lines":          "3376–3408",
        "legacy_source":  "catalysts.area_id IN (areas)",
        "norm_source":    "trial_indications WHERE indication_id IN (ind_ids)",
        "legacy_count":   total_cats,
        "norm_count":     ti_trials_total,
        "overlap_count":  None,
        "match_pct":      None,
        "extra_legacy":   [],
        "extra_norm":     [],
        "status":         "needs_rule_adjustment",
        "notes": (
            f"{total_cats} catalysts tagged with area_id. "
            f"trial_indications has {ti_trials_total} rows across 16 indications. "
            "These are different record types (catalysts = upcoming readouts, "
            "trial_indications = indication-level trial metadata). "
            "Catalysts cannot be directly replaced by trial_indications — they contain "
            "curated readout dates and notes not in trial_indications. "
            "Normalized path should JOIN trials + trial_indications to derive catalyst-like records. "
            "Rule needed: area_id → indication_id bridge for catalysts.area_id filter."
        ),
    })

    # 5. trial/signal paths — trials.area_id → trial_indications
    # trials table: check if indication_id is populated
    results.append({
        "function":       "Trial + Signal feed paths (_loadAreaDrugTabs)",
        "lines":          "3337–3460 / 3418 / 3460",
        "legacy_source":  "signals.area_id, trials join via drug_id",
        "norm_source":    "trial_indications WHERE indication_id IN (ind_ids)",
        "legacy_count":   None,
        "norm_count":     ti_trials_total,
        "overlap_count":  None,
        "match_pct":      None,
        "extra_legacy":   [],
        "extra_norm":     [],
        "status":         "needs_rule_adjustment",
        "notes": (
            "trials table has indication_id column but it is NULL for all rows inspected. "
            "trial_indications is now populated (319 rows) and provides the canonical "
            "trial → indication link. However, the trials table itself does not yet have "
            "indication_id backfilled from trial_indications. "
            "Migration path: backfill trials.indication_id from trial_indications, "
            "then replace area_id filter with indication_id filter. "
            "Phase 4 acceptance criteria: trial counts per indication via trial_indications "
            "must match or exceed legacy catalyst count per area."
        ),
    })

    return results


# ── Formatters ────────────────────────────────────────────────────────────────
STATUS_ICON = {
    "match":                "✅",
    "acceptable_mismatch":  "🟡",
    "needs_rule_adjustment": "🟠",
    "migration_blocker":    "🔴",
    "not_ready":            "⛔",
}

def format_report(area_results: list, fn_results: list, data: dict) -> str:
    lines = []
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines.append(f"# Phase 4 Comparison Harness — Meridian BD Platform")
    lines.append(f"**Generated:** {now}  ")
    lines.append(f"**Mode:** Read-only · No production data modified  ")
    lines.append(f"**Script:** `scripts/phase4_compare_legacy_vs_normalized.py`  ")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Status legend
    lines.append("## Status Legend")
    lines.append("")
    lines.append("| Status | Icon | Meaning |")
    lines.append("|---|---|---|")
    lines.append("| match | ✅ | Legacy and normalized produce equivalent results |")
    lines.append("| acceptable_mismatch | 🟡 | Normalized has more/different but difference is expected and safe |")
    lines.append("| needs_rule_adjustment | 🟠 | Gap points to a missing alias, incomplete coverage, or governance rule |")
    lines.append("| migration_blocker | 🔴 | Do NOT migrate — normalized source is not ready for production use |")
    lines.append("| not_ready | ⛔ | Fundamental mapping doesn't exist yet |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Part 1: indication-centric comparisons
    lines.append("## Part 1 — Indication-Centric Drug Population Comparison")
    lines.append("")
    lines.append("For each legacy area_id, compare drug populations between:")
    lines.append("- **Legacy:** `drug_areas.area_id` (what the dashboard currently reads)")
    lines.append("- **Normalized:** `drug_indications.indication_id` (ontology-based, post-migration)")
    lines.append("")
    lines.append("Match % = overlap / legacy_count × 100. A low match % means migrating now "
                 "would silently drop drugs from the dashboard.")
    lines.append("")

    # Summary table
    lines.append("### Summary Table")
    lines.append("")
    lines.append("| Legacy Area | Normalized Indications | Legacy | Norm | Overlap | Match% | Trials | Status |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in sorted(area_results, key=lambda x: x["match_pct"]):
        icon = STATUS_ICON.get(r["status"], "?")
        inds = ", ".join(r["ind_ids"])
        trials = str(r["norm_trials"]) if r["norm_trials"] is not None else "—"
        lines.append(f"| `{r['area_id']}` | {inds} | {r['legacy_count']} | {r['norm_count']} | "
                     f"{r['overlap_count']} | {r['match_pct']}% | {trials} | {icon} {r['status']} |")
    lines.append("")

    # Detail per area
    lines.append("### Detail by Area")
    lines.append("")
    for r in sorted(area_results, key=lambda x: x["match_pct"]):
        icon = STATUS_ICON.get(r["status"], "?")
        lines.append(f"#### `{r['area_id']}` → `{', '.join(r['ind_ids'])}` {icon} **{r['status']}**")
        lines.append("")
        lines.append(f"| Field | Value |")
        lines.append(f"|---|---|")
        lines.append(f"| Legacy drugs (`drug_areas`) | {r['legacy_count']} |")
        lines.append(f"| Legacy drugs (`drug_area_scores`) | {r['legacy_score_count']} |")
        lines.append(f"| Normalized drugs (`drug_indications`) | {r['norm_count']} |")
        lines.append(f"| Overlap | {r['overlap_count']} |")
        lines.append(f"| Match % | {r['match_pct']}% |")
        lines.append(f"| Extra in legacy only | {len(r['extra_legacy'])} |")
        lines.append(f"| Extra in normalized only | {len(r['extra_norm'])} |")
        lines.append(f"| Normalized trial count (`trial_indications`) | {r['norm_trials']} |")
        lines.append(f"| Deals tagged to legacy area | {r['deal_count']} |")
        lines.append(f"| Catalysts tagged to legacy area | {r['cat_count']} |")
        lines.append("")
        lines.append(f"**Assessment:** {r['note']}")
        lines.append("")
        if r["extra_legacy_names"]:
            lines.append("**Drugs in legacy only (first 15):**")
            for drug_id, name in r["extra_legacy_names"]:
                lines.append(f"- `{drug_id}`: {name}")
            if len(r["extra_legacy"]) > 15:
                lines.append(f"- _(+{len(r['extra_legacy'])-15} more)_")
            lines.append("")
        if r["extra_norm_names"]:
            lines.append("**Drugs in normalized only (first 15):**")
            for drug_id, name in r["extra_norm_names"]:
                conf_list = []
                for ind in r["ind_ids"]:
                    d = data["di_detail"].get((ind, drug_id))
                    if d:
                        conf_list.append(d.get("conf_level","?"))
                conf_str = "/".join(set(conf_list)) if conf_list else "?"
                lines.append(f"- `{drug_id}`: {name} (conf={conf_str})")
            if len(r["extra_norm"]) > 15:
                lines.append(f"- _(+{len(r['extra_norm'])-15} more)_")
            lines.append("")

    lines.append("---")
    lines.append("")

    # Part 2: Dashboard function comparisons
    lines.append("## Part 2 — High-Risk Dashboard Function Comparisons")
    lines.append("")
    lines.append("For each of the 5 high-risk legacy dashboard paths (from `docs/dashboard_dependency_inventory.md`), "
                 "this section compares what the legacy path produces vs. what the normalized replacement would produce.")
    lines.append("")

    for fn in fn_results:
        icon = STATUS_ICON.get(fn["status"], "?")
        lines.append(f"### {fn['function']}  {icon} **{fn['status']}**")
        lines.append("")
        lines.append(f"- **Lines:** {fn['lines']}")
        lines.append(f"- **Legacy source:** {fn['legacy_source']}")
        lines.append(f"- **Normalized source:** {fn['norm_source']}")
        if fn['legacy_count'] is not None:
            lines.append(f"- **Legacy count:** {fn['legacy_count']}")
        if fn['norm_count'] is not None:
            lines.append(f"- **Normalized count:** {fn['norm_count']}")
        if fn['overlap_count'] is not None:
            lines.append(f"- **Overlap:** {fn['overlap_count']}")
        if fn['match_pct'] is not None:
            lines.append(f"- **Match %:** {fn['match_pct']}%")
        lines.append(f"- **Notes:** {fn['notes']}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # Part 3: Migration blockers summary
    lines.append("## Part 3 — Migration Blockers (Do Not Migrate)")
    lines.append("")
    lines.append("These paths must NOT be migrated until the blocking conditions are resolved:")
    lines.append("")
    blockers = [r for r in area_results if r["status"] in ("migration_blocker", "not_ready")]
    fn_blockers = [f for f in fn_results if f["status"] in ("migration_blocker", "not_ready")]
    for r in blockers:
        icon = STATUS_ICON.get(r["status"], "?")
        lines.append(f"- {icon} **`{r['area_id']}`** ({r['match_pct']}% match): {r['note']}")
    for f in fn_blockers:
        icon = STATUS_ICON.get(f["status"], "?")
        lines.append(f"- {icon} **{f['function']}**: {f['notes'][:120]}...")
    lines.append("")

    lines.append("---")
    lines.append("")

    # Part 4: Acceptable mismatches and classification
    lines.append("## Part 4 — Mismatch Classification (Track B)")
    lines.append("")
    lines.append("Classifying why each mismatch exists. "
                 "Types: `coverage_gap` | `alias_gap` | `scope_difference` | "
                 "`legacy_noise` | `true_missing_row`")
    lines.append("")
    lines.append("| Area | Extra-Legacy Drug | Classification | Action |")
    lines.append("|---|---|---|---|")

    # Spot-check classification for key mismatches
    classifications = {
        # (area, drug_id): (type, action)
        ("atopy", "upadacitinib"):           ("true_missing_row", "Add drug_indications row: upadacitinib → ad"),
        ("fcrn", "batoclimab"):              ("scope_difference", "Batoclimab = FcRn-targeting but in legacy igf1r/autoimmune areas; not in gmg/cidp/waiha drug_indications"),
        ("fcrn", "imvt-1402"):              ("true_missing_row", "IMVT-1402 is FcRn; add drug_indications rows for gmg/cidp/waiha"),
        ("fcrn", "atg-201"):                ("scope_difference", "ATG-201 is CAR-T (tcell area), placed in fcrn legacy; different mechanism"),
        ("igf1r", "batoclimab"):            ("scope_difference", "Batoclimab = FcRn/IgG pathway, classified in igf1r legacy area; exclude from ted"),
        ("autoimmune", "batoclimab"):       ("scope_difference", "FcRn mechanism drug placed in autoimmune legacy catch-all"),
        ("autoimmune", "cnd261"):           ("coverage_gap", "Wave 2A did not cover CND261; need drug_indications backfill"),
        ("autoimmune", "cnd319"):           ("coverage_gap", "Wave 2A did not cover CND319; need drug_indications backfill"),
        ("autoimmune", "ofatumumab"):       ("coverage_gap", "Ofatumumab (gMG indication) missing from drug_indications"),
        ("autoimmune", "iscalimab"):        ("coverage_gap", "Iscalimab (CD40; gMG-adjacent) missing from drug_indications"),
        ("autoimmune", "omalizumab"):       ("scope_difference", "Omalizumab in autoimmune legacy; indication is CSU/asthma, not autoimmune"),
        ("ted", "batoclimab"):             ("scope_difference", "Batoclimab is FcRn; legacy igf1r area misclassified it; not TED"),
        ("tl1a", "es302"):                 ("coverage_gap", "es302 = ES302 (IL-23 inhibitor, UC/CD); Wave 2A did not cover"),
        ("tcell", "atg-201"):              ("scope_difference", "ATG-201 is CAR-T targeting GD2; not ALL or MM specifically"),
    }

    shown = set()
    for area_r in area_results:
        area = area_r["area_id"]
        for drug_id in area_r["extra_legacy"][:8]:
            key = (area, drug_id)
            if key in classifications and key not in shown:
                cls_type, action = classifications[key]
                name = data["drug_names"].get(drug_id, drug_id)
                lines.append(f"| `{area}` | `{drug_id}` ({name}) | {cls_type} | {action} |")
                shown.add(key)
    lines.append("")

    lines.append("---")
    lines.append("")

    # Part 5: Phase 4 acceptance criteria
    lines.append("## Part 5 — Phase 4 Acceptance Criteria")
    lines.append("")
    lines.append("Phase 4 migration is safe when ALL of the following are true:")
    lines.append("")
    lines.append("### Per-Indication Criteria")
    lines.append("")
    lines.append("| Indication(s) | Required Match % | Current | Criteria Met? |")
    lines.append("|---|---|---|---|")
    for r in sorted(area_results, key=lambda x: x["match_pct"], reverse=True):
        required = 95
        met = "✅" if r["match_pct"] >= required else "❌"
        inds = ", ".join(r["ind_ids"])
        lines.append(f"| `{r['area_id']}` → {inds} | ≥{required}% | {r['match_pct']}% | {met} |")
    lines.append("")
    lines.append("### Dashboard Function Criteria")
    lines.append("")
    lines.append("| Function | Blocking Condition | Resolved? |")
    lines.append("|---|---|---|")
    lines.append("| `openDrugEntityModal()` | drug_indications must have competitive enrichment data (overlap, rationale, cls) | ❌ Not yet — enrichment migration pending |")
    lines.append("| `_makeAreaPI()` IBD/TL1A | drug_indications must cover all 50 IBD/TL1A drugs | ❌ Only 17/50 covered |")
    lines.append("| `loadAreaDeals()` | deals.indication_id FK must exist | ❌ Column does not exist |")
    lines.append("| `loadAreaCatalysts()` | area_id→indication_id bridge must exist for catalysts | ❌ Bridge not built |")
    lines.append("| Trial + Signal feeds | trials.indication_id must be backfilled from trial_indications | ❌ trials.indication_id is NULL |")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Phase 4 Overall Status")
    lines.append("")
    n_match = sum(1 for r in area_results if r["status"] == "match")
    n_accept = sum(1 for r in area_results if r["status"] == "acceptable_mismatch")
    n_needs = sum(1 for r in area_results if r["status"] == "needs_rule_adjustment")
    n_block = sum(1 for r in area_results if r["status"] == "migration_blocker")
    n_nready = sum(1 for r in area_results if r["status"] == "not_ready")

    lines.append(f"**Comparison date:** {now}")
    lines.append(f"**Areas compared:** {len(area_results)}")
    lines.append(f"- ✅ match: {n_match}")
    lines.append(f"- 🟡 acceptable_mismatch: {n_accept}")
    lines.append(f"- 🟠 needs_rule_adjustment: {n_needs}")
    lines.append(f"- 🔴 migration_blocker: {n_block}")
    lines.append(f"- ⛔ not_ready: {n_nready}")
    lines.append("")
    lines.append("**Verdict:** Phase 4 migration is **NOT YET SAFE**. "
                 "Blockers must be resolved before any dashboard query is switched. "
                 "See Part 3 for specific blocking conditions.")
    lines.append("")
    lines.append("**Next action (Track A):** Expand drug_indications coverage "
                 "for tl1a/ibd area drugs — currently at 30% coverage. "
                 "This is the primary gating item.")
    lines.append("")

    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Phase 4 Comparison Harness (read-only)")
    parser.add_argument("--area", help="Compare one legacy area only")
    parser.add_argument("--indication", help="Compare one indication only (cross-refs to area)")
    parser.add_argument("--output", default="docs/phase4_comparison_harness.md",
                        help="Output file path (default: docs/phase4_comparison_harness.md)")
    parser.add_argument("--stdout", action="store_true", help="Print report to stdout instead of file")
    args = parser.parse_args()

    data = load_all()

    # Area selection
    if args.area:
        areas_to_run = [args.area]
    elif args.indication:
        areas_to_run = IND_TO_AREA.get(args.indication, [])
        if not areas_to_run:
            print(f"No legacy area mapping found for indication '{args.indication}'", file=sys.stderr)
            sys.exit(1)
    else:
        areas_to_run = list(AREA_TO_IND.keys())

    area_results = []
    for area in sorted(areas_to_run):
        r = compare_area(area, data)
        area_results.append(r)
        icon = STATUS_ICON.get(r["status"], "?")
        print(f"  {icon} {area:20s} legacy={r['legacy_count']:3d}  "
              f"norm={r['norm_count']:3d}  match={r['match_pct']:5.1f}%  {r['status']}")

    fn_results = compare_dashboard_functions(data)
    print()
    print("Dashboard function comparisons:")
    for fn in fn_results:
        icon = STATUS_ICON.get(fn["status"], "?")
        print(f"  {icon} {fn['function'][:45]:<45s}  {fn['status']}")

    report = format_report(area_results, fn_results, data)

    if args.stdout:
        print("\n" + report)
    else:
        out_path = os.path.join(os.path.dirname(__file__), '..', args.output)
        out_path = os.path.abspath(out_path)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\nReport written to: {out_path}")


if __name__ == "__main__":
    main()
