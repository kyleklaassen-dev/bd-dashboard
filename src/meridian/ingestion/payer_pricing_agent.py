#!/usr/bin/env python3
"""payer_pricing_agent.py — PAYER domain data layer (US public pricing & spend).

Pulls free CMS / Medicaid datasets and writes matched rows for the APPROVED
drugs in our catalog into `payer_pricing`, plus governance `drug_sources`
rows and the `data_dictionary` entry.

Sources (all free, no key):
  * cms_partd  — Medicare Part D Spending by Drug   (annual, 2019-2023)
  * cms_partb  — Medicare Part B Spending by Drug   (annual, 2019-2023)
  * nadac      — Medicaid NADAC per-unit acquisition cost (2025)

Matching is CONSERVATIVE: exact brand/generic (case-insensitive), brand-family
prefix, or biosimilar-suffix-stripped generic. Ambiguous -> SKIP + report.

Idempotent: payer_pricing upserts on (drug_id, source, metric, year);
drug_sources / data_dictionary are existence-checked before insert.

Env-free: reads creds from workspace files.
Usage: python3 scripts/payer_pricing_agent.py [--dry-run] [--limit N]
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SB_URL = "https://tghntyofptvfhmtchwcv.supabase.co/rest/v1"
SESSION_LABEL = "2026-06-07-payer"

PARTD_UUID = "7e0b4365-fd63-4a29-8f5e-e0ac9f66a81b"
PARTB_UUID = "76a714ad-3a2c-43ac-b76d-9dadf8f7d890"
NADAC_DS = "f38d0706-1239-442c-a3cc-40ef1b686ac0"  # NADAC 2025
NADAC_YEAR = 2025

PARTD_URL = f"https://data.cms.gov/data-api/v1/dataset/{PARTD_UUID}/data"
PARTB_URL = f"https://data.cms.gov/data-api/v1/dataset/{PARTB_UUID}/data"
NADAC_URL = f"https://data.medicaid.gov/api/1/datastore/query/{NADAC_DS}/0"

CMS_YEARS = [2019, 2020, 2021, 2022, 2023]


def _read(name):
    with open(os.path.join(ROOT, name)) as f:
        return f.read().strip()


SVC = _read(".supabase_service_key")
HEADERS = {"apikey": SVC, "Authorization": f"Bearer {SVC}",
           "Content-Type": "application/json"}
UA = "meridian-payer-agent/1.0"


# --------------------------------------------------------------------------- #
# HTTP helpers (backoff + chunk-friendly)
# --------------------------------------------------------------------------- #
def http_get(url, tries=4, timeout=25):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                       "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except Exception as e:  # noqa
            last = e
            time.sleep(1.5 * (i + 1))
    print(f"  ! GET failed ({last}) -> {url[:90]}", file=sys.stderr)
    return None


def sb_get(path):
    req = urllib.request.Request(f"{SB_URL}/{path}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_write(path, rows, prefer):
    if not rows:
        return 0
    data = json.dumps(rows).encode()
    h = dict(HEADERS)
    h["Prefer"] = prefer
    req = urllib.request.Request(f"{SB_URL}/{path}", data=data, headers=h, method="POST")
    for i in range(4):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                r.read()
                return len(rows)
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:300]
            print(f"  ! write {path} HTTP {e.code}: {body}", file=sys.stderr)
            if e.code in (502, 503, 504, 429):
                time.sleep(2 * (i + 1)); continue
            return 0
        except Exception as e:  # noqa
            print(f"  ! write {path} err {e}", file=sys.stderr)
            time.sleep(2 * (i + 1))
    return 0


# --------------------------------------------------------------------------- #
# Matching helpers
# --------------------------------------------------------------------------- #
def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def strip_bio_suffix(generic):
    # "risankizumab-rzaa" -> "risankizumab"; keep combo names intact
    return re.sub(r"-[a-z]{4}$", "", generic)


GREEK = {"alfa", "alpha", "beta", "gamma", "delta"}


def _brand_parts(brand):
    # brand_name may pack multiple brands: "Vyvgart / Vyvgart Hytrulo"
    return [norm(p) for p in re.split(r"[/;,]", brand or "") if norm(p)]


def brand_match(row_brand, brand):
    if not brand:
        return False
    rb = norm(row_brand)
    for b in _brand_parts(brand):
        if rb == b or rb.startswith(b + " "):
            return True
    return False


def generic_match(row_generic, generic):
    if not generic:
        return False
    rg, g = norm(row_generic), norm(generic)
    if "/" in rg:                      # true combination product -> not a match
        return False
    rg_base = strip_bio_suffix(rg)     # drop biosimilar "-xxxx"
    if rg == g or rg_base == g:
        return True
    # drop trailing INN glycoform tokens (alfa/beta/...) +/- suffix:
    # "efgartigimod alfa-fcab" -> "efgartigimod alfa" -> "efgartigimod"
    toks = rg_base.split()
    while toks and toks[-1] in GREEK:
        toks.pop()
    return " ".join(toks) == g


def num(v):
    try:
        if v in (None, "", "NA"):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# CMS spending (Part D / Part B) — keyword search + conservative match
# --------------------------------------------------------------------------- #
def fetch_cms_rows(base_url, term):
    url = f"{base_url}?keyword={urllib.parse.quote(term)}&size=500"
    return http_get(url) or []


def collect_cms(base_url, drug):
    """Return list of matched data rows for a drug from one CMS dataset."""
    seen = {}
    terms = [t for t in (drug["brand_name"], drug["name"]) if t]
    for term in terms:
        for row in fetch_cms_rows(base_url, term):
            key = (row.get("Brnd_Name"), row.get("Gnrc_Name"),
                   row.get("HCPCS_Cd"), row.get("Mftr_Name"))
            if key in seen:
                continue
            if brand_match(row.get("Brnd_Name"), drug["brand_name"]) or \
               generic_match(row.get("Gnrc_Name"), drug["name"]):
                seen[key] = row
        time.sleep(0.3)
    return list(seen.values())


def partd_metrics(rows):
    """Part D: aggregate Mftr_Name=='Overall' rows. -> {(metric,year):value}."""
    overall = [r for r in rows if norm(r.get("Mftr_Name")) == "overall"]
    if not overall:
        return {}, []
    out, brands = {}, sorted({r.get("Brnd_Name") for r in overall})
    for y in CMS_YEARS:
        spnd = [num(r.get(f"Tot_Spndng_{y}")) for r in overall]
        clms = [num(r.get(f"Tot_Clms_{y}")) for r in overall]
        s = sum(x for x in spnd if x is not None)
        c = sum(x for x in clms if x is not None)
        if any(x is not None for x in spnd) and s > 0:
            out[("total_spending", y)] = round(s, 2)
            if c > 0:
                out[("avg_spend_per_claim", y)] = round(s / c, 2)
    return out, brands


def partb_metrics(rows):
    """Part B: aggregate matched HCPCS rows. -> {(metric,year):value}."""
    if not rows:
        return {}, []
    out, brands = {}, sorted({r.get("Brnd_Name") for r in rows})
    for y in CMS_YEARS:
        spnd = [num(r.get(f"Tot_Spndng_{y}")) for r in rows]
        clms = [num(r.get(f"Tot_Clms_{y}")) for r in rows]
        s = sum(x for x in spnd if x is not None)
        c = sum(x for x in clms if x is not None)
        if any(x is not None for x in spnd) and s > 0:
            out[("total_spending", y)] = round(s, 2)
            if c > 0:
                out[("avg_spend_per_claim", y)] = round(s / c, 2)
    return out, brands


# --------------------------------------------------------------------------- #
# NADAC per-unit
# --------------------------------------------------------------------------- #
def nadac_lookup(term):
    cond = [{"property": "ndc_description", "value": term.upper() + "%", "operator": "like"}]
    q = urllib.parse.urlencode({
        "limit": 200,
        "conditions[0][property]": "ndc_description",
        "conditions[0][value]": term.upper() + "%",
        "conditions[0][operator]": "like",
    })
    return http_get(f"{NADAC_URL}?{q}", timeout=25) or {}


def collect_nadac(drug):
    """Most-recent per-unit NADAC for a conservative brand/generic match."""
    candidates = []
    for term, kind in ((drug["brand_name"], "brand"), (drug["name"], "generic")):
        if not term:
            continue
        res = nadac_lookup(term)
        for r in (res.get("results") or []):
            desc = r.get("ndc_description", "")
            d0 = norm(desc).split()[0] if desc else ""
            ok = (kind == "brand" and norm(desc).startswith(norm(term))) or \
                 (kind == "generic" and d0 == norm(term))
            if not ok:
                continue
            v = num(r.get("nadac_per_unit"))
            if v is None:
                continue
            candidates.append((r.get("effective_date") or "", v,
                               r.get("pricing_unit"), desc))
        if candidates:  # prefer brand match; stop if brand produced hits
            break
        time.sleep(0.3)
    if not candidates:
        return None
    candidates.sort(reverse=True)  # latest effective_date first
    eff, v, unit, desc = candidates[0]
    return {"value": v, "unit": (unit or "unit"), "desc": desc, "eff": eff}


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    dry = "--dry-run" in sys.argv
    limit = None
    offset = 0
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    if "--offset" in sys.argv:
        offset = int(sys.argv[sys.argv.index("--offset") + 1])

    drugs = sb_get("drugs?select=id,name,inn_name,brand_name,stage"
                   "&or=(stage.ilike.approved*,brand_name.not.is.null)&order=id")
    # generic name: prefer inn_name, else the canonical `name` field
    for d in drugs:
        d["name"] = (d.get("inn_name") or d.get("name") or "").strip() or None
    drugs = drugs[offset:]
    if limit:
        drugs = drugs[:limit]
    print(f"slice offset={offset} limit={limit}")
    print(f"Loaded {len(drugs)} candidate drugs")

    # existing drug_sources for idempotency
    existing_src = set()
    for r in sb_get("drug_sources?select=drug_id,source_url&claim_type=eq.payer_pricing"
                    "&added_by=eq.payer_agent"):
        existing_src.add((r.get("drug_id"), r.get("source_url")))

    pp_rows, src_rows = [], []
    counts = {"cms_partd": 0, "cms_partb": 0, "nadac": 0}
    matched_drugs = {"cms_partd": [], "cms_partb": [], "nadac": []}
    skipped = []

    for i, d in enumerate(drugs, 1):
        did, dname, brand = d["id"], d["name"], d.get("brand_name")
        print(f"[{i}/{len(drugs)}] {did}  brand={brand}  generic={dname}")
        hit_any = False

        # ---- Part D ----
        try:
            rows = collect_cms(PARTD_URL, d)
            m, brands = partd_metrics(rows)
            if m:
                hit_any = True
                matched_drugs["cms_partd"].append(f"{did} ({','.join(b for b in brands if b)})")
                for (metric, yr), val in m.items():
                    pp_rows.append({
                        "drug_id": did, "drug_name": dname, "brand_name": brand,
                        "source": "cms_partd", "metric": metric,
                        "value_numeric": val,
                        "unit": "USD" if metric == "total_spending" else "USD_per_claim",
                        "year": yr, "source_url": PARTD_URL})
                    counts["cms_partd"] += 1
        except Exception as e:  # noqa
            print(f"   partd err {e}", file=sys.stderr)

        # ---- Part B ----
        try:
            rows = collect_cms(PARTB_URL, d)
            m, brands = partb_metrics(rows)
            if m:
                hit_any = True
                matched_drugs["cms_partb"].append(f"{did} ({','.join(b for b in brands if b)})")
                for (metric, yr), val in m.items():
                    pp_rows.append({
                        "drug_id": did, "drug_name": dname, "brand_name": brand,
                        "source": "cms_partb", "metric": metric,
                        "value_numeric": val,
                        "unit": "USD" if metric == "total_spending" else "USD_per_claim",
                        "year": yr, "source_url": PARTB_URL})
                    counts["cms_partb"] += 1
        except Exception as e:  # noqa
            print(f"   partb err {e}", file=sys.stderr)

        # ---- NADAC ----
        try:
            n = collect_nadac(d)
            if n:
                hit_any = True
                matched_drugs["nadac"].append(f"{did} ({n['desc']})")
                pp_rows.append({
                    "drug_id": did, "drug_name": dname, "brand_name": brand,
                    "source": "nadac", "metric": "nadac_per_unit",
                    "value_numeric": n["value"], "unit": f"USD_per_{n['unit']}",
                    "year": NADAC_YEAR, "source_url": NADAC_URL})
                counts["nadac"] += 1
        except Exception as e:  # noqa
            print(f"   nadac err {e}", file=sys.stderr)

        # ---- governance drug_sources (one row per matched source) ----
        if hit_any:
            for source, url in (("cms_partd", PARTD_URL),
                                ("cms_partb", PARTB_URL),
                                ("nadac", NADAC_URL)):
                if did in [x.split(" ")[0] for x in matched_drugs[source]]:
                    if (did, url) in existing_src:
                        continue
                    src_rows.append({
                        "drug_id": did, "drug_name": dname,
                        "claim_type": "payer_pricing",
                        "claim_value": f"{source} US public pricing/spend",
                        "source_url": url, "source_type": "other",
                        "source_domain": urllib.parse.urlparse(url).netloc,
                        "content_confirms_claim": True, "confidence": "confirmed",
                        "added_by": "payer_agent", "session_label": SESSION_LABEL})
                    existing_src.add((did, url))
        else:
            skipped.append(did)

    # ---------------------------------------------------------------- write
    print("\n=== SUMMARY ===")
    print("payer_pricing rows:", counts, "total", len(pp_rows))
    print("drug_sources new rows:", len(src_rows))
    for s in matched_drugs:
        print(f"  matched {s}: {len(matched_drugs[s])}")
        for x in matched_drugs[s]:
            print(f"      - {x}")
    print("skipped (no match in any source):", len(skipped), skipped)

    if dry:
        print("\nDRY RUN — nothing written")
        print(json.dumps(pp_rows[:5], indent=2))
        return 0

    # chunked upserts
    wrote = 0
    for c in range(0, len(pp_rows), 200):
        wrote += sb_write("payer_pricing", pp_rows[c:c + 200],
                          "resolution=merge-duplicates,return=minimal")
    print(f"\nWrote {wrote} payer_pricing rows")

    sw = 0
    for c in range(0, len(src_rows), 200):
        sw += sb_write("drug_sources", src_rows[c:c + 200], "return=minimal")
    print(f"Wrote {sw} drug_sources rows")

    # ---------------------------------------------------------------- dictionary
    dd = {
        "attribute_key": "payer_pricing",
        "display_name": "US pricing & public spend",
        "domain": "Payer",
        "source_table": "payer_pricing",
        "source_column": None,
        "check_type": "satellite_rows",
        "phase_expected": 5,
        "plain_description": "What the US public payer actually spends on the drug "
                             "— Medicare Part B/D totals and Medicaid acquisition cost.",
        "example_text": "Skyrizi: Medicare Part D total spending by year",
        "citeline_module": "Evaluate — Forecasts & Revenue",
        "benchmark_status": "partial",
        "benchmark_note": "Actual US public spend; Evaluate adds global consensus forecasts",
        "sort_order": 43,
    }
    sb_write("data_dictionary?on_conflict=attribute_key", [dd],
             "resolution=merge-duplicates,return=minimal")
    print("Upserted data_dictionary payer_pricing row")
    return 0


if __name__ == "__main__":
    sys.exit(main())
