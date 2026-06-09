"""
The Meridian — explainer dashboard.

Landing page offers two views:
  • Github Workflows — one button per weekend GitHub Actions workflow, each
    leading to a page that shows, in order, which files the pipeline's
    entrypoint touches (including which steps run in parallel) and a
    plain-language sentence describing what each file does.
  • State Graphs — one button per LangGraph StateGraph pipeline in scripts/pipeline/.

Run with:
    streamlit run dashboard/app.py
"""
import streamlit as st

from pipelines import PIPELINE_GROUPS, PIPELINES
from state_graphs import STATE_GRAPHS
from state_graphs._topology import build_app, topology_dot

st.set_page_config(
    page_title="The Meridian",
    page_icon="🧬",
    layout="centered",
)

if "view" not in st.session_state:
    st.session_state.view = "landing"


def go_to(view_key: str) -> None:
    st.session_state.view = view_key


CARD_STYLES = """
<style>
button[kind="primary"] {
    min-height: 160px;
    white-space: pre-wrap;
    line-height: 1.5;
    background-color: #e4d9f7;
    border: 1px solid #b49ce8;
    color: #3a2c5c;
}
button[kind="primary"]:hover {
    background-color: #d6c5f3;
    border-color: #9d7fdc;
    color: #2c2047;
}
button[kind="primary"] strong {
    font-size: 1.3rem;
}

/* Teal accent — scoped to containers marked with key="teal_zone" so it
   overrides the purple card styling above without touching other buttons
   (e.g. "← Back", which is also a default/primary-less button elsewhere). */
.st-key-teal_zone button[kind="primary"] {
    background-color: #cfe8ff;
    border: 1px solid #6cb6ff;
    color: #3a2c5c;
}
.st-key-teal_zone button[kind="primary"]:hover {
    background-color: #a9d6ff;
    border-color: #3a9bff;
    color: #2c2047;
}

/* Green accent — scoped to key="model_zone" for the Mental Model card. */
.st-key-model_zone button[kind="primary"] {
    background-color: #d9f7e4;
    border: 1px solid #7fce9d;
    color: #2c4a37;
}
.st-key-model_zone button[kind="primary"]:hover {
    background-color: #bff0d2;
    border-color: #4fb87a;
    color: #1e3a2a;
}
</style>
"""


def inject_card_styles() -> None:
    st.markdown(CARD_STYLES, unsafe_allow_html=True)


def render_landing() -> None:
    inject_card_styles()

    st.title("🧬 The Meridian")
    st.caption("Pick a view to explore.")
    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.button(
            "**Github Workflows**",
            key="btn_github_workflows",
            type="primary",
            width="stretch",
            on_click=go_to,
            args=("home",),
        )
    with col2:
        with st.container(key="teal_zone"):
            st.button(
                "**State Graphs**",
                key="btn_state_graphs",
                type="primary",
                width="stretch",
                on_click=go_to,
                args=("state_graphs",),
            )

    with st.container(key="model_zone"):
        st.button(
            "**Mental Model**",
            key="btn_mental_model",
            type="primary",
            width="stretch",
            on_click=go_to,
            args=("mental_model",),
        )


# Mental Model stages, in the order data flows through the platform. Validate /
# Governance is last and stands on its own because it wraps every write rather
# than being a step in the chain. Each entry gets its own button on the Mental
# Model page and its own stub page (view key "mm::<key>").
MENTAL_MODEL_STAGES = [
    {
        "key": "ingest",
        "label": "1 · Ingest",
        "tagline": "getting facts in",
        "body": (
            "Pulling raw signal from the outside world, three ways: **automated feeds** "
            "(`sync/ct_gov_sync.py` for ClinicalTrials.gov, `intelligence/research.py` for "
            "nightly news, `signal_monitor.py`, abstracts, stock prices); **AI enrichment** "
            "(`enrichment/*` — Claude discovers and fills in pipelines, mechanisms, deals, "
            "profiles; `company_enrichment.py` is the flagship); and **manual intake** "
            "(`intake/*` — you feeding in a company, drug, or conversation transcript)."
        ),
    },
    {
        "key": "store",
        "label": "2 · Store",
        "tagline": "where it lives",
        "body": (
            "**Supabase Postgres** is the single source of truth (60+ tables: companies, "
            "drugs, trials, deals, partnerships, plus scoring and validation tables). "
            "`scripts/_db.py` is the thin access layer everything uses (get / upsert / "
            "patch / delete via REST); `migrations/v1_schema.sql` is the schema snapshot."
        ),
    },
    {
        "key": "score",
        "label": "3 · Score",
        "tagline": "facts into numbers & rankings",
        "body": (
            "`scripts/scoring/*` turns stored facts into metrics: **completeness / coverage** "
            "(`compute_coverage.py`, `rescore_completeness.py` — how well-covered each company "
            "is), **strategic ranking** (`compute_strategic_value.py`, `acquisition_scorer.py`, "
            "`compute_landscape_scores.py`), and **BD recommendations** (`bd_recommender.py` — "
            "who Ailux should consider for a deal)."
        ),
    },
    {
        "key": "interpret",
        "label": "4 · Interpret",
        "tagline": "facts into prose & strategy",
        "body": (
            "The LLM-analysis layer that reads the data and *writes intelligence*. "
            "`scripts/ai/client.py` is the one wrapper for all Claude calls (model choice, "
            "cost tracking, JSON parsing). On top of it sit the **narratives** "
            "(`intelligence/write_meridian.py` daily briefing, `narrative/*`) and the "
            "**reasoning over relationships** (`identity/*` dedup, `graph/*` edge materialization)."
        ),
    },
    {
        "key": "present",
        "label": "5 · Present",
        "tagline": "what you actually look at",
        "body": (
            "Two distinct UIs: **`index.html`** is the real production dashboard "
            "(~10k lines, served via GitHub Pages — browse companies, drugs, pipelines); "
            "**`pages/*.html`** are generated output documents (the daily Meridian briefing, "
            "atlas, strategic lens). This **Streamlit app** (`dashboard/app.py`) is a third, "
            "separate thing — it doesn't show BD data, it explains *the system itself*."
        ),
    },
    {
        "key": "validate",
        "label": "Validate · Governance",
        "tagline": "wraps every write",
        "body": (
            "Not a stage so much as a layer wrapping every write. `scripts/validation/*` "
            "(~15 scripts) enforces the rules in `CLAUDE.md` — every source URL is real "
            "(`source_verifier.py`), claims are actually supported (`content_verifier.py`), "
            "licensing attribution is correct, no fabricated data. Violations land in the "
            "`governance_violations` table."
        ),
    },
]

MENTAL_MODEL_STAGE_BY_KEY = {s["key"]: s for s in MENTAL_MODEL_STAGES}

