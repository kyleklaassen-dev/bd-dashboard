// ── INTEL SUBMIT + DOCUMENT UPLOAD ────────────────────────────────
// Extracted from app.js (Domain A2, §3 byte-identical). Plain script, load BEFORE app.js.
// Functions stay global (header/index.html onclick handlers call them). External: _sb (core.js), DOM, storage.

// ── INTEL QUICK-SUBMIT MODAL (header button) ──────────────────────
// ── SUBMIT INTEL — simple modal (Path 5 intake) ──────────────────
function openIntelModal() {
  // Reset to form state
  document.getElementById('im-form-body').style.display = '';
  document.getElementById('im-footer').style.display = '';
  document.getElementById('im-success').classList.remove('show');
  document.getElementById('im-err').classList.remove('show');
  ['im-url','im-name'].forEach(id => document.getElementById(id)?.classList.remove('error'));
  _siResetFileAttachment();
  document.getElementById('intel-modal-overlay').classList.add('open');
  setTimeout(() => document.getElementById('im-text')?.focus(), 80);
}
function closeIntelModal() {
  document.getElementById('intel-modal-overlay').classList.remove('open');
  _siResetFileAttachment();
}
async function submitIntelNew() {
  const url  = (document.getElementById('im-url')?.value  || '').trim();
  const text = (document.getElementById('im-text')?.value || '').trim();
  const name = (document.getElementById('im-name')?.value || '').trim();
  const err  = document.getElementById('im-err');
  // Capture any attached file info
  const fileInput = document.getElementById('si-file-input');
  const attachedFile = window._siFile || ((fileInput && fileInput.files && fileInput.files[0]) ? fileInput.files[0] : null);
  const attachedFileName = attachedFile ? attachedFile.name : null;
  // Validation
  let valid = true;
  document.getElementById('im-name')?.classList.remove('error');
  document.getElementById('im-url')?.classList.remove('error');
  err.classList.remove('show');
  if (!name) { document.getElementById('im-name')?.classList.add('error'); valid = false; }
  if (!url && !text && !attachedFile) { document.getElementById('im-url')?.classList.add('error'); valid = false; }
  if (url && !/^https?:\/\//i.test(url)) { document.getElementById('im-url')?.classList.add('error'); valid = false; }
  if (!valid) { err.classList.add('show'); return; }
  // Disable button
  const btn = document.getElementById('im-submit-btn');
  if (btn) { btn.disabled = true; btn.textContent = 'Submitting…'; }
  // Upload the attached file (if any) to Supabase Storage so the PDF is actually SAVED.
  // Private bucket source-documents (PDF only, ≤25MB). The backend reads it and generates
  // a signed view URL, so an uploaded PDF becomes viewable in the dashboard as its source.
  let attachedFilePath = null;
  if (attachedFile) {
    const isPdf = /pdf/i.test(attachedFile.type) || /\.pdf$/i.test(attachedFile.name);
    if (!isPdf) {
      if (btn) { btn.disabled = false; btn.textContent = 'Submit →'; }
      err.textContent = 'Attached file must be a PDF (max 25MB). For other docs, paste a link instead.';
      err.classList.add('show');
      return;
    }
    try {
      if (btn) btn.textContent = 'Uploading PDF…';
      const safe = attachedFile.name.replace(/[^\w.\-]+/g, '_').slice(-80);
      const path = `uploads/${Date.now()}_${safe}`;
      // Raw fetch upload — the supabase-js storage client omits the apikey header with
      // the new publishable key format, which trips storage RLS. Raw fetch with the key works.
      const upResp = await fetch(`${SUPABASE_URL}/storage/v1/object/source-documents/${path}`, {
        method: 'POST',
        headers: { 'apikey': SUPABASE_ANON, 'Authorization': 'Bearer ' + SUPABASE_ANON,
                   'Content-Type': 'application/pdf' },  // no x-upsert: upsert needs an UPDATE policy; paths are unique so a plain INSERT is correct
        body: attachedFile
      });
      if (!upResp.ok) throw new Error('storage ' + upResp.status + ': ' + (await upResp.text()).slice(0,120));
      attachedFilePath = path;
      if (btn) btn.textContent = 'Submitting…';
    } catch (upe) {
      if (btn) { btn.disabled = false; btn.textContent = 'Submit →'; }
      err.textContent = `File upload failed: ${upe?.message || upe}. You can submit the link instead.`;
      err.classList.add('show');
      console.error('[submit intel] upload error:', upe);
      return;
    }
  }
  // Insert to submitted_intel
  try {
    const payload = {
      submitted_by:     name,
      source_url:       url || null,
      submitted_text:   text || null,
      status:           'new',
      raw_payload_json: {
        url, text, name,
        attached_file: attachedFileName || null,
        attached_file_path: attachedFilePath,
        detected_fields: window._siLastDetected || null,
        submitted_at: new Date().toISOString()
      }
    };
    const { error } = await _sb.from('submitted_intel').insert([payload]);
    if (error) throw error;
  } catch(e) {
    // Show the actual error so we know what's wrong
    if (btn) { btn.disabled = false; btn.textContent = 'Submit →'; }
    err.textContent = `Submission failed: ${e?.message || e}. The submitted_intel table may need to be created — see migrations/v33_submitted_intel.sql.`;
    err.classList.add('show');
    console.error('[submit intel] insert error:', e);
    return;
  }
  // Show success
  document.getElementById('im-form-body').style.display = 'none';
  document.getElementById('im-footer').style.display = 'none';
  const _succ = document.getElementById('im-success');
  if (_succ) {
    let fc = document.getElementById('im-success-file');
    if (!fc) { fc = document.createElement('div'); fc.id = 'im-success-file'; fc.style.cssText = 'margin-top:8px;font-size:12px;font-weight:600'; _succ.appendChild(fc); }
    fc.textContent = attachedFilePath ? ('📎 PDF saved to library: ' + (attachedFileName||'file')) : '';
    fc.style.color = '#15803d';
  }
  _succ.classList.add('show');
  // Invalidate review panel cache so next open shows fresh data
  _siLoaded = false;
  // Auto-close after 3s
  setTimeout(() => {
    closeIntelModal();
    if (btn) { btn.disabled = false; btn.textContent = 'Submit →'; }
    ['im-url','im-text','im-name'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    });
    // Reset file attachment state
    _siResetFileAttachment();
  }, 3000);
}
// ── Submit Intel — File attachment helpers ────────────────────────────────────
window._siLastDetected = null;

