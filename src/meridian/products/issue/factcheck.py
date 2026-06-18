#!/usr/bin/env python3
"""
Fact-check / verification gates for the Meridian Issue (§3 write_meridian split).
=================================================================================
Extracted verbatim from write_meridian.py. build_verification_cautions +
build_reader_feedback_block inject source-disconfirmed claims and reader feedback
into the writer prompt; fact_check_report logs the pre-publish drop summary;
audit_draft_against_db is the post-draft consistency gate (format vs the drugs table).
"""

import os
import datetime

import requests
import re as _re

from meridian.products.issue.common import SUPABASE_URL, SB_HEADERS, _FACT_CHECK, log


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
