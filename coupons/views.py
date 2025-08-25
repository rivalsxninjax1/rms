from __future__ import annotations

import json
from django.views.decorators.http import require_GET, require_POST
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404

from .services import find_active_coupon, compute_discount_for_order
from orders.models import Order


@require_GET
def validate_coupon(request):
    code = (request.GET.get("code") or "").strip()
    c = find_active_coupon(code)
    if c:
        return JsonResponse({"valid": True, "percent": int(c.percent), "message": f"{c.percent}% discount"})
    return JsonResponse({"valid": False, "message": "Invalid coupon"}, status=404)


@require_POST
@login_required(login_url="/")
def apply_coupon_to_session(request):
    try:
        data = json.loads(request.body or "{}")
        code = (data.get("code") or "").strip()
    except Exception:
        code = ""
    c = find_active_coupon(code)
    if not c:
        return JsonResponse({"ok": False, "message": "Invalid coupon"}, status=400)
    request.session["coupon_code"] = c.code
    request.session.modified = True
    return JsonResponse({"ok": True, "message": f"Coupon {c.code} applied ({c.percent}% off)"})


@require_POST
@login_required(login_url="/")
def apply_coupon_to_order_view(request):
    try:
        data = json.loads(request.body or "{}")
    except Exception:
        data = {}
    code = (data.get("code") or "").strip()
    order_id = data.get("order_id")

    if not (order_id and code):
        return JsonResponse({"ok": False, "message": "order_id and code required"}, status=400)

    order = get_object_or_404(Order, pk=order_id)
    c = find_active_coupon(code)
    ok, discount, reason = compute_discount_for_order(order, c, request.user)
    if not ok:
        return JsonResponse({"ok": False, "message": reason}, status=400)

    order.discount_code = c.code
    order.discount_amount = discount
    order.save(update_fields=["discount_code", "discount_amount"])
    return JsonResponse({"ok": True, "message": f"Applied {c.code} (-{c.percent}%)", "discount": str(discount)})
