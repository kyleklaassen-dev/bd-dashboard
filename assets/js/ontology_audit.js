// ── ONTOLOGY AUDIT TAB ────────────────────────────────────────────────────────
let _ontAuditLoaded = false;

function ontToggle(id) {
  const body = document.getElementById('ont-' + id + '-body');
  const tog  = document.getElementById('ont-' + id + '-tog');
  if (!body) return;
  const collapsed = body.classList.toggle('collapsed');
  if (tog) tog.style.transform = collapsed ? 'rotate(-90deg)' : '';
}

async function ontologyLoad(force = false) {
  if (_ontAuditLoaded && !force) return;
  _ontAuditLoaded = true;
  const ts = document.getElementById('ont-timestamp');
  if (ts) ts.textContent = 'Loading…';

  const [
    { data: daRows },  /* Session 80: disease_areas stub — returns [] DB teardown complete Session 84 */
    { data: indRows },
    { data: tgtRows },
    { data: tpRows },
    { data: modRows },
    { count: drugCt },
    { count: coCt },
    { count: trialCt },
    { count: dealCt },
    { count: catCt },
    { count: intelCt },
    { count: edgeCt }
  ] = await Promise.all([
    Promise.resolve({ data: [] }),  /* disease_areas — retired from code reads (Session 80) */
    _sb.from('indications').select('*').order('name'),
    _sb.from('targets').select('id,name:label,family,pathway,cross_area_relevance').order('label'),
    _sb.from('target_pairs').select('id,name:pair_symbol').order('name'),
    _sb.from('modalities').select('*').order('name'),
    _sb.from('drugs').select('*',{count:'exact',head:true}),
    _sb.from('companies').select('*',{count:'exact',head:true}),
    _sb.from('trials').select('*',{count:'exact',head:true}),
    _sb.from('deals').select('*',{count:'exact',head:true}),
    _sb.from('catalysts').select('*',{count:'exact',head:true}),
    _sb.from('intel').select('*',{count:'exact',head:true}),
    _sb.from('entity_edges').select('*',{count:'exact',head:true})
  ]);

  const counts = {
    disease_areas: (daRows||[]).length,
    indications:   (indRows||[]).length,
    targets:       (tgtRows||[]).length,
    target_pairs:  (tpRows||[]).length,
    modalities:    (modRows||[]).length,
    drugs: drugCt||0, companies: coCt||0, trials: trialCt||0,
    deals: dealCt||0, catalysts: catCt||0, intel: intelCt||0, entity_edges: edgeCt||0
  };

  _renderOntMap(counts);
  _renderOntCards({ daRows: daRows||[], indRows: indRows||[], tgtRows: tgtRows||[], tpRows: tpRows||[], modRows: modRows||[], counts });
  _renderOntMatrix();
  _renderOntFlags(daRows||[]);
  _renderOntGaps({ indRows: indRows||[], daRows: daRows||[], counts });
  _renderOntMigration(daRows||[]);

  // Sync: roadmap is static — render immediately
  _renderOntRoadmap();

  // Async sections — load in background, don't block the sync render
  _renderOntImpact(daRows||[]);
  _renderOntCoverage();

  if (ts) ts.textContent = 'Loaded ' + new Date().toLocaleTimeString();
}

// ── A: Ontology Map ───────────────────────────────────────────────────────────
function _renderOntMap(counts) {
  const m = document.getElementById('ont-map-mount');
  if (!m) return;

  const sc = {
    exists:   { b:'#10b981', bg:'white',   bk:'#d1fae5', bt:'#065f46', bl:'EXISTS' },
    partial:  { b:'#8b5cf6', bg:'#faf5ff', bk:'#ede9fe', bt:'#5b21b6', bl:'PARTIAL' },
    missing:  { b:'#ef4444', bg:'#fff8f8', bk:'#fee2e2', bt:'#991b1b', bl:'MISSING' },
  };

  const layers = [
    { lbl:'Layer 1 · Taxonomy',  name:'Therapeutic Area',        q:'What specialty?',    tbl:'disease_areas',       status:'partial',  cnt:counts.disease_areas },
    { lbl:'Layer 2 · Disease',   name:'Indication',              q:'What disease?',      tbl:'indications',         status:'exists',   cnt:counts.indications },
    { lbl:'Layer 3 · Biology',   name:'Biology Tags',            q:'What mechanism?',    tbl:'indications.biology_tags', status:'partial', cnt:null },
    { lbl:'Layer 4 · Molecular', name:'Target',                  q:'What molecule?',     tbl:'targets',             status:'exists',   cnt:counts.targets },
    { lbl:'Layer 5 · Strategy',  name:'Target Pair',             q:'What combination?',  tbl:'target_pairs',        status:'exists',   cnt:counts.target_pairs },
    { lbl:'Layer 6 · Format',    name:'Modality',                q:'What format?',       tbl:'modalities',          status:'exists',   cnt:counts.modalities },
    { lbl:'Layer 7 · Delivery',  name:'Route of Admin',          q:'How delivered?',     tbl:'routes_of_admin',     status:'missing',  cnt:null },
  ];

  const entities = [
    { lbl:'Asset',        name:'Drug',      tbl:'drugs',         cnt:counts.drugs },
    { lbl:'Org',          name:'Company',   tbl:'companies',     cnt:counts.companies },
    { lbl:'Study',        name:'Trial',     tbl:'trials',        cnt:counts.trials },
    { lbl:'Transaction',  name:'Deal',      tbl:'deals',         cnt:counts.deals },
    { lbl:'Future Event', name:'Catalyst',  tbl:'catalysts',     cnt:counts.catalysts },
    { lbl:'Intelligence', name:'Signal',    tbl:'intel',         cnt:counts.intel },
    { lbl:'Relationship', name:'Edge',      tbl:'entity_edges',  cnt:counts.entity_edges },
  ];

  const layBox = l => {
    const s = sc[l.status];
    return `<div style="background:${s.bg};border:2px solid ${s.b};border-radius:10px;padding:12px 8px;text-align:center">
      <div style="font-size:8.5px;font-weight:800;text-transform:uppercase;letter-spacing:.05em;color:#94a3b8;margin-bottom:3px">${l.lbl}</div>
      <div style="font-size:13px;font-weight:800;color:#0f172a;margin-bottom:2px">${l.name}</div>
      <div style="font-size:10px;color:#64748b;font-style:italic;margin-bottom:5px">${l.q}</div>
      <div style="font-size:9px;font-family:monospace;color:#94a3b8;margin-bottom:5px">${l.tbl}</div>
      <span style="font-size:9px;font-weight:800;border-radius:4px;padding:1px 7px;background:${s.bk};color:${s.bt}">${s.bl}</span>
      ${l.cnt !== null ? `<div style="font-size:11px;font-weight:700;color:${l.status==='missing'?'#ef4444':'#10b981'};margin-top:5px">${l.cnt} rows</div>` : `<div style="font-size:10px;color:#94a3b8;margin-top:5px">array field</div>`}
    </div>`;
  };

  const entBox = e => `<div style="background:white;border:2px solid #10b981;border-radius:10px;padding:10px 6px;text-align:center">
    <div style="font-size:8.5px;font-weight:800;text-transform:uppercase;letter-spacing:.05em;color:#94a3b8;margin-bottom:2px">${e.lbl}</div>
    <div style="font-size:13px;font-weight:800;color:#0f172a;margin-bottom:3px">${e.name}</div>
    <div style="font-size:9px;font-family:monospace;color:#94a3b8;margin-bottom:4px">${e.tbl}</div>
    <div style="font-size:11px;font-weight:700;color:#10b981">${e.cnt} rows</div>
  </div>`;

  m.innerHTML = `
    <div style="font-size:11px;color:#94a3b8;font-weight:600;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px">Core Ontology Layers (classify everything)</div>
    <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:10px;margin-bottom:6px">
      ${layers.map(layBox).join('')}
    </div>
    <div style="text-align:center;font-size:22px;color:#94a3b8;margin:4px 0">↓</div>
    <div style="font-size:11px;color:#94a3b8;font-weight:600;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px">Entity Tables (the things being classified)</div>
    <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:10px">
      ${entities.map(entBox).join('')}
    </div>
    <div style="margin-top:16px;padding:12px 16px;background:#f8fafc;border-radius:8px;font-size:11px;color:#64748b;line-height:1.7">
      <strong style="color:#0f172a">How to read this:</strong>
      The top row organizes knowledge — every drug, trial, deal, and signal inherits meaning from these 7 layers.
      <span style="display:inline-block;width:12px;height:12px;background:#d1fae5;border:1.5px solid #10b981;border-radius:3px;vertical-align:middle;margin:0 4px"></span>EXISTS &nbsp;
      <span style="display:inline-block;width:12px;height:12px;background:#ede9fe;border:1.5px solid #8b5cf6;border-radius:3px;vertical-align:middle;margin:0 4px"></span>PARTIAL (needs cleanup or normalization) &nbsp;
      <span style="display:inline-block;width:12px;height:12px;background:#fee2e2;border:1.5px solid #ef4444;border-radius:3px;vertical-align:middle;margin:0 4px"></span>MISSING (should be created)
    </div>`;
}

