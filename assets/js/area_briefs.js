// AREA BRIEFS + MERIDIAN NARRATIVE — area-tab patient-brief loader and the prose
// 'read layer' (_loadMeridianNarrative), plus the AREA_BRIEF_INDICATIONS / IND_PATIENT_NAME
// maps. Extracted from app.js (Phase 4 split 2026-06-19). Classic script: globals called by
// switchTab at call time. Loaded before app.js (no registerTab at eval time).

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

