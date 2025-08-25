from __future__ import annotations

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone


class Coupon(models.Model):
    code = models.CharField(max_length=64, unique=True)
    percent = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percent discount (0–100).",
    )
    phrase = models.CharField(max_length=128, blank=True)

    active = models.BooleanField(default=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_to = models.DateTimeField(null=True, blank=True)
    max_uses = models.PositiveIntegerField(null=True, blank=True)
    times_used = models.PositiveIntegerField(default=0)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="created_coupons",
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.code} (-{self.percent}%)"

    def is_valid_now(self) -> bool:
        if not self.active:
            return False
        now = timezone.now()
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_to and now > self.valid_to:
            return False
        if self.max_uses is not None and self.times_used >= self.max_uses:
            return False
        if self.percent <= 0:
            return False
        return True
