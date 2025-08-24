(function () {
  function getCookie(name) {
    const v = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return v ? v.pop() : "";
  }
  const csrftoken = getCookie("csrftoken");

  function getLS() {
    try { return JSON.parse(localStorage.getItem("cart") || "[]"); }
    catch(_) { return []; }
  }
  function setLS(items) {
    localStorage.setItem("cart", JSON.stringify(items));
  }

  async function syncWithServer(items) {
    try {
      const res = await fetch("/api/cart/sync/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrftoken },
        body: JSON.stringify({ items })
      });
      return await res.json();
    } catch (e) {
      console.error("Cart sync failed", e);
      return { items };
    }
  }

  function normalizeItem(it) {
    const id = parseInt(it.menu_item || it.id || it.menu || it.menu_id || it.product || it.product_id, 10);
    const qty = parseInt(it.quantity || it.qty || it.q || 1, 10);
    if (!id || id <= 0 || !qty || qty <= 0) return null;
    return { menu_item: id, quantity: qty };
  }

  function upsertCartLS(menuId, qtyDelta) {
    const idNum = parseInt(menuId, 10);
    const items = getLS()
      .map(normalizeItem)
      .filter(Boolean);

    const idx = items.findIndex(it => it.menu_item === idNum);
    if (idx === -1) items.push({ menu_item: idNum, quantity: Math.max(1, qtyDelta) });
    else items[idx].quantity = Math.max(1, (parseInt(items[idx].quantity, 10) || 1) + qtyDelta);

    setLS(items);
    return items;
  }

  document.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-add-to-cart]");
    if (!btn) return;

    e.preventDefault();
    const menuId = btn.getAttribute("data-menu-id") || btn.getAttribute("data-id");
    if (!menuId) { console.warn("Missing data-menu-id"); return; }

    const qtyInput = document.querySelector("[data-qty-input]");
    const qty = qtyInput ? (parseInt(qtyInput.value, 10) || 1) : 1;

    const merged = upsertCartLS(menuId, qty);
    await syncWithServer(merged);

    btn.disabled = true;
    const prev = btn.innerText;
    btn.innerText = "Added ✓";
    setTimeout(() => { btn.disabled = false; btn.innerText = prev || "Add to cart"; }, 1200);
  });

  // On page load (including after login), sync LS -> session
  (async function bootstrapSync() {
    const items = getLS().map(normalizeItem).filter(Boolean);
    if (items.length) await syncWithServer(items);
  })();
})();
