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
            "**Supabase Postgres** is the single source of truth (~140 tables: companies, "
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
            "Where the data gets *read and turned into intelligence* — but only half of it "
            "is AI. `scripts/ai/client.py` is the one wrapper for every Claude call (model "
            "choice, cost tracking, JSON parsing). On top of it sit the **generative** "
            "layers: the **narratives** (`intelligence/write_meridian.py` daily briefing, "
            "`narrative/*`) and the **enrichment** synthesis (`enrichment/*`). Alongside "
            "them — and using **no LLM at all** — is the **deterministic relationship "
            "materialization** (`identity/*` dedup, `graph/*` edge building): pure string "
            "matching and SQL, with fuzzy matches flagged for a human, never auto-merged."
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
# The single source of truth: one Supabase Postgres project. Schema snapshot
# (migrations/v1_schema.sql) defines 140 tables; the live DB has drifted to ~167,
# of which only 73 are surfaced (rest = infra/inert/dark/scaffold/orphan). Every
# Python write goes through six helpers in scripts/_db.py; the browser reads
# directly with the anon key. Inventory from the TABLEDB catalog in the workflow map.

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
# Complete table inventory grouped by REAL status, from the team's own catalog
# embedded in pages/meridian_workflow_map.html (the TABLEDB object). Every table
# appears exactly once; counts sum to the live total. Row counts are from that
# snapshot. Categories: surfaced (app reads it) · infra (plumbing/links/audit) ·
# inert (data, no readers) · dark (written, never read) · scaffold (empty) ·
# orphan (disconnected). Each entry: (label, count, blurb, formatted table block).
STORE_CATALOG = [
    ("Surfaced", 73, (
        "What the app actually reads and shows. These are the tables that matter — the rest is plumbing, history, or dead weight."), (
        "field_change_audit                    59840\nidentity_audit_log                     4131\nentity_edges                           1164\nintel                                  1160\nintel_companies                        1146\ncatalysts                              1018\n"
        "competitive_signals                     997\ndrug_validation_results                 993\nbackfill_preview                        873\ntrials                                  706\ndrug_intelligence_qa                    590\ndrug_competitive_scores                 371\n"
        "drug_indications                        361\ntrial_indications                       299\ncompany_portfolio_conflicts             260\nnews_articles                           251\ndrug_targets                            216\ndeals                                   210\n"
        "drug_area_scores                        210\ndrug_areas                              206\ncanonical_drugs                         204\ndrugs                                   204\ncompany_documents                       191\nresearch_queue                          171\n"
        "company_strategic_views                 168\nsignals                                 151\ncompany_profiles                        138\ncoverage_scores                         137\ncompany_areas                           133\ncompanies                               132\n"
        "ownership_edges                         117\nmolecule_intelligence                    99\ndiscovery_queue                          87\ntargets                                  76\ncompany_platform_views                   71\ndrug_clinical_benchmarks                 68\n"
        "company_signals                          57\nsource_documents                         55\nindications                              50\ndrug_pk_parameters                       47\ngeographic_approvals                     46\nbd_insights                              35\n"
        "governance_violations                    34\ncatalyst_calendar                        28\nintel_areas                              27\narea_perspectives                        22\nindication_priority_scores               19\nindication_biology_validation            17\n"
        "indication_patient_intelligence          17\nindication_patient_stratifiability       17\nindication_regulatory_clarity            17\nindication_window_urgency                17\npayer_tpp_criteria                       17\nindication_company_map                   16\n"
        "drug_failure_cascade                     15\nailux_bd_context                         14\nasset_transfer_history                   14\narea_knowledge                           13\nmeridian_issues                          13\ndrug_biomarkers                          12\n"
        "submitted_intel                          12\nlegacy_area_ontology_map                 11\ndrug_bispecific_landscape                10\nmodalities                               10\nlandscape_expected_competitors            9\nnon_responder_profiles                    9\n"
        "deal_sequencing_constraints               8\ntherapeutic_areas                         8\ncompetitive_landscapes                    5\ntarget_pairs                              5\nasset_differentiation_profiles            3\ndrug_combinations                         3\n"
        "system_status                             1\n"),
    ),
    ("Infra", 32, (
        "Plumbing: link/junction tables, alias maps, audit logs, run records. Real and active, but support machinery, not content you browse."), (
        "source_validation_log                  1364\nintel_target_links                     1288\nintel_drug_links                        904\nenriched_field_log                      813\nintel_company_links                     764\nintel_indication_links                  637\n"
        "trial_registries                        629\nschema_change_log                       369\nstock_price_history                     319\nfield_backfill_preview                  317\nintelligence_debt_queue                 255\ndrug_targets_legacy                     195\n"
        "company_aliases                         184\ndrug_aliases                            178\nindication_aliases                       86\nchange_log                               84\nenrichment_runs                          40\nnews_company_links                       31\n"
        "ontology_edges                           25\ntarget_mechanism_links                   13\nontology_mappings                        11\nentity_consistency_checks                10\nnews_indication_links                    10\ntarget_era_history                        7\n"
        "enrichment_queue                          6\ncoverage_computation_log                  4\nnews_drug_links                           4\nreview_queue                              4\nprompt_versions                           3\nailux_positions                           2\n"
        "news_target_links                         2\nontology_versions                         2\n"),
    ),
    ("Inert", 38, (
        "Exist with data but nothing currently reads them — built ahead of a feature, or left behind when one moved."), (
        "trial_geographic_scope                  143\ncompany_therapeutic_areas                78\nindication_co_occurrence                 76\ndrug_milestones                          66\ndrug_formulation_variants                64\ndrug_timeline_estimates                  36\n"
        "company_pipeline_gaps                    25\nregulatory_designations                  23\nbiology_tags                             18\nbispecific_differentiation_factors       18\npeak_revenue_estimates                   18\ndrug_development_steps                   16\n"
        "mechanism_precedent_map                  15\nbd_readiness_composite                   13\nportfolio_conflict_matrix                13\nailux_strategic_context                  12\ndeal_value_tracking                      12\nefficacy_benchmarks                      12\n"
        "patent_expiry_cliff_map                  12\ntarget_areas                             12\narea_metadata                            11\ninternal_pipeline_conflicts              11\nplatform_trial_arms                      11\nnonresponder_bispecific_bridge            8\n"
        "area_market_data                          7\nclinical_evidence_items                   7\ndeal_implied_valuation                    7\ndrug_pd_parameters                        7\nroutes_of_administration                  6\ndrug_approvals                            5\n"
        "partner_intelligence_profiles             5\nsop_registry                              5\ndrug_study_design_comparisons             4\ndrug_cdx_strategy                         3\ndrug_nonresponder_profiles                3\nplatform_trials                           3\n"
        "bispecific_clinical_hypothesis            1\nclinical_trial_design_recommendations      1\n"),
    ),
    ("Dark", 13, (
        "Written by the pipeline but never read back into the product. Candidates for either wiring-up or removal."), (
        "entity_relationships                   2474\nvalidation_tests                       1042\nsource_verifications                    230\nkyle_reviews                            109\ncompany_partnerships                     52\nintelligence_discoveries                 35\n"
        "mechanism_status                         33\ndrug_sources                             25\nbd_recommendations                       20\ntarget_pair_whitespace                   15\nconversation_intelligence_intake         12\nasset_value_predictions                   3\n"
        "landscape_briefings                       1\n"),
    ),
    ("Scaffold", 7, (
        "Created but empty (0 rows) — placeholders for planned features."), (
        "correction_labels                         0\ndrug_modalities                           0\ndrug_routes                               0\ndrug_stage_history                        0\nindication_biology_tags                   0\nmodel_validation_results                  0\n"
        "resolver_errors                           0\n"),
    ),
    ("Orphan", 4, (
        "Disconnected from the entity graph — not joined to anything that surfaces."), (
        "drug_target_pairs                       161\nagent_disagreements                      51\ndrug_development_timelines               45\nnext_gen_rankings                         7\n"),
    ),
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
        "One **Supabase Postgres** project is the single source of truth. The table count is "
        "genuinely fuzzy: the schema snapshot `migrations/v1_schema.sql` defines **140 tables**, "
        "but the live database has **drifted to ~167** (64 live tables aren't in the snapshot; "
        "37 snapshot tables aren't live). And that 167 overstates it — only **73 are actually "
        "*surfaced*** in the product; the rest are plumbing, audit logs, or dead. The full, "
        "honest inventory is below."
    )
    st.caption(
        "Table inventory is from the team's own catalog (the TABLEDB in "
        "`pages/meridian_workflow_map.html`); column details are quoted from v1_schema.sql."
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
        "for almost everything, RLS-enforced). Browser writes are confined to **workflow & "
        "feedback tables** — `submitted_intel`, `discovery_queue`, `research_queue`, "
        "`governance_violations` (resolve), and the review verdicts `kyle_reviews` / "
        "`correction_labels`; the only core-entity write is a single `drugs.partnership_verified` "
        "toggle. Never substantive entity data (see the **Present** stage for the full audit). "
        "Credentials load from env vars or repo dotfiles via `scripts/_common.py` — never hard-coded."
    )

    st.divider()
    st.subheader("Every table, by how alive it is")
    st.write(
        "The honest inventory — **all 167 tables, each listed once**, grouped by whether the "
        "product actually uses them. This is why \"how many tables?\" has a fuzzy answer: only "
        "**73 are surfaced**; the other ~94 are plumbing, dead, or empty. Counts below sum to "
        "the whole. Row counts are from the workflow-map snapshot."
    )
    _hdr = f"{'table':<36}{'rows':>7}\n" + "─" * 43 + "\n"
    for label, count, blurb, block in STORE_CATALOG:
        with st.expander(f"{label} — {count} tables"):
            st.caption(blurb)
            st.code(_hdr + block, language="text")

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


