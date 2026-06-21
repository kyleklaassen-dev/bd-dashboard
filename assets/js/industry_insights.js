// ── INDUSTRY INSIGHTS FEED v2 (+ live intel) ──────────────────────
// Extracted from app.js (Domain A2, §3 byte-identical). Plain script, load BEFORE app.js.
// Self-contained: IIF_* maps + _iif* state/helpers move together; referenced only via the
// industry-insights tab-registry closure (runtime). External: _sb (core.js), DOM.

// ── Industry Insights Feed v2 ─────────────────────────────────────────────────
const IIF_TYPE_MAP = {
  // event_type values (new canonical)
  'clinical_data':  { cat:'clinical_data', label:'Clinical Data', cls:'clinical_data' },
  'deal':           { cat:'deal',          label:'BD Deal',       cls:'deal' },
  'regulatory':     { cat:'regulatory',    label:'Regulatory',    cls:'regulatory' },
  'partnership':    { cat:'partnership',   label:'Partnership',   cls:'partnership' },
  'pipeline':       { cat:'pipeline',      label:'Pipeline',      cls:'pipeline' },
  'publication':    { cat:'publication',   label:'Publication',   cls:'publication' },
  'market':         { cat:'market',        label:'Market',        cls:'market' },
  'other':          { cat:'other',         label:'Other',         cls:'other' },
  'signal':         { cat:'other',         label:'Signal',        cls:'signal' },
  // legacy intel_type fallbacks
  'clinical':       { cat:'clinical_data', label:'Clinical Data', cls:'clinical_data' },
  'clinical_update':{ cat:'clinical_data', label:'Clinical Data', cls:'clinical_data' },
  'data':           { cat:'clinical_data', label:'Clinical Data', cls:'clinical_data' },
  'conference':     { cat:'publication',   label:'Publication',   cls:'publication' },
  'financing':      { cat:'other',         label:'Other',         cls:'other' },
  'management':     { cat:'other',         label:'Other',         cls:'other' },
  'licensing':      { cat:'deal',          label:'BD Deal',       cls:'deal' },
  'patent':         { cat:'other',         label:'Patent',        cls:'other' },
  'news':           { cat:'pipeline',      label:'Pipeline',      cls:'pipeline' },
  'user_submitted': { cat:'publication',   label:'Submitted',     cls:'news' },
};
const IIF_AREA_LABELS = {
  'tl1a':'TL1A','tslp':'TSLP','il4ra':'IL-4Rα','il4ra-tslp':'IL-4Rα×TSLP',
  'il4ra-ox40l':'IL-4Rα×OX40L','igf1r':'IGF-1R','igf1r-tshr':'IGF-1R×TSHR',
  'fcrn':'FcRn','ted':'TED','respiratory':'Respiratory','atopy':'Atopy',
  'ibd':'IBD','autoimmune':'Autoimmune','ace':'ALX002','tl1a-ibd':'TL1A×IBD'
};
const IIF_AREA_CLS = {
  'tl1a':'tl1a','tslp':'tslp','il4ra':'il4ra','il4ra-tslp':'il4ra',
  'igf1r':'igf1r','igf1r-tshr':'igf1r','fcrn':'fcrn','ted':'ted',
  'respiratory':'respiratory','ibd':'ibd'
};

let _iifLoaded = false;
let _iifItems  = [];
let _iifCompanyMap = {};  // id -> name
let _iifFilters = {
  cat:     'all',      // event_type category
  src:     'all',      // 'all' | 'intel' | 'news'
  range:   'all',      // 'all' | 'today' | 'week' | 'month'
  rel:     'all',      // 'all' | 'high' | 'med'
  company: '',         // company id string
  areaSet: null,       // Set<string> of area_ids to include, null = no filter
};

