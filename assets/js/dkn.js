// ── DKN state ─────────────────────────────────────────────────────────────────
let _dknData    = null;   // array of drug records from Supabase (null = not yet loaded)
let _dknLoading = false;

let dknSortCol = 'stage'; // default: approved drugs first
let dknSortDir = 1;
let dknCatFilter = '';
let dknStageFilter = '';
let dknClassFilter = '';
let dknIndFilter = '';
let dknRemovedIds = [];
let dknUndoStack = [];
let dknShowRemoved = false;
let dknTargetFilter = '';
let dknCompanyFilter = '';
let dknModalityFilter = '';
let dknStageDropFilter = '';
let dknTaFilter = '';
let dknFmtChipFilter = '';

const STAGE_ORDER = { 'Approved':0, 'Phase 3':1, 'Phase 2':2, 'Phase 1':3, 'Preclinical':4, 'Research':5 };

const DKN_IND_MAP = {
  // Actual indications — matched against indication_short field
  'UC':       ['UC','ulcerative colitis'],
  'CD':       ['CD','crohn'],
  'RA':       ['RA','rheumatoid arthritis'],
  'PsA':      ['PsA','psoriatic arthritis'],
  'SLE':      ['SLE','lupus'],
  'IgG4-RD':  ['IgG4','igg4-rd','igg4-related'],
  'AD':       ['AD','atopic dermatitis','eczema'],
  'Asthma':   ['asthma'],
  'CSU':      ['CSU','urticaria','chronic spontaneous'],
  'PsO':      ['PsO','psoriasis'],
  'TED':      ['TED','thyroid eye'],
  'Graves':   ['Graves','graves'],
  'MG':       ['myasthenia','gmg'],
  'CIDP':     ['CIDP'],
  'PV':       ['pemphigus','PV'],
  'ITP':      ['ITP','thrombocytopenia'],
  'AIHA':     ['AIHA','hemolytic anemia'],
};
// DKN_TARGET_MAP: each entry is an array of required keyword sets.
// A drug matches if its target field contains ALL keywords in at least one set (AND within a set, OR across sets).
// Format: array of arrays. Single-element inner arrays = single keyword.
// Multi-element inner arrays = ALL must be present (AND logic) for that set.
const DKN_TARGET_MAP = {
  'ailux-focus': [['TL1A'],['TSLP'],['IL-33'],['IL-4R'],['OX40'],['IGF-1R'],['IGF1R'],['TSHR'],['FcRn'],['BCMA'],['CD19'],['neonatal fc'],['efgartigimod'],['batoclimab'],['nipocalimab'],['rozanolixizumab'],['duvakitug'],['tulisokibart'],['afimkibart'],['teprotumumab'],['tepezza'],['amlitelimab'],['dupilumab'],['tezepelumab']],
  'tl1a':        [['TL1A'],['tl1a']],
  'tslp-il33':   [['TSLP'],['IL-33'],['tslp'],['il-33']],
  'il4ra-tslp':  [['IL-4R','TSLP'],['il-4r','tslp']],
  'il4ra-ox40l': [['IL-4R','OX40'],['il-4r','ox40']],
  'igf1r-tshr':  [['IGF-1R'],['IGF1R'],['TSHR'],['igf1r'],['tshr']],
  'fcrn':        [['FcRn'],['fcrn'],['neonatal fc']],
  'bcma-cd19':   [['BCMA'],['bcma']]
};

// ── Helpers ───────────────────────────────────────────────────────────────────
function _dknRisk(drug_summary) {
  if (!drug_summary) return '';
  const m = drug_summary.match(/^Risk:\s*(.+?)(?:\s*\|\s*.*)?$/);
  return m ? m[1].trim() : '';
}
function _dknNotes(drug_summary) {
  if (!drug_summary) return '';
  const idx = drug_summary.indexOf(' | ');
  return idx >= 0 ? drug_summary.slice(idx + 3).trim() : '';
}
function _dknCoName(d) {
  // Prefer the joined companies.name (lead company only) over the denormalized company_display
  return (d.companies && d.companies.name) || d.company_display || d.company_id || '—';
}

