#!/usr/bin/env python3
"""
deep_enrich_intel.py — Deep structuring of submitted intel into the database
============================================================================
Second pass after review_submitted_intel.py. For an analyzed/needs_review row it
re-reads the source (URL or archived/uploaded PDF), runs a structured Claude
extraction, and writes — GOVERNED — to the relational tables, creating cards and
relationships as needed:

  • companies  — originator companies (skips analyst/news publishers)
  • drugs      — competitor cards (company_id = originator; target/stage/modality/
                 indication/mechanism/summary; source_url) + drug_sources provenance
  • catalysts  — dated, linked to drug_id + company_id + area_id + source_url +
                 source_submitted_intel_id  (deduped)
  • deals      — from/to company, type, economics, headline (deduped)

Governance: high-confidence facts are written; every fact carries its source. New
drugs are created as competitor cards. Ambiguous rows stay flagged for review.

Usage:
  python3 scripts/deep_enrich_intel.py --id <uuid>     # one row
  python3 scripts/deep_enrich_intel.py --limit 5       # all analyzed not yet deep-enriched
  python3 scripts/deep_enrich_intel.py --id <uuid> --dry-run
"""
import os, sys, re, json, argparse, pathlib, importlib.util
from datetime import datetime, timezone
import requests

BASE = pathlib.Path(__file__).parent.parent
def _key(env, f):
    v = os.environ.get(env, "").strip()
    if v: return v
    p = BASE / f
    return p.read_text().strip() if p.exists() else ""

SUPABASE_URL  = os.environ.get("SUPABASE_URL", "https://tghntyofptvfhmtchwcv.supabase.co")
SERVICE_KEY   = _key("SUPABASE_SERVICE_KEY", ".supabase_service_key")
ANTHROPIC_KEY = _key("ANTHROPIC_API_KEY", ".anthropic_api_key")
MODEL         = "claude-opus-4-6"
SB_H = {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}", "Content-Type": "application/json"}

# Reuse the review module's PDF/URL/storage fetchers
_spec = importlib.util.spec_from_file_location("rsi", str(BASE / "scripts" / "review_submitted_intel.py"))
rsi = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(rsi)

PUBLISHERS = ("wedbush", "endpoints", "fierce", "evercore", "leerink", "jefferies",
              "stat news", "biopharma dive", "iqvia", "morgan stanley", "goldman",
              "bofa", "cantor", "guggenheim", "piper", "stifel", "truist", "ubs", "iqvia")
def is_publisher(nm): return any(p in (nm or "").lower() for p in PUBLISHERS)

# ── Supabase helpers ──────────────────────────────────────────────────────────
def sb_get(t, params):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{t}", headers={**SB_H, "Range": "0-999"}, params=params, timeout=25)
    return r.json() if r.status_code == 200 else []
def sb_post(t, row, prefer="return=minimal"):
    r = requests.post(f"{SUPABASE_URL}/rest/v1/{t}", headers={**SB_H, "Prefer": prefer}, json=row, timeout=25)
    return r.status_code in (200, 201, 204), (r.text if r.status_code >= 300 else "")
def sb_patch(t, params, row):
    r = requests.patch(f"{SUPABASE_URL}/rest/v1/{t}", headers=SB_H, params=params, json=row, timeout=25)
    return r.status_code in (200, 204)

def cid_slug(name): return re.sub(r"[^a-z0-9]", "", (name or "").lower())[:40]
def did_slug(name): return re.sub(r"-+", "-", re.sub(r"[^a-z0-9-]", "-", (name or "").split("(")[0].strip().lower()))[:40]

