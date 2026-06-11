#!/usr/bin/env node
/* ask_eval.js — routing regression guard for the Meridian Ask search bar.
 * Mirrors the pure routing predicates in meridian_ask.html. If you change those
 * regexes, update here and run `node scripts/ask_eval.js` — it catches misroutes
 * (e.g. the "patient count" → drug-count bug) before users hit them.
 */
const norm = s => (s||"").toLowerCase().replace(/[×x+]/g," ").replace(/[^a-z0-9 ]/g," ").replace(/\s+/g," ").trim();

// ── predicates copied from meridian_ask.html (keep in sync) ──
const COUNT_SUBJ=/\b(drugs?|molecules?|assets?|programs?|compounds?|antibod\w*|bispecifics?|mabs?|companies|company|players?)\b/;
const TRIAL_ATTR=/\bpatients?\b|enroll|enrol(ment|led)|participants|sample\s*size|\bn\s*=|cohort size|patient count|cell count|blood count/;
function intent(q){
  const s=q.toLowerCase();
  if(/\b(how many|number of|count of)\b/.test(s) && COUNT_SUBJ.test(s) && !TRIAL_ATTR.test(s)) return 'count';
  if(/\blead(ing|er|ers)?\b|who('?s| is)?\s+(winning|ahead|leading|furthest)|furthest along|top (company|player|drug)/.test(s)) return 'leader';
  if(/completion date|read ?out|reports? out|when (will|does|is|do|are)|data (due|expected|coming)|topline|timeline|catalyst|pdufa|approval date|expected|milestone|finish|next (event|catalyst)/.test(s)) return 'timeline';
  if(/remission|efficac|response rate|endpoint|\bresults?\b|how effective|safety|tolerab|\bpk\b|pharmacokinet|half-?life|\bdata\b|\bada\b|immunogenic/.test(s)) return 'efficacy';
  if(/competitive landscape|competitor|compet(es|ing|ition)|who else|other (drugs|programs|assets|players)|\blandscape\b|players|\bfield\b|rivals/.test(s)) return 'landscape';
  return null;
}
const CMP=/\bvs\.?\b|\bversus\b|\bcompare\b|\bcompared\b|difference between|head.?to.?head|side.?by.?side/i;
const RANKQ=/\brank\b|\branked\b|best.?in.?class|\bhighest\b|\blowest\b|sort(ed)? by|order(ed)? by|leaderboard|which .*\b(highest|best|most|lowest|strongest)\b/i;
const REASON=/most important|what (should|matters|to consider)|\bconsider\b|\bshould i\b|\bwhy\b|how (do|would|should|can)|\bworst\b|\brisk\b|advantage|weakness|strength|\bstrateg|implication|trade-?off|too crowded|worth|recommend|\bbeat\b|differentiat/i;
function ttlDays(q){ const s=q.toLowerCase();
  if(/\b(latest|current|now|today|this week|recent|recently|upcoming|right now|so far|to date|newest|as of)\b/.test(s)) return 5;
  if(/\b(price|stock|market cap|valuation|deal|acquisition|partnership|catalyst|read ?out|pdufa|\bwhen\b|date|timeline|status|leading|furthest|pipeline|enroll)\b/.test(s)) return 14;
  if(/\b(mechanism|moa|target|what is|how does|structure|modality|binding|class)\b/.test(s)) return 180;
  return 30; }

// ── assertions ──
const cases = [
  // the bug that started this: "patient count" must NOT be the drug-count handler
  ["What was the patient count of phase 2 tulisokibart study?", () => intent("What was the patient count of phase 2 tulisokibart study?") !== 'count'],
  ["how many drugs target TL1A?", () => intent("how many drugs target TL1A?") === 'count'],
  ["how many patients enrolled in tulisokibart phase 2?", () => intent("how many patients enrolled in tulisokibart phase 2?") !== 'count'],
  ["number of companies in TSLP", () => intent("number of companies in TSLP") === 'count'],
  ["when does spy002 read out?", () => intent("when does spy002 read out?") === 'timeline'],
  ["when do we expect afimkibart data?", () => intent("when do we expect afimkibart data?") === 'timeline'],
  ["duvakitug efficacy", () => intent("duvakitug efficacy") === 'efficacy'],
  ["tulisokibart safety profile", () => intent("tulisokibart safety profile") === 'efficacy'],
  ["who is leading in TL1A?", () => intent("who is leading in TL1A?") === 'leader'],
  ["competitive landscape for duvakitug", () => intent("competitive landscape for duvakitug") === 'landscape'],
  ["other drugs targeting FcRn", () => intent("other drugs targeting FcRn") === 'landscape'],
  ["tulisokibart vs duvakitug", () => CMP.test("tulisokibart vs duvakitug")],
  ["compare spyre and roche TL1A assets", () => CMP.test("compare spyre and roche TL1A assets")],
  ["rank TL1A drugs by remission", () => RANKQ.test("rank TL1A drugs by remission")],
  ["which TL1A drug has the highest remission?", () => RANKQ.test("which TL1A drug has the highest remission?")],
  ["what matters most for a preclinical bispecific", () => REASON.test("what matters most for a preclinical bispecific")],
  ["is TL1A too crowded to enter?", () => REASON.test("is TL1A too crowded to enter?")],
  ["bare entity should not be reasoning", () => !REASON.test("tulisokibart")],
  ["TTL: 'latest TL1A deals' is short", () => ttlDays("latest TL1A deals") === 5],
  ["TTL: 'tulisokibart mechanism of action' is long", () => ttlDays("tulisokibart mechanism of action") === 180],
  ["TTL: 'duvakitug PDUFA date' is medium", () => ttlDays("duvakitug PDUFA date") === 14],
];
let pass=0;
for(const [name,fn] of cases){ let ok=false; try{ ok=!!fn(); }catch(e){} console.log((ok?"PASS":"FAIL")+"  "+name); pass+=ok; }
console.log(`\n${pass}/${cases.length} passed`);
process.exit(pass===cases.length?0:1);
