// ── PROGRAM BOARD ────────────────────────────────────────────────────────────
let _pbLoaded = false;

const PB_IND_META = {
  uc:     { label:'Ulcerative Colitis',            area:'Gastroenterology · IBD',  density:'MED',  queries:['TL1A drugs in UC','Companies active in both UC and CD','Targets with no approved drug in UC','Indication overlap with CD'] },
  cd:     { label:"Crohn’s Disease",               area:'Gastroenterology · IBD',  density:'MED',  queries:['IL-23p19 drugs in CD','Phase 3 readouts in CD 2027–2028','Companies active in both UC and CD','TNF franchise biosimilar threat'] },
  ad:     { label:'Atopic Dermatitis',             area:'Dermatology · Type 2',    density:'HIGH', queries:['IL-4Rα drugs in AD','TH2 targets in atopy','Phase 3 pipeline density','Next approvals after dupilumab'] },
  asthma: { label:'Asthma',                        area:'Pulmonology · Type 2',    density:'HIGH', queries:['TSLP vs IL-33 in asthma','Oral vs biologic pipeline','Companies in asthma + AD','Severe vs. moderate target split'] },
  ted:    { label:'Thyroid Eye Disease',           area:'Ophthalmology · IGF-1R',  density:'MED',  queries:['IGF-1R vs TSHR drugs in TED','Companies active in TED','First-line vs second-line assets','Phase 3 competitive landscape'] },
  gmg:    { label:'Generalized Myasthenia Gravis', area:'Neurology · FcRn',        density:'MED',  queries:['FcRn drugs in gMG','Approved vs pipeline in gMG','Companies with both FcRn and complement','Phase 3 timeline density'] },
  sle:    { label:'Systemic Lupus Erythematosus',  area:'Rheumatology · SLE',      density:'MED',  queries:['SLE drugs by target class','Companies with ≥2 SLE assets','B-cell vs innate immune targets','First-in-class openings in SLE'] }
};

const TARGET_LABELS = { tl1a:'TL1A', il23p19:'IL-23p19', a4b7:'α4β7', il12_23p40:'IL-12/23p40', il4ra:'IL-4Rα', il13:'IL-13', tslp:'TSLP', il33:'IL-33', fcrn:'FcRn', cd19:'CD19', bcma:'BCMA', cd3:'CD3', cd20:'CD20', cd38:'CD38', igf1r:'IGF-1R', tshr:'TSHR', il17a:'IL-17A', tnf:'TNF', il6:'IL-6', baff:'BAFF', baff_r:'BAFF-R', ifnar1:'IFNAR1', pd1:'PD-1', cd40:'CD40' };

// Phase 4 Comparison Readiness — sourced from docs/phase4_comparison_harness.md (2026-05-25)
// status: ready (≥95% raw), compare_pass (OOS-adjusted ≥95%), close (70-94%), blocked (active migration blocker), not_ready (<70% or fundamental gap)
const COMPARISON_READINESS = {
  uc:     { status:'compare_pass', pct:98,  note:'tl1a 92.2% raw / 97.9% OOS-adjusted · 3 confirmed OOS excluded (lm-302=gastric ADC, sim0500=RRMM, spy072=TL1A-PsA/axSpA) · governance rule 2026-05-25: OOS drugs removed from denominator · ready for Phase 4 dual-read — NOT Phase 5 migration' },
  cd:     { status:'compare_pass', pct:98,  note:'ibd 94.0% raw / 97.9% OOS-adjusted · 2 confirmed OOS excluded (lm-302, sim0500) · governance rule 2026-05-25: OOS drugs removed from denominator · ready for Phase 4 dual-read — NOT Phase 5 migration' },
  ad:     { status:'close',     pct:90,  note:'atopy 90% / il4ra 100% · 1 drug missing (upadacitinib→ad)' },
  asthma: { status:'ready',     pct:100, note:'il4ra 100% / respiratory 100% / tslp 100% · migration safe' },
  ted:    { status:'close',     pct:89,  note:'igf1r 88.9% / ted 91.7% · batoclimab scope mismatch unresolved' },
  gmg:    { status:'not_ready', pct:57,  note:'fcrn 57.1% / autoimmune 48% · FcRn + complement backfill needed' },
  sle:    { status:'not_ready', pct:48,  note:'autoimmune 48% · wave 2D multi-portfolio backfill needed' },
};
const READINESS_STYLE = {
  ready:        { icon:'✅', label:'Ready',        color:'#4caf76' },
  compare_pass: { icon:'🟢', label:'Compare Pass', color:'#22c55e' },
  close:        { icon:'🟡', label:'Close',        color:'#f59e0b' },
  blocked:      { icon:'🔴', label:'Blocked',      color:'#ef4444' },
  not_ready:    { icon:'⛔', label:'Not Ready',    color:'#6b8aad' },
};