# ── Date parsing for catalysts (3Q26 / 1H27 / Mid-2026 / 2026 / YYYY-MM-DD) ────
def parse_date(s):
    s = (s or "").strip()
    m = re.search(r"(20\d{2})-(\d{2})-(\d{2})", s)
    if m: return m.group(0), m.group(0)
    def yr(y): y = int(y); return y + 2000 if y < 100 else y
    m = re.search(r"([1-4])\s*Q\s*[''`]?\s*(\d{2,4})", s) or re.search(r"Q\s*([1-4])\s*[''`]?\s*(\d{2,4})", s)
    if m:
        q, y = int(m.group(1)), yr(m.group(2)); mm = {1:"03-31",2:"06-30",3:"09-30",4:"12-31"}[q]
        return f"{m.group(0)}", f"{y}-{mm}"
    m = re.search(r"([12])\s*H\s*[''`]?\s*(\d{2,4})", s)
    if m:
        h, y = int(m.group(1)), yr(m.group(2)); return m.group(0), f"{y}-{'06-30' if h==1 else '12-31'}"
    if re.search(r"mid[\s-]*20\d{2}", s, re.I):
        y = re.search(r"(20\d{2})", s).group(1); return f"Mid-{y}", f"{y}-06-30"
    if re.search(r"(year[\s-]*end|YE)\s*20?\d{2}", s, re.I):
        y = yr(re.search(r"(\d{2,4})", s).group(1)); return f"YE{y}", f"{y}-12-31"
    m = re.search(r"\b(20\d{2})\b", s)
    if m: return m.group(1), f"{m.group(1)}-12-31"
    return None, None

# ── Structured extraction prompt ──────────────────────────────────────────────
PROMPT = """You are a pharma BD intelligence analyst for Ailux (TL1A×IL-23p19 bispecific, IBD).
From the document below, extract structured competitive intelligence as STRICT JSON only.

For every drug, give its ORIGINATOR company (inventor/developer). Map each drug to ONE company.
Areas use these slugs: tl1a (IBD/TL1A/IL-23), tslp (respiratory), il4ra (atopic), igf1r (TED),
fcrn (autoimmune), tcell (T-cell engager), or general.

DOCUMENT:
{content}

Return JSON:
{{
 "drugs":[{{"name":"","company":"","target":"","modality":"","stage":"Preclinical|Phase 1|Phase 2|Phase 3|Approved","indication":"","area":"tl1a|tslp|il4ra|igf1r|fcrn|tcell|general","mechanism":"1-2 sentences","summary":"2-3 sentences with the data in this doc","is_competitor":true,"confidence":"high|medium|low"}}],
 "catalysts":[{{"drug":"","company":"","date_str":"e.g. 3Q26 / Mid-2026 / 1H27","event":"","indication":"","area":"tl1a","significance":"P0|P1|P2|P3","confidence":"high|medium|low"}}],
 "deals":[{{"from_company":"originator","to_company":"partner/acquirer","deal_type":"licensing|acquisition|collaboration|option","upfront_usd_m":null,"total_usd_m":null,"headline":"","confidence":"high|medium|low"}}],
 "digest":{{"title":"","one_paragraph":"2-3 sentences","executive_summary":"4-10 sentences capturing ALL the key content, numbers and themes","themes":[""],"bd_implications":"why it matters for Ailux/ALX001"}},
 "facts":[{{"fact_type":"clinical|commercial|deal|catalyst|competitive|management|patient|regulatory|financial|market","subject_name":"drug/company the fact is about","subject_drug":"drug name if applicable","area":"tl1a|tslp|il4ra|igf1r|fcrn|tcell|general","claim":"ONE specific fact stated in the doc","metric":"","value":"","unit":"","period":"","confidence":"high|medium|low"}}]
}}
CAPTURE EVERYTHING: in facts[], extract EVERY discrete fact, number, price, date, quote, and positioning statement in the document — even routine ones that would not become a card. The goal is a complete structured record of the document, not just card-worthy entities. Only include facts actually stated in the document. Use [] when a section is empty."""

def claude_extract(content):
    r = requests.post("https://api.anthropic.com/v1/messages",
        headers={"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": MODEL, "max_tokens": 3000, "messages": [{"role": "user", "content": PROMPT.format(content=content[:14000])}]},
        timeout=120)
    r.raise_for_status()
    raw = r.json()["content"][0]["text"].strip()
    if raw.startswith("```"): raw = raw.split("```")[1]; raw = raw[4:] if raw.startswith("json") else raw
    return json.loads(raw)

