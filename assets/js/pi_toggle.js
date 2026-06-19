function piToggle(cid){
  var dr=document.getElementById('pi-dr-'+cid);
  var ch=document.getElementById('pi-ch-'+cid);
  if(!dr) return;
  var open=dr.style.display==='table-row';
  dr.style.display=open?'none':'table-row';
  if(ch){ ch.className=open?'pi-chevron':'pi-chevron open'; }
}

function piSort(tableId, colIdx, isNumeric) {
  var tbl = document.getElementById(tableId);
  if (!tbl) return;
  var tbody = tbl.querySelector('tbody');
  var mainRows = Array.from(tbody.querySelectorAll('.pi-main-row'));
  var pairs = mainRows.map(function(mr) {
    var m = mr.getAttribute('onclick').match(/'([^']+)'/);
    var key = m ? m[1] : '';
    return { mainRow: mr, drRow: document.getElementById('pi-dr-' + key) };
  });
  var prevCol = tbl.getAttribute('data-sort-col');
  var prevDir = tbl.getAttribute('data-sort-dir') || 'asc';
  var newDir = (prevCol == colIdx && prevDir === 'asc') ? 'desc' : 'asc';
  function parseVal(pair) {
    var cells = pair.mainRow.querySelectorAll('td');
    var cell = cells[colIdx];
    if (!cell) return isNumeric ? 0 : '';
    var text = cell.textContent.replace(/\s+/g,' ').trim();
    if (isNumeric) {
      var m2 = text.match(/([\d.]+)\s*([BbMmKk]?)/);
      if (!m2) return 0;
      var v = parseFloat(m2[1]);
      var u = (m2[2]||'').toUpperCase();
      if (u === 'B') v *= 1000;
      else if (u === 'K') v /= 1000;
      return v;
    }
    return text.toLowerCase();
  }
  pairs.sort(function(a, b) {
    var va = parseVal(a), vb = parseVal(b);
    if (isNumeric) return newDir === 'asc' ? va - vb : vb - va;
    if (va < vb) return newDir === 'asc' ? -1 : 1;
    if (va > vb) return newDir === 'asc' ? 1 : -1;
    return 0;
  });
  pairs.forEach(function(p) {
    tbody.appendChild(p.mainRow);
    if (p.drRow) tbody.appendChild(p.drRow);
  });
  tbl.setAttribute('data-sort-col', colIdx);
  tbl.setAttribute('data-sort-dir', newDir);
  tbl.querySelectorAll('th').forEach(function(th, i) {
    th.classList.remove('pi-sort-asc','pi-sort-desc');
    if (i == colIdx) th.classList.add(newDir === 'asc' ? 'pi-sort-asc' : 'pi-sort-desc');
  });
}

function piFilter(input, tableId) {
  var q = input.value.toLowerCase().trim();
  var tbl = document.getElementById(tableId);
  if (!tbl) return;
  var tbody = tbl.querySelector('tbody');
  tbody.querySelectorAll('.pi-main-row').forEach(function(mr) {
    var m = mr.getAttribute('onclick').match(/'([^']+)'/);
    var key = m ? m[1] : '';
    var drRow = document.getElementById('pi-dr-' + key);
    var show = !q || mr.textContent.toLowerCase().includes(q);
    mr.style.display = show ? '' : 'none';
    if (drRow && !show) drRow.style.display = 'none';
  });
}

// ── All Companies (Pharma Landscape) ──────────────────────────────────────
let _acData = [], _acFiltered = [], _acInitialized = false;

async function _initAllCompanies() {
  if (_acInitialized) return;
  _acInitialized = true;
  const wrap = document.getElementById('all-cos-wrap');
  if (wrap) wrap.innerHTML = '<div style="padding:28px;text-align:center;color:#94a3b8;font-size:12px;font-style:italic">⟳ Loading companies…</div>';

  if (typeof _sb === 'undefined' || !_sb) { _acRender(); return; }
  try {
    const [coRes, drugRes] = await Promise.all([
      _sb.from('companies').select('id,name,ticker,company_type,geography,market_cap_display,ta_focus_1,ta_focus_2,status').neq('status','acquired').order('name'),
      _sb.from('drugs').select('company_id,stage')
    ]);
    const drugCounts = {};
    (drugRes.data || []).forEach(function(d) {
      if (d.stage !== 'Terminated') drugCounts[d.company_id] = (drugCounts[d.company_id] || 0) + 1;
    });
    _acData = (coRes.data || []).map(function(c) { return Object.assign({}, c, { drug_count: drugCounts[c.id] || 0 }); });
    _acFiltered = _acData.slice();
  } catch(e) { console.warn('[_initAllCompanies]', e.message); }
  _acRender();
}