# Flat, full-width, left-aligned buttons for the Mental Model stage list —
# scoped to key="mm_buttons" so the tall purple card styling doesn't apply.
MM_BUTTON_STYLES = """
<style>
.st-key-mm_buttons button {
    min-height: 56px;
    justify-content: flex-start;
    text-align: left;
    font-size: 1.05rem;
    border-radius: 8px;
}
</style>
"""


def render_mental_model() -> None:
    st.markdown(MM_BUTTON_STYLES, unsafe_allow_html=True)

    st.button("← Back", on_click=go_to, args=("landing",))

    st.title("🧠 Mental Model")
    st.caption(
        "The platform as the stages data flows through, top to bottom — with "
        "governance wrapping every write and the scheduler driving it all."
    )

    st.divider()

    with st.container(key="mm_buttons"):
        for stage in MENTAL_MODEL_STAGES:
            st.button(
                f"**{stage['label']}** — {stage['tagline']}",
                key=f"btn_mm_{stage['key']}",
                width="stretch",
                on_click=go_to,
                args=(f"mm::{stage['key']}",),
            )


# ── Ingest stage — full inventory ────────────────────────────────────────────
# Every point where external/new data enters the platform, grouped by HOW it
# gets in. Each source lists the file(s) that fetch it, when it runs, what's
# pulled, and the structure of what comes back ("structure" is a compact field
# list, not exhaustive). Verified against the codebase on the migration-baseline
# branch — file paths may shift as the scripts/pipeline/ migration lands.
INGEST_GROUPS = [
    {
        "label": "A · External APIs & feeds — machine pulls over the network",
        "blurb": (
            "Scheduled scripts hit public APIs and RSS feeds directly (no LLM), parse "
            "the response, and upsert it into Supabase. This is the bulk of automated ingest."
        ),
        "sources": [
            {
                "name": "ClinicalTrials.gov API v2",
                "system": "clinicaltrials.gov/api/v2 · REST/JSON",
                "files": "sync/ct_gov_sync.py · signal_monitor.py · intake/process_queue_item.py",
                "trigger": "Daily before enrichment + nightly 14-day update sweep",
                "pulls": (
                    "Trials by NCT id, or searched by drug name + indication. The deep "
                    "`protocolSection` JSON is flattened to the fields below."
                ),
                "structure": (
                    "id (NCT)            : str        # NCT05428163\n"
                    "trial_name          : str        # briefTitle\n"
                    "phase               : str        # Phase 1/2/3\n"
                    "status              : str        # Recruiting, Completed…\n"
                    "indication          : str        # conditions[] joined\n"
                    "n_enrollment        : int        # enrollmentInfo.count\n"
                    "primary_endpoint    : str        # primaryOutcomes[0]\n"
                    "secondary_endpoints : list[{measure, time_frame}]\n"
                    "arms                : list[{label, type, description}]\n"
                    "start_date          : date\n"
                    "primary_completion_date : date\n"
                    "sponsor             : str        # leadSponsor.name\n"
                    "source_url          : str        # /study/<NCT>"
                ),
            },
            {
                "name": "PubMed (NCBI E-utilities)",
                "system": "eutils.ncbi.nlm.nih.gov · esearch + efetch (XML)",
                "files": "abstracts/sources/pubmed.py · intelligence/research.py (PK/PD)",
                "trigger": "Weekly abstract sweep · nightly PK/PD queue",
                "pulls": (
                    "esearch returns PMIDs for a query; efetch returns full records. "
                    "Used for conference abstracts and PK/PD parameter extraction."
                ),
                "structure": (
                    "pmid       : str\n"
                    "doi        : str | null\n"
                    "title      : str   (≤400 chars)\n"
                    "authors    : str   (first 5, et al.)\n"
                    "journal    : str\n"
                    "pub_date   : str\n"
                    "abstract   : str   (≤3000 chars)\n"
                    "source_url : str   # pubmed.ncbi.nlm.nih.gov/<pmid>\n"
                    "source     : 'pubmed'"
                ),
            },
            {
                "name": "Europe PMC",
                "system": "ebi.ac.uk/europepmc/webservices/rest/search · JSON",
                "files": "abstracts/sources/europe_pmc.py · evidence/sources/europe_pmc.py",
                "trigger": "Weekly abstract sweep · weekend evidence collectors",
                "pulls": (
                    "Searched by drug name, or by disease + (epidemiology OR prevalence OR "
                    "incidence OR burden). Same publication shape as PubMed, plus a "
                    "conference-abstract flag."
                ),
                "structure": (
                    "pmid / doi / title / authors / journal / pub_date / abstract\n"
                    "is_conference : bool   # pubType contains 'conference'/'abstract'\n"
                    "source_url    : str    # europepmc.org/article/med/<pmid>\n"
                    "source        : 'europepmc'"
                ),
            },
            {
                "name": "News RSS feeds (3 tiers)",
                "system": "~20 feeds: Endpoints, FierceBiotech, company IR, FDA, trade press",
                "files": "intelligence/research.py · signal_monitor.py · fetch_homepage_news.py",
                "trigger": "Nightly news pipeline (~2–6 AM UTC) · quad-hourly signal scan",
                "pulls": (
                    "feedparser parses each feed. Tier 1 (trade press) and Tier 2 (company "
                    "IR) are always full-text-fetched; Tier 3 (secondary) only when title "
                    "keywords hit. Relevance keyed off targets (TL1A, TSLP…), clinical, and deal terms."
                ),
                "structure": (
                    "headline  : str\n"
                    "url       : str\n"
                    "summary   : str   (≤1200–2000 chars)\n"
                    "published : date\n"
                    "source    : str   # feed title\n"
                    "full_text : str   (≤4000 chars, if fetched)"
                ),
            },
            {
                "name": "Article full-text fetch",
                "system": "Arbitrary article URLs · HTTP GET/HEAD + BeautifulSoup",
                "files": "intelligence/research.py (fetch_full_text) · fetch_homepage_news.py (validate_url)",
                "trigger": "Inside the news pipeline, after RSS dedup",
                "pulls": (
                    "GETs the article body and extracts text from <article>/<main>; HEADs "
                    "the URL to classify accessibility before trusting it."
                ),
                "structure": (
                    "full_text         : str   (≤4000 chars)\n"
                    "http_status       : int\n"
                    "validation_status : 'valid' | 'limited' | 'invalid'\n"
                    "                    # 200/redirect=valid, 401/403=limited (paywall)"
                ),
            },
            {
                "name": "Yahoo Finance (stock prices)",
                "system": "yfinance library · last-2-day OHLC",
                "files": "sync/stock_prices.py",
                "trigger": "Daily 14:00 UTC (after US market open)",
                "pulls": (
                    "Close price + 1-day % change for ~20 mapped tickers (Roche→RHHBY, "
                    "AbbVie→ABBV…). Writes the company row and appends history."
                ),
                "structure": (
                    "companies update : { stock_price, stock_change, last_price_update }\n"
                    "stock_price_history : {\n"
                    "  company_id, ticker, price_usd, change_1d_pct,\n"
                    "  recorded_at, source:'yfinance'\n"
                    "}"
                ),
            },
            {
                "name": "GitHub Actions API (ops telemetry)",
                "system": "api.github.com · workflow run status",
                "files": "pipeline_health.py",
                "trigger": "Daily pipeline-health check",
                "pulls": (
                    "Recent workflow-run status/conclusions, rolled up into a health "
                    "summary. Not BD data — it's how the platform watches its own pipelines."
                ),
                "structure": (
                    "per workflow : { name, status, conclusion, run timestamps }\n"
                    "→ system_status.health_summary · pipeline_runs"
                ),
            },
        ],
    },
    {
        "label": "B · Brought back by an LLM — Claude grabs & returns facts",
        "blurb": (
            "Two modes. **Live web search** (the `web_search` tool, opt-in per prompt) "
            "genuinely pulls new info off the web. **Trained knowledge** asks the model to "
            "recall what it already knows — fast, but lower-trust, so it lands in a review "
            "queue rather than straight into production. All routed through `ai/client.py`."
        ),
        "sources": [
            {
                "name": "Landscape search  (live web search)",
                "system": "Claude Sonnet + web_search (max 5 searches) · run_text",
                "files": "ai/prompts/landscape_search.py · enrichment/company_enrichment.py",
                "trigger": "Company-enrichment run, per area",
                "pulls": (
                    "Every company with a program in an area (preclinical→approved): names, "
                    "compounds, mechanism, stage, indication, partnerships."
                ),
                "structure": (
                    "→ free-text narrative (no schema)\n"
                    "   consumed downstream by Entity Discovery, which structures it into\n"
                    "   discovery candidates (see group C / discovery_queue)."
                ),
            },
            {
                "name": "Company intel search  (live web search)",
                "system": "Claude Sonnet + web_search (max 5) · run_text",
                "files": "ai/prompts/company_intel_search.py · pipeline/nodes/gather_web_intel.py",
                "trigger": "Company-enrichment synthesis step",
                "pulls": (
                    "Fresh per-company intel: clinical readouts, financing/runway, BD & "
                    "M&A activity, catalyst timeline."
                ),
                "structure": (
                    "→ structured free-text block, organized as:\n"
                    "   clinical data · financing · BD activity · catalyst timeline\n"
                    "   then fed (no web search) into the enrichment synthesis schema."
                ),
            },
            {
                "name": "Company intake research  (trained knowledge)",
                "system": "Claude · run_json (no web search)",
                "files": "intake/company_intake.py · pipeline/company_intake/nodes/research_company.py",
                "trigger": "Manual CLI — you name a company",
                "pulls": (
                    "Open-ended profile of a named company across all active areas, scored "
                    "for relevance. Lands in discovery_queue for human approval."
                ),
                "structure": (
                    "company  : { canonical_name, ticker, geography, type, website }\n"
                    "pipeline : [{ drug_name, target, mechanism, modality, stage, nct_ids }]\n"
                    "deals    : [{ date, type, partner, asset, value }]\n"
                    "area_assessment : { <area_id>: {relevance, rationale, confidence} }"
                ),
            },
            {
                "name": "Drug intake research  (trained knowledge)",
                "system": "Claude Sonnet · run_json (no web search)",
                "files": "intake/drug_intake.py",
                "trigger": "Manual CLI — you name a drug",
                "pulls": (
                    "Resolves a drug's identity, routes it to areas, audits completeness, "
                    "assigns an evidence tier (Confirmed/Likely/Emerging/Hypothesis)."
                ),
                "structure": (
                    "drug_identity   : { canonical_name, aliases, company_origin,\n"
                    "                    modality, target, mechanism, stage }\n"
                    "area_relevance  : { <area_id>: {relevance_score, overlap_tier,\n"
                    "                    confidence, reasoning} }\n"
                    "completeness_audit : { missing_fields, missing_trials, … }"
                ),
            },
        ],
    },
    {
        "label": "C · Human-entered — you (or a reviewer) put data in",
        "blurb": (
            "Data a person supplies, by hand. The dashboard's other HTML pages "
            "(atlas, intelligence) only *read* from Supabase — they're not ingest. "
            "These are the points where a human is the source."
        ),
        "sources": [
            {
                "name": "Enrichment feedback UI",
                "system": "pages/meridian_feedback_ui.html · Supabase JS client",
                "files": "writes kyle_reviews · correction_labels · enriched_field_log",
                "trigger": "Browser — you review AI-enriched fields (Y/N/U/S keys)",
                "pulls": (
                    "Your verdict on each enriched field, plus an optional corrected value. "
                    "Doubles as the positive/negative label store for fine-tuning."
                ),
                "structure": (
                    "kyle_reviews : {\n"
                    "  entity_type, entity_id, field_name, field_value,\n"
                    "  action: confirmed|corrected|uncertain|skipped,\n"
                    "  notes, reviewed_at, fine_tune_use\n"
                    "}\n"
                    "correction_labels (on 'incorrect') : {\n"
                    "  model_output, correct_value, error_type, error_severity\n"
                    "}"
                ),
            },
            {
                "name": "Submitted intel (URL drop)",
                "system": "submitted_intel table → reviewed by script",
                "files": "intake/review_submitted_intel.py (fetch + extract) · execute_intel_actions.py",
                "trigger": "You submit a URL/paste; script validates, fetches, extracts",
                "pulls": (
                    "A user-supplied source URL (and optional pasted text). The script HEAD-"
                    "checks it, fetches the page, and has Claude extract entities + proposed actions."
                ),
                "structure": (
                    "submitted_intel : {\n"
                    "  source_url, submitted_text, validation_status, http_status,\n"
                    "  extracted_title,\n"
                    "  extracted_entities_json  : { companies[], drugs[], deals[] },\n"
                    "  extracted_key_facts_json : [{ fact, confidence }],\n"
                    "  proposed_actions_json    : [{ action, table, … }]\n"
                    "}"
                ),
            },
            {
                "name": "Conversation intake (session notes)",
                "system": "Claude extraction · run_json",
                "files": "intake/conversation_intake.py → conversation_intelligence_intake",
                "trigger": "Manual CLI — you paste meeting/call notes",
                "pulls": (
                    "Free-form notes → discrete, citation-scored facts (each kept with the "
                    "verbatim quote that supports it) for human review before promotion."
                ),
                "structure": (
                    "conversation_intelligence_intake : {\n"
                    "  session_date, entity_type, entity_name,\n"
                    "  fact_type, fact_text, supporting_quote,\n"
                    "  auto_confidence: 0.0–1.0, review_status: pending|confirmed|rejected\n"
                    "}"
                ),
            },
        ],
    },
]