# ── Score stage — how facts become numbers ───────────────────────────────────
# 13 scripts in scripts/scoring/ turn stored facts into metrics, rankings, and a
# call list. Organized below by the BD QUESTION each score answers, not by file,
# because that's how the platform actually uses them. Every formula is quoted
# from the code with exact weights/thresholds. The one thing to keep straight:
# 12 of 13 are pure deterministic arithmetic — only bd_recommender.py calls an
# LLM, and only to write prose, never the number. Verified against the
# migration-baseline branch.

# Families of scorers, each framed as the question it answers. Each scorer entry:
# name (file), type tag, output table, a one-line purpose, and a formula block
# with the real weights. "type" is one of: deterministic | hybrid (math+Claude) |
# rules | curated.
SCORE_FAMILIES = [
    {
        "question": "How complete & trustworthy is our data?",
        "summary": (
            "Before ranking anything, the platform scores *itself* — how well-covered "
            "each company/area/drug is, and how much you should trust a given profile. "
            "These are the meta-scores that gate and prioritize everything else."
        ),
        "scorers": [
            {
                "name": "compute_coverage.py",
                "type": "deterministic",
                "output": "coverage_scores",
                "purpose": (
                    "How complete is a company/area across 9 data dimensions? A weighted "
                    "average where the two things that matter most — having a real source and "
                    "a filled-out profile — carry double weight."
                ),
                "formula": (
                    "overall = Σ(dim_score × weight) / Σ(weight)          # 0–100\n"
                    "\n"
                    "  dimension               weight   measures\n"
                    "  profile_completeness     2.0    % of expected company_profiles fields present\n"
                    "  source_coverage          2.0    % of confirmed score rows that carry a source_url\n"
                    "  enrichment_recency       1.5    profile age: <7d=100 ·<14d=90 ·<30d=70 ·<60d=40 ·else=10\n"
                    "  target_mapping           1.0    % of drugs with a primary drug_targets row\n"
                    "  confidence_coverage      1.0    % of score rows with a confidence_level\n"
                    "  ownership_coverage       1.0    % of licensed-in drugs with an ownership_edge\n"
                    "  molecule_intelligence    1.0    % of drugs with a molecule_intelligence row\n"
                    "  catalyst_coverage        1.0    % of active clinical drugs with a future catalyst\n"
                    "  deal_linkage             0.5    % of transactional edges linked to a deal_id"
                ),
            },
            {
                "name": "rescore_completeness.py",
                "type": "deterministic",
                "output": "company_profiles.completeness_score",
                "purpose": (
                    "A simpler 100-point report card on a single company profile, recomputed "
                    "from current DB state (no enrichment). Mirrors the enrichment scorer so a "
                    "profile can be graded without re-running the LLM."
                ),
                "formula": (
                    "score = sum of points earned                        # max 100\n"
                    "\n"
                    "  +20  platform_intelligence present\n"
                    "  +20  bd_intelligence present\n"
                    "  +15  drug_summary for every drug\n"
                    "  +10  key_data for every Phase 2+ drug      (auto +10 if none exist)\n"
                    "  +10  mechanism_detail present\n"
                    "  +10  at least one catalyst row carries a source_url\n"
                    "  +10  key_risk AND why_it_matters both present\n"
                    "  +5   overlap_rationale for every Direct drug (auto +5 if none exist)\n"
                    "\n"
                    "  grade:  strong ≥70 · partial ≥40 · thin <40"
                ),
            },
            {
                "name": "compute_trust_score.py",
                "type": "deterministic",
                "output": "drug_trust_scores",
                "purpose": (
                    "\"How much should you trust this drug card?\" Starts at 100 and *subtracts* "
                    "for every integrity problem — missing sources, dead URLs, open governance "
                    "violations. A transparent penalty model, so a low grade always has a reason."
                ),
                "formula": (
                    "score = 100 − penalties                             # then graded A–F\n"
                    "\n"
                    "  −15            no source_url\n"
                    "  −10            no company_display\n"
                    "  −10            no mechanism / target\n"
                    "  −20            no confirmed sources AND no trials\n"
                    "  −8             only unconfirmed sources\n"
                    "  −min(10, 3×n)  dead URLs\n"
                    "  −min(30,10×n)  unresolved governance violations\n"
                    "  −min(8,  2×n)  duplicate catalyst rows\n"
                    "  −min(12, 4×n)  unresolved value conflicts\n"
                    "  −6             no peer-reviewed backing\n"
                    "  −3             no independently-corroborated claim\n"
                    "\n"
                    "  grade:  A ≥90 · B ≥75 · C ≥60 · D ≥40 · F <40"
                ),
            },
            {
                "name": "compute_landscape_scores.py  +  compute_landscape_coverage.py",
                "type": "deterministic",
                "output": "competitive_landscapes.landscape_dependency_score",
                "purpose": (
                    "How completely is a competitive landscape (e.g. TED × IGF-1R) mapped? "
                    "Two near-twin implementations of the same weighted formula. Its real job "
                    "is the feedback loop: a low score reprioritizes enrichment (see below)."
                ),
                "formula": (
                    "LDS = 100 × ( 0.35·drug_coverage\n"
                    "            + 0.25·relationship_coverage\n"
                    "            + 0.20·catalyst_coverage\n"
                    "            + 0.15·source_validation\n"
                    "            − 0.05·staleness_penalty )              # clamped 0–100\n"
                    "\n"
                    "  each sub-score is a 0.0–1.0 ratio  (captured / expected)\n"
                    "\n"
                    "  ▸ feeds BACK into research_queue priority:\n"
                    "      LDS <60 → +15 boost · 60–75 → +8 boost · ≥75 → none"
                ),
            },
            {
                "name": "update_area_knowledge_counts.py",
                "type": "deterministic",
                "output": "area_knowledge.drug_count_*",
                "purpose": (
                    "A small backfill utility — counts the drugs in each area so the dashboard "
                    "can show \"N programs.\" Not a judgment score, just set cardinality."
                ),
                "formula": (
                    "drug_count_direct = distinct drugs on the area's target IDs\n"
                    "drug_count_total  = distinct drugs on  target IDs ∪ indication IDs\n"
                    "  (bispecific area is special-cased on modality)"
                ),
            },
        ],
    },
    {
        "question": "How competitive is this drug?",
        "summary": (
            "Per-drug positioning against Ailux's programs — the raw competitive signal that "
            "company- and deal-level scores are later built on top of."
        ),
        "scorers": [
            {
                "name": "patch_competitive_scores_null.py",
                "type": "deterministic",
                "output": "drug_competitive_scores.total_competition_score",
                "purpose": (
                    "The core 0–100 competitiveness score for a drug in a given context (TL1A, "
                    "FcRn, TED…). A sum of five components — what it hits, what it treats, how "
                    "it's built, how far along, and where — capped to 0–100."
                ),
                "formula": (
                    "total = clamp(0..100,\n"
                    "        target_overlap      # Direct 30 · Adjacent 20 · Same-space 10 · Watch 5\n"
                    "      + indication_overlap  # Direct 30 · Adjacent 22 · Same-space 15 · Watch 10\n"
                    "      + modality_match      # bispecific 17–20 · mAb 10–15 · small-mol 6–10\n"
                    "      + stage_proximity     # Ph3/Appr 10 · Ph2 8 · Ph1 5 · Preclin 2 · Term 0\n"
                    "      − geography_penalty ) # China-only −15 · China-first −10 · else 0\n"
                    "\n"
                    "  (the TL1A context uses tuned target & modality weights)"
                ),
            },
            {
                "name": "add_competitive_relevance.py",
                "type": "curated",
                "output": "drug_area_scores.competitive_relevance",
                "purpose": (
                    "A hand-curated strategic-importance tag that deliberately separates *stage* "
                    "from *impact* — a failed Phase 3 drug can still be a 'monitor', a preclinical "
                    "disruptor can be 'very_high'. Seeds the TED × IGF-1R landscape by hand."
                ),
                "formula": (
                    "competitive_relevance ∈ {very_high, high, medium, low, monitor}\n"
                    "  NOT computed — curated per drug×area, each with a relevance_rationale.\n"
                    "  very_high = near-term disruptor (PDUFA/BLA imminent)\n"
                    "  monitor   = failed / discontinued, watch only"
                ),
            },
            {
                "name": "write_ranking_snapshots.py",
                "type": "deterministic",
                "output": "next_gen_rankings",
                "purpose": (
                    "Blends competitiveness with clinical stage into one composite, sorts, and "
                    "writes a dated leaderboard snapshot per area so the dashboard can show "
                    "movement over time."
                ),
                "formula": (
                    "composite = 0.7·total_competition_score + 0.3·stage_weight\n"
                    "  stage_weight: approved 10 · Ph3 9 · Ph2 8 · Ph1 6 · preclin 1 · term 0\n"
                    "  (Ailux's own drugs use a separate dev-stage scale)\n"
                    "  → ranked descending, snapshotted daily"
                ),
            },
        ],
    },
    {
        "question": "How valuable is this company to us?",
        "summary": (
            "Rolls every drug, deal, and data-coverage signal up to one 0–100 number per "
            "company — the input the deal-action scorers consume."
        ),
        "scorers": [
            {
                "name": "compute_strategic_value.py",
                "type": "deterministic",
                "output": "companies.strategic_value_score",
                "purpose": (
                    "How strategically valuable is a whole company to Ailux? Four components — "
                    "pipeline fit, deal activity, how well we've covered them, and what kind of "
                    "company they are — capped at 100. Feeds bd_recommender and acquisition_scorer."
                ),
                "formula": (
                    "score = min(100,\n"
                    "        pipeline_relevance  # Direct 30 · Adjacent 15 · Same 5  + min(2×drugs,10); cap 40\n"
                    "      + deal_activity       # recent <12mo +10 · >$1B +10 · $500M–1B +5;       cap 20\n"
                    "      + coverage            # enriched 20 · active 12 · else 5\n"
                    "      + strategic_context ) # large-pharma 20 · mid-cap 15 · biotech 12 · small 8"
                ),
            },
        ],
    },
    {
        "question": "Should we do a deal — and how urgently?",
        "summary": (
            "The business end of the chain: turn all the above into a ranked call list with a "
            "concrete 'when to reach out.' This is what a BD person actually acts on."
        ),
        "scorers": [
            {
                "name": "acquisition_scorer.py",
                "type": "deterministic",
                "output": "company_strategic_views (acquisition_target)",
                "purpose": (
                    "Scores every company 0–100 on \"how acquirable, right now\" across five "
                    "evenly-weighted dimensions, then maps the number to a BD rating. Carries "
                    "the hard governance overrides."
                ),
                "formula": (
                    "total = D1 + D2 + D3 + D4 + D5                       # 0–100, 20 pts each\n"
                    "\n"
                    "  D1 strategic overlap  Direct+Ph2/3 20 · Direct+Ph1 15 · Adjacent 8 · Same 5\n"
                    "  D2 timing urgency     Ph2/3 readout <12mo 20 · Ph1 <12mo 15 · 13–24mo 10 · none 5\n"
                    "  D3 platform value     bispecific platform 20 · FcRn engineering 15 · single bsAb 12\n"
                    "  D4 deal feasibility   biotech 18 · subsidiary 18 · mid-cap 12 · large-pharma 5 (+history)\n"
                    "  D5 Ailux window       mono vs our bsAb +20 · both bsAb +8 · partnered-w-rival −10\n"
                    "\n"
                    "  rating:  CALL NOW ≥85 · PRIORITY ≥70 · WATCH ≥55 · MONITOR ≥40 · HOLD <40\n"
                    "  overrides: AbbVie ≤69 until ABBV-701 readout (Oct 2026) · acquired→HOLD · Ailux excluded"
                ),
            },
            {
                "name": "bd_recommender.py",
                "type": "hybrid (math + Claude Haiku)",
                "output": "bd_recommendations",
                "purpose": (
                    "Ranks the top companies on five BD dimensions and sets a call urgency — then, "
                    "and only then, hands the result to Claude Haiku to write a 3-sentence deal "
                    "opener. The score is math; the LLM only writes the prose."
                ),
                "formula": (
                    "total = strategic_value   # strategic_value_score/100 × 30        (0–30)\n"
                    "      + pipeline_urgency   # readout/PDUFA <12mo 8 ea · P0 +2;     cap 25\n"
                    "      + deal_appetite      # each deal <18mo +5 · any >$500M +10;  cap 20\n"
                    "      + partnership_fit    # licensing 15 · partnership 12 · acq-target 10 · competitive 3\n"
                    "      + coverage_gap       # 10 × (1 − coverage/100)               (0–10)\n"
                    "\n"
                    "  call_urgency:  this_week ≥60 · this_month ≥45 · this_quarter ≥30 · watch <30\n"
                    "  → Claude Haiku then writes the deal opener (prose only — not the score)\n"
                    "  override: AbbVie → watch"
                ),
            },
        ],
    },
    {
        "question": "Does this company collide with our own pipeline?",
        "summary": (
            "A different question entirely — not 'how good are they' but 'does their pipeline "
            "cannibalize, or complement, one of Ailux's three programs.' Pure rules, no math."
        ),
        "scorers": [
            {
                "name": "portfolio_conflict_scorer.py",
                "type": "rules",
                "output": "company_portfolio_conflicts",
                "purpose": (
                    "Classifies each company against Ailux's three bispecifics by matching target "
                    "strings — flagging direct cannibalization (HARD), partial overlap (SOFT), or a "
                    "pairing opportunity (COMBO). Categorical, not numeric."
                ),
                "formula": (
                    "per Ailux asset — ALX001 (TL1A×IL-23) · ALX002 (CD19×BCMA) · ALX005 (FcRn×Alb):\n"
                    "\n"
                    "  HARD   competitor bispecific hits BOTH arms      → cannibalization risk\n"
                    "  SOFT   competitor mono on ONE arm               → partial overlap\n"
                    "  COMBO  advanced asset on the complementary arm  → pairing opportunity\n"
                    "  CLEAR  no overlap\n"
                    "\n"
                    "  pure target-string match + active-stage filter — no math, no LLM"
                ),
            },
        ],
    },
]

