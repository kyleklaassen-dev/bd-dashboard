#!/usr/bin/env python3
"""
seed_preclinical_competitors.py
Seeds preclinical TED × IGF-1R competitors that are missing from the DB.

Audit results:
  Bucket C (company + drug both missing):
    - Ollin Biosciences / OLN102   (TSHR×IGF-1R bispecific, preclinical)
    - Septerna         / SP-1351   (TSHR GPCR small molecule, preclinical)
    - Crinetics        / CRN12755  (SST-targeted, preclinical)
    - Alumis           / lonigutamab (anti-TSHR mAb, preclinical)
    - Minghui Pharma   / MHB018A   (anti-IGF-1R mAb, preclinical China)

  Bucket B (company exists, drug missing):
    - Innovent Biologics / ibi311 / SYCUME  (anti-IGF-1R, approved China)

Run:
  python3 scripts/seed_preclinical_competitors.py [--dry-run]
"""

import json, os, sys, urllib.request, urllib.error, datetime

_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from _common import load_credentials  # noqa: E402
import _db                              # noqa: E402

DRY_RUN = "--dry-run" in sys.argv

SUPABASE_URL, SUPABASE_KEY, _ = load_credentials(require_anthropic=False)
_db.init_db(SUPABASE_URL, SUPABASE_KEY)

NOW = datetime.datetime.utcnow().isoformat()


def section(title):
    print(f"\n{'═'*60}\n  {title}\n{'═'*60}")


def get(table, params):
    return _db.sb_get(table, params)


def upsert(table, rows, merge=True):
    if DRY_RUN:
        print(f"  [DRY RUN] Would upsert {len(rows)} row(s) into {table}")
        for r in rows if len(rows) <= 5 else rows[:5]:
            print(f"    {r}")
        return len(rows)
    if merge:
        result = _db.sb_upsert(table, rows)
        return len(result) if result else len(rows)
    # _db.sb_upsert only supports merge-duplicates; ignore-duplicates needs a
    # thin local POST (precedent: sync_collection_queue.py / seed_strategic_views.py)
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=ignore-duplicates,return=representation",
    }
    data = json.dumps(rows if isinstance(rows, list) else [rows]).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{table}", data=data, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req) as r:
            result = json.loads(r.read()) if r.status in (200, 201) else []
            return len(result) if result else len(rows)
    except urllib.error.HTTPError as e:
        print(f"  UPSERT {table} HTTP {e.code}: {e.read().decode()[:400]}")
        return 0


# ─────────────────────────────────────────────────────────────────
# 0. Pre-flight
# ─────────────────────────────────────────────────────────────────
section("PRE-FLIGHT")

BUCKET_C_CO_IDS   = ["ollin", "septerna", "crinetics", "alumis", "minghui"]
BUCKET_C_DRUG_IDS = ["oln102", "sp-1351", "crn12755", "lonigutamab", "mhb018a"]
BUCKET_B_DRUG_ID  = "ibi311"

existing_cos   = {r["id"] for r in get("companies", {
    "id": f"in.({','.join(BUCKET_C_CO_IDS)})",
    "select": "id",
})}
existing_drugs = {r["id"] for r in get("drugs", {
    "id": f"in.({','.join(BUCKET_C_DRUG_IDS + [BUCKET_B_DRUG_ID])})",
    "select": "id",
})}

# Resolve Innovent company_id (Bucket B)
innovent_rows = get("companies", {"name": "ilike.innovent*", "select": "id,name"})
if not innovent_rows:
    print("  ⚠️  Innovent company not found by name — trying id=innovent")
    innovent_rows = get("companies", {"id": "eq.innovent", "select": "id,name"})
INNOVENT_ID = innovent_rows[0]["id"] if innovent_rows else None

print(f"  Bucket C companies already in DB: {existing_cos or 'none'}")
print(f"  Bucket C/B drugs already in DB:   {existing_drugs or 'none'}")
print(f"  Innovent company_id resolved:      {INNOVENT_ID or 'NOT FOUND ⚠️'}")


