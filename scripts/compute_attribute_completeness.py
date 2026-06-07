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
 # ---- DEPTH ATTRIBUTES (2026-06-07 aggregation rebuild) -----------------------
 ("cmc_profile","CMC / manufacturing profile","Molecule","manufacturing_profile",None,"satellite_rows",0,
  "Manufacturing & CMC complexity inferred from modality and product form — how hard the molecule is to make and supply.",
  "Bispecific IgG → high CMC complexity (dual-chain assembly)","Pharmaprojects — Drug Profiles","partial",
  "Modality→CMC complexity is derived; paid platforms rarely score makeability",19),
 ("genetic_validation","Target genetic validation","Molecule","target_genetics",None,"satellite_rows",0,
  "Human-genetics evidence that the target matters — loss-of-function constraint and disease association from Open Targets.",
  "TL1A (TNFSF15): IBD risk locus, genetically validated","Pharmaprojects — Drug Profiles","have",
  "Open Targets genetic constraint per target — free, foundational",19),
 ("pathway_context","Target pathway context","Molecule","target_pathways",None,"satellite_rows",0,
  "Which signalling pathways the target sits in — the biological neighbourhood that shapes combination and escape logic.",
  "IL-23p19 → JAK-STAT / Th17 differentiation pathway","Pharmaprojects — Drug Profiles","have",
  "Reactome pathway membership per target — free",19),
 ("financials","Company financials & runway","Strategic BD","company_financials",None,"satellite_rows",0,
  "The owning company's cash position, burn and runway — does the seller have leverage or a financing cliff?",
  "Spyre: ~$600M cash, ~8 quarters runway (SEC 10-Q)","Deals (Cortellis/BioSciDB)","partial",
  "Runway/market-cap from SEC filings for public owners; private owners opaque",85),
 ("literature","Peer-reviewed literature","Clinical","publications",None,"satellite_rows",1,
  "Published papers reporting on the asset — the independent evidence base behind the headlines.",
  "Tulisokibart NEJM ARTEMIS-UC primary publication","Trialtrove — Clinical Trials","partial",
  "Drug↔publication links via crossref/openalex; a resumable collection frontier",29),
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

# =============================================================================
# MULTI-SOURCE RESOLVER  (2026-06-07 aggregation rebuild)
# -----------------------------------------------------------------------------
# An attribute is "filled" for a drug if the REAL data exists in the PRIMARY
# source OR ANY authoritative fallback. Each builder below returns a set of
# drug_ids, and every credited id traces back to an actual stored row — no
# fabrication, no inference. The per-attribute filled set is the union.
# =============================================================================

def _drug_col_set(drugs, col):
    """drug_ids where drugs.<col> is non-empty."""
    return {d["id"] for d in drugs if is_filled(d.get(col))}

def _sat_set(table):
    """drug_ids that have >=1 row in <table>."""
    rows = fetch_all(f"{table}?select=drug_id")
    return {r["drug_id"] for r in rows if r.get("drug_id")}

def _sat_nonnull_set(table, col, flt=None):
    """drug_ids with >=1 row in <table> where <col> is non-empty (optional filter)."""
    q = f"{table}?select=drug_id,{col}"
    if flt: q += f"&{flt}"
    return {r["drug_id"] for r in fetch_all(q) if r.get("drug_id") and is_filled(r.get(col))}

