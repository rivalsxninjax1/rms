# orders/views.py
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Tuple, Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from rest_framework import viewsets, status
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
    Accept flexible shapes:
    {menu_item_id, quantity} OR {menu_item, quantity} OR {id, qty}
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
    request.session["cart"] = items
    request.session.modified = True

def _enrich(items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Decimal]:
    """
    Enrich items with name/unit_price/line_total from DB.
    """
    enriched: List[Dict[str, Any]] = []
    subtotal = Decimal("0")
    for it in items:
        pid, qty = int(it["id"]), int(it["quantity"])
        name, unit = _fetch_menu_item(pid)
        line = (unit * qty).quantize(Decimal("0.01"))
        enriched.append({
            "id": pid,
            "name": name,
            "quantity": qty,
            "unit_price": str(unit),
            "line_total": str(line),
        })
        subtotal += line
    return enriched, subtotal.quantize(Decimal("0.01"))


# ---------- Cart (Session) ----------

class SessionCartViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def list(self, request):
        items = _normalize_items(_cart_get(request))
        enriched, subtotal = _enrich(items)
        return Response({"items": enriched, "subtotal": str(subtotal), "currency": _currency()})

    def create(self, request):
        # set entire cart
        items = _normalize_items(request.data.get("items", []))
        _cart_set(request, items)
        enriched, subtotal = _enrich(items)
        return Response({"status": "ok", "items": enriched, "subtotal": str(subtotal), "currency": _currency()})

    @action(methods=["post"], detail=False, url_path="items", permission_classes=[AllowAny])
    def add_item(self, request):
        # POST /api/orders/cart/items/ {menu_item_id, quantity}
        items = _normalize_items(_cart_get(request))
        payload = _normalize_items([request.data])
        if payload:
            add = payload[0]
            # merge quantities if exists
            merged = False
            for it in items:
                if it["id"] == add["id"]:
                    it["quantity"] += add["quantity"]
                    merged = True
                    break
            if not merged:
                items.append(add)
            _cart_set(request, items)
        enriched, subtotal = _enrich(items)
        return Response({"items": enriched, "subtotal": str(subtotal), "currency": _currency()})

    @action(methods=["post"], detail=False, url_path="items/remove", permission_classes=[AllowAny])
    def remove_item(self, request):
        # POST /api/orders/cart/items/remove/ {menu_item_id}
        pid = request.data.get("menu_item_id") or request.data.get("id")
        try:
            pid = int(pid)
        except Exception:
            pid = 0
        items = [it for it in _normalize_items(_cart_get(request)) if it["id"] != pid]
        _cart_set(request, items)
        enriched, subtotal = _enrich(items)
        return Response({"items": enriched, "subtotal": str(subtotal), "currency": _currency()})

    @action(methods=["post"], detail=False, url_path="reset_session", permission_classes=[AllowAny])
    def reset_session(self, request):
        request.session.flush()
        return Response({"status": "ok"})


# ---------- Orders ----------