// ── B: Table Cards ────────────────────────────────────────────────────────────
function _renderOntCards({ daRows, indRows, tgtRows, tpRows, modRows, counts }) {
  const m = document.getElementById('ont-cards-mount');
  if (!m) return;

  const esc = s => String(s).replace(/</g,'&lt;').replace(/>/g,'&gt;');

  const card = ({ id, tname, status, def, fields, items, issues, connections }) => {
    const cls = status === 'partial' ? 'c-partial' : status === 'missing' ? 'c-missing' : status === 'proposed' ? 'c-proposed' : '';
    const bdgCls = `ont-badge-${status === 'exists' ? 'exists' : status === 'partial' ? 'partial' : status === 'missing' ? 'missing' : 'proposed'}`;
    const cnt = counts[id] ?? '—';
    return `<div class="ont-card ${cls}">
      <div class="ont-card-hd">
        <span class="ont-card-tname">${tname}</span>
        <span class="ont-badge ${bdgCls}">${status.toUpperCase()}</span>
        <span style="font-size:10px;font-weight:700;color:#64748b;margin-left:4px">${cnt !== '—' ? cnt+' rows' : ''}</span>
      </div>
      <div class="ont-card-def">${def}</div>
      ${fields ? `<div class="ont-card-section"><div class="ont-card-sh">Key Fields</div><div class="ont-pills">${fields.map(f=>`<span class="ont-pill">${esc(f)}</span>`).join('')}</div></div>` : ''}
      ${items && items.length ? `<div class="ont-card-section"><div class="ont-card-sh">Current Items</div><div class="ont-pills">${items.map(i=>`<span class="ont-pill ${i.flag||''}">${esc(i.name)}</span>`).join('')}</div></div>` : ''}
      ${connections ? `<div class="ont-card-section"><div class="ont-card-sh">Connected Tables</div><div class="ont-pills">${connections.map(c=>`<span class="ont-pill ok">${esc(c)}</span>`).join('')}</div></div>` : ''}
      ${issues && issues.length ? `<div class="ont-card-section"><div class="ont-card-sh">Issues Detected</div>${issues.map(i=>`<div class="ont-issue-row"><span>${i.sev==='h'?'🔴':i.sev==='m'?'🟡':'🔵'}</span><span>${esc(i.text)}</span></div>`).join('')}</div>` : ''}
    </div>`;
  };

  // Classify disease_areas rows by known misclassification
  const TARGETS_IN_DA   = ['tl1a','tslp','il4ra','il-4ra','il4rα','fcrn','igf1r','igf-1r'];
  const INDICS_IN_DA    = ['ted','thyroid eye disease','eoe'];
  const BIOTAGS_IN_DA   = ['atopy','autoimmune','t-cell'];
  const daItems = daRows.map(r => {
    const id = (r.id||'').toLowerCase();
    const nm = (r.name||'').toLowerCase();
    const flag = TARGETS_IN_DA.some(t=>id.includes(t)||nm.includes(t)) ? 'issue' :
                 INDICS_IN_DA.some(t=>id.includes(t)||nm.includes(t)) ? 'warn' :
                 BIOTAGS_IN_DA.some(t=>id.includes(t)||nm.includes(t)) ? 'warn' : '';
    return { name: r.name||r.id, flag };
  });

  const indByArea = {};
  indRows.forEach(r => {
    const a = r.disease_area||'unknown';
    if (!indByArea[a]) indByArea[a] = [];
    indByArea[a].push(r.abbreviation || r.name);
  });

  // Collect all unique biology tags
  const bioTagSet = new Set();
  indRows.forEach(r => (r.biology_tags||[]).forEach(t => bioTagSet.add(t)));
  const bioTags = [...bioTagSet].sort();

  m.innerHTML = `
    <div style="font-size:11px;color:#94a3b8;margin-bottom:12px;line-height:1.7">
      <strong style="color:#475569">7 core ontology tables</strong> classify every entity in Meridian.
      Of these, 5 exist in Supabase today. 2 are missing.
      The existing <code>disease_areas</code> table needs cleanup — it mixes targets, indications, and biology tags.
    </div>
    <div class="ont-cards">
      ${card({
        id:'disease_areas', tname:'disease_areas', status:'partial',
        def:'Intended to be top-level clinical specialty (Gastroenterology, Respiratory…). Currently misused — contains targets (TL1A, TSLP), an indication (TED), and biology concepts (Atopy, Autoimmune). Needs to be cleaned into a proper therapeutic_areas table.',
        fields:['id','name','description','created_at'],
        items: daItems.length ? daItems : [{name:'(empty)',flag:''}],
        connections:['indications (FK: disease_area)','company_areas (FK: area_id)','drug_area_scores (FK: disease_area)'],
        issues:[
          {sev:'h', text:'Contains targets (TL1A, TSLP, IL-4Rα, FcRn, IGF-1R) — these are molecules, not specialty areas'},
          {sev:'h', text:'Contains TED — this is an indication (Thyroid Eye Disease) under Ophthalmology, not a specialty area'},
          {sev:'m', text:'Contains Atopy and Autoimmune — these are biology tags / phenotypes, not therapeutic areas'},
          {sev:'m', text:'Contains T-cell Engineering — this is a technology platform concept, not a disease area'},
          {sev:'l', text:'IBD is a supercategory (should be split into UC and CD as separate indications)'},
        ]
      })}
      ${card({
        id:'indications', tname:'indications', status:'exists',
        def:'Specific disease or condition being treated by a drug. The right level of granularity for pipeline analysis — not too broad (Autoimmune), not too specific (IBD flare subtype). Each indication belongs to one therapeutic area.',
        fields:['id','name','abbreviation','disease_area (FK)','description','biology_tags[]','patient_note','regulatory_note'],
        items: indRows.map(r => ({ name:`${r.abbreviation} — ${r.name}` })),
        connections:['disease_areas (FK: disease_area)','drugs (field: disease_area)','trials (field: indication)'],
        issues:[
          {sev:'m', text:'disease_area FK still points to disease_areas (messy) — should point to therapeutic_areas once migrated'},
          {sev:'l', text:'biology_tags stored as TEXT[] array inside indications — could become a separate normalized table if tags are reused across indications'},
          {sev:'l', text:'RA, SLE, Sjögren\'s, EoE appear in trial text but may not all have indication records yet'},
        ]
      })}
      ${card({
        id:'biology_tags', tname:'biology_tags (partial)', status:'partial',
        def:'Mechanism, immune phenotype, or disease biology that cuts across multiple indications and targets. Currently stored as a TEXT[] array inside indications.biology_tags — not a standalone table. Should become its own table to support cross-indication tagging.',
        fields:['(currently) indications.biology_tags TEXT[]'],
        items: bioTags.map(t => ({ name: t })),
        connections:['indications (embedded array)'],
        issues:[
          {sev:'m', text:'Not a standalone table — tags cannot have their own definitions, descriptions, or linked records'},
          {sev:'m', text:'Cannot create a dedicated indication_biology_tags join table without normalizing first'},
          {sev:'l', text:'Some tags (atopy, autoimmune) exist in disease_areas but should only live here'},
        ]
      })}
      ${card({
        id:'targets', tname:'targets', status:'exists',
        def:'Biological molecule being drugged or modulated. The most precise layer of the ontology — a target defines what a drug does at the molecular level. Each target belongs to a disease area and has a family (cytokine, receptor, etc.) and pathway.',
        fields:['id','name','full_name','disease_area','family','pathway','cross_area_relevance[]','description'],
        items: tgtRows.map(r => ({ name: r.name })),
        connections:['disease_areas (FK: disease_area)','target_pairs (FKs: target_1, target_2)','drugs (field: mechanism)'],
        issues:[
          {sev:'l', text:'drug→target relationship is stored as free text in drugs.mechanism — no normalized drug_targets join table exists'},
          {sev:'l', text:'target→indication link is inferred via disease_area, not through a direct target_indications join table'},
        ]
      })}
      ${card({
        id:'target_pairs', tname:'target_pairs', status:'exists',
        def:'Intentional paired or combination target strategy. Captures the co-targeting rationale (e.g. TL1A × IL-23p19 for mucosal immunity + systemic inflammation). Not every drug that happens to hit two targets is a target pair — the pairing must be an intentional design decision.',
        fields:['id','name','area','target_1','target_2','rationale','notes'],
        items: tpRows.map(r => ({ name: r.name })),
        connections:['targets (FKs: target_1, target_2)','disease_areas (FK: area)','drugs (field: target_pair)'],
        issues:[
          {sev:'l', text:'drug→target_pair link is stored as a field in drugs — not enforced as a FK'},
        ]
      })}
      ${card({
        id:'modalities', tname:'modalities', status:'exists',
        def:'Therapeutic format or technology class. Describes how the drug is built (antibody, small molecule, cell therapy). Route of administration is separate from modality — a mAb can be IV or SC.',
        fields:['id','name','abbreviation','examples','description'],
        items: modRows.map(r => ({ name: r.name })),
        connections:['drugs (field: modality)'],
        issues:[
          {sev:'m', text:'Route of administration is not captured separately — some modalities imply a route but this is not normalized'},
          {sev:'l', text:'drug→modality link is free text in drugs.modality — no drug_modalities join table'},
        ]
      })}
      ${card({
        id:'routes_of_admin', tname:'routes_of_administration', status:'missing',
        def:'How a drug is physically delivered into the body. Route is independent of modality — a monoclonal antibody can be IV or SC; a small molecule is usually oral. Route data currently lives only in trial arms or is inferred from modality.',
        fields:['(proposed) id, name, abbreviation, description, typical_modalities[]'],
        items:[{name:'IV (Intravenous)'},{name:'SC (Subcutaneous)'},{name:'Oral'},{name:'Inhaled'},{name:'Intravitreal'},{name:'Topical'}],
        connections:['(proposed) drugs (join: drug_routes)','trials (field: arm description)'],
        issues:[
          {sev:'h', text:'Table does not exist — route is embedded in trial text or inferred from modality'},
          {sev:'m', text:'Without this table, Meridian cannot answer: "Which SC injectables are moving to oral?" or "Which drugs compete on route?"'},
        ]
      })}
    </div>`;
}

// ── C: Relationship Matrix ────────────────────────────────────────────────────
function _renderOntMatrix() {
  const m = document.getElementById('ont-matrix-mount');
  if (!m) return;

  // Rows = FROM tables, Cols = TO tables
  const tables = ['disease_areas','indications','targets','target_pairs','modalities','drugs','companies','trials','deals','entity_edges'];
  const labels = ['disease_areas','indications','targets','target_pairs','modalities','drugs','companies','trials','deals','entity_edges'];

  // [from][to] = { type, mechanism, note }
  const rels = {
    'disease_areas→indications': { t:'1:many', m:'FK: disease_area', cls:'cy', note:'Each indication belongs to one therapeutic area' },
    'disease_areas→targets':     { t:'1:many', m:'FK: disease_area', cls:'cy', note:'Each target linked to one therapeutic area (crude — targets should link to indications, not areas directly)' },
    'disease_areas→target_pairs':{ t:'1:many', m:'FK: area', cls:'cy', note:'Each pair linked to one therapeutic area' },
    'indications→drugs':         { t:'many:many', m:'field text match', cls:'cw', note:'Loose text match — no join table' },
    'indications→trials':        { t:'many:many', m:'field text match', cls:'cw', note:'Loose text match — no join table' },
    'targets→target_pairs':      { t:'many:many', m:'FK: target_1, target_2', cls:'cy', note:'Each pair has two target FKs' },
    'targets→drugs':             { t:'many:many', m:'drugs.mechanism text', cls:'cw', note:'No drug_targets join table — loose text' },
    'modalities→drugs':          { t:'1:many', m:'drugs.modality text', cls:'cw', note:'No FK — free text modality field' },
    'companies→drugs':           { t:'many:many', m:'company_areas table', cls:'cp', note:'Via company_areas join table' },
    'drugs→trials':              { t:'1:many', m:'trials.drug_id FK', cls:'cy', note:'FK exists' },
    'drugs→deals':               { t:'many:many', m:'deals.company_id / partner', cls:'cw', note:'Loose company-level link, not drug-level' },
    'drugs→entity_edges':        { t:'many:many', m:'entity_edges.entity_id', cls:'cy', note:'Edge table links any entity type' },
    'companies→entity_edges':    { t:'many:many', m:'entity_edges.entity_id', cls:'cy', note:'Edge table links any entity type' },
    'trials→entity_edges':       { t:'many:many', m:'entity_edges.entity_id', cls:'cy', note:'Edge table links any entity type' },
  };

  let html = `<div style="font-size:11px;color:#64748b;margin-bottom:12px;line-height:1.7">
    <span style="display:inline-block;width:10px;height:10px;background:#d1fae5;border-radius:2px;margin-right:4px;vertical-align:middle"></span><strong>Direct FK</strong> &nbsp;
    <span style="display:inline-block;width:10px;height:10px;background:#dbeafe;border-radius:2px;margin-right:4px;vertical-align:middle"></span><strong>Join table</strong> &nbsp;
    <span style="display:inline-block;width:10px;height:10px;background:#fef3c7;border-radius:2px;margin-right:4px;vertical-align:middle"></span><strong>Loose text match (should be normalized)</strong>
  </div>
  <div class="ont-matrix-wrap"><table class="ont-matrix">
    <thead><tr><th>FROM ↓ TO →</th>${tables.map((t,i)=>`<th style="min-width:90px">${labels[i]}</th>`).join('')}</tr></thead>
    <tbody>`;

  tables.forEach((fromT, fi) => {
    html += `<tr><th>${fromT}</th>`;
    tables.forEach((toT, ti) => {
      if (fi === ti) { html += `<td class="cn">—</td>`; return; }
      const key = `${fromT}→${toT}`;
      const rel = rels[key];
      if (rel) {
        html += `<td class="${rel.cls}" title="${rel.note}"><div style="font-size:9px;font-weight:700">${rel.t}</div><div style="font-size:9px;opacity:.8">${rel.m}</div></td>`;
      } else {
        html += `<td class="cn">·</td>`;
      }
    });
    html += `</tr>`;
  });

  html += `</tbody></table></div>
    <div style="margin-top:14px;padding:12px 16px;background:#fffbeb;border:1px solid #fde68a;border-radius:8px;font-size:11px;color:#92400e;line-height:1.7">
      <strong>⚠️ Priority normalization work:</strong>
      The relationships marked yellow are loose text matches — Meridian cannot reliably join these tables.
      Recommended join tables to create:
      <code>drug_targets</code>, <code>drug_indications</code>, <code>drug_modalities</code>, <code>drug_routes</code>, <code>indication_biology_tags</code>, <code>trial_indications</code>, <code>deal_drugs</code>.
    </div>`;

  m.innerHTML = html;
}

