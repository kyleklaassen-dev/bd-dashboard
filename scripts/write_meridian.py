#!/usr/bin/env python3
"""
Meridian Writer — GitHub Actions edition
Reads biopharma intel from Supabase (last 24h), generates a full Meridian HTML
briefing using Claude Opus (two-pass: editorial plan → full draft), and commits
meridian_today.html to GitHub Pages.
Runs 6:30 AM ET Mon–Sat (10:30 UTC).
"""

import os, json, datetime, base64, re, time, hashlib
import requests
import anthropic

# Patient intelligence context (co-equal intelligence layer)
try:
    from patient_intelligence_module import PATIENT_INTELLIGENCE_CONTEXT, build_patient_context_block
    PATIENT_INTEL_AVAILABLE = True
except ImportError:
    PATIENT_INTELLIGENCE_CONTEXT = ""
    build_patient_context_block = lambda items: ""
    PATIENT_INTEL_AVAILABLE = False

# ── Credentials ─────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SUPABASE_URL      = os.environ["SUPABASE_URL"]
SUPABASE_KEY      = os.environ["SUPABASE_SERVICE_KEY"]
GITHUB_TOKEN      = os.environ["GITHUB_TOKEN"]
GITHUB_REPO       = os.environ.get("GITHUB_REPO", "kyleklaassen-dev/bd-dashboard")

# PUBLIC anon key for the in-issue feedback widget (write-only to meridian_feedback via
# RLS; same key already embedded client-side in index.html). NOT the service key — never
# put the service key in a deployed page. Env override allowed.
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY",
    "sb_publishable_3GLfZ7b9Tjp9RFRcc4YZew_ov-fY7dI")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SB_HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
}

# ── Pre-publish fact-check gate ───────────────────────────────────────────────
# A fact only earns a place in the Issue if it isn't backed by a FABRICATED source.
# This is the gate that would have stopped the veligrotug "gMG" line at the door:
# its catalyst carried a clinicaltrials.gov/search?term= URL (an invented citation).
# Keep the same patterns the Source Verifier uses. We DROP rows whose source_url is
# present-but-fabricated; we KEEP rows with no source (real-but-unsourced is fine —
# we never want to lose a real molecule like CLD-423), and log everything dropped.
import re as _re
_FABRICATED_SOURCE = _re.compile(
    r"(/search\?term=|/search\?q=|google\.com/search|clinicaltrials\.gov/search"
    r"|example\.com|placeholder\.|/drug-name-here|localhost|127\.0\.0\.1)", _re.I)

def _is_fabricated_source(url):
    return bool(url) and bool(_FABRICATED_SOURCE.search(str(url)))

_FACT_CHECK = {"dropped": [], "checked": 0}

def fact_check_filter(rows, label, url_field="source_url"):
    """Drop rows whose source_url is fabricated; keep the rest. Records drops."""
    kept = []
    for r in rows:
        _FACT_CHECK["checked"] += 1
        if _is_fabricated_source(r.get(url_field)):
            _FACT_CHECK["dropped"].append({"kind": label, "row": r.get("label") or r.get("headline") or r.get("id"), "url": r.get(url_field)})
        else:
            kept.append(r)
    n = len(rows) - len(kept)
    if n:
        log(f"  ⚖ fact-check: dropped {n} {label} with fabricated source URLs (kept {len(kept)})")
    return kept

def build_verification_cautions():
    """Pull claims the Content Verifier marked content_confirms_claim=FALSE and turn
    them into an explicit 'do NOT state these' block for the writer's system prompt.
    Claim-level (not drug-level), so a real molecule keeps its confirmed facts while
    a single disconfirmed claim (e.g. veligrotug→gMG) is withheld."""
    MEANINGFUL = "(mechanism,indication,stage,target,partnership,approval,deal)"
    try:
        rows = requests.get(f"{SUPABASE_URL}/rest/v1/drug_sources",
            headers=SB_HEADERS,
            params={"select": "drug_id,claim_type,claim_value",
                    "content_confirms_claim": "is.false",
                    "claim_type": f"in.{MEANINGFUL}",
                    "limit": "60"}, timeout=15).json()
    except Exception as e:
        log(f"  verification-cautions fetch failed (non-fatal): {e}")
        return ""
    if not rows:
        return ""
    lines = [f"  • {r['drug_id']}: do NOT state \"{str(r.get('claim_value'))[:120]}\" "
             f"({r.get('claim_type')}) — its cited source did not confirm it."
             for r in rows]
    log(f"  ⚖ Injected {len(rows)} verification cautions into the writer prompt")
    return ("\n\nVERIFICATION CAUTIONS — the following claims FAILED source confirmation "
            "(the cited page does not support them). Do NOT state them as fact in the Issue; "
            "omit them or note them only as unverified:\n" + "\n".join(lines))


def build_reader_feedback_block(days_back=30):
    """Close the feedback loop: pull Kyle's in-issue feedback (meridian_feedback) from
    the last N days and turn it into explicit editorial guidance for the writer.

    Section 👎 / negative notes → tighten or rethink that kind of section.
    Section 👍 → keep doing it. Comments are treated as direct editorial instructions.
    Reads with the service key (RLS lets only service/authenticated read)."""
    try:
        cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=days_back)).strftime("%Y-%m-%d")
        rows = requests.get(f"{SUPABASE_URL}/rest/v1/meridian_feedback",
            headers=SB_HEADERS,
            params={"select": "section_label,vote,comment,selected_text,created_at",
                    "created_at": f"gte.{cutoff}",
                    "order": "created_at.desc", "limit": "200"}, timeout=15).json()
    except Exception as e:
        log(f"  reader-feedback fetch failed (non-fatal): {e}")
        return ""
    if not rows or not isinstance(rows, list):
        return ""
    from collections import defaultdict
    votes = defaultdict(lambda: [0, 0])   # label -> [up, down]
    comments = []
    for r in rows:
        lab = (r.get("section_label") or "(unlabeled)").strip()
        if r.get("vote") == "up":   votes[lab][0] += 1
        elif r.get("vote") == "down": votes[lab][1] += 1
        c = (r.get("comment") or "").strip()
        if c:
            sel = (r.get("selected_text") or "").strip()
            comments.append((lab, c, sel))
    lines = []
    liked = [f'"{l}" ({v[0]}↑)' for l, v in votes.items() if v[0] > v[1] and v[0] > 0]
    disliked = [f'"{l}" ({v[1]}↓)' for l, v in votes.items() if v[1] > 0 and v[1] >= v[0]]
    if liked:
        lines.append("Sections the reader marked HELPFUL (keep this kind of content/treatment): " + "; ".join(liked[:12]))
    if disliked:
        lines.append("Sections the reader marked NOT USEFUL (tighten, rethink, or cut this kind of section): " + "; ".join(disliked[:12]))
    for lab, c, sel in comments[:25]:
        if sel:
            lines.append(f'On "{lab}" — re: “{sel[:120]}” — the reader wrote: "{c[:300]}"')
        else:
            lines.append(f'On "{lab}" — the reader wrote: "{c[:300]}"')
    if not lines:
        return ""
    log(f"  ✎ Injected reader feedback: {len(votes)} rated sections, {len(comments)} comments")
    return ("\n\nREADER FEEDBACK (from the actual reader of this briefing — treat as direct "
            "editorial instruction, higher priority than generic style rules; if a comment "
            "conflicts with a default, follow the comment):\n- " + "\n- ".join(lines))


def fact_check_report():
    """Log a summary and open a governance_violation if anything was dropped."""
    d = _FACT_CHECK["dropped"]
    log(f"⚖ Fact-check gate: {_FACT_CHECK['checked']} sourced facts checked, {len(d)} dropped for fabricated sources.")
    if d:
        try:
            requests.post(f"{SUPABASE_URL}/rest/v1/governance_violations",
                headers={**SB_HEADERS, "Prefer": "return=minimal"},
                json={"table_name": "meridian_issue_factcheck", "row_id": datetime.datetime.utcnow().strftime("%Y-%m-%d"),
                      "rule_name": "fabricated_source_excluded_from_issue",
                      "description": "Pre-publish fact-check dropped facts with fabricated source URLs before the Issue was written: "
                                     + "; ".join(f"[{x['kind']}] {str(x['row'])[:50]} ({str(x['url'])[:50]})" for x in d[:10]),
                      "resolved": False}, timeout=15)
        except Exception as e:
            log(f"  fact-check governance log failed (non-fatal): {e}")

def audit_draft_against_db(html, drugs):
    """POST-draft consistency gate. Catches the SPY072-class error: the finished
    Issue describing a DB-monospecific asset as a 'bispecific' (or a DB-bispecific
    asset as 'monospecific'). The pre-write gates check sources; this checks the
    PROSE against the canonical drugs table after the model has written it.

    Flag, don't silently rewrite — surfaces a governance_violation for morning
    review. Set MERIDIAN_FACTCHECK_STRICT=1 to hard-block deploy on any flag.
    Returns the list of flags.
    """
    flags = []
    # In this house style "bispecific"/"monospecific" are used constantly as CATEGORY
    # nouns ("the bispecific premium", "monospecific TL1A comps"), so proximity to a
    # drug name means nothing. We only flag two rare, unambiguous constructions that
    # actually attribute a format TO a named asset:
    #   A) copula/apposition:  "<NAME> is/are/—/, (a|an|the) … <OPP>"   (within one clause)
    #   B) class membership:   "<OPP> class/programs/assets/antibodies/candidates … <NAME>"
    # Both negation-guarded so legitimate comparisons ("NAME, unlike the bispecific
    # class, is monospecific") don't trip. Validated: 0 false positives on a full issue.
    #
    # Run on visible text, not raw HTML (strip tags + unescape entities).
    text = _re.sub(r"<[^>]+>", " ", html)
    try:
        import html as _htmlmod
        text = _htmlmod.unescape(text)
    except Exception:
        pass
    text = _re.sub(r"\s+", " ", text)

    fmt = {}
    for d in drugs.values():
        tc = (d.get("target_class") or "").strip().lower()
        if tc not in ("monospecific", "bispecific"):
            continue
        for nm in (d.get("display_name"), d.get("name")):
            if nm and len(nm) >= 3:
                base = _re.sub(r"\s*\(.*?\)\s*$", "", nm).strip()
                if base:
                    fmt[base] = tc
    _NEG = _re.compile(r"(?:not|n[’']t|unlike|rather than|versus|\bvs\b|whereas|distinct from|"
                       r"as opposed to|isn\W?t|never)", _re.I)
    for nm, tc in fmt.items():
        opp = "bispecific" if tc == "monospecific" else "monospecific"
        n = _re.escape(nm)
        hit = None
        pat_A = rf"{n}\b[^.]{{0,6}}(?:is|are|=|—|,|:)\s+(?:a|an|the)\s+(?:[\w/×.-]+\s+){{0,3}}{opp}\b"
        pat_B = rf"{opp}\s+(?:class|programs?|assets?|antibodies|candidates?)\b[^.]{{0,90}}?\b{n}\b"
        for pat in (pat_A, pat_B):
            for m in _re.finditer(pat, text, _re.I):
                if not _NEG.search(m.group()):
                    hit = _re.sub(r"\s+", " ", m.group()).strip()
                    break
            if hit:
                break
        if hit:
            flags.append({"drug": nm, "db_format": tc, "draft_says": opp, "snippet": hit[:160]})
    if flags:
        for f in flags:
            log(f"  ⚠ DRAFT-AUDIT: '{f['drug']}' is {f['db_format']} in DB but the Issue "
                f"reads as {f['draft_says']} — “…{f['snippet']}…”")
        try:
            requests.post(f"{SUPABASE_URL}/rest/v1/governance_violations",
                headers={**SB_HEADERS, "Prefer": "return=minimal"},
                json={"table_name": "meridian_issue_factcheck",
                      "row_id": datetime.datetime.utcnow().strftime("%Y-%m-%d"),
                      "rule_name": "draft_format_contradicts_db",
                      "description": "Post-draft audit: Issue prose describes an asset's format "
                                     "inconsistently with the drugs table — "
                                     + "; ".join(f"{x['drug']} (DB={x['db_format']}, draft={x['draft_says']})" for x in flags[:10]),
                      "resolved": False}, timeout=15)
        except Exception as ex:
            log(f"  draft-audit governance log failed (non-fatal): {ex}")
        if os.environ.get("MERIDIAN_FACTCHECK_STRICT") == "1":
            raise RuntimeError(f"Draft-audit hard-block: {len(flags)} format contradiction(s) vs DB")
    else:
        log("  ✓ draft-audit: no asset format contradicts the drugs table")
    return flags


GH_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept":        "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def log(msg):
    ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


# ── Area display names ───────────────────────────────────────────────────────
AREA_NAMES = {
    "tl1a":  "TL1A / IBD",
    "tslp":  "TSLP / Severe Asthma",
    "il4ra": "IL-4Rα / Atopy",
    "igf1r": "IGF1R / Thyroid Eye Disease",
    "fcrn":  "FcRn / IgG Autoimmune",
    "tcell": "T-cell / Treg Therapy",
    "ibd":   "IBD (broad)",
    "respiratory": "Respiratory",
}


