"""
Data model for the Workflow Atlas.

These dataclasses are a *faithful, read-only* projection of what actually lives
in `.github/workflows/*.yml` on the current branch. Nothing here is hand-curated
prose about how a pipeline "should" work — every field is parsed from ground
truth so the Atlas surfaces the repo as it really is (faults included).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Entrypoint:
    """A single script a workflow actually invokes from a `run:` step."""
    raw: str                      # exactly what appeared after `python ` in the YAML
    path: Optional[str]           # repo-relative path if we resolved one
    exists: bool                  # does that path exist on disk right now?
    is_module: bool               # invoked via `python -m dotted.module`
    docstring: Optional[str] = None   # module docstring / leading comment, trimmed
    loc: Optional[int] = None         # line count of the resolved file


@dataclass
class Step:
    name: str
    run: str
    uses: Optional[str] = None
    entrypoints: list[Entrypoint] = field(default_factory=list)


@dataclass
class Job:
    job_id: str
    runs_on: str
    timeout_minutes: Optional[int]
    steps: list[Step] = field(default_factory=list)


@dataclass
class Workflow:
    filename: str                 # basename, e.g. meridian-research.yml
    path: str                     # repo-relative path
    name: str                     # the `name:` field
    triggers: list[str] = field(default_factory=list)
    crons: list[str] = field(default_factory=list)
    after_workflows: list[str] = field(default_factory=list)  # workflow_run.workflows (by NAME)
    concurrency_group: Optional[str] = None
    cancel_in_progress: Optional[bool] = None
    jobs: list[Job] = field(default_factory=list)
    raw_yaml: str = ""
    parse_error: Optional[str] = None

    # ---- derived ----------------------------------------------------------
    cadence: str = "other"        # chain|daily|weekly|monthly|interval|manual|ci|other
    cadence_detail: str = ""      # human-readable schedule

    @property
    def all_entrypoints(self) -> list[Entrypoint]:
        out: list[Entrypoint] = []
        for j in self.jobs:
            for s in j.steps:
                out.extend(s.entrypoints)
        return out

    @property
    def timeout_minutes(self) -> Optional[int]:
        vals = [j.timeout_minutes for j in self.jobs if j.timeout_minutes]
        return max(vals) if vals else None

    @property
    def is_chain_link(self) -> bool:
        return bool(self.after_workflows)