# Every place a score crosses from a number into a decision — pulled into one
# reference so the cutoffs aren't buried in each scorer.
SCORE_THRESHOLDS = [
    ("Acquisition rating", "acquisition_scorer.py",
     "CALL NOW ≥85 · PRIORITY ≥70 · WATCH ≥55 · MONITOR ≥40 · HOLD <40"),
    ("BD call urgency", "bd_recommender.py",
     "this_week ≥60 · this_month ≥45 · this_quarter ≥30 · watch <30"),
    ("Trust grade", "compute_trust_score.py",
     "A ≥90 · B ≥75 · C ≥60 · D ≥40 · F <40"),
    ("Completeness grade", "rescore_completeness.py",
     "strong ≥70 · partial ≥40 · thin <40"),
    ("Landscape → enrichment", "compute_landscape_scores.py",
     "LDS <60 → +15 queue boost · 60–75 → +8 · ≥75 → none"),
]


# Genuine scoring that does NOT live in scripts/scoring/ — found by sweeping the
# rest of scripts/. These are real ranking/grading systems the dedicated library
# doesn't contain, so the Score page would be incomplete without them.
SCORE_OUTSIDE = [
    {
        "name": "enrichment/research_intelligence.py",
        "type": "deterministic",
        "output": "research_queue (priority_score, completeness_score, completeness_tier)",
        "purpose": (
            "The platform's \"guided research\" brain — scores how completely each entity is "
            "known across 6 research stages, then turns the gap into an urgency score that "
            "decides what gets enriched next. The biggest scorer outside the library."
        ),
        "formula": (
            "completeness = Σ(stage_score × weight) / 100         # 0–100, then tiered\n"
            "\n"
            "  stage                    weight\n"
            "  entity_discovery          10\n"
            "  drug_mapping              15\n"
            "  trial_intelligence        20\n"
            "  catalyst_engine           15\n"
            "  strategic_position        25   ← heaviest\n"
            "  deal_intelligence         15\n"
            "  tier:  thin <40 · partial 40–69 · strong ≥70\n"
            "\n"
            "priority = clamp(0..200,\n"
            "        (100 − completeness)            # the less we know, the more urgent\n"
            "      + 30  if strategic entity\n"
            "      + 20  if any research trigger fired  + 10×extra triggers (cap +40)\n"
            "      + 15  thin tier · +10 stale profile · +10 passed catalyst )"
        ),
    },
    {
        "name": "pipeline/nodes/score_completeness.py",
        "type": "deterministic",
        "output": "company_profiles.completeness_score",
        "purpose": (
            "The post-enrichment completeness rubric, run as a pipeline node right after a "
            "company is enriched. Same 100-point rubric as `rescore_completeness.py` in the "
            "library — that one is the standalone re-run, this one runs inline."
        ),
        "formula": (
            "score = sum of points earned                        # max 100\n"
            "  +20 platform_intelligence · +20 bd_intelligence · +15 drug_summary (all)\n"
            "  +10 key_data (Ph2+) · +10 mechanism_detail · +10 catalyst w/ source_url\n"
            "  +10 key_risk + why_it_matters · +5 overlap_rationale (Direct)\n"
            "  tier:  thin <40 · partial 40–69 · strong ≥70"
        ),
    },
    {
        "name": "intelligence/signal_monitor.py",
        "type": "deterministic",
        "output": "signals.relevance_score",
        "purpose": (
            "The Tier-1 gate (also noted on the Validate page): scores every incoming news "
            "signal 0–10 on how relevant it is, and anything ≥8 gets queued for enrichment. "
            "A lightweight keyword heuristic — no LLM."
        ),
        "formula": (
            "relevance = Σ point hits, capped at 10             # ≥8 → queue for enrichment\n"
            "  +3 company-name match · +3 drug-name match · +3 area/target match\n"
            "  +2 stage/phase detected · +2 trial-registry match · +2 alias match\n"
            "  +1 generic category keyword"
        ),
    },
    {
        "name": "seed/seed_indication_priorities.py",
        "type": "curated",
        "output": "indication_priority_scores",
        "purpose": (
            "Ranks diseases by strategic priority for Ailux. A real weighted formula, but "
            "its four inputs are hand-assigned 1–10 with written rationale — so it's a "
            "curated strategic judgment, not a computed-from-data score."
        ),
        "formula": (
            "composite = 0.30·unmet_need\n"
            "          + 0.30·ailux_fit\n"
            "          + 0.20·competitive_white_space\n"
            "          + 0.20·(biologic_failure_rate / 10)\n"
            "  each component hand-assigned 1–10 with rationale\n"
            "  → sorted into indication_priority_rank"
        ),
    },
]


