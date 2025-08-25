/* storefront/static/storefront/app.js
 * Auth + Cart + Session bridge + Auth-gated actions (My Orders, Checkout)
 * - Add to cart allowed for guests
 * - My Orders & Checkout require login (opens modal, then resumes the action)
 * - Coupon input + discount display + server-side validation
 * - Cart changes persist to SERVER session; UI cache uses localStorage
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
 * Auth (JWT)
 * =========================== */
const auth = {
  access(){ return localStorage.getItem("jwt_access") || ""; },
  refresh(){ return localStorage.getItem("jwt_refresh") || ""; },
  set(a,r){ if(a) localStorage.setItem("jwt_access", a); if(r) localStorage.setItem("jwt_refresh", r); },
  clear(){ localStorage.removeItem("jwt_access"); localStorage.removeItem("jwt_refresh"); },
};

/* Promote JWT -> Django session so server pages recognize auth */
async function ensureSessionFromJWT(){
  if (!auth.access()) return false;
  try {
    const whoRes = await fetch("/accounts/auth/whoami/", { credentials:"include" });
    const who = await whoRes.json().catch(()=>({authenticated:false}));
    if (who && who.authenticated) return true;

    await fetch("/accounts/auth/session/", {
      method: "POST",
      headers: { "Authorization": "Bearer " + auth.access() },
      credentials: "include",
    });

    const whoRes2 = await fetch("/accounts/auth/whoami/", { credentials:"include" });
    const who2 = await whoRes2.json().catch(()=>({authenticated:false}));
    return !!(who2 && who2.authenticated);
  } catch {
    return false;
  }
}

/* ===========================
 * API with auto-refresh (for JWT-protected endpoints)
 * =========================== */
async function _fetch(url, opts){ const res = await fetch(url, opts); let data={}; try{data=await res.json();}catch{} return {res,data}; }
async function api(url, opts={}, retry=true){
  opts.headers = Object.assign({"Content-Type":"application/json"}, opts.headers||{});
  opts.credentials = "include";
  const t = auth.access(); if (t) opts.headers.Authorization = "Bearer " + t;

  const first = await _fetch(url, opts);
  if (first.res.status !== 401){
    if(!first.res.ok) throw {status:first.res.status, data:first.data};
    return first.data;
  }
  if(!retry || !auth.refresh()) throw {status:first.res.status, data:first.data};

  let r = await fetch("/accounts/token/refresh/", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({refresh: auth.refresh()}), credentials:"include"
  });
  let jd = {}; try{ jd = await r.json(); }catch{}
  if(!r.ok || !jd.access){
    r = await fetch("/accounts/auth/token/refresh/", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({refresh: auth.refresh()}), credentials:"include"
    });
    try{ jd = await r.json(); }catch{}
  }
  if (r.ok && jd.access){
    auth.set(jd.access, jd.refresh || auth.refresh());
    return api(url, opts, /*retry*/false);
  }
  auth.clear();
  throw {status:first.res.status, data:first.data};
}

/* ===========================
 * Auth modal helpers
 * =========================== */
const modalEl = () => document.getElementById("auth-modal");
function show(step){
  // FIX: match template id 'auth-step-choice'
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
  m.classList.remove("hidden");
  m.setAttribute("aria-hidden","false");
  show(step);
}
function closeAuth(){ const m=modalEl(); if(!m) return; m.classList.add("hidden"); m.setAttribute("aria-hidden","true"); }

/* Resume a protected action after login */
let _pendingAction = null;
function requireLoginThen(doFn){
  if (auth.access()){
    return ensureSessionFromJWT().then(()=>doFn());
  }
  _pendingAction = doFn;
  openAuth("login");
}

/* ===========================
 * Server Cart API helpers
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
async function cartApiReplaceNonEmpty(items){
  if (!Array.isArray(items) || items.length === 0) return;
  await fetch("/api/orders/cart/", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie("csrftoken") },
    credentials: "include",
    body: JSON.stringify({ items }),
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
 * Local cache (UI only)
 * =========================== */
const CART_KEY = "cart";
const COUPON_KEY = "applied_coupon";

function getCartLS(){ try{ return JSON.parse(localStorage.getItem(CART_KEY) || "[]" ); }catch{ return []; } }
function setCartLS(cart){ localStorage.setItem(CART_KEY, JSON.stringify(cart)); updateCartBadgeFromLS(); }
function updateCartBadgeFromLS(){
  const count = getCartLS().reduce((a,i)=> a + Number(i.qty||0), 0);
  const el=document.getElementById("cart-count");
  if(el) el.textContent = String(count || 0);
}

/* Coupon helpers */
function getAppliedCoupon(){ try{ return JSON.parse(localStorage.getItem(COUPON_KEY) || "null"); }catch{return null;} }
function setAppliedCoupon(c){ localStorage.setItem(COUPON_KEY, JSON.stringify(c)); }
function clearAppliedCoupon(){ localStorage.removeItem(COUPON_KEY); }

/* ===========================
 * Render cart from SERVER and display coupon-adjusted totals
 * =========================== */
