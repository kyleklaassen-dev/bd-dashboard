"""
Shared console-output helpers for the company intake pipeline.

print_area_map is invoked from two points in the intake graph: the early
exit when no areas clear the relevance threshold (score_areas) and the
final summary after queue rows are written (write_queue).
"""
from __future__ import annotations

from pipeline.company_intake.nodes.research_company import ACTIVE_AREAS


def print_area_map(company_name: str, research: dict, relevant_areas: list, written: list) -> None:
    co = research.get("company", {})
    print()
    print("═" * 65)
    print(f"  AREA MAP — {co.get('canonical_name', company_name)}")
    ticker = co.get("ticker")
    if ticker:
        print(f"  {ticker} · {co.get('exchange', '')} · {co.get('geography', '')}")
    print(f"  {co.get('tagline', '')}")
    print("═" * 65)

    if not relevant_areas:
        print("  No areas meet the minimum evidence threshold.")
        print("  Company may not operate in active Meridian focus areas.")
    else:
        for area in relevant_areas:
            aid = area["area_id"]
            label = ACTIVE_AREAS[aid]["label"]
            status = "✅ queued" if aid in written else "⏭️  skipped"
            conf_bar = "█" * int(area["confidence"] * 10) + "░" * (10 - int(area["confidence"] * 10))
            print(f"\n  {area['relevance']:<15} {label}")
            print(f"  Confidence  [{conf_bar}] {area['confidence']:.0%}  {status}")
            print(f"  Rationale   {area['rationale'][:120]}")
            if area["evidence"]:
                print(f"  Evidence    {area['evidence'][:120]}")

    pipeline = research.get("pipeline", [])
    if pipeline:
        print(f"\n  Pipeline ({len(pipeline)} drug{'s' if len(pipeline) != 1 else ''} found):")
        for d in pipeline[:6]:
            stage = d.get("stage", "?")
            print(f"    • {d['drug_name']} — {d['target']} — {stage} — {d['indication'][:60]}")
        if len(pipeline) > 6:
            print(f"    ... and {len(pipeline) - 6} more")

    deals = research.get("deals", [])
    if deals:
        print(f"\n  Deals ({len(deals)} found):")
        for dl in deals[:3]:
            print(f"    • {dl.get('date', '?')} — {dl.get('partner', '?')} — {dl.get('asset', '?')}")

    why = research.get("why_relevant")
    if why:
        print(f"\n  BD Angle: {why}")

    print()
    print(f"  Data quality: {research.get('data_quality', 'unknown')}")
    if written:
        print(f"  {len(written)} area row(s) written to discovery_queue (source=user_intake, status=pending)")
        print("  → Review in Meridian Dashboard → Discovery Queue tab")
    print("═" * 65)
    print()