def render_mm_ingest() -> None:
    st.button("← Back", on_click=go_to, args=("mental_model",))

    st.title("1 · Ingest — getting facts in")
    st.write(
        "Every point where **new or external data enters** the platform, grouped by "
        "*how* it gets in. Anything that reaches outside the database — a public API, "
        "an RSS feed, a web search, a person typing — counts as ingest. Each source "
        "below lists the file(s) that pull it, when it runs, and the structure of what "
        "comes back."
    )
    st.caption(
        "Field lists are representative, not exhaustive. Verified against the current "
        "branch — paths may shift as the scripts/pipeline/ migration lands."
    )

    for group in INGEST_GROUPS:
        st.divider()
        st.subheader(group["label"])
        st.write(group["blurb"])
        for src in group["sources"]:
            with st.expander(f"{src['name']}  ·  {src['system']}"):
                st.caption(f"**Files:** `{src['files']}`")
                st.caption(f"**Runs:** {src['trigger']}")
                st.write(src["pulls"])
                st.markdown("**Expected data & structure**")
                st.code(src["structure"], language="text")

    st.divider()
    st.info(
        "Closely related but downstream: raw text pulled here is later *structured* "
        "by LLM extraction — news articles → intel records, abstracts → PK/PD "
        "parameters. That transformation lives in the **Interpret** stage, not here."
    )


