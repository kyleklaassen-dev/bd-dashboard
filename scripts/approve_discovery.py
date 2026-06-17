#!/usr/bin/env python3
"""
approve_discovery.py — Promote an approved discovery_queue item to production.

Usage:
  # Promote a single queue item by ID
  python scripts/approve_discovery.py --id <uuid>

  # List pending items for an area
  python scripts/approve_discovery.py --list --area tl1a

  # List all critical (relevance 9-10) pending items
  python scripts/approve_discovery.py --list --critical

  # Dry-run promotion (shows what would be created, does not write)
  python scripts/approve_discovery.py --id <uuid> --dry-run

After promotion:
  - company row created (if suggested_dest = 'new_company' and company doesn't exist)
  - company_areas row created
  - drugs row created (if drug_name present)
  - drug_areas row created
  - discovery_queue updated: created_company_id, created_drug_id, status='approved'
  - You should then run enrichment on the new company:
      python src/meridian/enrichment/company_enrichment.py --area <area_id> --company <company_id>
"""

import os
import re
import sys
import json
import datetime
import argparse
import requests

def _drug_writer(dry_run=False):
    """Lazy single-writer accessor (ADR-010). Routes drug writes through
    src/meridian/database/drug_writer.DrugWriter for canonical identity + governance."""
    import sys, pathlib as _pl
    _b = _pl.Path(__file__).resolve().parents[1]
    for _p in (str(_b / "src" / "meridian" / "database"), str(_b / "scripts")):
        if _p not in sys.path:
            sys.path.insert(0, _p)
    from drug_writer import DrugWriter
    return DrugWriter(dry_run=dry_run, source_required=False)


def _company_writer(dry_run=False):
    """Single-writer accessor for companies (ADR-010)."""
    import sys, pathlib as _pl
    _b = _pl.Path(__file__).resolve().parents[1]
    for _p in (str(_b / "src" / "meridian" / "database"), str(_b / "scripts")):
        if _p not in sys.path:
            sys.path.insert(0, _p)
    from company_writer import CompanyWriter
    return CompanyWriter(dry_run=dry_run)

# Graph consistency: import ACTIVE_IN edge writer
# (write_active_in_edge must be called after every company_areas write)
_src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _src not in sys.path:
    sys.path.insert(0, _src)
try:
    from meridian.identity.company_intake import write_active_in_edge as _write_active_in_edge
except ImportError:
    # Graceful degradation: if company_intake unavailable, log and continue
    def _write_active_in_edge(company_id, area_id, dry_run=False, created_by="approve_discovery"):
        print(f"  ⚠ ACTIVE_IN edge skipped (company_intake import failed): {company_id} → {area_id}")
        return False

# ── Supabase credentials ──────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    # Try loading from local files (for local dev)
    _base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        SUPABASE_URL = open(os.path.join(_base, ".supabase_config")).read().split("SUPABASE_URL=")[1].split("\n")[0].strip()
    except Exception:
        pass
    try:
        SUPABASE_KEY = open(os.path.join(_base, ".supabase_service_key")).read().strip()
    except Exception:
        pass

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set (env or .supabase_config / .supabase_service_key)")
    sys.exit(1)

TODAY = datetime.datetime.utcnow().strftime("%Y-%m-%d")

SB_HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=representation",
}
SB_UPSERT_HEADERS = {**SB_HEADERS, "Prefer": "resolution=merge-duplicates,return=representation"}


def sb_get(table, params=None):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    r = requests.get(url, headers=SB_HEADERS, params=params or {}, timeout=15)
    r.raise_for_status()
    return r.json()


def sb_post(table, record):
    r = requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=SB_HEADERS, json=record, timeout=15)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"[sb_post {table}] {r.status_code}: {r.text[:300]}")
    data = r.json()
    return data[0] if data else record


def sb_upsert(table, record, on_conflict=None):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    if on_conflict:
        url += f"?on_conflict={on_conflict}"
    r = requests.post(url, headers=SB_UPSERT_HEADERS, json=[record], timeout=15)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"[sb_upsert {table}] {r.status_code}: {r.text[:300]}")
    return r.json()


