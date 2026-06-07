#!/usr/bin/env python3
"""
apply_prompt_improvements.py — N1 fix: Training Pairs Consumer
===============================================================
Reads training_pairs_YYYY-MM-DD.jsonl (from flywheel_phase2.py) and:

1. Extracts field-level quality patterns from confirmed examples
2. Generates ENRICHMENT_QUALITY_NOTES that can be injected into
   company_enrichment.py's prompt to improve output quality
3. Identifies systematic errors (fields Claude gets wrong repeatedly)
4. Writes a prompt_improvements.json with structured guidance

This is the Phase 4 self-evolution foundation: Meridian learns
from Kyle's confirmed ground truth to improve its own enrichment.

Usage:
  python3 scripts/apply_prompt_improvements.py
  python3 scripts/apply_prompt_improvements.py --date 2026-06-03
  python3 scripts/apply_prompt_improvements.py --inject  # update prompt hints in enrichment

Output:
  output/prompt_improvements.json — structured improvement guidance
  output/field_quality_report.json — which fields drift most often
"""

import os, sys, json, glob, re, argparse
from collections import defaultdict, Counter
from typing import Optional
import requests

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DATA = os.path.join(_REPO, "data")
_OUTPUT = os.path.join(_REPO, "output")
os.makedirs(_OUTPUT, exist_ok=True)

def _key(f):
    p = os.path.join(_REPO, f)
    return open(p).read().strip() if os.path.exists(p) else None

SUPABASE_URL = os.environ.get("SUPABASE_URL") or "https://tghntyofptvfhmtchwcv.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or _key(".supabase_service_key") or ""
BASE = f"{SUPABASE_URL}/rest/v1"
SB_H = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}


def sb_get(table, params, limit=500):
    params = {**params, "limit": str(limit)}
    r = requests.get(f"{BASE}/{table}", headers=SB_H, params=params, timeout=20)
    return r.json() if r.status_code == 200 else []


def load_training_pairs(date: Optional[str] = None) -> list:
    """Load the most recent (or date-specific) training pairs file."""
    if date:
        path = os.path.join(_OUTPUT, f"training_pairs_{date}.jsonl")
    else:
        files = sorted(glob.glob(os.path.join(_OUTPUT, "training_pairs_*.jsonl")), reverse=True)
        path = files[0] if files else None

    if not path or not os.path.exists(path):
        print(f"No training pairs file found")
        return []

    pairs = [json.loads(l) for l in open(path) if l.strip()]
    print(f"Loaded {len(pairs)} training pairs from {os.path.basename(path)}")
    return pairs


def load_drift_report(date: Optional[str] = None) -> dict:
    """Load the corresponding drift report."""
    if date:
        path = os.path.join(_OUTPUT, f"drift_report_{date}.json")
    else:
        files = sorted(glob.glob(os.path.join(_OUTPUT, "drift_report_*.json")), reverse=True)
        path = files[0] if files else None

    if not path or not os.path.exists(path):
        return {}
    return json.load(open(path))


def analyze_field_patterns(pairs: list, drift: dict) -> dict:
    """
    Extract patterns from confirmed training pairs to understand:
    - Which fields drift most (= enrichment model gets wrong repeatedly)
    - What good examples look like per field
    - Common failure modes per field
    """
    # Count confirmed examples per field
    field_examples = defaultdict(list)
    for pair in pairs:
        if pair.get("source") == "kyle_confirmed":
            field = pair.get("field","")
            response = pair.get("response","")
            if field and response:
                field_examples[field].append(response)

    # Drift analysis from drift report
    drifted = drift.get("drifted", [])
    field_drift_count = Counter(d.get("field","") for d in drifted)

    # Build quality notes per field
    quality_notes = {}
    for field, examples in sorted(field_examples.items(), key=lambda x: -len(x)):
        drift_rate = field_drift_count.get(field, 0)
        n = len(examples)

        # Analyze example patterns
        avg_len = sum(len(e) for e in examples) / max(n, 1)
        has_brackets = sum(1 for e in examples if "[INFERRED]" in e or "[ASSESSED]" in e)
        has_specifics = sum(1 for e in examples if any(c.isdigit() for c in e))

        note = {
            "field": field,
            "confirmed_count": n,
            "drift_count": drift_rate,
            "drift_rate_pct": round(drift_rate * 100 / max(n, 1)),
            "avg_confirmed_length": round(avg_len),
            "uses_inferred_labels": has_brackets > 0,
            "includes_specifics": has_specifics > (n * 0.5),
            "example_preview": examples[0][:150] if examples else "",
            "guidance": _derive_guidance(field, examples, drift_rate),
        }
        quality_notes[field] = note

    return quality_notes