# ── Fetch intel from Supabase ────────────────────────────────────────────────
def fetch_recent_intel(hours_back=48):
    """Pull intel + area tags written (created) in the last N hours.

    Filters on created_at (when research.py wrote the row) rather than
    intel_date (the original event date). This handles the common case where
    research.py scrapes articles about historical deals — those rows have old
    intel_dates but were freshly added to the DB and should appear in today's issue.

    Falls back to a 96-hour window if the primary fetch returns fewer than 5 items,
    so a single missed nightly research run doesn't produce an empty issue.
    """
    cutoff_iso = (datetime.datetime.utcnow() - datetime.timedelta(hours=hours_back)).isoformat()
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/intel",
            headers=SB_HEADERS,
            params={
                "select": "id,intel_date,headline,body,source_url,source_name,importance,intel_type,created_at,intel_areas(area_id)",
                "created_at": f"gte.{cutoff_iso}",
                "order": "importance.desc,created_at.desc",
            },
        )
        items = r.json()
        for item in items:
            areas = item.pop("intel_areas", []) or []
            item["areas"] = [a["area_id"] for a in areas]
        log(f"Fetched {len(items)} intel items (created since {cutoff_iso[:10]})")

        # Fallback: if very sparse, extend window to 96h to survive a missed nightly run
        if len(items) < 5:
            cutoff_wide = (datetime.datetime.utcnow() - datetime.timedelta(hours=96)).isoformat()
            r2 = requests.get(
                f"{SUPABASE_URL}/rest/v1/intel",
                headers=SB_HEADERS,
                params={
                    "select": "id,intel_date,headline,body,source_url,source_name,importance,intel_type,created_at,intel_areas(area_id)",
                    "created_at": f"gte.{cutoff_wide}",
                    "order": "importance.desc,created_at.desc",
                },
            )
            items2 = r2.json()
            for item in items2:
                areas = item.pop("intel_areas", []) or []
                item["areas"] = [a["area_id"] for a in areas]
            if len(items2) > len(items):
                log(f"Sparse primary fetch ({len(items)} items) — extended to 96h: {len(items2)} items")
                items = items2

        return items
    except Exception as e:
        log(f"Intel fetch error: {e}")
        return []


def fetch_recent_deals(days_back=7):
    """Pull any deals logged in the last week."""
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=days_back)).strftime("%Y-%m-%d")
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/deals",
            headers=SB_HEADERS,
            params={
                "select": "deal_date,from_company,to_company,area_id,deal_type,upfront_usd_m,total_usd_m,headline,detail,source_url",
                "deal_date": f"gte.{cutoff}",
                "order": "deal_date.desc",
            },
        )
        deals = fact_check_filter(r.json(), "deal")
        log(f"Fetched {len(deals)} recent deals (fact-checked)")
        return deals
    except Exception as e:
        log(f"Deals fetch error: {e}")
        return []


def fetch_upcoming_catalysts():
    """Pull unresolved catalysts sorted by date."""
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/catalysts",
            headers=SB_HEADERS,
            params={
                "select": "catalyst_date,label,area_id,significance,catalyst_type,notes,source_url",
                "resolved": "eq.false",
                "sort_date": f"gte.{today}",
                "order": "sort_date.asc",
                "limit": "30",
            },
        )
        cats = fact_check_filter(r.json(), "catalyst")[:20]
        log(f"Fetched {len(cats)} upcoming catalysts (fact-checked)")
        return cats
    except Exception as e:
        log(f"Catalysts fetch error: {e}")
        return []


def fetch_drug_context():
    """Fetch all drugs and companies for context enrichment of intel items."""
    drugs, companies = {}, {}
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/drugs",
            headers=SB_HEADERS,
            params={
                "select": "id,name,display_name,company_id,stage,target,mechanism,overlap,overlap_rationale,ailux_angle,partner_company,partnership_type,partnership_verified,indication_short,target_class,modality",
                "limit": "500",
            },
        )
        for d in r.json():
            drugs[d["id"]] = d
            # Also index by lowercased name/display_name for matching
        log(f"Fetched {len(drugs)} drugs for context enrichment")
    except Exception as e:
        log(f"Drug context fetch error: {e}")

    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/companies",
            headers=SB_HEADERS,
            params={"select": "id,name,ticker", "limit": "200"},
        )
        for c in r.json():
            companies[c["id"]] = c
        log(f"Fetched {len(companies)} companies for context enrichment")
    except Exception as e:
        log(f"Company context fetch error: {e}")

    return drugs, companies


def fetch_ailux_position():
    """Fetch Ailux's competitive anchor from ailux_positions table."""
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/ailux_positions",
            headers=SB_HEADERS,
            params={"select": "*", "limit": "10"},
        )
        positions = r.json()
        log(f"Fetched {len(positions)} Ailux position records")
        return positions
    except Exception as e:
        log(f"Ailux position fetch error: {e}")
        return []


def fetch_recent_meridian_issues(n=7):
    """Fetch recent Meridian issues for editorial continuity.
    Returns title + intel_ids so we can surface what was covered and avoid repetition.
    Skips today's issue if already present."""
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/meridian_issues",
            headers=SB_HEADERS,
            params={
                "select": "issue_date,title,intel_ids",
                "order": "issue_date.desc",
                "limit": str(n + 1),
            },
        )
        issues = [i for i in r.json() if i.get("issue_date") != today][:n]
        log(f"Fetched {len(issues)} prior Meridian issues for continuity")
        return issues
    except Exception as e:
        log(f"Recent issues fetch error: {e}")
        return []


def fetch_company_signals():
    """Fetch current company-level intelligence bullets from the dashboard."""
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/company_signals",
            headers=SB_HEADERS,
            params={
                "select": "company_id,dir,signal_text,sort_order",
                "order": "company_id,sort_order",
            },
        )
        if r.status_code != 200:
            log(f"Company signals unavailable ({r.status_code}) — skipping")
            return []
        data = r.json()
        if not isinstance(data, list):
            log(f"Company signals unexpected response shape — skipping")
            return []
        log(f"Fetched {len(data)} company signals")
        return data
    except Exception as e:
        log(f"Company signals fetch error: {e}")
        return []


def fetch_graph_context():
    """
    Fetch entity_edges for graph-grounded competitive intelligence.

    Returns three structures:
      active_in:     {area_id: [company_ids]}  — who is in each area
      targets_edges: {entity_id: [target_ids]} — what each entity targets
      competes_with: [(subject_id, object_id)] — confirmed competitive pairs
    """
    active_in, targets_edges, competes_with = {}, {}, []

    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/entity_edges",
            headers=SB_HEADERS,
            params={
                "select": "subject_id,object_id",
                "predicate": "eq.ACTIVE_IN",
                "status": "eq.active",
                "limit": "500",
            },
        )
        if r.status_code == 200:
            for edge in r.json():
                area = edge.get("object_id")
                co   = edge.get("subject_id")
                if area and co:
                    active_in.setdefault(area, []).append(co)
            log(f"Graph: {sum(len(v) for v in active_in.values())} ACTIVE_IN edges across {len(active_in)} areas")
    except Exception as e:
        log(f"Graph ACTIVE_IN fetch error: {e}")

    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/entity_edges",
            headers=SB_HEADERS,
            params={
                "select": "subject_id,object_id",
                "predicate": "eq.TARGETS",
                "status": "eq.active",
                "limit": "300",
            },
        )
        if r.status_code == 200:
            for edge in r.json():
                subj = edge.get("subject_id")
                obj  = edge.get("object_id")
                if subj and obj:
                    targets_edges.setdefault(subj, []).append(obj)
            log(f"Graph: {len(targets_edges)} entities with TARGETS edges")
    except Exception as e:
        log(f"Graph TARGETS fetch error: {e}")

    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/entity_edges",
            headers=SB_HEADERS,
            params={
                "select": "subject_id,object_id",
                "predicate": "eq.COMPETES_WITH",
                "confidence_level": "eq.confirmed",
                "status": "eq.active",
                "limit": "200",
            },
        )
        if r.status_code == 200:
            seen = set()
            for e in r.json():
                subj, obj = e.get("subject_id"), e.get("object_id")
                if subj and obj:
                    pair = tuple(sorted([subj, obj]))
                    if pair not in seen:
                        seen.add(pair)
                        competes_with.append(pair)
            log(f"Graph: {len(competes_with)} unique COMPETES_WITH pairs (confirmed)")
    except Exception as e:
        log(f"Graph COMPETES_WITH fetch error: {e}")

    return active_in, targets_edges, competes_with


def fetch_catalyst_calendar(days_ahead=365):
    """
    Pull upcoming events from catalyst_calendar (structured BD timing table).
    Distinct from fetch_upcoming_catalysts() which reads the legacy catalysts table.
    Returns events ordered by expected_date ascending.
    """
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    future = (datetime.datetime.utcnow() + datetime.timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/catalyst_calendar",
            headers=SB_HEADERS,
            params={
                "select": (
                    "id,drug_id,company_id,event_type,event_name,"
                    "expected_date,expected_quarter,strategic_significance,"
                    "ailux_impact,description,source_url,confidence,is_past"
                ),
                "expected_date": f"gte.{today}",
                "is_past": "eq.false",
                "order": "expected_date.asc",
                "limit": "50",
            },
        )
        events = r.json() if r.status_code == 200 else []
        if not isinstance(events, list):
            log(f"Catalyst calendar unexpected response — skipping")
            return []
        log(f"Fetched {len(events)} catalyst calendar events (next {days_ahead}d)")
        return events
    except Exception as e:
        log(f"Catalyst calendar fetch error: {e}")
        return []


def fetch_bd_priority_companies():
    """
    Fetch top BD-priority companies via two signals:
      1. drug_competitive_scores: drugs with very_high competitive_relevance
      2. company_strategic_views: companies with view_type in competitive/acquisition_target
    Returns dict with keys 'scores' and 'views'.
    """
    scores, views = [], []

    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/drug_competitive_scores",
            headers=SB_HEADERS,
            params={
                "select": (
                    "drug_id,context_id,competitive_relevance,"
                    "total_competition_score,relevance_rationale"
                ),
                "competitive_relevance": "eq.very_high",
                "order": "total_competition_score.desc",
                "limit": "50",
            },
        )
        scores = r.json() if r.status_code == 200 and isinstance(r.json(), list) else []
        log(f"Fetched {len(scores)} very_high competitive relevance drug scores")
    except Exception as e:
        log(f"BD priority scores fetch error: {e}")

    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/company_strategic_views",
            headers=SB_HEADERS,
            params={
                "select": (
                    "company_id,view_type,strategic_score,"
                    "summary,ailux_relevance,key_assets"
                ),
                "view_type": "in.(competitive,acquisition_target)",
                "order": "strategic_score.desc.nullslast",
                "limit": "30",
            },
        )
        views = r.json() if r.status_code == 200 and isinstance(r.json(), list) else []
        log(f"Fetched {len(views)} competitive/acquisition_target strategic views")
    except Exception as e:
        log(f"BD priority views fetch error: {e}")

    return {"scores": scores, "views": views}


def fetch_patient_intelligence_stats():
    """
    Fetch top-level numeric patient intelligence columns (v65+).

    Returns a dict keyed by indication_name. Each value is a flat dict with:
        patient_count_us, patient_count_global, market_size_usd_bn,
        remission_rate_soc_pct, biologic_failure_rate_pct, unmet_need_score.

    Returns empty dict if the v65 migration has not been applied yet (columns
    will not exist → Supabase returns them as null for all rows, or PGRST204).
    Only rows with at least patient_count_us populated are included.
    """
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/indication_patient_intelligence",
            headers=SB_HEADERS,
            params={
                "select": (
                    "indication_name,patient_count_us,patient_count_global,"
                    "market_size_usd_bn,remission_rate_soc_pct,"
                    "biologic_failure_rate_pct,unmet_need_score"
                ),
                "limit": "50",
            },
        )
        if r.status_code != 200:
            log(f"Patient intelligence stats unavailable ({r.status_code}) — skipping")
            return {}
        rows = r.json()
        if not isinstance(rows, list):
            return {}
        result = {
            row["indication_name"]: row
            for row in rows
            if row.get("indication_name") and row.get("patient_count_us") is not None
        }
        log(f"Fetched patient intelligence numeric stats for {len(result)} indications")
        return result
    except Exception as e:
        log(f"Patient intelligence stats fetch error: {e}")
        return {}


def build_patient_stats_block(stats: dict) -> str:
    """
    Format the v65 numeric patient stats as a compact dashboard block.

    Used to inject market-size and unmet-need context into the LLM prompt
    without relying on JSON parsing or hallucinated statistics.
    Each row becomes one compact stats line.
    """
    if not stats:
        return "(Patient population stats not available — v65 migration may be pending)"

    lines = ["PATIENT POPULATION STATS (from indication_patient_intelligence — v65 columns):"]

    # Priority order for display
    priority = [
        "IBD (Inflammatory Bowel Disease)",
        "TL1A Target Area",
        "Ulcerative Colitis",
        "Crohn's Disease",
        "IL-4Rα Target Area",
        "Atopic Dermatitis",
        "TSLP Target Area",
        "FcRn Target Area",
        "IGF-1R Target Area",
        "Thyroid Eye Disease",
        "Generalized Myasthenia Gravis",
        "CIDP",
        "Autoimmune Diseases (Broad)",
        "Respiratory Diseases (Broad)",
    ]
    ordered = [k for k in priority if k in stats]
    ordered += sorted(k for k in stats if k not in priority)

    for name in ordered:
        row = stats[name]
        parts = []
        if row.get("patient_count_us"):
            us = int(row["patient_count_us"])
            parts.append(f"US ~{us:,}")
        if row.get("market_size_usd_bn"):
            mkt = float(row["market_size_usd_bn"])
            parts.append(f"${mkt:.1f}B market")
        if row.get("remission_rate_soc_pct") is not None:
            parts.append(f"{row['remission_rate_soc_pct']:.0f}% SoC remission")
        if row.get("biologic_failure_rate_pct") is not None:
            parts.append(f"{row['biologic_failure_rate_pct']:.0f}% biologic failure")
        if row.get("unmet_need_score") is not None:
            parts.append(f"unmet need {row['unmet_need_score']}/10")
        stat_line = " | ".join(parts) if parts else "(data pending)"
        lines.append(f"  {name}: {stat_line}")

    return "\n".join(lines)


