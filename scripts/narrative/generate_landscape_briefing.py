#!/usr/bin/env python3
"""
generate_landscape_briefing.py

Pulls all company_profiles for a given area, runs a multi-call Opus synthesis
(splitting into 4 structured sections to stay within 45s/call limits), stores
the result in landscape_briefings table, and writes a markdown file to docs/.

Usage:
  python3 generate_landscape_briefing.py --area tl1a [--dry-run] [--force]

Requirements:
  ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY env vars

Options:
  --force   Overwrite an existing briefing for this area (default: skip if exists)
  --dry-run Print synthesis output but do not write to DB or disk
"""

import os, sys, json, argparse, time, datetime
import urllib.request, urllib.parse, pathlib

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from _common import load_credentials  # noqa: E402
import _db  # noqa: E402
import ai.client as ai_client  # noqa: E402
from ai.client import PromptConfig  # noqa: E402

SUPABASE_URL, SUPABASE_KEY, ANTHROPIC_API_KEY = load_credentials()
_db.init_db(SUPABASE_URL, SUPABASE_KEY)
ai_client.setup(ANTHROPIC_API_KEY)

AILUX_CONTEXT = """
Ailux Immunology is a clinical-stage biotech focused on TL1A pathway biology in IBD
and other inflammatory diseases. Its lead asset (SPY002) is a TL1A×IL-23p19 bispecific
antibody in Phase 1. Strategy: build toward Phase 2b data package, then partner or
out-license to a large pharma acquirer (Takeda, Lilly, AbbVie, Merck) or a co-development
partner (Sanofi, Boehringer Ingelheim) with the capital to fund Phase 3.
"""

SYSTEM_ANALYST = (
    "You are a pharmaceutical business development strategist working for Ailux Immunology. "
    "You produce concise, structured, actionable intelligence for internal BD strategy. "
    "Ground your analysis in the data provided. Flag any claims you cannot verify from the "
    "provided profiles. Respond ONLY with valid JSON — no markdown fences, no preamble."
)

SYSTEM_WRITER = (
    "You are a pharmaceutical business development strategist working for Ailux Immunology. "
    "You write crisp, argument-first strategic briefings. Every paragraph makes a claim and "
    "defends it. Avoid passive voice, generic platitudes, and filler. Write for a BD committee "
    "that reads under time pressure and wants to know what to do, not what exists."
)


# ── Supabase helpers ──────────────────────────────────────────────────────────

sb_get = _db.sb_get
sb_post = _db.sb_post

# ── Profile fetch ─────────────────────────────────────────────────────────────

def fetch_profiles(area_id: str) -> list[dict]:
    rows = sb_get("company_profiles", {
        "area_id": f"eq.{area_id}",
        "select":  ("company_id,area_id,platform_summary,bd_summary,key_risk,"
                    "why_it_matters,strategic_behavior,vs_ailux,risk_summary,bd_angle"),
        "order":   "company_id.asc",
    })
    return rows


def summarize_profile(p: dict) -> str:
    """Compact single-company summary for synthesis input."""
    cid = p["company_id"]
    lines = [f"=== {cid.upper()} ==="]
    for field in ["platform_summary", "bd_summary", "key_risk",
                  "why_it_matters", "strategic_behavior", "vs_ailux",
                  "risk_summary", "bd_angle"]:
        val = (p.get(field) or "").strip()
        if val:
            label = field.replace("_", " ").title()
            lines.append(f"{label}: {val[:350]}")
    return "\n".join(lines)


# ── Section synthesis helpers ─────────────────────────────────────────────────

def call_opus(system: str, user: str, max_tokens: int = 2000) -> str:
    cfg = PromptConfig(name="landscape_briefing", system=system,
                       model="claude-opus-4-6", max_tokens=max_tokens)
    raw = ai_client.run_text(cfg, user).strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw = "\n".join(lines).strip()
    return raw


def parse_json(raw: str, label: str) -> dict | list | None:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"  [JSON ERROR in {label}]: {raw[:200]}")
        return None


