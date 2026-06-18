// ── Pharma Intel Tab — Live Intel Injection ─────────────────────────────────
// Fetches Supabase intel tagged with companies in the Pharma Intel drawers
// and prepends a "Live Intel" section into each expandable drawer.
(function(){
  // Map: Supabase company_id → piToggle slug
  const PI_COMPANY_MAP = {
    // US / Global Big Pharma
    'lilly':        'us-lilly',
    'jnj':          'us-jnj',
    'novartis':     'us-novartis',
    'abbvie':       'us-abbvie',
    'novonordisk':  'us-novonordisk',
    'astrazeneca':  'us-astrazeneca',
    'merck':        'us-merck',
    'roche':        'us-roche',
    'amgen':        'us-amgen',
    'pfizer':       'us-pfizer',
    'bms':          'us-bms',
    'sanofi':       'us-sanofi',
    'gilead':       'us-gilead',
    'vertex':       'us-vertex',
    'gsk':          'us-gsk',
    'regeneron':    'us-regeneron',
    'takeda':       'us-takeda',
    'bayer':        'us-bayer',
    'biogen':       'us-biogen',
    'moderna':      'us-moderna',
    // China Pharma
    'hengrui':      'cn-hengrui',
    'sinopharm':    'cn-sinopharm',
    'cspc':         'cn-cspc',
    'wuxi-bio':     'cn-wuxi-bio',
    'beone':        'cn-beigene',
    'beigene':      'cn-beigene',
    'sinobiopharm': 'cn-sino-biopharma',
    'hansoh':       'cn-hansoh',
    'innovent':     'cn-innovent',
    'fosun':        'cn-fosun',
    'hutchmed':     'cn-hutchmed',
    'zailab':       'cn-zailab',
    'remegen':      'cn-remegen',
    // AI Biotech
    'absci':        'ai-absci',
    'generatebio':  'ai-generate',
    'chai':         'ai-chai',
    'boltz':        'ai-boltz',
    'nabla':        'ai-nabla',
    'cradle':       'ai-cradle',
  };

  const companyIds = Object.keys(PI_COMPANY_MAP);
  const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
  const typeIcon = { news:'📰', data:'🔬', deal:'🤝', regulatory:'⚖️', conference:'🎤', other:'📌' };

  async function injectPharmaIntel() {
    if (!_sb) return;
    const { data, error } = await _sb
      .from('intel_companies')
      .select('company_id, intel!inner(id, intel_date, headline, source_url, importance, intel_type)')
      .in('company_id', companyIds)
      .gte('intel.intel_date', thirtyDaysAgo)
      .order('intel_date', { referencedTable: 'intel', ascending: false });

    if (error || !data || !data.length) return;

    // Group by company
    const byCompany = {};
    data.forEach(function(row) {
      const cid = row.company_id;
      if (!byCompany[cid]) byCompany[cid] = [];
      if (row.intel && row.intel.headline) {
        byCompany[cid].push(row.intel);
      }
    });

    // Inject into each drawer
    Object.entries(byCompany).forEach(function([cid, items]) {
      const slug = PI_COMPANY_MAP[cid];
      if (!slug) return;
      const drawer = document.getElementById('pi-dr-' + slug);
      if (!drawer) return;
      const body = drawer.querySelector('.pi-dr-body');
      if (!body) return;

      // Build live intel HTML
      const listItems = items.slice(0, 5).map(function(it) {
        const icon = typeIcon[it.intel_type] || '📌';
        const imp = it.importance === 'high' ? ' style="font-weight:600"' : '';
        const url = it.source_url ? `<a href="${it.source_url}" target="_blank" rel="noopener" class="pi-dr-pr-link"${imp}>${it.headline}</a>` : `<span${imp}>${it.headline}</span>`;
        return `<li class="pi-dr-pr"><span class="pi-dr-pr-date" style="color:#1a3f8f">${it.intel_date}</span> ${icon} ${url}</li>`;
      }).join('');

      const section = document.createElement('div');
      section.className = 'pi-live-intel';
      section.innerHTML = `<div class="pi-dr-hd" style="background:#dbeafe;color:#1e3a5f;margin-top:0">🔴 Live Intel <span style="font-weight:400;font-size:10px">(Supabase · last 30 days)</span></div><ul class="pi-dr-prs" style="margin-bottom:8px">${listItems}</ul>`;
      body.insertBefore(section, body.firstChild);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectPharmaIntel);
  } else {
    // If already loaded (tab switch), run after a tick
    setTimeout(injectPharmaIntel, 0);
  }
})();