def build_catalyst_calendar_block(events: list, days_window: int = 90) -> str:
    """
    Format catalyst_calendar events as a two-tier block:
      - Tier 1: events in the next `days_window` days (primary BD calendar)
      - Tier 2: events beyond that window up to 12 months (horizon scan)
    Used to inject structured BD timing into both prompt passes.
    """
    if not events:
        return "(No catalyst calendar events on record for the next 12 months)"

    cutoff = (datetime.datetime.utcnow() + datetime.timedelta(days=days_window)).strftime("%Y-%m-%d")
    near, far = [], []
    for ev in events:
        if ev.get("expected_date", "9999") <= cutoff:
            near.append(ev)
        else:
            far.append(ev)

    SIG_LABELS = {"P0": "CRITICAL", "P1": "HIGH", "P2": "MEDIUM", "P3": "LOW"}

    def _fmt(ev):
        sig = SIG_LABELS.get(ev.get("strategic_significance", ""), ev.get("strategic_significance", ""))
        drug = ev.get("drug_id", "?")
        company = ev.get("company_id", "?")
        etype = (ev.get("event_type") or "").replace("_", " ").upper()
        name = ev.get("event_name", "")
        date = ev.get("expected_date") or ev.get("expected_quarter", "?")
        impact = ev.get("ailux_impact", "")
        line = f"  [{sig}] {date} | {drug} ({company}) | {etype}\n  Name: {name}"
        if impact:
            line += f"\n  Ailux Impact: {impact}"
        return line

    lines = [f"BD CATALYST CALENDAR (next {days_window} days — primary timing anchor):"]
    if near:
        for ev in near:
            lines.append(_fmt(ev))
            lines.append("")
    else:
        lines.append(f"  (No catalysts in the next {days_window} days)")

    if far:
        lines.append(f"\nHORIZON CATALYSTS (>{days_window}d, next 12 months):")
        for ev in far[:15]:  # cap horizon to avoid prompt bloat
            lines.append(_fmt(ev))
            lines.append("")

    return "\n".join(lines)


def build_bd_priority_block(bd_data: dict) -> str:
    """
    Format BD priority company data (drug_competitive_scores + company_strategic_views)
    into a compact editorial block for both prompt passes.
    """
    scores = bd_data.get("scores", [])
    views  = bd_data.get("views", [])

    if not scores and not views:
        return "(BD priority company data unavailable)"

    lines = ["BD PRIORITY COMPANIES (from competitive scores + strategic views):"]

    if views:
        lines.append("\nTOP STRATEGIC COMPANIES (competitive + acquisition_target view_type, by strategic_score):")
        for v in views[:15]:
            co     = v.get("company_id", "?")
            vtype  = v.get("view_type", "?").replace("_", " ").upper()
            score  = v.get("strategic_score", "?")
            rel    = v.get("ailux_relevance", "")
            assets = ", ".join(v.get("key_assets") or [])
            line   = f"  {co} | {vtype} | score: {score}"
            if assets:
                line += f" | key assets: {assets}"
            if rel:
                line += f"\n    Relevance: {rel}"
            lines.append(line)

    if scores:
        lines.append("\nVERY_HIGH RELEVANCE DRUGS (direct competitive threats, by total_competition_score):")
        # Group by context_id (area) for readability
        by_area = {}
        for s in scores:
            area = s.get("context_id", "unknown")
            by_area.setdefault(area, []).append(s)
        for area in sorted(by_area):
            area_label = AREA_NAMES.get(area, area)
            lines.append(f"\n  {area_label}:")
            for s in sorted(by_area[area], key=lambda x: -(x.get("total_competition_score") or 0)):
                drug   = s.get("drug_id", "?")
                score  = s.get("total_competition_score", "?")
                rationale = s.get("relevance_rationale", "")
                line   = f"    {drug} | score: {score}"
                if rationale:
                    line += f" — {rationale}"
                lines.append(line)

    return "\n".join(lines)


def fetch_recent_trials():
    """Fetch clinical trial records updated in the last 30 days."""
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/trials",
            headers=SB_HEADERS,
            params={
                "select": "drug_id,trial_name,study_acronym,phase,status,n_enrollment,primary_completion_date,sponsor,indication,created_at",
                "created_at": f"gte.{cutoff}T00:00:00",
                "order": "created_at.desc",
                "limit": "60",
            },
        )
        trials = r.json() if r.status_code == 200 else []
        log(f"Fetched {len(trials)} recent trial records")
        return trials
    except Exception as e:
        log(f"Trials fetch error: {e}")
        return []


# ── Context enrichment ───────────────────────────────────────────────────────
def enrich_intel_with_drug_context(items, drugs, companies):
    """
    For each intel item, keyword-match against known drug names and company names.
    Append a compact DB-state block so the writer has live competitive context.
    """
    # Build lookup structures
    drug_lookup = {}   # lowercased token → drug record
    for d in drugs.values():
        for field in [d.get("name"), d.get("display_name"), d.get("id")]:
            if field and len(field) > 3:
                drug_lookup[field.lower()] = d

    company_lookup = {}  # lowercased token → company record
    for c in companies.values():
        for field in [c.get("name"), c.get("ticker"), c.get("id")]:
            if field and len(field) > 2:
                company_lookup[field.lower()] = c

    enriched = []
    for item in items:
        text = f"{item.get('headline','')} {item.get('body','')}".lower()

        matched_drugs = []
        seen_drug_ids = set()
        for token, drug in drug_lookup.items():
            if token in text and drug["id"] not in seen_drug_ids:
                matched_drugs.append(drug)
                seen_drug_ids.add(drug["id"])

        matched_companies = []
        seen_co_ids = set()
        for token, co in company_lookup.items():
            if token in text and co["id"] not in seen_co_ids:
                matched_companies.append(co)
                seen_co_ids.add(co["id"])

        ctx_lines = []
        for drug in matched_drugs[:4]:  # cap at 4 matched drugs
            parts = [
                f"  → {drug.get('display_name') or drug.get('name')} ({drug.get('company_id','')})",
                f"    Stage: {drug.get('stage','?')} | Target: {drug.get('target') or drug.get('mechanism','?')}",
                f"    Overlap: {drug.get('overlap','?')} | Indication: {drug.get('indication_short','?')}",
            ]
            if drug.get("ailux_angle"):
                parts.append(f"    BD Signal: {drug['ailux_angle']}")
            if drug.get("partner_company"):
                verified = "✓" if drug.get("partnership_verified") else "?"
                parts.append(f"    Partner: {drug['partner_company']} [{drug.get('partnership_type','')}] {verified}")
            ctx_lines.extend(parts)

        item = dict(item)
        item["_db_context"] = "\n".join(ctx_lines) if ctx_lines else None
        enriched.append(item)

    return enriched


# ── Build prompt data ────────────────────────────────────────────────────────
def build_intel_block(items):
    if not items:
        return "(No new intel items today)"
    lines = []
    for it in items:
        areas_str = ", ".join(AREA_NAMES.get(a, a) for a in it.get("areas", []))
        block = (
            f"[{it['importance'].upper()} | {it['intel_type']} | {areas_str}]\n"
            f"HEADLINE: {it['headline']}\n"
            f"DETAIL: {it['body']}\n"
            f"SOURCE: {it['source_name']} — {it['source_url']}\n"
            f"DATE: {it['intel_date']}"
        )
        if it.get("_db_context"):
            block += f"\nDB CONTEXT (live pipeline state for referenced assets):\n{it['_db_context']}"
        lines.append(block)
    return "\n\n---\n\n".join(lines)


def build_deals_block(deals):
    if not deals:
        return "(No recent deals)"
    lines = []
    for d in deals:
        val = f"${d['upfront_usd_m']}M upfront" if d.get("upfront_usd_m") else ""
        if d.get("total_usd_m"):
            val += f" / ${d['total_usd_m']}M total"
        lines.append(
            f"{d['deal_date']} | {d.get('deal_type','').upper()} | {AREA_NAMES.get(d['area_id'], d['area_id'])}\n"
            f"{d['from_company']} → {d['to_company']} {val}\n"
            f"{d['headline']}"
            + (f"\nDETAIL: {d['detail']}" if d.get("detail") else "")
        )
    return "\n\n".join(lines)


def build_catalysts_block(cats):
    if not cats:
        return "(No upcoming catalysts on record)"
    lines = []
    for c in cats:
        sig = c.get("significance", "").upper()
        notes = f" — {c['notes']}" if c.get("notes") else ""
        lines.append(
            f"{c['catalyst_date']} | {AREA_NAMES.get(c['area_id'], c['area_id'])} | {sig}\n"
            f"{c['label']}{notes}"
        )
    return "\n".join(lines)


def build_ailux_block(positions):
    """Construct the Ailux competitive anchor block from DB + static context."""
    # Static context is always included; DB positions supplement it
    static = """AILUX IDENTITY & COMPETITIVE POSITION:
Ailux Biotherapeutics is developing three bispecific antibody programs, all targeting IND by 2027:
- ALX001 (TL1A×IL-23p19): Lead IBD program for UC and CD. The p19 subunit selectivity preserves IL-12-driven Th1 immunity unlike p40-targeted agents. The bispecific hypothesis: simultaneous TL1A+IL-23 blockade achieves deep remission in the 40-45% of IBD patients who fail monospecific biologics.
- ALX002 (CD19×BCMA): I&I autoimmune program targeting SLE and Sjogren's via dual B-cell and plasma cell depletion.
- ALX005 (FcRn×Albumin): Rare disease program for gMG and CIDP; half-life extension bispecific format.

CRITICAL — SPYRE TL1A ASSETS ARE MONOSPECIFIC, NOT BISPECIFIC: SPY002 and SPY072 are two SEPARATE extended-half-life (YTE) MONOSPECIFIC anti-TL1A monoclonal antibodies from Spyre Therapeutics — NEITHER is a bispecific, and neither is an Ailux asset. SPY002 is in IBD (SKYLINE-UC; UC induction topline ~June 30 2026). SPY072 is in RHEUMATIC disease (SKYWAY basket: RA/PsA/axSpA; SKYWAY RA sub-study topline ~Q3 2026) — it has NO IBD program and there is no "ATLAS-1" trial. Treat both as TL1A-ARM benchmarks (proxies for the TL1A arm of ALX001), NOT as bispecific-format competitors. The genuine TL1A×IL-23p19 BISPECIFIC competitors to ALX001 are SIM0709 (Simcere/Boehringer Ingelheim), CLD-423 (Caldera/Qyuns — first subjects dosed Phase 1 Jan 2026), MT-251 (Mirador), XmAb412 (Xencor), HY8931 (Newsoara) and EAR-2001 (Earendil). RO7837195 (Roche/Pfizer) is another direct ALX001 competitor.

FORMAT / INDICATION DISCIPLINE (no assumptions): An asset's format (monospecific vs bispecific), molecular target, indication, and trial names come ONLY from its database row (target, target_class, modality, indication_short, stage_detail) and its drug_sources. NEVER infer "bispecific" from a hyphenated target string or a display name; a drug is bispecific ONLY if target_class says so. NEVER invent or guess a trial name, phase, or indication. If a fact is not in the DB or sources, leave it out rather than guessing.

TL1A CLASS STATE: Two monospecific anti-TL1A antibodies are in Phase 3 — tulisokibart (Merck, ATLAS-UC primary ~Nov 2026, first Ph3 TL1A readout) and afimkibart (Roche, AMETRINE-2 primary Jan 2027). Merck's readout is the single most consequential class validation event before Ailux reaches clinical inflection. A positive result validates sequencing and combination strategies and sets the monotherapy ceiling that a bispecific must exceed. A failure reshapes everything.

IL-23p19 CLASS STATE: Proven. Risankizumab (AbbVie, approved UC+CD), mirikizumab (Lilly, approved UC), guselkumab (J&J, CD Phase 3). Ailux enters against approved SOC — the clinical question is not "does IL-23 work" but "what does simultaneous TL1A+IL-23p19 blockade do beyond the sum of its parts."

BD PRIORITIES — what would actually move the needle for Ailux:
1. Combination data showing TL1A+IL-23 superiority over sequential therapy
2. Partner deals or licensing signals that reveal how the market values bispecific assets vs. monospecifics
3. Early-entry opportunities in less crowded Ailux areas (IGF1R/TED, FcRn, TSLP, T-cell/Treg)
4. Regulatory precedents for bispecific approval pathways in IBD
5. Clinical failures that reshape the competitive landscape or open white space"""

    if positions:
        pos_lines = []
        for p in positions:
            pos_lines.append(
                f"  Area: {p.get('area_id','')} | Ailux drug: {p.get('ailux_drug','')} "
                f"| Targets: {p.get('ailux_targets','')} | Stage: {p.get('ailux_stage','')}"
            )
            if p.get("ailux_angle"):
                pos_lines.append(f"  Angle: {p.get('ailux_angle')}")
        static += "\n\nLIVE DB POSITIONS:\n" + "\n".join(pos_lines)

    return static


def build_prior_coverage_block(recent_issues):
    """Give the writer a sense of what was covered in prior issues for continuity."""
    if not recent_issues:
        return "(No prior issue history available — this is the first issue.)"
    lines = []
    for i in recent_issues:
        intel_count = len(i.get("intel_ids") or [])
        lines.append(f"  {i['issue_date']}: {i['title']} ({intel_count} intel items)")
    return (
        "PRIOR ISSUE HISTORY (build on themes; connect to new developments; don't repeat without new signal):\n"
        + "\n".join(lines)
    )


def build_company_signals_block(signals):
    """Format current company intelligence bullets for the writer.
    Groups by company so the writer sees the full competitive posture of each player."""
    if not signals:
        return "(No company signals available)"
    by_company = {}
    for s in signals:
        cid = s.get("company_id", "?")
        by_company.setdefault(cid, []).append(s)
    lines = ["CURRENT COMPANY INTELLIGENCE (from live dashboard company cards):"]
    for company in sorted(by_company):
        lines.append(f"\n{company.upper()}:")
        for s in by_company[company]:
            stype = (s.get("dir") or s.get("signal_type") or "?").upper()
            lines.append(f"  [{stype}] {s.get('signal_text', '')}")
    return "\n".join(lines)


def build_trials_block(trials):
    """Format recent trial updates for editorial context."""
    if not trials:
        return "(No recent trial updates)"
    lines = ["RECENT CLINICAL TRIAL UPDATES (from dashboard trial tracker):"]
    for t in trials[:30]:  # cap at 30 to avoid prompt bloat
        drug   = t.get("drug_id", "?")
        phase  = t.get("phase", "?")
        status = t.get("status", "?")
        ind    = t.get("indication", "")
        name   = t.get("trial_name") or t.get("study_acronym", "")
        comp   = t.get("primary_completion_date", "")
        line   = f"  {drug} | Phase {phase} | {status} | {ind}"
        if comp:
            line += f" | completion: {comp}"
        if name:
            line += f" | {name}"
        lines.append(line)
    return "\n".join(lines)


