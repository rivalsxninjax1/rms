/* storefront/static/storefront/app.js
 * Session auth + Cart in server session + Auth-gated checkout
 * - Guests can add to cart (session-based)
 * - Checkout requires login (modal, then resume)
 * - Coupons optional via localStorage (UI-only)
 * - No JWT required
 */

/* ===========================
 * Utilities
 * =========================== */
function currency(amount){
  const cur = (window.DEFAULT_CURRENCY || "NPR");
  return `${cur} ${Number(amount||0).toFixed(2)}`;
}
function getCookie(name){
  const m = document.cookie.match(new RegExp("(^| )"+name+"=([^;]+)"));
  return m ? decodeURIComponent(m[2]) : "";
}

/* ===========================
 * Session auth helpers
 * =========================== */
async function whoami(){
  try{
    const r = await fetch("/accounts/auth/whoami/", { credentials:"include" });
    const j = await r.json().catch(()=>({authenticated:false}));
    return j;
  }catch{return {authenticated:false};}
}
async function isAuthenticated(){ const j = await whoami(); return !!j.authenticated; }

/* Auth modal helpers */
const modalEl = () => document.getElementById("auth-modal");
function show(step){
  ["choice","login","signup"].forEach(s=>{
    const el=document.getElementById("auth-step-"+s);
    if(el) el.classList.toggle("hidden", s!==step);
  });
}
function openAuth(step="login"){
  const m=modalEl();
  if(!m){
    const next = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.href = `/accounts/login/?next=${next}`;
    return;
  }
  m.classList.remove("hidden"); m.setAttribute("aria-hidden","false"); show(step);
}
function closeAuth(){ const m=modalEl(); if(!m) return; m.classList.add("hidden"); m.setAttribute("aria-hidden","true"); }

/* Resume a protected action after login */
let _pendingAction = null;
function requireLoginThen(doFn){
  return isAuthenticated().then(ok=>{
    if (ok) return doFn();
    _pendingAction = doFn; openAuth("login");
  });
}

/* ===========================
 * Server Cart API (session)
 * =========================== */
async function cartApiGet(){
  const r = await fetch("/api/orders/cart/", { credentials: "include" });
  if (!r.ok) return { items: [], subtotal: "0.00", currency: "NPR", meta: {} };
  return await r.json();
}
async function cartApiAdd(id, qty){
  await fetch("/api/orders/cart/items/", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie("csrftoken") },
    credentials: "include",
    body: JSON.stringify({ id, quantity: qty }),
  });
}
async function cartApiRemove(id){
  await fetch("/api/orders/cart/items/remove/", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie("csrftoken") },
    credentials: "include",
    body: JSON.stringify({ id }),
  });
}
async function cartApiReset(){
  await fetch("/api/orders/cart/reset_session/", {
    method: "POST",
    headers: { "X-CSRFToken": getCookie("csrftoken") },
    credentials: "include",
  });
}
async function cartApiMergeAfterLogin(){
  await fetch("/api/orders/cart/merge/", {
    method: "POST",
    headers: { "X-CSRFToken": getCookie("csrftoken") },
    credentials: "include",
  });
}

/* ===========================
 * Coupon helpers (optional: UI-only)
 * =========================== */
const COUPON_KEY = "applied_coupon";
function getAppliedCoupon(){ try{ return JSON.parse(localStorage.getItem(COUPON_KEY) || "null"); }catch{return null;} }
function setAppliedCoupon(c){ localStorage.setItem(COUPON_KEY, JSON.stringify(c)); }
function clearAppliedCoupon(){ localStorage.removeItem(COUPON_KEY); }

/* ===========================
 * Cart rendering (server session is source-of-truth)
 * =========================== */
async function updateCartBadge(){
  try{
    const data = await cartApiGet();
    const count = (data.items||[]).reduce((a,i)=> a + Number(i.quantity||0), 0);
    const el=document.getElementById("cart-count");
    if(el) el.textContent = String(count || 0);
    const payBtn=document.querySelector("#pay-btn, [data-checkout], [data-checkout-endpoint]");
    if (payBtn) payBtn.disabled = (count === 0);
  }catch{}
}