def render_mm_score() -> None:
    st.button("← Back", on_click=go_to, args=("mental_model",))

    st.title("3 · Score — facts into numbers & rankings")
    st.write(
        "Thirteen scripts in `scripts/scoring/` turn stored facts into metrics, rankings, "
        "and a call list. Read them as a **chain**: first the platform scores how complete "
        "*its own data* is, then how competitive each drug is, then how valuable each "
        "company is, and finally — built on all of that — whether and how urgently to do a "
        "deal. A separate scorer asks the inverse question: does a company *collide* with "
        "Ailux's own pipeline."
    )
    st.caption(
        "Formulas below are quoted from the code with exact weights. Verified against the "
        "current branch — paths may shift as the scripts/pipeline/ migration lands."
    )

    st.divider()
    st.info(
        "**The math is AI-free — but the inputs aren't.** 12 of the 13 scorers in "
        "`scripts/scoring/` are plain **deterministic arithmetic** — transparent weighted "
        "sums you could reproduce by hand. Only `bd_recommender.py` calls Claude (Haiku), "
        "and only to write the 3-sentence deal *opener* — the score that ranks the company "
        "is still math.\n\n"
        "The catch: the **values those formulas run on** — a drug's `overlap` "
        "(Direct / Adjacent / Same-Space) and its `relevance_score` 1–10 — are themselves "
        "**assigned by Claude during enrichment** (`company_enrichment.py`). So the "
        "arithmetic is deterministic, but it's computing on model-judged inputs. If a score "
        "looks wrong, it's either the formula, or the LLM-graded input feeding it."
    )

    st.subheader("The chain — what feeds what")
    st.markdown(
        "- **completeness / trust** gate everything — thin data is scored thin first.\n"
        "- `drug_competitive_scores` → roll up into → `companies.strategic_value_score`.\n"
        "- `strategic_value` + competitive scores → feed → **`acquisition_scorer`** and "
        "**`bd_recommender`** (the call list).\n"
        "- and a loop back to Ingest: a low **landscape score** *raises the enrichment "
        "priority* for that area — Score doesn't just consume data, it decides what gets "
        "collected next."
    )

    for fam in SCORE_FAMILIES:
        st.divider()
        st.subheader(fam["question"])
        st.write(fam["summary"])
        for s in fam["scorers"]:
            with st.expander(f"{s['name']}  ·  {s['type']}  →  {s['output']}"):
                st.write(s["purpose"])
                st.markdown("**Formula**")
                st.code(s["formula"], language="text")

    st.divider()
    st.subheader("Scoring that lives outside `scripts/scoring/`")
    st.write(
        "The library above isn't the whole story. Sweeping the rest of `scripts/` turned up "
        "four more genuine scorers — including the platform's research-prioritization brain, "
        "which is arguably the most consequential score of all."
    )
    for s in SCORE_OUTSIDE:
        with st.expander(f"{s['name']}  ·  {s['type']}  →  {s['output']}"):
            st.write(s["purpose"])
            st.markdown("**Formula**")
            st.code(s["formula"], language="text")

    st.warning(
        "**Heads-up: two of these scores have a *second* implementation.** "
        "`weekend_sprint.py` writes `companies.strategic_value_score`, "
        "`drug_competitive_scores`, and `coverage_scores` through its **own inline formulas "
        "with different weights** — e.g. its strategic value is just max-overlap + max-stage "
        "(Direct 30 + approved 20), where `compute_strategic_value.py` uses four components; "
        "its competitive score uses Direct = 40 where `patch_competitive_scores_null.py` uses "
        "Direct = 30. The two paths write the **same columns**, so the number a row ends up "
        "with depends on which ran last. Treat the `scripts/scoring/` versions as the fuller, "
        "canonical ones; the sprint's are simpler in-line variants."
    )

    st.divider()
    st.subheader("Score → action — every cutoff in one place")
    st.caption("Where a raw number flips into a decision or a label.")
    for label, src, cuts in SCORE_THRESHOLDS:
        st.markdown(f"**{label}**  ·  `{src}`")
        st.code(cuts, language="text")

    st.divider()
    st.info(
        "**The one loop worth remembering.** Scoring isn't a dead end — the landscape "
        "dependency score feeds *backward* into `research_queue` priority (LDS <60 → +15). "
        "Low-confidence areas get scored, and that low score is exactly what pushes them "
        "to the front of the **Ingest** queue. The platform uses its own scores to decide "
        "where to look next."
    )


