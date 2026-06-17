#!/usr/bin/env python3
"""v135 Institution Intelligence builder (FREE/derived, idempotent).

1. Classify every institution that appears in author_institution_focus:
   industry / hospital / academic / government / other (record basis).
2. Profile: total_papers (distinct pmids in paper_authors) + top_areas (top 3
   author_institution_focus areas by paper_count).
3. Bridges: papers co-authored by an ACADEMIC/HOSPITAL institution AND an
   INDUSTRY institution; map the industry institution -> a companies row
   (resolve-or-skip); count shared_papers per (academic inst, company);
   write where shared_papers >= 2.

Upserts on the UNIQUE keys so re-runs add 0 new rows.
"""
import json, os, re, sys, urllib.request, urllib.parse, urllib.error
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SK = open(os.path.join(BASE, ".supabase_service_key")).read().strip()
REST = "https://tghntyofptvfhmtchwcv.supabase.co/rest/v1"
HDR = {"apikey": SK, "Authorization": f"Bearer {SK}",
       "Content-Type": "application/json", "User-Agent": "curl/8.0.1"}


def get_all(table, select, extra=""):
    rows, offset, page = [], 0, 1000
    while True:
        url = f"{REST}/{table}?select={urllib.parse.quote(select)}{extra}&limit={page}&offset={offset}"
        req = urllib.request.Request(url, headers=HDR)
        with urllib.request.urlopen(req, timeout=60) as r:
            batch = json.loads(r.read().decode())
        rows.extend(batch)
        if len(batch) < page:
            break
        offset += page
    return rows


def post(table, payload, on_conflict):
    url = f"{REST}/{table}?on_conflict={on_conflict}"
    hdr = dict(HDR)
    hdr["Prefer"] = "resolution=merge-duplicates,return=minimal"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=hdr, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status
    except urllib.error.HTTPError as e:
        print("POST ERR", e.code, e.read().decode()[:400]); raise


