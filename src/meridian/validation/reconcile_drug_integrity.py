#!/usr/bin/env python3
"""
reconcile_drug_integrity.py — autonomous data-integrity reconciler
------------------------------------------------------------------
Detects and (only when confidence is sufficient) auto-corrects the data
conflicts that the Narrative Knowledge Layer surfaces, using the SAME detection
logic as narrative_gen.py (single source of truth for conflicts).

Fix classes & confidence:
  scrub_tokens   (HIGH)   remove a verifier-DISCONFIRMED identifier (e.g. a
                          fabricated NCT id) from every field of the drug row,
                          and replace a fabricated source_url with the best
                          CONFIRMED source.
  set_field      (HIGH)   correct a field whose value contradicts a CONFIRMED
                          source (e.g. stage='Phase 2' vs confirmed Phase 1).
  replace_token  (MEDIUM) replace a wrong company name in a prose field with the
                          canonical identity (company_display).

GOVERNANCE — NEVER SILENT. Every applied change writes THREE records:
  1. field_change_audit  — old_value/new_value, is_correction, row_snapshot
  2. drug_sources        — the correction documented as a sourced claim (CLAUDE.md §5)
  3. governance_violations — the violation, marked resolved with notes

Anything below the confidence threshold is NOT edited — it is logged to
governance_violations as resolved=false (a review queue). The default is to
auto-apply HIGH and MEDIUM; raise the bar with --min-confidence high.

Run:
  python3 scripts/reconcile_drug_integrity.py --drug-id mt-251 --dry-run
  python3 scripts/reconcile_drug_integrity.py --drug-id mt-251 --apply
  python3 scripts/reconcile_drug_integrity.py --all --apply        # whole catalog
"""

import os
import re
import sys
import json
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timezone

# Reuse the AUTHORITATIVE detection logic from the narrative generator.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meridian.products.narrative_gen import fetch_recipe, extract_atoms, SUPA_URL, SUPA_KEY, get  # noqa: E402

CONF_RANK = {"low": 0, "medium": 1, "high": 2}
ACTOR = "reconcile_drug_integrity.py@v0"
SESSION = f"auto-reconcile-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
# Authority order for choosing a replacement source_url
SRC_PRIORITY = ["ct_gov", "company_ir", "press_release", "publication", "news",
                "conference", "other"]


def _req(method, endpoint, data=None, prefer=None):
    url = f"{SUPA_URL}/{endpoint}"
    hdrs = {"apikey": SUPA_KEY, "Authorization": f"Bearer {SUPA_KEY}",
            "Content-Type": "application/json"}
    if prefer:
        hdrs["Prefer"] = prefer
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return json.loads(raw) if raw.strip() else []
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} {method} {endpoint.split('?')[0]}: {e.read().decode()[:200]}",
              file=sys.stderr)
        return None


_NCT_CACHE = {}


def nct_exists(nct):
    """Authoritative existence check against the ClinicalTrials.gov API.
    Grounds the 'fabricated trial' verdict in truth instead of an LLM's guess.
    Fails SAFE: on network error returns True (assume real) so we never delete on doubt."""
    nct = nct.upper()
    if nct in _NCT_CACHE:
        return _NCT_CACHE[nct]
    url = f"https://clinicaltrials.gov/api/v2/studies/{nct}?fields=protocolSection.identificationModule"
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": "Mozilla/5.0 meridian-reconciler"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            r.read(); _NCT_CACHE[nct] = True
    except urllib.error.HTTPError as e:
        _NCT_CACHE[nct] = (e.code != 404)   # 404 = truly nonexistent
    except Exception:
        _NCT_CACHE[nct] = True              # fail safe: don't scrub on uncertainty
    return _NCT_CACHE[nct]


def load_company_registry():
    """Build {token(lower) -> company_id} and {company_id -> name} from
    companies + company_aliases. Used to make company-mismatch detection safe."""
    cid_to_name, token_to_cid = {}, {}
    for c in get("companies?select=id,name"):
        cid_to_name[c["id"]] = c.get("name")
        if c.get("name"):
            token_to_cid[c["name"].lower()] = c["id"]
    for a in get("company_aliases?select=company_id,alias_name"):
        if a.get("alias_name"):
            token_to_cid.setdefault(a["alias_name"].lower(), a["company_id"])
    return {"token_to_cid": token_to_cid, "cid_to_name": cid_to_name}


_COMPANIES = None


def best_confirmed_url(sources):
    confirmed = [s for s in sources if s.get("content_confirms_claim") is True
                 and s.get("source_url")]
    if not confirmed:
        return None
    confirmed.sort(key=lambda s: SRC_PRIORITY.index(s["source_type"])
                   if s.get("source_type") in SRC_PRIORITY else 99)
    return confirmed[0]["source_url"]


def _strip_token(text, token):
    # remove "(TOKEN)", " TOKEN", "TOKEN" and tidy whitespace/punctuation
    out = re.sub(r"\s*\(\s*" + re.escape(token) + r"\s*\)", "", text, flags=re.I)
    out = re.sub(re.escape(token), "", out, flags=re.I)
    out = re.sub(r"\s{2,}", " ", out).replace(" ,", ",").replace(" .", ".").strip()
    return out


