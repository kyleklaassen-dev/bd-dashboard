// ── AUDIT TAB ─────────────────────────────────────────────────────────────────
let _auditLoaded = false;

// Load live counts from Supabase
async function auditCount(table, filter) {
  let q = _sb.from(table).select('*', { count: 'exact', head: true });
  if (filter) for (const [k, v] of Object.entries(filter)) {
    k.startsWith('!') ? q = q.neq(k.slice(1), v) : q = q.eq(k, v);
  }
  const { count } = await q;
  return count ?? 0;
}

// ── Schema Browser ────────────────────────────────────────────────────────────
let _schemaLoaded = false;

function _renderSchemaSection() {
  const mount = document.getElementById('s9-schema-mount');
  if (!mount) return;

  // Column type classifier
  const ct = col => {
    if (col === 'id') return 'pk';
    if (/_id$/.test(col)) return 'fk';
    if (/_at$|_date$/.test(col)) return 'ts';
    if (/_json$|_payload$|_breakdown$|_history$|_gaps$/.test(col)) return 'json';
    if (['disease_areas','biology_tags','typical_route','indications','cross_area_relevance',
         'missing_fields','missing_stages','trigger_flags','trigger_events','parties',
         'basis_tags','aliases','arms','alt_names','trial_names'].includes(col)) return 'arr';
    if (/^is_/.test(col) || ['cross_area','ailux_pair','resolved','verified','ailux_competes_directly','partnership_verified'].includes(col)) return 'bool';
    if (/score$|_count$|_usd_m$|^stock_|^market_cap$|^revenue$|^r_and_d|^sort_order$|^n_enrollment$|pct$|http_status$|failures$|significance$|importance$|area_fit$|affinity_kd$/.test(col)) return 'num';
    if (['overlap','cls','status','stage','type','confidence_level','confidence','entity_type',
         'catalyst_type','deal_type','intel_type','pair_type','target_type','company_type',
         'source_type','predicate','ailux_relevance','staleness_status','assigned_status',
         'catalog_category','ownership_status','drug_format','dosing_type','field_status',
         'test_type','generation_method','expected_operator','priority','last_pass_fail',
         'evidence_tier','completeness_tier','relationship_type','relationship_confidence',
         'discovery_status','trial_data_status','source_validation_status','catalyst_status',
         'partnership_type','identity_confidence','ownership_confidence_level'].includes(col)) return 'enum';
    return 'text';
  };

  const card = (tbl, desc, cols) => {
    const chips = cols.map(c=>`<span class="col-${ct(c)}">${c}</span>`).join('');
    return `<div class="au-schema-card">
      <div class="au-schema-thd">
        <span class="au-schema-tname">${tbl}</span>
        <span class="au-schema-cnt" id="sc-${tbl.replace(/_/g,'-')}">—</span>
      </div>
      <div class="au-schema-desc">${desc}</div>
      <div class="au-schema-cols">${chips}</div>
    </div>`;
  };

  const layerHd = (icon, color, label, n) =>
    `<div class="au-schema-lyr"><div class="au-schema-lyr-hd" style="color:${color}">${icon} ${label} <span style="font-weight:500;font-size:10px;opacity:.7">(${n} tables)</span></div>`;

  mount.innerHTML = `
  ${layerHd('🧬','#7c3aed','Layer 1 — Biology Ontology',5)}
    <div class="au-schema-grid">
      ${card('disease_areas','Therapeutic areas — top-level clinical specialties. 6 dashboard tab areas + 5 grouping filters.',['id','label','description','sort_order','indication_group'])}
      ${card('indications','Specific diseases mapped to a therapeutic area. Carries biology_tags metadata.',['id','name','abbreviation','disease_area','description','patient_note','regulatory_note','created_at','biology_tags'])}
      ${card('targets','Normalized biological targets. Gene symbol, family, pathway, cross-area relevance.',['id','label','full_name','gene_symbol','target_type','ailux_relevance','family','pathway','disease_areas','indications','cross_area','cross_area_relevance','alt_names','biology_note','mechanism_note','target_class','ailux_program','ailux_asset','approved_drug','notes','created_at','updated_at'])}
      ${card('target_pairs','Two targets combined in a therapeutic strategy (bispecific or combination).',['id','pair_symbol','pair_type','target_1_id','target_2_id','ailux_pair','first_drug','rationale','synergy_logic','disease_areas','created_at'])}
      ${card('modalities','Drug format technology — how the target is being drugged.',['id','name','abbreviation','typical_route','description','typical_dosing','examples','created_at'])}
    </div>
  </div>
  ${layerHd('🏢','#059669','Layer 2 — Entity Registry',4)}
    <div class="au-schema-grid">
      ${card('companies','~40 tracked companies. Source of truth for identity, financials, and BD context.',['id','name','ticker','exchange','status','company_type','overlap','geography','hq_city','hq_country','tagline','ailux_angle','insight_text','partner_co','acquired_by','market_cap','market_cap_display','stock_price','stock_change','revenue','r_and_d_spend','r_and_d_pct','ta_focus_1','ta_focus_2','display_co','group_id','last_enriched_at','last_verified','last_price_update','created_at','updated_at'])}
      ${card('drugs','100+ molecules. Primary enrichment output — mechanism, stage, classification, ownership.',['id','name','brand_name','display_name','canonical_drug_id','company_id','current_owner_company_id','originator_company_id','stage','cls','overlap','overlap_rationale','modality','target','mechanism','mechanism_detail','route','is_combo','is_combination','combination_label','drug_summary','vs_ailux','ailux_angle','ailux_competes_directly','confidence_level','data_source','catalog_category','entity_type','entity_id','entity_name','ownership_status','display_partner_name','partner_company','partnership_type','partnership_verified','licensor_name','licensor_code','strategic_role','differentiation_thesis','patient_population','final_endpoints','endpoints','trial_names','aliases','indication_short','phase_display','dosing_type','drug_format','dosing_schedule','half_life_note','color_hex','light_bg_hex','sort_order','completeness_score','completeness_tier','priority_score','confidence_score','identity_confidence','identity_method','discovery_status','trial_data_status','missing_fields','missing_stages','next_best_action','trigger_flags','approval_date','annual_revenue','expected_evidence_stage','last_enriched_model','last_enriched_by_run_id','enrichment_history','ownership_source_url','ownership_confidence_level','source_url','key_data','sources_json','last_synced_date','last_scored_at','last_verified','created_at','updated_at'])}
      ${card('company_areas','Junction table — which therapeutic areas each company participates in.',['company_id','area_id'])}
      ${card('trials','ClinicalTrials.gov data for tracked drugs. Phase, status, readout dates.',['id','drug_id','canonical_drug_id','combination_id','entity_id','trial_name','study_acronym','phase','status','indication','estimand','n_enrollment','arms','primary_endpoint','secondary_endpoints','primary_completion_date','readout_date','start_date','pcd_label','results_note','sponsor','area_fit','discovery_status','confidence_score','source_url','last_synced_date','created_at'])}
    </div>
  </div>
  ${layerHd('🧠','#d97706','Layer 3 — Intelligence Output',6)}
    <div class="au-schema-grid">
      ${card('ailux_positions','Classification anchor — the exact Direct/Adjacent/Same-Space/Watch definitions Claude reads before scoring.',['id','area_id','ailux_drug','ailux_targets','ailux_modality','ailux_stage','ailux_angle','direct_criteria','adjacent_criteria','same_space_criteria','watch_criteria','direct_examples','adjacent_examples','same_space_examples','watch_examples','notes','updated_at'])}
      ${card('drug_area_scores','Primary Claude output per drug per area. Overlap tier, rationale, positioning vs. Ailux.',['id','drug_id','canonical_drug_id','area_id','overlap','cls','overlap_rationale','vs_ailux_positioning','area_fit','area_fit_rationale','competitive_relevance','relevance_rationale','strategic_value_score','confidence_level','enriched_model','enriched_by_run_id','source_url','last_enriched_at','created_at'])}
      ${card('molecule_intelligence','Per-drug molecular characterization — format, epitope, safety, differentiation claim.',['id','drug_id','canonical_drug_id','modality','format','valency','igg_subclass','fc_engineering','epitope','affinity_kd','lowest_active_dose','lowest_active_dose_unit','safety_observations','differentiation_claim','field_status','confidence','enriched_by','source_url','last_enriched_at','created_at','updated_at'])}
      ${card('competitive_landscapes','Per-area landscape scoring — how complete and competitive each area is.',['id','area_id','target_pair','disease_name','mechanism_count','drug_count','failed_mechanism_count','expected_drug_count','expected_relationship_count','expected_catalyst_count','drug_coverage_score','relationship_coverage_score','catalyst_coverage_score','source_validation_score','staleness_penalty','landscape_completeness_score','landscape_dependency_score','coverage_breakdown','staleness_status','notes','coverage_computed_at','last_enriched_at','created_at'])}
      ${card('entity_edges','Relationship graph — competes_with, licensed_from, acquired, partnered_with edges.',['id','subject_type','subject_id','predicate','object_type','object_id','scope_area_id','scope_indication','confidence_level','generation_method','rationale','status','staleness_status','basis_tags','basis_text','notes','source_url','created_by','created_at','updated_at'])}
      ${card('validation_tests','QA assertions — "drug X should be Direct in area Y." Pass/fail tracking.',['id','test_name','test_type','area_id','entity_type','entity_id','field_name','expected_value','expected_operator','priority','last_pass_fail','last_actual_value','consecutive_failures','last_failure_at','last_checked_at','source','notes','created_at','updated_at'])}
    </div>
  </div>
  ${layerHd('📡','#e11d48','Layer 4 — Signals & Events',4)}
    <div class="au-schema-grid">
      ${card('catalysts','Upcoming BD-relevant events — PDUFA dates, conference readouts, data presentations.',['id','label','catalyst_type','catalyst_status','catalyst_date','sort_date','company_id','drug_id','canonical_drug_id','area_id','related_trial_id','significance','expected_impact','is_key_watch','resolved','resolved_note','outcome_text','confidence_level','confidence_score','confidence_source','staleness_status','notes','source_url','created_at'])}
      ${card('deals','BD transactions — M&A, licenses, collaborations, options.',['id','deal_date','deal_date_label','deal_type','from_company','to_company','company_id','drug_id','canonical_drug_id','entity_id','area_id','upfront_usd_m','total_usd_m','headline','detail','parties','geography_rights','economics_royalties','strategic_signal','ailux_signal','ailux_relevance','source_url','created_at'])}
      ${card('intel','Curated intelligence items — clinical data, market events, regulatory news.',['id','headline','body','intel_type','intel_date','source_name','source_url','primary_company_id','verified','importance','created_at'])}
      ${card('submitted_intel','User-submitted intelligence items. Screened by enrichment pipeline before promotion.',['id','submitted_by','submitted_text','status','source_url','source_name','source_type','source_validation_status','source_http_status','extracted_title','extracted_summary','extracted_key_facts_json','extracted_entities_json','proposed_actions_json','raw_payload_json','confidence_level','review_notes','reviewer','reviewed_at','imported_at','analyzed_at','created_at'])}
    </div>
  </div>
  ${layerHd('⚙️','#475569','Layer 5 — Pipeline & Queues',2)}
    <div class="au-schema-grid">
      ${card('research_queue','Enrichment backlog — companies and drugs that need to be enriched or re-enriched.',['id','entity_id','entity_name','company_id','area_id','priority_score','reason','next_best_action','missing_stage','missing_fields','strategic_importance','completeness_score','completeness_tier','staleness_score','trigger_events','assigned_status','last_updated','last_action_at','created_at'])}
      ${card('discovery_queue','Drug intake proposals awaiting human review before promotion to drugs + drug_area_scores.',['id','drug_name','company_name','company_id_suggested','target','stage','modality','route','entity_type','partner_co','acquired_by','area_id','overlap','competition_layer','relevance_score','relevance_rationale','confidence_score','strategic_priority_score','strategic_value_score','evidence_tier','coverage_score','completeness_gaps','relationship_type','relationship_confidence','why_discovered','reason','status','source','source_url','suggested_dest','change_log','promotion_payload','review_notes','reviewer','reviewed_at','discovered_by','discovered_at','created_company_id','created_drug_id','discovery_run_id','last_updated_at'])}
    </div>
  </div>`;

  _loadSchemaCounts();
}

