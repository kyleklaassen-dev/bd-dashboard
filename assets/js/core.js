// ── Ailux BD Platform · Supabase Layer ──────────────────────────────────────
const SUPABASE_URL  = "https://tghntyofptvfhmtchwcv.supabase.co";
const SUPABASE_ANON = "sb_publishable_3GLfZ7b9Tjp9RFRcc4YZew_ov-fY7dI";
const _sb = supabase.createClient(SUPABASE_URL, SUPABASE_ANON);

// ── S3: fresh-data banner ───────────────────────────────────────────────────
// Polls the system_status singleton row (stamped by the nightly enrichment and
// research pipelines on completion). We baseline the server timestamps at page
// load, then compare server-to-server on each poll — no wall-clock comparison,
// so client clock skew never produces false positives. When a newer
// last_enrichment_at (or last_research_at) appears, we surface a soft, dismissable
// "refresh" banner rather than auto-reloading, so work in progress is never lost.
const FRESH_POLL_MS = 5 * 60 * 1000;   // 5 minutes
let _freshBaseline   = null;           // {enr,res} captured on first poll
let _freshDismissed  = false;
let _freshShown      = false;

function _dismissFreshBanner() {
  _freshDismissed = true;
  const el = document.getElementById('fresh-data-banner');
  if (el) { el.classList.remove('show'); setTimeout(() => { el.hidden = true; }, 350); }
}

function _showFreshBanner(cur, enrNew, merNew) {
  const el  = document.getElementById('fresh-data-banner');
  const txt = document.getElementById('fresh-banner-text');
  if (!el || !txt) return;
  if (merNew) {
    txt.textContent = 'A new Meridian Issue has been published — refresh to read it.';
  } else if (enrNew && Number(cur.cnt) > 0) {
    const n = Number(cur.cnt);
    txt.textContent = `New intelligence has arrived — ${n} record${n === 1 ? '' : 's'} updated since you opened this page.`;
  } else {
    txt.textContent = 'New intelligence has arrived since you opened this page.';
  }
  el.hidden = false;
  requestAnimationFrame(() => el.classList.add('show'));
  _freshShown = true;
}

async function _pollSystemStatus() {
  try {
    const { data, error } = await _sb
      .from('system_status')
      .select('last_enrichment_at,last_research_at,last_meridian_at,last_scoring_at,updated_record_count')
      .eq('id', 1)
      .maybeSingle();
    if (error || !data) return;
    const cur = { enr: data.last_enrichment_at, res: data.last_research_at,
                  mer: data.last_meridian_at, sco: data.last_scoring_at,
                  cnt: data.updated_record_count };
    if (_freshBaseline === null) { _freshBaseline = cur; return; }   // establish baseline, no alert
    if (_freshShown || _freshDismissed) return;
    const newer = (a, b) => a && (!b || new Date(a) > new Date(b));
    const enrNew = newer(cur.enr, _freshBaseline.enr);
    const resNew = newer(cur.res, _freshBaseline.res);
    const merNew = newer(cur.mer, _freshBaseline.mer);
    const scoNew = newer(cur.sco, _freshBaseline.sco);
    if (enrNew || resNew || merNew || scoNew) _showFreshBanner(cur, enrNew, merNew);
  } catch (e) { /* non-fatal — banner is best-effort */ }
}

function _startFreshDataWatch() {
  _pollSystemStatus();                          // baseline immediately on load
  setInterval(_pollSystemStatus, FRESH_POLL_MS);
}
document.addEventListener('DOMContentLoaded', _startFreshDataWatch);
// preload the news-sentiment signal map (guard: fn is declared in a later script block)
(function _preloadSent(){ if (typeof _loadSentimentMap === 'function') { _loadSentimentMap(); }
  else { setTimeout(_preloadSent, 300); } })();

// ── Wave 2: pipeline health indicator ────────────────────────────────────────
// Surfaces the previously-dark pipeline_runs + system_status.health_summary as a
// soft header dot. Green = all workflows healthy, amber = something failing.
// Click opens a panel listing the latest run per workflow. Read-only, best-effort.
let _healthRuns = [];
const _HEALTH_LABELS = {  // tidy a couple of path-named legacy rows; most names are already friendly
  '.github/workflows/apply-migration.yml': 'Apply SQL Migration',
};
function _prettyWf(name) {
  if (!name) return 'Workflow';
  if (_HEALTH_LABELS[name]) return _HEALTH_LABELS[name];
  if (name.startsWith('.github/workflows/')) {
    return name.split('/').pop().replace(/\.ya?ml$/,'').replace(/[-_]/g,' ')
               .replace(/\b\w/g, c => c.toUpperCase());
  }
  return name;
}
function _relTime(iso) {
  if (!iso) return '';
  const ms = Date.now() - new Date(iso).getTime();
  const m = Math.round(ms/60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m/60);
  if (h < 24) return `${h}h ago`;
  return `${Math.round(h/24)}d ago`;
}
async function _loadSystemHealth() {
  try {
    const ssP = _sb.from('system_status').select('health_summary,last_health_at').eq('id',1).maybeSingle();
    const prP = _sb.from('pipeline_runs')
      .select('workflow_name,status,conclusion,recorded_at,run_started_at,run_html_url')
      .order('recorded_at',{ascending:false}).limit(80);
    const [{data:ss}, {data:runs}] = await Promise.all([ssP, prP]);
    // latest run per workflow
    const seen = new Map();
    (runs||[]).forEach(r => { if (!seen.has(r.workflow_name)) seen.set(r.workflow_name, r); });
    _healthRuns = [...seen.values()];
    const failing = _healthRuns.filter(r => r.conclusion && !['success','skipped','cancelled','neutral'].includes(r.conclusion) && r.status==='completed');
    // header dot
    const dot = document.getElementById('health-nav-dot');
    const dotDot = document.getElementById('health-nav-dot-dot');
    const dotLbl = document.getElementById('health-nav-dot-lbl');
    if (dot && dotDot && dotLbl) {
      let cls='unknown', lbl='—';
      if (_healthRuns.length) {
        if (failing.length===0) { cls='ok'; lbl='All green'; }
        else { cls='bad'; lbl=`${failing.length} failing`; }
      }
      dotDot.className = 'health-dot '+cls;
      dotLbl.textContent = lbl;
      dot.style.display = 'inline-flex';
    }
    // stash summary for the panel
    _healthRuns._summary = ss && ss.health_summary ? ss.health_summary.split(' @ ')[0] : null;
    _healthRuns._checked = ss && ss.last_health_at ? ss.last_health_at : null;
  } catch (e) { /* best-effort */ }
}
document.addEventListener('DOMContentLoaded', _loadSystemHealth);

// ── Needs-Your-Review queue: open governance_violations Claude flagged for human judgment ──
let _reviewItems = [];
const _RULE_LABEL = {
  mechanism_target_inconsistency:'Mechanism vs target', missing_originator:'Missing company',
  missing_originator_obscure:'Missing company', trial_id_misattribution:'Trial misattribution',
  hallucinated_mechanism:'Mechanism error', area_misclassification:'Wrong area',
  source_does_not_support_claim:'Source mismatch', misingested_out_of_scope:'Mis-ingested',
  ambiguous_identity:'Ambiguous identity', missing_originator_obscure:'Obscure code',
};
let _reviewNeedsDecision = [], _reviewParked = [];
async function _loadReviewQueue() {
  try {
    const { data } = await _sb.from('governance_violations')
      .select('id,table_name,row_id,rule_name,description,detected_at,resolution_notes')
      .eq('resolved', false).order('detected_at', { ascending:false }).limit(60);
    _reviewItems = data || [];
    // An item with resolution_notes has been adjudicated to a HOLD/PARK decision —
    // it's tracked but needs no fresh judgment. Only un-adjudicated items are "to review".
    _reviewNeedsDecision = _reviewItems.filter(v => !v.resolution_notes);
    _reviewParked        = _reviewItems.filter(v =>  v.resolution_notes);
    const btn = document.getElementById('review-nav-btn');
    const lbl = document.getElementById('review-nav-lbl');
    if (btn && lbl) {
      if (_reviewNeedsDecision.length) {
        lbl.textContent = '⚑ '+_reviewNeedsDecision.length+' to review';
        lbl.style.color = '#b45309'; btn.style.borderColor = '#fde68a'; btn.style.background = '#fffbeb';
        btn.style.display = 'inline-flex';
      } else if (_reviewParked.length) {
        // nothing needs a decision — show a calm, non-nagging "parked" pill
        lbl.textContent = '✓ '+_reviewParked.length+' parked';
        lbl.style.color = '#64748b'; btn.style.borderColor = '#e2e8f0'; btn.style.background = '#f8fafc';
        btn.style.display = 'inline-flex';
      } else btn.style.display = 'none';
    }
  } catch(e) { /* best-effort */ }
}
document.addEventListener('DOMContentLoaded', _loadReviewQueue);

function _reviewDrugLinks(rowId) {
  // row_id may be a comma-list of drug ids; each: open-card link + 🔍 web-verify
  return String(rowId||'').split(',').map(s=>s.trim()).filter(Boolean).slice(0,12).map(id =>
    `<span style="display:inline-flex;align-items:center;border:1px solid #e2e8f0;border-radius:6px;overflow:hidden">`
    + `<a href="#" data-trusted="1" onclick="event.preventDefault();closeReviewPanel();openDrugEntityModal('${id}','${id}',null)" style="font-size:11px;color:#2563eb;text-decoration:none;padding:1px 6px;white-space:nowrap">${id}</a>`
    + `🔍`
    + `</span>`
  ).join(' ');
}
function _reviewCard(v, parked) {
  const lbl = _RULE_LABEL[v.rule_name] || (v.rule_name||'').replace(/_/g,' ');
  const chipBg = parked ? '#f1f5f9' : '#fffbeb', chipFg = parked ? '#475569' : '#b45309', chipBd = parked ? '#e2e8f0' : '#fde68a';
  const decision = parked && v.resolution_notes
    ? `<div style="font-size:10.5px;color:#0f766e;background:#f0fdfa;border-left:3px solid #5eead4;border-radius:0 4px 4px 0;padding:5px 8px;line-height:1.45"><strong>Decision:</strong> ${(v.resolution_notes||'').replace(/</g,'&lt;')}</div>` : '';
  return `<div class="health-run" style="flex-direction:column;align-items:stretch;gap:5px;padding:10px 4px">
      <div style="display:flex;align-items:center;gap:8px">
        <span style="font-size:8.5px;font-weight:800;text-transform:uppercase;letter-spacing:.03em;background:${chipBg};color:${chipFg};border:1px solid ${chipBd};border-radius:8px;padding:1px 7px">${lbl}</span>
        <span style="font-size:10px;color:#94a3b8;margin-left:auto">${(v.detected_at||'').slice(0,10)}</span>
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:5px">${_reviewDrugLinks(v.row_id)}</div>
      <div style="font-size:11.5px;color:#475569;line-height:1.4">${(v.description||'').replace(/</g,'&lt;')}</div>
      ${decision}
    </div>`;
}
function openReviewPanel() {
  const ov = document.getElementById('review-overlay'); if (!ov) return;
  const nd = _reviewNeedsDecision.length, pk = _reviewParked.length;
  document.getElementById('review-summary').textContent =
    nd ? `${nd} item${nd!==1?'s':''} need your judgment${pk?` · ${pk} parked`:''}`
       : pk ? `All clear — nothing needs your judgment. ${pk} item${pk!==1?'s':''} parked (tracked, awaiting disclosure).`
            : 'Nothing to review — all clear. ✅';
  const list = document.getElementById('review-list');
  let html = '';
  if (nd) html += _reviewNeedsDecision.map(v => _reviewCard(v,false)).join('');
  if (pk) {
    html += `<div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.04em;color:#94a3b8;margin:14px 2px 4px">Parked — adjudicated, awaiting disclosure (no action needed)</div>`;
    html += _reviewParked.map(v => _reviewCard(v,true)).join('');
  }
  list.innerHTML = html || '<div class="health-empty">Nothing to review — all clear. ✅</div>';
  ov.classList.add('show');
}
function closeReviewPanel() { const ov=document.getElementById('review-overlay'); if(ov) ov.classList.remove('show'); }

// ── Whitespace Finder ─────────────────────────────────────────────────────────
// Reads v_whitespace_targets / v_whitespace_indications (v78): where high patient
// unmet need meets thin competition, using the structural graph (ADDRESSES/TREATS
// edges) + indication_patient_intelligence. Views are always-live; no staleness.
let _wsTargets = [], _wsIndications = [];
async function _loadWhitespace() {
  try {
    const [t, i] = await Promise.all([
      _sb.from('v_whitespace_targets')
         .select('target_label,full_name,target_class,ailux_relevance,best_unmet,indications_addressed,max_escape_rate,drug_count,opportunity_score')
         .order('opportunity_score', { ascending:false }).limit(40),
      _sb.from('v_whitespace_indications')
         .select('indication_name,disease_area,unmet_need_score,biologic_failure_rate_pct,patient_count_us,drugs_total,drugs_late,opportunity_score,data_confidence,trial_endpoint_gap')
         .order('opportunity_score', { ascending:false }).limit(40),
    ]);
    _wsTargets = t.data || []; _wsIndications = i.data || [];
    const btn = document.getElementById('ws-nav-btn');
    if (btn && (_wsTargets.length || _wsIndications.length)) btn.style.display='inline-flex';
  } catch(e) { /* best-effort */ }
}
// DEPRECATED 2026-06-06: Whitespace pill removed entirely per Kyle (non-inclusive DB → unreliable gap claims). Loader disabled.
// document.addEventListener('DOMContentLoaded', _loadWhitespace);

function _wsScoreColor(s) {
  if (s >= 65) return {bg:'#ecfdf5', bd:'#a7f3d0', fg:'#047857'};   // strong opportunity
  if (s >= 45) return {bg:'#fffbeb', bd:'#fde68a', fg:'#b45309'};   // moderate
  return {bg:'#f1f5f9', bd:'#e2e8f0', fg:'#64748b'};                // crowded / thin signal
}
function _wsScorePill(s) {
  const c = _wsScoreColor(s);
  return `<span style="font-size:13px;font-weight:800;background:${c.bg};color:${c.fg};border:1px solid ${c.bd};border-radius:8px;padding:2px 9px;min-width:34px;text-align:center;display:inline-block">${s}</span>`;
}
function _wsNum(n) { return n==null ? '—' : Number(n).toLocaleString(); }