def build_graph_block(active_in, targets_edges, competes_with):
    """
    Format entity_edges data as graph-grounded competitive intelligence.

    The graph supplements the editorial's drug/company context with stored
    structural relationships — who is where, what they target, and who
    directly competes. This is the L4-A graph injection layer.
    """
    if not active_in and not targets_edges and not competes_with:
        return "(Graph context unavailable)"

    PRIORITY_AREAS = ["tl1a", "tslp", "il4ra", "fcrn", "igf1r", "tcell", "ibd", "respiratory"]
    lines = ["GRAPH INTELLIGENCE (stored entity relationships — from entity_edges):"]

    # ── ACTIVE_IN: who is in each area ────────────────────────────────────────
    if active_in:
        lines.append("\nACTIVE PLAYERS BY AREA (ACTIVE_IN — confirmed company→area edges):")
        area_order = PRIORITY_AREAS + [a for a in sorted(active_in) if a not in PRIORITY_AREAS]
        for area in area_order:
            companies = active_in.get(area)
            if not companies:
                continue
            label = AREA_NAMES.get(area, area)
            lines.append(f"  {label}: {', '.join(sorted(companies))}")

    # ── TARGETS: mechanism convergence (which entities target the same mechanism) ──
    if targets_edges:
        # Reverse map: target → [entities]
        by_target = {}
        for entity, tgts in targets_edges.items():
            for t in tgts:
                by_target.setdefault(t, []).append(entity)
        # Only show contested mechanisms (≥2 entities)
        contested = {t: sorted(v) for t, v in by_target.items() if len(v) >= 2}
        if contested:
            lines.append("\nMECHANISM CONVERGENCE (TARGETS — mechanisms with multiple competing entities):")
            for target in sorted(contested, key=lambda t: -len(contested[t])):
                entities = contested[target]
                lines.append(f"  {target}: {', '.join(entities)} ({len(entities)} entities)")

    # ── COMPETES_WITH: direct competitive pairs ────────────────────────────────
    if competes_with:
        lines.append(f"\nDIRECT COMPETITIVE PAIRS (COMPETES_WITH — confirmed, {len(competes_with)} total):")
        # Group by shared tokens (rough area clustering)
        for subj, obj in competes_with[:50]:  # cap at 50 to avoid prompt bloat
            lines.append(f"  {subj} ↔ {obj}")

    return "\n".join(lines)


# ── System prompt (editorial identity) ──────────────────────────────────────
SYSTEM_PROMPT = """You are the founding editor of The Meridian, a Monday–Saturday morning intelligence briefing published exclusively for the BD and strategy leadership of Ailux, an AI-native antibody design company.

YOUR ROLE: The Meridian is the daily consolidation layer of the Ailux BD intelligence platform. Every piece of information flowing through the dashboard — company signals, clinical trial updates, deal activity, catalyst tracking, live intel — converges here. Your job is to synthesize all of it into a single coherent argument about what the competitive landscape looked like this morning, and what it means for Ailux's next 18 months.

YOUR READERS: PhD scientists who have published in Nature and NEJM. BD professionals who have closed nine-figure deals. They have already read the press releases. They do not need definitions of mechanisms, trial designs, or deal structures. They need the interpretive layer — the argument beneath the news.

YOUR EDITORIAL STANDARD:
- Every paragraph must contain one claim a smart, busy reader could not have made without reading this issue. If a paragraph only restates known facts, cut it or rewrite it.
- Never summarize what happened. Explain what it means and why it matters in the next 18 months.
- The BD Lens is ACTION ONLY, not a second pass at the argument. The preceding prose already made the case; the Lens states only the decision it forces: what to do, which counterparty, by when. If the Lens restates the why, cut the restatement — keep only the move.
- When two stories connect non-obviously, make the connection explicit and argue it. That is where the value lives.
- Draw threads across issues. If Monday covered a deal and today brings data from the same program, say so explicitly — this is how the briefing builds a living model of the landscape.
- When the news is quiet, say what is conspicuously absent and why that itself is signal. A mechanism with no news for three weeks when competitors are typically active is information.
- Company signals and trial status from the dashboard are primary inputs — they represent the accumulated intelligence state, not just today's news. Use them.
- Be precise about mechanism. "IL-23 inhibition" is not acceptable. Specify the subunit, the pathway, the cell type, the downstream effect.
- Do not write "it remains to be seen." That hedge belongs in investor presentations, not intelligence briefings.
- Do not write "this space continues to evolve" or any equivalent platitude.

DIRECTNESS & ANTI-REPETITION (house rules — enforce strictly):
- STATE EACH THESIS ONCE. The lead carries the central argument. Every later section must add NEW evidence, a NEW asset, or a NEW connection — it may build on the thesis but must never re-argue it. If a paragraph would only restate the lead in different words, cut it.
- NO POSTURING. Drop portentous throat-clearing — "the central fact strategy must metabolize this weekend," "make no mistake," "the question is whether," "the window is X weeks wide" repeated as a refrain. Lead with the fact, then the implication, in plain declarative sentences. A dramatic sentence is weaker than a precise one.
- FACTS AND RELATIONSHIPS OVER ADJECTIVES. Prefer a number, a date, a mechanism, or an explicit A→B relationship to any intensifier. Every competitive claim must name the relationship (who competes with / blocks / enables / sequences against / prices whom) and the evidence for it. Cut words that carry no fact: if a sentence survives deletion of an adjective with its meaning intact, delete the adjective.
- NO ASSUMPTIONS. If you do not have a sourced fact, do not assert it. Do not infer an asset's format, target, indication, trial name, phase, or deal terms. Absent evidence, say less.
- SEPARATE FACT FROM INTERPRETATION BY VERB (not by label). State sourced facts as flat declaratives: "Simcere licensed SIM0709 to Boehringer for €42M upfront." Mark every inference with a verb that signals it is your read: "this implies," "the likely read is," "suggests," "if that holds." The reader must always be able to tell a sourced fact from your interpretation without a tag. Never dress an inference as a fact (e.g., "this creates a valuation floor" is interpretation — write "this likely sets a floor").
- VARY THE ANALYTICAL MOVE. "External event → therefore Ailux should X" is ONE move; do not let it become the only one. Across the issue also use: contradiction (two sources disagree — say which wins and why), absence (an expected readout that did not arrive is itself signal), second-order (how a competitor will respond, not just what they did), and disconfirmation. Carry the plan's falsifier into the issue at least once — name the result that would prove the lead thesis wrong. If every item bends to support the thesis, the issue reads as confirmation bias, not intelligence.

SOURCE HIERARCHY: Endpoints News and Fierce Biotech are the primary trade sources. Direct company press releases are equally authoritative. When these sources conflict with secondary sources, prefer Endpoints/Fierce/company-direct. All factual claims must be hyperlinked to their source.

TONE: Plain, declarative, dense. The fact carries the weight, not the phrasing. Write like an analyst briefing a principal who trusts you and is short on time: state what is true, state what it implies, stop. No grandeur, no throat-clearing, no rhetorical build-up, no rhetorical questions, no "metabolize this weekend" theatrics, no refrains. A short sentence that states a fact beats a long one that performs insight. If a sentence's job is to sound smart rather than to inform, delete it. Precision is the only style.

HARD PROHIBITIONS:
- Do not include any contact information, email addresses, or tip lines. The Meridian has no public inbox.
- Do not include any sign-off line such as "Questions or tips:" or any equivalent.
- Do NOT include any confidentiality notice, classification label, or footer text. The Meridian Issue ends after the closing note — no disclaimers, no "AILUX INTERNAL", no "Not for external distribution", nothing after the closing section.

WRITING_STANDARDS:
- Resolve contradictions before writing. If two sources disagree on a drug's target or mechanism, the definitive answer is the primary literature or EMA/FDA label. Never present both versions as equally valid.
- No speculation about company strategy, executive intent, or institutional behavior unless supported by a press release, earnings call transcript, or investor letter. Inference is not evidence.
- Every competitive paragraph must include at minimum: patient population (N, geography), current SOC response rate, and what clinical improvement means for this patient. Numbers are mandatory.
- Cite exact trial data: registry ID or trial name, primary endpoint metric, value at which dose and timepoint, N enrolled or completed. Do not round or generalize.
- First mention of a drug name in the HTML output: wrap in <a href="#" onclick="openDrugModal('{drug_id}')">drug name</a>. Subsequent mentions: plain text.
- First mention of a company name: wrap in <a href="#" onclick="openCompanyModal('{company_id}')">company name</a>. Subsequent mentions: plain text.
- Target is the molecular target. Mechanism is how the drug engages it. Pathway is the downstream biology. Name all three distinctly.
- If a drug's mechanism is unknown or disputed, say so explicitly and do not write competitive analysis around it until resolved."""

ENRICHED_DATA_INSTRUCTIONS = """
ENRICHED DATA NOW AVAILABLE — USE IT:

1. PATIENT MARKET DATA: You have numeric patient counts and market sizes for each indication.
   - Cite the number, but MATCH THE DECORATION TO ITS CERTAINTY. A figure with a real source: state it plainly and cite it. A modeled estimate from the stats block: write it as a round approximation — "about $8B", "roughly 900,000 US patients" — with NO decimal place and NO tilde. Do NOT render an estimate as "$8.0B" or "~1,680,000US"; decorating an estimate with a decimal or a tilde-plus-exact-digits is false precision and erodes trust.
   - ALWAYS cite unmet_need_score (1–10) when available: "Unmet need score: {score}/10"
   - Interpret the score: 8–10 = severe unmet need, 5–7 = partial, 1–4 = manageable with current SoC
   - NEVER use vague phrases like "large patient population" without the number

2. UPCOMING CATALYSTS: You have a structured BD catalyst calendar with specific dates.
   - ALWAYS include a "⏰ BD Calendar — Next 90 Days" section (see section structure below)
   - Format each entry: "[SIGNIFICANCE] YYYY-MM-DD | drug (company) | EVENT TYPE — event name | Ailux impact"
   - This section appears even when there are no catalysts — show the table with "No near-term catalysts" if empty
   - This is the single most important timing intelligence for BD decision-making

3. BD PRIORITY COMPANIES: You have competitive relevance scores for all drugs.
   - In any section discussing a competitor drug, cite its competitive_relevance tier if available
   - For companies with view_type=acquisition_target and strategic_score ≥ 70, note this explicitly
   - AbbVie is NOT a current BD target for TL1A bispecific until after ABBV-701 Phase 1 readout (Oct 2026)
   - "CALL NOW" framing applies only to companies with no conflicting timing constraint

4. WRITING STANDARD (reconfirmed):
   - No speculation about company strategy unless supported by press release, earnings call, or investor letter
   - First mention of drug → hyperlink to drug card modal
   - First mention of company → hyperlink to company modal
   - Patient numbers required for every indication discussed
   - Mechanism precision required: name the target, pathway, and effector cell
"""

SYSTEM_PROMPT = SYSTEM_PROMPT + "\n\n" + PATIENT_INTELLIGENCE_CONTEXT + ENRICHED_DATA_INSTRUCTIONS


# ── Pass 1: Editorial planning ───────────────────────────────────────────────
PLAN_PROMPT = """Today is {date_long}.

You are planning today's issue of The Meridian before writing it. The Meridian is the daily consolidation layer of the Ailux BD intelligence platform — every signal flowing through the dashboard feeds this issue. Read all available intelligence carefully, then produce a tight editorial plan.

INTELLIGENCE AVAILABLE:
{intel_block}

RECENT DEALS:
{deals_block}

BD CATALYST CALENDAR (structured timing intelligence):
{catalyst_calendar_block}

BD PRIORITY COMPANIES (competitive scores + strategic views):
{bd_priority_block}

COMPANY INTELLIGENCE (live dashboard state):
{signals_block}

GRAPH INTELLIGENCE (stored entity relationships — who is active where, what they target, who competes with whom):
{graph_block}

PRIOR COVERAGE:
{prior_block}

AILUX CONTEXT:
{ailux_block}

## Today's Patient Intelligence Context
{patient_context_block}

## Patient Population & Market Stats (v65 — queryable numeric fields)
{patient_stats_block}

Your editorial plan must answer:
1. THESIS: In one sentence, what is the single most important thing today's full intelligence picture reveals about the competitive landscape? This becomes the editorial spine of the lede.
2. SIGNAL vs. NOISE: Which 3–5 items are genuinely significant and deserve analysis? Which are noise (announcements without substance, recycled data, obvious moves)?
3. CONNECTIONS: Identify 1–3 non-obvious connections between separate items — including connections to prior issue themes. What do they point to together that neither suggests alone?
4. BD IMPLICATIONS: What are the 2–3 most specific implications for Ailux's BD strategy — not "this is relevant" but the actual tactical or positional inference?
5. ABSENCES: What notable development is conspicuously NOT in today's news that is worth flagging?
6. CONTINUITY: Are there threads from prior issues that today's intelligence advances, resolves, or complicates? Name them.
7. SECTION PLAN: Which sections should appear today? (Lead is always present. Others: Mechanism Intelligence / Clinical Inflection Points / BD & Deal Watch / Regulatory Watch.) NOVELTY GATE: for each non-lead section, state in one line the NEW fact, asset, or connection it adds beyond the thesis. A section that would only re-argue the lead in different words must be CUT or MERGED — restating the thesis is not a contribution. Be ruthless: fewer sections that each add something beat many that echo each other.
8. FALSIFICATION: In one sentence, what concrete result or event would prove today's thesis WRONG? (This must be carried into the issue — an honest intelligence product names what would change its mind.)

Return your plan as JSON with keys: thesis, signal_items (list of headlines), noise_items (list of headlines), connections (list of strings), bd_implications (list of strings), absences (string), continuity_threads (list of strings), falsifier (string), section_plan (list of objects {{"name": section name, "adds": the one-line new contribution}})."""


