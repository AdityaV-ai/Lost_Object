document.addEventListener("DOMContentLoaded", () => {
  const login = document.querySelector("#login-form");
  const register = document.querySelector("#register-form");
  const show = (form, msg, kind="error") => { const el=form.querySelector(".form-message"); el.textContent=msg; el.className=`form-message ${kind}`; };
  if (login) login.addEventListener("submit", async e => {
    e.preventDefault(); const btn=login.querySelector("button"); btn.disabled=true; btn.textContent="Signing in…";
    const data=Object.fromEntries(new FormData(login).entries());
    try { await API.login(data); location.href="dashboard.html"; }
    catch(err) { show(login, err.message); }
    finally { btn.disabled=false; btn.innerHTML='Log in <span>→</span>'; }
  });
  if (register) register.addEventListener("submit", async e => {
    e.preventDefault(); const data=Object.fromEntries(new FormData(register).entries());
    if(data.password!==data.confirm_password) return show(register,"Passwords do not match.");
    if(data.password.length<8) return show(register,"Password must contain at least 8 characters.");
    delete data.confirm_password; const btn=register.querySelector("button"); btn.disabled=true; btn.textContent="Creating account…";
    try { await API.register(data); location.href="dashboard.html"; }
    catch(err) { show(register,err.message); }
    finally { btn.disabled=false; btn.innerHTML='Create account <span>→</span>'; }
  });
});