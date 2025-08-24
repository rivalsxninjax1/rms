/* storefront/static/storefront/js/app.js */

/* Utilities */
function money(n){ return Number(n||0).toFixed(2); }

/* Auth (JWT) */
const auth = {
  access(){ return localStorage.getItem("jwt_access") || ""; },
  refresh(){ return localStorage.getItem("jwt_refresh") || ""; },
  set(a,r){ if(a) localStorage.setItem("jwt_access", a); if(r) localStorage.setItem("jwt_refresh", r); },
  clear(){ localStorage.removeItem("jwt_access"); localStorage.removeItem("jwt_refresh"); },
};

/* API with auto-refresh */
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

  // refresh (try legacy then clean)
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

/* Auth UI */
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
  await updateCartBadge();
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

/* Cart API (session; these endpoints already exist in your orders urls) */
async function serverCartGet(){ return await api("/api/orders/cart/"); }
async function serverCartAdd(id, quantity=1){ return await api("/api/orders/cart/items/", {method:"POST", body: JSON.stringify({menu_item_id:id, quantity})}); }
async function serverCartRemove(id){ return await api("/api/orders/cart/items/remove/", {method:"POST", body: JSON.stringify({menu_item_id:id})}); }

/* Menu (PUBLIC) */
async function loadMenu(){
  const wrap=document.getElementById("menu-grid"); if(!wrap) return;
  try{
    let data = await api("/api/menu/items/");
    if (!Array.isArray(data) && !data.results && !data.items){
      // compat: some old routes return list directly at /api/items/
      data = await api("/api/items/");
    }
    const items = Array.isArray(data) ? data : (data.results || data.items || []);
    if(!items.length){ wrap.innerHTML = `<div class="card">No items available.</div>`; return; }
    wrap.innerHTML = items.map(i=>`
      <div class="card">
        <h3>${i.name || "Item"}</h3>
        <p>${i.description || ""}</p>
        <strong>NPR ${money(i.price || 0)}</strong><br/>
        <a href="/menu/${i.id}/"><button>View</button></a>
        <button data-id="${i.id}">Add</button>
      </div>
    `).join("");
    wrap.querySelectorAll("button[data-id]").forEach(b=>{
      b.onclick = async ()=>{ await addToCart(Number(b.dataset.id)); };
    });
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
        <strong>NPR ${money(i.price || 0)}</strong><br/>
        <div class="row"><button id="btn-add">Add to Cart</button></div>
      </div>
    `;
    const btn=document.getElementById("btn-add");
    if(btn) btn.onclick = async ()=>{ await addToCart(Number(i.id)); };
  }catch{
    wrap.innerHTML = `<div class="card">Failed to load item.</div>`;
  }
}

/* Cart rendering */
async function updateCartBadge(){
  try{
    const c=await serverCartGet();
    const count=(c.items||[]).reduce((s,i)=>s + Number(i.quantity||0),0);
    const el=document.getElementById("cart-count");
    if(el) el.textContent=count;
  }catch{}
}
async function addToCart(id, qty=1){ await serverCartAdd(id, qty); await renderCart(); await updateCartBadge(); }
async function changeQty(id, delta){
  const c=await serverCartGet();
  const line=(c.items||[]).find(l=>Number(l.id)===Number(id));
  const current=line?Number(line.quantity||0):0;
  const next=Math.max(0, current+delta);
  if(next===0) await serverCartRemove(id);
  else { if(current>0) await serverCartRemove(id); await serverCartAdd(id, next); }
  await renderCart(); await updateCartBadge();
}
async function renderCart(){
  const el=document.getElementById("cart"); if(!el) return;
  try{
    const c=await serverCartGet();
    const items=c.items||[];
    if(!items.length){ el.innerHTML="<p>Your cart is empty.</p>"; return; }
    const total = items.reduce((s,i)=>s+Number(i.line_total||0),0);
    el.innerHTML = `
      <div class="card">
        <ul>
          ${items.map(i=>`
            <li class="row" style="justify-content:space-between; align-items:center;">
              <span>${i.name}</span>
              <div class="row" style="gap:6px;">
                <button data-minus="${i.id}">−</button>
                <strong>${i.quantity}</strong>
                <button data-plus="${i.id}">+</button>
                <span>NPR ${money(i.line_total)}</span>
                <button data-remove="${i.id}">x</button>
              </div>
            </li>
          `).join("")}
        </ul>
        <div class="space"></div>
        <strong>Subtotal: <span id="subtotal">${money(total)}</span></strong>
        <div>Payable: <strong id="payable">${money(total)} ${String(c.currency||'').toUpperCase()}</strong></div>
      </div>`;
    el.querySelectorAll("button[data-plus]").forEach(b=>{ b.onclick=()=>changeQty(Number(b.dataset.plus), +1); });
    el.querySelectorAll("button[data-minus]").forEach(b=>{ b.onclick=()=>changeQty(Number(b.dataset.minus), -1); });
    el.querySelectorAll("button[data-remove]").forEach(b=>{ b.onclick=async ()=>{ await serverCartRemove(Number(b.dataset.remove)); await renderCart(); await updateCartBadge(); }; });
  }catch{ el.innerHTML="<p>Failed to load cart.</p>"; }
}

/* Checkout -> create order (server will return Stripe URL/external options) */
async function placeOrder(e){
  e.preventDefault();
  const statusEl=document.getElementById("order-status");
  try{
    statusEl && (statusEl.textContent="Creating order…");
    const order = await api("/api/orders/", {method:"POST", body: JSON.stringify({})});
    const parts=[];
    if(order.external_options && order.external_options.length){
      parts.push(order.external_options.map(o=>`<a target="_blank" href="${o.url}">${o.label}</a>`).join(" · "));
    }
    if(order.checkout_url){
      parts.push("Redirecting to Stripe…");
      statusEl && (statusEl.innerHTML = parts.join(" | "));
      window.location.href = order.checkout_url;  // Stripe
      return;
    }
    statusEl && (statusEl.innerHTML = parts.join(" | ") || "Order created.");
  }catch(err){
    const msg = (err && err.data && (err.data.detail || JSON.stringify(err.data))) || err.message || "Unknown error";
    statusEl && (statusEl.textContent = "Order error: " + msg);
    alert("Order error: " + msg);
  }
}

/* Boot */
document.addEventListener("DOMContentLoaded", async ()=>{
  bindAuthModal();
  await refreshHeaderAuth();

  if(window.page==='menu')       loadMenu();
  if(window.page==='menu_item')  loadMenuItem(window.item_id);
  if(window.page==='cart')       renderCart();
  if(window.page==='checkout'){
    renderCart();
    const f=document.getElementById("order-form");
    if(f) f.addEventListener("submit", placeOrder);
  }
});  