"""
Pipeline state for the company intake engine.

IntakeState is the single shared object that flows through every node for
both supported workflows:

  mode="intake"   — research a company, score area relevance, write
                    discovery_queue rows (run_intake / company_intake.py --company X)
  mode="reaudit"  — diff a known company's live pipeline against the DB and
                    queue any gaps (run_reaudit / company_intake.py --re-audit)

Both modes share identity resolution, the model-tier guard, and the open-ended
Claude research call; they diverge afterwards (area scoring + queue writes vs.
DB diff + gap writes). The graph in graph.py routes on state.mode.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class IntakeState:
    """Shared state object that flows through every node in the intake graph."""

    # ── Required inputs ────────────────────────────────────────────────────
    company_name: str
    mode: str = "intake"   # "intake" | "reaudit"

    # ── Run options ────────────────────────────────────────────────────────
    dry_run: bool = False
    verbose: bool = False
    force:   bool = False
    run_id:  str  = ""

    # ── Injected by the caller (company_intake.py) ─────────────────────────
    supabase_url: str = ""
    supabase_key: str = ""

    # ── Populated by: resolve_identity ─────────────────────────────────────
    resolution: dict           = field(default_factory=dict)
    company_id: Optional[str]  = None

    # ── Populated by: research_company ─────────────────────────────────────
    research: Optional[dict] = None

    # ── Populated by: score_areas / write_queue (mode="intake") ───────────
    relevant_areas: list = field(default_factory=list)
    written_areas:  list = field(default_factory=list)

    # ── Populated by: load_db_drugs / diff_pipeline / write_gaps (mode="reaudit") ─
    db_tokens:    list = field(default_factory=list)
    db_drugs:     list = field(default_factory=list)
    new_drugs:    list = field(default_factory=list)
    seen_drugs:   list = field(default_factory=list)
    gaps_written: int  = 0

    # ── Early-exit control (replaces the original functions' bare `return`s) ─
    aborted:      bool = False
    abort_reason: str  = ""

    # ── Pipeline tracking ───────────────────────────────────────────────────
    errors:          list = field(default_factory=list)
    nodes_completed: list = field(default_factory=list)

    # ── Helpers ────────────────────────────────────────────────────────────

    @property
    def ok(self) -> bool:
        """True when the run reached the end without aborting or erroring."""
        return not self.aborted and not self.errors

    def mark_complete(self, node_name: str) -> None:
        self.nodes_completed.append(node_name)

    def add_error(self, node_name: str, msg: str) -> None:
        self.errors.append(f"[{node_name}] {msg}")

    def abort(self, reason: str) -> None:
        """Stop the pipeline early (mirrors a bare `return` in the original functions)."""
        self.aborted = True
        self.abort_reason = reason
