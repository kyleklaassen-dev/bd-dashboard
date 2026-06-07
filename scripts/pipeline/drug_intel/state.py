"""
DrugIntelPipelineState — shared state for the drug intelligence researcher pipeline.

Covers the 100-question research run:
  load_drug → research_domains (per-domain Claude calls) → extract_benchmarks
                                                         → extract_timeline → store_all
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DrugIntelPipelineState:
    # ── Inputs ──────────────────────────────────────────────────────────────
    drug_id: str
    indication: str
    dry_run: bool = False
    verbose: bool = False
    domains_filter: Optional[list] = None

    # ── Drug record (populated by load_drug node) ────────────────────────────
    drug: dict = field(default_factory=dict)

    # ── Q&A (populated by research_domains node) ─────────────────────────────
    all_qa: list = field(default_factory=list)

    # ── Benchmarks + timeline (populated by extract nodes) ───────────────────
    benchmarks: list = field(default_factory=list)
    timeline: list = field(default_factory=list)

    # ── Results ──────────────────────────────────────────────────────────────
    qa_stored: int = 0
    benchmarks_stored: int = 0
    timeline_stored: int = 0

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
