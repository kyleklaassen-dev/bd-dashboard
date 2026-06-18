# Workflow Atlas

A read-only Streamlit lens over **this repo's real GitHub Actions workflows**.

It parses every file in `.github/workflows/*.yml` on the checked-out branch and
builds a faithful model — triggers, cron schedules, the `workflow_run` chain,
each `run:` step's Python entrypoint (resolved to a file, with its docstring and
line count) — then renders:

- **Overview** — counts by cadence and by data-lifecycle stage.
- **Workflow map** — the real `workflow_run` dependency graph (who triggers whom).
- **Mental model** — every workflow bucketed into the pipeline story
  (Ingest → Enrich → Resolve → Graph → Score → Validate → Publish → Monitor → Quality).
- **Per-workflow pages** — schedule, flow diagram, entrypoint docstrings, steps, raw YAML.
- **Audit** — mechanically-derived faults, flaws and improvement areas
  (broken script references, broken chain links, cron collisions, missing
  concurrency guards, dead dispatch-only workflows, shared entrypoints, timeout hygiene).

Nothing is hand-authored or executed — it's a pure static read, so it always
reflects the branch you launch it on and can flag where that branch is broken.

The design pattern (a Streamlit documentation surface for the pipelines) is
modeled on the dashboard in PR #21; the *content* is generated from ground truth
rather than curated by hand.

## Run

```bash
python3 -m venv .venv-atlas
.venv-atlas/bin/pip install -r workflow_atlas/requirements.txt
.venv-atlas/bin/streamlit run workflow_atlas/app.py
```

`graphviz` (the Python package) is optional — Streamlit's `graphviz_chart`
renders the DOT strings client-side, so only the DOT text is needed.

## Layout

```
workflow_atlas/
  app.py            Streamlit entry — routing + pages
  atlas/
    model.py        dataclasses (Workflow / Job / Step / Entrypoint)
    parse.py        YAML + entrypoint/docstring parsing, cadence classification
    graphs.py       Graphviz DOT generators (chain map, per-workflow flow)
    audit.py        fault/flaw/improvement findings
```
