#!/usr/bin/env python3
"""
event_research.py — event-driven deep research for Meridian catalysts.

When a catalyst is imminent or has just passed, hyper-focus on that molecule /
company / event, learn everything we can from the live web, and STORE it:

  • every extracted FACT  → `intel_facts`  (each REQUIRES a real http(s) source URL;
                                            no URL ⇒ the fact is dropped, never invented)
  • a one-paragraph synthesis →
        future event  → catalyst.expected_impact  ("what research expects")
        past event    → catalyst.outcome_text     ("what the data showed")
    written through the sanctioned CatalystWriter (meridian.database.update_catalyst).

The emphasis is on WHAT IT IS, not what it means: numbers, trial design, endpoints,
AE breadth, KOL quotes, deal terms — each tied to a source. Relevance is gated to
Ailux's key areas only (TL1A, TSLP, IL-4Rα, IGF1R, FcRn, Treg).

Scheduling: runs in GitHub Actions (daily cron + manual dispatch) — never on a
laptop. See .github/workflows/event-research.yml.

Usage:
    python3 scripts/maintenance/event_research.py --dry-run
    python3 scripts/maintenance/event_research.py --limit 4
    python3 scripts/maintenance/event_research.py --past-days 60 --future-days 120
    python3 scripts/maintenance/event_research.py --only past   # or: future

Credentials (env in CI, repo-root dotfiles locally):
    ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys

import anthropic
import requests

from meridian.credentials import read_key
from meridian.database import update_catalyst

# ── Config ───────────────────────────────────────────────────────────────────
MODEL = "claude-opus-4-8"
AILUX_AREAS = ["tl1a", "tslp", "il4ra", "igf1r", "fcrn", "tcell"]
AREA_LABEL = {
    "tl1a": "TL1A (anti-TL1A / TL1A×IL-23 IBD)",
    "tslp": "TSLP (alarmin — asthma/COPD)",
    "il4ra": "IL-4Rα (atopic dermatitis / Th2)",
    "igf1r": "IGF1R (thyroid eye disease)",
    "fcrn": "FcRn (IgG-mediated autoimmunity)",
    "tcell": "Treg / T-cell tolerance (autoimmunity)",
}
WEB_TOOLS = [
    {"type": "web_search_20260209", "name": "web_search", "max_uses": 8},
    {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 6},
]
NOW = datetime.date.today()

SUPABASE_URL = read_key("SUPABASE_URL", ".supabase_url", "https://tghntyofptvfhmtchwcv.supabase.co")
SUPABASE_KEY = read_key("SUPABASE_SERVICE_KEY", ".supabase_service_key")
ANTHROPIC_API_KEY = read_key("ANTHROPIC_API_KEY", ".anthropic_api_key")

SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def log(msg):
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ── Event selection (read-only) ───────────────────────────────────────────────
def _sb_get(table, params):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=SB_HEADERS, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def select_events(past_days, future_days, only):
    """Top Ailux events worth researching, highest-value first.

    PAST   — catalysts in the last `past_days` whose outcome_text is null
             (we don't yet know what the data showed). Data readouts rank above
             non-data events (initiations/filings) by significance.
    FUTURE — high-significance catalysts in the next `future_days` whose
             expected_impact is null (we haven't framed what's expected).
    """
    area_in = "in.(%s)" % ",".join(AILUX_AREAS)
    past_cutoff = (NOW - datetime.timedelta(days=past_days)).isoformat()
    future_cutoff = (NOW + datetime.timedelta(days=future_days)).isoformat()
    sig_rank = {"high": 0, "medium": 1, "low": 2}
    events = []

    if only in (None, "past"):
        rows = _sb_get("catalysts", {
            "select": "id,label,area_id,sort_date,catalyst_date,significance,catalyst_type,drug_id,company_id,outcome_text",
            "area_id": area_in,
            "sort_date": f"lte.{NOW.isoformat()}",
            "outcome_text": "is.null",
            "order": "sort_date.desc",
        })
        for r in rows:
            if r.get("sort_date", "") < past_cutoff:
                continue
            events.append({**r, "_mode": "past",
                           "_rank": (sig_rank.get(r.get("significance"), 3), r.get("sort_date", ""))})

    if only in (None, "future"):
        rows = _sb_get("catalysts", {
            "select": "id,label,area_id,sort_date,catalyst_date,significance,catalyst_type,drug_id,company_id,expected_impact",
            "area_id": area_in,
            "sort_date": f"gt.{NOW.isoformat()}",
            "significance": "eq.high",
            "expected_impact": "is.null",
            "order": "sort_date.asc",
        })
        for r in rows:
            if r.get("sort_date", "") > future_cutoff:
                continue
            events.append({**r, "_mode": "future",
                           "_rank": (sig_rank.get(r.get("significance"), 3), r.get("sort_date", ""))})

    # past events first (most concrete facts), then by significance, then recency/proximity
    events.sort(key=lambda e: (0 if e["_mode"] == "past" else 1, e["_rank"][0], e["_rank"][1]))
    return events


# ── Drug / company context for grounding the prompt ───────────────────────────
def _context(ev):
    bits = []
    if ev.get("drug_id"):
        rows = _sb_get("drugs", {"select": "name,inn_name,company_id,target,stage,modality,mechanism",
                                 "id": f"eq.{ev['drug_id']}"})
        if rows:
            d = rows[0]
            bits.append("Drug: %s%s — target %s, %s, %s%s" % (
                d.get("name") or ev["drug_id"],
                f" ({d['inn_name']})" if d.get("inn_name") else "",
                d.get("target") or "?", d.get("modality") or "?", d.get("stage") or "?",
                f"; MoA: {d['mechanism']}" if d.get("mechanism") else ""))
    if ev.get("company_id"):
        rows = _sb_get("companies", {"select": "name", "id": f"eq.{ev['company_id']}"})
        if rows:
            bits.append("Company: %s" % rows[0].get("name", ev["company_id"]))
    return "\n".join(bits)


# ── The research call (server-tool loop, pause_turn aware) ─────────────────────
SYSTEM = (
    "You are a biopharma competitive-intelligence analyst for Meridian, the BD platform behind "
    "Ailux (a TL1A×IL-23p19 bispecific for IBD). You research a single catalyst event deeply using "
    "live web search and fetch, then report FACTS — what the event IS, not what it means.\n\n"
    "Hard rules:\n"
    "• Prioritise primary sources: company press releases, ClinicalTrials.gov, FDA, peer-reviewed "
    "papers, conference abstracts (ECCO/EULAR/DDW/AAD/ATS), and reputable trade press (Endpoints, "
    "FierceBiotech, STAT).\n"
    "• EVERY fact you report must carry the exact http(s) URL you saw it at. If you cannot attach a "
    "real URL, DO NOT report the fact. Never invent or guess a URL.\n"
    "• Capture concrete specifics: trial design, N, endpoints, % responses/remission, p-values, AE "
    "breadth, dosing, regulatory dates, deal terms, and any directly-quoted KOL or management "
    "commentary (with attribution).\n"
    "• Be precise and terse. No spin, no 'this suggests'. State the datum and its source."
)

OUTPUT_INSTRUCTION = (
    "\n\nWhen you have gathered enough, STOP searching and output ONLY a single JSON object "
    "(no prose around it), in a ```json fenced block, with this shape:\n"
    "{\n"
    '  "facts": [\n'
    '    {"claim": "<one concrete fact>", "fact_type": "clinical|regulatory|commercial|deal|'
    'competitive|kol_sentiment|patient|pipeline|catalyst", "metric": "<what is measured, or null>", '
    '"value_text": "<short value, or null>", "value_num": <number or null>, "unit": "<unit or null>", '
    '"confidence": "high|medium|low", "source_url": "https://..."}\n'
    "  ],\n"
    '  "synthesis": "<2-4 sentence synthesis: for a FUTURE event, what the research expects from the '
    'catalyst and why it matters competitively; for a PAST event, what the data actually showed. '
    'Facts only, sourced above.>",\n'
    '  "kol_quotes": [{"quote": "<verbatim>", "who": "<name, affiliation>", "source_url": "https://..."}]\n'
    "}\n"
    "Aim for 6-15 facts. Drop any fact without a real source_url. If web_search repeatedly "
    "errors or returns nothing usable, stop and return an empty facts array with an empty "
    "synthesis — do NOT speculate or write a synthesis unsupported by sourced facts."
)


def run_research(client, ev, ctx, max_turns=14):
    when = "ALREADY OCCURRED (research what the data/outcome showed)" if ev["_mode"] == "past" \
        else "IS UPCOMING (research what the field expects from it)"
    user = (
        f"CATALYST EVENT TO RESEARCH (this event {when}):\n"
        f"  Label: {ev['label']}\n"
        f"  Date: {ev.get('catalyst_date') or ev.get('sort_date')}\n"
        f"  Therapeutic area: {AREA_LABEL.get(ev['area_id'], ev['area_id'])}\n"
        f"{ctx}\n\n"
        "Research this event thoroughly with web_search and web_fetch. Find the primary data, "
        "the trial details, regulatory specifics, competitive positioning, and any KOL/management "
        "commentary. Then report the facts." + OUTPUT_INSTRUCTION
    )
    messages = [{"role": "user", "content": user}]
    last = None
    for turn in range(max_turns):
        last = client.messages.create(
            model=MODEL,
            max_tokens=8000,
            system=SYSTEM,
            tools=WEB_TOOLS,
            messages=messages,
            thinking={"type": "adaptive"},
        )
        messages.append({"role": "assistant", "content": last.content})
        if last.stop_reason == "pause_turn":
            continue  # server-tool turn paused mid-loop; resume
        break
    return last


def _extract_json(resp):
    text = "\n".join(b.text for b in resp.content if getattr(b, "type", "") == "text" and getattr(b, "text", ""))
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    raw = m.group(1) if m else None
    if not raw:
        # last-ditch: outermost braces
        s, e = text.find("{"), text.rfind("}")
        raw = text[s:e + 1] if s != -1 and e > s else None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


# ── Writers ────────────────────────────────────────────────────────────────
_URL_RE = re.compile(r"^https?://", re.I)


def write_facts(ev, parsed, dry_run):
    """Insert sourced facts into intel_facts. Returns (written, dropped)."""
    subject_type = "drug" if ev.get("drug_id") else "company" if ev.get("company_id") else "area"
    subject_id = ev.get("drug_id") or ev.get("company_id") or ev["area_id"]
    rows, dropped = [], 0
    facts = parsed.get("facts") or []

    # fold KOL quotes in as kol_sentiment facts (each needs its own URL too)
    for q in parsed.get("kol_quotes") or []:
        if q.get("quote") and _URL_RE.match(str(q.get("source_url", ""))):
            facts.append({"claim": f'"{q["quote"]}" — {q.get("who", "KOL")}',
                          "fact_type": "kol_sentiment", "confidence": "medium",
                          "source_url": q["source_url"], "metric": None,
                          "value_text": None, "value_num": None, "unit": None})

    for f in facts:
        url = str(f.get("source_url", "")).strip()
        if not _URL_RE.match(url):
            dropped += 1
            continue
        rows.append({
            "source_url": url,
            "fact_type": (f.get("fact_type") or "clinical")[:40],
            "subject_type": subject_type,
            "subject_id": subject_id,
            "subject_name": None,
            "claim": str(f.get("claim", ""))[:2000],
            "metric": f.get("metric"),
            "value_num": f.get("value_num") if isinstance(f.get("value_num"), (int, float)) else None,
            "value_text": f.get("value_text"),
            "unit": f.get("unit"),
            "area_id": ev["area_id"],
            "confidence": f.get("confidence") if f.get("confidence") in ("high", "medium", "low") else "medium",
            "section": f"event_research:catalyst:{ev['id']}",
        })

    if not rows:
        return 0, dropped
    if dry_run:
        return len(rows), dropped
    r = requests.post(f"{SUPABASE_URL}/rest/v1/intel_facts",
                      headers={**SB_HEADERS, "Prefer": "return=minimal"},
                      json=rows, timeout=45)
    if r.status_code >= 300:
        log(f"  ! intel_facts insert failed: {r.status_code} {r.text[:200]}")
        return 0, dropped
    return len(rows), dropped


def write_synthesis(ev, parsed, dry_run):
    synth = (parsed.get("synthesis") or "").strip()
    if not synth:
        return False
    field = "outcome_text" if ev["_mode"] == "past" else "expected_impact"
    if dry_run:
        log(f"  [dry-run] would set catalyst {ev['id']}.{field} = {synth[:120]}…")
        return True
    ok = update_catalyst(ev["id"], {field: synth})
    if not ok:
        log(f"  ! update_catalyst({ev['id']}, {field}) rejected by writer")
    return ok


# ── Main ───────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="Event-driven deep research for Meridian catalysts.")
    ap.add_argument("--limit", type=int, default=4, help="max events to research (default 4, focused)")
    ap.add_argument("--past-days", type=int, default=60, help="look-back window for past catalysts")
    ap.add_argument("--future-days", type=int, default=120, help="look-ahead window for future catalysts")
    ap.add_argument("--only", choices=["past", "future"], default=None, help="restrict to one mode")
    ap.add_argument("--dry-run", action="store_true", help="research + parse, but write nothing")
    args = ap.parse_args()

    if not ANTHROPIC_API_KEY:
        log("FATAL: ANTHROPIC_API_KEY not set"); sys.exit(1)
    if not SUPABASE_KEY:
        log("FATAL: SUPABASE_SERVICE_KEY not set"); sys.exit(1)

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    events = select_events(args.past_days, args.future_days, args.only)
    log(f"Selected {len(events)} candidate Ailux events; researching top {min(args.limit, len(events))}"
        f"{' (DRY RUN)' if args.dry_run else ''}.")

    tot_facts = tot_dropped = tot_synth = 0
    for ev in events[:args.limit]:
        log(f"▶ [{ev['_mode']}] {ev['area_id']} · {ev.get('sort_date')} · {ev['label'][:80]}")
        ctx = _context(ev)
        try:
            resp = run_research(client, ev, ctx)
        except Exception as e:
            log(f"  ! research error: {e}")
            continue
        parsed = _extract_json(resp)
        if not parsed:
            log("  ! no parseable JSON returned; skipping writes")
            continue
        nf, nd = write_facts(ev, parsed, args.dry_run)
        # Never write a synthesis with no sourced facts behind it — a catalyst card
        # must always be backed by evidence (drop it if the search yielded nothing).
        ok = write_synthesis(ev, parsed, args.dry_run) if nf > 0 else False
        if nf == 0:
            log("  · 0 sourced facts (search yielded nothing usable) — synthesis suppressed")
        tot_facts += nf; tot_dropped += nd; tot_synth += (1 if ok else 0)
        log(f"  ✓ {nf} facts written, {nd} dropped (no URL), synthesis={'set' if ok else 'none'}")

    log(f"DONE — {tot_facts} facts written, {tot_dropped} dropped, {tot_synth} catalysts synthesised"
        f"{' (DRY RUN — nothing persisted)' if args.dry_run else ''}.")


if __name__ == "__main__":
    main()
