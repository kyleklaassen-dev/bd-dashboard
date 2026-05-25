# Meridian Normalization Engine
**Created:** 2026-05-25  
**Status:** Documentation only — rules extracted from wave2a + wave2b backfill scripts  
**Purpose:** Canonical reference for indication string normalization; foundation for reusable `normalizeIndication()` platform function

---

## Design Principle

Every raw string from an external source (ClinicalTrials, press releases, enrichment pipelines) must pass through a deterministic parser before touching the ontology. The parser never guesses. It either resolves to a canonical indication ID with an explicit confidence tier, or it returns `None` and the string enters the unresolved queue for review.

---

## Parser Priority Order

The parser applies rules in strict order. First match wins. Later tiers apply only if all earlier tiers fail.

### Tier 1 — Exact Alias Match (conf 99, auto_confirmed)
Normalize the raw string (lowercase, strip leading/trailing whitespace) and look up in `indication_aliases.normalized_alias`. If found, return the `indication_id` at full confidence.

```python
def normalize(s): return s.lower().strip()
key = normalize(raw)
if key in alias_lookup:
    return alias_lookup[key], 99, "tier1_structured", "auto_confirmed"
```

### Tier 2a — Parenthetical Abbreviation Strip (conf 97, auto_confirmed)
Remove trailing parenthetical abbreviations (2–6 uppercase letters, optional digit) and retry Tier 1.

```python
PAREN_ABBR_RE = re.compile(r'\s*\([A-Z]{2,6}\d*\)\s*$')
stripped = PAREN_ABBR_RE.sub('', raw).strip()
```

Examples: `Atopic Dermatitis (AD)` → `Atopic Dermatitis` → alias hit.

### Tier 2b — MedDRA Inverted Form (conf 96, auto_confirmed)
ClinicalTrials.gov uses MedDRA convention: `"Colitis, Ulcerative"` instead of `"Ulcerative Colitis"`. Detect the inversion pattern and try both the full inversion and single-word prefix.

```python
MEDDRA_RE = re.compile(r'^([A-Z][a-z]+(?:\s+[A-Za-z]+)*),\s+([A-Z][a-z]+(?:\s+[A-Za-z]+)*)$')
m = MEDDRA_RE.match(raw)
if m:
    inverted = f"{m.group(2)} {m.group(1)}"  # "Ulcerative Colitis"
    single   = m.group(2)                     # "Ulcerative" (fallback)
    # try alias lookup on inverted, then single
```

Examples: `Colitis, Ulcerative` → `Ulcerative Colitis` → `uc`. `Dermatitis, Atopic` → `Atopic Dermatitis` → `ad`.

### Tier 2c — Annotation Strip (conf 92, sampling_queue)
Strip year references, phase annotations, severity modifiers, and qualifier clauses from the raw string, then retry Tier 1.

Strip patterns (applied in order, iteratively until stable):
- Year suffix: `\s*\(\d{4}\)\s*$`
- Phase annotation: `\s*-?\s*Phase\s+\d[AB]?\b.*$` (case-insensitive)
- Mod/Sev prefix: `^(moderate[-\s]to[-\s]severe|moderate|severe|mild|refractory|relapsing[-\s]remitting)\s+` (case-insensitive)
- Qualifier suffix: `\s+(uncontrolled|resistant|inadequate|biologic.naive|biologic.experienced).*$` (case-insensitive)

### Tier 2d — Governance Normalization (conf 85, sampling_queue)
Apply hard-coded governance rules for known alias clusters that are not in `indication_aliases` but have a clear canonical mapping by policy.

```python
SEVERE_ASTHMA_RE = re.compile(r'^(severe|eosinophilic|allergic|moderate|bronchial|atopic)[\s\-]+asthma', re.IGNORECASE)
GRAVES_RE        = re.compile(r"graves['']?\s+(disease|orbitopathy|ophthalmopathy)", re.IGNORECASE)
TED_ALT_RE       = re.compile(r'thyroid.associated ophthalmopathy|thyroid eye', re.IGNORECASE)
```

Mappings:
- Any `*asthma` severity variant → `asthma` (governance: severity ≠ separate indication)
- `Graves' Disease/Orbitopathy` → `ted` (governance: orbital manifestation = TED)
- `Thyroid-Associated Ophthalmopathy` → `ted`

### Tier 2e — Partial Alias Scan (conf 82, sampling_queue)
Normalize both the raw string and all known aliases. If a known alias is a substring of the raw string (or vice versa), return the match at low confidence for sampling queue review.

```python
norm_raw = normalize(raw)
for alias_norm, ind_id in alias_lookup.items():
    if alias_norm in norm_raw or norm_raw in alias_norm:
        return ind_id, 82, "tier2_partial", "sampling_queue"
```

---

## Exclusion Rules (applied before composite split)

### Healthy Volunteer Exclusion
Exclude any string that matches the HV pattern. Write to `backfill_preview` with `preview_status='excluded'`. Never commit to the target table.

