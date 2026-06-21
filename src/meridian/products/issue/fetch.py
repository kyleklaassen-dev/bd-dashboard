#!/usr/bin/env python3
"""
Supabase fetch layer for the Meridian Issue (§3 write_meridian split).
======================================================================
Extracted verbatim from write_meridian.py. All read-only fetch_* helpers that
pull the day's intel/deals/catalysts/drugs/graph/patient context from Supabase
(each fact-check-filtered), plus the three render helpers tightly bound to that
data (patient stats, catalyst calendar, BD-priority blocks). Self-contained.
"""

import datetime

import requests

from meridian.products.issue.common import (
    SUPABASE_URL, SB_HEADERS, AREA_NAMES, log, fact_check_filter,
)


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


def fetch_recent_facts(days_back=14, limit=40):
    """Freshest SOURCED facts from the event-driven research pipeline (intel_facts)
    across Ailux's areas — the deep-research output, including KOL/management quotes.
    Every row carries a real source URL. Fed into the editorial plan so the Meridian
    issue reflects the current research, not just RSS headlines. Fail-soft."""
    try:
        cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=days_back)).isoformat()
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/intel_facts",
            headers=SB_HEADERS,
            params={
                "select": "claim,fact_type,subject_name,value_text,source_url,area_id,created_at",
                "area_id": "in.(tl1a,tslp,il4ra,igf1r,fcrn,tcell)",
                "created_at": f"gte.{cutoff}",
                "source_url": "not.is.null",
                "order": "created_at.desc",
                "limit": str(limit),
            },
        )
        if r.status_code != 200:
            log(f"Recent facts unavailable ({r.status_code}) — skipping")
            return []
        data = r.json()
        if not isinstance(data, list):
            return []
        log(f"Fetched {len(data)} recent deep-research facts")
        return data
    except Exception as e:
        log(f"Recent facts fetch error: {e}")
        return []


def build_recent_facts_block(facts):
    """Render recent sourced facts (incl. KOL/management quotes) as an editorial
    context block. Quotes are flagged so the LLM can attribute them."""
    if not facts:
        return ""
    lines = ["", "## Recent deep-research facts (sourced; event-driven research — use with attribution)"]
    for f in facts[:40]:
        who = f.get("subject_name") or (f.get("area_id") or "")
        val = f" [{f['value_text']}]" if f.get("value_text") else ""
        kind = f.get("fact_type") or "fact"
        tag = "QUOTE" if kind in ("kol_sentiment", "management") else kind
        claim = (f.get("claim") or "")[:260]
        url = f.get("source_url") or ""
        lines.append(f"- ({tag}) {claim}{val} — {who} {url}")
    return "\n".join(lines)


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