# ── Store stage — the Supabase database ──────────────────────────────────────
# The single source of truth: one Supabase Postgres project, ~140 tables + 13
# views. migrations/v1_schema.sql is the authoritative snapshot (no forward v2+
# migrations yet). Every Python write goes through six helpers in scripts/_db.py;
# the browser reads directly with the anon key. Verified against v1_schema.sql.

# The six REST helpers every backend write/read flows through.
STORE_ACCESS = [
    ("sb_get(table, params)", "GET /rest/v1/{table}", "Read rows (filters as query params)."),
    ("sb_upsert(table, records, on_conflict)", "POST · resolution=merge-duplicates",
     "Insert or merge on a conflict key — the workhorse for enrichment writes."),
    ("sb_insert(table, records)", "POST", "Plain insert, no conflict handling."),
    ("sb_post(table, record)", "POST", "Insert one row, return it."),
    ("sb_patch(table, record, match_params)", "PATCH /rest/v1/{table}?…", "Update rows matching the filter."),
    ("sb_delete(table, match_params)", "DELETE /rest/v1/{table}?…", "Delete rows matching the filter."),
]

# Table domains. Representative tables per domain (not all ~140), each with a
# one-line purpose. Grouped to match how the platform actually thinks about data.
STORE_DOMAINS = [
    {
        "label": "Core entities",
        "blurb": "The primary business objects everything else hangs off of.",
        "tables": [
            ("companies", "Pharma/biotech orgs — status, parent, ticker, strategic value."),
            ("drugs", "Candidates & approved products — stage, mechanism, ownership, overlap."),
            ("trial_identity / trial_facts", "Trials keyed by NCT id — phase, status, enrollment, endpoints."),
            ("targets", "Molecular targets (slug ids like `tl1a`) — class, pathway."),
            ("indications", "Diseases / conditions with abbreviations and biology tags."),
            ("catalysts", "Upcoming events — readouts, PDUFA dates, conferences."),
            ("canonical_drugs", "Identity registry that merges aliases to one drug."),
            ("molecule_intelligence", "Per-drug molecular detail — format, valency, Fc, affinity."),
        ],
    },
    {
        "label": "Relationships & graph",
        "blurb": "How entities connect — the joins that make the pipeline query work.",
        "tables": [
            ("entity_edges", "General subject→predicate→object triples (e.g. COMPETES_WITH)."),
            ("ownership_edges", "ORIGINATED_BY / LICENSED_IN / ACQUIRED, with territory scope."),
            ("company_partnerships", "Licensee/co-dev relationships — partner, type, verified, source."),
            ("drug_targets", "Drug→target links; role = primary | component (bispecific arm)."),
            ("drug_indications", "Drug→indication mapping with approval status per region."),
            ("company_areas / drug_areas", "Which entities are active in which areas."),
        ],
    },
    {
        "label": "Deals & BD intelligence",
        "blurb": "Business-development context — the deal record and who to call.",
        "tables": [
            ("deals", "Licensing/M&A events — parties, economics, source, verified flag."),
            ("bd_recommendations", "Scored deal suggestions for Ailux — rank, urgency, framing."),
            ("partner_intelligence_profiles", "Per-company BD dossier — thesis, fit, deal structure."),
            ("company_strategic_views", "Competitive / partner / acquisition-target classification."),
            ("company_profiles", "Per-area narrative — why it matters, key risk, BD summary."),
        ],
    },
    {
        "label": "Intelligence & signals (news)",
        "blurb": "Time-stamped competitive events and the literature behind them.",
        "tables": [
            ("intel", "Competitive news items — headline, body, importance, type."),
            ("signals / competitive_signals", "Enrichment-triggered events with relevance scores."),
            ("conference_abstracts", "Congress data linked to drug/target/indication/trial."),
            ("publications / clinical_evidence_items", "Papers & readouts with efficacy/safety data."),
            ("meridian_issues", "The synthesized daily BD briefing (body_html, plan_json)."),
        ],
    },
    {
        "label": "Clinical & molecular depth",
        "blurb": "The deep evidence layer — a large family of specialized tables.",
        "tables": [
            ("drug_pk_parameters / drug_pd_parameters", "PK (Cmax, AUC, half-life) and PD/target-engagement."),
            ("drug_biomarkers", "Biomarker predictivity — sensitivity, clinical utility."),
            ("drug_clinical_benchmarks / efficacy_benchmarks", "Remission/response rates by dose & timepoint."),
            ("indication_patient_intelligence", "Prevalence, treatment cascade, unmet need."),
            ("drug_bispecific_landscape", "TL1A/IL-23 program-specific competitive detail."),
        ],
    },
    {
        "label": "Scoring & ranking",
        "blurb": "Computed metrics — written by the Score stage, read by the dashboard.",
        "tables": [
            ("drug_area_scores", "Per-area overlap (Direct/Adjacent/…) and vs-Ailux positioning."),
            ("drug_competitive_scores", "Competitive score per context (target/indication/view)."),
            ("coverage_scores", "How complete each company/area is across 9 dimensions."),
            ("asset_value_predictions", "Composite program value score + rank."),
            ("drug_trust_scores", "Data-trust grade with a breakdown JSON."),
        ],
    },
    {
        "label": "Validation, sources & governance",
        "blurb": "The integrity layer — covered in depth on the Validate page.",
        "tables": [
            ("governance_violations", "Soft-constraint violations awaiting review (rule_name, resolved)."),
            ("drug_validation_results", "Per-check validation status & confidence."),
            ("source_validation_log / source_verifications", "Per-URL liveness & trust checks."),
            ("drug_sources", "Source-of-claim provenance — url_status, content_confirms_claim."),
            ("field_change_audit", "Every field change, flagged is_governance_relevant + rule."),
        ],
    },
    {
        "label": "Enrichment, ML & intake queues",
        "blurb": "How the platform records its own work and learns from corrections.",
        "tables": [
            ("enrichment_runs", "One row per job — model, tokens, fields set/changed/failed."),
            ("enriched_field_log", "Per-field enrichment metadata — value, confidence, source."),
            ("kyle_reviews / correction_labels", "Human verdicts + corrections → fine-tune corpus."),
            ("submitted_intel / conversation_intelligence_intake", "Human-supplied intake (see Ingest)."),
            ("research_queue / enrichment_queue", "Work waiting to be done."),
        ],
    },
    {
        "label": "System & ops",
        "blurb": "Operational state — how the platform watches itself.",
        "tables": [
            ("system_status", "Singleton heartbeat — last enrichment/research, record counts."),
            ("pipeline_runs", "GitHub Actions run history — status, conclusion, healthy flag."),
            ("stock_price_history", "Daily price snapshots per ticker."),
            ("validation_tests", "Ground-truth test cases with expected vs actual values."),
        ],
    },
]