def plan_fixes(recipe):
    """Map detected conflicts -> concrete, confidence-rated change records."""
    global _COMPANIES
    if _COMPANIES is None:
        _COMPANIES = load_company_registry()
    drug = recipe["drug"]
    sources = recipe["sources"]
    atoms = extract_atoms(recipe, known_companies=_COMPANIES)
    changes = []   # each: field, old, new, confidence, rule, issue, src_url, confirms

    for c in atoms["conflicts"]:
        fix = c.get("fix")
        if not fix:
            # 'verifier_disconfirmed' is informational — its remediation is the
            # 'scrubbed_identifier_still_in_row' scrub fix below, so don't double-queue it.
            if c["issue"] == "verifier_disconfirmed":
                continue
            changes.append({"issue": c["issue"], "detail": c["detail"],
                            "confidence": "low", "queue_only": True})
            continue

        if fix["kind"] == "scrub_tokens":
            # GUARD (added after the NCT07423299 incident): a "fabricated NCT" verdict
            # from an upstream verifier can be a hallucination. Before DELETING a trial
            # id, re-confirm nonexistence against the authoritative CT.gov API. If the
            # NCT actually EXISTS, do NOT scrub — queue the verifier's claim as a false
            # positive for review. Destructive auto-fixes must be grounded in truth.
            real_ncts = [t for t in fix["tokens"]
                         if re.match(r"NCT\d{8}$", t, re.I) and nct_exists(t)]
            if real_ncts:
                changes.append({
                    "issue": "verifier_false_positive", "confidence": "low",
                    "queue_only": True, "rule": "verifier_false_positive",
                    "detail": f"Upstream verifier flagged {real_ncts} as fabricated, but "
                              f"they EXIST on ClinicalTrials.gov. NOT scrubbed. Review the "
                              f"disconfirming drug_sources row."})
            fix = {**fix, "tokens": [t for t in fix["tokens"] if t not in real_ncts]}
            if not fix["tokens"]:
                continue
            repl_url = best_confirmed_url(sources)
            for f, v in drug.items():
                if not isinstance(v, str):
                    continue
                if any(t.lower() in v.lower() for t in fix["tokens"]):
                    if f == "source_url":
                        new = repl_url  # fabricated URL -> best confirmed source
                    else:
                        new = v
                        for t in fix["tokens"]:
                            new = _strip_token(new, t)
                    if new != v:
                        changes.append({
                            "field": f, "old": v, "new": new,
                            "confidence": fix["confidence"], "rule": fix["rule"],
                            "issue": c["issue"],
                            "src_url": "https://clinicaltrials.gov", "confirms": False,
                            "claim_type": "source_url_removed",
                            "detail": f"Removed verifier-disconfirmed token(s) "
                                      f"{fix['tokens']} from {f}."})

        elif fix["kind"] == "set_field":
            f = fix["field"]
            old = str(drug.get(f, ""))
            if old != fix["correct"]:
                # the confirming source for this field
                su = next((s["source_url"] for s in sources
                           if s.get("content_confirms_claim") and "phase"
                           in (s.get("claim_value", "").lower())), best_confirmed_url(sources))
                changes.append({
                    "field": f, "old": old, "new": fix["correct"],
                    "confidence": fix["confidence"], "rule": fix["rule"],
                    "issue": c["issue"], "src_url": su, "confirms": True,
                    "claim_type": "correction",
                    "detail": f"Corrected {f} '{old}' -> '{fix['correct']}' to match confirmed source."})

        elif fix["kind"] == "replace_token":
            f = fix["field"]
            old = str(drug.get(f, ""))
            new = old.replace(fix["wrong"], fix["correct"])
            if new != old:
                changes.append({
                    "field": f, "old": old, "new": new,
                    "confidence": fix["confidence"], "rule": fix["rule"],
                    "issue": c["issue"], "src_url": best_confirmed_url(sources),
                    "confirms": True, "claim_type": "correction",
                    "detail": f"Replaced wrong company '{fix['wrong']}' with canonical "
                              f"'{fix['correct']}' in {f}."})
    return drug, changes


