from django.db import models
from django.conf import settings
from menu.models import MenuItem


class Order(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("PAID", "Paid"),
        ("FAILED", "Failed"),
        ("CANCELLED", "Cancelled"),
    ]

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="orders",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    location = models.ForeignKey(
        "core.Location",
        related_name="orders",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="PENDING")
    service_type = models.CharField(max_length=30, blank=True, default="")

    customer_name = models.CharField(max_length=200, blank=True, default="")
    customer_phone = models.CharField(max_length=20, blank=True, default="")
    customer_email = models.EmailField(blank=True, default="")
    notes = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    placed_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    # Payment state (used by Stripe integration)
    is_paid = models.BooleanField(default=False)
    stripe_session_id = models.CharField(max_length=255, blank=True, default="")
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, default="")

    # Generated PDF invoice stored in MEDIA_ROOT/orders/
    invoice_pdf = models.FileField(upload_to="orders/", blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.pk}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    menu_item = models.ForeignKey(
        MenuItem,
        related_name="order_items",
        on_delete=models.PROTECT,
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Optional snapshot fields (keeps your KDS/ticket ideas compatible)
    modifiers = models.JSONField(default=list, blank=True)
    notes = models.CharField(max_length=255, blank=True, default="")

    def __str__(self):
        return f"{self.menu_item} x {self.quantity}"