def load_context():
    """Fetch every authoritative source ONCE, build reusable drug_id sets/maps."""
    cols = sorted({c for (_,_,_,t,c,_,_,_,_,_,_,_,_) in D if t=="drugs" and c})
    drugs = fetch_all(f"drugs?select=id,name,stage,company_id,{','.join(cols)}")
    print(f"drugs: {len(drugs)}")
    C = {"drugs": drugs}
    col = lambda c: _drug_col_set(drugs, c)

    # ---- simple satellite presence sets
    sat_tables = ["drug_pk_parameters","drug_pd_parameters","drug_biomarkers","drug_safety",
        "fda_adverse_events","drug_patents","drug_exclusivity","patent_families","fda_approvals",
        "eu_approvals","geographic_approvals","ownership_rights","asset_transfer_history",
        "payer_pricing","payer_tpp_criteria","peak_revenue_estimates","non_responder_profiles",
        "manufacturing_profile","drug_targets","drug_indications","drug_labels",
        # preserved (default-resolver) satellite attributes:
        "trial_facts","clinical_evidence_items","molecule_intelligence","catalysts",
        "drug_competitive_scores","regulatory_designations","drug_sources"]
    S = {}
    for t in sat_tables:
        try: S[t] = _sat_set(t)
        except Exception as e: print(f"  WARN {t}: {e}"); S[t] = set()
    C["S"] = S; C["col"] = col

    # ---- non-null satellite-column sets (for fallbacks)
    C["mfg_route"]   = _sat_nonnull_set("manufacturing_profile","route")
    C["mfg_dose"]    = _sat_nonnull_set("manufacturing_profile","dosage_form") | C["mfg_route"]
    C["labels_dose"] = _sat_nonnull_set("drug_labels","dosage_forms")
    C["labels_safety"] = (_sat_nonnull_set("drug_labels","boxed_warning")
                          | _sat_nonnull_set("drug_labels","adverse_reactions_text"))
    C["pk_route"]    = _sat_nonnull_set("drug_pk_parameters","dose_route")
    C["pk_halflife"] = _sat_nonnull_set("drug_pk_parameters","half_life_hours")
    C["cei_pk"]      = _sat_nonnull_set("clinical_evidence_items","pk_data")
    C["cei_pd"]      = _sat_nonnull_set("clinical_evidence_items","pd_data")
    C["cei_bio"]     = _sat_nonnull_set("clinical_evidence_items","biomarker_data")
    C["cei_eff"]     = _sat_nonnull_set("clinical_evidence_items","efficacy_data")
    C["tr_results"]  = _sat_nonnull_set("trial_results","has_results","has_results=is.true")
    C["tr_sec_ep"]   = _sat_nonnull_set("trial_results","secondary_endpoints")
    C["tf_prim_ep"]  = _sat_nonnull_set("trial_facts","primary_endpoints")
    C["fda_date"]    = _sat_nonnull_set("fda_approvals","approval_date")
    C["fda_brand"]   = _sat_nonnull_set("fda_approvals","brand_name")
    C["eu_date"]     = _sat_nonnull_set("eu_approvals","eu_auth_date")
    C["eu_brand"]    = _sat_nonnull_set("eu_approvals","brand_name")

    # ---- target-keyed sets (genetics / pathways) via drug_targets.target_id
    dt = fetch_all("drug_targets?select=drug_id,target_id")
    drug2targets = {}
    for r in dt:
        if r.get("drug_id") and r.get("target_id"):
            drug2targets.setdefault(r["drug_id"], set()).add(r["target_id"])
    gen_tids  = {r["target_id"] for r in fetch_all("target_genetics?select=target_id") if r.get("target_id")}
    path_tids = {r["target_id"] for r in fetch_all("target_pathways?select=target_id") if r.get("target_id")}
    C["genetic_drugs"] = {d for d,ts in drug2targets.items() if ts & gen_tids}
    C["pathway_drugs"] = {d for d,ts in drug2targets.items() if ts & path_tids}

    # ---- company-keyed financials via drugs.company_id
    fin_cids = {r["company_id"] for r in fetch_all("company_financials?select=company_id") if r.get("company_id")}
    C["financ_drugs"] = {d["id"] for d in drugs if d.get("company_id") in fin_cids}

    # ---- literature: drug->publication REPORTED_IN edges (subject_id = drug)
    lit = fetch_all("entity_edges?select=subject_id&predicate=eq.REPORTED_IN&subject_type=eq.drug&object_type=eq.publication")
    C["lit_drugs"] = {r["subject_id"] for r in lit if r.get("subject_id")}

    # ---- why_matters extras: news mentions + strategic_insights entity_refs
    news_drugs = set()
    for r in fetch_all("news_articles?select=matched_drug_ids"):
        for did in (r.get("matched_drug_ids") or []):
            if did: news_drugs.add(did)
    si_drugs = set()
    for r in fetch_all("strategic_insights?select=entity_refs"):
        er = r.get("entity_refs") or {}
        if isinstance(er, dict):
            for did in (er.get("drugs") or []):
                if did: si_drugs.add(did)
    C["news_drugs"] = news_drugs; C["si_drugs"] = si_drugs

    # ---- PATIENT layer: drug -> indications, indication -> patient intel
    di = fetch_all("drug_indications?select=drug_id,indication_id")
    drug2inds = {}
    for r in di:
        if r.get("drug_id") and r.get("indication_id"):
            drug2inds.setdefault(r["drug_id"], set()).add(r["indication_id"])
    # resolved-id set of indications carrying patient unmet-need intelligence (v133)
    punc_inds = {r["indication_id"] for r in
                 fetch_all("patient_unmet_need_competition?select=indication_id") if r.get("indication_id")}
    # map indication_patient_intelligence (keyed by display name) -> indication_id
    inds = fetch_all("indications?select=id,name,abbreviation")
    name2id, abbr2id = {}, {}
    for i in inds:
        if i.get("name"): name2id[i["name"].strip().lower()] = i["id"]
        if i.get("abbreviation"): abbr2id[i["abbreviation"].strip().lower()] = i["id"]
    def map_ipi_name(nm):
        n = (nm or "").strip().lower()
        if n in name2id: return name2id[n]
        if n in abbr2id: return abbr2id[n]
        # substring: a known indication name fully contained in the ipi label
        for full, iid in name2id.items():
            if len(full) >= 4 and full in n: return iid
        # parenthetical abbreviation e.g. "... (EoE)" / "COPD (Type-2)"
        import re
        for tok in re.findall(r"[A-Za-z][A-Za-z0-9\-]{1,12}", nm or ""):
            if tok.lower() in abbr2id: return abbr2id[tok.lower()]
        return None
    ipi = fetch_all("indication_patient_intelligence?select=indication_name,unmet_need_narrative,"
                    "unmet_need_score,why_it_matters,simplified_label,treatment_cascade,biologic_nonresponse_rate")
    ipi_unmet, ipi_benefit, ipi_cascade, ipi_nonresp, ipi_any = set(), set(), set(), set(), set()
    mapped = 0
    for r in ipi:
        iid = map_ipi_name(r.get("indication_name"))
        if not iid: continue
        mapped += 1; ipi_any.add(iid)
        if is_filled(r.get("unmet_need_narrative")) or is_filled(r.get("unmet_need_score")): ipi_unmet.add(iid)
        if is_filled(r.get("why_it_matters")) or is_filled(r.get("simplified_label")): ipi_benefit.add(iid)
        if is_filled(r.get("treatment_cascade")): ipi_cascade.add(iid)
        if is_filled(r.get("biologic_nonresponse_rate")): ipi_nonresp.add(iid)
    print(f"  patient: {len(punc_inds)} punc indications, {mapped}/{len(ipi)} ipi rows name-mapped")
    # any indication with patient intel (punc OR mapped ipi)
    intel_inds = punc_inds | ipi_any | ipi_unmet
    def drugs_with_ind_set(ind_set):
        return {d for d, dinds in drug2inds.items() if dinds & ind_set}
    C["patient_intel_drugs"] = drugs_with_ind_set(intel_inds)
    C["unmet_drugs"]   = drugs_with_ind_set(punc_inds | ipi_unmet)
    C["benefit_drugs"] = drugs_with_ind_set(ipi_benefit)
    C["cascade_drugs"] = drugs_with_ind_set(ipi_cascade)
    C["nonresp_ind_drugs"] = drugs_with_ind_set(ipi_nonresp)
    return C