// ── Originator marker (latest-owner-primary, originator-secondary) ───────────
// Governance (refined 2026-06-07): company_id = displayed latest/notable owner;
// originator_company_id is retained and shown as a MUTED secondary marker.
// Fully additive + guarded — any failure simply renders no marker (never throws).
window._ORIG_NAME_CACHE = window._ORIG_NAME_CACHE || {}; // company_id → display name
async function _resolveOriginatorNames(ids) {
  try {
    const need = [...new Set((ids || []).filter(Boolean))].filter(id => !(id in window._ORIG_NAME_CACHE));
    if (!need.length) return;
    const { data } = await _sb.from('companies').select('id,name').in('id', need);
    (data || []).forEach(c => { window._ORIG_NAME_CACHE[c.id] = c.name || c.id; });
    // Mark unresolved ids so we don't refetch endlessly
    need.forEach(id => { if (!(id in window._ORIG_NAME_CACHE)) window._ORIG_NAME_CACHE[id] = null; });
  } catch (e) { console.warn('_resolveOriginatorNames', e); }
}
function _origShortName(name) {
  if (!name) return null;
  // "Boehringer Ingelheim" → "Boehringer"; keep single-word names whole
  return name.split(/[\s,]/)[0] || name;
}
// ── Full ownership chain (inventor → … → current owner) ──────────────────────
// Round 13: assembled from asset_transfer_history (one row per hop). The chain
// is display-only — drugs.company_id is NEVER changed. A multi-hop chain
// (3+ entities) renders as "· chain: A → B → C"; a 1-hop transfer falls back to
// the existing "· orig. X" marker. Fully additive + guarded (any failure = no
// chain, never throws). Loaded once into a module-level cache.
window._CHAIN_CACHE = window._CHAIN_CACHE || {}; // drug_id → ordered [entity names]
async function _resolveOwnershipChains() {
  if (window._CHAIN_LOADED) return;
  try {
    const { data } = await _sb.from('asset_transfer_history')
      .select('drug_id,sequence_order,from_entity_name,to_entity_name')
      .order('drug_id').order('sequence_order');
    const byDrug = {};
    (data || []).forEach(r => { (byDrug[r.drug_id] = byDrug[r.drug_id] || []).push(r); });
    Object.keys(byDrug).forEach(did => {
      const rows = byDrug[did].sort((a, b) => (a.sequence_order || 0) - (b.sequence_order || 0));
      const names = [];
      rows.forEach((r, i) => {
        if (i === 0 && r.from_entity_name) names.push(r.from_entity_name);
        if (r.to_entity_name) names.push(r.to_entity_name);
      });
      if (names.length >= 2) window._CHAIN_CACHE[did] = names;
    });
    window._CHAIN_LOADED = true;
  } catch (e) { console.warn('_resolveOwnershipChains', e); }
}
// Returns the muted ownership-chain / "· orig. X" HTML, or '' when not applicable.
// ── News-sentiment signal (Kyle 2026-06-07): a small, stable, glanceable dot shown
// wherever a company appears. Loaded once into _SENT_MAP (company_news_sentiment, ~32 rows).
window._SENT_MAP = window._SENT_MAP || null;
async function _loadSentimentMap() {
  if (window._SENT_MAP) return window._SENT_MAP;
  try {
    const rows = await (await fetch((typeof SUPABASE_URL !== 'undefined' ? SUPABASE_URL : 'https://tghntyofptvfhmtchwcv.supabase.co')
      + '/rest/v1/company_news_sentiment?select=company_id,net_sentiment,n_articles,last_article_date',
      { headers: { apikey: SUPABASE_ANON, Authorization: 'Bearer ' + SUPABASE_ANON } })).json();
    const m = {};
    (Array.isArray(rows) ? rows : []).forEach(r => { m[r.company_id] = r; });
    window._SENT_MAP = m;
  } catch (e) { window._SENT_MAP = {}; }
  return window._SENT_MAP;
}
// Returns a tiny colored sentiment dot for a company id, or '' if unknown.
// Stable signal: green bullish · amber/red bearish · grey mixed; hollow when sample < 3.
function _sentDotHTML(companyId) {
  const r = (window._SENT_MAP || {})[companyId];
  if (!r || r.n_articles == null) return '';
  const v = r.net_sentiment, n = r.n_articles;
  const band = v >= 0.35 ? ['#16a34a', 'Positive'] : v <= -0.35 ? ['#dc2626', 'Negative']
    : v > 0.1 ? ['#65a30d', 'Leaning positive'] : v < -0.1 ? ['#d97706', 'Leaning negative']
    : ['#94a3b8', 'Mixed / neutral'];
  const thin = n < 3;
  const tip = `News sentiment: ${band[1]} · net ${v >= 0 ? '+' : ''}${(+v).toFixed(2)} over ${n} article${n !== 1 ? 's' : ''}${r.last_article_date ? ', latest ' + r.last_article_date.slice(0, 10) : ''}. Tone of news flow, not a fundamental.${thin ? ' Thin sample — directional only.' : ''}`;
  const fill = thin ? `background:transparent;border:1.5px solid ${band[0]}` : `background:${band[0]};border:1.5px solid ${band[0]}`;
  // custom tooltip via data-senttip (native title is unreliable on tiny elements) — title kept as a11y fallback
  return `<span class="sent-dot" data-senttip="${tip.replace(/"/g, '&quot;')}" title="${tip.replace(/"/g, '&quot;')}" style="display:inline-block;width:9px;height:9px;border-radius:50%;${fill};vertical-align:middle;margin-left:5px;cursor:pointer"></span>`;
}
// One global, reliable tooltip for sentiment dots (Kyle 2026-06-07: native title showed only a cursor).
(function _initSentTip(){
  function ready(){
    if (document.getElementById('sent-tooltip')) return;
    const tip = document.createElement('div');
    tip.id = 'sent-tooltip';
    tip.style.cssText = 'position:fixed;z-index:99999;max-width:280px;background:#0f2340;color:#e7eefb;font-size:11.5px;line-height:1.45;padding:8px 11px;border-radius:7px;box-shadow:0 8px 28px rgba(0,0,0,.45);pointer-events:none;display:none;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif';
    document.body.appendChild(tip);
    function show(e){
      const d = e.target.closest && e.target.closest('.sent-dot[data-senttip]');
      if (!d) return;
      tip.textContent = d.getAttribute('data-senttip');
      tip.style.display = 'block';
      const r = d.getBoundingClientRect();
      let top = r.bottom + 8, left = Math.min(Math.max(8, r.left - 6), window.innerWidth - 290);
      if (top + tip.offsetHeight > window.innerHeight - 8) top = r.top - tip.offsetHeight - 8;
      tip.style.top = top + 'px'; tip.style.left = left + 'px';
    }
    function hide(e){ const d = e.target.closest && e.target.closest('.sent-dot'); if (d) tip.style.display = 'none'; }
    document.addEventListener('mouseover', show, true);
    document.addEventListener('mouseout', hide, true);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ready); else ready();
})();