class OrderViewSet(viewsets.ModelViewSet):
    """
    - GET  /api/orders/         -> list current user's orders (auth only)
    - POST /api/orders/         -> create order from session cart or request.items
                                  returns: {id, checkout_url, total, eta_minutes, external_options[]}
    - GET  /api/orders/{id}/    -> retrieve (owner or staff)
    """
    queryset = Order.objects.all().order_by("-id")

    # Auth rules:
    #  - list/retrieve: user must be authenticated
    #  - create: allow guests (attach user if logged in)
    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [AllowAny()]

    # If you have a serializer, we'll use it; otherwise we build JSON manually
    try:
        from .serializers import OrderReadSerializer  # type: ignore
        read_serializer = OrderReadSerializer
    except Exception:
        read_serializer = None

    def get_queryset(self):
        qs = super().get_queryset()
        if getattr(self.request.user, "is_staff", False):
            return qs
        # filter by either created_by or user field, whichever exists
        if hasattr(Order, "created_by"):
            return qs.filter(created_by=self.request.user)
        if hasattr(Order, "user"):
            return qs.filter(user=self.request.user)
        return qs.none()

    def list(self, request, *args, **kwargs):
        if self.read_serializer:
            ser = self.read_serializer(self.get_queryset(), many=True)
            return Response(ser.data)
        # fallback manual
        data = []
        for o in self.get_queryset():
            items = []
            for it in o.items.all():
                items.append({
                    "menu_item": getattr(it, "menu_item_id", None),
                    "quantity": it.quantity,
                    "unit_price": str(it.unit_price),
                    "line_total": str(Decimal(str(it.unit_price)) * it.quantity),
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
        Build an Order from:
          - request.data.items (flexible shape), else
          - session cart
        Returns a Stripe Checkout URL and optional aggregator links (DoorDash / Uber Eats).
        Also generates and saves a PDF invoice on the order.
        """
        raw_items = _normalize_items(request.data.get("items", []))
        if not raw_items:
            raw_items = _normalize_items(_cart_get(request))
        if not raw_items:
            return Response({"detail": "Cart is empty."}, status=400)

        enriched, subtotal = _enrich(raw_items)
        if subtotal <= 0:
            return Response({"detail": "Invalid cart."}, status=400)

        with transaction.atomic():
            order = Order()
            # attach user if present
            if hasattr(order, "created_by") and getattr(request, "user", None) and request.user.is_authenticated:
                order.created_by = request.user
            if hasattr(order, "user") and getattr(request, "user", None) and request.user.is_authenticated:
                order.user = request.user

            # optional service / customer fields
            payload = request.data or {}
            for fld, default in (
                ("service_type", "DINE_IN"),
                ("customer_name", ""),
                ("customer_email", ""),
                ("customer_phone", ""),
                ("customer_address", ""),
                ("notes", ""),
            ):
                if hasattr(order, fld):
                    setattr(order, fld, payload.get(fld) or default)

            # status flags
            if hasattr(order, "status") and not getattr(order, "status", None):
                order.status = "PENDING"
            if hasattr(order, "is_paid") and getattr(order, "is_paid", None) is None:
                try:
                    order.is_paid = False
                except Exception:
                    pass
            if hasattr(order, "currency"):
                order.currency = _currency()

            # totals if model has such fields
            for tf in ("total", "total_amount", "grand_total", "amount", "subtotal"):
                if hasattr(order, tf):
                    try:
                        setattr(order, tf, subtotal)
                        break
                    except Exception:
                        pass

            order.save()

            # items
            for it in enriched:
                oi = OrderItem(
                    order=order,
                    menu_item=MenuItem.objects.get(pk=it["id"]),
                    quantity=int(it["quantity"]),
                    unit_price=Decimal(str(it["unit_price"])),
                )
                oi.save()

            # try to persist a PDF invoice file
            try:
                save_invoice_pdf_file(order)
            except Exception:
                pass

        # Stripe checkout
        session = create_checkout_session(order)
        checkout_url = getattr(session, "url", None) if session else None

        # External aggregator links (DoorDash / UberEats)
        options = []
        dd = getattr(settings, "DOORDASH_ORDER_URL", "") or ""
        ue = getattr(settings, "UBEREATS_ORDER_URL", "") or ""
        if dd:
            options.append({"code": "doordash", "label": "Order via DoorDash", "url": dd})
        if ue:
            options.append({"code": "ubereats", "label": "Order via Uber Eats", "url": ue})

        # Clear session cart
        try:
            _cart_set(request, [])
        except Exception:
            pass

        return Response(
            {
                "id": order.id,
                "checkout_url": checkout_url,
                "total": str(subtotal),
                "currency": _currency(),
                "eta_minutes": 15,
                "external_options": options,
            },
            status=201,
        )