# ── Catalog Category Inference ─────────────────────────────────────────────────
# Invariant: every drug that receives a drug_areas row must have catalog_category
# set so it appears in the Drugs to Know tab. Use this helper at all drug inserts.
_CCat_TCE_TARGETS  = {"bcma", "cd3", "cd19", "cd20", "cd38", "cd33", "cd123",
                      "her2", "egfr", "pd-1", "pd-l1", "pdl1", "ctla-4", "ctla4",
                      "tim-3", "lag-3", "cd47", "vegf"}
_CCat_IMMUNO_KWORDS = {"tl1a", "tnfrsf25", "il-4r", "il4r", "tslp", "fcrn",
                       "neonatal fc", "il-23", "il23", "il-17", "il17", "tnf",
                       "il-13", "il13", "il-33", "il33", "il-31", "il31",
                       "integrin", "α4β7", "a4b7", "rankl", "baff", "april",
                       "igg4", "ige", "il-5", "il5", "il-6", "il6"}
_CCat_ONCOLOGY_AREAS = {"tcell", "t_cell"}
_CCat_IMMUNO_AREAS   = {"tl1a", "fcrn", "il4ra", "tslp", "autoimmune",
                         "ibd", "respiratory", "ige"}
_CCat_EARLY_STAGES   = {"preclinical", "phase 1", "phase i", "pre-ind",
                         "ind-enabling", "discovery"}


def infer_catalog_category(target: str = "", modality: str = "",
                            stage: str = "", area_id: str = "") -> str:
    """Infer catalog_category from drug attributes. See company_enrichment.py for full docs."""
    import re as _re
    tgt  = (target   or "").lower()
    mod  = (modality or "").lower()
    stg  = (stage    or "").lower()
    area = (area_id  or "").lower()

    tgt_parts = {p.strip() for p in _re.split(r"[×x×/]", tgt) if p.strip()}
    if _CCat_TCE_TARGETS & tgt_parts:
        return "Oncology"
    if any(m in mod for m in ("adc", "car-t", "car t", "antibody-drug conjugate")):
        return "Oncology"
    if area in _CCat_ONCOLOGY_AREAS:
        return "Oncology"
    if "jak" in tgt or "small molecule" in mod or "oral small molecule" in mod:
        return "Small Molecule"
    is_immuno = any(kw in tgt for kw in _CCat_IMMUNO_KWORDS) or area in _CCat_IMMUNO_AREAS
    if is_immuno:
        return "Pipeline" if any(s in stg for s in _CCat_EARLY_STAGES) else "Immunology"
    return "Pipeline"


def sb_patch(table, match_col, match_val, patch):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{match_col}=eq.{match_val}"
    r = requests.patch(url, headers=SB_HEADERS, json=patch, timeout=15)
    if r.status_code not in (200, 204):
        raise RuntimeError(f"[sb_patch {table}] {r.status_code}: {r.text[:300]}")
    return r.json() if r.text else {}


def slugify(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())[:20]


def drug_slugify(s):
    return re.sub(r'[^a-z0-9]', '-', (s or '').lower()).strip('-')


# ── List pending items ────────────────────────────────────────────────────────
def cmd_list(area=None, critical=False):
    params = {"status": "eq.pending", "order": "relevance_score.desc,discovered_at.desc", "limit": "100"}
    if area:
        params["area_id"] = f"eq.{area}"
    rows = sb_get("discovery_queue", params)
    if not rows:
        print("No pending items found.")
        return

    if critical:
        rows = [r for r in rows if (r.get("relevance_score") or 0) >= 9]

    print(f"\n{'─'*100}")
    print(f"{'COMPANY':<25} {'DRUG':<20} {'AREA':<8} {'LYR':<5} {'REL':<5} {'CONF':<5} {'DEST':<18} {'WHY'}")
    print(f"{'─'*100}")
    for r in rows:
        layer = r.get("competition_layer") or "—"
        print(
            f"{r['company_name'][:24]:<25} "
            f"{(r.get('drug_name') or '')[:19]:<20} "
            f"{r['area_id']:<8} "
            f"L{layer:<4} "
            f"{r.get('relevance_score','?'):<5} "
            f"{r.get('confidence_score','?'):<5} "
            f"{(r.get('suggested_dest') or '')[:17]:<18} "
            f"{(r.get('reason') or '')[:60]}"
        )
        print(f"  ID: {r['id']}")
    print(f"{'─'*100}")
    print(f"Total: {len(rows)} item(s)")


