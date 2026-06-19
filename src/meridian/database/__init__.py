"""
Core database write layer.

Convenience drop-ins for the Single Writer Pattern (ADR-010 / Constitution §4).
`update_drug` / `update_company` route a field-level update through the one
sanctioned Writer for that core table, so callers never `sb_patch('drugs', …)`
directly. They preserve a simple bool return (True on success) so existing
call-sites that did `ok = sb_patch(...)` keep working unchanged.

    from meridian.database import update_drug
    ok = update_drug(drug_id, {"stage": "Phase 2", "last_synced_date": NOW})

The Writer applies governance (rejects unknown columns, brand⇒approved, etc.) and
records nothing extra for a pure field patch. The writer instance is cached so a
loop of updates fetches the column list only once.
"""
from __future__ import annotations

_dw = None
_cw = None


def update_drug(drug_id, fields) -> bool:
    """Governed field update of an existing drug via DrugWriter. True on success."""
    global _dw
    if _dw is None:
        from .drug_writer import DrugWriter
        _dw = DrugWriter()
    report = _dw.update_fields(drug_id, fields)
    return not report.get("errors")


def update_company(company_id, fields) -> bool:
    """Governed field update of an existing company via CompanyWriter."""
    global _cw
    if _cw is None:
        from .company_writer import CompanyWriter
        _cw = CompanyWriter()
    report = _cw.update_fields(company_id, fields)
    return not report.get("errors")
