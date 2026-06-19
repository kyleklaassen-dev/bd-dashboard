// COMPANY ENTITY MODAL — deep-dive slide-over: overview, areas, dossier panels, Files,
// and BD-Intelligence tabs. Extracted from app.js (Phase 4 split 2026-06-19). Classic script:
// globals (openCompanyEntityModal, closeCoSlideOver, _cemSwitchArea, _dossierSwitch,
// _cemLoadFiles, filterCompanyFiles, _cemLoadBdIntel, _openEntityByEl). Loaded before app.js.

// ── ENTITY DEEP-DIVE MODAL ────────────────────────────────────────────
// Opens when a company/drug name is clicked (not the row background).
// Row expansion is preserved — stopPropagation on the name span handles separation.

function _openEntityByEl(el) {
  const id     = el.dataset.eid;
  const cid    = el.dataset.cid   || id;   // company_id — guaranteed to be companies.id
  const name   = el.dataset.ename || el.textContent.trim();
  const tab    = el.dataset.tab   || '';
  const hints  = {
    ticker:     el.dataset.ticker     || '',
    hq_city:    el.dataset.hqcity     || '',
    hq_country: el.dataset.hqcountry  || '',
  };
  openCompanyEntityModal(id, name, tab, cid, hints);
}

/* ─── Company slide-over panel ──────────────────────────────────────────────── */
async function openCompanyEntityModal(companyId, companyName, sourceTabId, fallbackCid, rowHints) {
  console.log('[openCompanyEntityModal] called:', companyId, companyName, sourceTabId);
  // Open overlay FIRST — before any DOM manipulation that could throw
  const overlay = document.getElementById('entity-modal-overlay');
  if (!overlay) { console.warn('[openCompanyEntityModal] overlay not found'); return; }
  overlay.classList.add('open');

  const titleEl  = document.getElementById('entity-modal-title');
  const subEl    = document.getElementById('entity-modal-sub');
  const bodyEl   = document.getElementById('entity-modal-body');
  const footerEl = document.getElementById('entity-modal-footer');

  if (titleEl)  { titleEl.textContent = companyName || 'Company';
    // News-sentiment signal dot next to the company name (loads map if not yet cached)
    Promise.resolve(_loadSentimentMap()).then(() => {
      try { const dot = _sentDotHTML(companyId); if (dot && titleEl.querySelector('.sent-dot') == null) titleEl.insertAdjacentHTML('beforeend', dot); } catch(e){}
    });
  }
  if (subEl)    subEl.textContent   = 'Company Profile';
  if (bodyEl)   bodyEl.innerHTML    = '<div style="padding:60px;text-align:center;color:#94a3b8;font-style:italic;font-size:13px">⟳ Loading…</div>';
  if (footerEl) footerEl.style.display = 'none';

  if (!bodyEl) { console.warn('[openCompanyEntityModal] bodyEl not found'); return; }

  if (!_sb) {
    bodyEl.innerHTML = '<div style="padding:40px;text-align:center;color:#94a3b8;font-size:13px">Database not connected.</div>';
    return;
  }

  try {
    const AREA      = (sourceTabId && TAB_AREA_MAP[sourceTabId]?.[0]) || 'tl1a';
    const DRUG_AREA = AREA === 'tl1a' ? 'ibd' : AREA;

    // NOTE: profile cache intentionally disabled — ownership model requires fresh drug fetch
    // each time to correctly include acquired assets (current_owner_company_id).
    // Re-enable with proper cache invalidation once ownership changes stabilize.
    const piObj = _areaPIs[sourceTabId] || null;

    // ── Parallel fetch: profile + catalysts + deals + company row + all company areas + subsidiaries ──
    const [profileRes, catsRes, dealsRes, companyRowRes, allAreaRowsRes, subsidiariesRes, partnershipsRes] = await Promise.all([
      _sb.from('company_profiles').select('*')
         .eq('company_id', companyId).or(`target_id.eq.${AREA},area_id.eq.${AREA}`)
         .order('updated_at', { ascending: false }).limit(1),
      _sb.from('catalysts').select('*')
         .eq('company_id', companyId).eq('area_id', AREA)
         .eq('resolved', false).order('sort_date', { ascending: true }).limit(20),
      _sb.from('deals').select('*')
         .eq('company_id', companyId).order('deal_date', { ascending: false }).limit(20),
      _sb.from('companies').select('id,name,ticker,hq_city,hq_country,company_type,ta_focus_1,ta_focus_2,strategic_value_score,stock_price,stock_change,market_cap_usd_m:market_cap').eq('id', companyId).limit(1),
      _sb.from('company_areas').select('area_id').eq('company_id', companyId),
      _sb.from('companies').select('id,name,status').eq('parent_company_id', companyId).in('status', ['acquired', 'subsidiary']),
      // Wave 2: structured partnership relationships (both sides — this company as lead OR partner)
      _sb.from('company_partnerships')
         .select('partner_name,partner_company_name,partner_company_id,lead_company_id,partnership_type,deal_type,drug_id,geographic_rights,partnership_verified,source_url,is_current,notes')
         .or(`lead_company_id.eq.${companyId},partner_company_id.eq.${companyId},company_id.eq.${companyId}`).limit(40),
    ]);

    // ── Multi-area profiles + catalysts (for Assessment / Catalysts tabs) ──
    const allAreaIds = [...new Set((allAreaRowsRes.data||[]).map(r => r.area_id).filter(Boolean))];
    // Ensure the current area is always included
    if (!allAreaIds.includes(AREA)) allAreaIds.unshift(AREA);

    // Fetch profiles and catalysts for all areas in parallel
    const [allAreaProfileRows, allAreaCatRows] = await Promise.all([
      Promise.all(allAreaIds.map(aId =>
        _sb.from('company_profiles').select('*')
           .eq('company_id', companyId).or(`target_id.eq.${aId},area_id.eq.${aId}`)
           .order('updated_at', { ascending: false }).limit(1)
           .then(r => ({ areaId: aId, profile: r.data?.[0] || null }))
      )),
      Promise.all(allAreaIds.map(aId =>
        _sb.from('catalysts').select('*')
           .eq('company_id', companyId).eq('area_id', aId)
           .eq('resolved', false).order('sort_date', { ascending: true }).limit(30)
           .then(r => ({ areaId: aId, cats: r.data || [] }))
      )),
    ]);

    const allAreaProfiles = {}; // areaId → profile
    allAreaProfileRows.forEach(({ areaId, profile }) => { allAreaProfiles[areaId] = profile; });
    const allAreaCats = {}; // areaId → catalysts[]
    allAreaCatRows.forEach(({ areaId, cats }) => { allAreaCats[areaId] = cats; });

    // Competitive signals per area
    const allAreaSigsRows = await Promise.all(allAreaIds.map(aId =>
      _sb.from('competitive_signals')
         .select('id,signal_type,title,description,source_url,source_date,drug_id,confidence,area_id,target_id')
         .eq('company_id', companyId).or(`target_id.eq.${aId},area_id.eq.${aId}`)
         .order('source_date', { ascending: false }).limit(20)
         .then(r => ({ areaId: aId, sigs: r.data || [] }))
    ));
    const allAreaSigs = {};
    allAreaSigsRows.forEach(({ areaId, sigs }) => { allAreaSigs[areaId] = sigs; });

    const profile    = profileRes.data?.[0] || null;
    let companyRow = companyRowRes.data?.[0] || null;
    // If entity_id ≠ company_id (e.g. acquired asset), retry with company_id
    if (!companyRow && fallbackCid && fallbackCid !== companyId) {
      const { data: fbRows } = await _sb.from('companies')
        .select('id,name,ticker,hq_city,hq_country,company_type,ta_focus_1,ta_focus_2,strategic_value_score')
        .eq('id', fallbackCid).limit(1);
      companyRow = fbRows?.[0] || null;
    }
    // Merge hints from PI row as last-resort fallback (ticker/hq already in entity obj)
    if (!companyRow && rowHints) {
      companyRow = { ticker: rowHints.ticker||'', hq_city: rowHints.hq_city||'', hq_country: rowHints.hq_country||'', ta_focus_1:'', ta_focus_2:'' };
    } else if (companyRow && rowHints) {
      if (!companyRow.ticker     && rowHints.ticker)     companyRow.ticker     = rowHints.ticker;
      if (!companyRow.hq_city    && rowHints.hq_city)    companyRow.hq_city    = rowHints.hq_city;
      if (!companyRow.hq_country && rowHints.hq_country) companyRow.hq_country = rowHints.hq_country;
    }
    console.log('[openCompanyEntityModal] companyRow:', companyRow);
    const cats    = catsRes.data || [];
    let deals     = dealsRes.data || [];

    // Fallback deal name-match
    if (!deals.length) {
      const coName = (companyName||'').split('/')[0].trim().substring(0, 14);
      const { data: d2 } = await _sb.from('deals').select('*')
        .or(`from_company.ilike.*${coName}*,to_company.ilike.*${coName}*`)
        .order('deal_date', { ascending: false }).limit(20);
      deals = d2 || [];
    }

    // ── Deal sequencing constraints for this company ──────────────────────────
    let seqConstraints = [];
    try {
      const { data: scRows } = await _sb
        .from('deal_sequencing_constraints')
        .select('constraint_type, constraint_description:description, timing_note:reasoning, bd_action_blocked_until:window_opens')
        .eq('company_id', companyId)
        .limit(5);
      seqConstraints = scRows || [];
    } catch(_) {}

    // Intel news items
    let intelNews = [];
    try {
      const { data: icRows } = await _sb.from('intel_companies').select('intel_id')
        .eq('company_id', companyId).limit(20);
      if (icRows?.length) {
        const intelIds = icRows.map(r => r.intel_id);
        const { data: intelRows } = await _sb.from('intel')
          .select('id,intel_date,headline,body,source_url')
          .in('id', intelIds).order('intel_date', { ascending: false }).limit(10);
        intelNews = (intelRows||[]).map(i => ({
          _source: 'intel', deal_date: i.intel_date,
          deal_date_label: i.intel_date ? i.intel_date.slice(0, 10) : '',
          headline: i.headline, detail: (i.body||'').slice(0, 200),
          source_url: i.source_url, deal_type: 'news',
        }));
      }
    } catch(_) {}

    const allNews = [...deals, ...intelNews]
      .filter((item, idx, arr) =>
        arr.findIndex(x => (x.headline||'').slice(0,40) === (item.headline||'').slice(0,40)) === idx)
      .sort((a, b) => (b.deal_date||'').localeCompare(a.deal_date||''));

    // ── Drugs for this area ──
    // Resolve via ownership_edges CONTROLLED_BY — acquirer shows acquired/licensed drugs.
    // (e.g. UCB controls Candid's cizutamig/CND319/CND460 after May 2026 acquisition;
    //  UCB licensed ATG-201 from Antengene — LICENSED_IN edges also resolve as CONTROLLED_BY)
    const [drugAreaRes, controlledEdgesRes] = await Promise.all([
      _sb.from('drug_areas').select('drug_id').eq('area_id', DRUG_AREA),
      _sb.from('ownership_edges').select('subject_id,object_id')
         .eq('predicate', 'CONTROLLED_BY').eq('subject_type', 'drug')
         .eq('object_id', companyId).eq('status', 'active'),
    ]);
    const areaSet = new Set((drugAreaRes.data||[]).map(r => r.drug_id));
    const controlledDrugIds = (controlledEdgesRes.data||[]).map(r => r.subject_id);

    // Fetch originator IDs for acquired drugs (for the originator pill display)
    const originatorMap = {}; // drug_id → originator_company_id
    if (controlledDrugIds.length) {
      const { data: origEdges } = await _sb.from('ownership_edges').select('subject_id,object_id')
        .eq('predicate', 'ORIGINATED_BY').eq('subject_type', 'drug')
        .in('subject_id', controlledDrugIds).eq('status', 'active');
      (origEdges||[]).forEach(e => { originatorMap[e.subject_id] = e.object_id; });
    }

    // Resolve originator company display names
    const originatorNameMap = {}; // company_id → short display name
    const originatorIds = [...new Set(Object.values(originatorMap))];
    if (originatorIds.length) {
      const { data: coRows } = await _sb.from('companies').select('id,name')
        .in('id', originatorIds);
      (coRows||[]).forEach(c => {
        // Use first word of company name as short form (e.g. 'Candid Therapeutics' → 'Candid')
        originatorNameMap[c.id] = (c.name||'').split(' ')[0] || c.id;
      });
    }

    // Build drug fetch: own drugs + controlled via ownership_edges + co-developed drugs
    // co_developer_ids is a TEXT[] column; PostgREST cs.{id} = array contains operator
    const _codevFilter = `co_developer_ids.cs.{${companyId}}`;
    const _leadFilter  = `lead_company_id.eq.${companyId}`;
    const _ownFilter   = `company_id.eq.${companyId}`;
    const idsToFetch = controlledDrugIds.length
      ? `${_ownFilter},id.in.(${controlledDrugIds.join(',')}),${_leadFilter},${_codevFilter}`
      : `${_ownFilter},${_leadFilter},${_codevFilter}`;
    const { data: allDrugsData } = await _sb.from('drugs').select('*')
      .or(idsToFetch).order('sort_order', { ascending: true }).limit(50);

    const seen = new Set();
    const drugs = (allDrugsData||[]).filter(d => {
      if (seen.has(d.id)) return false;
      // Controlled assets show in the controlling company's dossier regardless of area context
      const isControlledAsset = controlledDrugIds.includes(d.id) && d.company_id !== companyId;
      // Co-developed: drug has co_developer_ids containing this company but company_id is a different org
      const isCoDevAsset = d.company_id !== companyId
        && (Array.isArray(d.co_developer_ids) && d.co_developer_ids.includes(companyId)
            || d.lead_company_id === companyId);
      if (!areaSet.has(d.id) && !isControlledAsset && !isCoDevAsset) return false;
      seen.add(d.id);
      // Controlled asset: override pill fields so controller's dossier shows originator, not legacy partner_company/licensor fields
      if (isControlledAsset) {
        const origName = (originatorMap[d.id] ? originatorNameMap[originatorMap[d.id]] : null)
          || d.display_partner_name || null;
        d._originator_name = origName;
        d.partner_company   = origName;   // takes priority in _partnerCo pill logic
        d.licensor_name     = null;        // clear legacy fields that would override
        d.entity_name       = null;
        d.partnership_verified = true;     // suppress "?" — this relationship is confirmed via ownership_edges
      }
      // Co-dev asset: mark it so pipeline UI shows CO-DEV badge + originator label
      if (isCoDevAsset && !isControlledAsset) {
        d._is_codev = true;
        // Show the originating company name as the pill label
        d._codev_originator = d.company_id; // raw id; resolved to name below if possible
      }
      return true;
    });

    // ── Trials per drug ──
    let trials = [];
    for (const d of drugs.slice(0, 8)) {
      const { data: tt } = await _sb.from('trials').select('*').eq('drug_id', d.id);
      if (tt) trials.push(...tt);
    }

    // ── Combos + combo trials ──
    let combos = [];
    try {
      const { data: comboRows } = await _sb.from('drug_combinations').select('*')
        .eq('company_id', companyId).eq('area_id', AREA)
        .order('strategic_significance', { ascending: true });
      const seen = new Set();
      combos = (comboRows||[]).filter(c => {
        const key = (c.label||'').toLowerCase().replace(/\s*[\(\[].*?[\)\]]/g,'').replace(/\s+/g,' ').trim();
        if (seen.has(key)) return false; seen.add(key); return true;
      });
      const comboIds = combos.map(c => c.id).filter(Boolean);
      if (comboIds.length) {
        const { data: ctr } = await _sb.from('trials').select('*').in('combination_id', comboIds);
        if (ctr?.length) trials.push(...ctr);
      }
    } catch(_) {}

    // ── Molecule intelligence ──
    let moleculeIntel = {};
    try {
      const drugIds = drugs.map(d => d.id).filter(Boolean);
      if (drugIds.length) {
        const { data: molRows } = await _sb.from('molecule_intelligence').select('*').in('drug_id', drugIds);
        if (molRows?.length) molRows.forEach(m => { moleculeIntel[m.drug_id] = m; });
      }
    } catch(_) {}

    // ── Recent news_articles for this company (Fix 4 — knowledge graph integration) ──
    // Fetches news_articles.matched_company_ids contains companyId.
    // Higher signal than intel_companies junction; direct FK set by fetch_homepage_news.py.
    let coNewsArticles = [];
    try {
      const _co90dAgo = new Date(Date.now() - 90*24*60*60*1000).toISOString().slice(0,10);
      const { data: coNaRows } = await _sb.from('news_articles')
        .select('id,headline,source_name,published_at,article_url,relevance_score,meridian_summary,why_it_matters,matched_drug_ids')
        .contains('matched_company_ids', [companyId])
        .neq('source_validation_status', 'invalid')
        .gte('published_at', _co90dAgo)
        .order('relevance_score', { ascending: false })
        .limit(20);
      coNewsArticles = coNaRows || [];
    } catch(_) {}

    // ── Intel directly linked via primary_company_id (Fix 4 — higher-signal intel path) ──
    // Separate from intelNews (intel_companies junction) — primary_company_id is a direct FK
    // for intel items where this company is the primary subject. Higher BD signal.
    let companyIntelDirect = [];
    try {
      const _ci90dAgo = new Date(Date.now() - 90*24*60*60*1000).toISOString().slice(0,10);
      const { data: ciRows } = await _sb.from('intel')
        .select('id,intel_date,headline,intel_type,source_url,importance,body')
        .eq('primary_company_id', companyId)
        .gte('intel_date', _ci90dAgo)
        .order('intel_date', { ascending: false })
        .limit(15);
      companyIntelDirect = ciRows || [];
    } catch(_) {}

    // ── Drug validation results for all company drugs ──
    // Shows pass/fail/warning status per drug per check_type in the Data Quality tab.
    let drugValidationResults = [];
    try {
      const _dvDrugIds = drugs.map(d => d.id).filter(Boolean);
      if (_dvDrugIds.length) {
        const { data: dvRows } = await _sb.from('drug_validation_results')
          .select('drug_id,check_type,check_status,details,verified_at')
          .in('drug_id', _dvDrugIds)
          .in('check_status', ['fail','warning','needs_review'])
          .order('verified_at', { ascending: false })
          .limit(50);
        drugValidationResults = dvRows || [];
      }
    } catch(_) {}

    // ── Recent field_change_audit entries for this company ──
    // Shows the last 8 field-level changes to any drug or company record linked to this entity.
    let fieldChangeAudit = [];
    try {
      const { data: fcaRows } = await _sb.from('field_change_audit')
        .select('entity_type,entity_id,field_name,old_value,new_value,changed_at,changed_by')
        .or(`entity_id.eq.${companyId},entity_id.in.(${(drugs.map(d=>d.id).filter(Boolean).join(','))||companyId})`)
        .order('changed_at', { ascending: false })
        .limit(8);
      fieldChangeAudit = fcaRows || [];
    } catch(_) {}

    // ── New data layers (2026-06-07) — financials (runway), typed SEC events,
    //    patent estate, leadership, and asset-transfer chains involving this company.
    //    One parallel batch; each section renders only when non-empty.
    let coFinancials = null, coSecEvents = [], coPatentRows = [], coPersonnel = [], coTransferChains = [], coSentiment = null;
    try {
      const [finR, evR, patR, perR, athR, sentR] = await Promise.all([
        _sb.from('company_financials').select('cash_and_equivalents,cash_as_of,quarterly_burn,runway_quarters,market_cap,source_url,fetched_at')
           .eq('company_id', companyId).order('fetched_at', {ascending:false}).limit(1),
        _sb.from('company_events').select('event_type,event_subtype,event_summary,form_type,filing_date,source_url,financing_type,is_dilutive')
           .eq('company_id', companyId).neq('event_type', 'other')
           .order('filing_date', {ascending:false}).limit(5),
        _sb.from('company_patents').select('patent_number,patent_title,matched_target,grant_year,patent_date,source_url')
           .eq('company_id', companyId).order('patent_date', {ascending:false}).limit(60),
        _sb.from('company_personnel').select('person_name,role,role_category,source_url')
           .eq('company_id', companyId).limit(12),
        _sb.from('asset_transfer_history').select('drug_id,sequence_order,from_entity_name,from_entity_id,to_entity_name,to_entity_id,transfer_type,geographic_scope,transfer_date,deal_value_notes,verified,source_url')
           .or(`from_entity_id.eq.${companyId},to_entity_id.eq.${companyId}`)
           .order('transfer_date', {ascending:false}).limit(12),
        _sb.from('company_news_sentiment').select('n_articles,net_sentiment,last_article_date')
           .eq('company_id', companyId).limit(1),
      ]);
      coFinancials     = finR.data?.[0] || null;
      coSecEvents      = evR.data  || [];
      coPatentRows     = patR.data || [];
      coPersonnel      = perR.data || [];
      coTransferChains = athR.data || [];
      coSentiment      = sentR.data?.[0] || null;
    } catch(_nlErr) { console.warn('[companyModal-newlayers]', _nlErr?.message); }

    const prog   = { co: companyName, entity_id: companyId, company_id: companyId, id: companyId,
                     summary: profile?.platform_summary || '', overlap: '', _groupEntries: [] };
    let _coIntelFacts = [];
    try { const { data: _cif } = await _sb.from('intel_fact_entities').select('role,intel_facts(fact_type,claim,value_num,unit,area_id,source_url,page_ref)').eq('entity_id', companyId).limit(150); _coIntelFacts = (_cif||[]).map(r=>r&&r.intel_facts).filter(Boolean); } catch(_e) {}
    const subsidiaries = subsidiariesRes.data || [];
    const sbData = { profile, company: companyRow, catalysts: cats, deals: allNews, drugs, trials, combos, moleculeIntel, newsArticles: coNewsArticles, companyIntel: companyIntelDirect, subsidiaries, seqConstraints, drugValidationResults, fieldChangeAudit, partnerships: (partnershipsRes.data || []), financials: coFinancials, secEvents: coSecEvents, companyPatents: coPatentRows, personnel: coPersonnel, transferChains: coTransferChains, newsSentiment: coSentiment, intelFacts: _coIntelFacts };
    const extraData = { allAreaIds, allAreaProfiles, allAreaCats, allAreaSigs, currentArea: AREA };

    // Cache disabled — ownership model requires fresh drug fetch each open
    // if (piObj) piObj._profileCache[companyId] = sbData;

    // ── Also-tracked footer — hidden for company cards (area filter in card replaces this) ──
    if (footerEl) footerEl.style.display = 'none';

    try   {
      bodyEl.classList.add('dossier-mode');
      bodyEl.innerHTML = _cemCompanyBody(prog, sbData, AREA, extraData);
    }
    catch (e) {
      console.error('[openCompanyEntityModal] render error:', e);
      bodyEl.innerHTML = `<div style="padding:20px;color:#dc2626;font-size:12px">Render error: ${e.message}</div>`;
    }
  } catch (err) {
    console.warn('[openCompanyEntityModal] fetch error:', err);
    bodyEl.innerHTML = '<div style="padding:40px;text-align:center;color:#94a3b8;font-size:13px">Failed to load company data.</div>';
  }
}

