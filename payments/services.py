# payments/services.py
from __future__ import annotations

import logging
from decimal import Decimal
from io import BytesIO
from typing import Optional, Tuple

from django.conf import settings
from django.urls import reverse

import stripe
from payments.models import Payment

logger = logging.getLogger(__name__)
stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")


def _site_url() -> str:
    base = (getattr(settings, "SITE_URL", "") or "").rstrip("/")
    return base or "http://localhost:8000"


def _money_cents(amount: Decimal) -> int:
    return int(Decimal(amount).quantize(Decimal("0.01")) * 100)


def compute_order_total(order) -> Decimal:
    """
    Compute order total from Order/OrderItem.
    Uses order.total if present; otherwise sums line items.
    """
    try:
        total = getattr(order, "total", None)
        if total is not None:
            return Decimal(str(total)).quantize(Decimal("0.01"))
    except Exception:
        pass

    total = Decimal("0")
    try:
        for it in order.items.all():  # adjust if your related_name differs
            line_total = getattr(it, "line_total", None)
            if line_total is not None:
                total += Decimal(str(line_total))
            else:
                qty = Decimal(str(getattr(it, "quantity", 0)))
                unit = Decimal(str(getattr(it, "unit_price", 0)))
                total += (qty * unit)
    except Exception as e:
        logger.exception("Failed computing order total: %s", e)
    return total.quantize(Decimal("0.01"))


def ensure_payment(order) -> Payment:
    """
    Get or create a Payment tied to the order. Keep amount/currency in sync.
    """
    currency = (getattr(settings, "STRIPE_CURRENCY", "usd") or "usd").lower()
    pay, _ = Payment.objects.get_or_create(order=order, defaults={"currency": currency})

    amount = compute_order_total(order)
    pay.amount = amount
    pay.currency = currency
    pay.save(update_fields=["amount", "currency"])
    return pay


def create_checkout_session(order):
    """
    Create Stripe Checkout Session for the order (single aggregate line).
    """
    payment = ensure_payment(order)
    amount = payment.amount
    if amount <= 0:
        raise ValueError("Order total is invalid")

    success_url = f"{_site_url()}{reverse('payments:checkout_success')}?order={order.id}"
    cancel_url = f"{_site_url()}{reverse('payments:checkout_cancel')}?order={order.id}"

    session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],  # includes Mastercard; Stripe manages brands
        line_items=[{
            "price_data": {
                "currency": payment.currency,
                "product_data": {"name": f"Order #{order.id}"},
                "unit_amount": _money_cents(amount),
            },
            "quantity": 1,
        }],
        metadata={"order_id": str(order.id)},
        success_url=success_url,
        cancel_url=cancel_url,
    )

    payment.stripe_session_id = session.get("id", "")
    payment.save(update_fields=["stripe_session_id"])
    return session


def mark_paid(order, payment_intent_id: Optional[str] = None):
    """
    Update Payment + Order to PAID (if your Order has a status field).
    """
    payment = ensure_payment(order)
    if not payment.is_paid:
        payment.is_paid = True
        if payment_intent_id:
            payment.stripe_payment_intent = payment_intent_id
        payment.save(update_fields=["is_paid", "stripe_payment_intent"])

    try:
        if hasattr(order, "status"):
            # keep your own status naming; "PAID" is common
            order.status = "PAID"
            order.save(update_fields=["status"])
    except Exception:
        pass


# ---------- Optional: PDF invoice (guarded) ----------
def generate_order_invoice_pdf(order) -> Tuple[Optional[str], Optional[bytes]]:
    """
    Generate invoice PDF and return (filename, bytes).
    If reportlab isn't installed, returns (None, None).
    """
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

    y = height - 30 * mm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(30 * mm, y, f"Invoice - Order #{order.id}")
    y -= 12 * mm

    c.setFont("Helvetica", 11)
    currency = getattr(settings, "STRIPE_CURRENCY", "usd").upper()
    c.drawString(30 * mm, y, f"Total: {compute_order_total(order)} {currency}")
    y -= 8 * mm

    try:
        for it in order.items.all():
            c.drawString(30 * mm, y, f"- {it.menu_item.name} x {it.quantity} @ {it.unit_price}")
            y -= 6 * mm
    except Exception:
        pass

    c.showPage()
    c.save()
    data = buf.getvalue()
    buf.close()

    filename = f"invoice_order_{order.id}.pdf"
    return (filename, data)


# ---------- Compatibility helper ----------
def save_invoice_pdf_file(order) -> Optional[str]:
    """
    Back-compat wrapper expected by older code:
    - generates the invoice PDF
    - if the Order model has an 'invoice_pdf' FileField, saves into it
    - returns the filename (or None if skipped)
    """
    try:
        filename, pdf_bytes = generate_order_invoice_pdf(order)
        if not filename or not pdf_bytes:
            return None

        # Save to Order.invoice_pdf if present
        if hasattr(order, "invoice_pdf"):
            from django.core.files.base import ContentFile
            order.invoice_pdf.save(filename, ContentFile(pdf_bytes), save=True)
        return filename
    except Exception as e:
        logger.exception("Failed to save invoice PDF: %s", e)
        return None