# ─────────────────────────────────────────────────────────────────
# 1. Companies (Bucket C only — Innovent already exists)
# ─────────────────────────────────────────────────────────────────
section("SECTION 1: companies (Bucket C)")

ALL_COMPANIES = [
    {
        "id":              "ollin",
        "name":            "Ollin Biosciences",
        "ticker":          None,
        "exchange":        None,
        "tagline":         "TSHR×IGF-1R bispecific antibody platform for TED",
        "status":          "active",
        "geography":       "US",
        "ta_focus_1":      "Ophthalmology",
        "ta_focus_2":      "Autoimmune",
        "last_enriched_at": NOW,
        "overlap":         "Direct",
    },
    {
        "id":              "septerna",
        "name":            "Septerna",
        "ticker":          None,
        "exchange":        None,
        "tagline":         "GPCR-targeted small molecules for endocrine and autoimmune diseases",
        "status":          "active",
        "geography":       "US",
        "ta_focus_1":      "Endocrinology",
        "ta_focus_2":      "Autoimmune",
        "last_enriched_at": NOW,
        "overlap":         "Adjacent",
    },
    {
        "id":              "crinetics",
        "name":            "Crinetics Pharmaceuticals",
        "ticker":          "CRNX",
        "exchange":        "NASDAQ",
        "tagline":         "Somatostatin receptor-targeted medicines for endocrine diseases",
        "status":          "active",
        "geography":       "US",
        "ta_focus_1":      "Endocrinology",
        "ta_focus_2":      "Ophthalmology",
        "last_enriched_at": NOW,
        "overlap":         "Adjacent",
    },
    {
        "id":              "alumis",
        "name":            "Alumis",
        "ticker":          "ALMS",
        "exchange":        "NASDAQ",
        "tagline":         "Precision autoimmune therapies",
        "status":          "active",
        "geography":       "US",
        "ta_focus_1":      "Autoimmune",
        "ta_focus_2":      "Ophthalmology",
        "last_enriched_at": NOW,
        "overlap":         "Adjacent",
    },
    {
        "id":              "minghui",
        "name":            "Minghui Pharmaceutical",
        "ticker":          None,
        "exchange":        None,
        "tagline":         "China-based biotech; anti-IGF-1R mAb platform",
        "status":          "active",
        "geography":       "China",
        "ta_focus_1":      "Ophthalmology",
        "ta_focus_2":      "Oncology",
        "last_enriched_at": NOW,
        "overlap":         "Direct",
    },
]

companies_to_insert = [c for c in ALL_COMPANIES if c["id"] not in existing_cos]
if companies_to_insert:
    n = upsert("companies", companies_to_insert, merge=True)
    for c in companies_to_insert:
        print(f"  ✅  {c['id']} ({c['name']})")
else:
    print("  All companies already present")


# ─────────────────────────────────────────────────────────────────
# 2. Drugs
#    Bucket C: oln102, sp-1351, crn12755, lonigutamab, mhb018a
#    Bucket B: ibi311 (under INNOVENT_ID)
# ─────────────────────────────────────────────────────────────────
section("SECTION 2: drugs")