function _originatorMarkerHTML(d) {
  try {
    if (!d) return '';
    // Multi-hop ownership chain takes precedence when available (3+ entities).
    const chain = (window._CHAIN_CACHE && d.id) ? window._CHAIN_CACHE[d.id] : null;
    if (chain && chain.length >= 3) {
      const owner = (typeof _dknCoName === 'function') ? _dknCoName(d) : (d.company_id || '');
      const trail = chain.map(n => _origShortName(n)).join(' → ');
      return `<span class="orig-marker" title="Ownership chain (inventor → current owner): ${chain.join(' → ')}. Displayed owner: ${owner}.">· chain: ${trail}</span>`;
    }
    const oid = d.originator_company_id;
    if (!oid || oid === d.company_id) return '';          // unknown or same-as-owner → no marker
    const full = window._ORIG_NAME_CACHE[oid];
    if (!full) return '';                                  // name not resolved yet → no marker (re-renders later)
    const owner = (typeof _dknCoName === 'function') ? _dknCoName(d) : (d.company_id || '');
    return `<span class="orig-marker" title="Originator (inventor/developer): ${full}. Displayed owner: ${owner}.">· orig. ${_origShortName(full)}</span>`;
  } catch (e) { return ''; }
}
// Strip leading trial-name / study-code prefixes from display names.
// Handles patterns like "CD-M24-885 risankizumab plus lictuzumab"
//   and "DUET risankizumab + lictuzumab" → "risankizumab + lictuzumab"
function _dknCleanName(raw) {
  if (!raw) return raw;
  // Strip one or more leading ALL-CAPS/alphanumeric-code tokens (trial names, codes)
  // A token qualifies if it starts with an uppercase letter and contains no lowercase letters
  let s = raw.replace(/^(?:[A-Z][A-Z0-9\-]*\s+)+/, '').trim();
  // Guard: if stripping left a leading '+', the first token was the first drug in a combo
  // label (e.g. "ABBV-701 + Skyrizi"), not a study prefix — restore the original string.
  if (s.startsWith('+')) s = raw;
  // Also handle colon separator: "DUET: risankizumab" → strip up to and including ": "
  s = s.replace(/^[A-Z][A-Z0-9\-]*:\s*/, '').trim();
  // Normalise " plus " and " / " as drug combinators → " + "
  s = s.replace(/\s+plus\s+/gi, ' + ');
  return s || raw; // fall back to original if we stripped everything
}

// ── PI tab drug label: brand name > INN > single code ────────────────────────
function _piDrugLabel(d) {
  if (d.brand_name) return d.brand_name;
  const raw = d.display_name || d.name || '';
  // Strip code-only parentheticals: "(REGN3500/SAR440340)", "(SAR-XXX)", etc.
  let s = raw.replace(/\s*\([A-Z][A-Z0-9\-]*(?:\/[A-Z0-9\-]+)+\)/g, '').trim();
  // Strip slash-separated code aliases after an INN: "Itepekimab/REGN3500" \u2192 "Itepekimab"
  s = s.replace(/^([A-Za-z][a-z]+\w*)\s*\/\s*[A-Z][A-Z0-9\-\/]+$/, '$1').trim();
  return _dknCleanName(s) || raw;
}
// ── Shared drug name HTML renderer: splits "Primary (Secondary)" → no parens ──
function _drugNameHTML(str) {
  if (!str) return '—';
  const m = str.match(/^(.+?)\s*\(([^)]+)\)\s*$/);
  if (!m) return str;
  return m[1].trim() + '<span class="drug-molecule-name">' + m[2].trim() + '</span>';
}
// ── PI tab drug label HTML: brand + (molecule) when brand exists ──────────────
function _piDrugLabelHTML(d) {
  const _sec = s => '<span class="drug-molecule-name">' + s + '</span>';
  if (d.brand_name) {
    // Use d.name (the INN) directly — avoids display_name doubling e.g. "Stelara (ustekinumab)"
    const mol = _dknCleanName(d.name || '') || '';
    if (!mol || mol.toLowerCase() === d.brand_name.toLowerCase()) return d.brand_name;
    return d.brand_name + _sec(mol);
  }
  // No brand name: use _piDrugLabel (strips research code parentheticals/slash codes)
  // then split any remaining "(secondary)" into styled span. Prevents "Itepekimab REGN3500/SAR440340".
  return _drugNameHTML(_piDrugLabel(d)) || '—';
}

