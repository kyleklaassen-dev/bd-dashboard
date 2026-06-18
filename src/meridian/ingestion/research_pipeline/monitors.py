#!/usr/bin/env python3
"""
Phase 9/10 competitive monitors (§3 research split): asset-differentiation-profile
staleness check + bispecific competitive monitor. Extracted verbatim.
"""

import datetime

import requests

from meridian.ingestion.research_pipeline.common import log, SUPABASE_URL, SUPABASE_KEY


# ── Phase 9: Asset differentiation profile staleness check ───────────────────
# Queries asset_differentiation_profiles for last_updated timestamps, then
# checks intelligence_discoveries and research_queue for recent competitor
# events touching ALX001/ALX002/ALX005 competitor programs.
# Flags profiles where a relevant competitor update is newer than last_updated
# and writes a research_queue item for human review.

ASSET_COMPETITOR_MAP = {
    "alx001": ["SPY072", "tulisokibart", "RO7837195", "SIM0709", "duvakitug", "risankizumab", "mirikizumab"],
    "alx002": ["KT501", "CLN-978", "HXN-1031", "CND460", "belimumab", "anifrolumab"],
    "alx005": ["efgartigimod", "rozanolixizumab", "nipocalimab", "IMVT-1402", "batoclimab"],
}

def _run_asset_profile_staleness_check():
    """Check if any asset_differentiation_profiles need KOL Q&A refresh based on recent competitor intel."""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }

    # Fetch current profile timestamps
    prof_resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/asset_differentiation_profiles",
        headers=headers,
        params={"select": "program_id,last_updated"},
        timeout=15,
    )
    if prof_resp.status_code != 200:
        log(f"  Phase 9: could not fetch profiles ({prof_resp.status_code})")
        return

    profiles = {p["program_id"]: p["last_updated"] for p in prof_resp.json()}

    # Fetch recent intelligence_discoveries (last 14 days)
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
    intel_resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/intelligence_discoveries",
        headers=headers,
        params={"select": "drug_name,discovery_text,created_at", "created_at": f"gte.{cutoff}", "limit": "200"},
        timeout=15,
    )
    recent_intel = intel_resp.json() if intel_resp.status_code == 200 else []

    flagged = []
    for program_id, competitors in ASSET_COMPETITOR_MAP.items():
        profile_ts = profiles.get(program_id)
        if not profile_ts:
            continue
        for item in recent_intel:
            drug = (item.get("drug_name") or "").lower()
            text = (item.get("discovery_text") or "").lower()
            created = item.get("created_at", "")
            # Check if this intel mentions a competitor for this program
            if any(c.lower() in drug or c.lower() in text for c in competitors):
                # Check if intel is newer than profile
                if created > profile_ts:
                    flagged.append({
                        "program_id": program_id,
                        "competitor_trigger": drug or "unknown",
                        "intel_date": created,
                        "profile_updated": profile_ts,
                    })
                    break  # one flag per program is enough

    if flagged:
        log(f"  Phase 9: {len(flagged)} program(s) flagged for profile review: {[f['program_id'] for f in flagged]}")
        # Write to research_queue
        queue_rows = []
        for f in flagged:
            queue_rows.append({
                "queue_type": "asset_profile_review",
                "drug_name": f["program_id"].upper(),
                "priority": "medium",
                "notes": (
                    f"Competitor update detected for {f['program_id'].upper()} profile. "
                    f"Trigger: {f['competitor_trigger']} ({f['intel_date'][:10]}). "
                    f"Profile last updated: {f['profile_updated'][:10]}. "
                    "Review KOL Q&A and pharma_bd_objections for accuracy."
                ),
                "status": "pending",
            })
        if queue_rows:
            rq_resp = requests.post(
                f"{SUPABASE_URL}/rest/v1/research_queue",
                headers={**headers, "Prefer": "resolution=merge-duplicates"},
                json=queue_rows,
                timeout=15,
            )
            if rq_resp.status_code in (200, 201):
                log(f"  Phase 9: {len(queue_rows)} research_queue item(s) written for human review")
            else:
                log(f"  Phase 9: research_queue write failed ({rq_resp.status_code})")
    else:
        log("  Phase 9: all asset profiles current — no staleness flags")


# ── Phase 10: Bispecific Competitive Monitor ──────────────────────────────────
# Watches for readout events from competing TL1A×IL-23 bispecifics and other
# bispecifics competing with ALX001. Queries catalyst_calendar + drug_timeline_estimates
# for imminent readouts and creates research_queue items + flags drug_intelligence_qa
# for update when competitor data is newly available.

