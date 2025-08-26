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

# Payments fallbacks (safe if app missing)
try:
    from payments.services import create_checkout_session, save_invoice_pdf_file  # type: ignore
except Exception:  # pragma: no cover
    def create_checkout_session(order: Order):
        class _Dummy: url = None
        return _Dummy()
    def save_invoice_pdf_file(order: Order):  # noqa
        return None

# Coupons services (percent-based)
try:
    from coupons.services import find_active_coupon, compute_discount_for_order  # type: ignore
except Exception:  # pragma: no cover
    def find_active_coupon(code: str): return None
    def compute_discount_for_order(order: Order, coupon, user):
        return False, Decimal("0.00"), "coupon service missing"

# Loyalty services (safe stubs)
try:
    from loyalty.services import get_available_reward_for_user, reserve_reward_for_order  # type: ignore
except Exception:  # pragma: no cover
    def get_available_reward_for_user(user): return None
    def reserve_reward_for_order(reward, order: Order): return None


# ---------- Helpers ----------
def _currency() -> str:
    return getattr(settings, "STRIPE_CURRENCY", "usd").lower()

def _fetch_menu_item(mi_id: int) -> Tuple[str, Decimal]:
    mi = MenuItem.objects.get(pk=mi_id)
    price = Decimal(str(getattr(mi, "price", 0)))
    return (mi.name, price)

