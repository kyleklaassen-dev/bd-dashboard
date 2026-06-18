#!/usr/bin/env python3
"""
Prompt-data block builders for the Meridian Issue (§3 write_meridian split).
============================================================================
Extracted verbatim from write_meridian.py. enrich_intel_with_drug_context joins
intel rows to drug/company context; the build_*_block helpers render each data
slice (intel, deals, catalysts, ailux, prior coverage, company signals, trials,
graph) into the dense text blocks fed to the editorial prompts. Self-contained.
"""

from meridian.products.issue.common import AREA_NAMES


# ── Context enrichment ───────────────────────────────────────────────────────
def enrich_intel_with_drug_context(items, drugs, companies):
    """
    For each intel item, keyword-match against known drug names and company names.
    Append a compact DB-state block so the writer has live competitive context.
    """
    # Build lookup structures
    drug_lookup = {}   # lowercased token → drug record
    for d in drugs.values():
        for field in [d.get("name"), d.get("display_name"), d.get("id")]:
            if field and len(field) > 3:
                drug_lookup[field.lower()] = d

    company_lookup = {}  # lowercased token → company record
    for c in companies.values():
        for field in [c.get("name"), c.get("ticker"), c.get("id")]:
            if field and len(field) > 2:
                company_lookup[field.lower()] = c

    enriched = []
    for item in items:
        text = f"{item.get('headline','')} {item.get('body','')}".lower()

        matched_drugs = []
        seen_drug_ids = set()
        for token, drug in drug_lookup.items():
            if token in text and drug["id"] not in seen_drug_ids:
                matched_drugs.append(drug)
                seen_drug_ids.add(drug["id"])

        matched_companies = []
        seen_co_ids = set()
        for token, co in company_lookup.items():
            if token in text and co["id"] not in seen_co_ids:
                matched_companies.append(co)
                seen_co_ids.add(co["id"])

        ctx_lines = []
        for drug in matched_drugs[:4]:  # cap at 4 matched drugs
            parts = [
                f"  → {drug.get('display_name') or drug.get('name')} ({drug.get('company_id','')})",
                f"    Stage: {drug.get('stage','?')} | Target: {drug.get('target') or drug.get('mechanism','?')}",
                f"    Overlap: {drug.get('overlap','?')} | Indication: {drug.get('indication_short','?')}",
            ]
            if drug.get("ailux_angle"):
                parts.append(f"    BD Signal: {drug['ailux_angle']}")
            if drug.get("partner_company"):
                verified = "✓" if drug.get("partnership_verified") else "?"
                parts.append(f"    Partner: {drug['partner_company']} [{drug.get('partnership_type','')}] {verified}")
            ctx_lines.extend(parts)

        item = dict(item)
        item["_db_context"] = "\n".join(ctx_lines) if ctx_lines else None
        # Preserve the structured matches so the integration feed can resolve the
        # day's in-scope entities (the text _db_context alone is not machine-usable).
        item["_matched_drug_ids"]   = [d["id"] for d in matched_drugs]
        item["_matched_company_ids"] = [c["id"] for c in matched_companies]
        enriched.append(item)

    return enriched


# ── Build prompt data ────────────────────────────────────────────────────────
def build_intel_block(items):
    if not items:
        return "(No new intel items today)"
    lines = []
    for it in items:
        areas_str = ", ".join(AREA_NAMES.get(a, a) for a in it.get("areas", []))
        block = (
            f"[{it['importance'].upper()} | {it['intel_type']} | {areas_str}]\n"
            f"HEADLINE: {it['headline']}\n"
            f"DETAIL: {it['body']}\n"
            f"SOURCE: {it['source_name']} — {it['source_url']}\n"
            f"DATE: {it['intel_date']}"
        )
        if it.get("_db_context"):
            block += f"\nDB CONTEXT (live pipeline state for referenced assets):\n{it['_db_context']}"
        lines.append(block)
    return "\n\n---\n\n".join(lines)


def build_deals_block(deals):
    if not deals:
        return "(No recent deals)"
    lines = []
    for d in deals:
        val = f"${d['upfront_usd_m']}M upfront" if d.get("upfront_usd_m") else ""
        if d.get("total_usd_m"):
            val += f" / ${d['total_usd_m']}M total"
        lines.append(
            f"{d['deal_date']} | {d.get('deal_type','').upper()} | {AREA_NAMES.get(d['area_id'], d['area_id'])}\n"
            f"{d['from_company']} → {d['to_company']} {val}\n"
            f"{d['headline']}"
            + (f"\nDETAIL: {d['detail']}" if d.get("detail") else "")
        )
    return "\n\n".join(lines)


