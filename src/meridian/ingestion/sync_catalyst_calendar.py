#!/usr/bin/env python3
"""sync_catalyst_calendar.py — keep the BD Today card fresh WITHOUT LLM.
Promotes upcoming, source-verified ct.gov catalysts from `catalysts` into
`catalyst_calendar` (the table the dashboard BD Today widget reads). Free,
deterministic, idempotent. Run on a schedule (meridian-free-ingest.yml)."""
import os,json,urllib.request,datetime
ROOT=os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SB="https://tghntyofptvfhmtchwcv.supabase.co/rest/v1"
KEY=open(os.path.join(ROOT,".supabase_service_key")).read().strip()
H={"apikey":KEY,"Authorization":"Bearer "+KEY,"Content-Type":"application/json"}
def req(path,method="GET",body=None,prefer=None):
    r=urllib.request.Request(SB+"/"+path,method=method,data=(json.dumps(body).encode() if body is not None else None))
    [r.add_header(k,v) for k,v in H.items()]
    if prefer:r.add_header("Prefer",prefer)
    with urllib.request.urlopen(r) as x:
        t=x.read().decode();return json.loads(t) if t else None
def get_all(path):
    out=[];off=0
    while True:
        r=urllib.request.Request(SB+"/"+path+("&" if "?" in path else "?")+f"limit=1000&offset={off}");[r.add_header(k,v) for k,v in H.items()]
        b=json.load(urllib.request.urlopen(r));out+=b
        if len(b)<1000:return out
        off+=1000
import re as _re
def _direct_url(label, fallback):
    m=_re.search(r"(NCT\d{8})", label or "")
    return ("https://clinicaltrials.gov/study/"+m.group(1)) if m else fallback
today=datetime.date.today().isoformat()
horizon=(datetime.date.today()+datetime.timedelta(days=120)).isoformat()
# upcoming source-verified ct.gov catalysts in the next 120 days
cats=get_all(f"catalysts?select=drug_id,company_id,label,sort_date,catalyst_date,catalyst_type,significance,source_url&confidence_source=eq.ct_gov&resolved=eq.false&sort_date=gte.{today}&sort_date=lte.{horizon}&order=sort_date.asc")
existing=get_all("catalyst_calendar?select=drug_id,event_name")
seen={(r.get("drug_id"),(r.get("event_name") or "").strip()) for r in existing}
rows=[]
for c in cats:
    name=(c.get("label") or "").strip()
    key=(c.get("drug_id"),name)
    if not name or key in seen: continue
    seen.add(key)
    nl=name.lower()
    et=("pdufa_date" if "pdufa" in nl else "regulatory_decision" if any(k in nl for k in ("approval","nda submission","bla","decision")) else "trial_readout")
    sig={"high":"P1","medium":"P2"}.get((c.get("significance") or "").lower(),"watch")
    rows.append(dict(drug_id=c.get("drug_id"),company_id=c.get("company_id"),event_name=name,
        expected_date=c.get("sort_date") or c.get("catalyst_date"),event_type=et,
        strategic_significance=sig,source_url=_direct_url(name, c.get("source_url")),
        confidence="verified",is_past=False,description="Auto-synced from ct.gov catalyst feed"))
import sys
dry="--apply" not in sys.argv
print(f"upcoming ct.gov catalysts={len(cats)} | new to add={len(rows)} | dry_run={dry}")
if rows and not dry:
    for i in range(0,len(rows),200):
        req("catalyst_calendar","POST",rows[i:i+200],prefer="return=minimal")
    print(f"inserted {len(rows)} into catalyst_calendar")
