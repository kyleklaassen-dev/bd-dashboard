// ══════════════════════════════════════════════════════════════════════════════
// COMPANY DATABASE — Slide-over profile panel
// Opens on "⎘" button click in Pharma Landscape rows for tracked companies.
// URL-addressable: #/company/{company_id}
// Queries: companies, company_areas, drugs, catalysts, deals, company_profiles
// ══════════════════════════════════════════════════════════════════════════════
(function() {
  'use strict';

  // ── Display maps ────────────────────────────────────────────────────────────
  const AREA_DISPLAY = {
    tl1a:'TL1A × IBD', tslp:'TSLP × Resp', il4ra:'IL-4Rα',
    fcrn:'FcRn', igf1r:'IGF1R × TED', tcell:'T-Cell', ibd:'IBD'
  };

  const OVERLAP_STYLE = {
    'Direct':     'background:#fef2f2;color:#991b1b;border:1px solid #fca5a5',
    'Adjacent':   'background:#fffbeb;color:#92400e;border:1px solid #fde68a',
    'Watch':      'background:#f8fafc;color:#475569;border:1px solid #e2e8f0',
    'Same-Space': 'background:#f5f3ff;color:#5b21b6;border:1px solid #c4b5fd',
  };

  const STAGE_STYLE = {
    'Approved':    'background:#1e3a5f;color:#fff',
    'Phase 3':     'background:#dcfce7;color:#166534',
    'Phase 2':     'background:#dbeafe;color:#1e40af',
    'Phase 1':     'background:#fef3c7;color:#92400e',
    'Preclinical': 'background:#f1f5f9;color:#475569',
  };

  const TIER_COLOR = { thin:'#dc2626', partial:'#d97706', strong:'#166534' };

  // PI table slug → Supabase company_id (inverse of PI_COMPANY_MAP)
  const PI_SLUG_TO_ID = {
    'us-lilly':'lilly','us-jnj':'jnj','us-novartis':'novartis','us-abbvie':'abbvie',
    'us-novonordisk':'novonordisk','us-astrazeneca':'astrazeneca','us-merck':'merck',
    'us-roche':'roche','us-amgen':'amgen','us-pfizer':'pfizer','us-bms':'bms',
    'us-sanofi':'sanofi','us-gilead':'gilead','us-vertex':'vertex','us-gsk':'gsk',
    'us-regeneron':'regeneron','us-takeda':'takeda','us-bayer':'bayer',
    'us-biogen':'biogen','us-moderna':'moderna',
    'cn-hengrui':'hengrui','cn-sinopharm':'sinopharm','cn-cspc':'cspc',
    'cn-wuxi-bio':'wuxi-bio','cn-beigene':'beone','cn-sino-biopharma':'sinobiopharm',
    'cn-hansoh':'hansoh','cn-innovent':'innovent','cn-fosun':'fosun',
    'cn-hutchmed':'hutchmed','cn-zailab':'zailab','cn-remegen':'remegen',
    'ai-absci':'absci','ai-generate':'generatebio',
  };

  // ── State ────────────────────────────────────────────────────────────────────
  let _activeId   = null;
  let _activeTab  = 'overview';
  let _coData     = null;
  let _panelOpen  = false;

  // ── Hash routing ─────────────────────────────────────────────────────────────
  window.addEventListener('hashchange', function() {
    var h = window.location.hash;
    var m = h.match(/^#\/company\/(.+)$/);
    if (m) {
      _openPanel(m[1], null);
    } else if (_panelOpen) {
      _dismissPanel(true);
    }
  });

  // ── Public API ────────────────────────────────────────────────────────────────
  window.openCOPanel = function(companyId, piRow) { _openPanel(companyId, piRow); };
  window.closeCOPanel = function() { _dismissPanel(false); };
  window.renderCOPanelTab = function(tab) {
    if (!_coData) return;
    _activeTab = tab;
    var body = document.querySelector('#co-panel .co-tab-body');
    if (body) { body.innerHTML = _buildTabContent(tab); body.scrollTop = 0; }
    document.querySelectorAll('#co-panel .co-tab-btn').forEach(function(b) {
      b.classList.toggle('co-tab-active', b.getAttribute('data-tab') === tab);
    });
  };

  // ── Open ──────────────────────────────────────────────────────────────────────
  function _openPanel(companyId, piRow) {
    _activeId  = companyId;
    _activeTab = 'overview';
    _coData    = null;
    _panelOpen = true;

    var panel   = document.getElementById('co-panel');
    var overlay = document.getElementById('co-overlay');
    if (!panel) return;

    // Push hash
    var target = '#/company/' + companyId;
    if (window.location.hash !== target) history.pushState(null, '', target);

    // Loading state
    panel.innerHTML = '<div class="co-panel-inner">'
      + '<div class="co-panel-hd"><div><div class="co-company-name">' + _esc(companyId) + '</div>'
      + '<div class="co-loading-msg">Fetching profile…</div></div>'
      + '<button class="co-close" onclick="closeCOPanel()">×</button></div></div>';

    overlay.style.display = 'block';
    panel.classList.add('open');
    document.body.style.overflow = 'hidden';

    _fetchData(companyId, piRow).then(function(data) {
      if (_activeId !== companyId) return; // panel changed before data arrived
      _coData = data;
      _renderPanel(data);
    }).catch(function(err) {
      console.error('CO panel error:', err);
      if (_activeId !== companyId) return;
      panel.innerHTML = '<div class="co-panel-inner"><div class="co-panel-hd">'
        + '<span style="color:#fca5a5">Error loading ' + _esc(companyId) + '</span>'
        + '<button class="co-close" onclick="closeCOPanel()">×</button></div></div>';
    });
  }

  // ── Dismiss ───────────────────────────────────────────────────────────────────
  function _dismissPanel(skipHash) {
    var panel   = document.getElementById('co-panel');
    var overlay = document.getElementById('co-overlay');
    if (!panel) return;
    panel.classList.remove('open');
    overlay.style.display = 'none';
    document.body.style.overflow = '';
    _activeId  = null;
    _coData    = null;
    _panelOpen = false;
    if (!skipHash && window.location.hash.startsWith('#/company/')) {
      history.pushState(null, '', window.location.pathname + window.location.search);
    }
  }

  // ── Fetch all data ────────────────────────────────────────────────────────────
  async function _fetchData(companyId, piRow) {
    var sb = (typeof _sb !== 'undefined') ? _sb : window._sb;
    if (!sb) throw new Error('Supabase client not available');

    // Read financials from existing PI table DOM row (no extra API call needed)
    var dom = {};
    if (piRow) {
      var cells = piRow.querySelectorAll('td');
      dom.mktCap  = cells[2] ? cells[2].textContent.trim() : null;
      dom.revenue = cells[3] ? cells[3].textContent.trim() : null;
      dom.rd      = cells[4] ? cells[4].textContent.trim() : null;
      dom.rdPct   = cells[5] ? cells[5].textContent.trim() : null;
    }

    var [compRes, areasRes, drugsRes, catsRes, dealsRes, profRes] = await Promise.all([
      sb.from('companies')
        .select('name,ticker,stock_price,ailux_angle,status')
        .eq('id', companyId).maybeSingle(),
      sb.from('company_areas')
        .select('area_id')
        .eq('company_id', companyId),
      sb.from('drugs')
        .select('id,display_name,target,stage,overlap,cls,indication_short,canonical_drug_id')
        .eq('company_id', companyId),
      sb.from('catalysts')
        .select('drug_id,catalyst_type,catalyst_date,label,sort_date')
        .eq('company_id', companyId)
        .order('sort_date', {ascending: true})
        .limit(12),
      sb.from('deals')
        .select('deal_date,deal_type,headline,total_usd_m')
        .eq('company_id', companyId)
        .order('deal_date', {ascending: false})
        .limit(5),
      sb.from('company_profiles')
        .select('area_id,platform_intelligence,bd_intelligence,vs_ailux,completeness_score,missing_fields')
        .eq('company_id', companyId),
    ]);

    return {
      companyId : companyId,
      company   : compRes.data  || { name: companyId, ticker: null, ailux_angle: null },
      areas     : (areasRes.data  || []).map(function(r){ return r.area_id; }),
      drugs     : drugsRes.data  || [],
      catalysts : catsRes.data   || [],
      deals     : dealsRes.data  || [],
      profiles  : profRes.data   || [],
      dom       : dom,
    };
  }

  // ── Render full panel ─────────────────────────────────────────────────────────
  function _renderPanel(d) {
    var panel = document.getElementById('co-panel');
    if (!panel) return;

    var company   = d.company;
    var areas     = d.areas;
    var profiles  = d.profiles;
    var dom       = d.dom;

    // Header
    var ticker = company.ticker
      ? ' <span class="co-ticker">' + _esc(company.ticker) + '</span>' : '';
    var stats = '';
    if (dom.mktCap)  stats += '<span class="co-stat"><span class="co-stat-lbl">Mkt Cap</span>' + _esc(dom.mktCap) + '</span>';
    if (dom.revenue) stats += '<span class="co-stat"><span class="co-stat-lbl">Revenue</span>' + _esc(dom.revenue) + '</span>';
    if (dom.rd)      stats += '<span class="co-stat"><span class="co-stat-lbl">R&amp;D</span>' + _esc(dom.rd)
                              + (dom.rdPct ? ' <span style="color:#93c5fd;font-size:10px">(' + _esc(dom.rdPct) + ')</span>' : '') + '</span>';

    var areaPills = areas.map(function(a){
      return '<span class="co-area-pill">' + _esc(AREA_DISPLAY[a] || a) + '</span>';
    }).join('');

    var ailux = company.ailux_angle
      ? '<div class="co-ailux"><span class="co-ailux-lbl">Ailux Angle</span>' + _esc(company.ailux_angle) + '</div>'
      : '';

    // Tabs: Overview + areas that have a company_profile row
    var profiledAreas = areas.filter(function(a){
      return profiles.some(function(p){ return p.area_id === a; });
    });
    var tabs = ['overview'].concat(profiledAreas);

    var tabBtns = tabs.map(function(t) {
      var label  = t === 'overview' ? '📊 Overview' : (_esc(AREA_DISPLAY[t] || t));
      var active = t === _activeTab ? ' co-tab-active' : '';
      return '<button class="co-tab-btn' + active + '" data-tab="' + t + '" onclick="renderCOPanelTab(\'' + t + '\')">' + label + '</button>';
    }).join('');

    panel.innerHTML = '<div class="co-panel-inner">'
      + '<div class="co-panel-hd">'
      +   '<div><div class="co-company-name">' + _esc(company.name || d.companyId) + ticker + '</div>'
      +   '<div class="co-financials">' + stats + '</div>'
      +   (areaPills ? '<div class="co-areas">' + areaPills + '</div>' : '')
      +   '</div>'
      +   '<button class="co-close" onclick="closeCOPanel()">×</button>'
      + '</div>'
      + ailux
      + '<div class="co-tab-bar">' + tabBtns + '</div>'
      + '<div class="co-tab-body">' + _buildTabContent(_activeTab) + '</div>'
      + '</div>';
  }

  // ── Tab content router ────────────────────────────────────────────────────────
  function _buildTabContent(tab) {
    if (!_coData) return '';
    if (tab === 'overview') return _overviewTab(_coData);
    var profile = _coData.profiles.find(function(p){ return p.area_id === tab; });
    return _areaTab(_coData, tab, profile);
  }

  // ── Overview tab ──────────────────────────────────────────────────────────────
  function _overviewTab(d) {
    var html = '';

    // Molecules
    if (d.drugs.length) {
      var rows = d.drugs.map(function(drug) {
        var ovStyle = OVERLAP_STYLE[drug.overlap] || 'background:#f8fafc;color:#475569';
        var stStyle = STAGE_STYLE[drug.stage]   || 'background:#f1f5f9;color:#475569';
        return '<tr>'
          + '<td class="co-td"><strong>' + _esc(_dknCleanName(drug.display_name || drug.id)) + '</strong>'
          + (drug.target ? '<br><span class="co-sub">' + _esc(drug.target) + '</span>' : '') + '</td>'
          + '<td class="co-td">' + (drug.stage   ? '<span class="co-badge" style="' + stStyle + '">' + _esc(drug.stage)   + '</span>' : '') + '</td>'
          + '<td class="co-td">' + (drug.overlap ? '<span class="co-badge" style="' + ovStyle + '">' + _esc(drug.overlap) + '</span>' : '') + '</td>'
          + '<td class="co-td co-sub">' + _esc(drug.indication_short || '') + '</td>'
          + '</tr>';
      }).join('');
      html += '<div class="co-section">'
        + '<div class="co-section-hd">💊 Molecules (' + d.drugs.length + ')</div>'
        + '<table class="co-table"><thead><tr>'
        + '<th class="co-th">Drug / Target</th><th class="co-th">Stage</th>'
        + '<th class="co-th">Overlap</th><th class="co-th">Indication</th>'
        + '</tr></thead><tbody>' + rows + '</tbody></table></div>';
    } else {
      html += '<div class="co-section"><div class="co-section-hd">💊 Molecules</div>'
        + '<div class="co-empty">No drugs in BD Platform for this company</div></div>';
    }

    // Catalysts — show upcoming first, fallback to latest
    var today    = new Date().toISOString().slice(0, 10);
    var upcoming = d.catalysts.filter(function(c){ return (c.sort_date || '') >= today; });
    var catList  = (upcoming.length ? upcoming : d.catalysts).slice(0, 6);
    if (catList.length) {
      var items = catList.map(function(c) {
        return '<div class="co-cat-row">'
          + '<span class="co-cat-date">' + _esc(c.catalyst_date || c.sort_date || '') + '</span>'
          + '<span class="co-cat-type">' + _esc(c.catalyst_type || '') + '</span>'
          + '<span class="co-cat-label">' + _esc(c.label || '') + '</span>'
          + '</div>';
      }).join('');
      html += '<div class="co-section"><div class="co-section-hd">📅 Catalysts' + (upcoming.length ? '' : ' (recent)') + '</div>' + items + '</div>';
    }

    // Deals
    if (d.deals.length) {
      var drows = d.deals.map(function(deal) {
        return '<div class="co-deal-row">'
          + '<span class="co-deal-date">' + _esc(deal.deal_date || '') + '</span>'
          + '<span class="co-deal-type">' + _esc(deal.deal_type || '') + '</span>'
          + '<span class="co-deal-hl">'  + _esc(deal.headline   || '') + '</span>'
          + (deal.total_usd_m ? '<span class="co-deal-val">$' + deal.total_usd_m + 'M</span>' : '')
          + '</div>';
      }).join('');
      html += '<div class="co-section"><div class="co-section-hd">🤝 Deals</div>' + drows + '</div>';
    }

    // BD intelligence summary from first available profile
    var bdProf = d.profiles.find(function(p){ return p.bd_intelligence || p.assessment || p.vs_ailux; });
    if (bdProf) {
      var bd       = bdProf.bd_intelligence || {};
      var assess   = bdProf.assessment      || '';
      var vsAilux  = bdProf.vs_ailux        || '';
      var areaLabel = AREA_DISPLAY[bdProf.area_id] || bdProf.area_id;
      var likelihood = bd.likelihood || bd.deal_likelihood || bd.likelihood_assessment || '';
      var rationale  = bd.rationale  || bd.bd_thesis       || bd.summary              || '';
      if (likelihood || rationale || assess || vsAilux) {
        html += '<div class="co-section">'
          + '<div class="co-section-hd">🎯 BD Assessment <span style="font-size:9px;font-weight:400;color:#64748b;letter-spacing:0">(' + _esc(areaLabel) + ')</span></div>'
          + (likelihood ? '<div class="co-bd-assess">' + _esc(likelihood) + '</div>' : '')
          + (rationale  ? '<div class="co-bd-text">'   + _esc(rationale)  + '</div>' : '')
          + (assess && !rationale ? '<div class="co-bd-text">' + _esc(assess) + '</div>' : '')
          + (vsAilux ? '<div class="co-kv" style="margin-top:6px"><span class="co-kv-lbl">vs Ailux</span><span class="co-kv-val">' + _esc(vsAilux) + '</span></div>' : '')
          + '</div>';
      }
    }

    if (!html) html = '<div class="co-empty">No BD Platform data for this company. Add it via company_areas in Supabase.</div>';
    return html;
  }

  // ── Per-area tab ──────────────────────────────────────────────────────────────
  function _areaTab(d, areaId, profile) {
    if (!profile) return '<div class="co-empty">No profile found for ' + _esc(AREA_DISPLAY[areaId] || areaId) + '</div>';

    var html = '';

    // Completeness score
    var score = profile.completeness_score;
    var tier  = profile.completeness_tier || '';
    if (score != null) {
      var color = TIER_COLOR[tier] || '#475569';
      html += '<div class="co-section">'
        + '<div class="co-section-hd">📊 Completeness Score</div>'
        + '<div class="co-score-row">'
        + '<span class="co-score-num" style="color:' + color + '">' + score + '</span>'
        + '<span class="co-score-tier" style="color:' + color + '">' + _esc(tier) + '</span>'
        + '<div class="co-score-bar"><div class="co-score-fill" style="width:' + Math.min(score,100) + '%;background:' + color + '"></div></div>'
        + '</div>'
        + _missingFields(profile.missing_fields)
        + '</div>';
    }

    // Platform intelligence
    var pi = profile.platform_intelligence || {};
    var piItems = [];
    if (pi.platform_thesis || pi.thesis)                piItems.push(['Platform Thesis',  pi.platform_thesis || pi.thesis]);
    if (pi.format)                                       piItems.push(['Format',           pi.format]);
    if (pi.modality)                                     piItems.push(['Modality',         pi.modality]);
    if (pi.differentiation || pi.differentiation_claim) piItems.push(['Differentiation',  pi.differentiation || pi.differentiation_claim]);
    if (pi.summary && !pi.platform_thesis)               piItems.push(['Summary',          pi.summary]);
    if (piItems.length) {
      html += '<div class="co-section"><div class="co-section-hd">🔬 Platform Intelligence</div>'
        + piItems.map(function(kv){
            return '<div class="co-kv"><span class="co-kv-lbl">' + _esc(kv[0]) + '</span>'
                 + '<span class="co-kv-val">' + _esc(String(kv[1])) + '</span></div>';
          }).join('')
        + '</div>';
    }

    // BD intelligence
    var bd     = profile.bd_intelligence || {};
    var bdItems = [];
    if (bd.likelihood || bd.deal_likelihood || bd.likelihood_assessment)
      bdItems.push(['Deal Likelihood', bd.likelihood || bd.deal_likelihood || bd.likelihood_assessment]);
    if (bd.rationale || bd.bd_thesis)  bdItems.push(['Rationale',     bd.rationale || bd.bd_thesis]);
    if (bd.strategic_fit)              bdItems.push(['Strategic Fit', bd.strategic_fit]);
    if (bd.deal_structure || bd.structure) bdItems.push(['Structure', bd.deal_structure || bd.structure]);
    if (profile.assessment)            bdItems.push(['Assessment',    profile.assessment]);
    if (profile.competitive_position)  bdItems.push(['Competitive Position', profile.competitive_position]);
    if (profile.vs_ailux)              bdItems.push(['vs Ailux',      profile.vs_ailux]);

    if (bdItems.length) {
      html += '<div class="co-section"><div class="co-section-hd">🎯 BD Intelligence</div>'
        + bdItems.map(function(kv){
            return '<div class="co-kv"><span class="co-kv-lbl">' + _esc(kv[0]) + '</span>'
                 + '<span class="co-kv-val">' + _esc(String(kv[1])) + '</span></div>';
          }).join('')
        + '</div>';
    }

    // Upcoming catalysts (area-level)
    var today    = new Date().toISOString().slice(0, 10);
    var upcoming = d.catalysts.filter(function(c){ return (c.sort_date || '') >= today; });
    var catList  = (upcoming.length ? upcoming : d.catalysts).slice(0, 5);
    if (catList.length) {
      html += '<div class="co-section"><div class="co-section-hd">📅 Catalysts</div>'
        + catList.map(function(c) {
            return '<div class="co-cat-row">'
              + '<span class="co-cat-date">' + _esc(c.catalyst_date || c.sort_date || '') + '</span>'
              + '<span class="co-cat-type">' + _esc(c.catalyst_type || '') + '</span>'
              + '<span class="co-cat-label">' + _esc(c.label || '') + '</span>'
              + '</div>';
          }).join('')
        + '</div>';
    }

    return html || '<div class="co-empty">Profile exists but fields are empty — run enrichment to populate.</div>';
  }

  // ── Missing fields ────────────────────────────────────────────────────────────
  function _missingFields(fields) {
    if (!fields || !fields.length) return '';
    var pills = fields.slice(0, 10).map(function(f){
      return '<span class="co-missing-pill">' + _esc(f) + '</span>';
    }).join('');
    return '<div class="co-missing-wrap"><span class="co-missing-lbl">Missing:</span>' + pills + '</div>';
  }

  // ── Escape HTML ───────────────────────────────────────────────────────────────
  function _esc(s) {
    if (s == null) return '';
    return String(s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  // ── Inject "⎘" profile buttons into PI table rows ────────────────────────────
  function _injectButtons() {
    document.querySelectorAll('.pi-main-row[onclick]').forEach(function(row) {
      var m = row.getAttribute('onclick').match(/'([^']+)'/);
      if (!m) return;
      var slug      = m[1];
      var companyId = PI_SLUG_TO_ID[slug];
      if (!companyId) return;

      var nameCell = row.querySelector('td:nth-child(2)');
      if (!nameCell || nameCell.querySelector('.co-profile-btn')) return;

      var btn = document.createElement('button');
      btn.className = 'co-profile-btn';
      btn.textContent = '⎘ Profile';
      btn.title = 'View BD Company Profile';
      btn.setAttribute('data-co-id', companyId);
      btn.onclick = (function(cid, r) {
        return function(e) { e.stopPropagation(); window.openCOPanel(cid, r); };
      })(companyId, row);
      nameCell.appendChild(btn);
    });
  }

  // ── Initialize ────────────────────────────────────────────────────────────────
  function _init() {
    _injectButtons();
    // Handle deep-link on initial page load
    var h = window.location.hash;
    if (h.startsWith('#/company/')) {
      var id = h.slice('#/company/'.length);
      window.openCOPanel(id, null);
    }
  }

  // Wait for DOM + slight delay so Supabase client is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function(){ setTimeout(_init, 150); });
  } else {
    setTimeout(_init, 150);
  }

})();

// ── Global link interceptor: replace all external link clicks with Google searches ──────────────
// Instead of navigating to a specific URL that may 404 or be paywalled, every external link
// opens a targeted Google search using the link's headline text (or nearest context).
// Links that already point to google.com (the 🔍 search buttons) pass through unchanged.
(function() {
  // Skip these — they're already searches, internal anchors, or mailto
  const SKIP_RE = /^(https?:\/\/(www\.)?google\.|mailto:|javascript:|#)/i;
  // Generic link labels that don't make good search queries
  const GENERIC_RE = /^(source|link|here|↗|→|view|read|more|open|🔍|[\s↗→.]+)$/i;

  function _bestQuery(anchor) {
    // 1. Use link text if it's a real headline/label
    const raw = (anchor.textContent || '').trim()
      .replace(/\s*↗\s*$/, '').replace(/^↗\s*/, '').trim();

    if (raw && raw.length > 10 && !GENERIC_RE.test(raw)) return raw.slice(0, 150);

    // 2. Walk up the DOM looking for a headline or label in the parent card/row
    const SELECTORS = [
      '.iif-headline',       // Industry Insights feed card
      '.ii-title',           // Old intel card
      '.pi-detail-cat-item', // Catalyst row — grab its full text
      '.pi-da-name',         // Drug row name
      '.pi-entity-name',     // Entity name
      '.deal-title',         // Deal title
      'strong',              // Any bolded label nearby
    ];
    let el = anchor.parentElement;
    for (let depth = 0; depth < 8 && el; depth++, el = el.parentElement) {
      for (const sel of SELECTORS) {
        const found = el.querySelector(sel);
        if (found) {
          const t = found.textContent.trim().replace(/\s*↗\s*$/, '').trim();
          if (t && t.length > 8) return t.slice(0, 150);
        }
      }
    }

    // 3. Fallback to whatever text the link has, or the raw domain from href
    if (raw && raw.length > 3) return raw;
    try {
      const u = new URL(anchor.href);
      // Extract path segments as a last-resort hint
      const seg = u.pathname.replace(/[-_/]+/g,' ').trim();
      return (u.hostname + (seg.length > 3 ? ' ' + seg : '')).slice(0, 120);
    } catch(_) { return 'pharma biotech news'; }
  }

  document.addEventListener('click', function(e) {
    // DISABLED 2026-06-08 (Kyle): this capture-phase handler used to hijack EVERY stored
    // source link into a Google "verification" search (unless data-trusted), which is why
    // clicking a source/PDF link searched the web instead of opening the document. Kyle
    // wants the direct link we have on file in every case, so source links now navigate
    // directly. Left as a no-op so call sites and SKIP_RE/_bestQuery refs don't break.
    return;
  }, true); // capture phase: fires before any stopPropagation in bubble phase
})();