async function loadIndustryInsightsFeed() {
  if (_iifLoaded) { iifRender(); return; }
  const feed = document.getElementById('iif-feed');
  if (!feed) return;
  feed.innerHTML = '<div class="iif-loading">Loading intelligence feed…</div>';
  try {
    // Learned-content sources (Kyle 2026-06-07: everything we learn lives in this tab)
    const [pubRes, absRes, insRes, grantRes, evtRes, chinaRes] = await Promise.all([
      _sb.from('publications').select('id,title,journal,pub_date,pub_year,doi,url,cited_by_count,tldr')
         .not('title','is',null).order('pub_date',{ascending:false,nullsFirst:false}).limit(400),
      _sb.from('conference_abstracts').select('id,title,conference,conference_year,presentation_date,presentation_type,doi,source_url,drug_id')
         .not('title','is',null).order('conference_year',{ascending:false}).limit(300),
      _sb.from('strategic_insights').select('id,title,detail,insight_type,metric,created_at,source_tables')
         .order('created_at',{ascending:false}).limit(450),
      _sb.from('grants').select('id,title,agency,fiscal_year,award_amount,matched_target,org_name,project_url,source_url')
         .not('title','is',null).order('fiscal_year',{ascending:false}).limit(300),
      _sb.from('company_events').select('id,doc_title,event_type,event_subtype,event_summary,filing_date,financing_type,offering_amount_text,source_url,company_id')
         .neq('event_type','other').order('filing_date',{ascending:false}).limit(300),
      _sb.from('china_intel').select('id,title,signal_type,published_date,url,source').limit(50),
    ]);
    const [iaRes, intelRes, sigRes, dealRes, naRes, coRes] = await Promise.all([
      _sb.from('intel_areas').select('intel_id,area_id,target_id,context_type').limit(2000),
      _sb.from('intel').select('id,intel_date,headline,body,source_url,source_name,intel_type,event_type,importance,primary_company_id')
         .order('intel_date',{ascending:false}).limit(300),
      _sb.from('competitive_signals').select('id,signal_type,title,description,source_url,source_date,area_id,target_id,context_type')
         .order('source_date',{ascending:false}).limit(200),
      _sb.from('deals').select('id,deal_date,headline,total_usd_m,upfront_usd_m,source_url,area_id')
         .order('deal_date',{ascending:false}).limit(100),
      _sb.from('news_articles')
         .select('id,published_at,headline,meridian_summary,why_it_matters,article_url,source_name,relevance_score,priority_level,event_type,matched_area_ids,matched_drug_ids,matched_company_ids')
         .neq('source_validation_status','invalid')
         .order('published_at',{ascending:false,nullsFirst:false})
         .limit(150),
      _sb.from('companies').select('id,name').order('name').limit(200),
    ]);

    // Build company map for name lookup
    _iifCompanyMap = {};
    (coRes.data||[]).forEach(c => { _iifCompanyMap[c.id] = c.name; });

    // Populate company dropdown - alphabetically sorted
    const sel = document.getElementById('iif-sel-company');
    if (sel && sel.options.length <= 1) {
      const seen2 = new Set();
      [...(intelRes.data||[]).map(x=>x.primary_company_id).filter(Boolean),
       ...(naRes.data||[]).flatMap(x=>x.matched_company_ids||[])
      ].forEach(id => { if (_iifCompanyMap[id]) seen2.add(id); });
      Array.from(seen2)
        .sort((a,b) => (_iifCompanyMap[a]||'').localeCompare(_iifCompanyMap[b]||''))
        .forEach(id => {
          const opt = document.createElement('option');
          opt.value = id; opt.textContent = _iifCompanyMap[id];
          sel.appendChild(opt);
        });
    }

    // Build intel->area map
    const areaMap = {};
    (iaRes.data||[]).forEach(r => { (areaMap[r.intel_id]=areaMap[r.intel_id]||[]).push(r.area_id); });

    // Importance/relevance to numeric score (0-1) for filtering
    const importanceScore = { high:0.9, medium:0.6, low:0.3 };

    // Normalise intel items
    const intelItems = (intelRes.data||[]).filter(x=>x.headline).map(x => ({
      _key:       'intel-'+x.id,
      date:       x.intel_date,
      headline:   x.headline,
      body:       x.body || '',
      sources:    x.source_url ? [{name: x.source_name||'Source', url: x.source_url}] : [],
      event_type: x.event_type || x.intel_type || 'signal',
      areas:      areaMap[x.id] || [],
      source_type:'intel',
      company_id: x.primary_company_id || '',
      rel_score:  importanceScore[x.importance] || 0.5,
    }));

    // Normalise competitive_signals
    const sigItems = (sigRes.data||[]).filter(x=>x.title).map(x => ({
      _key:       'sig-'+x.id,
      date:       x.source_date,
      headline:   x.title,
      body:       x.description || '',
      sources:    x.source_url ? [{name:'Source', url: x.source_url}] : [],
      event_type: x.signal_type || 'signal',
      areas:      x.area_id ? [x.area_id] : [],
      source_type:'intel',
      company_id: '',
      rel_score:  0.5,
    }));

    // Normalise deal items
    const dealItems = (dealRes.data||[]).filter(x=>x.headline).map(x => ({
      _key:       'deal-'+x.id,
      date:       x.deal_date,
      headline:   x.headline,
      body:       x.total_usd_m ? ('Total: $'+x.total_usd_m+'M'+(x.upfront_usd_m?' · $'+x.upfront_usd_m+'M upfront':'')) : '',
      sources:    x.source_url ? [{name:'Source', url: x.source_url}] : [],
      event_type: 'deal',
      areas:      x.area_id ? [x.area_id] : [],
      source_type:'intel',
      company_id: '',
      rel_score:  0.7,
    }));

    // Normalise news_articles
    const newsItems = (naRes.data||[]).filter(x=>x.headline).map(x => ({
      _key:       'na-'+x.id,
      date:       x.published_at ? x.published_at.slice(0,10) : '',
      headline:   x.headline,
      body:       x.meridian_summary || x.why_it_matters || '',
      sources:    x.article_url ? [{name: x.source_name||'News', url: x.article_url}] : [],
      event_type: x.event_type || 'pipeline',
      areas:      x.matched_area_ids || [],
      source_type:'news',
      company_id: (x.matched_company_ids||[])[0] || '',
      rel_score:  x.relevance_score ? x.relevance_score / 100 : 0.3,
    }));

    // Normalise publications (PubMed/Europe PMC corpus)
    const pubItems = (pubRes.data||[]).map(x => ({
      _key:'pub-'+x.id,
      date: x.pub_date ? String(x.pub_date).slice(0,10) : (x.pub_year ? x.pub_year+'-01-01' : ''),
      headline: x.title,
      body: [x.journal, x.cited_by_count?x.cited_by_count+' citations':null, x.tldr].filter(Boolean).join(' · '),
      sources: (x.doi||x.url) ? [{name: x.journal||'Paper', url: x.doi?('https://doi.org/'+x.doi):x.url}] : [],
      event_type:'publication', areas:[], source_type:'publication', company_id:'',
      rel_score: Math.min(0.3 + (x.cited_by_count||0)/200, 0.95),
    }));
    // Normalise conference abstracts (congress presence)
    const absItems = (absRes.data||[]).map(x => ({
      _key:'abs-'+x.id,
      date: x.presentation_date ? String(x.presentation_date).slice(0,10) : (x.conference_year ? x.conference_year+'-01-01' : ''),
      headline: x.title,
      body: [x.conference, x.conference_year, x.presentation_type, x.drug_id?('asset: '+x.drug_id):null].filter(Boolean).join(' · '),
      sources: (x.doi||x.source_url) ? [{name: x.conference||'Congress', url: x.doi?('https://doi.org/'+x.doi):x.source_url}] : [],
      event_type:'publication', areas:[], source_type:'abstract', company_id:'',
      rel_score: x.presentation_type==='late_breaker' ? 0.9 : 0.5,
    }));
    // Normalise strategic insights (Meridian's derived, cited conclusions)
    const insTypeMap = {deal_event:'deal', ma_event:'deal', financing_signal:'market', funding_momentum:'market',
      eu_approval_lag:'regulatory', orphan_designation:'regulatory', label_safety:'regulatory',
      trial_quality:'clinical_data', conference_readout:'clinical_data', readout_imminent:'clinical_data',
      partnership_termination:'partnership', patent_fto:'other', china_blind_spot:'market'};
    const insItems = (insRes.data||[]).map(x => ({
      _key:'ins-'+x.id,
      date: x.created_at ? String(x.created_at).slice(0,10) : '',
      headline: x.title,
      body: [x.detail, x.metric].filter(Boolean).join(' · ') + (x.source_tables?' — derived from: '+[].concat(x.source_tables).join(', '):''),
      sources: [],
      event_type: insTypeMap[x.insight_type] || 'other',
      areas:[], source_type:'conclusion', company_id:'',
      rel_score: 0.75,
    }));
    // Normalise NIH grants (upstream academic signal)
    const grantItems = (grantRes.data||[]).map(x => ({
      _key:'grant-'+x.id,
      date: x.fiscal_year ? x.fiscal_year+'-01-01' : '',
      headline: x.title,
      body: [x.agency, x.org_name, x.matched_target?('target: '+x.matched_target):null,
             x.award_amount?('$'+Math.round(x.award_amount/1000)+'k'):null].filter(Boolean).join(' · '),
      sources: (x.project_url||x.source_url) ? [{name:'NIH RePORTER', url:x.project_url||x.source_url}] : [],
      event_type:'other', areas:[], source_type:'grant', company_id:'',
      rel_score: Math.min(0.3 + (x.award_amount||0)/3e6, 0.9),
    }));
    // Normalise SEC company events (8-K typed: deals / leadership / financing)
    const evtTypeMap = {deal:'deal', ma:'deal', financing:'market', leadership:'other', pipeline:'pipeline'};
    const evtItems = (evtRes.data||[]).map(x => ({
      _key:'evt-'+x.id,
      date: x.filing_date ? String(x.filing_date).slice(0,10) : '',
      headline: x.event_summary || x.doc_title || (x.event_type+' — SEC filing'),
      body: [x.event_type, x.event_subtype, x.financing_type, x.offering_amount_text].filter(Boolean).join(' · '),
      sources: x.source_url ? [{name:'SEC EDGAR', url:x.source_url}] : [],
      event_type: evtTypeMap[x.event_type] || 'other',
      areas:[], source_type:'sec', company_id: x.company_id||'',
      rel_score: (x.event_type==='deal'||x.event_type==='ma') ? 0.8 : 0.55,
    }));
    // Normalise China signal
    const chinaItems = (chinaRes.data||[]).map(x => ({
      _key:'cn-'+x.id,
      date: x.published_date ? String(x.published_date).slice(0,10) : '',
      headline: x.title,
      body: [x.signal_type, x.source, 'China-language signal'].filter(Boolean).join(' · '),
      sources: x.url ? [{name:'GDELT', url:x.url}] : [],
      event_type:'market', areas:[], source_type:'intel', company_id:'',
      rel_score: 0.5,
    }));

    // Merge and deduplicate by normalised headline + date
    const seen = {};
    [...intelItems, ...sigItems, ...dealItems, ...newsItems,
     ...pubItems, ...absItems, ...insItems, ...grantItems, ...evtItems, ...chinaItems].forEach(item => {
      if (!item.date || !item.headline) return;
      const key = item.headline.toLowerCase().replace(/[^a-z0-9]/g,'').substring(0,60)+'|'+item.date;
      if (!seen[key]) {
        seen[key] = Object.assign({}, item, {sources:[...item.sources]});
      } else {
        item.sources.forEach(s => { if (!seen[key].sources.find(x=>x.url===s.url)) seen[key].sources.push(s); });
        if (!seen[key].body && item.body) seen[key].body = item.body;
        if (item.rel_score > seen[key].rel_score) seen[key].rel_score = item.rel_score;
      }
    });

    _iifItems = Object.values(seen).sort((a,b) => {
      if (!a.date && !b.date) return 0;
      if (!a.date) return 1; if (!b.date) return -1;
      return b.date > a.date ? 1 : b.date < a.date ? -1 : 0;
    });
    _iifLoaded = true;
    iifRender();
  } catch(e) {
    const feed2 = document.getElementById('iif-feed');
    if (feed2) feed2.innerHTML = '<div class="iif-empty">Error loading feed: '+e.message+'</div>';
    console.error('[IIF]', e);
  }
}