// \u2500\u2500 Stage resolver \u2014 systemic approval detection \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
// Enrichment sets drugs.stage from trial-phase activity; regulatory approvals can be
// inferred from two strong signals: (a) brand_name is assigned post-approval, and
// (b) indication_short contains a year-in-parens e.g. "RA (2019)".
function _resolveStage(d) {
  // §A.2: drugs.stage is server-authoritative — DrugWriter enforces brand_name⇒approved at write
  // time, so the dashboard does NOT re-derive truth here; it only normalizes the approved_* family
  // (approved_us / approved_us_eu / …) to a single "Approved" display label. The former client-side
  // band-aids (brand_name⇒Approved; a "(20XX)" indication-year heuristic) were removed 2026-06-18
  // after an audit corrected 7 stale stages in the DB (audit: 0 rows still relied on either rule).
  const s = (d.stage || '').toLowerCase();
  if (s.includes('approv')) return 'Approved';
  return d.stage || 'Preclinical';
}

// ── Data loading ──────────────────────────────────────────────────────────────
async function dknLoadData() {
  if (_dknData !== null || _dknLoading) return;
  _dknLoading = true;
  const tbody = document.getElementById('dkn-tbody');
  if (tbody) tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;padding:24px;color:#64748b;font-size:12px">Loading drug catalog…</td></tr>';
  try {
    const { data, error } = await _sb
      .from('drugs')
      .select('id,display_name,company_display,company_id,originator_company_id,target,cls,catalog_category,stage,phase_display,indication_short,differentiation_thesis,drug_summary,endpoints,trial_names,stage_detail,key_data,ailux_angle,ailux_competes_directly,modality,modality_fmt,binding_domain,therapeutic_area,companies!company_id(name)')
      .not('catalog_category', 'is', null)
      .order('catalog_category')
      .order('stage');
    if (error) throw error;
    _dknData = data || [];
    _dknLoading = false;
    dknRender();
    _dknUpdateSnap();
    // Resolve originator company names (latest-owner-primary, originator-secondary),
    // then re-render so the muted "· orig. X" markers appear. Fully guarded.
    try {
      const _origIds = _dknData.map(d => d.originator_company_id)
        .filter(o => o && _dknData.some(x => x.id && x.originator_company_id === o && x.company_id !== o));
      if (_origIds.length) _resolveOriginatorNames(_origIds).then(() => { try { dknRender(); } catch (e) {} });
    } catch (e) { /* marker is non-critical */ }
    // Load full ownership chains (asset_transfer_history) → re-render so multi-hop
    // "· chain: A → B → C" trails appear. Fully guarded; chain failure is non-critical.
    try {
      _resolveOwnershipChains().then(() => { try { dknRender(); } catch (e) {} });
    } catch (e) { /* chain marker is non-critical */ }
  } catch(e) {
    console.warn('dknLoadData', e);
    _dknLoading = false;
    if (tbody) tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;padding:24px;color:#dc2626;font-size:12px">⚠ Failed to load drug catalog. Please refresh.</td></tr>';
  }
}

// ── Filter setters ────────────────────────────────────────────────────────────
function dknSetCat(btn, val) {
  dknCatFilter = val;
  document.querySelectorAll('#dkn-cat-chips .dkn-chip').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  dknRender();
}
function dknSetStage(btn, val) {
  dknStageFilter = val;
  document.querySelectorAll('#dkn-stage-chips .dkn-chip').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  dknRender();
}
function dknSetTarget(btn, val) {
  dknTargetFilter = val;
  document.querySelectorAll('#dkn-target-chips .dkn-chip').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  dknRender();
}
function dknSetClass(sel) {
  dknClassFilter = sel.value;
  dknRender();
}
function dknSetInd(sel) {
  dknIndFilter = sel.value;
  dknRender();
}
function dknSetCompany(sel) {
  dknCompanyFilter = sel.value;
  dknRender();
}
function dknSetModality(sel) {
  dknModalityFilter = sel.value;
  dknRender();
}
function dknSetStageDrop(sel) {
  dknStageDropFilter = sel.value;
  dknRender();
}
function dknSetTa(btn, val) {
  dknTaFilter = val;
  document.querySelectorAll('#dkn-ta-chips .dkn-chip').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  dknRender();
}
function dknSetTaDrop(sel) {
  dknTaFilter = sel.value;
  // Cascade: filter indication options to only show relevant indications for this TA
  const indSel = document.getElementById('dkn-ind-select');
  if (indSel) {
    const ta = sel.value;
    Array.from(indSel.options).forEach(opt => {
      if (!opt.value) return; // keep "Indication" placeholder
      opt.hidden = ta ? (opt.dataset.ta !== ta) : false;
    });
    // Clear indication filter if the selected indication isn't valid for this TA
    const curInd = indSel.value;
    if (curInd && ta) {
      const curOpt = indSel.querySelector(`option[value="${curInd}"]`);
      if (curOpt && curOpt.dataset.ta !== ta) {
        indSel.value = '';
        dknIndFilter = '';
      }
    }
  }
  dknRender();
}
function dknSetTargetDrop(sel) {
  dknTargetFilter = sel.value;
  dknRender();
}
function dknSetFmt(btn, val) {
  dknFmtChipFilter = val;
  document.querySelectorAll('#dkn-fmt-chips .dkn-chip').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  dknRender();
}
function dknPopulateSelects() {
  const drugs = _dknData || [];
  const sel = document.getElementById('dkn-class-select');
  if (sel && sel.options.length <= 1) {
    const classes = [...new Set(drugs.map(d => d.cls).filter(Boolean))].sort();
    classes.forEach(c => {
      const opt = document.createElement('option');
      opt.value = c; opt.textContent = c;
      sel.appendChild(opt);
    });
  }
  // Populate company dropdown
  const coSel = document.getElementById('dkn-company-select');
  if (coSel && coSel.options.length <= 1) {
    const names = [...new Set(drugs.map(d => (d.companies && d.companies.name) || d.company_display || d.company_id).filter(Boolean))].sort();
    names.forEach(n => {
      const opt = document.createElement('option');
      opt.value = n; opt.textContent = n;
      coSel.appendChild(opt);
    });
  }
  // Populate modality dropdown using modality_fmt shorthand
  const modSel = document.getElementById('dkn-modality-select');
  if (modSel && modSel.options.length <= 1) {
    const mods = [...new Set(drugs.map(d => d.modality_fmt || d.modality).filter(Boolean))].sort();
    mods.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m; opt.textContent = m;
      modSel.appendChild(opt);
    });
  }
}
function dknSort(col) {
  if (dknSortCol === col) dknSortDir *= -1;
  else { dknSortCol = col; dknSortDir = 1; }
  document.querySelectorAll('.dkn-master-table th').forEach(th => {
    th.classList.remove('sort-asc','sort-desc');
  });
  const colMap = {name:0,company:1,stage:2,target:4,indication:6};
  const thIdx = colMap[col];
  if (thIdx !== undefined) {
    const ths = document.querySelectorAll('.dkn-master-table th');
    ths[thIdx]?.classList.add(dknSortDir===1?'sort-asc':'sort-desc');
  }
  dknRender();
}

