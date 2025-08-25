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

  // === NEW: read a table number if present (supports common field names) ===
  function getTableNumber() {
    const cands = [
      "#table_number", "#table-number", "[name='table_number']",
      "#table_num", "[name='table_num']"
    ];
    for (const sel of cands) {
      const el = $(sel);
      if (!el) continue;
      const raw = (el.value ?? "").toString().trim();
      if (!raw) continue;
      const n = parseInt(raw, 10);
      if (!Number.isNaN(n) && n > 0) return n;
    }
    return null;
  }

  async function setCartMeta(serviceType, tableNumber){              // <== signature extended
    const payload = { service_type: serviceType };
    // include table number only for Dine-In
    if (serviceType === "DINE_IN" && tableNumber) {
      const t = parseInt(tableNumber, 10);                           // <== ensure integer
      payload.table_number = t; // preferred
      payload.table_num = t;    // alias if serializer expects this
    }
    await fetch("/api/orders/cart/meta/", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
  }

  async function createOrderAndMaybeGo(serviceType, tableNumber){     // <== signature extended
    // Ask backend to create order; it may include external options (Uber/Doordash)
    const payload = { service_type: serviceType };
    // include table number only for Dine-In
    if (serviceType === "DINE_IN" && tableNumber) {
      const t = parseInt(tableNumber, 10);                           // <== ensure integer
      payload.table_number = t; // preferred
      payload.table_num = t;    // alias if serializer uses this
    }

    const r = await fetch("/api/orders/orders/", { // <-- FIXED endpoint (with trailing slash)
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(payload),
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || "Failed to create order");

    // If user chose aggregator, redirect to that URL; else use Stripe URL
    // Accept both spellings and normalize to backend's canonical key
    if (serviceType === "UBEREATS" || serviceType === "UBER_EATS" || serviceType === "DOORDASH") {
      const code = (serviceType === "UBEREATS") ? "UBER_EATS" : serviceType;   // <== normalized
      const opt = (d.external_options || []).find(o => o.code === code);
      if (opt && opt.url) {
        window.location.href = opt.url;
        return;
      }
      // Fallback: if URL not configured, error
      throw new Error(code + " is not configured.");
    } else {
      // Prefer backend-provided checkout_url if present
      if (d.checkout_url) {
        window.location.href = d.checkout_url;
        return;
      }

      // Robust fallback: try payments session endpoints using returned order id
      const orderId = d.id || d.pk;
      if (!orderId) throw new Error("Order created but no id returned.");

      // Try POST to get { url }
      try {
        const s = await fetch(`/payments/create-checkout-session/${orderId}/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
        });
        const j = await s.json().catch(() => ({}));
        if (s.ok && j && j.url) {
          window.location.assign(j.url);
          return;
        }
      } catch (_) {
        // ignore; fallback to GET below
      }

      // Final fallback: server will 302 to Stripe
      window.location.assign(`/payments/create-checkout-session/${orderId}/`);
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
    if (payStatus) payStatus.textContent = "Preparing checkout…";
    try {
      const st = (new FormData(payForm).get("service_type") || "DINE_IN").toString().toUpperCase();

      // === NEW: guard for Dine-In table number ===
      const tableNo = getTableNumber();
      if (st === "DINE_IN" && !tableNo) {
        if (payStatus) payStatus.textContent = "Please enter a table number for Dine-In.";
        return;
      }

      await setCartMeta(st, tableNo);              // safe, does not flush session
      await createOrderAndMaybeGo(st, tableNo);    // routes either to Stripe or aggregator
    } catch (err) {
      if (payStatus) payStatus.textContent = (err && err.message) || "Unable to start checkout.";
    }
  });

  // After auth flow, if continuation is set to show pay modal:
  if (typeof window.__continueCheckoutAfterAuth !== "function") {
    window.__continueCheckoutAfterAuth = async () => { openPayModal(); };
  }
})();
