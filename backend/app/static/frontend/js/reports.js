document.addEventListener("DOMContentLoaded",()=>{
  const lost=document.querySelector("#lost-form"), found=document.querySelector("#found-form");
  const message=(form,text,kind="error")=>{const el=form.querySelector(".form-message");el.textContent=text;el.className=`form-message ${kind}`};
  if(lost)lost.addEventListener("submit",async e=>{
    e.preventDefault();const fd=new FormData(lost);const data=fd;

    const btn=lost.querySelector('button[type="submit"]');btn.disabled=true;btn.textContent="Submitting…";
    try{const result=await API.createLost(data);message(lost,`Report submitted successfully. Reference: ${result.report_code}`,"success");lost.reset();}
    catch(err){message(lost,err.status===401?"Please log in before submitting a report.":err.message);}
    finally{btn.disabled=false;btn.textContent="Submit lost report →";}
  });
  if(found){
    found.querySelectorAll('input[name="custody_status"]').forEach(r=>r.addEventListener("change",()=>document.querySelector("#deposit-note").classList.toggle("hidden",r.value!=="AWAITING_DEPOSIT_CONFIRMATION"||!r.checked)));
    found.addEventListener("submit",async e=>{
      e.preventDefault();const fd=new FormData(found);const file=fd.get("image");
      if(!file||!file.size){message(found,"Please select an image.");return;}
      if(file.size>5*1024*1024){message(found,"Image must be 5 MB or smaller.");return;}
      const btn=found.querySelector('button[type="submit"]');btn.disabled=true;btn.textContent="Submitting…";
      try{const result=await API.createFound(fd);message(found,`Found report submitted. Reference: ${result.report_code}. Custody status: ${result.custody_status}.`,"success");found.reset();document.querySelector("#found-preview").classList.add("hidden");}
      catch(err){message(found,err.status===401?"Please log in before submitting a report.":err.message);}
      finally{btn.disabled=false;btn.textContent="Submit found report →";}
    });
  }
});