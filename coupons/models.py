# coupons/models.py
from __future__ import annotations

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone


class Coupon(models.Model):
    code = models.CharField(
        max_length=64,
        unique=True,
        help_text="Phrase or code the user types (unique, case-insensitive recommended at UI).",
    )

    # Single source of truth for discount percent (0–100)
    percent = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percent discount (0–100).",
    )

    # Optional human-friendly phrase trigger
    phrase = models.CharField(
        max_length=128,
        blank=True,
        help_text="Optional human-readable phrase trigger.",
    )

    active = models.BooleanField(default=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_to = models.DateTimeField(null=True, blank=True)

    # Limits and counters
    max_uses = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Optional cap on total coupon uses across all orders.",
    )
    times_used = models.PositiveIntegerField(
        default=0,
        help_text="Usage counter (increment on successful paid orders).",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_coupons",
    )

    # IMPORTANT: Use default=timezone.now (no auto_now_add) to avoid interactive prompt
    created_at = models.DateTimeField(
        default=timezone.now,
        editable=False,
        help_text="Creation timestamp.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.code} (-{self.percent}%)"

    # Compatibility with services using is_live()
    def is_live(self) -> bool:
        return self.is_valid_now()

    def is_valid_now(self) -> bool:
        """Return True if the coupon is currently usable."""
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
