// HOME WELCOME (deprecated old Home tab) — live clock + full-DB counter + 90-day catalyst
// calendar + BD-today panels, polling every 60s. Extracted from app.js (Phase 4 split 2026-06-19).
// Self-contained IIFE (all _hw* state private). Calls registerTab('home') at eval time, so this
// MUST load AFTER app.js (where registerTab/TAB_REGISTRY are defined). The live landing is
// Home Preview (home_preview.js); this only runs if a user opens the deprecated 'home' tab.

// ── Home Welcome — Live Clock + Full-Database Counter (polls every 60s) ──────
(function() {

  // Every confirmed table in Supabase (verified live, May 2026)
  const ALL_TABLES = [
    'drugs','companies','trials','intel','deals','catalysts','news_articles','entity_edges',
    'drug_targets','drug_indications','drug_areas','drug_area_scores',
    'drug_competitive_scores','drug_validation_results','drug_aliases',
    'intel_companies','intel_areas',
    'competitive_signals','competitive_landscapes','mechanism_status','molecule_intelligence',
    'trial_registries','validation_tests',
    'company_aliases','company_areas',
    'indications','indication_aliases','targets','target_pairs',
    'modalities',/* 'disease_areas' removed Session 80 — code retirement */'area_metadata',
    'ailux_positions','research_queue','geographic_approvals','submitted_intel',
    'trial_facts','publications','kols','drug_sources',
  ];

  const BREAKDOWN = [
    { tbl:'drugs',        l:'Drugs'         },
    { tbl:'companies',    l:'Companies'     },
    { tbl:'catalysts',    l:'Catalysts'     },
    { tbl:'trial_facts',  l:'Trials'        },
    { tbl:'publications', l:'Publications'  },
    { tbl:'kols',         l:'KOLs'          },
    { tbl:'entity_edges', l:'Graph edges'   },
    { tbl:'drug_sources', l:'Sourced facts' },
  ];

  let _hwClockTimer   = null;
  let _hwPollTimer    = null;
  let _hwCurrentTotal = 0;
  let _hwFirstLoad    = true;

  function _hwFmt(n) { return n.toLocaleString('en-US'); }

  // ── Clock ─────────────────────────────────────────────────────────
  function _hwUpdateClock() {
    const now = new Date();
    const dEl = document.getElementById('hw-date-line');
    const tEl = document.getElementById('hw-time-line');
    if (dEl) dEl.textContent = now.toLocaleDateString('en-US', { weekday:'long', year:'numeric', month:'long', day:'numeric' });
    if (tEl) tEl.textContent = now.toLocaleTimeString('en-US', { hour:'numeric', minute:'2-digit', second:'2-digit', hour12:true });
  }

  // ── Each element gets its own independent animation ───────────────
  function _hwAnimTo(el, from, to, duration, delay) {
    if (!el) return;
    setTimeout(() => {
      const start = performance.now();
      let rafId = null;
      function tick(now) {
        const p = Math.min((now - start) / duration, 1);
        const eased = p < 0.5 ? 4*p*p*p : 1 - Math.pow(-2*p+2, 3)/2;
        el.textContent = _hwFmt(Math.round(from + (to - from) * eased));
        if (p < 1) rafId = requestAnimationFrame(tick);
      }
      rafId = requestAnimationFrame(tick);
    }, delay || 0);
  }

  // ── Fetch every table count via _sb (the existing Supabase client) ─
  async function _hwFetchCounts() {
    const results = await Promise.allSettled(
      ALL_TABLES.map(t => _sb.from(t).select('*', { count:'exact', head:true }))
    );
    const map = {};
    results.forEach((r, i) => {
      map[ALL_TABLES[i]] = (r.status === 'fulfilled' ? (r.value.count || 0) : 0);
    });
    return map;
  }

  // ── Render breakdown strip (first time only) ───────────────────────
  function _hwRenderBreakdown(map) {
    const bd = document.getElementById('hw-breakdown');
    if (!bd || bd.dataset.rendered) return;
    bd.dataset.rendered = '1';
    bd.innerHTML = BREAKDOWN.map((x, i) => `
      <div class="hw-bd-item" style="transition-delay:${i*70+600}ms">
        <div class="hw-bd-num">0</div>
        <div class="hw-bd-lbl">${x.l}</div>
      </div>`).join('');
    requestAnimationFrame(() => {
      bd.querySelectorAll('.hw-bd-item').forEach((item, i) => {
        setTimeout(() => {
          item.classList.add('visible');
          _hwAnimTo(item.querySelector('.hw-bd-num'), 0, map[BREAKDOWN[i].tbl] || 0, 280, 0);
        }, i * 70 + 600);
      });
    });
  }

  // ── Update breakdown on subsequent polls ───────────────────────────
  function _hwUpdateBreakdown(map) {
    const bd = document.getElementById('hw-breakdown');
    if (!bd) return;
    bd.querySelectorAll('.hw-bd-item').forEach((item, i) => {
      const numEl = item.querySelector('.hw-bd-num');
      if (!numEl) return;
      const cur  = parseInt(numEl.textContent.replace(/,/g,''), 10) || 0;
      const next = map[BREAKDOWN[i].tbl] || 0;
      if (next !== cur) _hwAnimTo(numEl, cur, next, 800, 0);
    });
  }

  // ── Main refresh ───────────────────────────────────────────────────
  async function _hwRefresh(isFirst) {
    try {
      const map   = await _hwFetchCounts();
      const total = Object.values(map).reduce((s, n) => s + n, 0);
      const totalEl = document.getElementById('hw-count-num');
      const lbl     = document.getElementById('hw-count-label');
      if (isFirst) {
        _hwAnimTo(totalEl, 0, total, 3500, 500);
        _hwRenderBreakdown(map);
      } else {
        _hwAnimTo(totalEl, _hwCurrentTotal, total, 1200, 0);
        _hwUpdateBreakdown(map);
      }
      _hwCurrentTotal = total;
      if (lbl) lbl.textContent = '';
    } catch(e) {
      console.warn('[HomeWelcome]', e);
    }
  }

  // ── Graph metric tiles (static counts from last compute — 2026-05-27) ─────────
  function _hwLoadBDMetrics() {
    // Static graph metrics — recomputed each session via pg_stat_user_tables
    // total_data_points = sum of all table rows; total_connections = sum of all junction/edge tables
    // intelligence_signals = intelligence_discoveries(19) + company_pipeline_gaps(25) + bd_readiness_composite(13)
    const metricsEl = document.getElementById('hw-bd-metrics');
    if (metricsEl) setTimeout(() => metricsEl.classList.add('visible'), 1200);
  }

  // ── BD Today widget ────────────────────────────────────────────────
  async function loadBDToday() {
    const anchor = document.getElementById('bd-today-anchor');
    if (!anchor || typeof _sb === 'undefined') return;
    try {
      const todayISO  = new Date().toISOString().split('T')[0];
      const plus30    = new Date(Date.now() + 30*24*60*60*1000).toISOString().split('T')[0];
      const [catRes, drugRes] = await Promise.all([
        _sb.from('catalyst_calendar')
          .select('drug_id,event_name,expected_date,source_url')
          .eq('verified', true)
          .gte('expected_date', todayISO)
          .lte('expected_date', plus30)
          .eq('is_past', false)
          .order('expected_date', { ascending: true })
          .limit(5),
        // fallback: catalysts table if catalyst_calendar is empty/missing
        _sb.from('catalysts')
          .select('company_id,catalyst_name:label,sort_date,area_id,source_url,companies(name)')
          .gte('sort_date', todayISO)
          .lte('sort_date', plus30)
          .eq('resolved', false)
          .order('sort_date', { ascending: true })
          .limit(5),
      ]);

      // Prefer catalyst_calendar rows; fall back to catalysts table
      const todayMs = Date.now();
      let items = [];
      if (catRes.data && catRes.data.length) {
        items = (catRes.data||[]).map(c => {
          const d = new Date(c.expected_date + 'T12:00:00Z');
          const daysUntil = Math.ceil((d - todayMs) / (24*60*60*1000));
          const priColor = c.call_priority === 'call_now' ? '#dc2626' : c.call_priority === 'monitor' ? '#ea580c' : '#475569';
          const priLabel = (c.call_priority||'watch').replace(/_/g,' ');
          const _u = c.source_url || '';
          const _inner = `<div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:10px;">
            <div style="width:42px;text-align:center;flex-shrink:0;">
              <div style="font-size:15px;font-weight:700;color:#F4A261;">${daysUntil}</div>
              <div style="font-size:9px;color:#8BA3B8;">days</div>
            </div>
            <div style="flex:1;min-width:0;">
              <div style="font-size:13px;color:#E8F4FD;font-weight:600;">${c.event_name||'Catalyst'}</div>
            </div>
            ${_u ? '<div style=\'flex-shrink:0;color:#7EC8A4;font-size:13px;align-self:center;\'>\u2197</div>' : ''}
          </div>`;
          return _u ? `<a href="${_u}" target="_blank" rel="noopener" style="text-decoration:none;display:block;">${_inner}</a>` : _inner;
        });
      } else if (catRes.error && drugRes.data && drugRes.data.length) {
        items = (drugRes.data||[]).map(c => {
          const d = new Date((c.sort_date||'') + 'T12:00:00Z');
          const daysUntil = Math.ceil((d - todayMs) / (24*60*60*1000));
          const coName = c.companies?.name || c.company_id || '—';
          return `<div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:10px;">
            <div style="width:42px;text-align:center;flex-shrink:0;">
              <div style="font-size:15px;font-weight:700;color:#F4A261;">${daysUntil}</div>
              <div style="font-size:9px;color:#8BA3B8;">days</div>
            </div>
            <div style="flex:1;min-width:0;">
              <div style="font-size:13px;color:#E8F4FD;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${c.catalyst_name||'Catalyst'}</div>
              <div style="font-size:11px;color:#8BA3B8;">${coName}</div>
            </div>
          </div>`;
        });
      }

      if (!items.length) return; // no upcoming catalysts — hide widget

      const dateStr = new Date().toLocaleDateString('en-US',{month:'long',day:'numeric'});
      anchor.innerHTML = `<div class="bd-today-card">
        ${items.join('')}
      </div>`;
    } catch(e) {
      console.warn('[BDToday]', e);
    }
  }

  // ── Indication Priority widget ─────────────────────────────────────
  // Renders top 5 indication priorities on the home page.
  // Data source: indication_priority_scores table (if present) or
  // built-in static data derived from indication_priority_scores.json rankings.
  // Composite formula (v2): unmet×0.20 + fit×0.25 + wspace×0.15 + window_urgency×0.20
  //   + biology×0.10 + regulatory×0.05 + stratifiability×0.05
  async function loadIndicationPriority() {
    const anchor = document.getElementById('ind-priority-anchor');
    if (!anchor) return;

    // Static fallback data — new v2 ranking (2026-05-29)
    // Rank order: gMG(1), CIDP(2), CD(3), UC(4), MG-broad(5),
    //             Sjogren(6), TL1A-area(7), FcRn-area(8), SLE(9), IBD(10)...
    // Key insight: gMG rises to #1 because it is the ONLY indication with
    // validated biology (10) + established FDA endpoint (10) + perfect biomarker (AChR Ab+, 10)
    // Sjogren's drops 5 places: window is wide open (9) but biology contested,
    // endpoint not FDA-established, and no validated stratification biomarker.
    const STATIC_PRIORITIES = [
      { id:"gmg",      rank:1, name:"Generalized Myasthenia Gravis", fit:10, wspace:8, unmet:8,  wind:8, bio:10, reg:10, strat:10, composite:8.90, bfr:30.0, patients:90000,  progs:["alx005"], rationale:"FcRn mechanism fully validated (3+ approved drugs). MG-ADL is FDA gold standard. AChR Ab+ = 85% of patients — perfectly stratifiable at baseline.", tooltip:"Why #1: Window urgency=8 (no FcRn bispecific in gMG Phase 2 — bispecific niche is open) · Biology validated (efgartigimod, rozanolixizumab, nipocalimab all approved) · Endpoint established (MG-ADL is FDA gold standard) · Biomarker: AChR Ab+ = ~85% of gMG, perfectly stratifiable at baseline" },
      { id:"cidp",     rank:2, name:"CIDP",                          fit:10, wspace:9, unmet:8,  wind:9, bio:8,  reg:7,  strat:6,  composite:8.70, bfr:35.0, patients:40000,  progs:["alx005"], rationale:"Highest window urgency of any indication (9). Efgartigimod approved (mono) but bispecific white space is completely unchallenged — no competitor in Phase 2.", tooltip:"Why #2: Window urgency=9 (no FcRn bispecific in CIDP Phase 2; efgartigimod mono approved, bispecific space completely open) · FcRn mechanism validated by clinical data · INCAT disability score established, FDA-accepted · Anti-NF155 antibody subset exists; clinical severity stratification possible" },
      { id:"cd",       rank:3, name:"Crohn's Disease",               fit:10, wspace:7, unmet:9,  wind:7, bio:9,  reg:8,  strat:7,  composite:8.40, bfr:45.0, patients:780000, progs:["alx001"], rationale:"20% SoC remission — worst tracked. TL1A ARTEMIS-CD Phase 2b data validates mechanism. SPY072 Phase 1b sets 18-24 month window.", tooltip:"Why #3: Window urgency=7 (SPY072 TL1A×IL-23 Phase 1b active, 18-24mo window) · Biology validated (TL1A ARTEMIS-CD Phase 2b; IL-23 multiple Phase 3 trials) · CDAI + endoscopic endpoints established, FDA-precedented · Biomarker emerging (fecal calprotectin, TL1A-high expressors, fibrotic phenotype)" },
      { id:"uc",       rank:4, name:"Ulcerative Colitis",             fit:10, wspace:7, unmet:8,  wind:6, bio:10, reg:10, strat:8,  composite:8.25, bfr:40.0, patients:900000, progs:["alx001"], rationale:"Endoscopic remission is FDA gold standard. TL1A mechanism validated by ARTEMIS Phase 2b. Window compressing — duvakitug Phase 3 H2 2026.", tooltip:"Why #4: Window urgency=6 (SPY072 Phase 1b active; duvakitug Ph3 H2 2026 — 12-18mo window) · TL1A mechanism FDA-validated in UC via ARTEMIS Phase 2b · Endoscopic remission is FDA gold standard (Mayo score established) · Fecal calprotectin, TL1A-high expressors as strong baseline stratifiers" },
      { id:"mg",       rank:5, name:"Myasthenia Gravis (Broad)",      fit:8,  wspace:8, unmet:8,  wind:8, bio:9,  reg:9,  strat:8,  composite:8.15, bfr:30.0, patients:36000,  progs:["alx005"], rationale:"Bispecific white space mirrors gMG. AChR Ab stratification well-established. eculizumab/efgartigimod failures define refractory subgroup addressable by next-gen bispecific.", tooltip:"Why #5: Window urgency=8 (bispecific space open within broad MG; AChR-specific subgroup is addressable niche) · FcRn + complement mechanisms both clinically validated · MG-ADL + QMG established; mature regulatory pathway · AChR Ab+ stratification well-established; eculizumab failures define refractory subgroup" },
      { id:"sjogrens", rank:6, name:"Sjogren's Syndrome",             fit:9,  wspace:9, unmet:9,  wind:9, bio:5,  reg:4,  strat:3,  composite:8.05, bfr:60.0, patients:400000, progs:["alx002"], rationale:"Highest window urgency and white space. Critical caveat: biology contested (no validated animal model), endpoint not FDA-established, no validated stratification biomarker.", tooltip:"Why #6: Window urgency=9 (no Phase 2+ CD19 bispecific in Sjogren's — >24mo window) · Biology contested (no validated animal model; rituximab Phase 3 failures) · Endpoint contested (ESSDAI vs ESSPRI; no FDA gold standard) · No validated biomarker (RF/anti-SSA insufficient for stratification)" },
      { id:"tl1a",     rank:7, name:"TL1A Mechanism Area",            fit:10, wspace:7, unmet:9,  wind:5, bio:9,  reg:9,  strat:7,  composite:8.05, bfr:42.0, patients:2500000,progs:["alx001"], rationale:"TL1A mechanism FDA-validated. Window urgency penalized — monospecifics entering Phase 3 are defining the positioning before bispecifics reach Phase 2.", tooltip:"Why #7: Window urgency=5 (monospecifics entering Phase 3 — duvakitug Ph3 H2 2026 readout compresses differentiation window) · TL1A mechanism FDA-validated via ARTEMIS Phase 2b · Endoscopic remission gold standard in IBD · Fecal calprotectin + TL1A-high expressors as emerging stratification" },
    ];

    let rows = STATIC_PRIORITIES;

    // Try live data from Supabase if table exists
    if (typeof _sb !== 'undefined') {
      try {
        const { data, error } = await _sb
          .from('indication_priority_scores')
          .select('indication_priority_rank,indication_name,ailux_fit_score,competitive_white_space,unmet_need_score,biologic_failure_rate_pct,patient_count_us,alx_programs,priority_rationale,window_urgency_score,biology_validation_score,regulatory_pathway_clarity,patient_stratifiability,composite_score,tooltip_why')
          .order('indication_priority_rank', { ascending: true })
          .limit(7);
        if (!error && data && data.length) {
          rows = data.map(d => ({
            id: d.indication_id,
            rank: d.indication_priority_rank,
            name: d.indication_name,
            fit: d.ailux_fit_score,
            wspace: d.competitive_white_space,
            unmet: d.unmet_need_score,
            wind: d.window_urgency_score || null,
            bio: d.biology_validation_score || null,
            reg: d.regulatory_pathway_clarity || null,
            strat: d.patient_stratifiability || null,
            composite: d._composite_score || null,
            bfr: d.biologic_failure_rate_pct,
            patients: d.patient_count_us,
            progs: d.alx_programs || [],
            rationale: d.priority_rationale || '',
            tooltip: d.tooltip_why || '',
          }));
        }
      } catch(_) { /* use static fallback */ }
    }

    function _progPill(progs) {
      if (!progs || !progs.length) return '';
      if (progs.length > 1) return `<span class="ind-alx-pill ind-alx-multi">ALX Multi</span>`;
      const p = progs[0];
      return `<span class="ind-alx-pill ind-alx-${p}">${p.toUpperCase()}</span>`;
    }

    function _unmetBadge(score) {
      const cls = score >= 9 ? 'ind-unmet-high' : score >= 7 ? 'ind-unmet-mid' : 'ind-unmet-low';
      const lbl = score >= 9 ? 'High urgency' : score >= 7 ? 'Significant' : 'Moderate';
      return `<span class="ind-unmet-badge ${cls}">${lbl} ${score}/10</span>`;
    }

    function _wspaceDot(score) {
      const cls = score >= 8 ? 'ind-wspace-high' : score >= 6 ? 'ind-wspace-mid' : 'ind-wspace-low';
      const tip = score >= 8 ? 'Open white space' : score >= 6 ? 'Some competition' : 'Crowded';
      return `<span class="ind-wspace-dot ${cls}" title="${tip} (${score}/10)"></span>`;
    }

    function _rankBadge(rank) {
      const rankCls = rank <= 3 ? ` rank-${rank}` : '';
      return `<div class="ind-rank-badge${rankCls}">${rank}</div>`;
    }

    function _fmtPatients(n) {
      if (!n) return '';
      if (n >= 1000000) return (n/1000000).toFixed(1) + 'M US patients';
      if (n >= 1000)    return Math.round(n/1000) + 'K US patients';
      return n + ' US patients';
    }

    function _windBadge(score) {
      if (!score) return '';
      const cls = score >= 8 ? 'ind-wind-open' : score >= 6 ? 'ind-wind-mid' : 'ind-wind-narrow';
      const lbl = score >= 8 ? 'Window open' : score >= 6 ? 'Window narrowing' : 'Window closing';
      return `<span class="ind-wind-badge ${cls}" title="Competitive window urgency: ${score}/10">${lbl}</span>`;
    }

    const rowsHtml = rows.map(r => {
      const tooltipAttr = r.tooltip ? ` title="${r.tooltip.replace(/"/g, '&quot;')}"` : '';
      return `
      <div class="ind-priority-row"${tooltipAttr} style="cursor:pointer;" onclick="_hwShowIndicationDetail('${r.id || r.name}')" data-ind-id="${r.id || r.name}">
        ${_rankBadge(r.rank)}
        <div style="flex:1;min-width:0;">
          <div class="ind-priority-name">${r.name}${r.composite ? `<span style="font-size:9px;color:#94a3b8;font-weight:400;margin-left:6px;">${r.composite.toFixed(2)}</span>` : ''}</div>
          <div class="ind-priority-meta">${r.rationale ? r.rationale.substring(0,95) + (r.rationale.length > 95 ? '…' : '') : _fmtPatients(r.patients)}</div>
        </div>
        <div style="display:flex;align-items:center;gap:6px;flex-shrink:0;">
          ${_wspaceDot(r.wspace)}
          ${r.wind ? _windBadge(r.wind) : _unmetBadge(r.unmet)}
          ${_progPill(r.progs)}
        </div>
      </div>`;
    }).join('');

    anchor.innerHTML = `<div class="ind-priority-card">
      <div class="ind-priority-hd">
        <span class="ind-priority-hd-title">Indication Priority — Top 7</span>
        <span class="ind-priority-hd-sub">Unmet need · Ailux fit · Window urgency · Biology validation · Endpoint clarity · Biomarker stratifiability</span>
      </div>
      ${rowsHtml}
      <div style="margin-top:10px;padding-top:8px;border-top:1px solid #f1f5f9;display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
        <span style="font-size:9px;color:#94a3b8;">White space: <span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#22c55e;vertical-align:middle;"></span> open  <span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#f59e0b;vertical-align:middle;margin-left:4px;"></span> some  <span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#ef4444;vertical-align:middle;margin-left:4px;"></span> crowded</span>
        <span style="font-size:9px;color:#94a3b8;">Click any row for full indication intelligence</span>
        <span style="margin-left:auto;font-size:9px;color:#94a3b8;">Composite v2 · 7 dimensions · Meridian 2026-05-29</span>
      </div>
    </div>`;
  }

  // ── Indication Detail Modal ────────────────────────────────────────
  window._hwShowIndicationDetail = async function(indicationId) {
    // Normalize id: strip leading 'alx' prefixes if accidentally passed as name
    const id = (indicationId || '').toLowerCase().replace(/\s+/g, '_');

    // Show the overlay immediately with a loading state
    const backdrop = document.getElementById('home-overlay-backdrop');
    const card = document.getElementById('home-overlay-card');
    const titleEl = document.getElementById('home-overlay-title');
    const body = document.getElementById('home-overlay-body');
    if (!card || !body) return;

    // Hide all other panels
    card.querySelectorAll('.home-panel').forEach(p => p.style.display = 'none');

    titleEl.textContent = 'Loading indication intelligence…';
    backdrop.classList.add('open');
    card.classList.add('open');

    // Fetch all 4 scoring tables + company map in parallel
    let win = null, bio = null, reg = null, strat = null, companyMap = [];
    if (typeof _sb !== 'undefined') {
      try {
        const [wRes, bRes, rRes, sRes, cmRes] = await Promise.all([
          _sb.from('indication_window_urgency').select('*').eq('indication_id', id).single(),
          _sb.from('indication_biology_validation').select('*').eq('indication_id', id).single(),
          _sb.from('indication_regulatory_clarity').select('*').eq('indication_id', id).single(),
          _sb.from('indication_patient_stratifiability').select('*').eq('indication_id', id).single(),
          _sb.from('indication_company_map').select('*').eq('indication_id', id).order('relevance_score', { ascending: false }),
        ]);
        win   = wRes.data;
        bio   = bRes.data;
        reg   = rRes.data;
        strat = sRes.data;
        companyMap = cmRes.data || [];
      } catch(_) { /* tables may not exist yet */ }
    }

    // Pull static row for name + scores fallback
    const staticRow = (typeof loadIndicationPriority !== 'undefined')
      ? null // can't easily access STATIC_PRIORITIES — use fetched data
      : null;

    const indName = (win && win.indication_name) || (bio && bio.indication_name) || id.toUpperCase();
    titleEl.textContent = indName + ' — Indication Intelligence';

    function _score(n, max) {
      if (n == null) return '<span style="color:#94a3b8">—</span>';
      const pct = Math.round((n / max) * 100);
      const col = pct >= 80 ? '#22c55e' : pct >= 60 ? '#f59e0b' : '#ef4444';
      return `<span style="font-weight:700;color:${col}">${n}/${max}</span>`;
    }

    function _pill(label, val) {
      if (!val) return '';
      const colors = { gold_standard:'#1a3f8f,#e8f0f8', established:'#065f46,#d1fae5', contested:'#92400e,#fef3c7',
        evolving:'#7e22ce,#f3e8ff', undefined:'#64748b,#f1f5f9', validated:'#065f46,#d1fae5',
        emerging:'#0369a1,#e0f2fe', exploratory:'#7e22ce,#f3e8ff', none:'#64748b,#f1f5f9',
        approved_drug:'#065f46,#d1fae5', phase3_positive:'#1a3f8f,#e8f0f8', phase2_positive:'#0369a1,#e0f2fe',
        phase1_signal:'#92400e,#fef3c7', preclinical_only:'#64748b,#f1f5f9',
        good:'#065f46,#d1fae5', limited:'#92400e,#fef3c7', poor:'#7f1d1d,#fee2e2', gold_standard_model:'#065f46,#d1fae5' };
      const [fg, bg] = (colors[val] || '64748b,#f1f5f9').split(',');
      return `<span style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600;background:${bg};color:#${fg.replace('#','')};margin-right:4px">${label}</span>`;
    }

    function _section(title, content) {
      return `<div style="margin-bottom:18px;">
        <div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:0.08em;color:#1e3a5f;margin-bottom:8px;padding-bottom:4px;border-bottom:2px solid #1a3f8f;">${title}</div>
        ${content}
      </div>`;
    }

    function _row(label, val) {
      if (!val && val !== 0) return '';
      return `<div style="display:flex;gap:8px;margin-bottom:5px;font-size:12px;">
        <span style="min-width:180px;color:#64748b;flex-shrink:0">${label}</span>
        <span style="color:#0d1f38;font-weight:500">${val}</span>
      </div>`;
    }

    // Build modal sections
    let html = `<div style="padding:0 4px;">`;

    // WINDOW URGENCY
    if (win) {
      const bispecTotal = (win.competing_bispecifics_phase1||0) + (win.competing_bispecifics_phase2||0) + (win.competing_bispecifics_phase3||0);
      html += _section('Competitive Window', `
        <div style="display:flex;align-items:baseline;gap:16px;margin-bottom:10px;flex-wrap:wrap;">
          <div><span style="font-size:10px;color:#64748b">Window Urgency</span><br>${_score(win.window_urgency_score, 10)}</div>
          <div><span style="font-size:10px;color:#64748b">Months Remaining</span><br><span style="font-weight:700;color:#0d1f38">${win.months_to_window_close || '—'}</span></div>
          <div><span style="font-size:10px;color:#64748b">Ailux Program</span><br><span style="font-weight:700;color:#2e6fb0">${(win.ailux_program||'').toUpperCase()}</span></div>
          <div><span style="font-size:10px;color:#64748b">Competing Bispecifics</span><br><span style="font-weight:700;color:#0d1f38">Ph1: ${win.competing_bispecifics_phase1||0} · Ph2: ${win.competing_bispecifics_phase2||0} · Ph3: ${win.competing_bispecifics_phase3||0}</span></div>
        </div>
        ${win.next_key_event ? `<div style="background:#fef3c7;border-left:3px solid #f59e0b;padding:8px 12px;border-radius:0 4px 4px 0;font-size:12px;margin-bottom:8px;"><span style="font-weight:700;color:#92400e">Key Window Event:</span> ${win.next_key_event}${win.next_event_date ? ` <span style="color:#94a3b8">(${win.next_event_date})</span>` : ''}</div>` : ''}
        ${win.window_narrative ? `<div style="font-size:12px;color:#334155;line-height:1.6">${win.window_narrative}</div>` : ''}
      `);
    }

    // BIOLOGY VALIDATION
    if (bio) {
      html += _section('Biology Validation', `
        <div style="display:flex;align-items:baseline;gap:16px;margin-bottom:10px;flex-wrap:wrap;">
          <div><span style="font-size:10px;color:#64748b">Validation Score</span><br>${_score(bio.biology_validation_score, 10)}</div>
          <div><span style="font-size:10px;color:#64748b">Proof of Concept</span><br>${_pill('', bio.proof_of_concept_type)}${(bio.proof_of_concept_type||'').replace(/_/g,' ')}</div>
          <div><span style="font-size:10px;color:#64748b">Preclinical Fidelity</span><br>${_score(bio.preclinical_model_fidelity, 10)} ${_pill(bio.preclinical_model_type||'', bio.preclinical_model_type)}</div>
          ${bio.pubmed_publication_count ? `<div><span style="font-size:10px;color:#64748b">PubMed Papers</span><br><span style="font-weight:700;color:#0d1f38">~${bio.pubmed_publication_count.toLocaleString()}</span></div>` : ''}
        </div>
        ${bio.key_validation_drug ? `<div style="background:#e8f0f8;border-left:3px solid #1a3f8f;padding:8px 12px;border-radius:0 4px 4px 0;font-size:12px;margin-bottom:8px;">
          <div style="font-weight:700;color:#1a3f8f;margin-bottom:2px">${bio.key_validation_drug}</div>
          <div style="color:#334155">${bio.key_validation_trial || ''}</div>
          <div style="color:#0d1f38;margin-top:2px;font-weight:500">${bio.key_validation_result || ''}</div>
        </div>` : ''}
        ${bio.animal_to_human_translation ? `<div style="font-size:11px;color:#64748b;line-height:1.5;font-style:italic">${bio.animal_to_human_translation}</div>` : ''}
        ${bio.biology_narrative ? `<div style="font-size:12px;color:#334155;line-height:1.6;margin-top:6px">${bio.biology_narrative}</div>` : ''}
      `);
    }

    // REGULATORY CLARITY
    if (reg) {
      html += _section('Regulatory Pathway', `
        <div style="display:flex;align-items:baseline;gap:16px;margin-bottom:10px;flex-wrap:wrap;">
          <div><span style="font-size:10px;color:#64748b">Pathway Clarity</span><br>${_score(reg.regulatory_pathway_clarity, 10)}</div>
          <div><span style="font-size:10px;color:#64748b">Endpoint Status</span><br>${_pill(reg.endpoint_status||'', reg.endpoint_status)}</div>
          ${reg.orphan_drug_eligible ? '<div><span style="font-size:10px;color:#64748b">Orphan Drug</span><br><span style="font-weight:700;color:#065f46">Eligible</span></div>' : ''}
          ${reg.breakthrough_therapy_eligible ? '<div><span style="font-size:10px;color:#64748b">Breakthrough Therapy</span><br><span style="font-weight:700;color:#065f46">Eligible</span></div>' : ''}
          ${reg.typical_phase3_size ? `<div><span style="font-size:10px;color:#64748b">Typical Ph3 Size</span><br><span style="font-weight:700;color:#0d1f38">n≈${reg.typical_phase3_size.toLocaleString()}</span></div>` : ''}
          ${reg.typical_phase3_duration_months ? `<div><span style="font-size:10px;color:#64748b">Ph3 Duration</span><br><span style="font-weight:700;color:#0d1f38">${reg.typical_phase3_duration_months} mo</span></div>` : ''}
        </div>
        ${reg.primary_endpoint ? _row('Primary Endpoint', reg.primary_endpoint) : ''}
        ${reg.fda_precedent_drug ? _row('FDA Precedent Drug', reg.fda_precedent_drug) : ''}
        ${reg.regulatory_narrative ? `<div style="font-size:12px;color:#334155;line-height:1.6;margin-top:8px">${reg.regulatory_narrative}</div>` : ''}
      `);
    }

    // PATIENT STRATIFIABILITY
    if (strat) {
      html += _section('Patient Stratifiability', `
        <div style="display:flex;align-items:baseline;gap:16px;margin-bottom:10px;flex-wrap:wrap;">
          <div><span style="font-size:10px;color:#64748b">Stratifiability</span><br>${_score(strat.patient_stratifiability, 10)}</div>
          <div><span style="font-size:10px;color:#64748b">Biomarker Status</span><br>${_pill(strat.biomarker_status||'', strat.biomarker_status)}</div>
          ${strat.biomarker_sensitivity_pct != null ? `<div><span style="font-size:10px;color:#64748b">Patient Capture</span><br><span style="font-weight:700;color:#0d1f38">${strat.biomarker_sensitivity_pct}%</span></div>` : ''}
          ${strat.enriched_trial_size_reduction_pct ? `<div><span style="font-size:10px;color:#64748b">Ph2 Size Reduction</span><br><span style="font-weight:700;color:#065f46">−${strat.enriched_trial_size_reduction_pct}%</span></div>` : ''}
        </div>
        ${strat.primary_biomarker ? _row('Primary Biomarker', strat.primary_biomarker) : ''}
        ${strat.non_responder_escape_pathway ? `<div style="background:#fee2e2;border-left:3px solid #ef4444;padding:8px 12px;border-radius:0 4px 4px 0;font-size:11px;margin:8px 0;"><span style="font-weight:700;color:#7f1d1d">Non-Responder Escape:</span> ${strat.non_responder_escape_pathway}</div>` : ''}
        ${strat.stratifiability_narrative ? `<div style="font-size:12px;color:#334155;line-height:1.6">${strat.stratifiability_narrative}</div>` : ''}
      `);
    }

    if (!win && !bio && !reg && !strat) {
      html += `<div style="padding:24px;text-align:center;color:#94a3b8;font-size:13px">Detailed scoring data not yet available for this indication.</div>`;
    }

    // KEY COMPANIES IN THIS INDICATION
    if (companyMap.length > 0) {
      const roleMeta = {
        validates_biology:  { label: 'Validates Biology', fg: '#065f46', bg: '#d1fae5' },
        competes_directly:  { label: 'Competes Directly', fg: '#7f1d1d', bg: '#fee2e2' },
        potential_partner:  { label: 'Potential Partner',  fg: '#1a3f8f', bg: '#e8f0f8' },
        licensing_target:   { label: 'Licensing Target',   fg: '#92400e', bg: '#fef3c7' },
        monitor:            { label: 'Monitor',             fg: '#64748b', bg: '#f1f5f9' },
      };
      const partnerMeta = {
        high:    { label: 'High',    fg: '#065f46', bg: '#d1fae5' },
        medium:  { label: 'Medium',  fg: '#1a3f8f', bg: '#e8f0f8' },
        low:     { label: 'Low',     fg: '#64748b', bg: '#f1f5f9' },
        conflict: { label: 'Conflict', fg: '#7f1d1d', bg: '#fee2e2' },
      };

      function _badge(val, map) {
        const m = map[val] || { label: val, fg: '#64748b', bg: '#f1f5f9' };
        return `<span style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700;background:${m.bg};color:${m.fg}">${m.label}</span>`;
      }

      const rows = companyMap.map(c => {
        const drugBit = c.key_drug_id
          ? `<div style="font-size:11px;color:#334155;margin-top:2px"><span style="font-weight:600">${c.key_drug_id.replace(/-/g,' ')}</span>${c.key_drug_stage ? ` · <span style="color:#64748b">${c.key_drug_stage}</span>` : ''}</div>`
          : '';
        const resultBit = c.key_drug_result
          ? `<div style="font-size:10px;color:#64748b;margin-top:1px;line-height:1.4;font-style:italic">${c.key_drug_result}</div>`
          : '';
        return `<div style="border:1px solid #e2e8f0;border-radius:6px;padding:10px 12px;margin-bottom:8px;">
          <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px;flex-wrap:wrap;">
            <div style="flex:1;min-width:0;">
              <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:4px;">
                <span style="font-size:13px;font-weight:700;color:#0d1f38">${c.company_id.toUpperCase()}</span>
                ${_badge(c.role, roleMeta)}
              </div>
              ${drugBit}
              ${resultBit}
              ${c.role_rationale ? `<div style="font-size:11px;color:#475569;margin-top:4px;line-height:1.5">${c.role_rationale}</div>` : ''}
            </div>
            <div style="text-align:right;flex-shrink:0;">
              <div style="font-size:9px;color:#94a3b8;margin-bottom:3px;text-align:right">Partnership</div>
              ${_badge(c.partnership_potential, partnerMeta)}
              <div style="font-size:10px;color:#94a3b8;margin-top:3px">Relevance: ${c.relevance_score}/10</div>
            </div>
          </div>
        </div>`;
      }).join('');

      html += _section('Key Companies in This Indication', rows);
    }

    html += `</div>`;

    // Inject into a dedicated panel inside the overlay body
    let detailPanel = document.getElementById('home-panel-ind-detail');
    if (!detailPanel) {
      detailPanel = document.createElement('div');
      detailPanel.className = 'home-panel';
      detailPanel.id = 'home-panel-ind-detail';
      detailPanel.style.cssText = 'padding:16px 20px;max-height:calc(100vh - 160px);overflow-y:auto;';
      body.appendChild(detailPanel);
    }
    detailPanel.innerHTML = html;
    detailPanel.style.display = 'block';
  }

  // ── Meridian Issue inline reader ──────────────────────────────────
  async function _hwLoadMeridianIssue() {
    const panel = document.getElementById('hw-issue-panel');
    const content = document.getElementById('hw-issue-content');
    if (!panel || !content) return;
    try {
      // Single source of truth: read the most recent issue from Supabase
      // (same source as the Meridian tab) so the home card never falls behind
      // the static meridian_today.html deploy.
      let html, issueDate;
      if (typeof _sb !== 'undefined' && _sb) {
        const { data: issues, error } = await _sb
          .from('meridian_issues')
          .select('issue_date, body_html')
          .order('issue_date', { ascending: false })
          .limit(1);
        if (error) throw error;
        if (issues && issues.length && issues[0].body_html) {
          html = issues[0].body_html;
          issueDate = issues[0].issue_date;
        }
      }
      // Fallback: static file if Supabase is unavailable or empty
      if (!html) {
        const resp = await fetch('meridian_today.html?v=' + Date.now());
        if (!resp.ok) throw new Error('not found');
        html = await resp.text();
      }
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, 'text/html');
      // Remove <style>, <script>, <head> cruft — grab body children
      const body = doc.body;
      // Remove any base tags that would affect links
      body.querySelectorAll('base').forEach(el => el.remove());
      // Scope links: entity links (drug/company) open the canonical card in-place;
      // everything else opens in a new tab. Entity links carry href="#" — if we
      // blindly set target=_blank they spawn an about:blank tab, so leave them alone.
      body.querySelectorAll('a').forEach(a => {
        const oc = a.getAttribute('onclick') || '';
        const isEntity = oc.includes('openDrugModal(') || oc.includes('openCompanyModal(');
        if (isEntity) {
          a.removeAttribute('target');
          a.style.cursor = 'pointer';
        } else if (a.getAttribute('href') && !a.getAttribute('href').endsWith('#')) {
          a.target = '_blank';
          a.rel = 'noopener';
        }
      });
      // Inject scoped styles to make the serif issue content look clean inside the card
      content.innerHTML = `<style>
        #hw-issue-content h1 { font-size:26px; font-weight:700; color:#1a3f8f; margin:0 0 8px 0; font-family:Georgia,serif; }
        #hw-issue-content h2 { font-size:20px; font-weight:700; color:#1a3f8f; margin:22px 0 6px 0; border-bottom:1px solid #dce6f7; padding-bottom:5px; font-family:Georgia,serif; }
        #hw-issue-content h3 { font-size:17px; font-weight:600; color:#1e3a5f; margin:16px 0 5px 0; font-style:italic; font-family:Georgia,serif; }
        #hw-issue-content p { margin:0 0 14px 0; font-size:16px; line-height:1.9; }
        #hw-issue-content .dateline { font-size:10px; color:#3d5166; letter-spacing:0.5px; text-transform:uppercase; font-family:Calibri,Helvetica,sans-serif; }
        #hw-issue-content .tagline { font-style:italic; font-size:12px; color:#3d5166; margin:0 0 14px 0; }
        #hw-issue-content hr.thick { border:none; border-top:2px solid #1a3f8f; margin:8px 0 4px 0; }
        #hw-issue-content hr.thin { border:none; border-top:1px solid #d0d9ea; margin:4px 0 16px 0; }
        #hw-issue-content a { color:#1a3f8f; text-decoration:none; border-bottom:1px solid #bfdbfe; }
        #hw-issue-content .bd-lens { border-left:3px solid #1a3f8f; background:#f0f4fb; padding:12px 16px; margin:14px 0; border-radius:0 4px 4px 0; font-size:12px; }
        #hw-issue-content .label { font-size:9px; font-weight:700; letter-spacing:2px; color:#1a3f8f; text-transform:uppercase; margin-bottom:6px !important; }
        #hw-issue-content table { width:100%; border-collapse:collapse; margin:10px 0 16px; font-size:11px; font-family:Calibri,Helvetica,sans-serif; }
        #hw-issue-content th { background:#1a3f8f; color:#fff; padding:7px 10px; text-align:left; }
        #hw-issue-content td { padding:6px 10px; border:1px solid #dce6f7; vertical-align:top; }
        #hw-issue-content tr:nth-child(even) td { background:#f5f8ff; }
        #hw-issue-content .closing { font-style:italic; color:#3d5166; font-size:12px; border-top:1px solid #d0d9ea; padding-top:14px; margin-top:24px; }
        #hw-issue-content .issue-meta { font-size:10px; color:#94a3b8; margin-top:20px; padding-top:10px; border-top:1px solid #e8edf5; font-family:Calibri,Helvetica,sans-serif; }
      </style>` + body.innerHTML;
      // Bridge: route entity-link clicks to the parent dashboard's canonical
      // modal. Capture phase + stopPropagation prevents the inline
      // onclick="openDrugModal(...)" (undefined here) from firing and stops the
      // href="#" navigation that was spawning a blank tab.
      if (!content._meridianBridgeBound) {
        content._meridianBridgeBound = true;
        content.addEventListener('click', function(ev) {
          const a = ev.target.closest('a');
          if (!a) return;
          const oc = a.getAttribute('onclick') || '';
          if (oc.includes('openDrugModal(') || oc.includes('openCompanyModal(')) {
            ev.preventDefault();
            ev.stopPropagation();
            const m = oc.match(/open(?:Drug|Company)Modal\(\s*['"]([^'"]+)['"]/);
            if (m) {
              try {
                if (oc.includes('openDrugModal')) openDrugEntityModal(m[1], m[1], null);
                else openCompanyEntityModal(m[1], m[1], 'meridian', m[1]);
              } catch(err) { console.warn('[hw-issue:bridge]', err); }
            }
            return false;
          }
          // Guard: bare href="#" anchors shouldn't jump the page
          const href = a.getAttribute('href') || '';
          if (href === '#' || href.endsWith('#')) ev.preventDefault();
        }, true);
      }
      panel.style.display = 'block';
      const dateEl = document.getElementById('hw-issue-date');
      if (dateEl) {
        const labelDate = issueDate ? new Date(issueDate + 'T12:00:00') : new Date();
        dateEl.textContent = labelDate.toLocaleDateString('en-US', {weekday:'long', month:'long', day:'numeric'});
      }
    } catch(e) {
      if (content) content.innerHTML = '<p style="color:#94a3b8;font-size:11px;padding:8px 0">Issue not yet generated today. Check back after 3 PM ET.</p>';
      if (panel) panel.style.display = 'block';
    }
  }

  // ── 90-Day BD Catalyst Calendar ──────────────────────────────────
  async function _hwLoadCatalystCalendar() {
    const section = document.getElementById('hw-cal-section');
    const body = document.getElementById('hw-cal-body');
    if (!section || !body || typeof _sb === 'undefined') return;
    try {
      const todayISO = new Date().toISOString().split('T')[0];
      const plus90   = new Date(Date.now() + 90*24*60*60*1000).toISOString().split('T')[0];
      // Merge the curated calendar (rich Ailux-impact rows) with the full catalysts table
      // (1,300+ source-linked events) so the 90-day view is comprehensive, not just the 25
      // hand-curated ones (Kyle 2026-06-08). Curated rows win on dedupe (drug_id+date).
      const SIGMAP = { high:'P1', medium:'P2', low:'P3' };
      const [calRes, mainRes] = await Promise.all([
        _sb.from('catalyst_calendar')
          .select('drug_id,company_id,event_name,expected_date,strategic_significance,ailux_impact,source_url')
          .eq('verified', true)
          .gt('expected_date', todayISO).lt('expected_date', plus90)
          .order('expected_date', { ascending: true }).limit(60),
        _sb.from('catalysts')
          .select('drug_id,company_id,label,catalyst_date,significance,catalyst_type,source_url,notes')
          .eq('resolved', false).gte('catalyst_date', todayISO).lte('catalyst_date', plus90)
          .order('catalyst_date', { ascending: true }).limit(120),
      ]);
      const norm = [];
      (calRes.data || []).forEach(c => norm.push({
        drug_id: c.drug_id, expected_date: c.expected_date, event_name: c.event_name,
        strategic_significance: c.strategic_significance || 'P2', ailux_impact: c.ailux_impact,
        source_url: c.source_url, _curated: true,
      }));
      const seen = new Set(norm.map(c => (c.drug_id||'') + '|' + c.expected_date));
      (mainRes.data || []).forEach(c => {
        const key = (c.drug_id||'') + '|' + c.catalyst_date;
        if (seen.has(key)) return;            // curated row already covers it
        seen.add(key);
        norm.push({
          drug_id: c.drug_id, expected_date: c.catalyst_date, event_name: c.label,
          strategic_significance: SIGMAP[(c.significance||'').toLowerCase()] || 'P3',
          ailux_impact: c.notes || '', source_url: c.source_url, _curated: false,
        });
      });
      norm.sort((a,b) => a.expected_date < b.expected_date ? -1 : a.expected_date > b.expected_date ? 1 : 0);
      const cats = norm;
      if (!cats.length) {
        body.innerHTML = '<div style="color:#94a3b8;font-size:11px;padding:12px 0">No catalysts found in the next 90 days.</div>';
        section.style.display = 'block';
        return;
      }
      // Group by month
      const byMonth = {};
      cats.forEach(c => {
        const d = new Date(c.expected_date + 'T12:00:00Z');
        const key = d.toLocaleDateString('en-US', { month:'long', year:'numeric' });
        if (!byMonth[key]) byMonth[key] = [];
        byMonth[key].push(c);
      });
      const sigClass = s => { const sl = (s||'').toLowerCase(); return sl === 'p0' ? 'p0' : sl === 'p1' ? 'p1' : sl === 'p2' ? 'p2' : 'p3'; };
      const fmtDate = iso => { const d = new Date(iso + 'T12:00:00Z'); return d.toLocaleDateString('en-US',{month:'short',day:'numeric'}); };
      let html = ''; let cid = 0;
      Object.keys(byMonth).forEach(month => {
        html += `<div class="hw-cal-month">${month}</div>`;
        byMonth[month].forEach(c => {
          const sig = c.strategic_significance || 'P3';
          const sc  = sigClass(sig);
          const drugLabel = (c.drug_id || '').replace(/-/g,' ').toUpperCase().substring(0,18);
          const detailId = `hw-cal-d-${cid++}`;
          // Expandable row — click headline row to toggle detail
          const sourceLink = c.source_url ? `<a href="${c.source_url}" target="_blank" rel="noopener">Source ↗</a>` : '';
          const ctLink = c.nct_id ? ` · <a href="https://clinicaltrials.gov/study/${c.nct_id}" target="_blank" rel="noopener">ClinicalTrials ↗</a>` : '';
          const detail = (c.ailux_impact || c.catalyst_rationale || '') ;
          html += `<div class="hw-cal-item">
            <div class="hw-cal-item-row" onclick="document.getElementById('${detailId}').classList.toggle('open')" style="cursor:pointer">
              <span class="hw-cal-sig ${sc}">${sig}</span>
              <span class="hw-cal-date">${fmtDate(c.expected_date)}</span>
              <span class="hw-cal-headline">${c.event_name||'—'}</span>
              <span class="hw-cal-drug">${drugLabel}</span>
              <span style="font-size:10px;color:#94a3b8;flex-shrink:0">▾</span>
            </div>
            <div class="hw-cal-detail" id="${detailId}">
              ${detail ? `<div style="margin-bottom:6px">${detail}</div>` : ''}
              <div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:4px">
                ${sourceLink}${ctLink}
                ${c.drug_id ? `<span style="cursor:pointer;color:#7c3aed;font-weight:600" onclick="_hwCalClick('${c.drug_id}')">Open drug card ↗</span>` : ''}
              </div>
            </div>
          </div>`;
        });
      });
      body.innerHTML = html;
      const countEl = document.getElementById('hw-cal-count');
      if (countEl) { const cur = cats.filter(c=>c._curated).length;
        countEl.textContent = `${cats.length} events${cur?` · ${cur} Ailux-flagged`:''}`; }
      section.style.display = 'block';
    } catch(e) {
      console.warn('[CatalystCalendar]', e);
      section.style.display = 'block';
    }
  }

  function _hwCalClick(drugId) {
    if (!drugId) return;
    // Try to open the drug modal if available
    if (typeof openDrugModal === 'function') { openDrugModal(drugId); return; }
    if (typeof showDrugCard === 'function') { showDrugCard(drugId); return; }
    // Fallback: navigate to the drug in the search bar
    const searchEl = document.getElementById('drug-search-input') || document.getElementById('search-input');
    if (searchEl) { searchEl.value = drugId; searchEl.dispatchEvent(new Event('input')); }
  }

  // ── Asset Intelligence Card ────────────────────────────────────────
  const _ASSET_PROGRAMS = [
    { id:'alx001', label:'ALX001', targetPair:'TL1A×IL-23p19', indication:'UC + CD', color:'#2e6fb0', bg:'#e8f0f8' },
    { id:'alx002', label:'ALX002', targetPair:'CD19×BCMA',     indication:'SLE / I&I', color:'#be185d', bg:'#fce7f3' },
    { id:'alx005', label:'ALX005', targetPair:'FcRn×Albumin',  indication:'gMG + CIDP', color:'#065f46', bg:'#d1fae5' },
    { id:'alx004', label:'ALX004?', targetPair:'White Space',  indication:'Next Program', color:'#7c3aed', bg:'#ede9fe' },
  ];

  // ── ALX004 White Space data (top 3 candidates from target_pair_whitespace) ──
  const _ALX004_CANDIDATES = [
    {
      rank: 1,
      name: 'TL1A × α4β7',
      score: 9.33,
      indication: 'UC / Crohn\'s Disease',
      synergy: 9,
      whiteSpace: 9,
      platformFit: 10,
      bisp_p2: 0,
      oneLineSynergy: 'α4β7 stops gut lymphocytes from entering; TL1A stops the inflammation once they arrive — dual mechanism, one molecule.',
      rationale: 'Extends ALX001\'s TL1A expertise into the proven gut-selective trafficking axis. Vedolizumab is approved and widely used — a TL1A×α4β7 bispecific would be the first single agent combining both mechanisms simultaneously, targeting the 40-45% of IBD patients who fail anti-TNF and need more than one mechanism to achieve mucosal healing.',
      dataNeeded: 'Head-to-head mucosal healing data vs. vedolizumab monotherapy; PK characterization of bispecific in gut tissue; Phase 1 dose-finding in UC moderate-severe population.',
      color: '#2e6fb0',
    },
    {
      rank: 2,
      name: 'FcRn × CD19',
      score: 9.17,
      indication: 'SLE / Autoimmune Hepatitis / AIHA',
      synergy: 9,
      whiteSpace: 10,
      platformFit: 10,
      bisp_p2: 0,
      oneLineSynergy: 'FcRn clears the existing pathogenic IgG acutely; CD19 eliminates the B cells producing new IgG durably — acute + durable in one molecule.',
      rationale: 'Directly synergistic with ALX002\'s CD19 arm and ALX005\'s FcRn mechanism. White space score of 10 — no FcRn×CD19 bispecific exists anywhere in clinical development. Addresses the key FcRn monotherapy gap: disease rebounds when treatment stops. The combination could achieve durable drug-free remission in antibody-mediated autoimmune diseases where neither mechanism alone is sufficient.',
      dataNeeded: 'Mechanistic proof-of-concept in AChR+ gMG or SLE patient-derived cell systems; safety profiling of combined IgG depletion + B cell depletion; optimal dosing ratio for acute vs. durable components.',
      color: '#065f46',
    },
    {
      rank: 3,
      name: 'C5 × FcRn',
      score: 9.17,
      indication: 'AChR+ Generalized Myasthenia Gravis',
      synergy: 9,
      whiteSpace: 9,
      platformFit: 9,
      bisp_p2: 0,
      oneLineSynergy: 'FcRn removes the pathogenic AChR antibody; C5 blocks the complement attack at the neuromuscular junction — addresses both steps of gMG pathophysiology in one molecule.',
      rationale: 'The most precise mechanistic story: in AChR+ gMG, pathogenic IgG triggers C5-mediated complement attack at the NMJ. Blocking the IgG (FcRn) AND the downstream complement effector (C5) provides more complete NMJ protection than either alone. Natural extension of ALX005\'s FcRn platform into the rare neuromuscular disease space. Both efgartigimod (FcRn) and ravulizumab (C5) are already approved in gMG — the bispecific consolidates two standard-of-care agents into one subcutaneous injection.',
      dataNeeded: 'Ex vivo NMJ complement assay with dual blockade vs. each mono; meningococcal safety monitoring protocol design; PK modeling to align FcRn and C5 blockade half-lives in same molecule.',
      color: '#7c3aed',
    },
  ];

  let _assetProfiles = {};
  let _assetActiveTab = 'alx001';

  async function loadAssetIntelligence() {
    const anchor = document.getElementById('asset-intel-anchor');
    if (!anchor) return;

    // Fetch from Supabase
    if (typeof _sb !== 'undefined') {
      try {
        const { data, error } = await _sb
          .from('asset_differentiation_profiles')
          .select('program_id,lead_indication,key_differentiator,top_kol_questions,mechanism_advantage,vs_approved_soc,vs_closest_competitor,key_risk,clinical_hypothesis,patient_persona,soc_failure_definition,pharma_bd_objections,ind_target_year,target_pair,efficacy_bar_primary,efficacy_bar_benchmark,efficacy_bar_target_pct');
        if (!error && data) {
          data.forEach(d => { _assetProfiles[d.program_id] = d; });
        }
      } catch(_) {}
    }

    function _windowStatus(id) {
      const windows = { alx001:'Narrowing — SPY072 Ph1b active', alx002:'Open — 24+ mo window', alx005:'Open — no bispecific in Ph2' };
      const colors  = { alx001:'#f59e0b', alx002:'#22c55e', alx005:'#22c55e' };
      const w = windows[id] || 'Unknown';
      const c = colors[id] || '#94a3b8';
      return `<span style="font-size:10px;font-weight:600;color:${c};">${w}</span>`;
    }

    function _renderALX004Tab() {
      const scoreBar = (val) => {
        const pct = Math.round((val / 10) * 100);
        const col = val >= 9 ? '#16a34a' : val >= 7 ? '#d97706' : '#dc2626';
        return `<div style="display:flex;align-items:center;gap:6px;">
          <div style="flex:1;height:5px;background:#e2e8f0;border-radius:3px;">
            <div style="width:${pct}%;height:100%;background:${col};border-radius:3px;"></div>
          </div>
          <span style="font-size:10px;font-weight:700;color:${col};min-width:18px;text-align:right;">${val}</span>
        </div>`;
      };
      const cards = _ALX004_CANDIDATES.map((c, i) => `
        <div style="background:${i===0?'#f0fdf4':i===1?'#f0f9ff':'#faf5ff'};border-radius:8px;padding:11px 12px;margin-bottom:10px;border-left:3px solid ${c.color};">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:5px;">
            <div style="font-size:12px;font-weight:800;color:#0d1f38;">#${c.rank} ${c.name}</div>
            <div style="font-size:11px;font-weight:700;color:${c.color};background:white;border-radius:4px;padding:2px 7px;">${c.score.toFixed(2)}</div>
          </div>
          <div style="font-size:10px;color:#64748b;margin-bottom:7px;font-style:italic;">${c.indication}</div>
          <div style="font-size:10px;color:#1e293b;line-height:1.5;margin-bottom:8px;">${c.oneLineSynergy}</div>
          <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:5px;">
            <div><div style="font-size:9px;color:#64748b;margin-bottom:2px;">Synergy</div>${scoreBar(c.synergy)}</div>
            <div><div style="font-size:9px;color:#64748b;margin-bottom:2px;">White Space</div>${scoreBar(c.whiteSpace)}</div>
            <div><div style="font-size:9px;color:#64748b;margin-bottom:2px;">Platform Fit</div>${scoreBar(c.platformFit)}</div>
          </div>
        </div>`).join('');
      return `
        <div style="padding:10px 0 2px;">
          <div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:0.07em;color:#7c3aed;margin-bottom:8px;">Top 3 Candidates · 15 Pairs Scored</div>
          ${cards}
          <div style="font-size:9px;color:#94a3b8;text-align:center;margin-top:4px;">Composite score = avg of 6 dimensions (biology A+B, synergy, white space, unmet need, platform fit) · No Phase 2 bispecific in any candidate</div>
        </div>`;
    }

    function _renderTabContent(prog) {
      if (prog.id === 'alx004') return _renderALX004Tab();
      const p = _assetProfiles[prog.id];
      const diff = p ? p.key_differentiator : 'Profile loading…';
      const kol1 = (p && p.top_kol_questions && p.top_kol_questions[0]) ? p.top_kol_questions[0].question : '—';
      return `
        <div style="padding:14px 0 2px;">
          <div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:0.07em;color:#64748b;margin-bottom:4px;">Lead Indication</div>
          <div style="font-size:13px;font-weight:700;color:#0d1f38;margin-bottom:12px;">${prog.indication}</div>
          <div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:0.07em;color:#64748b;margin-bottom:4px;">Key Differentiator</div>
          <div style="font-size:12px;color:#1e293b;line-height:1.55;margin-bottom:12px;">${diff}</div>
          <div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:0.07em;color:#64748b;margin-bottom:4px;">Competitive Window</div>
          <div style="margin-bottom:12px;">${_windowStatus(prog.id)}</div>
          <div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:0.07em;color:#64748b;margin-bottom:4px;">Top KOL Question</div>
          <div style="font-size:11px;color:#475569;font-style:italic;line-height:1.5;margin-bottom:14px;">"${kol1}"</div>
          <button onclick="_hwShowAssetDetail('${prog.id}')"
            style="width:100%;padding:9px 0;background:#1a2f50;color:white;border:none;border-radius:6px;font-size:11px;font-weight:700;cursor:pointer;letter-spacing:0.03em;">
            Full Differentiation Profile →
          </button>
        </div>`;
    }

    function _buildCard() {
      const tabsHtml = _ASSET_PROGRAMS.map(p => `
        <button class="asset-tab-btn${p.id === _assetActiveTab ? ' active' : ''}"
          style="flex:1;padding:7px 4px;border:none;background:${p.id === _assetActiveTab ? p.bg : 'transparent'};color:${p.id === _assetActiveTab ? p.color : '#64748b'};font-size:11px;font-weight:${p.id === _assetActiveTab ? '800' : '600'};border-radius:6px;cursor:pointer;transition:all 0.15s;"
          onclick="assetTabSwitch('${p.id}')">
          ${p.label}<br><span style="font-size:9px;font-weight:400;opacity:0.75">${p.targetPair}</span>
        </button>`).join('');

      const activeProg = _ASSET_PROGRAMS.find(p => p.id === _assetActiveTab);
      return `
        <div class="home-card" id="asset-intel-card">
          <div class="home-card-hd" style="background:#0d3b2e;">
            <span>Ailux Asset Intelligence</span>
            <span class="hc-tag">IND 2027</span>
          </div>
          <div class="home-card-body" style="padding:12px 14px 14px;">
            <div style="display:flex;gap:4px;margin-bottom:14px;background:#f8fafc;border-radius:8px;padding:4px;">
              ${tabsHtml}
            </div>
            <div id="asset-tab-content">
              ${_renderTabContent(activeProg)}
            </div>
          </div>
        </div>`;
    }

    anchor.innerHTML = _buildCard();
  }

  window.assetTabSwitch = function(programId) {
    _assetActiveTab = programId;
    const content = document.getElementById('asset-tab-content');
    if (!content) return;
    const prog = _ASSET_PROGRAMS.find(p => p.id === programId);
    if (!prog) return;

    if (programId === 'alx004') {
      content.innerHTML = (function() {
        const scoreBar = (val) => {
          const pct = Math.round((val / 10) * 100);
          const col = val >= 9 ? '#16a34a' : val >= 7 ? '#d97706' : '#dc2626';
          return `<div style="display:flex;align-items:center;gap:6px;">
            <div style="flex:1;height:5px;background:#e2e8f0;border-radius:3px;">
              <div style="width:${pct}%;height:100%;background:${col};border-radius:3px;"></div>
            </div>
            <span style="font-size:10px;font-weight:700;color:${col};min-width:18px;text-align:right;">${val}</span>
          </div>`;
        };
        const cards = _ALX004_CANDIDATES.map((c, i) => `
          <div style="background:${i===0?'#f0fdf4':i===1?'#f0f9ff':'#faf5ff'};border-radius:8px;padding:11px 12px;margin-bottom:10px;border-left:3px solid ${c.color};">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:5px;">
              <div style="font-size:12px;font-weight:800;color:#0d1f38;">#${c.rank} ${c.name}</div>
              <div style="font-size:11px;font-weight:700;color:${c.color};background:white;border-radius:4px;padding:2px 7px;">${c.score.toFixed(2)}</div>
            </div>
            <div style="font-size:10px;color:#64748b;margin-bottom:7px;font-style:italic;">${c.indication}</div>
            <div style="font-size:10px;color:#1e293b;line-height:1.5;margin-bottom:8px;">${c.oneLineSynergy}</div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:5px;">
              <div><div style="font-size:9px;color:#64748b;margin-bottom:2px;">Synergy</div>${scoreBar(c.synergy)}</div>
              <div><div style="font-size:9px;color:#64748b;margin-bottom:2px;">White Space</div>${scoreBar(c.whiteSpace)}</div>
              <div><div style="font-size:9px;color:#64748b;margin-bottom:2px;">Platform Fit</div>${scoreBar(c.platformFit)}</div>
            </div>
          </div>`).join('');
        return `
          <div style="padding:10px 0 2px;">
            <div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:0.07em;color:#7c3aed;margin-bottom:8px;">Top 3 Candidates · 15 Pairs Scored</div>
            ${cards}
            <div style="font-size:9px;color:#94a3b8;text-align:center;margin-top:4px;">Composite score = avg of 6 dimensions · No Phase 2 bispecific in any candidate</div>
          </div>`;
      })();
    } else {
      content.innerHTML = (function() {
        const p = _assetProfiles[prog.id];
        const diff = p ? p.key_differentiator : 'Profile loading…';
        const windows = { alx001:'Narrowing — SPY072 Ph1b active', alx002:'Open — 24+ mo window', alx005:'Open — no bispecific in Ph2' };
        const colors  = { alx001:'#f59e0b', alx002:'#22c55e', alx005:'#22c55e' };
        const kol1 = (p && p.top_kol_questions && p.top_kol_questions[0]) ? p.top_kol_questions[0].question : '—';
        return `
          <div style="padding:14px 0 2px;">
            <div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:0.07em;color:#64748b;margin-bottom:4px;">Lead Indication</div>
            <div style="font-size:13px;font-weight:700;color:#0d1f38;margin-bottom:12px;">${prog.indication}</div>
            <div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:0.07em;color:#64748b;margin-bottom:4px;">Key Differentiator</div>
            <div style="font-size:12px;color:#1e293b;line-height:1.55;margin-bottom:12px;">${diff}</div>
            <div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:0.07em;color:#64748b;margin-bottom:4px;">Competitive Window</div>
            <div style="margin-bottom:12px;"><span style="font-size:10px;font-weight:600;color:${colors[prog.id] || '#94a3b8'};">${windows[prog.id] || 'Unknown'}</span></div>
            <div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:0.07em;color:#64748b;margin-bottom:4px;">Top KOL Question</div>
            <div style="font-size:11px;color:#475569;font-style:italic;line-height:1.5;margin-bottom:14px;">"${kol1}"</div>
            <button onclick="_hwShowAssetDetail('${prog.id}')"
              style="width:100%;padding:9px 0;background:#1a2f50;color:white;border:none;border-radius:6px;font-size:11px;font-weight:700;cursor:pointer;letter-spacing:0.03em;">
              Full Differentiation Profile →
            </button>
          </div>`;
      })();
    }
    // Update tab button styles
    document.querySelectorAll('.asset-tab-btn').forEach((btn, i) => {
      const p = _ASSET_PROGRAMS[i];
      if (!p) return;
      btn.style.background = p.id === programId ? p.bg : 'transparent';
      btn.style.color = p.id === programId ? p.color : '#64748b';
      btn.style.fontWeight = p.id === programId ? '800' : '600';
    });
  };

  window._hwShowAssetDetail = function(programId) {
    const p = _assetProfiles[programId];
    const prog = _ASSET_PROGRAMS.find(x => x.id === programId);
    if (!p || !prog) return;

    const backdrop = document.getElementById('home-overlay-backdrop');
    const card = document.getElementById('home-overlay-card');
    const titleEl = document.getElementById('home-overlay-title');
    const body = document.getElementById('home-overlay-body');
    if (!card || !body) return;

    card.querySelectorAll('.home-panel').forEach(pnl => pnl.style.display = 'none');
    const panel = document.getElementById('home-panel-asset');
    if (panel) panel.style.display = 'block';

    titleEl.textContent = `${prog.label} · ${prog.targetPair} · ${prog.indication}`;
    backdrop.classList.add('open');
    card.classList.add('open');

    function _sec(title, content) {
      return `<div style="margin-bottom:20px;">
        <div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:0.09em;color:#1e3a5f;padding-bottom:5px;border-bottom:2px solid #1a3f8f;margin-bottom:10px;">${title}</div>
        ${content}
      </div>`;
    }
    function _field(label, val) {
      if (!val) return '';
      return `<div style="display:flex;gap:10px;margin-bottom:7px;font-size:12px;">
        <span style="min-width:160px;color:#64748b;flex-shrink:0;font-weight:500">${label}</span>
        <span style="color:#0d1f38;line-height:1.5">${val}</span>
      </div>`;
    }

    const kolHtml = (p.top_kol_questions || []).map((q, i) => `
      <div style="margin-bottom:14px;border-left:3px solid ${prog.color};padding-left:10px;">
        <div style="font-size:11px;font-weight:700;color:#0d1f38;margin-bottom:4px;">Q${i+1}: ${q.question}</div>
        <div style="font-size:11px;color:#475569;line-height:1.55">${q.answer}</div>
      </div>`).join('');

    const objHtml = (p.pharma_bd_objections || []).map((o, i) => `
      <div style="margin-bottom:14px;border-left:3px solid #dc2626;padding-left:10px;">
        <div style="font-size:11px;font-weight:700;color:#7f1d1d;margin-bottom:4px;">Objection: ${o.objection}</div>
        <div style="font-size:11px;color:#475569;line-height:1.55"><strong>Response:</strong> ${o.response}</div>
      </div>`).join('');

    const detailHtml = `
      <div style="padding:4px 0;">
        <div class="ailux-card" style="margin-bottom:16px;">
          <div class="ailux-title">${prog.label} · ${prog.targetPair}</div>
          <div style="font-size:15px;font-weight:700;margin-top:4px;">${p.key_differentiator || '—'}</div>
        </div>

        ${_sec('Patient Profile',
          _field('Patient Persona', p.patient_persona) +
          _field('SoC Failure Definition', p.soc_failure_definition) +
          _field('US Population', p.patient_population_us ? (p.patient_population_us >= 1000000 ? (p.patient_population_us/1e6).toFixed(1)+'M' : Math.round(p.patient_population_us/1000)+'K') + ' estimated' : null) +
          _field('IND Target', p.ind_target_year ? p.ind_target_year.toString() : null)
        )}

        ${_sec('Mechanism Differentiation',
          _field('Bispecific Advantage', p.mechanism_advantage) +
          _field('Clinical Hypothesis', p.clinical_hypothesis)
        )}

        ${_sec('Efficacy Bar',
          _field('Primary Endpoint', p.efficacy_bar_primary) +
          _field('Benchmark Trial', p.efficacy_bar_benchmark) +
          _field('Target Response Rate', p.efficacy_bar_target_pct ? p.efficacy_bar_target_pct + '%' : null)
        )}

        ${_sec('Competitive Positioning',
          _field('vs Approved SoC', p.vs_approved_soc) +
          _field('vs Closest Competitor', p.vs_closest_competitor) +
          _field('Key Risk', p.key_risk)
        )}

        ${_sec('KOL Conversation Prep (5 Questions)', kolHtml || '<div style="color:#94a3b8;font-size:12px;">No KOL Q&amp;A loaded.</div>')}

        ${_sec('Pharma BD Objections & Responses', objHtml || '<div style="color:#94a3b8;font-size:12px;">No objections loaded.</div>')}
      </div>`;

    const detailBody = document.getElementById('asset-intel-detail-body');
    if (detailBody) detailBody.innerHTML = detailHtml;
  };

  // ── Entry / exit ───────────────────────────────────────────────────
  async function initHomeWelcome() {
    _hwUpdateClock();
    if (!_hwClockTimer) _hwClockTimer = setInterval(_hwUpdateClock, 1000);
    if (!_hwFirstLoad) return;
    _hwFirstLoad = false;
    await _hwRefresh(true);
    _hwLoadBDMetrics();
    loadBDToday();
    loadAssetIntelligence();
    loadIndicationPriority();
    _hwLoadMeridianIssue();
    _hwLoadCatalystCalendar();
    _hwPollTimer = setInterval(() => _hwRefresh(false), 60_000);
  }

  function _hwPause() {
    if (_hwPollTimer)  { clearInterval(_hwPollTimer);  _hwPollTimer  = null; }
    if (_hwClockTimer) { clearInterval(_hwClockTimer); _hwClockTimer = null; }
    _hwFirstLoad = true;
  }

  registerTab('home', { onEnter() { initHomeWelcome(); }, onLeave() { _hwPause(); } });
  // 2026-06-19 (rec #9): Home Preview (#tab-homeprev) is the default landing. Init it on load
  // (its mlInit is load-once guarded). The old Home no longer auto-polls on load — its
  // initHomeWelcome only runs if a user explicitly navigates to the deprecated 'home' tab.
  document.addEventListener('DOMContentLoaded', () => { window.mlInit && window.mlInit(); });
})();