BISPECIFIC_WATCH_LIST = [
    # drug_id, common names, watch_event, expected_date, priority
    {
        "drug_id": "mt-251",
        "names": ["MT-251", "mt-251", "mountainview"],
        "watch_event": "Phase 1 primary readout",
        "expected_date": "2027-03-01",
        "priority": "P0",
        "rationale": "TL1A×IL-23p19 bispecific — closest mechanism match to ALX001; Phase 1 primary data defines class safety profile",
    },
    {
        "drug_id": "ro7837195",
        "names": ["RO7837195", "ro7837195", "roche-pfizer", "RG6462"],
        "watch_event": "Phase 2b primary readout",
        "expected_date": "2027-08-01",
        "priority": "P0",
        "rationale": "IL-23p40×TL1A bispecific (Roche/Pfizer) — first bispecific Phase 2b readout in class; will establish bispecific efficacy benchmark",
    },
    {
        "drug_id": "spy072",
        "names": ["SPY072", "spy072", "SPY001", "spyre", "Spyre Therapeutics"],
        "watch_event": "Spyre platform study Phase 2 update",
        "expected_date": "2028-06-01",
        "priority": "P0",
        "rationale": "Spyre platform: monoAb vs combination arms — will be first direct test of bispecific hypothesis; critical for ALX001 positioning",
    },
    {
        "drug_id": "apg333",
        "names": ["APG333", "apg333", "AscentagePharma"],
        "watch_event": "Phase 1 safety/PK readout",
        "expected_date": "2026-12-01",
        "priority": "P1",
        "rationale": "TL1A-based bispecific in Phase 1; earlier safety data could shift class risk perception",
    },
    {
        "drug_id": "tulisokibart",
        "names": ["tulisokibart", "MK-7240", "PRA023", "ATLAS-UC", "atlas-uc"],
        "watch_event": "ATLAS-UC Phase 3 primary readout",
        "expected_date": "2026-11-01",
        "priority": "P0",
        "rationale": "TL1A monoAb Phase 3 readout — defines TL1A class efficacy ceiling and regulatory bar; directly sets ALX001 Phase 2 success threshold",
    },
    {
        "drug_id": "duvakitug",
        "names": ["duvakitug", "QP110", "Sanofi", "duvak"],
        "watch_event": "Phase 3 primary readout",
        "expected_date": "2027-06-01",
        "priority": "P1",
        "rationale": "Second TL1A monoAb Phase 3; confirms or modifies tulisokibart efficacy benchmark",
    },
]

# Number of days before expected_date to flag as "imminent"
BISPECIFIC_IMMINENT_DAYS = 90


