// ── NAVIGATION DROPDOWN / ONTOLOGY MEGA-MENU ──────────────────────
// Extracted from app.js (Domain A2, §3 method — byte-identical relocation).
// Plain script: every function stays a browser global so app.js + inline
// onclick handlers keep working. Loads BEFORE app.js. Eval-time deps are only
// _sb / _sbFetchAll (core.js, loaded first); all app.js symbols it uses
// (switchTab, loadMoleculeTab, TAB_AREA_MAP, _areaPIs) are referenced at
// call-time (runtime), never at eval.
// ── Nav dropdown — hover open, 1-second grace on mouseleave ───
let _molCloseTimer = null;
(function() {
  const wrap = document.getElementById('mol-dd-wrap');
  const menu = document.getElementById('mol-dd-menu');
  if (!wrap || !menu) return;
  wrap.addEventListener('mouseenter', function() {
    if (_molCloseTimer) { clearTimeout(_molCloseTimer); _molCloseTimer = null; }
    // Close the folder navigator immediately
    if (_hierCloseTimer) { clearTimeout(_hierCloseTimer); _hierCloseTimer = null; }
    document.getElementById('hier-dd-menu')?.classList.remove('open');
    menu.classList.add('open');
  });
  wrap.addEventListener('mouseleave', function() {
    _molCloseTimer = setTimeout(function() {
      menu.classList.remove('open');
      _molCloseTimer = null;
    }, 1000);
  });
})();

// ══════════════════════════════════════════════════════════
//  HIERARCHY / ONTOLOGY DROPDOWN — LIVE SUPABASE (Phase E)
//  Hover-triggered cascading flyout. Data from Supabase.
//  Sub-panels are DOM children of their parent .hier-item so
//  CSS :hover propagates through — no JS hover bridge needed.
//
//  Data sources:
//    therapeutic_areas  — top-level TA nodes (7 rows)
//    indications        — indication nodes with disease_area FK (11 rows)
//    drug_indications   — drug counts per indication (246 rows)
//    drug_targets       — target assignment per drug (250+ rows)
//
//  tabId mapping — therapeutic_areas.id → dashboard tab:
// ══════════════════════════════════════════════════════════

// tabId = existing Meridian dashboard to navTo() on click.
// null  = no dashboard yet; clicking shows a "coming soon" toast.
const _HIER_TA_TAB_MAP = {
  gastroenterology: 'tl1a',       // TL1A × IL-23p19 tab (IBD)
  respiratory:      'tslp',       // TSLP × IL-33 tab
  dermatology:      'il4ra-tslp', // IL-4Rα × TSLP tab (Atopy)
  rheumatology:     null,         // no dashboard yet
  neurology:        'fcrn',       // FcRn Bispecific tab
  ophthalmology:    'igf1r-tshr', // IGF-1R × TSHR tab (TED)
  oncology:         'ace',        // BCMA × CD19 × CD3 tab
  immunology:       null,         // no dashboard yet
};
// Therapeutic area color palette
const _HIER_TA_COLOR_MAP = {
  gastroenterology: '#7c3aed',
  respiratory:      '#0891b2',
  dermatology:      '#c2410c',
  rheumatology:     '#b45309',
  neurology:        '#1d4ed8',
  ophthalmology:    '#0f766e',
  oncology:         '#dc2626',
  immunology:       '#64748b',
};
// indication.id → tabId (per-indication override)
const _HIER_IND_TAB_MAP = {
  uc:          'tl1a',
  cd:          'tl1a',
  asthma:      'tslp',
  copd:        'tslp',
  ad:          'il4ra-tslp',
  csu:         'il4ra-tslp',
  ted:         'igf1r-tshr',
  gmg:         'fcrn',
  cidp:        'fcrn',
  mm:          'ace',
  all:         'ace',
};
// drug_targets.target_id → tabId
const _HIER_TGT_TAB_MAP = {
  tl1a:    'tl1a',
  il23p19: 'tl1a',
  il4ra:   'il4ra-tslp',
  tslp:    'tslp',
  tslpr:   'tslp',
  fcrn:    'fcrn',
  igf1r:   'igf1r-tshr',
  tshr:    'igf1r-tshr',
  bcma:    'ace',
  cd19:    'ace',
  cd3:     'ace',
};
// Map target_id slug to display symbol
const _HIER_TGT_SYMBOL = {
  tl1a:    'TL1A',
  il23p19: 'IL-23p19',
  il4ra:   'IL-4Rα',
  tslp:    'TSLP',
  tslpr:   'TSLP-R',
  fcrn:    'FcRn',
  igf1r:   'IGF-1R',
  tshr:    'TSHR',
  bcma:    'BCMA',
  cd19:    'CD19',
  cd3:     'CD3',
  a4b7:    'α4β7',
  il13:    'IL-13',
  il33:    'IL-33',
  ige:     'IgE',
  il5ra:   'IL-5Rα',
  cd40:    'CD40',
  il1ab:   'IL-1α/β',
  il6r:    'IL-6R',
  il17a:   'IL-17A',
  tnf:     'TNF',
};