function _renderWhitespace(mode) {
  document.getElementById('ws-tab-targets').className = 'ws-tab' + (mode==='targets'?' active':'');
  document.getElementById('ws-tab-indications').className = 'ws-tab' + (mode==='indications'?' active':'');
  const list = document.getElementById('ws-list');
  if (mode==='indications') {
    document.getElementById('ws-legend').textContent = 'Indications ranked by unmet need × patient scale vs. late-stage saturation. High score = real patient gap, thin pipeline.';
    list.innerHTML = _wsIndications.map(r => {
      const conf = r.data_confidence==='low'
        ? `<span title="Few drugs mapped in Meridian's catalog for this indication — score may understate true competition" style="font-size:8.5px;font-weight:800;text-transform:uppercase;background:#fef2f2;color:#b91c1c;border:1px solid #fecaca;border-radius:7px;padding:1px 6px">thin data</span>` : '';
      const esc = r.biologic_failure_rate_pct!=null ? `${Math.round(r.biologic_failure_rate_pct)}% fail biologics` : '';
      return `<div class="health-run" style="flex-direction:column;align-items:stretch;gap:6px;padding:11px 4px">
        <div style="display:flex;align-items:center;gap:9px">
          ${_wsScorePill(r.opportunity_score)}
          <span style="font-weight:700;font-size:13px;color:#1e293b">${r.indication_name}</span>
          ${conf}
          <span style="font-size:10px;color:#94a3b8;margin-left:auto">${r.disease_area||''}</span>
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:6px;font-size:10.5px;color:#475569">
          <span style="background:#f8fafc;border:1px solid #eef2f7;border-radius:6px;padding:1px 7px">unmet ${r.unmet_need_score}/10</span>
          <span style="background:#f8fafc;border:1px solid #eef2f7;border-radius:6px;padding:1px 7px">${_wsNum(r.patient_count_us)} US pts</span>
          ${esc?`<span style="background:#f8fafc;border:1px solid #eef2f7;border-radius:6px;padding:1px 7px">${esc}</span>`:''}
          <span style="background:#f8fafc;border:1px solid #eef2f7;border-radius:6px;padding:1px 7px">${r.drugs_total} drugs · ${r.drugs_late} late-stage</span>
        </div>
        ${r.trial_endpoint_gap?`<div style="font-size:11px;color:#64748b;line-height:1.4">↳ ${(r.trial_endpoint_gap||'').replace(/</g,'&lt;')}</div>`:''}
      </div>`;
    }).join('') || '<div class="health-empty">No indication data.</div>';
  } else {
    document.getElementById('ws-legend').textContent = 'Mechanisms ranked by unmet need of the indications they address vs. how many drugs already hit them. High score = under-exploited target.';
    list.innerHTML = _wsTargets.map(r => {
      const ail = r.ailux_relevance ? `<span style="font-size:8.5px;font-weight:800;text-transform:uppercase;background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;border-radius:7px;padding:1px 6px">Ailux: ${r.ailux_relevance}</span>` : '';
      return `<div class="health-run" style="flex-direction:column;align-items:stretch;gap:6px;padding:11px 4px">
        <div style="display:flex;align-items:center;gap:9px">
          ${_wsScorePill(r.opportunity_score)}
          <span style="font-weight:700;font-size:13px;color:#1e293b">${r.target_label}</span>
          ${ail}
          <span style="font-size:10px;color:#94a3b8;margin-left:auto">${r.target_class||''}</span>
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:6px;font-size:10.5px;color:#475569">
          <span style="background:#f8fafc;border:1px solid #eef2f7;border-radius:6px;padding:1px 7px">best unmet ${r.best_unmet}/10</span>
          <span style="background:#f8fafc;border:1px solid #eef2f7;border-radius:6px;padding:1px 7px">${r.indications_addressed} indication${r.indications_addressed!==1?'s':''}</span>
          <span style="background:#f8fafc;border:1px solid #eef2f7;border-radius:6px;padding:1px 7px">${r.drug_count} drug${r.drug_count!==1?'s':''} in dev</span>
        </div>
      </div>`;
    }).join('') || '<div class="health-empty">No target data.</div>';
  }
}
function openWhitespacePanel() {
  const ov = document.getElementById('ws-overlay'); if (!ov) return;
  _renderWhitespace('targets');
  ov.classList.add('show');
}
function closeWhitespacePanel() { const ov=document.getElementById('ws-overlay'); if(ov) ov.classList.remove('show'); }

function openHealthPanel() {
  const ov = document.getElementById('health-overlay'); if (!ov) return;
  const failing = _healthRuns.filter(r => r.conclusion && !['success','skipped','cancelled','neutral'].includes(r.conclusion) && r.status==='completed');
  document.getElementById('health-panel-dot').className = 'health-dot ' +
    (!_healthRuns.length ? 'unknown' : failing.length ? 'bad' : 'ok');
  document.getElementById('health-summary-line').textContent =
    _healthRuns._summary || (_healthRuns.length ? `${_healthRuns.length} workflows tracked` : 'No pipeline data yet.');
  document.getElementById('health-checked').textContent =
    _healthRuns._checked ? `Last checked ${_relTime(_healthRuns._checked)}` : '';
  // failing first, then by recency
  const ordered = [..._healthRuns].sort((a,b) => {
    const af = (a.conclusion && a.conclusion!=='success')?0:1;
    const bf = (b.conclusion && b.conclusion!=='success')?0:1;
    if (af!==bf) return af-bf;
    return new Date(b.recorded_at||b.run_started_at) - new Date(a.recorded_at||a.run_started_at);
  });
  const list = document.getElementById('health-run-list');
  if (!ordered.length) { list.innerHTML = '<div class="health-empty">No pipeline runs recorded yet.</div>'; }
  else {
    list.innerHTML = ordered.map(r => {
      let pill='run', word='running';
      if (r.status==='completed') {
        if (r.conclusion==='success') { pill='ok'; word='passed'; }
        else { pill='bad'; word=(r.conclusion||'failed').replace(/_/g,' '); }
      }
      const name = _prettyWf(r.workflow_name);
      const url = r.run_html_url || '';
      const isHttp = /^https?:\/\//i.test(url);
      // data-trusted="1" exempts these real GitHub run URLs from _fixGenericLinks(),
      // which otherwise rewrites "generic" hrefs to a Google search of the link text.
      const nameEl = isHttp
        ? `<a class="health-run-name" href="${url}" target="_blank" rel="noopener noreferrer" data-trusted="1">${name}</a>`
        : `<span class="health-run-name">${name}</span>`;
      return `<div class="health-run">${nameEl}<span class="health-run-pill ${pill}">${word}</span>`
           + `<span class="health-run-time">${_relTime(r.recorded_at||r.run_started_at)}</span></div>`;
    }).join('');
  }
  ov.classList.add('show');
}
function closeHealthPanel() {
  const ov = document.getElementById('health-overlay'); if (ov) ov.classList.remove('show');
}

// ── Next-gen ranking history: written by competitive_scoring.py (enrichment pipeline) ──
// The browser does NOT write to next_gen_rankings. Ranking changes are recorded
// when the pipeline runs and updates drug_competitive_scores — that script also
// writes a snapshot here. The dashboard reads this table to compute movement arrows.
// See scripts/competitive_scoring.py: _write_ranking_snapshot()
function _persistNextGenRankings() { /* no-op — pipeline writes, browser reads */ }

// ── Phase 5 Feature Flags ────────────────────────────────────────────────────
// All flags default false. Flip individually only after validation passes.
// Acceptance criteria and rollback paths: docs/phase5_migration_plan.md
const FEATURE_FLAGS = {
  useNormalizedIBD:       true,   // Candidate 1: ACTIVATED 2026-05-25 — advisor-approved. All 8 gates passed incl. runtime ibd_indication_group_view=compare_pass_oos_adjusted. Rollback: set false.
  useNormalizedTED:       true,   // Candidate 2: ACTIVATED 2026-05-25 — all 8 gates passed incl. runtime ted_indication_group_view=compare_pass_oos_adjusted. Rollback: set false.
  useNormalizedDrugModal: true,   // Candidate 3: ACTIVATED 2026-05-25 — advisor-approved. All 8 gates passed. Labels clean (IL-23p19, EoE, Chronic Urticaria), confidence display correct (95% not 9500%), CIDP evidence verified (reviewed_by kyle-2026-05-25, NCT07188/NCT05581). Rollback: set false.
  useUnifiedTL1A:         true,   // Candidate 4: ACTIVATED 2026-05-25 — all 8 gates passed. drug_targets(target_id='tl1a') replaces drug_areas. count 50→34 (scope-diff drugs correctly excluded). adjusted_match_pct=100, compare_pass_oos_adjusted. Rollback: set false.
  useUnifiedAtopy:        true,   // Candidates 5+6: ACTIVATED 2026-05-26 — advisor go. TSLP adj=100% (14→10, scopeDiff=6), IL-4Rα adj=100% (9→5, scopeDiff=5). compare_pass_oos_adjusted both. drug_targets(target_id IN il4ra,tslp,tslpr) replaces drug_areas. Rollback: set false.
  useUnifiedFCRN:         true,   // Candidate 7: ACTIVATED 2026-05-26 — advisor go. All 8 gates passed. legacy=7 norm=7 overlap=6 scopeDiff=1(atg-201=CD19×CD3) adj=100% compare_pass_oos_adjusted. drug_targets(target_id='fcrn') replaces drug_areas(fcrn). riliprubart added, atg-201 correctly excluded. LEGACY READ LAYER ELIMINATION MILESTONE. Rollback: set false.
};

// ── Tag colour map ──────────────────────────────────────────────────────────
const AREA_TAG = {
  tl1a:  {cls:'stag-tl1a', label:'TL1A'},
  tslp:  {cls:'stag-tslp', label:'TSLP'},
  il4ra: {cls:'stag-il4ra', label:'IL-4Rα'},
  igf1r: {cls:'stag-igf1r', label:'IGF1R'},
  fcrn:  {cls:'stag-fcrn',  label:'FcRn'},
  tcell: {cls:'stag-bcma',  label:'Immune Reset'},
};

// ── Enrichment freshness helper ───────────────────────────────────────────────
function _freshnessBadge(isoDate) {
  if (!isoDate) return '<span class="sc-freshness unknown">not enriched</span>';
  const d = new Date(isoDate);
  const hours = (Date.now() - d.getTime()) / 3600000;
  if (hours < 24) return '<span class="sc-freshness fresh">enriched today</span>';
  const days = Math.floor(hours / 24);
  if (days <= 7)  return `<span class="sc-freshness fresh">${days}d ago</span>`;
  if (days <= 21) return `<span class="sc-freshness recent">${days}d ago</span>`;
  return `<span class="sc-freshness stale">${days}d ago</span>`;
}

// ── Meridian v2 helpers ───────────────────────────────────────────────────────

// Stage progress dots — visual journey indicator for drug cards
function _stageProgressHtml(stage) {
  const stageOrder  = ['preclinical','phase_1','phase_1_2','phase_2','phase_2_3','phase_3','approved'];
  const stageLabels = ['Pre','1','1/2','2','2/3','3','✓'];
  const s = (stage||'').toLowerCase().replace(/ /g,'_');
  let currentIdx = stageOrder.findIndex(k => s === k || s.includes(k.replace('phase_','phase ').replace('_','-')));
  // Fuzzy match: "phase 2" → phase_2, "approved" variants
  if (currentIdx < 0) {
    if (s.includes('preclin')) currentIdx = 0;
    else if (s.includes('phase_1') || s.includes('phase 1')) currentIdx = 1;
    else if (s.includes('phase_2') || s.includes('phase 2')) currentIdx = 3;
    else if (s.includes('phase_3') || s.includes('phase 3')) currentIdx = 5;
    else if (s.includes('approv')) currentIdx = 6;
  }
  if (currentIdx < 0) return `<span style="font-size:11px;color:#8BA3B8;">${stage||'Unknown'}</span>`;
  const dots = stageOrder.map((_, i) => {
    const isApproved = i === 6 && i === currentIdx;
    const cls = isApproved ? 'approved-dot' : i < currentIdx ? 'past' : i === currentIdx ? 'active' : '';
    return `<div class="stage-dot ${cls}" title="${stageLabels[i]}"></div>`;
  }).join('');
  return `<div class="stage-progress" title="${stage}">${dots}<span style="font-size:10px;color:#8BA3B8;margin-left:4px;">${stageLabels[currentIdx]||stage}</span></div>`;
}

// Area status line — removed per Kyle (2026-05-29)
function _areaStatusLine(drugs, areaName, nextCatalystDays) { return ''; }

// ── Intel / Catalysts loader (for future sections) ───────────────────────────
async function sbFetch(table, opts = {}) {
  let q = _sb.from(table).select(opts.select || '*');
  if (opts.eq)    q = q.eq(opts.eq[0], opts.eq[1]);
  if (opts.order) q = q.order(opts.order, { ascending: opts.asc ?? false });
  if (opts.limit) q = q.limit(opts.limit);
  const { data, error } = await q;
  if (error) throw error;
  return data || [];
}

// ── Area label maps ─────────────────────────────────────────────────────────
const AREA_LABELS = {
  tl1a: 'TL1A · IBD', tslp: 'TSLP · Respiratory', il4ra: 'IL-4Rα · Atopy',
  igf1r: 'IGF1R · TED', fcrn: 'FcRn · Autoimmune', tcell: 'T-cell Eng.'
};
// Canonical SHORT target labels — the one source for the briefing/watch/news surfaces
// (the long disease-first AREA_LABELS above and app.js's pairing _AREA_LABEL are
// deliberately different display styles). Loaded before all feature modules.
const AREA_LABELS_SHORT = {
  tl1a: 'TL1A', tslp: 'TSLP', il4ra: 'IL-4Rα', igf1r: 'IGF1R', fcrn: 'FcRn', tcell: 'T-cell', other: 'Other'
};
// ── Portfolio section headers — disease-first labels per tab ─────────────────
const TAB_PORTFOLIO_LABELS = {
  'tl1a':       'IBD Portfolio',
  'tslp':       'Respiratory Portfolio',
  'il4ra-tslp': 'Atopic Disease Portfolio',
  'il4ra':      'Atopic Disease Portfolio',
  'igf1r-tshr': 'TED Portfolio',
  'fcrn':       'Autoimmune Portfolio',
  'ace':        'ALX002 (T-Cell Engager)',
};

// ── Canonical area palette — single source of truth for all panels ────────────
const AREA_COLORS = {
  tl1a:'#1a3f8f', tslp:'#0e7490', il4ra:'#7c3aed',
  igf1r:'#b45309', fcrn:'#15803d', tcell:'#dc2626',
};
const AREA_BG = {
  tl1a:'#eff6ff', tslp:'#ecfeff', il4ra:'#f5f3ff',
  igf1r:'#fffbeb', fcrn:'#f0fdf4', tcell:'#fef2f2',
};

// Extract domain for source attribution links
function _srcDomain(url) {
  if (!url) return 'Source';
  try { return new URL(url).hostname.replace(/^www\./, ''); } catch(e) { return 'Source'; }
}
// Source quality indicators
function _noSrcBadge() {
  return '<span style="font-size:9px;color:#94a3b8;background:#f8fafc;border:1px solid #e2e8f0;padding:1px 5px;border-radius:8px;margin-left:4px;">no source</span>';
}
// Returns a Google News search URL filtered to FierceBiotech and Endpoints — always resolves
function _srcSearch(headline) {
  const q = encodeURIComponent(((headline||'').slice(0,80)) + ' site:fiercebiotech.com OR site:endpointsnews.com');
  return 'https://www.google.com/search?q=' + q;
}
// Renders source link(s): stored URL if present, plus a reliable search fallback
function _srcHtml(url, headline, sz) {
  sz = sz || '9px';
  let h = '';
  if (url) h += `<a href="${url}" target="_blank" rel="noopener" style="font-size:${sz};color:#2563eb;margin-left:4px;">↗ ${_srcDomain(url)}</a>`;
  if (headline) {
    const su = _srcSearch(headline);
    const label = url ? '🔍' : '🔍 find on Fierce/Endpoints';
    const col   = url ? '#cbd5e1' : '#2563eb';
    const ml    = url ? '3px'    : '4px';
    h += `<a href="${su}" target="_blank" rel="noopener" title="Search on FierceBiotech / Endpoints" style="font-size:${sz};color:${col};margin-left:${ml};">${label}</a>`;
  }
  return h || _noSrcBadge();
}
function _impBadge(imp) {
  if (imp === 'high') return '<span style="font-size:9px;font-weight:800;color:#dc2626;background:#fef2f2;border:1px solid #fca5a5;padding:1px 5px;border-radius:8px;margin-right:3px;">HIGH</span>';
  return '';
}

// ── Deal Tracker ─────────────────────────────────────────────────────────────
let _allDeals = [];

function fmtMoney(m) {
  if (!m) return '';
  return m >= 1000 ? `$${(m/1000).toFixed(2).replace(/\.?0+$/,'')}B` : `$${m}M`;
}

