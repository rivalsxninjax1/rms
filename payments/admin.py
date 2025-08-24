from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "provider", "amount", "currency", "is_paid", "stripe_session_id", "created_at")
    list_filter = ("provider", "is_paid", "currency")
    search_fields = ("id", "order__id", "stripe_session_id", "stripe_payment_intent")
    readonly_fields = ("created_at", "updated_at")