// ── Main render ───────────────────────────────────────────────────────────────
function dknRender() {
  if (!_dknData) return; // still loading — dknLoadData() will call dknRender() when ready
  dknPopulateSelects();
  // Sync column header sort indicators (covers initial render, not just user clicks)
  document.querySelectorAll('.dkn-master-table th').forEach(th => th.classList.remove('sort-asc','sort-desc'));
  if (dknSortCol) {
    const _cm = {name:0,company:1,stage:2,target:4,indication:6};
    const _ti = _cm[dknSortCol];
    if (_ti !== undefined) document.querySelectorAll('.dkn-master-table th')[_ti]?.classList.add(dknSortDir===1?'sort-asc':'sort-desc');
  }
  const q = '';
  let data = _dknData.filter(d => {
    if (dknCatFilter && d.catalog_category !== dknCatFilter) return false;
    // Use _resolveStage so approved_us / approved_us_eu / bla_under_review all match "Approved"
    const _dStage = _resolveStage(d);
    if (dknStageFilter && _dStage !== dknStageFilter) return false;
    if (dknStageDropFilter && _dStage !== dknStageDropFilter) return false;
    if (!dknShowRemoved && dknRemovedIds.includes(d.id)) return false;
    if (dknTargetFilter) {
      const sets = DKN_TARGET_MAP[dknTargetFilter] || [];
      const tgt = (d.target || '').toLowerCase();
      // A drug matches if its target contains ALL keywords in at least one set (OR across sets, AND within each set)
      const matched = sets.some(kws => kws.every(k => tgt.includes(k.toLowerCase())));
      if (!matched) return false;
    }
    if (dknClassFilter && d.cls !== dknClassFilter) return false;
    if (dknIndFilter) {
      const kws = DKN_IND_MAP[dknIndFilter] || [];
      const ind = (d.indication_short || '').toLowerCase();
      if (!kws.some(k => ind.includes(k.toLowerCase()))) return false;
    }
    if (dknCompanyFilter && _dknCoName(d) !== dknCompanyFilter) return false;
    if (dknModalityFilter && (d.modality_fmt || d.modality || '') !== dknModalityFilter) return false;
    if (dknTaFilter && (d.therapeutic_area || '') !== dknTaFilter) return false;
    if (dknFmtChipFilter) {
      const fmt = d.modality_fmt || '';
      if (dknFmtChipFilter === '_other') {
        if (!['Fc','FP'].includes(fmt)) return false;
      } else if (fmt !== dknFmtChipFilter) return false;
    }
    if (q) {
      const risk  = _dknRisk(d.drug_summary);
      const notes = _dknNotes(d.drug_summary);
      const haystack = [d.display_name, _dknCoName(d), d.target, d.cls,
        d.indication_short, d.differentiation_thesis, risk, notes, d.trial_names
      ].join(' ').toLowerCase();
      if (!haystack.includes(q)) return false;
    }
    return true;
  });
  if (dknSortCol) {
    data.sort((a,b) => {
      if (dknSortCol === 'stage') {
        const sa = STAGE_ORDER[a.stage] ?? 9;
        const sb = STAGE_ORDER[b.stage] ?? 9;
        return dknSortDir * (sa - sb);
      }
      const fieldMap = {name:'display_name', company:'company_display', indication:'indication_short'};
      const f = fieldMap[dknSortCol] || dknSortCol;
      const av = (a[f]||'').toLowerCase();
      const bv = (b[f]||'').toLowerCase();
      return dknSortDir * av.localeCompare(bv);
    });
  }
  const tbody = document.getElementById('dkn-tbody');
  if (data.length === 0) {
    tbody.innerHTML = '<tr><td colspan="11" class="dkn-no-results">No drugs match your filters. <a href="#" onclick="dknReset();return false;">Reset all filters</a></td></tr>';
  } else {
    tbody.innerHTML = data.map(d => dknRow(d)).join('');
  }
  const totalActive = _dknData.filter(d => !dknRemovedIds.includes(d.id)).length;
  const allBtn = document.querySelector('#dkn-target-chips .dkn-chip:not([class*="tgt-"])');
  if (allBtn) allBtn.textContent = `All (${totalActive})`;
  document.getElementById('dkn-count').textContent = data.length + ' drug' + (data.length!==1?'s':'') + ' shown';
  const remCount = dknRemovedIds.length;
  document.getElementById('dkn-removed-count').textContent = remCount;
  document.getElementById('dkn-undo-btn').style.display = dknUndoStack.length ? '' : 'none';
  document.getElementById('dkn-show-removed').style.display = remCount ? '' : 'none';
  if (dknShowRemoved) dknRenderRemovedPanel();
  _dknSortFavoritesToTop();
}

