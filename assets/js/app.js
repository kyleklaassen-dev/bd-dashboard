// ── DATA (loaded from JSON files in /data/) ─────────────────────
async function loadData() {
 const files = {
 tl1aPipe: 'data/tl1a_pipe.json',
 tl1aMono: 'data/tl1a_mono.json',
 tl1aReadouts: 'data/tl1a_readouts.json',
 tl1aTech: 'data/tl1a_tech.json',
 tslpReadouts: 'data/tslp_readouts.json',
 tslpPipe: 'data/tslp_pipe.json',
 tslpMono: 'data/tslp_mono.json',
 il4raTslpReadouts: 'data/il4ra_tslp_readouts.json',
 il4raTslpPipe: 'data/il4ra_tslp_pipe.json',
 il4raTslpMono: 'data/il4ra_tslp_mono.json',
 il4raOx40lReadouts: 'data/il4ra_ox40l_readouts.json',
 il4raOx40lPipe: 'data/il4ra_ox40l_pipe.json',
 il4raOx40lMono: 'data/il4ra_ox40l_mono.json',
 igf1rTshrReadouts: 'data/igf1r_tshr_readouts.json',
 igf1rTshrPipe: 'data/igf1r_tshr_pipe.json',
 igf1rTshrMono: 'data/igf1r_tshr_mono.json',
 fcrnReadouts: 'data/fcrn_readouts.json',
 fcrnPipe: 'data/fcrn_pipe.json',
 fcrnMono: 'data/fcrn_mono.json',
 aceReadouts: 'data/ace_readouts.json',
 acePipe: 'data/ace_pipe.json',
 aceMono: 'data/ace_mono.json',
 assetProfiles: 'data/asset_profiles.json',
 assetDocs: 'data/asset_docs.json',
 };
 const keys = Object.keys(files);
 const results = await Promise.all(keys.map(k => fetch(files[k]).then(r => r.json()).catch(()=>null)));
 const d = {};
 keys.forEach((k, i) => d[k] = results[i]);
 return d;
}

// TL1A × IL-23p19 bispecific pipeline
// Cols: Company, Asset, Format, Stage, Indication, Licensee/Partner, Upfront, Total Value, Estimand
// TL1A monotherapy context
// Cols: Company, Asset, Stage, Indication, Estimand, Notes
// Clinical Readout Calendar — TL1A
// Cols: Category, Program, Phase, Expected Timing, Indication
// Technical bispecific comparison
// Cols: Company, Asset, Stage, TL1A Mechanism, IL-23 Mechanism, Key Differentiator, Timeline
// Clinical Readout Calendar — TSLP / Respiratory
// Cols: Category, Program, Phase, Expected Timing, Indication
// TSLP × IL-33 bispecific pipeline
// Cols: Company, Asset, Format, Stage, Indication, Licensee/Partner, Upfront, Total Value, Estimand
// TSLP / IL-33 monotherapy context
// Cols: Company, Asset, Stage, Indication, Estimand, Notes

// ── GRIDS ────────────────────────────────────────────────────────
const grids = {};
function initGrids(d) {
 // ── TL1A: Catalyst Calendar ──────────────────────────────────────
 // Purpose: When do things read out? Drop Category (redundant on disease tab)
 // and Indication (same disease area). Stripped cols: 0=Category, 4=Indication
 // Resulting order: Program(0), Phase(1), Expected Timing(2), Primary Completion(3), _url(4), Notes(5)
 grids.tl1aReadouts = new gridjs.Grid({
 columns:[
 {name:'Program',width:'270px',formatter:readoutProgFmtClean},
 {name:'Phase',width:'58px',formatter:sf,sort:phaseSort},
 {name:'Expected Timing',width:'270px'},
 {name:'Primary Completion',width:'155px',sort:dateSort,formatter:(c,row)=>{const url=row.cells[4]&&row.cells[4].data;const txt=`<span style="font-size:10px">${c}</span>`;return url?gridjs.html(`<a class="ct-link" href="${url}" target="_blank" rel="noopener">${txt}</a>`):gridjs.html(txt);}},
 {name:'_url',hidden:true},
 {name:'Notes',width:'80px',sort:false,formatter:(c)=>{const esc=String(c).replace(/\\/g,'\\\\').replace(/'/g,"\\'");return gridjs.html(`<button class="note-btn" onclick="toggleNote('tl1a','${esc}',this)">▼ Notes</button>`);}}
 ],
 data:dropCols(d.tl1aReadouts,[0,4]).sort((a,b)=>phaseRank(a[1])-phaseRank(b[1])||parseDateKey(a[3])-parseDateKey(b[3])), sort:true
 }).render(document.getElementById('grid-tl1a-readouts'));

 // NOTE: TL1A Competitive Landscape and Technical Comparison grids removed —
 // superseded by the tl1aPI Program Intelligence table in the redesigned TL1A tab.

 // ── TSLP: Catalyst Calendar ──────────────────────────────────────
 // Same logic: drop Category(0) and Indication(4)
 grids.tslpReadouts = new gridjs.Grid({
 columns:[
 {name:'Program',width:'265px',formatter:readoutProgFmtClean},
 {name:'Phase',width:'58px',formatter:sf,sort:phaseSort},
 {name:'Expected Timing',width:'270px'},
 {name:'Primary Completion',width:'155px',sort:dateSort,formatter:(c,row)=>{const url=row.cells[4]&&row.cells[4].data;const txt=`<span style="font-size:10px">${c}</span>`;return url?gridjs.html(`<a class="ct-link" href="${url}" target="_blank" rel="noopener">${txt}</a>`):gridjs.html(txt);}},
 {name:'_url',hidden:true},
 {name:'Notes',width:'80px',sort:false,formatter:(c)=>{const esc=String(c).replace(/\\/g,'\\\\').replace(/'/g,"\\'");return gridjs.html(`<button class="note-btn" onclick="toggleNote('tslp','${esc}',this)">▼ Notes</button>`);}}
 ],
 data:dropCols(d.tslpReadouts,[0,4]).sort((a,b)=>phaseRank(a[1])-phaseRank(b[1])||parseDateKey(a[3])-parseDateKey(b[3])), sort:true
 }); {const _e=document.getElementById('grid-tslp-readouts');if(_e)grids.tslpReadouts.render(_e);}

 // ── TSLP: Competitive Landscape ──────────────────────────────────
 grids.tslpLandscape = new gridjs.Grid({
 columns:[
 {name:'Company',width:'160px'},
 {name:'Asset',width:'150px'},
 {name:'Format',width:'175px'},
 {name:'Stage',width:'155px',formatter:sf,sort:phaseSort},
 {name:'Partner / Deal Value',width:'235px'},
 {name:'Estimand',width:'155px',formatter:ef},
 {name:'Notes',width:'80px',sort:false,formatter:(c)=>{if(!c)return'';const esc=String(c).replace(/\\/g,'\\\\').replace(/'/g,"\\'");return gridjs.html(`<button class="note-btn" onclick="toggleNote('tslp-landscape','${esc}',this)">▼ Notes</button>`);}}
 ],
 data:mergeLandscape(d.tslpPipe, d.tslpMono).sort((a,b)=>phaseRank(a[3])-phaseRank(b[3])), sort:true
 }); {const _e=document.getElementById('grid-tslp-landscape');if(_e)grids.tslpLandscape.render(_e);}

 // helper to build a standard 2-table pair for new tabs
 function makeTabGrids(prefix, readoutsData, pipeData, monoData) {
 grids[prefix+'Readouts'] = new gridjs.Grid({
 columns:[
 {name:'Program',width:'265px',formatter:readoutProgFmtClean},
 {name:'Phase',width:'58px',formatter:sf,sort:phaseSort},
 {name:'Expected Timing',width:'260px'},
 {name:'Primary Completion',width:'155px',sort:dateSort,formatter:(c,row)=>{const url=row.cells[4]&&row.cells[4].data;const txt=`<span style="font-size:10px">${c}</span>`;return url?gridjs.html(`<a class="ct-link" href="${url}" target="_blank" rel="noopener">${txt}</a>`):gridjs.html(txt);}},
 {name:'_url',hidden:true},
 {name:'Notes',width:'80px',sort:false,formatter:(c)=>{const esc=String(c).replace(/\\/g,'\\\\').replace(/'/g,"\\'");return gridjs.html(`<button class="note-btn" onclick="toggleNote('${prefix}','${esc}',this)">▼ Notes</button>`);}}
 ],
 data:dropCols(readoutsData,[0,4]).sort((a,b)=>phaseRank(a[1])-phaseRank(b[1])||parseDateKey(a[3])-parseDateKey(b[3])), sort:true
 }); {const _e=document.getElementById('grid-'+prefix+'-readouts');if(_e)grids[prefix+'Readouts'].render(_e);}

 grids[prefix+'Landscape'] = new gridjs.Grid({
 columns:[
 {name:'Company',width:'160px'},
 {name:'Asset',width:'155px'},
 {name:'Format',width:'175px'},
 {name:'Stage',width:'155px',formatter:sf,sort:phaseSort},
 {name:'Partner / Deal Value',width:'230px'},
 {name:'Estimand',width:'150px',formatter:ef},
 {name:'Notes',width:'80px',sort:false,formatter:(c)=>{if(!c)return'';const esc=String(c).replace(/\\/g,'\\\\').replace(/'/g,"\\'");return gridjs.html(`<button class="note-btn" onclick="toggleNote('${prefix}-landscape','${esc}',this)">▼ Notes</button>`);}}
 ],
 data:mergeLandscape(pipeData, monoData).sort((a,b)=>phaseRank(a[3])-phaseRank(b[3])), sort:true
 }); {const _e=document.getElementById('grid-'+prefix+'-landscape');if(_e)grids[prefix+'Landscape'].render(_e);}
 }

 if (d.il4raTslpReadouts) makeTabGrids('il4ra-tslp', d.il4raTslpReadouts, d.il4raTslpPipe, d.il4raTslpMono);
 if (d.il4raOx40lReadouts) makeTabGrids('il4ra-ox40l', d.il4raOx40lReadouts, d.il4raOx40lPipe, d.il4raOx40lMono);
 if (d.igf1rTshrReadouts) makeTabGrids('igf1r-tshr', d.igf1rTshrReadouts, d.igf1rTshrPipe, d.igf1rTshrMono);
 if (d.fcrnReadouts) makeTabGrids('fcrn', d.fcrnReadouts, d.fcrnPipe, d.fcrnMono);
 if (d.aceReadouts) makeTabGrids('ace', d.aceReadouts, d.acePipe, d.aceMono);
}

// ── DEAL SPOTLIGHT TOGGLE ─────────────────────────────────────────
function toggleDealSpotlight(id) {
 const body = document.getElementById(id + '-body');
 const toggle = document.getElementById(id + '-toggle');
 if (!body) return;
 body.classList.toggle('open');
 if (toggle) toggle.classList.toggle('open');
}

// ── INTEL ITEM READ / MINIMIZE ────────────────────────────────────
function markIntelRead(btn) {
 const item = btn.closest('.intel-item');
 if (!item) return;
 const isRead = item.classList.toggle('intel-item-read');
 btn.textContent = isRead ? '↩ Expand' : '✓ Read';
}

// ── READOUT CATEGORY BADGE ────────────────────────────────────────
function rf(cell) {
 const s = String(cell);
 let c = 'rb-mono';
 if (s.includes('IL-23') || s.includes('bsAb') || s.includes('Bispecific') || s.includes('×')) c = 'rb-bspc';
 else if (s === 'Combination') c = 'rb-combo';
 else if (s === 'Anti-TSLP' || s === 'Anti-IL-33' || s === 'Anti-IL-33R') c = 'rb-mono';
 return gridjs.html(`<span class="rb ${c}">${s}</span>`);
}

// ── GENERIC COLLAPSIBLE TOGGLE ────────────────────────────────────
function toggleSection(id) {
 const body = document.getElementById(id + '-body');
 const toggle = document.getElementById(id + '-toggle');
 if (body) {
   const isOpen = body.style.display === 'block';
   body.style.display = isOpen ? 'none' : 'block';
 }
 if (toggle) toggle.classList.toggle('open');
}

// ── ESTIMAND TOGGLE ───────────────────────────────────────────────
function toggleEstimand(id) {
 const body = document.getElementById(id);
 const toggle = document.getElementById('toggle-' + id);
 body.classList.toggle('open');
 toggle.classList.toggle('open');
}

// ── TABS ─────────────────────────────────────────────────────────
const TAB_META = {
 home:         { name: 'Home',                badge: null,            cls: '' },
 live:         { name: 'Live Intelligence',   badge: 'LIVE',          cls: '' },
 atlas:        { name: 'Coverage Atlas',      badge: null,            cls: '' },
 tl1a:         { name: 'TL1A × IL-23p19',     badge: 'IBD',           cls: '' },
 tslp:         { name: 'TSLP × IL-33',         badge: 'Respiratory',   cls: '' },
 'il4ra-tslp': { name: 'IL-4Rα × TSLP',       badge: 'Type 2',        cls: 'ct-t2' },
 'il4ra-ox40l':{ name: 'IL-4Rα × OX40L',      badge: 'AD',            cls: 'ct-t2' },
 'igf1r-tshr': { name: 'IGF1R × TSHR',         badge: 'TED',           cls: 'ct-ted' },
 fcrn:         { name: 'FcRn Bispecific',       badge: 'Autoimmune',    cls: 'ct-ai' },
 ace:          { name: 'BCMA × CD19 × CD3',    badge: 'Immune Reset',  cls: 'ct-ir' },
 stocks:       { name: 'Market & Learning',     badge: null,            cls: '' },
 'meridian-issue':    { name: 'The Meridian',         badge: "Today's Issue",  cls: 'ct-ai' },
 'drugs-know':        { name: 'Drugs to Know',          badge: null,             cls: '' },
 /* DEPRECATED 2026-06-06: 'pharma-intel' tab retired (removed from nav). */
 'industry-insights': { name: 'Industry Insights',       badge: null,             cls: '' },
 ontology:            { name: 'Ontology Audit',           badge: null,             cls: '' },
};
function updateTabTitle(id) {
 const fallbackName = id.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
 const meta = TAB_META[id] || { name: fallbackName, badge: null, cls: '' };
 const nameEl = document.getElementById('tab-current-name');
 const titleEl = document.getElementById('tab-current-title');
 if (!nameEl || !titleEl) return;
 nameEl.textContent = meta.name;
 // Remove old badge
 const oldBadge = titleEl.querySelector('.tab-current-badge');
 if (oldBadge) oldBadge.remove();
 if (meta.badge) {
  const badge = document.createElement('span');
  badge.className = 'tab-current-badge ct ' + meta.cls;
  badge.textContent = meta.badge;
  nameEl.insertAdjacentElement('afterend', badge);
 }
 // Show/hide drug dropdown affordance
 const isDrug = !!(typeof TAB_AREA_MAP !== 'undefined' && TAB_AREA_MAP[id]);
 titleEl.classList.toggle('is-drug', isDrug);
 if (!isDrug) closeCenterDrugDD();
}

/* Area tab → the disease indications whose Patient Briefs to surface (North Star layer). */
const AREA_BRIEF_INDICATIONS = {
  'tl1a': ['Ulcerative Colitis', "Crohn's Disease", 'IBD (Inflammatory Bowel Disease)'],
  'tslp': ['Severe Asthma', 'COPD (Type-2 / eosinophilic)', 'Chronic Rhinosinusitis with Nasal Polyps'],
  'il4ra-tslp': ['Atopic Dermatitis', 'Severe Asthma', 'Chronic Rhinosinusitis with Nasal Polyps'],
  'il4ra-ox40l': ['Atopic Dermatitis'],
  'igf1r-tshr': ['Thyroid Eye Disease'],
  'fcrn': ['Generalized Myasthenia Gravis', 'CIDP'],
  'ace': ['Multiple Myeloma', 'Systemic Lupus Erythematosus (SLE)'],
};

/* ontology indication_id → Patient-Brief indication_name (for the drug-card Patient Context) */
const IND_PATIENT_NAME = {
  uc: 'Ulcerative Colitis', cd: "Crohn's Disease", ibd: 'IBD (Inflammatory Bowel Disease)',
  ted: 'Thyroid Eye Disease', ad: 'Atopic Dermatitis', asthma: 'Severe Asthma',
  copd: 'COPD (Type-2 / eosinophilic)', crswnp: 'Chronic Rhinosinusitis with Nasal Polyps',
  gmg: 'Generalized Myasthenia Gravis', mg: 'Generalized Myasthenia Gravis', cidp: 'CIDP',
  sle: 'Systemic Lupus Erythematosus (SLE)', psoriasis: 'Plaque Psoriasis', psa: 'Psoriatic Arthritis',
  hs: 'Hidradenitis Suppurativa', eoe: 'Eosinophilic Esophagitis (EoE)',
  chronic_urticaria: 'Chronic Spontaneous Urticaria', sjogren: "Sjögren's Disease",
};

/* ── Area-level Meridian briefs: Landscape, Landscape Analysis, Strategic Brief, Patient Briefs ──
   Surfaces the target-level (entity_type='target') + patient (entity_type='indication') narratives
   at the top of an area tab. Each block is collapsible; fails silent so a missing brief never breaks the tab. */
async function _loadAreaBriefs(tabId) {
  try {
    if (typeof _sb === 'undefined' && typeof SUPABASE_ANON === 'undefined') return;
    const areaId = (typeof TAB_AREA !== 'undefined' && TAB_AREA[tabId]) || tabId;
    const pane = document.getElementById('tab-' + tabId);
    if (!pane) return;
    // mount inside the content column (the fixed left pill-nav overlaps full-width content)
    const mount = pane.querySelector('.' + areaId + '-layout') || pane.querySelector('[class*="-layout"]') || pane;
    let host = document.getElementById('area-briefs-' + tabId);
    if (host && host.dataset.loaded === '1') return;     // once per tab
    if (!host) {
      host = document.createElement('div');
      host.id = 'area-briefs-' + tabId;
      host.style.margin = '0 0 14px';
      mount.insertBefore(host, mount.firstChild);
    }
    const base = (typeof SUPABASE_URL !== 'undefined' ? SUPABASE_URL : 'https://tghntyofptvfhmtchwcv.supabase.co') + '/rest/v1';
    const hdr = { apikey: SUPABASE_ANON, Authorization: 'Bearer ' + SUPABASE_ANON };
    const q = async u => { try { return await (await fetch(base + u, { headers: hdr })).json(); } catch (e) { return []; } };

    const tgt = await q('/entity_narratives?entity_type=eq.target&entity_id=eq.' + encodeURIComponent(areaId) +
      '&section=in.(overview,intelligence,business)&select=section,body_md,generated_at,stale');
    const inds = AREA_BRIEF_INDICATIONS[tabId] || [];
    let pats = [];
    if (inds.length) {
      const list = inds.map(n => '"' + n.replace(/"/g, '') + '"').join(',');
      pats = await q('/entity_narratives?entity_type=eq.indication&section=eq.overview&entity_id=in.(' +
        encodeURIComponent(list) + ')&select=entity_id,body_md');
    }
    if ((!tgt || !tgt.length) && (!pats || !pats.length)) { host.dataset.loaded = '1'; return; }

    const byS = {}; (tgt || []).forEach(r => byS[r.section] = r);
    const block = (icon, label, tagText, tagCol, body, open) => !body ? '' :
      `<details ${open ? 'open' : ''} style="margin-bottom:8px"><summary style="cursor:pointer;font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:${tagCol};outline:none">${icon} ${label}${tagText ? ` <span style="font-weight:700;color:#94a3b8;text-transform:none;letter-spacing:0">· ${tagText}</span>` : ''}</summary><div style="margin-top:7px">${_mdMeridian(body)}</div></details>`;

    let inner = '';
    if (byS.business) inner += block('🧭', 'Meridian Strategic Brief', 'BD priorities · interpretation', '#6d28d9', byS.business.body_md, true);
    if (byS.overview) inner += block('🗺', 'Landscape', 'derived · cited', '#4f46e5', byS.overview.body_md, false);
    if (byS.intelligence) inner += block('📊', 'Landscape Analysis', 'interpretation', '#6d28d9', byS.intelligence.body_md, false);
    (pats || []).forEach(p => {
      inner += block('🧑‍⚕️', 'Patient Brief — ' + (p.entity_id || ''), 'North Star · derived · cited', '#0369a1', p.body_md, false);
    });
    if (!inner) { host.dataset.loaded = '1'; return; }

    host.innerHTML =
      `<div style="background:linear-gradient(180deg,#fbfcff,#f7f9ff);border:1px solid #dbe4ff;border-left:3px solid #4f6ef7;border-radius:10px;padding:13px 15px">
         <div style="font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:0.07em;color:#3730a3;margin-bottom:9px">◎ Meridian — Landscape, Strategy & Patient</div>
         ${inner}
       </div>`;
    host.dataset.loaded = '1';
  } catch (e) { /* silent */ }
}

/* ── DRUG card renderer ──────────────────────────────────────────── */
/* ── Meridian Narrative loader — the prose read layer (v70 entity_narratives) ──
   Fetches the derived, cited overview narrative + its provenance and renders it
   as the prose face of the drug card. Every clause carries a [n] citation that
   maps to a source in the footnote list. Fails silently (leaves placeholder empty)
   so a missing narrative never breaks the card. */
async function _loadMeridianNarrative(drugId) {
  const host = document.getElementById('meridian-narrative-' + drugId);
  if (!host) return;
  try {
    const base = (typeof SUPABASE_URL !== 'undefined' ? SUPABASE_URL : 'https://tghntyofptvfhmtchwcv.supabase.co') + '/rest/v1';
    const hdr  = { apikey: SUPABASE_ANON, Authorization: 'Bearer ' + SUPABASE_ANON };
    const secs = await (await fetch(base + '/entity_narratives?entity_type=eq.drug&entity_id=eq.' + encodeURIComponent(drugId) + '&section=in.(overview,intelligence)&select=id,section,body_md,generated_at,stale', { headers: hdr })).json();
    if (!Array.isArray(secs) || !secs.length) return;
    // data-quality / trust score badge
    let tsBadge = '';
    try {
      const ts = (await (await fetch(base + '/drug_trust_scores?drug_id=eq.' + encodeURIComponent(drugId) + '&select=score,grade', { headers: hdr })).json())[0];
      if (ts) {
        const c = ts.score >= 90 ? ['#dcfce7', '#166534', '#86efac'] : ts.score >= 75 ? ['#fef9c3', '#854d0e', '#fde68a'] : ['#fee2e2', '#991b1b', '#fecaca'];
        tsBadge = `<span title="Data-quality / trust score (0–100): how complete and verified this profile is." style="background:${c[0]};color:${c[1]};border:1px solid ${c[2]};border-radius:4px;padding:1px 5px;font-size:8px;font-weight:800;text-transform:uppercase">Trust ${ts.grade} ${ts.score}</span>`;
      }
    } catch (e) {}
    const esc = s => (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    // ── Depth-of-trust signals: independence (v74), agreement/conflicts (v74), gaps (v76) ──
    let indepBadge = '', conflictChip = '', gapChip = '', conflictDetails = '';
    try {
      const ind = await (await fetch(base + '/narrative_independence?entity_id=eq.' + encodeURIComponent(drugId) + '&entity_type=eq.drug&select=multi_domain_claims,independent_claims,peer_reviewed_claims', { headers: hdr })).json();
      if (Array.isArray(ind) && ind.length) {
        const best = ind.reduce((a, b) => (b.independent_claims > (a ? a.independent_claims : -1) ? b : a), null);
        if (best) indepBadge = `<span title="Corroboration depth. Independent = a claim backed across ≥2 domains including a peer-reviewed/regulatory source; multi-source = ≥2 domains." style="background:#ecfeff;color:#155e75;border:1px solid #a5f3fc;border-radius:4px;padding:1px 5px;font-size:8px;font-weight:800;text-transform:uppercase">${best.independent_claims} indep · ${best.multi_domain_claims} multi-src</span>`;
      }
    } catch (e) {}
    try {
      const vc = await (await fetch(base + '/narrative_value_conflicts?drug_id=eq.' + encodeURIComponent(drugId) + '&select=metric,timepoint_weeks,dose_norm,value_min,value_max,delta', { headers: hdr })).json();
      if (Array.isArray(vc) && vc.length) {
        conflictChip = `<span title="Sources disagree on a reported value — surfaced, not smoothed." style="background:#fee2e2;color:#991b1b;border:1px solid #fecaca;border-radius:4px;padding:1px 5px;font-size:8px;font-weight:800;text-transform:uppercase">⚠ ${vc.length} disagreement${vc.length > 1 ? 's' : ''}</span>`;
        conflictDetails = `<details style="margin-top:8px"><summary style="font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:#b91c1c;cursor:pointer">Source disagreements (${vc.length})</summary><ul style="margin:6px 0 0;padding-left:4px;list-style:none">` +
          vc.map(c => `<li style="margin:2px 0;font-size:10px;color:#7f1d1d">${esc((c.metric || '').replace(/_/g, ' '))}${c.timepoint_weeks ? ` wk${c.timepoint_weeks}` : ''} (${esc(c.dose_norm || '')}): <b>${c.value_min}%</b> vs <b>${c.value_max}%</b> (Δ${c.delta})</li>`).join('') +
          `</ul></details>`;
      }
    } catch (e) {}
    try {
      const gaps = await (await fetch(base + '/source_collection_queue?entity_id=eq.' + encodeURIComponent(drugId) + '&entity_type=eq.drug&status=eq.open&select=id', { headers: hdr })).json();
      if (Array.isArray(gaps) && gaps.length) gapChip = `<span title="Fact-bearing claims with no independent source yet — queued for collection." style="background:#fef9c3;color:#854d0e;border:1px solid #fde68a;border-radius:4px;padding:1px 5px;font-size:8px;font-weight:800;text-transform:uppercase">${gaps.length} source gap${gaps.length > 1 ? 's' : ''}</span>`;
    } catch (e) {}
    // markdown -> html. Citations [n] become HYPERLINKED superscripts straight to the source
    // (Kyle 2026-06-07: links, not bracketed numbers). provMap: claim_index -> {url,title}.
    const renderBody = (md, provMap) => {
      let h = esc(md);
      h = h.replace(/^\s*-{3,}\s*$/gm, '');                       // stray --- rules
      // Citations link the PROSE itself (Kyle 2026-06-07): the phrase before [n] becomes the
      // hyperlink. Up to 6 trailing words, never crossing sentence punctuation or brackets.
      // Extra co-citations on the same claim become tiny superscript "+" links; un-sourced
      // claims get no marker at all — provenance stays in the Sources drawer.
      h = h.replace(/((?:[^\s.;:!?()\[\]]+(?:\s+|$)){1,6})?\s*\[([\d,–—\- ]+)\]/g, (m, phrase, g) => {
        const nums = g.split(/[^\d]+/).filter(Boolean);
        const srcs = nums.map(n => (provMap && provMap[n]) || null);
        const first = srcs.find(s => s && s.url);
        phrase = phrase || '';
        const trail = phrase.endsWith(' ') ? ' ' : '';
        const extra = srcs.filter(s => s && s.url && s !== first).slice(0, 3)
          .map(s => `<sup style="font-size:8.5px;font-weight:700"><a href="${s.url}" target="_blank" rel="noopener" title="${s.title}" style="color:#93a8c8;text-decoration:none">+</a></sup>`).join('');
        if (first && phrase.trim()) {
          return `<a href="${first.url}" target="_blank" rel="noopener" title="${first.title}" style="color:#1d4ed8;text-decoration:none;border-bottom:1px solid #bfdbfe">${phrase.trim()}</a>${extra}${trail}`;
        }
        if (first) return `<sup style="font-size:9px;font-weight:600"><a href="${first.url}" target="_blank" rel="noopener" title="${first.title}" style="color:#2563eb;text-decoration:none">↗</a></sup>${extra}`;
        return phrase; // no sourced URL — keep the prose clean, no dangling number
      });
      h = h.replace(/^###\s+(.*)$/gm, '<div style="font-size:9.5px;font-weight:800;text-transform:uppercase;letter-spacing:0.07em;color:#64748b;margin:13px 0 4px">$1</div>');
      h = h.replace(/^##\s+(.*)$/gm, '<div style="font-size:13px;font-weight:700;color:#1e293b;margin:4px 0 8px">$1</div>');
      h = h.replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
      h = h.replace(/^_(.*)_\s*$/gm, '<em style="color:#6d28d9;font-style:italic">$1</em>');
      return h.split(/\n{2,}/).map(p => { p = p.trim(); if (!p) return '';
        return p.match(/^<(div|em)/)
          ? p : `<p style="font-size:12.5px;color:#243044;line-height:1.62;margin:0 0 9px;max-width:78ch">${p.replace(/\n/g, ' ')}</p>`; }).join('');
    };
    // claim_index -> first sourced row (for citation hyperlinks)
    const provMapOf = prov => {
      const m = {};
      (Array.isArray(prov) ? prov : []).forEach(p => {
        if (m[p.claim_index]) return;
        const dom = p.source_url ? (p.source_url.split('/')[2] || '') : '';
        m[p.claim_index] = { url: p.source_url || '',
          title: ((dom ? dom + ' — ' : '') + (p.claim_text || '')).slice(0, 140).replace(/"/g, '&quot;') };
      });
      return m;
    };
    const provFor = async id => await (await fetch(base + '/narrative_provenance?narrative_id=eq.' + id + '&select=claim_index,claim_text,source_url,source_table,independence_tier&order=claim_index,tier_rank.desc', { headers: hdr })).json().catch(() => []);
    // tier dot: peer-reviewed/regulatory green, registry blue, independent news teal, sponsor amber, internal gray
    const tierDot = t => {
      const c = (t === 'peer_reviewed' || t === 'regulatory') ? '#16a34a' : t === 'registry' ? '#2563eb'
        : t === 'independent_news' ? '#0d9488' : t === 'sponsor' ? '#d97706' : '#94a3b8';
      return `<span title="${t || 'source'}" style="display:inline-block;width:6px;height:6px;border-radius:50%;background:${c};margin-right:4px;vertical-align:middle"></span>`;
    };
    // group provenance rows by claim_index so a triangulated claim shows all its sources
    const foot = prov => {
      const byIdx = {};
      (Array.isArray(prov) ? prov : []).forEach(p => { (byIdx[p.claim_index] = byIdx[p.claim_index] || []).push(p); });
      return Object.keys(byIdx).map(k => {
        const rows = byIdx[k];
        const srcs = rows.map(p => {
          const dom = p.source_url ? (p.source_url.split('/')[2] || 'source') : (p.source_table || 'graph');
          const link = p.source_url ? `<a href="${p.source_url}" target="_blank" rel="noopener" style="color:#2563eb;text-decoration:none">${dom}↗</a>` : `<span style="color:#64748b">${dom}</span>`;
          return `${tierDot(p.independence_tier)}${link}`;
        }).join(' · ');
        return `<li style="margin:2px 0;font-size:10px;color:#475569"><b style="color:#94a3b8">[${k}]</b> ${esc(rows[0].claim_text).slice(0, 90)} — ${srcs}${rows.length > 1 ? ` <span style="color:#16a34a;font-weight:700">✓${rows.length}×</span>` : ''}</li>`;
      }).join('');
    };
    const ov = secs.find(s => s.section === 'overview');
    const an = secs.find(s => s.section === 'intelligence');
    let html = '';
    if (ov && ov.body_md) {
      const prov = await provFor(ov.id);
      html += `<div style="background:linear-gradient(180deg,#fbfcff,#f6f8ff);border:1px solid #dbe4ff;border-left:3px solid #4f6ef7;border-radius:8px;padding:12px 14px;margin-bottom:10px">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:7px">
          <span style="font-size:8.5px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#4f46e5">📖 Meridian Narrative</span>
          <span style="background:#eef2ff;color:#4338ca;border:1px solid #c7d2fe;border-radius:4px;padding:1px 5px;font-size:8px;font-weight:800;text-transform:uppercase" title="Generated from the knowledge graph; every clause cites a source.">Derived · Cited</span>
          ${tsBadge}
          ${indepBadge}
          ${conflictChip}
          ${gapChip}
          ${ov.stale ? '<span style="background:#fef3c7;color:#b45309;border:1px solid #fde68a;border-radius:4px;padding:1px 5px;font-size:8px;font-weight:800;text-transform:uppercase">Stale</span>' : ''}
          <span style="margin-left:auto;font-size:9px;color:#94a3b8">${(ov.generated_at || '').slice(0, 10)}</span>
        </div>
        ${renderBody(ov.body_md, provMapOf(prov))}
        ${conflictDetails}
        ${foot(prov) ? `<details style="margin-top:8px"><summary style="font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:#64748b;cursor:pointer">Sources (${prov.length})</summary><ul style="margin:6px 0 0;padding-left:4px;list-style:none">${foot(prov)}</ul></details>` : ''}
      </div>`;
    }
    if (an && an.body_md) {
      const prov = await provFor(an.id);
      html += `<div style="background:linear-gradient(180deg,#fcfbff,#f8f5ff);border:1px solid #ddd6fe;border-left:3px solid #7c3aed;border-radius:8px;padding:12px 14px;margin-bottom:10px">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:7px">
          <span style="font-size:8.5px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#6d28d9">🧭 Meridian Analysis</span>
          <span style="background:#f5f3ff;color:#6d28d9;border:1px solid #ddd6fe;border-radius:4px;padding:1px 5px;font-size:8px;font-weight:800;text-transform:uppercase" title="Interpretation by Meridian, grounded in the cited facts. Not a sourced fact.">Interpretation</span>
        </div>
        ${renderBody(an.body_md, provMapOf(prov))}
        ${foot(prov) ? `<details style="margin-top:8px"><summary style="font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:#64748b;cursor:pointer">Basis (${prov.length} facts)</summary><ul style="margin:6px 0 0;padding-left:4px;list-style:none">${foot(prov)}</ul></details>` : ''}
      </div>`;
    }
    // Patient Context — the lead indication's Meridian Patient Brief (North Star layer)
    try {
      const di = await (await fetch(base + '/drug_indications?drug_id=eq.' + encodeURIComponent(drugId) +
        '&select=indication_id,is_lead_indication&order=is_lead_indication.desc.nullslast', { headers: hdr })).json();
      const iid = Array.isArray(di) && di.length ? di[0].indication_id : null;
      const nm = iid && IND_PATIENT_NAME[iid];
      if (nm) {
        const pb = (await (await fetch(base + '/entity_narratives?entity_type=eq.indication&section=eq.overview&entity_id=eq.' +
          encodeURIComponent(nm) + '&select=body_md', { headers: hdr })).json())[0];
        if (pb && pb.body_md) {
          html += `<details style="background:linear-gradient(180deg,#f7fdff,#eff8ff);border:1px solid #bae6fd;border-left:3px solid #0ea5e9;border-radius:8px;padding:12px 14px;margin-bottom:10px">
            <summary style="cursor:pointer;font-size:8.5px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#0369a1;outline:none">🧑‍⚕️ Patient Context — ${esc(nm)} <span style="font-weight:700;color:#94a3b8;text-transform:none;letter-spacing:0">· North Star · derived · cited</span></summary>
            <div style="margin-top:8px">${_mdMeridian(pb.body_md)}</div></details>`;
        }
      }
    } catch (e) {}
    host.innerHTML = html;
  } catch (e) { /* silent — leave placeholder empty if narrative unavailable */ }
}

function _cemDrugBody(drug, areas, trials, molData, companyName, drugDeals, normData, drugNews, drugCatalysts, ownerData, cascadeRisk, transferChain, geoApprovals, drugSources, extData, intelFacts) {
  // Research Intelligence — facts extracted from submitted research (Cowen/Wedbush/etc.), grouped by type
  const _ifRows = (intelFacts || []).filter(f => f && f.claim);
  const _IF_TYPE = {clinical:'🧪 Clinical', competitive:'⚔️ Competitive', pipeline:'🔬 Pipeline', commercial:'💰 Commercial',
    market:'📊 Market', regulatory:'📋 Regulatory', patient:'👤 Patient', management:'🗣️ Management', deal:'🤝 Deal', catalyst:'📅 Catalyst'};
  const _ifByType = {};
  _ifRows.forEach(f => { (_ifByType[f.fact_type] = _ifByType[f.fact_type] || []).push(f); });
  const _ifHtml = _ifRows.length ? `<div class="cem-det-inner">
    <div class="cem-det-title">Research Intelligence — ${_ifRows.length} fact${_ifRows.length!==1?'s':''} from submitted reports</div>
    ${Object.entries(_ifByType).map(([t, fs]) => `<div style="margin-bottom:8px">
      <div style="font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:.4px;margin-bottom:3px">${_IF_TYPE[t]||t} (${fs.length})</div>
      ${fs.slice(0,12).map(f => {
        const v = (f.value_num!=null) ? ` <b style="color:#1d4ed8">${f.value_num}${f.unit?' '+f.unit:''}</b>` : '';
        const lk = f.source_url ? `<a href="${f.source_url}" target="_blank" rel="noopener" data-trusted="1" style="color:#94a3b8;text-decoration:none;font-size:9px">↗${f.page_ref?' '+f.page_ref:''}</a>` : '';
        return `<div style="font-size:11.5px;color:#1e293b;line-height:1.4;margin-bottom:2px">• ${f.claim}${v} ${lk}</div>`;
      }).join('')}
      ${fs.length>12?`<div style="font-size:10px;color:#94a3b8">+${fs.length-12} more — see 📑 Docs</div>`:''}
    </div>`).join('')}
  </div>` : '';
  if (!drug) return '<div style="padding:30px;text-align:center;color:#94a3b8;font-size:13px">Drug data not available.</div>';
  const _CEM_AMAP = {tl1a:'TL1A',tslp:'TSLP',il4ra:'IL-4Rα',igf1r:'IGF1R/TSHR',fcrn:'FcRn',tcell:'BCMA/CD19/CD3',ox40l:'OX40L',ibd:'IBD',atopy:'Atopy',respiratory:'Respiratory',
    // drug_competitive_scores indication context_ids (IBD expansion + TED)
    uc:'UC', cd:'CD', ted:'TED', autoimmune:'Autoimmune'};
  // ── Phase 5 Candidate 3 — normalized relationship label maps ─────────────────
  const _IND_LABEL = {
    uc:'Ulcerative Colitis', cd:"Crohn's Disease", ted:'Thyroid Eye Disease',
    ad:'Atopic Dermatitis', asthma:'Asthma', copd:'COPD', crswnp:'CRSwNP',
    ra:'Rheumatoid Arthritis', sle:'Lupus (SLE)', gmg:'Generalized MG',
    cidp:'CIDP', igg4rd:'IgG4-RD', mg:'Myasthenia Gravis', hs:'Hidradenitis Suppurativa',
    eoe:'EoE', chronic_urticaria:'Chronic Urticaria', psc:'PSC',
    iga_nephropathy:'IgAN', eoe_adult:'EoE', eos_esophagitis:'EoE',
  };
  const _TARGET_LABEL = {
    tl1a:'TL1A', tslp:'TSLP', il4ra:'IL-4Rα', fcrn:'FcRn',
    igf1r:'IGF1R', tshr:'TSHR', bcma:'BCMA', cd19:'CD19', cd3:'CD3',
    il13:'IL-13', il5:'IL-5', il33:'IL-33', ox40l:'OX40L', ox40:'OX40',
    il23p19:'IL-23p19', il12p40:'IL-12/23p40', il23:'IL-23',
  };

  const drugName = drug.display_name || drug.name || 'Unknown drug';
  const mechanism = drug.mechanism || '';
  const target    = drug.target    || '';
  const cls       = drug.cls       || '';
  const phase     = drug.stage     || drug.phase || '';
  const overlap   = areas?.[0]?.overlap || drug.overlap || '';
  const vsAilux   = areas?.[0]?.overlap_rationale || drug.vs_ailux || drug.differentiation_thesis || '';
  const summary   = drug.drug_summary || '';
  const diff      = drug.differentiation_thesis || '';

  // Summary stats
  const trialCount  = (trials||[]).length;
  const upfront     = drug.upfront_usd_m;
  const total       = drug.total_usd_m;
  const overlapTier = overlap || '—';

  const dealValDisplay = upfront ? (parseFloat(upfront)>=1000?`$${(parseFloat(upfront)/1000).toFixed(1)}B`:`$${Math.round(upfront)}M upfront`) : (total ? (parseFloat(total)>=1000?`$${(parseFloat(total)/1000).toFixed(1)}B`:`$${Math.round(total)}M total`) : '—');

  const statsHtml = `<div class="cem-stats">
    <div class="cem-stat"><div class="cem-stat-lbl">Deal value</div><div class="cem-stat-val">${dealValDisplay}</div><div class="cem-stat-sub">${upfront&&total?`$${parseFloat(total)>=1000?(parseFloat(total)/1000).toFixed(1)+'B':Math.round(total)+'M'} total`:'Best available'}</div></div>
    <div class="cem-stat"><div class="cem-stat-lbl">Overlap tier</div><div class="cem-stat-val" style="color:${overlap?.toLowerCase()==='direct'?'#b91c1c':overlap?.toLowerCase()==='adjacent'?'#1d4ed8':'#15803d'}">${overlapTier}</div><div class="cem-stat-sub">vs Ailux strategy</div></div>
    <div class="cem-stat"><div class="cem-stat-lbl">Active trials</div><div class="cem-stat-val">${trialCount}</div><div class="cem-stat-sub">${trialCount===1?'1 trial found':`${trialCount} trials found`}</div></div>
    <div class="cem-stat"><div class="cem-stat-lbl">Areas tracked</div><div class="cem-stat-val">${(areas||[]).length || 1}</div><div class="cem-stat-sub">disease areas</div></div>
  </div>
  <div style="text-align:center;margin:8px 0 2px"><a onclick="askMeridian('${String(drug.display_name||drug.name||'').replace(/['\\]/g,'')}')" style="cursor:pointer;font-size:12px;font-weight:700;color:#1e3a5f;border:1px solid #dbe4ee;border-radius:9px;padding:7px 14px;display:inline-block;background:#fff">◇ Ask Meridian about this ↗</a></div>`;

  // Meridian Interpretation
  const interpDots = [];
  if (vsAilux) interpDots.push({ col:'#dc2626', text: vsAilux });
  if (diff)    interpDots.push({ col:'#7c3aed', text: diff });
  if (summary) interpDots.push({ col:'#059669', text: summary });
  if (mechanism && !interpDots.length) interpDots.push({ col:'#0284c7', text: `Mechanism: ${mechanism}` });

  const interpSummaryHtml = interpDots.map(d =>
    `<div class="cem-interp-dot"><span style="width:7px;height:7px;border-radius:50%;background:${d.col};flex-shrink:0;margin-top:4px"></span><div>${d.text}</div></div>`
  ).join('');

  const interpDetailHtml = `<div class="cem-det-inner">
    <div class="cem-det-title">Facts generating this interpretation</div>
    ${mechanism ? `<div class="cem-fact"><span class="cem-fact-lbl">Mechanism</span><span class="cem-fact-val">${mechanism}</span></div>` : ''}
    ${target ? `<div class="cem-fact"><span class="cem-fact-lbl">Target</span><span class="cem-fact-val">${target}</span></div>` : ''}
    ${cls ? `<div class="cem-fact"><span class="cem-fact-lbl">Class</span><span class="cem-fact-val">${cls}</span></div>` : ''}
    ${drug.route ? `<div class="cem-fact"><span class="cem-fact-lbl">Route</span><span class="cem-fact-val">${drug.route}</span></div>` : ''}
    ${drug.indication_short ? `<div class="cem-fact"><span class="cem-fact-lbl">Indication</span><span class="cem-fact-val">${drug.indication_short}</span></div>` : ''}
    ${areas?.length ? areas.map(a => {
      const lbl = (_CEM_AMAP[a.area_id]||a.area_id);
      return `<div class="cem-fact"><span class="cem-fact-lbl">${lbl} overlap</span><span class="cem-fact-val">${_cemOverlapPill(a.overlap)} ${a.overlap_rationale ? '— '+a.overlap_rationale.slice(0,120) : ''}</span></div>`;
    }).join('') : ''}
  </div>`;

  const interpHtml = `<div class="cem-interp">
    <div class="cem-interp-hd" onclick="_cemToggle('dr-interp')"><span>🧠 Meridian interpretation</span><span style="font-size:9px;color:#7c3aed;margin-left:auto">See underlying data <i id="cem-chev-dr-interp" class="cem-chev">▶</i></span></div>
    <div class="cem-interp-dots">${interpSummaryHtml}</div>
    <div class="cem-det" id="cem-det-dr-interp">${interpDetailHtml}</div>
  </div>`;

  // Trials section
  // ── Phase 5 Candidate 3 — trial indication ontology map (normalized) ─────────
  // DEPRECATED 2026-06-07 — _trialIndMap pills no longer render: trial_indications is
  // keyed by legacy trials.id and the modal now reads trial_facts (different UUIDs).
  const _trialIndMap = {};
  (normData?.trialInds || []).forEach(ti => {
    if (!_trialIndMap[ti.trial_id]) _trialIndMap[ti.trial_id] = [];
    _trialIndMap[ti.trial_id].push(ti.indication_id);
  });
  // 2026-06-07: trials come from trial_facts — link via stored source_url first,
  // falling back to a constructed CT.gov study URL from the NCT id (never a fake URL).
  const _tfLink = (label, t) => t?.source_url
    ? `<a class="cem-link" href="${t.source_url}" target="_blank" rel="noopener">${label}</a>`
    : _cemTrialLink(label, t?.nct_id);
  const trialSummary = (trials||[]).slice(0,3).map(t => {
    return `
    <div class="cem-item-row">
      ${_cemPhasePill(t.phase)}
      <div>
        <div style="font-size:12px;font-weight:600;color:#0f172a">${_tfLink((t.trial_name||t.indication||'Trial').slice(0,90), t)}</div>
        <div style="font-size:10.5px;color:#64748b">${t.indication||''} ${t.status?'· '+t.status:''}${t.n_enrollment?` · N=${t.n_enrollment}`:''}</div>
      </div>
    </div>`;
  }).join('');

  const trialDetail = `<div class="cem-det-inner">
    <div class="cem-det-title">Full trial detail — ClinicalTrials.gov</div>
    <table class="cem-tbl"><thead><tr><th>Phase</th><th>Trial</th><th>Indication</th><th>Status</th><th>N</th><th>Dates</th></tr></thead><tbody>
    ${(trials||[]).map(t => `<tr>
      <td>${_cemPhasePill(t.phase)}</td>
      <td>${_tfLink((t.trial_name||'—').slice(0,80), t)}${t.why_stopped?`<div style="font-size:9.5px;color:#b91c1c">Stopped: ${(t.why_stopped||'').slice(0,80)}</div>`:''}</td>
      <td style="color:#64748b">${t.indication||'—'}</td>
      <td style="color:#64748b">${t.status||'—'}</td>
      <td style="color:#64748b">${t.n_enrollment||'—'}</td>
      <td style="color:#64748b;font-size:10px;white-space:nowrap">${[t.start_date?t.start_date.slice(0,7):'', t.completion_date?'→ '+t.completion_date.slice(0,7):''].filter(Boolean).join(' ')||'—'}</td>
    </tr>`).join('')}
    </tbody></table>
    ${(trials||[]).filter(t=>t.primary_endpoint).slice(0,3).map(t =>
      `<div style="margin-top:8px;padding:8px;background:white;border-radius:6px;border:0.5px solid #e2e8f0"><div style="font-size:10px;color:#94a3b8;margin-bottom:3px">${_tfLink(t.trial_name||t.nct_id||'Trial', t)} — Primary endpoint</div><div style="font-size:11px;color:#1e293b">${(t.primary_endpoint||'').slice(0,200)}</div></div>`
    ).join('')}
  </div>`;

  // Competitive position section
  // DEPRECATED 2026-06-07 — compSummary/compDetail were already unreferenced by the
  // assembly (relSummary/relDetail render the competitive view); kept for reference.
  const compSummary = (areas||[]).slice(0,3).map(a => `
    <div class="cem-item-row">
      <div style="flex:1">
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:2px">
          <span style="font-size:11px;font-weight:600;color:#0f172a">${(_CEM_AMAP[a.area_id]||a.area_id)}</span>
          ${_cemOverlapPill(a.overlap)}
        </div>
        ${a.overlap_rationale ? `<div style="font-size:11px;color:#64748b;line-height:1.4">${a.overlap_rationale.slice(0,100)}</div>` : ''}
      </div>
    </div>`).join('');

  const compDetail = `<div class="cem-det-inner">
    <div class="cem-det-title">Overlap rationale per area</div>
    ${(areas||[]).map(a => `
      <div style="margin-bottom:10px">
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
          <span style="font-size:11px;font-weight:600">${(_CEM_AMAP[a.area_id]||a.area_id)}</span>
          ${_cemOverlapPill(a.overlap)}
        </div>
        ${a.overlap_rationale ? `<div style="font-size:11px;color:#1e293b;line-height:1.5">${a.overlap_rationale}</div>` : ''}
        ${a.strategic_role ? `<div style="font-size:11px;color:#64748b;margin-top:3px"><strong>Strategic role:</strong> ${a.strategic_role}</div>` : ''}
        ${a.source_url ? `<div style="margin-top:4px"><a class="cem-link" href="${a.source_url}" target="_blank" rel="noopener" style="font-size:10px">↗ Source</a></div>` : ''}
      </div>`).join('')}
  </div>`;

  // Molecule intel section (signals / bd_angle / risk_summary)
  const bdAngle    = molData?.bd_angle     || '';
  const riskSum    = molData?.risk_summary  || '';
  const sigSummary = (bdAngle || riskSum)
    ? `<div style="font-size:12px;color:#1e293b;line-height:1.5;margin-bottom:6px">${bdAngle||riskSum}</div>`
    : '<div style="font-size:11px;color:#94a3b8;font-style:italic">No molecule intelligence enriched yet.</div>';

  const sigDetail = molData ? `<div class="cem-det-inner">
    <div class="cem-det-title">Molecule intelligence detail</div>
    ${bdAngle  ? `<div class="cem-fact"><span class="cem-fact-lbl">BD angle</span><span class="cem-fact-val">${bdAngle}</span></div>` : ''}
    ${riskSum  ? `<div class="cem-fact"><span class="cem-fact-lbl">Risk summary</span><span class="cem-fact-val">${riskSum}</span></div>` : ''}
    ${molData.format ? `<div class="cem-fact"><span class="cem-fact-lbl">Format</span><span class="cem-fact-val">${molData.format}</span></div>` : ''}
    ${molData.half_life ? `<div class="cem-fact"><span class="cem-fact-lbl">Half-life</span><span class="cem-fact-val">${molData.half_life}</span></div>` : ''}
    ${molData.dosing_interval ? `<div class="cem-fact"><span class="cem-fact-lbl">Dosing</span><span class="cem-fact-val">${molData.dosing_interval}</span></div>` : ''}
  </div>` : '<div class="cem-det-inner"><div style="font-size:11px;color:#94a3b8">No molecule intelligence data yet — run enrichment to populate.</div></div>';

  // ── Phase 5 Candidate 3 — Normalized Targets section ─────────────────────────
  const _normTargets = normData?.targets || [];
  // Declutter 2026-06-07: confidence % + review-status pills removed from the summary
  // view (plumbing) — they remain in the expandable detail table below.
  const normTargetsSummary = _normTargets.slice(0,4).map(t => {
    const tLbl = _TARGET_LABEL[t.target_id] || t.target_id.toUpperCase();
    return `<div class="cem-item-row"><div style="flex:1"><div style="font-size:12px;font-weight:600;color:#0f172a">${tLbl}</div></div></div>`;
  }).join('') || '<span style="font-size:11px;color:#94a3b8;font-style:italic">No target relationships in normalized table.</span>';
  const normTargetsDetail = `<div class="cem-det-inner">
    <div class="cem-det-title">drug_targets — normalized relationship data</div>
    <table class="cem-tbl"><thead><tr><th>Target</th><th>Confidence</th><th>Review status</th></tr></thead><tbody>
    ${_normTargets.map(t => `<tr>
      <td style="font-weight:600">${_TARGET_LABEL[t.target_id]||t.target_id.toUpperCase()}</td>
      <td style="color:#64748b">${t.confidence_score != null ? Math.round(t.confidence_score)+'%' : '—'}</td>
      <td style="color:#64748b">${t.review_status||'—'}</td>
    </tr>`).join('')}
    </tbody></table>
  </div>`;

  // ── Phase 5 Candidate 3 — Normalized Indications section ─────────────────────
  const _normInds = normData?.indications || [];
  // Declutter 2026-06-07: confidence % pill removed from the summary view (plumbing) —
  // it remains in the expandable detail table below. Stage pill kept (real signal).
  const normIndsSummary = _normInds.slice(0,4).map(i => {
    const iLbl = _IND_LABEL[i.indication_id] || i.indication_id.toUpperCase();
    const stagePill = i.development_stage
      ? `<span style="font-size:9px;background:#f0fdf4;color:#15803d;border-radius:4px;padding:1px 5px;margin-left:4px">${i.development_stage}</span>` : '';
    return `<div class="cem-item-row"><div style="flex:1"><div style="font-size:12px;font-weight:600;color:#0f172a">${iLbl}</div></div>${stagePill}</div>`;
  }).join('') || '<span style="font-size:11px;color:#94a3b8;font-style:italic">No indication relationships in normalized table.</span>';
  const normIndsDetail = `<div class="cem-det-inner">
    <div class="cem-det-title">drug_indications — normalized relationship data</div>
    <table class="cem-tbl"><thead><tr><th>Indication</th><th>Stage</th><th>Confidence</th><th>Status</th></tr></thead><tbody>
    ${_normInds.map(i => `<tr>
      <td style="font-weight:600">${_IND_LABEL[i.indication_id]||i.indication_id.toUpperCase()}</td>
      <td style="color:#64748b">${i.development_stage||'—'}</td>
      <td style="color:#64748b">${i.confidence_score != null ? Math.round(i.confidence_score)+'%' : '—'}</td>
      <td style="color:#64748b">${i.review_status||'—'}</td>
    </tr>`).join('')}
    </tbody></table>
  </div>`;

  // Knowledge gaps
  const gaps = [];
  if (!trials?.length) gaps.push({ level:'red', text:'No trial data linked — ClinicalTrials.gov lookup needed' });
  if (!molData)        gaps.push({ level:'red', text:'Molecule intelligence not enriched — run enrichment pipeline' });
  if (!areas?.some(a=>a.overlap)) gaps.push({ level:'amb', text:'Overlap tier unclassified — manual review or enrichment needed' });
  if (!drug.differentiation_thesis) gaps.push({ level:'amb', text:'Differentiation thesis missing' });
  if (!drug.mechanism) gaps.push({ level:'gry', text:'Mechanism not recorded' });

  const gapsSummary = gaps.slice(0,3).map(g => `
    <div class="cem-item-row">
      <div class="cem-dot-${g.level}"></div>
      <div style="font-size:11.5px;color:#1e293b">${g.text}</div>
    </div>`).join('') || '<div style="font-size:11px;color:#94a3b8;font-style:italic;padding:4px 0">No critical gaps detected.</div>';

  const gapsDetail = `<div class="cem-det-inner">
    <div class="cem-det-title">All gaps — priority order</div>
    ${gaps.length ? gaps.map(g => `
      <div style="display:flex;gap:8px;margin-bottom:6px;font-size:11px;align-items:flex-start">
        <div class="cem-dot-${g.level}" style="margin-top:3px"></div>
        <div style="color:#1e293b">${g.text}</div>
      </div>`).join('') : '<div style="font-size:11px;color:#94a3b8">Coverage complete across checked dimensions.</div>'}
  </div>`;

  // Source confidence
  // DEPRECATED 2026-06-07 — generic confidence-pill summary removed from display
  // (confidence plumbing); the Sources & provenance cell now uses drug_sources counts.
  const srcSummary = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px"><span style="font-size:11.5px;color:#64748b">Pipeline / overlap data</span><span class="cem-pill ${areas?.some(a=>a.source_url)?'cem-p-high':'cem-p-med'}">${areas?.some(a=>a.source_url)?'Confirmed · High':'AI enriched · Medium'}</span></div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px"><span style="font-size:11.5px;color:#64748b">Trial data</span><span class="cem-pill ${trialCount?'cem-p-blue':'cem-p-low'}">${trialCount?'ClinicalTrials.gov · High':'Not found'}</span></div>
    <div style="display:flex;justify-content:space-between;align-items:center"><span style="font-size:11.5px;color:#64748b">Molecule intelligence</span><span class="cem-pill ${molData?'cem-p-med':'cem-p-low'}">${molData?'AI enrichment · Medium':'Not run'}</span></div>`;

  const coQuery = companyName ? companyName + ' ' + drugName + ' pipeline' : drugName + ' clinical trial';

  // Header — identity pills + confidence bar
  const _cemDrugChipsEl = document.getElementById('entity-modal-hd-chips');
  const _cemDrugConfEl  = document.getElementById('entity-modal-conf');
  const _cemDrugSubEl   = document.getElementById('entity-modal-sub');
  if (_cemDrugChipsEl) {
    const phaseLabel   = phase ? phase.replace(/^Phase\s*/i,'Ph') : '';
    const licLabel     = drug.partner_company ? 'Out-licensed' : '';
    const _cemAMap2 = {tl1a:'TL1A',tslp:'TSLP',il4ra:'IL-4Rα',igf1r:'IGF1R/TSHR',fcrn:'FcRn',tcell:'BCMA/CD19/CD3',ox40l:'OX40L',ibd:'IBD',atopy:'Atopy',respiratory:'Respiratory'};
    const areaLabelsStr = (areas||[]).map(a=>(_cemAMap2[a.area_id]||a.area_id)).filter(Boolean).join(' · ');
    const phaseIsApproved = (phase||'').toLowerCase().includes('approved');
    const pills = [
      `<span class="cem-id-pill cem-id-pill-entity">Drug</span>`,
      phaseLabel && !phaseIsApproved ? `<span class="cem-id-pill cem-id-pill-phase">${phaseLabel}</span>` : '',
      phaseIsApproved ? `<span class="cem-id-pill cem-id-pill-approved">Approved</span>` : '',
      licLabel   ? `<span class="cem-id-pill cem-id-pill-status">${licLabel}</span>` : '',
      areaLabelsStr ? `<span class="cem-id-pill cem-id-pill-area">${areaLabelsStr}</span>` : '',
      (mechanism||target) ? `<span class="cem-id-pill cem-id-pill-target">${(mechanism||target).slice(0,30)}</span>` : '',
      (drug.format||drug.cls) ? `<span class="cem-id-pill cem-id-pill-format">${drug.format||drug.cls}</span>` : '',
    ].filter(Boolean);
    _cemDrugChipsEl.innerHTML = pills.join('');
  }
  if (_cemDrugSubEl) {
    const ind   = drug.indication_short || '';
    const fmt   = drug.format || drug.cls || '';
    const compLink = companyName && drug.company_id
      ? `<a href="#" style="color:#1d4ed8;text-decoration:none;font-weight:600" onclick="event.preventDefault();openCompanyEntityModal('${drug.company_id}','${(companyName||'').replace(/'/g,"\\'")}','')">${companyName}</a>`
      : companyName || '';
    const parts = [compLink, fmt, ind].filter(Boolean);
    _cemDrugSubEl.innerHTML = parts.length ? parts.join(' · ') : 'Drug Profile';
  }
  if (_cemDrugConfEl) {
    const rawScore = drug.completeness_score;
    const areaConf = areas?.[0]?.confidence_level;
    const confMap  = {High:88, Medium:65, Low:40};
    const scoreNum = rawScore != null ? Math.min(100, Math.max(0, Number(rawScore)))
                   : areaConf ? (confMap[areaConf] || 65) : null;
    const fillColor = scoreNum >= 80 ? '#4ade80' : scoreNum >= 50 ? '#fb923c' : '#f87171';
    const updDate  = drug.updated_at ? drug.updated_at.slice(0,10) : '';
    const updLabel = updDate ? (() => { try { const d=new Date(updDate); return d.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}); } catch(e){return updDate;} })() : '';
    _cemDrugConfEl.innerHTML = scoreNum != null ? `
      <div class="cem-conf-lbl">Meridian confidence</div>
      <div class="cem-conf-row">
        <div class="cem-conf-track"><div class="cem-conf-fill" style="width:${scoreNum}%;background:${fillColor}"></div></div>
        <span class="cem-conf-pct" style="color:${fillColor==='#4ade80'?'#15803d':fillColor==='#fb923c'?'#b45309':'#b91c1c'}">${scoreNum}%</span>
      </div>
      ${updLabel ? `<div class="cem-conf-date">Updated ${updLabel}</div>` : ''}
    ` : '';
  }

  // BD Deals section — prefer fetched deals table records, fallback to drug fields
  const _allDeals  = (drugDeals||[]).length ? drugDeals : [];
  const bdPartner  = drug.partner_company || '';
  const bdLicensor = drug.licensor || '';
  const bdUpfront  = drug.upfront_usd_m;
  const bdTotal    = drug.total_usd_m;
  const hasDrugFieldDeal = bdPartner || bdLicensor || bdUpfront || bdTotal;
  const hasDeal    = _allDeals.length > 0 || hasDrugFieldDeal;

  const bdDealsSummary = _allDeals.length ? _allDeals.slice(0,3).map(d => {
    const partner = d.to_company || d.from_company || '';
    const headline = d.headline || '';
    const searchQ  = [companyName, headline||partner, drugName, d.deal_date?d.deal_date.slice(0,4):''].filter(Boolean).join(' ');
    return `<div class="cem-item-row" style="flex-direction:column;gap:3px">
      <div style="font-size:12px;font-weight:600;color:#0f172a">${headline ? _cemLink(headline.slice(0,90)+(headline.length>90?'…':''), searchQ) : _cemLink(partner||'Deal', searchQ)}</div>
      <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
        ${d.deal_date ? `<span style="font-size:10px;color:#94a3b8">${_cemFmtDate(d.deal_date)}</span>` : ''}
        ${d.deal_type ? `<span class="cem-pill cem-p-purple">${d.deal_type}</span>` : ''}
        ${_cemFmtVal(d.upfront_usd_m, d.total_usd_m)}
      </div>
    </div>`;
  }).join('') : hasDrugFieldDeal ? `
    <div class="cem-item-row" style="flex-direction:column;gap:4px">
      ${bdPartner ? `<div style="font-size:12px;font-weight:600">${_cemLink(bdPartner, [companyName, bdPartner, drugName, 'license deal'].join(' '))}</div>` : ''}
      ${bdLicensor ? `<div style="font-size:11.5px;color:#64748b">Licensor: ${_cemLink(bdLicensor, [bdLicensor, drugName, 'pharma license'].join(' '))}</div>` : ''}
      <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-top:2px">
        ${_cemFmtVal(bdUpfront, bdTotal)}
      </div>
    </div>` : `<span style="font-size:11px;color:#94a3b8;font-style:italic">No BD deal on record.</span>`;

  const bdDealsDetail = `<div class="cem-det-inner">
    <div class="cem-det-title">Deal records — ${drugName}</div>
    ${_allDeals.length ? _allDeals.map(d => {
      const partner  = d.to_company||d.from_company||'';
      const headline = d.headline||'';
      const searchQ  = [companyName, headline||partner, drugName, d.deal_date?d.deal_date.slice(0,4):''].filter(Boolean).join(' ');
      return `<div style="margin-bottom:10px;padding-bottom:10px;border-bottom:0.5px solid #e2e8f0">
        <div style="font-size:12px;font-weight:600;margin-bottom:3px">${headline ? _cemLink(headline, searchQ) : _cemLink(partner||'Deal', searchQ)}</div>
        <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:3px">
          ${d.deal_type?`<span class="cem-pill cem-p-purple">${d.deal_type}</span>`:''}
          ${_cemFmtVal(d.upfront_usd_m, d.total_usd_m)}
          <span style="font-size:10px;color:#94a3b8">${_cemFmtDate(d.deal_date)}</span>
        </div>
        ${partner ? `<div style="font-size:11px;color:#64748b">Partner: ${_cemLink(partner, partner+' '+companyName+' pharma deal')}</div>` : ''}
        ${d.detail ? `<div style="font-size:11px;color:#1e293b;margin-top:4px;line-height:1.45">${d.detail.slice(0,200)}</div>` : ''}
      </div>`;
    }).join('') : `<div style="font-size:11px;color:#94a3b8">No deal records in database. Add via deals table with drug_name="${drugName}".</div>`}
  </div>`;

  // Relationship Intelligence — area overlap as competitive context
  const relSummary = (areas||[]).slice(0,3).map(a => {
    const lbl = (_CEM_AMAP[a.area_id]||a.area_id);
    return `<div class="cem-item-row">
      <div style="flex:1">
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:2px">
          <span style="font-size:11.5px;font-weight:600;color:#0f172a">${_cemLink(lbl, lbl+' drug landscape '+drugName)}</span>
          ${_cemOverlapPill(a.overlap)}
        </div>
        ${a.overlap_rationale ? `<div style="font-size:11px;color:#64748b;line-height:1.4">${a.overlap_rationale.slice(0,110)}</div>` : ''}
      </div>
    </div>`;
  }).join('') || '<span style="font-size:11px;color:#94a3b8;font-style:italic">No relationship data.</span>';

  const relDetail = `<div class="cem-det-inner">
    <div class="cem-det-title">Full competitive landscape — ${drugName}</div>
    ${(areas||[]).map(a => {
      const lbl = (_CEM_AMAP[a.area_id]||a.area_id);
      return `<div style="margin-bottom:10px">
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
          <span style="font-size:11px;font-weight:600">${lbl}</span>
          ${_cemOverlapPill(a.overlap)}
        </div>
        ${a.overlap_rationale ? `<div style="font-size:11px;color:#1e293b;line-height:1.5">${a.overlap_rationale}</div>` : ''}
        ${a.strategic_role ? `<div style="font-size:11px;color:#64748b;margin-top:3px"><strong>Strategic role:</strong> ${a.strategic_role}</div>` : ''}
        ${a.source_url ? `<div style="margin-top:4px"><a class="cem-link" href="${a.source_url}" target="_blank" rel="noopener" style="font-size:10px">↗ Source</a></div>` : ''}
      </div>`;
    }).join('') || '<div style="font-size:11px;color:#94a3b8">No area overlap records.</div>'}
  </div>`;

  // ── Catalyst Timeline (Fix 3B) ────────────────────────────────────────────
  const _SIG_CAT_STYLE = {
    clinical_readout: { label:'READOUT', bg:'#f0fdf4', color:'#15803d' },
    regulatory:       { label:'REG',     bg:'#fef2f2', color:'#b91c1c' },
    conference:       { label:'CONF',    bg:'#eff6ff', color:'#1d4ed8' },
    pdufa:            { label:'PDUFA',   bg:'#fef2f2', color:'#b91c1c' },
    trial_start:      { label:'START',   bg:'#f0fdf4', color:'#059669' },
    data_readout:     { label:'DATA',    bg:'#f0fdf4', color:'#15803d' },
  };
  const _drugCatalysts = drugCatalysts || [];
  const _catalystSummary = _drugCatalysts.slice(0,3).map(c => {
    const sty = _SIG_CAT_STYLE[c.catalyst_type] || { label: (c.catalyst_type||'EVENT').toUpperCase().slice(0,8), bg:'#f8fafc', color:'#64748b' };
    const dateStr = c.sort_date ? (() => { try { const d = new Date(c.sort_date); return d.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}); } catch(e){return c.sort_date;} })() : '';
    return `<div class="cem-item-row" style="align-items:flex-start">
      <span style="font-size:8px;font-weight:700;background:${sty.bg};color:${sty.color};border-radius:4px;padding:2px 5px;flex-shrink:0;margin-top:1px">${sty.label}</span>
      <div style="flex:1">
        <div style="font-size:11.5px;color:#1e293b;line-height:1.4">${c.catalyst_text ? c.catalyst_text.slice(0,110)+(c.catalyst_text.length>110?'…':'') : 'Upcoming catalyst'}</div>
        ${dateStr ? `<div style="font-size:10px;color:#94a3b8;margin-top:2px">${dateStr}</div>` : ''}
      </div>
      ${c.source_url ? `<a href="${c.source_url}" target="_blank" rel="noopener" style="font-size:10px;color:#1d4ed8;text-decoration:none;flex-shrink:0">↗</a>` : ''}
    </div>`;
  }).join('') || '<span style="font-size:11px;color:#94a3b8;font-style:italic">No upcoming catalysts linked to this drug.</span>';

  const _catalystDetail = `<div class="cem-det-inner">
    <div class="cem-det-title">All upcoming catalysts — ${drugName}</div>
    ${_drugCatalysts.length ? _drugCatalysts.map(c => {
      const sty = _SIG_CAT_STYLE[c.catalyst_type] || { label:(c.catalyst_type||'EVENT').toUpperCase().slice(0,8), bg:'#f8fafc', color:'#64748b' };
      const dateStr = c.sort_date ? (() => { try { const d = new Date(c.sort_date); return d.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}); } catch(e){return c.sort_date;} })() : '';
      return `<div style="display:flex;gap:8px;margin-bottom:8px;padding-bottom:8px;border-bottom:0.5px solid #e2e8f0;align-items:flex-start">
        <span style="font-size:8px;font-weight:700;background:${sty.bg};color:${sty.color};border-radius:4px;padding:2px 5px;flex-shrink:0;margin-top:2px">${sty.label}</span>
        <div style="flex:1">
          <div style="font-size:11.5px;color:#1e293b;line-height:1.45">${c.catalyst_text||'Upcoming catalyst'}</div>
          ${dateStr ? `<div style="font-size:10px;color:#94a3b8;margin-top:2px">${dateStr}</div>` : ''}
          ${c.source_url ? `<a href="${c.source_url}" target="_blank" rel="noopener" style="font-size:10px;color:#1d4ed8">↗ Source</a>` : ''}
        </div>
      </div>`;
    }).join('') : '<div style="font-size:11px;color:#94a3b8">No upcoming catalysts with drug_id linked in database. Catalysts linked via company_id may appear in the company card.</div>'}
  </div>`;

  // ── Drug News (Fix 3A) ────────────────────────────────────────────────────
  const _drugNewsItems = drugNews || [];
  const _drugNewsSummary = _drugNewsItems.slice(0,3).map(n => {
    const dateStr = n.published_at ? (() => { try { const d = new Date(n.published_at); return d.toLocaleDateString('en-US',{month:'short',day:'numeric'}); } catch(e){return n.published_at.slice(0,10);} })() : '';
    const relScore = n.relevance_score ? Math.round(n.relevance_score) : null;
    return `<div class="cem-item-row" style="flex-direction:column;gap:2px">
      <div style="display:flex;align-items:flex-start;gap:6px">
        <div style="flex:1">
          <div style="font-size:11.5px;font-weight:600;color:#0f172a;line-height:1.35">${n.article_url ? `<a href="${n.article_url}" target="_blank" rel="noopener" style="color:inherit;text-decoration:none">${(n.headline||'').slice(0,100)+(n.headline?.length>100?'…':'')}</a>` : (n.headline||'').slice(0,100)}</div>
          <div style="font-size:10px;color:#94a3b8;margin-top:2px">${[n.source_name, dateStr].filter(Boolean).join(' · ')}${relScore ? ` · relevance ${relScore}` : ''}</div>
        </div>
      </div>
      ${n.why_it_matters ? `<div style="font-size:11px;color:#64748b;line-height:1.4;margin-top:2px">${n.why_it_matters.slice(0,120)+(n.why_it_matters.length>120?'…':'')}</div>` : ''}
    </div>`;
  }).join('') || '<span style="font-size:11px;color:#94a3b8;font-style:italic">No recent articles matched to this drug.</span>';

  const _drugNewsDetail = `<div class="cem-det-inner">
    <div class="cem-det-title">Recent coverage — ${drugName}</div>
    ${_drugNewsItems.length ? _drugNewsItems.map(n => {
      const dateStr = n.published_at ? (() => { try { const d = new Date(n.published_at); return d.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}); } catch(e){return n.published_at.slice(0,10);} })() : '';
      return `<div style="margin-bottom:10px;padding-bottom:10px;border-bottom:0.5px solid #e2e8f0">
        <div style="font-size:12px;font-weight:600;margin-bottom:3px">${n.article_url ? `<a href="${n.article_url}" target="_blank" rel="noopener" style="color:#1d4ed8;text-decoration:none">${n.headline||'Article'}</a>` : n.headline||'Article'}</div>
        <div style="font-size:10px;color:#94a3b8;margin-bottom:4px">${[n.source_name, dateStr].filter(Boolean).join(' · ')}</div>
        ${n.meridian_summary ? `<div style="font-size:11px;color:#1e293b;line-height:1.5">${n.meridian_summary.slice(0,300)}</div>` : ''}
        ${n.why_it_matters ? `<div style="font-size:11px;color:#64748b;margin-top:4px;font-style:italic">${n.why_it_matters}</div>` : ''}
      </div>`;
    }).join('') : '<div style="font-size:11px;color:#94a3b8">No recent articles matched to this drug via news_articles.matched_drug_ids. Articles may appear via company card if matched to the company.</div>'}
  </div>`;

  // ── OVERVIEW TAB ─────────────────────────────────────────────────────────
  // Provenance badge: single inline badge combining FORMERLY (drug name history) +
  // transfer chain (company-by-company ownership journey).
  //
  // Design rule: method label goes ON the receiving node, not between nodes.
  //   EpimAb → Vignette Bio (lic. ex-China) → Candid (acq.) → UCB (acq.)
  // This makes direction unambiguous: "Candid (acq.)" = Candid received it via acquisition.
  //
  // Shows for any drug with asset_transfer_history rows OR ownerData.
  // Only most-recent former drug name shown (licensor_code); omit if same as current name.
  const _ownerBannerHtml = (() => {
    // _spName: shorten company names for provenance nodes (strip JV parentheticals + pharma suffixes)
    const _spName = n => n ? n.replace(/\s*\([^)]*\)/g,'').trim().replace(/[,\s]+(Biotherapeutics?|Biosciences?|Biopharmaceuticals?|Biologics?|Biotechnology|Technologies?|Pharmaceutical(s)?|Pharma|Biopharma|Therapeutics?|Holdings?|Sciences?|Labs?|Co\.?,?\s*Ltd\.?|Inc\.?|LLC|Corp\.?|GmbH|S\.A\.|B\.V\.|Limited)\.?\s*$/i,'').trim() : n;
    const _provNodeHtml = (name, id, methodLabel, tip) => {
      const _nSafe = (name || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
      const _nameEl = id
        ? `<span style="font-weight:700;color:#1d4ed8;cursor:pointer;white-space:nowrap" onclick="event.preventDefault();event.stopPropagation();openCompanyEntityModal('${id}','${_nSafe}','')">${name}</span>`
        : `<span style="font-weight:700;color:#475569;white-space:nowrap">${name}</span>`;
      if (!methodLabel) return _nameEl;
      const _tipAttr = tip ? ` title="${(tip).replace(/"/g,'&quot;')}"` : '';
      return `${_nameEl} <span style="font-size:8.5px;color:#64748b;background:#f1f5f9;border-radius:3px;padding:1px 4px;white-space:nowrap"${_tipAttr}>${methodLabel}</span>`;
    };

    if (transferChain && transferChain.length > 0) {
      // Build node list: [{name, id}] with method on each node except the first; names shortened
      const _tcNodes = [];
      transferChain.forEach((hop, i) => {
        if (i === 0) _tcNodes.push({ name: _spName(hop.from_entity_name), id: hop.from_entity_id });
        const _mShort = { license:'lic.', sublicense:'sub-lic.', acquisition:'acq.', co_development:'co-dev', spin_out:'spin-out', internal:'internal', merger:'merger' }[hop.transfer_type] || hop.transfer_type;
        const _geo = (hop.geographic_scope && hop.geographic_scope !== 'global') ? ` ${hop.geographic_scope}` : '';
        const _vd = hop.verified ? '' : ' ⚬';
        _tcNodes.push({ name: _spName(hop.to_entity_name), id: hop.to_entity_id, method: `${_mShort}${_geo}${_vd}`, tip: hop.deal_value_notes || '' });
      });

      let _chainHtml = _provNodeHtml(_tcNodes[0].name, _tcNodes[0].id, null, null);
      _tcNodes.slice(1).forEach(node => {
        _chainHtml += ` <span style="color:#cbd5e1;font-size:10px">→</span> ${_provNodeHtml(node.name, node.id, node.method, node.tip)}`;
      });

      // Former drug name — only the most recent / only one (licensor_code)
      const _curName = drug?.display_name || drug?.name || '';
      const _frmCode = (drug?.licensor_code && drug.licensor_code.trim() !== _curName.trim()) ? drug.licensor_code.trim() : null;

      return `<div style="display:inline-flex;align-items:center;flex-wrap:wrap;gap:5px;margin-bottom:10px;padding:4px 10px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:4px;font-size:10px;color:#64748b">
        ${_frmCode ? `<span style="font-weight:700;color:#94a3b8;font-size:9px;text-transform:uppercase;letter-spacing:0.05em">formerly</span><span style="font-weight:700;color:#475569">${_frmCode}</span><span style="color:#cbd5e1;margin:0 2px">·</span>` : ''}
        ${_chainHtml}
      </div>`;
    }

    // Fallback: simple two-node ownership (no ATH rows, but ownerData present)
    if (!ownerData) return '';
    const _curName2 = drug?.display_name || drug?.name || '';
    const _frmCode2 = (drug?.licensor_code && drug.licensor_code.trim() !== _curName2.trim()) ? drug.licensor_code.trim() : null;
    return `<div style="display:inline-flex;align-items:center;flex-wrap:wrap;gap:5px;margin-bottom:10px;padding:4px 10px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:4px;font-size:10px;color:#64748b">
      ${_frmCode2 ? `<span style="font-weight:700;color:#94a3b8;font-size:9px;text-transform:uppercase;letter-spacing:0.05em">formerly</span><span style="font-weight:700;color:#475569">${_frmCode2}</span><span style="color:#cbd5e1;margin:0 2px">·</span>` : ''}
      ${_provNodeHtml(ownerData.originatorName, ownerData.originatorCompanyId, null, null)}
      <span style="color:#cbd5e1;font-size:10px">→</span>
      ${_provNodeHtml(ownerData.ownerName, ownerData.ownerCompanyId, 'acq.', null)}
    </div>`;
  })();

  // ── Failure cascade risk banner (Fix B — Session 68) ─────────────────────
  const _cascadeRiskHtml = (() => {
    if (!cascadeRisk?.cascade_risk_level) return '';
    const lvl = cascadeRisk.cascade_risk_level;
    const _sty = {
      HIGH:   { bg:'#fef2f2', border:'#fca5a5', accent:'#b91c1c', bdg:'#b91c1c' },
      MEDIUM: { bg:'#fff7ed', border:'#fdba74', accent:'#c2410c', bdg:'#ea580c' },
      LOW:    { bg:'#fefce8', border:'#fde047', accent:'#ca8a04', bdg:'#ca8a04' },
    }[lvl] || { bg:'#f8fafc', border:'#e2e8f0', accent:'#64748b', bdg:'#64748b' };
    const mech = [cascadeRisk.mechanism_target, cascadeRisk.mechanism_indication].filter(Boolean).join(' × ');
    const validity = cascadeRisk.mechanism_validity || 'failed';
    const rationale = cascadeRisk.cascade_risk_rationale ? cascadeRisk.cascade_risk_rationale.slice(0,180)+(cascadeRisk.cascade_risk_rationale.length>180?'…':'') : '';
    return `<div style="display:flex;align-items:flex-start;gap:10px;background:${_sty.bg};border:1px solid ${_sty.border};border-left:3px solid ${_sty.accent};border-radius:7px;padding:10px 12px;margin-bottom:10px">
      <div style="flex-shrink:0;margin-top:1px"><span style="font-size:8px;font-weight:800;background:${_sty.bdg};color:white;border-radius:5px;padding:2px 7px;letter-spacing:0.04em;text-transform:uppercase">⚠ ${lvl} RISK</span></div>
      <div>
        <div style="font-size:11.5px;font-weight:700;color:${_sty.accent};margin-bottom:3px">Mechanism failure cascade risk</div>
        <div style="font-size:11px;color:#1e293b;line-height:1.45">${mech ? `<strong>${mech}</strong> mechanism is <em>${validity}</em>.` : ''} ${rationale}</div>
      </div>
    </div>`;
  })();

  // ── drug_sources provenance (Wave 2: surfaces the dark drug_sources table) ──
  const _provRows = (drugSources || []).filter(s => s && (s.source_url || s.claim_value));
  const _CLAIM_LBL = {mechanism:'Mechanism', stage:'Stage', company_pipeline:'Pipeline', partnership:'Partnership',
    approval:'Approval', trial_id:'Trial', indication:'Indication', correction:'Correction', source_url_removed:'Source removed'};
  const _confirmBadge = (s) => {
    if (s.claim_type === 'source_url_removed') return '<span style="font-size:8px;font-weight:700;background:#fef2f2;color:#b91c1c;border-radius:8px;padding:1px 6px">removed</span>';
    if (s.content_confirms_claim === true)  return '<span title="Source content verified to support this claim" style="font-size:8px;font-weight:700;background:#f0fdf4;color:#15803d;border-radius:8px;padding:1px 6px">✓ confirmed</span>';
    if (s.content_confirms_claim === false) return '<span title="Source checked — did not support claim" style="font-size:8px;font-weight:700;background:#fef2f2;color:#b91c1c;border-radius:8px;padding:1px 6px">✗ unconfirmed</span>';
    return '<span title="Stored but content not yet machine-verified" style="font-size:8px;font-weight:700;background:#f8fafc;color:#94a3b8;border:1px solid #e2e8f0;border-radius:8px;padding:1px 6px">unverified</span>';
  };
  const _provConfirmed = _provRows.filter(s => s.content_confirms_claim === true).length;
  const srcProvSummary = _provRows.length
    ? `<div style="font-size:11px;color:#475569">${_provRows.length} documented source${_provRows.length!==1?'s':''}${_provConfirmed?` · <span style="color:#15803d;font-weight:600">${_provConfirmed} content-verified</span>`:''}</div>`
    : '';
  const srcProvDetail = _provRows.length ? `<div class="cem-det-inner">
    <div class="cem-det-title">Documented provenance — drug_sources</div>
    ${_provRows.map(s => {
      const lbl = _CLAIM_LBL[s.claim_type] || (s.claim_type||'claim');
      const dom = s.source_domain || (s.source_url ? (function(){try{return new URL(s.source_url).hostname.replace(/^www\./,'');}catch(e){return 'source';}})() : '');
      const _isPdf = s.source_url && /\.pdf|\/pdf|bluematrix/i.test(s.source_url);
      const _lbl2 = _isPdf ? `📄 View source PDF (${dom||'source'})` : `↗ ${dom||'source'}`;
      const link = s.source_url ? `<a class="cem-link" href="${s.source_url}" target="_blank" rel="noopener" data-trusted="1">${_lbl2}</a>` : `<span style="color:#94a3b8">${dom||'—'}</span>`;
      const styp = s.source_type ? `<span style="font-size:9px;color:#64748b">${String(s.source_type).replace(/_/g,' ')}</span>` : '';
      return `<div class="cem-fact" style="align-items:flex-start">
        <span class="cem-fact-lbl">${lbl}</span>
        <span class="cem-fact-val" style="display:flex;flex-wrap:wrap;align-items:center;gap:6px">${link} ${styp} ${_confirmBadge(s)}</span>
      </div>`;
    }).join('')}
  </div>` : '';

  // ════════════════════════════════════════════════════════════════════════════
  // CANONICAL DRUG CARD IA (2026-06-07) — four titled sections, one per tab:
  //   1 · Asset Overview   2 · Development   3 · Business   4 · Intelligence
  // Panel ids (cem-dtab-overview/profile/molecule/intel) are kept STABLE so the
  // lazy injectors (_demLoadIntelligence → intel, clinical benchmarks → profile,
  // payer TPP → molecule) keep working. Sections render only when non-empty.
  // DEPRECATED 2026-06-07 — the previous single "Overview" cem-grid (catalysts/
  // trials/deals/news/signals/rel/gaps/src/geo all in one tab) was replaced by
  // this four-section IA; all cells were redistributed, none lost.
  // ════════════════════════════════════════════════════════════════════════════
  const _x = extData || {};
  const _xLink = (html, url) => url ? `<a class="cem-link" href="${url}" target="_blank" rel="noopener">${html}</a>` : html;
  const _xUsd  = v => { const n = +v; if (!n || isNaN(n)) return ''; return n >= 1e9 ? `$${(n/1e9).toFixed(1)}B` : n >= 1e6 ? `$${(n/1e6).toFixed(0)}M` : n >= 1e3 ? `$${(n/1e3).toFixed(0)}K` : `$${n.toFixed(2)}`; };

  // — Regulatory designations (Development) — chips
  const _DESIG_LBL = { orphan:'Orphan Drug', breakthrough:'Breakthrough Therapy', fast_track:'Fast Track', prime:'EMA PRIME', rmat:'RMAT', priority_review:'Priority Review', accelerated_approval:'Accelerated Approval', qidp:'QIDP' };
  const _desigs = _x.designations || [];
  const _desigCellHtml = _desigs.length ? `<div class="cem-cell">
    <div class="cem-sec-hdr"><div class="cem-sec-lbl">🏷 Regulatory designations</div><div class="cem-sec-hint">${_desigs.length}</div></div>
    <div class="cem-sec-body" style="display:flex;flex-wrap:wrap;gap:5px">${_desigs.map(d => {
      const lbl = _DESIG_LBL[d.designation_type] || (d.designation_type||'').replace(/_/g,' ');
      const yr  = d.granted_date ? ` ’${String(d.granted_date).slice(2,4)}` : '';
      const tip = [d.indication, d.granting_authority].filter(Boolean).join(' · ').replace(/"/g,'&quot;');
      return `<span title="${tip}" style="display:inline-flex;align-items:center;gap:4px;font-size:10px;font-weight:700;background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;border-radius:10px;padding:2px 8px;white-space:nowrap">${lbl}${yr}${d.indication?`<span style="font-weight:500;color:#64748b">· ${(d.indication||'').slice(0,26)}</span>`:''}</span>`;
    }).join('')}</div>
  </div>` : '';

  // — Safety & label (Development) — boxed-warning chips + FDA label link
  const _safetyRows = _x.safety || [];
  const _labelRows  = _x.labels || [];
  const _safetyCellHtml = (_safetyRows.length || _labelRows.length || molData?.safety_observations) ? `<div class="cem-cell">
    <div class="cem-sec-hdr"><div class="cem-sec-lbl">⚠ Safety &amp; label</div><div class="cem-sec-hint">${_safetyRows.length?_safetyRows.length+' warning'+(_safetyRows.length!==1?'s':''):''}</div></div>
    <div class="cem-sec-body">
      ${_safetyRows.slice(0,4).map(s => {
        const isBox = /black box|boxed/i.test(s.warning_type||'');
        const chip = `<span style="display:inline-block;font-size:10px;font-weight:700;background:${isBox?'#fef2f2':'#fff7ed'};color:${isBox?'#b91c1c':'#c2410c'};border:1px solid ${isBox?'#fecaca':'#fed7aa'};border-radius:6px;padding:2px 8px;margin:0 4px 4px 0">${isBox?'⬛ Boxed warning':'⚠ '+(s.warning_type||'Warning')}${s.description?` — ${(s.description||'').slice(0,60)}`:''}</span>`;
        return _xLink(chip, s.source_url);
      }).join('')}
      ${_labelRows.slice(0,1).map(l => `<div style="font-size:11px;margin-top:4px">${_xLink('↗ FDA label — '+((l.label_title||'Prescribing information').slice(0,70)), l.source_url || l.set_url)}</div>`).join('')}
      ${molData?.safety_observations ? `<div style="font-size:11px;color:#1e293b;line-height:1.5;margin-top:5px">${molData.safety_observations}</div>` : ''}
    </div>
  </div>` : '';

  // — PK one-liner (Development) — from drug_pk_parameters
  const _pkRow = (_x.pk || [])[0] || null;
  const _pkLineHtml = _pkRow ? (() => {
    const bits = [
      _pkRow.half_life_hours ? `t½ ${(_pkRow.half_life_hours/24).toFixed(1)}d` : '',
      [_pkRow.dose_mg ? _pkRow.dose_mg + 'mg' : '', _pkRow.dose_route || ''].filter(Boolean).join(' '),
      _pkRow.steady_state_weeks ? `steady state wk ${_pkRow.steady_state_weeks}` : '',
      _pkRow.immunogenicity_ada_pct != null ? `${_pkRow.immunogenicity_ada_pct}% ADA` : '',
    ].filter(Boolean).join(' · ');
    return bits ? `<div style="font-size:11.5px;color:#1e293b;background:#f8fafc;border:1px solid #e2e8f0;border-radius:7px;padding:8px 12px;margin-bottom:10px"><span style="font-weight:700;color:#7c3aed">💉 PK</span> &nbsp;${_xLink(bits, _pkRow.source_url)}${_pkRow.verified?' <span style="color:#22c55e;font-size:9px" title="Verified against source">✓</span>':''}</div>` : '';
  })() : '';

  // — Congress presence (Development) — last 3 conference abstracts
  const _confAbs = _x.abstracts || [];
  const _congressCellHtml = _confAbs.length ? `<div class="cem-cell">
    <div class="cem-sec-hdr"><div class="cem-sec-lbl">🎤 Congress presence</div><div class="cem-sec-hint">last ${_confAbs.length}</div></div>
    <div class="cem-sec-body">${_confAbs.map(a => `<div class="cem-item-row" style="flex-direction:column;gap:1px;align-items:flex-start">
      <div style="font-size:11.5px;font-weight:600;color:#0f172a;line-height:1.35">${_xLink((a.title||'Abstract').slice(0,110)+((a.title||'').length>110?'…':''), a.source_url || a.doi)}</div>
      <div style="font-size:10px;color:#94a3b8">${[a.conference, a.conference_year].filter(Boolean).join(' · ')}</div>
    </div>`).join('')}</div>
  </div>` : '';

  // — US payer economics (Business) — payer_pricing compact line
  const _pp = _x.payer || [];
  const _ppPick = (metric, src) => _pp.filter(p => p.metric === metric && (!src || p.source === src)).sort((a,b) => (b.year||0)-(a.year||0))[0];
  const _ppBits = [];
  { const r = _ppPick('total_spending','cms_partd'); if (r && r.value_numeric != null) _ppBits.push(_xLink(`Part D ${_xUsd(r.value_numeric)}${r.year?` (${r.year})`:''}`, r.source_url)); }
  { const r = _ppPick('total_spending','cms_partb'); if (r && r.value_numeric != null) _ppBits.push(_xLink(`Part B ${_xUsd(r.value_numeric)}${r.year?` (${r.year})`:''}`, r.source_url)); }
  { const r = _ppPick('asp_payment_limit_per_unit'); if (r && r.value_numeric != null) _ppBits.push(_xLink(`ASP ${_xUsd(r.value_numeric)}/unit`, r.source_url)); }
  { const r = _ppPick('nadac_per_unit');             if (r && r.value_numeric != null) _ppBits.push(_xLink(`NADAC ${_xUsd(r.value_numeric)}/unit`, r.source_url)); }
  const _payerCellHtml = _ppBits.length ? `<div class="cem-cell">
    <div class="cem-sec-hdr"><div class="cem-sec-lbl">💵 US payer economics</div><div class="cem-sec-hint">CMS</div></div>
    <div class="cem-sec-body"><div style="font-size:11.5px;color:#1e293b;line-height:1.7">US payer: ${_ppBits.join(' <span style="color:#cbd5e1">·</span> ')}</div></div>
  </div>` : '';

  // — IP & patents (Business) — drug_patents (Orange Book) + patent_families
  const _pats = _x.patents || [];
  const _fams = _x.patentFamilies || [];
  const _patExp = _pats.map(p => p.patent_expire_date).filter(Boolean).sort();
  const _famJur = [...new Set(_fams.map(f => f.jurisdiction).filter(Boolean))];
  const _ipCellHtml = (_pats.length || _famJur.length) ? `<div class="cem-cell">
    <div class="cem-sec-hdr" onclick="_cemToggle('dr-ip')"><div class="cem-sec-lbl">📜 IP &amp; patents</div><div class="cem-sec-hint">${_pats.length || _fams.length} <i id="cem-chev-dr-ip" class="cem-chev">▶</i></div></div>
    <div class="cem-sec-body"><div style="font-size:11.5px;color:#1e293b">IP: ${[
      _pats.length ? `${_pats.length} Orange Book patent${_pats.length!==1?'s':''}${_patExp.length?`, earliest expiry ${_patExp[0].slice(0,4)}`:''}` : '',
      _famJur.length ? `family in ${_famJur.length} jurisdiction${_famJur.length!==1?'s':''} (${_famJur.slice(0,6).join(', ')})` : '',
    ].filter(Boolean).join(' · ')}</div></div>
    <div class="cem-det" id="cem-det-dr-ip"><div class="cem-det-inner">
      <div class="cem-det-title">Patent detail — ${drugName}</div>
      ${_pats.length ? `<table class="cem-tbl"><thead><tr><th>Patent</th><th>Expiry</th><th>Scope</th></tr></thead><tbody>
      ${_pats.slice(0,12).map(p => `<tr>
        <td style="font-weight:600">${_xLink(p.patent_no||'—', p.source_url)}</td>
        <td style="color:#64748b">${p.patent_expire_date?p.patent_expire_date.slice(0,10):'—'}</td>
        <td style="color:#64748b;font-size:10px">${p.drug_substance_flag?'substance':(p.patent_use_code?'use':'product')}</td>
      </tr>`).join('')}</tbody></table>` : ''}
      ${_famJur.length ? `<div style="font-size:11px;color:#64748b;margin-top:6px">Patent family jurisdictions: ${_famJur.join(', ')}</div>` : ''}
    </div></div>
  </div>` : '';

  // — Regulatory exclusivity (Business) — drug_exclusivity (Purple/Orange Book) (added 2026-06-07)
  const _excl = _x.exclusivity || [];
  const _exclCellHtml = _excl.length ? (() => {
    const latest = _excl.map(e => e.exclusivity_date).filter(Boolean).sort().slice(-1)[0];
    return `<div class="cem-cell">
    <div class="cem-sec-hdr"><div class="cem-sec-lbl">🛡️ Regulatory exclusivity</div><div class="cem-sec-hint">${_excl[0].is_biologic?'Purple Book':'Orange Book'}</div></div>
    <div class="cem-sec-body"><div style="font-size:11.5px;color:#1e293b;line-height:1.7">${
      _excl.slice(0,4).map(e => _xLink([e.exclusivity_type||e.exclusivity_code||'exclusivity', e.exclusivity_date?('to '+e.exclusivity_date.slice(0,10)):null].filter(Boolean).join(' '), e.source_url)).join(' <span style="color:#cbd5e1">·</span> ')
    }${latest?` <span style="color:#94a3b8;font-size:10px">(latest cliff ${latest.slice(0,4)})</span>`:''}</div></div>
  </div>`; })() : '';

  // — Post-market safety (Development) — FAERS top reactions (added 2026-06-07)
  const _fa = _x.faers || [];
  const _faersCellHtml = _fa.length ? `<div class="cem-cell">
    <div class="cem-sec-hdr"><div class="cem-sec-lbl">📈 Post-market safety (FAERS)</div><div class="cem-sec-hint">top ${_fa.length}</div></div>
    <div class="cem-sec-body"><div style="font-size:11px;color:#1e293b;line-height:1.8">${
      _fa.map(r => _xLink(`${(r.reaction||'').toLowerCase()} <span style="color:#94a3b8">${(r.report_count||0).toLocaleString()}</span>`, r.source_url)).join(' <span style="color:#cbd5e1">·</span> ')
    }</div><div style="font-size:9.5px;color:#94a3b8;margin-top:3px">Spontaneous reports — signal volume, not incidence.</div></div>
  </div>` : '';

  // — Non-responder biology (Intelligence) — non_responder_profiles one-liners
  const _nrRows = _x.nonResponders || [];
  const _nrCellHtml = _nrRows.length ? `<div class="cem-cell">
    <div class="cem-sec-hdr"><div class="cem-sec-lbl">🧬 Non-responder biology</div><div class="cem-sec-hint">${_nrRows.length}</div></div>
    <div class="cem-sec-body">${_nrRows.map(r => `<div style="padding:5px 8px;background:#fff7ed;border-left:2px solid #fb923c;margin-bottom:3px;border-radius:0 4px 4px 0;font-size:11px">
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
        <span style="font-weight:700;color:#c2410c">${r.mechanism_class||'—'}</span>
        ${r.non_responder_rate_pct != null ? `<span style="color:#94a3b8">${r.non_responder_rate_pct}% NR</span>` : ''}
        <span style="color:#94a3b8;font-size:10px">${(r.line_of_therapy||'').replace(/_/g,' ')}</span>
      </div>
      ${r.escape_mechanism_text ? `<div style="color:#78350f;font-size:10px;margin-top:2px">${r.escape_mechanism_text.slice(0,140)}${r.escape_mechanism_text.length>140?'…':''}</div>` : ''}
    </div>`).join('')}</div>
  </div>` : '';

  // — Geographic approvals (Business) — moved from the old Overview grid
  const _geoCellHtml = (geoApprovals||[]).length ? (() => {
    const _geo = geoApprovals || [];
    const _geoSummary = _geo.slice(0,3).map(a => {
      const _status = a.approval_status === 'approved' ? `<span style="font-size:9px;background:#dcfce7;color:#15803d;border-radius:4px;padding:1px 5px;margin-left:4px;font-weight:700">Approved</span>` : `<span style="font-size:9px;background:#f1f5f9;color:#64748b;border-radius:4px;padding:1px 5px;margin-left:4px">${a.approval_status||'—'}</span>`;
      return `<div class="cem-item-row">
        <div style="flex:1">
          <div style="display:flex;align-items:center;gap:4px;flex-wrap:wrap">
            <span style="font-size:11.5px;font-weight:600;color:#0f172a">${a.geography||'—'}</span>${_status}
            ${a.brand_name?`<span style="font-size:10px;color:#7c3aed;font-weight:600;margin-left:4px">${a.brand_name}</span>`:''}
          </div>
          <div style="font-size:10px;color:#94a3b8;margin-top:1px">${[a.regulator, a.approval_date?a.approval_date.slice(0,10):''].filter(Boolean).join(' · ')}</div>
        </div>
      </div>`;
    }).join('');
    const _geoDetail = `<div class="cem-det-inner">
      <div class="cem-det-title">All approvals — ${drugName}</div>
      <table class="cem-tbl"><thead><tr><th>Geography</th><th>Brand Name</th><th>Regulator</th><th>Date</th><th>Indication</th></tr></thead><tbody>
      ${_geo.map(a => `<tr>
        <td style="font-weight:600">${a.geography||'—'}</td>
        <td style="color:#7c3aed;font-weight:600">${a.brand_name||'—'}</td>
        <td style="color:#64748b">${a.regulator||'—'}</td>
        <td style="color:#64748b">${a.approval_date?a.approval_date.slice(0,10):'—'}</td>
        <td style="color:#64748b;font-size:10px">${a.indication||'—'}</td>
      </tr>`).join('')}
      </tbody></table>
    </div>`;
    return `<div class="cem-cell">
      <div class="cem-sec-hdr" onclick="_cemToggle('dr-geo-approvals')">
        <div class="cem-sec-lbl">🌍 Geographic Approvals</div>
        <div class="cem-sec-hint">${_geo.length} region${_geo.length!==1?'s':''} <i id="cem-chev-dr-geo-approvals" class="cem-chev">▶</i></div>
      </div>
      <div class="cem-sec-body">${_geoSummary}</div>
      <div class="cem-det" id="cem-det-dr-geo-approvals">${_geoDetail}</div>
    </div>`;
  })() : '';
  // ── Shared card builders (reused across the four sections) ────────────────
  const _mbadgeFs = molData?.field_status || {};
  const _mbadge = s => {
    if (!s || s === 'confirmed') return '';
    const cfg = s === 'inferred'
      ? { bg:'#fffbeb', co:'#b45309', bd:'#fde68a', lbl:'Inferred' }
      : { bg:'#f8fafc', co:'#94a3b8', bd:'#e2e8f0', lbl:'Not disclosed' };
    return `<span style="font-size:7.5px;font-weight:800;text-transform:uppercase;background:${cfg.bg};color:${cfg.co};border:1px solid ${cfg.bd};border-radius:4px;padding:1px 4px;margin-left:4px">${cfg.lbl}</span>`;
  };

  const _summaryCardHtml = drug.drug_summary ? `<div style="background:#fafafa;border:1px solid #e2e8f0;border-radius:8px;padding:12px 14px;margin-bottom:10px"><div style="font-size:8.5px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#64748b;margin-bottom:6px">📋 Summary</div><p style="font-size:12px;color:#1e293b;line-height:1.65;margin:0">${drug.drug_summary}</p></div>` : '';
  const _mechDetailCardHtml = drug.mechanism_detail ? `<div style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:8px;padding:12px 14px;margin-bottom:10px"><div style="font-size:8.5px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#0284c7;margin-bottom:6px">🔬 Mechanism &amp; Context</div><p style="font-size:12px;color:#1e293b;line-height:1.65;margin:0">${drug.mechanism_detail}</p></div>` : '';
  const _diffCardHtml = drug.differentiation_thesis ? `<div style="background:#faf5ff;border:1px solid #ddd6fe;border-left:3px solid #7c3aed;border-radius:8px;padding:12px 14px;margin-bottom:10px"><div style="font-size:8.5px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#7c3aed;margin-bottom:6px">⚡ Differentiation</div><p style="font-size:12px;color:#1e293b;font-weight:600;line-height:1.55;margin:0">${drug.differentiation_thesis}</p></div>` : '';
  const _molDiffClaimCardHtml = molData?.differentiation_claim ? `<div style="background:#f5f3ff;border:1px solid #ddd6fe;border-left:3px solid #7c3aed;border-radius:8px;padding:12px 14px;margin-bottom:10px">
    <div style="font-size:8.5px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#7c3aed;margin-bottom:6px">Differentiation Claim ${_mbadge(_mbadgeFs.differentiation_claim)}</div>
    <p style="font-size:12px;color:#1e293b;font-style:italic;line-height:1.5;margin:0">${molData.differentiation_claim}</p>
  </div>` : '';

  // Asset identity — mechanism / target / format / route / lead indication
  const _identityFacts = [
    mechanism ? ['Mechanism', mechanism] : null,
    target ? ['Target', target] : null,
    cls ? ['Class', cls] : null,
    (drug.format && drug.format !== cls) ? ['Format', drug.format] : null,
    drug.route ? ['Route', drug.route] : null,
    drug.indication_short ? ['Lead indication', drug.indication_short] : null,
  ].filter(Boolean);
  const _identityCardHtml = _identityFacts.length ? `<div style="background:white;border:1px solid #e2e8f0;border-radius:8px;padding:12px 14px;margin-bottom:10px">
    <div style="font-size:8.5px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#64748b;margin-bottom:8px">Asset identity</div>
    ${_identityFacts.map(([k,v]) => `<div class="cem-fact"><span class="cem-fact-lbl">${k}</span><span class="cem-fact-val">${v}</span></div>`).join('')}
  </div>` : '';

  // Molecule characterization (modality/format/half-life + engineering detail)
  const _molCharCardHtml = molData ? (() => {
    const mRow = (k, v, fk) => v ? `<div class="cem-fact"><span class="cem-fact-lbl">${k}</span><span class="cem-fact-val">${v}${_mbadge(_mbadgeFs[fk])}</span></div>` : '';
    const rows = [
      mRow('Format',         molData.format,          'format'),
      mRow('Modality',       molData.modality,        'modality'),
      mRow('IgG subclass',   molData.igg_subclass,    'igg_subclass'),
      mRow('Fc engineering', molData.fc_engineering,  'fc_engineering'),
      mRow('Epitope',        molData.epitope,         'epitope'),
      mRow('Affinity (KD)',  molData.affinity_kd,     'affinity_kd'),
      mRow('Half-life',      molData.half_life,       'half_life'),
      mRow('Dosing interval',molData.dosing_interval, 'dosing_interval'),
    ].filter(Boolean).join('');
    return rows ? `<div style="background:white;border:1px solid #e2e8f0;border-radius:8px;padding:12px 14px;margin-bottom:10px">
      <div style="font-size:8.5px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#64748b;margin-bottom:8px">Molecule Characterization</div>
      ${rows}
    </div>` : '';
  })() : '';

  // Approval dates card (Development)
  const _approvalCardHtml = drug.approval_date ? (() => {
    const entries = drug.approval_date.split(';').map(s => s.trim()).filter(Boolean);
    const content = entries.length <= 1
      ? `<span style="font-size:12px;font-weight:700;color:#0f172a">${drug.approval_date}</span>`
      : `<ul style="margin:4px 0 0;padding-left:14px;list-style:disc;display:grid;grid-template-columns:1fr 1fr;gap:2px 10px">${entries.map(e => `<li style="font-size:11px;font-weight:600;color:#1e293b;padding:1px 0">${e}</li>`).join('')}</ul>`;
    return `<div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:10px 12px;margin-bottom:10px"><div style="font-size:8.5px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#1d4ed8;margin-bottom:4px">📅 Approval Dates</div>${content}</div>`;
  })() : '';

  // Pivotal endpoints card (Development)
  const _endpointsCardHtml = drug.final_endpoints ? (() => {
    const entries = drug.final_endpoints.split(/;\s*|\.\s+(?=[A-Z])/).map(s => s.trim()).filter(s => s.length > 4);
    const content = entries.length <= 1
      ? `<p style="font-size:12px;color:#1e293b;line-height:1.6;margin:0">${drug.final_endpoints}</p>`
      : `<ul style="margin:0;padding-left:16px;list-style:disc">${entries.map(e => `<li style="font-size:11.5px;color:#1e293b;padding:3px 0;line-height:1.5">${e.replace(/\.$/, '')}</li>`).join('')}</ul>`;
    return `<div style="background:#fffdf0;border:1px solid #fde68a;border-radius:8px;padding:12px 14px;margin-bottom:10px"><div style="font-size:8.5px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#92400e;margin-bottom:8px">⚗ Pivotal Endpoints</div>${content}</div>`;
  })() : '';

  // Revenue + patients stat cards (Business)
  const _bizStatCards = [
    drug.annual_revenue ? `<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:10px 12px;flex:1;min-width:140px"><div style="font-size:8.5px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#15803d;margin-bottom:4px">💰 Annual Revenue</div><span style="font-size:13px;font-weight:800;color:#0f172a">${drug.annual_revenue}</span></div>` : '',
    drug.patient_population ? `<div style="background:#faf5ff;border:1px solid #ddd6fe;border-radius:8px;padding:10px 12px;flex:1;min-width:140px"><div style="font-size:8.5px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#7c3aed;margin-bottom:4px">👥 Patients on Therapy</div><span style="font-size:12px;font-weight:700;color:#0f172a">${drug.patient_population}</span></div>` : '',
  ].filter(Boolean).join('');
  const _bizStatCardsHtml = _bizStatCards ? `<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px">${_bizStatCards}</div>` : '';

  // ── 1 · ASSET OVERVIEW — what the molecule IS ─────────────────────────────
  const _assetOverviewContent = `
    ${_ownerBannerHtml}
    ${statsHtml}
    <div id="meridian-narrative-${drug.id||''}" class="meridian-narrative-host"></div>
    ${_summaryCardHtml}
    ${_identityCardHtml}
    ${_mechDetailCardHtml}
    ${_molCharCardHtml}
    ${_normTargets.length ? `<div class="cem-grid"><div class="cem-cell">
      <div class="cem-sec-hdr" onclick="_cemToggle('dr-norm-tgt')">
        <div class="cem-sec-lbl">🎯 Targets</div>
        <div class="cem-sec-hint">${_normTargets.length} target${_normTargets.length!==1?'s':''} <i id="cem-chev-dr-norm-tgt" class="cem-chev">▶</i></div>
      </div>
      <div class="cem-sec-body">${normTargetsSummary}</div>
      <div class="cem-det" id="cem-det-dr-norm-tgt">${normTargetsDetail}</div>
    </div></div>` : ''}`;

  // ── 2 · DEVELOPMENT — where it is in the clinic ───────────────────────────
  const _developmentContent = `
    ${_approvalCardHtml}
    ${_pkLineHtml}
    <div class="cem-grid">
      <div class="cem-cell">
        <div class="cem-sec-hdr" onclick="_cemToggle('dr-trials')">
          <div class="cem-sec-lbl">🧪 Clinical trials</div>
          <div class="cem-sec-hint">${trialCount} trial${trialCount!==1?'s':''} <i id="cem-chev-dr-trials" class="cem-chev">▶</i></div>
        </div>
        <div class="cem-sec-body">${trialSummary || '<span style="font-size:11px;color:#94a3b8;font-style:italic">No trial data linked.</span>'}</div>
        <div class="cem-det" id="cem-det-dr-trials">${trialDetail}</div>
      </div>
      ${_desigCellHtml}
      ${_safetyCellHtml}
      ${_faersCellHtml}
      ${_congressCellHtml}
      ${_normInds.length ? `<div class="cem-cell">
        <div class="cem-sec-hdr" onclick="_cemToggle('dr-norm-ind')">
          <div class="cem-sec-lbl">🩺 Indications</div>
          <div class="cem-sec-hint">${_normInds.length} indication${_normInds.length!==1?'s':''} <i id="cem-chev-dr-norm-ind" class="cem-chev">▶</i></div>
        </div>
        <div class="cem-sec-body">${normIndsSummary}</div>
        <div class="cem-det" id="cem-det-dr-norm-ind">${normIndsDetail}</div>
      </div>` : ''}
    </div>
    <div style="margin-top:12px">${_endpointsCardHtml}</div>`;

  // ── 3 · BUSINESS — deals, payer economics, IP, market footprint ───────────
  const _businessCells = [
    hasDeal ? `<div class="cem-cell">
      <div class="cem-sec-hdr" onclick="_cemToggle('dr-deals')">
        <div class="cem-sec-lbl">🤝 BD deals</div>
        <div class="cem-sec-hint">${_allDeals.length>0?_allDeals.length+' deal'+(_allDeals.length!==1?'s':''):'on record'} <i id="cem-chev-dr-deals" class="cem-chev">▶</i></div>
      </div>
      <div class="cem-sec-body">${bdDealsSummary}</div>
      <div class="cem-det" id="cem-det-dr-deals">${bdDealsDetail}</div>
    </div>` : '',
    _payerCellHtml,
    _ipCellHtml,
    _exclCellHtml,
    _geoCellHtml,
  ].filter(Boolean).join('');
  const _businessContent = (_bizStatCardsHtml || _businessCells)
    ? `${_bizStatCardsHtml}${_businessCells ? `<div class="cem-grid">${_businessCells}</div>` : ''}`
    : '<div style="padding:20px 0;color:#94a3b8;font-size:12px;font-style:italic">No business intelligence on record yet — deals, payer pricing, and IP populate here as they are collected.</div>';

  // ── 4 · INTELLIGENCE — the Meridian read ──────────────────────────────────
  const _intelligenceCells = [
    _drugCatalysts.length ? `<div class="cem-cell" style="grid-column:1/-1">
      <div class="cem-sec-hdr" onclick="_cemToggle('dr-catalysts')">
        <div class="cem-sec-lbl">📅 Upcoming catalysts</div>
        <div class="cem-sec-hint">${_drugCatalysts.length} upcoming <i id="cem-chev-dr-catalysts" class="cem-chev">▶</i></div>
      </div>
      <div class="cem-sec-body">${_catalystSummary}</div>
      <div class="cem-det" id="cem-det-dr-catalysts">${_catalystDetail}</div>
    </div>` : '',
    (areas||[]).length ? `<div class="cem-cell">
      <div class="cem-sec-hdr" onclick="_cemToggle('dr-rel')">
        <div class="cem-sec-lbl">🔗 Competitive position</div>
        <div class="cem-sec-hint">${(areas||[]).length} area${(areas||[]).length!==1?'s':''} <i id="cem-chev-dr-rel" class="cem-chev">▶</i></div>
      </div>
      <div class="cem-sec-body">${relSummary}</div>
      <div class="cem-det" id="cem-det-dr-rel">${relDetail}</div>
    </div>` : '',
    (bdAngle || riskSum) ? `<div class="cem-cell">
      <div class="cem-sec-hdr" onclick="_cemToggle('dr-sigs')">
        <div class="cem-sec-lbl">⚡ Strategic signals</div>
        <div class="cem-sec-hint">Enriched <i id="cem-chev-dr-sigs" class="cem-chev">▶</i></div>
      </div>
      <div class="cem-sec-body">${sigSummary}</div>
      <div class="cem-det" id="cem-det-dr-sigs">${sigDetail}</div>
    </div>` : '',
    _drugNewsItems.length ? `<div class="cem-cell">
      <div class="cem-sec-hdr" onclick="_cemToggle('dr-news')">
        <div class="cem-sec-lbl">📰 Recent coverage</div>
        <div class="cem-sec-hint">${_drugNewsItems.length} article${_drugNewsItems.length!==1?'s':''} <i id="cem-chev-dr-news" class="cem-chev">▶</i></div>
      </div>
      <div class="cem-sec-body">${_drugNewsSummary}</div>
      <div class="cem-det" id="cem-det-dr-news">${_drugNewsDetail}</div>
    </div>` : '',
    _nrCellHtml,
    gaps.length ? `<div class="cem-cell">
      <div class="cem-sec-hdr" onclick="_cemToggle('dr-gaps')">
        <div class="cem-sec-lbl">⚠ Knowledge gaps</div>
        <div class="cem-sec-hint">${gaps.length} gap${gaps.length!==1?'s':''} <i id="cem-chev-dr-gaps" class="cem-chev">▶</i></div>
      </div>
      <div class="cem-sec-body">${gapsSummary}</div>
      <div class="cem-det" id="cem-det-dr-gaps">${gapsDetail}</div>
    </div>` : '',
    (_provRows.length || (areas||[]).some(a => a.source_url)) ? `<div class="cem-cell">
      <div class="cem-sec-hdr" onclick="_cemToggle('dr-src')">
        <div class="cem-sec-lbl">🛡 Sources &amp; provenance</div>
        <div class="cem-sec-hint">${_provRows.length ? _provRows.length+' documented' : 'per area'} <i id="cem-chev-dr-src" class="cem-chev">▶</i></div>
      </div>
      <div class="cem-sec-body">${srcProvSummary || '<div style="font-size:11px;color:#475569">Per-area primary sources documented below.</div>'}</div>
      <div class="cem-det" id="cem-det-dr-src">
        ${srcProvDetail}
        <div class="cem-det-inner">
        <div class="cem-det-title">Per-area source breakdown</div>
        ${areas?.map(a => a.source_url ? `<div class="cem-fact"><span class="cem-fact-lbl">${(_CEM_AMAP[a.area_id]||a.area_id)}</span><span class="cem-fact-val"><a class="cem-link" href="${a.source_url}" target="_blank" rel="noopener" data-trusted="1">↗ Primary source</a></span></div>` : '').filter(Boolean).join('') || '<div style="font-size:11px;color:#94a3b8">Sources linked via overlap confidence field in drug_competitive_scores.</div>'}
      </div></div>
    </div>` : '',
    _ifRows.length ? `<div class="cem-cell">
      <div class="cem-sec-hdr" onclick="_cemToggle('dr-intel-facts')">
        <div class="cem-sec-lbl">📑 Research intelligence</div>
        <div class="cem-sec-hint">${_ifRows.length} facts <i id="cem-chev-dr-intel-facts" class="cem-chev">▶</i></div>
      </div>
      <div class="cem-sec-body"><div style="font-size:11px;color:#475569">${_ifRows.length} facts extracted from submitted research (Cowen, Wedbush, etc.) — click to expand.</div></div>
      <div class="cem-det" id="cem-det-dr-intel-facts">${_ifHtml}</div>
    </div>` : '',
  ].filter(Boolean).join('');

  const _intelligenceContent = `
    ${_cascadeRiskHtml}
    ${interpHtml}
    ${_diffCardHtml}
    ${_molDiffClaimCardHtml}
    ${_intelligenceCells ? `<div class="cem-grid">${_intelligenceCells}</div>` : ''}
    <div id="cem-dtab-intel-panel" style="min-height:120px;margin-top:12px"><div style="padding:20px;text-align:center;color:#94a3b8;font-size:12px;font-style:italic">Loading deep intelligence profile…</div></div>`;

  // ── Assemble — canonical four-section Drug Card IA ────────────────────────
  const _drugTabs = [
    { id:'cem-dtab-overview', label:'Asset Overview' },
    { id:'cem-dtab-profile',  label:'Development' },
    { id:'cem-dtab-molecule', label:'Business' },
    { id:'cem-dtab-intel',    label:'Intelligence' },
  ];
  const _drugPanels = [
    { id:'cem-dtab-overview', content: _assetOverviewContent },
    { id:'cem-dtab-profile',  content: _developmentContent },
    { id:'cem-dtab-molecule', content: _businessContent },
    { id:'cem-dtab-intel',    content: _intelligenceContent },
  ];
  return _buildDossierShell(_drugTabs, _drugPanels);
}

/* ── Company card renderer ───────────────────────────────────────── */
function _cemCompanyBody(prog, sbData, areaId, extraData) {
  const profile            = sbData?.profile              || {};
  const companyRow         = sbData?.company              || null;
  const sbCats             = sbData?.catalysts            || [];
  const sbDeals            = sbData?.deals                || [];
  const sbDrugs            = sbData?.drugs                || [];
  const sbSubs             = sbData?.subsidiaries         || [];
  const sbSeqConst         = sbData?.seqConstraints       || [];
  const sbDrugValidation   = sbData?.drugValidationResults || [];
  const sbFieldAudit       = sbData?.fieldChangeAudit     || [];
  const pi = profile.platform_intelligence || null;
  const bd = profile.bd_intelligence      || null;
  const companyName = prog?.co || '';
  // Store current company ID so _dossierSwitch can trigger lazy file load
  window._cemCurrentCompanyId = prog?.company_id || prog?.id || null;

  // Research Intelligence — facts extracted from submitted research reports
  const _coFacts = (sbData?.intelFacts || []).filter(f => f && f.claim);
  const _COIF_T = {clinical:'🧪 Clinical', competitive:'⚔️ Competitive', pipeline:'🔬 Pipeline', commercial:'💰 Commercial', market:'📊 Market', regulatory:'📋 Regulatory', patient:'👤 Patient', management:'🗣️ Management', deal:'🤝 Deal', catalyst:'📅 Catalyst'};
  const _coIfBy = {}; _coFacts.forEach(f => { (_coIfBy[f.fact_type]=_coIfBy[f.fact_type]||[]).push(f); });
  const _coResearchContent = _coFacts.length ? `<div style="padding:4px 2px">
    <div style="font-size:12px;color:#475569;margin-bottom:10px">${_coFacts.length} facts extracted from submitted research (Cowen, Wedbush, etc.), grouped by type.</div>
    ${Object.entries(_coIfBy).map(([t,fs]) => `<div style="margin-bottom:12px">
      <div style="font-size:11px;font-weight:700;color:#334155;text-transform:uppercase;letter-spacing:.4px;margin-bottom:4px">${_COIF_T[t]||t} (${fs.length})</div>
      ${fs.map(f => { const v=(f.value_num!=null)?` <b style="color:#1d4ed8">${f.value_num}${f.unit?' '+f.unit:''}</b>`:''; const lk=f.source_url?`<a href="${f.source_url}" target="_blank" rel="noopener" data-trusted="1" style="color:#94a3b8;text-decoration:none;font-size:9px">↗${f.page_ref?' '+f.page_ref:''}</a>`:''; return `<div style="font-size:11.5px;color:#1e293b;line-height:1.45;margin-bottom:3px">• ${f.claim}${v} ${lk}</div>`; }).join('')}
    </div>`).join('')}
  </div>` : '';

  // Header — identity pills + confidence bar (areaLabel needed here, declare first)
  const _CEMAreaMap = {tl1a:'TL1A',tslp:'TSLP',il4ra:'IL-4Rα',igf1r:'IGF1R/TSHR',fcrn:'FcRn',tcell:'BCMA/CD19/CD3',ox40l:'OX40L'};
  const areaLabelHd = _CEMAreaMap[areaId] || (window._AREA_LABEL||{})[areaId] || areaId || '';
  const chipsEl = document.getElementById('entity-modal-hd-chips');
  const confEl  = document.getElementById('entity-modal-conf');
  const subEl2  = document.getElementById('entity-modal-sub');
  if (chipsEl) {
    const coType = companyRow?.company_type || profile.company_type || '';
    const coTypeCssMap = {
      'large_pharma':'large-pharma','Large Pharma':'large-pharma',
      'mid_pharma':'mid-pharma','Mid Pharma':'mid-pharma',
      'big_biotech':'big-biotech','Big Biotech':'big-biotech',
      'biotech':'biotech','Biotech':'biotech',
      'academic':'academic','Academic':'academic',
      'cro':'cro','CRO':'cro',
      'spinout':'spinout','Spinout':'spinout',
    };
    const coTypeLabel = {'large_pharma':'Large Pharma','mid_pharma':'Mid Pharma','big_biotech':'Big Biotech','biotech':'Biotech','academic':'Academic','cro':'CRO','spinout':'Spinout'}[coType] || coType;
    const coTypeCss   = coTypeCssMap[coType] || '';
    const typePill = `<span class="cem-id-pill cem-id-pill-entity">Company</span>`;
    const szPill   = coTypeCss ? `<span class="cem-id-pill cem-id-pill-${coTypeCss}">${coTypeLabel}</span>` : (coType ? `<span class="cem-id-pill cem-id-pill-status">${coType}</span>` : '');
    const areaPill = areaLabelHd ? `<span class="cem-id-pill cem-id-pill-area">${areaLabelHd}</span>` : '';
    chipsEl.innerHTML = [typePill, szPill].filter(Boolean).join('');
  }
  if (subEl2) {
    const ticker  = companyRow?.ticker || profile.ticker || '';
    const hqParts = [companyRow?.hq_city, companyRow?.hq_country].filter(Boolean);
    const hq      = hqParts.join(', ');
    const ta1     = companyRow?.ta_focus_1 || '';
    const ta2     = companyRow?.ta_focus_2 || '';
    const taStr   = [ta1, ta2].filter(Boolean).join(' · ');
    const parts   = [ticker, taStr, hq].filter(Boolean);
    subEl2.innerHTML = parts.length ? parts.map(p => `<span>${p}</span>`).join(' <span style="color:#cbd5e1">·</span> ') : '';
  }
  if (confEl) {
    const score    = profile.completeness_score;
    const scoreNum = score != null ? Math.min(100, Math.max(0, Number(score))) : null;
    const fillColor = scoreNum >= 80 ? '#4ade80' : scoreNum >= 50 ? '#fb923c' : '#f87171';
    const updDate  = profile.updated_at ? profile.updated_at.slice(0,10) : profile.last_enriched_at ? profile.last_enriched_at.slice(0,10) : '';
    const updLabel = updDate ? (() => { try { const d=new Date(updDate); return d.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}); } catch(e){return updDate;} })() : '';
    const _confPctColor = scoreNum == null ? '#94a3b8' : fillColor==='#4ade80'?'#15803d':fillColor==='#fb923c'?'#b45309':'#b91c1c';
    confEl.innerHTML = `
      <div class="cem-conf-lbl">Meridian confidence</div>
      <div class="cem-conf-row">
        <div class="cem-conf-track"><div class="cem-conf-fill" style="width:${scoreNum||0}%;background:${scoreNum!=null?fillColor:'#e2e8f0'}"></div></div>
        <span class="cem-conf-pct" style="color:${_confPctColor}">${scoreNum != null ? scoreNum+'%' : '—'}</span>
      </div>
      ${updLabel ? `<div class="cem-conf-date">Updated ${updLabel}</div>` : ''}
    `;
  }

  // Summary stats
  const drugCount    = sbDrugs.length;
  const dealCount    = sbDeals.filter(d => d.deal_type && d.deal_type !== 'news').length;
  const totalDealVal = sbDeals.reduce((s,d) => s + (parseFloat(d.total_usd_m)||0), 0);
  const catCount     = sbCats.length;
  const dealValStr   = totalDealVal >= 1000 ? `$${(totalDealVal/1000).toFixed(1)}B` : totalDealVal > 0 ? `$${Math.round(totalDealVal)}M` : '—';
  const areaLabel    = _CEMAreaMap[areaId] || (window._AREA_LABEL||{})[areaId] || areaId || '';

  const statsHtml = `<div class="cem-stats">
    <div class="cem-stat"><div class="cem-stat-lbl">Pipeline (${areaLabel})</div><div class="cem-stat-val">${drugCount} drug${drugCount!==1?'s':''}</div><div class="cem-stat-sub">${sbDrugs.filter(d=>d.stage&&(d.stage.includes('2')||d.stage.includes('3')||d.stage==='Approved')).length} Phase 2+</div></div>
    <div class="cem-stat"><div class="cem-stat-lbl">BD deal value</div><div class="cem-stat-val">${dealValStr}</div><div class="cem-stat-sub">${dealCount} deal${dealCount!==1?'s':''}</div></div>
    <div class="cem-stat"><div class="cem-stat-lbl">Upcoming catalysts</div><div class="cem-stat-val">${catCount}</div><div class="cem-stat-sub">in ${areaLabel}</div></div>
    ${(() => {
      const sp = companyRow?.stock_price; const mc = companyRow?.market_cap_usd_m;
      const chg = companyRow?.stock_change; const tkr = companyRow?.ticker;
      const cr = companyRow?.cash_runway;
      if (!sp && !mc) return '';
      const priceStr = sp ? `$${Number(sp).toFixed(2)}` : '—';
      const chgStr = chg != null ? `<span style="color:${chg>=0?'#16a34a':'#dc2626'};font-size:9px">${chg>=0?'+':''}${Number(chg).toFixed(1)}%</span>` : '';
      const mcStr = mc ? (mc>=1000?`$${(mc/1000).toFixed(1)}B`:`$${Math.round(mc)}M`) : '';
      const crStr = cr ? `<div style="font-size:9px;color:#94a3b8;margin-top:1px">Runway: ${cr}</div>` : '';
      return `<div class="cem-stat"><div class="cem-stat-lbl">${tkr&&tkr!=='Private'?tkr+' ':''}Market data</div><div class="cem-stat-val">${priceStr} ${chgStr}</div><div class="cem-stat-sub">${mcStr?'Mkt cap '+mcStr:''}</div>${crStr}</div>`;
    })()}
    <div class="cem-stat"><div class="cem-stat-lbl">Coverage score</div><div class="cem-stat-val" style="color:${(profile.completeness_score||0)>=80?'#15803d':(profile.completeness_score||0)>=50?'#b45309':'#94a3b8'}">${profile.completeness_score!=null?profile.completeness_score+'%':'—'}</div><div class="cem-stat-sub">Meridian completeness</div></div>
  </div>`;

  // Meridian Interpretation
  const piAssess  = (pi?.assessment||'').replace(/^\[ASSESSED\]\s*/i,'').slice(0,180);
  const vsAilux   = profile.vs_ailux   || '';
  const whyMatters= profile.why_it_matters || '';
  const bdSummary = profile.bd_summary || '';
  const platSumm  = profile.platform_summary || '';
  const keyRisk   = profile.key_risk || '';

  const interpDots = [
    piAssess  ? { col:'#dc2626', text: piAssess } : null,
    vsAilux   ? { col:'#7c3aed', text: vsAilux.slice(0,180) } : null,
    whyMatters? { col:'#059669', text: whyMatters.slice(0,180) } : null,
    bdSummary && !piAssess ? { col:'#0284c7', text: bdSummary.slice(0,180) } : null,
  ].filter(Boolean);

  if (!interpDots.length && platSumm) interpDots.push({ col:'#0284c7', text: platSumm.slice(0,200) });

  const interpSummHtml = interpDots.length
    ? `<div class="cem-interp-dots">${interpDots.map(d => `<div class="cem-interp-dot"><span style="width:7px;height:7px;border-radius:50%;background:${d.col};flex-shrink:0;margin-top:4px"></span><div>${d.text}</div></div>`).join('')}</div>`
    : `<div style="font-size:11px;color:#94a3b8;font-style:italic">Run enrichment to generate Meridian interpretation for this company.</div>`;

  const interpDetailHtml = `<div class="cem-det-inner">
    <div class="cem-det-title">Facts generating each interpretation</div>
    ${piAssess   ? `<div class="cem-fact"><span class="cem-fact-lbl" style="color:#dc2626">Assessment</span><span class="cem-fact-val">${piAssess}</span></div>` : ''}
    ${vsAilux    ? `<div class="cem-fact"><span class="cem-fact-lbl" style="color:#7c3aed">vs Ailux</span><span class="cem-fact-val">${vsAilux}</span></div>` : ''}
    ${whyMatters ? `<div class="cem-fact"><span class="cem-fact-lbl" style="color:#059669">Why it matters</span><span class="cem-fact-val">${whyMatters}</span></div>` : ''}
    ${keyRisk    ? `<div class="cem-fact"><span class="cem-fact-lbl">Key risk</span><span class="cem-fact-val">${keyRisk}</span></div>` : ''}
    ${bdSummary  ? `<div class="cem-fact"><span class="cem-fact-lbl">BD posture</span><span class="cem-fact-val">${bdSummary}</span></div>` : ''}
    ${platSumm   ? `<div class="cem-fact"><span class="cem-fact-lbl">Platform</span><span class="cem-fact-val">${platSumm.slice(0,250)}</span></div>` : ''}
    ${!(piAssess||vsAilux||whyMatters||bdSummary||platSumm) ? '<div style="font-size:11px;color:#94a3b8">No enrichment data found — run company enrichment pipeline.</div>' : ''}
  </div>`;

  const interpHtml = `<div class="cem-interp">
    <div class="cem-interp-hd" onclick="_cemToggle('co-interp')"><span>🧠 Meridian interpretation</span><span style="font-size:9px;color:#7c3aed;margin-left:auto">See underlying data <i id="cem-chev-co-interp" class="cem-chev">▶</i></span></div>
    ${interpSummHtml}
    <div class="cem-det" id="cem-det-co-interp">${interpDetailHtml}</div>
  </div>`;

  // Pipeline section
  const pipeSummary = sbDrugs.slice(0,4).map(d => {
    const dNameSafe = (d.display_name||d.name||'').replace(/'/g,"\\'");
    return `<div class="cem-item-row">
      ${_cemPhasePill(d.stage||d.phase)}
      <div style="flex:1;min-width:0">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:6px">
          <span style="font-size:12px;font-weight:600;color:#1d4ed8;cursor:pointer" onclick="openDrugEntityModal('${d.id}','${dNameSafe}',event)">${_drugNameHTML(d.display_name||d.name||'—')}</span>
          ${d.overlap ? _cemOverlapPill(d.overlap) : ''}
        </div>
        <div style="font-size:10.5px;color:#64748b">${d.mechanism||d.target||''} ${d.indication_short?'· '+d.indication_short:''}</div>
      </div>
    </div>`;
  }).join('');

  const pipeDetail = `<div class="cem-det-inner">
    <div class="cem-det-title">Full pipeline — ${areaLabel} area</div>
    <table class="cem-tbl"><thead><tr><th>Drug</th><th>Target</th><th>Phase</th><th>Overlap</th><th>Indication</th></tr></thead><tbody>
    ${sbDrugs.map(d => `<tr>
      <td><span style="color:#1d4ed8;cursor:pointer;font-weight:600" onclick="openDrugEntityModal('${d.id}','${(d.display_name||d.name||'').replace(/'/g,"\\'")}',event)">${_drugNameHTML(d.display_name||d.name||'—')}</span></td>
      <td style="color:#64748b">${d.target||d.mechanism||'—'}</td>
      <td>${_cemPhasePill(d.stage||d.phase)}</td>
      <td>${_cemOverlapPill(d.overlap)}</td>
      <td style="color:#64748b;font-size:10px">${d.indication_short||'—'}</td>
    </tr>`).join('')}
    </tbody></table>
  </div>`;

  // Deals section
  const realDeals = sbDeals.filter(d => d.deal_type && d.deal_type !== 'news');
  const dealSummary = realDeals.slice(0,3).map(d => {
    const valHtml = _cemFmtVal(d.upfront_usd_m, d.total_usd_m);
    const partner = d.to_company || d.from_company || '';
    return `<div class="cem-item-row" style="flex-direction:column;gap:3px">
      <div style="font-size:12px;font-weight:600;color:#0f172a">${d.headline ? _cemLink(d.headline.slice(0,80)+(d.headline.length>80?'…':''), d.headline) : _cemLink(partner||'Deal', companyName+' '+d.deal_type+' deal')}</div>
      <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
        <span style="font-size:10px;color:#94a3b8">${_cemFmtDate(d.deal_date)}</span>
        ${d.deal_type?`<span class="cem-pill cem-p-purple">${d.deal_type}</span>`:''}
        ${valHtml}
      </div>
    </div>`;
  }).join('');

  const dealDetail = `<div class="cem-det-inner">
    <div class="cem-det-title">All deals — ${companyName}</div>
    ${realDeals.length ? realDeals.map(d => {
      const partner = d.to_company||d.from_company||'';
      return `<div style="margin-bottom:10px;padding-bottom:10px;border-bottom:0.5px solid #e2e8f0">
        <div style="font-size:12px;font-weight:600;margin-bottom:3px">${d.headline ? _cemLink(d.headline, d.headline) : _cemLink(partner, companyName+' '+d.deal_type+' '+partner)}</div>
        <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:3px">
          ${d.deal_type?`<span class="cem-pill cem-p-purple">${d.deal_type}</span>`:''}
          ${_cemFmtVal(d.upfront_usd_m, d.total_usd_m)}
          <span style="font-size:10px;color:#94a3b8">${_cemFmtDate(d.deal_date)}</span>
        </div>
        ${partner ? `<div style="font-size:11px;color:#64748b">Partner: ${_cemLink(partner, partner+' pharma BD')}</div>` : ''}
        ${d.detail ? `<div style="font-size:11px;color:#1e293b;margin-top:4px">${d.detail.slice(0,200)}</div>` : ''}
      </div>`;
    }).join('') : '<div style="font-size:11px;color:#94a3b8">No deal records found.</div>'}
  </div>`;

  // ── Structured partnerships (Wave 2: surfaces company_partnerships) ──
  const _thisCoId = sbData?.company?.id || sbData?.profile?.company_id || '';
  const _partnerships = (sbData?.partnerships || []).filter(p => p && (p.partner_name || p.partner_company_name || p.lead_company_id));
  const _ptypeLbl = (p) => (p.partnership_type || p.deal_type || 'partnership').replace(/_/g,' ');
  const _ptColor = (p) => {
    const t = (p.partnership_type || p.deal_type || '').toLowerCase();
    if (t.includes('out') || t==='licensed_out') return {bg:'#eff6ff',c:'#1d4ed8'};
    if (t.includes('in') || t==='licensed_in')   return {bg:'#f0fdf4',c:'#15803d'};
    if (t.includes('accord') || t.includes('acquis')) return {bg:'#fef2f2',c:'#b91c1c'};
    return {bg:'#faf5ff',c:'#7c3aed'};
  };
  const _pPartnerName = (p) => {
    // show the OTHER party relative to the company whose modal this is
    if (_thisCoId && p.lead_company_id === _thisCoId) return p.partner_company_name || p.partner_name || p.partner_company_id || '—';
    if (_thisCoId && p.partner_company_id === _thisCoId) return p.lead_company_id || 'lead partner';
    return p.partner_company_name || p.partner_name || '—';
  };
  const _vPill = (p) => p.partnership_verified === true
    ? '<span title="Verified against a source" style="font-size:8px;font-weight:700;background:#f0fdf4;color:#15803d;border-radius:8px;padding:1px 5px">✓ verified</span>'
    : (p.partnership_verified === false
      ? '<span title="Flagged — not yet source-confirmed" style="font-size:8px;font-weight:700;background:#fffbeb;color:#b45309;border-radius:8px;padding:1px 5px">?</span>' : '');
  const partnershipCount = _partnerships.length;
  const partnershipSummary = _partnerships.slice(0,4).map(p => {
    const col=_ptColor(p);
    return `<div class="cem-item-row" style="align-items:center;gap:6px">
      <div style="flex:1;font-size:12px;font-weight:600;color:#0f172a">${_pPartnerName(p)}${p.drug_id?`<span style="font-size:10px;color:#94a3b8;font-weight:500"> · ${p.drug_id}</span>`:''}</div>
      <span style="font-size:8.5px;font-weight:700;text-transform:capitalize;background:${col.bg};color:${col.c};border-radius:8px;padding:1px 7px">${_ptypeLbl(p)}</span>
      ${_vPill(p)}
    </div>`;
  }).join('');
  const partnershipDetail = _partnerships.length ? `<div class="cem-det-inner">
    <div class="cem-det-title">Partnership relationships — company_partnerships</div>
    ${_partnerships.map(p => {
      const col=_ptColor(p);
      const src = p.source_url ? `<a class="cem-link" href="${p.source_url}" target="_blank" rel="noopener" data-trusted="1">↗ source</a>` : '';
      return `<div style="margin-bottom:9px;padding-bottom:9px;border-bottom:0.5px solid #e2e8f0">
        <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
          <span style="font-size:12px;font-weight:600;color:#0f172a">${_pPartnerName(p)}</span>
          <span style="font-size:8.5px;font-weight:700;text-transform:capitalize;background:${col.bg};color:${col.c};border-radius:8px;padding:1px 7px">${_ptypeLbl(p)}</span>
          ${p.is_current===false?'<span style="font-size:8px;color:#94a3b8">(ended)</span>':''}
          ${_vPill(p)}
        </div>
        <div style="font-size:10.5px;color:#64748b;margin-top:2px;display:flex;gap:8px;flex-wrap:wrap">
          ${p.drug_id?`<span>Asset: ${p.drug_id}</span>`:''}${p.geographic_rights?`<span>· ${p.geographic_rights}</span>`:''}${src?`<span>· ${src}</span>`:''}
        </div>
        ${p.notes?`<div style="font-size:10.5px;color:#475569;margin-top:2px">${String(p.notes).slice(0,160)}</div>`:''}
      </div>`;
    }).join('')}
  </div>` : '';

  // Catalysts section
  const catSummary = sbCats.slice(0,4).map(c => `
    <div class="cem-item-row">
      <div style="font-size:10px;color:#1d4ed8;font-weight:600;min-width:52px;flex-shrink:0">${c.sort_date?c.sort_date.slice(0,7):'—'}</div>
      <div style="font-size:12px;color:#1e293b">${_cemLink(c.headline||c.label||c.notes?.slice(0,80)||c.catalyst_type||'Catalyst', [companyName, c.headline||c.label||c.catalyst_type, c.drug_name||'', c.sort_date?c.sort_date.slice(0,4):''].filter(Boolean).join(' '))}</div>
    </div>`).join('');

  const catDetail = `<div class="cem-det-inner">
    <div class="cem-det-title">All upcoming catalysts</div>
    <table class="cem-tbl"><thead><tr><th>Date</th><th>Catalyst</th><th>Drug</th><th>Type</th></tr></thead><tbody>
    ${sbCats.map(c => `<tr>
      <td style="color:#1d4ed8;font-weight:600">${c.sort_date?c.sort_date.slice(0,10):'—'}</td>
      <td>${_cemLink(c.headline||c.catalyst_type||'—', [companyName, c.headline||c.catalyst_type||'', c.drug_name||'', c.sort_date?c.sort_date.slice(0,4):''].filter(Boolean).join(' '))}</td>
      <td style="color:#64748b;font-size:10px">${c.drug_name||'—'}</td>
      <td style="color:#64748b">${c.catalyst_type||'—'}</td>
    </tr>`).join('')}
    </tbody></table>
  </div>`;

  // Recent Coverage — news_articles + intel.primary_company_id (Fix 4)
  const _coNewsItems = sbData?.newsArticles || [];
  const _coIntelItems = sbData?.companyIntel || [];

  // Merge: intel first (higher signal), then news articles, dedup by headline
  const _allCoverage = [
    ..._coIntelItems.map(i => ({
      _type: 'intel', headline: i.headline, date: i.intel_date,
      source_url: i.source_url, summary: (i.body||'').slice(0,200),
      badge: i.intel_type || 'Intel', badge_bg: '#eff6ff', badge_color: '#1d4ed8',
      importance: i.importance,
    })),
    ..._coNewsItems.map(n => ({
      _type: 'news', headline: n.headline, date: n.published_at?.slice(0,10),
      source_url: n.article_url, summary: n.meridian_summary || n.why_it_matters || '',
      badge: n.source_name || 'News', badge_bg: '#f0fdf4', badge_color: '#15803d',
      relevance: n.relevance_score, drug_ids: n.matched_drug_ids,
    })),
  ].filter((item, idx, arr) =>
    arr.findIndex(x => (x.headline||'').slice(0,40) === (item.headline||'').slice(0,40)) === idx
  ).sort((a,b) => (b.date||'').localeCompare(a.date||''));

  const coverageSummary = _allCoverage.slice(0,3).map(item => {
    const dateStr = item.date ? (() => { try { const d = new Date(item.date); return d.toLocaleDateString('en-US',{month:'short',day:'numeric'}); } catch(e){return item.date.slice(0,10);} })() : '';
    return `<div class="cem-item-row" style="flex-direction:column;gap:2px">
      <div style="display:flex;align-items:flex-start;gap:5px">
        <span style="font-size:8px;font-weight:700;background:${item.badge_bg};color:${item.badge_color};border-radius:3px;padding:1px 5px;flex-shrink:0;margin-top:2px;max-width:70px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${(item.badge||'').toUpperCase().slice(0,10)}</span>
        <div style="flex:1">
          <div style="font-size:11.5px;font-weight:600;color:#0f172a;line-height:1.35">${item.source_url ? `<a href="${item.source_url}" target="_blank" rel="noopener" style="color:inherit;text-decoration:none">${(item.headline||'').slice(0,90)+(item.headline?.length>90?'…':'')}</a>` : (item.headline||'').slice(0,90)}</div>
          <div style="font-size:10px;color:#94a3b8;margin-top:1px">${dateStr}</div>
        </div>
      </div>
      ${item.summary ? `<div style="font-size:11px;color:#64748b;line-height:1.4;padding-left:0">${item.summary.slice(0,100)+(item.summary.length>100?'…':'')}</div>` : ''}
    </div>`;
  }).join('') || '<span style="font-size:11px;color:#94a3b8;font-style:italic">No recent coverage. news_articles and intel will appear here when matched to this company.</span>';

  const coverageDetail = `<div class="cem-det-inner">
    <div class="cem-det-title">All recent coverage — ${companyName}</div>
    <div style="font-size:9px;color:#94a3b8;margin-bottom:8px">Intel items (primary_company_id): ${_coIntelItems.length} · News articles (matched_company_ids): ${_coNewsItems.length}</div>
    ${_allCoverage.length ? _allCoverage.map(item => {
      const dateStr = item.date ? (() => { try { const d = new Date(item.date); return d.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}); } catch(e){return item.date.slice(0,10);} })() : '';
      return `<div style="margin-bottom:10px;padding-bottom:10px;border-bottom:0.5px solid #e2e8f0">
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:3px">
          <span style="font-size:8px;font-weight:700;background:${item.badge_bg};color:${item.badge_color};border-radius:3px;padding:1px 5px">${(item.badge||'').toUpperCase().slice(0,12)}</span>
          <span style="font-size:10px;color:#94a3b8">${dateStr}</span>
        </div>
        <div style="font-size:12px;font-weight:600;margin-bottom:3px">${item.source_url ? `<a href="${item.source_url}" target="_blank" rel="noopener" style="color:#1d4ed8;text-decoration:none">${item.headline||'Article'}</a>` : item.headline||'Article'}</div>
        ${item.summary ? `<div style="font-size:11px;color:#1e293b;line-height:1.5">${item.summary.slice(0,250)}</div>` : ''}
      </div>`;
    }).join('') : '<div style="font-size:11px;color:#94a3b8">No coverage found. Run fetch_homepage_news.py and ensure company_aliases are populated for this company.</div>'}
  </div>`;

  // Strategic signals
  const bdProfile  = bd?.profile || '';
  const bdFacts    = pi?.facts   || [];
  const bdDir      = pi?.direction || [];
  const bdLabels   = {acquirer:'Acquirer',licensor:'Licensor',collaborator:'Collaborator','partner-friendly':'Partner-Friendly','internal-focused':'Internal-Focused'};

  const sigsSummary = bdFacts.slice(0,3).map(f => `
    <div class="cem-item-row">
      <div class="cem-dot-gry"></div>
      <div style="font-size:11.5px;color:#1e293b">${f.slice(0,120)}</div>
    </div>`).join('') || (bdProfile ? `<div style="font-size:12px;color:#1e293b;font-weight:600">BD Profile: ${bdLabels[bdProfile]||bdProfile}</div>` : '<div style="font-size:11px;color:#94a3b8;font-style:italic">No signal intelligence — run enrichment.</div>');

  const sigsDetail = `<div class="cem-det-inner">
    <div class="cem-det-title">Full BD intelligence</div>
    ${bdProfile ? `<div class="cem-fact"><span class="cem-fact-lbl">BD profile</span><span class="cem-fact-val"><strong>${bdLabels[bdProfile]||bdProfile}</strong></span></div>` : ''}
    ${bdFacts.length ? bdFacts.map(f => `<div style="display:flex;gap:7px;margin-bottom:5px;font-size:11px"><span style="color:#94a3b8;flex-shrink:0">→</span><span style="color:#1e293b">${f}</span></div>`).join('') : ''}
    ${bdDir.length ? `<div style="margin-top:8px"><div class="cem-det-title">Direction signals</div>${bdDir.map(d=>`<div style="display:flex;gap:7px;margin-bottom:5px;font-size:11px"><span style="color:#1d4ed8;flex-shrink:0">→</span><span style="color:#1e293b">${d.replace(/^\[INFERRED\]\s*/i,'')}</span></div>`).join('')}</div>` : ''}
  </div>`;

  // Knowledge gaps
  const gaps = [];
  if (!pi) gaps.push({ level:'red', text:'Platform intelligence not enriched' });
  if (!bd) gaps.push({ level:'red', text:'BD intelligence not enriched' });
  if (!realDeals.length) gaps.push({ level:'amb', text:'No deal records found — verify company name mapping' });
  if (!sbCats.length) gaps.push({ level:'amb', text:'No catalyst data for this area' });
  if (profile.completeness_score < 50) gaps.push({ level:'amb', text: `Coverage score ${profile.completeness_score||0}% — below threshold` });
  if (!profile.vs_ailux) gaps.push({ level:'gry', text: 'vs. Ailux positioning not written' });

  const gapsSummary = gaps.slice(0,3).map(g => `
    <div class="cem-item-row">
      <div class="cem-dot-${g.level}"></div>
      <div style="font-size:11.5px;color:#1e293b">${g.text}</div>
    </div>`).join('') || '<div style="font-size:11px;color:#94a3b8;font-style:italic;padding:4px 0">No critical gaps detected.</div>';

  const gapsDetail = `<div class="cem-det-inner">
    <div class="cem-det-title">All knowledge gaps</div>
    ${gaps.map(g=>`<div style="display:flex;gap:8px;margin-bottom:6px;font-size:11px;align-items:flex-start"><div class="cem-dot-${g.level}" style="margin-top:3px"></div><div style="color:#1e293b">${g.text}</div></div>`).join('') || '<div style="font-size:11px;color:#94a3b8">No gaps detected.</div>'}
  </div>`;

  // Source confidence
  const srcSummary = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px"><span style="font-size:11.5px;color:#64748b">Pipeline data</span><span class="cem-pill cem-p-blue">ClinicalTrials · High</span></div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px"><span style="font-size:11.5px;color:#64748b">BD intelligence</span><span class="cem-pill ${pi?'cem-p-med':'cem-p-low'}">${pi?'AI enrichment · Medium':'Not enriched'}</span></div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px"><span style="font-size:11.5px;color:#64748b">Deal records</span><span class="cem-pill ${realDeals.length?'cem-p-high':'cem-p-low'}">${realDeals.length?'DB record · High':'Not found'}</span></div>
    <div style="display:flex;justify-content:space-between;align-items:center"><span style="font-size:11.5px;color:#64748b">Catalysts</span><span class="cem-pill ${sbCats.length?'cem-p-high':'cem-p-low'}">${sbCats.length?'DB record · High':'Not found'}</span></div>`;

  // ══ TABBED CARD ASSEMBLY ════════════════════════════════════════════════

  // ── Helpers for assessment / BD / platform intel rendering ──────────────
  const _confBadgeCem = c => {
    if (!c) return '';
    const cfg = c==='high'   ? {bg:'#f0fdf4',color:'#15803d',border:'#bbf7d0',label:'High confidence'} :
                c==='medium' ? {bg:'#fffbeb',color:'#b45309',border:'#fde68a',label:'Medium confidence'} :
                               {bg:'#f8fafc',color:'#64748b',border:'#e2e8f0',label:'Low confidence'};
    return `<span style="font-size:8px;font-weight:700;text-transform:uppercase;background:${cfg.bg};color:${cfg.color};border:1px solid ${cfg.border};border-radius:8px;padding:1px 6px">${cfg.label}</span>`;
  };

  const _renderCemAssessCard = (_pi, _bd) => {
    const _pa = (_pi?.assessment||'').replace(/^\[ASSESSED\]\s*/i,'');
    if (!_pa) return '';
    const _pcfgMap = {
      acquirer:{label:'Acquirer',bg:'#fef2f2',color:'#991b1b',border:'#fecaca'},
      licensor:{label:'Licensor',bg:'#eff6ff',color:'#1d4ed8',border:'#bfdbfe'},
      collaborator:{label:'Collaborator',bg:'#f0fdf4',color:'#15803d',border:'#bbf7d0'},
      'partner-friendly':{label:'Partner-Friendly',bg:'#f0fdf4',color:'#15803d',border:'#bbf7d0'},
      'internal-focused':{label:'Internal-Focused',bg:'#f8fafc',color:'#475569',border:'#e2e8f0'},
    };
    const _pc = _bd?.profile ? (_pcfgMap[_bd.profile]||{label:_bd.profile,bg:'#f8fafc',color:'#475569',border:'#e2e8f0'}) : null;
    const _pp = _pc ? `<span style="font-size:9px;font-weight:800;text-transform:uppercase;background:${_pc.bg};color:${_pc.color};border:1px solid ${_pc.border};border-radius:8px;padding:2px 8px">${_pc.label}</span>` : '';
    return `<div style="background:#faf9ff;border:1px solid #e9e5fb;border-radius:7px;padding:10px 12px;margin-bottom:10px">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:7px">
        <span style="font-size:8.5px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#7c3aed">Assessment</span>${_pp}
      </div>
      <p style="font-size:11.5px;color:#0f172a;font-weight:600;line-height:1.5;margin:0;border-left:2px solid #7c3aed;padding-left:8px">${_pa}</p>
    </div>`;
  };

  const _renderCemPlatformIntel = _pi => {
    if (!_pi) return null;
    const _facts = (_pi.facts||[]).map(f => `<li style="font-size:11px;color:#1e293b;padding:2px 0;line-height:1.45">${f}</li>`).join('');
    const _dir   = (_pi.direction||[]).map(d => {
      const _c = d.replace(/^\[INFERRED\]\s*/i,'');
      return `<li style="font-size:11px;color:#334155;padding:2px 0;line-height:1.45"><span style="font-size:8px;font-weight:800;text-transform:uppercase;color:#6d28d9;background:#ede9fe;border-radius:3px;padding:0 4px;margin-right:4px;vertical-align:middle">Inferred</span>${_c}</li>`;
    }).join('');
    return `<div class="pi-detail-section" style="display:flex;flex-direction:column"><h5 style="margin:0 0 8px;font-size:10.5px;font-weight:700;color:#475569">🧬 Platform Intelligence</h5>
      <div style="flex:1">${_facts?`<div style="font-size:8.5px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#94a3b8;margin-bottom:3px">Facts</div><ul style="margin:0 0 8px;padding-left:14px">${_facts}</ul>`:''
      }${_dir?`<div style="font-size:8.5px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#94a3b8;margin-bottom:3px">Direction</div><ul style="margin:0;padding-left:14px">${_dir}</ul>`:''
      }${!_facts&&!_dir?`<p style="font-size:11px;color:#94a3b8;font-style:italic;margin:0">Not yet enriched</p>`:''}</div>
      <div style="margin-top:8px;text-align:right">${_confBadgeCem(_pi.confidence)}</div>
    </div>`;
  };

  const _renderCemBdIntel = _bd => {
    if (!_bd) return null;
    const _bpcMap = {
      acquirer:{label:'Acquirer',bg:'#fef2f2',color:'#991b1b',border:'#fecaca'},
      licensor:{label:'Licensor',bg:'#eff6ff',color:'#1d4ed8',border:'#bfdbfe'},
      collaborator:{label:'Collaborator',bg:'#f0fdf4',color:'#15803d',border:'#bbf7d0'},
      'partner-friendly':{label:'Partner-Friendly',bg:'#f0fdf4',color:'#15803d',border:'#bbf7d0'},
      'internal-focused':{label:'Internal-Focused',bg:'#f8fafc',color:'#475569',border:'#e2e8f0'},
    };
    const _bpc = _bpcMap[_bd.profile]||{label:_bd.profile||'—',bg:'#f8fafc',color:'#475569',border:'#e2e8f0'};
    const _txRows = (_bd.transactions||[]).map(t =>
      `<div style="display:grid;grid-template-columns:56px 1fr auto;gap:6px;align-items:baseline;padding:3px 0;border-bottom:1px solid #f1f5f9;font-size:10.5px">
        <span style="color:#64748b;font-weight:600;white-space:nowrap">${t.date||''}</span>
        <span style="color:#1e293b">${t.asset||''}${t.partner?`<span style="color:#94a3b8"> · ${t.partner}</span>`:''}</span>
        <span style="color:#059669;font-weight:700;white-space:nowrap;font-size:10px">${t.total||t.upfront||''}</span>
      </div>`).join('');
    const _asmLines = (_bd.assessment||[]).map(a => {
      const _cl = a.replace(/^\[ASSESSED\]\s*/i,'');
      return `<li style="font-size:11px;color:#334155;padding:2px 0;line-height:1.45">${_cl}</li>`;
    }).join('');
    return `<div class="pi-detail-section" style="display:flex;flex-direction:column">
      <h5 style="margin:0 0 8px;font-size:10.5px;font-weight:700;color:#475569">🤝 BD Intelligence</h5>
      ${_bd.profile?`<div style="margin-bottom:8px"><span style="font-size:9px;font-weight:800;text-transform:uppercase;background:${_bpc.bg};color:${_bpc.color};border:1px solid ${_bpc.border};border-radius:8px;padding:2px 8px">${_bpc.label}</span></div>`:''}
      <div style="flex:1">${_txRows?`<div style="margin-bottom:8px">${_txRows}</div>`:''
      }${_asmLines?`<ul style="margin:0;padding-left:14px">${_asmLines}</ul>`:''
      }${!_txRows&&!_asmLines?`<p style="font-size:11px;color:#94a3b8;font-style:italic;margin:0">Not yet enriched</p>`:''}</div>
      <div style="margin-top:8px;text-align:right">${_confBadgeCem(_bd.confidence)}</div>
    </div>`;
  };

  // ── Area filter setup ────────────────────────────────────────────────────
  const _filterId    = prog.id || 'co';
  const _allAreaIds  = extraData?.allAreaIds     || [areaId];
  const _allAreaProf = extraData?.allAreaProfiles || {};
  const _allAreaCats = extraData?.allAreaCats    || {};
  const _allAreaSigs = extraData?.allAreaSigs    || {};
  const _currentArea = extraData?.currentArea   || areaId;
  const _AMAP2 = {tl1a:'TL1A',tslp:'TSLP',il4ra:'IL-4Rα',igf1r:'IGF1R/TSHR',fcrn:'FcRn',tcell:'BCMA/CD19/CD3',ox40l:'OX40L'};
  const _aLbl = a => _AMAP2[a] || (typeof _AREA_LABEL!=='undefined'?_AREA_LABEL[a]:null) || (a||'').toUpperCase();
  const _showAF = _allAreaIds.length > 1;

  // Populate header area pills slot (center of modal header)
  const _areaPillsEl = document.getElementById('entity-modal-area-pills');
  if (_areaPillsEl) {
    if (_showAF) {
      _areaPillsEl.id = 'cem-af-' + _filterId; // rename so _cemSwitchArea can find it
      _areaPillsEl.innerHTML =
        `<button class="cem-area-pill active" data-area="all" onclick="_cemSwitchArea('${_filterId}','all')">All areas</button>`
        + _allAreaIds.map(a => `<button class="cem-area-pill" data-area="${a}" onclick="_cemSwitchArea('${_filterId}','${a}')">${_aLbl(a)}</button>`).join('');
    } else {
      // Single-area: show one static pill (no filter needed)
      _areaPillsEl.innerHTML = _allAreaIds.length ? `<span class="cem-area-pill active" style="cursor:default">${_aLbl(_allAreaIds[0])}</span>` : '';
    }
  }
  const _areaFilterHtml = ''; // pills now live in the header, not in the body

  // ── OVERVIEW TAB ─────────────────────────────────────────────────────────
  // BD timing constraint banner — warns against "call now" when constraints exist
  const _seqBannerHtml = sbSeqConst.length ? sbSeqConst.map(sc => {
    const _expiry = sc.constraint_expires ? ` (expires ${sc.constraint_expires.slice(0,10)})` : '';
    const _blocked = sc.bd_action_blocked_until ? ` · blocked until ${sc.bd_action_blocked_until.slice(0,10)}` : '';
    const _note = sc.timing_note ? ` — ${sc.timing_note}` : '';
    return `<div style="background:#fff3cd;border:1px solid #ffc107;border-left:3px solid #e69900;border-radius:7px;padding:9px 12px;margin-bottom:8px;display:flex;gap:8px;align-items:flex-start">
      <span style="font-size:13px;flex-shrink:0">⚠️</span>
      <div>
        <span style="font-size:8.5px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#92400e">BD Timing Constraint${_expiry}</span>
        <div style="font-size:11.5px;font-weight:600;color:#78350f;margin-top:2px">${sc.constraint_description||sc.constraint_type||'Constraint'}</div>
        ${_note ? `<div style="font-size:10.5px;color:#92400e;margin-top:2px">${_note}${_blocked}</div>` : (_blocked ? `<div style="font-size:10.5px;color:#92400e;margin-top:2px">${_blocked}</div>` : '')}
      </div>
    </div>`;
  }).join('') : '';

  // Subsidiaries + acquired entities banner (Session 68)
  const _acquiredSubs  = sbSubs.filter(s => s.status === 'acquired');
  const _activeSubs    = sbSubs.filter(s => s.status === 'subsidiary');
  const _allSubsorted  = [..._activeSubs, ..._acquiredSubs];
  const _subsBannerHtml = _allSubsorted.length ? `<div style="display:flex;align-items:center;gap:8px;background:#f0fdf4;border:1px solid #bbf7d0;border-left:3px solid #15803d;border-radius:7px;padding:9px 12px;margin-bottom:10px;flex-wrap:wrap">
    <span style="font-size:8.5px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#15803d">Subsidiaries &amp; acquired entities</span>
    ${_activeSubs.map(s => `<span onclick="openCompanyEntityModal('${s.id}','${(s.name||'').replace(/'/g,"\\'")}','')" style="display:inline-flex;align-items:center;gap:5px;cursor:pointer;background:white;border:1px solid #bbf7d0;border-radius:12px;padding:3px 9px;font-size:11px;font-weight:600;color:#1d4ed8;white-space:nowrap"><span style="font-size:8px;font-weight:800;text-transform:uppercase;background:#eff6ff;color:#1d4ed8;border-radius:4px;padding:1px 5px">SUBSIDIARY</span>${s.name||s.id}</span>`).join('')}
    ${_acquiredSubs.map(s => `<span onclick="openCompanyEntityModal('${s.id}','${(s.name||'').replace(/'/g,"\\'")}','')" style="display:inline-flex;align-items:center;gap:5px;cursor:pointer;background:white;border:1px solid #bbf7d0;border-radius:12px;padding:3px 9px;font-size:11px;font-weight:600;color:#1d4ed8;white-space:nowrap"><span style="font-size:8px;font-weight:800;text-transform:uppercase;background:#fef2f2;color:#991b1b;border-radius:4px;padding:1px 5px">ACQUIRED</span>${s.name||s.id}</span>`).join('')}
  </div>` : '';

  // ── New data layers (2026-06-07) — financials banner, leadership line, and
  //    SEC events / patent estate / asset-transfer cells. Render only when non-empty.
  const _coXLink = (html, url) => url ? `<a class="cem-link" href="${url}" target="_blank" rel="noopener">${html}</a>` : html;
  const _coUsd = v => { const n = +v; if (!n || isNaN(n)) return ''; return n >= 1e9 ? `$${(n/1e9).toFixed(1)}B` : n >= 1e6 ? `$${(n/1e6).toFixed(0)}M` : `$${Math.round(n).toLocaleString()}`; };

  // Financials banner — cash, runway chip, burn (company_financials, SEC XBRL)
  const _coFin = sbData?.financials || null;
  const _finBits = [];
  if (_coFin) {
    if (_coFin.cash_and_equivalents) _finBits.push(`Cash ${_coUsd(_coFin.cash_and_equivalents)}${_coFin.cash_as_of?` <span style="color:#94a3b8;font-weight:400">(as of ${_coFin.cash_as_of.slice(0,7)})</span>`:''}`);
    if (_coFin.runway_quarters != null) {
      const _rq = Math.round(_coFin.runway_quarters * 10) / 10;
      const _rqCol = _rq < 4 ? '#b91c1c' : _rq < 8 ? '#b45309' : '#15803d';
      _finBits.push(`<span style="font-weight:800;color:${_rqCol}">Runway: ${_rq} quarters</span>`);
    }
    if (_coFin.quarterly_burn) _finBits.push(`Burn ${_coUsd(_coFin.quarterly_burn)}/qtr`);
  }
  const _finBannerHtml = _finBits.length ? `<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;background:#f8fafc;border:1px solid #e2e8f0;border-left:3px solid #0891b2;border-radius:7px;padding:8px 12px;margin-bottom:10px;font-size:11.5px;color:#1e293b">
    <span style="font-size:8.5px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#0891b2">💰 Financials</span>
    ${_finBits.join(' <span style="color:#cbd5e1">·</span> ')}
    ${_coFin?.source_url ? `<a href="${_coFin.source_url}" target="_blank" rel="noopener" style="font-size:10px;color:#1d4ed8;text-decoration:none;margin-left:auto">SEC ↗</a>` : ''}
  </div>` : '';

  // News sentiment banner (company_news_sentiment) — interpreted, not just a number (Kyle 2026-06-07)
  // net_sentiment is the mean article tone (−1 bearish … +1 bullish); n_articles is the sample.
  const _coSent = sbData?.newsSentiment || null;
  const _sentBannerHtml = (_coSent && _coSent.n_articles) ? (() => {
    const v = _coSent.net_sentiment, n = _coSent.n_articles;
    const lo = n < 3;  // thin sample caveat
    const band = v >= 0.35 ? ['Positive','#15803d','#dcfce7'] : v <= -0.35 ? ['Negative','#b91c1c','#fee2e2']
      : v > 0.1 ? ['Leaning positive','#15803d','#f0fdf4'] : v < -0.1 ? ['Leaning negative','#b45309','#fff7ed']
      : ['Mixed / neutral','#64748b','#f1f5f9'];
    const read = v >= 0.35 ? 'recent coverage skews favorable — readouts, deals, or approvals'
      : v <= -0.35 ? 'recent coverage skews adverse — failures, terminations, or safety'
      : 'no clear directional signal in recent coverage';
    return `<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;background:${band[2]};border:1px solid #e2e8f0;border-left:3px solid ${band[1]};border-radius:7px;padding:8px 12px;margin-bottom:10px;font-size:11.5px;color:#1e293b">
      <span style="font-size:8.5px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:${band[1]}">📰 News sentiment</span>
      <span style="font-weight:800;color:${band[1]}">${band[0]}</span>
      <span style="color:#94a3b8">net ${v>=0?'+':''}${(v).toFixed(2)} over ${n} article${n!==1?'s':''}${_coSent.last_article_date?`, latest ${_coSent.last_article_date.slice(0,10)}`:''}</span>
      <span style="flex-basis:100%;color:#64748b;font-size:10.5px">${read}.${lo?' <b style="color:#b45309">Thin sample</b> — directional only.':''} Tone of news flow, not a fundamental.</span>
    </div>`; })() : '';

  // Leadership one-liner (company_personnel)
  const _coPers = sbData?.personnel || [];
  const _persRank = { ceo:0, president:1, cso:2, cmo:3, cfo:4, coo:5, cbo:6 };
  const _persSorted = [..._coPers].sort((a,b) => (_persRank[a.role_category] ?? 9) - (_persRank[b.role_category] ?? 9));
  const _leadershipHtml = _coPers.length ? `<div style="font-size:11px;color:#475569;margin:0 2px 10px">👥 <span style="font-weight:700">Leadership:</span> ${_persSorted.slice(0,5).map(p =>
    `${_coXLink(p.person_name||'', p.source_url)}${p.role_category ? ` <span style="color:#94a3b8">(${(p.role_category||'').toUpperCase()})</span>` : (p.role ? ` <span style="color:#94a3b8">(${p.role})</span>` : '')}`
  ).join(' · ')}${_coPers.length > 5 ? ` <span style="color:#94a3b8">+${_coPers.length-5} more</span>` : ''}</div>` : '';

  // SEC filings & events cell (company_events, event_type ≠ 'other')
  const _coSecEv = sbData?.secEvents || [];
  const _SEC_EV_STYLE = {
    financing:        { lbl:'FINANCING',  bg:'#f0fdf4', co:'#065f46' },
    financial_update: { lbl:'FINANCIALS', bg:'#f8fafc', co:'#475569' },
    leadership:       { lbl:'LEADERSHIP', bg:'#faf5ff', co:'#7c3aed' },
    pipeline:         { lbl:'PIPELINE',   bg:'#eff6ff', co:'#1d4ed8' },
    deal:             { lbl:'DEAL',       bg:'#fff7ed', co:'#c2410c' },
    m_and_a:          { lbl:'M&A',        bg:'#fef2f2', co:'#991b1b' },
  };
  const _secEventsCellHtml = _coSecEv.length ? `<div class="cem-cell">
    <div class="cem-sec-hdr"><div class="cem-sec-lbl">🏛 SEC events</div><div class="cem-sec-hint">last ${_coSecEv.length}</div></div>
    <div class="cem-sec-body">${_coSecEv.map(e => {
      const sty = _SEC_EV_STYLE[e.event_type] || { lbl:(e.event_type||'EVENT').toUpperCase().slice(0,10), bg:'#f8fafc', co:'#64748b' };
      const dil = e.is_dilutive ? ' <span style="font-size:8px;font-weight:700;background:#fef9c3;color:#92400e;border-radius:4px;padding:1px 4px">dilutive</span>' : '';
      return `<div class="cem-item-row" style="align-items:flex-start">
        <span style="font-size:8px;font-weight:700;background:${sty.bg};color:${sty.co};border-radius:4px;padding:2px 5px;flex-shrink:0;margin-top:1px">${sty.lbl}</span>
        <div style="flex:1">
          <div style="font-size:11px;color:#1e293b;line-height:1.4">${_coXLink((e.event_summary||e.event_subtype||'SEC filing').slice(0,120)+((e.event_summary||'').length>120?'…':''), e.source_url)}${dil}</div>
          <div style="font-size:9.5px;color:#94a3b8;margin-top:1px">${[e.form_type, e.filing_date?e.filing_date.slice(0,10):''].filter(Boolean).join(' · ')}</div>
        </div>
      </div>`;
    }).join('')}</div>
  </div>` : '';

  // Patent estate cell (company_patents) — count by matched target + top 3 titles
  const _coPats2 = sbData?.companyPatents || [];
  const _patByTarget = {};
  _coPats2.forEach(p => { if (p.matched_target) _patByTarget[p.matched_target] = (_patByTarget[p.matched_target]||0) + 1; });
  const _patTargetChips = Object.entries(_patByTarget).sort((a,b) => b[1]-a[1]).slice(0,6)
    .map(([t,n]) => `<span style="font-size:9.5px;font-weight:700;background:#faf5ff;color:#7c3aed;border:1px solid #ddd6fe;border-radius:10px;padding:2px 8px;white-space:nowrap">${t.toUpperCase()} × ${n}</span>`).join(' ');
  const _patentsCellHtml = _coPats2.length ? `<div class="cem-cell">
    <div class="cem-sec-hdr"><div class="cem-sec-lbl">📜 Patent estate</div><div class="cem-sec-hint">${_coPats2.length} recent</div></div>
    <div class="cem-sec-body">
      ${_patTargetChips ? `<div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:6px">${_patTargetChips}</div>` : ''}
      ${_coPats2.slice(0,3).map(p => `<div class="cem-item-row" style="flex-direction:column;gap:1px;align-items:flex-start">
        <div style="font-size:11px;font-weight:600;color:#0f172a;line-height:1.35">${_coXLink((p.patent_title||p.patent_number||'Patent').slice(0,100), p.source_url)}</div>
        <div style="font-size:9.5px;color:#94a3b8">${[p.patent_number, p.grant_year ? 'granted '+p.grant_year : (p.patent_date ? 'published '+String(p.patent_date).slice(0,4) : '')].filter(Boolean).join(' · ')}</div>
      </div>`).join('')}
    </div>
  </div>` : '';

  // Asset transfer chains cell (asset_transfer_history involving this company)
  const _coTransfers = sbData?.transferChains || [];
  const _TT_SHORT = { license:'lic.', sublicense:'sub-lic.', acquisition:'acq.', co_development:'co-dev', spin_out:'spin-out', internal:'internal', merger:'merger' };
  const _transfersCellHtml = _coTransfers.length ? `<div class="cem-cell">
    <div class="cem-sec-hdr"><div class="cem-sec-lbl">🔁 Asset transfers</div><div class="cem-sec-hint">${_coTransfers.length}</div></div>
    <div class="cem-sec-body">${_coTransfers.slice(0,5).map(t => {
      const _drugLnk = t.drug_id ? `<span style="font-weight:700;color:#1d4ed8;cursor:pointer" onclick="openDrugEntityModal('${t.drug_id}','${(t.drug_id||'').replace(/'/g,"\\'")}',event)">${t.drug_id}</span>` : '';
      const _meth = `${_TT_SHORT[t.transfer_type]||t.transfer_type||''}${t.geographic_scope && t.geographic_scope!=='global' ? ' '+t.geographic_scope : ''}`;
      const _line = `${t.from_entity_name||'?'} <span style="color:#cbd5e1">→</span> ${t.to_entity_name||'?'} <span style="font-size:9px;color:#64748b;background:#f1f5f9;border-radius:3px;padding:1px 4px">${_meth}</span>`;
      return `<div class="cem-item-row" style="flex-direction:column;gap:1px;align-items:flex-start">
        <div style="font-size:11px;color:#1e293b">${_drugLnk}${_drugLnk?' — ':''}${t.source_url ? _coXLink(_line, t.source_url) : _line}</div>
        <div style="font-size:9.5px;color:#94a3b8">${[t.transfer_date?t.transfer_date.slice(0,7):'', t.deal_value_notes].filter(Boolean).join(' · ')}${t.verified===false?' · unverified':''}</div>
      </div>`;
    }).join('')}</div>
  </div>` : '';

  const _overviewContent = `<div>
    ${_seqBannerHtml}
    ${_subsBannerHtml}
    ${_finBannerHtml}
    ${_sentBannerHtml}
    ${_leadershipHtml}
    ${statsHtml}
    ${interpHtml}
    <div class="cem-grid">
      <div class="cem-cell">
        <div class="cem-sec-hdr" onclick="_cemToggle('co-pipe')"><div class="cem-sec-lbl">🔬 Pipeline</div><div class="cem-sec-hint">${drugCount} drug${drugCount!==1?'s':''} <i id="cem-chev-co-pipe" class="cem-chev">▶</i></div></div>
        <div class="cem-sec-body">${pipeSummary||'<span style="font-size:11px;color:#94a3b8;font-style:italic">No pipeline drugs found in this area.</span>'}</div>
        <div class="cem-det" id="cem-det-co-pipe">${pipeDetail}</div>
      </div>
      <div class="cem-cell">
        <div class="cem-sec-hdr" onclick="_cemToggle('co-deals')"><div class="cem-sec-lbl">🤝 Partnerships</div><div class="cem-sec-hint">${partnershipCount?partnershipCount+' relationship'+(partnershipCount!==1?'s':''):dealCount+' deal'+(dealCount!==1?'s':'')} <i id="cem-chev-co-deals" class="cem-chev">▶</i></div></div>
        <div class="cem-sec-body">${partnershipSummary || dealSummary || '<span style="font-size:11px;color:#94a3b8;font-style:italic">No partnership records found.</span>'}</div>
        <div class="cem-det" id="cem-det-co-deals">${partnershipDetail}${dealDetail}</div>
      </div>
      <div class="cem-cell">
        <div class="cem-sec-hdr" onclick="_cemToggle('co-cats')"><div class="cem-sec-lbl">📅 Catalysts</div><div class="cem-sec-hint">${catCount} upcoming <i id="cem-chev-co-cats" class="cem-chev">▶</i></div></div>
        <div class="cem-sec-body">${catSummary||'<span style="font-size:11px;color:#94a3b8;font-style:italic">No upcoming catalysts.</span>'}</div>
        <div class="cem-det" id="cem-det-co-cats">${catDetail}</div>
      </div>
      <div class="cem-cell">
        <div class="cem-sec-hdr" onclick="_cemToggle('co-coverage')"><div class="cem-sec-lbl">📰 Recent coverage</div><div class="cem-sec-hint">${_allCoverage.length ? _allCoverage.length+' items' : 'No matches'} <i id="cem-chev-co-coverage" class="cem-chev">▶</i></div></div>
        <div class="cem-sec-body">${coverageSummary}</div>
        <div class="cem-det" id="cem-det-co-coverage">${coverageDetail}</div>
      </div>
      <div class="cem-cell">
        <div class="cem-sec-hdr" onclick="_cemToggle('co-sigs')"><div class="cem-sec-lbl">⚡ Strategic signals</div><div class="cem-sec-hint">${bdFacts.length} signals <i id="cem-chev-co-sigs" class="cem-chev">▶</i></div></div>
        <div class="cem-sec-body">${sigsSummary}</div>
        <div class="cem-det" id="cem-det-co-sigs">${sigsDetail}</div>
      </div>
      <div class="cem-cell">
        <div class="cem-sec-hdr" onclick="_cemToggle('co-gaps')"><div class="cem-sec-lbl">⚠ Knowledge gaps</div><div class="cem-sec-hint">${gaps.length} gaps <i id="cem-chev-co-gaps" class="cem-chev">▶</i></div></div>
        <div class="cem-sec-body">${gapsSummary}</div>
        <div class="cem-det" id="cem-det-co-gaps">${gapsDetail}</div>
      </div>
      <div class="cem-cell">
        <div class="cem-sec-hdr" onclick="_cemToggle('co-src')"><div class="cem-sec-lbl">🛡 Source confidence</div><div class="cem-sec-hint">per section <i id="cem-chev-co-src" class="cem-chev">▶</i></div></div>
        <div class="cem-sec-body">${srcSummary}</div>
        <div class="cem-det" id="cem-det-co-src"><div class="cem-det-inner">
          <div class="cem-det-title">Source breakdown — ${companyName}</div>
          <div class="cem-fact"><span class="cem-fact-lbl">Last enriched</span><span class="cem-fact-val">${profile.last_enriched_at?profile.last_enriched_at.slice(0,10):'Not yet'}</span></div>
          <!-- DEPRECATED 2026-06-07 — Profile ID row removed from display (raw internal id, debug plumbing) -->
          <div class="cem-fact"><span class="cem-fact-lbl">Area context</span><span class="cem-fact-val">${areaLabel}</span></div>
        </div></div>
      </div>
      ${_secEventsCellHtml}
      ${_patentsCellHtml}
      ${_transfersCellHtml}
    </div>
  </div>`;

  // ── ASSESSMENT TAB ───────────────────────────────────────────────────────
  const _renderAreaAssessBlock = (_aId, _prof) => {
    const _pi2 = _prof?.platform_intelligence || null;
    const _bd2 = _prof?.bd_intelligence      || null;
    const _ac  = _renderCemAssessCard(_pi2, _bd2);
    const _ph  = _renderCemPlatformIntel(_pi2);
    const _bh  = _renderCemBdIntel(_bd2);
    if (!_ac && !_ph && !_bh) return `<p style="font-size:11px;color:#94a3b8;font-style:italic">No assessment data enriched for this area.</p>`;
    return `${_ac}<div class="cem-assess-intel-grid">
      ${_bh||'<div style="font-size:11px;color:#94a3b8;font-style:italic;padding:12px 0">BD intelligence not enriched</div>'}
      ${_ph||'<div style="font-size:11px;color:#94a3b8;font-style:italic;padding:12px 0">Platform intelligence not enriched</div>'}
    </div>`;
  };

  const _assessAllHtml = _allAreaIds.map(_aId => `<div class="cem-area-group">
    <div class="cem-area-group-hd">${_aLbl(_aId)}</div>
    ${_renderAreaAssessBlock(_aId, _allAreaProf[_aId]||null)}
  </div>`).join('');

  const _assessmentContent = `<div>
    <div class="cem-area-block active" data-fid="${_filterId}" data-area="all">
      ${_assessAllHtml||'<p style="color:#94a3b8;font-size:12px">No assessment data found.</p>'}
    </div>
    ${_allAreaIds.map(_aId => `<div class="cem-area-block" data-fid="${_filterId}" data-area="${_aId}">
      ${_renderAreaAssessBlock(_aId, _allAreaProf[_aId]||null)}
    </div>`).join('')}
  </div>`;

  // ── CATALYSTS TAB ────────────────────────────────────────────────────────
  const _catMONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const _fmtCatDate = iso => {
    if (!iso) return '—';
    const m = iso.match(/^(\d{4})-(\d{2})-?(\d{2})?/);
    if (m && m[3]) return `${_catMONTHS[parseInt(m[2])-1]} ${parseInt(m[3])}, ${m[1]}`;
    if (m) return `${_catMONTHS[parseInt(m[2])-1]} ${m[1]}`;
    return iso;
  };
  const _renderCatTable = _cats => {
    if (!_cats||!_cats.length) return '<p style="color:#94a3b8;font-size:12px;padding:4px 0">No upcoming catalysts on record</p>';
    const _rows = _cats.map(c => {
      const _lbl = c.headline||c.label||c.notes?.slice(0,80)||c.catalyst_type||'Catalyst';
      const _sig = c.significance==='high'?`<span style="font-size:8.5px;background:#fef9c3;color:#92400e;border-radius:4px;padding:1px 5px;margin-left:4px;font-weight:700">Key</span>`:'';
      const _lnk = c.source_url?`<a href="${c.source_url}" target="_blank" rel="noopener" style="color:#1d4ed8;text-decoration:none">${_lbl} ↗</a>${_sig}`:`${_lbl}${_sig}`;
      return `<tr><td style="color:#1d4ed8;font-weight:600;white-space:nowrap">${_fmtCatDate(c.sort_date)}</td><td style="font-size:11px">${_lnk}</td><td style="color:#64748b;font-size:10px">${c.drug_name||'—'}</td><td style="color:#64748b;font-size:10px">${c.catalyst_type||'—'}</td></tr>`;
    }).join('');
    return `<table class="cem-tbl"><thead><tr><th>Date</th><th>Catalyst</th><th>Drug</th><th>Type</th></tr></thead><tbody>${_rows}</tbody></table>`;
  };

  const _allCatsFlat = [];
  const _seenCatIds  = new Set();
  _allAreaIds.forEach(_aId => {
    (_allAreaCats[_aId]||[]).forEach(c => {
      const _k = c.id||(c.label||'')+(c.sort_date||'');
      if (!_seenCatIds.has(_k)) { _seenCatIds.add(_k); _allCatsFlat.push(c); }
    });
  });
  _allCatsFlat.sort((a,b) => (a.sort_date||'').localeCompare(b.sort_date||''));
  const _totalCatCount = _allCatsFlat.length;

  const _catalystsContent = `<div>
    <div class="cem-area-block active" data-fid="${_filterId}" data-area="all">
      ${_renderCatTable(_allCatsFlat)}
    </div>
    ${_allAreaIds.map(_aId => `<div class="cem-area-block" data-fid="${_filterId}" data-area="${_aId}">
      ${_renderCatTable(_allAreaCats[_aId]||[])}
    </div>`).join('')}
  </div>`;

  // ── RELATED NEWS TAB ─────────────────────────────────────────────────────
  const _newsItems = sbData?.deals || [];
  const _NMONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const _fmtNewsDate = iso => {
    if (!iso) return '';
    const m = iso.match(/^(\d{4})-(\d{2})-?(\d{2})?/);
    if (m && m[3]) return `${_NMONTHS[parseInt(m[2])-1]} ${parseInt(m[3])}, ${m[1]}`;
    if (m) return `${_NMONTHS[parseInt(m[2])-1]} ${m[1]}`;
    return iso.slice(0,10);
  };
  const _renderNewsRow = d => {
    const _typeMap = {acquisition:'M&A',license:'License',collaboration:'Collaboration',option:'Option',financing:'Financing',news:'News',press_release:'News'};
    const _tl = _typeMap[d.deal_type]||d.deal_type||'News';
    const _tbg = d.deal_type==='acquisition'?'#fef2f2':d.deal_type==='license'?'#eff6ff':d.deal_type==='collaboration'?'#f0fdf4':d.deal_type==='financing'?'#f0fdf4':'#f8fafc';
    const _tc  = d.deal_type==='acquisition'?'#991b1b':d.deal_type==='license'?'#1d4ed8':d.deal_type==='collaboration'?'#15803d':d.deal_type==='financing'?'#065f46':'#64748b';
    const _tb  = d.deal_type==='acquisition'?'#fecaca':d.deal_type==='license'?'#bfdbfe':d.deal_type==='collaboration'?'#bbf7d0':d.deal_type==='financing'?'#a7f3d0':'#e2e8f0';
    const _tpill = `<span style="font-size:8px;font-weight:800;text-transform:uppercase;background:${_tbg};color:${_tc};border:1px solid ${_tb};border-radius:4px;padding:1px 5px;flex-shrink:0">${_tl}</span>`;
    const _hl  = d.headline||(d.from_company||d.to_company||companyName)+' · '+_tl;
    const _lnk = d.source_url
      ? `<a href="${d.source_url}" target="_blank" rel="noopener" style="color:#1e3a5f;font-weight:600;text-decoration:none;border-bottom:1px solid #bfdbfe;word-break:break-word">${_hl.slice(0,100)}${_hl.length>100?'…':''} ↗</a>`
      : `<span style="color:#1e3a5f;font-weight:600;word-break:break-word">${_hl.slice(0,100)}${_hl.length>100?'…':''}</span>`;
    const _u = parseFloat(d.upfront_usd_m), _t = parseFloat(d.total_usd_m);
    const _fmtV = v => v>=1000?`$${(v/1000).toFixed(1)}B`:`$${Math.round(v)}M`;
    const _vp = [!isNaN(_u)&&_u>0?`<span class="cem-pill" style="background:#fef3c7;color:#92400e">${_fmtV(_u)} upfront</span>`:'',!isNaN(_t)&&_t>0?`<span class="cem-pill cem-p-high">${_fmtV(_t)} total</span>`:''].filter(Boolean).join(' ');
    const _det = d.detail?`<div style="font-size:10px;color:#64748b;margin-top:3px;line-height:1.4">${d.detail.slice(0,180)}${d.detail.length>180?'…':''}</div>`:'';
    return `<div style="display:flex;gap:8px;align-items:flex-start;margin-bottom:10px;padding-bottom:10px;border-bottom:1px solid #f1f5f9">
      <span style="color:#94a3b8;font-size:9px;flex-shrink:0;padding-top:3px;min-width:70px">${_fmtNewsDate(d.deal_date)}</span>
      ${_tpill}
      <div style="min-width:0;flex:1">${_lnk}${_vp?`<div style="margin-top:3px">${_vp}</div>`:''}${_det}</div>
    </div>`;
  };

  const _newsContent = `<div>
    ${_newsItems.length
      ? `<div style="${_newsItems.length>10?'max-height:500px;overflow-y:auto;scrollbar-width:thin;padding-right:4px':''}">
           ${_newsItems.length>10?`<div style="font-size:9.5px;color:#94a3b8;margin-bottom:8px">${_newsItems.length} items · scroll for more</div>`:''}
           ${_newsItems.map(_renderNewsRow).join('')}
         </div>`
      : '<p style="color:#94a3b8;font-size:12px">No news or deals on record — enrichment pipeline will populate.</p>'
    }
  </div>`;

  // ── COMPETITIVE SIGNALS TAB ─────────────────────────────────────────────
  const _SIG_STYLE_CEM = {
    conference:      { label:'CONF',    bg:'#eff6ff', color:'#1d4ed8', border:'#bfdbfe' },
    clinical_update: { label:'READOUT', bg:'#f0fdf4', color:'#15803d', border:'#bbf7d0' },
    regulatory:      { label:'REG',     bg:'#fef2f2', color:'#b91c1c', border:'#fecaca' },
    financing:       { label:'$',       bg:'#f0fdf4', color:'#065f46', border:'#a7f3d0' },
    patent:          { label:'PATENT',  bg:'#faf5ff', color:'#7c3aed', border:'#ddd6fe' },
    publication:     { label:'PUB',     bg:'#f5f3ff', color:'#4338ca', border:'#c7d2fe' },
    licensing:       { label:'DEAL',    bg:'#fff7ed', color:'#c2410c', border:'#fed7aa' },
  };
  const _renderSigRow = s => {
    const st = _SIG_STYLE_CEM[s.signal_type] || { label: s.signal_type||'—', bg:'#f8fafc', color:'#64748b', border:'#e2e8f0' };
    const badge = `<span style="font-size:8px;font-weight:800;text-transform:uppercase;background:${st.bg};color:${st.color};border:1px solid ${st.border};border-radius:4px;padding:1px 6px;flex-shrink:0;white-space:nowrap">${st.label}</span>`;
    const date  = (s.source_date||'').slice(0,7);
    const title = s.source_url
      ? `<a href="${s.source_url}" target="_blank" rel="noopener" style="color:#1e3a5f;font-weight:600;text-decoration:none;border-bottom:1px solid #bfdbfe">${s.title||''}</a>`
      : `<span style="color:#1e3a5f;font-weight:600">${s.title||''}</span>`;
    const desc  = s.description ? `<div style="font-size:10px;color:#64748b;margin-top:2px;line-height:1.4">${s.description.slice(0,200)}${s.description.length>200?'…':''}</div>` : '';
    return `<div style="display:flex;gap:8px;align-items:flex-start;padding:9px 0;border-bottom:1px solid #f1f5f9">
      <span style="color:#94a3b8;font-size:9px;flex-shrink:0;padding-top:3px;min-width:46px">${date}</span>
      ${badge}
      <div style="min-width:0;flex:1;font-size:11.5px">${title}${desc}</div>
    </div>`;
  };
  const _renderSigTable = _sigs => {
    if (!_sigs||!_sigs.length) return '<p style="color:#94a3b8;font-size:12px;padding:4px 0">No competitive signals on record for this area.</p>';
    return `<div style="${_sigs.length>8?'max-height:500px;overflow-y:auto;scrollbar-width:thin;padding-right:4px':''}">${_sigs.map(_renderSigRow).join('')}</div>`;
  };
  // Flatten all signals for "All areas" view
  const _allSigsFlat = [];
  const _seenSigIds = new Set();
  _allAreaIds.forEach(_aId => {
    (_allAreaSigs[_aId]||[]).forEach(s => {
      const _k = s.id || (s.title||'')+(s.source_date||'');
      if (!_seenSigIds.has(_k)) { _seenSigIds.add(_k); _allSigsFlat.push({...s, _area: _aId}); }
    });
  });
  _allSigsFlat.sort((a,b) => (b.source_date||'').localeCompare(a.source_date||''));
  const _totalSigCount = _allSigsFlat.length;

  const _signalsContent = `<div>
    <div class="cem-area-block active" data-fid="${_filterId}" data-area="all">
      ${_renderSigTable(_allSigsFlat)}
    </div>
    ${_allAreaIds.map(_aId => `<div class="cem-area-block" data-fid="${_filterId}" data-area="${_aId}">
      ${_renderSigTable(_allAreaSigs[_aId]||[])}
    </div>`).join('')}
  </div>`;

  // ── DATA QUALITY TAB ─────────────────────────────────────────────────────
  // Shows drug_validation_results (fail/warn/review) and recent field_change_audit entries.
  const _dqStatusCls = s => s==='pass'?'cem-dq-pass':s==='fail'?'cem-dq-fail':s==='warning'?'cem-dq-warn':s==='needs_review'?'cem-dq-review':'cem-dq-unknown';
  const _dqStatusLabel = s => s==='pass'?'Pass':s==='fail'?'Fail':s==='warning'?'Warning':s==='needs_review'?'Review':'?';
  const _dqCheckLabel = t => {
    const map = { stage_trial_match:'Stage vs Trial', brand_name_approved:'Brand Name → Approved', source_url_required:'Source URL', codev_requires_source:'Co-dev Source', approval_date_approved:'Approval Date → Approved' };
    return map[t] || (t||'').replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
  };

  // Group validation issues by drug
  const _dvByDrug = {};
  sbDrugValidation.forEach(v => { (_dvByDrug[v.drug_id] = _dvByDrug[v.drug_id]||[]).push(v); });
  const _dvDrugNames = {};
  sbDrugs.forEach(d => { if (d.id) _dvDrugNames[d.id] = d.display_name||d.name||d.id; });

  const _validationHtml = Object.keys(_dvByDrug).length
    ? Object.entries(_dvByDrug).map(([dId, rows]) => {
        const dName = _dvDrugNames[dId] || dId;
        const rowHtml = rows.map(v => `<div class="cem-dq-row">
          <div class="cem-dq-status ${_dqStatusCls(v.status)}" title="${_dqStatusLabel(v.status)}"></div>
          <div style="flex:1;min-width:0">
            <div style="font-size:11px;font-weight:700;color:#0f172a">${_dqCheckLabel(v.check_type)}</div>
            ${v.detail ? `<div style="font-size:10px;color:#64748b;line-height:1.4;margin-top:1px">${(v.detail||'').slice(0,200)}</div>` : ''}
          </div>
          <span style="font-size:9px;font-weight:700;background:${v.status==='fail'?'#fef2f2':v.status==='warning'?'#fffbeb':'#f5f3ff'};color:${v.status==='fail'?'#b91c1c':v.status==='warning'?'#92400e':'#6d28d9'};border:1px solid ${v.status==='fail'?'#fecaca':v.status==='warning'?'#fde68a':'#ddd6fe'};border-radius:6px;padding:1px 6px;white-space:nowrap">${_dqStatusLabel(v.status)}</span>
        </div>`).join('');
        return `<div style="margin-bottom:12px">
          <div style="font-size:9.5px;font-weight:800;text-transform:uppercase;letter-spacing:0.05em;color:#64748b;margin-bottom:4px">${dName}</div>
          ${rowHtml}
        </div>`;
      }).join('')
    : '<div style="font-size:11px;color:#94a3b8;font-style:italic;padding:8px 0">No validation issues found — all checks passing or not yet run.</div>';

  // Recent field changes
  const _MONTHS_FA = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const _fmtFaDate = iso => {
    if (!iso) return '—';
    const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
    return m ? `${_MONTHS_FA[parseInt(m[2])-1]} ${parseInt(m[3])}` : iso.slice(0,10);
  };
  const _auditHtml = sbFieldAudit.length
    ? sbFieldAudit.map(row => {
        const entityLabel = row.entity_type === 'drug'
          ? (_dvDrugNames[row.entity_id] || row.entity_id || 'Drug')
          : (companyName || 'Company');
        const fieldDisplay = (row.field_name||'').replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
        return `<div class="cem-audit-row">
          <span style="font-size:9px;color:#94a3b8;flex-shrink:0;min-width:44px;padding-top:1px">${_fmtFaDate(row.changed_at)}</span>
          <div style="flex:1;min-width:0">
            <div style="display:flex;align-items:center;gap:5px;flex-wrap:wrap">
              <span class="cem-audit-field">${fieldDisplay}</span>
              <span style="font-size:9px;color:#94a3b8">${entityLabel}</span>
            </div>
            <div style="display:flex;align-items:center;gap:6px;margin-top:2px">
              ${row.old_value ? `<span class="cem-audit-old">${(row.old_value||'').slice(0,60)}</span><span style="font-size:10px;color:#94a3b8">→</span>` : ''}
              <span class="cem-audit-new">${(row.new_value||'').slice(0,80)}</span>
            </div>
          </div>
        </div>`;
      }).join('')
    : '<div style="font-size:11px;color:#94a3b8;font-style:italic;padding:8px 0">No recent field changes recorded.</div>';

  const _totalDqIssues = sbDrugValidation.length;
  const _dqContent = `<div>
    <div style="margin-bottom:16px">
      <div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#64748b;margin-bottom:8px">Validation Issues</div>
      ${_validationHtml}
    </div>
    <div>
      <div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#64748b;margin-bottom:8px">Recent Changes</div>
      ${_auditHtml}
    </div>
  </div>`;

  // ── Assemble tabs + panels ────────────────────────────────────────────────
  const _filesContent = `<div>
    <div class="cem-files-header">
      <div class="cem-files-filter">
        <button class="cem-file-filter-btn active" onclick="filterCompanyFiles('all', this)">All</button>
        <button class="cem-file-filter-btn" onclick="filterCompanyFiles('abstract', this)">Abstracts</button>
        <button class="cem-file-filter-btn" onclick="filterCompanyFiles('8-K', this)">SEC Filings</button>
        <button class="cem-file-filter-btn" onclick="filterCompanyFiles('clinical_data', this)">Clinical Data</button>
        <button class="cem-file-filter-btn" onclick="filterCompanyFiles('press_release', this)">Press Releases</button>
      </div>
    </div>
    <div id="cem-files-list" class="cem-files-list">
      <div class="cem-files-loading">Select this tab to load documents.</div>
    </div>
  </div>`;

  // BD Intelligence tab — lazy-loaded on first activation
  const _svs = companyRow?.strategic_value_score ?? null;
  const _svsBadgeInline = _svs != null ? (() => {
    const col = _svs >= 80 ? '#15803d' : _svs >= 60 ? '#b45309' : '#64748b';
    const bg  = _svs >= 80 ? '#dcfce7' : _svs >= 60 ? '#fef9c3' : '#f1f5f9';
    return ` <span style="font-size:10px;font-weight:800;background:${bg};color:${col};border-radius:6px;padding:2px 7px;border:1px solid ${col}30">${_svs}</span>`;
  })() : '';
  const _bdContent = `<div id="cem-tab-bd-panel" style="min-height:120px"><div style="padding:20px;text-align:center;color:#94a3b8;font-size:12px;font-style:italic">Activate tab to load BD intelligence…</div></div>`;

  const _tabs = [
    { id:'cem-tab-overview',   label:'Overview' },
    { id:'cem-tab-assessment', label:'Assessment' },
    { id:'cem-tab-catalysts',  label:`Catalysts${_totalCatCount?' ('+_totalCatCount+')':''}` },
    { id:'cem-tab-news',       label:'Related News' },
    { id:'cem-tab-signals',    label:`Signals${_totalSigCount?' ('+_totalSigCount+')':''}` },
    { id:'cem-tab-bd',         label:`BD Intel${_svsBadgeInline}` },
    { id:'cem-tab-dq',         label:`Data Quality${_totalDqIssues?' ('+_totalDqIssues+')':''}` },
    ...(_coFacts.length ? [{ id:'cem-tab-research', label:`📑 Research (${_coFacts.length})` }] : []),
    { id:'cem-tab-files',      label:'📁 Files' },
  ];
  const _panels = [
    ...(_coFacts.length ? [{ id:'cem-tab-research', content: _coResearchContent }] : []),
    { id:'cem-tab-overview',   content: _overviewContent },
    { id:'cem-tab-assessment', content: _assessmentContent },
    { id:'cem-tab-catalysts',  content: _catalystsContent },
    { id:'cem-tab-news',       content: _newsContent },
    { id:'cem-tab-signals',    content: _signalsContent },
    { id:'cem-tab-bd',         content: _bdContent },
    { id:'cem-tab-dq',         content: _dqContent },
    { id:'cem-tab-files',      content: _filesContent },
  ];

  return _areaFilterHtml + _buildDossierShell(_tabs, _panels);
}

// Close modals on Escape key
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    closeEntityModal();
  }
});

/* ─── Shared area/tab color maps ─────────────────────────────────────────── */
const _AREA_CLS   = { tl1a:'ct', tslp:'ct', il4ra:'ct-t2', igf1r:'ct-ted', fcrn:'ct-ai', tcell:'ct-ir', ox40l:'ct-t2' };
const _AREA_LABEL = { tl1a:'TL1A', tslp:'TSLP', il4ra:'IL-4Rα', igf1r:'IGF1R/TSHR', fcrn:'FcRn', tcell:'BCMA/CD19/CD3', ox40l:'OX40L',
  ibd:'IBD', uc:'UC', cd:'CD', ted:'TED', autoimmune:'Autoimmune', respiratory:'Respiratory' };
const _TAB_CLS    = { 'tl1a':'ct','tslp':'ct','il4ra-tslp':'ct-t2','il4ra-ox40l':'ct-t2','igf1r-tshr':'ct-ted','fcrn':'ct-ai','ace':'ct-ir' };

/* ─── Company modal ──────────────────────────────────────────────────────── */
async function openEntityModal(type, id, name, sourceTabId) {
  const overlay  = document.getElementById('entity-modal-overlay');
  const titleEl  = document.getElementById('entity-modal-title');
  const subEl    = document.getElementById('entity-modal-sub');
  const bodyEl   = document.getElementById('entity-modal-body');
  const footerEl = document.getElementById('entity-modal-footer');
  const tagsEl   = document.getElementById('entity-modal-also-tags');
  if (!overlay) return;

  titleEl.textContent = name;
  subEl.textContent   = 'Company Profile';
  bodyEl.innerHTML    = '<div style="padding:40px;text-align:center;color:#94a3b8;font-style:italic;font-size:13px">⟳ Loading…</div>';
  footerEl.style.display = 'none';
  tagsEl.innerHTML = '';
  overlay.classList.add('open');
  document.body.style.overflow = 'hidden';

  if (!_sb) {
    bodyEl.innerHTML = '<p style="padding:20px;color:#dc2626;font-size:13px">Database not available.</p>';
    return;
  }

  try {
    const [profRes, catRes, drugRes, dealRes] = await Promise.all([
      _sb.from('company_profiles').select('*').eq('company_id', id).limit(10),
      _sb.from('catalysts').select('label,catalyst_date,sort_date,notes').eq('company_id', id).order('sort_date').limit(8),
      _sb.from('drugs').select('id,name,display_name,stage,mechanism,drug_summary,overlap,overlap_rationale,strategic_role,company_id,lead_company_id,co_developer_ids').or(`company_id.eq.${id},lead_company_id.eq.${id},co_developer_ids.cs.{${id}}`).limit(15),
      _sb.from('deals').select('headline,deal_date,deal_type,total_usd_m,source_url').eq('company_id', id).order('deal_date', {ascending:false}).limit(5),
    ]);

    const profiles = profRes.data || [];
    const cats     = catRes.data  || [];
    const drugs    = drugRes.data || [];
    const deals    = dealRes.data || [];

    // Fetch trials for all company drugs
    const drugIds = drugs.map(d => d.id).filter(Boolean);
    let trials = [];
    if (drugIds.length) {
      const { data: trialRows } = await _sb.from('trials')
        .select('id,drug_id,trial_name,status,phase,n_enrollment,primary_completion_date,indication,primary_endpoint')
        .in('drug_id', drugIds).limit(25);
      trials = trialRows || [];
    }

    subEl.textContent = profiles.length ? `${profiles.length} area${profiles.length>1?'s':''} tracked` : 'Company profile';
    bodyEl.innerHTML  = _entityModalBodyHTML(profiles, cats, drugs, deals, trials);

    // "Also tracked in" footer strip
    if (drugIds.length) {
      const { data: daRows } = await _sb.from('drug_areas').select('area_id').in('drug_id', drugIds);
      if (daRows && daRows.length) {
        const areaToTabs = {};
        Object.entries(TAB_AREA_MAP).forEach(([t, as]) => as.forEach(a => { (areaToTabs[a] = areaToTabs[a] || []).push(t); }));
        const foundAreas = [...new Set(daRows.map(r => r.area_id))];
        const otherTabs  = [...new Set(foundAreas.flatMap(a => areaToTabs[a] || []).filter(t => t !== sourceTabId))];
        if (otherTabs.length) {
          tagsEl.innerHTML = otherTabs.map(t => {
            const label = TAB_META[t]?.badge || TAB_META[t]?.name || t;
            return `<span class="entity-also-tag ${_TAB_CLS[t]||'ct'}" onclick="closeEntityModal();navTo('${t}')">${label}</span>`;
          }).join('');
          footerEl.style.display = 'flex';
        }
      }
    }
  } catch(e) {
    console.warn('[entityModal]', e);
    bodyEl.innerHTML = `<div style="padding:20px;color:#dc2626;font-size:13px">Failed to load: ${e.message}</div>`;
  }
}

function _eModalSelectArea(evt, areaId, btn) {
  evt.stopPropagation();
  btn.closest('.emodal-area-tabs').querySelectorAll('.emodal-atab').forEach(b => {
    b.style.background = '#f1f5f9'; b.style.color = '#64748b';
  });
  btn.style.background = '#0d1f38'; btn.style.color = 'white';
  btn.closest('.entity-modal-body').querySelectorAll('.emodal-panel').forEach(p => {
    p.style.display = p.dataset.area === areaId ? 'block' : 'none';
  });
}

function _entityModalBodyHTML(profiles, cats, drugs, deals, trials) {
  // ── Brief one-sentence company blurb ────────────────────────────────────
  const firstSummary = profiles.find(p => p.platform_summary)?.platform_summary || '';
  const briefBlurb = firstSummary
    ? (() => { const m = firstSummary.match(/^.+?[.!?](?:\s|$)/); return m ? m[0].trim() : (firstSummary.length > 220 ? firstSummary.slice(0,220)+'…' : firstSummary); })()
    : '';

  // ── Area tabs ────────────────────────────────────────────────────────────
  const trackedAreas = profiles.filter(p => p.area_id && (p.platform_summary || p.bd_summary));
  const multiArea    = trackedAreas.length > 1;
  const activeStyle  = 'background:#0d1f38;color:white;';
  const inactiveStyle = 'background:#f1f5f9;color:#64748b;';
  const tabBase = 'display:inline-flex;align-items:center;gap:5px;padding:4px 12px;border-radius:20px;font-size:11px;font-weight:700;cursor:pointer;border:none;transition:all 0.15s;';

  const areaTabs = multiArea ? `
    <div class="emodal-area-tabs" style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px;padding-bottom:14px;border-bottom:1px solid #e2e8f0">
      <button class="emodal-atab" style="${tabBase}${activeStyle}" onclick="_eModalSelectArea(event,'__overview__',this)">Overview</button>
      ${trackedAreas.map(p => {
        const aLbl = _AREA_LABEL[p.area_id] || p.area_id.toUpperCase();
        const aCls = _AREA_CLS[p.area_id]   || 'ct';
        return `<button class="emodal-atab" style="${tabBase}${inactiveStyle}" onclick="_eModalSelectArea(event,'${p.area_id}',this)"><span class="entity-also-tag ${aCls}" style="cursor:default;font-size:9px;padding:1px 6px;margin:0">${aLbl}</span></button>`;
      }).join('')}
    </div>` : '';

  // ── Drug pill helper ─────────────────────────────────────────────────────
  const drugPill = d => {
    const dn = (d.display_name||d.name||'').replace(/'/g,"\\'");
    return `<span class="pi-entity-name" style="display:inline-block;font-size:11px;font-weight:700;background:#e8f0f8;color:#1a3a6e;padding:3px 9px;border-radius:8px;margin:2px;cursor:pointer" onclick="openDrugEntityModal('${d.id}','${dn}',event)">${_drugNameHTML(d.display_name||d.name||'—')}</span>`;
  };

  // ── Overview panel content ───────────────────────────────────────────────
  let overviewHtml = '';
  if (briefBlurb)
    overviewHtml += `<p style="margin:0 0 16px;font-size:13px;line-height:1.6;color:#1e293b">${briefBlurb}</p>`;

  if (drugs.length)
    overviewHtml += `<div style="margin-bottom:16px"><div style="font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.07em;margin-bottom:6px">💊 Pipeline</div><div>${drugs.map(drugPill).join(' ')}</div></div>`;

  if (deals.length) {
    overviewHtml += `<div style="margin-bottom:16px"><div style="font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.07em;margin-bottom:6px">📰 Recent Deals</div>${deals.slice(0,5).map(d => {
      const val = d.total_usd_m ? `<span style="font-weight:700;color:#c45b11;margin-left:8px">$${Math.round(d.total_usd_m)}M</span>` : '';
      const src = d.source_url ? `<a href="${d.source_url}" target="_blank" rel="noopener" style="color:#2e6fb0;font-size:11px;font-weight:700;text-decoration:none;margin-right:4px">↗</a>` : '';
      return `<div style="padding:5px 0;border-bottom:1px solid #f1f5f9;font-size:12px;overflow:hidden">${src}${d.headline||d.deal_type||'Deal'}${val}<span style="float:right;font-size:10px;color:#94a3b8">${d.deal_date||''}</span></div>`;
    }).join('')}</div>`;
  }

  if (trials.length) {
    const drugMap = {}; drugs.forEach(d => { drugMap[d.id] = d.display_name||d.name||'—'; });
    const trialRows = trials.map(t => `<tr style="border-bottom:1px solid #f1f5f9">
      <td style="font-size:11px;font-weight:700;color:#1e3a5f;padding:5px 8px">${drugMap[t.drug_id]||'—'}</td>
      <td style="font-size:11px;padding:5px 8px">${t.trial_name||t.id||'—'}</td>
      <td style="padding:5px 8px;text-align:center">${_phasePill(t.phase)}</td>
      <td style="font-size:11px;color:#64748b;padding:5px 8px">${t.indication||'—'}</td>
      <td style="font-size:11px;color:#64748b;padding:5px 8px">${t.primary_completion_date||'—'}</td>
      <td style="font-size:11px;padding:5px 8px"><span style="display:inline-block;padding:2px 6px;border-radius:5px;font-size:10px;font-weight:700;background:${t.status==='Active'||t.status==='Recruiting'?'#dcfce7':'#f1f5f9'};color:${t.status==='Active'||t.status==='Recruiting'?'#15803d':'#64748b'}">${t.status||'—'}</span></td>
    </tr>`).join('');
    overviewHtml += `<div><div style="font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.07em;margin-bottom:6px">🧪 Clinical Trials (${trials.length})</div>
      <div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse">
        <thead><tr style="background:#f8fafc;border-bottom:2px solid #e2e8f0">
          <th style="text-align:left;padding:5px 8px;font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.06em">Drug</th>
          <th style="text-align:left;padding:5px 8px;font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.06em">Trial</th>
          <th style="text-align:center;padding:5px 8px;font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.06em">Ph</th>
          <th style="text-align:left;padding:5px 8px;font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.06em">Indication</th>
          <th style="text-align:left;padding:5px 8px;font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.06em">PCD</th>
          <th style="text-align:left;padding:5px 8px;font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.06em">Status</th>
        </tr></thead><tbody>${trialRows}</tbody>
      </table></div></div>`;
  }

  if (!overviewHtml && !trackedAreas.length)
    return '<p style="color:#94a3b8;font-style:italic;padding:10px 0">No detailed profile available for this company yet.</p>';

  // ── Per-area drill-down panels ────────────────────────────────────────────
  const areaPanelHtml = trackedAreas.map(profile => {
    const areaId = profile.area_id;
    let html = '';
    if (profile.platform_summary)
      html += `<div style="margin-bottom:14px"><div style="font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.07em;margin-bottom:5px">Platform Summary</div><p style="margin:0;font-size:12px;line-height:1.6;color:#1e293b">${profile.platform_summary}</p></div>`;
    if (profile.bd_summary)
      html += `<div style="margin-bottom:14px;padding:12px 14px;background:#f0f6ff;border-radius:8px;border-left:3px solid #2e6fb0"><div style="font-size:10px;font-weight:700;color:#2e6fb0;text-transform:uppercase;letter-spacing:0.07em;margin-bottom:5px">🤝 BD Context</div><p style="margin:0;font-size:12px;line-height:1.6;color:#1e293b">${profile.bd_summary}</p></div>`;
    const areaCats = cats.filter(c => !c.area_id || c.area_id === areaId);
    if (areaCats.length)
      html += `<div><div style="font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.07em;margin-bottom:6px">📅 Upcoming Catalysts</div>${areaCats.map(c =>
        `<div class="catalyst-item"><span class="catalyst-timing">${c.catalyst_date||c.sort_date||''}</span><span style="font-size:12px">${c.label||''}</span></div>`
      ).join('')}</div>`;
    if (!html) html = `<p style="color:#94a3b8;font-style:italic;font-size:12px">Area-specific detail not yet available.</p>`;
    return `<div class="emodal-panel" data-area="${areaId}" style="display:none">${html}</div>`;
  }).join('');

  const overviewPanel = `<div class="emodal-panel" data-area="__overview__" style="display:block">${overviewHtml||'<p style="color:#94a3b8;font-style:italic;font-size:12px">No overview available yet.</p>'}</div>`;

  // Single-area: skip tabs, append BD context directly below overview
  if (!multiArea && trackedAreas.length === 1) {
    const p = trackedAreas[0];
    let direct = overviewHtml;
    if (p.bd_summary)
      direct += `<div style="margin-top:16px;padding:12px 14px;background:#f0f6ff;border-radius:8px;border-left:3px solid #2e6fb0"><div style="font-size:10px;font-weight:700;color:#2e6fb0;text-transform:uppercase;letter-spacing:0.07em;margin-bottom:5px">🤝 BD Context</div><p style="margin:0;font-size:12px;line-height:1.6;color:#1e293b">${p.bd_summary}</p></div>`;
    return direct || '<p style="color:#94a3b8;font-style:italic;padding:10px 0">No detailed profile available for this company yet.</p>';
  }

  return areaTabs + overviewPanel + areaPanelHtml;
}

/* ─── Drug modal  ─────────────────────────────────────────────────────────── */
/* ── trial_facts → legacy trial display shape (2026-06-07) ─────────────────
   The drug modal now reads `trial_facts` (CT.gov-derived) instead of legacy
   `trials`. trial_facts column gotchas: trial_title (not title),
   primary_completion_date (not completion_date), conditions/primary_endpoints
   are arrays. This mapper normalizes to the field names the renderer expects. */
function _mapTrialFactRow(r) {
  const _phaseLbl = (r.phase || '')
    .replace(/^EARLY_PHASE(\d)/i, 'Early Ph $1')
    .replace(/^PHASE(\d)$/i, 'Phase $1')
    .replace(/_/g, '/').replace(/PHASE(\d)/gi, 'Ph $1') || '';
  const _statusLbl = r.status ? r.status.charAt(0) + r.status.slice(1).toLowerCase().replace(/_/g, ' ') : '';
  return {
    id: r.id,
    nct_id: r.nct_id,
    trial_name: r.trial_title || r.nct_id || '',
    phase: _phaseLbl,
    status: _statusLbl,
    indication: Array.isArray(r.conditions) ? r.conditions.slice(0, 2).join(', ') : (r.conditions || ''),
    n_enrollment: r.enrollment,
    start_date: r.start_date || null,
    completion_date: r.primary_completion_date || null,
    why_stopped: r.why_stopped || null,
    primary_endpoint: Array.isArray(r.primary_endpoints) ? r.primary_endpoints.join('; ') : (r.primary_endpoints || ''),
    source_url: r.source_url || (r.nct_id ? `https://clinicaltrials.gov/study/${r.nct_id}` : null),
  };
}

async function openDrugEntityModal(drugId, drugName, evt) {
  if (evt) { evt.stopPropagation(); evt.preventDefault(); }
  const overlay  = document.getElementById('entity-modal-overlay');
  const titleEl  = document.getElementById('entity-modal-title');
  const subEl    = document.getElementById('entity-modal-sub');
  const bodyEl   = document.getElementById('entity-modal-body');
  const footerEl = document.getElementById('entity-modal-footer');
  const tagsEl   = document.getElementById('entity-modal-also-tags');
  if (!overlay) return;

  titleEl.textContent = drugName;
  subEl.textContent   = 'Drug Profile';
  bodyEl.innerHTML    = '<div style="padding:40px;text-align:center;color:#94a3b8;font-style:italic;font-size:13px">⟳ Loading…</div>';
  footerEl.style.display = 'none';
  tagsEl.innerHTML = '';
  overlay.classList.add('open');
  document.body.style.overflow = 'hidden';

  if (!_sb) {
    bodyEl.innerHTML = '<p style="padding:20px;color:#dc2626;font-size:13px">Database not available.</p>';
    return;
  }

  try {
    // Primary lookup by ID; if ID is a static placeholder (starts with "static-") skip it
    const isStaticId = !drugId || String(drugId).startsWith('static-');
    // C1 — primary fetch: drug_competitive_scores (migrated from drug_area_scores, Session 64)
    // 2026-06-07: trials source switched legacy `trials` → `trial_facts` (CT.gov-derived, fresher).
    // Rows are normalized to the legacy display shape via _mapTrialFactRow.
    const _TRIAL_FACT_COLS = 'id,nct_id,trial_title,phase,status,enrollment,conditions,primary_endpoints,start_date,primary_completion_date,why_stopped,source_url,lead_sponsor';
    const [drugRes, scoreRes0, trialRes0, molRes0, srcRes0, ifRes0] = await Promise.all([
      isStaticId ? Promise.resolve({ data: [] }) : _sb.from('drugs').select('*').eq('id', drugId).limit(1),
      isStaticId ? Promise.resolve({ data: [] }) : _sb.from('drug_competitive_scores').select('context_type,context_id,overlap,overlap_rationale,cls,confidence_level,source_url,vs_ailux').eq('drug_id', drugId),
      isStaticId ? Promise.resolve({ data: [] }) : _sb.from('trial_facts').select(_TRIAL_FACT_COLS).eq('drug_id', drugId).order('phase', {ascending:false}).limit(20),
      isStaticId ? Promise.resolve({ data: [] }) : _sb.from('molecule_intelligence').select('*').eq('drug_id', drugId).limit(1),
      isStaticId ? Promise.resolve({ data: [] }) : _sb.from('drug_sources').select('claim_type,claim_value,source_url,source_type,source_domain,content_confirms_claim,confidence').eq('drug_id', drugId),
      isStaticId ? Promise.resolve({ data: [] }) : _sb.from('intel_fact_entities').select('role,intel_facts(fact_type,claim,value_num,unit,area_id,source_url,page_ref,section,confidence)').eq('entity_id', drugId).limit(150),
    ]);
    const drugSources = srcRes0.data || [];
    const intelFacts = (ifRes0.data || []).map(r => r && r.intel_facts).filter(Boolean);

    let drug    = drugRes.data?.[0]  || null;
    // Build areas[] from drug_competitive_scores; expose context_id as area_id for downstream compat
    let areas   = (scoreRes0.data || []).map(s => ({
      area_id: s.context_id,
      context_type: s.context_type,
      overlap: s.overlap || null,
      overlap_rationale: s.overlap_rationale || null,
      confidence_level: s.confidence_level || null,
      source_url: s.source_url || null,
      vs_ailux: s.vs_ailux || null,
    }));

    // ── DUAL-READ COMPARISON HARNESS (remove after 30-day monitoring window) ───
    if (drug?.id && !isStaticId) {
      (async () => {
        try {
          const { data: legacyScores } = await _sb
            .from('drug_area_scores')
            .select('area_id,overlap,overlap_rationale,confidence_level,source_url')
            .eq('drug_id', drug.id);
          const legacyMap = {};
          (legacyScores || []).forEach(r => { legacyMap[r.area_id] = r; });
          const newMap = {};
          (scoreRes0.data || []).forEach(r => { newMap[r.context_id] = r; });
          const legacyKeys = new Set(Object.keys(legacyMap));
          const newKeys    = new Set(Object.keys(newMap));
          const matched    = [...legacyKeys].filter(k => newKeys.has(k));
          const oldOnly    = [...legacyKeys].filter(k => !newKeys.has(k));
          const newOnly    = [...newKeys].filter(k => !legacyKeys.has(k));
          const CONF_MAP   = {confirmed:'A', supported:'B', inferred:'inferred'};
          const fieldMismatches = [];
          for (const ctx of matched) {
            const l = legacyMap[ctx], n = newMap[ctx];
            const lConf = CONF_MAP[l.confidence_level] || l.confidence_level;
            if (l.overlap    !== n.overlap)           fieldMismatches.push({ctx, field:'overlap', legacy:l.overlap, new_:n.overlap});
            if (lConf        !== n.confidence_level)  fieldMismatches.push({ctx, field:'confidence_level', legacy:l.confidence_level, mapped:lConf, new_:n.confidence_level});
            if (l.source_url !== n.source_url)        fieldMismatches.push({ctx, field:'source_url', legacy:l.source_url, new_:n.source_url});
          }
          const report = { drug_id:drug.id, drug_name:drug.name, ts:new Date().toISOString(),
            old_count:legacyScores?.length||0, new_count:scoreRes0.data?.length||0,
            matched:matched.length, old_only:oldOnly, new_only:newOnly, field_mismatches:fieldMismatches };
          window.__MERIDIAN_COMPETITIVE_SCORE_COMPARE__ = window.__MERIDIAN_COMPETITIVE_SCORE_COMPARE__ || [];
          window.__MERIDIAN_COMPETITIVE_SCORE_COMPARE__.push(report);
          if (oldOnly.filter(k=>k!=='ibd').length || fieldMismatches.length)
            console.warn('[MERIDIAN_CMP] Discrepancy for', drug.name, report);
          else
            console.debug('[MERIDIAN_CMP] OK:', drug.name, `old=${report.old_count} new=${report.new_count} matched=${report.matched} ibd_expansion=${oldOnly.includes('ibd')}`);
        } catch(e) { console.warn('[MERIDIAN_CMP] Harness error:', e); }
      })();
    }
    // ── END DUAL-READ HARNESS ─────────────────────────────────────────────────

    let trials  = (trialRes0.data || []).map(_mapTrialFactRow);
    let molData = molRes0.data?.[0]  || null;

    // If no drug found by ID (static placeholder or stale ID), fall back to name search
    if (!drug && drugName) {
      const clean = drugName.trim();
      const { data: r1 } = await _sb.from('drugs').select('*').ilike('name', clean).limit(1);
      drug = r1?.[0] || null;
      if (!drug) {
        const { data: r2 } = await _sb.from('drugs').select('*').ilike('display_name', clean).limit(1);
        drug = r2?.[0] || null;
      }
      if (drug) {
        // C2 — Re-fetch areas + trials + molecule intel using resolved DB id
        // Reads drug_competitive_scores (migrated from drug_area_scores, Session 64)
        const rid = drug.id;
        const [sr, tr, mr] = await Promise.all([
          _sb.from('drug_competitive_scores').select('context_type,context_id,overlap,overlap_rationale,cls,confidence_level,source_url,vs_ailux').eq('drug_id', rid),
          _sb.from('trial_facts').select(_TRIAL_FACT_COLS).eq('drug_id', rid).order('phase', {ascending:false}).limit(20),
          _sb.from('molecule_intelligence').select('*').eq('drug_id', rid).limit(1),
        ]);
        areas = (sr.data || []).map(s => ({
          area_id: s.context_id,
          context_type: s.context_type,
          overlap: s.overlap || null,
          overlap_rationale: s.overlap_rationale || null,
          confidence_level: s.confidence_level || null,
          source_url: s.source_url || null,
          vs_ailux: s.vs_ailux || null,
        }));
        trials  = (tr.data || []).map(_mapTrialFactRow);
        molData = mr.data?.[0] || null;
      }
    }

    // Fetch deals for this drug
    let drugDeals = [];
    try {
      const dId = drug?.id;
      const dNameQ = (drug?.name || drugName || '').split(/\s+/).slice(0,3).join(' ');
      const dealQ = dId
        ? _sb.from('deals').select('*').or(`drug_id.eq.${dId},drug_name.ilike.*${encodeURIComponent(dNameQ)}*`).order('deal_date',{ascending:false}).limit(10)
        : _sb.from('deals').select('*').ilike('drug_name', `*${dNameQ}*`).order('deal_date',{ascending:false}).limit(10);
      const { data: dealRows } = await dealQ;
      drugDeals = (dealRows||[]).filter(d => d.deal_type && d.deal_type !== 'news');
    } catch(_) {}

    // Fetch news articles linked to this drug (Fix 3A — knowledge graph integration)
    let drugNews = [];
    try {
      const _dNews90dAgo = new Date(Date.now() - 90*24*60*60*1000).toISOString().slice(0,10);
      const { data: newsRows } = await _sb.from('news_articles')
        .select('id,headline,source_name,published_at,article_url,relevance_score,meridian_summary,why_it_matters')
        .contains('matched_drug_ids', [drug?.id || drugId])
        .neq('source_validation_status', 'invalid')
        .gte('published_at', _dNews90dAgo)
        .order('relevance_score', { ascending: false })
        .limit(5);
      drugNews = newsRows || [];
    } catch(_) {}

    // Fetch upcoming catalysts linked to this drug (Fix 3B — knowledge graph integration)
    let drugCatalysts = [];
    try {
      const _todayStr = new Date().toISOString().slice(0,10);
      const { data: catRows } = await _sb.from('catalysts')
        .select('id,catalyst_text:notes,sort_date,catalyst_type,resolved,source_url')
        .eq('drug_id', drug?.id || drugId)
        .eq('resolved', false)
        .gte('sort_date', _todayStr)
        .order('sort_date', { ascending: true })
        .limit(5);
      drugCatalysts = catRows || [];
    } catch(_) {}

    // Fetch company name
    let companyName = '';
    if (drug?.company_id) {
      const { data: coRows } = await _sb.from('companies').select('name,ticker').eq('id', drug.company_id).limit(1);
      if (coRows?.[0]) companyName = coRows[0].name + (coRows[0].ticker ? ` (${coRows[0].ticker})` : '');
    }

    // Fetch current owner if different from originator (acquisition/licensing chain)
    let ownerData = null; // { ownerName, ownerCompanyId, originatorName, originatorCompanyId }
    if (drug?.current_owner_company_id && drug.current_owner_company_id !== drug.company_id) {
      try {
        const { data: ownerRows } = await _sb.from('companies').select('id,name').eq('id', drug.current_owner_company_id).limit(1);
        if (ownerRows?.[0]) {
          ownerData = {
            ownerName:         ownerRows[0].name,
            ownerCompanyId:    drug.current_owner_company_id,
            originatorName:    companyName,
            originatorCompanyId: drug.company_id,
          };
        }
      } catch(_) {}
    }

    subEl.textContent = companyName || 'Drug Profile';

    // Fetch asset transfer history (multi-hop provenance chain) — Session 69
    let transferChain = [];
    try {
      const _tcDrugId = drug?.id || drugId;
      if (_tcDrugId && !String(_tcDrugId).startsWith('static-')) {
        const { data: tcRows } = await _sb.from('asset_transfer_history')
          .select('sequence_order,from_entity_name,from_entity_id,to_entity_name,to_entity_id,transfer_type,geographic_scope,transfer_date,deal_value_upfront_usd,deal_value_milestones_usd,deal_value_notes,verified,source_url')
          .eq('drug_id', _tcDrugId)
          .order('sequence_order', { ascending: true });
        transferChain = tcRows || [];
      }
    } catch(_) {}

    // Fetch failure cascade risk for this drug (Fix B — Session 68)
    let cascadeRisk = null;
    try {
      const _crId = drug?.id || drugId;
      if (_crId && !String(_crId).startsWith('static-')) {
        const { data: crRows } = await _sb.from('failure_cascade_risk')
          .select('cascade_risk_level,mechanism_target,mechanism_indication,mechanism_validity,cascade_risk_rationale')
          .eq('drug_id', _crId).limit(1);
        cascadeRisk = crRows?.[0] || null;
      }
    } catch(_) {}

    // ── Geographic approvals for this drug (Connection 6) ─────────────────────
    let geoApprovals = [];
    try {
      const _gaId = drug?.id || drugId;
      if (_gaId && !String(_gaId).startsWith('static-')) {
        const { data: gaRows } = await _sb.from('geographic_approvals')
          .select('geography, approval_date, approval_status:approval_type, brand_name, regulator, indication')
          .eq('drug_id', _gaId)
          .order('approval_date', { ascending: false });
        geoApprovals = gaRows || [];
      }
    } catch(_) {}

    // ── New data layers (2026-06-07) — payer pricing, IP, regulatory designations,
    //    safety/labels, congress presence, PK, non-responder biology ─────────────
    //    All fetched in one parallel batch; each section renders only when non-empty.
    let extData = { payer:[], patents:[], patentFamilies:[], designations:[], safety:[], labels:[], abstracts:[], pk:[], nonResponders:[], exclusivity:[], faers:[] };
    try {
      const _nlId = drug?.id || drugId;
      if (_nlId && !String(_nlId).startsWith('static-')) {
        const [ppR, dpR, pfR, rdR, dsR, dlR, caR, pkR, nrR, exR, faR] = await Promise.all([
          _sb.from('payer_pricing').select('source,metric,value_numeric,unit,year,source_url').eq('drug_id', _nlId).order('year', {ascending:false}).limit(60),
          _sb.from('drug_patents').select('patent_no,patent_expire_date,drug_substance_flag,patent_use_code,source_url').eq('drug_id', _nlId).order('patent_expire_date', {ascending:true}).limit(40),
          _sb.from('patent_families').select('family_doc_id,jurisdiction').eq('drug_id', _nlId).limit(200),
          _sb.from('regulatory_designations').select('designation_type,indication,granted_date,granting_authority').eq('drug_id', _nlId).order('granted_date', {ascending:false}).limit(20),
          _sb.from('drug_safety').select('warning_type,description,source_url').eq('drug_id', _nlId).limit(10),
          // drug_labels gotcha: no `spl_url` column — link target is source_url (DailyMed) with set_url fallback
          _sb.from('drug_labels').select('label_title,marketing_status,set_url,source_url').eq('drug_id', _nlId).limit(2),
          _sb.from('conference_abstracts').select('title,conference,conference_year,doi,source_url').eq('drug_id', _nlId).order('conference_year', {ascending:false}).limit(3),
          _sb.from('drug_pk_parameters').select('dose_mg,dose_route,half_life_hours,steady_state_weeks,immunogenicity_ada_pct,verified,source_url').eq('drug_id', _nlId).limit(3),
          _sb.from('non_responder_profiles').select('indication_id,mechanism_class,non_responder_rate_pct,line_of_therapy,escape_mechanism_text').eq('drug_id', _nlId).limit(4),
          _sb.from('drug_exclusivity').select('exclusivity_type,exclusivity_date,exclusivity_code,is_biologic,source_url').eq('drug_id', _nlId).order('exclusivity_date', {ascending:false}).limit(8),
          _sb.from('fda_adverse_events').select('reaction,report_count,source_url').eq('drug_id', _nlId).order('report_count', {ascending:false}).limit(5),
        ]);
        extData = {
          payer: ppR.data || [], patents: dpR.data || [], patentFamilies: pfR.data || [],
          designations: rdR.data || [], safety: dsR.data || [], labels: dlR.data || [],
          abstracts: caR.data || [], pk: pkR.data || [], nonResponders: nrR.data || [],
          exclusivity: exR.data || [], faers: faR.data || [],
        };
      }
    } catch(_nlErr) { console.warn('[drugModal-newlayers]', _nlErr?.message); }

    // ── Phase 5 Candidate 3 — Drug modal normalized source ─────────────────────
    // When FEATURE_FLAGS.useNormalizedDrugModal=true: fetch drug_targets,
    // drug_indications, and trial_indications (via trial IDs) for display in the
    // Targets and Indications cells of the modal overview. Non-blocking — errors
    // fall back to normData=null (no normalized cells shown).
    let normData = null;
    if (FEATURE_FLAGS.useNormalizedDrugModal) {
      const _normDrugId = drug?.id || drugId;
      if (_normDrugId && !String(_normDrugId).startsWith('static-')) {
        try {
          const [_dtR, _diR] = await Promise.all([
            _sb.from('drug_targets').select('target_id,confidence_score,review_status').eq('drug_id', _normDrugId),
            _sb.from('drug_indications').select('indication_id,confidence_score,development_stage,review_status').eq('drug_id', _normDrugId),
          ]);
          const _nTargets = _dtR.data || [];
          const _nInds    = _diR.data || [];
          let   _nTrialInds = [];
          // DEPRECATED 2026-06-07 — trial_indications is keyed by legacy trials.id;
          // the modal now reads trial_facts (different UUIDs), so this lookup can no
          // longer match. trial_facts.conditions now supplies per-trial indication text.
          // if (trials.length) {
          //   const _tIds = trials.map(t => t.id).slice(0, 30);
          //   const { data: _tiData } = await _sb.from('trial_indications')
          //     .select('trial_id,indication_id,confidence_score')
          //     .in('trial_id', _tIds);
          //   _nTrialInds = _tiData || [];
          // }
          normData = { targets: _nTargets, indications: _nInds, trialInds: _nTrialInds };
        } catch(_normErr) {
          console.warn('[drugModal-norm] normalized fetch error:', _normErr?.message);
        }
      }
    }

    // Store drug context for lazy-loading Intelligence tab
    window._cemCurrentDrugId        = drug?.id || drugId;
    window._cemCurrentDrugName      = drug?.display_name || drug?.name || drugName || '';
    window._cemCurrentDrugCompanyId = drug?.company_id || null;

    bodyEl.classList.add('dossier-mode');
    bodyEl.innerHTML  = _cemDrugBody(drug, areas, trials, molData, companyName, drugDeals, normData, drugNews, drugCatalysts, ownerData, cascadeRisk, transferChain, geoApprovals, drugSources, extData, intelFacts);

    // ── Meridian Narrative (prose read layer) — non-blocking load into placeholder
    if (drug?.id) _loadMeridianNarrative(drug.id);

    // ── Lazy-load Clinical Intelligence (benchmarks, PK, biomarkers) ─────────────
    // Non-blocking: fetches after the modal renders, injects into Drug Profile tab
    if (drug?.id && !isStaticId && _sb) {
      (async () => {
        try {
          // DEPRECATED 2026-06-07 — drug_pk_parameters fetch + "PK Profile" block removed
          // from this lazy injector: PK now renders statically in the Development section
          // of the canonical Drug Card IA (built in _cemDrugBody from extData.pk).
          const [cbRes, bmRes] = await Promise.all([
            _sb.from('drug_clinical_benchmarks').select('*').eq('drug_id', drug.id).order('indication_id').limit(20),
            _sb.from('drug_biomarkers').select('*').eq('drug_id', drug.id).limit(15),
          ]);
          const cb = cbRes?.data || [];
          const bm = bmRes?.data || [];
          if (!cb.length && !bm.length) return;

          let clinHtml = '<div style="border-top:1px solid #f1f5f9;margin-top:10px;padding-top:12px">';
          clinHtml += '<div style="font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#6366f1;margin-bottom:8px">📊 Clinical Intelligence</div>';

          // Efficacy Benchmarks
          if (cb.length) {
            clinHtml += '<div style="margin-bottom:10px"><div style="font-size:9px;font-weight:700;text-transform:uppercase;color:#94a3b8;letter-spacing:0.05em;margin-bottom:5px">Efficacy Benchmarks</div>';
            const byInd = {};
            cb.forEach(r => { const k = r.indication_id||'?'; (byInd[k]=byInd[k]||[]).push(r); });
            Object.entries(byInd).forEach(([ind, rows]) => {
              clinHtml += `<div style="font-size:10px;font-weight:700;color:#475569;margin:4px 0 3px;text-transform:uppercase;letter-spacing:0.03em">${ind}</div>`;
              rows.forEach(r => {
                const rate = r.rate_pct != null ? `${r.rate_pct}%` : '—';
                const comp = r.comparator_rate_pct != null ? ` vs ${r.comparator_rate_pct}% PBO` : '';
                const tp   = r.timepoint_weeks ? ` wk${r.timepoint_weeks}` : '';
                const trial = r.trial_name ? ` · ${r.trial_name.substring(0,40)}` : '';
                const dim  = (r.benchmark_type||'').replace(/_/g,' ');
                clinHtml += `<div style="padding:3px 8px;background:#f0fdf4;border-left:2px solid #4ade80;margin-bottom:3px;border-radius:0 4px 4px 0;font-size:11px">
                  <span style="font-weight:700;color:#166534">${rate}${comp}</span><span style="color:#64748b"> ${dim}${tp}${trial}</span></div>`;
              });
            });
            clinHtml += '</div>';
          }

          // Biomarkers
          if (bm.length) {
            clinHtml += '<div><div style="font-size:9px;font-weight:700;text-transform:uppercase;color:#94a3b8;letter-spacing:0.05em;margin-bottom:5px">Patient Biomarkers</div>';
            bm.forEach(b => {
              const iconMap = {non_responder_marker:'⚠️',eligibility:'✓',predictive:'◎',pharmacodynamic:'📉'};
              const icon = iconMap[b.biomarker_class] || '◦';
              const dir  = b.direction_for_response ? `<span style="color:#64748b;font-size:10px;margin-left:4px">${b.direction_for_response}</span>` : '';
              const note = b.notes ? b.notes.substring(0,100) : '';
              clinHtml += `<div style="padding:4px 8px;background:#fafaf5;border:1px solid #e2e8f0;border-radius:4px;margin-bottom:3px;font-size:11px">
                <span style="margin-right:5px">${icon}</span><span style="font-weight:600;color:#374151">${b.biomarker_name}</span>${dir}
                ${note ? `<div style="font-size:10px;color:#94a3b8;margin-top:2px">${note}</div>` : ''}</div>`;
            });
            clinHtml += '</div>';
          }

          clinHtml += '</div>';

          // Inject into the Development panel (canonical Drug Card IA, 2026-06-07)
          const profilePanel = document.getElementById('cem-dtab-profile');
          if (profilePanel) profilePanel.insertAdjacentHTML('beforeend', clinHtml);
        } catch(_clinErr) {
          console.warn('[drugModal-clinical]', _clinErr?.message);
        }
      })();
    }

    // ── Lazy-load API-sourced data: chemistry, identifiers, sourced efficacy, approvals ──
    // (2026-06-10) Surfaces v149–v151 integrations into the Drug Profile tab:
    // molecule_properties (ChEMBL), compound_identifiers (PubChem/RxNorm/UNII),
    // drug_efficacy_endpoints (source-required), fda_approvals (drugsfda). Isolated +
    // fully guarded: returns silently if no data, never touches existing rendering.
    if (drug?.id && !isStaticId && _sb) {
      (async () => {
        try {
          const [mpRes, ciRes, eeRes, faRes] = await Promise.all([
            _sb.from('molecule_properties').select('molecule_type,max_phase,first_approval,black_box_warning,oral,mw_freebase,usan_stem,chembl_id').eq('drug_id', drug.id).limit(1),
            _sb.from('compound_identifiers').select('pubchem_cid,rxcui,unii,inchikey,molecular_formula').eq('drug_id', drug.id).limit(1),
            _sb.from('drug_efficacy_endpoints').select('indication_id,arm_label,timepoint_week,drug_pct,placebo_pct,placebo_adjusted_delta_pp,primary_endpoint_met,trial_name,source_url').eq('drug_id', drug.id).order('placebo_adjusted_delta_pp',{ascending:false}).limit(12),
            _sb.from('fda_approvals').select('brand_name,application_number,sponsor,marketing_status,approval_date').eq('drug_id', drug.id).order('approval_date').limit(6),
          ]);
          const mp = mpRes?.data?.[0]; const ci = ciRes?.data?.[0];
          const ee = eeRes?.data || []; const fa = faRes?.data || [];
          if (!mp && !ci && !ee.length && !fa.length) return;
          let h = '<div style="border-top:1px solid #f1f5f9;margin-top:10px;padding-top:12px">';
          h += '<div style="font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#0d9488;margin-bottom:8px">🧪 Chemistry, Identifiers & Sourced Efficacy</div>';
          if (mp || ci) {
            const chips = [];
            if (mp?.molecule_type) chips.push(['Type', mp.molecule_type]);
            if (mp?.first_approval) chips.push(['First approval', mp.first_approval]);
            if (mp?.max_phase) chips.push(['Max phase', mp.max_phase]);
            if (mp?.usan_stem) chips.push(['Class stem', mp.usan_stem]);
            if (mp?.mw_freebase) chips.push(['MW', mp.mw_freebase]);
            if (ci?.molecular_formula) chips.push(['Formula', ci.molecular_formula]);
            if (ci?.pubchem_cid) chips.push(['PubChem', ci.pubchem_cid]);
            if (ci?.rxcui) chips.push(['RxCUI', ci.rxcui]);
            if (ci?.unii) chips.push(['UNII', ci.unii]);
            if (mp?.chembl_id) chips.push(['ChEMBL', mp.chembl_id]);
            if (chips.length) {
              h += '<div style="display:flex;flex-wrap:wrap;gap:5px;margin-bottom:10px">' + chips.map(function(kv){
                return '<span style="font-size:10px;background:#f0fdfa;border:1px solid #99f6e4;border-radius:4px;padding:2px 7px"><span style="color:#64748b">'+kv[0]+':</span> <span style="font-weight:700;color:#0f766e">'+escHtml(String(kv[1]))+'</span></span>';
              }).join('') + '</div>';
            }
          }
          if (ee.length) {
            h += '<div style="margin-bottom:10px"><div style="font-size:9px;font-weight:700;text-transform:uppercase;color:#94a3b8;letter-spacing:0.05em;margin-bottom:5px">Sourced Efficacy Endpoints</div>';
            ee.forEach(function(r){
              const delta = r.placebo_adjusted_delta_pp != null ? '+'+r.placebo_adjusted_delta_pp+'pp' : '';
              const vs = (r.drug_pct!=null && r.placebo_pct!=null) ? ' ('+r.drug_pct+'% vs '+r.placebo_pct+'%)' : (r.drug_pct!=null?' ('+r.drug_pct+'%)':'');
              const wk = r.timepoint_week ? ' wk'+r.timepoint_week : '';
              const met = r.primary_endpoint_met===false ? ' <span style="color:#dc2626;font-weight:700">primary NOT met</span>' : '';
              const tr = r.trial_name ? ' · '+escHtml(r.trial_name) : '';
              h += '<div style="padding:3px 8px;background:#ecfeff;border-left:2px solid #06b6d4;margin-bottom:3px;border-radius:0 4px 4px 0;font-size:11px"><span style="font-weight:700;color:#0e7490">'+String(r.indication_id||'').toUpperCase()+' '+(r.arm_label||'')+' '+delta+'</span><span style="color:#64748b">'+vs+wk+tr+'</span>'+met+(r.source_url?' <a href="'+r.source_url+'" target="_blank" style="color:#0891b2;font-size:9px">[src]</a>':'')+'</div>';
            });
            h += '</div>';
          }
          if (fa.length) {
            h += '<div><div style="font-size:9px;font-weight:700;text-transform:uppercase;color:#94a3b8;letter-spacing:0.05em;margin-bottom:5px">FDA Approvals (drugsfda)</div>';
            fa.forEach(function(a){
              h += '<div style="padding:3px 8px;background:#fefce8;border-left:2px solid #eab308;margin-bottom:3px;border-radius:0 4px 4px 0;font-size:11px"><span style="font-weight:700;color:#854d0e">'+escHtml(a.brand_name||a.application_number||'')+'</span><span style="color:#64748b"> '+(a.approval_date||'')+' · '+escHtml(a.sponsor||'')+' · '+escHtml(a.marketing_status||'')+'</span></div>';
            });
            h += '</div>';
          }
          h += '</div>';
          const panel = document.getElementById('cem-dtab-profile');
          if (panel) panel.insertAdjacentHTML('beforeend', h);
        } catch(_apiErr) { console.warn('[drugModal-apiData]', _apiErr && _apiErr.message); }
      })();
    }

    // ── Lazy-load Trial Results & Target Pharmacology (v150–v153 integrations) ──
    // trial_outcome_measures via v_trial_remission_rates + iuphar_interactions, both
    // keyed by drug_id. Isolated + guarded; returns silently if no data.
    if (drug?.id && !isStaticId && _sb) {
      (async () => {
        try {
          const [rrRes, iuRes] = await Promise.all([
            _sb.from('v_trial_remission_rates').select('arm_label,remission_rate_pct,remitters_n,denominator_n,measure_title,nct_id').eq('drug_id', drug.id).not('remission_rate_pct','is',null).order('remission_rate_pct',{ascending:false}).limit(8),
            _sb.from('iuphar_interactions').select('target_name,action_type,affinity,affinity_parameter,pmid').eq('drug_id', drug.id).not('affinity','is',null).order('affinity',{ascending:false}).limit(8),
          ]);
          const rr = rrRes?.data || []; const iu = iuRes?.data || [];
          if (!rr.length && !iu.length) return;
          let h = '<div style="border-top:1px solid #f1f5f9;margin-top:10px;padding-top:12px">';
          h += '<div style="font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#7c3aed;margin-bottom:8px">📈 Trial Results & Target Pharmacology</div>';
          if (rr.length) {
            h += '<div style="margin-bottom:10px"><div style="font-size:9px;font-weight:700;text-transform:uppercase;color:#94a3b8;letter-spacing:0.05em;margin-bottom:5px">Remission Rates (CT.gov posted results)</div>';
            rr.forEach(function(r){
              const den = r.denominator_n ? '/'+r.denominator_n : '';
              const mt = r.measure_title ? ' · '+escHtml(String(r.measure_title).substring(0,60)) : '';
              h += '<div style="padding:3px 8px;background:#f5f3ff;border-left:2px solid #a78bfa;margin-bottom:3px;border-radius:0 4px 4px 0;font-size:11px"><span style="font-weight:700;color:#6d28d9">'+r.remission_rate_pct+'%</span><span style="color:#64748b"> '+escHtml(r.arm_label||'')+' ('+(r.remitters_n||'?')+den+')'+mt+'</span></div>';
            });
            h += '</div>';
          }
          if (iu.length) {
            h += '<div><div style="font-size:9px;font-weight:700;text-transform:uppercase;color:#94a3b8;letter-spacing:0.05em;margin-bottom:5px">Target Affinities (IUPHAR/GtoPdb)</div>';
            iu.forEach(function(r){
              const aff = r.affinity!=null ? r.affinity_parameter+' '+r.affinity : '';
              const pm = r.pmid ? ' · PMID '+r.pmid : '';
              h += '<div style="padding:3px 8px;background:#eef2ff;border-left:2px solid #818cf8;margin-bottom:3px;border-radius:0 4px 4px 0;font-size:11px"><span style="font-weight:700;color:#4338ca">'+escHtml(r.target_name||'')+'</span><span style="color:#64748b"> '+escHtml(r.action_type||'')+' · '+aff+pm+'</span></div>';
            });
            h += '</div>';
          }
          h += '</div>';
          const panel = document.getElementById('cem-dtab-profile');
          if (panel) panel.insertAdjacentHTML('beforeend', h);
        } catch(_trErr) { console.warn('[drugModal-trialPharm]', _trErr && _trErr.message); }
      })();
    }

    // ── Lazy-load Target Biology (v149–v152): genetic validation, protein, safety ──
    // target_disease_associations / target_proteins / target_safety are target-keyed;
    // map the drug's target tokens to candidate symbols (incl. HGNC synonyms) and match.
    if (drug?.id && !isStaticId && _sb && drug.target) {
      (async () => {
        try {
          const syn = {'TL1A':'TNFSF15','IL-23P19':'IL23A','IL23P19':'IL23A','FCRN':'FCGRT','IL-4RA':'IL4R','IL4RA':'IL4R','CD40L':'CD40LG','IGE':'IGHE','TSLPR':'CRLF2'};
          const cands = new Set();
          String(drug.target).split(/[×x\/+,()]/).map(s=>s.trim()).filter(Boolean).forEach(function(t){
            const u=t.toUpperCase(); cands.add(t); cands.add(u); if(syn[u]) cands.add(syn[u]);
          });
          const arr=[...cands]; if(!arr.length) return;
          const [taRes, tpRes, tsRes] = await Promise.all([
            _sb.from('target_disease_associations').select('target_symbol,disease_label,overall_score').in('target_symbol',arr).order('overall_score',{ascending:false}).limit(8),
            _sb.from('target_proteins').select('target_symbol,protein_name,function_text').in('target_symbol',arr).limit(2),
            _sb.from('target_safety').select('target_symbol,event').in('target_symbol',arr).limit(8),
          ]);
          const ta=taRes?.data||[]; const tp=tpRes?.data||[]; const ts=tsRes?.data||[];
          if(!ta.length && !tp.length && !ts.length) return;
          let h='<div style="border-top:1px solid #f1f5f9;margin-top:10px;padding-top:12px">';
          h+='<div style="font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#0369a1;margin-bottom:8px">🧬 Target Biology</div>';
          if(tp.length){
            tp.forEach(function(p){
              if(!p.function_text) return;
              h+='<div style="margin-bottom:8px"><div style="font-size:9px;font-weight:700;text-transform:uppercase;color:#94a3b8;letter-spacing:0.05em;margin-bottom:3px">'+escHtml(p.target_symbol||'')+' — function (UniProt)</div><div style="font-size:11px;color:#374151;line-height:1.5;background:#f0f9ff;border-radius:4px;padding:6px 8px">'+escHtml(String(p.function_text).substring(0,360))+(p.function_text.length>360?'…':'')+'</div></div>';
            });
          }
          if(ta.length){
            h+='<div style="margin-bottom:8px"><div style="font-size:9px;font-weight:700;text-transform:uppercase;color:#94a3b8;letter-spacing:0.05em;margin-bottom:5px">Genetic / Disease Association (Open Targets)</div>';
            ta.forEach(function(r){
              const sc=r.overall_score!=null?Number(r.overall_score).toFixed(2):'';
              h+='<div style="padding:3px 8px;background:#ecfdf5;border-left:2px solid #34d399;margin-bottom:3px;border-radius:0 4px 4px 0;font-size:11px"><span style="font-weight:700;color:#047857">'+escHtml(r.disease_label||'')+'</span><span style="color:#64748b"> '+sc+' · '+escHtml(r.target_symbol||'')+'</span></div>';
            });
            h+='</div>';
          }
          if(ts.length){
            h+='<div><div style="font-size:9px;font-weight:700;text-transform:uppercase;color:#94a3b8;letter-spacing:0.05em;margin-bottom:5px">Safety Liabilities (Open Targets)</div><div style="font-size:11px;color:#374151">'+ts.map(function(s){return escHtml(s.event||'');}).filter(Boolean).join(' · ')+'</div></div>';
          }
          h+='</div>';
          const panel=document.getElementById('cem-dtab-profile');
          if(panel) panel.insertAdjacentHTML('beforeend', h);
        } catch(_tbErr){ console.warn('[drugModal-targetBio]', _tbErr && _tbErr.message); }
      })();
    }

    // ── Lazy-load Payer TPP Intelligence ──────────────────────────────────────
    // Injects payer TPP criteria into the Business panel (canonical Drug Card IA).
    // DEPRECATED 2026-06-07 — non_responder_profiles fetch + render removed from this
    // injector: non-responder biology now renders statically in the Intelligence
    // section (built in _cemDrugBody from extData.nonResponders).
    if (drug?.id && !isStaticId && _sb) {
      (async () => {
        try {
          // Get indication IDs for this drug from drug_indications
          const { data: drugInds } = await _sb.from('drug_indications')
            .select('indication_id').eq('drug_id', drug.id).limit(10);
          const indIds = (drugInds||[]).map(r => r.indication_id).filter(Boolean);
          if (!indIds.length) return;

          const { data: tppRows } = await _sb.from('payer_tpp_criteria').select('*').in('indication_id', indIds).limit(15);
          const tpp = tppRows || [];
          if (!tpp.length) return;

          let payerHtml = '<div style="border-top:1px solid #f1f5f9;margin-top:10px;padding-top:12px">';
          payerHtml += '<div style="font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#0891b2;margin-bottom:8px">💊 Payer & Access Intelligence</div>';

          // Payer TPP
          if (tpp.length) {
            payerHtml += '<div style="margin-bottom:10px"><div style="font-size:9px;font-weight:700;text-transform:uppercase;color:#94a3b8;letter-spacing:0.05em;margin-bottom:5px">Target Product Profile Benchmarks</div>';
            const byInd = {};
            tpp.forEach(r => { const k = r.indication_id||'?'; (byInd[k]=byInd[k]||[]).push(r); });
            Object.entries(byInd).forEach(([ind, rows]) => {
              payerHtml += `<div style="font-size:10px;font-weight:700;color:#475569;margin:4px 0 3px;text-transform:uppercase;letter-spacing:0.03em">${ind}</div>`;
              rows.slice(0,3).forEach(r => {
                const dim = (r.tpp_dimension||'').replace(/_/g,' ');
                const pref = r.preferred_profile ? r.preferred_profile.substring(0,100) : '';
                const min  = r.minimum_acceptable ? r.minimum_acceptable.substring(0,80) : '';
                payerHtml += `<div style="padding:5px 8px;background:#f0f9ff;border-left:2px solid #38bdf8;margin-bottom:3px;border-radius:0 4px 4px 0;font-size:11px">
                  <div style="font-weight:700;color:#0369a1">${dim}</div>
                  ${pref ? `<div style="color:#374151;margin-top:2px">✓ Preferred: ${pref}</div>` : ''}
                  ${min  ? `<div style="color:#64748b;font-size:10px">Min: ${min}</div>` : ''}
                </div>`;
              });
            });
            payerHtml += '</div>';
          }

          // DEPRECATED 2026-06-07 — Non-Responder Profiles block removed (see note at top
          // of this injector): now rendered statically in the Intelligence section.

          payerHtml += '</div>';

          // Inject into the Business panel (canonical Drug Card IA, 2026-06-07)
          const businessPanel = document.getElementById('cem-dtab-molecule');
          if (businessPanel) businessPanel.insertAdjacentHTML('beforeend', payerHtml);
        } catch(_payerErr) {
          console.warn('[drugModal-payer]', _payerErr?.message);
        }
      })();
    }

    // Footer: disease area tabs this drug appears in
    if (areas.length) {
      const areaToTabs = {};
      Object.entries(TAB_AREA_MAP).forEach(([t, as]) => as.forEach(a => { (areaToTabs[a] = areaToTabs[a] || []).push(t); }));
      const tabIds = [...new Set(areas.flatMap(a => areaToTabs[a.area_id] || []))];
      if (tabIds.length) {
        tagsEl.innerHTML = tabIds.map(t => {
          const label = TAB_META[t]?.badge || TAB_META[t]?.name || t;
          return `<span class="entity-also-tag ${_TAB_CLS[t]||'ct'}" onclick="closeEntityModal();navTo('${t}')">${label}</span>`;
        }).join('');
        footerEl.style.display = 'flex';
      }
    }
    // Phase 4B Path C — drug entity modal dual-read (non-blocking, parallel only)
    _runPhase4CModalDualRead(drug?.id || drugId, areas);
  } catch(e) {
    console.warn('[drugModal]', e);
    bodyEl.innerHTML = `<div style="padding:20px;color:#dc2626;font-size:13px">Failed to load: ${e.message}</div>`;
  }
}

// ── Phase 4B Path C — Drug Entity Modal dual-read ─────────────────────────────
// Fires after openDrugEntityModal renders. Does NOT change visible output.
// Reads drug_targets + drug_indications + trial_indications in parallel.
// Compares against legacy drug_areas membership fetched by the modal.
// Writes comparison record to window.__MERIDIAN_PHASE4_COMPARE__.
//
// Area → normalized path mapping (mirrors LEGACY_VIEW_TYPES in harness):
//   target_views:          tl1a→tl1a, fcrn→fcrn, igf1r→igf1r, tslp→tslp, il4ra→il4ra
//   indication_views:      ted→ted
//   indication_group_views: ibd→[uc,cd], atopy→[ad], respiratory→[asthma,copd], autoimmune→[ra,sle]
//
async function _runPhase4CModalDualRead(resolvedDrugId, legacyAreas) {
  if (!resolvedDrugId || !_sb) return;
  // Area → expected normalized relationships
  const AREA_TARGET_MAP = {
    tl1a: 'tl1a', fcrn: 'fcrn', igf1r: 'igf1r', tslp: 'tslp', il4ra: 'il4ra',
  };
  const AREA_IND_MAP = {
    ibd:         ['uc', 'cd'],
    ted:         ['ted'],
    atopy:       ['ad'],
    respiratory: ['asthma', 'copd', 'crswnp'],
    autoimmune:  ['ra', 'sle'],
  };

  try {
    // Parallel normalized reads — independent of modal rendering
    const [dtRes, diRes, trialRes] = await Promise.all([
      _sb.from('drug_targets').select('target_id,confidence_score,review_status').eq('drug_id', resolvedDrugId),
      _sb.from('drug_indications').select('indication_id,confidence_score,development_stage,review_status').eq('drug_id', resolvedDrugId),
      _sb.from('trials').select('id').eq('drug_id', resolvedDrugId).limit(50),
    ]);

    const normTargetIds  = (dtRes.data  || []).map(r => r.target_id);
    const normIndIds     = (diRes.data  || []).map(r => r.indication_id);
    const trialIds       = (trialRes.data || []).map(r => r.id);

    // Trial indications (if any trials found)
    let trialIndIds = [];
    if (trialIds.length) {
      const tiRes = await _sb.from('trial_indications')
        .select('indication_id,confidence_score')
        .in('trial_id', trialIds.slice(0, 30));
      trialIndIds = [...new Set((tiRes.data || []).map(r => r.indication_id))];
    }

    // Legacy area IDs from what the modal already fetched
    const legacyAreaIds = (legacyAreas || []).map(a => a.area_id);

    // Build per-area comparison
    const missingNormTargets = [];
    const missingNormInds    = [];
    const conflicting        = [];
    const matchedTargets     = [];
    const matchedInds        = [];

    legacyAreaIds.forEach(areaId => {
      const expectedTarget = AREA_TARGET_MAP[areaId];
      const expectedInds   = AREA_IND_MAP[areaId] || [];

      if (expectedTarget) {
        if (normTargetIds.includes(expectedTarget)) {
          matchedTargets.push({ area: areaId, target: expectedTarget });
        } else {
          missingNormTargets.push({ area: areaId, expected_target: expectedTarget });
        }
      }
      expectedInds.forEach(indId => {
        if (normIndIds.includes(indId) || trialIndIds.includes(indId)) {
          matchedInds.push({ area: areaId, indication: indId });
        } else {
          missingNormInds.push({ area: areaId, expected_indication: indId });
        }
      });
    });

    // Normalized relationships not in any legacy area (new_normalized_value)
    const legacyExpectedTargets = legacyAreaIds.map(a => AREA_TARGET_MAP[a]).filter(Boolean);
    const legacyExpectedInds    = legacyAreaIds.flatMap(a => AREA_IND_MAP[a] || []);
    const extraNormTargets = normTargetIds.filter(t => !legacyExpectedTargets.includes(t));
    const extraNormInds    = normIndIds.filter(i => !legacyExpectedInds.includes(i));

    // Classify each gap
    const diffClassifications = {};
    missingNormTargets.forEach(({ area, expected_target }) => {
      const key = `${area}→target:${expected_target}`;
      // TL1A-specific: many legacy TL1A drugs are IBD indication competitors
      if (area === 'tl1a') {
        const hasIBDInd = normIndIds.some(i => ['uc','cd'].includes(i));
        diffClassifications[key] = hasIBDInd
          ? 'ibd_indication_not_tl1a_target'
          : 'needs_manual_review';
      } else {
        diffClassifications[key] = 'normalized_gap';
      }
    });
    missingNormInds.forEach(({ area, expected_indication }) => {
      const key = `${area}→ind:${expected_indication}`;
      // Check if trial evidence supports the indication despite missing drug_indications row
      const hasTrialEvidence = trialIndIds.includes(expected_indication);
      diffClassifications[key] = hasTrialEvidence ? 'trial_evidence_only' : 'normalized_gap';
    });
    extraNormTargets.forEach(t => {
      diffClassifications[`extra_target:${t}`] = 'new_normalized_value';
    });
    extraNormInds.forEach(i => {
      diffClassifications[`extra_ind:${i}`] = 'new_normalized_value';
    });

    // Overall status
    const hasUnresolvedGaps   = missingNormTargets.length + missingNormInds.length > 0;
    const hasClassifiedOOS    = Object.values(diffClassifications)
      .some(c => c === 'ibd_indication_not_tl1a_target');
    const hasManualReview     = Object.values(diffClassifications)
      .some(c => c === 'needs_manual_review');
    const hasNormalizedGaps   = Object.values(diffClassifications)
      .some(c => c === 'normalized_gap');

    let status = 'match';
    if (hasNormalizedGaps)    status = 'acceptable_mismatch';
    if (hasManualReview)      status = 'needs_manual_review';
    if (hasClassifiedOOS)     status = 'compare_pass_oos_adjusted';
    if (!hasUnresolvedGaps && !hasClassifiedOOS && !hasManualReview) status = 'match';
    // Degrade to cross_table_inconsistency if both missing targets and missing inds
    if (missingNormTargets.length > 0 && missingNormInds.length > 0 && hasNormalizedGaps)
      status = 'cross_table_inconsistency';

    const record = {
      component:                  'openDrugEntityModal',
      path:                       'drug_entity_modal',
      drug_id:                    resolvedDrugId,
      legacy_sources:             ['drug_areas', 'drug_area_scores'],
      normalized_sources:         ['drug_targets', 'drug_indications', 'trial_indications'],
      legacy_area_ids:            legacyAreaIds,
      normalized_target_ids:      normTargetIds,
      normalized_indication_ids:  normIndIds,
      trial_indication_ids:       trialIndIds,
      missing_normalized_targets: missingNormTargets,
      missing_normalized_indications: missingNormInds,
      extra_normalized_targets:   extraNormTargets,
      extra_normalized_indications: extraNormInds,
      conflicting_relationships:  conflicting,
      difference_classifications: diffClassifications,
      status,
      timestamp:                  new Date().toISOString(),
    };

    window.__MERIDIAN_PHASE4_COMPARE__ = window.__MERIDIAN_PHASE4_COMPARE__ || [];
    window.__MERIDIAN_PHASE4_COMPARE__.push(record);
    console.log(
      `[Phase4C-Modal] drug=${resolvedDrugId} areas=[${legacyAreaIds}]` +
      ` targets=[${normTargetIds}] inds=[${normIndIds}]` +
      ` missing_targets=${missingNormTargets.length} missing_inds=${missingNormInds.length}` +
      ` → ${status}`
    );
  } catch(err) {
    console.warn('[Phase4C-Modal] dual-read error:', err.message);
  }
}

function _phasePill(phase) {
  if (!phase) return '<span style="font-size:10px;color:#94a3b8">—</span>';
  const p  = String(phase).toLowerCase();
  const bg = p.includes('3') ? '#dbeafe' : p.includes('2') ? '#dcfce7' : p.includes('1') ? '#fef9c3' : '#f1f5f9';
  const co = p.includes('3') ? '#1d4ed8' : p.includes('2') ? '#15803d' : p.includes('1') ? '#854d0e' : '#64748b';
  return `<span style="display:inline-block;font-size:10px;font-weight:800;background:${bg};color:${co};padding:2px 7px;border-radius:6px;white-space:nowrap">${phase}</span>`;
}

function _drugModalBodyHTML(drug, areas, trials, molData) {
  if (!drug) return '<p style="color:#94a3b8;font-style:italic;padding:10px 0">Drug data not available.</p>';
  const sections = [];

  // Mechanism + summary
  if (drug.mechanism || drug.drug_summary) {
    let html = '';
    if (drug.mechanism)    html += `<h5 style="margin:0 0 4px;font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.07em">Mechanism</h5><p style="margin:0 0 10px;font-size:12px;line-height:1.5;color:#1e293b">${drug.mechanism}</p>`;
    if (drug.drug_summary) html += `<h5 style="margin:0 0 4px;font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.07em">Summary</h5><p style="margin:0;font-size:12px;line-height:1.5;color:#1e293b">${drug.drug_summary}</p>`;
    sections.push(`<div class="pi-detail-section" style="grid-column:1/-1">${html}</div>`);
  }

  // Competitive positioning by area
  const areaPos = areas.filter(a => a.overlap || a.overlap_rationale || a.strategic_role);
  if (areaPos.length) {
    const posRows = areaPos.map(a => {
      const aLbl = _AREA_LABEL[a.area_id] || (a.area_id||'').toUpperCase();
      const aCls = _AREA_CLS[a.area_id]   || 'ct';
      const ov   = (a.overlap||'').toLowerCase();
      const tierBg = ov==='direct' ? '#fee2e2' : ov==='adjacent' ? '#dbeafe' : '#f1f5f9';
      const tierCo = ov==='direct' ? '#b91c1c' : ov==='adjacent' ? '#1d4ed8' : '#64748b';
      return `<div style="margin-bottom:10px;padding-bottom:10px;border-bottom:1px solid #f1f5f9">
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:5px;flex-wrap:wrap">
          <span class="entity-also-tag ${aCls}" style="cursor:default;font-size:10px">${aLbl}</span>
          ${a.overlap ? `<span style="font-size:10px;font-weight:800;background:${tierBg};color:${tierCo};padding:2px 8px;border-radius:6px">${a.overlap}</span>` : ''}
        </div>
        ${a.overlap_rationale ? `<p style="margin:0 0 4px;font-size:11px;color:#475569;line-height:1.4">${a.overlap_rationale}</p>` : ''}
        ${a.strategic_role    ? `<p style="margin:0;font-size:11px;color:#64748b;font-style:italic">${a.strategic_role}</p>`    : ''}
      </div>`;
    }).join('');
    sections.push(`<div class="pi-detail-section" style="grid-column:1/-1"><h5>🎯 Competitive Positioning</h5>${posRows}</div>`);
  }

  // Clinical trials table
  if (trials.length) {
    const trialRows = trials.map(t => `<tr style="border-bottom:1px solid #f1f5f9">
      <td style="padding:6px 8px;text-align:center">${_phasePill(t.phase)}</td>
      <td style="font-size:11px;font-weight:600;color:#1e293b;padding:6px 8px">${t.trial_name||t.id||'—'}</td>
      <td style="font-size:11px;color:#64748b;padding:6px 8px">${t.indication||'—'}</td>
      <td style="font-size:11px;color:#64748b;padding:6px 8px;text-align:center">${t.n_enrollment ? Number(t.n_enrollment).toLocaleString() : '—'}</td>
      <td style="font-size:11px;color:#64748b;padding:6px 8px">${t.primary_completion_date||'—'}</td>
      <td style="font-size:11px;padding:6px 8px"><span style="display:inline-block;padding:2px 6px;border-radius:5px;font-size:10px;font-weight:700;background:${t.status==='Active'||t.status==='Recruiting'?'#dcfce7':'#f1f5f9'};color:${t.status==='Active'||t.status==='Recruiting'?'#15803d':'#64748b'}">${t.status||'—'}</span></td>
    </tr>`).join('');
    const firstEp = trials.find(t => t.primary_endpoint)?.primary_endpoint;
    sections.push(`<div class="pi-detail-section" style="grid-column:1/-1"><h5>🧪 Clinical Trials (${trials.length})</h5>
      <div style="overflow-x:auto;margin-top:6px"><table style="width:100%;border-collapse:collapse">
        <thead><tr style="background:#f8fafc;border-bottom:2px solid #e2e8f0">
          <th style="text-align:center;padding:5px 8px;font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.06em">Phase</th>
          <th style="text-align:left;padding:5px 8px;font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.06em">Trial</th>
          <th style="text-align:left;padding:5px 8px;font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.06em">Indication</th>
          <th style="text-align:center;padding:5px 8px;font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.06em">N</th>
          <th style="text-align:left;padding:5px 8px;font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.06em">PCD</th>
          <th style="text-align:left;padding:5px 8px;font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.06em">Status</th>
        </tr></thead>
        <tbody>${trialRows}</tbody>
      </table></div>
      ${firstEp ? `<div style="margin-top:10px;font-size:11px;color:#475569;line-height:1.4"><span style="font-weight:700;color:#64748b">Primary Endpoint:</span> ${firstEp}</div>` : ''}
    </div>`);
  }

  // Molecule Intelligence — structural / mechanistic / competitive data
  if (molData) {
    const fs = molData.field_status || {};
    const _sb = (field) => {
      const s = fs[field];
      if (!s || s === 'confirmed') return '';
      const cfg = s === 'inferred'
        ? {bg:'#fffbeb',color:'#b45309',border:'#fde68a',label:'Inferred'}
        : {bg:'#f8fafc',color:'#94a3b8',border:'#e2e8f0',label:'Not disclosed'};
      return `<span style="font-size:7.5px;font-weight:700;text-transform:uppercase;background:${cfg.bg};color:${cfg.color};border:1px solid ${cfg.border};border-radius:5px;padding:1px 5px;white-space:nowrap;margin-left:4px">${cfg.label}</span>`;
    };
    const _fr = (label, value, key) => !value ? '' :
      `<div style="display:flex;align-items:baseline;gap:4px;padding:3px 0;border-bottom:1px solid #f8fafc;font-size:11px">
        <span style="color:#64748b;font-weight:600;white-space:nowrap;min-width:114px">${label}</span>
        <span style="color:#1e293b;flex:1">${value}</span>${_sb(key)}
       </div>`;
    const structRows = [
      _fr('Format',         molData.format,        'format'),
      _fr('Modality',       molData.modality,       'modality'),
      _fr('IgG Subclass',   molData.igg_subclass,   'igg_subclass'),
      _fr('Fc Engineering', molData.fc_engineering, 'fc_engineering'),
      _fr('Epitope',        molData.epitope,        'epitope'),
      _fr('Affinity (KD)',  molData.affinity_kd,    'affinity_kd'),
    ].filter(Boolean).join('');
    const thesisSection = molData.differentiation_claim
      ? `<div style="margin-top:8px;padding:8px 10px;background:#f5f3ff;border-radius:6px;border-left:3px solid #7c3aed">
          <div style="font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:0.05em;color:#7c3aed;margin-bottom:3px">Differentiation${_sb('differentiation_claim')}</div>
          <p style="font-size:11px;color:#1e293b;margin:0;line-height:1.45;font-style:italic">${molData.differentiation_claim}</p>
         </div>` : '';
    const safetySection = molData.safety_observations
      ? `<div style="margin-top:8px;padding-top:6px;border-top:1px solid #f1f5f9">
          <div style="font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:0.05em;color:#94a3b8;margin-bottom:3px">Safety Observations</div>
          <p style="font-size:11px;color:#334155;margin:0;line-height:1.4">${molData.safety_observations}</p>
         </div>` : '';
    const confBadge = molData.confidence
      ? `<div style="text-align:right;margin-top:6px"><span style="font-size:8px;font-weight:700;text-transform:uppercase;background:${molData.confidence==='high'?'#f0fdf4':molData.confidence==='medium'?'#fffbeb':'#f8fafc'};color:${molData.confidence==='high'?'#15803d':molData.confidence==='medium'?'#b45309':'#64748b'};border:1px solid ${molData.confidence==='high'?'#bbf7d0':molData.confidence==='medium'?'#fde68a':'#e2e8f0'};border-radius:8px;padding:1px 6px">${molData.confidence.charAt(0).toUpperCase()+molData.confidence.slice(1)} confidence</span></div>` : '';
    const srcLink = molData.source_url
      ? `<div style="text-align:right;margin-top:4px"><a href="${molData.source_url}" target="_blank" rel="noopener" style="font-size:9px;color:#1d4ed8">Source ↗</a></div>` : '';
    const molBody = [structRows, thesisSection, safetySection, confBadge, srcLink].filter(Boolean).join('');
    if (molBody) sections.push(`<div class="pi-detail-section" style="grid-column:1/-1">
      <h5 style="display:flex;align-items:center;gap:6px">🔬 Molecule Intelligence <span style="font-size:9px;font-weight:400;color:#94a3b8;font-style:italic">Structural · Mechanistic · Competitive</span></h5>
      ${molBody}
    </div>`);
  }

  if (!sections.length)
    return '<p style="color:#94a3b8;font-style:italic;padding:10px 0">No detailed data available for this drug yet.</p>';
  return `<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">${sections.join('')}</div>`;
}

function closeEntityModal() {
  document.getElementById('entity-modal-overlay')?.classList.remove('open');
  const bodyEl = document.getElementById('entity-modal-body');
  if (bodyEl) bodyEl.classList.remove('dossier-mode');
  const chipsEl = document.getElementById('entity-modal-hd-chips');
  if (chipsEl) chipsEl.innerHTML = '';
  const footerEl = document.getElementById('entity-modal-footer');
  if (footerEl) footerEl.style.display = 'none';
  // Reset area pills slot back to base id so next open can find it
  const apEl = document.getElementById('entity-modal-area-pills');
  const apElAlt = document.querySelector('[id^="cem-af-"]');
  if (apElAlt) { apElAlt.innerHTML = ''; apElAlt.id = 'entity-modal-area-pills'; }
  else if (apEl) apEl.innerHTML = '';
  document.body.style.overflow = '';
}
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeEntityModal(); });

// ── TAB REGISTRY ─────────────────────────────────────────────────────
// Isolated per-tab lifecycle hooks. Errors in one tab never affect others.
// ══════════════════════════════════════════════════════════════════════════
// TOP OPPORTUNITIES — "Top Competitive Developments" card on Home tab
// Merges: discovery_queue (high relevance), upcoming catalysts, recent intel
// ══════════════════════════════════════════════════════════════════════════

const _TOP_OPPS_TYPE = {
  discovery: { label: 'New Discovery',    color: '#7c3aed', bg: '#f5f3ff' },
  catalyst:  { label: 'Upcoming Readout', color: '#d97706', bg: '#fffbeb' },
  intel:     { label: 'Market Intel',     color: '#0369a1', bg: '#f0f9ff' },
};

async function loadTopOpps() {
  const body   = document.getElementById('top-opps-body');
  const period = document.getElementById('top-opps-period');
  if (!body) return;
  body.innerHTML = '<div style="padding:20px;text-align:center;color:#94a3b8;font-size:12px">Loading…</div>';

  const cutoff14  = new Date(Date.now() - 14*864e5).toISOString().slice(0,10);
  const cutoff30  = new Date(Date.now() - 30*864e5).toISOString().slice(0,10);
  const todayISO  = new Date().toISOString().slice(0,10);
  const in180days = new Date(Date.now() + 180*864e5).toISOString().slice(0,10);

  const [dqRes, catRes, intelRes, coRes] = await Promise.allSettled([
    // High-relevance discovery candidates (pending + approved, last 30 days)
    _sb.from('discovery_queue')
      .select('id,company_name,drug_name,area_id,target_id,relevance_score,competition_layer,overlap,reason,relevance_rationale,discovered_at,status')
      .gte('relevance_score', 7)
      .in('status', ['pending','approved'])
      .gte('discovered_at', cutoff30 + 'T00:00:00Z')
      .order('relevance_score', { ascending: false })
      .limit(8),

    // Upcoming catalysts (next 6 months, not resolved, key watches + high significance first)
    _sb.from('catalysts')
      .select('id,company_id,drug_id,label,catalyst_type,catalyst_date,sort_date,area_id,significance,is_key_watch,expected_impact')
      .eq('resolved', false)
      .lte('sort_date', in180days)
      .gte('sort_date', todayISO)
      .order('is_key_watch', { ascending: false })
      .order('sort_date', { ascending: true })
      .limit(8),

    // Recent high-importance intel (with company attribution)
    _sb.from('intel')
      .select('id,headline,intel_date,source_url,importance,intel_type,primary_company_id')
      .in('importance', ['high'])
      .gte('intel_date', cutoff14)
      .order('intel_date', { ascending: false })
      .limit(6),

    // Companies name lookup
    _sb.from('companies').select('id,name'),
  ]);

  // Company name lookup map
  const _coMap = {};
  (coRes.value?.data || []).forEach(c => { _coMap[c.id] = c.name; });

  // Build unified item list
  const items = [];

  // Discovery queue candidates
  (dqRes.value?.data || []).forEach(r => {
    items.push({
      type:      'discovery',
      priority:  r.relevance_score || 0,
      company:   r.company_name,
      drug:      r.drug_name,
      area:      r.area_id,
      headline:  r.reason || r.relevance_rationale || '',
      sub:       '',
      date:      r.discovered_at?.slice(0,10),
      badge:     r.overlap,
      layer:     r.competition_layer,
      status:    r.status === 'approved' ? '✓ approved' : '⏳ pending review',
      link_tab:  'discovery-queue',
    });
  });

  // Upcoming catalysts — high significance or key watches in window
  (catRes.value?.data || []).forEach(r => {
    const coName = _coMap[r.company_id] || r.company_id || '';
    const sigPriority = r.significance === 'high' ? 9 : r.significance === 'medium' ? 7 : 5;
    items.push({
      type:      'catalyst',
      priority:  r.is_key_watch ? Math.max(sigPriority, 9) : sigPriority,
      company:   coName,
      drug:      r.drug_id || '',
      area:      r.area_id,
      headline:  r.label || r.catalyst_type || '',
      sub:       r.expected_impact || '',
      date:      r.sort_date || r.catalyst_date,
      badge:     r.catalyst_type,
      status:    r.is_key_watch ? '⭐ Key Watch' : (r.significance === 'high' ? '● High Significance' : ''),
      link_tab:  null,
    });
  });

  // Recent high-importance intel with company attribution
  (intelRes.value?.data || []).forEach(r => {
    const coName = r.primary_company_id ? (_coMap[r.primary_company_id] || r.primary_company_id) : '';
    items.push({
      type:      'intel',
      priority:  8,
      company:   coName,
      drug:      '',
      area:      '',
      headline:  r.headline || '',
      sub:       '',
      date:      r.intel_date,
      badge:     r.intel_type,
      url:       r.source_url,
      status:    '',
      link_tab:  null,
    });
  });

  if (!items.length) {
    body.innerHTML = '<div style="padding:24px;text-align:center;color:#94a3b8;font-size:12px">No recent developments found. Enrichment runs will populate this card.</div>';
    if (period) period.textContent = '· no data';
    return;
  }

  // Sort by priority desc, then date desc
  items.sort((a,b) => {
    if (b.priority !== a.priority) return b.priority - a.priority;
    return (b.date||'') > (a.date||'') ? 1 : -1;
  });

  const shown = items.slice(0, 7);
  if (period) period.textContent = `· ${shown.length} of ${items.length}`;

  body.innerHTML = shown.map((item, idx) => {
    const t = _TOP_OPPS_TYPE[item.type] || _TOP_OPPS_TYPE.intel;
    const areaTag = item.area ? `<span style="font-size:9px;font-weight:700;background:${AREA_BG[item.area]||'#f1f5f9'};color:${AREA_COLORS[item.area]||'#64748b'};padding:1px 5px;border-radius:8px;margin-left:4px">${AREA_LABELS[item.area]||item.area}</span>` : '';
    const layerTag = item.layer ? `<span style="font-size:9px;font-weight:700;color:#7c3aed;background:#f5f3ff;padding:1px 5px;border-radius:8px;margin-left:3px">L${item.layer}</span>` : '';
    const co = item.company ? `<span style="font-weight:700;color:#0f172a">${item.company}</span>${item.drug && item.drug !== item.company ? ` <span style="color:#64748b">/ ${item.drug}</span>` : ''}${areaTag}${layerTag}` : '';
    const countdown = item.type === 'catalyst' ? catDaysTag(item.date) : '';
    const dateStr = !countdown && item.date ? `<span style="color:#cbd5e1;font-size:10px;margin-left:auto;padding-left:8px;white-space:nowrap">${item.date}</span>` : '';
    const srcBadge = item.type === 'intel' && !item.url ? _noSrcBadge() : '';
    const srcLink = item.type === 'intel' && item.url ? `<a href="${item.url}" target="_blank" rel="noopener" style="font-size:9px;color:#2563eb;margin-left:4px;">↗ ${_srcDomain(item.url)}</a>` : '';
    const statusStr = item.status ? `<span style="font-size:10px;color:#94a3b8;margin-top:2px">${item.status}</span>` : '';
    const navClick = item.link_tab ? `onclick="switchTabTo('${item.link_tab}')"` : item.url ? `onclick="window.open('${item.url}','_blank')"` : '';
    const clickCursor = (item.link_tab || item.url) ? 'cursor:pointer;' : '';
    const isHot = item.priority >= 9;

    return `<div ${navClick} style="${clickCursor}display:flex;align-items:flex-start;gap:10px;padding:10px 16px;border-bottom:1px solid #f8fafc;${isHot?'background:#fffbeb;border-left:3px solid #f59e0b;':''}">
      <div style="display:flex;flex-direction:column;align-items:center;gap:2px;min-width:26px;margin-top:1px">
        <span style="font-size:11px;font-weight:900;color:${item.priority>=9?'#dc2626':item.priority>=7?'#d97706':'#94a3b8'}">${item.priority}</span>
        <div style="width:3px;height:3px;border-radius:50%;background:${t.color};opacity:0.5"></div>
      </div>
      <div style="flex:1;min-width:0">
        <div style="display:flex;align-items:center;gap:4px;flex-wrap:wrap;margin-bottom:3px">
          <span style="font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:0.5px;color:${t.color};background:${t.bg};padding:1px 6px;border-radius:8px">${t.label}</span>
          ${co}
          ${countdown}
          ${dateStr}
          ${srcLink}${srcBadge}
        </div>
        <div style="font-size:11px;color:#374151;line-height:1.4">${item.headline}</div>
        ${item.sub ? `<div style="font-size:10px;color:#6b7280;margin-top:2px;line-height:1.35">${item.sub}</div>` : ''}
        ${statusStr}
      </div>
    </div>`;
  }).join('') + `<div style="padding:8px 16px;background:#f8fafc;text-align:right">
    <span style="font-size:10px;color:#94a3b8">Updated on page load · </span>
    <a href="#" onclick="loadTopOpps();return false" style="font-size:10px;color:#2563eb;text-decoration:none">Refresh</a>
  </div>`;
}

// To add a new tab: registerTab('my-tab', { onEnter() {...}, onLeave() {...} })
// Never edit switchTab to add new tabs — use registerTab instead.
const TAB_REGISTRY = {};
function registerTab(id, hooks = {}) { TAB_REGISTRY[id] = hooks; }

// Core tab registrations — add new target tabs here as the platform grows
// Live Intelligence + Coverage Atlas — embedded pages; iframe src set lazily on first visit (Kyle 2026-06-07)
function _lazyFrame(frameId) {
  const f = document.getElementById(frameId);
  // cache-bust per session so the embedded page is never a stale cached copy (Kyle 2026-06-07)
  if (f && !f.src) f.src = f.dataset.src + (f.dataset.src.includes('?') ? '&' : '?') + 'cb=' + Date.now();
}
// 2026-06-19 (rec #5): Live Intelligence + Coverage Atlas consolidated into the
// Intelligence & Coverage tab (#tab-intel2) as sub-views. The sub-tab switch
// lazy-loads each iframe on first open.
function intelSubTab(view) {
  ['intelligence','coverage','live'].forEach(v => {
    const pane = document.getElementById('intel2-view-' + v);
    if (pane) pane.style.display = (v === view) ? '' : 'none';
  });
  document.querySelectorAll('#intel2-subtabs .intel2-subtab').forEach(b => {
    b.classList.toggle('intel2-subon', b.dataset.view === view);
  });
  if (view === 'coverage') _lazyFrame('atlas-frame');
  if (view === 'live')     _lazyFrame('live-frame');
}

// 2026-06-19 (rec #10): valuation-card comps now render from deal_comparables via
// renderValuationComps() in assets/js/asset_tab.js.
registerTab('meridian-issue', {
  onEnter() {
    loadMeridianIssue();
    const arc = document.getElementById('meridian-tab-archive');
    if (arc) arc.style.display = 'flex';
  },
  onLeave() {
    const arc = document.getElementById('meridian-tab-archive');
    if (arc) arc.style.display = 'none';
  }
});
// 2026-06-19: pharma-intel re-enabled as the live Company Repository only.
// Static China/US/AI ranking cards removed (rec #4); _addRankingDossierBtns() retired with them.
registerTab('pharma-intel', {
  onEnter() { _initAllCompanies(); }
});
registerTab('industry-insights', {

  onEnter() { _iifSyncSidebar(); loadIndustryInsightsFeed(); }

});

registerTab('discovery-queue', {
  onEnter() { if (!_dqData.length) dqLoad(); }
});
registerTab('submitted-intel', {
  onEnter() { siLoad(); }
});
registerTab('ontology-explorer', {
  onEnter() {
    if (!window.OEX_INITIALIZED) {
      window.OEX_INITIALIZED = true;
      setTimeout(oexRender, 80); // Wait for DOM to settle after tab switch
    } else {
      // Re-init CPM if canvas never rendered (was hidden during first init)
      setTimeout(function() {
        var cv = document.getElementById('oex-cpm-canvas');
        if (cv && cv.width <= 300) oexRender();
      }, 80);
    }
  }
});
registerTab('audit', {
  onEnter() { auditLoad(); }
});
registerTab('tl1a', {
  onEnter() {
    loadAreaPI('tl1a');
    loadTL1AIntelFeed();
    document.getElementById('tl1a-pills-left')?.classList.add('tl1a-pills-visible');
    document.getElementById('tl1a-pills-right')?.classList.add('tl1a-pills-visible');
  },
  onLeave() {
    document.getElementById('tl1a-pills-left')?.classList.remove('tl1a-pills-visible');
    document.getElementById('tl1a-pills-right')?.classList.remove('tl1a-pills-visible');
  }
});
// ── Generic drug modal system (used by all non-TL1A drug tabs) ──────────────
function openDrugModal(id) {
  document.querySelectorAll('.tl1a-modal-overlay').forEach(m => m.classList.remove('open'));
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.add('open');
  document.body.style.overflow = 'hidden';
  // Lazy-load BD activity
  const bdMatch = id.match(/^(tslp|il4ra-tslp|il4ra-ox40l|igf1r-tshr|fcrn|ace)-modal-bd$/);
  if (bdMatch) {
    const tabId = bdMatch[1];
    const bdEl = document.getElementById(tabId + '-bd-activity-modal');
    if (bdEl && !bdEl.dataset.loaded) { _loadBdIntoModal(tabId, bdEl); bdEl.dataset.loaded = '1'; }
  }
  // Lazy-load catalysts when catalyst modal opens
  const catMatch = id.match(/^(tslp|il4ra-tslp|il4ra-ox40l|igf1r-tshr|fcrn|ace)-modal-catalysts$/);
  if (catMatch && typeof loadAreaCatalysts === 'function') loadAreaCatalysts(catMatch[1]);
  // Lazy-load intel when intel modal opens
  const intelMatch = id.match(/^(tslp|il4ra-tslp|il4ra-ox40l|igf1r-tshr|fcrn|ace)-modal-intel$/);
  if (intelMatch && typeof loadAreaIntel === 'function') loadAreaIntel(intelMatch[1]);
  // Lazy-load bd_insights when catalyst modal opens (area insights panel)
  if (catMatch && typeof loadBdInsights === 'function') loadBdInsights(catMatch[1]);
}
// TL1A uses its own function names — wire them to the shared open/close logic
function openTl1aModal(id) {
  document.querySelectorAll('.tl1a-modal-overlay').forEach(m => m.classList.remove('open'));
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.add('open');
  document.body.style.overflow = 'hidden';
  if (id === 'tl1a-modal-catalysts' && typeof loadAreaCatalysts === 'function') loadAreaCatalysts('tl1a');
  if (id === 'tl1a-modal-catalysts' && typeof loadBdInsights    === 'function') loadBdInsights('tl1a');
  if (id === 'tl1a-modal-intel'     && typeof loadAreaIntel     === 'function') loadAreaIntel('tl1a');
  if (id === 'tl1a-modal-bd-activity') {
    const bdEl = document.getElementById('tl1a-bd-activity');
    if (bdEl && !bdEl.dataset.loaded) { _loadBdIntoModal('tl1a', bdEl); bdEl.dataset.loaded = '1'; }
  }
  if (id === 'tl1a-modal-ailux') _loadAiluxBdContext();
  if (id === 'tl1a-modal-bispecific-race') _loadBispecificRace();
}
function openBispecificRaceModal() {
  openTl1aModal('tl1a-modal-bispecific-race');
}
function closeTl1aModal(el) {
  if (!el) return;
  el.classList.remove('open');
  if (!document.querySelector('.tl1a-modal-overlay.open')) document.body.style.overflow = '';
}

// ── Ailux BD Context loader ──────────────────────────────────────────────────
var _ailuxBdContextLoaded = false;
async function _loadAiluxBdContext() {
  if (_ailuxBdContextLoaded) return;
  const container = document.getElementById('ailux-bd-context-cards');
  if (!container) return;
  try {
    const res = await _sb.from('ailux_bd_context')
      .select('context_type,context_key,context_value,strategic_implication,confidence')
      .in('context_key', ['asset_sale_timing','optimal_partner_profile','negotiation_leverage_drivers','china_vs_global_strategy'])
      .order('context_type');
    const rows = res.data || [];
    if (!rows.length) { container.innerHTML = '<div style="color:rgba(255,255,255,0.5);font-size:11px">No strategy context loaded.</div>'; return; }
    const keyLabels = {
      asset_sale_timing: 'Deal Timing',
      optimal_partner_profile: 'Best-Fit Partners',
      negotiation_leverage_drivers: 'Leverage Drivers',
      china_vs_global_strategy: 'China vs. Global Strategy'
    };
    const confColor = { high: '#86efac', medium: '#fcd34d', low: '#f87171' };
    container.innerHTML = rows.map(function(r) {
      const label = keyLabels[r.context_key] || r.context_key.replace(/_/g,' ');
      const conf = r.confidence || 'medium';
      const cc = confColor[conf] || '#fcd34d';
      return '<div style="background:rgba(255,255,255,0.09);border-radius:7px;padding:12px;border-top:2px solid ' + cc + '30">' +
        '<div style="font-size:9px;font-weight:800;color:' + cc + ';text-transform:uppercase;letter-spacing:0.4px;margin-bottom:4px">' + label + '</div>' +
        '<div style="font-size:11px;color:rgba(255,255,255,0.88);line-height:1.55;margin-bottom:7px">' + escHtml(r.context_value.substring(0, 280)) + (r.context_value.length > 280 ? '…' : '') + '</div>' +
        (r.strategic_implication ? '<div style="font-size:10.5px;color:rgba(255,255,255,0.6);font-style:italic;border-top:1px solid rgba(255,255,255,0.12);padding-top:6px;line-height:1.45">' + escHtml(r.strategic_implication.substring(0, 200)) + (r.strategic_implication.length > 200 ? '…' : '') + '</div>' : '') +
        '</div>';
    }).join('');
    _ailuxBdContextLoaded = true;
  } catch(e) {
    console.warn('ailux_bd_context load error', e);
    if (container) container.innerHTML = '<div style="color:rgba(255,255,255,0.4);font-size:11px">Strategy context unavailable.</div>';
  }
}

// ── Bispecific Race loader ────────────────────────────────────────────────────
var _bispecificRaceLoaded = false;
async function _loadBispecificRace() {
  if (_bispecificRaceLoaded) return;
  const wrap = document.getElementById('bispecific-race-table-wrap');
  const conflictCallout = document.getElementById('bispecific-race-conflict-callout');
  const conflictBody = document.getElementById('bispecific-race-conflict-body');
  if (!wrap) return;
  try {
    const res = await _sb.from('drug_bispecific_landscape')
      .select('*')
      .order('race_rank', { ascending: true });
    const rows = res.data || [];
    if (!rows.length) { wrap.innerHTML = '<div style="color:#94a3b8;font-size:12px;padding:16px">No landscape data found.</div>'; return; }

    const phaseClass = {
      'Phase 2b': 'race-phase-ph2b',
      'Phase 2': 'race-phase-ph2',
      'Phase 1': 'race-phase-ph1',
      'Pre-IND': 'race-phase-pre',
      'Preclinical': 'race-phase-prec'
    };
    const rankBadge = (r) => {
      const cls = r === 1 ? 'race-rank-1' : r === 2 ? 'race-rank-2' : r === 3 ? 'race-rank-3' : 'race-rank-other';
      return `<span class="race-rank-badge ${cls}">${r}</span>`;
    };
    const fmtBadge = (fmt) => {
      if (fmt === 'co_formulation' || fmt === 'co_dosing')
        return `<span class="race-format-badge race-fmt-co">co-form</span>`;
      return `<span class="race-format-badge race-fmt-true">single mol.</span>`;
    };
    const phaseBadge = (ph) => {
      const cls = phaseClass[ph] || 'race-phase-prec';
      return `<span class="race-phase-tag ${cls}">${ph || 'Unknown'}</span>`;
    };

    const tableRows = rows.map(r => {
      const isAlx = r.drug_id === 'alx001';
      const rowCls = isAlx ? ' class="race-alx-row"' : '';
      const mechanismNote = r.vs_alx001_mechanism && r.vs_alx001_mechanism.includes('CRITICAL DISADVANTAGE')
        ? `<div class="race-mech-note">p40-blocking (vs. p19-selective): suppresses IL-12/NK immunity</div>` : '';
      const conflictTag = r.has_internal_portfolio_conflict
        ? `<br><span class="race-conflict-badge" style="margin-top:4px;display:inline-block">Portfolio Conflict</span>` : '';
      const valencyNote = r.valency && r.valency !== 'co_formulation' ? `<div style="font-size:9.5px;color:#475569;margin-top:2px">Valency: ${r.valency}</div>` : '';
      const nctLink = r.nct_id
        ? `<a href="https://clinicaltrials.gov/study/${r.nct_id}" target="_blank" rel="noopener" style="font-size:9.5px;color:#2563eb;display:inline-block;margin-top:3px">${r.nct_id}</a>` : '';
      const partner = r.development_partner ? `<div style="font-size:9.5px;color:#64748b;margin-top:2px">+ ${r.development_partner}</div>` : '';
      const timeline = r.vs_alx001_timeline ? `<div class="race-timeline-note">${escHtml(r.vs_alx001_timeline)}</div>` : '';
      const milestone = r.landmark_event ? `<div style="font-size:10px;color:#475569;margin-top:3px;font-style:italic">${escHtml(r.landmark_event.substring(0,80))}${r.landmark_event.length > 80 ? '...' : ''}</div>` : '';

      return `<tr${rowCls}>
        <td style="text-align:center;width:40px">${rankBadge(r.race_rank || 99)}</td>
        <td><strong style="font-size:12px;color:#1e3a5f">${escHtml(r.drug_name)}</strong>${conflictTag}</td>
        <td><div style="font-size:11px;font-weight:600;color:#374151">${escHtml(r.company_name || '')}${isAlx ? ' <span style="color:#166534;font-size:9px;font-weight:800">(AILUX)</span>' : ''}</div>${partner}</td>
        <td>${phaseBadge(r.current_phase)}</td>
        <td>${fmtBadge(r.drug_format)}${valencyNote}</td>
        <td style="font-size:10px;color:#374151">${r.il23_arm_selectivity === 'p19_selective' ? '<span style="color:#166534;font-weight:700">p19-selective</span>' : r.il23_arm_selectivity === 'p40_blocking' ? '<span style="color:#dc2626;font-weight:700">p40-blocking</span>' : '<span style="color:#94a3b8">unknown</span>'}${mechanismNote}</td>
        <td style="font-size:10px;color:#374151">${timeline}${milestone}${nctLink}</td>
      </tr>`;
    }).join('');

    wrap.innerHTML = `<table class="race-table">
      <thead><tr>
        <th style="text-align:center">Rank</th>
        <th>Drug</th>
        <th>Company</th>
        <th>Phase</th>
        <th>Format</th>
        <th>IL-23 Arm</th>
        <th>Timeline vs. ALX001</th>
      </tr></thead>
      <tbody>${tableRows}</tbody>
    </table>`;

    // Show Sanofi conflict callout
    const conflictRow = rows.find(r => r.has_internal_portfolio_conflict && r.internal_conflict_description);
    if (conflictRow && conflictCallout && conflictBody) {
      conflictBody.textContent = conflictRow.internal_conflict_description;
      conflictCallout.style.display = 'block';
    }

    _bispecificRaceLoaded = true;
  } catch(e) {
    console.warn('[BispecificRace] load error', e);
    if (wrap) wrap.innerHTML = `<div style="color:#dc2626;font-size:12px;padding:16px">Error loading landscape: ${e.message}</div>`;
  }
}

async function _loadBdIntoModal(tabId, el) {
  const areas = TAB_AREA_MAP[tabId];
  if (!areas) { el.innerHTML = '<div style="padding:14px;color:#94a3b8;font-size:12px">No BD data for this area.</div>'; return; }
  try {
    // Phase 3 dual-filter: target_id OR area_id during transition
    let { data: rows, error } = await _sb.from('deals').select('*')
      .or(`target_id.in.(${areas.join(',')}),area_id.in.(${areas.join(',')})`)
      .order('deal_date', { ascending: false });
    if (error) throw error;
    // Fallback: if area_id filter returns nothing, also try deals with no area_id set
    // that may still belong here — query all and filter by relevance to the area label
    if ((!rows || rows.length === 0)) {
      const { data: allRows } = await _sb.from('deals').select('*').is('area_id', null).order('deal_date', { ascending: false }).limit(200);
      // Keep only deals where headline mentions any of the area keywords
      const areaKeywords = { tl1a:['TL1A','tl1a','IL-23','il23'], tslp:['TSLP','tslp'], il4ra:['IL-4','il4','OX40'], igf1r:['IGF-1R','igf1r','TED','thyroid eye'], fcrn:['FcRn','fcrn','neonatal Fc'], tcell:['CAR-T','TCR','T-cell','TIL'] };
      const kws = areas.flatMap(a => areaKeywords[a] || [a]);
      rows = (allRows||[]).filter(d => {
        const hay = ((d.headline||'')+(d.detail||'')+(d.from_company||'')+(d.to_company||'')).toLowerCase();
        return kws.some(k => hay.includes(k.toLowerCase()));
      });
    }
    _bdaState[tabId] = { rows: rows||[], filter:'all', search:'' };
    // Render directly: temporarily give el the expected ID so _bdaRender can find it,
    // then restore. This avoids the duplicate-ID bug where a tmp div with the same ID
    // confuses getElementById and causes _bdaRender to write to the real element
    // while tmp.innerHTML (empty) then wipes it.
    const origId = el.id;
    el.id = tabId + '-bd-activity';
    _bdaRender(tabId);
    el.id = origId;
  } catch(e) { el.innerHTML = `<div style="padding:14px;color:#dc2626;font-size:12px">Error: ${e.message}</div>`; }
}
function _showDrugPills(tid) {
  document.getElementById(tid+'-pills-left')?.classList.add('tl1a-pills-visible');
  document.getElementById(tid+'-pills-right')?.classList.add('tl1a-pills-visible');
}
function _hideDrugPills(tid) {
  document.getElementById(tid+'-pills-left')?.classList.remove('tl1a-pills-visible');
  document.getElementById(tid+'-pills-right')?.classList.remove('tl1a-pills-visible');
  document.querySelectorAll('.tl1a-modal-overlay.open').forEach(m => { m.classList.remove('open'); });
  document.body.style.overflow = '';
}
['tslp','il4ra-tslp','il4ra-ox40l','igf1r-tshr','fcrn','ace'].forEach(tid => {
  registerTab(tid, {
    onEnter() {
      loadAreaPI(tid);
      if (typeof loadMoleculeTab==='function' && !_molTabLoaded[tid]) loadMoleculeTab(tid);
      _showDrugPills(tid);
    },
    onLeave() { _hideDrugPills(tid); }
  });
});


// ══════════════════════════════════════════════════════════════════════════
// AreaPI — Universal Supabase-driven PI table for all drug tabs
// Reads cls / overlap / target from drugs table (added via schema migration)
// Falls back gracefully if columns are null
// ══════════════════════════════════════════════════════════════════════════

const _areaPIs = {};

// ── Phase 4B: Dual-read validation infrastructure ─────────────────────────────
// Stores runtime comparison records from parallel normalized reads.
// Access via: window.__MERIDIAN_PHASE4_COMPARE__
// Print summary via: window.showPhase4Compare()
window.__MERIDIAN_PHASE4_COMPARE__ = window.__MERIDIAN_PHASE4_COMPARE__ || [];
window.showPhase4Compare = function() {
  const records = window.__MERIDIAN_PHASE4_COMPARE__;
  if (!records.length) { console.log('[Phase4B] No comparison records yet. Trigger an IBD tab load first.'); return; }
  records.forEach(r => {
    const icon = r.status === 'compare_pass_oos_adjusted' ? '🟢' :
                 r.status === 'compare_pass'              ? '✅' :
                 r.status === 'migration_blocker'         ? '🔴' : '🟠';
    console.group(`${icon} [Phase4B] ${r.component} — ${r.path}  (${r.timestamp})`);
    console.log(`  legacy_source:      ${r.legacy_source}`);
    console.log(`  normalized_source:  ${r.normalized_source}`);
    console.log(`  legacy_count:       ${r.legacy_count}`);
    console.log(`  normalized_count:   ${r.normalized_count}`);
    console.log(`  overlap_count:      ${r.overlap_count}`);
    console.log(`  raw_match_pct:      ${r.raw_match_pct}%`);
    console.log(`  adjusted_match_pct: ${r.adjusted_match_pct}%`);
    console.log(`  status:             ${r.status}`);
    if (r.extra_legacy.length)     console.log(`  extra_legacy:`, r.extra_legacy);
    if (r.extra_normalized.length) console.log(`  extra_normalized:`, r.extra_normalized);
    if (Object.keys(r.difference_classifications).length)
      console.log(`  classifications:`, r.difference_classifications);
    console.groupEnd();
  });
};

function _makeAreaPI(tabId, areaIds) {
  const STAGE_ORDER_PI = {Approved:0,'Phase 3':1,'Phase 2':2,'Phase 1':3,'Pre-IND':4,Preclinical:5};
  const OV_ORDER = {Direct:0,Adjacent:1,'Same-Space':2,Watch:3};

  return {
    tabId, areaIds,
    data:[], entities:[], filteredEntities:[], expanded:new Set(),
    sortCol:'relevance', sortDir:1, loaded:false,
    _entityMeta: {},    // bulk meta: drugCount, indScope, activeTrials, nextCatalyst keyed by company_id
    _profileCache: {},  // company_profiles keyed by entity_id — populated on expand (Stage 3)

    async init() {
      const el = document.getElementById(this.tabId + '-area-pi');
      if (!el || typeof _sb === "undefined") return;
      try {
        // ── Phase 5 Candidate 1 — IBD normalized source ─────────────────────
        // When FEATURE_FLAGS.useNormalizedIBD=true: drug membership from
        // drug_indications (uc,cd) instead of drug_areas (ibd).
        // Competitive scores (drug_area_scores), combos, companies: unchanged.
        // Rollback: set FEATURE_FLAGS.useNormalizedIBD = false.
        const _IBD_NORM = !!(FEATURE_FLAGS.useNormalizedIBD && this.areaIds.includes('ibd'));
        // ── Phase 5 Candidate 2 — TED normalized source ──────────────────────
        // When FEATURE_FLAGS.useNormalizedTED=true: drug membership from
        // drug_indications (ted) instead of drug_areas (igf1r).
        // Competitive scores (drug_area_scores), combos, companies: unchanged.
        // Rollback: set FEATURE_FLAGS.useNormalizedTED = false.
        const _TED_NORM = !!(FEATURE_FLAGS.useNormalizedTED && this.areaIds.includes('igf1r'));
        // ── Phase 5 Candidate 4 — TL1A unified source ────────────────────────
        // When FEATURE_FLAGS.useUnifiedTL1A=true: drug membership from
        // drug_targets (target_id='tl1a') instead of drug_areas (tl1a).
        // This narrows the tab to actual TL1A-mechanism drugs only.
        // The 17 scope_difference drugs (α4β7, IL-23p19, JAK1, etc.) correctly
        // drop from the TL1A tab — they are not TL1A-targeting drugs.
        // Pre-flight audit: 100% adj match (33/33). All differences classified.
        // Rollback: set FEATURE_FLAGS.useUnifiedTL1A = false.
        const _TL1A_NORM = !!(FEATURE_FLAGS.useUnifiedTL1A && this.areaIds.includes('tl1a'));
        // ── Phase 5 Candidates 5+6 — TSLP + IL-4Rα unified source ───────────
        // Bundled because il4ra-tslp tab uses areaIds=['il4ra','tslp']:
        // activating only one would require a mixed legacy/normalized source.
        // When FEATURE_FLAGS.useUnifiedAtopy=true: drug membership from
        // drug_targets(target_id IN _atopyTargets) instead of drug_areas.
        // Atopy tabs scope_diff exclusions:
        //   IL-4Rα: OX40L(×1), IL-13(×3), IL-31Rα(×1) → 5 excluded, adj=100%
        //   TSLP:   IL-33(×2),IL-5Rα(×1),IL-5(×1),IL-4Rα(×1),IL-33R(×1) → 6 excl, adj=100%
        // Pre-flight audit (Session 54): all differences classified, adj=100%.
        // Rollback: set FEATURE_FLAGS.useUnifiedAtopy = false.
        const _il4ra = this.areaIds.includes('il4ra');
        const _tslp  = this.areaIds.includes('tslp');
        const _ATOPY_NORM = !!(FEATURE_FLAGS.useUnifiedAtopy && (_il4ra || _tslp));
        const _atopyTargets = [
          ...(_il4ra ? ['il4ra'] : []),
          ...(_tslp  ? ['tslp','tslpr'] : [])
        ];
        this._atopyNorm    = _ATOPY_NORM;    // stored for _loadEntityMeta
        this._atopyTargets = _atopyTargets;  // stored for _loadEntityMeta
        this._ibdNorm  = _IBD_NORM;  // stored for _loadEntityMeta
        this._tl1aNorm = _TL1A_NORM; // stored for _loadEntityMeta
        // ── Phase 5 Candidate 7 — FcRn unified source ────────────────────────
        // When FEATURE_FLAGS.useUnifiedFCRN=true: drug membership from
        // drug_targets(target_id='fcrn') instead of drug_areas(area_id='fcrn').
        // Gains: riliprubart (SAR443765, Phase 3, IgAN+CIDP — confirmed FcRn inhibitor).
        // Drops: atg-201 (scope_difference: CD19×CD3 bispecific — Watch-tier in legacy
        //         FcRn area as UCB autoimmune asset, not an FcRn-targeting agent).
        // Pre-flight (Session 54, updated Session 60): legacy=7 norm=7 overlap=6
        //   scopeDiff=1(atg-201) adj=6/6=100% → compare_pass_oos_adjusted.
        // Rollback: set FEATURE_FLAGS.useUnifiedFCRN = false.
        const _FCRN_NORM = !!(FEATURE_FLAGS.useUnifiedFCRN && this.areaIds.includes('fcrn'));
        this._fcrnNorm = _FCRN_NORM;  // stored for _loadEntityMeta

        // Parallel fetches — query A switches on flag; B/C/D always unchanged
        // Precedence: _ATOPY_NORM → _FCRN_NORM → _TL1A_NORM → _IBD_NORM → _TED_NORM → legacy drug_areas
        const [_memberResult, { data:comboRows }, { data:scoreRows }, { data:companiesRows }] = await Promise.all([
          _ATOPY_NORM
            ? _sb.from('drug_targets').select('drug_id').in('target_id', _atopyTargets)
            : _FCRN_NORM
              ? _sb.from('drug_targets').select('drug_id').eq('target_id', 'fcrn')
              : _TL1A_NORM
                ? _sb.from('drug_targets').select('drug_id').eq('target_id', 'tl1a')
                : _IBD_NORM
                  ? _sb.from('drug_indications').select('drug_id').in('indication_id', ['uc','cd'])
                  : _TED_NORM
                    ? _sb.from('drug_indications').select('drug_id').eq('indication_id', 'ted')
                    : _sb.from('drug_areas')
                        .select('drugs(id,name,brand_name,display_name,company_id,mechanism,target,cls,overlap,stage,stage_detail,key_data,ailux_angle,entity_id,entity_name,entity_type,partner_company,partnership_type,partnership_verified,licensor_name,licensor_code,indication_short,drug_summary,differentiation_thesis,strategic_role,route,dosing_type,current_owner_company_id,originator_company_id,ownership_status,display_partner_name,companies!company_id(name,ticker,status,hq_city,hq_country))')
                        .in('area_id', this.areaIds),
          _sb.from('drug_combinations')
            .select('company_id')
            .in('area_id', this.areaIds),
          // Phase 2 flip (Session 78): drug_area_scores → drug_competitive_scores
          // context_id is the canonical area identifier; IBD expanded to include uc/cd
          // indication-based rows alongside legacy ibd-keyed rows.
          _sb.from('drug_competitive_scores')
            .select('drug_id,context_id,overlap,cls,overlap_rationale,vs_ailux,confidence_level,competitive_relevance,relevance_rationale,relevance_score_numeric,score_breakdown_json')
            .in('context_id', this.areaIds.includes('ibd')
              ? [...this.areaIds.filter(a=>a!=='ibd'),'ibd','uc','cd']
              : this.areaIds),
          _sb.from('companies').select('id,name,ticker,status,hq_city,hq_country'),
        ]);

        // Normalized path: resolve drug_ids → full drug objects (second fetch)
        let rows, error;
        if (_ATOPY_NORM || _FCRN_NORM || _IBD_NORM || _TED_NORM || _TL1A_NORM) {
          if (_memberResult.error) throw _memberResult.error;
          const _normIds = [...new Set((_memberResult.data||[]).map(r=>r.drug_id))];
          if (_normIds.length) {
            const { data:_normDrugs, error:_normErr } = await _sb.from('drugs')
              .select('id,name,brand_name,display_name,company_id,mechanism,target,cls,overlap,stage,stage_detail,key_data,ailux_angle,entity_id,entity_name,entity_type,partner_company,partnership_type,partnership_verified,licensor_name,licensor_code,indication_short,drug_summary,differentiation_thesis,strategic_role,route,dosing_type,current_owner_company_id,originator_company_id,ownership_status,display_partner_name,companies!company_id(name,ticker,status,hq_city,hq_country)')
              .in('id', _normIds);
            if (_normErr) throw _normErr;
            rows = (_normDrugs||[]).map(d => ({drugs:d}));
          } else {
            rows = [];
          }
          error = null;
        } else {
          ({ data:rows, error } = _memberResult);
        }
        if (error) throw error;

        this.comboCountByCompany = {};
        (comboRows||[]).forEach(c => {
          this.comboCountByCompany[c.company_id] = (this.comboCountByCompany[c.company_id]||0) + 1;
        });

        // Build per-drug best area score map — prefer highest-tier score across all areaIds
        // so a multi-area tab (e.g. il4ra-tslp) shows the most relevant classification
        const _OV_SCORE = {Direct:0, Adjacent:1, 'Same-Space':2, Watch:3};
        const areaScoreMap = {};
        (scoreRows||[]).forEach(s => {
          const ex = areaScoreMap[s.drug_id];
          if (!ex || (_OV_SCORE[s.overlap]??9) < (_OV_SCORE[ex.overlap]??9)) {
            areaScoreMap[s.drug_id] = s;
          }
        });

        // Build company lookup by id — used to resolve entity_id → correct ticker/name
        // (d.companies joins on company_id which may be a partner, not the display entity)
        const companiesMap = new Map((companiesRows||[]).map(c => [c.id, c]));

        const seen = new Set();
        const drugs = (rows||[]).map(r=>r.drugs).filter(d => {
          if (!d || seen.has(d.id)) return false;
          seen.add(d.id);
          // Allow through drugs from acquired companies if current_owner_company_id is set
          // (e.g. Candid drugs rolling up under UCB after acquisition)
          if (d.companies?.status === 'acquired' && !d.current_owner_company_id) return false;
          return true;
        });
        this.data = drugs.map(d => {
          // Prefer area-specific score over global drug fields — this is the source of truth
          // for competitive tier within this tab's area context. Fall back to drugs table
          // globals only when no area score exists (e.g. newly added drug before enrichment).
          const score = areaScoreMap[d.id];
          // current_owner_company_id takes priority for acquisitions; entity_id for legacy
          // partnerships; company_id as fallback (the identity anchor, never changed)
          const ownerCoId = d.current_owner_company_id || d.entity_id || d.company_id;
          return {
          id:                   d.id,
          company_id:           d.company_id,
          entity_id:            ownerCoId || d.id,
          entity_name:          companiesMap.get(ownerCoId)?.name || d.entity_name || d.companies?.name || d.company_id || '—',
          entity_type:          d.entity_type || 'standalone',
          co:                   companiesMap.get(ownerCoId)?.name || d.companies?.name || d.company_id || '—',
          ticker:               companiesMap.get(ownerCoId)?.ticker || d.companies?.ticker || '',
          hq_city:              companiesMap.get(ownerCoId)?.hq_city  || d.companies?.hq_city  || '',
          hq_country:           companiesMap.get(ownerCoId)?.hq_country || d.companies?.hq_country || '',
          drug:                 d.brand_name ? d.brand_name + (d.name && d.name.toLowerCase() !== d.brand_name.toLowerCase() ? ` (${d.name})` : '') : d.name,
          name:                 d.name,
          target:               d.target || _piExtractTarget(d.mechanism) || '—',
          mechanism:            d.mechanism || '',
          cls:                  score?.cls    || d.cls || '1st Gen',
          stageKey:             _resolveStage(d),
          overlap:              score?.overlap || d.overlap || (d.ailux_competes_directly ? 'Direct' : 'Watch'),
          overlap_rationale:    score?.overlap_rationale || d.differentiation_thesis || '',
          vs_ailux:             score?.vs_ailux || '',
          competitive_relevance: score?.competitive_relevance || null,
          relevance_rationale:   score?.relevance_rationale || '',
          relevance_score_numeric: score?.relevance_score_numeric ?? null,
          score_breakdown_json:  score?.score_breakdown_json  ?? null,
          summary:              d.ailux_angle || d.key_data || '',
          stageDetail:          d.stage_detail || '',
          indication_short:     d.indication_short || '',
          drug_summary:         d.drug_summary || '',
          partner_company:        d.partner_company || null,
          partnership_type:       d.partnership_type || null,
          partnership_verified:   d.partnership_verified ?? null,
          licensor_name:          d.licensor_name || null,
          licensor_code:          d.licensor_code || null,
          current_owner_company_id: d.current_owner_company_id || null,
          originator_company_id:  d.originator_company_id || null,
          ownership_status:       d.ownership_status || null,
          display_partner_name:   d.display_partner_name || null,
          brand_name:             d.brand_name || null,
          display_name:           d.display_name || null,
          };
        });
        // Batch-fetch asset_transfer_history for all drugs in this area tab (Session 69).
        // Stored on `this` so _genericDetailHTML can access it per drug via this.athByDrugId[drugId].
        this.athByDrugId = {};
        try {
          const _athDrugIds = this.data.map(d => d.id).filter(Boolean);
          if (_athDrugIds.length) {
            const { data: _athRows } = await _sb.from('asset_transfer_history')
              .select('drug_id,sequence_order,from_entity_name,from_entity_id,to_entity_name,to_entity_id,transfer_type,geographic_scope,deal_value_notes,deal_value_upfront_usd,verified')
              .in('drug_id', _athDrugIds)
              .order('sequence_order', { ascending: true });
            (_athRows || []).forEach(r => {
              (this.athByDrugId[r.drug_id] = this.athByDrugId[r.drug_id] || []).push(r);
            });
          }
        } catch(_) {}

        // ── Coverage scores for this area (Connection 3) ──────────────────────
        this._covScoreMap = {};
        try {
          const _primaryArea = this.areaIds[0];
          const { data: _covRows } = await _sb
            .from('coverage_scores')
            .select('company_id, coverage_score:overall_score')
            .eq('area_slug', _primaryArea)
            .limit(200);
          (_covRows || []).forEach(s => { if (s.company_id) this._covScoreMap[s.company_id] = s.coverage_score; });
        } catch(_) {}

        this._buildEntities();
        this.filteredEntities = [...this.entities];
        this.loaded = true;
        this._renderPills();
        this._renderTable();
        this._loadEntityMeta(); // async — adds trials + catalysts + accurate counts
        // Phase 4B Path A — IBD dual-read (non-blocking, parallel only)
        if (this.areaIds.includes('ibd')) this._runPhase4BDualRead(scoreRows);
        // Phase 4B Path B — TL1A target-view dual-read (non-blocking, parallel only)
        if (this.areaIds.includes('tl1a')) this._runPhase4BTL1ADualRead(scoreRows);
        // Phase 4B Path C — TED indication-group dual-read (non-blocking, parallel only)
        if (this.areaIds.includes('igf1r')) this._runPhase4BTEDDualRead(scoreRows);
        // Phase 4B Paths D/E — Atopy dual-read: IL-4Rα + TSLP target-views (non-blocking)
        if (this.areaIds.includes('il4ra')) this._runPhase4BAtopyDualRead(scoreRows, 'il4ra', ['il4ra']);
        if (this.areaIds.includes('tslp'))  this._runPhase4BAtopyDualRead(scoreRows, 'tslp',  ['tslp','tslpr']);
        // Phase 4B Path F — FcRn target-view dual-read (non-blocking)
        if (this.areaIds.includes('fcrn')) this._runPhase4BFCRNDualRead(scoreRows);
      } catch(e) {
        const el2 = document.getElementById(this.tabId+'-area-pi');
        if (el2) el2.innerHTML = `<div style="color:#dc2626;font-size:12px;padding:16px">Error loading landscape: ${e.message}</div>`;
      }
    },

    _buildEntities() {
      const map = new Map();
      for (const prog of this.data) {
        const eid = prog.entity_id;
        if (!map.has(eid)) {
          map.set(eid, { entity_id:eid, company_id:prog.company_id, entity_name:prog.entity_name, entity_type:prog.entity_type, co:prog.co, ticker:prog.ticker, hq_city:prog.hq_city, hq_country:prog.hq_country, programs:[] });
        }
        map.get(eid).programs.push(prog);
      }
      this.entities = [...map.values()].map(ent => {
        const progs = ent.programs;
        const clsOrd = {'1st Gen':2,'2nd Gen':1,'Next Gen':0};
        const bestStage   = progs.reduce((b,p)=>(STAGE_ORDER_PI[p.stageKey]??9)<(STAGE_ORDER_PI[b]??9)?p.stageKey:b, progs[0]?.stageKey||'Preclinical');
        const bestCls     = progs.reduce((b,p)=>(clsOrd[p.cls]??3)<(clsOrd[b]??3)?p.cls:b, progs[0]?.cls||'1st Gen');
        const bestOverlap = progs.reduce((b,p)=>(OV_ORDER[p.overlap]??9)<(OV_ORDER[b]??9)?p.overlap:b, progs[0]?.overlap||'Watch');
        const leadProg    = progs.find(p=>p.stageKey===bestStage)||progs[0];
        const comboCount  = this.comboCountByCompany?.[ent.company_id || ent.entity_id] || 0;
        const totalPortfolioCount = progs.length + comboCount;
        const isTerminated = progs.every(p => p.stageKey === 'Terminated');
        const _RELEV_ORD  = {very_high:0,high:1,medium:2,low:3,monitor:4};
        const bestRelevanceProg = progs.reduce((b,p) =>
          (_RELEV_ORD[p.competitive_relevance]??9) < (_RELEV_ORD[b?.competitive_relevance]??9) ? p : b,
          progs[0] || {});
        const bestRelevance = bestRelevanceProg.competitive_relevance || null;
        const bestRelevanceRationale = bestRelevanceProg.relevance_rationale || '';
        // Numeric score: take the highest relevance_score_numeric across all programs
        const bestNumericProg = progs.reduce((b,p) => ((p.relevance_score_numeric??-1) > (b?.relevance_score_numeric??-1)) ? p : b, progs[0] || {});
        const bestNumericScore = bestNumericProg.relevance_score_numeric ?? null;
        const bestBreakdown    = bestNumericProg.score_breakdown_json    ?? null;
        return { ...ent, bestStage, bestCls, bestOverlap, bestRelevance, bestRelevanceRationale, bestNumericScore, bestBreakdown, isTerminated,
          target: leadProg?.target||'—',
          summary: progs.map(p=>p.summary).filter(Boolean)[0]||'',
          stageDetail: leadProg?.stageDetail||'',
          totalPortfolioCount };
      });
      this.entities.sort((a,b) => { if (a.isTerminated!==b.isTerminated) return a.isTerminated?1:-1; return 0; });
    },

    async _loadEntityMeta() {
      if (!_sb) return;
      try {
        const companyIds = [...new Set(this.data.map(p => p.company_id).filter(Boolean))];
        if (!companyIds.length) return;
        const today = new Date().toISOString().slice(0, 10);
        const companySet = new Set(companyIds);

        const [drugAreaRes, comboRes, catRes] = await Promise.all([
          this._atopyNorm
            ? _sb.from('drug_targets').select('drug_id,drugs(id,company_id,indication_short)').in('target_id', this._atopyTargets || []).limit(500)
            : this._tl1aNorm
              ? _sb.from('drug_targets').select('drug_id,drugs(id,company_id,indication_short)').eq('target_id', 'tl1a').limit(500)
              : this._ibdNorm
                ? _sb.from('drug_indications').select('drug_id,drugs(id,company_id,indication_short)').in('indication_id', ['uc','cd']).limit(500)
                : _sb.from('drug_areas').select('drugs(id,company_id,indication_short)').in('area_id', this.areaIds).limit(500),
          _sb.from('drug_combinations').select('company_id').in('area_id', this.areaIds).limit(300),
          _sb.from('catalysts').select('company_id,catalyst_date,sort_date').in('company_id', companyIds).eq('resolved', false).gte('sort_date', today).order('sort_date', { ascending: true }).limit(300),
        ]);

        const areaDrugs = (drugAreaRes.data||[]).map(r=>r.drugs).filter(d=>d && companySet.has(d.company_id));
        const combos = (comboRes.data||[]).filter(c=>companySet.has(c.company_id));
        const cats   = catRes.data || [];

        const drugIds = areaDrugs.map(d=>d.id);
        let trialRows = [];
        if (drugIds.length) {
          const { data: tr } = await _sb.from('trials').select('drug_id,status').in('drug_id', drugIds).limit(500);
          trialRows = tr || [];
        }

        const meta = {};
        const drugToCompany = {};
        areaDrugs.forEach(d => { drugToCompany[d.id] = d.company_id; });

        areaDrugs.forEach(d => {
          if (!meta[d.company_id]) meta[d.company_id] = { drugCount:0, indUC:false, indCD:false };
          meta[d.company_id].drugCount++;
          const ind = (d.indication_short||'').toUpperCase();
          if (/\bUC\b/.test(ind)||ind.includes('ULCERATIVE')) meta[d.company_id].indUC = true;
          if (/\bCD\b/.test(ind)||ind.includes('CROHN'))      meta[d.company_id].indCD = true;
          // Store first indication_short for non-IBD fallback
          if (!meta[d.company_id]._firstInd && d.indication_short) meta[d.company_id]._firstInd = d.indication_short;
        });
        combos.forEach(c => {
          if (!meta[c.company_id]) meta[c.company_id] = { drugCount:0, indUC:false, indCD:false };
          meta[c.company_id].drugCount++;
        });
        const _isTermMeta = s => /complet|terminat|withdrawn|suspend/i.test(s||'');
        trialRows.filter(t => !_isTermMeta(t.status)).forEach(t => {
          const cid = drugToCompany[t.drug_id];
          if (!cid) return;
          if (!meta[cid]) meta[cid] = {};
          meta[cid].activeTrials = (meta[cid].activeTrials||0) + 1;
        });
        const catSeen = new Set();
        cats.forEach(c => {
          if (!catSeen.has(c.company_id)) {
            catSeen.add(c.company_id);
            if (!meta[c.company_id]) meta[c.company_id] = {};
            meta[c.company_id].nextCatalyst = c.sort_date || c.catalyst_date;
          }
        });
        Object.keys(meta).forEach(cid => {
          const m = meta[cid];
          if (m.indUC && m.indCD) { m.indScope = 'UC+CD'; return; }
          if (m.indUC)            { m.indScope = 'UC';    return; }
          if (m.indCD)            { m.indScope = 'CD';    return; }
          // Non-IBD: derive from first known indication_short
          const raw = m._firstInd || '';
          if (raw) {
            m.indScope = raw
              .replace(/Chronic Obstructive Pulmonary Disease/gi,'COPD')
              .replace(/Atopic Dermatitis/gi,'AD').replace(/Rheumatoid Arthritis/gi,'RA')
              .replace(/Myasthenia Gravis/gi,'gMG').replace(/Thyroid Eye Disease/gi,'TED')
              .replace(/Systemic Lupus Erythematosus/gi,'SLE').replace(/Asthma/gi,'Asthma')
              .replace(/Chronic Spontaneous Urticaria/gi,'CSU').replace(/Eosinophilic Esophagitis/gi,'EoE')
              .replace(/Alopecia Areata/gi,'AA').replace(/Hidradenitis Suppurativa/gi,'HS')
              .replace(/Prurigo Nodularis/gi,'PN').replace(/Chronic Rhinosinusitis/gi,'CRS')
              .split(/[·,;—–]/)[0].trim().slice(0,18) || undefined;
          }
        });
        this._entityMeta = meta;
        this._renderTable();
      } catch(e) { /* silent — rows render without meta tokens if fetch fails */ }
    },

    filter() {
      const wrap = document.getElementById(this.tabId+'-area-pi-wrap');
      if (!wrap) return;
      const stage = wrap.querySelector('.pi-pill-group[data-filter="stage"] .pi-pill.active')?.dataset?.val||'';
      // Respect any active hier target/indication filter on top of stage pill
      const tgtName = this._hierFilterTarget || null;
      const indName = this._hierFilterInd || null;

      // Build O(1) drug-id sets from navigator_lookup when available (preferred)
      // Falls back to string-match when lookup hasn't loaded yet.
      let tgtDrugSet = null;
      let indDrugSet = null;
      const nav = window._navLookup;
      if (nav && tgtName) {
        // Find matching target_id(s) by label (case-insensitive)
        const tL = tgtName.toLowerCase();
        const matchedIds = Object.keys(nav.target_meta || {}).filter(id => {
          const m = nav.target_meta[id];
          return (m.label||'').toLowerCase() === tL
              || (m.full_name||'').toLowerCase().includes(tL)
              || id.toLowerCase() === tL.replace(/[^a-z0-9]/g,'_');
        });
        if (matchedIds.length > 0) {
          tgtDrugSet = new Set();
          matchedIds.forEach(id => (nav.target_drugs[id] || []).forEach(d => tgtDrugSet.add(d)));
        }
      }
      if (nav && indName && !tgtName) {
        const iL = indName.toLowerCase();
        const matchedIds = Object.keys(nav.indication_meta || {}).filter(id => {
          const m = nav.indication_meta[id];
          return (m.name||'').toLowerCase() === iL
              || (m.abbreviation||'').toLowerCase() === iL
              || id.toLowerCase() === iL.replace(/[^a-z0-9]/g,'_');
        });
        if (matchedIds.length > 0) {
          indDrugSet = new Set();
          matchedIds.forEach(id => (nav.indication_drugs[id] || []).forEach(d => indDrugSet.add(d)));
        }
      }

      this.filteredEntities = this.entities
        .map(ent => {
          let progs = ent.programs;
          if (stage) progs = progs.filter(p => p.stageKey === stage);
          if (tgtName) {
            if (tgtDrugSet) {
              // Precise lookup: keep programs whose drug_id is in the set
              progs = progs.filter(p => tgtDrugSet.has(p.drug_id || p.id || ''));
              // If no drug_id match, fall back to string-match (safety net for inline drugs)
              if (progs.length === 0) {
                const tL = tgtName.toLowerCase();
                progs = ent.programs.filter(p =>
                  (stage ? p.stageKey === stage : true) &&
                  ((p.target||'').toLowerCase().includes(tL) || (p.name||'').toLowerCase().includes(tL))
                );
              }
            } else {
              const tL = tgtName.toLowerCase();
              progs = progs.filter(p => (p.target||'').toLowerCase().includes(tL) || (p.name||'').toLowerCase().includes(tL));
            }
          }
          if (indName && !tgtName) {
            if (indDrugSet) {
              progs = progs.filter(p => indDrugSet.has(p.drug_id || p.id || ''));
              if (progs.length === 0) {
                const iL = indName.toLowerCase();
                progs = ent.programs.filter(p =>
                  (stage ? p.stageKey === stage : true) &&
                  (p.indication_short||'').toLowerCase().includes(iL)
                );
              }
            } else {
              const iL = indName.toLowerCase();
              progs = progs.filter(p => (p.indication_short||'').toLowerCase().includes(iL));
            }
          }
          return progs.length > 0 ? {...ent, programs: progs} : null;
        })
        .filter(Boolean);
      const cnt = document.getElementById(this.tabId+'-area-pi-count');
      if (cnt) cnt.textContent = `${this.filteredEntities.length} entities`;
      this._renderTable();
    },

    // Apply a target (and/or indication) filter from the navigator hierarchy.
    // targetName = null resets all hier filters and restores the full entity list.
    applyTargetFilter(targetName, indicationName) {
      this._hierFilterTarget = targetName || null;
      this._hierFilterInd    = indicationName || null;
      this.filter(); // re-runs combined stage + target + indication filter
    },

    sort(col) {
      if (this.sortCol===col) this.sortDir*=-1; else { this.sortCol=col; this.sortDir=1; }
      this._renderTable();
    },

    toggle(id) {
      const expanding = !this.expanded.has(id);
      if (this.expanded.has(id)) this.expanded.delete(id); else this.expanded.add(id);
      this._renderTable();
      if (expanding) {
        const ent = this.entities.find(e => e.entity_id === id);
        if (ent && !this._profileCache[id] && this._profileCache[id] !== null) {
          this._loadDynamicDetail(id, ent);
        }
      }
    },

    _renderPills() {
      const wrap = document.getElementById(this.tabId+'-area-pi-wrap');
      if (!wrap) return;
      const stages = [...new Set(this.data.map(p=>p.stageKey))].sort((a,b)=>(STAGE_ORDER_PI[a]??9)-(STAGE_ORDER_PI[b]??9));
      const tid = this.tabId;
      const pillBtn = (grp,val,lbl) => `<button class="pi-pill" data-val="${val}" onclick="_areaPIPill('${tid}','${grp}','${val}',this)">${lbl||val}</button>`;
      const pillsEl = wrap.querySelector('.pi-pills-wrap');
      if (!pillsEl) return;
      pillsEl.innerHTML = `
        <div class="pi-pill-group" data-filter="stage">
          <span class="pi-pill-lbl">Stage</span>
          <button class="pi-pill active" data-val="" onclick="_areaPIPill('${tid}','stage','',this)">All</button>
          ${stages.map(s=>pillBtn('stage',s)).join('')}
        </div>
        <span id="${tid}-area-pi-count" style="font-size:11px;color:#64748b;padding-left:6px;white-space:nowrap;flex-shrink:0"></span>`;
    },

    _clsPill(c)  {
      const norm={'1st gen':'1st Gen','2nd gen':'2nd Gen','next gen':'Next Gen','1stgen':'1st Gen','2ndgen':'2nd Gen','nextgen':'Next Gen'};
      const canon = norm[(c||'').toLowerCase()] || c || '1st Gen';
      const m={'1st Gen':'pi-cls-1st','2nd Gen':'pi-cls-2nd','Next Gen':'pi-cls-next'};
      return `<span class="pi-cls-pill ${m[canon]||'pi-cls-1st'}">${canon}</span>`;
    },
    _stagePill(s){ if(s==='Terminated') return `<span class="pi-stage-pill pi-stage-terminated">Terminated</span>`; const m={Approved:'pi-stage-approved','Phase 3':'pi-stage-ph3','Phase 2':'pi-stage-ph2','Phase 1':'pi-stage-ph1','Pre-IND':'pi-stage-pre',Preclinical:'pi-stage-pre','Planned Ph2b':'pi-stage-planned','Planned Ph1':'pi-stage-planned','Planned Phase 2':'pi-stage-planned','Planned Phase 1':'pi-stage-planned',Observational:'pi-stage-obs','Expanded Access':'pi-stage-comp'}; const lbl={'Observational':'Obs.','Expanded Access':'Comp. Use'}; const cls=m[s]||(s&&s.startsWith('Planned')?'pi-stage-planned':'pi-stage-pre'); return `<span class="pi-stage-pill ${cls}">${lbl[s]||s||'—'}</span>`; },
    _ovBadge(o)  {
      const norm={direct:'Direct',adjacent:'Adjacent','same-space':'Same-Space','same_space':'Same-Space',samespace:'Same-Space',watch:'Watch'};
      const canon = norm[(o||'').toLowerCase()] || o || 'Watch';
      const m={Direct:'pi-overlap-direct',Adjacent:'pi-overlap-adjacent','Same-Space':'pi-overlap-same',Watch:'pi-overlap-watch'};
      return `<span class="pi-overlap-badge ${m[canon]||'pi-overlap-watch'}">${canon}</span>`;
    },
    _etypeBadge(t) {
      if (t==='standalone') return '';
      const m={platform:'pi-etype-platform',partnership:'pi-etype-partnership',licensed:'pi-etype-licensed'};
      const l={platform:'Platform',partnership:'Partnership',licensed:'Licensed'};
      return `<span class="pi-etype-badge ${m[t]||''}">${l[t]||t}</span>`;
    },
    _relevBadge(r, rationale) {
      if (!r) return '';
      const cfg = {
        very_high: { cls:'pi-relev-veryhigh', lbl:'Very High' },
        high:      { cls:'pi-relev-high',     lbl:'High'      },
        medium:    { cls:'pi-relev-medium',   lbl:'Medium'    },
        low:       { cls:'pi-relev-low',      lbl:'Low'       },
        monitor:   { cls:'pi-relev-monitor',  lbl:'Monitor'   },
      };
      const { cls, lbl } = cfg[r] || { cls:'pi-relev-monitor', lbl:r };
      const tip = rationale ? ` title="${rationale.replace(/"/g,'&quot;')}"` : '';
      return `<span class="pi-relev-badge ${cls}"${tip}>${lbl}</span>`;
    },

    _numericRelevColor(n) {
      return n >= 9 ? {fg:'#dc2626',bg:'#fee2e2'} : n >= 7 ? {fg:'#ea580c',bg:'#ffedd5'} : n >= 5 ? {fg:'#d97706',bg:'#fef3c7'} : n >= 3 ? {fg:'#64748b',bg:'#f1f5f9'} : {fg:'#94a3b8',bg:'#f8fafc'};
    },

    _numericRelevPill(score, breakdown) {
      if (score == null) return '<span style="font-size:10px;color:#94a3b8">—</span>';
      const n = parseFloat(score);
      const {fg, bg} = this._numericRelevColor(n);
      const bAttr = breakdown ? ` data-breakdown='${JSON.stringify(breakdown).replace(/'/g,"&#39;")}'` : '';
      return `<span class="pi-numeric-relev" style="background:${bg};color:${fg};border-radius:6px;padding:2px 8px;font-size:11px;font-weight:800;cursor:pointer;white-space:nowrap;letter-spacing:0.01em" onclick="event.stopPropagation();_piShowRelevExplain(this,${n})"${bAttr}>${n.toFixed(1)}</span>`;
    },

    _entityDetailHTML(ent) {
      const eid = ent.entity_id;
      // If already cached, render full detail inline (no flicker on re-render)
      if (this._profileCache[eid] !== undefined) {
        const compatProg = this._makeCompatProg(ent);
        if (this._profileCache[eid] !== null) {
          try { return this._genericDetailHTML(compatProg, this._profileCache[eid], this.tabId); }
          catch(e) { console.error('[areaPI] cached render error:', e); }
        }
        // null cache = load failed, show fallback
        return this._entityDetailFallback(ent);
      }
      // Loading placeholder — _loadDynamicDetail() replaces this div with live data
      return `<div class="pi-detail-inner" id="pi-dyn-${eid}" style="display:block;padding:28px 16px;text-align:center">
        <span style="color:#94a3b8;font-size:12px;font-style:italic">⟳ Loading company intelligence...</span>
      </div>`;
    },

    _makeCompatProg(ent) {
      const leadProg = ent.programs.reduce((b,p) => {
        const ord = {Approved:0,'Phase 3':1,'Phase 2':2,'Phase 1':3,'Pre-IND':4,Preclinical:5};
        return (ord[p.stageKey]??9) < (ord[b.stageKey]??9) ? p : b;
      }, ent.programs[0] || {});
      return { ...leadProg, id: ent.company_id || ent.entity_id,
        co: ent.entity_name, ticker: ent.ticker,
        hq_city: ent.hq_city, hq_country: ent.hq_country,
        company_id: ent.company_id || ent.entity_id, _groupEntries: ent.programs };
    },

    _entityDetailFallback(ent) {
      let html = '';
      if (ent.programs.length > 0) {
        const bubbles = ent.programs.map(p =>
          `<div class="pi-prog-bubble"><span class="pi-prog-name">${p.brand_name || p.name}</span>${p.brand_name && p.name && p.name.toLowerCase() !== p.brand_name.toLowerCase() ? '<span class="drug-molecule-name">' + p.name + '</span>' : ''}
            ${this._stagePill(p.stageKey)} ${this._clsPill(p.cls)}
            ${p.target!=='—'?`<span class="pi-prog-target">${p.target}</span>`:''}
            ${this._ovBadge(p.overlap)}
          </div>`).join('');
        html += `<div class="pi-prog-bubbles">${bubbles}</div>`;
      }
      if (ent.summary)     html += `<p style="font-size:12px;line-height:1.6;color:#1e3a5f;margin:6px 0">${ent.summary}</p>`;
      if (ent.stageDetail) html += `<p style="font-size:11px;color:#475569;margin:0">${ent.stageDetail}</p>`;
      return html || '<span style="color:#94a3b8;font-size:11px">No detail available.</span>';
    },

    async _loadDynamicDetail(entityId, ent) {
      if (!_sb) { this._profileCache[entityId] = null; return; }
      const companyId = entityId; // entity_id is the display entity; company_id may be a partner/co-developer
      const AREA = this.areaIds[0] || 'tslp';
      try {
        // Company profile for this area
        const { data: profileRows } = await _sb.from('company_profiles').select('*')
          .eq('company_id', companyId).or(`target_id.eq.${AREA},area_id.eq.${AREA}`)
          .order('updated_at', { ascending: false }).limit(1);
        const profile = profileRows?.[0] || null;

        // Catalysts
        const { data: cats } = await _sb.from('catalysts').select('*')
          .eq('company_id', companyId).eq('area_id', AREA)
          .eq('resolved', false).order('sort_date', { ascending: true }).limit(20);

        // Deals + intel news
        let { data: deals } = await _sb.from('deals').select('*')
          .eq('company_id', companyId)
          .order('deal_date', { ascending: false }).limit(20);
        if (!deals || !deals.length) {
          const coName = (ent.entity_name||'').split('/')[0].trim().substring(0,14);
          const { data: d2 } = await _sb.from('deals').select('*')
            .or(`from_company.ilike.*${coName}*,to_company.ilike.*${coName}*`)
            .order('deal_date', { ascending: false }).limit(20);
          deals = d2 || [];
        }
        let intelNews = [];
        try {
          const { data: icRows } = await _sb.from('intel_companies').select('intel_id').eq('company_id', companyId).limit(20);
          if (icRows?.length) {
            const intelIds = icRows.map(r => r.intel_id);
            const { data: intelRows } = await _sb.from('intel').select('id,intel_date,headline,body,source_url')
              .in('id', intelIds).order('intel_date', { ascending: false }).limit(10);
            intelNews = (intelRows||[]).map(i => ({
              _source: 'intel', deal_date: i.intel_date,
              deal_date_label: i.intel_date ? i.intel_date.slice(0,10) : '',
              headline: i.headline, detail: (i.body||'').slice(0,200),
              source_url: i.source_url, deal_type: 'news',
            }));
          }
        } catch(_) {}
        const allNews = [...(deals||[]), ...intelNews]
          .filter((item, idx, arr) => arr.findIndex(x => (x.headline||'').slice(0,40) === (item.headline||'').slice(0,40)) === idx)
          .sort((a,b) => (b.deal_date||'').localeCompare(a.deal_date||''));

        // Drugs for this company in this area — including acquired/licensed assets via ownership_edges
        const [drugAreaRes2, controlledEdgesRes2] = await Promise.all([
          _sb.from('drug_areas').select('drug_id').eq('area_id', AREA),
          _sb.from('ownership_edges').select('subject_id,object_id')
             .eq('predicate', 'CONTROLLED_BY').eq('subject_type', 'drug')
             .eq('object_id', companyId).eq('status', 'active'),
        ]);
        const areaSet = new Set((drugAreaRes2.data||[]).map(r => r.drug_id));
        const controlledDrugIds2 = (controlledEdgesRes2.data||[]).map(r => r.subject_id);
        // Fetch originator names for controlled drugs (originator pill in dossier)
        const originatorMap2 = {};
        if (controlledDrugIds2.length) {
          const { data: origEdges2 } = await _sb.from('ownership_edges').select('subject_id,object_id')
            .eq('predicate', 'ORIGINATED_BY').eq('subject_type', 'drug')
            .in('subject_id', controlledDrugIds2).eq('status', 'active');
          (origEdges2||[]).forEach(e => { originatorMap2[e.subject_id] = e.object_id; });
        }
        const origNameMap2 = {};
        const origIds2 = [...new Set(Object.values(originatorMap2))];
        if (origIds2.length) {
          const { data: coRows2 } = await _sb.from('companies').select('id,name').in('id', origIds2);
          (coRows2||[]).forEach(c => { origNameMap2[c.id] = (c.name||'').split(' ')[0] || c.id; });
        }
        // Anchor on entity's actual programs (matching entity row grouping) + controlled drugs + co-dev drugs
        // This prevents cross-entity bleed (e.g. Simcere's company_id drugs showing under BI's entity)
        const programIds = (ent?.programs || []).map(p => p.id);
        const allDrugIds = [...new Set([...programIds, ...controlledDrugIds2])];
        // co_developer_ids / lead_company_id OR clause for co-dev drugs
        const _codevFilter2 = `co_developer_ids.cs.{${companyId}}`;
        const _leadFilter2  = `lead_company_id.eq.${companyId}`;
        const idsToFetch2 = allDrugIds.length
          ? `id.in.(${allDrugIds.join(',')}),company_id.eq.${companyId},${_leadFilter2},${_codevFilter2}`
          : `company_id.eq.${companyId},${_leadFilter2},${_codevFilter2}`;
        const { data: allCoDrugs } = await _sb.from('drugs').select('*')
          .or(idsToFetch2).order('sort_order', { ascending: true }).limit(30);
        const drugs = (allCoDrugs||[]).filter(d => {
          const isCtrl = controlledDrugIds2.includes(d.id) && d.company_id !== companyId;
          const isCoDev2 = d.company_id !== companyId
            && (Array.isArray(d.co_developer_ids) && d.co_developer_ids.includes(companyId)
                || d.lead_company_id === companyId);
          if (!areaSet.has(d.id) && !isCtrl && !isCoDev2) return false;
          if (isCtrl) {
            const origName2 = (originatorMap2[d.id] ? origNameMap2[originatorMap2[d.id]] : null)
              || d.display_partner_name || null;
            d._originator_name = origName2;
            d.partner_company  = origName2;
            d.licensor_name    = null;
            d.entity_name      = null;
            d.partnership_verified = true;
          }
          if (isCoDev2 && !isCtrl) {
            d._is_codev = true;
            d._codev_originator = d.company_id;
          }
          return true;
        });

        // Trials
        let trials = [];
        for (const d of drugs.slice(0, 8)) {
          const { data: tt } = await _sb.from('trials').select('*').eq('drug_id', d.id);
          if (tt) trials.push(...tt);
        }

        // Combos + combo trials
        let combos = [];
        try {
          const { data: comboRows } = await _sb.from('drug_combinations').select('*')
            .eq('company_id', companyId).eq('area_id', AREA)
            .order('strategic_significance', { ascending: true });
          const comboSeen = new Set();
          combos = (comboRows||[]).filter(c => {
            const key = (c.label||'').toLowerCase().replace(/\s*[\(\[].*?[\)\]]/g,'').replace(/\s+/g,' ').trim();
            if (comboSeen.has(key)) return false; comboSeen.add(key); return true;
          });
          const comboIds = combos.map(c => c.id).filter(Boolean);
          if (comboIds.length) {
            const { data: ctr } = await _sb.from('trials').select('*').in('combination_id', comboIds);
            if (ctr?.length) trials.push(...ctr);
          }
        } catch(_) {}

        // Molecule intelligence — keyed by drug_id, area-agnostic
        let moleculeIntel = {};
        try {
          const drugIds = drugs.map(d => d.id).filter(Boolean);
          if (drugIds.length) {
            const { data: molRows } = await _sb.from('molecule_intelligence')
              .select('*').in('drug_id', drugIds);
            if (molRows?.length) {
              molRows.forEach(m => { moleculeIntel[m.drug_id] = m; });
            }
          }
        } catch(_) {}

        // Competitive signals for this company × area
        let competitiveSignals = [];
        try {
          const { data: sigRows } = await _sb.from('competitive_signals')
            .select('id,signal_type,title,description,source_url,source_date,drug_id,confidence,area_id,target_id')
            .eq('company_id', companyId).or(`target_id.eq.${AREA},area_id.eq.${AREA}`)
            .order('source_date', { ascending: false }).limit(10);
          competitiveSignals = sigRows || [];
        } catch(_) {}

        // Recent news_articles for this company — feeds "Recent Coverage" in drug row dropdowns.
        // Fetches articles where matched_company_ids contains companyId (set by fetch_homepage_news.py).
        // 90-day window, relevance ≥ 25, invalid URLs excluded. Up to 20 articles shared across all
        // drugs for this company; each drug row filters / prioritises its own relevant subset.
        let newsArticles = [];
        try {
          const _90dAgo = new Date(Date.now() - 90*24*60*60*1000).toISOString().slice(0,10);
          const { data: naRows } = await _sb.from('news_articles')
            .select('id,headline,source_name,published_at,article_url,matched_company_ids,matched_drug_ids,relevance_score,meridian_summary,why_it_matters')
            .contains('matched_company_ids', [companyId])
            .gte('published_at', _90dAgo)
            .neq('source_validation_status', 'invalid')
            .order('relevance_score', { ascending: false })
            .limit(20);
          newsArticles = naRows || [];
        } catch(_) {}

        const sbData = { profile, catalysts: cats||[], deals: allNews, drugs, trials, combos, moleculeIntel, competitiveSignals, newsArticles, athByDrugId: this.athByDrugId || {} };
        this._profileCache[entityId] = sbData;

        // Replace loading placeholder with full rendering
        const target = document.getElementById(`pi-dyn-${entityId}`);
        if (target) {
          try {
            target.outerHTML = this._genericDetailHTML(this._makeCompatProg(ent), sbData, this.tabId);
          } catch(renderErr) {
            console.error('[areaPI] render error:', renderErr);
            target.outerHTML = `<div class="pi-detail-inner" style="display:block;padding:14px 16px">${this._entityDetailFallback(ent)}</div>`;
          }
        }
      } catch(err) {
        console.warn('[areaPI] _loadDynamicDetail error:', err);
        this._profileCache[entityId] = null;
        const target = document.getElementById(`pi-dyn-${entityId}`);
        if (target) target.outerHTML = `<div class="pi-detail-inner" style="display:block;padding:14px 16px">${this._entityDetailFallback(ent)}</div>`;
      }
    },

    _nextGenRanks(sorted, tid) {
      // ALL entities ranked in one unified sequential system.
      // Next-gen (bispecifics) and first-gen (monospecifics) are ranked separately
      // within their groups — ranks continue sequentially so every entity has a number.
      // Scores from actual DB values (drug_competitive_scores) refined over time by enrichment.
      // Every rank is written to next_gen_rankings table — permanent historical record.
      const AILUX_PROGS = {
        tl1a:{ drug:'ALX001', target:'TL1A × IL-23p19', ind:'UC; CD; Psoriasis' },
        ibd: { drug:'ALX001', target:'TL1A × IL-23p19', ind:'UC; CD; Psoriasis' },
        fcrn:{ drug:'ALX005', target:'FcRn × Albumin',  ind:'gMG; CIDP'         },
      };
      const aKey = Object.keys(AILUX_PROGS).find(k => tid.includes(k));
      const ap   = aKey ? AILUX_PROGS[aKey] : null;
      // All entities participate — Ailux uses dev-progress score, others use competitive score
      const ng   = sorted.filter(e => e.bestCls === 'Next Gen' && !e.isTerminated);
      const fg   = sorted.filter(e => e.bestCls !== 'Next Gen' && !e.isTerminated);
      if (!ng.length && !fg.length && !ap) return { rankMap:{}, ailuxProg:null, hasNextGen:false, ailuxEntry:null };

      // Score: 70% drug_competitive_scores.total_competition_score (enrichment pipeline)
      //      + 30% stage signal (drugs.stage). As 100Q fills in, enrichment incorporates it.
      const STAGE_W = {approved:10,approved_us:10,approved_eu:10,bla_under_review:9.5,
        'Phase 3':9,'Phase 2/3':8.5,'Phase 2':8,'Phase 1/2':7,'Phase 1':6,
        'IND filed':4,'IND-enabling':2.5,'Preclinical':1,'Terminated':0};
      const composite = (e) => ((e.bestNumericScore ?? 0) * 0.7) + ((STAGE_W[e.bestStage] ?? 0) * 0.3);

      // Ailux participates as a real DB entity — no synthetic creation.
      // Development-progress score: how far along is Ailux vs competitors?
      // Stage-based so it climbs naturally as ALX001 advances through clinical milestones.
      const AILUX_DEV_SC = {approved:50,approved_us:50,bla_under_review:45,
        'Phase 3':40,'Phase 2/3':37,'Phase 2':35,'Phase 1':20,
        'IND filed':12,'IND-enabling':7,'Preclinical':3,'Terminated':0};

      let ngCandidates = ng.map(e => {
        const isAilux = e.company_id === 'ailux';
        // Ailux: scored by development stage (not competitive relevance — it has no score against itself)
        // Everyone else: scored by actual DB value from drug_competitive_scores
        const sc = isAilux ? (AILUX_DEV_SC[e.bestStage] || 3) : composite(e);
        return { id:e.entity_id, ent:e, sc, stage:e.bestStage, relev:e.bestRelevance, isAilux, isNg:true };
      });
      const ailuxEnt = ng.find(e => e.company_id === 'ailux') || null;
      ngCandidates.sort((a,b) => Math.abs(b.sc-a.sc)>0.01 ? b.sc-a.sc : (STAGE_W[b.stage]??0)-(STAGE_W[a.stage]??0));

      // Score first-gen candidates (continue numbering after next-gen)
      let fgCandidates = fg.map(e => { const isAilux=e.company_id==='ailux'; const sc=isAilux?(AILUX_DEV_SC[e.bestStage]||3):composite(e); return { id:e.entity_id, ent:e, sc, stage:e.bestStage, relev:e.bestRelevance, isAilux, isNg:false }; });
      fgCandidates.sort((a,b) => Math.abs(b.sc-a.sc)>0.01 ? b.sc-a.sc : (STAGE_W[b.stage]??0)-(STAGE_W[a.stage]??0));

      // Assign sequential ranks: next-gen 1..N, then first-gen N+1..M
      const rankMap = {};
      let rank = 1;
      [...ngCandidates, ...fgCandidates].forEach(c => {
        rankMap[c.id] = { rank, score:c.sc, stage:c.stage, relev:c.relev, isAilux:c.isAilux, isNg:c.isNg, ent:c.ent };
        rank++;
      });

      // Movement arrows: compare to localStorage snapshot from last visit
      let prev = {};
      try { prev = JSON.parse(localStorage.getItem('ngRk_'+tid) || '{}'); } catch(e){}
      Object.entries(rankMap).forEach(([id,r]) => {
        const p = prev[id];
        if (!p)           r.move='new';
        else if(r.rank<p) { r.move='up';   r.delta=p-r.rank; }
        else if(r.rank>p) { r.move='down'; r.delta=r.rank-p; }
        else              r.move='same';
      });
      // Save to localStorage for session-level movement (browser only).
      // DB history is written by competitive_scoring.py (enrichment pipeline) — not the browser.
      // The browser is READ-ONLY from next_gen_rankings: fetches yesterday's snapshot for arrows.
      try { const s={}; Object.entries(rankMap).forEach(([id,r])=>{s[id]=r.rank;}); localStorage.setItem('ngRk_'+tid,JSON.stringify(s)); } catch(e){}

      return { rankMap, ailuxProg:ap, hasNextGen:ng.length>0, ailuxEntry:ailuxEnt };
    },

    _rankCell(info) {
      // Centered rank indicator: medal only for 1-2-3, number for 4+, dash if no movement
      if (!info) return '<td class="pi-rank-cell"></td>';
      const { rank, move, isAilux } = info;
      // Top 3: medal emoji only (no number). 4+: plain gray number. Ailux: ★
      let top;
      if (isAilux)    top = '<span class="pi-rk-num pi-rk-home" style="font-size:11px">★</span>';
      else if (rank===1) top = '<span class="pi-rk-medal">🥇</span>';
      else if (rank===2) top = '<span class="pi-rk-medal">🥈</span>';
      else if (rank===3) top = '<span class="pi-rk-medal">🥉</span>';
      else               top = '<span class="pi-rk-num">'+rank+'</span>';
      // Arrow or dash placeholder
      const mv = move==='up'   ? '<span class="pi-move-up">↑</span>'
               : move==='down' ? '<span class="pi-move-dn">↓</span>'
               : '<span class="pi-move-dash">—</span>';
      return '<td class="pi-rank-cell"><span class="pi-rk-wrap">'+top+mv+'</span></td>';
    },

    _renderTable() {
      const el = document.getElementById(this.tabId+'-area-pi');
      if (!el) return;
      const cnt = document.getElementById(this.tabId+'-area-pi-count');
      const tid = this.tabId;
      const clsOrd = {'1st Gen':2,'2nd Gen':1,'Next Gen':0};

      const _RELEV_ORD_SORT = {very_high:0,high:1,medium:2,low:3,monitor:4};
      const sorted = [...this.filteredEntities].sort((a,b)=>{
        let av,bv;
        if (this.sortCol==='relevance') {
          // Numeric score: sort descending (highest first); nulls last; stage as tiebreaker
          const an = a.bestNumericScore ?? -1;
          const bn = b.bestNumericScore ?? -1;
          if (an !== bn) return this.sortDir * (bn - an);
          return (STAGE_ORDER_PI[a.bestStage]??9) - (STAGE_ORDER_PI[b.bestStage]??9);
        }
        if      (this.sortCol==='co')      { av=a.entity_name; bv=b.entity_name; }
        else if (this.sortCol==='cls')     { av=clsOrd[a.bestCls]??3; bv=clsOrd[b.bestCls]??3; }
        else if (this.sortCol==='stage')   { av=STAGE_ORDER_PI[a.bestStage]??9; bv=STAGE_ORDER_PI[b.bestStage]??9; }
        else if (this.sortCol==='overlap') { av=OV_ORDER[a.bestOverlap]??9; bv=OV_ORDER[b.bestOverlap]??9; }
        else { av=a[this.sortCol]||''; bv=b[this.sortCol]||''; }
        if (typeof av==='string') return this.sortDir*av.localeCompare(bv);
        return this.sortDir*(av-bv);
      });
      sorted.sort((a,b) => { if (a.isTerminated!==b.isTerminated) return a.isTerminated?1:-1; return 0; });

      // ── Generation race ─────────────────────────────────────────────────────
      const { rankMap, ailuxProg, hasNextGen, ailuxEntry } = this._nextGenRanks(sorted, tid);
      const showRace = hasNextGen || !!ailuxProg;

      // Build display list: inject separators + Ailux at correct rank position
      let displayList = sorted;
      if (showRace) {
        // Ailux participates like all other entities — no filtering
        const ng = sorted.filter(e => e.bestCls === 'Next Gen' && !e.isTerminated);
        const fg = sorted.filter(e => e.bestCls !== 'Next Gen' || e.isTerminated);
        // Sort ng by rank — Ailux is already in ngSorted at its correct position
        const ngSorted = [...ng].sort((a,b) => (rankMap[a.entity_id]?.rank??99)-(rankMap[b.entity_id]?.rank??99));
        const ngFinal  = ngSorted;  // Ailux participates naturally, no injection needed
        const ngCount  = ngFinal.length;
        const _ailuxRealEnt = ng.find(e => e.company_id === 'ailux');
        const ailuxPos = _ailuxRealEnt ? rankMap[_ailuxRealEnt.entity_id]?.rank : null;
        const fgStart  = ngCount + 1;
        // Sort fg by their assigned rank so numbers appear in sequence
        const fgSorted = [...fg].sort((a,b) => (rankMap[a.entity_id]?.rank??99)-(rankMap[b.entity_id]?.rank??99));
        displayList = [
          { _sep:'ng', _label:'🧬 Next-Gen · '+ngCount+' programs'+(ailuxPos?' · Ailux #'+ailuxPos:'') },
          ...ngFinal,
          ...(fgSorted.length ? [{ _sep:'fg', _label:'🔬 First-Gen · #'+fgStart+'–'+(fgStart+fgSorted.length-1)+' · Sets the efficacy bar' }] : []),
          ...fgSorted
        ];
      }

      if (cnt) cnt.textContent = `${sorted.length} entities`;
      if (!sorted.length) {
        el.innerHTML = '<div style="padding:24px;text-align:center;color:#94a3b8;font-size:12px">No programs match the current filters.</div>';
        return;
      }

      const rows = displayList.map(ent => {
        if (ent._sep) { const cs=showRace?8:7; return `<tr class="pi-gen-sep pi-gen-${ent._sep}"><td colspan="${cs}">${ent._label}</td></tr>`; }
        const isExp = this.expanded.has(ent.entity_id);
        const meta         = this._entityMeta?.[ent.company_id] || this._entityMeta?.[ent.entity_id] || {};
        const drugCount    = ent.programs.length || meta.drugCount || ent.totalPortfolioCount || 0;  // programs.length = actual rendered rows (includes partner drugs grouped under entity)
        const activeTrials = meta.activeTrials != null ? meta.activeTrials : null;
        const nextCat      = meta.nextCatalyst || null;

        const indScope = meta.indScope || (() => {
          const inds = ent.programs.map(p=>(p.indication_short||'').toUpperCase()).join(' ');
          const hasUC = /\bUC\b/.test(inds)||inds.includes('ULCERATIVE');
          const hasCD = /\bCD\b/.test(inds)||inds.includes('CROHN');
          if (hasUC && hasCD) return 'UC+CD';
          if (hasUC) return 'UC';
          if (hasCD) return 'CD';
          // Non-IBD tabs: abbreviate first program's indication_short
          const raw = ent.programs.map(p=>p.indication_short).filter(Boolean)[0] || '';
          if (!raw) return null;
          return raw
            .replace(/Chronic Obstructive Pulmonary Disease/gi,'COPD')
            .replace(/Atopic Dermatitis/gi,'AD').replace(/Rheumatoid Arthritis/gi,'RA')
            .replace(/Myasthenia Gravis/gi,'gMG').replace(/Thyroid Eye Disease/gi,'TED')
            .replace(/Systemic Lupus Erythematosus/gi,'SLE').replace(/Asthma/gi,'Asthma')
            .replace(/Chronic Spontaneous Urticaria/gi,'CSU').replace(/Eosinophilic Esophagitis/gi,'EoE')
            .replace(/Alopecia Areata/gi,'AA').replace(/Hidradenitis Suppurativa/gi,'HS')
            .replace(/Prurigo Nodularis/gi,'PN').replace(/Chronic Rhinosinusitis/gi,'CRS')
            .split(/[·,;—–]/)[0].trim().slice(0,18) || null;
        })();

        const trialsToken = activeTrials != null
          ? `<span style="font-size:10px;color:#475569;white-space:nowrap;background:#f8fafc;border:1px solid #e2e8f0;border-radius:5px;padding:1px 5px;margin-left:4px">${activeTrials} trial${activeTrials!==1?'s':''}</span>`
          : '';
        const pipelineCell = `<div style="display:flex;flex-wrap:wrap;align-items:center;gap:2px"><span style="font-size:12px;font-weight:700;color:#1e3a5f">${drugCount}</span><span style="font-size:10px;color:#94a3b8;font-weight:400"> drug${drugCount!==1?'s':''}</span>${trialsToken}</div>`;

        const indCell = indScope
          ? `<span style="font-size:9px;background:#f0f9ff;color:#0369a1;border:1px solid #bae6fd;border-radius:8px;padding:2px 7px;font-weight:700;white-space:nowrap;display:inline-block">${indScope}</span>`
          : `<span style="font-size:10px;color:#cbd5e1">—</span>`;

        // Always show a relevance pill for active companies; fall back to 'low' if no score
        const _effectiveRelev = ent.bestRelevance || (ent.isTerminated ? null : 'low');
        const relevBadge = this._relevBadge(_effectiveRelev, ent.bestRelevanceRationale);
        // Numeric score pill (replaces word pill as primary display)
        const numericPill = this._numericRelevPill(ent.bestNumericScore, ent.bestBreakdown);
        const threatCell = ent.isTerminated
          ? `<span style="color:#cbd5e1">—</span>`
          : numericPill;

        const catFmt = (() => {
          if (!nextCat) return null;
          if (/^\d{4}-\d{2}-\d{2}/.test(nextCat)) {
            const d = new Date(nextCat + 'T12:00:00Z');
            if (!isNaN(d)) return d.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'});
          }
          return nextCat;
        })();
        const catContent = catFmt
          ? `<span style="font-size:9px;color:#b45309;font-weight:700;white-space:nowrap;background:#fffbeb;border:1px solid #fde68a;border-radius:5px;padding:2px 6px">${catFmt}</span>`
          : `<span style="font-size:10px;color:#cbd5e1">—</span>`;
        const catCell = `<div style="display:flex;align-items:center;justify-content:space-between;gap:4px">${catContent}<span class="pi-expand-icon${isExp?' open':''}">▼</span></div>`;

        const _RELEV_BORDER = {very_high:'#dc2626',high:'#ea580c',medium:'#d97706',low:'#94a3b8',monitor:'#94a3b8'};
        // Use numeric score for border color if available, else fall back to word-label lookup
        const _numBorderCol = ent.bestNumericScore != null ? this._numericRelevColor(parseFloat(ent.bestNumericScore)).fg : (_RELEV_BORDER[_effectiveRelev||''] || '#e2e8f0');
        const relevBorder = `border-left:3px solid ${_numBorderCol}`;
        const isAilux = ent.company_id === 'ailux';  // amber HOME styling for real Ailux entity
        const rInfo   = rankMap[ent.entity_id] || null;
        const colSpan = showRace ? 8 : 7;
        const expRow = isExp ? '<tr class="pi-detail-row"><td colspan="'+colSpan+'"><div class="pi-research-host" id="pi-research-host-'+ent.entity_id+'"></div>'+this._entityDetailHTML(ent)+'</td></tr>' : '';
        const _covPct = this._covScoreMap?.[ent.company_id] ?? this._covScoreMap?.[ent.entity_id] ?? null;
        const _covHtml = _covPct != null ? `<span style="font-size:9px;font-weight:700;color:${_covPct>=70?'#15803d':_covPct>=40?'#b45309':'#b91c1c'};margin-left:5px" title="Coverage score: ${_covPct}%">⬤ ${_covPct}%</span>` : '';
        // Ailux row: amber highlight, HOME tag, no toggle
        if (isAilux) {
          const aBorder = 'border-left:3px solid #f59e0b';
          const rk = this._rankCell(rInfo);
          const sc = rInfo ? '<span class="pi-sc-chip">'+rInfo.score+'</span>' : '';
          return '<tr class="pi-main pi-ailux-row" style="cursor:default;'+aBorder+'">'
            + rk
            + '<td><strong style="font-size:12px;color:#92400e;white-space:nowrap">Ailux <span class="pi-ailux-tag">HOME</span></strong>'
            + '<div style="font-size:10px;color:#94a3b8;font-weight:500;margin-top:2px">Private — Shanghai, China</div></td>'
            + '<td><div style="font-size:10px;color:#92400e;font-weight:700">'+ailuxProg.drug+sc+'</div></td>'
            + '<td><span style="font-size:9px;background:#fff8e1;color:#92400e;border:1px solid #fde68a;border-radius:8px;padding:2px 7px;font-weight:700;display:inline-block">'+(ailuxProg.ind||'').split(';')[0].trim()+'</span></td>'
            + '<td style="font-size:11px;color:#92400e;font-weight:600;white-space:nowrap">'+ailuxProg.target+'</td>'
            + '<td>'+this._stagePill('Preclinical')+'</td>'
            + '<td><span style="font-size:9px;color:#b45309;font-weight:700;background:#fffbeb;border:1px solid #fde68a;padding:2px 7px;border-radius:8px">Your Asset</span></td>'
            + '<td><span style="font-size:9px;color:#d97706;font-weight:700;white-space:nowrap">IND 2026 →</span></td>'
            + '</tr>' + expRow;
        }
        // Row build — Ailux uses same structure, amber styling applied here
        const rk = showRace ? this._rankCell(rInfo) : '';
        const rowBg     = isAilux ? ' pi-ailux-row' : '';
        const entBorder = isAilux ? 'border-left:3px solid #f59e0b' : ('border-left:3px solid ' + _numBorderCol);
        const nameColor = isAilux ? '#92400e' : '#1e3a5f';
        const ailuxTag  = isAilux ? ' <span class="pi-ailux-tag">HOME</span>' : '';
        const entityInner = isAilux
          ? ent.entity_name + ailuxTag
          : '<span class="pi-entity-name" data-eid="'+ent.entity_id+'" data-cid="'+(ent.company_id||ent.entity_id)+'" data-ename="'+ent.entity_name.replace(/"/g,'&quot;')+'" data-tab="'+tid+'" data-ticker="'+(ent.ticker||'').replace(/"/g,'')+'" data-hqcity="'+(ent.hq_city||'').replace(/"/g,'')+'" data-hqcountry="'+(ent.hq_country||'').replace(/"/g,'')+'" onclick="event.stopPropagation();_openEntityByEl(this)">'+ent.entity_name+'</span>'+_covHtml;
        const locLine = isAilux
          ? 'Private — Shanghai, China'
          : (()=>{const t=(ent.ticker||'').split('/')[0].trim()||'Private';const loc=(ent.hq_city&&ent.hq_country)?' — '+ent.hq_city+', '+ent.hq_country:'';return t+loc;})();
        const rowOnclick = ' onclick="_areaPIToggle(\''+tid+'\',\''+ent.entity_id+'\')"';  // all entities have dropdown
        const rowCursor  = 'cursor:pointer;';  // all entities expand on click
        return '<tr class="pi-main'+(isExp?' expanded':'')+rowBg+'" style="'+rowCursor+entBorder+'"'+rowOnclick+'>'
          + rk
          + '<td><strong style="font-size:12px;color:'+nameColor+';display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'+entityInner+'</strong><div style="font-size:10px;color:#94a3b8;font-weight:500;margin-top:2px">'+locLine+'</div></td>'
          + '<td>'+pipelineCell+'</td>'
          + '<td>'+indCell+'</td>'
          + '<td style="font-size:11px;color:#475569;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'+(ent.target||'')+'</td>'
          + '<td>'+this._stagePill(ent.bestStage)+'</td>'
          + '<td>'+threatCell+'</td>'
          + '<td>'+catCell+'</td>'
          + '</tr>' + expRow;
      }).join('');

      // ── Status line (replaces 4-box stats block) ──────────────────────────────
      const _qsDrugs   = this.data || [];
      const _qsToday   = new Date();
      // Next catalyst in days (for status line)
      let _qsNextDays  = null;
      const _allCats   = Object.values(this._entityMeta || {}).map(m=>m.nextCatalyst).filter(Boolean);
      if (_allCats.length) {
        const soonest = _allCats.map(c => new Date(c+'T12:00:00Z')).filter(d=>!isNaN(d)&&d>=_qsToday).sort((a,b)=>a-b)[0];
        if (soonest) _qsNextDays = Math.ceil((soonest - _qsToday) / (24*60*60*1000));
      }

      // Area name from tab ID (title-case, strip suffixes)
      const _areaRaw   = (this.tabId||'').replace(/-area-pi$/,'').replace(/[-_]/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
      const _statusLine = _areaStatusLine(_qsDrugs, _areaRaw, _qsNextDays);

      const _quickStats = `<div style="padding:0 12px 2px 12px;">${_statusLine}</div>`;

      const _cg = showRace
        ? '<colgroup><col style="width:20px"><col style="width:auto"><col style="width:10%"><col style="width:12%"><col style="width:14%"><col style="width:10%"><col style="width:14%"><col style="width:16%"></colgroup>'
        : '<colgroup><col style="width:19%"><col style="width:11%"><col style="width:13%"><col style="width:17%"><col style="width:11%"><col style="width:14%"><col style="width:15%"></colgroup>';
      const _th = showRace
        ? '<thead><tr><th style="width:20px;min-width:20px;padding:0;border:none"></th><th class="pi-th-sort" onclick="_areaPISort(\''+tid+'\',\'co\')">Entity</th><th>Pipeline</th><th>Indication</th><th>Lead Target</th><th class="pi-th-sort" onclick="_areaPISort(\''+tid+'\',\'stage\')">Stage</th><th class="pi-th-sort" onclick="_areaPISort(\''+tid+'\',\'relevance\')">Relevance</th><th>Catalyst</th></tr></thead>'
        : '<thead><tr><th class="pi-th-sort" onclick="_areaPISort(\''+tid+'\',\'co\')">Entity</th><th>Pipeline</th><th>Indication</th><th onclick="_areaPISort(\''+tid+'\',\'target\')" style="cursor:pointer">Lead Target</th><th class="pi-th-sort" onclick="_areaPISort(\''+tid+'\',\'stage\')">Stage</th><th class="pi-th-sort" onclick="_areaPISort(\''+tid+'\',\'relevance\')">Relevance</th><th>Catalyst</th></tr></thead>';
      el.innerHTML = _quickStats + '<table class="pi-table">' + _cg + _th + '<tbody>' + rows + '</tbody></table>';
    },

 _genericDetailHTML(prog, sbData, tabId) {
  // ── Disease-area portfolio label — disease-first, not mechanism-first ───────
  const _portfolioLabel = (typeof TAB_PORTFOLIO_LABELS !== 'undefined' && tabId && TAB_PORTFOLIO_LABELS[tabId])
    ? TAB_PORTFOLIO_LABELS[tabId]
    : 'IBD Portfolio';
  const profile       = sbData?.profile || {};
  const sbCats        = sbData?.catalysts || [];
  const sbDeals       = sbData?.deals || [];
  const sbTrials      = sbData?.trials || [];
  const sbDrugs       = sbData?.drugs || [];
  const sbCombos      = sbData?.combos || [];
  const moleculeIntel       = sbData?.moleculeIntel || {};
  const competitiveSignals  = sbData?.competitiveSignals || [];
  const athByDrugId         = sbData?.athByDrugId || {};

  // ── Narrative fields ────────────────────────────────────────────────────
  const platformSummary   = profile.platform_summary || prog.summary || '';
  const bdSummary         = profile.bd_summary || '';
  const platformIntel     = profile.platform_intelligence || null;
  const bdIntel           = profile.bd_intelligence || null;
  const keyRisk           = profile.key_risk || prog.risk || '';
  const whyMatters        = profile.why_it_matters || prog.diff || '';
  const pipelineUrl       = profile.pipeline_url || null;

  // ── Structured intelligence renderers ───────────────────────────────────
  const _confBadge = c => {
   if (!c) return '';
   const cfg = c === 'high'   ? {bg:'#f0fdf4',color:'#15803d',border:'#bbf7d0',label:'High confidence'} :
               c === 'medium' ? {bg:'#fffbeb',color:'#b45309',border:'#fde68a',label:'Medium confidence'} :
                                {bg:'#f8fafc',color:'#64748b',border:'#e2e8f0',label:'Low confidence'};
   return `<span style="font-size:8px;font-weight:700;text-transform:uppercase;background:${cfg.bg};color:${cfg.color};border:1px solid ${cfg.border};border-radius:8px;padding:1px 6px">${cfg.label}</span>`;
  };

  const _renderMoleculeIntel = (drugs, moleculeIntel) => {
   // Collect all molecule rows for the drugs shown in this card
   const mols = (drugs||[]).map(d => moleculeIntel[d.id]).filter(Boolean);
   if (!mols.length) return null;

   const _statusBadge = (field, fs) => {
    const status = (fs||{})[field];
    if (!status || status === 'confirmed') return '';  // confirmed = no badge needed
    const cfg = status === 'inferred'
     ? {bg:'#fffbeb',color:'#b45309',border:'#fde68a',label:'Inferred'}
     : {bg:'#f8fafc',color:'#94a3b8',border:'#e2e8f0',label:'Not disclosed'};
    return `<span style="font-size:7.5px;font-weight:700;text-transform:uppercase;background:${cfg.bg};color:${cfg.color};border:1px solid ${cfg.border};border-radius:5px;padding:1px 5px;white-space:nowrap;flex-shrink:0">${cfg.label}</span>`;
   };

   const _fieldRow = (label, value, fieldKey, fs) => {
    if (!value) return '';
    const badge = _statusBadge(fieldKey, fs);
    return `<div style="display:flex;align-items:baseline;gap:6px;padding:2px 0;border-bottom:1px solid #f8fafc;font-size:10.5px">
     <span style="color:#64748b;font-weight:600;white-space:nowrap;min-width:100px">${label}</span>
     <span style="color:#1e293b;flex:1">${value}</span>
     ${badge}
    </div>`;
   };

   const rows = mols.map(mol => {
    const fs = mol.field_status || {};
    const drugLabel = drugs.find(d => d.id === mol.drug_id)?.name || mol.drug_id;
    const header = mols.length > 1
     ? `<div style="font-size:9px;font-weight:800;text-transform:uppercase;color:#7c3aed;letter-spacing:0.05em;margin-bottom:4px;padding-bottom:2px;border-bottom:1px solid #ede9fe">${drugLabel}</div>`
     : '';
    const structRows = [
     _fieldRow('Format',         mol.format,       'format',      fs),
     _fieldRow('Modality',       mol.modality,     'modality',    fs),
     _fieldRow('IgG subclass',   mol.igg_subclass, 'igg_subclass',fs),
     _fieldRow('Fc engineering', mol.fc_engineering,'fc_engineering',fs),
     _fieldRow('Epitope',        mol.epitope,      'epitope',     fs),
     _fieldRow('Affinity (KD)',  mol.affinity_kd,  'affinity_kd', fs),
    ].filter(Boolean).join('');

    const safetySection = mol.safety_observations
     ? `<div style="margin-top:6px;padding-top:4px;border-top:1px solid #f1f5f9">
         <div style="font-size:8.5px;font-weight:800;text-transform:uppercase;letter-spacing:0.05em;color:#94a3b8;margin-bottom:3px">Safety observations</div>
         <p style="font-size:10.5px;color:#334155;margin:0;line-height:1.4">${mol.safety_observations}</p>
        </div>` : '';

    const thesisSection = mol.differentiation_claim
     ? `<div style="margin-top:7px;padding:7px 9px;background:#f5f3ff;border-radius:6px;border-left:3px solid #7c3aed">
         <div style="font-size:8.5px;font-weight:800;text-transform:uppercase;letter-spacing:0.05em;color:#7c3aed;margin-bottom:3px">Differentiation thesis ${_statusBadge('differentiation_claim', fs)}</div>
         <p style="font-size:11px;color:#1e293b;margin:0;line-height:1.45;font-style:italic">${mol.differentiation_claim}</p>
        </div>` : '';

    const srcNote = mol.source_url
     ? `<div style="margin-top:5px;text-align:right"><a href="${mol.source_url}" target="_blank" rel="noopener" style="font-size:9px;color:#1d4ed8">Source ↗</a></div>`
     : '';

    return `${header}<div style="display:flex;flex-direction:column;gap:0">${structRows}</div>${thesisSection}${safetySection}${srcNote}`;
   }).join('<hr style="margin:8px 0;border:none;border-top:1px solid #f1f5f9">');

   const confBadge = mols[0]?.confidence
    ? `<span style="font-size:8px;font-weight:700;text-transform:uppercase;background:${mols[0].confidence==='high'?'#f0fdf4':mols[0].confidence==='medium'?'#fffbeb':'#f8fafc'};color:${mols[0].confidence==='high'?'#15803d':mols[0].confidence==='medium'?'#b45309':'#64748b'};border:1px solid ${mols[0].confidence==='high'?'#bbf7d0':mols[0].confidence==='medium'?'#fde68a':'#e2e8f0'};border-radius:8px;padding:1px 6px">${mols[0].confidence.charAt(0).toUpperCase()+mols[0].confidence.slice(1)} confidence</span>`
    : '';

   return `<div style="flex:1;display:flex;flex-direction:column">
    <div>${rows}</div>
    <div style="margin-top:auto;padding-top:8px;text-align:right">${confBadge}</div>
   </div>`;
  };

  const _renderPlatformIntel = pi => {
   if (!pi) return null;
   const facts = (pi.facts||[]).map(f =>
    `<li style="font-size:11px;color:#1e293b;padding:2px 0;line-height:1.45">${f}</li>`).join('');
   const direction = (pi.direction||[]).map(d => {
    const clean = d.replace(/^\[INFERRED\]\s*/i,'');
    return `<li style="font-size:11px;color:#334155;padding:2px 0;line-height:1.45"><span style="font-size:8px;font-weight:800;text-transform:uppercase;color:#6d28d9;background:#ede9fe;border-radius:3px;padding:0 4px;margin-right:4px;vertical-align:middle">Inferred</span>${clean}</li>`;
   }).join('');
   // Assessment is rendered at the top of the dropdown — omitted here
   return `<div style="flex:1;display:flex;flex-direction:column">
    <div>
     ${facts?`<div style="font-size:8.5px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#94a3b8;margin-bottom:3px">Facts</div><ul style="margin:0 0 8px 0;padding-left:14px">${facts}</ul>`:''}
     ${direction?`<div style="font-size:8.5px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#94a3b8;margin-bottom:3px">Direction</div><ul style="margin:0 0 0 0;padding-left:14px">${direction}</ul>`:''}
    </div>
    <div style="margin-top:auto;padding-top:8px;text-align:right">${_confBadge(pi.confidence)}</div>
   </div>`;
  };

  const _renderBdIntel = bd => {
   if (!bd) return null;
   const profileCfg = {
    acquirer:         {label:'Acquirer',          bg:'#fef2f2',color:'#991b1b',border:'#fecaca'},
    licensor:         {label:'Licensor',           bg:'#eff6ff',color:'#1d4ed8',border:'#bfdbfe'},
    collaborator:     {label:'Collaborator',       bg:'#f0fdf4',color:'#15803d',border:'#bbf7d0'},
    'partner-friendly':{label:'Partner-Friendly', bg:'#f0fdf4',color:'#15803d',border:'#bbf7d0'},
    'internal-focused':{label:'Internal-Focused', bg:'#f8fafc',color:'#475569',border:'#e2e8f0'},
   };
   const pcfg = profileCfg[bd.profile] || {label:bd.profile||'—',bg:'#f8fafc',color:'#475569',border:'#e2e8f0'};
   const profilePill = `<span style="font-size:9px;font-weight:800;text-transform:uppercase;background:${pcfg.bg};color:${pcfg.color};border:1px solid ${pcfg.border};border-radius:8px;padding:2px 8px">${pcfg.label}</span>`;
   const txRows = (bd.transactions||[]).map(t =>
    `<div style="display:grid;grid-template-columns:56px 1fr auto;gap:6px;align-items:baseline;padding:3px 0;border-bottom:1px solid #f1f5f9;font-size:10.5px">
      <span style="color:#64748b;font-weight:600;white-space:nowrap">${t.date||''}</span>
      <span style="color:#1e293b">${t.asset||''}${t.partner?`<span style="color:#94a3b8"> · ${t.partner}</span>`:''}</span>
      <span style="color:#059669;font-weight:700;white-space:nowrap;font-size:10px">${t.total||t.upfront||''}</span>
     </div>`).join('');
   const assessLines = (bd.assessment||[]).map(a => {
    const clean = a.replace(/^\[ASSESSED\]\s*/i,'');
    return `<li style="font-size:11px;color:#334155;padding:2px 0;line-height:1.45">${clean}</li>`;
   }).join('');
   return `<div style="flex:1;display:flex;flex-direction:column">
    <div>
     ${txRows?`<div style="margin-bottom:8px">${txRows}</div>`:''}
     ${assessLines?`<ul style="margin:0;padding-left:14px">${assessLines}</ul>`:''}
    </div>
    <div style="margin-top:auto;padding-top:8px;text-align:right">${_confBadge(bd.confidence)}</div>
   </div>`;
  };

  // ── Top-level assessment card ────────────────────────────────────────────
  const _renderAssessmentCard = (pi, bd) => {
   const piAssess = (pi?.assessment||'').replace(/^\[ASSESSED\]\s*/i,'');
   if (!piAssess) return '';
   const profileCfg = {
    acquirer:         {label:'Acquirer',          bg:'#fef2f2',color:'#991b1b',border:'#fecaca'},
    licensor:         {label:'Licensor',           bg:'#eff6ff',color:'#1d4ed8',border:'#bfdbfe'},
    collaborator:     {label:'Collaborator',       bg:'#f0fdf4',color:'#15803d',border:'#bbf7d0'},
    'partner-friendly':{label:'Partner-Friendly', bg:'#f0fdf4',color:'#15803d',border:'#bbf7d0'},
    'internal-focused':{label:'Internal-Focused', bg:'#f8fafc',color:'#475569',border:'#e2e8f0'},
   };
   const pcfg = bd?.profile ? (profileCfg[bd.profile] || {label:bd.profile,bg:'#f8fafc',color:'#475569',border:'#e2e8f0'}) : null;
   const profilePill = pcfg
    ? `<span style="font-size:9px;font-weight:800;text-transform:uppercase;background:${pcfg.bg};color:${pcfg.color};border:1px solid ${pcfg.border};border-radius:8px;padding:2px 8px">${pcfg.label}</span>`
    : '';
   return `<div style="background:#faf9ff;border:1px solid #e9e5fb;border-radius:7px;padding:10px 12px">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:7px">
     <span style="font-size:8.5px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#7c3aed">Assessment</span>
     ${profilePill}
    </div>
    <p style="font-size:11.5px;color:#0f172a;font-weight:600;line-height:1.5;margin:0;border-left:2px solid #7c3aed;padding-left:8px">${piAssess}</p>
   </div>`;
  };

  const enrichedAt = profile.last_enriched_at
   ? `<span style="font-size:9px;color:#94a3b8;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:1px 6px;margin-left:6px">🤖 ${profile.last_enriched_at.slice(0,10)}</span>`
   : `<span style="font-size:9px;color:#cbd5e1;background:#f8fafc;border:1px solid #f1f5f9;border-radius:8px;padding:1px 6px;margin-left:6px">⏳ pending enrichment</span>`;

  // ── Trial status helper ─────────────────────────────────────────────────
  const trialStatusCls = s => {
   const sl = (s||'').toLowerCase();
   if (sl.includes('terminat') || sl.includes('withdrawn') || sl.includes('suspend')) return 'pi-trial-stopped';
   if (sl.includes('not yet recruit')) return 'pi-trial-planned';
   if (sl.includes('active') && sl.includes('not recruit')) return 'pi-trial-anr';
   if (sl.includes('recruit')) return 'pi-trial-recruiting';
   if (sl.includes('complet')) return 'pi-trial-done';
   return 'pi-trial-planned';
  };

  // ── Trial relevance score (0–100) for sorting + bar ────────────────────
  // overlap = drug-level competitive overlap with Ailux ('direct'|'adjacent'|'same'|'watch')
  const trialRelevance = (t, overlap = '') => {
   const ph = (t.phase||'').toLowerCase();
   const st = (t.status||'').toLowerCase();
   const ov = overlap.toLowerCase();
   let score = 0;
   if      (ph.includes('3'))              score += 50;
   else if (ph.includes('2/3') || ph.includes('2b')) score += 40;
   else if (ph.includes('2'))              score += 28;
   else if (ph.includes('1/2'))            score += 18;
   else if (ph.includes('1'))              score += 10;
   // "Active, not recruiting" = enrollment done, data imminent
   if      (st.includes('active') && st.includes('not recruit')) score += 35;
   else if (st.includes('recruit') && !st.includes('not'))       score += 25;
   else if (st.includes('not yet'))                               score += 10;
   else if (st.includes('complet'))                               score += 5;
   // Competitive overlap: direct = same exact targets → always high relevance regardless of phase
   if      (ov === 'direct')   score = Math.max(score + 15, 82);
   else if (ov === 'adjacent') score += 14;
   return Math.min(100, score);
  };

  // Bar color: orange for high (Phase 3), blue for medium (Phase 2), gray for low
  const relBarColor = score => score >= 75 ? '#f97316' : score >= 45 ? '#3b82f6' : '#94a3b8';

  // ── Date helpers — defined HERE (before fmtPcd + renderNewsItem that use them)
  // (const is NOT hoisted — defining after the callers causes ReferenceError in TDZ)
  const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const fmtExactDate = iso => {
   if (!iso) return '';
   const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
   if (m) return `${MONTHS[parseInt(m[2])-1]} ${parseInt(m[3])}, ${m[1]}`;
   return iso; // already formatted (e.g. "Q3 2026", "April 28, 2028")
  };

  // ── PCD full-date formatter ─────────────────────────────────────────────
  const fmtPcd = raw => {
   if (!raw) return '';
   const full = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
   if (full) { const d=new Date(raw+'T00:00:00Z'); return `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}, ${d.getUTCFullYear()}`; }
   const mo = raw.match(/^(\d{4})-(\d{2})$/);
   if (mo) return `${MONTHS[parseInt(mo[2])-1]} ${mo[1]}`;
   return raw;
  };

  // ── Build trials index by drug_id ───────────────────────────────────────
  // Always fall back to static prog.trials when DB trials are empty.
  // When sbTrials is empty and static trials key as '__all__', the drugTrials
  // assignment below pins them to the first drug to avoid cross-row spillage.
  const trialsByDrug  = {};
  const trialsByCombo = {};
  const allTrials = sbTrials.length ? sbTrials
    : (prog.trials||[]).map(t=>({...t, id:t.id||t.nct}));
  allTrials.forEach(t => {
   if (t.combination_id) {
    // Combination trial — index by combination_id so combo accordion sections can find it
    (trialsByCombo[t.combination_id] = trialsByCombo[t.combination_id] || []).push(t);
   } else {
    const key = t.drug_id || t.canonical_drug_id || '__all__';
    (trialsByDrug[key] = trialsByDrug[key] || []).push(t);
   }
  });

  // ── Build drug accordion rows ───────────────────────────────────────────
  let drugsToRender = [];
  if (sbDrugs.length) {
   drugsToRender = [...sbDrugs].sort((a,b) => (a.sort_order||0)-(b.sort_order||0));
  } else {
   // Use _groupEntries to build one static drug row per program in the company group.
   // This ensures multi-drug companies (AbbVie: FG-M701 + Skyrizi + Rinvoq;
   // Xencor: XmAb942 + XmAb412; Spyre: SPY002 + SPY230) each get their own row.
   const sourceEntries = prog._groupEntries || [prog];
   drugsToRender = sourceEntries.flatMap((entry, ei) => {
    const drugNames = (entry.drug||'').split(',').map(s=>s.trim()).filter(Boolean);
    return drugNames.map((dn,i) => ({
     id: `static-${entry.id}-${i}`,
     name: dn.replace(/\s*[/(].*/, '').trim(),
     mechanism: entry.target||'', stage: entry.stageKey||'',
     route: null, dosing_type: null, indication_short: entry.indication_short || entry.indication || '',
     differentiation_thesis: null, vs_ailux: null,
     _staticTrials: entry.trials || [],   // per-entry trials for static fallback
     // NOTE: _partnerCo is a legacy static field. DB drugs use partner_company (from Supabase).
     // Kept here only as last-resort fallback for companies with no DB drug record yet.
     _partnerCo: entry.partnerCo || null,
     _overlap: entry.overlap || null,     // per-drug relevance badge
     _altCode: entry._altCode || null,         // partner's alternate code (e.g. QX030N for CLD-423)
     _altCodeNote: entry._altCodeNote || null, // human-readable note for the alt code
    }));
   });
  }

  // ── Drug relevance score for sorting (0–100) ────────────────────────────
  const drugRelevance = item => {
   // Use per-drug overlap first; fall back to company-level only as a soft signal (not override).
   const perDrug = ((item._overlap || item.overlap_category || '')).toLowerCase().replace(/[-_\s]/g,'');
   const coLevel = (prog.overlap || '').toLowerCase().replace(/[-_\s]/g,'');
   // Per-drug score: definitive if set
   if (perDrug === 'direct')    return 100;
   if (perDrug === 'adjacent')  return 70;
   if (perDrug === 'samespace') return 40;
   if (perDrug === 'watch')     return 20;
   // No per-drug overlap: use company-level as a soft signal (score capped at 65 to stay below explicit adjacent)
   if (coLevel === 'direct')    return 65;
   if (coLevel === 'adjacent')  return 55;
   if (coLevel === 'samespace') return 35;
   if (coLevel === 'watch')     return 15;
   return 30;
  };

  // ── First-sentence extractor (hoisted so combos can use it) ─────────────
  const firstSentence = txt => {
   if (!txt) return '';
   const m = txt.match(/^.+?[.!?](?:\s|$)/);
   return m ? m[0].trim() : (txt.length > 140 ? txt.slice(0, 140).trim() + '…' : txt.trim());
  };

  // ── Indication abbreviator — maps full disease names to standard clinical abbreviations ──
  // Applied at render time to all indication_short values; no DB changes required.
  const _abbrevInd = str => {
   if (!str) return str;
   const _IM = [
    // ── Semicolon ICD-style forms (must precede splitting) ──
    ['Asthma; Eosinophilic','Eo-Asthma'],['Asthma; Severe','Sev. Asthma'],
    ['Asthma; Allergic','Allergic Asthma'],['Asthma Acute','Acute Asthma'],
    ['Bronchial Asthma','Asthma'],['Acute Asthma','Asthma'],['Asthma Acute','Asthma'],
    ['Acute Exacerbation of Chronic Obstructive Pulmonary Disease','AECOPD'],
    ['Acute Exacerbation of COPD','AECOPD'],['COPD Acute Exacerbation','AECOPD'],
    ['Acute COPD Exacerbation','AECOPD'],
    ['COVID-19','COVID-19'],['SARS-CoV-2','COVID-19'],['Coronavirus Disease','COVID-19'],
    ['Acute Respiratory Distress Syndrome','ARDS'],['Acute Respiratory Distress','ARDS'],
    ['Acute Respiratory Infection','ARI'],['Viral Lung Infection','VLI'],
    ['Mental Health Disorder','MHD'],['Mental Health Disorders','MHD'],['Mental Health','MH'],
    // ── Comma-inverted ICD-style forms (must precede standard forms) ──
    ['MG, Generalized','gMG'],['MG, Ocular','oMG'],
    ['Multiple Sclerosis, Primary Progressive','PPMS'],['Multiple Sclerosis, Secondary Progressive','SPMS'],
    ['Multiple Sclerosis, Relapsing-Remitting','RRMS'],['Multiple Sclerosis, Relapsing','RRMS'],
    ['Arthritis, Rheumatoid','RA'],['Arthritis, Psoriatic','PsA'],['Arthritis, Juvenile Idiopathic','JIA'],
    ['Colitis, Ulcerative','UC'],['Dermatitis, Atopic','AD'],['Dermatitis Atopic','AD'],['Colitis, Microscopic','MC'],
    ['Sclerosis, Systemic','SSc'],['Sclerosis, Multiple','MS'],
    ['Lupus Erythematosus, Systemic','SLE'],['Lupus Erythematosus Systemic','SLE'],
    ['Anemia, Hemolytic, Autoimmune','AIHA'],
    ['Carcinoma, Hepatocellular','HCC'],['Carcinoma, Renal Cell','RCC'],
    ['Pulmonary Disease, Chronic Obstructive','COPD'],
    ['Chronic Urticaria, Idiopathic','CIU'],
    ['Lymphoma, Non-Hodgkin','NHL'],['Lymphoma, Large B-Cell, Diffuse','DLBCL'],
    ['Lymphocytic Leukemia, Chronic','CLL'],
    ['Diabetes Mellitus, Type 1','T1D'],['Diabetes Mellitus, Type 2','T2D'],
    ['Diabetes Mellitus','DM'],['Type1 Diabetes Mellitus','T1D'],
    ['Myeloma Multiple','MM'],['Plasma Cell Myeloma','MM'],
    // ── Qualifier-prefixed forms (before base conditions) ──
    ['Diffuse Cutaneous Systemic Sclerosis','dcSSc'],['Diffuse Cutaneous SSc','dcSSc'],
    ['Limited Cutaneous Systemic Sclerosis','lcSSc'],['Limited Cutaneous SSc','lcSSc'],
    ['Radiographic Axial Spondyloarthritis','r-axSpA'],['Radiographic axSpA','r-axSpA'],
    ['Non-Radiographic Axial Spondyloarthritis','nr-axSpA'],['Nonradiographic axSpA','nr-axSpA'],
    ['Non-radiographic Axial Spondyloarthritis','nr-axSpA'],
    ['Interstitial Lung Disease','ILD'],['Pulmonary Arterial Hypertension','PAH'],
    ['Idiopathic Pulmonary Fibrosis','IPF'],['Pulmonary Fibrosis','PF'],
    // ── Autoimmune / Rheumatology ──
    ['Moderately to Severely Active Ulcerative Colitis','Mod-Sev UC'],
    ['Moderately to Severely Active Crohn\'s Disease','Mod-Sev CD'],
    ['Moderately to Severely Active Crohn Disease','Mod-Sev CD'],
    ['Ulcerative Colitis','UC'],["Crohn's Disease",'CD'],['Crohn Disease','CD'],
    ['Atopic Dermatitis','AD'],['Atopic Eczema','AD'],['Eczema, Atopic','AD'],['Eczema','AD'],
    ['Rheumatoid Arthritis','RA'],['Psoriatic Arthritis','PsA'],
    ['Papulopustular Rosacea','PPR'],['Erythematotelangiectatic Rosacea','ETR'],['Rosacea','Rosa.'],
    ['Plaque Psoriasis','PsO'],['Psoriasis Vulgaris','PsO'],['Psoriasis','PsO'],
    ['Ankylosing Spondylitis','AS'],['Axial Spondyloarthritis','axSpA'],['Spondyloarthritis','SpA'],
    ['Hidradenitis Suppurativa','HS'],['Eosinophilic Esophagitis','EoE'],
    ['Alopecia Areata','AA'],['Prurigo Nodularis','PN'],
    ['Polymyalgia Rheumatica','PMR'],
    ['IgG4-Related Disease','IgG4-RD'],['IgG4 Related Disease','IgG4-RD'],
    ['Psoriatic-arthritis','PsA'],['Atopic Disorders','Atop. Dis.'],
    ['Chronic Hand Dermatitis','Chr. Hand Derm.'],
    ['Thyroid-Associated Ophthalmopathy','TAO'],['Thyroid Associated Ophthalmopathy','TAO'],
    ['Thyroid Associated Ophthalmopathies','TAO'],
    ["Graves' Orbitopathy",'GO'],['Graves Orbitopathy','GO'],
    ['Autoimmune Lymphoproliferative Syndrome','ALPS'],
    ['Childhood-onset Systemic Lupus Erythematous','cSLE'],
    ['Childhood-onset Systemic Lupus Erythematosus','cSLE'],['Childhood Onset Systemic Lupus Erythematosus','cSLE'],
    ['Juvenile Systemic Lupus Erythematosus','cSLE'],['Paediatric SLE','cSLE'],['Pediatric SLE','cSLE'],
    ['Subacute Cutaneous Lupus Erythematosus','SCLE'],['Cutaneous Lupus Erythematosus','CLE'],
    ['Discoid Lupus Erythematosus','DLE'],['Neonatal Lupus Erythematosus','NLE'],
    ['Systemic Lupus Erythematosus','SLE'],
    ['Primary Progressive Multiple Sclerosis','PPMS'],['Secondary Progressive Multiple Sclerosis','SPMS'],
    ['Relapsing-Remitting Multiple Sclerosis','RRMS'],['Relapsing Remitting Multiple Sclerosis','RRMS'],
    ['Relapsing Multiple Sclerosis','RRMS'],['Relapsing MS','RRMS'],
    ['Progressive Multiple Sclerosis (PMS)','Prog. MS'],
    ['Progressive Multiple Sclerosis','Prog. MS'],['Clinically Isolated Syndrome','CIS'],
    ['Multiple Sclerosis','MS'],['Thyroid Eye Disease','TED'],
    ["Graves's Disease",'GD'],["Graves' Disease",'GD'],['Graves Disease','GD'],
    ['Myelin Oligodendrocyte Glycoprotein Antibody-Associated Disease','MOGAD'],
    ['Myelin Oligodendrocyte Glycoprotein Antibody-associated Disease','MOGAD'],
    ['MOG Antibody-Associated Disease','MOGAD'],['MOG Antibody Disease','MOGAD'],
    ['Ocular Myasthenia Gravis','oMG'],['Generalized Myasthenia Gravis','gMG'],
    ['Myasthaenia Gravis','gMG'],['Myasthenia Gravis','MG'],
    ['Inflammatory Bowel Disease','IBD'],['Chronic Obstructive Pulmonary Disease','COPD'],
    ['Nonalcoholic Steatohepatitis','NASH'],['Non-alcoholic Steatohepatitis','NASH'],['Non-Alcoholic Steatohepatitis','NASH'],
    ['Metabolic-associated Steatohepatitis','MASH'],['Metabolic Associated Steatohepatitis','MASH'],
    ['Systemic Sclerosis','SSc'],['Scleroderma','SSc'],
    ['Warm Autoimmune Hemolytic Anemia','wAIHA'],['Autoimmune Hemolytic Anemia','AIHA'],
    ['Chronic Spontaneous Urticaria','CSU'],['Chronic Idiopathic Urticaria','CIU'],
    ['Immune Thrombocytopenic Purpura','ITP'],['Primary Immune Thrombocytopenia','ITP'],['Immune Thrombocytopenia','ITP'],
    ['Pemphigus Vulgaris','PV'],['Pemphigus Foliaceus','PF'],['Bullous Pemphigoid','BP'],['Pemphigus','PV'],
    ['Neuromyelitis Optica Spectrum Disorder','NMOSD'],['Neuromyelitis Optica','NMO'],
    ['Chronic Inflammatory Demyelinating Polyneuropathy','CIDP'],
    ['Chronic Inflammatory Demyelinating Polyradiculoneuropathy','CIDP'],
    ['Multifocal Motor Neuropathy','MMN'],
    ['Paroxysmal Nocturnal Hemoglobinuria','PNH'],
    ['Amyotrophic Lateral Sclerosis','ALS'],
    ['Guillain-Barré Syndrome','GBS'],['Guillain-Barre Syndrome','GBS'],
    ['Primary Biliary Cholangitis','PBC'],['Primary Sclerosing Cholangitis','PSC'],
    ['Lupus Nephritis - World Health Organization (WHO) Class III','LN (III)'],
    ['Lupus Nephritis - World Health Organization (WHO) Class IV','LN (IV)'],
    ['Lupus Nephritis - World Health Organization (WHO) Class V','LN (V)'],
    ['Lupus Nephritis - WHO Class III','LN (III)'],['Lupus Nephritis - WHO Class IV','LN (IV)'],['Lupus Nephritis - WHO Class V','LN (V)'],
    ['LN - World Health Organization (WHO) Class III','LN (III)'],['LN - World Health Organization (WHO) Class IV','LN (IV)'],
    ['LN - WHO Class III','LN (III)'],['LN - WHO Class IV','LN (IV)'],['LN - WHO Class V','LN (V)'],
    ['IgA Nephropathy','IgAN'],['Membranous Nephropathy','MN'],['Focal Segmental Glomerulosclerosis','FSGS'],['Lupus Nephritis','LN'],
    ['Stiff-Person Syndrome','SPS'],['Stiff Person Syndrome','SPS'],
    ['ANCA-IgG-positive ANCA Associated Vasculitis','AAV'],['ANCA-IgG-positive ANCA-Associated Vasculitis','AAV'],['ANCA-IgG Positive ANCA-Associated Vasculitis','AAV'],
    ['Anti-Synthetase Syndrome','ASyS'],['Antisynthetase Syndrome','ASyS'],['Antysinthetase Syndrome','ASyS'],
    ['Dermatomyositis','DM'],['Polymyositis','PM'],['Idiopathic Inflammatory Myopathies','IIM'],['Idiopathic Inflammatory Myopathy','IIM'],
    ['Giant Cell Arteritis','GCA'],['Takayasu Arteritis','TAK'],
    ['Eosinophilic Granulomatosis with Polyangiitis','EGPA'],['Granulomatosis with Polyangiitis','GPA'],
    ['ANCA-Associated Vasculitis','AAV'],['Microscopic Polyangiitis','MPA'],
    ["Behçet's Disease",'BD'],["Behcet's Disease",'BD'],['Behçet Disease','BD'],['Behcet Disease','BD'],
    ['Behçet Syndrome','BD'],['Behcet Syndrome','BD'],
    ['Anterior Uveitis','Ant. Uv.'],['Posterior Uveitis','Post. Uv.'],['Pan-Uveitis','Uv.'],['Uveitis','Uv.'],
    ["Primary Sjögren's Syndrome",'pSS'],['Primary Sjögren Syndrome','pSS'],
    ["Sjögren's Syndrome",'pSS'],["Sjögren's Disease",'pSS'],
    ['Sjögren Syndrome','pSS'],['Sjögren Disease','pSS'],['Sjögren','pSS'],
    ["Sjogren's Syndrome",'pSS'],["Sjogren's Disease",'pSS'],
    ['Primary Sjögren','pSS'],['Sjogren','pSS'],
    ['Systemic Juvenile Idiopathic Arthritis','sJIA'],['Juvenile Idiopathic Arthritis','JIA'],
    ['Anti-NMDA Receptor Encephalitis','ANMDARE'],['Autoimmune Encephalitis','AE'],
    // ── Respiratory / Allergy ──
    ['Eosinophilic Asthma','Eo-Asthma'],['Severe Asthma','Asthma'],['Asthma','Asthma'],
    ['Chronic Rhinosinusitis with Nasal Polyps','CRSwNP'],
    ['Chronic Rhinosinusitis Without Nasal Polyps','CRSsNP'],['CRS Without Nasal Polyps','CRSsNP'],
    ['Chronic Rhinosinusitis','CRS'],
    ['Allergic Rhinitis','AR'],['Food Allergy','FA'],
    // ── Hematology / Oncology ──
    ['Transthyretin Amyloidosis Cardiomyopathy','ATTR-CM'],['Transthyretin Amyloidosis','ATTR'],
    ['Glioblastoma WHO Grade IV','GBM'],['Glioblastoma WHO Grade III','GBM'],['Glioblastoma Multiforme','GBM'],['Glioblastoma','GBM'],
    ['Pancreatic Ductal Adenocarcinoma','PDAC'],
    ['Malignant Peripheral Nerve Sheath Tumor, Malignant','MPNST'],['Malignant Peripheral Nerve Sheath Tumor','MPNST'],['Peripheral Nerve Sheath Tumor','PNST'],
    ['Pleural Mesothelioma','Meso.'],['Peritoneal Mesothelioma','Meso.'],['Mesothelioma','Meso.'],
    ['Advanced Solid Tumor','Adv. Solid Tu.'],['Solid Tumors','Solid Tu.'],['Solid Tumor','Solid Tu.'],
    ['Advanced Cancer','Adv. Ca.'],['Advanced Malignancy','Adv. Ca.'],
    ['Castration-Resistant Prostate Cancer','CRPC'],['Metastatic Castration-Resistant Prostate Cancer','mCRPC'],
    ['Prostate Cancer','PCa'],['Renal Cell Carcinoma','RCC'],['Clear Cell Renal Cell Carcinoma','ccRCC'],
    ['Bladder Cancer','BlaCa'],['Urothelial Carcinoma','UCa'],['Transitional Cell Carcinoma','TCC'],
    ['Endometrial Cancer','EndoCa'],['Cervical Cancer','CxCa'],['Esophageal Cancer','EsoCa'],['Gastroesophageal Junction','GEJ'],
    ['Non-Small Cell Lung Cancer','NSCLC'],['Non-SCLC','NSCLC'],['Non SCLC','NSCLC'],['Small Cell Lung Cancer','SCLC'],
    ['Hepatocellular Carcinoma','HCC'],['Cholangiocarcinoma','CCA'],
    ['Non-Hodgkin Lymphoma, Relapsed, Adult','r/r NHL'],['Non-Hodgkin Lymphoma, Relapsed','r/r NHL'],
    ['Non-Hodgkin Lymphoma, Refractory','r/r NHL'],['Relapsed or Refractory NHL','r/r NHL'],
    ['Peripheral T-Cell Lymphoma, Not Otherwise Specified','PTCL-NOS'],
    ['Peripheral T-Cell Lymphoma','PTCL'],
    ['Angioimmunoblastic T-cell Lymphoma','AITL'],['Angioimmunoblastic T-Cell Lymphoma','AITL'],
    ['Follicular T-Cell Lymphoma','FTCL'],
    ['B-Cell Acute Lymphoblastic Leukemia','B-cell ALL'],
    ['Acute Lymphoblastic Leukemia','ALL'],
    ['Mantle Cell Lymphoma','MCL'],['Marginal Zone Lymphoma','MZL'],
    ['Diffuse Large B Cell Lymphoma','DLBCL'],
    ['Non-Hodgkin Lymphoma','NHL'],["Non-Hodgkin's Lymphoma",'NHL'],['Non-Hodgkins Lymphoma','NHL'],['Hodgkin Lymphoma','HL'],
    ['Colorectal Cancer','CRC'],['Diffuse Large B-Cell Lymphoma','DLBCL'],['Follicular Lymphoma','FL'],
    ['Chronic Lymphocytic Leukemia','CLL'],['Acute Myeloid Leukemia','AML'],['Multiple Myeloma','MM'],
    ['Myelodysplastic Syndrome','MDS'],['Myelofibrosis','MF'],
    ['Head and Neck Squamous Cell Carcinoma','HNSCC'],
    ['Oropharyngeal Squamous Cell Carcinoma','OPSCC'],['Oropharyngeal Carcinoma','OPC'],
    ['Nasopharyngeal Carcinoma','NPC'],['Laryngeal Carcinoma','LarCa'],
    ['Basaloid Squamous Cell Carcinoma','BSCC'],['Squamous Cell Carcinoma','SCC'],
    ['Triple-Negative Breast Cancer','TNBC'],['Breast Cancer','BC'],
    ['Ovarian Cancer','OvCa'],['Pancreatic Cancer','PanCa'],['Gastric Cancer','GC'],
    ['Adrenocortical Carcinoma','ACC'],
    ['Biliary Tract Cancer','BTC'],
    ['Hematological Malignancies','Hem. Malig.'],['Hematologic Malignancies','Hem. Malig.'],
    ['Malignant Melanoma','Mel.'],
    ['Gastric Adenocarcinoma','GAdCa'],['Rectal Adenocarcinoma','RecCa'],
    ['Gastroesophageal Adenocarcinoma','GEJ AdCa'],
    ['Relapsed and/or Refractory Multiple Myeloma','R/R MM'],
    ['Relapsed or Refractory Multiple Myeloma','R/R MM'],
    ['Relapsed Refractory Multiple Myeloma','R/R MM'],
    ['Malignant Ascites','Malig. Asc.'],['Malignant Pleural Effusion','MPE'],
    ['Peritoneal Metastases','Perit. Met.'],['Peritoneal Cancer','Perit. Ca.'],
    // ── Congenital / Surgical / Misc ──
    ['Cleft Lip and Palate','CL/P'],['Cleft Lip','CL'],['Cleft Palate','CP'],
    ['Crohns Disease','CD'],['Crohn Disease','CD'],
    // ── Musculoskeletal / Other ──
    ['Spinal Cord Injuries','SCI'],['Spinal Cord Injury','SCI'],
    ['Developmental Dysplasia of the Hip','DDH'],['Hip Dysplasia','DDH'],
    ['Chronic Exertional Compartment Syndrome','CECS'],['Exertional Compartment Syndrome','ECS'],
    ['Liver Ablation','Liver Abl.'],
    ['Healthy Subjects or Volunteers','HV'],['Healthy Volunteers','HV'],['Healthy Subjects','HV'],['Healthy Normal Volunteers','HV'],['Healthy Volunteer','HV'],['Healthy Adult Volunteers','HV'],['Healthy Adults','HV'],['Normal Healthy Volunteers','HV'],['Normal Volunteers','HV'],
    ['Ventilation','Vent.'],['Lung Function','Lung Fxn.'],['Anesthesia, General','Gen. Anesthesia'],
    // ── Cardiovascular / Metabolic ──
    // NOTE: "CD" is reserved for Crohn's Disease — Cardiovascular Disease must map to "CVD"
    ['Cardiovascular Disease','CVD'],['Coronary Artery Disease','CAD'],['Atherosclerotic Cardiovascular Disease','ASCVD'],
    ['Endothelial Dysfunction','End. Dysf.'],
    ['Type 1 Diabetes','T1D'],['Type 2 Diabetes','T2D'],
    ['Heart Failure with Reduced Ejection Fraction','HFrEF'],['Heart Failure','HF'],
    ['Hypertrophic Cardiomyopathy','HCM'],['Dilated Cardiomyopathy','DCM'],
    ['Neovascular Age-related Macular Degeneration','nAMD'],['Age-related Macular Degeneration','AMD'],
    ['Non-alcoholic Fatty Liver Disease','NAFLD'],['Nonalcoholic Fatty Liver Disease','NAFLD'],
    ['Metabolic Dysfunction-associated Steatohepatitis','MASH'],
    ['Paroxysmal Nocturnal Hemoglobinuria','PNH'],
    ['Allergic Bronchopulmonary Aspergillosis','ABPA'],
    ['Human Immunodeficiency Virus','HIV'],['Human Immuno-deficiency Virus','HIV'],
    ['Healthy Participants','HV'],['Healthy Adults','HV'],
    ['Pulmonary Embolism','PE'],['Pulmonary Hypertension','PH'],
    ['Cytokine Release Syndrome','CytRS'],
    ['Kidney Transplantation','Kidney Tx'],['Kidney Transplant','Kidney Tx'],
    ['Liver Transplant Rejection','Liver Tx Rej.'],
    ['Knee Osteoarthritis','Knee OA'],['Erosive Hand Osteoarthritis','Erosive Hand OA'],['Osteoarthritis','OA'],
    ['Thrombocytopenia','TCP'],
    ['Chronic Bronchitis','Chr. Bronchitis'],
    // ── Gastric / GI oncology forms ──
    // Compound GC/GEJ forms — must precede individual matches
    ['Gastric or Esophagogastric Junction Adenocarcinoma','GC/GEJ AdCa'],
    ['Gastric or Gastroesophageal Junction Adenocarcinoma','GC/GEJ AdCa'],
    ['Gastric or Gastroesophageal Adenocarcinoma','GC/GEJ AdCa'],
    ['Locally Advanced or Metastatic GC and GCJ Adenocarcinoma','GC/GEJ AdCa (LA/Met.)'],
    ['Locally Advanced and Metastatic GC and GCJ Adenocarcinoma','GC/GEJ AdCa (LA/Met.)'],
    // Peritoneal met "From GC" forms — map whole phrase to avoid "From GC" residue
    ['Peritoneal Metastases From Gastric Cancer','Perit. Met.'],
    ['Peritoneal Metastases from Gastric Cancer','Perit. Met.'],
    ['Peritoneal Metastasis From Gastric Cancer','Perit. Met.'],
    ['Peritoneal Metastasis from Gastric Cancer','Perit. Met.'],
    // Stage-qualified GC forms
    ['Gastric Cancer Stage IV','GC (St.IV)'],['Gastric Cancer, Stage IV','GC (St.IV)'],
    ['Gastric Cancer Stage III','GC (St.III)'],['Gastric Cancer Stage II','GC (St.II)'],
    // LA/Met GC (already-abbreviated DB values)
    ['Locally Advanced or Metastatic GC','GC (LA/Met.)'],
    ['Locally Advanced and Metastatic GC','GC (LA/Met.)'],
    // Post-substitution "Gastric or GEJ" forms
    // (GEJ AdCa rule at line ~13217 runs first and converts Gastroesophageal → GEJ,
    //  so we also catch the intermediate "Gastric or GEJ ..." forms here)
    ['Gastric or GEJ AdCa','GC/GEJ AdCa'],
    ['Gastric or GEJ Adenocarcinoma','GC/GEJ AdCa'],
    ['Gastric or GEJ Cancer','GC/GEJ'],
    // GCJ forms not otherwise mapped
    ['GCJ Adenocarcinoma','GC/GEJ AdCa'],['GCJ Cancer','GC/GEJ'],['GCJ','GEJ'],
    // Standard GEJ
    ['Metastatic Gastro-esophageal Adenocarcinoma','Met. GEJ AdCa'],
    ['Esophagogastric Junction Adenocarcinoma','GEJ AdCa'],
    ['GEJ Adenocarcinoma','GEJ AdCa'],
    ['Non Muscle Invasive Bladder Cancer','NMIBC'],
    ['Clear Cell Renal Cell Cancer','ccRCC'],
    ['High Risk Smoldering Multiple Myeloma','HR-SMM'],['Smoldering Multiple Myeloma','SMM'],
    ['Waldenstrom Macroglobulinaemia','WM'],["Waldenström Macroglobulinemia",'WM'],['Waldenstrom Macroglobulinemia','WM'],
    ['Leucine-Rich Glioma Inactivated 1 Autoimmune Encephalitis','LGI1-AE'],
    ['Delayed Graft Function','DGF'],
    ['Cardiovascular Events','CV Events'],
    ['Pediatric Autoimmune','Ped. AI'],
    ['Asthma, Allergic','Allergic Asthma'],
    ['COPD Exacerbation','COPD Exac.'],['COPD Acute Exacerbation','AECOPD'],
    ['Acute Respiratory Failure','ARF'],
    ['COVID-19 Pneumonia','COVID Pneu.'],
    ['Uncontrolled Asthma','Unctrl. Asthma'],
    ['Vulvovaginal Candidiasis','VVC'],
    ['Cognitive Decline','Cog. Dec.'],
    ['Osteo Arthritis Knee','Knee OA'],
    ['Malignant Neoplasms of Digestive Organs','Dig. Malig.'],
    ['Pulmonary Embolism','PE'],
    // ── Generic trial condition qualifiers ──
    ['Flare Up','Flare'],['Inflammation','Inflam.'],
    // ── Generic disease-qualifier prefix (catch-all — must be last) ──
    // Applied after specific disease names are already abbreviated
    ['Locally Advanced or Metastatic ','LA/Met. '],
    ['Locally Advanced and Metastatic ','LA/Met. '],
    ['Locally Advanced ','LA '],
    // Fallback: standalone Adenocarcinoma not caught by specific rules above
    ['Adenocarcinoma','AdCa'],
   ];
   // Split on separators, abbreviate each part, deduplicate
   const _sepRe = /\s*(?:·|•|\bAND\b)\s*/i;
   const parts = str.split(_sepRe).map(p => p.trim()).filter(Boolean);
   const abbrevPart = p => {
    let r = p;
    _IM.forEach(([long, abbr]) => {
     r = r.replace(new RegExp(long.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'), 'gi'), abbr);
    });
    // Remove parenthetical that duplicates what precedes: "CRSwNP (CRSwNP)" → "CRSwNP"
    r = r.replace(/\b(\S+)\s+\(\1\)/gi, '$1');
    // Severity/activity qualifiers → compact prefix
    r = r.replace(/\bPrimary\s+(pSS)\b/gi, '$1');
    // Strip acronym-expansion parens: "(RMS)", "(PMS)", "(RA)" etc — short all-caps in parens
    r = r.replace(/\s*\([A-Z]{2,6}\)/g, '');
    // Strip expansion parentheticals: "SLE (Systemic Lupus)" → "SLE", "RA (RA" → "RA"
    r = r.replace(/\s*\(Systemic\s+Lupus[^)]*\)?/gi, '');
    r = r.replace(/\b([A-Z][A-Za-z\/]{1,8})\s+\(\1[^)]*\)?/g, '$1');
    // Strip pSS artifact suffixes: "pSS's Syndrome" → "pSS", "pSS Disease" → "pSS"
    r = r.replace(/\bpSS('s)?\s+(Syndrome|Disease|Disorder)\b/gi, 'pSS');
    r = r.replace(/\bhealthy\s+(?:adult\s+|normal\s+|male\s+|female\s+)?(?:subjects?|volunteers?)\b/gi, 'HV');
    r = r.replace(/\bHealthy\s+Vol\.?\b/g, 'HV');
    r = r.replace(/\bModerately\s+to\s+Severely\s+Active\s+/gi, 'Mod-Sev ');
    r = r.replace(/\bModerate\s+to\s+Severe\s+/gi, 'Mod-Sev ');
    r = r.replace(/\bMild\s+to\s+Moderate\s+/gi, 'Mild-Mod ');
    r = r.replace(/\bSeverely\s+Active\s+/gi, 'Sev. ');
    r = r.replace(/\bMild\s+to\s+Severely\s+Active\s+/gi, 'Mild-Sev ');
    // Strip WHO/AJCC/ICD versioning qualifiers that add no abbreviation value
    r = r.replace(/\s*[,\-]\s*World\s+Health\s+Organization[^)]*?Class\s+[IVX]+/gi, '');
    r = r.replace(/\s*\([^)]*\bWHO\b[^)]*\)/gi, '');
    r = r.replace(/\s*[,\-]\s*AJCC[^,·]*/gi, '');
    r = r.replace(/\s+AJCC\s+v?\d+/gi, '');
    r = r.replace(/\bClinical\s+Stage\s+[IVX]+\s*/gi, '');
    r = r.replace(/\s*HPV-Mediated\s*\([^)]*\)/gi, ' (HPV+)');
    r = r.replace(/\s*\(p16[^)]*\)/gi, '');
    r = r.replace(/\s*\(Diagnosis\)/gi, '').replace(/\s*\(Only[^)]*\)/gi, '');
    r = r.replace(/\s{2,}/g, ' ').trim();
    // Strip "from [ABBREV]" suffixes that are redundant when disease appears elsewhere in string
    // e.g. "Perit. Met. From GC" → "Perit. Met." when GC already shown in another segment
    r = r.replace(/\s+[Ff]rom\s+[A-Z][A-Z0-9\/]{1,6}\b/g, '');
    // Strip leftover qualifier noise and suffix junk
    r = r.replace(/\s*,\s*Clinical Stage.*/i,'').replace(/\s*·\s*HPV.*/i,'').trim();
    return r;
   };
   const abbrevParts = parts.map(abbrevPart);
   // Deduplicate identical parts after abbreviation (e.g. "EoE · EoE")
   const seen = new Set();
   const deduped = abbrevParts.filter(p => { const k = p.toLowerCase(); if (seen.has(k)) return false; seen.add(k); return true; });
   const joined = deduped.join(' · ');
   // Collapse MG family: if both "MG" and "gMG"/"oMG" present, drop plain "MG"
   const hasMGSubtype = /\b(gMG|oMG)\b/.test(joined);
   // Collapse Asthma family: drop plain "Asthma" when a subtype is present
   const hasAsthmaSubtype = /\b(Eo-Asthma|Sev\.\s*Asthma|Allergic\s+Asthma|Acute\s+Asthma)\b/.test(joined);
   const _dropParent = (s, parent) => s.split(' · ').filter(p => p.trim() !== parent).join(' · ').trim();
   const hasNHLSubtype = /\br\/r\s+NHL\b/.test(joined);
   let result = joined;
   if (hasMGSubtype) result = _dropParent(result, 'MG');
   if (hasAsthmaSubtype) result = _dropParent(result, 'Asthma');
   if (hasNHLSubtype) result = _dropParent(result, 'NHL');
   // GC/GEJ family collapse: if a composite GC/GEJ form is present, drop redundant simpler
   // GC-only variants (GC, GC Stage..., GC (qualifier), GAdCa, GEJ, GEJ AdCa, LA/Met. GC)
   // so display shows e.g. "GC/GEJ AdCa · Perit. Met." instead of "GC St.IV · Perit. Met. · GC/GEJ AdCa"
   const hasGCGEJCombo = /\bGC\/GEJ\b/.test(result);
   if (hasGCGEJCombo) {
    result = result.split(' · ').filter(p => {
     const t = p.trim();
     if (t === 'GC' || t === 'GAdCa' || t === 'GEJ AdCa' || t === 'GEJ') return false;
     if (/^GC[\s(]/.test(t)) return false; // "GC Stage IV", "GC (St.IV)", "GC (LA/Met.)"
     if (/^LA\/Met\.\s+GC\b/.test(t)) return false;
     return true;
    }).join(' · ').trim();
   }
   // Stage 2: collapse intra-part comma duplicates ("TED, TED" → "TED")
   result = result.split(' · ').map(p => {
    const sub = p.split(/\s*,\s*/).map(s => s.trim()).filter(Boolean);
    const uniqSub = [...new Set(sub.map(s => s.toLowerCase()))].map(k => sub.find(s => s.toLowerCase()===k));
    return uniqSub.length === 1 ? uniqSub[0] : p;
   }).join(' · ');
   // Stage 3: cross-part dedup after intra-part collapse
   const finalSeen = new Set();
   result = result.split(' · ').filter(p => { const k=p.trim().toLowerCase(); if(finalSeen.has(k))return false; finalSeen.add(k); return true; }).join(' · ');
   return result;
  };

  // ── Trial note: meaningful descriptor from design/dosing/route ──
  const _trialNote = t => {
   if (t.trial_note) return t.trial_note.slice(0, 22);
   const dt = (t.dosing_type || '').trim();
   if (dt && dt.length <= 22) return dt;
   const route = (t.route || '').trim().toLowerCase();
   if (route) {
    if (route.includes('subcutan')) return 'SC';
    if (route.includes('intraven')) return 'IV';
    if (route === 'oral' || route === 'po' || route.includes('oral')) return 'Oral';
    if (route.includes('intramuscul')) return 'IM';
   }
   const nm = (t.trial_name || '').toLowerCase();
   if (/\bole\b|open.label extension|long.term extension/.test(nm)) return 'OLE/Ext.';
   if (/\bregistry\b/.test(nm)) return 'Registry';
   if (/dose.rang|dose.find/.test(nm)) return 'Dose-ranging';
   if (/double.blind/.test(nm)) return 'Double-blind';
   if (/open.label/.test(nm)) return 'Open-label';
   if (/pharmacokinetic|\bpk\b/.test(nm)) return 'PK/PD';
   if (/\bsafety\b/.test(nm)) return 'Safety';
   if (/\befficacy\b/.test(nm)) return 'Efficacy';
   const clean = nm.replace(/\b(a |an |the |phase |study |of |in |for |with |and |evaluating |assessing |investigating |examining )/gi,'').trim();
   const words = clean.split(/\s+/).filter(w => w.length > 2);
   if (words.length) return words.slice(0,2).map(w=>w.charAt(0).toUpperCase()+w.slice(1)).join(' ');
   return '';
  };

  // ── Group drugs + combos into three portfolio tiers ───────────────────────
  // Tier is determined by drug.overlap (DB field), combo.overlap (DB field), or static _overlap.
  // Sort by competitive relevance (very_high → high → medium → low → monitor → null),
  // then by stage within each relevance tier. No tier headers — flat list.
  const _RELEV_SORT_DA = {very_high:0, high:1, medium:2, low:3, monitor:4};
  const stageSortScore = item => {
   const s = (_resolveStage(item)||item.stageKey||item.phase_display||'').toLowerCase();
   if (s.includes('approv')) return 100;
   if (s.includes('3'))      return 80;
   if (s.includes('2'))      return 60;
   if (s.includes('1'))      return 40;
   return 20;
  };
  const allItems = [
   ...drugsToRender.map(d => ({...d, _isCombo: false})),
   ...sbCombos.map(c => ({...c, _isCombo: true, name: c.label || c.name})),
  ].sort((a, b) => {
   // Approved drugs always float to the very top
   const aApp = stageSortScore(a) >= 100 ? 0 : 1;
   const bApp = stageSortScore(b) >= 100 ? 0 : 1;
   if (aApp !== bApp) return aApp - bApp;
   // Then by competitive relevance
   const ar = a.competitive_relevance != null ? (_RELEV_SORT_DA[a.competitive_relevance] ?? 5) : 6;
   const br = b.competitive_relevance != null ? (_RELEV_SORT_DA[b.competitive_relevance] ?? 5) : 6;
   if (ar !== br) return ar - br;
   // Then by stage (Ph3 → Ph2 → Ph1 → earlier)
   return stageSortScore(b) - stageSortScore(a);
  });

  // ── renderNewsItem defined HERE so it is available inside allItemsHTML.map()
  // (const is NOT hoisted — defining after the map causes ReferenceError)
  const typeMap = {financing:'💰 Funding', licensing:'📋 License', partnership:'🤝 Partnership',
                   acquisition:'🏢 Acquisition', news:'📰 News', collaboration:'🤝 Collab',
                   regulatory:'🏥 Regulatory', clinical:'🔬 Clinical'};
  const renderNewsItem = (d, singleLine=false) => {
   // Prefer exact deal_date over deal_date_label (month-year only)
   const date       = fmtExactDate(d.deal_date) || d.deal_date_label || d.date || '';
   const title      = d.headline || d.desc || '';
   const url        = d.source_url || d.url || '';
   const tooltipRaw = d.body || d.headline || d.desc || '';
   const tooltip    = tooltipRaw.replace(/"/g,'&quot;');
   const typeBadge  = d.deal_type && typeMap[d.deal_type]
    ? `<span style="font-size:8px;background:#f0fdf4;color:#166534;border-radius:3px;padding:1px 4px;margin-right:4px;font-weight:700;white-space:nowrap;flex-shrink:0">${typeMap[d.deal_type]}</span>` : '';
   const upfront    = d.upfront_usd_m ? `<span style="font-size:9px;color:#166534;font-weight:700;margin-left:4px;white-space:nowrap;flex-shrink:0">$${d.upfront_usd_m}M</span>` : '';
   if (singleLine) {
    return `<div title="${tooltip}" style="display:flex;align-items:center;gap:5px;padding:3px 0;border-bottom:1px solid #f1f5f9;overflow:hidden;min-height:22px;cursor:default">
     <span style="font-size:9px;color:#64748b;white-space:nowrap;flex-shrink:0;font-weight:600;min-width:70px">${date}</span>
     ${typeBadge}
     <span style="font-size:10.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;min-width:0">${url?`<a href="${url}" target="_blank" rel="noopener" style="color:#1d4ed8;text-decoration:none">${title} ↗</a>`:title}</span>
     ${upfront}
    </div>`;
   }
   const titleEl = url
    ? `<a href="${url}" target="_blank" rel="noopener" style="color:#1d4ed8;text-decoration:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0">${title} ↗</a>`
    : `<span style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0">${title}</span>`;
   return `<div class="pi-detail-cat-item" title="${tooltip}" style="cursor:default">
    <span class="pi-detail-cat-date">${date}</span>
    <span style="font-size:11px;display:flex;align-items:center;gap:3px;overflow:hidden;min-width:0;flex:1">${typeBadge}${titleEl}${upfront}</span>
   </div>`;
  };

  // ── Hoisted helpers — must be declared BEFORE allItems.map so both the combo
  //    branch and the drug branch can reference them without TDZ errors.
  const _parsePcdTs = t => {
   const raw = t.primary_completion_date || t.pcd_label || t.pcd || '';
   if (!raw) return 0;
   const _d = new Date(raw + (raw.length === 10 ? 'T12:00:00Z' : ''));
   if (!isNaN(_d)) return _d.getTime();
   const qm = raw.match(/Q([1-4])\s*(\d{4})/i);
   if (qm) return Date.UTC(+qm[2], (+qm[1]-1)*3+2, 15);
   const hm = raw.match(/H([12])\s*(\d{4})/i);
   if (hm) return Date.UTC(+hm[2], hm[1]==='1'?2:8, 15);
   const ym = raw.match(/\b(\d{4})\b/);
   if (ym) return Date.UTC(+ym[1], 6, 1);
   return 0;
  };
  const _pcdCountdown = (t, status) => {
   const isOngoing = /recruit|active|enrolling|not yet/i.test(status) && !/complet|terminat/i.test(status);
   if (!isOngoing) return '<span></span>';
   const ts = _parsePcdTs(t);
   if (!ts) return '<span></span>';
   const days = Math.ceil((ts - Date.now()) / 86400000);
   if (days <= 0) return '<span style="font-size:9px;color:#94a3b8;text-align:center;display:block">past PCD</span>';
   const col = days < 180 ? '#dc2626' : days < 365 ? '#d97706' : '#64748b';
   return `<span style="font-size:9px;font-weight:700;color:${col};text-align:center;white-space:nowrap;display:block">${days}d</span>`;
  };

  const allItemsHTML = allItems.map(item => {

   // ── Combination program branch ─────────────────────────────────────────
   if (item._isCombo) {
    const combo = item;
    const _isTerminalTrial = s => /complet|terminat|withdrawn|suspend/i.test(s||'');
    const comboTrials = [...(trialsByCombo[combo.id] || [])].sort((a,b) => {
     const aT=_isTerminalTrial(a.status),bT=_isTerminalTrial(b.status);
     if (aT!==bT) return aT?1:-1;
     const ta=_parsePcdTs(a)||Infinity,tb=_parsePcdTs(b)||Infinity; return ta-tb;
    });
    const comboTrialHeader = comboTrials.length ? `<div class="pi-tr-header"><span></span><span>NCT</span><span>Acronym</span><span>Phase</span><span>Indication</span><span>Note</span><span>Status</span><span>PCD</span><span style="text-align:center">Days</span></div>` : '';
    const comboTrialRowsHTML = comboTrials.map(t => {
     const nct    = t.nct_id || t.nct || t.id || '';
     const acronym = t.study_acronym || '';
     const status = t.status || '';
     const _pRaw = (t.phase||'').replace(/\s*\/\s*/g,'/').trim();
     const _pAbbr = {observational:'Obs',expanded:'Exp.','not applicable':'—','n/a':'—','open label':'Open-label'};
     const phaseDisplay = !_pRaw ? '—' : /^early\s+(phase\s*)?\d/i.test(_pRaw) ? `EPh ${_pRaw.replace(/^early\s+(phase\s*)?/i,'')}` : (r=>!r?'—':/\d/.test(r)?`Ph ${r}`:(_pAbbr[r.toLowerCase()]||r.slice(0,5)))(_pRaw.replace(/Phase\s*/gi,'').trim());
     const pcd    = fmtPcd(t.primary_completion_date || t.pcd_label || t.pcd || '');
     const _nctComboMatch = (nct+'').match(/NCT\d{6,}/i);
     const _nctComboId = _nctComboMatch ? _nctComboMatch[0].toUpperCase() : null;
     const nctLink = _nctComboId
      ? `<span class="pi-nct-a" style="cursor:pointer" onclick="event.stopPropagation();window.open('https://clinicaltrials.gov/study/${_nctComboId}','_blank')">${_nctComboId}</span>`
      : `<span style="font-size:10px;color:#94a3b8">${nct||'—'}</span>`;
     const acronymCell = `<span class="pi-tr-acronym-cell">${acronym?`<span class="pi-tr-acronym">${acronym}</span>`:''}</span>`;
     const comboInd = t.indication || t.condition || '';
     const noteText = _trialNote(t);
     return `<div class="pi-tr-item"><div class="pi-tr-row" onclick="piToggleTrialRow(this)">
      <span class="pi-tr-chev">▼</span>${nctLink}${acronymCell}
      <span class="pi-tr-phase-cell">${phaseDisplay}</span>
      <span class="pi-tr-ind-cell" title="${comboInd}">${_abbrevInd(comboInd)||comboInd||'—'}</span>
      <span class="pi-tr-note-cell" title="${noteText}">${noteText||'—'}</span>
      <span class="pi-trial-status ${trialStatusCls(status)}">${status||'—'}</span>
      <span class="pi-tr-pcd-cell">${pcd}</span>${_pcdCountdown(t, status)}
     </div><div class="pi-tr-detail"><div class="pi-td-card">${(t.trial_name||t.name)?`<div class="pi-td-name">${t.trial_name||t.name}${_trialNote(t)?`<span style="margin-left:8px;font-size:9px;font-weight:600;background:#f1f5f9;color:#64748b;border-radius:10px;padding:2px 8px;vertical-align:middle">${_trialNote(t)}</span>`:''}</div>`:''}${(()=>{const chips=[];const _r=(t.route||'').trim();if(_r)chips.push(`<span class="pi-td-reg-chip route">${_r.toUpperCase()}</span>`);const _dl=t.dose_levels||t.dose_amount||'';if(_dl)chips.push(`<span class="pi-td-reg-chip dose">${_dl}</span>`);const _df=t.dosing_frequency||t.dosing_schedule||t.dosing||'';if(_df)chips.push(`<span class="pi-td-reg-chip freq">${_df}</span>`);const _cmp=t.comparator||t.control_arm||'';if(_cmp)chips.push(`<span class="pi-td-reg-chip comparator">vs. ${_cmp}</span>`);return chips.length?`<div class="pi-td-regimen">${chips.join('')}</div>`:'';})()}${(t.enrollment||t.enrollment_count)?`<div class="pi-td-stats"><div class="pi-td-stat"><div class="pi-td-stat-lbl">Enrollment</div><div class="pi-td-stat-val">N=${t.enrollment||t.enrollment_count}</div></div></div>`:''}</div></div></div>`;
    }).join('');
    const isPlannedStage = (combo.stage||'').startsWith('Planned');
    const plannedSrcLink = combo.source_url
      ? `<a href="${combo.source_url}" target="_blank" rel="noopener" onclick="event.stopPropagation()" style="color:#0369a1;font-weight:700;font-style:normal;text-decoration:underline;margin-left:6px">Source ↗</a>`
      : `<span style="color:#f97316;font-weight:700;font-style:normal;margin-left:6px" title="No source URL on file — data quality risk">⚠ No source</span>`;
    const anticipatedStr = combo.anticipated_start
      ? `<span style="font-style:normal;color:#475569"> · Anticipated: <strong>${combo.anticipated_start}</strong></span>`
      : '';
    const prereqNote = combo.prerequisite_note
      ? `<div style="font-size:11px;color:#92400e;background:#fef9c3;border:1px solid #fde68a;border-radius:4px;padding:4px 10px;margin-top:6px;display:inline-block">⚠ Prerequisite: ${combo.prerequisite_note}</div>`
      : '';
    const comboTrialSection = comboTrials.length
     ? `<div class="pi-tr-hd-label">Clinical Trials (${comboTrials.length})</div>${comboTrialHeader}<div>${comboTrialRowsHTML}</div>`
     : isPlannedStage
       ? `<div style="font-size:11px;color:#0369a1;padding:4px 0;font-style:italic">Study planned — no trial registration yet${anticipatedStr}${plannedSrcLink}</div>${prereqNote}`
       : `<div style="font-size:11px;color:#94a3b8;padding:4px 0">No trials linked yet</div>`;
    const stagePill = this._stagePill(combo.stage || '');
    const comboInd  = _abbrevInd(combo.indication_short) || '—';
    // Display name: drug names only — strip em-dash suffix, parenthetical targets, and leading "CODE: " prefix
    // e.g. "SPY230: SPY002 + SPY003 (TL1A + IL-23p19) — SKYLINE Part B" → "SPY002 + SPY003"
    const comboDisplayName = _dknCleanName((combo.label||'')
      .replace(/\s+[—–-]{1,2}\s+.*$/, '')  // strip " — SKYLINE Part B" and similar
      .replace(/\s*\([^)]*\)\s*$/, '')      // strip trailing "(targets)"
      .trim()) || combo.label || '—';
    // Extract targets from ANY parenthetical in label — not just trailing, handles "(...) — suffix" format
    const comboTargetMatch = (combo.label||'').match(/\(([^)]+)\)/);
    const comboTargetRaw = comboTargetMatch ? comboTargetMatch[1] : '';
    const comboTarget = comboTargetRaw
      .replace(/\s*(?:sequential\s+)?combo\s*$/i, '')
      .replace(/\s+sequential\s*$/i, '')
      .trim();
    // Source link lives only in the accordion body, not the header
    const comboBodySrcLink = combo.source_url
     ? `<a href="${combo.source_url}" target="_blank" rel="noopener" style="color:#1d4ed8;font-size:11px;font-weight:700;text-decoration:none">Source ↗</a>` : '';
    const comboTypeLabel = (combo.combination_type||'').replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
    const hasBody   = combo.mechanism_detail || combo.drug_summary || comboTrials.length || combo.source_url;
    const comboDesc = combo.drug_summary || combo.mechanism_detail || '';
    const comboDescStrip = comboDesc ? `<div class="pi-da-desc-strip">${firstSentence(comboDesc)}</div>` : '';

    return `<div class="pi-da-row">
     <div class="pi-da-hd" onclick="piToggleDrugRow(this)">
      <span class="pi-da-toggle" style="${hasBody?'':'visibility:hidden'}">▶</span>
      <span class="pi-da-name">${comboDisplayName}</span>
      <span class="pi-da-mech">${comboTarget}</span>
      <div class="pi-da-stage">${stagePill}</div>
      <div class="pi-da-pills"><span class="pi-da-tag" style="background:#f0fdf4;color:#15803d;border-color:#bbf7d0">${comboInd}</span></div>
      <div class="pi-da-partner"></div>
     </div>
     ${hasBody?`<div class="pi-da-body">
      ${comboDescStrip}
      <div>
       ${comboTypeLabel?`<div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:#94a3b8;margin-bottom:8px">${comboTypeLabel}${comboBodySrcLink?` · ${comboBodySrcLink}`:''}</div>`:(comboBodySrcLink?`<div style="margin-bottom:8px">${comboBodySrcLink}</div>`:'')}
       ${comboTrialSection}
      </div>
     </div>`:''}
    </div>`;
   }

   // ── Regular drug branch ────────────────────────────────────────────────
   const d = item;
   // Use __all__ only when there's a single drug (no ambiguity about ownership).
   // For static fallback rows, prefer the per-entry _staticTrials if set.
   const drugTrials = trialsByDrug[d.id] || trialsByDrug[d.canonical_drug_id]
     || ((drugsToRender.length <= 1 || (!sbTrials.length && drugsToRender.indexOf(d) === 0))
       ? (trialsByDrug['__all__'] || []) : [])
     || (d._staticTrials ? d._staticTrials.map(t=>({...t,id:t.id||t.nct})) : []);
   const resolvedTrials = drugTrials.length ? drugTrials
     : (d._staticTrials ? d._staticTrials.map(t=>({...t,id:t.id||t.nct})) : []);
   // Drug row header fields: Name | Target | Phase | Indication | [partner tag]
   // RULE: Always prefer d.target (clean notation e.g. "TL1A", "IL-23p19") over d.mechanism
   // (verbose description like "Anti-TL1A mAb"). Mechanism belongs in the expanded detail only.
   // cleanTarget: strips everything after first semicolon (company credits), parentheticals,
   // modality suffixes ("bispecific antibody", "mAb"), ALL co-dev/company patterns,
   // then normalises × / + spacing. Target col = targets only, no annotations.
   const cleanTarget = s => (s||'')
    .replace(/;.*/g, '')                                                          // strip "; anything after semicolon"
    .replace(/,\s*[^,×+]+co-dev[^,]*/gi, '')                                    // strip ", Company/Company co-dev" variants
    .replace(/\s+co-dev\b.*/gi, '')                                              // strip trailing "co-dev" and anything after
    .replace(/\s*[-–—]\s*[A-Za-z][^×+,;]*(co-?developed|co-?dev|originated)[^×+,;]*/gi, '') // strip "– Roche-originated; co-developed with X"
    .replace(/\s*\([^)]*\)\s*/g, ' ')                                            // strip parenthetical notes
    .replace(/\s*(bi-?specific\s*antibody|bi-?specific|antibody|mAb)\s*/gi, ' ')
    .replace(/\s*[×x]\s*/g, ' × ')
    .replace(/\s*\+\s*/g, ' + ')
    .replace(/\s+/g, ' ')
    .trim();

   const drugTarget   = cleanTarget(d.target || d.mechanism || prog.target || '—');
   const drugPhase    = _resolveStage(d) || d.phase_display || prog.stageKey || '';
   const drugInd      = _abbrevInd(d.indication_short) || '—';
   // partner_company comes from Supabase drug record (DB-loaded) or static _partnerCo fallback.
   // Final fallback: for licensed_in/co_developed/collaboration deals, derive from licensor_name.
   // _shortenPartner: known abbreviations first, then strip bio/pharma suffixes → first meaningful name only.
   const _shortenPartner = name => {
    if (!name) return name;
    // Strip parenthetical annotations first (e.g. "(Roivant Sciences / Pfizer JV)")
    name = name.replace(/\s*\([^)]*\)/g, '').trim();
    const _MAP = {
     'Boehringer Ingelheim': 'BI', 'Simcere Pharmaceutical': 'Simcere', 'Simcere': 'Simcere',
     'Prometheus Biosciences': 'Prometheus', 'FutureGen Biopharmaceutical': 'FutureGen',
     'FutureGen Biopharmaceutical Co., Ltd.': 'FutureGen', 'Teva Pharmaceutical': 'Teva',
     'Telavant Holdings': 'Telavant', 'Qyuns Therapeutics': 'Qyuns', 'Earendil Pharmaceuticals': 'Earendil',
     'Zymeworks Inc.': 'Zymeworks', 'Novamab': 'Novamab', 'Sanofi-Aventis': 'Sanofi',
    };
    if (_MAP[name]) return _MAP[name];
    // Strip common legal/pharma suffixes — including Biologics, Biotherapeutics, Bio, Labs etc.
    return name.replace(/[,\s]+(Biotherapeutics?|Biosciences?|Biopharmaceuticals?|Biologics?|Biotechnology|Technologies?|Pharmaceutical(s)?|Pharma|Biopharma|Therapeutics?|Holdings?|Sciences?|Labs?|Co\.?,?\s*Ltd\.?|Inc\.?|LLC|Corp\.?|GmbH|S\.A\.|B\.V\.|Limited)\.?\s*$/i,'').trim();
   };
   const _trimLegal = s => s ? s.replace(/[,\s]+(Co\.?,?\s*Ltd\.?|Inc\.?|LLC|Corp\.?|GmbH|S\.A\.|B\.V\.)\.?\s*$/i,'').trim() : null;
   // _isOwnershipPill: true when pill source is the ownership chain (acquired/licensed asset),
   // not a traditional partner_company field. Ownership-derived pills never show "?" because
   // the acquisition or licensing event itself is the confirmation.
   const _hasDirectPartner = !!(d.partner_company || d._partnerCo ||
     (d.partnership_type && d.partnership_type !== 'self' && d.licensor_name));
   const _partnerCo   = d.partner_company || d._partnerCo
    || ((d.partnership_type && d.partnership_type !== 'self') ? _trimLegal(d.licensor_name) : null)
    // ownership model: show originator pill for acquired/licensed assets
    || ((d.ownership_status && d.ownership_status !== 'originated') ? (d.display_partner_name || null) : null)
    // ATH fallback: if an asset_transfer_history chain exists and the originator ≠ current display
    // entity, use the ATH originator as the inferred partner (e.g. HXN-1002/HXN-1003 → Earendil)
    || (() => {
      const _ath = athByDrugId?.[d.id];
      if (!_ath?.length) return null;
      const _orig = _ath[0].from_entity_name;
      const _cN = s => (s||'').toLowerCase().replace(/[_\-\s]+/g,'');
      return (_orig && _cN(_orig) !== _cN(d.co)) ? _orig : null;
    })()
    || null;
   const _isOwnershipPill = !_hasDirectPartner && !!(d.ownership_status && d.ownership_status !== 'originated');
   const _partnerShort = _partnerCo ? _shortenPartner(_partnerCo) : null;
   // Self-attribution guard: suppress pill when the partner is the same entity we're already
   // grouped under (e.g. fg-m701 grouped under AbbVie showing "w/ AbbVie" is redundant).
   // Exact match first, then first-token match to handle hyphenated variants (Sanofi-Aventis vs Sanofi).
   const _entityShort = d.co ? _shortenPartner(d.co) : '';
   const _ft = s => s ? s.split(/[-\s]/)[0] : s;
   const _coIdNorm = s => (s || '').toLowerCase().replace(/[_\-\s]+/g, '');
   // Self-attribution guard: suppress when partner = the entity we're viewing FROM.
   // Use prog.entity_id (slug) + prog.co (display name) — NOT d.company_id (the drug's originator).
   // d.company_id caused false suppression for licensed drugs where originator === partner
   // (e.g. HXN-1002/erd-1 company_id='earendil', display_partner_name='Earendil' → wrongly suppressed).
   const _partnerMatchesEntity = !!(_partnerShort && (
     (_entityShort && _partnerShort.toLowerCase() === _entityShort.toLowerCase()) ||
     (_entityShort && _ft(_partnerShort.toLowerCase()) === _ft(_entityShort.toLowerCase()) && _ft(_partnerShort.toLowerCase()).length >= 3) ||
     (prog?.company_id && _coIdNorm(_partnerShort) === _coIdNorm(prog.company_id)) ||
     (prog?.co && _coIdNorm(_partnerShort) === _coIdNorm(prog.co))
   ));
   // Co-dev inversion: when primary partner_company = viewing entity (self-attribution fires),
   // but the drug was originated by a DIFFERENT company, show that originator as the pill instead.
   // Example: itepekimab has partner_company="Sanofi" (recorded from Regeneron's POV). When Sanofi
   // views their card, the guard kills "w/ Sanofi" but we should show "w/ Regeneron" instead.
   let _finalPartnerShort = _partnerShort;
   let _finalPartnerCo    = _partnerCo;
   let _suppressPill      = _partnerMatchesEntity;
   if (_partnerMatchesEntity && d.company_id && _coIdNorm(d.company_id) !== _coIdNorm(prog?.company_id || '')) {
     const _altCo    = d.entity_name || d.company_id;
     const _altShort = _altCo ? _shortenPartner(_altCo) : null;
     const _altSelf  = _altShort && (
       (prog?.company_id && _coIdNorm(_altShort) === _coIdNorm(prog.company_id)) ||
       (prog?.co         && _coIdNorm(_altShort) === _coIdNorm(prog.co))
     );
     if (_altShort && !_altSelf) {
       _finalPartnerShort = _altShort;
       _finalPartnerCo    = _altCo;
       _suppressPill      = false;
     }
   }
   // partnership_verified: true=confirmed (blue), null=unverified (gray "?"), false=flagged (amber "?")
   // Ownership-derived pills are always treated as confirmed — the acquisition IS the confirmation.
   const _pv = _isOwnershipPill ? true : d.partnership_verified;
   const _pvColor   = _pv === true  ? {c:'#1d4ed8',bg:'#eff6ff',br:'#bfdbfe',lbl:'Confirmed partnership — click to manage'}
                    : _pv === false ? {c:'#92400e',bg:'#fffbeb',br:'#fcd34d',lbl:'Flagged unconfirmed by enrichment — click to confirm or remove'}
                    :                 {c:'#64748b',bg:'#f8fafc',br:'#cbd5e1',lbl:'Partnership not yet verified — click to confirm or remove'};
   const _pvMark    = _pv === true ? '' : ' ?';
   const partnerTag = (_finalPartnerShort && !_suppressPill)
    ? `<span class="pi-partner-pill" data-drug-id="${d.id||''}" data-partner="${(_finalPartnerCo||'').replace(/"/g,'&quot;')}" data-pv="${_pv}" onclick="piConfirmPartner(this,event)" style="font-size:9px;cursor:pointer;color:${_pvColor.c};background:${_pvColor.bg};border:1px solid ${_pvColor.br};border-radius:8px;padding:1px 6px;white-space:nowrap" title="${_pvColor.lbl}">w/ ${_finalPartnerShort}${_pvMark}</span>`
    : '';
   const overlapTag   = d._overlap && d._overlap !== (prog.overlap||'') ? this._ovBadge(d._overlap) : '';

   // Show ALL trials — active first (by PCD), then completed/terminated (muted visually).
   // Filtering out completed trials caused "CLINICAL TRIALS (3)" to show with zero visible rows
   // whenever all trials for a drug were historical. Now count and rows always match.
   const _isTermTrial = s => /complet|terminat|withdrawn|suspend/i.test(s||'');
   const sortedTrials = [...resolvedTrials].sort((a,b) => {
    const aT = _isTermTrial(a.status), bT = _isTermTrial(b.status);
    if (aT !== bT) return aT ? 1 : -1; // active trials float to top
    const ta=_parsePcdTs(a)||Infinity,tb=_parsePcdTs(b)||Infinity; return ta-tb;
   });

   // Column header row (rendered once above the trial items)
   const trialHeader = sortedTrials.length ? `<div class="pi-tr-header">
    <span></span><span>NCT</span><span>Acronym</span><span>Phase</span><span>Indication</span><span>Note</span><span>Status</span><span>PCD</span><span style="text-align:center">Days</span>
   </div>` : '';

   // Trial rows — built as array so active and completed can be sectioned separately
   const _allTrialRowsArr = sortedTrials.map(t => {
    const nct     = t.nct_id || t.nct || t.id || '';
    const name    = t.trial_name || t.name || '';
    const acronym = t.study_acronym || '';
    const status  = t.status || '';
    const phase   = t.phase || '';
    const n       = t.n_enrollment || t.enrollment || t.n;
    // Prefer full YYYY-MM-DD from primary_completion_date; pcd_label as fallback
    const pcdRaw  = t.primary_completion_date || t.pcd_label || t.pcd || '';
    const pcd     = fmtPcd(pcdRaw);
    const ind     = t.indication || t.condition || '';
    const route   = t.route || d.route || '';
    const dosing  = t.dosing_type || d.dosing_type || '';
    const ep       = t.primary_endpoint || t.primary || '';
    const estimand = t.estimand || '';
    const results  = t.results_note || t.results_summary || '';
    const hasResults = results || status.toLowerCase().includes('complet');

    const countdownCell = _pcdCountdown(t, status);

    const _nctDrugMatch = (nct+'').match(/NCT\d{6,}/i);
    const _nctDrugId = _nctDrugMatch ? _nctDrugMatch[0].toUpperCase() : null;
    const nctLink = _nctDrugId
     ? `<span class="pi-nct-a" style="cursor:pointer" onclick="event.stopPropagation();window.open('https://clinicaltrials.gov/study/${_nctDrugId}','_blank')">${_nctDrugId}</span>`
     : `<span style="font-size:10px;color:#94a3b8">${nct||'—'}</span>`;

    // Acronym cell always present — keeps grid column count constant
    const acronymCell = `<span class="pi-tr-acronym-cell">${acronym ? `<span class="pi-tr-acronym">${acronym}</span>` : ''}</span>`;

    // Phase cell — normalize all "Phase X / Phase Y" → "Ph X/Y"
    const _pRaw2 = (phase||'').replace(/\s*\/\s*/g,'/').trim();
    const _pAbbr2 = {observational:'Obs',expanded:'Exp.','not applicable':'—','n/a':'—','open label':'Open-label'};
    const phaseShort = !_pRaw2 ? '—' : /^early\s+(phase\s*)?\d/i.test(_pRaw2) ? `EPh ${_pRaw2.replace(/^early\s+(phase\s*)?/i,'')}` : (r=>!r?'—':/\d/.test(r)?`Ph ${r}`:(_pAbbr2[r.toLowerCase()]||r.slice(0,5)))(_pRaw2.replace(/Phase\s*/gi,'').trim());
    const phaseCell  = `<span class="pi-tr-phase-cell">${phaseShort}</span>`;

    // Extended trial fields — new columns auto-populate when added to Supabase
    const doseLevel    = t.dose_levels    || t.dose_amount   || '';
    const dosFreq      = t.dosing_frequency || t.dosing_schedule || '';
    const comparator   = t.comparator     || t.control_arm   || '';
    const txDuration   = t.treatment_duration || t.duration  || '';
    const keySec       = t.key_secondary_endpoints || t.secondary_endpoints || '';
    const population   = t.population_criteria || t.inclusion_criteria_note || '';
    const studyDesign  = t.study_design   || '';
    const readout      = t.expected_readout || t.data_readout || '';
    const arms         = t.arms_description || t.arm_count ? (t.arms_description || `${t.arm_count} arms`) : '';
    const geoScope     = t.geographic_scope || t.regions || '';

    // Build regimen string: route · dose · frequency (combine what's available)
    const regimenParts = [route, doseLevel, dosFreq || dosing].filter(Boolean);
    const regimenStr   = regimenParts.join(' · ');

    const _fld = (lbl, val, wide) =>
     val ? `<div class="pi-tr-field"${wide?' style="grid-column:1/-1"':''}><span class="pi-tr-field-lbl">${lbl}</span><span class="pi-tr-field-val" style="${wide?'font-weight:400;font-size:11px':''}">${val}</span></div>` : '';

    const detailFields = [
     _fld('Condition', ind),
     _fld('Enrollment', n ? `N = ${n}` : ''),
     _fld('Regimen', regimenStr),
     _fld('Comparator', comparator),
     _fld('Treatment Duration', txDuration),
     _fld('Study Design', studyDesign),
     _fld('Arms', arms),
     _fld('Geographic Scope', geoScope),
     _fld('Population', population, true),
     _fld('Primary Endpoint', ep, true),
     _fld('Key Secondary Endpoints', keySec, true),
     _fld('Estimand', estimand, true),
     readout ? `<div class="pi-tr-field"><span class="pi-tr-field-lbl">Expected Readout</span><span class="pi-tr-field-val" style="font-weight:700;color:#0369a1">${readout}</span></div>` : '',
    ].filter(Boolean).join('');

    const resultsSection = hasResults ? `
     <div class="pi-tr-results-btn" onclick="piToggleTrialResults(this)">📊 Study Results ▾</div>
     <div class="pi-tr-results-body">${results || '<em style="color:#94a3b8">Trial completed — results not yet extracted. Run enrichment pipeline to populate.</em>'}</div>` : '';

    const trialNoteText = _trialNote(t);
    const _isTerm = _isTermTrial(status);
    const termItemStyle = _isTerm ? ' style="opacity:0.55"' : '';
    return `<div class="pi-tr-item"${termItemStyle}>
     <div class="pi-tr-row" onclick="piToggleTrialRow(this)">
      <span class="pi-tr-chev">▼</span>
      ${nctLink}
      ${acronymCell}
      ${phaseCell}
      <span class="pi-tr-ind-cell" title="${ind}">${_abbrevInd(ind)||ind||'—'}</span>
      <span class="pi-tr-note-cell" title="${trialNoteText}">${trialNoteText||'—'}</span>
      <span class="pi-trial-status ${trialStatusCls(status)}">${status||'—'}</span>
      <span class="pi-tr-pcd-cell">${pcd}</span>
      ${countdownCell}
     </div>
     <div class="pi-tr-detail">
      <div class="pi-td-card">
       ${name ? `<div class="pi-td-name">${name}${trialNoteText ? `<span style="margin-left:8px;font-size:9px;font-weight:600;background:#f1f5f9;color:#64748b;border-radius:10px;padding:2px 8px;vertical-align:middle">${trialNoteText}</span>` : ''}</div>` : ''}
       ${(()=>{
        const chips = [];
        if (route) chips.push(`<span class="pi-td-reg-chip route">${route.toUpperCase()}</span>`);
        if (doseLevel) chips.push(`<span class="pi-td-reg-chip dose">${doseLevel}</span>`);
        if (dosFreq||dosing) chips.push(`<span class="pi-td-reg-chip freq">${dosFreq||dosing}</span>`);
        if (comparator) chips.push(`<span class="pi-td-reg-chip comparator">vs. ${comparator}</span>`);
        if (txDuration) chips.push(`<span class="pi-td-reg-chip duration">${txDuration}</span>`);
        return chips.length ? `<div class="pi-td-regimen">${chips.join('')}</div>` : '';
       })()}
       <div class="pi-td-stats">
        <div class="pi-td-stat"><div class="pi-td-stat-lbl">Enrollment</div><div class="pi-td-stat-val">${n ? `N=${n}` : '—'}</div></div>
        <div class="pi-td-stat"><div class="pi-td-stat-lbl">Design</div><div class="pi-td-stat-val">${studyDesign||'—'}</div></div>
        <div class="pi-td-stat"><div class="pi-td-stat-lbl">Arms</div><div class="pi-td-stat-val">${arms||'—'}</div></div>
        <div class="pi-td-stat"><div class="pi-td-stat-lbl">Geography</div><div class="pi-td-stat-val">${geoScope||'—'}</div></div>
       </div>
       ${population ? `<div class="pi-td-section"><div class="pi-td-sec-lbl">Population</div><div class="pi-td-sec-val">${population}</div></div>` : ''}
       ${ep ? `<div class="pi-td-section"><div class="pi-td-sec-lbl">Primary Endpoint</div><div class="pi-td-sec-val">${ep}</div></div>` : ''}
       ${keySec ? `<div class="pi-td-section"><div class="pi-td-sec-lbl">Key Secondary Endpoints</div><div class="pi-td-sec-val">${keySec}</div></div>` : ''}
       ${estimand ? `<div class="pi-td-section"><div class="pi-td-sec-lbl">Estimand</div><div class="pi-td-sec-val">${estimand}</div></div>` : ''}
       ${readout ? `<div class="pi-td-section"><div class="pi-td-sec-lbl">Expected Readout</div><div class="pi-td-sec-val"><span class="pi-td-readout">📅 ${readout}</span></div></div>` : ''}
       ${!population && !ep && !keySec && !estimand && !readout && !(route||doseLevel||dosFreq||dosing||comparator||txDuration) && !n && !studyDesign && !arms && !geoScope ? `<div class="pi-td-empty">Detail not yet enriched — run pipeline to populate</div>` : ''}
       ${resultsSection}
      </div>
     </div>
    </div>`;
   });

   const trialCount = sortedTrials.length;
   const activeCount = sortedTrials.filter(t => !_isTermTrial(t.status)).length;
   const termCount   = trialCount - activeCount;

   // Active trial rows — always fully visible
   const activeTrialRowsHTML = _allTrialRowsArr.slice(0, activeCount).join('');
   // Completed/terminated — show first row only; rest collapse behind a toggle
   const _termRowsArr = _allTrialRowsArr.slice(activeCount);
   const termSection = _termRowsArr.length === 0 ? '' : (() => {
    const first = _termRowsArr[0];
    const rest  = _termRowsArr.slice(1);
    if (rest.length === 0) return first; // single completed trial — just show it
    const tid = 'pi-term-' + d.id.replace(/[^a-zA-Z0-9]/g, '_');
    const moreLabel = rest.length === 1 ? '1 more completed' : `${rest.length} more completed`;
    return `${first}<div id="${tid}" style="display:none">${rest.join('')}</div>`
     + `<div onclick="const e=document.getElementById('${tid}');const o=e.style.display!=='none';e.style.display=o?'none':'block';this.textContent=o?'▾ ${moreLabel}':'▴ hide completed';" `
     + `style="font-size:10px;color:#94a3b8;cursor:pointer;padding:2px 0 4px;user-select:none;display:inline-block">▾ ${moreLabel}</div>`;
   })();

   const trialCountLabel = termCount > 0
    ? `Clinical Trials (${activeCount} active · ${termCount} completed)`
    : `Clinical Trials (${trialCount})`;
   const trialsSection = trialCount
    ? `<div class="pi-tr-hd-label">${trialCountLabel}</div>${trialHeader}<div>${activeTrialRowsHTML}${termSection}</div>`
    : `<div style="font-size:11px;color:#94a3b8;padding:4px 0">No trials linked yet</div>`;

   // Provenance badge — single inline badge: FORMERLY [name] · [chain]
   // Method label goes ON the receiving node: "Candid (acq.)" = Candid received it via acquisition.
   // No separate FORMERLY + chain badges — one badge handles both name history and chain.
   let acquisitionNote = '';
   try {
    const _athChain = athByDrugId[d.id] || [];
    const _curDrugName = (d.display_name || d.name || '').trim();
    const _frmCode = (d.licensor_code && d.licensor_code.trim() !== _curDrugName) ? d.licensor_code.trim() : null;

    const _pnHtml = (name, id, methodLabel, tip) => {
     const _nSafe = (name || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
     const _nameEl = id
      ? `<span style="font-weight:700;color:#1d4ed8;cursor:pointer;white-space:nowrap" onclick="event.stopPropagation();openCompanyEntityModal('${id}','${_nSafe}','')">${name}</span>`
      : `<span style="font-weight:700;color:#475569;white-space:nowrap">${name}</span>`;
     if (!methodLabel) return _nameEl;
     const _tipAttr = tip ? ` title="${(tip+'').replace(/"/g,'&quot;')}"` : '';
     return `${_nameEl} <span style="font-size:8.5px;color:#64748b;background:#f1f5f9;border-radius:3px;padding:1px 4px;white-space:nowrap"${_tipAttr}>${methodLabel}</span>`;
    };

    if (_athChain.length > 0) {
     // Build nodes with method on each receiving node; shorten company names
     const _pnodes = [];
     _athChain.forEach((hop, i) => {
      if (i === 0) _pnodes.push({ name: _shortenPartner(hop.from_entity_name), id: hop.from_entity_id });
      const _ms = { license:'lic.', sublicense:'sub-lic.', acquisition:'acq.', co_development:'co-dev', spin_out:'spin-out', internal:'internal', merger:'merger' }[hop.transfer_type] || hop.transfer_type;
      const _geo = (hop.geographic_scope && hop.geographic_scope !== 'global') ? ` ${hop.geographic_scope}` : '';
      const _vd = hop.verified ? '' : ' ⚬';
      _pnodes.push({ name: _shortenPartner(hop.to_entity_name), id: hop.to_entity_id, method: `${_ms}${_geo}${_vd}`, tip: hop.deal_value_notes || '' });
     });
     let _chainStr = _pnHtml(_pnodes[0].name, _pnodes[0].id, null, null);
     _pnodes.slice(1).forEach(n => {
      _chainStr += ` <span style="color:#cbd5e1;font-size:10px">→</span> ${_pnHtml(n.name, n.id, n.method, n.tip)}`;
     });
     acquisitionNote = '<div style="display:inline-flex;align-items:center;flex-wrap:wrap;gap:5px;margin-bottom:8px;padding:4px 10px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:4px;font-size:10px;color:#64748b">'
      + (_frmCode ? `<span style="font-weight:700;color:#94a3b8;font-size:9px;text-transform:uppercase;letter-spacing:0.05em">formerly</span><span style="font-weight:700;color:#475569">${_frmCode}</span><span style="color:#cbd5e1;margin:0 2px">·</span>` : '')
      + _chainStr
      + '</div>';
    } else if (_frmCode) {
     // Fallback: no ATH chain yet — show FORMERLY + simple originator if available
     const _origSpan = d.licensor_name ? ` <span style="color:#cbd5e1">·</span> <span>${d.licensor_name}</span>` : '';
     acquisitionNote = '<div style="display:inline-flex;align-items:center;flex-wrap:wrap;gap:5px;margin-bottom:8px;padding:4px 10px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:4px;font-size:10px;color:#64748b">'
      + `<span style="font-weight:700;color:#94a3b8;font-size:9px;text-transform:uppercase;letter-spacing:0.05em">formerly</span><span style="font-weight:700;color:#475569">${_frmCode}</span>${_origSpan}`
      + '</div>';
    }
   } catch(_) { acquisitionNote = ''; }

   // Partner alt-code note — shown when a drug has a partner code (e.g. QX030N for CLD-423)
   // Used for co-development deals where two companies use different codes for the same molecule
   let altCodeNote = '';
   try {
    if (d._altCode) {
     const noteSpan = d._altCodeNote
      ? '<span>· ' + d._altCodeNote + '</span>'
      : '';
     altCodeNote = '<div style="display:inline-flex;align-items:center;gap:5px;margin-bottom:8px;padding:3px 8px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:4px;font-size:10px;color:#64748b">'
      + '<span style="font-weight:700;color:#94a3b8;font-size:9px;text-transform:uppercase;letter-spacing:0.05em">also</span>'
      + '<span style="font-weight:700;color:#475569">' + d._altCode + '</span>'
      + noteSpan
      + '</div>';
    }
   } catch(_) { altCodeNote = ''; }

   // Approved drug profile section — shown when stage is Approved
   const isApproved = /approv/i.test(drugPhase);
   const approvedSection = isApproved ? (() => {
    // ── Approval date: two-column bullet list if multiple entries ─
    const approvalDateContent = d.approval_date ? (() => {
     const entries = d.approval_date.split(';').map(s => s.trim()).filter(Boolean);
     if (entries.length <= 1) return `<span class="pi-da-appr-val">${d.approval_date}</span>`;
     const items = entries.map(e => `<li>${e}</li>`).join('');
     return `<ul style="margin:3px 0 0;padding-left:14px;list-style:disc;display:grid;grid-template-columns:1fr 1fr;gap:1px 10px;font-size:10.5px;font-weight:600;color:#1e293b;line-height:1.5">${items}</ul>`;
    })() : null;
    // ── Stat cards ────────────────────────────────────────────────
    const statCards = [
     approvalDateContent ? `<div class="pi-da-appr-stat stat-approval"><span class="pi-da-appr-lbl">📅 Approval Dates</span>${approvalDateContent}</div>` : '',
     d.annual_revenue    ? `<div class="pi-da-appr-stat stat-revenue"><span class="pi-da-appr-lbl">💰 Annual Revenue</span><span class="pi-da-appr-val">${d.annual_revenue}</span></div>` : '',
     d.patient_population? `<div class="pi-da-appr-stat stat-patients"><span class="pi-da-appr-lbl">👥 Patients on Therapy</span><span class="pi-da-appr-val">${d.patient_population}</span></div>` : '',
    ].filter(Boolean).join('');
    // ── Endpoints as bullet list ───────────────────────────────────
    const endpointsContent = d.final_endpoints ? (() => {
     const entries = d.final_endpoints.split(/;\s*|\.\s+(?=[A-Z])/).map(s=>s.trim()).filter(Boolean);
     if (entries.length <= 1) return `<div class="pi-da-appr-card-body">${d.final_endpoints}</div>`;
     const items = entries.map(e=>`<li style="margin-bottom:3px">${e.replace(/\.$/,'')}</li>`).join('');
     return `<ul style="margin:0;padding-left:16px;list-style:disc" class="pi-da-appr-card-body">${items}</ul>`;
    })() : null;
    // ── Section cards ─────────────────────────────────────────────
    const endpointsCard = endpointsContent
     ? `<div class="pi-da-appr-card card-endpoints"><span class="pi-da-appr-card-lbl">⚗ Pivotal Endpoints</span>${endpointsContent}</div>` : '';
    const summaryCard = d.drug_summary
     ? `<div class="pi-da-appr-card card-summary"><span class="pi-da-appr-card-lbl">📋 Summary</span><div class="pi-da-appr-card-body">${d.drug_summary}</div></div>` : '';
    const mechCard = d.mechanism_detail
     ? `<div class="pi-da-appr-card card-mech"><span class="pi-da-appr-card-lbl">🔬 Mechanism &amp; Context</span><div class="pi-da-appr-card-body">${d.mechanism_detail}</div></div>` : '';
    const diffCard = d.differentiation_thesis
     ? `<div class="pi-da-appr-card card-diff"><span class="pi-da-appr-card-lbl">⚡ Differentiation</span><div class="pi-da-appr-card-body">${d.differentiation_thesis}</div></div>` : '';
    if (!statCards && !endpointsCard && !summaryCard && !mechCard && !diffCard) return '';
    return `<div class="pi-da-approved">
     ${summaryCard}
     ${statCards?`<div class="pi-da-appr-stats">${statCards}</div>`:''}
     ${endpointsCard}${mechCard}${diffCard}
    </div>`;
   })() : '';

   // ── Drug-specific Related News (from news_articles table) ───────────────
   // Source: sbData.newsArticles — preloaded on company expansion from the news_articles
   // RSS feed table. All articles already filtered to this company (matched_company_ids).
   // Priority: direct drug-name match (matched_drug_ids contains d.id or d.name) ranked
   // above generic company match. Show max 4, with "Drug match" badge on direct matches.
   // Only surface articles where matched_drug_ids directly contains this drug's id or name.
   // Company-level news (matched_company_ids) is intentionally excluded here — it is not
   // specific enough to be useful at the individual drug row level.
   // Drug codes like ABBV-382, LBL-053 are in the alias set and will match when they appear
   // in trade press. Brand names (Skyrizi, Humira) match immediately via existing RSS scoring.
   const sbNewsArticles = sbData?.newsArticles || [];
   const drugNewsItems = sbNewsArticles
    .filter(a => (a.matched_drug_ids||[]).some(did => did === d.id || did === d.name))
    .slice(0, 4);
   const drugNewsSection = drugNewsItems.length ? (() => {
    const rows = drugNewsItems.map(a => {
     const isDirect = _drugDirect.includes(a);
     const dateStr = (a.published_at||'').slice(0,10);
     const src = a.source_name ? `<span style="font-weight:500">${a.source_name}</span>` : '';
     const hl = (a.headline||'').replace(/</g,'&lt;').replace(/>/g,'&gt;');
     const headline = a.article_url
      ? `<a href="${a.article_url}" target="_blank" rel="noopener" onclick="event.stopPropagation()" style="color:#1d4ed8;text-decoration:none;font-weight:500;line-height:1.4">${hl}</a>`
      : `<span style="font-weight:500">${hl}</span>`;
     const whyNote = (a.why_it_matters||'').trim();
     const summaryNote = whyNote
      ? `<div style="font-size:10px;color:#64748b;line-height:1.4;margin-top:2px">${whyNote.slice(0,140)}${whyNote.length>140?'…':''}</div>` : '';
     const directBadge = isDirect
      ? `<span style="font-size:8px;font-weight:700;background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;border-radius:8px;padding:1px 5px;margin-left:4px">Drug match</span>` : '';
     return `<div style="padding:5px 0;border-bottom:1px solid #f1f5f9">
      <div style="font-size:9.5px;color:#94a3b8;margin-bottom:2px">${dateStr}${src?` · ${src}`:''}${directBadge}</div>
      <div style="font-size:11px;line-height:1.45">${headline}</div>
      ${summaryNote}
     </div>`;
    }).join('');
    return `<div style="margin-top:10px;border-top:1px solid #e2e8f0;padding-top:8px">
     <div style="font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:0.05em;color:#64748b;margin-bottom:6px">📰 Recent Coverage</div>
     ${rows}
    </div>`;
   })() : '';


   // Brief drug description shown across top of expanded body — capped at first 2 sentences
   const descText = d.drug_summary || d.differentiation_thesis || '';
   const _twoSentences = txt => {
    if (!txt) return '';
    const m = txt.match(/^(?:.+?[.!?](?:\s|$)){1,2}/);
    return m ? m[0].trim() : (txt.length > 200 ? txt.slice(0,200).trim()+'…' : txt.trim());
   };
   const descStrip = descText
    ? `<div class="pi-da-desc-strip">${_twoSentences(descText)}</div>` : '';

   // Tier class: driven by drug.overlap (DB) or _overlap (static). Never inherits company-level.
   const _tierVal = (d.overlap||d._overlap||d.overlap_category||'').toLowerCase().replace(/[-_\s]/g,'');
   const _tierCls = _tierVal==='direct' ? ' pi-da-direct' : _tierVal==='adjacent' ? ' pi-da-adjacent' : (_tierVal==='watch'||_tierVal==='samespace') ? ' pi-da-watch' : '';

   // Confidence indicator: surfaces data quality at a glance
   const _conf = (d.confidence_level || '').toLowerCase();
   // Confidence indicator — subtle, small, tooltip-first. Font reduced to 7px, low opacity.
   // confirmed=✓ green, supported=◐ amber, inferred=? gray. All suppressed unless hovering drug name.
   const _confIndicator = _conf === 'confirmed'
    ? `<span title="Verified — confirmed from direct source" style="font-size:7px;color:#15803d;font-weight:700;opacity:0.6;white-space:nowrap;flex-shrink:0;margin-left:2px">✓</span>`
    : _conf === 'supported'
    ? `<span title="Partially verified — supported by indirect sources" style="font-size:7px;color:#b45309;font-weight:700;opacity:0.6;white-space:nowrap;flex-shrink:0;margin-left:2px">◐</span>`
    : _conf === 'inferred'
    ? `<span title="Inferred — not directly confirmed" style="font-size:7px;color:#94a3b8;font-weight:600;opacity:0.5;white-space:nowrap;flex-shrink:0;margin-left:2px">?</span>`
    : '';

   return `<div class="pi-da-row${_tierCls}">
    <div class="pi-da-hd" onclick="piToggleDrugRow(this)">
     <span class="pi-da-toggle">▶</span>
     <span class="pi-da-name"><span class="pi-entity-name" onclick="event.stopPropagation();openDrugEntityModal('${d.id}','${(_piDrugLabel(d)).replace(/'/g,"\\'")}',event)">${_piDrugLabelHTML(d)}</span>${_confIndicator}</span>
     <span class="pi-da-mech">${drugTarget}</span>
     <div class="pi-da-stage">${this._stagePill(drugPhase)}</div>
     <div class="pi-da-pills"><span class="pi-da-tag" style="background:#f0fdf4;color:#15803d;border-color:#bbf7d0">${drugInd}</span></div>
     <div class="pi-da-partner">${partnerTag}</div>
    </div>
    <div class="pi-da-body">
     ${descStrip}
     <div>
      ${acquisitionNote}${altCodeNote}
      ${trialsSection}
     </div>
     ${drugNewsSection}
    </div>
   </div>`;
  }).join('');

  // ── Three-tier portfolio view ────────────────────────────────────────────
  // Flat list — no tier section headers. Split rendered HTML by row boundary.
  const _allRows = allItemsHTML.split(/(?=<div class="pi-da-row)/g).filter(Boolean);

  const drugSection = allItems.length
   ? `<div class="pi-da-wrap">
      <div class="pi-da-label" style="display:flex;align-items:center;justify-content:space-between;padding-bottom:6px"><span>${_portfolioLabel}</span>${enrichedAt}</div>
      ${_allRows.join('')}
     </div>`
   : `<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
      <div class="pi-da-label" style="padding:0">${_portfolioLabel}</div>${enrichedAt}
     </div>`;

  // (MONTHS + fmtExactDate moved above fmtPcd to fix temporal dead zone — see date helpers block)

  // ── Catalysts — first 3 visible, scroll for more, exact dates ────────────
  let catsHTML;
  const catItemsRaw = sbCats.length ? sbCats : (prog.catalysts || []);
  // Deduplicate: same normalized label + same date = one entry (prefer version with source_url)
  const _catSeen = new Map();
  catItemsRaw.forEach(c => {
   const isFromSb = sbCats.length > 0;
   const date     = isFromSb ? (c.catalyst_date||'') : (c.date||'');
   const labelRaw = isFromSb ? (c.label||'') : (c.event||'');
   const key      = labelRaw.toLowerCase().replace(/[^a-z0-9]/g,'').slice(0,55) + '|' + date;
   const prev     = _catSeen.get(key);
   if (!prev || (!prev.source_url && c.source_url)) _catSeen.set(key, c);
  });
  const catItems = [..._catSeen.values()];
  if (catItems.length) {
   const catRows = catItems.map(c => {
    const isFromSb = sbCats.length > 0;
    const date     = fmtExactDate(isFromSb ? (c.catalyst_date||'') : (c.date||''));
    const labelRaw = isFromSb ? (c.label||'') : (c.event||'');
    const srcUrl   = isFromSb ? (c.source_url||'') : (c.url||'');
    const sigBadge = isFromSb && c.significance === 'high'
     ? `<span style="font-size:8.5px;background:#fef9c3;color:#92400e;border-radius:4px;padding:1px 5px;margin-left:4px;font-weight:700;flex-shrink:0">Key</span>` : '';
    const tooltipText = (c.notes||c.label||c.event||'').replace(/"/g,'&quot;');
    const linkEl = srcUrl
     ? `<a href="${srcUrl}" target="_blank" rel="noopener" style="color:#1d4ed8;text-decoration:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0">${labelRaw} ↗</a>`
     : `<span style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0">${labelRaw}</span>`;
    return `<div class="pi-detail-cat-item" title="${tooltipText}" style="cursor:default">
      <span class="pi-detail-cat-date">${date}</span>
      <span style="font-size:11px;display:flex;align-items:center;gap:3px;overflow:hidden;min-width:0;flex:1">${linkEl}${sigBadge}</span>
     </div>`;
   }).join('');
   // 5 items visible, scroll reveals rest
   const scrollStyle = catItems.length > 5
    ? 'max-height:120px;overflow-y:auto;scrollbar-width:thin;padding-right:2px'
    : '';
   const countNote = catItems.length > 5
    ? `<div style="font-size:9.5px;color:#94a3b8;margin-bottom:4px">${catItems.length} upcoming · scroll for more</div>` : '';
   catsHTML = `${countNote}<div style="${scrollStyle}">${catRows}</div>`;
  } else {
   catsHTML = '<p style="color:#94a3b8;font-size:12px">No upcoming catalysts on record</p>';
  }

  // ── Related News (deals + financing + press releases + intel) ────────────
  // RULE: "Related News" = any notable company event — formal deals, financing rounds,
  // pipeline milestones, press releases. Sourced from deals table + intel table.
  // typeMap and renderNewsItem are defined above (before allItemsHTML.map) to avoid hoisting bug.

  let dealsHTML;
  const newsItems = sbDeals.length ? sbDeals : (prog.deals || []);
  if (newsItems.length) {
   const newsRows = newsItems.map(d => renderNewsItem(d, true)).join('');
   // 5 items visible, scroll reveals rest
   const scrollStyle = newsItems.length > 5
    ? 'max-height:120px;overflow-y:auto;scrollbar-width:thin;padding-right:2px'
    : '';
   const countNote = newsItems.length > 5
    ? `<div style="font-size:9.5px;color:#94a3b8;margin-bottom:4px">${newsItems.length} items · scroll for more</div>` : '';
   dealsHTML = `${countNote}<div style="${scrollStyle}">${newsRows}</div>`;
  } else {
   dealsHTML = '<p style="color:#94a3b8;font-size:12px">No news on record — enrichment pipeline will populate</p>';
  }

  const piHtml  = _renderPlatformIntel(platformIntel);
  const bdHtml  = _renderBdIntel(bdIntel);
  const assessCardHtml = _renderAssessmentCard(platformIntel, bdIntel);

  // Intelligence grid layout:
  // - If molecule data exists, add it as a full-width card below the 2-col intel grid
  // - Otherwise layout is unchanged
  const intelSections = (() => {
   if (piHtml && bdHtml) {
    return `<div style="display:flex;flex-direction:column;gap:10px">
             ${assessCardHtml}
             <div class="pi-detail-section" style="display:flex;flex-direction:column;flex:1"><h5>🤝 BD Intelligence</h5>${bdHtml}</div>
            </div>
            <div class="pi-detail-section" style="display:flex;flex-direction:column"><h5>🧬 Platform Intelligence</h5>${piHtml}</div>`;
   } else if (piHtml) {
    return `${assessCardHtml?`<div style="grid-column:1/-1">${assessCardHtml}</div>`:''}
            <div class="pi-detail-section" style="grid-column:1/-1"><h5>🧬 Platform Intelligence</h5>${piHtml}</div>`;
   } else if (bdHtml) {
    return `<div class="pi-detail-section"><h5>Platform Summary</h5><p>${platformSummary||'<span style="color:#94a3b8">Not yet enriched</span>'}</p></div>
            <div style="display:flex;flex-direction:column;gap:10px">
             ${assessCardHtml}
             <div class="pi-detail-section" style="display:flex;flex-direction:column;flex:1"><h5>🤝 BD Intelligence</h5>${bdHtml}</div>
            </div>`;
   } else {
    return `${assessCardHtml?`<div style="grid-column:1/-1">${assessCardHtml}</div>`:''}
            <div class="pi-detail-section" style="grid-column:1/-1">
             <h5>Platform Summary</h5>
             <p>${platformSummary||'<span style="color:#94a3b8">Not yet enriched</span>'}</p>
            </div>
            ${bdSummary?`<div class="pi-detail-section" style="grid-column:1/-1"><h5>🤝 BD Summary</h5><p>${bdSummary}</p></div>`:''}`;
   }
  })();

  // ── Competitive Signals ────────────────────────────────────────────────
  const _SIG_STYLE = {
    conference:      { label:'CONF',   bg:'#eff6ff', color:'#1d4ed8', border:'#bfdbfe' },
    clinical_update: { label:'READOUT',bg:'#f0fdf4', color:'#15803d', border:'#bbf7d0' },
    regulatory:      { label:'REG',    bg:'#fef2f2', color:'#b91c1c', border:'#fecaca' },
    financing:       { label:'$',      bg:'#f0fdf4', color:'#065f46', border:'#a7f3d0' },
    patent:          { label:'PATENT', bg:'#faf5ff', color:'#7c3aed', border:'#ddd6fe' },
    publication:     { label:'PUB',    bg:'#f5f3ff', color:'#4338ca', border:'#c7d2fe' },
    licensing:       { label:'DEAL',   bg:'#fff7ed', color:'#c2410c', border:'#fed7aa' },
  };
  const sigsHTML = (() => {
    if (!competitiveSignals.length) return '';
    const rows = competitiveSignals.slice(0, 6).map(s => {
      const st = _SIG_STYLE[s.signal_type] || { label: s.signal_type||'—', bg:'#f8fafc', color:'#64748b', border:'#e2e8f0' };
      const badge = `<span style="font-size:8px;font-weight:800;text-transform:uppercase;background:${st.bg};color:${st.color};border:1px solid ${st.border};border-radius:4px;padding:1px 5px;flex-shrink:0">${st.label}</span>`;
      const date  = (s.source_date||'').slice(0,7); // YYYY-MM
      const title = s.source_url
        ? `<a href="${s.source_url}" target="_blank" rel="noopener" style="color:#1e3a5f;font-weight:600;text-decoration:none;border-bottom:1px solid #bfdbfe">${s.title||''}</a>`
        : `<span style="color:#1e3a5f;font-weight:600">${s.title||''}</span>`;
      const desc  = s.description ? `<div style="font-size:10px;color:#64748b;margin-top:2px;line-height:1.4">${s.description.slice(0,180)}${s.description.length>180?'…':''}</div>` : '';
      return `<div style="display:flex;gap:7px;align-items:flex-start;margin-bottom:8px;padding-bottom:8px;border-bottom:1px solid #f1f5f9">
        <span style="color:#94a3b8;font-size:9px;flex-shrink:0;padding-top:2px;min-width:46px">${date}</span>
        ${badge}
        <div style="min-width:0">${title}${desc}</div>
      </div>`;
    });
    return `<div style="margin-top:10px"><div class="pi-detail-section" style="grid-column:1/-1">
      <h5>📡 Competitive Signals</h5>
      <div style="${competitiveSignals.length>4?'max-height:180px;overflow-y:auto;scrollbar-width:thin':''}">
        ${rows.join('')}
      </div>
    </div></div>`;
  })();

  return `<div class="pi-detail-inner" style="display:block;padding:14px 16px">
   ${drugSection}
  </div>`;
 },

  // ── Phase 4B Path A — IBD indication-group dual-read ───────────────────────
  // Runs after init() rendering is complete. Does NOT modify the dashboard.
  // Reads drug_indications (uc+cd) in parallel with legacy drug_area_scores (ibd).
  // Writes comparison record to window.__MERIDIAN_PHASE4_COMPARE__.
  // Expected status: compare_pass_oos_adjusted (lm-302 + sim0500 are classified OOS).
  async _runPhase4BDualRead(legacyScoreRows) {
    // Known OOS classifications for IBD extra-legacy records (mirrors DIFFERENCE_CLASSIFICATIONS in harness)
    const IBD_DIFF_CLASSIFICATIONS = {
      'lm-302':  { classification: 'legacy_noise_removed',
                   note: 'Gastric/GEJ ADC — not an IBD indication drug; wrong legacy area assignment' },
      'sim0500': { classification: 'legacy_noise_removed',
                   note: 'RRMM trispecific — not an IBD indication drug; wrong legacy area assignment' },
      'epi-001': { classification: 'needs_manual_review',
                   note: 'Anti-TL1A, preclinical — IBD indication not yet confirmed by source evidence' },
    };

    try {
      // Legacy set: drugs in drug_area_scores with area_id = 'ibd'
      // Self-fetch if legacyScoreRows is missing or empty (robustness fix: IBD PI has no
      // dedicated DOM entry point, so init() may not pass scoreRows in all call paths).
      let _legacyRows = (legacyScoreRows || []).filter(s => s.area_id === 'ibd');
      if (!_legacyRows.length) {
        const { data: fetched } = await _sb
          .from('drug_area_scores')
          .select('drug_id,area_id')
          .eq('area_id', 'ibd');
        _legacyRows = fetched || [];
      }
      const legacySet = new Set(_legacyRows.map(s => s.drug_id));

      // Normalized set: drugs in drug_indications with indication_id IN ('uc','cd')
      const { data: normRows, error: normErr } = await _sb
        .from('drug_indications')
        .select('drug_id,indication_id')
        .in('indication_id', ['uc', 'cd']);
      if (normErr) throw normErr;

      const normSet = new Set((normRows || []).map(r => r.drug_id));

      // Overlap, extra-legacy, extra-normalized
      const overlapSet    = new Set([...legacySet].filter(id => normSet.has(id)));
      const extraLegacy   = [...legacySet].filter(id => !normSet.has(id));
      const extraNorm     = [...normSet].filter(id => !legacySet.has(id));

      // Classify all differences
      const diffClassifications = {};
      extraLegacy.forEach(id => {
        diffClassifications[id] = IBD_DIFF_CLASSIFICATIONS[id]
          || { classification: 'needs_manual_review', note: 'Unclassified extra-legacy record' };
      });
      extraNorm.forEach(id => {
        diffClassifications[id] = IBD_DIFF_CLASSIFICATIONS[id]
          || { classification: 'new_normalized_value', note: 'Drug in normalized not present in legacy' };
      });

      // Metrics
      const legacyCount  = legacySet.size;
      const normCount    = normSet.size;
      const overlapCount = overlapSet.size;
      const rawMatchPct  = legacyCount > 0 ? Math.round(overlapCount / legacyCount * 1000) / 10 : 0;

      // Adjusted: legacy_noise_removed records are correct exclusions — add to numerator
      const noiseRemovedCount = extraLegacy.filter(id =>
        diffClassifications[id]?.classification === 'legacy_noise_removed'
      ).length;
      const adjOverlap  = overlapCount + noiseRemovedCount;
      const adjMatchPct = legacyCount > 0 ? Math.round(adjOverlap / legacyCount * 1000) / 10 : 0;

      const status = adjMatchPct >= 95 ? 'compare_pass_oos_adjusted' :
                     rawMatchPct >= 95 ? 'compare_pass' : 'migration_blocker';

      const record = {
        component:               '_makeAreaPI',
        path:                    'ibd_indication_group_view',
        legacy_source:           "drug_area_scores.area_id = 'ibd'",
        normalized_source:       "drug_indications.indication_id IN ('uc','cd')",
        legacy_count:            legacyCount,
        normalized_count:        normCount,
        overlap_count:           overlapCount,
        raw_match_pct:           rawMatchPct,
        adjusted_match_pct:      adjMatchPct,
        extra_legacy:            extraLegacy,
        extra_normalized:        extraNorm,
        difference_classifications: diffClassifications,
        status,
        timestamp:               new Date().toISOString(),
      };

      window.__MERIDIAN_PHASE4_COMPARE__.push(record);
      console.log(
        `[Phase4B-IBD] legacy=${legacyCount} norm=${normCount} overlap=${overlapCount}` +
        ` raw=${rawMatchPct}% adj=${adjMatchPct}% → ${status}`
      );
    } catch(err) {
      console.warn('[Phase4B-IBD] dual-read error:', err.message);
    }
  },

  // ── Phase 4B Path B — TL1A target-view dual-read ───────────────────────────
  // Governance: TL1A is a biological TARGET, not an indication group.
  // Normalized source: drug_targets WHERE target_id='tl1a'
  // Legacy source:     drug_area_scores.area_id='tl1a'
  // The legacy TL1A bucket was a competitive landscape container mixing true TL1A
  // target drugs (35) with IBD indication competitors (15) and legacy noise (2).
  // All 17 gap drugs are classified — zero are true TL1A target drugs missing rows.
  // Expected adjusted match: 35/35 = 100% → compare_pass_oos_adjusted.
  async _runPhase4BTL1ADualRead(legacyScoreRows) {
    // Mirrors DIFFERENCE_CLASSIFICATIONS in phase4_compare_legacy_vs_normalized.py
    // Classification (Session 53h): 15 ibd_indication_not_tl1a_target + 2 legacy_noise_removed
    const TL1A_DIFF_CLASSIFICATIONS = {
      // Legacy noise — wrong area entirely
      'lm-302':              { classification: 'legacy_noise_removed',
                               note: 'CLDN18.2 MMAE-ADC for gastric/GEJ cancer. No TL1A biology.' },
      'sim0500':             { classification: 'legacy_noise_removed',
                               note: 'GPRC5D×BCMA×CD3 trispecific for RRMM. No TL1A biology.' },
      // IBD indication competitors — correct path is drug_indications (uc/cd), not drug_targets (tl1a)
      'vedolizumab':         { classification: 'ibd_indication_not_tl1a_target',
                               note: 'Anti-α4β7 mAb. Approved UC/CD. No TL1A biology.' },
      'risankizumab':        { classification: 'ibd_indication_not_tl1a_target',
                               note: 'Anti-IL-23p19. Approved PsO/CD/UC. No TL1A biology.' },
      'mirikizumab':         { classification: 'ibd_indication_not_tl1a_target',
                               note: 'Anti-IL-23p19. Approved UC/CD. No TL1A biology.' },
      'guselkumab':          { classification: 'ibd_indication_not_tl1a_target',
                               note: 'Anti-IL-23p19. Approved PsO/PsA/CD. No TL1A biology.' },
      'guselkumab-golimumab':{ classification: 'ibd_indication_not_tl1a_target',
                               note: 'IL-23p19+TNFα combo. UC Phase 2b/3. No TL1A biology.' },
      'golimumab':           { classification: 'ibd_indication_not_tl1a_target',
                               note: 'Anti-TNFα. Approved RA/PsA/AS/UC. No TL1A biology.' },
      'ustekinumab':         { classification: 'ibd_indication_not_tl1a_target',
                               note: 'Anti-IL-12/23p40. Approved PsO/PsA/CD/UC. No TL1A biology.' },
      'upadacitinib':        { classification: 'ibd_indication_not_tl1a_target',
                               note: 'JAK1 inhibitor. Approved RA/PsA/AD/UC/CD. No TL1A biology.' },
      'abbv-382':            { classification: 'ibd_indication_not_tl1a_target',
                               note: 'Anti-α4β7 mAb. UC/CD Phase 2. No TL1A biology.' },
      'abbv-668':            { classification: 'ibd_indication_not_tl1a_target',
                               note: 'RIPK1 inhibitor. CD Phase 2. No TL1A biology.' },
      'lutikizumab':         { classification: 'ibd_indication_not_tl1a_target',
                               note: 'Dual IL-1α/β inhibitor. CD Phase 3. No TL1A biology.' },
      'spy001':              { classification: 'ibd_indication_not_tl1a_target',
                               note: 'Anti-α4β7 mAb. UC Phase 2. No TL1A biology.' },
      'spy003':              { classification: 'ibd_indication_not_tl1a_target',
                               note: 'Anti-IL-23p19. UC/CD Phase 2. No TL1A biology.' },
      'spy130':              { classification: 'ibd_indication_not_tl1a_target',
                               note: 'Anti-α4β7+IL-23 combo. UC/CD Phase 2. No TL1A biology.' },
      'gb004':               { classification: 'ibd_indication_not_tl1a_target',
                               note: 'PHD1/HIF-1α stabilizer. UC (terminated). No TL1A biology. ⚠️ mechanism field data error.' },
      // Pending manual review
      'epi-001':             { classification: 'needs_manual_review',
                               note: 'Anti-TL1A, preclinical — IBD indication unconfirmed; held in backfill_preview.' },
    };
    // OOS classes: both ibd_indication_not_tl1a_target and legacy_noise_removed excluded from adjusted denominator
    const _TL1A_OOS_CLASSES = new Set(['legacy_noise_removed', 'ibd_indication_not_tl1a_target']);

    try {
      // Legacy set: drugs in drug_area_scores with area_id='tl1a'
      // Self-fetch if legacyScoreRows is empty (robustness: scoreRows now from drug_competitive_scores
      // which uses context_id not area_id, so filter always returns empty — fallback to direct fetch).
      let _legacyRows = (legacyScoreRows || []).filter(s => s.area_id === 'tl1a');
      if (!_legacyRows.length) {
        const { data: fetched } = await _sb
          .from('drug_area_scores')
          .select('drug_id,area_id')
          .eq('area_id', 'tl1a');
        _legacyRows = fetched || [];
      }
      const legacySet = new Set(_legacyRows.map(s => s.drug_id));

      // Normalized set: drugs in drug_targets with target_id='tl1a'
      // NOTE: do NOT use drug_indications here — TL1A is a TARGET, not an indication
      const { data: normRows, error: normErr } = await _sb
        .from('drug_targets')
        .select('drug_id,target_id')
        .eq('target_id', 'tl1a');
      if (normErr) throw normErr;

      const normSet = new Set((normRows || []).map(r => r.drug_id));

      // Overlap, extra-legacy, extra-normalized
      const overlapSet  = new Set([...legacySet].filter(id => normSet.has(id)));
      const extraLegacy = [...legacySet].filter(id => !normSet.has(id));
      const extraNorm   = [...normSet].filter(id => !legacySet.has(id));

      // Classify all differences
      const diffClassifications = {};
      extraLegacy.forEach(id => {
        diffClassifications[id] = TL1A_DIFF_CLASSIFICATIONS[id]
          || { classification: 'needs_manual_review', note: 'Unclassified extra-legacy TL1A record' };
      });
      extraNorm.forEach(id => {
        diffClassifications[id] = TL1A_DIFF_CLASSIFICATIONS[id]
          || { classification: 'new_normalized_value', note: 'Drug in drug_targets tl1a not present in legacy area' };
      });

      // Metrics
      const legacyCount  = legacySet.size;
      const normCount    = normSet.size;
      const overlapCount = overlapSet.size;
      const rawMatchPct  = legacyCount > 0 ? Math.round(overlapCount / legacyCount * 1000) / 10 : 0;

      // Adjusted: exclude ibd_indication_not_tl1a_target + legacy_noise_removed from denominator
      const oosCount    = extraLegacy.filter(id => _TL1A_OOS_CLASSES.has(
        diffClassifications[id]?.classification || ''
      )).length;
      const adjOverlap  = overlapCount + oosCount;
      const adjMatchPct = legacyCount > 0 ? Math.round(adjOverlap / legacyCount * 1000) / 10 : 0;

      const status = adjMatchPct >= 95 ? 'compare_pass_oos_adjusted' :
                     rawMatchPct >= 95 ? 'compare_pass' : 'migration_blocker';

      const record = {
        component:               '_makeAreaPI',
        path:                    'tl1a_target_view',
        legacy_source:           "drug_area_scores.area_id = 'tl1a'",
        normalized_source:       "drug_targets WHERE target_id = 'tl1a'",
        legacy_count:            legacyCount,
        normalized_count:        normCount,
        overlap_count:           overlapCount,
        raw_match_pct:           rawMatchPct,
        adjusted_match_pct:      adjMatchPct,
        extra_legacy:            extraLegacy,
        extra_normalized:        extraNorm,
        difference_classifications: diffClassifications,
        status,
        timestamp:               new Date().toISOString(),
      };

      window.__MERIDIAN_PHASE4_COMPARE__.push(record);
      console.log(
        `[Phase4B-TL1A] legacy=${legacyCount} norm=${normCount} overlap=${overlapCount}` +
        ` raw=${rawMatchPct}% adj=${adjMatchPct}% oos=${oosCount} → ${status}`
      );
    } catch(err) {
      console.warn('[Phase4B-TL1A] dual-read error:', err.message);
    }
  },

  // ── Phase 4B Path C — TED indication-group dual-read ───────────────────────
  // Governance: TED (Thyroid Eye Disease) is an indication mapped to igf1r area.
  // Normalized source: drug_indications WHERE indication_id='ted'
  // Legacy source:     drug_area_scores.area_id='igf1r'
  // Pre-flight audit 2026-05-25: legacy=9, norm=13, overlap=9, raw=100%.
  // 4 extra_norm drugs (crn12755, iscalimab, lonigutamab, sp-1351) classified as
  // new_normalized_value — genuine TED drugs not in legacy igf1r bucket.
  // 1 data error removed: cizutamig (BCMA×CD3 myeloma bispecific, tier3_pattern false
  // positive on "TED" in compound indication list).
  async _runPhase4BTEDDualRead(legacyScoreRows) {
    // No extra-legacy classifications needed — all 9 legacy drugs confirmed in normalized.
    // Extra-norm drugs are genuine TED additions (normalized path is strictly richer).
    const TED_DIFF_CLASSIFICATIONS = {};

    try {
      // Legacy set: drugs in drug_area_scores with area_id = 'igf1r'
      // Self-fetch if legacyScoreRows is missing or empty (robustness fix).
      let _legacyRows = (legacyScoreRows || []).filter(s => s.area_id === 'igf1r');
      if (!_legacyRows.length) {
        const { data: fetched } = await _sb
          .from('drug_area_scores')
          .select('drug_id,area_id')
          .eq('area_id', 'igf1r');
        _legacyRows = fetched || [];
      }
      const legacySet = new Set(_legacyRows.map(s => s.drug_id));

      // Normalized set: drugs in drug_indications with indication_id = 'ted'
      const { data: normRows, error: normErr } = await _sb
        .from('drug_indications')
        .select('drug_id,indication_id')
        .eq('indication_id', 'ted');
      if (normErr) throw normErr;

      const normSet = new Set((normRows || []).map(r => r.drug_id));

      // Overlap, extra-legacy, extra-normalized
      const overlapSet    = new Set([...legacySet].filter(id => normSet.has(id)));
      const extraLegacy   = [...legacySet].filter(id => !normSet.has(id));
      const extraNorm     = [...normSet].filter(id => !legacySet.has(id));

      // Classify differences
      const diffClassifications = {};
      extraLegacy.forEach(id => {
        diffClassifications[id] = TED_DIFF_CLASSIFICATIONS[id]
          || { classification: 'needs_manual_review', note: 'Unclassified extra-legacy record' };
      });
      extraNorm.forEach(id => {
        diffClassifications[id] = TED_DIFF_CLASSIFICATIONS[id]
          || { classification: 'new_normalized_value', note: 'Drug in normalized not present in legacy — genuine TED addition' };
      });

      // Metrics
      const legacyCount  = legacySet.size;
      const normCount    = normSet.size;
      const overlapCount = overlapSet.size;
      const rawMatchPct  = legacyCount > 0 ? Math.round(overlapCount / legacyCount * 1000) / 10 : 0;

      // Adjusted: no noise_removed drugs for TED — raw and adjusted are equal
      const noiseRemovedCount = extraLegacy.filter(id =>
        diffClassifications[id]?.classification === 'legacy_noise_removed'
      ).length;
      const adjOverlap  = overlapCount + noiseRemovedCount;
      const adjMatchPct = legacyCount > 0 ? Math.round(adjOverlap / legacyCount * 1000) / 10 : 0;

      const status = adjMatchPct >= 95 ? 'compare_pass_oos_adjusted' :
                     rawMatchPct >= 95 ? 'compare_pass' : 'migration_blocker';

      const record = {
        component:               '_makeAreaPI',
        path:                    'ted_indication_group_view',
        legacy_source:           "drug_area_scores.area_id = 'igf1r'",
        normalized_source:       "drug_indications.indication_id = 'ted'",
        legacy_count:            legacyCount,
        normalized_count:        normCount,
        overlap_count:           overlapCount,
        raw_match_pct:           rawMatchPct,
        adjusted_match_pct:      adjMatchPct,
        extra_legacy:            extraLegacy,
        extra_normalized:        extraNorm,
        difference_classifications: diffClassifications,
        status,
        timestamp:               new Date().toISOString(),
      };

      window.__MERIDIAN_PHASE4_COMPARE__.push(record);
      console.log(
        `[Phase4B-TED] legacy=${legacyCount} norm=${normCount} overlap=${overlapCount}` +
        ` raw=${rawMatchPct}% adj=${adjMatchPct}% → ${status}`
      );
    } catch(err) {
      console.warn('[Phase4B-TED] dual-read error:', err.message);
    }
  },

  // Phase 4B Path D/E — Atopy (IL-4Rα + TSLP) dual-read comparison
  // Called once per atopy area on PI tab load. areaId = 'il4ra' | 'tslp'
  // targetIds = ['il4ra'] | ['tslp','tslpr']
  async _runPhase4BAtopyDualRead(legacyScoreRows, areaId, targetIds) {
    // Scope-diff drugs per area: present in legacy drug_areas (atopy area) but correctly
    // excluded from drug_targets because they target a different molecule in the pathway.
    const IL4RA_SCOPE_DIFF = {
      'amlitelimab':  { classification: 'scope_difference', note: 'Targets OX40L, not IL-4Rα — atopy area scope, different target' },
      'lebrikizumab': { classification: 'scope_difference', note: 'Targets IL-13, not IL-4Rα — atopy area scope, different target' },
      'nemolizumab':  { classification: 'scope_difference', note: 'Targets IL-31Rα, not IL-4Rα — atopy area scope, different target' },
      'tralokinumab': { classification: 'scope_difference', note: 'Targets IL-13, not IL-4Rα — atopy area scope, different target' },
      'zumilokibart': { classification: 'scope_difference', note: 'Targets IL-13, not IL-4Rα — atopy area scope, different target' },
    };
    const TSLP_SCOPE_DIFF = {
      'astegolimab':  { classification: 'scope_difference', note: 'Targets IL-33, not TSLP/TSLPR — atopy area scope, different target' },
      'benralizumab': { classification: 'scope_difference', note: 'Targets IL-5Rα, not TSLP/TSLPR — atopy area scope, different target' },
      'dupilumab':    { classification: 'scope_difference', note: 'Targets IL-4Rα (not TSLP/TSLPR) — appears in TSLP tab via area join only' },
      'itepekimab':   { classification: 'scope_difference', note: 'Targets IL-33, not TSLP/TSLPR — atopy area scope, different target' },
      'mepolizumab':  { classification: 'scope_difference', note: 'Targets IL-5, not TSLP/TSLPR — atopy area scope, different target' },
      'tozorakimab':  { classification: 'scope_difference', note: 'Targets IL-33R/ST2, not TSLP/TSLPR — atopy area scope, different target' },
    };

    const SCOPE_DIFF_MAP = areaId === 'il4ra' ? IL4RA_SCOPE_DIFF : TSLP_SCOPE_DIFF;
    const pathName = areaId === 'il4ra' ? 'il4ra_target_view' : 'tslp_target_view';
    const legacyLabel = `[Phase4B-Atopy-${areaId.toUpperCase()}]`;

    try {
      // Legacy set: drugs in drug_area_scores with area_id = areaId
      let _legacyRows = (legacyScoreRows || []).filter(s => s.area_id === areaId);
      if (!_legacyRows.length) {
        const { data: fetched } = await _sb
          .from('drug_area_scores')
          .select('drug_id,area_id')
          .eq('area_id', areaId);
        _legacyRows = fetched || [];
      }
      const legacySet = new Set(_legacyRows.map(s => s.drug_id));

      // Normalized set: drugs in drug_targets with target_id IN targetIds
      const { data: normRows, error: normErr } = await _sb
        .from('drug_targets')
        .select('drug_id,target_id')
        .in('target_id', targetIds);
      if (normErr) throw normErr;
      const normSet = new Set((normRows || []).map(r => r.drug_id));

      // Overlap, extra-legacy, extra-normalized
      const overlapSet  = new Set([...legacySet].filter(id => normSet.has(id)));
      const extraLegacy = [...legacySet].filter(id => !normSet.has(id));
      const extraNorm   = [...normSet].filter(id => !legacySet.has(id));

      // Classify differences
      const diffClassifications = {};
      extraLegacy.forEach(id => {
        diffClassifications[id] = SCOPE_DIFF_MAP[id]
          || { classification: 'needs_manual_review', note: 'Unclassified extra-legacy record — check target assignment' };
      });
      extraNorm.forEach(id => {
        diffClassifications[id] = { classification: 'new_normalized_value', note: `Drug in drug_targets(${targetIds.join(',')}) not in legacy — genuine normalized addition` };
      });

      // Metrics
      const legacyCount  = legacySet.size;
      const normCount    = normSet.size;
      const overlapCount = overlapSet.size;
      const rawMatchPct  = legacyCount > 0 ? Math.round(overlapCount / legacyCount * 1000) / 10 : 0;

      // Adjusted: scope_difference drugs are correctly excluded — remove from denominator
      const scopeDiffCount = extraLegacy.filter(id =>
        diffClassifications[id]?.classification === 'scope_difference'
      ).length;
      const adjDenominator = legacyCount - scopeDiffCount;
      const adjMatchPct    = adjDenominator > 0 ? Math.round(overlapCount / adjDenominator * 1000) / 10 : 100;

      const status = adjMatchPct >= 95 ? 'compare_pass_oos_adjusted' :
                     rawMatchPct >= 95 ? 'compare_pass' : 'migration_blocker';

      const record = {
        component:               '_makeAreaPI',
        path:                    pathName,
        legacy_source:           `drug_area_scores.area_id = '${areaId}'`,
        normalized_source:       `drug_targets.target_id IN (${targetIds.map(t=>`'${t}'`).join(',')})`,
        legacy_count:            legacyCount,
        normalized_count:        normCount,
        overlap_count:           overlapCount,
        raw_match_pct:           rawMatchPct,
        scope_diff_count:        scopeDiffCount,
        adjusted_denominator:    adjDenominator,
        adjusted_match_pct:      adjMatchPct,
        extra_legacy:            extraLegacy,
        extra_normalized:        extraNorm,
        difference_classifications: diffClassifications,
        status,
        timestamp:               new Date().toISOString(),
      };

      window.__MERIDIAN_PHASE4_COMPARE__.push(record);
      console.log(
        `${legacyLabel} legacy=${legacyCount} norm=${normCount} overlap=${overlapCount}` +
        ` raw=${rawMatchPct}% scopeDiff=${scopeDiffCount} adj=${adjMatchPct}% → ${status}`
      );
    } catch(err) {
      console.warn(`${legacyLabel} dual-read error:`, err.message);
    }
  },

  // Phase 4B Path F — FcRn target-view dual-read
  // Legacy source:     drug_area_scores WHERE area_id='fcrn'     (7 rows incl. atg-201)
  // Normalized source: drug_targets    WHERE target_id='fcrn'    (7 rows incl. riliprubart)
  // Scope-diff: atg-201 (CD19×CD3 bispecific — Watch-tier in fcrn legacy, not an FcRn drug)
  // Extra-norm: riliprubart (SAR443765 — confirmed FcRn inhibitor, was missing from drug_area_scores)
  // Expected: legacy=7 norm=7 overlap=6 scopeDiff=1 adj=6/6=100% → compare_pass_oos_adjusted
  async _runPhase4BFCRNDualRead(legacyScoreRows) {
    const FCRN_SCOPE_DIFF = {
      'atg-201': { classification: 'scope_difference', note: 'Targets CD19×CD3, not FcRn — Watch-tier UCB autoimmune asset in legacy fcrn area; correctly excluded from drug_targets(fcrn)' },
    };
    const pathName   = 'fcrn_target_view';
    const legacyLabel = '[Phase4B-FCRN]';

    try {
      // Legacy set: drugs in drug_area_scores with area_id = 'fcrn'
      let _legacyRows = (legacyScoreRows || []).filter(s => s.area_id === 'fcrn');
      if (!_legacyRows.length) {
        const { data: fetched } = await _sb
          .from('drug_area_scores')
          .select('drug_id,area_id')
          .eq('area_id', 'fcrn');
        _legacyRows = fetched || [];
      }
      const legacySet = new Set(_legacyRows.map(s => s.drug_id));

      // Normalized set: drugs in drug_targets with target_id = 'fcrn'
      const { data: normRows, error: normErr } = await _sb
        .from('drug_targets')
        .select('drug_id,target_id')
        .eq('target_id', 'fcrn');
      if (normErr) throw normErr;
      const normSet = new Set((normRows || []).map(r => r.drug_id));

      // Overlap, extra-legacy, extra-normalized
      const overlapSet  = new Set([...legacySet].filter(id => normSet.has(id)));
      const extraLegacy = [...legacySet].filter(id => !normSet.has(id));
      const extraNorm   = [...normSet].filter(id => !legacySet.has(id));

      // Classify differences
      const diffClassifications = {};
      extraLegacy.forEach(id => {
        diffClassifications[id] = FCRN_SCOPE_DIFF[id]
          || { classification: 'needs_manual_review', note: 'Unclassified extra-legacy record — check target assignment' };
      });
      extraNorm.forEach(id => {
        diffClassifications[id] = { classification: 'new_normalized_value', note: 'Drug in drug_targets(fcrn) not in legacy drug_area_scores — genuine normalized addition' };
      });

      // Metrics
      const legacyCount  = legacySet.size;
      const normCount    = normSet.size;
      const overlapCount = overlapSet.size;
      const rawMatchPct  = legacyCount > 0 ? Math.round(overlapCount / legacyCount * 1000) / 10 : 0;

      // Adjusted: scope_difference drugs correctly excluded — remove from denominator
      const scopeDiffCount = extraLegacy.filter(id =>
        diffClassifications[id]?.classification === 'scope_difference'
      ).length;
      const adjDenominator = legacyCount - scopeDiffCount;
      const adjMatchPct    = adjDenominator > 0 ? Math.round(overlapCount / adjDenominator * 1000) / 10 : 100;

      const status = adjMatchPct >= 95 ? 'compare_pass_oos_adjusted' :
                     rawMatchPct >= 95 ? 'compare_pass' : 'migration_blocker';

      const record = {
        component:               '_makeAreaPI',
        path:                    pathName,
        legacy_source:           "drug_area_scores.area_id = 'fcrn'",
        normalized_source:       "drug_targets.target_id = 'fcrn'",
        legacy_count:            legacyCount,
        normalized_count:        normCount,
        overlap_count:           overlapCount,
        raw_match_pct:           rawMatchPct,
        scope_diff_count:        scopeDiffCount,
        adjusted_denominator:    adjDenominator,
        adjusted_match_pct:      adjMatchPct,
        extra_legacy:            extraLegacy,
        extra_normalized:        extraNorm,
        difference_classifications: diffClassifications,
        status,
        timestamp:               new Date().toISOString(),
      };

      window.__MERIDIAN_PHASE4_COMPARE__.push(record);
      console.log(
        `${legacyLabel} legacy=${legacyCount} norm=${normCount} overlap=${overlapCount}` +
        ` raw=${rawMatchPct}% scopeDiff=${scopeDiffCount} adj=${adjMatchPct}% → ${status}`
      );
    } catch(err) {
      console.warn(`${legacyLabel} dual-read error:`, err.message);
    }
  },

  };
}

function _piExtractTarget(mech) {
  if (!mech) return null;
  const m = mech.match(/Anti-([A-Za-z0-9αβγδεζηθιΩÀ-ÿ×\-]+)/i);
  if (m) return m[1];
  const bi = mech.match(/([A-Z][A-Za-z0-9α-ω×\-]+\s*[×x]\s*[A-Z][A-Za-z0-9α-ω×\-]+)/);
  if (bi) return bi[1];
  return mech.replace(/\(.*?\)/g,'').split(/[\s,]/)[0] || null;
}

// Global delegation helpers
function _areaPIPill(tabId, group, val, btn) {
  const wrap = document.getElementById(tabId+'-area-pi-wrap');
  if (!wrap) return;
  wrap.querySelectorAll(`.pi-pill-group[data-filter="${group}"] .pi-pill`).forEach(p=>p.classList.remove('active'));
  btn.classList.add('active');
  _areaPIs[tabId]?.filter();
}
function _areaPISort(tabId, col) { _areaPIs[tabId]?.sort(col); }
function _areaPIToggle(tabId, id) { _areaPIs[tabId]?.toggle(id); }

// ── Relevance score explanation modal ──────────────────────────────────────
function _piShowRelevExplain(el, score) {
  // Remove any existing modal
  document.querySelectorAll('.pi-relev-modal-wrap').forEach(m => m.remove());
  const n = parseFloat(score);
  const col = n >= 9 ? '#dc2626' : n >= 7 ? '#ea580c' : n >= 5 ? '#d97706' : '#64748b';
  let breakdown = {};
  try { breakdown = JSON.parse(el.dataset.breakdown || '{}'); } catch(e) {}
  const rows = [
    ['Stage Proximity',    breakdown.stage_points,    3, breakdown.stage_label || 'Unknown'],
    ['Mechanism Overlap',  breakdown.overlap_points,  3, breakdown.overlap_type || 'Unknown'],
    ['Deal Activity',      breakdown.deal_points,     2, (breakdown.deal_count || 0) + ' deal(s) in this area'],
    ['Pipeline Depth',     breakdown.depth_points,    1, (breakdown.pipeline_depth || 1) + ' program(s) tracked'],
    ['Research Activity',  breakdown.research_points, 1, 'Scientific publications + conference presence'],
  ];
  const rowsHtml = rows.map(([label, pts, max, note]) => {
    const pctW = max > 0 && pts != null ? Math.round((pts / max) * 100) : 0;
    return `<div style="margin-bottom:10px">
      <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:3px">
        <div style="flex:1"><div style="font-size:11px;font-weight:600;color:#1e293b">${label}</div><div style="font-size:10px;color:#94a3b8">${note}</div></div>
        <div style="text-align:right;flex-shrink:0"><span style="font-size:13px;font-weight:800;color:#0f172a">${pts != null ? parseFloat(pts).toFixed(1) : '?'}</span><span style="font-size:10px;color:#94a3b8">/${max}</span></div>
      </div>
      <div style="height:4px;background:#f1f5f9;border-radius:2px"><div style="height:4px;border-radius:2px;background:${col};width:${pctW}%"></div></div>
    </div>`;
  }).join('');
  const wrap = document.createElement('div');
  wrap.className = 'pi-relev-modal-wrap';
  wrap.style.cssText = 'position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,0.2)';
  wrap.innerHTML = `<div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);background:white;border-radius:12px;box-shadow:0 20px 60px rgba(0,0,0,0.3);padding:24px;width:340px;max-width:90vw">
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
      <span style="font-size:28px;font-weight:900;color:${col}">${n.toFixed(1)}</span>
      <div><div style="font-size:13px;font-weight:700;color:#0f172a">Relevance Score</div><div style="font-size:11px;color:#64748b">out of 10.0</div></div>
      <button onclick="this.closest('.pi-relev-modal-wrap').remove()" style="margin-left:auto;background:none;border:1px solid #e2e8f0;border-radius:6px;padding:4px 8px;cursor:pointer;color:#64748b;font-size:13px">✕</button>
    </div>
    <div style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:12px">How this was calculated</div>
    ${rowsHtml}
    <div style="border-top:1px solid #f1f5f9;padding-top:10px;margin-top:2px;display:flex;justify-content:space-between;font-size:11px">
      <span style="color:#64748b">Total score</span>
      <span style="font-weight:800;color:${col}">${n.toFixed(1)} / 10.0</span>
    </div>
  </div>`;
  wrap.addEventListener('click', e => { if (e.target === wrap) wrap.remove(); });
  document.body.appendChild(wrap);
}

// ── Drug accordion + trial row toggle helpers ──────────────────────────────
function piToggleDrugRow(hd) {
  event.stopPropagation();
  const body = hd.nextElementSibling;
  const tog  = hd.querySelector('.pi-da-toggle');
  if (!body) return;
  body.classList.toggle('open');
  if (tog) tog.classList.toggle('open');
}
function piToggleTrialRow(hd) {
  event.stopPropagation();
  const body = hd.nextElementSibling;
  const chev = hd.querySelector('.pi-tr-chev');
  if (!body) return;
  body.classList.toggle('open');
  if (chev) chev.classList.toggle('open');
}
function piToggleTrialResults(btn) {
  event.stopPropagation();
  btn.nextElementSibling.classList.toggle('open');
}

// ── Partner pill confirm/deny popover ────────────────────────────────────────
function piConfirmPartner(pillEl, evt) {
  evt.stopPropagation();
  const existing = document.getElementById('pi-partner-pop');
  if (existing) {
    // If clicking the same pill, toggle off
    if (existing.dataset.forPill === pillEl.dataset.drugId + pillEl.dataset.partner) {
      existing.remove(); return;
    }
    existing.remove();
  }
  const drugId   = pillEl.dataset.drugId;
  const partner  = pillEl.dataset.partner;
  const shortP   = pillEl.textContent.replace(/^w\/ /,'').replace(/ \?$/,'').trim();
  const isConf   = pillEl.dataset.pv === 'true';

  const pop = document.createElement('div');
  pop.id = 'pi-partner-pop';
  pop.dataset.forPill = drugId + partner;
  pop.innerHTML = `
    <div style="font-size:10px;font-weight:700;color:#1e3a5f;margin-bottom:7px;line-height:1.3">w/ ${shortP}</div>
    <div style="display:flex;gap:6px">
      <button data-action="confirm" data-drug-id="${drugId}" style="font-size:10px;font-weight:700;padding:3px 10px;border-radius:6px;border:none;background:#1d4ed8;color:#fff;cursor:pointer;white-space:nowrap">✓ Confirm</button>
      <button data-action="remove"  data-drug-id="${drugId}" style="font-size:10px;font-weight:700;padding:3px 10px;border-radius:6px;border:1px solid #e2e8f0;background:#fff;color:#64748b;cursor:pointer;white-space:nowrap">✗ Remove</button>
    </div>`;
  pop.querySelectorAll('button[data-action]').forEach(b => {
    b.addEventListener('click', e => { e.stopPropagation(); piPartnerAction(b.dataset.action, b.dataset.drugId, b); });
  });
  pop.style.cssText = 'position:fixed;z-index:9999;background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:10px 12px;box-shadow:0 4px 20px rgba(0,0,0,0.14);min-width:160px';

  document.body.appendChild(pop);

  // Position near pill
  const rect = pillEl.getBoundingClientRect();
  let top = rect.bottom + 6;
  let left = rect.left;
  if (left + 180 > window.innerWidth) left = window.innerWidth - 190;
  if (top + 80 > window.innerHeight) top = rect.top - 80;
  pop.style.top  = top  + 'px';
  pop.style.left = left + 'px';

  // Close on outside click
  setTimeout(() => {
    document.addEventListener('click', function _close(e) {
      if (!pop.contains(e.target) && e.target !== pillEl) { pop.remove(); }
      document.removeEventListener('click', _close);
    });
  }, 0);
}

async function piPartnerAction(action, drugId, btn) {
  if (!drugId) return;
  const pop = document.getElementById('pi-partner-pop');
  const origText = btn.textContent;
  btn.textContent = '…'; btn.disabled = true;

  try {
    const patch = action === 'confirm'
      ? { partnership_verified: true }
      : { partnership_verified: false, partner_company: null };

    const res = await _sb.from('drugs').update(patch).eq('id', drugId);
    if (res.error) throw res.error;

    // Update all matching pills in the DOM
    document.querySelectorAll(`.pi-partner-pill[data-drug-id="${drugId}"]`).forEach(pill => {
      if (action === 'confirm') {
        pill.style.color = '#1d4ed8'; pill.style.background = '#eff6ff'; pill.style.borderColor = '#bfdbfe';
        pill.title = 'Confirmed partnership — click to manage';
        pill.dataset.pv = 'true';
        pill.textContent = 'w/ ' + pill.textContent.replace(/^w\/ /,'').replace(/ \?$/,'').trim();
      } else {
        pill.style.display = 'none';
      }
    });

    if (pop) pop.remove();
  } catch(e) {
    console.error('piPartnerAction error:', e);
    btn.textContent = origText; btn.disabled = false;
  }
}

async function loadAreaPI(tabId) {
  if (!TAB_AREA_MAP[tabId] || _areaPIs[tabId]?.loaded) return;
  const pi = _makeAreaPI(tabId, TAB_AREA_MAP[tabId]);
  _areaPIs[tabId] = pi;
  await pi.init();
  _injPIScores(tabId, TAB_AREA_MAP[tabId]);
}

// ── Landscape Coverage Panel (v32) ────────────────────────────────────────────
// Shows landscape_dependency_score + per-dimension bars + missing drugs.
// igf1r-tshr is the only instrumented landscape as of v32.
// Extend by adding entries to TAB_LANDSCAPE_MAP as new landscapes are seeded.
const TAB_LANDSCAPE_MAP = {
  // 'igf1r-tshr' coverage panel removed — filter pills restored (v33 UI fix)
  // Re-enable here when coverage panel gets its own dedicated section below the pills
};

async function loadLandscapeCoverage(tabId) {
  const cfg = TAB_LANDSCAPE_MAP[tabId];
  if (!cfg || !_sb) return;
  const el = document.getElementById(cfg.pillsId);
  if (!el) return;

  try {
    // Fetch landscape row
    const { data: ls, error: lsErr } = await _sb
      .from('competitive_landscapes')
      .select('id,disease_name,landscape_dependency_score,drug_coverage_score,relationship_coverage_score,catalyst_coverage_score,source_validation_score,staleness_penalty,expected_drug_count,coverage_computed_at')
      .eq('area_id', cfg.area_id)
      .limit(1);
    if (lsErr || !ls?.length) { el.innerHTML = ''; return; }
    const L = ls[0];

    // Fetch expected competitors to find missing ones
    const { data: lec } = await _sb
      .from('landscape_expected_competitors')
      .select('drug_name,confirmed,tier,drug_id')
      .eq('landscape_id', L.id)
      .order('tier', { ascending: true });

    const score   = Math.round(L.landscape_dependency_score ?? 0);
    const drug    = Math.round((L.drug_coverage_score ?? 0) * 100);
    const rel     = Math.round((L.relationship_coverage_score ?? 0) * 100);
    const cat     = Math.round((L.catalyst_coverage_score ?? 0) * 100);
    const src     = Math.round((L.source_validation_score ?? 0) * 100);
    const stale   = Math.round((L.staleness_penalty ?? 0) * 100);
    const missing = (lec || []).filter(r => !r.confirmed || !r.drug_id).map(r => r.drug_name);

    // Score color: green ≥80, amber ≥60, red <60
    const scoreCol = score >= 80 ? '#065f46' : score >= 60 ? '#92400e' : '#991b1b';
    const scoreBg  = score >= 80 ? '#d1fae5' : score >= 60 ? '#fef3c7' : '#fee2e2';

    function dimBar(label, pct, color) {
      const bg = pct >= 80 ? '#d1fae5' : pct >= 50 ? '#fef3c7' : '#fee2e2';
      const fg = pct >= 80 ? '#065f46' : pct >= 50 ? '#92400e' : '#991b1b';
      return `<span title="${label}: ${pct}%" style="display:inline-flex;align-items:center;gap:4px;background:${bg};color:${fg};font-size:10px;font-weight:700;padding:3px 8px;border-radius:10px;white-space:nowrap">
        ${label} ${pct}%</span>`;
    }

    const missingChips = missing.length
      ? `<span style="color:#94a3b8;font-size:10px;margin-left:2px">Missing:</span> ` +
        missing.map(n => `<span style="background:#f1f5f9;color:#475569;font-size:10px;padding:2px 7px;border-radius:8px">${n}</span>`).join(' ')
      : '';

    const computedAt = L.coverage_computed_at
      ? new Date(L.coverage_computed_at).toLocaleDateString('en-US', { month:'short', day:'numeric' })
      : '';

    el.innerHTML = `
      <span title="Landscape dependency score — computed from drug, relationship, catalyst, and source coverage. Updated ${computedAt}."
            style="background:${scoreBg};color:${scoreCol};font-size:12px;font-weight:800;padding:3px 10px;border-radius:10px;cursor:default">
        ${L.disease_name || 'TED'} Coverage&nbsp;&nbsp;${score}/100
      </span>
      ${dimBar('Drug', drug, '#065f46')}
      ${dimBar('Edges', rel, '#1d4ed8')}
      ${dimBar('Catalyst', cat, '#7c3aed')}
      ${dimBar('Source', src, '#b45309')}
      ${stale > 0 ? `<span title="Staleness penalty: ${stale}% of tracked items flagged needs_revalidation" style="background:#fef2f2;color:#dc2626;font-size:10px;font-weight:700;padding:3px 7px;border-radius:10px">⚠ ${stale}% stale</span>` : ''}
      ${missingChips}
    `.trim();
  } catch(e) {
    console.warn('[loadLandscapeCoverage]', tabId, e);
    el.innerHTML = '';
  }
}

function switchTab(id, btn) {
  // Fire onLeave for the departing tab — isolated so errors don't block navigation
  const prevId = document.querySelector('.tab-pane.active')?.id?.replace(/^tab-/, '');
  if (prevId && prevId !== id && TAB_REGISTRY[prevId]?.onLeave) {
    try { TAB_REGISTRY[prevId].onLeave(); }
    catch(e) { console.warn(`[TAB:${prevId}:onLeave]`, e); }
  }
  // Swap active pane + button
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + id)?.classList.add('active');
  btn?.classList.add('active');
  updateTabTitle(id);
  try { clearGlobalSearch(); } catch(e) { /* grid not yet rendered — safe to skip */ }
  buildToc(id);
  closeToc();
  if (typeof fixTabBarTop === 'function') requestAnimationFrame(fixTabBarTop);
  // Fire onEnter for the arriving tab — isolated so errors don't break the UI
  if (TAB_REGISTRY[id]?.onEnter) {
    try { TAB_REGISTRY[id].onEnter(); }
    catch(e) { console.warn(`[TAB:${id}:onEnter]`, e); }
  }
  // Meridian briefs (landscape + strategy + patient) for any area tab
  try {
    if (typeof TAB_AREA !== 'undefined' && TAB_AREA[id] && typeof _loadAreaBriefs === 'function') _loadAreaBriefs(id);
  } catch(e) { /* non-blocking */ }
}
// Helper for programmatic tab switching (used by home nav buttons)
function switchTabTo(id) {
  const btn = document.querySelector(`.tab-btn[onclick*="'${id}'"]`);
  switchTab(id, btn);
}

// ── ASSET JUMP DROPDOWN ───────────────────────────────────────────
function jumpToAsset(val) {
 if (!val) return;
 const [tab, anchor] = val.split('|');
 const btn = document.querySelector(`.tab-btn[onclick*="'${tab}'"]`);
 if (btn) {
 switchTab(tab, btn);
 if (anchor) setTimeout(() => scrollToSection(anchor), 250);
 }
 document.getElementById('asset-jump').value = '';
}

// ── INTEL QUICK-SUBMIT MODAL (header button) ──────────────────────
// ── SUBMIT INTEL — simple modal (Path 5 intake) ──────────────────
function openIntelModal() {
  // Reset to form state
  document.getElementById('im-form-body').style.display = '';
  document.getElementById('im-footer').style.display = '';
  document.getElementById('im-success').classList.remove('show');
  document.getElementById('im-err').classList.remove('show');
  ['im-url','im-name'].forEach(id => document.getElementById(id)?.classList.remove('error'));
  _siResetFileAttachment();
  document.getElementById('intel-modal-overlay').classList.add('open');
  setTimeout(() => document.getElementById('im-text')?.focus(), 80);
}
function closeIntelModal() {
  document.getElementById('intel-modal-overlay').classList.remove('open');
  _siResetFileAttachment();
}
async function submitIntelNew() {
  const url  = (document.getElementById('im-url')?.value  || '').trim();
  const text = (document.getElementById('im-text')?.value || '').trim();
  const name = (document.getElementById('im-name')?.value || '').trim();
  const err  = document.getElementById('im-err');
  // Capture any attached file info
  const fileInput = document.getElementById('si-file-input');
  const attachedFile = window._siFile || ((fileInput && fileInput.files && fileInput.files[0]) ? fileInput.files[0] : null);
  const attachedFileName = attachedFile ? attachedFile.name : null;
  // Validation
  let valid = true;
  document.getElementById('im-name')?.classList.remove('error');
  document.getElementById('im-url')?.classList.remove('error');
  err.classList.remove('show');
  if (!name) { document.getElementById('im-name')?.classList.add('error'); valid = false; }
  if (!url && !text && !attachedFile) { document.getElementById('im-url')?.classList.add('error'); valid = false; }
  if (url && !/^https?:\/\//i.test(url)) { document.getElementById('im-url')?.classList.add('error'); valid = false; }
  if (!valid) { err.classList.add('show'); return; }
  // Disable button
  const btn = document.getElementById('im-submit-btn');
  if (btn) { btn.disabled = true; btn.textContent = 'Submitting…'; }
  // Upload the attached file (if any) to Supabase Storage so the PDF is actually SAVED.
  // Private bucket source-documents (PDF only, ≤25MB). The backend reads it and generates
  // a signed view URL, so an uploaded PDF becomes viewable in the dashboard as its source.
  let attachedFilePath = null;
  if (attachedFile) {
    const isPdf = /pdf/i.test(attachedFile.type) || /\.pdf$/i.test(attachedFile.name);
    if (!isPdf) {
      if (btn) { btn.disabled = false; btn.textContent = 'Submit →'; }
      err.textContent = 'Attached file must be a PDF (max 25MB). For other docs, paste a link instead.';
      err.classList.add('show');
      return;
    }
    try {
      if (btn) btn.textContent = 'Uploading PDF…';
      const safe = attachedFile.name.replace(/[^\w.\-]+/g, '_').slice(-80);
      const path = `uploads/${Date.now()}_${safe}`;
      // Raw fetch upload — the supabase-js storage client omits the apikey header with
      // the new publishable key format, which trips storage RLS. Raw fetch with the key works.
      const upResp = await fetch(`${SUPABASE_URL}/storage/v1/object/source-documents/${path}`, {
        method: 'POST',
        headers: { 'apikey': SUPABASE_ANON, 'Authorization': 'Bearer ' + SUPABASE_ANON,
                   'Content-Type': 'application/pdf' },  // no x-upsert: upsert needs an UPDATE policy; paths are unique so a plain INSERT is correct
        body: attachedFile
      });
      if (!upResp.ok) throw new Error('storage ' + upResp.status + ': ' + (await upResp.text()).slice(0,120));
      attachedFilePath = path;
      if (btn) btn.textContent = 'Submitting…';
    } catch (upe) {
      if (btn) { btn.disabled = false; btn.textContent = 'Submit →'; }
      err.textContent = `File upload failed: ${upe?.message || upe}. You can submit the link instead.`;
      err.classList.add('show');
      console.error('[submit intel] upload error:', upe);
      return;
    }
  }
  // Insert to submitted_intel
  try {
    const payload = {
      submitted_by:     name,
      source_url:       url || null,
      submitted_text:   text || null,
      status:           'new',
      raw_payload_json: {
        url, text, name,
        attached_file: attachedFileName || null,
        attached_file_path: attachedFilePath,
        detected_fields: window._siLastDetected || null,
        submitted_at: new Date().toISOString()
      }
    };
    const { error } = await _sb.from('submitted_intel').insert([payload]);
    if (error) throw error;
  } catch(e) {
    // Show the actual error so we know what's wrong
    if (btn) { btn.disabled = false; btn.textContent = 'Submit →'; }
    err.textContent = `Submission failed: ${e?.message || e}. The submitted_intel table may need to be created — see migrations/v33_submitted_intel.sql.`;
    err.classList.add('show');
    console.error('[submit intel] insert error:', e);
    return;
  }
  // Show success
  document.getElementById('im-form-body').style.display = 'none';
  document.getElementById('im-footer').style.display = 'none';
  const _succ = document.getElementById('im-success');
  if (_succ) {
    let fc = document.getElementById('im-success-file');
    if (!fc) { fc = document.createElement('div'); fc.id = 'im-success-file'; fc.style.cssText = 'margin-top:8px;font-size:12px;font-weight:600'; _succ.appendChild(fc); }
    fc.textContent = attachedFilePath ? ('📎 PDF saved to library: ' + (attachedFileName||'file')) : '';
    fc.style.color = '#15803d';
  }
  _succ.classList.add('show');
  // Invalidate review panel cache so next open shows fresh data
  _siLoaded = false;
  // Auto-close after 3s
  setTimeout(() => {
    closeIntelModal();
    if (btn) { btn.disabled = false; btn.textContent = 'Submit →'; }
    ['im-url','im-text','im-name'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    });
    // Reset file attachment state
    _siResetFileAttachment();
  }, 3000);
}
// ── Submit Intel — File attachment helpers ────────────────────────────────────
window._siLastDetected = null;

function triggerDocAttach() {
  // Open the intel modal first (if not already open), then trigger file pick
  if (!document.getElementById('intel-modal-overlay')?.classList.contains('open')) {
    openIntelModal();
    setTimeout(() => document.getElementById('si-file-input')?.click(), 120);
  } else {
    document.getElementById('si-file-input')?.click();
  }
}

function _siResetFileAttachment() {
  const fileInput = document.getElementById('si-file-input');
  if (fileInput) fileInput.value = '';
  const dropInner = document.querySelector('#si-drop-zone .si-drop-inner');
  if (dropInner) dropInner.style.display = '';
  const zone = document.getElementById('si-file-zone');
  if (zone) { zone.innerHTML = ''; zone.style.display = 'none'; }
  const det = document.getElementById('si-detected-fields');
  if (det) { det.style.display = 'none'; det.innerHTML = ''; }
  const q = document.getElementById('si-questions');
  if (q) { q.style.display = 'none'; q.innerHTML = ''; }
  window._siLastDetected = null;
  window._siFile = null;
}

function siHandleFileSelected(evt) {
  const file = evt.target.files[0];
  if (!file) return;
  _siShowFileInZone(file);
  _siReadFile(file);
}

function _siShowFileInZone(file) {
  window._siFile = file;  // shared ref — drag-drop does NOT populate the file input, so the
                          // submit handler must read this (fixes dropped PDFs not being uploaded)
  const dropInner = document.querySelector('#si-drop-zone .si-drop-inner');
  if (dropInner) dropInner.style.display = 'none';
  const zone = document.getElementById('si-file-zone');
  if (zone) { zone.innerHTML = `📎 <strong>${file.name}</strong> <span style="color:#94a3b8;font-size:11px">(${(file.size/1024).toFixed(1)} KB)</span> <span style="color:#6366f1;cursor:pointer;font-size:11px" onclick="_siResetFileAttachment()">✕ remove</span>`; zone.style.display = ''; }
}

(function() {
  function initSIDrop() {
    const dropZone = document.getElementById('si-drop-zone');
    if (!dropZone) return;
    dropZone.addEventListener('dragover', function(e) { e.preventDefault(); dropZone.classList.add('si-drop-active'); });
    dropZone.addEventListener('dragleave', function() { dropZone.classList.remove('si-drop-active'); });
    dropZone.addEventListener('drop', function(e) {
      e.preventDefault();
      dropZone.classList.remove('si-drop-active');
      const file = e.dataTransfer.files[0];
      if (file) { _siShowFileInZone(file); _siReadFile(file); }
    });
  }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', initSIDrop); }
  else { initSIDrop(); }
  window._initSIDropOnOpen = initSIDrop;
})();

function _siReadFile(file) {
  const det = document.getElementById('si-detected-fields');
  const q   = document.getElementById('si-questions');
  // Text-readable types
  const isText = /text\/(plain|markdown|csv)|application\/json/.test(file.type) ||
                 /\.(txt|md|csv|json)$/i.test(file.name);
  if (isText) {
    if (det) { det.style.display = ''; det.innerHTML = '<em style="color:#64748b">Reading…</em>'; }
    const reader = new FileReader();
    reader.onload = e => {
      const content = e.target.result || '';
      const fields  = _siExtractIntelFields(content);
      window._siLastDetected = fields.detected;
      // Show detected
      if (det) {
        if (fields.detected.length) {
          det.style.display = '';
          det.innerHTML = '<strong style="color:#166534">Detected:</strong> ' +
            fields.detected.map(f => `<span style="background:#dcfce7;border-radius:3px;padding:1px 5px;margin:0 2px">${_esc(f)}</span>`).join(' ');
        } else {
          det.style.display = '';
          det.innerHTML = '<span style="color:#64748b">No structured fields auto-detected — add context in Comments above.</span>';
        }
      }
      // Show questions
      if (q && fields.questions.length) {
        q.style.display = '';
        q.innerHTML = '<strong style="color:#92400e">Questions for Kyle:</strong><ul style="margin:4px 0 0 16px;padding:0">' +
          fields.questions.map(qn => `<li>${_esc(qn)}</li>`).join('') + '</ul>';
      } else if (q) {
        q.style.display = 'none';
      }
    };
    reader.readAsText(file);
  } else {
    // Binary / PDF / docx
    window._siLastDetected = null;
    if (det) {
      det.style.display = '';
      const typeLabel = /pdf/i.test(file.name) ? 'PDF' :
                        /docx?/i.test(file.name) ? 'Word document' :
                        /xlsx?/i.test(file.name) ? 'Excel file' : 'File';
      det.innerHTML = `<span style="color:#64748b">${typeLabel} attached — ${/pdf/i.test(file.name)?'will be uploaded & saved to the source library, then read by the backend':'will be noted on submission'}. Add key points in Comments above.</span>`;
    }
    if (q) q.style.display = 'none';
  }
}

function _siExtractIntelFields(text) {
  const detected  = [];
  const questions = [];
  // Dollar amounts
  const dollars = text.match(/\$[\d,]+(?:\.\d+)?(?:\s*[BMK](?:illion|n)?)?/gi) || [];
  dollars.slice(0,3).forEach(d => detected.push(d.trim()));
  // Drug codes: 2-5 uppercase letters + digits (e.g. XPF-005, ABBV-701, SPY001)
  const drugCodes = text.match(/\b[A-Z]{2,5}[-‑]?\d{2,4}\b/g) || [];
  [...new Set(drugCodes)].slice(0,4).forEach(d => detected.push(d));
  // Company names: 2+ consecutive Title-Case words (rough heuristic, exclude common sentence starts)
  const coNames = text.match(/\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b/g) || [];
  const filtered = [...new Set(coNames)].filter(n =>
    !/^(The|This|These|There|Their|They|Phase|Study|Trial|Data|Drug|Results|Safety|Efficacy)\b/.test(n)
  );
  filtered.slice(0,4).forEach(n => detected.push(n));
  // Dates: YYYY, or Month YYYY, or M/D/YYYY
  const dates = text.match(/\b(?:20\d{2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+20\d{2}|\d{1,2}\/\d{1,2}\/20\d{2})\b/gi) || [];
  [...new Set(dates)].slice(0,2).forEach(d => detected.push(d));
  // Generate gap questions
  if (!dollars.length) questions.push('What is the deal or milestone value (if any)?');
  if (!dates.length)   questions.push('What is the effective or announcement date?');
  if (!drugCodes.length && detected.filter(d => /[A-Z]/.test(d)).length < 2)
    questions.push('Which specific drug or asset does this relate to?');
  return { detected: [...new Set(detected)].slice(0, 10), questions };
}

// ── Document Upload Modal ─────────────────────────────────────────────────────
// Populates entity dropdown, handles form, saves to source_documents via Supabase.

let _docEntitiesLoaded = false;

async function openDocUploadModal() {
  // Reset form
  ['doc-form-body','doc-footer'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = '';
  });
  document.getElementById('doc-success')?.classList.remove('show');
  document.getElementById('doc-err')?.classList.remove('show');
  ['doc-entity-id','doc-type','doc-title','doc-date','doc-venue',
   'doc-url','doc-findings','doc-tags','doc-authors'].forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.classList.remove('error'); }
  });
  const btn = document.getElementById('doc-submit-btn');
  if (btn) { btn.disabled = false; btn.textContent = 'Save Document →'; }

  // Reset file drop
  const fileInput = document.getElementById('doc-file');
  if (fileInput) fileInput.value = '';
  const dropLabel = document.getElementById('doc-filedrop-label');
  const dropName  = document.getElementById('doc-filedrop-name');
  if (dropLabel) dropLabel.style.display = '';
  if (dropName)  { dropName.style.display = 'none'; dropName.textContent = ''; }

  document.getElementById('doc-modal-overlay')?.classList.add('open');

  // Load entity dropdown once
  if (!_docEntitiesLoaded) {
    await _docLoadEntities();
  }
}

function closeDocUploadModal() {
  document.getElementById('doc-modal-overlay')?.classList.remove('open');
}

async function _docLoadEntities() {
  const sel = document.getElementById('doc-entity-id');
  if (!sel) return;
  sel.innerHTML = '<option value="">Loading…</option>';
  try {
    // Fetch drugs
    const { data: drugs, error: dErr } = await _sb
      .from('drugs')
      .select('id,name,stage')
      .order('name', { ascending: true })
      .limit(300);
    if (dErr) throw dErr;

    // Fetch companies
    const { data: companies, error: cErr } = await _sb
      .from('companies')
      .select('id,name')
      .order('name', { ascending: true })
      .limit(200);
    if (cErr) throw cErr;

    let html = '<option value="">Select drug or company…</option>';

    if (drugs && drugs.length) {
      html += '<optgroup label="── Drugs ──">';
      drugs.forEach(d => {
        const stage = d.stage ? ` (${d.stage})` : '';
        html += `<option value="${_escAttr(d.id)}" data-type="drug">${_escAttr(d.name)}${stage}</option>`;
      });
      html += '</optgroup>';
    }

    if (companies && companies.length) {
      html += '<optgroup label="── Companies ──">';
      companies.forEach(c => {
        html += `<option value="${_escAttr(c.id)}" data-type="company">${_escAttr(c.name)}</option>`;
      });
      html += '</optgroup>';
    }

    sel.innerHTML = html;
    _docEntitiesLoaded = true;
  } catch (e) {
    sel.innerHTML = '<option value="">Error loading — type entity ID manually</option>';
    console.error('[doc-upload] entity load error:', e);
  }
}

function _escAttr(s) {
  if (s == null) return '';
  return String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;');
}

function handleDocFileSelect(evt) {
  const file = evt.target.files[0];
  if (!file) return;
  const dropLabel = document.getElementById('doc-filedrop-label');
  const dropName  = document.getElementById('doc-filedrop-name');
  if (dropLabel) dropLabel.style.display = 'none';
  if (dropName)  { dropName.textContent = `${file.name} (${(file.size/1024).toFixed(1)} KB)`; dropName.style.display = ''; }
}

function handleDocFileDrop(evt) {
  evt.preventDefault();
  document.getElementById('doc-filedrop')?.classList.remove('dragover');
  const file = evt.dataTransfer.files[0];
  if (!file) return;
  const input = document.getElementById('doc-file');
  // Assign via DataTransfer so the input reflects the file
  const dt = new DataTransfer();
  dt.items.add(file);
  if (input) input.files = dt.files;
  handleDocFileSelect({ target: { files: [file] } });
}

async function submitDocUpload() {
  const entitySel  = document.getElementById('doc-entity-id');
  const entityId   = (entitySel?.value || '').trim();
  const entityType = entitySel?.options[entitySel.selectedIndex]?.dataset?.type || 'drug';
  const docType    = (document.getElementById('doc-type')?.value || '').trim();
  const title      = (document.getElementById('doc-title')?.value || '').trim();
  const dateVal    = (document.getElementById('doc-date')?.value || '').trim();
  const venue      = (document.getElementById('doc-venue')?.value || '').trim();
  const url        = (document.getElementById('doc-url')?.value || '').trim();
  const findingsRaw= (document.getElementById('doc-findings')?.value || '').trim();
  const tagsRaw    = (document.getElementById('doc-tags')?.value || '').trim();
  const authorsRaw = (document.getElementById('doc-authors')?.value || '').trim();

  const errEl = document.getElementById('doc-err');
  if (errEl) { errEl.classList.remove('show'); errEl.textContent = ''; }

  // Validation
  const missing = [];
  if (!entityId) missing.push('entity');
  if (!docType)  missing.push('document type');
  if (!title)    missing.push('title');
  if (missing.length) {
    if (errEl) {
      errEl.textContent = `Required: ${missing.join(', ')}.`;
      errEl.classList.add('show');
    }
    if (!entityId) entitySel?.classList.add('error');
    if (!docType)  document.getElementById('doc-type')?.classList.add('error');
    if (!title)    document.getElementById('doc-title')?.classList.add('error');
    return;
  }

  // Parse arrays
  const keyFindings = findingsRaw
    ? findingsRaw.split('\n').map(s => s.replace(/^[•\-\*]\s*/,'').trim()).filter(Boolean)
    : [];
  const relevanceTags = tagsRaw
    ? tagsRaw.split(',').map(s => s.trim()).filter(Boolean)
    : [];
  const authors = authorsRaw
    ? authorsRaw.split(',').map(s => s.trim()).filter(Boolean)
    : [];

  // Determine conference vs journal
  const isConference = ['conference_poster','investor_presentation','investor_day'].includes(docType);
  const conferenceName = isConference ? (venue || null) : null;
  const journalName    = isConference ? null : (venue || null);

  const payload = {
    entity_id:       entityId   || null,
    entity_type:     entityType || 'drug',
    document_type:   docType,
    title:           title,
    authors:         authors.length ? authors : null,
    publication_date: dateVal || null,
    conference_name: conferenceName,
    journal_name:    journalName,
    external_url:    url || null,
    key_findings:    keyFindings.length ? keyFindings : null,
    relevance_tags:  relevanceTags.length ? relevanceTags : null,
    uploaded_by:     'kyle',
    verified:        false,
  };

  const btn = document.getElementById('doc-submit-btn');
  if (btn) { btn.disabled = true; btn.textContent = 'Saving…'; }

  try {
    const resp = await fetch(
      'https://tghntyofptvfhmtchwcv.supabase.co/rest/v1/source_documents',
      {
        method: 'POST',
        headers: {
          'apikey':        SUPABASE_ANON,
          'Authorization': 'Bearer ' + SUPABASE_ANON,
          'Content-Type':  'application/json',
          'Prefer':        'return=representation',
        },
        body: JSON.stringify(payload),
      }
    );
    if (!resp.ok) {
      const detail = await resp.text();
      throw new Error(`HTTP ${resp.status}: ${detail}`);
    }
    const saved = await resp.json();
    console.log('[doc-upload] saved:', saved);

    // Show success
    document.getElementById('doc-form-body').style.display = 'none';
    document.getElementById('doc-footer').style.display = 'none';
    document.getElementById('doc-success')?.classList.add('show');

    // Auto-close after 3.5s
    setTimeout(() => {
      closeDocUploadModal();
      if (btn) { btn.disabled = false; btn.textContent = 'Save Document →'; }
    }, 3500);

  } catch(e) {
    if (btn) { btn.disabled = false; btn.textContent = 'Save Document →'; }
    if (errEl) {
      errEl.textContent = `Save failed: ${e?.message || e}`;
      errEl.classList.add('show');
    }
    console.error('[doc-upload] insert error:', e);
  }
}
// ── End Document Upload Modal ─────────────────────────────────────────────────

// Legacy stubs — kept so any old references don't throw
function saveFromModal() { submitIntelNew(); }
function submitIntel()    { submitIntelNew(); }
function copyFromModal()  {}
function renderIntelSubmissions() {}
function deleteIntel()    {}
function clearIntelForm() {}
function copyIntelForClaude() {}

// ── SUBMITTED INTEL REVIEW PANEL ──────────────────────────────────
let _siData = [];
let _siLoaded = false;
let _siStatusFilter = '';

async function siLoad(force = false) {
  if (_siLoaded && !force) { siRender(); return; }
  const tbody = document.getElementById('si-tbody');
  if (tbody) tbody.innerHTML = '<tr><td colspan="6" class="si-empty">Loading…</td></tr>';
  try {
    const { data, error } = await _sb
      .from('submitted_intel')
      .select('*')
      .order('created_at', { ascending: false })
      .limit(200);
    if (error) throw error;
    _siData = data || [];
    _siLoaded = true;
    siRender();
    // Update badge in tab header
    const newCount = _siData.filter(r => r.status === 'new').length;
    const badge = document.getElementById('si-new-badge');
    if (badge) {
      if (newCount > 0) { badge.textContent = newCount + ' new'; badge.style.display = 'inline-block'; }
      else { badge.style.display = 'none'; }
    }
    // Also update nav icon tooltip
    const navBtn = document.getElementById('nav-icon-si');
    if (navBtn) navBtn.title = newCount > 0 ? `Submitted Intel (${newCount} new)` : 'Submitted Intel Review';
  } catch(e) {
    // Don't set _siLoaded on error so next open retries
    const msg = e?.message || String(e);
    const hint = msg.includes('does not exist') || msg.includes('relation')
      ? ' — the <strong>submitted_intel</strong> table needs to be created. Apply <code>migrations/v33_submitted_intel.sql</code> in the Supabase SQL editor.'
      : '';
    if (tbody) tbody.innerHTML = `<tr><td colspan="6" class="si-empty" style="color:#dc2626;text-align:left;padding:20px">
      <strong>Error loading submissions:</strong> ${msg}${hint}<br><br>
      <button onclick="siLoad(true)" style="font-size:11px;padding:4px 10px;border:1px solid #dc2626;border-radius:5px;background:#fff1f2;color:#dc2626;cursor:pointer">Retry</button>
    </td></tr>`;
  }
}

function siFilter(btn, status) {
  document.querySelectorAll('#si-filter-bar .si-pill').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  _siStatusFilter = status;
  siRender();
}

function siRender() {
  const tbody = document.getElementById('si-tbody');
  if (!tbody) return;
  const rows = _siStatusFilter ? _siData.filter(r => r.status === _siStatusFilter) : _siData;
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="7" class="si-empty">No submissions${_siStatusFilter ? ` with status "${_siStatusFilter}"` : ''}.</td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map((r, i) => {
    const date   = r.created_at ? new Date(r.created_at).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}) : '';
    const title  = r.extracted_title || (r.submitted_text ? r.submitted_text.slice(0,80) : '—');
    const urlDom = r.source_url ? (() => { try { return new URL(r.source_url).hostname.replace('www.',''); } catch(e) { return r.source_url.slice(0,30); } })() : '';
    const status = r.status || 'new';
    const conf   = r.confidence_level || '';
    const detId  = `si-det-${r.id}`;
    const chevId = `si-chev-${r.id}`;

    // ── Status timeline ──────────────────────────────────────────────────────
    const _siSteps = [
      { key:'submitted', label:'Submitted', done: true, ts: r.created_at },
      { key:'processed', label:'Processed', done: !!(r.analyzed_at || r.extracted_title || status === 'analyzed' || status === 'approved' || status === 'rejected' || status === 'imported'), ts: r.analyzed_at },
      { key:'resolved',  label: status === 'rejected' ? 'Rejected' : status === 'imported' ? 'Imported' : 'Published', done: !!(status === 'approved' || status === 'rejected' || status === 'imported'), ts: r.reviewed_at || r.imported_at },
    ];
    const _siTimeline = `<div style="display:flex;align-items:center;gap:0;margin-bottom:12px">
      ${_siSteps.map((step, si) => {
        const dotColor = step.done ? (step.key === 'resolved' && status === 'rejected' ? '#dc2626' : '#16a34a') : '#cbd5e1';
        const labelColor = step.done ? '#1e293b' : '#94a3b8';
        const tsStr = step.ts ? (() => { try { return new Date(step.ts).toLocaleDateString('en-US',{month:'short',day:'numeric'}); } catch(_){ return ''; } })() : '';
        return `<div style="display:flex;flex-direction:column;align-items:center;gap:3px;flex:1;min-width:60px">
          <div style="display:flex;align-items:center;width:100%">
            ${si > 0 ? `<div style="flex:1;height:2px;background:${_siSteps[si-1].done ? dotColor : '#e2e8f0'}"></div>` : '<div style="flex:1"></div>'}
            <div style="width:10px;height:10px;border-radius:50%;background:${dotColor};flex-shrink:0;border:2px solid ${step.done ? dotColor : '#e2e8f0'}"></div>
            ${si < _siSteps.length - 1 ? `<div style="flex:1;height:2px;background:#e2e8f0"></div>` : '<div style="flex:1"></div>'}
          </div>
          <div style="font-size:10px;font-weight:700;color:${labelColor};text-align:center;white-space:nowrap">${step.label}</div>
          ${tsStr ? `<div style="font-size:9px;color:#94a3b8;text-align:center">${tsStr}</div>` : ''}
        </div>`;
      }).join('')}
    </div>`;

    // ── Matched entity pills ─────────────────────────────────────────────────
    const _matchedCos  = r.matched_company_ids  || null;
    const _matchedDrugs= r.matched_drug_ids     || null;
    const _entityPillsHtml = (_matchedCos || _matchedDrugs) ? `<div style="margin-bottom:10px">
      <div class="si-detail-label" style="margin-bottom:5px">Matched Entities</div>
      <div style="display:flex;flex-wrap:wrap;gap:5px">
        ${(_matchedCos || []).map(cId => `<span onclick="event.stopPropagation();openCompanyEntityModal('${cId}','${cId}','')" style="display:inline-block;font-size:11px;font-weight:600;background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;border-radius:12px;padding:3px 9px;cursor:pointer" title="Open company card">🏢 ${cId}</span>`).join('')}
        ${(_matchedDrugs || []).map(dId => `<span onclick="event.stopPropagation();openDrugEntityModal('${dId}','${dId}',event)" style="display:inline-block;font-size:11px;font-weight:600;background:#f0fdf4;color:#15803d;border:1px solid #bbf7d0;border-radius:12px;padding:3px 9px;cursor:pointer" title="Open drug card">💊 ${dId}</span>`).join('')}
      </div>
    </div>` : '';

    // ── Rejection reason ─────────────────────────────────────────────────────
    const _rejectionHtml = (status === 'rejected' && r.rejection_reason) ? `<div style="background:#fff1f2;border:1px solid #fca5a5;border-left:3px solid #dc2626;border-radius:6px;padding:8px 11px;margin-bottom:10px">
      <div class="si-detail-label" style="color:#dc2626;margin-bottom:3px">Rejection Reason</div>
      <div style="font-size:12px;color:#991b1b">${r.rejection_reason}</div>
    </div>` : '';

    return `<tr class="si-data-row" onclick="siToggleDetail('${r.id}')">
  <td style="white-space:nowrap">${date}</td>
  <td style="white-space:nowrap">${r.submitted_by || '—'}</td>
  <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${title}">${title}</td>
  <td>${urlDom ? `<a href="${r.source_url}" target="_blank" onclick="event.stopPropagation()" style="color:#2563eb;font-size:11px">${urlDom}</a>` : '—'}</td>
  <td><span class="si-status-badge si-status-${status}">${status.replace('_',' ')}</span></td>
  <td class="si-conf-badge">${conf}</td>
  <td style="white-space:nowrap;color:#64748b;font-size:11px"><span id="${chevId}">▶ Details</span></td>
</tr>
<tr class="si-detail-row" id="${detId}">
  <td colspan="7"><div class="si-detail-inner" id="si-di-${r.id}">
    ${_siTimeline}
    ${_rejectionHtml}
    ${_entityPillsHtml}
    <div class="si-detail-grid">
      <div class="si-detail-section">
        <div class="si-detail-label">Source Link</div>
        <div class="si-detail-value">${r.source_url ? `<a href="${r.source_url}" target="_blank" onclick="event.stopPropagation()" style="color:#2563eb;word-break:break-all;font-size:11px">${r.source_url.length > 80 ? r.source_url.slice(0,77)+'…' : r.source_url}</a><div style="margin-top:6px"><a href="${r.source_url}" target="_blank" rel="noopener" data-trusted="1" onclick="event.stopPropagation()" style="display:inline-block;background:#1d4ed8;color:#fff;font-size:11px;font-weight:600;border-radius:6px;padding:4px 10px;text-decoration:none">${/\.pdf|\/pdf|bluematrix/i.test(r.source_url)?'📄 View source PDF':'↗ Open source'}</a></div>` : '—'}</div>
      </div>
      ${(()=>{const rpj=r.raw_payload_json||{};const nm=rpj.attached_file;const pth=rpj.attached_file_path;
        if(!nm&&!pth)return '';
        return `<div class="si-detail-section"><div class="si-detail-label">Attached PDF</div>
          <div class="si-detail-value" style="font-size:11.5px">${pth
            ? `📎 <strong>${nm||'PDF'}</strong> &nbsp;<span style="color:#15803d;font-weight:700">✓ saved to library</span>`
            : `📎 <strong>${nm||'file'}</strong> &nbsp;<span style="color:#b91c1c;font-weight:700">⚠ not uploaded — re-attach the PDF and resubmit</span>`}</div></div>`;})()}
      <div class="si-detail-section">
        <div class="si-detail-label">Submitted Text</div>
        <div class="si-detail-value" style="max-height:80px;overflow-y:auto">${r.submitted_text || '—'}</div>
      </div>
      ${r.extracted_summary ? `<div class="si-detail-section" style="grid-column:1/-1">
        <div class="si-detail-label">Claude Summary</div>
        <div class="si-detail-value">${r.extracted_summary}</div>
      </div>` : ''}
      ${r.extracted_entities_json ? `<div class="si-detail-section" style="grid-column:1/-1">
        <div class="si-detail-label">Extracted Entities</div>
        <div class="si-detail-value" style="font-size:11px;color:#475569">${JSON.stringify(r.extracted_entities_json, null, 1).slice(0,300)}</div>
      </div>` : ''}
      ${r.proposed_actions_json ? `<div class="si-detail-section" style="grid-column:1/-1">
        <div class="si-detail-label">Proposed Actions</div>
        <div class="si-detail-value">${(r.proposed_actions_json||[]).map(a =>
          `<div style="font-size:11.5px;margin-bottom:4px">• <strong>${a.action}</strong>${a.table?' → '+a.table:''}: ${a.rationale||''}</div>`
        ).join('')}</div>
      </div>` : ''}
    </div>
    <div class="si-action-bar">
      <button class="si-action-btn si-btn-approve"  onclick="siSendToQueue('${r.id}',this);event.stopPropagation()">✅ Send to Queue</button>
      <button class="si-action-btn si-btn-info"     onclick="siSetStatus('${r.id}','needs_review',this);event.stopPropagation()">💬 Needs Review</button>
      <button class="si-action-btn si-btn-reject"   onclick="siSetStatus('${r.id}','rejected',this);event.stopPropagation()">❌ Reject</button>
    </div>
  </div></td>
</tr>`;
  }).join('');
}

function siToggleDetail(id) {
  const el   = document.getElementById(`si-di-${id}`);
  const chev = document.getElementById(`si-chev-${id}`);
  if (el) {
    const isOpen = el.classList.toggle('open');
    if (chev) chev.textContent = isOpen ? '▼ Details' : '▶ Details';
  }
}

async function siSetStatus(id, newStatus, btn) {
  if (btn) { btn.disabled = true; btn.style.opacity = '0.5'; }
  try {
    const reviewer = (window._currentUser || 'reviewer');
    const { error } = await _sb.from('submitted_intel')
      .update({
        status:      newStatus,
        reviewer:    reviewer,
        reviewed_at: new Date().toISOString(),
      })
      .eq('id', id);
    if (error) throw error;
    const row = _siData.find(r => r.id === id);
    if (row) { row.status = newStatus; row.reviewer = reviewer; }
    siRender();
  } catch(e) {
    console.warn('[si review] update error:', e);
    if (btn) { btn.disabled = false; btn.style.opacity = ''; }
  }
}

async function siSendToQueue(id, btn) {
  if (btn) { btn.disabled = true; btn.textContent = 'Sending…'; }
  try {
    const row = _siData.find(r => r.id === id);
    if (!row) throw new Error('Row not found in local cache');

    const entities  = row.extracted_entities_json || {};
    const companies = entities.companies || [];
    const drugs     = entities.drugs     || [];
    const areas     = entities.areas     || [];
    const targets   = entities.targets   || [];

    const queueRow = {
      entity_type:    drugs[0] ? 'molecule' : 'company',
      company_name:   companies[0] || null,
      drug_name:      drugs[0]     || null,
      area_id:        areas[0]     || 'tl1a',
      target:         targets[0]   || null,
      overlap:        'Direct',
      reason:         row.extracted_summary || row.submitted_text || null,
      source_url:     row.source_url        || null,
      source:         'user_intake',
      discovered_by:  row.submitted_by      || null,
      why_discovered: row.extracted_summary || row.submitted_text || null,
      review_notes:   row.submitted_text    || null,
      status:         'pending',
      discovered_at:  new Date().toISOString(),
    };

    const { error: qErr } = await _sb.from('discovery_queue').insert([queueRow]);
    if (qErr) throw qErr;

    // Mark the submission as imported
    const reviewer = (window._currentUser || 'reviewer');
    const { error: sErr } = await _sb.from('submitted_intel')
      .update({
        status:      'imported',
        reviewer:    reviewer,
        reviewed_at: new Date().toISOString(),
        imported_at: new Date().toISOString(),
      })
      .eq('id', id);
    if (sErr) throw sErr;

    const cached = _siData.find(r => r.id === id);
    if (cached) { cached.status = 'imported'; cached.reviewer = reviewer; }
    siRender();
  } catch(e) {
    console.warn('[si queue] error:', e);
    alert(`Failed to send to Discovery Queue: ${e?.message || e}`);
    if (btn) { btn.disabled = false; btn.textContent = '🔍 Send to Discovery Queue'; }
  }
}
// Run on page load

// ── WEEKLY LEARNING TASKS ─────────────────────────────────────────
const WEEKLY_TASKS = [
 { day: 'Monday', tasks: [
 { id:'m1', area:'IBD', color:'#c45b11', text:'Read TL1A × IL-23 Field Intelligence — focus on deal benchmarks and ATLAS-UC timeline', tab:'tl1a', anchor:'tl1a-intel-anchor' },
 { id:'m2', area:'IBD', color:'#c45b11', text:'Review TL1A Catalyst Calendar — identify the 2 most important readouts to monitor', tab:'tl1a', anchor:'tl1a-readouts-anchor' },
 { id:'m3', area:'General', color:'#4b5563', text:'Check Recent Deals on Home — is anything new since last week?', tab:'home', anchor:'home-deals-anchor' },
 ]},
 { day: 'Tuesday', tasks: [
 { id:'t1', area:'Resp', color:'#2563eb', text:'Read TSLP × IL-33 Field Intelligence — understand the QX031N/Roche deal rationale', tab:'tslp', anchor:'tslp-intel-anchor' },
 { id:'t2', area:'Resp', color:'#2563eb', text:'Review TSLP Competitive Landscape — compare FORMAT column: what formats are partners choosing?', tab:'tslp', anchor:'tslp-landscape-anchor' },
 { id:'t3', area:'Type 2', color:'#9d174d', text:'Skim IL-4Rα × TSLP tab — understand how dupilumab dominance creates the bispecific opportunity', tab:'il4ra-tslp', anchor:'il4ra-tslp-intel-anchor' },
 ]},
 { day: 'Wednesday', tasks: [
 { id:'w1', area:'AD', color:'#7c3aed', text:'Read IL-4Rα × OX40L — focus on amlitelimab (Sanofi) as the reference asset for AD immune reset', tab:'il4ra-ox40l', anchor:'il4ra-ox40l-intel-anchor' },
 { id:'w2', area:'AD', color:'#7c3aed', text:'Review OX40L Deal Spotlight — understand the deal structure and valuation logic', tab:'il4ra-ox40l', anchor:'il4ra-ox40l-deal-anchor' },
 { id:'w3', area:'IBD', color:'#c45b11', text:'Read TL1A Estimand Guide — this is the most important concept for understanding Ph3 data quality', tab:'tl1a', anchor:'tl1a-estimand-anchor' },
 ]},
 { day: 'Thursday', tasks: [
 { id:'th1', area:'TED', color:'#065f46', text:'Read IGF1R × TSHR Field Intelligence — understand teprotumumab as the reference and linsitinib LIDS results', tab:'igf1r-tshr', anchor:'igf1r-tshr-intel-anchor' },
 { id:'th2', area:'AI', color:'#5b21b6', text:'Read FcRn Bispecific tab — focus on how FcRn recycling biology creates the bispecific rationale', tab:'fcrn', anchor:'fcrn-edu-anchor' },
 { id:'th3', area:'AI', color:'#5b21b6', text:'Compare FcRn Competitive Landscape — efgartigimod vs nipocalimab vs rozanolixizumab differentiation', tab:'fcrn', anchor:'fcrn-landscape-anchor' },
 ]},
 { day: 'Friday', tasks: [
 { id:'f1', area:'Immune Reset', color:'#991b1b', text:'Read BCMA × CD19 × CD3 (ALX002) tab — understand why dual B-cell lineage depletion is the hypothesis', tab:'ace', anchor:'ace-edu-anchor' },
 { id:'f2', area:'Immune Reset', color:'#991b1b', text:'Review ALX002 Competitive Landscape — KT501 vs CLN-978 vs CAR-T: what is Ailux doing differently?', tab:'ace', anchor:'ace-landscape-anchor' },
 { id:'f3', area:'General', color:'#4b5563', text:'Review Meridian Daily Reader — are all 7 coverage areas still current? Submit anything new via ＋ Submit Intel', tab:'home', anchor:'meridian-reader-anchor' },
 ]},
];

function getWeekKey() {
 const now = new Date();
 const day = now.getDay(); // 0=Sun
 const monday = new Date(now);
 monday.setDate(now.getDate() - (day === 0 ? 6 : day - 1));
 return `wt-${monday.getFullYear()}-${monday.getMonth()}-${monday.getDate()}`;
}
function getWeeklyState() {
 return JSON.parse(localStorage.getItem(getWeekKey()) || '{}');
}
function setTaskDone(id, done) {
 const state = getWeeklyState();
 state[id] = done;
 localStorage.setItem(getWeekKey(), JSON.stringify(state));
 renderWeeklyTasks();
}
function resetWeeklyTasks() {
 if (!confirm('Reset all tasks for this week?')) return;
 localStorage.removeItem(getWeekKey());
 renderWeeklyTasks();
}
function renderWeeklyTasks() {
 const body = document.getElementById('weekly-tasks-body');
 if (!body) return;
 const state = getWeeklyState();
 const todayIdx = new Date().getDay(); // 0=Sun, 1=Mon … 5=Fri, 6=Sat
 // Map: 1=Mon,2=Tue,3=Wed,4=Thu,5=Fri — idx 0..4 in array
 const todayTaskIdx = todayIdx >= 1 && todayIdx <= 5 ? todayIdx - 1 : -1;
 body.innerHTML = WEEKLY_TASKS.map((dayObj, i) => {
 const isToday = i === todayTaskIdx;
 const doneCount = dayObj.tasks.filter(t => state[t.id]).length;
 const totalCount = dayObj.tasks.length;
 return `<div class="wtc-day">
 <div class="wtc-day-hd ${isToday ? 'today' : ''}">
 ${isToday ? '<span class="wtc-today-badge">Today</span>' : ''}
 ${dayObj.day}
 <span style="margin-left:auto;font-size:10px;font-weight:600;color:${doneCount===totalCount?'#2a7a47':'#8a9bb0'}">${doneCount}/${totalCount} done</span>
 </div>
 ${dayObj.tasks.map(t => {
 const done = !!state[t.id];
 return `<label class="wtc-task ${done ? 'done' : ''}" onclick="event.preventDefault();setTaskDone('${t.id}',${!done})">
 <input type="checkbox" ${done ? 'checked' : ''} onchange="event.stopPropagation();setTaskDone('${t.id}',this.checked)">
 <span>
 <span class="wtc-task-area" style="background:${t.color}">${t.area}</span>
 ${t.text}
 ${t.tab ? `<a class="ct-link" href="#" onclick="event.stopPropagation();switchTabTo('${t.tab}');setTimeout(()=>scrollToSection('${t.anchor}'),250);return false;" style="font-size:11px;margin-left:4px">→ Go</a>` : ''}
 </span>
 </label>`;
 }).join('')}
 </div>`;
 }).join('');
}

// ── Rolling Deal Tracker ─────────────────────────────────────────────────────
let _rdtAll = [];
let _rdtShown = 10;

const RDT_CO_CLASS = {
  'eli lilly':'hi-lilly','lilly':'hi-lilly',
  'sanofi':'hi-sanofi','takeda':'hi-takeda',
  'abbvie':'hi-abbvie','roche':'hi-roche','genentech':'hi-roche',
  'gilead':'hi-gilead',
};
function rdtCoClass(name) {
  const lc = (name||'').toLowerCase();
  for (const [k,v] of Object.entries(RDT_CO_CLASS)) if (lc.includes(k)) return v;
  return '';
}
function rdtModClass(dealType, areaId) {
  const dt = (dealType||'').toLowerCase();
  if (dt.includes('ai')) return ['rdt-mod-ai', dealType];
  if (dt.includes('tce')||dt.includes('bispecific')||dt.includes('trispecific')) return ['rdt-mod-tce', dealType];
  if (dt.includes('cell')||dt.includes('car')||dt.includes('tcr')||dt.includes('rna')) return ['rdt-mod-cell', dealType];
  if (dt.includes('biolog')||dt.includes('mab')||dt.includes('antibod')) return ['rdt-mod-bio', dealType];
  if (dt.includes('oral')||dt.includes('small')||dt.includes('iv &')) return ['rdt-mod-oral', dealType];
  if (areaId && AREA_LABELS[areaId]) return ['rdt-mod-area', AREA_LABELS[areaId]];
  if (dealType && !['license','acquisition','collab','option'].includes(dealType)) return ['rdt-mod-def', dealType];
  return ['rdt-mod-def', dealType || '—'];
}
function rdtFmtEcon(d) {
  const fmt = m => m >= 1000 ? `$${(m/1000).toFixed(m%1000===0?0:2).replace(/\.?0+$/,'')}B` : `$${m}M`;
  const parts = [];
  if (d.upfront_usd_m) parts.push(`${fmt(d.upfront_usd_m)} upfront`);
  if (d.total_usd_m && d.total_usd_m !== d.upfront_usd_m) parts.push(`up to ${fmt(d.total_usd_m)}`);
  return parts.join('; ') || 'Not disclosed';
}

function rdtFmtDate(d) {
  if (!d) return '';
  try {
    const dt = new Date(d + 'T12:00:00');
    return dt.toLocaleDateString('en-US', {month:'short', day:'numeric', year:'numeric'});
  } catch(e) { return d; }
}

function rdtInitResize() {
  var table = document.getElementById('rdt-main-table');
  if (!table) return;
  table.querySelectorAll('thead th').forEach(function(th) {
    var handle = document.createElement('div');
    handle.className = 'rdt-col-handle';
    th.appendChild(handle);
    handle.addEventListener('mousedown', function(e) {
      e.preventDefault();
      handle.classList.add('dragging');
      var startX = e.pageX;
      var startW = th.getBoundingClientRect().width;
      function onMove(e2) {
        var newW = Math.max(48, startW + e2.pageX - startX);
        th.style.minWidth = newW + 'px';
        th.style.width    = newW + 'px';
      }
      function onUp() {
        handle.classList.remove('dragging');
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
      }
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    });
  });
}

async function loadRollingDeals() {
  const tbody = document.getElementById('rdt-tbody');
  if (!tbody) return;
  try {
    const { data, error } = await _sb.from('deals').select('*').order('deal_date', { ascending: false });
    if (error) throw error;
    _rdtAll = data || [];
    renderRollingDeals();
    rdtInitResize();
  } catch(e) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="7" style="color:#dc2626;font-size:12px;padding:14px;">Error: ${e.message}</td></tr>`;
  }
}

function renderRollingDeals() {
  const tbody = document.getElementById('rdt-tbody');
  const btn   = document.getElementById('rdt-more-btn');
  if (!tbody) return;
  const slice = _rdtAll.slice(0, _rdtShown);
  tbody.innerHTML = slice.map(d => {
    const fromCls = rdtCoClass(d.from_company);
    const toCls   = rdtCoClass(d.to_company);
    const [modCls, modLabel] = rdtModClass(d.deal_type, d.area_id);
    const econ = rdtFmtEcon(d);
    const rat  = (d.detail || d.ailux_signal || '').replace(/<[^>]+>/g,'');
    const ratShort = rat.length > 120 ? rat.slice(0,120)+'…' : rat;
    return `<tr>
<td class="rdt-date">${rdtFmtDate(d.deal_date)||d.deal_date_label||''}</td>
<td><span class="rdt-co ${fromCls}">${d.from_company||''}</span></td>
<td><span class="rdt-co ${toCls}">${d.to_company||''}</span></td>
<td class="rdt-focus">${d.headline||''}</td>
<td><span class="rdt-mod ${modCls}">${modLabel}</span></td>
<td class="rdt-econ">${econ}</td>
<td class="rdt-rat">${ratShort}</td>
</tr>`;
  }).join('');
  if (btn) btn.style.display = _rdtShown >= _rdtAll.length ? 'none' : 'inline-block';
}

function rdtLoadMore() {
  _rdtShown += 10;
  renderRollingDeals();
}

// ── II Live Intel Feed ────────────────────────────────────────────────────────
function iiToggle(id) {
  const detail = document.getElementById('ii-detail-' + id);
  const chev   = document.getElementById('ii-chev-' + id);
  if (!detail) return;
  const open = detail.classList.toggle('open');
  if (chev) chev.textContent = open ? '▼' : '▶';
}


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

// ── Home panel overlay ────────────────────────────────────────────────────────
const HOME_PANEL_META = {
  catalysts: { title: '📅 Catalysts & Signals', color: '#1e4a82' },
  deals:     { title: '💼 Recent Deal Activity', color: '#1a5c2e' },
  updates:   { title: '⚡ Essential Updates',    color: '#b84e10' },
  si:        { title: '📥 Submitted Intel',      color: '#374151', onOpen: () => siLoad() },
  news:      { title: '📰 Important Articles to Know', color: '#6b21a8', onOpen: () => loadNewsModule() },
};
function openHomePanel(panel) {
  const meta = HOME_PANEL_META[panel];
  if (!meta) return;
  // Hide all panels, show target
  document.querySelectorAll('.home-panel').forEach(p => { p.style.display = 'none'; });
  const pEl = document.getElementById(`home-panel-${panel}`);
  if (pEl) pEl.style.display = 'block';
  // Update header
  const hd = document.getElementById('home-overlay-hd');
  if (hd) hd.style.background = `linear-gradient(90deg,${meta.color},${meta.color}cc)`;
  const title = document.getElementById('home-overlay-title');
  if (title) title.textContent = meta.title;
  // Mark active launcher
  document.querySelectorAll('.home-launcher').forEach(l => l.classList.remove('active'));
  const launcher = document.querySelector(`.home-launcher[data-panel="${panel}"]`);
  if (launcher) launcher.classList.add('active');
  // Show overlay
  const backdrop = document.getElementById('home-overlay-backdrop');
  const card = document.getElementById('home-overlay-card');
  if (backdrop) backdrop.classList.add('open');
  if (card) card.classList.add('open');
  // Prevent page scroll while overlay is open
  document.body.style.overflow = 'hidden';
  // Run panel-specific onOpen hook
  if (meta.onOpen) meta.onOpen();
}
// ── Important Articles to Know — News Intelligence Module ────────────────────

let _newsData = null;  // cached {today: [], week: []}
let _newsTab = 'today';

const NEWS_AREA_LABELS = { tl1a:'TL1A', tslp:'TSLP', il4ra:'IL-4Rα', igf1r:'IGF1R', fcrn:'FcRn', tcell:'T-cell' };

async function loadNewsModule() {
  if (_newsData) { renderNewsArticles(); return; }
  const body = document.getElementById('news-articles-body');
  if (body) body.innerHTML = '<div class="na-empty">Loading articles…</div>';
  try {
    const ANON = (typeof SUPABASE_ANON !== 'undefined') ? SUPABASE_ANON : '';
    const url = `https://tghntyofptvfhmtchwcv.supabase.co/rest/v1/news_articles?is_this_week=eq.true&source_validation_status=neq.invalid&review_status=neq.suppressed&order=relevance_score.desc&limit=40&select=id,headline,article_url,source_name,published_at,meridian_summary,why_it_matters,relevance_score,priority_level,matched_company_ids,matched_area_ids,is_today,is_this_week`;
    const resp = await fetch(url, {
      headers: { 'apikey': ANON, 'Authorization': `Bearer ${ANON}` }
    });
    const articles = resp.ok ? await resp.json() : [];
    const today = articles.filter(a => a.is_today);
    const week  = articles.filter(a => !a.is_today);
    _newsData = { today, week };
    // Update counts
    const ct = document.getElementById('news-count-today');
    const cw = document.getElementById('news-count-week');
    if (ct) ct.textContent = today.length || '0';
    if (cw) cw.textContent = (today.length + week.length) || '0';
    renderNewsArticles();
  } catch(e) {
    const body = document.getElementById('news-articles-body');
    if (body) body.innerHTML = `<div class="na-empty">Could not load articles: ${e.message}</div>`;
  }
}

function newsTabSwitch(tab) {
  _newsTab = tab;
  document.querySelectorAll('.news-tab-btn').forEach(b => b.classList.remove('active'));
  const btn = document.getElementById(`news-tab-${tab}`);
  if (btn) btn.classList.add('active');
  renderNewsArticles();
}

function _naFormatDate(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', { month:'short', day:'numeric', year:'numeric' });
  } catch { return ''; }
}

function _naSourceIcon(name) {
  const icons = { 'FierceBiotech': '🔬', 'BioPharma Dive': '📊', 'STAT News': '📰', 'Endpoints': '📡' };
  return icons[name] || '📄';
}

function renderNewsArticles() {
  if (!_newsData) return;
  const body = document.getElementById('news-articles-body');
  if (!body) return;

  const list = _newsTab === 'today'
    ? _newsData.today.slice(0, 5)
    : [..._newsData.today, ..._newsData.week].slice(0, 10);

  if (!list.length) {
    const msg = _newsTab === 'today'
      ? 'No articles fetched today yet. Run <code>fetch_homepage_news.py</code> to populate.'
      : 'No articles this week. Run <code>fetch_homepage_news.py</code> to populate.';
    body.innerHTML = `<div class="na-empty">${msg}</div>`;
    return;
  }

  const cards = list.map(a => {
    const pCls = a.priority_level || 'standard';
    const dateStr = _naFormatDate(a.published_at);
    const icon = _naSourceIcon(a.source_name);

    // Area tags
    const areaTags = (a.matched_area_ids || []).map(id =>
      `<span class="na-tag area">${NEWS_AREA_LABELS[id] || id}</span>`
    ).join('');

    // Summary block — prefer AI-generated, fall back to empty
    const summary = a.meridian_summary
      ? `<div class="na-summary">${_esc(a.meridian_summary)}</div>`
      : '';

    // Why it matters block
    const why = a.why_it_matters
      ? `<div class="na-why">💡 ${_esc(a.why_it_matters)}</div>`
      : '';

    // Tags row — only show if any tags
    const tagsRow = areaTags
      ? `<div class="na-tags">${areaTags}</div>`
      : '';

    return `<div class="na-card na-${pCls}">
      <div class="na-headline"><a href="${_esc(a.article_url)}" target="_blank" rel="noopener">${_esc(a.headline)}</a></div>
      <div class="na-meta">
        <span class="na-source">${icon} ${_esc(a.source_name)}</span>
        <span class="na-date">${dateStr}</span>
        <span class="na-priority ${pCls}">${pCls}</span>
      </div>
      ${summary}${why}${tagsRow}
    </div>`;
  }).join('');

  body.innerHTML = `<div class="news-articles-list">${cards}</div>`;
}

function closeHomePanel() {
  const backdrop = document.getElementById('home-overlay-backdrop');
  const card = document.getElementById('home-overlay-card');
  if (backdrop) backdrop.classList.remove('open');
  if (card) card.classList.remove('open');
  document.querySelectorAll('.home-launcher').forEach(l => l.classList.remove('active'));
  document.body.style.overflow = '';
}
// Close overlay on Escape key
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeHomePanel(); });


document.addEventListener('DOMContentLoaded', () => { renderIntelSubmissions(); renderWeeklyTasks(); loadDeals(); loadCatalysts(); loadIdentityHealth(); loadIdentityFooter(); loadGovernanceViolations(); loadMeridianReader(); dknLoadSbData(); loadTopOpps(); });

// ── BIOLOGY DEEP DIVE MODAL ───────────────────────────────────────
function openBioDD(id) { const el = document.getElementById(id); if (el) el.classList.add('open'); }
function closeBioDD(id) { const el = document.getElementById(id); if (el) el.classList.remove('open'); }

/* ── Spyre drug popup hover persistence ── */
let _spyrePopupTimer = null;
let _spyreActiveId = null;
function showSpyrePopup(id) {
  clearTimeout(_spyrePopupTimer);
  document.querySelectorAll('.spyre-drug-popup').forEach(p => { p.style.display='none'; });
  document.querySelectorAll('.spyre-drug-btn').forEach(b => b.classList.remove('spy-popup-active'));
  _spyreActiveId = id;
  const btn = document.getElementById(id);
  if (!btn) return;
  btn.classList.add('spy-popup-active');
  const popup = btn.querySelector('.spyre-drug-popup');
  if (!popup) return;
  // Show with default left so we can measure popup width
  popup.style.left = '0';
  popup.style.transform = 'none';
  popup.style.display = 'block';
  // Clamp horizontal position to viewport after paint
  requestAnimationFrame(() => {
    const btnR = btn.getBoundingClientRect();
    const popW = popup.offsetWidth;
    const vw = window.innerWidth;
    const margin = 10;
    // Ideal viewport left: centered on button
    let vpLeft = btnR.left + btnR.width / 2 - popW / 2;
    vpLeft = Math.max(margin, Math.min(vpLeft, vw - popW - margin));
    // Convert to CSS left relative to button's top-left corner
    popup.style.left = (vpLeft - btnR.left) + 'px';
  });
}
function hideSpyrePopup() {
  clearTimeout(_spyrePopupTimer);
  document.querySelectorAll('.spyre-drug-popup').forEach(p => { p.style.display='none'; });
  document.querySelectorAll('.spyre-drug-btn').forEach(b => b.classList.remove('spy-popup-active'));
  _spyreActiveId = null;
}
function cancelHideSpyrePopup() { /* no-op — kept for compatibility */ }
document.addEventListener('keydown', e => { if (e.key === 'Escape') { document.querySelectorAll('.bio-dd-overlay.open').forEach(el => el.classList.remove('open')); }});

// ── TL1A PROGRAM INTELLIGENCE TABLE ──────────────────────────────
// ── TL1A LIVE INTEL FEED ──────────────────────────────────────────
async function loadTL1AIntelFeed() {
 const body = document.getElementById('tl1a-intel-feed-body');
 if (!body || !_sb) { return; }
 try {
  const { data: iaRows } = await _sb.from('intel_areas').select('intel_id,area_id,target_id').or('target_id.eq.tl1a,area_id.eq.tl1a').limit(100);
  const tl1aIds = (iaRows||[]).map(r=>r.intel_id);
  let rows = [];
  if (tl1aIds.length) {
   const { data } = await _sb.from('intel').select('id,intel_date,headline,body,source_url,source_name,intel_type,importance')
    .in('id', tl1aIds.slice(0,50)).order('intel_date',{ascending:false}).limit(15);
   rows = data||[];
  }
  if (!rows.length) { body.innerHTML = '<div style="color:#94a3b8;font-size:12px;">No TL1A intelligence in Supabase yet — check back after next research update.</div>'; return; }
  const TYPE_LABEL = {deal:'Deal',clinical:'Clinical',regulatory:'Regulatory',news:'News',conference:'Conference',user_submitted:'User Intel'};
  body.innerHTML = rows.map(item => {
   const dotCls = item.importance==='high'?'high':item.importance==='medium'?'medium':'low';
   const typeTag = item.intel_type ? `<span class="intel-feed-type">${TYPE_LABEL[item.intel_type]||item.intel_type}</span>` : '';
   const src = item.source_url ? `<a href="${item.source_url}" target="_blank" rel="noopener" style="font-size:10px;color:#2563eb;margin-left:4px;">↗ Source</a>` : '';
   return `<div class="intel-feed-item">
    <div class="intel-feed-dot ${dotCls}"></div>
    <div style="flex:1;min-width:0">
     <div class="intel-feed-meta">${typeTag}<span class="intel-feed-date">${item.intel_date||''}</span>${src}</div>
     <div style="font-size:12px;font-weight:700;color:#1e293b;line-height:1.45">${item.headline||''}</div>
     ${item.body?`<div style="font-size:11px;color:#475569;margin-top:4px;line-height:1.55">${item.body}</div>`:''}
     <div style="font-size:10px;color:#94a3b8;margin-top:3px">${item.source_name||''}</div>
    </div>
   </div>`;
  }).join('');
 } catch(e) { if(body) body.innerHTML = `<div style="color:#dc2626;font-size:12px">Feed error: ${e.message}</div>`; }
}

// ── TOC NAVIGATION ────────────────────────────────────────────────
const TOC_MAP = {
 home: [
 {label:'Meridian Daily Reader', id:'meridian-reader-anchor'},
 {label:'Key Catalysts', id:'home-catalysts-anchor'},
 {label:'BD Signal', id:'bd-signal-panel'},
 {label:'Recent Deals', id:'home-deals-anchor'},
 ],
 tl1a: [
 {label:'Program Intelligence', id:'tl1a-area-pi-wrap'},
 {label:'Intel Feed', id:'tl1a-intel-feed-card'},
 {label:'Ailux Profile', id:'tl1a-ailux-anchor'},
 {label:'Estimand Guide', id:'tl1a-estimand-anchor'},
 {label:'Catalyst Calendar', id:'tl1a-readouts-anchor'},
 {label:'IBD Market & SOC', id:'tl1a-ailux-anchor'},
 {label:'Chinese Programs', id:'tl1a-china-anchor'},
 ],
 tslp: [
 {label:'Field Intelligence', id:'tslp-intel-anchor'},
 {label:'Summary Stats', id:'tslp-stats-anchor'},
 {label:'Deal Spotlight', id:'tslp-deal-anchor'},
 {label:'Ailux Profile', id:'tslp-ailux-anchor'},
 {label:'Estimand Guide', id:'tslp-estimand-anchor'},
 {label:'Catalyst Calendar', id:'tslp-readouts-anchor'},
 {label:'Competitive Landscape', id:'tslp-landscape-anchor'},
 {label:'Alarmin Strategy', id:'tslp-alarmin-anchor'},
 ],
 'il4ra-tslp': [
 {label:'Field Intelligence', id:'il4ra-tslp-intel-anchor'},
 {label:'Summary Stats', id:'il4ra-tslp-stats-anchor'},
 {label:'Platform Spotlight', id:'il4ra-tslp-platform-anchor'},
 {label:'Ailux Profile', id:'il4ra-tslp-ailux-anchor'},
 {label:'Biology Education', id:'il4ra-tslp-edu-anchor'},
 {label:'Catalyst Calendar', id:'il4ra-tslp-readouts-anchor'},
 {label:'Competitive Landscape', id:'il4ra-tslp-landscape-anchor'},
 ],
 'il4ra-ox40l': [
 {label:'Field Intelligence', id:'il4ra-ox40l-intel-anchor'},
 {label:'Summary Stats', id:'il4ra-ox40l-stats-anchor'},
 {label:'Deal Spotlight', id:'il4ra-ox40l-deal-anchor'},
 {label:'Ailux Profile', id:'il4ra-ox40l-ailux-anchor'},
 {label:'Biology Education', id:'il4ra-ox40l-edu-anchor'},
 {label:'Catalyst Calendar', id:'il4ra-ox40l-readouts-anchor'},
 {label:'Competitive Landscape', id:'il4ra-ox40l-landscape-anchor'},
 ],
 'igf1r-tshr': [
 {label:'Field Intelligence', id:'igf1r-tshr-intel-anchor'},
 {label:'Summary Stats', id:'igf1r-tshr-stats-anchor'},
 {label:'Mechanism Spotlight', id:'igf1r-tshr-mech-anchor'},
 {label:'Ailux Profile', id:'igf1r-tshr-ailux-anchor'},
 {label:'Biology Education', id:'igf1r-tshr-edu-anchor'},
 {label:'Catalyst Calendar', id:'igf1r-tshr-readouts-anchor'},
 {label:'Competitive Landscape', id:'igf1r-tshr-landscape-anchor'},
 ],
 fcrn: [
 {label:'Field Intelligence', id:'fcrn-intel-anchor'},
 {label:'Summary Stats', id:'fcrn-stats-anchor'},
 {label:'Platform Spotlight', id:'fcrn-platform-anchor'},
 {label:'Ailux Profile', id:'fcrn-ailux-anchor'},
 {label:'Biology Education', id:'fcrn-edu-anchor'},
 {label:'Catalyst Calendar', id:'fcrn-readouts-anchor'},
 {label:'Competitive Landscape', id:'fcrn-landscape-anchor'},
 ],
 ace: [
 {label:'Field Intelligence', id:'ace-intel-anchor'},
 {label:'Summary Stats', id:'ace-stats-anchor'},
 {label:'Deal Spotlight', id:'ace-deal-anchor'},
 {label:'Ailux Profile', id:'ace-ailux-anchor'},
 {label:'Biology Education', id:'ace-edu-anchor'},
 {label:'Catalyst Calendar', id:'ace-readouts-anchor'},
 {label:'Competitive Landscape', id:'ace-landscape-anchor'},
 ],
};
function buildToc(activeTab) {
 const dd = document.getElementById('toc-dropdown');
 if (!dd) return;
 const items = TOC_MAP[activeTab] || [];
 dd.innerHTML = `<div class="toc-section">${activeTab.toUpperCase()} Sections</div>` +
 items.map(it=>`<span class="toc-item" onclick="scrollToSection('${it.id}');closeToc()">${it.label}</span>`).join('');
}
function toggleToc() {
 document.getElementById('toc-dropdown')?.classList.toggle('open');
}
function closeToc() {
 document.getElementById('toc-dropdown')?.classList.remove('open');
}
function scrollToSection(anchorId) {
 const el = document.getElementById(anchorId);
 if (el) el.scrollIntoView({behavior:'smooth', block:'start'});
}
// Close TOC on outside click
document.addEventListener('click', e => {
 const wrap = document.getElementById('toc-wrap');
 if (wrap && !wrap.contains(e.target)) closeToc();
});

// ── CHART COLLAPSE ────────────────────────────────────────────────
function toggleChartCollapse(id) {
 const body = document.getElementById(id+'-body');
 const tog = document.getElementById(id+'-toggle');
 if (body) { body.classList.toggle('open'); tog.classList.toggle('open'); }
}

function toggleEdu(id) {
 const body = document.getElementById(id+'-body');
 const tog = document.getElementById(id+'-toggle');
 if (body) {
 body.classList.toggle('open');
 if (tog) tog.textContent = body.classList.contains('open') ? '▲' : '▼';
 }
}

function togglePredict(id) {
 const body = document.getElementById(id+'-body');
 const tog = document.getElementById(id+'-toggle');
 if (body) {
 body.classList.toggle('open');
 if (tog) tog.classList.toggle('open');
 if (tog) tog.textContent = body.classList.contains('open') ? '▲' : '▼';
 }
}

function toggleRuleChip(id) {
 const chip = document.getElementById(id);
 if (chip) chip.classList.toggle('open');
}

// ── INTEL SUBMIT PANEL ────────────────────────────────────────────
function toggleIntelPanel() {
 const panel = document.getElementById('intel-panel-wrap');
 panel.classList.toggle('open');
 if (panel.classList.contains('open')) {
 document.getElementById('intel-panel-text').focus();
 }
}

function analyzeIntelPanel() {
 const text = document.getElementById('intel-panel-text').value.trim();
 const resultsEl = document.getElementById('intel-panel-results');
 if (!text) { resultsEl.innerHTML = '<p style="color:#c45b11;font-size:13px">Please paste some content to analyze.</p>'; return; }

 const d = window._dashData;
 if (!d) { resultsEl.innerHTML = '<p style="color:#c45b11;font-size:13px">Data still loading — please wait a moment and try again.</p>'; return; }

 resultsEl.innerHTML = '<p style="color:#5a7a9e;font-size:13px">Analyzing…</p>';

 // Detect URLs in submission
 const urlMatch = text.match(/https?:\/\/[^\s<>"]+/g);
 const hasUrl = urlMatch && urlMatch.length > 0;
 const confidence = hasUrl ? 'high' : (text.length > 300 ? 'med' : 'low');
 const confLabel = {high:'HIGH', med:'MEDIUM', low:'LOW'};
 const confClass = {high:'confidence-high', med:'confidence-med', low:'confidence-low'};

 const lc = text.toLowerCase();
 const stopWords = new Set(['with','that','this','from','have','been','will','were','they','their','into','also','when','than','more','after','before','which','about','such']);
 const tokens = [...new Set((lc.match(/\b[a-z0-9][a-z0-9\-]{3,}\b/g)||[]).filter(t=>!stopWords.has(t)))];

 const allSources = [
 {label:'TL1A Readout Calendar', rows:d.tl1aReadouts},
 {label:'TL1A Pipeline', rows:d.tl1aPipe},
 {label:'TL1A Monotherapy', rows:d.tl1aMono},
 {label:'TSLP Readout Calendar', rows:d.tslpReadouts},
 {label:'TSLP Pipeline', rows:d.tslpPipe},
 {label:'TSLP Monotherapy', rows:d.tslpMono},
 ];
 const matches = [];
 allSources.forEach(src => {
 if (!src.rows) return;
 src.rows.forEach(row => {
 const rowStr = row.slice(0,6).join(' ').toLowerCase();
 const hits = tokens.filter(t => rowStr.includes(t));
 if (hits.length >= 1) matches.push({ section:src.label, program:row[1], status:row[2], timing:row[3]||'', hits });
 });
 });
 const deduped = matches.filter((m,i,arr)=>arr.findIndex(x=>x.program===m.program)===i);

 // Build result HTML
 const confBadge = `<span class="${confClass[confidence]}">SOURCE CONFIDENCE: ${confLabel[confidence]}</span>`;
 const urlBadge = hasUrl ? `<span class="auto-updated">✓ Source URL detected</span>` : '<span class="confidence-low">No URL — manual verification required</span>';
 const timestamp = new Date().toLocaleString('en-US',{month:'short',day:'numeric',year:'numeric',hour:'2-digit',minute:'2-digit'});

 let html = `<div style="padding:12px 14px;background:#f8fafc;border-radius:6px;border:1px solid #dde3ea">`;
 html += `<div style="font-size:12px;color:#8a9bb0;margin-bottom:8px">Submitted ${timestamp} ${confBadge} ${urlBadge}</div>`;

 if (hasUrl) {
 html += `<div style="font-size:13px;color:#155724;background:#d4edda;padding:8px 12px;border-radius:5px;margin-bottom:10px">
 <strong>✓ Source URL found:</strong> ${urlMatch[0]}<br>
 <span style="font-size:12px;color:#1a5030">This submission has a verifiable source. Any matched programs below should be reviewed for accuracy, then manually updated if confirmed.</span>
 </div>`;
 }

 if (deduped.length === 0) {
 html += `<div style="font-size:13px;color:#2a7a47;font-weight:700">✓ No existing rows matched.</div>
 <div style="font-size:12px;color:#5a7a9e;margin-top:4px">This may represent a new program or deal not yet tracked. Consider adding it to the relevant pipeline file.</div>`;
 } else {
 html += `<div style="font-size:14px;font-weight:800;color:#1a2f50;margin-bottom:10px">Found <span style="color:#c45b11">${deduped.length}</span> tracked program(s) that may be affected:</div>`;
 html += deduped.map(m => {
 const rowConf = m.hits.length >= 3 ? 'confidence-high' : m.hits.length >= 2 ? 'confidence-med' : 'confidence-low';
 return `<div style="padding:10px 12px;margin-bottom:8px;background:white;border-left:3px solid #e8a020;border-radius:4px;box-shadow:0 1px 3px rgba(0,0,0,0.05)">
 <div style="font-weight:800;font-size:13px;color:#1a2f50">${m.program} <span class="${rowConf}" style="font-size:11px">Match: ${m.hits.length >= 3 ? 'STRONG' : m.hits.length >= 2 ? 'MODERATE' : 'WEAK'}</span></div>
 <div style="font-size:12px;color:#5a7a9e;margin-top:3px">${m.section} · Stage: <strong>${m.status}</strong>${m.timing?' · '+m.timing:''}</div>
 <div style="font-size:11px;color:#8a9bb0;margin-top:3px">Matched on: ${m.hits.slice(0,6).join(', ')}</div>
 </div>`;
 }).join('');

 if (hasUrl) {
 html += `<div style="background:#e8f3ff;border:1px solid #90bff0;border-radius:5px;padding:10px 12px;font-size:12px;color:#1a3f6e;margin-top:8px">
 <strong>Action required:</strong> Review each matched program above against the submitted content. If the data has changed (new phase, new timing, new efficacy result), update the corresponding JSON file in the data/ folder and redeploy. The source URL provides evidence for the change.
 </div>`;
 }
 }
 html += `</div>`;
 resultsEl.innerHTML = html;
}

// ── UPDATE BOX TOGGLE ────────────────────────────────────────────
function toggleUpdate(tab) {
 const body = document.getElementById('update-body-' + tab);
 const tog = document.getElementById('update-toggle-' + tab);
 if (body) body.classList.toggle('open');
 if (tog) tog.classList.toggle('open');
}

// ── CROSS-REFERENCE TOOL ─────────────────────────────────────────
function crossRef(tab) {
 const textarea = document.getElementById('update-text-' + tab);
 const resultsEl = document.getElementById('update-results-' + tab);
 const text = textarea.value.trim();
 if (!text) {
 resultsEl.innerHTML = '<span style="color:#8a9bb0">Please paste some text to analyze.</span>';
 return;
 }
 const d = window._dashData;
 if (!d) { resultsEl.innerHTML = '<span style="color:#c45b11">Data not yet loaded. Please wait and try again.</span>'; return; }

 const lc = text.toLowerCase();
 const sources = tab === 'tl1a'
 ? [{label:'Readout Calendar', rows:d.tl1aReadouts}, {label:'Pipeline', rows:d.tl1aPipe}, {label:'Monotherapy Context', rows:d.tl1aMono}]
 : [{label:'Readout Calendar', rows:d.tslpReadouts}, {label:'Pipeline', rows:d.tslpPipe}, {label:'Monotherapy Context', rows:d.tslpMono}];

 // Extract meaningful search tokens (4+ chars, skip common words)
 const stopWords = new Set(['with','that','this','from','have','been','will','were','they','their','into','also','when','than','more','after','before','which','about']);
 const tokens = [...new Set((lc.match(/\b[a-z0-9][a-z0-9\-]{3,}\b/g) || []).filter(t => !stopWords.has(t)))];

 const matches = [];
 sources.forEach(src => {
 if (!src.rows) return;
 src.rows.forEach(row => {
 const rowStr = row.slice(0, 5).join(' ').toLowerCase();
 const hits = tokens.filter(t => rowStr.includes(t));
 if (hits.length >= 1) matches.push({ section: src.label, program: row[1], status: row[2], timing: row[3] || '', hits });
 });
 });

 if (matches.length === 0) {
 resultsEl.innerHTML = '<span style="color:#2a7a47;font-weight:700">✓ No existing rows matched.</span> This may be a new program not yet in the dashboard — consider adding it manually.';
 } else {
 const deduped = matches.filter((m, i, arr) => arr.findIndex(x => x.program === m.program) === i);
 resultsEl.innerHTML =
 `<div style="font-weight:700;color:#1a2f50;margin-bottom:8px">Found <span style="color:#c45b11">${deduped.length}</span> row(s) that may need verification:</div>` +
 deduped.map(m =>
 `<div style="padding:6px 10px;margin-bottom:5px;background:#fff8e6;border-left:3px solid #e8a020;border-radius:4px">
 <div style="font-weight:700;font-size:11px;color:#1a2f50">${m.program}</div>
 <div style="font-size:10px;color:#5a7a9e;margin-top:2px">${m.section} · Current stage: <strong>${m.status}</strong>${m.timing ? ' · ' + m.timing : ''}</div>
 <div style="font-size:10px;color:#8a9bb0;margin-top:2px">Matched on: ${m.hits.slice(0,5).join(', ')}</div>
 </div>`
 ).join('');
 }
}

// ── READOUT NOTE TOGGLE ───────────────────────────────────────
function toggleNote(panelId, text, btn) {
 const panel = document.getElementById('note-panel-' + panelId);
 const body = document.getElementById('note-panel-body-' + panelId);

 // Toggle off if same button clicked again
 if (btn.classList.contains('note-active')) {
 btn.classList.remove('note-active');
 panel.style.display = 'none';
 return;
 }

 // Deactivate all other note buttons and hide all panels
 document.querySelectorAll('.note-btn').forEach(b => b.classList.remove('note-active'));
 document.querySelectorAll('.note-panel').forEach(p => { p.style.display = 'none'; });

 btn.classList.add('note-active');
 body.textContent = text;

 // Fixed position: pin to viewport right below the clicked button row
 const r = btn.getBoundingClientRect();
 panel.style.top = (r.bottom + 6) + 'px';
 panel.style.display = 'block';
}

// ── GLOBAL SEARCH — SUPABASE LAYER ───────────────────────────────
const _AREA_LABEL_GS = { tl1a:'TL1A', tslp:'TSLP', il4ra:'IL-4Rα', igf1r:'IGF1R', fcrn:'FcRn', tcell:'T-Cell' };
const _TYPE_COLOR_GS = { news:'#3b82f6', data:'#10b981', deal:'#f59e0b', regulatory:'#8b5cf6', conference:'#ec4899', other:'#6b7280' };
let _gsDebounce = null;

function _gsLikeEsc(s) { return s.replace(/[%_\\]/g, c => '\\' + c); }

// ── Area → tab mapping for deep-link navigation ──────────────────
const _GS_AREA_TO_TAB = {
 'tl1a':'tl1a','tslp':'tslp','il4ra':'il4ra-tslp','igf1r':'igf1r-tshr','fcrn':'fcrn','tcell':'ace'
};
const _GS_TAB_LABEL = {
 'tl1a':'TL1A','tslp':'TSLP','il4ra-tslp':'IL-4Rα','il4ra-ox40l':'IL-4Rα','igf1r-tshr':'IGF-1R',
 'fcrn':'FcRn','ace':'T-Cell','industry-insights':'Intel Hub','home':'Home'
};
function _gsNavigate(areaId, type, sourceUrl) {
 // Close panel
 const panel = document.getElementById('gs-sb-panel');
 if (panel) panel.style.display = 'none';
 // Resolve tab
 const tabId = _GS_AREA_TO_TAB[areaId] || 'industry-insights';
 const btn = document.querySelector(`.tab-btn[onclick*="'${tabId}'"],[data-tab="${tabId}"]`)
           || Array.from(document.querySelectorAll('.tab-btn')).find(b => b.getAttribute('onclick') && b.getAttribute('onclick').includes(tabId));
 if (typeof switchTab === 'function') switchTab(tabId, btn);
 // After tab switch, open relevant modal
 setTimeout(() => {
  if (type === 'deal') {
   if (tabId === 'tl1a') { openTl1aModal('tl1a-modal-bd-activity'); }
   else if (tabId !== 'industry-insights') { openDrugModal(tabId + '-modal-bd'); }
  } else if (type === 'intel') {
   if (tabId === 'tl1a') { openTl1aModal('tl1a-modal-intel'); }
   else if (tabId !== 'industry-insights') { openDrugModal(tabId + '-modal-intel'); }
  } else if (type === 'catalyst') {
   if (tabId === 'home') { const el = document.querySelector('.catalyst-section,.cat-section,#home-catalysts'); if (el) el.scrollIntoView({behavior:'smooth',block:'start'}); }
  }
 }, 120);
}

async function _gsSbSearch(term) {
 const panel = document.getElementById('gs-sb-panel');
 if (!panel) return;
 if (!term || term.length < 2) { panel.style.display = 'none'; return; }
 const esc = _gsLikeEsc(term);
 panel.innerHTML = '<div class="gs-sb-empty">Searching…</div>';
 panel.style.display = 'block';
 try {
  const [coRes, drugRes, intelRes, dealsRes, catsRes] = await Promise.all([
   _sb.from('companies')
    .select('id,name,ticker,company_type,geography,status')
    .neq('status','acquired')
    .or(`name.ilike.%${esc}%,ticker.ilike.%${esc}%`)
    .order('name', { ascending: true }).limit(6),
   _sb.from('drugs')
    .select('id,name,display_name,stage,mechanism,company_id')
    .or(`name.ilike.%${esc}%,display_name.ilike.%${esc}%,mechanism.ilike.%${esc}%`)
    .order('name', { ascending: true }).limit(5),
   _sb.from('intel')
    .select('id,intel_date,headline,intel_type,importance,source_url,intel_areas(area_id,target_id)')
    .or(`headline.ilike.%${esc}%,body.ilike.%${esc}%`)
    .order('intel_date', { ascending: false }).limit(5),
   _sb.from('deals')
    .select('id,deal_date,headline,from_company,to_company,area_id,deal_type,total_usd_m,source_url')
    .or(`headline.ilike.%${esc}%,detail.ilike.%${esc}%,from_company.ilike.%${esc}%,to_company.ilike.%${esc}%`)
    .order('deal_date', { ascending: false }).limit(4),
   _sb.from('catalysts')
    .select('id,catalyst_date,label,company_id,area_id,significance')
    .eq('resolved', false)
    .or(`label.ilike.%${esc}%,notes.ilike.%${esc}%`)
    .order('sort_date', { ascending: true }).limit(4)
  ]);
  const cos   = coRes.data   || [];
  const drugs = drugRes.data || [];
  const intel = intelRes.data || [];
  const deals = dealsRes.data || [];
  const cats  = catsRes.data  || [];
  if (!cos.length && !drugs.length && !intel.length && !deals.length && !cats.length) {
   panel.innerHTML = '<div class="gs-sb-empty">No results for "<em>' + term.replace(/</g,'&lt;') + '</em>"</div>';
   return;
  }
  const re = new RegExp(term.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'), 'gi');
  function hl(s) { return (s||'').replace(/</g,'&lt;').replace(re, m => '<mark class="gs-hl">'+m+'</mark>'); }
  let html = '';

  // ── Companies ────────────────────────────────────────────────────
  if (cos.length) {
   html += '<div class="gs-sb-section-hd">Companies (' + cos.length + ')</div>';
   cos.forEach(co => {
    const typeTag = co.company_type ? `<span class="gs-sb-badge" style="background:rgba(255,255,255,0.1);color:rgba(255,255,255,0.7)">${co.company_type}</span>` : '';
    const geoTag  = co.geography    ? `<span>${co.geography}</span>` : '';
    const ticker  = co.ticker       ? ` <span style="font-size:10px;color:rgba(255,255,255,0.45);font-family:monospace">${co.ticker}</span>` : '';
    html += `<div class="gs-sb-item gs-nav-item" data-gtype="company" data-company-id="${co.id}" data-company-name="${(co.name||'').replace(/"/g,'&quot;')}" style="cursor:pointer">`
     + `<div class="gs-sb-headline">🏢 ${hl(co.name)}${ticker}</div>`
     + `<div class="gs-sb-meta">${typeTag}${geoTag}</div></div>`;
   });
  }

  // ── Drugs ─────────────────────────────────────────────────────────
  if (drugs.length) {
   html += '<div class="gs-sb-section-hd">Drugs (' + drugs.length + ')</div>';
   drugs.forEach(d => {
    const label    = d.display_name || d.name || '';
    const mechTag  = d.mechanism ? `<span class="gs-sb-badge" style="background:rgba(255,255,255,0.1);color:rgba(255,255,255,0.7)">${d.mechanism.slice(0,50)}</span>` : '';
    const stageTag = d.stage ? `<span class="gs-sb-badge" style="background:rgba(46,111,176,0.35);color:#7cb9ff">${d.stage}</span>` : '';
    html += `<div class="gs-sb-item gs-nav-item" data-gtype="drug" data-drug-id="${d.id}" data-drug-name="${label.replace(/"/g,'&quot;')}" style="cursor:pointer">`
     + `<div class="gs-sb-headline">💊 ${hl(label)}${d.name !== label ? '<span style="font-size:10px;opacity:0.55;margin-left:5px">'+hl(d.name)+'</span>' : ''}</div>`
     + `<div class="gs-sb-meta">${stageTag}${mechTag}</div></div>`;
   });
  }
  if (intel.length) {
   html += '<div class="gs-sb-section-hd">Intel (' + intel.length + ')</div>';
   intel.forEach(item => {
    const areas = (item.intel_areas||[]).map(a => _AREA_LABEL_GS[a.area_id]||a.area_id).join(', ');
    const tc = _TYPE_COLOR_GS[item.intel_type] || _TYPE_COLOR_GS.other;
    const click = item.source_url ? ' onclick="window.open(this.dataset.url,\'_blank\')" data-url="' + item.source_url.replace(/"/g,'&quot;') + '"' : '';
    const areaIds = (item.intel_areas||[]).map(a => a.area_id);
    const tabId = _GS_AREA_TO_TAB[areaIds[0]] || 'industry-insights';
    const tabLbl = _GS_TAB_LABEL[tabId] || tabId;
    const srcBtn = item.source_url ? '<a onclick="event.stopPropagation()" href="'+item.source_url.replace(/"/g,'&quot;')+'" target="_blank" rel="noopener" class="gs-sb-src">↗</a>' : '';
    html += '<div class="gs-sb-item gs-nav-item" data-area="'+(areaIds[0]||'')+'" data-gtype="intel" style="cursor:pointer">'
     + '<div class="gs-sb-headline">' + hl(item.headline) + srcBtn + '</div>'
     + '<div class="gs-sb-meta">'
     + '<span class="gs-sb-badge" style="background:'+tc+'28;color:'+tc+'">'+(item.intel_type||'news')+'</span>'
     + (areas ? '<span class="gs-sb-badge" style="background:rgba(255,255,255,0.1);color:rgba(255,255,255,0.7)">'+areas+'</span>' : '')
     + '<span>'+(item.intel_date||'')+'</span>'
     + '<span class="gs-sb-nav-pill">→ '+tabLbl+'</span>'
     + '</div></div>';
   });
  }
  if (deals.length) {
   html += '<div class="gs-sb-section-hd">Deals (' + deals.length + ')</div>';
   deals.forEach(d => {
    const aLabel = _AREA_LABEL_GS[d.area_id] || d.area_id || '';
    const val = d.total_usd_m ? ' · $' + d.total_usd_m + 'M' : '';
    const click = d.source_url ? ' onclick="window.open(this.dataset.url,\'_blank\')" data-url="' + d.source_url.replace(/"/g,'&quot;') + '"' : '';
    const dTabId = _GS_AREA_TO_TAB[d.area_id] || 'industry-insights';
    const dTabLbl = _GS_TAB_LABEL[dTabId] || dTabId;
    const dSrcBtn = d.source_url ? '<a onclick="event.stopPropagation()" href="'+d.source_url.replace(/"/g,'&quot;')+'" target="_blank" rel="noopener" class="gs-sb-src">↗</a>' : '';
    html += '<div class="gs-sb-item gs-nav-item" data-area="'+(d.area_id||'')+'" data-gtype="deal" style="cursor:pointer">'
     + '<div class="gs-sb-headline">' + hl(d.headline) + dSrcBtn + '</div>'
     + '<div class="gs-sb-meta">'
     + '<span class="gs-sb-badge" style="background:#f59e0b28;color:#f59e0b">deal</span>'
     + (aLabel ? '<span class="gs-sb-badge" style="background:rgba(255,255,255,0.1);color:rgba(255,255,255,0.7)">'+aLabel+'</span>' : '')
     + '<span>'+(d.from_company||'')+(d.to_company?' → '+d.to_company:'')+val+'</span>'
     + '<span class="gs-sb-nav-pill">→ '+dTabLbl+'</span>'
     + '</div></div>';
   });
  }
  if (cats.length) {
   html += '<div class="gs-sb-section-hd">Catalysts (' + cats.length + ')</div>';
   cats.forEach(c => {
    const aLabel = _AREA_LABEL_GS[c.area_id] || c.area_id || '';
    const sc = c.significance === 'high' ? '#ef4444' : c.significance === 'medium' ? '#f59e0b' : '#6b7280';
    const cTabId = _GS_AREA_TO_TAB[c.area_id] || 'home';
    const cTabLbl = _GS_TAB_LABEL[cTabId] || cTabId;
    html += '<div class="gs-sb-item gs-nav-item" data-area="'+(c.area_id||'')+'" data-gtype="catalyst" style="cursor:pointer">'
     + '<div class="gs-sb-headline">' + hl(c.label) + '</div>'
     + '<div class="gs-sb-meta">'
     + '<span class="gs-sb-badge" style="background:'+sc+'28;color:'+sc+'">'+(c.significance||'')+'</span>'
     + (aLabel ? '<span class="gs-sb-badge" style="background:rgba(255,255,255,0.1);color:rgba(255,255,255,0.7)">'+aLabel+'</span>' : '')
     + '<span>'+(c.catalyst_date||'')+'</span>'
     + '<span class="gs-sb-nav-pill">→ '+cTabLbl+'</span>'
     + '</div></div>';
   });
  }
  panel.innerHTML = html;
 } catch(e) {
  panel.innerHTML = '<div class="gs-sb-empty">Search error: ' + e.message + '</div>';
 }
}

// Close Supabase panel when clicking outside the search wrap
document.addEventListener('click', function(e) {
 const wrap = document.querySelector('.header-search-wrap');
 const panel = document.getElementById('gs-sb-panel');
 // Delegated navigation click on search results
 const navItem = e.target.closest('.gs-nav-item');
 if (navItem && wrap && wrap.contains(navItem)) {
   if (e.target.closest('.gs-sb-src')) return; // let source link handle itself
   const gtype = navItem.dataset.gtype || 'intel';
   if (gtype === 'company') {
     // Open company slide-over directly
     const coId   = navItem.dataset.companyId   || '';
     const coName = navItem.dataset.companyName || '';
     const panel  = document.getElementById('gs-sb-panel');
     if (panel) panel.style.display = 'none';
     const activeTabId = document.querySelector('.tab-pane.active')?.id?.replace(/^tab-/,'') || 'home';
     if (typeof openCompanyEntityModal === 'function') openCompanyEntityModal(coId, coName, activeTabId);
     return;
   }
   if (gtype === 'drug') {
     // Open drug entity modal
     const drugId   = navItem.dataset.drugId   || '';
     const drugName = navItem.dataset.drugName || '';
     const sbPanel  = document.getElementById('gs-sb-panel');
     if (sbPanel) sbPanel.style.display = 'none';
     if (typeof openDrugEntityModal === 'function') openDrugEntityModal(drugId, drugName, null);
     return;
   }
   const area = navItem.dataset.area || '';
   _gsNavigate(area, gtype);
   return;
 }
 if (panel && wrap && !wrap.contains(e.target)) panel.style.display = 'none';
});

// ── GLOBAL SEARCH ────────────────────────────────────────────────
function globalSearch(term) {
 const t = term.toLowerCase().trim();
 const d = window._dashData;
 const clearBtn = document.getElementById('gs-clear');
 const countEl = document.getElementById('gs-count');
 if (clearBtn) clearBtn.style.display = t ? 'inline' : 'none';

 // Debounced Supabase search
 clearTimeout(_gsDebounce);
 if (t.length >= 2) {
  _gsDebounce = setTimeout(() => _gsSbSearch(t), 280);
 } else {
  const panel = document.getElementById('gs-sb-panel');
  if (panel) panel.style.display = 'none';
 }

 function filt(arr) {
 if (!t || !arr) return arr || [];
 return arr.filter(row => row.some(cell => String(cell).toLowerCase().includes(t)));
 }
 function matches(el) { return el.textContent.toLowerCase().includes(t); }
 function vis(el, show) { el.style.display = show ? '' : 'none'; }

 // ── Grids: filter rows ──────────────────────────────────────────
 // try/catch: Grid.js throws "Container is empty" if a grid hasn't rendered yet
 // (e.g. searching from Home before visiting a molecule tab) — must not break search.
 try {
 if (grids.tl1aReadouts) grids.tl1aReadouts.updateConfig({ data: filt(d && d.tl1aReadouts) }).forceRender();
 if (grids.tl1aPipe) grids.tl1aPipe.updateConfig( { data: filt(d && d.tl1aPipe) }).forceRender();
 if (grids.tl1aMono) grids.tl1aMono.updateConfig( { data: filt(d && d.tl1aMono) }).forceRender();
 if (grids.tl1aTech) grids.tl1aTech.updateConfig( { data: filt(d && d.tl1aTech) }).forceRender();
 if (grids.tslpReadouts) grids.tslpReadouts.updateConfig( { data: filt(d && d.tslpReadouts) }).forceRender();
 if (grids.tslpPipe) grids.tslpPipe.updateConfig( { data: filt(d && d.tslpPipe) }).forceRender();
 if (grids.tslpMono) grids.tslpMono.updateConfig( { data: filt(d && d.tslpMono) }).forceRender();
 } catch(e) { console.warn('[search] grid filter skipped:', e.message); }

 // ── All content blocks: hide everything that doesn't match ──────
 // Grid wrapper cards (the chart-collapse / info-card wrapping each grid)
 const BLOCK_SELS = [
 '.intel-card', '.info-card', '.chart-collapse', '.estimand-card',
 '.comp-section', '.ailux-card', '.china-grid', '.two-col',
 '.stat-row', '.meridian-reader', '.home-card', '.home-nav',
 '.stock-card', '.predict-card', '.edu-section'
 ];
 BLOCK_SELS.forEach(sel => {
 document.querySelectorAll(sel).forEach(el => vis(el, !t || matches(el)));
 });

 // Intel items — individual row filtering within the card
 document.querySelectorAll('.intel-item').forEach(el => {
 vis(el, !t || matches(el));
 });

 // China cards — individual
 document.querySelectorAll('.china-card').forEach(el => {
 vis(el, !t || matches(el));
 });

 // Edu chapters inside edu-sections
 document.querySelectorAll('.edu-chapter').forEach(ch => {
 vis(ch, !t || matches(ch));
 });

 // If search active, auto-expand edu sections that have matching chapters
 document.querySelectorAll('.edu-section').forEach(sec => {
 if (!t) return;
 const anyChapter = Array.from(sec.querySelectorAll('.edu-chapter'))
 .some(ch => ch.style.display !== 'none');
 if (anyChapter) sec.querySelector('.edu-body')?.classList.add('open');
 });

 // Close note panels
 document.querySelectorAll('.note-panel').forEach(p => { p.style.display = 'none'; });
 document.querySelectorAll('.note-btn').forEach(b => b.classList.remove('note-active'));

 // ── Result count ────────────────────────────────────────────────
 if (countEl) {
 if (!t) { countEl.style.display = 'none'; }
 else {
 let total = 0;
 ['tl1aReadouts','tl1aPipe','tl1aMono','tl1aTech','tslpReadouts','tslpPipe','tslpMono'].forEach(k => {
 if (d && d[k]) total += filt(d[k]).length;
 });
 ['.intel-item','.china-card','.stock-card','.edu-chapter','.predict-rule'].forEach(sel => {
 document.querySelectorAll(sel).forEach(el => { if (el.style.display !== 'none') total++; });
 });
 countEl.textContent = total + ' match' + (total !== 1 ? 'es' : '');
 countEl.style.display = 'inline';
 }
 }

 // ── Text highlight ───────────────────────────────────────────────
 // Remove previous highlights
 document.querySelectorAll('mark.search-hl').forEach(function(m) {
 var p = m.parentNode; if (!p) return;
 p.replaceChild(document.createTextNode(m.textContent), m);
 p.normalize();
 });
 if (t && t.length >= 2) {
 var re = new RegExp(t.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'), 'gi');
 function hlNode(node) {
 if (node.nodeType === 3) {
 var txt = node.textContent;
 if (!re.test(txt)) { re.lastIndex = 0; return; }
 re.lastIndex = 0;
 var frag = document.createDocumentFragment();
 var last = 0, m;
 while ((m = re.exec(txt)) !== null) {
 if (m.index > last) frag.appendChild(document.createTextNode(txt.slice(last, m.index)));
 var mk = document.createElement('mark');
 mk.className = 'search-hl';
 mk.textContent = m[0];
 frag.appendChild(mk);
 last = m.index + m[0].length;
 }
 if (last < txt.length) frag.appendChild(document.createTextNode(txt.slice(last)));
 node.parentNode.replaceChild(frag, node);
 } else if (node.nodeType === 1) {
 var tag = node.tagName;
 if (['SCRIPT','STYLE','MARK','INPUT','TEXTAREA','SELECT','BUTTON'].indexOf(tag) !== -1) return;
 if (node.style && node.style.display === 'none') return;
 Array.from(node.childNodes).forEach(hlNode);
 }
 }
 var activePane = document.querySelector('.tab-pane.active');
 if (activePane) hlNode(activePane);
 var first = activePane && activePane.querySelector('mark.search-hl');
 if (first) first.scrollIntoView({behavior:'smooth', block:'center'});
 }
}

function clearGlobalSearch() {
 const inp = document.getElementById('global-search');
 if (inp) inp.value = '';
 clearTimeout(_gsDebounce);
 const panel = document.getElementById('gs-sb-panel');
 if (panel) panel.style.display = 'none';
 globalSearch('');
}

// ── ASSET PROFILE MODAL ──────────────────────────────────────────
function openAssetModal(slug) {
 const d = window._dashData;
 if (!d || !d.assetProfiles) return;
 const p = d.assetProfiles[slug];
 if (!p) return;

 // Populate header
 document.getElementById('am-name').textContent = p.name + (p.aliases && p.aliases.length ? ' (' + p.aliases.slice(0,2).join(' / ') + ')' : '');
 document.getElementById('am-meta').innerHTML = `${p.company} &nbsp;·&nbsp; ${p.target} &nbsp;·&nbsp; ${p.indications.join(' / ')}`;
 const stageEl = document.getElementById('am-stage');
 stageEl.textContent = p.stage;
 stageEl.className = 'asset-modal-stage ' + (p.stage.includes('Approved') ? 'sb sb-approved' : p.stage.includes('Phase 3') || p.stage.includes('Ph3') ? 'sb sb-ph3' : p.stage.includes('Phase 2') || p.stage.includes('Ph2') ? 'sb sb-ph2' : 'sb sb-ph1');

 // Overview tab
 document.getElementById('amp-overview').innerHTML = `
 <div class="modal-highlight">${p.headline}</div>
 <div class="modal-section-title">Format &amp; Target</div>
 <div class="modal-prose"><strong>${p.format}</strong> · Target: ${p.target}</div>
 <div class="modal-section-title">Mechanism</div>
 <div class="modal-prose">${p.mechanism_short}</div>
 ${p.companion_dx ? `<div class="modal-section-title">Companion Diagnostic</div><div class="modal-prose">${p.companion_dx}</div>` : ''}
 `;

 // Science tab
 document.getElementById('amp-science').innerHTML = `
 <div class="modal-section-title">Mechanism of Action — Full Detail</div>
 <div class="modal-prose">${p.mechanism_detail}</div>
 ${p.companion_dx ? `<div class="modal-section-title">Biomarker Strategy</div><div class="modal-highlight">${p.companion_dx}</div>` : ''}
 ${p.educational_links && p.educational_links.length ? `
 <div class="modal-section-title">Key Scientific References</div>
 ${p.educational_links.map(l => `<a class="edu-link" href="${l.url}" target="_blank" rel="noopener">${l.title}</a>`).join('')}
 ` : ''}
 `;

 // Clinical tab
 const clinHtml = (p.clinical_summary||[]).map(t => `
 <div class="modal-trial">
 <div class="modal-trial-name">${t.trial}</div>
 <div class="modal-trial-result">${t.result}</div>
 <div class="modal-trial-date">${t.timing}</div>
 </div>
 `).join('');
 document.getElementById('amp-clinical').innerHTML = `
 <div class="modal-section-title">Trial Summary</div>
 ${clinHtml || '<p style="color:#8a9bb0;font-size:13px">No clinical data on record yet.</p>'}
 `;

 // Documents tab
 const docs = d.assetDocs && d.assetDocs[slug] || [];
 const docTypeIcon = {publication:'[Paper]', conference_presentation:'[Deck]', trial_registry:'[Trial]', press_release:'[Press]', poster:'', other:'[File]'};
 const docHtml = docs.map(doc => `
 <div class="doc-card">
 <div class="doc-icon">${docTypeIcon[doc.type]||'[File]'}</div>
 <div class="doc-info">
 <div class="doc-title">${doc.title}</div>
 <div class="doc-meta">${doc.conference}${doc.date ? ' · ' + doc.date : ''}</div>
 ${doc.description ? `<div class="doc-desc">${doc.description}</div>` : ''}
 ${doc.url ? `<a class="doc-link" href="${doc.url}" target="_blank" rel="noopener">View source ↗</a>` : ''}
 </div>
 </div>
 `).join('');
 document.getElementById('amp-documents').innerHTML = `
 <div class="modal-section-title">Conference Posters &amp; Publications</div>
 ${docHtml || '<p style="color:#8a9bb0;font-size:13px">No documents on file yet.</p>'}
 <div style="margin-top:14px">
 <button class="add-doc-btn" onclick="toggleAddDocForm('${slug}')">+ Add Document or Link</button>
 <div class="add-doc-form" id="add-doc-form-${slug}">
 <div style="font-size:12px;font-weight:700;color:#5a7a9e;margin-bottom:10px">Add a document, poster, or external link to this asset's profile:</div>
 <input type="text" id="doc-title-${slug}" placeholder="Title (e.g. NAVIGATOR Ph3 Poster — DDW 2024)">
 <select id="doc-type-${slug}">
 <option value="publication">Publication / Paper</option>
 <option value="conference_presentation">Conference Presentation</option>
 <option value="poster"> Conference Poster</option>
 <option value="trial_registry">Trial Registry</option>
 <option value="press_release">Press Release</option>
 </select>
 <input type="text" id="doc-conf-${slug}" placeholder="Conference / Source (e.g. DDW 2025)">
 <input type="text" id="doc-url-${slug}" placeholder="URL (paste link to the document or source)">
 <textarea id="doc-desc-${slug}" rows="2" placeholder="Brief description (optional)"></textarea>
 <button class="add-doc-save" onclick="saveAssetDoc('${slug}')">Save</button>
 </div>
 </div>
 `;

 // BD Lens tab
 const qHtml = (p.key_questions||[]).map(q => `<div class="modal-question">${q}</div>`).join('');
 document.getElementById('amp-bd').innerHTML = `
 <div class="modal-section-title">Deal &amp; Partnership Context</div>
 <div class="modal-prose">${p.deal_context}</div>
 <div class="modal-section-title">BD Evaluation Lens</div>
 <div class="modal-highlight">${p.bd_lens}</div>
 ${qHtml ? `<div class="modal-section-title">Key Questions for BD Evaluation</div>${qHtml}` : ''}
 `;

 // Reset to overview tab
 switchModalTab('overview', document.querySelector('.asset-modal-tab'));
 document.getElementById('asset-overlay').classList.add('open');
 document.body.style.overflow = 'hidden';
}

function closeAssetModal(e) {
 if (e && e.target !== document.getElementById('asset-overlay')) return;
 document.getElementById('asset-overlay').classList.remove('open');
 document.body.style.overflow = '';
}

function switchModalTab(id, btn) {
 document.querySelectorAll('.asset-modal-pane').forEach(p => p.classList.remove('active'));
 document.querySelectorAll('.asset-modal-tab').forEach(b => b.classList.remove('active'));
 document.getElementById('amp-' + id).classList.add('active');
 if (btn) btn.classList.add('active');
}

function toggleAddDocForm(slug) {
 const f = document.getElementById('add-doc-form-' + slug);
 if (f) f.classList.toggle('open');
}

function saveAssetDoc(slug) {
 const title = document.getElementById('doc-title-'+slug)?.value?.trim();
 const url = document.getElementById('doc-url-'+slug)?.value?.trim();
 const type = document.getElementById('doc-type-'+slug)?.value;
 const conf = document.getElementById('doc-conf-'+slug)?.value?.trim();
 const desc = document.getElementById('doc-desc-'+slug)?.value?.trim();
 if (!title) { alert('Please enter a title.'); return; }
 // Store in session memory (page refresh will reset — for persistence, deploy to JSON)
 const d = window._dashData;
 if (!d.assetDocs) d.assetDocs = {};
 if (!d.assetDocs[slug]) d.assetDocs[slug] = [];
 d.assetDocs[slug].unshift({ id:'u'+Date.now(), title, type, conference: conf||'', date: new Date().toISOString().slice(0,7), url: url||'', description: desc||'', uploaded: false });
 // Re-open modal to refresh documents tab
 openAssetModal(slug);
 switchModalTab('documents', null);
 document.querySelector('.asset-modal-tab:nth-child(4)').classList.add('active');
}

// Make asset name clickable from grid
function assetLinkHtml(name, slug) {
 if (!slug) return name;
 return `<span class="asset-link" onclick="openAssetModal('${slug}')">${name}</span>`;
}

window.addEventListener('load', () => {
 // Set dynamic date
 const now = new Date();
 const dayNames = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
 const monthNames = ['January','February','March','April','May','June','July','August','September','October','November','December'];
 const dateStr = `${dayNames[now.getDay()]}, ${monthNames[now.getMonth()]} ${now.getDate()}, ${now.getFullYear()}`;
 const shortDate = `${monthNames[now.getMonth()]} ${now.getDate()}, ${now.getFullYear()}`;
 const el = document.getElementById('home-date');
 if (el) el.textContent = dateStr;
 const hd = document.getElementById('header-date');
 if (hd) hd.textContent = dateStr;
 // Live world clocks — tick every second
 function _tickClocks() {
  const fmt = (tz) => new Date().toLocaleTimeString('en-US', {timeZone: tz, hour: 'numeric', minute: '2-digit', hour12: true});
  const et = document.getElementById('hclock-et'); if (et) et.textContent = fmt('America/New_York');
  const pt = document.getElementById('hclock-pt'); if (pt) pt.textContent = fmt('America/Los_Angeles');
  const cn = document.getElementById('hclock-cn'); if (cn) cn.textContent = fmt('Asia/Shanghai');
 }
 _tickClocks();
 setInterval(_tickClocks, 1000);
 // ── Generic-link → specific Google search converter ────────────────
 // Any link whose href is a bare homepage or generic index page gets replaced
 // with a Google search for the link's visible text, so every click yields
 // a result about the specific topic — not a generic company front page.
 function _isGenericHref(href) {
   if (!href || !href.startsWith('http')) return false;
   try {
     const url = new URL(href);
     // Never rewrite Google, CDN, or font resources
     if (/google\.com|cdn\.|cdnjs\.|jsdelivr|fonts\.googleapis/.test(url.hostname)) return false;
     const p = url.pathname;
     // Bare domain (no path, or just "/")
     if (!p || p === '/') return true;
     // Path exists: generic only if every segment is a short locale/section word
     const genericSeg = /^(en|zh|us|cn|global|news|media|press|press-releases|news-releases|en-us|zh-cn|about|ir|investors|investor-relations|resources|insights|blog|events|publications|page|archive|company|home|index)$/i;
     const segs = p.split('/').filter(Boolean);
     return segs.length > 0 && segs.every(s => genericSeg.test(s) || (s.length <= 5 && !s.includes('-')));
   } catch(e) { return false; }
 }
 // Build a Google search URL from any raw link text — uses the shared _buildGQuery cleaner.
 function _gUrlFromText(raw) {
   const q = _buildGQuery(raw || '');
   return 'https://www.google.com/search?q=' + encodeURIComponent(q);
 }
 function _fixGenericLinks(root) {
   // DISABLED 2026-06-08 (Kyle): this used to rewrite "generic-looking" stored source_urls
   // (press-release indexes, company homepages) into a Google search. Kyle wants the direct
   // link we have on file in every case — so we no longer rewrite anything. Kept as a no-op
   // so existing call sites don't break.
   return;
 }
 _fixGenericLinks(); // no-op
 // Observer retained but no longer rewrites hrefs (see above). Left in place harmlessly.
 (new MutationObserver(function(muts) {
   muts.forEach(function(m) {
     m.addedNodes.forEach(function(n) {
       if (n.nodeType !== 1) return;
       // intentionally no href rewriting (Kyle 2026-06-08)
       if (false) {
         _fixGenericLinks(n);
       }
     });
   });
 })).observe(document.body, {childList: true, subtree: true});
 // Build TOC for default Home tab
 buildToc('home');
 // Load data and init grids
 loadData().then(d => { window._dashData = d; initGrids(d); });
});

// ── Nav dropdown — hover open, 1-second grace on mouseleave ───
let _molCloseTimer = null;
(function() {
  const wrap = document.getElementById('mol-dd-wrap');
  const menu = document.getElementById('mol-dd-menu');
  if (!wrap || !menu) return;
  wrap.addEventListener('mouseenter', function() {
    if (_molCloseTimer) { clearTimeout(_molCloseTimer); _molCloseTimer = null; }
    // Close the folder navigator immediately
    if (_hierCloseTimer) { clearTimeout(_hierCloseTimer); _hierCloseTimer = null; }
    document.getElementById('hier-dd-menu')?.classList.remove('open');
    menu.classList.add('open');
  });
  wrap.addEventListener('mouseleave', function() {
    _molCloseTimer = setTimeout(function() {
      menu.classList.remove('open');
      _molCloseTimer = null;
    }, 1000);
  });
})();

// ══════════════════════════════════════════════════════════
//  HIERARCHY / ONTOLOGY DROPDOWN — LIVE SUPABASE (Phase E)
//  Hover-triggered cascading flyout. Data from Supabase.
//  Sub-panels are DOM children of their parent .hier-item so
//  CSS :hover propagates through — no JS hover bridge needed.
//
//  Data sources:
//    therapeutic_areas  — top-level TA nodes (7 rows)
//    indications        — indication nodes with disease_area FK (11 rows)
//    drug_indications   — drug counts per indication (246 rows)
//    drug_targets       — target assignment per drug (250+ rows)
//
//  tabId mapping — therapeutic_areas.id → dashboard tab:
// ══════════════════════════════════════════════════════════

// tabId = existing Meridian dashboard to navTo() on click.
// null  = no dashboard yet; clicking shows a "coming soon" toast.
const _HIER_TA_TAB_MAP = {
  gastroenterology: 'tl1a',       // TL1A × IL-23p19 tab (IBD)
  respiratory:      'tslp',       // TSLP × IL-33 tab
  dermatology:      'il4ra-tslp', // IL-4Rα × TSLP tab (Atopy)
  rheumatology:     null,         // no dashboard yet
  neurology:        'fcrn',       // FcRn Bispecific tab
  ophthalmology:    'igf1r-tshr', // IGF-1R × TSHR tab (TED)
  oncology:         'ace',        // BCMA × CD19 × CD3 tab
  immunology:       null,         // no dashboard yet
};
// Therapeutic area color palette
const _HIER_TA_COLOR_MAP = {
  gastroenterology: '#7c3aed',
  respiratory:      '#0891b2',
  dermatology:      '#c2410c',
  rheumatology:     '#b45309',
  neurology:        '#1d4ed8',
  ophthalmology:    '#0f766e',
  oncology:         '#dc2626',
  immunology:       '#64748b',
};
// indication.id → tabId (per-indication override)
const _HIER_IND_TAB_MAP = {
  uc:          'tl1a',
  cd:          'tl1a',
  asthma:      'tslp',
  copd:        'tslp',
  ad:          'il4ra-tslp',
  csu:         'il4ra-tslp',
  ted:         'igf1r-tshr',
  gmg:         'fcrn',
  cidp:        'fcrn',
  mm:          'ace',
  all:         'ace',
};
// drug_targets.target_id → tabId
const _HIER_TGT_TAB_MAP = {
  tl1a:    'tl1a',
  il23p19: 'tl1a',
  il4ra:   'il4ra-tslp',
  tslp:    'tslp',
  tslpr:   'tslp',
  fcrn:    'fcrn',
  igf1r:   'igf1r-tshr',
  tshr:    'igf1r-tshr',
  bcma:    'ace',
  cd19:    'ace',
  cd3:     'ace',
};
// Map target_id slug to display symbol
const _HIER_TGT_SYMBOL = {
  tl1a:    'TL1A',
  il23p19: 'IL-23p19',
  il4ra:   'IL-4Rα',
  tslp:    'TSLP',
  tslpr:   'TSLP-R',
  fcrn:    'FcRn',
  igf1r:   'IGF-1R',
  tshr:    'TSHR',
  bcma:    'BCMA',
  cd19:    'CD19',
  cd3:     'CD3',
  a4b7:    'α4β7',
  il13:    'IL-13',
  il33:    'IL-33',
  ige:     'IgE',
  il5ra:   'IL-5Rα',
  cd40:    'CD40',
  il1ab:   'IL-1α/β',
  il6r:    'IL-6R',
  il17a:   'IL-17A',
  tnf:     'TNF',
};

// disease_area string → human-readable DA label (one level below TA)
const _HIER_DA_LABEL = {
  ibd:              'IBD',
  gastroenterology: 'GI / IBD',
  respiratory:      'Airway Diseases',
  atopy:            'Atopic Disease',
  dermatology:      'Skin Diseases',
  ted:              'Thyroid Eye Disease',
  ophthalmology:    'Eye Diseases',
  autoimmune:       'Autoimmune',
  rheumatology:     'Musculoskeletal',
  neurology:        'Neuromuscular',
  hematology:       'Hematology',
  oncology:         'Oncology',
};

// indications.disease_area (legacy string) → therapeutic_areas.id
// Also used as per-indication-id overrides (checked first in lookup below)
const _HIER_LEGACY_TO_TA = {
  // disease_area values that match TA ids directly
  gastroenterology: 'gastroenterology',
  respiratory:      'respiratory',
  dermatology:      'dermatology',
  rheumatology:     'rheumatology',
  neurology:        'neurology',
  ophthalmology:    'ophthalmology',
  oncology:         'oncology',
  // legacy disease_area aliases
  ibd:              'gastroenterology',
  atopy:            'dermatology',
  ted:              'ophthalmology',
  autoimmune:       'rheumatology',
  hematology:       'neurology',   // waiha → FcRn/neurology umbrella
  // per-indication-id overrides (these take precedence — lookup checks ind.id first)
  gmg:                'neurology',
  cidp:               'neurology',
  nmosd:              'neurology',
  waiha:              'neurology',
  mm:                 'oncology',
  all:                'oncology',
  // DB indication IDs that differ from short aliases in _HIER_IND_TAB_MAP
  multiple_myeloma:   'oncology',
  chronic_urticaria:  'dermatology',
};

let _hierLiveData = null;  // cached tree array; null = not yet loaded
let _hierFetching = false; // guard against parallel fetches

// Navigator lookup — pre-computed target→drug, indication→drug, etc. mappings
// Loaded once alongside the navigator tree; enables O(1) set-based drug filtering.
window._navLookup = null;
(function _loadNavLookup() {
  fetch('./data/navigator_lookup.json?_v=' + Date.now())
    .then(r => r.ok ? r.json() : null)
    .then(data => { if (data) window._navLookup = data; })
    .catch(() => { /* non-fatal: falls back to string-match filter */ });
})();

// ── Async data fetcher — builds the tree from 4 Supabase tables ──
async function _hierFetchLiveData() {
  // _sb is a module-level const — not on window. Use it directly.
  if (typeof _sb === 'undefined') throw new Error('_sb not ready');

  const [r1, r2, r3, r4] = await Promise.all([
    _sb.from('therapeutic_areas').select('id,name,sort_order').eq('status','active').order('sort_order'),
    _sb.from('indications').select('id,name,abbreviation,disease_area').order('name'),
    // drug_indications / drug_targets exceed the 1000-row cap → paginate (was silently truncated)
    _sbFetchAll((f, t) => _sb.from('drug_indications').select('drug_id,indication_id').range(f, t)).then(d => ({ data: d })),
    _sbFetchAll((f, t) => _sb.from('drug_targets').select('drug_id,target_id').range(f, t)).then(d => ({ data: d })),
  ]);

  if (r1.error || r2.error) {
    throw r1.error || r2.error;
  }

  const taRows  = r1.data || [];
  const indRows = r2.data || [];
  const diRows  = r3.data || [];
  const dtRows  = r4.data || [];

  // Build: indication_id → Set<drug_id>
  const indDrugMap = {};
  diRows.forEach(r => {
    if (!indDrugMap[r.indication_id]) indDrugMap[r.indication_id] = new Set();
    indDrugMap[r.indication_id].add(r.drug_id);
  });

  // Build: drug_id → [target_id]
  const drugTargetMap = {};
  dtRows.forEach(r => {
    if (!drugTargetMap[r.drug_id]) drugTargetMap[r.drug_id] = [];
    drugTargetMap[r.drug_id].push(r.target_id);
  });

  // Group indications under their therapeutic area
  const taIndMap = {};
  indRows.forEach(ind => {
    // Check ind.id first (per-indication overrides), then disease_area string
    const taId = _HIER_LEGACY_TO_TA[ind.id] || _HIER_LEGACY_TO_TA[ind.disease_area];
    if (!taId) return;
    if (!taIndMap[taId]) taIndMap[taId] = [];
    taIndMap[taId].push(ind);
  });

  // Build tree: therapeutic_area → [indication nodes] (no intermediate disease-area level)
  const tree = taRows.map(ta => {
    const inds    = taIndMap[ta.id] || [];
    const taTabId = _HIER_TA_TAB_MAP[ta.id] || null;

    // Helper: build one indication node from a raw indication row
    function _mkIndNode(ind) {
      const drugSet  = indDrugMap[ind.id] || new Set();
      const total    = drugSet.size;
      const indTabId = _HIER_IND_TAB_MAP[ind.id] || taTabId;
      const tgtCount = {};
      drugSet.forEach(dId => {
        (drugTargetMap[dId] || []).forEach(tId => {
          tgtCount[tId] = (tgtCount[tId] || 0) + 1;
        });
      });
      const tgts = Object.entries(tgtCount)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 6)
        .map(([tId, n]) => ({
          id:    tId,
          name:  _HIER_TGT_SYMBOL[tId] || tId.toUpperCase().replace(/_/g,'-'),
          n,
          tabId: _HIER_TGT_TAB_MAP[tId] || indTabId,
        }));
      return { id: ind.id, abbr: ind.abbreviation || ind.id.toUpperCase().slice(0,6), name: ind.name, total, tabId: indTabId, tgts };
    }

    // Group raw indications by their disease_area field → DA-level buckets
    const daGroupInds = {};
    inds.forEach(ind => {
      const daKey = ind.disease_area || ta.id;
      if (!daGroupInds[daKey]) daGroupInds[daKey] = [];
      daGroupInds[daKey].push(ind);
    });

    // Count unique drugs across all indications under this TA
    const taDrugSet = new Set();
    inds.forEach(ind => (indDrugMap[ind.id] || new Set()).forEach(id => taDrugSet.add(id)));
    const taTotal = taDrugSet.size;

    // Build one DA node per distinct disease_area bucket, with a readable name
    const daNode = Object.entries(daGroupInds).map(([daKey, daInds]) => {
      const daLabel    = _HIER_DA_LABEL[daKey] || (daKey.charAt(0).toUpperCase() + daKey.slice(1));
      const daIndNodes = daInds.map(_mkIndNode).filter(n => n.total > 0);
      if (!daIndNodes.length) return null;
      const daDrugSet  = new Set();
      daInds.forEach(ind => (indDrugMap[ind.id] || new Set()).forEach(id => daDrugSet.add(id)));
      return {
        id:    ta.id + '-' + daKey,
        name:  daLabel,
        full:  daLabel,
        total: daDrugSet.size,
        tabId: taTabId,
        inds:  daIndNodes,
      };
    }).filter(Boolean).sort((a, b) => b.total - a.total);

    return {
      id:    ta.id,
      name:  ta.name,
      color: _HIER_TA_COLOR_MAP[ta.id] || '#64748b',
      total: taTotal,
      tabId: taTabId,
      das:   daNode,
    };
  }).filter(ta => ta.total > 0 || (taIndMap[ta.id] || []).length > 0);

  return tree;
}

// Track selection (expansion is purely CSS :hover now)
const hierState = {
  sel: null, // { ta, da, ind, tgt } — last clicked target
  built: false,
};

// ── Per-item 1-second grace period for sub-panels ─────────────
// mouseenter: open this sub-panel immediately; close any open siblings immediately
// mouseleave: wait 1 second, then close — mouse can return within that window
function hierAttachHover(item) {
  let timer = null;
  const sub = item.querySelector(':scope > .hier-sub-panel');
  if (!sub) return;

  item._hierForceClose = function() {
    if (timer) { clearTimeout(timer); timer = null; }
    sub.classList.remove('open');
  };

  item.addEventListener('mouseenter', function() {
    if (timer) { clearTimeout(timer); timer = null; }
    // Immediately close any open siblings so only one sub-panel shows at a time
    const parent = item.parentElement;
    if (parent) {
      parent.querySelectorAll(':scope > .hier-item').forEach(function(sib) {
        if (sib !== item && sib._hierForceClose) sib._hierForceClose();
      });
    }
    // Collapse any deeper panels already open within this item (going back a level)
    item.querySelectorAll('.hier-sub-panel.open').forEach(function(s) { s.classList.remove('open'); });
    sub.classList.add('open');
  });

  item.addEventListener('mouseleave', function() {
    timer = setTimeout(function() {
      sub.classList.remove('open');
      timer = null;
    }, 500);
  });
}

// ── Hover open / 1-second grace-period close ──────────────────
let _hierCloseTimer = null;
(function() {
  const wrap = document.getElementById('hier-dd-wrap');
  const menu = document.getElementById('hier-dd-menu');
  if (!wrap || !menu) return;
  wrap.addEventListener('mouseenter', function() {
    if (_hierCloseTimer) { clearTimeout(_hierCloseTimer); _hierCloseTimer = null; }
    // Close the DNA dropdown immediately
    if (_molCloseTimer) { clearTimeout(_molCloseTimer); _molCloseTimer = null; }
    document.getElementById('mol-dd-menu')?.classList.remove('open');
    if (!hierState.built) {
      hierBuildTree().then(() => { hierState.built = true; }).catch(console.error);
    }
    menu.classList.add('open');
  });
  wrap.addEventListener('mouseleave', function() {
    _hierCloseTimer = setTimeout(function() {
      menu.classList.remove('open');
      _hierCloseTimer = null;
    }, 500);
  });
})();

// ── Tree builder — nested DOM, hover handled purely by CSS :hover ──
// No timers. Hit area is enlarged physically: taller rows (11px padding),
// 6px top/bottom buffer inside sub-panels, and sub-panels overlap parent
// by 6px (left: calc(100% - 6px)) so there is never a physical gap.
//
// async: fetches Supabase on first call, caches in _hierLiveData.
// Subsequent calls (e.g. from hierSetSel) render synchronously from cache.
async function hierBuildTree() {
  const body = document.getElementById('hier-dd-body');
  if (!body) return;

  // If cache is empty and a fetch isn't already in progress, load from Supabase
  if (!_hierLiveData && !_hierFetching) {
    _hierFetching = true;
    body.innerHTML = '<div style="padding:14px 16px;font-size:11px;color:#94a3b8">Loading navigator…</div>';
    try {
      _hierLiveData = await _hierFetchLiveData();
    } catch(e) {
      console.error('hierBuildTree: Supabase fetch failed — navigator will be empty. Error:', e);
      _hierLiveData = [];
      body.innerHTML = '<div style="padding:14px 16px;font-size:11px;color:#ef4444">Navigator failed to load. Check console.</div>';
    }
    _hierFetching = false;
  }

  // If still fetching (parallel call), just return — first call will re-render
  if (_hierFetching) return;

  const data = _hierLiveData || [];
  body.innerHTML = '';
  data.forEach((ta, ti) => {
    if (ti > 0) body.appendChild(hierDivider());
    body.appendChild(hierMakeTA(ta));
  });
}

function hierDivider() {
  const d = document.createElement('div');
  d.className = 'hier-divider';
  return d;
}

// ── Navigation helper ──
// Navigates to the dashboard and closes the dropdown.
// If no tabId, shows a "dashboard coming soon" toast instead.
function hierNav(tabId, label) {
  if (tabId) {
    // Immediate close on deliberate selection — no delay
    if (_hierCloseTimer) { clearTimeout(_hierCloseTimer); _hierCloseTimer = null; }
    document.getElementById('hier-dd-menu')?.classList.remove('open');
    navTo(tabId);
    // Override the title bar with the selection breadcrumb path
    const s = hierState.sel;
    if (s) {
      const parts = [s.ta?.name, s.da?.name, s.ind?.name, s.tgt?.name].filter(Boolean);
      const nameEl = document.getElementById('tab-current-name');
      if (nameEl && parts.length) nameEl.textContent = parts.join(' › ');
    }
    // Apply target/indication filter to the PI component for this tab.
    // The component may not be loaded yet if this is the first visit — poll for up to 5s.
    _hierScheduleFilter(tabId, s);
  } else {
    hierShowNoTabToast(label);
  }
}

// Schedules a filter application after a hierarchy selection.
// Polls until the _areaPIs component for the tab is loaded (lazy-load may not be done yet).
function _hierScheduleFilter(tabId, sel) {
  const tgtName = sel?.tgt?.name || null;
  const indName = sel?.ind?.name || null;

  // Update filter chip visibility immediately
  _hierUpdateFilterChip(tgtName, indName);

  // If no actual filter to apply, just clear any existing filter and return
  if (!tgtName && !indName) {
    _areaPIs[tabId]?.applyTargetFilter(null, null);
    return;
  }

  let attempts = 0;
  const MAX = 25; // up to ~5 seconds (25 × 200ms)
  function _tryApply() {
    const pi = _areaPIs[tabId];
    if (pi && pi.loaded) {
      pi.applyTargetFilter(tgtName, indName);
      return;
    }
    if (++attempts < MAX) setTimeout(_tryApply, 200);
  }
  _tryApply();
}

// Shows/hides the filter chip in the title bar.
function _hierUpdateFilterChip(targetName, indicationName) {
  const chip  = document.getElementById('hier-filter-chip');
  const label = document.getElementById('hier-filter-chip-label');
  if (!chip || !label) return;
  if (targetName) {
    label.textContent = targetName + ' only';
    chip.style.display = 'inline-flex';
  } else if (indicationName) {
    label.textContent = indicationName + ' only';
    chip.style.display = 'inline-flex';
  } else {
    chip.style.display = 'none';
  }
}

// Called by the chip × and by hierClearSelection to reset all hier filters.
function applyHierFilterToActivePI(sel) {
  const tgtName = sel?.tgt?.name || null;
  const indName = sel?.ind?.name || null;
  _hierUpdateFilterChip(tgtName, indName);
  // Apply to all loaded PI components (covers the case where we don't know which tab is active)
  Object.values(_areaPIs).forEach(pi => {
    if (typeof pi.applyTargetFilter === 'function') {
      pi.applyTargetFilter(tgtName, indName);
    }
  });
}

// ── Level 1: Therapeutic Area ──
function hierMakeTA(ta) {
  const item = document.createElement('div');
  item.className = 'hier-item';

  const row = document.createElement('div');
  row.className = 'hier-row';
  row.style.cursor = ta.tabId ? 'pointer' : 'default';
  row.innerHTML = `
    <div class="hier-ta-dot" style="background:${ta.color}"></div>
    <div class="hier-row-name hier-ta-name">${ta.name}</div>
    <div class="hier-row-count">${ta.total}</div>
    <div class="hier-row-arrow">▶</div>
  `;
  row.addEventListener('click', (e) => {
    e.stopPropagation();
    hierSetSel({ta});
    hierNav(ta.tabId, ta.name);
  });

  const sub = document.createElement('div');
  sub.className = 'hier-sub-panel';
  ta.das.forEach((da, di) => {
    if (di > 0) sub.appendChild(hierDivider());
    sub.appendChild(hierMakeDA(ta, da));
  });

  item.appendChild(row);
  item.appendChild(sub);
  hierAttachHover(item);
  return item;
}

// ── Level 2: Disease Area ──
function hierMakeDA(ta, da) {
  const item = document.createElement('div');
  item.className = 'hier-item';

  const row = document.createElement('div');
  row.className = 'hier-row';
  row.title = da.full;
  row.style.cursor = da.tabId ? 'pointer' : 'default';
  row.innerHTML = `
    <div class="hier-row-name hier-da-name">${da.name}</div>
    <div class="hier-row-count">${da.total}</div>
    <div class="hier-row-arrow">▶</div>
  `;
  row.addEventListener('click', (e) => {
    e.stopPropagation();
    hierSetSel({ta, da});
    hierNav(da.tabId, da.name);
  });

  const sub = document.createElement('div');
  sub.className = 'hier-sub-panel';
  da.inds.forEach((ind, ii) => {
    if (ii > 0) sub.appendChild(hierDivider());
    sub.appendChild(hierMakeInd(ta, da, ind));
  });

  item.appendChild(row);
  item.appendChild(sub);
  hierAttachHover(item);
  return item;
}

// ── Level 3: Indication ──
function hierMakeInd(ta, da, ind) {
  const item = document.createElement('div');
  item.className = 'hier-item';

  const row = document.createElement('div');
  row.className = 'hier-row';
  row.style.cursor = ind.tabId ? 'pointer' : 'default';
  row.innerHTML = `
    <span class="hier-ind-abbr">${ind.abbr}</span>
    <div class="hier-row-name hier-ind-name">${ind.name}</div>
    <div class="hier-row-count">${ind.total}</div>
    <div class="hier-row-arrow">▶</div>
  `;
  row.addEventListener('click', (e) => {
    e.stopPropagation();
    hierSetSel({ta, da, ind});
    hierNav(ind.tabId, ind.name);
  });

  // Sub-panel: Targets (leaf level)
  const sub = document.createElement('div');
  sub.className = 'hier-sub-panel';

  const hd = document.createElement('div');
  hd.className = 'hier-sub-hd';
  hd.innerHTML = `
    <div class="hier-sub-hd-label">${da.name}</div>
    <div class="hier-sub-hd-name">${ind.name}</div>
  `;
  sub.appendChild(hd);

  ind.tgts.forEach(tgt => {
    const trow = document.createElement('div');
    const isSel = hierState.sel?.tgt?.id === tgt.id && hierState.sel?.ind?.id === ind.id;
    trow.className = 'hier-row hier-tgt-row' + (isSel ? ' selected-tgt' : '');
    trow.style.cursor = tgt.tabId ? 'pointer' : 'not-allowed';
    trow.innerHTML = `
      <div class="hier-tgt-dot"></div>
      <div class="hier-row-name hier-tgt-name">${tgt.name}</div>
      <div class="hier-row-count">${tgt.n}</div>
    `;
    trow.addEventListener('click', (e) => {
      e.stopPropagation();
      hierSetSel({ta, da, ind, tgt});
      hierNav(tgt.tabId, tgt.name);
    });
    sub.appendChild(trow);
  });

  item.appendChild(row);
  item.appendChild(sub);
  hierAttachHover(item);
  return item;
}

// ── Selection tracking ──────────────────────────────────
function hierSetSel(sel) {
  hierState.sel = sel;
  // Rebuild to update selected-tgt highlight, then update footer
  // hierBuildTree is async but renders synchronously from cache after first load
  hierState.built = false;
  hierBuildTree().then(() => { hierState.built = true; hierUpdateFooter(); }).catch(console.error);
}

function hierClearSelection() {
  hierState.sel = null;
  hierState.built = false;
  hierBuildTree().then(() => { hierState.built = true; hierUpdateFooter(); }).catch(console.error);
  // Clear all PI filters and hide the chip
  applyHierFilterToActivePI(null);
}

function hierUpdateFooter() {
  const path  = document.getElementById('hier-footer-path');
  const clear = document.getElementById('hier-footer-clear');
  if (!path) return;
  const s = hierState.sel;
  if (!s || !s.ta) {
    path.textContent = 'Hover to explore · click to select';
    path.className = 'hier-dd-footer-path';
    clear.className = 'hier-dd-footer-clear';
  } else {
    const parts = [s.ta.name];
    if (s.da)  parts.push(s.da.name);
    if (s.ind) parts.push(s.ind.abbr);
    if (s.tgt) parts.push(s.tgt.name);
    path.textContent = parts.join(' › ');
    path.className = 'hier-dd-footer-path has-sel';
    clear.className = 'hier-dd-footer-clear visible';
  }
}

function hierToast(msg, bg) {
  let t = document.getElementById('hier-toast');
  if (!t) {
    t = document.createElement('div');
    t.id = 'hier-toast';
    t.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);padding:9px 18px;border-radius:8px;font-size:12px;font-weight:700;z-index:9999;box-shadow:0 4px 20px rgba(0,0,0,0.3);pointer-events:none;transition:opacity 0.3s;';
    document.body.appendChild(t);
  }
  t.style.background = bg || '#0f1e32';
  t.style.color = 'white';
  t.textContent = msg;
  t.style.opacity = '1';
  clearTimeout(t._timer);
  t._timer = setTimeout(() => { t.style.opacity = '0'; }, 2400);
}
function hierShowSelectionToast(name) {
  hierToast('🎯 ' + name, '#0f1e32');
}
function hierShowNoTabToast(name) {
  hierToast('⏳ No dashboard yet for ' + name, '#475569');
}
// Prefetch hierarchy data so it's ready the first time the menu opens.
// hierBuildTree is async — data loads from Supabase and caches in _hierLiveData.
hierBuildTree().then(() => { hierState.built = true; }).catch(console.error);

function closeCenterDrugDD() {
  const dd = document.getElementById('center-drug-dd');
  const title = document.getElementById('tab-current-title');
  if (dd) dd.classList.remove('open');
  if (title) title.classList.remove('open');
}
function toggleCenterDrugDD(e) {
  const title = document.getElementById('tab-current-title');
  if (!title || !title.classList.contains('is-drug')) return;
  e && e.stopPropagation();
  const dd = document.getElementById('center-drug-dd');
  const isOpen = dd && dd.classList.contains('open');
  closeCenterDrugDD();
  if (!isOpen) {
    if (dd) dd.classList.add('open');
    title.classList.add('open');
  }
}
// Map tabId → nav icon button id
const NAV_ICON_MAP = {
  'home': 'nav-icon-home',
  'industry-insights': 'nav-icon-insights',
  'drugs-know': 'nav-icon-drugs',
  /* DEPRECATED 2026-06-06: 'pharma-intel': 'nav-icon-pharma' (tab retired) */
  'meridian-issue': 'nav-icon-meridian',
  'predictions': 'nav-icon-predictions',
  'reads': 'nav-icon-reads',
  'tl1a': 'mol-dd-btn', 'tslp': 'mol-dd-btn', 'il4ra-tslp': 'mol-dd-btn',
  'il4ra-ox40l': 'mol-dd-btn', 'igf1r-tshr': 'mol-dd-btn',
  'fcrn': 'mol-dd-btn', 'ace': 'mol-dd-btn',
  'homeprev': 'nav-icon-home',  /* 2026-06-19 (rec #9): Home Preview is now the default Home (🏠). */
  /* 2026-06-19 (rec #5): 'live' + 'atlas' consolidated into intel2 sub-views. */
  'intel2': 'nav-icon-intel2',
  /* 2026-06-19 (rec #8): admin/ops cluster lives behind the ⚙ Admin hub — all map to its icon. */
  'admin': 'nav-icon-admin',
  'discovery-queue': 'nav-icon-admin',
  'submitted-intel': 'nav-icon-admin',
  'program-board': 'nav-icon-admin',
  'ontology': 'nav-icon-admin',
  'ontology-explorer': 'nav-icon-admin',
  'audit': 'nav-icon-admin',
  /* DEPRECATED 2026-06-06: 'changes-feed': 'nav-icon-changes' (Activity Feed retired) */
};
function updateNavIconActive(tabId) {
  document.querySelectorAll('.nav-icon-btn').forEach(b => b.classList.remove('active'));
  const iconId = NAV_ICON_MAP[tabId];
  if (iconId) document.getElementById(iconId)?.classList.add('active');
}
function navTo(tabId) {
  const btn = document.querySelector(`.tab-btn[onclick*="'${tabId}'"]`);
  switchTab(tabId, btn);
  document.getElementById('mol-dd-menu')?.classList.remove('open');
  closeCenterDrugDD();
  updateNavIconActive(tabId);
  window.scrollTo({top: 0, behavior: 'smooth'});
  // Lazy-load molecule tab data on first visit
  if (typeof loadMoleculeTab === 'function' && TAB_AREA_MAP && TAB_AREA_MAP[tabId]) {
    loadMoleculeTab(tabId);
  }
}
// Close molecule dropdown and center drug dropdown when clicking outside
document.addEventListener('click', function(e) {
  const wrap = document.getElementById('mol-dd-wrap');
  if (wrap && !wrap.contains(e.target)) {
    document.getElementById('mol-dd-menu')?.classList.remove('open');
  }
  const title = document.getElementById('tab-current-title');
  if (title && !title.contains(e.target)) {
    closeCenterDrugDD();
  }
});

// ── Dynamic tab-bar sticky offset ─────────────────────────────
function fixTabBarTop() {
  const hdr = document.querySelector('.header');
  const tb  = document.querySelector('.tab-bar');
  if (!hdr || !tb) return;
  const hdrH = hdr.getBoundingClientRect().height;
  const tbH  = tb.getBoundingClientRect().height;
  tb.style.top = hdrH + 'px';
  // Pin dkn-master-wrap directly below header+tabbar using fixed positioning
  const wrap = document.querySelector('.dkn-master-wrap');
  if (wrap) wrap.style.top = (hdrH + tbH) + 'px';
  // Pin TL1A side pills just below header+tabbar
  const pillsOffset = hdrH + tbH + 10;
  document.querySelectorAll('.tl1a-pills-col').forEach(p => { p.style.top = pillsOffset + 'px'; });
  // Align all drug-tab dashboards with pill button tops — fixed 10px gap below tab bar
  document.querySelectorAll('.tab-pane .tl1a-layout').forEach(l => {
    l.style.paddingTop = '10px';
  });
}
fixTabBarTop();
window.addEventListener('resize', fixTabBarTop);
