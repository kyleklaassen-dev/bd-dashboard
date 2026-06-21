/* ── Executive Briefing ────────────────────────────────────────────────────────
   The one "what is happening" surface. Assembles the cross-cutting intelligence
   that was previously dark — competitive_signals, intel_facts — alongside the
   catalyst calendar, all relevance-gated to Ailux's areas and lead with the datum.

     1. COMING UP      — next Ailux catalysts + what research expects (expected_impact)
     2. DEVELOPMENTS   — competitive_signals: what just moved, sourced (clinical / conference / financing)
     3. LATEST FACTS   — newest intel_facts: the literal facts, each with its source

   Self-contained; registerTab('briefing'). Fed continuously by the daily research
   + event-research pipelines. ──────────────────────────────────────────────────── */
(function(){
  const SB_URL=(typeof SUPABASE_URL!=='undefined'?SUPABASE_URL:'https://tghntyofptvfhmtchwcv.supabase.co');
  const SB_KEY=(typeof SUPABASE_ANON!=='undefined'?SUPABASE_ANON:'');
  const AILUX=['tl1a','tslp','il4ra','igf1r','fcrn','tcell'];
  const AREA_LABEL={tl1a:'TL1A',tslp:'TSLP',il4ra:'IL-4Rα',igf1r:'IGF1R',fcrn:'FcRn',tcell:'T-cell'};
  const SIG_COL={clinical_update:'#1d4ed8',conference:'#b45309',financing:'#065f46',deal:'#065f46',regulatory:'#7c3aed',data:'#be123c',partnership:'#0f766e'};
  let _data=null, _fArea=null;

  function esc(s){ return (s==null?'':String(s)).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];}); }
  function fmtDate(iso){ if(!iso) return ''; try{ return new Date(iso).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}); }catch(e){ return ''; } }
  function relDays(iso){ if(!iso) return ''; try{ var d=Math.round((new Date(iso)-Date.now())/864e5); return d<0?Math.abs(d)+'d ago':(d===0?'today':'in '+d+'d'); }catch(e){ return ''; } }
  function sigPill(sig){ var c=sig==='high'?'#991b1b':(sig==='medium'?'#92400e':'#475569'),b=sig==='high'?'#fee2e2':(sig==='medium'?'#fef3c7':'#f1f5f9');
    return '<span style="font-size:9.5px;font-weight:800;color:'+c+';background:'+b+';border-radius:10px;padding:1px 8px;text-transform:uppercase;letter-spacing:.3px">'+esc(sig||'—')+'</span>'; }
  function areaTag(a){ return '<span style="font-size:10.5px;font-weight:700;color:#1e527d;background:#eef4fb;border-radius:10px;padding:1px 8px">'+esc(AREA_LABEL[a]||a)+'</span>'; }
  function conf(c){ if(c==null) return ''; var pct=(typeof c==='number')?Math.round(c*100)+'%':esc(c); return '<span style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.3px">'+pct+' conf</span>'; }
  function srcLink(u,label){ if(!u) return ''; return '<a href="'+esc(u)+'" target="_blank" rel="noopener" style="font-size:11px;color:#2563eb;text-decoration:none">'+(label||'source')+' &#8599;</a>'; }

  const QIN='in.('+AILUX.join(',')+')';
  function q(table,params){ var url=SB_URL+'/rest/v1/'+table+'?'+params; return fetch(url,{headers:{apikey:SB_KEY,Authorization:'Bearer '+SB_KEY}}).then(function(r){return r.ok?r.json():[];}).catch(function(){return [];}); }

  async function fetchAll(){
    const today=new Date().toISOString().slice(0,10);
    const [cats,sigs,facts,posters,voices]=await Promise.all([
      q('catalysts','select=id,label,sort_date,catalyst_date,area_id,significance,expected_impact,drug_id,company_id&area_id='+QIN+'&sort_date=gte.'+today+'&order=sort_date.asc&limit=40'),
      q('competitive_signals','select=id,area_id,signal_type,title,description,source_url,source_date,confidence,created_at&area_id='+QIN+'&order=created_at.desc&limit=80'),
      q('intel_facts','select=id,claim,metric,value_text,value_num,unit,source_url,area_id,confidence,fact_type,created_at&area_id='+QIN+'&fact_type=not.in.(kol_sentiment,management)&order=created_at.desc&limit=60'),
      q('conference_abstracts','select=id,title,conference,conference_year,presentation_date,presentation_type,abstract_text,source_url,therapeutic_area_id,created_at&therapeutic_area_id='+QIN+'&order=created_at.desc&limit=40'),
      q('intel_facts','select=id,claim,subject_name,source_url,area_id,fact_type,created_at&area_id='+QIN+'&fact_type=in.(kol_sentiment,management)&order=created_at.desc&limit=30')
    ]);
    // normalize posters to carry area_id for the shared area filter
    (posters||[]).forEach(function(p){ p.area_id=p.therapeutic_area_id; });
    return {cats:cats,sigs:sigs,facts:facts,posters:posters||[],voices:voices||[]};
  }

  // ── section renderers ──
  function catItem(c){
    const exp=(c.expected_impact||'').trim();
    return '<div style="display:flex;gap:13px;align-items:baseline;padding:10px 0;border-top:1px solid #f1f5f9">'
      + '<div style="min-width:78px"><div style="font-size:13.5px;font-weight:800;color:#0f172a">'+esc(c.catalyst_date||fmtDate(c.sort_date))+'</div>'
      +   '<div style="font-size:10px;color:#94a3b8;font-weight:600">'+esc(relDays(c.sort_date))+'</div></div>'
      + '<div style="flex:1">'
      +   '<div style="display:flex;gap:7px;align-items:center;flex-wrap:wrap;margin-bottom:2px">'+areaTag(c.area_id)+sigPill(c.significance)+'</div>'
      +   '<div style="font-size:13.5px;font-weight:700;color:#1e293b;line-height:1.4">'+esc(c.label)+'</div>'
      +   (exp?'<div style="margin-top:5px;font-size:12px;color:#5b4a8a;background:#f5f1fe;border-left:3px solid #7c3aed;border-radius:0 6px 6px 0;padding:6px 10px;line-height:1.5"><b style="color:#6d28d9;font-size:10px;text-transform:uppercase;letter-spacing:.4px">Research expects</b><br>'+esc(exp)+'</div>':'')
      + '</div></div>';
  }
  function sigCard(s){
    const c=SIG_COL[s.signal_type]||'#475569';
    return '<div style="background:#fff;border:1px solid #e6edf4;border-radius:12px;padding:14px 16px;margin-bottom:11px">'
      + '<div style="display:flex;justify-content:space-between;gap:10px;align-items:baseline;flex-wrap:wrap">'
      +   '<div style="display:flex;gap:7px;align-items:center;flex-wrap:wrap">'
      +     '<span style="font-size:9.5px;font-weight:800;color:#fff;background:'+c+';border-radius:7px;padding:2px 8px;text-transform:uppercase;letter-spacing:.3px">'+esc((s.signal_type||'signal').replace(/_/g,' '))+'</span>'
      +     areaTag(s.area_id)+'</div>'
      +   '<span style="font-size:11px;color:#94a3b8;font-weight:600">'+esc(fmtDate(s.source_date||s.created_at))+'</span>'
      + '</div>'
      + '<div style="font-size:14.5px;font-weight:800;color:#0f172a;margin:8px 0 5px;line-height:1.35">'+esc(s.title)+'</div>'
      + (s.description?'<div style="font-size:13px;color:#334155;line-height:1.6">'+esc(s.description)+'</div>':'')
      + '<div style="display:flex;gap:12px;align-items:center;margin-top:9px">'+srcLink(s.source_url)+conf(s.confidence)+'</div>'
      + '</div>';
  }
  function factRow(f){
    var val=f.value_text||((f.value_num!=null)?(f.value_num+(f.unit?(' '+f.unit):'')):'');
    return '<div style="padding:9px 0;border-top:1px solid #f1f5f9">'
      + '<div style="display:flex;gap:7px;align-items:center;flex-wrap:wrap;margin-bottom:2px">'+areaTag(f.area_id)
      +   (f.fact_type?'<span style="font-size:9.5px;font-weight:700;color:#7c8aa0;background:#eef2f6;border-radius:9px;padding:1px 7px">'+esc(f.fact_type)+'</span>':'')
      +   (val?'<span style="font-size:11.5px;font-weight:800;color:#0f766e">'+esc(val)+'</span>':'')+'</div>'
      + '<div style="font-size:12.5px;color:#334155;line-height:1.5">'+esc(f.claim)+' '+srcLink(f.source_url)+'</div>'
      + '</div>';
  }
  function posterCard(p){
    const type=(p.presentation_type||'').toLowerCase();
    const isLB=type.indexOf('late')>=0;
    const typeCol=isLB?'#991b1b':(type.indexOf('oral')>=0?'#1d4ed8':'#b45309');
    const when=p.presentation_date?fmtDate(p.presentation_date):(p.conference_year||'');
    return '<div style="padding:10px 0;border-top:1px solid #f1f5f9">'
      + '<div style="display:flex;gap:7px;align-items:center;flex-wrap:wrap;margin-bottom:3px">'
      +   (p.conference?'<span style="font-size:10.5px;font-weight:800;color:#fff;background:'+typeCol+';border-radius:7px;padding:1px 8px">'+esc(p.conference)+(p.conference_year?(' '+p.conference_year):'')+'</span>':'')
      +   (p.presentation_type?'<span style="font-size:9.5px;font-weight:700;color:#475569;background:#eef2f6;border-radius:9px;padding:1px 7px;text-transform:uppercase;letter-spacing:.3px">'+esc(p.presentation_type)+'</span>':'')
      +   areaTag(p.area_id)
      +   '<span style="font-size:11px;color:#94a3b8;font-weight:600;margin-left:auto">'+esc(when)+'</span>'
      + '</div>'
      + '<div style="font-size:13.5px;font-weight:700;color:#0f172a;line-height:1.4">'+esc(p.title)+' '+srcLink(p.source_url)+'</div>'
      + (p.abstract_text?'<div style="margin-top:4px;font-size:12px;color:#46586a;line-height:1.55;white-space:pre-wrap">'+esc(String(p.abstract_text).slice(0,420))+(p.abstract_text.length>420?'…':'')+'</div>':'')
      + '</div>';
  }
  function voiceCard(v){
    // claim is typically a verbatim quote (often '"…" — Name, affiliation' from the research pipeline)
    var txt=String(v.claim||'').trim();
    var isQuote=txt.charAt(0)==='"'||txt.charAt(0)==='“';
    var who=v.subject_name?'<span style="font-size:11px;color:#94a3b8;font-weight:700">'+esc(v.subject_name)+'</span>':'';
    var kind=v.fact_type==='kol_sentiment'?'KOL':'MGMT';
    var kc=v.fact_type==='kol_sentiment'?'#9333ea':'#0f766e';
    return '<div style="padding:10px 0;border-top:1px solid #f1f5f9">'
      + '<div style="display:flex;gap:7px;align-items:center;flex-wrap:wrap;margin-bottom:3px">'
      +   '<span style="font-size:9.5px;font-weight:800;color:#fff;background:'+kc+';border-radius:7px;padding:1px 7px;letter-spacing:.3px">'+kind+'</span>'+areaTag(v.area_id)+who
      +   '<span style="font-size:11px;color:#94a3b8;font-weight:600;margin-left:auto">'+esc(fmtDate(v.created_at))+'</span>'
      + '</div>'
      + '<div style="font-size:13px;color:'+(isQuote?'#1e293b':'#334155')+';line-height:1.6;'+(isQuote?'font-style:italic;border-left:3px solid '+kc+';padding-left:10px':'')+'">'+esc(txt)+' '+srcLink(v.source_url)+'</div>'
      + '</div>';
  }
  function sectionH(t,sub){ return '<div style="font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:.05em;color:#8595a6;margin:26px 0 8px">'+esc(t)+(sub?' <span style="color:#cbd5e1;font-weight:600;text-transform:none;letter-spacing:0">· '+esc(sub)+'</span>':'')+'</div>'; }

  window.__briefFilter=function(a){ _fArea=a; render(); };

  function render(){
    const root=document.getElementById('briefing-body'); if(!root) return;
    if(!_data){ root.innerHTML='<div style="color:#64748b;padding:40px;text-align:center">Loading briefing&hellip;</div>'; return; }
    const fa=function(x){ return _fArea? x.area_id===_fArea : true; };
    const cats=_data.cats.filter(fa), sigs=_data.sigs.filter(fa), facts=_data.facts.filter(fa), posters=(_data.posters||[]).filter(fa), voices=(_data.voices||[]).filter(fa);
    // freshness + filter chips
    const sub=document.getElementById('briefing-subtitle');
    if(sub) sub.textContent=sigs.length+' developments · '+cats.length+' upcoming catalysts · '+posters.length+' posters · '+voices.length+' voices · '+facts.length+' facts · Ailux focus areas';
    const fc=document.getElementById('briefing-filter');
    if(fc){ const present=AILUX.filter(function(a){ return _data.sigs.some(function(s){return s.area_id===a;})||_data.cats.some(function(c){return c.area_id===a;}); });
      function chip(lab,val,active){ return '<button onclick="window.__briefFilter('+(val===null?'null':"'"+val+"'")+')" style="cursor:pointer;font-size:11px;font-weight:700;padding:4px 11px;border-radius:14px;border:1px solid '+(active?'#0b5e52':'#cbd5e1')+';background:'+(active?'#0b5e52':'#fff')+';color:'+(active?'#fff':'#475569')+'">'+esc(lab)+'</button>'; }
      fc.innerHTML='<span style="font-size:11px;color:#94a3b8;font-weight:700;margin-right:2px">AREA</span>'+chip('All',null,_fArea===null)+present.map(function(a){return chip(AREA_LABEL[a]||a,a,_fArea===a);}).join(''); }

    let html='';
    if(cats.length){ html+=sectionH('Coming up','what research expects'); html+='<div style="background:#fff;border:1px solid #e6edf4;border-radius:13px;padding:4px 17px 12px">'+cats.slice(0,8).map(catItem).join('')+'</div>'; }
    html+=sectionH('Developments','what just moved — sourced');
    html+= sigs.length? sigs.map(sigCard).join('') : '<div style="color:#94a3b8;padding:20px;text-align:center;font-size:13px">No recent developments in this filter.</div>';
    if(voices.length){ html+=sectionH('KOL & industry voices','what people are saying — sourced quotes'); html+='<div style="background:#fff;border:1px solid #e6edf4;border-radius:13px;padding:4px 17px 12px">'+voices.slice(0,15).map(voiceCard).join('')+'</div>'; }
    if(posters.length){ html+=sectionH('Posters & presentations','what was shown — DDW / ECCO / EULAR / AAD / ATS …'); html+='<div style="background:#fff;border:1px solid #e6edf4;border-radius:13px;padding:4px 17px 12px">'+posters.slice(0,20).map(posterCard).join('')+'</div>'; }
    if(facts.length){ html+=sectionH('Latest facts','newest sourced intelligence'); html+='<div style="background:#fff;border:1px solid #e6edf4;border-radius:13px;padding:4px 17px 12px">'+facts.slice(0,25).map(factRow).join('')+'</div>'; }
    root.innerHTML=html;
  }

  async function load(){
    const root=document.getElementById('briefing-body'); if(!root) return;
    if(!_data) root.innerHTML='<div style="color:#64748b;padding:40px;text-align:center">Loading briefing&hellip;</div>';
    try{ _data=await fetchAll(); render(); }
    catch(e){ root.innerHTML='<div style="color:#b91c1c;padding:40px;text-align:center">Could not load briefing ('+esc(e.message)+')</div>'; }
  }
  if(typeof registerTab==='function') registerTab('briefing',{onEnter:load});
  window.__briefingRender=load;
})();