# Key columns for the core tables — abridged to the meaningful + governance-
# relevant fields. Quoted from v1_schema.sql.
STORE_CORE_COLUMNS = [
    ("companies", (
        "id            : text  [PK]   # slug, e.g. 'merck'\n"
        "name          : text\n"
        "ticker / exchange : text\n"
        "status        : text         # subsidiary | acquired | …  ← governance\n"
        "parent_company_id : text     # set for both subsidiary & acquired ← governance\n"
        "company_type  : text\n"
        "strategic_value_score : int\n"
        "enrichment_run_id : text"
    )),
    ("drugs", (
        "id            : text  [PK]   # slug, e.g. 'alx001'\n"
        "name          : text\n"
        "brand_name    : text         # if set → stage must be approved* ← governance\n"
        "brand_name_verified : bool\n"
        "company_id    : text         # ORIGINATOR, always ← governance\n"
        "current_owner_company_id : text   # may differ from originator\n"
        "canonical_drug_id : text\n"
        "stage         : text         # Preclinical | Phase 1/2/3 | Approved…\n"
        "mechanism / target : text\n"
        "overlap       : text         # Direct | Adjacent | Same-Space | Watch\n"
        "source_url    : text         # source for stage/indication ← governance\n"
        "data_confidence : text"
    )),
    ("trial_identity + trial_facts", (
        "nct_id        : text  [PK]   # ClinicalTrials.gov id\n"
        "drug_id       : text\n"
        "acronym / official_title : text\n"
        "secondary_ids / alias_tokens : text[]\n"
        "phase / status : text\n"
        "enrollment    : bigint\n"
        "primary_endpoints : jsonb\n"
        "conditions    : jsonb\n"
        "has_china_site : bool\n"
        "start_date / primary_completion_date : date"
    )),
    ("catalysts", (
        "id            : bigserial [PK]\n"
        "drug_id / company_id : text\n"
        "event_type    : text   # trial_readout | pdufa_date | conference…\n"
        "event_name    : text\n"
        "expected_date / expected_quarter\n"
        "strategic_significance : text  # P0 | P1 | P2 | watch\n"
        "confidence    : text   # verified | model | inferred\n"
        "source_url    : text\n"
        "is_past / actual_date"
    )),
    ("deals", (
        "id            : bigint [PK]\n"
        "deal_date     : date\n"
        "from_company / to_company : text\n"
        "drug_id       : text\n"
        "deal_type     : text   # license | acquisition | collab | option\n"
        "upfront_usd_m / total_usd_m : text\n"
        "headline / detail : text\n"
        "source_url    : text         # required ← governance\n"
        "economic_terms_verified : bool"
    )),
    ("company_partnerships", (
        "id            : bigint [PK]\n"
        "lead_company_id / partner_company_id : text\n"
        "partner_name  : text\n"
        "partnership_type : text\n"
        "drug_id / area_id : text\n"
        "partnership_verified : bool   # false until confirmed ← governance\n"
        "source_url    : text          # required ← governance\n"
        "geographic_rights / is_current"
    )),
    ("governance_violations", (
        "id            : bigserial [PK]\n"
        "table_name    : text   # e.g. 'drugs'\n"
        "row_id        : text   # the offending row's PK\n"
        "rule_name     : text   # e.g. brand_name_implies_approved\n"
        "description   : text\n"
        "detected_at   : timestamptz\n"
        "resolved      : bool   # session-start check = WHERE resolved=false\n"
        "resolved_at / resolved_by / resolution_notes\n"
        "UNIQUE(table_name, row_id, rule_name)"
    )),
]


def render_mm_store() -> None:
    st.button("← Back", on_click=go_to, args=("mental_model",))

    st.title("2 · Store — where it lives")
    st.write(
        "One **Supabase Postgres** project is the single source of truth — roughly "
        "**140 tables and 13 views**. `migrations/v1_schema.sql` is the authoritative "
        "snapshot; there are no forward (v2+) migrations yet, so that file *is* the schema."
    )
    st.caption(
        "Table lists below are representative, not the full ~140. Columns are abridged "
        "to the meaningful + governance-relevant fields, quoted from v1_schema.sql."
    )

    st.divider()
    st.subheader("How data gets in and out")
    st.write(
        "**Every backend write goes through six helpers** in `scripts/_db.py` — no raw "
        "SQL or stray HTTP from pipeline code. They wrap the Supabase REST API and run "
        "with the **service key** (full access)."
    )
    for sig, http, note in STORE_ACCESS:
        st.markdown(f"`{sig}`  ·  *{http}*")
        st.caption(note)
    st.write(
        "**The browser reads directly** from Supabase with the **anon key** (read-only "
        "for almost everything, RLS-enforced). The only browser writes are user feedback "
        "(`meridian_feedback`) and document uploads (`source_documents`). Credentials load "
        "from env vars or repo dotfiles via `scripts/_common.py` — never hard-coded."
    )

    st.divider()
    st.subheader("The tables, by domain")
    for dom in STORE_DOMAINS:
        with st.expander(f"{dom['label']}"):
            st.caption(dom["blurb"])
            for name, purpose in dom["tables"]:
                st.markdown(f"`{name}` — {purpose}")

    st.divider()
    st.subheader("Key columns — the core tables")
    st.caption("Fields marked ← governance are the ones the rules on the Validate page police.")
    for name, cols in STORE_CORE_COLUMNS:
        with st.expander(f"{name}"):
            st.code(cols, language="text")

    st.divider()
    st.subheader("ID & key conventions")
    st.markdown(
        "- **Core entities use human-readable slug ids** — `drugs.id='alx001'`, "
        "`companies.id='merck'`, `targets.id='tl1a'`.\n"
        "- **Trials** are keyed by `nct_id`; **system/audit** tables use UUIDs; "
        "**deals / catalysts / partnerships / governance_violations** use integer (BIGSERIAL) ids.\n"
        "- **Soft FKs** like `enrichment_run_id` aren't DB-enforced (so pipeline recovery "
        "can't orphan-block); a few are hard FKs (e.g. `drug_targets → targets` ON DELETE RESTRICT)."
    )

    st.divider()
    st.info(
        "**Governance is coupled to writes — but mostly logged, not blocked.** A Pydantic "
        "pass (`ai/validators/drug_fields.py`) runs *before* a write and silently drops "
        "invalid fields; it doesn't reject the row. Rule violations (brand_name implies "
        "approved, deal/partnership missing source_url, …) are written to "
        "`governance_violations` as soft constraints for human review — they don't halt "
        "enrichment. The full picture is the **Validate · Governance** page."
    )


