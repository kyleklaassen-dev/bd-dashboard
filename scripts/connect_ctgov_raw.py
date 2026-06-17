import sys,uuid,datetime; sys.path.insert(0,"src")
from meridian.database import client as c
NOW=datetime.datetime.utcnow().isoformat()
NS=uuid.UUID("a7f1c0de-1111-4222-8333-0a1b2c3d4e5f")
uid=lambda k:str(uuid.uuid5(NS,k))
raw=c.select_all("api_raw_documents",{"select":"entity_key,drug_id,payload","source":"eq.ctgov"})
edges={}; whystopped=[]; ref_trials=0
for d in raw:
    nct=d["entity_key"]; did=d.get("drug_id"); p=d.get("payload") or {}
    ps=p.get("protocolSection") or {}
    ws=(ps.get("statusModule") or {}).get("whyStopped")
    if ws: whystopped.append((nct,ws[:480]))
    refs=(ps.get("referencesModule") or {}).get("references") or []
    pmids=[r.get("pmid") for r in refs if r.get("pmid")]
    if pmids and did:
        ref_trials+=1
        for pm in pmids:
            k=f"REFSTUDIES_{did}_{pm}"
            edges[uid(k)]=dict(id=uid(k),subject_type="drug",subject_id=did,predicate="STUDIES",
                object_type="publication",object_id=pm,source_url=f"https://clinicaltrials.gov/study/{nct}",
                basis_text=f"CT.gov reference on {nct}",confidence_level="inferred",
                generation_method="deterministic",notes="ctgov_refs_v152",status="active",
                created_by="connect_raw",created_at=NOW,updated_at=NOW)
ev=list(edges.values()); ins=0
for i in range(0,len(ev),500):
    code,b,_=c.insert("entity_edges",ev[i:i+500],on_conflict="subject_id,predicate,object_id",ignore_duplicates=True,return_rep=False)
    if code>=400: print("edge err",code,str(b)[:140]); break
    ins+=len(ev[i:i+500])
for nct,ws in whystopped:
    c.update("trials",f"id=eq.{nct}",{"why_stopped":ws})
print(f"ref edges processed: {ins} (from {ref_trials} trials) | whyStopped updated: {len(whystopped)}")
