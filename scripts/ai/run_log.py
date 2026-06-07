"""
ai/run_log.py — Thin wrapper around model_comparison enrichment_runs helpers.

Provides a stable import surface so scripts never import model_comparison
directly. If model_comparison is unavailable (e.g. local dev without the
full dependency set), all functions degrade gracefully to no-ops.

Usage
-----
  from ai.run_log import start_run, patch_run, update_run

  run_id = start_run(area_id="tl1a", entity_id="sanofi", skill="company_enrich")
  # ... do work ...
  patch_run(run_id, {"raw_llm_response": text[:8000]})
  update_run(run_id, success=True, summary="Enriched sanofi/tl1a")
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Optional

logger = logging.getLogger(__name__)

# Add scripts/ to path so model_comparison (in scripts/ml/) can be found.
_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.dirname(os.path.dirname(_HERE))  # scripts/ai/ → scripts/ (wait, ai/ is inside scripts/)
# Actually: scripts/ai/run_log.py → dirname → scripts/ai/ → dirname → scripts/
_SCRIPTS = os.path.dirname(_HERE)  # scripts/
_ML_DIR  = os.path.join(_SCRIPTS, "ml")

for _p in (_SCRIPTS, _ML_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from model_comparison import (  # type: ignore[import]
        log_enrichment_run as _log_run,
        update_enrichment_run as _update_run,
        patch_enrichment_run as _patch_run,
        build_enrichment_summary as _build_summary,
    )
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False
    logger.debug("model_comparison not available — run_log is a no-op")

    def _log_run(*args, **kwargs) -> None: return None       # type: ignore[misc]
    def _update_run(*args, **kwargs) -> bool: return False   # type: ignore[misc]
    def _patch_run(*args, **kwargs) -> bool: return False    # type: ignore[misc]
    def _build_summary(*args, **kwargs): return None         # type: ignore[misc]


def start_run(
    area_id: str,
    entity_id: str = "",
    skill: str = "company_enrich",
    **kwargs,
) -> Optional[str]:
    """Create an enrichment_runs row. Returns run UUID or None."""
    try:
        return _log_run(area_id=area_id, entity_id=entity_id,
                        skill_name=skill, **kwargs)
    except Exception as exc:
        logger.warning("run_log.start_run failed (non-fatal): %s", exc)
        return None


def patch_run(run_id: Optional[str], payload: dict) -> bool:
    """PATCH an enrichment_runs row. Returns True on success."""
    if not run_id:
        return False
    try:
        return bool(_patch_run(run_id, payload))
    except Exception as exc:
        logger.warning("run_log.patch_run failed (non-fatal): %s", exc)
        return False


def update_run(run_id: Optional[str], **kwargs) -> bool:
    """UPDATE enrichment_runs (e.g. mark success/fail). Returns True on success."""
    if not run_id:
        return False
    try:
        return bool(_update_run(run_id, **kwargs))
    except Exception as exc:
        logger.warning("run_log.update_run failed (non-fatal): %s", exc)
        return False


def build_summary(*args, **kwargs):
    """Build a human-readable enrichment summary string."""
    try:
        return _build_summary(*args, **kwargs)
    except Exception:
        return None
