# coupons/services.py
from __future__ import annotations

from decimal import Decimal
from typing import Optional, Tuple

from django.db import transaction
from django.db.models import Q

from .models import Coupon


def _norm(code: str) -> str:
    return (code or "").strip().upper()


def find_active_coupon(code: str) -> Optional[Coupon]:
    """
    Find a coupon by code OR phrase (case-insensitive) and ensure it's live.
    Your Coupon model exposes: code, phrase, percent, is_live()
    """
    c = _norm(code)
    if not c:
        return None
    obj = Coupon.objects.filter(Q(code__iexact=c) | Q(phrase__iexact=c)).first()
    if obj and getattr(obj, "is_live", None) and obj.is_live():
        return obj
    return None


def apply_coupon_code_to_order(order, code: str) -> Tuple[bool, str]:
    """
    Attach coupon by code to an order in a flexible way:
      - order.coupon_percent / order.discount_percent
      - order.coupon_code
      - order.coupon (FK to Coupon) if present
      - order.discount_amount (rough estimate; final amount recomputed in payments.services)
    Returns (ok, message).
    """
    c = find_active_coupon(code)
    if not c:
        return False, "Invalid or inactive coupon"

    updated = []

    # % fields
    if hasattr(order, "coupon_percent"):
        setattr(order, "coupon_percent", int(c.percent))
        updated.append("coupon_percent")
    elif hasattr(order, "discount_percent"):
        setattr(order, "discount_percent", int(c.percent))
        updated.append("discount_percent")

    # Code field
    if hasattr(order, "coupon_code"):
        setattr(order, "coupon_code", c.code)
        updated.append("coupon_code")

    # Relation
    if hasattr(order, "coupon_id"):
        try:
            order.coupon = c
            updated.append("coupon_id")
        except Exception:
            pass

    # Optional: set discount_amount best-effort from items
    if hasattr(order, "discount_amount"):
        try:
            subtotal = Decimal("0.00")
            for it in order.items.all():
                line_total = getattr(it, "line_total", None)
                if line_total is not None:
                    subtotal += Decimal(str(line_total))
                else:
                    qty = Decimal(str(getattr(it, "quantity", 0)))
                    unit = Decimal(str(getattr(it, "unit_price", 0)))
                    subtotal += (qty * unit)
            discount = (subtotal * Decimal(int(c.percent)) / Decimal(100)).quantize(Decimal("0.01"))
            setattr(order, "discount_amount", discount)
            updated.append("discount_amount")
        except Exception:
            pass

    if updated:
        try:
            order.save(update_fields=list(set(updated)))
        except Exception:
            order.save()

    # Optionally increment usage (you can also move this to mark_paid)
    try:
        with transaction.atomic():
            c.times_used = (c.times_used or 0) + 1
            c.save(update_fields=["times_used"])
    except Exception:
        pass

    return True, f"Applied {c.percent}% off"