function closeCoSlideOver() {
  closeEntityModal();
}

/* ═══════════════════════════════════════════════════════════════════════════
   CANONICAL ENTITY DOSSIER
   The permanent home for all entity intelligence. Every drug and company
   opens the same modal from any tab. Provenance, confidence, and audit
   history will slot in here as Phase 4 (Trust) matures.
   ═══════════════════════════════════════════════════════════════════════════ */

// Switch area filter on the canonical company card
function _cemSwitchArea(filterId, areaId) {
  // Update area pills
  document.querySelectorAll(`#cem-af-${filterId} .cem-area-pill`).forEach(p => {
    p.classList.toggle('active', p.dataset.area === areaId);
  });
  // Show matching area blocks, hide others
  document.querySelectorAll(`.cem-area-block[data-fid="${filterId}"]`).forEach(b => {
    b.classList.toggle('active', b.dataset.area === areaId);
  });
}

// Switch between internal dossier tabs
function _dossierSwitch(panelId) {
  const body = document.getElementById('entity-modal-body');
  if (!body) return;
  body.querySelectorAll('.dossier-tab-btn').forEach(b => b.classList.remove('active'));
  body.querySelectorAll('.dossier-panel').forEach(p => p.classList.remove('active'));
  const btn = body.querySelector(`.dossier-tab-btn[data-panel="${panelId}"]`);
  const panel = body.querySelector(`#${panelId}`);
  if (btn) btn.classList.add('active');
  if (panel) panel.classList.add('active');
  // Load files on demand when Files tab is activated
  if (panelId === 'cem-tab-files' && window._cemCurrentCompanyId) {
    _cemLoadFiles(window._cemCurrentCompanyId);
  }
  // Load BD Intelligence on demand when BD tab is activated
  if (panelId === 'cem-tab-bd' && window._cemCurrentCompanyId) {
    _cemLoadBdIntel(window._cemCurrentCompanyId);
  }
  // Load drug Intelligence tab on demand
  if (panelId === 'cem-dtab-intel' && window._cemCurrentDrugId) {
    _demLoadIntelligence(window._cemCurrentDrugId, window._cemCurrentDrugName, window._cemCurrentDrugCompanyId);
  }
}

