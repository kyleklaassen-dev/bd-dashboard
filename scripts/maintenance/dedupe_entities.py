#!/usr/bin/env python3
"""Full dedupe merge: collapse duplicate company/drug rows onto a single canonical.
Introspects the OpenAPI schema for every FK column, repoints all references
old->new (conflict-safe), field-merges nulls, deletes the loser. Dry-run default."""
import sys, requests, concurrent.futures as cf
URL="https://tghntyofptvfhmtchwcv.supabase.co"
KEY=open("/sessions/tender-nifty-curie/mnt/BD Platform/.supabase_service_key").read().strip()
H={"apikey":KEY,"Authorization":f"Bearer {KEY}","Content-Type":"application/json"}
APPLY="--apply" in sys.argv

# (loser -> winner). Winner = higher-reference / canonical (INN preferred).
COMPANY_MERGES=[("johnsonjohnson","jnj"),("bausch","bauschhealth"),("morphicholding","morphic"),
 ("protagonisttherapeutics","protagonist"),("spyretherapeutics","spyre"),("ucbpharma","ucb"),
 ("vertexpharmaceuticals","vertex"),("wuxi_biologics","wuxi-bio")]
DRUG_MERGES=[("bsi-045b","bosakitug"),("miv-cel","kyv-101")]

COMPANY_REF=("company_id","parent_company_id","partner_company_id","lead_company_id",
 "current_owner_company_id","originator_company_id")
DRUG_REF=("drug_id","canonical_drug_id")
GENERIC_REF=("entity_id","subject_id","object_id")  # hold either type; safe to repoint by exact value
ARRAY_REF=("partner_company_ids","company_ids","co_developer_ids","drug_ids")

spec=requests.get(f"{URL}/rest/v1/",headers=H).json()
defs=spec.get("definitions") or spec.get("components",{}).get("schemas",{})
def cols_for(refset):
    out=[]
    for t,d in defs.items():
        for c in (d.get("properties") or {}):
            if c in refset: out.append((t,c))
    return out
company_cols=cols_for(COMPANY_REF); drug_cols=cols_for(DRUG_REF)
generic_cols=cols_for(GENERIC_REF); array_cols=cols_for(ARRAY_REF)

def patch_eq(table,col,old,new):
    r=requests.patch(f"{URL}/rest/v1/{table}?{col}=eq.{old}",headers={**H,"Prefer":"return=minimal"},json={col:new})
    if r.status_code in (200,204): return ("ok",0)
    if r.status_code==409:  # unique conflict -> winner already has the row; drop loser's
        d=requests.delete(f"{URL}/rest/v1/{table}?{col}=eq.{old}",headers={**H,"Prefer":"return=minimal"})
        return ("dedup-del" if d.status_code in (200,204) else f"delfail{d.status_code}",0)
    return (f"err{r.status_code}:{r.text[:80]}",0)

def count_eq(table,col,val):
    r=requests.get(f"{URL}/rest/v1/{table}?{col}=eq.{val}&select=*",headers={**H,"Prefer":"count=exact","Range":"0-0"})
    v=r.headers.get("content-range","").split("/")[-1]; return int(v) if v.isdigit() else 0

def do_merge(loser,new,kind):
    cols=(company_cols if kind=="company" else drug_cols)+generic_cols
    actions=[]
    def handle(tc):
        table,col=tc
        n=count_eq(table,col,loser)
        if n==0: return None
        if APPLY:
            st,_=patch_eq(table,col,loser,new); return f"{table}.{col}({n}:{st})"
        return f"{table}.{col}({n})"
    with cf.ThreadPoolExecutor(max_workers=24) as ex:
        actions=[a for a in ex.map(handle, cols) if a]
    # array refs
    for table,col in array_cols:
        rows=requests.get(f"{URL}/rest/v1/{table}?{col}=cs.{{{loser}}}&select=id,{col}",headers=H).json()
        if isinstance(rows,list) and rows:
            actions.append(f"{table}.{col}[arr]({len(rows)})")
            if APPLY:
                for r in rows:
                    arr=[new if x==loser else x for x in (r[col] or [])]
                    requests.patch(f"{URL}/rest/v1/{table}?id=eq.{r['id']}",headers={**H,"Prefer":"return=minimal"},json={col:arr})
    # field-merge: fill winner nulls from loser; then delete loser
    ent="companies" if kind=="company" else "drugs"
    if APPLY:
        lo=requests.get(f"{URL}/rest/v1/{ent}?id=eq.{loser}&select=*",headers=H).json()
        wi=requests.get(f"{URL}/rest/v1/{ent}?id=eq.{new}&select=*",headers=H).json()
        if lo and wi:
            fill={k:lo[0][k] for k in lo[0] if lo[0][k] not in (None,"",[],{}) and wi[0].get(k) in (None,"",[],{}) and k!="id"}
            if fill: requests.patch(f"{URL}/rest/v1/{ent}?id=eq.{new}",headers={**H,"Prefer":"return=minimal"},json=fill)
        requests.delete(f"{URL}/rest/v1/{ent}?id=eq.{loser}",headers={**H,"Prefer":"return=minimal"})
    print(f"  {kind} {loser} -> {new}: {', '.join(actions) or 'no refs'}", flush=True)

print(f"{'APPLY' if APPLY else 'DRY RUN'} | company-ref cols={len(company_cols)} drug-ref cols={len(drug_cols)} generic={len(generic_cols)} array={len(array_cols)}")
print("### COMPANY MERGES ###")
for lo,wi in COMPANY_MERGES: do_merge(lo,wi,"company")
print("### DRUG MERGES ###")
for lo,wi in DRUG_MERGES: do_merge(lo,wi,"drug")
print("done" if APPLY else "dry run — re-run with --apply")
