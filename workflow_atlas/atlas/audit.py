"""
Static audit over the parsed workflows — the "faults, flaws & improvement areas"
surface. Every finding is derived mechanically from ground truth, so it's a
starting point for investigation, not a verdict. Severities:

  error    something is broken right now (a reference points at nothing)
  warning  a real risk / smell worth a look (overlap, no guard, redundancy)
  info     an observation that aids understanding (shared scripts, defaults)
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .model import Workflow

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
DEFAULT_GH_TIMEOUT = 360  # GitHub's default job timeout (minutes)


@dataclass
class Finding:
    severity: str
    category: str
    title: str
    detail: str
    workflows: list[str] = field(default_factory=list)


def _scheduled(wf: Workflow) -> bool:
    return bool(wf.crons)


def audit(workflows) -> list[Finding]:
    findings: list[Finding] = []
    by_name = {wf.name: wf for wf in workflows}

    # 1) Parse failures -----------------------------------------------------
    for wf in workflows:
        if wf.parse_error:
            findings.append(Finding(
                "error", "Parse", f"{wf.filename} failed to parse",
                wf.parse_error, [wf.filename]))

    # 2) Broken entrypoint references --------------------------------------
    for wf in workflows:
        for ep in wf.all_entrypoints:
            if not ep.exists and not ep.is_module:
                findings.append(Finding(
                    "error", "Broken reference",
                    f"{wf.filename} → missing script",
                    f"`run:` invokes `{ep.raw}` but no such file exists on this branch.",
                    [wf.filename]))

    # 3) Broken chain links (workflow_run name with no matching workflow) ---
    for wf in workflows:
        for up in wf.after_workflows:
            if up not in by_name:
                findings.append(Finding(
                    "error", "Broken chain",
                    f"{wf.filename} waits on an unknown workflow",
                    f"`workflow_run` references **{up}**, but no workflow has that "
                    f"`name:`. This link will never fire (names, not filenames, must match).",
                    [wf.filename]))

    # 4) Cron collisions (same exact cron string on 2+ workflows) ----------
    cron_map: dict[str, list[str]] = defaultdict(list)
    for wf in workflows:
        for c in wf.crons:
            cron_map[c].append(wf.filename)
    for cron, files in sorted(cron_map.items()):
        if len(files) > 1:
            findings.append(Finding(
                "warning", "Schedule contention",
                f"{len(files)} workflows share cron `{cron}`",
                "They kick off at the same minute and compete for runners / DB "
                "connections. Consider staggering by a few minutes.",
                sorted(set(files))))

    # 5) Manual-only workflows with no python entrypoint (possible dead) ----
    for wf in workflows:
        if wf.cadence == "manual" and not wf.all_entrypoints and not wf.parse_error:
            findings.append(Finding(
                "warning", "Possibly dead",
                f"{wf.filename} is dispatch-only with no script",
                "Only `workflow_dispatch`, and no python entrypoint was detected — "
                "likely retired or a stub. Confirm it still earns its place.",
                [wf.filename]))

    # 6) Scheduled but no concurrency guard --------------------------------
    for wf in workflows:
        if _scheduled(wf) and not wf.concurrency_group and not wf.parse_error:
            findings.append(Finding(
                "warning", "No concurrency guard",
                f"{wf.filename} has a schedule but no concurrency group",
                "A slow run can overlap the next scheduled run (or a manual one), "
                "doubling writes. Add a `concurrency.group`.",
                [wf.filename]))

    # 7) Shared entrypoints across workflows (coupling / possible dupes) ----
    ep_map: dict[str, set[str]] = defaultdict(set)
    for wf in workflows:
        for ep in wf.all_entrypoints:
            if ep.exists:
                ep_map[ep.path].add(wf.filename)
    for path, files in sorted(ep_map.items()):
        if len(files) > 1:
            findings.append(Finding(
                "info", "Shared entrypoint",
                f"{path.split('/')[-1]} runs in {len(files)} workflows",
                f"`{path}` is invoked by: {', '.join(sorted(files))}. Shared logic — "
                "a change here ripples across all of them; confirm it's intended and "
                "not an accidental duplicate cadence.",
                sorted(files)))

    # 8) Timeout hygiene ----------------------------------------------------
    for wf in workflows:
        t = wf.timeout_minutes
        if t is None and wf.jobs and not wf.parse_error:
            findings.append(Finding(
                "info", "No timeout set",
                f"{wf.filename} relies on the {DEFAULT_GH_TIMEOUT}-min default",
                "No `timeout-minutes` on any job — a hung run burns up to 6h of "
                "Actions minutes before GitHub kills it.",
                [wf.filename]))
        elif t and t >= 300:
            findings.append(Finding(
                "info", "Long timeout",
                f"{wf.filename} allows up to {t} min",
                "Long budget is fine for big sweeps, but worth confirming the run "
                "actually needs it.",
                [wf.filename]))

    findings.sort(key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), f.category, f.title))
    return findings


def summarize(findings) -> dict[str, int]:
    out = {"error": 0, "warning": 0, "info": 0}
    for f in findings:
        out[f.severity] = out.get(f.severity, 0) + 1
    return out