def synthesize_archetypes(profiles_text: str, area_id: str) -> tuple[list, str]:
    prompt = f"""Disease area: {area_id}
Ailux context: {AILUX_CONTEXT.strip()}

Company profiles (one per block):
{profiles_text}

Classify every company into one of these BD archetypes:
1. LIKELY_ACQUIRER — large pharma that will buy, not partner
2. LARGE_PHARMA_COMPETITOR — committed internally, not a partner
3. BISPECIFIC_COMPETITOR — direct clinical-stage bispecific competitor
4. LICENSING_ORIGINATOR — companies Ailux could license from
5. GEOGRAPHIC_PLAY — China-origin assets with ex-China licensing opportunity
6. PLATFORM_TOOL — IP/technology licensor (Fc, formulation, etc.)
7. MONITOR_ONLY — no actionable near-term BD angle

Return a JSON array of archetype clusters. Each element:
{{
  "archetype": "<one of the 7 above>",
  "companies": ["company_id1", "company_id2", ...],
  "implication": "2-3 sentences on strategic implication for Ailux"
}}

Return ONLY the JSON array. No markdown. No preamble."""

    raw = call_opus(SYSTEM_ANALYST, prompt, max_tokens=1200)
    data = parse_json(raw, "archetypes")
    if not data:
        return [], "## Section 1: BD Archetypes\n\n*Synthesis failed — retry.*"

    md_lines = ["# SECTION 1: BD ARCHETYPES\n"]
    for cluster in data:
        arch = cluster.get("archetype", "UNKNOWN")
        companies = ", ".join(cluster.get("companies", []))
        impl = cluster.get("implication", "")
        md_lines.append(f"## {arch}\n\n**Companies:** {companies}\n\n{impl}\n")

    return data, "\n".join(md_lines)


def synthesize_risk_themes(profiles_text: str, area_id: str) -> tuple[list, str]:
    prompt = f"""Disease area: {area_id}
Ailux context: {AILUX_CONTEXT.strip()}

Company profiles:
{profiles_text}

Identify the top 5 landscape-level risk themes — risks that appear across multiple companies
and represent structural threats to Ailux's BD strategy in this area (not company-specific risks).

Return a JSON array of exactly 5 elements:
{{
  "theme": "Short title",
  "companies": ["company_id", ...],
  "description": "2-3 sentences explaining the risk",
  "implication": "1-2 sentences on what Ailux should do about it"
}}

Return ONLY the JSON array. No markdown."""

    raw = call_opus(SYSTEM_ANALYST, prompt, max_tokens=1200)
    data = parse_json(raw, "risk_themes")
    if not data:
        return [], "## Section 2: Risk Themes\n\n*Synthesis failed — retry.*"

    md_lines = ["# SECTION 2: RISK CONCENTRATION MAP\n"]
    for i, theme in enumerate(data, 1):
        md_lines.append(f"## {i}. {theme.get('theme', '')}\n")
        companies = ", ".join(theme.get("companies", []))
        md_lines.append(f"**Exhibiting companies:** {companies}\n")
        md_lines.append(f"{theme.get('description', '')}\n")
        md_lines.append(f"**Ailux response:** {theme.get('implication', '')}\n")

    return data, "\n".join(md_lines)


def synthesize_opportunity_map(profiles_text: str, area_id: str) -> tuple[list, str]:
    prompt = f"""Disease area: {area_id}
Ailux context: {AILUX_CONTEXT.strip()}

Company profiles:
{profiles_text}

Identify 3 white space opportunities — structural gaps in the competitive landscape
that Ailux is uniquely positioned to exploit. Focus on gaps that are:
- Not being pursued by any competitor
- Actionable within 12-18 months
- High-leverage for Ailux's BD strategy

Return a JSON array of 3 elements:
{{
  "opportunity": "Short title",
  "rationale": "3-4 sentences explaining why this is a real gap and why Ailux is positioned for it",
  "deal_structure": "1-2 sentences on the concrete deal or action Ailux should pursue"
}}

Return ONLY the JSON array. No markdown."""

    raw = call_opus(SYSTEM_ANALYST, prompt, max_tokens=1000)
    data = parse_json(raw, "opportunity_map")
    if not data:
        return [], "## Section 3: Opportunity Map\n\n*Synthesis failed — retry.*"

    md_lines = ["# SECTION 3: WHITE SPACE & OPPORTUNITY MAP\n"]
    for opp in data:
        md_lines.append(f"## {opp.get('opportunity', '')}\n")
        md_lines.append(f"{opp.get('rationale', '')}\n")
        md_lines.append(f"**Deal structure:** {opp.get('deal_structure', '')}\n")

    return data, "\n".join(md_lines)