function iifSetFilter(dim, val) {
  if (['company','cat','src','range','rel'].includes(dim)) _iifFilters[dim] = val;
  const selMap = { cat:'.iif-pill', src:'.iif-src-pill', range:'.iif-date-pill', rel:'.iif-rel-pill' };
  if (selMap[dim]) {
    document.querySelectorAll('.iif-sb-pill' + selMap[dim]).forEach(p => {
      p.classList.toggle('active', (p.dataset[dim]||'') === val);
    });
  }
  iifRender();
}

function iifResetFilters() {
  _iifFilters = { cat:'all', src:'all', range:'all', rel:'all', company:'', areaSet:null };
  document.querySelectorAll('.iif-sb-pill.iif-pill').forEach(p => p.classList.toggle('active', p.dataset.cat==='all'));
  document.querySelectorAll('.iif-sb-pill.iif-src-pill').forEach(p => p.classList.toggle('active', p.dataset.src==='all'));
  document.querySelectorAll('.iif-sb-pill.iif-date-pill').forEach(p => p.classList.toggle('active', p.dataset.range==='all'));
  document.querySelectorAll('.iif-sb-pill.iif-rel-pill').forEach(p => p.classList.toggle('active', p.dataset.rel==='all'));
  const cs = document.getElementById('iif-sel-company'); if (cs) cs.value = '';
  const ts = document.getElementById('iif-sel-therapeutic'); if (ts) ts.value = '';
  const is_ = document.getElementById('iif-sel-indication');
  if (is_) is_.innerHTML = '<option value="">All Indications</option>';
  const tgt = document.getElementById('iif-sel-target');
  if (tgt) tgt.innerHTML = '<option value="">All Targets</option>';
  const iis = document.getElementById('iif-sel-indication'); if (iis) { iis.innerHTML='<option value="">All Indications</option>'; iis.style.display='none'; }
  const its = document.getElementById('iif-sel-target');      if (its) { its.innerHTML='<option value="">All Targets</option>';     its.style.display='none'; }
  iifRender();
}

