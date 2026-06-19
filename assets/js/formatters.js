// FORMATTERS — grid cell renderers + sort comparators (extracted from app.js, Phase 4 split 2026-06-19).
// Classic script: defines globals (sf, ef, rf-style formatters, phaseSort/dateSort) used by initGrids in app.js.
// Loaded before app.js; depends on the gridjs global.

// ── FORMATTERS ────────────────────────────────────────────────────
// Stage badge formatter
function sf(cell) {
 const s = String(cell);
 let c = 'sb-pre';
 if (s.includes('Approved')) c = 'sb-approved';
 else if (s.includes('Phase 3')||s.includes('Ph3')) c = 'sb-ph3';
 else if (s.includes('Phase 2')||s.includes('Ph2')||s.includes('2b')) c = 'sb-ph2';
 else if (s.includes('Phase 1')||s.includes('Ph1')||s.includes('1a')) c = 'sb-ph1';
 return gridjs.html(`<span class="sb ${c}">${s}</span>`);
}

// Phase rank for custom sort — handles both "Ph3" and "Phase 3" variants
// Clinical development order: Approved(0) → Ph3(10) → Ph2b(20) → Ph2(30) → Ph1/2(35) → Ph1(40) → Pre-Ph1(50) → Pre-IND(60) → Preclinical(70)
function phaseRank(s) {
 const v = String(s).trim();
 if (v.includes('Approved')) return 0;
 if (v.includes('Ph3') || v.includes('Phase 3')) return 10;
 if (v.includes('Ph2b') || v.includes('2b') || v.includes('Phase 2b')) return 20;
 if (v.includes('Ph2') || v.includes('Phase 2')) return 30;
 if (v.includes('Ph1→Ph2') || v.includes('Ph1 / Ph2') || v.includes('Ph1/2') || v.includes('Phase 1/2')) return 35;
 if (v.includes('Ph1') || v.includes('Phase 1')) return 40;
 if (v.includes('Pre-P1') || v.includes('Pre-Ph1') || v.includes('Pre Ph1') || v.includes('Pre P1')) return 50;
 if (v.includes('Pre-IND') || v.includes('PreIND') || v.includes('Pre IND')) return 60;
 if (v.includes('Preclinical') || v.includes('Patent stage')) return 70;
 return 80;
}
const phaseSort = { enabled: true, compare: (a, b) => phaseRank(a) - phaseRank(b) };

// Date sort for Primary Completion column
function parseDateKey(str) {
 if (!str) return 999999;
 const s = String(str).trim();
 if (/^(tbd|—|-|n\/a)$/i.test(s)) return 999999;
 const months = {Jan:1,Feb:2,Mar:3,Apr:4,May:5,Jun:6,Jul:7,Aug:8,Sep:9,Oct:10,Nov:11,Dec:12};
 // "Nov 2026"
 const mY = s.match(/^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})$/);
 if (mY) return parseInt(mY[2]) * 100 + months[mY[1]];
 // "Q1 2026"
 const qY = s.match(/^Q([1-4])\s+(\d{4})$/);
 if (qY) return parseInt(qY[2]) * 100 + [1,4,7,10][parseInt(qY[1])-1];
 // "H1 2026"
 const hY = s.match(/^H([12])\s+(\d{4})$/);
 if (hY) return parseInt(hY[2]) * 100 + (parseInt(hY[1]) === 1 ? 1 : 7);
 // "2027" bare year
 const yOnly = s.match(/^(\d{4})$/);
 if (yOnly) return parseInt(yOnly[1]) * 100;
 return 999999;
}
const dateSort = { enabled: true, compare: (a, b) => parseDateKey(a) - parseDateKey(b) };

// Readout program link formatter (uses hidden 7th column for URL)
function readoutProgFmt(cell, row) {
 const url = row.cells[6] && row.cells[6].data;
 if (url) return gridjs.html(`<a class="ct-link" href="${url}" target="_blank" rel="noopener">${cell}</a>`);
 return cell;
}

// Deal partner link formatter (uses hidden 10th column for news URL)
function dealPartnerFmt(cell, row) {
 const url = row.cells[9] && row.cells[9].data;
 if (url) return gridjs.html(`<a class="deal-link" href="${url}" target="_blank" rel="noopener">${cell}</a>`);
 return cell;
}

// Readout program formatter for clean calendar (URL now at cells[4] after dropping Category+Indication)
function readoutProgFmtClean(cell, row) {
 const url = row.cells[4] && row.cells[4].data;
 if (url) return gridjs.html(`<a class="ct-link" href="${url}" target="_blank" rel="noopener">${cell}</a>`);
 return cell;
}

// Drop columns by index from a data array (used to strip redundant columns at render time)
function dropCols(data, indices) {
 return data.map(row => row.filter((_,i) => !indices.includes(i)));
}

// Merge bispecific pipeline + monotherapy into one competitive landscape table
// Pipe cols : [Company, Asset, Format, Stage, Indication, Partner, Upfront, Total, Estimand, _news]
// Mono cols : [Company, Asset, Stage, Indication, Estimand, Notes]
// Output : [Company, Asset, Format, Stage, Partner/Deal, Estimand, Notes]
function mergeLandscape(pipeData, monoData) {
 const pRows = pipeData.map(r => {
 const partner = (r[5] && r[5] !== '—') ? r[5] : '';
 const upfront = (r[6] && r[6] !== '—') ? r[6] : '';
 const total = (r[7] && r[7] !== '—') ? r[7] : '';
 let deal = '—';
 if (partner || upfront || total) {
 const terms = [upfront, total].filter(Boolean).join(' / ');
 deal = [partner, terms].filter(Boolean).join(' · ');
 }
 return [r[0], r[1], r[2], r[3], deal, r[8], ''];
 });
 const mRows = monoData.map(r => [r[0], r[1], 'Monotherapy', r[2], '—', r[4], r[5]]);
 return [...pRows, ...mRows];
}

// Estimand badge formatter
function ef(cell) {
 const s = String(cell);
 let c = 'eb-tbd-pre';
 let label = s;
 if (s === 'Composite') { c = 'eb-composite'; }
 else if (s === 'Treatment Policy' || s === 'Treatment Policy (TBD)') { c = 'eb-policy'; }
 else if (s === 'Hypothetical') { c = 'eb-hypothetical'; }
 else if (s === 'While on Treatment') { c = 'eb-while'; }
 else if (s === 'Ph1 Safety Only') { c = 'eb-tbd-ph1'; }
 else if (s === 'Design TBD') { c = 'eb-tbd-pre'; }
 return gridjs.html(`<span class="eb ${c}">${label}</span>`);
}