ALL_DRUGS = [
    # ── Bucket B: ibi311 / SYCUME (Innovent — approved China) ────
    {
        "id":               "ibi311",
        "name":             "ibi311",
        "brand_name":       "SYCUME",
        "company_id":       INNOVENT_ID,
        "mechanism":        "Anti-IGF-1R monoclonal antibody",
        "stage":            "Approved",
        "route":            "IV",
        "target":           "IGF-1R",
        "modality":         "anti-IGF-1R monoclonal antibody",
        "drug_format":      "mAb",
        "cls":              "Anti-IGF-1R mAb",
        "indication_short": "TED",
        "phase_display":    "Approved (NMPA China, March 2025)",
        "overlap":          "Direct",
        "overlap_rationale": "Same IGF-1R mechanism and TED indication as Tepezza; approved only in China. Relevant as China market reference; not a direct US competitor.",
        "confidence_level": "confirmed",
        "data_source":      "manual",
        "source_url":       "https://www.innoventbio.com/en/news/press-release/innovent-biologics-receives-nmpa-approval-for-ibi311",
        "vs_ailux":         "Anti-IGF-1R mAb approved by NMPA China (March 2025). Same mechanism as Tepezza. China-only; demonstrates Asian market regulatory path for IGF-1R in TED. Innovent may pursue ex-China partnerships.",
        "ailux_angle":      "China IGF-1R approval establishes regional biosimilar-competitive dynamic; potential partnership target for Asia ex-China rights",
        "last_verified":    NOW[:10],
        "created_at":       NOW,
        "updated_at":       NOW,
    },
    # ── OLN102 (Ollin — TSHR×IGF-1R bispecific, preclinical) ────
    {
        "id":               "oln102",
        "name":             "OLN102",
        "brand_name":       None,
        "company_id":       "ollin",
        "mechanism":        "TSHR×IGF-1R bispecific antibody",
        "stage":            "Preclinical",
        "route":            "IV",
        "target":           "TSHR / IGF-1R",
        "modality":         "bispecific antibody",
        "drug_format":      "bispecific mAb",
        "cls":              "Bispecific mAb",
        "indication_short": "TED",
        "phase_display":    "Preclinical (IND unconfirmed May 2026)",
        "overlap":          "Direct",
        "overlap_rationale": "Directly targets both key TED mechanisms simultaneously (TSHR and IGF-1R); if validated, could obsolete single-target approach entirely",
        "confidence_level": "supported",
        "data_source":      "manual",
        "source_url":       "https://www.ollinbiosciences.com",
        "vs_ailux":         "Preclinical TSHR×IGF-1R bispecific. IND filing unconfirmed as of May 2026. If IND filed and Phase 1 initiated, becomes the definitive 'next-gen TED' asset. Recheck CT.gov Q4 2026.",
        "ailux_angle":      "Potential game-changer: bispecific hits both root causes simultaneously. Preclinical risk = high but strategic signal = very high",
        "last_verified":    NOW[:10],
        "created_at":       NOW,
        "updated_at":       NOW,
    },
    # ── SP-1351 (Septerna — TSHR GPCR small molecule, preclinical) ─
    {
        "id":               "sp-1351",
        "name":             "SP-1351",
        "brand_name":       None,
        "company_id":       "septerna",
        "mechanism":        "TSHR GPCR inverse agonist / antagonist (oral small molecule)",
        "stage":            "Preclinical",
        "route":            "oral",
        "target":           "TSHR",
        "modality":         "small molecule",
        "drug_format":      "small molecule",
        "cls":              "TSHR antagonist",
        "indication_short": "TED / Graves disease",
        "phase_display":    "Preclinical",
        "overlap":          "Adjacent",
        "overlap_rationale": "Oral TSHR-targeted small molecule; different mechanism from IGF-1R mAbs but same upstream autoimmune driver. Oral route vs IV Tepezza is key differentiator.",
        "confidence_level": "supported",
        "data_source":      "manual",
        "source_url":       "https://www.septerna.com",
        "vs_ailux":         "Oral TSHR GPCR small molecule. Preclinical. If clinical-stage, represents oral route alternative addressing TSHR upstream — potentially disrupts IV IGF-1R antibody class.",
        "ailux_angle":      "Oral TSHR targeting + preclinical = early watch. If Phase 1 data shows TSHR activity, escalates from watch to primary concern for IGF-1R class.",
        "last_verified":    NOW[:10],
        "created_at":       NOW,
        "updated_at":       NOW,
    },
    # ── CRN12755 (Crinetics — SST-targeted, preclinical) ─────────
    {
        "id":               "crn12755",
        "name":             "CRN12755",
        "brand_name":       None,
        "company_id":       "crinetics",
        "mechanism":        "Somatostatin receptor 2 (SST2) agonist",
        "stage":            "Preclinical",
        "route":            "oral",
        "target":           "SST2",
        "modality":         "small molecule",
        "drug_format":      "small molecule",
        "cls":              "SST2 agonist",
        "indication_short": "TED",
        "phase_display":    "Preclinical",
        "overlap":          "Adjacent",
        "overlap_rationale": "SST2 receptors expressed in orbital fibroblasts; SST2 agonism may reduce proptosis via different pathway than IGF-1R. Adjacent mechanism, same indication.",
        "confidence_level": "supported",
        "data_source":      "manual",
        "source_url":       "https://www.crinetics.com",
        "vs_ailux":         "Oral SST2 agonist for TED. Preclinical. Crinetics is building an SST-targeted platform across endocrine diseases. TED is a logical extension given orbital SST2 expression.",
        "ailux_angle":      "Mechanism diversification play. If SST2 data show proptosis reduction, creates oral adjunct or alternative to IGF-1R mAbs.",
        "last_verified":    NOW[:10],
        "created_at":       NOW,
        "updated_at":       NOW,
    },
    # ── lonigutamab (Alumis — anti-TSHR mAb, preclinical) ────────
    {
        "id":               "lonigutamab",
        "name":             "lonigutamab",
        "brand_name":       None,
        "company_id":       "alumis",
        "mechanism":        "Anti-TSHR monoclonal antibody",
        "stage":            "Preclinical",
        "route":            "IV",
        "target":           "TSHR",
        "modality":         "anti-TSHR monoclonal antibody",
        "drug_format":      "mAb",
        "cls":              "Anti-TSHR mAb",
        "indication_short": "TED / Graves disease",
        "phase_display":    "Preclinical",
        "overlap":          "Adjacent",
        "overlap_rationale": "Anti-TSHR mAb targets the autoimmune root cause upstream of IGF-1R activation. Adjacent mechanism, same disease. Competes with YB-101 in TSHR space.",
        "confidence_level": "supported",
        "data_source":      "manual",
        "source_url":       "https://www.alumis.com",
        "vs_ailux":         "Anti-TSHR mAb for TED. Preclinical. Alumis is autoimmune-focused; TSHR is a natural extension. Competes with YB-101 (Yarrow) in TSHR mAb space.",
        "ailux_angle":      "TSHR mAb space getting crowded (YB-101 in Phase 1b, lonigutamab preclinical). Watch for IND filing — triggers TSHR vs IGF-1R debate.",
        "last_verified":    NOW[:10],
        "created_at":       NOW,
        "updated_at":       NOW,
    },
    # ── MHB018A (Minghui — anti-IGF-1R, preclinical China) ───────
    {
        "id":               "mhb018a",
        "name":             "MHB018A",
        "brand_name":       None,
        "company_id":       "minghui",
        "mechanism":        "Anti-IGF-1R monoclonal antibody",
        "stage":            "Preclinical",
        "route":            "IV",
        "target":           "IGF-1R",
        "modality":         "anti-IGF-1R monoclonal antibody",
        "drug_format":      "mAb",
        "cls":              "Anti-IGF-1R mAb",
        "indication_short": "TED",
        "phase_display":    "Preclinical (China)",
        "overlap":          "Direct",
        "overlap_rationale": "Same IGF-1R mechanism as Tepezza; China-based development mirrors IBI311/SYCUME path. Multiple China IGF-1R entrants emerging.",
        "confidence_level": "supported",
        "data_source":      "manual",
        "source_url":       "https://www.minghui-pharma.com",
        "vs_ailux":         "China-based anti-IGF-1R mAb. Preclinical. Part of a second wave of China IGF-1R TED candidates following IBI311 NMPA approval. Watch for IND filing.",
        "ailux_angle":      "China market IGF-1R crowding — IBI311 approved, MHB018A in preclinical. Signals China as an increasingly important TED × IGF-1R battleground.",
        "last_verified":    NOW[:10],
        "created_at":       NOW,
        "updated_at":       NOW,
    },
]

