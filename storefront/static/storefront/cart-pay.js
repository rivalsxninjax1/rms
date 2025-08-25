/* storefront/static/storefront/cart-pay.js
 * Pay flow with "service_type" selection. Never clears cart here.
 */
(function () {
  const $ = (sel, el=document) => el.querySelector(sel);

  const payBtn = $("#pay-btn");
  const payModal = $("#pay-options-modal");
  const payClose = $("#pay-close"); // legacy single-id close (kept)
  const payForm = $("#pay-options-form");
  const payStatus = $("#pay-options-status");

  function openPayModal(){ payModal?.classList.remove("hidden"); }
  function closePayModal(){ payModal?.classList.add("hidden"); }

  function isLoggedIn() { return !!(localStorage.getItem("jwt_access") || ""); }

  // --- CSRF helpers ---
  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
    return null;
  }
  function csrfHeader(initHeaders) {
    const token = getCookie("csrftoken") || getCookie("CSRF-TOKEN") || getCookie("XSRF-TOKEN");
    const headers = initHeaders ? new Headers(initHeaders) : new Headers();
    if (token) headers.set("X-CSRFToken", token);
    return headers;
  }

  // === read a table number if present (supports common field names) ===
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

  async function setCartMeta(serviceType, tableNumber){
    const payload = { service_type: serviceType };
    if (serviceType === "DINE_IN" && tableNumber) {
      const t = parseInt(tableNumber, 10);
      payload.table_number = t;
      payload.table_num = t;
    }
    await fetch("/api/orders/cart/meta/", {
      method: "POST",
      credentials: "include",
      headers: csrfHeader({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload)
    });
  }

  async function createOrderAndMaybeGo(serviceType, tableNumber){
    const payload = { service_type: serviceType };
    if (serviceType === "DINE_IN" && tableNumber) {
      const t = parseInt(tableNumber, 10);
      payload.table_number = t;
      payload.table_num = t;
    }

    const r = await fetch("/api/orders/orders/", {
      method: "POST",
      headers: csrfHeader({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify(payload),
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || "Failed to create order");

    // Aggregators (accept both spellings, normalize to UBER_EATS)
    const isUber = (serviceType === "UBEREATS" || serviceType === "UBER_EATS");
    if (isUber || serviceType === "DOORDASH") {
      const code = isUber ? "UBER_EATS" : serviceType;
      const opt = (d.external_options || []).find(o => o.code === code);
      if (opt && opt.url) { window.location.href = opt.url; return; }
      throw new Error(code + " is not configured.");
    }

    // Stripe path
    if (d.checkout_url) { window.location.href = d.checkout_url; return; }

    const orderId = d.id || d.pk;
    if (!orderId) throw new Error("Order created but no id returned.");

    // Try POST to get { url }
    try {
      const s = await fetch(`/payments/create-checkout-session/${orderId}/`, {
        method: "POST",
        headers: csrfHeader({ "Content-Type": "application/json" }),
        credentials: "include",
      });
      const j = await s.json().catch(() => ({}));
      if (s.ok && j && j.url) { window.location.assign(j.url); return; }
    } catch (_) {}

    // Final fallback: server will 302 to Stripe
    window.location.assign(`/payments/create-checkout-session/${orderId}/`);
  }

  async function handlePay(){
    if (!isLoggedIn()) {
      window.__continueCheckoutAfterAuth = async () => { openPayModal(); };
      if (typeof window.__openAuthModalForPay === "function") window.__openAuthModalForPay();
      return;
    }
    openPayModal();
  }

  // Wire Pay button
  payBtn?.addEventListener("click", async (e) => { e.preventDefault(); await handlePay(); });

  // Close buttons (support both legacy #pay-close and .pay-close)
  payClose?.addEventListener("click", (e) => { e.preventDefault(); closePayModal(); });
  document.querySelectorAll(".pay-close").forEach(btn => {
    btn.addEventListener("click", (e) => { e.preventDefault(); closePayModal(); });
  });

  // Click outside modal content closes the modal (overlay click)
  payModal?.addEventListener("mousedown", (e) => {
    if (e.target === payModal) closePayModal();
  });

  // ESC key closes modal
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closePayModal();
  });

  // Submit chosen service type
  payForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (payStatus) payStatus.textContent = "Preparing checkout…";
    try {
      const st = (new FormData(payForm).get("service_type") || "DINE_IN").toString().toUpperCase();
      const tableNo = getTableNumber();
      if (st === "DINE_IN" && !tableNo) {
        if (payStatus) payStatus.textContent = "Please enter a table number for Dine-In.";
        return;
      }
      await setCartMeta(st, tableNo);
      await createOrderAndMaybeGo(st, tableNo);
    } catch (err) {
      if (payStatus) payStatus.textContent = (err && err.message) || "Unable to start checkout.";
    }
  });

  // After auth flow, if continuation is set to show pay modal:
  if (typeof window.__continueCheckoutAfterAuth !== "function") {
    window.__continueCheckoutAfterAuth = async () => { openPayModal(); };
  }
})();
