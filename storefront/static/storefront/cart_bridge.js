/* storefront/static/storefront/cart-bridge.js
 * Bridges JWT login -> Django session, then merges session cart to DB cart.
 * Keeps cart intact unless payment succeeds or user manually empties it.
 */
(function () {
  async function sessionBridgeFromJWT() {
    const tok = localStorage.getItem("jwt_access") || "";
    if (!tok) return false;
    await fetch("/accounts/auth/session/", {
      method: "POST",
      headers: { "Authorization": "Bearer " + tok },
      credentials: "include",
    }).catch(()=>{});
    await fetch("/api/orders/cart/merge/", {
      method: "POST",
      credentials: "include",
    }).catch(()=>{});
    return true;
  }

  // Monkey-patch the global auth.set if present
  try {
    if (window.auth && typeof window.auth.set === "function") {
      const orig = window.auth.set.bind(window.auth);
      window.auth.set = function (a, r) {
        orig(a, r);
        sessionBridgeFromJWT();
      };
    }
  } catch (e) { /* no-op */ }
})();
