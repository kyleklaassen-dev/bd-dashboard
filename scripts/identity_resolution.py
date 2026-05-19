"""
identity_resolution.py — MVP DrugIdentityResolver

Resolves a drug name string to a canonical_drug_id using a 4-step cascade:
  1. Exact alias match          — confidence 100, method 'exact'
  2. Normalised name match      — confidence 90,  method 'normalized'
  3. Fuzzy match (≥ 0.85)       — confidence 70,  method 'fuzzy'   [FLAGGED for review, NOT auto-merged]
  4. Create new canonical drug  — confidence 100, method 'new'

DESIGN CONSTRAINTS (per ChatGPT review):
  - Fuzzy matches are flagged to identity_audit_log with operation='flag_review'.
    They return a NEW canonical_id, not the fuzzy-matched one.
    A human must approve a merge before any consolidation happens.
  - No auto-merge of fuzzy matches, ever.
  - No entity relationship graph yet — canonical drug identity only.

USAGE:
    resolver = DrugIdentityResolver(supabase_url, service_key)
    canonical_id, confidence, method = resolver.resolve("tulisokibart", source="ct_gov")

    # Batch (returns dict keyed by input name):
    results = resolver.resolve_batch(["tulisokibart", "CLD-423", "PF-06480090"], source="ct_gov")
"""

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Optional

import requests


# ─── Constants ─────────────────────────────────────────────────────────────────

FUZZY_THRESHOLD = 0.85      # SequenceMatcher ratio; below this → create new
EXACT_CONFIDENCE = 100
NORMALIZED_CONFIDENCE = 90
FUZZY_CONFIDENCE = 70       # returned for NEW canonical created after fuzzy near-miss flag
NEW_CANONICAL_CONFIDENCE = 100


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _normalize_name(name: str) -> str:
    """Lowercase, strip punctuation/whitespace noise for comparison."""
    if not name:
        return ""
    s = name.lower().strip()
    # Remove common prefixes/suffixes that vary across sources
    s = re.sub(r'\b(anti[-\s]?|mab$|antibody$|inhibitor$)\b', '', s)
    # Collapse punctuation and extra whitespace
    s = re.sub(r'[-_\s]+', ' ', s)
    s = re.sub(r'[^a-z0-9 ]', '', s)
    return s.strip()


def _canonical_id_from_name(name: str) -> str:
    """Generate a deterministic canonical_id from the normalized name."""
    norm = _normalize_name(name)
    hash_hex = hashlib.sha256(norm.encode()).hexdigest()[:8]
    return f"CANON_DRUG_{hash_hex.upper()}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── DrugIdentityResolver ──────────────────────────────────────────────────────