```python
HV_RE = re.compile(
    r'\bhealthy\b|\bnormal\s+(volunteer|control|subject|participant|adult)\b'
    r'|\bplacebo.only\b|\bnon.disease\b',
    re.IGNORECASE
)
```

Rationale: healthy volunteer trials carry no indication signal and inflate coverage counts.

### Out-of-Scope Classifier
Flag strings matching known out-of-scope disease domains. Write to `backfill_preview` with `preview_status='excluded'`. Do not force into an in-scope indication.

```python
OOS_RE = re.compile(
    r'\bcancer\b|\btumou?r\b|\blymphoma\b|\bleukemia\b|\bmelanoma\b|\bcarcinoma\b'
    r'|\boncology\b|\bdiabetes\b|\bobesity\b|\bhypertension\b|\bhyperlipidemia\b'
    r'|\bparkinson\b|\balzheimer\b|\bschizophrenia\b|\bdepression\b'
    r'|\bhepatitis\b|\bhiv\b|\binfection\b|\bcovid\b|\bsars\b',
    re.IGNORECASE
)
```

Rationale: OOS strings are expected in broad trial databases. Excluding them produces a cleaner indication-level coverage metric.

---

## Composite Split Rules

Applied only after all tier 1–2 resolution attempts have failed on the full string.

### Composite Detection
Source strings from ClinicalTrials.gov often encode multiple indications as dot-separated (`·`) or semicolon-separated (`;`) lists.

```python
DOT_SEP  = '·'   # U+00B7 MIDDLE DOT (ClinicalTrials standard)
SEMI_SEP = ';'
```

### Composite Resolution
Split on the separator. For each component:
1. Apply HV exclusion → if HV, discard component
2. Apply OOS classifier → if OOS, discard component
3. Apply Tier 1–2e resolution on the component
4. If resolved: assign `confidence = max(component_score - 10, 78)`, method = `tier3_pattern`
5. If not resolved: add to unresolved set

A composite that splits into N components may produce 0–N rows.

### Composite Penalty Floor
Composite-derived rows get a minimum confidence of 78 regardless of component match tier. This deliberately places them in Tier C territory to trigger `review_required` status for low-confidence composites, while still allowing `sampling_queue` for high-confidence components (e.g., a Tier 1 alias match within a composite scores `max(99-10, 78) = 89`, which is Tier B `sampling_queue`).

---

## Confidence → Review Status Mapping

| Confidence | Level | Review Status |
|---|---|---|
| ≥ 95 AND method in (tier1, tier2_synonym) | A | auto_confirmed |
| ≥ 80 | A or B | sampling_queue |
| < 80 | C | review_required |

---

## Reusable Function Signature (planned)

```python
def normalizeIndication(
    raw: str,
    alias_lookup: dict,          # normalized_alias → indication_id
    composite_lookup: dict,      # normalized_alias → [indication_id, ...]
    governance_rules: list,      # list of (regex, indication_id, conf) tuples
    exclude_hv: bool = True,
    exclude_oos: bool = True,
) -> NormalizationResult | None:
    """
    Returns NormalizationResult(indication_id, confidence_score, confidence_level,
    review_status, extraction_method, is_composite, composite_of) or None.
    Never raises. Unknown strings return None.
    """
```

Same pattern should apply for:
- `normalizeTarget(raw, target_lookup, ...)` — for drug_targets backfill
- `normalizeCompany(raw, company_lookup, ...)` — for deal/partnership ingestion
- `normalizeModality(raw, modality_lookup, ...)` — for drug modality classification
- `normalizeRoute(raw, route_lookup, ...)` — for dosing/formulation enrichment

---

## Known Alias Gaps (found during Wave 2B)

| Raw string | Freq | Resolution | Action taken |
|---|---|---|---|
| `Crohns Disease` | 2 | Missing apostrophe | Added as synonym alias |
| `Chronic Rhinosinusitis With Nasal Polyps` | 11 | Not aliased | Added `crswnp` as new indication |
| `CRSwNP` | — | Not aliased | Added as abbreviation alias |
| `Nasal Polyps` | — | Not aliased | Added as synonym alias |
| `Crohn Disease (CD)` | — | Resolves via paren strip → `crohn disease` | Resolves correctly |
| `Multifocal Motor Neuropathy (MMN)` | 2 | Not in scope | Left OOS |
| `Prurigo Nodularis` | 2 | Not in scope | Left OOS |

---

## Governance Rules (standing)

1. **Severity ≠ indication** — `Severe Asthma`, `Moderate-to-Severe Atopic Dermatitis`, etc. normalize to the base indication (`asthma`, `ad`). Severity is a patient selection criterion, not a distinct disease entity.
2. **Orbital manifestations of Graves' disease = TED** — `Graves' Orbitopathy`, `Thyroid-Associated Ophthalmopathy` → `ted`.
3. **CRSwNP ≠ Asthma** — despite type 2 biology overlap and comorbidity, CRSwNP is a distinct clinical indication with separate regulatory pathway.
4. **Healthy volunteers = always exclude** — no indication assignment regardless of other string content.
5. **OOS = exclude, not force-assign** — never map an oncology or metabolic string to an immunology indication for coverage inflation.