def _run_bispecific_competitive_monitor():
    """
    Phase 10: Bispecific competitive event monitor.

    1. For each drug in BISPECIFIC_WATCH_LIST, checks how close we are to the
       watch_event expected_date.
    2. If within BISPECIFIC_IMMINENT_DAYS days: writes a research_queue item
       (priority P0 or P1) to flag for active monitoring.
    3. Checks intelligence_discoveries + news_articles for any recent mention of
       the drug that might indicate data has been published early or leaked.
    4. If recent data detected: flags drug_intelligence_qa rows for the drug
       (competitive Q66-Q80) by setting needs_update=TRUE.
    5. Also checks catalyst_calendar and drug_timeline_estimates for any
       newly resolved catalyst events.
    """
    log("--- Phase 10: Bispecific Competitive Monitor ---")

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }

    today = datetime.datetime.utcnow().date()
    flagged_imminent = []
    flagged_data_detected = []

    # Step 1: Check proximity to expected readout dates
    for watch in BISPECIFIC_WATCH_LIST:
        try:
            expected = datetime.date.fromisoformat(watch["expected_date"])
            days_until = (expected - today).days
            if 0 <= days_until <= BISPECIFIC_IMMINENT_DAYS:
                flagged_imminent.append({**watch, "days_until": days_until})
                log(f"  IMMINENT: {watch['drug_id']} — {watch['watch_event']} in {days_until} days")
            elif days_until < 0:
                log(f"  PAST DUE: {watch['drug_id']} — {watch['watch_event']} was expected {-days_until} days ago (check if data published)")
                # Past due = check for actual data below
                flagged_imminent.append({**watch, "days_until": days_until, "past_due": True})
        except Exception as exc:
            log(f"  Date parse error for {watch['drug_id']}: {exc}")
            continue

    # Step 2: Check intelligence_discoveries for recent mentions of watch drugs
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        intel_resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/intelligence_discoveries",
            headers=headers,
            params={
                "select": "drug_name,discovery_text,created_at,headline",
                "created_at": f"gte.{cutoff}",
                "limit": "300",
            },
            timeout=15,
        )
        recent_intel = intel_resp.json() if intel_resp.status_code == 200 else []
    except Exception:
        recent_intel = []

    # Step 3: Check news_articles for recent mentions
    try:
        news_resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/news_articles",
            headers=headers,
            params={
                "select": "title,body,published_at",
                "published_at": f"gte.{cutoff}",
                "limit": "200",
            },
            timeout=15,
        )
        recent_news = news_resp.json() if news_resp.status_code == 200 else []
    except Exception:
        recent_news = []

    # Data detection keywords — indicate actual trial data has been reported
    DATA_KEYWORDS = [
        "phase 2", "phase 3", "primary endpoint", "clinical remission", "topline",
        "readout", "data", "results", "trial met", "trial failed", "dose response",
        "efficacy", "asco", "ddw", "ueg", "ecco", "nejm", "lancet", "gastroenterology",
    ]

    for watch in BISPECIFIC_WATCH_LIST:
        drug_names_lower = [n.lower() for n in watch["names"]]
        mentions = []

        for item in recent_intel:
            drug = (item.get("drug_name") or "").lower()
            text = (item.get("discovery_text") or "").lower() + " " + (item.get("headline") or "").lower()
            if any(n in drug or n in text for n in drug_names_lower):
                has_data_keyword = any(kw in text for kw in DATA_KEYWORDS)
                mentions.append({"source": "intelligence_discoveries", "has_data": has_data_keyword, "date": item.get("created_at", "")})

        for item in recent_news:
            text = ((item.get("title") or "") + " " + (item.get("body") or "")).lower()
            if any(n in text for n in drug_names_lower):
                has_data_keyword = any(kw in text for kw in DATA_KEYWORDS)
                mentions.append({"source": "news_articles", "has_data": has_data_keyword, "date": item.get("published_at", "")})

        if mentions:
            has_data_mention = any(m["has_data"] for m in mentions)
            log(f"  MENTION: {watch['drug_id']} — {len(mentions)} recent mention(s), data_keywords={has_data_mention}")
            if has_data_mention:
                flagged_data_detected.append({**watch, "mentions": len(mentions)})

    # Step 4: Write research_queue items for imminent/past-due events
    queue_rows = []
    for f in flagged_imminent:
        days = f["days_until"]
        label = f"PAST DUE ({-days}d)" if days < 0 else f"T-{days}d"
        queue_rows.append({
            "entity_type": "drug",
            "entity_id": f["drug_id"],
            "gap_type": "competitive_readout_imminent",
            "priority": f["priority"],
            "reason": (
                f"[{label}] {f['drug_id'].upper()} — {f['watch_event']}. "
                f"Expected: {f['expected_date']}. Rationale: {f['rationale']}"
            )[:1000],
            "source": "bispecific_competitive_monitor",
            "status": "pending",
        })

    if queue_rows:
        rq = requests.post(
            f"{SUPABASE_URL}/rest/v1/research_queue",
            headers={**headers, "Prefer": "resolution=ignore-duplicates,return=minimal"},
            json=queue_rows,
            timeout=15,
        )
        if rq.status_code in (200, 201):
            log(f"  Phase 10: {len(queue_rows)} research_queue item(s) written (imminent/past-due readouts)")
        else:
            log(f"  Phase 10: research_queue write error: {rq.status_code} {rq.text[:150]}")

    # Step 5: For drugs where data was detected, flag drug_intelligence_qa Q66-Q80
    # (competitive questions) for the ALX001 drug as needs_update=TRUE
    alx001_competitive_qs = list(range(66, 81))  # Q66–Q80 competitive domain
    for f in flagged_data_detected:
        drug_id = f["drug_id"]
        log(f"  Phase 10: Data detected for {drug_id} — flagging ALX001 competitive QA for update")
        # Flag ALX001 competitive Q&A
        for q_id in alx001_competitive_qs:
            try:
                requests.patch(
                    f"{SUPABASE_URL}/rest/v1/drug_intelligence_qa",
                    headers={**headers, "Prefer": "return=minimal"},
                    params={"drug_id": "eq.anti-tl1a-xpf005-arm", "question_id": f"eq.{q_id}"},
                    json={
                        "needs_update": True,
                        "last_researched": datetime.datetime.utcnow().isoformat(),
                    },
                    timeout=10,
                )
            except Exception:
                pass
        log(f"  Phase 10: Flagged Q66-Q80 for ALX001 due to {drug_id} data detection ({f['mentions']} mentions)")

    # Step 6: Check catalyst_calendar for resolved bispecific catalysts
    try:
        catalyst_resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/catalyst_calendar",
            headers=headers,
            params={
                "select": "drug_name,catalyst_date,catalyst_type,resolved,area_id",
                "resolved": "eq.false",
                "limit": "100",
            },
            timeout=15,
        )
        catalysts = catalyst_resp.json() if catalyst_resp.status_code == 200 else []
        bispecific_catalysts = []
        all_names_lower = []
        for w in BISPECIFIC_WATCH_LIST:
            all_names_lower.extend([n.lower() for n in w["names"]])
        for cat in catalysts:
            name = (cat.get("drug_name") or "").lower()
            if any(n in name for n in all_names_lower):
                bispecific_catalysts.append(cat)
        if bispecific_catalysts:
            log(f"  Phase 10: {len(bispecific_catalysts)} unresolved bispecific catalyst(s) in catalyst_calendar")
            for cat in bispecific_catalysts:
                log(f"    - {cat.get('drug_name')} | {cat.get('catalyst_date')} | {cat.get('catalyst_type')}")
        else:
            log("  Phase 10: No unresolved bispecific catalysts in catalyst_calendar")
    except Exception as exc:
        log(f"  Phase 10: catalyst_calendar check error: {exc}")

    total_flagged = len(flagged_imminent) + len(flagged_data_detected)
    log(f"--- Phase 10 complete: {total_flagged} event(s) flagged ---")