# ── Interpret stage — reading data, writing intelligence ─────────────────────
# The layer that reads stored facts and produces something new — prose, strategy,
# or graph structure. The honest split that shapes this page: GENERATIVE work
# (narratives + enrichment) calls Claude; RELATIONSHIP work (identity + graph) is
# pure deterministic matching and SQL with NO model. Both "interpret" the data,
# but only one half is AI. Every LLM call routes through scripts/ai/client.py —
# there are no raw anthropic calls anywhere else. Verified against the
# migration-baseline branch.

# What the one AI client provides — the single chokepoint every Claude call uses.
INTERPRET_CLIENT = [
    ("run_text(cfg, prompt)", "Free-text generation. Optionally turns on the "
     "`web_search_20250305` tool (cfg.web_search_max_uses) for live look-ups."),
    ("run_json(cfg, prompt)", "Structured extraction — strips markdown fences, repairs/retries "
     "on bad JSON, flags truncation."),
    ("PromptConfig", "Immutable per-prompt descriptor: name, system prompt, model, max_tokens, "
     "temperature, web_search_max_uses."),
    ("token_usage() / _cost()", "Module-level token accumulator + pricing, so every run's cost "
     "is tracked. Sonnet 4.6 = $3/$15 per 1M · Haiku 4.5 = $0.8/$4."),
]

