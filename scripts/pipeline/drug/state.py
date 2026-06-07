"""
DrugPipelineState — shared state object threaded through the drug enrichment pipeline.

Mirrors pipeline/state.py but is scoped to drug-level enrichment.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class DrugPipelineState:
    # ── Inputs ──────────────────────────────────────────────────────────────
    drug_id: str
    dry_run: bool = False

    # ── Context (populated by load_context node) ─────────────────────────────
    ctx: dict = field(default_factory=dict)          # drug + company + targets + trials
    drug_name: str = ""
    coverage: int = 0
    missing_fields: list = field(default_factory=list)

    # ── LLM outputs (populated by synthesize node) ───────────────────────────
    prompt: str = ""
    llm_raw: dict = field(default_factory=dict)      # parsed JSON from Claude
    validated_data: dict = field(default_factory=dict)
    fields_to_write: dict = field(default_factory=dict)

    # ── Results ──────────────────────────────────────────────────────────────
    fields_written: int = 0
    coverage_before: int = 0
    coverage_after: int = 0
    enrichment_run_id: Optional[str] = None

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
