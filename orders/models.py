# orders/models.py
from __future__ import annotations

from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from menu.models import MenuItem


class Order(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("PAID", "Paid"),
        ("FAILED", "Failed"),
        ("CANCELLED", "Cancelled"),
    ]
    SOURCE_CHOICES = [
        ("DINE_IN", "Dine-In"),
        ("UBER_EATS", "Uber Eats"),
        ("DOORDASH", "DoorDash"),
    ]

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="orders",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="PENDING")
    is_paid = models.BooleanField(default=False)
    currency = models.CharField(max_length=8, default="usd")

    # Ordering source & related info
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="DINE_IN")
    table_number = models.PositiveIntegerField(null=True, blank=True)
    external_order_id = models.CharField(max_length=64, blank=True, default="")

    # Totals
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    tip_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount_code = models.CharField(max_length=64, blank=True, default="")
    loyalty_reward_applied = models.BooleanField(default=False)

    # Optional reservation relation (ok if app not installed; keep null/blank)
    reservation = models.ForeignKey(
        "reservations.Reservation",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
    )

    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    # Optional: PDF invoice file
    invoice_pdf = models.FileField(upload_to="invoices/", blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Order #{self.pk}"

    # ---------- Totals ----------
    def items_subtotal(self) -> Decimal:
        total = Decimal("0.00")
        for it in self.items.all():
            total += (Decimal(str(it.unit_price)) * int(it.quantity))
        return total.quantize(Decimal("0.01"))

    def grand_total(self) -> Decimal:
        sub = self.items_subtotal()
        tip = Decimal(str(self.tip_amount or 0))
        disc = Decimal(str(self.discount_amount or 0))
        total = sub + tip - disc
        if total < 0:
            total = Decimal("0.00")
        return total.quantize(Decimal("0.01"))

    def clean(self):
        if self.source == "DINE_IN" and not self.table_number:
            raise ValidationError("Table number is required for Dine-In orders.")
        if self.discount_amount and self.discount_amount < 0:
            raise ValidationError("Discount cannot be negative.")
        if self.tip_amount and self.tip_amount < 0:
            raise ValidationError("Tip cannot be negative.")

    def sync_subtotals(self):
        self.subtotal = self.items_subtotal()

    def save(self, *args, **kwargs):
        try:
            self.sync_subtotals()
        except Exception:
            pass
        super().save(*args, **kwargs)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    menu_item = models.ForeignKey(MenuItem, related_name="order_items", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # optional snapshots / notes
    modifiers = models.JSONField(default=list, blank=True)
    notes = models.CharField(max_length=255, blank=True, default="")

    def line_total(self) -> Decimal:
        return (Decimal(str(self.unit_price)) * int(self.quantity)).quantize(Decimal("0.01"))

    def __str__(self) -> str:
        return f"{self.menu_item} x {self.quantity}"