function _dedupeDeals(deals) {
  const STOP = new Set(['the','a','an','and','or','of','to','in','for','on','with','by','at','from','is','are','was','were','after','before','as','that','this','it','its','be','been','has','have','had','will','would','could','should','not','but','also','than','more','up','into','about','over','under','pays','per','its','after']);
  function kwds(s) {
    return (s||'').toLowerCase().replace(/[^a-z0-9\s]/g,' ').split(/\s+/).filter(w => w.length > 2 && !STOP.has(w));
  }
  function overlap(a, b) {
    const sa = new Set(a), sb = new Set(b), smaller = Math.min(sa.size, sb.size);
    if (!smaller) return 0;
    let n = 0; sa.forEach(w => { if (sb.has(w)) n++; });
    return n / smaller;
  }
  const kept = [], keptKw = [];
  for (const d of deals) {
    const kw = kwds(d.headline);
    if (!keptKw.some(k => overlap(kw, k) > 0.6)) { kept.push(d); keptKw.push(kw); }
  }
  return kept;
}
function renderDeals(deals) {
  const list = document.getElementById('deals-list');
  if (!list) return;
  deals = _dedupeDeals(deals);
  if (!deals.length) { list.innerHTML = '<div style="padding:20px;color:#94a3b8;font-size:12px;text-align:center;">No deals found.</div>'; return; }
  const renderDeal = (d, idx) => {
    const val       = fmtMoney(d.total_usd_m);
    const areaColor = AREA_COLORS[d.area_id] || '#64748b';
    const areaLabel = AREA_LABELS[d.area_id] || d.area_id || '';
    const dateStr   = rdtFmtDate(d.deal_date) || d.deal_date_label || '';
    const headline  = d.headline || `${d.from_company||''} / ${d.to_company||''} deal`;
    const gLink     = d.source_url || ''; // direct source only — no Google fallback (Kyle 2026-06-08)
    const parties   = [d.from_company, d.to_company].filter(Boolean).join(' → ');
    const cardId    = `deal-card-${idx}`;
    // Expandable body content
    const bodyParts = [];
    if (d.detail)        bodyParts.push(`<div class="deal-card-detail">${d.detail}</div>`);
    if (d.upfront_usd_m) bodyParts.push(`<div class="deal-card-upfront">💰 ${fmtMoney(d.upfront_usd_m)} upfront</div>`);
    if (d.ailux_signal)  bodyParts.push(`<div class="deal-card-ailux"><strong>Ailux lens:</strong> ${d.ailux_signal}</div>`);
    const hasBody = bodyParts.length > 0;
    return `<div class="deal-card" id="${cardId}" data-area="${d.area_id||''}">
  <div class="deal-card-hd" onclick="${hasBody ? `toggleDealCard('${cardId}')` : ''}">
    <div class="deal-card-meta">
      ${dateStr ? `<span class="deal-date-badge">📅 ${dateStr}</span>` : ''}
      ${areaLabel ? `<span class="deal-area-pill" style="background:${areaColor}">${areaLabel}</span>` : ''}
      ${val ? `<span class="deal-card-val">${val}</span>` : ''}
    </div>
    <div class="deal-card-title-row">
      ${gLink ? `<a class="deal-title-link" href="${gLink}" target="_blank" rel="noopener" onclick="event.stopPropagation()">${headline}</a>` : `<span class="deal-title-link" style="cursor:default">${headline}</span>`}
      ${hasBody ? `<button class="deal-chevron-btn" onclick="event.stopPropagation();toggleDealCard('${cardId}')">▾</button>` : ''}
    </div>
    ${parties ? `<div class="deal-parties">${parties}</div>` : ''}
  </div>
  ${hasBody ? `<div class="deal-card-body">${bodyParts.join('')}</div>` : ''}
</div>`;
  };
  list.innerHTML = deals.map(renderDeal).join('');
}
function toggleDealCard(id) {
  const card = document.getElementById(id);
  if (card) card.classList.toggle('open');
}

async function loadDeals() {
  const list = document.getElementById('deals-list');
  if (!list) return;
  try {
    const { data, error } = await _sb.from('deals').select('*').order('deal_date', { ascending: false });
    if (error) throw error;
    _allDeals = data || [];
    renderDeals(_allDeals);
  } catch(err) {
    list.innerHTML = `<div style="padding:16px;color:#dc2626;font-size:12px;">Error loading deals: ${err.message}</div>`;
  }
}

function dealFilter(btn, area) {
  document.querySelectorAll('.deal-filter-bar .deal-pill').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const filtered = area ? _allDeals.filter(d => d.area_id === area) : _allDeals;
  renderDeals(filtered);
}

// ── Catalysts & Signals — Unified Feed ───────────────────────────────────────
let _allCatalysts = []; // raw catalyst rows (backward compat)
let _allUnified   = []; // merged unified feed
let _uniTypeFilter = '';
let _uniAreaFilter = '';
let _uniVisible    = 8;   // items shown; grows by 8 on each "Load more" click

const SIG_ORDER = { high: 0, medium: 1, low: 2 };

const UNI_TYPE_STYLE = {
  readout:         { label:'Readout',       bg:'#eff6ff', color:'#1d4ed8' },
  filing:          { label:'Filing',        bg:'#f0fdf4', color:'#15803d' },
  approval:        { label:'Approval',      bg:'#dcfce7', color:'#166534' },
  conference:      { label:'Conference',    bg:'#faf5ff', color:'#6d28d9' },
  deal:            { label:'Deal',          bg:'#ecfdf5', color:'#047857' },
  trial_update:    { label:'Trial Update',  bg:'#f0fdf4', color:'#15803d' },
  press_release:   { label:'Press Release', bg:'#eff6ff', color:'#1d4ed8' },
  fda:             { label:'FDA',           bg:'#fef2f2', color:'#b91c1c' },
  pipeline_change: { label:'Pipeline',      bg:'#fff7ed', color:'#c2410c' },
  abstract:        { label:'Abstract',      bg:'#faf5ff', color:'#6d28d9' },
  financing:       { label:'Financing',     bg:'#ecfdf5', color:'#047857' },
  intel:           { label:'Intel',         bg:'#f1f5f9', color:'#475569' },
};

