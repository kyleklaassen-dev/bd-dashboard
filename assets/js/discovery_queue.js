// ══════════════════════════════════════════════════════════════════════════
// DISCOVERY QUEUE — Review and approve/reject candidates from Step 1
// ══════════════════════════════════════════════════════════════════════════

let _dqData   = [];          // all rows loaded from Supabase
let _dqStatus = 'pending';   // current status filter

const DQ_LAYER_LABEL = { 1: 'Direct', 2: 'Clinical', 3: 'Strategic' };
const DQ_LAYER_COLOR = { 1: '#dc2626', 2: '#d97706', 3: '#2563eb' };
const DQ_OVERLAP_COLOR = {
  'Direct': '#dc2626', 'Adjacent': '#d97706',
  'Same-Space': '#2563eb', 'Watch': '#64748b'
};
const DQ_DEST_LABEL = {
  'new_company':     '+ New Company',
  'molecule_update': '↑ Molecule',
  'trial_update':    '↑ Trial',
  'deal_update':     '↑ Deal',
  'catalyst_update': '↑ Catalyst',
  'evidence_update': '↑ Evidence',
  'research_queue':  '→ Research Q',
};

async function dqLoad() {
  const wrap  = document.getElementById('dq-loading');
  const table = document.getElementById('dq-table');
  const empty = document.getElementById('dq-empty');
  if (wrap)  { wrap.style.display = 'block'; wrap.textContent = 'Loading…'; }
  if (table)  table.style.display = 'none';
  if (empty)  empty.style.display = 'none';

  try {
    const { data, error } = await _sb.from('discovery_queue')
      .select('*')
      .order('relevance_score', { ascending: false })
      .order('discovered_at',   { ascending: false })
      .limit(500);
    if (error) throw error;
    _dqData = data || [];
    await _dqLoadReview();   // NEW 2026-06-06: pull research-queue gaps + flagged items into the queue
    dqRenderStats();
    dqRender();
  } catch(e) {
    if (wrap) { wrap.style.display = 'block'; wrap.textContent = 'Error loading queue: ' + e.message; }
  }
}

function dqFilterStatus(status) {
  _dqStatus = status;
  document.querySelectorAll('.dq-stab').forEach(b => {
    const active = b.dataset.status === status;
    b.style.background    = active ? '#2563eb' : 'white';
    b.style.color         = active ? 'white'   : '#374151';
    b.style.borderColor   = active ? '#2563eb' : '#d1d5db';
    b.style.fontWeight    = active ? '700'      : '400';
  });
  dqRender();
}

function dqRenderStats() {
  const el = document.getElementById('dq-stats');
  if (!el) return;
  const counts = { pending:0, approved:0, rejected:0, watch:0, archived:0 };
  const byRel  = { critical:0, important:0, watch_r:0 };
  _dqData.forEach(r => {
    counts[r.status] = (counts[r.status]||0) + 1;
    // Use strategic_value_score when available; fall back to relevance_score for older rows
    const svs = r.strategic_value_score ?? r.relevance_score ?? 0;
    if (svs >= 9) byRel.critical++;
    else if (svs >= 7) byRel.important++;
    else if (svs >= 5) byRel.watch_r++;
  });
  // Update pending badge in tab header
  const badge = document.getElementById('dq-pending-badge');
  if (badge) { badge.textContent = counts.pending || ''; badge.style.display = counts.pending ? 'inline-block' : 'none'; }
  // Update nav badge (red dot for critical pending items) — DEPRECATED node, guarded
  const navBadge = document.getElementById('dq-nav-badge');
  if (navBadge) { navBadge.style.display = byRel.critical > 0 ? 'block' : 'none'; }
  // NEW 2026-06-06: Needs-Review count badge on the filter button
  const revBadge = document.getElementById('dq-review-count');
  const revN = (_dqReviewItems && _dqReviewItems.length) || 0;
  if (revBadge) { revBadge.textContent = revN; revBadge.style.display = revN ? 'inline-block' : 'none'; }

  el.innerHTML = [
    { label: 'Pending Review', val: counts.pending,  color: '#2563eb' },
    { label: '⚡ Critical (9–10)', val: byRel.critical,  color: '#dc2626' },
    { label: 'Important (7–8)', val: byRel.important, color: '#d97706' },
    { label: 'Approved', val: counts.approved, color: '#059669' },
    { label: 'Watch', val: counts.watch, color: '#7c3aed' },
    { label: 'Rejected', val: counts.rejected, color: '#94a3b8' },
  ].map(s => `
    <div style="background:white;border:1px solid #e2e8f0;border-radius:8px;padding:10px 14px;min-width:100px;text-align:center;box-shadow:0 1px 2px rgba(0,0,0,0.04)">
      <div style="font-size:18px;font-weight:800;color:${s.color}">${s.val}</div>
      <div style="font-size:10px;color:#64748b;font-weight:600;margin-top:2px">${s.label}</div>
    </div>`).join('');
}

