# orders/views.py
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Tuple

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import action

from .models import Order, OrderItem
from menu.models import MenuItem
from payments.services import create_checkout_session, save_invoice_pdf_file


# ---------- Helpers ----------

def _currency() -> str:
    return getattr(settings, "STRIPE_CURRENCY", "usd").lower()

def _fetch_menu_item(mi_id: int) -> Tuple[str, Decimal]:
    mi = MenuItem.objects.get(pk=mi_id)
    price = Decimal(str(getattr(mi, "price", 0)))
    return (mi.name, price)

def _normalize_items(items_in: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Flexible input: supports {menu_item_id, quantity} or {menu_item, quantity} or {id, qty}
    -> returns list[{id, quantity}]
    """
    out: List[Dict[str, Any]] = []
    for raw in items_in or []:
        pid = raw.get("menu_item_id") or raw.get("menu_item") or raw.get("product") or raw.get("id")
        qty = raw.get("quantity") or raw.get("qty") or 1
        try:
            pid = int(pid)
            qty = int(qty)
        except Exception:
            continue
        if pid > 0 and qty > 0:
            out.append({"id": pid, "quantity": qty})
    return out

def _cart_get(request) -> List[Dict[str, Any]]:
    return list(request.session.get("cart", []))

def _cart_set(request, items: List[Dict[str, Any]]):
    # IMPORTANT: never flush the whole session — only update the cart key.
    request.session["cart"] = items
    request.session.modified = True

def _cart_meta_get(request) -> Dict[str, Any]:
    return dict(request.session.get("cart_meta", {}))

def _cart_meta_set(request, meta: Dict[str, Any]):
    # Stores metadata like service_type. Never flushes.
    request.session["cart_meta"] = meta
    request.session.modified = True

def _enrich(items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Decimal]:
    """
    Enrich items with name/unit_price/line_total from DB and compute subtotal.
    """
    enriched: List[Dict[str, Any]] = []
    subtotal = Decimal("0")
    for it in items:
        pid, qty = int(it["id"]), int(it["quantity"])
        name, unit = _fetch_menu_item(pid)
        line = (unit * qty).quantize(Decimal("0.01"))
        enriched.append({
            "id": pid, "name": name, "quantity": qty,
            "unit_price": str(unit), "line_total": str(line),
        })
        subtotal += line
    return enriched, subtotal.quantize(Decimal("0.01"))


# ---------- Cart (Session) ----------

class SessionCartViewSet(viewsets.ViewSet):
    """
    Session-scoped cart for guests.
    IMPORTANT: never flush the whole session here.
    """
    permission_classes = [AllowAny]

    def list(self, request):
        items = _normalize_items(_cart_get(request))
        enriched, subtotal = _enrich(items)
        meta = _cart_meta_get(request)
        return Response({"items": enriched, "subtotal": str(subtotal), "currency": _currency(), "meta": meta})

    def create(self, request):
        # Replace entire cart (no flush)
        items = _normalize_items(request.data.get("items", []))
        _cart_set(request, items)
        enriched, subtotal = _enrich(items)
        return Response({"status": "ok", "items": enriched, "subtotal": str(subtotal), "currency": _currency()})

    @action(methods=["post"], detail=False, url_path="items", permission_classes=[AllowAny])
    def add_item(self, request):
        items = _normalize_items(_cart_get(request))
        payload = _normalize_items([request.data])
        if payload:
            add = payload[0]
            for it in items:
                if it["id"] == add["id"]:
                    it["quantity"] = int(it["quantity"]) + int(add["quantity"])
                    break
            else:
                items.append(add)
            _cart_set(request, items)
        enriched, subtotal = _enrich(items)
        return Response({"items": enriched, "subtotal": str(subtotal), "currency": _currency()})

    @action(methods=["post"], detail=False, url_path="items/remove", permission_classes=[AllowAny])
    def remove_item(self, request):
        pid = request.data.get("menu_item_id") or request.data.get("id")
        try:
            pid = int(pid)
        except Exception:
            pid = 0
        items = [it for it in _normalize_items(_cart_get(request)) if it["id"] != pid]
        _cart_set(request, items)
        enriched, subtotal = _enrich(items)
        return Response({"items": enriched, "subtotal": str(subtotal), "currency": _currency()})

    @action(methods=["post"], detail=False, url_path="meta", permission_classes=[AllowAny])
    def set_meta(self, request):
        """
        Set cart meta safely (e.g., service_type). Never flush.
        Body: { "service_type": "DINE_IN" | "UBEREATS" | "DOORDASH" | "TAKEAWAY" }
        """
        allowed = {"DINE_IN", "UBEREATS", "DOORDASH", "TAKEAWAY"}
        meta = _cart_meta_get(request)
        st = str(request.data.get("service_type", "")).upper().strip()
        if st and st in allowed:
            meta["service_type"] = st
        _cart_meta_set(request, meta)
        return Response({"status": "ok", "meta": meta})

    @action(methods=["post"], detail=False, url_path="reset_session", permission_classes=[AllowAny])
    def reset_session(self, request):
        """
        Only clear cart-related keys; DO NOT flush the session (prevents losing sessionid cookie).
        This is intentionally called only after successful payment.
        """
        request.session.pop("cart", None)
        request.session.pop("cart_meta", None)
        request.session.pop("applied_coupon", None)
        request.session.modified = True
        return Response({"status": "ok"})

    @action(methods=["post"], detail=False, url_path="merge", permission_classes=[IsAuthenticated])
    def merge(self, request):
        """
        Manual merge after login (idempotent).
        Takes the session cart and upserts into user's PENDING DB order.
        """
        session_items = _normalize_items(_cart_get(request))
        if not session_items:
            return Response({"status": "noop", "detail": "empty session cart"})

        with transaction.atomic():
            order = (
                Order.objects.select_for_update()
                .filter(created_by=request.user, status="PENDING", is_paid=False)
                .order_by("-id").first()
            )
            if not order:
                order = Order.objects.create(created_by=request.user, status="PENDING")

            existing = {oi.menu_item_id: oi for oi in order.items.select_related("menu_item")}
            for it in session_items:
                pid, qty = int(it["id"]), int(it["quantity"])
                _, unit = _fetch_menu_item(pid)
                if pid in existing:
                    oi = existing[pid]
                    oi.quantity = int(oi.quantity) + qty
                    oi.unit_price = unit
                    oi.save(update_fields=["quantity", "unit_price"])
                else:
                    OrderItem.objects.create(order=order, menu_item_id=pid, quantity=qty, unit_price=unit)
        return Response({"status": "ok", "order_id": order.id})

    @action(methods=["get"], detail=False, url_path="debug", permission_classes=[AllowAny])
    def debug(self, request):
        """
        Dev helper to diagnose cart/session persistence.
        GET /api/orders/cart/debug/
        If session_key changes across page loads, your cookie/host/HTTPS settings are rotating the session.
        """
        sess = request.session
        if "sess_canary" not in sess:
            sess["sess_canary"] = "alive"
            sess.modified = True
        return Response({
            "session_key": getattr(sess, "session_key", None),
            "has_canary": "sess_canary" in sess,
            "cart_len": len(sess.get("cart", [])),
            "cart_meta": sess.get("cart_meta", {}),
            "user": getattr(request.user, "id", None),
            "host": request.get_host(),
            "cookies_seen": sorted([k for k in request.COOKIES.keys() if k.lower().startswith(("session", "csr"))]),
        })


# ---------- Orders (Checkout) ----------

class OrderViewSet(viewsets.ModelViewSet):
    """
    - GET  /api/orders/         -> list (auth only)
    - POST /api/orders/         -> create checkout order. Prefer user's PENDING DB cart.
    """
    queryset = Order.objects.all().order_by("-id")

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [AllowAny()]

    try:
        from .serializers import OrderReadSerializer  # type: ignore
        read_serializer = OrderReadSerializer
    except Exception:
        read_serializer = None

    def get_queryset(self):
        qs = super().get_queryset()
        user = getattr(self.request, "user", None)
        if getattr(user, "is_staff", False):
            return qs
        if user and user.is_authenticated:
            if hasattr(Order, "created_by"):
                return qs.filter(created_by=user)
            if hasattr(Order, "user"):
                return qs.filter(user=user)
        return qs.none()

    def list(self, request, *args, **kwargs):
        if self.read_serializer:
            ser = self.read_serializer(self.get_queryset(), many=True)
            return Response(ser.data)
        data = []
        for o in self.get_queryset():
            items = []
            for it in o.items.all():
                line_total = (Decimal(str(it.unit_price)) * int(it.quantity)).quantize(Decimal("0.01"))
                items.append({
                    "menu_item": getattr(it, "menu_item_id", None),
                    "quantity": it.quantity,
                    "unit_price": str(it.unit_price),
                    "line_total": str(line_total),
                })
            total = sum(Decimal(x["line_total"]) for x in items)
            data.append({
                "id": o.id,
                "status": getattr(o, "status", "PENDING"),
                "is_paid": getattr(o, "is_paid", False),
                "service_type": getattr(o, "service_type", ""),
                "items": items,
                "total": str(total),
                "created_at": timezone.localtime(getattr(o, "created_at", timezone.now())),
            })
        return Response(data)

    def create(self, request, *args, **kwargs):
        """
        Build an Order for checkout:
          - If authenticated and a PENDING order exists -> reuse it (DB cart)
          - Else build from session cart or request.data.items
        Never clear the cart here. Cart is cleared only after successful payment.
        """
        user = getattr(request, "user", None)

        # Determine service_type priority: body > session cart_meta > default
        allowed = {"DINE_IN", "UBEREATS", "DOORDASH", "TAKEAWAY"}
        req_service_type = str(request.data.get("service_type", "")).upper().strip()
        session_meta = _cart_meta_get(request)
        service_type = (
            req_service_type if req_service_type in allowed
            else (session_meta.get("service_type") if session_meta.get("service_type") in allowed else "DINE_IN")
        )

        with transaction.atomic():
            order = None
            items_source: List[Dict[str, Any]] = []

            if user and user.is_authenticated:
                order = (
                    Order.objects.filter(created_by=user, status="PENDING", is_paid=False)
                    .prefetch_related("items__menu_item").first()
                )
                if order and order.items.exists():
                    # subtotal computed from DB items
                    subtotal = sum((oi.unit_price * oi.quantity) for oi in order.items.all())
                    subtotal = Decimal(subtotal).quantize(Decimal("0.01"))
                else:
                    items_source = _normalize_items(request.data.get("items", [])) or _normalize_items(_cart_get(request))
            else:
                items_source = _normalize_items(request.data.get("items", [])) or _normalize_items(_cart_get(request))

            if order is None:
                if not items_source:
                    return Response({"detail": "Cart is empty."}, status=400)
                enriched, subtotal = _enrich(items_source)
                if subtotal <= 0:
                    return Response({"detail": "Invalid cart."}, status=400)

                order = Order()
                if hasattr(order, "created_by") and user and user.is_authenticated:
                    order.created_by = user
                if hasattr(order, "currency"):
                    order.currency = _currency()
                if hasattr(order, "status"):
                    order.status = "PENDING"
                if hasattr(order, "is_paid"):
                    try:
                        order.is_paid = False
                    except Exception:
                        pass
                if hasattr(order, "service_type"):
                    order.service_type = service_type

                # total field
                for tf in ("total", "total_amount", "grand_total", "amount", "subtotal"):
                    if hasattr(order, tf):
                        try:
                            setattr(order, tf, subtotal)
                            break
                        except Exception:
                            pass
                order.save()

                for it in enriched:
                    OrderItem.objects.create(
                        order=order,
                        menu_item_id=it["id"],
                        quantity=int(it["quantity"]),
                        unit_price=Decimal(str(it["unit_price"])),
                    )
            else:
                # sync totals and service_type on existing PENDING order
                total_calc = Decimal("0")
                for oi in order.items.all():
                    total_calc += (oi.unit_price * oi.quantity)
                for tf in ("total", "total_amount", "grand_total", "amount", "subtotal"):
                    if hasattr(order, tf):
                        try:
                            setattr(order, tf, total_calc.quantize(Decimal("0.01")))
                            break
                        except Exception:
                            pass
                if hasattr(order, "currency"):
                    order.currency = _currency()
                if hasattr(order, "service_type"):
                    order.service_type = service_type
                order.save()

            # save a draft invoice (optional pre-payment)
            try:
                save_invoice_pdf_file(order)
            except Exception:
                pass

        # External aggregator choices presented to the client (front-end decides)
        options = []
        dd = getattr(settings, "DOORDASH_ORDER_URL", "") or ""
        ue = getattr(settings, "UBEREATS_ORDER_URL", "") or ""
        if dd:
            options.append({"code": "DOORDASH", "label": "Order via DoorDash", "url": dd})
        if ue:
            options.append({"code": "UBEREATS", "label": "Order via Uber Eats", "url": ue})

        # If service_type is aggregator, front-end should redirect there, not Stripe
        checkout_url = None
        if service_type in {"DINE_IN", "TAKEAWAY"}:
            session = create_checkout_session(order)
            checkout_url = getattr(session, "url", None) if session else None

        # DO NOT clear the session cart here.

        subtotal_resp = None
        for tf in ("total", "total_amount", "grand_total", "amount", "subtotal"):
            if hasattr(order, tf):
                subtotal_resp = getattr(order, tf)
                break

        return Response(
            {
                "id": order.id,
                "checkout_url": checkout_url,  # may be None when choosing aggregator
                "total": str(subtotal_resp) if subtotal_resp is not None else None,
                "currency": _currency(),
                "eta_minutes": 15,
                "external_options": options,
                "service_type": service_type,
            },
            status=201,
        )
