// Basic storefront JS: product listing + cart
const grid = document.getElementById("product-grid");
const cartCountEl = document.getElementById("cart-count");
const authLink = document.getElementById("auth-link");

function getCart() { return JSON.parse(localStorage.getItem("cart") || "[]"); }
function setCart(items) { localStorage.setItem("cart", JSON.stringify(items)); updateCartCount(); }
function updateCartCount() {
  const c = getCart().reduce((s,i)=>s + Number(i.qty||0), 0);
  if (cartCountEl) cartCountEl.textContent = c;
}
function jwt() { return localStorage.getItem("jwt_access") || ""; }

async function fetchMenu() {
  try {
    const res = await fetch("/api/menu/items/");
    const data = await res.json();
    renderProducts(Array.isArray(data) ? data : (data.results || []));
  } catch (e) {
    if (grid) grid.innerHTML = "<p>Failed to load products.</p>";
  }
}

function renderProducts(items) {
  if (!grid) return;
  if (!items.length) { grid.innerHTML = "<p>No products.</p>"; return; }
  grid.innerHTML = items.map(item => `
    <div class="card">
      <h3>${item.name || item.title || "Item"}</h3>
      <p>${item.description || ""}</p>
      <strong>${Number(item.price || item.unit_price || item.amount || 0).toFixed(2)}</strong>
      <div style="margin-top:8px">
        <button data-id="${item.id}" data-name="${item.name || "Item"}"
                data-price="${item.price || item.unit_price || 0}">Add to Cart</button>
      </div>
    </div>
  `).join("");

  grid.querySelectorAll("button").forEach(btn => {
    btn.addEventListener("click", () => {
      const id = Number(btn.dataset.id);
      const name = btn.dataset.name;
      const unit_price = Number(btn.dataset.price);
      const current = getCart();
      const found = current.find(i => i.menu_item === id);
      if (found) {
        found.qty += 1;
        found.total = (found.qty * unit_price).toFixed(2);
      } else {
        current.push({ menu_item: id, name, qty: 1, unit_price: unit_price.toFixed(2), total: unit_price.toFixed(2) });
      }
      setCart(current);
    });
  });
}

function initAuthLink() {
  if (!authLink) return;
  if (jwt()) {
    authLink.textContent = "Logout";
    authLink.addEventListener("click", (e) => {
      e.preventDefault();
      localStorage.removeItem("jwt_access");
      localStorage.removeItem("jwt_refresh");
      location.reload();
    });
  }
}

document.addEventListener("DOMContentLoaded", () => {
  updateCartCount();
  initAuthLink();
  if (grid) fetchMenu(); // only on index page
});