// ── Files tab: fetch + render company_documents ───────────────────────────
function _cemLoadFiles(companyId) {
  const list = document.getElementById('cem-files-list');
  if (!list) return;
  list.innerHTML = '<div class="cem-files-loading">Loading documents...</div>';

  const url = `${SUPABASE_URL}/rest/v1/company_documents?company_id=eq.${companyId}&select=id,document_type,title,authors,conference,journal,publication_date,conference_date,source_url,pubmed_id,drug_names,phase,abstract_text,key_findings&order=publication_date.desc.nullslast&limit=50`;

  fetch(url, { headers: { apikey: SUPABASE_ANON, Authorization: `Bearer ${SUPABASE_ANON}` } })
    .then(r => r.json())
    .then(docs => {
      window._cemFilesData = Array.isArray(docs) ? docs : [];
      _cemRenderFiles(window._cemFilesData);
    })
    .catch(() => {
      list.innerHTML = '<div class="cem-files-empty">No documents found.</div>';
    });
}

function _cemRenderFiles(docs) {
  const list = document.getElementById('cem-files-list');
  if (!list) return;
  if (!docs || !docs.length) {
    list.innerHTML = '<div class="cem-files-empty">No documents stored for this company yet. Documents are collected during nightly enrichment.</div>';
    return;
  }

  const TYPE_ICONS = {
    'abstract': '📄', '8-K': '📋', 'poster': '🖼️', 'slide_deck': '📊',
    'press_release': '📰', 'IND': '💉', 'clinical_data': '🔬',
    'patent': '⚖️', 'analyst_report': '📈', 'other': '📎'
  };
  const TYPE_COLORS = {
    'abstract': '#6366f1', '8-K': '#dc2626', 'poster': '#7c3aed',
    'slide_deck': '#0891b2', 'press_release': '#059669', 'IND': '#d97706',
    'clinical_data': '#4f46e5', 'patent': '#374151', 'other': '#64748b'
  };

  list.innerHTML = docs.map(doc => {
    const icon = TYPE_ICONS[doc.document_type] || '📎';
    const color = TYPE_COLORS[doc.document_type] || '#64748b';
    const date = doc.publication_date || doc.conference_date || '';
    const venue = doc.conference || doc.journal || '';
    const drugs = (doc.drug_names || []).join(', ');
    const hasAbstract = doc.abstract_text && doc.abstract_text.length > 20;

    return `<div class="cem-file-row" data-type="${doc.document_type}">
      <div class="cem-file-icon" style="color:${color}">${icon}</div>
      <div class="cem-file-body">
        <div class="cem-file-title">
          ${doc.source_url ? `<a href="${doc.source_url}" target="_blank" rel="noopener">${doc.title || 'Untitled'}</a>` : (doc.title || 'Untitled')}
        </div>
        <div class="cem-file-meta">
          <span class="cem-file-type-badge" style="background:${color}20;color:${color}">${doc.document_type}</span>
          ${venue ? `<span class="cem-file-venue">${venue}</span>` : ''}
          ${date ? `<span class="cem-file-date">${date.slice(0,7)}</span>` : ''}
          ${drugs ? `<span class="cem-file-drugs">${drugs}</span>` : ''}
          ${doc.phase ? `<span class="cem-file-phase">${doc.phase}</span>` : ''}
        </div>
        ${doc.authors ? `<div class="cem-file-authors">${doc.authors.slice(0,120)}${doc.authors.length > 120 ? '...' : ''}</div>` : ''}
        ${hasAbstract ? `<div class="cem-file-abstract-toggle">
          <button onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none';this.textContent=this.textContent==='Show abstract'?'Hide abstract':'Show abstract'" class="cem-file-toggle-btn">Show abstract</button>
          <div class="cem-file-abstract" style="display:none">${(doc.abstract_text || '').slice(0,800)}${(doc.abstract_text||'').length>800?'...':''}</div>
        </div>` : ''}
        ${doc.key_findings ? `<div class="cem-file-findings">💡 ${doc.key_findings.slice(0,200)}</div>` : ''}
      </div>
    </div>`;
  }).join('');
}