def build_resolvers(C):
    """attribute_key -> set(drug_id) filled, aggregated across all real sources."""
    col, S = C["col"], C["S"]
    R = {
      # ---- CLINICAL / molecule depth fallbacks
      "dosing":        lambda: col("dosing_schedule") | C["labels_dose"] | C["mfg_dose"] | C["pk_route"],
      "route":         lambda: col("route") | C["mfg_route"] | C["pk_route"],
      "half_life":     lambda: col("half_life_note") | C["pk_halflife"],
      "pk_parameters": lambda: S["drug_pk_parameters"] | C["cei_pk"],
      "pd_parameters": lambda: S["drug_pd_parameters"] | C["cei_pd"],
      "biomarkers":    lambda: S["drug_biomarkers"] | C["cei_bio"],
      "safety_label":  lambda: S["drug_safety"] | C["labels_safety"] | S["fda_adverse_events"],
      "key_data":      lambda: col("key_data") | C["cei_eff"] | C["tr_results"],
      "endpoints":     lambda: col("endpoints") | C["tf_prim_ep"] | C["tr_sec_ep"],
      # ---- IP
      "patents":        lambda: S["drug_patents"] | S["drug_exclusivity"],
      "patent_families":lambda: S["patent_families"] | S["drug_patents"] | S["drug_exclusivity"],
      # ---- REGULATORY
      "approval_date": lambda: col("approval_date") | C["fda_date"] | C["eu_date"],
      "brand_name":    lambda: col("brand_name") | C["fda_brand"] | C["eu_brand"],
      "geo_approvals": lambda: S["geographic_approvals"] | S["eu_approvals"] | S["fda_approvals"],
      # ---- STRATEGIC BD / PAYER
      "ownership":   lambda: col("ownership_status") | S["ownership_rights"] | S["asset_transfer_history"],
      "revenue":     lambda: col("annual_revenue") | S["payer_pricing"],
      "payer_tpp":   lambda: S["payer_tpp_criteria"] | S["payer_pricing"],
      "peak_revenue":lambda: S["peak_revenue_estimates"],
      "why_matters": lambda: col("why_it_matters") | C["news_drugs"] | C["si_drugs"],
      # ---- PATIENT (indication-derived intelligence)
      "unmet_need":         lambda: col("unmet_need_addressed") | C["unmet_drugs"],
      "patient_population": lambda: col("patient_population") | C["patient_intel_drugs"],
      "patient_benefit":    lambda: col("patient_benefit_simplified") | C["benefit_drugs"],
      "treatment_line":     lambda: col("treatment_line") | C["cascade_drugs"],
      "nonresponder":       lambda: S["non_responder_profiles"] | C["nonresp_ind_drugs"],
      # ---- DEPTH attributes
      "cmc_profile":       lambda: S["manufacturing_profile"],
      "genetic_validation":lambda: C["genetic_drugs"],
      "pathway_context":   lambda: C["pathway_drugs"],
      "financials":        lambda: C["financ_drugs"],
      "literature":        lambda: C["lit_drugs"],
    }
    return {k: f() for k, f in R.items()}