# The interpretation layers, grouped by KIND. "llm" drives the badge and framing:
# True = generative Claude work, False = deterministic (no model).
INTERPRET_GROUPS = [
    {
        "label": "A · Narrative & briefing writing",
        "llm": True,
        "blurb": (
            "The generative core — reads structured intelligence and writes prose for a human "
            "to read. Every writer here is **fail-closed**: it reasons only from supplied, cited "
            "facts and drops anything it can't ground."
        ),
        "files": [
            {
                "name": "intelligence/write_meridian.py",
                "type": "Claude · Sonnet (2-pass)",
                "output": "meridian_issues",
                "desc": (
                    "The daily BD briefing. Pass 1 (`run_json`) builds an editorial plan — thesis, "
                    "signal vs noise, connections, BD implications; Pass 2 (`run_text`) writes the "
                    "full HTML from that plan. A pre-write gate drops facts with fabricated source "
                    "URLs; a post-write audit flags prose that contradicts the `drugs` table → "
                    "`governance_violations`. Also folds in reader feedback from `meridian_feedback`."
                ),
            },
            {
                "name": "intelligence/research.py",
                "type": "Claude · Sonnet + Haiku",
                "output": "intel · deals · catalysts",
                "desc": (
                    "Reads RSS + article full-text and extracts structured intel records, deals, "
                    "and catalysts (Haiku also pulls PK/PD from abstracts). Straddles **Ingest** — "
                    "it both fetches the news and interprets it into rows."
                ),
            },
            {
                "name": "intelligence/strategic_brief.py",
                "type": "Claude · Sonnet",
                "output": "entity_narratives (target/business)",
                "desc": (
                    "A ranked BD brief for a mechanism area — Call now / Watch / Timing-gated — "
                    "reasoning only from numbered, trust-graded facts, explicitly discounting "
                    "low-trust assets."
                ),
            },
            {
                "name": "narrative/generate_landscape_briefing.py",
                "type": "Claude · Opus (multi-call)",
                "output": "landscape_briefings",
                "desc": (
                    "Area-level strategic synthesis in several Opus calls — classifies companies by "
                    "BD archetype (likely acquirer, platform, emerging threat…), finds whitespace, "
                    "extracts financials, and writes BD recommendations."
                ),
            },
            {
                "name": "narrative/narrative_gen.py",
                "type": "Claude · Sonnet (or offline template)",
                "output": "entity_narratives (+ provenance)",
                "desc": (
                    "The narrative engine the others build on. Turns a structured 'recipe' into "
                    "cited atoms — every claim must match a source or it's dropped. Has a no-API "
                    "`template` composer mode for offline runs."
                ),
            },
            {
                "name": "narrative/patient_narrative.py · landscape_narrative.py",
                "type": "Claude · Sonnet",
                "output": "entity_narratives",
                "desc": (
                    "Turn `indication_patient_intelligence` stats and per-area landscape data into "
                    "cited prose via the engine above."
                ),
            },
            {
                "name": "narrative/generate_area_narratives.py · generate_patient_briefs.py",
                "type": "orchestrator (no direct LLM)",
                "output": "→ shells out per entity",
                "desc": (
                    "Batch drivers — they don't call Claude themselves, they loop over entities and "
                    "invoke `narrative_gen.py` / `patient_narrative.py` for each."
                ),
            },
        ],
    },
    {
        "label": "B · Enrichment — reads data, writes synthesized strategy",
        "llm": True,
        "blurb": (
            "The biggest LLM layer. Each script reads a drug or company's stored context and has "
            "Claude synthesize new analytical fields — strictly grounded ('expected', 'estimated', "
            "never invented). ⚠ This group **spans Ingest and Interpret**: the Ingest page also "
            "lists `enrichment/*` under 'AI enrichment', because these scripts both pull facts in "
            "*and* interpret them. It's the same code, doing both jobs."
        ),
        "files": [
            {
                "name": "enrichment/company_enrichment.py",
                "type": "Claude · Sonnet  (flagship)",
                "output": "company_profiles · company_partnerships · drug_area_scores",
                "desc": (
                    "The largest enrichment script. Synthesizes 15+ profile fields — platform_summary, "
                    "bd_summary, key_risk, why_it_matters, vs_ailux, strategic_behavior, risk_summary. "
                    "Crucially, it also assigns the `overlap` / `relevance_score` / `confidence_level` "
                    "that the **Score** stage later does deterministic math on."
                ),
            },
            {
                "name": "enrichment/drug_enrichment.py",
                "type": "Claude · Sonnet",
                "output": "drugs · enrichment_run · enriched_field_log",
                "desc": (
                    "Per-drug synthesis: bd_angle, risk summary, vs-Ailux positioning, competitive "
                    "threat. Logs old values to `enriched_field_log` for an audit trail."
                ),
            },
            {
                "name": "enrichment/drug_intelligence_researcher.py",
                "type": "Claude · Sonnet (8k tokens)",
                "output": "drug_intelligence_qa · drug_clinical_benchmarks · drug_development_timelines",
                "desc": (
                    "The deep dive — answers a 100-question rubric across 8 domains (molecule, "
                    "clinical, patient, competitive, regulatory, commercial, BD, timing) and extracts "
                    "benchmarks and milestone dates from the answers."
                ),
            },
            {
                "name": "enrichment/molecule_enrichment.py",
                "type": "Claude · Sonnet",
                "output": "molecule_intelligence",
                "desc": "Structures molecule-level detail — modality, format, formulation, CMC/manufacturing notes.",
            },
            {
                "name": "enrichment/backfill_bd_angle.py · quick_profiles_enrich.py",
                "type": "Claude · Sonnet",
                "output": "company_profiles (.bd_angle)",
                "desc": (
                    "Targeted top-ups — a focused 2–3 sentence BD angle for profiles missing one, and "
                    "a fast pass to fill sparse company profiles."
                ),
            },
        ],
    },
    {
        "label": "C · Identity resolution & dedup  —  no LLM",
        "llm": False,
        "blurb": (
            "Resolves messy name strings to canonical IDs. **Pure deterministic matching — no model.** "
            "These scripts load credentials with `require_anthropic=False`; they literally don't have "
            "an API key. Fuzzy near-misses are *flagged for human review*, never auto-merged."
        ),
        "files": [
            {
                "name": "identity/identity_resolution.py",
                "type": "deterministic",
                "output": "canonical_drugs · drug_aliases · identity_audit_log",
                "desc": (
                    "Drug-name → canonical_drug_id, 4-step cascade: exact alias (conf 100) → "
                    "normalized (90) → fuzzy ≥0.85 (70, FLAGGED, makes a NEW id — never auto-merges) → "
                    "brand-new id. Every decision is logged for audit."
                ),
            },
            {
                "name": "identity/company_identity_resolver.py",
                "type": "deterministic",
                "output": "identity_audit_log",
                "desc": (
                    "Company-name → company_id: alias → name/ticker → fuzzy (flagged) → not-found. "
                    "Unknown companies are **never auto-created** — logged as not-found instead, which "
                    "is safer than hallucinating an org."
                ),
            },
            {
                "name": "identity/identity_health_check.py · trial_id_audit.py",
                "type": "deterministic (audit)",
                "output": "reports / flags",
                "desc": "Audit utilities — surface duplicate/ambiguous identities and trial-ID mismatches for review.",
            },
        ],
    },
    {
        "label": "D · Graph / relationship materialization  —  no LLM",
        "llm": False,
        "blurb": (
            "Builds the traversable relationship graph from the normalized tables. **Pure SQL "
            "inference — no model, no 'reasoning'.** A drug that targets T and treats I *implies* "
            "T addresses I; two drugs on the same target *imply* they compete. Idempotent inserts, "
            "fully reproducible."
        ),
        "files": [
            {
                "name": "graph/materialize_structural_edges.py",
                "type": "deterministic (SQL)",
                "output": "entity_edges",
                "desc": "Materializes TREATS (drug→indication), ADDRESSES (target→indication), DEVELOPED_BY (drug→company).",
            },
            {
                "name": "graph/materialize_deal_edges.py",
                "type": "deterministic (SQL)",
                "output": "entity_edges (HAS_PARTNERSHIP)",
                "desc": "Turns deal records into partnership edges.",
            },
            {
                "name": "graph/seed_company_edges.py · seed_partnership_edges.py · seed_patient_edges.py",
                "type": "deterministic (rules)",
                "output": "entity_edges (COMPETES_WITH, …)",
                "desc": (
                    "Seed high-confidence competitive / partnership / shared-patient-population edges "
                    "via rules — same target → COMPETES_WITH, etc."
                ),
            },
            {
                "name": "graph/coverage_gap_finder.py",
                "type": "deterministic",
                "output": "research_queue",
                "desc": (
                    "The inverse of writing intelligence — finds what's *missing* (low-coverage drugs, "
                    "absent molecules/indications/catalysts, phantom companies) and queues it. Feeds "
                    "back into the **Ingest** priority loop."
                ),
            },
        ],
    },
]


def render_mm_interpret() -> None:
    st.button("← Back", on_click=go_to, args=("mental_model",))

    st.title("4 · Interpret — facts into prose & strategy")
    st.write(
        "Where stored facts get **read and turned into something new** — a briefing, a strategic "
        "judgment, or a graph edge. Read it as two halves that both 'interpret' the data but work "
        "completely differently: a **generative** half where Claude writes narratives and enrichment "
        "synthesis, and a **deterministic** half where plain code materializes the relationship "
        "graph and resolves identities — with no model involved at all."
    )
    st.caption(
        "Verified against the current branch — paths may shift as the scripts/pipeline/ migration "
        "lands."
    )

    st.divider()
    st.info(
        "**Only half of 'interpretation' is AI.** The narratives (group A) and enrichment "
        "(group B) call Claude. But **identity resolution (C) and the relationship graph (D) "
        "use no LLM whatsoever** — they're string matching and SQL inference. The tell: those "
        "scripts load credentials with `require_anthropic=False`, so they don't even hold an API "
        "key. Fuzzy matches there are *flagged for a human*, never auto-merged — the system would "
        "rather leave a gap than guess."
    )

    st.subheader("One client, every call")
    st.write(
        "Every Claude call in the platform routes through **`scripts/ai/client.py`** — there are "
        "no raw `anthropic` calls anywhere else. That one chokepoint is what makes model choice, "
        "web search, cost tracking, and JSON repair uniform:"
    )
    for sig, note in INTERPRET_CLIENT:
        st.markdown(f"`{sig}`")
        st.caption(note)

    for group in INTERPRET_GROUPS:
        st.divider()
        st.subheader(group["label"])
        badge = "🤖 Claude-generated" if group["llm"] else "⚙️ Deterministic · no LLM"
        st.caption(badge)
        st.write(group["blurb"])
        for f in group["files"]:
            with st.expander(f"{f['name']}  ·  {f['type']}  →  {f['output']}"):
                st.write(f["desc"])

    st.divider()
    st.info(
        "**The discipline that ties it together: fail-closed grounding.** The generative side "
        "never free-associates — Meridian drops fabricated source URLs before writing and audits "
        "its own draft against the database after; the narrative engine drops any claim it can't "
        "match to a source. The deterministic side refuses to guess — unresolved identities are "
        "flagged, not merged. In both halves, the safe failure is a *gap*, which the **Validate** "
        "stage then surfaces for a human."
    )


