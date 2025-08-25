from __future__ import annotations
from decimal import Decimal
from typing import Tuple

from django.db.models import Q
from .models import Coupon
from orders.models import Order


def find_active_coupon(code_or_phrase: str) -> Coupon | None:
    if not code_or_phrase:
        return None
    code = (code_or_phrase or "").strip()
    coupon = (
        Coupon.objects.filter(
            Q(code__iexact=code) | Q(phrase__iexact=code),
            active=True,
        )
        .order_by("-created_at")
        .first()
    )
    if coupon and coupon.is_valid_now():
        return coupon
    return None


def compute_discount_for_order(order: Order, coupon: Coupon | None, user) -> Tuple[bool, Decimal, str]:
    if not coupon:
        return False, Decimal("0.00"), "No coupon"
    if not coupon.is_valid_now():
        return False, Decimal("0.00"), "Coupon not valid"

    pct = Decimal(str(coupon.percent)) / Decimal("100")
    discount = (order.subtotal * pct).quantize(Decimal("0.01"))
    if discount <= 0:
        return False, Decimal("0.00"), "No discount"
    return True, discount, "OK"
