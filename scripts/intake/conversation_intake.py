#!/usr/bin/env python3
"""
conversation_intake.py
======================
Auto-capture intelligence from session notes and store in
conversation_intelligence_intake for review.

Run at the END of every session:
  python3 scripts/conversation_intake.py --session-notes "..."

Or in batch from a file:
  python3 scripts/conversation_intake.py --notes-file session_notes.txt

High-confidence facts (>0.85) auto-create a governance_violation row
flagging them for human confirmation before promotion to canonical tables.

Usage:
  python3 scripts/conversation_intake.py --session-notes "Notes text here..."
  python3 scripts/conversation_intake.py --notes-file path/to/notes.txt
  python3 scripts/conversation_intake.py --review   # show pending items
  python3 scripts/conversation_intake.py --promote ID  # confirm + promote item
"""

import os
import sys
import json
import argparse
from datetime import date

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from _common import load_credentials      # noqa: E402
import _db                                 # noqa: E402
import ai.client as ai_client              # noqa: E402
from ai.client import PromptConfig         # noqa: E402

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SUPABASE_URL, SUPABASE_KEY, ANTHROPIC_KEY = load_credentials()
_db.init_db(SUPABASE_URL, SUPABASE_KEY)
ai_client.setup(ANTHROPIC_KEY)

_INTAKE_CFG = PromptConfig(
    name="conversation_intake_extract",
    system="",
    model="claude-opus-4-5",
    max_tokens=4096,
)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
INTAKE_PROMPT = """You are a knowledge extraction agent for the Meridian pharmaceutical intelligence platform (Ailux Biotherapeutics BD platform).

Extract ALL new factual intelligence from the following session notes and return as a JSON array.

Rules:
- Only extract FACTS, not interpretations or opinions
- Each fact must reference a specific drug name, company, number, date, mechanism, or regulatory event
- Do NOT invent facts — only extract what is explicitly stated
- Set auto_confidence based on: explicit citation = 0.90+, named source = 0.75-0.89, stated as known = 0.60-0.74, inferred = 0.40-0.59
- Set should_auto_promote = true ONLY if confidence > 0.85 AND fact is a simple field update (stage, date, NCT ID)

For each new fact produce one JSON object:
{
  "entity_type": "drug" | "company" | "deal" | "clinical_data" | "regulatory" | "biomarker" | "timeline",
  "entity_id": "supabase id if known, else null",
  "entity_name": "exact drug/company name as mentioned",
  "fact_type": "new_drug" | "stage_update" | "deal_announced" | "efficacy_data" | "correction" | "new_relationship" | "timeline_update" | "biomarker_update",
  "fact_text": "exact factual statement (1-2 sentences, precise)",
  "supporting_quote": "verbatim phrase from the notes that triggered this extraction",
  "auto_confidence": 0.0 to 1.0,
  "should_auto_promote": true or false
}

Session notes:
{notes}

Return ONLY the JSON array with no markdown, no preamble, no trailing text. If no facts are found, return [].
"""

# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def extract_facts(notes: str) -> list[dict]:
    """Use Claude to extract structured facts from free-text session notes."""
    prompt = INTAKE_PROMPT.replace('{notes}', notes)

    # run_text (not run_json): the response is a JSON *array*, and
    # ai_client._parse_json only handles top-level JSON objects.
    raw = ai_client.run_text(_INTAKE_CFG, prompt).strip()

    # Strip markdown code fences if present
    if raw.startswith('```'):
        raw = raw.split('```')[1]
        if raw.startswith('json'):
            raw = raw[4:]
    raw = raw.strip()

    try:
        facts = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"WARNING: Could not parse Claude response as JSON: {e}")
        print(f"Raw response: {raw[:500]}")
        facts = []

    return facts


def store_facts(facts: list[dict], source: str = 'conversation') -> int:
    """Insert extracted facts into conversation_intelligence_intake."""
    if not facts:
        return 0

    today = date.today().isoformat()
    rows = []
    for f in facts:
        row = {
            'session_date': today,
            'source': source,
            'entity_type': f.get('entity_type'),
            'entity_id': f.get('entity_id'),
            'entity_name': f.get('entity_name'),
            'fact_type': f.get('fact_type'),
            'fact_text': f.get('fact_text', ''),
            'supporting_quote': f.get('supporting_quote'),
            'auto_confidence': float(f.get('auto_confidence', 0.60)),
            'review_status': 'pending'
        }
        rows.append(row)

    inserted = 0
    for row in rows:
        result = _db.sb_post('conversation_intelligence_intake', row)
        if result is not None:
            inserted += 1
            conf = row['auto_confidence']
            flag = ' [HIGH CONF — governance flag queued]' if conf > 0.85 else ''
            print(f"  STORED [{conf:.2f}]: {row['entity_name']} — {row['fact_text'][:80]}{flag}")
        else:
            print(f"  FAIL: insert failed for {row['entity_name']}")

    return inserted


