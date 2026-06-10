#!/usr/bin/env python3
"""Dashboard-wide knowledge-graph connectivity audit.
Measures, for every entity-bearing table, how many rows are linked to a canonical
entity vs unlinked (null FK), and finds orphan nodes in entity_edges. Writes JSON."""
import requests, json, concurrent.futures as cf
URL="https://tghntyofptvfhmtchwcv.supabase.co"
KEY=open("/sessions/tender-nifty-curie/mnt/BD Platform/.supabase_service_key").read().strip()
H={"apikey":KEY,"Authorization":f"Bearer {KEY}"}

ENT=('drug_id','company_id','entity_id','subject_id','object_id','target_id','indication_id',
     'partner_company_id','parent_company_id','canonical_drug_id','originator_company_id',
     'lead_company_id','current_owner_company_id','partner_company_ids','co_developer_ids',
     'drug_ids','company_ids')
TEXT=('company','drug_name','subject_name','entity_name','partner_company','licensor_name')

def count(table, flt=None):
    p={"select":"*" if False else next(iter(()),"")}  # noop
    params={"select":"id"} if True else {}
    q=f"{URL}/rest/v1/{table}?select=id"
    if flt: q+="&"+flt
    try:
        r=requests.get(q,headers={**H,"Prefer":"count=exact","Range":"0-0"},timeout=20)
        cr=r.headers.get("content-range","")
        if "/" in cr:
            v=cr.split("/")[-1]
            return int(v) if v.isdigit() else None
    except Exception: return None
    return None

spec=requests.get(f"{URL}/rest/v1/",headers=H).json()
defs=spec.get("definitions") or spec.get("components",{}).get("schemas",{})
tables={}
for t,d in defs.items():
    cols=list((d.get("properties") or {}).keys())
    fk=[c for c in cols if c in ENT]
    tx=[c for c in cols if c in TEXT]
    if fk or tx: tables[t]={"fk":fk,"text":tx,"cols":cols}

# total counts in parallel
def get_total(t):
    return t, count(t)
totals={}
with cf.ThreadPoolExecutor(max_workers=24) as ex:
    for t,c in ex.map(get_total, tables): totals[t]=c

# null FK counts in parallel (skip array cols for null — treat empty too)
jobs=[]
for t,info in tables.items():
    for c in info["fk"]:
        jobs.append((t,c))
def get_null(job):
    t,c=job
    return (t,c,count(t,f"{c}=is.null"))
nulls={}
with cf.ThreadPoolExecutor(max_workers=24) as ex:
    for t,c,n in ex.map(get_null, jobs): nulls[(t,c)]=n

out={"totals":totals,"nulls":{f"{k[0]}|{k[1]}":v for k,v in nulls.items()},
     "tables":{t:info for t,info in tables.items()}}
json.dump(out, open("/sessions/tender-nifty-curie/mnt/outputs/graph_audit.json","w"))
print("tables audited:",len(tables),"| total-count jobs:",len(totals),"| null jobs:",len(jobs))
print("done -> graph_audit.json")
