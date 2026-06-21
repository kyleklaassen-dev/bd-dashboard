// ── DOSSIER RENDERERS (company + drug) ───────────────────────────
// Extracted from app.js (Domain A2, §3 method — byte-identical relocation).
// Plain script loaded BEFORE app.js: the 4 builders stay global (entity modals call them).
// Free vars resolve at call-time: _drugNameHTML (dkn.js); _cem*/_dossierSwitch/openDrugEntityModal/
// openKFFromTarget/openKFFromIndication (app.js). mRow/badge/stageStyle/_confBadge are locals here.

// Build the tab-nav + panels HTML shell
function _buildDossierShell(tabs, panels) {
  const tabBtns = tabs.map((t, i) =>
    `<button class="dossier-tab-btn${i===0?' active':''}" data-panel="${t.id}" onclick="_dossierSwitch('${t.id}')">${t.label}</button>`
  ).join('');
  const panelDivs = panels.map((p, i) =>
    `<div class="dossier-panel${i===0?' active':''}" id="${p.id}">${p.content}</div>`
  ).join('');
  return `<div class="dossier-tabs">${tabBtns}</div><div class="dossier-panels">${panelDivs}</div>`;
}

// Shared KV row
function _dossierKV(k, v) {
  if (!v) return '';
  return `<div class="dossier-kv"><span class="dossier-kv-k">${k}</span><span class="dossier-kv-v">${v}</span></div>`;
}

