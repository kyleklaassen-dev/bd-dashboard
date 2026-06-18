#!/usr/bin/env python3
"""
intelligence_quality.py — the PRODUCT-value scoreboard for Meridian.

`meridian_health_metrics.py` measures the CODE (structure, cycles, write paths). This measures
the INTELLIGENCE — the thing the platform exists to produce: is the data accurate, complete,
source-backed, governance-clean, and fresh? Read-only; safe to run anytime.

  1. Validation pass-rate   (drug_validation_results)
  2. Governance cleanliness (governance_violations, unresolved)
  3. Drug completeness      (completeness tiers + critical-field fill)
  4. Source coverage        (% of drugs with a cited drug_sources row)
  5. Freshness              (how recently records were updated)
  6. Volume                 (the corpus sizes)

Run: `python scripts/maintenance/intelligence_quality.py`  (add `--json` for machine output)

Credentials: env first (SUPABASE_URL / SUPABASE_SERVICE_KEY), then repo-root files.
"""
import os
import sys
import json
import datetime
import collections
import urllib.request
import urllib.parse

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _cred(env, filename):
    if os.environ.get(env):
        return os.environ[env].strip()
    try:
        with open(os.path.join(_ROOT, filename)) as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


URL = (_cred("SUPABASE_URL", ".supabase_url") or "https://tghntyofptvfhmtchwcv.supabase.co").rstrip("/")
KEY = _cred("SUPABASE_SERVICE_KEY", ".supabase_service_key")
_H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}
_NOW = datetime.datetime.now(datetime.timezone.utc)


def _get(table, params):
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{URL}/rest/v1/{table}?{q}", headers=_H)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _all(table, select, page=1000):
    """Paginated full fetch (PostgREST caps a single response, default 1000)."""
    out, off = [], 0
    while True:
        rows = _get(table, {"select": select, "limit": page, "offset": off})
        out += rows
        if len(rows) < page:
            return out
        off += page


def _pct(num, den):
    return f"{(100*num/den):.1f}%" if den else "n/a"


def _age_days(s):
    if not s:
        return None
    try:
        return (_NOW - datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))).days
    except Exception:
        return None


def collect():
    m = {}
    # 1. validation
    vr = _all("drug_validation_results", "check_status")
    vc = collections.Counter(x.get("check_status") for x in vr)
    m["validation"] = {"total": len(vr), "by_status": dict(vc),
                       "pass_rate": _pct(vc.get("pass", 0), len(vr))}
    # 2. governance
    gv = _all("governance_violations", "resolved,rule_name")
    unresolved = [x for x in gv if not x.get("resolved")]
    m["governance"] = {"total": len(gv), "unresolved": len(unresolved),
                       "top_unresolved_rules": dict(collections.Counter(
                           x.get("rule_name") for x in unresolved).most_common(5))}
    # 3 + 4 + 5. drugs
    dr = _all("drugs", "id,completeness_tier,mechanism,stage,drug_summary,source_url,"
                       "dashboard_visible,updated_at,discovery_status")
    n = len(dr)
    tiers = collections.Counter(d.get("completeness_tier") or "(untiered)" for d in dr)
    m["completeness"] = {
        "drugs": n, "tiers": dict(tiers),
        "missing_mechanism": sum(1 for d in dr if not d.get("mechanism")),
        "missing_stage": sum(1 for d in dr if not d.get("stage")),
        "missing_summary": sum(1 for d in dr if not d.get("drug_summary")),
        "untiered": tiers.get("(untiered)", 0),
        "dashboard_visible": sum(1 for d in dr if d.get("dashboard_visible")),
    }
    actual_ids = set(d.get("id") for d in dr)
    ds = _all("drug_sources", "drug_id")
    src_ids = set(x.get("drug_id") for x in ds)
    covered = src_ids & actual_ids
    orphan_src = src_ids - actual_ids   # source rows citing drugs not in the drugs table
    m["source_coverage"] = {
        "source_rows": len(ds), "drugs_with_sources": len(covered),
        "coverage": _pct(len(covered), n),
        "drugs_null_source_url": sum(1 for d in dr if not d.get("source_url")),
        "orphan_source_drug_ids": len(orphan_src),   # ← data-integrity signal
    }
    ages = [a for a in (_age_days(d.get("updated_at")) for d in dr) if a is not None]
    ages.sort()
    m["freshness"] = {
        "drugs_with_timestamp": len(ages),
        "median_age_days": ages[len(ages)//2] if ages else None,
        "stale_over_90d": sum(1 for a in ages if a > 90),
        "stale_over_180d": sum(1 for a in ages if a > 180),
    }
    # 6. volume (exact counts via PostgREST count header)
    vol = {}
    for t in ["drugs", "companies", "deals", "catalysts", "entity_edges", "trials", "intel_facts"]:
        req = urllib.request.Request(f"{URL}/rest/v1/{t}?select=id&limit=0",
                                     headers={**_H, "Prefer": "count=exact", "Range": "0-0"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                vol[t] = int(r.headers.get("content-range", "0/0").split("/")[-1])
        except Exception:
            vol[t] = "?"
    m["volume"] = vol
    return m


def render(m):
    P = print
    P("=" * 70); P("MERIDIAN INTELLIGENCE QUALITY"); P("=" * 70)
    v = m["validation"]
    P(f"\n── 1. VALIDATION PASS-RATE ──\n  {v['pass_rate']} pass  ({v['by_status']}) of {v['total']} checks")
    g = m["governance"]
    flag = "  ✓" if g["unresolved"] == 0 else f"  ⚠ {g['unresolved']} OPEN"
    P(f"\n── 2. GOVERNANCE ──\n  {g['unresolved']} unresolved / {g['total']} total{flag}")
    for rule, c in g["top_unresolved_rules"].items():
        P(f"     {c:3d}  {rule}")
    c = m["completeness"]
    P(f"\n── 3. DRUG COMPLETENESS ({c['drugs']} drugs) ──")
    P(f"  tiers: {c['tiers']}")
    P(f"  untiered (no score computed): {c['untiered']}  ← scoring gap")
    P(f"  missing: mechanism={c['missing_mechanism']} stage={c['missing_stage']} summary={c['missing_summary']}")
    P(f"  dashboard-visible: {c['dashboard_visible']}/{c['drugs']}")
    s = m["source_coverage"]
    P(f"\n── 4. SOURCE COVERAGE ──\n  {s['coverage']} of drugs have ≥1 cited source "
      f"({s['drugs_with_sources']} drugs, {s['source_rows']} source rows)")
    P(f"  drugs with null source_url: {s['drugs_null_source_url']}")
    if s.get("orphan_source_drug_ids"):
        P(f"  ⚠ orphan source rows: {s['orphan_source_drug_ids']} drug_ids cited in drug_sources "
          f"but absent from the drugs table (aliased/deleted/dangling)")
    f = m["freshness"]
    P(f"\n── 5. FRESHNESS (drugs.updated_at) ──\n  median age {f['median_age_days']}d  |  "
      f">90d: {f['stale_over_90d']}  >180d: {f['stale_over_180d']}")
    P(f"\n── 6. VOLUME ──\n  " + "  ".join(f"{k}={vv}" for k, vv in m["volume"].items()))
    P("")


def main():
    if not KEY:
        print("ERROR: no Supabase key (set SUPABASE_SERVICE_KEY or add .supabase_service_key).")
        sys.exit(2)
    m = collect()
    if "--json" in sys.argv:
        print(json.dumps(m, indent=2, default=str))
    else:
        render(m)


if __name__ == "__main__":
    main()
