#!/usr/bin/env python3
"""
recompute_indication_priority.py — refresh indication_priority_scores from CURRENT live signals.

Data-derived dimensions are recomputed from production tables; curated expert judgments
(ailux_fit, biology_validation, regulatory_pathway_clarity, patient_stratifiability) are kept.
Composite (documented v2 weights):
  unmet×0.20 + fit×0.25 + wspace×0.15 + window×0.20 + bio×0.10 + reg×0.05 + strat×0.05

Refreshed from live:
  - unmet_need_score, patient_count_us, market_size, remission/failure rates ← indication_patient_intelligence
  - competitive_white_space ← v_whitespace_indications (fewer late-stage competitors = more whitespace)
  - window_urgency_score ← nearest upcoming catalyst in the indication's area (sooner = more urgent)

Idempotent. Run: python3 scripts/recompute_indication_priority.py [--apply]
"""
import json, os, sys, datetime, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SB = "https://tghntyofptvfhmtchwcv.supabase.co/rest/v1"
KEY = open(os.path.join(ROOT, ".supabase_service_key")).read().strip()
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
APPLY = "--apply" in sys.argv
TODAY = datetime.date.today()

def get(path):
    r = urllib.request.Request(f"{SB}/{path}")
    for k, v in H.items(): r.add_header(k, v)
    with urllib.request.urlopen(r, timeout=40) as resp:
        return json.loads(resp.read().decode())

def patch(path, body):
    r = urllib.request.Request(f"{SB}/{path}", method="PATCH", data=json.dumps(body).encode())
    for k, v in H.items(): r.add_header(k, v)
    r.add_header("Prefer", "return=minimal")
    with urllib.request.urlopen(r, timeout=40) as resp:
        return resp.status

# ---- weights
W = dict(unmet=.20, fit=.25, wspace=.15, window=.20, bio=.10, reg=.05, strat=.05)

# ---- whitespace from late-stage competitor count
def whitespace_from_late(n_late):
    if n_late is None: return None
    if n_late <= 0: return 10
    if n_late <= 2: return 8
    if n_late <= 5: return 6
    if n_late <= 9: return 4
    return 2

# ---- window urgency from days to nearest upcoming catalyst
def window_from_days(days):
    if days is None: return None
    if days < 90:  return 9
    if days < 180: return 8
    if days < 365: return 7
    if days < 540: return 6
    return 5

def main():
    rows = get("indication_priority_scores?select=*")
    pat  = {r["indication_name"]: r for r in get("indication_patient_intelligence?select=indication_name,unmet_need_score,patient_count_us,market_size_usd_bn,remission_rate_soc_pct,biologic_failure_rate_pct,source_urls")}
    ws   = {r.get("indication_id"): r for r in get("v_whitespace_indications?select=indication_id,indication_name,drugs_late,drugs_total,saturation")}
    # nearest upcoming catalyst per area_id
    cats = get(f"catalysts?select=area_id,catalyst_date&resolved=eq.false&catalyst_date=gte.{TODAY}&order=catalyst_date.asc&limit=2000")
    nearest = {}
    for c in cats:
        a = c.get("area_id"); d = c.get("catalyst_date")
        if a and d and a not in nearest: nearest[a] = d   # first = soonest (ordered)

    # area_id for each indication row — fall back to indication_id itself (areas share id)
    updated = []
    for r in rows:
        iid = r.get("indication_id"); nm = r.get("indication_name")
        new = {}
        # unmet need (live patient intel)
        p = pat.get(nm)
        if p:
            if p.get("unmet_need_score") is not None: new["unmet_need_score"] = p["unmet_need_score"]
            for col in ("patient_count_us", "market_size_usd_bn", "remission_rate_soc_pct", "biologic_failure_rate_pct"):
                if p.get(col) is not None: new[col] = p[col]
        # whitespace (live competitor counts)
        w = ws.get(iid)
        if w:
            v = whitespace_from_late(w.get("drugs_late"))
            if v is not None: new["competitive_white_space"] = v
        # window urgency (nearest upcoming catalyst in this area)
        nd = nearest.get(iid)
        if nd:
            try:
                days = (datetime.date.fromisoformat(nd[:10]) - TODAY).days
                v = window_from_days(days)
                if v is not None: new["window_urgency_score"] = v
            except Exception: pass
        # recompute composite with refreshed + kept dims
        g = lambda k, dflt: new.get(k, r.get(dflt))
        comp = (g("unmet_need_score","unmet_need_score") or 0)*W["unmet"] \
             + (r.get("ailux_fit_score") or 0)*W["fit"] \
             + (g("competitive_white_space","competitive_white_space") or 0)*W["wspace"] \
             + (g("window_urgency_score","window_urgency_score") or 0)*W["window"] \
             + (r.get("biology_validation_score") or 0)*W["bio"] \
             + (r.get("regulatory_pathway_clarity") or 0)*W["reg"] \
             + (r.get("patient_stratifiability") or 0)*W["strat"]
        new["composite_score"] = round(comp, 2)
        new["last_computed"] = datetime.datetime.utcnow().isoformat() + "Z"
        updated.append((r, new))

    # re-rank ONLY the core indications (existing rank <100) contiguously 1..N by new composite;
    # the >100 "area/sentinel" rows keep their existing sentinel ranks (not part of the Top list).
    core = sorted([u for u in updated if (u[0].get("indication_priority_rank") or 0) < 100],
                  key=lambda x: -x[1]["composite_score"])
    for i, (r, new) in enumerate(core, 1):
        new["indication_priority_rank"] = i

    print(f"{'APPLYING' if APPLY else 'DRY-RUN'} — {len(updated)} indications")
    print(f"{'rank':>4} {'indication':32} {'old→new comp':>14}  unmet wspace window")
    for r, new in sorted(updated, key=lambda x: x[1].get("indication_priority_rank", 999)):
        print(f"{new.get('indication_priority_rank', r.get('indication_priority_rank')):>4} {(r['indication_name'] or '')[:32]:32} "
              f"{r.get('composite_score')}→{new['composite_score']:>5}   "
              f"{new.get('unmet_need_score', r.get('unmet_need_score'))}    "
              f"{new.get('competitive_white_space', r.get('competitive_white_space'))}     "
              f"{new.get('window_urgency_score', r.get('window_urgency_score'))}")
        if APPLY:
            patch(f"indication_priority_scores?indication_id=eq.{urllib_quote(r['indication_id'])}", new)
    if APPLY: print("done — table updated")

def urllib_quote(s):
    import urllib.parse
    return urllib.parse.quote(str(s), safe="")

if __name__ == "__main__":
    main()
