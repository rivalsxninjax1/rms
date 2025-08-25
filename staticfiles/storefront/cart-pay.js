/* storefront/static/storefront/cart-pay.js
 * Pay flow with "service_type" selection. Never clears cart here.
 */
(function () {
  const $ = (sel, el=document) => el.querySelector(sel);

  const payBtn = $("#pay-btn");
  const payModal = $("#pay-options-modal");
  const payClose = $("#pay-close");
  const payForm = $("#pay-options-form");
  const payStatus = $("#pay-options-status");

  function openPayModal(){ payModal?.classList.remove("hidden"); }
  function closePayModal(){ payModal?.classList.add("hidden"); }

  function isLoggedIn() { return !!(localStorage.getItem("jwt_access") || ""); }

  async function setCartMeta(serviceType){
    await fetch("/api/orders/cart/meta/", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ service_type: serviceType })
    });
  }

  async function createOrderAndMaybeGo(serviceType){
    // Ask backend to create order; it will include external options (Uber/Doordash)
    const r = await fetch("/api/orders/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ service_type: serviceType }),
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || "Failed to create order");

    // If user chose aggregator, redirect to that URL; else use Stripe URL
    if (serviceType === "UBEREATS" || serviceType === "DOORDASH") {
      const code = serviceType;
      const opt = (d.external_options || []).find(o => o.code === code);
      if (opt && opt.url) {
        window.location.href = opt.url;
        return;
      }
      // Fallback: if URL not configured, error
      throw new Error(code + " is not configured.");
    } else {
      if (d.checkout_url) {
        window.location.href = d.checkout_url;
        return;
      }
      throw new Error("Checkout URL missing.");
    }
  }

  async function handlePay(){
    // If not logged in → show auth, then resume to pay modal
    if (!isLoggedIn()) {
      window.__continueCheckoutAfterAuth = async () => { openPayModal(); };
      if (typeof window.__openAuthModalForPay === "function") window.__openAuthModalForPay();
      return;
    }
    // Logged in → show options
    openPayModal();
  }

  // Wire Pay button
  payBtn?.addEventListener("click", async (e) => { e.preventDefault(); await handlePay(); });
  payClose?.addEventListener("click", (e) => { e.preventDefault(); closePayModal(); });

  // Submit chosen service type
  payForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    payStatus.textContent = "Preparing checkout…";
    try {
      const st = (new FormData(payForm).get("service_type") || "DINE_IN").toString().toUpperCase();
      await setCartMeta(st);                    // safe, does not flush session
      await createOrderAndMaybeGo(st);          // routes either to Stripe or aggregator
    } catch (err) {
      payStatus.textContent = (err && err.message) || "Unable to start checkout.";
    }
  });

  // After auth flow, if continuation is set to show pay modal:
  if (typeof window.__continueCheckoutAfterAuth !== "function") {
    window.__continueCheckoutAfterAuth = async () => { openPayModal(); };
  }
})();
