document.addEventListener("DOMContentLoaded",async()=>{
 const escape=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
 const detail=document.querySelector("#match-detail-content");
 const id=new URLSearchParams(location.search).get("id");
 try{
 if(detail&&id){const m=await API.match(id);detail.innerHTML=`<h3>${escape(m.found_item_name)}</h3><p>Related lost report: ${escape(m.lost_report.report_code)}</p><p>Relevance score: ${(m.fusion_score*100).toFixed(1)}% (not ownership probability)</p><button id="interest-btn" class="btn btn-primary">Express interest</button>`;document.querySelector("#interest-btn").onclick=async()=>{await API.interest(id);document.querySelector("#interest-btn").textContent="Interest submitted";};}
 else{const el=document.querySelector("#matches-content")||document.querySelector("#matches-list");if(el){const rows=await API.matches();el.innerHTML=rows.length?rows.map(m=>`<a href="match-detail.html?id=${m.id}" class="card" style="display:block;padding:16px;margin:12px 0">${escape(m.found_item_name)} — ${(m.fusion_score*100).toFixed(1)}% relevance</a>`).join(""):'<div class="empty-state">No potential matches yet.</div>';}}
 }catch(e){if(detail)detail.textContent=e.message;}
});