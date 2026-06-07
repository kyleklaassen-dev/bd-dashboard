#!/usr/bin/env python3
"""
compute_attribute_completeness.py — Kyle voice-memo build (2026-06-07).

Seeds/updates `data_dictionary` (the attribute taxonomy, 100Q 8-domain frame,
with plain-English descriptions + Citeline benchmark mapping) and computes
`attribute_completeness` (per drug x attribute: filled / phase-expected).

Phase-conditional: a preclinical asset missing Phase-3 attributes is NOT a gap.
Idempotent: upserts both tables. Run: python3 scripts/compute_attribute_completeness.py
"""
import json, os, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SB = "https://tghntyofptvfhmtchwcv.supabase.co/rest/v1"
KEY = open(os.path.join(ROOT, ".supabase_service_key")).read().strip()

def req(path, method="GET", body=None, prefer=None, rng=None):
    r = urllib.request.Request(f"{SB}/{path}", method=method,
        data=json.dumps(body).encode() if body is not None else None)
    r.add_header("apikey", KEY); r.add_header("Authorization", f"Bearer {KEY}")
    r.add_header("Content-Type", "application/json")
    if prefer: r.add_header("Prefer", prefer)
    if rng: r.add_header("Range", rng); r.add_header("Range-Unit", "items")
    with urllib.request.urlopen(r) as resp:
        t = resp.read().decode()
        return json.loads(t) if t else None

def fetch_all(path_qs):
    out, off, page = [], 0, 1000
    while True:
        chunk = req(f"{path_qs}", rng=f"{off}-{off+page-1}")
        out += chunk
        if len(chunk) < page: return out
        off += page

# ---- stage rank: 0 Preclinical | 1 Ph1 | 2 Ph2 | 3 Ph3 | 4 Filed | 5 Approved | None excluded
def stage_rank(stage):
    if not stage: return None
    s = stage.strip().lower()
    if s in ("discontinued", "terminated"): return None
    if s.startswith("approved") or s == "marketed": return 5
    if "nda" in s or "bla" in s or "filed" in s or "under_review" in s: return 4
    if "2/3" in s or s.startswith("phase 3"): return 3
    if "1/2" in s or s.startswith("phase 2"): return 2
    if s.startswith("phase 1"): return 1
    if "preclinical" in s or "ind" in s or "discovery" in s: return 0
    return None

EMPTYISH = {"", "—", "-", "n/a", "na", "unknown", "tbd", "none", "null"}
def is_filled(v):
    if v is None: return False
    if isinstance(v, bool): return True
    if isinstance(v, (int, float)): return True
    if isinstance(v, (list, dict)): return len(v) > 0
    return str(v).strip().lower() not in EMPTYISH

