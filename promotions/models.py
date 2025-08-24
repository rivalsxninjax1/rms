from django.db import models
from django.utils import timezone

class Coupon(models.Model):
    code = models.CharField(max_length=32, unique=True)
    discount_percent = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_to = models.DateTimeField(null=True, blank=True)

    def is_valid_now(self):
        now = timezone.now()
        return self.active and (not self.valid_from or now >= self.valid_from) and (not self.valid_to or now <= self.valid_to)

    def __str__(self): return f"{self.code} ({self.discount_percent}%)"