async function renderCart(){
  const holder = document.getElementById("cart-items") || document.getElementById("cart");
  if(!holder){ await updateCartBadge(); return; }

  const data = await cartApiGet();
  const items = Array.isArray(data.items) ? data.items : [];

  if(!items.length){
    holder.innerHTML = `<p>Your cart is empty.</p>`;
    await updateCartBadge();
    return;
  }

  const applied = getAppliedCoupon();
  const subtotal = items.reduce((s,i)=> s + Number(i.unit_price||0) * Number(i.quantity||0), 0);
  const discount = applied ? (subtotal * (Number(applied.percent_off||0)/100)) : 0;
  const grand = Math.max(0, subtotal - discount);

  let html = `<div class="cart-list">`;
  items.forEach(i => {
    html += `
      <div class="cart-row" data-id="${i.id}" style="display:grid;grid-template-columns:72px 1fr auto;gap:12px;align-items:center;padding:10px 0;border-bottom:1px solid #eee;">
        <div style="width:72px;height:72px;background:#f7f7f7;border-radius:8px;overflow:hidden;display:flex;align-items:center;justify-content:center;">
          ${i.image ? `<img src="${i.image}" alt="${i.name}" style="width:100%;height:100%;object-fit:cover;">` : `<div style="opacity:.6;">No image</div>`}
        </div>
        <div>
          <div style="font-weight:600;margin-bottom:4px;">${i.name}</div>
          <div style="color:#555;">${currency(Number(i.unit_price||0))}</div>
          <div style="margin-top:8px;display:flex;align-items:center;gap:6px;">
            <button class="qty-dec" data-id="${i.id}" type="button">−</button>
            <input class="qty-input" data-id="${i.id}" type="number" min="1" value="${i.quantity}" style="width:60px;">
            <button class="qty-inc" data-id="${i.id}" type="button">+</button>
            <button class="remove-item" data-id="${i.id}" style="margin-left:8px;" type="button">Remove</button>
          </div>
        </div>
        <div style="font-weight:600;">${currency(Number(i.unit_price||0) * Number(i.quantity||0))}</div>
      </div>
    `;
  });
  html += `</div>`;

  // Coupon UI
  html += `
    <div id="coupon-box" style="margin-top:16px;padding:12px;border:1px dashed #ddd;border-radius:8px;">
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
        <input id="coupon-input" type="text" placeholder="Have a coupon or phrase?" style="padding:8px;border:1px solid #ccc;border-radius:6px;min-width:220px;" ${applied ? 'value="'+(applied.code||'')+'"' : ''} />
        <button id="apply-coupon-btn" type="button" class="btn btn-secondary">Apply</button>
        ${applied ? `<button id="remove-coupon-btn" type="button" class="btn">Remove</button>` : ``}
        <span id="coupon-status" style="margin-left:6px;color:#666;"></span>
      </div>
    </div>
  `;

  // Totals
  html += `
    <div style="display:flex;flex-direction:column;align-items:flex-end;margin-top:16px;gap:6px;">
      <div style="font-size:15px;">Subtotal: <strong>${currency(subtotal)}</strong></div>
      ${applied ? `<div style="font-size:15px;">Coupon <strong>${(applied.code||'').toUpperCase()}</strong> (-${Number(applied.percent_off)}%): <strong>- ${currency(discount)}</strong></div>` : ``}
      <div style="font-size:18px;font-weight:700;">Grand Total: ${currency(grand)}</div>
    </div>
  `;

  holder.innerHTML = html;
  await updateCartBadge();
}

/* Apply/Remove coupon helpers */
async function applyCouponFromInput(){
  const input = document.getElementById("coupon-input");
  const status = document.getElementById("coupon-status");
  if(!input) return;
  const code = (input.value || "").trim();
  if(!code){ status && (status.textContent = "Enter a code/phrase."); return; }

  try{
    const res = await fetch(`/coupons/validate/?code=${encodeURIComponent(code)}`, {credentials:"include"});
    const data = await res.json().catch(()=>({}));
    if(res.ok && data && data.valid){
      setAppliedCoupon({ code, percent_off: Number(data.percent) });
      status && (status.textContent = "Applied!");
      renderCart();
    }else{
      clearAppliedCoupon();
      status && (status.textContent = (data.message || "Invalid/expired code."));
      renderCart();
    }
  }catch{
    const status = document.getElementById("coupon-status");
    if(status) status.textContent = "Server error.";
  }
}