async function _loadSchemaCounts() {
  const tables = [
    'disease_areas','indications','targets','target_pairs','modalities',
    'companies','drugs','company_areas','trials',
    'ailux_positions','drug_area_scores','molecule_intelligence','competitive_landscapes','entity_edges','validation_tests',
    'catalysts','deals','intel','submitted_intel',
    'research_queue','discovery_queue'
  ];
  await Promise.all(tables.map(async t => {
    try {
      const { count } = await _sb.from(t).select('*', { count:'exact', head:true });
      const el = document.getElementById('sc-' + t.replace(/_/g,'-'));
      if (el) el.textContent = (count ?? 0).toLocaleString();
    } catch(e) {
      const el = document.getElementById('sc-' + t.replace(/_/g,'-'));
      if (el) el.textContent = '—';
    }
  }));
  _schemaLoaded = true;
}

// ── Ontology Explorer ────────────────────────────────────────────────────────
let _ontLoaded = false;

async function _loadOntologyExplorer(force = false) {
  if (_ontLoaded && !force) return;
  const el = document.getElementById('ont-explorer');
  if (!el) return;
  el.innerHTML = '<div style="padding:36px;text-align:center;color:#94a3b8;font-size:12px;font-style:italic">Loading live data…</div>';

  try {
    const [r1,r2,r3,r4,r5] = await Promise.all([
      Promise.resolve({ data: [] }),  /* disease_areas — retired from code reads (Session 80); table DB teardown complete Session 84 */
      _sb.from('indications').select('id,name,abbreviation,disease_area,biology_tags').order('disease_area,id'),
      _sb.from('targets').select('id,label,gene_symbol,target_type,family,pathway,ailux_relevance,disease_areas,cross_area_relevance').order('id'),
      _sb.from('target_pairs').select('id,pair_symbol,pair_type,ailux_pair,disease_areas,first_drug').order('id'),
      _sb.from('modalities').select('id,name,abbreviation,typical_route,examples').order('name')
    ]);
    const areas    = r1.data || [];
    const inds     = r2.data || [];
    const tgtsAll  = r3.data || [];
    const tgts     = tgtsAll.filter(t => t.gene_symbol);
    const pairs    = r4.data || [];
    const mods     = r5.data || [];

    // helpers
    const rBadge = v => { const cfg={primary:['#b91c1c','#fff5f5'],combination:['#7c3aed','#f5f3ff'],adjacent:['#0369a1','#e0f2fe'],benchmark:['#d97706','#fffbeb'],watch:['#475569','#f1f5f9'],monitor:['#94a3b8','#f8fafc']}; const [c,bg]=cfg[v]||['#475569','#f8fafc']; return `<span style="font-size:9px;font-weight:700;color:${c};background:${bg};border:1px solid ${c}25;border-radius:3px;padding:1px 5px;white-space:nowrap">${v}</span>`; };
    const chip = (t,c,bg) => `<span style="font-size:9px;font-weight:600;color:${c};background:${bg};border-radius:3px;padding:1px 5px;white-space:nowrap">${t}</span>`;

    // ── Panel: disease_areas ──
    const tabA = areas.filter(a=>a.sort_order<=6), grpA = areas.filter(a=>a.sort_order>6);
    const pDA = `<div style="display:flex;flex-direction:column;height:100%">
      <div style="background:#7c3aed;padding:9px 13px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0">
        <div><div style="font-size:11px;font-weight:800;color:white">Therapeutic Areas</div><div style="font-size:9px;color:rgba(255,255,255,.65);font-family:monospace;margin-top:1px">disease_areas</div></div>
        <span style="font-size:10px;background:rgba(255,255,255,.25);color:white;border-radius:10px;padding:1px 8px;font-weight:700">${areas.length}</span>
      </div>
      <div style="flex:1;overflow-y:auto;padding:11px 12px;font-size:11px">
        <div style="font-size:9px;font-weight:800;color:#7c3aed;text-transform:uppercase;letter-spacing:.07em;margin-bottom:7px;padding-bottom:3px;border-bottom:1px solid #ede9fe">Tab Areas — 6 dashboard tabs</div>
        ${tabA.map(a=>`<div style="margin-bottom:9px">
          <div style="display:flex;align-items:center;gap:4px;flex-wrap:wrap">
            <span style="font-size:9px;font-family:monospace;background:#ede9fe;color:#5b21b6;border-radius:3px;padding:1px 5px;font-weight:700">${a.id}</span>
            <span style="font-weight:700;color:#3b0764;font-size:10px">${a.label}</span>
          </div>
          <div style="color:#6d28d9;font-size:9px;margin-top:2px;line-height:1.4">${(a.description||'').slice(0,62)}…</div>
        </div>`).join('')}
        <div style="font-size:9px;font-weight:800;color:#a78bfa;text-transform:uppercase;letter-spacing:.07em;margin:10px 0 7px;padding-top:7px;border-top:1px solid #ede9fe">Grouping Areas — drug-display filters</div>
        ${grpA.map(a=>`<div style="margin-bottom:6px;display:flex;align-items:center;gap:4px;flex-wrap:wrap">
          <span style="font-size:9px;font-family:monospace;background:#f3f0ff;color:#7c3aed;border-radius:3px;padding:1px 5px;font-weight:700">${a.id}</span>
          <span style="font-weight:600;color:#5b21b6;font-size:10px">${a.label}</span>
        </div>`).join('')}
      </div>
    </div>`;

    // ── Panel: indications ──
    const indByA = {}; inds.forEach(i=>{if(!indByA[i.disease_area])indByA[i.disease_area]=[];indByA[i.disease_area].push(i);});
    const aHdr = {ibd:'#1d4ed8',respiratory:'#0369a1',atopy:'#d97706',ted:'#9333ea',autoimmune:'#059669',oncology:'#dc2626'};
    const pIND = `<div style="display:flex;flex-direction:column;height:100%">
      <div style="background:#3b82f6;padding:9px 13px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0">
        <span style="font-size:11px;font-weight:800;color:white;font-family:monospace">indications</span>
        <span style="font-size:10px;background:rgba(255,255,255,.25);color:white;border-radius:10px;padding:1px 8px;font-weight:700">${inds.length}</span>
      </div>
      <div style="flex:1;overflow-y:auto;padding:11px 12px;font-size:11px">
        ${Object.entries(indByA).map(([area,items])=>`<div style="margin-bottom:11px">
          <div style="font-size:9px;font-weight:800;color:${aHdr[area]||'#475569'};text-transform:uppercase;letter-spacing:.07em;margin-bottom:6px;padding-bottom:3px;border-bottom:1px solid #dbeafe">${area}</div>
          ${items.map(i=>`<div style="margin-bottom:8px;padding-left:8px;border-left:2px solid #bfdbfe">
            <div style="display:flex;align-items:center;gap:4px;flex-wrap:wrap">
              <span style="font-size:9px;font-weight:800;background:#1d4ed8;color:white;border-radius:3px;padding:1px 6px;min-width:22px;text-align:center">${i.abbreviation}</span>
              <span style="font-weight:700;color:#1e3a8a;font-size:10px">${i.name}</span>
            </div>
            <div style="margin-top:4px;display:flex;flex-wrap:wrap;gap:2px">${(i.biology_tags||[]).map(t=>chip(t,'#475569','#f1f5f9')).join('')}</div>
          </div>`).join('')}
        </div>`).join('')}
      </div>
    </div>`;

    // ── Panel: targets ──
    const relOrd = {primary:0,combination:1,adjacent:2,benchmark:3,watch:4,monitor:5};
    const sT = [...tgts].sort((a,b)=>(relOrd[a.ailux_relevance]??9)-(relOrd[b.ailux_relevance]??9));
    const borderC = r => ({primary:'#dc2626',combination:'#7c3aed',adjacent:'#0369a1',benchmark:'#d97706'}[r]||'#86efac');
    const pTGT = `<div style="display:flex;flex-direction:column;height:100%">
      <div style="background:#16a34a;padding:9px 13px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0">
        <span style="font-size:11px;font-weight:800;color:white;font-family:monospace">targets</span>
        <span style="font-size:10px;background:rgba(255,255,255,.25);color:white;border-radius:10px;padding:1px 8px;font-weight:700">${tgts.length} enriched</span>
      </div>
      <div style="flex:1;overflow-y:auto;padding:11px 12px;font-size:11px">
        <div style="font-size:9px;font-weight:700;color:#94a3b8;margin-bottom:7px;padding-bottom:3px;border-bottom:1px solid #dcfce7">Sorted by ailux_relevance</div>
        ${sT.map(t=>`<div style="margin-bottom:10px;padding-left:8px;border-left:2.5px solid ${borderC(t.ailux_relevance)}">
          <div style="display:flex;align-items:center;gap:4px;flex-wrap:wrap">
            <span style="font-size:9px;font-family:monospace;font-weight:800;background:#f0fdf4;border:1px solid #86efac;color:#166534;border-radius:3px;padding:1px 5px">${t.gene_symbol}</span>
            <span style="font-weight:700;color:#14532d;font-size:10px">${t.label}</span>
            ${rBadge(t.ailux_relevance||'watch')}
          </div>
          <div style="color:#475569;margin-top:2px;font-size:9px">${[t.target_type,t.family].filter(Boolean).join(' · ')}</div>
          ${t.pathway?`<div style="color:#94a3b8;font-size:9px;margin-top:1px">${t.pathway}</div>`:''}
          <div style="margin-top:3px;display:flex;flex-wrap:wrap;gap:2px">
            ${(t.disease_areas||[]).map(d=>chip(d,'#166534','#f0fdf4')).join('')}
            ${(t.cross_area_relevance||[]).map(d=>chip(d,'#0369a1','#eff6ff')).join('')}
          </div>
        </div>`).join('')}
        <div style="font-size:9px;color:#94a3b8;margin-top:4px;font-style:italic;padding-top:6px;border-top:1px solid #f0fdf4">+ ${tgtsAll.length - tgts.length} combination/pair targets also in table</div>
      </div>
    </div>`;

    // ── Panel: target_pairs ──
    const pTP = `<div style="border:1.5px solid #0891b2;border-radius:8px;overflow:hidden;margin-bottom:8px">
      <div style="background:#0891b2;padding:8px 12px;display:flex;align-items:center;justify-content:space-between">
        <span style="font-size:11px;font-weight:800;color:white;font-family:monospace">target_pairs</span>
        <span style="font-size:10px;background:rgba(255,255,255,.25);color:white;border-radius:10px;padding:1px 7px;font-weight:700">${pairs.length}</span>
      </div>
      <div style="padding:10px 12px;font-size:11px;background:white">
        ${pairs.map(p=>`<div style="margin-bottom:9px;padding-left:8px;border-left:2.5px solid ${p.ailux_pair?'#f59e0b':'#a5f3fc'}">
          <div style="display:flex;align-items:center;gap:4px;flex-wrap:wrap">
            ${p.ailux_pair?`<span style="color:#d97706;font-size:11px">★</span>`:''}
            <span style="font-weight:700;color:#164e63;font-size:10px">${p.pair_symbol}</span>
          </div>
          <div style="color:#475569;font-size:9px;margin-top:1px">${(p.pair_type||'').replace(/_/g,' ')}</div>
          <div style="margin-top:3px;display:flex;flex-wrap:wrap;gap:2px">${(p.disease_areas||[]).map(d=>chip(d,'#0e7490','#ecfeff')).join('')}</div>
          ${p.first_drug?`<div style="color:#94a3b8;font-size:9px;margin-top:2px;font-style:italic">${p.first_drug.slice(0,42)}${p.first_drug.length>42?'…':''}</div>`:''}
        </div>`).join('')}
      </div>
    </div>`;

    // ── Panel: modalities ──
    const pMOD = `<div style="border:1.5px solid #059669;border-radius:8px;overflow:hidden">
      <div style="background:#059669;padding:8px 12px;display:flex;align-items:center;justify-content:space-between">
        <span style="font-size:11px;font-weight:800;color:white;font-family:monospace">modalities</span>
        <span style="font-size:10px;background:rgba(255,255,255,.25);color:white;border-radius:10px;padding:1px 7px;font-weight:700">${mods.length}</span>
      </div>
      <div style="padding:10px 12px;font-size:11px;background:white">
        ${mods.map(m=>`<div style="margin-bottom:7px;padding-left:8px;border-left:2px solid #d1fae5">
          <div style="display:flex;align-items:center;gap:4px;flex-wrap:wrap">
            <span style="font-size:9px;font-family:monospace;font-weight:800;background:#d1fae5;color:#065f46;border-radius:3px;padding:1px 5px">${m.abbreviation}</span>
            <span style="font-weight:700;color:#14532d;font-size:10px">${m.name}</span>
            ${(m.typical_route||[]).map(r=>chip(r,'#1d4ed8','#dbeafe')).join('')}
          </div>
          ${m.examples?`<div style="color:#94a3b8;font-size:9px;margin-top:2px;line-height:1.4">${m.examples.slice(0,55)}${m.examples.length>55?'…':''}</div>`:''}
        </div>`).join('')}
      </div>
    </div>`;

    // ── Assemble layout ──
    el.innerHTML = `
      <div style="display:flex;gap:0;align-items:stretch;padding:14px 14px 0;overflow-x:auto;min-height:380px">
        <div style="flex:1.1;min-width:190px;background:white;border:1.5px solid #7c3aed;border-radius:8px;overflow:hidden;display:flex;flex-direction:column;max-height:490px">${pDA}</div>
        <div style="flex-shrink:0;display:flex;align-items:center;padding:0 7px;padding-top:0;font-size:22px;color:#7c3aed;opacity:.7;align-self:center;margin-top:-20px">→</div>
        <div style="flex:1.2;min-width:200px;background:white;border:1.5px solid #3b82f6;border-radius:8px;overflow:hidden;display:flex;flex-direction:column;max-height:490px">${pIND}</div>
        <div style="flex-shrink:0;display:flex;align-items:center;padding:0 7px;font-size:22px;color:#3b82f6;opacity:.7;align-self:center;margin-top:-20px">→</div>
        <div style="flex:1.4;min-width:220px;background:white;border:1.5px solid #16a34a;border-radius:8px;overflow:hidden;display:flex;flex-direction:column;max-height:490px">${pTGT}</div>
        <div style="flex-shrink:0;display:flex;align-items:center;padding:0 7px;font-size:22px;color:#16a34a;opacity:.7;align-self:center;margin-top:-20px">→</div>
        <div style="flex:1.1;min-width:195px;display:flex;flex-direction:column;gap:0;max-height:490px;overflow-y:auto">${pTP}${pMOD}</div>
      </div>
      <div style="padding:9px 14px 10px;background:#f8fafc;border-top:1px solid #e2e8f0;font-size:10px;color:#64748b;line-height:1.9;margin-top:12px">
        <span style="font-weight:700;color:#7c3aed">Biology chain:</span> disease_areas.id → indications.disease_area → targets.disease_areas[] → target_pairs.target_1/2_id &nbsp;·&nbsp;
        <span style="font-weight:700;color:#059669">Drug bridge:</span> drugs.target → targets.id · drugs.modality → modalities.id &nbsp;·&nbsp;
        <span style="font-weight:700;color:#0369a1">Score chain:</span> drug_area_scores.(area_id → disease_areas.id) · (drug_id → drugs.id)
      </div>`;

    _ontLoaded = true;
  } catch(e) {
    if (el) el.innerHTML = `<div style="padding:24px;color:#ef4444;font-size:12px">Error loading ontology: ${e.message}</div>`;
  }
}

