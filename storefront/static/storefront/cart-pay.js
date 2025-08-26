/* storefront/static/storefront/cart-pay.js
 * Pay flow with "service_type" selection. Never clears cart here.
 * - Preserves cart across login (backup before auth, restore after login)
 * - Inline method radios above Pay; Pay disabled until valid selection
 * - Dine-in immediately prompts for Table # via modal
 */
(function () {
  // ---------- small helpers ----------
  const $ = (sel, el=document) => el.querySelector(sel);

  // CSRF helpers (needed for POSTs)
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

  function isLoggedIn() { return !!(localStorage.getItem("jwt_access") || ""); }

  // ---- cart backup/restore (to survive login redirects) ----
  const LS_CART = "cart_backup_v1";
  const LS_CHOICE = "cart_choice_v1";

  async function fetchCart() {
    const r = await fetch("/api/orders/cart/", { credentials: "include" });
    if (!r.ok) return { items: [] };
    return r.json();
  }
  async function setCart(items) {
    return fetch("/api/orders/cart/", {
      method: "POST",
      credentials: "include",
      headers: csrfHeader({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        items: (items || []).map(it => ({
          id: it.id || it.menu_item || it.menu_item_id,
          quantity: it.quantity || 1
        }))
      })
    });
  }
  async function backupCartNow() {
    try {
      const data = await fetchCart();
      const items = Array.isArray(data.items) ? data.items : [];
      localStorage.setItem(LS_CART, JSON.stringify(items));
    } catch(_) {}
  }
  async function restoreCartIfEmpty() {
    try {
      const data = await fetchCart();
      const items = Array.isArray(data.items) ? data.items : [];
      if (items.length === 0) {
        const backup = localStorage.getItem(LS_CART);
        if (backup) {
          const parsed = JSON.parse(backup);
          if (Array.isArray(parsed) && parsed.length > 0) {
            await setCart(parsed);
          }
        }
      } else {
        localStorage.setItem(LS_CART, JSON.stringify(items));
      }
    } catch(_) {}
  }

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

    // Aggregators (accept both spellings; normalize to UBER_EATS)
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

  // ---------- bind after DOM is ready ----------
  function ready(fn){
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  ready(function initCartPay() {
    const payBtn   = $("#pay-btn");
    const payModal = $("#pay-options-modal");
    const payForm  = $("#pay-options-form");
    const payStatus= $("#pay-options-status");
    const tableWrap= $("#table-number-wrapper");
    const inlineChoices = document.getElementsByName("order_method_inline");

    // Force hidden by default (don’t rely on CSS class existing)
    if (payModal) { payModal.style.display = "none"; }

    function openPayModal(){
      if (!payModal) return;
      payModal.style.display = "flex";
      payModal.classList.remove("hidden");
    }
    function closePayModal(){
      if (!payModal) return;
      payModal.style.display = "none";
      payModal.classList.add("hidden");
    }

    // selection state
    let selectedMethod = null;   // "DINE_IN" | "UBER_EATS" | "DOORDASH"
    let selectionReady = false;  // Pay enabled only if true
    let dineInTable = null;

    function setPayEnabled(on) {
      if (!payBtn) return;
      payBtn.disabled = !on;
    }
    setPayEnabled(false); // start disabled until user picks a method

    // When user picks a method inline
    inlineChoices.forEach(el => {
      el.addEventListener("change", async () => {
        selectedMethod = el.value.toUpperCase();
        selectionReady = false;
        setPayEnabled(false);

        // remember choice (so we can resume after login)
        localStorage.setItem(LS_CHOICE, JSON.stringify({ method: selectedMethod, table: dineInTable }));

        if (selectedMethod === "DINE_IN") {
          // sync modal radios + show table field, then open modal
          try {
            payForm?.querySelectorAll("input[name='service_type']").forEach(r => {
              r.checked = (r.value.toUpperCase() === "DINE_IN");
            });
            if (tableWrap) tableWrap.style.display = "block";
          } catch(_) {}
          openPayModal();
        } else {
          // aggregator selected → set meta, enable Pay
          try { await setCartMeta(selectedMethod, null); } catch(_) {}
          selectionReady = true;
          setPayEnabled(true);
        }
      });
    });

    // Close buttons (any .pay-close or legacy #pay-close)
    document.addEventListener("click", (e) => {
      const tgt = e.target;
      if (!tgt) return;
      if (tgt.closest && (tgt.closest(".pay-close") || tgt.closest("#pay-close"))) {
        e.preventDefault();
        closePayModal();
        // if Dine-in modal canceled, keep Pay disabled until user re-chooses
        if (selectedMethod === "DINE_IN" && !dineInTable) {
          selectionReady = false;
          setPayEnabled(false);
        }
      }
    });

    // Overlay click closes modal
    payModal?.addEventListener("click", (e) => {
      const content = payModal.firstElementChild;
      if (!content) return;
      if (!content.contains(e.target)) {
        closePayModal();
        if (selectedMethod === "DINE_IN" && !dineInTable) {
          selectionReady = false;
          setPayEnabled(false);
        }
      }
    });

    // ESC closes modal
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        closePayModal();
        if (selectedMethod === "DINE_IN" && !dineInTable) {
          selectionReady = false;
          setPayEnabled(false);
        }
      }
    });

    // Submit Dine-in table in modal
    payForm?.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (payStatus) payStatus.textContent = "Saving…";
      try {
        const st = (new FormData(payForm).get("service_type") || "").toString().toUpperCase();
        if (st !== "DINE_IN") selectedMethod = st || selectedMethod;
        const tableNo = getTableNumber();
        if (!tableNo) {
          if (payStatus) payStatus.textContent = "Please enter a valid table number.";
          return;
        }
        dineInTable = tableNo;
        localStorage.setItem(LS_CHOICE, JSON.stringify({ method: "DINE_IN", table: dineInTable }));
        await setCartMeta("DINE_IN", dineInTable);
        selectionReady = true;
        setPayEnabled(true);
        if (payStatus) payStatus.textContent = "";
        closePayModal();
      } catch (err) {
        if (payStatus) payStatus.textContent = (err && err.message) || "Unable to save.";
      }
    });

    // Pay button: only proceeds when selectionReady
    payBtn?.addEventListener("click", async (e) => {
      e.preventDefault();
      if (!selectionReady || !selectedMethod) {
        const hint = $("#order-method-hint");
        if (hint) { hint.style.color = "#b00"; setTimeout(()=>hint.style.color="#666", 1500); }
        return;
      }

      // Backup cart before any redirect to login
      await backupCartNow();

      if (!isLoggedIn()) {
        // define continuation ONLY when user actually tried to pay
        window.__continueCheckoutAfterAuth = async () => {
          await restoreCartIfEmpty();

          // re-apply saved choice
          const saved = JSON.parse(localStorage.getItem(LS_CHOICE) || "{}");
          const method = (saved.method || selectedMethod || "").toUpperCase();
          const table  = saved.table || dineInTable || null;

          if (method === "DINE_IN" && !table) {
            try {
              payForm?.querySelectorAll("input[name='service_type']").forEach(r => {
                r.checked = (r.value.toUpperCase() === "DINE_IN");
              });
              if (tableWrap) tableWrap.style.display = "block";
            } catch(_) {}
            openPayModal();
            return;
          }

          try { await setCartMeta(method, table); } catch(_) {}
          await createOrderAndMaybeGo(method, table);
        };
        if (typeof window.__openAuthModalForPay === "function") window.__openAuthModalForPay();
        return;
      }

      // Logged in
      await createOrderAndMaybeGo(selectedMethod, dineInTable);
    });

    // If returning from login organically, attempt a one-time restore silently
    restoreCartIfEmpty();
  });
})();
