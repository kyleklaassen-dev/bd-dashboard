"""
ClinicalTrials.gov source client.

Responsibilities:
  - Validate NCT ID format
  - Verify a given NCT exists on CT.gov via the v2 API (one round-trip)
  - Build the canonical CT.gov study URL
"""
import json
import re
import urllib.request

from ..config import UA

_CTGOV_API = "https://clinicaltrials.gov/api/v2/studies"
_CTGOV_WEB = "https://clinicaltrials.gov/study"
_NCT_RE = re.compile(r"^NCT\d{8}$")


def is_valid_nct(nct: str) -> bool:
    return bool(_NCT_RE.match(str(nct or "")))


def study_url(nct: str) -> str:
    return f"{_CTGOV_WEB}/{nct}"


def verify_nct(nct: str, timeout: int = 12) -> bool:
    """Return True if this NCT ID exists and is retrievable on ClinicalTrials.gov."""
    try:
        req = urllib.request.Request(
            f"{_CTGOV_API}/{nct}?fields=protocolSection.identificationModule",
            headers={"User-Agent": UA},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
        confirmed = (
            data.get("protocolSection", {})
                .get("identificationModule", {})
                .get("nctId") == nct
        )
        return confirmed
    except Exception:
        return False
