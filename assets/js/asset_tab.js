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

  window.renderAssetPrograms = renderAssetPrograms;
  document.addEventListener('DOMContentLoaded', renderAssetPrograms);
})();
