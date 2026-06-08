"""
Node: diff_pipeline  (mode="reaudit" only)
Step [4/4] (diff phase) — fuzzy-match each drug from the fresh research
pull against the DB token set and split into seen vs. new (gap) drugs.
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

from pipeline.company_intake.state import IntakeState  # noqa: E402


def drug_already_in_db(drug_name: str, db_tokens: list) -> bool:
    """
    Fuzzy match: is this pipeline drug already captured in the DB?
    Checks cleaned drug name against the flat token set.
    """
    name_clean = drug_name.lower().replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
    name_words = [w for w in drug_name.lower().split() if len(w) >= 4]

    # Direct substring match on cleaned name
    for token in db_tokens:
        token_clean = token.replace("-", "").replace(" ", "")
        if name_clean == token_clean or name_clean in token_clean or token_clean in name_clean:
            return True

    # Word-level match (any long word in the drug name hits a DB token)
    for word in name_words:
        if word in db_tokens:
            return True

    return False


def diff_pipeline_node(state: IntakeState) -> IntakeState:
    """
    Step [4/4] diff phase — populate state.new_drugs / state.seen_drugs.
    Prints the per-drug diff and summary; routing decides whether write_gaps runs.
    """
    print("\n[4/4] Diffing pipeline against DB...")
    pipeline = state.research.get("pipeline", [])

    new_drugs:  list = []
    seen_drugs: list = []

    for drug in pipeline:
        drug_name = drug.get("drug_name", "")
        if not drug_name:
            continue
        if drug_already_in_db(drug_name, state.db_tokens):
            seen_drugs.append(drug_name)
            print(f"  ✓  {drug_name} — already in DB")
        else:
            new_drugs.append(drug)
            print(f"  ✦  {drug_name} — NOT in DB  [{drug.get('stage','?')} | {drug.get('target','?')}]")

    state.seen_drugs = seen_drugs
    state.new_drugs  = new_drugs

    print(f"\n  Summary: {len(seen_drugs)} already in DB, {len(new_drugs)} new gap(s) found")
    if not new_drugs:
        print("  ✅ No gaps — DB matches live pipeline.")

    state.mark_complete("diff_pipeline")
    return state
