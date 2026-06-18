#!/usr/bin/env python3
"""
credentials.py — the one fail-soft credential reader for the meridian package.

Every credentialed module needs the same thing: read a secret from the environment (CI /
GitHub Actions), fall back to the repo-root dotfile for local runs, and — crucially — NEVER
raise at import time when neither is present. A bare `os.environ["X"]` at module scope makes
the module un-importable without secrets, which breaks unit tests, REPL exploration, and the
CI static gate (ROADMAP §B). `scripts/maintenance/check_import_clean.py` enforces the no-bare-
subscript invariant; this module is the sanctioned way to satisfy it.

Using ONE helper (rather than a per-file copy) also removes the `__file__`-relative repo-root
depth-anchor calculation from every call site — a recurring source of bugs during the §3 splits
(a module moved one dir deeper needed parents[N]→[N+1], silently wrong until an import smoke).
The root is computed once here, relative to this file.

    from meridian.credentials import read_key
    SUPABASE_KEY = read_key("SUPABASE_SERVICE_KEY", ".supabase_service_key")
    SUPABASE_URL = read_key("SUPABASE_URL", ".supabase_url", "https://tghntyofptvfhmtchwcv.supabase.co")

Imports nothing from the package (only stdlib `os`), so it is safe at the bottom of any
dependency graph — no cycles.
"""
import os

# repo root: this file is src/meridian/credentials.py → 3 dirnames up.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# The Supabase project URL is public (it's already embedded client-side in index.html), so it
# is a safe default when neither env nor a .supabase_url file is present.
DEFAULT_SUPABASE_URL = "https://tghntyofptvfhmtchwcv.supabase.co"


def read_key(env, filename="", default=""):
    """Fail-soft credential read: env var first (prod/CI), then the repo-root file, then
    `default`. Never raises — a key-less import returns `default` instead of KeyError, so
    pure functions stay importable without secrets.

    env       : environment variable name (checked first; whitespace-stripped).
    filename  : repo-root dotfile to fall back to (e.g. ".supabase_service_key"); "" = skip.
    default   : returned when neither source yields a value.
    """
    if os.environ.get(env, "").strip():
        return os.environ[env].strip()
    if filename:
        try:
            with open(os.path.join(REPO_ROOT, filename)) as f:
                return f.read().strip()
        except FileNotFoundError:
            pass
    return default
