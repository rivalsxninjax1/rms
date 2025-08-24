/* storefront/static/storefront/cart-pay.js
 * Stripe checkout starter with JWT auto-refresh + retry.
 */

function getCookie(name){
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
  if (match) return decodeURIComponent(match[2]);
  return "";
}

/* ---- JWT helpers (aligned with app.js conventions) ---- */
function jwtAccess(){ return localStorage.getItem("jwt_access") || ""; }
function jwtRefresh(){ return localStorage.getItem("jwt_refresh") || ""; }
function setTokens(access, refresh){
  if (access) localStorage.setItem("jwt_access", access);
  if (refresh) localStorage.setItem("jwt_refresh", refresh);
}
function clearTokens(){
  localStorage.removeItem("jwt_access");
  localStorage.removeItem("jwt_refresh");
}

/* Try both refresh endpoints for compatibility */
async function tryRefresh(){
  const refreshToken = jwtRefresh();
  if (!refreshToken) return null;

  const body = JSON.stringify({ refresh: refreshToken });
  const headers = { "Content-Type": "application/json" };

  // 1) DRF SimpleJWT default path sometimes mounted at /api/auth/token/refresh/
  let r = await fetch("/api/auth/token/refresh/", { method: "POST", headers, body, credentials: "include" });
  let data = {};
  try { data = await r.json(); } catch {}

  if (r.ok && data && data.access){
    setTokens(data.access, data.refresh || refreshToken);
    return data.access;
  }

  // 2) Fallback to /api/token/refresh/
  r = await fetch("/api/token/refresh/", { method: "POST", headers, body, credentials: "include" });
  data = {};
  try { data = await r.json(); } catch {}

  if (r.ok && data && data.access){
    setTokens(data.access, data.refresh || refreshToken);
    return data.access;
  }
  return null;
}

/* ---- JSON POST with optional auth + auto-refresh-once ---- */
async function postJSON(url, body, withAuth=true, retry=true){
  const headers = { "Content-Type": "application/json" };
  const csrftoken = getCookie("csrftoken");
  if (csrftoken) headers["X-CSRFToken"] = csrftoken;

  if (withAuth && jwtAccess()){
    headers["Authorization"] = "Bearer " + jwtAccess();
  }

  let res = await fetch(url, {
    method: "POST",
    headers,
    credentials: "include",
    body: JSON.stringify(body || {})
  });

  // On 401, try to refresh once and retry
  if (withAuth && res.status === 401 && retry){
    const newAccess = await tryRefresh();
    if (newAccess){
      headers["Authorization"] = "Bearer " + newAccess;
      res = await fetch(url, {
        method: "POST",
        headers,
        credentials: "include",
        body: JSON.stringify(body || {})
      });
    } else {
      // Refresh failed → force re-login
      clearTokens();
    }
  }

  let data = {};
  try { data = await res.json(); } catch {}

  if (!res.ok){
    const msg = (data && (data.detail || data.message)) ? (data.detail || data.message) : ("HTTP " + res.status);
    const err = new Error(msg);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

/* ---- Cart helpers (localStorage) ---- */
function getCart(){
  try { return JSON.parse(localStorage.getItem("cart") || "[]"); } catch { return []; }
}
function cartToPayload(){
  const items = getCart().map(i => ({
    id: Number(i.id),
    quantity: Number(i.qty || 1),
    price: Number(i.price || 0)
  }));
  return { items };
}

/* ---- Order + Checkout ---- */
async function createOrder(){
  try {
    const data = await postJSON("/api/orders/orders/", cartToPayload(), /*withAuth*/true, /*retry*/true);
    const orderId = data.id || data.pk || data.order_id;
    if (!orderId) throw new Error("Unable to create order");
    return orderId;
  } catch (e) {
    // If backend accepts session-cart creation, fallback to empty body (still auth’d).
    if (e.status && e.status !== 400 && e.status !== 415) throw e;
    const data = await postJSON("/api/orders/orders/", {}, true, true);
    const orderId = data.id || data.pk || data.order_id;
    if (!orderId) throw new Error("Unable to create order");
    return orderId;
  }
}

async function startCheckout(orderId){
  // Prefer POST JSON returning {url} for SPA
  try{
    const data = await postJSON(`/payments/create-checkout-session/${orderId}/`, {}, /*withAuth*/false, /*retry*/false);
    if (data && data.url) {
      window.location.href = data.url;
      return;
    }
  }catch(e){
    // fall through to GET redirect
  }
  // GET → server 302 to Stripe
  window.location.href = `/payments/create-checkout-session/${orderId}/`;
}

/* ---- UI wiring ---- */
document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("pay-btn");
  if (!btn) return;
  btn.disabled = (getCart().length === 0);

  btn.addEventListener("click", async () => {
    btn.disabled = true;
    try {
      // Must be logged in (we also refresh silently if token is stale)
      if (!jwtAccess() && !jwtRefresh()){
        alert("Please login first to continue to payment.");
        const link = document.getElementById("nav-login") || document.getElementById("auth-link");
        if (link) link.click();
        return;
      }
      const orderId = await createOrder();     // will refresh access token once if needed
      await startCheckout(orderId);
    } catch (e) {
      console.error(e);
      // If we still have a 401 here, prompt a fresh login.
      if (e && e.status === 401){
        alert("Your session expired. Please login again.");
        clearTokens();
        const link = document.getElementById("nav-login") || document.getElementById("auth-link");
        if (link) link.click();
      } else {
        alert(e.message || "Unable to start checkout");
      }
    } finally {
      btn.disabled = (getCart().length === 0);
    }
  });
});
