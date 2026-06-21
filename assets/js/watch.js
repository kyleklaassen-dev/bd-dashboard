/* ── Priority Watch ───────────────────────────────────────────────────────────
   The depth-focus list: companies running drugs that compete DIRECTLY with Ailux's
   molecules, tiered by threat. Preclinical / early-clinical direct competitors of
   our core mechanism (TL1A × IL-23p19) are surfaced first — they are the assets to
   watch hardest when news or data drops.

   Derived live from drugs.ailux_competes_directly (no backend table needed):
     CRITICAL — owns an EARLY (Preclinical/Ph1) competitor on our CORE mechanism
                (TL1A × IL-23p19 bispecific). The essential early radar.
     HIGH     — owns an EARLY direct competitor in any Ailux area.
     ACTIVE   — owns only later-stage (Ph2+/approved) direct competitors.
   Self-contained; registerTab('watch'). ──────────────────────────────────────── */
(function(){
  const SB_URL = (typeof SUPABASE_URL!=='undefined'?SUPABASE_URL:'https://tghntyofptvfhmtchwcv.supabase.co');
  const SB_KEY = (typeof SUPABASE_ANON!=='undefined'?SUPABASE_ANON:'');
  let _rows = null, _fArea = null;

  function esc(s){ return (s==null?'':String(s)).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];}); }

  // ── classification helpers ──
  function isEarly(stage){ const s=(stage||'').toLowerCase(); return s.indexOf('preclin')>=0 || /phase\s*1\b|phase\s*i\b|phase 1/.test(s); }
  function isCore(target){ const t=(target||'').toUpperCase().replace(/[-\s]/g,''); return t.indexOf('TL1A')>=0 && (t.indexOf('IL23')>=0); }
  function areaOf(target){
    const t=(target||'').toUpperCase();
    if(t.indexOf('TL1A')>=0 || t.indexOf('DR3')>=0) return 'tl1a';
    if(t.indexOf('TSLP')>=0) return 'tslp';
    if(t.indexOf('IL-4')>=0 || t.indexOf('IL4')>=0 || t.indexOf('IL-13')>=0 || t.indexOf('IL13')>=0 || t.indexOf('OX40')>=0) return 'il4ra';
    if(t.indexOf('IGF')>=0 || t.indexOf('TSHR')>=0) return 'igf1r';
    if(t.indexOf('FCRN')>=0 || t.indexOf('FCRN')>=0) return 'fcrn';
    if(t.indexOf('CD19')>=0 || t.indexOf('CD3')>=0 || t.indexOf('BCMA')>=0 || t.indexOf('TREG')>=0) return 'tcell';
    return 'other';
  }
  const AREA_LABEL = {tl1a:'TL1A',tslp:'TSLP',il4ra:'IL-4Rα',igf1r:'IGF1R',fcrn:'FcRn',tcell:'T-cell',other:'Other'};
  // stage display color
  function stageColor(stage){
    const s=(stage||'').toLowerCase();
    if(s.indexOf('approv')>=0||s.indexOf('bla')>=0||s.indexOf('nda')>=0) return '#166534';
    if(s.indexOf('phase 3')>=0||s.indexOf('phase iii')>=0) return '#1e40af';
    if(s.indexOf('phase 2')>=0||s.indexOf('phase ii')>=0) return '#854d0e';
    if(s.indexOf('phase 1')>=0||s.indexOf('phase i')>=0) return '#475569';
    return '#64748b'; // preclinical / unknown
  }
  const TIERS = {
    critical:{label:'CRITICAL · early core-mechanism',col:'#991b1b',bg:'#fee2e2'},
    high:    {label:'HIGH · early direct competitor',  col:'#9a3412',bg:'#ffedd5'},
    active:  {label:'ACTIVE · later-stage competitor',  col:'#1e40af',bg:'#dbeafe'}
  };

  async function fetchRows(){
    const sel='name,company_id,company_display,stage,target,ailux_angle,vs_ailux';
    const url=SB_URL+'/rest/v1/drugs?select='+encodeURIComponent(sel)+'&ailux_competes_directly=is.true&limit=500';
    const res=await fetch(url,{headers:{apikey:SB_KEY,Authorization:'Bearer '+SB_KEY}});
    if(!res.ok) throw new Error('HTTP '+res.status);
    return await res.json();
  }

  // group competitor drugs by company, assign a tier
  function buildCompanies(rows){
    const by={};
    rows.forEach(function(r){
      const key=r.company_id || (r.company_display||'unknown');
      if(!by[key]) by[key]={key:key, name:r.company_display||r.company_id||'Unknown', drugs:[], areas:{}};
      const a=areaOf(r.target);
      by[key].drugs.push({name:r.name, stage:r.stage, target:r.target, area:a, early:isEarly(r.stage), core:isCore(r.target), angle:r.ailux_angle, vs:r.vs_ailux});
      by[key].areas[a]=true;
    });
    const list=Object.values(by).map(function(c){
      const earlyCore=c.drugs.some(function(d){return d.early&&d.core;});
      const early=c.drugs.some(function(d){return d.early;});
      c.tier = earlyCore?'critical':(early?'high':'active');
      c.nEarly=c.drugs.filter(function(d){return d.early;}).length;
      c.nCore=c.drugs.filter(function(d){return d.core;}).length;
      // sort a company's own assets: early+core first, then by stage recency (earlier stage = higher watch)
      const sord={preclinical:0,'phase 1':1,'phase i':1,'phase 2':2,'phase ii':2,'phase 3':3,'phase iii':3};
      c.drugs.sort(function(a,b){
        if(a.core!==b.core) return a.core?-1:1;
        if(a.early!==b.early) return a.early?-1:1;
        return (sord[(a.stage||'').toLowerCase()]||9)-(sord[(b.stage||'').toLowerCase()]||9);
      });
      return c;
    });
    const tord={critical:0,high:1,active:2};
    list.sort(function(a,b){
      if(tord[a.tier]!==tord[b.tier]) return tord[a.tier]-tord[b.tier];
      if(b.nCore!==a.nCore) return b.nCore-a.nCore;
      if(b.nEarly!==a.nEarly) return b.nEarly-a.nEarly;
      return b.drugs.length-a.drugs.length;
    });
    return list;
  }

  function openCompany(c){
    try{ if(typeof openCompanyEntityModal==='function'){ openCompanyEntityModal(c.key, c.name, null); return; } }catch(e){}
    try{ if(typeof navTo==='function'){ /* no-op fallback */ } }catch(e){}
  }
  window.__watchOpen=function(key){ const c=(_rows||[]).find(function(x){return x.key===key;}); if(c) openCompany(c); };
  window.__watchFilter=function(a){ _fArea=a; render(); };

  function drugRow(d){
    const flags=[];
    if(d.core) flags.push('<span style="font-size:9.5px;font-weight:800;color:#991b1b;background:#fee2e2;border-radius:6px;padding:1px 6px;letter-spacing:.3px">CORE MECH</span>');
    if(d.early && !d.core) flags.push('<span style="font-size:9.5px;font-weight:800;color:#9a3412;background:#ffedd5;border-radius:6px;padding:1px 6px;letter-spacing:.3px">EARLY</span>');
    return '<div style="display:flex;align-items:baseline;gap:9px;padding:6px 0;border-top:1px solid #f1f5f9;flex-wrap:wrap">'
      + '<span style="font-weight:800;color:#0f172a;font-size:13.5px">'+esc(d.name)+'</span>'
      + '<span style="font-size:11.5px;color:#64748b">'+esc(d.target||'')+'</span>'
      + '<span style="font-size:10.5px;font-weight:800;color:#fff;background:'+stageColor(d.stage)+';padding:1px 7px;border-radius:7px">'+esc(d.stage||'—')+'</span>'
      + flags.join(' ')
      + '</div>';
  }
  function card(c){
    const t=TIERS[c.tier];
    const areas=Object.keys(c.areas).filter(function(a){return a!=='other';}).map(function(a){return '<span style="font-size:10.5px;font-weight:700;color:#1e527d;background:#eef4fb;border-radius:10px;padding:1px 8px">'+esc(AREA_LABEL[a]||a)+'</span>';}).join(' ');
    const lead=c.drugs[0]||{};
    const angle=(lead.angle||lead.vs||'').trim();
    const why=angle?'<div style="margin-top:9px;font-size:12px;color:#46586a;line-height:1.5;border-left:3px solid '+t.col+';background:#f8fafc;padding:7px 11px;border-radius:0 6px 6px 0">'+esc(angle.slice(0,260))+(angle.length>260?'…':'')+'</div>':'';
    return '<div onclick="window.__watchOpen(\''+esc(c.key)+'\')" style="background:#fff;border:1px solid #e6edf4;border-left:4px solid '+t.col+';border-radius:13px;padding:15px 17px;margin-bottom:12px;cursor:pointer;transition:box-shadow .15s" '
      + 'onmouseover="this.style.boxShadow=\'0 4px 16px rgba(20,40,70,.08)\'" onmouseout="this.style.boxShadow=\'none\'">'
      + '<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap">'
      +   '<div style="font-size:16px;font-weight:900;color:#0f172a">'+esc(c.name)+'</div>'
      +   '<span style="font-size:9.5px;font-weight:800;color:'+t.col+';background:'+t.bg+';border-radius:20px;padding:3px 10px;letter-spacing:.3px;text-transform:uppercase">'+t.label+'</span>'
      + '</div>'
      + '<div style="display:flex;gap:7px;flex-wrap:wrap;margin-top:7px;align-items:center">'+areas
      +   '<span style="font-size:11px;color:#94a3b8;font-weight:600">'+c.drugs.length+' competing asset'+(c.drugs.length===1?'':'s')+(c.nEarly?' · '+c.nEarly+' early':'')+'</span>'
      + '</div>'
      + c.drugs.map(drugRow).join('')
      + why
      + '</div>';
  }

  function render(){
    const list=document.getElementById('watch-list'); if(!list) return;
    if(!_rows){ list.innerHTML='<div style="color:#64748b;padding:40px;text-align:center">Loading priority watch&hellip;</div>'; return; }
    const companies=_rows.filter(function(c){ return _fArea? c.areas[_fArea] : true; });
    // tier counts for the subtitle
    const crit=_rows.filter(function(c){return c.tier==='critical';}).length;
    const sub=document.getElementById('watch-subtitle');
    if(sub) sub.textContent=_rows.length+' priority companies · '+crit+' critical (early core-mechanism) · direct competitors of Ailux molecules';
    // area filter chips
    const fc=document.getElementById('watch-filter');
    if(fc){
      const present=['tl1a','tslp','il4ra','igf1r','fcrn','tcell'].filter(function(a){ return _rows.some(function(c){return c.areas[a];}); });
      function chip(lab,val,active){ return '<button onclick="window.__watchFilter('+(val===null?'null':"'"+val+"'")+')" style="cursor:pointer;font-size:11px;font-weight:700;padding:4px 11px;border-radius:14px;border:1px solid '+(active?'#991b1b':'#cbd5e1')+';background:'+(active?'#991b1b':'#fff')+';color:'+(active?'#fff':'#475569')+'">'+esc(lab)+'</button>'; }
      fc.innerHTML='<span style="font-size:11px;color:#94a3b8;font-weight:700;margin-right:2px">AREA</span>'
        + chip('All',null,_fArea===null)
        + present.map(function(a){return chip(AREA_LABEL[a]||a,a,_fArea===a);}).join('');
    }
    list.innerHTML = companies.length ? companies.map(card).join('')
      : '<div style="color:#64748b;padding:40px;text-align:center">No priority companies in this area.</div>';
  }

  async function load(){
    const list=document.getElementById('watch-list'); if(!list) return;
    if(!_rows) list.innerHTML='<div style="color:#64748b;padding:40px;text-align:center">Loading priority watch&hellip;</div>';
    try{
      const rows=await fetchRows();
      _rows=buildCompanies(rows);
      render();
    }catch(e){ list.innerHTML='<div style="color:#b91c1c;padding:40px;text-align:center">Could not load priority watch ('+esc(e.message)+')</div>'; }
  }
  if(typeof registerTab==='function') registerTab('watch',{onEnter:load});
  window.__watchRender=load;
})();