async function auditLoad(force = false) {
  if (_auditLoaded && !force) return;
  const jobs = [
    { id:'au-n-co', table:'companies',       filter:{'!status':'acquired'} },
    { id:'au-n-dr', table:'drugs',            filter:null },
    { id:'au-n-tr', table:'trials',           filter:null },
    { id:'au-n-ca', table:'catalysts',        filter:null },
    { id:'au-n-de', table:'deals',            filter:null },
    { id:'au-n-in', table:'intel',            filter:null },
    { id:'au-n-dq', table:'discovery_queue',  filter:{status:'pending'} },
  ];
  await Promise.all(jobs.map(async j => {
    try { const n = await auditCount(j.table, j.filter); const el = document.getElementById(j.id); if (el) el.textContent = n.toLocaleString(); }
    catch(e) { const el = document.getElementById(j.id); if (el) el.textContent = '—'; }
  }));
  try {
    const [tot, nw] = await Promise.all([auditCount('submitted_intel',null), auditCount('submitted_intel',{status:'new'})]);
    const el = document.getElementById('au-n-si'); if (el) el.textContent = tot;
    // Show new badge in stat label
    const lbl = el?.parentElement?.querySelector('.au-stat-l');
    if (lbl && nw > 0) lbl.textContent = `Submitted · ${nw} new`;
  } catch(e) {}
  _auditLoaded = true;
  const ts = document.getElementById('au-ts');
  if (ts) ts.textContent = 'Loaded ' + new Date().toLocaleTimeString();
  // Restore all saved annotations
  auRestoreAll();
  auRestoreEdits();
  // Load live ontology explorer
  _loadOntologyExplorer(force);
  if (_schemaLoaded) _loadSchemaCounts();
}

// Section toggle
function auToggle(id) {
  const body = document.getElementById(id+'-body');
  const tog  = document.getElementById(id+'-tog');
  if (!body) return;
  const isCollapsed = body.style.display === 'none' || body.classList.contains('collapsed');
  if (isCollapsed) {
    body.style.display = ''; body.classList.remove('collapsed');
    if (tog) tog.textContent = '▾';
    if (id === 's9' && !_schemaLoaded) _renderSchemaSection();
  } else {
    body.style.display = 'none';
    if (tog) tog.textContent = '▸';
  }
}

// Annotation persistence (localStorage)
const AU_PREFIX = 'meridian_audit_';
function auSave(id) {
  const el = document.getElementById(id);
  if (!el) return;
  localStorage.setItem(AU_PREFIX + id, el.value);
  const saved = document.getElementById(id + '-saved');
  if (saved) { saved.textContent = 'saved'; setTimeout(() => { if(saved) saved.textContent = ''; }, 1500); }
}
function auRestoreAll() {
  ['anno-s0','anno-s1','anno-s2','anno-s3','anno-s4','anno-s5','anno-s6','anno-s7','anno-s8','anno-s9',
   'anno-anchor','anno-direct','anno-adjacent','anno-samespace','anno-watch','anno-fields'].forEach(id => {
    const val = localStorage.getItem(AU_PREFIX + id);
    const el  = document.getElementById(id);
    if (el && val) el.value = val;
  });
}