# ── Writers ───────────────────────────────────────────────────────────────────
def ensure_company(name, dry):
    if not name or is_publisher(name): return None
    cid = cid_slug(name)
    if not cid: return None
    if sb_get("companies", {"id": f"eq.{cid}", "select": "id"}): return cid
    if dry: return cid
    ok, _ = sb_post("companies", {"id": cid, "name": name, "status": "active", "company_type": "biotech", "ta_focus_1": "Immunology"})
    return cid if ok else None

def find_drug(name):
    slug = did_slug(name)
    rows = sb_get("drugs", {"id": f"eq.{slug}", "select": "id,company_id"})
    if rows: return rows[0]["id"]
    # match by name (exact-ish)
    rows = sb_get("drugs", {"name": f"ilike.{name.split('(')[0].strip()}", "select": "id"})
    return rows[0]["id"] if rows else None

def write_source(drug_id, dname, claim_type, claim_value, url, domain, conf):
    sb_post("drug_sources", {
        "drug_id": drug_id, "drug_name": (dname or "").split("(")[0].strip(),
        "claim_type": claim_type, "claim_value": (claim_value or "")[:300],
        "source_url": url, "source_type": "other", "source_domain": domain,
        "content_confirms_claim": True, "confidence": conf,
        "added_by": "deep_enrich_intel", "session_label": f"deep_{datetime.now(timezone.utc):%Y-%m-%d}"})

CONF_DS = {"high": "inferred", "medium": "inferred", "low": "unverified"}
SIG_MAP = {"P0": "high", "P1": "high", "P2": "medium", "P3": "low",
           "high": "high", "medium": "medium", "low": "low"}

