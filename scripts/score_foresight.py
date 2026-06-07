#!/usr/bin/env python3
"""score_foresight.py — the Foresight Rate resolution loop.

What it does (idempotent, safe to re-run):
  1. SCAN    — find catalysts past their sort_date.
  2. LOG     — catalysts already resolved (resolved=true / status='met') become
               foresight_events rows (foreseen=true, matched to the catalyst).
  3. VERIFY  — past-due *pending* catalysts with a related_trial_id are checked
               against ClinicalTrials.gov v2; clear outcomes (results posted /
               COMPLETED past primary completion / TERMINATED) auto-resolve.
  4. QUEUE   — everything else is written to docs/foresight_review_queue.md for
               human resolution (Kyle confirms outcome + source, or kills stale rows).
  5. SCORE   — recompute foresight_scores per (period, area) + ALL roll-up from
               foresight_events, upserted on (period, area_id).

What it does NOT do: detect MISSES (material events that had no catalyst row).
Miss detection needs the event sweep (research.py / news pipeline integration) —
until then, Foresight Rate is an UPPER BOUND and is labeled as such in notes.

Usage:
  python3 scripts/score_foresight.py [--dry-run]

Env/files: .supabase_service_key in workspace root (or SUPABASE_SERVICE_KEY env).
See docs/frameworks/FORESIGHT_RATE_METRIC.md and migrations/v105/v106.
"""

import json
import os
import sys
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import date, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "https://tghntyofptvfhmtchwcv.supabase.co"
TODAY = date.today().isoformat()
DRY = "--dry-run" in sys.argv
QUEUE_DOC = os.path.join(ROOT, "docs", "foresight_review_queue.md")
PRED_QUEUE_DOC = os.path.join(ROOT, "docs", "prediction_review_queue.md")

# status -> outcome score for Brier (1=happened, 0=didn't, 0.5=partial)
OUTCOME = {"correct": 1.0, "incorrect": 0.0, "partially_correct": 0.5}

# Miss-detection scope
COVERED_AREAS = ("tl1a", "tslp", "il4ra", "igf1r", "fcrn", "ibd", "ted")
TRACKING_START = "2026-05-18"        # Meridian's birthday — no system existed before this, so
                                     # pre-existing events cannot be "missed". Honest window start.
MATCH_TOLERANCE_DAYS = 120           # a catalyst's sort_date must be within +/- this of the event
# deal_type (ground-truth event) -> the catalyst_type(s) that would count as having predicted it.
# Per-type so an M&A event is only credited to a deal-family catalyst, not an unrelated approval.
DEAL_TYPE_TO_CATALYST = {
    "acquisition":   {"deal", "partnership"},
    "licensing":     {"deal", "partnership"},
    "collaboration": {"deal", "partnership"},
    "partnership":   {"deal", "partnership"},
    "option":        {"deal", "partnership"},
    "financing":     {"financing", "deal"},
    "regulatory":    {"regulatory", "approval", "filing"},
    "clinical":      {"readout", "clinical_update"},
}
DEFAULT_CATALYST_MATCH = {"deal", "partnership"}
# covered mechanism -> drugs.target keyword (to scope clinical readouts to covered areas)
COVERED_TARGET_KW = {"tl1a": "TL1A", "tslp": "TSLP", "il4ra": "IL-4", "igf1r": "IGF-1R", "fcrn": "FcRn"}
READOUT_CATALYST_TYPES = {"readout", "clinical_update"}


def service_key() -> str:
    k = os.environ.get("SUPABASE_SERVICE_KEY")
    if k:
        return k.strip()
    with open(os.path.join(ROOT, ".supabase_service_key")) as f:
        return f.read().strip()


SK = service_key()
HDRS = {"apikey": SK, "Authorization": f"Bearer {SK}", "Content-Type": "application/json"}


