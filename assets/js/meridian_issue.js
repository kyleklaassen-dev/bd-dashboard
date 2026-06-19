// MERIDIAN ISSUE + ARCHIVE — daily-issue loader/renderer, entity-link bridge, archive popover.
// Extracted from app.js (Phase 4 split 2026-06-19). Classic script: globals (loadMeridianIssue,
// renderMeridianIssue, toggleMeridianArchive, selectMeridianIssue, _injectMeridianBridge, …).
// Loaded before app.js; uses _sb + the meridian_issues table at call time.

// ── Meridian entity link bridge ───────────────────────────────────────────────
// Injected on every iframe load (both srcdoc and static file fallback).
// Same-origin iframe — contentDocument is accessible.
function _injectMeridianBridge(frame) {
  try {
    const doc = frame.contentDocument || (frame.contentWindow && frame.contentWindow.document);
    if (!doc || !doc.head) return;
    // Remove any previous bridge to avoid duplicates on reload
    const prev = doc.getElementById('_meridian_bridge');
    if (prev) prev.remove();
    const s = doc.createElement('script');
    s.id = '_meridian_bridge';
    s.textContent = [
      'function openDrugModal(id){try{window.parent.openDrugEntityModal(id,id,null);}catch(e){}}',
      'function openCompanyModal(id){try{window.parent.openCompanyEntityModal(id,id,"meridian",id);}catch(e){}}',
      'document.addEventListener("click",function(e){',
      '  var a=e.target.closest("a");if(!a)return;',
      '  var oc=a.getAttribute("onclick")||"";',
      '  var hasModal=oc.indexOf("openDrugModal(")>=0||oc.indexOf("openCompanyModal(")>=0',
      '    ||oc.indexOf("openDrugEntityModal(")>=0||oc.indexOf("openCompanyEntityModal(")>=0;',
      '  if(hasModal){e.preventDefault();return;}',
      '  var rawHref=a.getAttribute("href")||"";',
      '  if(a.href&&rawHref!=="#"&&!rawHref.startsWith("javascript")){',
      '    e.preventDefault();',
      '    window.open(a.href,"_blank","noopener,noreferrer");',
      '  }',
      '},false);'
    ].join('\n');
    doc.head.appendChild(s);

    // Directly neutralize href on entity links so they ONLY fire the onclick modal.
    // Some links have both href="https://..." and onclick="openCompanyModal()" —
    // stripping the href ensures the modal opens, nothing navigates.
    setTimeout(function() {
      try {
        doc.querySelectorAll('a[onclick]').forEach(function(a) {
          var oc = a.getAttribute('onclick') || '';
          if (oc.indexOf('openDrugModal(') >= 0 || oc.indexOf('openCompanyModal(') >= 0 || oc.indexOf('openDrugEntityModal(') >= 0 || oc.indexOf('openCompanyEntityModal(') >= 0) {
            a.setAttribute('href', 'javascript:void(0)');
            a.removeAttribute('target');
          }
        });
      } catch(e2) {}
    }, 500);
  } catch(e) { console.warn('[meridian bridge]', e); }
}

// ── Meridian Archive ──────────────────────────────────────────────────────────
let _meridianLoaded = false;

async function loadMeridianIssue() {
  if (_meridianLoaded) return;
  _meridianLoaded = true;

  const list  = document.getElementById('meridian-archive-list');
  const frame = document.getElementById('meridian-issue-frame');
  if (!frame || !_sb) return;

  try {
    const { data: issues } = await _sb
      .from('meridian_issues')
      .select('id, issue_date, title')
      .order('issue_date', { ascending: false });

    const today         = new Date().toISOString().slice(0, 10);
    const todayInDb     = issues && issues.length > 0 && issues[0].issue_date === today;
    const archiveIssues = (issues || []).filter(i => i.issue_date !== today);

    // Build the popover list
    if (list) {
      const mkItem = (id, label, shortLabel, isToday) =>
        `<div class="mr-arch-item${isToday ? ' mr-arch-today' : ''}" onclick="selectMeridianIssue('${id}','${shortLabel.replace(/'/g,"&#39;")}')">` +
        `${isToday ? '📰 ' : ''}${label}</div>`;

      // If today's issue is in DB, show it first; otherwise show most recent issue as the pinned top item
      let topId, topLabel, topShort;
      if (todayInDb) {
        topId = issues[0].id; topLabel = "Today's Issue"; topShort = 'today';
      } else if (issues && issues.length > 0) {
        const latest = issues[0];
        const d = new Date(latest.issue_date + 'T12:00:00');
        topId    = latest.id;
        topLabel = '📌 Latest: ' + d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
        topShort = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
      } else {
        topId = '__live__'; topLabel = "Today's Issue"; topShort = 'today';
      }

      const archItems = archiveIssues.map(issue => {
        const d   = new Date(issue.issue_date + 'T12:00:00');
        const full = d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
        const sht  = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        return mkItem(issue.id, full, sht, false);
      }).join('');

      list.innerHTML =
        mkItem(topId, topLabel, topShort, true) +
        (archItems || '<div style="padding:10px 16px;font-size:12px;color:#94a3b8;font-style:italic">No archived issues yet</div>');
    }

    if (!issues || issues.length === 0) {
      // Absolute last resort: no issues anywhere — load the static live file
      frame.removeAttribute('srcdoc'); frame.srcdoc = '';
      frame.src = 'https://kyleklaassen-dev.github.io/bd-dashboard/meridian_today.html?v=' + Date.now();
      return;
    }

    if (todayInDb) {
      await renderMeridianIssue(issues[0].id, 'today');
    } else {
      // Today's issue not written yet — show the most recent issue instead of a blank page
      const latest = issues[0];
      const d = new Date(latest.issue_date + 'T12:00:00');
      const label = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
      await renderMeridianIssue(latest.id, label);
    }

  } catch(e) {
    console.warn('[MERIDIAN:load]', e);
    frame.removeAttribute('srcdoc'); frame.srcdoc = '';
    frame.src = 'https://kyleklaassen-dev.github.io/bd-dashboard/meridian_today.html?v=' + Date.now();
  }
}