def synthesize_priority_matrix(profiles_text: str, area_id: str) -> tuple[list, str]:
    prompt = f"""Disease area: {area_id}
Ailux context: {AILUX_CONTEXT.strip()}

Company profiles:
{profiles_text}

Rank the top 10 engagement priorities for Ailux — companies or situations that deserve
the most immediate BD attention. Each entry should be actionable, specific, and time-bounded.

Return a JSON array of exactly 10 elements, ordered by priority:
{{
  "rank": 1,
  "company_id": "company_id",
  "engagement_type": "PARTNER | ACQUIRE | MONITOR | LICENSE | CO-DEVELOP",
  "headline": "One punchy sentence on the engagement thesis",
  "rationale": "3-4 sentences: why now, what deal structure, what trigger event",
  "timing": "Concrete window or trigger (e.g., 'Before Q3 2026 FIH', 'Post-ATLAS-UC (Nov 2026)')"
}}

Return ONLY the JSON array. No markdown."""

    raw = call_opus(SYSTEM_ANALYST, prompt, max_tokens=2000)
    data = parse_json(raw, "priority_matrix")
    if not data:
        return [], "## Section 4: Priority Matrix\n\n*Synthesis failed — retry.*"

    md_lines = ["# SECTION 4: PRIORITY MATRIX — TOP 10 ENGAGEMENTS\n"]
    for entry in data:
        rank = entry.get("rank", "?")
        cid  = entry.get("company_id", "unknown")
        etype = entry.get("engagement_type", "")
        headline = entry.get("headline", "")
        rationale = entry.get("rationale", "")
        timing = entry.get("timing", "")
        md_lines.append(f"## #{rank} — {cid.upper()} | {etype}\n")
        md_lines.append(f"**{headline}**\n")
        md_lines.append(f"{rationale}\n")
        md_lines.append(f"**Timing:** {timing}\n")

    return data, "\n".join(md_lines)


# ── Assemble full markdown ────────────────────────────────────────────────────

def build_full_markdown(area_id: str, profile_count: int,
                        arch_md: str, risk_md: str,
                        opp_md: str, matrix_md: str) -> str:
    date = datetime.date.today().isoformat()
    return f"""# {area_id.upper()} Landscape Intelligence Briefing

**Prepared for:** Ailux BD Committee
**Source:** {profile_count} company profiles — risk_summary + bd_angle meta-analysis
**Date:** {date}
**Model:** claude-opus-4-6

---

{arch_md}

---

{risk_md}

---

{opp_md}

---

{matrix_md}
"""


# ── DB persistence ────────────────────────────────────────────────────────────

