#!/usr/bin/env python3
"""
content_verifier.py — Tier-4 trust layer: CONTENT confirmation
================================================================
The Source Verifier (Tier 3) proves a URL is real, live, specific, and not
fabricated. It cannot tell whether the page actually SAYS the claim. This script
closes that gap — the difference between "the URL exists" and "the URL proves the
fact" — which is exactly what the veligrotug "gMG" hallucination exploited.

For each (claim, source) pair in `drug_sources`, it:
  1. fetches the source page and extracts readable text
  2. asks Claude whether the page SUPPORTS the specific claim_value
  3. writes drug_sources.content_confirms_claim + url_status + url_last_checked

Decision policy (deliberately conservative — never punish a real molecule for a
page we simply could not read):
  • supports        → content_confirms_claim = TRUE,  confidence='confirmed'
  • contradicts/absent on a readable page → content_confirms_claim = FALSE,
                       opens a governance_violation (a veligrotug-class error)
  • page unreadable / JS-only / paywalled / fetch failed → url_status='unverifiable',
                       content_confirms_claim left unchanged (NOT set false)

Usage:
  python scripts/content_verifier.py                 # verify unverified drug_sources
  python scripts/content_verifier.py --limit 20
  python scripts/content_verifier.py --dry-run       # fetch + judge, no DB writes
  python scripts/content_verifier.py --recheck       # also re-verify already-checked rows
"""
import os, sys, re, html, argparse, datetime
import requests

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from _common import load_credentials, sb_headers  # noqa: E402
import _db                                         # noqa: E402
import ai.client as ai_client                      # noqa: E402
from ai.client import PromptConfig                 # noqa: E402

SUPABASE_URL, SUPABASE_KEY, ANTHROPIC_API_KEY = load_credentials()
_db.init_db(SUPABASE_URL, SUPABASE_KEY)
ai_client.setup(ANTHROPIC_API_KEY)

MODEL = "claude-haiku-4-5-20251001"   # cheap + fast: a judging task, not generation

UA = {"User-Agent": "Mozilla/5.0 (compatible; MeridianSourceVerifier/1.0)"}
FABRICATED = re.compile(r"(/search\?term=|/search\?q=|google\.com/search|clinicaltrials\.gov/search|example\.com|placeholder\.)", re.I)


def log(m): print(m, flush=True)


def fetch_text(url):
    """Return (text, status). status in: ok | fabricated | http_4xx/5xx | error | empty."""
    if FABRICATED.search(url or ""):
        return None, "fabricated"
    try:
        r = requests.get(url, headers=UA, timeout=20, allow_redirects=True)
        if r.status_code >= 400:
            return None, f"http_{r.status_code}"
        raw = r.text or ""
        # strip scripts/styles + tags, unescape, collapse whitespace
        raw = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", raw)
        text = re.sub(r"(?s)<[^>]+>", " ", raw)
        text = html.unescape(re.sub(r"\s+", " ", text)).strip()
        if len(text) < 200:            # JS-rendered shell / paywall / empty
            return None, "empty"
        return text[:8000], "ok"
    except Exception as e:
        return None, f"error:{type(e).__name__}"


JUDGE_SYS = (
    "You are a meticulous biopharma fact-checker. You are given a CLAIM and the visible "
    "TEXT of its cited web page. Decide whether the page SUPPORTS the claim.\n"
    "Reply ONLY with compact JSON: {\"verdict\":\"supports|contradicts|absent|unreadable\","
    "\"evidence\":\"<=160 chars quoting or paraphrasing the page\"}.\n"
    "- supports: the page clearly states or directly implies the claim.\n"
    "- contradicts: the page states something incompatible with the claim.\n"
    "- absent: the page is readable and on-topic but does NOT contain the claim.\n"
    "- unreadable: the page text is a shell/login/error with no real content.\n"
    "Be strict: a drug's indication, target, stage, deal terms must actually appear."
)

_JUDGE_CFG = PromptConfig(name="content_verifier_judge", system=JUDGE_SYS, model=MODEL, max_tokens=200)


def judge(claim_type, claim_value, page_text):
    result = ai_client.run_json(_JUDGE_CFG, f"CLAIM ({claim_type}): {claim_value}\n\nPAGE TEXT:\n{page_text}")
    if not result.ok:
        return "unreadable", "judge_error: invalid JSON response"
    d = result.data
    return d.get("verdict", "unreadable"), (d.get("evidence") or "")[:160]


def open_violation(row, verdict, evidence):
    _db.sb_post("governance_violations", {
        "table_name": "drug_sources", "row_id": str(row["id"]),
        "rule_name": "source_does_not_support_claim",
        "description": f"[{verdict}] {row.get('drug_id')} / {row.get('claim_type')}: "
                       f"'{str(row.get('claim_value'))[:80]}' — source content does not support the claim. "
                       f"Evidence: {evidence}. URL: {row.get('source_url')}",
        "resolved": False})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--recheck", action="store_true")
    args = ap.parse_args()

    params = {"select": "id,drug_id,claim_type,claim_value,source_url,content_confirms_claim",
              "source_url": "not.is.null", "limit": str(args.limit)}
    if not args.recheck:
        params["content_confirms_claim"] = "is.null"
    rows = _db.sb_get("drug_sources", params)
    log(f"Content-verifying {len(rows)} drug_sources claims (model={MODEL}, dry_run={args.dry_run})")

    tally = {"supports": 0, "contradicts": 0, "absent": 0, "unreadable": 0, "fabricated": 0}
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    for row in rows:
        text, status = fetch_text(row["source_url"])
        if status == "fabricated":
            verdict, evidence = "contradicts", "fabricated source URL"
        elif text is None:
            verdict, evidence = "unreadable", status
        else:
            verdict, evidence = judge(row["claim_type"], row["claim_value"], text)
        tally[verdict] = tally.get(verdict, 0) + 1
        mark = {"supports": "✓ confirms", "contradicts": "✗ CONTRADICTS",
                "absent": "✗ not on page", "unreadable": "· unverifiable"}[verdict]
        log(f"  {mark}  {row['drug_id']}/{row['claim_type']}  {str(row['source_url'])[:54]}  ({evidence[:60]})")

        if args.dry_run:
            continue
        patch = {"url_last_checked": now, "url_status": status}
        if verdict == "supports":
            patch["content_confirms_claim"] = True
            patch["confidence"] = "confirmed"
        elif verdict in ("contradicts", "absent"):
            patch["content_confirms_claim"] = False
            patch["confidence"] = "unverified"
            open_violation(row, verdict, evidence)
        # 'unreadable' → leave content_confirms_claim unchanged (do NOT punish)
        _db.sb_patch("drug_sources", patch, {"id": f"eq.{row['id']}"})

    log("\n=== Content verification summary ===")
    for k, v in tally.items():
        log(f"  {k:12} {v}")
    bad = tally.get("contradicts", 0) + tally.get("absent", 0)
    log(f"\n{bad} claim(s) whose source does NOT support them — opened as governance_violations for review.")
    # exit non-zero only on a true contradiction (a real data error), so the job alerts
    sys.exit(1 if tally.get("contradicts", 0) else 0)


if __name__ == "__main__":
    main()
