#!/usr/bin/env python3
"""
BD Platform — Patient Layer Edge Seeder
=======================================
Relationship-completeness sprint (2026-06-06, cowork). Final piece of the
North Star chain: Patient -> Indication -> Target -> Company.

The rich patient layer (indication_patient_intelligence, 28 rows) lived OUTSIDE
the entity graph. This connects it: one PATIENT node per indication/area that has
patient intelligence, joined to the existing indication/area node by
  patient --AFFECTED_BY--> indication      (disease rows)
  patient --AFFECTED_BY--> area            (area-aggregate rows; only existing areas)

Requires migration v82 (patient node type + AFFECTED_BY predicate).

DETERMINISTIC + NO FABRICATION
------------------------------
- Rows are mapped to canonical ids via an EXPLICIT mapping dict (below). A row
  that does not map is SKIPPED and reported — never guessed.
- The AFFECTED_BY edge is a STRUCTURAL/definitional link (this patient population
  is affected by this disease); confidence='confirmed'. The unmet-need MAGNITUDE
  (score/severity) is carried in the rationale, attributed to the source table;
  a real source_url from source_urls is attached when present.
- patient node id reuses the indication/area id (type disambiguates), matching the
  graph's "reuse the entity's own id" convention.

USAGE
-----
  python3 scripts/seed_patient_edges.py --dry-run
  python3 scripts/seed_patient_edges.py --apply
"""
import os, sys, argparse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'narrative'))
import narrative_gen as ng

CREATED_BY = "seed_patient_edges"

# Explicit, deterministic mapping. (patient_intelligence.indication_name -> (object_type, object_id))
DISEASE = {
    "Multiple Myeloma": "multiple_myeloma",
    "Severe Asthma": "asthma",
    "Hidradenitis Suppurativa": "hs",
    "Eosinophilic Esophagitis (EoE)": "eoe",
    "Generalized Myasthenia Gravis": "gmg",
    "Thyroid Eye Disease": "ted",
    "Crohn's Disease": "cd",
    "Psoriatic Arthritis": "psa",
    "Lupus Nephritis": "lupus_nephritis",
    "COPD (Type-2 / eosinophilic)": "copd",
    "Ulcerative Colitis": "uc",
    "Chronic Spontaneous Urticaria": "chronic_urticaria",
    "Chronic Rhinosinusitis with Nasal Polyps": "crswnp",
    "Atopic Dermatitis": "ad",
    "Sjögren's Disease": "sjogrens",
    "CIDP": "cidp",
    "Gastric/GEJ Adenocarcinoma - FGFR2b+": "gastric_cancer",
    "Plaque Psoriasis": "psoriasis",
    "Systemic Lupus Erythematosus (SLE)": "sle",
}
# area-aggregate rows -> area ids (only areas that exist as graph nodes)
AREA = {
    "TSLP Target Area": "tslp",
    "FcRn Target Area": "fcrn",
    "IGF-1R Target Area": "igf1r",
    "IL-4Rα Target Area": "il4ra",
    "TL1A Target Area": "tl1a",
    "IBD (Inflammatory Bowel Disease)": "ibd",
    "Respiratory Diseases (Broad)": "respiratory",
    "Autoimmune Diseases (Broad)": "autoimmune",
}
# Rows intentionally NOT mapped (no existing node / not a single indication):
#   "IL-23 / IL-23p19 Target Area" (no il23p19 area node), "TSLP Target Area" handled,
#   reported as skipped at runtime.

VALID_AREAS = {"atopy", "autoimmune", "fcrn", "ibd", "igf1r", "il4ra",
               "respiratory", "tcell", "ted", "tl1a", "tslp"}


def fetch_all(endpoint_base, page=1000):
    out, off = [], 0
    while True:
        sep = "&" if "?" in endpoint_base else "?"
        b = ng.get(f"{endpoint_base}{sep}limit={page}&offset={off}")
        if not b:
            break
        out += b
        if len(b) < page:
            break
        off += page
    return out


def edge_key(e):
    return (e["subject_type"], e["subject_id"], e["predicate"],
            e["object_type"], e["object_id"], e.get("scope_area_id"))


def first_url(su):
    if isinstance(su, list):
        for u in su:
            if isinstance(u, str) and u.strip().lower().startswith("http"):
                return u.strip()
    elif isinstance(su, str) and su.strip().lower().startswith("http"):
        return su.strip()
    return None


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    rows = fetch_all("indication_patient_intelligence?select=indication_name,unmet_need_score,"
                     "unmet_need_severity,unmet_need_narrative,source_urls,patient_count_us,patient_count_global")
    ind_ids = {i["id"] for i in fetch_all("indications?select=id")}
    existing = {edge_key(e) for e in
                fetch_all("entity_edges?select=subject_type,subject_id,predicate,object_type,object_id,scope_area_id")}

    new_rows, skipped = [], []
    for r in rows:
        name = r.get("indication_name")
        if name in DISEASE:
            otype, oid = "indication", DISEASE[name]
            if oid not in ind_ids:
                skipped.append((name, f"indication id '{oid}' not in indications table"))
                continue
        elif name in AREA:
            otype, oid = "area", AREA[name]
            if oid not in VALID_AREAS:
                skipped.append((name, f"area id '{oid}' not a valid area node"))
                continue
        else:
            skipped.append((name, "no explicit mapping (target-aggregate / not a single indication)"))
            continue

        url = first_url(r.get("source_urls"))
        score, sev = r.get("unmet_need_score"), r.get("unmet_need_severity")
        pus, pgl = r.get("patient_count_us"), r.get("patient_count_global")
        rat = (f"Patient population affected by '{name}' "
               f"(indication_patient_intelligence). Unmet-need score "
               f"{score}/10, severity {sev}."
               + (f" US patients ~{pus}." if pus else "")
               + (f" Global ~{pgl}." if pgl else ""))
        row = {
            "subject_type": "patient", "subject_id": oid, "predicate": "AFFECTED_BY",
            "object_type": otype, "object_id": oid, "scope_area_id": None,
            "confidence_level": "confirmed", "source_url": url,
            "generation_method": "deterministic", "rationale": rat[:1000],
            "status": "active", "created_by": CREATED_BY,
        }
        if edge_key(row) not in existing:
            existing.add(edge_key(row))
            new_rows.append(row)

    n_ind = sum(1 for r in new_rows if r["object_type"] == "indication")
    n_area = sum(1 for r in new_rows if r["object_type"] == "area")
    print(f"patient AFFECTED_BY indication ... +{n_ind}")
    print(f"patient AFFECTED_BY area ......... +{n_area}")
    print(f"TOTAL new edges: {len(new_rows)}")
    print(f"Skipped {len(skipped)} rows (not mapped — reported, never guessed):")
    for name, why in skipped:
        print(f"   - {name}: {why}")

    if args.apply and new_rows:
        applied, failed = 0, 0
        for i in range(0, len(new_rows), 200):
            batch = new_rows[i:i+200]
            res = ng._request("POST", "entity_edges", batch, {"Prefer": "return=minimal"})
            if res is None:
                failed += len(batch)
            else:
                applied += len(batch)
        print(f"\nAPPLIED {applied} edges; FAILED {failed}." if failed
              else f"\nAPPLIED {applied} edges to entity_edges.")
    else:
        print("\n[dry-run] no writes.")


if __name__ == "__main__":
    main()
