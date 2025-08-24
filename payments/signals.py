# FILE: payments/signals.py
from __future__ import annotations
import logging
from decimal import Decimal

from django.db.models.signals import post_save
from django.dispatch import receiver

from payments.models import Payment
from payments.services import compute_order_total, save_invoice_pdf_file

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Payment)
def on_payment_paid(sender, instance: Payment, created: bool, **kwargs):
    """
    When a Payment becomes paid:
    - Ensure a Billing.Payment + PaymentReceipt exist
    - Generate a PDF invoice if reportlab is installed
    - Update DailySales (if reports app is installed)
    Safe to call multiple times; guarded by existence checks.
    """
    try:
        if not instance.is_paid:
            return

        order = getattr(instance, "order", None)
        if not order:
            return

        amount = instance.amount or compute_order_total(order)
        currency = instance.currency or getattr(order, "currency", "NPR")

        # Mirror into billing app (idempotent-ish)
        try:
            from billing.models import Payment as BillingPayment, PaymentReceipt, InvoiceSequence
            bp, bp_created = BillingPayment.objects.get_or_create(
                order=order,
                defaults={
                    "amount": amount,
                    "currency": currency,
                    "status": "paid",
                    "reference": instance.stripe_payment_intent or instance.stripe_session_id or "",
                }
            )
            if not bp_created and bp.status != "paid":
                bp.status = "paid"
                bp.amount = amount
                bp.currency = currency
                bp.save(update_fields=["status", "amount", "currency"])

            # Create a receipt if none exists
            if not PaymentReceipt.objects.filter(payment=bp).exists():
                seq, _ = InvoiceSequence.objects.get_or_create(prefix="INV")
                receipt_no = seq.next_invoice_no()
                PaymentReceipt.objects.create(payment=bp, receipt_no=receipt_no)
        except Exception as e:
            logger.info("Billing mirror skipped/failed: %s", e)

        # Generate and attach invoice PDF (best-effort)
        try:
            save_invoice_pdf_file(order)
        except Exception as e:
            logger.info("Invoice PDF skipped: %s", e)

        # Update daily sales if reports app is present
        try:
            from reports.models import DailySales
            loc_id = getattr(order, "location_id", None)
            if loc_id:
                ds, _ = DailySales.objects.get_or_create(location_id=loc_id, date=order.created_at.date())
                ds.total_orders = int(ds.total_orders or 0) + 1
                ds.total_sales = (ds.total_sales or Decimal("0")) + (amount or Decimal("0"))
                ds.save(update_fields=["total_orders", "total_sales"])
        except Exception as e:
            logger.info("DailySales update skipped: %s", e)
    except Exception as e:
        logger.exception("on_payment_paid failed: %s", e)
