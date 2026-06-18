#!/usr/bin/env python3
"""
Step 1 — Entity Discovery (§3 company_enrichment split).
========================================================
Extracted verbatim from company_enrichment.py.

Live web search (Phase A) + Claude synthesis (Phase B) to find NEW companies / drug
programs relevant to a disease area but not yet in the DB, then create company/drug/
company_areas records tagged discovery_status='auto'. Self-contained — calls no other
company/* feature module.
"""

import json
import re
import datetime

from meridian.enrichment.company.common import (
    client, _acc_tokens, log, sb_get, sb_post,
    TODAY, VALID_AREA_IDS, AREA_LABELS_MAP, normalize_area_id, KNOWN_DRUG_TARGETS,
)
from meridian.enrichment.company.resolve import resolve_company_id


# ══════════════════════════════════════════════════════════════════════════
# STEP 1 — ENTITY DISCOVERY
#
# IF new competitor found in the target/disease space:
#   → Create company + drug + company_areas records
#   → Tag discovery_status='auto', confidence_score
#   → Link to disease area
#
# Phase A: Live web search for current competitive landscape (web_search_20250305)
# Phase B: Claude Haiku compares landscape against existing DB, extracts new entities
# Secondary: recent Supabase intel used as supplemental signal if available
# ══════════════════════════════════════════════════════════════════════════

DISCOVERY_SYSTEM = """You are a biopharma competitive intelligence analyst for Ailux Biotherapeutics.
Identify NEW companies or drug programs that are relevant to the given disease area but not yet in our
database. Return ONLY valid JSON — no markdown, no explanation."""

LANDSCAPE_SEARCH_SYSTEM = """You are a biopharma competitive intelligence researcher.
Use web_search to find ALL companies with drug programs in the given target area — at ANY stage,
from preclinical through approved. Include large pharma (Pfizer, Roche, AZ, Lilly, etc.) as well
as small/mid-cap biotechs and early-stage companies.

IMPORTANT: Do NOT limit results to clinical-stage programs. Preclinical and IND-enabling programs
are strategically critical — they represent future competitors and partnership opportunities.
Be comprehensive — missing a player (especially an early-stage one) is worse than a false positive.

For each program found, report: company name, drug name/compound ID, mechanism of action, stage
(Preclinical/IND Enabling/Phase 1/Phase 2/Phase 3/Approved), indication, partnership details.

# TRANSACTION_PIPELINE_EXPANSION
When enriching a company, investigate not only internally discovered assets, but also assets
acquired through M&A, licensing, partnerships, and platform transactions. The company's pipeline
should reflect current ownership and control, not merely original invention. Every acquired company
should be treated as a potential pipeline import event requiring asset discovery and area
reclassification. When a company has acquired another entity or signed a major licensing deal,
ingest the ENTIRE acquired pipeline — all stages, not just the headline asset — and re-map
company areas, competitive landscapes, and strategic relevance accordingly."""


def gather_landscape_intel(area_id: str) -> str:
    """
    Phase A of Step 1: live web search for current competitive landscape.
    Returns free-text summary or empty string on failure.
    """
    area_label = AREA_LABELS_MAP.get(area_id, area_id)
    year = datetime.datetime.utcnow().year

    prompt = (
        f"Search for ALL companies with drug programs targeting {area_label} "
        f"as of {year-1}-{year}, at ANY stage from preclinical through approved. Include:\n"
        "1. Large pharma (Pfizer, Roche, AstraZeneca, Lilly, Sanofi, AbbVie, etc.) with relevant programs\n"
        "2. Mid-cap and small-cap biotechs\n"
        "3. Early-stage companies with preclinical or IND-enabling programs\n"
        "4. China-based companies — search ChiCTR registry, Chinese pharma pipeline pages\n\n"
        "For each program, report: company name, drug name/compound ID, mechanism of action, "
        "stage (Preclinical / IND Enabling / Phase 1 / Phase 2 / Phase 3 / Approved), "
        "indication, partnership details.\n\n"
        "Search ALL of these source types:\n"
        "- ClinicalTrials.gov for registered trials (Phase 1+)\n"
        "- Company pipeline pages and IR websites for preclinical/IND-enabling disclosures\n"
        "- Investor presentations and R&D day slides for pipeline updates\n"
        "- Conference abstracts (DDW, ECCO, ASCO, ATS, EULAR, ACR, ADA, ESMO) for emerging data\n"
        "- Press releases and news for company/deal announcements\n\n"
        "CRITICAL: Do not skip a program just because it is preclinical or has no registered trial. "
        "A company disclosing a preclinical program on their pipeline page or at a conference is a "
        "strategically important competitive signal."
    )

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2500,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
            system=LANDSCAPE_SEARCH_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            timeout=90.0,  # cap at 90s to avoid infinite hang
        )
        _acc_tokens(resp)
        parts = [block.text for block in resp.content if hasattr(block, "text") and block.text]
        return "\n\n".join(parts)
    except Exception as e:
        log(f"  Landscape search error: {e}", indent=1)
        return ""