// ── D: Quality Flags ──────────────────────────────────────────────────────────
function _renderOntFlags(daRows) {
  const m = document.getElementById('ont-flags-mount');
  if (!m) return;

  const flags = [
    { id:'f-tgt-as-area', sev:'h', cat:'Misclassification · Structural',
      title:'Targets listed as disease areas (4 records)',
      body:'TL1A, TSLP, IL-4Rα, FcRn, and IGF-1R appear in disease_areas but are biological targets (molecules), not clinical specialty areas. This is the most critical structural issue — it means the ontology can\'t tell the difference between "what is being treated" and "what is being drugged."',
    },
    { id:'f-ind-as-area', sev:'h', cat:'Misclassification · Structural',
      title:'TED listed as a disease area (should be indication)',
      body:'Thyroid Eye Disease (TED) is a specific disease — an indication — not a clinical specialty. It belongs under Ophthalmology as a therapeutic area. Currently, TED exists in both disease_areas and indications, creating a duplicate.',
    },
    { id:'f-biotag-as-area', sev:'m', cat:'Misclassification · Conceptual',
      title:'Biology concepts listed as disease areas',
      body:'"Atopy" and "Autoimmune" are biology tags or phenotypes — they describe mechanism and immune biology, not clinical specialty areas. A patient can have an atopic condition (AD, CSU, Asthma) — Atopy is not a therapeutic area. "T-cell Engineering" is a technology platform concept.',
    },
    { id:'f-roa-missing', sev:'h', cat:'Missing Table · Structural Gap',
      title:'No routes_of_administration table',
      body:'Route of administration (IV, SC, Oral, Inhaled, Intravitreal, Topical) is currently not captured in its own table. Route is sometimes implied by modality but should be independent — a monoclonal antibody can be IV or SC, a nanobody can be inhaled. Without this table, Meridian cannot answer competitive questions about delivery.',
    },
    { id:'f-no-join-drug-target', sev:'h', cat:'Missing Join Table · Relationship Gap',
      title:'No drug_targets join table — drug-to-target relationship is free text',
      body:'drugs.mechanism is a text field that describes what a drug targets. This means Meridian cannot reliably join drugs to targets, cannot count drugs per target, and cannot detect when a new drug is entering a target space. A drug_targets table with relationship_type (primary/secondary/inferred) would fix this.',
    },
    { id:'f-no-join-drug-ind', sev:'h', cat:'Missing Join Table · Relationship Gap',
      title:'No drug_indications join table — drug-to-indication relationship is loose',
      body:'Drug-to-indication links are inferred via disease_area text matching. This means Meridian cannot reliably answer "which drugs are in UC?" unless the text matches exactly. A drug_indications table would make this a reliable structural link with confidence levels and sources.',
    },
    { id:'f-ibd-supercategory', sev:'m', cat:'Category Granularity',
      title:'IBD is a supercategory — should resolve to UC and CD',
      body:'"IBD" appears in disease_areas but is not a specific enough indication. Pipeline drugs target UC or CD specifically. Having IBD as a top-level area mixes drugs that treat UC-only, CD-only, or both. The correct structure: IBD is a biology tag or parent concept, UC and CD are the indications.',
    },
    { id:'f-da-dep-display', sev:'m', cat:'Migration Safety · ID vs Label',
      title:'Dashboard references disease_areas IDs directly',
      body:'Several dashboard widgets and filter logic depend on disease_areas.id values like "ibd", "ted", "atopy". If these are deleted or renamed without a migration mapping table, the dashboard will silently break. Rule: always migrate by adding new tables first, keeping old ones, then switching logic.',
    },
    { id:'f-biotag-array', sev:'l', cat:'Schema Design · Normalization',
      title:'Biology tags stored as TEXT[] array, not normalized',
      body:'"biology_tags" is an array inside the indications table. This works but limits what you can do — you can\'t add definitions, usage counts, or linked records to individual tags. A standalone biology_tags table with an indication_biology_tags join would make tags first-class entities.',
    },
    { id:'f-modality-route', sev:'m', cat:'Conceptual Mixing · Modality vs Route',
      title:'TCE means T-cell Engager, not T-cell Engineering',
      body:'T-cell Engager (TCE) is a format — a bispecific antibody designed to redirect T-cells against tumor antigens (like BCMA × CD3). This is correct. If any records describe it as "T-cell Engineering," that is an incorrect description of the modality.',
    },
    { id:'f-source-coverage', sev:'m', cat:'Relationship Quality',
      title:'Most relationships have no source or confidence field',
      body:'Drug-to-company, drug-to-target, and drug-to-indication links are stored without a source_id, confidence_level, or created_by field. This means Meridian cannot explain WHY a relationship exists. Recommended: add relationship_type, source_id, confidence_level, and review_status to all major join tables.',
    },
    { id:'f-no-join-drug-modality', sev:'m', cat:'Missing Join Table · Relationship Gap',
      title:'No drug_modalities join table — modality is stored as free text',
      body:'drugs.modality is a text field. While a modalities lookup table exists, there is no drug_modalities join table that formally links a drug to its modality with a FK, confidence level, or source. This means Meridian cannot reliably count "how many bispecifics are in UC?" as a structural query.',
    },
    { id:'f-trial-ind-text', sev:'h', cat:'Missing Join Table · Relationship Gap',
      title:'No trial_indications join table — trial indication is free text',
      body:'trials.indication stores a text string, not a FK to the indications table. This means a trial for "Ulcerative Colitis" and one for "UC" are different records to a query engine. A trial_indications join table would normalize this link and allow reliable cross-trial indication counts.',
    },
    { id:'f-entity-edge-source', sev:'h', cat:'Relationship Quality · Provenance',
      title:'Entity edges have no source or confidence level',
      body:'entity_edges connects entities (drug↔company, company↔company, etc.) but stores no source_id or confidence_level. This means Meridian cannot explain where a relationship came from — was it sourced from a press release, a trial, or AI inference? Every edge should have source, confidence, and review_status.',
    },
    { id:'f-company-drug-no-type', sev:'m', cat:'Relationship Quality · Completeness',
      title:'Company-to-drug relationships lack a relationship_type',
      body:'A company can be an originator, owner, licensee, licensor, co-developer, trial sponsor, or acquirer around a drug. Currently, Meridian stores company-drug links without a relationship_type field. This means "Roche" in a drug record could mean they discovered it, licensed it in, or are running a trial — the relationship is ambiguous.',
    },
    { id:'f-no-ontology-versions', sev:'m', cat:'Migration Safety · Versioning',
      title:'No ontology version tracking',
      body:'When the disease_areas table is eventually migrated to therapeutic_areas, there will be no way to compare drug counts between ontology versions. A drug counted under "IBD" in v1 might land under "Gastroenterology" in v2 with a different count if indications were also reorganized. An ontology_versions table would make this comparison auditable.',
    },
    { id:'f-ind-no-ta', sev:'h', cat:'Missing Relationship · Structural',
      title:'Indications have no therapeutic_area_id foreign key',
      body:'The indications table has a disease_area text field pointing to legacy disease_areas IDs (which are targets and biology tags, not therapeutic areas). There is no therapeutic_area_id FK to a normalized therapeutic_areas table. This is the root of the ontology confusion — until indications have a clean therapeutic area parent, the derived chain (Drug → Indication → Therapeutic Area) cannot be traversed.',
    },
    { id:'f-tce-correct', sev:'l', cat:'Terminology · Modality',
      title:'TCE = T-cell Engager, not T-cell Engineering',
      body:'T-cell Engager (TCE) is a bispecific antibody format designed to redirect cytotoxic T-cells against tumor targets (e.g. BCMA × CD3). If any record or label describes this as "T-cell Engineering," the terminology is incorrect. T-cell Engineering is a broader concept (includes CAR-T, TCR therapy). For Meridian\'s oncology tab, the correct label is T-Cell Therapies (broader) or T-cell Engager (specific modality).',
    },
  ];

  const html = `<div style="font-size:11px;color:#64748b;margin-bottom:12px;line-height:1.7">
    <strong style="color:#475569">${flags.filter(f=>f.sev==='h').length} HIGH</strong> ·
    <strong style="color:#92400e">${flags.filter(f=>f.sev==='m').length} MEDIUM</strong> ·
    <strong style="color:#1e40af">${flags.filter(f=>f.sev==='l').length} LOW</strong> severity flags detected.
    Use the review controls to track which issues have been accepted, rejected, or need discussion.
  </div>
  <div class="ont-flags">
    ${flags.map(flag => {
      const stored = (localStorage.getItem('ont-flag-' + flag.id) || 'proposed');
      const sevLbl = flag.sev==='h'?'HIGH':flag.sev==='m'?'MEDIUM':'LOW';
      return `<div class="ont-flag sev-${flag.sev}" id="ont-flag-${flag.id}">
        <div class="ont-flag-left">
          <div class="ont-flag-cat">${flag.cat}</div>
          <div class="ont-flag-title">${flag.title}</div>
          <div class="ont-flag-body">${flag.body}</div>
          <div class="ont-flag-review">
            ${['proposed','accepted','rejected','discuss'].map(s =>
              `<button class="ont-rvw-btn${stored===s?' rv-'+s:''}" onclick="_ontFlagReview('${flag.id}','${s}')">${s.charAt(0).toUpperCase()+s.slice(1)}</button>`
            ).join('')}
          </div>
        </div>
        <div class="ont-flag-sev ${flag.sev}">${sevLbl}</div>
      </div>`;
    }).join('')}
  </div>`;

  m.innerHTML = html;
}

function _ontFlagReview(flagId, status) {
  localStorage.setItem('ont-flag-' + flagId, status);
  const flagEl = document.getElementById('ont-flag-' + flagId);
  if (!flagEl) return;
  flagEl.querySelectorAll('.ont-rvw-btn').forEach(btn => {
    btn.className = 'ont-rvw-btn';
    if (btn.textContent.toLowerCase() === status || btn.textContent.toLowerCase() === 'discuss' && status === 'discuss') {
      btn.classList.add('rv-' + status);
    }
  });
  // re-set all buttons cleanly
  flagEl.querySelectorAll('.ont-rvw-btn').forEach(btn => {
    const s = btn.getAttribute('onclick').match(/'(\w+)'\)$/)[1];
    btn.className = 'ont-rvw-btn' + (s === status ? ' rv-' + s : '');
  });
}

