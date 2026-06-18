#!/usr/bin/env python3
"""
Publish + post-publish bookkeeping for the Meridian Issue (§3 write_meridian split).
====================================================================================
Extracted verbatim from write_meridian.py:
  - sync_catalyst_outcomes: resolve catalysts matched by today's intel (CatalystWriter).
  - inject_feedback_widget: embed the in-issue feedback widget (anon-key, write-only).
  - deploy_to_github: commit meridian_today.html to GitHub Pages via the blob API.
  - bump_editorial_priority: raise enrichment priority for companies featured today.
"""

import datetime
import base64

import requests

from meridian.products.issue.common import (
    SUPABASE_URL, SUPABASE_ANON_KEY, SB_HEADERS, GH_HEADERS, GITHUB_REPO, log,
)
from meridian.database.catalyst_writer import CatalystWriter
import os


# ── Commit HTML to GitHub Pages via blob API ─────────────────────────────────
def sync_catalyst_outcomes(plan: dict, intel: list):
    """
    G4 Feedback Loop: After generating the Issue, scan recent intel for confirmed
    data readouts and mark matching catalysts as resolved in Supabase.

    Logic:
      1. Build a set of drug/company names that had data events this week
         (intel items with catalyst_type='readout' or importance='high' + keywords)
      2. For each, find unresolved catalysts in the DB for that drug/company
      3. If the catalyst label matches the intel signal, mark resolved

    This closes the loop: Issue reads catalysts → Issue generates → Issue resolves
    catalysts that are now confirmed events.
    """
    if not plan or not intel:
        return

    # Keywords that indicate a catalyst resolved
    RESOLVE_SIGNALS = [
        "positive", "met primary", "statistically significant", "approved",
        "phase 3 complete", "topline", "data readout", "presented at",
        "published", "fda approved", "ema approved", "nda filed", "bla filed",
        "phase 2b results", "phase 3 results", "pivotal trial",
    ]

    resolved_count = 0
    now_str = datetime.datetime.utcnow().isoformat()

    # Build drug name → drug_id mapping from plan
    drug_signals: dict[str, str] = {}  # drug_name_lower → drug_id
    company_signals: list[str] = []    # company_ids featured

    if isinstance(plan, dict):
        for section in plan.get("sections", []):
            for drug_id in section.get("drug_ids", []):
                drug_signals[drug_id.lower()] = drug_id
            for co_id in section.get("company_ids", []):
                company_signals.append(co_id)

    # Scan recent intel for resolution signals
    for item in intel:
        headline = (item.get("headline") or "").lower()
        body = (item.get("body") or "").lower()
        text = headline + " " + body

        # Check if this intel item confirms a catalyst resolved
        has_signal = any(kw in text for kw in RESOLVE_SIGNALS)
        if not has_signal:
            continue

        importance = item.get("importance", "")
        if importance not in ("high", "critical"):
            continue

        # Find drug IDs mentioned in this intel item
        for drug_id in drug_signals.values():
            if drug_id.lower() in text or drug_id.replace("-", " ").lower() in text:
                # Look for unresolved catalysts for this drug
                try:
                    r = requests.get(
                        f"{SUPABASE_URL}/rest/v1/catalysts",
                        headers=SB_HEADERS,
                        params={
                            "drug_id": f"eq.{drug_id}",
                            "resolved": "eq.false",
                            "significance": "in.(high,critical)",
                            "select": "id,label,drug_id",
                            "limit": "5",
                        },
                        timeout=10,
                    )
                    cats = r.json() if r.status_code == 200 else []
                    for cat in cats:
                        cat_label = (cat.get("label") or "").lower()
                        # Only resolve if there's label overlap with the intel headline
                        label_words = set(cat_label.split())
                        headline_words = set(headline.split())
                        overlap = label_words & headline_words - {"a","the","in","of","for","and","with","or","to","from"}
                        if len(overlap) >= 2:  # meaningful overlap
                            outcome = (item.get("headline") or "")[:200]
                            CatalystWriter().upsert({"id": cat["id"], "resolved": True,
                                "resolved_note": f"[auto] Meridian Issue: {outcome}",
                                "catalyst_status": "resolved", "staleness_status": "stale"})
                            log(f"  [sync_catalyst] Resolved catalyst for {drug_id}: {cat['label'][:60]}")
                            resolved_count += 1
                except Exception as e:
                    log(f"  [sync_catalyst warn] {drug_id}: {e}")

    if resolved_count:
        log(f"sync_catalyst_outcomes: resolved {resolved_count} catalysts from today's intel")
    else:
        log("sync_catalyst_outcomes: no matching resolved catalysts (normal — most issues are monitoring, not readout)")


