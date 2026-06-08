"""
Node: load_db_drugs  (mode="reaudit" only)
Step [2/4] — load every drug Meridian already attributes to this company
(direct + acquired/current-owner) and flatten them into a name-token set
for the diff_pipeline node to match against.
"""
from __future__ import annotations

import os
import sys

_HERE     = os.path.dirname(os.path.abspath(__file__))
_NODES    = os.path.dirname(_HERE)
_PIPELINE = os.path.dirname(_NODES)
_SCRIPTS  = os.path.dirname(_PIPELINE)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from _db import sb_get                                  # noqa: E402
from pipeline.company_intake.state import IntakeState   # noqa: E402


def get_db_drugs_for_company(company_id: str) -> tuple[list, list]:
    """
    Return normalised drug name tokens for all drugs owned or originated by company_id.
    Checks both company_id column and current_owner_company_id (for acquired companies).
    """
    try:
        rows = []
        rows += sb_get("drugs", {"company_id": f"eq.{company_id}", "select": "id,name,aliases", "limit": "200"})
        rows += sb_get("drugs", {"current_owner_company_id": f"eq.{company_id}", "select": "id,name,aliases", "limit": "200"})

        # Deduplicate by id
        seen = set()
        unique = []
        for r in rows:
            if r["id"] not in seen:
                seen.add(r["id"])
                unique.append(r)

        # Build a flat set of tokens: drug_id + name words + aliases
        tokens = set()
        for row in unique:
            tokens.add(row["id"].lower())
            for word in row.get("name", "").lower().split():
                if len(word) >= 4:
                    tokens.add(word)
            for alias in (row.get("aliases") or []):
                tokens.add(alias.lower())
                # Also add the base identifier stripped of hyphens/dashes
                tokens.add(alias.lower().replace("-", "").replace(" ", ""))

        return list(tokens), unique
    except Exception as e:
        print(f"  ⚠️  Could not fetch DB drugs: {e}")
        return [], []


def load_db_drugs_node(state: IntakeState) -> IntakeState:
    """Step [2/4] — populate state.db_tokens / state.db_drugs."""
    print("\n[2/4] Loading existing DB drugs for this company...")
    state.db_tokens, state.db_drugs = get_db_drugs_for_company(state.company_id)
    print(f"  DB drugs: {len(state.db_drugs)} rows ({len(state.db_tokens)} name tokens)")
    if state.verbose and state.db_drugs:
        for d in state.db_drugs:
            print(f"    • {d['id']:30} {d.get('name', '')}")

    state.mark_complete("load_db_drugs")
    return state
