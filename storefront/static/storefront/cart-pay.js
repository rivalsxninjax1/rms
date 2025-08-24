/* storefront/static/storefront/cart-pay.js */

/* Read CSRF cookie if present */
function getCookie(name){
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
  if (match) return decodeURIComponent(match[2]);
  return "";
}

/* JWT from your existing localStorage scheme */
function jwtAccess(){ return localStorage.getItem("jwt_access") || ""; }

/* Small helper for JSON POST with optional auth */
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
    const msg = data && (data.detail || data.message) ? (data.detail || data.message) : ("HTTP " + res.status);
    throw new Error(msg);
  }
  return data;
}

/* Create order from server's session cart.
   If your API uses a different endpoint/fields, adjust here. */
async function createOrder(){
  // This assumes your DRF OrdersViewSet creates from session cart at POST /api/orders/orders/
  const data = await postJSON("/api/orders/orders/", {});
  const orderId = data.id || data.pk || data.order_id;
  if (!orderId) throw new Error("Unable to create order");
  return orderId;
}

/* Create Stripe session and redirect */
async function startCheckout(orderId){
  const data = await postJSON(`/payments/create-checkout-session/${orderId}/`, {}, /*withAuth*/ false);
  if (data && data.url){
    window.location.href = data.url;
  } else {
    throw new Error("Failed to create checkout session");
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  const btn = document.getElementById("pay-btn");
  if (!btn) return;

  btn.disabled = false;

  btn.addEventListener("click", async () => {
    btn.disabled = true;
    try {
      if (!jwtAccess()){
        alert("Please login first to continue to payment.");
        const link = document.getElementById("nav-login");
        if (link) link.click();
        return;
      }
      const orderId = await createOrder();
      await startCheckout(orderId);
    } catch (e) {
      console.error(e);
      alert(e.message || "Unable to start checkout");
    } finally {
      btn.disabled = false;
    }
  });
});
