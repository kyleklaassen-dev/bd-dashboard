#!/usr/bin/env python3
"""
score_foresight.py — Foresight resolution loop (weekend score-foresight workflow).

Orchestrator after the §3 split: main() + the miss-detection / tier-2 logic, over
the IO + config + constants layer in score_foresight_base. Run with PYTHONPATH=src
(as the score-foresight workflow does); --dry-run suppresses writes.
"""
import os
import sys
import re
import json
from collections import defaultdict
from datetime import date, datetime

from meridian.scoring.score_foresight_base import (
    rest, period_of, ctgov_status, existing_event_catalyst_ids, log_event, resolve_catalyst,
    OUTCOME, COVERED_AREAS, TRACKING_START, MATCH_TOLERANCE_DAYS, DEAL_TYPE_TO_CATALYST,
    DEFAULT_CATALYST_MATCH, COVERED_TARGET_KW, READOUT_CATALYST_TYPES,
    DRY, TODAY, URL, ROOT, QUEUE_DOC, PRED_QUEUE_DOC,
)


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
        f"\n**Generated:** {TODAY} by `src/meridian/scoring/score_foresight.py`",
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
                 "confidence,status,predicted_window_end,resolved_at,reasons_held,area_id,"
                 "made_on,outcome_date,lead_time_days"
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
         f"\n**Generated:** {TODAY} by `src/meridian/scoring/score_foresight.py`",
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

    # lead-time: how EARLY did we call it? (outcome_date - made_on, in days).
    # Only meaningful for calls made BEFORE the event; feeds v_signal_library.avg_lead_days,
    # the measure of how far ahead each "early signal" reason lets us see.
    from datetime import date as _date
    def _d(s):
        try: return _date.fromisoformat(s[:10])
        except Exception: return None
    lead_set = 0
    for p in resolved:
        if p.get("lead_time_days") is not None:
            continue
        md, od = _d(p.get("made_on")), _d(p.get("outcome_date"))
        if md and od and od > md:
            days = (od - md).days
            if not DRY:
                rest(f"foresight_predictions?id=eq.{p['id']}", method="PATCH",
                     body={"lead_time_days": days})
            lead_set += 1
    if lead_set:
        print(f"  lead-time computed for {lead_set} resolved call(s) (made_on -> outcome).")

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