// ── E: Gap Finder ─────────────────────────────────────────────────────────────
function _renderOntGaps({ indRows, daRows, counts }) {
  const m = document.getElementById('ont-gaps-mount');
  if (!m) return;

  const existingIndIds = new Set((indRows||[]).map(r => (r.id||'').toLowerCase()));

  const potentialMissing = [
    { id:'ra', name:'Rheumatoid Arthritis', area:'rheumatology' },
    { id:'sle', name:'Systemic Lupus Erythematosus', area:'rheumatology' },
    { id:'sjogrens', name:'Sjögren\'s Syndrome', area:'rheumatology' },
    { id:'eoe', name:'Eosinophilic Esophagitis', area:'gastroenterology' },
    { id:'psc', name:'Primary Sclerosing Cholangitis', area:'gastroenterology' },
    { id:'nmo', name:'Neuromyelitis Optica Spectrum', area:'neurology' },
  ].filter(p => !existingIndIds.has(p.id));

  const gaps = [
    { type:'Missing Table', cls:'gap-h', title:'therapeutic_areas table does not exist',
      body:'The current disease_areas table is used as a proxy for therapeutic areas but contains misclassified records. The correct structure is a clean therapeutic_areas table with 7 entries (Gastroenterology, Respiratory, Dermatology, Rheumatology, Neurology, Ophthalmology, Oncology) and a FK from indications.therapeutic_area_id.',
      fix:'Phase 1: CREATE TABLE therapeutic_areas — populate alongside disease_areas, do not replace yet'
    },
    { type:'Missing Table', cls:'gap-h', title:'routes_of_administration table does not exist',
      body:'IV, SC, Oral, Inhaled, Intravitreal, Topical are currently not stored as structured records. Route appears in trial arm text and is sometimes implied by modality. Without this table, competitive route-of-delivery analysis is impossible.',
      fix:'CREATE TABLE routes_of_administration (id, name, abbreviation, description)'
    },
    { type:'Missing Join Tables', cls:'gap-h', title:'5 critical join tables are missing',
      body:'drug_targets, drug_indications, drug_modalities, drug_routes, indication_biology_tags — without these, drug-to-ontology relationships are stored as free text and cannot be reliably queried, counted, or validated.',
      fix:'Phase 2: Create join tables after ontology tables are stable'
    },
    ...(potentialMissing.length > 0 ? [{
      type:'Missing Indications', cls:'gap-m', title:`${potentialMissing.length} common indications may be missing`,
      body:`These indications appear in trial and signal text but may not have formal indication records: ${potentialMissing.map(p=>p.name).join(', ')}. Without these records, drugs targeting these diseases cannot be properly classified.`,
      fix:'INSERT INTO indications for each missing indication'
    }] : []),
    { type:'Structural Gap', cls:'gap-m', title:'disease_areas.id values are used as foreign keys in 3+ tables',
      body:'company_areas.area_id, drug_area_scores.disease_area, targets.disease_area, and potentially others FK to disease_areas.id. If disease_areas is cleaned up or replaced, all these FKs will break. An ontology_mappings table (legacy_id → new_id) must exist before any migration.',
      fix:'CREATE TABLE ontology_mappings (legacy_area, new_therapeutic_area) before touching disease_areas'
    },
    { type:'Conceptual Gap', cls:'gap-m', title:'Relationship provenance: no source or confidence on entity-to-ontology links',
      body:'Meridian cannot currently answer WHY a drug is classified in a given area — the relationship has no source, confidence level, or created_by field. The platform can tell you that SIM0709 is in Gastroenterology but cannot show the chain: SIM0709 → UC/CD → Gastroenterology (sourced from press release, confidence: high).',
      fix:'Add source_id, confidence_level, relationship_type, and review_status to all major join tables (Phase 3)'
    },
    { type:'Version Gap', cls:'gap-m', title:'No ontology version tracking',
      body:'If the disease_areas table is migrated to therapeutic_areas, there is no way to compare drug counts between ontology versions. A drug counted under "IBD" in v1 might land in "Gastroenterology" in v2 — without version tracking, this change is invisible.',
      fix:'Add ontology_version field to major tables, or create an ontology_versions audit log'
    },
  ];

  m.innerHTML = `<div class="ont-gaps">${gaps.map(g => `
    <div class="ont-gap-card ${g.cls}">
      <div class="ont-gap-type">${g.type}</div>
      <div class="ont-gap-title">${g.title}</div>
      <div class="ont-gap-body">${g.body}</div>
      <div class="ont-gap-fix">→ ${g.fix}</div>
    </div>`).join('')}</div>`;
}

// ── F: Migration Plan ─────────────────────────────────────────────────────────
function _renderOntMigration(daRows) {
  const m = document.getElementById('ont-migration-mount');
  if (!m) return;

  const TARGET_IDS   = ['tl1a','tslp','il4ra','fcrn','igf1r'];
  const BAD_AREAS    = ['ted','atopy','autoimmune','t-cell'];

  const currentBad  = daRows.filter(r => {
    const id = (r.id||'').toLowerCase(), nm = (r.name||'').toLowerCase();
    return TARGET_IDS.some(t=>id.includes(t)||nm.includes(t)) || BAD_AREAS.some(t=>id.includes(t)||nm.includes(t));
  }).map(r => r.name||r.id);

  const currentOk   = daRows.filter(r => {
    const id = (r.id||'').toLowerCase(), nm = (r.name||'').toLowerCase();
    return !TARGET_IDS.some(t=>id.includes(t)||nm.includes(t)) && !BAD_AREAS.some(t=>id.includes(t)||nm.includes(t));
  }).map(r => r.name||r.id);

  const proposedTA = ['Gastroenterology','Respiratory','Dermatology','Rheumatology','Neurology','Ophthalmology','Oncology'];
  const proposedInd = ['UC','CD','EoE','Asthma','COPD','AD','CSU','HS','RA','SLE','Sjögren\'s','gMG','CIDP','TED','MM','ALL'];
  const proposedBT  = ['autoimmune','atopy','type_2','type_17','fibrosis','eosinophilic','alarmin','complement','b_cell','autoantibody','pruritus','barrier_dysfunction','mast_cell','orbital_fibroblast','gut_microbiome'];

  m.innerHTML = `
    <div class="ont-mig">
      <div class="ont-mig-col cur">
        <div class="ont-mig-hd cur">⚠ Current: disease_areas (mixed)</div>
        <div class="ont-mig-sh">Items that belong here (correct)</div>
        ${currentOk.map(n=>`<div class="ont-mig-item good">${n}</div>`).join('') || '<div class="ont-mig-item neu">(none confirmed correct)</div>'}
        <div class="ont-mig-sh">Items that are MISCLASSIFIED</div>
        ${currentBad.map(n=>`<div class="ont-mig-item bad">${n}</div>`).join('') || '<div class="ont-mig-item neu">(loading…)</div>'}
        <div class="ont-mig-sh">What's missing</div>
        ${proposedTA.map(t=>`<div class="ont-mig-item bad">${t} (not present)</div>`).join('')}
      </div>
      <div class="ont-mig-col pro">
        <div class="ont-mig-hd pro">✓ Proposed: three clean tables</div>
        <div class="ont-mig-sh">therapeutic_areas (7 rows)</div>
        ${proposedTA.map(t=>`<div class="ont-mig-item good">${t}</div>`).join('')}
        <div class="ont-mig-sh">indications (16 rows, already mostly exists)</div>
        ${proposedInd.map(t=>`<div class="ont-mig-item good">${t}</div>`).join('')}
        <div class="ont-mig-sh">biology_tags (normalized, 15 rows)</div>
        ${proposedBT.map(t=>`<div class="ont-mig-item good">${t}</div>`).join('')}
      </div>
    </div>

    <div style="margin-top:20px">
      <div style="font-size:13px;font-weight:800;color:#0f172a;margin-bottom:12px">3-Phase Safe Migration</div>
      <div class="ont-phases">
        <div class="ont-phase" style="border-top:4px solid #3b82f6">
          <div class="ont-phase-num">Phase 1 · Add New Structure</div>
          <div class="ont-phase-title">Create without breaking</div>
          <div class="ont-phase-item">CREATE TABLE therapeutic_areas (id, name, description)</div>
          <div class="ont-phase-item">CREATE TABLE routes_of_administration (id, name, abbreviation)</div>
          <div class="ont-phase-item">CREATE TABLE ontology_mappings (legacy_area, new_therapeutic_area)</div>
          <div class="ont-phase-item">Populate therapeutic_areas with 7 rows</div>
          <div class="ont-phase-item">Populate ontology_mappings (ibd→gastroenterology, ted→ophthalmology, atopy→dermatology, autoimmune→rheumatology)</div>
          <div class="ont-phase-item">Keep disease_areas untouched — dashboard still reads from it</div>
        </div>
        <div class="ont-phase" style="border-top:4px solid #f59e0b">
          <div class="ont-phase-num">Phase 2 · Switch Logic</div>
          <div class="ont-phase-title">Verify, then migrate</div>
          <div class="ont-phase-item">Add therapeutic_area_id FK to indications table</div>
          <div class="ont-phase-item">Run validation: every indication maps to exactly one therapeutic area</div>
          <div class="ont-phase-item">Update dashboard widgets to read from therapeutic_areas via ontology_mappings</div>
          <div class="ont-phase-item">Create drug_targets, drug_indications join tables</div>
          <div class="ont-phase-item">Run coverage report: what % of drugs have proper joins?</div>
          <div class="ont-phase-item">Verify ontology version v1 vs v2 counts match expectations</div>
        </div>
        <div class="ont-phase" style="border-top:4px solid #10b981">
          <div class="ont-phase-num">Phase 3 · Clean Up</div>
          <div class="ont-phase-title">Remove legacy structures</div>
          <div class="ont-phase-item">Remove misclassified records from disease_areas (targets, TED, Atopy, Autoimmune)</div>
          <div class="ont-phase-item">Deprecate disease_areas in favor of therapeutic_areas</div>
          <div class="ont-phase-item">Normalize biology_tags into standalone table with indication_biology_tags join</div>
          <div class="ont-phase-item">Add source_id + confidence_level to all join tables</div>
          <div class="ont-phase-item">Run full relationship coverage report — target 90%+ drug coverage</div>
        </div>
      </div>
    </div>

    <div style="margin-top:16px;padding:14px 18px;background:#f0fdf4;border:1px solid #86efac;border-radius:8px;font-size:12px;color:#14532d;line-height:1.8">
      <strong>The one rule to follow throughout migration:</strong><br>
      The dashboard should reference IDs, not display names.
      <code style="background:#dcfce7;padding:1px 5px;border-radius:3px">disease_area_id = "ibd"</code> is safe.
      <code style="background:#dcfce7;padding:1px 5px;border-radius:3px">disease_area = "IBD"</code> is fragile.
      If you use ontology_mappings as a translation layer, the dashboard never has to know about the migration — it just reads different rows.
    </div>`;
}