class DrugIdentityResolver:
    """
    Resolves drug name strings to canonical_drug_id values.

    Parameters
    ----------
    supabase_url : str
        Supabase project URL (e.g. https://tghntyofptvfhmtchwcv.supabase.co)
    service_key : str
        Supabase service role key (bypasses RLS for writes)
    dry_run : bool
        If True, print what would happen but make no writes.
    """

    def __init__(self, supabase_url: str, service_key: str, dry_run: bool = False):
        self.url = supabase_url.rstrip('/')
        self.headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        self.dry_run = dry_run

        # In-memory alias cache: normalised_name → (canonical_id, alias_name, confidence_score)
        # Populated lazily on first resolve; refreshed per batch call.
        self._alias_cache: dict[str, tuple[str, str, int]] = {}
        self._cache_loaded = False

    # ── Public API ────────────────────────────────────────────────────────────

    def resolve(
        self,
        drug_name: str,
        source: str = "unknown",
        drug_class: Optional[str] = None,
        mechanism: Optional[str] = None,
        target: Optional[str] = None,
    ) -> tuple[str, int, str]:
        """
        Resolve a drug name to (canonical_id, confidence, method).

        Steps:
          1. Exact alias match
          2. Normalised alias match
          3. Fuzzy match → flag review, create new canonical
          4. Create new canonical

        Always safe to call; creates a new canonical_drug if nothing matches.
        """
        if not drug_name or not drug_name.strip():
            raise ValueError("drug_name must be a non-empty string")

        if not self._cache_loaded:
            self._load_alias_cache()

        # Step 1: exact match (case-insensitive, trim)
        exact_key = drug_name.strip().lower()
        if exact_key in self._alias_cache:
            canonical_id, _orig_alias, _conf = self._alias_cache[exact_key]
            self._add_alias_if_new(canonical_id, drug_name, source, EXACT_CONFIDENCE)
            self._log_audit("resolve_drug", canonical_id, drug_name,
                            {"method": "exact"}, source)
            return canonical_id, EXACT_CONFIDENCE, "exact"

        # Step 2: normalised match
        norm = _normalize_name(drug_name)
        if norm and norm in self._alias_cache:
            canonical_id, _orig_alias, _conf = self._alias_cache[norm]
            self._add_alias_if_new(canonical_id, drug_name, source, NORMALIZED_CONFIDENCE)
            self._log_audit("resolve_drug", canonical_id, drug_name,
                            {"method": "normalized", "normalized_form": norm}, source)
            return canonical_id, NORMALIZED_CONFIDENCE, "normalized"

        # Step 3: fuzzy match across all cached names
        best_ratio = 0.0
        best_canonical_id = None
        for cache_key, (c_id, orig, _) in self._alias_cache.items():
            ratio = SequenceMatcher(None, norm, cache_key).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_canonical_id = c_id

        if best_ratio >= FUZZY_THRESHOLD and best_canonical_id:
            # Flag for review — do NOT merge; create a fresh canonical instead
            print(f"  [identity] FUZZY near-miss: '{drug_name}' ≈ existing "
                  f"canonical {best_canonical_id} (ratio={best_ratio:.2f}) — flagging review")
            self._flag_fuzzy_review(drug_name, best_canonical_id, best_ratio, source)
            # Fall through to create a new canonical for this name
            # (human must approve merge explicitly)

        # Step 4: create new canonical drug
        canonical_id = self._create_canonical_drug(
            drug_name,
            drug_class=drug_class,
            mechanism=mechanism,
            target=target,
            source=source,
        )
        self._log_audit("resolve_drug", canonical_id, drug_name,
                        {"method": "new"}, source)
        return canonical_id, NEW_CANONICAL_CONFIDENCE, "new"

    def resolve_batch(
        self,
        drug_names: list[str],
        source: str = "unknown",
        drug_class: Optional[str] = None,
        mechanism: Optional[str] = None,
        target: Optional[str] = None,
    ) -> dict[str, tuple[str, int, str]]:
        """
        Resolve a list of drug names. Returns dict keyed by input name.
        Refreshes the alias cache once before processing the batch.
        """
        self._load_alias_cache()  # always refresh for batch
        results = {}
        for name in drug_names:
            try:
                results[name] = self.resolve(name, source=source,
                                             drug_class=drug_class,
                                             mechanism=mechanism,
                                             target=target)
            except Exception as e:
                print(f"  [identity] ERROR resolving '{name}': {e}")
                results[name] = ("UNRESOLVED", 0, "error")
        return results

    # ── Private: alias cache ─────────────────────────────────────────────────

    def _load_alias_cache(self):
        """Load all drug_aliases from Supabase into memory for fast lookup."""
        resp = requests.get(
            f"{self.url}/rest/v1/drug_aliases",
            headers={**self.headers, "Prefer": ""},
            params={"select": "canonical_id,alias_name,confidence_score", "limit": "10000"},
        )
        if resp.status_code != 200:
            print(f"  [identity] WARNING: could not load alias cache: {resp.status_code} {resp.text}")
            self._alias_cache = {}
            self._cache_loaded = True
            return

        self._alias_cache = {}
        for row in resp.json():
            alias_lower = row["alias_name"].strip().lower()
            alias_norm = _normalize_name(row["alias_name"])
            entry = (row["canonical_id"], row["alias_name"], row["confidence_score"])
            # Store both exact-lower and normalised keys
            self._alias_cache[alias_lower] = entry
            if alias_norm:
                self._alias_cache[alias_norm] = entry

        self._cache_loaded = True
        print(f"  [identity] Alias cache loaded: {len(self._alias_cache)} entries "
              f"({len(resp.json())} raw aliases)")

    # ── Private: canonical drug creation ────────────────────────────────────

    def _create_canonical_drug(
        self,
        drug_name: str,
        drug_class: Optional[str] = None,
        mechanism: Optional[str] = None,
        target: Optional[str] = None,
        source: str = "unknown",
    ) -> str:
        """
        Insert a new canonical_drugs row and its primary alias.
        Returns the canonical_id.
        """
        canonical_id = _canonical_id_from_name(drug_name)

        # Guard: if canonical_id already exists (hash collision or race), fetch it
        existing = self._fetch_canonical(canonical_id)
        if existing:
            print(f"  [identity] canonical_id {canonical_id} already exists — skipping create")
            self._add_alias_if_new(canonical_id, drug_name, source, NEW_CANONICAL_CONFIDENCE)
            return canonical_id

        record = {
            "canonical_id": canonical_id,
            "canonical_name": drug_name.strip(),
            "is_active": True,
            "confidence_score": NEW_CANONICAL_CONFIDENCE,
        }
        if drug_class:
            record["drug_class"] = drug_class
        if mechanism:
            record["mechanism"] = mechanism
        if target:
            record["target"] = target

        if self.dry_run:
            print(f"  [DRY RUN] Would create canonical drug: {canonical_id} '{drug_name}'")
        else:
            resp = requests.post(
                f"{self.url}/rest/v1/canonical_drugs",
                headers=self.headers,
                json=record,
            )
            if resp.status_code not in (200, 201):
                raise RuntimeError(
                    f"Failed to create canonical drug '{drug_name}': "
                    f"{resp.status_code} {resp.text}"
                )
            print(f"  [identity] Created canonical drug: {canonical_id} '{drug_name}'")

        # Add primary alias
        self._add_alias_if_new(canonical_id, drug_name, source,
                               NEW_CANONICAL_CONFIDENCE, is_primary=True)

        # Update local cache
        norm = _normalize_name(drug_name)
        entry = (canonical_id, drug_name, NEW_CANONICAL_CONFIDENCE)
        self._alias_cache[drug_name.strip().lower()] = entry
        if norm:
            self._alias_cache[norm] = entry

        # Audit
        self._log_audit("create_canonical", canonical_id, None,
                        None, {"canonical_name": drug_name, "source": source})

        return canonical_id

    def _add_alias_if_new(
        self,
        canonical_id: str,
        alias_name: str,
        source: str,
        confidence: int,
        alias_type: Optional[str] = None,
        is_primary: bool = False,
    ):
        """
        Upsert an alias. Uses ON CONFLICT DO UPDATE to refresh last_seen_at.
        Safe to call repeatedly — never creates duplicate rows.
        """
        if self.dry_run:
            return

        payload = {
            "canonical_id": canonical_id,
            "alias_name": alias_name.strip(),
            "source": source,
            "confidence_score": confidence,
            "is_primary": is_primary,
            "last_seen_at": _now_iso(),
        }
        if alias_type:
            payload["alias_type"] = alias_type

        resp = requests.post(
            f"{self.url}/rest/v1/drug_aliases",
            headers={
                **self.headers,
                "Prefer": "resolution=ignore-duplicates,return=minimal",
            },
            json=payload,
        )
        if resp.status_code not in (200, 201, 204):
            print(f"  [identity] WARNING: could not upsert alias '{alias_name}': "
                  f"{resp.status_code} {resp.text}")

    # ── Private: fuzzy review flag ───────────────────────────────────────────

    def _flag_fuzzy_review(
        self,
        drug_name: str,
        near_canonical_id: str,
        ratio: float,
        source: str,
    ):
        """
        Log a fuzzy near-miss to identity_audit_log for human review.
        Does NOT merge or modify any existing canonical drug.
        """
        if self.dry_run:
            print(f"  [DRY RUN] Would flag fuzzy review: '{drug_name}' ~ {near_canonical_id} "
                  f"(ratio={ratio:.2f})")
            return

        payload = {
            "operation": "flag_review",
            "canonical_id": near_canonical_id,
            "related_id": drug_name,
            "old_value": None,
            "new_value": {
                "input_name": drug_name,
                "fuzzy_ratio": round(ratio, 4),
                "near_canonical_id": near_canonical_id,
                "source": source,
                "recommendation": "Human review required before merge",
            },
            "reason": (
                f"Fuzzy match (ratio={ratio:.2f}) between '{drug_name}' "
                f"and existing canonical {near_canonical_id}. "
                f"Not auto-merged per policy — review and merge manually if correct."
            ),
            "performed_by": "identity_resolution.py",
        }
        resp = requests.post(
            f"{self.url}/rest/v1/identity_audit_log",
            headers=self.headers,
            json=payload,
        )
        if resp.status_code not in (200, 201):
            print(f"  [identity] WARNING: could not write fuzzy review flag: "
                  f"{resp.status_code} {resp.text}")

    # ── Private: audit log ───────────────────────────────────────────────────

    def _log_audit(
        self,
        operation: str,
        canonical_id: Optional[str],
        related_id: Optional[str],
        old_value: Optional[dict],
        new_value,
    ):
        """Append an entry to identity_audit_log."""
        if self.dry_run:
            return

        payload = {
            "operation": operation,
            "canonical_id": canonical_id,
            "related_id": related_id,
            "old_value": old_value,
            "new_value": new_value if isinstance(new_value, dict) else {"value": new_value},
            "performed_by": "identity_resolution.py",
        }
        resp = requests.post(
            f"{self.url}/rest/v1/identity_audit_log",
            headers=self.headers,
            json=payload,
        )
        if resp.status_code not in (200, 201):
            print(f"  [identity] WARNING: audit log write failed ({operation}): "
                  f"{resp.status_code}")

    # ── Private: helpers ─────────────────────────────────────────────────────

    def _fetch_canonical(self, canonical_id: str) -> Optional[dict]:
        """Return the canonical_drugs row for a given ID, or None."""
        resp = requests.get(
            f"{self.url}/rest/v1/canonical_drugs",
            headers={**self.headers, "Prefer": ""},
            params={"canonical_id": f"eq.{canonical_id}", "limit": "1"},
        )
        if resp.status_code == 200:
            rows = resp.json()
            return rows[0] if rows else None
        return None


# ─── CLI (quick smoke test) ────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Resolve a drug name to canonical_id")
    parser.add_argument("--name", required=True, help="Drug name to resolve")
    parser.add_argument("--source", default="cli_test", help="Source label")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    sb_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    sb_key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not sb_url or not sb_key:
        raise SystemExit("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY env vars required")

    resolver = DrugIdentityResolver(sb_url, sb_key, dry_run=args.dry_run)
    canonical_id, confidence, method = resolver.resolve(args.name, source=args.source)
    print(f"\nResult: canonical_id={canonical_id}  confidence={confidence}  method={method}")
