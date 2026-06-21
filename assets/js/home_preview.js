/* ── Home Preview lens app (cowork 2026-06-06) ─────────────────────────────────
   Self-contained, namespaced (ml-), scoped under #ml-app. Registered via
   TAB_REGISTRY so any error is isolated. Live read via publishable key.
   Trust upgrade: narrative_provenance (claim→source) + narrative_claim_triangulation. */
(function(){
  const SB="https://tghntyofptvfhmtchwcv.supabase.co/rest/v1";
  const PUB="sb_publishable_3GLfZ7b9Tjp9RFRcc4YZew_ov-fY7dI";
  const HZ={headers:{apikey:PUB,Authorization:"Bearer "+PUB}};
  const Q=(t,p="")=>fetch(`${SB}/${t}?${p}`,HZ).then(r=>r.json());
  async function QALL(t,p=""){ let out=[],off=0; for(;;){ const b=await Q(t,`${p}${p?'&':''}limit=1000&offset=${off}`); if(!Array.isArray(b)||!b.length)break; out=out.concat(b); if(b.length<1000)break; off+=1000; } return out; }
  const TODAY=new Date();
  const ISO=TODAY.toISOString().slice(0,10);
  const E=s=>String(s==null?"":s).replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
  const fN=n=>n==null?"—":(n>=1e9?(n/1e9).toFixed(1)+"B":n>=1e6?(n/1e6).toFixed(1)+"M":n>=1e3?(n/1e3).toFixed(0)+"K":(""+n));
  const nc=s=>s>=9?"#b91c1c":s>=7?"#d97706":s>=5?"#ca8a04":"#16a34a";
  const dF=d=>Math.round((new Date(d)-TODAY)/864e5);
  const sc=s=>{s=(s||"").toLowerCase();return s.includes("approv")?"ml-app2":s.includes("3")?"ml-p3":s.includes("2")?"ml-p2":"ml-early";};
  const sr=s=>{s=(s||"").toLowerCase();return s.includes("approv")?0:s.includes("3")?1:s.includes("2")?2:s.includes("1")?3:4;};
  function mlMd(t){ if(!t)return"";let s=E(t);s=s.replace(/^_(.+?)_$/gm,'<i>$1</i>').replace(/\*\*(.+?)\*\*/g,'<b>$1</b>').replace(/\[(\d+)\]/g,'<span class="ml-cite">[$1]</span>');
    const L=s.split(/\n/);let o=[],il=false;
    for(let ln of L){ if(/^###\s+/.test(ln)){if(il){o.push('</ul>');il=false;}o.push('<h5>'+ln.replace(/^###\s+/,'')+'</h5>');}
      else if(/^#{1,2}\s+/.test(ln)){if(il){o.push('</ul>');il=false;}o.push('<h4>'+ln.replace(/^#{1,2}\s+/,'')+'</h4>');}
      else if(/^[-*]\s+/.test(ln)){if(!il){o.push('<ul>');il=true;}o.push('<li>'+ln.replace(/^[-*]\s+/,'')+'</li>');}
      else if(ln.trim()===''){if(il){o.push('</ul>');il=false;}}
      else{if(il){o.push('</ul>');il=false;}o.push('<p>'+ln+'</p>');} }
    if(il)o.push('</ul>');return o.join(''); }
  function fs(t){if(!t)return'';const s=t.replace(/^#.*$/gm,'').replace(/^_.*_$/gm,'').replace(/\[\d+\]/g,'').replace(/[*#]/g,'').trim();const m=s.match(/^.*?[.!?](\s|$)/);return (m?m[0]:s.slice(0,180)).trim();}

  const MAP={"Multiple Myeloma":["indication","multiple_myeloma"],"Severe Asthma":["indication","asthma"],"Hidradenitis Suppurativa":["indication","hs"],"Eosinophilic Esophagitis (EoE)":["indication","eoe"],"Generalized Myasthenia Gravis":["indication","gmg"],"Thyroid Eye Disease":["indication","ted"],"Crohn's Disease":["indication","cd"],"Psoriatic Arthritis":["indication","psa"],"Lupus Nephritis":["indication","lupus_nephritis"],"COPD (Type-2 / eosinophilic)":["indication","copd"],"Ulcerative Colitis":["indication","uc"],"Chronic Spontaneous Urticaria":["indication","chronic_urticaria"],"Chronic Rhinosinusitis with Nasal Polyps":["indication","crswnp"],"Atopic Dermatitis":["indication","ad"],"Sjögren's Disease":["indication","sjogrens"],"CIDP":["indication","cidp"],"Gastric/GEJ Adenocarcinoma - FGFR2b+":["indication","gastric_cancer"],"Plaque Psoriasis":["indication","psoriasis"],"Systemic Lupus Erythematosus (SLE)":["indication","sle"],"TSLP Target Area":["area","tslp"],"FcRn Target Area":["area","fcrn"],"IGF-1R Target Area":["area","igf1r"],"IL-4Rα Target Area":["area","il4ra"],"TL1A Target Area":["area","tl1a"],"IBD (Inflammatory Bowel Disease)":["area","ibd"],"Respiratory Diseases (Broad)":["area","respiratory"],"Autoimmune Diseases (Broad)":["area","autoimmune"],"IL-23 / IL-23p19 Target Area":["area","il23p19"]};
  const TGTS=[["tl1a","TL1A × IL-23p19"],["il23p19","IL-23p19"],["tslp","TSLP"],["il4ra","IL-4Rα"],["fcrn","FcRn"],["igf1r","IGF-1R"]];
  // ── Ailux relevance: the dashboard only surfaces these areas/targets + supporting CI ──
  const AILUX_AREAS=['tl1a','il23p19','tslp','il33','il4ra','ox40l','igf1r','tshr','ted','fcrn','tcell','bcma','cd19','ibd','autoimmune','respiratory','atopy'];
  const AREA_SET=new Set(AILUX_AREAS);
  const AILUX_TARGETS=new Set(['tl1a','il23p19','il-23p19','tslp','il33','il-33','il4ra','il-4ra','ox40l','igf1r','igf-1r','tshr','fcrn','bcma','cd19','cd3','cd3e','albumin']);
  const AREA_IN='area_id=in.('+AILUX_AREAS.join(',')+')';
  // Ailux disease spaces (I&I / autoimmune / respiratory / derm / TED) — excludes oncology etc.
  const AILUX_INDS=new Set(['uc','cd','ibd','ad','asthma','copd','ted','gmg','cidp','sle','sjogrens','lupus_nephritis','hs','crswnp','chronic_urticaria','psoriasis','psa','eoe','ssc','nmosd','itp','pemphigus']);
  const relInsight=refs=>{ try{ const ind=(refs&&refs.indications)||[]; if(ind.length) return ind.some(x=>AILUX_INDS.has(String(x).toLowerCase())); const t=(refs&&refs.targets)||[]; return t.some(x=>AILUX_TARGETS.has(String(x).toLowerCase())); }catch(e){ return false; } };
  let DB=null;

  window.mlInit=async function(){
    if(DB){return;} // load once
    const view=document.getElementById('ml-view'); if(!view)return;
    try{
      const CAT_F="label,sort_date,significance,is_key_watch,catalyst_type,area_id,drug_id,expected_impact,outcome_text,source_url";
      const [pi,tpp,drugs,treats,cats,catsPast,deals,nar,prov,tri,programs,insights,clinical,facts]=await Promise.all([
        Q("indication_patient_intelligence","select=indication_name,market_size_usd_bn,patient_count_us,patient_count_global,unmet_need_score,biologic_failure_rate_pct,remission_rate_soc_pct,why_it_matters"),
        Q("payer_tpp_criteria","select=indication_id,tpp_dimension,payer_willingness_to_pay,ailux_positioning,biologic_advantage_claim"),
        Q("drugs","select=id,name,display_name,stage,company_id,overlap,vs_ailux,differentiation_thesis,ailux_angle"),
        Q("entity_edges","select=subject_id,object_id&subject_type=eq.drug&predicate=eq.TREATS&object_type=eq.indication"),
        Q("catalysts",`select=${CAT_F}&sort_date=gte.${ISO}&${AREA_IN}&order=sort_date.asc&limit=120`),
        Q("catalysts",`select=${CAT_F}&sort_date=lt.${ISO}&${AREA_IN}&order=sort_date.desc&limit=40`),
        Q("deals","select=deal_date,headline,deal_type,strategic_signal,area_id&order=deal_date.desc&limit=60"),
        QALL("entity_narratives","select=id,entity_type,entity_id,section,body_md,confidence"),
        QALL("narrative_provenance","select=narrative_id,claim_text,source_url"),
        QALL("narrative_claim_triangulation","select=narrative_id,claims,multi_source_claims,triangulated_claims"),
        Q("asset_programs","select=program_code,target_pair_id,indication_lead,modality,status,differentiators&order=program_code.asc"),
        Q("strategic_insights","select=insight_type,title,detail,metric,entity_refs,confidence,created_at&order=created_at.desc&limit=200"),
        Q("drug_clinical_signals","select=drug_id,best_quality_tier,best_quality_score,n_rct,max_enrollment,any_discontinued,serious_ae_organ_classes,top_serious_organ,best_remission_pct&order=best_quality_score.desc.nullslast&limit=300"),
        QALL("intel_facts",`select=subject_id,subject_name,fact_type,claim,metric,value_text,source_url,area_id&${AREA_IN}`)
      ]);
      const factsBySubj={}; (facts||[]).forEach(f=>{ if(f.subject_id){(factsBySubj[f.subject_id]=factsBySubj[f.subject_id]||[]).push(f);} });
      const drugById={};drugs.forEach(d=>drugById[d.id]=d);
      const byInd={};treats.forEach(e=>{(byInd[e.object_id]=byInd[e.object_id]||[]).push(e.subject_id);});
      const tppBy={};tpp.forEach(t=>{(tppBy[t.indication_id]=tppBy[t.indication_id]||[]).push(t);});
      const ailuxIds=new Set(drugs.filter(d=>d.company_id==='ailux').map(d=>d.id));
      const narInd={},narTgt={};nar.forEach(n=>{const m=(n.entity_type==='indication'?narInd:n.entity_type==='target'?narTgt:null);if(m){(m[n.entity_id]=m[n.entity_id]||{})[n.section]={id:n.id,md:n.body_md,conf:n.confidence};}});
      const PROV={};prov.forEach(p=>{(PROV[p.narrative_id]=PROV[p.narrative_id]||[]).push(p);});
      const TRI={};tri.forEach(t=>{TRI[t.narrative_id]=t;});
      DB={pi,tppBy,drugById,byInd,cats,catsPast:catsPast||[],deals,ailuxIds,narInd,narTgt,PROV,TRI,programs:programs||[],insights:insights||[],clinical:clinical||[],factsBySubj};
      go('home');
    }catch(e){view.innerHTML='<div class="ml-err">Could not load: '+E(e.message)+'</div>';}
  };

  function trust(nar){
    if(!nar||!nar.id)return'';
    const tri=DB.TRI[nar.id],prov=DB.PROV[nar.id]||[];
    const withUrl=prov.filter(p=>p.source_url);
    const triLine=tri?`${tri.claims} claims · ${tri.multi_source_claims||0} corroborated by ≥2 independent sources`:`${prov.length} claims traced`;
    const rows=prov.slice(0,12).map(p=>`<div class="ml-src">${E((p.claim_text||'').slice(0,130))} ${p.source_url?`<a href="${E(p.source_url)}" target="_blank" rel="noopener">source ↗</a>`:'<span class="ml-int">internal</span>'}</div>`).join('');
    return `<details class="ml-trust"><summary>▸ Sources &amp; provenance — ${withUrl.length}/${prov.length} externally sourced</summary><div class="ml-tri">${triLine}</div>${rows}</details>`;
  }

  /* HOME — signal-first command center (MUI). Lead with what moved + Ailux watch; doors below. */
  function vHome(){
    const sigMod=s=>{s=(s||'').toLowerCase();return s.includes('high')?'low':s.includes('med')?'med':'neutral';};
    // top sourced fact for a drug_id (from intel_facts) — "what the research says", with its link
    const topFact=id=>{const f=((DB.factsBySubj||{})[id]||[])[0];if(!f)return'';return ` <span style="color:var(--mui-ink-2)">${E((f.claim||f.value_text||'').slice(0,150))}</span>${f.source_url?' '+MUI.link(f.source_url,'↗'):''}`;};
    // ── What moved: recent Ailux-relevant deals (deduped)
    const seenD=new Set();
    const moved=(DB.deals||[]).filter(x=>x.headline&&AREA_SET.has(x.area_id)&&!seenD.has(x.headline)&&seenD.add(x.headline)).slice(0,8).map(x=>MUI.row({name:E(x.headline),sub:E((x.deal_type||'deal')+(x.deal_date?' · '+x.deal_date:'')),right:MUI.pill('Deal','info')})).join('')||'<div class="ml-sub">No recent deals in your areas.</div>';
    // ── Recent readouts: PAST Ailux catalysts + what the data showed (outcome_text) + a sourced fact
    const readouts=(DB.catsPast||[]).filter(c=>AREA_SET.has(c.area_id))
      .sort((a,b)=>((b.outcome_text?1:0)-(a.outcome_text?1:0))||(new Date(b.sort_date)-new Date(a.sort_date)))
      .slice(0,8).map(c=>{
      const data=c.outcome_text?E(c.outcome_text):(c.expected_impact?'expected: '+E(String(c.expected_impact).slice(0,120)):'<span style="color:var(--mui-ink-3)">awaiting readout data</span>');
      const src=c.source_url?' '+MUI.link(c.source_url,'source ↗'):'';
      return MUI.row({name:E(c.label),sub:`${E(c.sort_date)} · ${data}${c.drug_id?topFact(c.drug_id):''}${src}`,right:c.significance?MUI.pill(c.significance,sigMod(c.significance)):''});
    }).join('')||'<div class="ml-sub">No recent readouts in your areas.</div>';
    // ── Strategic signals: high-value insight types AND Ailux-relevant (drops off-target + noise)
    const HV={patient_whitespace:'high',genetically_validated:'high',discontinuation_signal:'low',partnership_termination:'low',label_safety:'low',safety_burden:'low',readout_imminent:'med',exclusivity_cliff:'med',competitive_density:'med',china_blind_spot:'med',manufacturing_risk:'med',patent_fto:'med',deal_event:'info',ma_event:'info',acquisition_signal:'info',orphan_designation:'info',funding_momentum:'info',financing_signal:'info',conference_readout:'info'};
    const seenS=new Set();
    const sigs=(DB.insights||[]).filter(s=>HV[s.insight_type]&&relInsight(s.entity_refs)&&!seenS.has(s.title)&&seenS.add(s.title)).slice(0,9)
      .map(s=>MUI.row({name:E(s.title),sub:E((s.detail?String(s.detail).slice(0,150):(s.insight_type||'').replace(/_/g,' '))),right:MUI.pill((s.insight_type||'').replace(/_/g,' '),HV[s.insight_type])})).join('')||'<div class="ml-sub">No strategic signals in your areas.</div>';
    // ── Ailux watch: one scannable line per program
    const watch=(DB.programs||[]).map(p=>{
      const diffN=Array.isArray(p.differentiators)?p.differentiators.length:0;
      const tgt=(p.target_pair_id||'').replace(/-/g,' × ').toUpperCase();
      return MUI.row({name:E(p.program_code)+(tgt?` <span style="color:var(--mui-ink-3);font-weight:600">${E(tgt)}</span>`:''),
        sub:E([p.indication_lead,p.modality].filter(Boolean).join(' · ')||'—'),
        right:MUI.pill(p.status||'—','neutral')+(diffN?MUI.pill(diffN+' differentiators','info'):'')});
    }).join('')||'<div class="ml-sub">No Ailux programs.</div>';
    // ── Coming up: upcoming Ailux catalysts within a year, soonest first, with what the research expects
    const up=(DB.cats||[]).filter(c=>{const d=dF(c.sort_date);return d>=0&&d<=365;}).sort((a,b)=>new Date(a.sort_date)-new Date(b.sort_date)).slice(0,10).map(c=>{const d=dF(c.sort_date);
      const exp=c.expected_impact?` <span style="color:var(--mui-ink-2)">— expects: ${E(String(c.expected_impact).slice(0,140))}</span>`:'';
      return MUI.timelineItem({when:d<=0?'now':d+'d',what:E(c.label)+exp,meta:(c.significance?MUI.pill(c.significance,sigMod(c.significance)):'')+(c.is_key_watch?MUI.pill('key watch','med'):'')});
    }).join('')||'<div class="ml-sub">No upcoming catalysts in your areas.</div>';
    const L=[['__briefing__','📋','Executive Briefing','The full what\'s-happening feed — every development, catalyst, poster &amp; sourced fact across your areas.'],['commercial','💰','Commercial &amp; Market','Where the opening is — unmet population, remission ceiling, how each rival stacks vs Ailux, payer hurdle.'],['landscape','🧬','Scientific Landscapes','Cited competitive-science synthesis per target space + Meridian interpretation.'],['clinical','🧪','Clinical Evidence','Per-drug trial-evidence signals — design quality, safety breadth, remission — from the trial harvest.'],['catalysts','📈','Pipeline &amp; Catalysts','What is about to read out, file, or present — ranked, significance-tagged.'],['deals','🤝','Deal Activity','Recent licensing / M&amp;A / financings with the strategic read where we have one.']];
    return `<div class="ml-h2">Good morning. Here's what moved.</div><div class="ml-sub">Your 30-second glance across Ailux's areas — every item sourced. For the comprehensive feed open the <b>📋 Executive Briefing</b>; for the raw daily stream, <b>Reads</b>.</div>
      <div class="ml-sech">📊 Recent readouts — what the data showed</div><div class="mui-list">${readouts}</div>
      <div class="ml-sech">⚡ What moved — recent deals</div><div class="mui-list">${moved}</div>
      <div class="ml-sech">🔎 Strategic signals</div><div class="mui-list">${sigs}</div>
      <div class="ml-sech">🎯 Ailux watch</div><div class="mui-list">${watch}</div>
      <div class="ml-sech">⏱ Coming up — catalysts &amp; what research expects</div><div class="mui-list">${up}</div>
      <div class="ml-sech">Choose your lens</div><div class="ml-rg">${L.map(l=>`<div class="ml-rc" data-go="${l[0]}"><div class="ml-ic">${l[1]}</div><div class="ml-t">${l[2]}</div><div class="ml-d">${l[3]}</div></div>`).join('')}</div>`;
  }
  /* COMMERCIAL */
  function vComm(){return `<div class="ml-h2">Commercial &amp; Market</div><div class="ml-sub">Not the headline numbers your team already knows — the <b>cited read on where the opening actually is</b>. Each card opens to the Meridian analysis (with sources), the competitive field by how each rival stacks vs Ailux, the payer hurdle, and Ailux's own play.</div>
    <div class="ml-ctrls"><span>Sort</span><select id="ml-sort"><option value="market">Market size</option><option value="unmet">Unmet need</option><option value="patients">US patients</option><option value="comp">Competitive intensity</option></select>
    <label style="margin-left:8px"><input type="checkbox" id="ml-dis" checked/> Diseases only</label></div><div id="ml-cgrid"></div>`;}
  function rComm(){
    const sort=document.getElementById('ml-sort').value,dO=document.getElementById('ml-dis').checked;
    let rows=DB.pi.map(r=>{const m=MAP[r.indication_name]||[null,null];const id=m[1];const c=DB.byInd[id]||[];return{...r,_id:id,_k:m[0],_comp:m[0]==='indication'?c.length:null,_cids:c,_tpp:DB.tppBy[id]||[]};});
    if(dO)rows=rows.filter(r=>r._k==='indication');
    const key={market:r=>r.market_size_usd_bn||-1,unmet:r=>r.unmet_need_score||-1,patients:r=>r.patient_count_us||-1,comp:r=>r._comp||-1}[sort];
    rows.sort((a,b)=>key(b)-key(a));
    document.getElementById('ml-cgrid').innerHTML='<div class="ml-grid">'+rows.map(cCard).join('')+'</div>';
    document.querySelectorAll('#ml-cgrid .ml-c').forEach(c=>c.onclick=e=>{if(e.target.closest('a')||e.target.closest('details'))return;c.querySelector('.ml-det')?.classList.toggle('ml-open');});
  }
  function cCard(r){
    const need=r.unmet_need_score||0,mkt=r.market_size_usd_bn!=null?("$"+r.market_size_usd_bn+"B"):"—";
    const soc=r.remission_rate_soc_pct!=null?r.remission_rate_soc_pct+"%":"—",fail=r.biologic_failure_rate_pct!=null?r.biologic_failure_rate_pct+"%":"—";
    const nar=DB.narInd[r.indication_name]||{},intel=nar.intelligence,brief=nar.overview;
    const comps=(r._cids||[]).map(id=>DB.drugById[id]).filter(Boolean);
    const lead=comps.filter(d=>d.overlap==='Direct'||d.overlap==='Adjacent').sort((a,b)=>sr(a.stage)-sr(b.stage)).slice(0,6);
    const cHTML=lead.map(d=>{const j=d.vs_ailux||d.differentiation_thesis||d.ailux_angle||'';return `<div class="ml-ci"><span class="ml-ch">${E(d.display_name||d.name||d.id)}</span><span class="ml-sp ${sc(d.stage)}">${E(d.stage||'?')}</span>${j?`<div class="ml-cj">${E(String(j).slice(0,220))}</div>`:''}</div>`;}).join('')||'<div style="font-size:12px;color:#9aa8b6">No Direct/Adjacent competitors mapped.</div>';
    const ail=comps.filter(d=>DB.ailuxIds.has(d.id));
    const aHTML=ail.length?ail.map(d=>`<div class="ml-ax"><b>◆ Ailux — ${E(d.display_name||d.id)} (${E(d.stage||'?')})</b><div style="margin-top:4px">${E(String(d.differentiation_thesis||d.ailux_angle||d.vs_ailux||'Position tracked; thesis not yet written.').slice(0,300))}</div></div>`).join(''):'';
    const tp=r._tpp.find(t=>t.biologic_advantage_claim||t.ailux_positioning);
    const pHTML=tp?`<div class="ml-read" style="border-left-color:#d97706;background:#fffdf6;border-color:#f3e6c8">${tp.biologic_advantage_claim?'<b>To win reimbursement:</b> '+E(tp.biologic_advantage_claim):''}${tp.ailux_positioning?'<div style="margin-top:5px"><b>Ailux angle:</b> '+E(tp.ailux_positioning)+'</div>':''}${tp.payer_willingness_to_pay?'<div style="margin-top:5px;color:#5b6b7d">Payer willingness to pay: '+E(tp.payer_willingness_to_pay)+'</div>':''}</div>`:'<div style="font-size:12px;color:#9aa8b6">No payer/TPP criteria captured yet — collection gap.</div>';
    return `<div class="ml-c ml-clk"><div class="ml-top"><div class="ml-nm">${E(r.indication_name)}${r._k==='area'?'<span class="ml-tag">· target area</span>':''}</div><div style="text-align:right"><div style="font-size:18px;font-weight:800">${mkt}</div><div style="font-size:10px;color:#5b6b7d;text-transform:uppercase">market</div></div></div>
      <div class="ml-mx"><div class="ml-m"><div class="ml-mv">${fN(r.patient_count_us)}</div><div class="ml-mk">US patients</div></div><div class="ml-m"><div class="ml-mv" style="color:${nc(need)}">${need}/10</div><div class="ml-mk">Unmet need<div class="ml-bb"><div style="width:${need*10}%;background:${nc(need)}"></div></div></div></div><div class="ml-m"><div class="ml-mv">${soc}</div><div class="ml-mk">SoC remission ceiling</div></div><div class="ml-m"><div class="ml-mv">${fail}</div><div class="ml-mk">Biologic failure</div></div>${r._comp!=null?`<div class="ml-m"><div class="ml-mv">${r._comp}</div><div class="ml-mk">Competing drugs</div></div>`:''}</div>
      ${intel?`<div style="font-size:12px;color:#46586a;margin-top:9px;border-top:1px solid #f0f3f7;padding-top:9px"><b style="color:#1e527d">Meridian read:</b> ${E(fs(intel.md))} <span style="color:#9aa8b6">…click to expand</span></div>`:''}
      <div class="ml-det">
        ${intel?`<div class="ml-blk"><div class="ml-blkh">The opening — Meridian analysis</div><div class="ml-read">${mlMd(intel.md)}<div class="ml-prov">Confidence: ${E(intel.conf||'—')}</div>${trust(intel)}</div></div>`:''}
        <div class="ml-blk"><div class="ml-blkh">Competitive field — how it stacks vs Ailux</div>${cHTML}</div>
        ${aHTML?`<div class="ml-blk"><div class="ml-blkh">Ailux's play</div>${aHTML}</div>`:''}
        <div class="ml-blk"><div class="ml-blkh">Payer hurdle</div>${pHTML}</div>
        ${brief?`<div class="ml-blk"><div class="ml-blkh">Patient brief (who fails, who's left)</div><div class="ml-read">${mlMd(brief.md)}${trust(brief)}</div></div>`:''}
      </div></div>`;
  }
  /* LANDSCAPES */
  function vLand(){
    const cards=TGTS.map(([slug,label])=>{const n=DB.narTgt[slug]||{};if(!n.overview&&!n.intelligence)return'';
      return `<div class="ml-c"><div class="ml-nm" style="margin-bottom:8px">${E(label)}${slug==='tl1a'?' <span class="ml-tag">· Ailux lead space</span>':''}</div>
        ${n.overview?`<div class="ml-blk"><div class="ml-blkh">Competitive landscape (cited)</div><div class="ml-read">${mlMd(n.overview.md)}<div class="ml-prov">Confidence: ${E(n.overview.conf||'—')}</div>${trust(n.overview)}</div></div>`:''}
        ${n.intelligence?`<div class="ml-blk"><div class="ml-blkh">Meridian interpretation</div><div class="ml-read" style="border-left-color:#6d28d9;background:#faf8ff;border-color:#e8def9">${mlMd(n.intelligence.md)}${trust(n.intelligence)}</div></div>`:''}
        ${n.business?`<div class="ml-blk"><div class="ml-blkh">Strategic BD brief</div><div class="ml-read" style="border-left-color:#16a34a;background:#f4fbf6;border-color:#d6efdd">${mlMd(n.business.md)}${trust(n.business)}</div></div>`:''}
      </div>`;}).join('');
    return `<div class="ml-h2">Scientific Landscapes</div><div class="ml-sub">The cited competitive-science synthesis per target space — field size, clinical leaders, architecture, and the Meridian interpretation. Every block opens to its sources.</div><div class="ml-grid">${cards}</div>`;
  }
  /* CATALYSTS */
  function vCat(){
    const sig=s=>{s=(s||'').toLowerCase();return s.includes('high')?'ml-sh':s.includes('med')?'ml-sm':'ml-sl';};
    const items=DB.cats.slice().sort((a,b)=>new Date(a.sort_date)-new Date(b.sort_date)).map(c=>{const d=dF(c.sort_date);return `<div class="ml-c"><div class="ml-when">${d<=0?'now':d+'d'}<small>${E(c.sort_date)}</small></div><div style="flex:1;font-size:12.5px;line-height:1.45">${E(c.label)}<div style="margin-top:4px">${c.significance?`<span class="ml-sig ${sig(c.significance)}">${E(c.significance)}</span>`:''}${c.is_key_watch?' <span class="ml-pill" style="background:#fde68a;color:#92400e">key watch</span>':''}${c.catalyst_type?` <span style="font-size:11px;color:#9aa8b6">${E(c.catalyst_type)}</span>`:''}</div></div></div>`;}).join('');
    return `<div class="ml-h2">Pipeline &amp; Catalysts</div><div class="ml-sub">Everything about to read out, file, or present — soonest first, tagged by significance.</div><div class="ml-grid ml-feed">${items||'No upcoming catalysts.'}</div>`;
  }
  /* DEALS */
  function vDeal(){
    const items=DB.deals.map(x=>`<div class="ml-c" style="display:block"><div style="display:flex;gap:13px;align-items:baseline"><div style="font-size:11px;color:#5b6b7d;min-width:82px">${E(x.deal_date)}<br><span style="font-weight:700;color:#1e527d">${E(x.deal_type||'')}</span></div><div style="font-size:12.5px;line-height:1.45;flex:1">${E(x.headline)}</div></div>${x.strategic_signal?`<div class="ml-signal">↳ <b>Read:</b> ${E(x.strategic_signal)}</div>`:''}</div>`).join('');
    return `<div class="ml-h2">Deal Activity</div><div class="ml-sub">Recent licensing, M&amp;A and financings — with the strategic read where Meridian has one.</div><div class="ml-grid ml-feed">${items}</div>`;
  }
  /* CLINICAL EVIDENCE — per-drug signals from drug_clinical_signals (MUI) */
  function vClinical(){
    const sig=(DB.clinical||[]).slice().sort((a,b)=>(b.best_quality_score||0)-(a.best_quality_score||0));
    if(!sig.length)return `<div class="ml-h2">Clinical Evidence</div><div class="ml-sub">No clinical signals computed yet.</div>`;
    const rows=sig.map(r=>{
      const d=DB.drugById[r.drug_id],nm=d?(d.display_name||d.name||d.id):r.drug_id;const bits=[];
      if(r.n_rct)bits.push(r.n_rct+' RCT'+(r.n_rct>1?'s':''));
      if(r.max_enrollment)bits.push('largest n='+fN(r.max_enrollment));
      if(r.serious_ae_organ_classes)bits.push(r.serious_ae_organ_classes+' serious-AE organ classes'+(r.top_serious_organ?' ('+r.top_serious_organ+')':''));
      if(r.best_remission_pct!=null)bits.push('remission '+Number(r.best_remission_pct).toFixed(0)+'%');
      if(r.any_discontinued)bits.push('⚠ trial discontinued');
      return MUI.row({name:E(nm),sub:E(bits.join(' · ')||'evidence tracked'),right:r.best_quality_tier?MUI.qualityPill(r.best_quality_tier+(r.best_quality_score!=null?' '+Number(r.best_quality_score).toFixed(0):'')):''});
    }).join('');
    return `<div class="ml-h2">Clinical Evidence</div><div class="ml-sub">Per-drug signals derived from the clinical-trial harvest — trial-design quality, serious-AE breadth, remission outcomes — pre-aggregated from <code>drug_clinical_signals</code>, refreshed weekly. ${sig.length} drugs with signals; each shows only where the data exists.</div><div class="mui-list">${rows}</div>`;
  }
  const V={home:vHome,commercial:vComm,landscape:vLand,clinical:vClinical,catalysts:vCat,deals:vDeal};
  function go(lens){
    document.querySelectorAll('#ml-app .ml-lb').forEach(b=>b.classList.toggle('ml-on',b.dataset.lens===lens));
    document.getElementById('ml-view').innerHTML=V[lens]();
    if(lens==='commercial'){rComm();document.getElementById('ml-sort').onchange=rComm;document.getElementById('ml-dis').onchange=rComm;}
    if(lens==='home'){document.querySelectorAll('#ml-app .ml-rc').forEach(c=>c.onclick=()=>{ if(c.dataset.go==='__briefing__'){ if(typeof navTo==='function') navTo('briefing'); return; } go(c.dataset.go); });}
    const f=document.getElementById('ml-foot');if(f)f.innerHTML='Live preview · reads the same Supabase as the dashboard (publishable key, read-only) · cited narratives + per-claim provenance from narrative_provenance / triangulation. Nothing here is saved to your view yet.';
  }
  // wire lens buttons once DOM is present
  document.addEventListener('click',function(ev){const b=ev.target.closest('#ml-app .ml-lb');if(b)go(b.dataset.lens);});
  if(typeof registerTab==='function') registerTab('homeprev',{onEnter(){window.mlInit&&window.mlInit();}});
})();