def rest(path: str, method: str = "GET", body=None, prefer: str | None = None):
    headers = dict(HDRS)
    if prefer:
        headers["Prefer"] = prefer
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{URL}/rest/v1/{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        print(f"  !! REST {method} {path} -> {e.code}: {e.read().decode()[:300]}", file=sys.stderr)
        raise


def period_of(d: str) -> str:
    y, m = d[:4], int(d[5:7])
    return f"{y}-Q{(m - 1) // 3 + 1}"


def ctgov_status(nct: str):
    """Best-effort CT.gov v2 lookup. Returns dict or None."""
    try:
        req = urllib.request.Request(
            f"https://clinicaltrials.gov/api/v2/studies/{nct}"
            "?fields=protocolSection.statusModule,hasResults",
            headers={"User-Agent": "meridian-foresight/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            j = json.load(r)
        sm = j.get("protocolSection", {}).get("statusModule", {})
        return {
            "overall": sm.get("overallStatus"),
            "primary_completion": (sm.get("primaryCompletionDateStruct") or {}).get("date"),
            "results_posted": bool(j.get("hasResults")),
            "last_update": (sm.get("lastUpdatePostDateStruct") or {}).get("date"),
        }
    except Exception as e:  # noqa: BLE001 — network best-effort, queue on any failure
        print(f"  ctgov lookup failed for {nct}: {e}")
        return None


def existing_event_catalyst_ids() -> set:
    rows = rest("foresight_events?select=matched_catalyst_id&matched_catalyst_id=not.is.null&limit=10000")
    return {r["matched_catalyst_id"] for r in rows}


def log_event(cat: dict, event_date: str, foreseen: bool, source_url: str,
              source_type: str, notes: str) -> None:
    """Insert one foresight_events row matched to a catalyst."""
    try:
        terr = (datetime.fromisoformat(cat["sort_date"]) - datetime.fromisoformat(event_date)).days
    except Exception:  # noqa: BLE001
        terr = None
    row = {
        "period": period_of(event_date),
        "area_id": cat.get("area_id"),
        "event_type": cat.get("catalyst_type") or "readout",
        "asset_label": cat["label"][:300],
        "drug_id": cat.get("drug_id"),
        "company_id": cat.get("company_id"),
        "event_date": event_date,
        "source_url": source_url or "https://clinicaltrials.gov",
        "source_type": source_type,
        "significance": cat.get("significance") or "medium",
        "foreseen": foreseen,
        "matched_catalyst_id": cat["id"],
        "timing_error_days": terr,
        "notes": notes,
        "added_by": "score_foresight.py",
    }
    if DRY:
        print(f"  [dry] would log event for catalyst #{cat['id']}: {notes}")
        return
    rest("foresight_events", "POST", row, prefer="return=minimal")
    print(f"  + event logged for catalyst #{cat['id']} ({cat.get('area_id')}/{row['event_type']}) — {notes}")


def resolve_catalyst(cat_id: int, note: str) -> None:
    if DRY:
        return
    rest(f"catalysts?id=eq.{cat_id}", "PATCH",
         {"resolved": True, "catalyst_status": "met", "resolved_note": note[:500]},
         prefer="return=minimal")


def main() -> int:
    print(f"=== Foresight resolution loop — {TODAY}{' (DRY RUN)' if DRY else ''} ===\n")

    past_due = rest(
        "catalysts?select=id,label,area_id,catalyst_type,sort_date,catalyst_status,"
        "resolved,resolved_note,related_trial_id,drug_id,company_id,significance,source_url"
        f"&sort_date=lte.{TODAY}&order=sort_date.asc&limit=500")
    already = existing_event_catalyst_ids()
    print(f"past-due catalysts: {len(past_due)} | already logged as events: {len(already)}\n")

    queue = []
    n_logged = n_verified = 0

    for cat in past_due:
        if cat["id"] in already:
            continue

        # --- step 2: already human/pipeline-resolved -> log directly -----------
        if cat.get("resolved") or cat.get("catalyst_status") == "met":
            log_event(cat, cat["sort_date"], True, cat.get("source_url"),
                      "press_release",
                      f"pre-resolved catalyst; note: {(cat.get('resolved_note') or 'n/a')[:160]}")
            n_logged += 1
            continue

        # --- step 3: auto-verify via CT.gov when a trial id exists -------------
        nct = (cat.get("related_trial_id") or "").strip()
        if nct.startswith("NCT"):
            st = ctgov_status(nct)
            if st:
                clear_outcome = (
                    st["results_posted"]
                    or st["overall"] in ("TERMINATED", "WITHDRAWN")
                    or (st["overall"] == "COMPLETED" and (st["primary_completion"] or "9999") <= TODAY)
                )
                if clear_outcome:
                    ev_date = st["primary_completion"] or st["last_update"] or cat["sort_date"]
                    if len(ev_date) == 7:  # YYYY-MM -> first of month
                        ev_date += "-01"
                    note = (f"auto-verified via CT.gov: {st['overall']}, "
                            f"results_posted={st['results_posted']}")
                    log_event(cat, ev_date, True,
                              f"https://clinicaltrials.gov/study/{nct}", "ct_gov", note)
                    resolve_catalyst(cat["id"], note)
                    n_logged += 1
                    n_verified += 1
                    continue
                cat["_ctgov"] = f"{st['overall']} (pc={st['primary_completion']}, results={st['results_posted']})"

        # --- step 4: human review queue ----------------------------------------
        queue.append(cat)

    # --- write the review queue doc --------------------------------------------
    lines = [
        "# Foresight Review Queue",
        f"\n**Generated:** {TODAY} by `scripts/score_foresight.py`",
        "\nPast-due catalysts with no confirmed outcome. For each: confirm what happened",
        "(+ source URL), then either mark the catalyst resolved and let the next run log",
        "the event, or fix the row (wrong date / not a real event / supersede).",
        "Misses (events with NO catalyst) must be added to `foresight_events` manually",
        "with `foreseen=false` + `miss_reason` — that is where the learning lives.\n",
        "| # | id | due | area | type | label | CT.gov says | action |",
        "|---|----|-----|------|------|-------|------------|--------|",
    ]
    for i, c in enumerate(queue, 1):
        lines.append(
            f"| {i} | {c['id']} | {c['sort_date']} | {c.get('area_id') or '—'} "
            f"| {c['catalyst_type']} | {c['label'][:90].replace('|', '/')} "
            f"| {c.get('_ctgov', '—')} | ☐ |")
    if not DRY:
        with open(QUEUE_DOC, "w") as f:
            f.write("\n".join(lines) + "\n")
    print(f"\nreview queue: {len(queue)} rows -> {os.path.relpath(QUEUE_DOC, ROOT)}")

    # --- step 4.5: MISS DETECTION (makes the rate honest) ----------------------
    n_seen, n_miss = detect_misses()
    detect_readout_misses()

    # --- step 5: recompute scores ----------------------------------------------
    events = rest("foresight_events?select=period,area_id,foreseen,significance&limit=10000")
    W = {"high": 3, "medium": 2, "low": 1}
    agg = defaultdict(lambda: [0, 0, 0.0, 0.0])  # total, foreseen, w_total, w_foreseen
    for e in events:
        if e["foreseen"] is None:
            continue
        w = W.get(e.get("significance"), 2)
        for key in ((e["period"], e.get("area_id") or "unmapped"), (e["period"], "ALL")):
            a = agg[key]
            a[0] += 1
            a[2] += w
            if e["foreseen"]:
                a[1] += 1
                a[3] += w

    note = ("Deal-event miss detection ACTIVE (deals since Meridian birthday vs catalyst ledger). "
            "Readout/regulatory phase-transition miss sweep still pending — rate is honest for "
            "deal events, near-upper-bound for clinical events.")
    scores = [{
        "period": p, "area_id": a,
        "events_total": v[0], "events_foreseen": v[1],
        "weighted_total": v[2], "weighted_foreseen": v[3],
        "notes": note, "computed_at": datetime.utcnow().isoformat() + "Z",
    } for (p, a), v in sorted(agg.items())]

    if scores and not DRY:
        rest("foresight_scores?on_conflict=period,area_id", "POST", scores,
             prefer="resolution=merge-duplicates,return=minimal")

    print(f"\n=== Tier-1 summary ===\nevents logged this run: {n_logged} (ctgov-verified: {n_verified})")
    print(f"score rows upserted: {len(scores)}")
    for s in scores:
        rate = (s["events_foreseen"] / s["events_total"]) if s["events_total"] else None
        print(f"  {s['period']:>8} {s['area_id']:>12}: {s['events_foreseen']}/{s['events_total']}"
              f"  rate={rate:.2f}" if rate is not None else
              f"  {s['period']:>8} {s['area_id']:>12}: 0/0")

    resolve_tier2()
    return 0


def _ddate(s):
    try:
        return date.fromisoformat((s or "")[:10])
    except Exception:
        return None


def detect_misses():
    """Tier-1 miss detection — makes Foresight Rate honest.

    Ground truth = dated deals in covered areas SINCE Meridian's birthday
    (pre-existence events can't be 'missed'). Each is a material event; it counts
    as FORESEEN only if a deal-family catalyst existed in the same area, was
    created BEFORE the event (immutable-timestamp rule — no hindsight catalysts),
    and had a sort_date within tolerance. Otherwise it's a MISS (foreseen=false).
    Logs both so the denominator is complete. Idempotent via a 'deal:<id>' key in
    notes. Returns (n_foreseen, n_missed) logged this run.
    """
    print("\n=== miss detection (deal events) ===")
    inlist = ",".join(COVERED_AREAS)
    deals = rest("deals?select=id,deal_date,area_id,deal_type,from_company,to_company,company_id,"
                 f"headline,source_url,total_usd_m&deal_date=gte.{TRACKING_START}&deal_date=lte.{TODAY}"
                 f"&area_id=in.({inlist})&order=deal_date.asc&limit=2000")
    cats = rest("catalysts?select=id,area_id,catalyst_type,sort_date,created_at"
                f"&area_id=in.({inlist})&limit=5000")
    logged = rest("foresight_events?select=notes&added_by=eq.miss_sweep&limit=10000")
    done = {tok for r in logged for tok in (r.get("notes") or "").split() if tok.startswith("deal:")}

    n_seen = n_miss = 0
    rows = []
    for dl in deals:
        key = f"deal:{dl['id']}"
        if key in done:
            continue
        ev = _ddate(dl["deal_date"])
        if not ev:
            continue
        allowed = DEAL_TYPE_TO_CATALYST.get(dl.get("deal_type"), DEFAULT_CATALYST_MATCH)
        matched = None
        for c in cats:
            if c.get("area_id") != dl.get("area_id"):
                continue
            if c.get("catalyst_type") not in allowed:
                continue
            cc, sd = _ddate(c.get("created_at")), _ddate(c.get("sort_date"))
            if not cc or cc >= ev:                       # must predate the event — no hindsight
                continue
            if not sd or abs((sd - ev).days) > MATCH_TOLERANCE_DAYS:
                continue
            matched = c
            break
        foreseen = matched is not None
        rows.append({
            "period": period_of(dl["deal_date"]),
            "area_id": dl.get("area_id"),
            "event_type": dl.get("deal_type") or "deal",
            "asset_label": (dl.get("headline") or f"{dl.get('from_company')} deal")[:300],
            "company_id": dl.get("company_id") or dl.get("to_company") or dl.get("from_company"),
            "event_date": dl["deal_date"][:10],
            "source_url": dl.get("source_url") or "https://www.sec.gov",
            "source_type": "press_release",
            "significance": "high" if (dl.get("total_usd_m") or 0) >= 1000 else "medium",
            "foreseen": foreseen,
            "matched_catalyst_id": matched["id"] if matched else None,
            "miss_reason": None if foreseen else
                f"no catalyst predicted this {dl.get('deal_type')} event in '{dl.get('area_id')}' before {dl['deal_date'][:10]}",
            "notes": f"{key} | miss_sweep",
            "added_by": "miss_sweep",
        })
        n_seen += foreseen
        n_miss += not foreseen

    if rows and not DRY:
        rest("foresight_events", "POST", rows, prefer="return=minimal")
    print(f"  window {TRACKING_START}..{TODAY} | in-window covered deal events: {len(deals)} | "
          f"new logged: {len(rows)} (foreseen={n_seen}, missed={n_miss})")
    if not rows:
        print("  nothing new (all in-window deal events already swept).")
    return n_seen, n_miss


def _norm_pcd(s):
    """Normalize a primary-completion string ('2026-06' or '2026-06-30') to a date."""
    s = (s or "")[:10]
    if len(s) == 7:
        s += "-01"
    return _ddate(s)


def covered_drug_map():
    """{drug_id: (area_id, drug_name)} for drugs whose target matches a covered mechanism."""
    m = {}
    for area, kw in COVERED_TARGET_KW.items():
        for d in rest(f"drugs?select=id,name,target&target=ilike.*{kw}*&limit=500"):
            m.setdefault(d["id"], (area, d.get("name") or d["id"]))
    return m


def detect_readout_misses():
    """CT.gov readout-miss sweep — extends honesty to CLINICAL events.

    Candidate events = trials of covered-area drugs whose primary completion falls
    in the tracking window (a readout came due). CT.gov v2 confirms the event
    actually occurred (results posted / COMPLETED / TERMINATED / completion passed).
    Foreseen only if a catalyst predicted it: exact related_trial_id match, OR a
    readout/clinical_update catalyst in the same area tied to the drug, created
    BEFORE the event, sort_date within tolerance. Else a MISS. Idempotent via
    'trial:<NCT>' in notes; added_by='readout_sweep'.
    """
    print("\n=== readout-miss sweep (CT.gov-verified clinical events) ===")
    dmap = covered_drug_map()
    trials = rest("trials?select=id,drug_id,phase,status,primary_completion_date,study_acronym,source_url"
                  f"&primary_completion_date=gte.{TRACKING_START}&primary_completion_date=lte.{TODAY}&limit=500")
    in_scope = [t for t in trials if t.get("drug_id") in dmap]
    cats = rest("catalysts?select=id,area_id,catalyst_type,sort_date,created_at,drug_id,related_trial_id,label&limit=5000")
    logged = rest("foresight_events?select=notes&added_by=eq.readout_sweep&limit=10000")
    done = {tok for r in logged for tok in (r.get("notes") or "").split() if tok.startswith("trial:")}

    n_seen = n_miss = 0
    rows = []
    for t in in_scope:
        nct = t["id"]
        key = f"trial:{nct}"
        if key in done:
            continue
        area, dname = dmap[t["drug_id"]]
        ev = _norm_pcd(t.get("primary_completion_date"))
        if not ev:
            continue
        # CT.gov confirmation (best-effort); if unreachable, fall back to DB completion date
        st = ctgov_status(nct)
        occurred = True
        if st:
            occurred = (st["results_posted"] or st["overall"] in ("COMPLETED", "TERMINATED", "WITHDRAWN")
                        or (st["primary_completion"] or "9999") <= TODAY)
            if st["primary_completion"]:
                ev = _norm_pcd(st["primary_completion"]) or ev
        if not occurred:
            continue  # readout not actually in yet — not a material event to score this run
        # foreseen? exact trial match first, then drug+area readout catalyst created before the event
        matched = None
        for c in cats:
            cc = _ddate(c.get("created_at"))
            if c.get("related_trial_id") == nct and cc and cc < ev:
                matched = c; break
        if not matched:
            for c in cats:
                if c.get("area_id") != area or c.get("catalyst_type") not in READOUT_CATALYST_TYPES:
                    continue
                cc, sd = _ddate(c.get("created_at")), _ddate(c.get("sort_date"))
                if not cc or cc >= ev or not sd or abs((sd - ev).days) > MATCH_TOLERANCE_DAYS:
                    continue
                if c.get("drug_id") == t["drug_id"] or dname.lower() in (c.get("label") or "").lower():
                    matched = c; break
        foreseen = matched is not None
        label = f"{dname} {t.get('study_acronym') or ''} readout ({t.get('phase')})".strip()
        rows.append({
            "period": period_of(ev.isoformat()), "area_id": area, "event_type": "readout",
            "asset_label": label[:300], "drug_id": t["drug_id"],
            "event_date": ev.isoformat(),
            "source_url": t.get("source_url") or f"https://clinicaltrials.gov/study/{nct}",
            "source_type": "ct_gov", "significance": "high",
            "foreseen": foreseen, "matched_catalyst_id": matched["id"] if matched else None,
            "miss_reason": None if foreseen else f"no catalyst predicted the {nct} readout in '{area}' before {ev.isoformat()}",
            "notes": f"{key} | readout_sweep", "added_by": "readout_sweep",
        })
        n_seen += foreseen
        n_miss += not foreseen

    if rows and not DRY:
        rest("foresight_events", "POST", rows, prefer="return=minimal")
    print(f"  window {TRACKING_START}..{TODAY} | covered in-window trials: {len(in_scope)} | "
          f"new logged: {len(rows)} (foreseen={n_seen}, missed={n_miss})")
    if not rows:
        print("  nothing new (all in-window covered readouts already swept or not yet occurred).")
    return n_seen, n_miss


def resolve_tier2() -> None:
    """Tier-2 (judgment) pass: flag overdue calls for human verdict, then score
    whatever is already resolved (Brier + hit rate + calibration).

    Judgment calls (acquisition, asset_value, leader_rank, ...) are NOT auto-
    verdicted — fabricating an outcome would poison the very metric we're building.
    The loop's job is to surface what's DUE and to score what's DONE. A linked
    CT.gov trial (related to the prediction) is shown as a hint, not a verdict.
    """
    print("\n=== Tier-2 (judgment predictions) ===")
    preds = rest("foresight_predictions?select=id,subject_label,prediction_type,statement,"
                 "confidence,status,predicted_window_end,resolved_at,reasons_held,area_id"
                 "&order=predicted_window_end.asc&limit=1000")
    if not preds:
        print("  no predictions seeded yet.")
        return

    overdue = [p for p in preds if p["status"] == "open" and (p.get("predicted_window_end") or "9999") < TODAY]
    resolved = [p for p in preds if p["status"] in OUTCOME]
    open_n = sum(1 for p in preds if p["status"] == "open")
    print(f"  total={len(preds)} | open={open_n} | resolved={len(resolved)} | overdue(need verdict)={len(overdue)}")

    # write the prediction review queue (overdue open calls)
    q = ["# Prediction Review Queue (Tier-2)",
         f"\n**Generated:** {TODAY} by `scripts/score_foresight.py`",
         "\nThese judgment calls are past their resolution window and still `open`.",
         "For each: set `status` (correct / incorrect / partially_correct / expired),",
         "fill `outcome_text` + `outcome_date` (+ `outcome_value_usd` for deals),",
         "set `reasons_held` (did the rationale survive?), and add a source URL.",
         "Do this in Supabase or via a follow-up script — never let the loop guess.\n",
         "| id | type | due | confidence | statement |",
         "|----|------|-----|-----------|-----------|"]
    for p in overdue:
        q.append(f"| {p['id'][:8]} | {p['prediction_type']} | {p['predicted_window_end']} "
                 f"| {p['confidence']:.0%} | {p['statement'][:90].replace('|', '/')} |")
    if not DRY:
        with open(PRED_QUEUE_DOC, "w") as f:
            f.write("\n".join(q) + "\n")
    print(f"  prediction review queue: {len(overdue)} rows -> {os.path.relpath(PRED_QUEUE_DOC, ROOT)}")

    # score the resolved set (Brier: lower is better; hit rate; calibration)
    if not resolved:
        print("  no resolved predictions yet — accuracy series starts at first resolution.")
        print("  (the Predictions tab builds the running accuracy line from resolved_at order.)")
        return
    brier = sum((p["confidence"] - OUTCOME[p["status"]]) ** 2 for p in resolved) / len(resolved)
    hits = sum(1 for p in resolved if p["status"] == "correct")
    held = sum(1 for p in resolved if p.get("reasons_held"))
    print(f"  Brier score: {brier:.3f} (0=perfect, 0.25=coin-flip at 50%)")
    print(f"  hit rate: {hits}/{len(resolved)} = {hits/len(resolved):.0%}")
    print(f"  rationale held (incl. missed calls): {held}/{len(resolved)}")
    # calibration buckets
    buckets = defaultdict(lambda: [0, 0.0])  # n, sum_outcome
    for p in resolved:
        b = round(p["confidence"] * 10) / 10
        buckets[b][0] += 1
        buckets[b][1] += OUTCOME[p["status"]]
    print("  calibration (predicted -> actual):")
    for b in sorted(buckets):
        n, s = buckets[b]
        print(f"    said {b:.0%} (n={n}): happened {s/n:.0%}")


if __name__ == "__main__":
    sys.exit(main())