def persist_briefing(area_id: str, profiles: list,
                     archetypes_json: list, risk_themes_json: list,
                     opportunity_map_json: list, priority_matrix_json: list,
                     full_markdown: str) -> str:
    """Insert into landscape_briefings table; return the new UUID."""
    company_ids = [p["company_id"] for p in profiles]
    payload = {
        "area_id":               area_id,
        "briefing_type":         "competitive_landscape",
        "title":                 f"{area_id.upper()} Competitive Landscape Briefing",
        "summary":               (
            f"Meta-analysis of {len(profiles)} company profiles in the {area_id} area. "
            f"Covers {len(archetypes_json)} BD archetypes, "
            f"{len(risk_themes_json)} risk themes, "
            f"{len(opportunity_map_json)} white space opportunities, "
            f"and {len(priority_matrix_json)} priority engagements."
        ),
        "source_profile_count":  len(profiles),
        "source_company_ids":    json.dumps(company_ids),
        "archetypes_json":       json.dumps(archetypes_json),
        "risk_themes_json":      json.dumps(risk_themes_json),
        "opportunity_map_json":  json.dumps(opportunity_map_json),
        "priority_matrix_json":  json.dumps(priority_matrix_json),
        "full_markdown":         full_markdown,
        "model_used":            "claude-opus-4-6",
        "confidence_level":      "medium",
        "needs_review":          True,
    }
    result = sb_post("landscape_briefings", payload)
    return (result or {}).get("id", "unknown")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--area",    default="tl1a", help="disease area id")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force",   action="store_true",
                        help="Overwrite existing briefing for this area")
    args = parser.parse_args()
    area_id = args.area

    # Check for existing briefing
    if not args.force and not args.dry_run:
        existing = sb_get("landscape_briefings", {
            "area_id": f"eq.{area_id}",
            "select":  "id,created_at",
            "limit":   "1",
            "order":   "created_at.desc",
        })
        if existing:
            print(f"Briefing already exists for '{area_id}' (id={existing[0]['id']}). "
                  f"Use --force to regenerate.")
            sys.exit(0)

    # Fetch profiles
    print(f"Fetching company_profiles for area '{area_id}'...")
    profiles = fetch_profiles(area_id)
    if not profiles:
        sys.exit(f"No profiles found for area_id='{area_id}'")

    # Filter to profiles that have at least one populated field
    populated = [p for p in profiles if any([
        p.get("platform_summary"), p.get("bd_summary"),
        p.get("risk_summary"),     p.get("bd_angle"),
    ])]
    print(f"  {len(populated)} / {len(profiles)} profiles have content. Using populated set.")

    profiles_text = "\n\n".join(summarize_profile(p) for p in populated)

    # Split profiles_text if very long (rough char split into halves for risk/opp)
    MAX_CHARS = 40_000
    if len(profiles_text) > MAX_CHARS:
        print(f"  Profile text is {len(profiles_text)} chars; truncating to {MAX_CHARS}.")
        profiles_text = profiles_text[:MAX_CHARS] + "\n\n[... additional profiles truncated ...]"

    print(f"\nRunning 4-section Opus synthesis for '{area_id}'...")

    print("  [1/4] Archetypes...", end=" ", flush=True)
    t0 = time.time()
    archetypes_json, arch_md = synthesize_archetypes(profiles_text, area_id)
    print(f"done ({time.time()-t0:.1f}s)")
    time.sleep(1)

    print("  [2/4] Risk themes...", end=" ", flush=True)
    t0 = time.time()
    risk_themes_json, risk_md = synthesize_risk_themes(profiles_text, area_id)
    print(f"done ({time.time()-t0:.1f}s)")
    time.sleep(1)

    print("  [3/4] Opportunity map...", end=" ", flush=True)
    t0 = time.time()
    opp_json, opp_md = synthesize_opportunity_map(profiles_text, area_id)
    print(f"done ({time.time()-t0:.1f}s)")
    time.sleep(1)

    print("  [4/4] Priority matrix...", end=" ", flush=True)
    t0 = time.time()
    matrix_json, matrix_md = synthesize_priority_matrix(profiles_text, area_id)
    print(f"done ({time.time()-t0:.1f}s)")

    full_markdown = build_full_markdown(
        area_id, len(populated),
        arch_md, risk_md, opp_md, matrix_md
    )

    if args.dry_run:
        print("\n[DRY RUN] Full markdown preview (first 2000 chars):\n")
        print(full_markdown[:2000])
        print("\n[DRY RUN] archetypes_json:", json.dumps(archetypes_json, indent=2)[:500])
        print("\n[DRY RUN] Skipping DB write and file write.")
        return

    # Write markdown file
    docs_dir = pathlib.Path(__file__).parent.parent / "docs"
    docs_dir.mkdir(exist_ok=True)
    md_path = docs_dir / f"{area_id}_landscape_briefing.md"
    md_path.write_text(full_markdown, encoding="utf-8")
    print(f"\nMarkdown written: {md_path}")

    # Persist to DB
    print("Persisting to landscape_briefings table...")
    briefing_id = persist_briefing(
        area_id, populated,
        archetypes_json, risk_themes_json, opp_json, matrix_json,
        full_markdown,
    )
    print(f"  -> Inserted: id={briefing_id}")
    print(f"\nDone. Briefing for '{area_id}' saved to DB + {md_path.name}.")
    print(f"  Note: needs_review=true — review and set to false when validated.")


if __name__ == "__main__":
    main()
