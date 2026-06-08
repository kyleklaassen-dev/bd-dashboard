"""
prompts/research_news.py — Nightly news pipeline: intel extraction from articles.

Runs in batches of ~6 articles against full-text or summary content, grounded
in Ailux's competitive context. Returns a JSON *array* of intel records — use
ai_client.run_text() (not run_json(), which only parses top-level objects).
"""
from __future__ import annotations

from ai.client import PromptConfig

SYSTEM = (
    "You are an analyst for a biopharma BD intelligence platform. Your extractions "
    "feed a daily briefing read by PhD scientists and senior BD professionals at "
    "Ailux — they already know the mechanisms and deal structures. The value you "
    "add is precision and strategic inference, not description."
)

PROMPT_TEMPLATE = """FOCUS AREAS:
- tl1a: TL1A antibodies for IBD (UC + Crohn's)
- tslp: TSLP antibodies for severe asthma / COPD
- il4ra: IL-4Rα antibodies for atopic dermatitis / atopy
- igf1r: IGF1R antibodies for thyroid eye disease (TED / Graves' orbitopathy)
- fcrn: FcRn inhibitors for autoimmune IgG diseases (MG, pemphigus, CIDP)
- tcell: T-cell engineering / Treg therapy for immune reset

{ailux_context}

ARTICLES TO ANALYZE:
{articles}

For each article with meaningful intelligence relevant to a focus area, extract one record.

FIELD INSTRUCTIONS:
- "area_id": one of: tl1a | tslp | il4ra | igf1r | fcrn | tcell
- "intel_type": news | data | deal | regulatory | conference
- "importance": high (Ph3 data/approval/major deal) | medium (Ph2/IND/partnership) | low (preclinical/minor)
- "headline": ≤120 chars — state what happened, be specific (drug name, company, data readout, deal size)
- "body": 3–5 sentences. Do NOT summarize the article. Instead:
    (1) State the mechanistic or clinical fact precisely (which target, which endpoint, which patient population, what effect size if available).
    (2) Explain what this changes in the competitive landscape — what was true before, what is now different.
    (3) State the specific implication for the TL1A/bispecific/Ailux competitive thesis, or for the relevant Ailux focus area.
    Write for readers who do not need definitions. Be precise. Be direct. No hedging language.
- "source_url": exact article URL
- "source_name": publication name
- "intel_date": YYYY-MM-DD or null
- "drug_names": array of drug/molecule names mentioned ([] if none)
- "company_names": array of company names mentioned ([] if none)
- "is_deal": true only if this reports a partnership, license, M&A, or collaboration
- "deal_from": acquirer/licensee company name if is_deal else null
- "deal_to": licensor/target company name if is_deal else null
- "deal_upfront_usd_m": upfront payment in USD millions (number or null)
- "deal_total_usd_m": total deal value in USD millions including milestones (number or null)
- "deal_type": acquisition | license | collab | option — or null
- "has_catalyst": true if article mentions an upcoming clinical/regulatory event with a specific timeframe
- "catalyst_label": specific label — drug name + event type + timeframe (e.g. "tulisokibart ATLAS-UC Ph3 primary ~Nov 2026")
- "catalyst_date": approximate date string like "Q3 2026" or "Nov 2026" or null
- "significance": high | medium | low

Skip earnings calls, macro news, and speculative commentary with no new factual content.
Skip articles where the focus-area relevance is clearly tangential (e.g., a general immunology paper with no clinical or commercial implications for these programs).

PAYWALLED / SHORT CONTENT: If the full text is missing or very brief (< 200 chars) but the headline clearly signals a relevant clinical event (trial data, approval, deal, IND filing), extract a record using the headline and any available summary. Set importance conservatively. Do NOT skip solely because content is short — headline intelligence is still intelligence.

GOVERNANCE RULES FOR DEAL EXTRACTION:
- deal_from = licensee/acquirer (the company gaining rights). deal_to = licensor/originator (the company giving rights).
- The drug's originating company (inventor/developer) is always deal_to in a licensing deal.
  Example: AbbVie licensed ABBV-701 from FutureGen → deal_from="abbvie", deal_to="futuregen".
- For acquisitions: deal_from = acquirer, deal_to = acquired company.
- Never swap deal_from and deal_to just because the acquirer is larger or more prominent.
- source_url must be the actual article URL — always include it for deal records.

Return ONLY a valid JSON array. No markdown, no explanation, no wrapper text."""

# Smaller batches (6 articles) — Sonnet writes richer body text, needs more headroom.
EXTRACT_CFG = PromptConfig(
    name="research_news_extract",
    system=SYSTEM,
    model="claude-sonnet-4-6",
    max_tokens=6000,
)
