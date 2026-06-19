// DRUG-INTEL MODAL + DOSSIER RENDERERS — 100-question intelligence framework (_DIM/_dem),
// dossier shell + company/drug dossier bodies, and _cem* render helpers + _mdMeridian markdown.
// Extracted from app.js (Phase 4 split 2026-06-19). Classic script: globals used by
// company_modal.js + app.js at call time (e.g. _buildCompanyDossierBody, _demLoadIntelligence).
// Loaded before app.js.

// ── Drug entity modal — Intelligence tab lazy loader ───────────────────────
// Domain config for 100-question intelligence framework
const _DIM_DOMAINS = [
  { id:'molecule',    icon:'🔬', label:'Molecule & Mechanism',   questions:[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20], color:'#e0f2fe' },
  { id:'clinical',    icon:'🏥', label:'Clinical Development',   questions:[21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40], color:'#dcfce7' },
  { id:'patient',     icon:'👤', label:'Patient Intelligence',   questions:[41,42,43,44,45,46,47,48,49,50,51,52,53,54,55], color:'#fef3c7' },
  { id:'payer',       icon:'💰', label:'Payer & Market Access',  questions:[56,57,58,59,60,61,62,63,64,65], color:'#f3e8ff' },
  { id:'competitive', icon:'⚔️', label:'Competitive Landscape', questions:[66,67,68,69,70,71,72,73,74,75,76,77,78,79,80], color:'#fff1f2' },
  { id:'regulatory',  icon:'⚖️', label:'Regulatory Pathway',   questions:[81,82,83,84,85,86,87,88,89,90], color:'#f0fdf4' },
  { id:'ip',          icon:'🔒', label:'IP & Legal',            questions:[91,92,93,94,95], color:'#faf5ff' },
  { id:'strategic',   icon:'🎯', label:'BD & Strategic Value',  questions:[96,97,98,99,100], color:'#fff7ed' },
];

function _dimConfClass(score) {
  if (score == null) return 'dim-conf-unknown';
  if (score >= 0.7) return 'dim-conf-high';
  if (score >= 0.4) return 'dim-conf-medium';
  return 'dim-conf-low';
}

function _dimConfLabel(score, level) {
  if (level === 'high') return 'High confidence';
  if (level === 'low') return 'Low confidence';
  if (score == null) return 'Confidence unknown';
  if (score >= 0.7) return 'High confidence';
  if (score >= 0.4) return 'Medium confidence';
  return 'Low confidence';
}

function _dimSourceChips(urls, labels) {
  if (!urls || !urls.length) return '';
  return (urls||[]).map((u,i) => {
    const lbl = (labels && labels[i]) ? labels[i] : (() => {
      try { const h = new URL(u).hostname.replace('www.',''); return h.split('.')[0].toUpperCase().slice(0,10); } catch(_) { return 'SOURCE'; }
    })();
    const shortLbl = lbl.length > 18 ? lbl.slice(0,18)+'…' : lbl;
    return u ? `<a class="dim-source-chip" href="${u}" target="_blank" rel="noopener" title="${lbl}">${shortLbl}</a>` : `<span class="dim-source-chip" title="${lbl}">${shortLbl}</span>`;
  }).join('');
}

