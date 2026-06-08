"""
ResearchNewsState — shared state object for the nightly news-extraction pipeline
(intelligence/research.py phases 1-5: fetch -> filter -> dedup -> enrich
full-text -> extract intel -> write).

Mirrors PipelineState (company enrichment) and DrugPipelineState — inter-step
data gets names and types instead of being threaded as loose lists/dicts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ResearchNewsState:
    # ── Inputs ────────────────────────────────────────────────────────────
    hours_back: int = 48
    dry_run:    bool = False

    # ── External dependencies (injected by the caller) ───────────────────
    company_map: dict = field(default_factory=dict)
    resolver:    Any  = None

    # ── Populated by: fetch_feeds ─────────────────────────────────────────
    articles: list = field(default_factory=list)

    # ── Populated by: filter_relevant ─────────────────────────────────────
    relevant: list = field(default_factory=list)

    # ── Populated by: dedup ───────────────────────────────────────────────
    existing_urls: set  = field(default_factory=set)
    new_articles:  list = field(default_factory=list)

    # ── Populated by: extract_intel ───────────────────────────────────────
    intel: list = field(default_factory=list)

    # ── Populated by: write_intel ─────────────────────────────────────────
    inserted_intel:     int = 0
    inserted_deals:     int = 0
    inserted_catalysts: int = 0

    # ── Pipeline bookkeeping ──────────────────────────────────────────────
    errors:          list = field(default_factory=list)
    nodes_completed: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def mark_complete(self, node_name: str) -> None:
        self.nodes_completed.append(node_name)

    def add_error(self, node_name: str, msg: str) -> None:
        self.errors.append(f"[{node_name}] {msg}")