// disease_area string → human-readable DA label (one level below TA)
const _HIER_DA_LABEL = {
  ibd:              'IBD',
  gastroenterology: 'GI / IBD',
  respiratory:      'Airway Diseases',
  atopy:            'Atopic Disease',
  dermatology:      'Skin Diseases',
  ted:              'Thyroid Eye Disease',
  ophthalmology:    'Eye Diseases',
  autoimmune:       'Autoimmune',
  rheumatology:     'Musculoskeletal',
  neurology:        'Neuromuscular',
  hematology:       'Hematology',
  oncology:         'Oncology',
};

// indications.disease_area (legacy string) → therapeutic_areas.id
// Also used as per-indication-id overrides (checked first in lookup below)
const _HIER_LEGACY_TO_TA = {
  // disease_area values that match TA ids directly
  gastroenterology: 'gastroenterology',
  respiratory:      'respiratory',
  dermatology:      'dermatology',
  rheumatology:     'rheumatology',
  neurology:        'neurology',
  ophthalmology:    'ophthalmology',
  oncology:         'oncology',
  // legacy disease_area aliases
  ibd:              'gastroenterology',
  atopy:            'dermatology',
  ted:              'ophthalmology',
  autoimmune:       'rheumatology',
  hematology:       'neurology',   // waiha → FcRn/neurology umbrella
  // per-indication-id overrides (these take precedence — lookup checks ind.id first)
  gmg:                'neurology',
  cidp:               'neurology',
  nmosd:              'neurology',
  waiha:              'neurology',
  mm:                 'oncology',
  all:                'oncology',
  // DB indication IDs that differ from short aliases in _HIER_IND_TAB_MAP
  multiple_myeloma:   'oncology',
  chronic_urticaria:  'dermatology',
};

let _hierLiveData = null;  // cached tree array; null = not yet loaded
let _hierFetching = false; // guard against parallel fetches

// Navigator lookup — pre-computed target→drug, indication→drug, etc. mappings
// Loaded once alongside the navigator tree; enables O(1) set-based drug filtering.
window._navLookup = null;
(function _loadNavLookup() {
  fetch('./data/navigator_lookup.json?_v=' + Date.now())
    .then(r => r.ok ? r.json() : null)
    .then(data => { if (data) window._navLookup = data; })
    .catch(() => { /* non-fatal: falls back to string-match filter */ });
})();