def build_catalysts_block(cats):
    if not cats:
        return "(No upcoming catalysts on record)"
    lines = []
    for c in cats:
        sig = c.get("significance", "").upper()
        notes = f" — {c['notes']}" if c.get("notes") else ""
        lines.append(
            f"{c['catalyst_date']} | {AREA_NAMES.get(c['area_id'], c['area_id'])} | {sig}\n"
            f"{c['label']}{notes}"
        )
    return "\n".join(lines)


def build_ailux_block(positions):
    """Construct the Ailux competitive anchor block from DB + static context."""
    # Static context is always included; DB positions supplement it
    static = """AILUX IDENTITY & COMPETITIVE POSITION:
Ailux Biotherapeutics is developing three bispecific antibody programs, all targeting IND by 2027:
- ALX001 (TL1A×IL-23p19): Lead IBD program for UC and CD. The p19 subunit selectivity preserves IL-12-driven Th1 immunity unlike p40-targeted agents. The bispecific hypothesis: simultaneous TL1A+IL-23 blockade achieves deep remission in the 40-45% of IBD patients who fail monospecific biologics.
- ALX002 (CD19×BCMA): I&I autoimmune program targeting SLE and Sjogren's via dual B-cell and plasma cell depletion.
- ALX005 (FcRn×Albumin): Rare disease program for gMG and CIDP; half-life extension bispecific format.

CRITICAL — SPYRE TL1A ASSETS ARE MONOSPECIFIC, NOT BISPECIFIC: SPY002 and SPY072 are two SEPARATE extended-half-life (YTE) MONOSPECIFIC anti-TL1A monoclonal antibodies from Spyre Therapeutics — NEITHER is a bispecific, and neither is an Ailux asset. SPY002 is in IBD (SKYLINE-UC; UC induction topline ~June 30 2026). SPY072 is in RHEUMATIC disease (SKYWAY basket: RA/PsA/axSpA; SKYWAY RA sub-study topline ~Q3 2026) — it has NO IBD program and there is no "ATLAS-1" trial. Treat both as TL1A-ARM benchmarks (proxies for the TL1A arm of ALX001), NOT as bispecific-format competitors. The genuine TL1A×IL-23p19 BISPECIFIC competitors to ALX001 are SIM0709 (Simcere/Boehringer Ingelheim), CLD-423 (Caldera/Qyuns — first subjects dosed Phase 1 Jan 2026), MT-251 (Mirador), XmAb412 (Xencor), HY8931 (Newsoara) and EAR-2001 (Earendil). RO7837195 (Roche/Pfizer) is another direct ALX001 competitor.

FORMAT / INDICATION DISCIPLINE (no assumptions): An asset's format (monospecific vs bispecific), molecular target, indication, and trial names come ONLY from its database row (target, target_class, modality, indication_short, stage_detail) and its drug_sources. NEVER infer "bispecific" from a hyphenated target string or a display name; a drug is bispecific ONLY if target_class says so. NEVER invent or guess a trial name, phase, or indication. If a fact is not in the DB or sources, leave it out rather than guessing.

TL1A CLASS STATE: Two monospecific anti-TL1A antibodies are in Phase 3 — tulisokibart (Merck, ATLAS-UC primary ~Nov 2026, first Ph3 TL1A readout) and afimkibart (Roche, AMETRINE-2 primary Jan 2027). Merck's readout is the single most consequential class validation event before Ailux reaches clinical inflection. A positive result validates sequencing and combination strategies and sets the monotherapy ceiling that a bispecific must exceed. A failure reshapes everything.

IL-23p19 CLASS STATE: Proven. Risankizumab (AbbVie, approved UC+CD), mirikizumab (Lilly, approved UC), guselkumab (J&J, CD Phase 3). Ailux enters against approved SOC — the clinical question is not "does IL-23 work" but "what does simultaneous TL1A+IL-23p19 blockade do beyond the sum of its parts."

BD PRIORITIES — what would actually move the needle for Ailux:
1. Combination data showing TL1A+IL-23 superiority over sequential therapy
2. Partner deals or licensing signals that reveal how the market values bispecific assets vs. monospecifics
3. Early-entry opportunities in less crowded Ailux areas (IGF1R/TED, FcRn, TSLP, T-cell/Treg)
4. Regulatory precedents for bispecific approval pathways in IBD
5. Clinical failures that reshape the competitive landscape or open white space"""

    if positions:
        pos_lines = []
        for p in positions:
            pos_lines.append(
                f"  Area: {p.get('area_id','')} | Ailux drug: {p.get('ailux_drug','')} "
                f"| Targets: {p.get('ailux_targets','')} | Stage: {p.get('ailux_stage','')}"
            )
            if p.get("ailux_angle"):
                pos_lines.append(f"  Angle: {p.get('ailux_angle')}")
        static += "\n\nLIVE DB POSITIONS:\n" + "\n".join(pos_lines)

    return static