async function renderMeridianIssue(issueId, label) {
  const frame = document.getElementById('meridian-issue-frame');
  if (!frame) return;

  // Sync tab badge to reflect selected issue
  try {
    const badge = document.querySelector('#tab-current-title .tab-current-badge');
    if (badge) {
      badge.textContent = (!label || label === 'today' || issueId === '__live__') ? "Today's Issue" : label;
    }
  } catch(_) {}

  // '__live__' means no issues in DB at all — try DB one more time, then fall back to static file
  if (issueId === '__live__') {
    try {
      const { data: fallbackIssues } = await _sb
        .from('meridian_issues')
        .select('id, issue_date')
        .order('issue_date', { ascending: false })
        .limit(1);
      if (fallbackIssues && fallbackIssues.length > 0) {
        const fi = fallbackIssues[0];
        const d  = new Date(fi.issue_date + 'T12:00:00');
        const lb = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        await renderMeridianIssue(fi.id, lb);
        return;
      }
    } catch(_) {}
    frame.removeAttribute('srcdoc'); frame.srcdoc = '';
    frame.src = 'https://kyleklaassen-dev.github.io/bd-dashboard/meridian_today.html?v=' + Date.now();
    return;
  }
  if (!_sb) return;
  frame.srcdoc = "<p style='font-family:Georgia,serif;padding:60px 80px;color:#94a3b8;font-size:16px'>Loading…</p>";
  try {
    const { data } = await _sb
      .from('meridian_issues')
      .select('body_html')
      .eq('id', issueId)
      .single();
    if (data?.body_html) {
      // Bridge: entity links open canonical cards in parent dashboard, never navigate out.
      // Intercepts ALL anchor clicks — if onclick has openDrugModal/openCompanyModal,
      // preventDefault stops any href navigation, then calls parent modal directly.
      const BRIDGE = `<script>
function openDrugModal(id){try{window.parent.openDrugEntityModal(id,id,null);}catch(e){console.warn('bridge:drug',e);}}
function openCompanyModal(id){try{window.parent.openCompanyEntityModal(id,id,'meridian',id);}catch(e){console.warn('bridge:co',e);}}
document.addEventListener('click',function(e){
  var a=e.target.closest('a');
  if(!a)return;
  var oc=a.getAttribute('onclick')||'';
  // Any link with an entity modal onclick — intercept and block navigation
  if(oc.includes('openDrugModal(')||oc.includes('openCompanyModal(')){
    e.preventDefault();
    e.stopPropagation();
    try{
      var m=oc.match(/open(?:Drug|Company)Modal\(\'([^\']+)\'\)/);
      if(m){
        if(oc.includes('openDrugModal'))openDrugModal(m[1]);
        else openCompanyModal(m[1]);
      }
    }catch(err){}
    return false;
  }
  // All other links: open in new tab (never navigate away from dashboard)
  if(a.href&&a.href!==window.location.href+'#'&&!a.href.endsWith('#')){
    e.preventDefault();
    window.open(a.href,'_blank','noopener,noreferrer');
  }
},true); // capture phase catches it before browser default
<\/script>`;
      frame.srcdoc = BRIDGE + data.body_html;
    }
  } catch(e) {
    console.warn('[MERIDIAN:render]', e);
  }
}
function toggleMeridianArchive(e) {
  e.stopPropagation();
  const dd = document.getElementById('meridian-archive-dd');
  const ch = document.getElementById('meridian-archive-chevron');
  const isOpen = dd && dd.style.display !== 'none';
  if (dd) dd.style.display = isOpen ? 'none' : 'block';
  if (ch) ch.style.transform = isOpen ? '' : 'rotate(180deg)';
  if (!isOpen) setTimeout(() => document.addEventListener('click', closeMeridianArchive, { once: true }), 0);
}
function closeMeridianArchive() {
  const dd = document.getElementById('meridian-archive-dd');
  const ch = document.getElementById('meridian-archive-chevron');
  if (dd) dd.style.display = 'none';
  if (ch) ch.style.transform = '';
}
function selectMeridianIssue(id, label) {
  closeMeridianArchive();
  renderMeridianIssue(id, label === 'today' ? 'today' : label);
}
