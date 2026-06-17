#!/usr/bin/env python3
"""
entity_matcher.py — one canonical entity resolver for the whole dashboard.
=========================================================================
Builds a name->entity registry from `drugs` + `companies` (+ their aliases) and
resolves free text (claims, subject names, market-tracker company/drug columns)
to canonical drug/company ids. This is the SHARED matcher used by the knowledge-
graph builders so every table links entities the same way.

Design rules (this is a governance-strict platform — never mis-attribute):
  * Whole-word, case-insensitive matching (regex word boundaries).
  * A surface form that maps to >1 DISTINCT id is AMBIGUOUS and is dropped from
    auto-matching (reported), UNLESS a curated alias pins the canonical id.
  * Short / generic tokens are excluded via STOP + a minimum length.
  * Only entities that EXIST in the DB can be matched. Names that aren't in the
    DB (untracked comparators) are returned by callers as discovery candidates,
    never fabricated into edges.

Public API:
    reg = Registry(url, headers)            # builds from live tables
    reg.resolve("...text...")               # -> [(etype, eid, surface, pos), ...]
    reg.ambiguous                           # set of dropped ambiguous surfaces
"""
import re, requests

STOP = {
    "data", "study", "phase", "trial", "results", "approved", "patients", "disease",
    "therapy", "health", "group", "sciences", "cohort", "arm", "other", "general",
    "bio", "labs", "pharma", "therapeutics", "medicines", "biologics", "oncology",
    "company", "holdings", "global", "human", "adult", "active", "placebo", "dose",
}

# Suffix tokens stripped (iteratively) to derive a short company surface form.
_SUFFIX = (r"(inc|llc|l\.l\.c\.|ltd|limited|corp|corporation|co|company|plc|s\.a\.|sa|"
           r"ag|n\.v\.|nv|gmbh|holdings|group|therapeutics|pharmaceuticals|pharma|"
           r"biopharmaceuticals|biopharma|biosciences|biotherapeutics|biologics|"
           r"immunotherapeutics|immunotherapy|immunology|sciences|health|labs|"
           r"laboratories|bio|oncology|medicines)")
_SUFFIX_RE = re.compile(r",?\s+" + _SUFFIX + r"\.?$", re.I)

# Curated aliases for forms not derivable from the name, and to PIN the canonical
# id where duplicate company rows share a name. surface(lower) -> (etype, id).
# Only applied if the target id is actually present in the DB.
CURATED = {
    # company abbreviations / variants
    "bms": ("company", "bms"), "bristol myers squibb": ("company", "bms"),
    "bristol-myers squibb": ("company", "bms"), "bristol-myers": ("company", "bms"),
    "j&j": ("company", "jnj"), "jnj": ("company", "jnj"),
    "johnson & johnson": ("company", "jnj"), "janssen": ("company", "jnj"),
    "gsk": ("company", "gsk"), "glaxosmithkline": ("company", "gsk"), "glaxo": ("company", "gsk"),
    "eli lilly": ("company", "lilly"), "lilly": ("company", "lilly"),
    "gilead": ("company", "gilead"),
    "roivant": ("company", "roivant"),
    "protagonist": ("company", "protagonist"),
    "spyre": ("company", "spyre"),
    "bellus": ("company", "bellushealth"),
    "aclaris": ("company", "aclaris"),
    "abbvie": ("company", "abbvie"), "abbv": ("company", "abbvie"),
    "merck": ("company", "merck"), "msd": ("company", "merck"),
    "regeneron": ("company", "regeneron"),
    "ucb": ("company", "ucb"),  # 3-char (below the length guard) + pins the ucb/ucbpharma dup
    # drug brand -> generic (resolved to the generic's id at build time if present)
    "skyrizi": ("drug", "risankizumab"), "rinvoq": ("drug", "upadacitinib"),
    "stelara": ("drug", "ustekinumab"), "entyvio": ("drug", "vedolizumab"),
    "omvoh": ("drug", "mirikizumab"), "velsipity": ("drug", "etrasimod"),
    "tremfya": ("drug", "guselkumab"), "xeljanz": ("drug", "tofacitinib"),
}


def _getall(url, headers, table, params):
    out, s = [], 0
    while True:
        r = requests.get(f"{url}/rest/v1/{table}",
                         headers={**headers, "Range": f"{s}-{s+999}"}, params=params)
        d = r.json() if r.status_code in (200, 206) else []
        if not isinstance(d, list):
            break
        out += d
        if len(d) < 1000:
            break
        s += 1000
    return out