// ── Async data fetcher — builds the tree from 4 Supabase tables ──
async function _hierFetchLiveData() {
  // _sb is a module-level const — not on window. Use it directly.
  if (typeof _sb === 'undefined') throw new Error('_sb not ready');

  const [r1, r2, r3, r4] = await Promise.all([
    _sb.from('therapeutic_areas').select('id,name,sort_order').eq('status','active').order('sort_order'),
    _sb.from('indications').select('id,name,abbreviation,disease_area').order('name'),
    // drug_indications / drug_targets exceed the 1000-row cap → paginate (was silently truncated)
    _sbFetchAll((f, t) => _sb.from('drug_indications').select('drug_id,indication_id').range(f, t)).then(d => ({ data: d })),
    _sbFetchAll((f, t) => _sb.from('drug_targets').select('drug_id,target_id').range(f, t)).then(d => ({ data: d })),
  ]);

  if (r1.error || r2.error) {
    throw r1.error || r2.error;
  }

  const taRows  = r1.data || [];
  const indRows = r2.data || [];
  const diRows  = r3.data || [];
  const dtRows  = r4.data || [];

  // Build: indication_id → Set<drug_id>
  const indDrugMap = {};
  diRows.forEach(r => {
    if (!indDrugMap[r.indication_id]) indDrugMap[r.indication_id] = new Set();
    indDrugMap[r.indication_id].add(r.drug_id);
  });

  // Build: drug_id → [target_id]
  const drugTargetMap = {};
  dtRows.forEach(r => {
    if (!drugTargetMap[r.drug_id]) drugTargetMap[r.drug_id] = [];
    drugTargetMap[r.drug_id].push(r.target_id);
  });

  // Group indications under their therapeutic area
  const taIndMap = {};
  indRows.forEach(ind => {
    // Check ind.id first (per-indication overrides), then disease_area string
    const taId = _HIER_LEGACY_TO_TA[ind.id] || _HIER_LEGACY_TO_TA[ind.disease_area];
    if (!taId) return;
    if (!taIndMap[taId]) taIndMap[taId] = [];
    taIndMap[taId].push(ind);
  });

  // Build tree: therapeutic_area → [indication nodes] (no intermediate disease-area level)
  const tree = taRows.map(ta => {
    const inds    = taIndMap[ta.id] || [];
    const taTabId = _HIER_TA_TAB_MAP[ta.id] || null;

    // Helper: build one indication node from a raw indication row
    function _mkIndNode(ind) {
      const drugSet  = indDrugMap[ind.id] || new Set();
      const total    = drugSet.size;
      const indTabId = _HIER_IND_TAB_MAP[ind.id] || taTabId;
      const tgtCount = {};
      drugSet.forEach(dId => {
        (drugTargetMap[dId] || []).forEach(tId => {
          tgtCount[tId] = (tgtCount[tId] || 0) + 1;
        });
      });
      const tgts = Object.entries(tgtCount)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 6)
        .map(([tId, n]) => ({
          id:    tId,
          name:  _HIER_TGT_SYMBOL[tId] || tId.toUpperCase().replace(/_/g,'-'),
          n,
          tabId: _HIER_TGT_TAB_MAP[tId] || indTabId,
        }));
      return { id: ind.id, abbr: ind.abbreviation || ind.id.toUpperCase().slice(0,6), name: ind.name, total, tabId: indTabId, tgts };
    }

    // Group raw indications by their disease_area field → DA-level buckets
    const daGroupInds = {};
    inds.forEach(ind => {
      const daKey = ind.disease_area || ta.id;
      if (!daGroupInds[daKey]) daGroupInds[daKey] = [];
      daGroupInds[daKey].push(ind);
    });

    // Count unique drugs across all indications under this TA
    const taDrugSet = new Set();
    inds.forEach(ind => (indDrugMap[ind.id] || new Set()).forEach(id => taDrugSet.add(id)));
    const taTotal = taDrugSet.size;

    // Build one DA node per distinct disease_area bucket, with a readable name
    const daNode = Object.entries(daGroupInds).map(([daKey, daInds]) => {
      const daLabel    = _HIER_DA_LABEL[daKey] || (daKey.charAt(0).toUpperCase() + daKey.slice(1));
      const daIndNodes = daInds.map(_mkIndNode).filter(n => n.total > 0);
      if (!daIndNodes.length) return null;
      const daDrugSet  = new Set();
      daInds.forEach(ind => (indDrugMap[ind.id] || new Set()).forEach(id => daDrugSet.add(id)));
      return {
        id:    ta.id + '-' + daKey,
        name:  daLabel,
        full:  daLabel,
        total: daDrugSet.size,
        tabId: taTabId,
        inds:  daIndNodes,
      };
    }).filter(Boolean).sort((a, b) => b.total - a.total);

    return {
      id:    ta.id,
      name:  ta.name,
      color: _HIER_TA_COLOR_MAP[ta.id] || '#64748b',
      total: taTotal,
      tabId: taTabId,
      das:   daNode,
    };
  }).filter(ta => ta.total > 0 || (taIndMap[ta.id] || []).length > 0);

  return tree;
}