async function pbLoadCard(indId) {
  const meta = PB_IND_META[indId] || {};
  document.querySelectorAll('.pb-ind-btn').forEach(b => {
    const active = b.dataset.ind === indId;
    b.style.borderColor = active ? '#0891b2' : '#1e3a5f';
    b.style.background  = active ? '#0c2233' : 'transparent';
    b.style.color       = active ? '#38bdf8' : '#6b8aad';
  });
  document.getElementById('pb-card-area').textContent    = meta.area || '—';
  document.getElementById('pb-card-ind').textContent     = meta.label || indId;
  document.getElementById('pb-card-density').textContent = meta.density || '—';
  const _r = COMPARISON_READINESS[indId] || { status:'not_ready', pct:0, note:'No harness data for this indication' };
  const _rs = READINESS_STYLE[_r.status] || READINESS_STYLE.not_ready;
  const _rEl = document.getElementById('pb-card-readiness');
  if (_rEl) { _rEl.innerHTML = `<span style="color:${_rs.color}">${_rs.icon} ${_rs.label}</span> <span style="font-size:10px;color:#6b8aad">(${_r.pct}%)</span>`; _rEl.title = _r.note; }
  ['pb-card-assets','pb-card-companies','pb-card-catalysts','pb-card-targets-count'].forEach(id => {
    document.getElementById(id).textContent = '—';
  });
  document.getElementById('pb-card-targets').innerHTML  = '<span style="color:#6b8aad;font-size:11px">loading…</span>';
  document.getElementById('pb-card-readouts').innerHTML = '<span style="color:#6b8aad;font-size:11px">loading…</span>';
  document.getElementById('pb-card-source').textContent = 'Loading from relationship tables…';
  if (meta.queries) {
    document.getElementById('pb-card-queries').innerHTML = meta.queries.map(q =>
      `<code style="font-size:10px;color:#94a3b8;background:#1a2a3d;padding:3px 8px;border-radius:3px">${q}</code>`
    ).join('');
  }
  const sb = _sb;
  if (!sb) return;
  try {
    // 1. Drugs via drug_indications
    const diRes = await sb.from('drug_indications').select('drug_id,confidence_level,review_status').eq('indication_id', indId);
    const diRows  = diRes.data || [];
    const drugIds = [...new Set(diRows.map(r => r.drug_id))];
    const confA   = diRows.filter(r => r.confidence_level === 'A').length;
    const confB   = diRows.filter(r => r.confidence_level === 'B').length;
    const confC   = diRows.filter(r => r.confidence_level === 'C').length;
    const sampling = diRows.filter(r => r.review_status === 'sampling_queue').length;
    document.getElementById('pb-card-assets').textContent     = drugIds.length;
    document.getElementById('pb-card-assets-sub').textContent = `${diRows.length} rows · drug_indications`;
    document.getElementById('pb-card-source').textContent     = 'L4 active · drug_indications + drug_targets + trial_indications';

    // 2. Targets via drug_targets
    let tgtMap = {};
    if (drugIds.length > 0) {
      const dtRes = await sb.from('drug_targets').select('drug_id,target_id').in('drug_id', drugIds.slice(0, 50));
      (dtRes.data || []).forEach(r => { tgtMap[r.target_id] = (tgtMap[r.target_id] || 0) + 1; });
    }
    const sortedTgts = Object.entries(tgtMap).sort((a,b) => b[1]-a[1]);
    document.getElementById('pb-card-targets-count').textContent = sortedTgts.length;
    document.getElementById('pb-card-targets-sub').textContent   = sortedTgts.length > 0 ? 'from drug_targets' : 'no target links yet';
    document.getElementById('pb-card-targets').innerHTML = sortedTgts.length > 0
      ? sortedTgts.map(([tid, n]) => {
          const lbl = TARGET_LABELS[tid] || tid.toUpperCase();
          return `<span style="background:#0f1923;border:1px solid #1e3a5f;color:#f0f6ff;padding:4px 10px;border-radius:4px;font-size:11px;font-weight:600">${lbl}<span style="color:#4a90c4;margin-left:4px;font-size:10px">${n}↑</span></span>`;
        }).join('')
      : '<span style="color:#6b8aad;font-size:11px">No drug_targets rows for this indication yet</span>';

    // 3. Companies via drugs.company_id
    let compCount = drugIds.length;
    if (drugIds.length > 0) {
      const drRes = await sb.from('drugs').select('id,company_id').in('id', drugIds.slice(0, 50));
      const coIds = new Set((drRes.data || []).map(r => r.company_id).filter(Boolean));
      if (coIds.size > 0) compCount = coIds.size;
    }
    document.getElementById('pb-card-companies').textContent     = compCount;
    document.getElementById('pb-card-companies-sub').textContent = 'unique companies · drugs table';

    // 4. Trials via trial_indications
    const tiRes = await sb.from('trial_indications').select('trial_id').eq('indication_id', indId);
    const tiCount = new Set((tiRes.data || []).map(r => r.trial_id)).size;
    document.getElementById('pb-card-catalysts').textContent     = tiCount;
    document.getElementById('pb-card-catalysts-sub').textContent = 'trials · trial_indications';

    // 5. Confidence mix + held reviews
    const heldRes = await sb.from('backfill_preview').select('id', { count: 'exact', head: true })
      .eq('target_id_col', indId).eq('preview_status', 'pending_review').eq('proposed_review_status', 'review_required');
    const heldCount = heldRes.count || 0;
    document.getElementById('pb-card-readouts').innerHTML =
      `<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-bottom:8px">
        <div style="text-align:center;background:#0f1923;border-radius:4px;padding:6px 4px">
          <div style="font-size:18px;font-weight:800;color:#4caf76">${confA}</div>
          <div style="font-size:9px;color:#6b8aad;text-transform:uppercase;letter-spacing:1px">Conf A</div>
        </div>
        <div style="text-align:center;background:#0f1923;border-radius:4px;padding:6px 4px">
          <div style="font-size:18px;font-weight:800;color:#f59e0b">${confB}</div>
          <div style="font-size:9px;color:#6b8aad;text-transform:uppercase;letter-spacing:1px">Conf B</div>
        </div>
        <div style="text-align:center;background:#0f1923;border-radius:4px;padding:6px 4px">
          <div style="font-size:18px;font-weight:800;color:${confC > 0 ? '#ef4444' : '#4a90c4'}">${confC}</div>
          <div style="font-size:9px;color:#6b8aad;text-transform:uppercase;letter-spacing:1px">Conf C</div>
        </div>
      </div>` +
      (sampling > 0 ? `<div style="font-size:10px;color:#f59e0b;margin-bottom:3px">⚑ ${sampling} row${sampling>1?'s':''} sampling_queue</div>` : '') +
      (heldCount > 0 ? `<div style="font-size:10px;color:#ef4444">⚠ ${heldCount} held review_required</div>` : '<div style="font-size:10px;color:#4caf76">✓ No held rows</div>');

  } catch (e) {
    console.error('pbLoadCard error:', e);
    document.getElementById('pb-card-source').textContent = 'Error loading — check console';
  }
}

async function pbInit() {
  if (_pbLoaded) return;
  _pbLoaded = true;
  const ts = document.getElementById('pb-timestamp');
  if (ts) ts.textContent = new Date().toLocaleDateString('en-US', {month:'short',day:'numeric',year:'numeric'});
  const bar  = document.getElementById('pb-l4-bar');
  const pct  = document.getElementById('pb-l4-pct');
  const gate = document.getElementById('pb-di-gate');
  if (bar) { bar.style.width = '100%'; bar.style.background = 'linear-gradient(90deg,#4caf76,#0891b2)'; }
  if (pct) { pct.textContent = 'L4 Queryable — ACHIEVED 2026-05-25'; pct.style.color = '#4caf76'; }
  if (gate) gate.textContent = '✓ Trial Indications (Wave 2B · 319 rows committed 2026-05-25)';
  const dSub = document.getElementById('pb-d-summary');
  if (dSub) dSub.innerHTML = '177 refs audited · 68 safe · 94 needs-migration · <span style="color:#f59e0b">15 → Phase 4 queue</span>';
  await pbLoadCard('uc');
}