/* ===========================
 * Checkout (auth-gated)
 * =========================== */
async function beginCheckoutFlow(){
  // Build order and go to Stripe (server uses session cart)
  const btn = document.querySelector("#pay-btn, [data-checkout], [data-checkout-endpoint]");
  if (!btn) { window.location.reload(); return; }

  const endpoint = btn.getAttribute("data-checkout-endpoint");
  const href     = btn.getAttribute("data-href");
  const applied  = getAppliedCoupon();

  if (endpoint){
    try {
      const payload = {};
      if (applied && applied.code){ payload.coupon = applied.code; }
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie("csrftoken") },
        credentials: "include",
        body: JSON.stringify(payload)
      });
      const data = await res.json().catch(()=>({}));
      if (res.ok && data && (data.url || data.checkout_url)){
        window.location.href = data.url || data.checkout_url; return;
      }
      if (href) window.location.href = href;
    } catch { if (href) window.location.href = href; }
  } else {
    try{
      const res = await fetch("/api/orders/orders/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie("csrftoken") },
        credentials: "include",
        body: JSON.stringify({})
      });
      const data = await res.json().catch(()=>({}));
      if (res.ok && data && (data.checkout_url || data.url)){
        window.location.href = data.checkout_url || data.url; return;
      }
      if (href) window.location.href = href; else window.location.reload();
    }catch{
      if (href) window.location.href = href; else window.location.reload();
    }
  }
}

/* ===========================
 * Header auth state + nav
 * =========================== */
async function refreshHeaderAuth(){
  const linkLogin  = document.getElementById("nav-login") || document.getElementById("auth-link");
  const linkLogout = document.getElementById("nav-logout");
  const linkOrders = document.getElementById("nav-orders") || document.querySelector('a[href="/my-orders/"]');

  const authed = await isAuthenticated();
  if (linkLogin)  linkLogin.style.display  = authed ? "none" : "";
  if (linkLogout) linkLogout.style.display = authed ? "" : "none";
  if (linkOrders) linkOrders.style.display = authed ? "" : "none";

  if (linkLogin && !linkLogin._bound){
    linkLogin._bound = true;
    linkLogin.addEventListener("click", (e)=>{ e.preventDefault(); openAuth("login"); });
  }

  if (linkLogout && !linkLogout._bound){
    linkLogout._bound = true;
    linkLogout.addEventListener("click", async (e)=>{
      e.preventDefault();
      try { await fetch("/accounts/logout/", {method:"POST", headers:{"X-CSRFToken": getCookie("csrftoken")}, credentials:"include"}); } catch {}
      try { await cartApiReset(); } catch {}
      try { clearAppliedCoupon(); } catch {}
      await updateCartBadge();
      window.location.href = "/";
    });
  }

  if (linkOrders && !linkOrders._bound2){
    linkOrders._bound2 = true;
    linkOrders.addEventListener("click", (e)=>{
      e.preventDefault();
      requireLoginThen(async ()=>{ window.location.href = "/my-orders/"; });
    });
  }
}

/* ===========================
 * Events
 * =========================== */
document.addEventListener("click", async (e) => {
  // Add-to-cart
  const btn = e.target.closest(".add-to-cart");
  if (btn){
    const id = Number(btn.getAttribute("data-id"));
    if (id > 0){
      await cartApiAdd(id, 1);
      await renderCart();
    }
  }

  const dec = e.target.closest(".qty-dec");
  const inc = e.target.closest(".qty-inc");
  const rem = e.target.closest(".remove-item");

  if (dec){
    const id = Number(dec.getAttribute("data-id"));
    const data = await cartApiGet();
    const row = (data.items||[]).find(x=> Number(x.id)===id);
    if (row){
      const nextQty = Math.max(0, Number(row.quantity||0)-1);
      if (nextQty===0){ await cartApiRemove(id); }
      else { await cartApiAdd(id, -1); }
      await renderCart();
    }
  }
  if (inc){
    const id = Number(inc.getAttribute("data-id"));
    await cartApiAdd(id, 1);
    await renderCart();
  }
  if (rem){
    const id = Number(rem.getAttribute("data-id"));
    await cartApiRemove(id);
    await renderCart();
  }

  // Checkout button (requires login) — robust selector
  const pay = e.target.closest("#pay-btn, [data-checkout], [data-checkout-endpoint]");
  if (pay){
    e.preventDefault();
    requireLoginThen(beginCheckoutFlow);
  }

  // Coupon apply/remove
  if (e.target && e.target.id === "apply-coupon-btn"){ e.preventDefault(); applyCouponFromInput(); }
  if (e.target && e.target.id === "remove-coupon-btn"){ e.preventDefault(); clearAppliedCoupon(); renderCart(); }
});

