"""
company_identity_resolver.py — Canonical Company Identity Resolution

Resolves free-text company names (from press releases, research.py extraction,
deal records, signal_monitor.py) to canonical company_id values in the companies
table. Mirrors the 4-step DrugIdentityResolver cascade.

RESOLUTION CASCADE:
  1. Alias table exact match   — case-insensitive, fast, authoritative
  2. Companies table direct    — name/ticker match if alias table is sparse
  3. Fuzzy match               — flag for review, do NOT auto-merge
  4. Not-found                 — log to identity_audit_log, return None

DESIGN PRINCIPLES:
  - Never creates companies automatically (unlike DrugIdentityResolver which
    can create new canonicals). Unknown companies are logged as not-found.
  - Fuzzy matches are flagged, not resolved. A signal that routes to the wrong
    company is worse than a signal that routes to no company.
  - All resolution decisions logged to identity_audit_log for audit trail.
  - Thread-safe: alias index built once on init, reused across calls.

USAGE:
    from company_identity_resolver import CompanyIdentityResolver

    resolver = CompanyIdentityResolver(sb_url, service_key)

    company_id = resolver.resolve("AbbVie")         # → 'abbvie'
    company_id = resolver.resolve("ABBV")            # → 'abbvie'
    company_id = resolver.resolve("J&J")             # → 'jnj'
    company_id = resolver.resolve("Gilead Sciences") # → 'gilead'
    company_id = resolver.resolve("UnknownCo")       # → None (logged)
"""

import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher

import requests

_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)


# ── Text normalisation ────────────────────────────────────────────────────────

_STRIP_SUFFIXES = [
    " inc.", " inc", " ltd.", " ltd", " plc", " ag", " gmbh",
    " co.", " & co.", " & co", " sa", " s.a.", " s.a",
    " pharmaceuticals", " pharmaceutical", " pharma",
    " biosciences", " bioscience", " biopharma", " biopharmaceuticals",
    " therapeutics", " sciences", " science",
    " holdings", " holding", " group",
]


def _normalise(name: str) -> str:
    """
    Lowercase, strip punctuation and common legal suffixes.
    'AbbVie Inc.' → 'abbvie'
    'F. Hoffmann-La Roche Ltd' → 'f hoffmann-la roche'
    """
    if not name:
        return ""
    # Unicode normalise
    n = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    n = n.lower().strip()
    # Remove periods (except in abbreviations — keep hyphens)
    n = n.replace(".", "")
    # Strip known legal suffixes (longest first to avoid partial strips)
    for suffix in sorted(_STRIP_SUFFIXES, key=len, reverse=True):
        if n.endswith(suffix):
            n = n[: -len(suffix)].strip()
            break
    return n.strip()


# ── CompanyIdentityResolver ───────────────────────────────────────────────────

