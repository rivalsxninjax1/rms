/* storefront/static/storefront/cart-pay.js
 * Stripe checkout starter with robust fallback (POST JSON -> GET redirect).
 */

function getCookie(name){
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
  if (match) return decodeURIComponent(match[2]);
  return "";
}
function jwtAccess(){ return localStorage.getItem("jwt_access") || ""; }

async function postJSON(url, body, withAuth=true){
  const headers = {"Content-Type": "application/json"};
  const csrftoken = getCookie("csrftoken");
  if (csrftoken) headers["X-CSRFToken"] = csrftoken;
  if (withAuth && jwtAccess()) headers["Authorization"] = "Bearer " + jwtAccess();

  const res = await fetch(url, {
    method: "POST",
    headers,
    credentials: "include",
    body: JSON.stringify(body || {})
  });
  let data = {};
  try { data = await res.json(); } catch {}
  if (!res.ok) {
    const msg = (data && (data.detail || data.message)) ? (data.detail || data.message) : ("HTTP " + res.status);
    const err = new Error(msg);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

function getCart(){ try { return JSON.parse(localStorage.getItem("cart") || "[]"); } catch { return []; } }
function cartToPayload(){
  const items = getCart().map(i => ({
    id: Number(i.id),
    quantity: Number(i.qty || 1),
    price: Number(i.price || 0)
  }));
  return { items };
}

async function createOrder(){
  try {
    const data = await postJSON("/api/orders/orders/", cartToPayload());
    const orderId = data.id || data.pk || data.order_id;
    if (!orderId) throw new Error("Unable to create order");
    return orderId;
  } catch (e) {
    if (e.status && e.status !== 400 && e.status !== 415) throw e;
    const data = await postJSON("/api/orders/orders/", {});
    const orderId = data.id || data.pk || data.order_id;
    if (!orderId) throw new Error("Unable to create order");
    return orderId;
  }
}

async function startCheckout(orderId){
  // 1) Try POST that returns JSON {url}
  try{
    const data = await postJSON(`/payments/create-checkout-session/${orderId}/`, {}, false);
    if (data && data.url) {
      window.location.href = data.url;
      return;
    }
  }catch(e){
    // ignore and fall through to GET redirect
  }
  // 2) Fallback: server issues 302 redirect to Stripe
  window.location.href = `/payments/create-checkout-session/${orderId}/`;
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("pay-btn");
  if (!btn) return;
  btn.disabled = (getCart().length === 0);

  btn.addEventListener("click", async () => {
    btn.disabled = true;
    try {
      if (!jwtAccess()){
        alert("Please login first to continue to payment.");
        const link = document.getElementById("nav-login") || document.getElementById("auth-link");
        if (link) link.click();
        return;
      }
      const orderId = await createOrder();
      await startCheckout(orderId);
    } catch (e) {
      console.error(e);
      alert(e.message || "Unable to start checkout");
    } finally {
      btn.disabled = (getCart().length === 0);
    }
  });
});
