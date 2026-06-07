"""
ResearchPipelineState — shared state object for the intelligence audit pipeline.

Mirrors DrugPipelineState but is scoped to entity-level research scoring.
No LLM calls — this is a pure data pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ResearchPipelineState:
    # ── Inputs ──────────────────────────────────────────────────────────────
    entity_id: str
    area_id: str
    dry_run: bool = False

    # ── Context (populated by load_context node) ─────────────────────────────
    ctx: dict = field(default_factory=dict)

    # ── Scoring (populated by score node) ────────────────────────────────────
    score_result: dict = field(default_factory=dict)

    # ── Triggers (populated by triggers node) ────────────────────────────────
    triggers: list = field(default_factory=list)

    # ── Action + priority (populated by action + priority nodes) ─────────────
    next_action: str = ""
    priority_score: int = 0
    priority_reason: str = ""

    # ── Pipeline bookkeeping ─────────────────────────────────────────────────
    errors: list = field(default_factory=list)
    nodes_completed: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def mark_complete(self, node_name: str) -> None:
        self.nodes_completed.append(node_name)

    def add_error(self, node_name: str, msg: str) -> None:
        self.errors.append(f"[{node_name}] {msg}")