document.addEventListener("input", async (e) => {
  const qty = e.target.closest(".qty-input");
  if (qty){
    const id = Number(qty.getAttribute("data-id"));
    let n = Math.max(1, Number(qty.value || 1));
    // Simplest sync: remove then re-add desired qty
    await cartApiRemove(id);
    await cartApiAdd(id, n);
    await renderCart();
  }
});

/* ===========================
 * Bind modal forms (login/signup) and resume pending action
 * =========================== */
function bindAuthModal(){
  const m=modalEl(); if(!m) return;

  const closeBtn = document.getElementById("auth-close");
  if (closeBtn && !closeBtn._bound){ closeBtn._bound = true; closeBtn.addEventListener("click", ()=> closeAuth()); }

  (document.getElementById("btn-open-login")||{}).onclick = ()=>show("login");
  (document.getElementById("btn-open-signup")||{}).onclick = ()=>show("signup");
  (document.getElementById("link-to-signup")||{}).onclick = (e)=>{ e.preventDefault(); show("signup"); };
  (document.getElementById("link-to-login")||{}).onclick = (e)=>{ e.preventDefault(); show("login"); };

  // LOGIN (session)
  const loginForm=document.getElementById("modal-login-form");
  if(loginForm && !loginForm._bound){
    loginForm._bound = true;
    loginForm.addEventListener("submit", async (e)=>{
      e.preventDefault();
      const fd=new FormData(loginForm);
      const body=JSON.stringify({username:fd.get("username"), password:fd.get("password")});
      const r = await fetch("/accounts/login/", {
        method:"POST",
        headers:{"Content-Type":"application/json", "X-CSRFToken": getCookie("csrftoken")},
        credentials:"include",
        body
      });
      const data = await r.json().catch(()=>({}));
      const st=document.getElementById("modal-login-status");
      if(r.ok && data && data.ok){
        try { await cartApiMergeAfterLogin(); } catch {}
        st.textContent=""; closeAuth();
        if (typeof _pendingAction === "function"){ const action = _pendingAction; _pendingAction=null; await action(); }
        await refreshHeaderAuth(); await renderCart();
      } else {
        st.textContent=(data && (data.detail||data.message)) || "Login failed.";
      }
    });
  }

  // SIGNUP (session)
  const signupForm=document.getElementById("modal-signup-form");
  if(signupForm && !signupForm._bound){
    signupForm._bound = true;
    signupForm.addEventListener("submit", async (e)=>{
      e.preventDefault();
      const fd=new FormData(signupForm);
      const payload={
        username:fd.get("username"),
        email:fd.get("email"),
        first_name:fd.get("first_name") || "",
        last_name:fd.get("last_name") || "",
        password:fd.get("password"),
      };
      const res = await fetch("/accounts/register/", {
        method:"POST",
        headers:{"Content-Type":"application/json","X-CSRFToken": getCookie("csrftoken")},
        credentials:"include",
        body: JSON.stringify(payload)
      });
      const data=await res.json().catch(()=>({}));
      const st=document.getElementById("modal-signup-status");
      if(res.ok && data && data.ok){
        try { await cartApiMergeAfterLogin(); } catch {}
        st.textContent=""; closeAuth();
        if (typeof _pendingAction === "function"){ const action = _pendingAction; _pendingAction=null; await action(); }
        await refreshHeaderAuth(); await renderCart();
      } else {
        st.textContent=(data && (data.detail||JSON.stringify(data))) || "Signup failed.";
      }
    });
  }
}

/* ===========================
 * Boot
 * =========================== */
document.addEventListener("DOMContentLoaded", async ()=>{
  bindAuthModal();
  await refreshHeaderAuth();
  await renderCart(); // server session is the single source of truth
});