def show_pending():
    """Display all pending intake items for review."""
    items = _db.sb_get('conversation_intelligence_intake', {
        'review_status': 'eq.pending',
        'order':         'auto_confidence.desc',
    })

    if not items:
        print("No pending intake items.")
        return

    print(f"\n{'='*70}")
    print(f"PENDING INTAKE ITEMS ({len(items)} total)")
    print(f"{'='*70}")

    for item in items:
        conf = item.get('auto_confidence', 0)
        flag = ' *** HIGH CONFIDENCE ***' if conf > 0.85 else ''
        print(f"\n[ID {item['id']}] {item['session_date']} | conf={conf:.2f}{flag}")
        print(f"  Entity: {item['entity_name']} ({item['entity_type']})")
        print(f"  Type:   {item['fact_type']}")
        print(f"  Fact:   {item['fact_text']}")
        if item.get('supporting_quote'):
            print(f"  Quote:  \"{item['supporting_quote']}\"")

    print(f"\n{'='*70}")
    print("To confirm an item: python3 scripts/conversation_intake.py --promote ID")
    print("To reject an item:  python3 scripts/conversation_intake.py --reject ID")


def promote_item(item_id: int):
    """Mark an intake item as confirmed and log it for manual DB promotion."""
    items = _db.sb_get('conversation_intelligence_intake', {'id': f'eq.{item_id}'})
    if not items:
        print(f"Item {item_id} not found.")
        return

    item = items[0]

    # Mark as confirmed
    update = {
        'review_status': 'confirmed',
        'reviewed_by': 'kyle',
        'reviewed_at': date.today().isoformat() + 'T00:00:00Z'
    }
    ok = _db.sb_patch('conversation_intelligence_intake', update, {'id': f'eq.{item_id}'})

    if ok:
        print(f"\nItem {item_id} confirmed:")
        print(f"  {item['entity_name']} — {item['fact_text']}")
        print(f"\nNEXT STEP: Manually promote to canonical table:")
        print(f"  Entity type: {item['entity_type']}")
        print(f"  Entity ID:   {item.get('entity_id', 'UNKNOWN')}")
        print(f"  Fact type:   {item['fact_type']}")
        print(f"  Fact text:   {item['fact_text']}")
        print(f"\nUse Supabase REST API or SQL editor to apply the canonical update.")
    else:
        print(f"FAIL: could not update item {item_id}")


def reject_item(item_id: int):
    """Mark an intake item as rejected."""
    update = {
        'review_status': 'rejected',
        'reviewed_by': 'kyle',
        'reviewed_at': date.today().isoformat() + 'T00:00:00Z'
    }
    ok = _db.sb_patch('conversation_intelligence_intake', update, {'id': f'eq.{item_id}'})
    if ok:
        print(f"Item {item_id} rejected.")
    else:
        print(f"FAIL: could not update item {item_id}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Meridian Conversation Intelligence Intake Agent')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--session-notes', type=str, help='Free-text session notes to process')
    group.add_argument('--notes-file', type=str, help='Path to file containing session notes')
    group.add_argument('--review', action='store_true', help='Show pending intake items')
    group.add_argument('--promote', type=int, metavar='ID', help='Confirm and promote intake item by ID')
    group.add_argument('--reject', type=int, metavar='ID', help='Reject intake item by ID')
    args = parser.parse_args()

    if args.review:
        show_pending()
        return

    if args.promote:
        promote_item(args.promote)
        return

    if args.reject:
        reject_item(args.reject)
        return

    # Extract from notes
    notes = None
    if args.session_notes:
        notes = args.session_notes
    elif args.notes_file:
        with open(args.notes_file) as f:
            notes = f.read()
    else:
        # Read from stdin if no args
        print("Enter session notes (Ctrl+D when done):")
        notes = sys.stdin.read()

    if not notes or not notes.strip():
        print("No notes provided.")
        sys.exit(1)

    print(f"\nExtracting intelligence from session notes ({len(notes)} chars)...")
    facts = extract_facts(notes)

    if not facts:
        print("No facts extracted.")
        return

    print(f"\nExtracted {len(facts)} facts. Storing to conversation_intelligence_intake...")
    inserted = store_facts(facts)
    print(f"\nDone: {inserted}/{len(facts)} facts stored.")
    print("\nRun `python3 scripts/conversation_intake.py --review` to review pending items.")


if __name__ == '__main__':
    main()