def inject_feedback_widget(html, issue_date):
    """Inject the in-issue reader-feedback widget (per-section 👍/👎 + notes, inline
    selection comments, and an overall feedback panel) into the generated issue HTML.

    Lives ONLY inside the Meridian issue document — which renders solely in the
    'Today's Issue' tab (iframe → meridian_today.html / srcdoc for archived issues).
    The home tab uses a separate reader list and never embeds this document, so the
    widget never appears on the home page.

    Writes go to public.meridian_feedback with the PUBLIC anon key (write-only via RLS).
    Hidden in print. Fails silent if Supabase is unreachable.
    """
    css = """
<style id="mf-styles">
.mf-ctl{display:inline-flex;gap:6px;align-items:center;margin:8px 0 2px;vertical-align:middle;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}
.mf-btn{cursor:pointer;border:1px solid #d9dee8;background:#fff;border-radius:7px;padding:2px 9px;font-size:12px;line-height:1.5;color:#64748b;transition:all .12s;user-select:none}
.mf-btn:hover{border-color:#a78bfa;color:#6d28d9}
.mf-btn.mf-on-up{background:#ecfdf5;border-color:#10b981;color:#047857}
.mf-btn.mf-on-down{background:#fef2f2;border-color:#ef4444;color:#b91c1c}
.mf-note-wrap{margin:6px 0 12px;display:none}
.mf-note-wrap.mf-open{display:block}
.mf-ta{width:100%;max-width:640px;min-height:54px;border:1px solid #d9dee8;border-radius:8px;padding:8px 10px;font:13px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;resize:vertical;display:block}
.mf-save{margin-top:6px;cursor:pointer;border:none;background:#6d28d9;color:#fff;border-radius:7px;padding:5px 13px;font-size:12px;font-weight:600}
.mf-save:hover{background:#5b21b6}
.mf-sel-pop{position:absolute;z-index:99999;display:none;background:#0d1f38;border-radius:8px;box-shadow:0 6px 20px rgba(0,0,0,.25)}
.mf-sel-pop button{cursor:pointer;border:none;background:transparent;color:#fff;font-size:12px;font-weight:600;padding:6px 11px}
.mf-toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#0d1f38;color:#fff;padding:9px 16px;border-radius:9px;font:13px -apple-system,sans-serif;opacity:0;transition:opacity .2s;z-index:99999;pointer-events:none}
.mf-toast.mf-show{opacity:1}
.mf-fab{position:fixed;bottom:18px;right:18px;z-index:99998;background:#6d28d9;color:#fff;border:none;border-radius:24px;padding:10px 16px;font:600 13px -apple-system,sans-serif;cursor:pointer;box-shadow:0 6px 18px rgba(109,40,217,.35)}
.mf-panel{position:fixed;bottom:64px;right:18px;z-index:99998;width:320px;max-width:90vw;background:#fff;border:1px solid #e2e8f0;border-radius:12px;box-shadow:0 12px 40px rgba(2,6,23,.2);padding:14px;display:none}
.mf-panel.mf-open{display:block}
.mf-panel h4{font:700 13px -apple-system,sans-serif;color:#0d1f38;margin:0 0 8px}
@media print{.mf-ctl,.mf-fab,.mf-panel,.mf-sel-pop,.mf-toast,.mf-note-wrap{display:none!important}}
</style>
"""
    js = """
<script id="mf-feedback">
(function(){
  var SB="%%URL%%",KEY="%%KEY%%",ISSUE_DATE="%%DATE%%";
  function post(b){b.issue_date=ISSUE_DATE;b.issue_id=(window.__MERIDIAN_ISSUE_ID__||null);b.page_url=location.href;b.user_agent=(navigator.userAgent||"").slice(0,300);
    return fetch(SB+"/rest/v1/meridian_feedback",{method:"POST",headers:{"apikey":KEY,"Authorization":"Bearer "+KEY,"Content-Type":"application/json","Prefer":"return=minimal"},body:JSON.stringify(b)});}
  function toast(m){var t=document.querySelector(".mf-toast");if(!t){t=document.createElement("div");t.className="mf-toast";document.body.appendChild(t);}t.textContent=m;t.classList.add("mf-show");setTimeout(function(){t.classList.remove("mf-show");},1700);}
  function lbl(h){return (h.textContent||"").trim().replace(/\\s+/g," ").slice(0,180);}
  function attach(h,idx){
    if(h.getAttribute("data-mf"))return;h.setAttribute("data-mf","1");
    var ctl=document.createElement("div");ctl.className="mf-ctl";
    var up=document.createElement("span");up.className="mf-btn";up.textContent="\\uD83D\\uDC4D";up.title="Helpful";
    var dn=document.createElement("span");dn.className="mf-btn";dn.textContent="\\uD83D\\uDC4E";dn.title="Not useful";
    var nb=document.createElement("span");nb.className="mf-btn";nb.textContent="\\uD83D\\uDCAC note";
    var wrap=document.createElement("div");wrap.className="mf-note-wrap";
    var ta=document.createElement("textarea");ta.className="mf-ta";ta.placeholder="What works or doesn't in this section?";
    var sv=document.createElement("button");sv.className="mf-save";sv.textContent="Save note";
    wrap.appendChild(ta);wrap.appendChild(sv);
    up.onclick=function(){post({section_index:idx,section_label:lbl(h),vote:"up"}).then(function(r){if(r.ok){up.classList.add("mf-on-up");dn.classList.remove("mf-on-down");toast("Marked helpful");}else toast("Couldn't save");}).catch(function(){toast("Couldn't save");});};
    dn.onclick=function(){post({section_index:idx,section_label:lbl(h),vote:"down"}).then(function(r){if(r.ok){dn.classList.add("mf-on-down");up.classList.remove("mf-on-up");toast("Marked not useful");}else toast("Couldn't save");}).catch(function(){toast("Couldn't save");});};
    nb.onclick=function(){wrap.classList.toggle("mf-open");if(wrap.classList.contains("mf-open"))ta.focus();};
    sv.onclick=function(){var c=ta.value.trim();if(!c){toast("Write a note first");return;}post({section_index:idx,section_label:lbl(h),comment:c}).then(function(r){if(r.ok){toast("Note saved");ta.value="";wrap.classList.remove("mf-open");}else toast("Couldn't save");}).catch(function(){toast("Couldn't save");});};
    ctl.appendChild(up);ctl.appendChild(dn);ctl.appendChild(nb);
    h.parentNode.insertBefore(ctl,h.nextSibling);h.parentNode.insertBefore(wrap,ctl.nextSibling);
  }
  function init(){
    var hs=document.querySelectorAll("h2,h3");for(var i=0;i<hs.length;i++)attach(hs[i],i);
    var pop=document.createElement("div");pop.className="mf-sel-pop";var pb=document.createElement("button");pb.textContent="\\uD83D\\uDCAC Comment";pop.appendChild(pb);document.body.appendChild(pop);
    var lastSel="";
    document.addEventListener("mouseup",function(){setTimeout(function(){var s=window.getSelection();var t=s&&s.toString().trim();
      if(t&&t.length>3&&t.length<800){lastSel=t;var r=s.getRangeAt(0).getBoundingClientRect();pop.style.top=(window.scrollY+r.top-40)+"px";pop.style.left=(window.scrollX+r.left)+"px";pop.style.display="block";}
      else if(!pop.contains(document.activeElement))pop.style.display="none";},10);});
    pb.onclick=function(){var c=prompt("Comment on:\\n\\n\\u201c"+lastSel.slice(0,160)+(lastSel.length>160?"\\u2026":"")+"\\u201d\\n\\nYour note:");
      if(c&&c.trim())post({section_label:"(inline selection)",selected_text:lastSel.slice(0,800),comment:c.trim()}).then(function(r){toast(r.ok?"Comment saved":"Couldn't save");}).catch(function(){toast("Couldn't save");});pop.style.display="none";};
    var fab=document.createElement("button");fab.className="mf-fab";fab.textContent="\\uD83D\\uDCAC Feedback";document.body.appendChild(fab);
    var panel=document.createElement("div");panel.className="mf-panel";panel.innerHTML="<h4>Feedback on this issue</h4>";
    var pta=document.createElement("textarea");pta.className="mf-ta";pta.placeholder="Overall thoughts on today's issue\\u2026";
    var psv=document.createElement("button");psv.className="mf-save";psv.textContent="Send";
    panel.appendChild(pta);panel.appendChild(psv);document.body.appendChild(panel);
    fab.onclick=function(){panel.classList.toggle("mf-open");if(panel.classList.contains("mf-open"))pta.focus();};
    psv.onclick=function(){var c=pta.value.trim();if(!c){toast("Write something first");return;}post({section_label:"(overall)",comment:c}).then(function(r){if(r.ok){toast("Thanks \\u2014 feedback sent");pta.value="";panel.classList.remove("mf-open");}else toast("Couldn't save");}).catch(function(){toast("Couldn't save");});};
  }
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);else init();
})();
</script>
"""
    js = (js.replace("%%URL%%", SUPABASE_URL)
            .replace("%%KEY%%", SUPABASE_ANON_KEY)
            .replace("%%DATE%%", issue_date))
    if "</head>" in html:
        html = html.replace("</head>", css + "</head>", 1)
    else:
        html = css + html
    if "</body>" in html:
        html = html.replace("</body>", js + "</body>", 1)
    else:
        html = html + js
    return html


