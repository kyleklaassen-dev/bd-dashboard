#!/usr/bin/env python3
"""Shared base for the narrative_gen split (§3): config/creds, the urllib REST helpers
(_request/get), recipe fetch + hash, and the shared RECIPE_DRUG_FIELDS / IND_NAME / NCT_RE."""

import os
import re
import json
import hashlib
import urllib.request
import urllib.error
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Config / credentials (house pattern)
# ---------------------------------------------------------------------------
SUPA_URL = "https://tghntyofptvfhmtchwcv.supabase.co/rest/v1"
# repo root: this file is one dir deeper (src/meridian/products/narrative/) than the
# pre-§3-split home (src/meridian/products/), so 5 dirnames up, not 4.
WORKSPACE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))


def _read_key(filename, env=None):
    # env var first (CI / GitHub Actions secrets), then the local workspace file,
    # then '' (never raises) so the module imports test-clean without secrets.
    if env and os.environ.get(env, "").strip():
        return os.environ[env].strip()
    try:
        with open(os.path.join(WORKSPACE, filename)) as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


SUPA_KEY = _read_key(".supabase_service_key", "SUPABASE_SERVICE_KEY")

# Drugs columns the overview recipe is allowed to look at (candidate structured atoms).
# Each is admitted to the ASSERTED set only if a confirmed source corroborates it.
RECIPE_DRUG_FIELDS = [
    "name", "company_display", "company_id", "mechanism", "modality",
    "stage", "phase_display", "route", "drug_format", "indication_short",
    "target", "half_life_note", "dosing_schedule",
]

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
def _request(method, endpoint, data=None, extra_headers=None):
    url = f"{SUPA_URL}/{endpoint}"
    body = json.dumps(data).encode() if data is not None else None
    hdrs = {"apikey": SUPA_KEY, "Authorization": f"Bearer {SUPA_KEY}",
            "Content-Type": "application/json"}
    if extra_headers:
        hdrs.update(extra_headers)
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw) if raw.strip() else []
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} {method} /{endpoint.split('?')[0]}: {e.read().decode()[:200]}",
              file=sys.stderr)
        return None


def get(endpoint):
    return _request("GET", endpoint) or []


# ---------------------------------------------------------------------------
# 1. RECIPE — fetch the row set that feeds a drug/overview narrative
# ---------------------------------------------------------------------------
# indication_id (ontology) -> indication_name (patient-intel table key)
IND_NAME = {
    "uc": "Ulcerative Colitis", "cd": "Crohn's Disease", "ra": "Rheumatoid Arthritis",
    "ax-spa": "Axial Spondyloarthritis", "hs": "Hidradenitis Suppurativa",
    "ssc-ild": "Systemic Sclerosis", "ibd": "Inflammatory Bowel Disease",
    "psoriasis": "Psoriasis", "ad": "Atopic Dermatitis", "asthma": "Asthma",
}


def fetch_recipe(drug_id):
    from urllib.parse import quote
    drug = get(f"drugs?id=eq.{drug_id}")
    if not drug:
        raise SystemExit(f"drug '{drug_id}' not found")
    targets = get(f"drug_targets?drug_id=eq.{drug_id}")
    indications = get(f"drug_indications?drug_id=eq.{drug_id}")

    # Patient-population depth — epidemiology + unmet need for the lead indications
    # (fall back to all indications when none are flagged lead).
    _lead = {i.get("indication_id") for i in indications if i.get("is_lead_indication")}
    _inds = _lead or {i.get("indication_id") for i in indications}
    patients = []
    for iid in _inds:
        nm = IND_NAME.get(iid)
        if nm:
            patients += get("indication_patient_intelligence?indication_name=eq."
                            + quote(nm) + "&select=indication_name,patient_count_us,"
                            "patient_count_global,biologic_failure_rate_pct,unmet_need_score,"
                            "unmet_need_narrative,treatment_cascade,patient_reported_priorities,"
                            "source_urls")

    # Competitor depth — other agents hitting the same primary target.
    competitors = []
    prim = next((t["target_id"] for t in targets), None)
    if prim:
        cids = [r["drug_id"] for r in
                get(f"drug_targets?target_id=eq.{prim}&select=drug_id")
                if r.get("drug_id") and r["drug_id"] != drug_id]
        if cids:
            ids = ",".join(sorted(set(cids)))
            competitors = get(f"drugs?id=in.({ids})&dashboard_visible=eq.true"
                              "&select=id,display_name,stage,company_display,source_url")

    # Study-identity resolver inputs: canonical aliases + the trial→publication
    # crosswalk (v73), so a registry claim can triangulate against its paper and
    # any row naming a study by acronym/sponsor-id/DOI resolves to its NCT.
    tids = get(f"trial_identity?drug_id=eq.{drug_id}")
    _ncts = [t["nct_id"] for t in tids if t.get("nct_id")]
    tpubs = get(f"trial_publications?nct_id=in.({','.join(_ncts)})") if _ncts else []

    return {
        "drug": drug[0],
        "sources": get(f"drug_sources?drug_id=eq.{drug_id}"),
        "trial_identity": tids,
        "trial_publications": tpubs,
        "targets": targets,
        "indications": indications,
        # Clinical-evidence depth — each row carries its own CT.gov provenance.
        "trials": get(f"trials?drug_id=eq.{drug_id}"),
        "benchmarks": get(f"drug_clinical_benchmarks?drug_id=eq.{drug_id}"),
        "pk": get(f"drug_pk_parameters?drug_id=eq.{drug_id}"),
        "patients": patients,
        "competitors": competitors,
        "primary_target": prim,
        # Strategic depth — ownership, molecule, escape biology, the clock.
        "deals": get(f"deals?drug_id=eq.{drug_id}"),
        "molecule": get(f"molecule_intelligence?drug_id=eq.{drug_id}"),
        "non_responder": get(f"non_responder_profiles?drug_id=eq.{drug_id}"),
        "catalysts": get(f"catalysts?drug_id=eq.{drug_id}&catalyst_status=neq.resolved"
                         "&order=sort_date.asc&limit=8"),
    }


def recipe_hash(recipe):
    """Stable hash of the underlying rows — drives staleness / drift detection."""
    blob = json.dumps(recipe, sort_keys=True, default=str).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


# ---------------------------------------------------------------------------
# 2. ATOM EXTRACTION (deterministic — no model involved)
# ---------------------------------------------------------------------------
# An atom: {claim, backing, kind, confidence, source_url, source_table, source_row_id}
#   kind ∈ external_confirmed | ontology | structured_unverified | conflict | scrubbed

NCT_RE = re.compile(r"NCT\d{8}", re.I)
