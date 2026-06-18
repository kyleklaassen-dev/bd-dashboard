// ── Saved Views Panel — localStorage-backed view bookmarking ──────────────────
(function() {
  const SVP_KEY = 'meridian_saved_views';

  function _getSavedViews() {
    try { return JSON.parse(localStorage.getItem(SVP_KEY) || '[]'); }
    catch(e) { return []; }
  }

  function _setSavedViews(views) {
    try { localStorage.setItem(SVP_KEY, JSON.stringify(views)); }
    catch(e) { console.warn('[SVP] localStorage write failed', e); }
  }

  function _currentTab() {
    return document.querySelector('.tab-pane.active')?.id?.replace(/^tab-/, '') || 'home';
  }

  function _currentFilters() {
    return {
      ta:       document.getElementById('dkn-ta-select')?.value || '',
      ind:      document.getElementById('dkn-ind-select')?.value || '',
      target:   document.getElementById('dkn-target-select')?.value || '',
      modality: document.getElementById('dkn-modality-select')?.value || '',
      stage:    document.getElementById('dkn-stage-drop-select')?.value || ''
    };
  }

  function _applyFilters(filters) {
    if (!filters) return;
    const set = (id, val) => {
      const el = document.getElementById(id);
      if (el && val !== undefined) el.value = val;
    };
    set('dkn-ta-select',         filters.ta);
    set('dkn-ind-select',        filters.ind);
    set('dkn-target-select',     filters.target);
    set('dkn-modality-select',   filters.modality);
    set('dkn-stage-drop-select', filters.stage);
    // Trigger filter re-render if function exists
    if (typeof dknApplyFilters === 'function') dknApplyFilters();
    else if (typeof dknSetTaDrop === 'function' && filters.ta) dknSetTaDrop(document.getElementById('dkn-ta-select'));
  }

  function _formatMeta(view) {
    const parts = [view.tab];
    if (view.filters?.stage) parts.push(view.filters.stage);
    if (view.filters?.ind) parts.push(view.filters.ind);
    if (view.savedAt) parts.push(view.savedAt.replace(/^\d{4}-/, '').replace('-', '/'));
    return parts.filter(Boolean).join(' · ');
  }

  window._renderSavedViews = function() {
    const body = document.getElementById('svp-body');
    if (!body) return;
    const views = _getSavedViews();
    if (!views.length) {
      body.innerHTML = '<div class="svp-empty">No saved views yet.<br>Navigate to a tab, set filters, then click<br>"+ Save current view".</div>';
      return;
    }
    body.innerHTML = views.map(v =>
      `<div class="svp-row">
        <div class="svp-name" onclick="loadSavedView(${v.id})">${v.name}</div>
        <div class="svp-meta">${_formatMeta(v)}</div>
        <button class="svp-del" onclick="deleteSavedView(${v.id})" title="Remove">✕</button>
      </div>`
    ).join('');
  };

  window.openSavedViewsPanel = function() {
    window._renderSavedViews();
    document.getElementById('svp-overlay')?.classList.add('open');
  };

  window.closeSavedViewsPanel = function() {
    document.getElementById('svp-overlay')?.classList.remove('open');
  };

  window.saveCurrentView = function() {
    const name = prompt('Name this view (e.g. "Phase 3 IBD Watch"):');
    if (!name || !name.trim()) return;
    const views = _getSavedViews();
    views.push({
      id: Date.now(),
      name: name.trim(),
      tab: _currentTab(),
      filters: _currentFilters(),
      savedAt: new Date().toISOString().slice(0, 10)
    });
    _setSavedViews(views);
    window._renderSavedViews();
  };

  window.loadSavedView = function(viewId) {
    const views = _getSavedViews();
    const view = views.find(v => v.id === viewId);
    if (!view) return;
    // Switch to saved tab
    if (view.tab) {
      const btn = document.querySelector(`.tab-btn[onclick*="'${view.tab}'"]`);
      if (typeof switchTab === 'function') switchTab(view.tab, btn);
    }
    // Apply filters after short delay so tab renders first
    setTimeout(() => { _applyFilters(view.filters); }, 150);
    window.closeSavedViewsPanel();
  };

  window.deleteSavedView = function(viewId) {
    const views = _getSavedViews().filter(v => v.id !== viewId);
    _setSavedViews(views);
    window._renderSavedViews();
  };
})();