async function renderCart(){
  const holder = document.getElementById("cart-items") || document.getElementById("cart");
  if(!holder) return;

  const data = await cartApiGet();
  const items = Array.isArray(data.items) ? data.items : [];
  const curr  = data.currency || (window.DEFAULT_CURRENCY || "NPR");

  if(!items.length){
    holder.innerHTML = `<p>Your cart is empty.</p>`;
    updateCartBadgeFromLS();
    const payBtn=document.getElementById("pay-btn");
    if (payBtn) payBtn.disabled = true;
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
  updateCartBadgeFromLS();
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
  await ensureSessionFromJWT();

  const btn = document.getElementById("pay-btn");
  if (!btn) { window.location.reload(); return; }

  const endpoint = btn.getAttribute("data-checkout-endpoint");
  const href     = btn.getAttribute("data-href");
  const applied  = getAppliedCoupon();

  if (endpoint){
    try {
      const payload = { };
      if (applied && applied.code){
        payload.coupon = applied.code;
      }
      const res = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
          ...(auth.access() ? { "Authorization": "Bearer " + auth.access() } : {}),
        },
        credentials: "include",
        body: JSON.stringify(payload)
      });
      const data = await res.json().catch(()=>({}));
      if (res.ok && data && (data.url || data.checkout_url)){
        window.location.href = data.url || data.checkout_url;
        return;
      }
      if (href) window.location.href = href;
    } catch {
      if (href) window.location.href = href;
    }
  } else if (href){
    window.location.href = href;
  } else {
    const form = document.getElementById("checkout-form");
    if (form) form.submit();
  }
}

/* ===========================
 * Header auth state + nav (clear cart on logout per your request)
 * =========================== */
async function refreshHeaderAuth(){
  const linkLogin  = document.getElementById("nav-login") || document.getElementById("auth-link");
  const linkLogout = document.getElementById("nav-logout");
  const linkOrders = document.getElementById("nav-orders") || document.querySelector('a[href="/my-orders/"]');

  const loggedIn = !!auth.access();
  if (linkLogin)  linkLogin.style.display  = loggedIn ? "none" : "";
  if (linkLogout) linkLogout.style.display = loggedIn ? "" : "none";
  if (linkOrders) linkOrders.style.display = loggedIn ? "" : "none";

  if (linkLogin && !linkLogin._bound){
    linkLogin._bound = true;
    linkLogin.addEventListener("click", (e)=>{ e.preventDefault(); openAuth("login"); });
  }
  document.addEventListener("click", (e)=>{
    const open = e.target.closest('[data-open-login], .js-login, a[href="/login/"], a[href="/accounts/login/"]');
    if (open){
      e.preventDefault();
      openAuth("login");
    }
  });

  if (linkLogout && !linkLogout._bound){
    linkLogout._bound = true;
    linkLogout.addEventListener("click", async (e)=>{
      e.preventDefault();
      try {
        await fetch("/accounts/auth/logout/", {method:"POST", credentials:"include"});
      } catch {}
      // Clear server-side cart and local cache ON LOGOUT (as you requested)
      try { await cartApiReset(); } catch {}
      try {
        localStorage.removeItem("cart");
        localStorage.removeItem("applied_coupon");
        auth.clear();
      } catch {}
      updateCartBadgeFromLS();
      window.location.href = "/";
    });
  }

  if (linkOrders && !linkOrders._bound2){
    linkOrders._bound2 = true;
    linkOrders.addEventListener("click", (e)=>{
      e.preventDefault();
      requireLoginThen(async ()=>{
        await ensureSessionFromJWT();
        window.location.href = "/my-orders/";
      });
    });
  }
}

/* ===========================
 * Events (Add/Qty/Remove/Checkout/Coupons)
 * =========================== */
