# payments/services.py
from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple

import stripe
from django.conf import settings
from django.urls import reverse
from io import BytesIO

from payments.models import Payment

logger = logging.getLogger(__name__)
stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")


def _site_url() -> str:
    """
    Normalized base URL for callbacks.
    Prefers SITE_URL, else DOMAIN, else localhost fallback.
    """
    site = (getattr(settings, "SITE_URL", "") or "").strip().rstrip("/")
    if site:
        return site
    dom = (getattr(settings, "DOMAIN", "") or "").strip().rstrip("/")
    if dom:
        return dom
    return "http://127.0.0.1:8000"


def _currency() -> str:
    cur = getattr(settings, "STRIPE_CURRENCY", "usd")
    return (cur or "usd").lower()


def _as_decimal(x) -> Decimal:
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))


def _money_cents(amount: Decimal) -> int:
    """
    Convert Decimal dollars to integer cents (minor units) safely.
    """
    cents = (_as_decimal(amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) * 100)
    return int(cents)


def _apply_order_discounts(order, total: Decimal) -> Decimal:
    """
    Apply optional discount fields, if present on the Order:
    - discount_percent / coupon_percent
    - discount_amount / coupon_amount
    - coupon relation with 'percent'
    """
    try:
        # Percent fields first
        for pf in ("discount_percent", "coupon_percent"):
            if hasattr(order, pf):
                p = getattr(order, pf) or 0
                if p:
                    total = total * (Decimal(100) - _as_decimal(p)) / Decimal(100)

        # Coupon relation (percent)
        if hasattr(order, "coupon") and getattr(order, "coupon", None):
            pct = getattr(order.coupon, "percent", 0)
            if pct:
                total = total * (Decimal(100) - _as_decimal(pct)) / Decimal(100)

        # Fixed amounts
        for af in ("discount_amount", "coupon_amount"):
            if hasattr(order, af):
                a = getattr(order, af) or 0
                if a:
                    total = total - _as_decimal(a)
    except Exception:
        pass

    return max(Decimal("0.00"), total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_order_total(order) -> Decimal:
    """
    Compute order total and apply discounts if present.
    Prefers order.total/grand_total(); otherwise sums items.
    """
    try:
        # Prefer explicit methods if available
        if hasattr(order, "grand_total"):
            return _as_decimal(order.grand_total()).quantize(Decimal("0.01"))
        if getattr(order, "total", None) is not None:
            return _as_decimal(order.total).quantize(Decimal("0.01"))

        # Fallback: sum items
        total = Decimal("0.00")
        for it in order.items.all():
            if hasattr(it, "line_total"):
                total += _as_decimal(it.line_total())
            else:
                qty = _as_decimal(getattr(it, "quantity", 0))
                unit = _as_decimal(getattr(it, "unit_price", 0))
                total += (qty * unit)
        total = total.quantize(Decimal("0.01"))
        return _apply_order_discounts(order, total)
    except Exception as e:
        logger.exception("Failed computing order total: %s", e)
        return Decimal("0.00")


def ensure_payment(order) -> Payment:
    """
    Get or create a Payment tied to the order. Keep amount/currency in sync.
    """
    currency = _currency()
    pay, _ = Payment.objects.get_or_create(
        order=order,
        defaults={"currency": currency, "provider": Payment.PROVIDER_STRIPE},
    )

    amount = compute_order_total(order)
    try:
        # If your model has amount/currency fields
        if hasattr(pay, "amount"):
            pay.amount = amount
        if hasattr(pay, "currency"):
            pay.currency = currency
        pay.save(update_fields=[f for f in ["amount", "currency"] if hasattr(pay, f)])
    except Exception:
        pass

    return pay


def create_checkout_session(order):
    """
    Create a Stripe Checkout Session for the order (single aggregate line).
    """
    if not stripe.api_key:
        raise RuntimeError("Stripe secret key is not configured.")

    payment = ensure_payment(order)
    amount = compute_order_total(order)
    if amount <= 0:
        raise ValueError("Order total must be greater than zero.")

    success_url = f"{_site_url()}{reverse('payments:checkout_success')}?order={order.id}&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{_site_url()}{reverse('payments:checkout_cancel')}?order={order.id}"

    line_items = [{
        "price_data": {
            "currency": _currency(),
            "product_data": {"name": f"Order #{order.id}"},
            "unit_amount": _money_cents(amount),
        },
        "quantity": 1,
    }]

    session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=line_items,
        metadata={"order_id": str(order.id)},
        success_url=success_url,
        cancel_url=cancel_url,
    )

    # Persist identifiers
    try:
        if hasattr(payment, "stripe_session_id"):
            payment.stripe_session_id = session.get("id", "") or getattr(session, "id", "")
        if hasattr(payment, "stripe_payment_intent"):
            payment.stripe_payment_intent = session.get("payment_intent", "") or getattr(session, "payment_intent", "") or ""
        payment.save(update_fields=[f for f in ["stripe_session_id", "stripe_payment_intent"] if hasattr(payment, f)])
    except Exception:
        logger.exception("Failed to persist Stripe IDs for order %s", order.id)

    return session


