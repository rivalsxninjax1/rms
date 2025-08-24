# orders/admin.py
from __future__ import annotations

import csv
from django.contrib import admin
from django.http import HttpResponse
from django.utils.html import format_html

from .models import Order, OrderItem

# Optional: Payment (from payments app). If missing, admin still works.
try:
    from payments.models import Payment
except Exception:  # pragma: no cover
    Payment = None

# Optional: invoice generator helper. If missing, the action is a no-op.
try:
    from payments.services import save_invoice_pdf_file
except Exception:  # pragma: no cover
    def save_invoice_pdf_file(order):  # type: ignore
        """Safe no-op if invoice generator isn't available."""
        return None


class OrderItemInline(admin.TabularInline):
    """Inline to inspect order line items."""
    model = OrderItem
    extra = 0
    raw_id_fields = ("menu_item",)


if Payment:
    class PaymentInline(admin.StackedInline):
        """
        Read-only view of the related Payment (OneToOne via order).
        """
        model = Payment
        extra = 0
        can_delete = False
        fk_name = "order"
        fields = (
            "provider",
            "amount",
            "currency",
            "is_paid",
            "stripe_session_id",
            "stripe_payment_intent",
            "created_at",
            "updated_at",
        )
        readonly_fields = fields
else:
    PaymentInline = None


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """
    RMS-aligned Order admin:
    - Payment inline (read-only) when payments app is installed
    - Invoice link (if `invoice_pdf` FileField exists on Order)
    - Actions: Regenerate invoice PDF, Export sales CSV
    """
    list_display = (
        "id",
        "created_by",
        "customer_name",
        "customer_email",
        "status",
        "paid",
        "created_at",
        "invoice_link",
    )
    list_filter = ("status", "created_at")
    date_hierarchy = "created_at"
    inlines = [x for x in (OrderItemInline, PaymentInline) if x]

    search_fields = ("=id", "customer_name", "customer_email", "created_by__username", "created_by__email")
    raw_id_fields = ("created_by", "location")
    list_select_related = ("created_by", "location")
    ordering = ("-created_at",)

    actions = ["regenerate_invoice_pdf", "export_sales_csv"]

    # ---- helpers / columns ----
    def get_readonly_fields(self, request, obj=None):
        base = super().get_readonly_fields(request, obj)
        # If your Order has an invoice file field, show it read-only
        if hasattr(Order, "invoice_pdf"):
            return tuple(base) + ("invoice_pdf",)
        return base

    def paid(self, obj: Order) -> bool:
        """
        Paid status preference:
        - Payment.is_paid (if payments app present)
        - fallback to legacy Order.is_paid
        """
        try:
            if Payment and hasattr(obj, "payment"):
                return bool(getattr(obj.payment, "is_paid", False))
        except Exception:
            pass
        return bool(getattr(obj, "is_paid", False))
    paid.boolean = True
    paid.short_description = "Paid"

    def invoice_link(self, obj: Order) -> str:
        """
        Clickable PDF link if Order.invoice_pdf exists and is populated.
        """
        invoice = getattr(obj, "invoice_pdf", None)
        if invoice:
            try:
                return format_html('<a href="{}" target="_blank" rel="noopener">PDF</a>', invoice.url)
            except Exception:
                return "-"
        return "-"
    invoice_link.short_description = "Invoice"

    # ---- actions ----
    def regenerate_invoice_pdf(self, request, queryset):
        """
        Rebuild invoice PDF for selected orders. Safe even if helper is a no-op.
        """
        count = 0
        for order in queryset:
            try:
                save_invoice_pdf_file(order)  # should be idempotent
                count += 1
            except Exception:
                # keep processing; report how many succeeded
                continue
        self.message_user(request, f"Regenerated invoice for {count} order(s).")
    regenerate_invoice_pdf.short_description = "Regenerate invoice PDF"

    def export_sales_csv(self, request, queryset):
        """
        Export selected orders as CSV.
        Tip for daily sales: filter by 'created_at = Today' then run this action.
        """
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="sales.csv"'
        writer = csv.writer(response)
        writer.writerow(["Order ID", "Created At", "Customer", "Email", "Status", "Paid", "Amount", "Currency"])

        qs = queryset.select_related("payment")
        for o in qs:
            paid = False
            amount = ""
            currency = ""
            if hasattr(o, "payment") and o.payment:
                paid = bool(o.payment.is_paid)
                amount = o.payment.amount
                currency = (o.payment.currency or "").upper()
            elif hasattr(o, "is_paid"):
                paid = bool(o.is_paid)

            writer.writerow([
                o.id,
                o.created_at,
                o.customer_name,
                o.customer_email,
                o.status,
                "YES" if paid else "NO",
                amount,
                currency,
            ])
        return response
    export_sales_csv.short_description = "Export Sales (CSV)"