// ── H: Impact Analysis ───────────────────────────────────────────────────────
async function _renderOntImpact(daRows) {
  const m = document.getElementById('ont-impact-mount');
  if (!m) return;

  const IMPACT_META = {
    'tl1a':       { type:'Target',              tc:'#ef4444', risk:'HIGH',   tabs:['TL1A × IL-23p19 tab'],           tArea:'Gastroenterology (via UC / CD)',               action:'Keep as dashboard tab driver. Ensure it exists in targets table. Do NOT use as therapeutic area — it is a molecule.' },
    'tslp':       { type:'Target',              tc:'#ef4444', risk:'HIGH',   tabs:['TSLP × IL-33 tab'],              tArea:'Respiratory (via Asthma / COPD)',              action:'Keep as dashboard tab driver. Add to targets table if not present. Do NOT use as therapeutic area.' },
    'il4ra':      { type:'Target',              tc:'#ef4444', risk:'HIGH',   tabs:['IL-4Rα / Atopy tab'],            tArea:'Dermatology + Respiratory (via AD, CSU, Asthma)', action:'Keep as dashboard tab driver. Already in targets table. Do NOT use as therapeutic area.' },
    'igf1r':      { type:'Target',              tc:'#ef4444', risk:'HIGH',   tabs:['IGF-1R × TSHR / TED tab'],       tArea:'Ophthalmology (via TED)',                      action:'Keep as dashboard tab driver. Already in targets table. Do NOT use as therapeutic area.' },
    'fcrn':       { type:'Target',              tc:'#ef4444', risk:'HIGH',   tabs:['FcRn Bispecific tab'],            tArea:'Neurology + Rheumatology (via gMG, CIDP, SLE)', action:'Keep as dashboard tab driver. Already in targets table. Do NOT use as therapeutic area.' },
    'tcell':      { type:'Platform / Modality', tc:'#f59e0b', risk:'MEDIUM', tabs:['T-Cell Therapies tab'],          tArea:'Oncology (via MM, ALL)',                       action:'Keep as dashboard tab driver. Classify as technology platform/modality concept — NOT a therapeutic area.' },
    'ibd':        { type:'Disease Family',      tc:'#f59e0b', risk:'HIGH',   tabs:['IBD drug filter'],               tArea:'Gastroenterology',                            action:'Map to Gastroenterology via ontology_mappings. Split into UC, CD, EoE at indication level. Do not delete until all FKs migrated.' },
    'respiratory':{ type:'Therapeutic Area ✓',  tc:'#10b981', risk:'LOW',    tabs:['Respiratory drug filter'],       tArea:'Respiratory',                                 action:'Direct map to Respiratory therapeutic area. Most correctly classified record — lowest migration risk.' },
    'atopy':      { type:'Biology Tag',         tc:'#8b5cf6', risk:'MEDIUM', tabs:['IL-4Rα tab (Atopy subfilter)'], tArea:'Dermatology / Respiratory (via AD, CSU, Asthma)', action:'Move to biology_tags table. Map to Dermatology + Respiratory through indications — not as a therapeutic area.' },
    'ted':        { type:'Indication',          tc:'#f59e0b', risk:'HIGH',   tabs:['IGF-1R × TSHR / TED tab'],       tArea:'Ophthalmology',                               action:'Remove from disease_areas. Already in indications table. Map to Ophthalmology therapeutic area via ontology_mappings.' },
    'autoimmune': { type:'Biology Tag',         tc:'#8b5cf6', risk:'LOW',    tabs:['Cross-area autoimmune filter'],  tArea:'Multiple: Rheumatology, Dermatology, Neurology', action:'Move to biology_tags table. Does not map to one therapeutic area — spans multiple. Remove from disease_areas after mapping.' },
  };

  const riskCls = r => r === 'HIGH' ? 'rh' : r === 'MEDIUM' ? 'rm' : 'rl';

  // Fetch live counts per area from drug_area_scores and indications
  const countResults = await Promise.all((daRows||[]).map(async r => {
    const id = (r.id||'').toLowerCase();
    const [dasRes, indRes] = await Promise.all([
      _sb.from('drug_area_scores').select('*',{count:'exact',head:true}).eq('area_id', id),
      _sb.from('indications').select('*',{count:'exact',head:true}).eq('disease_area', id),
    ]);
    return { id, drugs: dasRes.count||0, inds: indRes.count||0 };
  }));
  const cMap = {};
  countResults.forEach(c => { cMap[c.id.toLowerCase()] = c; });

  const cards = (daRows||[]).map(r => {
    const id = (r.id||'').toLowerCase();
    const meta = IMPACT_META[id] || { type:'Unclassified', tc:'#94a3b8', risk:'UNKNOWN', tabs:[], tArea:'Needs manual review', action:'Classify manually before including in migration plan.' };
    const cnt  = cMap[id] || { drugs:0, inds:0 };
    return `<div class="ont-impact-card" id="ont-ic-${id}">
      <div class="ont-impact-hd">
        <span class="ont-impact-id">${r.id||id}</span>
        <span class="ont-impact-type" style="background:${meta.tc}22;color:${meta.tc}">${meta.type}</span>
        <span class="ont-impact-risk ${riskCls(meta.risk)}">⚠ ${meta.risk}</span>
      </div>
      <div class="ont-impact-body">
        <div style="font-size:12px;font-weight:700;color:#0f172a;margin-bottom:6px">${r.name||r.id}</div>
        <div class="ont-impact-stat">
          <span class="ont-impact-pill">💊 ${cnt.drugs} drugs (drug_area_scores)</span>
          <span class="ont-impact-pill">🏷️ ${cnt.inds} linked indications</span>
        </div>
        ${meta.tabs.length ? `<div class="ont-impact-tabs">📊 Dashboard: ${meta.tabs.join(' · ')}</div>` : ''}
        <div class="ont-impact-sh">Correct therapeutic area</div>
        <div style="font-size:11px;color:#374151;font-weight:600">${meta.tArea}</div>
        <div class="ont-impact-sh">Migration action</div>
        <div class="ont-impact-action">${meta.action}</div>
      </div>
      <button class="ont-inspect-btn" id="ont-inspect-btn-${id}" onclick="ontInspectArea('${id}', this)">🔍 Inspect Records →</button>
      <div class="ont-inspect-body" id="ont-inspect-${id}"></div>
    </div>`;
  });

  m.innerHTML = `
    <div style="font-size:11px;color:#64748b;margin-bottom:14px;line-height:1.7">
      Every legacy <code>disease_areas</code> record shown with its true classification, live drug count from <code>drug_area_scores</code>,
      which dashboard tabs depend on it, and the safe migration action.
      <strong style="color:#991b1b">HIGH</strong> = many drugs / tabs depend on this ID.
      <strong style="color:#92400e">MEDIUM</strong> = moderate dependencies.
      <strong style="color:#065f46">LOW</strong> = safe to migrate early.
    </div>
    <div class="ont-impact-grid">${cards.join('')}</div>
    <div style="margin-top:16px;padding:14px 18px;background:#fffbeb;border:1px solid #fde68a;border-radius:8px;font-size:11px;color:#92400e;line-height:1.8">
      <strong>⚠ Before changing any legacy ID:</strong> Every table that FKs to <code>disease_areas</code> must be audited first.
      Known dependents: <code>drug_area_scores.area_id</code> · <code>company_areas.area_id</code> · <code>targets.disease_area</code> · <code>target_pairs.area</code> · <code>indications.disease_area</code>.
      Each legacy ID must have a row in <code>ontology_mappings</code> before it is removed.
    </div>`;
}

// ── I: Relationship Coverage Scoreboard ──────────────────────────────────────
async function _renderOntCoverage() {
  const m = document.getElementById('ont-coverage-mount');
  if (!m) return;

  const qc = async (table, filters) => {
    let q = _sb.from(table).select('*',{count:'exact',head:true});
    (filters||[]).forEach(f => {
      if (f[0] === '!null') q = q.not(f[1],'is',null);
      else if (f[0] === 'neq')  q = q.neq(f[1], f[2]);
      else if (f[0] === 'eq')   q = q.eq(f[1], f[2]);
    });
    const { count } = await q;
    return count || 0;
  };

  const [
    totalDrugs,
    drugsWithCompany,
    drugsWithMechanism,
    drugsWithArea,
    drugsWithModality,
    drugsWithStage,
    totalTrials,
    trialsWithDrug,
    trialsWithPhase,
    trialsWithIndication,
    totalDeals,
    dealsWithCompany,
    totalCatalysts,
    catWithSource,
    totalSignals,
    sigWithEntity,
    totalEdges,
    edgesWithConf,
  ] = await Promise.all([
    qc('drugs'),
    qc('drugs',[['!null','company'],['neq','company','']]),
    qc('drugs',[['!null','mechanism'],['neq','mechanism','']]),
    qc('drugs',[['!null','disease_area'],['neq','disease_area','']]),
    qc('drugs',[['!null','modality'],['neq','modality','']]),
    qc('drugs',[['!null','stage'],['neq','stage','']]),
    qc('trials'),
    qc('trials',[['!null','drug_id']]),
    qc('trials',[['!null','phase'],['neq','phase','']]),
    qc('trials',[['!null','indication'],['neq','indication','']]),
    qc('deals'),
    qc('deals',[['!null','company_id']]),
    qc('catalysts'),
    qc('catalysts',[['!null','source'],['neq','source','']]),
    qc('intel'),
    qc('intel',[['!null','entity_id']]),
    qc('entity_edges'),
    qc('entity_edges',[['!null','confidence_level']]),
  ]);

  const pct = (n,d) => d > 0 ? Math.round(n/d*100) : 0;
  const barHtml = (n, d) => {
    const p = pct(n,d);
    const col = p >= 80 ? '#10b981' : p >= 50 ? '#f59e0b' : '#ef4444';
    return `<div class="ont-cov-bar-wrap"><div class="ont-cov-bar" style="width:${p}%;background:${col}"></div></div><span class="ont-cov-pct" style="color:${col}">${p}%</span>`;
  };
  const row = (label, n, d, req, note) => `<tr>
    <td style="font-weight:600;color:#374151">${label}${note?`<div style="font-size:9px;color:#94a3b8;font-weight:400;margin-top:1px">${note}</div>`:''}  </td>
    <td style="text-align:right;font-weight:700;color:#0f172a;white-space:nowrap">${n.toLocaleString()} / ${d.toLocaleString()}</td>
    <td style="white-space:nowrap">${barHtml(n,d)}</td>
    <td><span class="ont-cov-req ${req==='req'?'cov-req':'cov-rec'}">${req==='req'?'REQUIRED':'RECOMMENDED'}</span></td>
  </tr>`;
  const rowMissing = (label, note) => `<tr>
    <td style="color:#94a3b8">${label}<div style="font-size:9px;color:#94a3b8;font-weight:400;margin-top:1px;font-style:italic">${note}</div></td>
    <td style="text-align:right;color:#cbd5e1">—</td>
    <td><span style="font-size:9px;background:#f1f5f9;color:#94a3b8;padding:1px 8px;border-radius:3px;font-weight:700">TABLE MISSING</span></td>
    <td><span class="ont-cov-req cov-req">REQUIRED</span></td>
  </tr>`;

  m.innerHTML = `
    <div style="font-size:11px;color:#64748b;margin-bottom:16px;line-height:1.7">
      What percent of entities have each required and recommended relationship?
      <strong style="color:#10b981">Green 80%+</strong> ·
      <strong style="color:#92400e">Yellow 50–79%</strong> ·
      <strong style="color:#991b1b">Red &lt;50%</strong>.
      Rows marked TABLE MISSING represent relationships that can't exist yet — blocked by Phase 2 schema work.
    </div>

    <div class="ont-cov-entity">
      <div class="ont-cov-title">💊 Drugs <span style="font-size:12px;font-weight:600;color:#64748b">${totalDrugs} total</span></div>
      <table class="ont-cov-table">
        <thead><tr><th style="width:40%">Relationship</th><th style="text-align:right">Count</th><th>Coverage</th><th>Type</th></tr></thead>
        <tbody>
          ${row('Has company', drugsWithCompany, totalDrugs, 'req', 'drugs.company field')}
          ${row('Has mechanism / target', drugsWithMechanism, totalDrugs, 'req', 'drugs.mechanism field (free text — no join table yet)')}
          ${row('Has disease area (legacy)', drugsWithArea, totalDrugs, 'req', 'drugs.disease_area field')}
          ${row('Has modality', drugsWithModality, totalDrugs, 'req', 'drugs.modality field')}
          ${row('Has stage', drugsWithStage, totalDrugs, 'rec', 'drugs.stage field')}
          ${rowMissing('Normalized target FK (drug_targets)', 'Create drug_targets join table in Phase 2')}
          ${rowMissing('Normalized indication FK (drug_indications)', 'Create drug_indications join table in Phase 2')}
          ${rowMissing('Route of administration (drug_routes)', 'Create routes_of_administration + drug_routes in Phase 1/2')}
        </tbody>
      </table>
    </div>

    <div class="ont-cov-entity">
      <div class="ont-cov-title">🔬 Trials <span style="font-size:12px;font-weight:600;color:#64748b">${totalTrials} total</span></div>
      <table class="ont-cov-table">
        <thead><tr><th style="width:40%">Relationship</th><th style="text-align:right">Count</th><th>Coverage</th><th>Type</th></tr></thead>
        <tbody>
          ${row('Linked to drug (drug_id FK)', trialsWithDrug, totalTrials, 'req', '')}
          ${row('Has phase recorded', trialsWithPhase, totalTrials, 'req', '')}
          ${row('Has indication text', trialsWithIndication, totalTrials, 'rec', 'free text only — no normalized FK')}
          ${rowMissing('Normalized indication FK (trial_indications)', 'Create trial_indications join table in Phase 2')}
        </tbody>
      </table>
    </div>

    <div class="ont-cov-entity">
      <div class="ont-cov-title">🤝 Deals <span style="font-size:12px;font-weight:600;color:#64748b">${totalDeals} total</span></div>
      <table class="ont-cov-table">
        <thead><tr><th style="width:40%">Relationship</th><th style="text-align:right">Count</th><th>Coverage</th><th>Type</th></tr></thead>
        <tbody>
          ${row('Has company link', dealsWithCompany, totalDeals, 'req', '')}
          ${rowMissing('Drug-level link (deal_drugs)', 'Most deals link at company level only — drug_id FK would require deal_drugs join table')}
        </tbody>
      </table>
    </div>

    <div class="ont-cov-entity">
      <div class="ont-cov-title">⚡ Catalysts <span style="font-size:12px;font-weight:600;color:#64748b">${totalCatalysts} total</span></div>
      <table class="ont-cov-table">
        <thead><tr><th style="width:40%">Relationship</th><th style="text-align:right">Count</th><th>Coverage</th><th>Type</th></tr></thead>
        <tbody>
          ${row('Has source', catWithSource, totalCatalysts, 'req', 'catalysts.source field')}
        </tbody>
      </table>
    </div>

    <div class="ont-cov-entity">
      <div class="ont-cov-title">🧠 Signals (Intel) <span style="font-size:12px;font-weight:600;color:#64748b">${totalSignals} total</span></div>
      <table class="ont-cov-table">
        <thead><tr><th style="width:40%">Relationship</th><th style="text-align:right">Count</th><th>Coverage</th><th>Type</th></tr></thead>
        <tbody>
          ${row('Has linked entity (entity_id)', sigWithEntity, totalSignals, 'req', '')}
        </tbody>
      </table>
    </div>

    <div class="ont-cov-entity">
      <div class="ont-cov-title">🔗 Entity Edges <span style="font-size:12px;font-weight:600;color:#64748b">${totalEdges} total</span></div>
      <table class="ont-cov-table">
        <thead><tr><th style="width:40%">Relationship</th><th style="text-align:right">Count</th><th>Coverage</th><th>Type</th></tr></thead>
        <tbody>
          ${row('Has confidence level', edgesWithConf, totalEdges, 'req', 'entity_edges.confidence_level field')}
          ${rowMissing('Has source_id', 'Add source_id FK to entity_edges table in Phase 3')}
        </tbody>
      </table>
    </div>

    <div style="margin-top:6px;padding:12px 16px;background:#f8fafc;border-radius:8px;font-size:11px;color:#64748b;line-height:1.7">
      <strong style="color:#0f172a">Coverage target:</strong>
      Required relationships → 90%+ before Phase 5 (switch dashboard logic).
      Recommended relationships → 70%+ before Phase 6 (deprecate legacy).
      TABLE MISSING rows are blocked by Phase 2 schema work — required before backfill can begin.
    </div>`;
}

