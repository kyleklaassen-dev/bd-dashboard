#!/usr/bin/env python3
"""
Import-smoke for the ingestion + research entrypoints (Domain B5).

These pipelines run unattended in GitHub Actions (and are PAUSED during travel). A
regression that imports-clean syntactically but breaks at import time — a NameError,
a bad top-level call, an undefined symbol after a refactor — would only surface when
the cron next fires. This test imports each entrypoint with NO secrets and NO network
execution, so CI (and a local run) catch it first. Relies on the fail-soft
`meridian.credentials.read_key` pattern (no module-level `os.environ[...]`).

Run: PYTHONPATH=src python3 tests/integration/test_ingestion_smoke.py
"""
import importlib
import importlib.util
import os
import sys
import traceback

PKG_MODULES = [
    "meridian.ingestion.abstract_fetcher", "meridian.ingestion.api_harvester",
    "meridian.ingestion.ct_gov_sync", "meridian.ingestion.research",
    "meridian.ingestion.fetch_homepage_news", "meridian.ingestion.drug_intake",
    "meridian.ingestion.stock_prices",
    "meridian.ingestion.collect_evidence",
    "meridian.ingestion.refresh_orange_purple_book",
]
# NOT import-safe — these flat scripts run their whole pipeline at module top-level
# (no `if __name__ == "__main__"` guard), so importing them executes work / DB writes.
# Excluded from smoke until they get a main()-guard refactor (tracked finding):
#   meridian.ingestion.seed_data_sources       (upserts data_sources on import)
#   meridian.ingestion.sync_catalyst_calendar  (runs the ct.gov sync on import)
#   meridian.ingestion.payer_pricing_agent     (reads .supabase_service_key FILE at import,
#                                               not the env-first read_key → fails on env-only creds)
# standalone scripts (not importable as a package) — loaded by file path
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT_FILES = [
    os.path.join(ROOT, "scripts", "maintenance", "event_research.py"),
    os.path.join(ROOT, "scripts", "maintenance", "poster_research.py"),
]
# 3rd-party libs that may be absent in a bare local env → skip (CI installs requirements)
THIRD_PARTY = {"feedparser", "anthropic", "bs4", "requests", "yaml", "dateutil", "lxml", "openai"}


def _classify(name, exc):
    if isinstance(exc, ModuleNotFoundError):
        miss = (exc.name or "").split(".")[0]
        if miss in THIRD_PARTY:
            return "skip", f"no {miss}"
    return "FAIL", f"{type(exc).__name__}: {exc}"


def main():
    passed = failed = skipped = 0
    for m in PKG_MODULES:
        try:
            importlib.import_module(m)
            passed += 1; print(f"  ok    {m}")
        except Exception as e:
            kind, msg = _classify(m, e)
            if kind == "skip":
                skipped += 1; print(f"  skip  {m} ({msg})")
            else:
                failed += 1; print(f"  FAIL  {m}: {msg}"); traceback.print_exc()
    for path in SCRIPT_FILES:
        name = os.path.basename(path)
        try:
            spec = importlib.util.spec_from_file_location(name[:-3], path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            passed += 1; print(f"  ok    {name}")
        except Exception as e:
            kind, msg = _classify(name, e)
            if kind == "skip":
                skipped += 1; print(f"  skip  {name} ({msg})")
            else:
                failed += 1; print(f"  FAIL  {name}: {msg}"); traceback.print_exc()
    print(f"\nimport-smoke: {passed} ok, {skipped} skipped, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