def _derive_guidance(field: str, examples: list, drift_count: int) -> str:
    """Derive prompt guidance from confirmed examples for this field."""
    if not examples:
        return ""

    avg_len = sum(len(e) for e in examples) / len(examples)

    if field == "ailux_angle":
        return (f"Write {round(avg_len)} chars. Always include: (1) mechanism relationship to TL1A/IL-23, "
                "(2) BD action (partner/compete/benchmark/monitor). Never generic — always drug-specific.")
    elif field == "drug_summary":
        return (f"Write {round(avg_len)} chars. Lead with mechanism + stage + key differentiator. "
                "Include company name. No adjectives (important/noteworthy) — show the fact.")
    elif field == "differentiation_thesis":
        return (f"Write {round(avg_len)} chars. 1-2 sentences max. Focus on what makes this drug "
                "unique vs its class — format, half-life, dosing schedule, clinical data advantage.")
    elif field == "source_url":
        return "Always prefer CT.gov study URL or company IR press release. Never fabricate."
    elif drift_count > 3:
        return f"HIGH DRIFT FIELD ({drift_count} regressions). Be precise and specific — vague answers tend to drift."
    else:
        return f"Confirmed average length: {round(avg_len)} chars."


def generate_enrichment_prompt_hints(quality_notes: dict) -> str:
    """Generate a block of guidance text for injection into enrichment prompts."""
    lines = ["## FIELD QUALITY GUIDANCE (from confirmed ground truth)\n"]
    lines.append("Apply these guidelines when generating each field:\n")

    # Sort by drift rate (most problematic first)
    sorted_notes = sorted(quality_notes.values(), key=lambda x: -x.get("drift_rate_pct", 0))

    for note in sorted_notes[:10]:  # top 10 most-confirmed fields
        field = note["field"]
        guidance = note["guidance"]
        drift = note["drift_count"]
        flag = f" ⚠️ drifts {drift}x" if drift > 2 else ""
        lines.append(f"  - {field}{flag}: {guidance}")

    return "\n".join(lines)


def inject_into_enrichment(prompt_block: str):
    """Write prompt hints to a companion file that company_enrichment.py can read."""
    hints_path = os.path.join(_OUTPUT, "enrichment_prompt_hints.md")
    with open(hints_path, "w") as f:
        f.write("# Enrichment Prompt Quality Hints\n")
        f.write("<!-- Auto-generated by apply_prompt_improvements.py -->\n\n")
        f.write(prompt_block)
    print(f"Prompt hints written to: {hints_path}")


def main():
    parser = argparse.ArgumentParser(description="N1: Consume training pairs → prompt improvements")
    parser.add_argument("--date", default=None, help="Date of training file (YYYY-MM-DD)")
    parser.add_argument("--inject", action="store_true", help="Write hints to enrichment_prompt_hints.md")
    args = parser.parse_args()

    pairs = load_training_pairs(args.date)
    drift = load_drift_report(args.date)

    if not pairs:
        print("No training data — run flywheel_phase2.py first")
        sys.exit(0)

    # Analyze patterns
    quality_notes = analyze_field_patterns(pairs, drift)

    # Generate improvement guidance
    prompt_block = generate_enrichment_prompt_hints(quality_notes)
    print("\n" + prompt_block)

    # Write outputs
    improvements_path = os.path.join(_OUTPUT, "prompt_improvements.json")
    with open(improvements_path, "w") as f:
        json.dump({
            "generated": __import__("datetime").date.today().isoformat(),
            "training_pairs_count": len(pairs),
            "fields_analyzed": len(quality_notes),
            "top_drift_fields": [n["field"] for n in
                sorted(quality_notes.values(), key=lambda x: -x.get("drift_rate_pct",0))[:5]],
            "quality_notes": quality_notes,
            "prompt_block": prompt_block,
        }, f, indent=2)
    print(f"\nImprovements written: {improvements_path}")

    quality_path = os.path.join(_OUTPUT, "field_quality_report.json")
    with open(quality_path, "w") as f:
        report = {k: {"confirmed": v["confirmed_count"], "drifted": v["drift_count"],
                      "drift_pct": v["drift_rate_pct"], "guidance_preview": v["guidance"][:80]}
                  for k, v in quality_notes.items()}
        json.dump(report, f, indent=2)
    print(f"Quality report: {quality_path}")

    if args.inject:
        inject_into_enrichment(prompt_block)


if __name__ == "__main__":
    main()
