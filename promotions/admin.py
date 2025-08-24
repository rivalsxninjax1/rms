# promotions/admin.py
from django.contrib import admin
from .models import Coupon


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ("code", "discount_percent", "active", "valid_from", "valid_to")
    list_filter = ("active",)
    search_fields = ("code",)
