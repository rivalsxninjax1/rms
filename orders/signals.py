# orders/signals.py
from __future__ import annotations

from decimal import Decimal
from typing import Dict, List

from django.contrib.auth.signals import user_logged_in
from django.db import transaction
from django.dispatch import receiver

from menu.models import MenuItem
from .models import Order, OrderItem


def _normalize_items(items_in: List[Dict]) -> List[Dict[str, int]]:
    """
    Accept flexible shapes:
    {menu_item_id, quantity} OR {menu_item, quantity} OR {id, qty}
    -> returns list[{id, quantity}]
    """
    out: List[Dict[str, int]] = []
    for raw in (items_in or []):
        pid = (
            raw.get("menu_item_id")
            or raw.get("menu_item")
            or raw.get("product")
            or raw.get("id")
        )
        qty = raw.get("quantity", raw.get("qty", 1))
        try:
            pid = int(pid)
            qty = max(1, int(qty))
        except Exception:
            continue
        out.append({"id": pid, "quantity": qty})
    return out


@receiver(user_logged_in)
def merge_session_cart_into_user(sender, user, request, **kwargs):
    """
    On login, merge the guest's session cart into a persistent DB cart:
    - Find or create a PENDING Order for the user
    - Upsert OrderItems and increase quantities
    - DO NOT clear the session cart here (UI keeps showing the same items)
    - Checkout prefers the DB cart, so no duplicates occur
    """
    session_items_raw = request.session.get("cart", [])
    items = _normalize_items(session_items_raw)
    if not items:
        return

    with transaction.atomic():
        order = (
            Order.objects.select_for_update()
            .filter(created_by=user, status="PENDING", is_paid=False)
            .order_by("-id")
            .first()
        )
        if not order:
            order = Order.objects.create(created_by=user, status="PENDING")

        existing = {oi.menu_item_id: oi for oi in order.items.select_related("menu_item").all()}

        for it in items:
            pid, qty = it["id"], it["quantity"]
            mi = MenuItem.objects.get(pk=pid)
            unit = Decimal(str(getattr(mi, "price", 0)))
            if pid in existing:
                oi = existing[pid]
                oi.quantity = int(oi.quantity) + qty
                # Update to current price (keeps totals fresh)
                oi.unit_price = unit
                oi.save(update_fields=["quantity", "unit_price"])
            else:
                OrderItem.objects.create(
                    order=order, menu_item=mi, quantity=qty, unit_price=unit
                )
