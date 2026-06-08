#!/usr/bin/env python3
"""
add_competitive_relevance.py
Adds competitive_relevance + relevance_rationale columns to drug_area_scores
and seeds values for all TED × IGF-1R drugs.

competitive_relevance separates STRATEGIC IMPORTANCE from DEVELOPMENT STAGE.
Ailux is preclinical — stage-based sorting puts Tepezza (approved, benchmark)
above OLN102 (preclinical, but potential class disruptor). This fixes that.

Enum: very_high | high | medium | low | monitor

Values for IGF-1R × TSHR landscape (2026-05-24):
  very_high: veligrotug (PDUFA June 30), elegrobart (Phase 3 positive, BLA Q1 2027), oln102 (bispecific)
  high:      yb-101 (TSHR mAb Phase 1b), sp-1351 (oral TSHR SM), crn12755 (oral SST2)
  medium:    lonigutamab (TSHR mAb preclinical), linsitinib (oral IGF-1R SM), mhb018a (China IGF-1R)
  low:       teprotumumab (approved benchmark), ibi311 (China-only approved)
  monitor:   batoclimab (failed FcRn), efgartigimod (failed FcRn)

Run:
  python3 scripts/add_competitive_relevance.py [--dry-run]
"""

import json, os, sys, datetime

_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from _common import load_credentials  # noqa: E402
import _db                              # noqa: E402

DRY_RUN  = "--dry-run" in sys.argv

SB_URL, SERVICE_KEY, _ = load_credentials(require_anthropic=False)
_db.init_db(SB_URL, SERVICE_KEY)

NOW = datetime.datetime.utcnow().isoformat()


def section(title):
    print(f"\n{'═'*60}\n  {title}\n{'═'*60}")


def get(table, params):
    return _db.sb_get(table, params)


def patch(table, filters, updates):
    if DRY_RUN:
        filter_str = " AND ".join(f"{k}={v}" for k, v in filters.items())
        print(f"  [DRY RUN] PATCH {table} WHERE {filter_str} → {list(updates.keys())}")
        return True
    return _db.sb_patch(table, updates, filters)


# ─────────────────────────────────────────────────────────────────
# 0. Add columns via DDL (using PostgREST ALTER — not directly possible;
#    must go through Supabase SQL editor OR we probe and patch only if
#    column exists. We'll attempt to PATCH a known row with the new field
#    and interpret the 400 error as "column missing".)
#
#    The actual ALTER must be run via Supabase SQL editor.
#    This script outputs the DDL to run, then seeds the values.
# ─────────────────────────────────────────────────────────────────
section("DDL CHECK")

print("""
  Run this SQL in Supabase SQL editor first (if not already applied):

  ALTER TABLE drug_area_scores
      ADD COLUMN IF NOT EXISTS competitive_relevance TEXT
          CHECK (competitive_relevance IN ('very_high','high','medium','low','monitor')),
      ADD COLUMN IF NOT EXISTS relevance_rationale TEXT;

  Then re-run this script to seed values.
""")

# Probe: try to read competitive_relevance from one row
probe = get("drug_area_scores", {
    "drug_id": "eq.teprotumumab",
    "area_id": "eq.igf1r",
    "select":  "drug_id,competitive_relevance",
    "limit":   "1",
})
if probe and "competitive_relevance" in probe[0]:
    print("  ✅  Column competitive_relevance exists — proceeding to seed")
elif probe:
    print("  ❌  Column competitive_relevance does NOT exist yet.")
    print("      Run the DDL above in Supabase SQL editor, then re-run this script.")
    sys.exit(1)
else:
    print("  ⚠️  No rows found for probe — check drug_area_scores has teprotumumab/igf1r")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────
# 1. Seed competitive_relevance values
#    Covers all drug_area_scores rows for the TED × IGF-1R landscape
# ─────────────────────────────────────────────────────────────────
section("SECTION 1: seeding competitive_relevance")