# ── Present stage — the surfaces you actually look at ────────────────────────
# Three distinct UIs, often confused for one. (1) index.html is the live
# production dashboard — a ~33k-line vanilla-JS SPA. (2) pages/*.html is a mix of
# live mini-apps and static generated documents. (3) this Streamlit app explains
# the system itself. The honest headline: the browser holds NO scoring or
# business math — every number is pre-computed upstream and stored; the frontend
# only reads, formats, and writes a few workflow/feedback rows. Verified by
# auditing index.html + pages/*.html on the migration-baseline branch.

# Everything index.html is allowed to write. All workflow/feedback tables — never
# substantive entity data. (The 3 "deletes" a naive grep finds are JS Set/Map
# .delete() on in-memory UI state, not DB deletes — the browser issues none.)
PRESENT_WRITES = [
    ("governance_violations", "update",
     "Click **Resolve** on a data-quality flag in the Ontology Audit tab (sets resolved=true)."),
    ("discovery_queue", "update",
     "Approve / reject a discovery candidate — including the bulk \"approve ≥80 confidence\" action."),
    ("discovery_queue", "insert",
     "**Send to Discovery Queue** — promote a reviewed submitted-intel item into the queue."),
    ("submitted_intel", "insert",
     "Submit a URL or pasted text via the Intel Submission modal."),
    ("submitted_intel", "update",
     "Approve / reject / mark-imported a submitted-intel item in the review panel."),
    ("drugs.partnership_verified", "update",
     "Inline toggle confirming/denying a partner relationship — the **only** core-entity "
     "write, and it's a single boolean, not substantive data."),
    ("research_queue", "update",
     "**Research Now** on an entity — manually queue it for batch research (sets assigned_status, next_best_action)."),
]

# Per-view breakdown of index.html. Each view: what's LIVE (a (label, source-table)
# tuple, rendered from a DB query each load) vs STATIC (hardcoded in the file).
# Tables verified by grepping index.html's .from()/.select() calls — note the live
# DB has drifted past migrations/v1_schema.sql (e.g. discovery_queue, news_articles
# exist live but aren't in the snapshot), so the HTML, not the schema, is the oracle.
PRESENT_VIEWS = [
    {
        "name": "Home",
        "summary": "The landing tab — the most DB-heavy view; nearly everything is live.",
        "live": [
            ("**BD Today** — the next 5 catalysts inside 30 days", "catalyst_calendar (→ catalysts fallback)"),
            ("**Indication Priority — Top 7** leaderboard with composite scores", "indication_priority_scores"),
            ("**Today's Meridian** — the full daily briefing, inline", "meridian_issues.body_html"),
            ("**90-Day Catalyst Calendar**, grouped by month, P0–P3 tagged", "catalyst_calendar"),
            ("**Asset Intelligence** — company spotlight cards", "company_profiles · company_strategic_views · deals"),
            ("**Health dot + \"fresh data\" banner** (polled on an interval)", "system_status · pipeline_runs"),
        ],
        "static": [
            "ET / PT / CN clocks, page title, section layout",
            "The fallback Top-7 list (gMG, CIDP, CD, UC…) shown **only** when the live table is empty",
            "Scoring-methodology blurbs and tooltips",
        ],
    },
    {
        "name": "The Meridian (daily issue)",
        "summary": "A tab that embeds the briefing rather than querying for it.",
        "live": [],
        "static": [
            "An **iframe embedding the generated briefing** (`pages/meridian_today.html`, produced "
            "by `write_meridian.py`) — a frozen document. The *live* copy of the same briefing is "
            "the one on Home, read from `meridian_issues`.",
        ],
    },
    {
        "name": "Drugs to Know",
        "summary": "A filterable catalog grid — one big live query, static chrome.",
        "live": [
            ("**The whole drug grid** — stage, modality, target, class/MOA, indication, "
             "differentiation, Ailux angle, key risk", "drugs  (catalog_category ≠ null)"),
        ],
        "static": [
            "Filter dropdown options — TA, indication, target, modality, stage, company",
            "Grid column headers & layout; the removed-drugs / undo panel",
        ],
    },
    {
        "name": "Industry Insights",
        "summary": "A live merged news feed sitting on top of a hardcoded archive.",
        "live": [
            ("A merged **intelligence feed** — headlines, deals, signals, news, sorted by date",
             "intel · intel_areas · competitive_signals · deals · news_articles · companies"),
        ],
        "static": [
            "Left filter-panel options — source, date, relevance, event type, area/target, company",
            "A large **hardcoded historical archive** (Dec 2025 – Apr 2026 snapshot) below the live feed",
        ],
    },
    {
        "name": "Ontology Audit",
        "summary": "A data-governance console — live counts & violations, static taxonomy.",
        "live": [
            ("**Open governance violations** (rule, table, row, detected_at)", "governance_violations (resolved=false)"),
            ("**Live row counts** per table", "drugs · companies · trials · deals · catalysts · intel · entity_edges"),
            ("**Taxonomy lookup data** for the layer cards", "indications · targets · target_pairs · modalities"),
            ("**Legacy area coverage** check", "legacy_area_ontology_map"),
        ],
        "static": [
            "The 7-layer taxonomy descriptions (Therapeutic Area → Delivery)",
            "Relationship-matrix labels, migration-planner copy, the admin sub-tab structure",
        ],
    },
]

# The seven program tabs are one machine pointed at seven targets. Documented once.
PRESENT_PROGRAM_TEMPLATE = {
    "note": "Each program tab runs the same loaders (loadAreaPI / Intel / Catalysts / Deals / "
            "BDActivity) filtered to one target_id — only the filter and the hardcoded copy differ.",
    "live": [
        ("**Program Intelligence table** — companies & drugs in the area (stage, mechanism, financials)",
         "drug_targets (→ legacy drug_areas) · drugs · companies"),
        ("**Intel feed** for the program", "intel · intel_areas"),
        ("**Catalyst calendar** — readouts & events", "catalysts · catalyst_calendar"),
        ("**Deals & BD activity**", "deals · company_bd_momentum"),
        ("**Strategic BD position** cards", "ailux_bd_context"),
    ],
    "static": [
        "The target's **biology deep-dive** prose (e.g. \"TL1A is a TNF-superfamily cytokine…\")",
        "Ailux **mechanism differentiators** (4 boxes) and **estimated deal valuation** ranges",
        "Treatment ladders, market-size projections, China-molecule cards, BD takeaways",
        "Section headings, the left pill-button labels, gridjs column definitions",
    ],
}

# (display target, area badge, what's unique to this one)
PRESENT_PROGRAMS = [
    ("TL1A × IL-23p19", "IBD", "the richest static set — biology DD, IBD treatment eras, "
     "market $30.7B→$41.9B, China-molecule cards, and the Bispecific-Race gridjs grid (← drug_area_scores)"),
    ("TSLP × IL-33", "Respiratory", "alarmin-strategy thesis"),
    ("IL-4Rα × TSLP", "Type 2", "atopy-platform thesis, IL-4Rα × IL-33 cross-talk"),
    ("IL-4Rα × OX40L", "Atopic dermatitis", "OX40 co-stimulation biology"),
    ("IGF1R × TSHR", "Thyroid eye disease", "orbit-fibrosis biology"),
    ("FcRn bispecific", "Autoimmune (CIDP, gMG, SLE)", "half-life-extension thesis"),
    ("BCMA × CD19 × CD3", "Immune reset", "triple-engager mechanism"),
]