// Track selection (expansion is purely CSS :hover now)
const hierState = {
  sel: null, // { ta, da, ind, tgt } — last clicked target
  built: false,
};

// ── Per-item 1-second grace period for sub-panels ─────────────
// mouseenter: open this sub-panel immediately; close any open siblings immediately
// mouseleave: wait 1 second, then close — mouse can return within that window
function hierAttachHover(item) {
  let timer = null;
  const sub = item.querySelector(':scope > .hier-sub-panel');
  if (!sub) return;

  item._hierForceClose = function() {
    if (timer) { clearTimeout(timer); timer = null; }
    sub.classList.remove('open');
  };

  item.addEventListener('mouseenter', function() {
    if (timer) { clearTimeout(timer); timer = null; }
    // Immediately close any open siblings so only one sub-panel shows at a time
    const parent = item.parentElement;
    if (parent) {
      parent.querySelectorAll(':scope > .hier-item').forEach(function(sib) {
        if (sib !== item && sib._hierForceClose) sib._hierForceClose();
      });
    }
    // Collapse any deeper panels already open within this item (going back a level)
    item.querySelectorAll('.hier-sub-panel.open').forEach(function(s) { s.classList.remove('open'); });
    sub.classList.add('open');
  });

  item.addEventListener('mouseleave', function() {
    timer = setTimeout(function() {
      sub.classList.remove('open');
      timer = null;
    }, 500);
  });
}

// ── Hover open / 1-second grace-period close ──────────────────
let _hierCloseTimer = null;
(function() {
  const wrap = document.getElementById('hier-dd-wrap');
  const menu = document.getElementById('hier-dd-menu');
  if (!wrap || !menu) return;
  wrap.addEventListener('mouseenter', function() {
    if (_hierCloseTimer) { clearTimeout(_hierCloseTimer); _hierCloseTimer = null; }
    // Close the DNA dropdown immediately
    if (_molCloseTimer) { clearTimeout(_molCloseTimer); _molCloseTimer = null; }
    document.getElementById('mol-dd-menu')?.classList.remove('open');
    if (!hierState.built) {
      hierBuildTree().then(() => { hierState.built = true; }).catch(console.error);
    }
    menu.classList.add('open');
  });
  wrap.addEventListener('mouseleave', function() {
    _hierCloseTimer = setTimeout(function() {
      menu.classList.remove('open');
      _hierCloseTimer = null;
    }, 500);
  });
})();

