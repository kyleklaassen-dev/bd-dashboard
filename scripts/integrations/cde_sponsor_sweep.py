#!/usr/bin/env python3
"""
cde_sponsor_sweep.py — China NMPA/CDE sponsor-sweep matcher + writer for `china_trials`.

WHY THIS EXISTS
  The 15 China-developed TL1A/IL-23 competitors are invisible to ClinicalTrials.gov,
  the WHO ICTRP search endpoint is broken upstream, and ChiCTR is mostly academic.
  The registry where Chinese company drug trials actually live is the NMPA/CDE
  platform (chinadrugtrials.org.cn). It cannot be reached by curl or a GitHub
  runner (JS SPA + egress block) — only by a real browser (Cowork / Claude-in-Chrome).
  Companies there register under their OWN internal codes (e.g. Qyuns = QX###N),
  not the Western pipeline codes Meridian tracks, so we sweep by SPONSOR and match.

TWO-PHASE DESIGN
  1. COLLECT (browser, Cowork-only): for each company in china_sponsors.json, open
     the CDE advanced query (二级查询), type the company's cn[] term into the 申请人
     field, search, page through, and dump every result row to a JSON list:
        [{"company_id","ctr","status","drug_name","indication","title"}, ...]
  2. PROCESS (this script, deterministic, idempotent): match each row to a Meridian
     asset and upsert confirmed matches into china_trials; report NEW filings and
     lower-confidence REVIEW candidates. resolve-or-skip — never fabricates a match.

MATCHING
  * CODE match (high confidence -> auto-write): the row's drug_name/title contains
    one of the asset's codes/aliases (normalized: lower, strip spaces/hyphens and
    the CN dosage suffix 注射液/片/胶囊...).
  * HEURISTIC (review only -> NOT written): row.company_id == asset.company_id AND an
    indication keyword overlaps the asset's indication_kw profile. Surfaced for a
    human to confirm (handles the different-internal-code case) but never auto-written.

USAGE
  python3 scripts/integrations/cde_sponsor_sweep.py --ingest rows.json [--dry-run]
  python3 scripts/integrations/cde_sponsor_sweep.py --report      # show current china_trials
Env:    SUPABASE_URL, SUPABASE_SERVICE_KEY
Config: data/china_sponsors.json
"""
import os, sys, json, re, argparse
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE_DIR, "src"))
from database import client as c  # shared Supabase REST client (urllib, no deps)

NOW = datetime.now(timezone.utc).isoformat()
CONFIG = os.path.join(BASE_DIR, "data", "china_sponsors.json")
SESSION = f"cde-sweep-{datetime.now(timezone.utc):%Y%m%d}"
SRC_URL = "https://www.chinadrugtrials.org.cn/clinicaltrials.searchlist.dhtml"
_SUFFIX = re.compile(r"(注射液|注射用|片剂|片|胶囊|溶液|缓释|口服液)")


def _norm(s: str) -> str:
    """Lowercase, drop CN dosage suffixes, strip non-alphanumerics -> code-comparable."""
    s = _SUFFIX.sub("", s or "")
    return re.sub(r"[^a-z0-9]", "", s.lower())


def load_config():
    with open(CONFIG, encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg["assets"]


def match_row(row, assets):
    """Return (drug_id, matched_term, confidence) or (None, reason, 'none')."""
    hay = _norm(row.get("drug_name", "")) + " " + _norm(row.get("title", ""))
    hay_raw = (row.get("drug_name", "") or "") + " " + (row.get("title", "") or "")
    # 1) CODE match (high confidence)
    for a in assets:
        for code in a["codes"]:
            if _norm(code) and _norm(code) in hay:
                return a["drug_id"], code, "code"
    # 2) HEURISTIC (review only): same sponsor + indication keyword overlap
    cid = row.get("company_id")
    ind = (row.get("indication", "") or "") + hay_raw
    for a in assets:
        if a.get("company_id") == cid:
            for kw in a.get("indication_kw", []):
                if kw and kw in ind:
                    return a["drug_id"], f"heuristic:{kw}", "review"
    return None, "no-match", "none"


def to_china_trial(row, drug_id, matched_term, cfg_company_en):
    return {
        "trial_id": row["ctr"],
        "registry": "NMPA/CDE",
        "drug_id": drug_id,
        "matched_term": matched_term,
        "public_title": row.get("title"),
        "scientific_title": row.get("title"),
        "condition": row.get("indication"),
        "intervention": row.get("drug_name"),
        "sponsor": cfg_company_en,
        "recruitment_status": row.get("status"),
        "registration_date": None,
        "source_url": SRC_URL,
        "session_label": SESSION,
        "fetched_at": NOW,
    }


def ingest(path, dry_run=False):
    assets = load_config()
    cfg = json.load(open(CONFIG, encoding="utf-8"))
    en = {c0["company_id"]: c0["en"] for c0 in cfg["companies"]}
    rows = json.load(open(path, encoding="utf-8"))
    existing = {r["trial_id"] for r in c.select_all("china_trials", {"select": "trial_id"})}

    writes, review, skipped, new = [], [], 0, []
    for r in rows:
        did, term, conf = match_row(r, assets)
        if conf == "code":
            wt = to_china_trial(r, did, term, en.get(r.get("company_id"), r.get("company_id")))
            writes.append(wt)
            if r["ctr"] not in existing:
                new.append((r["ctr"], did, r.get("drug_name"), r.get("indication")))
        elif conf == "review":
            review.append((r["ctr"], did, term, r.get("drug_name"), r.get("indication")))
        else:
            skipped += 1

    print(f"rows={len(rows)}  code-matches={len(writes)}  review-candidates={len(review)}  skipped={skipped}")
    if writes:
        print("\n=== CONFIRMED (code match) -> china_trials ===")
        for w in writes:
            flag = " [NEW]" if w["trial_id"] in [n[0] for n in new] else ""
            print(f"  {w['trial_id']}  {w['drug_id']:10s}  {w['intervention']}{flag}")
    if review:
        print("\n=== REVIEW (sponsor+indication heuristic — NOT written, confirm manually) ===")
        for ctr, did, term, dn, ind in review:
            print(f"  {ctr}  ?{did:10s}  {term}  | {dn} | {ind}")

    if not dry_run and writes:
        for i in range(0, len(writes), 200):
            code, body, _ = c.insert("china_trials", writes[i:i + 200], on_conflict="trial_id")
            if code >= 300:
                print(f"  ! write batch HTTP{code}: {str(body)[:200]}")
        print(f"\nwrote/upserted {len(writes)} rows ({len(new)} new) into china_trials")
    elif dry_run:
        print("\n[DRY RUN] no writes")
    return writes, review, new


def report():
    rows = c.select_all("china_trials", {"select": "trial_id,drug_id,intervention,condition,recruitment_status,registry", "order": "fetched_at.desc"})
    print(f"china_trials: {len(rows)} rows")
    for r in rows[:50]:
        print(f"  {r['trial_id']}  {str(r.get('drug_id')):10s}  {r.get('registry')}  {r.get('intervention')}  | {r.get('condition')}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ingest", metavar="rows.json")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.report:
        report()
    elif a.ingest:
        ingest(a.ingest, dry_run=a.dry_run)
    else:
        ap.print_help()
