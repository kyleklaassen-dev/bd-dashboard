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

from pipelines import ABSTRACT_FETCHER, EVIDENCE_COLLECTORS, PIPELINES

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
    st.title("🧬 Github Workflows")
    st.caption(
        "Pick a workflow to see exactly what runs, in what order, "
        "and what each file is responsible for."
    )
    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader(ABSTRACT_FETCHER["workflow_name"])
        st.caption(ABSTRACT_FETCHER["schedule"])
        st.write(ABSTRACT_FETCHER["summary"])
        st.button(
            ABSTRACT_FETCHER["workflow_name"],
            key="btn_abstract_fetcher",
            type="primary",
            width="stretch",
            on_click=go_to,
            args=(ABSTRACT_FETCHER["key"],),
        )

    with col2:
        st.subheader(EVIDENCE_COLLECTORS["workflow_name"])
        st.caption(EVIDENCE_COLLECTORS["schedule"])
        st.write(EVIDENCE_COLLECTORS["summary"])
        st.button(
            EVIDENCE_COLLECTORS["workflow_name"],
            key="btn_evidence_collectors",
            type="primary",
            width="stretch",
            on_click=go_to,
            args=(EVIDENCE_COLLECTORS["key"],),
        )


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
    st.subheader("File-by-file, in order")

    for phase in pipeline["phases"]:
        st.markdown(f"#### {phase['label']}")
        st.caption(phase["note"])

        for group in phase["groups"]:
            if len(group) > 1:
                st.markdown("**Run in parallel:**")
            for item in group:
                st.markdown(f"`{item['file']}`")
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
