/* storefront/static/storefront/app.js
 * Canonical client script.
 * Fixes: path mismatch, add-to-cart event delegation, type="button" buttons.
 */

/* ===========================
 * Utilities
 * =========================== */
function money(n){ return Number(n||0).toFixed(2); }
function currency(amount){
  const cur = (window.DEFAULT_CURRENCY || "NPR");
  return `${cur} ${Number(amount||0).toFixed(2)}`;
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

/* ===========================
 * API with auto-refresh
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

  let r = await fetch("/api/auth/token/refresh/", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({refresh: auth.refresh()})});
  if(!r.ok){
    r = await fetch("/api/token/refresh/", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({refresh: auth.refresh()})});
  }
  const jd = await r.json().catch(()=>({}));
  if (r.ok && jd.access){
    auth.set(jd.access, jd.refresh);
    opts.headers.Authorization = "Bearer " + jd.access;
    const second = await _fetch(url, opts);
    if(!second.res.ok) throw {status:second.res.status, data:second.data};
    return second.data;
  } else {
    auth.clear();
    throw {status:first.res.status, data:first.data};
  }
}

/* ===========================
 * Auth UI
 * =========================== */
const modalEl=()=>document.getElementById("auth-modal");
function show(step){ ["choose","login","signup"].forEach(s=>{ const el=document.getElementById("auth-step-"+s); if(el) el.classList.toggle("hidden", s!==step);});}
function openAuth(step="login"){ const m=modalEl(); if(!m) return; m.classList.remove("hidden"); m.setAttribute("aria-hidden","false"); show(step); }
function closeAuth(){ const m=modalEl(); if(!m) return; m.classList.add("hidden"); m.setAttribute("aria-hidden","true"); }

async function refreshHeaderAuth(){
  const link=document.getElementById("auth-link");
  const orders=document.getElementById("nav-orders") || document.querySelector('a[href="/orders/"]');
  if(orders) orders.style.display = auth.access() ? "inline-block":"none";

  if(link){
    link.onclick = (e)=>{ e.preventDefault(); openAuth("login"); };
    if(auth.access()){
      link.textContent="Logout";
      link.onclick=(e)=>{ e.preventDefault(); auth.clear(); location.reload(); };
    } else {
      link.textContent="Login";
    }
  }
  updateCartBadge();
}

function bindAuthModal(){
  const m=modalEl(); if(!m) return;
  m.addEventListener("click", (e)=>{ if(e.target.dataset.close) closeAuth(); });
  (document.getElementById("btn-go-login")||{}).onclick = ()=>show("login");
  (document.getElementById("btn-go-signup")||{}).onclick = ()=>show("signup");
  (document.getElementById("link-to-signup")||{}).onclick = (e)=>{ e.preventDefault(); show("signup"); };
  (document.getElementById("link-to-login")||{}).onclick = (e)=>{ e.preventDefault(); show("login"); };

  // LOGIN
  const loginForm=document.getElementById("modal-login-form");
  if(loginForm) loginForm.addEventListener("submit", async (e)=>{
    e.preventDefault();
    const fd=new FormData(loginForm);
    const body=JSON.stringify({username:fd.get("username"), password:fd.get("password")});
    let r = await fetch("/api/auth/token/", {method:"POST", headers:{"Content-Type":"application/json"}, body});
    if(!r.ok) r = await fetch("/api/token/", {method:"POST", headers:{"Content-Type":"application/json"}, body});
    const data=await r.json().catch(()=>({}));
    const st=document.getElementById("modal-login-status");
    if(r.ok && data.access){
      auth.set(data.access, data.refresh);
      st.textContent=""; closeAuth(); await refreshHeaderAuth();
    } else {
      st.textContent=(data && (data.detail||data.error)) || "Login failed.";
    }
  });

  // SIGNUP
  const signupForm=document.getElementById("modal-signup-form");
  if(signupForm) signupForm.addEventListener("submit", async (e)=>{
    e.preventDefault();
    const fd=new FormData(signupForm);
    const payload={
      username:fd.get("username"),
      email:fd.get("email"),
      first_name:fd.get("first_name"),
      last_name:fd.get("last_name"),
      password:fd.get("password"),
    };
    let res = await fetch("/api/auth/register/", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(payload)});
    if(!res.ok) res = await fetch("/api/register/", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(payload)});
    const data=await res.json().catch(()=>({}));
    const st=document.getElementById("modal-signup-status");
    if(res.ok){
      if(data && data.access) auth.set(data.access, data.refresh);
      else {
        const r = await fetch("/api/auth/token/", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({username: payload.username, password: payload.password})});
        const td=await r.json().catch(()=>({}));
        if(r.ok) auth.set(td.access, td.refresh);
      }
      st.textContent=""; closeAuth(); await refreshHeaderAuth();
    } else {
      st.textContent=(data && (data.detail||JSON.stringify(data))) || "Signup failed.";
    }
  });
}

