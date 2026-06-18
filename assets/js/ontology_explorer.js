  (function(){
    'use strict';

    /* ── Config ──────────────────────────────────────────────────────────── */
    var TODAY = new Date().toISOString().split('T')[0];

    var AREA_META = {
      tl1a:        {label:'TL1A',        color:'#3b82f6', type:'TARGET'},
      ibd:         {label:'IBD',         color:'#8b5cf6', type:'INDICATION'},
      atopy:       {label:'Atopy',       color:'#f59e0b', type:'INDICATION'},
      ted:         {label:'TED',         color:'#10b981', type:'INDICATION'},
      igf1r:       {label:'IGF-1R',      color:'#f97316', type:'TARGET'},
      fcrn:        {label:'FcRn',        color:'#06b6d4', type:'TARGET'},
      tcell:       {label:'T-Cell',      color:'#a78bfa', type:'PLATFORM'},
      respiratory: {label:'Respiratory', color:'#64748b', type:'AREA'},
      autoimmune:  {label:'Autoimmune',  color:'#ec4899', type:'AREA'},
      il4ra:       {label:'IL-4Rα', color:'#22d3ee', type:'TARGET'},
      tslp:        {label:'TSLP',        color:'#84cc16', type:'TARGET'},
    };

    var STAGE_ORDER = ['Preclinical','Phase 1','Phase 2','Phase 3','BLA Filed','Approved'];

    var OVERLAP_COLOR = {
      'Direct':    '#ef4444',
      'Watch':     '#f59e0b',
      'Adjacent':  '#60a5fa',
      'Same-Space':'#9ca3af',
    };
    var OVERLAP_BG = {
      'Direct':    'rgba(239,68,68,.12)',
      'Watch':     'rgba(245,158,11,.12)',
      'Adjacent':  'rgba(96,165,250,.1)',
      'Same-Space':'rgba(156,163,175,.08)',
    };

    var oexSelectedNodes = new Set();

    /* ── Main entry (called by TAB_REGISTRY onEnter + switchOntSubTab) ──── */
    window.oexRender = async function() {
      try { await oexLoadTree();   } catch(e) { console.error('[OEX] tree',   e); }
      try { await oexLoadMatrix(); } catch(e) { console.error('[OEX] matrix', e); }
      try { await oexInitMap();    } catch(e) { console.error('[OEX] map',    e); }
    };

    /* ── Live polling — refresh OEX data every 60s while tab visible ─────── */
    window.OEX_POLL_INTERVAL = 60000;
    window.oexStartPolling = function() {
      if (window._oexPollTimer) clearInterval(window._oexPollTimer);
      window._oexPollTimer = setInterval(async function() {
        var panel = document.getElementById('tab-ontology-explorer');
        if (!panel || panel.style.display === 'none') return;
        try { await oexLoadMatrix(); } catch(e) { console.warn('[OEX poll] matrix', e); }
        try { await oexLoadTree();   } catch(e) { console.warn('[OEX poll] tree',   e); }
        var ts = document.getElementById('oex-ts');
        if (ts) ts.textContent = 'Live · ' + new Date().toLocaleTimeString('en-US', {hour:'2-digit',minute:'2-digit'});
      }, window.OEX_POLL_INTERVAL);
    };
    window.oexStartPolling();


    window.oexCollapseAll = function() {
      document.querySelectorAll('#oex-tree .oex-tc-hd').forEach(function(h){
        h.classList.remove('sel');
        var arr = h.querySelector('.oex-t-arr');
        if (arr) arr.classList.remove('open');
      });
      document.querySelectorAll('#oex-tree .oex-tv-wrap').forEach(function(w){ w.classList.remove('open'); });
      document.querySelectorAll('#oex-tree .oex-tsv-wrap').forEach(function(w){ w.classList.remove('open'); });
    };

    /* ── Tree Panel ──────────────────────────────────────────────────────── */
    async function oexLoadTree() {
      var tree = document.getElementById('oex-tree');
      if (!tree) return;
      tree.innerHTML = '<div style="padding:16px 12px;font-size:11px;color:#3a5a7a">Loading…</div>';

      /* ── Biological Quick View — reads from new ontology tables ── */
      var results = await Promise.all([
        _sb.from('therapeutic_areas').select('id,name,color,sort_order').eq('status','active').order('sort_order'),
        _sb.from('indications').select('id,name,abbreviation,disease_area').order('name'),
        _sb.from('drug_indications').select('drug_id,indication_id').limit(2000),
        _sb.from('drugs').select('id,name,stage').limit(500),
        _sb.from('drug_targets').select('drug_id,target_id').limit(1000),
        _sb.from('companies').select('id,name').neq('status','acquired').order('name').limit(200),
      ]);

      var taRows    = (results[0].data || []);
      var indRows   = (results[1].data || []);
      var diRows    = (results[2].data || []);
      var drugs     = (results[3].data || []);
      var dtRows    = (results[4].data || []);
      var companies = (results[5].data || []);

      /* Build indication → Set<drug_id> */
      var indDrugMap = {};
      diRows.forEach(function(r){
        if (!indDrugMap[r.indication_id]) indDrugMap[r.indication_id] = new Set();
        indDrugMap[r.indication_id].add(r.drug_id);
      });

      /* Map indications to therapeutic areas using same logic as Navigator */
      /* _HIER_LEGACY_TO_TA is a global const defined in the main script */
      var legacyToTA = (typeof _HIER_LEGACY_TO_TA !== 'undefined') ? _HIER_LEGACY_TO_TA : {};

      var taIndMap = {};
      indRows.forEach(function(ind){
        var taId = legacyToTA[ind.id] || legacyToTA[ind.disease_area];
        if (!taId) return;
        if (!taIndMap[taId]) taIndMap[taId] = [];
        taIndMap[taId].push(ind);
      });

      var stageCounts = {};
      drugs.forEach(function(d){ var s = d.stage||'Unknown'; stageCounts[s] = (stageCounts[s]||0)+1; });

      var targetCounts = {};
      dtRows.forEach(function(r){ targetCounts[r.target_id] = (targetCounts[r.target_id]||0)+1; });
      var topTargets = Object.entries(targetCounts).sort(function(a,b){return b[1]-a[1];}).slice(0,14);

      /* ── Live counts from Supabase for DB table view ── */
      var SEED_CAT_DATA = [  {
    id:'pipeline',icon:'&#128138;',label:'Pipeline',emoji:'💊',
    tables:[
          {name:'drugs',count:155,desc:'Core drug/asset records; stage, name, company_display, overlap classification'},
          {name:'drug_area_scores',count:212,desc:'Drug membership in each disease area with overlap tier (Direct/Adjacent/etc.)'},
          {name:'drug_targets',count:176,desc:'Drug→molecular target assignments (e.g. drug X hits TL1A)'},
          {name:'drug_indications',count:294,desc:'Drug→indication mappings from ontology migration'},
          {name:'drug_competitive_scores',count:234,desc:'Per-drug competitive pressure scores by area'},
          {name:'drug_validation_results',count:848,desc:'Automated validation check results per drug (stage_match, trial_match, etc.)'}
    ]
  },
  {
    id:'companies',icon:'&#127970;',label:'Companies & Deals',emoji:'🏢',
    tables:[
          {name:'companies',count:114,desc:'Company master records; status=acquired hides from dashboard'},
          {name:'company_areas',count:134,desc:'Company→disease area associations'},
          {name:'deals',count:195,desc:'BD transactions; upfront/total USD, deal type, area_id, drug_id'},
          {name:'ailux_positions',count:2,desc:'Internal Ailux portfolio positions and strategic notes'}
    ]
  },
  {
    id:'ontology',icon:'&#129516;',label:'Ontology',emoji:'🧬',
    tables:[
          {name:'therapeutic_areas',count:8,desc:'Therapeutic area taxonomy (Gastroenterology, Respiratory, Dermatology, etc.)'},
          /* disease_areas removed from catalog — Session 80 code retirement; table DB teardown complete Session 84 */
          {name:'indications',count:38,desc:'Disease/indication ontology nodes (diseases only rule)'},
          {name:'indication_aliases',count:86,desc:'Synonym mappings for indication normalization'},
          {name:'area_metadata',count:11,desc:'Per-area configuration metadata for dashboard rendering'},
          {name:'mechanism_status',count:25,desc:'Mechanism-of-action status tracking per target'}
    ]
  },
  {
    id:'evidence',icon:'&#128300;',label:'Evidence & Intelligence',emoji:'🔬',
    tables:[
          {name:'catalysts',count:794,desc:'Upcoming BD-relevant events, readouts, and catalysts with sort_date'},
          {name:'news_articles',count:55,desc:'Fetched news articles with Meridian AI summaries and drug/area matching'},
          {name:'entity_edges',count:1068,desc:'Graph edges between entities (drug–drug, drug–company, etc.)'},
          {name:'competitive_landscapes',count:5,desc:'Structured competitive landscape assessments per mechanism'},
          {name:'geographic_approvals',count:3,desc:'Drug approval status by geography'},
          {name:'research_queue',count:60,desc:'Enrichment job queue for background research tasks'}
    ]
  },
  {
    id:'trials',icon:'&#129514;',label:'Trials & Validation',emoji:'🧪',
    tables:[
          {name:'trials',count:554,desc:'Clinical trial records linked to drugs; phase, status, endpoints'},
          {name:'trial_registries',count:620,desc:'Raw ClinicalTrials.gov registry sync data'},
          {name:'validation_tests',count:1059,desc:'Automated validation test definitions and results'}
    ]
  },
  {
    id:'platform',icon:'&#9881;',label:'Platform',emoji:'⚙️',
    tables:[
          
    ]
  }];

      /* Fetch live row counts for all tables */
      var SB_URL = (typeof SUPABASE_URL !== 'undefined') ? SUPABASE_URL : 'https://tghntyofptvfhmtchwcv.supabase.co';
      var SB_KEY = (typeof SUPABASE_ANON_KEY !== 'undefined') ? SUPABASE_ANON_KEY : '';
      /* Try to get live counts via _sb metadata or just use seed data */
      var liveCounts = {};
      try {
        var allTables = [];
        SEED_CAT_DATA.forEach(function(cat){ cat.tables.forEach(function(t){ allTables.push(t.name); }); });
        var countFetches = allTables.map(function(tbl){
          return _sb.from(tbl).select('*',{count:'exact',head:true}).then(function(res){
            if (res.count !== null && res.count !== undefined) liveCounts[tbl] = res.count;
          }).catch(function(){});
        });
        await Promise.all(countFetches);
      } catch(e) { /* fall through to seed data */ }

      /* Merge live counts with seed data */
      var CAT_DATA = SEED_CAT_DATA.map(function(cat){
        return Object.assign({}, cat, {
          tables: cat.tables.map(function(t){
            return Object.assign({}, t, {count: liveCounts[t.name] !== undefined ? liveCounts[t.name] : t.count});
          })
        });
      });

      /* Join map for inspector (mirrors OEX_JOIN_MAP) */
      /* Session 80: disease_areas removed from JOIN_MAP fallback — code retirement */
      var JOIN_MAP = OEX_JOIN_MAP || {
  drugs: ['drug_area_scores','drug_targets','drug_indications','drug_competitive_scores','drug_validation_results','trials','catalysts','deals'],
  companies: ['company_areas','deals','ailux_positions','entity_edges','news_articles'],
  drug_area_scores: ['drugs'],
  /* disease_areas removed — Session 80 code retirement */
  drug_targets: ['drugs'],
  drug_indications: ['drugs','indications'],
  trials: ['drugs','trial_registries'],
  catalysts: ['drugs'],
  news_articles: ['companies'],
  company_areas: ['companies'],
  therapeutic_areas: ['indications'],
  indications: ['drug_indications','indication_aliases','therapeutic_areas'],
  indication_aliases: ['indications'],
  entity_edges: ['drugs','companies'],
  mechanism_status: [],
  competitive_landscapes: [],
  geographic_approvals: ['drugs'],
  trial_registries: ['trials'],
  drug_validation_results: ['drugs'],
  research_queue: ['drugs','companies'],
  ailux_positions: ['companies'],
  deals: ['companies','drugs'],
  validation_tests: ['drugs'],
  area_metadata: [],
  drug_competitive_scores: ['drugs']
};

      /* ── Build HTML ── */
      var html = '';

      /* Section 1: Quick View (biological) */
      html += '<div style="padding:6px 12px 4px;font-size:9px;font-weight:800;letter-spacing:2px;color:#2d4a6a;text-transform:uppercase">Quick View</div>';

      /* Build TA children: each TA shows its indications with drug counts */
      var taChildren = taRows.map(function(ta){
        var inds = (taIndMap[ta.id] || []).map(function(ind){
          var drugCount = indDrugMap[ind.id] ? indDrugMap[ind.id].size : 0;
          return {id:ind.id, label:ind.name, count:drugCount, color:ta.color||'#4a6080', sub:[]};
        }).filter(function(c){return c.count>0;})
          .sort(function(a,b){return b.count-a.count;});
        var totalDrugs = new Set();
        inds.forEach(function(i){ if (indDrugMap[i.id]) indDrugMap[i.id].forEach(function(d){totalDrugs.add(d);}); });
        return {id:ta.id, label:ta.name, count:totalDrugs.size, color:ta.color||'#4a6080', children:inds};
      }).filter(function(ta){return ta.count>0;});

      var bioSections = [
        {
          id:'ta', icon:'&#127919;', label:'Therapeutic Areas', cls:'ta', type:'areas',
          count: taChildren.reduce(function(s,t){return s+t.count;},0),
          /* Nested: TA → Indications */
          nested: taChildren,
          children: [], /* not used for nested render */
        },
        {
          id:'tc', icon:'&#128300;', label:'Molecular Targets', cls:'tc', type:'targets',
          count: Object.keys(targetCounts).length,
          children: topTargets.map(function(e){return {id:e[0], label:e[0].toUpperCase(), count:e[1], color:'#10b981', sub:[]};}),
        },
        {
          id:'ds', icon:'&#128138;', label:'Drug Pipeline', cls:'ds', type:'stages',
          count: drugs.length,
          children: STAGE_ORDER.filter(function(s){return stageCounts[s];}).map(function(s){
            return {id:s, label:s, count:stageCounts[s], color:'#f59e0b', sub:[]};
          }),
        },
        {
          id:'cot', icon:'&#127970;', label:'Companies', cls:'cot', type:'companies',
          count: companies.length,
          children: companies.slice(0,22).map(function(c){return {id:c.id, label:c.name, count:null, color:'#637d9a', sub:[]};}),
        },
      ];

      bioSections.forEach(function(sec){
        html += '<div class="oex-tc"><div class="oex-tc-hd" onclick="oexTreeToggle(this)">'
          +'<span class="oex-t-arr">▶</span>'
          +'<span class="oex-t-ico">'+sec.icon+'</span>'
          +'<span class="oex-t-lbl">'+sec.label+'</span>'
          +'<span class="oex-t-cnt">'+sec.count+'</span>'
          +'</div><div class="oex-tv-wrap">';

        if (sec.nested && sec.nested.length) {
          /* Nested TA → Indication render (Therapeutic Areas section) */
          sec.nested.forEach(function(ta){
            var taDot = 'style="background:'+ta.color+'"';
            var taBadge = '<span class="oex-t-cnt">'+ta.count+'</span>';
            html += '<div class="oex-tv" onclick="oexTreeToggleLeaf(this)">'
              +'<span class="oex-tv-dot" '+taDot+'></span>'
              +'<span class="oex-tv-lbl" style="font-weight:700">'+ta.label+'</span>'+taBadge
              +'<span class="oex-tv-sarr">▶</span>'
              +'</div><div class="oex-tsv-wrap">';
            ta.children.forEach(function(ind){
              var chkSpan = '<span class="oex-leaf-chks" onclick="event.stopPropagation()">'
                +'<input type="checkbox" class="oex-node-chk" style="width:12px;height:12px;accent-color:#4ade80;cursor:pointer;flex-shrink:0"></span>';
              html += '<div class="oex-tv" data-type="areas" data-id="'+ind.id+'" data-label="'+ind.label+'" '
                +'onclick="oexSelectNode(\''+ind.label.replace(/'/g,"\\'")+'\')">'
                +'<span class="oex-tsv-dot" style="background:'+ta.color+';margin-left:8px"></span>'
                +'<span class="oex-tv-lbl">'+ind.label+'</span>'
                +'<span class="oex-t-cnt">'+ind.count+'</span>'
                +chkSpan+'</div>';
            });
            html += '</div>';
          });
        } else {
          sec.children.forEach(function(child){
            var cntBadge = child.count!==null ? '<span class="oex-t-cnt">'+child.count+'</span>' : '';
            var dot = child.color ? 'style="background:'+child.color+'"' : '';
            var chkSpan = '<span class="oex-leaf-chks" onclick="event.stopPropagation()">'
              +'<input type="checkbox" class="oex-node-chk" style="width:12px;height:12px;accent-color:#4ade80;cursor:pointer;flex-shrink:0"></span>';
            var nodeId = child.id || child.label;
            var dataAttrs = ' data-type="'+sec.type+'" data-id="'+nodeId+'" data-label="'+child.label+'"';
            if (child.sub && child.sub.length) {
              html += '<div class="oex-tv"'+dataAttrs+' onclick="oexTreeToggleLeaf(this)">'
                +'<span class="oex-tv-dot" '+dot+'></span>'
                +'<span class="oex-tv-lbl">'+child.label+'</span>'+cntBadge
                +'<span class="oex-tv-sarr">▶</span>'
                +chkSpan
                +'</div><div class="oex-tsv-wrap">';
              child.sub.forEach(function(s){
                html += '<div class="oex-tsv">'
                  +'<span class="oex-tsv-dot" style="background:'+s.color+'"></span>'
                  +'<span class="oex-tsv-lbl">'+s.label+'</span></div>';
              });
              html += '</div>';
            } else {
              html += '<div class="oex-tv"'+dataAttrs+' onclick="oexSelectNode(\''+child.label+'\')">'
                +'<span class="oex-tv-dot" '+dot+'></span>'
                +'<span class="oex-tv-lbl">'+child.label+'</span>'+cntBadge
                +chkSpan+'</div>';
            }
          });
        }
        html += '</div></div>';
      });

      /* Section 2: Database Tables */
      html += '<div style="padding:10px 12px 4px;font-size:9px;font-weight:800;letter-spacing:2px;color:#2d4a6a;text-transform:uppercase;border-top:1px solid #1a2e48;margin-top:6px">Database Tables</div>';

      var CAT_COLORS = {
        pipeline:  '#3b82f6',
        companies: '#10b981',
        ontology:  '#8b5cf6',
        evidence:  '#f59e0b',
        trials:    '#06b6d4',
        platform:  '#64748b',
      };

      CAT_DATA.forEach(function(cat){
        if (!cat.tables.length) return;
        var totalRows = cat.tables.reduce(function(s,t){return s+(typeof t.count==='number'?t.count:0);},0);
        var catColor = CAT_COLORS[cat.id] || '#4a6080';
        html += '<div class="oex-tc">'
          +'<div class="oex-tc-hd" onclick="oexTreeToggle(this)">'
          +'<span class="oex-t-arr">▶</span>'
          +'<span class="oex-t-ico" style="font-size:13px">'+cat.icon+'</span>'
          +'<span class="oex-t-lbl" style="color:'+catColor+'">'+cat.label+'</span>'
          +'<span class="oex-t-cnt">'+cat.tables.length+' tables</span>'
          +'</div><div class="oex-tv-wrap">';
        cat.tables.forEach(function(tbl){
          var dispCount = typeof tbl.count === 'number' ? tbl.count.toLocaleString() : '—';
          html += '<div class="oex-tv" data-type="tables" data-id="'+tbl.name+'" data-label="'+tbl.name+'" style="cursor:pointer" onclick="oexInspectTable('+JSON.stringify(tbl.name)+','+tbl.count+','+JSON.stringify(tbl.desc)+','+JSON.stringify(JOIN_MAP[tbl.name]||[])+',\''+cat.id+'\')">'
            +'<span class="oex-tv-dot" style="background:'+catColor+'"></span>'
            +'<span class="oex-tv-lbl" style="font-family:monospace;font-size:10px">'+tbl.name+'</span>'
            +'<span class="oex-t-cnt" id="oex-cnt-'+tbl.name+'" style="background:rgba(0,0,0,.3)">'+dispCount+'</span>'
            +'<span class="oex-leaf-chks" onclick="event.stopPropagation()">'
            +'<input type="checkbox" class="oex-node-chk" style="width:12px;height:12px;accent-color:#4ade80;cursor:pointer;flex-shrink:0"></span>'
            +'</div>';
        });
        html += '</div></div>';
      });

      tree.innerHTML = html;

      /* Wire checkbox change listener once — survives innerHTML replacement since listener is on tree element itself */
      if (!tree.dataset.chkWired) {
        tree.dataset.chkWired = '1';
        tree.addEventListener('change', function(e) {
          var chk = e.target;
          if (!chk || chk.type !== 'checkbox' || !chk.classList.contains('oex-node-chk')) return;
          e.stopPropagation();
          var leaf = chk.closest('[data-type]');
          if (!leaf) return;
          var type = leaf.getAttribute('data-type');
          var id   = leaf.getAttribute('data-id');
          var label= leaf.getAttribute('data-label');
          if (!type || !id) return;
          oexToggleNode(type, id, label, 'both', chk.checked);
        });
      }

      var tsEl = document.getElementById('oex-ts');
      if (tsEl) tsEl.textContent = 'Live · ' + new Date().toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit'});
    }

    window.oexTreeToggle = function(hd) {
      hd.classList.toggle('sel');
      var arr  = hd.querySelector('.oex-t-arr');
      var wrap = hd.nextElementSibling;
      if (arr) arr.classList.toggle('open');
      if (wrap) wrap.classList.toggle('open');
    };
    window.oexTreeToggleLeaf = function(el) {
      el.classList.toggle('sel');
      var arr  = el.querySelector('.oex-tv-sarr');
      var wrap = el.nextElementSibling;
      if (arr) arr.classList.toggle('open');
      if (wrap && wrap.classList.contains('oex-tsv-wrap')) wrap.classList.toggle('open');
    };
    window.oexSelectNode = function(label, cls) {
      if (oexSelectedNodes.has(label)) oexSelectedNodes.delete(label);
      else { oexSelectedNodes.add(label); if (oexSelectedNodes.size>6) oexSelectedNodes.delete(oexSelectedNodes.values().next().value); }
      var container = document.getElementById('oex-sb-nodes');
      if (!container) return;
      if (!oexSelectedNodes.size) { container.innerHTML='<span class="oex-sb-none">None selected — click any node</span>'; return; }
      container.innerHTML = Array.from(oexSelectedNodes).map(function(n){
        return '<span class="oex-sb-chip '+cls+'" onclick="oexSelectNode(\''+n+'\',\''+cls+'\')">'+n+' ×</span>';
      }).join('');
    };

    /* ── Matrix Panel ────────────────────────────────────────────────────── */
    async function oexLoadMatrix() {
      var wrap = document.getElementById('oex-mwrap');
      if (!wrap) return;
      wrap.innerHTML = '<div style="padding:24px;font-size:11px;color:#3a5a7a">Loading…</div>';

      /* Step 1: Get all drug-area memberships — Phase 2 flip (Session 78): drug_competitive_scores */
      var dasRes = await _sb.from('drug_competitive_scores').select('context_id,drug_id,overlap').limit(1500);
      var das = (dasRes.data || []);

      /* Build per-area drug sets; map indication-based uc/cd rows back to 'ibd' key */
      var byArea = {};
      das.forEach(function(r){
        var aId = (r.context_id==='uc'||r.context_id==='cd') ? 'ibd' : r.context_id;
        if (!byArea[aId]) byArea[aId] = new Set();
        byArea[aId].add(r.drug_id);
      });

      var AREA_ORDER = ['tl1a','ibd','atopy','ted','igf1r','fcrn','tcell','respiratory','il4ra','tslp','autoimmune'];
      var visAreas   = AREA_ORDER.filter(function(a){return byArea[a];});

      /* Step 2: Fetch coverage data with correct joins */

      /* Targets: drug_targets has drug_id */
      var targRes = await _sb.from('drug_targets').select('drug_id').limit(1000);
      var withTargets = new Set((targRes.data||[]).map(function(r){return r.drug_id;}));

      /* Indications: drug_indications has drug_id */
      var indicRes = await _sb.from('drug_indications').select('drug_id').limit(1000);
      var withIndic = new Set((indicRes.data||[]).map(function(r){return r.drug_id;}));

      /* Trials: trials table has drug_id AND canonical_drug_id — use both */
      var trialsRes = await _sb.from('trials').select('drug_id,canonical_drug_id').limit(2000);
      var withTrials = new Set();
      (trialsRes.data||[]).forEach(function(r){
        if (r.drug_id) withTrials.add(r.drug_id);
        if (r.canonical_drug_id) withTrials.add(r.canonical_drug_id);
      });

      /* Catalysts: catalysts has drug_id */
      var TODAY = new Date().toISOString().split('T')[0];
      var catsRes = await _sb.from('catalysts').select('drug_id').gte('sort_date',TODAY).limit(1000);
      var withCats = new Set((catsRes.data||[]).map(function(r){return r.drug_id;}).filter(Boolean));

      /* News: use matched_drug_ids directly; also expand matched_area_ids to drug-level
         (most articles only carry area tags, not drug tags — both must be used) */
      var newsRes = await _sb.from('news_articles').select('matched_drug_ids,matched_area_ids').neq('source_validation_status','invalid').limit(500);
      var newsSet = new Set();
      (newsRes.data||[]).forEach(function(r){
        if (Array.isArray(r.matched_drug_ids)) {
          r.matched_drug_ids.forEach(function(id){ if (id) newsSet.add(id); });
        }
        if (Array.isArray(r.matched_area_ids)) {
          r.matched_area_ids.forEach(function(aId){
            if (byArea[aId]) byArea[aId].forEach(function(dId){ newsSet.add(dId); });
          });
        }
      });

      var COLS = [
        {id:'targets',     label:'Targets',     icon:'🔬', set:withTargets,  desc:'Drug→target assignments'},
        {id:'indications', label:'Indications', icon:'🏷', set:withIndic,    desc:'Drug→indication mappings'},
        {id:'trials',      label:'Trials',      icon:'🧪', set:withTrials,   desc:'ClinicalTrials.gov records'},
        {id:'catalysts',   label:'Catalysts',   icon:'📅', set:withCats,     desc:'Upcoming events & readouts'},
        {id:'news',        label:'News',        icon:'📰', set:newsSet,      desc:'News coverage (matched_drug_ids)'},
      ];

      function ccls(p){ return p>=70?'s':p>=40?'p':p>=15?'sp':'m'; }
      function clbl(p){ return p>=70?'Strong':p>=40?'Partial':p>=15?'Sparse':'Gap'; }

      var html = '<table><thead><tr><th class="oex-mcorner"><div class="oex-mcorner-txt">Area × Layer</div></th>';
      COLS.forEach(function(col){
        html += '<th class="oex-ch"><div class="oex-ch-in" title="'+col.desc+'">'
          +'<span style="font-size:14px">'+col.icon+'</span>'
          +'<span class="oex-ch-lbl">'+col.label+'</span>'
          +'</div></th>';
      });
      html += '</tr></thead><tbody>';

      visAreas.forEach(function(aId){
        var meta    = AREA_META[aId]||{label:aId, color:'#4a6080'};
        var drugSet = byArea[aId];
        var total   = drugSet.size;
        if (total === 0) return;
        html += '<tr><th class="oex-rh"><div class="oex-rh-in">'
          +'<span style="width:6px;height:6px;border-radius:50%;background:'+meta.color+';display:inline-block;flex-shrink:0"></span>'
          +'<span class="oex-rh-lbl">'+meta.label+'</span>'
          +'<span style="font-size:9px;color:#3a5a7a;margin-left:auto">'+total+'</span>'
          +'</div></th>';
        COLS.forEach(function(col){
          var covered=0;
          drugSet.forEach(function(did){ if (col.set.has(did)) covered++; });
          var pct = Math.round(covered/total*100);
          var cls = ccls(pct), lbl = clbl(pct);
          html += '<td class="oex-mc"><div class="oex-ci '+cls+'"'
            +' onclick="oexInspectCell(\''+aId+'\',\''+col.id+'\','+covered+','+total+','+pct+')"'
            +' title="'+meta.label+' × '+col.label+': '+covered+'/'+total+' ('+pct+'%)">'
            +'<span class="oex-cpct">'+pct+'%</span>'
            +'<span class="oex-clbl">'+covered+'/'+total+'</span>'
            +'</div></td>';
        });
        html += '</tr>';
      });
      html += '</tbody></table>';
      wrap.innerHTML = html;

      var mlevel = document.getElementById('oex-mat-level');
      if (mlevel) {
        mlevel.innerHTML = '<span style="color:#1e3050">·</span>'
          +'<span class="oex-lb oex-lb2">Live</span>'
          +'<span style="font-size:10px;color:#3a5a7a">'+visAreas.length+' areas × '+COLS.length+' layers · '+das.length+' drug-area scores</span>';
      }
    }

    window.oexInspectCell = function(areaId, colId, covered, total, pct) {
      var insp = document.getElementById('oex-insp');
      if (!insp) return;
      var meta = AREA_META[areaId]||{label:areaId, color:'#4a6080'};
      var colLabels = {targets:'Targets',indications:'Indications',trials:'Trials',catalysts:'Catalysts',news:'News'};
      var colDescs  = {targets:'drug→target assignments',indications:'drug→indication mappings',
                       trials:'ClinicalTrials.gov records',catalysts:'upcoming events & readouts',news:'news coverage'};
      var lbl = colLabels[colId]||colId;
      var desc= colDescs[colId]||'';
      var gap = total-covered;
      function ccls(p){ return p>=70?'s':p>=40?'p':p>=15?'sp':'m'; }
      function clbl2(p){ return p>=70?'Strong':p>=40?'Partial':p>=15?'Sparse':'Gap'; }
      function fcls(c){ return c==='s'?'strong':c==='p'?'partial':c==='sp'?'sparse':'missing'; }
      var cls = ccls(pct);
      insp.innerHTML = '<div class="oex-is">'
        +'<div class="oex-is-t">Cell Inspector</div>'
        +'<div class="oex-it">'+meta.label+' <span style="color:#3a5a7a">×</span> '+lbl+'</div>'
        +'<div class="oex-is-d">'+desc+'</div>'
        +'<span class="oex-sbadge '+cls+'">'+clbl2(pct)+' — '+pct+'%</span>'
        +'<div class="oex-cov-row">'
        +'<span style="font-size:10px;color:#637d9a;min-width:60px">Coverage</span>'
        +'<div class="oex-cov-bg"><div class="oex-cov-fill f-'+cls+'" style="width:'+pct+'%"></div></div>'
        +'<span class="oex-cov-pct" style="color:var(--oex-'+fcls(cls)+')">'+pct+'%</span>'
        +'</div></div>'
        +'<div class="oex-is"><div class="oex-is-t">Counts</div>'
        +'<div class="oex-i-note">'
        +'<strong style="color:#c8d8ec">'+covered+'</strong> of <strong style="color:#c8d8ec">'+total+'</strong> drugs in '+meta.label+' have '+lbl+' data'
        +(gap>0 ? '<br><span style="color:#f97316">'+gap+' drug'+(gap===1?'':'s')+' missing '+lbl+' coverage</span>'
                : '<br><span style="color:#10b981">✓ Full coverage</span>')
        +'</div></div>';
    };


    /* ── Table Inspector ────────────────────────────────────────────────── */
    window.oexInspectTable = async function(tableName, rowCount, desc, joins, catId) {
      var insp = document.getElementById('oex-insp');
      if (!insp) return;
      var CAT_COLORS = {
        pipeline:  '#3b82f6', companies:'#10b981', ontology:'#8b5cf6',
        evidence:  '#f59e0b', trials:   '#06b6d4', platform:'#64748b',
      };
      var catColor = CAT_COLORS[catId] || '#4a6080';
      var joinsHtml = (joins && joins.length)
        ? joins.map(function(j){return '<span style="background:rgba(255,255,255,.06);color:#93c5fd;padding:1px 5px;border-radius:3px;font-size:10px;font-family:monospace">'+j+'</span>';}).join(' ')
        : '<span style="color:#3a5a7a;font-size:10px">none mapped</span>';
      insp.innerHTML = '<div class="oex-is">'
        +'<div class="oex-is-t">Table Inspector</div>'
        +'<div class="oex-it" style="font-family:monospace;font-size:14px;color:'+catColor+'">'+tableName+'</div>'
        +'<div class="oex-is-d">'+desc+'</div>'
        +'<span class="oex-sbadge s" style="font-family:monospace" id="oex-insp-count">'+rowCount.toLocaleString()+' rows</span>'
        +'</div>'
        +'<div class="oex-is"><div class="oex-is-t">Joins To</div>'
        +'<div style="display:flex;flex-wrap:wrap;gap:4px;padding:6px 0">'+joinsHtml+'</div>'
        +'</div>'
        +'<div class="oex-is"><div class="oex-is-t">Sample Rows</div>'
        +'<div id="oex-sample-wrap" style="font-size:10px;color:#3a5a7a;padding:4px 0">Loading sample…</div>'
        +'<button onclick="window.oexLoadSample(\''+tableName+'\')" style="margin-top:6px;padding:4px 10px;font-size:10px;background:#1a2e48;border:1px solid #2d4a6a;border-radius:4px;color:#93c5fd;cursor:pointer">↻ Refresh sample</button>'
        +'</div>';
      /* Load sample automatically */
      window.oexLoadSample(tableName);
    };

    window.oexLoadSample = async function(tableName) {
      var wrap = document.getElementById('oex-sample-wrap');
      if (!wrap) return;
      wrap.textContent = 'Fetching…';
      try {
        var res = await _sb.from(tableName).select('*').limit(3);
        var rows = res.data || [];
        if (!rows.length) { wrap.textContent = '(no rows)'; return; }
        var keys = Object.keys(rows[0]).slice(0, 6); /* max 6 cols to avoid overflow */
        var tbl = '<div style="overflow-x:auto"><table style="font-size:9px;border-collapse:collapse;width:100%">'
          +'<thead><tr>'+keys.map(function(k){return '<th style="padding:2px 6px;border-bottom:1px solid #1e3a5f;color:#4a90c4;text-align:left;font-family:monospace;white-space:nowrap">'+k+'</th>';}).join('')+'</tr></thead>'
          +'<tbody>';
        rows.forEach(function(row){
          tbl += '<tr>'+keys.map(function(k){
            var v = row[k];
            if (v === null || v === undefined) v = '—';
            else if (typeof v === 'object') v = JSON.stringify(v).slice(0,40);
            else v = String(v).slice(0,40);
            return '<td style="padding:2px 6px;border-bottom:1px solid #0f1d2e;color:#8ba8c8;font-family:monospace;white-space:nowrap">'+v+'</td>';
          }).join('')+'</tr>';
        });
        tbl += '</tbody></table></div>';
        wrap.innerHTML = tbl;
      } catch(e) {
        wrap.textContent = 'Error: ' + (e.message||e);
      }
    };

    /* ── Competitive Pressure Map (canvas) ───────────────────────────────── */
    async function oexInitMap() {
      var canvas = document.getElementById('oex-cpm-canvas');
      if (!canvas) return;

      var results = await Promise.all([
        _sb.from('drug_area_scores').select('drug_id,area_id,overlap').limit(1500),
        _sb.from('drugs').select('id,name,stage,company_display').limit(500),
        _sb.from('catalysts').select('drug_id').gte('sort_date',TODAY).limit(500),
      ]);
      var das   = (results[0].data||[]);
      var drugs = (results[1].data||[]);
      var cats  = (results[2].data||[]);

      var drugById = {};
      drugs.forEach(function(d){ drugById[d.id]=d; });
      var withCat = new Set(cats.map(function(c){return c.drug_id;}).filter(Boolean));

      var MAP_AREAS = ['tl1a','ibd','atopy','ted','igf1r','fcrn','tcell','respiratory'];

      function stageToCol(stage) {
        if (!stage) return 0;
        var s = stage.toLowerCase();
        if (s.indexOf('approved')>=0)                      return 4;
        if (s.indexOf('bla')>=0||s.indexOf('filed')>=0)   return 3.7;
        if (s.indexOf('phase 3')>=0||s.indexOf('2/3')>=0) return 3;
        if (s.indexOf('phase 2')>=0||s.indexOf('1/2')>=0) return 2;
        if (s.indexOf('phase 1')>=0)                       return 1;
        return 0;
      }

      var areaRows = {};
      das.forEach(function(r){
        var drug = drugById[r.drug_id];
        if (!drug) return;
        if (MAP_AREAS.indexOf(r.area_id)<0) return;
        if (!areaRows[r.area_id]) areaRows[r.area_id]=[];
        areaRows[r.area_id].push({
          drug:    drug,
          overlap: r.overlap,
          hasCat:  withCat.has(r.drug_id),
          sx:      stageToCol(drug.stage),
        });
      });

      /* Visual config */
      var LEFT_MARGIN = 150;
      var RIGHT_PAD   = 20;
      var TOP_PAD     = 52;
      var BOTTOM_PAD  = 32;
      var ROW_HEIGHT  = 72;

      var STAGE_LABELS = ['Preclinical','Phase 1','Phase 2','Phase 3','Approved'];

      var TIER_CFG = {
        'Direct':    {r:11, fill:'#ef4444', glow:18,  glowColor:'#ef4444'},
        'Watch':     {r:9,  fill:'#f59e0b', glow:10,  glowColor:'#f59e0b'},
        'Adjacent':  {r:7,  fill:'#60a5fa', glow:0,   glowColor:'transparent'},
        'Same-Space':{r:5,  fill:'#6b7280', glow:0,   glowColor:'transparent'},
      };

      var DPR = window.devicePixelRatio||1;
      var hoveredDot = null;

      function getTooltip() {
        var tt = document.getElementById('oex-cpm-tt');
        if (!tt) {
          tt = document.createElement('div');
          tt.id = 'oex-cpm-tt';
          tt.style.cssText = 'position:fixed;display:none;z-index:9999;background:#1a2840;border:1px solid #2d4060;border-radius:6px;padding:8px 10px;font-size:11px;color:#c8d8ec;pointer-events:none;max-width:220px;box-shadow:0 4px 16px rgba(0,0,0,.6);font-family:Inter,system-ui,sans-serif;line-height:1.5';
          document.body.appendChild(tt);
        }
        return tt;
      }

      function buildCanvas(wCss) {
        var visAreas = MAP_AREAS.filter(function(a){return areaRows[a];});
        var numAreas = visAreas.length;

        var H_CSS = TOP_PAD + (numAreas * ROW_HEIGHT) + BOTTOM_PAD;
        var colW  = (wCss - LEFT_MARGIN - RIGHT_PAD) / 5;

        canvas.width  = Math.round(wCss * DPR);
        canvas.height = Math.round(H_CSS * DPR);
        canvas.style.height = H_CSS + 'px';

        var ctx = canvas.getContext('2d');
        ctx.scale(DPR, DPR);

        /* Pre-compute max Direct count for pressure bar scaling */
        var maxDirect = 0;
        visAreas.forEach(function(aId){
          var dct = (areaRows[aId]||[]).filter(function(r){return r.overlap==='Direct';}).length;
          if (dct > maxDirect) maxDirect = dct;
        });

        var dots = [];

        function draw() {
          ctx.clearRect(0, 0, wCss, H_CSS);
          ctx.fillStyle = '#060d14';
          ctx.fillRect(0, 0, wCss, H_CSS);

          /* Pre-compute fixed dot column — all dots share same X */
          ctx.font = '600 12px Inter,system-ui,sans-serif';
          var maxLW = 0;
          visAreas.forEach(function(aId){
            var m = AREA_META[aId];
            if (m) { var lw = ctx.measureText(m.label).width; if (lw > maxLW) maxLW = lw; }
          });
          var DOT_X = LEFT_MARGIN - 14 - maxLW - 14;

          /* ── Column divider lines (subtle dotted) */
          ctx.save();
          ctx.setLineDash([2, 4]);
          ctx.strokeStyle = 'rgba(255,255,255,0.06)';
          ctx.lineWidth = 1;
          for (var ci = 1; ci < 5; ci++) {
            var vx = LEFT_MARGIN + ci * colW;
            ctx.beginPath(); ctx.moveTo(vx, TOP_PAD - 16); ctx.lineTo(vx, H_CSS - BOTTOM_PAD + 8); ctx.stroke();
          }
          ctx.setLineDash([]);
          ctx.restore();

          /* ── Stage header labels */
          ctx.save();
          ctx.textAlign = 'center';
          ctx.font = '700 9px Inter,system-ui,sans-serif';
          ctx.fillStyle = '#4b6280';
          ctx.letterSpacing = '0.1em';
          STAGE_LABELS.forEach(function(lbl, ci){
            var hx = LEFT_MARGIN + ci * colW + colW / 2;
            ctx.fillText(lbl.toUpperCase(), hx, TOP_PAD - 16);
          });
          ctx.restore();

          /* ── Top separator under stage headers */
          ctx.save();
          ctx.strokeStyle = 'rgba(30,48,80,0.6)';
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(LEFT_MARGIN, TOP_PAD - 6);
          ctx.lineTo(wCss - RIGHT_PAD, TOP_PAD - 6);
          ctx.stroke();
          ctx.restore();

          /* ── Per-row: shading + labels + dots */
          dots = [];

          visAreas.forEach(function(aId, ri){
            var rows    = areaRows[aId] || [];
            var meta    = AREA_META[aId] || {label:aId, color:'#4a6080'};
            var rowY    = TOP_PAD + ri * ROW_HEIGHT;
            var rowMidY = rowY + ROW_HEIGHT / 2;

            var directCt = rows.filter(function(r){return r.overlap==='Direct';}).length;
            var watchCt  = rows.filter(function(r){return r.overlap==='Watch';}).length;
            var hotScore = directCt + watchCt;

            /* Row pressure background shading */
            ctx.save();
            if (hotScore > 8) {
              ctx.fillStyle = 'rgba(239,68,68,0.06)';
            } else if (hotScore >= 4) {
              ctx.fillStyle = 'rgba(245,158,11,0.04)';
            } else {
              ctx.fillStyle = 'transparent';
            }
            ctx.fillRect(LEFT_MARGIN, rowY, wCss - LEFT_MARGIN - RIGHT_PAD, ROW_HEIGHT);
            ctx.restore();

            /* Left accent bar (4px, full row height, area color) */
            ctx.save();
            ctx.fillStyle = meta.color;
            ctx.globalAlpha = 0.55;
            ctx.fillRect(LEFT_MARGIN, rowY, 4, ROW_HEIGHT);
            ctx.restore();

            /* Area label — right-aligned into left margin */
            ctx.save();
            ctx.textAlign  = 'right';
            ctx.font       = '600 12px Inter,system-ui,sans-serif';
            ctx.fillStyle  = meta.color;
            ctx.fillText(meta.label, LEFT_MARGIN - 14, rowMidY + 1);
            ctx.restore();

            /* Type subtext beneath label */
            if (meta.type) {
              ctx.save();
              ctx.textAlign = 'right';
              ctx.font = '500 8px Inter,system-ui,sans-serif';
              ctx.fillStyle = '#3a5a7a';
              ctx.fillText(meta.type, LEFT_MARGIN - 14, rowMidY + 13);
              ctx.restore();
            }

            /* Small bullet circle before label — all dots at fixed DOT_X column */
            ctx.save();
            ctx.beginPath();
            ctx.arc(DOT_X, rowMidY + 1, 3.5, 0, Math.PI*2);
            ctx.fillStyle = meta.color;
            ctx.globalAlpha = 0.85;
            ctx.fill();
            ctx.restore();

            /* Row separator */
            if (ri > 0) {
              ctx.save();
              ctx.strokeStyle = 'rgba(255,255,255,0.07)';
              ctx.lineWidth = 1;
              ctx.beginPath();
              ctx.moveTo(LEFT_MARGIN, rowY);
              ctx.lineTo(wCss - RIGHT_PAD, rowY);
              ctx.stroke();
              ctx.restore();
            }

            /* Right-side pressure bar */
            if (maxDirect > 0) {
              var barH     = ROW_HEIGHT * 0.6;
              var barFillH = (directCt / maxDirect) * barH;
              var barX     = wCss - RIGHT_PAD + 4;
              var barY     = rowMidY - barH / 2;
              ctx.save();
              ctx.fillStyle = 'rgba(30,48,80,0.5)';
              ctx.fillRect(barX, barY, 4, barH);
              if (barFillH > 0) {
                ctx.fillStyle = directCt > 0 ? '#ef4444' : '#2d4060';
                ctx.globalAlpha = 0.8;
                ctx.fillRect(barX, barY + barH - barFillH, 4, barFillH);
              }
              ctx.restore();
            }

            /* ── Dots ── */
            var buckets = {};
            rows.forEach(function(r){
              var k = r.sx;
              if (!buckets[k]) buckets[k] = [];
              buckets[k].push(r);
            });

            Object.keys(buckets).forEach(function(sx){
              var items  = buckets[sx];
              var cx     = LEFT_MARGIN + parseFloat(sx) * colW + colW / 2;
              var cfg0   = TIER_CFG['Direct'];
              /* max dot radius across items in this bucket for spacing */
              var maxR   = cfg0.r;
              var spacing = maxR * 2 + 4;
              var dpr2   = Math.max(1, Math.floor((colW - maxR*2 - 8) / spacing));

              items.forEach(function(item, i){
                var cfg     = TIER_CFG[item.overlap] || TIER_CFG['Same-Space'];
                var dotR    = cfg.r;
                var col     = i % dpr2;
                var row2    = Math.floor(i / dpr2);
                var totalCols = Math.min(items.length, dpr2);
                var totalRows = Math.ceil(items.length / dpr2);
                var gridW   = (totalCols - 1) * spacing;
                var gridH   = (totalRows - 1) * spacing;
                var dx      = cx - gridW / 2 + col * spacing;
                var dy      = rowMidY - gridH / 2 + row2 * spacing;
                var isHov   = (hoveredDot && hoveredDot.drug.id===item.drug.id && hoveredDot.area===aId);

                ctx.save();

                /* Glow for Direct / Watch */
                if (cfg.glow > 0) {
                  ctx.shadowBlur  = isHov ? cfg.glow * 1.4 : cfg.glow;
                  ctx.shadowColor = cfg.glowColor;
                } else {
                  ctx.shadowBlur  = 0;
                  ctx.shadowColor = 'transparent';
                }

                /* Dot fill */
                ctx.beginPath();
                ctx.arc(dx, dy, dotR + (isHov ? 2 : 0), 0, Math.PI*2);
                ctx.fillStyle = isHov ? cfg.fill : cfg.fill + 'cc';
                ctx.fill();

                ctx.shadowBlur  = 0;
                ctx.shadowColor = 'transparent';

                /* Catalyst ring — bright gold halo */
                if (item.hasCat) {
                  ctx.beginPath();
                  ctx.arc(dx, dy, dotR + 5 + (isHov ? 2 : 0), 0, Math.PI*2);
                  ctx.strokeStyle = '#fde68a';
                  ctx.lineWidth   = 2.5;
                  ctx.globalAlpha = isHov ? 1 : 0.85;
                  ctx.stroke();
                }

                ctx.restore();

                dots.push({
                  dx: dx, dy: dy,
                  r:  dotR + 6,
                  drug:    item.drug,
                  overlap: item.overlap,
                  hasCat:  item.hasCat,
                  area:    aId,
                });
              });
            });
          });

          /* ── Timestamp */
          ctx.save();
          ctx.textAlign  = 'right';
          ctx.font       = '400 8px Inter,system-ui,sans-serif';
          ctx.fillStyle  = 'rgba(30,48,80,0.9)';
          ctx.fillText(
            'Live · ' + new Date().toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit'}),
            wCss - RIGHT_PAD - 8,
            H_CSS - 8
          );
          ctx.restore();
        } /* end draw() */

        draw();
        canvas._draw = draw;
        canvas._dots = dots;
        return ctx;
      } /* end buildCanvas() */

      /* ── Tooltip hover */
      canvas.addEventListener('mousemove', function(e){
        var rect = canvas.getBoundingClientRect();
        var mx   = e.clientX - rect.left;
        var my   = e.clientY - rect.top;
        var found = null;
        var dotsArr = canvas._dots || [];
        for (var i = 0; i < dotsArr.length; i++) {
          var d = dotsArr[i];
          var dist = Math.sqrt((d.dx-mx)*(d.dx-mx) + (d.dy-my)*(d.dy-my));
          if (dist <= d.r + 1) { found = d; break; }
        }
        hoveredDot = found;
        if (canvas._draw) { canvas._draw(); canvas._dots = canvas._dots || []; }

        var tt = getTooltip();
        if (found) {
          var meta    = AREA_META[found.area] || {label:found.area};
          var cfg     = TIER_CFG[found.overlap] || {fill:'#637d9a'};
          var color   = cfg.fill;
          var bg      = OVERLAP_BG[found.overlap] || 'rgba(99,125,154,.1)';
          tt.innerHTML =
            '<div style="font-weight:700;color:#e8f0fa;margin-bottom:3px">' + (found.drug.name||found.drug.id) + '</div>'
            + '<div style="color:#637d9a;font-size:10px;margin-bottom:5px">' + (found.drug.company_display||'') + '</div>'
            + '<div style="display:flex;gap:5px;flex-wrap:wrap;align-items:center">'
            + '<span style="background:rgba(59,130,246,.15);color:#93c5fd;padding:2px 6px;border-radius:3px;font-size:10px;font-weight:600">' + (found.drug.stage||'?') + '</span>'
            + '<span style="background:' + bg + ';color:' + color + ';padding:2px 6px;border-radius:3px;font-size:10px;font-weight:700;border:1px solid ' + color + '40">' + (found.overlap||'?') + '</span>'
            + '<span style="color:#4b6280;font-size:10px">' + meta.label + '</span>'
            + (found.hasCat ? '<span style="color:#fde68a;font-size:10px;font-weight:700">⚡ catalyst</span>' : '')
            + '</div>';
          tt.style.display = 'block';
          tt.style.left    = (e.clientX + 16) + 'px';
          tt.style.top     = (e.clientY - 12) + 'px';
          canvas.style.cursor = 'pointer';
        } else {
          tt.style.display    = 'none';
          canvas.style.cursor = 'default';
        }
      });

      canvas.addEventListener('mouseleave', function(){
        hoveredDot = null;
        if (canvas._draw) canvas._draw();
        var tt = document.getElementById('oex-cpm-tt');
        if (tt) tt.style.display = 'none';
      });

      /* ── Init via ResizeObserver — saved to canvas._cpmRO to prevent GC */
      if (canvas._cpmRO) { canvas._cpmRO.disconnect(); }
      canvas._cpmRO = new ResizeObserver(function(entries){
        var w = entries[0].contentRect.width;
        if (w < 100) return;
        buildCanvas(w);
      });
      canvas._cpmRO.observe(canvas);
      /* Fallback: if parent already has width, render immediately */
      var pw = canvas.parentElement ? canvas.parentElement.offsetWidth : 0;
      if (pw > 100) buildCanvas(pw);
      else setTimeout(function(){
        var w2 = canvas.parentElement ? canvas.parentElement.offsetWidth : 0;
        if (w2 > 100) buildCanvas(w2);
      }, 150);
    }



    /* ══════════════════════════════════════════════════════════════════════
       DYNAMIC MATRIX SYSTEM — Session 73
       Checkboxes (R/C), quartile row-hiding, table nodes, event-delegation
       multi-cell inspector, CPM dot gap already in base
    ══════════════════════════════════════════════════════════════════════ */

    /* ── State ─────────────────────────────────────────────────────────── */
    var OEX_CAT = null;
    var OEX_LABEL_MAP = {};
    var OEX_MS = { rows:[], cols:[], ceiling:100, sort:'desc', cache:{} };
    var OEX_SEL = [];
    var OEX_TREE_INJECTED = false;

    /* Section header label → catalog type */
    var OEX_SECTION_MAP = {
      'Disease Areas':'areas', 'Molecular Targets':'targets',
      'Drug Pipeline':'stages', 'Companies':'companies'
    };

    /* All Supabase table names (for table-node matrix) */
    var OEX_ALL_TABLES = [
      'drugs','drug_area_scores','drug_targets','drug_indications',
      'drug_competitive_scores','drug_validation_results',
      'companies','company_areas','deals','ailux_positions',
      /* disease_areas removed — Session 80 code retirement: table pending FK teardown */
      'therapeutic_areas','indications','indication_aliases',
      'area_metadata','mechanism_status',
      'catalysts','news_articles','entity_edges','competitive_landscapes',
      'geographic_approvals','research_queue',
      'trials','trial_registries','validation_tests'
    ];

    /* FK relationship map: table → array of tables it links to via a shared key.
       Session 80: disease_areas removed — code retirement complete; table DB teardown complete Session 84.
       New hierarchy: therapeutic_areas → indications */
    var OEX_JOIN_MAP = {
      drugs:['drug_area_scores','drug_targets','drug_indications','drug_competitive_scores',
             'drug_validation_results','trials','catalysts','deals','entity_edges',
             'geographic_approvals','research_queue','validation_tests'],
      companies:['company_areas','deals','ailux_positions','entity_edges','news_articles','research_queue'],
      drug_area_scores:['drugs'],
      /* disease_areas removed — Session 80 code retirement */
      drug_targets:['drugs'],
      drug_indications:['drugs','indications'],
      trials:['drugs','trial_registries'],
      catalysts:['drugs'],
      news_articles:['companies'],
      company_areas:['companies'],
      therapeutic_areas:['indications'],
      indications:['drug_indications','indication_aliases','therapeutic_areas'],
      indication_aliases:['indications'],
      entity_edges:['drugs','companies'],
      mechanism_status:[],  /* was ['disease_areas'] — FK pending DB teardown */
      competitive_landscapes:[],  /* was ['disease_areas'] — FK pending DB teardown */
      geographic_approvals:['drugs'],
      trial_registries:['trials'],
      drug_validation_results:['drugs'],
      research_queue:['drugs','companies'],
      ailux_positions:['companies'],
      deals:['companies','drugs'],
      validation_tests:['drugs'],
      area_metadata:[],  /* was ['disease_areas'] — FK pending DB teardown */
      drug_competitive_scores:['drugs']
    };

    /* Context-aware FK map: OEX_FK_MAP[childTable][parentTable] = fkColumn
       The FK column lives in childTable and references parentTable.id
       Used by _oexTableStrength to find the right FK depending on which
       table is the parent vs child in a given row×col pair.           */
    /* Session 80: removed disease_areas:'area_id' FK entries from all tables.
       area_metadata/mechanism_status/competitive_landscapes still reference disease_areas
       via DB constraints — those will be dropped in the DB FK teardown session. */
    var OEX_FK_MAP = {
      drug_area_scores:        {drugs:'drug_id'},
      drug_targets:            {drugs:'drug_id'},
      drug_indications:        {drugs:'drug_id',      indications:'indication_id'},
      drug_competitive_scores: {drugs:'drug_id'},
      drug_validation_results: {drugs:'drug_id'},
      trials:                  {drugs:'drug_id'},
      catalysts:               {drugs:'drug_id'},
      deals:                   {companies:'company_id', drugs:'drug_id'},
      company_areas:           {companies:'company_id'},
      entity_edges:            {drugs:'drug_id',      companies:'company_id'},
      geographic_approvals:    {drugs:'drug_id'},
      research_queue:          {drugs:'drug_id',      companies:'company_id'},
      trial_registries:        {trials:'drug_id'},
      validation_tests:        {drugs:'drug_id'},
      area_metadata:           {},  /* area_id FK to disease_areas — pending DB teardown */
      mechanism_status:        {},  /* area_id FK to disease_areas — pending DB teardown */
      competitive_landscapes:  {},  /* area_id FK to disease_areas — pending DB teardown */
      indication_aliases:      {indications:'indication_id'},
      ailux_positions:         {companies:'company_id'},
      news_articles:           {companies:'company_id'}
    };

    /* ── Catalog initializer ─────────────────────────────────────────── */
    async function oexInitCatalog() {
      if (OEX_CAT) return;
      /* Use new ontology: indications (not disease_areas) */
      var indRes  = await _sb.from('indications').select('id,name').order('name').limit(100);
      var coRes   = await _sb.from('companies').select('id,name').neq('status','acquired').order('name').limit(150);
      var tgtRes  = await _sb.from('drug_targets').select('target_id').limit(2000);

      var tgtCount = {};
      (tgtRes.data||[]).forEach(function(r){
        if (r.target_id) tgtCount[r.target_id]=(tgtCount[r.target_id]||0)+1;
      });
      var topTgts = Object.keys(tgtCount)
        .sort(function(a,b){return tgtCount[b]-tgtCount[a];})
        .slice(0,40).map(function(t){return {id:t,label:t};});

      OEX_CAT = {
        areas:{
          label:'Indications', icon:'\u{1F9EC}',
          items:(indRes.data||[]).map(function(a){return {id:a.id,label:a.name||a.id};})
        },
        layers:{
          label:'Data Layers', icon:'\u{1F4CA}',
          items:[
            {id:'targets',label:'Targets'},{id:'indications',label:'Indications'},
            {id:'trials',label:'Trials'},{id:'catalysts',label:'Catalysts'},{id:'news',label:'News'}
          ]
        },
        stages:{
          label:'Dev Stages', icon:'\u{1F52C}',
          items:[
            {id:'Preclinical',label:'Preclinical'},{id:'Phase 1',label:'Phase 1'},
            {id:'Phase 2',label:'Phase 2'},{id:'Phase 3',label:'Phase 3'},{id:'Approved',label:'Approved'}
          ]
        },
        companies:{
          label:'Companies', icon:'\u{1F3E2}',
          items:(coRes.data||[]).map(function(c){return {id:c.id,label:c.name||c.id};})
        },
        targets:{
          label:'Molecular Targets', icon:'\u{1F3AF}',
          items:topTgts
        },
        tables:{
          label:'Database Tables', icon:'\u{1F5C4}',
          items:OEX_ALL_TABLES.map(function(t){return {id:t,label:t};})
        }
      };

      OEX_LABEL_MAP = {};
      Object.keys(OEX_CAT).forEach(function(type){
        OEX_CAT[type].items.forEach(function(item){
          OEX_LABEL_MAP[item.label.toLowerCase()]={type:type,id:item.id,label:item.label};
          OEX_LABEL_MAP[item.id.toLowerCase()]   ={type:type,id:item.id,label:item.label};
        });
      });
    }

    /* ── Inject checkboxes into Quick View tree + DB Tables ─────────── */
    function oexInjectTreeButtons() {
      /* Checkboxes now embedded in oexLoadTree at render time — just refresh states */
      oexRefreshChks();
      return;
      var tree = document.getElementById('oex-tree');
      if (!tree || !OEX_CAT) return;

      var allSections = Array.prototype.slice.call(tree.querySelectorAll('.oex-tc'));
      allSections.forEach(function(sec) {
        var hd = sec.querySelector('.oex-tc-hd');
        if (!hd) return;
        var sectionLabel = (hd.querySelector('.oex-t-lbl')||{}).textContent||'';
        var catType = OEX_SECTION_MAP[sectionLabel];
        if (!catType) {
          // Check if it's a Database Tables section — inject table checkboxes
          if (sectionLabel && !hd.hasAttribute('data-oex-wired')) {
            _oexInjectDbTableCheckboxes(sec, sectionLabel);
          }
          return;
        }

        /* Quick View section: inject "All R" / "All C" on header */
        if (!hd.hasAttribute('data-oex-wired')) {
          hd.setAttribute('data-oex-wired','1');
          var g = document.createElement('span');
          g.style.cssText='display:inline-flex;gap:4px;margin-left:6px;flex-shrink:0;vertical-align:middle';
          g.innerHTML=
            '<label style="font-size:9px;color:#4ade80;cursor:pointer;display:flex;align-items:center;gap:3px" title="Select all in this group">'
            +'<input type="checkbox" class="oex-grp-chk" data-type="'+catType+'" style="width:11px;height:11px;accent-color:#4ade80;cursor:pointer"> All</label>';
          hd.appendChild(g);
        }

        /* Individual leaf items */
        var leaves = Array.prototype.slice.call(sec.querySelectorAll('.oex-tv'));
        leaves.forEach(function(leaf){
          if (leaf.hasAttribute('data-oex-wired')) return;
          leaf.setAttribute('data-oex-wired','1');
          var lblEl = leaf.querySelector('.oex-tv-lbl');
          var rawLabel = lblEl ? lblEl.textContent.trim() : '';
          var node = OEX_LABEL_MAP[rawLabel.toLowerCase()] || {type:catType,id:rawLabel,label:rawLabel};
          leaf.setAttribute('data-type',node.type);
          leaf.setAttribute('data-id',  node.id);
          leaf.setAttribute('data-label',node.label);
          var chks = document.createElement('span');
          chks.className='oex-leaf-chks';
          chks.style.cssText='display:inline-flex;gap:4px;margin-left:auto;flex-shrink:0;padding-right:4px;align-items:center';
          chks.innerHTML=_oexChkHtml(node.type,node.id,node.label);
          chks.addEventListener('click',function(e){e.stopPropagation();});
          leaf.style.display='flex'; leaf.style.alignItems='center';
          leaf.appendChild(chks);
          leaf.setAttribute('onclick','');
        });
      });

      /* Wire one delegated listener on the tree */
      if (!OEX_TREE_INJECTED) {
        OEX_TREE_INJECTED=true;
        tree.addEventListener('change',function(e){
          var chk=e.target;
          if (!chk || chk.type!=='checkbox') return;
          e.stopPropagation();
          if (chk.classList.contains('oex-grp-chk')) {
            var type=chk.getAttribute('data-type');
            _oexSetGroupAll(type,chk.checked);
          } else if (chk.classList.contains('oex-node-chk')) {
            var leaf=chk.closest('[data-type]');
            if (!leaf) return;
            var type=leaf.getAttribute('data-type');
            var id=leaf.getAttribute('data-id');
            var label=leaf.getAttribute('data-label');
            oexToggleNode(type,id,label,'both',chk.checked);
          }
        });
      }
      oexRefreshChks();
    }

    /* ── Inject checkboxes into database table items ──────────────────── */
    function _oexInjectDbTableCheckboxes(sec, sectionLabel) {
      var hd = sec.querySelector('.oex-tc-hd');
      if (!hd) return;
      hd.setAttribute('data-oex-wired','1');

      var leaves = Array.prototype.slice.call(sec.querySelectorAll('.oex-tv'));
      leaves.forEach(function(leaf){
        if (leaf.hasAttribute('data-oex-wired')) return;
        leaf.setAttribute('data-oex-wired','1');
        var lblEl = leaf.querySelector('.oex-tv-lbl');
        var tblName = lblEl ? lblEl.textContent.trim() : '';
        // Only add checkboxes if this is a known table
        if (OEX_ALL_TABLES.indexOf(tblName) < 0) return;
        leaf.setAttribute('data-type','tables');
        leaf.setAttribute('data-id', tblName);
        leaf.setAttribute('data-label', tblName);
        var chks = document.createElement('span');
        chks.className='oex-leaf-chks';
        chks.style.cssText='display:inline-flex;gap:4px;margin-left:auto;flex-shrink:0;padding-right:4px;align-items:center';
        chks.innerHTML=_oexChkHtml('tables',tblName,tblName);
        chks.addEventListener('click',function(e){e.stopPropagation();});
        leaf.style.display='flex'; leaf.style.alignItems='center';
        leaf.appendChild(chks);
        leaf.setAttribute('onclick','');
      });
    }

    /* ── Checkbox HTML — single checkbox adds node to BOTH row and col axes ── */
    function _oexChkHtml(type,id,label) {
      var active=OEX_MS.rows.some(function(n){return n.id===id&&n.type===type;});
      var safe=(label||'').replace(/"/g,'&quot;');
      return '<label style="cursor:pointer;display:flex;align-items:center" title="Include in matrix">'
        +'<input type="checkbox" class="oex-node-chk" '+(active?'checked':'')+' style="width:12px;height:12px;accent-color:#4ade80;cursor:pointer"></label>';
    }

    /* ── Refresh all checkbox states ────────────────────────────────── */
    function oexRefreshChks() {
      /* Directly update .checked on embedded oex-node-chk inputs */
      var tree=document.getElementById('oex-tree');
      if (!tree) return;
      tree.querySelectorAll('.oex-node-chk').forEach(function(chk){
        var leaf=chk.closest('[data-type]');
        if (!leaf) return;
        var type=leaf.getAttribute('data-type');
        var id  =leaf.getAttribute('data-id');
        if (!type||!id) return;
        chk.checked=OEX_MS.rows.some(function(n){return n.id===id&&n.type===type;});
      });
    }

    /* ── Set all items in group checked/unchecked — always both axes ── */
    function _oexSetGroupAll(type,checked) {
      if (!OEX_CAT||!OEX_CAT[type]) return;
      var catItems=OEX_CAT[type].items;
      if (checked) {
        catItems.forEach(function(item){
          if (!OEX_MS.rows.some(function(n){return n.id===item.id&&n.type===type;}))
            OEX_MS.rows.push({type:type,id:item.id,label:item.label});
          if (!OEX_MS.cols.some(function(n){return n.id===item.id&&n.type===type;}))
            OEX_MS.cols.push({type:type,id:item.id,label:item.label});
        });
      } else {
        var ids=catItems.map(function(i){return i.id;});
        OEX_MS.rows=OEX_MS.rows.filter(function(n){return !(n.type===type&&ids.indexOf(n.id)>=0);});
        OEX_MS.cols=OEX_MS.cols.filter(function(n){return !(n.type===type&&ids.indexOf(n.id)>=0);});
      }
      OEX_MS.cache={};
      oexRefreshChks();
      oexLoadMatrix();
    }

    /* ── Toggle a single node — 'both' adds/removes from rows AND cols ── */
    window.oexToggleNode = function(type,id,label,axis,add) {
      function _tog(arr) {
        var idx=arr.findIndex(function(n){return n.id===id&&n.type===type;});
        var shouldAdd=(typeof add==='boolean')?add:idx===-1;
        if (shouldAdd && idx===-1) arr.push({type:type,id:id,label:label});
        else if (!shouldAdd && idx>=0) arr.splice(idx,1);
      }
      if (axis==='both'||axis==='row') _tog(OEX_MS.rows);
      if (axis==='both'||axis==='col') _tog(OEX_MS.cols);
      OEX_MS.cache={};
      oexRefreshChks();
      oexLoadMatrix();
    };

    /* ── Coverage strength ───────────────────────────────────────────── */
    async function oexStrength(rowNode,colNode) {
      var key=rowNode.type+'|'+rowNode.id+'|'+colNode.type+'|'+colNode.id;
      if (OEX_MS.cache[key] && OEX_MS.cache[key]!=='pending') return OEX_MS.cache[key];
      var result={pct:null,covered:null,total:null};
      try {
        if (rowNode.type==='tables' || colNode.type==='tables') {
          result = await _oexTableStrength(rowNode,colNode);
        } else {
          var drugIds=await _oexGetDrugIds(rowNode);
          if (!drugIds||!drugIds.length){OEX_MS.cache[key]=result;return result;}
          result.total=drugIds.length;
          result.covered=await _oexCountCovered(drugIds,colNode);
          result.pct=Math.round(result.covered/result.total*100);
        }
      } catch(e){console.warn('[OEX strength]',e);}
      OEX_MS.cache[key]=result;
      return result;
    }

    /* ── Table × Table strength (schema overlap metric) ─────────────── */
    async function _oexTableStrength(rowNode,colNode) {
      var result={pct:null,covered:null,total:null};
      try {
        var rowTbl=rowNode.type==='tables'?rowNode.id:null;
        var colTbl=colNode.type==='tables'?colNode.id:null;
        if (!rowTbl) return result;

        /* Count total rows in row table */
        var cntRes=await _sb.from(rowTbl).select('*',{count:'exact',head:true});
        var total=cntRes.count||0;
        if (!total) return result;
        result.total=total;

        if (colTbl) {
          /* Table × Table: check if they share any relationship */
          var related=(OEX_JOIN_MAP[rowTbl]||[]).indexOf(colTbl)>=0;
          if (!related&&(OEX_JOIN_MAP[colTbl]||[]).indexOf(rowTbl)<0) {
            result.pct=0; result.covered=0; return result;
          }
          /* Context-aware FK lookup:
             fkForward = FK in colTbl pointing to rowTbl (colTbl child, rowTbl parent)
             fkReverse = FK in rowTbl pointing to colTbl (rowTbl child, colTbl parent) */
          var fkForward = OEX_FK_MAP[colTbl] && OEX_FK_MAP[colTbl][rowTbl];
          var fkReverse = OEX_FK_MAP[rowTbl] && OEX_FK_MAP[rowTbl][colTbl];

          if (fkForward) {
            /* colTbl references rowTbl — "what % of rowTbl rows appear in colTbl?" */
            var lr=await _sb.from(colTbl).select(fkForward).limit(2000);
            var ids=new Set((lr.data||[]).map(function(r){return r[fkForward];}));
            var pkRes=await _sb.from(rowTbl).select('id').limit(2000);
            var pkIds=(pkRes.data||[]).map(function(r){return r.id;});
            result.covered=pkIds.filter(function(id){return ids.has(id);}).length;
            result.pct=Math.round(result.covered/total*100);
          } else if (fkReverse) {
            /* rowTbl references colTbl — "what % of rowTbl FK values are valid in colTbl?" */
            var lr2=await _sb.from(rowTbl).select(fkReverse).limit(2000);
            var colPkRes=await _sb.from(colTbl).select('id').limit(2000);
            var colPkSet=new Set((colPkRes.data||[]).map(function(r){return r.id;}));
            result.covered=(lr2.data||[]).filter(function(r){return colPkSet.has(r[fkReverse]);}).length;
            result.pct=Math.round(result.covered/total*100);
          } else {
            /* No direct FK known — mark as not directly related */
            result.pct=null; result.covered=null;
          }
        } else {
          /* Table × biological layer */
          var drugIds=await _oexGetDrugIds(colNode);
          if (!drugIds||!drugIds.length) return result;
          var pkRes2=await _sb.from(rowTbl).select('id').limit(2000);
          var pkIds2=(pkRes2.data||[]).map(function(r){return r.id;});
          var drugSet=new Set(drugIds);
          var covered2=pkIds2.filter(function(id){return drugSet.has(id);}).length;
          result.covered=covered2;
          result.pct=Math.round(covered2/total*100);
        }
      } catch(e){console.warn('[OEX table strength]',e);}
      return result;
    }

    async function _oexGetDrugIds(node) {
      if (node.type==='areas'){
        var r=await _sb.from('drug_area_scores').select('drug_id').eq('area_id',node.id).limit(500);
        return (r.data||[]).map(function(x){return x.drug_id;});
      }
      if (node.type==='stages'){
        var r=await _sb.from('drugs').select('id').eq('stage',node.id).limit(500);
        return (r.data||[]).map(function(x){return x.id;});
      }
      if (node.type==='companies'){
        var r=await _sb.from('drugs').select('id').eq('company_id',node.id).limit(500);
        if (!r.data||!r.data.length){
          var cr=await _sb.from('companies').select('name').eq('id',node.id).limit(1);
          var cname=cr.data&&cr.data[0]?cr.data[0].name:node.label;
          var r2=await _sb.from('drugs').select('id').ilike('company_display','%'+cname+'%').limit(500);
          return (r2.data||[]).map(function(x){return x.id;});
        }
        return (r.data||[]).map(function(x){return x.id;});
      }
      if (node.type==='targets'){
        var r=await _sb.from('drug_targets').select('drug_id').eq('target_id',node.id).limit(500);
        return (r.data||[]).map(function(x){return x.drug_id;});
      }
      return [];
    }

    async function _oexCountCovered(drugIds,colNode) {
      if (!drugIds.length) return 0;
      var ids=drugIds.slice(0,400);
      if (colNode.type==='layers') return await _oexCountCoveredLayer(ids,colNode.id);
      if (colNode.type==='areas'){
        var r=await _sb.from('drug_area_scores').select('drug_id').eq('area_id',colNode.id).in('drug_id',ids).limit(500);
        return (r.data||[]).length;
      }
      if (colNode.type==='stages'){
        var r=await _sb.from('drugs').select('id').eq('stage',colNode.id).in('id',ids).limit(500);
        return (r.data||[]).length;
      }
      if (colNode.type==='companies'){
        var r=await _sb.from('drugs').select('id').eq('company_id',colNode.id).in('id',ids).limit(500);
        return (r.data||[]).length;
      }
      if (colNode.type==='targets'){
        var r=await _sb.from('drug_targets').select('drug_id').eq('target_id',colNode.id).in('drug_id',ids).limit(500);
        return (r.data||[]).length;
      }
      return 0;
    }

    async function _oexCountCoveredLayer(drugIds,layerId) {
      if (layerId==='news'){
        var r=await _sb.from('news_articles').select('matched_drug_ids').limit(500);
        var found=new Set();
        (r.data||[]).forEach(function(row){
          (row.matched_drug_ids||[]).forEach(function(id){if(drugIds.indexOf(id)>=0)found.add(id);});
        });
        return found.size;
      }
      var tbl=layerId==='targets'?'drug_targets':layerId==='indications'?'drug_indications':layerId==='trials'?'trials':layerId==='catalysts'?'catalysts':null;
      if (!tbl) return 0;
      var r=await _sb.from(tbl).select('drug_id').in('drug_id',drugIds).limit(1000);
      return new Set((r.data||[]).map(function(x){return x.drug_id;})).size;
    }

    /* ── Render matrix (event delegation, no inline onclick) ────────── */
    async function oexRenderMatrix() {
      var wrap=document.getElementById('oex-mwrap');
      if (!wrap) return;
      var rows=OEX_MS.rows, cols=OEX_MS.cols;
      if (!rows.length||!cols.length) {
        wrap.innerHTML='<div style="padding:24px 16px;font-size:12px;color:#475569;text-align:center">'
          +'Check items in the sidebar to add them to the matrix.</div>';
        _oexWireCellClicks();
        return;
      }

      /* For symmetric matrix: if rows and cols have same items, compute strength for all pairs.
         We use union of rows+cols as the load set to handle asymmetric cases too. */
      var allNodes=rows.slice();
      cols.forEach(function(c){if(!allNodes.some(function(n){return n.id===c.id&&n.type===c.type;}))allNodes.push(c);});

      /* Pre-load all cells */
      await Promise.all(allNodes.map(function(r){return Promise.all(allNodes.map(function(c){return oexStrength(r,c);}));}));

      /* Collect per-cell data */
      var cellData={};
      rows.forEach(function(r){cols.forEach(function(c){
        var k=r.type+'|'+r.id+'|'+c.type+'|'+c.id;
        cellData[k]=OEX_MS.cache[k]||{pct:null,covered:null,total:null};
      });});

      /* Sort rows */
      var sorted=_oexSortRows(rows,cellData);

      /* Symmetric adjacency matrix: when rows and cols contain the same items,
         sort columns to match the row order so item N is at row N AND col N. */
      var rowKeys=sorted.map(function(n){return n.type+'|'+n.id;});
      var colKeys=cols.map(function(n){return n.type+'|'+n.id;});
      var sameItems=rowKeys.length===colKeys.length&&rowKeys.every(function(k){return colKeys.indexOf(k)>=0;});
      var displayCols=sameItems?sorted:cols;

      /* Build table — use data-* attrs only, no inline onclick strings */
      var html='<table style="border-collapse:collapse;min-width:100%">';
      html+='<thead><tr><th style="padding:6px 10px;font-size:10px;color:#475569;text-align:left;background:#060d14;position:sticky;top:0;z-index:2;min-width:130px">Node</th>';
      displayCols.forEach(function(c){
        html+='<th style="padding:6px 8px;font-size:10px;color:#94a3b8;text-align:center;background:#060d14;position:sticky;top:0;z-index:2;min-width:80px;white-space:nowrap">'
          +'<span style="font-size:8px;text-transform:uppercase;letter-spacing:.05em">'+c.label+'</span></th>';
      });
      html+='</tr></thead><tbody>';

      sorted.forEach(function(row){
        /* Determine if this row has ANY cell ≤ ceiling */
        var hasCellInCeiling = displayCols.some(function(col){
          var k=row.type+'|'+row.id+'|'+col.type+'|'+col.id;
          var d=cellData[k]; var p=d?d.pct:null;
          return p===null || p<=OEX_MS.ceiling;
        });
        var rowDisplay = (OEX_MS.ceiling<100 && !hasCellInCeiling) ? 'display:none' : '';

        html+='<tr style="'+rowDisplay+'">';
        html+='<td style="padding:5px 10px;font-size:11px;color:#cbd5e1;background:#060d14;white-space:nowrap;position:sticky;left:0;z-index:1">'+_oexTypeDot(row.type)+row.label+'</td>';
        displayCols.forEach(function(col){
          var k=row.type+'|'+row.id+'|'+col.type+'|'+col.id;
          var d=cellData[k]; var pct=d?d.pct:null;
          /* When ceiling<100: cells > ceiling are dimmed; cells ≤ ceiling shown fully */
          var belowCeiling = pct===null || pct<=OEX_MS.ceiling;
          var bg=pct===null?'#0d1520':(pct>=70?'rgba(74,222,128,.12)':pct>=40?'rgba(251,191,36,.10)':pct>=15?'rgba(251,146,60,.09)':'rgba(248,113,113,.08)');
          var fg=pct===null?'#2d4a6a':(pct>=70?'#4ade80':pct>=40?'#fbbf24':pct>=15?'#fb923c':'#f87171');
          var opacity = (OEX_MS.ceiling<100 && !belowCeiling) ? '0.12' : '1';
          /* Highlight gap cells when filtered */
          var outline = (OEX_MS.ceiling<100 && belowCeiling && pct!==null && pct<70) ? 'outline:1px solid '+fg+';outline-offset:-1px;' : '';
          html+='<td class="oex-cell" '
            +'data-row-type="'+row.type+'" data-row-id="'+row.id+'" data-row-label="'+row.label.replace(/"/g,'&quot;')+'" '
            +'data-col-type="'+col.type+'" data-col-id="'+col.id+'" data-col-label="'+col.label.replace(/"/g,'&quot;')+'" '
            +'style="text-align:center;padding:4px 6px;cursor:pointer;background:'+bg+';opacity:'+opacity+';transition:opacity .15s;'+outline+'">';
          if (pct!==null) html+='<span style="font-size:11px;font-weight:700;color:'+fg+'">'+pct+'%</span>';
          else html+='<span style="font-size:10px;color:#1e3050">—</span>';
          html+='</td>';
        });
        html+='</tr>';
      });
      html+='</tbody></table>';
      wrap.innerHTML=html;
      _oexWireCellClicks();

      var sub=document.getElementById('oex-matrix-subtitle');
      if (sub) {
        var visRows=sorted.filter(function(row){
          return displayCols.some(function(col){
            var k=row.type+'|'+row.id+'|'+col.type+'|'+col.id;
            var d=cellData[k]; var p=d?d.pct:null;
            return p===null||p<=OEX_MS.ceiling;
          });
        }).length;
        sub.textContent=rows.length+' rows × '+displayCols.length+' cols'
          +(OEX_MS.ceiling<100?' · '+visRows+' rows with gaps ≤'+OEX_MS.ceiling+'%':'');
      }
    }

    /* ── Wire cell click listener (event delegation) ─────────────────── */
    function _oexWireCellClicks() {
      var wrap=document.getElementById('oex-mwrap');
      if (!wrap||wrap._oexClickWired) return;
      wrap._oexClickWired=true;
      wrap.addEventListener('click',function(e){
        var td=e.target.closest('.oex-cell');
        if (!td) return;
        _oexHandleCell(td, e);
      });
    }

    function _oexHandleCell(td, e) {
      var rn={type:td.getAttribute('data-row-type'),id:td.getAttribute('data-row-id'),label:td.getAttribute('data-row-label')};
      var cn={type:td.getAttribute('data-col-type'),id:td.getAttribute('data-col-id'),label:td.getAttribute('data-col-label')};
      var isMulti = e && (e.shiftKey||e.metaKey||e.ctrlKey);
      if (isMulti) {
        var key=rn.id+'|'+cn.id;
        var idx=OEX_SEL.findIndex(function(s){return s.key===key;});
        if (idx>=0) {
          OEX_SEL.splice(idx,1);
          td.style.outline=''; td.style.outlineOffset='';
        } else {
          if (OEX_SEL.length>=6) {
            var old=OEX_SEL.shift();
            var oldTd=document.querySelector('.oex-cell[data-row-id="'+old.rn.id+'"][data-col-id="'+old.cn.id+'"]');
            if (oldTd){oldTd.style.outline='';oldTd.style.outlineOffset='';}
          }
          OEX_SEL.push({key:key,rn:rn,cn:cn});
          td.style.outline='2px solid #f59e0b'; td.style.outlineOffset='-2px';
        }
      } else {
        document.querySelectorAll('#oex-mwrap .oex-cell').forEach(function(t){t.style.outline='';t.style.outlineOffset='';});
        OEX_SEL=[{key:rn.id+'|'+cn.id,rn:rn,cn:cn}];
        td.style.outline='2px solid #f59e0b'; td.style.outlineOffset='-2px';
      }
      oexRenderInspector();
    }

    function _oexTypeDot(type) {
      var colors={areas:'#10b981',targets:'#8b5cf6',stages:'#f59e0b',companies:'#3b82f6',layers:'#06b6d4',tables:'#94a3b8'};
      var c=colors[type]||'#64748b';
      return '<span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:'+c+';margin-right:6px;flex-shrink:0;vertical-align:middle"></span>';
    }

    function _oexSortRows(rows,cellData) {
      if (OEX_MS.sort==='alpha') return rows.slice().sort(function(a,b){return a.label.localeCompare(b.label);});
      return rows.slice().sort(function(a,b){
        var aA=_rowAvg(a,cellData), bA=_rowAvg(b,cellData);
        return OEX_MS.sort==='desc'?bA-aA:aA-bA;
      });
    }
    function _rowAvg(node,cellData) {
      var k=node.type+'|'+node.id;
      var vals=Object.keys(cellData).filter(function(key){return key.startsWith(k+'|');})
        .map(function(key){return cellData[key].pct;}).filter(function(v){return v!==null;});
      return vals.length?vals.reduce(function(a,b){return a+b;},0)/vals.length:-1;
    }

    /* ── Inspector ───────────────────────────────────────────────────── */
    async function oexRenderInspector() {
      var panel=document.getElementById('oex-insp');
      var countEl=document.getElementById('oex-insp-sel-count');
      if (!panel) return;
      if (!OEX_SEL.length) {
        panel.innerHTML='<div style="padding:16px 12px;font-size:11px;color:#2d4a6a">Click a cell to inspect.<br><span style="font-size:10px;color:#1e3050">&#8679;Shift or &#8984;Cmd+click to compare multiple.</span></div>';
        if (countEl) countEl.textContent='';
        return;
      }
      if (countEl) countEl.textContent=OEX_SEL.length>1?OEX_SEL.length+' selected':'';
      panel.innerHTML='<div style="padding:8px 12px;font-size:10px;color:#3a5a7a">Loading...</div>';

      var loaded=await Promise.all(OEX_SEL.map(async function(sel){
        return {sel:sel,d:await oexStrength(sel.rn,sel.cn)};
      }));

      var html='';
      if (loaded.length===1) {
        var rn=loaded[0].sel.rn, cn=loaded[0].sel.cn, d=loaded[0].d;
        var pct=d.pct;
        var bc=pct===null?'#475569':(pct>=70?'#4ade80':pct>=40?'#fbbf24':pct>=15?'#fb923c':'#f87171');
        var tier=pct===null?'No data':(pct>=70?'Strong':pct>=40?'Partial':pct>=15?'Sparse':'Missing');
        html='<div style="padding:10px 12px">'
          +'<div style="font-size:12px;font-weight:600;color:#e2e8f0;margin-bottom:4px">'+rn.label+' <span style="color:#475569">&#215;</span> '+cn.label+'</div>'
          +'<div style="margin-bottom:10px"><span style="background:'+bc+';color:#0a1525;font-size:11px;font-weight:700;padding:2px 8px;border-radius:10px">'+tier+(pct!==null?' &mdash; '+pct+'%':'')+'</span></div>';
        if (d.covered!==null) html+='<div style="font-size:11px;color:#64748b;margin-bottom:8px">'+d.covered+' of '+d.total+' have '+cn.label+' data</div>';
        if (rn.type==='areas'&&cn.type==='layers') html+='<div id="oex-drill-detail" style="font-size:10px;color:#475569;margin-top:4px">Loading details...</div>';
        html+='</div>';
      } else {
        html='<div style="padding:8px 12px">';
        html+='<div style="font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px">Comparison ('+loaded.length+')</div>';
        html+='<table style="width:100%;border-collapse:collapse">'
          +'<tr style="border-bottom:1px solid #1e3050"><th style="font-size:10px;color:#475569;padding:3px 4px;text-align:left">Row</th><th style="font-size:10px;color:#475569;padding:3px 4px;text-align:left">Col</th><th style="font-size:10px;color:#475569;padding:3px 4px;text-align:right">%</th><th style="font-size:10px;color:#475569;padding:3px 4px;text-align:right">n</th></tr>';
        loaded.forEach(function(item){
          var p=item.d.pct;
          var fg=p===null?'#475569':(p>=70?'#4ade80':p>=40?'#fbbf24':p>=15?'#fb923c':'#f87171');
          html+='<tr style="border-bottom:1px solid #0d1520">'
            +'<td style="font-size:10px;color:#94a3b8;padding:4px">'+item.sel.rn.label+'</td>'
            +'<td style="font-size:10px;color:#94a3b8;padding:4px">'+item.sel.cn.label+'</td>'
            +'<td style="font-size:11px;font-weight:700;color:'+fg+';text-align:right;padding:4px">'+(p===null?'&mdash;':p+'%')+'</td>'
            +'<td style="font-size:10px;color:#64748b;text-align:right;padding:4px">'+(item.d.covered!==null?item.d.covered+'/'+item.d.total:'&mdash;')+'</td></tr>';
        });
        html+='</table>';
        var gaps=loaded.filter(function(i){return i.d.pct!==null&&i.d.pct<40;});
        if (gaps.length) {
          html+='<div style="margin-top:10px;font-size:10px;font-weight:700;color:#f87171;text-transform:uppercase;letter-spacing:.06em">Gaps ('+gaps.length+')</div>';
          gaps.forEach(function(item){
            html+='<div style="font-size:10px;color:#f87171;padding:2px 0">'+item.sel.rn.label+' × '+item.sel.cn.label+' <span style="color:#475569">('+item.d.pct+'%)</span></div>';
          });
        }
        html+='</div>';
      }
      panel.innerHTML=html;

      if (loaded.length===1) {
        var rn=loaded[0].sel.rn, cn=loaded[0].sel.cn, d=loaded[0].d;
        if (rn.type==='areas'&&cn.type==='layers') _oexDrillAreaLayer(panel,rn,cn,d);
      }
    }

    async function _oexDrillAreaLayer(panel,rowNode,colNode,d) {
      var detailEl=panel.querySelector('#oex-drill-detail');
      if (!detailEl) return;
      try {
        var dasRes=await _sb.from('drug_area_scores').select('drug_id,drugs(name)').eq('area_id',rowNode.id).limit(200);
        var allDrugs=(dasRes.data||[]).map(function(r){return {id:r.drug_id,name:(r.drugs&&r.drugs.name)||r.drug_id};});
        var layerIds=new Set();
        var tbl=colNode.id==='targets'?'drug_targets':colNode.id==='indications'?'drug_indications':colNode.id==='trials'?'trials':colNode.id==='catalysts'?'catalysts':null;
        if (tbl) {
          var lr=await _sb.from(tbl).select('drug_id').in('drug_id',allDrugs.map(function(d){return d.id;})).limit(500);
          (lr.data||[]).forEach(function(r){layerIds.add(r.drug_id);});
        }
        var covered=allDrugs.filter(function(d){return layerIds.has(d.id);});
        var missing =allDrugs.filter(function(d){return !layerIds.has(d.id);});
        var chip='display:inline-block;padding:1px 5px;border-radius:8px;font-size:9px;margin:1px;white-space:nowrap';
        var html='<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px">'
          +'<div><div style="color:#4ade80;font-size:9px;font-weight:700;margin-bottom:3px">COVERED ('+covered.length+')</div>';
        covered.slice(0,25).forEach(function(d){html+='<span style="'+chip+';background:rgba(74,222,128,.1);color:#4ade80">'+d.name+'</span>';});
        if (covered.length>25) html+='<div style="color:#475569;font-size:9px">+'+(covered.length-25)+' more</div>';
        html+='</div><div><div style="color:#f87171;font-size:9px;font-weight:700;margin-bottom:3px">MISSING ('+missing.length+')</div>';
        missing.slice(0,25).forEach(function(d){html+='<span style="'+chip+';background:rgba(248,113,113,.1);color:#f87171">'+d.name+'</span>';});
        if (missing.length>25) html+='<div style="color:#475569;font-size:9px">+'+(missing.length-25)+' more</div>';
        html+='</div></div>';
        detailEl.innerHTML=html;
      } catch(e){detailEl.textContent='Error: '+e.message;}
    }

    /* ── Toolbar controls ─────────────────────────────────────────────── */
    window.oexSortMatrix = function(val){OEX_MS.sort=val;oexRenderMatrix();};

    window.oexSetCeiling = function(val) {
      OEX_MS.ceiling=parseInt(val,10);
      var off='font-size:10px;padding:2px 7px;background:#0d1f35;border:1px solid #1e3050;border-radius:4px;color:#94a3b8;cursor:pointer;font-weight:400';
      var on ='font-size:10px;padding:2px 7px;background:#1e4d2b;border:1px solid #4ade80;border-radius:4px;color:#4ade80;cursor:pointer;font-weight:600';
      [25,50,75,100].forEach(function(v){
        var el=document.getElementById('oexq-'+v); if(el) el.style.cssText=(v===OEX_MS.ceiling?on:off);
      });
      oexRenderMatrix();
    };

    window.oexResetMatrix = function(){
      OEX_MS.rows=[]; OEX_MS.cols=[]; OEX_MS.cache={}; OEX_MS.ceiling=100; OEX_MS.sort='desc';
      OEX_SEL=[];
      oexSetCeiling(100);
      var s=document.getElementById('oex-sort-select'); if(s) s.value='desc';
      oexRefreshChks();
      oexRenderMatrix();
      var p=document.getElementById('oex-insp'); if(p) p.innerHTML='';
      var c=document.getElementById('oex-insp-sel-count'); if(c) c.textContent='';
    };

    window.oexClearInspector = function(){
      OEX_SEL=[];
      document.querySelectorAll('#oex-mwrap .oex-cell').forEach(function(t){t.style.outline='';t.style.outlineOffset='';});
      var p=document.getElementById('oex-insp');
      if(p) p.innerHTML='<div style="padding:16px 12px;font-size:11px;color:#2d4a6a">Click a cell to inspect.<br><span style="font-size:10px;color:#1e3050">&#8679;Shift or &#8984;Cmd+click to compare multiple.</span></div>';
      var c=document.getElementById('oex-insp-sel-count'); if(c) c.textContent='';
    };

    window.oexLoadMatrix = async function(){
      var wrap=document.getElementById('oex-mwrap');
      if(wrap&&OEX_MS.rows.length&&OEX_MS.cols.length)
        wrap.innerHTML='<div style="padding:16px 12px;font-size:11px;color:#3a5a7a">Computing...</div>';
      await oexRenderMatrix();
    };

    /* ── L4 expansion ─────────────────────────────────────────────────── */
    window.oexExpandL4 = async function(el,areaId,overlapTier){
      var wrap=el.nextElementSibling;
      if (!wrap) return;
      if (wrap.classList.contains('open')){wrap.classList.remove('open');el.classList.remove('sel');return;}
      el.classList.add('sel');
      wrap.innerHTML='<div style="padding:4px 20px;font-size:10px;color:#3a5a7a">Loading...</div>';
      wrap.classList.add('open');
      try {
        var q=_sb.from('drug_area_scores').select('drug_id,drugs(name,brand_name,stage)').eq('area_id',areaId).limit(200);
        if (overlapTier) q=q.eq('overlap',overlapTier);
        var res=await q;
        var drugs=(res.data||[]).map(function(r){
          var bn=(r.drugs&&r.drugs.brand_name)||null;
          var nm=(r.drugs&&r.drugs.name)||r.drug_id;
          return {name: bn ? bn + (nm && nm.toLowerCase()!==bn.toLowerCase() ? ' ('+nm+')' : '') : nm, stage:(r.drugs&&r.drugs.stage)||''};
        }).sort(function(a,b){return a.name.localeCompare(b.name);});
        if (!drugs.length){wrap.innerHTML='<div style="padding:4px 20px;font-size:10px;color:#3a5a7a">No drugs found</div>';return;}
        wrap.innerHTML=drugs.map(function(d){
          return '<div style="padding:2px 20px;font-size:10px;color:#64748b;display:flex;justify-content:space-between"><span>'+d.name+'</span><span style="color:#3a5a7a;font-size:9px">'+d.stage+'</span></div>';
        }).join('');
      } catch(e){wrap.innerHTML='<div style="padding:4px 20px;font-size:10px;color:#f87171">Error: '+e.message+'</div>';}
    };

    /* ── Override oexRender ───────────────────────────────────────────── */
    var _origOexRender=window.oexRender;
    window.oexRender=async function(){
      await _origOexRender();
      try {
        if (!OEX_CAT) await oexInitCatalog();
        setTimeout(function(){
          oexInjectTreeButtons();
          var p=document.getElementById('oex-insp');
          if(p&&!p.innerHTML.trim()) p.innerHTML='<div style="padding:16px 12px;font-size:11px;color:#2d4a6a">Click a cell to inspect.<br><span style="font-size:10px;color:#1e3050">&#8679;Shift or &#8984;Cmd+click to compare multiple.</span></div>';
        },400);
      } catch(e){console.error('[OEX] init',e);}
    };

    /* Patch oexLoadTree to re-inject after polls */
    setTimeout(function(){
      var orig=window.oexLoadTree;
      if (orig&&!orig._patched){
        orig._patched=true;
        window.oexLoadTree=async function(){
          await orig();
          OEX_TREE_INJECTED=false;
          setTimeout(function(){if(OEX_CAT) oexInjectTreeButtons();},300);
        };
      }
    },600);

  })();
