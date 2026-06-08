#!/usr/bin/env python3
"""Idempotent dedup of exact-duplicate entity_edges triples (subject,predicate,object).
Keeps the earliest row per triple. Ran 2026-06-07: COMPETES_WITH 1346->852 (-494 dupes)."""
import os,urllib.request,json
SB="https://tghntyofptvfhmtchwcv.supabase.co/rest/v1"; SVC=open(".supabase_service_key").read().strip()
H={"apikey":SVC,"Authorization":"Bearer "+SVC,"Content-Type":"application/json"}
PRED=os.environ.get("PRED","COMPETES_WITH")
rows=[];off=0
while True:
    h={**H,"Range":f"{off}-{off+999}"}
    req=urllib.request.Request(SB+f"/entity_edges?select=id,subject_id,object_id&predicate=eq.{PRED}&order=created_at.asc",headers=h)
    b=json.load(urllib.request.urlopen(req)); rows+=b
    if len(b)<1000: break
    off+=1000
seen={};dupes=[]
for r in rows:
    k=(r["subject_id"],r["object_id"])
    dupes.append(r["id"]) if k in seen else seen.__setitem__(k,r["id"])
for i in range(0,len(dupes),100):
    url=SB+"/entity_edges?id=in.("+",".join(dupes[i:i+100])+")"
    urllib.request.urlopen(urllib.request.Request(url,headers={**H,"Prefer":"return=minimal"},method="DELETE"))
print(f"{PRED}: {len(rows)} -> {len(seen)} unique ({len(dupes)} dupes removed)")