// Shared query cleaner: takes a headline → returns a short, findable Google query.
// Google fails on long exact phrases (>8 words). Strategy: take the most meaningful
// first clause, keep drug names/numbers, truncate to 7 words, drop trailing filler.
function _buildGQuery(text) {
  let s = (text || '').replace(/^[↗→·•\s]+/, '').trim();
  // Split at first semicolon or " - " / em-dash to get the primary clause
  s = s.split(/[;—]|(?:\s+[-–]\s+)/)[0].trim();
  // Replace punctuation (commas, colons, parens, etc.) with spaces — keep numbers & drug names
  s = s.replace(/[,;:!?'"()\[\]{}]+/g, ' ').replace(/\s+/g, ' ').trim();
  // Truncate to 7 words
  let words = s.split(/\s+/);
  words = words.slice(0, 7);
  // Drop trailing weak stop/filler words so we don't end on "at" "in" "a" etc.
  const stops = new Set(['at','in','on','the','a','an','of','for','to','and','or','but','with','by','from','as','after','into','per','via','vs','its']);
  while (words.length > 3 && stops.has(words[words.length - 1].toLowerCase())) words.pop();
  return words.join(' ');
}
function _gUrl(text) {
  const q = _buildGQuery(text);
  return 'https://www.google.com/search?q=' + encodeURIComponent(q);
}

function uniTypeFilter(btn, type) {
  document.querySelectorAll('#uni-type-bar .uni-pill').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  _uniTypeFilter = type;
  _uniVisible = 8;
  _applyUniFilters();
}
function uniAreaFilter(btn, area) {
  document.querySelectorAll('#uni-area-bar .uni-pill').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  _uniAreaFilter = area;
  _uniVisible = 8;
  _applyUniFilters();
}
function _applyUniFilters() {
  let items = [..._allUnified];
  if (_uniTypeFilter) items = items.filter(i => i.catType === _uniTypeFilter);
  if (_uniAreaFilter) items = items.filter(i => i.area_id === _uniAreaFilter);
  renderCatalysts(items);
}

function renderCatalysts(items) {
  const list = document.getElementById('catalysts-list');
  if (!list) return;
  if (!items.length) {
    list.innerHTML = '<div style="padding:20px;color:#94a3b8;font-size:12px;text-align:center;">No items match your filters.</div>';
    return;
  }

  const fmtDate = (sd) => {
    if (!sd) return '';
    try {
      const [y, m, d] = sd.split('-').map(Number);
      const mn = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][m-1]||'';
      if (!d || d === 1 || d === 15) return `${mn} ${y}`;
      return `${mn} ${d}`;
    } catch(e) { return sd; }
  };

  const renderItem = (item) => {
    const ts   = UNI_TYPE_STYLE[item.catType] || { label: item.catType || 'Update', bg:'#f8fafc', color:'#64748b' };
    const area = AREA_LABELS[item.area_id] || '';
    const areaColor = AREA_COLORS[item.area_id] || '#64748b';
    const areaBg    = AREA_BG[item.area_id]    || '#f1f5f9';
    const areaPill  = area ? `<span class="uni-type-pill" style="background:${areaBg};color:${areaColor};">${area}</span>` : '';
    const typePill  = `<span class="uni-type-pill" style="background:${ts.bg};color:${ts.color};">${ts.label}</span>`;
    const countdown = item.srcType === 'catalyst' && !item.resolved ? catDaysTag(item.sortDate) : '';
    const dateStr   = fmtDate(item.sortDate);
    const isHigh    = item.significance === 'high';
    const opacity   = item.resolved ? 'opacity:0.45;' : '';
    const gLink     = item.source_url || ''; // direct source only — no Google fallback (Kyle 2026-06-08)

    return `<div class="uni-item${isHigh ? ' sig-high' : ''}" style="${opacity}">
  <div class="uni-meta">
    ${typePill}${areaPill}
    ${countdown}
    <span class="uni-date">${dateStr}</span>
  </div>
  ${gLink ? `<a class="uni-headline" href="${gLink}" target="_blank" rel="noopener">${item.label}</a>` : `<span class="uni-headline" style="cursor:default">${item.label}</span>`}
  ${item.notes ? `<div class="uni-notes">${item.notes}</div>` : ''}
  ${item.resolved && item.resolved_note ? `<div style="font-size:10px;color:#16a34a;margin-top:3px;">✓ ${item.resolved_note}</div>` : ''}
</div>`;
  };

  // Sort: upcoming catalysts (soonest first) at top; recent signals/intel/deals (newest first) below
  const today = new Date().toISOString().split('T')[0];
  const open = items.filter(i => !i.resolved).sort((a, b) => {
    const aUpcoming = a.srcType === 'catalyst' && (a.sortDate || '9999') >= today;
    const bUpcoming = b.srcType === 'catalyst' && (b.sortDate || '9999') >= today;
    // Upcoming catalysts always before non-upcoming items
    if (aUpcoming && !bUpcoming) return -1;
    if (!aUpcoming && bUpcoming) return 1;
    if (aUpcoming && bUpcoming) {
      // Among upcoming catalysts: soonest date first, tie-break by significance
      const dateCmp = (a.sortDate||'9999').localeCompare(b.sortDate||'9999');
      if (dateCmp !== 0) return dateCmp;
      return (SIG_ORDER[a.significance]??1) - (SIG_ORDER[b.significance]??1);
    }
    // Among recent events (signals/intel/deals): most recent first
    return (b.sortDate||'0').localeCompare(a.sortDate||'0');
  });
  const resolved = items.filter(i => i.resolved);

  const BATCH  = 8;
  const toShow = open.slice(0, _uniVisible);
  const remaining = open.length - _uniVisible;

  let html = toShow.map(renderItem).join('');
  if (remaining > 0) {
    const nextBatch = Math.min(BATCH, remaining);
    html += `<button onclick="_uniVisible+=${BATCH};_applyUniFilters()" style="width:100%;margin:8px 0 4px;padding:7px 0;font-size:11px;font-weight:600;color:#1e4a82;background:#f0f6ff;border:1.5px solid #bfdbfe;border-radius:8px;cursor:pointer;">Load ${nextBatch} more &nbsp;·&nbsp; ${remaining} remaining ↓</button>`;
  }
  if (resolved.length) {
    html += `<div class="uni-section-hd">Resolved</div>` + resolved.map(renderItem).join('');
  }

  list.innerHTML = html;
}

// Paginated fetch — PostgREST caps each response at 1000 rows; loop .range() until exhausted.
async function _sbFetchAll(builderFn, pageSize = 1000) {
  let out = [], from = 0;
  while (true) {
    const { data, error } = await builderFn(from, from + pageSize - 1);
    if (error) throw error;
    out = out.concat(data || []);
    if (!data || data.length < pageSize) break;
    from += pageSize;
  }
  return out;
}

async function loadCatalysts() {
  const list = document.getElementById('catalysts-list');
  if (!list) return;
  try {
    // catalysts exceed the 1000-row cap → paginate (was silently truncated)
    const catsRes = { data: await _sbFetchAll((f, t) =>
      _sb.from('catalysts').select('*').order('sort_date', { ascending: true }).range(f, t)) };
    const [sigsRes, intelRes, dealsRes] = await Promise.all([
      _sb.from('signals').select('*,companies(name)')
          .order('event_date', { ascending: false }).limit(500),
      _sb.from('intel').select('id,headline,summary:body,intel_date,importance,source_url')
          .order('intel_date', { ascending: false }).limit(500),
      _sb.from('deals').select('*').order('deal_date', { ascending: false }).limit(100),
    ]);
    if (catsRes.error) throw catsRes.error;

    const unified = [];

    // ── Catalysts ──────────────────────────────────────────────────────────
    (catsRes.data || []).forEach(c => unified.push({
      srcType:    'catalyst',
      catType:    c.catalyst_type || 'readout',
      label:      c.label || '',
      notes:      c.notes || '',
      area_id:    c.area_id || '',
      sortDate:   c.sort_date || '',
      significance: c.significance || 'medium',
      resolved:   c.resolved || false,
      resolved_note: c.resolved_note || '',
      is_key_watch:  c.is_key_watch || false,
    }));

    // ── Signals (last 7d, relevance-scored) ────────────────────────────────
    (sigsRes.data || []).forEach(s => unified.push({
      srcType:    'signal',
      catType:    s.signal_type || 'press_release',
      label:      s.headline || '',
      notes:      [s.companies?.name, s.ailux_angle].filter(Boolean).join(' · '),
      area_id:    s.area_id || '',
      sortDate:   s.event_date || '',
      significance: (s.relevance_score||0) >= 8 ? 'high' : (s.relevance_score||0) >= 6 ? 'medium' : 'low',
      resolved:   false,
    }));

    // ── High-importance Intel ──────────────────────────────────────────────
    (intelRes.data || []).forEach(i => unified.push({
      srcType:    'intel',
      catType:    'intel',
      label:      i.headline || '',
      notes:      i.ailux_angle || i.summary || '',
      area_id:    i.area_id || '',
      sortDate:   i.intel_date || '',
      significance: 'high',
      resolved:   false,
    }));

    // ── Recent deals with BD signal ────────────────────────────────────────
    const deals = dealsRes.data || [];
    deals.filter(d => d.ailux_signal).slice(0, 5).forEach(d => unified.push({
      srcType:    'deal',
      catType:    'deal',
      label:      d.headline || `${d.from_company||''} → ${d.to_company||''}`,
      notes:      d.ailux_signal || (d.total_usd_m ? fmtMoney(d.total_usd_m) : ''),
      area_id:    d.area_id || '',
      sortDate:   d.deal_date || '',
      significance: 'medium',
      resolved:   false,
    }));

    _allCatalysts = catsRes.data || [];
    _allUnified   = unified;
    renderCatalysts(unified);
  } catch(err) {
    if (list) list.innerHTML = `<div style="padding:16px;color:#dc2626;font-size:12px;">Error loading: ${err.message}</div>`;
  }
}

// ── Catalyst countdown helper ─────────────────────────────────────────────────
function catDaysTag(sortDate) {
  if (!sortDate) return '';
  const today = new Date(); today.setHours(0,0,0,0);
  const target = new Date(sortDate); target.setHours(0,0,0,0);
  const diff = Math.round((target - today) / (1000 * 60 * 60 * 24));
  if (diff === 0)
    return `<span style="font-size:9px;font-weight:800;background:#dc2626;color:white;padding:2px 7px;border-radius:8px;margin-left:4px;">TODAY</span>`;
  if (diff > 0 && diff <= 7)
    return `<span style="font-size:9px;font-weight:800;background:#fef2f2;color:#dc2626;border:1px solid #fca5a5;padding:2px 7px;border-radius:8px;margin-left:4px;">${diff}d</span>`;
  if (diff > 0 && diff <= 30)
    return `<span style="font-size:9px;font-weight:700;background:#fffbeb;color:#d97706;border:1px solid #fde68a;padding:2px 7px;border-radius:8px;margin-left:4px;">${diff}d</span>`;
  if (diff > 0)
    return `<span style="font-size:9px;color:#64748b;background:#f1f5f9;border:1px solid #e2e8f0;padding:2px 7px;border-radius:8px;margin-left:4px;">${diff}d</span>`;
  return `<span style="font-size:9px;color:#94a3b8;background:#f8fafc;padding:2px 7px;border-radius:8px;margin-left:4px;">${Math.abs(diff)}d ago</span>`;
}

// ── Meridian Reader — live essential intel ────────────────────────────────────
const MR_AREA_STYLE = {
  tl1a:        { label:'IBD',          color:'#1a3f8f', bg:'#eff6ff' },
  tslp:        { label:'Resp',         color:'#0e7490', bg:'#ecfeff' },
  il4ra:       { label:'Type 2',       color:'#7c3aed', bg:'#f5f3ff' },
  il4ra_tslp:  { label:'Type 2',       color:'#7c3aed', bg:'#f5f3ff' },
  il4ra_ox40l: { label:'Type 2',       color:'#7c3aed', bg:'#f5f3ff' },
  igf1r:       { label:'TED',          color:'#b45309', bg:'#fffbeb' },
  fcrn:        { label:'FcRn',         color:'#15803d', bg:'#f0fdf4' },
  tcell:       { label:'Immune Reset', color:'#dc2626', bg:'#fef2f2' },
  ace:         { label:'Immune Reset', color:'#dc2626', bg:'#fef2f2' },
};
const MR_TYPE_STYLE = {
  deal:       { label:'Deal',     color:'#1d4ed8', bg:'#dbeafe' },
  clinical:   { label:'Clinical', color:'#c45b11', bg:'#fff7ed' },
  regulatory: { label:'Reg',      color:'#065f46', bg:'#f0fdf4' },
  news:       { label:'News',     color:'#475569', bg:'#f1f5f9' },
  conference: { label:'Conf',     color:'#5b21b6', bg:'#f5f3ff' },
};

async function loadMeridianReader() {
  const container = document.getElementById('meridian-reader-items');
  if (!container || !_sb) return;
  try {
    const [intelRes, iaRes, dealsRes, catsRes, profilesRes] = await Promise.all([
      _sb.from('intel')
        .select('id,intel_date,headline,body,source_url,source_name,intel_type,importance,primary_company_id')
        .in('importance', ['high', 'medium'])
        .order('intel_date', { ascending: false })
        .limit(40),
      _sb.from('intel_areas').select('intel_id,area_id,target_id,context_type'),
      _sb.from('deals')
        .select('id,deal_date,deal_date_label,from_company,to_company,headline,area_id,total_usd_m,upfront_usd_m,source_url')
        .order('deal_date', { ascending: false })
        .limit(15),
      _sb.from('catalysts')
        .select('id,catalyst_date,sort_date,label,area_id,significance,catalyst_type,notes,source_url')
        .eq('resolved', false)
        .order('sort_date', { ascending: true })
        .limit(20),
      _sb.from('company_profiles')
        .select('company_id,area_id,platform_summary,why_it_matters,last_enriched_at')
        .not('last_enriched_at', 'is', null)
        .order('last_enriched_at', { ascending: false })
        .limit(8),
    ]);

    const areaMap = {};
    (iaRes.data || []).forEach(r => { if (!areaMap[r.intel_id]) areaMap[r.intel_id] = r.area_id; });

    const feed = [];
    const _impRank = { high: 2, medium: 1, low: 0 };

    // ── Intel items ────────────────────────────────────────────────────────
    const intelGroups = new Map();
    (intelRes.data || []).forEach(item => {
      const storyKey = item.primary_company_id
        ? `${item.primary_company_id}|${item.intel_date||''}|${item.intel_type||''}`
        : `_solo_${item.id}`;
      if (!intelGroups.has(storyKey)) intelGroups.set(storyKey, []);
      intelGroups.get(storyKey).push(item);
    });

    intelGroups.forEach(group => {
      group.sort((a, b) => (_impRank[b.importance] || 0) - (_impRank[a.importance] || 0));
      const item   = group[0];
      const extras = group.slice(1);
      const areaId = areaMap[item.id] || '';
      const aStyle = MR_AREA_STYLE[areaId];
      const tStyle = MR_TYPE_STYLE[item.intel_type];
      const areaPill = aStyle ? `<span class="mr-pill" style="color:${aStyle.color};background:${aStyle.bg}">${aStyle.label}</span>` : '';
      const typePill = tStyle ? `<span class="mr-pill" style="color:${tStyle.color};background:${tStyle.bg}">${tStyle.label}</span>` : '';
      const impPill  = item.importance === 'high' ? `<span class="mr-pill" style="color:#b91c1c;background:#fef2f2">High</span>` : '';
      const hl = item.headline || '';
      const bodyParts = [];
      if (item.body) bodyParts.push(`<div>${item.body}</div>`);
      if (extras.length) {
        const extraLinks = extras.map(e => {
          if (!e.source_url) return `<div style="color:#64748b;padding:1px 0">• ${e.headline || 'related item'}</div>`;
          return `<a href="${e.source_url}" target="_blank" rel="noopener" style="color:#2563eb;display:block;padding:1px 0;text-decoration:none;">↗ ${e.headline || _srcDomain(e.source_url) || 'source'}</a>`;
        }).join('');
        bodyParts.push(`<div style="margin-top:6px;padding-top:6px;border-top:1px solid #e2e8f0;font-size:11px">${extraLinks}</div>`);
      }
      feed.push({
        sortScore: (item.importance === 'high' ? 100 : 50) + new Date(item.intel_date || 0).getTime() / 1e13,
        dateStr:   item.intel_date || '',
        dateLabel: rdtFmtDate(item.intel_date) || item.intel_date || '',
        type: 'intel', areaId,
        pills: areaPill + typePill + impPill,
        headline: hl,
        hlUrl: item.source_url || '',   // direct source only — no Google fallback (Kyle 2026-06-08)
        body: bodyParts.join(''),
        countdown: '',
      });
    });

    // ── Deal items ─────────────────────────────────────────────────────────
    (dealsRes.data || []).forEach(d => {
      // Skip incomplete deals — must have a real counterparty OR a descriptive headline
      const hasCounterparty = d.to_company && d.to_company.trim();
      const hasHeadline     = d.headline    && d.headline.trim();
      if (!hasCounterparty && !hasHeadline) return;

      const aStyle = MR_AREA_STYLE[d.area_id];
      const areaPill = aStyle ? `<span class="mr-pill" style="color:${aStyle.color};background:${aStyle.bg}">${aStyle.label}</span>` : '';
      const dealPill = `<span class="mr-pill" style="color:#1d4ed8;background:#dbeafe">Deal</span>`;
      const val = d.total_usd_m ? ` · ${fmtMoney(d.total_usd_m)}` : '';
      // Headline: if we have both parties show the arrow format; if only from_company use the DB headline
      const hl = hasCounterparty
        ? `${d.from_company || '—'} → ${d.to_company}${val}`
        : (d.headline || `${d.from_company || '—'} deal`);
      const bodyParts = [];
      if (d.headline && hasCounterparty) bodyParts.push(`<div>${d.headline}</div>`);
      if (d.upfront_usd_m) bodyParts.push(`<div style="color:#64748b;margin-top:3px">${fmtMoney(d.upfront_usd_m)} upfront</div>`);
      // Build a meaningful search query from the deal
      const searchTerms = [d.from_company, d.to_company, 'deal', d.total_usd_m ? fmtMoney(d.total_usd_m) : ''].filter(Boolean).join(' ');
      feed.push({
        sortScore: 80 + new Date(d.deal_date || 0).getTime() / 1e13,
        dateStr:   d.deal_date || '',
        dateLabel: rdtFmtDate(d.deal_date) || d.deal_date_label || '',
        type: 'deal', areaId: d.area_id || '',
        pills: areaPill + dealPill,
        headline: hl,
        hlUrl: d.source_url || '',
        body: bodyParts.join(''),
        countdown: '',
      });
    });

    // ── Catalyst items ─────────────────────────────────────────────────────
    (catsRes.data || []).slice(0, 12).forEach(c => {
      if (!c.label) return;
      const aStyle = MR_AREA_STYLE[c.area_id];
      const areaPill = aStyle ? `<span class="mr-pill" style="color:${aStyle.color};background:${aStyle.bg}">${aStyle.label}</span>` : '';
      const catPill  = `<span class="mr-pill" style="color:#c45b11;background:#fff7ed">Catalyst</span>`;
      const bodyParts = c.notes ? [`<div>${c.notes}</div>`] : [];
      const sigScore  = c.significance === 'high' ? 70 : c.significance === 'medium' ? 40 : 20;
      feed.push({
        sortScore: sigScore - new Date(c.sort_date || '9999-12-31').getTime() / 1e13,
        dateStr:   c.sort_date || '',
        dateLabel: c.catalyst_date || c.sort_date || '',
        type: 'catalyst', areaId: c.area_id || '',
        pills: areaPill + catPill,
        headline: c.label,
        hlUrl: c.source_url || '',
        body: bodyParts.join(''),
        countdown: catDaysTag(c.sort_date),
      });
    });

    // ── Enrichment items ───────────────────────────────────────────────────
    const today = new Date().toISOString().split('T')[0];
    (profilesRes.data || []).forEach(p => {
      if (!p.last_enriched_at) return;
      const enrichedDate = p.last_enriched_at.split('T')[0];
      if (enrichedDate !== today) return;
      const aStyle = MR_AREA_STYLE[p.area_id];
      const areaPill  = aStyle ? `<span class="mr-pill" style="color:${aStyle.color};background:${aStyle.bg}">${aStyle.label}</span>` : '';
      const enrichPill = `<span class="mr-pill" style="color:#6d28d9;background:#ede9fe">Enriched</span>`;
      const summary = p.why_it_matters || p.platform_summary || '';
      feed.push({
        sortScore: 30,
        dateStr:   enrichedDate,
        dateLabel: rdtFmtDate(enrichedDate) || enrichedDate,
        type: 'enriched', areaId: p.area_id || '',
        pills: areaPill + enrichPill,
        headline: `${p.company_id} profile updated`,
        hlUrl: '', coId: p.company_id || '',   // opens the company card in-app, not Google
        body: summary ? summary.slice(0, 220) + (summary.length > 220 ? '…' : '') : '',
        countdown: '',
      });
    });

    if (!feed.length) {
      container.innerHTML = '<div style="padding:20px;text-align:center;color:#94a3b8;font-size:12px;">No essential intel yet — check back after the next Meridian run.</div>';
      return;
    }

    feed.sort((a, b) => b.sortScore - a.sortScore);
    _mrFeed = feed;
    renderMeridianFeed();

  } catch(e) {
    console.error('loadMeridianReader', e);
    container.innerHTML = '<div style="color:#94a3b8;font-size:12px;padding:16px;">Intel feed unavailable.</div>';
  }
}


// ── Essential Updates — state + render + filter + toggle ─────────────────────
let _mrFeed       = [];
let _mrTypeFilter = '';
let _mrAreaFilter = '';

function renderMeridianFeed() {
  const container = document.getElementById('meridian-reader-items');
  if (!container) return;
  let items = _mrFeed;
  if (_mrTypeFilter) items = items.filter(f => f.type === _mrTypeFilter);
  if (_mrAreaFilter) items = items.filter(f => f.areaId === _mrAreaFilter);
  if (!items.length) {
    container.innerHTML = '<div style="padding:20px;text-align:center;color:#94a3b8;font-size:12px;">No updates match these filters.</div>';
    return;
  }
  container.innerHTML = items.map(f => {
    const hasBody = !!f.body;
    const chev = `<span class="mr-chev" style="${hasBody?'':'visibility:hidden'}">▶</span>`;
    const bodyBlock = hasBody ? `<div class="mr-body" style="display:none">${f.body}</div>` : '';
    // headline: direct source link if we have one; else open the company card in-app; else plain text.
    // No Google-search fallback (Kyle 2026-06-08).
    const headlineEl = f.hlUrl
      ? `<a class="mr-hl" href="${f.hlUrl}" target="_blank" rel="noopener" onclick="event.stopPropagation()">${f.headline}</a>`
      : (f.coId
        ? `<a class="mr-hl" href="javascript:void(0)" onclick="event.stopPropagation();openCompanyEntityModal('${(f.coId||'').replace(/'/g,"\\'")}','${(f.coId||'').replace(/'/g,"\\'")}','home')">${f.headline}</a>`
        : `<span class="mr-hl" style="cursor:default">${f.headline}</span>`);
    return `<div class="mr-item" data-type="${f.type}" data-area="${f.areaId}">
  <div class="mr-item-hd" onclick="mrToggle(this)">
    ${chev}
    <div class="mr-pills">${f.pills}</div>
    ${headlineEl}
    ${f.countdown || ''}
    <span class="mr-date-tag">${f.dateLabel}</span>
  </div>
  ${bodyBlock}
</div>`;
  }).join('');
}

function mrTypeFilter(btn, type) {
  document.querySelectorAll('#mr-type-bar .mr-pill-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  _mrTypeFilter = type;
  renderMeridianFeed();
}
function mrAreaFilter(btn, area) {
  document.querySelectorAll('#mr-area-bar .mr-pill-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  _mrAreaFilter = area;
  renderMeridianFeed();
}
function mrToggle(hd) {
  const item = hd.closest('.mr-item');
  if (!item) return;
  const body = item.querySelector('.mr-body');
  if (!body) return;
  const isOpen = body.style.display === 'block';
  body.style.display = isOpen ? 'none' : 'block';
  item.classList.toggle('mr-open', !isOpen);
}

// ── Missing fields: stage grouping map ───────────────────────────────────────
const _STAGE_PREFIX = [
  { key:'s2', label:'Stage 2 · Drug Mapping',      match: f => /^drug:.*:(target|mechanism|differentiation_thesis)$/.test(f) },
  { key:'s3', label:'Stage 3 · Trial Intelligence', match: f => /^drug:.*:(has_trials|trial_)/.test(f) },
  { key:'s4', label:'Stage 4 · Catalysts',          match: f => f === 'catalysts_list' },
  { key:'s5', label:'Stage 5 · Strategic Position', match: f => ['company_profile_exists','competitive_position','vs_ailux','key_differentiators'].includes(f) },
  { key:'s6', label:'Stage 6 · Deal Intelligence',  match: f => f === 'deals_list' },
];
function _humanField(f) {
  if (f.startsWith('drug:')) {
    const parts = f.split(':');
    const drug = parts[1]; const field = parts.slice(2).join(':');
    const fieldLabel = field.replace(/_/g,' ').replace('differentiation thesis','diff. thesis').replace('canonical linked','canonical link');
    return `${drug}:${fieldLabel}`;
  }
  return f.replace(/_/g,' ');
}
function _groupMissingFields(missingArr) {
  if (!missingArr || !missingArr.length) return [];
  const groups = {};
  missingArr.forEach(f => {
    const stage = _STAGE_PREFIX.find(s => s.match(f));
    const key = stage ? stage.key : 'other';
    const label = stage ? stage.label : 'Other';
    if (!groups[key]) groups[key] = { label, fields:[] };
    groups[key].fields.push(f);
  });
  return Object.values(groups);
}


// Area color map shared across queue + badges
const _AREA_PILL_COLORS = {
  tl1a:  { bg:'#1a3f8f', text:'white' },
  tslp:  { bg:'#0e7490', text:'white' },
  il4ra: { bg:'#7c3aed', text:'white' },
  igf1r: { bg:'#b45309', text:'white' },
  fcrn:  { bg:'#15803d', text:'white' },
  tcell: { bg:'#dc2626', text:'white' },
};
const _AREA_SHORT = { tl1a:'TL1A', tslp:'TSLP', il4ra:'IL-4Rα', igf1r:'IGF1R', fcrn:'FcRn', tcell:'T-cell' };


// ── Identity Health Panel ────────────────────────────────────────────────────
async function loadIdentityHealth() {
  const body = document.getElementById('ih-body');
  if (!body) return;
  body.innerHTML = '<div style="color:#94a3b8;font-size:12px">Loading…</div>';
  try {
    // 1. Drug coverage: total vs resolved
    const [drugsRes, canonRes, fuzzyRes, orphanRes, errRes] = await Promise.all([
      _sb.from('drugs').select('canonical_drug_id', { count: 'exact', head: false }),
      _sb.from('canonical_drugs').select('canonical_id,is_active', { count: 'exact', head: false }),
      _sb.from('identity_audit_log').select('id', { count: 'exact' }).eq('operation', 'flag_review'),
      _sb.rpc ? null : null, // placeholder
      _sb.from('resolver_errors').select('id', { count: 'exact' }).is('resolved_at', null),
    ]);

    const total     = (drugsRes.data || []).length;
    const resolved  = (drugsRes.data || []).filter(d => d.canonical_drug_id).length;
    const coverage  = total > 0 ? Math.round((resolved / total) * 100) : 0;
    const active    = (canonRes.data || []).filter(d => d.is_active).length;
    const fuzzy     = fuzzyRes.count ?? (fuzzyRes.data || []).length;
    const unresErrs = errRes.count  ?? (errRes.data  || []).length;

    // unresolved: drugs with no canonical_drug_id set at all
    const unresolved = total - resolved;
    // true FK orphans: drugs whose canonical_drug_id points to a non-existent canonical
    const canonIds = new Set((canonRes.data || []).map(c => c.canonical_id).filter(Boolean));
    const orphanCount = (drugsRes.data || []).filter(d => d.canonical_drug_id && !canonIds.has(d.canonical_drug_id)).length;

    const stat = (val, label, okIf) => {
      const cls = okIf(val) ? 'ok' : (val === 0 ? 'ok' : 'bad');
      return `<div class="ih-stat ${cls}"><div class="ih-stat-val">${val}</div><div class="ih-stat-lbl">${label}</div></div>`;
    };

    const coverageCls = coverage === 100 ? 'ok' : coverage >= 90 ? 'warn' : 'bad';
    const coverageHtml = `<div class="ih-stat ${coverageCls}"><div class="ih-stat-val">${coverage}%</div><div class="ih-stat-lbl">Canonical Coverage</div></div>`;

    const issues = [];
    if (coverage < 100) issues.push(`${unresolved} drug${unresolved !== 1 ? 's' : ''} unresolved`);
    if (orphanCount > 0) issues.push(`${orphanCount} FK orphan${orphanCount !== 1 ? 's' : ''} (broken reference)`);
    if (fuzzy > 0)      issues.push(`${fuzzy} fuzzy match${fuzzy !== 1 ? 'es' : ''} need review`);
    if (unresErrs > 0)  issues.push(`${unresErrs} resolver error${unresErrs !== 1 ? 's' : ''} unretried`);

    body.innerHTML = `
      ${coverageHtml}
      <div class="ih-divider"></div>
      ${stat(active, 'Active Canonicals', v => v > 0)}
      <div class="ih-divider"></div>
      ${stat(orphanCount, 'FK Orphans', v => v === 0)}
      <div class="ih-divider"></div>
      ${stat(fuzzy, 'Fuzzy Pending', v => v === 0)}
      <div class="ih-divider"></div>
      ${stat(unresErrs, 'Resolver Errors', v => v === 0)}
      ${issues.length ? `<div class="ih-issue" style="margin-top:6px">⚠ ${issues.join(' · ')}</div>` : '<div class="ih-issue" style="color:#16a34a;margin-top:6px">✅ All checks passing</div>'}
    `;
  } catch(e) {
    body.innerHTML = '<div style="color:#ef4444;font-size:12px">Error loading health data.</div>';
  }
}

// ── Governance Violations Widget ──────────────────────────────────────────────
// Fetches open governance_violations and injects a badge into the footer + populates
// the #gov-violations-mount element in the Architecture tab if present.
async function loadGovernanceViolations() {
  try {
    const { data: govViolations } = await _sb
      .from('governance_violations')
      .select('rule_name, row_id, table_name, description, detected_at')
      .eq('resolved', false)
      .order('detected_at', { ascending: false })
      .limit(20);
    const _vCount = (govViolations || []).length;

    // Inject badge next to identity footer if violations exist
    const _govBadgeEl = document.getElementById('idf-gov-badge');
    if (_govBadgeEl) {
      _govBadgeEl.textContent = _vCount > 0 ? ` · ${_vCount} governance violation${_vCount!==1?'s':''}` : '';
      _govBadgeEl.style.color = _vCount > 0 ? '#b91c1c' : '';
    }

    // Populate governance violations mount in Architecture tab (if present)
    const _govMount = document.getElementById('gov-violations-mount');
    if (_govMount) {
      if (!_vCount) {
        _govMount.innerHTML = '<div style="color:#15803d;font-size:12px;padding:8px 0">✅ No open governance violations.</div>';
      } else {
        _govMount.innerHTML = `
          <div style="margin-bottom:8px;display:flex;align-items:center;gap:8px">
            <span style="font-size:11px;font-weight:700;color:#b91c1c">${_vCount} open violation${_vCount!==1?'s':''}</span>
            <span style="font-size:10px;color:#94a3b8">— resolve in Supabase or via scripts/apply_governance_violations.py</span>
          </div>
          ${(govViolations||[]).map(v => `<div style="display:flex;gap:8px;align-items:flex-start;padding:6px 0;border-bottom:1px solid #fee2e2">
            <span style="font-size:8px;font-weight:800;text-transform:uppercase;background:#fef2f2;color:#b91c1c;border:1px solid #fecaca;border-radius:4px;padding:1px 5px;flex-shrink:0;white-space:nowrap">${(v.rule_name||'').replace(/_/g,' ')}</span>
            <div style="flex:1;min-width:0">
              <div style="font-size:11px;font-weight:600;color:#1e293b">${v.row_id||'—'} <span style="font-weight:400;color:#64748b">(${v.table_name||'—'})</span></div>
              <div style="font-size:10.5px;color:#475569;margin-top:1px">${v.description||''}</div>
            </div>
            <span style="font-size:9px;color:#94a3b8;flex-shrink:0;padding-top:1px">${(v.detected_at||'').slice(0,10)}</span>
          </div>`).join('')}
        `;
      }
    }
  } catch(_) {}
}

// ── Identity Health Footer ────────────────────────────────────────────────────
async function loadIdentityFooter() {
  const footer = document.getElementById('id-footer');
  const txt    = document.getElementById('idf-text');
  if (!footer || !txt) return;
  try {
    const [drugsRes, canonRes, fuzzyRes, errRes] = await Promise.all([
      _sb.from('drugs').select('canonical_drug_id', { count:'exact', head:false }),
      _sb.from('canonical_drugs').select('canonical_id,is_active', { count:'exact', head:false }),
      _sb.from('identity_audit_log').select('id', { count:'exact' }).eq('operation','flag_review'),
      _sb.from('resolver_errors').select('id', { count:'exact' }).is('resolved_at', null),
    ]);
    const total      = (drugsRes.data||[]).length;
    const resolved   = (drugsRes.data||[]).filter(d=>d.canonical_drug_id).length;
    const canonIds   = new Set((canonRes.data||[]).map(c=>c.canonical_id).filter(Boolean));
    const orphans    = (drugsRes.data||[]).filter(d=>d.canonical_drug_id&&!canonIds.has(d.canonical_drug_id)).length;
    const fuzzy      = fuzzyRes.count ?? (fuzzyRes.data||[]).length;
    const errs       = errRes.count  ?? (errRes.data||[]).length;

    // Also populate the hidden ih-body for backward compat
    loadIdentityHealth();

    const parts = [`${resolved}/${total} resolved`];
    if (fuzzy  > 0) parts.push(`${fuzzy} fuzzy pending`);
    if (orphans > 0) parts.push(`${orphans} orphans`);
    if (errs    > 0) parts.push(`${errs} resolver errors`);
    txt.textContent = parts.join(' · ');

    if (orphans > 0 || errs > 0) {
      footer.className = 'idf-bad';
    } else if (fuzzy > 0 || resolved < total) {
      footer.className = 'idf-warn';
    } else {
      footer.className = 'idf-ok';
      txt.textContent = `✓ ${resolved}/${total} resolved · 0 fuzzy · 0 orphans — identity layer clean`;
    }
  } catch(e) {
    footer.className = 'idf-warn';
    if (txt) txt.textContent = 'Identity health unavailable';
  }
}

// ── Ontology Health Diagnostic ───────────────────────────────────────────────
// Loads live from Supabase; wired to Ontology Audit tab, Session 88.
async function loadOntologyHealth() {
  const mount = document.getElementById('ont-health-mount');
  if (!mount || !_sb) return;
  mount.innerHTML = '<div style="color:#94a3b8;font-size:12px;padding:8px 0">Querying Supabase…</div>';
  try {
    // Coverage query per table — count total vs with target_id
    const TABLES = [
      { tbl:'catalysts',           alias:'catalysts' },
      { tbl:'company_areas',       alias:'company_areas' },
      { tbl:'deals',               alias:'deals' },
      { tbl:'intel_areas',         alias:'intel_areas' },
      { tbl:'research_queue',      alias:'research_queue' },
      { tbl:'competitive_signals', alias:'competitive_signals' },
      { tbl:'company_profiles',    alias:'company_profiles' },
      { tbl:'discovery_queue',     alias:'discovery_queue' },
      { tbl:'signals',             alias:'signals' },
    ];

    const results = await Promise.all(TABLES.map(({ tbl }) =>
      _sb.from(tbl).select('area_id,target_id,context_type').limit(5000)
        .then(r => {
          const rows = r.data || [];
          const total = rows.length;
          const withTarget = rows.filter(x => x.target_id).length;
          const fallbackContexts = [...new Set(rows.filter(x => !x.target_id && x.area_id).map(x => x.area_id))].sort();
          return { tbl, total, withTarget, pct: total > 0 ? Math.round(withTarget * 100 / total) : 0, fallbackContexts };
        })
    ));

    // Legacy structure status
    const [dasRes, daRes, lamRes] = await Promise.all([
      _sb.from('drug_area_scores').select('area_id', { count:'exact', head:true }),
      _sb.from('drug_areas').select('area_id', { count:'exact', head:true }),
      _sb.from('legacy_area_ontology_map').select('legacy_area_id,context_type,target_id'),
    ]);
    const dasCount = dasRes.count ?? 0;
    const daCount  = daRes.count ?? 0;
    const lamRows  = lamRes.data || [];
    const nullTargetContexts = lamRows.filter(r => !r.target_id).map(r => `${r.legacy_area_id} (${r.context_type})`);

    // Build coverage table
    const coverageRows = results.map(r => {
      const pctCls = r.pct === 100 ? '#16a34a' : r.pct >= 80 ? '#d97706' : r.pct >= 40 ? '#f59e0b' : '#dc2626';
      const fallbackStr = r.fallbackContexts.length ? r.fallbackContexts.join(', ') : '—';
      const note = r.tbl === 'signals' ? '<span style="color:#94a3b8;font-style:italic">area_id never populated by pipeline</span>' : (r.pct === 100 ? '<span style="color:#16a34a">✓ full ontology coverage</span>' : `<span style="color:#64748b">fallback: ${fallbackStr}</span>`);
      return `<tr>
        <td style="font-family:monospace;font-size:11px;font-weight:700;color:#0f172a;padding:5px 10px;white-space:nowrap">${r.tbl}</td>
        <td style="text-align:right;padding:5px 10px;font-size:12px;color:#334155">${r.total}</td>
        <td style="text-align:right;padding:5px 10px;font-size:12px;color:#334155">${r.withTarget}</td>
        <td style="text-align:right;padding:5px 10px;font-size:13px;font-weight:800;color:${pctCls}">${r.pct}%</td>
        <td style="padding:5px 10px;font-size:11px">${note}</td>
      </tr>`;
    }).join('');

    const totalRows  = results.reduce((s,r) => s + r.total, 0);
    const totalOnt   = results.reduce((s,r) => s + r.withTarget, 0);
    const overallPct = totalRows > 0 ? Math.round(totalOnt * 100 / totalRows) : 0;
    const overallCls = overallPct >= 85 ? '#16a34a' : '#d97706';

    mount.innerHTML = `
      <div style="display:flex;align-items:center;gap:24px;margin-bottom:16px;padding:12px 16px;background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0">
        <div style="text-align:center">
          <div style="font-size:28px;font-weight:800;color:${overallCls}">${overallPct}%</div>
          <div style="font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.05em">Ontology Coverage</div>
          <div style="font-size:10px;color:#94a3b8;margin-top:2px">${totalOnt}/${totalRows} rows with target_id</div>
        </div>
        <div style="flex:1;border-left:1px solid #e2e8f0;padding-left:20px">
          <div style="font-size:11px;font-weight:700;color:#334155;margin-bottom:8px">Permanent bridge tables (retain forever)</div>
          <div style="font-size:11px;color:#64748b">• <code style="font-size:11px">legacy_area_ontology_map</code> — ${lamRows.length} rows, ${lamRows.filter(r=>r.target_id).length} target contexts, ${nullTargetContexts.length} non-target: ${nullTargetContexts.join(' · ')}</div>
          <div style="font-size:11px;color:#64748b;margin-top:4px">• <code style="font-size:11px">area_metadata</code> — migration tracking system</div>
        </div>
        <div style="border-left:1px solid #e2e8f0;padding-left:20px">
          <div style="font-size:11px;font-weight:700;color:#334155;margin-bottom:8px">Legacy safety rails (gated)</div>
          <div style="font-size:11px;color:#64748b">• <code style="font-size:11px">drug_area_scores</code> — ${dasCount} rows — gate 2026-06-27</div>
          <div style="font-size:11px;color:#f59e0b;font-weight:600;margin-top:4px">• <code style="font-size:11px">drug_areas</code> — ${daCount} rows — Phase 5 activations pending (il4ra, tslp, ted)</div>
        </div>
      </div>

      <table style="width:100%;border-collapse:collapse;font-size:12px">
        <thead>
          <tr style="border-bottom:2px solid #e2e8f0">
            <th style="text-align:left;padding:5px 10px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#94a3b8">Table</th>
            <th style="text-align:right;padding:5px 10px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#94a3b8">Total</th>
            <th style="text-align:right;padding:5px 10px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#94a3b8">Ontology</th>
            <th style="text-align:right;padding:5px 10px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#94a3b8">Coverage</th>
            <th style="text-align:left;padding:5px 10px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#94a3b8">Fallback Path</th>
          </tr>
        </thead>
        <tbody>${coverageRows}</tbody>
        <tfoot>
          <tr style="border-top:2px solid #e2e8f0;background:#f8fafc">
            <td style="padding:6px 10px;font-size:11px;font-weight:700;color:#0f172a">All tables</td>
            <td style="text-align:right;padding:6px 10px;font-size:12px;font-weight:700;color:#0f172a">${totalRows}</td>
            <td style="text-align:right;padding:6px 10px;font-size:12px;font-weight:700;color:#0f172a">${totalOnt}</td>
            <td style="text-align:right;padding:6px 10px;font-size:13px;font-weight:800;color:${overallCls}">${overallPct}%</td>
            <td style="padding:6px 10px;font-size:11px;color:#94a3b8">signals excluded from meaningful %</td>
          </tr>
        </tfoot>
      </table>

      <div style="margin-top:14px;padding:10px 14px;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:7px;font-size:11px;color:#166534">
        <strong>Dual-filter locations (12 active reads):</strong> research_queue · intel_areas · catalysts (area tabs) · deals (area tabs) · bd_activity · competitive_signals (company modal) · company_profiles (company modal) · discovery_queue (client-side) · signals (client-side) · Morning Report · loadTL1AIntelFeed · _loadBdIntoModal
      </div>
      <div style="margin-top:8px;padding:10px 14px;background:#fffbeb;border:1px solid #fde68a;border-radius:7px;font-size:11px;color:#92400e">
        <strong>Outstanding code flips (low urgency):</strong> catalysts reads in company modal (lines 10476, 10500) and OEX card (line 14110) still use direct .eq('area_id') — works correctly because catalysts.area_id is still populated; will pick up in a future cleanup session.
      </div>
      <div style="margin-top:8px;font-size:10px;color:#94a3b8;text-align:right">Queried live · ${new Date().toLocaleString()}</div>
      <div id="lds-scores-panel" style="margin-top:12px"></div>
    `;
    // G7 fix: load LDS scores into panel
    (async () => {
      try {
        const { data: lsRows } = await _sb.from('competitive_landscapes')
          .select('area_id,landscape_dependency_score,relationship_coverage_score,drug_coverage_score,source_validation_score,coverage_computed_at')
          .order('landscape_dependency_score', { ascending: false });
        if (!lsRows?.length) return;
        const cols = lsRows.map(l => {
          const s = Math.round(l.landscape_dependency_score ?? 0);
          const col = s >= 80 ? '#065f46' : s >= 60 ? '#92400e' : '#991b1b';
          const bg  = s >= 80 ? '#d1fae5' : s >= 60 ? '#fef3c7' : '#fee2e2';
          return `<div style="text-align:center;padding:8px 12px;background:${bg};border-radius:8px;flex:1;min-width:90px">
            <div style="font-size:18px;font-weight:800;color:${col}">${s}</div>
            <div style="font-size:9px;font-weight:700;color:${col};text-transform:uppercase">${l.area_id}</div>
            <div style="font-size:9px;color:${col};opacity:.75;margin-top:2px">rel ${Math.round((l.relationship_coverage_score??0)*100)}% · src ${Math.round((l.source_validation_score??0)*100)}%</div>
          </div>`;
        }).join('');
        const computedAt = lsRows[0]?.coverage_computed_at ? new Date(lsRows[0].coverage_computed_at).toLocaleDateString('en-US',{month:'short',day:'numeric'}) : '';
        document.getElementById('lds-scores-panel').innerHTML = `
          <div style="padding:10px 14px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px">
            <div style="font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px">Landscape Dependency Scores (LDS/100) — updated ${computedAt}</div>
            <div style="display:flex;gap:6px;flex-wrap:wrap">${cols}</div>
            <div style="font-size:9px;color:#94a3b8;margin-top:6px">Formula: Drug×35 + Rel×25 + Cat×20 + Source×15 − Stale×5 · computed weekly</div>
          </div>`;
      } catch(e) { console.warn('LDS panel error', e); }
    })();
  } catch(e) {
    mount.innerHTML = `<div style="color:#dc2626;font-size:12px">Error: ${e.message}</div>`;
  }
}

// ── PI Score Badge injection ──────────────────────────────────────────────────
// Called after _makeAreaPI loads; injects colored score chips into the table.
async function _injPIScores(tabId, areaIds) {
  if (!areaIds || !areaIds.length) return;
  try {
    const { data, error } = await _sb
      .from('research_queue')
      .select('entity_id,completeness_score,completeness_tier,next_best_action,priority_score,area_id,target_id,context_type')
      .or(`target_id.in.(${areaIds.join(',')}),area_id.in.(${areaIds.join(',')})`);
    if (error || !data || !data.length) return;

    // Build map: entity_id → best record (highest priority)
    const map = new Map();
    for (const r of data) {
      const cur = map.get(r.entity_id);
      if (!cur || (r.priority_score||0) > (cur.priority_score||0)) map.set(r.entity_id, r);
    }
    if (!map.size) return;

    // Find all pi-co-name elements in this tab and inject badges
    const tableEl = document.getElementById(tabId + '-area-pi');
    if (!tableEl) return;
    tableEl.querySelectorAll('.pi-co-name').forEach(el => {
      const entityName = el.textContent.trim();
      // Try to match by normalizing: lowercase, remove spaces/special chars
      const norm = s => s.toLowerCase().replace(/[^a-z0-9]/g,'');
      let matched = null;
      for (const [eid, r] of map) {
        if (norm(eid) === norm(entityName) || norm(r.entity_id) === norm(entityName)) {
          matched = r; break;
        }
        // Also try partial match on entity_id
        if (norm(entityName).includes(norm(eid)) || norm(eid).includes(norm(entityName))) {
          matched = r; break;
        }
      }
      if (!matched) return;
      // Don't double-inject
      if (el.parentNode.querySelector('.pi-score-chip')) return;
      const tier  = matched.completeness_tier || 'thin';
      const score = matched.completeness_score || 0;
      const eid2  = matched.entity_id;
      const aid   = matched.area_id;
      const action= (matched.next_best_action || '').replace(/'/g, "\\'");
      const chip  = document.createElement('span');
      chip.className = `pi-score-chip ${tier}`;
      chip.title     = `Completeness: ${score}/100 (${tier})`;
      chip.innerHTML = `${score}`;
      chip.onclick   = (e) => {
        e.stopPropagation();
        showPIScoreModal(eid2, aid, entityName, score, tier, matched.next_best_action||'', matched.priority_score||0);
      };
      el.parentNode.appendChild(chip);
    });
  } catch(e) { /* non-critical; silent fail */ }
}

// ── PI Score Modal ────────────────────────────────────────────────────────────
function showPIScoreModal(entityId, areaId, entityName, score, tier, action, priority) {
  const overlay   = document.getElementById('pi-score-modal-overlay');
  const elName    = document.getElementById('pi-modal-entity');
  const elArea    = document.getElementById('pi-modal-area');
  const elScore   = document.getElementById('pi-modal-score-num');
  const elTier    = document.getElementById('pi-modal-score-tier');
  const elBarFill = document.getElementById('pi-modal-bar-fill');
  const elAction  = document.getElementById('pi-modal-action');
  const elPri     = document.getElementById('pi-modal-pri');
  if (!overlay) return;
  const areaLabel = AREA_LABELS[areaId] || areaId || '';
  elName.textContent    = entityName;
  elArea.textContent    = areaLabel;
  elScore.textContent   = score;
  elTier.textContent    = (tier||'unknown').charAt(0).toUpperCase() + (tier||'').slice(1);
  [elScore, elTier, elBarFill].forEach(el => {
    el.className = el.className.replace(/\b(thin|partial|strong)\b/g, '').trim();
    el.classList.add(tier||'thin');
  });
  // Animate bar fill after a tick
  elBarFill.style.width = '0%';
  setTimeout(() => { elBarFill.style.width = Math.min(100, score) + '%'; }, 30);
  elAction.textContent  = action || 'No action specified.';
  elPri.innerHTML       = priority ? `<span style="color:#94a3b8">Pipeline priority:</span> <strong style="color:#1a2f50">${priority}</strong>` : '';
  overlay.style.display = 'flex';
  document.body.style.overflow = 'hidden';
}
function closePIModal() {
  const overlay = document.getElementById('pi-score-modal-overlay');
  if (overlay) overlay.style.display = 'none';
  document.body.style.overflow = '';
}
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    closePIModal();
    // Close any open drug/area modal overlays
    document.querySelectorAll('.tl1a-modal-overlay.open').forEach(m => m.classList.remove('open'));
    if (!document.querySelector('.tl1a-modal-overlay.open')) document.body.style.overflow = '';
  }
});

// ── BD Signal Panel ───────────────────────────────────────────────────────────
async function loadBDSignal() {
  const body = document.getElementById('bd-signal-body');
  if (!body) return;
  try {
    const sevenDaysAgo = new Date(Date.now() - 7*24*60*60*1000).toISOString().split('T')[0];
    const [dealsRes, intelRes] = await Promise.all([
      _sb.from('deals').select('*').order('deal_date', { ascending: false }).limit(10),
      _sb.from('intel').select('id,headline,summary:body,intel_date,importance,source_url')
        .eq('importance','high').gte('intel_date', sevenDaysAgo)
        .order('intel_date', { ascending: false }).limit(6),
    ]);
    if (dealsRes.error) throw dealsRes.error;

    // Build unified feed items with type + sort date
    const feedItems = [];

    // Deals: prefer ones with ailux_signal, take top 3
    const deals = dealsRes.data || [];
    const dealsWithSignal = deals.filter(d => d.ailux_signal);
    const topDeals = (dealsWithSignal.length >= 2 ? dealsWithSignal : deals).slice(0, 3);
    topDeals.forEach(d => {
      feedItems.push({ type: 'deal', sortDate: d.deal_date || '0000-00-00', data: d });
    });

    // Intel: high-importance last 7d
    const intel = intelRes.data || [];
    intel.slice(0, 3).forEach(i => {
      feedItems.push({ type: 'intel', sortDate: i.intel_date || '0000-00-00', data: i });
    });

    // Sort by date desc
    feedItems.sort((a, b) => b.sortDate.localeCompare(a.sortDate));

    if (!feedItems.length) {
      body.innerHTML = `<div style="color:#94a3b8;font-size:12px;padding:8px 0">No recent signals — run the pipeline to generate intelligence.</div>`;
      return;
    }

    const cards = feedItems.map(item => {
      const areaColor = AREA_COLORS[item.data.area_id] || '#4b5563';
      const areaLabel = AREA_LABELS[item.data.area_id] || item.data.area_id || '';
      const areaPill  = areaLabel
        ? `<span style="font-size:9px;font-weight:700;color:white;background:${areaColor};padding:2px 7px;border-radius:8px;">${areaLabel}</span>`
        : '';

      if (item.type === 'deal') {
        const d = item.data;
        const val = d.total_usd_m ? `<span style="font-weight:800;color:#0d1f38">${fmtMoney(d.total_usd_m)}</span>` : '';
        const upfront = d.upfront_usd_m ? `<span style="font-size:10px;color:#64748b"> · ${fmtMoney(d.upfront_usd_m)} upfront</span>` : '';
        const srcLink = _srcHtml(d.source_url, d.headline);
        const signalHtml = d.ailux_signal
          ? `<div class="bds-item-signal"><span style="font-size:9px;font-weight:800;text-transform:uppercase;color:#1a3f8f;display:block;margin-bottom:2px;">◈ Ailux BD Signal</span>${d.ailux_signal}</div>`
          : '';
        return `<div class="bds-item">
          <div style="display:flex;align-items:center;gap:5px;flex-wrap:wrap;margin-bottom:3px;">
            <span class="bds-item-type deal">Deal</span>
            ${areaPill}
            <span style="font-size:9px;color:#94a3b8;">${rdtFmtDate(d.deal_date)||d.deal_date_label||''}</span>
            ${val}${upfront}${srcLink}
          </div>
          <div style="font-size:11.5px;font-weight:600;color:#1e293b;line-height:1.4;">${d.from_company||''} → ${d.to_company||''}</div>
          <div style="font-size:11px;color:#475569;margin-top:2px;line-height:1.4;">${d.headline||''}</div>
          ${signalHtml}
        </div>`;
      } else {
        const i = item.data;
        const srcLink = _srcHtml(i.source_url, i.headline);
        const angleHtml = i.ailux_angle
          ? `<div class="bds-item-signal"><span style="font-size:9px;font-weight:800;text-transform:uppercase;color:#15803d;display:block;margin-bottom:2px;">◈ Ailux Angle</span>${i.ailux_angle}</div>`
          : '';
        return `<div class="bds-item">
          <div style="display:flex;align-items:center;gap:5px;flex-wrap:wrap;margin-bottom:3px;">
            <span class="bds-item-type intel">Intel</span>
            <span style="font-size:9px;font-weight:800;color:#dc2626;background:#fef2f2;border:1px solid #fca5a5;padding:1px 5px;border-radius:8px;">HIGH</span>
            ${areaPill}
            <span style="font-size:9px;color:#94a3b8;">${rdtFmtDate(i.intel_date)||''}</span>
            ${srcLink}
          </div>
          <div style="font-size:11.5px;font-weight:600;color:#1e293b;line-height:1.4;">${i.headline||''}</div>
          ${i.summary ? `<div style="font-size:11px;color:#475569;margin-top:2px;line-height:1.4;">${i.summary}</div>` : ''}
          ${angleHtml}
        </div>`;
      }
    }).join('');

    const intelCnt = intel.length;
    const dealCnt  = (dealsRes.data||[]).length;
    const summary = `<div style="font-size:10px;color:#64748b;padding-top:8px;border-top:1px solid #f0f4f8;margin-top:2px;">${topDeals.length} deals · ${Math.min(3,intelCnt)} high-priority intel (last 7d) · ${dealCnt} total deals on record</div>`;
    body.innerHTML = cards + summary;
  } catch(err) {
    body.innerHTML = `<div style="color:#dc2626;font-size:12px;padding:8px 0">Error loading BD signal: ${err.message}</div>`;
    console.warn('[loadBDSignal]', err);
  }
}

// ── Signals Panel ─────────────────────────────────────────────────────────────
let _allSignals = [];
let _sigAreaFilter = '';
let _sigTypeFilter = '';

const SIG_TYPE_STYLE = {
  press_release:   { label: 'Press Release',   bg: '#eff6ff', color: '#1d4ed8' },
  trial_update:    { label: 'Trial Update',     bg: '#f0fdf4', color: '#15803d' },
  deal:            { label: 'Deal',             bg: '#f0fdf4', color: '#065f46' },
  abstract:        { label: 'Abstract',         bg: '#faf5ff', color: '#6d28d9' },
  financing:       { label: 'Financing',        bg: '#ecfdf5', color: '#047857' },
  pipeline_change: { label: 'Pipeline',         bg: '#fff7ed', color: '#c2410c' },
  fda:             { label: 'FDA',              bg: '#fef2f2', color: '#b91c1c' },
};

function _sigScoreClass(score) {
  if (score >= 8) return 'high';
  if (score >= 6) return 'notable';
  return 'watch';
}

function _sigGroupLabel(dateStr) {
  if (!dateStr) return 'Earlier';
  const d = new Date(dateStr);
  const now = new Date();
  const diffDays = Math.floor((now - d) / 86400000);
  if (diffDays <= 0) return 'Today';
  if (diffDays <= 7) return 'This Week';
  return 'Earlier';
}

function renderSignals(rows) {
  const list = document.getElementById('signals-list');
  if (!list) return;
  let filtered = _sigAreaFilter ? rows.filter(r => r.area_id === _sigAreaFilter || r.target_id === _sigAreaFilter) : rows;
  if (_sigTypeFilter) filtered = filtered.filter(r => r.signal_type === _sigTypeFilter);
  if (!filtered.length) {
    list.innerHTML = '<div style="text-align:center;padding:20px;color:#94a3b8;font-size:12px;">No signals found.</div>';
    return;
  }

  const renderSigItem = r => {
    const scoreClass = _sigScoreClass(r.relevance_score || 0);
    const typeStyle = SIG_TYPE_STYLE[r.signal_type] || { label: r.signal_type || '—', bg: '#f8fafc', color: '#64748b' };
    const coName = r.companies?.name || r.company_id || '—';
    const areaLabel = AREA_LABELS[r.area_id] || r.area_id || '';
    const areaTag = areaLabel ? `<span style="font-size:9px;font-weight:700;color:${AREA_COLORS[r.area_id]||'#64748b'};background:${AREA_BG[r.area_id]||'#f1f5f9'};padding:1px 5px;border-radius:8px;margin-left:4px;">${areaLabel}</span>` : '';
    const srcName = r.source_name ? `<span style="font-size:10px;color:#94a3b8">${r.source_name}</span>` : '';
    const noSrc   = '';
    const dateStr = r.event_date ? `<span style="font-size:10px;color:#cbd5e1;margin-left:4px;">${r.event_date}</span>` : '';
    const sigHeadlineUrl = r.source_url || _srcSearch(r.headline);
    const headline = `<a href="${sigHeadlineUrl}" target="_blank" rel="noopener" style="color:#0f172a;text-decoration:none;font-weight:600;font-size:12px;line-height:1.4;">${r.headline || '—'}</a>`;
    return `
      <div class="sig-item">
        <div class="sig-score ${scoreClass}" title="Relevance score: ${r.relevance_score}">${r.relevance_score || 0}</div>
        <div style="flex:1;min-width:0;">
          <div style="display:flex;align-items:center;flex-wrap:wrap;gap:4px;margin-bottom:3px;">
            <span class="sig-type" style="background:${typeStyle.bg};color:${typeStyle.color};">${typeStyle.label}</span>
            <span style="font-size:11px;font-weight:700;color:#1e293b;">${coName}</span>${areaTag}
          </div>
          <div style="margin-bottom:3px;">${headline}</div>
          <div style="display:flex;align-items:center;gap:0;">${srcName}${dateStr}${noSrc}</div>
        </div>
      </div>`;
  };

  // Show top 5, collapse rest
  const SIG_SHOW = 5;
  const visible = filtered.slice(0, SIG_SHOW);
  const hidden  = filtered.slice(SIG_SHOW);
  let html = visible.map(renderSigItem).join('');
  if (hidden.length) {
    html += `<div id="signals-more" style="display:none">${hidden.map(renderSigItem).join('')}</div>`;
    html += `<button onclick="document.getElementById('signals-more').style.display='';this.style.display='none'" style="width:100%;margin-top:6px;padding:5px 0;font-size:10px;font-weight:700;color:#2563eb;background:#f0f6ff;border:1px solid #bfdbfe;border-radius:6px;cursor:pointer;">Show ${hidden.length} more signals ↓</button>`;
  }
  list.innerHTML = html;
}

function sigTypeFilter(btn, type) {
  document.querySelectorAll('#sig-type-filter-bar .stock-fbtn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  _sigTypeFilter = type;
  renderSignals(_allSignals);
}

async function loadSignals(force = false) {
  const list = document.getElementById('signals-list');
  if (!list) return;
  if (_allSignals.length && !force) { renderSignals(_allSignals); return; }
  list.innerHTML = '<div style="text-align:center;padding:20px;color:#94a3b8;font-size:12px;">Loading signals…</div>';
  try {
    const since = new Date(Date.now() - 7*24*60*60*1000).toISOString().split('T')[0];
    const { data, error } = await _sb.from('signals')
      .select('*,companies(name)')
      .gte('event_date', since)
      .order('relevance_score', { ascending: false })
      .order('event_date', { ascending: false })
      .limit(100);
    if (error) throw error;
    _allSignals = data || [];
    renderSignals(_allSignals);
  } catch(err) {
    list.innerHTML = `<div style="color:#dc2626;font-size:12px;padding:8px 0">Error loading signals: ${err.message}</div>`;
    console.warn('[loadSignals]', err);
  }
}

function sigFilter(btn, area) {
  document.querySelectorAll('#sig-area-filter-bar .stock-fbtn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  _sigAreaFilter = area;
  renderSignals(_allSignals);
}

// ── MOLECULE TAB DYNAMIC LOADERS ──────────────────────────────────────────────
// Maps each tab ID to one or more Supabase area_ids
const TAB_AREA_MAP = {
  'tl1a':       ['tl1a', 'ibd'],  // 'ibd' enables useNormalizedIBD flag path; union(tl1a,ibd)=tl1a in legacy (no display change)
  'tslp':       ['tslp'],
  'il4ra-tslp': ['il4ra','tslp'],
  'il4ra-ox40l':['il4ra'],
  'igf1r-tshr': ['igf1r'],
  'fcrn':       ['fcrn'],
  'ace':        ['tcell'],
};
const _molTabLoaded = {}; // lazy-load cache

const STAGE_COLOR = {
  'Approved':    '#065f46', 'BLA Filed': '#1d4ed8',
  'Phase 3':     '#1d4ed8', 'Phase 2':   '#7c3aed',
  'Phase 1/2':   '#7c3aed', 'Phase 1b':  '#b45309',
  'Phase 1':     '#b45309', 'Preclinical':'#6b7280',
};
function stagePill(stage) {
  const col = STAGE_COLOR[stage] || '#4b5563';
  return `<span style="background:${col}1a;color:${col};font-size:9px;font-weight:800;padding:2px 8px;border-radius:10px;white-space:nowrap">${stage}</span>`;
}
function importanceDot(imp) {
  return imp === 'high' ? '🔴' : imp === 'medium' ? '🟡' : '⚪';
}

// ── Area Intel Loader ─────────────────────────────────────────────────────────
async function loadAreaIntel(tabId) {
  const areas = TAB_AREA_MAP[tabId];
  if (!areas) return;
  const el = document.getElementById(tabId + '-live-intel');
  if (!el) return;
  try {
    // Step 1: get intel_ids tagged to these areas
    const { data: iaRows, error: iaErr } = await _sb.from('intel_areas')
      .select('intel_id').or(`target_id.in.(${areas.join(',')}),area_id.in.(${areas.join(',')})`);
    if (iaErr) throw iaErr;
    if (!iaRows || !iaRows.length) {
      el.innerHTML = `<div style="color:#94a3b8;font-size:12px;padding:10px 0">No Meridian intel yet — updates will appear here after the next morning run.</div>`;
      return;
    }
    const intelIds = [...new Set(iaRows.map(r => r.intel_id))].slice(0, 15);
    // Step 2: fetch those intel records
    const { data: rows, error: iErr } = await _sb.from('intel')
      .select('*').in('id', intelIds)
      .order('intel_date', { ascending: false }).limit(8);
    if (iErr) throw iErr;
    if (!rows || !rows.length) {
      el.innerHTML = `<div style="color:#94a3b8;font-size:12px;padding:10px 0">No Meridian intel yet — updates will appear here after the next morning run.</div>`;
      return;
    }
    el.innerHTML = rows.map(item => `
      <div style="padding:10px 0;border-bottom:1px solid #f0f4f8">
        <div style="display:flex;align-items:flex-start;gap:8px">
          <span style="flex-shrink:0;margin-top:1px">${importanceDot(item.importance)}</span>
          <div style="flex:1">
            <div style="font-size:13px;font-weight:700;color:#0d1f38;line-height:1.4">${item.headline}</div>
            ${item.body ? `<div style="font-size:12px;color:#4b5563;margin-top:4px;line-height:1.5">${item.body}</div>` : ''}
            <div style="display:flex;gap:8px;margin-top:6px;align-items:center;flex-wrap:wrap">
              <span style="font-size:11px;color:#94a3b8">${rdtFmtDate(item.intel_date)||item.intel_date}</span>
              ${item.source_name ? `<span style="font-size:11px;color:#6b7280">· ${item.source_name}</span>` : ''}
              ${item.intel_type ? `<span style="font-size:10px;font-weight:700;text-transform:uppercase;padding:1px 6px;border-radius:8px;background:#f0f4f8;color:#6b7280">${item.intel_type}</span>` : ''}
              ${_srcHtml(item.source_url, item.headline, '11px')}
            </div>
          </div>
        </div>
      </div>`).join('');
  } catch(e) {
    el.innerHTML = `<div style="color:#94a3b8;font-size:12px">Intel feed unavailable.</div>`;
    console.error('loadAreaIntel', tabId, e);
  }
}

// ── Area Catalysts Loader ─────────────────────────────────────────────────────
async function loadAreaCatalysts(tabId) {
  const areas = TAB_AREA_MAP[tabId];
  if (!areas) return;
  const el = document.getElementById(tabId + '-live-catalysts');
  if (!el) return;
  try {
    // Phase 3 dual-filter: target_id (new) OR area_id (legacy) — both valid during transition
    const { data: rows, error } = await _sb.from('catalysts')
      .select('*').eq('resolved', false)
      .or(`target_id.in.(${areas.join(',')}),area_id.in.(${areas.join(',')})`)
      .order('sort_date', { ascending: true }).limit(10);
    if (error) throw error;
    if (!rows || !rows.length) {
      el.innerHTML = `<div style="color:#94a3b8;font-size:12px;padding:10px 0">No upcoming catalysts logged. Meridian will add events here.</div>`;
      return;
    }

    // ── Enrich with BD timing window data ─────────────────────────────────────
    let bdTimingMap = {};
    try {
      const _catDrugIds = rows.map(c => c.drug_id).filter(Boolean);
      if (_catDrugIds.length) {
        const { data: bdTiming } = await _sb
          .from('catalyst_bd_timing_window')
          .select('company_id, bd_score:overall_bd_score, call_priority, ailux_pitch, ailux_action_tier')
          .in('drug_id', _catDrugIds);
        (bdTiming || []).forEach(b => { bdTimingMap[b.drug_id] = b; });
      }
    } catch(_) {}

    const sigColor = { high:'#dc2626', medium:'#d97706', low:'#6b7280' };
    const _bdPriorityStyle = { call_now:'#dc3545', monitor:'#fd7e14', watch:'#6c757d' };
    el.innerHTML = rows.map(c => {
      const _bd = c.drug_id ? bdTimingMap[c.drug_id] : null;
      const _bdBadge = _bd ? `<span style="background:${_bdPriorityStyle[_bd.call_priority]||'#6c757d'};color:#fff;border-radius:3px;padding:1px 5px;font-size:9px;font-weight:700;white-space:nowrap;margin-left:4px" title="${_bd.ailux_pitch||''}">${(_bd.call_priority||'').replace(/_/g,' ')}</span>` : '';
      return `
      <div style="display:flex;gap:12px;align-items:flex-start;padding:10px 0;border-bottom:1px solid #f0f4f8">
        <div style="flex-shrink:0;width:80px;text-align:right">
          <span style="font-size:11px;font-weight:800;color:${sigColor[c.significance]||'#6b7280'}">${c.catalyst_date}</span>
        </div>
        <div style="flex:1">
          <div style="font-size:13px;font-weight:700;color:#0d1f38;line-height:1.4;display:flex;align-items:center;flex-wrap:wrap;gap:4px">${c.label}${_bdBadge}</div>
          ${c.notes ? `<div style="font-size:12px;color:#6b7280;margin-top:3px">${c.notes}</div>` : ''}
          ${_bd?.ailux_pitch ? `<div style="font-size:10.5px;color:#1d4ed8;margin-top:3px;font-style:italic">${_bd.ailux_pitch}</div>` : ''}
        </div>
        <div style="flex-shrink:0">
          <span style="font-size:9px;font-weight:800;text-transform:uppercase;padding:2px 7px;border-radius:8px;background:${sigColor[c.significance]||'#6b7280'}1a;color:${sigColor[c.significance]||'#6b7280'}">${c.significance}</span>
        </div>
      </div>`;
    }).join('');
  } catch(e) {
    el.innerHTML = `<div style="color:#94a3b8;font-size:12px">Catalysts unavailable.</div>`;
    console.error('loadAreaCatalysts', tabId, e);
  }
}

// ── Area Deals Loader ─────────────────────────────────────────────────────────
async function loadAreaDeals(tabId) {
  const areas = TAB_AREA_MAP[tabId];
  if (!areas) return;
  const el = document.getElementById(tabId + '-live-deals');
  if (!el) return;
  try {
    // Phase 3 dual-filter: target_id OR area_id during transition
    const { data: rows, error } = await _sb.from('deals')
      .select('*').or(`target_id.in.(${areas.join(',')}),area_id.in.(${areas.join(',')})`)
      .order('deal_date', { ascending: false }).limit(6);
    if (error) throw error;
    if (!rows || !rows.length) {
      el.innerHTML = `<div style="color:#94a3b8;font-size:12px;padding:10px 0">No deals logged for this area yet.</div>`;
      return;
    }
    const typeColor = { acquisition:'#7c3aed', license:'#1d4ed8', collab:'#065f46', option:'#b45309' };
    el.innerHTML = rows.map(d => {
      const val = d.upfront_usd_m ? `$${d.upfront_usd_m}M up${d.total_usd_m ? ` / $${d.total_usd_m}M total` : ''}` :
                  d.total_usd_m ? `$${d.total_usd_m}M` : null;
      const tc = typeColor[d.deal_type] || '#6b7280';
      return `<div style="padding:12px 0;border-bottom:1px solid #f0f4f8">
        <div style="flex:1">
          <div style="display:flex;gap:6px;align-items:center;margin-bottom:5px;flex-wrap:wrap">
            <span style="font-size:10px;font-weight:800;text-transform:uppercase;padding:2px 7px;border-radius:8px;background:${tc}1a;color:${tc}">${d.deal_type||'deal'}</span>
            <span style="font-size:11px;color:#94a3b8">${rdtFmtDate(d.deal_date)||d.deal_date_label||''}</span>
            ${val ? `<span style="font-size:11px;font-weight:700;color:#065f46">${val}</span>` : ''}
          </div>
          <div style="font-size:13px;font-weight:700;color:#0d1f38;line-height:1.4">${d.headline}</div>
          ${d.detail ? `<div style="font-size:12px;color:#4b5563;margin-top:5px;line-height:1.5">${d.detail}</div>` : ''}
          ${d.ailux_signal ? `<div style="font-size:12px;font-weight:600;color:#1d4ed8;margin-top:6px;padding:6px 10px;background:#eff6ff;border-radius:5px;border-left:3px solid #2e6fb0">◈ Ailux Lens: ${d.ailux_signal}</div>` : ''}
        </div>
      </div>`;
    }).join('');
  } catch(e) {
    el.innerHTML = `<div style="color:#94a3b8;font-size:12px">Deals unavailable.</div>`;
    console.error('loadAreaDeals', tabId, e);
  }
}

// ── BD Insights Loader ───────────────────────────────────────────────────────
// Loads strategic intelligence summaries from bd_insights table (v54)
// Renders below existing area tab content as collapsible insight cards
// tabId = the modal/tab ID (e.g. 'tslp', 'il4ra-tslp', 'ace'); maps to area_slug + container
const _BD_INSIGHTS_MAP = {
  'tl1a':       { slug:'tl1a',  cid:'tl1a-bd-insights' },
  'tslp':       { slug:'tslp',  cid:'tslp-bd-insights' },
  'il4ra-tslp': { slug:'il4ra', cid:'il4ra-tslp-bd-insights' },
  'il4ra-ox40l':{ slug:'il4ra', cid:'il4ra-ox40l-bd-insights' },
  'igf1r-tshr': { slug:'igf1r', cid:'igf1r-tshr-bd-insights' },
  'igf1r':      { slug:'igf1r', cid:'igf1r-tshr-bd-insights' },
  'fcrn':       { slug:'fcrn',  cid:'fcrn-bd-insights' },
  'ace':        { slug:'tcell', cid:'ace-bd-insights' },
  'tcell':      { slug:'tcell', cid:'ace-bd-insights' },
};
async function loadBdInsights(tabId) {
  const mapping = _BD_INSIGHTS_MAP[tabId];
  if (!mapping) return;
  const el = document.getElementById(mapping.cid);
  if (!el || typeof _sb === 'undefined') return;
  const areaSlug = mapping.slug;
  try {
    const { data, error } = await _sb
      .from('bd_insights')
      .select('*')
      .eq('area_slug', areaSlug)
      .order('significance_score', { ascending: false })
      .limit(5);
    if (error) throw error;
    if (!data || !data.length) {
      el.innerHTML = '';
      return;
    }
    const typeLabel = {
      landscape_summary: 'Landscape', competitive_threat: 'Competitive Threat',
      deal_context: 'Deal Context', patient_insight: 'Patient Intel',
      mechanism_note: 'Mechanism', timing_alert: 'Timing Alert',
      acquisition_signal: 'Acquisition Signal'
    };
    const typeColor = {
      landscape_summary: '#1d4ed8', competitive_threat: '#dc2626',
      deal_context: '#7c3aed', patient_insight: '#059669',
      mechanism_note: '#0891b2', timing_alert: '#d97706',
      acquisition_signal: '#9333ea'
    };
    const scoreBar = (s) => {
      const pct = Math.round((s / 10) * 100);
      const col = s >= 9 ? '#dc2626' : s >= 7 ? '#d97706' : '#6b7280';
      return `<div style="display:flex;align-items:center;gap:6px"><span style="font-size:10px;font-weight:800;color:${col}">${s}/10</span><div style="width:50px;height:4px;background:#e5e7eb;border-radius:2px"><div style="width:${pct}%;height:4px;background:${col};border-radius:2px"></div></div></div>`;
    };
    el.innerHTML = `
      <div style="margin-top:16px">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
          <span style="font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:#64748b">Strategic Intelligence</span>
          <span style="font-size:9px;background:#e8f0f8;color:#2e6fb0;padding:1px 7px;border-radius:8px;font-weight:800">Live · Supabase</span>
        </div>
        ${data.map(ins => {
          const tc = typeColor[ins.insight_type] || '#6b7280';
          const tl = typeLabel[ins.insight_type] || ins.insight_type;
          const insId = 'insight-' + ins.id;
          return `<div style="border:1px solid #e5e7eb;border-radius:8px;margin-bottom:8px;overflow:hidden">
            <div onclick="var b=document.getElementById('${insId}');b.style.display=b.style.display==='none'?'block':'none'" style="display:flex;align-items:flex-start;gap:10px;padding:10px 12px;cursor:pointer;background:#fafbfc">
              <span style="flex-shrink:0;font-size:9px;font-weight:800;text-transform:uppercase;padding:2px 7px;border-radius:8px;background:${tc}1a;color:${tc};margin-top:1px">${tl}</span>
              <span style="flex:1;font-size:12px;font-weight:700;color:#0d1f38;line-height:1.4">${ins.headline}</span>
              <span style="flex-shrink:0">${scoreBar(ins.significance_score||0)}</span>
            </div>
            <div id="${insId}" style="display:none;padding:10px 12px;background:white;border-top:1px solid #f0f4f8">
              <p style="font-size:12px;color:#374151;line-height:1.7;margin:0">${ins.body}</p>
              ${ins.source_url ? `<a href="${ins.source_url}" target="_blank" rel="noopener" style="font-size:11px;color:#2e6fb0;margin-top:6px;display:inline-block">Source</a>` : ''}
            </div>
          </div>`;
        }).join('')}
      </div>`;
  } catch(e) {
    el.innerHTML = '';
    console.error('loadBdInsights', areaSlug, e);
  }
}

// ── BD ACTIVITY TABLE ────────────────────────────────────────────────────────
const _BDA_TYPE_COLOR = { acquisition:'#7c3aed', license:'#1d4ed8', collab:'#065f46', option:'#b45309' };
const _bdaState = {}; // per-section filter state

async function loadAreaBDActivity(tabId) {
  const areas = TAB_AREA_MAP[tabId];
  if (!areas) return;
  const el = document.getElementById(tabId + '-bd-activity');
  if (!el) return;
  try {
    // Phase 3 dual-filter: target_id OR area_id during transition
    let { data: rows, error } = await _sb.from('deals')
      .select('*').or(`target_id.in.(${areas.join(',')}),area_id.in.(${areas.join(',')})`)
      .order('deal_date', { ascending: false });
    if (error) throw error;
    _bdaState[tabId] = { rows: rows || [], filter: 'all', search: '' };
    _bdaRender(tabId);
  } catch(e) {
    const el2 = document.getElementById(tabId + '-bd-activity');
    if (el2) el2.innerHTML = '<div class="bda-empty">BD activity unavailable.</div>';
    console.error('loadAreaBDActivity', e);
  }
}

function _bdaRender(tabId) {
  const el = document.getElementById(tabId + '-bd-activity');
  if (!el) return;
  const s = _bdaState[tabId];
  if (!s) return;

  // Deduplicate by normalized headline — merge richer fields from duplicates
  const _hlKey = hl => (hl || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim().slice(0, 80);
  const deduped = [];
  const seen = new Map();
  (s.rows || []).forEach(d => {
    const k = _hlKey(d.headline);
    if (!k) { deduped.push({...d}); return; }
    if (!seen.has(k)) { seen.set(k, deduped.length); deduped.push({...d}); }
    else {
      const ex = deduped[seen.get(k)];
      if (!ex.detail        && d.detail)        ex.detail        = d.detail;
      if (!ex.ailux_signal  && d.ailux_signal)  ex.ailux_signal  = d.ailux_signal;
      if (!ex.total_usd_m   && d.total_usd_m)   ex.total_usd_m   = d.total_usd_m;
      if (!ex.upfront_usd_m && d.upfront_usd_m) ex.upfront_usd_m = d.upfront_usd_m;
      if (!ex.to_company    && d.to_company)    ex.to_company    = d.to_company;
    }
  });

  const rows = deduped.filter(d => !!(d.headline || d.from_company));
  el.innerHTML = rows.length
    ? `<div class="bda-list">${rows.map((d, i) => _bdaRowHtml(tabId, d, i)).join('')}</div>`
    : `<div class="bda-empty">No BD activity on record for this area.</div>`;
}

function _bdaFmtExact(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr + 'T00:00:00');
  if (isNaN(d)) return dateStr.slice(0, 10);
  return d.toLocaleString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
}
function _bdaFmtVal(d) {
  const fmt = n => n >= 1000 ? `$${(n/1000).toFixed(1)}B` : `$${n}M`;
  if (d.upfront_usd_m && d.total_usd_m) return `${fmt(d.upfront_usd_m)} upfront · ${fmt(d.total_usd_m)} total`;
  if (d.upfront_usd_m) return `${fmt(d.upfront_usd_m)} upfront`;
  if (d.total_usd_m)   return `${fmt(d.total_usd_m)} total`;
  return '';
}
function _bdaRowHtml(tabId, d, i) {
  const tc      = _BDA_TYPE_COLOR[d.deal_type] || '#6b7280';
  const dateStr = _bdaFmtExact(d.deal_date);
  const val     = _bdaFmtVal(d);
  const hl      = d.headline || `${d.from_company || ''} × ${d.to_company || ''} deal`;
  const rowId   = `${tabId}-bda-row-${i}`;
  const hasDetail = !!(d.detail || d.ailux_signal);

  return `<div class="bda-row${hasDetail ? '' : ' bda-no-expand'}" id="${rowId}">
    <div class="bda-compact"${hasDetail ? ` onclick="_bdaToggleRow('${rowId}')"` : ''}>
      <div class="bda-main-col">
        <div class="bda-meta-row">
          ${dateStr ? `<span class="bda-exact-date">${dateStr}</span>` : ''}
          <span class="bda-type" style="background:${tc}18;color:${tc}">${d.deal_type || 'deal'}</span>
          ${val ? `<span class="bda-value">${val}</span>` : ''}
        </div>
        ${d.source_url ? `<a class="bda-hl-link" href="${d.source_url}" target="_blank" rel="noopener" onclick="event.stopPropagation()">${hl}</a>` : `<span class="bda-hl-link" style="cursor:default">${hl}</span>`}
      </div>
      ${hasDetail ? `<span class="bda-chevron">▶</span>` : ''}
    </div>
    ${hasDetail ? `<div class="bda-detail">
      ${d.detail ? `<div class="bda-detail-text">${d.detail}</div>` : ''}
      ${d.ailux_signal ? `<div class="bda-ailux-box">◈ Ailux Lens: ${d.ailux_signal}</div>` : ''}
    </div>` : ''}
  </div>`;
}

function _bdaToggleRow(rowId) {
  const row = document.getElementById(rowId);
  if (row) row.classList.toggle('bda-open');
}


// ── Molecule Tab Orchestrator (lazy-loads on first visit) ─────────────────────
// ── Tab → area_id map (some tabs share an area_id) ──────────────────────────
const TAB_AREA = {
  'tl1a': 'tl1a', 'tslp': 'tslp',
  'il4ra-tslp': 'il4ra', 'il4ra-ox40l': 'il4ra',
  'igf1r-tshr': 'igf1r', 'fcrn': 'fcrn', 'ace': 'tcell'
};

// ── Phase ordering for competitive table ─────────────────────────────────────
const PHASE_ORDER = {
  'Approved': 0, 'BLA Filed': 1, 'BLA filed': 1,
  'Phase 3': 2, 'Phase 2': 3, 'Phase 2/3': 2,
  'Phase 1/2': 4, 'Phase 1 (deprioritized)': 6,
  'Phase 1': 4, 'Phase 1b': 4, 'Preclinical': 5
};
const PHASE_COLOR = {
  'Approved':   '#dcfce7:#166534',
  'BLA Filed':  '#ede9fe:#5b21b6', 'BLA filed': '#ede9fe:#5b21b6',
  'Phase 3':    '#dbeafe:#1d4ed8',
  'Phase 2/3':  '#dbeafe:#1d4ed8',
  'Phase 2':    '#fef9c3:#854d0e',
  'Phase 1/2':  '#fce7f3:#9d174d',
  'Phase 1b':   '#fce7f3:#9d174d',
  'Phase 1':    '#fce7f3:#9d174d',
  'Phase 1 (deprioritized)': '#f1f5f9:#94a3b8',
  'Preclinical':'#f1f5f9:#64748b'
};

async function loadAreaCompetitors(tabId) {
  const areaId = TAB_AREA[tabId];
  const elId = tabId + '-live-competitive';
  const el = document.getElementById(elId);
  if (!el || !areaId) return;

  // Fetch drug_areas join drug details
  const { data: daRows, error: daErr } = await _sb
    .from('drug_areas')
    .select('drug_id, drugs(id, name, brand_name, company_id, mechanism, stage, ailux_angle, ailux_competes_directly, key_data, companies(name))')
    .eq('area_id', areaId);

  if (daErr || !daRows || !daRows.length) {
    el.innerHTML = '<div style="color:#94a3b8;font-size:12px">No competitive programs found.</div>';
    return;
  }

  // Deduplicate (drug can appear multiple times if multiple area_ids)
  const seen = new Set();
  const drugs = daRows
    .map(r => r.drugs).filter(d => d && !seen.has(d.id) && seen.add(d.id))
    .sort((a, b) => {
      const ao = PHASE_ORDER[a.stage] ?? 7, bo = PHASE_ORDER[b.stage] ?? 7;
      if (ao !== bo) return ao - bo;
      return (b.ailux_competes_directly ? 1 : 0) - (a.ailux_competes_directly ? 1 : 0);
    });

  function phasePill(stage) {
    const colors = (PHASE_COLOR[stage] || '#f1f5f9:#64748b').split(':');
    return `<span style="background:${colors[0]};color:${colors[1]};padding:2px 7px;border-radius:8px;font-size:9px;font-weight:700;white-space:nowrap">${stage || '?'}</span>`;
  }

  const rows = drugs.map(d => {
    const threat = d.ailux_competes_directly
      ? '<span style="background:#fef2f2;color:#dc2626;border:1px solid #fca5a5;padding:1px 5px;border-radius:4px;font-size:9px;font-weight:700">Direct</span>'
      : '<span style="background:#f1f5f9;color:#64748b;border:1px solid #e2e8f0;padding:1px 5px;border-radius:4px;font-size:9px;font-weight:700">Monitor</span>';
    const coName = d.companies ? d.companies.name : (d.company_id || '');
    // RULE: Show target (clean notation) not mechanism (verbose). Mechanism shown in expanded detail only.
    const targetDisplay = d.target || d.mechanism || '';
    const mech = targetDisplay.slice(0,55) + (targetDisplay.length > 55 ? '…' : '');
    const angle = (d.ailux_angle || d.key_data || '').slice(0, 90) + ((d.ailux_angle || d.key_data || '').length > 90 ? '…' : '');
    return `<tr style="border-bottom:1px solid #f1f5f9">
      <td style="padding:7px 10px;font-weight:600;font-size:12px;white-space:nowrap">${d.brand_name ? `<span class="drug-brand-name">${d.brand_name}</span>${d.name !== d.brand_name ? '<span class="drug-molecule-name">'+d.name+'</span>' : ''}` : d.name}</td>
      <td style="padding:7px 10px;font-size:11px;color:#374151;white-space:nowrap">${coName}</td>
      <td style="padding:7px 10px">${phasePill(d.stage)}</td>
      <td style="padding:7px 10px;font-size:10px;color:#475569">${mech}</td>
      <td style="padding:7px 10px">${threat}</td>
      <td style="padding:7px 10px;font-size:10px;color:#1e3a5f;line-height:1.4">${angle}</td>
    </tr>`;
  }).join('');

  el.innerHTML = `<div style="overflow-x:auto">
    <table style="width:100%;border-collapse:collapse;font-size:12px">
      <thead><tr style="background:#f8fafc">
        <th style="padding:6px 10px;text-align:left;font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:.04em;border-bottom:2px solid #dde3ea">Drug</th>
        <th style="padding:6px 10px;text-align:left;font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:.04em;border-bottom:2px solid #dde3ea">Company</th>
        <th style="padding:6px 10px;text-align:left;font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:.04em;border-bottom:2px solid #dde3ea">Stage</th>
        <th style="padding:6px 10px;text-align:left;font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:.04em;border-bottom:2px solid #dde3ea">Mechanism</th>
        <th style="padding:6px 10px;text-align:left;font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:.04em;border-bottom:2px solid #dde3ea">Threat</th>
        <th style="padding:6px 10px;text-align:left;font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:.04em;border-bottom:2px solid #dde3ea">Ailux Signal</th>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  </div>`;
}

// ── Area Companies Loader (placeholder — renders into tabId+'-companies' if present) ──
async function loadAreaCompanies(tabId) {
  const el = document.getElementById(tabId + '-companies');
  if (!el || typeof _sb === "undefined") return;
  const areas = TAB_AREA_MAP[tabId];
  if (!areas) return;
  try {
    const { data: rows, error } = await _sb.from('companies').select('id,name,ticker,insight_text,ailux_angle')
      .in('area_id', areas).order('name').limit(20);
    if (error || !rows || !rows.length) return;
    el.innerHTML = rows.map(c => `<div style="padding:6px 0;border-bottom:1px solid #f1f5f9;font-size:12px">
      <strong>${c.name}</strong>${c.ticker ? ` <span style="color:#94a3b8;font-size:11px">(${c.ticker})</span>` : ''}
      ${c.insight_text ? `<div style="font-size:11px;color:#4b5563;margin-top:2px">${c.insight_text}</div>` : ''}
    </div>`).join('');
  } catch(e) { console.warn('loadAreaCompanies', tabId, e); }
}

// ── Area Drugs Loader (placeholder — renders into tabId+'-drugs' if present) ──
async function loadAreaDrugs(tabId) {
  const el = document.getElementById(tabId + '-drugs');
  if (!el || typeof _sb === "undefined") return;
  const areaId = TAB_AREA[tabId];
  if (!areaId) return;
  try {
    const { data: rows, error } = await _sb.from('drug_areas').select('drug_id, drugs(id,name,brand_name,stage,mechanism)')
      .eq('area_id', areaId).limit(20);
    if (error || !rows || !rows.length) return;
    const drugs = rows.map(r => r.drugs).filter(Boolean);
    el.innerHTML = drugs.map(d => `<div style="padding:6px 0;border-bottom:1px solid #f1f5f9;font-size:12px">
      <span class="drug-brand-name">${d.brand_name || d.name}</span>${d.brand_name && d.name && d.name !== d.brand_name ? '<span class="drug-molecule-name">'+d.name+'</span>' : ''} · <span style="color:#64748b;font-size:11px">${d.stage||''}</span>
    </div>`).join('');
  } catch(e) { console.warn('loadAreaDrugs', tabId, e); }
}

function loadMoleculeTab(tabId) {
  if (_molTabLoaded[tabId]) return; // already loaded
  _molTabLoaded[tabId] = true;
  loadAreaIntel(tabId);
  loadAreaCatalysts(tabId);
  loadAreaDeals(tabId);
  loadAreaPI(tabId);           // replaces loadAreaCompetitors
  loadAreaBDActivity(tabId);
  if (TAB_LANDSCAPE_MAP?.[tabId]) loadLandscapeCoverage(tabId); // v32 coverage panel
  _loadAreaBriefs(tabId);      // Meridian landscape + strategic brief + patient briefs
  _injectAreaFreshness(tabId); // G15 fix: show last-enriched timestamp
}

// G15: inject last-enriched freshness into area tab header
async function _injectAreaFreshness(tabId) {
  try {
    // Find the area_id for this tab
    const areaId = (typeof TAB_AREA !== 'undefined' && TAB_AREA[tabId]) || tabId;
    const el = document.getElementById(tabId + '-freshness-badge');
    if (!el || !_sb) return;
    const { data } = await _sb.from('company_profiles')
      .select('last_enriched_at')
      .eq('area_id', areaId)
      .not('last_enriched_at', 'is', null)
      .order('last_enriched_at', { ascending: false })
      .limit(1);
    if (data?.[0]?.last_enriched_at) {
      el.innerHTML = _freshnessBadge(data[0].last_enriched_at);
    }
  } catch(e) {}
}

