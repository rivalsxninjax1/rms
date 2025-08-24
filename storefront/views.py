# storefront/views.py
from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import FieldDoesNotExist
from django.shortcuts import render, get_object_or_404
from django.views.generic import TemplateView

# Optional, robust imports (won't crash if app/model not ready)
try:
    from menu.models import MenuItem  # used by MenuItemsView & menu_item
except Exception:  # pragma: no cover
    MenuItem = None

try:
    from orders.models import Order  # used by MyOrdersView
except Exception:  # pragma: no cover
    Order = None


def _ctx(page: str | None = None, **kw):
    """
    Small helper to add a 'page' flag for active nav highlighting.
    """
    base = {"page": page or ""}
    base.update(kw)
    return base


# -------------------------
# Existing function-based views you already had
# -------------------------
def home(request):
    return render(request, "storefront/index.html", _ctx("home"))


def about(request):
    return render(request, "storefront/about.html", _ctx("about"))


def branches(request):
    return render(request, "storefront/branches.html", _ctx("branches"))


def menu_item(request, item_id: int):
    """
    Detail page: fetch the real MenuItem so the template can show
    name, price, image and full description set in RMS Admin.
    """
    if MenuItem is None:
        return render(request, "storefront/menu_item.html", _ctx("menu_item", item=None))
    item = get_object_or_404(MenuItem, pk=item_id)
    return render(request, "storefront/menu_item.html", _ctx("menu_item", item=item))


def cart(request):
    return render(request, "storefront/cart.html", _ctx("cart"))


def checkout(request):
    return render(request, "storefront/checkout.html", _ctx("checkout"))


def orders(request):
    """
    Legacy page you already had; kept as-is to avoid breaking links.
    """
    return render(request, "storefront/orders.html", _ctx("orders"))


def contact(request):
    return render(request, "storefront/contact.html", _ctx("contact"))


def login_page(request):
    return render(request, "storefront/login.html", _ctx("login"))


def reservations(request):
    return render(request, "storefront/reservations.html", _ctx("reservations"))


# -------------------------
# New/updated class-based views
# -------------------------
class MenuItemsView(TemplateView):
    """
    Server-rendered menu page that actually loads items with images.
    Template: storefront/menu_items.html

    - Works even if MenuItem has no 'is_active' or 'category' fields.
    - Selects related 'category' only if field exists to avoid errors.
    - Orders by category name then item name when possible; otherwise falls back.
    """
    template_name = "storefront/menu_items.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        if MenuItem is None:  # app not ready yet
            ctx["items"] = []
            return ctx

        qs = MenuItem.objects.all()

        # Optional filter: only active items if the field exists
        try:
            MenuItem._meta.get_field("is_active")
        except FieldDoesNotExist:
            pass
        else:
            qs = qs.filter(is_active=True)

        # Optional select_related: only if category FK exists
        category_exists = False
        try:
            MenuItem._meta.get_field("category")
            qs = qs.select_related("category")
            category_exists = True
        except FieldDoesNotExist:
            category_exists = False

        # Ordering: category name then item name if possible; fallback to id
        order_by = []
        if category_exists:
            order_by.append("category__name")
        try:
            MenuItem._meta.get_field("name")
            order_by.append("name")
        except FieldDoesNotExist:
            order_by.append("id")
        qs = qs.order_by(*order_by)

        ctx["items"] = qs
        ctx.update(_ctx("menu"))
        return ctx


class MyOrdersView(LoginRequiredMixin, TemplateView):
    """
    Simple orders history page for the signed-in user.
    Template: storefront/my_orders.html

    - Shows paid status (via related Payment, if present)
    - Shows invoice PDF link (if stored on Order.invoice_pdf)
    """
    template_name = "storefront/my_orders.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        if Order is None:
            ctx["orders"] = []
            return ctx

        qs = (
            Order.objects.filter(created_by=self.request.user)
            .select_related("payment")  # OneToOne if payments app is enabled
            .order_by("-created_at")
        )
        ctx["orders"] = qs
        ctx.update(_ctx("my_orders"))
        return ctx