# Only skip ibi311 if Innovent ID couldn't be resolved
drugs_to_insert = []
for d in ALL_DRUGS:
    if d["id"] in existing_drugs:
        print(f"  {d['id']} already exists — skipping")
        continue
    if d["id"] == "ibi311" and INNOVENT_ID is None:
        print(f"  ⚠️  ibi311 skipped — Innovent company_id not resolved")
        continue
    drugs_to_insert.append(d)

if drugs_to_insert:
    n = upsert("drugs", drugs_to_insert, merge=True)
    for d in drugs_to_insert:
        print(f"  ✅  {d['id']} ({d['name']}, {d['stage']}, {d['target']})")
else:
    print("  All drugs already present")

inserted_drug_ids = {d["id"] for d in drugs_to_insert}


# ─────────────────────────────────────────────────────────────────
# 3. drug_areas
#    Each new drug gets entries for igf1r + ted (where applicable)
# ─────────────────────────────────────────────────────────────────
section("SECTION 3: drug_areas")

# Drug → area mapping
# - igf1r + ted: direct mechanism drugs
# - igf1r only: TED-adjacent mechanisms that inform the IGF-1R landscape
# - autoimmune: for broad autoimmune-mechanism drugs
DRUG_AREA_MAP = {
    "ibi311":      ["igf1r", "ted"],
    "oln102":      ["igf1r", "ted"],           # bispecific: targets both key TED mechanisms
    "sp-1351":     ["ted", "autoimmune"],       # TSHR → TED upstream
    "crn12755":    ["ted"],                      # SST2 orbital pathway → TED
    "lonigutamab": ["ted", "autoimmune"],       # TSHR mAb → TED upstream
    "mhb018a":     ["igf1r", "ted"],            # anti-IGF-1R → same landscape as Tepezza
}