# ── Pass 2: Full draft ───────────────────────────────────────────────────────
DRAFT_PROMPT = """Today is {date_long}. Write today's complete issue of The Meridian as a self-contained HTML document.

The Meridian is the daily consolidation layer of the Ailux BD intelligence platform. It synthesizes every signal the platform has captured — live intel, company signals, trial updates, deals, catalysts — into a single coherent morning briefing. Use all of the data below.

EDITORIAL PLAN (developed before writing — follow it):
{plan_block}

INTELLIGENCE (last 48 hours — primary sources: Endpoints News, Fierce Biotech, direct company press releases):
{intel_block}

RECENT DEALS (last 7 days):
{deals_block}

UPCOMING CATALYSTS (legacy catalysts table):
{catalysts_block}

BD CATALYST CALENDAR (structured timing intelligence — use this for the BD Calendar section):
{catalyst_calendar_block}

BD PRIORITY COMPANIES (competitive scores + strategic views):
{bd_priority_block}

COMPANY INTELLIGENCE (live state from dashboard company cards):
{signals_block}

GRAPH INTELLIGENCE (stored entity relationships — who is active where, mechanism convergence, confirmed competitive pairs):
{graph_block}

CLINICAL TRIAL TRACKER (recent updates from dashboard trial panel):
{trials_block}

AILUX CONTEXT:
{ailux_block}

## Today's Patient Intelligence Context
{patient_context_block}

## Patient Population & Market Stats (v65 — queryable numeric fields)
{patient_stats_block}

─────────────────────────────────────────────
SECTION STRUCTURE (build exactly this architecture):

1. LEAD — No section header. 3–5 paragraphs. Open with the editorial thesis in the first sentence — a claim, not a summary. Build the argument across paragraphs. Weave the day's most important stories into a single thematic arc. No bullet points. This is the intellectual core of the issue.

2. MECHANISM INTELLIGENCE — One subsection per target/pathway with meaningful news. Header: name the mechanism with a subtitle that argues something (e.g., "TL1A: Setting the Monospecific Ceiling" not "TL1A Update"). Each subsection: 2–4 paragraphs of analysis + one BD Lens callout. Link source URLs inline as anchor tags.

3. CLINICAL INFLECTION POINTS — Only if there are meaningful data readouts, enrollment milestones, or trial events that change the prior on a mechanism or asset. If today has no genuine clinical news, omit this section entirely rather than pad it.

4. BD & DEAL WATCH — If there are recent deals. For each deal: what was the strategic logic, what does the pricing signal about asset valuation, who is now foreclosed from this asset. Go beyond describing the deal to arguing its implications.

5. ⏰ BD CALENDAR — NEXT 90 DAYS — ALWAYS INCLUDE. Never omit this section, even on quiet news days. It is the fixed BD timing anchor.
   - Use the BD CATALYST CALENDAR data above (from catalyst_calendar table)
   - Group entries by calendar month (e.g., "June 2026", "July 2026", "August 2026")
   - For each event: drug name, company, event type, expected date, and the ailux_impact field verbatim (truncated to 2 sentences max)
   - After the grouped list, include a compact HTML table: columns = Month | Event | Drug (Company) | Significance | Ailux Impact
   - If no events fall in the 90-day window, show the table header with a single row: "(No near-term catalysts on record)"
   - Then add a sub-header "Horizon (>90 days)" and list events in the next 12 months

6. 🩺 INDICATION INTELLIGENCE — ALWAYS INCLUDE. Pull from the Patient Population & Market Stats block.
   - Select the 2–3 indications most relevant to this week's news (IBD / UC / CD always eligible; add others if they appeared in today's intel)
   - For each indication, write one compact paragraph using this exact structure:
     "There are approximately [N] patients with [indication] in the United States ([M] globally). The addressable market is estimated at $[X]B. Current standard-of-care achieves remission in approximately [R]% of patients; [F]% fail biologics, leaving a substantial refractory population. Unmet need score: [U]/10." — fill in the actual numbers from the Patient Population & Market Stats block above.
   - If a numeric field is null, omit that clause rather than using "N/A"
   - Follow each paragraph with a BD Lens callout linking the market size and failure rate to Ailux's positioning

7. CATALYST WATCH — The legacy catalyst table (from UPCOMING CATALYSTS block above). HTML table with columns: Event | Asset | Area | Expected | Significance. Order by date ascending. If no legacy catalysts, note "(No entries in legacy catalyst table — see BD Calendar section above)"

8. CLOSING NOTE — 2–3 sentences in italic. End on a single forward-looking observation or open question — the one thing to watch next. Do NOT restate the lead thesis or recap the issue; if the closer could have been written before reading the body, rewrite it. It must point forward, not back.

─────────────────────────────────────────────
4-LAYER NARRATIVE FORMAT — mandatory for any drug event, clinical trial result, or deal:
When writing about any drug event, clinical trial result, or deal involving a drug in the IBD, atopy, TED, FcRn, T-cell, or GI oncology space, apply the 4-layer format:
1. What the molecule does (1 sentence)
2. Who the patient is and what they face (2-3 sentences)
3. What the mechanism means for the patient's daily life (1-2 sentences)
4. What this means for BD strategy and deal value (1-2 sentences)

─────────────────────────────────────────────
BD LENS FORMAT — use this HTML for every BD Lens callout:
<div class="bd-lens">
  <p class="label">BD LENS</p>
  <p>[ACTION ONLY — 1–2 sentences. The decision the section forces: what to do, which counterparty, by when. Do NOT restate the analysis above it; the reader just read it. If you find yourself re-explaining the why, delete that and keep only the move. Example shape: "Brief Merck BD on the X angle before the Nov 30 ATLAS-UC readout; after it, the price moves." Not: a paragraph re-arguing why Merck matters.]</p>
</div>

─────────────────────────────────────────────
SOURCE LINKING — MANDATORY:
Every factual claim drawn from an intel item MUST be hyperlinked to its source_url using an inline anchor tag. This is non-negotiable.
- Format: <a href="SOURCE_URL" target="_blank" rel="noopener noreferrer">linked text</a>
- ALWAYS include target="_blank" rel="noopener noreferrer" on every source link. This is mandatory — without it, the link navigates the iframe instead of opening a new tab.
- Link on the most specific noun — drug name, trial name, company name, or the key phrase — not generic words like "reported" or "announced"
- IMPORTANT: Do NOT wrap drug or company names in source links. If a drug name IS the source anchor, use a generic word instead (e.g., "announced" or "reported") so the drug name stays available for entity modal linking.
- When Endpoints News or Fierce Biotech is the source, prefer those links over others covering the same story
- Aim for at minimum one hyperlink per paragraph. Dense sourcing is a feature, not clutter.
- If two sources cover the same claim, link both: "Endpoints <a href="...">reported</a> and Fierce <a href="...">confirmed</a>"
- Do NOT write "(Source: X)" footnotes. Links are inline, in context.

─────────────────────────────────────────────
HTML INSTRUCTIONS:
Return ONLY valid, complete HTML starting with <!DOCTYPE html>. Use this exact CSS verbatim:

* {{ box-sizing: border-box; }}
body {{ max-width: 860px; margin: 0 auto; padding: 36px 40px 80px; font-family: Georgia, 'Times New Roman', serif; font-size: 17px; color: #1a1a1a; line-height: 1.8; background: #fff; }}
h1 {{ color: #1a3f8f; font-size: 38px; margin: 0 0 6px 0; letter-spacing: -0.5px; }}
h2 {{ color: #1a3f8f; font-size: 22px; margin: 40px 0 4px 0; border-bottom: 1px solid #dce6f7; padding-bottom: 6px; }}
h3 {{ color: #1e3a5f; font-size: 18px; margin: 28px 0 6px 0; font-style: italic; }}
p {{ margin: 0 0 14px 0; }}
.dateline {{ font-family: Calibri, Helvetica, sans-serif; font-size: 14px; color: #3d5166; letter-spacing: 0.5px; text-transform: uppercase; }}
.tagline {{ font-style: italic; font-size: 16px; color: #3d5166; margin: 0 0 24px 0; }}
hr.thick {{ border: none; border-top: 3px solid #1a3f8f; margin: 10px 0 4px 0; }}
hr.thin {{ border: none; border-top: 1px solid #d0d9ea; margin: 4px 0 28px 0; }}
a {{ color: #1a3f8f; text-decoration: none; border-bottom: 1px solid #bfdbfe; }}
a:hover {{ border-bottom-color: #1a3f8f; }}
table {{ width: 100%; border-collapse: collapse; margin: 16px 0 24px 0; font-size: 14px; font-family: Calibri, Helvetica, sans-serif; }}
th {{ background: #1a3f8f; color: #fff; font-weight: 700; padding: 10px 12px; text-align: left; border: 1px solid #1a3f8f; }}
td {{ padding: 9px 12px; border: 1px solid #dce6f7; vertical-align: top; line-height: 1.5; }}
tr:nth-child(even) td {{ background: #f5f8ff; }}
.bd-lens {{ border-left: 4px solid #1a3f8f; background: #f0f4fb; padding: 18px 22px; margin: 22px 0; border-radius: 0 4px 4px 0; }}
.bd-lens p {{ margin: 0 0 6px 0; }}
.bd-lens p:last-child {{ margin: 0; }}
.label {{ font-family: Calibri, Helvetica, sans-serif; font-size: 11px; font-weight: 700; letter-spacing: 2px; color: #1a3f8f; text-transform: uppercase; margin-bottom: 8px !important; }}
.closing {{ font-style: italic; color: #3d5166; font-size: 16px; border-top: 1px solid #d0d9ea; padding-top: 20px; margin-top: 40px; }}
.issue-meta {{ font-family: Calibri, Helvetica, sans-serif; font-size: 13px; color: #64748b; margin-top: 60px; padding-top: 16px; border-top: 1px solid #e8edf5; }}

The header block must be exactly:
<p class="dateline">{date_dateline}</p>
<hr class="thick">
<h1>The Meridian</h1>
<p class="tagline">Intelligence for the intersection of science, strategy, and the examined life.</p>
<hr class="thin">

Return ONLY the HTML document. No markdown. No explanation outside the HTML."""


# ── First-mention hyperlink post-processor ───────────────────────────────────
def apply_first_mention_links(html: str, drugs: dict, companies: dict) -> str:
    """
    Post-processing pass: wrap the FIRST occurrence of each known drug name and
    company name in the HTML with the appropriate onclick modal link.  All
    subsequent occurrences are left as plain text.

    Rules:
      - Drug first mention  → <a href="#" onclick="openDrugModal('{id}')">name</a>
      - Company first mention → <a href="#" onclick="openCompanyModal('{id}')">name</a>
      - Names already inside an <a …> tag are skipped (source links placed by LLM).
      - Only replaces exact-case matches with word-boundary guards to avoid
        partial-word collisions (e.g. "Roche" inside "Roche/Genentech" is handled
        by longest-match ordering).
      - Skips tokens shorter than 4 characters to reduce false positives.

    This closes the gap when the LLM fails to apply the onclick pattern itself,
    and enforces the WRITING_STANDARDS first-mention rule programmatically.
    """
    import re as _re

    # Build sorted lists: longest name first to avoid partial replacements
    drug_entries = []
    for d in drugs.values():
        for field in [d.get("display_name"), d.get("name")]:
            if field and len(field) >= 4:
                drug_entries.append((field, d["id"]))
    # Deduplicate by name, keep first occurrence (display_name preferred)
    seen_drug_names = set()
    drug_entries_dedup = []
    for name, did in sorted(drug_entries, key=lambda x: -len(x[0])):
        if name.lower() not in seen_drug_names:
            seen_drug_names.add(name.lower())
            drug_entries_dedup.append((name, did))

    company_entries = []
    for c in companies.values():
        if c.get("name") and len(c["name"]) >= 4:
            company_entries.append((c["name"], c["id"]))
    company_entries = sorted(company_entries, key=lambda x: -len(x[0]))

    # Helper: check if position pos in html is already inside an <a> tag
    def _inside_anchor(html_str, pos):
        """Return True if pos falls between an <a …> and its </a>."""
        preceding = html_str[:pos]
        open_count  = len(_re.findall(r'<a[\s>]', preceding, _re.IGNORECASE))
        close_count = len(_re.findall(r'</a>', preceding, _re.IGNORECASE))
        return open_count > close_count

    def _replace_first(html_str, token, replacement):
        """Replace the first word-boundary occurrence of token (case-sensitive)
        that is NOT already inside an anchor tag."""
        pattern = _re.compile(r'(?<![a-zA-Z0-9\-])' + _re.escape(token) + r'(?![a-zA-Z0-9\-])')
        for m in pattern.finditer(html_str):
            if not _inside_anchor(html_str, m.start()):
                return html_str[:m.start()] + replacement + html_str[m.end():]
        return html_str  # no eligible occurrence found

    # Apply drug links
    drug_linked = set()
    for name, did in drug_entries_dedup:
        if name.lower() not in drug_linked:
            link = f'<a href="javascript:void(0)" style="cursor:pointer" onclick="try{{window.parent.openDrugEntityModal(\'{did}\',\'{name}\',null)}}catch(e){{}}">{name}</a>'
            new_html = _replace_first(html, name, link)
            if new_html is not html:  # replacement was made
                html = new_html
                drug_linked.add(name.lower())

    # Apply company links
    co_linked = set()
    for name, cid in company_entries:
        if name.lower() not in co_linked:
            link = f'<a href="javascript:void(0)" style="cursor:pointer" onclick="try{{window.parent.openCompanyEntityModal(\'{cid}\',\'{name}\',\'meridian\',\'{cid}\')}}catch(e){{}}">{name}</a>'
            new_html = _replace_first(html, name, link)
            if new_html is not html:
                html = new_html
                co_linked.add(name.lower())

    log(f"First-mention links applied: {len(drug_linked)} drugs, {len(co_linked)} companies")

    # ── Final cleanup: fix LLM-generated href="#" entity links ──────────────────
    # The LLM sometimes generates <a href="#" onclick="openDrugModal('id')"> or
    # <a href="#" onclick="openCompanyModal('id')"> links. These break because:
    #   1. openDrugModal / openCompanyModal don't exist in the Meridian iframe
    #   2. href="#" scrolls or navigates the iframe instead of opening a card
    # Fix: convert to javascript:void(0) + window.parent calls, or strip entirely.
    import re as _re2

    def _fix_drug_modal_link(m):
        did = m.group(1).strip("'\"")
        # Try to get the display name from between the tags
        display = m.group(2)
        safe_name = display.replace("'", "\\'")
        return (f'<a href="javascript:void(0)" style="cursor:pointer" '
                f'onclick="try{{window.parent.openDrugEntityModal(\'{did}\',\'{safe_name}\',null)}}catch(e){{}}">'
                f'{display}</a>')

    def _fix_company_modal_link(m):
        cid = m.group(1).strip("'\"")
        display = m.group(2)
        safe_name = display.replace("'", "\\'")
        return (f'<a href="javascript:void(0)" style="cursor:pointer" '
                f'onclick="try{{window.parent.openCompanyEntityModal(\'{cid}\',\'{safe_name}\',\'meridian\',\'{cid}\')}}catch(e){{}}">'
                f'{display}</a>')

    # Match: <a href="#" onclick="openDrugModal('id')">text</a>
    html = _re2.sub(
        r'<a\s+href=["\']#["\'][^>]*onclick=["\']openDrugModal\(([^)]+)\)["\'][^>]*>([^<]+)</a>',
        _fix_drug_modal_link, html)
    # Also handle reversed attr order: onclick first, then href
    html = _re2.sub(
        r'<a\s+onclick=["\']openDrugModal\(([^)]+)\)["\'][^>]*href=["\']#["\'][^>]*>([^<]+)</a>',
        _fix_drug_modal_link, html)

    # Match: <a href="#" onclick="openCompanyModal('id')">text</a>
    html = _re2.sub(
        r'<a\s+href=["\']#["\'][^>]*onclick=["\']openCompanyModal\(([^)]+)\)["\'][^>]*>([^<]+)</a>',
        _fix_company_modal_link, html)
    html = _re2.sub(
        r'<a\s+onclick=["\']openCompanyModal\(([^)]+)\)["\'][^>]*href=["\']#["\'][^>]*>([^<]+)</a>',
        _fix_company_modal_link, html)

    # Catch-all: any remaining href="#" on entity links → strip href (leave onclick)
    html = _re2.sub(r'(<a\b[^>]*) href=["\']#["\']([^>]*onclick[^>]*>)', r'\1\2', html)

    log("LLM href='#' entity links sanitized")

    # ── Ensure ALL external source links have target="_blank" ──────────────────
    # Source links without target="_blank" navigate the iframe itself when clicked,
    # which browsers show as about:blank (cross-origin blocked). This post-processor
    # guarantees every external href gets target="_blank" rel="noopener noreferrer"
    # regardless of what the LLM emitted.
    def _add_target_blank(m):
        tag = m.group(0)
        if 'target=' in tag:
            return tag  # already has target
        if 'onclick=' in tag:
            return tag  # entity modal link — never add target
        # Insert target="_blank" rel="noopener noreferrer" before the closing >
        return tag[:-1] + ' target="_blank" rel="noopener noreferrer">'

    html = _re2.sub(r'<a\b[^>]*href=["\']https?://[^"\']*["\'][^>]*>', _add_target_blank, html)

    # Count and log
    n_blanks = len(_re2.findall(r'target="_blank"', html))
    log(f"Source links with target=_blank ensured: {n_blanks}")

    return html


