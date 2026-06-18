"""
Workflow Atlas — a Streamlit lens over THIS repo's real GitHub Actions.

Pattern borrowed from the Streamlit dashboard in PR #21 (wnkinc): a documentation
surface that explains, workflow by workflow, exactly what runs and in what order.
But every page here is generated from the live `.github/workflows/*.yml` on the
checked-out branch (parsed in `atlas/parse.py`) — nothing is hand-authored, so it
models main as it actually is and can flag where it's broken.

Run:  streamlit run workflow_atlas/app.py
"""
from __future__ import annotations

from collections import defaultdict

import streamlit as st

from atlas.audit import audit, summarize
from atlas.code import analyze, call_flow_dot, plain_flow_dot
from atlas.db import (db_audit, db_summary, load_tables, workflows_touching,
                      CORE_TABLES)
from atlas.graphs import chain_map_dot, db_core_governance_dot, workflow_flow_dot
from atlas.parse import load_workflows, name_index

st.set_page_config(page_title="Meridian Workflow Atlas", page_icon="🗺️", layout="wide")

# ── Workflow Atlas design system — one standardized type scale & rhythm ───────
#  H1 page title · H2 section (with divider) · H3 minor · body · caption.
#  Every page uses these same tokens so sizing stays consistent everywhere.
st.markdown("""
<style>
  .block-container { padding-top: 2.6rem; padding-bottom: 3rem; max-width: 1160px; }

  /* H1 — page title (one per page) */
  h1, [data-testid="stHeading"] h1 { font-size: 1.5rem !important; font-weight: 700 !important;
       line-height: 1.25 !important; margin: 0 0 .6rem !important; }

  /* H2 — section header; the page backbone. Clearly above body + a divider rule. */
  h2 { font-size: 1.12rem !important; font-weight: 650 !important; line-height: 1.3 !important;
       margin: 1.6rem 0 .55rem !important; padding-bottom: .28rem !important;
       border-bottom: 1px solid rgba(130,130,130,.20) !important; }

  /* H3 / H4 — minor headers */
  h3 { font-size: .98rem !important; font-weight: 600 !important; line-height: 1.3 !important; margin: .85rem 0 .3rem !important; }
  h4 { font-size: .9rem  !important; font-weight: 600 !important; line-height: 1.3 !important; margin: .6rem 0 .25rem !important; }

  /* Body */
  [data-testid="stMarkdownContainer"] p,
  [data-testid="stMarkdownContainer"] li { font-size: .9rem !important; line-height: 1.55 !important; margin: 0 0 .45rem !important; }
  [data-testid="stMarkdownContainer"] code { font-size: .84rem !important; padding: .04rem .3rem !important; }
  [data-testid="stCaptionContainer"] p { font-size: .8rem !important; line-height: 1.45 !important; margin: 0 0 .3rem !important; }

  /* Consistent vertical/horizontal rhythm */
  [data-testid="stVerticalBlock"] { gap: .6rem !important; }
  [data-testid="stHorizontalBlock"] { gap: 1rem !important; }
  hr { margin: .6rem 0 !important; }

  /* Metrics — value dominant, label quiet & uppercase (consistent everywhere) */
  [data-testid="stMetricValue"] { font-size: 1.45rem !important; font-weight: 700 !important; line-height: 1.1 !important; }
  [data-testid="stMetricLabel"] p { font-size: .74rem !important; text-transform: uppercase; letter-spacing: .02em; opacity: .72; }
  [data-testid="stMetricDelta"] { font-size: .72rem !important; }

  /* Buttons */
  .stButton button { padding: .26rem .6rem !important; }
  .stButton button p { font-size: .82rem !important; margin: 0 !important; line-height: 1.3 !important; }

  /* Expanders + inputs */
  [data-testid="stExpander"] summary p { font-size: .84rem !important; }
  [data-testid="stSidebar"] .stButton button p { font-size: .8rem !important; }
  [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { font-size: .82rem !important; }
  .stRadio label p, .stMultiSelect label p, .stTextInput label p { font-size: .82rem !important; }
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------------------------------- #
# Data (cached by Streamlit across reruns; parse layer is also lru_cached)
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def _data():
    wfs = list(load_workflows())
    return wfs, audit(wfs)


@st.cache_data(show_spinner=False)
def _db_data():
    tbls = list(load_tables())
    return tbls, db_audit(tbls)


WORKFLOWS, FINDINGS = _data()
BY_NAME = name_index(WORKFLOWS)
TABLES, DB_FINDINGS = _db_data()
TBL_INDEX = {t.name: t for t in TABLES}
DB_SEV = db_summary(DB_FINDINGS)

CADENCE_LABEL = {
    "chain": "🔗 Nightly chain", "daily": "🌅 Daily", "weekly": "📅 Weekly",
    "monthly": "🗓️ Monthly", "interval": "⏱️ Sub-daily interval",
    "manual": "🖐️ Manual", "ci": "✅ CI gate", "other": "❓ Other",
}
CADENCE_ORDER = ["chain", "daily", "interval", "weekly", "monthly", "manual", "ci", "other"]

# Map an entrypoint path to a lifecycle stage (the "mental model").
STAGE_BY_DIR = [
    ("meridian/ingestion", "Ingest"), ("integrations", "Ingest"),
    ("meridian/enrichment", "Enrich"), ("meridian/identity", "Resolve"),
    ("meridian/graph", "Graph"), ("meridian/scoring", "Score"),
    ("meridian/validation", "Validate"), ("meridian/products", "Publish"),
    ("meridian/ops", "Monitor"), ("maintenance", "Quality"), ("tests", "Quality"),
]
STAGE_ORDER = ["Ingest", "Enrich", "Resolve", "Graph", "Score", "Validate",
               "Publish", "Monitor", "Quality", "Other"]
STAGE_BLURB = {
    "Ingest": "Pull raw signal from the outside world (RSS, CT.gov, EDGAR, FDA, patents, APIs).",
    "Enrich": "Flesh out company / molecule records once they exist.",
    "Resolve": "Entity resolution, queue processing, identity linking.",
    "Graph": "Materialize and unify the relationship graph (edges, ownership, networks).",
    "Score": "Compute landscape scores, rankings, completeness, foresight.",
    "Validate": "Verify sources, content, edges, ground truth — the truth-keeping layer.",
    "Publish": "Generate the briefs, narratives, summaries and BD recommendations users read.",
    "Monitor": "Watch pipeline health and signals; alert on drift.",
    "Quality": "CI / regression gates that protect the codebase itself.",
    "Other": "Uncategorized.",
}


def stage_of(wf) -> str:
    counts: dict[str, int] = defaultdict(int)
    for ep in wf.all_entrypoints:
        p = ep.path or ""
        for frag, stage in STAGE_BY_DIR:
            if frag in p:
                counts[stage] += 1
                break
    if not counts:
        return "Quality" if wf.cadence == "ci" else "Other"
    return max(counts, key=counts.get)


def go(view: str):
    st.session_state["view"] = view


# --------------------------------------------------------------------------- #
# Sidebar navigation
# --------------------------------------------------------------------------- #
st.session_state.setdefault("view", "overview")
sev = summarize(FINDINGS)

with st.sidebar:
    st.markdown("## 🗺️ Workflow Atlas")
    st.caption(f"{len(WORKFLOWS)} workflows · live from `.github/workflows`")
    if st.button("📊 Overview", width="stretch"):
        go("overview")
    if st.button("⭐ Core example (Stock Prices)", width="stretch"):
        go("wf::stock-prices.yml")
    if st.button("🔗 Workflow map", width="stretch"):
        go("map")
    if st.button("🧭 Mental model", width="stretch"):
        go("mental")
    badge = f"  ·  🟥{sev['error']} 🟧{sev['warning']}"
    if st.button(f"🔎 Audit{badge}", width="stretch"):
        go("audit")

    st.divider()
    st.markdown("### 🗄️ Database")
    if st.button("🗄️ DB overview", width="stretch"):
        go("db")
    if st.button("🛡️ Governance map", width="stretch"):
        go("db_map")
    if st.button("📋 Tables", width="stretch"):
        go("db_tables")
    dbadge = f"  ·  🟥{DB_SEV['error']} 🟧{DB_SEV['warning']}"
    if st.button(f"🕳️ DB gaps{dbadge}", width="stretch"):
        go("db_gaps")

    st.divider()
    st.caption("Browse a workflow")
    cad_groups: dict[str, list] = defaultdict(list)
    for wf in WORKFLOWS:
        cad_groups[wf.cadence].append(wf)
    for cad in CADENCE_ORDER:
        group = sorted(cad_groups.get(cad, []), key=lambda w: w.filename)
        if not group:
            continue
        with st.expander(f"{CADENCE_LABEL[cad]} ({len(group)})"):
            for wf in group:
                if st.button(wf.name, key=f"nav_{wf.filename}", width="stretch"):
                    go(f"wf::{wf.filename}")


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #
def page_overview():
    st.title("Meridian Workflow Atlas")
    st.markdown(
        "A live, parsed model of every GitHub Actions workflow on this branch — "
        "what runs, when, in what order, and which scripts it calls. Built to make "
        "the repo's moving parts legible and to surface faults, overlaps and dead code."
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Workflows", len(WORKFLOWS))
    c2.metric("Scheduled (cron)", sum(1 for w in WORKFLOWS if w.crons))
    c3.metric("Chain links", sum(1 for w in WORKFLOWS if w.is_chain_link))
    c4.metric("Audit findings", len(FINDINGS),
              delta=f"{sev['error']} errors", delta_color="inverse")

    st.subheader("By cadence")
    cols = st.columns(4)
    cad_counts = defaultdict(int)
    for w in WORKFLOWS:
        cad_counts[w.cadence] += 1
    for i, cad in enumerate([c for c in CADENCE_ORDER if cad_counts[c]]):
        cols[i % 4].metric(CADENCE_LABEL[cad], cad_counts[cad])

    st.subheader("By lifecycle stage")
    stage_counts = defaultdict(int)
    for w in WORKFLOWS:
        stage_counts[stage_of(w)] += 1
    line = "  ·  ".join(f"**{s}** {stage_counts[s]}" for s in STAGE_ORDER if stage_counts[s])
    st.markdown(line)
    st.info("Use **Workflow map** to see the nightly chain, **Mental model** to walk "
            "the data lifecycle, or **Audit** to jump to the problems.")


def page_map():
    st.title("🔗 Workflow dependency map")
    st.caption("Edges are real `workflow_run` triggers (one workflow firing the next). "
               "Node color = cadence; the label shows the fallback cron.")
    chain_links = [w for w in WORKFLOWS if w.is_chain_link]
    if chain_links:
        st.graphviz_chart(chain_map_dot(WORKFLOWS), width="stretch")
    else:
        st.warning("No `workflow_run` chains found.")
    st.subheader("Chain links (event-triggered)")
    for wf in sorted(chain_links, key=lambda w: w.filename):
        st.markdown(f"- **{wf.name}** ← after _{', '.join(wf.after_workflows)}_ "
                    f"· fallback cron `{', '.join(wf.crons) or '—'}` "
                    f"· [`{wf.filename}`](#) ")


def page_mental():
    st.title("🧭 Mental model — the data lifecycle")
    st.markdown(
        "Each workflow is bucketed into a lifecycle stage by the directory its "
        "entrypoint scripts live in. This is the repo's pipeline told as a story: "
        "raw signal in on the left, published intelligence out on the right."
    )
    buckets: dict[str, list] = defaultdict(list)
    for wf in WORKFLOWS:
        buckets[stage_of(wf)].append(wf)
    for stage in STAGE_ORDER:
        group = sorted(buckets.get(stage, []), key=lambda w: w.filename)
        if not group:
            continue
        st.subheader(f"{stage} · {len(group)}")
        st.caption(STAGE_BLURB.get(stage, ""))
        for wf in group:
            cols = st.columns([3, 2, 5])
            if cols[0].button(wf.name, key=f"ms_{wf.filename}", width="stretch"):
                go(f"wf::{wf.filename}")
                st.rerun()
            cols[1].markdown(f"`{CADENCE_LABEL[wf.cadence].split(' ',1)[-1]}`")
            cols[2].caption(wf.cadence_detail or ", ".join(wf.triggers))
        st.divider()


SEV_ICON = {"error": "🟥", "warning": "🟧", "info": "🟦"}


def page_audit():
    st.title("🔎 Audit — faults, flaws & improvement areas")
    st.caption("Mechanical findings from the parsed YAML. A starting point for "
               "investigation, not a verdict.")
    c1, c2, c3 = st.columns(3)
    c1.metric("🟥 Errors", sev["error"])
    c2.metric("🟧 Warnings", sev["warning"])
    c3.metric("🟦 Info", sev["info"])

    cats = sorted({f.category for f in FINDINGS})
    chosen = st.multiselect("Filter by category", cats, default=cats)
    only_sev = st.multiselect("Severity", ["error", "warning", "info"],
                              default=["error", "warning", "info"])
    for f in FINDINGS:
        if f.category not in chosen or f.severity not in only_sev:
            continue
        with st.expander(f"{SEV_ICON[f.severity]} [{f.category}] {f.title}"):
            st.markdown(f.detail)
            if f.workflows:
                st.caption("Affected: " + ", ".join(f"`{w}`" for w in f.workflows))
                for w in f.workflows:
                    wf = next((x for x in WORKFLOWS if x.filename == w), None)
                    if wf and st.button(f"Open {wf.name}", key=f"au_{f.title}_{w}"):
                        go(f"wf::{w}")
                        st.rerun()


FEATURED = "stock-prices.yml"   # the fully-worked "core example"


def _yaml_header(raw: str) -> str:
    """Leading # comment block above `name:` — the author's own description."""
    out = []
    for ln in raw.splitlines():
        s = ln.strip()
        if s.startswith("#"):
            out.append(s.lstrip("# ").rstrip())
        elif s == "" and not out:
            continue
        else:
            break
    return " ".join(out).strip()


def page_workflow(filename: str):
    wf = next((w for w in WORKFLOWS if w.filename == filename), None)
    if not wf:
        st.error(f"Unknown workflow: {filename}")
        return
    scripts = [(ep, analyze(ep.path)) for ep in wf.all_entrypoints if ep.exists]
    mine = [f for f in FINDINGS if filename in f.workflows]

    st.title(wf.name)
    st.caption(f"`{wf.path}` · cadence: **{wf.cadence}**")
    if filename == FEATURED:
        st.success("⭐ **Core example.** This page is the worked template — every "
                   "section below answers one question you'd ask of *any* workflow. "
                   "The same layout is generated for all 52; this is the clearest one "
                   "to learn the shape from.")

    # ── 1. WHEN ──────────────────────────────────────────────────────────
    st.subheader("1 · When does it run?")
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"**Triggers**\n\n{', '.join(wf.triggers) or '—'}")
    c2.markdown(f"**Schedule**\n\n{wf.cadence_detail or '—'}")
    c3.markdown(f"**Timeout**\n\n{wf.timeout_minutes or 'default (360m)'} min")
    if wf.after_workflows:
        st.info("🔗 Triggered by completion of: " +
                ", ".join(f"**{u}**" for u in wf.after_workflows))
    if wf.concurrency_group:
        st.caption(f"✅ Safe from overlap — concurrency group `{wf.concurrency_group}` "
                   f"(cancel-in-progress: {wf.cancel_in_progress}).")
    else:
        st.caption("⚠️ No concurrency group — a slow run could overlap the next.")

    # ── 2. WHY ───────────────────────────────────────────────────────────
    # purpose stated once here; section 4 is the "how", not a repeat of the "what"
    st.subheader("2 · Why does it exist?")
    why = _yaml_header(wf.raw_yaml)
    if not why and scripts and scripts[0][1].doc:
        why = scripts[0][1].doc.strip()
    st.markdown(why or "_No description in the workflow file or entrypoint docstring._")

    # ── 3. WHAT FILES ────────────────────────────────────────────────────
    st.subheader("3 · What does it run?")
    if not scripts:
        st.caption("No python entrypoint — this workflow uses actions / shell only.")
    for ep, sc in scripts:
        kind = "self-contained" if sc.funcs else "thin wrapper"
        purpose = sc.doc.strip().splitlines()[0] if sc.doc else ""
        line = (f"- `{ep.path}` · **{ep.loc} lines**, {len(sc.funcs)} functions "
                f"({kind})")
        if purpose:
            line += f"  \n  ↳ {purpose}"
        st.markdown(line)

    # ── 4 & 5. HOW + FUNCTIONS ───────────────────────────────────────────
    for ep, sc in scripts:
        if sc.parse_error:
            st.warning(f"Could not parse `{ep.path}`: {sc.parse_error}")
            continue
        st.subheader(f"4 · How does `{ep.path.split('/')[-1]}` run?")
        st.markdown("**Step by step** — what it actually does, in order:")
        st.graphviz_chart(plain_flow_dot(sc, trigger=wf.cadence_detail), width="content")
        with st.expander("Technical call graph (function names)"):
            st.graphviz_chart(call_flow_dot(sc), width="content")

        st.subheader(f"5 · What does each function do? ({len(sc.funcs)})")
        for f in sc.funcs:
            sig = f"{f.name}({', '.join(f.args)})"
            io = []
            if f.writes:
                io.append("✍️ writes")
            if f.reads:
                io.append("👁️ reads")
            tag = (" · " + ", ".join(io)) if io else ""
            with st.expander(f"`{sig}`  ·  lines {f.lineno}–{f.end_lineno}{tag}"):
                st.markdown(f.doc or "_No docstring — purpose inferred from name/body._")
                if f.calls:
                    st.markdown("- **Calls:** " + ", ".join(f"`{c}()`" for c in f.calls))
                if f.writes:
                    st.markdown("- ✍️ **Writes:** " + ", ".join(f"`{t}`" for t in f.writes))
                if f.reads:
                    st.markdown("- 👁️ **Reads:** " + ", ".join(f"`{t}`" for t in f.reads))
                if f.writers_used:
                    st.markdown("- 🛡️ **Via Writer:** " + ", ".join(f"`{w}`" for w in f.writers_used))
                if not (f.calls or f.writes or f.reads):
                    st.caption("Pure helper — no table access or local calls.")

    # ── 6. DATA IN & OUT ─────────────────────────────────────────────────
    externals = sorted({e for _, sc in scripts for e in sc.externals})
    writes = sorted({t for _, sc in scripts for t in sc.all_writes})
    reads = sorted({t for _, sc in scripts for t in sc.all_reads if t not in writes})
    if externals or writes or reads:
        st.subheader("6 · What data goes in & out?")
        cols = st.columns(2)
        with cols[0]:
            st.markdown("**Inputs**")
            if externals:
                st.markdown("🌐 External: " + ", ".join(f"**{e}**" for e in externals))
            if reads:
                st.markdown("👁️ Reads tables: " + ", ".join(f"`{t}`" for t in reads))
            if not (externals or reads):
                st.caption("—")
        with cols[1]:
            st.markdown("**Outputs**")
            if writes:
                for t in writes:
                    core = " 🔑" if t in CORE_TABLES else ""
                    st.markdown(f"- ✍️ `{t}`{core}")
            else:
                st.caption("—")
        st.caption("Detected from the entrypoint files (imports, URLs, sb_*/Writer "
                   "calls). Logic inside imported modules isn't traced yet.")

    # ── 7. WHAT'S WRONG / RISKY ──────────────────────────────────────────
    st.subheader("7 · Anything wrong or risky?")
    if mine:
        for f in mine:
            st.markdown(f"{SEV_ICON[f.severity]} **{f.title}** — {f.detail}")
    else:
        st.caption("No audit findings for this workflow. ✅")

    # reference material
    with st.expander("Trigger / flow diagram"):
        st.graphviz_chart(workflow_flow_dot(wf), width="stretch")
    with st.expander("CI steps"):
        for job in wf.jobs:
            st.markdown(f"**job `{job.job_id}`** · runs-on `{job.runs_on}`")
            for s in job.steps:
                label = s.name or s.uses or "step"
                st.markdown(f"- {label}" + (f"  ·  `{s.uses}`" if s.uses else ""))
    with st.expander("Raw YAML"):
        st.code(wf.raw_yaml, language="yaml")