// ── Inline edit mode ──────────────────────────────────────────────────────────
const AU_EDIT_PREFIX = 'meridian_edit_';
const AU_ORIG_PREFIX = 'meridian_orig_';
let _auEditMode = false;

function auRestoreEdits() {
  const els = document.querySelectorAll('#tab-audit .au-editable');
  els.forEach((el, i) => {
    if (!el.dataset.auKey) el.dataset.auKey = 'e' + i;
    const key = el.dataset.auKey;
    if (!localStorage.getItem(AU_ORIG_PREFIX + key)) {
      localStorage.setItem(AU_ORIG_PREFIX + key, el.textContent.trim().slice(0, 500));
    }
    const saved = localStorage.getItem(AU_EDIT_PREFIX + key);
    if (saved) {
      el.textContent = saved;
      el.classList.add('au-user-edit');
    }
  });
}

function auToggleEditMode() {
  _auEditMode = !_auEditMode;
  const btn = document.getElementById('au-edit-btn');
  const wrap = document.querySelector('#tab-audit .au-wrap');
  const copyBtn = document.getElementById('au-copy-btn');
  const els = document.querySelectorAll('#tab-audit .au-editable');
  if (_auEditMode) {
    btn.textContent = '✓ Done editing';
    btn.classList.add('active');
    wrap && wrap.classList.add('au-edit-active');
    copyBtn && (copyBtn.style.display = 'inline-block');
    els.forEach((el, i) => {
      if (!el.dataset.auKey) el.dataset.auKey = 'e' + i;
      el.contentEditable = 'true';
      el.addEventListener('input', function() { auHandleEdit(this); }, {once: false});
    });
  } else {
    btn.textContent = '✏️ Edit text';
    btn.classList.remove('active');
    wrap && wrap.classList.remove('au-edit-active');
    els.forEach(el => { el.contentEditable = 'false'; });
  }
}

function auHandleEdit(el) {
  const key = el.dataset.auKey;
  if (!key) return;
  localStorage.setItem(AU_EDIT_PREFIX + key, el.textContent.trim());
  el.classList.add('au-user-edit');
  const section = el.closest('.au-section');
  if (section) {
    const title = section.querySelector('.au-sec-title');
    if (title && !title.querySelector('.au-edit-indicator')) {
      const dot = document.createElement('span');
      dot.className = 'au-edit-indicator';
      dot.title = 'This section has your edits';
      dot.textContent = ' ✎';
      title.appendChild(dot);
    }
  }
}

function auCollectEdits() {
  const els = document.querySelectorAll('#tab-audit [data-au-key]');
  const edits = [];
  els.forEach(el => {
    const key = el.dataset.auKey;
    const original = localStorage.getItem(AU_ORIG_PREFIX + key) || '';
    const current  = el.textContent.trim();
    if (original && current !== original) {
      const section = el.closest('.au-section');
      const sectionTitle = section?.querySelector('.au-sec-title')?.textContent?.replace(' ✎','')?.trim() || 'Unknown';
      edits.push({ section: sectionTitle, key, original: original.slice(0,200), current: current.slice(0,500) });
    }
  });
  if (!edits.length) {
    alert('No inline edits found yet. Click "Edit text", change some text, then click "Done editing" before copying.');
    return;
  }
  let msg = '=== MY AUDIT PAGE EDITS — ' + new Date().toLocaleDateString() + ' ===\n\n';
  msg += 'These are changes I made directly in the audit page.\n';
  msg += 'Each edit shows the section, the original text, and what I changed it to.\n\n';
  edits.forEach((e, i) => {
    msg += 'EDIT ' + (i+1) + '\n';
    msg += 'Section: "' + e.section + '"\n';
    msg += 'Key: ' + e.key + '\n';
    msg += 'Original: "' + e.original + '..."\n';
    msg += 'Changed to: "' + e.current + '"\n\n';
  });
  msg += '=== END ===\nPlease apply these changes to the corresponding source text.';
  navigator.clipboard.writeText(msg).then(() => {
    const btn = document.getElementById('au-copy-btn');
    const orig = btn.textContent;
    btn.textContent = '✓ Copied!';
    btn.style.background = '#dcfce7';
    btn.style.borderColor = '#86efac';
    setTimeout(() => { btn.textContent = orig; btn.style.background = ''; btn.style.borderColor = ''; }, 2500);
  }).catch(() => {
    const ta = document.createElement('textarea');
    ta.value = msg;
    ta.style.cssText = 'position:fixed;top:10%;left:10%;width:80%;height:70%;z-index:9999;font-size:11px;padding:12px;border:2px solid #f59e0b;border-radius:8px;font-family:monospace';
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.4);z-index:9998';
    const close = document.createElement('button');
    close.textContent = 'Close (select all + copy first)';
    close.style.cssText = 'position:fixed;bottom:12%;left:50%;transform:translateX(-50%);z-index:10000;padding:10px 20px;background:#0f172a;color:white;border:none;border-radius:7px;cursor:pointer;font-size:13px;font-weight:700';
    close.onclick = () => { document.body.removeChild(ta); document.body.removeChild(overlay); document.body.removeChild(close); };
    document.body.appendChild(overlay);
    document.body.appendChild(ta);
    document.body.appendChild(close);
    ta.select();
  });
}

function escHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}


function switchOntSubTab(which) {
  var audit = document.getElementById('ont-wrap');
  var explorer = document.getElementById('ont-explorer-panel');
  var btnAudit = document.getElementById('ont-subbtn-audit');
  var btnExplorer = document.getElementById('ont-subbtn-explorer');
  if (!audit || !explorer) return;
  if (which === 'explorer') {
    audit.style.display = 'none';
    explorer.style.display = 'flex';
    if (btnAudit) { btnAudit.style.borderBottomColor = 'transparent'; btnAudit.style.color = '#6b8aad'; btnAudit.style.fontWeight = '500'; }
    if (btnExplorer) { btnExplorer.style.borderBottomColor = '#4a90c4'; btnExplorer.style.color = '#f0f6ff'; btnExplorer.style.fontWeight = '700'; }
    if (!window.OEX_INITIALIZED) { window.OEX_INITIALIZED = true; setTimeout(oexRender, 80); }
    else { setTimeout(function(){ var cv=document.getElementById('oex-cpm-canvas'); if(cv&&cv.width<=300) oexRender(); }, 80); }
  } else {
    audit.style.display = '';
    explorer.style.display = 'none';
    if (btnAudit) { btnAudit.style.borderBottomColor = '#4a90c4'; btnAudit.style.color = '#f0f6ff'; btnAudit.style.fontWeight = '700'; }
    if (btnExplorer) { btnExplorer.style.borderBottomColor = 'transparent'; btnExplorer.style.color = '#6b8aad'; btnExplorer.style.fontWeight = '500'; }
  }
}

// ═══════════════════════════════════════════════════════
// KNOWLEDGE FOLDERS — Meridian v2
// ═══════════════════════════════════════════════════════
var _kfCurrentSlug = null;
var _kfKnowledge = null;
var _kfPerspectives = [];
var _kfCurrentTab = 'overview';
var _kfCurrentPerspRole = 'CEO';

async function openKnowledgeFolder(slug) {
  _kfCurrentSlug = slug;
  _kfCurrentTab = 'overview';
  _kfCurrentPerspRole = 'CEO';

  // Show panel immediately
  document.getElementById('kf-panel-overlay').classList.add('open');
  document.getElementById('kf-panel-body').innerHTML = '<div class="kf-loading">Loading intelligence briefing…</div>';

  // Mark active chip
  document.querySelectorAll('.kf-chip').forEach(function(c) {
    c.classList.toggle('active', c.getAttribute('onclick').includes("'" + slug + "'"));
  });

  try {
    var knowProm = _sb.from('area_knowledge').select('*').eq('area_slug', slug).single();
    var perspProm = _sb.from('area_perspectives').select('*').eq('area_slug', slug).order('perspective_role');

    var knowRes = await knowProm;
    var perspRes = await perspProm;

    _kfKnowledge = knowRes.data;
    _kfPerspectives = perspRes.data || [];

    if (_kfKnowledge) {
      document.getElementById('kf-icon').textContent = _kfKnowledge.icon || '🔬';
      document.getElementById('kf-name').textContent = _kfKnowledge.area_name;
      document.getElementById('kf-tagline').textContent = _kfKnowledge.tagline || '';
    }

    // Reset tabs UI
    document.querySelectorAll('.kf-tab').forEach(function(t, i) { t.classList.toggle('active', i === 0); });
    kfRenderTab('overview');

  } catch(e) {
    console.error('KF load error', e);
    document.getElementById('kf-panel-body').innerHTML =
      '<div class="kf-loading">⚠️ Could not load intelligence briefing. Try refreshing.</div>';
  }
}

function closeKnowledgeFolder() {
  document.getElementById('kf-panel-overlay').classList.remove('open');
  document.querySelectorAll('.kf-chip').forEach(function(c) { c.classList.remove('active'); });
  _kfCurrentSlug = null;
}

function kfSwitchTab(el, tab) {
  document.querySelectorAll('.kf-tab').forEach(function(t) { t.classList.remove('active'); });
  el.classList.add('active');
  _kfCurrentTab = tab;
  kfRenderTab(tab);
}