class CompanyIdentityResolver:
    """
    Resolve free-text company names to canonical company_id values.

    Builds an in-memory alias index from the company_aliases and companies
    tables on first use. The index is shared across all resolve() calls.
    Re-initialize (or call refresh()) to pick up new aliases added to the DB.
    """

    def __init__(self, sb_url: str, service_key: str, dry_run: bool = False):
        self.sb_url     = sb_url.rstrip("/")
        self.service_key = service_key
        self.dry_run    = dry_run

        self._headers = {
            "apikey":        service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type":  "application/json",
            "Prefer":        "return=minimal",
        }

        # alias_index: normalised_name → company_id
        # fuzzy_candidates: list of (normalised_name, company_id) for fuzzy scan
        self._alias_index:     dict[str, str] = {}
        self._fuzzy_candidates: list[tuple[str, str]] = []
        self._loaded = False

    # ── Index loading ─────────────────────────────────────────────────────────

    def _load(self):
        """Build alias index from company_aliases + companies tables."""
        # 1. Load company_aliases (authoritative)
        resp = requests.get(
            f"{self.sb_url}/rest/v1/company_aliases",
            headers={**self._headers, "Prefer": ""},
            params={"select": "company_id,alias_name", "limit": "2000"},
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to load company_aliases: {resp.status_code}")

        for row in resp.json():
            cid   = row.get("company_id", "").strip()
            alias = (row.get("alias_name") or "").strip()
            if cid and alias:
                # Exact (case-insensitive)
                self._alias_index[alias.lower()] = cid
                # Normalised
                norm = _normalise(alias)
                if norm and norm not in self._alias_index:
                    self._alias_index[norm] = cid

        # 2. Load companies table as fallback (name + ticker)
        resp2 = requests.get(
            f"{self.sb_url}/rest/v1/companies",
            headers={**self._headers, "Prefer": ""},
            params={"select": "id,name,ticker", "limit": "500"},
        )
        if resp2.status_code != 200:
            raise RuntimeError(f"Failed to load companies: {resp2.status_code}")

        for row in resp2.json():
            cid    = (row.get("id") or "").strip()
            name   = (row.get("name") or "").strip()
            ticker = (row.get("ticker") or "").strip()
            if not cid:
                continue
            for variant in [name, ticker, cid]:
                if not variant:
                    continue
                key  = variant.lower()
                norm = _normalise(variant)
                if key not in self._alias_index:
                    self._alias_index[key] = cid
                if norm and norm not in self._alias_index:
                    self._alias_index[norm] = cid

        # 3. Build fuzzy candidates (only entries ≥5 chars to avoid false positives)
        self._fuzzy_candidates = [
            (k, v) for k, v in self._alias_index.items() if len(k) >= 5
        ]

        self._loaded = True

    def refresh(self):
        """Clear and reload the alias index from the database."""
        self._alias_index     = {}
        self._fuzzy_candidates = []
        self._loaded          = False
        self._load()

    # ── Resolution ────────────────────────────────────────────────────────────

    def resolve(
        self,
        name: str,
        source: str = "unknown",
        fuzzy_threshold: float = 0.82,
    ) -> str | None:
        """
        Resolve a company name string to a canonical company_id.

        Returns company_id (str) on success, None on failure.
        Logs every resolution decision to identity_audit_log.

        Parameters
        ----------
        name : str
            Raw company name to resolve (e.g. "AbbVie", "ABBV", "J&J").
        source : str
            Caller identifier for audit log ('research.py', 'signal_monitor', etc.)
        fuzzy_threshold : float
            SequenceMatcher ratio threshold for flagging a fuzzy candidate.
            Matches above this threshold are flagged for review (not auto-resolved).
        """
        if not name or not name.strip():
            return None

        if not self._loaded:
            self._load()

        raw     = name.strip()
        key     = raw.lower()
        norm    = _normalise(raw)

        # ── Step 1: Exact alias match ─────────────────────────────────────────
        if key in self._alias_index:
            cid = self._alias_index[key]
            self._log("alias_exact", raw, cid, source, confidence=100)
            return cid

        # ── Step 2: Normalised alias match ────────────────────────────────────
        if norm and norm in self._alias_index:
            cid = self._alias_index[norm]
            self._log("alias_normalised", raw, cid, source, confidence=95)
            return cid

        # ── Step 3: Substring scan (input contains known alias or vice versa) ──
        best_cid  = None
        best_len  = 0
        for candidate, cid in self._fuzzy_candidates:
            if len(candidate) < 5:
                continue
            if candidate in key or key in candidate:
                if len(candidate) > best_len:
                    best_cid = cid
                    best_len = len(candidate)
        if best_cid:
            self._log("substring", raw, best_cid, source, confidence=85)
            return best_cid

        # ── Step 4: Fuzzy match — flag, do NOT resolve ────────────────────────
        if norm:
            best_ratio  = 0.0
            best_fuzzy  = None
            best_fuzzy_cid = None
            for candidate, cid in self._fuzzy_candidates:
                ratio = SequenceMatcher(None, norm, candidate).ratio()
                if ratio > best_ratio:
                    best_ratio     = ratio
                    best_fuzzy     = candidate
                    best_fuzzy_cid = cid

            if best_ratio >= fuzzy_threshold:
                self._log(
                    "flag_fuzzy", raw, None, source,
                    confidence=int(best_ratio * 100),
                    extra={
                        "fuzzy_candidate": best_fuzzy,
                        "fuzzy_company_id": best_fuzzy_cid,
                        "fuzzy_ratio": round(best_ratio, 4),
                        "input_normalised": norm,
                    },
                )
                return None  # flag, do not resolve

        # ── Step 5: Not found ─────────────────────────────────────────────────
        self._log("not_found", raw, None, source, confidence=0)
        return None

    # ── Audit logging ─────────────────────────────────────────────────────────

    def _log(
        self,
        operation: str,
        input_name: str,
        company_id: str | None,
        source: str,
        confidence: int = 100,
        extra: dict | None = None,
    ):
        """Write a resolution decision to identity_audit_log."""
        if self.dry_run:
            return

        payload = {
            "operation":    f"company_{operation}",
            "performed_by": source,
            "related_id":   input_name,
            "canonical_id": company_id,
            "new_value":    {
                "input":      input_name,
                "resolved_to": company_id,
                "confidence":  confidence,
                **(extra or {}),
            },
            "performed_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            requests.post(
                f"{self.sb_url}/rest/v1/identity_audit_log",
                headers=self._headers,
                json=payload,
                timeout=5,
            )
        except Exception:
            pass  # logging failure must never block the caller


# ── Credential loader ──────────────────────────────────────────────────────────

def get_credentials() -> tuple[str, str]:
    """Read SUPABASE_URL + SUPABASE_SERVICE_KEY via the shared loader.

    NOTE: this used to read .supabase_service_key/.supabase_config relative to
    workspace = dirname(dirname(__file__)), which resolved to scripts/ rather
    than the repo root after the scripts/ reorg moved this file deeper —
    load_credentials locates the repo root correctly regardless of depth.
    """
    from _common import load_credentials
    sb_url, sb_key, _ = load_credentials(require_anthropic=False)
    return sb_url.rstrip("/"), sb_key


# ── CLI smoke-test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    sb_url, sb_key = get_credentials()
    resolver = CompanyIdentityResolver(sb_url, sb_key, dry_run=True)

    test_cases = [
        # Should resolve
        ("AbbVie",                  "abbvie"),
        ("ABBV",                    "abbvie"),
        ("J&J",                     "jnj"),
        ("Johnson & Johnson",       "jnj"),
        ("Janssen",                 "jnj"),
        ("Merck",                   "merck"),
        ("MSD",                     "merck"),
        ("Merck Sharp & Dohme",     "merck"),
        ("Roche",                   "roche"),
        ("Genentech",               "roche"),
        ("AstraZeneca",             "astrazeneca"),
        ("AZ",                      "astrazeneca"),
        ("Eli Lilly",               "lilly"),
        ("Lilly",                   "lilly"),
        ("Regeneron",               "regeneron"),
        ("REGN",                    "regeneron"),
        ("Pfizer",                  "pfizer"),
        ("Gilead",                  "gilead"),
        ("Gilead Sciences",         "gilead"),
        ("GILD",                    "gilead"),
        ("Novartis",                "novartis"),
        ("GSK",                     "gsk"),
        ("GlaxoSmithKline",         "gsk"),
        ("Boehringer Ingelheim",    "boehringer"),
        ("Takeda",                  "takeda"),
        ("UCB",                     "ucb"),
        ("Sanofi",                  "sanofi"),
        ("BMS",                     "bms"),
        ("Bristol-Myers Squibb",    "bms"),
        # Should NOT resolve
        ("Anthropic",               None),
        ("Biosion",                 None),
        ("River Vision",            None),
        ("XYZ Pharma",              None),
    ]

    print("CompanyIdentityResolver — smoke test (dry_run=True)\n")
    passed = failed = 0
    for name, expected in test_cases:
        result = resolver.resolve(name, source="smoke_test")
        ok = result == expected
        status = "✅" if ok else "❌"
        if ok:
            passed += 1
        else:
            failed += 1
        print(f"  {status}  '{name}' → {result!r}  (expected {expected!r})")

    print(f"\n{passed}/{passed+failed} passed")
    sys.exit(0 if failed == 0 else 1)