// ── Tree builder — nested DOM, hover handled purely by CSS :hover ──
// No timers. Hit area is enlarged physically: taller rows (11px padding),
// 6px top/bottom buffer inside sub-panels, and sub-panels overlap parent
// by 6px (left: calc(100% - 6px)) so there is never a physical gap.
//
// async: fetches Supabase on first call, caches in _hierLiveData.
// Subsequent calls (e.g. from hierSetSel) render synchronously from cache.
async function hierBuildTree() {
  const body = document.getElementById('hier-dd-body');
  if (!body) return;

  // If cache is empty and a fetch isn't already in progress, load from Supabase
  if (!_hierLiveData && !_hierFetching) {
    _hierFetching = true;
    body.innerHTML = '<div style="padding:14px 16px;font-size:11px;color:#94a3b8">Loading navigator…</div>';
    try {
      _hierLiveData = await _hierFetchLiveData();
    } catch(e) {
      console.error('hierBuildTree: Supabase fetch failed — navigator will be empty. Error:', e);
      _hierLiveData = [];
      body.innerHTML = '<div style="padding:14px 16px;font-size:11px;color:#ef4444">Navigator failed to load. Check console.</div>';
    }
    _hierFetching = false;
  }

  // If still fetching (parallel call), just return — first call will re-render
  if (_hierFetching) return;

  const data = _hierLiveData || [];
  body.innerHTML = '';
  data.forEach((ta, ti) => {
    if (ti > 0) body.appendChild(hierDivider());
    body.appendChild(hierMakeTA(ta));
  });
}

function hierDivider() {
  const d = document.createElement('div');
  d.className = 'hier-divider';
  return d;
}

// ── Navigation helper ──
// Navigates to the dashboard and closes the dropdown.
// If no tabId, shows a "dashboard coming soon" toast instead.
function hierNav(tabId, label) {
  if (tabId) {
    // Immediate close on deliberate selection — no delay
    if (_hierCloseTimer) { clearTimeout(_hierCloseTimer); _hierCloseTimer = null; }
    document.getElementById('hier-dd-menu')?.classList.remove('open');
    navTo(tabId);
    // Override the title bar with the selection breadcrumb path
    const s = hierState.sel;
    if (s) {
      const parts = [s.ta?.name, s.da?.name, s.ind?.name, s.tgt?.name].filter(Boolean);
      const nameEl = document.getElementById('tab-current-name');
      if (nameEl && parts.length) nameEl.textContent = parts.join(' › ');
    }
    // Apply target/indication filter to the PI component for this tab.
    // The component may not be loaded yet if this is the first visit — poll for up to 5s.
    _hierScheduleFilter(tabId, s);
  } else {
    hierShowNoTabToast(label);
  }
}

// Schedules a filter application after a hierarchy selection.
// Polls until the _areaPIs component for the tab is loaded (lazy-load may not be done yet).
function _hierScheduleFilter(tabId, sel) {
  const tgtName = sel?.tgt?.name || null;
  const indName = sel?.ind?.name || null;

  // Update filter chip visibility immediately
  _hierUpdateFilterChip(tgtName, indName);

  // If no actual filter to apply, just clear any existing filter and return
  if (!tgtName && !indName) {
    _areaPIs[tabId]?.applyTargetFilter(null, null);
    return;
  }

  let attempts = 0;
  const MAX = 25; // up to ~5 seconds (25 × 200ms)
  function _tryApply() {
    const pi = _areaPIs[tabId];
    if (pi && pi.loaded) {
      pi.applyTargetFilter(tgtName, indName);
      return;
    }
    if (++attempts < MAX) setTimeout(_tryApply, 200);
  }
  _tryApply();
}

// Shows/hides the filter chip in the title bar.
function _hierUpdateFilterChip(targetName, indicationName) {
  const chip  = document.getElementById('hier-filter-chip');
  const label = document.getElementById('hier-filter-chip-label');
  if (!chip || !label) return;
  if (targetName) {
    label.textContent = targetName + ' only';
    chip.style.display = 'inline-flex';
  } else if (indicationName) {
    label.textContent = indicationName + ' only';
    chip.style.display = 'inline-flex';
  } else {
    chip.style.display = 'none';
  }
}

// Called by the chip × and by hierClearSelection to reset all hier filters.
function applyHierFilterToActivePI(sel) {
  const tgtName = sel?.tgt?.name || null;
  const indName = sel?.ind?.name || null;
  _hierUpdateFilterChip(tgtName, indName);
  // Apply to all loaded PI components (covers the case where we don't know which tab is active)
  Object.values(_areaPIs).forEach(pi => {
    if (typeof pi.applyTargetFilter === 'function') {
      pi.applyTargetFilter(tgtName, indName);
    }
  });
}

