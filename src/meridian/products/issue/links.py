#!/usr/bin/env python3
"""
First-mention hyperlink post-processor for the Meridian Issue (§3 write_meridian split).
========================================================================================
Extracted verbatim from write_meridian.py. apply_first_mention_links hyperlinks the
first mention of each known drug/company in the finished HTML. Self-contained.
"""

from meridian.products.issue.common import log


# ── First-mention hyperlink post-processor ───────────────────────────────────
def apply_first_mention_links(html: str, drugs: dict, companies: dict) -> str:
    """
    Post-processing pass: wrap the FIRST occurrence of each known drug name and
    company name in the HTML with the appropriate onclick modal link.  All
    subsequent occurrences are left as plain text.

    Rules:
      - Drug first mention  → <a href="#" onclick="openDrugModal('{id}')">name</a>
      - Company first mention → <a href="#" onclick="openCompanyModal('{id}')">name</a>
      - Names already inside an <a …> tag are skipped (source links placed by LLM).
      - Only replaces exact-case matches with word-boundary guards to avoid
        partial-word collisions (e.g. "Roche" inside "Roche/Genentech" is handled
        by longest-match ordering).
      - Skips tokens shorter than 4 characters to reduce false positives.

    This closes the gap when the LLM fails to apply the onclick pattern itself,
    and enforces the WRITING_STANDARDS first-mention rule programmatically.
    """
    import re as _re

    # Build sorted lists: longest name first to avoid partial replacements
    drug_entries = []
    for d in drugs.values():
        for field in [d.get("display_name"), d.get("name")]:
            if field and len(field) >= 4:
                drug_entries.append((field, d["id"]))
    # Deduplicate by name, keep first occurrence (display_name preferred)
    seen_drug_names = set()
    drug_entries_dedup = []
    for name, did in sorted(drug_entries, key=lambda x: -len(x[0])):
        if name.lower() not in seen_drug_names:
            seen_drug_names.add(name.lower())
            drug_entries_dedup.append((name, did))

    company_entries = []
    for c in companies.values():
        if c.get("name") and len(c["name"]) >= 4:
            company_entries.append((c["name"], c["id"]))
    company_entries = sorted(company_entries, key=lambda x: -len(x[0]))

    # Helper: check if position pos in html is already inside an <a> tag
    def _inside_anchor(html_str, pos):
        """Return True if pos falls between an <a …> and its </a>."""
        preceding = html_str[:pos]
        open_count  = len(_re.findall(r'<a[\s>]', preceding, _re.IGNORECASE))
        close_count = len(_re.findall(r'</a>', preceding, _re.IGNORECASE))
        return open_count > close_count

    def _replace_first(html_str, token, replacement):
        """Replace the first word-boundary occurrence of token (case-sensitive)
        that is NOT already inside an anchor tag."""
        pattern = _re.compile(r'(?<![a-zA-Z0-9\-])' + _re.escape(token) + r'(?![a-zA-Z0-9\-])')
        for m in pattern.finditer(html_str):
            if not _inside_anchor(html_str, m.start()):
                return html_str[:m.start()] + replacement + html_str[m.end():]
        return html_str  # no eligible occurrence found

    # Apply drug links
    drug_linked = set()
    for name, did in drug_entries_dedup:
        if name.lower() not in drug_linked:
            link = f'<a href="javascript:void(0)" style="cursor:pointer" onclick="try{{window.parent.openDrugEntityModal(\'{did}\',\'{name}\',null)}}catch(e){{}}">{name}</a>'
            new_html = _replace_first(html, name, link)
            if new_html is not html:  # replacement was made
                html = new_html
                drug_linked.add(name.lower())

    # Apply company links
    co_linked = set()
    for name, cid in company_entries:
        if name.lower() not in co_linked:
            link = f'<a href="javascript:void(0)" style="cursor:pointer" onclick="try{{window.parent.openCompanyEntityModal(\'{cid}\',\'{name}\',\'meridian\',\'{cid}\')}}catch(e){{}}">{name}</a>'
            new_html = _replace_first(html, name, link)
            if new_html is not html:
                html = new_html
                co_linked.add(name.lower())

    log(f"First-mention links applied: {len(drug_linked)} drugs, {len(co_linked)} companies")

    # ── Final cleanup: fix LLM-generated href="#" entity links ──────────────────
    # The LLM sometimes generates <a href="#" onclick="openDrugModal('id')"> or
    # <a href="#" onclick="openCompanyModal('id')"> links. These break because:
    #   1. openDrugModal / openCompanyModal don't exist in the Meridian iframe
    #   2. href="#" scrolls or navigates the iframe instead of opening a card
    # Fix: convert to javascript:void(0) + window.parent calls, or strip entirely.
    import re as _re2

    def _fix_drug_modal_link(m):
        did = m.group(1).strip("'\"")
        # Try to get the display name from between the tags
        display = m.group(2)
        safe_name = display.replace("'", "\\'")
        return (f'<a href="javascript:void(0)" style="cursor:pointer" '
                f'onclick="try{{window.parent.openDrugEntityModal(\'{did}\',\'{safe_name}\',null)}}catch(e){{}}">'
                f'{display}</a>')

    def _fix_company_modal_link(m):
        cid = m.group(1).strip("'\"")
        display = m.group(2)
        safe_name = display.replace("'", "\\'")
        return (f'<a href="javascript:void(0)" style="cursor:pointer" '
                f'onclick="try{{window.parent.openCompanyEntityModal(\'{cid}\',\'{safe_name}\',\'meridian\',\'{cid}\')}}catch(e){{}}">'
                f'{display}</a>')

    # Match: <a href="#" onclick="openDrugModal('id')">text</a>
    html = _re2.sub(
        r'<a\s+href=["\']#["\'][^>]*onclick=["\']openDrugModal\(([^)]+)\)["\'][^>]*>([^<]+)</a>',
        _fix_drug_modal_link, html)
    # Also handle reversed attr order: onclick first, then href
    html = _re2.sub(
        r'<a\s+onclick=["\']openDrugModal\(([^)]+)\)["\'][^>]*href=["\']#["\'][^>]*>([^<]+)</a>',
        _fix_drug_modal_link, html)

    # Match: <a href="#" onclick="openCompanyModal('id')">text</a>
    html = _re2.sub(
        r'<a\s+href=["\']#["\'][^>]*onclick=["\']openCompanyModal\(([^)]+)\)["\'][^>]*>([^<]+)</a>',
        _fix_company_modal_link, html)
    html = _re2.sub(
        r'<a\s+onclick=["\']openCompanyModal\(([^)]+)\)["\'][^>]*href=["\']#["\'][^>]*>([^<]+)</a>',
        _fix_company_modal_link, html)

    # Catch-all: any remaining href="#" on entity links → strip href (leave onclick)
    html = _re2.sub(r'(<a\b[^>]*) href=["\']#["\']([^>]*onclick[^>]*>)', r'\1\2', html)

    log("LLM href='#' entity links sanitized")

    # ── Ensure ALL external source links have target="_blank" ──────────────────
    # Source links without target="_blank" navigate the iframe itself when clicked,
    # which browsers show as about:blank (cross-origin blocked). This post-processor
    # guarantees every external href gets target="_blank" rel="noopener noreferrer"
    # regardless of what the LLM emitted.
    def _add_target_blank(m):
        tag = m.group(0)
        if 'target=' in tag:
            return tag  # already has target
        if 'onclick=' in tag:
            return tag  # entity modal link — never add target
        # Insert target="_blank" rel="noopener noreferrer" before the closing >
        return tag[:-1] + ' target="_blank" rel="noopener noreferrer">'

    html = _re2.sub(r'<a\b[^>]*href=["\']https?://[^"\']*["\'][^>]*>', _add_target_blank, html)

    # Count and log
    n_blanks = len(_re2.findall(r'target="_blank"', html))
    log(f"Source links with target=_blank ensured: {n_blanks}")

    return html
