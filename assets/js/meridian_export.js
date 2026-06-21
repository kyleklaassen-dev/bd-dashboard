/* ── Meridian → Word export ────────────────────────────────────────────────────
   Download the current Meridian Issue as an EDITABLE Word document so Kyle can
   mark it up and resubmit it for structural improvement. Pure client-side: wraps
   the published issue HTML in a Word-compatible envelope (Word opens HTML .doc
   natively) — no backend, no library, no build step.
   Exposes window.meridianDownloadWord(). ──────────────────────────────────────── */
(function(){
  const SB_URL=(typeof SUPABASE_URL!=='undefined'?SUPABASE_URL:'https://tghntyofptvfhmtchwcv.supabase.co');
  const SB_KEY=(typeof SUPABASE_ANON!=='undefined'?SUPABASE_ANON:'');

  // strip scripts / inline handlers / iframes so the exported doc is clean prose+tables
  function clean(html){
    return String(html||'')
      .replace(/<script[\s\S]*?<\/script>/gi,'')
      .replace(/<iframe[\s\S]*?<\/iframe>/gi,'')
      .replace(/ on[a-z]+="[^"]*"/gi,'')
      .replace(/ on[a-z]+='[^']*'/gi,'');
  }
  function wordBlob(inner,title){
    const head='<html xmlns:o="urn:schemas-microsoft-com:office:office" '
      +'xmlns:w="urn:schemas-microsoft-com:office:word" xmlns="http://www.w3.org/TR/REC-html40">'
      +'<head><meta charset="utf-8"><title>'+title+'</title>'
      +'<!--[if gte mso 9]><xml><w:WordDocument><w:View>Print</w:View><w:Zoom>100</w:Zoom></w:WordDocument></xml><![endif]-->'
      +'<style>'
      +'body{font-family:Georgia,"Times New Roman",serif;font-size:11pt;line-height:1.5;color:#1a1a1a;margin:1in}'
      +'h1{font-size:21pt;color:#0f2740;margin:0 0 4pt} h2{font-size:15pt;color:#1a3f8f;margin:16pt 0 4pt}'
      +'h3{font-size:12.5pt;color:#26384a;margin:12pt 0 3pt} p{margin:0 0 8pt}'
      +'table{border-collapse:collapse;width:100%;margin:8pt 0} td,th{border:1px solid #b9c4d0;padding:5pt 7pt;vertical-align:top;font-size:10pt}'
      +'th{background:#0f2740;color:#fff} a{color:#1a3f8f}'
      +'</style></head><body>';
    return new Blob(['﻿'+head+inner+'</body></html>'],{type:'application/msword'});
  }
  function download(blob,fname){
    const a=document.createElement('a'); const url=URL.createObjectURL(blob);
    a.href=url; a.download=fname; document.body.appendChild(a); a.click();
    setTimeout(function(){ URL.revokeObjectURL(url); a.remove(); },400);
  }

  // Try the live iframe first (shows exactly the issue on screen, incl. archived);
  // fall back to the newest row in meridian_issues.
  async function getIssue(){
    try{
      const fr=document.getElementById('meridian-issue-frame');
      const doc=fr&&fr.contentDocument;
      if(doc&&doc.body&&doc.body.innerHTML&&doc.body.innerHTML.length>500){
        const art=doc.querySelector('article,.issue,.meridian,main')||doc.body;
        const h=doc.querySelector('h1');
        return {html:art.innerHTML, title:(h&&h.textContent)||doc.title||'The Meridian', date:(doc.querySelector('time')||{}).textContent||''};
      }
    }catch(e){ /* cross-origin or not ready — fall back */ }
    const r=await fetch(SB_URL+'/rest/v1/meridian_issues?select=title,issue_date,body_html&order=issue_date.desc&limit=1',
      {headers:{apikey:SB_KEY,Authorization:'Bearer '+SB_KEY}});
    const rows=await r.json();
    if(!rows||!rows.length) throw new Error('no issue found');
    return {html:rows[0].body_html, title:rows[0].title||'The Meridian', date:rows[0].issue_date||''};
  }

  window.meridianDownloadWord=async function(btn){
    const label=btn&&btn.innerHTML;
    try{
      if(btn){ btn.disabled=true; btn.innerHTML='Preparing…'; }
      const iss=await getIssue();
      const dateSlug=(iss.date||new Date().toISOString().slice(0,10)).replace(/[^0-9A-Za-z]/g,'-').slice(0,24);
      const titleBlock='<h1>'+(iss.title||'The Meridian')+'</h1>'+(iss.date?'<p style="color:#64748b;font-style:italic">'+iss.date+'</p>':'');
      const blob=wordBlob(titleBlock+clean(iss.html),iss.title||'The Meridian');
      download(blob,'Meridian_'+dateSlug+'.doc');
    }catch(e){
      alert('Could not export the issue to Word: '+(e&&e.message||e));
    }finally{
      if(btn){ btn.disabled=false; btn.innerHTML=label; }
    }
  };
})();
