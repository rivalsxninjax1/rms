/* storefront/static/storefront/my-orders.js
 * Rebuild cart from a previous order and jump to /cart/
 */

(function(){
  function getCart(){ try { return JSON.parse(localStorage.getItem("cart") || "[]"); } catch { return []; } }
  function saveCart(cart){
    localStorage.setItem("cart", JSON.stringify(cart));
    if (typeof updateCartBadge === "function") updateCartBadge();
  }

  function setCartFromOrder(items, replace=true){
    const norm = (items || []).map(it => ({
      id: Number(it.id),
      name: it.name || `Item ${it.id}`,
      price: Number(it.price || 0),
      image: it.image || null,
      qty: Number(it.qty || it.quantity || 1),
    })).filter(x => x.id > 0 && x.qty > 0);

    let cart = replace ? [] : getCart();

    norm.forEach(n => {
      const idx = cart.findIndex(c => Number(c.id) === n.id);
      if (idx >= 0){
        cart[idx].qty = Number(cart[idx].qty || 0) + n.qty;
        // Keep the most recent name/price/image
        cart[idx].name = n.name || cart[idx].name;
        cart[idx].price = n.price || cart[idx].price;
        cart[idx].image = n.image || cart[idx].image;
      } else {
        cart.push(n);
      }
    });

    saveCart(cart);
  }

  document.addEventListener("click", (e) => {
    const btn = e.target.closest(".btn-reorder");
    if (!btn) return;

    const raw = btn.getAttribute("data-items") || "[]";
    let items = [];
    try { items = JSON.parse(raw); } catch { items = []; }

    // Replace cart with the reorder list for clarity
    setCartFromOrder(items, true);
    window.location.href = "/cart/";
  });
})();