def delete_all(table, key_col):
    """Clear a derived table (REST DELETE requires a filter; match all non-null
    keys). Used to rebuild cleanly so re-runs never accumulate stale rows."""
    url = f"{REST}/{table}?{key_col}=not.is.null"
    hdr = dict(HDR)
    hdr["Prefer"] = "return=minimal"
    req = urllib.request.Request(url, headers=hdr, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status
    except urllib.error.HTTPError as e:
        print("DELETE ERR", e.code, e.read().decode()[:400]); raise


def norm(s):
    if not s:
        return ""
    s = s.lower().strip()
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# Brand names — unambiguous companies; classified industry BEFORE academic so
# "Novartis Institutes for BioMedical Research" stays industry.
INDUSTRY_BRAND = [
    "genentech", "janssen", "abbvie", "sanofi", "pfizer", "novartis", "amgen",
    "astrazeneca", "boehringer", "glaxosmithkline", "takeda", "gilead",
    "biogen", "regeneron", "celgene", "galapagos", "morphosys", "sandoz",
    "servier", "daiichi", "astellas", "otsuka", "chugai", "shionogi",
    "vir biotechnology", "novo nordisk",
]
# Generic commercial substrings — checked AFTER academic/government so that
# "University of Medicine and Pharmacy" / "Institute for Pharmacological
# Research" are not mis-tagged industry off the "pharma" substring.
INDUSTRY_GENERIC = [
    "pharmaceutical", "pharma", "therapeutics", "biosciences", "bioscience",
    "biotherapeutics", "biologics", "biopharma", "biotech", "biotechnology",
    "laboratories",
]
# Short legal-form / ambiguous tokens — match only as whole words (\b...\b)
# to avoid false hits like "agriculture"->ag, "against"->ag.
INDUSTRY_WORD = [
    "inc", "incorporated", "ltd", "llc", "corp", "corporation", "gmbh",
    "ag", "plc", "nv", "bv", "kgaa", "labs", "co kg",
]
# Academic markers checked early (before generic pharma) so medicine/pharmacy
# schools resolve academic.
ACADEMIC_EARLY = [
    "university", "universit", "college", "school of medicine", "faculty of",
    "academy", "polytechnic", "hochschule", "ecole",
    "institute", "institut", "instituto",
]
HOSPITAL_TOKENS = [
    "hospital", "clinic", "medical center", "medical centre", "hopital",
    "hôpital", "klinik", "klinikum", "infirmary", "ospedale", "hospitalier",
    "health system", "cancer center", "cancer centre", "hospitales",
    "hospitais", "medical centers", "general hospital", "nhs",
]
ACADEMIC_TOKENS = [
    "university", "universit", "institute", "instituto", "institut",
    "college", "academy", "academia", "school of medicine", "faculty of",
    "polytechnic", "ecole", "hochschule", "max planck", "cnrs", "inserm",
    "national institutes", "research center", "research centre",
    "research institute",
]
GOVERNMENT_TOKENS = [
    "ministry", "department of health", "national institutes of health",
    " nih ", "centers for disease control", "food and drug administration",
    "public health england", "agency", "government", "national health",
    "council", "administration", "bureau", "veterans affairs", "va medical",
]


PAREN_COUNTRY = re.compile(r"\s*\([^)]*\)\s*$")


def clean_name(raw):
    """Drop a trailing parenthetical like '(United States)' from the RAW name,
    then normalize. Done pre-norm because norm() would dissolve the parens."""
    raw = PAREN_COUNTRY.sub("", raw or "")
    return norm(raw)


def has_word(text, word):
    return re.search(r"\b" + re.escape(word) + r"\b", text) is not None


def classify(base, resolve_fn):
    """Return (institution_type, basis). Resolution order is deliberate:
    company match -> brand industry -> hospital -> government -> academic
    markers -> generic industry tokens -> other. Academic/government precede the
    generic 'pharma' substring so medicine/pharmacy schools are not mislabeled."""
    n = " " + base + " "
    # 1. resolves to a known company (strongest industry signal)
    cid = resolve_fn(base)
    if cid:
        return "industry", f"company_match:{cid}"
    # 2. unambiguous industry brand names
    for t in INDUSTRY_BRAND:
        if t in base:
            return "industry", f"industry_brand:{t}"
    # 3. hospital
    for t in HOSPITAL_TOKENS:
        if t in n:
            return "hospital", f"hospital_token:{t.strip()}"
    # 4. government
    for t in GOVERNMENT_TOKENS:
        if t in n:
            return "government", f"government_token:{t.strip()}"
    # 5. early academic markers (university/college/medicine&pharmacy schools)
    for t in ACADEMIC_EARLY:
        if t in base:
            return "academic", f"academic_token:{t}"
    # 6. generic industry substrings + legal-form whole words
    for t in INDUSTRY_GENERIC:
        if t in base:
            return "industry", f"industry_token:{t}"
    for t in INDUSTRY_WORD:
        if has_word(base, t):
            return "industry", f"industry_word:{t}"
    # 7. remaining academic markers (institute/research center/inserm/...)
    for t in ACADEMIC_TOKENS:
        if t in n:
            return "academic", f"academic_token:{t.strip()}"
    return "other", "no_token_match"


def main():
    print("Loading data...")
    institutions = get_all("institutions", "id,name,normalized_name,country")
    companies = get_all("companies", "id,name,lei_legal_name")
    aif = get_all("author_institution_focus",
                  "institution_id,area_or_target,paper_count")
    pa = get_all("paper_authors", "pmid,institution_id")
    print(f"  institutions={len(institutions)} companies={len(companies)} "
          f"aif={len(aif)} paper_authors={len(pa)}")

    inst_by_id = {i["id"]: i for i in institutions}

    LEGAL_RE = re.compile(
        r"\b(inc|incorporated|ltd|limited|corp|corporation|se|sa|gmbh|ag|plc|"
        r"nv|bv|llc|co|kgaa|company|group|holdings?|pharmaceuticals?|pharma|"
        r"therapeutics|biosciences?|biologics|biopharma|biotherapeutics)\b")

    def strip_legal(s):
        s = LEGAL_RE.sub(" ", s)
        return re.sub(r"\s+", " ", s).strip()

    # exact name/lei -> company id
    company_norms, company_stripped = {}, {}
    for c in companies:
        nm = norm(c["name"])
        if nm:
            company_norms.setdefault(nm, c["id"])
            st = strip_legal(nm)
            if st:
                company_stripped.setdefault(st, c["id"])
        lei = norm(c.get("lei_legal_name"))
        if lei:
            company_norms.setdefault(lei, c["id"])
            st = strip_legal(lei)
            if st:
                company_stripped.setdefault(st, c["id"])

    # hand-curated aliases (institution-name variant -> company id) — documented,
    # not fabricated: each maps a publicly-known alternate name of a companies row.
    ALIAS = {
        "glaxosmithkline": "gsk",
        "bristol myers squibb": "bms",
        "bristol-myers squibb": "bms",
        "johnson and johnson": "jnj",
        "eli lilly and company": "lilly",
        "eli lilly": "lilly",
        "f hoffmann la roche": "roche",
        "hoffmann la roche": "roche",
        "janssen": "jnj",
        "janssen research and development": "jnj",
        "janssen pharmaceutica": "jnj",
    }

    def resolve_company(base):
        """Resolve an industry institution name (already country-stripped via
        clean_name) to a companies.id, or None. Conservative: exact -> alias ->
        legal-stripped -> distinctive leading word-prefix."""
        if base in company_norms:
            return company_norms[base]
        if base in ALIAS:
            return ALIAS[base]
        sb = strip_legal(base)
        if sb in company_stripped:
            return company_stripped[sb]
        if sb in ALIAS:
            return ALIAS[sb]
        # leading word-prefix match: company name is the head of the inst name
        # (e.g. 'merck and co inc rahway nj usa' -> 'merck and co'). Require the
        # company norm to be distinctive (>=5 chars) to avoid spurious hits.
        best = None
        for cnorm, cid in company_norms.items():
            if len(cnorm) >= 5 and (base == cnorm or base.startswith(cnorm + " ")):
                if best is None or len(cnorm) > len(best[0]):
                    best = (cnorm, cid)
        return best[1] if best else None

    # institutions that appear in author_institution_focus -> classify these
    focus_inst_ids = {r["institution_id"] for r in aif}
    print(f"  institutions in author_institution_focus = {len(focus_inst_ids)}")

    # distinct pmids per institution (from paper_authors)
    inst_pmids = defaultdict(set)
    for r in pa:
        if r.get("institution_id") and r.get("pmid"):
            inst_pmids[r["institution_id"]].add(r["pmid"])

    # top areas per institution from author_institution_focus
    inst_areas = defaultdict(list)
    for r in aif:
        inst_areas[r["institution_id"]].append(
            (r["area_or_target"], r.get("paper_count") or 0))

    # ---- classify + profile ----
    profile_rows = []
    type_counts = defaultdict(int)
    inst_type = {}
    for iid in focus_inst_ids:
        inst = inst_by_id.get(iid)
        if not inst:
            continue  # resolve-or-skip: orphan institution_id
        nm = clean_name(inst.get("name") or inst.get("normalized_name"))
        itype, basis = classify(nm, resolve_company)
        inst_type[iid] = itype
        type_counts[itype] += 1
        areas_sorted = sorted(inst_areas.get(iid, []),
                              key=lambda x: (-x[1], x[0]))
        top_areas = [a for a, _ in areas_sorted[:3]]
        profile_rows.append({
            "institution_id": iid,
            "institution_type": itype,
            "total_papers": len(inst_pmids.get(iid, set())),
            "top_areas": top_areas,
            "classification_basis": basis,
        })

    print("\nClassification counts:", dict(type_counts))

    # ---- academic<->industry bridges ----
    # map industry institution -> company id (resolve-or-skip)
    industry_inst_to_company = {}
    skipped_industry = []
    for iid, itype in inst_type.items():
        if itype != "industry":
            continue
        inst = inst_by_id[iid]
        nm = clean_name(inst.get("name") or inst.get("normalized_name"))
        cid = resolve_company(nm)
        if cid:
            industry_inst_to_company[iid] = cid
        else:
            skipped_industry.append(inst.get("name"))

    print(f"\nIndustry institutions resolved to a company: "
          f"{len(industry_inst_to_company)}; skipped (no company row): "
          f"{len(skipped_industry)}")

    # pmid -> set of institution_ids on that paper
    pmid_insts = defaultdict(set)
    for r in pa:
        if r.get("pmid") and r.get("institution_id"):
            pmid_insts[r["pmid"]].add(r["institution_id"])

    # for each paper, pair every academic/hospital inst with every industry->company
    bridge_pmids = defaultdict(set)  # (academic_inst_id, company_id) -> {pmid}
    for pmid, iset in pmid_insts.items():
        acad = [i for i in iset if inst_type.get(i) in ("academic", "hospital")]
        comps = {industry_inst_to_company[i] for i in iset
                 if i in industry_inst_to_company}
        if not acad or not comps:
            continue
        for ai in acad:
            for cid in comps:
                bridge_pmids[(ai, cid)].add(pmid)

    bridge_rows = []
    for (ai, cid), pmids in bridge_pmids.items():
        if len(pmids) >= 2:
            bridge_rows.append({
                "institution_id": ai,
                "company_id": cid,
                "shared_papers": len(pmids),
                "basis": "co_authorship:academic_or_hospital+industry_institution",
            })

    print(f"Bridge candidates (shared_papers>=2): {len(bridge_rows)}")

    # ---- write (clean rebuild: delete-all then insert; derived tables owned
    # entirely by this script, so re-run yields identical table state) ----
    delete_all("institution_company_bridge", "institution_id")
    delete_all("institution_research_profile", "institution_id")
    if profile_rows:
        for i in range(0, len(profile_rows), 500):
            post("institution_research_profile", profile_rows[i:i+500],
                 "institution_id")
        print(f"Wrote {len(profile_rows)} profile rows")
    if bridge_rows:
        for i in range(0, len(bridge_rows), 500):
            post("institution_company_bridge", bridge_rows[i:i+500],
                 "institution_id,company_id")
        print(f"Wrote {len(bridge_rows)} bridge rows")

    # ---- report ----
    print("\n=== TOP ACADEMIC CENTERS BY total_papers ===")
    acad_profiles = [p for p in profile_rows
                     if p["institution_type"] == "academic"]
    for p in sorted(acad_profiles, key=lambda x: -x["total_papers"])[:15]:
        print(f"  {p['total_papers']:4d}  {inst_by_id[p['institution_id']]['name']}")

    print("\n=== STRONGEST academic<->company bridges ===")
    cname = {c["id"]: c["name"] for c in companies}
    for b in sorted(bridge_rows, key=lambda x: -x["shared_papers"])[:20]:
        print(f"  {b['shared_papers']:3d}  "
              f"{inst_by_id[b['institution_id']]['name'][:45]:45s} <-> "
              f"{cname.get(b['company_id'], b['company_id'])}")

    if skipped_industry:
        print(f"\n=== RESOLVE-OR-SKIP: industry insts with no companies row "
              f"({len(skipped_industry)}) — sample ===")
        for s in skipped_industry[:25]:
            print("   -", s)


if __name__ == "__main__":
    main()