# ---- THE DICTIONARY ----------------------------------------------------------
# (key, name, domain, table, column|None, check, phase, plain_description,
#  example, citeline_module, benchmark_status, benchmark_note, sort)
MERIDIAN_ONLY = "Meridian-only"
D = [
 # MOLECULE
 ("mechanism","Mechanism of action","Molecule","drugs","mechanism","column_nonnull",0,
  "How the molecule works — what it binds and what that does in the body.",
  "Tulisokibart: anti-TL1A monoclonal antibody","Pharmaprojects — Drug Profiles","have",None,10),
 ("mechanism_detail","Mechanism detail","Molecule","drugs","mechanism_detail","column_nonnull",1,
  "The deeper scientific story: epitope, signaling consequences, format rationale.",
  "XmAb942: XTEND-Fc half-life extension, t1/2 74 days","Pharmaprojects — Drug Profiles","have",None,11),
 ("target_ontology","Molecular target(s)","Molecule","drug_targets",None,"satellite_rows",0,
  "The specific protein(s) the drug acts on, in our structured target ontology.",
  "ALX001 → TL1A + IL-23p19","Pharmaprojects — Drug Profiles","have",None,12),
 ("modality","Modality","Molecule","drugs","modality","column_nonnull",0,
  "What kind of medicine it is: antibody, bispecific, small molecule, cell therapy…",
  "Bispecific antibody","Pharmaprojects — Drug Profiles","have",None,13),
 ("drug_format","Molecular format","Molecule","drugs","drug_format","column_nonnull",0,
  "The engineering format of the molecule (IgG subclass, Fc modifications, valency).",
  "IgG1 with YTE Fc mutation","Pharmaprojects — Drug Profiles","partial",
  "Citeline rarely has format depth either; ours is curated where disclosed",14),
 ("binding_domain","Binding domain","Molecule","drugs","binding_domain","column_nonnull",1,
  "Which part of the target the drug binds.",
  "TL1A trimer interface","Pharmaprojects — Drug Profiles","partial",None,15),
 ("half_life","Half-life","Molecule","drugs","half_life_note","column_nonnull",1,
  "How long the drug stays active in the body — drives dosing convenience.",
  "XmAb942: ~74 days → quarterly dosing possible",MERIDIAN_ONLY,"have",
  "Paid platforms list PK trials, not a curated half-life comparison",16),
 ("pk_parameters","PK parameters","Molecule","drug_pk_parameters",None,"satellite_rows",1,
  "Pharmacokinetics: how the body absorbs, distributes and clears the drug.",
  "Cmax, AUC, clearance from Phase 1","Trialtrove — Clinical Trials","partial",
  "Only 14 drugs covered today — a known collection gap",17),
 ("pd_parameters","PD parameters","Molecule","drug_pd_parameters",None,"satellite_rows",2,
  "Pharmacodynamics: what the drug measurably does to its target in patients.",
  "Free TL1A suppression %","Trialtrove — Clinical Trials","partial",
  "4 drugs covered — early build",18),
 ("molecule_profile","Molecule characterization","Molecule","molecule_intelligence",None,"satellite_rows",0,
  "Our structured molecule-level intelligence record.",
  "99 molecules characterized",MERIDIAN_ONLY,"have",None,19),
 # CLINICAL
 ("stage","Development stage","Clinical","drugs","stage","column_nonnull",0,
  "Where the drug is in development, preclinical through approved.",
  "Phase 3","Pharmaprojects — Pipeline","have",None,20),
 ("trials","Registered trials","Clinical","trial_facts",None,"satellite_rows",1,
  "The clinical trials testing this drug, from registries (CT.gov and others).",
  "1,245 trials linked","Trialtrove — Clinical Trials","have",
  "Ex-China registries; CDE/NMPA assets are a known gap",21),
 ("endpoints","Trial endpoints","Clinical","drugs","endpoints","column_nonnull",2,
  "What the trials measure to declare success.",
  "Clinical remission at week 12 (modified Mayo)","Trialtrove — Clinical Trials","partial",None,22),
 ("key_data","Key clinical data","Clinical","drugs","key_data","column_nonnull",2,
  "Headline efficacy/safety results reported so far.",
  "ARTEMIS-UC: 26.5% remission vs 1.5% placebo","Trialtrove — Clinical Trials","partial",
  "We capture headlines; Citeline has fuller result records",23),
 ("biomarkers","Biomarker strategy","Clinical","drug_biomarkers",None,"satellite_rows",2,
  "Biomarkers used to select or stratify patients.",
  "Tulisokibart: TL1A genetic-signature CDx","Trialtrove — Clinical Trials","partial",
  "5 drugs covered — priority collection gap",24),
 ("dosing","Dosing schedule","Clinical","drugs","dosing_schedule","column_nonnull",1,
  "How often and how the drug is given.",
  "Q4W subcutaneous maintenance","Pharmaprojects — Drug Profiles","partial",None,25),
 ("route","Route of administration","Clinical","drugs","route","column_nonnull",1,
  "IV, subcutaneous, oral… — a key convenience differentiator.",
  "Subcutaneous","Pharmaprojects — Drug Profiles","have",None,26),
 ("phase3_data","Phase 3 outcome","Clinical","drugs","positive_phase3_data","column_nonnull",3,
  "Whether pivotal data read out positive.",
  "Risankizumab: positive (FORTIFY)","Biomedtracker — Events","have",None,27),
 ("safety_label","Safety profile (label)","Clinical","drug_safety",None,"satellite_rows",5,
  "Label-level safety: boxed warnings and major risks.",
  "29 black-box records from FDA labels","Pharmaprojects — Regulatory","have",None,28),
 # PATIENT
 ("indications","Indications","Patient","drug_indications",None,"satellite_rows",0,
  "Which diseases the drug is being developed or approved for.",
  "Ulcerative colitis; Crohn's disease","Pharmaprojects — Pipeline","have",None,30),
 ("patient_population","Patient population","Patient","drugs","patient_population","column_nonnull",2,
  "Who exactly the drug is for — line of therapy, severity, subgroups.",
  "Moderate-to-severe UC, biologic-experienced","Epidemiology (Citeline/Evaluate)","partial",
  "We have descriptors; paid platforms add quantified epidemiology",31),
 ("unmet_need","Unmet need addressed","Patient","drugs","unmet_need_addressed","column_nonnull",0,
  "The patient problem this molecule exists to solve.",
  "~40% of UC patients fail all current biologics",MERIDIAN_ONLY,"have",
  "Patient-anchored framing is Meridian's North Star — paid platforms don't do this",32),
 ("patient_benefit","Patient benefit (plain language)","Patient","drugs","patient_benefit_simplified","column_nonnull",2,
  "What the drug means for a patient, in plain words.",
  "One injection every 3 months instead of every 2 weeks",MERIDIAN_ONLY,"have",None,33),
 ("nonresponder","Non-responder biology","Patient","non_responder_profiles",None,"satellite_rows",3,
  "Why some patients don't respond — escape pathways and what that implies.",
  "OSM/OSMR escape in anti-TNF failures",MERIDIAN_ONLY,"partial",
  "7 drugs covered — strategically critical for ALX001 Phase 1 design",34),
 ("treatment_line","Treatment line","Patient","drugs","treatment_line","column_nonnull",3,
  "Where the drug sits in the treatment sequence.",
  "Post-anti-TNF, pre-JAK","Epidemiology (Citeline/Evaluate)","partial",None,35),
 # PAYER
 ("payer_tpp","Payer target product profile","Payer","payer_tpp_criteria",None,"satellite_rows",4,
  "What payers would need to see to cover and prefer this drug.",
  "Step therapy after 2 biologics; remission delta ≥8%",MERIDIAN_ONLY,"partial",
  "1 drug covered — earliest layer; paid platforms also weak here",40),
 ("revenue","Annual revenue","Payer","drugs","annual_revenue","column_nonnull",5,
  "Actual sales for approved drugs.",
  "Skyrizi: $11.7B (2024)","Evaluate — Forecasts & Revenue","partial",
  "We have actuals for majors; Evaluate adds consensus forecasts",41),
 ("peak_revenue","Peak revenue estimate","Payer","peak_revenue_estimates",None,"satellite_rows",4,
  "Estimated commercial ceiling, with assumptions shown.",
  "Tulisokibart: ~$2.5B peak (penetration-based)","Evaluate — Forecasts & Revenue","partial",
  "Sparse; forecasts are Evaluate's core strength — our honest 20%",42),
 ("payer_pricing","US pricing & public spend","Payer","payer_pricing",None,"satellite_rows",5,
  "What the US public payer actually spends — Medicare Part B/D totals and Medicaid acquisition cost.",
  "Skyrizi: Medicare Part D total spending by year (CMS)","Evaluate — Forecasts & Revenue","partial",
  "Actual US public spend; Evaluate adds global consensus forecasts",43),
 # COMPETITIVE
 ("competitive_scores","Competitive positioning","Competitive","drug_competitive_scores",None,"satellite_rows",0,
  "How this drug stacks up against competitors in each context, scored.",
  "350 scored drug-context pairs",MERIDIAN_ONLY,"have",
  "CLASS×RELEVANCE scoring vs Ailux is proprietary",50),
 ("overlap","Ailux overlap class","Competitive","drugs","overlap","column_nonnull",0,
  "Direct / Adjacent / Same-Space classification vs the Ailux pipeline.",
  "Tulisokibart: Direct (TL1A)",MERIDIAN_ONLY,"have",None,51),
 ("differentiation","Differentiation thesis","Competitive","drugs","differentiation_thesis","column_nonnull",2,
  "What would make this drug win or lose against its competition.",
  "Bispecific = two mechanisms, one molecule, one price",MERIDIAN_ONLY,"have",None,52),
 ("vs_ailux","Read vs Ailux","Competitive","drugs","vs_ailux","column_nonnull",0,
  "What this asset specifically means for Ailux strategy.",
  "Validates TL1A but monospecific — window for ALX001",MERIDIAN_ONLY,"have",None,53),
 ("catalysts","Upcoming catalysts","Competitive","catalysts",None,"satellite_rows",1,
  "Dated future events that will move the landscape: readouts, decisions, filings.",
  "ABBV-701 Phase 1 readout — Oct 2026","Biomedtracker — Catalysts","have",None,54),
 # REGULATORY
 ("approval_date","Approval date","Regulatory","drugs","approval_date","column_nonnull",5,
  "When the drug was first approved.",
  "Skyrizi: 2019-04-23","Pharmaprojects — Regulatory","have",None,60),
 ("brand_name","Brand name","Regulatory","drugs","brand_name","column_nonnull",5,
  "The marketed name.",
  "Skyrizi","Pharmaprojects — Regulatory","have",None,61),
 ("designations","Regulatory designations","Regulatory","regulatory_designations",None,"satellite_rows",2,
  "Orphan, Fast Track, Breakthrough — signals of regulatory advantage.",
  "148 orphan designations from FDA OOPD","Pharmaprojects — Regulatory","have",None,62),
 ("label","FDA label","Regulatory","drug_labels",None,"satellite_rows",5,
  "The official prescribing information.",
  "46 DailyMed SPL labels linked","Pharmaprojects — Regulatory","have",None,63),
 ("faers","Post-market adverse events","Regulatory","fda_adverse_events",None,"satellite_rows",5,
  "Real-world safety reports after approval (FAERS).",
  "469 FAERS burden records","Pharmaprojects — Regulatory","have",None,64),
 ("geo_approvals","Geographic approvals","Regulatory","geographic_approvals",None,"satellite_rows",5,
  "Where in the world the drug is approved, with dates.",
  "Bimekizumab: EU-first (−788 days vs US)","Pharmaprojects — Regulatory","have",None,65),
 # IP
 ("patents","Patent families","IP","drug_patents",None,"satellite_rows",3,
  "The patents protecting (or blocking) the asset — freedom-to-operate.",
  "Prometheus anti-TL1A family, expiry 2040-45","IP (Cortellis)","partial",
  "8 drugs drug-level; 224 company-level patents; full sweep resumable",70),
 ("exclusivity","Regulatory exclusivity","IP","drug_exclusivity",None,"satellite_rows",5,
  "Non-patent monopoly: biologic 12-year exclusivity, orphan exclusivity.",
  "119 Purple Book / Orange Book records","IP (Cortellis)","have",None,71),
 ("patent_families","Patent families (global)","IP","patent_families",None,"satellite_rows",3,
  "Every jurisdiction a patent is filed in — the INPADOC-style family, each member referenceable.",
  "Prometheus TL1A patent: 27 members across 16 countries (SureChEMBL)","IP (Cortellis)","partial",
  "Keyless SureChEMBL family graph; seeded from tracked patents",72),
 # STRATEGIC BD
 ("ownership","Ownership & originator","Strategic BD","drugs","ownership_status","column_nonnull",0,
  "Who owns the asset now, who invented it, and the chain between.",
  "Cizutamig: EpimAb → Vignette → Candid → UCB","Deals (Cortellis/BioSciDB)","have",None,80),
 ("ailux_angle","Ailux BD angle","Strategic BD","drugs","ailux_angle","column_nonnull",0,
  "The specific BD play this asset creates or forecloses for Ailux.",
  "AbbVie untouchable until ABBV-701 readout",MERIDIAN_ONLY,"have",
  "The whole point: no paid platform does Ailux-relative strategy",81),
 ("why_matters","Why it matters","Strategic BD","drugs","why_it_matters","column_nonnull",0,
  "One sentence on why this asset is worth tracking at all.",
  "First bispecific validation of the TL1A+IL-23 thesis",MERIDIAN_ONLY,"have",None,82),
 ("summary","Drug summary","Strategic BD","drugs","drug_summary","column_nonnull",0,
  "The narrative card a reader sees first.",
  "Plain-English asset story","Pharmaprojects — Drug Profiles","have",None,83),
 ("provenance","Source documentation","Strategic BD","drug_sources",None,"satellite_rows",0,
  "Every fact traceable to its source — Meridian's primary governance rule.",
  "2,700+ cited claims",MERIDIAN_ONLY,"have",
  "Per-claim provenance is rare even in paid platforms",84),
 ("source_url","Primary source URL","Strategic BD","drugs","source_url","column_nonnull",0,
  "The single most authoritative link for the asset.",
  "CT.gov or company IR page","Pharmaprojects — Drug Profiles","have",None,85),
]

