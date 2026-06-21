(function(){
  const SB_URL = (typeof SUPABASE_URL!=='undefined'?SUPABASE_URL:'https://tghntyofptvfhmtchwcv.supabase.co');
  const SB_KEY = (typeof SUPABASE_ANON!=='undefined'?SUPABASE_ANON:'');
  const SEEN_KEY = 'meridian_reads_last_seen';
  // Colors cover both the legacy editorial read_types and the live `intel` intel_types.
  const TYPE_COLORS = {competitive:'#b45309',clinical_caveat:'#be123c',mechanism:'#1d4ed8',market:'#065f46',regulatory:'#7c3aed',thesis:'#0f766e',kol:'#9333ea',patient:'#0369a1',other:'#475569',
    data:'#be123c',deal:'#065f46',partnership:'#0f766e',conference:'#b45309',management:'#475569'};
  let _reads = null;
  const esc=MUI.esc, fmtDate=MUI.fmtDate;  // shared helpers (ui.js, loaded early)
  function refsLine(r){
    const e=r.entity_refs||{}; const parts=[].concat(e.drugs||[],e.companies||[],e.targets||[]);
    return parts.length ? parts.map(function(p){return '<span style="background:#eef2f7;color:#334155;font-size:11px;font-weight:600;padding:2px 7px;border-radius:8px">'+esc(p)+'</span>';}).join(' ') : '';
  }
  // Map the live daily research feed (`intel`, written every morning by the research
  // pipeline) onto the Read card shape. Reads is no longer a manual-only table — it
  // reflects what enrichment surfaced today. (research_reads was never written by any
  // pipeline; it went stale. See fix/aibs-and-reads-freshness.)
  function fromIntel(r){
    const co = (r.companies && r.companies.name) ? r.companies.name : null;
    const areas = (r.intel_areas||[]).map(function(a){return a.area_id;}).filter(Boolean);
    return {
      id: r.id,
      title: r.headline,
      read: r.body,
      read_type: r.intel_type || 'other',
      confidence: r.importance,
      so_what: null,
      source_url: r.source_url,
      source_name: r.source_name,
      created_at: r.created_at,
      intel_date: r.intel_date,
      entity_refs: { companies: co ? [co] : [], drugs: [], targets: areas }
    };
  }
  async function fetchReads(){
    const sel = 'id,headline,body,intel_type,importance,intel_date,created_at,source_url,source_name,'
      + 'companies!intel_primary_company_id_fkey(name),intel_areas(area_id)';
    const url = SB_URL+'/rest/v1/intel?select='+encodeURIComponent(sel)+'&order=created_at.desc&limit=200';
    const res = await fetch(url,{headers:{apikey:SB_KEY,Authorization:'Bearer '+SB_KEY}});
    if(!res.ok) throw new Error('HTTP '+res.status);
    const rows = await res.json();
    return rows.map(fromIntel);
  }
  function card(r){
    const col = TYPE_COLORS[r.read_type]||TYPE_COLORS.other;
    const conf = r.confidence ? '<span style="font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.4px">'+esc(r.confidence)+' confidence</span>' : '';
    const so = r.so_what ? '<div style="margin-top:10px;padding:10px 12px;background:#f8fafc;border-left:3px solid '+col+';border-radius:0 6px 6px 0;font-size:13.5px;color:#1e293b;line-height:1.55"><span style="font-weight:800;color:'+col+';font-size:11px;text-transform:uppercase;letter-spacing:.5px">So what</span><br>'+esc(r.so_what)+'</div>' : '';
    const srcLabel = r.source_name ? esc(r.source_name)+' &#8599;' : 'source &#8599;';
    const src = r.source_url ? '<a href="'+esc(r.source_url)+'" target="_blank" rel="noopener" style="font-size:11px;color:#2563eb;text-decoration:none">'+srcLabel+'</a>'
              : (r.source_name ? '<span style="font-size:11px;color:#94a3b8">'+esc(r.source_name)+'</span>' : '');
    return '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:18px 20px;margin-bottom:14px;box-shadow:0 1px 2px rgba(0,0,0,.04)">'
      + '<div style="display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap">'
      +   '<span style="font-size:10px;font-weight:800;color:#fff;background:'+col+';padding:3px 9px;border-radius:7px;text-transform:uppercase;letter-spacing:.5px">'+esc((r.read_type||'read').replace(/_/g,' '))+'</span>'
      +   '<span style="font-size:12px;color:#94a3b8;font-weight:600">'+fmtDate(r.created_at)+'</span>'
      + '</div>'
      + '<div style="font-size:16px;font-weight:800;color:#0f172a;margin:10px 0 6px;line-height:1.35">'+esc(r.title)+'</div>'
      + '<div style="font-size:14px;color:#334155;line-height:1.6">'+esc(r.read)+'</div>'
      + so
      + '<div style="display:flex;justify-content:space-between;align-items:center;gap:10px;margin-top:12px;flex-wrap:wrap"><div style="display:flex;gap:6px;flex-wrap:wrap">'+refsLine(r)+'</div><div style="display:flex;gap:12px;align-items:center">'+conf+src+'</div></div>'
      + '</div>';
  }
  function setBadge(n){ const b=document.getElementById('reads-badge'); if(!b) return; if(n>0){ b.textContent=n>9?'9+':String(n); b.style.display='inline-block'; } else { b.style.display='none'; } }
  let _fType=null, _fTarget=null;   // active filters (null = all)
  function targetsOf(r){ return ((r.entity_refs||{}).targets)||[]; }
  function chip(label,active,onclickAttr,col){
    const bg=active?(col||'#5b2da8'):'#fff', fg=active?'#fff':'#475569', bd=active?(col||'#5b2da8'):'#cbd5e1';
    return '<button onclick="'+onclickAttr+'" style="cursor:pointer;font-size:11px;font-weight:700;padding:4px 11px;border-radius:14px;border:1px solid '+bd+';background:'+bg+';color:'+fg+';letter-spacing:.2px">'+esc(label)+'</button>';
  }
  function buildFilters(){
    const types=[...new Set(_reads.map(function(r){return r.read_type||'other';}))].sort();
    const targets=[...new Set([].concat.apply([],_reads.map(targetsOf)))].sort();
    const tc=document.getElementById('reads-filter-type');
    const gc=document.getElementById('reads-filter-target');
    if(tc){ tc.innerHTML='<span style="font-size:11px;color:#94a3b8;font-weight:700;margin-right:2px">CATEGORY</span>'
      + chip('All',_fType===null,"window.__readsFilter('type',null)")
      + types.map(function(t){return chip(t.replace(/_/g,' '),_fType===t,"window.__readsFilter('type','"+t+"')",TYPE_COLORS[t]);}).join(''); }
    if(gc){ gc.innerHTML = targets.length ? ('<span style="font-size:11px;color:#94a3b8;font-weight:700;margin-right:2px">TARGET</span>'
      + chip('All',_fTarget===null,"window.__readsFilter('target',null)")
      + targets.map(function(t){return chip(t,_fTarget===t,"window.__readsFilter('target','"+t.replace(/'/g,"\\'")+"')",'#0f766e');}).join('')) : ''; }
  }
  function renderList(){
    const list=document.getElementById('reads-list'); if(!list) return;
    const rows=_reads.filter(function(r){
      if(_fType && (r.read_type||'other')!==_fType) return false;
      if(_fTarget && targetsOf(r).indexOf(_fTarget)<0) return false;
      return true;
    });
    list.innerHTML = rows.length ? rows.map(card).join('')
      : '<div style="color:#64748b;padding:40px;text-align:center">No reads match this filter.</div>';
    const sub=document.getElementById('reads-subtitle');
    if(sub){ const f=(_fType||_fTarget); sub.textContent = 'Raw daily research feed · '+rows.length+' read'+(rows.length===1?'':'s')+(f?' shown · '+_reads.length+' total':' · newest first'); }
  }
  window.__readsFilter=function(kind,val){ if(kind==='type')_fType=val; else _fTarget=val; buildFilters(); renderList(); };
  async function render(){
    const list=document.getElementById('reads-list'); if(!list) return;
    if(!_reads) list.innerHTML='<div style="color:#64748b;padding:40px;text-align:center">Loading reads&hellip;</div>';
    try{
      _reads = await fetchReads();
      if(!_reads.length){ list.innerHTML='<div style="color:#64748b;padding:40px;text-align:center">No reads yet. They appear here as research surfaces them.</div>'; setBadge(0); return; }
      buildFilters(); renderList();
      localStorage.setItem(SEEN_KEY,_reads[0].created_at);
      setBadge(0);
    }catch(e){ list.innerHTML='<div style="color:#b91c1c;padding:40px;text-align:center">Could not load reads ('+esc(e.message)+')</div>'; }
  }
  async function checkBadge(){
    try{
      const seen=localStorage.getItem(SEEN_KEY);
      const rows=await fetchReads();
      if(!rows.length) return setBadge(0);
      setBadge(seen ? rows.filter(function(r){return r.created_at>seen;}).length : rows.length);
    }catch(e){ /* non-blocking */ }
  }
  if(typeof registerTab==='function') registerTab('reads',{onEnter:render});
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',checkBadge); else setTimeout(checkBadge,800);
  window.__readsRender=render;
})();
