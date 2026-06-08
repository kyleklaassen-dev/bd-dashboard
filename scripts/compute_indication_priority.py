#!/usr/bin/env python3
"""compute_indication_priority.py — refresh the home Indication Priority card.
Merges the curated Ailux strategic overlay (fit/window/biology/regulatory/stratifiability,
which program targets it) with LIVE patient data from patient_unmet_need_competition
(unmet need, competition→whitespace, patient counts), recomputes the composite, ranks,
and upserts into indication_priority_scores (the table the card live-reads).
Free, deterministic, idempotent — safe to schedule."""
import os,json,math,urllib.request,datetime
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SB="https://tghntyofptvfhmtchwcv.supabase.co/rest/v1"
KEY=open(os.path.join(ROOT,".supabase_service_key")).read().strip()
H={"apikey":KEY,"Authorization":"Bearer "+KEY,"Content-Type":"application/json"}
def get(q):
    r=urllib.request.Request(SB+"/"+q);[r.add_header(k,v) for k,v in H.items()]
    return json.load(urllib.request.urlopen(r))
def upsert(table,rows,conflict):
    req=urllib.request.Request(SB+f"/{table}?on_conflict={conflict}",data=json.dumps(rows).encode(),
        headers={**H,"Prefer":"resolution=merge-duplicates,return=minimal"},method="POST")
    urllib.request.urlopen(req)

# curated Ailux strategic overlay (judgment that isn't auto-derivable) — patient-data fields filled live
CURATED=[
 {"id":"gmg","name":"Generalized Myasthenia Gravis","fit":10,"wind":8,"bio":10,"reg":10,"strat":10,"progs":["alx005"],"live":"gmg",
  "rationale":"FcRn mechanism fully validated (3+ approved). MG-ADL is FDA gold standard. AChR Ab+ ~85% — perfectly stratifiable.","tooltip":"Validated biology + FDA endpoint + perfect biomarker; bispecific niche open."},
 {"id":"cidp","name":"CIDP","fit":10,"wind":9,"bio":8,"reg":7,"strat":6,"progs":["alx005"],"live":"cidp",
  "rationale":"Highest window urgency. Efgartigimod mono approved but bispecific whitespace unchallenged.","tooltip":"No FcRn bispecific in CIDP Ph2; INCAT established."},
 {"id":"cd","name":"Crohn's Disease","fit":10,"wind":7,"bio":9,"reg":8,"strat":7,"progs":["alx001"],"live":"cd",
  "rationale":"Worst SoC remission. TL1A ARTEMIS-CD Ph2b validates mechanism; SPY072 sets the window.","tooltip":"TL1A validated; CDAI+endoscopic endpoints established."},
 {"id":"uc","name":"Ulcerative Colitis","fit":10,"wind":6,"bio":10,"reg":10,"strat":8,"progs":["alx001"],"live":"uc",
  "rationale":"Endoscopic remission is FDA gold standard. TL1A validated by ARTEMIS Ph2b; window compressing.","tooltip":"duvakitug Ph3 H2 2026 compresses window."},
 {"id":"mg","name":"Myasthenia Gravis (Broad)","fit":8,"wind":8,"bio":9,"reg":9,"strat":8,"progs":["alx005"],"live":"gmg",
  "rationale":"Bispecific whitespace mirrors gMG; AChR Ab stratification established.","tooltip":"Refractory subgroup addressable by next-gen bispecific."},
 {"id":"sjogrens","name":"Sjogren's Syndrome","fit":9,"wind":9,"bio":5,"reg":4,"strat":3,"progs":["alx002"],"live":"sjogrens",
  "rationale":"Highest window + whitespace, but biology contested, endpoint not FDA-established, no validated biomarker.","tooltip":"No Ph2+ CD19 bispecific; ESSDAI vs ESSPRI unresolved."},
 {"id":"tl1a","name":"TL1A Mechanism Area","fit":10,"wind":5,"bio":9,"reg":9,"strat":7,"progs":["alx001"],"live":"ibd",
  "rationale":"TL1A FDA-validated; window penalized as monospecifics enter Ph3 and define positioning.","tooltip":"Monospecific Ph3 readouts compress the differentiation window."},
]
pic={r["indication_id"]:r for r in get("patient_unmet_need_competition?select=indication_id,unmet_need_score,competitor_count,whitespace_score,patient_count_us,market_size_usd_bn&limit=200")}
def wspace_from_comp(c):  # more competitors -> less whitespace, on a 1-10 scale
    if c is None: return 7
    return max(1,min(10,round(10-1.6*math.log1p(c))))
rows=[]
for c in CURATED:
    p=pic.get(c["live"],{})
    unmet=round(p.get("unmet_need_score") or 8)
    wspace=wspace_from_comp(p.get("competitor_count"))
    comp=(unmet*0.20)+(c["fit"]*0.25)+(wspace*0.15)+(c["wind"]*0.20)+(c["bio"]*0.10)+(c["reg"]*0.05)+(c["strat"]*0.05)
    rows.append(dict(indication_id=c["id"],indication_name=c["name"],
        patient_count_us=p.get("patient_count_us"),market_size_usd_bn=p.get("market_size_usd_bn"),
        unmet_need_score=unmet,biologic_failure_rate_pct=p.get("biologic_failure_rate_pct"),
        remission_rate_soc_pct=p.get("remission_rate_soc_pct"),
        ailux_fit_score=c["fit"],competitive_white_space=wspace,
        window_urgency_score=c["wind"],biology_validation_score=c["bio"],
        regulatory_pathway_clarity=c["reg"],patient_stratifiability=c["strat"],
        composite_score=round(comp,2),priority_rationale=c["rationale"],tooltip_why=c["tooltip"],
        alx_programs=c["progs"],last_computed=datetime.datetime.utcnow().isoformat()+"Z"))
rows.sort(key=lambda r:-r["composite_score"])
for i,r in enumerate(rows,1): r["indication_priority_rank"]=i
upsert("indication_priority_scores",rows,"indication_id")
print("indication_priority_scores upserted:",len(rows))
for r in rows: print(f"  #{r['indication_priority_rank']} {r['indication_name'][:26]:28} comp={r['composite_score']} unmet={r['unmet_need_score']} wspace={r['competitive_white_space']} pts={r['patient_count_us']}")