function triggerDocAttach() {
  // Open the intel modal first (if not already open), then trigger file pick
  if (!document.getElementById('intel-modal-overlay')?.classList.contains('open')) {
    openIntelModal();
    setTimeout(() => document.getElementById('si-file-input')?.click(), 120);
  } else {
    document.getElementById('si-file-input')?.click();
  }
}

function _siResetFileAttachment() {
  const fileInput = document.getElementById('si-file-input');
  if (fileInput) fileInput.value = '';
  const dropInner = document.querySelector('#si-drop-zone .si-drop-inner');
  if (dropInner) dropInner.style.display = '';
  const zone = document.getElementById('si-file-zone');
  if (zone) { zone.innerHTML = ''; zone.style.display = 'none'; }
  const det = document.getElementById('si-detected-fields');
  if (det) { det.style.display = 'none'; det.innerHTML = ''; }
  const q = document.getElementById('si-questions');
  if (q) { q.style.display = 'none'; q.innerHTML = ''; }
  window._siLastDetected = null;
  window._siFile = null;
}

function siHandleFileSelected(evt) {
  const file = evt.target.files[0];
  if (!file) return;
  _siShowFileInZone(file);
  _siReadFile(file);
}

function _siShowFileInZone(file) {
  window._siFile = file;  // shared ref — drag-drop does NOT populate the file input, so the
                          // submit handler must read this (fixes dropped PDFs not being uploaded)
  const dropInner = document.querySelector('#si-drop-zone .si-drop-inner');
  if (dropInner) dropInner.style.display = 'none';
  const zone = document.getElementById('si-file-zone');
  if (zone) { zone.innerHTML = `📎 <strong>${file.name}</strong> <span style="color:#94a3b8;font-size:11px">(${(file.size/1024).toFixed(1)} KB)</span> <span style="color:#6366f1;cursor:pointer;font-size:11px" onclick="_siResetFileAttachment()">✕ remove</span>`; zone.style.display = ''; }
}

