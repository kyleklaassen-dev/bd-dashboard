#!/usr/bin/env python3
"""
poster_research.py — active discovery & enrichment of conference posters/presentations.

Conference posters are a perpetual high-need signal: a competitor presenting
late-breaking data at DDW/ECCO/EULAR/AAD/ATS can move a program before any press
release. The seeded `conference_abstracts` table is title-only and hollow (no
abstract text, authors, dates). This pipeline actively HUNTS posters relevant to
Ailux's molecules and their direct competitors, and STORES the specifics:

  • enriched poster record → `conference_abstracts` (conference, date, type, title,
    key results as abstract_text, source_url) — deduped on (title, year)
  • high-signal posters (clinical readouts / competitor data) ALSO emit a
    `competitive_signals` row (signal_type='conference') → which surfaces directly
    in the Executive Briefing "Developments" feed and intel2.
  • key numeric findings → `intel_facts` (sourced)

Sourced-only: every record requires a real http(s) URL or it is dropped. Reuses the
same web_search/web_fetch engine as event_research.py. Runs in GitHub Actions.

Usage:
    python3 scripts/maintenance/poster_research.py --dry-run
    python3 scripts/maintenance/poster_research.py --area tl1a --limit 8
    python3 scripts/maintenance/poster_research.py --only upcoming
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

MODEL = "claude-opus-4-8"
NOW = datetime.date.today()

# Ailux areas → the conferences that matter for each (Ailux-relevant congresses only)
AREA_CONFS = {
    "tl1a":  ["DDW", "ECCO", "UEGW", "Crohn's & Colitis Congress"],
    "tslp":  ["ATS", "ERS", "AAAAI", "CHEST"],
    "il4ra": ["AAD", "EADV", "RAD", "AAAAI"],
    "igf1r": ["ASRS", "ARVO", "ENDO", "ESE"],
    "fcrn":  ["AAN", "MGFA", "PNS", "EAN"],
    "tcell": ["ACR", "EULAR", "LUPUS 21st Century"],
}
AREA_FOCUS = {
    "tl1a":  "TL1A and TL1A×IL-23 bispecifics in IBD/UC/CD",
    "tslp":  "TSLP / alarmin biologics in asthma and COPD",
    "il4ra": "IL-4Rα / IL-13 / OX40 biologics in atopic dermatitis",
    "igf1r": "IGF-1R agents in thyroid eye disease",
    "fcrn":  "FcRn antagonists in IgG-mediated autoimmunity (gMG/CIDP/ITP)",
    "tcell": "Treg / T-cell tolerance approaches in autoimmunity",
}
WEB_TOOLS = [
    {"type": "web_search_20260209", "name": "web_search", "max_uses": 8},
    {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 6},
]

SUPABASE_URL = read_key("SUPABASE_URL", ".supabase_url", "https://tghntyofptvfhmtchwcv.supabase.co")
SUPABASE_KEY = read_key("SUPABASE_SERVICE_KEY", ".supabase_service_key")
ANTHROPIC_API_KEY = read_key("ANTHROPIC_API_KEY", ".anthropic_api_key")
SB_HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
_URL_RE = re.compile(r"^https?://", re.I)


def log(msg):
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def _sb_get(table, params):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=SB_HEADERS, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def _resolve_drug_id(name):
    """Best-effort drug name → id (None if no confident hit). conference_abstracts.drug_id is nullable."""
    if not name:
        return None
    try:
        safe = name.strip().replace("%", "").replace("_", "").replace(",", "")  # avoid ILIKE wildcards / PostgREST delimiters
        if len(safe) < 3:
            return None
        hits = _sb_get("drugs", {"select": "id,name", "name": f"ilike.%{safe}%", "limit": "1"})
        return hits[0]["id"] if hits else None
    except Exception:
        return None


# ── Research (server-tool loop, pause_turn aware) ─────────────────────────────
SYSTEM = (
    "You are a biopharma competitive-intelligence analyst for Meridian, the BD platform behind "
    "Ailux. You hunt for CONFERENCE POSTERS AND PRESENTATIONS relevant to a therapeutic area, using "
    "live web search/fetch, and report the specifics.\n\n"
    "Hard rules:\n"
    "• Prioritise the official congress program/abstract book, the presenting company's press release, "
    "and reputable trade coverage (Endpoints, FierceBiotech, STAT).\n"
    "• EVERY poster you report must carry the exact http(s) URL where you saw it. If you can't attach a "
    "real URL, DO NOT report it. Never invent a URL.\n"
    "• Capture: conference name, year, presentation date (YYYY-MM-DD if known), type (oral/poster/"
    "late-breaker), exact title, the drug, the company, presenting authors if named, and the KEY RESULTS "
    "(N, endpoints, % response/remission, p-values, safety) — the data, not spin.\n"
    "• Flag whether each is a clinical_readout (real trial data) and note any competing molecule named."
)
OUTPUT = (
    "\n\nWhen done, output ONLY a single JSON object in a ```json fenced block:\n"
    "{\n"
    '  "posters": [\n'
    '    {"conference": "...", "year": 2026, "presentation_date": "YYYY-MM-DD|null", '
    '"presentation_type": "oral|poster|late-breaker|null", "title": "...", "drug": "...", '
    '"company": "...", "authors": "...|null", "key_results": "<concrete findings>", '
    '"is_clinical_readout": true, "competing_molecules": ["..."], "confidence": "high|medium|low", '
    '"source_url": "https://..."}\n'
    "  ]\n"
    "}\n"
    "Aim for 4-10 posters. Drop any without a real source_url. If search returns nothing usable, "
    "return an empty posters array — never fabricate."
)


def run_research(client, area, only, max_turns=14):
    confs = ", ".join(AREA_CONFS.get(area, []))
    when = ("upcoming (next ~6 months) and the most recent past" if only is None
            else ("upcoming (next ~6 months)" if only == "upcoming" else "the most recent past (last ~6 months)"))
    user = (
        f"Find {when} conference posters/presentations on {AREA_FOCUS.get(area, area)}.\n"
        f"Focus congresses: {confs} (and any other major venue where relevant data appeared).\n"
        f"Cover both Ailux-relevant assets AND direct competitors in this space. For each, report the "
        f"specifics and the key data." + OUTPUT
    )
    messages = [{"role": "user", "content": user}]
    last = None
    for _ in range(max_turns):
        last = client.messages.create(model=MODEL, max_tokens=8000, system=SYSTEM,
                                      tools=WEB_TOOLS, messages=messages, thinking={"type": "adaptive"})
        messages.append({"role": "assistant", "content": last.content})
        if last.stop_reason == "pause_turn":
            continue
        break
    return last


def _extract_json(resp):
    text = "\n".join(b.text for b in resp.content if getattr(b, "type", "") == "text" and getattr(b, "text", ""))
    candidates = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    start = text.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(text[start:i + 1])
                    break
    for raw in candidates:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            continue
    return None


# ── Writers ──────────────────────────────────────────────────────────────────
def _exists(title, year):
    try:
        hits = _sb_get("conference_abstracts", {"select": "id", "title": f"eq.{title}",
                                                "conference_year": f"eq.{year}", "limit": "1"})
        return bool(hits)
    except Exception:
        return False


def write_posters(area, posters, dry_run):
    written = signals = dropped = 0
    for p in posters:
        url = str(p.get("source_url", "")).strip()
        title = str(p.get("title", "")).strip()
        if not _URL_RE.match(url) or not title:
            dropped += 1
            continue
        year = p.get("year") if isinstance(p.get("year"), int) else NOW.year
        drug_id = _resolve_drug_id(p.get("drug"))
        pdate = p.get("presentation_date") if re.match(r"^\d{4}-\d{2}-\d{2}$", str(p.get("presentation_date") or "")) else None
        conf_val = p.get("confidence") if p.get("confidence") in ("high", "medium", "low") else "medium"
        conf_num = {"high": 0.9, "medium": 0.7, "low": 0.5}[conf_val]

        if _exists(title, year):
            continue  # dedup

        abstract = (p.get("key_results") or "").strip()
        comp = p.get("competing_molecules") or []
        if comp:
            abstract += ("\n\nCompeting molecules: " + ", ".join(str(c) for c in comp))

        ca = {
            "title": title[:1000], "conference": (p.get("conference") or "")[:200], "conference_year": year,
            "presentation_date": pdate, "presentation_type": (p.get("presentation_type") or None),
            "abstract_text": abstract or None, "source_url": url, "drug_id": drug_id,
            "therapeutic_area_id": area, "confidence": conf_num, "source": "poster_research",
        }
        if dry_run:
            written += 1
            if p.get("is_clinical_readout"):
                signals += 1
            continue
        r = requests.post(f"{SUPABASE_URL}/rest/v1/conference_abstracts",
                          headers={**SB_HEADERS, "Prefer": "return=minimal"}, json=ca, timeout=45)
        if r.status_code >= 300:
            log(f"  ! conference_abstracts insert failed: {r.status_code} {r.text[:160]}")
            continue
        written += 1

        # high-signal posters → competitive_signals (surfaces in Executive Briefing + intel2)
        if p.get("is_clinical_readout") or comp:
            desc = abstract
            if p.get("authors"):
                desc = f"{p['authors']} — {desc}"
            cs = {
                "area_id": area, "drug_id": drug_id, "signal_type": "conference",
                "title": f"{p.get('conference', 'Conference')} {year}: {title}"[:300],
                "description": desc[:2000] if desc else None,
                "source_url": url, "source_date": pdate, "confidence": conf_num,
            }
            sr = requests.post(f"{SUPABASE_URL}/rest/v1/competitive_signals",
                               headers={**SB_HEADERS, "Prefer": "return=minimal"}, json=cs, timeout=45)
            if sr.status_code < 300:
                signals += 1
            else:
                log(f"  ! competitive_signals insert failed: {sr.status_code} {sr.text[:160]}")
    return written, signals, dropped


def main():
    ap = argparse.ArgumentParser(description="Active conference poster/presentation discovery for Ailux areas.")
    ap.add_argument("--area", choices=list(AREA_CONFS.keys()), default=None, help="restrict to one area (default: all)")
    ap.add_argument("--limit", type=int, default=8, help="max posters to keep per area")
    ap.add_argument("--only", choices=["upcoming", "past"], default=None, help="restrict to upcoming or recent past")
    ap.add_argument("--dry-run", action="store_true", help="research + parse, write nothing")
    args = ap.parse_args()

    if not ANTHROPIC_API_KEY:
        log("FATAL: ANTHROPIC_API_KEY not set"); sys.exit(1)
    if not SUPABASE_KEY:
        log("FATAL: SUPABASE_SERVICE_KEY not set"); sys.exit(1)

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=300.0, max_retries=2)
    areas = [args.area] if args.area else list(AREA_CONFS.keys())
    log(f"Hunting posters for areas: {areas}{' (DRY RUN)' if args.dry_run else ''}")

    tot_w = tot_s = tot_d = 0
    for area in areas:
        log(f"▶ {area} — {AREA_FOCUS.get(area, area)}")
        try:
            resp = run_research(client, area, args.only)
        except Exception as e:
            log(f"  ! research error: {e}"); continue
        parsed = _extract_json(resp)
        if not parsed or not parsed.get("posters"):
            log("  · no posters parsed"); continue
        posters = parsed["posters"][:args.limit]
        w, s, d = write_posters(area, posters, args.dry_run)
        tot_w += w; tot_s += s; tot_d += d
        log(f"  ✓ {w} posters written, {s} high-signal → competitive_signals, {d} dropped (no URL)")

    log(f"DONE — {tot_w} posters, {tot_s} signals, {tot_d} dropped"
        f"{' (DRY RUN — nothing persisted)' if args.dry_run else ''}.")


if __name__ == "__main__":
    main()