class Registry:
    def __init__(self, url, headers):
        self.url, self.h = url, headers
        self.name2ids = {}          # surface(lower) -> set(ids)
        self.id2type = {}           # id -> 'drug'|'company'
        self.id2name = {}
        self.pinned = {}            # surface(lower) -> (etype, id) from CURATED
        self.ambiguous = set()
        self._build()

    def _add(self, surface, etype, eid):
        if not surface:
            return
        s = surface.strip()
        if len(s) < 4 or s.lower() in STOP:
            return
        self.name2ids.setdefault(s.lower(), set()).add(eid)

    def _build(self):
        drugs = _getall(self.url, self.h, "drugs",
                        {"select": "id,name,display_name,brand_name,inn_name,dev_code,aliases"})
        comps = _getall(self.url, self.h, "companies", {"select": "id,name"})
        gen2id = {}
        for d in drugs:
            self.id2type[d["id"]] = "drug"; self.id2name[d["id"]] = d.get("name")
            for k in [d.get("name"), d.get("brand_name"), d.get("inn_name"), d.get("dev_code")] + (d.get("aliases") or []):
                self._add(k, "drug", d["id"])
            dn = (d.get("display_name") or "").split("(")[0].strip()
            self._add(dn, "drug", d["id"])
            if d.get("name"):
                gen2id[d["name"].strip().lower()] = d["id"]
            if d.get("inn_name"):
                gen2id[d["inn_name"].strip().lower()] = d["id"]
        for c in comps:
            self.id2type[c["id"]] = "company"; self.id2name[c["id"]] = c.get("name")
            nm = (c.get("name") or "").strip()
            self._add(nm, "company", c["id"])
            short, prev = nm, None
            while short != prev:
                prev = short
                short = _SUFFIX_RE.sub("", short).strip().rstrip(",").strip()
                if short and short != nm:
                    self._add(short, "company", c["id"])
        # ambiguity: any surface mapping to >1 distinct id is dropped
        for s, ids in self.name2ids.items():
            if len(ids) > 1:
                self.ambiguous.add(s)
        # curated pins (override ambiguity); only if target id exists in DB
        for s, (et, target) in CURATED.items():
            eid = target if et == "company" else gen2id.get(target.lower(), target)
            if eid in self.id2type:
                self.pinned[s] = (self.id2type[eid], eid)
        # compile matcher over all non-ambiguous surfaces + all pinned surfaces
        surfaces = ({s for s in self.name2ids if s not in self.ambiguous}
                    | set(self.pinned.keys()))
        surfaces = sorted(surfaces, key=len, reverse=True)
        self._pat = re.compile(r"(?<![A-Za-z0-9])(" + "|".join(re.escape(s) for s in surfaces) + r")(?![A-Za-z0-9])", re.I)

    def resolve(self, text):
        """Return ordered, de-duped [(etype, eid, surface, pos)] for a text blob."""
        if not text:
            return []
        out, seen = [], set()
        for m in self._pat.finditer(text):
            s = m.group(1).lower()
            hit = self.pinned.get(s)
            if not hit:
                ids = self.name2ids.get(s)
                if not ids or len(ids) != 1:
                    continue
                eid = next(iter(ids)); hit = (self.id2type.get(eid, "company"), eid)
            if hit[1] in seen:
                continue
            seen.add(hit[1])
            out.append((hit[0], hit[1], m.group(1), m.start()))
        out.sort(key=lambda r: (r[0] != "drug", r[3]))  # drugs first, then by position
        return out


if __name__ == "__main__":
    import os, pathlib
    base = pathlib.Path(__file__).resolve().parents[3]
    url = os.environ.get("SUPABASE_URL", "https://tghntyofptvfhmtchwcv.supabase.co")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or (base / ".supabase_service_key").read_text().strip()
    H = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    reg = Registry(url, H)
    print(f"registry: {len(reg.name2ids)} surfaces, {len(reg.pinned)} pinned, {len(reg.ambiguous)} ambiguous(dropped)")
    for t in ["SL-325 vs tulisokibart and Skyrizi; J&J / Protagonist Therapeutics; Eli Lilly / Incyte",
              "Bristol-Myers Squibb and GSK competition", "Spyre Therapeutics SPY002"]:
        print(" •", t, "->", [(e[0], e[1], e[2]) for e in reg.resolve(t)])
    print("sample ambiguous:", sorted(reg.ambiguous)[:10])