# ── Validate · Governance stage ──────────────────────────────────────────────
# The integrity layer that wraps writes. Two truths shape this page, both
# verified in code: (1) governance is mostly a SOFT constraint — violations are
# logged for review, they don't block the write; (2) there's a real gap between
# rules described in CLAUDE.md and rules actually enforced by code. Both are
# surfaced honestly below.

# The 4-tier model (Tier 2 is the enrichment layer itself, not a separate script).
VALIDATE_TIERS = [
    ("Tier 1 · Signal monitor",
     "Lightweight heuristic relevance scoring on incoming signals; score ≥ 8 gets "
     "queued for enrichment. `intelligence/signal_monitor.py`. No LLM."),
    ("Tier 2 · Enrichment + write-time check",
     "The enrichment layer itself. Its only synchronous guard is a Pydantic pass "
     "(`ai/validators/drug_fields.py`) that drops bad fields before the write."),
    ("Tier 3 · Source verification",
     "Is every `source_url` real, reachable, and from a trusted domain? "
     "`source_verifier.py` (HTTP) + `content_verifier.py` (Claude judges claim support)."),
    ("Tier 4 · QA / data integrity",
     "Post-enrichment contradiction, conflict, and coverage scans — and the only "
     "auto-fixer. `consistency_checker.py`, `conflict_detector.py`, `reconcile_drug_integrity.py`."),
]

# Rules actually enforced in code, writing to governance_violations.
VALIDATE_RULES_CODED = [
    {
        "name": "brand_name_implies_approved",
        "trigger": "Drug has a `brand_name` but `stage` is not one of the approved* values.",
        "where": "weekend_sprint.py (phase A2) + consistency_checker.py (E5)",
        "timing": "write-time scan + async",
        "lands": "governance_violations",
    },
    {
        "name": "codev_requires_source_url",
        "trigger": "A deal or company_partnership row has a null `source_url`.",
        "where": "weekend_sprint.py (phase A3) + migration seed",
        "timing": "async (reported)",
        "lands": "governance_violations",
    },
    {
        "name": "partner_name_in_target",
        "trigger": "A co-developed drug's `target` field contains the partner company's name "
                   "(target should be molecular targets only).",
        "where": "weekend_sprint.py (phase D1)",
        "timing": "write-time",
        "lands": "governance_violations",
    },
    {
        "name": "company_id_originator_mismatch",
        "trigger": "A deal's company differs from `drugs.company_id` (the originator).",
        "where": "consistency_checker.py (E5)",
        "timing": "async",
        "lands": "agent_disagreements  (not governance_violations)",
    },
]

# Rules described in CLAUDE.md / enrichment prompts but NOT enforced by an automated check.
VALIDATE_RULES_POLICY = [
    ("Licensing attribution", "`drugs.company_id` = originator always. Detected as a "
     "*disagreement* if violated, but there's no hard rule that blocks or auto-flags it."),
    ("Company status (subsidiary vs acquired)", "The 5-step decision test is human judgment — "
     "no enforcement code."),
    ("Deal sequencing / timing", "e.g. don't target AbbVie for a TL1A bispecific before the "
     "Oct-2026 ABBV-701 readout. Lives in the enrichment prompt, not a violation check."),
    ("Co-development attribution", "`partnership_verified=false` until sourced is a field "
     "convention, not an automated violation."),
    ("approval_date_implies_approved", "Named in the governance migration's docstring but "
     "never actually implemented."),
]

# The async validation scripts, grouped by what they do.
VALIDATE_SCRIPT_GROUPS = [
    {
        "label": "Source & content verification (Tier 3–4)",
        "scripts": [
            ("source_verifier.py", "HTTP",
             "Every `source_url` is real, reachable, trusted-domain; flags fabricated/search URLs. "
             "→ source_validation_log, governance_violations."),
            ("content_verifier.py", "Claude (judge)",
             "Does the page actually *support* the claim? Verdict supports/contradicts/absent/unreadable "
             "(conservative — won't mark false on unreadable). → drug_sources.content_confirms_claim."),
            ("verify_sources.py", "HTTP",
             "Are `drug_sources` URLs still live? Updates url_status and recomputes "
             "`drugs.data_confidence` from source counts."),
            ("audit_sources.py", "HTTP",
             "Classifies & HTTP-checks every source_url across scores/intel/catalysts into "
             "authority tiers. → source_verifications."),
            ("source_verify.py", "Claude (knowledge)",
             "Fills missing `source_url` + confidence for Direct/Adjacent score rows."),
        ],
    },
    {
        "label": "Consistency & conflicts (Tier 4)",
        "scripts": [
            ("consistency_checker.py", "rules",
             "8 contradiction checks — stage vs trial phase, brand vs approval, originator, "
             "duplicates, deal attribution, broken stage history… → governance_violations / agent_disagreements."),
            ("conflict_detector.py", "rules",
             "Free-text `drugs` fields vs the structured tables (target, indication, company). "
             "→ drug_validation_results (needs_review)."),
            ("verify_competitor_edges.py", "rules",
             "Rule-verifies competitive graph edges (shared area/target, parent_company_id). "
             "→ entity_relationships."),
            ("verify_publication_values.py", "rules",
             "Do stored efficacy numbers actually appear in the linked paper's abstract (±1.5pp)? "
             "→ benchmark_publication_checks."),
        ],
    },
    {
        "label": "Completeness & ground-truth",
        "scripts": [
            ("company_validator.py", "rules",
             "Company completeness (P0/P1/P2) + a 0–100 health score. → drug_validation_results."),
            ("validate_ground_truth.py", "rules",
             "Runs the `validation_tests` suite against live data; a failing P1 test exits non-zero "
             "(regression gate)."),
            ("validation_research.py", "HTTP",
             "Resolves 'claims a clinical stage but has 0 trials' warnings by searching CT.gov / ANZCTR; "
             "flips warning→pass or confirms the gap."),
        ],
    },
    {
        "label": "Auto-fix — never silent",
        "scripts": [
            ("reconcile_drug_integrity.py", "rules",
             "Auto-corrects only high-confidence conflicts. Every fix writes THREE records: "
             "field_change_audit + a documenting drug_sources row + a resolved governance_violations row."),
        ],
    },
]