def compute():
    C = load_context()
    drugs = C["drugs"]; S = C["S"]; col = C["col"]
    resolved = build_resolvers(C)

    # build the filled-set for EVERY attribute: custom resolver, else default
    # (default preserves prior behaviour: satellite presence OR drugs.column non-null)
    filled_sets = {}
    for (k,_,_,t,c,ck,_,*_r) in D:
        if k in resolved:
            filled_sets[k] = resolved[k]
        elif ck == "satellite_rows":
            filled_sets[k] = S.get(t) if t in S else _sat_set(t)
        else:  # column_nonnull
            filled_sets[k] = col(c)

    out = []
    for d in drugs:
        sr = stage_rank(d.get("stage"))
        for (k,_,dm,t,c,ck,ph,*_rest) in D:
            out.append(dict(drug_id=d["id"], drug_name=d.get("name"), stage=d.get("stage"),
                            stage_rank=sr, attribute_key=k, domain=dm,
                            expected=(sr is not None and sr >= ph),
                            filled=(d["id"] in filled_sets[k])))
    for i in range(0, len(out), 1000):
        req("attribute_completeness?on_conflict=drug_id,attribute_key", "POST",
            out[i:i+1000], prefer="resolution=merge-duplicates,return=minimal")
    print(f"attribute_completeness: {len(out)} rows upserted")
    rollup(out)
    return out