def deploy_to_github(html_content, filename="meridian_today.html"):
    api = f"https://api.github.com/repos/{GITHUB_REPO}"
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")

    ref_r = requests.get(f"{api}/git/ref/heads/main", headers=GH_HEADERS)
    ref_r.raise_for_status()
    head_sha = ref_r.json()["object"]["sha"]

    # ── Guard: skip if today's issue was already committed ────────────────────
    # Checks the last commit touching meridian_today.html. If it already
    # has today's date in the message, this is a duplicate run — skip.
    import sys as _sys
    _force = ("--force" in _sys.argv) or (os.environ.get("MERIDIAN_FORCE", "").lower() in ("1", "true", "yes"))
    try:
        recent = requests.get(
            f"https://api.github.com/repos/{GITHUB_REPO}/commits",
            headers=GH_HEADERS,
            params={"path": filename, "per_page": 1},
            timeout=10,
        )
        if recent.status_code == 200 and recent.json():
            last_msg = recent.json()[0]["commit"]["message"]
            if today in last_msg and "[auto]" in last_msg and not _force:
                log(f"Skipping deploy — today's issue already committed ({last_msg[:60]}). "
                    f"Use workflow_dispatch with force=true to override.")
                return
            if _force and today in last_msg:
                log("Force flag set — re-deploying over today's existing issue commit.")
    except Exception as _guard_err:
        log(f"[WARN] Could not check last commit: {_guard_err} — proceeding with deploy")

    commit_r = requests.get(f"{api}/git/commits/{head_sha}", headers=GH_HEADERS)
    commit_r.raise_for_status()
    base_tree_sha = commit_r.json()["tree"]["sha"]

    blob_r = requests.post(f"{api}/git/blobs", headers=GH_HEADERS, json={
        "content":  base64.b64encode(html_content.encode()).decode(),
        "encoding": "base64",
    })
    blob_r.raise_for_status()
    blob_sha = blob_r.json()["sha"]

    tree_r = requests.post(f"{api}/git/trees", headers=GH_HEADERS, json={
        "base_tree": base_tree_sha,
        "tree": [{"path": filename, "mode": "100644", "type": "blob", "sha": blob_sha}],
    })
    tree_r.raise_for_status()
    new_tree_sha = tree_r.json()["sha"]

    commit_post = requests.post(f"{api}/git/commits", headers=GH_HEADERS, json={
        "message": f"Meridian issue {today} [auto]",
        "tree":    new_tree_sha,
        "parents": [head_sha],
    })
    commit_post.raise_for_status()
    new_commit_sha = commit_post.json()["sha"]

    patch_r = requests.patch(f"{api}/git/refs/heads/main", headers=GH_HEADERS, json={
        "sha": new_commit_sha, "force": False,
    })
    patch_r.raise_for_status()
    log(f"Deployed {filename} → commit {new_commit_sha[:7]}")