# (drug_id, area_id, relevance, rationale)
RELEVANCE_DATA = [
    # ── very_high ─────────────────────────────────────────────────
    ("veligrotug", "igf1r", "very_high",
     "BLA Filed, PDUFA June 30 2026 (IV). If approved, first non-Tepezza IGF-1R in US market. Immediate commercial threat."),
    ("veligrotug", "ted", "very_high",
     "BLA Filed, PDUFA June 30 2026 (IV). Direct TED competitor to Tepezza with same mechanism, different company."),

    ("elegrobart", "igf1r", "very_high",
     "Phase 3 — REVEAL-1 (active TED) + REVEAL-2 (chronic TED) both positive as of Q1/Q2 2026. BLA Q1 2027. SC autoinjector = paradigm shift: home dosing eliminates infusion center."),
    ("elegrobart", "ted", "very_high",
     "Phase 3 positive (both active + chronic TED trials). BLA Q1 2027. First SC autoinjector in TED — major route differentiation from IV Tepezza."),

    ("oln102", "igf1r", "very_high",
     "TSHR×IGF-1R bispecific — hits both TED mechanisms simultaneously. If IND filed (recheck Q4 2026), potential best-in-class disruptor."),
    ("oln102", "ted", "very_high",
     "TSHR×IGF-1R bispecific. Preclinical risk is high but strategic signal is highest in landscape — simultaneous dual-target approach could make single-target drugs obsolete."),

    # ── high ──────────────────────────────────────────────────────
    ("yb-101", "igf1r", "high",
     "Anti-TSHR mAb targeting TED root cause upstream of IGF-1R. Phase 1b US 2026. If Phase 1 shows durable proptosis response, repositions TSHR vs IGF-1R debate entirely."),
    ("yb-101", "ted", "high",
     "Anti-TSHR mAb Phase 1b. Upstream mechanism: if TSHR is sufficient for TED, IGF-1R drugs become downstream. Revalidate Q3 2026 after data."),

    ("sp-1351", "ted", "high",
     "Oral TSHR GPCR small molecule. Preclinical. Oral route + TSHR mechanism = double differentiation from IV IGF-1R mAbs. Watch for IND filing."),
    ("sp-1351", "autoimmune", "high",
     "TSHR GPCR targeting in autoimmune disease. Oral small molecule approach — platform potential beyond TED."),

    ("crn12755", "ted", "high",
     "Oral SST2 agonist for TED. Preclinical. Adjacent mechanism (orbital SST2 expression). Oral route is key differentiator vs IV Tepezza class."),

    # ── medium ────────────────────────────────────────────────────
    ("lonigutamab", "ted", "medium",
     "Anti-TSHR mAb preclinical. TSHR space is already occupied by YB-101 (Phase 1b ahead). Watch for IND — will crowd the TSHR mAb space with YB-101."),
    ("lonigutamab", "autoimmune", "medium",
     "Anti-TSHR mAb in autoimmune disease. Preclinical. Alumis autoimmune platform may accelerate but YB-101 has head start."),

    ("linsitinib", "igf1r", "medium",
     "Oral IGF-1R small molecule Phase 2/3. Route advantage (oral) but Roche is not TED-focused — execution risk. Mechanism same as Tepezza."),
    ("linsitinib", "ted", "medium",
     "Oral IGF-1R SM Phase 2/3 for TED. Oral route differentiator but Roche's strategic commitment to TED is unclear."),

    ("mhb018a", "igf1r", "medium",
     "China-based anti-IGF-1R mAb preclinical. Mirrors IBI311 path. Second China IGF-1R TED entrant — signals China market crowding. Minimal US relevance."),
    ("mhb018a", "ted", "medium",
     "China anti-IGF-1R TED preclinical. Relevant for Asia market landscape; not a direct US/EU competitive threat at this stage."),

    # ── low ───────────────────────────────────────────────────────
    ("teprotumumab", "igf1r", "low",
     "Tepezza — approved US + Japan. Market benchmark: Ailux would partner with Amgen or around Tepezza, not compete. Low competitive relevance = high strategic relevance as reference asset."),
    ("teprotumumab", "ted", "low",
     "Approved IGF-1R mAb. The reference asset — any Ailux BD move in TED is defined in relation to Tepezza. Low competitive threat, high strategic anchor."),

    ("ibi311", "igf1r", "low",
     "SYCUME — approved China only. Same mechanism as Tepezza. Relevant as Asia market reference and potential partnership target; not a direct US competitor."),
    ("ibi311", "ted", "low",
     "NMPA approved China March 2025. China-market reference for IGF-1R approval pathway. Partnership signal: Innovent may seek ex-China rights holder."),

    # ── monitor ───────────────────────────────────────────────────
    ("batoclimab", "fcrn", "monitor",
     "Failed Phase 3 TED (April 2026). FcRn mechanism invalidated for TED. Monitor as negative data signal confirming IGF-1R is the validated path."),
    ("batoclimab", "ted", "monitor",
     "Phase 3 TED failure. Key signal: FcRn does not work in TED. Strengthens IGF-1R/TSHR thesis. No active threat."),
    ("batoclimab", "autoimmune", "monitor",
     "FcRn mechanism failed in TED but may still work in other autoimmune indications (Graves disease ongoing). Watch IMVT-1402 data."),
    ("batoclimab", "igf1r", "monitor",
     "Failed FcRn TED trial. IGF-1R relevance: failed competitor confirms IGF-1R is the right target. Monitor for any follow-on TED program."),

    ("efgartigimod", "fcrn", "monitor",
     "UplighTED discontinued Dec 2025 (IDMC recommendation). FcRn mechanism invalidated for TED (same conclusion as batoclimab failure)."),
    ("efgartigimod", "autoimmune", "monitor",
     "FcRn failed in TED; argenx continues FcRn in other autoimmune. Monitor ADHERE/ADAPT trials for MG/CIDP success — those don't affect TED thesis."),
    ("efgartigimod", "ted", "monitor",
     "UplighTED SC discontinued Dec 2025. FcRn mechanism failure confirmed. No active TED threat."),
]