// ── Level 1: Therapeutic Area ──
function hierMakeTA(ta) {
  const item = document.createElement('div');
  item.className = 'hier-item';

  const row = document.createElement('div');
  row.className = 'hier-row';
  row.style.cursor = ta.tabId ? 'pointer' : 'default';
  row.innerHTML = `
    <div class="hier-ta-dot" style="background:${ta.color}"></div>
    <div class="hier-row-name hier-ta-name">${ta.name}</div>
    <div class="hier-row-count">${ta.total}</div>
    <div class="hier-row-arrow">▶</div>
  `;
  row.addEventListener('click', (e) => {
    e.stopPropagation();
    hierSetSel({ta});
    hierNav(ta.tabId, ta.name);
  });

  const sub = document.createElement('div');
  sub.className = 'hier-sub-panel';
  ta.das.forEach((da, di) => {
    if (di > 0) sub.appendChild(hierDivider());
    sub.appendChild(hierMakeDA(ta, da));
  });

  item.appendChild(row);
  item.appendChild(sub);
  hierAttachHover(item);
  return item;
}

// ── Level 2: Disease Area ──
function hierMakeDA(ta, da) {
  const item = document.createElement('div');
  item.className = 'hier-item';

  const row = document.createElement('div');
  row.className = 'hier-row';
  row.title = da.full;
  row.style.cursor = da.tabId ? 'pointer' : 'default';
  row.innerHTML = `
    <div class="hier-row-name hier-da-name">${da.name}</div>
    <div class="hier-row-count">${da.total}</div>
    <div class="hier-row-arrow">▶</div>
  `;
  row.addEventListener('click', (e) => {
    e.stopPropagation();
    hierSetSel({ta, da});
    hierNav(da.tabId, da.name);
  });

  const sub = document.createElement('div');
  sub.className = 'hier-sub-panel';
  da.inds.forEach((ind, ii) => {
    if (ii > 0) sub.appendChild(hierDivider());
    sub.appendChild(hierMakeInd(ta, da, ind));
  });

  item.appendChild(row);
  item.appendChild(sub);
  hierAttachHover(item);
  return item;
}

// ── Level 3: Indication ──
function hierMakeInd(ta, da, ind) {
  const item = document.createElement('div');
  item.className = 'hier-item';

  const row = document.createElement('div');
  row.className = 'hier-row';
  row.style.cursor = ind.tabId ? 'pointer' : 'default';
  row.innerHTML = `
    <span class="hier-ind-abbr">${ind.abbr}</span>
    <div class="hier-row-name hier-ind-name">${ind.name}</div>
    <div class="hier-row-count">${ind.total}</div>
    <div class="hier-row-arrow">▶</div>
  `;
  row.addEventListener('click', (e) => {
    e.stopPropagation();
    hierSetSel({ta, da, ind});
    hierNav(ind.tabId, ind.name);
  });

  // Sub-panel: Targets (leaf level)
  const sub = document.createElement('div');
  sub.className = 'hier-sub-panel';

  const hd = document.createElement('div');
  hd.className = 'hier-sub-hd';
  hd.innerHTML = `
    <div class="hier-sub-hd-label">${da.name}</div>
    <div class="hier-sub-hd-name">${ind.name}</div>
  `;
  sub.appendChild(hd);

  ind.tgts.forEach(tgt => {
    const trow = document.createElement('div');
    const isSel = hierState.sel?.tgt?.id === tgt.id && hierState.sel?.ind?.id === ind.id;
    trow.className = 'hier-row hier-tgt-row' + (isSel ? ' selected-tgt' : '');
    trow.style.cursor = tgt.tabId ? 'pointer' : 'not-allowed';
    trow.innerHTML = `
      <div class="hier-tgt-dot"></div>
      <div class="hier-row-name hier-tgt-name">${tgt.name}</div>
      <div class="hier-row-count">${tgt.n}</div>
    `;
    trow.addEventListener('click', (e) => {
      e.stopPropagation();
      hierSetSel({ta, da, ind, tgt});
      hierNav(tgt.tabId, tgt.name);
    });
    sub.appendChild(trow);
  });

  item.appendChild(row);
  item.appendChild(sub);
  hierAttachHover(item);
  return item;
}

