// ── IMPORTANT ARTICLES — News Intelligence Module ────────────────
// Extracted from app.js (Domain A2, §3 byte-identical). Plain script, load BEFORE app.js.
// loadNewsModule/renderNewsArticles/newsTabSwitch + _na* helpers stay global (home-panel/onclick). External: _sb, DOM.

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
