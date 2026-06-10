#!/usr/bin/env python3
"""
seed_tl1a_companies.py
======================
One-time (re-runnable) script that seeds all TL1A_PROGRAMS static data
from index.html into Supabase so the pipeline can enrich them.

Writes to:
  companies      — id, name, ticker, company_type, partner_co, group_id, display_co, overlap
  company_areas  — company_id × area_id='tl1a'
  drugs          — one row per drug name within each program entry
  drug_areas     — drug_id × area_id='tl1a'

Idempotent — safe to run multiple times (uses upsert with merge-duplicates).

USAGE:
  python scripts/seed_tl1a_companies.py
  python scripts/seed_tl1a_companies.py --dry-run
"""

import os
import re
import sys
import argparse
import datetime
import requests

def _drug_writer(dry_run=False):
    """Single-writer accessor (ADR-010)."""
    import sys, pathlib as _pl
    _b = _pl.Path(__file__).resolve().parents[1]
    for _p in (str(_b / "src" / "database"), str(_b / "scripts")):
        if _p not in sys.path:
            sys.path.insert(0, _p)
    from drug_writer import DrugWriter
    return DrugWriter(dry_run=dry_run, source_required=False)

# ── Credentials ──────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE  = os.path.join(SCRIPT_DIR, "..")

def _read_cred(filename):
    path = os.path.join(WORKSPACE, filename)
    with open(path) as f:
        return f.read().strip()

SUPABASE_URL = _read_cred(".supabase_config").split("SUPABASE_URL=")[-1].split()[0] \
    if "SUPABASE_URL=" in _read_cred(".supabase_config") \
    else "https://tghntyofptvfhmtchwcv.supabase.co"
SUPABASE_KEY = _read_cred(".supabase_service_key")

TODAY = datetime.datetime.utcnow().strftime("%Y-%m-%d")

SB_HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "resolution=merge-duplicates,return=representation",
}

