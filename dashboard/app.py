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

from pipelines import (
    ABSTRACT_FETCHER,
    EVIDENCE_COLLECTORS,
    FLYWHEEL_PHASE2,
    PIPELINES,
    SCHOOL_WEEK_SPRINT,
    TRIAL_AUDIT,
    WEEKEND_SPRINT,
)
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

    def workflow_card(pipeline: dict, key: str) -> None:
        workflow_filename = pipeline["workflow_file"].rsplit("/", 1)[-1]
        st.button(
            f"**{workflow_filename}**",
            key=key,
            type="primary",
            width="stretch",
            on_click=go_to,
            args=(pipeline["key"],),
        )

    cards = [
        (ABSTRACT_FETCHER, "btn_abstract_fetcher"),
        (EVIDENCE_COLLECTORS, "btn_evidence_collectors"),
        (WEEKEND_SPRINT, "btn_weekend_sprint"),
        (SCHOOL_WEEK_SPRINT, "btn_school_week_sprint"),
        (FLYWHEEL_PHASE2, "btn_flywheel_phase2"),
        (TRIAL_AUDIT, "btn_trial_audit"),
    ]
    cols = st.columns(3)
    for i, (pipeline, key) in enumerate(cards):
        with cols[i % 3]:
            workflow_card(pipeline, key)


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
                st.markdown(f"`{item[unit_key]}` &nbsp;·&nbsp; {item['lines']} lines")
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
