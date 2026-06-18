#!/usr/bin/env python3
"""Shared base for the acquisition_scorer split (§3): config, creds, governance
constraints, and the Supabase REST helpers (_request/get/post/patch/upsert)."""

import os
import json
import urllib.request
import urllib.error
from datetime import datetime, date


SUPA_URL = "https://tghntyofptvfhmtchwcv.supabase.co/rest/v1"
WORKSPACE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))  # repo root (5 up from src/meridian/scoring/acquisition/)
OUTPUTS_DIR = os.path.join(WORKSPACE, "outputs")
os.makedirs(OUTPUTS_DIR, exist_ok=True)

RUN_ID = f"aps_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
TODAY = date.today()
TODAY_STR = TODAY.isoformat()


def _read_key(filename, env=None):
    """Credential read, tolerant for CI/tests: env var first, then the repo-root file,
    then '' (never raises). Real runs still read the file; CI/test imports don't need it."""
    if env and os.environ.get(env):
        return os.environ[env].strip()
    try:
        with open(os.path.join(WORKSPACE, filename)) as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


SUPA_KEY = _read_key(".supabase_service_key", "SUPABASE_SERVICE_KEY")
GITHUB_TOKEN = _read_key(".github_token_workflow", "GITHUB_TOKEN")  # .github_token is DEAD (CLAUDE.md)
REPO = "kyleklaassen-dev/bd-dashboard"

# ---------------------------------------------------------------------------
# Hard constraints (governance rules)
# ---------------------------------------------------------------------------

# AbbVie cannot be targeted for TL1A bispecific until after ABBV-701 Ph1 readout
ABBVIE_CONSTRAINT_UNTIL = date(2026, 10, 1)
ABBVIE_CONSTRAINT_NOTE = (
    "AbbVie cap: ABBV-701 (FutureGen-licensed TL1A mAb) Phase 1 readout expected "
    "Oct 2026. Cannot target AbbVie for TL1A bispecific BD until after readout. "
    "Governance rule: deal_sequencing / CLAUDE.md."
)

# Companies to exclude from scoring entirely
EXCLUDE_COMPANY_IDS = {"ailux"}

# Companies that should be forced to HOLD regardless of score
FORCE_HOLD_STATUSES = {"acquired"}

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _request(method, endpoint, data=None, extra_headers=None):
    url = f"{SUPA_URL}/{endpoint}"
    body = json.dumps(data).encode() if data is not None else None
    hdrs = {
        "apikey": SUPA_KEY,
        "Authorization": f"Bearer {SUPA_KEY}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        hdrs.update(extra_headers)
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw) if raw.strip() else []
    except urllib.error.HTTPError as e:
        body_err = e.read().decode()
        print(f"  HTTP {e.code} {method} /{endpoint.split('?')[0]}: {body_err[:200]}", file=sys.stderr)
        return None


def get(endpoint):
    return _request("GET", endpoint) or []


def post(endpoint, data, prefer=None):
    hdrs = {"Prefer": prefer} if prefer else {}
    return _request("POST", endpoint, data, hdrs)


def patch(endpoint, data):
    return _request("PATCH", endpoint, data)


def upsert(endpoint, data):
    hdrs = {"Prefer": "resolution=merge-duplicates,return=minimal"}
    return _request("POST", endpoint, data, hdrs)


# ---------------------------------------------------------------------------
# Step 1: Fetch data from Supabase
# ---------------------------------------------------------------------------