function _dimBuildTimeline(qaMap) {
  // Extract clean date estimates from Q21 (FIH) and Q28 (Phase 3 completion)
  // Only use as sub-label if it looks like a real date (year, quarter, or month)
  const _cleanDate = (s) => {
    if (!s) return '';
    // Look for patterns like "Q4 2027", "H1 2028", "2027", "Oct 2027", "early 2027"
    const m = s.match(/(?:Q[1-4]|H[12]|[A-Z][a-z]{2,8}|early|late|mid)?\s*20\d\d/i);
    if (m) return m[0].trim();
    // If it starts with "FIH" or is a description, skip it
    if (/^fih|^phase|^ind|^approval|^discovery/i.test(s.trim())) return '';
    // Short clean date string (under 12 chars)
    return s.length <= 12 ? s.trim() : '';
  };
  const q21 = _cleanDate((qaMap[21]||{}).answer_short || '');
  const q28 = _cleanDate((qaMap[28]||{}).answer_short || '');
  const milestones = [
    { label:'Discovery', sub:'', state:'done' },
    { label:'IND Filing', sub:'', state:'done' },
    { label:'FIH', sub: q21, state: q21 ? 'done' : 'future' },
    { label:'Ph1 Complete', sub:'', state:'future' },
    { label:'Phase 2', sub:'', state:'current' },
    { label:'Phase 3', sub: q28, state: q28 ? 'imminent' : 'future' },
    { label:'NDA/BLA', sub:'', state:'future' },
    { label:'Approval', sub:'', state:'future' },
  ];

  const dots = milestones.map((m, i) => {
    const isAbove = i % 2 === 0;
    const labelClass = isAbove ? 'above' : 'below';
    const subHtml = m.sub ? `<span style="font-weight:400;color:#94a3b8"> · ${m.sub}</span>` : '';
    return `${i > 0 ? '<div class="dim-timeline-line"></div>' : ''}
      <div class="dim-timeline-dot ${m.state}" style="position:relative">
        <div class="dim-timeline-label ${labelClass}">${m.label}${subHtml}</div>
      </div>`;
  }).join('');

  return `<div class="dim-timeline">
    <div style="font-size:9px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px">Development Timeline</div>
    <div class="dim-timeline-track">${dots}</div>
    <div style="display:flex;gap:12px;margin-top:8px;flex-wrap:wrap">
      <span style="font-size:9px;color:#64748b;display:flex;align-items:center;gap:4px"><span style="width:8px;height:8px;border-radius:50%;background:#22c55e;display:inline-block"></span> Confirmed</span>
      <span style="font-size:9px;color:#64748b;display:flex;align-items:center;gap:4px"><span style="width:8px;height:8px;border-radius:50%;background:#3b82f6;display:inline-block"></span> Current</span>
      <span style="font-size:9px;color:#64748b;display:flex;align-items:center;gap:4px"><span style="width:8px;height:8px;border-radius:50%;border:2px solid #f59e0b;display:inline-block"></span> Imminent (&lt;12 mo)</span>
      <span style="font-size:9px;color:#64748b;display:flex;align-items:center;gap:4px"><span style="width:8px;height:8px;border-radius:50%;border:2px solid #cbd5e1;display:inline-block"></span> Future</span>
    </div>
  </div>`;
}