# ── Promote a single queue item ────────────────────────────────────────────────
def cmd_promote(queue_id: str, dry_run: bool = False):
    rows = sb_get("discovery_queue", {"id": f"eq.{queue_id}"})
    if not rows:
        print(f"ERROR: No discovery_queue item found with id={queue_id}")
        sys.exit(1)
    row = rows[0]

    print(f"\n{'═'*60}")
    print(f"  Promoting: {row['company_name']}")
    if row.get('drug_name'):
        print(f"  Drug: {row['drug_name']}")
    print(f"  Area: {row['area_id']}  |  Relevance: {row.get('relevance_score')}  |  Layer: {row.get('competition_layer')}")
    print(f"  Overlap: {row.get('overlap')}  |  Destination: {row.get('suggested_dest')}")
    print(f"  Reason: {row.get('reason','')}")
    print(f"  {'[DRY RUN] ' if dry_run else ''}Processing…")
    print(f"{'─'*60}")

    co_name    = row["company_name"]
    drug_name  = row.get("drug_name")
    area_id    = row["area_id"]
    overlap    = row.get("overlap", "Watch")
    suggested  = row.get("suggested_dest", "new_company")

    created_company_id = None
    created_drug_id    = None

    # ── 1. Resolve or create company ─────────────────────────────────────────
    co_id_slug = row.get("company_id_suggested") or slugify(co_name)

    existing_co = sb_get("companies", {"id": f"eq.{co_id_slug}", "select": "id,name"})
    if not existing_co:
        # Canonical-identity fallback (ADR-010): the exact-slug check above misses
        # companies stored under a different slug (how jnj/johnsonjohnson dups arose).
        try:
            _chits = [h for h in _company_writer().reg.resolve(co_name) if h[0] == "company"]
            if len(_chits) == 1:
                existing_co = sb_get("companies", {"id": f"eq.{_chits[0][1]}", "select": "id,name"})
                if existing_co:
                    print(f"  canonical-match: '{co_name}' -> {existing_co[0]['id']} (dedup)")
        except Exception:
            pass
    if existing_co:
        co_id = existing_co[0]["id"]
        print(f"  ✓ Company exists: {co_id} ({existing_co[0]['name']})")
    else:
        co_id = co_id_slug
        acquired_by = row.get("acquired_by") or None
        co_status   = "acquired" if acquired_by else "active"

        _co_record = {
            "id":            co_id,
            "name":          co_name,
            "ticker":        "Private",
            "company_type":  "small_cap",
            "group_id":      co_id,
            "overlap":       overlap,
            "ailux_angle":   f"Promoted from discovery: {row.get('reason','')}",
            "last_verified": TODAY,
            "status":        co_status,
            "acquired_by":   acquired_by,
            "partner_co":    row.get("partner_co"),
        }
        if co_status == "acquired" and acquired_by:
            _co_record["parent_company_id"] = acquired_by
        # Single writer (ADR-010): create through CompanyWriter (governance + validation).
        _cres = _company_writer(dry_run=dry_run).upsert(_co_record)
        if _cres.get("errors"):
            print(f"  CompanyWriter rejected: {_cres['errors']}")
        else:
            co_id = _cres["company_id"]
            print(f"  {'[DRY RUN] would ' if dry_run else ''}{_cres['action']} company: {co_id} (status={co_status})")
        created_company_id = co_id

        if co_status == "acquired":
            print(f"  ⚠ Company marked ACQUIRED by {acquired_by} — skipping drug/area creation.")
            _finalize(queue_id, co_id, None, dry_run)
            return

    # ── 2. Create company_areas link ──────────────────────────────────────────
    existing_link = sb_get("company_areas", {
        "company_id": f"eq.{co_id}", "area_id": f"eq.{area_id}", "select": "company_id"
    })
    if existing_link:
        print(f"  ✓ company_areas link exists: {co_id} → {area_id}")
        # Ensure ACTIVE_IN edge exists (idempotent — harmless if already present)
        _write_active_in_edge(co_id, area_id, dry_run=dry_run, created_by="approve_discovery")
    else:
        if dry_run:
            print(f"  [DRY RUN] Would create company_areas: {co_id} → {area_id}")
        else:
            sb_upsert("company_areas", {"company_id": co_id, "area_id": area_id}, on_conflict="company_id,area_id")
            print(f"  + company_areas: {co_id} → {area_id}")
            _write_active_in_edge(co_id, area_id, dry_run=dry_run, created_by="approve_discovery")

    # Fetch indication_group for tagging (e.g. tl1a → ibd)
    area_meta = sb_get("disease_areas", {"id": f"eq.{area_id}", "select": "indication_group"})
    indication_group = (area_meta[0].get("indication_group") if area_meta else None) or area_id
    if indication_group != area_id:
        ig_link = sb_get("company_areas", {
            "company_id": f"eq.{co_id}", "area_id": f"eq.{indication_group}", "select": "company_id"
        })
        if not ig_link:
            if dry_run:
                print(f"  [DRY RUN] Would create company_areas: {co_id} → {indication_group}")
            else:
                sb_upsert("company_areas", {"company_id": co_id, "area_id": indication_group}, on_conflict="company_id,area_id")
                print(f"  + company_areas: {co_id} → {indication_group} (indication group)")
                _write_active_in_edge(co_id, indication_group, dry_run=dry_run, created_by="approve_discovery")

    # ── 3. Create drug row ────────────────────────────────────────────────────
    if drug_name:
        drug_slug = drug_slugify(drug_name)
        _stage_map = {
            "Preclinical": 1, "Pre-IND": 1, "IND-enabling": 1,
            "Phase 1": 2, "Phase 2": 3, "Phase 3": 4, "Approved": 5,
        }
        stage = row.get("stage", "Preclinical")
        target = row.get("target", "")
        _modality = row.get("modality") or ""
        _cat_cat = infer_catalog_category(target=target, modality=_modality, stage=stage, area_id=area_id)
        # Single Writer Pattern (ADR-010): DrugWriter resolves CANONICAL identity
        # via entity_matcher BEFORE creating a row, preventing slug-mismatch
        # duplicates this step used to create (e.g. sl-325 vs sl325). No explicit
        # id is passed so an existing drug (by name/alias) is reused, not duplicated.
        _drug_record = {
            "name": drug_name, "company_id": co_id, "entity_id": co_id,
            "entity_name": co_name, "entity_type": "standalone", "stage": stage,
            "target": target, "mechanism": f"Anti-{target}" if target else None,
            "modality": _modality or None, "drug_format": _modality or None,
            "route": row.get("route"),
            "cls": "Next Gen" if "\u00d7" in (target or "") else "1st Gen",
            "overlap": "Direct", "catalog_category": _cat_cat,
            "discovery_status": "promoted", "confidence_score": row.get("confidence_score"),
            "confidence_level": "inferred", "data_source": "discovery_queue",
            "expected_evidence_stage": _stage_map.get(stage, 2), "sort_order": 99,
        }
        _src = row.get("source_url") or row.get("source_note")
        _res = _drug_writer(dry_run=dry_run).upsert(
            _drug_record,
            source=({"url": _src, "type": "discovery_queue", "added_by": "approve_discovery",
                     "claim_type": "drug_promotion",
                     "claim_value": f"{drug_name} promoted from discovery_queue"} if _src else None),
        )
        if _res.get("errors"):
            print(f"  \u26a0\ufe0f drug write rejected by DrugWriter: {_res['errors']}")
            created_drug_id = _res.get("drug_id")
        else:
            created_drug_id = _res["drug_id"]
            print(f"  {'[DRY RUN] would ' if dry_run else ''}{_res['action']} drug: {created_drug_id}")

            # Drug areas + Guard E2: always write stub drug_area_scores immediately after drug_areas
            # Invariant: every drug_areas row must have a matching drug_area_scores row.
            # Stub uses confidence_level='inferred' — enrichment will overwrite with full classification.
            if not dry_run:
                for _aid in ([area_id] + ([indication_group] if indication_group != area_id else [])):
                    sb_upsert("drug_areas", {"drug_id": drug_slug, "area_id": _aid}, on_conflict="drug_id,area_id")
                    # [E2 guard] Ensure stub drug_area_scores exists for this pair
                    _das_existing = sb_get("drug_area_scores", {
                        "drug_id": f"eq.{drug_slug}", "area_id": f"eq.{_aid}", "select": "drug_id", "limit": "1"
                    })
                    if not _das_existing:
                        _inferred_overlap = "Direct" if row.get("overlap") in ("Direct",) else row.get("overlap") or "Watch"
                        sb_upsert("drug_area_scores", {
                            "drug_id":          drug_slug,
                            "area_id":          _aid,
                            "overlap":          _inferred_overlap,
                            "confidence_level": "inferred",
                            "overlap_rationale": (
                                f"Stub created at drug intake (approve_discovery.py). "
                                f"Run company_enrichment.py to classify with full context."
                            ),
                        })
                        print(f"  + drug_area_scores [E2 stub]: {drug_slug} → {_aid} (overlap={_inferred_overlap!r}, inferred)")
                print(f"  + drug_areas: {drug_slug} → {area_id}{', '+indication_group if indication_group!=area_id else ''}")

    # ── 4. Finalize queue row ─────────────────────────────────────────────────
    _finalize(queue_id, created_company_id, created_drug_id, dry_run)

    print(f"\n  ✓ Promotion complete!")
    print(f"\n  ► Next step: run enrichment to populate intelligence:")
    print(f"      python src/meridian/enrichment/company_enrichment.py --area {area_id} --company {co_id}")
    print()