function filterCompanyFiles(type, btn) {
  document.querySelectorAll('.cem-file-filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const docs = window._cemFilesData || [];
  _cemRenderFiles(type === 'all' ? docs : docs.filter(d => d.document_type === type));
}

// ── BD Intelligence tab: fetch company_strategic_views + company_platform_views + deal count ──
async function _cemLoadBdIntel(companyId) {
  const panel = document.getElementById('cem-tab-bd-panel');
  if (!panel || !_sb) return;
  panel.innerHTML = '<div style="padding:20px;text-align:center;color:#94a3b8;font-size:12px;font-style:italic">Loading BD intelligence…</div>';

  try {
    const _24mAgo = new Date(Date.now() - 730*24*60*60*1000).toISOString().slice(0,10);
    const [svRes, pvRes, dealRes, svScoreRes, conflictRes] = await Promise.all([
      _sb.from('company_strategic_views').select('view_type,summary,ailux_relevance,strategic_score,key_assets,confidence_source').eq('company_id', companyId).limit(5),
      _sb.from('company_platform_views').select('platform_type,platform_description,relevance_to_ailux,partnership_potential,confidence_source').eq('company_id', companyId).limit(5),
      _sb.from('deals').select('id,deal_date,deal_type,headline,upfront_usd_m,total_usd_m').eq('company_id', companyId).gte('deal_date', _24mAgo).order('deal_date', {ascending:false}).limit(10),
      _sb.from('companies').select('strategic_value_score').eq('id', companyId).limit(1),
      _sb.from('company_portfolio_conflicts').select('ailux_asset_id,conflict_level,conflict_rationale,conflicting_drug_ids,combo_opportunity,combo_description').eq('company_id', companyId).order('ailux_asset_id'),
    ]);

    const svViews   = svRes.data  || [];
    const pvViews   = pvRes.data  || [];
    const deals24m  = dealRes.data || [];
    const svs       = svScoreRes.data?.[0]?.strategic_value_score ?? null;
    const conflicts = conflictRes.data || [];

    // Portfolio Conflict Analysis
    const _conflictAssets = [
      { id:'alx001', label:'ALX001', desc:'TL1A×IL-23p19 · IBD' },
      { id:'alx002', label:'ALX002', desc:'CD19×BCMA · I&I Autoimmune' },
      { id:'alx005', label:'ALX005', desc:'FcRn×Albumin · Autoantibody' },
    ];
    const _conflictMeta = {
      hard:  { badge:'#dc2626', bg:'#fef2f2', icon:'🔴', label:'Hard Conflict' },
      soft:  { badge:'#b45309', bg:'#fffbeb', icon:'🟡', label:'Soft Conflict' },
      combo: { badge:'#1d4ed8', bg:'#eff6ff', icon:'🔵', label:'Combo Opportunity' },
      clear: { badge:'#15803d', bg:'#f0fdf4', icon:'🟢', label:'Clear' },
    };
    const _conflictHtml = _conflictAssets.map(asset => {
      const row = conflicts.find(c => c.ailux_asset_id === asset.id);
      if (!row) return '';
      const m = _conflictMeta[row.conflict_level] || _conflictMeta.clear;
      const drugList = (row.conflicting_drug_ids || []).length > 0
        ? `<div style="font-size:10px;color:#64748b;margin-top:3px">Conflicting assets: <span style="font-weight:600;color:#475569">${(row.conflicting_drug_ids||[]).slice(0,4).join(', ')}</span></div>`
        : '';
      const comboNote = row.combo_opportunity && row.combo_description
        ? `<div style="margin-top:5px;padding:6px 8px;background:#eff6ff;border-left:3px solid #3b82f6;border-radius:0 4px 4px 0;font-size:10.5px;color:#1e40af;line-height:1.45">💡 ${row.combo_description.slice(0,200)+(row.combo_description.length>200?'…':'')}</div>`
        : '';
      const hardNote = row.conflict_level === 'hard'
        ? `<div style="margin-top:5px;padding:6px 8px;background:#fef2f2;border-left:3px solid #dc2626;border-radius:0 4px 4px 0;font-size:10.5px;color:#991b1b;line-height:1.45">⚠️ This company's pipeline directly competes with ${asset.label} — partnership may face internal resistance from their BD team.</div>`
        : '';
      return `<div style="margin-bottom:10px;padding:10px;background:${m.bg};border-radius:8px;border:0.5px solid ${m.badge}22">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
          <span style="font-size:11px;font-weight:800;color:#1e293b">${asset.label}</span>
          <span style="font-size:9.5px;color:#64748b">${asset.desc}</span>
          <span style="margin-left:auto;font-size:10px;font-weight:700;background:${m.bg};color:${m.badge};border:1px solid ${m.badge}40;border-radius:6px;padding:2px 8px">${m.icon} ${m.label}</span>
        </div>
        <div style="font-size:11px;color:#334155;line-height:1.45">${(row.conflict_rationale||'').slice(0,200)+(row.conflict_rationale&&row.conflict_rationale.length>200?'…':'')}</div>
        ${drugList}${hardNote}${comboNote}
      </div>`;
    }).join('');
    const _conflictSection = conflicts.length > 0
      ? _conflictHtml || '<div style="font-size:11px;color:#94a3b8;font-style:italic">No conflict data on record.</div>'
      : '<div style="font-size:11px;color:#94a3b8;font-style:italic">No conflict analysis on record for this company.</div>';

    // Strategic Value Score badge
    const _svsBadge = svs != null ? (() => {
      const col   = svs >= 80 ? '#15803d' : svs >= 60 ? '#b45309' : '#64748b';
      const bg    = svs >= 80 ? '#dcfce7' : svs >= 60 ? '#fef9c3' : '#f1f5f9';
      const label = svs >= 80 ? 'High priority' : svs >= 60 ? 'Monitor' : 'Lower priority';
      return `<span style="font-size:11px;font-weight:800;background:${bg};color:${col};border-radius:8px;padding:3px 10px;border:1px solid ${col}20">${svs} — ${label}</span>`;
    })() : `<span style="font-size:11px;color:#94a3b8;font-style:italic">Not scored</span>`;

    // View type rows
    const _viewTypeLabel = {competitive:'Competitive threat',partnership:'Partnership target','licensing_candidate':'Licensing candidate','acquisition_target':'Acquisition target'};
    const _svHtml = svViews.map(v => {
      const lbl = _viewTypeLabel[v.view_type] || v.view_type;
      const sc  = v.strategic_score != null ? `<span style="font-size:10px;font-weight:700;color:#1d4ed8;margin-left:6px">${v.strategic_score}</span>` : '';
      return `<div style="margin-bottom:10px;padding-bottom:10px;border-bottom:0.5px solid #e2e8f0">
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
          <span style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:0.04em;background:#eff6ff;color:#1d4ed8;border-radius:4px;padding:2px 7px">${lbl}</span>${sc}
          ${v.confidence_source==='model'?`<span style="font-size:9px;color:#94a3b8">model</span>`:''}
        </div>
        ${v.summary ? `<div style="font-size:11px;color:#1e293b;line-height:1.5;margin-bottom:3px">${v.summary.slice(0,200)+(v.summary.length>200?'…':'')}</div>` : ''}
        ${v.ailux_relevance ? `<div style="font-size:11px;color:#64748b;font-style:italic">${v.ailux_relevance.slice(0,150)+(v.ailux_relevance.length>150?'…':'')}</div>` : ''}
      </div>`;
    }).join('') || '<div style="font-size:11px;color:#94a3b8;font-style:italic">No strategic view classification on record.</div>';

    // Platform type rows
    const _pvHtml = pvViews.map(v => {
      const pot = v.partnership_potential;
      const potCol = pot==='high'?'#15803d':pot==='medium'?'#b45309':'#64748b';
      const potBg  = pot==='high'?'#dcfce7':pot==='medium'?'#fef9c3':'#f1f5f9';
      return `<div style="margin-bottom:8px">
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:3px">
          <span style="font-size:10px;font-weight:700;background:#f5f3ff;color:#7c3aed;border-radius:4px;padding:2px 7px;text-transform:capitalize">${(v.platform_type||'').replace(/_/g,' ')}</span>
          ${pot?`<span style="font-size:9px;font-weight:700;background:${potBg};color:${potCol};border-radius:4px;padding:1px 5px">${pot} potential</span>`:''}
        </div>
        ${v.platform_description ? `<div style="font-size:11px;color:#1e293b;line-height:1.45">${v.platform_description.slice(0,180)+(v.platform_description.length>180?'…':'')}</div>` : ''}
        ${v.relevance_to_ailux ? `<div style="font-size:11px;color:#64748b;margin-top:2px;font-style:italic">${v.relevance_to_ailux.slice(0,150)+(v.relevance_to_ailux.length>150?'…':'')}</div>` : ''}
      </div>`;
    }).join('') || '<div style="font-size:11px;color:#94a3b8;font-style:italic">No platform classification on record.</div>';

    // Recent deals
    const _SIG_DEAL_STYLE = {licensing:{bg:'#fff7ed',color:'#c2410c'},acquisition:{bg:'#fef2f2',color:'#b91c1c'},'co-development':{bg:'#f0fdf4',color:'#15803d'},collaboration:{bg:'#eff6ff',color:'#1d4ed8'}};
    const _dealHtml = deals24m.map(d => {
      const sty = _SIG_DEAL_STYLE[d.deal_type] || {bg:'#f8fafc',color:'#64748b'};
      const val = d.upfront_usd_m ? `<span style="font-size:10px;font-weight:700;color:#15803d;margin-left:4px">$${d.upfront_usd_m>=1000?(d.upfront_usd_m/1000).toFixed(1)+'B':Math.round(d.upfront_usd_m)+'M'} upfront</span>` : '';
      return `<div style="display:flex;gap:8px;align-items:flex-start;margin-bottom:6px">
        <span style="font-size:8px;font-weight:700;background:${sty.bg};color:${sty.color};border-radius:4px;padding:2px 5px;flex-shrink:0;margin-top:2px">${(d.deal_type||'deal').toUpperCase().slice(0,8)}</span>
        <div style="flex:1">
          <div style="font-size:11.5px;color:#1e293b;line-height:1.35">${d.headline||'Deal'}</div>
          <div style="font-size:10px;color:#94a3b8;margin-top:1px">${d.deal_date?d.deal_date.slice(0,10):''}${val}</div>
        </div>
      </div>`;
    }).join('') || '<div style="font-size:11px;color:#94a3b8;font-style:italic">No deals in the last 24 months.</div>';

    panel.innerHTML = `
      <div style="margin-bottom:20px;padding-bottom:18px;border-bottom:1px solid #e2e8f0">
        <div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#64748b;margin-bottom:10px">Portfolio Conflict Analysis
          <span style="font-size:9px;font-weight:400;color:#94a3b8;text-transform:none;letter-spacing:0"> · vs Ailux ALX001 / ALX002 / ALX005</span>
        </div>
        ${_conflictSection}
      </div>
      <div style="margin-bottom:20px">
        <div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#64748b;margin-bottom:8px">Strategic Value Score</div>
        <div style="display:flex;align-items:center;gap:10px">${_svsBadge}</div>
        <div style="font-size:10px;color:#94a3b8;margin-top:4px">0–100 scale · ≥80 = high BD priority · 60–79 = monitor · &lt;60 = lower priority</div>
      </div>
      <div style="margin-bottom:20px">
        <div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#64748b;margin-bottom:8px">Strategic View Classification</div>
        ${_svHtml}
      </div>
      <div style="margin-bottom:20px">
        <div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#64748b;margin-bottom:8px">Platform Type</div>
        ${_pvHtml}
      </div>
      <div>
        <div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#64748b;margin-bottom:8px">Deal Activity · Last 24 Months <span style="font-weight:400;color:#94a3b8">${deals24m.length} deals</span></div>
        ${_dealHtml}
      </div>`;
  } catch(e) {
    panel.innerHTML = `<div style="padding:16px;color:#dc2626;font-size:12px">Failed to load BD intelligence: ${e.message}</div>`;
  }
}

