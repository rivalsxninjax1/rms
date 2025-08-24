# payments/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import Payment

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "order_link", "provider", "amount", "currency", "is_paid", "created_at")
    list_filter = ("provider", "is_paid", "created_at")
    search_fields = ("=id", "order__id", "stripe_session_id", "stripe_payment_intent")
    readonly_fields = ("order", "provider", "amount", "currency", "is_paid", "stripe_session_id", "stripe_payment_intent", "created_at", "updated_at")
    ordering = ("-created_at",)

    def order_link(self, obj):
        try:
            return format_html('<a href="/admin/orders/order/{}/change/">Order #{}</a>', obj.order_id, obj.order_id)
        except Exception:
            return f"#{obj.order_id}"
    order_link.short_description = "Order"