da_rows = []
for drug_id, areas in DRUG_AREA_MAP.items():
    if drug_id in inserted_drug_ids:
        for area_id in areas:
            da_rows.append({"drug_id": drug_id, "area_id": area_id})

if da_rows:
    n = upsert("drug_areas", da_rows, merge=False)
    print(f"  ✅  {len(da_rows)} drug_area rows written:")
    for r in da_rows:
        print(f"    {r['drug_id']:<18} → {r['area_id']}")
else:
    print("  No new drug_area rows (all drugs already existed)")


# ─────────────────────────────────────────────────────────────────
# 4. drug_area_scores
#    source_url + confidence_level — essential for source_validation
#    dimension of landscape_dependency_score
# ─────────────────────────────────────────────────────────────────
section("SECTION 4: drug_area_scores")

DRUG_AREA_SCORES = [
    # ── ibi311 ────────────────────────────────────────────────────
    {"drug_id": "ibi311", "area_id": "igf1r",
     "overlap": "Direct", "confidence_level": "confirmed",
     "source_url": "https://www.innoventbio.com/en/news/press-release/innovent-biologics-receives-nmpa-approval-for-ibi311",
     "last_enriched_at": NOW},
    {"drug_id": "ibi311", "area_id": "ted",
     "overlap": "Direct", "confidence_level": "confirmed",
     "source_url": "https://www.innoventbio.com/en/news/press-release/innovent-biologics-receives-nmpa-approval-for-ibi311",
     "last_enriched_at": NOW},
    # ── OLN102 ───────────────────────────────────────────────────
    {"drug_id": "oln102", "area_id": "igf1r",
     "overlap": "Direct", "confidence_level": "supported",
     "source_url": "https://www.ollinbiosciences.com",
     "last_enriched_at": NOW},
    {"drug_id": "oln102", "area_id": "ted",
     "overlap": "Direct", "confidence_level": "supported",
     "source_url": "https://www.ollinbiosciences.com",
     "last_enriched_at": NOW},
    # ── SP-1351 ──────────────────────────────────────────────────
    {"drug_id": "sp-1351", "area_id": "ted",
     "overlap": "Adjacent", "confidence_level": "supported",
     "source_url": "https://www.septerna.com",
     "last_enriched_at": NOW},
    {"drug_id": "sp-1351", "area_id": "autoimmune",
     "overlap": "Adjacent", "confidence_level": "supported",
     "source_url": "https://www.septerna.com",
     "last_enriched_at": NOW},
    # ── CRN12755 ─────────────────────────────────────────────────
    {"drug_id": "crn12755", "area_id": "ted",
     "overlap": "Adjacent", "confidence_level": "supported",
     "source_url": "https://www.crinetics.com",
     "last_enriched_at": NOW},
    # ── lonigutamab ───────────────────────────────────────────────
    {"drug_id": "lonigutamab", "area_id": "ted",
     "overlap": "Adjacent", "confidence_level": "supported",
     "source_url": "https://www.alumis.com",
     "last_enriched_at": NOW},
    {"drug_id": "lonigutamab", "area_id": "autoimmune",
     "overlap": "Adjacent", "confidence_level": "supported",
     "source_url": "https://www.alumis.com",
     "last_enriched_at": NOW},
    # ── MHB018A ──────────────────────────────────────────────────
    {"drug_id": "mhb018a", "area_id": "igf1r",
     "overlap": "Direct", "confidence_level": "supported",
     "source_url": "https://www.minghui-pharma.com",
     "last_enriched_at": NOW},
    {"drug_id": "mhb018a", "area_id": "ted",
     "overlap": "Direct", "confidence_level": "supported",
     "source_url": "https://www.minghui-pharma.com",
     "last_enriched_at": NOW},
]