def mark_paid(order, payment_intent_id: Optional[str] = None, session_id: Optional[str] = None) -> None:
    """
    Mark the order and its Payment record as paid.
    """
    try:
        pay = ensure_payment(order)
        changed = False

        if hasattr(pay, "is_paid") and not pay.is_paid:
            pay.is_paid = True
            changed = True
        if payment_intent_id and hasattr(pay, "stripe_payment_intent"):
            pay.stripe_payment_intent = payment_intent_id
            changed = True
        if session_id and hasattr(pay, "stripe_session_id"):
            pay.stripe_session_id = session_id
            changed = True

        if changed:
            fields = []
            for f in ["is_paid", "stripe_payment_intent", "stripe_session_id"]:
                if hasattr(pay, f):
                    fields.append(f)
            pay.save(update_fields=fields)

        if hasattr(order, "status"):
            if getattr(order, "status") != "PAID":
                order.status = "PAID"
                order.save(update_fields=["status"])
    except Exception as e:
        logger.exception("mark_paid failed: %s", e)


# ---------- Optional: PDF invoice (safe no-op if reportlab not installed) ----------
def generate_order_invoice_pdf(order) -> Tuple[Optional[str], Optional[bytes]]:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
    except Exception:
        logger.info("reportlab not installed; skipping invoice pdf generation")
        return (None, None)

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    y = height - 30 * 1 * mm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(30 * mm, y, f"Invoice — Order #{order.id}")
    y -= 12 * mm

    c.setFont("Helvetica", 11)
    c.drawString(30 * mm, y, f"Total: {compute_order_total(order)} {_currency().upper()}")
    y -= 8 * mm

    try:
        for it in order.items.all():
            name = getattr(getattr(it, "menu_item", None), "name", "Item")
            qty = getattr(it, "quantity", 0)
            unit = getattr(it, "unit_price", 0)
            c.drawString(30 * mm, y, f"- {name} x {qty} @ {unit}")
            y -= 6 * mm
    except Exception:
        pass

    c.showPage()
    c.save()
    data = buf.getvalue()
    buf.close()

    filename = f"invoice_order_{order.id}.pdf"
    return (filename, data)


def save_invoice_pdf_file(order) -> Optional[str]:
    try:
        filename, pdf_bytes = generate_order_invoice_pdf(order)
        if not filename or not pdf_bytes:
            return None
        if hasattr(order, "invoice_pdf"):
            from django.core.files.base import ContentFile
            if not order.invoice_pdf:
                order.invoice_pdf.save(filename, ContentFile(pdf_bytes), save=True)
        return filename
    except Exception as e:
        logger.exception("Failed to save invoice PDF: %s", e)
        return None
