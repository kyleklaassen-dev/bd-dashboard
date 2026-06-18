"""
Parse `.github/workflows/*.yml` into the Atlas data model.

Everything is read live from the working tree, so the Atlas always reflects the
branch you launch it on. No network, no Supabase, no execution — pure static
read of YAML + a light AST/comment scrape of each entrypoint script.
"""
from __future__ import annotations

import ast
import re
from functools import lru_cache
from pathlib import Path

import yaml

from .model import Entrypoint, Job, Step, Workflow

# workflow_atlas/atlas/parse.py -> repo root is two parents up from this file.
REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"

# `python foo/bar.py ...`  or  `python -m dotted.module ...`
_PY_FILE = re.compile(r"python[0-9.]*\s+(?:-m\s+)?([^\s;&|<>]+\.py)")
_PY_MODULE = re.compile(r"python[0-9.]*\s+-m\s+([A-Za-z_][\w.]+)(?!\.py)")


# --------------------------------------------------------------------------- #
# Entrypoint resolution
# --------------------------------------------------------------------------- #
def _resolve_path(candidate: str) -> tuple[str | None, bool]:
    """Return (repo-relative-path, exists). Tries the path as-is and under src/."""
    cand = candidate.strip().strip("\"'")
    for base in ("", "src/"):
        p = REPO_ROOT / (base + cand)
        if p.is_file():
            return str(p.relative_to(REPO_ROOT)), True
    return cand, False


def _resolve_module(dotted: str) -> tuple[str | None, bool]:
    rel = dotted.replace(".", "/") + ".py"
    for base in ("src/", ""):
        p = REPO_ROOT / (base + rel)
        if p.is_file():
            return str(p.relative_to(REPO_ROOT)), True
    return dotted, False


@lru_cache(maxsize=512)
def _script_meta(path: str) -> tuple[str | None, int | None]:
    """(docstring-or-leading-comment, line-count) for a resolved repo file."""
    p = REPO_ROOT / path
    if not p.is_file():
        return None, None
    text = p.read_text(encoding="utf-8", errors="replace")
    loc = text.count("\n") + 1
    doc = None
    try:
        doc = ast.get_docstring(ast.parse(text))
    except (SyntaxError, ValueError):
        doc = None
    if not doc:  # fall back to a leading `#` comment block
        lines = []
        for ln in text.splitlines():
            s = ln.strip()
            if s.startswith("#!"):
                continue
            if s.startswith("#"):
                lines.append(s.lstrip("# ").rstrip())
            elif s == "":
                if lines:
                    break
            else:
                break
        doc = "\n".join(lines).strip() or None
    if doc:
        doc = doc.strip()
        if len(doc) > 600:
            doc = doc[:600].rstrip() + " …"
    return doc, loc


def _extract_entrypoints(run: str) -> list[Entrypoint]:
    eps: list[Entrypoint] = []
    seen: set[str] = set()
    for raw in _PY_FILE.findall(run):
        if raw in seen:
            continue
        seen.add(raw)
        path, exists = _resolve_path(raw)
        doc, loc = _script_meta(path) if exists else (None, None)
        eps.append(Entrypoint(raw=raw, path=path, exists=exists, is_module=False,
                              docstring=doc, loc=loc))
    for raw in _PY_MODULE.findall(run):
        if raw in seen or raw in {"compileall", "pytest", "pip", "venv", "json", "unittest"}:
            continue
        seen.add(raw)
        path, exists = _resolve_module(raw)
        doc, loc = _script_meta(path) if exists else (None, None)
        eps.append(Entrypoint(raw=raw, path=path, exists=exists, is_module=True,
                              docstring=doc, loc=loc))
    return eps


# --------------------------------------------------------------------------- #
# Cadence classification (from cron / triggers)
# --------------------------------------------------------------------------- #
_DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _cron_to_dow(field_: str) -> list[str]:
    """GitHub cron DOW: 0/7=Sun..6=Sat. Return readable day names."""
    out: list[str] = []
    for tok in field_.split(","):
        if "-" in tok:
            a, b = tok.split("-")
            try:
                rng = list(range(int(a), int(b) + 1))
            except ValueError:
                continue
            for n in rng:
                out.append(_DOW[6 if n in (0, 7) else n - 1])
        elif tok.isdigit():
            n = int(tok)
            out.append(_DOW[6 if n in (0, 7) else n - 1])
    return out