function kfRenderTab(tab) {
  var body = document.getElementById('kf-panel-body');
  var k = _kfKnowledge;

  if (!k) {
    body.innerHTML = '<div class="kf-loading">No data available for this area yet.</div>';
    return;
  }

  if (tab === 'overview') {
    body.innerHTML =
      '<div class="kf-section">' +
        '<div class="kf-stat-row">' +
          '<div class="kf-stat"><div class="kf-stat-num">' + (k.drug_count_total || '—') + '</div><div class="kf-stat-lbl">Programs tracked</div></div>' +
          '<div class="kf-stat"><div class="kf-stat-num">' + (k.drug_count_direct || '—') + '</div><div class="kf-stat-lbl">Direct competitors</div></div>' +
          '<div class="kf-stat"><div class="kf-stat-num">' + (k.area_type ? k.area_type.charAt(0).toUpperCase() + k.area_type.slice(1) : 'Area') + '</div><div class="kf-stat-lbl">Area type</div></div>' +
        '</div>' +
      '</div>' +
      (k.description ? '<div class="kf-section"><div class="kf-section-title">About this area</div><div class="kf-text">' + escHtml(k.description) + '</div></div>' : '') +
      (k.patient_population ? '<div class="kf-section"><div class="kf-section-title">Patient population</div><div class="kf-text">' + escHtml(k.patient_population) + '</div></div>' : '') +
      (k.unmet_need ? '<div class="kf-section"><div class="kf-section-title">Unmet need</div><div class="kf-text">' + escHtml(k.unmet_need) + '</div></div>' : '') +
      (k.standard_of_care ? '<div class="kf-section"><div class="kf-section-title">Current standard of care</div><div class="kf-text">' + escHtml(k.standard_of_care) + '</div></div>' : '') +
      (k.key_mechanism ? '<div class="kf-section"><div class="kf-section-title">Mechanism of action</div><div class="kf-text">' + escHtml(k.key_mechanism) + '</div></div>' : '');

  } else if (tab === 'ailux') {
    body.innerHTML =
      '<div class="kf-section">' +
        '<div class="kf-section-title">Ailux\'s position</div>' +
        '<div class="kf-text">' + escHtml(k.ailux_relevance || 'Ailux monitors this area closely as part of its competitive intelligence program.') + '</div>' +
      '</div>' +
      '<div class="kf-section">' +
        '<div class="kf-section-title">Key programs</div>' +
        '<div class="kf-text" style="background:#f0fdf4;border-radius:8px;padding:12px;border-left:4px solid #16a34a;">' +
          '<strong>ALX001</strong> — TL1A×IL-23p19 bispecific · Lead program · IND filed Q2 2026 · FIH target Q4 2027<br>' +
          '<strong>ALX002 / ALX005</strong> — Next-generation programs · Preclinical' +
        '</div>' +
      '</div>' +
      '<div class="kf-section" id="kf-ailux-bd-section">' +
        '<div class="kf-section-title">BD Strategy Context</div>' +
        '<div id="kf-ailux-bd-rows" style="color:#94a3b8;font-size:12px">Loading…</div>' +
      '</div>';
    _loadKfAiluxBdContext();

  } else if (tab === 'perspectives') {
    var roles = ['CEO', 'CSO', 'CBO', 'CFO', 'KOL'];
    var roleIcons = {CEO: '👔', CSO: '🔬', CBO: '🤝', CFO: '💰', KOL: '🏥'};

    var perspTabsHtml = roles.map(function(r) {
      return '<div class="kf-persp-tab' + (r === _kfCurrentPerspRole ? ' active' : '') +
             '" onclick="kfSwitchPersp(\'' + r + '\',this)">' + (roleIcons[r] || '') + ' ' + r + '</div>';
    }).join('');

    body.innerHTML =
      '<div class="kf-section">' +
        '<div class="kf-section-title">View through the lens of…</div>' +
        '<div class="kf-persp-tabs" id="kf-persp-tabs">' + perspTabsHtml + '</div>' +
        '<div id="kf-persp-content">' + _kfBuildPerspContent(_kfCurrentPerspRole) + '</div>' +
      '</div>';

  } else if (tab === 'bd') {
    body.innerHTML = '<div class="kf-loading">Loading BD intelligence…</div>';
    _loadKfBdData();

  } else if (tab === 'landscape') {
    body.innerHTML = '<div class="kf-loading">Landscape view coming soon — tracks competitive programs by stage.</div>';

  } else {
    body.innerHTML = '<div class="kf-loading">Loading…</div>';
  }
}

function _kfBuildPerspContent(role) {
  var persp = null;
  for (var i = 0; i < _kfPerspectives.length; i++) {
    if (_kfPerspectives[i].perspective_role === role) { persp = _kfPerspectives[i]; break; }
  }
  if (!persp) {
    return '<div class="kf-loading">No ' + role + ' perspective available for this area yet.</div>';
  }
  var pts = [];
  if (Array.isArray(persp.key_points)) pts = persp.key_points;
  else if (typeof persp.key_points === 'string') { try { pts = JSON.parse(persp.key_points); } catch(e) {} }

  return '<div class="kf-persp-content">' +
    '<div class="kf-persp-role">' + escHtml(persp.role_title || role) + ' perspective</div>' +
    '<div class="kf-persp-narrative">' + escHtml(persp.narrative) + '</div>' +
    (pts.length ? '<ul class="kf-persp-points">' + pts.map(function(p) { return '<li>' + escHtml(p) + '</li>'; }).join('') + '</ul>' : '') +
    (persp.strategic_question ? '<div class="kf-persp-sq">❓ Key question: <em>' + escHtml(persp.strategic_question) + '</em></div>' : '') +
    (persp.bottom_line ? '<div class="kf-bottom-line">🎯 Bottom line: ' + escHtml(persp.bottom_line) + '</div>' : '') +
    '</div>';
}

function kfSwitchPersp(role, el) {
  _kfCurrentPerspRole = role;
  document.querySelectorAll('.kf-persp-tab').forEach(function(t) { t.classList.remove('active'); });
  el.classList.add('active');
  document.getElementById('kf-persp-content').innerHTML = _kfBuildPerspContent(role);
}

async function _loadKfAiluxBdContext() {
  var el = document.getElementById('kf-ailux-bd-rows');
  if (!el) return;
  try {
    var res = await _sb.from('ailux_bd_context')
      .select('context_key,context_value,strategic_implication,confidence')
      .in('context_key', ['asset_sale_timing','optimal_partner_profile','negotiation_leverage_drivers'])
      .order('context_key');
    var rows = res.data || [];
    var keyLabels = { asset_sale_timing:'Deal Timing', optimal_partner_profile:'Best-Fit Partners', negotiation_leverage_drivers:'Leverage Drivers' };
    el.innerHTML = rows.map(function(r) {
      var label = keyLabels[r.context_key] || r.context_key.replace(/_/g,' ');
      var confMap = { high:'#16a34a', medium:'#d97706', low:'#dc2626' };
      var cc = confMap[r.confidence] || '#d97706';
      return '<div style="margin-bottom:12px;padding:10px 12px;background:#f8fafc;border-radius:7px;border-left:3px solid ' + cc + '">' +
        '<div style="font-size:10px;font-weight:800;color:' + cc + ';text-transform:uppercase;letter-spacing:0.4px;margin-bottom:3px">' + escHtml(label) + '</div>' +
        '<div style="font-size:11.5px;color:#1e293b;line-height:1.55;margin-bottom:4px">' + escHtml(r.context_value.substring(0,250)) + (r.context_value.length > 250 ? '…' : '') + '</div>' +
        (r.strategic_implication ? '<div style="font-size:11px;color:#475569;font-style:italic">' + escHtml(r.strategic_implication.substring(0,180)) + (r.strategic_implication.length > 180 ? '…' : '') + '</div>' : '') +
        '</div>';
    }).join('') || '<div style="color:#94a3b8;font-size:12px">No context available.</div>';
  } catch(e) {
    console.warn('KF ailux_bd_context error', e);
    if (el) el.innerHTML = '<div style="color:#94a3b8;font-size:12px">Could not load strategy context.</div>';
  }
}

async function _loadKfBdData() {
  var body = document.getElementById('kf-panel-body');
  try {
    var catsRes = await _sb.from('catalyst_calendar')
      .select('drug_id, event_name, expected_date, expected_quarter, strategic_significance, ailux_impact, drugs(name,stage)')
      .eq('verified', true)
      .not('is_past', 'is', true)
      .order('expected_date', { ascending: true })
      .limit(10);

    var cats = catsRes.data || [];
    var now = new Date();

    var catHtml = cats.length ? cats.map(function(c) {
      var daysUntil = c.expected_date ? Math.ceil((new Date(c.expected_date) - now) / 86400000) : null;
      var sig = c.strategic_significance;
      var sigColor = sig === 'P0' ? '#dc2626' : sig === 'P1' ? '#ea580c' : '#64748b';
      return '<div style="padding:8px 0;border-bottom:1px solid #f1f5f9;display:flex;gap:10px;align-items:flex-start;">' +
        '<span style="font-size:10px;font-weight:800;color:' + sigColor + ';background:' + sigColor + '18;border-radius:4px;padding:2px 6px;flex-shrink:0;margin-top:2px">' + (sig || '—') + '</span>' +
        '<div>' +
          '<div style="font-size:12px;font-weight:600;color:#1e293b">' + escHtml((c.drugs && c.drugs.name) || c.drug_id || '—') + '</div>' +
          '<div style="font-size:11px;color:#475569">' + escHtml(c.event_name || '') +
            (daysUntil !== null ? ' · <strong style="color:' + (daysUntil < 90 ? '#dc2626' : '#374151') + '">' + daysUntil + 'd away</strong>' : (c.expected_quarter ? ' · ' + c.expected_quarter : '')) +
          '</div>' +
          (c.ailux_impact ? '<div style="font-size:11px;color:#6b7280;margin-top:2px;font-style:italic">' + escHtml(c.ailux_impact) + '</div>' : '') +
        '</div>' +
        '</div>';
    }).join('') : '<div style="color:#94a3b8;font-size:12px">No upcoming catalysts tracked.</div>';

    if (body) {
      body.innerHTML =
        '<div class="kf-section">' +
          '<div class="kf-section-title">Upcoming catalysts</div>' +
          catHtml +
        '</div>';
    }
  } catch(e) {
    console.warn('KF BD data error', e);
    if (body) body.innerHTML = '<div class="kf-loading">Could not load BD data.</div>';
  }
}

// ═══════════════════════════════════════════════════════
// DISCOVERY QUEUE PANEL — Meridian v2
// ═══════════════════════════════════════════════════════
var _dqpData = null;
var _dqpLoaded = false;

