/* ─────────────────────────────────────────────────────────────────────────────
   MUI — Meridian UI component vocabulary  (2026-06-20)
   The shared, visual-first rendering primitives for the surface-led revamp.
   Consolidates helpers that were duplicated across modules (home_preview E/fN/nc/
   mlMd/trust, intel2 E/fNum/tier/row, asset_tab esc/renderDiffGrid). Classic
   script — defines the global `MUI`. Pairs with assets/css/tokens.css. No deps.
   Adopt incrementally: all NEW rendering uses MUI; legacy modules migrate when touched.
   ───────────────────────────────────────────────────────────────────────────── */
(function () {
  const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g,
    c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  const fmtNum = n => {
    if (n == null || n === '' || isNaN(n)) return '—';
    n = Number(n);
    return n >= 1e9 ? (n / 1e9).toFixed(1) + 'B'
         : n >= 1e6 ? (n / 1e6).toFixed(1) + 'M'
         : n >= 1e3 ? (n / 1e3).toFixed(0) + 'K'
         : '' + n;
  };

  const fmtDate = d => { if (d == null || d === '') return ''; try { return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); } catch (e) { return String(d); } };
  const daysUntil = d => { try { return Math.round((new Date(d) - new Date()) / 864e5); } catch (e) { return null; } };
  const relDays = d => { const n = daysUntil(d); return n == null ? '—' : n === 0 ? 'now' : n > 0 ? `${n}d` : `${-n}d ago`; };

  /* quality/believability: high = good = green */
  const tierClass = t => {
    t = String(t || '').toLowerCase();
    if (/high|strong|^a\b|tier.?a|robust/.test(t)) return 'high';
    if (/med|moderate|^b\b|tier.?b|partial/.test(t)) return 'med';
    if (/low|weak|^c\b|tier.?c|single|sparse/.test(t)) return 'low';
    return 'info';
  };
  /* significance/urgency: high score = attention = red→amber→green */
  const scoreClass = n => { n = Number(n); return n >= 9 ? 'low' : n >= 7 ? 'med' : n >= 5 ? 'med' : 'high'; };

  const pill = (text, mod) => `<span class="mui-pill mui-pill--${mod || 'neutral'}">${esc(text)}</span>`;
  const qualityPill = t => t ? `<span class="mui-pill mui-pill--${tierClass(t)}">${esc(t)}</span>` : '';
  const scorePill = (label, n) => `<span class="mui-pill mui-pill--${scoreClass(n)}">${esc(label)}</span>`;
  const link = (href, text) => href ? `<a class="mui-a" href="${esc(href)}" target="_blank" rel="noopener">${esc(text || 'source ↗')}</a>` : '';
  const bar = frac => `<span class="mui-bar"><i style="width:${Math.max(0, Math.min(100, Math.round((Number(frac) || 0) * 100)))}%"></i></span>`;

  /* items: [{label, value, sub}] — big value, small label */
  const metricGrid = items => `<div class="mui-metrics">${(items || []).map(m =>
    `<div class="mui-metric"><div class="mui-metric-l">${esc(m.label)}</div>` +
    `<div class="mui-metric-v">${m.valueHtml || esc(m.value)}</div>` +
    (m.sub ? `<div class="mui-metric-sub">${esc(m.sub)}</div>` : '') + `</div>`).join('')}</div>`;

  /* {name, sub, right} — name/sub left, right is raw HTML (pills/links) */
  const row = ({ name, sub, right } = {}) =>
    `<div class="mui-row"><div class="mui-row-main">` +
    `<div class="mui-row-nm">${name || ''}</div>` +
    (sub ? `<div class="mui-row-sub">${sub}</div>` : '') +
    `</div><div class="mui-row-spacer"></div>` +
    (right ? `<div class="mui-row-right">${right}</div>` : '') + `</div>`;

  const timelineItem = ({ when, what, meta } = {}) =>
    `<div class="mui-tl"><div class="mui-tl-when">${esc(when)}</div>` +
    `<div class="mui-tl-what">${what || ''}</div>` +
    (meta ? `<div class="mui-tl-meta">${meta}</div>` : '') + `</div>`;

  const labelValueSub = items => `<div class="mui-lvs">${(items || []).map(d =>
    `<div class="mui-lvs-cell"><div class="mui-lvs-l">${esc(d.label)}</div>` +
    `<div class="mui-lvs-v">${esc(d.value)}</div>` +
    (d.sub ? `<div class="mui-lvs-sub">${esc(d.sub)}</div>` : '') + `</div>`).join('')}</div>`;

  /* prov: [{claim_text, source_url}], tri: {claims, multi_source_claims} */
  const trustBlock = (prov, tri) => {
    prov = prov || [];
    const withUrl = prov.filter(p => p.source_url);
    const triLine = tri ? `${tri.claims} claims · ${tri.multi_source_claims || 0} corroborated by ≥2 independent sources` : `${prov.length} claims traced`;
    const rows = prov.slice(0, 12).map(p =>
      `<div class="mui-src">${esc((p.claim_text || '').slice(0, 130))} ` +
      (p.source_url ? link(p.source_url) : '<span class="mui-int">internal</span>') + `</div>`).join('');
    if (!prov.length) return '';
    return `<details class="mui-trust"><summary>▸ Sources &amp; provenance — ${withUrl.length}/${prov.length} externally sourced</summary><div class="mui-tri">${triLine}</div>${rows}</details>`;
  };

  /* lightweight markdown (port of home_preview mlMd) → .mui-md */
  const md = t => {
    if (!t) return '';
    let s = esc(t).replace(/^_(.+?)_$/gm, '<i>$1</i>').replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/\[(\d+)\]/g, '<span class="mui-cite">[$1]</span>');
    const out = []; let inList = false;
    for (const ln of s.split(/\n/)) {
      if (/^###\s+/.test(ln)) { if (inList) { out.push('</ul>'); inList = false; } out.push('<h5>' + ln.replace(/^###\s+/, '') + '</h5>'); }
      else if (/^#{1,2}\s+/.test(ln)) { if (inList) { out.push('</ul>'); inList = false; } out.push('<h4>' + ln.replace(/^#{1,2}\s+/, '') + '</h4>'); }
      else if (/^[-*]\s+/.test(ln)) { if (!inList) { out.push('<ul>'); inList = true; } out.push('<li>' + ln.replace(/^[-*]\s+/, '') + '</li>'); }
      else if (ln.trim() === '') { if (inList) { out.push('</ul>'); inList = false; } }
      else { if (inList) { out.push('</ul>'); inList = false; } out.push('<p>' + ln + '</p>'); }
    }
    if (inList) out.push('</ul>');
    return `<div class="mui-md">${out.join('')}</div>`;
  };

  window.MUI = {
    esc, fmtNum, fmtDate, daysUntil, relDays,
    tierClass, scoreClass, pill, qualityPill, scorePill, link, bar,
    metricGrid, row, timelineItem, labelValueSub, trustBlock, md,
  };
})();