def step1_discover_new_entities(area_id: str, company_map: dict,
                                  dry_run: bool = False, resolver=None) -> int:
    """
    Proactively discover new competitors via live web search, then diff against
    the existing Supabase entity list. Supplemented by recent in-DB intel.

    IMPORTANT: Discovered entities are NO LONGER auto-inserted into production tables.
    Instead they are written to discovery_queue (status='pending') for manual review.
    Only after human approval are they promoted to companies/drugs/company_areas.

    Relevance scoring (1-10):
      9-10 → Critical (Direct Mechanism or major Clinical Competition) → priority review
      7-8  → Important (Layer 2/3, late-stage) → standard review
      5-6  → Watch (early stage, emerging mechanism)
      <5   → Low relevance → auto-archived, no queue notification

    Returns count of items written to discovery_queue.
    """
    # ── Normalize + validate area_id before anything else ────────────────────
    _raw_area = area_id
    area_id = normalize_area_id(area_id)
    if not area_id:
        log(f"[ERROR] Invalid area_id '{_raw_area}' — not in VALID_AREA_IDS {VALID_AREA_IDS}. Aborting.", indent=0)
        return 0
    if area_id != _raw_area:
        log(f"[WARN] area_id normalized '{_raw_area}' → '{area_id}'", indent=0)

    # Run ID ties every row in this batch to a specific discovery run — critical for debugging
    run_id = f"{area_id}_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M')}"

    log(f"\n{'─'*50}")
    log(f"STEP 1 — Entity Discovery (area: {area_id}, run_id: {run_id})")
    log(f"{'─'*50}")

    existing_cos = sb_get("company_areas", {
        "area_id": f"eq.{area_id}", "select": "company_id"
    })
    existing_ids = {r["company_id"] for r in existing_cos}

    # Fetch indication_group for this area (e.g. tl1a → 'ibd').
    # New drugs are tagged to BOTH the specific area AND the indication_group area,
    # so the frontend's expanded drug row (filtered by indication_group) picks them up.
    area_meta = sb_get("disease_areas", {"id": f"eq.{area_id}", "select": "indication_group"})
    indication_group = (area_meta[0].get("indication_group") if area_meta else None) or area_id

    # ── Phase A: live web search for current landscape ──────────────────────
    log("  Phase A — Web landscape search...", indent=1)
    landscape_text = gather_landscape_intel(area_id)
    if landscape_text:
        log(f"  Landscape search returned {len(landscape_text)} chars", indent=1)
    else:
        log("  Landscape search returned nothing — will rely on local intel", indent=1)

    # ── Secondary: recent Supabase intel (last 14 days) ─────────────────────
    fourteen_ago = (datetime.datetime.utcnow() - datetime.timedelta(days=14)).strftime("%Y-%m-%d")
    intel_areas = sb_get("intel_areas", {"area_id": f"eq.{area_id}", "select": "intel_id"})
    intel_ids   = [r["intel_id"] for r in intel_areas[:20]]
    recent_intel = []
    for iid in intel_ids:
        rows = sb_get("intel", {
            "id":         f"eq.{iid}",
            "intel_date": f"gte.{fourteen_ago}",
            "select":     "headline,body,source_url",
        })
        recent_intel.extend(rows)

    if not landscape_text and not recent_intel:
        log("  No web results and no local intel — skipping discovery", indent=1)
        return 0

    intel_text = "\n\n".join(
        f"HEADLINE: {i['headline']}\nBODY: {(i.get('body') or '')[:300]}"
        for i in recent_intel[:10]
    ) if recent_intel else "(none)"

    existing_list = ", ".join(sorted(existing_ids)[:40])

    # Build landscape section safely (no nested f-string with special chars)
    landscape_section = ""
    if landscape_text:
        landscape_section = (
            "\nCURRENT LANDSCAPE (live web search — primary signal):\n"
            + landscape_text[:3000]
        )

    prompt = (
        f"Disease area: {area_id}  |  Today: {TODAY}\n"
        f"Already tracked IDs: {existing_list}\n"
        f"{landscape_section}\n"
        f"\nSUPPLEMENTAL INTEL (recent Supabase intel, last 14 days):\n{intel_text}\n\n"
        f"Find NEW companies or drugs in THIS SPECIFIC AREA ({area_id}) NOT already tracked above.\n"
        "Include large pharma subsidiaries/programs if their compound is not yet tracked.\n"
        "Return only genuine competitive entries (not CROs, service providers, etc.).\n\n"
        f"CRITICAL — AREA-SPECIFIC DRUG ASSIGNMENT:\n"
        f"Each entity you return must have drug_name set to the drug RELEVANT TO {area_id.upper()},\n"
        "NOT a different drug from the same company's pipeline in a different area.\n"
        "Example: if Hengrui has HR7044 (TSLP) AND SHR0817 (IL-4Rα), and you are discovering\n"
        "for area_id=il4ra, set drug_name='SHR0817'. Do NOT set drug_name='HR7044'.\n"
        "If the company has no area-specific drug, omit drug_name (null).\n\n"
        "SCOPE — THINK INDICATION-FIRST, NOT JUST MECHANISM:\n"
        "Do not limit discovery to exact-mechanism matches. Include companies that compete\n"
        "for the SAME PATIENTS in the SAME INDICATION even if their mechanism differs.\n"
        "Examples: for IBD/TL1A, include IL-23 inhibitors, IL-23+TNF combo programs, JAKs\n"
        "with active UC/CD trials. For atopic disease, include OX40L, IL-31, IL-13 programs.\n"
        "A company running a Phase 3 combo study in UC belongs in the IBD competitive map\n"
        "even if their drug doesn't target TL1A directly. Assign overlap='Adjacent' for these.\n\n"
        "CRITICAL ACQUISITION RULE: If a company was wholly acquired and its drug now belongs to\n"
        "the acquirer (e.g., Prometheus Biosciences was acquired by Merck — tulisokibart is now\n"
        "Merck's program), DO NOT list the acquired company as a new_entity. The drug lives under\n"
        "the acquirer. If the acquirer is NOT yet tracked, list the acquirer as the entity.\n"
        "Only set acquired_by if you are adding the company AND know it was acquired — this\n"
        "is rare (most of the time just skip the acquired company entirely).\n\n"
        "COMPETITION LAYERS:\n"
        "  layer 1 = Direct Mechanism (same target/class as the lead asset)\n"
        "  layer 2 = Direct Clinical Competition (same indication/patient population, different mechanism)\n"
        "  layer 3 = Strategic Threat (adjacent indication, platform breadth, or deal activity)\n\n"
        "RELEVANCE SCORING (1-10):\n"
        "  9-10 = Critical competitor (Direct Mechanism or major late-stage Clinical Competition)\n"
        "  7-8  = Important (Layer 2/3 with Phase 2+ data in same patient population)\n"
        "  5-6  = Watch (early stage, emerging mechanism, or adjacent indication)\n"
        "  1-4  = Low relevance (very early, different patient population)\n\n"
        '{"new_entities": [{'
        '"company_name": "...", "drug_name": "... or null", "target": "...",'
        '"stage": "Phase 1|Phase 2|Phase 3|Pre-IND|Preclinical",'
        '"modality": "mAb|bispecific|small molecule|ADC|nanobody|fusion protein|unknown",'
        '"route": "SC|IV|oral|unknown|null",'
        '"entity_type": "company|molecule|trial|deal|catalyst|article|evidence_item",'
        '"partner_co": "name of licensor/partner company or null",'
        '"acquired_by": "company_id of the acquirer if this entity was wholly acquired and no longer independent, else null",'
        '"overlap": "Direct|Adjacent|Same-Space|Watch",'
        '"competition_layer": 1|2|3,'
        '"relevance_score": 1-10,'
        '"relevance_rationale": "why this score — patient population overlap, stage, mechanism",'
        '"confidence": 60-100,'
        '"reason": "one sentence — why this entity matters for this area",'
        '"suggested_dest": "new_company|molecule_update|trial_update|deal_update|catalyst_update|evidence_update",'
        '"relationship_type": "peer_competitor|licensor|licensee|partner|parent_subsidiary|asset_owner|co_developer|direct_competitor|adjacent_competitor|unknown",'
        '"relationship_confidence": "confirmed|inferred|suggested",'
        '"why_discovered": "brief explanation of what search query / criteria matched this entity"'
        "}]}\n\n"
        "RELATIONSHIP CLASSIFICATION RULES (critical — read before writing relationship_type):\n"
        "- Default: relationship_type = 'peer_competitor', relationship_confidence = 'inferred'\n"
        "  Use this when the entity is in the same competitive landscape but there is NO explicit deal.\n"
        "- Only use 'licensor' or 'licensee' if you can cite a specific licensing agreement (press release,\n"
        "  SEC filing, ClinicalTrials.gov record, or official announcement). Do NOT infer licensing from\n"
        "  market proximity alone.\n"
        "- Use 'confirmed' only for relationships stated explicitly in a primary source.\n"
        "- Use 'inferred' for logical deductions (same target/indication, overlapping geography).\n"
        "- Use 'suggested' for speculative associations that need human verification.\n"
        "- why_discovered: explain the specific search criteria that surfaced this entity\n"
        "  (e.g. 'IL-4Ra antibody in atopic dermatitis Phase 3 — same target and indication').\n\n"
        "DRUG DISAMBIGUATION — KNOWN ASSET TABLE (authoritative; do not override):\n"
        "These drug→target mappings are ground truth. If a source contradicts them, trust this table.\n"
        + "".join(
            f"  {drug}: target={info['target']}, stage={info['stage']} — {info['note']}\n"
            for drug, info in KNOWN_DRUG_TARGETS.items()
        )
        + "\nIMPORTANT: AK104 (cadonilimab) targets PD-1/CTLA-4 — NOT PD-1/TIM-3. "
        "AK129 targets PD-1/TIM-3 and is a completely separate program. Never conflate them.\n\n"
        "JAK INHIBITOR CLASSIFICATION RULES:\n"
        "Always specify selectivity explicitly — do NOT write 'JAK1/JAK2' unless the drug is\n"
        "a confirmed dual JAK1/JAK2 inhibitor (e.g. baricitinib, ruxolitinib).\n"
        "  JAK1-selective  = upadacitinib, filgotinib, abrocitinib, SHR0302/ivarmacitinib\n"
        "  JAK1/JAK2 dual  = baricitinib, ruxolitinib\n"
        "  JAK1/2/3 pan    = tofacitinib\n"
        "If uncertain about selectivity profile, set target = 'JAK1-selective (unconfirmed)' and\n"
        "relationship_confidence = 'suggested' — never assume JAK1/JAK2 dual by default.\n\n"
        'IF none found: {"new_entities": []}'
    )

    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=1500,
            system=DISCOVERY_SYSTEM,
            messages=[{"role": "user", "content": prompt}]
        )
        _acc_tokens(resp)
        text = resp.content[0].text.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:].strip()
        data = json.loads(text)
    except Exception as e:
        log(f"  Discovery error: {e}", indent=1)
        return 0

    new_entities = data.get("new_entities", [])
    if not new_entities:
        log("  No new entities found", indent=1)
        return 0

    # ── Post-processing: validate drug targets against known-drug table ───────
    for ent in new_entities:
        drug = (ent.get("drug_name") or "").strip()
        if drug and drug in KNOWN_DRUG_TARGETS:
            known = KNOWN_DRUG_TARGETS[drug]
            llm_target = (ent.get("target") or "").strip()
            if llm_target != known["target"]:
                log(f"  ⚠ Drug target mismatch for {drug}: LLM said '{llm_target}', "
                    f"overriding with authoritative '{known['target']}'", indent=1)
                ent["target"] = known["target"]
            llm_stage = (ent.get("stage") or "").strip()
            if llm_stage != known["stage"]:
                log(f"  ⚠ Drug stage mismatch for {drug}: LLM said '{llm_stage}', "
                    f"overriding with authoritative '{known['stage']}'", indent=1)
                ent["stage"] = known["stage"]

    queued = 0
    for ent in new_entities:
        co_name          = ent.get("company_name", "")
        drug_name        = ent.get("drug_name")
        confidence       = int(ent.get("confidence", 60))
        relevance_score  = int(ent.get("relevance_score", 5))
        relevance_rat    = ent.get("relevance_rationale", "")
        competition_lay  = ent.get("competition_layer") or None
        overlap          = ent.get("overlap", "Watch")
        entity_type      = ent.get("entity_type", "company")
        reason           = ent.get("reason", "")
        suggested_dest   = ent.get("suggested_dest", "new_company")
        partner_co       = ent.get("partner_co") or None
        acquired_by      = ent.get("acquired_by") or None
        # Relationship classification (v10 fields — require migration v10)
        relationship_type = ent.get("relationship_type") or "peer_competitor"
        relationship_conf = ent.get("relationship_confidence") or "inferred"
        why_discovered    = ent.get("why_discovered") or None
        # Enforce: never write licensor/licensee without explicit evidence
        if relationship_type in ("licensor", "licensee") and relationship_conf != "confirmed":
            log(f"    ⚠ relationship_type={relationship_type} requires confirmed evidence — downgrading to peer_competitor/inferred", indent=2)
            relationship_type = "peer_competitor"
            relationship_conf = "inferred"

        # Normalize entity_type to discovery_queue CHECK constraint values
        _valid_etypes = {"company","molecule","trial","deal","catalyst","article","evidence_item","poster"}
        if entity_type not in _valid_etypes:
            entity_type = "company"

        log(
            f"  → {co_name}/{drug_name} "
            f"(conf={confidence} rel={relevance_score} layer={competition_lay}): {reason}",
            indent=1
        )

        if confidence < 70:
            log(f"    ↷ Low confidence ({confidence}) — skip", indent=2)
            continue

        if relevance_score < 5:
            log(f"    ↷ Low relevance ({relevance_score}) — auto-archive", indent=2)
            if not dry_run:
                # Still record it so we have a history, but mark archived immediately
                _dq_archived = {
                    "company_name":           co_name,
                    "company_id_suggested":   re.sub(r'[^a-z0-9]', '', co_name.lower())[:20],
                    "drug_name":              drug_name,
                    "target":                 ent.get("target", ""),
                    "stage":                  ent.get("stage", "Preclinical"),
                    "modality":               ent.get("modality") or None,
                    "route":                  ent.get("route") or None,
                    "entity_type":            entity_type,
                    "partner_co":             partner_co,
                    "acquired_by":            acquired_by,
                    "area_id":                area_id,
                    "overlap":                overlap,
                    "competition_layer":      competition_lay,
                    "confidence_score":       confidence,
                    "relevance_score":        relevance_score,
                    "relevance_rationale":    relevance_rat,
                    "reason":                 reason,
                    "suggested_dest":         suggested_dest,
                    "discovered_by":          "step1_discovery",
                    "discovery_run_id":       run_id,
                    "status":                 "archived",
                    "relationship_type":      relationship_type,
                    "relationship_confidence": relationship_conf,
                    "why_discovered":         why_discovered,
                }
                ok = sb_post("discovery_queue", _dq_archived)
                if not ok:
                    # Fallback: retry without v10 columns (migration not yet applied)
                    _dq_archived.pop("relationship_type", None)
                    _dq_archived.pop("relationship_confidence", None)
                    _dq_archived.pop("why_discovered", None)
                    sb_post("discovery_queue", _dq_archived)
            continue

        # Check if this entity is already in the queue (pending or approved) to avoid duplicates
        co_id_suggested = re.sub(r'[^a-z0-9]', '', co_name.lower())[:20]

        # Check if already a first-class entity in the database
        already_exists = bool(resolve_company_id(co_name, company_map))
        if already_exists:
            existing_area = sb_get("company_areas", {
                "company_id": f"eq.{resolve_company_id(co_name, company_map)}",
                "area_id":    f"eq.{area_id}",
                "select":     "company_id"
            })
            if existing_area:
                log(f"    ↷ Already in DB as {resolve_company_id(co_name, company_map)} — skip queue", indent=2)
                continue

        # Check for duplicate pending entry in discovery_queue
        dq_existing = sb_get("discovery_queue", {
            "company_id_suggested": f"eq.{co_id_suggested}",
            "area_id":              f"eq.{area_id}",
            "status":               "in.(pending,approved)",
            "select":               "id"
        })
        if dq_existing:
            log(f"    ↷ Already in discovery_queue (pending/approved) — skip", indent=2)
            continue

        if dry_run:
            log(f"    [DRY RUN] Would queue: {co_name} rel={relevance_score} layer={competition_lay}", indent=2)
            queued += 1
            continue

        # Determine queue status based on confidence + relevance
        # ≥90 confidence → auto-approve (bypass queue — high-signal, skip manual review)
        # 9-10 relevance → priority pending (needs human review but flagged urgent)
        # 7-8  → standard pending
        # 5-6  → watch
        AUTO_APPROVE_THRESHOLD = 90
        _now_iso = datetime.datetime.utcnow().isoformat() + "Z"
        if confidence >= AUTO_APPROVE_THRESHOLD:
            queue_status  = "approved"
            _reviewed_by  = "auto"
            _reviewed_at  = _now_iso
            log(f"    ⚡ conf={confidence} ≥ {AUTO_APPROVE_THRESHOLD} → AUTO-APPROVED", indent=2)
        else:
            queue_status  = "pending"
            _reviewed_by  = None
            _reviewed_at  = None

        _dq_pending = {
            "company_name":            co_name,
            "company_id_suggested":    co_id_suggested,
            "drug_name":               drug_name,
            "target":                  ent.get("target", ""),
            "stage":                   ent.get("stage", "Preclinical"),
            "modality":                ent.get("modality") or None,
            "route":                   ent.get("route") or None,
            "entity_type":             entity_type,
            "partner_co":              partner_co,
            "acquired_by":             acquired_by,
            "area_id":                 area_id,
            "overlap":                 overlap,
            "competition_layer":       competition_lay,
            "confidence_score":        confidence,
            "relevance_score":         relevance_score,
            "relevance_rationale":     relevance_rat,
            "reason":                  reason,
            "suggested_dest":          suggested_dest,
            "discovered_by":           "step1_discovery",
            "discovery_run_id":        run_id,
            "status":                  queue_status,
            "reviewed_by":             _reviewed_by,
            "reviewed_at":             _reviewed_at,
            "relationship_type":       relationship_type,
            "relationship_confidence": relationship_conf,
            "why_discovered":          why_discovered,
        }
        # Strip None fields to avoid Supabase rejecting nulls for non-nullable columns
        _dq_pending = {k: v for k, v in _dq_pending.items() if v is not None}
        ok = sb_post("discovery_queue", _dq_pending)
        if not ok:
            # Fallback: retry without v10 columns (migration not yet applied)
            _dq_pending.pop("relationship_type", None)
            _dq_pending.pop("relationship_confidence", None)
            _dq_pending.pop("why_discovered", None)
            ok = sb_post("discovery_queue", _dq_pending)

        priority_flag = " ⚡ PRIORITY" if relevance_score >= 9 else ""
        status_flag   = " [AUTO-APPROVED]" if queue_status == "approved" else ""
        log(
            f"    → Queued in discovery_queue: {co_name} "
            f"(rel={relevance_score} conf={confidence} layer={competition_lay}){priority_flag}{status_flag}",
            indent=2
        )
        queued += 1

    if queued:
        log(f"  Step 1 complete: {queued} candidates added to discovery_queue (pending review)", indent=1)
    else:
        log(f"  Step 1 complete: no new candidates queued", indent=1)

    return queued