async function _loadResearchQueue() {
  if (_dqpLoaded && _dqpData) return _dqpData;
  try {
    var res = await _sb.from('research_queue')
      .select('id,entity_id,entity_name,priority:priority_score,assigned_status,created_at,reason,next_best_action,completeness_score')
      .eq('status', 'pending')
      .order('priority', { ascending: true })
      .order('created_at', { ascending: false })
      .limit(200);
    _dqpData = res.data || [];
    _dqpLoaded = true;

    // Update the nav badge
    var count = _dqpData.length;
    var navBadge = document.getElementById('dq-nav-badge');
    var navCount = document.getElementById('dq-nav-count');
    if (navBadge) navBadge.style.display = count > 0 ? 'inline-flex' : 'none';
    if (navCount) navCount.textContent = count;

    return _dqpData;
  } catch(e) {
    console.warn('DQP load error', e);
    return [];
  }
}

// Initialise on page load — fetch queue and update badge
document.addEventListener('DOMContentLoaded', function() {
  setTimeout(function() { _loadResearchQueue(); }, 2000);
});

function openDQPanel() {
  document.getElementById('dqp-overlay').classList.add('open');
  _renderDQPanel();
}

function closeDQPanel() {
  document.getElementById('dqp-overlay').classList.remove('open');
}

async function _renderDQPanel() {
  var body = document.getElementById('dqp-body');
  var countsEl = document.getElementById('dqp-hero-counts');
  if (!body) return;

  body.innerHTML = '<div class="dqp-empty">Loading…</div>';

  var items = await _loadResearchQueue();

  if (!items.length) {
    body.innerHTML = '<div class="dqp-empty">No pending items in the research queue. The pipeline is up to date.</div>';
    if (countsEl) countsEl.innerHTML = '';
    return;
  }

  // Group by priority
  var groups = { P0: [], P1: [], P2: [], P3: [] };
  var other = [];
  items.forEach(function(item) {
    var p = (item.priority || 'P3').toUpperCase();
    if (groups[p]) groups[p].push(item);
    else other.push(item);
  });

  // Hero counts
  if (countsEl) {
    var countHtml = '';
    Object.keys(groups).forEach(function(p) {
      if (groups[p].length) {
        var cls = p.toLowerCase();
        countHtml += '<div class="dqp-hcount ' + cls + '">' + p + ' · ' + groups[p].length + '</div>';
      }
    });
    if (other.length) countHtml += '<div class="dqp-hcount">' + other.length + ' other</div>';
    countsEl.innerHTML = countHtml;
  }

  var now = new Date();
  function ageStr(ts) {
    if (!ts) return '';
    var d = Math.floor((now - new Date(ts)) / 86400000);
    if (d === 0) return 'today';
    if (d === 1) return '1d ago';
    if (d < 30) return d + 'd ago';
    return Math.floor(d/30) + 'mo ago';
  }

  function buildGroup(label, p, arr) {
    if (!arr.length) return '';
    var cls = p.toLowerCase();
    var rows = arr.map(function(item) {
      var gapText = item.gap_type || item.reason || item.next_best_action || '';
      var entityType = item.entity_type ? ' · ' + item.entity_type : '';
      var score = item.completeness_score != null ? ' · ' + Math.round(item.completeness_score) + '% complete' : '';
      var itemId = item.id || '';
      var entityName = item.entity_name || item.entity_id || '—';
      return '<div class="dqp-row">' +
        '<div class="dqp-badge ' + cls + '" onclick="closeDQPanel();navTo(\'discovery-queue\')" style="cursor:pointer">' + p + '</div>' +
        '<div style="min-width:0;flex:1;cursor:pointer" onclick="closeDQPanel();navTo(\'discovery-queue\')">' +
          '<div class="dqp-row-name">' + escHtml(entityName) + '</div>' +
          '<div class="dqp-row-gap">' + escHtml(gapText.slice(0,80)) + entityType + score + '</div>' +
        '</div>' +
        '<div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px;flex-shrink:0">' +
          '<div class="dqp-row-age">' + ageStr(item.created_at) + '</div>' +
          (itemId ? '<button onclick="event.stopPropagation();_dqResearchNow(\'' + itemId + '\',\'' + escHtml(entityName).replace(/'/g,'\\\'') + '\')" ' +
            'style="font-size:9px;font-weight:700;padding:3px 8px;border-radius:4px;border:1px solid #2563eb;background:white;color:#2563eb;cursor:pointer;white-space:nowrap;transition:all .15s" ' +
            'onmouseover="this.style.background=\'#2563eb\';this.style.color=\'white\'" ' +
            'onmouseout="this.style.background=\'white\';this.style.color=\'#2563eb\'" ' +
            'title="Queue this item for the next pipeline run">▶ Research Now</button>' : '') +
        '</div>' +
      '</div>';
    }).join('');
    return '<div class="dqp-priority-group">' +
      '<div class="dqp-group-hd ' + cls + '">' + label + ' — ' + arr.length + ' item' + (arr.length !== 1 ? 's' : '') + '</div>' +
      rows +
    '</div>';
  }

  var html = '';
  html += buildGroup('P0 — Critical', 'P0', groups.P0);
  html += buildGroup('P1 — Important', 'P1', groups.P1);
  html += buildGroup('P2 — Fill-in', 'P2', groups.P2);
  html += buildGroup('P3 — Background', 'P3', groups.P3);
  if (other.length) html += buildGroup('Other', 'P3', other);

  body.innerHTML = html || '<div class="dqp-empty">No pending items.</div>';
}

// ─── Research Now — queue a research_queue item for the next pipeline run ───
async function _dqResearchNow(itemId, entityName) {
  if (!itemId) return;

  // Optimistically update button to show it's been queued
  var btns = document.querySelectorAll('[onclick*="_dqResearchNow(\'' + itemId + '\'"]');
  btns.forEach(function(b) {
    b.disabled = true;
    b.textContent = '⏳ Queued';
    b.style.borderColor = '#94a3b8';
    b.style.color = '#94a3b8';
    b.style.background = 'white';
  });

  try {
    var now = new Date().toISOString();
    var { error } = await _sb.from('research_queue')
      .update({
        assigned_status: 'processing',
        last_action_at: now,
        next_best_action: 'Manually queued via Research Now — will be processed by next pipeline run',
      })
      .eq('id', itemId);

    if (error) throw error;

    // Show toast
    var toast = document.createElement('div');
    toast.innerHTML = '<strong>' + escHtml(entityName) + '</strong> queued for research. '
      + 'Run <code style="font-size:10px;background:rgba(255,255,255,0.2);padding:1px 4px;border-radius:3px">'
      + 'python3 scripts/process_queue_item.py --batch</code> to execute now.';
    Object.assign(toast.style, {
      position: 'fixed', bottom: '24px', left: '50%', transform: 'translateX(-50%)',
      background: '#1e40af', color: 'white', padding: '10px 20px', borderRadius: '8px',
      fontSize: '12px', fontWeight: '600', zIndex: '99999',
      boxShadow: '0 4px 12px rgba(0,0,0,0.25)', maxWidth: '520px', textAlign: 'center',
      lineHeight: '1.5',
    });
    document.body.appendChild(toast);
    setTimeout(function() { toast.remove(); }, 5000);

    // Update button to confirmed state
    btns.forEach(function(b) {
      b.textContent = '✓ Queued';
      b.style.borderColor = '#059669';
      b.style.color = '#059669';
    });

  } catch(e) {
    console.error('_dqResearchNow error:', e);
    // Restore button on failure
    btns.forEach(function(b) {
      b.disabled = false;
      b.textContent = '▶ Research Now';
      b.style.borderColor = '#2563eb';
      b.style.color = '#2563eb';
    });
    alert('Error queuing item: ' + (e.message || e));
  }
}

// ═══════════════════════════════════════════════════════
// ABOUT THIS DATA PANEL — Meridian v2
// ═══════════════════════════════════════════════════════
function openAboutDataPanel() {
  document.getElementById('atd-overlay').classList.add('open');
}

function closeAboutDataPanel() {
  document.getElementById('atd-overlay').classList.remove('open');
}

// ═══════════════════════════════════════════════════════
// ENHANCED SEARCH — add indications/areas to Supabase search
// ═══════════════════════════════════════════════════════
// Patch _gsSbSearch to also query indications, patient intel, and news_articles
var _gsSbSearchOrig = _gsSbSearch;

// ── Source label helper ────────────────────────────────────────────────────
var _GS_SOURCE_LABELS = {
  'fiercebiotech.com':'Fierce','fiercepharma.com':'Fierce',
  'endpts.com':'Endpoints','endpoints.news':'Endpoints',
  'prnewswire.com':'PRNewswire','businesswire.com':'BusinessWire',
  'globenewswire.com':'GlobeNewswire',
  'statnews.com':'STAT','biopharmadive.com':'BioPharma Dive',
  'reuters.com':'Reuters','bloomberg.com':'Bloomberg',
  'sec.gov':'SEC','clinicaltrials.gov':'ClinicalTrials.gov'
};
function _gsSourceLabel(url) {
  try {
    var host = new URL(url).hostname.replace('www.','');
    var match = Object.entries(_GS_SOURCE_LABELS).find(function(e) { return host.includes(e[0]); });
    return match ? match[1] : host.split('.')[0];
  } catch(e) { return 'Source'; }
}

// ── News dedup: token overlap >60% = same story ────────────────────────────
function _gsNewsTokens(headline) {
  return (headline||'').toLowerCase().replace(/[^\w\s]/g,'').split(/\s+/).filter(function(w) {
    return w.length > 3 && !['with','that','from','this','have','been','will','were','they','their','into','more','than','also'].includes(w);
  });
}
function _gsNewsOverlap(a, b) {
  var ta = _gsNewsTokens(a), tb = _gsNewsTokens(b);
  if (!ta.length || !tb.length) return 0;
  var setB = new Set(tb);
  var shared = ta.filter(function(w) { return setB.has(w); }).length;
  return shared / Math.max(ta.length, tb.length);
}
function _gsDedupeNews(items) {
  var groups = [];
  items.forEach(function(item) {
    var placed = false;
    for (var i = 0; i < groups.length; i++) {
      if (_gsNewsOverlap(item.headline, groups[i][0].headline) > 0.6) {
        groups[i].push(item);
        placed = true;
        break;
      }
    }
    if (!placed) groups.push([item]);
  });
  return groups;
}

