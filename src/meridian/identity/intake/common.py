#!/usr/bin/env python3
"""Shared base for the company_intake split (§3): creds, _sb_headers, the lazy Anthropic
client, ACTIVE_AREAS, and the relevance→overlap/layer/score/relationship mapping helpers."""

from __future__ import annotations

import os

import anthropic

from meridian.identity.company_identity_resolver import get_credentials


# ══════════════════════════════════════════════════════════════════════════════
# CREDENTIALS
# ══════════════════════════════════════════════════════════════════════════════

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
SUPABASE_URL, SUPABASE_KEY = get_credentials()

_sb_headers = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=minimal",
}

# Lazy-init: _ai is created on first use so import doesn't require ANTHROPIC_API_KEY
_ai: anthropic.Anthropic | None = None

def _get_ai() -> anthropic.Anthropic:
    global _ai
    if _ai is None:
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            raise SystemExit(
                "ERROR: ANTHROPIC_API_KEY not set. "
                "export ANTHROPIC_API_KEY=sk-ant-..."
            )
        _ai = anthropic.Anthropic(api_key=key)
    return _ai

# ── Active Meridian areas ─────────────────────────────────────────────────────

ACTIVE_AREAS = {
    "tl1a":   {
        "label":    "TL1A × IBD",
        "keywords": ["TL1A", "TNF-like ligand 1A", "DR3", "IBD", "Crohn", "ulcerative colitis", "UC", "CD"],
    },
    "tslp":   {
        "label":    "TSLP × Respiratory",
        "keywords": ["TSLP", "thymic stromal lymphopoietin", "asthma", "COPD", "atopic", "eosinophil"],
    },
    "il4ra":  {
        "label":    "IL-4Rα × Atopy",
        "keywords": ["IL-4R", "IL-4Rα", "IL4", "dupilumab", "atopic dermatitis", "AD", "asthma", "CRSwNP"],
    },
    "fcrn":   {
        "label":    "FcRn × Autoimmune",
        "keywords": ["FcRn", "neonatal Fc receptor", "IgG", "autoimmune", "gMG", "ITP", "pemphigus", "HDFN", "nipocalimab", "rozanolixizumab", "efgartigimod"],
    },
    "igf1r":  {
        "label":    "IGF-1R × Thyroid Eye",
        "keywords": ["IGF-1R", "IGF1R", "TSH receptor", "TSHR", "thyroid eye disease", "TED", "Graves", "teprotumumab"],
    },
    "tcell":  {
        "label":    "T-cell Engineering × Autoimmune",
        "keywords": ["CAR-T", "T cell", "TCR", "BCMA", "CD19", "autoimmune", "cell therapy", "ACE", "CAR"],
    },
}


# ── Overlap/layer/score helpers ───────────────────────────────────────────────

def _map_relevance_to_overlap(relevance: str) -> str:
    return {
        "Direct":       "Direct",
        "Adjacent":     "Adjacent",
        "Same-patient": "Same-Space",
        "Watchlist":    "Watch",
    }.get(relevance, "Watch")


def _map_relevance_to_layer(relevance: str) -> int:
    return {"Direct": 1, "Adjacent": 2, "Same-patient": 3, "Watchlist": 4}.get(relevance, 4)


def _confidence_to_relevance_score(confidence: float, relevance: str) -> int:
    base = {"Direct": 8, "Adjacent": 6, "Same-patient": 5, "Watchlist": 4}.get(relevance, 3)
    return min(10, int(base + confidence * 2))


def _map_relevance_to_relationship(relevance: str) -> str:
    return {
        "Direct":       "direct_competitor",
        "Adjacent":     "platform_overlap",
        "Same-patient": "same_patient_population",
        "Watchlist":    "strategic_watchlist",
    }.get(relevance, "strategic_watchlist")