function dqRender() {
  const tbody = document.getElementById('dq-tbody');
  const table = document.getElementById('dq-table');
  const empty = document.getElementById('dq-empty');
  const loading = document.getElementById('dq-loading');
  if (!tbody) return;

  // NEW 2026-06-06: "Needs Review" mode renders the unified review surface instead of the discovery table.
  const _tableWrap  = document.getElementById('dq-table-wrap');
  const _reviewWrap = document.getElementById('dq-review-wrap');
  if (_dqStatus === 'review') {
    if (_tableWrap)  _tableWrap.style.display  = 'none';
    if (_reviewWrap) _reviewWrap.style.display = 'block';
    dqRenderReview();
    return;
  } else {
    if (_reviewWrap) _reviewWrap.style.display = 'none';
    if (_tableWrap)  _tableWrap.style.display  = '';
  }

  const areaF   = document.getElementById('dq-area-filter')?.value  || '';
  const sourceF = document.getElementById('dq-source-filter')?.value || '';
  const sortV   = document.getElementById('dq-sort')?.value          || 'relevance';

  let rows = _dqData.filter(r => {
    if (_dqStatus !== 'all' && r.status !== _dqStatus) return false;
    if (areaF && r.area_id !== areaF && r.target_id !== areaF) return false;
    if (sourceF) {
      const rowSource = r.source || (r.discovered_by === 'company_intake' ? 'user_intake' : 'signal_monitoring');
      if (rowSource !== sourceF) return false;
    }
    return true;
  });

  rows.sort((a, b) => {
    if (sortV === 'strategic') {
      // BD Priority: strategic_value_score DESC (nulls last → fall back to relevance_score)
      // then relevance_score DESC, then newest
      const asvs = a.strategic_value_score ?? a.relevance_score ?? 0;
      const bsvs = b.strategic_value_score ?? b.relevance_score ?? 0;
      return bsvs - asvs
          || (b.relevance_score||0) - (a.relevance_score||0)
          || new Date(b.discovered_at||0) - new Date(a.discovered_at||0);
    }
    if (sortV === 'relevance') return (b.relevance_score||0) - (a.relevance_score||0);
    if (sortV === 'layer')     return (a.competition_layer||9) - (b.competition_layer||9);
    if (sortV === 'area')      return (a.area_id||'').localeCompare(b.area_id||'');
    if (sortV === 'recent')    return new Date(b.discovered_at||0) - new Date(a.discovered_at||0);
    return 0;
  });

  if (loading) loading.style.display = 'none';
  if (!rows.length) {
    if (table) table.style.display = 'none';
    if (empty) empty.style.display = 'block';
    return;
  }
  if (table) table.style.display = 'table';
  if (empty) empty.style.display = 'none';

  tbody.innerHTML = rows.map(r => {
    const rel    = r.relevance_score || 0;
    const svs    = r.strategic_value_score ?? rel;
    const svsBadge = svs >= 9
      ? `<span style="font-size:9px;font-weight:800;background:#fef2f2;color:#991b1b;border:1px solid #fca5a5;padding:2px 7px;border-radius:8px;display:inline-block">⚡ Critical</span>`
      : svs >= 7
      ? `<span style="font-size:9px;font-weight:800;background:#fff7ed;color:#9a3412;border:1px solid #fdba74;padding:2px 7px;border-radius:8px;display:inline-block">↑ High</span>`
      : svs >= 5
      ? `<span style="font-size:9px;font-weight:800;background:#eff6ff;color:#1e40af;border:1px solid #93c5fd;padding:2px 7px;border-radius:8px;display:inline-block">Med</span>`
      : svs >= 1
      ? `<span style="font-size:9px;font-weight:800;background:#f8fafc;color:#64748b;border:1px solid #cbd5e1;padding:2px 7px;border-radius:8px;display:inline-block">Low</span>`
      : `<span style="color:#cbd5e1;font-size:11px">—</span>`;
    const layer  = r.competition_layer;
    const layerLbl = layer ? DQ_LAYER_LABEL[layer] || ('L'+layer) : '—';
    const layerCol = layer ? DQ_LAYER_COLOR[layer]  || '#94a3b8'  : '#94a3b8';
    const overlapCol = DQ_OVERLAP_COLOR[r.overlap] || '#94a3b8';
    const destLbl = DQ_DEST_LABEL[r.suggested_dest] || r.suggested_dest || '—';
    const priority = svs >= 9 ? '⚡ ' : '';
    const date = r.discovered_at ? new Date(r.discovered_at).toLocaleDateString('en-US',{month:'short',day:'numeric'}) : '';

    const isPending  = r.status === 'pending';
    const isApproved = r.status === 'approved';
    const isRejected = r.status === 'rejected';
    const isWatch    = r.status === 'watch';

    // ── Source badge ─────────────────────────────────────────────────────────
    // Detect user_intake from source column (post-migration) or discovered_by field (fallback)
    const isUserIntake = r.source === 'user_intake' || r.discovered_by === 'company_intake';
    const isSignal     = !isUserIntake && (r.source === 'signal_monitoring' || r.discovered_by?.startsWith('step'));
    const sourceBadge  = isUserIntake
      ? `<span style="font-size:9px;font-weight:700;background:#fef3c7;color:#92400e;border:1px solid #fcd34d;padding:1px 6px;border-radius:8px;margin-top:3px;display:inline-block">🔍 User Intake</span>`
      : isSignal
      ? `<span style="font-size:9px;font-weight:700;background:#eff6ff;color:#1e40af;border:1px solid #bfdbfe;padding:1px 6px;border-radius:8px;margin-top:3px;display:inline-block">📡 Signal Monitor</span>`
      : '';

    // ── Intelligence display ──────────────────────────────────────────────────
    // For user intake rows: show why_discovered prominently (area routing context)
    // For signal rows: show reason + rationale as before
    const intelligenceCell = isUserIntake
      ? `<div style="font-size:11px;color:#374151;line-height:1.4;font-weight:600">${_esc(r.overlap||'')} relevance to ${_esc(r.area_id||'')}</div>
         ${r.relevance_rationale ? `<div style="font-size:11px;color:#374151;line-height:1.4;margin-top:3px">${_esc(r.relevance_rationale.slice(0,150))}${(r.relevance_rationale||'').length>150?'…':''}</div>` : ''}
         ${r.why_discovered ? `<div style="font-size:10px;color:#64748b;margin-top:4px;padding:4px 7px;background:#fffbeb;border-left:2px solid #f59e0b;border-radius:0 4px 4px 0;line-height:1.4">${_esc(r.why_discovered.slice(0,200))}${(r.why_discovered||'').length>200?'…':''}</div>` : ''}`
      : `<div style="font-size:11px;color:#374151;line-height:1.4">${_esc(r.reason||'')}</div>
         ${r.relevance_rationale ? `<div style="font-size:10px;color:#94a3b8;margin-top:3px;font-style:italic">${_esc(r.relevance_rationale.slice(0,120))}${(r.relevance_rationale||'').length>120?'…':''}</div>` : ''}
         ${r.source_url ? `<a href="${_esc(r.source_url)}" target="_blank" style="font-size:10px;color:#2563eb;text-decoration:none">↗ source</a>` : ''}`;

    // ── Row highlight ─────────────────────────────────────────────────────────
    const rowBg = isUserIntake ? 'background:#fffdf5' : svs >= 9 ? 'background:#fff7f7' : '';

    return `<tr style="border-bottom:1px solid #f1f5f9;${rowBg}">
      <td style="padding:10px 14px;max-width:220px">
        <div style="font-weight:700;color:#0f172a;font-size:12px">${priority}${_esc(r.company_name)}</div>
        ${sourceBadge}
        ${r.drug_name ? `<div style="font-size:11px;color:#64748b;margin-top:2px">${_esc(r.drug_name)}${r.target ? ` · ${_esc(r.target)}` : ''}</div>` : ''}
        ${r.stage ? `<div style="font-size:10px;color:#94a3b8;margin-top:1px">${_esc(r.stage)}</div>` : ''}
        <div style="font-size:10px;color:#cbd5e1;margin-top:2px">${date}</div>
      </td>
      <td style="padding:10px;text-align:center">
        <span style="font-size:10px;font-weight:700;background:#f1f5f9;padding:2px 7px;border-radius:10px;color:#374151">${r.area_id||'—'}</span>
      </td>
      <td style="padding:10px;text-align:center">
        ${layer ? `<span style="font-size:10px;font-weight:700;color:${layerCol};background:${layerCol}18;padding:2px 7px;border-radius:10px">L${layer} ${layerLbl}</span>` : '<span style="color:#94a3b8">—</span>'}
      </td>
      <td style="padding:10px;text-align:center">
        ${r.overlap ? `<span style="font-size:10px;font-weight:700;color:${overlapCol};background:${overlapCol}18;padding:2px 7px;border-radius:10px">${r.overlap}</span>` : '<span style="color:#94a3b8">—</span>'}
      </td>
      <td style="padding:10px;text-align:center">
        ${svsBadge}
        <div style="font-size:9px;color:#cbd5e1;margin-top:3px">${svs}</div>
      </td>
      <td style="padding:10px;text-align:center">
        <span style="font-size:11px;color:#64748b">${r.confidence_score||'—'}</span>
      </td>
      <td style="padding:10px 14px;max-width:280px">
        ${intelligenceCell}
      </td>
      <td style="padding:10px 14px">
        <span style="font-size:10px;font-weight:700;color:#374151;background:#f8fafc;padding:2px 7px;border-radius:6px;border:1px solid #e2e8f0">${_esc(destLbl)}</span>
      </td>
      <td style="padding:10px 14px;text-align:center;white-space:nowrap">
        ${isPending ? `
          <button onclick="dqAction('${r.id}','approved')" title="Approve — promote to dashboard" style="font-size:10px;padding:4px 9px;border-radius:5px;border:none;background:#059669;color:white;cursor:pointer;font-weight:700;margin:1px">✓</button>
          <button onclick="dqAction('${r.id}','watch')" title="Watch — park for later" style="font-size:10px;padding:4px 9px;border-radius:5px;border:none;background:#7c3aed;color:white;cursor:pointer;font-weight:700;margin:1px">👁</button>
          <button onclick="dqAction('${r.id}','rejected')" title="Reject — not relevant" style="font-size:10px;padding:4px 9px;border-radius:5px;border:none;background:#dc2626;color:white;cursor:pointer;font-weight:700;margin:1px">✗</button>
          <button onclick="dqShowDetail('${r.id}')" title="View full detail" style="font-size:10px;padding:4px 9px;border-radius:5px;border:1px solid #d1d5db;background:white;color:#374151;cursor:pointer;margin:1px">⋯</button>
        ` : isApproved ? `
          <span style="font-size:11px;color:#059669;font-weight:700">✓ Approved</span>
          <button onclick="dqAction('${r.id}','pending')" style="font-size:10px;padding:3px 7px;border-radius:5px;border:1px solid #d1d5db;background:white;color:#374151;cursor:pointer;margin-left:4px">Undo</button>
        ` : isRejected ? `
          <span style="font-size:11px;color:#94a3b8;font-weight:700">✗ Rejected</span>
          <button onclick="dqAction('${r.id}','pending')" style="font-size:10px;padding:3px 7px;border-radius:5px;border:1px solid #d1d5db;background:white;color:#374151;cursor:pointer;margin-left:4px">Re-open</button>
        ` : isWatch ? `
          <span style="font-size:11px;color:#7c3aed;font-weight:700">👁 Watch</span>
          <button onclick="dqAction('${r.id}','pending')" style="font-size:10px;padding:3px 7px;border-radius:5px;border:1px solid #d1d5db;background:white;color:#374151;cursor:pointer;margin-left:4px">Re-open</button>
        ` : `<span style="font-size:11px;color:#94a3b8">${r.status}</span>`}
      </td>
    </tr>`;
  }).join('');
}

