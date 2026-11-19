document.addEventListener("DOMContentLoaded",async()=>{
 const content=document.querySelector("#dashboard-content");
 try {const u=await API.me();document.querySelector("#welcome-line").textContent=`Welcome, ${u.name}. Your reports and updates in one place.`;}
 catch(e){content.textContent="Please log in to view your dashboard.";return;}
 const escape=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
 async function show(key){try{let rows;
 if(key==="lost"||key==="found")rows=(await API.myReports())[key];
 else if(key==="notifications")rows=await API.notifications();
 else rows=await API.recovery();
 content.innerHTML=rows.length?rows.map(r=>`<div class="card" style="padding:16px;margin:10px 0"><strong>${escape(r.item_name||r.title||"Recovery request")}</strong><p>${escape(r.report_code||r.message||r.status||"")}</p></div>`).join(""):'<div class="empty-state">No records yet.</div>';
 }catch(e){content.textContent=e.message;}}
 document.querySelectorAll(".tab").forEach(t=>t.addEventListener("click",()=>{document.querySelectorAll(".tab").forEach(x=>x.classList.remove("active"));t.classList.add("active");show(t.dataset.tab)}));
 show(document.querySelector(".tab.active")?.dataset.tab||"lost");
});