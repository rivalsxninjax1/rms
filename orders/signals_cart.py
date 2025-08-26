# orders/signals_cart.py
from __future__ import annotations
from collections import defaultdict
from typing import Any, Dict, List

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

# Helper: normalize a cart list (prevent duplicates)
def _normalize_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    bucket = defaultdict(lambda: {"quantity": 0, "extras": []})
    for it in items or []:
        # expected keys in your session cart: menu_item (id), quantity, notes/options...
        key = str(it.get("menu_item") or it.get("id") or it.get("sku") or "")
        if not key:
            continue
        qty = int(it.get("quantity") or 0)
        bucket[key]["quantity"] += max(0, qty)
        # carry over optional fields if you need them
        if it.get("notes"):
            bucket[key]["extras"].append({"notes": it["notes"]})
    merged = []
    for key, agg in bucket.items():
        merged.append({"menu_item": int(key), "quantity": max(1, agg["quantity"])})
    return merged

@receiver(user_logged_in)
def merge_session_cart_into_user(sender, user, request, **kwargs):
    """
    On login: merge session cart items with any user-bound draft/cart order if your project has one.
    If there isn't a persistent user cart, we keep the merged list in session (no duplicates).
    """
    try:
        sess_items = request.session.get("cart") or []
        if not isinstance(sess_items, list):
            sess_items = []
        sess_items = _normalize_items(sess_items)

        # Try to merge with a user "draft/cart" order if your app uses it.
        # This block is best-effort and will no-op if your data model differs.
        try:
            from orders.models import Order, OrderItem  # your app model names
            draft = (
                Order.objects.filter(customer=user, status__in=["CART", "DRAFT", "PENDING"])
                .order_by("-id").first()
            )
            if draft:
                # build current db map
                db_map = {}
                for oi in draft.items.all():
                    k = str(getattr(oi, "menu_item_id", None) or getattr(oi, "product_id", None))
                    if not k:
                        continue
                    db_map[k] = oi

                # merge into order items
                for it in sess_items:
                    k = str(it["menu_item"])
                    q = int(it["quantity"])
                    if k in db_map:
                        # bump quantity, avoid duplicates
                        oi = db_map[k]
                        oi.quantity = max(1, int(getattr(oi, "quantity", 1)) + q)
                        oi.save(update_fields=["quantity"])
                    else:
                        # create a new OrderItem (match your field names)
                        OrderItem.objects.create(
                            order=draft,
                            menu_item_id=it["menu_item"],
                            quantity=q,
                            unit_price=getattr(oi, "unit_price", 0) if (oi:=None) else 0,  # safe default
                        )
                # now that db contains both, clear session cart
                request.session["cart"] = []
                request.session.modified = True
                return
        except Exception:
            # If models/fields don't match, just keep it in session after normalization.
            pass

        # Fallback: store normalized merged items back in session (no duplicates)
        request.session["cart"] = sess_items
        request.session.modified = True
    except Exception:
        # Never break login
        pass

@receiver(user_logged_out)
def clear_cart_on_logout(sender, request, user, **kwargs):
    """
    Spec requires: when a logged-out user opens the site, cart should start at zero.
    Easiest predictable point is logout → clear cart.
    """
    try:
        request.session["cart"] = []
        request.session.modified = True
    except Exception:
        pass