def enrich_row(row, dry=False, cache=None):
    rid = row["id"]; url = row.get("source_url") or ""
    rpj = row.get("raw_payload_json") or {}
    domain = row.get("source_name") or (url.split("/")[2] if "//" in url else "submitted_intel")
    log = {"drugs": [], "catalysts": [], "deals": [], "skipped": []}

    # 1) Get the document text — prefer the archived/uploaded PDF, else the URL
    content, _ = ("", None)
    arch = f"{domain}/{rid}.pdf" if "bluematrix" in domain or "wedbush" in domain else None
    if isinstance(rpj, dict) and rpj.get("attached_file_path"):
        content, _ = rsi.fetch_storage_pdf(rpj["attached_file_path"])
    if not content and arch:
        content, _ = rsi.fetch_storage_pdf(arch)
    if not content and url:
        content, _ = rsi.fetch_page_text(url)
    if not content:
        # fall back to the stored summary so we still structure something
        content = (row.get("extracted_summary") or "") + "\n" + json.dumps(row.get("extracted_entities_json") or {})
    if len(content.strip()) < 40:
        print(f"  ! {rid[:8]}: no usable content"); return log

    if cache and os.path.exists(cache):
        data = json.load(open(cache)); print(f"  (using cached extraction {cache})")
    else:
        data = claude_extract(content)
        if cache: json.dump(data, open(cache, "w"))

    # 2) Drugs → competitor cards + provenance
    drug_ids = {}
    for d in data.get("drugs", []):
        nm = (d.get("name") or "").strip()
        if not nm or len(nm) < 2: continue
        if re.search(r"undisclosed|unnamed|\btbd\b|next[\s-]?gen|pipeline|portfolio", nm, re.I):
            log["skipped"].append(f"drug '{nm}' (non-specific name)"); continue
        comp = d.get("company") or ""
        if is_publisher(comp): comp = ""
        existing = find_drug(nm)
        cid = ensure_company(comp, dry) if comp else None
        if existing:
            drug_ids[nm] = existing
            if not dry: write_source(existing, nm, "company_pipeline", d.get("summary"), url, domain, CONF_DS.get(d.get("confidence"), "inferred"))
            if cid and not dry:
                cur = sb_get("drugs", {"id": f"eq.{existing}", "select": "company_id"})
                if cur and not cur[0].get("company_id"): sb_patch("drugs", {"id": f"eq.{existing}"}, {"company_id": cid})
            log["drugs"].append(f"~{existing} (source+link)")
            continue
        if d.get("confidence") == "low":
            log["skipped"].append(f"drug {nm} (low confidence)"); continue
        slug = did_slug(nm)
        drug = {"id": slug, "name": nm.split("(")[0].strip(), "display_name": nm,
                "company_id": cid, "target": (d.get("target") or None),
                "stage": d.get("stage") or "Preclinical", "modality": d.get("modality") or None,
                "indication_short": d.get("indication") or None,
                "overlap": "Direct" if d.get("is_competitor") else "Watch", "catalog_category": "Competitor",
                "therapeutic_area": "Immunology", "mechanism": d.get("mechanism") or None,
                "drug_summary": d.get("summary") or None, "source_url": url or None,
                "confidence_level": "inferred", "discovery_status": "auto", "data_source": "deep_enrich_intel"}
        if dry:
            log["drugs"].append(f"+{slug} (would create)"); drug_ids[nm] = slug; continue
        ok, errtxt = sb_post("drugs", drug)
        if ok:
            drug_ids[nm] = slug
            write_source(slug, nm, "mechanism", d.get("mechanism"), url, domain, CONF_DS.get(d.get("confidence"), "inferred"))
            write_source(slug, nm, "company_pipeline", d.get("summary"), url, domain, CONF_DS.get(d.get("confidence"), "inferred"))
            log["drugs"].append(f"+{slug} ({comp or '?'})")
        else:
            log["skipped"].append(f"drug {nm}: {errtxt[:80]}")

    # 3) Catalysts → dated, drug-linked, source-linked (deduped)
    for c in data.get("catalysts", []):
        ev = (c.get("event") or "").strip()
        if not ev: continue
        if c.get("confidence") == "low": log["skipped"].append(f"catalyst {ev[:40]} (low conf)"); continue
        dnm = c.get("drug") or ""
        did = drug_ids.get(dnm) or find_drug(dnm) if dnm else None
        cdate, sdate = parse_date(c.get("date_str"))
        label = f"{(c.get('date_str') or '').strip()}: {ev}".strip(": ")[:200]
        # dedup: same drug + similar label
        if did:
            dup = sb_get("catalysts", {"drug_id": f"eq.{did}", "select": "id,label"})
            if any(_sim(label, x.get("label")) for x in dup): log["skipped"].append(f"catalyst dup {label[:40]}"); continue
        cid = ensure_company(c.get("company"), dry) if c.get("company") else None
        cat = {"label": label, "catalyst_date": (c.get("date_str") or None), "sort_date": sdate,
               "drug_id": did, "company_id": cid, "area_id": c.get("area") or None,
               "significance": SIG_MAP.get(c.get("significance") or "P2", "medium"), "catalyst_type": "readout",
               "catalyst_status": "pending", "resolved": False, "confidence_level": "inferred",
               "source_url": url or None,
               "notes": (c.get("indication") or "")}
        if dry: log["catalysts"].append(f"+{label[:50]} → {did or '?'}"); continue
        ok, errtxt = sb_post("catalysts", cat)
        log["catalysts"].append(f"+{label[:50]} → {did or '?'}" if ok else f"FAIL {errtxt[:70]}")

    # 4) Deals (deduped by headline)
    for dl in data.get("deals", []):
        hl = (dl.get("headline") or "").strip()
        if not hl or dl.get("confidence") == "low": continue
        dup = sb_get("deals", {"headline": f"ilike.%{hl[:30]}%", "select": "id"})
        if dup: log["skipped"].append(f"deal dup {hl[:40]}"); continue
        if dry: log["deals"].append(f"+{hl[:50]}"); continue
        ok, _ = sb_post("deals", {"from_company": dl.get("from_company") or "", "to_company": dl.get("to_company") or "",
            "deal_type": dl.get("deal_type") or "collaboration", "upfront_usd_m": dl.get("upfront_usd_m"),
            "total_usd_m": dl.get("total_usd_m"), "headline": hl[:300], "source_url": url or None,
            "economic_terms_verified": False})
        if ok: log["deals"].append(f"+{hl[:50]}")

    # 5) Document digest (comprehensive — captures the whole doc, not just cards)
    dg = data.get("digest") or {}
    if dg.get("executive_summary") and not dry:
        ok, _ = sb_post("intel_digests", {
            "submitted_intel_id": rid, "source_url": url or None,
            "doc_type": (row.get("source_name") or "document"), "title": (dg.get("title") or "")[:300],
            "one_paragraph": dg.get("one_paragraph"), "executive_summary": dg.get("executive_summary"),
            "themes": dg.get("themes") or [],
            "companies": list({(d.get("company") or "") for d in data.get("drugs", []) if d.get("company")}),
            "drugs": [d.get("name") for d in data.get("drugs", []) if d.get("name")],
            "bd_implications": dg.get("bd_implications")})
        if ok: log.setdefault("digest", []).append(dg.get("title", "")[:50])

    # 6) Atomic facts — the full structured record of the document
    for f in data.get("facts", []):
        claim = (f.get("claim") or "").strip()
        if not claim:
            continue
        v = f.get("value")
        try: vnum = float(v) if v not in (None, "", "null") and str(v).replace(".", "").replace("-", "").isdigit() else None
        except Exception: vnum = None
        dnm = f.get("subject_drug") or ""
        if dry:
            log.setdefault("facts", []).append(claim[:50]); continue
        ok, _ = sb_post("intel_facts", {
            "submitted_intel_id": rid, "source_url": url or None, "fact_type": f.get("fact_type") or "other",
            "subject_type": "drug" if dnm else "company", "subject_id": (drug_ids.get(dnm) or find_drug(dnm)) if dnm else None,
            "subject_name": f.get("subject_name") or dnm or None, "claim": claim[:600],
            "metric": f.get("metric") or None, "value_num": vnum, "value_text": (None if vnum is not None else (str(v) if v not in (None, "") else None)),
            "unit": f.get("unit") or None, "period": f.get("period") or None, "area_id": f.get("area") or None,
            "confidence": f.get("confidence") or "medium"})
        if ok: log.setdefault("facts", []).append(claim[:50])

    # 7) mark deep-enriched
    if not dry and isinstance(rpj, dict):
        rpj["deep_enriched_at"] = datetime.now(timezone.utc).isoformat()
        sb_patch("submitted_intel", {"id": f"eq.{rid}"}, {"raw_payload_json": rpj})
    return log