// ── Detail panel ──────────────────────────────────────────────────────────────
function dknToggleDetail(id) {
  const mainRow   = document.querySelector(`.dkn-drug-row[data-id="${id}"]`);
  const detailRow = document.getElementById(`dkn-dr-${id}`);
  if (!mainRow || !detailRow) return;
  const opening = !mainRow.classList.contains('dkn-open');
  mainRow.classList.toggle('dkn-open', opening);
  detailRow.classList.toggle('dkn-open', opening);
  if (opening && detailRow.querySelector('.dkn-detail-panel')?.dataset.loaded !== 'true') {
    _renderDetailPanel(id, detailRow);
  }
}

function _renderDetailPanel(id, detailRow) {
  const d = (_dknData || []).find(x => x.id === id);
  if (!d) return;
  const panel = detailRow.querySelector('.dkn-detail-panel');
  if (!panel) return;
  panel.dataset.loaded = 'true';

  const risk  = _dknRisk(d.drug_summary);
  const notes = _dknNotes(d.drug_summary);

  const gridCells = [
    { label: 'Class / Mechanism', val: d.cls || '—' },
    { label: 'Stage', val: d.stage_detail || d.phase_display || d.stage || '—' },
    { label: 'Key Trials', val: d.trial_names || (d.key_data ? 'See data below' : '—') },
    { label: 'Format (Fmt)', val: d.modality_fmt ? `${d.modality_fmt}${d.binding_domain ? ' · ' + d.binding_domain : ''}` : (d.modality || '—') },
    { label: 'Therapeutic Area', val: d.therapeutic_area || '—' },
  ].map(c => `<div class="dkn-dp-cell"><div class="dkn-dp-label">${c.label}</div><div class="dkn-dp-val">${c.val}</div></div>`).join('');

  const endpointsHtml = d.endpoints
    ? `<div class="dkn-dp-full"><div class="dkn-dp-label">Primary Endpoints</div><div class="dkn-dp-val">${d.endpoints}</div></div>`
    : '';

  const diffHtml = d.differentiation_thesis
    ? `<div class="dkn-dp-diff"><strong>💡 Why It Matters:</strong> ${d.differentiation_thesis}</div>` : '';
  const riskHtml = risk
    ? `<div class="dkn-dp-risk"><strong>⚠️ Key Risk:</strong> ${risk}</div>` : '';

  let liveHtml = '';
  if (d.key_data || d.ailux_angle) {
    const competesTag = d.ailux_competes_directly
      ? `<span class="dkn-dp-competes">⚔ Directly Competes with Ailux</span>` : '';
    if (d.key_data) {
      liveHtml += `<div class="dkn-dp-live"><div class="dkn-dp-live-label">📊 Trial Data ${competesTag}</div><div class="dkn-dp-live-text">${d.key_data}</div></div>`;
    }
    if (d.ailux_angle) {
      liveHtml += `<div class="dkn-dp-ailux"><div class="dkn-dp-ailux-label">◈ Ailux BD Signal</div><div class="dkn-dp-ailux-text">${d.ailux_angle}</div></div>`;
    }
  }

  const notesHtml = notes
    ? `<div class="dkn-dp-full" style="margin-top:6px"><div class="dkn-dp-label">Notes</div><div class="dkn-dp-val">${notes}</div></div>` : '';

  panel.innerHTML = `
    <div class="dkn-dp-grid">${gridCells}</div>
    ${endpointsHtml}
    ${diffHtml}
    ${riskHtml}
    ${liveHtml}
    ${notesHtml}
  `;
}