// ── J: Migration Roadmap ─────────────────────────────────────────────────────
function _renderOntRoadmap() {
  const m = document.getElementById('ont-roadmap-mount');
  if (!m) return;

  const phases = [
    {
      num: 'Phase 0', title: 'Audit & Dependency Mapping', status: 'done', statusLbl: '✓ Complete',
      purpose: 'Understand the current structure, risks, dependencies, and gaps before touching anything in production.',
      left: {
        hd: 'Completed',
        items: [
          { done:true, text:'Terminology cleanup — "therapeutic area" language adopted in UI' },
          { done:true, text:'Quality flags expanded to 18 flags (HIGH/MEDIUM/LOW severity)' },
          { done:true, text:'Section H: Impact Analysis — per-legacy-ID dependency cards with live Supabase counts' },
          { done:true, text:'Section I: Relationship Coverage Scoreboard — baseline before Phase 1' },
          { done:true, text:'Click-through inspection — drugs, trials, overlap distribution, evidence layer' },
          { done:true, text:'Section J: Migration Roadmap with phase gates' },
          { done:true, text:'Advisor ontology review — therapeutic area model, knowledge graph design, migration safety rules' },
        ]
      },
      right: {
        hd: 'Phase 0 outcomes',
        items: [
          { done:true, text:'All 11 legacy IDs classified: 5 targets, 2 biology tags, 1 indication, 1 disease family, 1 direct map, 1 platform concept' },
          { done:true, text:'Clinical Specialty therapeutic area model confirmed (Gastroenterology, Respiratory, Dermatology, Rheumatology, Neurology, Ophthalmology, Oncology)' },
          { done:true, text:'ontology_edges architectural role defined: secondary/derived layer; primary truth in structured join tables (Phase 2)' },
          { done:true, text:'Phase 1 SQL plan reviewed and approved by advisor — execution approved 2026-05-25' },
        ]
      },
      criteria: [
        '✓ Every legacy disease_areas ID has a mapped true classification (ontology_mappings, 11 rows)',
        '✓ Every FK dependency to disease_areas is documented (Section H Impact Analysis)',
        '✓ Coverage Scoreboard shows baseline before Phase 1',
        '✓ No schema changes made yet — all legacy IDs and fields unchanged at Phase 0 exit',
      ],
      next: 'Phase 0 complete 2026-05-25. Phase 1 executed same day.',
    },
    {
      num: 'Phase 1', title: 'Add New Ontology Tables', status: 'done', statusLbl: '✓ Complete',
      purpose: 'Create clean new ontology structures alongside the existing ones. No existing tables, columns, or IDs modified.',
      left: {
        hd: '6 Tables Created (2026-05-25)',
        items: [
          { done:true, text:'therapeutic_areas — 7 rows: Gastroenterology, Respiratory, Dermatology, Rheumatology, Neurology, Ophthalmology, Oncology' },
          { done:true, text:'routes_of_administration — 6 rows: IV, SC, Oral, Inhaled, Intravitreal, Topical' },
          { done:true, text:'biology_tags — 18 rows: immune_axis, cell_type, pathway, pathology, phenotype, anatomical_feature, clinical_feature' },
          { done:true, text:'ontology_versions — 2 rows: v1-legacy (active), v2-normalized (draft)' },
          { done:true, text:'ontology_mappings — 11 rows: all legacy disease_areas IDs mapped with type, risk, dashboard tabs affected' },
          { done:true, text:'ontology_edges — 25 seed rows: knowledge graph backbone; UC cluster queryable; 4 graph traversal indexes' },
        ]
      },
      right: {
        hd: 'Advisor notes recorded',
        items: [
          { done:true, text:'ontology_edges = secondary/derived graph layer; primary truth remains in structured join tables (Phase 2)' },
          { done:true, text:'relationship_types table enters Phase 3 roadmap (prevents vocabulary drift: targets vs target_of vs acts_on)' },
          { done:true, text:'mechanism_classes table enters future roadmap (cytokine_blockade, trafficking_inhibition, IgG_reduction, T-cell_engagement)' },
          { done:true, text:'Step 7 (ALTER indications) deferred to Phase 2 — establish drug_targets and drug_indications first' },
          { done:true, text:'disease_areas unchanged: 11 rows intact; drug_area_scores: 214 rows intact — zero dashboard regressions' },
        ]
      },
      criteria: [
        '✓ All 6 new tables exist with correct row counts (7 / 6 / 18 / 2 / 11 / 25)',
        '✓ Exactly one active ontology version (v1-legacy)',
        '✓ All 11 legacy IDs mapped in ontology_mappings',
        '✓ UC knowledge cluster queryable in ontology_edges (5 rows via source_id or target_id = uc)',
        '✓ Legacy disease_areas and drug_area_scores unchanged — zero dashboard regressions',
        '✓ 4 graph traversal indexes created on ontology_edges',
      ],
      next: 'Phase 1 complete. Begin Phase 2 planning: drug_targets → drug_indications → trial_indications (revised priority order per advisor).',
    },
    {
      num: 'Phase 2', title: 'Add Normalized Relationship Tables', status: 'next', statusLbl: 'Next',
      purpose: 'Replace free-text matching with queryable FK relationships. Priority order revised: relationships matter more than classification. All tables are additive — legacy fields remain.',
      left: {
        hd: 'Priority order (revised per advisor)',
        items: [
          { text:'① drug_targets — CRITICAL: drug → molecular target (currently embedded in drugs.mechanism free text)' },
          { text:'② drug_indications — CRITICAL: drug → indication (currently embedded in drugs.disease_area text)' },
          { text:'③ trial_indications — CRITICAL: trial → indication (connects ClinicalTrials.gov data to indication chain)' },
          { text:'④ drug_modalities — IMPORTANT: drug → modality (structured, replaces drugs.modality text)' },
          { text:'⑤ drug_routes — IMPORTANT: drug → route of administration (new — currently not captured)' },
          { text:'⑥ indication_biology_tags — USEFUL: indication → biology tag (Phase 1 biology_tags table now ready)' },
          { text:'⑦ indications.therapeutic_area_id FK — deferred from Phase 1; backfill after drug_indications verified' },
        ]
      },
      right: {
        hd: 'Rules & Dependencies',
        items: [
          { text:'Phase 1 ✓ complete — all 6 tables exist; ontology_edges ready to populate from these join tables' },
          { text:'Each join table needs: relationship_type, confidence_level, source_id, review_status, created_at' },
          { text:'Do NOT remove drugs.mechanism or drugs.disease_area — keep as legacy fallback throughout Phase 2' },
          { text:'Populate ontology_edges FROM join tables (not vice versa) — ontology_edges is secondary/derived' },
          { text:'Coverage Scoreboard (Section I) should show tables moving from TABLE MISSING to actual %' },
        ]
      },
      criteria: [
        'drug_targets, drug_indications, trial_indications all exist and populated (top 3 priority)',
        'Every join table has confidence_level, source_id, review_status fields',
        'ontology_edges populated from structured join tables (not manual inserts)',
        'Coverage Scoreboard shows Drug → Target and Drug → Indication as green or yellow',
        'Legacy fields still in place as fallback',
      ],
      next: 'Begin Phase 2 planning. Start with drug_targets schema design. Key question: how to parse drugs.mechanism free text → target IDs reliably.',
    },
    {
      num: 'Phase 3', title: 'Backfill, Confidence Scoring & Governance', status: 'pending', statusLbl: 'Not Started',
      purpose: 'Populate Phase 2 tables from existing data. Add relationship governance (relationship_types table). Every relationship gets a source, confidence level, and review status.',
      left: {
        hd: 'Backfill Strategy',
        items: [
          { text:'drug_targets: parse drugs.mechanism + target synonyms → confidence: medium, source: derived' },
          { text:'drug_indications: trials.indication + drugs.disease_area → use ontology_mappings for area→indication' },
          { text:'drug_modalities: drugs.modality text → match to modalities table' },
          { text:'indication_biology_tags: normalize existing indications.biology_tags[] into join table' },
          { text:'trial_indications: parse trials.indication free text → match to indications table' },
          { text:'Populate ontology_edges from Phase 2 join tables (derived layer, not hand-inserted)' },
        ]
      },
      right: {
        hd: 'Governance additions (new in Phase 3)',
        items: [
          { text:'relationship_types table — canonical vocabulary for ontology_edges.relationship field. Prevents spelling drift (targets vs target_of vs acts_on). Each type gets: id, label, inverse_label, domain, range, description.' },
          { text:'Confidence rules: FK from trial registry = HIGH; text match to canonical = MEDIUM; AI inference only = LOW (review_status = proposed)' },
          { text:'Do NOT treat AI inference as high confidence without human verification' },
          { text:'Mark all AI-derived rows: created_by = ai_enrichment, review_status = proposed' },
        ]
      },
      criteria: [
        'drug_targets: 70%+ of drugs have at least one normalized target',
        'drug_indications: 70%+ of drugs have at least one normalized indication',
        'All backfilled rows have source, confidence, and review_status',
        'Coverage Scoreboard shows green or yellow for all required drug relationships',
        'Uncertain rows flagged as proposed (not accepted)',
      ],
      next: 'Build enrichment scripts per table. Run on a staging copy first. Compare Coverage Scoreboard before/after.',
    },
    {
      num: 'Phase 4', title: 'Compare Legacy vs. New Ontology', status: 'pending', statusLbl: 'Not Started',
      purpose: 'Verify that the new ontology produces the same or better results as the legacy structure. Catch mismatches before any dashboard logic changes.',
      left: {
        hd: 'Comparison Checks',
        items: [
          { text:'Drug counts: legacy area → new therapeutic area (should match or explain differences)' },
          { text:'Trials by indication: legacy text match vs. trial_indications FK' },
          { text:'Targets by drug: legacy mechanism text vs. drug_targets join' },
          { text:'Modalities by drug: legacy text vs. drug_modalities join' },
          { text:'Companies by asset: legacy company field vs. drug_company_relationships' },
        ]
      },
      right: {
        hd: 'Flag & Resolve',
        items: [
          { text:'Missing records: drugs in legacy area but not mapped to new therapeutic area' },
          { text:'Count mismatches: legacy area = 53 drugs, new TA = 48 drugs → investigate 5 gaps' },
          { text:'Broken joins: drugs with mechanism text that cannot parse to a targets row' },
          { text:'Unexpected category changes: drugs that move areas in the new ontology' },
        ]
      },
      criteria: [
        'Mismatch report exists for every major entity type',
        'All HIGH-risk mismatches resolved before Phase 5',
        'Count differences < 5% or all differences explained',
        'No drug loses all of its area/indication/target relationships in the new ontology',
      ],
      next: 'Build a comparison query set. Add a "v1 vs v2" view to this audit page showing count deltas.',
    },
    {
      num: 'Phase 5', title: 'Gradually Switch Dashboard Logic', status: 'pending', statusLbl: 'Not Started',
      purpose: 'Move dashboard queries from legacy fields to normalized relationships, one module at a time. Legacy fallback logic stays in until the end.',
      left: {
        hd: 'Switch Order',
        items: [
          { text:'Indications panel (uses therapeutic_area_id → therapeutic_areas)' },
          { text:'Drug count widgets (use drug_indications count instead of disease_area match)' },
          { text:'Target panels (use drug_targets instead of mechanism text)' },
          { text:'Modality filters (use drug_modalities instead of modality text)' },
          { text:'Company panels (use drug_company_relationships instead of company field)' },
        ]
      },
      right: {
        hd: 'Safety Rules',
        items: [
          { text:'Use ontology_mappings as translation layer — dashboard never has to know about migration' },
          { text:'Validate counts before and after each module switch' },
          { text:'Keep legacy fields as fallback: if normalized join returns 0, fall back to legacy field' },
          { text:'Switch one module per session — do not batch multiple changes' },
          { text:'Do NOT remove legacy fields during this phase' },
        ]
      },
      criteria: [
        'All major dashboard views read from normalized tables',
        'Legacy fields still present (no deletes yet)',
        'Zero count regressions across all dashboard tabs',
        'All tabs validated with before/after count screenshots',
      ],
      next: 'Do not start Phase 5 until Phase 4 comparison is clean. Begin with the lowest-risk module first.',
    },
    {
      num: 'Phase 6', title: 'Deprecate Legacy Semantics + Future Layers', status: 'future', statusLbl: 'Future',
      purpose: 'Once the new ontology is stable and verified, stop using legacy disease_area semantics. Archive legacy fields. Add mechanism_classes and expanded biology tag vocabulary.',
      left: {
        hd: 'Deprecation Steps',
        items: [
          { text:'Stop writing to disease_area / disease_areas fields in enrichment scripts' },
          { text:'Add deprecated column comments in Supabase schema' },
          { text:'Remove legacy fallback code from dashboard queries' },
          { text:'Archive legacy fields (rename to _legacy_disease_area) rather than DROP COLUMN' },
          { text:'mechanism_classes table: group targets by mechanism (cytokine_blockade → TNF/TL1A/IL23; trafficking_inhibition → α4β7; IgG_reduction → FcRn; T-cell_engagement → CD3; cell_depletion → BCMA). Enables "show me all trafficking inhibitors" query.' },
        ]
      },
      right: {
        hd: 'Gate Criteria (all must pass)',
        items: [
          { text:'No dashboard query reads directly from legacy disease_area IDs' },
          { text:'90%+ of drugs have normalized targets and indications' },
          { text:'All 7 dashboard area tabs validated against new ontology' },
          { text:'Coverage Scoreboard shows green for all required relationships' },
          { text:'Audit page shows zero HIGH-severity migration risk flags unresolved' },
          { text:'ontology_versions v2 is marked active' },
        ]
      },
      criteria: [
        'All legacy "disease area" semantics removed from production logic',
        'Audit page shows zero open HIGH-risk flags',
        'ontology_versions v2 marked active, v1 archived',
        'Meridian can answer all 5 Meridian OS questions via normalized relationships',
      ],
      next: 'Phase 6 is gated on all prior phases being fully verified. Do not rush — the legacy fields are harmless until then.',
    },
  ];

  const statusCls = { done:'rmp-s-done', active:'rmp-s-active', next:'rmp-s-next', pending:'rmp-s-pending', future:'rmp-s-future' };

  const phaseHtml = phases.map((ph, i) => {
    const isActive = ph.status === 'active';
    const bodyItems = side => side.items.map(it =>
      `<div class="ont-rmp-item${it.done?' done':it.block?' block':''}">${it.text}</div>`
    ).join('');
    const criteriaHtml = ph.criteria.map(c => `<div class="ont-rmp-item">${c}</div>`).join('');

    return `<div class="ont-rmp-phase${isActive?' rmp-active':''}">
      <div class="ont-rmp-hd" onclick="(function(el){const b=el.closest('.ont-rmp-phase').querySelector('.ont-rmp-body');b.classList.toggle('open')})(this)">
        <span class="ont-rmp-num">${ph.num}</span>
        <span class="ont-rmp-title">${ph.title}</span>
        <span class="ont-rmp-status ${statusCls[ph.status]}">${ph.statusLbl}</span>
      </div>
      <div class="ont-rmp-body${isActive?' open':''}">
        <div>
          <div class="ont-rmp-col-hd">Purpose</div>
          <div style="font-size:11px;color:#475569;line-height:1.7;margin-bottom:12px">${ph.purpose}</div>
          <div class="ont-rmp-col-hd">${ph.left.hd}</div>
          ${bodyItems(ph.left)}
        </div>
        <div>
          <div class="ont-rmp-col-hd">${ph.right.hd}</div>
          ${bodyItems(ph.right)}
          <div class="ont-rmp-col-hd" style="margin-top:14px">Completion Criteria</div>
          ${criteriaHtml}
        </div>
        <div class="ont-rmp-next">
          <strong>→ Next Safe Action</strong>
          ${ph.next}
        </div>
      </div>
    </div>`;
  }).join('');

  m.innerHTML = `
    <div style="font-size:11px;color:#64748b;margin-bottom:14px;line-height:1.7">
      The audit page is the control room, not the endpoint. This roadmap keeps the migration moving forward safely.
      <strong style="color:#1d4ed8">Phase 0 is open by default</strong> — click any other phase to expand it.
      Do not begin a phase until all completion criteria for the previous phase are met.
    </div>
    <div class="ont-roadmap">${phaseHtml}</div>`;
}

