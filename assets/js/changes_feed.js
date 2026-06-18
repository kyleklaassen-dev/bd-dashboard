// ══════════════════════════════════════════════════════════════════════════════
// CHANGES FEED  — cfLoadFeed() + helpers
// ══════════════════════════════════════════════════════════════════════════════

// Register tab so navTo fires onEnter
registerTab('changes-feed', {
  onEnter: () => { if (!window._cfLoaded) cfLoadFeed(); }
});

// Chip click handler (bound via onclick attribute in HTML)
function cfChipClick(btn) {
  document.querySelectorAll('.cf-chip').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  cfLoadFeed();
}

// ── Format relative time ─────────────────────────────────────────────────────
function _cfFmtTime(ts) {
  if (!ts) return '—';
  const d   = new Date(ts);
  const now = new Date();
  const diffMs = now - d;
  const diffH  = Math.floor(diffMs / 3600000);
  const diffM  = Math.floor(diffMs / 60000);
  if (diffM < 2)  return 'Just now';
  if (diffM < 60) return `${diffM}m ago`;
  if (diffH < 24) return `${diffH}h ago`;
  const diffD = Math.floor(diffH / 24);
  if (diffD < 7)  return `${diffD}d ago`;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// ── Badge CSS class lookup ───────────────────────────────────────────────────
function _cfBadgeClass(type, docType) {
  if (type === 'abstract') {
    // Doc-type-specific colors
    const dt = (docType || '').toLowerCase();
    if (dt === '8-k' || dt === 'press_release') return 'cf-badge-deal';
    if (dt === 'poster' || dt === 'slide_deck')  return 'cf-badge-catalyst';
    if (dt === 'patent')                          return 'cf-badge-signal';
    return 'cf-badge-abstract'; // default for abstract, clinical_data, etc.
  }
  return { news:'cf-badge-news', drug:'cf-badge-drug', company:'cf-badge-company',
           deal:'cf-badge-deal', signal:'cf-badge-signal',
           catalyst:'cf-badge-catalyst' }[type] || 'cf-badge-change';
}
function _cfBadgeLabel(type, docType) {
  if (type === 'abstract') {
    const dt = (docType || '').replace(/_/g,' ').replace(/\b\w/g, c => c.toUpperCase());
    return dt || 'Document';
  }
  return { news:'News', drug:'Drug', company:'Company', deal:'Deal',
           signal:'Signal', catalyst:'Catalyst', change:'Change' }[type] || type;
}

// ── Relevance bar (0-100) ────────────────────────────────────────────────────
function _cfRelBar(score) {
  if (!score && score !== 0) return '';
  const pct = Math.min(100, Math.max(0, score));
  const col  = pct >= 70 ? '#22c55e' : pct >= 40 ? '#f59e0b' : '#94a3b8';
  return `<span class="cf-relevance" title="Relevance ${pct}"><span class="cf-relevance-fill" style="width:${pct}%;background:${col}"></span></span>`;
}

// ── Truncate safely ─────────────────────────────────────────────────────────
function _cfTrunc(str, n) { return str && str.length > n ? str.slice(0, n) + '…' : (str || ''); }

// ── Escape HTML ─────────────────────────────────────────────────────────────
function _cfEsc(s) {
  if (!s) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Render a single feed item to HTML ───────────────────────────────────────
function _cfRenderItem(item) {
  const badge = `<span class="cf-badge ${_cfBadgeClass(item.type, item.docType)}">${_cfBadgeLabel(item.type, item.docType)}</span>`;

  // Change before→after pill
  const changePill = item.isChange
    ? `<div class="cf-change-pill"><span class="cf-old">${_cfEsc(_cfTrunc(item.oldVal, 60))}</span><span class="cf-arrow">→</span><span class="cf-new">${_cfEsc(_cfTrunc(item.newVal, 80))}</span></div>`
    : '';

  // URLs must not be HTML-escaped — only replace " to prevent attribute breakout
  const _safeUrl = u => (u || '').replace(/"/g, '%22').replace(/'/g, '%27').replace(/\s/g, '%20');
  const srcLabel = item.type==='news' ? 'Read Article' :
                   item.type==='abstract' ? 'Open Document' :
                   item.type==='deal' ? 'Source' :
                   item.type==='catalyst' ? 'Source' : 'Source';
  const source = (item.url && item.url.startsWith('http'))
    ? `<a href="${_safeUrl(item.url)}" target="_blank" rel="noopener noreferrer" class="cf-source">${srcLabel} ↗</a>`
    : '';

  const entity = item.entity
    ? `<span style="font-size:10px;font-weight:600;color:#64748b;background:#f1f5f9;border-radius:4px;padding:1px 5px">${_cfEsc(_cfTrunc(item.entity, 40))}</span>`
    : '';

  const field = item.field
    ? `<span style="font-size:10px;color:#94a3b8;font-family:monospace">${_cfEsc(item.field)}</span>`
    : '';

  const severity = item.severity
    ? `<span style="font-size:9px;font-weight:700;color:${item.severity==='high'?'#dc2626':item.severity==='medium'?'#d97706':'#94a3b8'};text-transform:uppercase">${item.severity}</span>`
    : '';

  return `<div class="cf-item">
    ${badge}
    <div class="cf-content">
      <div class="cf-title">${_cfEsc(_cfTrunc(item.title, 130))}</div>
      ${item.detail ? `<div class="cf-detail">${_cfEsc(_cfTrunc(item.detail, 240))}</div>` : ''}
      ${changePill}
      <div class="cf-meta">
        <span class="cf-time">${_cfFmtTime(item.ts)}</span>
        ${entity}${field}${severity}${_cfRelBar(item.relevance)}${source}
      </div>
    </div>
  </div>`;
}

// ── Main feed loader ─────────────────────────────────────────────────────────
async function cfLoadFeed() {
  const body = document.getElementById('cf-body');
  const badge = document.getElementById('cf-count-badge');
  if (!body) return;
  if (typeof _sb === 'undefined') {
    body.innerHTML = '<div style="color:#94a3b8;padding:60px 0;text-align:center">Supabase not ready — try refreshing.</div>';
    return;
  }

  body.innerHTML = '<div style="color:#94a3b8;padding:60px 0;text-align:center;font-size:13px">Loading…</div>';
  if (badge) badge.textContent = '';

  const days  = parseInt(document.getElementById('cf-range')?.value || '7');
  const since = new Date(Date.now() - days * 86400 * 1000).toISOString();
  const activeType = document.querySelector('.cf-chip.active')?.dataset.type || 'all';

  const items = [];
  const want  = t => activeType === 'all' || activeType === t;

  try {

    // ── 1. News articles ──────────────────────────────────────────────────
    if (want('news')) {
      const { data: news, error: ne } = await _sb.from('news_articles')
        .select('id,headline,source_name,article_url,source_url,relevance_score,why_it_matters,raw_summary,meridian_summary,published_at,created_at,priority_level,matched_area_ids')
        .gte('created_at', since)
        .order('created_at', { ascending: false })
        .limit(60);
      if (ne) console.warn('[CF news]', ne);
      (news || []).forEach(n => {
        const detail = n.why_it_matters || n.meridian_summary || n.raw_summary || '';
        const areas  = (n.matched_area_ids || []).join(', ');
        items.push({
          type:      'news',
          ts:        n.created_at,
          title:     n.headline || 'News article',
          detail:    detail || (areas ? `Area: ${areas}` : ''),
          entity:    n.source_name || '',
          // Prefer full article URL; reject bare domain-only source_urls (< 30 chars or no path)
          url:       (n.article_url && n.article_url.length > 20) ? n.article_url
                     : (n.source_url && n.source_url.split('/').length > 3) ? n.source_url
                     : null,
          relevance: n.relevance_score,
          severity:  n.priority_level === 'high' ? 'high' : n.priority_level === 'medium' ? 'medium' : null
        });
      });
    }

    // ── 2. Field change audit ─────────────────────────────────────────────
    if (want('drug') || want('company')) {
      const tableFilter = activeType === 'drug'    ? ['drugs']
                        : activeType === 'company' ? ['companies']
                        : ['drugs', 'companies', 'company_partnerships'];
      let q = _sb.from('field_change_audit')
        .select('id,table_name,entity_id,entity_type,field_name,old_value,new_value,changed_at,change_source,is_governance_relevant,is_correction')
        .gte('changed_at', since)
        .order('changed_at', { ascending: false })
        .limit(120);
      if (activeType !== 'all') q = q.in('table_name', tableFilter);
      const { data: changes, error: ce } = await q;
      if (ce) console.warn('[CF changes]', ce);
      (changes || []).forEach(c => {
        const resolvedType = c.table_name === 'drugs' ? 'drug'
                           : c.table_name === 'companies' ? 'company'
                           : 'change';
        const isCorrxn = c.is_correction;
        items.push({
          type:     resolvedType,
          ts:       c.changed_at,
          title:    `${c.entity_id || c.entity_type || c.table_name} — ${c.field_name} updated${isCorrxn ? ' (correction)' : ''}`,
          detail:   c.is_governance_relevant ? 'Governance-relevant change' : `Source: ${c.change_source || 'system'}`,
          entity:   c.table_name,
          field:    c.field_name,
          isChange: true,
          oldVal:   c.old_value,
          newVal:   c.new_value,
          severity: c.is_governance_relevant ? 'medium' : null
        });
      });
    }

    // ── 3. Deals ──────────────────────────────────────────────────────────
    if (want('deal')) {
      const { data: deals, error: de } = await _sb.from('deals')
        .select('id,from_company,to_company,deal_type,upfront_usd_m,headline,detail,deal_date,created_at,source_url')
        .gte('created_at', since)
        .order('created_at', { ascending: false })
        .limit(40);
      if (de) console.warn('[CF deals]', de);
      (deals || []).forEach(d => {
        const upfront = d.upfront_usd_m ? ` · $${d.upfront_usd_m}M upfront` : '';
        items.push({
          type:   'deal',
          ts:     d.created_at || d.deal_date,
          title:  d.headline || `${d.from_company || '?'} → ${d.to_company || '?'}`,
          detail: d.detail || `${d.deal_type || 'deal'}${upfront}`,
          entity: [d.from_company, d.to_company].filter(Boolean).join(' × '),
          url:    d.source_url
        });
      });
    }

    // ── 4. Abstracts / company documents ─────────────────────────────────
    if (want('abstract')) {
      const { data: docs, error: dce } = await _sb.from('company_documents')
        .select('id,title,document_type,source_url,publication_date,conference,journal,phase,drug_names,key_findings,authors,created_at,company_id,pubmed_id')
        .gte('created_at', since)
        .order('created_at', { ascending: false })
        .limit(100);
      if (dce) console.warn('[CF docs]', dce);
      (docs || []).forEach(d => {
        const docType = (d.document_type || 'document').toLowerCase();
        // Build a rich detail line with all available context
        const parts = [];
        if (d.drug_names) parts.push(`Drug: ${d.drug_names}`);
        if (d.conference) parts.push(d.conference);
        if (d.journal) parts.push(d.journal);
        if (d.phase) parts.push(`Phase ${d.phase}`);
        if (d.authors) parts.push(`by ${String(d.authors).substring(0, 60)}`);
        if (d.key_findings) parts.push(String(d.key_findings).substring(0, 120));
        // Build direct access URL — prefer source_url, fallback to PubMed
        const accessUrl = d.source_url || (d.pubmed_id ? `https://pubmed.ncbi.nlm.nih.gov/${d.pubmed_id}/` : null);
        items.push({
          type:    'abstract',
          docType: docType,
          ts:      d.created_at,
          title:   d.title || 'Scientific document',
          detail:  parts.join(' · ') || `${docType} document`,
          entity:  d.company_id || '',
          url:     accessUrl,
          docBadge: docType  // raw type for badge color
        });
      });
    }

    // ── 5. Catalysts ──────────────────────────────────────────────────────
    if (want('catalyst')) {
      const { data: cats, error: cate } = await _sb.from('catalysts')
        .select('id,label,company_id,area_id,significance,catalyst_type,catalyst_date,created_at,source_url,confidence_level,catalyst_status')
        .gte('created_at', since)
        .order('created_at', { ascending: false })
        .limit(40);
      if (cate) console.warn('[CF catalysts]', cate);
      (cats || []).forEach(c => {
        items.push({
          type:     'catalyst',
          ts:       c.created_at,
          title:    c.label || `Catalyst · ${c.catalyst_type || 'event'}`,
          detail:   [c.catalyst_date, c.confidence_level, c.catalyst_status].filter(Boolean).join(' · '),
          entity:   c.company_id || c.area_id || '',
          url:      c.source_url,
          severity: c.significance === 'high' ? 'high' : c.significance === 'medium' ? 'medium' : null
        });
      });
    }

  } catch(err) {
    console.warn('[ChangesFeed] fetch error', err);
  }

  // Sort all items by timestamp descending
  items.sort((a, b) => {
    const ta = a.ts || '';
    const tb = b.ts || '';
    return tb.localeCompare(ta);
  });

  window._cfLoaded = true;

  if (badge) badge.textContent = `${items.length} item${items.length !== 1 ? 's' : ''}`;

  if (!items.length) {
    body.innerHTML = `<div style="color:#94a3b8;padding:60px 0;text-align:center;font-size:13px">No activity in the last ${days} day${days > 1 ? 's' : ''}.</div>`;
    return;
  }

  body.innerHTML = items.map(_cfRenderItem).join('');
}
