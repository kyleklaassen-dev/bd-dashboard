/* ── INTELLIGENCE TAB (intel2) — self-contained, namespaced, error-isolated ──
   Registered via TAB_REGISTRY so any failure stays inside this tab. Reads via
   the existing publishable/anon key (SUPABASE_ANON). No service_role. No writes.
   Added 2026-06-15. */
(function(){
  const SB  = (typeof SUPABASE_URL!=='undefined'?SUPABASE_URL:'https://tghntyofptvfhmtchwcv.supabase.co')+'/rest/v1';
  const KEY = (typeof SUPABASE_ANON!=='undefined'?SUPABASE_ANON:'');
  const HZ  = { headers:{ apikey:KEY, Authorization:'Bearer '+KEY } };
  const E = s => String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  // Single page (capped) — for ordered/top-N sections.
  const Q = (t,p='') => fetch(`${SB}/${t}?${p}`,HZ).then(r=>r.ok?r.json():[]).catch(()=>[]);
  // Full pagination — for tables read in bulk (>1000 rows possible).
  async function QALL(t,p=''){ let out=[],off=0; for(;;){ const b=await Q(t,`${p}${p?'&':''}limit=1000&offset=${off}`); if(!Array.isArray(b)||!b.length)break; out=out.concat(b); if(b.length<1000)break; off+=1000; if(off>20000)break; } return out; }
  const fNum = n => n==null?'—':(n>=1e9?(n/1e9).toFixed(1)+'B':n>=1e6?(n/1e6).toFixed(1)+'M':n>=1e3?(n/1e3).toFixed(0)+'K':(''+n));
  const tier = t => { t=(t||'').toLowerCase(); return t.includes('high')?'t-high':t.includes('med')?'t-med':t.includes('low')?'t-low':'t-info'; };

  let DB=null, LOADING=false, CUR='insights';

  function setSec(sec){
    CUR=sec;
    document.querySelectorAll('#intel2-nav .intel2-navbtn').forEach(b=>b.classList.toggle('intel2-on',b.dataset.sec===sec));
    document.querySelectorAll('#intel2-body .intel2-sec').forEach(s=>s.classList.toggle('intel2-show',s.id==='intel2-sec-'+sec));
  }

  /* ── Section renderers (each returns an HTML string) ── */

  // 1. Strategic insights — ranked, grouped by type.
  function rInsights(){
    const rows=(DB.insights||[]);
    if(!rows.length) return '<div class="intel2-muted">No strategic insights found.</div>';
    const byType={}; rows.forEach(r=>{(byType[r.insight_type]=byType[r.insight_type]||[]).push(r);});
    const order=Object.keys(byType).sort((a,b)=>byType[b].length-byType[a].length);
    const cards=order.map(tp=>{
      const items=byType[tp].slice(0,8).map(r=>`<div class="intel2-row"><div><div class="intel2-nm">${E(r.title||'(untitled)')}</div>${r.detail?`<div class="intel2-sub">${E(String(r.detail).slice(0,220))}</div>`:''}${r.metric?`<div class="intel2-sub" style="color:#138073">${E(String(r.metric).slice(0,120))}</div>`:''}</div><div class="intel2-spacer"></div>${r.confidence?`<span class="intel2-pill ${tier(r.confidence)}">${E(r.confidence)}</span>`:''}</div>`).join('');
      return `<div class="intel2-card"><div class="intel2-sech">${E(tp.replace(/_/g,' '))} <span class="intel2-count">${byType[tp].length}</span></div>${items}${byType[tp].length>8?`<div class="intel2-sub" style="margin-top:6px">+ ${byType[tp].length-8} more</div>`:''}</div>`;
    }).join('');
    return `<div class="intel2-subh">${rows.length} derived cross-table insights the platform produced — grouped by type, most-populated first. Each carries its <code>metric</code> and source tables.</div>${cards}`;
  }

  // 2. Genetic validation — target_disease_assoc (richer, 1537) + target_genetics (gnomAD constraint).
  function rGenetics(){
    const tda=(DB.tda||[]).filter(r=>r.genetic_association_score!=null).sort((a,b)=>b.genetic_association_score-a.genetic_association_score);
    const tg=(DB.tgen||[]).filter(r=>r.constraint_type==='lof');
    const assocRows=tda.slice(0,60).map(r=>{const g=r.genetic_association_score||0;return `<div class="intel2-row"><div class="intel2-nm">${E(r.symbol||'?')}</div><div class="intel2-sub">→ ${E(r.indication_name||r.efo_name||'')}</div><div class="intel2-spacer"></div><span class="intel2-bar"><i style="width:${(g*100).toFixed(0)}%"></i></span><span class="intel2-sub">${g.toFixed(2)} genetic</span>${r.overall_score!=null?`<span class="intel2-pill t-info">overall ${Number(r.overall_score).toFixed(2)}</span>`:''}</div>`;}).join('')||'<div class="intel2-muted">No scored associations.</div>';
    const lofRows=tg.slice(0,40).map(r=>`<div class="intel2-row"><div class="intel2-nm">${E(r.symbol||'?')}</div><div class="intel2-sub">o/e ${r.oe!=null?Number(r.oe).toFixed(2):'—'} (LoF intolerance)</div><div class="intel2-spacer"></div>${r.source_url?`<a class="intel2-a" href="${E(r.source_url)}" target="_blank" rel="noopener">source ↗</a>`:`<span class="intel2-sub">${E(r.source||'')}</span>`}</div>`).join('')||'<div class="intel2-muted">No gnomAD constraint rows.</div>';
    return `<div class="intel2-subh">Genetic backbone for "is the science real?". <b>Open Targets disease association</b> (<code>target_disease_assoc</code>, 1,537 rows — the richer table; the queried 600-row <code>target_disease_associations</code> is the thinner duplicate) ranked by genetic association score, plus <b>gnomAD loss-of-function constraint</b> (<code>target_genetics</code>) — low observed/expected = intolerant to LoF = a more druggable, validated target.</div>
      <div class="intel2-grid">
        <div class="intel2-card"><div class="intel2-sech">Target → disease, by genetic association <span class="intel2-count">top ${Math.min(60,tda.length)} / ${tda.length}</span></div>${assocRows}</div>
        <div class="intel2-card"><div class="intel2-sech">LoF intolerance (gnomAD) <span class="intel2-count">${tg.length} targets</span></div>${lofRows}</div>
      </div>`;
  }

  // 3. Trial-design quality — believability tiers.
  function rTrials(){
    let rows=(DB.tdq||[]).slice();
    const tiers={high:0,medium:0,low:0,other:0}; rows.forEach(r=>{const t=(r.quality_tier||'').toLowerCase();tiers[t==='high'?'high':t==='medium'||t==='med'?'medium':t==='low'?'low':'other']++;});
    rows.sort((a,b)=>(b.quality_score||0)-(a.quality_score||0));
    const list=rows.slice(0,80).map(r=>{
      const flags=[r.randomized?'randomized':null,r.controlled?'controlled':null].filter(Boolean).join(' · ')||'open / single-arm';
      return `<div class="intel2-row"><div><div class="intel2-nm">${r.nct_id?`<a class="intel2-a" href="https://clinicaltrials.gov/study/${E(r.nct_id)}" target="_blank" rel="noopener">${E(r.nct_id)}</a>`:'(no NCT)'}</div><div class="intel2-sub">${E(flags)}${r.enrollment?` · n=${fNum(r.enrollment)}`:''}${r.why_stopped?` · ⚠ ${E(String(r.why_stopped).slice(0,80))}`:''}</div></div><div class="intel2-spacer"></div>${r.quality_score!=null?`<span class="intel2-sub">${r.quality_score}</span>`:''}<span class="intel2-pill ${tier(r.quality_tier)}">${E(r.quality_tier||'—')}</span></div>`;
    }).join('')||'<div class="intel2-muted">No trial-design rows.</div>';
    return `<div class="intel2-subh">Separates real evidence from open-label noise — <code>trial_design_quality</code> scores each trial (randomized / controlled / model / endpoint count) into a believability tier. ${rows.length} trials scored: <b>${tiers.high} high</b> · ${tiers.medium} medium · ${tiers.low} low.</div>
      <div class="intel2-card"><div class="intel2-sech">Trials by quality score <span class="intel2-count">top ${Math.min(80,rows.length)} / ${rows.length}</span></div>${list}</div>`;
  }

  // 4. Conference / late-breaker signals.
  function rConf(){
    let rows=(DB.cas||[]).slice().sort((a,b)=>(b.signal_score||0)-(a.signal_score||0));
    const lb=rows.filter(r=>r.is_late_breaker).length, rd=rows.filter(r=>r.is_clinical_readout).length;
    const list=rows.slice(0,80).map(r=>{
      const dir=(r.result_direction||'').toLowerCase();
      const dpill=dir.includes('pos')?'t-high':dir.includes('neg')?'t-low':dir.includes('mix')?'t-med':'t-info';
      return `<div class="intel2-row"><div><div class="intel2-nm">${E(String(r.title||'(untitled)').slice(0,160))}</div><div class="intel2-sub">${E(r.conference||'')}${r.conference_year?' '+E(r.conference_year):''}${r.readout_phase?' · '+E(r.readout_phase):''}${r.is_late_breaker?' · 🔴 late-breaker':''}</div></div><div class="intel2-spacer"></div>${r.result_direction?`<span class="intel2-pill ${dpill}">${E(r.result_direction)}</span>`:''}${r.signal_score!=null?`<span class="intel2-sub">sig ${r.signal_score}</span>`:''}${r.source_url?`<a class="intel2-a" href="${E(r.source_url)}" target="_blank" rel="noopener">↗</a>`:''}</div>`;
    }).join('')||'<div class="intel2-muted">No conference signals.</div>';
    return `<div class="intel2-subh">The early-warning layer — <code>conference_abstract_signals</code> (the derived <i>signal</i> table, distinct from the raw <code>conference_abstracts</code> titles already shown elsewhere): late-breaker flag, readout phase, result direction and a signal score. ${rows.length} signals · ${lb} late-breakers · ${rd} clinical readouts.</div>
      <div class="intel2-card"><div class="intel2-sech">Signals by score <span class="intel2-count">top ${Math.min(80,rows.length)} / ${rows.length}</span></div>${list}</div>`;
  }

  // 5. EU approvals + US lag.
  function rEu(){
    let rows=(DB.eu||[]).slice().sort((a,b)=>String(b.eu_auth_date||'').localeCompare(String(a.eu_auth_date||'')));
    const list=rows.map(r=>{
      const lag=r.eu_vs_us_lag_days;
      const lagTxt=lag==null?'—':lag>0?`EU +${lag}d after US`:lag<0?`EU ${Math.abs(lag)}d before US`:'same day';
      const lagPill=lag==null?'t-info':lag>180?'t-low':lag>0?'t-med':'t-high';
      return `<div class="intel2-row"><div><div class="intel2-nm">${E(r.brand_name||r.ema_medicine_name||r.inn||'?')}${r.inn&&r.brand_name?` <span class="intel2-sub">(${E(r.inn)})</span>`:''}</div><div class="intel2-sub">EU auth ${E(r.eu_auth_date||'—')}${r.mah?' · '+E(r.mah):''}${r.is_biosimilar?' · biosimilar':''}</div></div><div class="intel2-spacer"></div><span class="intel2-pill ${lagPill}">${E(lagTxt)}</span>${r.ema_product_url?`<a class="intel2-a" href="${E(r.ema_product_url)}" target="_blank" rel="noopener">EMA ↗</a>`:''}</div>`;
    }).join('')||'<div class="intel2-muted">No EU approvals.</div>';
    return `<div class="intel2-subh">The ex-US regulatory picture — <code>eu_approvals</code> (EMA dates, marketing-authorization holder, biosimilar flag) and the EU-vs-US lag in days. ${rows.length} approvals mapped.</div>
      <div class="intel2-card"><div class="intel2-sech">EU approvals, newest first <span class="intel2-count">${rows.length}</span></div>${list}</div>`;
  }

  // 6. Manufacturing / supply-deal candidates.
  function rMfg(){
    const all=(DB.mfg||[]);
    const cand=all.filter(r=>r.is_supplies_candidate);
    const inhouse=all.filter(r=>r.is_inhouse).length;
    const candRows=cand.map(r=>`<div class="intel2-row"><div><div class="intel2-nm">${E(r.drug_name||r.brand_name||'?')}</div><div class="intel2-sub">${E(r.manufacturer_name||'—')}${r.establishment_type?' · '+E(r.establishment_type):''}</div></div><div class="intel2-spacer"></div>${r.is_inhouse?'<span class="intel2-pill t-info">in-house</span>':'<span class="intel2-pill t-high">supply candidate</span>'}${r.source_url?`<a class="intel2-a" href="${E(r.source_url)}" target="_blank" rel="noopener">↗</a>`:''}</div>`).join('')||'<div class="intel2-muted">No supply-deal candidates flagged.</div>';
    const allRows=all.slice(0,60).map(r=>`<div class="intel2-row"><div class="intel2-nm">${E(r.drug_name||r.brand_name||'?')}</div><div class="intel2-sub">${E(r.manufacturer_name||'—')}</div><div class="intel2-spacer"></div>${r.is_inhouse?'<span class="intel2-pill t-info">in-house</span>':'<span class="intel2-pill t-med">external CDMO</span>'}</div>`).join('');
    return `<div class="intel2-subh">A make-vs-buy / CDMO deal vector nothing else exposes — <code>manufacturing_sites</code> (FDA establishment, in-house flag). The <code>is_supplies_candidate</code> flag is a ready-made BD list. ${all.length} sites · ${inhouse} in-house · <b>${cand.length} supply-deal candidates</b>.</div>
      <div class="intel2-grid">
        <div class="intel2-card"><div class="intel2-sech">🎯 Supply-deal candidates <span class="intel2-count">${cand.length}</span></div>${candRows}</div>
        <div class="intel2-card"><div class="intel2-sech">All manufacturing sites <span class="intel2-count">${Math.min(60,all.length)} / ${all.length}</span></div>${allRows}</div>
      </div>`;
  }

  // 7. Narrative trust — RELINKED from the retired changes-feed tab.
  //    narrative_provenance (claim→source) + narrative_claim_triangulation (independence).
  function rTrust(){
    const prov=(DB.prov||[]), tri=(DB.tri||[]);
    if(!prov.length && !tri.length) return '<div class="intel2-muted">No narrative trust data found.</div>';
    const triByNar={}; tri.forEach(t=>{triByNar[t.narrative_id]=t;});
    const provByNar={}; prov.forEach(p=>{(provByNar[p.narrative_id]=provByNar[p.narrative_id]||[]).push(p);});
    const totalClaims=tri.reduce((s,t)=>s+(t.claims||0),0);
    const totalCorrob=tri.reduce((s,t)=>s+(t.multi_source_claims||0),0);
    const withUrl=prov.filter(p=>p.source_url).length;
    // Show the most-corroborated narratives first.
    const narIds=Object.keys(provByNar).sort((a,b)=>((triByNar[b]?.multi_source_claims||0)-(triByNar[a]?.multi_source_claims||0))||(provByNar[b].length-provByNar[a].length));
    const cards=narIds.slice(0,40).map(nid=>{
      const ps=provByNar[nid], t=triByNar[nid];
      const triLine=t?`${t.claims||ps.length} claims · ${t.multi_source_claims||0} corroborated by ≥2 independent sources · ${t.triangulated_claims||0} triangulated`:`${ps.length} claims traced`;
      const srcRows=ps.slice(0,12).map(p=>`<div class="intel2-src">${E(String(p.claim_text||'').slice(0,150))} ${p.source_url?`<a class="intel2-a" href="${E(p.source_url)}" target="_blank" rel="noopener">source ↗</a>`:'<span class="intel2-int">internal</span>'}</div>`).join('');
      const ext=ps.filter(p=>p.source_url).length;
      return `<details class="intel2-card intel2-trust"><summary>Narrative ${E(nid)} — ${ext}/${ps.length} externally sourced</summary><div class="intel2-tri">${triLine}</div>${srcRows}</details>`;
    }).join('');
    return `<div class="intel2-subh">The "trusted intelligence, not AI summaries" layer — relinked from the retired changes-feed tab. <code>narrative_provenance</code> traces each claim to its source; <code>narrative_claim_triangulation</code> records how many claims are independently corroborated. Across the corpus: <b>${fNum(prov.length)}</b> claim-source rows (${fNum(withUrl)} externally sourced) · <b>${fNum(totalClaims)}</b> claims · <b>${fNum(totalCorrob)}</b> corroborated by ≥2 sources.</div>${cards||'<div class="intel2-muted">No per-narrative provenance.</div>'}`;
  }

  // 8. KOL influence — kols ranked by influence_score (trial + publication weighted).
  function rKols(){
    let rows=(DB.kols||[]).slice().filter(r=>r.influence_score!=null).sort((a,b)=>(b.influence_score||0)-(a.influence_score||0));
    if(!rows.length) rows=(DB.kols||[]).slice().sort((a,b)=>(b.trial_count||0)-(a.trial_count||0));
    if(!rows.length) return '<div class="intel2-muted">No KOL data found.</div>';
    const pis=rows.filter(r=>(r.role||'').toUpperCase().includes('INVESTIGATOR')).length;
    const km=(DB.kolm||[]);
    const list=rows.slice(0,80).map(r=>{
      const inf=r.influence_score||0;
      const meta=[r.role?E(r.role.replace(/_/g,' ').toLowerCase()):null,r.trial_count?`${r.trial_count} trial${r.trial_count>1?'s':''}`:null,r.pub_count?`${fNum(r.pub_count)} pubs`:null,r.citation_count?`${fNum(r.citation_count)} cites`:null,r.h_index!=null?`h-index ${r.h_index}`:null].filter(Boolean).join(' · ');
      return `<div class="intel2-row"><div><div class="intel2-nm">${E(r.name||'?')}</div><div class="intel2-sub">${meta||'—'}</div></div><div class="intel2-spacer"></div><span class="intel2-bar"><i style="width:${Math.min(100,inf*100).toFixed(0)}%"></i></span><span class="intel2-sub">${inf.toFixed(2)} influence</span></div>`;
    }).join('')||'<div class="intel2-muted">No ranked KOLs.</div>';
    const kmRows=km.slice(0,8).map(r=>`<div class="intel2-row"><div class="intel2-nm">${E(r.kol_name||'?')}</div><div class="intel2-sub">h-index ${r.h_index!=null?r.h_index:'—'} · ${fNum(r.citation_count)} cites · ${fNum(r.paper_count)} papers</div><div class="intel2-spacer"></div>${r.source_url?`<a class="intel2-a" href="${E(r.source_url)}" target="_blank" rel="noopener">↗</a>`:''}</div>`).join('');
    const kmCard=km.length?`<div class="intel2-card"><div class="intel2-sech">Semantic Scholar bibliometrics <span class="intel2-count">${km.length}</span></div>${kmRows}</div>`:'';
    return `<div class="intel2-subh">Who moves the field — <code>kols</code> ranks principal investigators &amp; authors by an <b>influence score</b> blending trial leadership, citations and h-index (formula v136). ${rows.length} KOLs · ${pis} principal investigators. The score is the BD layer for "who do we need on the advisory board?".</div>
      <div class="intel2-card"><div class="intel2-sech">KOLs by influence <span class="intel2-count">top ${Math.min(80,rows.length)} / ${rows.length}</span></div>${list}</div>${kmCard}`;
  }

  // 9. Grant funding — NIH/agency awards mapped to target / indication.
  function rGrants(){
    const rows=(DB.grants||[]).slice();
    if(!rows.length) return '<div class="intel2-muted">No grant data found.</div>';
    const total=rows.reduce((a,r)=>a+(Number(r.award_amount)||0),0);
    // Aggregate by indication.
    const byInd={}; rows.forEach(r=>{const k=r.matched_indication||r.matched_target||'unmatched'; (byInd[k]=byInd[k]||{n:0,amt:0}); byInd[k].n++; byInd[k].amt+=Number(r.award_amount)||0;});
    const indOrder=Object.keys(byInd).sort((a,b)=>byInd[b].amt-byInd[a].amt).slice(0,18);
    const aggRows=indOrder.map(k=>`<div class="intel2-row"><div class="intel2-nm">${E(k)}</div><div class="intel2-sub">${byInd[k].n} grant${byInd[k].n>1?'s':''}</div><div class="intel2-spacer"></div><span class="intel2-pill t-info">$${fNum(byInd[k].amt)}</span></div>`).join('');
    // Top individual awards.
    const top=rows.slice().sort((a,b)=>(Number(b.award_amount)||0)-(Number(a.award_amount)||0)).slice(0,60);
    const topRows=top.map(r=>{
      const meta=[r.org_name?E(r.org_name):null,r.pi_names?'PI '+E(r.pi_names):null,r.agency?E(r.agency):null,r.fiscal_year?'FY'+E(r.fiscal_year):null,r.matched_indication?'→ '+E(r.matched_indication):null,r.matched_target?'· '+E(r.matched_target):null].filter(Boolean).join(' · ');
      const url=r.project_url||r.source_url;
      return `<div class="intel2-row"><div><div class="intel2-nm">${E(String(r.title||'(untitled grant)').slice(0,140))}</div><div class="intel2-sub">${meta||'—'}</div></div><div class="intel2-spacer"></div><span class="intel2-pill t-high">$${fNum(Number(r.award_amount)||0)}</span>${url?`<a class="intel2-a" href="${E(url)}" target="_blank" rel="noopener">↗</a>`:''}</div>`;
    }).join('')||'<div class="intel2-muted">No awards.</div>';
    return `<div class="intel2-subh">Where the public money is going — <code>grants</code> maps NIH/agency awards to targets &amp; indications. ${rows.length} grants · <b>$${fNum(total)}</b> total funding across the disease scope. A leading indicator of academic momentum behind a mechanism.</div>
      <div class="intel2-grid">
        <div class="intel2-card"><div class="intel2-sech">Funding by indication / target <span class="intel2-count">top ${indOrder.length}</span></div>${aggRows}</div>
        <div class="intel2-card"><div class="intel2-sech">Largest individual awards <span class="intel2-count">top ${Math.min(60,top.length)} / ${rows.length}</span></div>${topRows}</div>
      </div>`;
  }

  // 10. Corporate ownership — company_ownership parent→sub chains (GLEIF LEI).
  function rOwnership(){
    const rows=(DB.own||[]);
    if(!rows.length) return '<div class="intel2-muted">No ownership data found.</div>';
    // Group by company_id; prefer ultimate_parent when present.
    const byCo={}; rows.forEach(r=>{(byCo[r.company_id]=byCo[r.company_id]||[]).push(r);});
    const cos=Object.keys(byCo).sort();
    const list=cos.map(cid=>{
      const recs=byCo[cid];
      const ult=recs.find(r=>r.relationship_type==='ultimate_parent')||recs[0];
      const dir=recs.find(r=>r.relationship_type==='direct_parent');
      const parent=ult.parent_legal_name||(dir&&dir.parent_legal_name)||'—';
      const pid=ult.parent_company_id||(dir&&dir.parent_company_id);
      const isSelf=(parent||'').toLowerCase().replace(/[^a-z]/g,'').includes((cid||'').toLowerCase().replace(/[^a-z]/g,'').slice(0,5));
      const rel=isSelf?'standalone (self-parented)':'subsidiary of';
      const url=ult.source_url||(dir&&dir.source_url);
      return `<div class="intel2-row"><div><div class="intel2-nm">${E(cid)}</div><div class="intel2-sub">${E(rel)} ${E(parent)}${pid?` <span class="intel2-pill t-info">${E(pid)}</span>`:''}</div></div><div class="intel2-spacer"></div>${ult.confidence?`<span class="intel2-pill ${tier(ult.confidence==='confirmed'?'high':ult.confidence)}">${E(ult.confidence)}</span>`:''}${url?`<a class="intel2-a" href="${E(url)}" target="_blank" rel="noopener">GLEIF ↗</a>`:''}</div>`;
    }).join('');
    const named=cos.filter(c=>byCo[c].some(r=>r.parent_company_id)).length;
    return `<div class="intel2-subh">Who really owns whom — <code>company_ownership</code> resolves legal-entity parent chains from <b>GLEIF LEI</b> records (direct &amp; ultimate parent). Critical for BD: an asset's effective owner is the ultimate parent, not the operating subsidiary. ${cos.length} companies mapped · ${named} link to a known parent in the graph.</div>
      <div class="intel2-card"><div class="intel2-sech">Ownership chains <span class="intel2-count">${cos.length}</span></div>${list}</div>`;
  }

  // 11. Market & unmet need — indication_patient_intelligence (NEW panel; home cards untouched).
  function rMarket(){
    let rows=(DB.ipi||[]).slice().sort((a,b)=>(b.unmet_need_score||b.unmet_need_severity||0)-(a.unmet_need_score||a.unmet_need_severity||0));
    if(!rows.length) return '<div class="intel2-muted">No market / unmet-need data found.</div>';
    const list=rows.map(r=>{
      const un=r.unmet_need_score!=null?r.unmet_need_score:r.unmet_need_severity;
      const unPill=un==null?'t-info':un>=9?'t-low':un>=7?'t-med':'t-high';
      const meta=[r.simplified_label?E(r.simplified_label):null,r.patient_count_us!=null?`${fNum(r.patient_count_us)} US pts`:null,r.patient_count_global!=null?`${fNum(r.patient_count_global)} global`:null,r.market_size_usd_bn!=null?`$${Number(r.market_size_usd_bn).toFixed(1)}B mkt`:null,r.biologic_failure_rate_pct!=null?`${Number(r.biologic_failure_rate_pct).toFixed(0)}% biologic failure`:null].filter(Boolean).join(' · ');
      const srcs=Array.isArray(r.source_urls)?r.source_urls:[];
      const srcLink=srcs.length?`<a class="intel2-a" href="${E(srcs[0])}" target="_blank" rel="noopener">source ↗</a>`:'';
      const why=r.why_it_matters?`<details class="intel2-trust" style="margin-top:4px"><summary>why it matters</summary><div class="intel2-src">${E(String(r.why_it_matters).slice(0,400))}</div></details>`:'';
      return `<div class="intel2-card"><div class="intel2-row"><div><div class="intel2-nm">${E(r.indication_name||'?')}</div><div class="intel2-sub">${meta||'—'}</div></div><div class="intel2-spacer"></div>${un!=null?`<span class="intel2-pill ${unPill}">unmet ${un}/10</span>`:''}${srcLink}</div>${why}</div>`;
    }).join('');
    return `<div class="intel2-subh">Sizing the prize — <code>indication_patient_intelligence</code> ranks diseases by <b>unmet need</b> with patient counts, market size and biologic-failure rates. This is a NEW read of the same table; the homepage patient cards are unchanged. ${rows.length} indications profiled.</div>${list}`;
  }

  function rClinical(){
    const sig=DB.clinical||[], nameById=DB.nameById||{};
    if(!sig.length) return '<div class="intel2-muted">No clinical signals computed yet.</div>';
    const rows=sig.slice().sort((a,b)=>(b.best_quality_score||0)-(a.best_quality_score||0)).map(r=>{
      const nm=nameById[r.drug_id]||r.drug_id;
      const bits=[];
      if(r.n_rct) bits.push(r.n_rct+' RCT'+(r.n_rct>1?'s':''));
      if(r.max_enrollment) bits.push('largest n='+fNum(r.max_enrollment));
      if(r.serious_ae_organ_classes) bits.push(r.serious_ae_organ_classes+' serious-AE organ classes'+(r.top_serious_organ?' (top: '+E(r.top_serious_organ)+')':''));
      if(r.best_remission_pct!=null) bits.push('remission '+Number(r.best_remission_pct).toFixed(0)+'%');
      if(r.any_discontinued) bits.push('⚠ trial discontinued'+(r.why_stopped?': '+E(String(r.why_stopped).slice(0,60)):''));
      const right=r.best_quality_tier?`<span class="intel2-pill ${tier(r.best_quality_tier)}">${E(r.best_quality_tier)}${r.best_quality_score!=null?' '+Number(r.best_quality_score).toFixed(0):''}</span>`:'';
      return `<div class="intel2-row"><div><div class="intel2-nm">${E(nm)}</div><div class="intel2-sub">${bits.join(' · ')||'evidence tracked'}</div></div><div class="intel2-spacer"></div>${right}</div>`;
    }).join('');
    return `<div class="intel2-subh">Per-drug clinical-evidence signals from the CTGov harvest (<code>trial_design_quality</code>, <code>ct_trial_adverse_events</code>, <code>trial_outcome_measures</code>) — pre-aggregated into <code>drug_clinical_signals</code>, refreshed weekly. ${sig.length} drugs with signals; each signal shows only where the data exists (115 quality / 58 safety / 20 remission).</div>${rows}`;
  }

  const RENDER={insights:rInsights,clinical:rClinical,genetics:rGenetics,trials:rTrials,conf:rConf,eu:rEu,mfg:rMfg,trust:rTrust,kols:rKols,grants:rGrants,ownership:rOwnership,market:rMarket};

  function paint(){
    const body=document.getElementById('intel2-body'); if(!body) return;
    body.innerHTML=Object.keys(RENDER).map(sec=>`<div class="intel2-sec ${sec===CUR?'intel2-show':''}" id="intel2-sec-${sec}">${RENDER[sec]()}</div>`).join('');
    setSec(CUR);
    const f=document.getElementById('intel2-foot');
    if(f) f.innerHTML='Reads the same Supabase as the dashboard (publishable key, read-only). Source-bearing tables, surfaced 2026-06-15.';
  }

  window.intel2Init=async function(){
    if(DB||LOADING) { return; }
    LOADING=true;
    const body=document.getElementById('intel2-body');
    try{
      const [insights,tda,tgen,tdq,cas,eu,mfg,prov,tri,kols,kolm,grants,own,ipi,clin,drugs]=await Promise.all([
        Q('strategic_insights','select=insight_type,title,detail,metric,source_tables,confidence&order=created_at.desc&limit=1000'),
        Q('target_disease_assoc','select=symbol,indication_name,efo_name,overall_score,genetic_association_score&order=genetic_association_score.desc.nullslast&limit=1000'),
        Q('target_genetics','select=symbol,constraint_type,oe,score,source,source_url&limit=1000'),
        Q('trial_design_quality','select=nct_id,drug_id,randomized,controlled,intervention_model,enrollment,quality_score,quality_tier,why_stopped&order=quality_score.desc.nullslast&limit=1000'),
        Q('conference_abstract_signals','select=title,conference,conference_year,presentation_type,is_late_breaker,is_clinical_readout,readout_phase,result_direction,signal_score,source_url&order=signal_score.desc.nullslast&limit=1000'),
        Q('eu_approvals','select=inn,brand_name,ema_medicine_name,ema_product_url,eu_auth_date,mah,is_biosimilar,eu_vs_us_lag_days&limit=1000'),
        Q('manufacturing_sites','select=drug_name,brand_name,manufacturer_name,establishment_type,is_inhouse,is_supplies_candidate,source_url&limit=1000'),
        QALL('narrative_provenance','select=narrative_id,claim_text,source_url'),
        QALL('narrative_claim_triangulation','select=narrative_id,claims,multi_source_claims,triangulated_claims'),
        Q('kols','select=name,role,trial_count,pub_count,citation_count,h_index,influence_score&order=influence_score.desc.nullslast&limit=1000'),
        Q('kol_metrics','select=kol_name,h_index,citation_count,paper_count,source_url&order=h_index.desc.nullslast&limit=1000'),
        QALL('grants','select=title,pi_names,org_name,fiscal_year,award_amount,agency,matched_target,matched_indication,project_url,source_url,confidence'),
        Q('company_ownership','select=company_id,relationship_type,parent_legal_name,parent_company_id,source_url,confidence&limit=1000'),
        Q('indication_patient_intelligence','select=indication_name,simplified_label,patient_count_us,patient_count_global,market_size_usd_bn,unmet_need_score,unmet_need_severity,biologic_failure_rate_pct,why_it_matters,source_urls&order=unmet_need_score.desc.nullslast&limit=1000'),
        Q('drug_clinical_signals','select=drug_id,best_quality_tier,best_quality_score,n_rct,total_trials_scored,max_enrollment,any_discontinued,why_stopped,serious_ae_organ_classes,top_serious_organ,best_remission_pct&order=best_quality_score.desc.nullslast&limit=1000'),
        Q('drugs','select=id,display_name,name&limit=2000')
      ]);
      const nameById={}; (drugs||[]).forEach(d=>{ nameById[d.id]=d.display_name||d.name||d.id; });
      DB={insights,tda,tgen,tdq,cas,eu,mfg,prov,tri,kols,kolm,grants,own,ipi,clinical:clin||[],nameById};
      paint();
    }catch(e){
      if(body) body.innerHTML='<div class="intel2-muted">Could not load intelligence: '+E(e&&e.message?e.message:e)+'</div>';
    }finally{ LOADING=false; }
  };

  // Section nav (event delegation so it survives repaints).
  document.addEventListener('click',function(ev){
    const b=ev.target.closest('#intel2-nav .intel2-navbtn');
    if(b && b.dataset.sec) setSec(b.dataset.sec);
  });

  if(typeof registerTab==='function') registerTab('intel2',{ onEnter(){ window.intel2Init && window.intel2Init(); } });
})();