// Legacy compatibility
function iifFilter(cat) { iifSetFilter('cat', cat); }

// Hierarchical area filter data
const IIF_HIER = {
  indication: {
    immuno: [
      { val:'ibd_i',        label:'Inflammatory Bowel Disease', areas:['tl1a','ibd'] },
      { val:'autoimmune_i', label:'Autoimmune (Broad)',         areas:['autoimmune'] },
    ],
    resp: [
      { val:'atopy_i', label:'Atopy / Allergy',     areas:['tslp','il4ra'] },
      { val:'resp_i',  label:'Respiratory (Broad)', areas:['respiratory','fcrn'] },
    ],
    endo: [
      { val:'ted_i', label:'Thyroid Eye Disease', areas:['igf1r','ted'] },
    ],
  },
  target: {
    ibd_i:        [{val:'tl1a',label:'TL1A'},{val:'ibd',label:'IBD (General)'}],
    autoimmune_i: [{val:'autoimmune',label:'Autoimmune (General)'}],
    atopy_i:      [{val:'tslp',label:'TSLP'},{val:'il4ra',label:'IL-4Rα'}],
    resp_i:       [{val:'respiratory',label:'Respiratory (General)'},{val:'fcrn',label:'FcRn'}],
    ted_i:        [{val:'igf1r',label:'IGF-1R / TSHr'},{val:'ted',label:'TED (General)'}],
  },
  therapeuticAreas: {
    immuno: ['tl1a','ibd','autoimmune'],
    resp:   ['tslp','il4ra','respiratory','fcrn'],
    endo:   ['igf1r','ted'],
  },
};