function _esc(s) {
  if (!s) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ════════════════════════════════════════════════════════════════════════════
// NEW 2026-06-06 — Discovery Queue · unified "Needs Review" surface
// Consolidates the old red Research-Queue pill (research_queue) and the yellow
// review pill (governance_violations) into one place. Each item carries a
// SPECIFIC verification question so Kyle knows exactly what is unknown / to check.
// ════════════════════════════════════════════════════════════════════════════
let _dqReviewItems = [];

// Build a concrete, human-readable verification question for a review item.
function _dqReviewQuestion(it) {
  const n = it.name || 'this item';
  if (it.kind === 'flag') {
    switch (it.rule_name) {
      case 'missing_originator':
      case 'missing_originator_obscure':
        return `Who is the originator (developer) company for ${n}?`;
      case 'mechanism_target_inconsistency':
      case 'hallucinated_mechanism':
        return `Is ${n}'s stated mechanism/target correct? A check flagged a mismatch — verify against a primary source.`;
      case 'trial_id_misattribution':
        return `Is the trial attributed to ${n} actually for this drug? Verify the NCT ID and sponsor.`;
      case 'area_misclassification':
        return `Is ${n} classified in the right disease area? A check flagged a possible misclassification.`;
      case 'source_does_not_support_claim':
        return `Does the cited source actually support the claim for ${n}? Re-verify the source.`;
      case 'misingested_out_of_scope':
        return `Is ${n} actually in scope for Meridian, or was it mis-ingested?`;
      case 'ambiguous_identity':
        return `Which entity does ${n} refer to? Resolve the ambiguous identity.`;
      default:
        return it.description ? `Verify: ${it.description}` : `Review the flagged data for ${n}.`;
    }
  }
  // research_queue gap
  const gap = (it.reason || it.action || '').trim();
  const pct = (it.completeness != null) ? ` (currently ${Math.round(it.completeness)}% complete)` : '';
  return gap
    ? `What's still unknown for ${n}? ${gap}${pct}`
    : `What key facts is ${n} missing? Verify and complete its profile${pct}.`;
}

async function _dqLoadReview() {
  try {
    const rq = await _loadResearchQueue();   // research_queue (returns array)
    await _loadReviewQueue();                 // side-effect: populates _reviewNeedsDecision
    const flags = (_reviewNeedsDecision || []).map(v => ({
      kind: 'flag',
      id: v.id,
      name: (String(v.row_id || '').split(',')[0] || '').trim() || v.table_name || '—',
      row_id: v.row_id,
      rule_name: v.rule_name,
      description: v.description,
      created_at: v.detected_at,
    }));
    const research = (rq || []).map(it => ({
      kind: 'research',
      id: it.id,
      name: it.entity_name || it.entity_id || '—',
      entity_id: it.entity_id,
      reason: it.reason,
      action: it.next_best_action,
      completeness: it.completeness_score,
      created_at: it.created_at,
    }));
    _dqReviewItems = flags.concat(research);   // data flags first (need judgment), then research gaps
  } catch(e) {
    console.warn('dq review load error', e);
    _dqReviewItems = [];
  }
  return _dqReviewItems;
}

function _dqAge(ts) {
  if (!ts) return '';
  const d = Math.floor((Date.now() - new Date(ts)) / 86400000);
  if (d <= 0) return 'today';
  if (d === 1) return '1d ago';
  if (d < 30) return d + 'd ago';
  return Math.floor(d / 30) + 'mo ago';
}

function dqRenderReview() {
  const wrap = document.getElementById('dq-review-wrap');
  if (!wrap) return;
  const items = _dqReviewItems || [];
  if (!items.length) {
    wrap.innerHTML = `<div style="background:white;border:1px solid #e2e8f0;border-radius:10px;padding:48px;text-align:center;color:#94a3b8;font-size:13px">Nothing needs review — the pipeline is up to date. ✅</div>`;
    return;
  }
  const flags    = items.filter(i => i.kind === 'flag');
  const research = items.filter(i => i.kind === 'research');

  function card(it) {
    const q = _esc(_dqReviewQuestion(it));
    const isFlag = it.kind === 'flag';
    const chip = isFlag
      ? `<span style="font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.03em;background:#fffbeb;color:#b45309;border:1px solid #fde68a;border-radius:8px;padding:2px 8px">⚑ Data flag</span>`
      : `<span style="font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.03em;background:#eff6ff;color:#1e40af;border:1px solid #bfdbfe;border-radius:8px;padding:2px 8px">🔍 Research gap</span>`;
    const links = isFlag
      ? `<div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:6px">${_reviewDrugLinks(it.row_id)}</div>`
      : `<div style="margin-top:6px"><a href="#" data-trusted="1" onclick="event.preventDefault();openDrugEntityModal('${_esc(it.entity_id)}','${_esc(it.name)}',null)" style="font-size:11px;color:#2563eb;text-decoration:none">${_esc(it.name)}</a> 🔍</div>`;
    const ctx = isFlag
      ? (it.description ? `<div style="font-size:11px;color:#64748b;line-height:1.45;margin-top:6px">${_esc(it.description)}</div>` : '')
      : (it.action ? `<div style="font-size:11px;color:#64748b;line-height:1.45;margin-top:6px"><strong>Suggested step:</strong> ${_esc(it.action)}</div>` : '');
    const actions = isFlag
      ? `<button onclick="dqReviewResolve('${it.id}',this)" title="Mark this flag resolved" style="font-size:10px;font-weight:700;padding:5px 11px;border-radius:6px;border:none;background:#059669;color:white;cursor:pointer">✓ Resolved</button>`
      : `<button onclick="_dqResearchNow('${it.id}','${_esc(it.name).replace(/'/g, "\\'")}')" title="Queue this item for the next pipeline run" style="font-size:10px;font-weight:700;padding:5px 11px;border-radius:6px;border:1px solid #2563eb;background:white;color:#2563eb;cursor:pointer">▶ Research Now</button>`;
    return `<div style="background:white;border:1px solid #e2e8f0;border-left:3px solid ${isFlag ? '#f59e0b' : '#3b82f6'};border-radius:8px;padding:12px 14px;margin-bottom:10px">
      <div style="display:flex;align-items:center;gap:8px">${chip}<span style="font-size:10px;color:#94a3b8;margin-left:auto">${_dqAge(it.created_at)}</span></div>
      <div style="font-size:13px;font-weight:700;color:#0f172a;line-height:1.4;margin-top:8px">${q}</div>
      ${links}
      ${ctx}
      <div style="margin-top:10px">${actions}</div>
    </div>`;
  }

  function section(title, sub, arr) {
    if (!arr.length) return '';
    return `<div style="margin-bottom:18px">
      <div style="font-size:12px;font-weight:800;color:#0f172a;margin-bottom:2px">${title} <span style="color:#94a3b8;font-weight:700">· ${arr.length}</span></div>
      <div style="font-size:11px;color:#64748b;margin-bottom:10px">${sub}</div>
      ${arr.map(card).join('')}
    </div>`;
  }

  wrap.innerHTML =
    `<div style="background:#fffbeb;border:1px solid #fde68a;border-radius:10px;padding:12px 16px;margin-bottom:16px;font-size:12px;color:#92400e;line-height:1.5">
       <strong>Everything that needs your eyes, in one place.</strong> Each item asks a specific question — the exact thing Meridian can't confirm on its own. Answer it (verify a source, confirm a company, or queue research) and it clears.
     </div>` +
    section('⚑ Data integrity flags', 'A check found something that may be wrong — your judgment decides.', flags) +
    section('🔍 Research gaps', 'Known unknowns the pipeline can fill — queue them for the next run.', research);
}

async function dqReviewResolve(id, btn) {
  if (btn) { btn.disabled = true; btn.textContent = '…'; }
  try {
    const { error } = await _sb.from('governance_violations')
      .update({ resolved: true, resolution_notes: 'Resolved via Discovery Queue review ' + new Date().toISOString().slice(0, 10) })
      .eq('id', id);
    if (error) throw error;
    _reviewNeedsDecision = (_reviewNeedsDecision || []).filter(v => v.id !== id);
    _dqReviewItems = _dqReviewItems.filter(x => !(x.kind === 'flag' && x.id === id));
    dqRenderStats();
    dqRender();
  } catch(e) {
    if (btn) { btn.disabled = false; btn.textContent = '✓ Resolved'; }
    alert('Could not mark resolved (writes may be restricted): ' + (e.message || e));
  }
}

async function dqAction(id, newStatus, extraPatch = null) {
  // Optimistically update local data
  const row = _dqData.find(r => r.id === id);
  if (!row) return;
  const oldStatus = row.status;
  row.status = newStatus;
  row.reviewed_at = new Date().toISOString();
  if (extraPatch) Object.assign(row, extraPatch);  // optimistic update for overrides
  dqRenderStats();
  dqRender();

  try {
    const patch = {
      status:      newStatus,
      reviewed_at: new Date().toISOString(),
      reviewed_by: 'kyle',
      ...(extraPatch || {}),   // merge any overrides (e.g. relationship_type)
    };
    const { error } = await _sb.from('discovery_queue').update(patch).eq('id', id);
    if (error) throw error;
    if (newStatus === 'approved') {
      dqShowApprovedNote(row);
    }
  } catch(e) {
    // Roll back optimistic update
    row.status = oldStatus;
    row.reviewed_at = null;
    if (extraPatch) Object.keys(extraPatch).forEach(k => delete row[k]);
    dqRenderStats();
    dqRender();
    console.error('dqAction error:', e);
    alert('Error updating queue item: ' + e.message);
  }
}

function dqShowApprovedNote(row) {
  const msg = `✓ "${row.company_name}" approved.\n\nTo promote to the dashboard, run:\n  python src/meridian/enrichment/company_enrichment.py --area ${row.area_id} --company ${row.company_id_suggested||row.company_name.toLowerCase().replace(/[^a-z0-9]/g,'')}\n\nOr use the promotion script (coming soon).`;
  // Show a non-blocking toast instead of alert
  const toast = document.createElement('div');
  toast.textContent = `✓ ${row.company_name} approved — run enrichment to promote to dashboard`;
  Object.assign(toast.style, {
    position:'fixed', bottom:'24px', left:'50%', transform:'translateX(-50%)',
    background:'#059669', color:'white', padding:'10px 20px', borderRadius:'8px',
    fontSize:'12px', fontWeight:'700', zIndex:'99999', boxShadow:'0 4px 12px rgba(0,0,0,0.2)',
    maxWidth:'480px', textAlign:'center'
  });
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 4500);
}