function _acFilter() {
  var q = (document.getElementById('all-cos-search') ? document.getElementById('all-cos-search').value : '').toLowerCase().trim();
  var geo = document.getElementById('all-cos-geo') ? document.getElementById('all-cos-geo').value : '';
  var type = document.getElementById('all-cos-type') ? document.getElementById('all-cos-type').value : '';
  _acFiltered = _acData.filter(function(c) {
    if (q && !c.name.toLowerCase().includes(q) && !(c.ticker||'').toLowerCase().includes(q)
        && !(c.ta_focus_1||'').toLowerCase().includes(q) && !(c.ta_focus_2||'').toLowerCase().includes(q)) return false;
    if (geo === 'bd' && c.geography) return false;
    if (geo && geo !== 'bd' && c.geography !== geo) return false;
    if (type && c.company_type !== type) return false;
    return true;
  });
  var countEl = document.getElementById('all-cos-count');
  if (countEl) countEl.textContent = _acFiltered.length + ' of ' + _acData.length + ' companies';
  _acRender();
}

function _acRender() {
  var wrap = document.getElementById('all-cos-wrap');
  if (!wrap) return;
  var countEl = document.getElementById('all-cos-count');
  if (countEl) countEl.textContent = _acFiltered.length + ' of ' + _acData.length + ' companies';

  if (!_acFiltered.length) {
    wrap.innerHTML = '<div style="padding:20px;text-align:center;color:#94a3b8;font-size:12px">No companies match the selected filters.</div>';
    return;
  }
  var GEO_LABEL = { china: '🇨🇳', global: '🌐' };
  var GEO_COLOR = { china: '#dcfce7;color:#166534', global: '#dbeafe;color:#1d4ed8' };
  var TYPE_LABEL = { large_cap:'Large Cap', biotech:'Biotech', mid_cap:'Mid Cap', small_cap:'Small Cap', innovative:'Innovative', cdmo:'CDMO', state_owned:'State-owned', tcm:'TCM', distribution:'Distribution', pharma:'Pharma', private:'Private' };

  var rows = _acFiltered.map(function(c) {
    var geoFlag = GEO_LABEL[c.geography] || '';
    var geoLbl = c.geography ? (geoFlag + ' ' + (c.geography.charAt(0).toUpperCase() + c.geography.slice(1))) : '<span style="color:#94a3b8;font-size:10px">BD Focus</span>';
    var geoBg = c.geography ? ('background:#' + (GEO_COLOR[c.geography] || 'f1f5f9;color:#475569')) : '';
    var type = TYPE_LABEL[c.company_type] || c.company_type || '<span style="color:#94a3b8">—</span>';
    var ticker = c.ticker ? '<br><span style="color:#64748b;font-size:9.5px">' + c.ticker + '</span>' : '';
    var mktcap = c.market_cap_display || '<span style="color:#94a3b8">—</span>';
    var ta1 = c.ta_focus_1 ? '<span class="pi-ta-pill" style="font-size:10px">' + c.ta_focus_1 + '</span>' : '<span style="color:#94a3b8">—</span>';
    var ta2 = c.ta_focus_2 ? '<span class="pi-ta-pill pi-ta2" style="font-size:10px">' + c.ta_focus_2 + '</span>' : '';
    var drugs = c.drug_count > 0 ? '<span style="font-weight:700;color:#1e3a5f">' + c.drug_count + '</span>' : '<span style="color:#94a3b8">—</span>';
    var safeName = c.name.replace(/'/g, '\\\'');
    return '<tr class="ac-row" onclick="openCompanyEntityModal(\'' + c.id + '\',\'' + safeName + '\',\'pharma-intel\')" title="Open ' + c.name + ' dossier">'
      + '<td><strong>' + c.name + '</strong>' + ticker + '</td>'
      + '<td><span class="ac-geo-pill" style="' + geoBg + '">' + geoLbl + '</span></td>'
      + '<td style="font-size:10.5px;color:#475569">' + type + '</td>'
      + '<td style="font-size:10.5px;font-weight:600">' + mktcap + '</td>'
      + '<td>' + ta1 + '</td>'
      + '<td>' + ta2 + '</td>'
      + '<td style="text-align:center">' + drugs + '</td>'
      + '</tr>';
  }).join('');

  wrap.innerHTML = '<div class="ac-scroll"><table class="pi-table ac-table"><thead><tr>'
    + '<th style="width:24%">Company</th>'
    + '<th style="width:12%">Geography</th>'
    + '<th style="width:13%">Type</th>'
    + '<th style="width:10%">Mkt Cap</th>'
    + '<th style="width:16%">TA #1</th>'
    + '<th style="width:15%">TA #2</th>'
    + '<th style="width:8%;text-align:center">Drugs</th>'
    + '</tr></thead><tbody>' + rows + '</tbody></table></div>';
}