def log_and_apply(drug, changes, min_conf, apply):
    drug_id = drug["id"]
    drug_name = drug.get("display_name") or drug.get("name")
    threshold = CONF_RANK[min_conf]
    updates = {}
    applied, queued = [], []

    for ch in changes:
        if ch.get("queue_only") or CONF_RANK.get(ch["confidence"], 0) < threshold:
            queued.append(ch)
            continue
        applied.append(ch)
        if "field" in ch:
            updates[ch["field"]] = ch["new"]

    print(f"\n=== {drug_id} — {len(applied)} auto-fix, {len(queued)} queued "
          f"(threshold={min_conf}) ===")
    for ch in applied:
        print(f"  FIX [{ch['confidence']}] {ch.get('field','-')}: "
              f"{str(ch.get('old'))[:50]!r} -> {str(ch.get('new'))[:50]!r}  ({ch['rule']})")
    for ch in queued:
        print(f"  QUEUE [{ch['confidence']}] {ch['issue']}: {ch.get('detail','')[:80]}")

    if not apply:
        print("\n[dry-run] no writes.")
        return

    now = datetime.now(timezone.utc).isoformat()
    snapshot = json.dumps(drug, default=str)

    # ---- STEP 1: AUDIT FIRST. Write field_change_audit BEFORE touching the row.
    # If the edit later fails, we roll these back. This makes a silent edit
    # structurally impossible: no row changes unless its audit already exists.
    audit_ids = []
    for ch in applied:
        if "field" not in ch:
            continue
        res = _req("POST", "field_change_audit", [{
            "table_name": "drugs", "entity_id": drug_id, "entity_type": "drug",
            "field_name": ch["field"], "old_value": str(ch.get("old")),
            "new_value": str(ch.get("new")), "changed_by": ACTOR,
            "change_source": "auto_reconciler", "change_reason": ch["detail"],
            "is_governance_relevant": True, "governance_rule": ch["rule"],
            "is_correction": True, "session_id": SESSION, "row_snapshot": snapshot,
        }], prefer="return=representation")
        if not res:
            print("  ! audit write failed — rolling back audit, NOT editing the row.")
            for aid in audit_ids:
                _req("DELETE", f"field_change_audit?id=eq.{aid}")
            return
        audit_ids.append(res[0]["id"])

    # ---- STEP 2: apply the edit (single PATCH). Compensate audit on failure.
    if updates:
        updates["updated_at"] = now
        res = _req("PATCH", f"drugs?id=eq.{drug_id}", updates, prefer="return=minimal")
        if res is None:
            print("  ! drugs PATCH failed — rolling back audit rows to stay consistent.")
            for aid in audit_ids:
                _req("DELETE", f"field_change_audit?id=eq.{aid}")
            return

    # ---- STEP 3: supporting trails. drug_sources per change (no unique constraint);
    # governance_violations aggregated per rule (UNIQUE table,row,rule -> upsert).
    for ch in applied:
        _req("POST", "drug_sources", [{
            "drug_id": drug_id, "drug_name": drug_name,
            "claim_type": ch.get("claim_type", "correction"),
            "claim_value": ch["detail"], "source_url": ch.get("src_url"),
            "source_type": "other",
            "source_domain": (ch.get("src_url") or "").split("/")[2]
                             if ch.get("src_url") else None,
            "content_confirms_claim": ch.get("confirms"),
            "confidence": "confirmed", "added_by": ACTOR, "session_label": SESSION,
        }], prefer="return=minimal")

    by_rule = {}
    for ch in applied:
        by_rule.setdefault(ch["rule"], []).append(ch)
    for rule, chs in by_rule.items():
        fields = ", ".join(c.get("field", "-") for c in chs)
        conf = max((c["confidence"] for c in chs), key=lambda c: CONF_RANK[c])
        _req("POST", "governance_violations?on_conflict=table_name,row_id,rule_name", [{
            "table_name": "drugs", "row_id": drug_id, "rule_name": rule,
            "description": "; ".join(c["detail"] for c in chs),
            "resolved": True, "resolved_at": now, "resolved_by": ACTOR,
            "resolution_notes": f"Auto-corrected ({conf} confidence) field(s): {fields}. "
                                f"Trails: field_change_audit + drug_sources.",
        }], prefer="resolution=merge-duplicates,return=minimal")

    # queued items -> unresolved governance_violations (review queue), never edited
    for ch in queued:
        _req("POST", "governance_violations?on_conflict=table_name,row_id,rule_name", [{
            "table_name": "drugs", "row_id": drug_id,
            "rule_name": ch.get("rule", ch.get("issue")),
            "description": ch.get("detail", ch.get("issue")),
            "resolved": False,
            "resolution_notes": f"Below auto-fix confidence ({ch['confidence']}). "
                                f"Queued for human review — NOT edited.",
        }], prefer="resolution=merge-duplicates,return=minimal")

    print(f"  logged: {len(applied)} corrections (audit-first + drug_sources + "
          f"{len(by_rule)} governance rows), {len(queued)} queued.")


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--drug-id")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--min-confidence", default="medium", choices=["high", "medium", "low"])
    ap.add_argument("--apply", action="store_true", help="write changes (default is dry-run)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    apply = args.apply and not args.dry_run

    ids = [args.drug_id] if args.drug_id else [d["id"] for d in get("drugs?select=id")]
    for did in ids:
        try:
            recipe = fetch_recipe(did)
        except SystemExit as e:
            print(e); continue
        drug, changes = plan_fixes(recipe)
        if changes:
            log_and_apply(drug, changes, args.min_confidence, apply)
        elif args.drug_id:
            print(f"{did}: clean — no conflicts.")


if __name__ == "__main__":
    main()