# Where validation output lands.
VALIDATE_TABLES = [
    ("governance_violations", "Soft-constraint violations awaiting review — rule_name, row_id, resolved."),
    ("agent_disagreements", "Data contradictions found by the consistency checker."),
    ("drug_validation_results", "pass / needs_review for completeness, conflicts, and tests."),
    ("source_validation_log · source_verifications", "Per-URL liveness, trust, and authority-tier checks."),
    ("drug_sources", "content_confirms_claim, url_status, confidence — claim-level provenance."),
    ("field_change_audit", "Every change, flagged is_governance_relevant + is_correction with a row snapshot."),
]


def render_mm_validate() -> None:
    st.button("← Back", on_click=go_to, args=("mental_model",))

    st.title("Validate · Governance — wraps every write")
    st.write(
        "The integrity layer. It's drawn as a band around the whole flow because it "
        "touches every write — but two things are true and worth being precise about:"
    )
    st.markdown(
        "- **It's mostly a *soft* constraint.** Violations are *logged for human review*, "
        "they don't block the write. Enrichment keeps flowing; a person resolves issues later.\n"
        "- **Described ≠ enforced.** Several rules in `CLAUDE.md` are policy the enrichment "
        "prompt and a human follow — only a few are actually checked by code."
    )

    st.divider()
    st.subheader("Two timing modes")
    st.markdown(
        "**Synchronous (write-time)** — light and fast. One real guard: "
        "`ai/validators/drug_fields.py` → `validate_drug_updates()` runs a Pydantic check on "
        "the 7 enriched drug fields *before* the write and **drops** any that fail "
        "(drop-on-fail — the bad field is stripped, the row still writes). A couple of "
        "`weekend_sprint` phases also scan as they go."
    )
    st.markdown(
        "**Asynchronous (scheduled scans)** — the heavy lifting. ~13 scripts in "
        "`scripts/validation/` run on schedules and in the weekend sprint's Block E, *after* "
        "data has already landed. This is where most governance actually happens."
    )

    st.divider()
    st.subheader("The 4-tier model")
    for name, desc in VALIDATE_TIERS:
        st.markdown(f"**{name}** — {desc}")

    st.divider()
    st.subheader("Governance rules — enforced in code")
    st.caption("These write to a violations table. Trigger conditions are quoted from the code.")
    for r in VALIDATE_RULES_CODED:
        with st.expander(f"{r['name']}"):
            st.markdown(f"**Triggers when:** {r['trigger']}")
            st.markdown(f"**Where:** `{r['where']}`")
            st.markdown(f"**Timing:** {r['timing']}")
            st.markdown(f"**Lands in:** `{r['lands']}`")

    st.subheader("Governance rules — policy only (prompt + human review)")
    st.caption("Described in CLAUDE.md and followed during enrichment, but no automated check enforces them.")
    for name, desc in VALIDATE_RULES_POLICY:
        st.markdown(f"**{name}** — {desc}")

    st.divider()
    st.subheader("The validation scripts")
    for grp in VALIDATE_SCRIPT_GROUPS:
        with st.expander(grp["label"]):
            for name, kind, desc in grp["scripts"]:
                st.markdown(f"`{name}`  ·  *{kind}*")
                st.caption(desc)

    st.divider()
    st.subheader("Where it lands")
    for name, purpose in VALIDATE_TABLES:
        st.markdown(f"`{name}` — {purpose}")

    st.divider()
    st.info(
        "**How violations get acted on.** The session-start ritual in CLAUDE.md "
        "(check `governance_violations WHERE resolved=false`) is a *convention*, not "
        "automation — the morning-summary pipeline surfaces open violations, and "
        "`weekend_sprint` Phase A1 logs them, but nothing hard-fails on them. They wait "
        "for a human to resolve and stamp `resolved=true`."
    )


# Custom per-stage renderers; stages without one fall back to the generic stub.
MM_STAGE_RENDERERS = {
    "ingest": render_mm_ingest,
    "store": render_mm_store,
    "validate": render_mm_validate,
}


def render_mm_stage(stage: dict) -> None:
    custom = MM_STAGE_RENDERERS.get(stage["key"])
    if custom is not None:
        custom()
        return

    st.button("← Back", on_click=go_to, args=("mental_model",))

    st.title(f"{stage['label']} — {stage['tagline']}")
    st.write(stage["body"])
    st.divider()
    st.info("More depth on this stage is coming — we'll build it out next.")


def render_home() -> None:
    inject_card_styles()

    st.button("← Back", on_click=go_to, args=("landing",))

    st.title("🛠️ Github Workflows")
    st.caption(
        "Pick a workflow to see exactly what runs, in what order, "
        "and what each file is responsible for."
    )
    st.write(
        "**Why GitHub Workflows?** These are scheduled jobs (GitHub Actions, on cron) "
        "that do the unattended, recurring work — sweeping news, fetching abstracts, "
        "running weekend enrichment sprints — without anyone needing to kick them off "
        "by hand. The benefit is hands-off reliability: each one runs on its own "
        "schedule, in its own isolated environment, and leaves a log trail you can "
        "audit after the fact."
    )
    st.divider()

    def workflow_card(pipeline: dict) -> None:
        workflow_filename = pipeline["workflow_file"].rsplit("/", 1)[-1]
        st.button(
            f"**{workflow_filename}**",
            key=f"btn_{pipeline['key']}",
            type="primary",
            width="stretch",
            on_click=go_to,
            args=(pipeline["key"],),
        )

    for label, group in PIPELINE_GROUPS:
        st.markdown(f"### {label}")
        cols = st.columns(3)
        for i, pipeline in enumerate(group):
            with cols[i % 3]:
                workflow_card(pipeline)
        st.write("")