// ── Row renderer ──────────────────────────────────────────────────────────────
function dknRow(d) {
  const isRemoved = dknRemovedIds.includes(d.id);
  const stageCls  = 'sp-' + (d.stage || '').replace(' ','');
  const cat       = d.catalog_category || 'Pipeline';
  const catBarCls = 'cat-bar-' + cat.replace(/\s/g,'.');
  const eid       = `'${d.id}'`; // single-quoted for inline onclick — JSON.stringify produces double-quotes which break HTML attributes
  const dLabel    = _dknCleanName(d.display_name || d.id);
  const removeOrRestore = isRemoved
    ? `<button class="dkn-restore-btn" onclick="event.stopPropagation();dknRestoreInline(${eid})" title="Restore">↩</button>`
    : `<button class="dkn-trash-btn" onclick="event.stopPropagation();dknRemove(${eid})" title="Remove drug">🗑</button>`;
  const rowStyle = isRemoved ? ' style="opacity:0.4;background:#fff8f8;"' : '';
  const diff = d.differentiation_thesis || '';
  const risk = _dknRisk(d.drug_summary);
  const fmtBadge = d.modality_fmt
    ? `<span class="dkn-fmt-pill dkn-fmt-${d.modality_fmt.replace(/[^a-zA-Z]/g,'')}">${d.modality_fmt}</span>`
    : (d.modality ? `<span class="dkn-modality-pill" style="font-size:9px">${d.modality.slice(0,12)}</span>` : '<span style="color:#94a3b8">—</span>');
  const taPill = d.therapeutic_area
    ? `<span class="dkn-ta-pill dkn-ta-${d.therapeutic_area.split(' ')[0].toLowerCase()}">${d.therapeutic_area}</span>`
    : '<span style="color:#94a3b8">—</span>';
  const _dknFavs = JSON.parse(localStorage.getItem('meridian_drug_favorites') || '[]');
  const isFav = _dknFavs.includes(d.id);
  return `<tr data-id="${d.id}" data-drug-id="${d.id}" class="dkn-drug-row" onclick="dknToggleDetail(${eid})"${rowStyle}>
  <td class="dkn-fav-cell"><button class="dkn-fav-btn" onclick="event.stopPropagation();toggleDrugFav(${eid},this)" data-drug-id="${d.id}" title="Favorite">${isFav ? '⭐' : '☆'}</button></td>
  <td class="dkn-col-drug"><span class="dkn-cat-bar ${catBarCls}"></span><span class="dkn-drug-name" onclick="event.stopPropagation();openDrugEntityModal(${eid},'${dLabel.replace(/'/g,"\\'")}',event)" title="Open dossier">${dLabel}</span><span class="dkn-chevron">▶</span></td>
  <td class="dkn-col-co"><span class="dkn-co-link" onclick="event.stopPropagation();openCompanyEntityModal('${(d.company_id||'').replace(/'/g,"\\'")}','${(_dknCoName(d)).replace(/'/g,"\\'")}','drugs-know')" title="Open company profile">${_dknCoName(d)}</span>${(typeof _sentDotHTML==='function'?_sentDotHTML(d.company_id):'')}${_originatorMarkerHTML(d)}</td>
  <td class="dkn-col-stage"><span class="dkn-stage-pill ${stageCls}">${d.stage || '—'}</span></td>
  <td class="dkn-col-format">${fmtBadge}</td>
  <td class="dkn-col-ta">${taPill}</td>
  <td class="dkn-col-target" style="font-size:11px;font-weight:600;color:#2e6fb0">${d.target || '—'}</td>
  <td class="dkn-col-cls" style="font-size:10.5px;color:#475569">${d.cls || '—'}</td>
  <td class="dkn-col-ind" style="font-size:11px">${d.indication_short || '—'}</td>
  <td class="dkn-col-diff" style="font-size:11px;color:#1e293b">${diff.length > 90 ? diff.slice(0,90)+'…' : diff}</td>
  <td class="dkn-col-risk" style="font-size:11px;color:#64748b">${risk.length > 70 ? risk.slice(0,70)+'…' : risk}</td>
</tr>
<tr id="dkn-dr-${d.id}" class="dkn-detail-row">
  <td colspan="11" class="dkn-detail-td">
    <div class="dkn-detail-panel"></div>
  </td>
</tr>`;
}