# ── Generate HTML with Claude Opus (two passes) ──────────────────────────────
def generate_editorial_plan(date_long, intel_block, deals_block, ailux_block,
                             prior_block, signals_block="", graph_block="",
                             patient_context_block="", patient_stats_block="",
                             catalyst_calendar_block="", bd_priority_block=""):
    """Pass 1: produce a tight editorial plan before writing a word of prose."""
    prompt = PLAN_PROMPT.format(
        date_long               = date_long,
        intel_block             = intel_block,
        deals_block             = deals_block,
        ailux_block             = ailux_block,
        prior_block             = prior_block,
        signals_block           = signals_block,
        graph_block             = graph_block or "(Graph context unavailable)",
        patient_context_block   = patient_context_block or "(No patient intelligence context available)",
        patient_stats_block     = patient_stats_block or "(Patient population stats not available — v65 migration may be pending)",
        catalyst_calendar_block = catalyst_calendar_block or "(No catalyst calendar data available)",
        bd_priority_block       = bd_priority_block or "(No BD priority company data available)",
    )
    log("Pass 1 — generating editorial plan (Sonnet)…")
    log(f"Pass 1 prompt length: {len(prompt):,} chars / ~{len(prompt)//4:,} tokens")
    try:
        resp = client.messages.create(
            model      = "claude-sonnet-4-6",
            max_tokens = 1500,
            system     = SYSTEM_PROMPT,
            messages   = [{"role": "user", "content": prompt}],
        )
    except Exception as api_err:
        log(f"Pass 1 API error: {type(api_err).__name__}: {api_err}")
        raise
    raw = resp.content[0].text.strip()
    log(f"Editorial plan: {resp.usage.input_tokens:,} in / {resp.usage.output_tokens:,} out")

    # Parse JSON — strip markdown fencing if present
    cleaned = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.MULTILINE).replace("```", "").strip()
    try:
        plan = json.loads(cleaned)
    except json.JSONDecodeError:
        log("Plan JSON parse failed — using raw text")
        plan = {"thesis": raw, "sections": ["Mechanism Intelligence", "BD & Deal Watch", "Catalyst Watch"]}
    return plan


def format_plan_block(plan):
    """Convert the parsed editorial plan into a readable block for the draft prompt."""
    lines = []
    if plan.get("thesis"):
        lines.append(f"EDITORIAL THESIS: {plan['thesis']}")
    if plan.get("signal_items"):
        lines.append("\nSIGNAL ITEMS (prioritise these):")
        for item in plan["signal_items"]:
            lines.append(f"  • {item}")
    if plan.get("noise_items"):
        lines.append("\nNOISE (handle briefly or skip):")
        for item in plan["noise_items"]:
            lines.append(f"  • {item}")
    if plan.get("connections"):
        lines.append("\nNON-OBVIOUS CONNECTIONS (make these explicit in the writing):")
        for c in plan["connections"]:
            lines.append(f"  • {c}")
    if plan.get("bd_implications"):
        lines.append("\nBD IMPLICATIONS FOR AILUX (ground the BD Lens callouts here):")
        for imp in plan["bd_implications"]:
            lines.append(f"  • {imp}")
    if plan.get("absences"):
        lines.append(f"\nNOTABLE ABSENCE: {plan['absences']}")
    if plan.get("continuity_threads"):
        lines.append("\nCONTINUITY THREADS (connect today's issue to prior coverage):")
        for t in plan["continuity_threads"]:
            lines.append(f"  • {t}")
    if plan.get("falsifier"):
        lines.append(f"\nWHAT WOULD PROVE THE THESIS WRONG (carry this into the issue): {plan['falsifier']}")
    if plan.get("section_plan"):
        lines.append("\nSECTIONS TO INCLUDE — each must deliver its stated NEW contribution; "
                     "if a section cannot, drop it (do not pad or echo the lead):")
        for s in plan["section_plan"]:
            if isinstance(s, dict):
                lines.append(f"  • {s.get('name','(unnamed)')} — adds: {s.get('adds','(no distinct contribution — reconsider)')}")
            else:
                lines.append(f"  • {s}")
    elif plan.get("sections"):
        lines.append(f"\nSECTIONS TO INCLUDE: {', '.join(plan['sections'])}")
    return "\n".join(lines)


def generate_html(intel, deals, catalysts, drugs, companies, ailux_positions,
                  recent_issues, company_signals, trials,
                  graph_active_in=None, graph_targets=None, graph_competes=None,
                  catalyst_calendar_events=None, bd_priority_data=None):
    now = datetime.datetime.utcnow()
    date_long     = now.strftime("%A, %B %-d, %Y")
    week_num      = now.isocalendar()[1]
    date_dateline = f"{now.strftime('%A')} · {now.strftime('%B %-d')} · W{week_num} · {now.year}"

    # Enrich intel with live drug/company context
    enriched_intel = enrich_intel_with_drug_context(intel, drugs, companies)

    # Build patient intelligence context for all areas represented in today's intel.
    # This block is passed to both API passes (plan + draft) so the LLM has
    # verified disease burden data and does not need to hallucinate statistics.
    # v65+: patient_intelligence_module now pulls live numeric stats (patient counts,
    # market sizes, remission/failure rates) from the DB when the v65 columns are
    # present, supplementing the hardcoded disease context text blocks.
    patient_context = build_patient_context_block(enriched_intel) if PATIENT_INTEL_AVAILABLE else ""

    # v65+: Fetch numeric patient stats (patient counts, market sizes, failure rates)
    # as a separate compact block. Injected into the draft prompt so the LLM has
    # precise, queryable figures rather than hand-wavy ranges.
    patient_stats = fetch_patient_intelligence_stats()
    patient_stats_block = build_patient_stats_block(patient_stats)

    intel_block            = build_intel_block(enriched_intel)
    deals_block            = build_deals_block(deals)
    catalysts_block        = build_catalysts_block(catalysts)
    ailux_block            = build_ailux_block(ailux_positions)
    prior_block            = build_prior_coverage_block(recent_issues)
    signals_block          = build_company_signals_block(company_signals)
    trials_block           = build_trials_block(trials)
    graph_block            = build_graph_block(
        graph_active_in or {},
        graph_targets   or {},
        graph_competes  or [],
    )
    catalyst_calendar_block = build_catalyst_calendar_block(catalyst_calendar_events or [])
    bd_priority_block       = build_bd_priority_block(bd_priority_data or {})

    # Pass 1: editorial plan — includes company signals + graph for landscape context
    plan = generate_editorial_plan(date_long, intel_block, deals_block,
                                   ailux_block, prior_block, signals_block,
                                   graph_block=graph_block,
                                   patient_context_block=patient_context,
                                   patient_stats_block=patient_stats_block,
                                   catalyst_calendar_block=catalyst_calendar_block,
                                   bd_priority_block=bd_priority_block)
    plan_block = format_plan_block(plan)

    # ── Persist Pass 1 plan before Pass 2 so it is never lost ────────────────
    # This closes the editorial feedback gap: the plan's editorial judgments
    # (what matters, what is noise, what connections exist) are now queryable.
    _plan_intel_ids  = [it["id"] for it in intel if it.get("id")]
    _plan_company_ids = _extract_company_ids_from_plan(plan, intel)
    _content_fingerprint = _compute_content_fingerprint(_plan_intel_ids, _plan_company_ids)
    log(f"Pass 1 plan persisted: {len(_plan_company_ids)} companies · fingerprint={_content_fingerprint[:12]}…")

    # Pass 2: full draft
    prompt = DRAFT_PROMPT.format(
        date_long               = date_long,
        date_dateline           = date_dateline,
        plan_block              = plan_block,
        intel_block             = intel_block,
        deals_block             = deals_block,
        catalysts_block         = catalysts_block,
        catalyst_calendar_block = catalyst_calendar_block,
        bd_priority_block       = bd_priority_block,
        ailux_block             = ailux_block,
        signals_block           = signals_block,
        trials_block            = trials_block,
        graph_block             = graph_block,
        patient_context_block   = patient_context or "(No patient intelligence context available)",
        patient_stats_block     = patient_stats_block or "(Patient population stats not available — v65 migration may be pending)",
    )

    log("Pass 2 — generating full Meridian draft (Sonnet)…")
    log(f"Pass 2 prompt length: {len(prompt):,} chars / ~{len(prompt)//4:,} tokens")
    try:
        resp = client.messages.create(
            model      = "claude-sonnet-4-6",
            max_tokens = 16000,
            system     = SYSTEM_PROMPT,
            messages   = [{"role": "user", "content": prompt}],
        )
    except Exception as api_err:
        log(f"Pass 2 API error: {type(api_err).__name__}: {api_err}")
        raise
    html = resp.content[0].text.strip()
    log(f"Full draft: {resp.usage.input_tokens:,} in / {resp.usage.output_tokens:,} out → {len(html):,} chars")

    # Strip markdown fencing if model wraps it
    if "```" in html:
        html = re.sub(r"^```[a-z]*\n?", "", html, flags=re.MULTILINE)
        html = html.replace("```", "")

    # Ensure all links open in a new tab (iframe navigation guard)
    if "<base " not in html:
        html = html.replace("<head>", '<head>\n', 1)

    # Apply first-mention hyperlinks for drug and company names.
    # This enforces the WRITING_STANDARDS rule programmatically: first occurrence
    # of each known entity gets an onclick modal link; subsequent occurrences are
    # plain text.  Runs after the LLM draft so the LLM's own source hyperlinks
    # (which already sit inside <a> tags) are never double-wrapped.
    html = apply_first_mention_links(html, drugs, companies)

    # Post-draft fact-check gate: prose format vs canonical drugs table.
    audit_draft_against_db(html, drugs)

    # In-issue reader feedback widget (issue-tab only; writes to meridian_feedback).
    html = inject_feedback_widget(html, datetime.datetime.utcnow().strftime("%Y-%m-%d"))

    return html, plan, _plan_company_ids, _content_fingerprint


# ── Editorial plan helpers ────────────────────────────────────────────────────

def _extract_company_ids_from_plan(plan: dict, intel: list) -> list:
    """
    Extract company IDs from the editorial plan for persistence.
    Combines companies mentioned in signal_items with primary_company_id
    from featured intel items.
    Returns a deduplicated list of company ID strings.
    """
    company_ids = set()

    # Pull from plan sections (signal items often name companies)
    # We use the intel primary_company_id as the canonical source since
    # plan signal_items are free-text and not FK-linked.
    intel_map = {str(it.get("id")): it for it in intel}
    for item_ref in plan.get("signal_items", []):
        # signal_items are free-text descriptions — scan for known company slugs
        for it in intel:
            if it.get("primary_company_id") and any(
                str(it["id"])[:8] in item_ref or
                (it.get("headline","")[:20]).lower() in item_ref.lower()
                for _ in [1]  # single iteration, just for short-circuit eval
            ):
                company_ids.add(it["primary_company_id"])

    # Also include primary_company_id from all featured intel
    # (this is the most reliable source since it's FK-linked)
    for it in intel:
        if it.get("primary_company_id"):
            company_ids.add(it["primary_company_id"])

    return sorted(company_ids)


def _compute_content_fingerprint(intel_ids: list, company_ids: list) -> str:
    """
    SHA-256 fingerprint of the intel + company set for this issue.
    Enables repeat-story detection: if today's fingerprint matches a
    recent issue's fingerprint, the same stories are being featured again.
    """
    canonical = "|".join(sorted(str(i) for i in intel_ids)) + "##" + \
                "|".join(sorted(str(c) for c in company_ids))
    return hashlib.sha256(canonical.encode()).hexdigest()