(function() {
  function initSIDrop() {
    const dropZone = document.getElementById('si-drop-zone');
    if (!dropZone) return;
    dropZone.addEventListener('dragover', function(e) { e.preventDefault(); dropZone.classList.add('si-drop-active'); });
    dropZone.addEventListener('dragleave', function() { dropZone.classList.remove('si-drop-active'); });
    dropZone.addEventListener('drop', function(e) {
      e.preventDefault();
      dropZone.classList.remove('si-drop-active');
      const file = e.dataTransfer.files[0];
      if (file) { _siShowFileInZone(file); _siReadFile(file); }
    });
  }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', initSIDrop); }
  else { initSIDrop(); }
  window._initSIDropOnOpen = initSIDrop;
})();

function _siReadFile(file) {
  const det = document.getElementById('si-detected-fields');
  const q   = document.getElementById('si-questions');
  // Text-readable types
  const isText = /text\/(plain|markdown|csv)|application\/json/.test(file.type) ||
                 /\.(txt|md|csv|json)$/i.test(file.name);
  if (isText) {
    if (det) { det.style.display = ''; det.innerHTML = '<em style="color:#64748b">Reading…</em>'; }
    const reader = new FileReader();
    reader.onload = e => {
      const content = e.target.result || '';
      const fields  = _siExtractIntelFields(content);
      window._siLastDetected = fields.detected;
      // Show detected
      if (det) {
        if (fields.detected.length) {
          det.style.display = '';
          det.innerHTML = '<strong style="color:#166534">Detected:</strong> ' +
            fields.detected.map(f => `<span style="background:#dcfce7;border-radius:3px;padding:1px 5px;margin:0 2px">${_esc(f)}</span>`).join(' ');
        } else {
          det.style.display = '';
          det.innerHTML = '<span style="color:#64748b">No structured fields auto-detected — add context in Comments above.</span>';
        }
      }
      // Show questions
      if (q && fields.questions.length) {
        q.style.display = '';
        q.innerHTML = '<strong style="color:#92400e">Questions for Kyle:</strong><ul style="margin:4px 0 0 16px;padding:0">' +
          fields.questions.map(qn => `<li>${_esc(qn)}</li>`).join('') + '</ul>';
      } else if (q) {
        q.style.display = 'none';
      }
    };
    reader.readAsText(file);
  } else {
    // Binary / PDF / docx
    window._siLastDetected = null;
    if (det) {
      det.style.display = '';
      const typeLabel = /pdf/i.test(file.name) ? 'PDF' :
                        /docx?/i.test(file.name) ? 'Word document' :
                        /xlsx?/i.test(file.name) ? 'Excel file' : 'File';
      det.innerHTML = `<span style="color:#64748b">${typeLabel} attached — ${/pdf/i.test(file.name)?'will be uploaded & saved to the source library, then read by the backend':'will be noted on submission'}. Add key points in Comments above.</span>`;
    }
    if (q) q.style.display = 'none';
  }
}

function _siExtractIntelFields(text) {
  const detected  = [];
  const questions = [];
  // Dollar amounts
  const dollars = text.match(/\$[\d,]+(?:\.\d+)?(?:\s*[BMK](?:illion|n)?)?/gi) || [];
  dollars.slice(0,3).forEach(d => detected.push(d.trim()));
  // Drug codes: 2-5 uppercase letters + digits (e.g. XPF-005, ABBV-701, SPY001)
  const drugCodes = text.match(/\b[A-Z]{2,5}[-‑]?\d{2,4}\b/g) || [];
  [...new Set(drugCodes)].slice(0,4).forEach(d => detected.push(d));
  // Company names: 2+ consecutive Title-Case words (rough heuristic, exclude common sentence starts)
  const coNames = text.match(/\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b/g) || [];
  const filtered = [...new Set(coNames)].filter(n =>
    !/^(The|This|These|There|Their|They|Phase|Study|Trial|Data|Drug|Results|Safety|Efficacy)\b/.test(n)
  );
  filtered.slice(0,4).forEach(n => detected.push(n));
  // Dates: YYYY, or Month YYYY, or M/D/YYYY
  const dates = text.match(/\b(?:20\d{2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+20\d{2}|\d{1,2}\/\d{1,2}\/20\d{2})\b/gi) || [];
  [...new Set(dates)].slice(0,2).forEach(d => detected.push(d));
  // Generate gap questions
  if (!dollars.length) questions.push('What is the deal or milestone value (if any)?');
  if (!dates.length)   questions.push('What is the effective or announcement date?');
  if (!drugCodes.length && detected.filter(d => /[A-Z]/.test(d)).length < 2)
    questions.push('Which specific drug or asset does this relate to?');
  return { detected: [...new Set(detected)].slice(0, 10), questions };
}

// ── Document Upload Modal ─────────────────────────────────────────────────────
// Populates entity dropdown, handles form, saves to source_documents via Supabase.

let _docEntitiesLoaded = false;

async function openDocUploadModal() {
  // Reset form
  ['doc-form-body','doc-footer'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = '';
  });
  document.getElementById('doc-success')?.classList.remove('show');
  document.getElementById('doc-err')?.classList.remove('show');
  ['doc-entity-id','doc-type','doc-title','doc-date','doc-venue',
   'doc-url','doc-findings','doc-tags','doc-authors'].forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.classList.remove('error'); }
  });
  const btn = document.getElementById('doc-submit-btn');
  if (btn) { btn.disabled = false; btn.textContent = 'Save Document →'; }

  // Reset file drop
  const fileInput = document.getElementById('doc-file');
  if (fileInput) fileInput.value = '';
  const dropLabel = document.getElementById('doc-filedrop-label');
  const dropName  = document.getElementById('doc-filedrop-name');
  if (dropLabel) dropLabel.style.display = '';
  if (dropName)  { dropName.style.display = 'none'; dropName.textContent = ''; }

  document.getElementById('doc-modal-overlay')?.classList.add('open');

  // Load entity dropdown once
  if (!_docEntitiesLoaded) {
    await _docLoadEntities();
  }
}

