"""
Graphviz DOT generators — all derived from parsed ground truth, none hand-drawn.

  * chain_map_dot()      — the workflow_run dependency graph (who triggers whom)
  * workflow_flow_dot()  — one workflow: triggers → job/steps → entrypoint scripts
"""
from __future__ import annotations

import html

from .model import Workflow

# shared palette (light fills so it reads on Streamlit's white canvas)
_TRIGGER = ('shape=box, style="rounded,filled", fillcolor="#fde9c8", color="#d99a3b", '
            'fontcolor="#111827"')
_WF = ('shape=box, style="rounded,filled", fillcolor="#bcd4f6", color="#3567b5", '
       'fontcolor="#111827"')
_SCRIPT = ('shape=box, style="filled", fillcolor="#e7eef7", color="#5b6b7d", '
           'fontcolor="#111827"')
_BAD = ('shape=box, style="filled", fillcolor="#fbdada", color="#c0392b", '
        'fontcolor="#7b1f17"')
_CADENCE_FILL = {
    "chain": "#bcd4f6", "daily": "#d2f2dc", "weekly": "#e7dcf7",
    "monthly": "#f7e6c8", "interval": "#cdeef0", "manual": "#e4e8ee",
    "ci": "#fbe3ef", "other": "#e4e8ee",
}


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _node_id(name: str) -> str:
    return "n_" + "".join(c if c.isalnum() else "_" for c in name)


def chain_map_dot(workflows) -> str:
    """workflow_run edges between workflows, keyed by the `name:` field."""
    by_name = {wf.name: wf for wf in workflows}
    # Only show nodes involved in a chain (as source or target) to keep it legible.
    involved: set[str] = set()
    edges: list[tuple[str, str]] = []
    for wf in workflows:
        for upstream in wf.after_workflows:
            edges.append((upstream, wf.name))
            involved.add(upstream)
            involved.add(wf.name)

    lines = [
        "digraph chain {",
        '  rankdir=LR; bgcolor="transparent"; fontname="Helvetica";',
        '  node [fontname="Helvetica", fontsize=11, margin="0.18,0.1"];',
        '  edge [color="#2f9e63", arrowsize=0.8, penwidth=1.4];',
    ]
    for name in sorted(involved):
        wf = by_name.get(name)
        if wf:
            fill = _CADENCE_FILL.get(wf.cadence, "#bcd4f6")
            sched = wf.crons[0] if wf.crons else "via trigger"
            label = f"{name}\\n{_esc(sched)}"
            lines.append(
                f'  {_node_id(name)} [label="{label}", shape=box, '
                f'style="rounded,filled", fillcolor="{fill}", color="#3567b5", '
                f'fontcolor="#111827"];')
        else:
            # named in a workflow_run but no matching workflow file = broken link
            lines.append(
                f'  {_node_id(name)} [label="{_esc(name)}\\n(no matching workflow!)", {_BAD}];')
    for up, down in edges:
        lines.append(f"  {_node_id(up)} -> {_node_id(down)};")
    lines.append("}")
    return "\n".join(lines)


def workflow_flow_dot(wf: Workflow) -> str:
    lines = [
        "digraph wf {",
        '  rankdir=LR; bgcolor="transparent"; fontname="Helvetica";',
        '  node [fontname="Helvetica", fontsize=11, margin="0.16,0.1"];',
        '  edge [color="#5b6b7d", arrowsize=0.8];',
    ]
    # --- trigger nodes ---
    trig_ids = []
    for t in wf.triggers:
        if t == "schedule" and wf.crons:
            lbl = "schedule\\n" + _esc(" · ".join(wf.crons))
        elif t == "workflow_run":
            lbl = "workflow_run\\nafter " + _esc(", ".join(wf.after_workflows))
        else:
            lbl = _esc(t)
        nid = _node_id("trig_" + t)
        trig_ids.append(nid)
        lines.append(f'  {nid} [label="{lbl}", {_TRIGGER}];')

    wf_id = _node_id("wf_" + wf.name)
    fill = _CADENCE_FILL.get(wf.cadence, "#bcd4f6")
    lines.append(f'  {wf_id} [label="{_esc(wf.name)}\\n({wf.cadence})", '
                 f'shape=box, style="rounded,filled,bold", fillcolor="{fill}", '
                 f'color="#3567b5", fontcolor="#111827"];')
    for tid in trig_ids:
        lines.append(f"  {tid} -> {wf_id};")

    # --- entrypoint scripts in invocation order ---
    prev = wf_id
    idx = 0
    for ep in wf.all_entrypoints:
        idx += 1
        nid = _node_id(f"ep_{idx}")
        style = _SCRIPT if ep.exists else _BAD
        tag = "" if ep.exists else "\\n(missing!)"
        loc = f"\\n{ep.loc} LOC" if ep.loc else ""
        lines.append(f'  {nid} [label="{_esc(ep.path or ep.raw)}{loc}{tag}", {style}];')
        lines.append(f"  {prev} -> {nid};")
        prev = nid

    if idx == 0:
        nid = _node_id("noscript")
        lines.append(f'  {nid} [label="no python entrypoint\\n(uses action / shell only)", {_SCRIPT}];')
        lines.append(f"  {wf_id} -> {nid};")
    lines.append("}")
    return "\n".join(lines)


def db_core_governance_dot(tables) -> str:
    """Core tables, their designated Writer (green = correct path), and any
    ad-hoc writers that bypass it (red = governance gap)."""
    from .db import CORE_TABLES, ARCHIVE_HINTS

    def is_arch(p):
        return any(h in p for h in ARCHIVE_HINTS)

    by_name = {t.name: t for t in tables}
    lines = [
        "digraph db {",
        '  rankdir=LR; bgcolor="transparent"; fontname="Helvetica";',
        '  node [fontname="Helvetica", fontsize=11, margin="0.16,0.1"];',
    ]
    for name, (writer_file, cls) in CORE_TABLES.items():
        t = by_name.get(name)
        if not t:
            continue
        tid = _node_id("tbl_" + name)
        rdrs = len(t.reader_files)
        lines.append(f'  {tid} [label="{name}\\n{rdrs} reader files", shape=cylinder, '
                     f'style=filled, fillcolor="#dbe9fb", color="#3567b5", fontcolor="#111827"];')
        wid = _node_id("wr_" + name)
        lines.append(f'  {wid} [label="{cls}\\n{writer_file}", shape=box, '
                     f'style="rounded,filled", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"];')
        lines.append(f'  {wid} -> {tid} [color="#2f9e63", penwidth=1.6, label="  sole writer"];')
        active = [r for r in t.writers
                  if writer_file not in r.file and "database/" not in r.file and not is_arch(r.file)]
        if active:
            bid = _node_id("byp_" + name)
            nfiles = len({r.file for r in active})
            lines.append(f'  {bid} [label="{nfiles} ad-hoc writer file(s)\\n({len(active)} write calls)", '
                         f'shape=box, style="filled", fillcolor="#fbdada", color="#c0392b", fontcolor="#7b1f17"];')
            lines.append(f'  {bid} -> {tid} [color="#c0392b", style=dashed, label="  bypass"];')
    lines.append("}")
    return "\n".join(lines)
