#!/usr/bin/env python3
"""
Step 6 — Deal Intelligence (§3 company_enrichment split).
=========================================================
Extracted verbatim from company_enrichment.py. Detects deal announcements in recent
intel not yet in the deals table and back-fills deal fields. _deal_signature dedupes
on normalized headline. Self-contained leaf.
"""

import re
import datetime

from meridian.enrichment.company.common import TODAY, log, sb_post


# ══════════════════════════════════════════════════════════════════════════
# STEP 6 — DEAL INTELLIGENCE
#
# IF recent intel contains deal announcement not yet in deals table:
#   → Create deal record
#   → Connect to entity, company
# ══════════════════════════════════════════════════════════════════════════

def _deal_signature(headline: str) -> str:
    """Normalised fingerprint for deal deduplication.

    Strips all non-alphanumeric characters, lowercases, and returns the first
    100 characters.  Using 100 normalised chars (vs the old raw[:50]) removes
    punctuation/spacing variance that caused false positives and catches more
    near-duplicate headlines.
    """
    return re.sub(r"[^a-z0-9]", "", headline.lower())[:100]


def step6_deal_intelligence(company_id: str, area_id: str, ctx: dict,
                             company_map: dict, dry_run: bool = False,
                             resolver=None) -> int:
    """Log new deals found in recent intel. Returns count created.

    Args:
      resolver: a pre-instantiated DrugIdentityResolver (passed from run_intelligence_pipeline).
                Pass None to skip canonical identity stamping on deals.
    """
    existing_signatures = {
        _deal_signature(d.get("headline") or "")
        for d in ctx.get("deals", [])
    }
    new_deals = 0
    # RULE: "Related News" = any notable company event, not just formal BD deals.
    # Keywords expanded to capture financing rounds, press releases, regulatory news, and pipeline milestones.
    # Financing rounds (Series A/B/C, IPO, SPAC) are critical competitive signals and must be captured.
    deal_kws   = {
        # Formal BD
        "license","acqui","partner","collaborat","deal","agreement","merger",
        # Financing
        "series a","series b","series c","series d","financing","raises","raised",
        "ipo","spac","public offering","oversubscribed","valuation",
        "million","billion","$",
        # Company milestones
        "invest","phase","readout","data","approval","clearance","fda","ema","cde",
        "breakthrough","fast track","orphan","pdufa",
        # Press release markers
        "announces","announced","today announced","reports","closes","completes",
    }

    # Build a quick lookup: drug name → canonical_drug_id for this company's drugs.
    # Resolver pre-instantiated by caller — no per-company Supabase round-trip here.
    drug_canonical_map: dict[str, str] = {}
    if resolver is not None and not dry_run:
        for drug in ctx.get("drugs", []):
            drug_name = drug.get("name") or drug.get("id", "")
            if drug_name:
                try:
                    canon_id, _, _ = resolver.resolve(
                        drug_name, source="company_enrichment",
                        drug_class=drug.get("drug_class"),
                        mechanism=drug.get("mechanism"),
                        target=drug.get("target"),
                    )
                    drug_canonical_map[drug_name.lower()] = canon_id
                except Exception as inner_exc:
                    try:
                        resolver.log_resolver_error(
                            drug_name=drug_name, source="company_enrichment",
                            error=inner_exc, source_table="drugs",
                            source_row_id=drug.get("id"),
                        )
                    except Exception:
                        pass

    for item in ctx.get("recent_intel", []):
        headline = (item.get("headline") or "").lower()
        if not any(kw in headline for kw in deal_kws):
            continue
        if _deal_signature(headline) in existing_signatures:
            continue

        deal_date = item.get("intel_date") or TODAY
        try:
            deal_date_label = datetime.datetime.strptime(deal_date[:7], "%Y-%m").strftime("%b %Y")
        except Exception:
            deal_date_label = deal_date[:7]

        # Attempt to identify which drug this deal is about (if any)
        headline_lc = (item.get("headline") or "").lower()
        deal_canonical_drug_id = None
        for drug_name_lc, canon_id in drug_canonical_map.items():
            if drug_name_lc in headline_lc:
                deal_canonical_drug_id = canon_id
                break

        # Infer deal_type from headline content — displayed as badge in "Related News" panel
        # RULE: financing rounds, press releases, and clinical milestones all belong in Related News
        hl = (item.get("headline") or "").lower()
        if any(w in hl for w in ["series","financing","raises","raised","ipo","offering","valuation","oversubscribed"]):
            inferred_type = "financing"
        elif any(w in hl for w in ["acqui","merger","acquisition"]):
            inferred_type = "acquisition"
        elif any(w in hl for w in ["partner","collaborat","co-develop"]):
            inferred_type = "partnership"
        elif any(w in hl for w in ["license","licens"]):
            inferred_type = "licensing"
        elif any(w in hl for w in ["approval","approved","clearance","pdufa","fda","ema","cde"]):
            inferred_type = "regulatory"
        elif any(w in hl for w in ["readout","data","phase","trial","endpoint"]):
            inferred_type = "clinical"
        else:
            inferred_type = "news"

        deal_rec = {
            "deal_date":         deal_date,
            "deal_date_label":   deal_date_label,
            "from_company":      ctx["company"].get("name", company_id),
            "to_company":        "",
            "company_id":        company_id,
            "area_id":           area_id,
            "deal_type":         inferred_type,
            "headline":          (item.get("headline") or "")[:200],
            "detail":            (item.get("body") or "")[:1000],
            "source_url":        item.get("source_url", ""),
            "ailux_signal":      "",
            "canonical_drug_id": deal_canonical_drug_id,
        }
        if dry_run:
            log(f"  [DRY RUN] Deal: {deal_rec['headline'][:60]}", indent=2)
        else:
            result = sb_post("deals", deal_rec)
            if result:
                log(f"  + Deal: {deal_rec['headline'][:60]}", indent=2)
                new_deals += 1

    return new_deals
