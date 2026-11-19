document.addEventListener("DOMContentLoaded", async () => {
  const mount=document.querySelector("#app-header");
  if(mount){
    mount.innerHTML=`<header class="site-header"><a class="brand" href="index.html"><span class="brand-mark">F</span><span>FindBack<small>Campus Lost & Found</small></span></a><nav><a href="dashboard.html">Dashboard</a><a href="report-lost.html">Report lost</a><a href="report-found.html">Report found</a></nav><div class="nav-actions"><span class="user-chip" id="user-chip">Account</span><button class="btn btn-ghost" id="logout-btn">Log out</button></div></header>`;
    document.querySelector("#logout-btn").addEventListener("click",async()=>{try{await API.logout()}catch(e){} location.href="index.html"});
    try{const u=await API.me();document.querySelector("#user-chip").textContent=u.name||u.email||"Account"}catch(e){document.querySelector("#user-chip").textContent="Guest"}
  }
  document.querySelectorAll('input[type="file"]').forEach(input=>input.addEventListener("change",()=>{
    const preview=document.querySelector(`#${input.id || (input.name==="image" ? (input.closest("#found-form")?"found-preview":"lost-preview"):"")}`);
    if(!preview)return;
    const file=input.files[0]; if(!file){preview.classList.add("hidden");return;}
    if(file.size>5*1024*1024){input.value="";preview.classList.add("hidden");alert("Please choose an image smaller than 5 MB.");return;}
    preview.src=URL.createObjectURL(file);preview.classList.remove("hidden");
  }));
});