def render_pipeline_page(pipeline: dict) -> None:
    st.button("← Back", on_click=go_to, args=("home",))

    st.title(pipeline["workflow_name"])
    st.caption(f"Workflow file: `{pipeline['workflow_file']}`")
    st.caption(f"Schedule: {pipeline['schedule']}")
    st.caption(f"Entrypoint: `{pipeline['entrypoint']}`")
    st.write(pipeline["summary"])

    st.divider()
    st.subheader("Execution flow")
    st.caption(
        "Boxes inside a dotted cluster run in parallel; the dashed clusters "
        "and the arrows between them show the sequential order of phases."
    )
    st.graphviz_chart(pipeline["dot"], width="stretch")

    st.divider()
    st.subheader("Data flow — inputs & outputs")
    st.caption(
        "What information comes in (and where from), what the pipeline "
        "does with it, and what it ultimately persists (and where to)."
    )
    st.graphviz_chart(pipeline["io_dot"], width="stretch")

    io_col1, io_col2 = st.columns(2)
    with io_col1:
        st.markdown("**Reads — inputs**")
        for item in pipeline["io"]["reads"]:
            st.markdown(f"`{item['name']}` — {item['kind']}")
            st.caption(f"via `{item['via']}`")
            st.write(item["desc"])
            with st.expander("How much does it ask for, and how?"):
                st.write(item["scope"])
            st.write("")
    with io_col2:
        st.markdown("**Writes — outputs**")
        for item in pipeline["io"]["writes"]:
            st.markdown(f"`{item['name']}` — {item['kind']}")
            st.caption(f"via `{item['via']}`")
            st.write(item["desc"])
            with st.expander("How much does it write, and how?"):
                st.write(item["scope"])
            st.write("")

    with st.expander("How is the data filtered, deduped, and cleaned before it's persisted?"):
        st.write(pipeline["io"]["cleaning"])

    st.divider()
    unit_key = pipeline.get("unit_key", "file")
    st.subheader(pipeline.get("unit_section_title", "File-by-file, in order"))

    for phase in pipeline["phases"]:
        st.markdown(f"#### {phase['label']}")
        st.caption(phase["note"])

        for group in phase["groups"]:
            if len(group) > 1:
                st.markdown("**Run in parallel:**")
            for item in group:
                if item.get("lines") is not None:
                    st.markdown(f"`{item[unit_key]}` &nbsp;·&nbsp; {item['lines']} lines")
                else:
                    st.markdown(f"`{item[unit_key]}`")
                st.write(item["desc"])
            st.write("")


def render_state_graphs_home() -> None:
    inject_card_styles()

    st.button("← Back", on_click=go_to, args=("landing",))

    st.title("🌐 State Graphs")
    st.caption(
        "Pick a LangGraph StateGraph pipeline to see its nodes, topology, "
        "and what each step is responsible for."
    )
    st.write(
        "**Why LangGraph?** These pipelines do multi-step work that branches — "
        "fetch, filter, enrich, extract, write — where the next step depends on "
        "what the previous one found. LangGraph makes that explicit: each step is "
        "an independent node, the data threaded between them is a typed state "
        "object, and the branching logic is a named, visible edge in a compiled "
        "graph rather than buried in nested if/else. The benefit is a pipeline "
        "you can see, test step-by-step, and resume from the last successful node "
        "instead of rerunning the whole thing from scratch."
    )
    st.divider()

    def state_graph_card(graph: dict, key: str) -> None:
        st.button(
            f"**{graph['name']}**",
            key=key,
            type="primary",
            width="stretch",
            on_click=go_to,
            args=(f"state_graph::{graph['key']}",),
        )

    with st.container(key="teal_zone"):
        cols = st.columns(3)
        for i, graph in enumerate(STATE_GRAPHS):
            with cols[i % 3]:
                state_graph_card(graph, f"btn_state_graph_{graph['key']}")


def render_state_graph_page(graph: dict) -> None:
    st.button("← Back", on_click=go_to, args=("state_graphs",))

    st.title(graph["name"])
    st.caption(f"Module: `{graph['module']}` &nbsp;·&nbsp; builder: `{graph['builder']}()`")

    if "summary" not in graph:
        st.info("More detail (topology diagram, node-by-node breakdown) coming soon.")
        return

    if "entrypoint" in graph:
        st.caption(f"Entrypoint: `{graph['entrypoint']}`")
    st.write(graph["summary"])

    st.divider()
    st.subheader("Graph topology")
    st.caption(
        "Generated live from the compiled StateGraph (app.get_graph()) — it "
        "can't drift from the code. Solid edges are unconditional; dashed "
        "amber edges are conditional branches, explained under "
        "“Conditional routing” below."
    )
    try:
        compiled_app = build_app(graph["module"], graph["builder"])
        st.graphviz_chart(topology_dot(compiled_app), width=graph.get("diagram_width", 320))
    except (Exception, SystemExit) as e:
        # Some pipelines import scripts that load Supabase/Anthropic credentials
        # at module level (sys.exit if absent) — that's a SystemExit, not an
        # Exception, so it must be caught explicitly to keep the page usable
        # in environments without those credentials configured.
        st.warning(f"Could not build a live topology diagram: {e}")

    state = graph.get("state")
    if state:
        st.divider()
        st.subheader("State")
        st.caption(f"`{state['class']}` — defined in `{state['module']}`")
        for f in state["fields"]:
            st.markdown(f"`{f['name']}` &nbsp;·&nbsp; *{f['type']}*")
            st.write(f["desc"])
            st.write("")

    nodes = graph.get("nodes")
    if nodes:
        st.divider()
        st.subheader("Nodes, in graph order")
        for node in nodes:
            st.markdown(f"#### {node['name']}")
            st.caption(f"`{node['file']}` &nbsp;·&nbsp; {node['lines']} lines")
            st.write(node["desc"])

    routing = graph.get("routing")
    if routing:
        st.divider()
        st.subheader("Conditional routing")
        st.caption(
            "Each branch below replaces a nested if/else in the original "
            "script with an explicit, named routing function — visible as a "
            "dashed edge in the topology diagram above."
        )
        for r in routing:
            st.markdown(f"**After `{r['after']}` → `{r['function']}`**")
            for b in r["branches"]:
                st.markdown(f"- *{b['condition']}* → `{b['to']}` — {b['desc']}")
            st.write("")


def main() -> None:
    view = st.session_state.view
    if view == "landing":
        render_landing()
    elif view == "mental_model":
        render_mental_model()
    elif view.startswith("mm::"):
        stage = MENTAL_MODEL_STAGE_BY_KEY.get(view.split("::", 1)[1])
        if stage is not None:
            render_mm_stage(stage)
        else:
            st.session_state.view = "mental_model"
            render_mental_model()
    elif view == "home":
        render_home()
    elif view == "state_graphs":
        render_state_graphs_home()
    elif view in PIPELINES:
        render_pipeline_page(PIPELINES[view])
    elif view.startswith("state_graph::"):
        graph_key = view.split("::", 1)[1]
        graph = next((g for g in STATE_GRAPHS if g["key"] == graph_key), None)
        if graph is not None:
            render_state_graph_page(graph)
        else:
            st.session_state.view = "state_graphs"
            render_state_graphs_home()
    else:
        st.session_state.view = "landing"
        render_landing()


main()
