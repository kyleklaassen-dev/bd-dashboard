#!/usr/bin/env python3
"""
Issue persistence + editorial-plan helpers (§3 write_meridian split).
=====================================================================
Extracted verbatim from write_meridian.py. _extract_company_ids_from_plan /
_compute_content_fingerprint derive identity/dedupe keys from the editorial plan;
save_to_supabase archives the generated Issue (HTML + metadata) to Supabase.
"""

import datetime
import hashlib

import requests

from meridian.products.issue.common import SUPABASE_URL, SB_HEADERS, log


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