# ── Persist issue to Supabase archive ────────────────────────────────────────
def save_to_supabase(html_content: str, intel: list, date_str: str,
                     plan: dict = None, company_ids: list = None,
                     content_fingerprint: str = None):
    """Upsert the generated issue into meridian_issues for the archive.

    Persists:
      - body_html: the full HTML output (Pass 2)
      - plan_json: the editorial plan from Pass 1 (E8 — editorial loop persistence)
      - intel_ids: IDs of intel items that fed this issue
      - company_ids: companies featured (derived from plan + intel attribution)
      - content_fingerprint: SHA-256 hash for repeat-story detection

    Uses check-then-patch/insert to avoid PostgREST merge-duplicates ambiguity
    (default conflict resolution is on primary key, not issue_date).
    """
    title     = f"The Meridian — {datetime.datetime.utcnow().strftime('%B %-d, %Y')}"
    intel_ids = [it["id"] for it in intel if it.get("id")]
    now_str   = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    # Build the payload with all new fields
    base_payload = {
        "title":               title,
        "body_html":           html_content,
        "intel_ids":           intel_ids,
        "updated_at":          now_str,
    }
    if plan is not None:
        base_payload["plan_json"] = plan
    if company_ids is not None:
        base_payload["company_ids"] = company_ids
    if content_fingerprint is not None:
        base_payload["content_fingerprint"] = content_fingerprint

    # ── Repeat-story detection ───────────────────────────────────────────────
    # If today's fingerprint matches a recent issue, log a warning.
    # Does not block publication — editorial judgement required.
    if content_fingerprint:
        try:
            cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
            dup_r = requests.get(
                f"{SUPABASE_URL}/rest/v1/meridian_issues",
                params={"select": "issue_date,content_fingerprint",
                        "issue_date": f"gte.{cutoff}",
                        "content_fingerprint": f"eq.{content_fingerprint}"},
                headers=SB_HEADERS,
            )
            dups = dup_r.json() if dup_r.status_code == 200 else []
            dups = [d for d in dups if d.get("issue_date") != date_str]
            if dups:
                log(f"⚠ REPEAT DETECTION: fingerprint matches {dups[0]['issue_date']} — same stories as a recent issue")
                base_payload["repeat_of_issue_date"] = dups[0]["issue_date"]
        except Exception as dup_e:
            log(f"Repeat detection check error (non-fatal): {dup_e}")

    try:
        # Check whether a row already exists for today
        chk = requests.get(
            f"{SUPABASE_URL}/rest/v1/meridian_issues",
            params={"select": "id", "issue_date": f"eq.{date_str}"},
            headers=SB_HEADERS,
        )
        existing = chk.json() if chk.status_code == 200 else []

        # One Issue per day — never overwrite an existing day's Issue unless
        # explicitly forced. (Belt-and-suspenders behind the entry-point guard.)
        import sys as _sys
        _force = ("--force" in _sys.argv) or (os.environ.get("MERIDIAN_FORCE", "").lower() in ("1", "true", "yes"))
        if existing and not _force:
            log(f"Issue for {date_str} already exists (id={existing[0]['id']}) — keeping the original, NOT overwriting. "
                f"Use --force to replace it.")
            return

        if existing:
            # PATCH the existing row in-place (only reached with --force)
            row_id = existing[0]["id"]
            r = requests.patch(
                f"{SUPABASE_URL}/rest/v1/meridian_issues",
                params={"id": f"eq.{row_id}"},
                headers={**SB_HEADERS, "Prefer": "return=minimal"},
                json=base_payload,
            )
            verb = "Updated (forced)"
        else:
            # INSERT brand-new row
            r = requests.post(
                f"{SUPABASE_URL}/rest/v1/meridian_issues",
                headers={**SB_HEADERS, "Prefer": "return=minimal"},
                json={"issue_date": date_str, **base_payload},
            )
            verb = "Inserted"

        if r.status_code in (200, 201, 204):
            log(f"{verb} issue {date_str} in Supabase meridian_issues ✓ (plan_json={'yes' if plan else 'no'}, fingerprint={content_fingerprint[:12] if content_fingerprint else 'none'}…)")
        else:
            log(f"Supabase save warning {r.status_code}: {r.text[:200]}")
    except Exception as e:
        log(f"Supabase save error (non-fatal): {e}")


# ── Commit HTML to GitHub Pages via blob API ─────────────────────────────────
def sync_catalyst_outcomes(plan: dict, intel: list):
    """
    G4 Feedback Loop: After generating the Issue, scan recent intel for confirmed
    data readouts and mark matching catalysts as resolved in Supabase.

    Logic:
      1. Build a set of drug/company names that had data events this week
         (intel items with catalyst_type='readout' or importance='high' + keywords)
      2. For each, find unresolved catalysts in the DB for that drug/company
      3. If the catalyst label matches the intel signal, mark resolved

    This closes the loop: Issue reads catalysts → Issue generates → Issue resolves
    catalysts that are now confirmed events.
    """
    if not plan or not intel:
        return

    # Keywords that indicate a catalyst resolved
    RESOLVE_SIGNALS = [
        "positive", "met primary", "statistically significant", "approved",
        "phase 3 complete", "topline", "data readout", "presented at",
        "published", "fda approved", "ema approved", "nda filed", "bla filed",
        "phase 2b results", "phase 3 results", "pivotal trial",
    ]

    resolved_count = 0
    now_str = datetime.datetime.utcnow().isoformat()

    # Build drug name → drug_id mapping from plan
    drug_signals: dict[str, str] = {}  # drug_name_lower → drug_id
    company_signals: list[str] = []    # company_ids featured

    if isinstance(plan, dict):
        for section in plan.get("sections", []):
            for drug_id in section.get("drug_ids", []):
                drug_signals[drug_id.lower()] = drug_id
            for co_id in section.get("company_ids", []):
                company_signals.append(co_id)

    # Scan recent intel for resolution signals
    for item in intel:
        headline = (item.get("headline") or "").lower()
        body = (item.get("body") or "").lower()
        text = headline + " " + body

        # Check if this intel item confirms a catalyst resolved
        has_signal = any(kw in text for kw in RESOLVE_SIGNALS)
        if not has_signal:
            continue

        importance = item.get("importance", "")
        if importance not in ("high", "critical"):
            continue

        # Find drug IDs mentioned in this intel item
        for drug_id in drug_signals.values():
            if drug_id.lower() in text or drug_id.replace("-", " ").lower() in text:
                # Look for unresolved catalysts for this drug
                try:
                    r = requests.get(
                        f"{SUPABASE_URL}/rest/v1/catalysts",
                        headers=SB_HEADERS,
                        params={
                            "drug_id": f"eq.{drug_id}",
                            "resolved": "eq.false",
                            "significance": "in.(high,critical)",
                            "select": "id,label,drug_id",
                            "limit": "5",
                        },
                        timeout=10,
                    )
                    cats = r.json() if r.status_code == 200 else []
                    for cat in cats:
                        cat_label = (cat.get("label") or "").lower()
                        # Only resolve if there's label overlap with the intel headline
                        label_words = set(cat_label.split())
                        headline_words = set(headline.split())
                        overlap = label_words & headline_words - {"a","the","in","of","for","and","with","or","to","from"}
                        if len(overlap) >= 2:  # meaningful overlap
                            outcome = (item.get("headline") or "")[:200]
                            requests.patch(
                                f"{SUPABASE_URL}/rest/v1/catalysts",
                                headers={**SB_HEADERS, "Prefer": "return=minimal"},
                                params={"id": f"eq.{cat['id']}"},
                                json={"resolved": True, "resolved_note": f"[auto] Meridian Issue: {outcome}",
                                      "catalyst_status": "resolved", "staleness_status": "stale"},
                                timeout=10,
                            )
                            log(f"  [sync_catalyst] Resolved catalyst for {drug_id}: {cat['label'][:60]}")
                            resolved_count += 1
                except Exception as e:
                    log(f"  [sync_catalyst warn] {drug_id}: {e}")

    if resolved_count:
        log(f"sync_catalyst_outcomes: resolved {resolved_count} catalysts from today's intel")
    else:
        log("sync_catalyst_outcomes: no matching resolved catalysts (normal — most issues are monitoring, not readout)")


def inject_feedback_widget(html, issue_date):
    """Inject the in-issue reader-feedback widget (per-section 👍/👎 + notes, inline
    selection comments, and an overall feedback panel) into the generated issue HTML.

    Lives ONLY inside the Meridian issue document — which renders solely in the
    'Today's Issue' tab (iframe → meridian_today.html / srcdoc for archived issues).
    The home tab uses a separate reader list and never embeds this document, so the
    widget never appears on the home page.

    Writes go to public.meridian_feedback with the PUBLIC anon key (write-only via RLS).
    Hidden in print. Fails silent if Supabase is unreachable.
    """
    css = """
<style id="mf-styles">
.mf-ctl{display:inline-flex;gap:6px;align-items:center;margin:8px 0 2px;vertical-align:middle;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}
.mf-btn{cursor:pointer;border:1px solid #d9dee8;background:#fff;border-radius:7px;padding:2px 9px;font-size:12px;line-height:1.5;color:#64748b;transition:all .12s;user-select:none}
.mf-btn:hover{border-color:#a78bfa;color:#6d28d9}
.mf-btn.mf-on-up{background:#ecfdf5;border-color:#10b981;color:#047857}
.mf-btn.mf-on-down{background:#fef2f2;border-color:#ef4444;color:#b91c1c}
.mf-note-wrap{margin:6px 0 12px;display:none}
.mf-note-wrap.mf-open{display:block}
.mf-ta{width:100%;max-width:640px;min-height:54px;border:1px solid #d9dee8;border-radius:8px;padding:8px 10px;font:13px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;resize:vertical;display:block}
.mf-save{margin-top:6px;cursor:pointer;border:none;background:#6d28d9;color:#fff;border-radius:7px;padding:5px 13px;font-size:12px;font-weight:600}
.mf-save:hover{background:#5b21b6}
.mf-sel-pop{position:absolute;z-index:99999;display:none;background:#0d1f38;border-radius:8px;box-shadow:0 6px 20px rgba(0,0,0,.25)}
.mf-sel-pop button{cursor:pointer;border:none;background:transparent;color:#fff;font-size:12px;font-weight:600;padding:6px 11px}
.mf-toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#0d1f38;color:#fff;padding:9px 16px;border-radius:9px;font:13px -apple-system,sans-serif;opacity:0;transition:opacity .2s;z-index:99999;pointer-events:none}
.mf-toast.mf-show{opacity:1}
.mf-fab{position:fixed;bottom:18px;right:18px;z-index:99998;background:#6d28d9;color:#fff;border:none;border-radius:24px;padding:10px 16px;font:600 13px -apple-system,sans-serif;cursor:pointer;box-shadow:0 6px 18px rgba(109,40,217,.35)}
.mf-panel{position:fixed;bottom:64px;right:18px;z-index:99998;width:320px;max-width:90vw;background:#fff;border:1px solid #e2e8f0;border-radius:12px;box-shadow:0 12px 40px rgba(2,6,23,.2);padding:14px;display:none}
.mf-panel.mf-open{display:block}
.mf-panel h4{font:700 13px -apple-system,sans-serif;color:#0d1f38;margin:0 0 8px}
@media print{.mf-ctl,.mf-fab,.mf-panel,.mf-sel-pop,.mf-toast,.mf-note-wrap{display:none!important}}
</style>
"""
    js = """
<script id="mf-feedback">
(function(){
  var SB="%%URL%%",KEY="%%KEY%%",ISSUE_DATE="%%DATE%%";
  function post(b){b.issue_date=ISSUE_DATE;b.issue_id=(window.__MERIDIAN_ISSUE_ID__||null);b.page_url=location.href;b.user_agent=(navigator.userAgent||"").slice(0,300);
    return fetch(SB+"/rest/v1/meridian_feedback",{method:"POST",headers:{"apikey":KEY,"Authorization":"Bearer "+KEY,"Content-Type":"application/json","Prefer":"return=minimal"},body:JSON.stringify(b)});}
  function toast(m){var t=document.querySelector(".mf-toast");if(!t){t=document.createElement("div");t.className="mf-toast";document.body.appendChild(t);}t.textContent=m;t.classList.add("mf-show");setTimeout(function(){t.classList.remove("mf-show");},1700);}
  function lbl(h){return (h.textContent||"").trim().replace(/\\s+/g," ").slice(0,180);}
  function attach(h,idx){
    if(h.getAttribute("data-mf"))return;h.setAttribute("data-mf","1");
    var ctl=document.createElement("div");ctl.className="mf-ctl";
    var up=document.createElement("span");up.className="mf-btn";up.textContent="\\uD83D\\uDC4D";up.title="Helpful";
    var dn=document.createElement("span");dn.className="mf-btn";dn.textContent="\\uD83D\\uDC4E";dn.title="Not useful";
    var nb=document.createElement("span");nb.className="mf-btn";nb.textContent="\\uD83D\\uDCAC note";
    var wrap=document.createElement("div");wrap.className="mf-note-wrap";
    var ta=document.createElement("textarea");ta.className="mf-ta";ta.placeholder="What works or doesn't in this section?";
    var sv=document.createElement("button");sv.className="mf-save";sv.textContent="Save note";
    wrap.appendChild(ta);wrap.appendChild(sv);
    up.onclick=function(){post({section_index:idx,section_label:lbl(h),vote:"up"}).then(function(r){if(r.ok){up.classList.add("mf-on-up");dn.classList.remove("mf-on-down");toast("Marked helpful");}else toast("Couldn't save");}).catch(function(){toast("Couldn't save");});};
    dn.onclick=function(){post({section_index:idx,section_label:lbl(h),vote:"down"}).then(function(r){if(r.ok){dn.classList.add("mf-on-down");up.classList.remove("mf-on-up");toast("Marked not useful");}else toast("Couldn't save");}).catch(function(){toast("Couldn't save");});};
    nb.onclick=function(){wrap.classList.toggle("mf-open");if(wrap.classList.contains("mf-open"))ta.focus();};
    sv.onclick=function(){var c=ta.value.trim();if(!c){toast("Write a note first");return;}post({section_index:idx,section_label:lbl(h),comment:c}).then(function(r){if(r.ok){toast("Note saved");ta.value="";wrap.classList.remove("mf-open");}else toast("Couldn't save");}).catch(function(){toast("Couldn't save");});};
    ctl.appendChild(up);ctl.appendChild(dn);ctl.appendChild(nb);
    h.parentNode.insertBefore(ctl,h.nextSibling);h.parentNode.insertBefore(wrap,ctl.nextSibling);
  }
  function init(){
    var hs=document.querySelectorAll("h2,h3");for(var i=0;i<hs.length;i++)attach(hs[i],i);
    var pop=document.createElement("div");pop.className="mf-sel-pop";var pb=document.createElement("button");pb.textContent="\\uD83D\\uDCAC Comment";pop.appendChild(pb);document.body.appendChild(pop);
    var lastSel="";
    document.addEventListener("mouseup",function(){setTimeout(function(){var s=window.getSelection();var t=s&&s.toString().trim();
      if(t&&t.length>3&&t.length<800){lastSel=t;var r=s.getRangeAt(0).getBoundingClientRect();pop.style.top=(window.scrollY+r.top-40)+"px";pop.style.left=(window.scrollX+r.left)+"px";pop.style.display="block";}
      else if(!pop.contains(document.activeElement))pop.style.display="none";},10);});
    pb.onclick=function(){var c=prompt("Comment on:\\n\\n\\u201c"+lastSel.slice(0,160)+(lastSel.length>160?"\\u2026":"")+"\\u201d\\n\\nYour note:");
      if(c&&c.trim())post({section_label:"(inline selection)",selected_text:lastSel.slice(0,800),comment:c.trim()}).then(function(r){toast(r.ok?"Comment saved":"Couldn't save");}).catch(function(){toast("Couldn't save");});pop.style.display="none";};
    var fab=document.createElement("button");fab.className="mf-fab";fab.textContent="\\uD83D\\uDCAC Feedback";document.body.appendChild(fab);
    var panel=document.createElement("div");panel.className="mf-panel";panel.innerHTML="<h4>Feedback on this issue</h4>";
    var pta=document.createElement("textarea");pta.className="mf-ta";pta.placeholder="Overall thoughts on today's issue\\u2026";
    var psv=document.createElement("button");psv.className="mf-save";psv.textContent="Send";
    panel.appendChild(pta);panel.appendChild(psv);document.body.appendChild(panel);
    fab.onclick=function(){panel.classList.toggle("mf-open");if(panel.classList.contains("mf-open"))pta.focus();};
    psv.onclick=function(){var c=pta.value.trim();if(!c){toast("Write something first");return;}post({section_label:"(overall)",comment:c}).then(function(r){if(r.ok){toast("Thanks \\u2014 feedback sent");pta.value="";panel.classList.remove("mf-open");}else toast("Couldn't save");}).catch(function(){toast("Couldn't save");});};
  }
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);else init();
})();
</script>
"""
    js = (js.replace("%%URL%%", SUPABASE_URL)
            .replace("%%KEY%%", SUPABASE_ANON_KEY)
            .replace("%%DATE%%", issue_date))
    if "</head>" in html:
        html = html.replace("</head>", css + "</head>", 1)
    else:
        html = css + html
    if "</body>" in html:
        html = html.replace("</body>", js + "</body>", 1)
    else:
        html = html + js
    return html


