from django.db import models

class Payment(models.Model):
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="billing_payments",
        related_query_name="billing_payment",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=8, default="NPR")
    status = models.CharField(max_length=32, default="created")
    reference = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        verbose_name = "Billing Payment"
        verbose_name_plural = "Billing Payments"
    def __str__(self):
        return f"BillingPayment {self.pk} for Order {self.order_id} ({self.amount} {self.currency})"

class InvoiceSequence(models.Model):
    prefix = models.CharField(max_length=16, unique=True)
    last_number = models.PositiveIntegerField(default=0)
    class Meta:
        verbose_name = "Invoice Sequence"
        verbose_name_plural = "Invoice Sequences"
    def __str__(self): return f"{self.prefix}-{self.last_number:06d}"
    def next_invoice_no(self) -> str:
        self.last_number += 1
        self.save(update_fields=["last_number"])
        return f"{self.prefix}-{self.last_number:06d}"

class PaymentReceipt(models.Model):
    payment = models.ForeignKey(
        Payment, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="receipts", related_query_name="receipt",
    )
    receipt_no = models.CharField(max_length=32, unique=True, null=True, blank=True)
    issued_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, default="")
    class Meta:
        verbose_name = "Payment Receipt"
        verbose_name_plural = "Payment Receipts"
    def __str__(self):
        return f"Receipt {self.receipt_no or '-'} for BillingPayment {self.payment_id or '-'}"
