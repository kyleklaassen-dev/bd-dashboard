#!/usr/bin/env python3
"""signal_scoring.py — heuristic relevance scoring for the Signal Monitor (§3 split).
Pure: keyword tables + title extraction + score_signal (headline -> score). No I/O."""
import re

DISEASE_KEYWORDS = [
    "tl1a", "tl1-a", "tnfsf15",
    "tslp", "thymic stromal lymphopoietin",
    "il-4r", "il4r", "il-4 receptor", "dupilumab", "il-13",
    "fcrn", "neonatal fc receptor",
    "igf1r", "igf-1r", "insulin-like growth factor",
    "t-cell", "tcell", "car-t", "t cell",
    "ulcerative colitis", " uc ", "crohn", "ibd", "inflammatory bowel",
    "atopic dermatitis", "eczema", "asthma", "allergic",
    "myasthenia gravis", " mg ", "itp ", "thyroid eye",
]

PHASE_KEYWORDS = [
    "phase 2", "phase 3", "phase ii", "phase iii", "phase 2/3",
    "primary endpoint", "efficacy data", "data readout", "topline", "top-line",
    "clinical data", "pivotal", "approval", "fda approved", "bla", "nda", "sba",
    "nda ", "bla ", "pdufa",
]

DEAL_KEYWORDS = [
    "licens", "acqui", "merger", "deal", "partner", "collaboration",
    "milestone", "upfront", "billion", "million", "agreement",
]

PIPELINE_KEYWORDS = [
    "iND ", "ind filing", "first-in-human", "first in human", "phase 1",
    "phase i ", "ipo", "pipeline", "candidate", "program",
]

def _extract_title_from_html(raw_title: str) -> str:
    """Strip HTML tags from RSS title (FierceBiotech embeds anchors in title)."""
    clean = re.sub(r'<[^>]+>', '', raw_title)
    clean = clean.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
    return clean.strip()


def score_signal(headline: str, source_url: str, signal_type: str, watchlist: dict) -> tuple[int, str | None]:
    """Return (relevance_score 0–10, matched_company_id | None)."""
    hl = headline.lower()
    score = 0
    matched_co: str | None = None

    # ── Company match (most important signal) ────────────────────────────────
    # Use word-boundary matching to avoid "vant" matching "Elevance", etc.
    for alias, co_id in watchlist["alias_map"].items():
        if not alias or len(alias) < 4:
            continue
        # For short aliases (< 8 chars), require word boundaries
        if len(alias) < 8:
            pattern = r'\b' + re.escape(alias) + r'\b'
            if re.search(pattern, hl):
                score += 3
                if matched_co is None:
                    matched_co = co_id
                break
        elif alias in hl:
            score += 3
            if matched_co is None:
                matched_co = co_id
            break

    # ── Drug alias match ─────────────────────────────────────────────────────
    for drug_alias in watchlist["drug_alias_set"]:
        if not drug_alias or len(drug_alias) < 5:
            continue
        if len(drug_alias) < 10:
            pattern = r'\b' + re.escape(drug_alias) + r'\b'
            if re.search(pattern, hl):
                score += 3
                break
        elif drug_alias in hl:
            score += 3
            break

    # ── Disease area keywords ─────────────────────────────────────────────────
    for kw in DISEASE_KEYWORDS:
        if kw in hl:
            score += 2
            break  # only score once per category

    # ── Signal type bonus ─────────────────────────────────────────────────────
    if signal_type in ("deal",):
        score += 2
    elif signal_type in ("trial_update", "fda"):
        score += 2
    elif signal_type == "press_release":
        for kw in DEAL_KEYWORDS:
            if kw in hl:
                score += 2
                break
        for kw in PHASE_KEYWORDS:
            if kw in hl:
                score += 1
                break

    return min(score, 10), matched_co


# ── RSS fetching ───────────────────────────────────────────────────────────────
