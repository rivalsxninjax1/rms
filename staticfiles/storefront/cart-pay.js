/* storefront/static/storefront/cart-pay.js
 * Pay button flow: show auth at payment time; never clear the cart here.
 */
(function () {
  const $ = (sel, el=document) => el.querySelector(sel);
  const payBtn = $("#pay-btn");

  function isLoggedIn() { return !!(localStorage.getItem("jwt_access") || ""); }

  async function createOrderVia(url) {
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({}), // server picks DB PENDING cart or session
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || `Failed to create order @ ${url}`);
    return d;
  }

  async function createOrderAndGo() {
    // Try modern route first; fallback to legacy route if needed
    let d;
    try {
      d = await createOrderVia("/api/orders/");
    } catch (e) {
      d = await createOrderVia("/api/orders/orders/");
    }
    if (d.checkout_url) window.location.href = d.checkout_url;
  }

  async function handlePay() {
    try {
      if (!isLoggedIn()) {
        // Register a continuation after auth
        window.__continueCheckoutAfterAuth = async () => { await createOrderAndGo(); };
        if (typeof window.__openAuthModalForPay === "function") window.__openAuthModalForPay();
        return;
      }
      await createOrderAndGo();
    } catch (err) {
      alert((err && err.message) || "Unable to start checkout.");
    }
  }

  payBtn?.addEventListener("click", async (e) => { e.preventDefault(); await handlePay(); });
})();