async function dqBulkApproveHighConf() {
  const THRESHOLD = 80;
  const candidates = _dqData.filter(r => r.status === 'pending' && (r.confidence_score || 0) >= THRESHOLD);
  if (!candidates.length) {
    alert(`No pending items with confidence ≥ ${THRESHOLD} found.`);
    return;
  }
  const btn = document.getElementById('dq-bulk-approve-btn');
  if (btn) { btn.disabled = true; btn.textContent = `Approving ${candidates.length}…`; }

  let approved = 0, failed = 0;
  const now = new Date().toISOString();
  for (const row of candidates) {
    try {
      const { error } = await _sb.from('discovery_queue').update({
        status:      'approved',
        reviewed_at: now,
        reviewed_by: 'kyle',
      }).eq('id', row.id);
      if (error) throw error;
      row.status = 'approved';
      row.reviewed_at = now;
      approved++;
    } catch(e) {
      console.error('bulk approve error:', row.id, e);
      failed++;
    }
  }

  if (btn) { btn.disabled = false; btn.innerHTML = '⚡ Approve ≥80 conf'; }
  dqRenderStats();
  dqRender();

  // Toast
  const toast = document.createElement('div');
  toast.textContent = `✓ ${approved} item${approved !== 1 ? 's' : ''} approved${failed ? ` · ${failed} failed` : ''} — run enrichment to promote to dashboard`;
  Object.assign(toast.style, {
    position:'fixed', bottom:'24px', left:'50%', transform:'translateX(-50%)',
    background: failed ? '#dc2626' : '#059669', color:'white', padding:'10px 20px', borderRadius:'8px',
    fontSize:'12px', fontWeight:'700', zIndex:'99999', boxShadow:'0 4px 12px rgba(0,0,0,0.2)',
    maxWidth:'540px', textAlign:'center'
  });
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 5000);
}