// ── Show/hide extra sources list ───────────────────────────────────────────
function _gsShowSources(btn) {
  var list = btn.parentElement.nextElementSibling;
  if (list) list.style.display = list.style.display === 'none' ? 'block' : 'none';
}

// ── Format date string to short form ──────────────────────────────────────
function _gsShortDate(dateStr) {
  if (!dateStr) return '';
  try {
    var d = new Date(dateStr);
    return d.toLocaleDateString('en-US', {month:'short', day:'numeric'});
  } catch(e) { return dateStr.slice(0,10); }
}

async function _gsSbSearch(term) {
  // Rebuilt 2026-06-07 (Kyle): collapsible categories, relevance-sorted, every row
  // opens its stored web source directly; drugs/companies open their in-app cards.
  var panel = document.getElementById('gs-sb-panel');
  if (!panel) return;
  if (!term || term.length < 2) { panel.style.display = 'none'; return; }
  var esc = term.replace(/[%_\\]/g, function(c) { return '\\' + c; });
  panel.innerHTML = '<div class="gs-sb-empty">Searching…</div>';
  panel.style.display = 'block';
  try {
    if (typeof _loadSentimentMap === 'function' && !window._SENT_MAP) { try { await _loadSentimentMap(); } catch(e){} }
    var results = await Promise.all([
      _sb.from('companies').select('id,name,ticker,company_type,geography,status')
        .neq('status','acquired').or('name.ilike.%' + esc + '%,ticker.ilike.%' + esc + '%').limit(8),
      _sb.from('drugs').select('id,name,display_name,stage,mechanism,company_id,source_url,canonical_drug_id')
        .or('name.ilike.%' + esc + '%,display_name.ilike.%' + esc + '%,mechanism.ilike.%' + esc + '%').limit(8),
      _sb.from('intel').select('id,intel_date,headline,intel_type,importance,source_url')
        .or('headline.ilike.%' + esc + '%,body.ilike.%' + esc + '%')
        .order('intel_date', { ascending: false }).limit(8),
      _sb.from('deals').select('id,deal_date,headline,from_company,to_company,deal_type,total_usd_m,source_url')
        .or('headline.ilike.%' + esc + '%,detail.ilike.%' + esc + '%,from_company.ilike.%' + esc + '%,to_company.ilike.%' + esc + '%')
        .order('deal_date', { ascending: false }).limit(8),
      _sb.from('catalysts').select('id,catalyst_date,label,significance,source_url')
        .eq('resolved', false).or('label.ilike.%' + esc + '%,notes.ilike.%' + esc + '%')
        .order('sort_date', { ascending: true }).limit(8),
      _sb.from('indications').select('id,name,abbreviation,disease_area')
        .or('name.ilike.%' + esc + '%,abbreviation.ilike.%' + esc + '%').limit(6),
      _sb.from('news_articles').select('id,headline,article_url,source_name,published_at,relevance_score')
        .or('headline.ilike.%' + esc + '%,meridian_summary.ilike.%' + esc + '%')
        .neq('source_validation_status','invalid')
        .order('published_at', { ascending: false }).limit(10),
      _sb.from('drug_aliases').select('canonical_id,alias_name')
        .ilike('alias_name', '%' + esc + '%').limit(10),
      _sb.from('targets').select('id,symbol,name,target_class')
        .or('symbol.ilike.%' + esc + '%,name.ilike.%' + esc + '%').limit(6),
      _sb.from('publications').select('id,title,journal,pub_year,doi,url,cited_by_count')
        .ilike('title', '%' + esc + '%')
        .order('cited_by_count', { ascending: false, nullsFirst: false }).limit(8),
      _sb.from('conference_abstracts').select('id,title,conference,conference_year,doi,source_url')
        .ilike('title', '%' + esc + '%').order('conference_year', { ascending: false }).limit(8),
      _sb.from('strategic_insights').select('id,title,detail,insight_type,created_at')
        .or('title.ilike.%' + esc + '%,detail.ilike.%' + esc + '%')
        .order('created_at', { ascending: false }).limit(8),
      _sb.from('grants').select('id,title,agency,fiscal_year,award_amount,project_url,source_url')
        .ilike('title', '%' + esc + '%').order('fiscal_year', { ascending: false }).limit(8),
      _sb.from('trial_facts').select('nct_id,title,phase,status,source_url')
        .or('title.ilike.%' + esc + '%,nct_id.ilike.%' + esc + '%')
        .limit(8),
      _sb.from('kols').select('id,name,specialty')
        .ilike('name', '%' + esc + '%').limit(6),
      _sb.from('company_events').select('id,event_summary,event_type,filing_date,source_url')
        .ilike('event_summary', '%' + esc + '%')
        .order('filing_date', { ascending: false }).limit(8),
      _sb.from('indication_patient_intelligence').select('indication_name,patient_count_us,unmet_need_narrative')
        .ilike('indication_name', '%' + esc + '%').limit(4),
      _sb.from('intel_facts').select('claim,fact_type,subject_id,subject_name,area_id,source_url,page_ref')
        .ilike('claim', '%' + esc + '%').limit(12),
    ]);
    var D = results.map(function(r) { return (r && r.data) || []; });
    var cos=D[0], drugs=D[1], intel=D[2], deals=D[3], cats=D[4], indics=D[5], news=D[6],
        aliases=D[7], tgts=D[8], pubs=D[9], confAbs=D[10], insights=D[11], grants2=D[12],
        trials=D[13], kolHits=D[14], secEvts=D[15], patIntel=D[16], ifacts=D[17];

    // alias hits → resolve to drugs not already matched
    try {
      var haveC = {}; drugs.forEach(function(x){ if (x.canonical_drug_id) haveC[x.canonical_drug_id]=1; });
      var want = []; var aMap = {};
      aliases.forEach(function(a){ if (a.canonical_id && !haveC[a.canonical_id]) { if (want.indexOf(a.canonical_id)<0) want.push(a.canonical_id); if (!aMap[a.canonical_id]) aMap[a.canonical_id]=a.alias_name; } });
      if (want.length) {
        var aRes = await _sb.from('drugs').select('id,name,display_name,stage,mechanism,company_id,source_url,canonical_drug_id')
          .in('canonical_drug_id', want).limit(6);
        (aRes.data||[]).forEach(function(dd){ if (!drugs.some(function(x){return x.id===dd.id;})) { dd._aliasHit = aMap[dd.canonical_drug_id]; drugs.push(dd); } });
      }
    } catch(e) {}

    var tl = term.toLowerCase();
    function mScore(text) {  // how well the visible text matches the query
      var s = (text||'').toLowerCase(); var i = s.indexOf(tl);
      if (i < 0) return 0.2;          // matched on a hidden field (body/detail)
      if (i === 0) return 3;
      return /\W/.test(s.charAt(i-1)) ? 2 : 1;
    }
    var re = new RegExp(term.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'), 'gi');
    function hl(s) { return (s||'').replace(/</g,'&lt;').replace(re, function(m){ return '<mark class="gs-hl">'+m+'</mark>'; }); }
    function meta(parts) { return '<div class="gs-sb-meta">' + parts.filter(Boolean).join('') + '</div>'; }
    function badge(t, c) { return t ? '<span class="gs-sb-badge" style="background:'+(c||'rgba(255,255,255,0.1)')+';color:rgba(255,255,255,0.75)">'+t+'</span>' : ''; }
    function span(t) { return t ? '<span>'+t+'</span>' : ''; }

    // every item: {score, url (direct web source) OR nav (in-app card), inner html}
    var groups = [];
    function grp(label, items) {
      items = items.filter(Boolean).sort(function(a,b){ return b.score - a.score; });
      if (items.length) groups.push({ label: label, items: items, top: items[0].score });
    }

    grp('Drugs', drugs.map(function(d){
      var label = d.display_name || d.name;
      return { score: mScore(label) + mScore(d.name) * 0.5 + (d._aliasHit ? 1.5 : 0),
        nav: { gtype:'drug', id:d.id, name:label }, srcUrl: d.source_url || '',
        inner: '<div class="gs-sb-headline">'+hl(label)+(d._aliasHit?' <span class="gs-sb-badge" style="background:rgba(124,185,255,0.2);color:#7cb9ff">aka '+hl(d._aliasHit)+'</span>':'')+'</div>'+
               meta([badge(d.stage), span(hl(d.mechanism||'')), span(d.company_id||''), '<span class="gs-sb-nav-pill">→ drug card</span>']) };
    }));
    grp('Companies', cos.map(function(c){
      return { score: mScore(c.name) + (c.ticker && c.ticker.toLowerCase()===tl ? 2 : 0),
        nav: { gtype:'company', id:c.id, name:c.name },
        inner: '<div class="gs-sb-headline">'+hl(c.name)+(typeof _sentDotHTML==='function'?_sentDotHTML(c.id):'')+(c.ticker?' <span class="gs-sb-badge" style="background:rgba(255,255,255,0.1);color:rgba(255,255,255,0.7)">'+c.ticker+'</span>':'')+'</div>'+
               meta([span(c.company_type||''), span(c.geography||''), '<span class="gs-sb-nav-pill">→ company card</span>']) };
    }));
    grp('Research facts', (ifacts||[]).map(function(f){
      return { score: mScore(f.claim) + 0.4,
        url: f.source_url || '',
        inner: '<div class="gs-sb-headline">'+hl(f.claim||'')+'</div>'+
               meta([badge(f.fact_type,'rgba(34,197,94,0.25)'), span(f.subject_name||''), span(f.area_id||''), span(f.page_ref||''), '<span class="gs-sb-nav-pill">↗ source</span>']) };
    }));
    grp('Targets', tgts.map(function(t){
      return { score: mScore(t.symbol) * 1.2 + mScore(t.name) * 0.5,
        inner: '<div class="gs-sb-headline">'+hl(t.symbol||t.name)+'</div>'+meta([span(hl(t.name||'')), badge(t.target_class)]) };
    }));
    grp('Disease Areas', indics.map(function(x){
      return { score: mScore(x.name) + mScore(x.abbreviation),
        inner: '<div class="gs-sb-headline">'+hl(x.name)+(x.abbreviation?' ('+hl(x.abbreviation)+')':'')+'</div>'+meta([span(x.disease_area||'')]) };
    }));
    grp('News', news.map(function(n){
      return { score: mScore(n.headline) + (n.relevance_score||0)/100,
        url: n.article_url,
        inner: '<div class="gs-sb-headline">'+hl(n.headline)+'</div>'+
               meta([badge(_gsSourceLabel(n.article_url||''),'rgba(46,111,176,0.35)'), span(_gsShortDate(n.published_at))]) };
    }));
    grp('Intel', intel.map(function(x){
      return { score: mScore(x.headline) + (x.importance==='high'?1:x.importance==='medium'?0.5:0),
        url: x.source_url,
        inner: '<div class="gs-sb-headline">'+hl(x.headline)+'</div>'+
               meta([badge(x.intel_type), badge(x.importance, x.importance==='high'?'rgba(239,68,68,0.25)':''), span(x.intel_date||'')]) };
    }));
    grp('Deals', deals.map(function(x){
      return { score: mScore(x.headline) + mScore(x.from_company)*0.5 + mScore(x.to_company)*0.5 + (x.total_usd_m?Math.min(x.total_usd_m/5000,1):0),
        url: x.source_url,
        inner: '<div class="gs-sb-headline">'+hl(x.headline || (x.from_company+' → '+x.to_company))+'</div>'+
               meta([badge(x.deal_type), span(x.total_usd_m?('$'+x.total_usd_m+'M'):''), span(x.deal_date||'')]) };
    }));
    grp('Catalysts', cats.map(function(c){
      return { score: mScore(c.label) + (c.significance==='high'?1:c.significance==='medium'?0.5:0),
        url: c.source_url,
        inner: '<div class="gs-sb-headline">'+hl(c.label)+'</div>'+
               meta([badge(c.significance, c.significance==='high'?'rgba(239,68,68,0.25)':''), span(c.catalyst_date||'')]) };
    }));
    grp('Clinical Trials', trials.map(function(t){
      return { score: mScore(t.title) + mScore(t.nct_id)*1.5,
        url: t.source_url || ('https://clinicaltrials.gov/study/' + t.nct_id),
        inner: '<div class="gs-sb-headline">'+hl(t.title||t.nct_id)+'</div>'+
               meta([badge(t.nct_id,'rgba(46,111,176,0.35)'), badge(t.phase), span(t.status||'')]) };
    }));
    grp('Publications', pubs.map(function(p){
      return { score: mScore(p.title) + Math.min((p.cited_by_count||0)/200, 1),
        url: p.doi ? ('https://doi.org/'+p.doi) : p.url,
        inner: '<div class="gs-sb-headline">'+hl(p.title)+'</div>'+
               meta([span(p.journal||''), span(p.pub_year||''), span(p.cited_by_count?p.cited_by_count+' citations':'')]) };
    }));
    grp('Congress Abstracts', confAbs.map(function(a){
      return { score: mScore(a.title) + (a.conference_year>=2025?0.5:0),
        url: a.doi ? ('https://doi.org/'+a.doi) : a.source_url,
        inner: '<div class="gs-sb-headline">'+hl(a.title)+'</div>'+meta([badge(a.conference), span(a.conference_year||'')]) };
    }));
    grp('Meridian Conclusions', insights.map(function(s){
      return { score: mScore(s.title) + 0.3,
        inner: '<div class="gs-sb-headline">'+hl(s.title)+'</div>'+
               meta([badge(s.insight_type,'rgba(46,111,176,0.35)'), span((s.detail||'').slice(0,100))]) };
    }));
    grp('SEC Events', secEvts.map(function(ev){
      return { score: mScore(ev.event_summary) + (ev.event_type==='deal'||ev.event_type==='ma'?0.8:0.2),
        url: ev.source_url,
        inner: '<div class="gs-sb-headline">'+hl(ev.event_summary)+'</div>'+meta([badge(ev.event_type), span(ev.filing_date||'')]) };
    }));
    grp('NIH Grants', grants2.map(function(g){
      return { score: mScore(g.title) + Math.min((g.award_amount||0)/3e6, 0.8),
        url: g.project_url || g.source_url,
        inner: '<div class="gs-sb-headline">'+hl(g.title)+'</div>'+
               meta([span(g.agency||'NIH'), span('FY'+(g.fiscal_year||'')), span(g.award_amount?('$'+Math.round(g.award_amount/1000)+'k'):'')]) };
    }));
    grp('KOLs', kolHits.map(function(k){
      return { score: mScore(k.name),
        url: 'https://clinicaltrials.gov/search?term=' + encodeURIComponent(k.name||''),
        inner: '<div class="gs-sb-headline">'+hl(k.name)+'</div>'+meta([span(k.specialty||'investigator'), span('trials ↗')]) };
    }));
    grp('Patient Intelligence', patIntel.map(function(p){
      return { score: mScore(p.indication_name) + 0.5,
        inner: '<div class="gs-sb-headline">'+hl(p.indication_name)+'</div>'+
               meta([span(p.patient_count_us?('US patients: '+p.patient_count_us):''), span((p.unmet_need_narrative||'').slice(0,90))]) };
    }));

    if (!groups.length) {
      panel.innerHTML = '<div class="gs-sb-empty">No results for "<em>' + term.replace(/</g,'&lt;') + '</em>"</div>';
      return;
    }
    // most relevant category first; auto-open the best one
    groups.sort(function(a,b){ return b.top - a.top; });
    var html = '<div class="gs-sb-section-hd" style="display:flex;justify-content:space-between"><span>' +
      groups.reduce(function(s,g){ return s+g.items.length; },0) + ' results in ' + groups.length +
      ' categories</span><span style="text-transform:none;letter-spacing:0">click a row to open its source ↗</span></div>';
    groups.forEach(function(g, gi) {
      html += '<details class="gs-grp"' + (gi===0 ? ' open' : '') + '><summary><span class="gs-grp-car">▶</span>' +
        g.label + '<span class="gs-grp-cnt">' + g.items.length + '</span></summary>';
      g.items.forEach(function(it) {
        if (it.nav) {  // drugs/companies → in-app card via the delegated handler
          var dAttrs = it.nav.gtype==='company'
            ? ' data-gtype="company" data-company-id="'+it.nav.id+'" data-company-name="'+(it.nav.name||'').replace(/"/g,'&quot;')+'"'
            : ' data-gtype="drug" data-drug-id="'+it.nav.id+'" data-drug-name="'+(it.nav.name||'').replace(/"/g,'&quot;')+'"';
          html += '<div class="gs-sb-item gs-nav-item"'+dAttrs+' style="cursor:pointer">' + it.inner +
            (it.srcUrl ? '<a class="gs-sb-src" href="'+it.srcUrl+'" target="_blank" rel="noopener" data-trusted="1" onclick="event.stopPropagation()">source ↗</a>' : '') + '</div>';
        } else if (it.url) {  // everything with a stored source → straight to the web
          html += '<a class="gs-sb-item" href="'+it.url+'" target="_blank" rel="noopener" data-trusted="1">' + it.inner + '</a>';
        } else {
          html += '<div class="gs-sb-item" style="cursor:default">' + it.inner + '</div>';
        }
      });
      html += '</details>';
    });

    panel.innerHTML = html;
  } catch(e) {
    panel.innerHTML = '<div class="gs-sb-empty">Search error: ' + e.message + '</div>';
  }
}

// Handle Knowledge Folder click in search results (targets + indications)
document.addEventListener('click', function(e) {
  var item = e.target.closest('.gs-nav-item[data-gtype="knowledgefolder"]');
  if (item) {
    var slug = item.dataset.kfSlug;
    var panel = document.getElementById('gs-sb-panel');
    if (panel) panel.style.display = 'none';
    if (slug && typeof openKnowledgeFolder === 'function') openKnowledgeFolder(slug);
  }
}, true);

// openKFFromIndication — maps an indication string to a KF slug and opens it
function openKFFromIndication(indStr) {
  if (!indStr || indStr === '—') return;
  var t = indStr.toLowerCase();
  var indicSlugMap = [
    {keys:['ulcerative colitis',' uc ','\\buc\\b'],  slug:'uc'},
    {keys:["crohn's disease",'crohn disease','\\bcd\\b'], slug:'cd'},
    {keys:['rheumatoid arthritis','\\bra\\b'], slug:'ra'},
    {keys:['thyroid eye disease','\\bted\\b'], slug:'ted'},
    {keys:["graves' disease",'graves disease','graves'], slug:'graves'},
    {keys:['myasthenia gravis','\\bgmg\\b','\\bmg\\b'],  slug:'mg'},
    {keys:['cidp','chronic inflammatory demyelinating'], slug:'cidp'},
    {keys:['atopic dermatitis','\\bad\\b','atopy'],    slug:'atopy'},
    {keys:['inflammatory bowel','\\bibd\\b'],          slug:'ibd'},
  ];
  var match = null;
  for (var i = 0; i < indicSlugMap.length; i++) {
    var entry = indicSlugMap[i];
    for (var j = 0; j < entry.keys.length; j++) {
      try {
        if (new RegExp(entry.keys[j],'i').test(t)) { match = entry.slug; break; }
      } catch(e) {
        if (t.includes(entry.keys[j])) { match = entry.slug; break; }
      }
    }
    if (match) break;
  }
  if (match && typeof openKnowledgeFolder === 'function') openKnowledgeFolder(match);
}

// openKFFromTarget — maps a target string from the PI table to a KF slug and opens it
function openKFFromTarget(targetStr) {
  if (!targetStr || targetStr === '—') return;
  var t = targetStr.toLowerCase().replace(/[\s×x\-_\/]/g, '');
  var slugMap = [
    {keys:['tl1a'],              slug:'tl1a'},
    {keys:['il23','il23p19'],    slug:'il23'},
    {keys:['igf1r','tshr'],      slug:'ted'},
    {keys:['fcrn'],              slug:'fcrn'},
    {keys:['il4ra'],             slug:'atopy'},
    {keys:['tslp'],              slug:'atopy'},
    {keys:['cd19','bcma','cd38'],slug:'ace'},
  ];
  var match = null;
  for (var i = 0; i < slugMap.length; i++) {
    var entry = slugMap[i];
    for (var j = 0; j < entry.keys.length; j++) {
      if (t.includes(entry.keys[j])) { match = entry.slug; break; }
    }
    if (match) break;
  }
  if (match && typeof openKnowledgeFolder === 'function') openKnowledgeFolder(match);
}