document.addEventListener("click", async (e) => {
  // Add-to-cart
  const btn = e.target.closest(".add-to-cart");
  if (btn){
    const item = {
      id: Number(btn.getAttribute("data-id")),
      name: btn.getAttribute("data-name") || undefined,
      price: Number(btn.getAttribute("data-price") || 0),
      image: btn.getAttribute("data-image") || undefined,
    };
    // Update LS for immediate UI feedback
    const ls = getCartLS();
    const row = ls.find(x => Number(x.id) === item.id);
    if (row){ row.qty = Number(row.qty||0) + 1; } else { ls.push({ id:item.id, name:item.name, price:item.price, image:item.image, qty:1 }); }
    setCartLS(ls);
    // Persist to server
    await cartApiAdd(item.id, 1);
    await renderCart();
  }

  const dec = e.target.closest(".qty-dec");
  const inc = e.target.closest(".qty-inc");
  const rem = e.target.closest(".remove-item");

  if (dec){
    const id = Number(dec.getAttribute("data-id"));
    const ls = getCartLS(); const row = ls.find(x=>Number(x.id)===id);
    if (row){
      row.qty = Math.max(0, Number(row.qty||0)-1);
      if (row.qty===0){
        const nx = ls.filter(x=>Number(x.id)!==id); setCartLS(nx);
        await cartApiRemove(id);
      } else {
        setCartLS(ls);
        await cartApiAdd(id, -1);
      }
      await renderCart();
    }
  }
  if (inc){
    const id = Number(inc.getAttribute("data-id"));
    const ls = getCartLS(); const row = ls.find(x=>Number(x.id)===id);
    if (row){
      row.qty = Number(row.qty||0)+1; setCartLS(ls);
      await cartApiAdd(id, 1);
      await renderCart();
    }
  }
  if (rem){
    const id = Number(rem.getAttribute("data-id"));
    const nx = getCartLS().filter(x => Number(x.id) !== id); setCartLS(nx);
    await cartApiRemove(id);
    await renderCart();
  }

  // Checkout button (requires login)
  const pay = e.target.closest("#pay-btn");
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
    // Compute delta vs server? Easier: remove then add n times; but to reduce calls:
    // We'll read LS, sync delta.
    const ls = getCartLS();
    let row = ls.find(x => Number(x.id)===id);
    const old = row ? Number(row.qty||1) : 0;
    if (!row){ row = {id, qty:n}; ls.push(row); }
    row.qty = n; setCartLS(ls);
    const delta = n - old;
    if (delta > 0) { await cartApiAdd(id, delta); }
    if (delta < 0) {
      // simulate by removing and re-adding n
      await cartApiRemove(id);
      if (n > 0) await cartApiAdd(id, n);
    }
    await renderCart();
  }
});

/* ===========================
 * Bind modal forms (login/signup) and resume pending action
 * =========================== */
function bindAuthModal(){
  const m=modalEl(); if(!m) return;

  // Close button fix
  const closeBtn = document.getElementById("auth-close");
  if (closeBtn && !closeBtn._bound){ closeBtn._bound = true; closeBtn.addEventListener("click", ()=> closeAuth()); }

  // Match template IDs: btn-open-login / btn-open-signup
  (document.getElementById("btn-open-login")||{}).onclick = ()=>show("login");
  (document.getElementById("btn-open-signup")||{}).onclick = ()=>show("signup");
  (document.getElementById("link-to-signup")||{}).onclick = (e)=>{ e.preventDefault(); show("signup"); };
  (document.getElementById("link-to-login")||{}).onclick = (e)=>{ e.preventDefault(); show("login"); };

  // LOGIN
  const loginForm=document.getElementById("modal-login-form");
  if(loginForm && !loginForm._bound){
    loginForm._bound = true;
    loginForm.addEventListener("submit", async (e)=>{
      e.preventDefault();
      const fd=new FormData(loginForm);
      const body=JSON.stringify({username:fd.get("username"), password:fd.get("password")});

      let r = await fetch("/accounts/token/", {method:"POST", headers:{"Content-Type":"application/json"}, body, credentials:"include"});
      let data = {}; try{ data = await r.json(); }catch{}
      if(!r.ok || !data.access){
        r = await fetch("/accounts/auth/token/", {method:"POST", headers:{"Content-Type":"application/json"}, body, credentials:"include"});
        try{ data = await r.json(); }catch{}
      }

      const st=document.getElementById("modal-login-status");
      if(r.ok && data && data.access){
        auth.set(data.access, data.refresh);
        await ensureSessionFromJWT();
        // Merge session cart into user's DB cart after login
        try { await cartApiMergeAfterLogin(); } catch {}
        st.textContent=""; closeAuth();
        if (typeof _pendingAction === "function"){
          const action = _pendingAction; _pendingAction=null;
          await action();
        } else {
          await refreshHeaderAuth();
        }
      } else {
        st.textContent=(data && (data.detail||data.message)) || "Login failed.";
      }
    });
  }

  // SIGNUP
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
      let res = await fetch("/accounts/register/", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(payload), credentials:"include"});
      if(!res.ok) res = await fetch("/accounts/auth/register/", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(payload), credentials:"include"});
      const data=await res.json().catch(()=>({}));
      const st=document.getElementById("modal-signup-status");
      if(res.ok){
        if(data && data.access){
          auth.set(data.access, data.refresh);
        } else {
          const r = await fetch("/accounts/token/", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({username: payload.username, password: payload.password}), credentials:"include"});
          const td=await r.json().catch(()=>({}));
          if(r.ok && td.access) auth.set(td.access, td.refresh);
        }
        await ensureSessionFromJWT();
        // Merge after signup->login
        try { await cartApiMergeAfterLogin(); } catch {}
        st.textContent=""; closeAuth();
        if (typeof _pendingAction === "function"){
          const action = _pendingAction; _pendingAction=null;
          await action();
        } else {
          await refreshHeaderAuth();
        }
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

  // DO NOT clear guest cart. If LS has items, mirror them to the server once.
  const ls = getCartLS();
  if (Array.isArray(ls) && ls.length > 0){
    const items = ls.map(i => ({ id: Number(i.id), quantity: Number(i.qty||1) })).filter(i => i.id>0 && i.quantity>0);
    try { await cartApiReplaceNonEmpty(items); } catch(e){}
  }

  updateCartBadgeFromLS();
  await renderCart();
});