// ── H: Per-area click-through inspection ─────────────────────────────────────
async function ontInspectArea(id, btn) {
  const body = document.getElementById('ont-inspect-' + id);
  if (!body) return;

  // Toggle open/close
  const isOpen = body.classList.contains('open');
  body.classList.toggle('open', !isOpen);
  if (btn) {
    btn.classList.toggle('open', !isOpen);
    btn.textContent = isOpen ? '🔍 Inspect Records →' : '✕ Close';
  }
  if (isOpen) return;

  // Already loaded — just show
  if (body.dataset.loaded === 'true') return;

  body.innerHTML = '<div style="padding:16px;text-align:center;color:#94a3b8;font-size:11px">Loading records…</div>';

  // 1. Drugs in this area (drug_area_scores)
  const { data: dasData } = await _sb.from('drug_area_scores')
    .select('drug_id, overlap, score:strategic_value_score')
    .eq('area_id', id)
    .order('strategic_value_score', { ascending: false })
    .limit(60);

  const drugIds = (dasData||[]).map(d => d.drug_id);
  const overlapMap = {};
  (dasData||[]).forEach(d => { overlapMap[d.drug_id] = d.overlap; });

  // 2. Drug details
  let drugRows = [];
  if (drugIds.length > 0) {
    const { data } = await _sb.from('drugs')
      .select('id, name, company:company_id, mechanism, modality, stage')
      .in('id', drugIds);
    drugRows = data || [];
    // Preserve drug_area_scores order (by score desc)
    const order = {};
    drugIds.forEach((did, i) => { order[did] = i; });
    drugRows.sort((a,b) => (order[a.id]||99) - (order[b.id]||99));
  }

  // 3. Trial count for these drugs
  let trialCount = 0;
  if (drugIds.length > 0) {
    const { count } = await _sb.from('trials').select('*',{count:'exact',head:true}).in('drug_id', drugIds);
    trialCount = count || 0;
  }

  // 4. Catalysts + signals (area_id field — may not exist, handled gracefully)
  let catCount = 0, sigCount = 0;
  const [catRes, sigRes] = await Promise.all([
    _sb.from('catalysts').select('*',{count:'exact',head:true}).eq('area_id', id),
    _sb.from('intel').select('*',{count:'exact',head:true}).eq('area_id', id),
  ]);
  catCount = catRes.error ? 0 : (catRes.count || 0);
  sigCount = sigRes.error ? 0 : (sigRes.count || 0);

  // 5. Coverage analysis for these drugs
  const total = drugRows.length || 1;
  const withCompany   = drugRows.filter(d => d.company   && d.company.trim()).length;
  const withMechanism = drugRows.filter(d => d.mechanism && d.mechanism.trim()).length;
  const withModality  = drugRows.filter(d => d.modality  && d.modality.trim()).length;
  const withStage     = drugRows.filter(d => d.stage     && d.stage.trim()).length;

  // 6. Overlap distribution
  const ovCounts = {};
  (dasData||[]).forEach(d => { if (d.overlap) ovCounts[d.overlap] = (ovCounts[d.overlap]||0)+1; });
  const ovColors = { Direct:'#ef4444', Adjacent:'#f59e0b', 'Same-Space':'#3b82f6', Watch:'#94a3b8' };

  const pct = (n,d) => d > 0 ? Math.round(n/d*100) : 0;
  const covChip = (label, n, d) => {
    const p = pct(n,d);
    const col = p>=80?'#10b981':p>=50?'#f59e0b':'#ef4444';
    return `<span style="font-size:10px;font-weight:600;color:#475569">${label}: <strong style="color:${col}">${p}%</strong> <span style="color:#94a3b8">(${n}/${d})</span></span>`;
  };

  // Drug list rows
  const drugListHtml = drugRows.slice(0, 25).map(d => {
    const ov = overlapMap[d.id];
    const ovCol = ovColors[ov] || '#94a3b8';
    const _dLabel = d.brand_name ? `<span class="drug-brand-name">${d.brand_name}</span>${d.name && d.name.toLowerCase() !== d.brand_name.toLowerCase() ? '<span class="drug-molecule-name">'+d.name+'</span>' : ''}` : (d.name||d.id);
    return `<div style="display:flex;align-items:center;gap:8px;padding:5px 0;border-bottom:1px solid #f8fafc;font-size:11px">
      <span style="flex:1;font-weight:600;color:#0f172a;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${d.name||d.id}">${_dLabel}</span>
      <span style="font-size:10px;color:#64748b;min-width:90px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${d.company||'—'}</span>
      <span style="font-size:9px;font-weight:700;padding:1px 6px;border-radius:3px;background:${ovCol}22;color:${ovCol};flex-shrink:0">${ov||'—'}</span>
      <span style="font-size:9px;color:#94a3b8;min-width:55px;text-align:right;flex-shrink:0">${d.stage||'—'}</span>
    </div>`;
  }).join('');

  const statBox = (n, label, col) => `<div style="text-align:center;background:#f8fafc;border-radius:8px;padding:10px 6px;flex:1">
    <div style="font-size:22px;font-weight:800;color:${col||'#0f172a'}">${n}</div>
    <div style="font-size:9px;font-weight:700;text-transform:uppercase;color:#94a3b8;margin-top:2px">${label}</div>
  </div>`;

  // 7. Build relationship evidence definitions using live counts
  const evConf = c => {
    const m = { HIGH:{bg:'#d1fae5',col:'#065f46'}, MEDIUM:{bg:'#fef3c7',col:'#92400e'}, LOW:{bg:'#fee2e2',col:'#991b1b'}, 'LOW–MEDIUM':{bg:'#fef3c7',col:'#92400e'} };
    return `<span style="font-size:9px;font-weight:800;padding:1px 7px;border-radius:4px;background:${m[c]?.bg||'#f1f5f9'};color:${m[c]?.col||'#64748b'}">${c}</span>`;
  };
  const evStat = (txt, col) => `<span style="font-size:9px;font-weight:700;color:${col}">${txt}</span>`;
  const evidence = [
    { rel:'Drug → Therapeutic Area', source:'drug_area_scores.area_id',    method:'Structural FK',           conf:'LOW',        stat:evStat('Legacy assignment — needs migration', '#ef4444'),   note:'Area IDs mix targets, indications, and biology tags. FK exists but points to a semantically incorrect table. Correct mapping requires ontology_mappings → therapeutic_areas before this link can be trusted.' },
    { rel:'Drug → Company',          source:'drugs.company (text)',          method:'Free text',               conf:'MEDIUM',     stat:evStat(`${withCompany}/${drugRows.length} filled (${pct(withCompany,total)}%)`, withCompany/total>=0.8?'#10b981':'#f59e0b'), note:'Text field — not a normalized FK to companies table. No source_id, no relationship_type field. Cannot distinguish originator vs. licensee vs. trial sponsor from this field alone.' },
    { rel:'Drug → Target',           source:'drugs.mechanism (text)',        method:'Free text / AI enriched', conf:'LOW–MEDIUM',  stat:evStat(`${withMechanism}/${drugRows.length} filled — no join table`, '#f59e0b'), note:'Free-text description of mechanism. Cannot reliably join to targets table as a structural query. Needs drug_targets join table with relationship_type (primary/secondary/inferred) and source_id per relationship.' },
    { rel:'Drug → Indication',       source:'Inferred via drugs.disease_area', method:'Inferred',             conf:'LOW',        stat:evStat('Inferred only — no direct link', '#ef4444'),         note:'Indication is derived from the disease_area field — the same legacy field being migrated. No drug_indications join table exists. Cannot verify confidence or source for this link.' },
    { rel:'Drug → Modality',         source:'drugs.modality (text)',         method:'Free text / AI enriched', conf:'MEDIUM',     stat:evStat(`${withModality}/${drugRows.length} filled (${pct(withModality,total)}%)`, withModality/total>=0.8?'#10b981':'#f59e0b'), note:'Text field matching to modalities lookup table. Route of administration is not separated. Needs drug_modalities join table with source_id.' },
    { rel:'Drug → Trial',            source:'trials.drug_id (FK)',           method:'Direct FK',               conf:'HIGH',       stat:evStat(`${trialCount} trial${trialCount!==1?'s':''} linked`, '#10b981'),           note:'Direct FK exists in trials table. Most reliable structural link in the current schema — this is the pattern all other relationships should follow.' },
  ];

  const evidenceRows = evidence.map(e => `
    <tr>
      <td style="font-weight:700;color:#0f172a;padding:6px 10px;white-space:nowrap;vertical-align:top">${e.rel}</td>
      <td style="font-family:monospace;font-size:10px;color:#475569;padding:6px 10px;vertical-align:top">${e.source}</td>
      <td style="font-size:10px;color:#64748b;font-style:italic;padding:6px 10px;vertical-align:top;white-space:nowrap">${e.method}</td>
      <td style="padding:6px 10px;vertical-align:top">${evConf(e.conf)}</td>
      <td style="padding:6px 10px;vertical-align:top">${e.stat}</td>
    </tr>
    <tr><td colspan="5" style="padding:1px 10px 9px;font-size:10px;color:#94a3b8;border-bottom:1px solid #f1f5f9;line-height:1.5">${e.note}</td></tr>
  `).join('');

  body.dataset.loaded = 'true';
  body.innerHTML = `
    <div style="padding:16px 16px 18px">

      <div style="display:flex;gap:8px;margin-bottom:16px">
        ${statBox(drugRows.length, 'Drugs', '#0f172a')}
        ${statBox(trialCount, 'Trials', '#2563eb')}
        ${statBox(catCount, 'Catalysts', '#f59e0b')}
        ${statBox(sigCount, 'Signals', '#8b5cf6')}
      </div>

      <div style="font-size:10px;font-weight:800;text-transform:uppercase;color:#94a3b8;letter-spacing:.05em;margin-bottom:6px">Relationship Evidence — Source · Method · Confidence</div>
      <div style="overflow-x:auto;margin-bottom:16px;border:1px solid #e2e8f0;border-radius:8px">
        <table style="width:100%;border-collapse:collapse;font-size:11px;min-width:600px">
          <thead><tr style="background:#f8fafc">
            <th style="text-align:left;padding:6px 10px;font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.04em;color:#94a3b8;border-bottom:1px solid #e2e8f0">Relationship</th>
            <th style="text-align:left;padding:6px 10px;font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.04em;color:#94a3b8;border-bottom:1px solid #e2e8f0">Source Field</th>
            <th style="text-align:left;padding:6px 10px;font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.04em;color:#94a3b8;border-bottom:1px solid #e2e8f0">Method</th>
            <th style="text-align:left;padding:6px 10px;font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.04em;color:#94a3b8;border-bottom:1px solid #e2e8f0">Confidence</th>
            <th style="text-align:left;padding:6px 10px;font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.04em;color:#94a3b8;border-bottom:1px solid #e2e8f0">Live Status</th>
          </tr></thead>
          <tbody>${evidenceRows}</tbody>
        </table>
      </div>

      <div style="font-size:10px;font-weight:800;text-transform:uppercase;color:#94a3b8;letter-spacing:.05em;margin-bottom:6px">Record Coverage (${drugRows.length} drugs)</div>
      <div style="display:flex;gap:14px;flex-wrap:wrap;margin-bottom:14px;padding:10px 12px;background:#f8fafc;border-radius:8px">
        ${covChip('Company', withCompany, drugRows.length)}
        ${covChip('Mechanism', withMechanism, drugRows.length)}
        ${covChip('Modality', withModality, drugRows.length)}
        ${covChip('Stage', withStage, drugRows.length)}
      </div>

      ${Object.keys(ovCounts).length ? `
      <div style="font-size:10px;font-weight:800;text-transform:uppercase;color:#94a3b8;letter-spacing:.05em;margin-bottom:6px">Overlap Tier Distribution</div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px">
        ${['Direct','Adjacent','Same-Space','Watch'].filter(t=>ovCounts[t]).map(t =>
          `<span style="font-size:11px;font-weight:700;padding:3px 10px;border-radius:20px;background:${ovColors[t]}22;color:${ovColors[t]}">${t}: ${ovCounts[t]}</span>`
        ).join('')}
      </div>` : ''}

      ${drugRows.length > 0 ? `
      <div style="font-size:10px;font-weight:800;text-transform:uppercase;color:#94a3b8;letter-spacing:.05em;margin-bottom:6px">
        Drugs in this area${drugRows.length > 25 ? ` — top 25 of ${drugRows.length}` : ` — ${drugRows.length} total`}
      </div>
      <div style="max-height:260px;overflow-y:auto;border:1px solid #e2e8f0;border-radius:8px;padding:2px 10px 6px">
        <div style="display:flex;gap:8px;padding:5px 0 4px;border-bottom:1px solid #e2e8f0;font-size:9px;font-weight:800;text-transform:uppercase;color:#94a3b8;position:sticky;top:0;background:white">
          <span style="flex:1">Drug</span><span style="min-width:90px">Company</span><span style="min-width:58px">Overlap</span><span style="min-width:55px;text-align:right">Stage</span>
        </div>
        ${drugListHtml}
      </div>` : '<div style="font-size:11px;color:#94a3b8;text-align:center;padding:12px">No drugs found in drug_area_scores for this area ID.</div>'}

      <div style="font-size:10px;font-weight:800;text-transform:uppercase;color:#94a3b8;letter-spacing:.05em;margin:14px 0 6px">Missing Relationship Tables (Phase 2)</div>
      <div style="display:flex;flex-wrap:wrap;gap:5px">
        <span style="font-size:9px;font-weight:700;padding:2px 8px;border-radius:4px;background:#fee2e2;color:#991b1b">drug_targets</span>
        <span style="font-size:9px;font-weight:700;padding:2px 8px;border-radius:4px;background:#fee2e2;color:#991b1b">drug_indications</span>
        <span style="font-size:9px;font-weight:700;padding:2px 8px;border-radius:4px;background:#fee2e2;color:#991b1b">drug_routes</span>
        <span style="font-size:9px;font-weight:700;padding:2px 8px;border-radius:4px;background:#fef3c7;color:#92400e">therapeutic_areas</span>
        <span style="font-size:9px;font-weight:700;padding:2px 8px;border-radius:4px;background:#fef3c7;color:#92400e">ontology_mappings</span>
      </div>

    </div>`;
}

registerTab('ontology', {
  onEnter() { ontologyLoad(); loadOntologyHealth(); }
});
registerTab('program-board', {
  onEnter() { pbInit(); }
});