def _sim(a, b):
    wa = set(re.sub(r"[^a-z0-9 ]", " ", (a or "").lower()).split())
    wb = set(re.sub(r"[^a-z0-9 ]", " ", (b or "").lower()).split())
    if not wa or not wb: return False
    return len(wa & wb) / min(len(wa), len(wb)) > 0.6

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id"); ap.add_argument("--limit", type=int, default=5); ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cache")
    a = ap.parse_args()
    sel = "id,source_url,source_name,extracted_summary,extracted_entities_json,raw_payload_json,status"
    if a.id:
        rows = sb_get("submitted_intel", {"id": f"eq.{a.id}", "select": sel})
    else:
        rows = sb_get("submitted_intel", {"status": "in.(analyzed,needs_review)", "select": sel,
                                          "order": "created_at.desc", "limit": str(a.limit)})
        rows = [r for r in rows if not (isinstance(r.get("raw_payload_json"), dict) and r["raw_payload_json"].get("deep_enriched_at"))]
    print(f"Deep-enriching {len(rows)} row(s)  dry={a.dry_run}")
    for r in rows:
        print(f"\n┌─ {r['id'][:8]} | {r.get('source_name') or '—'}")
        try:
            log = enrich_row(r, a.dry_run, a.cache)
            for k in ("drugs", "catalysts", "deals", "digest", "facts", "skipped"):
                for x in log.get(k, []): print(f"  {k[:5]}: {x}")
        except Exception as e:
            print(f"  ! error: {e}")
    print("\nDone.")

if __name__ == "__main__":
    main()