# --------------------------------------------------------------------------- #
# Database pages
# --------------------------------------------------------------------------- #
def page_db():
    st.title("🗄️ Database — the tables behind the pipelines")
    st.markdown(
        "Modeled the same way as the workflows: every table is parsed from "
        "`CREATE TABLE` in `migrations/`, cross-referenced with the `sb_*`/client "
        "calls in `src/` + `scripts/` (who writes it, who reads it), and overlaid "
        "with `docs/database/governance_table.md`."
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tables modeled", len(TABLES))
    c2.metric("Defined in SQL", sum(1 for t in TABLES if t.defined))
    c3.metric("Referenced in code", sum(1 for t in TABLES if t.refs))
    c4.metric("DB gaps", len(DB_FINDINGS),
              delta=f"{DB_SEV['error']} errors", delta_color="inverse")
    st.subheader("Core governed tables")
    for name, (wf_, cls) in CORE_TABLES.items():
        t = TBL_INDEX.get(name)
        if not t:
            continue
        cols = st.columns([2, 5])
        if cols[0].button(f"🔑 {name}", key=f"dbcore_{name}", width="stretch"):
            go(f"tbl::{name}"); st.rerun()
        cols[1].caption(f"writer **{cls}** · {len(t.writer_files)} writer / "
                        f"{len(t.reader_files)} reader files · "
                        f"{'✅ governed' if t.governance else '⚠️ no governance row'}")
    st.info("**Governance map** shows where writes bypass the Writers. "
            "**DB gaps** lists unused tables, write-only/read-only tables, and "
            "schema that isn't version-controlled.")


def page_db_map():
    st.title("🛡️ Core-table governance map")
    st.caption("Green = the designated Writer (the only sanctioned write path). "
               "Red dashed = active code that writes the core table directly, "
               "bypassing the Writer (a CLAUDE.md governance violation).")
    st.graphviz_chart(db_core_governance_dot(TABLES), width="stretch")
    bypass = [f for f in DB_FINDINGS if f.category == "Writer bypass"]
    for f in bypass:
        st.markdown(f"🟥 **{f.title}**")
        st.caption(f.detail)


def page_db_tables():
    st.title("📋 Tables")
    q = st.text_input("Filter tables", "").strip().lower()
    only = st.radio("Show", ["all", "core", "defined in SQL", "with gaps"],
                    horizontal=True)
    gap_tables = {tn for f in DB_FINDINGS for tn in f.tables}
    rows = []
    for t in TABLES:
        if q and q not in t.name:
            continue
        if only == "core" and not t.is_core:
            continue
        if only == "defined in SQL" and not t.defined:
            continue
        if only == "with gaps" and t.name not in gap_tables:
            continue
        rows.append(t)
    st.caption(f"{len(rows)} tables")
    for t in rows:
        cols = st.columns([3, 1, 1, 1, 2])
        tag = "🔑" if t.is_core else ("🗄️" if t.defined else "·")
        if cols[0].button(f"{tag} {t.name}", key=f"tbl_{t.name}", width="stretch"):
            go(f"tbl::{t.name}"); st.rerun()
        cols[1].caption(f"✍️ {len(t.writer_files)}")
        cols[2].caption(f"👁️ {len(t.reader_files)}")
        cols[3].caption("SQL ✓" if t.defined else "—")
        cols[4].caption("⚠️ gap" if t.name in gap_tables else "")


def page_table(name: str):
    t = TBL_INDEX.get(name)
    if not t:
        st.error(f"Unknown table: {name}")
        return
    st.title(f"🗄️ {name}")
    tags = []
    if t.is_core:
        tags.append("🔑 core governed")
    tags.append("defined in SQL ✓" if t.defined else "schema not in repo")
    st.caption(" · ".join(tags))

    if t.governance:
        g = t.governance
        st.subheader("Governance")
        st.markdown(f"- **Owner:** {g.get('owner','')}\n"
                    f"- **Sole writer:** {g.get('writer','')}\n"
                    f"- **Validation on write:** {g.get('validation','')}\n"
                    f"- **Source hierarchy:** {g.get('source_hierarchy','')}")

    c1, c2, c3 = st.columns(3)
    c1.metric("Writer files", len(t.writer_files))
    c2.metric("Reader files", len(t.reader_files))
    c3.metric("Columns (from SQL)", len(t.columns) or "—")

    mine = [f for f in DB_FINDINGS if name in f.tables]
    if mine:
        with st.expander(f"🕳️ {len(mine)} gap finding(s) for this table", expanded=True):
            for f in mine:
                icon = {"error": "🟥", "warning": "🟧", "info": "🟦"}[f.severity]
                st.markdown(f"{icon} **{f.title}** — {f.detail}")

    wfs = sorted(workflows_touching(t))
    if wfs:
        st.subheader("Workflows that touch it")
        st.markdown(", ".join(f"`{w}`" for w in wfs))

    st.subheader("Writers")
    if t.writers:
        for r in sorted(t.writers, key=lambda r: r.file):
            st.markdown(f"- `{r.file}:{r.line}` · `{r.func}()`")
    else:
        st.caption("No code writes this table.")

    st.subheader("Readers")
    if t.readers:
        for f in sorted(t.reader_files):
            st.markdown(f"- `{f}`")
    else:
        st.caption("No code reads this table.")

    if t.columns:
        with st.expander(f"Columns ({len(t.columns)})"):
            st.markdown(", ".join(f"`{c}`" for c in t.columns))
    if t.create_files:
        st.caption("Schema: " + ", ".join(f"`{f}`" for f in t.create_files))


def page_db_gaps():
    st.title("🕳️ Database gaps")
    st.caption("Mechanically-derived from schema + code. A starting point, not a verdict.")
    c1, c2, c3 = st.columns(3)
    c1.metric("🟥 Errors", DB_SEV["error"])
    c2.metric("🟧 Warnings", DB_SEV["warning"])
    c3.metric("🟦 Info", DB_SEV["info"])
    cats = sorted({f.category for f in DB_FINDINGS})
    chosen = st.multiselect("Category", cats, default=[c for c in cats
                            if c in ("Writer bypass", "Possibly unused table")])
    sevpick = st.multiselect("Severity", ["error", "warning", "info"],
                             default=["error", "warning"])
    icon = {"error": "🟥", "warning": "🟧", "info": "🟦"}
    shown = 0
    for f in DB_FINDINGS:
        if f.category not in chosen or f.severity not in sevpick:
            continue
        shown += 1
        with st.expander(f"{icon[f.severity]} [{f.category}] {f.title}"):
            st.markdown(f.detail)
            for tn in f.tables:
                if st.button(f"Open {tn}", key=f"gap_{f.title}_{tn}"):
                    go(f"tbl::{tn}"); st.rerun()
    if not shown:
        st.info("No findings match the current filter.")


# --------------------------------------------------------------------------- #
# Router
# --------------------------------------------------------------------------- #
view = st.session_state["view"]
if view == "overview":
    page_overview()
elif view == "map":
    page_map()
elif view == "mental":
    page_mental()
elif view == "audit":
    page_audit()
elif view == "db":
    page_db()
elif view == "db_map":
    page_db_map()
elif view == "db_tables":
    page_db_tables()
elif view == "db_gaps":
    page_db_gaps()
elif view.startswith("tbl::"):
    page_table(view[5:])
elif view.startswith("wf::"):
    page_workflow(view[4:])
else:
    page_overview()
