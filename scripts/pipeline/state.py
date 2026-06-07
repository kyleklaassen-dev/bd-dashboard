"""
Pipeline state dataclasses for the company enrichment pipeline.

PipelineState is the single shared object that flows through every node.
Each node reads the fields it needs, writes its outputs, and returns the
mutated state.  The orchestrator drives the sequence.

Typical usage:
    state = PipelineState(area_id="tl1a", company_id="abbvie",
                          company_map={...}, resolver=resolver)
    state = run_company_pipeline(state)
    success = state.ok
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# ── CompanyContext ─────────────────────────────────────────────────────────────

@dataclass
class CompanyContext:
    """
    Raw Supabase data for one company × area, populated by the load_context node.

    Carries the same fields as the legacy ctx dict so all downstream functions
    that accept `ctx: dict` can receive `state.ctx.as_dict()` without changes.
    """
    company:     dict = field(default_factory=dict)
    profile:     dict = field(default_factory=dict)
    drugs:       list = field(default_factory=list)
    trials:      list = field(default_factory=list)
    catalysts:   list = field(default_factory=list)
    deals:       list = field(default_factory=list)
    recent_intel: list = field(default_factory=list)
    ailux_pos:   dict = field(default_factory=dict)

    @property
    def loaded(self) -> bool:
        return bool(self.company)

    def as_dict(self) -> dict:
        """Return the legacy dict format expected by functions in company_enrichment.py."""
        return {
            "company":      self.company,
            "profile":      self.profile,
            "drugs":        self.drugs,
            "trials":       self.trials,
            "catalysts":    self.catalysts,
            "deals":        self.deals,
            "recent_intel": self.recent_intel,
            "ailux_pos":    self.ailux_pos,
        }


# ── PipelineState ──────────────────────────────────────────────────────────────

@dataclass
class PipelineState:
    """
    Shared state object that flows through every node in run_company_pipeline().

    Fields are grouped by which node populates them.  Inputs are set by the
    caller (enrich_company); all other fields start empty and are filled in
    as nodes complete.
    """

    # ── Required inputs ────────────────────────────────────────────────────
    area_id:    str
    company_id: str

    # ── Run options ────────────────────────────────────────────────────────
    dry_run:             bool          = False
    skip_web_search:     bool          = False
    skip_trial_refresh:  bool          = False
    fast_model:          bool          = False
    enrichment_run_id:   Optional[str] = None

    # ── External dependencies (injected by enrich_company) ────────────────
    company_map: dict      = field(default_factory=dict)  # full area company map
    resolver:    Any       = None                          # DrugIdentityResolver instance

    # ── Populated by: load_context ─────────────────────────────────────────
    ctx: CompanyContext = field(default_factory=CompanyContext)

    # ── Populated by: generate_catalysts ──────────────────────────────────
    catalysts_generated: int = 0

    # ── Populated by: gather_web_intel ────────────────────────────────────
    web_intel: str = ""

    # ── Populated by: synthesize_enrichment ───────────────────────────────
    synth_result:   Any  = None   # ai.client.RunResult (typed as Any to avoid import)
    synth_data:     dict = field(default_factory=dict)
    synth_raw_text: str  = ""

    # ── Populated by: validate_enrichment ─────────────────────────────────
    validated_data:   dict = field(default_factory=dict)
    validation_stats: Any  = None   # ai.validators.drug_fields.ValidationStats

    # ── Populated by: score_completeness ──────────────────────────────────
    completeness_score:   Optional[int] = None
    completeness_tier:    Optional[str] = None
    completeness_missing: list          = field(default_factory=list)

    # ── Populated by: generate_deals ──────────────────────────────────────
    deals_created: int = 0

    # ── Pipeline tracking ──────────────────────────────────────────────────
    errors:          list = field(default_factory=list)
    nodes_completed: list = field(default_factory=list)

    # ── Helpers ────────────────────────────────────────────────────────────

    @property
    def ok(self) -> bool:
        """True when no errors have been recorded (matches original enrich_company bool return)."""
        return len(self.errors) == 0

    def mark_complete(self, node_name: str) -> None:
        self.nodes_completed.append(node_name)

    def add_error(self, node_name: str, msg: str) -> None:
        self.errors.append(f"[{node_name}] {msg}")