// ── Selection tracking ──────────────────────────────────
function hierSetSel(sel) {
  hierState.sel = sel;
  // Rebuild to update selected-tgt highlight, then update footer
  // hierBuildTree is async but renders synchronously from cache after first load
  hierState.built = false;
  hierBuildTree().then(() => { hierState.built = true; hierUpdateFooter(); }).catch(console.error);
}

function hierClearSelection() {
  hierState.sel = null;
  hierState.built = false;
  hierBuildTree().then(() => { hierState.built = true; hierUpdateFooter(); }).catch(console.error);
  // Clear all PI filters and hide the chip
  applyHierFilterToActivePI(null);
}

function hierUpdateFooter() {
  const path  = document.getElementById('hier-footer-path');
  const clear = document.getElementById('hier-footer-clear');
  if (!path) return;
  const s = hierState.sel;
  if (!s || !s.ta) {
    path.textContent = 'Hover to explore · click to select';
    path.className = 'hier-dd-footer-path';
    clear.className = 'hier-dd-footer-clear';
  } else {
    const parts = [s.ta.name];
    if (s.da)  parts.push(s.da.name);
    if (s.ind) parts.push(s.ind.abbr);
    if (s.tgt) parts.push(s.tgt.name);
    path.textContent = parts.join(' › ');
    path.className = 'hier-dd-footer-path has-sel';
    clear.className = 'hier-dd-footer-clear visible';
  }
}

function hierToast(msg, bg) {
  let t = document.getElementById('hier-toast');
  if (!t) {
    t = document.createElement('div');
    t.id = 'hier-toast';
    t.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);padding:9px 18px;border-radius:8px;font-size:12px;font-weight:700;z-index:9999;box-shadow:0 4px 20px rgba(0,0,0,0.3);pointer-events:none;transition:opacity 0.3s;';
    document.body.appendChild(t);
  }
  t.style.background = bg || '#0f1e32';
  t.style.color = 'white';
  t.textContent = msg;
  t.style.opacity = '1';
  clearTimeout(t._timer);
  t._timer = setTimeout(() => { t.style.opacity = '0'; }, 2400);
}
function hierShowSelectionToast(name) {
  hierToast('🎯 ' + name, '#0f1e32');
}
function hierShowNoTabToast(name) {
  hierToast('⏳ No dashboard yet for ' + name, '#475569');
}
// Prefetch hierarchy data so it's ready the first time the menu opens.
// hierBuildTree is async — data loads from Supabase and caches in _hierLiveData.
hierBuildTree().then(() => { hierState.built = true; }).catch(console.error);