def _finalize(queue_id, co_id, drug_id, dry_run):
    patch = {
        "status":             "approved",
        "reviewed_at":        datetime.datetime.utcnow().isoformat(),
        "reviewed_by":        "approve_discovery.py",
        "created_company_id": co_id,
        "created_drug_id":    drug_id,
    }
    if dry_run:
        print(f"  [DRY RUN] Would update discovery_queue id={queue_id}: {patch}")
    else:
        sb_patch("discovery_queue", "id", queue_id, patch)
        print(f"  ✓ discovery_queue updated: status=approved, created_company_id={co_id}")


# ── Reject a queue item + auto-create not_hallucinated validation test ─────────
def cmd_reject(queue_id: str, reason: str = "", dry_run: bool = False):
    """
    Reject a discovery_queue item and optionally auto-create a not_hallucinated
    validation test for the rejected drug.

    When a human reviewer marks a drug as hallucinated or wrong, that rejection
    is the clearest possible signal that the LLM invented something. Recording it
    as a validation test means the same hallucination will be caught automatically
    on future enrichment runs without human review.

    Creates:
      - discovery_queue.status = 'rejected'
      - validation_tests row (test_type='not_hallucinated') for the drug name + company
        if the item has a drug_name set
    """
    rows = sb_get("discovery_queue", {"id": f"eq.{queue_id}"})
    if not rows:
        print(f"ERROR: No discovery_queue item found with id={queue_id}")
        sys.exit(1)
    row = rows[0]

    drug_name  = row.get("drug_name") or ""
    co_name    = row.get("company_name") or ""
    area_id    = row.get("area_id") or ""
    why        = row.get("reason") or ""
    reject_msg = reason or f"Manually rejected during review — hallucinated or incorrect discovery"

    print(f"\n{'═'*60}")
    print(f"  Rejecting: {co_name}" + (f" / {drug_name}" if drug_name else ""))
    print(f"  Area: {area_id}  |  Reason: {reject_msg}")
    print(f"  {'[DRY RUN] ' if dry_run else ''}Processing…")
    print(f"{'─'*60}")

    # ── 1. Update discovery_queue status to 'rejected' ───────────────────────
    if dry_run:
        print(f"  [DRY RUN] Would mark discovery_queue id={queue_id} as rejected")
    else:
        sb_patch("discovery_queue", "id", queue_id, {
            "status":       "rejected",
            "reviewed_at":  datetime.datetime.utcnow().isoformat(),
            "reviewed_by":  "approve_discovery.py",
            "notes":        reject_msg,
        })
        print(f"  ✓ discovery_queue id={queue_id} marked as rejected")

    # ── 2. Auto-create not_hallucinated validation test for the drug ─────────
    if drug_name:
        test_name = f"not_hallucinated — {drug_name} ({co_name}, {area_id})"
        # Use drug slug as entity_id — if a drug with this name already exists,
        # the test will verify it is real. If not, it guards against LLM re-discovery.
        entity_id = re.sub(r'[^a-z0-9]', '-', drug_name.lower()).strip('-')[:40]

        test_record = {
            "test_name":         test_name,
            "test_type":         "not_hallucinated",
            "entity_type":       "drug",
            "entity_id":         entity_id,
            "field_name":        "name",
            "expected_value":    drug_name,
            "expected_operator": "neq",  # drug should NOT exist with this name (it was rejected)
            "priority":          "P2",
            "area_id":           area_id,
            "notes":             (
                f"Auto-created by cmd_reject() on {TODAY}. "
                f"Drug '{drug_name}' was rejected from discovery_queue for {co_name} ({area_id}). "
                f"Rejection reason: {reject_msg}. "
                f"Original discovery reason: {why}"
            ),
        }

        if dry_run:
            print(f"  [DRY RUN] Would create validation test: {test_name}")
        else:
            try:
                created = sb_post("validation_tests", test_record)
                print(f"  + validation_test created: id={created.get('id')} '{test_name}'")
            except Exception as e:
                print(f"  ⚠ validation_test creation failed (non-fatal): {e}")
    else:
        print(f"  (No drug_name on queue item — skipping validation test creation)")

    print(f"{'═'*60}")
    print(f"  Rejection complete{'  [DRY RUN — no writes made]' if dry_run else ''}.")


# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Promote discovery_queue items to production (companies/drugs/company_areas)"
    )
    parser.add_argument("--id",       help="UUID of the discovery_queue item to promote or reject")
    parser.add_argument("--list",     action="store_true", help="List pending items")
    parser.add_argument("--area",     help="Filter by area_id")
    parser.add_argument("--critical", action="store_true", help="Show only relevance 9-10 items")
    parser.add_argument("--dry-run",  action="store_true", help="Preview — do not write to DB")
    parser.add_argument("--reject",   action="store_true", help="Reject this item (creates not_hallucinated validation test)")
    parser.add_argument("--reason",   default="", help="Rejection reason (used in validation test notes)")
    args = parser.parse_args()

    if args.list:
        cmd_list(area=args.area, critical=args.critical)
    elif args.id and args.reject:
        cmd_reject(args.id, reason=args.reason, dry_run=args.dry_run)
    elif args.id:
        cmd_promote(args.id, dry_run=args.dry_run)
    else:
        parser.print_help()
        print("\nExamples:")
        print("  python scripts/approve_discovery.py --list --area tl1a")
        print("  python scripts/approve_discovery.py --list --critical")
        print("  python scripts/approve_discovery.py --id <uuid> --dry-run")
        print("  python scripts/approve_discovery.py --id <uuid>")
        print("  python scripts/approve_discovery.py --id <uuid> --reject")
        print("  python scripts/approve_discovery.py --id <uuid> --reject --reason 'Drug does not exist'")
        print("  python scripts/approve_discovery.py --id <uuid> --reject --dry-run")


if __name__ == "__main__":
    main()