function _dimBuildEfficacyChart(qaMap) {
  // Q29 = efficacy ceiling; Q67 = BIC benchmark
  const q29 = (qaMap[29]||{}).answer_short || '';
  const q67 = (qaMap[67]||{}).answer_short || '';
  if (!q29 && !q67) return '';

  // Parse numbers from text for simple bar chart
  const extractPct = s => { const m = s.match(/(\d+(?:\.\d+)?)\s*%/); return m ? parseFloat(m[1]) : null; };
  const thisPct  = extractPct(q29) || 26;   // TUSCANY-2 baseline
  const bicPct   = extractPct(q67) || 24.2; // mirikizumab LUCENT-1
  const ailuxTgt = 50;

  const maxPct = Math.max(thisPct, bicPct, ailuxTgt) * 1.2;
  const bar = (pct, color, label, sublabel) => {
    const w = Math.round((pct / maxPct) * 100);
    return `<div style="margin-bottom:10px">
      <div style="display:flex;justify-content:space-between;font-size:10px;color:#64748b;margin-bottom:3px">
        <span style="font-weight:600;color:#0f172a">${label}</span>
        <span style="font-weight:700;color:${color}">${pct}%</span>
      </div>
      <div style="background:#f1f5f9;border-radius:4px;height:8px;position:relative">
        <div style="background:${color};border-radius:4px;height:8px;width:${w}%;transition:width 0.4s"></div>
      </div>
      ${sublabel ? `<div style="font-size:9px;color:#94a3b8;margin-top:2px">${sublabel}</div>` : ''}
    </div>`;
  };

  // Dotted ALX001 target line
  const tgtW = Math.round((ailuxTgt / maxPct) * 100);

  return `<div style="background:#f8fafc;border:0.5px solid #e2e8f0;border-radius:8px;padding:12px 14px;margin-top:12px">
    <div style="font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:10px">Efficacy Benchmark — Clinical Remission Rate (Wk 12)</div>
    <div style="position:relative">
      ${bar(thisPct, '#3b82f6', 'This drug (Ph2, enriched)', 'TUSCANY-2 unenriched UC population')}
      ${bar(bicPct, '#64748b', 'BIC: mirikizumab LUCENT-1 Ph3', 'Moderately-to-severely active UC, ITT')}
      <div style="margin-top:6px;position:relative">
        <div style="display:flex;justify-content:space-between;font-size:10px;margin-bottom:3px">
          <span style="font-weight:600;color:#7c3aed">ALX001 target</span>
          <span style="font-weight:700;color:#7c3aed">&gt;${ailuxTgt}%</span>
        </div>
        <div style="background:#f1f5f9;border-radius:4px;height:8px;position:relative">
          <div style="position:absolute;left:${tgtW}%;top:-3px;bottom:-3px;width:2px;background:#7c3aed;border-radius:1px"></div>
          <div style="background:repeating-linear-gradient(90deg,#e9d5ff 0px,#e9d5ff 4px,transparent 4px,transparent 8px);border-radius:4px;height:8px;width:${tgtW}%"></div>
        </div>
        <div style="font-size:9px;color:#94a3b8;margin-top:2px">TL1A×IL-23p19 bispecific target (biologic design ceiling)</div>
      </div>
    </div>
    <div style="font-size:9px;color:#94a3b8;margin-top:8px;border-top:0.5px solid #e2e8f0;padding-top:6px">Source: TUSCANY-2 (Ph2) · LUCENT-1 D'Haens et al. NEJM 2023 · Confidence: medium</div>
  </div>`;
}