// ── Company dossier renderer ──────────────────────────────────────────────
function _buildCompanyDossierBody(prog, sbData, areaId) {
  const profile  = sbData?.profile   || {};
  const sbCats   = sbData?.catalysts || [];
  const sbDeals  = sbData?.deals     || [];
  const sbDrugs  = sbData?.drugs     || [];
  const sbCombos = sbData?.combos    || [];
  const pi = profile.platform_intelligence || null;
  const bd = profile.bd_intelligence      || null;

  // ── Header chips: overlap + score + BD profile ──
  const chipsEl = document.getElementById('entity-modal-hd-chips');
  if (chipsEl) {
    const allProgs = sbData?.drugs || [];
    // Show best overlap for this area
    const bestOv = prog.overlap || allProgs[0]?.overlap || '';
    const ovCls = {Direct:'em-hd-chip-direct',Adjacent:'em-hd-chip-adjacent','Same-Space':'em-hd-chip-same',Watch:'em-hd-chip-watch'}[bestOv] || '';
    const ovChip = bestOv ? `<span class="em-hd-chip ${ovCls}">${bestOv}</span>` : '';
    const score = profile.completeness_score;
    const scoreCls = score >= 80 ? 'em-hd-chip-score' : score >= 50 ? 'em-hd-chip-score partial' : 'em-hd-chip-score thin';
    const scoreChip = score != null ? `<span class="em-hd-chip ${scoreCls}">Coverage ${score}%</span>` : '';
    const bdProfile = bd?.profile;
    const bdLabels = {acquirer:'Acquirer',licensor:'Licensor',collaborator:'Collaborator','partner-friendly':'Partner-Friendly','internal-focused':'Internal-Focused'};
    const bdChip = bdProfile ? `<span class="em-hd-chip em-hd-chip-bd">${bdLabels[bdProfile]||bdProfile}</span>` : '';
    const enriched = profile.last_enriched_at ? `<span class="em-hd-chip em-hd-chip-bd">Enriched ${profile.last_enriched_at.slice(0,10)}</span>` : '';
    chipsEl.innerHTML = [ovChip, scoreChip, bdChip, enriched].filter(Boolean).join('');
  }

  // ── OVERVIEW tab ──
  const piAssess = (pi?.assessment||'').replace(/^\[ASSESSED\]\s*/i,'');
  const profileCfg = {
    acquirer:{label:'Acquirer',bg:'#fef2f2',color:'#991b1b',border:'#fecaca'},
    licensor:{label:'Licensor',bg:'#eff6ff',color:'#1d4ed8',border:'#bfdbfe'},
    collaborator:{label:'Collaborator',bg:'#f0fdf4',color:'#15803d',border:'#bbf7d0'},
    'partner-friendly':{label:'Partner-Friendly',bg:'#f0fdf4',color:'#15803d',border:'#bbf7d0'},
    'internal-focused':{label:'Internal-Focused',bg:'#f8fafc',color:'#475569',border:'#e2e8f0'},
  };
  const bdPcfg = bd?.profile ? (profileCfg[bd.profile] || {label:bd.profile,bg:'#f8fafc',color:'#475569',border:'#e2e8f0'}) : null;
  const bdPill = bdPcfg ? `<span style="font-size:9px;font-weight:800;text-transform:uppercase;background:${bdPcfg.bg};color:${bdPcfg.color};border:1px solid ${bdPcfg.border};border-radius:8px;padding:2px 8px">${bdPcfg.label}</span>` : '';
  const assessHtml = piAssess ? `<div class="dossier-assess"><div class="dossier-assess-lbl"><span>Assessment</span>${bdPill}</div><p class="dossier-assess-text">${piAssess}</p></div>` : '';

  const platformSummary = profile.platform_summary || prog.summary || '';
  const bdSummary = profile.bd_summary || '';
  const vsAilux   = profile.vs_ailux  || '';
  const keyRisk   = profile.key_risk  || '';
  const whyMatters= profile.why_it_matters || '';

  const contextRows = [_dossierKV('vs. Ailux', vsAilux), _dossierKV('Key Risk', keyRisk), _dossierKV('Why It Matters', whyMatters)].filter(Boolean).join('');

  const overviewContent = `
    ${assessHtml}
    ${platformSummary ? `<div class="dossier-card"><div class="dossier-section-hd">Platform</div><p style="font-size:12px;line-height:1.6;color:#1e293b;margin:0">${platformSummary}</p></div>` : ''}
    ${bdSummary ? `<div class="dossier-card"><div class="dossier-section-hd">BD Posture</div><p style="font-size:12px;line-height:1.6;color:#1e293b;margin:0">${bdSummary}</p></div>` : ''}
    ${contextRows ? `<div class="dossier-card"><div class="dossier-section-hd">BD Context</div>${contextRows}</div>` : ''}
    ${!assessHtml && !platformSummary && !bdSummary && !contextRows ? '<div class="dossier-empty">No overview data yet — run enrichment to populate.</div>' : ''}
  `;

  // ── BD INTEL tab ──
  const facts = (pi?.facts||[]).map(f => `<li style="font-size:11.5px;color:#1e293b;padding:2px 0;line-height:1.5">${f}</li>`).join('');
  const direction = (pi?.direction||[]).map(d => {
    const clean = d.replace(/^\[INFERRED\]\s*/i,'');
    return `<li style="font-size:11.5px;color:#334155;padding:2px 0;line-height:1.5"><span style="font-size:8px;font-weight:800;background:#ede9fe;color:#6d28d9;border-radius:3px;padding:0 4px;margin-right:4px">INFERRED</span>${clean}</li>`;
  }).join('');
  const txRows = (bd?.transactions||[]).map(t =>
    `<div style="display:grid;grid-template-columns:60px 1fr auto;gap:6px;align-items:baseline;padding:4px 0;border-bottom:1px solid #f8fafc;font-size:11px">
      <span style="color:#64748b;font-weight:600">${t.date||''}</span>
      <span style="color:#1e293b">${t.asset||''}${t.partner?`<span style="color:#94a3b8"> · ${t.partner}</span>`:''}</span>
      <span style="color:#059669;font-weight:700;font-size:10px;white-space:nowrap">${t.total||t.upfront||''}</span>
    </div>`).join('');
  const bdAssess = (bd?.assessment||[]).map(a => `<li style="font-size:11.5px;color:#334155;padding:2px 0;line-height:1.5">${a.replace(/^\[ASSESSED\]\s*/i,'')}</li>`).join('');
  const bdIntelContent = `
    ${pi ? `<div class="dossier-card"><div class="dossier-section-hd">Platform Intelligence</div>
      ${facts ? `<div style="margin-bottom:8px"><div style="font-size:9px;font-weight:700;color:#94a3b8;margin-bottom:4px">FACTS</div><ul style="margin:0;padding-left:14px">${facts}</ul></div>` : ''}
      ${direction ? `<div><div style="font-size:9px;font-weight:700;color:#94a3b8;margin-bottom:4px">INFERRED DIRECTION</div><ul style="margin:0;padding-left:14px">${direction}</ul></div>` : ''}
    </div>` : ''}
    ${bd ? `<div class="dossier-card"><div class="dossier-section-hd">BD Intelligence</div>
      ${txRows ? `<div style="margin-bottom:10px">${txRows}</div>` : ''}
      ${bdAssess ? `<ul style="margin:0;padding-left:14px">${bdAssess}</ul>` : ''}
    </div>` : ''}
    ${!pi && !bd ? '<div class="dossier-empty">No intelligence data yet. Run enrichment to populate.</div>' : ''}
  `;

  // ── PIPELINE tab ──
  const stageStyle = s => {
    const c = s==='Approved'?['#15803d','#dcfce7']:s?.includes('3')?['#1d4ed8','#dbeafe']:s?.includes('2')?['#0d9488','#ccfbf1']:s?.includes('1')?['#b45309','#fef3c7']:['#64748b','#f1f5f9'];
    return `background:${c[1]};color:${c[0]}`;
  };
  const drugItems = sbDrugs.map(d => {
    // Originator pill: shown when drug was acquired/licensed from another company.
    // Priority: ownership_edges ORIGINATED_BY (_originator_name) > partner_company text field.
    const _origPillStyle = 'font-size:9px;color:#64748b;background:#f1f5f9;border:1px solid #cbd5e1;border-radius:8px;padding:1px 7px;white-space:nowrap';
    const _codevPillStyle = 'font-size:9px;font-weight:700;color:#7c3aed;background:#f5f3ff;border:1px solid #c4b5fd;border-radius:8px;padding:1px 7px;white-space:nowrap';
    // CO-DEV badge: shown when this drug appears here because of co-development (not origination)
    const codevBadge = d._is_codev
      ? `<span style="${_codevPillStyle}" title="Co-developed asset — originated by ${d._codev_originator}">CO-DEV</span>`
      : '';
    const originatorPill = d._originator_name
      ? `<span style="${_origPillStyle}" title="Originated by ${d._originator_name}">via ${d._originator_name}</span>`
      : (d.partner_company && !d._is_codev
        ? `<span style="${_origPillStyle}">w/ ${d.partner_company}</span>`
        : '');
    return `
    <div class="dossier-drug-item">
      <div>
        <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:3px">
          <span style="font-size:12px;font-weight:700;color:#1e3a5f;cursor:pointer" onclick="openDrugEntityModal('${d.id}','${(d.display_name||d.name||'').replace(/'/g,"\\'")}',event)">${_drugNameHTML(d.display_name||d.name||'—')}</span>
          <span style="font-size:9px;font-weight:800;padding:2px 6px;border-radius:5px;${stageStyle(d.stage)}">${d.stage||'Preclinical'}</span>
          ${d.cls?`<span style="font-size:9px;color:#64748b;font-weight:600">${d.cls}</span>`:''}
          ${codevBadge}
          ${originatorPill}
        </div>
        ${d.target?`<div style="font-size:10.5px;color:#2e6fb0;font-weight:600;margin-bottom:2px">${d.target}</div>`:''}
        ${d.mechanism?`<div style="font-size:11px;color:#475569;line-height:1.4">${d.mechanism.slice(0,140)}${d.mechanism.length>140?'…':''}</div>`:''}
        ${d.drug_summary?`<div style="font-size:11px;color:#374151;line-height:1.45;margin-top:3px">${d.drug_summary.slice(0,200)}${d.drug_summary.length>200?'…':''}</div>`:''}
      </div>
    </div>`;
  }).join('');
  const comboItems = sbCombos.map(c => `
    <div class="dossier-drug-item">
      <div>
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:3px">
          <span style="font-size:12px;font-weight:700;color:#7c3aed">${c.label||'Combination'}</span>
          <span style="font-size:9px;background:#f5f3ff;color:#7c3aed;padding:2px 6px;border-radius:5px;font-weight:800">COMBO</span>
          ${c.stage?`<span style="font-size:9px;font-weight:800;padding:2px 6px;border-radius:5px;${stageStyle(c.stage)}">${c.stage}</span>`:''}
        </div>
        ${c.indication?`<div style="font-size:11px;color:#475569">${c.indication}</div>`:''}
      </div>
    </div>`).join('');
  const pipelineContent = (drugItems||comboItems)
    ? `<div class="dossier-card">${drugItems}${comboItems}</div>`
    : '<div class="dossier-empty">No pipeline data for this area.</div>';

  // ── CATALYSTS tab ──
  const catItems = sbCats.map(c => {
    const d = (c.sort_date||c.catalyst_date||'').slice(0,7) || '—';
    const detail = c.detail ? `<span style="color:#64748b"> — ${c.detail.slice(0,80)}${c.detail.length>80?'…':''}</span>` : '';
    return `<div class="dossier-cat-item">
      <span class="dossier-cat-date">${d}</span>
      <span class="dossier-cat-lbl">${c.label||'—'}${detail}</span>
      <span class="dossier-cat-type">${(c.catalyst_type||'').replace(/_/g,' ')}</span>
    </div>`;
  }).join('');
  const catalystsContent = catItems
    ? `<div class="dossier-card">${catItems}</div>`
    : '<div class="dossier-empty">No upcoming catalysts.</div>';

  // ── ACTIVITY tab ──
  const actItems = sbDeals.map(item => {
    const isIntel = item._source === 'intel';
    const date = (item.deal_date||'').slice(0,10);
    const typeTag = isIntel
      ? `<span style="font-size:8.5px;font-weight:800;background:#f1f5f9;color:#475569;border-radius:4px;padding:1px 5px">NEWS</span>`
      : `<span style="font-size:8.5px;font-weight:800;background:#eff6ff;color:#1d4ed8;border-radius:4px;padding:1px 5px">${(item.deal_type||'DEAL').toUpperCase()}</span>`;
    const headline = item.headline || `${item.from_company||''} → ${item.to_company||''}`;
    const detail   = item.detail   || item.description || '';
    const val      = item.total_value || item.deal_value_formatted || '';
    const src      = item.source_url ? `<div class="dossier-news-src"><a href="${item.source_url}" target="_blank" rel="noopener">Source ↗</a></div>` : '';
    return `<div class="dossier-news-item">
      <div class="dossier-news-meta">${typeTag}<span class="dossier-news-date">${date}</span>${val?`<span style="font-size:10px;font-weight:700;color:#059669">${val}</span>`:''}</div>
      <div class="dossier-news-hl">${headline}</div>
      ${detail?`<div class="dossier-news-body">${detail.slice(0,220)}${detail.length>220?'…':''}</div>`:''}
      ${src}
    </div>`;
  }).join('');
  const activityContent = actItems
    ? `<div class="dossier-card">${actItems}</div>`
    : '<div class="dossier-empty">No recent deals or news.</div>';

  return _buildDossierShell(
    [{id:'dos-overview',label:'Overview'},{id:'dos-bdintel',label:'BD Intel'},{id:'dos-pipeline',label:'Pipeline'},{id:'dos-catalysts',label:'Catalysts'},{id:'dos-activity',label:'Activity'}],
    [{id:'dos-overview',content:overviewContent},{id:'dos-bdintel',content:bdIntelContent},{id:'dos-pipeline',content:pipelineContent},{id:'dos-catalysts',content:catalystsContent},{id:'dos-activity',content:activityContent}]
  );
}