# ── TL1A Programs (mirrors TL1A_PROGRAMS in index.html) ──────────────────────
# Each entry: id, co, ticker, drug (comma-sep for multi-drug), target,
#             stageKey, overlap, groupId, partnerCo (optional), trials (optional)
TL1A_PROGRAMS = [
    # NOTE: Tulisokibart (MK-7240/PRA023) is Merck's drug, acquired via Prometheus Biosciences.
    # It is listed under groupId='merck' below. Do not add it under spyre.
    #
    # Each entry includes: modality, route, mechanismDetail where known.
    # Uncertain fields are set to None — pipeline enrichment will populate them.
    # TL1A × IL-23 bispecifics are listed first (highest relevance to Ailux asset).

    # ── Direct: TL1A × IL-23 / TL1A × other bispecifics ────────────────────
    # SPYRE THERAPEUTICS — full 7-drug rational combination platform
    # IMPORTANT: Spyre does NOT have a bispecific. Their strategy is monospecific mAbs
    # that are then combined as two-antibody combinations (+), not fused into bispecifics (×).
    # SPY002 = anti-TL1A mAb (monospecific)
    # SPY003 = anti-IL-23p19 mAb (monospecific)
    # SPY001 = anti-α4β7 mAb (monospecific)
    # SPY072 = anti-TL1A mAb for rheumatology (monospecific)
    # SPY120 = SPY001 + SPY002 (α4β7 + TL1A combination, two separate mAbs)
    # SPY130 = SPY001 + SPY003 (α4β7 + IL-23 combination, two separate mAbs)
    # SPY230 = SPY003 + SPY002 (IL-23 + TL1A combination, two separate mAbs)
    dict(id="spyre-spy002",  co="Spyre Therapeutics", ticker="SYRE",
         drug="SPY002",
         target="TL1A", stageKey="Phase 2", overlap="Direct",
         groupId="spyre", partnerCo=None,
         modality="mAb",
         # SKYLINE-UC (NCT07012395): IV induction loading doses then SC maintenance
         route="IV/SC",
         mechanismDetail="Selective anti-TL1A monoclonal antibody (monospecific). SKYLINE-UC (NCT07012395): IV induction + SC maintenance platform trial. Part A topline expected mid-2026."),

    dict(id="spyre-spy003",  co="Spyre Therapeutics", ticker="SYRE",
         drug="SPY003",
         # RULE: Always specify p19 subunit for IL-23 inhibitors — distinguishes from p40 class
         target="IL-23p19", stageKey="Phase 2", overlap="Direct",
         groupId="spyre", partnerCo=None,
         modality="mAb",
         # SKYLINE-UC (NCT07012395): IV induction + SC maintenance
         route="IV/SC",
         mechanismDetail="Selective anti-IL-23p19 monoclonal antibody (monospecific). SKYLINE-UC (NCT07012395): IV induction + SC maintenance platform trial. Part A topline expected Q3 2026."),

    dict(id="spyre-spy230",  co="Spyre Therapeutics", ticker="SYRE",
         drug="SPY230",
         # RULE: "+" = co-administered combination; "×" = bispecific. Spyre has NO bispecifics.
         # RULE: Always specify IL-23p19 (not just IL-23)
         target="IL-23p19 + TL1A", stageKey="Phase 2", overlap="Direct",
         groupId="spyre", partnerCo=None,
         modality="combination",
         # SKYLINE-UC: IV induction + SC maintenance
         route="IV/SC",
         mechanismDetail="Rational combination of SPY003 (IL-23p19) + SPY002 (TL1A) — two separate mAbs co-administered, NOT a bispecific. SKYLINE-UC (NCT07012395): IV induction + SC maintenance. Part B expected 2027."),

    dict(id="spyre-spy120",  co="Spyre Therapeutics", ticker="SYRE",
         drug="SPY120",
         target="α4β7 + TL1A", stageKey="Phase 2", overlap="Direct",
         groupId="spyre", partnerCo=None,
         modality="combination",
         # SKYLINE-UC: IV induction + SC maintenance platform trial
         route="IV/SC",
         mechanismDetail="Rational combination of SPY001 (α4β7) + SPY002 (TL1A) — two separate mAbs, NOT a bispecific. SKYLINE-UC (NCT07012395): IV induction + SC maintenance. Part B expected 2027."),

    dict(id="spyre-spy130",  co="Spyre Therapeutics", ticker="SYRE",
         drug="SPY130",
         # RULE: Always specify IL-23p19 (not just IL-23)
         target="α4β7 + IL-23p19", stageKey="Phase 2", overlap="Direct",
         groupId="spyre", partnerCo=None,
         modality="combination",
         # SKYLINE-UC: IV induction + SC maintenance platform trial
         route="IV/SC",
         mechanismDetail="Rational combination of SPY001 (α4β7) + SPY003 (IL-23p19) — two separate mAbs, NOT a bispecific. SKYLINE-UC (NCT07012395): IV induction + SC maintenance. Part B expected 2027."),

    dict(id="spyre-spy001",  co="Spyre Therapeutics", ticker="SYRE",
         drug="SPY001",
         target="α4β7", stageKey="Phase 2", overlap="Adjacent",
         groupId="spyre", partnerCo=None,
         modality="mAb",
         # SKYLINE-UC: IV induction + SC maintenance platform trial
         route="IV/SC",
         mechanismDetail="Selective anti-α4β7 integrin mAb (monospecific); gut-restricted mechanism. SKYLINE-UC (NCT07012395): IV induction + SC maintenance. Part A topline reported Q2 2026."),

    dict(id="spyre-spy072",  co="Spyre Therapeutics", ticker="SYRE",
         drug="SPY072",
         target="TL1A", stageKey="Phase 2", overlap="Adjacent",
         groupId="spyre", partnerCo=None,
         modality="mAb", route="SC",
         mechanismDetail="Selective anti-TL1A mAb for rheumatologic indications (PsA, axSpA) — adjacent to IBD programs by indication. SKYWAY-RD trial."),

    dict(id="xencor-412",   co="Xencor", ticker="XNCR",
         drug="XmAb412",
         # RULE: Bispecific targets use "×" separator. Always specify IL-23p19 (not just IL-23).
         target="TL1A × IL-23p19", stageKey="Pre-IND", overlap="Direct",
         groupId="xencor", partnerCo=None,
         modality="bispecific", route=None,
         mechanismDetail="XTEND-Fc bispecific simultaneously blocking TL1A and IL-23p19. XTEND technology (enhanced FcRn binding) engineered for ultra-long half-life analogous to XmAb942 (~74 days in Phase 1). Preclinical data at DDW 2026. FIH in healthy volunteers planned Q3 2026. Xencor runs both XmAb942 (mono, Ph2b) and XmAb412 (bispecific, FIH) in parallel — unique dual-track strategy. No pharma partner announced as of May 2026."),

    # ── Direct: TL1A monospecifics (Phase 3 leaders first) ──────────────────
    dict(id="merck",         co="Merck & Co.", ticker="MRK",
         drug="Tulisokibart (MK-7240/PRA023)",
         target="TL1A", stageKey="Phase 3", overlap="Direct",
         groupId="merck", partnerCo=None,
         modality="mAb", route="SC",
         mechanismDetail="Anti-TL1A monoclonal antibody; acquired via $10.8B Prometheus Biosciences acquisition (Apr 2023); Phase 3 leader in UC"),

    dict(id="roche",         co="Roche", ticker="ROG",
         drug="Afimkibart (RO7790121)",
         target="TL1A", stageKey="Phase 3", overlap="Direct",
         groupId="roche", partnerCo="Telavant (Roivant)",
         modality="mAb", route="SC",
         mechanismDetail="Anti-TL1A monoclonal antibody; in-licensed from Telavant (Roivant); Phase 3 in UC and CD"),

    dict(id="sanofi",        co="Sanofi", ticker="SNY",
         drug="Duvakitug (SAR447029)",
         target="TL1A", stageKey="Phase 3", overlap="Direct",
         groupId="sanofi", partnerCo="Teva",
         modality="mAb", route="SC",
         mechanismDetail="Anti-TL1A monoclonal antibody co-developed with Teva; Phase 3 in UC and CD (RELEGATE, CELESTIA programs)"),

    dict(id="abbvie",        co="AbbVie", ticker="ABBV",
         drug="FG-M701",
         target="TL1A", stageKey="Phase 2", overlap="Direct",
         groupId="abbvie", partnerCo=None,
         modality="mAb", route=None,
         mechanismDetail="Anti-TL1A monoclonal antibody; AbbVie internal TL1A program; Phase 2 in IBD"),

    dict(id="xencor-942",   co="Xencor", ticker="XNCR",
         # IMPORTANT: XmAb942 is a monospecific XTEND-Fc anti-TL1A mAb (NOT a bispecific).
         # Vudalimab = XmAb20717, a PD-1×CTLA-4 bispecific for oncology. Completely unrelated.
         drug="XmAb942",
         target="TL1A", stageKey="Phase 2", overlap="Direct",
         groupId="xencor", partnerCo=None,
         modality="mAb", route="SC",
         mechanismDetail="Monospecific XTEND-Fc anti-TL1A mAb engineered for ultra-long half-life via enhanced FcRn binding. Phase 1 HV study (reported April 2025): ~74-day half-life — longest in the TL1A class — supports Q13W+ SC dosing vs Q8W for standard IgG mAbs. XENITH-UC (NCT06619990): Ph1 HV + Ph2b UC, N=270, primary completion April 28, 2028; YE 2026 interim expected. NOTE: Vudalimab (XmAb20717) is a completely separate Xencor drug (PD-1×CTLA-4 bispecific, oncology) — not related to XmAb942."),

    dict(id="simcere",       co="Simcere", ticker="Private",
         drug="SIM0500",
         target="TL1A", stageKey="Phase 1", overlap="Direct",
         groupId="simcere", partnerCo="Boehringer Ingelheim",
         modality="mAb", route=None,
         mechanismDetail="Anti-TL1A antibody; co-developed with Boehringer Ingelheim; Phase 1 (China CDE registry — may not appear on CT.gov)"),

    dict(id="caldera",       co="Caldera", ticker="Private",
         drug="CLDR-001",
         target="TL1A", stageKey="Phase 1", overlap="Direct",
         groupId="caldera", partnerCo="Qyuns Therapeutics",
         modality="mAb", route=None,
         mechanismDetail="Anti-TL1A antibody; partnership with Qyuns Therapeutics; Phase 1"),

    dict(id="earendil",      co="Earendil / Helixon", ticker="Private",
         drug="EAR-2001",
         target="TL1A", stageKey="Phase 1", overlap="Direct",
         groupId="earendil", partnerCo="Sanofi",
         modality="mAb", route=None,
         mechanismDetail="Anti-TL1A antibody; partnered with Sanofi; Phase 1"),

    dict(id="lanova",        co="LaNova", ticker="Private",
         drug="LM-302",
         target="TL1A", stageKey="Phase 1", overlap="Direct",
         groupId="lanova", partnerCo="Zymeworks",
         modality="mAb", route=None,
         mechanismDetail="Anti-TL1A antibody; co-development with Zymeworks; Phase 1 (CDE China registry)"),

    dict(id="mirador",       co="Mirador Therapeutics", ticker="Private",
         drug="MDR-018",
         target="TL1A", stageKey="Phase 1", overlap="Direct",
         groupId="mirador", partnerCo=None,
         modality="mAb", route=None,
         mechanismDetail="Anti-TL1A antibody; Mirador lead program; Phase 1 in IBD"),

    dict(id="episcience",    co="Episcience", ticker="Private",
         drug="EPI-001",
         target="TL1A", stageKey="Preclinical", overlap="Watch",
         groupId="episcience", partnerCo=None,
         modality="mAb", route=None,
         mechanismDetail="Anti-TL1A antibody; Preclinical; watch for IND filing"),

    # ── Adjacent: IBD-space approved/late-stage competitors ─────────────────
    dict(id="abbvie-skyrizi", co="AbbVie", ticker="ABBV",
         drug="Risankizumab (Skyrizi)",
         # RULE: Use "IL-23p19" not "IL-23 (p19)" — consistent subunit notation throughout
         target="IL-23p19", stageKey="Approved", overlap="Adjacent",
         groupId="abbvie", partnerCo=None,
         modality="mAb", route="SC",
         mechanismDetail="Anti-IL-23p19 monoclonal antibody; approved for UC and CD; SC maintenance after IV induction"),

    dict(id="abbvie-rinvoq", co="AbbVie", ticker="ABBV",
         drug="Upadacitinib (Rinvoq)",
         target="JAK1", stageKey="Approved", overlap="Adjacent",
         groupId="abbvie", partnerCo=None,
         modality="small molecule", route="oral",
         mechanismDetail="Selective JAK1 inhibitor; oral small molecule; approved for moderate-to-severe UC and CD"),

    dict(id="lilly-omvoh",   co="Eli Lilly", ticker="LLY",
         drug="Mirikizumab (Omvoh)",
         # RULE: Use "IL-23p19" not "IL-23 (p19)" — consistent subunit notation throughout
         target="IL-23p19", stageKey="Approved", overlap="Adjacent",
         groupId="lilly", partnerCo=None,
         modality="mAb", route="SC",
         mechanismDetail="Anti-IL-23p19 monoclonal antibody; approved for UC; IV induction then SC maintenance"),

    dict(id="takeda-entyvio", co="Takeda", ticker="TAK",
         drug="Vedolizumab (Entyvio)",
         target="α4β7", stageKey="Approved", overlap="Adjacent",
         groupId="takeda", partnerCo=None,
         modality="mAb", route="IV/SC",
         mechanismDetail="Anti-α4β7 integrin monoclonal antibody; gut-selective mechanism; IV or SC; approved for UC and CD"),
]

