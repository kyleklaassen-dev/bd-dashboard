// ── Asset-tab templating (rec #6) ────────────────────────────────────────────
// Renders per-program content from Supabase (asset_programs) into the asset tabs,
// replacing hardcoded clones. Falls back silently to the existing static markup
// when the table is empty or unreachable — so there is never a regression.
//
// Pilot: ALX001 (TL1A × IL-23p19). Add a program → tab mapping below as each
// program's row is seeded (see migrations/APPLIED_2026-06-19_asset_programs_seed_*.sql).
(function () {
  // program_code → the asset tab's differentiator-grid element id (set in index.html).
  const DIFF_GRID_BY_PROGRAM = {
    'ALX001':          'asset-diff-tl1a',
    'ALX-TSLP-IL33':   'asset-diff-tslp',
    'ALX-IL4RA-TSLP':  'asset-diff-il4ra-tslp',
    'ALX-IL4RA-OX40L': 'asset-diff-il4ra-ox40l',
    'ALX-IGF1R-TSHR':  'asset-diff-igf1r-tshr',
    'ALX005':          'asset-diff-fcrn',
    'ALX002':          'asset-diff-ace',
  };

  function esc(s) {
    return (s == null ? '' : String(s)).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function renderDiffGrid(gridEl, items) {
    gridEl.innerHTML = items.map(function (d) {
      return '<div class="ailux-diff">'
        + '<div class="ad-label">' + esc(d.label) + '</div>'
        + '<div class="ad-val">' + esc(d.value) + '</div>'
        + '<div class="ad-sub">' + esc(d.sub) + '</div>'
        + '</div>';
    }).join('');
    gridEl.setAttribute('data-source', 'asset_programs');
  }

  async function renderAssetPrograms() {
    if (typeof _sb === 'undefined' || !_sb) return;           // no client → keep static fallback
    try {
      const { data, error } = await _sb
        .from('asset_programs')
        .select('program_code,differentiators');
      if (error || !Array.isArray(data)) return;              // error → keep static fallback
      data.forEach(function (p) {
        const gridId = DIFF_GRID_BY_PROGRAM[p.program_code];
        if (!gridId) return;
        const grid = document.getElementById(gridId);
        if (!grid) return;
        const items = Array.isArray(p.differentiators) ? p.differentiators : [];
        if (!items.length) return;                            // empty → keep static fallback
        renderDiffGrid(grid, items);
      });
    } catch (e) {
      console.warn('[asset_tab] render skipped:', e.message); // never block the UI
    }
  }

  // ── #10: valuation cards — sourced comparables beside the labeled estimate ──
  // The valuation card shares an .ailux-card with the program's differentiator grid
  // (which carries data-asset-program), so resolve the program there — robust even
  // though several asset modals live outside their .tab-pane in the DOM.
  const AREA_BY_PROGRAM = {
    'ALX001': 'tl1a', 'ALX-TSLP-IL33': 'tslp', 'ALX-IL4RA-TSLP': 'il4ra',
    'ALX-IL4RA-OX40L': 'il4ra', 'ALX-IGF1R-TSHR': 'igf1r', 'ALX005': 'fcrn', 'ALX002': 'tcell',
  };

  function areaForCard(card) {
    const host = card.closest('.ailux-card') || card.parentElement;
    const gridEl = host && host.querySelector('[data-asset-program]');
    const prog = gridEl && gridEl.getAttribute('data-asset-program');
    return prog ? AREA_BY_PROGRAM[prog] : null;
  }

  function fmtUsdM(n) {
    if (n == null) return null;
    return n >= 1000 ? '$' + (n / 1000).toFixed(n % 1000 === 0 ? 0 : 1) + 'B' : '$' + n + 'M';
  }

  function compLine(c) {
    const up = fmtUsdM(c.upfront_usd_m), tot = fmtUsdM(c.total_usd_m);
    const money = [up && up + ' up', tot && tot + ' total'].filter(Boolean).join(' / ');
    const yr = c.deal_year ? ' (' + c.deal_year + ')' : '';
    const who = esc(c.acquirer || '—');
    const link = c.source_url
      ? ' <a href="' + esc(c.source_url) + '" target="_blank" rel="noopener" style="color:#7fb2e6;text-decoration:none">↗</a>'
      : '';
    return '<li style="margin:3px 0;line-height:1.35"><span style="color:#cdd9e8;font-weight:700">' + who + '</span>'
      + (money ? ' <span style="color:#9fb4cc">' + money + '</span>' : '') + yr + link + '</li>';
  }

  function renderCompsInto(card, comps) {
    if (card.querySelector('.cv-comps')) return;
    const box = document.createElement('div');
    box.className = 'cv-comps';
    box.style.cssText = 'margin-top:10px;padding-top:8px;border-top:1px solid rgba(255,255,255,0.12)';
    if (comps && comps.length) {
      const top = comps.slice(0, 5);
      box.innerHTML =
        '<div style="font-size:10px;font-weight:800;letter-spacing:.3px;text-transform:uppercase;color:#9fb4cc;margin-bottom:4px">Sourced comparables (tracked deals)</div>'
        + '<ul style="margin:0;padding-left:16px;font-size:11px;color:#9fb4cc">' + top.map(compLine).join('') + '</ul>'
        + '<div style="font-size:10px;color:#94a3b8;font-style:italic;margin-top:6px;line-height:1.35">Estimate above is directional (internal); comparables are real, sourced deals for context.</div>';
    } else {
      box.innerHTML = '<div style="font-size:10px;color:#94a3b8;font-style:italic;line-height:1.35">Illustrative internal estimate — no sourced comparables tagged for this area yet.</div>';
    }
    card.appendChild(box);
  }

  async function renderValuationComps() {
    const cards = document.querySelectorAll('.comp-valuation-card');
    if (!cards.length || typeof _sb === 'undefined' || !_sb) return;
    try {
      const { data, error } = await _sb
        .from('deal_comparables')
        .select('area_id,acquirer,upfront_usd_m,total_usd_m,deal_year,source_url')
        .order('total_usd_m', { ascending: false, nullsFirst: false });
      if (error || !Array.isArray(data)) return;
      const byArea = {};
      data.forEach(c => { if (!c.area_id) return; (byArea[c.area_id] = byArea[c.area_id] || []).push(c); });
      cards.forEach(card => {
        const area = areaForCard(card);
        renderCompsInto(card, area ? byArea[area] : null);
      });
    } catch (e) {
      console.warn('[asset_tab] valuation comps skipped:', e.message);
    }
  }

  window.renderAssetPrograms = renderAssetPrograms;
  window.renderValuationComps = renderValuationComps;
  document.addEventListener('DOMContentLoaded', function () {
    renderAssetPrograms();
    renderValuationComps();
  });
})();