def humanize_cron(cron: str) -> str:
    """Best-effort UTC description of a single 5-field cron expression."""
    parts = cron.split()
    if len(parts) != 5:
        return cron
    minute, hour, dom, mon, dow = parts
    # time component
    if hour.startswith("*/"):
        t = f"every {hour[2:]}h"
    elif "," in hour or "-" in hour:
        t = f"{hour}:{minute.zfill(2)} UTC"
    elif hour == "*":
        t = f"every hour at :{minute.zfill(2)}"
    else:
        t = f"{hour.zfill(2)}:{minute.zfill(2)} UTC"
    # day component
    if dow != "*":
        days = _cron_to_dow(dow)
        when = ", ".join(days) if days else f"dow={dow}"
    elif dom != "*":
        when = f"day {dom} of month" + ("" if mon == "*" else f" (month {mon})")
    else:
        when = "daily"
    return f"{when} · {t}"


def _classify(wf: Workflow) -> tuple[str, str]:
    if "workflow_run" in wf.triggers and wf.after_workflows:
        return "chain", "after: " + ", ".join(wf.after_workflows)
    has_push = "push" in wf.triggers or "pull_request" in wf.triggers
    if has_push and not wf.crons:
        return "ci", "on push / pull_request"
    if not wf.crons:
        if wf.triggers == ["workflow_dispatch"] or set(wf.triggers) <= {"workflow_dispatch"}:
            return "manual", "manual dispatch only"
        return "other", ", ".join(wf.triggers)
    # has cron(s)
    descs = [humanize_cron(c) for c in wf.crons]
    fields = [c.split() for c in wf.crons if len(c.split()) == 5]
    dom_set = any(f[2] != "*" for f in fields)
    dow_set = any(f[4] != "*" for f in fields)
    interval = any(f[1].startswith("*/") or "," in f[1] for f in fields)
    if dom_set and not dow_set:
        cad = "monthly"
    elif dow_set:
        cad = "weekly"
    elif interval:
        cad = "interval"
    else:
        cad = "daily"
    return cad, " · ".join(dict.fromkeys(descs))


# --------------------------------------------------------------------------- #
# Top-level parse
# --------------------------------------------------------------------------- #
def _get_on(doc: dict):
    # PyYAML parses the bare key `on:` as the boolean True.
    return doc.get("on", doc.get(True))


def parse_workflow(path: Path) -> Workflow:
    raw = path.read_text(encoding="utf-8", errors="replace")
    wf = Workflow(filename=path.name, path=str(path.relative_to(REPO_ROOT)),
                  name=path.stem, raw_yaml=raw)
    try:
        doc = yaml.safe_load(raw) or {}
    except yaml.YAMLError as e:
        wf.parse_error = str(e)
        return wf

    wf.name = doc.get("name") or path.stem
    on = _get_on(doc)
    if isinstance(on, dict):
        wf.triggers = list(on.keys())
        for s in (on.get("schedule") or []):
            if isinstance(s, dict) and s.get("cron"):
                wf.crons.append(s["cron"])
        wr = on.get("workflow_run")
        if isinstance(wr, dict):
            wf.after_workflows = list(wr.get("workflows", []) or [])
    elif isinstance(on, list):
        wf.triggers = [str(x) for x in on]
    elif isinstance(on, str):
        wf.triggers = [on]

    conc = doc.get("concurrency")
    if isinstance(conc, dict):
        wf.concurrency_group = conc.get("group")
        wf.cancel_in_progress = conc.get("cancel-in-progress")
    elif isinstance(conc, str):
        wf.concurrency_group = conc

    for job_id, job in (doc.get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        j = Job(job_id=job_id, runs_on=str(job.get("runs-on", "?")),
                timeout_minutes=job.get("timeout-minutes"))
        for st in (job.get("steps") or []):
            if not isinstance(st, dict):
                continue
            run = st.get("run", "") or ""
            j.steps.append(Step(
                name=st.get("name", "") or (st.get("uses", "") or "step"),
                run=run, uses=st.get("uses"),
                entrypoints=_extract_entrypoints(run) if run else [],
            ))
        wf.jobs.append(j)

    wf.cadence, wf.cadence_detail = _classify(wf)
    return wf


@lru_cache(maxsize=1)
def load_workflows() -> tuple[Workflow, ...]:
    files = sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml"))
    return tuple(parse_workflow(p) for p in files)


def name_index(workflows) -> dict[str, Workflow]:
    return {wf.name: wf for wf in workflows}