function closeDocUploadModal() {
  document.getElementById('doc-modal-overlay')?.classList.remove('open');
}

async function _docLoadEntities() {
  const sel = document.getElementById('doc-entity-id');
  if (!sel) return;
  sel.innerHTML = '<option value="">Loading…</option>';
  try {
    // Fetch drugs
    const { data: drugs, error: dErr } = await _sb
      .from('drugs')
      .select('id,name,stage')
      .order('name', { ascending: true })
      .limit(300);
    if (dErr) throw dErr;

    // Fetch companies
    const { data: companies, error: cErr } = await _sb
      .from('companies')
      .select('id,name')
      .order('name', { ascending: true })
      .limit(200);
    if (cErr) throw cErr;

    let html = '<option value="">Select drug or company…</option>';

    if (drugs && drugs.length) {
      html += '<optgroup label="── Drugs ──">';
      drugs.forEach(d => {
        const stage = d.stage ? ` (${d.stage})` : '';
        html += `<option value="${_escAttr(d.id)}" data-type="drug">${_escAttr(d.name)}${stage}</option>`;
      });
      html += '</optgroup>';
    }

    if (companies && companies.length) {
      html += '<optgroup label="── Companies ──">';
      companies.forEach(c => {
        html += `<option value="${_escAttr(c.id)}" data-type="company">${_escAttr(c.name)}</option>`;
      });
      html += '</optgroup>';
    }

    sel.innerHTML = html;
    _docEntitiesLoaded = true;
  } catch (e) {
    sel.innerHTML = '<option value="">Error loading — type entity ID manually</option>';
    console.error('[doc-upload] entity load error:', e);
  }
}

function _escAttr(s) {
  if (s == null) return '';
  return String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;');
}

function handleDocFileSelect(evt) {
  const file = evt.target.files[0];
  if (!file) return;
  const dropLabel = document.getElementById('doc-filedrop-label');
  const dropName  = document.getElementById('doc-filedrop-name');
  if (dropLabel) dropLabel.style.display = 'none';
  if (dropName)  { dropName.textContent = `${file.name} (${(file.size/1024).toFixed(1)} KB)`; dropName.style.display = ''; }
}

function handleDocFileDrop(evt) {
  evt.preventDefault();
  document.getElementById('doc-filedrop')?.classList.remove('dragover');
  const file = evt.dataTransfer.files[0];
  if (!file) return;
  const input = document.getElementById('doc-file');
  // Assign via DataTransfer so the input reflects the file
  const dt = new DataTransfer();
  dt.items.add(file);
  if (input) input.files = dt.files;
  handleDocFileSelect({ target: { files: [file] } });
}

