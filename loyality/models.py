# FILE: loyalty/models.py
from __future__ import annotations

from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone


class LoyaltyConfig(models.Model):
    TYPE_PERCENT = "PERCENT"
    TYPE_FIXED = "FIXED"
    TYPES = [(TYPE_PERCENT, "Percent"), (TYPE_FIXED, "Fixed amount")]

    threshold_tip_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("50.00"))
    reward_type = models.CharField(max_length=10, choices=TYPES, default=TYPE_PERCENT)
    reward_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("10.00"))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Loyalty Configuration"

    @classmethod
    def get_solo(cls) -> "LoyaltyConfig":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class LoyaltyProgress(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="loyalty_progress")
    total_tip = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} – tipped {self.total_tip}"

    def reset(self):
        self.total_tip = Decimal("0.00")
        self.save(update_fields=["total_tip"])


class LoyaltyReward(models.Model):
    TYPE_PERCENT = "PERCENT"
    TYPE_FIXED = "FIXED"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="loyalty_rewards")
    reward_type = models.CharField(max_length=10, choices=[(TYPE_PERCENT,"Percent"),(TYPE_FIXED,"Fixed")])
    reward_amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_redeemed = models.BooleanField(default=False)
    reserved_order_id = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    redeemed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} reward {self.reward_type} {self.reward_amount} redeemed={self.is_redeemed}"

    def as_discount_amount(self, subtotal):
        from decimal import Decimal
        if self.reward_type == self.TYPE_PERCENT:
            disc = (subtotal * (self.reward_amount / Decimal("100"))).quantize(Decimal("0.01"))
        else:
            disc = Decimal(str(self.reward_amount)).quantize(Decimal("0.01"))
        if disc > subtotal:
            disc = subtotal
        return disc