# Map stageKey → company_type (rough heuristic for pipeline)
STAGE_TO_TYPE = {
    "Approved":    "large_cap",
    "Phase 3":     "mid_cap",
    "Phase 2":     "small_cap",
    "Phase 1":     "small_cap",
    "Preclinical": "small_cap",
}


# ── Supabase helpers ──────────────────────────────────────────────────────────

def sb_upsert(table, records, dry_run=False):
    if isinstance(records, dict):
        records = [records]
    if not records:
        return []
    if dry_run:
        print(f"  [DRY] {table}: {[r.get('id') or r for r in records]}")
        return records
    r = requests.post(f"{SUPABASE_URL}/rest/v1/{table}",
                      headers=SB_HEADERS, json=records, timeout=15)
    if r.status_code not in (200, 201):
        print(f"  [ERR] {table} {r.status_code}: {r.text[:300]}")
        return []
    return r.json()


def sb_get(table, params):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}",
                     headers=SB_HEADERS, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


# ── Slug helpers ──────────────────────────────────────────────────────────────

def slugify(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


# ── Main ──────────────────────────────────────────────────────────────────────

def seed(dry_run=False):
    print(f"{'[DRY RUN] ' if dry_run else ''}Seeding TL1A programs → Supabase")
    print(f"  URL: {SUPABASE_URL}")
    print()

    # Deduplicate by groupId for company-level records
    seen_groups = {}  # groupId → first entry representing the group
    for prog in TL1A_PROGRAMS:
        gid = prog["groupId"]
        if gid not in seen_groups:
            seen_groups[gid] = prog

    # 1. Upsert companies (one per groupId)
    print("── Companies ──────────────────────────────────────────")
    for gid, prog in seen_groups.items():
        co_id     = gid  # groupId IS the company_id (e.g. 'spyre', 'abbvie', 'roche')
        co_name   = prog["co"].split(" / ")[0].strip()  # first name only for display
        co_type   = STAGE_TO_TYPE.get(prog["stageKey"], "small_cap")

        record = {
            "id":           co_id,
            "name":         co_name,
            "ticker":       prog["ticker"],
            "company_type": co_type,
            "group_id":     gid,
            "display_co":   prog["co"],          # full display name (may include "/ Helixon")
            "partner_co":   prog.get("partnerCo"),
            "overlap":      prog["overlap"],
            "last_verified": TODAY,
        }
        print(f"  → {co_id}: {co_name} ({prog['stageKey']})")
        sb_upsert("companies", record, dry_run=dry_run)

    print()

    # 2. Upsert company_areas — tag to BOTH specific area (tl1a) AND indication_group (ibd).
    # Company eligibility for the TL1A tab is IBD-based: any company with an IBD drug qualifies.
    print("── company_areas ───────────────────────────────────────")
    for gid in seen_groups:
        print(f"  → {gid} × tl1a + ibd")
        sb_upsert("company_areas", {"company_id": gid, "area_id": "tl1a"}, dry_run=dry_run)
        sb_upsert("company_areas", {"company_id": gid, "area_id": "ibd"},  dry_run=dry_run)

    print()

    # 3. Upsert drugs (one row per drug name; multiple per entry if comma-sep)
    print("── drugs ───────────────────────────────────────────────")
    for prog in TL1A_PROGRAMS:
        co_id      = prog["groupId"]
        drug_names = [d.strip() for d in prog["drug"].split(",") if d.strip()]

        for raw_name in drug_names:
            # Slug: use first word/identifier (e.g. "Afimkibart" from "Afimkibart (RO7790121)")
            short_name = re.sub(r'\s*[(/].*', '', raw_name).strip()
            drug_slug  = slugify(short_name)
            if not drug_slug:
                continue

            # expected_evidence_stage: max completeness stage to expect given drug phase.
            # Preclinical = 1 (no trials expected); Phase 3 = 4; Approved = 5.
            _stage_to_expected = {
                "Preclinical": 1, "Pre-IND": 1, "IND-enabling": 1,
                "Phase 1": 2, "Phase 2": 3, "Phase 3": 4, "Approved": 5,
            }
            record = {
                "id":                     drug_slug,
                "name":                   raw_name,
                "company_id":             co_id,
                "entity_id":              co_id,
                "entity_name":            prog["co"],
                "entity_type":            "partnership" if prog.get("partnerCo") else "standalone",
                "stage":                  prog["stageKey"],
                "target":                 prog["target"],
                # RULE: Do NOT auto-prefix "Anti-" blindly. Derive mechanism from modality:
                #   bispecific  → "{target} bispecific"  (e.g. "TL1A × IL-23p19 bispecific")
                #   combination → "{target} combination" (e.g. "IL-23p19 + TL1A combination")
                #   mAb / other → "Anti-{target} mAb"   (e.g. "Anti-TL1A mAb")
                # This ensures the mechanism label is accurate regardless of target complexity.
                # "Anti-" prefix ONLY applies to monospecific mAbs, NOT to bispecifics or combos.
                "mechanism": (
                    f"{prog['target']} bispecific"   if prog.get("modality") == "bispecific"
                    else f"{prog['target']} combination" if prog.get("modality") == "combination"
                    else f"Anti-{prog['target']} mAb" if prog["target"]
                    else None
                ),
                "modality":               prog.get("modality"),
                "drug_format":            prog.get("modality"),      # keep in sync
                "route":                  prog.get("route"),
                "mechanism_detail":       prog.get("mechanismDetail"),
                "cls":                    "Next Gen" if "×" in (prog["target"] or "") else "1st Gen",
                "overlap":                prog["overlap"],
                "discovery_status":       "seeded",
                "confidence_level":       "confirmed",               # seeded from known public data
                "data_source":            "manual",
                "expected_evidence_stage": _stage_to_expected.get(prog["stageKey"], 2),
                "sort_order":             1 if prog["overlap"] == "Direct" else 5,
            }
            print(f"  → {drug_slug} ({co_id})")
            # Single writer (ADR-010): resolve canonical identity before create.
            record.pop("id", None)
            _res = _drug_writer(dry_run=dry_run).upsert(record)
            if _res.get("errors"):
                print(f"     \u26a0\ufe0f DrugWriter rejected {drug_slug}: {_res['errors']}")
            else:
                print(f"  \u2192 {_res['action']} {_res['drug_id']} ({co_id})")

            # drug_areas — tag to specific target area AND the broader indication_group area.
            # 'ibd' is the indication_group for tl1a: drugs tagged here show in the
            # expanded row for any IBD-tab company, not just TL1A-specific drugs.
            sb_upsert("drug_areas", {"drug_id": drug_slug, "area_id": "tl1a"}, dry_run=dry_run)
            sb_upsert("drug_areas", {"drug_id": drug_slug, "area_id": "ibd"}, dry_run=dry_run)

    print()
    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed TL1A programs to Supabase")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be done without writing")
    args = parser.parse_args()
    seed(dry_run=args.dry_run)
