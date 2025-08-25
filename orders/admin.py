from __future__ import annotations

import csv
from django.contrib import admin
from django.http import HttpResponse
from django.utils.html import format_html

from .models import Order, OrderItem

# Optional Payment inline
try:
    from payments.models import Payment  # type: ignore
except Exception:
    Payment = None


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    raw_id_fields = ("menu_item",)


if Payment:
    class PaymentInline(admin.StackedInline):
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
    list_display = (
        "id",
        "created_by",
        "source",
        "table_number",
        "status",
        "is_paid",
        "subtotal",
        "tip_amount",
        "discount_amount",
        "discount_code",
        "created_at",
        "invoice_link",
    )
    list_filter = ("status", "source", "is_paid", "created_at")
    date_hierarchy = "created_at"
    inlines = [x for x in (OrderItemInline, PaymentInline) if x]
    search_fields = ("=id", "created_by__username", "discount_code", "external_order_id")
    raw_id_fields = ("created_by",)
    ordering = ("-created_at",)
    readonly_fields = ("invoice_pdf",)

    def invoice_link(self, obj: Order) -> str:
        invoice = getattr(obj, "invoice_pdf", None)
        if invoice:
            try:
                return format_html('<a href="{}" target="_blank" rel="noopener">PDF</a>', invoice.url)
            except Exception:
                return "-"
        return "-"
    invoice_link.short_description = "Invoice"

    actions = ["export_sales_csv"]

    def export_sales_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="sales.csv"'
        writer = csv.writer(response)
        writer.writerow([
            "Order ID", "Created At", "User", "Source", "Table",
            "Status", "Paid", "Subtotal", "Tip", "Discount", "Final Total", "Currency"
        ])
        for o in queryset:
            writer.writerow([
                o.id,
                o.created_at,
                getattr(o.created_by, "username", "") if o.created_by_id else "",
                o.source,
                o.table_number or "",
                o.status,
                "YES" if o.is_paid else "NO",
                str(o.subtotal),
                str(o.tip_amount),
                str(o.discount_amount),
                str(o.grand_total()),
                o.currency.upper(),
            ])
        return response
    export_sales_csv.short_description = "Export Sales (CSV)"
