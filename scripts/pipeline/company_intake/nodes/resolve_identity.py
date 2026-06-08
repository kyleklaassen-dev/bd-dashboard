"""
Node: resolve_identity
Step 1 for both modes — resolve the company name via CompanyIdentityResolver
and decide whether the run can proceed.

mode="intake":
  resolved_existing / alias_match → require --force to re-research
  unresolved (fuzzy alias conflict) → require --force to proceed
  candidate_new → proceed

mode="reaudit":
  requires an existing, resolved company — aborts otherwise
"""
from __future__ import annotations

import os
import sys

_HERE     = os.path.dirname(os.path.abspath(__file__))
_NODES    = os.path.dirname(_HERE)
_PIPELINE = os.path.dirname(_NODES)
_SCRIPTS  = os.path.dirname(_PIPELINE)
for _p in (_SCRIPTS, os.path.join(_SCRIPTS, "identity")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from company_identity_resolver import CompanyIdentityResolver  # noqa: E402

from pipeline.company_intake.state import IntakeState  # noqa: E402


def resolve_identity(company_name: str, supabase_url: str, supabase_key: str,
                      dry_run: bool = False) -> dict:
    """Resolve company name using CompanyIdentityResolver."""
    resolver = CompanyIdentityResolver(supabase_url, supabase_key, dry_run=dry_run)
    return resolver.resolve_with_detail(company_name, source="company_intake")


def _resolve_for_intake(state: IntakeState) -> None:
    resolution = state.resolution
    rtype = resolution["resolution_type"]

    if rtype in ("resolved_existing", "alias_match"):
        existing_id = resolution["company_id"]
        print(f"  ℹ️  Company already in Meridian: {existing_id} ({rtype})")
        if not state.force:
            print(f"  Use --force to re-research an existing company.")
            print(f"  Or use the Company Database tab to view their current profile.")
            state.abort("existing_company_without_force")
            return
        print(f"  --force flag set: proceeding with research for {existing_id}")

    elif rtype == "unresolved":
        print(f"  ⚠️  Possible alias conflict detected:")
        print(f"     '{state.company_name}' is {resolution['fuzzy_ratio']:.0%} similar to "
              f"'{resolution['fuzzy_match']}' → {resolution['fuzzy_company_id']}")
        print(f"     If this is a new company, use --force to proceed.")
        print(f"     If this is an alias, add it via company_aliases table first.")
        if not state.force:
            state.abort("unresolved_alias_conflict")
            return
        print(f"  --force flag set: treating as candidate_new.")

    else:
        # candidate_new — normal path
        print(f"  ✅ New company candidate: '{state.company_name}' (suggested_id: {resolution['canonical_name']})")

    state.company_id = resolution.get("company_id")  # None for new candidates


def _resolve_for_reaudit(state: IntakeState) -> None:
    resolution = state.resolution
    rtype = resolution["resolution_type"]

    if rtype not in ("resolved_existing", "alias_match"):
        print(f"  ❌ Company not found in Meridian (type={rtype}).")
        print(f"     Re-audit requires an existing company. Use --company with a known company_id.")
        print(f"     To add a new company, run without --re-audit.")
        state.abort("company_not_found")
        return

    state.company_id = resolution["company_id"]
    print(f"  ✅ Resolved: {state.company_id}")


def resolve_identity_node(state: IntakeState) -> IntakeState:
    """
    Resolve the company's identity and apply the mode-specific gating rules.
    Sets state.resolution / state.company_id, and aborts the run (state.abort)
    when the resolution result blocks further processing.
    """
    print("\n[1/4] Resolving company identity...")
    if state.mode == "reaudit":
        state.resolution = resolve_identity(state.company_name, state.supabase_url, state.supabase_key, dry_run=False)
        _resolve_for_reaudit(state)
    else:
        state.resolution = resolve_identity(state.company_name, state.supabase_url, state.supabase_key, dry_run=state.dry_run)
        _resolve_for_intake(state)

    state.mark_complete("resolve_identity")
    return state