das_to_insert = [r for r in DRUG_AREA_SCORES if r["drug_id"] in inserted_drug_ids]

if das_to_insert:
    n = upsert("drug_area_scores", das_to_insert, merge=False)
    print(f"  ✅  {len(das_to_insert)} drug_area_scores rows written")
    for r in das_to_insert:
        print(f"    {r['drug_id']:<18} {r['area_id']:<12} {r['overlap']:<12} {r['confidence_level']}")
else:
    print("  No new drug_area_scores (all drugs already existed)")


# ─────────────────────────────────────────────────────────────────
# 5. Verify
# ─────────────────────────────────────────────────────────────────
section("VERIFICATION")

all_drug_ids = ["ibi311", "oln102", "sp-1351", "crn12755", "lonigutamab", "mhb018a"]
check_drugs = get("drugs", {
    "id":     f"in.({','.join(all_drug_ids)})",
    "select": "id,name,company_id,stage,target",
    "order":  "stage.asc,id.asc",
})
print(f"  Drugs in DB ({len(check_drugs)}/{len(all_drug_ids)}):")
for d in check_drugs:
    print(f"    {'✅' if d['id'] in inserted_drug_ids else '·'} {d['id']:<18} stage={d['stage']:<12} target={d['target']:<20} co={d['company_id']}")

missing_drugs = set(all_drug_ids) - {d["id"] for d in check_drugs}
if missing_drugs:
    print(f"  ⚠️  Still missing: {missing_drugs}")

all_co_ids = ["ollin", "septerna", "crinetics", "alumis", "minghui"]
check_cos = get("companies", {
    "id": f"in.({','.join(all_co_ids)})",
    "select": "id,name,status",
})
print(f"\n  Companies in DB ({len(check_cos)}/{len(all_co_ids)}):")
for c in check_cos:
    print(f"    {'✅' if c['id'] not in existing_cos else '·'} {c['id']:<12} {c['name']}")

check_da = get("drug_areas", {
    "drug_id": f"in.({','.join(all_drug_ids)})",
    "select":  "drug_id,area_id",
    "order":   "drug_id.asc,area_id.asc",
})
print(f"\n  drug_areas ({len(check_da)} rows):")
for r in check_da:
    print(f"    {r['drug_id']:<18} → {r['area_id']}")

print(f"\n{'═'*60}")
if DRY_RUN:
    print("  [DRY RUN complete — no DB writes]")
else:
    print("  ✅  Done.")
    print("  Next: python3 scripts/compute_landscape_coverage.py")
    print("        Verify preclinical drugs appear in IGF-1R tab 'All' pill")
print(f"{'═'*60}")