def seed_dictionary():
    rows = [dict(attribute_key=k, display_name=n, domain=dm, source_table=t,
                 source_column=c, check_type=ck, phase_expected=ph,
                 plain_description=pd, example_text=ex, citeline_module=cm,
                 benchmark_status=bs, benchmark_note=bn, sort_order=so)
            for (k,n,dm,t,c,ck,ph,pd,ex,cm,bs,bn,so) in D]
    req("data_dictionary?on_conflict=attribute_key", "POST", rows,
        prefer="resolution=merge-duplicates,return=minimal")
    print(f"data_dictionary: {len(rows)} attributes upserted")

def compute():
    cols = sorted({c for (_,_,_,t,c,_,_,_,_,_,_,_,_) in D if t=="drugs" and c})
    drugs = fetch_all(f"drugs?select=id,name,stage,{','.join(cols)}")
    print(f"drugs: {len(drugs)}")
    sat = {}
    for t in sorted({t for (_,_,_,t,_,ck,_,_,_,_,_,_,_) in D if ck=="satellite_rows"}):
        ids = fetch_all(f"{t}?select=drug_id")
        sat[t] = {r["drug_id"] for r in ids if r.get("drug_id")}
        print(f"  {t}: {len(sat[t])} drugs")
    out = []
    for d in drugs:
        sr = stage_rank(d.get("stage"))
        for (k,_,dm,t,c,ck,ph,*_rest) in [(x[0],x[1],x[2],x[3],x[4],x[5],x[6]) for x in D]:
            filled = (d["id"] in sat[t]) if ck=="satellite_rows" else is_filled(d.get(c))
            out.append(dict(drug_id=d["id"], drug_name=d.get("name"), stage=d.get("stage"),
                            stage_rank=sr, attribute_key=k, domain=dm,
                            expected=(sr is not None and sr >= ph), filled=filled))
    for i in range(0, len(out), 1000):
        req("attribute_completeness?on_conflict=drug_id,attribute_key", "POST",
            out[i:i+1000], prefer="resolution=merge-duplicates,return=minimal")
    print(f"attribute_completeness: {len(out)} rows upserted")
    # quick rollup print
    from collections import defaultdict
    agg = defaultdict(lambda: [0,0])
    for r in out:
        if r["expected"] and r["stage_rank"] is not None:
            agg[(r["domain"], r["stage_rank"])][0] += 1
            if r["filled"]: agg[(r["domain"], r["stage_rank"])][1] += 1
    for (dm, srk) in sorted(agg):
        e, f = agg[(dm, srk)]
        print(f"  {dm:13s} rank{srk}: {f}/{e} = {100*f/e:.0f}%")

if __name__ == "__main__":
    seed_dictionary()
    compute()