# pages/*.html — each with its own live/static split and any writes it makes.
PRESENT_PAGES = [
    {
        "name": "pages/intelligence.html",
        "kind": "live · read-only",
        "note": "A standalone research-review tool — reads only, no writes.",
        "live": [
            ("Ranked research queue + full entity profiles (drug / trial / catalyst / deal / intel detail)",
             "research_queue · company_profiles · drugs · trials · catalysts · deals · intel · intel_companies"),
        ],
        "static": ["Layout, labels, the sidebar / detail-panel split"],
    },
    {
        "name": "pages/meridian_feedback_ui.html",
        "kind": "live · read + WRITE",
        "note": "The human-label capture that feeds the fine-tuning corpus (the Y/N/U/S review tool).",
        "live": [
            ("The enriched-field review queue — old value → new value, confidence, provenance",
             "enriched_field_log · kyle_reviews · drugs · companies"),
        ],
        "static": ["The Y / N / U / S key bindings, layout"],
        "writes": "`kyle_reviews` (verdicts) · `correction_labels` (your corrected values)",
    },
    {
        "name": "pages/meridian_today.html",
        "kind": "static · generated  (+1 write)",
        "note": "This is where the `meridian_feedback` write actually lives — NOT index.html.",
        "live": [],
        "static": [
            "The full daily briefing — frozen HTML written by `write_meridian.py` and committed to "
            "Pages. Loads no `data/*.json` and inits no Supabase client.",
        ],
        "writes": "`meridian_feedback` — a single reader like/dislike + note, POSTed via **raw REST** "
                  "(not the JS client, which is why a `createClient` grep misses it)",
    },
    {
        "name": "pages/meridian_atlas.html",
        "kind": "static · document",
        "live": [],
        "static": ["A knowledge-graph SVG — assets, companies, indications, targets, and their edges. No DB."],
    },
    {
        "name": "pages/meridian_strategic_lens.html",
        "kind": "static · document",
        "live": [],
        "static": ["A TL1A competitive-landscape SVG — assets by stage, ownership/licence arrows. No DB."],
    },
    {
        "name": "pages/meridian_workflow_map.html",
        "kind": "static · document",
        "live": [],
        "static": ["A system-topology map of ~200 tables with producer/consumer scripts and row counts "
                   "— from an embedded snapshot, not live queries."],
    },
]


def render_mm_present() -> None:
    st.button("← Back", on_click=go_to, args=("mental_model",))

    st.title("5 · Present — what you actually look at")
    st.write(
        "Three separate surfaces, easy to mistake for one. **`index.html`** is the real "
        "production dashboard — a large single-page app that reads live from the database. "
        "**`pages/*.html`** is a mix: a couple of live mini-apps plus several static, generated "
        "documents. And **this Streamlit app** is a third thing entirely — it doesn't show BD "
        "data, it explains the system you're reading about right now."
    )
    st.caption(
        "Verified by auditing index.html and pages/*.html on the current branch — line counts "
        "and table lists may drift as the UI evolves."
    )

    st.divider()
    st.info(
        "**The browser does no thinking.** There is **zero scoring or business math** in the "
        "frontend — every score, rank, and metric is computed upstream (the Score / Interpret "
        "stages) and stored; the JS only *reads, formats, sorts, and filters* what's already "
        "there. And it's **not purely read-only** — but the handful of writes it makes go only "
        "to **workflow & feedback tables** (queues, review verdicts), never to substantive "
        "entity data. The anon key + row-level security enforce exactly that boundary."
    )

    st.divider()
    st.subheader("① `index.html` — the live production dashboard")
    st.markdown(
        "- **~33,000 lines of vanilla JS** (no React/Vue) — `gridjs` for sortable tables, "
        "`supabase-js` for data, nothing else.\n"
        "- **A dozen views**: Home + seven target programs (TL1A, TSLP, the two IL-4Rα pairs, "
        "IGF1R×TSHR, FcRn, BCMA×CD19×CD3) + The Meridian, Drugs-to-Know, Industry Insights, "
        "Ontology Audit. (A 'Market' tab was retired — `tab-stocks-removed`.) Client-side "
        "`switchTab()` routing; entity-detail modals.\n"
        "- **Reads ~81 tables directly** with the **anon key** (RLS-enforced) — almost all raw "
        "tables, not views. It displays pre-computed scores verbatim."
    )
    st.markdown("**What the browser is allowed to write** — workflow & feedback only:")
    for table, op, trigger in PRESENT_WRITES:
        st.markdown(f"`{table}`  ·  *{op}*")
        st.caption(trigger)
    st.markdown(
        "**One build artifact:** it `fetch()`es `data/navigator_lookup.json` — a pre-computed "
        "`target→drugs` / `indication→drugs` map built by `scripts/build/build_navigator_lookup.py` "
        "— purely to make the navigator tree's drug filtering O(1). It's an optimization; the page "
        "falls back to string-match filtering if the file is missing."
    )

    st.divider()
    st.subheader("What each view actually shows — live vs baked-in")
    st.caption(
        "🟢 LIVE = fetched from the database on load · 🔵 STATIC = hardcoded in the file. "
        "Expand a view to see the split; everything's collapsed so it isn't a wall of text."
    )

    def _ls(live, static):
        if live:
            st.markdown("🟢 **LIVE** — pulled from the database")
            for label, src in live:
                st.markdown(f"- {label}" + (f"  ←  `{src}`" if src else ""))
        if static:
            if live:
                st.write("")
            st.markdown("🔵 **STATIC** — baked into the page")
            for s in static:
                st.markdown(f"- {s}")

    for v in PRESENT_VIEWS:
        with st.expander(v["name"]):
            if v.get("summary"):
                st.caption(v["summary"])
            _ls(v["live"], v["static"])

    with st.expander("The seven program tabs  ·  one template, seven targets"):
        st.caption(PRESENT_PROGRAM_TEMPLATE["note"])
        _ls(PRESENT_PROGRAM_TEMPLATE["live"], PRESENT_PROGRAM_TEMPLATE["static"])
        st.markdown("**The seven, by target** — only the filter + hardcoded copy differ:")
        for name, area, unique in PRESENT_PROGRAMS:
            st.markdown(f"- **{name}** · *{area}* — {unique}")

    st.divider()
    st.subheader("② `pages/*.html` — mini-apps & generated documents")
    st.write(
        "Only **two** load the Supabase client; the rest are static documents. Watch the writes "
        "(✏️) — this is where `meridian_feedback`, `kyle_reviews`, and `correction_labels` "
        "actually get written, *not* from index.html."
    )
    for p in PRESENT_PAGES:
        with st.expander(f"{p['name']}  ·  {p['kind']}"):
            if p.get("note"):
                st.caption(p["note"])
            _ls(p.get("live", []), p.get("static", []))
            if p.get("writes"):
                st.markdown(f"✏️ **Writes:** {p['writes']}")

    st.divider()
    st.subheader("③ This Streamlit app — the system explaining itself")
    st.write(
        "`dashboard/app.py` (what you're in now) is the odd one out: it shows **no BD data**. "
        "It's a documentation surface — the GitHub Workflows map, the state graphs, and this "
        "Mental Model. Think of it as the platform's own operating manual, not a view of the "
        "intelligence it produces."
    )

    st.divider()
    st.info(
        "**The loop closes here.** The few things the dashboard *does* write — a submitted URL, "
        "a discovery-queue verdict, a \"Research Now\" click, a field review — don't change the "
        "intelligence directly. They drop rows into the **queues** (`submitted_intel`, "
        "`discovery_queue`, `research_queue`, `kyle_reviews`) that the **Ingest** and "
        "**Interpret** stages pick up next. The human looking at Present is, quietly, an input "
        "back into the top of the pipeline."
    )


# Custom per-stage renderers; stages without one fall back to the generic stub.
MM_STAGE_RENDERERS = {
    "ingest": render_mm_ingest,
    "store": render_mm_store,
    "score": render_mm_score,
    "interpret": render_mm_interpret,
    "present": render_mm_present,
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
