"""
Meridian Weekend Pipelines — explainer dashboard.

Two buttons on the home page, one per weekend GitHub Actions workflow.
Each leads to a page that shows, in order, which files the pipeline's
entrypoint touches (including which steps run in parallel) and a
plain-language sentence describing what each file does.

Run with:
    streamlit run dashboard/app.py
"""
import streamlit as st

from pipelines import (
    ABSTRACT_FETCHER,
    EVIDENCE_COLLECTORS,
    PIPELINES,
    SCHOOL_WEEK_SPRINT,
    WEEKEND_SPRINT,
)

st.set_page_config(
    page_title="Github Workflows",
    page_icon="🧬",
    layout="centered",
)

if "view" not in st.session_state:
    st.session_state.view = "home"


def go_to(view_key: str) -> None:
    st.session_state.view = view_key


def render_home() -> None:
    st.markdown(
        """
        <style>
        button[kind="primary"] {
            background-color: #e4d9f7;
            border: 1px solid #b49ce8;
            color: #3a2c5c;
            min-height: 160px;
            white-space: pre-wrap;
            line-height: 1.5;
        }
        button[kind="primary"]:hover {
            background-color: #d6c5f3;
            border-color: #9d7fdc;
            color: #2c2047;
        }
        button[kind="primary"] strong {
            font-size: 1.3rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("🧬 Github Workflows")
    st.caption(
        "Pick a workflow to see exactly what runs, in what order, "
        "and what each file is responsible for."
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

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        workflow_card(ABSTRACT_FETCHER, "btn_abstract_fetcher")
    with col2:
        workflow_card(EVIDENCE_COLLECTORS, "btn_evidence_collectors")
    with col3:
        workflow_card(WEEKEND_SPRINT, "btn_weekend_sprint")
    with col4:
        workflow_card(SCHOOL_WEEK_SPRINT, "btn_school_week_sprint")


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


def main() -> None:
    view = st.session_state.view
    if view == "home":
        render_home()
    elif view in PIPELINES:
        render_pipeline_page(PIPELINES[view])
    else:
        st.session_state.view = "home"
        render_home()


main()
