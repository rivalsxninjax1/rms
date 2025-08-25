/* storefront/static/storefront/auth-modal.js */
(function () {
  const $ = (sel, el=document) => el.querySelector(sel);
  const modal = $("#auth-modal");
  const stepChoice = $("#auth-step-choice");
  const stepLogin = $("#auth-step-login");
  const stepSignup = $("#auth-step-signup");
  const btnOpenLogin = $("#btn-open-login");
  const btnOpenSignup = $("#btn-open-signup");
  const linkToLogin = $("#link-to-login");
  const linkToSignup = $("#link-to-signup");
  const btnClose = $("#auth-close");
  const loginForm = $("#modal-login-form");
  const signupForm = $("#modal-signup-form");
  const loginStatus = $("#modal-login-status");
  const signupStatus = $("#modal-signup-status");

  function show(which){ stepChoice.classList.toggle("hidden", which!=="choice"); stepLogin.classList.toggle("hidden", which!=="login"); stepSignup.classList.toggle("hidden", which!=="signup"); }
  function openModal(which="login"){ modal.classList.remove("hidden"); show(which); }
  function closeModal(){ modal.classList.add("hidden"); }

  btnOpenLogin?.addEventListener("click", () => openModal("login"));
  btnOpenSignup?.addEventListener("click", () => openModal("signup"));
  linkToLogin?.addEventListener("click", (e) => { e.preventDefault(); show("login"); });
  linkToSignup?.addEventListener("click", (e) => { e.preventDefault(); show("signup"); });
  btnClose?.addEventListener("click", closeModal);
  $("#auth-link")?.addEventListener("click", (e) => { e.preventDefault(); openModal("login"); });

  function setBusy(el, busy){ if(!el) return; el.disabled = !!busy; el.classList.toggle("is-busy", !!busy); }

  async function jwtLogin(username, password){
    const res = await fetch("/accounts/auth/login/", { method:"POST", headers:{ "Content-Type":"application/json" }, credentials:"include", body: JSON.stringify({ username, password }) });
    const data = await res.json().catch(()=>({}));
    if(!res.ok) throw new Error(data.detail || "Login failed");
    if (window.auth && typeof window.auth.set === "function") window.auth.set(data.access, data.refresh);
    else { localStorage.setItem("jwt_access", data.access||""); localStorage.setItem("jwt_refresh", data.refresh||""); }
  }

  async function createSessionAndMerge(){
    const tok = localStorage.getItem("jwt_access") || "";
    if(!tok) return;
    await fetch("/accounts/auth/session/", { method:"POST", headers:{ "Authorization":"Bearer "+tok }, credentials:"include" });
    await fetch("/api/orders/cart/merge/", { method:"POST", credentials:"include" });
  }

  async function afterAuthContinueCheckout(){
    if (typeof window.__continueCheckoutAfterAuth === "function") await window.__continueCheckoutAfterAuth();
  }

  loginForm?.addEventListener("submit", async (e) => {
    e.preventDefault(); loginStatus.textContent="Logging in…";
    setBusy(loginForm.querySelector("button[type=submit]"), true);
    const f = new FormData(loginForm);
    try { await jwtLogin(f.get("username"), f.get("password")); await createSessionAndMerge(); loginStatus.textContent="Success!"; modal.classList.add("hidden"); await afterAuthContinueCheckout(); }
    catch (err) { loginStatus.textContent = (err && err.message) || "Login failed."; }
    finally { setBusy(loginForm.querySelector("button[type=submit]"), false); }
  });

  signupForm?.addEventListener("submit", async (e) => {
    e.preventDefault(); signupStatus.textContent="Creating account…";
    setBusy(signupForm.querySelector("button[type=submit]"), true);
    const f = new FormData(signupForm);
    const payload = { username:f.get("username"), email:f.get("email"), first_name:f.get("first_name")||"", last_name:f.get("last_name")||"", password:f.get("password") };
    try {
      const r = await fetch("/accounts/auth/register/", { method:"POST", headers:{ "Content-Type":"application/json" }, credentials:"include", body: JSON.stringify(payload) });
      const d = await r.json().catch(()=>({}));
      if(!r.ok) throw new Error(d.detail || d.username || d.email || "Signup failed");
      await jwtLogin(payload.username, payload.password); await createSessionAndMerge();
      signupStatus.textContent="Account created!"; modal.classList.add("hidden"); await afterAuthContinueCheckout();
    } catch (err) { signupStatus.textContent = (err && err.message) || "Signup failed."; }
    finally { setBusy(signupForm.querySelector("button[type=submit]"), false); }
  });

  document.addEventListener("keydown", (e)=>{ if(e.key==="Escape") modal.classList.add("hidden"); });
  window.__openAuthModalForPay = () => openModal("login");
})();