function iifHierFilter(level, val) {
  const indicSel  = document.getElementById('iif-sel-indication');
  const targetSel = document.getElementById('iif-sel-target');

  if (level === 'therapeutic') {
    if (indicSel)  { indicSel.innerHTML  = '<option value="">All Indications</option>'; indicSel.style.display = 'none'; }
    if (targetSel) { targetSel.innerHTML = '<option value="">All Targets</option>';      targetSel.style.display = 'none'; }
    if (!val) {
      _iifFilters.areaSet = null;
    } else {
      if (indicSel) indicSel.style.display = '';
      (IIF_HIER.indication[val]||[]).forEach(i => {
        const o = document.createElement('option');
        o.value = i.val; o.textContent = i.label;
        if (indicSel) indicSel.appendChild(o);
      });
      _iifFilters.areaSet = new Set(IIF_HIER.therapeuticAreas[val]||[]);
    }

  } else if (level === 'indication') {
    if (targetSel) { targetSel.innerHTML = '<option value="">All Targets</option>'; targetSel.style.display = 'none'; }
    if (!val) {
      const tv = (document.getElementById('iif-sel-therapeutic')||{}).value||'';
      _iifFilters.areaSet = tv ? new Set(IIF_HIER.therapeuticAreas[tv]||[]) : null;
    } else {
      if (targetSel) targetSel.style.display = '';
      (IIF_HIER.target[val]||[]).forEach(t => {
        const o = document.createElement('option');
        o.value = t.val; o.textContent = t.label;
        if (targetSel) targetSel.appendChild(o);
      });
      const allIndics = Object.values(IIF_HIER.indication).flat();
      const found = allIndics.find(i => i.val === val);
      _iifFilters.areaSet = found ? new Set(found.areas) : null;
    }

  } else if (level === 'target') {
    if (!val) {
      const iv = (indicSel||{}).value||'';
      const allIndics = Object.values(IIF_HIER.indication).flat();
      const found = allIndics.find(i => i.val === iv);
      _iifFilters.areaSet = found ? new Set(found.areas) : null;
    } else {
      _iifFilters.areaSet = new Set([val]);
    }
  }

  iifRender();
}