// ── Remove / restore / undo ───────────────────────────────────────────────────
function dknRemove(id) {
  if (!dknRemovedIds.includes(id)) {
    dknRemovedIds.push(id);
    dknUndoStack.push(id);
  }
  dknRender();
}
function dknRestoreInline(id) {
  dknRemovedIds = dknRemovedIds.filter(x => x !== id);
  dknUndoStack  = dknUndoStack.filter(x => x !== id);
  dknRender();
}
function dknUndo() {
  if (!dknUndoStack.length) return;
  const id = dknUndoStack.pop();
  dknRemovedIds = dknRemovedIds.filter(x => x !== id);
  dknRender();
}
function dknToggleRemoved() {
  dknShowRemoved = !dknShowRemoved;
  const panel = document.getElementById('dkn-removed-panel');
  panel.style.display = dknShowRemoved ? '' : 'none';
  document.getElementById('dkn-show-removed').textContent = (dknShowRemoved ? '🙈 Hide' : '👁 Removed') + ' (' + dknRemovedIds.length + ')';
  dknRender();
}
function dknRenderRemovedPanel() {
  const removedData = (_dknData || []).filter(d => dknRemovedIds.includes(d.id));
  const list = document.getElementById('dkn-removed-list');
  list.innerHTML = removedData.map(d =>
    `<div class="dkn-removed-item">
      <button class="dkn-restore-btn" onclick="dknRestoreInline(${JSON.stringify(d.id)})">↩ Restore</button>
      <strong>${d.display_name || d.id}</strong> <span style="color:#94a3b8">${_dknCoName(d)}${_originatorMarkerHTML(d)} · ${d.target || '—'}</span>
    </div>`
  ).join('');
}
function dknReset() {
  dknCatFilter = ''; dknStageFilter = ''; dknTargetFilter = '';
  dknClassFilter = ''; dknIndFilter = '';
  dknCompanyFilter = ''; dknModalityFilter = ''; dknStageDropFilter = ''; dknTaFilter = ''; dknFmtChipFilter = '';
  const is = document.getElementById('dkn-ind-select');
  if (is) { is.value = ''; Array.from(is.options).forEach(o => { o.hidden = false; }); }
  const ts = document.getElementById('dkn-ta-select');
  if (ts) ts.value = '';
  const tgt = document.getElementById('dkn-target-select');
  if (tgt) tgt.value = '';
  const cs = document.getElementById('dkn-company-select');
  if (cs) cs.value = '';
  const ms = document.getElementById('dkn-modality-select');
  if (ms) ms.value = '';
  const sd = document.getElementById('dkn-stage-drop-select');
  if (sd) sd.value = '';
  dknRender();
}

// ── Favorites ─────────────────────────────────────────────────────────────────
function toggleDrugFav(drugId, btn) {
  let favs = JSON.parse(localStorage.getItem('meridian_drug_favorites') || '[]');
  if (favs.includes(drugId)) {
    favs = favs.filter(id => id !== drugId);
    btn.textContent = '☆';
  } else {
    favs.push(drugId);
    btn.textContent = '⭐';
  }
  localStorage.setItem('meridian_drug_favorites', JSON.stringify(favs));
  _dknSortFavoritesToTop();
}

function _dknSortFavoritesToTop() {
  const favs = JSON.parse(localStorage.getItem('meridian_drug_favorites') || '[]');
  const tbody = document.getElementById('dkn-tbody');
  if (!tbody) return;
  // Collect pairs: [mainRow, detailRow]
  const allRows = Array.from(tbody.querySelectorAll('tr'));
  const pairs = [];
  for (let i = 0; i < allRows.length; i++) {
    const row = allRows[i];
    if (row.dataset.drugId) {
      const detailRow = allRows[i + 1];
      pairs.push({ main: row, detail: detailRow, isFav: favs.includes(row.dataset.drugId) });
      if (detailRow) i++; // skip the detail row in the outer loop
    }
  }
  pairs.sort((a, b) => (b.isFav ? 1 : 0) - (a.isFav ? 1 : 0));
  pairs.forEach(p => {
    tbody.appendChild(p.main);
    if (p.detail) tbody.appendChild(p.detail);
  });
}

// ── Snap / changelog (runs after Supabase data loads) ─────────────────────────
function _dknUpdateSnap() {
  var SNAP_KEY = 'dkn_snap_v4';  // bump key — old integer IDs incompatible with text slugs
  var drugs    = _dknData || [];
  var currentMap = {};
  drugs.forEach(function(d){ currentMap[d.id] = d.display_name || d.id; });
  var currentIds = Object.keys(currentMap);
  var stored = null;
  try { stored = JSON.parse(localStorage.getItem(SNAP_KEY)); } catch(e) {}
  if (stored && stored.ids) {
    var storedSet  = new Set(stored.ids);
    var currentSet = new Set(currentIds);
    var added   = currentIds.filter(function(id){ return !storedSet.has(id); });
    var removed = stored.ids.filter(function(id){ return !currentSet.has(id); });
    if (added.length || removed.length) {
      var badge   = document.getElementById('dkn-change-badge');
      var countEl = document.getElementById('dkn-badge-count');
      if (badge)   badge.style.display = 'block';
      if (countEl) countEl.textContent = added.length + removed.length;
      window._dknCL = {
        added:   added.map(function(id){ return currentMap[id] || id; }),
        removed: removed.map(function(id){ return (stored.nameMap && stored.nameMap[id]) || id; }),
        date: new Date().toLocaleDateString()
      };
    }
  }
  var snap = { ids: currentIds, nameMap: currentMap, date: new Date().toISOString().split('T')[0] };
  try { localStorage.setItem(SNAP_KEY, JSON.stringify(snap)); } catch(e) {}
}

// ── Backward compat — dknLoadSbData now just calls dknLoadData ────────────────
function dknLoadSbData() { return dknLoadData(); }

// ── Auto-init when DKN tab becomes active ─────────────────────────────────────
(function() {
  const observer = new MutationObserver(() => {
    const pane = document.getElementById('tab-drugs-know');
    if (pane && pane.classList.contains('active')) {
      if (_dknData) dknRender(); else dknLoadData();
    }
  });
  const pane = document.getElementById('tab-drugs-know');
  if (pane) observer.observe(pane, {attributes:true, attributeFilter:['class']});
  if (pane && pane.classList.contains('active')) dknLoadData();
})();