// Relationship type display config
const DQ_REL_TYPE_LABEL = {
  peer_competitor:    'Peer Competitor',
  direct_competitor:  'Direct Competitor',
  adjacent_competitor:'Adjacent Competitor',
  licensor:           'Licensor',
  licensee:           'Licensee',
  partner:            'Partner',
  co_developer:       'Co-Developer',
  parent_subsidiary:  'Parent/Subsidiary',
  asset_owner:        'Asset Owner',
  unknown:            'Unknown',
};
const DQ_REL_TYPE_COLOR = {
  peer_competitor:    '#2563eb',
  direct_competitor:  '#dc2626',
  adjacent_competitor:'#d97706',
  licensor:           '#7c3aed',
  licensee:           '#7c3aed',
  partner:            '#059669',
  co_developer:       '#059669',
  parent_subsidiary:  '#64748b',
  asset_owner:        '#0f172a',
  unknown:            '#94a3b8',
};
const DQ_REL_CONF_COLOR = {
  confirmed: '#059669',
  inferred:  '#d97706',
  suggested: '#94a3b8',
};

function dqShowDetail(id) {
  const row = _dqData.find(r => r.id === id);
  if (!row) return;
  const panel  = document.getElementById('dq-detail-panel');
  const overlay = document.getElementById('dq-detail-overlay');
  if (!panel || !overlay) return;

  const rel    = row.relevance_score || 0;
  const relCls = rel >= 9 ? '#dc2626' : rel >= 7 ? '#d97706' : rel >= 5 ? '#2563eb' : '#94a3b8';
  const layer  = row.competition_layer;
  const date   = row.discovered_at ? new Date(row.discovered_at).toLocaleString() : '—';

  // Relationship fields (v10)
  const relType  = row.relationship_type || 'unknown';
  const relConf  = row.relationship_confidence || 'suggested';
  const relTypeLabel = DQ_REL_TYPE_LABEL[relType] || relType;
  const relTypeColor = DQ_REL_TYPE_COLOR[relType] || '#94a3b8';
  const relConfColor = DQ_REL_CONF_COLOR[relConf] || '#94a3b8';

  panel.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:20px">
      <div>
        <div style="font-size:18px;font-weight:800;color:#0f172a">${_esc(row.company_name)}</div>
        ${row.drug_name ? `<div style="font-size:13px;color:#64748b;margin-top:4px">${_esc(row.drug_name)}${row.target?` · ${_esc(row.target)}`:''}</div>` : ''}
      </div>
      <button onclick="dqCloseDetail()" style="background:none;border:none;font-size:20px;color:#94a3b8;cursor:pointer;padding:0 4px">×</button>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:20px">
      ${[
        ['Area', row.area_id||'—'],
        ['Stage', row.stage||'—'],
        ['Entity Type', row.entity_type||'—'],
        ['Modality', row.modality||'—'],
        ['Route', row.route||'—'],
        ['Overlap', row.overlap||'—'],
        ['Layer', layer ? `L${layer} ${DQ_LAYER_LABEL[layer]||''}` : '—'],
        ['Destination', DQ_DEST_LABEL[row.suggested_dest]||row.suggested_dest||'—'],
      ].map(([k,v]) => `
        <div style="background:#f8fafc;border-radius:6px;padding:8px 10px">
          <div style="font-size:10px;color:#94a3b8;font-weight:700;text-transform:uppercase;letter-spacing:0.5px">${k}</div>
          <div style="font-size:12px;font-weight:600;color:#374151;margin-top:2px">${_esc(String(v))}</div>
        </div>`).join('')}
    </div>

    <div style="display:flex;gap:12px;margin-bottom:20px">
      <div style="text-align:center;flex:1;background:#f8fafc;border-radius:8px;padding:12px">
        <div style="font-size:26px;font-weight:900;color:${relCls}">${rel}</div>
        <div style="font-size:10px;color:#64748b;font-weight:700">RELEVANCE</div>
      </div>
      <div style="text-align:center;flex:1;background:#f8fafc;border-radius:8px;padding:12px">
        <div style="font-size:26px;font-weight:900;color:#374151">${row.confidence_score||'—'}</div>
        <div style="font-size:10px;color:#64748b;font-weight:700">CONFIDENCE</div>
      </div>
    </div>

    <!-- Relationship Classification (v10) -->
    <div style="margin-bottom:16px;background:#f8fafc;border-radius:8px;padding:12px 14px;border-left:3px solid ${relTypeColor}">
      <div style="font-size:10px;color:#94a3b8;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px">Relationship Classification</div>
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
        <span style="font-size:12px;font-weight:700;color:${relTypeColor};background:${relTypeColor}18;padding:3px 8px;border-radius:4px">${_esc(relTypeLabel)}</span>
        <span style="font-size:11px;color:${relConfColor};font-weight:600">${_esc(relConf)}</span>
      </div>
      ${row.why_discovered ? `<div style="font-size:11px;color:#64748b;line-height:1.4;margin-bottom:8px">${_esc(row.why_discovered)}</div>` : ''}
      ${row.status === 'pending' ? `
      <div style="margin-top:8px">
        <div style="font-size:10px;color:#94a3b8;font-weight:600;margin-bottom:4px">Override relationship type:</div>
        <select id="dq-rel-override-${row.id}" style="font-size:11px;padding:4px 6px;border-radius:5px;border:1px solid #d1d5db;width:100%;background:white">
          ${Object.entries(DQ_REL_TYPE_LABEL).map(([v,l]) =>
            `<option value="${v}"${v===relType?' selected':''}>${l}</option>`
          ).join('')}
        </select>
      </div>` : ''}
    </div>

    ${row.reason ? `
      <div style="margin-bottom:14px">
        <div style="font-size:10px;color:#94a3b8;font-weight:700;text-transform:uppercase;margin-bottom:5px">Why It Matters</div>
        <div style="font-size:12px;color:#374151;line-height:1.5;background:#f8fafc;padding:10px 12px;border-radius:7px">${_esc(row.reason)}</div>
      </div>` : ''}

    ${row.relevance_rationale ? `
      <div style="margin-bottom:14px">
        <div style="font-size:10px;color:#94a3b8;font-weight:700;text-transform:uppercase;margin-bottom:5px">Relevance Rationale</div>
        <div style="font-size:12px;color:#374151;line-height:1.5;background:#f8fafc;padding:10px 12px;border-radius:7px">${_esc(row.relevance_rationale)}</div>
      </div>` : ''}

    ${row.partner_co ? `<div style="margin-bottom:10px;font-size:12px;color:#374151"><strong>Partner:</strong> ${_esc(row.partner_co)}</div>` : ''}
    ${row.acquired_by ? `<div style="margin-bottom:10px;font-size:12px;color:#dc2626"><strong>Acquired by:</strong> ${_esc(row.acquired_by)}</div>` : ''}
    ${row.source_url ? `<div style="margin-bottom:14px"><a href="${_esc(row.source_url)}" target="_blank" style="font-size:12px;color:#2563eb">↗ View source</a></div>` : ''}

    <div style="font-size:10px;color:#94a3b8;margin-bottom:20px">Discovered: ${date} · by ${_esc(row.discovered_by||'')}</div>

    ${row.status === 'pending' ? `
    <div style="display:flex;gap:8px;flex-direction:column">
      <button onclick="dqApproveWithOverride('${row.id}')" style="padding:10px;border-radius:8px;border:none;background:#059669;color:white;font-size:13px;font-weight:700;cursor:pointer;width:100%">✓ Approve</button>
      <div style="display:flex;gap:8px">
        <button onclick="dqAction('${row.id}','watch');dqCloseDetail()" style="flex:1;padding:9px;border-radius:8px;border:none;background:#7c3aed;color:white;font-size:12px;font-weight:700;cursor:pointer">👁 Watch</button>
        <button onclick="dqAction('${row.id}','rejected');dqCloseDetail()" style="flex:1;padding:9px;border-radius:8px;border:none;background:#dc2626;color:white;font-size:12px;font-weight:700;cursor:pointer">✗ Reject</button>
      </div>
    </div>` : `
    <button onclick="dqAction('${row.id}','pending');dqCloseDetail()" style="padding:10px;border-radius:8px;border:1px solid #d1d5db;background:white;color:#374151;font-size:13px;cursor:pointer;width:100%">↩ Return to Pending</button>`}
  `;

  overlay.style.display = 'block';
  panel.style.display   = 'block';
}

// Approve with optional relationship_type override from the detail panel dropdown
async function dqApproveWithOverride(id) {
  const sel = document.getElementById(`dq-rel-override-${id}`);
  const overrideType = sel ? sel.value : null;
  await dqAction(id, 'approved', overrideType ? { relationship_type: overrideType } : null);
  dqCloseDetail();
}

function dqCloseDetail(e) {
  if (e && e.target !== document.getElementById('dq-detail-overlay')) return;
  document.getElementById('dq-detail-overlay').style.display = 'none';
  document.getElementById('dq-detail-panel').style.display   = 'none';
}