function closeCenterDrugDD() {
  const dd = document.getElementById('center-drug-dd');
  const title = document.getElementById('tab-current-title');
  if (dd) dd.classList.remove('open');
  if (title) title.classList.remove('open');
}
function toggleCenterDrugDD(e) {
  const title = document.getElementById('tab-current-title');
  if (!title || !title.classList.contains('is-drug')) return;
  e && e.stopPropagation();
  const dd = document.getElementById('center-drug-dd');
  const isOpen = dd && dd.classList.contains('open');
  closeCenterDrugDD();
  if (!isOpen) {
    if (dd) dd.classList.add('open');
    title.classList.add('open');
  }
}
// Map tabId → nav icon button id
const NAV_ICON_MAP = {
  'home': 'nav-icon-home',
  'industry-insights': 'nav-icon-insights',
  'drugs-know': 'nav-icon-drugs',
  /* DEPRECATED 2026-06-06: 'pharma-intel': 'nav-icon-pharma' (tab retired) */
  'meridian-issue': 'nav-icon-meridian',
  'predictions': 'nav-icon-predictions',
  'reads': 'nav-icon-reads',
  'tl1a': 'mol-dd-btn', 'tslp': 'mol-dd-btn', 'il4ra-tslp': 'mol-dd-btn',
  'il4ra-ox40l': 'mol-dd-btn', 'igf1r-tshr': 'mol-dd-btn',
  'fcrn': 'mol-dd-btn', 'ace': 'mol-dd-btn',
  'homeprev': 'nav-icon-home',  /* 2026-06-19 (rec #9): Home Preview is now the default Home (🏠). */
  /* 2026-06-19 (rec #5): 'live' + 'atlas' consolidated into intel2 sub-views. */
  'intel2': 'nav-icon-intel2',
  /* 2026-06-19 (rec #8): admin/ops cluster lives behind the ⚙ Admin hub — all map to its icon. */
  'admin': 'nav-icon-admin',
  'discovery-queue': 'nav-icon-admin',
  'submitted-intel': 'nav-icon-admin',
  'program-board': 'nav-icon-admin',
  'ontology': 'nav-icon-admin',
  'ontology-explorer': 'nav-icon-admin',
  'audit': 'nav-icon-admin',
  /* DEPRECATED 2026-06-06: 'changes-feed': 'nav-icon-changes' (Activity Feed retired) */
};
function updateNavIconActive(tabId) {
  document.querySelectorAll('.nav-icon-btn').forEach(b => b.classList.remove('active'));
  const iconId = NAV_ICON_MAP[tabId];
  if (iconId) document.getElementById(iconId)?.classList.add('active');
}
function navTo(tabId) {
  const btn = document.querySelector(`.tab-btn[onclick*="'${tabId}'"]`);
  switchTab(tabId, btn);
  document.getElementById('mol-dd-menu')?.classList.remove('open');
  closeCenterDrugDD();
  updateNavIconActive(tabId);
  window.scrollTo({top: 0, behavior: 'smooth'});
  // Lazy-load molecule tab data on first visit
  if (typeof loadMoleculeTab === 'function' && TAB_AREA_MAP && TAB_AREA_MAP[tabId]) {
    loadMoleculeTab(tabId);
  }
}
// Close molecule dropdown and center drug dropdown when clicking outside
document.addEventListener('click', function(e) {
  const wrap = document.getElementById('mol-dd-wrap');
  if (wrap && !wrap.contains(e.target)) {
    document.getElementById('mol-dd-menu')?.classList.remove('open');
  }
  const title = document.getElementById('tab-current-title');
  if (title && !title.contains(e.target)) {
    closeCenterDrugDD();
  }
});

// ── Dynamic tab-bar sticky offset ─────────────────────────────
function fixTabBarTop() {
  const hdr = document.querySelector('.header');
  const tb  = document.querySelector('.tab-bar');
  if (!hdr || !tb) return;
  const hdrH = hdr.getBoundingClientRect().height;
  const tbH  = tb.getBoundingClientRect().height;
  tb.style.top = hdrH + 'px';
  // Pin dkn-master-wrap directly below header+tabbar using fixed positioning
  const wrap = document.querySelector('.dkn-master-wrap');
  if (wrap) wrap.style.top = (hdrH + tbH) + 'px';
  // Pin TL1A side pills just below header+tabbar
  const pillsOffset = hdrH + tbH + 10;
  document.querySelectorAll('.tl1a-pills-col').forEach(p => { p.style.top = pillsOffset + 'px'; });
  // Align all drug-tab dashboards with pill button tops — fixed 10px gap below tab bar
  document.querySelectorAll('.tab-pane .tl1a-layout').forEach(l => {
    l.style.paddingTop = '10px';
  });
}
fixTabBarTop();
window.addEventListener('resize', fixTabBarTop);
