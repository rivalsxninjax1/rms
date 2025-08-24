from django.conf import settings
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Table(models.Model):
    location = models.ForeignKey('core.Location', on_delete=models.CASCADE, related_name='tables')
    table_number = models.CharField(max_length=50)
    capacity = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['location', 'table_number']

    def __str__(self):
        return f"Table {self.table_number} ({self.location.name})"

class Reservation(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('SEATED', 'Seated'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('NO_SHOW', 'No Show'),
    ]
    
    location = models.ForeignKey('core.Location', on_delete=models.CASCADE)
    table = models.ForeignKey(Table, on_delete=models.CASCADE, null=True, blank=True)
    customer_name = models.CharField(max_length=200)
    customer_phone = models.CharField(max_length=20)
    customer_email = models.EmailField(blank=True)
    party_size = models.PositiveIntegerField()
    reservation_date = models.DateField()
    reservation_time = models.TimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.customer_name} - {self.reservation_date} {self.reservation_time}"
