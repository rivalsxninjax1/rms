from django.conf import settings
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class DailySales(models.Model):
    location = models.ForeignKey('core.Location', on_delete=models.CASCADE)
    date = models.DateField()
    total_orders = models.PositiveIntegerField(default=0)
    total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_tips = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cash_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    card_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    upi_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['location', 'date']

    def __str__(self):
        return f"{self.location.name} - {self.date}"

class ShiftReport(models.Model):
    location = models.ForeignKey('core.Location', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    shift_start = models.DateTimeField()
    shift_end = models.DateTimeField()
    opening_cash = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    closing_cash = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_orders = models.PositiveIntegerField(default=0)
    total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    is_closed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.shift_start.date()}"