// ── Drug dossier renderer ─────────────────────────────────────────────────
function _buildDrugDossierBody(drug, areas, trials, molData) {
  const chipsEl = document.getElementById('entity-modal-hd-chips');
  if (chipsEl && drug) {
    const st = drug.stage || '';
    const stBg = st==='Approved'?'rgba(34,197,94,0.22)':st.includes('3')?'rgba(96,165,250,0.25)':st.includes('2')?'rgba(20,184,166,0.22)':'rgba(148,163,184,0.22)';
    const stCo = st==='Approved'?'#86efac':st.includes('3')?'#93c5fd':st.includes('2')?'#5eead4':'#cbd5e1';
    const stChip = st ? `<span class="em-hd-chip" style="background:${stBg};color:${stCo}">${st}</span>` : '';
    // Use area-specific overlap if available, else fall back to drug-level overlap
    const areasWithOverlap = areas.filter(a => a.overlap);
    const chipsSource = areasWithOverlap.length ? areasWithOverlap
      : (drug.overlap ? [{ area_id: 'global', overlap: drug.overlap }] : []);
    // Confidence badge helper
    const _confBadge = (confLevel, srcUrl) => {
      // Handles both new (A/B/C) and legacy (confirmed/supported) confidence values
      if ((confLevel === 'A' || confLevel === 'confirmed') && srcUrl)
        return `<span title="Confirmed: source URL on file" style="font-size:8px;margin-left:3px">✓</span>`;
      if (confLevel === 'B' || confLevel === 'supported')
        return `<span title="Supported: inferred from related evidence" style="font-size:8px;margin-left:3px;opacity:0.7">≈</span>`;
      if (confLevel === 'C')
        return `<span title="Low confidence: limited evidence" style="font-size:8px;margin-left:3px;opacity:0.5">◦</span>`;
      if (confLevel === 'inferred')
        return `<span title="Inferred: no primary source" style="font-size:8px;margin-left:3px;opacity:0.6">~</span>`;
      return `<span title="Unverified: no source URL on file" style="font-size:8px;margin-left:3px;opacity:0.45">?</span>`;
    };
    const _CONF_LABEL = {A:'Confirmed',B:'Supported',C:'Low confidence',inferred:'Inferred',confirmed:'Confirmed',supported:'Supported'};
    const areaChips = chipsSource.map(a => {
      const ov = (a.overlap||'').toLowerCase();
      const cls = {direct:'em-hd-chip-direct',adjacent:'em-hd-chip-adjacent','same-space':'em-hd-chip-same',watch:'em-hd-chip-watch'}[ov] || '';
      const lbl = a.area_id !== 'global' ? (_AREA_LABEL[a.area_id] || a.area_id || '') : '';
      const conf = _confBadge(a.confidence_level, a.source_url);
      const tooltip = a.source_url ? `title="Source: ${a.source_url}"` : (a.confidence_level ? `title="${_CONF_LABEL[a.confidence_level] || a.confidence_level}"` : '');
      return a.overlap ? `<span class="em-hd-chip ${cls}" ${tooltip}>${lbl ? lbl + ': ' : ''}${a.overlap}${conf}</span>` : '';
    }).filter(Boolean).join('');
    chipsEl.innerHTML = [stChip, areaChips].filter(Boolean).join('');
  }

  if (!drug) return '<div class="dossier-empty">Drug data not available.</div>';

  // ── OVERVIEW tab ──
  const mechanism = drug.mechanism || '';
  const summary   = drug.drug_summary || '';
  const diff      = drug.differentiation_thesis || '';
  // Fallback: if no area has overlap data, synthesize one row from drugs.overlap
  let areasForPos = areas.filter(a => a.overlap);
  if (!areasForPos.length && drug.overlap) {
    areasForPos = [{ area_id: 'global', overlap: drug.overlap, overlap_rationale: drug.overlap_rationale || drug.vs_ailux || '' }];
  }
  const areaPos   = areasForPos;
  const posRows   = areaPos.map(a => {
    const lbl = _AREA_LABEL[a.area_id] || (a.area_id||'').toUpperCase();
    const ov  = (a.overlap||'').toLowerCase();
    const [bg,co] = ov==='direct'?['#fee2e2','#b91c1c']:ov==='adjacent'?['#dbeafe','#1d4ed8']:ov==='same-space'?['#dcfce7','#15803d']:['#f1f5f9','#64748b'];
    return `<div style="display:flex;align-items:center;gap:8px;padding:5px 0;border-bottom:1px solid #f8fafc">
      <span style="font-size:10px;font-weight:700;color:#475569;min-width:68px">${lbl}</span>
      <span style="font-size:10px;font-weight:800;background:${bg};color:${co};padding:2px 7px;border-radius:5px">${a.overlap}</span>
      ${a.overlap_rationale?`<span style="font-size:11px;color:#475569;flex:1">${a.overlap_rationale.slice(0,100)}${a.overlap_rationale.length>100?'…':''}</span>`:''}
    </div>`;
  }).join('');

  const overviewContent = `
    ${mechanism||summary||diff ? `<div class="dossier-card">
      <div class="dossier-section-hd">Drug Profile</div>
      ${_dossierKV('Mechanism', mechanism)}
      ${drug.target ? `<div class="dossier-kv"><span class="dossier-kv-k">Target</span><span class="dossier-kv-v"><span class="entity-link" onclick="openKFFromTarget('${(drug.target||'').replace(/'/g,"\\'")}')" title="Open Knowledge Folder for this target">${drug.target}</span></span></div>` : ''}
      ${_dossierKV('Class', drug.cls)}
      ${_dossierKV('Route', drug.route)}
      ${drug.indication_short ? `<div class="dossier-kv"><span class="dossier-kv-k">Indication</span><span class="dossier-kv-v"><span class="entity-link" onclick="openKFFromIndication('${(drug.indication_short||'').replace(/'/g,"\\'").replace(/"/g,'&quot;')}')" title="Open Knowledge Folder for this indication">${drug.indication_short}</span></span></div>` : ''}
    </div>` : ''}
    ${summary ? `<div class="dossier-card"><div class="dossier-section-hd">Summary</div><p style="font-size:12px;line-height:1.6;color:#1e293b;margin:0">${summary}</p></div>` : ''}
    ${diff ? `<div class="dossier-card" style="border-left:3px solid #7c3aed"><div class="dossier-section-hd">Differentiation Thesis</div><p style="font-size:12px;line-height:1.55;color:#1e293b;margin:0;font-weight:600">${diff}</p></div>` : ''}
    ${posRows ? `<div class="dossier-card"><div class="dossier-section-hd">Competitive Position</div>${posRows}</div>` : ''}
    ${!mechanism && !summary && !diff && !posRows ? '<div class="dossier-empty">No drug data yet.</div>' : ''}
  `;

  // ── TRIALS tab ──
  const trialItems = (trials||[]).map(t => {
    const ph = t.phase||'';
    const [phBg,phCo] = ph.includes('3')?['#dbeafe','#1d4ed8']:ph.includes('2')?['#ccfbf1','#0d9488']:['#fef3c7','#92400e'];
    const stLow = (t.status||'').toLowerCase();
    const dot = stLow.includes('recruit')&&!stLow.includes('not yet')?'#22c55e':stLow.includes('terminat')||stLow.includes('withdrawn')?'#ef4444':stLow.includes('complet')?'#94a3b8':'#f59e0b';
    return `<div class="dossier-trial-item">
      <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:4px">
        ${ph?`<span style="font-size:10px;font-weight:800;background:${phBg};color:${phCo};padding:2px 6px;border-radius:5px">${ph}</span>`:''}
        <span style="font-size:11px;font-weight:700;color:#1e3a5f">${t.trial_name||'—'}</span>
        <span style="font-size:10px;color:#94a3b8"><span style="color:${dot}">●</span> ${t.status||''}</span>
      </div>
      ${t.n_enrollment?`<div style="font-size:10.5px;color:#64748b;margin-bottom:2px">N = ${t.n_enrollment}${t.primary_completion_date?` · Est. ${t.primary_completion_date.slice(0,7)}`:''}</div>`:''}
      ${t.primary_endpoint?`<div style="font-size:11px;color:#1e293b;line-height:1.4"><strong>Primary:</strong> ${t.primary_endpoint.slice(0,160)}${t.primary_endpoint.length>160?'…':''}</div>`:''}
      ${t.results_note?`<div style="font-size:11px;color:#0f172a;line-height:1.4;margin-top:3px;background:#f0fdf4;padding:4px 8px;border-radius:4px">${t.results_note.slice(0,200)}</div>`:''}
    </div>`;
  }).join('');
  const trialsContent = trialItems
    ? `<div class="dossier-card">${trialItems}</div>`
    : '<div class="dossier-empty">No trial data found.</div>';

  // ── MOLECULE INTEL tab (if available) ──
  let molContent = '';
  if (molData) {
    const fs = molData.field_status || {};
    const badge = s => {
      if (!s||s==='confirmed') return '';
      const cfg = s==='inferred'?{bg:'#fffbeb',co:'#b45309',bd:'#fde68a',lbl:'Inferred'}:{bg:'#f8fafc',co:'#94a3b8',bd:'#e2e8f0',lbl:'Not disclosed'};
      return `<span style="font-size:7.5px;font-weight:800;text-transform:uppercase;background:${cfg.bg};color:${cfg.co};border:1px solid ${cfg.bd};border-radius:4px;padding:1px 4px;margin-left:4px">${cfg.lbl}</span>`;
    };
    const mRow = (k,v,fk) => v ? `<div class="dossier-kv"><span class="dossier-kv-k">${k}</span><span class="dossier-kv-v">${v}${badge(fs[fk])}</span></div>` : '';
    molContent = `<div class="dossier-card"><div class="dossier-section-hd">Molecule Intelligence</div>
      ${mRow('Format',         molData.format,          'format')}
      ${mRow('Modality',       molData.modality,        'modality')}
      ${mRow('IgG subclass',   molData.igg_subclass,    'igg_subclass')}
      ${mRow('Fc engineering', molData.fc_engineering,  'fc_engineering')}
      ${mRow('Epitope',        molData.epitope,         'epitope')}
      ${mRow('Affinity (KD)',  molData.affinity_kd,     'affinity_kd')}
      ${molData.differentiation_claim?`<div style="margin-top:8px;padding:7px 10px;background:#f5f3ff;border-radius:6px;border-left:3px solid #7c3aed">
        <div style="font-size:8.5px;font-weight:800;color:#7c3aed;text-transform:uppercase;margin-bottom:3px">Differentiation Thesis ${badge(fs.differentiation_claim)}</div>
        <p style="font-size:11px;color:#1e293b;margin:0;font-style:italic;line-height:1.45">${molData.differentiation_claim}</p>
      </div>`:''}
    </div>`;
  }

  const tabs   = [{id:'ddos-overview',label:'Overview'},{id:'ddos-trials',label:'Trials'},{id:'ddos-molintel',label:'Molecule'}];
  const panels = [
    {id:'ddos-overview',  content:overviewContent},
    {id:'ddos-trials',    content:trialsContent},
    {id:'ddos-molintel',  content:molContent || '<div class="dossier-empty">Not yet profiled — molecule intelligence runs automatically with enrichment.</div>'},
  ];

  return _buildDossierShell(tabs, panels);
}