async function _demLoadIntelligence(drugId, drugName, companyId) {
  const panel = document.getElementById('cem-dtab-intel-panel');
  if (!panel || !_sb) return;
  panel.innerHTML = '<div style="padding:20px;text-align:center;color:#94a3b8;font-size:12px;font-style:italic">Loading intelligence profile…</div>';

  try {
    const _drugIdSafe = drugId && !String(drugId).startsWith('static-') ? drugId : null;

    // Fetch the 100-question intelligence profile
    const { data: qaRows, error: qaErr } = _drugIdSafe
      ? await _sb.from('drug_intelligence_qa')
          .select('question_id,domain,question_text,answer_text,answer_short,confidence_score,evidence_level,source_urls,source_labels')
          .eq('drug_id', _drugIdSafe)
          .order('question_id', {ascending: true})
      : { data: [], error: null };

    if (qaErr) throw qaErr;

    // No data state
    if (!qaRows || qaRows.length === 0) {
      panel.innerHTML = `<div style="padding:32px;text-align:center">
        <div style="font-size:32px;margin-bottom:12px">🔬</div>
        <div style="font-size:14px;font-weight:600;color:#0f172a;margin-bottom:6px">Intelligence profile not yet generated for ${drugName || 'this drug'}</div>
        <div style="font-size:12px;color:#64748b;margin-bottom:16px">Run the enrichment pipeline to generate 100-question analysis covering mechanism, clinical development, patient intelligence, competitive positioning, and BD strategy.</div>
        <div style="font-size:10px;color:#94a3b8">drug_intelligence_qa table · drug_id: ${_drugIdSafe || 'unknown'}</div>
      </div>`;
      return;
    }

    // Index by question_id for fast lookup
    const qaMap = {};
    qaRows.forEach(r => { qaMap[r.question_id] = r; });

    // Group by domain
    const byDomain = {};
    qaRows.forEach(r => {
      if (!byDomain[r.domain]) byDomain[r.domain] = [];
      byDomain[r.domain].push(r);
    });

    // ── Layer 1: Headline Strip ──────────────────────────────────────────────
    const _hlFact = (icon, label, qRow) => {
      const val = qRow ? (qRow.answer_short || '').slice(0, 80) || '—' : '—';
      return `<div class="dim-headline-fact">
        <div class="dim-headline-icon">${icon}</div>
        <div class="dim-headline-label">${label}</div>
        <div class="dim-headline-value">${val}</div>
      </div>`;
    };

    // Q2 = mechanism (block TL1A→DR3), Q29 = efficacy ceiling, Q41 = patient, Q9 = route/interval, Q28 = timeline
    const hlMech = qaMap[2] ? (qaMap[2].answer_short||'').slice(0,80) : (qaMap[1] ? (qaMap[1].answer_short||'').slice(0,80) : '—');
    const hlEff  = qaMap[29] ? (qaMap[29].answer_short||'').slice(0,80) : '—';
    const hlPat  = qaMap[41] ? (qaMap[41].answer_short||'').slice(0,80) : '—';
    const hlRoute= qaMap[9]  ? (qaMap[9].answer_short||'').slice(0,80) : (qaMap[8] ? (qaMap[8].answer_short||'').slice(0,80) : '—');
    const hlTime = qaMap[28] ? (qaMap[28].answer_short||'').slice(0,80) : (qaMap[21] ? (qaMap[21].answer_short||'').slice(0,80) : '—');

    const headlineHtml = `<div class="dim-headline-strip">
      <div class="dim-headline-fact"><div class="dim-headline-icon">🎯</div><div class="dim-headline-label">Mechanism</div><div class="dim-headline-value">${hlMech}</div></div>
      <div class="dim-headline-fact"><div class="dim-headline-icon">📊</div><div class="dim-headline-label">Efficacy ceiling</div><div class="dim-headline-value">${hlEff}</div></div>
      <div class="dim-headline-fact"><div class="dim-headline-icon">👤</div><div class="dim-headline-label">Patient</div><div class="dim-headline-value">${hlPat}</div></div>
      <div class="dim-headline-fact"><div class="dim-headline-icon">💊</div><div class="dim-headline-label">Route</div><div class="dim-headline-value">${hlRoute}</div></div>
      <div class="dim-headline-fact"><div class="dim-headline-icon">🏁</div><div class="dim-headline-label">Timeline</div><div class="dim-headline-value">${hlTime}</div></div>
    </div>`;

    // ── Layer 2+3: Domain Bars with expandable Q&A ───────────────────────────
    const _uid = () => Math.random().toString(36).slice(2,8);

    const domainsHtml = _DIM_DOMAINS.map(dom => {
      const rows = (byDomain[dom.id] || []).sort((a,b) => a.question_id - b.question_id);
      if (!rows.length) return '';

      const answered = rows.filter(r => r.answer_short && r.answer_short !== '—').length;
      const highConf = rows.filter(r => (r.confidence_score||0) >= 0.7 || r.evidence_level === 'high').length;
      const domId = `dim-dom-${dom.id}-${_uid()}`;

      // 2-sentence domain summary: first 2 non-empty answer_shorts
      const summaryRows = rows.filter(r => r.answer_short).slice(0,2);
      const summaryText = summaryRows.map(r => r.answer_short.replace(/\.$/, '')).join('. ') + (summaryRows.length ? '.' : '');

      // Q&A items for this domain
      const qaItemsHtml = rows.map(r => {
        const detId = `dim-det-${r.question_id}-${_uid()}`;
        const chips = _dimSourceChips(r.source_urls, r.source_labels);
        const hasDetail = r.answer_text && r.answer_text !== r.answer_short && r.answer_text.length > 20;
        return `<div class="dim-qa-item">
          <div class="dim-qa-num">Q${r.question_id}</div>
          <div class="dim-qa-q">${r.question_text || ''}</div>
          <div class="dim-qa-short">${r.answer_short || '—'}</div>
          ${hasDetail ? `<span class="dim-qa-toggle" onclick="this.nextElementSibling.classList.toggle('open');this.textContent=this.nextElementSibling.classList.contains('open')?'▲ Hide detail':'→ Detail'">→ Detail</span>
          <div class="dim-qa-detail" id="${detId}">${r.answer_text || ''}</div>` : ''}
          <div class="dim-qa-meta">
            <div class="dim-conf-dot ${_dimConfClass(r.confidence_score)}" title="${_dimConfLabel(r.confidence_score, r.evidence_level)}"></div>
            <span style="font-size:9px;color:#94a3b8">${_dimConfLabel(r.confidence_score, r.evidence_level)}</span>
            ${chips}
          </div>
        </div>`;
      }).join('');

      // Insert efficacy benchmark chart after Clinical domain Q&A
      const extraHtml = dom.id === 'clinical' ? _dimBuildEfficacyChart(qaMap) : '';

      return `<div class="dim-domain-bar">
        <div class="dim-domain-hd" onclick="(function(el){const b=el.nextElementSibling;const arr=el.querySelector('.dim-domain-arrow');b.classList.toggle('open');if(arr)arr.classList.toggle('open');})(this)">
          <span class="dim-domain-icon">${dom.icon}</span>
          <span class="dim-domain-name">${dom.label}</span>
          <span class="dim-domain-summary">${summaryText.slice(0,120)}${summaryText.length>120?'…':''}</span>
          <span class="dim-domain-meta">${answered}/${rows.length} answered${highConf > 0 ? ` · ${highConf} high conf` : ''}</span>
          <span class="dim-domain-arrow">▶</span>
        </div>
        <div class="dim-domain-body">
          ${qaItemsHtml}
          ${extraHtml}
        </div>
      </div>`;
    }).join('');

    // ── Layer 4: Timeline ────────────────────────────────────────────────────
    const timelineHtml = _dimBuildTimeline(qaMap);

    // ── Assemble panel ───────────────────────────────────────────────────────
    const totalAnswered = qaRows.filter(r => r.answer_short && r.answer_short !== '—').length;
    const highConfTotal = qaRows.filter(r => (r.confidence_score||0) >= 0.7 || r.evidence_level === 'high').length;
    const _latestRow = [...qaRows].sort((a,b) => new Date(b.last_researched||0) - new Date(a.last_researched||0))[0] || {};
    const _lastUpdated = _latestRow.last_researched
      ? new Date(_latestRow.last_researched).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'})
      : 'unknown';

    panel.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 16px 8px;border-bottom:1px solid #f1f5f9;background:#fafbfc">
        <div>
          <span style="font-size:12px;font-weight:700;color:#0f172a">${drugName || 'Drug'} — Intelligence Profile</span>
          <span style="font-size:10px;color:#94a3b8;margin-left:8px">${totalAnswered}/100 questions answered · ${highConfTotal} high confidence</span>
        </div>
        <div style="display:flex;gap:6px;align-items:center">
          <span style="font-size:9px;color:#94a3b8">Click any domain to expand</span>
        </div>
      </div>
      ${headlineHtml}
      <div style="margin:0">
        ${domainsHtml}
      </div>
      ${timelineHtml}
      <div style="padding:10px 16px;font-size:9px;color:#cbd5e1;border-top:1px solid #f8fafc">
        Intelligence profile generated by Meridian enrichment pipeline · ${qaRows.length} questions · Last updated ${_lastUpdated}
      </div>`;

  } catch(e) {
    panel.innerHTML = `<div style="padding:16px;color:#dc2626;font-size:12px">Failed to load intelligence: ${e.message}</div>`;
  }
}

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

/* ══ CANONICAL ENTITY MODAL — CEM renderer ═══════════════════════════════
   Shared expandable card layout for both Company and Drug entities.
   Replaces the tab-based dossier with a single scrollable canonical card.
   ═══════════════════════════════════════════════════════════════════════ */

function _cemToggle(id) {
  const det  = document.getElementById('cem-det-' + id);
  const chev = document.getElementById('cem-chev-' + id);
  if (!det) return;
  const open = det.classList.contains('open');
  det.classList.toggle('open', !open);
  if (chev) chev.classList.toggle('open', !open);
}

function _cemGq(text) {
  if (!text) return 'https://www.google.com/search?q=';
  let s = (text||'').replace(/^[↗→·•\s]+/, '').replace(/[;—].*/,'').trim();
  s = s.replace(/[,;:!?'"()\[\]{}]+/g,' ').replace(/\s+/g,' ').trim();
  const words = s.split(/\s+/).slice(0, 7);
  return 'https://www.google.com/search?q=' + encodeURIComponent(words.join(' '));
}

function _cemLink(name, query) {
  if (!name) return '';
  const url = _cemGq(query || name);
  return `<a class="cem-link" href="${url}" target="_blank" rel="noopener">${name}</a>`;
}
/* _cemTrialLink — NCT IDs go directly to clinicaltrials.gov/study/NCTXXXXXX;
   anything else falls back to a Google search via _cemLink */
function _cemTrialLink(label, nctId) {
  const nct = (nctId||'').match(/NCT\d{6,}/i)?.[0] || (label||'').match(/NCT\d{6,}/i)?.[0];
  if (nct) return `<a class="cem-link" href="https://clinicaltrials.gov/study/${nct.toUpperCase()}" target="_blank" rel="noopener">${label||nct}</a>`;
  return _cemLink(label, label);
}

function _cemFmtDate(d) {
  if (!d) return '';
  const dt = new Date((d+'').slice(0,10)+'T00:00:00');
  if (isNaN(dt)) return (d+'').slice(0,10);
  return dt.toLocaleString('en-US',{month:'short',year:'numeric'});
}

function _cemFmtVal(upfront, total) {
  const fmt = v => {
    if (!v) return '';
    const n = parseFloat(v);
    if (isNaN(n)) return '';
    return n >= 1000 ? `$${(n/1000).toFixed(1)}B` : `$${Math.round(n)}M`;
  };
  const u = fmt(upfront), t = fmt(total);
  return [u ? `<span class="cem-pill" style="background:#fef3c7;color:#92400e">${u} upfront</span>` : '',
          t ? `<span class="cem-pill cem-p-high">${t} total</span>` : ''].filter(Boolean).join('');
}

function _cemOverlapPill(overlap) {
  if (!overlap) return '';
  const ov = (overlap||'').toLowerCase();
  const cls = ov==='direct'?'cem-p-direct':ov==='adjacent'?'cem-p-adj':ov.includes('same')?'cem-p-same':'cem-p-low';
  return `<span class="cem-pill ${cls}">${overlap}</span>`;
}

function _cemPhasePill(phase) {
  if (!phase) return '';
  const p = String(phase).toLowerCase();
  const cls = p.includes('3')?'cem-p-blue':p.includes('2')?'cem-p-same':p.includes('1')?'cem-p-med':p.includes('approv')?'cem-p-high':'cem-p-low';
  return `<span class="cem-pill ${cls}">${phase}</span>`;
}

/* ── Shared markdown renderer for Meridian narratives (headers, bold, italic, [n] cites) ── */
function _mdMeridian(md) {
  // Typography aligned with the entity-card narrative (Kyle 2026-06-07): muted unlinked
  // citation superscripts (no source map available here), no stray --- rules, readable measure.
  const esc = s => (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  let h = esc(md);
  h = h.replace(/^\s*-{3,}\s*$/gm, '');
  h = h.replace(/\s*\[([\d,–—\- ]+)\]/g, (m, g) => `<sup style="color:#94a3b8;font-weight:600;font-size:9px;margin-left:1px">${g.replace(/[^\d,]/g, '')}</sup>`);
  h = h.replace(/^###\s+(.*)$/gm, '<div style="font-size:9.5px;font-weight:800;text-transform:uppercase;letter-spacing:0.07em;color:#64748b;margin:13px 0 4px">$1</div>');
  h = h.replace(/^##\s+(.*)$/gm, '<div style="font-size:13px;font-weight:700;color:#1e293b;margin:4px 0 8px">$1</div>');
  h = h.replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
  h = h.replace(/^_(.*)_\s*$/gm, '<em style="color:#6d28d9;font-style:italic">$1</em>');
  return h.split(/\n{2,}/).map(p => { p = p.trim(); if (!p) return '';
    return p.match(/^<(div|em)/)
      ? p : `<p style="font-size:12.5px;color:#243044;line-height:1.62;margin:0 0 9px;max-width:78ch">${p.replace(/\n/g, ' ')}</p>`; }).join('');
}