/* ===========================
 * Cart (localStorage)
 * =========================== */
const CART_KEY = "cart";
function getCart(){ try{ return JSON.parse(localStorage.getItem(CART_KEY) || "[]" ); }catch{ return []; } }
function saveCart(cart){ localStorage.setItem(CART_KEY, JSON.stringify(cart)); updateCartBadge(); }
function cartTotal(){ return getCart().reduce((s,i)=> s + Number(i.price||0) * Number(i.qty||0), 0); }

function toast(msg) {
  try {
    const t = document.createElement("div");
    t.textContent = msg;
    t.style.position = "fixed";
    t.style.bottom = "16px";
    t.style.right = "16px";
    t.style.background = "rgba(0,0,0,.8)";
    t.style.color = "#fff";
    t.style.padding = "8px 12px";
    t.style.borderRadius = "8px";
    t.style.zIndex = 9999;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 1400);
  } catch {}
}

function updateCartBadge(){
  const count = getCart().reduce((a,i)=> a + Number(i.qty||0), 0);
  const el=document.getElementById("cart-count");
  if(el) el.textContent = String(count);
  const payBtn=document.getElementById("pay-btn");
  if (payBtn) payBtn.disabled = (count === 0);
}

function addToCart(itemOrId, qty=1, itemFallback=null){
  let item = null;
  if (typeof itemOrId === "object" && itemOrId !== null){
    item = itemOrId;
  } else {
    item = Object.assign({ id: Number(itemOrId) }, itemFallback || {});
  }
  const cart = getCart();
  const id = Number(item.id);
  const row = cart.find(x => Number(x.id) === id);
  if (row){
    row.qty = Number(row.qty||0) + Number(qty||1);
  } else {
    cart.push({
      id,
      name: item.name || `Item ${id}`,
      price: Number(item.price || 0),
      image: item.image || null,
      qty: Number(qty||1),
    });
  }
  saveCart(cart);
  toast(`${item.name || "Item"} added to cart`);
}

function setQty(id, qty){
  const cart = getCart();
  const row = cart.find(x => Number(x.id) === Number(id));
  if(!row) return;
  row.qty = Math.max(1, Number(qty||1));
  saveCart(cart);
}
function removeFromCart(id){
  const cart = getCart().filter(x => Number(x.id) !== Number(id));
  saveCart(cart);
}

/* Render cart for #cart-items or legacy #cart */
function renderCart(){
  const holder = document.getElementById("cart-items") || document.getElementById("cart");
  if(!holder) return;

  const cart = getCart();
  if(!cart.length){
    holder.innerHTML = `<p>Your cart is empty.</p>`;
    updateCartBadge();
    return;
  }

  let html = `<div class="cart-list">`;
  cart.forEach(i => {
    html += `
      <div class="cart-row" data-id="${i.id}" style="display:grid;grid-template-columns:72px 1fr auto;gap:12px;align-items:center;padding:10px 0;border-bottom:1px solid #eee;">
        <div style="width:72px;height:72px;background:#f7f7f7;border-radius:8px;overflow:hidden;display:flex;align-items:center;justify-content:center;">
          ${i.image ? `<img src="${i.image}" alt="${i.name}" style="width:100%;height:100%;object-fit:cover;">` : `<div style="opacity:.6;">No image</div>`}
        </div>
        <div>
          <div style="font-weight:600;margin-bottom:4px;">${i.name}</div>
          <div style="color:#555;">${currency(i.price)}</div>
          <div style="margin-top:8px;display:flex;align-items:center;gap:6px;">
            <button class="qty-dec" data-id="${i.id}" type="button">−</button>
            <input class="qty-input" data-id="${i.id}" type="number" min="1" value="${i.qty}" style="width:60px;">
            <button class="qty-inc" data-id="${i.id}" type="button">+</button>
            <button class="remove-item" data-id="${i.id}" style="margin-left:8px;" type="button">Remove</button>
          </div>
        </div>
        <div style="font-weight:600;">${currency(Number(i.price) * Number(i.qty))}</div>
      </div>
    `;
  });
  html += `</div>`;
  html += `<div style="display:flex;justify-content:flex-end;margin-top:16px;font-size:18px;font-weight:600;">Total: ${currency(cartTotal())}</div>`;
  holder.innerHTML = html;

  updateCartBadge();
}

