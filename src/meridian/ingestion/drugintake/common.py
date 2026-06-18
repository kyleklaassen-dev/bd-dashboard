#!/usr/bin/env python3
"""Shared base for the drug_intake split (§3): creds, _sb_headers, lazy Anthropic client,
ACTIVE_AREAS, and the relevance→overlap/layer/score mapping helpers."""

import os

import anthropic


# ── Credential helpers (reuse company_intake pattern) ────────────────────────
try:
    from meridian.identity.company_identity_resolver import get_credentials
except ImportError:
    def get_credentials():
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SERVICE_KEY", "")
        if not url or not key:
            # Try workspace files
            base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))  # repo root (5 up from src/meridian/ingestion/drugintake/)
            try:
                with open(os.path.join(base, ".supabase_config")) as f:
                    for line in f:
                        if line.startswith("SUPABASE_URL="):
                            url = line.split("=", 1)[1].strip()
            except FileNotFoundError:
                pass
            try:
                with open(os.path.join(base, ".supabase_service_key")) as f:
                    key = f.read().strip()
            except FileNotFoundError:
                pass
        return url, key

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
SUPABASE_URL, SUPABASE_KEY = get_credentials()

_sb_headers = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=minimal",
}

_ai: anthropic.Anthropic | None = None

def _get_ai() -> anthropic.Anthropic:
    global _ai
    if _ai is None:
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            raise SystemExit(
                "ERROR: ANTHROPIC_API_KEY not set.\n"
                "export ANTHROPIC_API_KEY=sk-ant-..."
            )
        _ai = anthropic.Anthropic(api_key=key)
    return _ai


# ── Active Meridian areas ─────────────────────────────────────────────────────

ACTIVE_AREAS = {
    "tl1a":  {"label": "TL1A × IBD",                     "keywords": ["TL1A", "TNFSF15", "DR3", "IBD", "Crohn", "ulcerative colitis", "UC", "CD"]},
    "tslp":  {"label": "TSLP × Respiratory",              "keywords": ["TSLP", "thymic stromal lymphopoietin", "IL-33", "ST2", "asthma", "COPD", "atopic", "eosinophil"]},
    "il4ra": {"label": "IL-4Rα × Atopy",                  "keywords": ["IL-4R", "IL-4Rα", "IL-13", "atopic dermatitis", "AD", "asthma", "OX40L", "CRSwNP"]},
    "fcrn":  {"label": "FcRn × Autoimmune",               "keywords": ["FcRn", "neonatal Fc receptor", "IgG", "gMG", "ITP", "pemphigus", "HDFN", "nipocalimab", "rozanolixizumab"]},
    "igf1r": {"label": "IGF-1R × Thyroid Eye",            "keywords": ["IGF-1R", "IGF1R", "TSH receptor", "TSHR", "thyroid eye disease", "TED", "Graves", "teprotumumab"]},
    "tcell": {"label": "T-cell Engineering × Autoimmune", "keywords": ["CAR-T", "T cell", "TCR", "BCMA", "CD19", "autoimmune", "cell therapy", "CAR-Treg"]},
}


def _map_relevance_to_overlap(r: str) -> str:
    return {"Direct": "Direct", "Adjacent": "Adjacent", "Same-patient": "Same-Space", "Watchlist": "Watch"}.get(r, "Watch")

def _map_relevance_to_layer(r: str) -> int:
    return {"Direct": 1, "Adjacent": 2, "Same-patient": 3, "Watchlist": 4}.get(r, 4)

def _confidence_to_relevance_score(confidence: float, relevance: str) -> int:
    base = {"Direct": 8, "Adjacent": 6, "Same-patient": 5, "Watchlist": 4}.get(relevance, 3)
    return min(10, int(base + confidence * 2))
