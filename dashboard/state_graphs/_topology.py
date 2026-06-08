"""
Live topology rendering for compiled LangGraph StateGraphs.

Rather than hand-drawing diagrams that can drift from the code (the way the
GitHub workflow `dot` strings are static descriptions), we import the actual
`build_*_graph()` function, compile it, and walk `app.get_graph()` to emit a
Graphviz DOT string. The diagram is always exactly what the code does.
"""
import importlib
import os
import sys

_HERE       = os.path.dirname(os.path.abspath(__file__))
_DASHBOARD  = os.path.dirname(_HERE)
_REPO_ROOT  = os.path.dirname(_DASHBOARD)
_SCRIPTS    = os.path.join(_REPO_ROOT, "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

_START_END_STYLE = 'shape=ellipse, fillcolor="#133a6b", color="#3a9bff", fontcolor="#ffffff"'


def build_app(module_path: str, builder_name: str):
    """Import `module_path` and call `builder_name()` to compile the graph."""
    module = importlib.import_module(module_path)
    builder = getattr(module, builder_name)
    return builder()


def topology_dot(app) -> str:
    """Render a compiled StateGraph's nodes/edges as a Graphviz DOT digraph.

    Solid edges are unconditional `add_edge` transitions; dashed amber edges
    are conditional branches added via `add_conditional_edges` (the routing
    functions documented separately on the page).
    """
    g = app.get_graph()

    lines = [
        "digraph {",
        "    rankdir=TB",
        '    bgcolor="transparent"',
        '    fontcolor="#e8ecf2"',
        "",
        "    node [",
        "        shape=box,",
        '        style="rounded,filled",',
        '        fillcolor="#cfe8ff",',
        '        color="#3a9bff",',
        '        fontcolor="#111827",',
        '        fontname="Helvetica",',
        "        fontsize=12,",
        '        margin="0.18,0.12"',
        "    ]",
        "",
        "    edge [",
        '        color="#5b6b7d",',
        '        fontcolor="#e8ecf2",',
        '        fontname="Helvetica",',
        "        fontsize=10,",
        "        arrowsize=0.8",
        "    ]",
        "",
    ]

    for node_id in g.nodes:
        if node_id == "__start__":
            lines.append(f'    "{node_id}" [label="START", {_START_END_STYLE}]')
        elif node_id == "__end__":
            lines.append(f'    "{node_id}" [label="END", {_START_END_STYLE}]')
        else:
            lines.append(f'    "{node_id}" [label="{node_id}"]')

    lines.append("")

    for edge in g.edges:
        if edge.conditional:
            attrs = ' [style=dashed, color="#e8a33d"]'
        else:
            attrs = ""
        lines.append(f'    "{edge.source}" -> "{edge.target}"{attrs}')

    lines.append("}")
    return "\n".join(lines)