def build_prior_coverage_block(recent_issues):
    """Give the writer a sense of what was covered in prior issues for continuity."""
    if not recent_issues:
        return "(No prior issue history available — this is the first issue.)"
    lines = []
    for i in recent_issues:
        intel_count = len(i.get("intel_ids") or [])
        lines.append(f"  {i['issue_date']}: {i['title']} ({intel_count} intel items)")
    return (
        "PRIOR ISSUE HISTORY (build on themes; connect to new developments; don't repeat without new signal):\n"
        + "\n".join(lines)
    )


def build_company_signals_block(signals):
    """Format current company intelligence bullets for the writer.
    Groups by company so the writer sees the full competitive posture of each player."""
    if not signals:
        return "(No company signals available)"
    by_company = {}
    for s in signals:
        cid = s.get("company_id", "?")
        by_company.setdefault(cid, []).append(s)
    lines = ["CURRENT COMPANY INTELLIGENCE (from live dashboard company cards):"]
    for company in sorted(by_company):
        lines.append(f"\n{company.upper()}:")
        for s in by_company[company]:
            stype = (s.get("dir") or s.get("signal_type") or "?").upper()
            lines.append(f"  [{stype}] {s.get('signal_text', '')}")
    return "\n".join(lines)


def build_trials_block(trials):
    """Format recent trial updates for editorial context."""
    if not trials:
        return "(No recent trial updates)"
    lines = ["RECENT CLINICAL TRIAL UPDATES (from dashboard trial tracker):"]
    for t in trials[:30]:  # cap at 30 to avoid prompt bloat
        drug   = t.get("drug_id", "?")
        phase  = t.get("phase", "?")
        status = t.get("status", "?")
        ind    = t.get("indication", "")
        name   = t.get("trial_name") or t.get("study_acronym", "")
        comp   = t.get("primary_completion_date", "")
        line   = f"  {drug} | Phase {phase} | {status} | {ind}"
        if comp:
            line += f" | completion: {comp}"
        if name:
            line += f" | {name}"
        lines.append(line)
    return "\n".join(lines)


def build_graph_block(active_in, targets_edges, competes_with):
    """
    Format entity_edges data as graph-grounded competitive intelligence.

    The graph supplements the editorial's drug/company context with stored
    structural relationships — who is where, what they target, and who
    directly competes. This is the L4-A graph injection layer.
    """
    if not active_in and not targets_edges and not competes_with:
        return "(Graph context unavailable)"

    PRIORITY_AREAS = ["tl1a", "tslp", "il4ra", "fcrn", "igf1r", "tcell", "ibd", "respiratory"]
    lines = ["GRAPH INTELLIGENCE (stored entity relationships — from entity_edges):"]

    # ── ACTIVE_IN: who is in each area ────────────────────────────────────────
    if active_in:
        lines.append("\nACTIVE PLAYERS BY AREA (ACTIVE_IN — confirmed company→area edges):")
        area_order = PRIORITY_AREAS + [a for a in sorted(active_in) if a not in PRIORITY_AREAS]
        for area in area_order:
            companies = active_in.get(area)
            if not companies:
                continue
            label = AREA_NAMES.get(area, area)
            lines.append(f"  {label}: {', '.join(sorted(companies))}")

    # ── TARGETS: mechanism convergence (which entities target the same mechanism) ──
    if targets_edges:
        # Reverse map: target → [entities]
        by_target = {}
        for entity, tgts in targets_edges.items():
            for t in tgts:
                by_target.setdefault(t, []).append(entity)
        # Only show contested mechanisms (≥2 entities)
        contested = {t: sorted(v) for t, v in by_target.items() if len(v) >= 2}
        if contested:
            lines.append("\nMECHANISM CONVERGENCE (TARGETS — mechanisms with multiple competing entities):")
            for target in sorted(contested, key=lambda t: -len(contested[t])):
                entities = contested[target]
                lines.append(f"  {target}: {', '.join(entities)} ({len(entities)} entities)")

    # ── COMPETES_WITH: direct competitive pairs ────────────────────────────────
    if competes_with:
        lines.append(f"\nDIRECT COMPETITIVE PAIRS (COMPETES_WITH — confirmed, {len(competes_with)} total):")
        # Group by shared tokens (rough area clustering)
        for subj, obj in competes_with[:50]:  # cap at 50 to avoid prompt bloat
            lines.append(f"  {subj} ↔ {obj}")

    return "\n".join(lines)
