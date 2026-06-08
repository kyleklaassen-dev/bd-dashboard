"""
PipelineState for the daily Meridian Issue writer (intelligence/write_meridian.py).

Threads fetched context, the two-pass LLM artifacts (editorial plan + draft),
and publish/wrap-up bookkeeping through the compiled StateGraph.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MeridianState:
    today: str = ""

    # ── Fetched context (load_context) ──────────────────────────────────────
    intel:                    list = field(default_factory=list)
    deals:                    list = field(default_factory=list)
    catalysts:                list = field(default_factory=list)
    catalyst_calendar_events: list = field(default_factory=list)
    bd_priority_data:         dict = field(default_factory=dict)
    drugs:                    dict = field(default_factory=dict)
    companies:                dict = field(default_factory=dict)
    ailux_positions:          list = field(default_factory=list)
    recent_issues:            list = field(default_factory=list)
    company_signals:          list = field(default_factory=list)
    trials:                   list = field(default_factory=list)
    graph_active_in:          dict = field(default_factory=dict)
    graph_targets:            dict = field(default_factory=dict)
    graph_competes:           list = field(default_factory=list)

    # ── Content blocks (build_blocks) ───────────────────────────────────────
    blocks: dict = field(default_factory=dict)

    # ── Pass 1 — editorial plan (generate_plan) ─────────────────────────────
    plan:                Any  = None
    plan_block:          str  = ""
    plan_company_ids:    list = field(default_factory=list)
    content_fingerprint: Any  = None

    # ── Pass 2 — draft (generate_draft) / placeholder ───────────────────────
    html: str = ""

    # ── Bookkeeping ──────────────────────────────────────────────────────────
    errors:          list = field(default_factory=list)
    nodes_completed: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def mark_complete(self, node_name: str) -> None:
        self.nodes_completed.append(node_name)

    def add_error(self, node_name: str, msg: str) -> None:
        self.errors.append(f"[{node_name}] {msg}")
