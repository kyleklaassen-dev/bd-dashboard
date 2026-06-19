"""
The read-first / session-start docs — the canon every Claude session loads before
touching anything (per CLAUDE.md "Read-first" + "Session start"). This module makes
that canon reviewable inside the Atlas: what each doc IS, whether it exists, how
fresh it is, and its rendered content.

Source of truth = CLAUDE.md §"Read-first" and §"Session start".
"""
from __future__ import annotations

import datetime as _dt
import subprocess
from dataclasses import dataclass

from .parse import REPO_ROOT


def _git_modified(rel: str) -> _dt.datetime | None:
    """Last *commit* time for a path — accurate freshness (file mtime is reset by
    every git checkout, so it would always read 'today' in a working tree)."""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%ct", "--", rel],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=5,
        )
        ts = out.stdout.strip()
        if ts:
            return _dt.datetime.fromtimestamp(int(ts))
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None

# Ordered exactly as a session loads them. `role` = why it's read every time.
READ_FIRST = [
    ("CLAUDE.md", "Operating Instructions",
     "The master index — governance hard-rules, deploy, key paths. Everything else hangs off this."),
    ("docs/STABILIZATION_PLAN.md", "Stabilization Plan",
     "Current phase, what's in progress, success criteria. **READ FIRST** — we're in a stabilization sprint."),
    ("docs/constitution.md", "Constitution",
     "What is truth, what may modify it, the source hierarchy, and what needs Kyle's approval."),
    ("docs/database/governance_table.md", "Governance Table",
     "Per core table: owner, sole Writer, the validation that must pass on write, source hierarchy."),
    ("docs/architecture/drug_lifecycle.md", "Drug Lifecycle",
     "How a drug record flows — the truth-test the write layer enforces."),
    ("docs/decisions.md", "Decisions (ADR)",
     "Why things are the way they are. Don't re-debate settled calls."),
    ("NEXT_SESSION.md", "Next-Session Handoff",
     "Last session's handoff / the live roadmap. The single most time-sensitive doc."),
    ("PRIORITY.md", "Priorities",
     "Current priorities, framed against the stabilization stage board."),
]


@dataclass
class DocCard:
    path: str
    title: str
    role: str
    exists: bool
    text: str = ""
    lines: int = 0
    modified: _dt.datetime | None = None

    @property
    def age_days(self) -> int | None:
        if not self.modified:
            return None
        return (_dt.datetime.now() - self.modified).days

    @property
    def freshness(self) -> str:
        if not self.exists:
            return "missing"
        d = self.age_days
        if d is None:
            return "?"
        if d == 0:
            return "today"
        if d == 1:
            return "yesterday"
        return f"{d}d ago"


def load_docs() -> list[DocCard]:
    out: list[DocCard] = []
    for rel, title, role in READ_FIRST:
        p = REPO_ROOT / rel
        if p.is_file():
            text = p.read_text(encoding="utf-8", errors="replace")
            out.append(DocCard(
                path=rel, title=title, role=role, exists=True, text=text,
                lines=text.count("\n") + 1,
                modified=_git_modified(rel) or _dt.datetime.fromtimestamp(p.stat().st_mtime),
            ))
        else:
            out.append(DocCard(path=rel, title=title, role=role, exists=False))
    return out