# ── Editorial → Enrichment Priority Bump ─────────────────────────────────────
def bump_editorial_priority(company_ids: list, boost: int = 10):
    """
    Bump priority_score for companies featured in today's Meridian.

    Meridian editorial judgment is the strongest signal for BD relevance.
    If a company appears in the briefing, it should be among the first to
    re-enrich. This function finds the company's research_queue row and
    applies a +boost to priority_score, capped at 100.

    Falls back gracefully: if research_queue doesn't have a row for a company,
    no error is raised.
    """
    if not company_ids:
        return

    bumped = []
    errors = []
    for co_id in company_ids:
        try:
            r = requests.get(
                f"{SUPABASE_URL}/rest/v1/research_queue",
                headers=SB_HEADERS,
                params={"company_id": f"eq.{co_id}", "select": "id,company_id,priority_score", "limit": "1"},
                timeout=10,
            )
            rows = r.json() if r.status_code == 200 else []
            if not rows:
                continue  # Company not in research_queue — skip silently

            row = rows[0]
            current_score = row.get("priority_score") or 0
            new_score     = min(100, current_score + boost)

            patch_r = requests.patch(
                f"{SUPABASE_URL}/rest/v1/research_queue",
                headers={**SB_HEADERS, "Prefer": "return=minimal"},
                params={"id": f"eq.{row['id']}"},
                json={"priority_score": new_score, "updated_at": datetime.datetime.utcnow().isoformat()},
                timeout=10,
            )
            if patch_r.status_code in (200, 204):
                bumped.append(f"{co_id}:{current_score}→{new_score}")
        except Exception as e:
            errors.append(f"{co_id}: {e}")

    if bumped:
        log(f"Editorial priority bumps (+{boost}): {', '.join(bumped)}")
    if errors:
        log(f"Priority bump errors (non-fatal): {'; '.join(errors)}")