def _normalize_items(items_in: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for raw in items_in or []:
        pid = raw.get("menu_item_id") or raw.get("menu_item") or raw.get("product") or raw.get("id")
        qty = raw.get("quantity") or raw.get("qty") or 1
        try:
            pid = int(pid); qty = int(qty)
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

def _cart_meta_get(request) -> Dict[str, Any]:
    return dict(request.session.get("cart_meta", {}))

def _cart_meta_set(request, meta: Dict[str, Any]):
    request.session["cart_meta"] = meta
    request.session.modified = True

def _enrich(items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Decimal]:
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


# ---------- Session Cart API ----------
class SessionCartViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def list(self, request):
        items = _normalize_items(_cart_get(request))
        enriched, subtotal = _enrich(items)
        meta = _cart_meta_get(request)
        return Response({"items": enriched, "subtotal": str(subtotal), "currency": _currency(), "meta": meta})

    def create(self, request):
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
        # Accept 'UBER_EATS' (canonical) and 'UBEREATS' alias
        allowed = {"DINE_IN", "UBER_EATS", "DOORDASH"}
        meta = _cart_meta_get(request)
        st = str(request.data.get("service_type", "")).upper().strip()
        if st == "UBEREATS":
            st = "UBER_EATS"
        if st and st in allowed:
            meta["service_type"] = st
        table = request.data.get("table_number") or request.data.get("table_num")
        if table:
            try:
                meta["table_number"] = int(table)
            except Exception:
                pass
        _cart_meta_set(request, meta)
        return Response({"status": "ok", "meta": meta})

    @action(methods=["post"], detail=False, url_path="reset_session", permission_classes=[AllowAny])
    def reset_session(self, request):
        for k in ("cart", "cart_meta", "applied_coupon"):
            request.session.pop(k, None)
        request.session.modified = True
        return Response({"status": "ok"})

    @action(methods=["post"], detail=False, url_path="merge", permission_classes=[IsAuthenticated])
    def merge(self, request):
        """
        Merge session cart into user's open PENDING order (no duplicates: quantities are summed).
        Leaves everything else untouched.
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
                order = Order.objects.create(created_by=request.user, status="PENDING", currency=_currency())

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

            # Optionally clear session cart after merge (keeps system consistent)
            _cart_set(request, [])

        return Response({"status": "ok", "order_id": order.id})


# ---------- Orders (Checkout) ----------
class OrderViewSet(viewsets.ModelViewSet):
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
            total = o.grand_total()
            data.append({
                "id": o.id,
                "status": o.status,
                "is_paid": o.is_paid,
                "source": o.source,
                "table_number": o.table_number,
                "external_order_id": o.external_order_id,
                "tip_amount": str(o.tip_amount),
                "discount_amount": str(o.discount_amount),
                "discount_code": o.discount_code,
                "items": items,
                "total": str(total),
                "created_at": timezone.localtime(getattr(o, "created_at", timezone.now())),
            })
        return Response(data)

    def create(self, request, *args, **kwargs):
        """
        Build an Order for checkout:
          - If authenticated and a PENDING order exists -> reuse it
          - Else build from session cart or request.data.items
          - Apply: source + table + tip + coupon + loyalty
          - Return Stripe Checkout session URL
        """
        user = getattr(request, "user", None)

        # ---- Parse incoming options
        body_source_raw = (request.data.get("service_type") or request.data.get("source") or "").upper().strip()
        # accept UBEREATS alias, normalize to UBER_EATS
        if body_source_raw == "UBEREATS":
            body_source_raw = "UBER_EATS"
        body_source = body_source_raw if body_source_raw in {"DINE_IN", "UBER_EATS", "DOORDASH"} else None

        table_number = request.data.get("table_number") or request.data.get("table_num")
        tip_percent = request.data.get("tip_percent")
        tip_amount_custom = request.data.get("tip_amount") or request.data.get("tip_custom")
        coupon_code = (request.data.get("coupon") or request.data.get("coupon_code") or "").strip()

        # Session defaults
        session_meta = _cart_meta_get(request)
        session_source = str(session_meta.get("service_type") or "").upper().strip()
        if session_source == "UBEREATS":
            session_source = "UBER_EATS"

        source = body_source or session_source or "DINE_IN"
        if source not in {"DINE_IN", "UBER_EATS", "DOORDASH"}:
            source = "DINE_IN"

        with transaction.atomic():
            order = None
            items_source: List[Dict[str, Any]] = []

            if user and user.is_authenticated:
                order = (
                    Order.objects.filter(created_by=user, status="PENDING", is_paid=False)
                    .prefetch_related("items__menu_item").first()
                )
                if not order:
                    order = Order(created_by=user, status="PENDING", currency=_currency())
                    order.save()

                if not order.items.exists():
                    items_source = _normalize_items(request.data.get("items", [])) or _normalize_items(_cart_get(request))
            else:
                items_source = _normalize_items(request.data.get("items", [])) or _normalize_items(_cart_get(request))

            # Create items if needed
            if items_source and (not order or not order.items.exists()):
                enriched, subtotal = _enrich(items_source)
                if subtotal <= 0:
                    return Response({"detail": "Cart is empty."}, status=400)
                if not order:
                    order = Order(status="PENDING", currency=_currency())
                    order.save()
                order.items.all().delete()
                for it in enriched:
                    OrderItem.objects.create(
                        order=order,
                        menu_item_id=it["id"],
                        quantity=int(it["quantity"]),
                        unit_price=Decimal(str(it["unit_price"])),
                    )

            # Set meta/source/table
            order.source = source
            if source == "DINE_IN":
                if table_number is None:
                    table_number = session_meta.get("table_number") or session_meta.get("table_num")
                if table_number:
                    try:
                        order.table_number = int(table_number)
                    except Exception:
                        pass

            order.currency = _currency()
            order.sync_subtotals()

            # ---- Tips
            tip_dec = Decimal("0.00")
            if tip_amount_custom not in (None, "", 0, "0"):
                try:
                    tip_dec = Decimal(str(tip_amount_custom))
                except Exception:
                    tip_dec = Decimal("0.00")
            elif tip_percent not in (None, "", 0, "0"):
                try:
                    pct = Decimal(str(tip_percent)) / Decimal("100")
                    tip_dec = (order.subtotal * pct).quantize(Decimal("0.01"))
                except Exception:
                    tip_dec = Decimal("0.00")
            order.tip_amount = tip_dec

            # ---- Coupon (percent-based)
            order.discount_amount = Decimal("0.00")
            order.discount_code = ""
            if coupon_code:
                c = find_active_coupon(coupon_code)
                ok, disc, _reason = compute_discount_for_order(order, c, user)
                if ok:
                    order.discount_amount = disc
                    order.discount_code = c.code

            # ---- Loyalty (auto-apply once when available)
            if user and user.is_authenticated and not getattr(order, "loyalty_reward_applied", False):
                reward = get_available_reward_for_user(user)
                if reward:
                    reserve_reward_for_order(reward, order)
                    order.discount_amount = (order.discount_amount or Decimal("0.00")) + reward.as_discount_amount(order.subtotal)
                    order.loyalty_reward_applied = True
                    if not order.discount_code:
                        order.discount_code = "LOYALTY"

            order.full_clean()
            order.save()

            # Optional invoice generation
            try:
                save_invoice_pdf_file(order)
            except Exception:
                pass

            # Stripe Checkout
            session = create_checkout_session(order)
            checkout_url = getattr(session, "url", None) if session else None

            return Response(
                {
                    "id": order.id,
                    "checkout_url": checkout_url,
                    "total": str(order.grand_total()),
                    "currency": _currency(),
                    "source": order.source,
                    "table_number": getattr(order, "table_number", None),
                },
                status=201,
            )