# Patch each row
ok_count = 0
fail_count = 0
for drug_id, area_id, relevance, rationale in RELEVANCE_DATA:
    ok = patch(
        "drug_area_scores",
        {"drug_id": f"eq.{drug_id}", "area_id": f"eq.{area_id}"},
        {"competitive_relevance": relevance, "relevance_rationale": rationale,
         "last_enriched_at": NOW},
    )
    if ok:
        ok_count += 1
        rel_icon = {"very_high": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "monitor": "⚫"}.get(relevance, "·")
        print(f"  {rel_icon} {drug_id:<18} × {area_id:<12} → {relevance}")
    else:
        fail_count += 1
        print(f"  ❌ {drug_id:<18} × {area_id:<12} FAILED")

print(f"\n  {ok_count} patched, {fail_count} failed")


# ─────────────────────────────────────────────────────────────────
# 2. Verify — show distribution
# ─────────────────────────────────────────────────────────────────
section("VERIFICATION")

rows = get("drug_area_scores", {
    "area_id": "in.(igf1r,ted,fcrn,autoimmune)",
    "select":  "drug_id,area_id,competitive_relevance",
    "order":   "competitive_relevance.asc,drug_id.asc",
})

# Group by relevance
from collections import defaultdict
by_rel = defaultdict(list)
for r in rows:
    rel = r.get("competitive_relevance") or "—"
    by_rel[rel].append(f"{r['drug_id']} × {r['area_id']}")

order = ["very_high", "high", "medium", "low", "monitor", "—"]
icons = {"very_high": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "monitor": "⚫", "—": "·"}
for rel in order:
    if rel in by_rel:
        print(f"\n  {icons[rel]} {rel.upper()} ({len(by_rel[rel])}):")
        for entry in by_rel[rel]:
            print(f"      {entry}")

print(f"\n{'═'*60}")
if DRY_RUN:
    print("  [DRY RUN — no writes]")
else:
    print("  ✅  Done. Update dashboard sort logic next: competitive_relevance DESC, stage ASC")
print(f"{'═'*60}")