from collections import defaultdict
def rollup(out, label="AFTER"):
    """Green% = filled where expected (stage_rank known). Print overall + per-domain."""
    dom = defaultdict(lambda: [0,0]); tot = [0,0]
    for r in out:
        if r["expected"] and r["stage_rank"] is not None:
            dom[r["domain"]][0] += 1; tot[0] += 1
            if r["filled"]: dom[r["domain"]][1] += 1; tot[1] += 1
    print(f"\n==== {label} green % ====")
    for dm in sorted(dom):
        e,f = dom[dm]; print(f"  {dm:13s} {f:4d}/{e:<4d} = {100*f/e:5.1f}%")
    print(f"  {'OVERALL':13s} {tot[1]:4d}/{tot[0]:<4d} = {100*tot[1]/max(tot[0],1):5.1f}%")
    return tot, dom

def read_current():
    """Snapshot existing attribute_completeness for BEFORE/AFTER comparison."""
    return fetch_all("attribute_completeness?select=drug_id,attribute_key,domain,expected,filled,stage_rank")

if __name__ == "__main__":
    # ---- BEFORE snapshot (existing rows)
    before_rows = read_current()
    print(f"BEFORE snapshot: {len(before_rows)} existing attribute_completeness rows")
    btot, bdom = rollup(before_rows, label="BEFORE") if before_rows else ((0,1), {})
    before_attr = defaultdict(lambda: [0,0])
    for r in before_rows:
        if r.get("expected") and r.get("stage_rank") is not None:
            before_attr[r["attribute_key"]][0]+=1
            if r["filled"]: before_attr[r["attribute_key"]][1]+=1

    # ---- seed dictionary + recompute
    seed_dictionary()
    out = compute()

    # ---- per-attribute movement (expected-only green %)
    after_attr = defaultdict(lambda: [0,0])
    for r in out:
        if r["expected"] and r["stage_rank"] is not None:
            after_attr[r["attribute_key"]][0]+=1
            if r["filled"]: after_attr[r["attribute_key"]][1]+=1
    print("\n==== per-attribute green % (BEFORE -> AFTER, expected-only) ====")
    moves=[]
    keys = sorted(set(list(before_attr)+list(after_attr)))
    for k in keys:
        be,bf = before_attr.get(k,[0,0]); ae,af = after_attr.get(k,[0,0])
        bp = 100*bf/be if be else None; ap = 100*af/ae if ae else None
        delta = (ap or 0)-(bp if bp is not None else 0)
        moves.append((delta,k,bp,ap,af,ae))
    for delta,k,bp,ap,af,ae in sorted(moves, key=lambda x:-x[0]):
        bs = f"{bp:5.1f}%" if bp is not None else "  new "
        print(f"  {k:20s} {bs} -> {ap:5.1f}%  ({af}/{ae})  Δ{delta:+5.1f}")

    # ---- idempotency check: recompute, confirm stable overall green
    out2 = compute()
    t1,_ = rollup(out, label="AFTER (run1)")
    t2,_ = rollup(out2, label="AFTER (run2)")
    g1 = 100*t1[1]/max(t1[0],1); g2 = 100*t2[1]/max(t2[0],1)
    print(f"\nIDEMPOTENT: run1 {g1:.2f}% vs run2 {g2:.2f}% -> "
          f"{'STABLE' if abs(g1-g2)<1e-9 and len(out)==len(out2) else 'DRIFT!'}")