async function submitDocUpload() {
  const entitySel  = document.getElementById('doc-entity-id');
  const entityId   = (entitySel?.value || '').trim();
  const entityType = entitySel?.options[entitySel.selectedIndex]?.dataset?.type || 'drug';
  const docType    = (document.getElementById('doc-type')?.value || '').trim();
  const title      = (document.getElementById('doc-title')?.value || '').trim();
  const dateVal    = (document.getElementById('doc-date')?.value || '').trim();
  const venue      = (document.getElementById('doc-venue')?.value || '').trim();
  const url        = (document.getElementById('doc-url')?.value || '').trim();
  const findingsRaw= (document.getElementById('doc-findings')?.value || '').trim();
  const tagsRaw    = (document.getElementById('doc-tags')?.value || '').trim();
  const authorsRaw = (document.getElementById('doc-authors')?.value || '').trim();

  const errEl = document.getElementById('doc-err');
  if (errEl) { errEl.classList.remove('show'); errEl.textContent = ''; }

  // Validation
  const missing = [];
  if (!entityId) missing.push('entity');
  if (!docType)  missing.push('document type');
  if (!title)    missing.push('title');
  if (missing.length) {
    if (errEl) {
      errEl.textContent = `Required: ${missing.join(', ')}.`;
      errEl.classList.add('show');
    }
    if (!entityId) entitySel?.classList.add('error');
    if (!docType)  document.getElementById('doc-type')?.classList.add('error');
    if (!title)    document.getElementById('doc-title')?.classList.add('error');
    return;
  }

  // Parse arrays
  const keyFindings = findingsRaw
    ? findingsRaw.split('\n').map(s => s.replace(/^[•\-\*]\s*/,'').trim()).filter(Boolean)
    : [];
  const relevanceTags = tagsRaw
    ? tagsRaw.split(',').map(s => s.trim()).filter(Boolean)
    : [];
  const authors = authorsRaw
    ? authorsRaw.split(',').map(s => s.trim()).filter(Boolean)
    : [];

  // Determine conference vs journal
  const isConference = ['conference_poster','investor_presentation','investor_day'].includes(docType);
  const conferenceName = isConference ? (venue || null) : null;
  const journalName    = isConference ? null : (venue || null);

  const payload = {
    entity_id:       entityId   || null,
    entity_type:     entityType || 'drug',
    document_type:   docType,
    title:           title,
    authors:         authors.length ? authors : null,
    publication_date: dateVal || null,
    conference_name: conferenceName,
    journal_name:    journalName,
    external_url:    url || null,
    key_findings:    keyFindings.length ? keyFindings : null,
    relevance_tags:  relevanceTags.length ? relevanceTags : null,
    uploaded_by:     'kyle',
    verified:        false,
  };

  const btn = document.getElementById('doc-submit-btn');
  if (btn) { btn.disabled = true; btn.textContent = 'Saving…'; }

  try {
    const resp = await fetch(
      'https://tghntyofptvfhmtchwcv.supabase.co/rest/v1/source_documents',
      {
        method: 'POST',
        headers: {
          'apikey':        SUPABASE_ANON,
          'Authorization': 'Bearer ' + SUPABASE_ANON,
          'Content-Type':  'application/json',
          'Prefer':        'return=representation',
        },
        body: JSON.stringify(payload),
      }
    );
    if (!resp.ok) {
      const detail = await resp.text();
      throw new Error(`HTTP ${resp.status}: ${detail}`);
    }
    const saved = await resp.json();
    console.log('[doc-upload] saved:', saved);

    // Show success
    document.getElementById('doc-form-body').style.display = 'none';
    document.getElementById('doc-footer').style.display = 'none';
    document.getElementById('doc-success')?.classList.add('show');

    // Auto-close after 3.5s
    setTimeout(() => {
      closeDocUploadModal();
      if (btn) { btn.disabled = false; btn.textContent = 'Save Document →'; }
    }, 3500);

  } catch(e) {
    if (btn) { btn.disabled = false; btn.textContent = 'Save Document →'; }
    if (errEl) {
      errEl.textContent = `Save failed: ${e?.message || e}`;
      errEl.classList.add('show');
    }
    console.error('[doc-upload] insert error:', e);
  }
}
// ── End Document Upload Modal ─────────────────────────────────────────────────

// Legacy stubs — kept so any old references don't throw
function saveFromModal() { submitIntelNew(); }
function submitIntel()    { submitIntelNew(); }
function copyFromModal()  {}
function renderIntelSubmissions() {}
function deleteIntel()    {}
function clearIntelForm() {}
function copyIntelForClaude() {}