/* ===========================
 * Menu (PUBLIC, optional)
 * =========================== */
async function loadMenu(){
  const wrap=document.getElementById("menu-grid"); if(!wrap) return;
  try{
    let data = await api("/api/menu/items/");
    if (!Array.isArray(data) && !data.results && !data.items){
      data = await api("/api/items/");
    }
    const items = Array.isArray(data) ? data : (data.results || data.items || []);
    if(!items.length){ wrap.innerHTML = `<div class="card">No items available.</div>`; return; }
    wrap.innerHTML = items.map(i=>`
      <div class="card">
        <h3>${i.name || "Item"}</h3>
        <p>${i.description || ""}</p>
        <strong>${currency(i.price || 0)}</strong><br/>
        <a href="/menu/${i.id}/"><button type="button">View</button></a>
        <button class="add-to-cart"
                type="button"
                data-id="${i.id}"
                data-name="${(i.name||'').replace(/"/g,'&quot;')}"
                data-price="${i.price||0}"
                data-image="${i.image_url||i.image||''}">
          Add
        </button>
      </div>
    `).join("");

  }catch(e){
    wrap.innerHTML = `<div class="card">Failed to load menu.</div>`;
  }
}

async function loadMenuItem(id){
  const wrap=document.getElementById("menu-item"); if(!wrap) return;
  try{
    const i=await api(`/api/menu/items/${id}/`).catch(()=>api(`/api/items/${id}/`));
    wrap.innerHTML = `
      <div class="card">
        <h2>${i.name || "Item"}</h2>
        <p>${i.description || ""}</p>
        <strong>${currency(i.price || 0)}</strong><br/>
        <div class="row">
          <button class="add-to-cart"
                  type="button"
                  data-id="${i.id}"
                  data-name="${(i.name||'').replace(/"/g,'&quot;')}"
                  data-price="${i.price||0}"
                  data-image="${i.image_url||i.image||''}">
            Add to Cart
          </button>
        </div>
      </div>
    `;
  }catch{
    wrap.innerHTML = `<div class="card">Failed to load item.</div>`;
  }
}

/* ===========================
 * Global Event Delegation
 * =========================== */
document.addEventListener("click", (e) => {
  const btn = e.target.closest(".add-to-cart");
  if (btn){
    const item = {
      id: Number(btn.getAttribute("data-id")),
      name: btn.getAttribute("data-name") || undefined,
      price: Number(btn.getAttribute("data-price") || 0),
      image: btn.getAttribute("data-image") || undefined,
    };
    addToCart(item, 1);
  }

  const dec = e.target.closest(".qty-dec");
  const inc = e.target.closest(".qty-inc");
  const rem = e.target.closest(".remove-item");

  if (dec){
    const id = Number(dec.getAttribute("data-id"));
    const cart = getCart();
    const row = cart.find(x=> Number(x.id)===id);
    if (row){ row.qty = Math.max(1, Number(row.qty||0)-1); saveCart(cart); renderCart(); }
  }
  if (inc){
    const id = Number(inc.getAttribute("data-id"));
    const cart = getCart();
    const row = cart.find(x=> Number(x.id)===id);
    if (row){ row.qty = Number(row.qty||0)+1; saveCart(cart); renderCart(); }
  }
  if (rem){
    const id = Number(rem.getAttribute("data-id"));
    removeFromCart(id);
    renderCart();
  }
});

document.addEventListener("input", (e) => {
  const qty = e.target.closest(".qty-input");
  if (qty){
    const id = Number(qty.getAttribute("data-id"));
    setQty(id, qty.value);
    renderCart();
  }
});

document.addEventListener("DOMContentLoaded", async ()=>{
  bindAuthModal();
  await refreshHeaderAuth();

  if(window.page==='menu')       loadMenu();        // no-op if #menu-grid missing
  if(window.page==='menu_item')  loadMenuItem(window.item_id);

  renderCart(); // only affects pages with a cart container
});
