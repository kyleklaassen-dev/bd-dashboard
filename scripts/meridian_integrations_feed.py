#!/usr/bin/env python3
"""
meridian_integrations_feed.py — read-only data feed for the Meridian Issue.

PURPOSE
-------
Surfaces the Round 11–17 API-integration data (genetics, patents, regulatory
designations, financing/SEC events, KOL metrics) and the synthesized
`strategic_insights` layer into prompt-ready blocks for write_meridian.py.

DESIGN (per docs/MERIDIAN_ISSUE_V2_PLAN.md)
-------------------------------------------
- STANDALONE + READ-ONLY. This module performs zero writes and makes zero edits
  to write_meridian.py. The writer integrates it later with a one-line import,
  once parallel-session file/table ownership is settled. Until then this can be
  run on its own (`python3 scripts/meridian_integrations_feed.py`) to preview
  exactly what would be injected.
- APERTURE BY SCOPE. `strategic_insights` is filtered to the day's in-scope
  entities via its `entity_refs` JSONB (client-side intersection — the table is
  small, ~hundreds of rows, and is actively written by another session so we do
  not assume a stable insight_type set). Raw integration tables are fetched in
  full ONLY for in-scope entities. Out-of-scope rows are never loaded.
- PROVENANCE. Every emitted fact carries its DB source_url so the writer can
  hyperlink it. Nothing is fabricated; if a table returns nothing for the scope,
  the block says so rather than inventing.

VERIFIED SCHEMAS (probed 2026-06-07)
------------------------------------
strategic_insights : insight_type, title, detail, entity_refs{drugs[],companies[],
                     targets[],indications[]}, metric, source_tables[], confidence,
                     created_at
target_disease_assoc: target_id, symbol, indication_id, indication_name,
                     overall_score, genetic_association_score, literature_score,
                     source_url            (TL1A->IBD genetic = 0.892)
company_patents    : company_id, matched_drug_id, matched_target, patent_title,
                     assignee_org, expiry_estimate, family_country_codes, source_url
regulatory_designations: drug_id, designation_type, indication, granting_authority,
                     granted_date, source
company_events     : company_id, event_type, event_subtype, event_summary,
                     filing_date, source_url   (event_type='financing' = runway)
kol_metrics        : kol_name, h_index, citation_count, paper_count, source_url
"""

import os
import json
import urllib.parse
import urllib.request

SB_URL = "https://tghntyofptvfhmtchwcv.supabase.co/rest/v1"
_WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _key():
    """Read the Supabase service key from the workspace root (read-only use)."""
    # env override first (matches how write_meridian.py runs in CI)
    for env in ("SUPABASE_SERVICE_KEY", "SUPABASE_SERVICE_ROLE_KEY"):
        if os.environ.get(env):
            return os.environ[env].strip()
    path = os.path.join(_WORKSPACE, ".supabase_service_key")
    with open(path) as f:
        return f.read().strip()


