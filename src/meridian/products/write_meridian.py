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
from meridian.database.catalyst_writer import CatalystWriter
import anthropic

# Patient intelligence context (co-equal intelligence layer)
try:
    from patient_intelligence_module import PATIENT_INTELLIGENCE_CONTEXT, build_patient_context_block
    PATIENT_INTEL_AVAILABLE = True
except ImportError:
    PATIENT_INTELLIGENCE_CONTEXT = ""
    build_patient_context_block = lambda items: ""
    PATIENT_INTEL_AVAILABLE = False

# Integration feed (Round 11–17 API data + synthesized strategic_insights layer).
# Read-only; surfaces genetics / patents / regulatory / financing / KOL + the
# distilled insight layer, scoped to the day's entities. Fully guarded: if the
# module or its data is unavailable, the Issue still generates with empty blocks.
try:
    from meridian_integrations_feed import extract_scope_from_intel, render_feed
    INTEGRATIONS_FEED_AVAILABLE = True
except Exception as _feed_err:
    INTEGRATIONS_FEED_AVAILABLE = False
    def extract_scope_from_intel(intel, plan=None):
        return {"drugs": [], "companies": [], "targets": [], "indications": []}
    def render_feed(scope):
        return ("(Integration feed unavailable.)", "(Integration feed unavailable.)")

# ── Shared base — creds, Anthropic client, Supabase/GitHub headers, log,
# AREA_NAMES, and the fact-check gate. Extracted to issue/common.py (§3 split);
# imported here so existing call sites are unchanged.
import re as _re
from meridian.products.issue.common import (
    SUPABASE_URL, SUPABASE_ANON_KEY, GITHUB_REPO,
    client, SB_HEADERS, GH_HEADERS, log, AREA_NAMES,
    fact_check_filter, _FACT_CHECK,
)


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


from meridian.products.issue.fetch import (
    fetch_recent_intel, fetch_recent_deals, fetch_upcoming_catalysts, fetch_drug_context,
    fetch_ailux_position, fetch_recent_meridian_issues, fetch_company_signals,
    fetch_graph_context, fetch_catalyst_calendar, fetch_bd_priority_companies,
    fetch_patient_intelligence_stats, fetch_recent_trials,
    build_patient_stats_block, build_catalyst_calendar_block, build_bd_priority_block,
)


from meridian.products.issue.blocks import (
    enrich_intel_with_drug_context,
    build_intel_block, build_deals_block, build_catalysts_block, build_ailux_block,
    build_prior_coverage_block, build_company_signals_block, build_trials_block, build_graph_block,
)


from meridian.products.issue.prompts import SYSTEM_PROMPT, PLAN_PROMPT, DRAFT_PROMPT


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
                             catalyst_calendar_block="", bd_priority_block="",
                             insights_block="", integration_block=""):
    """Pass 1: produce a tight editorial plan before writing a word of prose."""
    prompt = PLAN_PROMPT.format(
        date_long               = date_long,
        intel_block             = intel_block,
        deals_block             = deals_block,
        ailux_block             = ailux_block,
        prior_block             = prior_block,
        signals_block           = signals_block,
        graph_block             = graph_block or "(Graph context unavailable)",
        insights_block          = insights_block or "(No in-scope strategic insights today)",
        integration_block       = integration_block or "(No in-scope integration data today)",
        patient_context_block   = patient_context_block or "(No patient intelligence context available)",
        patient_stats_block     = patient_stats_block or "(Patient population stats not available — v65 migration may be pending)",
        catalyst_calendar_block = catalyst_calendar_block or "(No catalyst calendar data available)",
        bd_priority_block       = bd_priority_block or "(No BD priority company data available)",
    )
    log("Pass 1 — generating editorial plan (Sonnet)…")
    log(f"Pass 1 prompt length: {len(prompt):,} chars / ~{len(prompt)//4:,} tokens")
    try:
        resp = client.messages.create(
            model      = "claude-opus-4-8",
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
    if plan.get("the_move"):
        lines.append(f"\nTHE MOVE (render as the decision block at the top, right after the lead): {plan['the_move']}")
    if plan.get("forecasts"):
        lines.append("\nFORECASTS (render each with its auditable decomposition where you state the probability):")
        for fc in plan["forecasts"]:
            lines.append(f"  • {fc}")
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

    # Integration feed: resolve today's in-scope entities from the intel, then pull
    # the synthesized insight layer + authoritative integration data (genetics,
    # patents, regulatory, financing, KOL) for just those entities. Fully guarded —
    # any failure degrades to empty blocks and the Issue still generates.
    insights_block = "(No in-scope strategic insights today)"
    integration_block = "(No in-scope integration data today)"
    try:
        feed_scope = extract_scope_from_intel(enriched_intel)
        insights_block, integration_block = render_feed(feed_scope)
        log(f"Integration feed: scope = {len(feed_scope.get('drugs',[]))} drugs / "
            f"{len(feed_scope.get('companies',[]))} companies / "
            f"{len(feed_scope.get('targets',[]))} targets · "
            f"insights {len(insights_block):,} chars · integration {len(integration_block):,} chars")
    except Exception as _fe:
        log(f"Integration feed failed (non-fatal, Issue continues): {type(_fe).__name__}: {_fe}")

    # Pass 1: editorial plan — includes company signals + graph for landscape context
    plan = generate_editorial_plan(date_long, intel_block, deals_block,
                                   ailux_block, prior_block, signals_block,
                                   graph_block=graph_block,
                                   patient_context_block=patient_context,
                                   patient_stats_block=patient_stats_block,
                                   catalyst_calendar_block=catalyst_calendar_block,
                                   bd_priority_block=bd_priority_block,
                                   insights_block=insights_block,
                                   integration_block=integration_block)
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
        insights_block          = insights_block,
        integration_block       = integration_block,
        patient_context_block   = patient_context or "(No patient intelligence context available)",
        patient_stats_block     = patient_stats_block or "(Patient population stats not available — v65 migration may be pending)",
    )

    log("Pass 2 — generating full Meridian draft (Sonnet)…")
    log(f"Pass 2 prompt length: {len(prompt):,} chars / ~{len(prompt)//4:,} tokens")
    try:
        resp = client.messages.create(
            model      = "claude-opus-4-8",
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
                            CatalystWriter().upsert({"id": cat["id"], "resolved": True,
                                "resolved_note": f"[auto] Meridian Issue: {outcome}",
                                "catalyst_status": "resolved", "staleness_status": "stale"})
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