// Sync sidebar top/height to sit below sticky header + tab-bar
function _iifSyncSidebar() {
  const header  = document.querySelector('.header');
  const tabBar  = document.querySelector('.tab-bar');
  const sidebar = document.getElementById('iif-sidebar');
  if (!sidebar) return;
  const offset = Math.round(
    (header ? header.getBoundingClientRect().height : 0) +
    (tabBar  ? tabBar.getBoundingClientRect().height  : 0)
  );
  sidebar.style.top    = offset + 'px';
  sidebar.style.height = 'calc(100vh - ' + offset + 'px)';
}
window.addEventListener('resize', _iifSyncSidebar);

function iifRender() {
  const feed = document.getElementById('iif-feed');
  if (!feed) return;
  const f = _iifFilters;

  // Date range cutoffs
  const today = new Date(); today.setHours(0,0,0,0);
  const weekAgo  = new Date(today); weekAgo.setDate(today.getDate()-7);
  const monthAgo = new Date(today); monthAgo.setMonth(today.getMonth()-1);

  let items = _iifItems.filter(item => {
    if (f.src !== 'all' && item.source_type !== f.src) return false;
    if (f.cat !== 'all') {
      const m = IIF_TYPE_MAP[item.event_type];
      const cat = m ? m.cat : item.event_type;
      if (cat !== f.cat) return false;
    }
    if (f.range !== 'all' && item.date) {
      const d = new Date(item.date + 'T00:00:00');
      if (f.range === 'today' && d < today) return false;
      if (f.range === 'week'  && d < weekAgo) return false;
      if (f.range === 'month' && d < monthAgo) return false;
    }
    if (f.rel === 'high' && item.rel_score < 0.75) return false;
    if (f.rel === 'med'  && item.rel_score < 0.5)  return false;
    if (f.company && item.company_id !== f.company) return false;
    if (f.areaSet && !((item.areas||[]).some(a => f.areaSet.has(a)))) return false;
    return true;
  });

  const bar = document.getElementById('iif-results-bar');
  if (bar) bar.textContent = '';

  if (!items.length) { feed.innerHTML = '<div class="iif-empty">No items match the current filters.</div>'; return; }

  const totalCount = items.length;
  // Render cap — the corpus is now ~2,400 items (pubs/abstracts/conclusions/grants/SEC added 2026-06-07)
  const RENDER_CAP = 600;
  const capped = items.length > RENDER_CAP;
  if (capped) items = items.slice(0, RENDER_CAP);
  let lastDay = ''; let firstDay = true; let html = '';
  items.forEach(item => {
    const dayStr = _iifFormatDay(item.date);
    if (dayStr !== lastDay) {
      const countBadge = firstDay ? `<span class="iif-day-count">${totalCount} item${totalCount===1?'':'s'}</span>` : '';
      html += `<div class="iif-day-sep">${dayStr}${countBadge}</div>`;
      lastDay = dayStr; firstDay = false;
    }
    const et = item.event_type || 'signal';
    const tm = IIF_TYPE_MAP[et] || {label: et, cls:'news'};
    const SRC_BADGES = {news:['iif-source-badge-news','NEWS'], intel:['iif-source-badge-intel','INTEL'],
      publication:['iif-source-badge-intel','PAPER'], abstract:['iif-source-badge-intel','CONGRESS'],
      conclusion:['iif-source-badge-intel','MERIDIAN'], grant:['iif-source-badge-intel','GRANT'],
      sec:['iif-source-badge-news','SEC']};
    const [srcBadgeCls, srcLabel] = SRC_BADGES[item.source_type] || SRC_BADGES.intel;
    const areaPills = (item.areas||[]).map(a =>
      `<span class="iif-area-pill iif-area-${IIF_AREA_CLS[a]||'default'}">${IIF_AREA_LABELS[a]||a}</span>`
    ).join('');
    const companyName = item.company_id ? (_iifCompanyMap[item.company_id]||item.company_id) : '';
    const companyChip = companyName ? `<span class="iif-company-name">${_iifEsc(companyName)}</span>` : '';
    const relCls = item.rel_score >= 0.75 ? 'iif-card-rel-high' : item.rel_score >= 0.5 ? 'iif-card-rel-medium' : 'iif-card-rel-low';
    const hasBody = !!item.body;
    const hlUrl = (item.sources && item.sources[0] && item.sources[0].url) || ''; // direct source only — no Google fallback (Kyle 2026-06-08)
    const toggleAttr = hasBody ? ` onclick="iifToggleCard('${item._key}')"` : '';
    html += `<div class="iif-card" id="iif-card-${item._key}"${toggleAttr}><div class="iif-card-rel ${relCls}"></div><div class="iif-card-inner">
  <div class="iif-card-top">
    <span class="iif-date">${item.date||''}</span>
    <span class="iif-source-badge ${srcBadgeCls}">${srcLabel}</span>
    <span class="iif-type-badge iif-type-${tm.cls}">${tm.label}</span>${companyChip}${areaPills}
  </div>
  ${(item.sources&&item.sources.length)||item.source_type!=='conclusion'
    ? `<a class="iif-headline" href="${hlUrl}" target="_blank" rel="noopener" onclick="event.stopPropagation()">${_iifEsc(item.headline)}</a>`
    : `<span class="iif-headline" style="cursor:inherit">${_iifEsc(item.headline)}</span>`}
  ${hasBody?`<div class="iif-meta"><span class="iif-expand-icon">&#9660;</span></div>`:''}
  ${hasBody?`<div class="iif-body-text" id="iif-body-${item._key}">${_iifEsc(item.body)}</div>`:''}
</div></div>`;
  });
  if (capped) html += `<div class="iif-empty">Showing the ${RENDER_CAP} most recent of ${totalCount} matching items — use the filters to narrow.</div>`;
  feed.innerHTML = html;
}

function _iifSrcHTML(key, sources) {
  if (!sources||!sources.length) return '';
  if (sources.length === 1) {
    const s = sources[0];
    return s.url
      ? `<a class="iif-source-link" href="${s.url}" target="_blank" rel="noopener" onclick="event.stopPropagation()">${_iifEsc(s.name||'Source')} ↗</a>`
      : `<span style="font-size:11px;color:#94a3b8">${_iifEsc(s.name||'')}</span>`;
  }
  const items = sources.map((s,i) => s.url
    ? `<a class="iif-source-dd-item" href="${s.url}" target="_blank" rel="noopener" onclick="event.stopPropagation()">${_iifEsc(s.name||'Source '+(i+1))}<span style="margin-left:auto;color:#94a3b8;font-size:10px">↗</span></a>`
    : `<div class="iif-source-dd-item">${_iifEsc(s.name||'Source '+(i+1))}</div>`
  ).join('');
  return `<div class="iif-source-dd-wrap">
  <button class="iif-source-dd-btn" onclick="event.stopPropagation();_iifToggleSrc('${key}')">${sources.length} sources ▾</button>
  <div class="iif-source-dd" id="iif-src-${key}">${items}</div>
</div>`;
}

function _iifToggleSrc(key) {
  const dd = document.getElementById('iif-src-'+key);
  if (!dd) return;
  const open = dd.classList.toggle('open');
  if (open) {
    document.querySelectorAll('.iif-source-dd.open').forEach(d=>{ if(d!==dd) d.classList.remove('open'); });
    setTimeout(()=>{
      document.addEventListener('click', function _c(e){
        if(!dd.contains(e.target)){ dd.classList.remove('open'); document.removeEventListener('click',_c); }
      });
    },0);
  }
}

function iifToggleCard(key) {
  const card = document.getElementById('iif-card-'+key);
  const body = document.getElementById('iif-body-'+key);
  if (!body) return;
  card?.classList.toggle('open');
  body.classList.toggle('open');
}

function _iifFormatDay(d) {
  if (!d) return 'Unknown date';
  try {
    const dt = new Date(d+'T00:00:00');
    return dt.toLocaleDateString('en-US',{month:'long',day:'numeric',year:'numeric'});
  } catch { return d; }
}
function _iifEsc(s) {
  if (!s) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}


async function loadLiveIntel() {
  const body = document.getElementById('ii-live-body');
  if (!body) return;
  try {
    const { data: iaRows } = await _sb.from('intel_areas').select('intel_id,area_id,target_id,context_type').limit(200);
    const { data: rows, error } = await _sb.from('intel')
      .select('*').order('intel_date', { ascending: false }).limit(40);
    if (error) throw error;
    if (!rows || !rows.length) {
      body.innerHTML = '<div style="color:#94a3b8;font-size:12px;">No intelligence yet — research pipeline runs Mon–Sat at 4 AM ET.</div>';
      return;
    }
    const areaMap = {};
    (iaRows||[]).forEach(r => { if (!areaMap[r.intel_id]) areaMap[r.intel_id] = []; areaMap[r.intel_id].push(r.area_id); });
    body.innerHTML = rows.map(item => {
      const dot   = item.importance==='high'?'🔴':item.importance==='medium'?'🟡':'⚪';
      const areas = (areaMap[item.id]||[]).map(a =>
        `<span class="ii-live-area" style="background:${AREA_COLORS[a]||'#4b5563'}">${AREA_LABELS[a]||a}</span>`
      ).join('');
      const src = item.source_url
        ? `<a href="${item.source_url}" target="_blank" rel="noopener" style="font-size:10px;color:#2563eb;margin-left:6px;" onclick="event.stopPropagation()">↗</a>`
        : '';
      const hasDetail = item.body || item.source_name;
      return `<div class="ii-item" onclick="iiToggle('${item.id}')">
  <div class="ii-item-row">
    <span class="ii-item-dot">${dot}</span>
    <span class="ii-item-areas">${areas}</span>
    <span class="ii-item-headline">${item.headline||''}</span>
    <span class="ii-item-date">${item.intel_date||''}</span>
    ${hasDetail ? `<span class="ii-item-chevron" id="ii-chev-${item.id}">▶</span>` : '<span class="ii-item-chevron"></span>'}
  </div>
  ${hasDetail ? `<div class="ii-item-detail" id="ii-detail-${item.id}">
    ${item.body ? `<div class="ii-item-detail-body">${item.body}</div>` : ''}
    ${(item.source_name||item.source_url) ? `<div class="ii-item-detail-meta">${item.source_name||''}${src}</div>` : ''}
  </div>` : ''}
</div>`;
    }).join('');
  } catch(e) {
    if (body) body.innerHTML = `<div style="color:#dc2626;font-size:12px">Error: ${e.message}</div>`;
  }
}