def _get(table, params, timeout=25):
    """GET rows from a PostgREST table. Returns a list (empty on error)."""
    key = _key()
    qs = urllib.parse.urlencode(params, safe="(),.*:")
    url = f"{SB_URL}/{table}?{qs}"
    req = urllib.request.Request(url, headers={
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode())
            return data if isinstance(data, list) else []
    except Exception as e:  # read-only; degrade gracefully, never crash the issue
        print(f"  [feed] warn: {table} fetch failed: {e}")
        return []


# ── Scope ────────────────────────────────────────────────────────────────────
def _norm_target(s):
    """'IL-23p19' -> 'il23p19', 'TL1A' -> 'tl1a' (matches target_disease_assoc.target_id)."""
    return "".join(ch for ch in s.lower() if ch.isalnum())


def _targets_from_string(tgt, into):
    """Split a bispecific/combination target string into normalized tokens."""
    for tok in (tgt or "").replace("×", "x").replace("/", "x").replace("+", "x").split("x"):
        tok = _norm_target(tok)
        if tok:
            into.add(tok)


def expand_scope(seed, company_drug_cap=40):
    """
    Given a seed {drugs:[ids], companies:[ids]}, resolve the full typed scope:
      drugs      → their owning companies + molecular targets
      companies  → their BD-relevant drugs (overlap in Direct/Adjacent/Same-Space)
                   and the targets of those drugs

    This is the typed scope extractor the plan's Phase 1 requires (replacing the
    company-only _extract_company_ids_from_plan in write_meridian.py). The
    company→drug expansion is bounded to overlap-relevant assets so diversified
    pharma (e.g. AbbVie) does not flood the genetics block with off-mechanism
    targets.
    """
    drugs = set(seed.get("drugs") or [])
    companies = set(seed.get("companies") or [])
    targets = {_norm_target(t) for t in (seed.get("targets") or []) if t}
    indications = set(seed.get("indications") or [])

    # drugs → companies + targets
    if drugs:
        for r in _get("drugs", {
            "select": "id,company_id,target",
            "id": f"in.({','.join(sorted(drugs))})",
        }):
            if r.get("company_id"):
                companies.add(r["company_id"])
            _targets_from_string(r.get("target"), targets)

    # companies → BD-relevant drugs + their targets (bounded by overlap tier)
    if companies:
        for r in _get("drugs", {
            "select": "id,company_id,target,overlap",
            "company_id": f"in.({','.join(sorted(companies))})",
            "overlap": "in.(Direct,Adjacent,Same-Space)",
            "limit": str(company_drug_cap),
        }):
            if r.get("id"):
                drugs.add(r["id"])
            _targets_from_string(r.get("target"), targets)

    return {
        "drugs": sorted(drugs),
        "companies": sorted(companies),
        "targets": sorted(targets),
        "indications": sorted(indications),
    }


def extract_scope_from_intel(intel, plan=None):
    """
    Derive a seed scope from the day's intel rows (+ optional editorial plan),
    then expand it. This is what write_meridian.py calls.

    Intel rows do NOT carry FK columns; entities are resolved by
    enrich_intel_with_drug_context (keyword match → _matched_drug_ids /
    _matched_company_ids) and by the intel `areas` tags (e.g. 'tl1a', 'ibd').
    Area ids double as both target seeds (tl1a → target_disease_assoc.target_id)
    and indication seeds; non-matching ones are harmless no-ops downstream.
    """
    seed = {"drugs": set(), "companies": set(), "targets": set(), "indications": set()}
    for it in intel or []:
        seed["drugs"].update(it.get("_matched_drug_ids") or [])
        seed["companies"].update(it.get("_matched_company_ids") or [])
        # legacy / alternative field names, if ever present
        if it.get("primary_company_id"):
            seed["companies"].add(it["primary_company_id"])
        if it.get("drug_id"):
            seed["drugs"].add(it["drug_id"])
        for a in it.get("areas") or []:
            seed["targets"].add(a)
            seed["indications"].add(a)
    if plan:
        for d in plan.get("drug_ids", []):
            seed["drugs"].add(d)
        for a in plan.get("area_tags", []):
            seed["targets"].add(a)
            seed["indications"].add(a)
    return expand_scope({k: list(v) for k, v in seed.items()})


# ── Synthesized insight layer ────────────────────────────────────────────────
# Insight types that are internal ops/governance signals, not reader-facing
# intelligence — excluded from the Issue feed (they belong on Kyle's QA surface).
_INTERNAL_INSIGHT_TYPES = {"data_integrity"}


def fetch_strategic_insights(scope, cap=400, max_emit=18):
    """
    Fetch the strategic_insights layer and keep only rows whose entity_refs
    intersect the scope (drugs / companies / targets). Client-side filter — the
    table is small and its insight_type set is volatile. Internal/governance
    insight types are dropped; reader-facing ones are returned newest first,
    with confirmed-confidence rows surfaced ahead of inferred.
    """
    rows = _get("strategic_insights", {
        "select": "insight_type,title,detail,entity_refs,metric,source_tables,confidence,created_at",
        "order": "created_at.desc",
        "limit": str(cap),
    })
    sdr, sco, stg = set(scope["drugs"]), set(scope["companies"]), set(scope["targets"])
    hits = []
    for r in rows:
        if r.get("insight_type") in _INTERNAL_INSIGHT_TYPES:
            continue
        refs = r.get("entity_refs") or {}
        rd = set(refs.get("drugs") or [])
        rc = set(refs.get("companies") or [])
        rt = {_norm_target(t) for t in (refs.get("targets") or [])}
        if (rd & sdr) or (rc & sco) or (rt & stg):
            hits.append(r)
    # confirmed first, then inferred/supported — preserves recency within each tier
    hits.sort(key=lambda r: 0 if r.get("confidence") == "confirmed" else 1)
    return hits[:max_emit]


# ── Raw integration drill-down (in-scope only) ───────────────────────────────
def fetch_integration_drilldown(scope):
    """Pull raw integration rows for in-scope entities only. Returns a dict."""
    dd = {"genetics": [], "patents": [], "regulatory": [], "financing": [], "kol": []}

    # 1. Genetics — target-disease association for in-scope targets, IBD-relevant
    if scope["targets"]:
        dd["genetics"] = _get("target_disease_assoc", {
            "select": "target_id,symbol,indication_id,indication_name,genetic_association_score,overall_score,source_url",
            "target_id": f"in.({','.join(scope['targets'])})",
            "genetic_association_score": "not.is.null",
            "order": "genetic_association_score.desc",
            "limit": "12",
        })

    # 2. Patents — by owning company OR matched drug (FTO relevance)
    if scope["companies"]:
        dd["patents"] = _get("company_patents", {
            "select": "company_id,matched_drug_id,matched_target,patent_title,assignee_org,expiry_estimate,family_country_codes,source_url",
            "company_id": f"in.({','.join(scope['companies'])})",
            "limit": "15",
        })

    # 3. Regulatory designations — by in-scope drug
    if scope["drugs"]:
        dd["regulatory"] = _get("regulatory_designations", {
            "select": "drug_id,designation_type,indication,granting_authority,granted_date,source",
            "drug_id": f"in.({','.join(scope['drugs'])})",
            "limit": "20",
        })

    # 4. Financing / runway signals — SEC company_events for in-scope companies
    if scope["companies"]:
        dd["financing"] = _get("company_events", {
            "select": "company_id,event_type,event_subtype,event_summary,filing_date,source_url",
            "company_id": f"in.({','.join(scope['companies'])})",
            "event_type": "eq.financing",
            "order": "filing_date.desc",
            "limit": "10",
        })

    # 5. KOL context — top influencers (linking to assets is via entity_edges;
    #    until that join is wired, surface the top-cited KOLs as area context).
    dd["kol"] = _get("kol_metrics", {
        "select": "kol_name,h_index,citation_count,paper_count,source_url",
        "order": "h_index.desc",
        "limit": "6",
    })
    return dd


# ── Prompt-ready block builders ──────────────────────────────────────────────
def build_insights_block(insights):
    if not insights:
        return "STRATEGIC INSIGHTS (synthesized, in-scope): none for today's entities."
    lines = ["STRATEGIC INSIGHTS (synthesized layer — in-scope; cite the source_tables, mark as inference unless confidence=confirmed):"]
    for r in insights:
        m = f" [metric={r['metric']}]" if r.get("metric") is not None else ""
        conf = r.get("confidence", "inferred")
        lines.append(f"• ({r['insight_type']}, {conf}){m} {r['title']}")
        if r.get("detail"):
            detail = " ".join(r["detail"].split())  # collapse whitespace
            if len(detail) > 360:
                detail = detail[:357].rstrip() + "…"
            lines.append(f"    {detail}")
    return "\n".join(lines)


def build_integration_block(dd):
    out = []

    g = dd.get("genetics") or []
    if g:
        out.append("GENETIC VALIDATION (Open Targets — genetic_association_score 0–1; higher = stronger human-genetics support):")
        for r in g:
            out.append(f"• {r['symbol']} ({r['target_id']}) → {r['indication_name']}: "
                       f"genetic={round(r['genetic_association_score'],3)} "
                       f"(overall={round(r['overall_score'],3)}) — {r['source_url']}")

    reg = dd.get("regulatory") or []
    if reg:
        out.append("\nREGULATORY DESIGNATIONS (in-scope drugs):")
        for r in reg:
            out.append(f"• {r['drug_id']}: {r['designation_type']} — {r['indication']} "
                       f"({r['granting_authority']}, {r.get('granted_date','?')}) [{r.get('source','')}]")

    fin = dd.get("financing") or []
    if fin:
        out.append("\nFINANCING / RUNWAY SIGNALS (SEC 8-K event bodies — counterparty health):")
        for r in fin:
            summ = (r.get("event_summary") or "").strip().replace("\n", " ")[:180]
            out.append(f"• {r['company_id']} ({r['filing_date']}, {r.get('event_subtype','')}): {summ} — {r['source_url']}")

    pat = dd.get("patents") or []
    if pat:
        out.append("\nPATENT / FTO (in-scope companies — relevant to deal diligence):")
        for r in pat:
            fam = ",".join(r.get("family_country_codes") or [])
            tag = r.get("matched_target") or r.get("matched_drug_id") or "—"
            out.append(f"• {r['company_id']} [{tag}] exp~{r.get('expiry_estimate','?')} ({fam}): "
                       f"{(r.get('patent_title') or '')[:70]} — {r['source_url']}")

    kol = dd.get("kol") or []
    if kol:
        out.append("\nKOL CONTEXT (top influencers by h-index — area context, not asset-linked yet):")
        for r in kol:
            out.append(f"• {r['kol_name']}: h-index {r['h_index']}, {r['citation_count']} citations, "
                       f"{r['paper_count']} papers — {r['source_url']}")

    return "\n".join(out) if out else "INTEGRATION DRILL-DOWN: no in-scope rows in genetics/patents/regulatory/financing."


def render_feed(scope):
    """Convenience: returns (insights_block, integration_block) for a scope."""
    insights = fetch_strategic_insights(scope)
    dd = fetch_integration_drilldown(scope)
    return build_insights_block(insights), build_integration_block(dd)


if __name__ == "__main__":
    # Demo on a real IBD / TL1A scope (assets that exist in the DB today).
    seed = {
        "drugs": ["abs-101", "duvakitug", "tulisokibart"],
        "companies": ["absci", "abbvie", "merck", "takeda"],
        "indications": ["uc", "cd", "ibd"],
    }
    scope = expand_scope(seed)
    print("=" * 78)
    print("RESOLVED SCOPE:", json.dumps(scope))
    print("=" * 78)
    ins_block, int_block = render_feed(scope)
    print("\n" + ins_block)
    print("\n" + "-" * 78 + "\n")
    print(int_block)