def deploy_to_github(html_content, filename="meridian_today.html"):
    api = f"https://api.github.com/repos/{GITHUB_REPO}"
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")

    ref_r = requests.get(f"{api}/git/ref/heads/main", headers=GH_HEADERS)
    ref_r.raise_for_status()
    head_sha = ref_r.json()["object"]["sha"]

    # ── Guard: skip if today's issue was already committed ────────────────────
    # Checks the last commit touching meridian_today.html. If it already
    # has today's date in the message, this is a duplicate run — skip.
    import sys as _sys
    _force = ("--force" in _sys.argv) or (os.environ.get("MERIDIAN_FORCE", "").lower() in ("1", "true", "yes"))
    try:
        recent = requests.get(
            f"https://api.github.com/repos/{GITHUB_REPO}/commits",
            headers=GH_HEADERS,
            params={"path": filename, "per_page": 1},
            timeout=10,
        )
        if recent.status_code == 200 and recent.json():
            last_msg = recent.json()[0]["commit"]["message"]
            if today in last_msg and "[auto]" in last_msg and not _force:
                log(f"Skipping deploy — today's issue already committed ({last_msg[:60]}). "
                    f"Use workflow_dispatch with force=true to override.")
                return
            if _force and today in last_msg:
                log("Force flag set — re-deploying over today's existing issue commit.")
    except Exception as _guard_err:
        log(f"[WARN] Could not check last commit: {_guard_err} — proceeding with deploy")

    commit_r = requests.get(f"{api}/git/commits/{head_sha}", headers=GH_HEADERS)
    commit_r.raise_for_status()
    base_tree_sha = commit_r.json()["tree"]["sha"]

    blob_r = requests.post(f"{api}/git/blobs", headers=GH_HEADERS, json={
        "content":  base64.b64encode(html_content.encode()).decode(),
        "encoding": "base64",
    })
    blob_r.raise_for_status()
    blob_sha = blob_r.json()["sha"]

    tree_r = requests.post(f"{api}/git/trees", headers=GH_HEADERS, json={
        "base_tree": base_tree_sha,
        "tree": [{"path": filename, "mode": "100644", "type": "blob", "sha": blob_sha}],
    })
    tree_r.raise_for_status()
    new_tree_sha = tree_r.json()["sha"]

    commit_post = requests.post(f"{api}/git/commits", headers=GH_HEADERS, json={
        "message": f"Meridian issue {today} [auto]",
        "tree":    new_tree_sha,
        "parents": [head_sha],
    })
    commit_post.raise_for_status()
    new_commit_sha = commit_post.json()["sha"]

    patch_r = requests.patch(f"{api}/git/refs/heads/main", headers=GH_HEADERS, json={
        "sha": new_commit_sha, "force": False,
    })
    patch_r.raise_for_status()
    log(f"Deployed {filename} → commit {new_commit_sha[:7]}")


# ── Editorial → Enrichment Priority Bump ─────────────────────────────────────
def bump_editorial_priority(company_ids: list, boost: int = 10):
    """
    Bump priority_score for companies featured in today's Meridian.

    Meridian editorial judgment is the strongest signal for BD relevance.
    If a company appears in the briefing, it should be among the first to
    re-enrich. This function finds the company's research_queue row and
    applies a +boost to priority_score, capped at 100.

    Falls back gracefully: if research_queue doesn't have a row for a company,
    no error is raised.
    """
    if not company_ids:
        return

    bumped = []
    errors = []
    for co_id in company_ids:
        try:
            r = requests.get(
                f"{SUPABASE_URL}/rest/v1/research_queue",
                headers=SB_HEADERS,
                params={"company_id": f"eq.{co_id}", "select": "id,company_id,priority_score", "limit": "1"},
                timeout=10,
            )
            rows = r.json() if r.status_code == 200 else []
            if not rows:
                continue  # Company not in research_queue — skip silently

            row = rows[0]
            current_score = row.get("priority_score") or 0
            new_score     = min(100, current_score + boost)

            patch_r = requests.patch(
                f"{SUPABASE_URL}/rest/v1/research_queue",
                headers={**SB_HEADERS, "Prefer": "return=minimal"},
                params={"id": f"eq.{row['id']}"},
                json={"priority_score": new_score, "updated_at": datetime.datetime.utcnow().isoformat()},
                timeout=10,
            )
            if patch_r.status_code in (200, 204):
                bumped.append(f"{co_id}:{current_score}→{new_score}")
        except Exception as e:
            errors.append(f"{co_id}: {e}")

    if bumped:
        log(f"Editorial priority bumps (+{boost}): {', '.join(bumped)}")
    if errors:
        log(f"Priority bump errors (non-fatal): {'; '.join(errors)}")


# ── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys
    log(f"=== Meridian Writer — {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} ===")

    # ── One Issue per day ─────────────────────────────────────────────────────
    # The Writer is triggered twice daily (chained off Meridian Research, plus a
    # 6:30 ET fallback cron) — and can also be dispatched manually. Without this
    # guard it regenerates (full LLM pass + republish) each time. If today's Issue
    # already exists, skip; the fallback cron only does work when the chain didn't.
    # Override with --force or MERIDIAN_FORCE=1.
    _FORCE = ("--force" in _sys.argv) or (os.environ.get("MERIDIAN_FORCE", "").lower() in ("1", "true", "yes"))
    _today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    if not _FORCE:
        try:
            _r = requests.get(
                f"{SUPABASE_URL}/rest/v1/meridian_issues",
                headers=SB_HEADERS,
                params={"issue_date": f"eq.{_today}", "select": "id,created_at"},
                timeout=15)
            _existing = _r.json() if _r.status_code == 200 else []
            if _existing:
                log(f"Issue for {_today} already generated (id={_existing[0].get('id')}). "
                    f"Skipping — only one Issue is produced per day. "
                    f"Use --force or MERIDIAN_FORCE=1 to regenerate.")
                _sys.exit(0)
        except Exception as _e:
            log(f"Same-day guard check failed (continuing to generate): {_e}")

    # Close the trust loop: feed content-disconfirmed claims (content_confirms_claim
    # = false, set by the Content Verifier) into the writer's system prompt so they
    # are withheld from the Issue — claim-level, so real molecules keep their facts.
    SYSTEM_PROMPT = SYSTEM_PROMPT + build_verification_cautions()

    # Close the editorial loop: feed the reader's own in-issue feedback (👍/👎 + notes
    # from meridian_feedback) back into the writer so each issue responds to real taste.
    SYSTEM_PROMPT = SYSTEM_PROMPT + build_reader_feedback_block()

    # Fetch all data sources — the full dashboard state feeds the Meridian
    intel                              = fetch_recent_intel(hours_back=48)
    deals                              = fetch_recent_deals(days_back=7)
    catalysts                          = fetch_upcoming_catalysts()
    catalyst_calendar_events           = fetch_catalyst_calendar(days_ahead=365)
    bd_priority_data                   = fetch_bd_priority_companies()
    drugs, companies                   = fetch_drug_context()
    ailux_positions                    = fetch_ailux_position()
    recent_issues                      = fetch_recent_meridian_issues(n=7)
    company_signals                    = fetch_company_signals()
    trials                             = fetch_recent_trials()
    graph_active_in, graph_targets, graph_competes = fetch_graph_context()

    log(f"Data assembled: {len(intel)} intel · {len(deals)} deals · {len(catalysts)} catalysts · "
        f"{len(catalyst_calendar_events)} cal events · "
        f"{len(bd_priority_data.get('scores',[]))} very_high scores · "
        f"{len(bd_priority_data.get('views',[]))} strategic views · "
        f"{len(company_signals)} signals · {len(trials)} trials · {len(recent_issues)} prior issues · "
        f"graph: {sum(len(v) for v in graph_active_in.values())} ACTIVE_IN / "
        f"{len(graph_targets)} TARGETS / {len(graph_competes)} COMPETES_WITH")

    if not intel:
        log("No intel found — writing placeholder issue.")
        html         = (
            "<!DOCTYPE html><html><head><meta charset='UTF-8'><title>The Meridian</title></head>"
            "<body><h1 style='color:#1a3f8f;font-family:Georgia,serif'>The Meridian</h1>"
            f"<p style='font-family:Georgia,serif'>No significant biopharma intelligence collected in the last 48 hours "
            f"for today, {datetime.datetime.utcnow().strftime('%B %-d, %Y')}. "
            "Check back tomorrow.</p></body></html>"
        )
        plan                = None
        plan_company_ids    = []
        content_fingerprint = None
    else:
        html, plan, plan_company_ids, content_fingerprint = generate_html(
            intel, deals, catalysts, drugs, companies, ailux_positions,
            recent_issues, company_signals, trials,
            graph_active_in=graph_active_in,
            graph_targets=graph_targets,
            graph_competes=graph_competes,
            catalyst_calendar_events=catalyst_calendar_events,
            bd_priority_data=bd_priority_data,
        )

    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    save_to_supabase(html, intel, today,
                     plan=plan,
                     company_ids=plan_company_ids,
                     content_fingerprint=content_fingerprint)

    # Publish the Issue FIRST. The page deploy is the critical output and must
    # not be blocked by the optional post-processing below. (Root cause of the
    # 2026-06-03+ Writer failures: a post-save feedback-loop step raised after the
    # Issue was already saved to Supabase — which crashed the run BEFORE this
    # deploy, so meridian_today.html never published and the workflow went red.)
    deploy_to_github(html)

    # ── Editorial → Enrichment Priority Bump (best-effort) ────────────────────
    # Companies featured in today's Meridian are the most BD-relevant right now.
    # Bump their priority_score in research_queue by +10 so the next enrichment
    # scheduler run picks them up first. Never fail the publish over this.
    try:
        if plan_company_ids:
            bump_editorial_priority(plan_company_ids)
    except Exception as e:
        log(f"bump_editorial_priority failed (non-fatal): {e}")

    # ── G4: Catalyst outcome sync (best-effort) ───────────────────────────────
    # Scan today's intel for confirmed readouts and resolve matching catalysts.
    try:
        sync_catalyst_outcomes(plan, intel)
    except Exception as e:
        log(f"sync_catalyst_outcomes failed (non-fatal): {e}")

    # ── S3: stamp system_status so the dashboard surfaces the new Issue ───────
    try:
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        requests.patch(
            f"{SUPABASE_URL}/rest/v1/system_status",
            headers={**SB_HEADERS, "Prefer": "return=minimal"},
            params={"id": "eq.1"},
            json={"last_meridian_at": now_iso, "updated_at": now_iso,
                  "last_pipeline_label": "meridian_write",
                  "note": "New Meridian Issue published"},
            timeout=15)
        log("system_status stamped (meridian_write)")
    except Exception as e:
        log(f"system_status stamp failed (non-fatal): {e}")

    # Pre-publish fact-check summary + governance log (what the gate excluded today)
    fact_check_report()

    log("=== Write complete ===")
