from django.contrib import admin
from .models import Payment, InvoiceSequence, PaymentReceipt

@admin.register(Payment)
class BillingPaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "amount", "currency", "status", "created_at")
    list_filter = ("status", "currency")
    search_fields = ("reference",)
    autocomplete_fields = ("order",)

@admin.register(InvoiceSequence)
class InvoiceSequenceAdmin(admin.ModelAdmin):
    list_display = ("prefix", "last_number")
    search_fields = ("prefix",)

@admin.register(PaymentReceipt)
class PaymentReceiptAdmin(admin.ModelAdmin):
    list_display = ("receipt_no", "payment", "issued_at")
    search_fields = ("receipt_no",)
    autocomplete_fields = ("payment",)
